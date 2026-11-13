"""Layout presets as files, and fitting a layout made for one screen size to another.

A preset file holds a layout: where each section sits on the screen (from its top left corner),
its size, text size and options, and the size of the screen it was made for. Nothing personal: it
can be shared, and TurboHUD ships one per common screen size (assets/presets). Asked for by the
user on 2026-11-13: defaults for 1920x1080, 2560x1440, 2560x1600, 3840x2160 and 5120x1440, made
from their own 5120x1440 layout, and presets of one's own to make and share.

Fitting keeps the order of the sections (`fit_layout`): they scale by the ratio of the screens'
heights, so text keeps its proportion to the screen, and the empty room between them is shared
out on each axis, so a section near an edge stays near it and none that were apart come to
overlap. Only where the sections would not fit side by side even without room between them (a
wide screen's layout on a narrow one) are they scaled smaller, as little as needs be.
"""

import json
from dataclasses import replace
from pathlib import Path

from turbohud.core.hud import FONT_SIZES, is_text_section, text_box
from turbohud.core.settings import SectionPlace, _font, _sections, _spacing

FORMAT = 1  # the preset file's format, written into it
SCREENS = ((1920, 1080), (2560, 1440), (2560, 1600), (3840, 2160), (5120, 1440))  # shipped ones


def file_name(size):
    """The shipped preset's file name for a screen `size` (width, height)."""
    return f'{size[0]}x{size[1]}.json'


def preset_data(places, size, font_size):
    """A preset file's data: `places` {name: SectionPlace} on a screen of `size` (width, height),
    at its top left (0, 0). Each text section's text size is written out (a section following the
    global one gets `font_size`), so the file stands on its own."""
    return {
        'format': FORMAT,
        'screen': list(size),
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
    return tuple(screen), places


def load_file(path):
    """read_preset of a .json file; None where it cannot be read or is no preset."""
    try:
        return read_preset(json.loads(Path(path).read_text(encoding='utf-8')))
    except (OSError, ValueError):
        return None


def save_file(path, places, size, font_size):
    """Write a preset file (preset_data), whole or not at all."""
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(preset_data(places, size, font_size), indent=2) + '\n', encoding='utf-8')
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
    return result


def nearest(size, available):
    """Of the screen sizes `available`, the one to fit a layout for `size` from: the same, else the
    one of the nearest shape (width to height), then the nearest height."""
    if not available:
        return None
    if tuple(size) in available:
        return tuple(size)
    shape = size[0] / size[1]
    return min(available, key=lambda s: (abs(s[0] / s[1] - shape), abs(s[1] - size[1])))


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
        return places
    return fit_layout(places, made_for, size, sections, measure, ink)


def kept_sections(places, known):
    """`places` without sections TurboHUD does not have (a file from a newer version)."""
    return {name: place for name, place in places.items() if name in known}


__all__ = [
    'FORMAT',
    'SCREENS',
    'SectionPlace',
    'absolute',
    'default_for',
    'file_name',
    'fit_layout',
    'kept_sections',
    'load_file',
    'nearest',
    'preset_data',
    'read_preset',
    'relative',
    'save_file',
    'shipped',
]
