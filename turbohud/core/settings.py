"""TurboHUD's settings: where they live on each system, and reading and writing them.

Settings are one JSON file in the user's settings folder. Reading never fails: a missing,
broken or partly wrong file gives the defaults for whatever is missing or wrong.
"""

import json
import math
import os
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

from turbohud.core.class_registry import CLASS_TAGS, MAX_CLASS_TAG, class_tag

COLOUR_BLIND_MODES = ('off', 'all', 'chosen')  # Settings.colour_blind (hud.COLOUR_BLIND_MODES)

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
# 2: a text section's box fits closely round its text; 3: 20 lap times; 4: the track map's
# dark square is its tint (on), where its saved tint meant nothing before; 5: the last and
# best lap has sector bars below its text; 6: text sections have a text size (their own, or the
# global one), and the box follows it; 7: the standings and nearby cars narrower (closer columns);
# 8: nearby cars 4 rows tall where its short list is on (the default since 2026-11-15)
LAYOUT_VERSION = 8
FONT_LIMITS = (6, 120)  # text sizes in pixels (core.hud.FONT_SIZES)
DEFAULT_FONT = 13  # core.hud.DEFAULT_FONT
_COLOR = re.compile(r'#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?')


@dataclass(frozen=True)
class Theme:
    text_color: str = '#ffffff'
    accent_color: str = '#ffd65a'
    outline_color: str = '#000000c8'  # #rrggbbaa: the dark edge that keeps text readable
    scale: float = 1.0  # size of everything the HUD draws


BLUE_SECONDS = (1.0, 10.0, 0.5)  # the blue flag's warning time: least, most, step
RADAR_SECONDS = (0.2, 3.0, 0.1)  # the proximity radar's
READS_PER_SECOND = (20, 10, 5)  # how often a race may be read; fewer ask less of the game
GROUPS = ('A', 'B', 'C', 'D', 'E', 'F', 'G')  # section groups (E to G since 2026-11-15); '' is none
PRESETS = (1, 2, 3, 4, 5)  # the layouts a player can keep (5 since 2026-11-15, asked for by players)
PRESET_NAME_MOST = 24  # letters in a preset's name, such as "Race" or "Recordings"
# The kinds of event a preset can load for by itself as one begins (asked for by players on
# 2026-11-15; Spectating since 2026-11-19, asked for by the user: a layout to watch a race online
# apart from a replay's): (key, what the settings call it). turbohud.core.race.event_mode tells them apart.
EVENT_MODES = (
    ('recording', 'Recording'),
    ('spectating', 'Spectating'),
    ('hotlapping', 'Hotlapping'),
    ('race', 'Race'),
    ('special', 'Special event'),
)


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
    tint: bool = False  # a light tint behind its text while locked; for the track map, its dark square
    font: int | None = None  # a text section's own text size in pixels; None: the global one
    spacing: float = 1.0  # the room between its rows, as a share of the usual (core.hud.SPACINGS)
    # The Standings' columns shown (LAP_COLUMNS), kept with its place so each preset has its own
    # (asked for by the user on 2026-11-20); None: not kept (other sections, older presets).
    columns: tuple | None = None
    # A text section's own font (asked for by the user on 2026-11-20): a family from
    # customization/fonts or the system's, '' for the system font; None: the global one
    # (Settings.font_family). Kept with its place, so presets and layout files keep it.
    family: str | None = None


FAMILY_MOST = 100  # the most letters a font family's name has in the settings file


def font_family_value(value):
    """A font family from a file: a name ('' the system font), or None where there is none."""
    if not isinstance(value, str):
        return None
    return value.strip()[:FAMILY_MOST]


# The clan tags that name a car class, for a multi-class race: turbohud.core.class_registry.
# The settings file can have its own list (`class_tags`); it is saved only when it differs.
# Before the categories (2026-11-12) every settings file was saved with this list: such a file
# reads as the registry's.
OLD_CLASS_TAGS = (
    'LMP', 'LMP1', 'LMP2', 'LMP3', 'LMH', 'LMDH', 'HYPER', 'GTP', 'DPI',
    'GT1', 'GT2', 'GT3', 'GT4', 'GTE', 'GTLM', 'GTD', 'GTC', 'GTS', 'TCR', 'CUP',
    'F1', 'F2', 'F3', 'F4', 'PRO', 'AM', 'PROAM', 'SILV',
)  # fmt: skip


