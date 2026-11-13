"""What the HUD shows and where, as plain data that turbohud.hud draws."""

import colorsys
import math
from dataclasses import dataclass, field, replace

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
    flag: str = ''  # an ISO country code drawn as a flag before the text
    right: str = ''  # text at the right edge of the box (a column that lines up)
    right_color: str = 'text'
    middle: str = ''  # a second column, lined up on the right just before `right`
    middle_color: str = 'text'
    slot: str = ''  # the text is at the right of a slot this wide, with the tail after it
    before: str = ''  # a column lined up on the right just before `middle`, in the text's colour
    rule: str = ''  # a line above it, labelled with this (a class in the lap times)
    centred: bool = False  # in the middle of the box, whatever the section's other lines do
    tag: str = ''  # a column lined up on the left just before `before` (a clan tag in the lap times)
    tag_color: str = ''  # the tag's own colour ('#rrggbb' or a theme name); '' for the text's
    rule_color: str = ''  # the rule's own colour; '' for the accent
    tyre: str = ''  # a tire compound's letter, in a ring, just before `middle` (the lap times)
    tyre_color: str = ''  # its ring's colour, '#rrggbb'
    overall: str = (
        ''  # a column lined up on the right just after the text (the overall place in the lap times)
    )


@dataclass(frozen=True)
class Row:
    """One line of HUD content, before layout."""

    text: str
    style: str  # 'title', 'big', 'medium' or 'small': a font size from Sizes
    color: str = 'text'  # 'text', 'accent', 'ahead' (green), 'behind' (red) or 'lift' (yellow)
    tail: str = ''  # more text right after it, in its own colour
    tail_color: str = 'text'
    flag: str = ''  # an ISO country code drawn as a flag before the text
    right: str = ''  # text at the right edge of the box (a column that lines up)
    right_color: str = 'text'
    middle: str = ''  # a second column, lined up on the right just before `right`
    middle_color: str = 'text'
    slot: str = ''  # the text is at the right of a slot this wide, with the tail after it
    before: str = ''  # a column lined up on the right just before `middle`, in the text's colour
    rule: str = ''  # a line in the gap above it, labelled with this (a class in the lap times)
    centred: bool = False  # in the middle of the box (the yellow flag's heading)
    tag: str = ''  # a column lined up on the left just before `before` (a clan tag in the lap times)
    tag_color: str = ''  # the tag's own colour ('#rrggbb' or a theme name); '' for the text's
    rule_color: str = ''  # the rule's own colour; '' for the accent
    tyre: str = ''  # a tire compound's letter, in a ring, just before `middle` (the lap times)
    tyre_color: str = ''  # its ring's colour, '#rrggbb'
    overall: str = (
        ''  # a column lined up on the right just after the text (the overall place in the lap times)
    )


FLAG_WIDTH = 1.5  # a flag's room before the text, in font sizes
TYRE_WIDTH = 1.0  # a tire compound's ring, in font sizes (no lower than the text's descenders)
COLUMN_GAP = 1.0  # least room between the text and the right column, in font sizes


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


def blend(start, end, share):
    """'#rrggbb' that far (0 to 1) from colour `start` to `end`, both '#rrggbb', round
    the colour wheel (hue, saturation and brightness each move evenly): a straight mix
    of cyan and red turns grey halfway, this stays bright (through violet). The hue
    goes the shorter way round."""
    share = min(max(share, 0.0), 1.0)
    if share in (0.0, 1.0):
        return start if share == 0.0 else end
    h1, s1, v1 = colorsys.rgb_to_hsv(*(int(start[i : i + 2], 16) / 255 for i in (1, 3, 5)))
    h2, s2, v2 = colorsys.rgb_to_hsv(*(int(end[i : i + 2], 16) / 255 for i in (1, 3, 5)))
    turn = (h2 - h1 + 0.5) % 1.0 - 0.5  # the shorter way round
    rgb = colorsys.hsv_to_rgb((h1 + turn * share) % 1.0, s1 + (s2 - s1) * share, v1 + (v2 - v1) * share)
    return '#' + ''.join(f'{round(c * 255):02x}' for c in rgb)


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


def help_lines(shortcuts, commands=False, lock_key='Ctrl+Shift+L'):
    """The move-mode hint, as lines, for the move-mode panel. `commands`: the command
    line can switch move mode (turbohud.control), for systems without shortcuts. `lock_key`:
    the key that switches it (Ctrl+Shift+F12 where another program has Ctrl+Shift+L)."""
    finish = f'{lock_key} or Lock finishes.' if shortcuts else 'Lock finishes.'
    lines = [
        'Drag a section to move it. At its corner: taller or shorter scales',
        'the text, wider makes room for it.',
        finish,
    ]
    if commands and not shortcuts:
        lines.append('Without shortcuts: run_turbohud.sh --toggle (a key can run it).')
    return lines


def _content(rows, sizes):
    """(lines, bottom baseline) for content rows laid out from the top."""
    lines, baseline = [], sizes.margin
    for index, row in enumerate(rows):
        size = getattr(sizes, row.style)
        baseline += (sizes.gap if index else 0) + size
        lines.append(
            Line(
                row.text,
                size,
                row.color,
                baseline,
                row.tail,
                row.tail_color,
                row.flag,
                row.right,
                row.right_color,
                row.middle,
                row.middle_color,
                row.slot,
                row.before,
                row.rule,
                row.centred,
                row.tag,
                row.tag_color,
                row.rule_color,
                row.tyre,
                row.tyre_color,
                row.overall,
            )
        )
    return lines, baseline


def hud_lines(rows, scale=1.0):
    """The lines of a section's content `rows`, top to bottom."""
    return _content(rows, Sizes.for_scale(scale))[0]


