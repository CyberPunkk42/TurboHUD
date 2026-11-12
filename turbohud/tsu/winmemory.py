"""Reading TSU's memory as a Windows program: on Windows, and inside CrossOver on the Mac.

Windows lets a program read another of the same user (`OpenProcess` with
PROCESS_VM_READ, `ReadProcessMemory`); no probe is needed. Inside a CrossOver bottle
the same calls work for programs of that bottle, through the Wine server. There every
read is a round trip to the server, about 250 µs whatever its size up to 4 KiB, and
the server also serves the game. Two things follow:
- `PageCache`: a race read makes hundreds of small reads on a few dozen pages, so each
  4 KiB page is read once per race read and the small reads are served from it.
- `read_pages`: the game keeps its objects where they are during a race, so a race read
  needs nearly the same pages as the one before. The cache asks for all of those at once,
  and pages close together are read in one call: a large read costs little more than a
  small one (about 0.8 GiB/s, so 64 KiB in about 80 µs on top of the 250 µs). Reading
  the memory between two wanted pages is cheaper than a second call up to about 200 KiB,
  which is where `MERGE_GAP` comes from. A call that reaches memory that is not there
  fails as a whole; the gaps where that happened are kept (`breaks`) and not read across
  again.
- `search` goes in pieces with pauses between them, so a search of the whole game
  (about 2 GiB) does not hold the server for seconds at a time (TSU stuttered then).

Only reads: nothing here can change the game. The pure parts (regions, cache, search)
run and test on any system; the Win32 calls load only when a process is opened. The
reader in the bottle (`bottle_reader.py`) uses only those parts, so `connect` alone
loads the race logic.
"""

import ctypes
import os
import struct
import time
from pathlib import Path

PAGE = 4096
CHUNK = 1 << 20  # bytes a search reads at once
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TH32CS_SNAPPROCESS = 0x2
MEM_COMMIT = 0x1000
MEM_IMAGE, MEM_MAPPED, MEM_PRIVATE = 0x1000000, 0x40000, 0x20000
PAGE_GUARD = 0x100
STILL_ACTIVE = 259
FILETIME_EPOCH = 11_644_473_600  # seconds from 1601 (Windows' FILETIME) to 1970 (Unix time)
# Page protections: which allow reading, writing, running.
READ = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}
WRITE = {0x04, 0x08, 0x40, 0x80}
EXECUTE = {0x10, 0x20, 0x40, 0x80}
MERGE_GAP = 48  # pages: wanted pages at most this far apart (192 KiB) are read in one call
SPAN_MOST = 512  # pages a merged read covers at most (2 MiB)
BREAKS_MOST = 4096  # gaps kept as not readable across; forgotten all at once beyond this
WINE_SEARCH_SHARE = 0.5  # in Wine, the share of the time a search may read
# Bytes below the last race's place where the search for the next begins. Three races in a row lay
# within 0.5 MiB of the one before (2026-11-10); a race further below is found on the way round.
SEARCH_BEFORE = 4 << 20
# How far a quick look for the next race reaches from where the search would begin: on a tester's Mac
# one race lay 209.5 MiB above the last (2026-11-11), the others within 0.5 MiB.
NEAR_SPAN = 256 << 20


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


def spans(pages, gap=MERGE_GAP, most=SPAN_MOST, breaks=()):
    """(first, last) page numbers of the reads that cover `pages`: pages at most `gap`
    apart share a read, which covers at most `most` pages. Two wanted pages whose pair
    is in `breaks` never share one."""
    found = []
    for number in sorted(set(pages)):
        if (
            found
            and number - found[-1][1] <= gap
            and number - found[-1][0] < most
            and (found[-1][1], number) not in breaks
        ):
            found[-1][1] = number
        else:
            found.append([number, number])
    return [tuple(span) for span in found]


