"""Can a program inside TSU's CrossOver bottle read the game's memory? (macOS)

On the Mac, TSU runs as a Windows game inside CrossOver. A native Mac program would need
`task_for_pid` to read it, which macOS refuses for CrossOver's signed (hardened
runtime) Wine loader unless the system is weakened. Inside the bottle, though, every
program is a Windows program under the same Wine server, and Windows lets a program read
another of the same user (`OpenProcess` with PROCESS_VM_READ, `ReadProcessMemory`).

This probe runs inside the bottle (with a portable Windows Python, through
`run_bottle_memory_probe_mac.sh`), and only reads:
1. finds TSU.exe and opens it for reading,
2. lists its memory regions (VirtualQueryEx) and finds the mapped global-metadata.dat,
3. times small and large reads,
4. runs TurboHUD's own lookup by name (turbohud.core.il2cpp and race) on it and, if a
   race is on, reads it a few times as the HUD would.

It prints no player names or IDs. Windows only (also works on Windows itself).
"""

import argparse
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from turbohud.core.il2cpp import Il2Cpp, Memory, NotFound, ReadError
from turbohud.core.race import LapReader

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TH32CS_SNAPPROCESS = 0x2
MEM_COMMIT = 0x1000
MEM_PRIVATE, MEM_MAPPED, MEM_IMAGE = 0x20000, 0x40000, 0x1000000
PAGE_NOACCESS, PAGE_GUARD = 0x01, 0x100
READABLE = 0x02 | 0x04 | 0x08 | 0x20 | 0x40 | 0x80  # R, RW, WC, XR, XRW, XWC
WRITABLE = 0x04 | 0x08 | 0x40 | 0x80

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('cntUsage', wintypes.DWORD),
        ('th32ProcessID', wintypes.DWORD),
        ('th32DefaultHeapID', ctypes.c_size_t),
        ('th32ModuleID', wintypes.DWORD),
        ('cntThreads', wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD),
        ('pcPriClassBase', wintypes.LONG),
        ('dwFlags', wintypes.DWORD),
        ('szExeFile', wintypes.WCHAR * 260),
    ]


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BaseAddress', ctypes.c_void_p),
        ('AllocationBase', ctypes.c_void_p),
        ('AllocationProtect', wintypes.DWORD),
        ('PartitionId', wintypes.WORD),
        ('RegionSize', ctypes.c_size_t),
        ('State', wintypes.DWORD),
        ('Protect', wintypes.DWORD),
        ('Type', wintypes.DWORD),
    ]


kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = kernel32.Process32NextW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(PROCESSENTRY32W),
]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.VirtualQueryEx.restype = ctypes.c_size_t
kernel32.VirtualQueryEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.POINTER(MEMORY_BASIC_INFORMATION),
    ctypes.c_size_t,
]
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
psapi.GetMappedFileNameW.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.LPWSTR, wintypes.DWORD]


def find_process(name):
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == name.lower():
                return entry.th32ProcessID
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return None


class Process:
    def __init__(self, pid):
        self.handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not self.handle:
            raise OSError(f'OpenProcess failed: error {ctypes.get_last_error()}')
        self._buffer = ctypes.create_string_buffer(1 << 20)

    def read(self, address, size):
        buffer = self._buffer if size <= len(self._buffer) else ctypes.create_string_buffer(size)
        done = ctypes.c_size_t()
        if (
            not kernel32.ReadProcessMemory(self.handle, address, buffer, size, ctypes.byref(done))
            or done.value != size
        ):
            raise ReadError(f'cannot read {size} bytes at {address:#x} (error {ctypes.get_last_error()})')
        return buffer.raw[:size]

    def image_path(self):
        size = wintypes.DWORD(1024)
        text = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(self.handle, 0, text, ctypes.byref(size)):
            raise OSError(f'QueryFullProcessImageNameW failed: error {ctypes.get_last_error()}')
        return text.value

    def mapped_name(self, address):
        text = ctypes.create_unicode_buffer(1024)
        return text.value if psapi.GetMappedFileNameW(self.handle, address, text, 1024) else ''

    def regions(self):
        """[(start, end, type, protect, path)] of committed, readable memory."""
        found, address, info = [], 0, MEMORY_BASIC_INFORMATION()
        while kernel32.VirtualQueryEx(self.handle, address, ctypes.byref(info), ctypes.sizeof(info)):
            start, size = info.BaseAddress or 0, info.RegionSize
            if info.State == MEM_COMMIT and info.Protect & READABLE and not info.Protect & PAGE_GUARD:
                path = self.mapped_name(start) if info.Type in (MEM_MAPPED, MEM_IMAGE) else ''
                found.append((start, start + size, info.Type, info.Protect, path))
            address = start + size
            if address >= 1 << 47:
                break
        return found