def _left_width(line, measure):
    """How wide a line's text is with its flag, without the columns."""
    width = measure((line.slot or line.text) + line.tail, line.size)
    if line.flag:
        width += FLAG_WIDTH * line.size
    return width


def line_width(line, measure):
    """How wide a line is with its flag and its columns."""
    width = _left_width(line, measure)
    if line.overall:
        width += COLUMN_GAP * line.size + measure(line.overall, line.size)
    if line.tag:
        width += COLUMN_GAP * line.size + measure(line.tag, line.size)
    if line.before:
        width += COLUMN_GAP * line.size + measure(line.before, line.size)
    if line.tyre:
        width += (COLUMN_GAP + TYRE_WIDTH) * line.size
    if line.middle:
        width += COLUMN_GAP * line.size + measure(line.middle, line.size)
    if line.right:
        width += COLUMN_GAP * line.size + measure(line.right, line.size)
    return width


def lines_width(lines, measure):
    """How wide `lines` are together. With a middle column, the columns line up: the
    widest text, the widest middle and the widest right column side by side."""
    if not any(line.middle for line in lines):
        return max((line_width(line, measure) for line in lines), default=0)
    gap = max(COLUMN_GAP * line.size for line in lines)
    before = max((measure(line.before, line.size) for line in lines if line.before), default=None)
    tag = max((measure(line.tag, line.size) for line in lines if line.tag), default=None)
    overall = max((measure(line.overall, line.size) for line in lines if line.overall), default=None)
    tyre = tyre_width(lines)
    return (
        max(_left_width(line, measure) for line in lines)
        + (overall + gap if overall is not None else 0)
        + (tag + gap if tag is not None else 0)
        + (before + gap if before is not None else 0)
        + (tyre + gap if tyre is not None else 0)
        + gap
        + max((measure(line.middle, line.size) for line in lines if line.middle), default=0)
        + gap
        + max((measure(line.right, line.size) for line in lines if line.right), default=0)
    )


def snug_width(lines, reserve, width, margin, measure):
    """How wide the box is for the columns of a snug section (Section.snug): up to just
    after the text field `reserve` (the section's sample) makes room for, with its columns,
    at most `width`; only a text in `lines` wider than that field moves them on. Asked for by
    the user on 2026-11-13: the lap times' columns close to the names, after a field for a
    20-letter name (LAP_NAME_SHOWN), so the list keeps its width whoever joins."""
    return min(width, lines_width(list(lines) + list(reserve), measure) + 2 * margin)


def middle_right(lines, width, margin, measure):
    """Where the middle column ends (it is right-aligned there) in a box `width` wide:
    before the widest right column, with a gap."""
    right = max((measure(line.right, line.size) for line in lines if line.middle and line.right), default=0)
    gap = max((COLUMN_GAP * line.size for line in lines if line.middle), default=0)
    return width - margin - right - gap


def tyre_width(lines):
    """How wide the tire column is (the largest ring); None without one."""
    return max((TYRE_WIDTH * line.size for line in lines if line.tyre), default=None)


def tyre_right(lines, middle_end, measure):
    """Where the tire column ends: before the widest middle column, whose right edge is at
    `middle_end`, with a gap."""
    middle = max((measure(line.middle, line.size) for line in lines if line.middle), default=0)
    gap = max((COLUMN_GAP * line.size for line in lines if line.middle), default=0)
    return middle_end - middle - gap


def before_right(lines, middle_end, measure, tyre_end=None):
    """Where the `before` column ends (it is right-aligned there): before the tire column, if
    any, else before the widest middle column, whose right edge is at `middle_end`, with a gap.
    `tyre_end`: tyre_right's answer for the same lines, if the caller has it (draw_hud does,
    each frame), so the middle column is not measured twice."""
    end = tyre_right(lines, middle_end, measure) if tyre_end is None else tyre_end
    tyre = tyre_width(lines)
    if tyre is None:
        return end
    return end - tyre - max(COLUMN_GAP * line.size for line in lines)


def tag_left(lines, before_end, measure):
    """Where the `tag` column starts (it is left-aligned there): before the widest `before`
    column, which ends at `before_end`, and the widest tag, with a gap; None without tags."""
    tag = max((measure(line.tag, line.size) for line in lines if line.tag), default=None)
    if tag is None:
        return None
    before = max((measure(line.before, line.size) for line in lines if line.before), default=None)
    gap = max(COLUMN_GAP * line.size for line in lines)
    start = before_end - before - gap if before is not None else before_end
    return start - tag


def overall_right(lines, middle_end, tyre_end, before_end, tag_start, measure):
    """Where the `overall` column ends (it is right-aligned there): a gap before the leftmost
    of the other columns (the tag, `before`, the tire, the middle one); None without it."""
    if not any(line.overall for line in lines):
        return None

    def widest(name):
        return max(
            (measure(getattr(line, name), line.size) for line in lines if getattr(line, name)), default=None
        )

    if tag_start is not None:
        start = tag_start
    elif widest('before') is not None:
        start = before_end - widest('before')
    elif tyre_width(lines) is not None:
        start = tyre_end - tyre_width(lines)
    else:
        start = middle_end - (widest('middle') or 0)
    return start - max(COLUMN_GAP * line.size for line in lines)


def content_size(rows, scale, measure):
    """(width, height) a section needs for `rows` at `scale`. `measure(text, size)` gives
    a text's width in pixels (Qt knows the font)."""
    sizes = Sizes.for_scale(scale)
    lines, bottom = _content(rows, sizes)
    width = lines_width(lines, measure)
    # Below the last baseline: room for letters such as g and p, then the margin.
    return round(width + 2 * sizes.margin), round(bottom + sizes.margin)


ALL_ZEROS = str.maketrans('123456789-\u2212', '000000000++')  # and signs as wide as a plus


