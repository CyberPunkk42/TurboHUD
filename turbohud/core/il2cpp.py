"""Finding classes and fields by name in a running IL2CPP game, such as TSU.

TSU is built with IL2CPP. Its type information (global-metadata.dat) is mapped into the
game's memory, and every class the game uses has a runtime record that points to its
name there, to its fields (each with name and position) and to its static fields. So
nothing here needs a fixed address: everything is looked up by name at every start.

Reading goes through a `read(address, size) -> bytes` callable, so this runs and tests
without a game.
"""

import struct
from dataclasses import dataclass, field

# IL2CPP runtime layouts (Unity 2021.3, metadata version 29, 64-bit).
CLASS_NAME = 0x10
CLASS_NAMESPACE = 0x18
CLASS_PARENT = 0x58
CLASS_FIELDS = 0x80
CLASS_STATIC_FIELDS = 0xB8
FIELD_INFO_SIZE = 32  # name, type, parent, offset (int32), token
FIELD_BLOCK = 32  # FieldInfo records read at once
NAME_LIMIT = 96  # bytes read for a field's name
TYPE_ATTRS = 8  # in Il2CppType, after its data pointer
TYPE_CODE = 10  # in Il2CppType: the type's kind (Il2CppTypeEnum), after the attributes
# Il2CppTypeEnum values of the simple types, with their struct format.
SIMPLE_TYPES = {
    0x02: ('bool', '<?'),
    0x04: ('sbyte', '<b'),
    0x05: ('byte', '<B'),
    0x06: ('short', '<h'),
    0x07: ('ushort', '<H'),
    0x08: ('int', '<i'),
    0x09: ('uint', '<I'),
    0x0A: ('long', '<q'),
    0x0B: ('ulong', '<Q'),
    0x0C: ('float', '<f'),
    0x0D: ('double', '<d'),
}
TYPE_VALUETYPE = 0x11  # a struct, such as a Vector3
FIELD_ATTRIBUTE_STATIC = 0x10
LIST_ITEMS = 0x10
LIST_SIZE = 0x18
ARRAY_LENGTH = 0x18
ARRAY_DATA = 0x20


class ReadError(OSError):
    """The game refused a read: the address is not mapped (a stale pointer)."""


class NotFound(Exception):
    """The game is not in a state that has this data (menu, loading), or it changed."""


class Memory:
    """Reads the game's memory through a `read(address, size) -> bytes` callable.
    `regions` are (start, end, permissions, offset, path) from the game's memory map, or
    a callable giving them as they are now: the game's memory grows between its menu and
    a race, and a class loaded later lies outside an old list."""

    def __init__(self, read, regions, read_many=None, find_pointers=None, searcher=None):
        self.read = read
        self._regions = regions
        self._read_many = read_many
        # (value) -> addresses holding it, searched where the memory is (the probe);
        # None where only reads are possible.
        self.find_pointers = find_pointers
        # (regions, value) -> addresses holding it, for a reader that searches in its
        # own way (on Windows and in CrossOver: in paced pieces); None reads here.
        self._searcher = searcher

    @property
    def regions(self):
        return self._regions() if callable(self._regions) else self._regions

    def read_many(self, addresses, size):
        """The same number of bytes at many addresses, in one request where the reader
        can (the probe can); None for an address that cannot be read."""
        if self._read_many is not None:
            return self._read_many(list(addresses), size)
        values = []
        for address in addresses:
            try:
                values.append(self.read(address, size))
            except OSError:
                values.append(None)
        return values

    def u64(self, address):
        return struct.unpack('<Q', self.read(address, 8))[0]

    def i32(self, address):
        return struct.unpack('<i', self.read(address, 4))[0]

    def u32(self, address):
        return struct.unpack('<I', self.read(address, 4))[0]

    def u16(self, address):
        return struct.unpack('<H', self.read(address, 2))[0]

    def u8(self, address):
        return self.read(address, 1)[0]

    def f32(self, address):
        return struct.unpack('<f', self.read(address, 4))[0]

    def cstring(self, address, limit=128):
        return self.read(address, limit).split(b'\0', 1)[0].decode('utf-8', 'replace')

    def search(self, regions, value, chunk=32 << 20):
        """Addresses (8-aligned) in `regions` that hold the 64-bit `value`."""
        if self._searcher is not None:
            return self._searcher(regions, value)
        pattern = struct.pack('<Q', value)
        hits = []
        for start, end in regions:
            address = start
            while address < end:
                size = min(chunk, end - address)
                try:
                    data = self.read(address, size)
                except OSError:
                    address += size
                    continue
                index = data.find(pattern)
                while index != -1:
                    if index % 8 == 0:
                        hits.append(address + index)
                    index = data.find(pattern, index + 1)
                address += size
        return hits


