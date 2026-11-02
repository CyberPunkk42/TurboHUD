import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.overlay import hyprland

CLIENTS = [
    {
        'address': '0xaaa',
        'pid': 10,
        'title': 'TurboHUD',
        'mapped': True,
        'floating': True,
        'at': [40, 50],
        'size': [420, 194],
    },
    {
        'address': '0xddd',
        'pid': 10,
        'title': 'tiled',
        'mapped': True,
        'floating': False,
        'at': [0, 0],
        'size': [5096, 1390],
    },
    {'address': '0xbbb', 'pid': 99, 'title': 'TurboHUD', 'mapped': True, 'at': [0, 0], 'size': [10, 10]},
    {'address': '0xccc', 'pid': 10, 'title': 'other', 'mapped': True, 'at': [0, 0], 'size': [10, 10]},
]


# The user's layout: a second monitor above and to the right of the main one.
MONITORS = [
    {'x': 1280, 'y': -1440, 'width': 2560, 'height': 1440, 'scale': 1, 'activeWorkspace': {'id': 2}},
    {'x': 0, 'y': 0, 'width': 5120, 'height': 1440, 'scale': 1, 'activeWorkspace': {'id': 1}},
]


class FakeHyprctl:
    """Answers like hyprctl; `lua` says whether this Hyprland takes Lua commands."""

    def __init__(self, lua=True):
        self.lua = lua
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if args == ['-j', 'clients']:
            return json.dumps(CLIENTS)
        if args == ['-j', 'monitors']:
            return json.dumps(MONITORS)
        if args == ['-j', 'activewindow']:
            return json.dumps({'address': '0xgame'})
        if args[0] == 'dispatch':
            is_lua = args[1].startswith('hl.')
            return 'ok' if is_lua == self.lua else 'error: invalid dispatcher'
        raise AssertionError(args)

    def dispatched(self):
        return [args[1] for args in self.calls if args[0] == 'dispatch']


class AvailableTests(unittest.TestCase):
    def test_needs_hyprland_and_hyprctl(self):
        def found(_name):
            return '/usr/bin/hyprctl'

        self.assertTrue(hyprland.available({'HYPRLAND_INSTANCE_SIGNATURE': 'x'}, found))
        self.assertFalse(hyprland.available({}, found))
        self.assertFalse(hyprland.available({'HYPRLAND_INSTANCE_SIGNATURE': 'x'}, lambda _name: None))


class CommandTests(unittest.TestCase):
    def test_every_command_names_only_turbohuds_window(self):
        for lua, classic in hyprland.place_commands('address:0xaaa', 1, 2, 3, 4) + [
            hyprland.focus_command('address:0xaaa')
        ]:
            with self.subTest(lua=lua):
                self.assertIn("window = 'address:0xaaa'", lua)
                if classic is not None:
                    self.assertIn('address:0xaaa', classic)

    def test_fullscreen_is_ended_for_this_window_only_and_never_with_classic_commands(self):
        commands = hyprland.place_commands('address:0xaaa', 1, 2, 3, 4)
        lua, classic = commands[0]
        self.assertIn("fullscreen({ action = 'unset', window = 'address:0xaaa' })", lua)
        self.assertIsNone(classic)  # classic fullscreen commands act on the active window
        fake = FakeHyprctl(lua=False)
        hyprland.Hyprland(fake).place('0xaaa', 1, 2, 3, 4)
        self.assertFalse(
            any('fullscreen' in text and not text.startswith('hl.') for text in fake.dispatched())
        )

    def test_place_floats_sizes_moves_pins_and_keeps_focus_away(self):
        lua = ' '.join(command for command, _ in hyprland.place_commands('address:0xaaa', 40, 50, 420, 194))
        for part in (
            'float(',
            'x = 420, y = 194',
            'x = 40, y = 50',
            'pin(',
            "prop = 'no_focus', value = '1'",
        ):
            self.assertIn(part, lua)