def steady_text(text):
    """`text` with its digits as zeros and its signs as plus, to measure it: in a font
    whose digits differ in width, text centred by its real width would shake as a number
    changes."""
    return text.translate(ALL_ZEROS)


def steady_rows(rows):
    """`rows` with their digits as zeros (steady_text), to measure them."""
    return [
        replace(
            row,
            text=steady_text(row.text),
            tail=steady_text(row.tail),
            middle=steady_text(row.middle),
            before=steady_text(row.before),
            overall=steady_text(row.overall),
            tag=steady_text(row.tag),
            right=steady_text(row.right),
        )
        for row in rows
    ]


def centred_text(size, rows, scale, measure, cap_height, least_left=0):
    """(left, down) that centre `rows` in a box of `size`: where the content starts
    across (at least `least_left`, to keep clear of what is at the side), and how far to
    move it down. `cap_height(font_size)` gives how tall a capital letter is.

    Digits count as zeros (steady_text), so it only shifts when a number gets another
    digit."""

    def steady(text, font_size):
        return measure(steady_text(text), font_size)

    lines = hud_lines(rows, scale)
    top = lines[0].baseline - cap_height(lines[0].size)
    left = max((size[0] - content_size(rows, scale, steady)[0]) // 2, least_left)
    return left, round((size[1] - top - lines[-1].baseline) / 2)


@dataclass(frozen=True)
class Section:
    """One part of the HUD in its own window, placed by the player."""

    name: str  # its key in settings.json
    label: str  # how menus and move mode name it
    samples: tuple  # row lists it may show; the widest and tallest sets its size
    pedals: bool = False  # a throttle bar on its left and a brake bar on its right
    bar: tuple = ()  # (width, height) at scale 1 for a drawing without text
    drawing: str = ''  # what it draws instead of text: 'flag' (blue flag), 'radar' or 'map'
    level: bool = False  # a bar below the text showing how much is left (fuel, tires, health)
    sectors: bool = False  # with `level`: the room below the text holds the lap's sector bars
    background: str = ''  # '#rrggbb': a solid box behind its text, in place of the Tint (the yellow flag)
    snug: bool = (
        False  # its columns right after the longest text shown, not at the box's right edge (snug_width)
    )


LAP_TIME_ROWS = 20  # how many drivers the lap times section is made for
OLD_LAP_TIME_ROWS = 16  # before layout 3


def has_tint(section):
    """Whether a section has a Tint option: every text section (a light tint behind its
    text) and the track map (its dark square)."""
    return (not section.drawing and not section.background) or section.drawing == 'map'


def default_tint(section, backdrop=False):
    """A section's tint where nothing saved says: the track map has its dark square, as
    before it had the option; a text section follows `backdrop` (Settings.backdrop)."""
    return True if section.drawing == 'map' else backdrop


def text_can_centre(section):
    """Whether a section's text can go in the middle of its box: not the speed, which is
    always between its pedal bars, nor a drawing, nor a list with columns."""
    if section.bar or section.pedals:
        return False
    rows = [row for sample in section.samples for row in sample]
    return not any(row.right or row.middle or row.flag for row in rows)


RACE_SECTIONS = (
    Section(
        'lap',
        'Lap and time left',
        (
            (Row('Lap 13/13  -  21:00 left', 'title'),),
            (Row('Waiting for TSU (launch option)', 'title'),),
        ),
    ),
    Section('current', 'Running lap', ((Row('0:00.0', 'big'),), (Row('10:00.000', 'big'),))),
    Section('delta', 'Delta to best', ((Row('+00.00 vs best', 'medium'),),)),
    Section(
        'times',
        'Last and best lap',
        ((Row('Last 0:00.000   Best 0:00.000', 'medium'),),),
        level=True,
        sectors=True,
    ),
    Section('fuel', 'Fuel', ((Row('Fuel 100.0%', 'medium', tail='  ~10.0 laps  +0.00%'),),), level=True),
    Section('fuelfinish', 'Fuel to finish', ((Row('Finish +00.0 laps', 'medium'),),)),
    Section('tires', 'Tires', ((Row('Tires 100%  ~10.0 laps', 'medium'),),), level=True),
    Section('health', 'Health', ((Row('Health 100%', 'medium', tail='  less downforce'),),), level=True),
    Section(
        'draft',
        'Draft',
        (
            (
                Row('Draft 100%', 'medium', tail='  -80% downforce'),
                Row('Max -10% drag  -80% downforce  reach 30  20°', 'small'),
                Row('Playername1234567 drafts you 100%', 'small'),
            ),
        ),
        level=True,
    ),
    Section('speed', 'Speed', ((Row('000 km/h', 'medium'),),), pedals=True),
    Section('localtime', 'Local time', ((Row('00:00', 'medium'),),)),
    Section(
        'players',
        'Players',
        (
            tuple(
                Row(
                    f'{n}. Playername1234567',
                    'small',
                    tail='  PIT 00.0s',
                    flag='DE',
                    middle='+00.000',
                    tag='PROAM P20',  # the longest class and its place
                    tyre='M',
                )
                for n in range(10, 10 + 8)
            ),
        ),
    ),
    Section(
        'laptimes',
        'Lap times',
        (
            (Row('Driver', 'small', 'accent', middle='Best', right='Lap'),)
            + tuple(
                Row(
                    f'{n}. Playername1234567890',  # a 20-letter name (race.LAP_NAME_SHOWN)
                    'small',
                    before='L99',
                    flag='DE',
                    middle='PIT 00.0s',
                    right='CUT 00.0s',  # the widest there: wider than (00.00s), JUMP and 0:00.0
                    tag='PROAM',  # a clan tag or class has up to 5 letters
                    tyre='M',
                    overall='P20',  # the overall place, in a multi-class race
                )
                for n in range(10, 10 + LAP_TIME_ROWS)
            ),
        ),
        snug=True,
    ),
    Section(
        'yellowflag',
        'Yellow flag',
        (
            (
                Row('YELLOW  -  Sector 3', 'title', '#111111', centred=True),
                Row('S3  Playername1234567  respawned', 'small', '#111111'),
                Row('S3  Playername1234567  off track', 'small', '#111111'),
                Row('S4  Playername1234567  stopped', 'small', '#111111'),
            ),
        ),
        background='#ffd400',
    ),
    Section(
        'shortcut',
        'Penalties',
        ((Row('SHORTCUT  0.0 s', 'title', '#111111', centred=True),),),
        background='#ff8c1a',
    ),
    Section('blueflag', 'Blue flag', (), bar=(480, 24), drawing='flag'),
    Section('deltabar', 'Delta bar', (), bar=(360, 36), drawing='delta'),
    Section('radar', 'Proximity radar', (), bar=(160, 160), drawing='radar'),
    Section('trackmap', 'Track map', (), bar=(240, 240), drawing='map'),
)
# The move-mode panel lists the sections under these headings (asked for by the user on
# 2026-11-11); a section not named here comes under the last.
PANEL_CATEGORIES = (
    ('Timing', ('lap', 'current', 'delta', 'deltabar', 'times', 'laptimes')),
    ('Car', ('fuel', 'fuelfinish', 'tires', 'health', 'draft', 'speed')),
    ('Race', ('players', 'trackmap', 'radar', 'blueflag', 'yellowflag', 'shortcut')),
    ('Other', ('localtime', 'clock')),
)


def panel_categories(sections):
    """[(heading, [sections])] for the move-mode panel, in PANEL_CATEGORIES' order, empty
    headings left out; one heading alone is no heading ('', [all])."""
    named = {name: index for index, (_heading, names) in enumerate(PANEL_CATEGORIES) for name in names}
    found = [(heading, []) for heading, _names in PANEL_CATEGORIES]
    for section in sections:
        found[named.get(section.name, len(found) - 1)][1].append(section)
    order = {name: place for _heading, names in PANEL_CATEGORIES for place, name in enumerate(names)}
    kept = [
        (heading, sorted(listed, key=lambda s: order.get(s.name, len(order))))
        for heading, listed in found
        if listed
    ]
    if len(kept) == 1:
        return [('', kept[0][1])]
    return kept


CLOCK_SECTIONS = (
    Section('clock', 'Session time', ((Row('TurboHUD - session time', 'title'), Row('00:00', 'big')),)),
    Section('localtime', 'Local time', ((Row('00:00', 'medium'),),)),
)


def base_size(section, scale, measure):
    """(width, height) of a section at scale 1 of its own: as wide as its usual content
    (the first sample, and its pedal bars) and as tall as its tallest."""
    if section.bar:
        return round(section.bar[0] * scale), round(section.bar[1] * scale)
    sizes = [content_size(rows, scale, measure) for rows in section.samples]
    extra = pedal_space(scale) if section.pedals else 0
    below = level_space(scale) if section.level else 0
    return sizes[0][0] + extra, max(h for _w, h in sizes) + below


LEVEL_HEIGHT = 8  # the level bar's height below the text, at scale 1


def level_space(scale):
    """The height the level bar adds below a section's text."""
    return round(LEVEL_HEIGHT * scale)


def level_bar(width, content_height, scale, fill, color):
    """The level bar below a section's text: as wide as the section between its
    margins, just under the text (whose height with margins is `content_height`), lit
    from the left to `fill` (0 to 1) in `color` ('ahead', 'lift' or 'behind')."""
    margin = round(MARGIN * scale)
    top = content_height - margin // 2
    return Bar(
        margin, top, max(width - 2 * margin, 1), max(level_space(scale), 2), min(max(fill, 0.0), 1.0), color
    )


@dataclass(frozen=True)
class Sectors:
    """The sector bars below the last and best lap: one colour per sector of the lap
    shown ('#rrggbb', or None while that sector is still to come)."""

    colours: tuple


SECTOR_GAP = 4  # between two sector bars, at scale 1, at most
SECTOR_GAP_SHARE = 0.25  # and at most this share of a bar's room: many sectors, thin gaps


def sector_bars(width, content_height, scale, count):
    """`count` equal bars side by side where a level bar goes (see level_bar), as Bars
    with no fill: the caller colours them."""
    whole = level_bar(width, content_height, scale, 0.0, '')
    gap = max(min(SECTOR_GAP * scale, whole.width / count * SECTOR_GAP_SHARE), 1) if count > 1 else 0
    each = max((whole.width - gap * (count - 1)) / count, 1)
    bars = []
    for index in range(count):
        left = round(whole.x + index * (each + gap))
        right = round(whole.x + index * (each + gap) + each)
        bars.append(Bar(left, whole.y, max(right - left, 1), whole.height, 0.0, ''))
    return bars


def sector_bar_place(section, place, scale, ink):
    """`place` (x, y, width, height) of a section saved before it had sector bars (layout
    5): taller by their room, so that its text stays the same size."""
    if not section.sectors:
        return place
    x, y, width, height = place
    old = tight_height(replace(section, level=False, sectors=False), scale, ink)
    return x, y, width, round(height / old * tight_height(section, scale, ink))


PEDAL_WIDTH = 10  # a pedal bar's width at scale 1
PEDAL_GAP = 4  # between a bar and the text


def pedal_space(scale):
    """The width both pedal bars take, with their gaps to the text."""
    return 2 * round((PEDAL_WIDTH + PEDAL_GAP) * scale)


@dataclass(frozen=True)
class Bar:
    x: int
    y: int
    width: int
    height: int
    fill: float  # 0 to 1: how much of it lights up, from the bottom
    color: str  # 'ahead' (green) or 'behind' (red) where lit


def pedal_bars(width, height, scale, throttle, brake, inset=4):
    """The throttle bar (left edge, green) and brake bar (right edge, red) of a section
    `width` x `height`, as tall as the section. `throttle` and `brake` are 0 to 1, or
    None when unknown (then grey, like no input)."""
    bar = max(2, round(PEDAL_WIDTH * scale))
    top, tall = inset, max(1, height - 2 * inset)

    def amount(value):
        return min(max(value or 0.0, 0.0), 1.0)

    return [
        Bar(inset, top, bar, tall, amount(throttle), 'ahead'),
        Bar(width - inset - bar, top, bar, tall, amount(brake), 'behind'),
    ]


TIGHT_PAD = 3  # room between a box's edge and its content, at scale 1
FIT_ROOM = 2  # pixels kept free in a box that its content only just fits
FIT_STEP, FIT_STEPS = 0.98, 40  # how far fitted_scale goes, and how often at most
OLD_LABEL_SPACE = 14  # room boxes kept for the section's name before they were tight


def ink_span(section, scale, ink):
    """(top, bottom) of what a text section draws, from its box's top, in pixels: from
    the top of its first letters to the bottom of its last, or of its level bar. Taken
    from its tallest sample, so that it stays put as the text changes. Where the sample
    has letters, room for those that hang below the line, as the live text may have
    them. `ink(text, size)` gives how far a text reaches (above, below) its baseline."""
    sizes = Sizes.for_scale(scale)
    lines, bottom_baseline = max(
        (_content(rows, sizes) for rows in section.samples), key=lambda content: content[1]
    )

    def whole(line):
        return line.text + line.tail + line.middle + line.right

    top = lines[0].baseline - ink(whole(lines[0]), lines[0].size)[0]
    if section.level:
        content_height = bottom_baseline + sizes.margin
        return top, content_height - sizes.margin // 2 + max(level_space(scale), 2)
    last = whole(lines[-1])
    hanging = 'g' if any(letter.isalpha() for letter in last) else ''
    return top, lines[-1].baseline + ink(last + hanging, lines[-1].size)[1]


def tight_height(section, scale, ink):
    """A text section's normal height: its box fits closely round its content."""
    top, bottom = ink_span(section, scale, ink)
    return round(bottom - top + 2 * max(1, round(TIGHT_PAD * scale)))


def fitted_scale(section, height, scale, ink, width=None, rows=(), measure=None):
    """`scale`, a little smaller if the content would not fit a box of `height`: font
    sizes and gaps round to whole pixels, which in a long list adds up. As small as the
    box allows, within reason: a box can be shorter than any readable text. With `width`,
    `rows` and `measure` the same goes across: text is not as wide as its font size says
    (at 8 px, a quarter wider than in proportion to 20 px in the Mac's system font), so
    only measuring it at the size it is drawn tells whether it fits."""

    def fits(scale):
        top, bottom = ink_span(section, scale, ink)
        if bottom - top + FIT_ROOM > height:
            return False
        if width is None or not rows:
            return True
        bars = pedal_space(scale) if section.pedals else 0
        return content_size(rows, scale, measure)[0] + bars <= width

    for _step in range(FIT_STEPS):
        if fits(scale):
            break
        scale *= FIT_STEP
    return scale


def content_shift(section, height, scale, ink):
    """How far to move a section's content down (negative: up) to centre it in a box of
    `height`. Its layout starts a margin from the top, which a tight box does not have."""
    top, bottom = ink_span(section, scale, ink)
    return round((height - top - bottom) / 2)


def _with_old_lap_rows(section):
    """The lap times section as it was before layout 3; any other section as it is."""
    if section.name != 'laptimes':
        return section
    rows = section.samples[0][: 1 + OLD_LAP_TIME_ROWS]  # the heading and the drivers
    return replace(section, samples=(rows,))


def more_lap_rows_place(section, place, scale, ink):
    """`place` (x, y, width, height) of a section saved before the lap times list had room
    for more drivers (layout 3): as tall as needs be for the text to stay the same size.
    The box grows downwards, so the rows it had stay where they were."""
    if section.name != 'laptimes':
        return place
    x, y, width, height = place
    old_normal = tight_height(_with_old_lap_rows(section), scale, ink)
    return x, y, width, round(height / old_normal * tight_height(section, scale, ink))


def tight_place(section, place, scale, ink):
    """`place` (x, y, width, height) of a section saved before boxes were tight (layout
    2), as a tight box with its text the same size and in the same spot. The text's size
    came from the height's share of a taller normal height. Pedal bars were as tall as the
    box, with the speed centred between them, so that box keeps its middle."""
    x, y, width, height = place
    section = _with_old_lap_rows(section)
    if section.bar:
        return place
    old_normal = base_size(section, scale, lambda _text, _size: 0)[1] + round(OLD_LABEL_SPACE * scale)
    share = height / old_normal
    new_height = round(share * tight_height(section, scale, ink))
    if section.pedals:
        return x, y + (height - new_height) // 2, width, new_height
    return x, y - content_shift(section, new_height, scale * share, ink), width, new_height


def widest_rows(section, rows, scale, measure):
    """What a section's text size is worked out from, so that it stays as the content
    changes: the `rows` or the section's usual content, whichever is wider, with digits
    as zeros. Without any `rows`, nothing."""
    if not rows:
        return []
    # Together, so each column is as wide as the wider of the two: before, the wider of the
    # two whole lists, and a CUT or PIT made the lap times wider than their usual content
    # though the names were shorter: the text shrank and grew back (reported 2026-11-12).
    return steady_rows(section.samples[0]) + steady_rows(rows)


def drawn_scale(section, size, rows, normal_height, scale, ink, measure):
    """The scale a section draws `rows` at in a box of `size`; `normal_height` is its
    normal height at the theme's `scale`."""
    widest = widest_rows(section, rows, scale, measure)
    needed = None
    if widest:
        needed = content_size(widest, scale, measure)[0] + (pedal_space(scale) if section.pedals else 0)
    drawn = scale * section_scale(size, normal_height, needed)
    return fitted_scale(section, size[1], drawn, ink, size[0], widest, measure)


def _first_font(section, scale):
    """The font size of a section's first row at `scale`."""
    return getattr(Sizes.for_scale(scale), section.samples[0][0].style)


def match_sizes(places, scale, measure, ink):
    """{name: (x, y, width, height)} giving `places` {section: (x, y, width, height)} the
    same font size, the largest they have, and the same width, the widest they then need.
    A section's height sets its font size, so heights stay as different as the content
    is (level bars, several rows). They stay where they are. `scale` is the theme's."""

    def usual(section):
        return list(section.samples[0])

    normal = {section: tight_height(section, scale, ink) for section in places}
    font = max(
        _first_font(
            section, drawn_scale(section, place[2:], usual(section), normal[section], scale, ink, measure)
        )
        for section, place in places.items()
    )

    def width_at(section, at):
        bars = pedal_space(at) if section.pedals else 0
        return content_size(steady_rows(usual(section)), at, measure)[0] + bars

    heights, needed = {}, 0
    for section, height in normal.items():
        near = round(font / _first_font(section, scale) * height)
        heights[section] = next(
            (
                tried
                for tried in range(max(near - 2, 1), near + 4)
                if _first_font(section, fitted_scale(section, tried, scale * tried / height, ink)) == font
            ),
            near,
        )
        # Both: what the height's share of the normal width allows the text, and how wide
        # it really is at that size.
        share = heights[section] / height
        needed = max(needed, width_at(section, scale) * share, width_at(section, scale * share))
    return {
        section.name: (place[0], place[1], math.ceil(needed), heights[section])
        for section, place in places.items()
    }


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
    screen = next(
        (s for s in screens if s[0] <= first[0] < s[0] + s[2] and s[1] <= first[1] < s[1] + s[3]), None
    )
    if screen is not None:
        # Only the sections on that screen count (some may sit on another monitor).
        placed = {
            name: place
            for name, place in placed.items()
            if screen[0] <= place[0] < screen[0] + screen[2] and screen[1] <= place[1] < screen[1] + screen[3]
        }
    bottom = max(y + height for _x, y, _w, height in placed.values())
    places = stacked(sections, first[0], bottom + gap, sizes, gap)
    if screen is None or all(y + h <= screen[1] + screen[3] for _x, y, _w, h in places.values()):
        return places
    right = max(x + width for x, _y, width, _h in placed.values())
    top = min(y for _x, y, _w, _h in placed.values())
    return stacked(sections, right + gap, top, sizes, gap)


REFERENCE_SCREEN = (1920, 1080)  # the first-launch layout is made for this size
LAYOUT_MARGIN = 40  # from the screen's edges


def main_screen(screens):
    """The screen the first-launch layout goes on: the largest (where games usually run);
    of equal ones, the first. None without screens."""
    return max(screens, key=lambda s: s[2] * s[3], default=None)


def first_launch(sections, sizes, origin=(0, 0), reference=REFERENCE_SCREEN, margin=LAYOUT_MARGIN, gap=8):
    """{name: (x, y, width, height)} for a first launch: the sections one below the other
    at the left of a `reference`-sized screen whose top-left corner is `origin`,
    vertically centred, so the middle stays free. What does not fit in the height starts
    another column to the right; nothing overlaps. Bars (the blue flag) are not in the
    column: see top_centre."""
    sections = [section for section in sections if not section.bar]
    room = reference[1] - 2 * margin
    columns, column, height = [], [], 0
    for section in sections:
        section_height = sizes[section.name][1]
        if column and height + gap + section_height > room:
            columns.append(column)
            column, height = [], 0
        height += (gap if column else 0) + section_height
        column.append(section)
    if column:
        columns.append(column)
    places = {}
    x = origin[0] + margin
    for column in columns:
        total = sum(sizes[s.name][1] for s in column) + gap * (len(column) - 1)
        y = origin[1] + margin + max((room - total) // 2, 0)
        for section in column:
            width, section_height = sizes[section.name]
            places[section.name] = (x, y, width, section_height)
            y += section_height + gap
        x += max(sizes[s.name][0] for s in column) + gap
    return places


def top_centre(size, screen, margin=LAYOUT_MARGIN):
    """(x, y, width, height) of a `size` box at the top centre of `screen` (x, y, width,
    height): where a bar such as the blue flag goes first."""
    width, height = size
    x, y, screen_width, _screen_height = screen
    return (x + (screen_width - width) // 2, y + margin, width, height)


RADAR_DOWN = 0.6  # the radar starts centred, this far down the screen (below the car)


DELTA_BAR_DOWN = 0.07  # how far below the blue flag the delta bar goes first, of the screen


def drawing_place(section, size, screen, margin=LAYOUT_MARGIN):
    """Where a drawing section goes first: the blue flag at the top centre, the radar
    in the middle a little below the centre, where the eyes are while driving, and the
    track map at the right edge, half way down (the other sections start at the left)."""
    if section.drawing == 'map':
        width, height = size
        x, y, screen_width, screen_height = screen
        return (x + screen_width - margin - width, y + (screen_height - height) // 2, width, height)
    if section.drawing == 'delta':  # below where the blue flag goes
        x, y, width, height = top_centre(size, screen)
        return (x, y + round(screen[3] * DELTA_BAR_DOWN), width, height)
    if section.drawing == 'radar':
        width, height = size
        x, y, screen_width, screen_height = screen
        return (x + (screen_width - width) // 2, y + round(screen_height * RADAR_DOWN), width, height)
    return top_centre(size, screen)


GROUP_TOLERANCE = 3  # pixels: a window this close to where TurboHUD moved it has arrived
GROUP_PENDING = 1.0  # seconds a move TurboHUD asked for may take to arrive


@dataclass
class GroupMover:
    """Moves and resizes a group's sections along when the player drags or resizes one of
    them (move mode).

    The desktop changes the dragged window; TurboHUD only sees where windows are when it
    looks (on Wayland only the desktop knows). So `follow` compares each look with the
    one before: if exactly one section of a group has moved, the others are moved by the
    same amount; if exactly one has changed size, the others change by the same factors.
    Their own arrival is then expected, not taken for a drag. Sizes are worked out from
    those at the start of a resize, so rounding does not add up over a long one.
    """

    known: dict = field(default_factory=dict)  # name -> (x, y, width, height) last seen or set
    # name -> (place asked for: (x, y) or (x, y, width, height), until)
    pending: dict = field(default_factory=dict)
    # group -> (the section being resized, {name: (width, height) when it began})
    resizing: dict = field(default_factory=dict)

    def follow(self, seen, groups, now):
        """{name: (x, y, width, height)} to give group mates, for `seen` {name: place} at
        monotonic time `now`; `groups` is {name: group or ''}."""
        moved, resized = {}, {}
        for name, place in seen.items():
            before = self.known.get(name)
            target = self.pending.get(name)
            if target is not None:
                goal, until = target
                arrived = all(abs(got - wanted) <= GROUP_TOLERANCE for got, wanted in zip(place, goal))
                if arrived or now > until:
                    # There (or it never got there): this is its place, not a drag.
                    del self.pending[name]
                    self.known[name] = place
                continue  # else still on its way: neither a drag nor its new place
            if before is not None:
                if tuple(place[:2]) != tuple(before[:2]):
                    moved[name] = (place[0] - before[0], place[1] - before[1])
                if tuple(place[2:]) != tuple(before[2:]):
                    resized[name] = tuple(before[2:])
            self.known[name] = place
        moves = {}
        for group in {g for g in groups.values() if g}:
            members = [name for name in seen if groups.get(name) == group]
            movers = [name for name in members if name in moved]
            resizers = [name for name in members if name in resized]
            if not resizers:
                self.resizing.pop(group, None)
            dx, dy = moved[movers[0]] if len(movers) == 1 else (0, 0)
            sizes = None
            if len(resizers) == 1:
                sizes = self._sizes(group, resizers[0], resized[resizers[0]], members)
            elif len(movers) != 1:
                continue  # nobody dragged, or several changed (not by one drag)
            leaders = {*movers, *resizers}
            for name in members:
                if name in leaders or name not in self.known:
                    continue
                x, y, width, height = self.known[name]
                if sizes is not None and name in sizes:
                    width, height = sizes[name]
                place = (x + dx, y + dy, width, height)
                if place != self.known[name]:
                    moves[name] = place
        for name, place in moves.items():
            self.known[name] = place
            self.pending[name] = (place, now + GROUP_PENDING)
        return moves

    def _sizes(self, group, leader, leader_before, members):
        """{name: (width, height)} for a group whose `leader` is being resized."""
        started = self.resizing.get(group)
        if started is None or started[0] != leader:
            start = {name: tuple(self.known[name][2:]) for name in members if name in self.known}
            start[leader] = leader_before
            started = self.resizing[group] = (leader, start)
        start = started[1]
        across = self.known[leader][2] / start[leader][0]
        down = self.known[leader][3] / start[leader][1]
        return {
            name: (max(1, round(width * across)), max(1, round(height * down)))
            for name, (width, height) in start.items()
        }


FRAMES_EVERY = 30.0  # seconds between the log's lines about how the overlay draws
RACE_FRAME_MOST = 0.1  # seconds without a read before a race frame is drawn anyway


class FramePacer:
    """Whether to draw a frame now. In a race, one for each new read: on timers of their
    own, 19 reads and 20 frames a second left a frame with nothing new about once a
    second, and the track map's dots stood still and then jumped. A late read still gets a
    frame after `most` seconds, for the times that run on: two read intervals, so that
    fewer reads also mean fewer frames. Otherwise at every call."""

    def __init__(self, most=RACE_FRAME_MOST):
        self.most = most
        self._read_at = self._drawn_at = None

    def due(self, read_at, racing, now):
        """(draw now, the frame has a new read). `read_at`: when the latest read was made."""
        fresh = read_at != self._read_at
        late = self._drawn_at is None or now - self._drawn_at >= self.most
        if not (fresh or late or not racing):
            return False, False
        self._read_at, self._drawn_at = read_at, now
        return True, fresh


class FrameTimes:
    """How smoothly the overlay's frames come and how busy they keep its thread, for the
    log, over FRAMES_EVERY seconds at a time. `frame(worked, drawn, fresh)` at each frame:
    the seconds it spent on the content, on drawing since the last one, and whether it
    has a new read."""

    def __init__(self, clock, log_line):
        self._clock = clock
        self._log_line = log_line
        self.clear()

    def clear(self):
        self._gaps, self._last, self._since = [], None, None
        self._worked = self._drawn = 0.0
        self._stale = 0

    def frame(self, worked, drawn, fresh=True):
        now = self._clock()
        if self._last is not None:
            self._gaps.append(now - self._last)
        else:
            self._since = now
        self._last = now
        self._worked += worked
        self._drawn += drawn
        self._stale += not fresh
        if now - self._since >= FRAMES_EVERY:
            self.flush()

    def flush(self):
        if self._gaps:
            span = max(self._clock() - self._since, 1e-6)
            gaps = sorted(self._gaps)
            self._log_line(
                'HUD frames: %d in %.0f s, %.0f ms apart, slowest %.0f ms, %d with no new read; '
                'content %.0f%% and drawing %.0f%% of the time',
                len(gaps),
                span,
                gaps[len(gaps) // 2] * 1000,
                gaps[-1] * 1000,
                self._stale,
                self._worked / span * 100,
                self._drawn / span * 100,
            )
        self.clear()


HISTORY_SETTLE = 1.0  # seconds a dragged layout stays still before it counts as one change


class LayoutHistory:
    """The earlier layouts, for Undo, as long as TurboHUD runs. A state is whatever can be
    compared: the sections and presets. Buttons `record` their change at once. Dragging is
    the desktop's, and TurboHUD only sees where things are when it looks, so `look` takes
    it for one change when it has stood still, however many looks it took."""

    def __init__(self, state):
        self.current = state
        self.past = []
        self._seen = state
        self._changed = None

    def record(self, state):
        """The layout is now `state`: one change, if it differs."""
        if state != self.current:
            self.past.append(self.current)
            self.current = state
        self._seen = state

    def look(self, state, now):
        """What TurboHUD sees at monotonic time `now`, perhaps in the middle of a drag."""
        if state != self._seen:
            self._seen = state
            self._changed = now
        elif state != self.current and now - self._changed >= HISTORY_SETTLE:
            self.record(state)

    def resume(self, state):
        """Move mode begins at `state`. With nothing to undo yet, this is simply the start:
        at first the desktop may report windows a little off from where they were asked."""
        if self.past:
            self.record(state)
        else:
            self.current = self._seen = state

    def can_undo(self, state):
        return bool(self.past) or state != self.current

    def undo(self, state):
        """The layout before the last change, a drag still going on being one; None if
        there is nothing left to go back to."""
        self.record(state)
        if not self.past:
            return None
        self.current = self._seen = self.past.pop()
        return self.current


FREE_STEP = 40  # pixels between the spots free_spot tries
FREE_GAP = 12  # room kept between the panel and a section


def _overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0, min(ay + ah, by + bh) - max(ay, by))


def free_spot(size, screen, boxes, wanted, margin=LAYOUT_MARGIN, step=FREE_STEP, gap=FREE_GAP):
    """(x, y) for a box of `size` on `screen` (x, y, width, height) that covers none of
    `boxes` (x, y, width, height), as near `wanted` (x, y) as possible; if every spot
    covers something, the one covering least. For the move-mode panel, which must not
    hide a section the player wants to drag."""
    width, height = size
    sx, sy, sw, sh = screen
    padded = [(x - gap, y - gap, w + 2 * gap, h + 2 * gap) for x, y, w, h in boxes]
    left, top = sx + margin, sy + margin
    right, bottom = max(left, sx + sw - margin - width), max(top, sy + sh - margin - height)
    xs = sorted({*range(left, right + 1, step), right, min(max(wanted[0], left), right)})
    ys = sorted({*range(top, bottom + 1, step), bottom, min(max(wanted[1], top), bottom)})

    def cost(spot):
        covered = sum(_overlap((spot[0], spot[1], width, height), box) for box in padded)
        return covered, abs(spot[0] - wanted[0]) + abs(spot[1] - wanted[1])

    return min(((x, y) for x in xs for y in ys), key=cost)


def panel_place(size, boxes, screens, margin=LAYOUT_MARGIN):
    """(x, y) for the move-mode panel of `size`: on the screen holding the middle of the
    first of `boxes` (the shown sections; else the main screen), near its middle a third
    down, and covering none of them where it can. `screens` are the usable areas (without
    the menu bar and the Dock). A section just past a screen's edge (seen: at x = -1) no
    longer sends the panel off the screen with it."""
    screen = (screen_of(boxes[0], screens) if boxes else main_screen(screens)) or (0, 0, 1920, 1080)
    sx, sy, sw, sh = screen
    wanted = (sx + (sw - size[0]) // 2, sy + sh // 3)
    return free_spot(size, screen, boxes, wanted, margin=min(margin, max(0, (sh - size[1]) // 2)))


BESIDE_GAP = 20  # between the move-mode panel and the settings window
SCREEN_EDGE = 8  # the least room a window beside the panel keeps from the screen's edges


def beside(size, anchor, screen, gap=BESIDE_GAP, edge=SCREEN_EDGE):
    """(x, y) for a window of `size` next to `anchor` (x, y, width, height), wholly on
    `screen`: to its right if it fits there, else to its left, else as near as the screen
    allows. Its top is level with the anchor's, moved up if it would run off the bottom.
    For the settings window beside the move-mode panel, which may be anywhere."""
    width, height = size
    ax, ay, aw, _ah = anchor
    sx, sy, sw, sh = screen
    left_most, right_most = sx + edge, sx + sw - edge - width
    top_most, bottom_most = sy + edge, sy + sh - edge - height
    if ax + aw + gap <= right_most:
        x = ax + aw + gap
    elif ax - gap - width >= left_most:
        x = ax - gap - width
    else:
        x = right_most
    x = max(left_most, min(x, right_most))  # a window wider than the screen keeps its left edge
    y = max(top_most, min(ay, bottom_most))
    return x, y


def screen_of(place, screens):
    """The screen (x, y, width, height) that holds the middle of `place`, else the
    largest; None without screens."""
    x, y, width, height = place
    cx, cy = x + width / 2, y + height / 2
    for screen in screens:
        sx, sy, sw, sh = screen
        if sx <= cx < sx + sw and sy <= cy < sy + sh:
            return screen
    return main_screen(screens)


def centred(place, screen, horizontal=False, vertical=False):
    """`place` (x, y, width, height) centred on `screen` across (horizontal), down
    (vertical) or both; its size stays."""
    x, y, width, height = place
    sx, sy, sw, sh = screen
    if horizontal:
        x = sx + (sw - width) // 2
    if vertical:
        y = sy + (sh - height) // 2
    return (x, y, width, height)
