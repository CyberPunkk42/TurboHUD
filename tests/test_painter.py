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


if __name__ == '__main__':
    unittest.main()
