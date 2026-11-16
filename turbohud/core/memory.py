"""TurboHUD's own memory, for the log (asked for by the user on 2026-11-16).

A tester's Mac had 2.9 GB of 18 GB left with TSU and the whole HUD running, and TurboHUD's own
share was not in his logs. The 30 s summary of reads and frames now says it: what Activity
Monitor's Memory column shows on the Mac (the physical footprint), the private working set's
size on Windows (Task Manager's Memory), the resident size on Linux. One system call, about a
microsecond, once every 30 s: nothing the HUD would notice. None where it cannot be read.
"""

import ctypes
import logging
import sys

log = logging.getLogger(__name__)

MB = 1024 * 1024


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


def _windows():
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    counters = _ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    process = ctypes.c_void_p(kernel32.GetCurrentProcess())
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


class MemoryWatch:
    """TurboHUD's memory in one log line on each flush (the 30 s summary), with the most seen."""

    def __init__(self, read=own_memory, log_line=None):
        self._read = read
        self._log_line = log_line or log.info
        self.most = 0

    def flush(self):
        size = self._read()
        if size is None:
            return
        self.most = max(self.most, size)
        self._log_line('memory: TurboHUD %.0f MB (most so far %.0f MB)', size / MB, self.most / MB)


watch = MemoryWatch()


__all__ = ['MemoryWatch', 'own_memory', 'watch']
