"""TurboHUD's settings: where they live on each system, and reading and writing them.

Settings are one JSON file in the user's settings folder. Reading never fails: a missing,
broken or partly wrong file gives the defaults for whatever is missing or wrong.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

APP_NAME = 'TurboHUD'
SETTINGS_FILE = 'settings.json'
LOG_FILE = 'turbohud.log'
DEFAULT_PLACEMENT = (40, 40, 420, 190)  # x, y, width, height
MIN_WIDTH = 240
MIN_HEIGHT = 100
MIN_SECTION_SIZE = 8  # a saved section smaller than this is broken
SPEED_UNITS = ('kmh', 'mph')
MIN_SCALE = 0.5
MAX_SCALE = 3.0
LAYOUT_VERSION = 3  # 2: a text section's box fits closely round its text; 3: 20 lap times
_COLOR = re.compile(r'#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?')


@dataclass(frozen=True)
class Theme:
    text_color: str = '#ffffff'
    accent_color: str = '#ffd65a'
    outline_color: str = '#000000c8'  # #rrggbbaa: the dark edge that keeps text readable
    scale: float = 1.0  # size of everything the HUD draws


GROUPS = ('A', 'B', 'C', 'D')  # section groups; '' is none
PRESETS = (1, 2, 3)  # the layouts a player can keep


@dataclass(frozen=True)
class SectionPlace:
    """Where one HUD section sits and whether it shows."""

    x: int
    y: int
    width: int
    height: int
    visible: bool = True
    group: str = ''  # sections with the same group (one of GROUPS) move together
    text_centred: bool = False  # its text in the middle of its box, not at the left
    tint: bool = False  # a light tint behind its text while locked


@dataclass(frozen=True)
class Settings:
    placement: tuple = DEFAULT_PLACEMENT  # the whole HUD before it had sections; new sections start here
    theme: Theme = field(default_factory=Theme)
    sections: dict = field(default_factory=dict)  # section name -> SectionPlace
    speed_unit: str = 'kmh'  # 'kmh' or 'mph'
    backdrop: bool = False  # every text section has its tint on (see SectionPlace.tint)
    map_others: bool = False  # the track map also shows the other cars, as faint grey dots
    layout_version: int = 1  # how to read the section sizes: LAYOUT_VERSION is the latest
    presets: dict = field(default_factory=dict)  # number (one of PRESETS) -> a kept `sections`


def settings_dir(platform=sys.platform, environ=None, home=None):
    """The folder for TurboHUD's settings and log on this system."""
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
    """The placement, moved to the default spot on the largest screen if no part of its
    top edge is on any screen (for example after a monitor was unplugged). `screens` are
    (x, y, width, height) boxes; with none known, the placement is kept."""
    x, y, width, height = placement
    for sx, sy, sw, sh in screens:
        if sy <= y < sy + sh and x < sx + sw and x + width > sx:
            return placement
    if not screens:
        return placement
    sx, sy = max(screens, key=lambda s: s[2] * s[3])[:2]
    return (sx + DEFAULT_PLACEMENT[0], sy + DEFAULT_PLACEMENT[1], width, height)


def preset_places(preset, names, screens):
    """{name: SectionPlace} to load from `preset`, for the sections in `names`: each on a
    screen (see fit_on_screens). A section the preset does not have stays out of it."""
    places = {}
    for name in names:
        place = preset.get(name)
        if place is not None:
            box = (place.x, place.y, place.width, place.height)
            x, y, width, height = fit_on_screens(box, screens)
            places[name] = replace(place, x=x, y=y, width=width, height=height)
    return places


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


def _sections(data, tint=False):
    """{name: SectionPlace} from the file; a broken entry is left out (it then starts
    at its default place). `tint` is for a file from before each section had its own."""
    places = {}
    if not isinstance(data, dict):
        return places
    for name, entry in data.items():
        if not isinstance(entry, dict):
            continue
        try:
            x, y, width, height = (int(entry[key]) for key in ('x', 'y', 'width', 'height'))
        except (KeyError, TypeError, ValueError):
            continue
        if width < MIN_SECTION_SIZE or height < MIN_SECTION_SIZE:
            continue
        group = entry.get('group', '')
        group = group if group in GROUPS else ''
        places[str(name)] = SectionPlace(
            x,
            y,
            width,
            height,
            entry.get('visible', True) is not False,
            group,
            entry.get('text_centred') is True,
            entry.get('tint', tint) is True,
        )
    return places


def _presets(data, tint=False):
    """{number: sections} from the file; an empty or unknown preset is left out."""
    if not isinstance(data, dict):
        return {}
    kept = {number: _sections(data.get(str(number)), tint) for number in PRESETS}
    return {number: sections for number, sections in kept.items() if sections}


def _section_data(sections):
    return {
        name: {
            'x': place.x,
            'y': place.y,
            'width': place.width,
            'height': place.height,
            'visible': place.visible,
            'group': place.group,
            'text_centred': place.text_centred,
            'tint': place.tint,
        }
        for name, place in sections.items()
    }


def _layout_version(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 1 else 1


def load_settings(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    return Settings(
        placement=_placement(data.get('placement')),
        theme=_theme(data.get('theme')),
        sections=_sections(data.get('sections'), data.get('backdrop') is True),
        speed_unit=data.get('speed_unit') if data.get('speed_unit') in SPEED_UNITS else 'kmh',
        backdrop=data.get('backdrop') is True,
        map_others=data.get('map_others') is True,
        layout_version=_layout_version(data.get('layout_version')),
        presets=_presets(data.get('presets'), data.get('backdrop') is True),
    )


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
        'speed_unit': settings.speed_unit,
        'backdrop': settings.backdrop,
        'map_others': settings.map_others,
        'layout_version': settings.layout_version,
        'sections': _section_data(settings.sections),
        'presets': {str(number): _section_data(kept) for number, kept in settings.presets.items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)
