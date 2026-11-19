import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import settings as s


class SettingsDirTests(unittest.TestCase):
    home = Path('/home/racer')

    def test_windows_uses_appdata(self):
        folder = s.settings_dir('win32', {'APPDATA': r'C:\Users\x\AppData\Roaming'}, self.home)
        self.assertEqual(folder, Path(r'C:\Users\x\AppData\Roaming') / 'TurboHUD')

    def test_windows_without_appdata(self):
        self.assertEqual(
            s.settings_dir('win32', {}, self.home), self.home / 'AppData' / 'Roaming' / 'TurboHUD'
        )

    def test_mac(self):
        folder = s.settings_dir('darwin', {}, self.home)
        self.assertEqual(folder, self.home / 'Library' / 'Application Support' / 'TurboHUD')

    def test_linux_follows_xdg(self):
        self.assertEqual(s.settings_dir('linux', {}, self.home), self.home / '.config' / 'TurboHUD')
        folder = s.settings_dir('linux', {'XDG_CONFIG_HOME': '/cfg'}, self.home)
        self.assertEqual(folder, Path('/cfg') / 'TurboHUD')


class LoadSaveTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'sub' / 'settings.json'

    def tearDown(self):
        self.folder.cleanup()

    def test_round_trip(self):
        theme = s.Theme(text_color='#eeeeee', accent_color='#00ff00', outline_color='#10203040', scale=1.5)
        settings = s.Settings(placement=(300, 12, 700, 250), theme=theme)
        s.save_settings(self.path, settings)
        self.assertEqual(s.load_settings(self.path), settings)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])  # no temporary file left

    def test_missing_or_broken_file_gives_defaults(self):
        self.assertEqual(s.load_settings(self.path), s.Settings())
        self.path.parent.mkdir(parents=True)
        for content in ('not json', '[1, 2]', '{}', '{"placement": 5, "theme": "red"}'):
            with self.subTest(content=content):
                self.path.write_text(content, encoding='utf-8')
                self.assertEqual(s.load_settings(self.path), s.Settings())

    def test_wrong_values_fall_back_one_by_one(self):
        self.path.parent.mkdir(parents=True)
        data = {
            'placement': {'x': 5, 'y': 6, 'width': 10, 'height': 10},
            'theme': {'text_color': 'red', 'accent_color': '#123456', 'scale': 99, 'outline_color': None},
        }
        self.path.write_text(json.dumps(data), encoding='utf-8')
        settings = s.load_settings(self.path)
        self.assertEqual(settings.placement, (5, 6, s.MIN_WIDTH, s.MIN_HEIGHT))
        self.assertEqual(settings.theme.text_color, s.Theme().text_color)
        self.assertEqual(settings.theme.accent_color, '#123456')
        self.assertEqual(settings.theme.outline_color, s.Theme().outline_color)
        self.assertEqual(settings.theme.scale, s.MAX_SCALE)

    def test_scale_must_be_a_number(self):
        self.path.parent.mkdir(parents=True)
        for scale in (True, '2', None):
            with self.subTest(scale=scale):
                self.path.write_text(json.dumps({'theme': {'scale': scale}}), encoding='utf-8')
                self.assertEqual(s.load_settings(self.path).theme.scale, 1.0)


