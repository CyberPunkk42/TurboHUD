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
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def window(self, theme=None, **options):
        from turbohud.overlay.settings_window import SettingsWindow
        from turbohud.overlay.window import window_flags

        return SettingsWindow(FakeNative(), window_flags(), theme or Theme(), **options)

    OPTIONS = (
        ('mph', 'Speed in mph', False, 'tip'),
        ('sector_bars', 'Sector bars in My laps', True, 'tip'),
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

    # Reported by the user on 2026-11-20: "Class" read as the same switch as "Classes in the standings".
    CLASS_OPTIONS = (
        ('classes', 'Classes in the standings', False, 'tip'),
        ('column_flag', 'Flag', True, 'flag tip'),
        ('column_class', 'Class code', True, 'class tip'),
        ('column_overall', 'Overall place', False, 'overall tip'),
    )

    def test_the_class_columns_are_greyed_out_without_classes_keeping_their_ticks(self):
        from turbohud.overlay.settings_window import NEEDS_TIP

        window = self.window(options=self.CLASS_OPTIONS)
        for key in ('column_class', 'column_overall'):
            self.assertFalse(window.options[key].isEnabled())
            self.assertEqual(window.options[key].toolTip(), NEEDS_TIP)
        self.assertTrue(window.options['column_class'].isChecked())  # kept for when classes come on
        self.assertTrue(window.options['column_flag'].isEnabled())  # needs nothing
        window.options['classes'].click()
        self.assertTrue(window.options['column_class'].isEnabled())
        self.assertEqual(window.options['column_class'].toolTip(), 'class tip')
        self.assertTrue(window.options['column_class'].isChecked())

    def test_classes_turned_off_elsewhere_greys_them_out_too(self):
        options = (('classes', 'Classes in the standings', True, 'tip'), *self.CLASS_OPTIONS[1:])
        window = self.window(options=options)
        self.assertTrue(window.options['column_overall'].isEnabled())
        got = []
        window.option_changed.connect(lambda *change: got.append(change))
        window.set_option('classes', False)  # from the icon's menu
        self.assertFalse(window.options['column_overall'].isEnabled())
        self.assertEqual(got, [])

    def test_the_class_columns_say_what_they_show(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from turbohud.app import LAP_COLUMN_OPTIONS

        labels = {column: label for column, label, _tip in LAP_COLUMN_OPTIONS}
        self.assertEqual((labels['class'], labels['overall']), ('Class code', 'Overall place'))

    def test_the_radar_cameras_are_a_choice_of_two(self):
        # Asked for by the user on 2026-11-15: the radar in third person too, not only "CAM 5".
        options = (('radar_cockpit_only', 'Radar in every camera', True, 'tip'),)
        window = self.window(options=options)
        buttons = window.camera_buttons
        self.assertEqual((buttons[True].text(), buttons[False].text()), ('Cockpit cameras', 'Every camera'))
        self.assertTrue(buttons[True].isChecked())
        self.assertNotIn('radar_cockpit_only', window.options)  # buttons, not a tick box
        got = []
        window.option_changed.connect(lambda *change: got.append(change))
        buttons[False].click()
        self.assertEqual(got, [('radar_cockpit_only', False)])
        self.assertEqual((buttons[True].isChecked(), buttons[False].isChecked()), (False, True))
        window.set_option('radar_cockpit_only', True)  # changed in the menu: shown, nothing said back
        self.assertTrue(buttons[True].isChecked())
        self.assertEqual(len(got), 1)

    def test_the_options_come_under_headings(self):
        from PySide6.QtWidgets import QLabel

        options = (
            ('mph', 'Speed in mph', False, 'tip'),
            ('clan_tags', 'Clan tags in the standings', True, 'tip'),
            ('column_flag', 'Flag', True, 'tip'),
            ('yellow_flags', 'Yellow flags', True, 'tip'),
            ('something_new', 'Something new', True, 'tip'),  # not placed: under More
        )
        window = self.window(options=options, reads_per_second=10)
        headings = [label.text() for label in window.findChildren(QLabel) if '<small>' in label.text()]
        for heading in ('TEXT COLOURS', 'STANDINGS', 'RADAR', 'FLAGS', 'READING THE RACE', 'MORE'):
            self.assertTrue(any(heading in text for text in headings), heading)
        tabs = [window.tabs.tabText(index) for index in range(window.tabs.count())]
        self.assertEqual(tabs, ['Look', 'Sections', 'Race'])  # no Colours tab without its choices
        self.assertEqual(set(window.options), {key for key, *_rest in options})

    # Asked for by drivers on 2026-11-28: TurboHUD closed once TSU closes.
    def test_quit_with_tsu_is_in_the_race_tab_under_turbohud(self):
        from PySide6.QtWidgets import QLabel

        window = self.window(options=(('quit_with_tsu', 'Quit TurboHUD when TSU quits', False, 'tip'),))
        tabs = [window.tabs.tabText(index) for index in range(window.tabs.count())]
        race = window.tabs.widget(tabs.index('Race'))
        self.assertIs(window.options['quit_with_tsu'].parent(), race)
        headings = [label.text() for label in race.findChildren(QLabel) if '<small>' in label.text()]
        self.assertTrue(any('TURBOHUD' in text for text in headings), headings)
        self.assertFalse(any('MORE' in text for text in headings))  # not one of the rest
        got = []
        window.option_changed.connect(lambda key, on: got.append((key, on)))
        window.options['quit_with_tsu'].click()
        self.assertEqual(got, [('quit_with_tsu', True)])

    def test_colour_blind_off_all_or_chosen_sections(self):
        # Asked for by the user on 2026-11-21: for every section or the ones chosen.
        sections = [('fuel', 'Fuel'), ('radar', 'Radar'), ('times', 'My laps')]
        window = self.window(colours=('off', ('fuel',), sections))
        got = []
        window.colour_blind_changed.connect(lambda mode, chosen: got.append((mode, chosen)))
        self.assertIn('Colours', [window.tabs.tabText(i) for i in range(window.tabs.count())])
        self.assertNotIn('blueflag', window.colour_boxes)  # the app leaves the flags out
        self.assertFalse(window.colour_boxes['fuel'].isEnabled())  # ticks only with Chosen sections
        window.colour_buttons['all'].click()
        self.assertEqual(got[-1], ('all', ('fuel',)))
        window.colour_buttons['chosen'].click()
        self.assertTrue(window.colour_boxes['radar'].isEnabled())
        window.colour_boxes['radar'].setChecked(True)
        self.assertEqual(got[-1], ('chosen', ('fuel', 'radar')))
        window.colour_buttons['off'].click()
        self.assertEqual(got[-1], ('off', ('fuel', 'radar')))  # the ticks kept for next time

    def test_legacy_colours_in_the_colours_tab(self):
        from PySide6.QtWidgets import QLabel

        options = (('legacy_colours', 'TSU Legacy colours', False, 'tip'),)
        window = self.window(options=options)
        got = []
        window.option_changed.connect(lambda key, on: got.append((key, on)))
        window.options['legacy_colours'].setChecked(True)
        self.assertEqual(got, [('legacy_colours', True)])
        colours = window.tabs.widget(
            [window.tabs.tabText(i) for i in range(window.tabs.count())].index('Colours')
        )
        names = [label.text() for label in colours.findChildren(QLabel)]
        self.assertTrue({'Health', 'Tires', 'Fuel'} <= set(names))  # TSU's colours shown

    def test_it_stays_compact_with_every_option(self):
        options = [(f'k{n}', f'Option {n}', True, 'tip') for n in range(4)]
        options += [(f'column_{c}', c, True, 'tip') for c in ('flag', 'lap', 'tyre', 'best', 'current')]
        window = self.window(options=options, reads_per_second=10)
        # Rows 6 px apart, not the columns' 24 (a layout inside another takes on its spacing).
        self.assertLess(window.sizeHint().height(), 480)

    def test_the_class_sheet_opens_beside_it_and_lists_every_class(self):
        from PySide6.QtWidgets import QLabel, QPushButton

        from turbohud.core.class_registry import CLASSES

        window = self.window()
        button = next(b for b in window.findChildren(QPushButton) if b.text() == 'Car classes')
        button.click()
        sheet = window.class_sheet
        self.assertTrue(sheet.isVisible())
        text = ''.join(label.text() for label in sheet.findChildren(QLabel))
        self.assertTrue(all(f'<b>{c.code}</b>' in text for c in CLASSES))
        self.assertIn('#2586CC', text)  # GT's colour
        button.click()
        self.assertIs(window.class_sheet, sheet)  # the same one again
        sheet.close_window()
        self.assertFalse(sheet.isVisible())

    def test_about_asks_for_the_about_window(self):
        from PySide6.QtWidgets import QPushButton

        window = self.window()
        got = []
        window.about_requested.connect(lambda: got.append(True))
        next(b for b in window.findChildren(QPushButton) if b.text() == 'About').click()
        self.assertEqual(got, [True])

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


class ColumnTests(unittest.TestCase):
    def test_the_sheet_has_every_category_once_and_in_order(self):
        from turbohud.core.class_registry import CATEGORIES, sheet_columns

        columns = sheet_columns()
        self.assertLessEqual(len(columns), 5)
        self.assertEqual([category for groups in columns for category, _classes in groups], list(CATEGORIES))
