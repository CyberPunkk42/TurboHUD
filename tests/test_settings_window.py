import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core.settings import Theme


class FakeNative:
    name = 'test'

    def raise_window(self, widget):
        return 'shown'


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class SettingsWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def window(self, theme=None, **options):
        from turbohud.overlay.settings_window import SettingsWindow
        from turbohud.overlay.window import window_flags

        return SettingsWindow(FakeNative(), window_flags(), theme or Theme(), **options)

    def test_the_warning_times_show_and_say_when_they_change(self):
        window = self.window(blue_seconds=3.0, radar_seconds=0.8)
        self.assertEqual((window.blue_seconds.value(), window.radar_seconds.value()), (3.0, 0.8))
        blue, radar = [], []
        window.blue_seconds_changed.connect(blue.append)
        window.radar_seconds_changed.connect(radar.append)
        window.blue_seconds.stepUp()
        window.radar_seconds.stepUp()
        self.assertEqual(blue, [3.5])
        self.assertAlmostEqual(radar[0], 0.9)
        window.blue_seconds.setValue(99)
        self.assertEqual(blue[-1], 10.0)

    def test_a_swatch_changes_that_colour_only(self):
        window = self.window()
        got = []
        window.theme_changed.connect(got.append)
        cyan = next(b for b in window.swatches['text_color'] if b.color == '#5ec8ff')
        cyan.click()
        self.assertEqual(got[-1].text_color, '#5ec8ff')
        self.assertEqual(got[-1].accent_color, Theme().accent_color)
        self.assertTrue(cyan.chosen)

    def test_reset_brings_the_default_colours_back(self):
        window = self.window(Theme(text_color='#ff8fd0', outline_color='#00000000', scale=1.2))
        got = []
        window.theme_changed.connect(got.append)
        window.reset()
        self.assertEqual(
            (got[-1].text_color, got[-1].outline_color), (Theme().text_color, Theme().outline_color)
        )
        self.assertEqual(got[-1].scale, 1.2)  # the scale is not a colour

    def test_bigger_and_smaller_ask_for_a_factor(self):
        from PySide6.QtWidgets import QPushButton

        window = self.window()
        got = []
        window.resize_requested.connect(got.append)
        for button in window.findChildren(QPushButton):
            if button.text() in ('Bigger', 'Smaller'):
                button.click()
        self.assertEqual(sorted(round(f, 3) for f in got), [0.909, 1.1])
