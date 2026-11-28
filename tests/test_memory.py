"""TurboHUD's own memory in the log every 30 s (asked for by the user on 2026-11-16)."""

import os
import sys
import tempfile
import timeit
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import memory


class OwnMemoryTests(unittest.TestCase):
    def test_this_system_gives_a_size(self):
        if not (sys.platform in ('darwin', 'win32') or sys.platform.startswith('linux')):
            self.skipTest('a system TurboHUD runs on')
        size = memory.own_memory()
        self.assertIsNotNone(size)
        self.assertGreater(size, 1 * memory.MB)  # Python itself takes more
        self.assertLess(size, 64 * 1024 * memory.MB)

    def test_it_grows_with_what_is_held(self):
        if memory.own_memory() is None:
            self.skipTest('not readable here')
        before = memory.own_memory()
        block = bytearray(64 * memory.MB)
        for at in range(0, len(block), 4096):
            block[at] = 1  # touched, so the system gives it pages
        self.assertGreater(memory.own_memory() - before, 32 * memory.MB)

    def test_it_costs_nothing_the_hud_would_notice(self):
        # Once every 30 s; even a millisecond would be far below a frame.
        if memory.own_memory() is None:
            self.skipTest('not readable here')
        each = timeit.timeit(memory.own_memory, number=200) / 200
        self.assertLess(each, 0.001)

    def test_an_unknown_system_says_nothing(self):
        self.assertIsNone(memory.own_memory('sunos5'))

    @unittest.skipUnless(sys.platform == 'win32', 'Windows')
    def test_windows_gives_the_private_working_set(self):
        # Task Manager's Memory: without the pages shared with Windows and Qt's libraries, so
        # less than the whole working set the log showed before (2026-11-28).
        import ctypes

        counters = memory._ProcessMemoryCountersEx2()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.c_void_p(ctypes.WinDLL('kernel32').GetCurrentProcess())
        if not ctypes.WinDLL('psapi').GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
            self.skipTest('a Windows before 10 2004 has no private working set')
        size = memory.own_memory()
        self.assertLess(size, counters.WorkingSetSize)
        self.assertLess(abs(size - counters.PrivateWorkingSetSize), 8 * memory.MB)

    @unittest.skipUnless(hasattr(os, 'sysconf'), "Linux and the Mac: Windows has no page size there")
    def test_linux_reads_its_resident_pages(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'statm'
            path.write_text('50000 12800 900 1 0 3000 0\n', encoding='ascii')
            self.assertEqual(memory._linux(str(path)), 12800 * os.sysconf('SC_PAGE_SIZE'))


class MemoryWatchTests(unittest.TestCase):
    def test_one_line_a_flush_with_the_most_so_far(self):
        sizes = iter([300 * memory.MB, 250 * memory.MB])
        lines = []
        watch = memory.MemoryWatch(lambda: next(sizes), lambda text, *args: lines.append(text % args))
        watch.flush()
        watch.flush()
        self.assertEqual(
            lines,
            ['memory: TurboHUD 300 MB (most so far 300 MB)', 'memory: TurboHUD 250 MB (most so far 300 MB)'],
        )

    def test_nothing_where_it_cannot_be_read(self):
        lines = []
        memory.MemoryWatch(lambda: None, lambda *args: lines.append(args)).flush()
        self.assertEqual(lines, [])

    def test_where_it_is_on_a_second_line(self):
        # Looked into with the user on 2026-11-20: +350 MB in 18 min of racing on Linux.
        lines = []
        watch = memory.MemoryWatch(lambda: 300 * memory.MB, lambda text, *args: lines.append(text % args))
        watch.add_part('Python objects', lambda: '1,000 blocks')
        watch.add_part('C heap', lambda: None)  # not on this system: left out

        def gone():
            raise OSError('gone')

        watch.add_part('drawn texts', gone)
        watch.flush()
        self.assertEqual(lines[1], 'memory parts: Python objects 1,000 blocks; drawn texts not read (gone)')

    def test_tracing_says_where_python_grew(self):
        lines = []
        watch = memory.MemoryWatch(lambda: 300 * memory.MB, lambda text, *args: lines.append(text % args))
        watch.trace()
        self.addCleanup(memory.tracemalloc.stop)
        kept = [bytearray(1000) for _ in range(2000)]  # about 2 MB, here
        watch.flush()
        self.assertTrue(kept)
        grew = [line for line in lines if line.startswith('memory grew:')]
        self.assertTrue(grew)
        self.assertIn('test_memory.py', grew[0])
        self.assertTrue(any(line.startswith('memory traced: Python') for line in lines))

    def test_tracing_only_when_asked(self):
        self.assertFalse(memory.tracing_asked({}))
        self.assertFalse(memory.tracing_asked({'TURBOHUD_TRACE_MEMORY': '0'}))
        self.assertTrue(memory.tracing_asked({'TURBOHUD_TRACE_MEMORY': '1'}))

    def test_paths_in_the_log_name_no_ones_folders(self):
        self.assertEqual(
            memory._short('/home/someone/TurboHUD/turbohud/core/race.py'), 'turbohud/core/race.py'
        )
        self.assertEqual(
            memory._short('C:\\Users\\someone\\venv\\Lib\\site-packages\\PySide6\\x.py'), 'PySide6/x.py'
        )
        self.assertEqual(memory._short('/home/someone/odd.py'), 'odd.py')

    def test_the_c_heap_on_linux_only(self):
        self.assertIsNone(memory.c_heap('win32'))
        if sys.platform.startswith('linux'):
            used, free, _large = memory.c_heap()
            self.assertGreater(used, 0)
            self.assertGreaterEqual(free, 0)


if __name__ == '__main__':
    unittest.main()
