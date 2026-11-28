"""Layout presets as files, and fitting a layout made for one screen size to another.

A preset file holds a layout: where each section sits on the screen (from its top left corner),
its size, text size and options, and the size of the screen it was made for. Nothing personal: it
can be shared, and TurboHUD ships one per common screen size (assets/presets). Asked for by the
user on 2026-11-13: defaults for 1920x1080, 2560x1440, 2560x1600, 3840x2160 and 5120x1440, made
from their own 5120x1440 layout, and presets of one's own to make and share. On 2026-11-15 made
again from their newer layout, with 2294x1490 (a Mac's) added.

Fitting keeps the order of the sections (`fit_layout`): they scale by the ratio of the screens'
heights, so text keeps its proportion to the screen, and the empty room between them is shared
out on each axis, so a section near an edge stays near it and none that were apart come to
overlap. Only where the sections would not fit side by side even without room between them (a
wide screen's layout on a narrow one) are they scaled smaller, as little as needs be.
"""

import hashlib
import json
import os
import shutil
import sys
from dataclasses import replace
from pathlib import Path

from turbohud.core.hud import FONT_SIZES, is_text_section, text_box
from turbohud.core.settings import SectionPlace, _font, _sections, _spacing, font_family_value

FORMAT = 1  # the preset file's format, written into it
# The shipped ones (assets/presets); 2294x1490, a Mac's, since 2026-11-15 (asked for by the user).
SCREENS = ((1920, 1080), (2294, 1490), (2560, 1440), (2560, 1600), (3840, 2160), (5120, 1440))


def file_name(size):
    """The shipped preset's file name for a screen `size` (width, height)."""
    return f'{size[0]}x{size[1]}.json'


def preset_data(places, size, font_size, family=''):
    """A preset file's data: `places` {name: SectionPlace} on a screen of `size` (width, height),
    at its top left (0, 0). Each text section's text size is written out (a section following the
    global one gets `font_size`), so the file stands on its own. So is the global font `family`
    where it is not the system's: read_preset gives it to the sections without a font of their own."""
    return {
        'format': FORMAT,
        'screen': list(size),
        **({'font_family': family} if family else {}),
        'sections': {
            name: {
                'x': place.x,
                'y': place.y,
                'width': place.width,
                'height': place.height,
                'visible': place.visible,
                'group': place.group,
                'text_centred': place.text_centred,
                'tint': place.tint,
                'font': place.font if place.font is not None else font_size,
                'spacing': place.spacing,
                **({'columns': list(place.columns)} if place.columns is not None else {}),
                **({'family': place.family} if place.family is not None else {}),
            }
            for name, place in places.items()
        },
    }


def read_preset(data):
    """(screen size, {name: SectionPlace}) from a preset file's data; None where it is not one.
    A broken section is left out, as in the settings file."""
    if not isinstance(data, dict) or data.get('format') != FORMAT:
        return None
    screen = data.get('screen')
    if not (
        isinstance(screen, list)
        and len(screen) == 2
        and all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in screen)
    ):
        return None
    places = _sections(data.get('sections'))
    if not places:
        return None
    for name, entry in data['sections'].items():
        if name in places and isinstance(entry, dict):
            places[name] = replace(
                places[name], font=_font(entry.get('font')), spacing=_spacing(entry.get('spacing'))
            )
    # The global font the file was made with: the font of each section without its own, so it
    # looks as made, and the player's own global font is left as it is.
    made_in = font_family_value(data.get('font_family'))
    if made_in:
        places = {
            name: replace(place, family=made_in) if place.family is None else place
            for name, place in places.items()
        }
    return tuple(screen), places


def load_file(path):
    """read_preset of a .json file; None where it cannot be read or is no preset."""
    try:
        return read_preset(json.loads(Path(path).read_text(encoding='utf-8')))
    except (OSError, ValueError):
        return None


