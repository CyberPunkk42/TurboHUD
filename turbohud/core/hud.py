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


@dataclass(frozen=True)
class Row:
    """One line of HUD content, before layout."""

    text: str
    style: str  # 'title', 'big', 'medium' or 'small': a font size from Sizes
    color: str = 'text'  # 'text', 'accent', 'ahead' (green) or 'behind' (red)


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


def session_rows(seconds):
    """The content without game data: how long TurboHUD has been running."""
    return [Row('TurboHUD - session time', 'title'), Row(clock(seconds), 'big', 'accent')]


def help_lines(shortcuts):
    """The move-mode hint, as lines, for the move-mode panel."""
    finish = 'Ctrl+Shift+L or Lock finishes.' if shortcuts else 'Lock finishes.'
    return ['Drag a section to move it; resize it at its corner to scale it.', finish]


def _content(rows, sizes):
    """(lines, bottom baseline) for content rows laid out from the top."""
    lines, baseline = [], sizes.margin
    for index, row in enumerate(rows):
        size = getattr(sizes, row.style)
        baseline += (sizes.gap if index else 0) + size
        lines.append(Line(row.text, size, row.color, baseline))
    return lines, baseline


def hud_lines(rows, scale=1.0):
    """The lines of a section's content `rows`, top to bottom."""
    return _content(rows, Sizes.for_scale(scale))[0]


def content_size(rows, scale, measure):
    """(width, height) a section needs for `rows` at `scale`. `measure(text, size)` gives
    a text's width in pixels (Qt knows the font)."""
    sizes = Sizes.for_scale(scale)
    lines, bottom = _content(rows, sizes)
    width = max((measure(line.text, line.size) for line in lines), default=0)
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
)
CLOCK_SECTIONS = (Section('clock', 'Session time', ((Row('TurboHUD - session time', 'title'), Row('00:00', 'big')),)),)


def base_size(section, scale, measure):
    """(width, height) of a section at scale 1 of its own: fits all its samples."""
    sizes = [content_size(rows, scale, measure) for rows in section.samples]
    return max(w for w, _h in sizes), max(h for _w, h in sizes)


def section_scale(size, base, low=0.5, high=8.0):
    """How much a section resized to `size` scales its content, against its `base`
    size; the content keeps its shape and fits."""
    (width, height), (base_width, base_height) = size, base
    return min(max(min(width / base_width, height / base_height), low), high)


def stacked(sections, x, y, sizes, gap=8):
    """{name: (x, y, width, height)}: sections one below the other from (x, y), where
    the HUD used to be, for a first start."""
    places = {}
    for section in sections:
        width, height = sizes[section.name]
        places[section.name] = (x, y, width, height)
        y += height + gap
    return places
