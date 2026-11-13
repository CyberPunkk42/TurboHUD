import os
import socket
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud import app, control
from turbohud.core import hud, presets, settings
from turbohud.overlay import choose_platform


class UpgradeLayoutTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / settings.SETTINGS_FILE

    @staticmethod
    def ink(_text, size):
        return size * 0.7, 0

    def saved(self, **fields):
        place = settings.SectionPlace(100, 200, 300, 155, visible=False, group='A')
        return settings.Settings(sections={'localtime': place}, **fields)

    def test_old_sizes_are_converted_once_and_the_old_file_is_kept(self):
        settings.save_settings(self.path, self.saved())
        old = self.path.read_bytes()
        upgraded = app.upgrade_layout(settings.load_settings(self.path), self.path, self.ink)
        place = upgraded.sections['localtime']
        self.assertEqual(place.height, 50)
        self.assertEqual((place.visible, place.group), (False, 'A'))
        self.assertEqual(settings.load_settings(self.path), upgraded)
        backup = f'settings.before-layout-{settings.LAYOUT_VERSION}.json'
        self.assertEqual(self.path.with_name(backup).read_bytes(), old)
        # A second start finds them converted.
        self.assertEqual(app.upgrade_layout(upgraded, self.path, self.ink), upgraded)

    def lap_times(self, layout_version, height):
        place = settings.SectionPlace(100, 200, 500, height)
        return settings.Settings(
            sections={'laptimes': place}, presets={2: {'laptimes': place}}, layout_version=layout_version
        )

    def test_a_tight_lap_times_box_grows_by_its_new_rows_also_in_a_preset(self):
        settings.save_settings(self.path, self.lap_times(2, 300))
        upgraded = app.upgrade_layout(settings.load_settings(self.path), self.path, self.ink)
        place = upgraded.sections['laptimes']
        self.assertEqual((place.x, place.y, place.width), (100, 200, 500))
        # The 4 more rows of 21 px on a box that fits 16 rows and a heading, 351 px at scale 1.
        self.assertEqual(place.height, round(300 * (351 + 84) / 351))
        self.assertEqual(upgraded.presets[2]['laptimes'], place)
        self.assertEqual(settings.load_settings(self.path).layout_version, settings.LAYOUT_VERSION)

    def test_a_section_from_before_tight_boxes_goes_through_both_steps(self):
        old_normal = 14 + 13 + 16 * (13 + 8) + 14 + 14  # the 16 rows and the room for its name
        settings.save_settings(self.path, self.lap_times(1, old_normal * 2))
        upgraded = app.upgrade_layout(settings.load_settings(self.path), self.path, self.ink)
        section = next(s for s in hud.RACE_SECTIONS if s.name == 'laptimes')
        self.assertEqual(upgraded.sections['laptimes'].height, 2 * hud.tight_height(section, 1.0, self.ink))

    def test_other_sections_keep_their_size_in_layout_3(self):
        place = settings.SectionPlace(1, 2, 300, 40)
        current = settings.Settings(sections={'localtime': place}, layout_version=2)
        settings.save_settings(self.path, current)
        upgraded = app.upgrade_layout(settings.load_settings(self.path), self.path, self.ink)
        self.assertEqual(upgraded.sections['localtime'], place)

    def test_a_lap_times_box_from_layout_3_keeps_its_size(self):
        settings.save_settings(self.path, self.lap_times(3, 300))
        upgraded = app.upgrade_layout(settings.load_settings(self.path), self.path, self.ink)
        self.assertEqual(upgraded.sections['laptimes'].height, 300)

    def test_the_track_map_gets_its_dark_square_once_also_in_a_preset(self):
        place = settings.SectionPlace(10, 20, 240, 240, tint=False)  # saved when its tint meant nothing
        old = settings.Settings(
            sections={'trackmap': place}, presets={1: {'trackmap': place}}, layout_version=3
        )
        settings.save_settings(self.path, old)
        upgraded = app.upgrade_layout(settings.load_settings(self.path), self.path, self.ink)
        self.assertTrue(upgraded.sections['trackmap'].tint)
        self.assertTrue(upgraded.presets[1]['trackmap'].tint)
        self.assertEqual(upgraded.sections['trackmap'], replace(place, tint=True))
        # Turned off afterwards, it stays off.
        off = replace(upgraded, sections={'trackmap': place})
        self.assertFalse(app.upgrade_layout(off, self.path, self.ink).sections['trackmap'].tint)

    def test_the_last_and_best_lap_grows_by_its_sector_bars_once(self):
        place = settings.SectionPlace(100, 200, 400, 50)
        old = settings.Settings(sections={'times': place}, presets={3: {'times': place}}, layout_version=4)
        settings.save_settings(self.path, old)
        upgraded = app.upgrade_layout(settings.load_settings(self.path), self.path, self.ink)
        times = next(s for s in hud.RACE_SECTIONS if s.name == 'times')
        grown = hud.sector_bar_place(times, (100, 200, 400, 50), 1.0, self.ink)
        self.assertGreater(grown[3], 50)
        self.assertEqual((upgraded.sections['times'].x, upgraded.sections['times'].height), (100, grown[3]))
        self.assertEqual(upgraded.presets[3]['times'], upgraded.sections['times'])
        self.assertEqual(app.upgrade_layout(upgraded, self.path, self.ink), upgraded)

    def test_converted_sizes_stay(self):
        current = self.saved(layout_version=settings.LAYOUT_VERSION)
        self.assertEqual(app.upgrade_layout(current, self.path, self.ink), current)
        self.assertFalse(self.path.exists())

    def test_a_first_start_has_nothing_to_convert(self):
        upgraded = app.upgrade_layout(settings.Settings(), self.path, self.ink)
        self.assertEqual(upgraded.layout_version, settings.LAYOUT_VERSION)
        self.assertFalse(self.path.exists())

    def test_a_section_it_does_not_know_stays_as_it_was(self):
        place = settings.SectionPlace(1, 2, 300, 155)
        settings.save_settings(self.path, settings.Settings(sections={'unknown': place}))
        upgraded = app.upgrade_layout(settings.load_settings(self.path), self.path, self.ink)
        self.assertEqual(upgraded.sections['unknown'], place)

    def test_text_sizes_come_from_the_boxes_the_common_one_global(self):
        # Asked for by the user on 2026-11-13: a global text size, a section's own where it differs.
        sections = {s.name: s for s in hud.RACE_SECTIONS}

        def box_for(name, font):
            return hud.text_box(sections[name], (0, 0, 0, 0), font, self.measure, self.ink)

        def place(name, font):
            x, y, width, height = box_for(name, font)
            return settings.SectionPlace(x, y, width, height)

        old = settings.Settings(
            sections={
                'lap': place('lap', 16),
                'players': place('players', 16),
                'laptimes': place('laptimes', 20),
                'trackmap': settings.SectionPlace(5, 5, 240, 240, tint=True),
            },
            presets={1: {'players': place('players', 26)}},
            layout_version=5,
        )
        settings.save_settings(self.path, old)
        upgraded = app.upgrade_layout(old, self.path, self.ink, self.measure)
        self.assertEqual(upgraded.font_size, 16)  # what most have
        fonts = {name: p.font for name, p in upgraded.sections.items()}
        self.assertEqual(fonts, {'lap': None, 'players': None, 'laptimes': 20, 'trackmap': None})
        self.assertEqual(upgraded.presets[1]['players'].font, 26)
        self.assertEqual(settings.load_settings(self.path), upgraded)  # kept in the file

    @staticmethod
    def measure(text, size):
        return len(text) * size * 0.6

    def test_a_file_that_cannot_be_written_still_gives_the_converted_sizes(self):
        missing = self.path.parent / 'none' / settings.SETTINGS_FILE
        with self.assertLogs('turbohud', level='WARNING'):
            upgraded = app.upgrade_layout(self.saved(), missing, self.ink)
        self.assertEqual(upgraded.sections['localtime'].height, 50)