class SectionPlaceTests(unittest.TestCase):
    def test_section_places_and_visibility_are_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            places = {
                'delta': s.SectionPlace(2000, 600, 300, 60),
                'times': s.SectionPlace(10, 20, 250, 40, visible=False),
            }
            s.save_settings(path, s.Settings(sections=places))
            self.assertEqual(s.load_settings(path).sections, places)

    def test_an_old_file_without_sections_still_loads(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text(json.dumps({'placement': {'x': 40, 'y': 40, 'width': 626, 'height': 688}}))
            loaded = s.load_settings(path)
            self.assertEqual(loaded.sections, {})
            self.assertEqual(loaded.placement, (40, 40, 626, 688))

    def test_broken_section_entries_are_left_out(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text(
                json.dumps(
                    {
                        'sections': {
                            'lap': {'x': 1, 'y': 2, 'width': 100, 'height': 30},
                            'delta': {'x': 'left'},
                            'times': 'nonsense',
                            'current': {'x': 1, 'y': 2, 'width': 0, 'height': 0},
                        }
                    }
                )
            )
            self.assertEqual(list(s.load_settings(path).sections), ['lap'])


class SpeedUnitSettingTests(unittest.TestCase):
    def test_kept_and_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            s.save_settings(path, s.Settings(speed_unit='mph'))
            self.assertEqual(s.load_settings(path).speed_unit, 'mph')
            path.write_text(json.dumps({'speed_unit': 'knots'}))
            self.assertEqual(s.load_settings(path).speed_unit, 'kmh')

    def test_backdrop_option_round_trips_and_is_off_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            self.assertFalse(s.load_settings(path).backdrop)
            s.save_settings(path, s.Settings(backdrop=True))
            self.assertTrue(s.load_settings(path).backdrop)
            path.write_text(json.dumps({'backdrop': 'yes'}))
            self.assertFalse(s.load_settings(path).backdrop)

    def test_other_cars_on_the_track_map_round_trip_and_are_off_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            self.assertFalse(s.load_settings(path).map_others)
            s.save_settings(path, s.Settings(map_others=True))
            self.assertTrue(s.load_settings(path).map_others)
            path.write_text(json.dumps({'map_others': 1}))
            self.assertFalse(s.load_settings(path).map_others)
            path.write_text(json.dumps({}))
            self.assertTrue(s.load_settings(path).radar_cone)  # as it was before the option
            s.save_settings(path, s.Settings(radar_cone=False))
            self.assertFalse(s.load_settings(path).radar_cone)
            path.write_text(json.dumps({}))
            self.assertTrue(s.load_settings(path).sector_bars)  # on, as before the option
            s.save_settings(path, s.Settings(sector_bars=False))
            self.assertFalse(s.load_settings(path).sector_bars)
            path.write_text(json.dumps({}))
            self.assertTrue(s.load_settings(path).yellow_flags)  # on, as when they came
            s.save_settings(path, s.Settings(yellow_flags=False))
            self.assertFalse(s.load_settings(path).yellow_flags)
            path.write_text(json.dumps({}))
            self.assertTrue(s.load_settings(path).classes)
            self.assertTrue(s.load_settings(path).clan_tags)  # on, as when they came
            s.save_settings(path, s.Settings(clan_tags=False))
            self.assertFalse(s.load_settings(path).clan_tags)
            path.write_text(json.dumps({}))
            self.assertEqual(s.load_settings(path).class_tags, s.CLASS_TAGS)
            s.save_settings(path, s.Settings(classes=False, class_tags=('GT3', 'LMP')))
            self.assertFalse(s.load_settings(path).classes)
            self.assertEqual(s.load_settings(path).class_tags, ('GT3', 'LMP'))
            path.write_text(json.dumps({'class_tags': [' [gt3] ', 'lmp', 'GT3', 'MUCHTOOLONG', 7]}))
            self.assertEqual(s.load_settings(path).class_tags, ('GT3', 'LMP'))
            path.write_text(json.dumps({'class_tags': []}))
            self.assertEqual(s.load_settings(path).class_tags, s.CLASS_TAGS)


class FitOnScreensTests(unittest.TestCase):
    screens = ((0, 0, 1920, 1080), (1920, 0, 1280, 1024))

    def test_kept_when_on_a_screen(self):
        for placement in ((40, 40, 420, 150), (2000, 900, 420, 150), (-100, 10, 420, 150)):
            with self.subTest(placement=placement):
                self.assertEqual(s.fit_on_screens(placement, self.screens), placement)

    def test_moved_back_when_off_every_screen(self):
        self.assertEqual(s.fit_on_screens((4000, 40, 420, 150), self.screens), (40, 40, 420, 150))
        self.assertEqual(s.fit_on_screens((40, 1500, 420, 150), self.screens), (40, 40, 420, 150))

    def test_kept_when_no_screens_are_known(self):
        self.assertEqual(s.fit_on_screens((4000, 40, 420, 150), []), (4000, 40, 420, 150))


class SectionTintTests(unittest.TestCase):
    def path(self):
        return Path(tempfile.mkdtemp()) / 'settings.json'

    def test_it_round_trips_also_in_a_preset_and_is_off_by_default(self):
        path = self.path()
        place = s.SectionPlace(1, 2, 300, 40, tint=True)
        s.save_settings(path, s.Settings(sections={'lap': place}, presets={1: {'lap': place}}))
        loaded = s.load_settings(path)
        self.assertTrue(loaded.sections['lap'].tint)
        self.assertTrue(loaded.presets[1]['lap'].tint)
        self.assertFalse(s.SectionPlace(1, 2, 300, 40).tint)

    def test_a_file_from_before_takes_the_tint_it_had_for_all(self):
        path = self.path()
        entry = {'x': 1, 'y': 2, 'width': 30, 'height': 40}
        path.write_text(
            json.dumps({'backdrop': True, 'sections': {'lap': entry}, 'presets': {'1': {'lap': entry}}})
        )
        loaded = s.load_settings(path)
        self.assertTrue(loaded.sections['lap'].tint)
        self.assertTrue(loaded.presets[1]['lap'].tint)
        path.write_text(json.dumps({'backdrop': False, 'sections': {'lap': entry}}))
        self.assertFalse(s.load_settings(path).sections['lap'].tint)

    def test_a_section_s_own_choice_counts_over_all(self):
        path = self.path()
        entry = {'x': 1, 'y': 2, 'width': 30, 'height': 40, 'tint': False}
        path.write_text(json.dumps({'backdrop': True, 'sections': {'lap': entry}}))
        self.assertFalse(s.load_settings(path).sections['lap'].tint)


class WarningTimeTests(unittest.TestCase):
    def path(self):
        return Path(tempfile.mkdtemp()) / 'settings.json'

    def test_they_round_trip_and_have_their_old_values_by_default(self):
        path = self.path()
        self.assertEqual((s.Settings().blue_seconds, s.Settings().radar_seconds), (2.0, 0.5))
        s.save_settings(path, s.Settings(blue_seconds=3.0, radar_seconds=0.8))
        loaded = s.load_settings(path)
        self.assertEqual((loaded.blue_seconds, loaded.radar_seconds), (3.0, 0.8))

    def test_wrong_values_give_the_default_or_the_limit(self):
        path = self.path()
        path.write_text(json.dumps({'blue_seconds': 'soon', 'radar_seconds': True}))
        loaded = s.load_settings(path)
        self.assertEqual((loaded.blue_seconds, loaded.radar_seconds), (2.0, 0.5))
        path.write_text(json.dumps({'blue_seconds': 500, 'radar_seconds': 0}))
        loaded = s.load_settings(path)
        self.assertEqual((loaded.blue_seconds, loaded.radar_seconds), (s.BLUE_SECONDS[1], s.RADAR_SECONDS[0]))


class ReadsPerSecondTests(unittest.TestCase):
    def path(self):
        return Path(tempfile.mkdtemp()) / 'settings.json'

    def test_it_round_trips_and_is_10_by_default(self):
        path = self.path()
        self.assertEqual(s.Settings().reads_per_second, 10)  # since 2026-11-15, asked for by the user
        s.save_settings(path, s.Settings(reads_per_second=5))
        self.assertEqual(s.load_settings(path).reads_per_second, 5)

    def test_a_file_from_before_or_a_wrong_value_gives_the_default(self):
        path = self.path()
        for data in ({}, {'reads_per_second': 7}, {'reads_per_second': 'often'}, {'reads_per_second': [5]}):
            path.write_text(json.dumps(data))
            self.assertEqual(s.load_settings(path).reads_per_second, 10)


class TextCentredTests(unittest.TestCase):
    def test_it_round_trips_also_in_a_preset_and_is_off_by_default(self):
        path = Path(tempfile.mkdtemp()) / 'settings.json'
        place = s.SectionPlace(1, 2, 300, 40, text_centred=True)
        s.save_settings(path, s.Settings(sections={'lap': place}, presets={1: {'lap': place}}))
        loaded = s.load_settings(path)
        self.assertTrue(loaded.sections['lap'].text_centred)
        self.assertTrue(loaded.presets[1]['lap'].text_centred)
        self.assertFalse(s.SectionPlace(1, 2, 300, 40).text_centred)

    def test_a_file_from_before_has_it_off(self):
        path = Path(tempfile.mkdtemp()) / 'settings.json'
        path.write_text(json.dumps({'sections': {'lap': {'x': 1, 'y': 2, 'width': 30, 'height': 40}}}))
        self.assertFalse(s.load_settings(path).sections['lap'].text_centred)

    def test_only_true_counts(self):
        path = Path(tempfile.mkdtemp()) / 'settings.json'
        entry = {'x': 1, 'y': 2, 'width': 30, 'height': 40, 'text_centred': 'yes'}
        path.write_text(json.dumps({'sections': {'lap': entry}}))
        self.assertFalse(s.load_settings(path).sections['lap'].text_centred)


class PresetTests(unittest.TestCase):
    PLACE = s.SectionPlace(10, 20, 300, 40, visible=False, group='B')

    def path(self):
        return Path(tempfile.mkdtemp()) / 's.json'

    def test_presets_round_trip_and_start_empty(self):
        path = self.path()
        kept = s.Settings(presets={2: {'lap': self.PLACE}})
        s.save_settings(path, kept)
        self.assertEqual(s.load_settings(path).presets, {2: {'lap': self.PLACE}})
        self.assertEqual(s.Settings().presets, {})

    def test_a_file_from_before_presets_has_none(self):
        path = self.path()
        path.write_text('{"sections": {}}')
        self.assertEqual(s.load_settings(path).presets, {})

    def test_broken_presets_are_left_out(self):
        path = self.path()
        good = {'x': 1, 'y': 2, 'width': 30, 'height': 40}
        path.write_text(
            json.dumps({'presets': {'1': 'broken', '2': {}, '3': {'lap': good}, '9': {'lap': good}}})
        )
        self.assertEqual(list(s.load_settings(path).presets), [3])
        path.write_text('{"presets": []}')
        self.assertEqual(s.load_settings(path).presets, {})

    def test_one_tint_for_each_group_is_on_unless_turned_off(self):
        path = self.path()
        path.write_text('{}')
        with mock.patch.object(s.sys, 'platform', 'darwin'):
            self.assertTrue(s.load_settings(path).group_tint)
            self.assertTrue(s.Settings().group_tint)
        s.save_settings(path, s.Settings(group_tint=False))
        self.assertFalse(s.load_settings(path).group_tint)

    def test_on_windows_one_tint_for_each_group_is_off_until_turned_on(self):
        # A window behind each group there, off until the user has seen it over TSU (2026-11-16).
        path = self.path()
        path.write_text('{}')
        with mock.patch.object(s.sys, 'platform', 'win32'):
            self.assertFalse(s.load_settings(path).group_tint)
            self.assertFalse(s.Settings().group_tint)
            self.assertFalse(s.load_settings(path.with_name('missing.json')).group_tint)
            s.save_settings(path, s.Settings(group_tint=True))
            self.assertTrue(s.load_settings(path).group_tint)  # the player's choice is kept
        self.assertFalse(s.group_tint_default('win32'))
        self.assertTrue(s.group_tint_default('linux'))

    def test_the_move_mode_grid_is_on_unless_turned_off(self):
        # A switch since 2026-11-16 (asked for by the user).
        path = self.path()
        path.write_text('{}')
        self.assertTrue(s.load_settings(path).grid)
        s.save_settings(path, s.Settings(grid=False))
        self.assertFalse(s.load_settings(path).grid)

    def test_nearby_cars_short_list_is_on_unless_turned_off(self):
        path = self.path()
        path.write_text('{}')
        self.assertTrue(s.load_settings(path).nearby_short)
        s.save_settings(path, s.Settings(nearby_short=False))
        self.assertFalse(s.load_settings(path).nearby_short)

    def test_five_presets_since_2026_11_15(self):
        # Asked for by players: five, for recordings, practice, qualifying, racing and the rest.
        path = self.path()
        good = {'x': 1, 'y': 2, 'width': 30, 'height': 40}
        path.write_text(json.dumps({'presets': {str(n): {'lap': good} for n in range(1, 7)}}))
        self.assertEqual(list(s.load_settings(path).presets), [1, 2, 3, 4, 5])

    def test_names_and_presets_by_mode_round_trip_and_start_empty(self):
        path = self.path()
        kept = s.Settings(
            presets={4: {'lap': self.PLACE}},
            preset_names={1: 'Race', 4: 'Recordings'},
            auto_presets={'recording': 4, 'race': 1},
        )
        s.save_settings(path, kept)
        loaded = s.load_settings(path)
        self.assertEqual(loaded.preset_names, {1: 'Race', 4: 'Recordings'})
        self.assertEqual(loaded.auto_presets, {'recording': 4, 'race': 1})
        self.assertEqual((s.Settings().preset_names, s.Settings().auto_presets), ({}, {}))

    def test_a_file_from_before_names_has_none_and_loads_nothing_by_itself(self):
        path = self.path()
        path.write_text('{"presets": {"1": {"lap": {"x": 1, "y": 2, "width": 30, "height": 40}}}}')
        loaded = s.load_settings(path)
        self.assertEqual((loaded.preset_names, loaded.auto_presets), ({}, {}))

    def test_broken_names_and_choices_are_left_out(self):
        path = self.path()
        path.write_text(
            json.dumps(
                {
                    'preset_names': {'1': 7, '2': '   ', '3': '  Quali  \n run ', '6': 'Six', '5': 'x' * 40},
                    'auto_presets': {
                        'race': 6,
                        'special': True,
                        'recording': '2',
                        'sumo': 1,
                        'hotlapping': 3,
                    },
                }
            )
        )
        loaded = s.load_settings(path)
        self.assertEqual(loaded.preset_names, {3: 'Quali run', 5: 'x' * s.PRESET_NAME_MOST})
        self.assertEqual(loaded.auto_presets, {'hotlapping': 3})
        path.write_text('{"preset_names": [], "auto_presets": "race"}')
        loaded = s.load_settings(path)
        self.assertEqual((loaded.preset_names, loaded.auto_presets), ({}, {}))

    def test_a_spectating_preset_is_kept_beside_the_recordings(self):
        path = self.path()
        path.write_text(json.dumps({'auto_presets': {'recording': 1, 'spectating': 5}}))
        self.assertEqual(s.load_settings(path).auto_presets, {'recording': 1, 'spectating': 5})

    def test_a_preset_is_named_by_its_number_and_name(self):
        self.assertEqual(s.preset_label(3, {3: 'Race'}), '3 Race')
        self.assertEqual(s.preset_label(2, {3: 'Race'}), '2')
        self.assertEqual(s.preset_name('  Hot   laps '), 'Hot laps')
        self.assertEqual(s.preset_name(None), '')

    def test_a_preset_keeps_what_shows_and_the_group(self):
        places = s.preset_places({'lap': self.PLACE}, ['lap'], [(0, 0, 1920, 1080)])
        self.assertEqual(places['lap'], self.PLACE)

    def test_a_section_the_preset_does_not_have_stays_out_of_it(self):
        preset = {'lap': self.PLACE, 'clock': self.PLACE}
        self.assertEqual(list(s.preset_places(preset, ['lap', 'speed'], [])), ['lap'])

    def test_a_section_off_every_screen_comes_back_at_its_size(self):
        off = s.SectionPlace(5000, 20, 300, 40)
        place = s.preset_places({'lap': off}, ['lap'], [(0, 0, 1920, 1080)])['lap']
        self.assertEqual((place.x, place.y), s.DEFAULT_PLACEMENT[:2])
        self.assertEqual((place.width, place.height), (300, 40))


class CurrentPresetTests(unittest.TestCase):
    """Which preset the layout is in now, as move mode's panel shows it (asked for 2026-11-19)."""

    SCREENS = ((0, 0, 1920, 1080),)

    def layout(self, x=100, visible=True):
        return {'lap': s.SectionPlace(x, 50, 200, 40, visible), 'fuel': s.SectionPlace(400, 50, 200, 40)}

    def test_the_preset_the_sections_are_in(self):
        presets = {1: self.layout(x=10), 3: self.layout()}
        self.assertEqual(s.current_preset(self.layout(), presets, self.SCREENS), (3, False))

    def test_a_pixel_or_two_off_still_counts(self):
        presets = {3: self.layout()}
        self.assertEqual(s.current_preset(self.layout(x=102), presets, self.SCREENS), (3, False))
        self.assertIsNone(s.current_preset(self.layout(x=103), presets, self.SCREENS))

    def test_an_option_changed_is_another_layout(self):
        presets = {3: self.layout()}
        self.assertIsNone(s.current_preset(self.layout(visible=False), presets, self.SCREENS))

    def test_the_last_loaded_first_where_two_are_the_same(self):
        presets = {2: self.layout(), 4: self.layout()}
        self.assertEqual(s.current_preset(self.layout(), presets, self.SCREENS), (2, False))
        self.assertEqual(s.current_preset(self.layout(), presets, self.SCREENS, last=4), (4, False))

    def test_moved_on_from_the_last_it_is_changed(self):
        presets = {3: self.layout()}
        self.assertEqual(s.current_preset(self.layout(x=500), presets, self.SCREENS, last=3), (3, True))

    def test_a_last_one_deleted_is_none(self):
        self.assertIsNone(s.current_preset(self.layout(), {}, self.SCREENS, last=3))

    def test_a_preset_off_the_screen_counts_where_loading_puts_it(self):
        off = {'lap': s.SectionPlace(5000, 50, 200, 40), 'fuel': s.SectionPlace(400, 50, 200, 40)}
        fitted = s.preset_places(off, off, self.SCREENS)
        self.assertEqual(s.current_preset(fitted, {1: off}, self.SCREENS), (1, False))

    def test_a_section_the_preset_lacks_is_left_alone(self):
        presets = {3: {'lap': self.layout()['lap']}}
        self.assertEqual(s.current_preset(self.layout(), presets, self.SCREENS), (3, False))

    def test_how_the_panel_names_it(self):
        self.assertEqual(s.preset_shown(None, {}), 'Preset: none')
        self.assertEqual(s.preset_shown((3, False), {3: 'Race'}), 'Preset: 3 Race')
        self.assertEqual(s.preset_shown((2, True), {}), 'Preset: 2 (changed)')


class StartPresetTests(unittest.TestCase):
    """The Race preset is the layout TurboHUD starts with (asked for by the user on 2026-11-19)."""

    def settings(self, auto, saved):
        place = {'lap': s.SectionPlace(1, 2, 30, 40)}
        return s.Settings(auto_presets=auto, presets={number: place for number in saved})

    def test_the_preset_chosen_for_a_race(self):
        self.assertEqual(s.start_preset(self.settings({'race': 4, 'recording': 1}, (1, 4))), 4)

    def test_none_without_one_chosen_for_a_race(self):
        self.assertIsNone(s.start_preset(self.settings({'recording': 1}, (1, 4))))

    def test_none_where_it_is_not_saved(self):
        self.assertIsNone(s.start_preset(self.settings({'race': 4}, (1,))))


if __name__ == '__main__':
    unittest.main()


class GroupSettingTests(unittest.TestCase):
    def test_groups_round_trip_and_unknown_ones_are_dropped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            places = {'lap': s.SectionPlace(1, 2, 300, 40, True, 'A'), 'fuel': s.SectionPlace(1, 50, 300, 40)}
            s.save_settings(path, s.Settings(sections=places))
            loaded = s.load_settings(path).sections
            self.assertEqual(loaded['lap'].group, 'A')
            self.assertEqual(loaded['fuel'].group, '')
            data = json.loads(path.read_text())
            data['sections']['lap']['group'] = 'Z'
            path.write_text(json.dumps(data))
            self.assertEqual(s.load_settings(path).sections['lap'].group, '')
            # Seven groups since 2026-11-15 (asked for by players): G kept, H dropped.
            for group, kept in (('G', 'G'), ('H', '')):
                data['sections']['lap']['group'] = group
                path.write_text(json.dumps(data))
                self.assertEqual(s.load_settings(path).sections['lap'].group, kept)


class LineSpacingTests(unittest.TestCase):
    def test_kept_in_the_file_only_where_it_is_not_the_usual(self):
        path = Path(tempfile.mkdtemp()) / s.SETTINGS_FILE
        places = {
            'players': s.SectionPlace(1, 2, 300, 100, spacing=1.5),
            'lap': s.SectionPlace(1, 2, 300, 40),
        }
        s.save_settings(path, s.Settings(sections=places))
        self.assertEqual(s.load_settings(path).sections, places)
        text = path.read_text(encoding='utf-8')
        self.assertEqual(text.count('"spacing"'), 1)

    def test_a_wrong_value_is_the_usual_or_held_within_limits(self):
        self.assertEqual(s._spacing('wide'), 1.0)
        self.assertEqual(s._spacing(9), 3.0)
        self.assertEqual(s._spacing(-1), 0.0)


class RadarCockpitSettingTests(unittest.TestCase):
    def test_on_unless_turned_off(self):
        path = Path(tempfile.mkdtemp()) / s.SETTINGS_FILE
        self.assertTrue(s.Settings().radar_cockpit_only)
        s.save_settings(path, s.Settings(radar_cockpit_only=False))
        self.assertFalse(s.load_settings(path).radar_cockpit_only)
        path.write_text('{}', encoding='utf-8')
        self.assertTrue(s.load_settings(path).radar_cockpit_only)


class GearSettingTests(unittest.TestCase):
    def test_on_unless_turned_off(self):
        path = Path(tempfile.mkdtemp()) / s.SETTINGS_FILE
        self.assertTrue(s.Settings().gear)
        s.save_settings(path, s.Settings(gear=False))
        self.assertFalse(s.load_settings(path).gear)
