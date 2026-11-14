import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'experiments'))

from turbohud.tsu import probe

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

    def test_stops_looking_once_the_started_program_has_ended(self):
        # Stopped before the game was found: no waiting out the timeout.
        started = time.monotonic()
        self.assertIsNone(
            probe.find_game(11, timeout=30, proc_root=self.proc.dir.name, running=lambda: False)
        )
        self.assertLess(time.monotonic() - started, 1)


class GameEnvTests(unittest.TestCase):
    BUNDLE = '/home/a/TurboHUD/_internal'

    def test_from_the_source_folder_the_game_gets_the_same(self):
        env = {'LD_LIBRARY_PATH': '/steam/lib', 'HOME': '/home/a'}
        self.assertEqual(probe.game_env(env, frozen=False), env)

    def test_the_bundled_app_gives_back_steams_library_path(self):
        env = {
            'LD_LIBRARY_PATH': f'{self.BUNDLE}:/steam/lib',
            'LD_LIBRARY_PATH_ORIG': '/steam/lib',
            '_PYI_APPLICATION_HOME_DIR': self.BUNDLE,
            '_PYI_PARENT_PROCESS_LEVEL': '1',
            'SteamAppId': '1234',
        }
        self.assertEqual(
            probe.game_env(env, frozen=True, bundle=self.BUNDLE),
            {'LD_LIBRARY_PATH': '/steam/lib', 'SteamAppId': '1234'},
        )

    def test_a_path_only_pyinstaller_set_is_dropped(self):
        env = {'LD_LIBRARY_PATH': self.BUNDLE, 'HOME': '/home/a'}
        self.assertEqual(probe.game_env(env, frozen=True, bundle=self.BUNDLE), {'HOME': '/home/a'})
        env = {'LD_LIBRARY_PATH': f'{self.BUNDLE}:/other/lib'}
        self.assertEqual(
            probe.game_env(env, frozen=True, bundle=self.BUNDLE), {'LD_LIBRARY_PATH': '/other/lib'}
        )

    def test_the_input_is_left_alone(self):
        env = {'LD_LIBRARY_PATH': self.BUNDLE, 'LD_LIBRARY_PATH_ORIG': '/steam/lib'}
        probe.game_env(env, frozen=True, bundle=self.BUNDLE)
        self.assertEqual(env, {'LD_LIBRARY_PATH': self.BUNDLE, 'LD_LIBRARY_PATH_ORIG': '/steam/lib'})


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux only')
class LiveReadTests(unittest.TestCase):
    def test_reads_own_child(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        time.sleep(0.3)
        exe = Path(f'/proc/{child.pid}/exe').resolve().name
        self.assertTrue(probe.check_read(child.pid, exe).startswith('OK'))


class LapTimeTests(unittest.TestCase):
    def setUp(self):
        import tsu_memory_scan as scan

        self.scan = scan

    def test_three_decimals_cover_ten_values(self):
        self.assertEqual(self.scan.parse_lap_time('1:35.421'), range(954210, 954220))

    def test_four_decimals_are_exact(self):
        self.assertEqual(self.scan.parse_lap_time('1:35.4216'), range(954216, 954217))

    def test_seconds_only(self):
        self.assertEqual(self.scan.parse_lap_time('59.5'), range(595000, 596000))

    def test_rejects_other_text(self):
        with self.assertRaises(ValueError):
            self.scan.parse_lap_time('fast')

    def test_keep_matching_drops_unreadable_and_other_values(self):
        values = [struct.pack('<i', 954216).hex(), None, struct.pack('<i', 5).hex()]
        self.assertEqual(self.scan.keep_matching([1, 2, 3], values, range(954210, 954220)), [1])


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux only')
class ServerTests(unittest.TestCase):
    """The socket service against a stand-in game: a child holding a known lap time."""

    def test_search_finds_a_value_held_by_the_child(self):
        import tsu_memory_scan as scan

        code = (
            'import array, sys, time\n'
            'held = array.array("i", [954216] * 4)\n'
            'print(hex(held.buffer_info()[0]), flush=True)\n'
            'time.sleep(20)\n'
        )
        child = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, text=True)
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        address = int(child.stdout.readline(), 16)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name, 'run', 'tsu-memory.sock')
        server = probe.serve(child.pid, path, Path(folder.name, 'probe.log'))
        self.addCleanup(server.close)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        client = scan.Client(path)
        header, _ = client.ask(op='search', patterns=scan.int32_patterns([954216]))
        self.assertIn(address, header['hits'])
        header, data = client.ask(op='read', address=address, size=4)
        self.assertEqual(struct.unpack('<i', data)[0], 954216)
        client.conn.close()


if __name__ == '__main__':
    unittest.main()