# The lap times' columns one can turn off (asked for by the user on 2026-11-12): the flag, the
# lap number, the tire compound, the best lap and the current lap; since 2026-11-15 also the gap
# to the leader, the class (the tag column in a multi-class race) and the overall place: every
# column but the place and the name. The settings file keeps those shown, in this order, and
# those it knew of (`lap_columns_known`), so a column added later shows until it is turned off.
LAP_COLUMNS = ('flag', 'lap', 'tyre', 'gap', 'best', 'current', 'class', 'overall')
FIRST_LAP_COLUMNS = ('flag', 'lap', 'tyre', 'best', 'current')  # a file without `lap_columns_known`


def _lap_columns(value, known=None):
    """The lap times' columns shown, from the settings file: all where there is no list; a column
    the file did not know of yet shows."""
    if not isinstance(value, list):
        return LAP_COLUMNS
    known = known if isinstance(known, list) else FIRST_LAP_COLUMNS
    return tuple(column for column in LAP_COLUMNS if column in value or column not in known)


def _names(value):
    """Section names from a saved list (colour_blind_sections), without anything else, each once."""
    if not isinstance(value, list):
        return ()
    return tuple(dict.fromkeys(name for name in value if isinstance(name, str) and name))


def _class_tags(value):
    """The class tags from the settings file, or CLASS_TAGS where there are none."""
    if not isinstance(value, list):
        return CLASS_TAGS
    tags = tuple(dict.fromkeys(class_tag(tag) for tag in value if 0 < len(class_tag(tag)) <= MAX_CLASS_TAG))
    if not tags or tags == OLD_CLASS_TAGS:
        return CLASS_TAGS
    return tags


def group_tint_default(platform=None):
    """One tint for each group before the player chose: on (the Mac, since 2026-11-15), but off on
    Windows, where it is a window of its own behind each group, until the user has seen it over TSU
    (asked for by the user on 2026-11-16, so no player gets it untried)."""
    return (sys.platform if platform is None else platform) != 'win32'


