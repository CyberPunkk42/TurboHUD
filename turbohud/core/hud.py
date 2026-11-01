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
    color: str = 'text'  # 'text' or 'accent'


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


# The tallest content the HUD shows (a race: title, current lap, last and best); the
# box's minimum size leaves room for it.
TALLEST = (Row('Lap', 'title'), Row('0:00.0', 'big'), Row('Last', 'medium'))


def clock(seconds):
    """'m:ss' for a number of seconds, like a lap time."""
    minutes, seconds = divmod(int(seconds), 60)
    return f'{minutes}:{seconds:02d}'


def session_rows(seconds):
    """The content without game data: how long TurboHUD has been running."""
    return [Row('TurboHUD - session time', 'title'), Row(clock(seconds), 'big', 'accent')]


def help_lines(locked, shortcuts):
    """The hint shown in move mode, as lines; none while locked."""
    if locked:
        return []
    finish = 'Ctrl+Shift+L or Lock finishes.' if shortcuts else 'Lock finishes, Close quits.'
    return ['Drag to move. Resize at the corner.', finish]


def _content(rows, sizes):
    """(lines, bottom baseline) for content rows laid out from the top."""
    lines, baseline = [], sizes.margin
    for index, row in enumerate(rows):
        size = getattr(sizes, row.style)
        baseline += (sizes.gap if index else 0) + size
        lines.append(Line(row.text, size, row.color, baseline))
    return lines, baseline


def hud_lines(rows, locked, shortcuts, scale=1.0, hint_bottom=None):
    """The HUD's lines, top to bottom: the content `rows`, then in move mode the hint.

    The move-mode hint sits at the bottom, its last line just above `hint_bottom` (the
    top of the Lock and Close buttons), so it never covers them; without `hint_bottom`
    it follows the content.
    """
    sizes = Sizes.for_scale(scale)
    lines, baseline = _content(rows, sizes)
    hint = help_lines(locked, shortcuts)
    if not hint:
        return lines
    step = sizes.small + sizes.hint_gap
    if hint_bottom is None:
        first = baseline + sizes.hint_gap + step
    else:
        # The last baseline leaves room below it for letters such as g and p.
        first = hint_bottom - sizes.hint_gap - (len(hint) - 1) * step
    for index, text in enumerate(hint):
        lines.append(Line(text, sizes.small, 'text', first + index * step))
    return lines


def min_size(scale, controls_height):
    """(width, height) the box needs so the tallest content, the hint and the buttons do
    not overlap. `controls_height` is the height the Lock and Close row takes at the
    bottom."""
    sizes = Sizes.for_scale(scale)
    _, content_bottom = _content(TALLEST, sizes)
    hint = len(help_lines(locked=False, shortcuts=True)) * (sizes.small + sizes.hint_gap)
    height = content_bottom + sizes.hint_gap + hint + sizes.hint_gap + controls_height
    return max(MIN_WIDTH, round(MIN_WIDTH * scale)), height
