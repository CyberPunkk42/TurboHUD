"""Live lap data from TSU's memory, found by name at every start (no fixed addresses).

TSU is built with IL2CPP. Its type information (global-metadata.dat) is mapped into the
game's memory, and every class the game uses has a runtime record that points to its
name there, to its fields (each with name and position) and to its static fields. So the
reader finds things by name:

    TS.Services (static sm_instance)
      .m_activeServer.m_eventListener          the event controller
      .m_eventState                            TS.EventState
          .times                               race clock: ticks, time, time limit
          .players[i]                          TS.EventPlayer; the local one has
                                               m_localHumanIndex >= 0
              .m_stats                         TS.PlayerRaceStats
                  .m_lapsCompleted, .m_lapsToFinish, .m_startTime
                  .m_checkpointTimesForLaps[lap].m_times[0]   when that lap started

All times are whole numbers in steps of 0.1 ms. A lap's time is the start of the next
lap minus its own start; the current lap is the race clock minus its start.

It reads through the memory probe's socket (tsu_memory_probe.py), only reads, and needs
TSU started through the probe. Run it while driving:

    python3 -B experiments/tsu_lap_reader.py
"""

import socket
import struct
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

UNITS_PER_SECOND = 10_000

# IL2CPP runtime layouts (Unity 2021.3, metadata version 29, 64-bit).
CLASS_NAME = 0x10
CLASS_NAMESPACE = 0x18
CLASS_PARENT = 0x58
CLASS_FIELDS = 0x80
CLASS_STATIC_FIELDS = 0xB8
FIELD_INFO_SIZE = 32  # name, type, parent, offset (int32), token
TYPE_ATTRS = 8  # in Il2CppType, after its data pointer
FIELD_ATTRIBUTE_STATIC = 0x10
LIST_ITEMS = 0x10
LIST_SIZE = 0x18
ARRAY_LENGTH = 0x18
ARRAY_DATA = 0x20
# EventState.times: ticks, time, ..., time limit (int32 each).
TIMES_TICKS, TIMES_NOW, TIMES_LIMIT = 0, 4, 20


class ReadError(OSError):
    """The game refused a read: the address is not mapped (a stale pointer)."""


class NotFound(Exception):
    """The game is not in a state that has this data (menu, loading), or it changed."""


class Memory:
    """Reads TSU's memory through a `read(address, size) -> bytes` callable."""

    def __init__(self, read, regions):
        self.read = read
        self.regions = regions

    def u64(self, address):
        return struct.unpack('<Q', self.read(address, 8))[0]

    def i32(self, address):
        return struct.unpack('<i', self.read(address, 4))[0]

    def u32(self, address):
        return struct.unpack('<I', self.read(address, 4))[0]

    def u16(self, address):
        return struct.unpack('<H', self.read(address, 2))[0]

    def cstring(self, address, limit=128):
        return self.read(address, limit).split(b'\0', 1)[0].decode('utf-8', 'replace')

    def search(self, regions, value, chunk=32 << 20):
        """Addresses (8-aligned) in `regions` that hold the 64-bit `value`."""
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
        name_address = self.string_address(name)
        namespace_address = self.string_address(namespace) if namespace else None
        heap = [(start, end) for start, end, *_rest, path in self.memory.regions if path == '[heap]']
        for hit in self.memory.search(heap, name_address):
            klass = hit - CLASS_NAME
            if namespace_address is None or self.memory.u64(klass + CLASS_NAMESPACE) == namespace_address:
                return klass
        raise NotFound(f'class {namespace}.{name} is not loaded')

    def fields(self, klass):
        """{name: (offset, is_static)} of `klass` and its parents."""
        if klass in self._fields:
            return self._fields[klass]
        found = {}
        current = klass
        while current:
            entry = self.memory.u64(current + CLASS_FIELDS)
            while entry:
                name, type_, parent = struct.unpack('<QQQ', self.memory.read(entry, 24))
                if parent != current:
                    break
                offset = self.memory.i32(entry + 24)
                attrs = struct.unpack('<H', self.memory.read(type_ + TYPE_ATTRS, 2))[0]
                found.setdefault(self.memory.cstring(name), (offset, bool(attrs & FIELD_ATTRIBUTE_STATIC)))
                entry += FIELD_INFO_SIZE
            current = self.memory.u64(current + CLASS_PARENT)
        self._fields[klass] = found
        return found

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
        return [self.memory.u64(array + ARRAY_DATA + 8 * i) for i in range(size)]

    def first_u32(self, lst):
        """First uint32 of a List<uint>."""
        if self.memory.i32(lst + LIST_SIZE) < 1:
            raise NotFound('empty list')
        return self.memory.u32(self.memory.u64(lst + LIST_ITEMS) + ARRAY_DATA)


