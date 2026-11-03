"""Reading TSU's memory as a Windows program: on Windows, and inside CrossOver on the Mac.

Windows lets a program read another of the same user (`OpenProcess` with
PROCESS_VM_READ, `ReadProcessMemory`); no probe is needed. Inside a CrossOver bottle
the same calls work for programs of that bottle, through the Wine server. There every
read is a round trip to the server, about 250 µs whatever its size up to 4 KiB, and
the server also serves the game. Two things follow:
- `PageCache`: a race read makes hundreds of small reads on a few dozen pages, so each
  4 KiB page is read once per race read and the small reads are served from it.
- `search` goes in pieces with pauses between them, so a search of the whole game
  (about 2 GiB) does not hold the server for seconds at a time (TSU stuttered then).

Only reads: nothing here can change the game. The pure parts (regions, cache, search)
run and test on any system; the Win32 calls load only when a process is opened.
"""

import ctypes
import os
import struct
import time
from pathlib import Path

from turbohud.core.il2cpp import Il2Cpp, Memory, NotFound
from turbohud.core.race import LapReader
from turbohud.tsu.gamelog import EventLog

PAGE = 4096
CHUNK = 1 << 20  # bytes a search reads at once
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TH32CS_SNAPPROCESS = 0x2
MEM_COMMIT = 0x1000
MEM_IMAGE, MEM_MAPPED, MEM_PRIVATE = 0x1000000, 0x40000, 0x20000
PAGE_GUARD = 0x100
# Page protections: which allow reading, writing, running.
READ = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}
WRITE = {0x04, 0x08, 0x40, 0x80}
EXECUTE = {0x10, 0x20, 0x40, 0x80}
WINE_SEARCH_SHARE = 0.25  # in Wine, the share of the time a search may read


def region(start, size, protect, kind, path=''):
    """A region in the form of a Linux memory map line: (start, end, permissions,
    offset, path), so the IL2CPP lookup (`turbohud/core/il2cpp.py`) takes it as it is.
    Private memory is where the C heap is, so it is named '[heap]'."""
    base = protect & 0xFF
    perms = (
        ('r' if base in READ else '-')
        + ('w' if base in WRITE else '-')
        + ('x' if base in EXECUTE else '-')
        + ('p' if kind == MEM_PRIVATE else 's')
    )
    return (start, start + size, perms, 0, '[heap]' if kind == MEM_PRIVATE else path)


def readable(state, protect):
    return state == MEM_COMMIT and protect & 0xFF in READ and not protect & PAGE_GUARD


def searchable(item):
    """Writable private memory, where the game keeps its objects."""
    perms = item[2]
    return perms.startswith('rw') and perms.endswith('p')


class PageCache:
    """Serves small reads from whole pages, each read once until `clear()`. Call
    `clear()` before every race read, so each one sees the game as it is then."""

    def __init__(self, read, page=PAGE, largest=4 * PAGE):
        self._read = read
        self._page = page
        self._largest = largest  # larger reads go straight through
        self._pages = {}
        self.reads = 0  # reads passed on, for measuring

    def clear(self):
        self._pages.clear()

    def read(self, address, size):
        if size > self._largest:
            self.reads += 1
            return self._read(address, size)
        page = self._page
        first, last = address // page, (address + size - 1) // page
        parts = []
        for number in range(first, last + 1):
            data = self._pages.get(number)
            if data is None:
                try:
                    self.reads += 1
                    data = self._read(number * page, page)
                except OSError:
                    # A page that cannot be read whole (the end of a region): read
                    # just what was asked, and keep nothing.
                    self.reads += 1
                    return self._read(address, size)
                self._pages[number] = data
            parts.append(data)
        start = address - first * page
        return b''.join(parts)[start : start + size]


