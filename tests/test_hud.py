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


def measure(text, size):
    """A stand-in for Qt's text width: every letter 0.6 of the font size wide."""
    return len(text) * size * 0.6


class HelpLinesTests(unittest.TestCase):
    def test_move_mode_says_how_to_finish(self):
        self.assertIn('Ctrl+Shift+L', hud.help_lines(shortcuts=True)[-1])
        without = ' '.join(hud.help_lines(shortcuts=False))
        self.assertIn('Lock', without)
        self.assertNotIn('Ctrl', without)


class HudLinesTests(unittest.TestCase):
    def test_session_rows(self):
        lines = hud.hud_lines(hud.session_rows(65))
        self.assertEqual([line.color for line in lines], ['text', 'accent'])
        self.assertEqual(lines[1].text, '1:05')

    def test_rows_use_their_style_and_colour(self):
        lines = hud.hud_lines([hud.Row('a', 'title'), hud.Row('b', 'medium', 'accent')])
        sizes = hud.Sizes.for_scale(1)
        self.assertEqual([(line.size, line.color) for line in lines], [(sizes.title, 'text'), (sizes.medium, 'accent')])

    def test_lines_go_down_and_grow_with_the_scale(self):
        normal = hud.hud_lines(hud.session_rows(0))
        double = hud.hud_lines(hud.session_rows(0), scale=2)
        self.assertLess(normal[0].baseline, normal[1].baseline)
        for one, two in zip(normal, double, strict=True):
            self.assertAlmostEqual(two.size, 2 * one.size, delta=1)
            self.assertAlmostEqual(two.baseline, 2 * one.baseline, delta=2)


class SectionTests(unittest.TestCase):
    def test_race_sections_have_distinct_names(self):
        names = [section.name for section in hud.RACE_SECTIONS]
        self.assertEqual(names, ['lap', 'current', 'delta', 'times'])

    def test_content_size_fits_the_text(self):
        width, height = hud.content_size([hud.Row('0:00.0', 'big')], 1, measure)
        sizes = hud.Sizes.for_scale(1)
        self.assertEqual(width, round(6 * 40 * 0.6 + 2 * sizes.margin))
        self.assertGreater(height, sizes.big)

    def test_base_size_fits_every_sample(self):
        lap = hud.RACE_SECTIONS[0]
        width, _ = hud.base_size(lap, 1, measure)
        for rows in lap.samples:
            self.assertGreaterEqual(width, hud.content_size(rows, 1, measure)[0])

    def test_resizing_scales_the_content_and_keeps_its_shape(self):
        self.assertEqual(hud.section_scale((200, 50), (100, 50)), 1.0)
        self.assertEqual(hud.section_scale((300, 150), (100, 50)), 3.0)
        self.assertEqual(hud.section_scale((10, 5), (100, 50)), 0.5)  # never below half

    def test_first_start_stacks_the_sections_where_the_hud_was(self):
        sizes = {'lap': (200, 40), 'current': (150, 60), 'delta': (180, 30), 'times': (300, 30)}
        places = hud.stacked(hud.RACE_SECTIONS, 40, 40, sizes, gap=8)
        self.assertEqual(places['lap'], (40, 40, 200, 40))
        self.assertEqual(places['current'], (40, 88, 150, 60))
        self.assertEqual(places['times'][1], 40 + 40 + 8 + 60 + 8 + 30 + 8)


class CoreIsQtFreeTests(unittest.TestCase):
    def test_core_does_not_use_qt(self):
        for path in (ROOT / 'turbohud' / 'core').glob('*.py'):
            with self.subTest(path=path.name):
                self.assertNotIn('PySide6', path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