@dataclass
class LapState:
    clock: int  # race clock, 0.1 ms
    time_limit: int
    laps_completed: int
    laps_to_finish: int
    lap_starts: list  # when each started lap began, 0.1 ms

    @property
    def lap_times(self):
        return [b - a for a, b in zip(self.lap_starts, self.lap_starts[1:])][: self.laps_completed]

    @property
    def current_lap(self):
        return self.clock - self.lap_starts[-1] if self.lap_starts else None

    @property
    def last_lap(self):
        return self.lap_times[-1] if self.lap_times else None

    @property
    def best_lap(self):
        return min(self.lap_times) if self.lap_times else None

    @property
    def time_left(self):
        return self.time_limit - self.clock if self.time_limit > 0 else None


class LapReader:
    def __init__(self, il2cpp):
        self.il = il2cpp
        self.services_class = il2cpp.find_class('TS', 'Services')

    def read(self):
        il, memory = self.il, self.il.memory
        services = il.static_ref(self.services_class, 'sm_instance')
        state = il.ref(services, 'm_activeServer', 'm_eventListener', 'm_eventState')
        times = state + il.offset(state, 'times')
        local = [
            player
            for player in il.list_items(il.ref(state, 'players'))
            if player and memory.i32(player + il.offset(player, 'm_localHumanIndex')) >= 0
        ]
        if not local:
            raise NotFound('no local player')
        stats = il.ref(local[0], 'm_stats')
        starts = []
        for lap in il.list_items(il.ref(stats, 'm_checkpointTimesForLaps')):
            if lap:
                starts.append(il.first_u32(il.ref(lap, 'm_times')))
        return LapState(
            clock=memory.i32(times + TIMES_NOW),
            time_limit=memory.i32(times + TIMES_LIMIT),
            laps_completed=memory.u16(stats + il.offset(stats, 'm_lapsCompleted')),
            laps_to_finish=memory.u16(stats + il.offset(stats, 'm_lapsToFinish')),
            lap_starts=starts,
        )


def format_time(units):
    if units is None:
        return '-'
    sign, units = ('-' if units < 0 else ''), abs(units)
    minutes, rest = divmod(units, 60 * UNITS_PER_SECOND)
    return f'{sign}{minutes}:{rest / UNITS_PER_SECOND:06.3f}'


def connect(path=None):
    """A LapReader on TSU through the memory probe's socket. Raises OSError if TSU is
    not running through the probe."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import tsu_memory_probe as probe

    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    conn.connect(str(path or probe.socket_path()))

    def ask(request):
        probe.send_message(conn, request)
        header, data = probe.receive_message(conn)
        if not header.get('ok'):
            raise ReadError(header.get('error'))
        return header, data

    def read(address, size):
        return ask({'op': 'read', 'address': address, 'size': size})[1]

    regions = ask({'op': 'maps'})[0]['regions']
    metadata_path = next(path for *_rest, path in regions if path.endswith('global-metadata.dat'))
    metadata_base = next(start for start, _end, _p, offset, path in regions if path == metadata_path and offset == 0)
    memory = Memory(read, regions)
    return LapReader(Il2Cpp(memory, Path(metadata_path).read_bytes(), metadata_base))


NOT_CONNECTED = 'TSU is not running through TurboHUD. Start TSU from Steam (with the launch option).'
NO_RACE = 'TSU is running, but no race is on yet (menu or loading). Waiting...'


def format_state(state):
    return (
        f'lap {min(state.laps_completed + 1, state.laps_to_finish)}/{state.laps_to_finish}  '
        f'current {format_time(state.current_lap)}  last {format_time(state.last_lap)}  '
        f'best {format_time(state.best_lap)}  time left {format_time(state.time_left)}'
    )


def main(interval=0.5):
    reader, status = None, None

    def say(text, detail=''):
        nonlocal status
        if text != status:
            print(text + (f' ({detail})' if detail else ''), flush=True)
            status = text

    while True:
        try:
            if reader is None:
                reader = connect()
            state = reader.read()
            print(format_state(state), flush=True)
            status = None
        except NotFound as error:
            say(NO_RACE, str(error))
        except ReadError as error:
            # A pointer led nowhere: the game was between states. Try again.
            say(NO_RACE, str(error))
        except (OSError, ConnectionError, StopIteration):
            # Not started, or TSU quit (the socket closed): reconnect on the next round.
            reader = None
            say(NOT_CONNECTED)
        time.sleep(interval)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