def search(read, regions, value, align=8, chunk=CHUNK, share=1.0, sleep=time.sleep, clock=time.perf_counter):
    """Addresses (multiples of `align`) in `regions` that hold the 64-bit `value`,
    lowest first, reading `chunk` bytes at a time. A generator: it reads on only as far
    as its hits are taken, so a lookup that stops at the first good one reads little
    (in TSU the class records and the online race lie in the first fifth of its data).
    With `share` below 1, it pauses after each piece so that reading takes about that
    share of the time (0.25: four times as long, the rest left to the game)."""
    pattern = struct.pack('<Q', value)
    overlap = len(pattern) - 1
    for start, end, *_ in sorted(regions):
        address = start
        while address < end:
            size = min(chunk + overlap, end - address)
            began = clock()
            try:
                data = read(address, size)
            except OSError:
                data = b''
            hits = []
            index = data.find(pattern)
            while index != -1:
                if index < chunk and (address + index) % align == 0:
                    hits.append(address + index)
                index = data.find(pattern, index + 1)
            address += chunk
            if share < 1.0:
                sleep((clock() - began) * (1.0 - share) / share)
            yield from hits


def under_wine():
    """True when this Windows program runs in Wine (CrossOver)."""
    try:
        return hasattr(ctypes.WinDLL('ntdll'), 'wine_get_version')
    except (AttributeError, OSError):
        return False


