"""TurboHUD's own memory, for the log (asked for by the user on 2026-11-16).

A tester's Mac had 2.9 GB of 18 GB left with TSU and the whole HUD running, and TurboHUD's own
share was not in his logs. The 30 s summary of reads and frames now says it: what Activity
Monitor's Memory column shows on the Mac (the physical footprint), the private working set on
Windows (Task Manager's Memory), the resident size on Linux. One system call, about a
microsecond, once every 30 s: nothing the HUD would notice. None where it cannot be read.
"""

import ctypes
import logging
import os
import sys
import tracemalloc

log = logging.getLogger(__name__)

MB = 1024 * 1024
TRACE_VARIABLE = 'TURBOHUD_TRACE_MEMORY'  # set to 1: the log says where Python's memory grew (slower)
TRACE_SITES = 10  # places in the code shown in each such summary
TRACE_LEAST = 50 * 1024  # bytes: a place that grew less is left out


class _TaskVmInfo(ctypes.Structure):
    """task_vm_info_data_t (mach/task_info.h) as far as phys_footprint, its 1st revision."""

    _fields_ = [
        ('virtual_size', ctypes.c_uint64),
        ('region_count', ctypes.c_int32),
        ('page_size', ctypes.c_int32),
        ('resident_size', ctypes.c_uint64),
        ('resident_size_peak', ctypes.c_uint64),
        ('device', ctypes.c_uint64),
        ('device_peak', ctypes.c_uint64),
        ('internal', ctypes.c_uint64),
        ('internal_peak', ctypes.c_uint64),
        ('external', ctypes.c_uint64),
        ('external_peak', ctypes.c_uint64),
        ('reusable', ctypes.c_uint64),
        ('reusable_peak', ctypes.c_uint64),
        ('purgeable_volatile_pmap', ctypes.c_uint64),
        ('purgeable_volatile_resident', ctypes.c_uint64),
        ('purgeable_volatile_virtual', ctypes.c_uint64),
        ('compressed', ctypes.c_uint64),
        ('compressed_peak', ctypes.c_uint64),
        ('compressed_lifetime', ctypes.c_uint64),
        ('phys_footprint', ctypes.c_uint64),
    ]


TASK_VM_INFO = 22


def _mac():
    libc = ctypes.CDLL('/usr/lib/libSystem.B.dylib')
    libc.mach_task_self.restype = ctypes.c_uint32
    info = _TaskVmInfo()
    count = ctypes.c_uint32(ctypes.sizeof(info) // 4)  # in natural_t (4 bytes)
    if libc.task_info(libc.mach_task_self(), TASK_VM_INFO, ctypes.byref(info), ctypes.byref(count)) != 0:
        return None
    return info.phys_footprint or None


class _ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = [
        ('cb', ctypes.c_uint32),
        ('PageFaultCount', ctypes.c_uint32),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
        ('PrivateUsage', ctypes.c_size_t),
    ]


class _ProcessMemoryCountersEx2(_ProcessMemoryCountersEx):
    """PROCESS_MEMORY_COUNTERS_EX2 (psapi.h, Windows 10 2004 and later): the private working set."""

    _fields_ = [
        ('PrivateWorkingSetSize', ctypes.c_size_t),
        ('SharedCommitUsage', ctypes.c_uint64),
    ]


def _windows():
    """Task Manager's Memory column: the private working set (PrivateWorkingSetSize). The whole
    working set counts the pages shared with Windows and Qt's libraries too, so it shows more than
    Task Manager (seen 2026-11-28); a Windows before 10 2004 has only that, and gets it."""
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    process = ctypes.c_void_p(kernel32.GetCurrentProcess())
    counters = _ProcessMemoryCountersEx2()
    counters.cb = ctypes.sizeof(counters)
    if (
        psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb)
        and counters.PrivateWorkingSetSize
    ):
        return counters.PrivateWorkingSetSize
    counters = _ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
        return None
    return counters.WorkingSetSize or None


def _linux(path='/proc/self/statm'):
    import os

    with open(path, encoding='ascii') as statm:
        resident_pages = int(statm.read().split()[1])
    return resident_pages * os.sysconf('SC_PAGE_SIZE') or None


def own_memory(platform=sys.platform):
    """TurboHUD's own memory in bytes, as the system's monitor shows it; None where it cannot be
    read (an unknown system, or the call failing: the log then says nothing of it)."""
    try:
        if platform == 'darwin':
            return _mac()
        if platform == 'win32':
            return _windows()
        if platform.startswith('linux'):
            return _linux()
    except (OSError, AttributeError, ValueError, IndexError):
        return None
    return None


