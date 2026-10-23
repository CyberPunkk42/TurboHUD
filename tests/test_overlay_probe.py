import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))

import overlay_probe as probe


class ExStyleTests(unittest.TestCase):
    def test_click_through_adds_transparent_flag(self):
        style = probe.ex_style(click_through=True)
        self.assertTrue(style & probe.WS_EX_TRANSPARENT)
        self.assertTrue(style & probe.WS_EX_LAYERED)
        self.assertTrue(style & probe.WS_EX_TOPMOST)

    def test_without_click_through_box_takes_clicks(self):
        style = probe.ex_style(click_through=False)
        self.assertFalse(style & probe.WS_EX_TRANSPARENT)
        self.assertTrue(style & probe.WS_EX_TOPMOST)


class LayeredAttributesTests(unittest.TestCase):
    def test_move_mode_tints_the_whole_box(self):
        self.assertEqual(probe.layered_attributes(False, 170), (0, 170, probe.LWA_ALPHA))

    def test_locked_hides_the_background_and_keeps_text_solid(self):
        key, alpha, flags = probe.layered_attributes(True, 170)
        self.assertEqual((key, alpha, flags), (probe.KEY_COLOR, 255, probe.LWA_COLORKEY))

    def test_key_colour_is_neither_the_text_nor_its_shadow(self):
        self.assertNotIn(probe.KEY_COLOR, (0x00FFFFFF, 0x00000000))


class StyleReportTests(unittest.TestCase):
    def test_all_styles_kept(self):
        requested = probe.ex_style(True)
        self.assertEqual(probe.style_report(requested, requested), [])

    def test_names_dropped_styles(self):
        requested = probe.ex_style(True)
        actual = requested & ~probe.WS_EX_TRANSPARENT & ~probe.WS_EX_TOPMOST
        self.assertEqual(probe.style_report(requested, actual), ['topmost', 'click-through'])


class ParseArgsTests(unittest.TestCase):
    def test_defaults_leave_placement_to_the_saved_one(self):
        args = probe.parse_args([])
        self.assertFalse(args.locked)
        self.assertEqual((args.x, args.y, args.width, args.height), (None, None, None, None))

    def test_locked(self):
        self.assertTrue(probe.parse_args(['--locked']).locked)

    def test_rejects_bad_values(self):
        bad = (
            ['--alpha', '256'],
            ['--alpha', '-1'],
            ['--seconds', '0'],
            ['--width', str(probe.MIN_WIDTH - 1)],
            ['--height', str(probe.MIN_HEIGHT - 1)],
        )
        for argv in bad:
            with (
                self.subTest(argv=argv),
                self.assertRaises(SystemExit),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                probe.parse_args(argv)


class PartTests(unittest.TestCase):
    def test_default_size_is_larger_than_the_first_probe(self):
        _, _, width, height = probe.DEFAULT_PLACEMENT
        self.assertGreater(width, 420)
        self.assertGreater(height, 150)

    def test_controls_fit_in_the_smallest_box_without_overlapping(self):
        width, height = probe.MIN_WIDTH, probe.MIN_HEIGHT
        rects = probe.part_rects(width, height)
        lock, close, grip = rects['lock'], rects['close'], rects['resize']
        self.assertLessEqual(lock[2], close[0])
        self.assertLessEqual(close[2], grip[0])
        self.assertEqual((grip[2], grip[3]), (width, height))
        for left, top, right, bottom in rects.values():
            self.assertGreaterEqual(left, 0)
            self.assertGreaterEqual(top, 0)
            self.assertLessEqual(right, width)
            self.assertLessEqual(bottom, height)

    def test_part_at_finds_each_control_and_nothing_elsewhere(self):
        for name, (left, top, right, bottom) in probe.part_rects(640, 240).items():
            with self.subTest(name=name):
                self.assertEqual(probe.part_at((left + right) // 2, (top + bottom) // 2, 640, 240), name)
                self.assertEqual(probe.part_at(left, top, 640, 240), name)
                self.assertIsNone(probe.part_at(left - 1, top - 1, 640, 240))
        self.assertIsNone(probe.part_at(20, 20, 640, 240))


class ResizedTests(unittest.TestCase):
    def test_grows_and_shrinks_with_the_drag(self):
        self.assertEqual(probe.resized(640, 240, 100, -40), (740, 200))

    def test_never_below_the_minimum(self):
        self.assertEqual(probe.resized(640, 240, -1000, -1000), (probe.MIN_WIDTH, probe.MIN_HEIGHT))


class ClientPointTests(unittest.TestCase):
    def test_positive_coordinates(self):
        self.assertEqual(probe.client_point((25 << 16) | 300), (300, 25))

    def test_negative_coordinates(self):
        self.assertEqual(probe.client_point((0xFFFE << 16) | 0xFFFF), (-1, -2))


class PlacementFileTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sub' / 'overlay_probe.json'
            probe.save_placement(path, 812, -5, 900, 300)
            self.assertEqual(probe.load_placement(path), (812, -5, 900, 300))

    def test_saved_size_below_the_minimum_is_raised(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'overlay_probe.json'
            probe.save_placement(path, 0, 0, 10, 10)
            self.assertEqual(probe.load_placement(path), (0, 0, probe.MIN_WIDTH, probe.MIN_HEIGHT))

    def test_missing_old_or_broken_file_gives_none(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'overlay_probe.json'
            self.assertIsNone(probe.load_placement(path))
            broken = ('not json', '{"x": 1, "y": 2}', '[1, 2]', '{"x": "a", "y": 2, "width": 3, "height": 4}')
            for content in broken:
                with self.subTest(content=content):
                    path.write_text(content, encoding='utf-8')
                    self.assertIsNone(probe.load_placement(path))

    def test_placement_file_is_in_the_ignored_tools_folder(self):
        self.assertEqual(probe.PLACEMENT_FILE.parent.name, '.buildtools')


class LogTests(unittest.TestCase):
    def test_log_goes_to_the_terminal_and_the_open_log_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'overlay_probe.log'
            with path.open('w', encoding='utf-8') as log_file:
                probe._log_file = log_file
                try:
                    with contextlib.redirect_stdout(io.StringIO()) as out:
                        probe.log('hello')
                finally:
                    probe._log_file = None
            self.assertIn('hello', out.getvalue())
            self.assertTrue(path.read_text(encoding='utf-8').rstrip().endswith('hello'))

    def test_log_file_is_in_the_ignored_tools_folder(self):
        self.assertEqual(probe.LOG_FILE.parent.name, '.buildtools')


class MainTests(unittest.TestCase):
    @unittest.skipIf(sys.platform == 'win32', 'checks the message shown on other systems')
    def test_other_systems_get_a_pointer_to_crossover(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(probe.main(['--seconds', '1']), 2)
        self.assertIn('CrossOver', out.getvalue())


if __name__ == '__main__':
    unittest.main()
