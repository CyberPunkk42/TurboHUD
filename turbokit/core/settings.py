"""TurboKit's settings: where they live on each system, and reading and writing them.

Settings are one JSON file in the user's settings folder. Reading never fails: a missing,
broken or partly wrong file gives the defaults for whatever is missing or wrong.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

APP_NAME = 'TurboKit'
SETTINGS_FILE = 'settings.json'
LOG_FILE = 'turbokit.log'
DEFAULT_PLACEMENT = (40, 40, 420, 190)  # x, y, width, height
MIN_WIDTH = 240
MIN_HEIGHT = 100
MIN_SCALE = 0.5
MAX_SCALE = 3.0
_COLOR = re.compile(r'#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?')


@dataclass(frozen=True)
class Theme:
    text_color: str = '#ffffff'
    accent_color: str = '#ffd65a'
    outline_color: str = '#000000c8'  # #rrggbbaa: the dark edge that keeps text readable
    scale: float = 1.0  # size of everything the HUD draws


@dataclass(frozen=True)
class Settings:
    placement: tuple = DEFAULT_PLACEMENT
    theme: Theme = field(default_factory=Theme)


def settings_dir(platform=sys.platform, environ=None, home=None):
    """The folder for TurboKit's settings and log on this system."""
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    if platform == 'win32':
        base = environ.get('APPDATA')
        return (Path(base) if base else home / 'AppData' / 'Roaming') / APP_NAME
    if platform == 'darwin':
        return home / 'Library' / 'Application Support' / APP_NAME
    base = environ.get('XDG_CONFIG_HOME')
    return (Path(base) if base else home / '.config') / APP_NAME


def clamped_size(width, height):
    return max(width, MIN_WIDTH), max(height, MIN_HEIGHT)


def fit_on_screens(placement, screens):
    """The placement, moved to the default spot on the first screen if no part of its top
    edge is on any screen (for example after a monitor was unplugged). `screens` are
    (x, y, width, height) boxes; with none known, the placement is kept."""
    x, y, width, height = placement
    for sx, sy, sw, sh in screens:
        if sy <= y < sy + sh and x < sx + sw and x + width > sx:
            return placement
    if not screens:
        return placement
    sx, sy = screens[0][:2]
    return (sx + DEFAULT_PLACEMENT[0], sy + DEFAULT_PLACEMENT[1], width, height)


def _color(value, default):
    return value if isinstance(value, str) and _COLOR.fullmatch(value) else default


def _theme(data):
    theme = Theme()
    if not isinstance(data, dict):
        return theme
    scale = data.get('scale')
    if isinstance(scale, (int, float)) and not isinstance(scale, bool):
        theme = replace(theme, scale=min(max(float(scale), MIN_SCALE), MAX_SCALE))
    return replace(
        theme,
        text_color=_color(data.get('text_color'), theme.text_color),
        accent_color=_color(data.get('accent_color'), theme.accent_color),
        outline_color=_color(data.get('outline_color'), theme.outline_color),
    )


def _placement(data):
    try:
        x, y, width, height = (int(data[key]) for key in ('x', 'y', 'width', 'height'))
    except (KeyError, TypeError, ValueError):
        return DEFAULT_PLACEMENT
    return (x, y, *clamped_size(width, height))


def load_settings(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    return Settings(placement=_placement(data.get('placement')), theme=_theme(data.get('theme')))


def save_settings(path, settings):
    """Write the settings; a temporary file and a rename keep the old file whole if
    writing fails halfway."""
    path = Path(path)
    x, y, width, height = settings.placement
    data = {
        'placement': {'x': x, 'y': y, 'width': width, 'height': height},
        'theme': {
            'text_color': settings.theme.text_color,
            'accent_color': settings.theme.accent_color,
            'outline_color': settings.theme.outline_color,
            'scale': settings.theme.scale,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)