def read_pages(read, pages, page=PAGE, gap=MERGE_GAP, most=SPAN_MOST, breaks=None):
    """({page number: its bytes}, reads made) for the `pages` that can be read, with
    pages close together read in one call (`spans`). Where such a read fails (it reaches
    memory that is not there), it is tried again as two, cut at its widest gap, and so
    on down to single pages; pages that cannot be read are left out. A gap whose two
    sides could be read is added to `breaks` (a set the caller keeps), so the reads
    after this one do not try across it again."""
    wanted = sorted(set(pages))
    found, calls = {}, 0

    def fetch(group):
        """Whether all of `group` (wanted pages, ascending) could be read."""
        nonlocal calls
        first = group[0]
        calls += 1
        try:
            data = read(first * page, (group[-1] - first + 1) * page)
        except OSError:
            data = None
        if data is not None:
            for number in group:
                offset = (number - first) * page
                found[number] = data[offset : offset + page]
            return True
        if len(group) == 1:
            return False
        cut = max(range(1, len(group)), key=lambda index: group[index] - group[index - 1])
        below, above = fetch(group[:cut]), fetch(group[cut:])
        if below and above and breaks is not None:
            if len(breaks) >= BREAKS_MOST:
                breaks.clear()
            breaks.add((group[cut - 1], group[cut]))
        return False

    position = 0
    for _first, last in spans(wanted, gap, most, breaks or ()):
        end = position
        while end < len(wanted) and wanted[end] <= last:
            end += 1
        fetch(wanted[position:end])
        position = end
    return found, calls


class PageCache:
    """Serves small reads from whole pages, each read once until `clear()`. Call
    `clear()` before every race read, so each one sees the game as it is then.

    With `fetch_many` (page numbers -> {page number: bytes}), `prefetch()` after `clear()`
    asks for the pages the read before used, in one go; pages new to this read are still
    read one at a time. `clear(kind)` names the kind of read coming ('quick', 'full'): each
    kind prefetches the pages the last read of its kind used, so a full read once a second
    neither fetches its extra pages one by one nor makes the quick reads after it fetch them."""

    def __init__(self, read, page=PAGE, largest=4 * PAGE, fetch_many=None):
        self._read = read
        self._page = page
        self._largest = largest  # larger reads go straight through
        self._fetch_many = fetch_many
        self._pages = {}
        self._used = set()  # pages served since the last clear()
        self._kind = None  # the kind of read now (clear)
        self._last = {}  # kind of read -> the pages the last read of that kind used
        self.reads = 0  # reads passed on, for measuring

    def clear(self, kind=None):
        if self._used:
            self._last[self._kind] = self._used
        self._kind = kind
        self._used = set()
        self._pages.clear()

    def prefetch(self):
        """Fetch the pages the last read of this kind used, in one go (with `fetch_many`)."""
        last = self._last.get(self._kind)
        if self._fetch_many is None or not last:
            return
        self.reads += 1
        self._pages.update(self._fetch_many(sorted(last)))

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
            self._used.add(number)
            parts.append(data)
        start = address - first * page
        return b''.join(parts)[start : start + size]


def search_start(address):
    """Where a search for the next race begins when the last one was at `address`: a
    little below it, as the game may put the new race's objects on either side."""
    return max(address - SEARCH_BEFORE, 0) // PAGE * PAGE


def near(regions, address, span=NEAR_SPAN):
    """The parts of `regions` within `span` bytes up from search_start(address), as (start,
    end): where a quick look for the next race reads, a few percent of the game's data."""
    low = search_start(address)
    high = low + span
    return [
        (max(start, low), min(end, high)) for start, end, *_ in sorted(regions) if start < high and end > low
    ]


def starting_at(regions, address):
    """`regions` as (start, end) in the order a search from `address` takes them: upwards
    from there, then round from the lowest up to it. A region `address` lies in is cut
    in two there."""
    later, earlier = [], []
    for start, end, *_ in sorted(regions):
        if end <= address:
            earlier.append((start, end))
        elif start >= address:
            later.append((start, end))
        else:
            later.append((address, end))
            earlier.append((start, address))
    return later + earlier


