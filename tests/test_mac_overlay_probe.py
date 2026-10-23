import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))

import mac_overlay_probe as probe


def window(owner, pid, layer, width, height):
    return {'owner': owner, 'pid': pid, 'layer': layer, 'width': width, 'height': height}


class ParseArgsTests(unittest.TestCase):
    def test_defaults(self):
        args = probe.parse_args([])
        self.assertEqual(args.level, 'screensaver')
        self.assertEqual((args.x, args.y, args.width, args.height), (None, None, 640, 120))

    def test_rejects_bad_values(self):
        for argv in (['--width', '0'], ['--seconds', '0'], ['--level', 'sky']):
            with (
                self.subTest(argv=argv),
                self.assertRaises(SystemExit),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                probe.parse_args(argv)


class LevelTests(unittest.TestCase):
    def test_named_levels(self):
        self.assertEqual(probe.level_value('floating', 0), 3)
        self.assertEqual(probe.level_value('screensaver', 0), 1000)

    def test_shielding_goes_just_above_a_captured_display(self):
        self.assertEqual(probe.level_value('shielding', 2147483628), 2147483629)

    def test_levels_rise_in_order(self):
        fixed = [value for value in probe.LEVELS.values() if value is not None]
        self.assertEqual(fixed, sorted(fixed))


class CocoaFrameTests(unittest.TestCase):
    def test_top_left_becomes_bottom_left(self):
        self.assertEqual(probe.cocoa_frame(40, 40, 640, 120, 1329), (40, 1169, 640, 120))

    def test_converting_twice_gives_the_start(self):
        x, y, width, height = probe.cocoa_frame(40, 40, 640, 120, 1329)
        self.assertEqual(probe.cocoa_frame(x, y, width, height, 1329), (40, 40, 640, 120))


class MoveModeCheckTests(unittest.TestCase):
    def test_waits_until_the_overlay_has_been_active(self):
        self.assertEqual(probe.move_mode_check(front_pid=5, own_pid=7, was_front=False), (False, False))

    def test_notes_when_the_overlay_is_active(self):
        self.assertEqual(probe.move_mode_check(front_pid=7, own_pid=7, was_front=False), (True, False))

    def test_locks_when_another_app_becomes_active_afterwards(self):
        self.assertEqual(probe.move_mode_check(front_pid=5, own_pid=7, was_front=True), (True, True))

    def test_no_active_app_after_being_active_also_locks(self):
        self.assertEqual(probe.move_mode_check(front_pid=None, own_pid=7, was_front=True), (True, True))


class FourccTests(unittest.TestCase):
    def test_known_codes(self):
        self.assertEqual(probe.fourcc('keyb'), 0x6B657962)
        self.assertEqual(probe.fourcc('----'), 0x2D2D2D2D)

    def test_rejects_wrong_length(self):
        with self.assertRaises(ValueError):
            probe.fourcc('key')


class PositionFileTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sub' / 'mac_overlay_probe.json'
            probe.save_position(path, 300, 12)
            self.assertEqual(probe.load_position(path), (300, 12))

    def test_missing_or_broken_file_gives_none(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'mac_overlay_probe.json'
            self.assertIsNone(probe.load_position(path))
            for content in ('not json', '{"x": 1}', '[1, 2]'):
                with self.subTest(content=content):
                    path.write_text(content, encoding='utf-8')
                    self.assertIsNone(probe.load_position(path))


class WindowListTests(unittest.TestCase):
    screen = (2056, 1329)

    def test_summary_lists_the_overlay_and_large_windows_only(self):
        windows = [
            window('Python', 7, 1000, 640, 120),
            window('Notes', 9, 0, 800, 600),
            window('TSU.exe', 5, 25, 2056, 1329),
        ]
        self.assertEqual(
            probe.window_summary(windows, *self.screen, own_pid=7),
            ['this overlay: level 1000, 640x120', 'TSU.exe: level 25, 2056x1329'],
        )

    def test_overlay_in_front_of_the_game(self):
        windows = [window('Python', 7, 1000, 640, 120), window('TSU.exe', 5, 25, 2056, 1329)]
        self.assertTrue(probe.overlay_in_front(windows, *self.screen, own_pid=7))

    def test_game_in_front_of_the_overlay(self):
        windows = [window('TSU.exe', 5, 1001, 2056, 1329), window('Python', 7, 1000, 640, 120)]
        self.assertFalse(probe.overlay_in_front(windows, *self.screen, own_pid=7))

    def test_small_windows_in_front_do_not_count(self):
        windows = [window('Notes', 9, 0, 800, 600), window('Python', 7, 1000, 640, 120)]
        self.assertTrue(probe.overlay_in_front(windows, *self.screen, own_pid=7))

    def test_overlay_not_on_screen(self):
        self.assertIsNone(
            probe.overlay_in_front([window('TSU.exe', 5, 0, 2056, 1329)], *self.screen, own_pid=7)
        )


class MiscTests(unittest.TestCase):
    def test_log_and_position_files_are_in_the_ignored_tools_folder(self):
        self.assertEqual(probe.LOG_FILE.parent.name, '.buildtools')
        self.assertEqual(probe.POSITION_FILE.parent.name, '.buildtools')

    @unittest.skipIf(sys.platform == 'darwin', 'checks the message shown on other systems')
    def test_other_systems_are_pointed_to_the_windows_probe(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(probe.main(['--seconds', '1']), 2)
        self.assertIn('overlay_probe.py', out.getvalue())


if __name__ == '__main__':
    unittest.main()
