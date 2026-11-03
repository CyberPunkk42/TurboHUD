import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class TextPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_overlapping_parts_of_a_letter_are_filled(self):
        # A plus is two overlapping bars in many fonts; filled odd-even, its centre was
        # a hole, which is what made letters such as the 4 look broken.
        from turbohud.hud.painter import text_path

        path = text_path('+', 80)
        self.assertTrue(path.contains(path.boundingRect().center()))

    def test_paths_are_reused(self):
        from turbohud.hud.painter import text_path

        self.assertIs(text_path('0:44', 40), text_path('0:44', 40))

    def test_outlines_are_kept_and_go_round_the_text(self):
        from turbohud.hud.painter import outline_path, text_path

        outline = outline_path('0:44', 40)
        self.assertIs(outline, outline_path('0:44', 40))
        # The outline reaches a little beyond the letters on every side.
        self.assertTrue(outline.boundingRect().contains(text_path('0:44', 40).boundingRect()))


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class RedrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_a_section_is_drawn_again_only_when_its_content_changes(self):
        from turbohud.core.hud import RACE_SECTIONS, Row
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        window = SectionWindow(Native(), Theme(), RACE_SECTIONS[0])
        self.addCleanup(window.close)
        rows = [Row('Lap 1/3', 'title')]
        self.assertTrue(window.show_content(rows))
        self.assertFalse(window.show_content([Row('Lap 1/3', 'title')]))  # equal, not the same list
        self.assertTrue(window.show_content([Row('Lap 2/3', 'title')]))
        self.assertTrue(window.show_content(window.rows, level=(0.5, 'ahead')))
        self.assertEqual(window.level, (0.5, 'ahead'))


if __name__ == '__main__':
    unittest.main()