def save_file(path, places, size, font_size, family=''):
    """Write a preset file (preset_data), whole or not at all."""
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    data = preset_data(places, size, font_size, family)
    temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def relative(places, screen):
    """`places` moved so that `screen` (x, y, width, height)'s top left is (0, 0)."""
    return {name: replace(p, x=p.x - screen[0], y=p.y - screen[1]) for name, p in places.items()}


def absolute(places, screen):
    """`places` (from a screen's top left) moved onto `screen` (x, y, width, height)."""
    return {name: replace(p, x=p.x + screen[0], y=p.y + screen[1]) for name, p in places.items()}


def _axis(spans, total, new_total, scale):
    """A mapping of one axis of a screen `total` long onto one `new_total` long, and the scale the
    sections get on it: the stretches the sections cover (`spans`, (start, end) each) keep their
    order and are scaled by `scale`, at most as much as fits, and the empty stretches between them
    share what room is left. So sections near an edge stay near it, and none that were apart come
    to overlap. Returns (map(position) -> new position, the scale)."""
    covered = []
    for start, end in sorted((max(a, 0), min(b, total)) for a, b in spans if b > a):
        if covered and start <= covered[-1][1]:
            covered[-1][1] = max(covered[-1][1], end)
        else:
            covered.append([start, end])
    occupied = sum(end - start for start, end in covered)
    if occupied > 0:
        scale = min(scale, new_total / occupied)
    empty = total - occupied
    gap = (new_total - occupied * scale) / empty if empty > 0 else 0.0

    def mapped(position):
        new, at = 0.0, 0.0
        for start, end in covered:
            if position <= start:
                return new + (position - at) * gap
            new += (start - at) * gap
            if position <= end:
                return new + (position - start) * scale
            new += (end - start) * scale
            at = end
        return new + (position - at) * gap

    return mapped, scale


def _overlaps(boxes):
    """The pairs of shown sections whose boxes overlap: {(name, name)}."""
    found = set()
    names = sorted(boxes)
    for i, a in enumerate(names):
        ax, ay, aw, ah = boxes[a]
        for b in names[i + 1 :]:
            bx, by, bw, bh = boxes[b]
            if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                found.add((a, b))
    return found


def fit_layout(places, from_size, to_size, sections, measure, ink):
    """`places` {name: SectionPlace} made for a screen of `from_size` fitted to one of `to_size`
    (both from the screen's top left), see the module's notes: the sections scaled by the ratio of
    the heights (less where they would not fit), the room between them shared out. `sections`
    {name: hud.Section}; `measure` and `ink` as for hud.text_box. Text sections get whole text
    sizes, at least the smallest; a section TurboHUD does not know keeps its place, scaled."""
    shown = [p for p in places.values() if p.visible] or list(places.values())
    scale = to_size[1] / from_size[1]
    across = [(p.x, p.x + p.width) for p in shown]
    down = [(p.y, p.y + p.height) for p in shown]
    _map, scale = _axis(across, from_size[0], to_size[0], scale)
    _map, scale = _axis(down, from_size[1], to_size[1], scale)
    map_x, _ = _axis(across, from_size[0], to_size[0], scale)
    map_y, _ = _axis(down, from_size[1], to_size[1], scale)
    # Room left over once the sections are scaled less than the screen (the width set the scale):
    # shared out by where each section is, so one at the bottom (right) edge stays there and one in
    # the middle stays in the middle; never so that sections that were apart overlap.
    spare_x = max(to_size[0] - map_x(from_size[0]), 0)
    spare_y = max(to_size[1] - map_y(from_size[1]), 0)
    result = {}
    for name, place in places.items():
        section = sections.get(name)
        if section is not None and is_text_section(section) and place.font is not None:
            font = min(max(round(place.font * scale), FONT_SIZES[0]), FONT_SIZES[1])
            box = (0, 0, round(place.width * scale), round(place.height * scale))
            _x, _y, width, height = text_box(section, box, font, measure, ink)
        else:
            font = place.font
            width, height = max(round(place.width * scale), 1), max(round(place.height * scale), 1)
        share_x = min(max((place.x + place.width / 2) / from_size[0], 0.0), 1.0)
        share_y = min(max((place.y + place.height / 2) / from_size[1], 0.0), 1.0)
        x = round(min(max(map_x(place.x) + spare_x * share_x, 0), max(to_size[0] - width, 0)))
        y = round(min(max(map_y(place.y) + spare_y * share_y, 0), max(to_size[1] - height, 0)))
        result[name] = replace(place, x=x, y=y, width=width, height=height, font=font)
    return readable_nearby(result, to_size, sections, measure, ink)


