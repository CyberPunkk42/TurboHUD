"""The watched driver's banner, the second part of the Race Director mode (asked for by the user on
2026-11-16, started on 2026-11-19): while watching, "Watching" and "P<n>  <name>" each time the
camera turns to another driver, as a TV broadcast names the car it shows.

In a replay the driver is the one TSU's replay camera follows (LapReader._followed, the snapshot's
local player); spectating, the one the spectator camera follows (LapState.followed, the Race
Director mode's third part). The camera must stay on a driver for WATCH_HOLD seconds of
race clock before the banner shows, so flicking through the drivers names only the one stopped at;
it shows BANNER_SHOWN seconds with the race leader banner's fade, and a driver the camera turns to
while one shows takes its place at once, without fading in again. The same driver is not named
again until the camera has turned away from it. A race clock that goes back (a replay rewound)
starts afresh, so the driver is named again."""

from dataclasses import dataclass

from turbohud.core.leader import BANNER_FADE, BANNER_SHOWN, banner_opacity

WATCH_HOLD = 1.0  # seconds of race clock the camera must stay on a driver before the banner names it
WATCHING = 'Watching'


@dataclass(frozen=True)
class Watched:
    """What the watched driver's banner shows now: the driver's name and how far it is faded in,
    0 to 1. `winner` is always False: the banner drawing (overlay.window) shares it with the race
    leader banner, which has a winner's flag."""

    name: str
    opacity: float
    winner: bool = False


class WatchedDriver:
    """Follows the driver the camera follows from one read to the next and says when the
    banner shows (`update`)."""

    def __init__(self, hold=WATCH_HOLD, shown=BANNER_SHOWN, fade=BANNER_FADE):
        self.hold, self.shown, self.fade = hold, shown, fade
        self.reset()

    def reset(self):
        """Forget the race: the next driver followed is named again."""
        self._named = None  # the driver last named
        self._candidate = None  # (name, race clock since when the camera follows it), not named yet
        self._banner = None  # (name, race clock when it began)
        self._clock = None

    def update(self, name, clock):
        """The Watched to show now, or None. `name`: the driver the camera follows, or None where
        none is known; `clock`: the race clock in seconds."""
        if self._clock is not None and clock < self._clock - 1.0:
            self.reset()
        self._clock = clock
        if name is None or name == self._named:
            self._candidate = None
        elif self._candidate is None or self._candidate[0] != name:
            self._candidate = (name, clock)
        elif clock - self._candidate[1] >= self.hold:
            began = clock
            if self._showing(clock) is not None:
                began = clock - self.fade  # one shows: the new name takes its place at full strength
            self._named, self._candidate = name, None
            self._banner = (name, began)
        return self._showing(clock)

    def _showing(self, clock):
        if self._banner is None:
            return None
        name, began = self._banner
        opacity = banner_opacity(clock - began, self.shown, self.fade)
        if opacity is None:
            if clock - began > self.shown:
                self._banner = None
            return None
        return Watched(name, opacity)