class FakeTurboHUD:
    """A socket that answers like a running TurboHUD and notes the commands."""

    def __init__(self, path, answer='ok'):
        self.path, self.answer, self.got = path, answer, []
        control.prepare_folder(path)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(path))
        self.server.listen(4)
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with conn:
                self.got.append(conn.recv(256).decode().strip())
                conn.sendall(self.answer.encode() + b'\n')

    def close(self):
        self.server.close()


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = control.control_path({'XDG_RUNTIME_DIR': self.folder}, 'linux')

    def test_path_in_the_private_runtime_folder(self):
        self.assertEqual(self.path, Path(self.folder) / 'turbohud' / 'control.sock')
        self.assertEqual(
            control.control_path({}, 'linux', uid=1000), Path('/tmp/turbohud-1000/turbohud/control.sock')
        )
        self.assertIsNone(control.control_path({}, 'win32'))

    def test_send_reaches_the_running_turbohud(self):
        fake = FakeTurboHUD(self.path)
        try:
            self.assertEqual(control.send('toggle', self.path), 'ok')
            self.assertEqual(fake.got, ['toggle'])
            self.assertEqual(os.stat(self.path.parent).st_mode & 0o777, 0o700)
        finally:
            fake.close()

    def test_nothing_running(self):
        self.assertIsNone(control.send('quit', self.path))
        control.prepare_folder(self.path)
        self.path.write_text('')  # left behind, nobody listening
        self.assertIsNone(control.send('quit', self.path))
        with self.assertRaises(ValueError):
            control.send('format the disk', self.path)