def readable_nearby(places, size, sections, measure, ink):
    """`places` with Nearby cars' text at least as large as the Standings' (a player found it too
    small at 1920x1080 on 2026-11-15; kept for every fitted layout on 2026-11-20, as the user's own
    layout has it smaller, which fitted down gave 8 px). Its box is made for the larger text and
    grows upwards, its bottom edge kept (in the user's layout the lap times sit right below it at
    the screen's bottom), and the sections stacked right above it in its column move up as much."""
    nearby, standings, section = places.get('players'), places.get('laptimes'), sections.get('players')
    if nearby is None or standings is None or section is None:
        return places
    if nearby.font is None or standings.font is None or nearby.font >= standings.font:
        return places
    box = (nearby.x, nearby.y, nearby.width, nearby.height)
    _x, _y, width, height = text_box(section, box, standings.font, measure, ink, keep_width=False)
    x = min(nearby.x, max(size[0] - width, 0))

    def beside(place):
        return place.visible and place.x < x + width and x < place.x + place.width

    others = {name: place for name, place in places.items() if name != 'players'}
    # Its bottom edge: where it was, or the top of the section right below it, whichever is higher.
    below = [p.y for p in others.values() if beside(p) and p.y >= nearby.y + nearby.height / 2]
    bottom = min([nearby.y + nearby.height, size[1], *below])
    y = max(bottom - height, 0)
    raised = max(nearby.y - y, 0)
    result = {**places, 'players': replace(nearby, x=x, y=y, width=width, height=height, font=standings.font)}
    for name, place in others.items():
        if beside(place) and place.y < nearby.y <= place.y + place.height + STACKED:
            result[name] = replace(place, y=max(place.y - raised, 0))  # stacked right above it
    return result


STACKED = 4  # pixels a section may reach into the next below and still count as stacked on it


def nearest(size, available):
    """Of the screen sizes `available`, the one to fit a layout for `size` from: the same, else the
    one of the nearest shape (width to height), then the nearest height."""
    if not available:
        return None
    if tuple(size) in available:
        return tuple(size)
    shape = size[0] / size[1]
    return min(available, key=lambda s: (abs(s[0] / s[1] - shape), abs(s[1] - size[1])))


# The starting presets (asked for by the user on 2026-11-20): the user's presets 1 to 5, with their
# names and Load by itself choices, made for one screen (tools/make_layouts.py); a first start fits
# them to the player's screen (app.with_starting_presets). In a folder of their own, so `shipped`
# does not take the file for a layout.
STARTING_FOLDER = 'starting'
STARTING_FILE = f'{STARTING_FOLDER}/presets.json'


def starting_data(kept, size, font_size, names, auto_presets):
    """The starting presets file's data: `kept` {number: {name: SectionPlace}} on a screen of
    `size` from its top left, each as a layout file has it (preset_data), with the presets' `names`
    {number: name} and `auto_presets` {event mode: number}."""
    return {
        'format': FORMAT,
        'screen': list(size),
        'presets': {str(n): preset_data(kept[n], size, font_size)['sections'] for n in sorted(kept)},
        'names': {str(n): name for n, name in sorted(names.items()) if n in kept},
        'auto_presets': {mode: n for mode, n in auto_presets.items() if n in kept},
    }