class HyprlandTests(unittest.TestCase):
    def test_finds_its_own_window_by_pid_and_title(self):
        self.assertEqual(hyprland.Hyprland(FakeHyprctl()).own_window(10, 'TurboHUD'), '0xaaa')
        self.assertIsNone(hyprland.Hyprland(FakeHyprctl()).own_window(11, 'TurboHUD'))

    def test_geometry_and_active_window(self):
        hypr = hyprland.Hyprland(FakeHyprctl())
        self.assertEqual(hypr.geometry('0xaaa'), (40, 50, 420, 194))
        self.assertIsNone(hypr.geometry('0xdead'))
        self.assertIsNone(hypr.geometry('0xddd'))  # tiled: the layout's size, not TurboHUD's
        self.assertEqual(hypr.active_window(), '0xgame')

    def test_the_window_goes_to_the_monitor_of_its_place_first(self):
        # It opens where the focus is (here the upper monitor); a pinned window shows only
        # on its own monitor, so it must move to the main one before it is placed there.
        fake = FakeHyprctl()
        hyprland.Hyprland(fake).place('0xaaa', 40, 40, 420, 194)
        sent = fake.dispatched()
        to_workspace = next(i for i, text in enumerate(sent) if 'workspace = 1, follow = false' in text)
        self.assertLess(to_workspace, next(i for i, text in enumerate(sent) if 'x = 40, y = 40' in text))

    def test_workspace_at(self):
        hypr = hyprland.Hyprland(FakeHyprctl())
        self.assertEqual(hypr.workspace_at(40, 40), 1)
        self.assertEqual(hypr.workspace_at(2000, -500), 2)
        self.assertIsNone(hypr.workspace_at(-100, 5000))

    def test_lua_commands_on_new_hyprland(self):
        fake = FakeHyprctl(lua=True)
        self.assertTrue(hyprland.Hyprland(fake).place('0xaaa', 40, 50, 420, 194))
        self.assertTrue(all(text.startswith('hl.') for text in fake.dispatched()))

    def test_classic_commands_on_older_hyprland(self):
        fake = FakeHyprctl(lua=False)
        hypr = hyprland.Hyprland(fake)
        self.assertTrue(hypr.place('0xaaa', 40, 50, 420, 194))
        self.assertTrue(hypr.focus('0xgame'))
        self.assertIn('pin address:0xaaa', fake.dispatched())
        self.assertIn('focuswindow address:0xgame', fake.dispatched())

    def test_move_mode_lets_the_mouse_in(self):
        fake = FakeHyprctl()
        hypr = hyprland.Hyprland(fake)
        hypr.set_focusable('0xaaa', True)
        hypr.set_focusable('0xaaa', False)
        self.assertIn("prop = 'no_focus', value = '0', window = 'address:0xaaa'", fake.dispatched()[0])
        self.assertIn("value = '1'", fake.dispatched()[1])

    def test_a_missing_hyprctl_is_not_an_error(self):
        def broken(_args):
            raise subprocess.TimeoutExpired('hyprctl', 2)

        hypr = hyprland.Hyprland(broken)
        self.assertFalse(hypr.place('0xaaa', 0, 0, 1, 1))
        self.assertIsNone(hypr.own_window(1, 'TurboHUD'))
        self.assertIsNone(hypr.active_window())


if __name__ == '__main__':
    unittest.main()


class GroupMoveTests(unittest.TestCase):
    def test_all_places_in_one_request_floating_only(self):
        fake = FakeHyprctl()
        found = hyprland.Hyprland(fake).geometries({'0xaaa', '0xddd'})
        self.assertEqual(found, {'0xaaa': (40, 50, 420, 194)})  # 0xddd is tiled
        self.assertEqual(fake.calls, [['-j', 'clients']])

    def test_move_is_a_single_request_for_that_window(self):
        fake = FakeHyprctl(lua=False)
        self.assertTrue(hyprland.Hyprland(fake).move('0xaaa', 70, 80))
        self.assertEqual(fake.dispatched()[-1], 'movewindowpixel exact 70 80,address:0xaaa')