@dataclass(frozen=True)
class Settings:
    placement: tuple = DEFAULT_PLACEMENT  # the whole HUD before it had sections; new sections start here
    theme: Theme = field(default_factory=Theme)
    sections: dict = field(default_factory=dict)  # section name -> SectionPlace
    speed_unit: str = 'kmh'  # 'kmh' or 'mph'
    backdrop: bool = False  # every section with a tint has it on (see SectionPlace.tint)
    # One tint behind each group's tinted sections, the room between them too, while locked: on the Mac's
    # one window (asked for by the user on 2026-11-15) and, since 2026-11-16, a window behind each group on
    # Windows. Its default by system: group_tint_default.
    group_tint: bool = field(default_factory=group_tint_default)
    grid: bool = (
        True  # move mode's grid on the main screen (a switch since 2026-11-16, asked for by the user)
    )
    map_others: bool = False  # the track map also shows the other cars, as faint grey dots
    # The compass's needle and N in a blue told apart with colour blindness, not red (asked for by the
    # user on 2026-11-20).
    compass_colourblind: bool = False
    # Colour-blind colours (asked for by the user on 2026-11-21): 'off', 'all' sections or those 'chosen'
    # (colour_blind_sections); never the blue and yellow flags (hud.colour_blind_for).
    colour_blind: str = 'off'
    colour_blind_sections: tuple = ()
    # The car sections' bars in TSU's own colours (asked for by the user on 2026-11-21: hud.LEGACY_BARS).
    legacy_colours: bool = False
    # The compass's north from the track's sun (TSU's sun sets in the west), not up on the track map
    # (asked for by the user on 2026-11-20; on by default).
    compass_sun: bool = True
    # Nearby cars shows only the leader, the car ahead, you and the car behind (asked for by players
    # on 2026-11-15, on by default); off: the 3 cars ahead and the 3 behind.
    nearby_short: bool = True
    radar_cone: bool = True  # the proximity radar shows the slipstream behind cars ahead
    radar_cockpit_only: bool = True  # the proximity radar only while the camera sits at the driver
    sector_bars: bool = True  # the sector bars below the last and best lap
    yellow_flags: bool = True  # the yellow flag section and the yellow rings on the track map
    gear: bool = True  # the Gear section: the engine sound's gear and revs (read only while on and shown)
    clan_tags: bool = True  # the lap times show each driver's clan tag, outside a multi-class race
    classes: bool = True  # the lap times grouped by class, from the drivers' clan tags (see class_tags)
    class_tags: tuple = CLASS_TAGS  # the clan tags that name a class (upper case, without brackets)
    lap_columns: tuple = LAP_COLUMNS  # the lap times' columns shown (see LAP_COLUMNS)
    layout_version: int = 1  # how to read the section sizes: LAYOUT_VERSION is the latest
    presets: dict = field(default_factory=dict)  # number (one of PRESETS) -> a kept `sections`
    preset_names: dict = field(default_factory=dict)  # number -> the player's name for it; none: unnamed
    # Number -> the global font (font_family) the preset was saved with, loaded with it (asked for by
    # the user on 2026-11-20); none: a preset saved before, which leaves the font as it is.
    preset_fonts: dict = field(default_factory=dict)
    # Event mode (a key of EVENT_MODES) -> the preset loaded as such an event begins; none: off.
    auto_presets: dict = field(default_factory=dict)
    blue_seconds: float = 2.0  # how far behind a car about to lap the player shows the blue flag
    radar_seconds: float = 0.5  # how far ahead or behind a car shows the proximity radar
    # How often a race is read and its sections updated (READS_PER_SECOND); 10 by default since
    # 2026-11-15 (asked for by the user): smooth enough, and half the work for the game.
    reads_per_second: int = 10
    font_size: int = DEFAULT_FONT  # the global text size in pixels, for text sections without their own
    # The HUD's font: a family from customization/fonts (core.fonts), '' for the system's.
    font_family: str = ''
    # The digest of the layout file from customization/display_presets last taken at a start: a file is
    # taken once each time it is new or has changed (turbohud.core.presets.custom_for).
    applied_preset: str = ''


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
    screen (see fit_on_screens). A section the preset does not have stays out of it. The Standings
    of a preset saved before presets kept its columns gets every column, TurboHUD's default, not
    the columns another preset left (reported by the user on 2026-11-20)."""
    places = {}
    for name in names:
        place = preset.get(name)
        if place is not None:
            box = (place.x, place.y, place.width, place.height)
            x, y, width, height = fit_on_screens(box, screens)
            places[name] = replace(place, x=x, y=y, width=width, height=height)
            if name == 'laptimes' and place.columns is None:
                places[name] = replace(places[name], columns=LAP_COLUMNS)
    return places


PRESET_MATCH_PIXELS = 2  # how far a section may be off a preset's place and still count as there


def _same_place(a, b):
    """Whether two SectionPlaces are the same, the box within PRESET_MATCH_PIXELS (a desktop may
    report a moved window a pixel off)."""
    boxes = ((a.x, b.x), (a.y, b.y), (a.width, b.width), (a.height, b.height))
    if any(abs(one - other) > PRESET_MATCH_PIXELS for one, other in boxes):
        return False
    if b.columns is None:
        b = replace(b, columns=a.columns)  # a preset kept without its columns: any count
    return replace(a, x=b.x, y=b.y, width=b.width, height=b.height) == b


def current_preset(sections, presets, screens, last=None, fonts=None, family=''):
    """(number, changed): the preset the layout `sections` {name: SectionPlace} is in now (asked
    for by the user on 2026-11-19: which preset move mode shows), or None. A preset whose every
    section is where `sections` has it, as loading it would put them (preset_places), counts, `last`
    (the preset loaded or saved last) first; else `last`, changed since, where it is still kept.
    A preset that keeps a global font (`fonts` {number: family}) counts only with `family`, the
    global font now."""
    fonts = fonts or {}
    order = ([last] if last in presets else []) + [number for number in sorted(presets) if number != last]
    for number in order:
        if fonts.get(number, family) != family:
            continue
        places = preset_places(presets[number], sections, screens)
        if places and all(_same_place(sections[name], place) for name, place in places.items()):
            return number, False
    if last in presets:
        return last, True
    return None


def preset_shown(current, names):
    """How move mode's panel names the preset in use (current_preset): "Preset: 3 Race", with
    "(changed)" after it where the layout has moved on, or "Preset: none"."""
    if current is None:
        return 'Preset: none'
    number, changed = current
    text = f'Preset: {preset_label(number, names)}'
    return f'{text} (changed)' if changed else text


START_MODE = 'race'  # the kind of event whose preset is also the layout TurboHUD starts with


def start_preset(settings):
    """The preset TurboHUD puts the sections in as it starts, or None: the one chosen for a race
    (Layouts > Load by itself), where it is saved (asked for by the user on 2026-11-19: the Race
    preset is the default one). None keeps the layout as it was at the last quit."""
    number = settings.auto_presets.get(START_MODE)
    return number if number in settings.presets else None


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
            _font(entry.get('font')),
            _spacing(entry.get('spacing')),
            _columns(entry.get('columns')),
            font_family_value(entry.get('family')),
        )
    return places


def _columns(value):
    """The Standings' columns from the file (SectionPlace.columns), in LAP_COLUMNS' order; None
    where there is no list. Unknown columns are left out; an empty list is every one off."""
    if not isinstance(value, list):
        return None
    return tuple(column for column in LAP_COLUMNS if column in value)


def _spacing(value):
    """A line spacing from the file, from none to three times the usual; 1 where there is none."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or math.isnan(value):
        return 1.0
    return min(max(float(value), 0.0), 3.0)