def read_starting(path):
    """(screen size, {number: {name: SectionPlace}}, {number: name}, {mode: number}) from the starting
    presets file at `path` (starting_data); None where it is missing or broken. The names and choices
    are read as the settings file reads them."""
    from turbohud.core.settings import _auto_presets, _preset_names

    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get('presets'), dict):
        return None
    kept = {}
    for number, sections in data['presets'].items():
        found = read_preset(
            {'format': data.get('format'), 'screen': data.get('screen'), 'sections': sections}
        )
        if found is None or not number.isdigit():
            continue
        kept[int(number)] = found[1]
        size = found[0]
    if not kept:
        return None
    auto = {mode: n for mode, n in _auto_presets(data.get('auto_presets')).items() if n in kept}
    names = {n: name for n, name in _preset_names(data.get('names')).items() if n in kept}
    return size, kept, names, auto


def shipped(folder):
    """{screen size: (size, places)} of the preset files in `folder` (assets/presets)."""
    found = {}
    for path in sorted(Path(folder).glob('*.json')):
        preset = load_file(path)
        if preset is not None:
            found[preset[0]] = preset
    return found


def default_for(size, folder, sections, measure, ink):
    """{name: SectionPlace} for a screen of `size` from the shipped presets in `folder`: the one
    made for it, else the nearest fitted to it (fit_layout); None without any."""
    presets = shipped(folder)
    source = nearest(size, list(presets))
    if source is None:
        return None
    made_for, places = presets[source]
    if made_for == tuple(size):
        return on_screen(places, size)
    return fit_layout(places, made_for, size, sections, measure, ink)


def on_screen(places, size):
    """`places` each moved, where it sticks out, wholly onto a screen of `size` (from its top left)."""
    return {
        name: replace(
            p,
            x=min(max(p.x, 0), max(size[0] - p.width, 0)),
            y=min(max(p.y, 0), max(size[1] - p.height, 0)),
        )
        for name, p in places.items()
    }


DESIGN_ROOM = (0.94, 0.88)  # share of the screen's width and height a shrunken design frame may take


