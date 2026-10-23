import contextlib
import importlib.util
import io
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))

import qt_overlay_probe as probe


class ParseArgsTests(unittest.TestCase):
    def test_defaults(self):
        args = probe.parse_args([])
        self.assertEqual((args.x, args.y, args.width, args.height), (None, None, None, None))
        self.assertEqual(args.level, 'screensaver')
        self.assertFalse(args.move)

    def test_rejects_bad_values(self):
        for argv in (['--width', '0'], ['--height', '-5'], ['--seconds', '0'], ['--level', 'sky']):
            with (
                self.subTest(argv=argv),
                self.assertRaises(SystemExit),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                probe.parse_args(argv)


class PlacementTests(unittest.TestCase):
    def test_default_without_saved_or_given_values(self):
        self.assertEqual(probe.placement(probe.parse_args([]), None), probe.DEFAULT_PLACEMENT)

    def test_given_values_win_over_saved_ones(self):
        args = probe.parse_args(['--x', '300', '--height', '400'])
        self.assertEqual(probe.placement(args, (10, 20, 800, 200)), (300, 20, 800, 400))

    def test_small_sizes_are_raised_to_the_minimum(self):
        args = probe.parse_args(['--width', '10', '--height', '10'])
        self.assertEqual(probe.placement(args, None)[2:], (probe.MIN_WIDTH, probe.MIN_HEIGHT))

    def test_file_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sub' / 'qt_overlay_probe.json'
            probe.save_placement(path, 300, 12, 700, 250)
            self.assertEqual(probe.load_placement(path), (300, 12, 700, 250))

    def test_missing_or_broken_file_gives_none(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'qt_overlay_probe.json'
            self.assertIsNone(probe.load_placement(path))
            for content in ('not json', '{"x": 1}', '[1, 2]'):
                with self.subTest(content=content):
                    path.write_text(content, encoding='utf-8')
                    self.assertIsNone(probe.load_placement(path))


class TextTests(unittest.TestCase):
    def test_help_names_the_shortcuts_where_there_are_some(self):
        self.assertIn('Ctrl+Shift+L', probe.help_text(locked=True, shortcuts=True))
        self.assertIn('locks', probe.help_text(locked=False, shortcuts=True))

    def test_help_without_shortcuts(self):
        self.assertIn('Ctrl+C', probe.help_text(locked=True, shortcuts=False))
        self.assertIn('Lock or Close', probe.help_text(locked=False, shortcuts=False))

    def test_clock(self):
        self.assertEqual(probe.clock(0), '0:00')
        self.assertEqual(probe.clock(83.9), '1:23')
        self.assertEqual(probe.clock(600), '10:00')


class MapDotTests(unittest.TestCase):
    def test_starts_at_the_right_and_comes_back(self):
        for seconds in (0, 8, 16):
            with self.subTest(seconds=seconds):
                x, y = probe.map_dot(seconds)
                self.assertAlmostEqual(x, 1)
                self.assertAlmostEqual(y, 0)

    def test_stays_on_the_oval(self):
        for seconds in (0.5, 2, 3.3, 7.9):
            with self.subTest(seconds=seconds):
                x, y = probe.map_dot(seconds)
                self.assertAlmostEqual(math.hypot(x, y / 0.6), 1)


class MiscTests(unittest.TestCase):
    def test_log_and_placement_files_are_in_the_ignored_tools_folder(self):
        self.assertEqual(probe.LOG_FILE.parent.name, '.buildtools')
        self.assertEqual(probe.PLACEMENT_FILE.parent.name, '.buildtools')

    def test_qt_version_is_pinned(self):
        requirements = Path(probe.__file__).with_name('requirements-qt.txt').read_text(encoding='utf-8')
        pins = [line for line in requirements.splitlines() if line and not line.startswith('#')]
        self.assertEqual(len(pins), 1)
        self.assertRegex(pins[0], r'^PySide6-Essentials==\d+\.\d+\.\d+$')

    @unittest.skipIf(importlib.util.find_spec('PySide6'), 'checks the message shown without Qt')
    def test_without_qt_points_to_the_runners(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(probe.main(['--seconds', '1']), 2)
        self.assertIn('run_qt_overlay_probe', out.getvalue())


if __name__ == '__main__':
    unittest.main()