def _font(value):
    """A text size from the file, within FONT_LIMITS; None where there is none."""
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return min(max(value, FONT_LIMITS[0]), FONT_LIMITS[1])


def _presets(data, tint=False):
    """{number: sections} from the file; an empty or unknown preset is left out."""
    if not isinstance(data, dict):
        return {}
    kept = {number: _sections(data.get(str(number)), tint) for number in PRESETS}
    return {number: sections for number, sections in kept.items() if sections}


def _preset_fonts(data):
    """{number: font family} from the file; an unknown number or no name is left out."""
    if not isinstance(data, dict):
        return {}
    fonts = {number: font_family_value(data.get(str(number))) for number in PRESETS}
    return {number: family for number, family in fonts.items() if family is not None}


def preset_name(value):
    """A preset's name as kept: one line, no spaces round it, at most PRESET_NAME_MOST letters."""
    if not isinstance(value, str):
        return ''
    return ' '.join(value.split())[:PRESET_NAME_MOST].strip()


def _preset_names(data):
    """{number: name} from the file; an empty or unknown one is left out."""
    if not isinstance(data, dict):
        return {}
    names = {number: preset_name(data.get(str(number))) for number in PRESETS}
    return {number: name for number, name in names.items() if name}


def _auto_presets(data):
    """{event mode: preset number} from the file; an unknown mode or number is left out."""
    if not isinstance(data, dict):
        return {}
    return {
        mode: data[mode]
        for mode, _label in EVENT_MODES
        if data.get(mode) in PRESETS and not isinstance(data.get(mode), bool)
    }


def preset_label(number, names):
    """How the app names preset `number`: "3 Race" with a name in `names`, else "3"."""
    name = names.get(number, '')
    return f'{number} {name}' if name else str(number)


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
            **({'font': place.font} if place.font is not None else {}),
            **({'spacing': place.spacing} if place.spacing != 1.0 else {}),
            **({'columns': list(place.columns)} if place.columns is not None else {}),
            **({'family': place.family} if place.family is not None else {}),
        }
        for name, place in sections.items()
    }


