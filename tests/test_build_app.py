import contextlib
import hashlib
import importlib.util
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT))

import build_app

from turbohud import app


class BuildArgsTests(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(build_app.parse_args([]).version, 'dev')
        self.assertEqual(build_app.parse_args(['--version', 'v2026.10.24']).version, '2026.10.24')

    def test_a_second_build_of_a_day(self):
        self.assertEqual(build_app.parse_args(['--version', '2026.11.06.2']).version, '2026.11.06.2')

    def test_rejects_other_versions(self):
        for version in ('1.0', '2026-10-24', 'v26.1.1'):
            with (
                self.subTest(version=version),
                self.assertRaises(SystemExit),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                build_app.parse_args(['--version', version])


class NamingTests(unittest.TestCase):
    def test_platform_tags(self):
        self.assertEqual(build_app.platform_tag('win32', 'AMD64'), 'windows-x64')
        self.assertEqual(build_app.platform_tag('darwin', 'arm64'), 'macos-arm64')
        self.assertEqual(build_app.platform_tag('linux', 'x86_64'), 'linux-x64')
        self.assertEqual(build_app.platform_tag('linux', 'aarch64'), 'linux-arm64')

    def test_archive_names(self):
        self.assertEqual(
            build_app.archive_name('2026.10.24', 'windows-x64'), 'TurboHUD-2026.10.24-windows-x64.zip'
        )
        self.assertEqual(build_app.archive_name('dev', 'linux-x64'), 'TurboHUD-dev-linux-x64.tar.gz')

    def test_the_mac_app_comes_as_a_disk_image(self):
        self.assertEqual(build_app.archive_name('dev', 'macos-arm64'), 'TurboHUD-dev-macos-arm64.dmg')

    def test_executables(self):
        dist = Path('dist')
        self.assertEqual(build_app.executable(dist, 'win32'), dist / 'TurboHUD' / 'TurboHUD.exe')
        self.assertEqual(build_app.executable(dist, 'linux'), dist / 'TurboHUD' / 'TurboHUD')
        self.assertEqual(
            build_app.executable(dist, 'darwin'), dist / 'TurboHUD.app' / 'Contents' / 'MacOS' / 'TurboHUD'
        )

    def test_the_macos_a_program_needs(self):
        text = (
            'program (architecture arm64):\n'
            'Load command 8\n'
            '      cmd LC_BUILD_VERSION\n'
            ' platform MACOS\n'
            '    minos 11.0\n'
            '      sdk 14.2\n'
            '   ntools 1\n'
            '     tool LD\n'
            '  version 27037.1\n'
        )
        self.assertEqual(build_app.minimum_in(text), (11, 0))
        self.assertEqual(build_app.minimum_in(text + '    minos 13.4\n'), (13, 4))
        self.assertEqual(
            build_app.minimum_in('      cmd LC_VERSION_MIN_MACOSX\n  cmdsize 16\n  version 10.15\n'), (10, 15)
        )
        self.assertIsNone(build_app.minimum_in('no build version\n'))

    def test_the_build_stops_if_the_app_would_need_too_new_a_macos(self):
        build_app.check_mac_minimum((13, 0), Path('fine'), most=(15, 0))
        build_app.check_mac_minimum((15, 0), Path('fine'), most=(15, 0))
        with self.assertRaises(SystemExit) as stopped:
            build_app.check_mac_minimum((27, 0), Path('Python'), most=(15, 0))
        self.assertIn('Python needs macOS 27.0', str(stopped.exception))

    def test_programs_are_told_from_other_files(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Path(folder)
            (app / 'library.dylib').write_bytes(b'\xcf\xfa\xed\xfe' + b'x' * 20)
            (app / 'universal').write_bytes(b'\xca\xfe\xba\xbe' + b'x' * 20)
            (app / 'windows.exe').write_bytes(b'MZ' + b'x' * 20)
            (app / 'text.txt').write_text('hello')
            (app / 'empty').write_bytes(b'')
            (app / 'link').symlink_to(app / 'library.dylib')
            found = [path.name for path in build_app.mac_programs(app)]
        self.assertEqual(found, ['library.dylib', 'universal'])

    def test_the_quick_start_has_every_shortcut(self):
        text = build_app.QUICK_START.read_text(encoding='utf-8')
        for keys in ('Ctrl+Shift+L', 'Ctrl+Shift+F12', 'Ctrl+Shift+1', 'Ctrl+Shift+Q', 'AMD Software'):
            self.assertIn(keys, text)

    def test_the_read_me_says_what_to_do(self):
        text = build_app.MAC_READ_ME.read_text(encoding='utf-8')
        self.assertIn('{minimum}', text)
        self.assertIn('Open Anyway', text)
        self.assertIn('D3DMetal', text)

    @unittest.skipUnless(sys.platform == 'darwin', 'makes a disk image')
    def test_the_disk_image_holds_the_app_the_link_and_the_read_me(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = root / 'dist' / 'TurboHUD.app'
            (app / 'Contents').mkdir(parents=True)
            (app / 'Contents' / 'Info.plist').write_text('x')
            archive = root / 'out' / 'TurboHUD-dev-macos-arm64.dmg'
            build_app.pack(root / 'dist', archive, 'darwin', (13, 0))
            mount = root / 'mount'
            subprocess.run(
                [
                    'hdiutil',
                    'attach',
                    '-quiet',
                    '-nobrowse',
                    '-readonly',
                    '-mountpoint',
                    str(mount),
                    str(archive),
                ],
                check=True,
            )
            try:
                self.assertEqual(
                    sorted(path.name for path in mount.iterdir() if not path.name.startswith('.')),
                    ['Applications', 'Quick Start.txt', 'Read Me First.txt', 'TurboHUD.app'],
                )
                self.assertEqual(os.readlink(mount / 'Applications'), '/Applications')
                read_me = (mount / 'Read Me First.txt').read_text(encoding='utf-8')
                self.assertIn('macOS 13.0 or newer', read_me)
                self.assertNotIn('{minimum}', read_me)
            finally:
                subprocess.run(['hdiutil', 'detach', '-quiet', str(mount)], check=True)
            self.assertTrue(archive.with_name(archive.name + '.sha256').exists())

    def test_bundle_id_only_on_the_mac(self):
        self.assertIn('--osx-bundle-identifier', build_app.pyinstaller_args('darwin'))
        self.assertNotIn('--osx-bundle-identifier', build_app.pyinstaller_args('win32'))
        self.assertIn('--windowed', build_app.pyinstaller_args('linux'))

    def test_icon_is_the_app_icon_and_ships_inside(self):
        args = build_app.pyinstaller_args('win32')
        self.assertEqual(args[args.index('--icon') + 1], str(build_app.ICON))
        self.assertEqual(args[args.index('--add-data') + 1], f'{build_app.ICON}:assets')
        self.assertTrue(build_app.ICON.is_file())


class PackTests(unittest.TestCase):
    def make_dist(self, folder):
        dist = Path(folder) / 'dist'
        (dist / 'TurboHUD' / '_internal').mkdir(parents=True)
        (dist / 'TurboHUD' / 'TurboHUD.exe').write_bytes(b'program')
        (dist / 'TurboHUD' / '_internal' / 'lib.dll').write_bytes(b'library')
        return dist

    def check_digest(self, archive):
        line = archive.with_name(archive.name + '.sha256').read_text(encoding='utf-8')
        self.assertEqual(line, f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n')

    def test_zip_holds_the_app_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'out' / 'TurboHUD-dev-windows-x64.zip'
            build_app.pack(self.make_dist(folder), archive, system='win32')
            with zipfile.ZipFile(archive) as zip_file:
                self.assertEqual(sorted(zip_file.namelist()), [
                    'TurboHUD/Quick Start.txt', 'TurboHUD/TurboHUD.exe', 'TurboHUD/_internal/',
                    'TurboHUD/_internal/lib.dll',
                ])  # fmt: skip
                guide = zip_file.read('TurboHUD/Quick Start.txt')
                self.assertEqual(guide, build_app.QUICK_START.read_bytes())
            self.check_digest(archive)

    def test_tar_holds_the_app_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'TurboHUD-dev-linux-x64.tar.gz'
            build_app.pack(self.make_dist(folder), archive, system='linux')
            with tarfile.open(archive) as tar:
                self.assertIn('TurboHUD/_internal/lib.dll', tar.getnames())
                self.assertIn('TurboHUD/Quick Start.txt', tar.getnames())
            self.check_digest(archive)


class AssetPathTests(unittest.TestCase):
    def test_from_the_source_folder(self):
        self.assertEqual(app.asset_path(app.ICON), ROOT / 'assets' / app.ICON)
        self.assertTrue(app.asset_path(app.ICON).is_file())

    def test_inside_the_bundle(self):
        self.assertEqual(app.asset_path(app.ICON, bundle='/b'), Path('/b') / 'assets' / app.ICON)


class AppArgsTests(unittest.TestCase):
    def test_defaults(self):
        args = app.parse_args([])
        self.assertFalse(args.move)
        self.assertIsNone(args.seconds)

    def test_rejects_bad_seconds(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            app.parse_args(['--seconds', '0'])

    @unittest.skipIf(importlib.util.find_spec('PySide6'), 'checks the message shown without Qt')
    def test_without_qt_points_to_the_start_scripts(self):
        # As if no TurboHUD runs: main() first asks a running one over the real command
        # socket, and a test run once switched the player's TurboHUD to move mode mid-race.
        with (
            mock.patch('turbohud.control.send', return_value=None) as send,
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            self.assertEqual(app.main(['--seconds', '1']), 2)
        send.assert_called_once_with('ping')
        self.assertIn('run_turbohud', err.getvalue())


if __name__ == '__main__':
    unittest.main()
