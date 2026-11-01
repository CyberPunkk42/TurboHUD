import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from turbohud.core import hud


class ClockTests(unittest.TestCase):
    def test_clock(self):
        self.assertEqual(hud.clock(0), '0:00')
        self.assertEqual(hud.clock(83.9), '1:23')
        self.assertEqual(hud.clock(600), '10:00')


class HelpLinesTests(unittest.TestCase):
    def test_nothing_while_locked(self):
        self.assertEqual(hud.help_lines(locked=True, shortcuts=True), [])
        self.assertEqual(hud.help_lines(locked=True, shortcuts=False), [])

    def test_move_mode_says_how_to_finish(self):
        self.assertIn('Ctrl+Shift+L', hud.help_lines(locked=False, shortcuts=True)[-1])
        without = ' '.join(hud.help_lines(locked=False, shortcuts=False))
        self.assertIn('Lock', without)
        self.assertNotIn('Ctrl', without)


class HudLinesTests(unittest.TestCase):
    controls = 44  # height of the Lock and Close row

    def test_locked_shows_title_and_clock(self):
        lines = hud.hud_lines(hud.session_rows(65), locked=True, shortcuts=True)
        self.assertEqual([line.color for line in lines], ['text', 'accent'])
        self.assertEqual(lines[1].text, '1:05')

    def test_hint_sits_just_above_the_buttons(self):
        height = 300
        lines = hud.hud_lines(hud.session_rows(0), locked=False, shortcuts=True, hint_bottom=height - self.controls)
        hint = lines[2:]
        self.assertEqual(len(hint), 2)
        self.assertLess(hint[-1].baseline, height - self.controls)
        self.assertGreater(hint[-1].baseline, height - self.controls - 2 * hint[-1].size)

    def test_nothing_overlaps_at_the_minimum_size(self):
        for scale in (0.5, 1, 1.5, 2, 3):
            with self.subTest(scale=scale):
                _, height = hud.min_size(scale, self.controls)
                bottom = height - self.controls
                lines = hud.hud_lines(hud.session_rows(0), locked=False, shortcuts=True, scale=scale, hint_bottom=bottom)
                clock_line, first_hint = lines[1], lines[2]
                # The hint's first line starts below the clock's baseline.
                self.assertGreaterEqual(first_hint.baseline - first_hint.size, clock_line.baseline)
                self.assertLessEqual(lines[-1].baseline, bottom)

    def test_the_tallest_content_fits_at_the_minimum_size(self):
        for scale in (0.5, 1, 2, 3):
            with self.subTest(scale=scale):
                _, height = hud.min_size(scale, self.controls)
                bottom = height - self.controls
                lines = hud.hud_lines(list(hud.TALLEST), locked=False, shortcuts=True, scale=scale, hint_bottom=bottom)
                content, first_hint = lines[len(hud.TALLEST) - 1], lines[len(hud.TALLEST)]
                self.assertGreaterEqual(first_hint.baseline - first_hint.size, content.baseline)

    def test_rows_use_their_style_and_colour(self):
        lines = hud.hud_lines([hud.Row('a', 'title'), hud.Row('b', 'medium', 'accent')], locked=True, shortcuts=True)
        sizes = hud.Sizes.for_scale(1)
        self.assertEqual([(line.size, line.color) for line in lines], [(sizes.title, 'text'), (sizes.medium, 'accent')])

    def test_without_a_bottom_the_hint_follows_the_clock(self):
        lines = hud.hud_lines(hud.session_rows(0), locked=False, shortcuts=True)
        baselines = [line.baseline for line in lines]
        self.assertEqual(baselines, sorted(baselines))

    def test_scale_grows_sizes_and_spacing(self):
        normal = hud.hud_lines(hud.session_rows(0), locked=False, shortcuts=True)
        double = hud.hud_lines(hud.session_rows(0), locked=False, shortcuts=True, scale=2)
        for one, two in zip(normal, double, strict=True):
            self.assertAlmostEqual(two.size, 2 * one.size, delta=1)
            self.assertAlmostEqual(two.baseline, 2 * one.baseline, delta=2)

    def test_minimum_width_grows_with_the_scale(self):
        self.assertEqual(hud.min_size(1, self.controls)[0], hud.MIN_WIDTH)
        self.assertEqual(hud.min_size(0.5, self.controls)[0], hud.MIN_WIDTH)
        self.assertEqual(hud.min_size(2, self.controls)[0], 2 * hud.MIN_WIDTH)


class CoreIsQtFreeTests(unittest.TestCase):
    def test_core_does_not_use_qt(self):
        for path in (ROOT / 'turbohud' / 'core').glob('*.py'):
            with self.subTest(path=path.name):
                self.assertNotIn('PySide6', path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