def _seconds(value, default, limits):
    """A warning time from the file, within its `limits`; `default` if it is no number."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or math.isnan(value):
        return default
    return min(max(float(value), limits[0]), limits[1])


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
        group_tint=data['group_tint'] if isinstance(data.get('group_tint'), bool) else group_tint_default(),
        grid=data.get('grid') is not False,
        map_others=data.get('map_others') is True,
        compass_colourblind=data.get('compass_colourblind') is True,
        colour_blind=data.get('colour_blind') if data.get('colour_blind') in COLOUR_BLIND_MODES else 'off',
        colour_blind_sections=_names(data.get('colour_blind_sections')),
        legacy_colours=data.get('legacy_colours') is True,
        compass_sun=data.get('compass_sun') is not False,
        nearby_short=data.get('nearby_short') is not False,
        radar_cone=data.get('radar_cone') is not False,
        radar_cockpit_only=data.get('radar_cockpit_only') is not False,
        sector_bars=data.get('sector_bars') is not False,
        yellow_flags=data.get('yellow_flags') is not False,
        gear=data.get('gear') is not False,
        classes=data.get('classes') is not False,
        clan_tags=data.get('clan_tags') is not False,
        class_tags=_class_tags(data.get('class_tags')),
        lap_columns=_lap_columns(data.get('lap_columns'), data.get('lap_columns_known')),
        layout_version=_layout_version(data.get('layout_version')),
        presets=_presets(data.get('presets'), data.get('backdrop') is True),
        preset_names=_preset_names(data.get('preset_names')),
        preset_fonts=_preset_fonts(data.get('preset_fonts')),
        auto_presets=_auto_presets(data.get('auto_presets')),
        blue_seconds=_seconds(data.get('blue_seconds'), Settings.blue_seconds, BLUE_SECONDS),
        radar_seconds=_seconds(data.get('radar_seconds'), Settings.radar_seconds, RADAR_SECONDS),
        reads_per_second=(
            data['reads_per_second']
            if data.get('reads_per_second') in READS_PER_SECOND
            else Settings.reads_per_second
        ),
        font_size=_font(data.get('font_size')) or DEFAULT_FONT,
        font_family=data.get('font_family') if isinstance(data.get('font_family'), str) else '',
        applied_preset=data.get('applied_preset') if isinstance(data.get('applied_preset'), str) else '',
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
        'group_tint': settings.group_tint,
        'grid': settings.grid,
        'map_others': settings.map_others,
        'compass_colourblind': settings.compass_colourblind,
        'colour_blind': settings.colour_blind,
        'colour_blind_sections': list(settings.colour_blind_sections),
        'legacy_colours': settings.legacy_colours,
        'compass_sun': settings.compass_sun,
        'nearby_short': settings.nearby_short,
        'radar_cone': settings.radar_cone,
        'radar_cockpit_only': settings.radar_cockpit_only,
        'sector_bars': settings.sector_bars,
        'yellow_flags': settings.yellow_flags,
        'gear': settings.gear,
        'classes': settings.classes,
        'clan_tags': settings.clan_tags,
        'lap_columns': list(settings.lap_columns),
        'lap_columns_known': list(LAP_COLUMNS),
        'layout_version': settings.layout_version,
        'blue_seconds': settings.blue_seconds,
        'radar_seconds': settings.radar_seconds,
        'reads_per_second': settings.reads_per_second,
        'font_size': settings.font_size,
        'font_family': settings.font_family,
        'applied_preset': settings.applied_preset,
        'sections': _section_data(settings.sections),
        'presets': {str(number): _section_data(kept) for number, kept in settings.presets.items()},
        'preset_names': {str(number): name for number, name in settings.preset_names.items()},
        'preset_fonts': {str(number): family for number, family in settings.preset_fonts.items()},
        'auto_presets': dict(settings.auto_presets),
    }
    if settings.class_tags != CLASS_TAGS:  # else the registry's, which may grow
        data['class_tags'] = list(settings.class_tags)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)