class CommandLineTests(unittest.TestCase):
    def test_commands_go_to_the_running_turbohud(self):
        sent = []

        def send(command):
            sent.append(command)
            return 'ok'

        self.assertEqual(app.tell_running(app.parse_args(['--toggle']), send), 0)
        self.assertEqual(app.tell_running(app.parse_args(['--quit']), send), 0)
        self.assertEqual(sent, ['toggle', 'quit'])

    def test_a_second_start_switches_the_running_one_to_move_mode(self):
        sent = []

        def send(command):
            sent.append(command)
            return 'ok'

        self.assertEqual(app.tell_running(app.parse_args([]), send), 0)
        self.assertEqual(sent, ['ping', 'move'])

    def test_with_none_running_a_start_starts_and_a_command_fails(self):
        def send(command):
            return None

        self.assertIsNone(app.tell_running(app.parse_args([]), send))
        self.assertIsNone(app.tell_running(app.parse_args(['--move']), send))
        self.assertEqual(app.tell_running(app.parse_args(['--toggle']), send), 1)

    def test_one_command_at_a_time(self):
        with self.assertRaises(SystemExit):
            app.parse_args(['--toggle', '--quit'])
        with self.assertRaises(SystemExit):
            app.parse_args(['--toggle', '--preset', '1'])

    def test_a_preset_goes_to_the_running_turbohud(self):
        sent = []

        def send(command):
            sent.append(command)
            return 'ok'

        self.assertEqual(app.tell_running(app.parse_args(['--preset', '2']), send), 0)
        self.assertEqual(sent, ['preset2'])

    def test_only_presets_that_exist(self):
        with self.assertRaises(SystemExit):
            app.parse_args(['--preset', '4'])
        self.assertTrue(set(control.COMMANDS) >= {f'preset{n}' for n in settings.PRESETS})

    def test_an_empty_preset_is_reported(self):
        self.assertEqual(
            app.tell_running(app.parse_args(['--preset', '1']), lambda _: 'preset 1 is empty: save it first'),
            1,
        )


class PlatformTests(unittest.TestCase):
    def test_xwayland_on_wayland_desktops_other_than_hyprland(self):
        kde = {'WAYLAND_DISPLAY': 'wayland-0', 'DISPLAY': ':0', 'XDG_SESSION_TYPE': 'wayland'}
        self.assertEqual(choose_platform(kde, 'linux'), 'xcb')

    def test_left_alone_otherwise(self):
        hyprland = {'WAYLAND_DISPLAY': 'wayland-1', 'DISPLAY': ':1', 'HYPRLAND_INSTANCE_SIGNATURE': 'x'}
        self.assertIsNone(choose_platform(hyprland, 'linux'))
        self.assertIsNone(choose_platform({'DISPLAY': ':0'}, 'linux'))  # X11 session
        self.assertIsNone(
            choose_platform({'WAYLAND_DISPLAY': 'w', 'DISPLAY': ':0', 'QT_QPA_PLATFORM': 'wayland'}, 'linux')
        )
        self.assertIsNone(
            choose_platform(
                {'WAYLAND_DISPLAY': 'w', 'DISPLAY': ':0', 'TURBOHUD_PLATFORM': 'wayland'}, 'linux'
            )
        )
        self.assertIsNone(choose_platform({'WAYLAND_DISPLAY': 'w'}, 'linux'))  # no XWayland
        self.assertIsNone(choose_platform({'WAYLAND_DISPLAY': 'w', 'DISPLAY': ':0'}, 'darwin'))


