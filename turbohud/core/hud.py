"""What the HUD shows and where, as plain data that turbohud.hud draws."""

from dataclasses import dataclass

MARGIN = 14  # space between the box's edge and the text, before scaling
MIN_WIDTH = 380  # the last and best lap line fits at scale 1


@dataclass(frozen=True)
class Line:
    text: str
    size: int  # font size in pixels
    color: str  # 'text' or 'accent', a colour from the theme
    baseline: int  # y of the text's baseline, from the box's top
    tail: str = ''  # more text right after it, in its own colour
    tail_color: str = 'text'


@dataclass(frozen=True)
class Row:
    """One line of HUD content, before layout."""

    text: str
    style: str  # 'title', 'big', 'medium' or 'small': a font size from Sizes
    color: str = 'text'  # 'text', 'accent', 'ahead' (green) or 'behind' (red)
    tail: str = ''  # more text right after it, in its own colour
    tail_color: str = 'text'


@dataclass(frozen=True)
class Sizes:
    """Font sizes and gaps in pixels for one theme scale."""

    margin: int
    title: int
    big: int
    medium: int
    small: int
    gap: int  # between content rows
    hint_gap: int  # between the content and the hint, and between hint lines

    @classmethod
    def for_scale(cls, scale):
        def scaled(value):
            return max(1, round(value * scale))

        return cls(scaled(MARGIN), scaled(16), scaled(40), scaled(20), scaled(13), scaled(8), scaled(6))


def clock(seconds):
    """'m:ss' for a number of seconds, like a lap time."""
    minutes, seconds = divmod(int(seconds), 60)
    return f'{minutes}:{seconds:02d}'


def local_time_rows(now):
    """The local time of day, 'HH:MM' (24 hours), from a time.struct_time."""
    return [Row(f'{now.tm_hour:02d}:{now.tm_min:02d}', 'medium')]


def session_rows(seconds):
    """The content without game data: how long TurboHUD has been running."""
    return [Row('TurboHUD - session time', 'title'), Row(clock(seconds), 'big', 'accent')]


def help_lines(shortcuts):
    """The move-mode hint, as lines, for the move-mode panel."""
    finish = 'Ctrl+Shift+L or Lock finishes.' if shortcuts else 'Lock finishes.'
    return ['Drag a section to move it. At its corner: taller or shorter scales', 'the text, wider makes room for it.', finish]


def _content(rows, sizes):
    """(lines, bottom baseline) for content rows laid out from the top."""
    lines, baseline = [], sizes.margin
    for index, row in enumerate(rows):
        size = getattr(sizes, row.style)
        baseline += (sizes.gap if index else 0) + size
        lines.append(Line(row.text, size, row.color, baseline, row.tail, row.tail_color))
    return lines, baseline


def hud_lines(rows, scale=1.0):
    """The lines of a section's content `rows`, top to bottom."""
    return _content(rows, Sizes.for_scale(scale))[0]


def content_size(rows, scale, measure):
    """(width, height) a section needs for `rows` at `scale`. `measure(text, size)` gives
    a text's width in pixels (Qt knows the font)."""
    sizes = Sizes.for_scale(scale)
    lines, bottom = _content(rows, sizes)
    width = max((measure(line.text + line.tail, line.size) for line in lines), default=0)
    # Below the last baseline: room for letters such as g and p, then the margin.
    return round(width + 2 * sizes.margin), round(bottom + sizes.margin)


@dataclass(frozen=True)
class Section:
    """One part of the HUD in its own window, placed by the player."""

    name: str  # its key in settings.json
    label: str  # how menus and move mode name it
    samples: tuple  # row lists it may show; the widest and tallest sets its size


RACE_SECTIONS = (
    Section('lap', 'Lap and time left', (
        (Row('Lap 13/13  -  21:00 left', 'title'),),
        (Row('Waiting for TSU (launch option)', 'title'),),
    )),
    Section('current', 'Running lap', ((Row('0:00.0', 'big'),), (Row('10:00.000', 'big'),))),
    Section('delta', 'Delta to best', ((Row('+00.000 vs best', 'medium'),),)),
    Section('times', 'Last and best lap', ((Row('Last 0:00.000   Best 0:00.000', 'medium'),),)),
    Section('fuel', 'Fuel', ((Row('Fuel 100.0%', 'medium', tail='  ~10.0 laps'),),)),
    Section('tires', 'Tires', ((Row('Tires 100%  ~10.0 laps', 'medium'),),)),
    Section('speed', 'Speed', ((Row('000 km/h', 'medium'),),)),
    Section('localtime', 'Local time', ((Row('00:00', 'medium'),),)),
)
CLOCK_SECTIONS = (
    Section('clock', 'Session time', ((Row('TurboHUD - session time', 'title'), Row('00:00', 'big')),)),
    Section('localtime', 'Local time', ((Row('00:00', 'medium'),),)),
)


def base_size(section, scale, measure):
    """(width, height) of a section at scale 1 of its own: as wide as its usual content
    (the first sample) and as tall as its tallest."""
    sizes = [content_size(rows, scale, measure) for rows in section.samples]
    return sizes[0][0], max(h for _w, h in sizes)


def section_scale(size, base_height, needed_width=None, low=0.3, high=8.0):
    """How much a section of `size` scales its content: the box's height sets it, so
    resizing taller or shorter makes the text bigger or smaller. `needed_width` is how
    wide the content is at scale 1; it only shrinks further if the box is too narrow
    for it, so the text never sticks out."""
    width, height = size
    scale = min(max(height / base_height, low), high)
    if needed_width and needed_width * scale > width:
        scale = max(width / needed_width, low)
    return scale


def stacked(sections, x, y, sizes, gap=8):
    """{name: (x, y, width, height)}: sections one below the other from (x, y), where
    the HUD used to be, for a first start."""
    places = {}
    for section in sections:
        width, height = sizes[section.name]
        places[section.name] = (x, y, width, height)
        y += height + gap
    return places


def below(sections, placed, sizes, screens=(), gap=8):
    """{name: place} for sections new to a player who has placed others: stacked one
    below the other under the lowest placed one, lined up with the first. If they would
    run off the bottom of that screen, they start a new column to the right of the placed
    sections instead, from the top of the highest one."""
    first = next(iter(placed.values()))
    bottom = max(y + height for _x, y, _w, height in placed.values())
    places = stacked(sections, first[0], bottom + gap, sizes, gap)
    screen = next((s for s in screens if s[0] <= first[0] < s[0] + s[2] and s[1] <= first[1] < s[1] + s[3]), None)
    if screen is None or all(y + h <= screen[1] + screen[3] for _x, y, _w, h in places.values()):
        return places
    right = max(x + width for x, _y, width, _h in placed.values())
    top = min(y for _x, y, _w, _h in placed.values())
    return stacked(sections, right + gap, top, sizes, gap)
