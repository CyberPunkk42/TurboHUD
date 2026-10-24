import contextlib
import hashlib
import importlib.util
import io
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT))

import build_app

from turbokit import app


class BuildArgsTests(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(build_app.parse_args([]).version, 'dev')
        self.assertEqual(build_app.parse_args(['--version', 'v2026.10.24']).version, '2026.10.24')

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
            build_app.archive_name('2026.10.24', 'windows-x64'), 'TurboKit-2026.10.24-windows-x64.zip'
        )
        self.assertEqual(build_app.archive_name('dev', 'linux-x64'), 'TurboKit-dev-linux-x64.tar.gz')

    def test_executables(self):
        dist = Path('dist')
        self.assertEqual(build_app.executable(dist, 'win32'), dist / 'TurboKit' / 'TurboKit.exe')
        self.assertEqual(build_app.executable(dist, 'linux'), dist / 'TurboKit' / 'TurboKit')
        self.assertEqual(
            build_app.executable(dist, 'darwin'), dist / 'TurboKit.app' / 'Contents' / 'MacOS' / 'TurboKit'
        )

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
        (dist / 'TurboKit' / '_internal').mkdir(parents=True)
        (dist / 'TurboKit' / 'TurboKit.exe').write_bytes(b'program')
        (dist / 'TurboKit' / '_internal' / 'lib.dll').write_bytes(b'library')
        return dist

    def check_digest(self, archive):
        line = archive.with_name(archive.name + '.sha256').read_text(encoding='utf-8')
        self.assertEqual(line, f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n')

    def test_zip_holds_the_app_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'out' / 'TurboKit-dev-windows-x64.zip'
            build_app.pack(self.make_dist(folder), archive, system='win32')
            with zipfile.ZipFile(archive) as zip_file:
                self.assertEqual(sorted(zip_file.namelist()), [
                    'TurboKit/TurboKit.exe', 'TurboKit/_internal/', 'TurboKit/_internal/lib.dll',
                ])  # fmt: skip
            self.check_digest(archive)

    def test_tar_holds_the_app_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'TurboKit-dev-linux-x64.tar.gz'
            build_app.pack(self.make_dist(folder), archive, system='linux')
            with tarfile.open(archive) as tar:
                self.assertIn('TurboKit/_internal/lib.dll', tar.getnames())
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
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(app.main(['--seconds', '1']), 2)
        self.assertIn('run_turbokit', err.getvalue())


if __name__ == '__main__':
    unittest.main()
