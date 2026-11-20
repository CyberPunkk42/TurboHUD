"""The race leader banner (asked for by the user on 2026-11-16, as in Formula 1's TV graphics):
"New Race Leader - <name>" when a new driver has led for LEAD_HOLD seconds, and "Race Winner -
<name>" as soon as TSU has the winner finished. Each shows BANNER_SHOWN seconds in all, fading in
and out over LEADER_FADE.

It works only on the race order the standings already make (no read of the game of its own), and
on the race clock, so a paused replay holds it where it is. The order at a race's start is the
grid's until the first checkpoint, and online the other cars' places may come a moment late, so
no change counts until the leader has passed a checkpoint, and a new leader must keep the lead for
LEAD_HOLD seconds: a car that takes the lead and loses it again, or an order that flickers for a
read or two, shows nothing."""

from dataclasses import dataclass

LEAD_HOLD = 5.0  # seconds a new leader must lead before the banner shows
BANNER_SHOWN = 6.0  # seconds the banner shows in all, fades included
BANNER_FADE = 1.0  # seconds of fading in, and of fading out at the end (the Battle and Watched banners)
# The race leader banner's own, shorter (asked for by the user on 2026-11-20).
LEADER_FADE = 0.67
NEW_LEADER = 'New Race Leader'
WINNER = 'Race Winner'


@dataclass(frozen=True)
class Banner:
    """What the banner shows now: the driver's name, whether the race is won (the checkered
    flag), and how far it is faded in, 0 to 1."""

    name: str
    winner: bool
    opacity: float

    @property
    def title(self):
        return WINNER if self.winner else NEW_LEADER


def banner_opacity(age, shown=BANNER_SHOWN, fade=BANNER_FADE):
    """How far the banner is faded in `age` seconds after it began, 0 to 1; None once it is
    over (or before it began)."""
    if age is None or age < 0 or age > shown:
        return None
    if fade <= 0:
        return 1.0
    return max(0.0, min(1.0, age / fade, (shown - age) / fade))


def got_going(player):
    """Whether a car has passed a checkpoint after the start line: before that the order is the
    grid's, and online it may still be settling."""
    return len(player.passed) >= 2


class LeadChanges:
    """Follows the race leader from one read to the next and says when the banner shows
    (`update`). One for each run of TurboHUD: a race clock that goes back is a new race."""

    def __init__(self, hold=LEAD_HOLD, shown=BANNER_SHOWN, fade=LEADER_FADE):
        self.hold, self.shown, self.fade = hold, shown, fade
        self.reset()

    def reset(self):
        """Forget the race: the next look takes its leader as known."""
        self._leader = None  # the leader known (shown, or there at the start)
        self._candidate = None  # (name, race clock in seconds since when it leads) not yet known
        self._banner = None  # (name, winner, race clock in seconds when it began)
        self._won = False  # the winner is in: no more lead changes this race
        self._clock = None

    def update(self, order, clock, finish_at=None):
        """The Banner to show now, or None. `order`: the players in race order (the standings');
        `clock`: the race clock in seconds; `finish_at(player)`: when that player finished, in
        race clock seconds, or None (from its finish time)."""
        if self._clock is not None and clock < self._clock - 1.0:
            self.reset()  # a new race (or a replay rewound)
        self._clock = clock
        if order:
            self._follow(order[0], clock, finish_at)
        return self._showing(clock)

    def _follow(self, leader, clock, finish_at):
        if self._won:
            return
        if leader.finished:
            self._won = True
            finished = finish_at(leader) if finish_at is not None else None
            # Shown at once; but a winner long in (TurboHUD started after the finish) is old news.
            if finished is None or clock - finished <= self.shown:
                self._banner = (leader.name, True, clock)
            else:
                self._banner = None
            return
        if self._leader is None or not got_going(leader):
            self._leader, self._candidate = leader.name, None  # the start: no change to tell
            return
        if leader.name == self._leader:
            self._candidate = None  # it got the lead back: nothing to tell
            return
        if self._candidate is None or self._candidate[0] != leader.name:
            self._candidate = (leader.name, clock)
            return
        if clock - self._candidate[1] >= self.hold:
            self._leader, self._candidate = leader.name, None
            self._banner = (leader.name, False, clock)

    def _showing(self, clock):
        if self._banner is None:
            return None
        name, winner, began = self._banner
        opacity = banner_opacity(clock - began, self.shown, self.fade)
        if opacity is None:
            if clock - began > self.shown:
                self._banner = None  # over: nothing kept that would draw
            return None
        return Banner(name, winner, opacity)
