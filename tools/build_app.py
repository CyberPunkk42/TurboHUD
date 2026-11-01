"""Build TurboHUD as a ready-to-run app for this system with PyInstaller, and pack it.

    python tools/build_app.py [--version 2026.10.24] [--smoke]

Needs the packages in requirements-build.txt. PyInstaller builds only for the system it
runs on, so GitHub Actions runs this once per system (.github/workflows/build.yml).

- Windows: releases/TurboHUD-<version>-windows-x64.zip, holding TurboHUD/TurboHUD.exe
- macOS:   releases/TurboHUD-<version>-macos-arm64.zip, holding TurboHUD.app
- Linux:   releases/TurboHUD-<version>-linux-x64.tar.gz, holding TurboHUD/TurboHUD

Each archive gets a .sha256 file next to it. --smoke then starts the built app for a few
seconds and fails if it does not quit cleanly.
"""

import argparse
import hashlib
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build'
RELEASES = ROOT / 'releases'
VERSION_FILE = ROOT / 'turbohud' / '_build.py'  # gitignored; written for the build only
NAME = 'TurboHUD'
ICON = ROOT / 'assets' / 'tsu_turbo_hud_00.png'  # PyInstaller turns it into .ico / .icns with Pillow
BUNDLE_ID = 'io.github.cyberpunkk42.turbohud'
SMOKE_SECONDS = 3
SMOKE_TIMEOUT = 120
_VERSION = re.compile(r'dev|\d{4}\.\d{2}\.\d{2}')


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Build the TurboHUD app for this system.')
    parser.add_argument('--version', default='dev', help='dev, or a release date like 2026.10.24')
    parser.add_argument('--smoke', action='store_true', help='start the built app briefly to check it')
    args = parser.parse_args(argv)
    args.version = args.version.removeprefix('v')
    if not _VERSION.fullmatch(args.version):
        parser.error(f'version must be dev or YYYY.MM.DD: {args.version}')
    return args


def platform_tag(system=sys.platform, machine=None):
    """'windows-x64', 'macos-arm64', 'linux-x64' and so on."""
    machine = (machine or platform.machine()).lower()
    cpu = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(machine, machine)
    name = {'win32': 'windows', 'darwin': 'macos'}.get(
        system, 'linux' if system.startswith('linux') else system
    )
    return f'{name}-{cpu}'


def archive_name(version, tag):
    extension = '.tar.gz' if tag.startswith('linux') else '.zip'
    return f'{NAME}-{version}-{tag}{extension}'


def pyinstaller_args(system=sys.platform):
    args = [
        str(ROOT / 'launch_turbohud.py'),
        '--name', NAME,
        '--windowed',
        '--noconfirm',
        '--clean',
        '--distpath', str(BUILD / 'dist'),
        '--workpath', str(BUILD / 'work'),
        '--specpath', str(BUILD),
        '--paths', str(ROOT),
        '--exclude-module', 'tkinter',
        '--icon', str(ICON),
        '--add-data', f'{ICON}:assets',  # for the tray and window icon at runtime
    ]  # fmt: skip
    if system == 'darwin':
        args += ['--osx-bundle-identifier', BUNDLE_ID]
    return args


def mark_mac_app(app, version):
    """An accessory app (no Dock icon, LSUIElement) with its version, signed again ad hoc
    because changing Info.plist breaks PyInstaller's signature."""
    info_path = app / 'Contents' / 'Info.plist'
    with info_path.open('rb') as file:
        info = plistlib.load(file)
    info['LSUIElement'] = True
    if version != 'dev':
        info['CFBundleShortVersionString'] = version
    with info_path.open('wb') as file:
        plistlib.dump(info, file)
    subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(app)], check=True)


def pack(dist, archive, system=sys.platform):
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.unlink(missing_ok=True)
    if system == 'darwin':
        # ditto keeps the app's symbolic links and signature intact.
        app = dist / f'{NAME}.app'
        subprocess.run(
            ['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app), str(archive)], check=True
        )
    elif archive.name.endswith('.tar.gz'):
        with tarfile.open(archive, 'w:gz') as tar:
            tar.add(dist / NAME, arcname=NAME)
    else:
        folder = dist / NAME
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for path in sorted(folder.rglob('*')):
                zip_file.write(path, Path(NAME) / path.relative_to(folder))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(archive.name + '.sha256').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    return digest


def executable(dist, system=sys.platform):
    if system == 'darwin':
        return dist / f'{NAME}.app' / 'Contents' / 'MacOS' / NAME
    return dist / NAME / (f'{NAME}.exe' if system == 'win32' else NAME)


def smoke(program):
    env = dict(os.environ)
    if sys.platform.startswith('linux') and not env.get('DISPLAY') and not env.get('WAYLAND_DISPLAY'):
        env['QT_QPA_PLATFORM'] = 'offscreen'
    result = subprocess.run(
        [str(program), '--seconds', str(SMOKE_SECONDS)], env=env, timeout=SMOKE_TIMEOUT, check=False
    )
    if result.returncode != 0:
        raise SystemExit(f'smoke test failed: the app quit with {result.returncode}')
    print('smoke test passed')


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    import PyInstaller.__main__

    VERSION_FILE.write_text(f'VERSION = {args.version!r}\n', encoding='utf-8')
    try:
        PyInstaller.__main__.run(pyinstaller_args())
    finally:
        VERSION_FILE.unlink(missing_ok=True)
    dist = BUILD / 'dist'
    if sys.platform == 'darwin':
        mark_mac_app(dist / f'{NAME}.app', args.version)
    archive = RELEASES / archive_name(args.version, platform_tag())
    digest = pack(dist, archive)
    size = archive.stat().st_size / 1e6
    print(f'{archive.relative_to(ROOT)}: {size:.1f} MB, sha256 {digest}')
    if args.smoke:
        smoke(executable(dist))
    shutil.rmtree(BUILD / 'work', ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
