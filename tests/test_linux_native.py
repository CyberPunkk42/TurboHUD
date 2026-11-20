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

    def windowTitle(self):
        return 'TurboHUD - Test'


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

    def test_focus_back_only_from_the_window_that_just_took_it(self):
        hypr = FakeHypr()
        native = self.native(hypr)
        native.prepare_app()
        native.addresses.update({1: '0xsettings', 2: '0xlabel'})
        hypr.active = '0xsettings'  # the player clicks in the settings
        native.give_focus_back(only_from='0xlabel')
        self.assertEqual(hypr.focused, [])
        hypr.active = '0xlabel'  # the label took it as it opened
        native.give_focus_back(only_from='0xlabel')
        self.assertEqual(hypr.focused, ['0xgame'])

    def test_a_window_that_takes_clicks_keeps_the_focus_once_placed(self):
        # Focusing the game moved the mouse to the game's screen (reported by the user on 2026-11-20).
        hypr = FakeHypr()
        hypr.own_window = lambda pid, title: '0xsettings'
        hypr.set_focusable = lambda address, focusable: True
        native = self.native(hypr)
        native.prepare_app()
        hypr.active = '0xsettings'
        widget = FakeWidget()
        widget.focusable = True
        native._place(widget, (10, 20, 300, 200), 1)
        self.assertEqual(hypr.placed[0], '0xsettings')
        self.assertEqual(hypr.focused, [])
        section = FakeWidget()  # takes no focus: it is given back, as before
        hypr.own_window = lambda pid, title: '0xsection'
        hypr.active = '0xsection'
        native._place(section, (10, 20, 300, 200), 1)
        self.assertEqual(hypr.focused, ['0xgame'])

    def test_a_window_that_takes_clicks_opens_with_a_fixed_size_for_a_moment(self):
        # Hyprland floats a window of a fixed size as it opens: no large tiled window first.
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QWidget

        from turbohud.overlay.linux import FloatAtOpen

        float_at_open = FloatAtOpen()
        settings, section = QWidget(), QWidget()
        settings.focusable = True
        for widget in (settings, section):
            self.addCleanup(widget.close)
            widget.setMinimumSize(50, 40)
            widget.resize(300, 200)
            float_at_open.eventFilter(widget, QEvent(QEvent.Show))
        self.assertEqual(settings.minimumSize().toTuple(), (300, 200))
        self.assertEqual(settings.maximumSize().toTuple(), (300, 200))
        self.assertEqual(section.minimumSize().toTuple(), (50, 40))  # a section is left alone
        float_at_open.release(id(settings))
        self.assertEqual(settings.minimumSize().toTuple(), (50, 40))
        self.assertGreater(settings.maximumSize().width(), 10000)

    def test_the_panel_is_placed_first_and_brought_in_front_again(self):
        # Move mode opens some 50 windows: the panel, opened last, came 2 s after the key (2026-11-20).
        hypr = FakeHypr()
        order, fronts = [], []
        hypr.own_window = lambda pid, title: '0x' + title
        hypr.place = lambda address, *place, focusable=False: order.append(address) or True
        hypr.to_front = lambda address: fronts.append(address) or True
        native = self.native(hypr)

        class Window(FakeWidget):
            def __init__(self, title, **kind):
                self.title = title
                self.__dict__.update(kind)

            def windowTitle(self):
                return self.title

            def x(self):
                return 0

            y = x

            def width(self):
                return 10

            height = width

        windows = [
            Window('grid'),
            Window('label', float_at_open=True),
            Window('fuel'),
            Window('panel', focusable=True),
        ]
        for window in windows:
            native.raise_window(window)
        while native.waiting:
            native._place_next()
        self.assertEqual(order, ['0xpanel', '0xgrid', '0xfuel', '0xlabel'])
        self.assertEqual(fronts, ['0xpanel'])  # above the sections placed after it

    def test_a_window_raised_twice_while_waiting_is_placed_once(self):
        hypr = FakeHypr()
        order = []
        hypr.own_window = lambda pid, title: '0xaaa'
        hypr.place = lambda address, *place, focusable=False: order.append(place) or True
        native = self.native(hypr)
        widget = mock.Mock(focusable=False, float_at_open=False, locked=True)
        widget.x.return_value, widget.y.return_value = 0, 0
        widget.width.return_value = widget.height.return_value = 10
        native.raise_window(widget)
        widget.x.return_value = 50
        native.raise_window(widget)
        while native.waiting:
            native._place_next()
        self.assertEqual(order, [(50, 0, 10, 10)])  # where it was raised last

    def test_hyprland_keeps_the_place_labels_open(self):
        self.assertTrue(self.native(FakeHypr()).keeps_labels_open)
        self.assertFalse(self.native(None).keeps_labels_open)

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

    def test_move_mode_focuses_nothing_on_its_own(self):
        # Hyprland would move the mouse onto a window it focuses.
        hypr = FakeHypr()
        native = self.native(hypr)
        native.prepare_app()
        native.take_focus()
        self.assertEqual(native.activate(FakeWidget()), 'left to the desktop')
        self.assertEqual(hypr.focused, [])


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

    def test_all_seven_keys_while_it_runs_and_none_after(self):
        desktop = self.Keymap().entry('SUPER + SHIFT + H', 'TurboHUD move mode')  # the player's own
        keymap = self.Keymap([desktop])
        native = self.native(keymap)
        self.assertTrue(native.register_hotkeys(lambda number: None))
        self.assertEqual(native.lock_keys, ['Ctrl+Shift+L'])
        self.assertEqual(
            self.keys(keymap), [(5, '1'), (5, '2'), (5, '3'), (5, '4'), (5, '5'), (5, 'L'), (5, 'Q')]
        )
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
        self.assertEqual(self.keys(keymap), [(5, '1'), (5, '2'), (5, '4'), (5, '5'), (5, 'F12'), (5, 'Q')])
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
        self.assertEqual(len(keymap.ours()), 7)

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
