import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))

import tsu_memory_probe as probe

MAPS = """\
55d0c000-55d0e000 r--p 00000000 103:02 1234 /opt/game/TSU.x64
7f1000000000-7f1000400000 r--p 00000000 103:02 5678 /opt/game/GameAssembly.so
7f1000400000-7f1002000000 r-xp 00400000 103:02 5678 /opt/game/GameAssembly.so
7f1003000000-7f1003001000 rw-p 00000000 00:00 0
7ffd00000000-7ffd00021000 rw-p 00000000 00:00 0 [stack]
"""


class MapsTests(unittest.TestCase):
    def test_parses_regions_with_and_without_paths(self):
        regions = probe.parse_maps(MAPS)
        self.assertEqual(len(regions), 5)
        self.assertEqual(regions[1], (0x7F1000000000, 0x7F1000400000, 'r--p', 0, '/opt/game/GameAssembly.so'))
        self.assertEqual(regions[3][4], '')

    def test_module_base_is_the_mapping_at_offset_zero(self):
        regions = probe.parse_maps(MAPS)
        self.assertEqual(probe.module_base(regions, 'GameAssembly.so'), 0x7F1000000000)
        self.assertIsNone(probe.module_base(regions, 'UnityPlayer.so'))


class FakeProc:
    def __init__(self, processes):
        self.dir = tempfile.TemporaryDirectory()
        for pid, (ppid, name) in processes.items():
            folder = Path(self.dir.name, str(pid))
            folder.mkdir()
            (folder / 'stat').write_text(f'{pid} ({name}) S {ppid} 1 1 0')
            (folder / 'comm').write_text(name + '\n')
        Path(self.dir.name, 'self').mkdir()


class DescendantTests(unittest.TestCase):
    def setUp(self):
        self.proc = FakeProc(
            {
                10: (1, 'python3'),
                11: (10, 'reaper'),
                12: (11, 'pv (bwrap) x'),
                13: (12, 'TSU.x64'),
                20: (1, 'TSU.x64'),
            }
        )
        self.addCleanup(self.proc.dir.cleanup)

    def test_finds_the_whole_chain_below_the_probe(self):
        self.assertEqual(sorted(probe.descendants(10, self.proc.dir.name)), [11, 12, 13])

    def test_finds_only_the_game_below_the_probe(self):
        self.assertEqual(probe.find_game(10, timeout=1, proc_root=self.proc.dir.name), 13)

    def test_a_game_elsewhere_is_not_ours(self):
        self.assertIsNone(probe.find_game(11, timeout=0, proc_root=self.proc.dir.name))


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux only')
class LiveReadTests(unittest.TestCase):
    def test_reads_own_child(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        time.sleep(0.3)
        exe = Path(f'/proc/{child.pid}/exe').resolve().name
        self.assertTrue(probe.check_read(child.pid, exe).startswith('OK'))


if __name__ == '__main__':
    unittest.main()
