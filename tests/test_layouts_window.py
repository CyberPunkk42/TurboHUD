"""The layouts window: five presets with names, a preset per kind of event, files and the design
screen (asked for by players and the user on 2026-11-15)."""

import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeNative:
    name = 'test'

    def __init__(self):
        self.raised = []

    def raise_window(self, widget):
        self.raised.append(widget)
        return 'shown'


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class LayoutsWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def window(self, shortcuts=True, saved=(), names=None, auto=None):
        from turbohud.overlay.layouts_window import LayoutsWindow
        from turbohud.overlay.window import window_flags

        window = LayoutsWindow(FakeNative(), window_flags(), shortcuts, saved, names, auto)
        self.addCleanup(window.close)
        return window

    def test_five_presets_each_with_its_name_box(self):
        window = self.window(names={2: 'Race'})
        self.assertEqual(list(window.name_boxes), [1, 2, 3, 4, 5])
        self.assertEqual(window.name_boxes[2].text(), 'Race')
        self.assertEqual(window.name_boxes[1].placeholderText(), 'Name')

    def test_a_name_is_told_once_tidied(self):
        window = self.window()
        got = []
        window.preset_renamed.connect(lambda number, name: got.append((number, name)))
        box = window.name_boxes[4]
        box.setText('  Hot   laps ')
        box.editingFinished.emit()
        box.editingFinished.emit()  # the same name again: nothing new to tell
        self.assertEqual(got, [(4, 'Hot laps')])
        self.assertEqual(box.text(), 'Hot laps')
        self.assertIn('preset 4 Hot laps', window.preset_saves[4].toolTip())
        box.setText('')
        box.editingFinished.emit()
        self.assertEqual(got[-1], (4, ''))
        self.assertNotIn('Hot laps', window.preset_saves[4].toolTip())

    def test_enter_lets_go_of_the_keyboard(self):
        """After Enter the name box has no cursor (asked for by the user on 2026-11-17)."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        window = self.window()
        window.show()
        box = window.name_boxes[2]
        box.setFocus()
        self.app.processEvents()
        if not box.hasFocus():
            self.skipTest('no keyboard focus here')
        got = []
        window.preset_renamed.connect(lambda *change: got.append(change))
        QTest.keyClicks(box, 'Race')
        QTest.keyClick(box, Qt.Key_Return)
        self.assertFalse(box.hasFocus())
        self.assertEqual(got, [(2, 'Race')])

    def test_a_line_says_what_was_done_then_goes(self):
        from turbohud.overlay import layouts_window

        window = self.window()
        self.assertEqual(window.status.text(), '')
        box = window.name_boxes[3]
        box.setText('Qualifying')
        box.editingFinished.emit()
        self.assertEqual(window.status.text(), '\u2713 Preset 3 named Qualifying')
        self.assertEqual(window.status_timer.interval(), layouts_window.STATUS_SHOWN_MS)
        self.assertTrue(window.status_timer.isActive())
        box.setText('')
        box.editingFinished.emit()
        self.assertEqual(window.status.text(), '\u2713 Preset 3: name removed')
        window.show_status('Preset 1 saved')
        self.assertEqual(window.status.text(), '\u2713 Preset 1 saved')
        window.status_timer.timeout.emit()
        self.assertEqual(window.status.text(), '')
        self.assertGreater(window.status.minimumHeight(), 0)  # keeps its line while empty

    def test_the_panel_passes_a_status_on(self):
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.overlay.window import MovePanel

        panel = MovePanel(FakeNative(), RACE_SECTIONS, True)
        self.addCleanup(panel.close)
        panel.show_preset_status('Preset 2 Race saved')
        self.assertEqual(panel.layouts.status.text(), '\u2713 Preset 2 Race saved')

    def test_names_set_elsewhere_say_nothing_back(self):
        window = self.window()
        got = []
        window.preset_renamed.connect(lambda *change: got.append(change))
        window.set_preset_names({1: 'Practice'})
        self.assertEqual(window.name_boxes[1].text(), 'Practice')
        self.assertEqual(got, [])

    def test_only_a_saved_preset_loads_and_its_load_names_the_shortcut(self):
        window = self.window(saved=(5,))
        self.assertFalse(window.preset_loads[1].isEnabled())
        self.assertTrue(window.preset_loads[5].isEnabled())
        self.assertIn('Ctrl+Shift+5', window.preset_loads[5].toolTip())
        self.assertNotIn('Ctrl+Shift', self.window(shortcuts=False).preset_loads[5].toolTip())
        self.assertIn('empty', window.auto_buttons['race'][1].toolTip())  # nothing would load
        window.set_presets_saved((1,))
        self.assertNotIn('empty', window.auto_buttons['race'][1].toolTip())

    def test_the_buttons_say_which_preset(self):
        window = self.window(saved=(1, 2, 3, 4, 5))
        got = []
        window.preset_save_requested.connect(lambda n: got.append(('save', n)))
        window.preset_load_requested.connect(lambda n: got.append(('load', n)))
        window.preset_delete_requested.connect(lambda n: got.append(('delete', n)))
        window.preset_saves[4].click()
        window.preset_loads[5].click()
        window.preset_deletes[1].click()
        self.assertEqual(got, [('save', 4), ('load', 5), ('delete', 1)])

    def test_a_preset_or_off_for_each_kind_of_event(self):
        from turbohud.core.settings import EVENT_MODES

        window = self.window(auto={'recording': 4})
        self.assertEqual(list(window.auto_buttons), [mode for mode, _label in EVENT_MODES])
        self.assertTrue(window.auto_buttons['recording'][4].isChecked())
        self.assertTrue(window.auto_buttons['race'][0].isChecked())  # Off by default
        got = []
        window.auto_preset_changed.connect(lambda mode, number: got.append((mode, number)))
        window.auto_buttons['special'][5].click()
        window.auto_buttons['recording'][0].click()
        self.assertEqual(got, [('special', 5), ('recording', 0)])
        self.assertFalse(window.auto_buttons['recording'][4].isChecked())  # one choice a mode
        window.set_auto_preset('race', 2)  # from elsewhere: nothing told
        self.assertTrue(window.auto_buttons['race'][2].isChecked())
        self.assertEqual(len(got), 2)

    def test_spectating_has_its_own_row_after_recording(self):
        window = self.window(auto={'recording': 1, 'spectating': 5})
        self.assertEqual(list(window.auto_buttons)[:2], ['recording', 'spectating'])
        self.assertTrue(window.auto_buttons['recording'][1].isChecked())
        self.assertTrue(window.auto_buttons['spectating'][5].isChecked())
        got = []
        window.auto_preset_changed.connect(lambda mode, number: got.append((mode, number)))
        window.auto_buttons['spectating'][3].click()
        self.assertEqual(got, [('spectating', 3)])
        self.assertTrue(window.auto_buttons['recording'][1].isChecked())  # the replay's stays

    def test_every_word_button_is_wide_enough_for_its_word(self):
        # As in the panel (reported by the user on 2026-11-11: macOS cut "Delete" short).
        from PySide6.QtWidgets import QPushButton

        window = self.window(saved=(1,))
        window.show()
        words = ('Save', 'Load', 'Delete', 'Off', 'Load screen default', 'Export…', 'Import…', 'Design')
        buttons = [b for b in window.findChildren(QPushButton) if b.text() in words]
        self.assertEqual({b.text() for b in buttons}, set(words))
        for button in buttons:
            self.assertGreaterEqual(button.width(), button.sizeHint().width(), button.text())

    def test_nothing_is_cut_off_once_this_screens_size_is_in_the_list(self):
        # Reported by the user on 2026-11-15: at move mode's start the list shows "5120x1440 (this
        # screen)", wider than the window was made for, and Design, Save design and Cancel were cut off.
        from PySide6.QtWidgets import QPushButton

        window = self.window(saved=(1,))
        window.show()
        window.set_own_screen((5120, 1440))
        self.app.processEvents()
        for button in window.findChildren(QPushButton):
            self.assertGreaterEqual(button.width(), button.sizeHint().width(), button.text())
        combo = window.design_size
        self.assertGreaterEqual(combo.width(), combo.sizeHint().width())
        self.assertIn('(this screen)', combo.currentText())

    def test_the_panel_opens_it_and_passes_its_signals_on(self):
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.overlay.window import MovePanel

        native = FakeNative()
        panel = MovePanel(
            native, RACE_SECTIONS, True, preset_names={3: 'Quali'}, auto_presets={'hotlapping': 3}
        )
        self.addCleanup(panel.close)
        self.addCleanup(panel.layouts.close)
        self.assertEqual(panel.layouts.name_boxes[3].text(), 'Quali')
        self.assertTrue(panel.layouts.auto_buttons['hotlapping'][3].isChecked())
        got = []
        panel.preset_renamed.connect(lambda *change: got.append(change))
        panel.auto_preset_changed.connect(lambda *change: got.append(change))
        panel.preset_load_requested.connect(lambda n: got.append(('load', n)))
        panel.layouts.name_boxes[1].setText('Race')
        panel.layouts.name_boxes[1].editingFinished.emit()
        panel.layouts.auto_buttons['race'][1].click()
        panel.layouts.preset_loads[1].setEnabled(True)
        panel.layouts.preset_loads[1].click()
        self.assertEqual(got, [(1, 'Race'), ('race', 1), ('load', 1)])
        self.assertFalse(panel.layouts.isVisible())
        panel.show()
        panel.open_layouts()
        self.assertTrue(panel.layouts.isVisible())
        self.assertIn(panel.layouts, native.raised)

    def test_the_panel_no_longer_holds_the_presets(self):
        # The user, 2026-11-15: in a window of their own, so the panel is not crowded.
        from PySide6.QtWidgets import QPushButton

        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.overlay.window import MovePanel

        panel = MovePanel(FakeNative(), RACE_SECTIONS, True)
        self.addCleanup(panel.close)
        self.addCleanup(panel.layouts.close)
        texts = {b.text() for b in panel.findChildren(QPushButton)}
        self.assertIn('Layouts', texts)
        self.assertFalse(texts & {'Save', 'Load', 'Delete', 'Design', 'Export…'})


if __name__ == '__main__':
    unittest.main()
