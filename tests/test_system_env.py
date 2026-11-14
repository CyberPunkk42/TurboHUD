import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from turbohud.core.system_env import system_env
from turbohud.overlay import hyprland
from turbohud.tsu import probe


class SystemEnvTests(unittest.TestCase):
    BUNDLE = '/home/a/TurboHUD/_internal'

    def test_from_the_source_folder_nothing_changes(self):
        env = {'LD_LIBRARY_PATH': '/steam/lib', 'HOME': '/home/a'}
        self.assertEqual(system_env(env, frozen=False), env)

    def test_the_bundled_app_gives_back_the_library_path_from_before(self):
        env = {
            'LD_LIBRARY_PATH': f'{self.BUNDLE}:/steam/lib',
            'LD_LIBRARY_PATH_ORIG': '/steam/lib',
            '_PYI_APPLICATION_HOME_DIR': self.BUNDLE,
            '_PYI_PARENT_PROCESS_LEVEL': '1',
            'SteamAppId': '1234',
        }
        self.assertEqual(
            system_env(env, frozen=True, bundle=self.BUNDLE),
            {'LD_LIBRARY_PATH': '/steam/lib', 'SteamAppId': '1234'},
        )

    def test_a_path_only_pyinstaller_set_is_dropped(self):
        env = {'LD_LIBRARY_PATH': self.BUNDLE, 'HOME': '/home/a'}
        self.assertEqual(system_env(env, frozen=True, bundle=self.BUNDLE), {'HOME': '/home/a'})
        env = {'LD_LIBRARY_PATH': f'{self.BUNDLE}:/other/lib'}
        self.assertEqual(system_env(env, frozen=True, bundle=self.BUNDLE), {'LD_LIBRARY_PATH': '/other/lib'})

    def test_the_input_is_left_alone(self):
        env = {'LD_LIBRARY_PATH': self.BUNDLE, 'LD_LIBRARY_PATH_ORIG': '/steam/lib'}
        system_env(env, frozen=True, bundle=self.BUNDLE)
        self.assertEqual(env, {'LD_LIBRARY_PATH': self.BUNDLE, 'LD_LIBRARY_PATH_ORIG': '/steam/lib'})


class UsedByTests(unittest.TestCase):
    """hyprctl and the game both get it (hyprctl did not start in the bundled app without)."""

    def test_hyprctl(self):
        with (
            mock.patch.object(hyprland, 'system_env', return_value={'X': '1'}),
            mock.patch('subprocess.run') as run,
        ):
            run.return_value.stdout = ' ok '
            self.assertEqual(hyprland._run(['version']), 'ok')
        self.assertEqual(run.call_args.kwargs['env'], {'X': '1'})

    def test_the_game(self):
        with (
            mock.patch.object(probe, 'system_env', return_value={'X': '1'}),
            mock.patch('subprocess.Popen') as popen,
            mock.patch.object(probe, 'find_game', return_value=None),
            mock.patch.object(probe, 'log'),
            mock.patch('signal.signal'),
        ):
            popen.return_value.wait.return_value = 0
            self.assertEqual(probe.run_game(['game']), 0)
        self.assertEqual(popen.call_args.kwargs['env'], {'X': '1'})


if __name__ == '__main__':
    unittest.main()
