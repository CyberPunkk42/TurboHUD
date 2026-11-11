"""Where the blue and yellow flags go when both are out (asked for by the user on 2026-11-11:
both may be placed in the same spot). Both stay visible, stacked, and a flag that is already
on the screen never moves, so nothing jumps while the player looks at it:
- the flag that came first stays at its own place;
- one that comes while the other is out, and would overlap it, goes right next to it: the
  blue flag below the yellow box, the yellow box above the blue flag (the other side where
  that would leave the screen);
- it stays there until it goes; then each comes back at its own place next time.
Places are (x, y, width, height) in screen pixels.
"""

GAP = 4  # pixels between two stacked flags
FLAG_SECTIONS = ('yellowflag', 'blueflag')
FIRST = 'yellowflag'  # the section that goes first when both come at once
BELOW = {'blueflag': True, 'yellowflag': False}  # which way each one moves: True is down


def overlap(a, b):
    """Whether boxes `a` and `b` share any area."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def next_to(place, anchor, below, screen):
    """`place` moved up or down to sit right next to `anchor`, on the side `below` asks for,
    or on the other one where that side would leave `screen` (x, y, width, height; None: no
    bounds)."""
    x, _y, width, height = place
    down = anchor[1] + anchor[3] + GAP
    up = anchor[1] - GAP - height
    if screen is not None:
        top, bottom = screen[1], screen[1] + screen[3]
        if below and down + height > bottom:
            below = False
        elif not below and up < top:
            below = True
    return (x, down if below else up, width, height)


class FlagStack:
    """Follows which of the two flags is out to give each its place (see the module)."""

    def __init__(self):
        self.shown = []  # the flags out, in the order they came
        self.moved = {}  # flag -> the place it was given away from its own, while it is out

    def places(self, homes, out, screen=None):
        """{flag: place} for the flags `out` (a set of section names), from their own places
        `homes` {flag: place}; `screen` is the screen's box, or None."""
        self.shown = [name for name in self.shown if name in out]
        for name in sorted(out - set(self.shown), key=lambda n: n != FIRST):
            self.shown.append(name)
        self.moved = {name: place for name, place in self.moved.items() if name in out}
        if len(self.shown) == 2:
            first, second = self.shown
            if second not in self.moved and overlap(homes[first], homes[second]):
                anchor = self.moved.get(first, homes[first])
                self.moved[second] = next_to(homes[second], anchor, BELOW[second], screen)
        return {name: self.moved.get(name, homes[name]) for name in out}

    def reset(self):
        """Every flag back at its own place (move mode, a new layout)."""
        self.shown, self.moved = [], {}
