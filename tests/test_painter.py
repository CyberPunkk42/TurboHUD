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

    def text_box(self, name, rows, size_share=1.0, height=None):
        """(left, top, right, bottom) of the bright pixels in a section at that share of
        its size, and the window's size: the text is white, the pedal bars are not, and
        text this small has hardly a pixel of its exact colour."""
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        section = next(section for section in RACE_SECTIONS if section.name == name)
        window = SectionWindow(Native(), Theme(), section)
        self.addCleanup(window.close)
        window.resize(window.base[0], height or round(window.base[1] * size_share))
        window.show_content(rows)
        image = window.grab().toImage()
        found = [
            (x, y)
            for x in range(image.width())
            for y in range(image.height())
            if min(image.pixelColor(x, y).getRgb()) >= 150
        ]
        xs, ys = [x for x, _y in found], [y for _x, y in found]
        return (min(xs), min(ys), max(xs), max(ys)), (image.width(), image.height())

    def test_the_speed_stays_centred_between_its_bars_when_shrunk(self):
        from turbohud.core.hud import Row

        for share in (1.0, 0.6, 0.35):
            with self.subTest(share=share):
                # Digits only: it centres on their height.
                (left, top, right, bottom), (width, height) = self.text_box(
                    'speed', [Row('000', 'medium')], share
                )
                self.assertLessEqual(abs(left - (width - 1 - right)), 3)
                self.assertLessEqual(abs(top - (height - 1 - bottom)), 3)

    def test_text_without_bars_keeps_to_the_left_when_shrunk(self):
        from turbohud.core.hud import MARGIN, Row

        (left, _top, _right, _bottom), _size = self.text_box('localtime', [Row('12:34', 'medium')], 0.5)
        self.assertLessEqual(left, MARGIN + 3)

    def test_the_text_shrinks_with_the_box(self):
        from turbohud.core.hud import Row

        rows = [Row('12:34', 'medium')]

        def tall(share):
            (_left, top, _right, bottom), _size = self.text_box('localtime', rows, share)
            return bottom - top

        self.assertGreater(tall(2.0), tall(1.0))
        self.assertLess(tall(0.7), tall(1.0))

    def test_every_text_section_fits_closely_in_its_box(self):
        from turbohud.core.hud import RACE_SECTIONS

        for section in RACE_SECTIONS:
            if section.bar:
                continue
            for share in (1.0, 2.0, 0.6):
                with self.subTest(section=section.name, share=share):
                    (_left, top, _right, bottom), (_width, height) = self.text_box(
                        section.name, list(section.samples[0]), share
                    )
                    self.assertGreaterEqual(top, 1)
                    self.assertLessEqual(bottom, height - 2)


if __name__ == '__main__':
    unittest.main()
