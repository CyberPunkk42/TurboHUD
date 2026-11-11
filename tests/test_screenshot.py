import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud import app, control, screenshot
from turbohud.core import settings as s
from turbohud.overlay import HOTKEY_LOCK, HOTKEY_PRESETS, HOTKEY_QUIT, HOTKEY_SCREENSHOT


class FolderTests(unittest.TestCase):
    def test_pictures_turbohud_or_the_chosen_folder(self):
        home = Path('/home/racer')
        self.assertEqual(
            screenshot.screenshot_folder(None, 'darwin', home, {}), home / 'Pictures' / 'TurboHUD'
        )
        self.assertEqual(screenshot.screenshot_folder('', 'win32', home, {}), home / 'Pictures' / 'TurboHUD')
        self.assertEqual(
            screenshot.screenshot_folder(None, 'linux', home, {'XDG_PICTURES_DIR': '/pics'}),
            Path('/pics/TurboHUD'),
        )
        self.assertEqual(screenshot.screenshot_folder('/shots', 'linux', home, {}), Path('/shots'))

    def test_names_by_the_time_and_never_over_another(self):
        now = time.strptime('2026-11-11 12:34:56', '%Y-%m-%d %H:%M:%S')
        name = screenshot.screenshot_name(now)
        self.assertEqual(name, 'TurboHUD 2026-11-11 at 12.34.56.png')
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            self.assertEqual(screenshot.free_path(folder, name), folder / name)
            (folder / name).write_bytes(b'')
            (folder / 'TurboHUD 2026-11-11 at 12.34.56 2.png').write_bytes(b'')
            self.assertEqual(screenshot.free_path(folder, name).name, 'TurboHUD 2026-11-11 at 12.34.56 3.png')


class CaptureTests(unittest.TestCase):
    def test_each_system_its_own_way(self):
        path = Path('/p/shot.png')
        geometry = (1920, 0, 2560, 1440)
        self.assertEqual(
            screenshot.capture_command(path, 1, geometry, 'darwin'),
            ['/usr/sbin/screencapture', '-D', '2', str(path)],  # macOS counts its displays from 1
        )
        self.assertEqual(
            screenshot.capture_command(path, 0, geometry, 'linux', which=lambda _name: '/usr/bin/grim'),
            ['/usr/bin/grim', '-g', '1920,0 2560x1440', str(path)],
        )
        self.assertIsNone(screenshot.capture_command(path, 0, geometry, 'linux', which=lambda _name: None))
        self.assertIsNone(screenshot.capture_command(path, 0, geometry, 'win32', which=lambda _name: '/x'))

    def screen(self, saved=True):
        rect = mock.Mock()
        rect.x.return_value, rect.y.return_value, rect.width.return_value, rect.height.return_value = (
            0,
            0,
            800,
            600,
        )
        screen = mock.Mock()
        screen.geometry.return_value = rect
        screen.grabWindow.return_value.save.return_value = saved
        return screen

    def test_a_tool_is_started_and_turbohud_goes_on(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            mock.patch.object(screenshot.subprocess, 'Popen') as popen,
        ):
            path = screenshot.take_screenshot(self.screen(), 0, Path(folder) / 'new', 'darwin')
            self.assertEqual(path.parent, Path(folder) / 'new')  # made where it was missing
        command = popen.call_args[0][0]
        self.assertEqual(command[:3], ['/usr/sbin/screencapture', '-D', '1'])
        self.assertEqual(command[-1], str(path))

    def test_qt_takes_it_where_there_is_no_tool(self):
        screen = self.screen()
        with tempfile.TemporaryDirectory() as folder:
            path = screenshot.take_screenshot(screen, 0, folder, 'win32')
        screen.grabWindow.return_value.save.assert_called_once_with(str(path), 'PNG')
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(OSError):
            screenshot.take_screenshot(self.screen(saved=False), 0, folder, 'win32')


class WiringTests(unittest.TestCase):
    def test_its_own_hotkey_and_command(self):
        self.assertNotIn(HOTKEY_SCREENSHOT, (HOTKEY_LOCK, HOTKEY_QUIT, *HOTKEY_PRESETS))
        self.assertIn('screenshot', control.COMMANDS)
        self.assertEqual(app.command_of(app.parse_args(['--screenshot'])), 'screenshot')

    def test_the_folder_is_kept_in_the_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text(json.dumps({}))
            self.assertEqual(s.load_settings(path).screenshot_folder, '')
            s.save_settings(path, s.Settings(screenshot_folder='/shots'))
            self.assertEqual(s.load_settings(path).screenshot_folder, '/shots')
            path.write_text(json.dumps({'screenshot_folder': 3}))
            self.assertEqual(s.load_settings(path).screenshot_folder, '')


if __name__ == '__main__':
    unittest.main()
