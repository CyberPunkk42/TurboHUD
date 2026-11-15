import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


class FakeHypr:
    def __init__(self):
        self.where = (300, 200, 450, 220)
        self.focused = []
        self.active = '0xgame'

    def active_window(self):
        return self.active

    def geometry(self, address):
        return self.where

    def focus(self, address):
        self.focused.append(address)
        return True

    def geometries(self, addresses):
        return {address: self.where for address in addresses}

    def move(self, address, x, y):
        self.moved = (address, x, y)
        return True

    def place(self, address, x, y, width, height, focusable=False):
        self.placed = (address, x, y, width, height, focusable)
        return True


class FakeWidget:
    visible = True

    def isVisible(self):
        return self.visible


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class LinuxNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def native(self, hypr):
        from turbohud.overlay.linux import Native

        return Native(hypr)

    def test_without_hyprland_qt_does_it(self):
        self.assertIsNone(self.native(None).placement(FakeWidget()))

    def test_the_last_known_place_is_kept_once_the_window_is_gone(self):
        hypr = FakeHypr()
        native = self.native(hypr)
        widget = FakeWidget()
        native.addresses[id(widget)] = '0xaaa'
        self.assertEqual(native.placement(widget), (300, 200, 450, 220))
        hypr.where, widget.visible = None, False
        self.assertEqual(native.placement(widget), (300, 200, 450, 220))

    def test_focus_goes_back_to_the_window_that_had_it(self):
        hypr = FakeHypr()
        native = self.native(hypr)
        native.prepare_app()
        native.addresses[1] = '0xaaa'
        hypr.active = '0xaaa'  # TurboHUD's panel has it
        native.give_focus_back()
        self.assertEqual(hypr.focused, ['0xgame'])

    def test_no_focus_and_no_mouse_jump_where_the_focus_never_left(self):
        # Hyprland moves the mouse onto a window it focuses: the grid and the sections take no
        # focus, so placing them must not focus the game (or a terminal) again.
        hypr = FakeHypr()
        native = self.native(hypr)
        native.prepare_app()
        native.addresses[1] = '0xaaa'
        hypr.active = '0xbrowser'
        native.give_focus_back()
        self.assertEqual(hypr.focused, [])

    def test_move_mode_remembers_the_window_focused_then(self):
        hypr = FakeHypr()
        native = self.native(hypr)
        hypr.active = '0xterminal'  # where TurboHUD was started from
        native.prepare_app()
        native.addresses[1] = '0xpanel'
        hypr.active = '0xgame'
        native.take_focus()  # move mode begins over the game
        hypr.active = '0xpanel'
        native.give_focus_back()
        self.assertEqual(hypr.focused, ['0xgame'])

    def test_move_mode_never_remembers_its_own_window(self):
        hypr = FakeHypr()
        native = self.native(hypr)
        native.prepare_app()
        native.addresses[1] = '0xpanel'
        hypr.active = '0xpanel'
        native.take_focus()
        self.assertEqual(native.previous, '0xgame')


