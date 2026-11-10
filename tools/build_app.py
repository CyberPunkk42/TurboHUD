"""Build TurboHUD as a ready-to-run app for this system with PyInstaller, and pack it.

    python tools/build_app.py [--version 2026.10.24[.2]] [--smoke]

Needs the packages in requirements-build.txt. PyInstaller builds only for the system it
runs on, so GitHub Actions runs this once per system (.github/workflows/build.yml). On the
Mac, build with the Python from tools/get_mac_python.sh: with Homebrew's, the app would
only start on this Mac's macOS or newer, and the build stops.

- Windows: releases/TurboHUD-<version>-windows-x64.zip, holding TurboHUD/TurboHUD.exe
- macOS:   releases/TurboHUD-<version>-macos-arm64.dmg, holding TurboHUD.app, a link to
           Applications to drag it onto, and a read-me (tools/mac_read_me.txt)
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
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build'
RELEASES = ROOT / 'releases'
VERSION_FILE = ROOT / 'turbohud' / '_build.py'  # gitignored; written for the build only
NAME = 'TurboHUD'
ICON = ROOT / 'assets' / 'tsu_turbo_hud_00.png'  # PyInstaller turns it into .ico / .icns with Pillow
BUNDLE_ID = 'local.turbohud.TurboHUD'  # holds nothing personal: it goes out with the app
MAC_READ_ME = ROOT / 'tools' / 'mac_read_me.txt'
MAC_NEWEST_MINIMUM = (15, 0)  # the build stops if the app would need a newer macOS than this
MACH_O_MAGIC = {
    b'\xcf\xfa\xed\xfe',  # 64-bit
    b'\xce\xfa\xed\xfe',  # 32-bit
    b'\xca\xfe\xba\xbe',  # universal
}
_MINOS = re.compile(r'^\s*minos\s+(\d+)\.(\d+)', re.MULTILINE)
_VERSION_MIN = re.compile(r'LC_VERSION_MIN_MACOSX\s*\n(?:\s*cmdsize.*\n)?\s*version\s+(\d+)\.(\d+)')
SMOKE_SECONDS = 3
SMOKE_TIMEOUT = 120
_VERSION = re.compile(r'dev|\d{4}\.\d{2}\.\d{2}(\.\d+)?')  # a second build of a day: .2
# The Mac app's reader runs in TSU's CrossOver bottle with its own Windows Python, so it
# ships as plain files beside the app: these, and that Python (see turbohud/tsu/bottle.py).
WIN_PYTHON = ROOT / '.buildtools' / 'win-python'
GET_WIN_PYTHON = ROOT / 'tools' / 'get_windows_python.sh'
# The Rust reader, which the Mac app starts in place of the Python one (turbohud/tsu/bottle.py).
RUST_READER = ROOT / '.buildtools' / 'reader' / 'turbohud-reader.exe'
GET_RUST = ROOT / 'tools' / 'get_rust.sh'
READER_FILES = (
    'turbohud/__init__.py',
    'turbohud/tsu/__init__.py',
    'turbohud/tsu/bottle_reader.py',
    'turbohud/tsu/gamelog.py',
    'turbohud/tsu/winmemory.py',
)


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Build the TurboHUD app for this system.')
    parser.add_argument(
        '--version',
        default='dev',
        help='dev, or a release date like 2026.10.24, with .2 for a second build that day',
    )
    parser.add_argument('--smoke', action='store_true', help='start the built app briefly to check it')
    parser.add_argument(
        '--any-macos',
        action='store_true',
        help='Mac: build even if the app would only start on a new macOS (the build says which)',
    )
    args = parser.parse_args(argv)
    args.version = args.version.removeprefix('v')
    if not _VERSION.fullmatch(args.version):
        parser.error(f'version must be dev or YYYY.MM.DD[.N]: {args.version}')
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
    extension = '.tar.gz' if tag.startswith('linux') else '.dmg' if tag.startswith('macos') else '.zip'
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
        args += ['--add-data', f'{WIN_PYTHON}:win-python']
        args += ['--add-data', f'{RUST_READER}:reader']
        for name in READER_FILES:
            args += ['--add-data', f'{ROOT / name}:{Path(name).parent.as_posix()}']
    return args


def minimum_in(build_text):
    """The newest macOS a program asks for in `vtool -show-build` text, as (major, minor),
    or None. A universal program lists each of its parts."""
    # Not any line called version: the tools that made the program list theirs too.
    found = _MINOS.findall(build_text) + _VERSION_MIN.findall(build_text)
    return max(((int(major), int(minor)) for major, minor in found), default=None)


def mac_programs(app):
    """The programs and libraries inside `app`: everything in Mach-O format."""
    for path in sorted(app.rglob('*')):
        if path.is_file() and not path.is_symlink():
            with path.open('rb') as file:
                if file.read(4) in MACH_O_MAGIC:
                    yield path


def mac_minimum(app):
    """(the oldest macOS on which all of `app` can start, as (major, minor), the program
    that asks for it)."""
    newest, program = (0, 0), None
    for path in mac_programs(app):
        text = subprocess.run(
            ['vtool', '-show-build', str(path)], capture_output=True, text=True, check=False
        ).stdout
        minimum = minimum_in(text)
        if minimum is not None and minimum > newest:
            newest, program = minimum, path
    return newest, program


def check_mac_minimum(minimum, program, most=MAC_NEWEST_MINIMUM):
    """Stop the build if the app would not start on the macOS versions it is meant for."""
    if minimum > most:
        raise SystemExit(
            f'{program} needs macOS {minimum[0]}.{minimum[1]}, newer than the '
            f'{most[0]}.{most[1]} allowed: build with the Python from tools/get_mac_python.sh'
        )


def mark_mac_app(app, version, minimum=None):
    """An accessory app (no Dock icon, LSUIElement) with its version and the macOS it needs,
    signed again ad hoc because changing Info.plist breaks PyInstaller's signature."""
    info_path = app / 'Contents' / 'Info.plist'
    with info_path.open('rb') as file:
        info = plistlib.load(file)
    info['LSUIElement'] = True
    if minimum is not None:
        info['LSMinimumSystemVersion'] = f'{minimum[0]}.{minimum[1]}'
    if version != 'dev':
        info['CFBundleShortVersionString'] = version
        info['CFBundleVersion'] = version
    with info_path.open('wb') as file:
        plistlib.dump(info, file)
    subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(app)], check=True)
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)


