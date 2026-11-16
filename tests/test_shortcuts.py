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

    def test_on_hyprland_the_note_names_a_bind(self):
        note = app.taken_note(['Ctrl+Shift+F12'], taken_by='another Hyprland bind')
        self.assertIn('Ctrl+Shift+L is taken by another Hyprland bind', note)
        self.assertNotIn('AMD', note)

    def test_the_hint_names_the_key_that_works(self):
        self.assertIn('Ctrl+Shift+L', hud.help_lines(True)[-1])
        self.assertIn('Ctrl+Shift+F12 or Lock', hud.help_lines(True, lock_key='Ctrl+Shift+F12')[-1])

    def test_the_second_key_is_no_altgr_combination(self):
        # Ctrl+Alt is AltGr on many keyboards: AltGr+L types a letter in Polish.
        self.assertNotIn('Alt', LOCK_KEY_BACKUP)


@unittest.skipUnless(sys.platform == 'win32' and importlib.util.find_spec('PySide6'), 'Windows with Qt')
class WindowsStackingTests(unittest.TestCase):
    """A group's tint window goes just below the lowest shown section (2026-11-16)."""

    def test_the_lowest_of_the_wanted_windows(self):
        from turbohud.overlay import windows

        self.assertEqual(windows.lowest([9, 3, 7, 5, 1], {3, 5}), 5)
        self.assertIsNone(windows.lowest([9, 3], {4}))

    def test_placed_below_without_taking_the_focus(self):
        from turbohud.overlay import windows

        def window(handle):
            return mock.Mock(winId=mock.Mock(return_value=handle))

        native = windows.Native.__new__(windows.Native)
        with (
            mock.patch.object(windows, 'window_order', return_value=[1, 2, 3, 4]),
            mock.patch.object(windows.user32, 'SetWindowPos', return_value=1) as set_pos,
        ):
            self.assertEqual(native.place_below(window(9), [window(2), window(3)]), 'below its sections')
            self.assertEqual(native.place_below(window(9), [window(8)]), 'nothing to go below')
        hwnd, after, *_place, flags = set_pos.call_args.args
        self.assertEqual((hwnd, after), (9, 3))
        self.assertTrue(flags & windows.SWP_NOACTIVATE)
        self.assertEqual(set_pos.call_count, 1)


@unittest.skipUnless(sys.platform == 'win32' and importlib.util.find_spec('PySide6'), 'Windows with Qt')
class WindowsMoveModeFocusTests(unittest.TestCase):
    """Move mode brings its panel in front, so TSU no longer holds its pointer hidden (reported by
    players on 2026-11-16: no pointer until TSU's menu was opened with ESC)."""

    def native(self):
        from turbohud.overlay import windows

        return windows, windows.Native.__new__(windows.Native)

    def panel(self, handle=9):
        return mock.Mock(winId=mock.Mock(return_value=handle))

    def test_the_panel_comes_in_front(self):
        windows, native = self.native()
        with (
            mock.patch.object(windows.user32, 'SetForegroundWindow', return_value=1) as front,
            mock.patch.object(windows.user32, 'AttachThreadInput') as attach,
        ):
            self.assertEqual(native.activate(self.panel()), 'in front')
        front.assert_called_once_with(9)
        attach.assert_not_called()

    def test_refused_it_tries_again_joined_to_the_games_input(self):
        windows, native = self.native()
        with (
            mock.patch.object(windows.user32, 'SetForegroundWindow', side_effect=[0, 1]) as front,
            mock.patch.object(windows.user32, 'GetForegroundWindow', return_value=5),
            mock.patch.object(windows.user32, 'GetWindowThreadProcessId', return_value=77),
            mock.patch.object(windows.kernel32, 'GetCurrentThreadId', return_value=11),
            mock.patch.object(windows.user32, 'AttachThreadInput') as attach,
        ):
            self.assertEqual(native.activate(self.panel()), "in front, joined to the game's input")
        self.assertEqual(front.call_count, 2)
        self.assertEqual(attach.call_args_list, [mock.call(11, 77, True), mock.call(11, 77, False)])

    def test_refused_twice_it_says_so_and_detaches(self):
        windows, native = self.native()
        with (
            mock.patch.object(windows.user32, 'SetForegroundWindow', return_value=0),
            mock.patch.object(windows.user32, 'GetForegroundWindow', return_value=5),
            mock.patch.object(windows.user32, 'GetWindowThreadProcessId', return_value=77),
            mock.patch.object(windows.kernel32, 'GetCurrentThreadId', return_value=11),
            mock.patch.object(windows.user32, 'AttachThreadInput') as attach,
        ):
            self.assertTrue(native.activate(self.panel()).startswith('not in front'))
        self.assertEqual(attach.call_args_list[-1], mock.call(11, 77, False))

    def test_the_game_comes_back_when_locked(self):
        windows, native = self.native()
        with mock.patch.object(windows.user32, 'GetForegroundWindow', return_value=5):
            native.take_focus()
        with mock.patch.object(windows.user32, 'SetForegroundWindow', return_value=1) as front:
            native.give_focus_back()
        front.assert_called_once_with(5)


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