@dataclass
class Il2Cpp:
    """Finds classes and fields by name in a running IL2CPP game."""

    memory: Memory
    metadata: bytes
    metadata_base: int
    _fields: dict = field(default_factory=dict)

    def string_address(self, text):
        index = self.metadata.find(b'\0' + text.encode() + b'\0')
        if index < 0:
            raise NotFound(f'{text!r} is not in the game metadata')
        return self.metadata_base + index + 1

    def find_class(self, namespace, name):
        """The runtime class record. Class records live in the C heap (`[heap]`)."""
        name_address = self.string_address(name)
        namespace_address = self.string_address(namespace) if namespace else None
        heap = [(start, end) for start, end, *_rest, path in self.memory.regions if path == '[heap]']
        for hit in self.memory.search(heap, name_address):
            klass = hit - CLASS_NAME
            if namespace_address is None or self.memory.u64(klass + CLASS_NAMESPACE) == namespace_address:
                return klass
        raise NotFound(f'class {namespace}.{name} is not loaded')

    def own_fields(self, klass):
        """[(name, offset, is_static, type_code)] declared by `klass` itself, read in a
        few batched requests: its FieldInfo records in blocks, then all names and types
        at once. type_code is the field's Il2CppTypeEnum value."""
        entry = self.memory.u64(klass + CLASS_FIELDS)
        records = []
        while entry:
            block = self.memory.read(entry, FIELD_INFO_SIZE * FIELD_BLOCK)
            more = False
            for index in range(FIELD_BLOCK):
                name, type_, parent, offset = struct.unpack_from('<QQQi', block, index * FIELD_INFO_SIZE)
                if parent != klass:
                    break
                records.append((name, type_, offset))
            else:
                more = True
            entry = entry + FIELD_INFO_SIZE * FIELD_BLOCK if more else 0
        if not records:
            return []
        names = self.memory.read_many([name for name, _type, _offset in records], NAME_LIMIT)
        types = self.memory.read_many([type_ + TYPE_ATTRS for _name, type_, _offset in records], 3)
        found = []
        for (_name, _type, offset), name, kind in zip(records, names, types):
            if name is None or kind is None:
                raise ReadError('field record not readable')
            attrs, code = struct.unpack('<HB', kind)
            text = name.split(b'\0', 1)[0].decode('utf-8', 'replace')
            found.append((text, offset, bool(attrs & FIELD_ATTRIBUTE_STATIC), code))
        return found

    def field_list(self, klass):
        """[(name, offset, is_static, type_code)] of `klass` and its parents."""
        found = []
        while klass:
            found.extend(self.own_fields(klass))
            klass = self.memory.u64(klass + CLASS_PARENT)
        return found

    def fields(self, klass):
        """{name: (offset, is_static)} of `klass` and its parents; a field of the class
        itself wins over a parent's of the same name."""
        if klass not in self._fields:
            found = {}
            for name, offset, is_static, _code in self.field_list(klass):
                found.setdefault(name, (offset, is_static))
            self._fields[klass] = found
        return self._fields[klass]

    def class_name(self, obj):
        klass = self.memory.u64(obj)
        return f'{self.memory.cstring(self.memory.u64(klass + CLASS_NAMESPACE))}.{self.memory.cstring(self.memory.u64(klass + CLASS_NAME))}'

    def offset(self, obj, name):
        try:
            return self.fields(self.memory.u64(obj))[name][0]
        except KeyError:
            raise NotFound(f'no field {name}') from None

    def ref(self, obj, *names):
        """Follow reference fields by name; raises NotFound on a null."""
        for name in names:
            obj = self.memory.u64(obj + self.offset(obj, name))
            if not obj:
                raise NotFound(f'{name} is null')
        return obj

    def static_ref(self, klass, name):
        offset, is_static = self.fields(klass)[name]
        statics = self.memory.u64(klass + CLASS_STATIC_FIELDS)
        value = self.memory.u64(statics + offset) if is_static and statics else 0
        if not value:
            raise NotFound(f'static {name} is null')
        return value

    def list_items(self, lst):
        array, size = self.memory.u64(lst + LIST_ITEMS), self.memory.i32(lst + LIST_SIZE)
        if not 0 <= size <= 1024:
            raise NotFound('implausible list size')
        if not size:
            return []
        data = self.memory.read(array + ARRAY_DATA, 8 * size)
        return list(struct.unpack(f'<{size}Q', data))

    def u32_list(self, lst):
        """All values of a List<uint>."""
        array, size = self.memory.u64(lst + LIST_ITEMS), self.memory.i32(lst + LIST_SIZE)
        if not 0 <= size <= 4096:
            raise NotFound('implausible list size')
        if not size:
            return ()
        return struct.unpack(f'<{size}I', self.memory.read(array + ARRAY_DATA, 4 * size))

    def first_u32(self, lst):
        """First uint32 of a List<uint>."""
        if self.memory.i32(lst + LIST_SIZE) < 1:
            raise NotFound('empty list')
        return self.memory.u32(self.memory.u64(lst + LIST_ITEMS) + ARRAY_DATA)