def pack_dmg(app, archive, minimum):
    """A disk image that opens on the app, a link to Applications and the read-me."""
    read_me = MAC_READ_ME.read_text(encoding='utf-8').replace('{minimum}', f'{minimum[0]}.{minimum[1]}')
    with tempfile.TemporaryDirectory() as folder:
        stage = Path(folder)
        subprocess.run(['ditto', str(app), str(stage / app.name)], check=True)  # keeps links and signature
        (stage / 'Applications').symlink_to('/Applications')
        (stage / 'Read Me First.txt').write_text(read_me, encoding='utf-8')
        subprocess.run(
            ['hdiutil', 'create', '-quiet', '-volname', NAME, '-srcfolder', str(stage), '-ov']
            + ['-format', 'UDZO', str(archive)],
            check=True,
        )


def pack(dist, archive, system=sys.platform, minimum=(0, 0)):
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.unlink(missing_ok=True)
    if system == 'darwin':
        pack_dmg(dist / f'{NAME}.app', archive, minimum)
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

    if sys.platform == 'darwin':
        subprocess.run(['sh', str(GET_WIN_PYTHON)], check=True)
        subprocess.run(['sh', str(GET_RUST)], check=True)  # sets up Rust if needed, builds the reader
    VERSION_FILE.write_text(f'VERSION = {args.version!r}\n', encoding='utf-8')
    try:
        PyInstaller.__main__.run(pyinstaller_args())
    finally:
        VERSION_FILE.unlink(missing_ok=True)
    dist = BUILD / 'dist'
    minimum = (0, 0)
    if sys.platform == 'darwin':
        minimum, program = mac_minimum(dist / f'{NAME}.app')
        if not args.any_macos:
            check_mac_minimum(minimum, program)
        print(f'the app needs macOS {minimum[0]}.{minimum[1]}, because of {program.name}')
        mark_mac_app(dist / f'{NAME}.app', args.version, minimum)
    archive = RELEASES / archive_name(args.version, platform_tag())
    digest = pack(dist, archive, minimum=minimum)
    size = archive.stat().st_size / 1e6
    print(f'{archive.relative_to(ROOT)}: {size:.1f} MB, sha256 {digest}')
    if args.smoke:
        smoke(executable(dist))
    shutil.rmtree(BUILD / 'work', ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
