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


if __name__ == '__main__':
    unittest.main()