def timed(label, action, repeat):
    start = time.perf_counter()
    for _ in range(repeat):
        action()
    each = (time.perf_counter() - start) / repeat
    print(f'  {label}: {each * 1e6:.0f} us each ({repeat} times)')
    return each


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--reads', type=int, default=40, help='race reads at 20 a second, if a race is on')
    args = parser.parse_args()

    wine = hasattr(ctypes.WinDLL('ntdll'), 'wine_get_version')
    print(f'Python {sys.version.split()[0]}, {"under Wine" if wine else "on Windows"}.')
    pid = find_process('TSU.exe')
    if pid is None:
        print('TSU.exe is not running in this bottle.')
        return 1
    process = Process(pid)
    print(f'1. TSU.exe found and opened for reading (Windows pid {pid}).')

    started = time.perf_counter()
    regions = process.regions()
    took = time.perf_counter() - started
    total = sum(end - start for start, end, *_ in regions)
    private = [r for r in regions if r[2] == MEM_PRIVATE]
    print(
        f'2. {len(regions)} readable regions, {total / 2**30:.2f} GiB ({len(private)} private), listed in {took:.2f} s.'
    )
    metadata_regions = [r for r in regions if r[4].lower().endswith('global-metadata.dat')]
    image = process.image_path()
    metadata_file = Path(image).parent / 'TSU_Data' / 'il2cpp_data' / 'Metadata' / 'global-metadata.dat'
    metadata = metadata_file.read_bytes()
    if metadata_regions:
        metadata_base = min(r[0] for r in metadata_regions)
        how = 'by its mapped file name'
    else:
        head = metadata[:64]
        metadata_base = next(
            (r[0] for r in regions if r[2] != MEM_PRIVATE and process.read(r[0], 64) == head), None
        )
        how = 'by its first bytes (no mapped file name)'
    if metadata_base is None:
        print('   global-metadata.dat is not mapped yet.')
        return 1
    same = process.read(metadata_base, 4096) == metadata[:4096]
    print(f'   global-metadata.dat found {how}; its first 4 KiB match the file: {same}.')

    print('3. Read speed:')
    timed('8 bytes', lambda: process.read(metadata_base, 8), 2000)
    timed('4 KiB', lambda: process.read(metadata_base, 4096), 500)
    big = min(16 << 20, len(metadata))
    each = timed(f'{big >> 20} MiB', lambda: process.read(metadata_base, big), 5)
    print(f'  = {big / each / 2**30:.2f} GiB/s')

    # TurboHUD's lookup expects Linux-style regions; class records are in the C heap,
    # which on Windows is private memory.
    as_linux = [(s, e, 'r', 0, '[heap]' if t == MEM_PRIVATE else p) for s, e, t, _p, p in regions]
    # The online race is found by a search of the game's data for objects of a class:
    # writable private memory, as the Linux probe searches.
    data = [(s, e) for s, e, t, protect, _p in regions if t == MEM_PRIVATE and protect & WRITABLE]
    searches = []

    def find_pointers(value):
        started = time.perf_counter()
        hits = memory.search(data, value)
        searches.append(time.perf_counter() - started)
        return hits

    memory = Memory(process.read, as_linux, find_pointers=find_pointers)
    il = Il2Cpp(memory, metadata, metadata_base)
    print('4. TurboHUD lookup by name:')
    started = time.perf_counter()
    try:
        services = il.find_class('TS', 'Services')
    except NotFound as error:
        print(f'   {error}')
        return 1
    print(
        f'   TS.Services found in {time.perf_counter() - started:.2f} s; {len(il.fields(services))} fields.'
    )
    instance = il.static_ref(services, 'sm_instance')
    print(f'   TS.Services.sm_instance read: {bool(instance)}')

    # Count each race read's reads and the 4 KiB pages they touch: a read costs the
    # same up to 4 KiB, so pages are what a block cache would read.
    counted = {'reads': 0, 'pages': set()}
    plain_read = memory.read

    def counting_read(address, size):
        counted['reads'] += 1
        counted['pages'].update(range(address >> 12, (address + size - 1 >> 12) + 1))
        return plain_read(address, size)

    memory.read = counting_read
    per_read = []
    reader = LapReader(il, event_running=lambda: True)
    times, state = [], None
    for _ in range(args.reads):
        started = time.perf_counter()
        try:
            state = reader.read()
        except (NotFound, ReadError) as error:
            print(f'   No race to read: {error}')
            break
        times.append(time.perf_counter() - started)
        per_read.append((counted['reads'], len(counted['pages'])))
        counted['reads'], counted['pages'] = 0, set()
        time.sleep(0.05)
    if searches:
        print(f'   Online race searched for {len(searches)} time(s), {sum(searches):.1f} s in all.')
    if per_read[1:]:
        later = sorted(per_read[1:])
        reads, pages = later[len(later) // 2]
        print(f'   A race read (median, after the first): {reads} reads on {pages} pages of 4 KiB.')
    if times:
        times.sort()
        print(
            f'   Race read {len(times)} times: median {times[len(times) // 2] * 1e3:.1f} ms, '
            f'slowest {times[-1] * 1e3:.1f} ms (the first includes the cached lookups).'
        )
        print(
            f'   Last read: {state.laps_completed}/{state.laps_to_finish} laps done, '
            f'clock {state.clock / 10000:.1f} s, {len(state.players)} players, position known: '
            f'{state.position is not None}, car: {state.car is not None}.'
        )
    return 0


if __name__ == '__main__':
    sys.exit(main())
