"""Screenshots of the game with the HUD on it: Ctrl+Shift+S (asked for by the user on
2026-11-11: Steam's F12 needs Steam's overlay, which does not show in TSU's CrossOver bottle
with D3DMetal). Ctrl+Shift+S is free in TSU (its key bindings know only Ctrl as a modifier;
its editor saves with Ctrl+S) and on macOS and Windows.

The picture is of the screen the HUD is on (where most of its shown sections are), saved as a
PNG in the Pictures folder, under TurboHUD (`screenshot_folder` in the settings file can name
another). How, by system:
- macOS: its own `screencapture` tool, which plays the camera sound. The first time, macOS
  asks whether TurboHUD may record the screen.
- Linux: `grim` where it is installed (Wayland, as on Hyprland), else Qt (X11).
- Windows: Qt. A game in Fullscreen Exclusive may come out black there.
The capture is started and TurboHUD goes on at once; nothing is written into the game.
"""

import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger(__name__)

FOLDER_NAME = 'TurboHUD'


def screenshot_folder(chosen=None, platform=sys.platform, home=None, environ=None):
    """Where screenshots go: `chosen` (the settings' screenshot_folder), else Pictures/TurboHUD
    (on Linux the XDG pictures folder where its variable says so)."""
    if chosen:
        return Path(chosen).expanduser()
    home = Path.home() if home is None else Path(home)
    environ = os.environ if environ is None else environ
    if not platform.startswith(('win', 'darwin')) and environ.get('XDG_PICTURES_DIR'):
        return Path(environ['XDG_PICTURES_DIR']) / FOLDER_NAME
    return home / 'Pictures' / FOLDER_NAME


def screenshot_name(now=None):
    """'TurboHUD 2026-11-11 at 12.34.56.png' for local time `now` (time.struct_time)."""
    now = time.localtime() if now is None else now
    return time.strftime(f'{FOLDER_NAME} %Y-%m-%d at %H.%M.%S.png', now)


def free_path(folder, name):
    """`folder/name`, or with ' 2', ' 3' ... before the extension when it is taken."""
    path = folder / name
    number = 2
    while path.exists():
        path = folder / f'{Path(name).stem} {number}{Path(name).suffix}'
        number += 1
    return path


def capture_command(path, screen_index, geometry, platform=sys.platform, which=shutil.which):
    """The command that saves the screen to `path`, or None where Qt takes it. `screen_index`
    is the screen's place in Qt's list (0: the main one), `geometry` its (x, y, width, height)."""
    if platform == 'darwin':
        return ['/usr/sbin/screencapture', '-D', str(screen_index + 1), str(path)]
    if not platform.startswith('win') and which('grim'):
        x, y, width, height = geometry
        return [which('grim'), '-g', f'{x},{y} {width}x{height}', str(path)]
    return None


def take_screenshot(screen, screen_index, folder, platform=sys.platform):
    """Save what `screen` (a QScreen) shows into `folder`; the file's path. Raises OSError
    when it cannot be started or saved."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = free_path(folder, screenshot_name())
    rect = screen.geometry()
    command = capture_command(path, screen_index, (rect.x(), rect.y(), rect.width(), rect.height()), platform)
    if command is not None:
        subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    elif not screen.grabWindow(0).save(str(path), 'PNG'):
        raise OSError(f'could not save {path}')
    log.info('screenshot: %s', path.name)
    return path