def design_frame(size, screen):
    """(the frame (x, y, width, height), its scale) that stands for a screen of `size` on `screen`
    (x, y, width, height), in the middle of it (the design screen, asked for by the user on
    2026-11-13: presets for screens one does not have). A size that fits on the screen, one's own
    among them, is shown at full size (100%, reported by users on 2026-11-15: their own size came
    out at 88%); a larger one is shrunk to fit within DESIGN_ROOM of it."""
    if size[0] <= screen[2] and size[1] <= screen[3]:
        scale = 1.0
    else:
        scale = min(screen[2] * DESIGN_ROOM[0] / size[0], screen[3] * DESIGN_ROOM[1] / size[1])
    width, height = round(size[0] * scale), round(size[1] * scale)
    return (screen[0] + (screen[2] - width) // 2, screen[1] + (screen[3] - height) // 2, width, height), scale


def into_frame(places, frame, scale):
    """`places` (from the designed screen's top left) shown in `frame` at `scale`: positions,
    sizes and text sizes scaled (text at least the smallest size)."""
    return {
        name: replace(
            p,
            x=frame[0] + round(p.x * scale),
            y=frame[1] + round(p.y * scale),
            width=max(round(p.width * scale), 1),
            height=max(round(p.height * scale), 1),
            font=None if p.font is None else max(round(p.font * scale), FONT_SIZES[0]),
        )
        for name, p in places.items()
    }


def out_of_frame(places, frame, scale, size):
    """`places` shown in `frame` at `scale` back at full size, from the designed screen's top left,
    each wholly on it (into_frame's reverse)."""
    full = {
        name: replace(
            p,
            x=round((p.x - frame[0]) / scale),
            y=round((p.y - frame[1]) / scale),
            width=max(round(p.width / scale), 1),
            height=max(round(p.height / scale), 1),
            font=None if p.font is None else min(max(round(p.font / scale), FONT_SIZES[0]), FONT_SIZES[1]),
        )
        for name, p in places.items()
    }
    return on_screen(full, size)


# Layouts of one's own, beside the app (asked for by the user on 2026-11-13: easy to find): Export,
# Import and Save design open it, and at every start a layout there for the screen's size is taken,
# once each time the file is new or has changed.
CUSTOM_FOLDER = Path('customization') / 'display_presets'
CUSTOM_README = 'README.txt'
# TurboHUD's own layouts, also in this folder (asked for by the user on 2026-11-15: in every build, to
# see and start from), under names of their own: unpacking a new version over an old one then never
# replaces a layout of the player's, and these files never put a layout over sections the player has
# already placed. They are written again from the shipped ones at each start (default_files).
DEFAULT_SUFFIX = ' (TurboHUD default).json'
CUSTOM_README_TEXT = """TurboHUD display presets

Put a TurboHUD layout file (.json) here, named after the screen size it is for, such as
2560x1440.json. When TurboHUD starts on a screen of that size, it takes that layout (once each
time the file is new or has changed, so moving sections afterwards sticks).

The files named like "2560x1440 (TurboHUD default).json" are the layouts TurboHUD comes with,
one per common screen size. On the first start, TurboHUD lays out the HUD as the one for your
screen's size (or the nearest, fitted). They never replace a layout of your own, and every new
version of TurboHUD writes them again, so to change one, save your layout under another name
(Export... in move mode does).

Export... in move mode saves the layout here; Import... loads one from here; Load screen default
puts back your own one here for your screen, or else the layout TurboHUD comes with.
"""


def app_folder(frozen=None, executable=None, source=None):
    """The folder TurboHUD was started from: the one holding TurboHUD.exe (or TurboHUD, or on the
    Mac the one holding TurboHUD.app) in the built app, the source folder otherwise."""
    frozen = getattr(sys, 'frozen', False) if frozen is None else frozen
    if not frozen:
        return Path(source) if source is not None else Path(__file__).resolve().parents[2]
    program = Path(executable or sys.executable).resolve()
    bundle = next((parent for parent in program.parents if parent.suffix == '.app'), None)
    return bundle.parent if bundle is not None else program.parent


def applications_folders(platform=sys.platform, home=None):
    """The Mac's Applications folders: an app there keeps its customization folder in the settings
    folder, as the Applications folder is no place for a player's files and an admin account can
    write to it (found on 2026-11-24: customization/ was made in /Applications). None elsewhere."""
    if platform != 'darwin':
        return ()
    return (Path('/Applications'), (Path(home) if home is not None else Path.home()) / 'Applications')


def in_applications(start, applications=None):
    """Whether the folder `start` is one of `applications` (applications_folders) or inside one."""
    applications = applications_folders() if applications is None else applications
    start = Path(start)
    return any(start == folder or folder in start.parents for folder in applications)


def custom_folder(settings_folder, start=None, applications=None):
    """customization/display_presets in the folder TurboHUD was started from (`start`, else
    app_folder()), or in `settings_folder` where that one cannot be written to or is a Mac's
    Applications folder (`applications`, else applications_folders())."""
    start = Path(start) if start is not None else app_folder()
    if os.access(start, os.W_OK) and not in_applications(start, applications):
        return start / CUSTOM_FOLDER
    return Path(settings_folder) / CUSTOM_FOLDER


def move_old_customization(settings_folder, start=None, applications=None):
    """Where an earlier TurboHUD made customization/ in a Mac's Applications folder (beside the
    app, before applications_folders): move the player's files in it to the settings folder's
    (custom_folder), a file of the same name there kept, and delete TurboHUD's own (read-mes, its
    default layouts, Finder's .DS_Store) and the folders left empty. The names of the files moved,
    with / between folders on every system."""
    start = Path(start) if start is not None else app_folder()
    old = start / CUSTOM_FOLDER.parent
    if not in_applications(start, applications) or not old.is_dir():
        return []
    new = Path(settings_folder) / CUSTOM_FOLDER.parent
    moved = []
    for path in sorted(old.rglob('*'), reverse=True):  # files before the folders holding them
        try:
            if path.is_dir():
                if not any(path.iterdir()):
                    path.rmdir()
            elif path.name in (CUSTOM_README, '.DS_Store') or is_default_file(path):
                path.unlink()
            else:
                target = new / path.relative_to(old)
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(path), str(target))
                    moved.append(path.relative_to(old).as_posix())
        except OSError:
            continue  # left where it is
    try:
        old.rmdir()
    except OSError:
        pass  # files the player keeps there
    return sorted(moved)


