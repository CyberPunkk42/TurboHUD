import json
import sys
import tempfile
import unittest
from pathlib import Path

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

    def test_it_round_trips_and_stays_at_20_by_default(self):
        path = self.path()
        self.assertEqual(s.Settings().reads_per_second, 20)
        s.save_settings(path, s.Settings(reads_per_second=5))
        self.assertEqual(s.load_settings(path).reads_per_second, 5)

    def test_a_file_from_before_or_a_wrong_value_gives_the_default(self):
        path = self.path()
        for data in ({}, {'reads_per_second': 7}, {'reads_per_second': 'often'}, {'reads_per_second': [10]}):
            path.write_text(json.dumps(data))
            self.assertEqual(s.load_settings(path).reads_per_second, 20)


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