class HelpTests(unittest.TestCase):
    def test_the_panel_says_how_to_switch_without_shortcuts(self):
        self.assertIn('--toggle', ' '.join(hud.help_lines(shortcuts=False, commands=True)))
        self.assertNotIn('--toggle', ' '.join(hud.help_lines(shortcuts=True, commands=True)))


class FirstStartLayoutTests(unittest.TestCase):
    """A first start gets the shipped layout for its screen (asked for by the user on 2026-11-13)."""

    @staticmethod
    def measure(text, size):
        return len(text) * size * 0.6

    @staticmethod
    def ink(_text, size):
        return size * 0.7, size * 0.2

    def layout(self, screen):
        return app.first_start_layout(settings.Settings(), screen, hud.RACE_SECTIONS, self.measure, self.ink)

    def test_every_section_placed_on_the_screen(self):
        for screen in ((0, 0, 1920, 1080), (0, 0, 5120, 1440), (1920, 0, 2560, 1440), (0, 0, 1366, 768)):
            with self.subTest(screen=screen):
                result = self.layout(screen)
                self.assertEqual(set(result.sections), {s.name for s in hud.RACE_SECTIONS})
                for name, place in result.sections.items():
                    inside = screen[0] <= place.x and place.x + place.width <= screen[0] + screen[2]
                    self.assertTrue(inside and screen[1] <= place.y <= screen[1] + screen[3], name)

    def test_the_common_text_size_is_the_global_one(self):
        result = self.layout((0, 0, 5120, 1440))
        fonts = [p.font for p in result.sections.values()]
        self.assertIn(None, fonts)  # those with the common size follow the global one
        self.assertNotIn(result.font_size, fonts)

    def test_without_shipped_layouts_nothing_changes(self):
        empty = Path(tempfile.mkdtemp())
        before = settings.Settings()
        after = app.first_start_layout(
            before, (0, 0, 1920, 1080), hud.RACE_SECTIONS, self.measure, self.ink, empty
        )
        self.assertEqual(after, before)


class StartLayoutTests(unittest.TestCase):
    """A layout in customization/display_presets for the screen's size is taken at a start, once
    each time it is new or changed (asked for by the user on 2026-11-13)."""

    measure = staticmethod(FirstStartLayoutTests.measure)
    ink = staticmethod(FirstStartLayoutTests.ink)
    screen = (0, 0, 1920, 1080)

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.own = {s.name: settings.SectionPlace(100, 200, 300, 40) for s in hud.RACE_SECTIONS}

    def start(self, before):
        return app.start_layout(before, self.screen, hud.RACE_SECTIONS, self.measure, self.ink, self.folder)

    def test_own_layout_taken_once(self):
        presets.save_file(self.folder / '1920x1080.json', self.own, (1920, 1080), 13)
        first = self.start(settings.Settings())
        self.assertEqual(first.sections['speed'].x, 100)
        self.assertTrue(first.applied_preset)
        moved = replace(first, sections={**first.sections, 'speed': replace(first.sections['speed'], x=5)})
        self.assertEqual(self.start(moved), moved)  # moving sections afterwards sticks

    def test_changed_file_taken_again(self):
        presets.save_file(self.folder / '1920x1080.json', self.own, (1920, 1080), 13)
        first = self.start(settings.Settings())
        changed = {**self.own, 'speed': settings.SectionPlace(600, 200, 300, 40)}
        presets.save_file(self.folder / '1920x1080.json', changed, (1920, 1080), 13)
        self.assertEqual(self.start(first).sections['speed'].x, 600)

    def test_other_size_not_taken(self):
        presets.save_file(self.folder / '2560x1440.json', self.own, (2560, 1440), 13)
        shipped = app.first_start_layout(
            settings.Settings(), self.screen, hud.RACE_SECTIONS, self.measure, self.ink
        )
        self.assertEqual(self.start(settings.Settings()), shipped)

    def test_placed_sections_kept_without_own_layout(self):
        placed = replace(settings.Settings(), sections={'speed': settings.SectionPlace(1, 2, 3, 4)})
        self.assertEqual(self.start(placed), placed)