def ready_folder(folder):
    """Make `folder` (custom_folder) with its read-me where missing; the folder, or None where it
    cannot be made."""
    try:
        Path(folder).mkdir(parents=True, exist_ok=True)
        readme = Path(folder) / CUSTOM_README
        if not readme.exists():
            readme.write_text(CUSTOM_README_TEXT, encoding='utf-8')
    except OSError:
        return None
    return Path(folder)


def default_name(size):
    """The name of TurboHUD's own layout for a screen `size` in customization/display_presets."""
    return f'{size[0]}x{size[1]}{DEFAULT_SUFFIX}'


def is_default_file(path):
    """Whether `path` is one of TurboHUD's own layouts there (default_name), not the player's."""
    return Path(path).name.endswith(DEFAULT_SUFFIX)


def default_files(folder, shipped_folder):
    """Write TurboHUD's own layouts (the files in `shipped_folder`, assets/presets) into `folder`
    (customization/display_presets) as default_name files, where one is missing or differs (an
    older version's); the player's own files are never touched. The names written, or None where
    the folder cannot be written to."""
    if ready_folder(folder) is None:
        return None
    written = []
    for source in sorted(Path(shipped_folder).glob('*.json')):
        preset = load_file(source)
        if preset is None:
            continue
        target = Path(folder) / default_name(preset[0])
        try:
            data = source.read_bytes()
            if not target.exists() or target.read_bytes() != data:
                target.write_bytes(data)
                written.append(target.name)
        except OSError:
            return None
    return written


def custom_for(size, folder):
    """(the file's digest, {name: SectionPlace}) of the player's own layout made for exactly `size`
    among the files in `folder` (its name, else any file made for that size; TurboHUD's own
    default_name files do not count); None where there is none."""
    folder = Path(folder)
    named = folder / file_name(size)
    found = sorted(p for p in folder.glob('*.json') if p != named and not is_default_file(p))
    candidates = [named] + found if folder.is_dir() else []
    for path in candidates:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        try:
            preset = read_preset(json.loads(data.decode('utf-8')))
        except (UnicodeDecodeError, ValueError):
            continue
        if preset is not None and preset[0] == tuple(size):
            return hashlib.sha256(data).hexdigest(), preset[1]
    return None


def layout_for(size, folder, shipped_folder, sections, measure, ink):
    """{name: SectionPlace} for a screen of `size`: one's own layout for it in `folder`
    (custom_for), else the shipped one (default_for); None without either."""
    own = custom_for(size, folder) if folder is not None else None
    if own is not None:
        return on_screen(own[1], size)
    return default_for(size, shipped_folder, sections, measure, ink)


def kept_sections(places, known):
    """`places` without sections TurboHUD does not have (a file from a newer version)."""
    return {name: place for name, place in places.items() if name in known}


__all__ = [
    'CUSTOM_FOLDER',
    'DEFAULT_SUFFIX',
    'FORMAT',
    'SCREENS',
    'SectionPlace',
    'absolute',
    'app_folder',
    'applications_folders',
    'custom_folder',
    'custom_for',
    'default_files',
    'default_for',
    'default_name',
    'design_frame',
    'file_name',
    'fit_layout',
    'in_applications',
    'into_frame',
    'is_default_file',
    'kept_sections',
    'layout_for',
    'load_file',
    'move_old_customization',
    'nearest',
    'on_screen',
    'out_of_frame',
    'preset_data',
    'read_preset',
    'ready_folder',
    'relative',
    'save_file',
    'shipped',
]
