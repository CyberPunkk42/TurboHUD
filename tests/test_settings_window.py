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

    OPTIONS = (
        ('mph', 'Speed in mph', False, 'tip'),
        ('sector_bars', 'Sector bars below the last and best lap', True, 'tip'),
    )

    def test_the_options_show_and_say_which_changed(self):
        window = self.window(options=self.OPTIONS)
        self.assertEqual(
            {key: box.isChecked() for key, box in window.options.items()}, {'mph': False, 'sector_bars': True}
        )
        got = []
        window.option_changed.connect(lambda *change: got.append(change))
        window.options['mph'].click()
        self.assertEqual(got, [('mph', True)])
        window.set_option('sector_bars', False)  # changed in the menu: nothing to say back
        self.assertEqual(got, [('mph', True)])
        self.assertFalse(window.options['sector_bars'].isChecked())
        window.set_option('radar_cone', True)  # not listed: nothing happens

    def test_without_options_there_are_none(self):
        self.assertEqual(self.window().options, {})

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

    def test_the_reads_show_the_chosen_rate_and_say_when_it_changes(self):
        window = self.window(reads_per_second=10)
        self.assertEqual([reads for reads, b in window.read_buttons.items() if b.isChecked()], [10])
        chosen = []
        window.reads_changed.connect(chosen.append)
        window.read_buttons[5].click()
        self.assertEqual(chosen, [5])
        self.assertEqual([reads for reads, b in window.read_buttons.items() if b.isChecked()], [5])

    def test_the_chosen_rate_can_be_seen(self):
        from PySide6.QtGui import QColor

        from turbohud.overlay.settings_window import CHOSEN_RING

        window = self.window(reads_per_second=10)
        window.show()
        self.addCleanup(window.close)

        def fill(button):
            return button.grab().toImage().pixelColor(button.width() // 2, 4)

        self.assertEqual(fill(window.read_buttons[10]), QColor(*CHOSEN_RING))
        self.assertNotEqual(fill(window.read_buttons[20]), QColor(*CHOSEN_RING))

    def test_without_a_live_race_there_is_no_choice_of_reads(self):
        self.assertEqual(self.window().read_buttons, {})

    def press(self, window, button):
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QMouseEvent

        event = QMouseEvent(
            QMouseEvent.MouseButtonPress, QPointF(5, 5), QPointF(5, 5), button, button, Qt.NoModifier
        )
        window.mousePressEvent(event)

    def test_it_moves_when_dragged_by_its_background(self):
        from unittest import mock

        from PySide6.QtCore import Qt

        window = self.window()
        handle = mock.Mock()
        with mock.patch.object(window, 'windowHandle', return_value=handle):
            self.press(window, Qt.RightButton)
            handle.startSystemMove.assert_not_called()
            self.press(window, Qt.LeftButton)
        handle.startSystemMove.assert_called_once()

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