class _MallInfo2(ctypes.Structure):
    """glibc's struct mallinfo2 (malloc.h, glibc 2.33 and later), all in bytes."""

    _fields_ = [
        (name, ctypes.c_size_t)
        for name in ('arena', 'ordblks', 'smblks', 'hblks', 'hblkhd', 'usmblks', 'fsmblks')
        + ('uordblks', 'fordblks', 'keepcost')
    ]


def c_heap(platform=sys.platform):
    """(in use, held free, in large blocks of their own) bytes of the C heap (glibc's malloc, which
    Python, Qt and their threads use) on Linux, or None. Much held free is memory freed but kept by
    malloc in pieces (fragmentation, more with threads): the resident size then stays high though
    TurboHUD holds less (looked into with the user on 2026-11-20: +350 MB in 18 min of racing)."""
    if not platform.startswith('linux'):
        return None
    try:
        call = ctypes.CDLL(None).mallinfo2
    except (OSError, AttributeError):
        return None
    call.restype = _MallInfo2
    info = call()
    return info.uordblks + info.hblkhd, info.fordblks, info.hblkhd


class MemoryWatch:
    """TurboHUD's memory in one log line on each flush (the 30 s summary), with the most seen.

    With `parts` added (add_part: a name and a callable giving a text, or None to leave it out) a
    second line says where it is; with tracing on (TRACE_VARIABLE, or trace()) the places in the
    code where Python's memory grew most since the last flush, a line each."""

    def __init__(self, read=own_memory, log_line=None):
        self._read = read
        self._log_line = log_line or log.info
        self.most = 0
        self.parts = []  # (name, callable)
        self._snapshot = None  # the last trace's tracemalloc snapshot, while tracing

    def add_part(self, name, describe):
        self.parts.append((name, describe))

    def trace(self):
        """Follow where Python allocates from now on (tracemalloc: slower, for a look into growth)."""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        self._snapshot = tracemalloc.take_snapshot()
        self._log_line('memory: tracing where Python allocates (%s)', TRACE_VARIABLE)

    def flush(self):
        size = self._read()
        if size is None:
            return
        self.most = max(self.most, size)
        self._log_line('memory: TurboHUD %.0f MB (most so far %.0f MB)', size / MB, self.most / MB)
        shown = []
        for name, describe in self.parts:
            try:
                text = describe()
            except (
                OSError,
                ValueError,
                TypeError,
                AttributeError,
                RuntimeError,
            ) as error:  # never stops the HUD
                text = f'not read ({error})'
            if text is not None:
                shown.append(f'{name} {text}')
        if shown:
            self._log_line('memory parts: %s', '; '.join(shown))
        if self._snapshot is not None:
            self._log_growth()

    def _log_growth(self):
        snapshot = tracemalloc.take_snapshot().filter_traces(
            (tracemalloc.Filter(False, tracemalloc.__file__),)
        )
        grown = [d for d in snapshot.compare_to(self._snapshot, 'lineno') if d.size_diff >= TRACE_LEAST][
            :TRACE_SITES
        ]
        traced, _peak = tracemalloc.get_traced_memory()
        self._log_line('memory traced: Python %.1f MB in all', traced / MB)
        for diff in grown:
            frame = diff.traceback[0]
            self._log_line(
                'memory grew: %+.2f MB (%+d blocks), %.2f MB now, at %s:%d',
                diff.size_diff / MB,
                diff.count_diff,
                diff.size / MB,
                _short(frame.filename),
                frame.lineno,
            )
        self._snapshot = snapshot


def _short(filename):
    """A file's path from its package on (turbohud/..., or after site-packages), not the whole path, which
    would name the user's folders in the log."""
    parts = filename.replace('\\', '/').split('/')
    for anchor in ('turbohud', 'site-packages', 'lib'):
        if anchor in parts:
            return '/'.join(parts[parts.index(anchor) + (anchor != 'turbohud') :])
    return parts[-1]


def python_objects():
    """Python's memory blocks in use, a count that grows where Python objects pile up."""
    return f'{sys.getallocatedblocks():,} blocks'


def c_heap_text():
    heap = c_heap()
    if heap is None:
        return None
    used, free, large = heap
    return f'{used / MB:.0f} MB in use ({large / MB:.0f} MB of it in large blocks), {free / MB:.0f} MB freed but held'


def tracing_asked(environ=None):
    return (os.environ if environ is None else environ).get(TRACE_VARIABLE, '') not in ('', '0')


watch = MemoryWatch()


__all__ = ['MemoryWatch', 'c_heap', 'own_memory', 'python_objects', 'tracing_asked', 'watch']
