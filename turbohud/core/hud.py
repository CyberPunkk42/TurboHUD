"""What the HUD shows and where, as plain data that turbohud.hud draws."""

from dataclasses import dataclass, field

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


FLAG_WIDTH = 1.5  # a flag's room before the text, in font sizes
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
        lines.append(Line(row.text, size, row.color, baseline, row.tail, row.tail_color, row.flag, row.right, row.right_color))
    return lines, baseline


def hud_lines(rows, scale=1.0):
    """The lines of a section's content `rows`, top to bottom."""
    return _content(rows, Sizes.for_scale(scale))[0]


def line_width(line, measure):
    """How wide a line is with its flag and its right column."""
    width = measure(line.text + line.tail, line.size)
    if line.flag:
        width += FLAG_WIDTH * line.size
    if line.right:
        width += COLUMN_GAP * line.size + measure(line.right, line.size)
    return width


def content_size(rows, scale, measure):
    """(width, height) a section needs for `rows` at `scale`. `measure(text, size)` gives
    a text's width in pixels (Qt knows the font)."""
    sizes = Sizes.for_scale(scale)
    lines, bottom = _content(rows, sizes)
    width = max((line_width(line, measure) for line in lines), default=0)
    # Below the last baseline: room for letters such as g and p, then the margin.
    return round(width + 2 * sizes.margin), round(bottom + sizes.margin)


@dataclass(frozen=True)
class Section:
    """One part of the HUD in its own window, placed by the player."""

    name: str  # its key in settings.json
    label: str  # how menus and move mode name it
    samples: tuple  # row lists it may show; the widest and tallest sets its size
    pedals: bool = False  # a throttle bar on its left and a brake bar on its right
    bar: tuple = ()  # (width, height) at scale 1 for a drawing without text
    drawing: str = ''  # what it draws instead of text: 'flag' (blue flag) or 'radar'


RACE_SECTIONS = (
    Section('lap', 'Lap and time left', (
        (Row('Lap 13/13  -  21:00 left', 'title'),),
        (Row('Waiting for TSU (launch option)', 'title'),),
    )),
    Section('current', 'Running lap', ((Row('0:00.0', 'big'),), (Row('10:00.000', 'big'),))),
    Section('delta', 'Delta to best', ((Row('+00.000 vs best', 'medium'),),)),
    Section('times', 'Last and best lap', ((Row('Last 0:00.000   Best 0:00.000', 'medium'),),)),
    Section('fuel', 'Fuel', ((Row('Fuel 100.0%', 'medium', tail='  ~10.0 laps  +0.00%'),),)),
    Section('fuelfinish', 'Fuel to finish', ((Row('Finish +00.0 laps', 'medium'),),)),
    Section('tires', 'Tires', ((Row('Tires 100%  ~10.0 laps', 'medium'),),)),
    Section('speed', 'Speed', ((Row('000 km/h', 'medium'),),), pedals=True),
    Section('localtime', 'Local time', ((Row('00:00', 'medium'),),)),
    Section('players', 'Players', (tuple(
        Row(f'{n}. Playername1234567', 'small', tail='  PIT', flag='DE', right='+00.000') for n in range(10, 10 + 8)
    ),)),
    Section('blueflag', 'Blue flag', (), bar=(480, 24), drawing='flag'),
    Section('radar', 'Proximity radar', (), bar=(160, 160), drawing='radar'),
)
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
    return sizes[0][0] + extra, max(h for _w, h in sizes)


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
    screen = next((s for s in screens if s[0] <= first[0] < s[0] + s[2] and s[1] <= first[1] < s[1] + s[3]), None)
    if screen is not None:
        # Only the sections on that screen count (some may sit on another monitor).
        placed = {
            name: place for name, place in placed.items()
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


def drawing_place(section, size, screen):
    """Where a drawing section goes first: the blue flag at the top centre, the radar
    in the middle a little below the centre, where the eyes are while driving."""
    if section.drawing == 'radar':
        width, height = size
        x, y, screen_width, screen_height = screen
        return (x + (screen_width - width) // 2, y + round(screen_height * RADAR_DOWN), width, height)
    return top_centre(size, screen)


GROUP_TOLERANCE = 3  # pixels: a window this close to where TurboHUD moved it has arrived
GROUP_PENDING = 1.0  # seconds a move TurboHUD asked for may take to arrive


@dataclass
class GroupMover:
    """Moves a group's sections along when the player drags one of them (move mode).

    The desktop moves the dragged window; TurboHUD only sees where windows are when it
    looks (on Wayland only the desktop knows). So `follow` compares each look with the
    one before: if exactly one section of a group has moved, the others are moved by
    the same amount. Their own arrival is then expected, not taken for a drag.
    """

    known: dict = field(default_factory=dict)  # name -> (x, y, width, height) last seen or set
    pending: dict = field(default_factory=dict)  # name -> ((x, y), until) moves asked for

    def follow(self, seen, groups, now):
        """{name: (x, y, width, height)} to move group mates to, for `seen` {name:
        place} at monotonic time `now`; `groups` is {name: group or ''}."""
        moved = {}
        for name, place in seen.items():
            before = self.known.get(name)
            target = self.pending.get(name)
            if target is not None:
                (tx, ty), until = target
                arrived = abs(place[0] - tx) <= GROUP_TOLERANCE and abs(place[1] - ty) <= GROUP_TOLERANCE
                if arrived or now > until:
                    # There (or it never got there): this is its place, not a drag.
                    del self.pending[name]
                    self.known[name] = place
                continue  # else still on its way: neither a drag nor its new place
            if before is not None and tuple(place[:2]) != tuple(before[:2]):
                moved[name] = (place[0] - before[0], place[1] - before[1])
            self.known[name] = place
        moves = {}
        for group in {g for g in groups.values() if g}:
            members = [name for name in seen if groups.get(name) == group]
            movers = [name for name in members if name in moved]
            if len(movers) != 1:
                continue  # nobody dragged, or several moved (not by one drag)
            dx, dy = moved[movers[0]]
            for name in members:
                if name == movers[0] or name not in self.known:
                    continue
                x, y, width, height = self.known[name]
                moves[name] = (x + dx, y + dy, width, height)
        for name, place in moves.items():
            self.known[name] = place
            self.pending[name] = (place[:2], now + GROUP_PENDING)
        return moves
