"""Move mode's second key, Ctrl+Shift+F12, where another program (AMD Software) has
Ctrl+Shift+L (reported by the user on 2026-11-12)."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud import app
from turbohud.core import hud
from turbohud.overlay import HOTKEY_LOCK, HOTKEY_LOCK_BACKUP, HOTKEY_QUIT, LOCK_KEY_BACKUP


class NoteTests(unittest.TestCase):
    def test_the_note_only_where_ctrl_shift_l_is_taken(self):
        self.assertIsNone(app.taken_note(['Ctrl+Shift+L', 'Ctrl+Shift+F12']))
        self.assertIsNone(app.taken_note([]))  # neither: the tray menu, as without shortcuts
        note = app.taken_note(['Ctrl+Shift+F12'])
        self.assertIn('Ctrl+Shift+L is taken', note)
        self.assertIn('Ctrl+Shift+F12 switches move mode', note)

    def test_the_hint_names_the_key_that_works(self):
        self.assertIn('Ctrl+Shift+L', hud.help_lines(True)[-1])
        self.assertIn('Ctrl+Shift+F12 or Lock', hud.help_lines(True, lock_key='Ctrl+Shift+F12')[-1])

    def test_the_second_key_is_no_altgr_combination(self):
        # Ctrl+Alt is AltGr on many keyboards: AltGr+L types a letter in Polish.
        self.assertNotIn('Alt', LOCK_KEY_BACKUP)


@unittest.skipUnless(sys.platform == 'win32' and importlib.util.find_spec('PySide6'), 'Windows with Qt')
class WindowsRegistrationTests(unittest.TestCase):
    def register(self, taken):
        from turbohud.overlay import windows

        native = windows.Native.__new__(windows.Native)
        calls = []

        def register_hotkey(_window, number, _modifiers, _key):
            calls.append(number)
            return number not in taken

        with (
            mock.patch.object(windows.user32, 'RegisterHotKey', side_effect=register_hotkey),
            mock.patch.object(windows, 'QCoreApplication'),
        ):
            ok = native.register_hotkeys(lambda number: None)
        return ok, native.lock_keys, calls

    def test_both_keys_when_free(self):
        ok, keys, calls = self.register(taken=())
        self.assertTrue(ok)
        self.assertEqual(keys, ['Ctrl+Shift+L', 'Ctrl+Shift+F12'])
        self.assertIn(HOTKEY_LOCK_BACKUP, calls)

    def test_the_second_key_when_ctrl_shift_l_is_taken(self):
        ok, keys, _calls = self.register(taken=(HOTKEY_LOCK,))
        self.assertTrue(ok)  # move mode still has a key
        self.assertEqual(keys, ['Ctrl+Shift+F12'])

    def test_no_shortcuts_without_either_key_or_quit(self):
        self.assertFalse(self.register(taken=(HOTKEY_LOCK, HOTKEY_LOCK_BACKUP))[0])
        self.assertFalse(self.register(taken=(HOTKEY_QUIT,))[0])


if __name__ == '__main__':
    unittest.main()