def search(
    read,
    regions,
    value,
    align=8,
    chunk=CHUNK,
    share=1.0,
    sleep=time.sleep,
    clock=time.perf_counter,
    first=None,
):
    """Addresses (multiples of `align`) in `regions` that hold the 64-bit `value`,
    lowest first, reading `chunk` bytes at a time. A generator: it reads on only as far
    as its hits are taken, so a lookup that stops at the first good one reads little
    (in TSU the class records and the online race lie in the first fifth of its data).
    With `share` below 1, it pauses after each piece so that reading takes about that
    share of the time (0.5: twice as long, the rest left to the game). With `first` (a
    multiple of `align`), it begins at that address and comes round to it, so what lies
    just above is found at once. With several values (a tuple), one pass looks for all of
    them and gives (address, value): reading the memory is what takes the time."""
    several = isinstance(value, tuple)
    patterns = {struct.pack('<Q', v): v for v in (value if several else (value,))}
    overlap = 7
    for start, end, *_ in sorted(regions) if first is None else starting_at(regions, first):
        address = start
        while address < end:
            size = min(chunk + overlap, end - address)
            began = clock()
            try:
                data = read(address, size)
            except OSError:
                data = b''
            hits = []
            for pattern, found in patterns.items():
                index = data.find(pattern)
                while index != -1:
                    if index < chunk and (address + index) % align == 0:
                        hits.append((address + index, found))
                    index = data.find(pattern, index + 1)
            hits.sort()
            address += chunk
            if share < 1.0:
                sleep((clock() - began) * (1.0 - share) / share)
            yield from hits if several else (hit for hit, _value in hits)


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
    k.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    k.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4
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

    def alive(self):
        """False once the program has quit: a read then fails for good, unlike a read
        of a stale pointer."""
        from ctypes import wintypes

        code = wintypes.DWORD()
        if not self._k.GetExitCodeProcess(self.handle, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE

    def started(self):
        """When the program started, as time.time() gives it, or None where not known."""
        from ctypes import wintypes

        times = [wintypes.FILETIME() for _ in range(4)]  # created, exited, kernel, user
        if not self._k.GetProcessTimes(self.handle, *(ctypes.byref(t) for t in times)):
            return None
        created = times[0].dwHighDateTime << 32 | times[0].dwLowDateTime
        return created / 10_000_000 - FILETIME_EPOCH if created else None

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


def metadata_path(image_path):
    """TSU's `global-metadata.dat`, from where its program file is."""
    return Path(image_path).parent / 'TSU_Data' / 'il2cpp_data' / 'Metadata' / 'global-metadata.dat'


class CachedReader:
    """A race reader that starts every read with an empty page cache, and fetches the
    pages the read before used in one go. `last_read` says what the latest read took, for
    the log: (trips for the game's memory, seconds of them spent on that memory or None
    when not known, reads of that memory or None). `in_game` and `game_reads` give such
    seconds and reads so far."""

    def __init__(self, reader, cache, in_game=None, game_reads=None):
        self.reader, self.cache = reader, cache
        self._in_game = in_game
        self._game_reads = game_reads
        self.last_read = None

    def read(self):
        plan = getattr(self.reader, 'plan_read', None)
        self.cache.clear(plan() if plan else None)  # 'quick' or 'full' (LapReader.plan_read)
        trips = self.cache.reads
        spent = self._in_game() if self._in_game else None
        calls = self._game_reads() if self._game_reads else None
        try:
            self.cache.prefetch()
            return self.reader.read()
        finally:
            self.last_read = (
                self.cache.reads - trips,
                self._in_game() - spent if self._in_game else None,
                self._game_reads() - calls if self._game_reads else None,
            )


def connect(name='TSU.exe'):
    """(race reader, open process) on the running TSU, read as a Windows program; the
    same shape as `turbohud.tsu.client.connect`, for `LiveRace`. Raises OSError while TSU
    does not run, NotFound while its metadata is not mapped yet."""
    from turbohud.core.il2cpp import Il2Cpp, Memory, NotFound
    from turbohud.core.race import LapReader
    from turbohud.tsu.gamelog import EventLog

    pid = find_process(name)
    if pid is None:
        raise OSError(f'{name} is not running')
    process = WindowsProcess(pid)
    try:
        metadata = metadata_path(process.image_path()).read_bytes()
        base = metadata_base(process.regions(), process.read, metadata)
        if base is None:
            raise NotFound('the game metadata is not mapped yet')
        share = WINE_SEARCH_SHARE if under_wine() else 1.0

        def paced(search_regions, value, first=None):
            return search(process.read, search_regions, value, share=share, first=first)

        def data():
            return [r for r in process.regions() if searchable(r)]

        breaks = set()  # gaps a merged read failed across: see read_pages
        cache = PageCache(
            process.read, fetch_many=lambda pages: read_pages(process.read, pages, breaks=breaks)[0]
        )
        memory = Memory(
            cache.read,
            process.regions,  # listed anew for each search: the memory grows towards a race
            find_pointers=lambda value: paced(data(), value),
            searcher=paced,
            find_pointers_from=lambda value, address: paced(data(), value, search_start(address)),
            find_pointers_any=lambda values, address=None: paced(
                data(), tuple(values), None if address is None else search_start(address)
            ),
            find_pointers_near=lambda value, address: paced(near(data(), address), value),
        )
        il2cpp = Il2Cpp(memory, metadata, base)
        reader = LapReader(il2cpp, event_running=EventLog(tsu_data(), since=process.started()).running)
        return CachedReader(reader, cache), process
    except BaseException:
        process.close()
        raise
