import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from turbokit.core import hud


class ClockTests(unittest.TestCase):
    def test_clock(self):
        self.assertEqual(hud.clock(0), '0:00')
        self.assertEqual(hud.clock(83.9), '1:23')
        self.assertEqual(hud.clock(600), '10:00')


class HelpTextTests(unittest.TestCase):
    def test_nothing_while_locked(self):
        self.assertEqual(hud.help_text(locked=True, shortcuts=True), '')
        self.assertEqual(hud.help_text(locked=True, shortcuts=False), '')

    def test_move_mode_says_how_to_lock(self):
        self.assertIn('Ctrl+Shift+L', hud.help_text(locked=False, shortcuts=True))
        self.assertIn('Lock', hud.help_text(locked=False, shortcuts=False))
        self.assertNotIn('Ctrl', hud.help_text(locked=False, shortcuts=False))


class HudLinesTests(unittest.TestCase):
    def test_locked_shows_title_and_clock(self):
        lines = hud.hud_lines(65, locked=True, shortcuts=True)
        self.assertEqual([line.color for line in lines], ['text', 'accent'])
        self.assertEqual(lines[1].text, '1:05')

    def test_move_mode_adds_the_hint_below(self):
        lines = hud.hud_lines(0, locked=False, shortcuts=True)
        self.assertEqual(len(lines), 3)
        baselines = [line.baseline for line in lines]
        self.assertEqual(baselines, sorted(baselines))

    def test_scale_grows_sizes_and_spacing(self):
        normal = hud.hud_lines(0, locked=False, shortcuts=True)
        double = hud.hud_lines(0, locked=False, shortcuts=True, scale=2)
        for one, two in zip(normal, double, strict=True):
            self.assertAlmostEqual(two.size, 2 * one.size, delta=1)
            self.assertAlmostEqual(two.baseline, 2 * one.baseline, delta=2)


class CoreIsQtFreeTests(unittest.TestCase):
    def test_core_does_not_use_qt(self):
        for path in (ROOT / 'turbokit' / 'core').glob('*.py'):
            with self.subTest(path=path.name):
                self.assertNotIn('PySide6', path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
