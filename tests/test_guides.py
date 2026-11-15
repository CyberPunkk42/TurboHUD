"""The players' guides stay in step with the app (asked for by the user on 2026-11-15).

QUICK_START.md and USER_GUIDE.md ship in every download (tools/build_app.py, GUIDES). These tests
collect what the player sees from the app itself: the sections, the tray menu, the move-mode panel's
and the settings window's buttons and labels, the options and the shortcuts. A name the app shows that
a guide does not mention fails here, so a new or renamed part of the UI needs its guide line in the
same branch."""

import importlib.util
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from turbohud.core.hud import CLOCK_SECTIONS, PANEL_CATEGORIES, RACE_SECTIONS, help_lines

QUICK_START = ROOT / 'QUICK_START.md'
USER_GUIDE = ROOT / 'USER_GUIDE.md'
SHORTCUTS = ('Ctrl+Shift+L', 'Ctrl+Shift+F12', 'Ctrl+Shift+1', 'Ctrl+Shift+5', 'Ctrl+Shift+Q')
COMMANDS = ('--toggle', '--move', '--lock', '--settings', '--preset', '--quit', '--launch-option')
_TAG = re.compile(r'<[^>]+>')
_ACTION = re.compile(r"""(?:QAction\(|addMenu\()\s*'((?:[^'\\]|\\.)+)'""")


def plain(text):
    """Text as compared: no Markdown or HTML marks, one space for any run of them, any case, and
    '...' for the ellipsis character."""
    text = _TAG.sub('', text).replace('…', '...').replace('**', '').replace('`', '')
    return ' '.join(text.split()).lower()


def label(text):
    """A widget's text as a name to look for, or None for what is no name (a symbol, a number,
    a window title)."""
    text = plain(text).rstrip(':').strip()
    if len(text) <= 1 or text.isdigit() or text.startswith('turbohud - '):
        return None
    return text


def section_labels():
    return sorted({section.label for section in RACE_SECTIONS + CLOCK_SECTIONS})


def tray_labels():
    """Every item of the tray icon's menu, read from app.py (the menu is built inside run())."""
    source = (ROOT / 'turbohud' / 'app.py').read_text(encoding='utf-8')
    return sorted({found.replace("\\'", "'") for found in _ACTION.findall(source)})


class GuideTestCase(unittest.TestCase):
    def assertMentions(self, path, names):
        text = plain(path.read_text(encoding='utf-8'))
        missing = [name for name in names if plain(name) not in text]
        self.assertEqual(missing, [], f'{path.name} does not mention these; add them to it')


class BothGuidesTests(GuideTestCase):
    def test_every_section_is_in_both(self):
        for guide in (QUICK_START, USER_GUIDE):
            self.assertMentions(guide, section_labels())

    def test_every_shortcut_is_in_both(self):
        for guide in (QUICK_START, USER_GUIDE):
            self.assertMentions(guide, SHORTCUTS)


class UserGuideTests(GuideTestCase):
    def test_every_panel_heading(self):
        self.assertMentions(USER_GUIDE, [heading for heading, _names in PANEL_CATEGORIES])

    def test_every_tray_menu_item(self):
        labels = tray_labels()
        self.assertIn('Quit TurboHUD', labels)  # the reading of app.py still finds the menu
        self.assertMentions(USER_GUIDE, labels)

    def test_every_lap_times_column(self):
        from turbohud.app import LAP_COLUMN_OPTIONS

        self.assertMentions(USER_GUIDE, [text for _column, text, _tip in LAP_COLUMN_OPTIONS])

    def test_every_linux_command(self):
        self.assertMentions(USER_GUIDE, COMMANDS)


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class UserGuideWindowTests(GuideTestCase):
    """The move-mode panel and the settings window as the app makes them, offscreen."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    class Native:
        name = 'test'

        def raise_window(self, widget):
            return 'shown'

    def names(self, window, leave_out=()):
        from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton

        self.addCleanup(window.close)
        texts = [w.text() for kind in (QPushButton, QLabel, QCheckBox) for w in window.findChildren(kind)]
        left_out = {plain(text) for text in leave_out}
        found = {label(text) for text in texts if plain(text) not in left_out}
        return sorted(found - {None})

    def test_every_move_panel_button_and_column(self):
        from turbohud.overlay.window import MovePanel

        panel = MovePanel(self.Native(), RACE_SECTIONS, True)
        self.addCleanup(panel.layouts.close)
        names = self.names(panel, help_lines(True))
        for expected in ('layouts...', 'redo', 'size px', 'lines %'):
            self.assertIn(expected, names)  # the panel is read as meant
        self.assertMentions(USER_GUIDE, names)

    def test_every_layouts_window_control(self):
        from turbohud.core.settings import EVENT_MODES
        from turbohud.overlay.layouts_window import LayoutsWindow
        from turbohud.overlay.window import window_flags

        window = LayoutsWindow(self.Native(), window_flags(), True)
        names = self.names(window)
        for expected in ('load screen default', 'design for', 'load by itself', 'off'):
            self.assertIn(expected, names)  # the window is read as meant
        for _mode, text in EVENT_MODES:
            self.assertIn(label(text), names)  # every kind of event is read from the window
        self.assertMentions(USER_GUIDE, names)

    def test_every_settings_window_control(self):
        from turbohud.core.settings import Theme
        from turbohud.overlay.settings_window import SettingsWindow
        from turbohud.overlay.window import window_flags

        window = SettingsWindow(self.Native(), window_flags(), Theme(), reads_per_second=20)
        names = self.names(window)
        self.assertIn('car classes...', names)
        self.assertMentions(USER_GUIDE, names)


class PlainTests(unittest.TestCase):
    def test_marks_and_line_breaks_do_not_count(self):
        self.assertEqual(plain('**Lap times: tire\n  compound**'), 'lap times: tire compound')
        self.assertEqual(plain('<small><b>TIMING</b></small>'), 'timing')
        self.assertEqual(plain('Export…'), 'export...')

    def test_symbols_numbers_and_titles_are_no_names(self):
        for text in ('↔', 'A', '20', '<b>1</b>', '<b>TurboHUD - Settings</b>', ''):
            self.assertIsNone(label(text))
        self.assertEqual(label('Presets:'), 'presets')


if __name__ == '__main__':
    unittest.main()