if __name__ == '__main__':
    unittest.main()

    def test_group_moves_on_hyprland(self):
        hypr = FakeHypr()
        native = self.native(hypr)
        widget = FakeWidget()
        widget.locked = False
        native.addresses[id(widget)] = '0xaaa'
        self.assertEqual(native.placements([widget]), {id(widget): (300, 200, 450, 220)})
        native.move_window(widget, (350, 220, 450, 220))
        self.assertEqual(hypr.moved, ('0xaaa', 350, 220))
        self.assertEqual(native.placement(FakeWidget()), None)  # unknown window: nothing
        native.move_window(widget, (350, 220, 450, 220), settle=True)
        self.assertEqual(hypr.placed, ('0xaaa', 350, 220, 450, 220, True))  # still movable


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class HyprlandShortcutTests(unittest.TestCase):
    """TurboHUD's keys in Hyprland's live keymap while it runs."""

    @classmethod
    def setUpClass(cls):
        LinuxNativeTests.setUpClass()

    def setUp(self):
        from test_hyprland import FakeKeymap

        from turbohud.overlay import hyprland, linux

        self.hyprland, self.linux = hyprland, linux
        self.Keymap = FakeKeymap
        self.no_events = mock.patch.object(hyprland, 'event_socket', return_value=None)
        self.no_events.start()
        self.addCleanup(self.no_events.stop)

    def native(self, keymap):
        return self.linux.Native(self.hyprland.Hyprland(run=keymap))

    def keys(self, keymap):
        return sorted((b['modmask'], b['key']) for b in keymap.ours())

    def test_all_five_keys_while_it_runs_and_none_after(self):
        desktop = self.Keymap().entry('SUPER + SHIFT + H', 'TurboHUD move mode')  # the player's own
        keymap = self.Keymap([desktop])
        native = self.native(keymap)
        self.assertTrue(native.register_hotkeys(lambda number: None))
        self.assertEqual(native.lock_keys, ['Ctrl+Shift+L'])
        self.assertEqual(self.keys(keymap), [(5, '1'), (5, '2'), (5, '3'), (5, 'L'), (5, 'Q')])
        commands = {b['key']: b['arg'] for b in keymap.ours()}
        self.assertTrue(commands['L'].endswith('--toggle'))
        self.assertTrue(commands['2'].endswith('--preset 2'))
        self.assertIn('launch_turbohud.py', commands['Q'])  # from the source folder
        native.unregister_hotkeys()
        self.assertEqual(keymap.ours(), [])
        self.assertEqual(keymap.binds, [desktop])

    def test_keys_the_desktop_uses_stay_its_own(self):
        keymap = self.Keymap()
        taken = [
            keymap.entry('CTRL + SHIFT + L', 'Lock screen'),
            keymap.entry('CTRL + SHIFT + 3', 'Screenshot'),
        ]
        keymap.binds = list(taken)
        native = self.native(keymap)
        self.assertTrue(native.register_hotkeys(lambda number: None))
        self.assertEqual(native.lock_keys, ['Ctrl+Shift+F12'])  # the second key, as on Windows
        self.assertEqual(self.keys(keymap), [(5, '1'), (5, '2'), (5, 'F12'), (5, 'Q')])
        native.unregister_hotkeys()
        self.assertEqual(keymap.binds, taken)

    def test_without_move_mode_and_quit_no_shortcuts(self):
        keymap = self.Keymap()
        keymap.binds = [keymap.entry('CTRL + SHIFT + Q', 'Quit app')]
        self.assertFalse(self.native(keymap).register_hotkeys(lambda number: None))

    def test_keys_left_by_a_turbohud_that_did_not_quit_are_taken_over(self):
        keymap = self.Keymap()
        keymap.binds = [
            keymap.entry('CTRL + SHIFT + L', 'TurboHUD shortcut: move mode', '/old/TurboHUD --toggle')
        ]
        native = self.native(keymap)
        native.register_hotkeys(lambda number: None)
        own = [b for b in keymap.ours() if b['key'] == 'L']
        self.assertEqual(len(own), 1)
        self.assertNotIn('/old/', own[0]['arg'])

    def test_after_a_config_reload_the_keys_come_back(self):
        keymap = self.Keymap()
        native = self.native(keymap)
        native.register_hotkeys(lambda number: None)
        keymap.binds = []  # what a reload does to them
        native._rebind()
        self.assertEqual(len(keymap.ours()), 5)

    def test_a_reload_event_starts_it(self):
        native = self.native(self.Keymap())
        native.events = mock.Mock()
        native.event_text = ''
        native.events.readAll.side_effect = [b'activewindow>>foot,x\nconfigrel', b'oaded>>\n']
        with mock.patch.object(self.linux.QTimer, 'singleShot') as later:
            native._read_events()
            later.assert_not_called()
            native._read_events()
        later.assert_called_once_with(self.linux.REBIND_MS, native._rebind)

    def test_without_hyprland_none(self):
        native = self.linux.Native(None)
        self.assertFalse(native.register_hotkeys(lambda number: None))
        native.unregister_hotkeys()

    def test_the_command_line_it_binds(self):
        own = self.linux.own_command
        self.assertEqual(own(['--quit'], frozen=True, executable='/x/TurboHUD'), ['/x/TurboHUD', '--quit'])
        self.assertEqual(
            own(['--toggle'], frozen=False, executable='/v/python', source='/s/launch_turbohud.py'),
            ['/v/python', '-B', '/s/launch_turbohud.py', '--toggle'],
        )
