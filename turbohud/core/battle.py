"""The battle warning, the first part of the Race Director mode (asked for by the user on 2026-11-16,
started on 2026-11-18): while watching a race (a recording, or spectating), a banner in three rows,
"Battle for P<n>", "Possible Overtake" and "<driver ahead>  vs  <driver behind>", when a car has
come close behind the one ahead and is closing in, or sits right behind it.

As the race leader banner (core.leader) it works only on the race order the standings already make
and on the live gaps (no read of the game of its own), and on the race clock, so a paused replay
holds it where it is. A pair must stay a battle for BATTLE_HOLD seconds before it shows, so a gap
that flickers for a read or two shows nothing; one battle shows at a time, the one for the highest
place; it shows BANNER_SHOWN seconds, fading in and out, and the same two cars not again for
BATTLE_AGAIN seconds."""

from dataclasses import dataclass

from turbohud.core.leader import BANNER_FADE, BANNER_SHOWN, banner_opacity, got_going

BATTLE_GAP = 1.0  # seconds: a car this close behind the one ahead, and closing in, is in a battle
BATTLE_CLOSE = 0.4  # seconds: this close it is a battle whether it gains or not (it sits right behind)
BATTLE_CLOSING = 0.1  # seconds the gap must have shrunk over CLOSING_OVER to count as closing in
CLOSING_OVER = 3.0  # seconds of race clock the gap is compared over
BATTLE_HOLD = 2.0  # seconds a pair must stay a battle before the banner shows
BATTLE_AGAIN = 60.0  # seconds before the same two cars may show again
TITLE = 'Battle for P{place}'
OVERTAKE = 'Possible Overtake'


@dataclass(frozen=True)
class Battle:
    """What the battle banner shows now: the place fought for (1 is the lead), the drivers ahead
    and behind, and how far it is faded in, 0 to 1. `winner` is always False: the banner drawing
    (overlay.window) shares it with the race leader banner, which has a winner's flag."""

    place: int
    ahead: str
    behind: str
    opacity: float
    winner: bool = False

    @property
    def title(self):
        return TITLE.format(place=self.place)


class Battles:
    """Follows the gaps between neighbours in the race order from one read to the next and says
    when the battle banner shows (`update`). A race clock that goes back is a new race (or a
    replay rewound)."""

    def __init__(
        self,
        gap=BATTLE_GAP,
        close=BATTLE_CLOSE,
        closing=BATTLE_CLOSING,
        over=CLOSING_OVER,
        hold=BATTLE_HOLD,
        again=BATTLE_AGAIN,
        shown=BANNER_SHOWN,
        fade=BANNER_FADE,
    ):
        self.gap, self.close, self.closing, self.over = gap, close, closing, over
        self.hold, self.again, self.shown, self.fade = hold, again, shown, fade
        self.reset()

    def reset(self):
        """Forget the race."""
        self._gaps = {}  # (ahead, behind) -> [(race clock, gap in seconds), ...] over the last `over`
        self._since = {}  # (ahead, behind) -> race clock since when they are a battle
        self._shown_at = {}  # (ahead, behind) -> race clock when their banner last began
        self._banner = None  # (place, ahead, behind, race clock when it began)
        self._clock = None

    def update(self, order, clock, gap_of, out=frozenset()):
        """The Battle to show now, or None. `order`: the players in race order (the standings');
        `clock`: the race clock in seconds; `gap_of(ahead, behind)`: how far `behind` is behind
        `ahead` in seconds, or None where not known (a lap or more apart, no positions);
        `out`: names of cars out of the race (retired)."""
        if self._clock is not None and clock < self._clock - 1.0:
            self.reset()
        self._clock = clock
        battles = self._battles(order, clock, gap_of, out)
        if self._banner is None or clock - self._banner[3] > self.shown:
            self._banner = None
            for place, pair in battles:  # the highest place first
                began = self._shown_at.get(pair)
                if began is not None and clock - began < self.again:
                    continue
                if clock - self._since[pair] >= self.hold:
                    self._banner = (place, *pair, clock)
                    self._shown_at[pair] = clock
                    break
        return self._showing(clock)

    def _battles(self, order, clock, gap_of, out):
        """[(place fought for, (ahead, behind))] of the pairs that are a battle now, the highest
        place first; the gaps' history and the times since kept up to date."""
        found = []
        seen = set()
        for index in range(len(order) - 1):
            ahead, behind = order[index], order[index + 1]
            if not self._racing(ahead, out) or not self._racing(behind, out):
                continue
            seconds = gap_of(ahead, behind)
            if seconds is None:
                continue
            pair = (ahead.name, behind.name)
            seen.add(pair)
            history = [(at, g) for at, g in self._gaps.get(pair, ()) if clock - at <= self.over]
            history.append((clock, seconds))
            self._gaps[pair] = history
            if self._is_battle(history, seconds):
                self._since.setdefault(pair, clock)
                found.append((index + 1, pair))
            else:
                self._since.pop(pair, None)
        for pair in list(self._gaps):
            if pair not in seen:  # no longer neighbours, or one is out: start afresh
                self._gaps.pop(pair, None)
                self._since.pop(pair, None)
        return found

    def _is_battle(self, history, seconds):
        if seconds <= self.close:
            return True
        if seconds > self.gap:
            return False
        first_at, first = history[0]
        # Closing in over most of the span compared, so a single read just after a pass is not enough.
        return history[-1][0] - first_at >= self.over / 2 and first - seconds >= self.closing

    @staticmethod
    def _racing(player, out):
        return not player.finished and not player.in_pit and player.name not in out and got_going(player)

    def _showing(self, clock):
        if self._banner is None:
            return None
        place, ahead, behind, began = self._banner
        opacity = banner_opacity(clock - began, self.shown, self.fade)
        if opacity is None:
            return None
        return Battle(place, ahead, behind, opacity)