def _win32():
    """kernel32 and psapi with the signatures used here (Windows only)."""
    from ctypes import wintypes as w  # here, not at the top: Windows types

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ('dwSize', w.DWORD),
            ('cntUsage', w.DWORD),
            ('th32ProcessID', w.DWORD),
            ('th32DefaultHeapID', ctypes.c_size_t),
            ('th32ModuleID', w.DWORD),
            ('cntThreads', w.DWORD),
            ('th32ParentProcessID', w.DWORD),
            ('pcPriClassBase', w.LONG),
            ('dwFlags', w.DWORD),
            ('szExeFile', w.WCHAR * 260),
        ]

    class MEMORY_BASIC_INFORMATION(ctypes.Structure):
        _fields_ = [
            ('BaseAddress', ctypes.c_void_p),
            ('AllocationBase', ctypes.c_void_p),
            ('AllocationProtect', w.DWORD),
            ('PartitionId', w.WORD),
            ('RegionSize', ctypes.c_size_t),
            ('State', w.DWORD),
            ('Protect', w.DWORD),
            ('Type', w.DWORD),
        ]

    k = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    k.CreateToolhelp32Snapshot.restype = w.HANDLE
    k.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    k.Process32FirstW.argtypes = k.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k.OpenProcess.restype = w.HANDLE
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.CloseHandle.argtypes = [w.HANDLE]
    k.ReadProcessMemory.argtypes = [
        w.HANDLE,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    k.VirtualQueryEx.restype = ctypes.c_size_t
    k.VirtualQueryEx.argtypes = [
        w.HANDLE,
        ctypes.c_void_p,
        ctypes.POINTER(MEMORY_BASIC_INFORMATION),
        ctypes.c_size_t,
    ]
    k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
    psapi.GetMappedFileNameW.argtypes = [w.HANDLE, ctypes.c_void_p, w.LPWSTR, w.DWORD]
    return k, psapi, PROCESSENTRY32W, MEMORY_BASIC_INFORMATION


def find_process(name='TSU.exe'):
    """The process ID of the first running program called `name`, or None."""
    k, _psapi, entry_type, _info = _win32()
    snapshot = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    entry = entry_type()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        ok = k.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == name.lower():
                return entry.th32ProcessID
            ok = k.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        k.CloseHandle(snapshot)
    return None


class WindowsProcess:
    """Another program of this user, opened for reading only."""

    def __init__(self, pid):
        self._k, self._psapi, _entry, self._info_type = _win32()
        self.handle = self._k.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not self.handle:
            raise OSError(f'cannot open process {pid} for reading (error {ctypes.get_last_error()})')
        self.pid = pid
        self._buffer = ctypes.create_string_buffer(CHUNK + 64)

    def close(self):
        if self.handle:
            self._k.CloseHandle(self.handle)
            self.handle = None

    def read(self, address, size):
        buffer = self._buffer if size <= len(self._buffer) else ctypes.create_string_buffer(size)
        done = ctypes.c_size_t()
        if (
            not self._k.ReadProcessMemory(self.handle, address, buffer, size, ctypes.byref(done))
            or done.value != size
        ):
            raise OSError(f'cannot read {size} bytes at {address:#x} (error {ctypes.get_last_error()})')
        return buffer.raw[:size]

    def image_path(self):
        """The program's own file (a Windows path)."""
        from ctypes import wintypes

        size = wintypes.DWORD(1024)
        text = ctypes.create_unicode_buffer(size.value)
        if not self._k.QueryFullProcessImageNameW(self.handle, 0, text, ctypes.byref(size)):
            raise OSError(f'cannot get the program file (error {ctypes.get_last_error()})')
        return text.value

    def regions(self):
        """The readable memory, as `region()` tuples. Wine names no mapped files, so a
        mapped file may come with an empty path."""
        found, address, info = [], 0, self._info_type()
        while self._k.VirtualQueryEx(self.handle, address, ctypes.byref(info), ctypes.sizeof(info)):
            start, size = info.BaseAddress or 0, info.RegionSize
            if readable(info.State, info.Protect):
                path = ''
                if info.Type in (MEM_MAPPED, MEM_IMAGE):
                    text = ctypes.create_unicode_buffer(1024)
                    if self._psapi.GetMappedFileNameW(self.handle, start, text, 1024):
                        path = text.value
                found.append(region(start, size, info.Protect, info.Type, path))
            address = start + size
            if not size or address >= 1 << 47:
                break
        return found


def metadata_base(regions, read, metadata):
    """Where the game's `global-metadata.dat` (its bytes: `metadata`) is mapped: by its
    file name where Windows gives one, else by its first bytes in mapped memory."""
    named = [r[0] for r in regions if r[4].lower().endswith('global-metadata.dat')]
    if named:
        return min(named)
    head = metadata[:64]
    for start, _end, perms, _offset, _path in regions:
        if perms.endswith('s'):
            try:
                if read(start, len(head)) == head:
                    return start
            except OSError:
                continue
    return None


def tsu_data(environ=None):
    """TSU's data folder on Windows (and in a CrossOver bottle), holding one folder per
    Steam account."""
    environ = os.environ if environ is None else environ
    return Path(environ.get('USERPROFILE', '')) / 'AppData' / 'LocalLow' / 'Turbo Sliders' / 'Unlimited'


class CachedReader:
    """A race reader that starts every read with an empty page cache."""

    def __init__(self, reader, cache):
        self.reader, self.cache = reader, cache

    def read(self):
        self.cache.clear()
        return self.reader.read()


def connect(name='TSU.exe'):
    """(race reader, open process) on the running TSU, read as a Windows program; the
    same shape as `turbohud.tsu.client.connect`, for `LiveRace`. Raises OSError while TSU
    does not run, NotFound while its metadata is not mapped yet."""
    pid = find_process(name)
    if pid is None:
        raise OSError(f'{name} is not running')
    process = WindowsProcess(pid)
    try:
        regions = process.regions()
        metadata_file = (
            Path(process.image_path()).parent
            / 'TSU_Data'
            / 'il2cpp_data'
            / 'Metadata'
            / 'global-metadata.dat'
        )
        metadata = metadata_file.read_bytes()
        base = metadata_base(regions, process.read, metadata)
        if base is None:
            raise NotFound('the game metadata is not mapped yet')
        share = WINE_SEARCH_SHARE if under_wine() else 1.0

        def paced(search_regions, value):
            return search(process.read, search_regions, value, share=share)

        cache = PageCache(process.read)
        memory = Memory(
            cache.read,
            regions,
            find_pointers=lambda value: paced([r for r in regions if searchable(r)], value),
            searcher=paced,
        )
        il2cpp = Il2Cpp(memory, metadata, base)
        reader = LapReader(il2cpp, event_running=EventLog(tsu_data()).running)
        return CachedReader(reader, cache), process
    except BaseException:
        process.close()
        raise
