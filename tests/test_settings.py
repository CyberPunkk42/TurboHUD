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
            places = {'delta': s.SectionPlace(2000, 600, 300, 60), 'times': s.SectionPlace(10, 20, 250, 40, visible=False)}
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
            path.write_text(json.dumps({'sections': {
                'lap': {'x': 1, 'y': 2, 'width': 100, 'height': 30},
                'delta': {'x': 'left'},
                'times': 'nonsense',
                'current': {'x': 1, 'y': 2, 'width': 0, 'height': 0},
            }}))
            self.assertEqual(list(s.load_settings(path).sections), ['lap'])


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


if __name__ == '__main__':
    unittest.main()
