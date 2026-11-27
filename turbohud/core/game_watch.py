"""Whether TSU has quit, for Quit with TSU (asked for by drivers on 2026-11-28): TurboHUD quits
once the game it was reading has been gone a while. No Qt here."""

from turbohud.core.race import WAITING_FOR_GAME

# Seconds TSU must stay gone: a connection dropped and made again at once (a read that failed,
# the reader started again) is not the game quitting.
GONE_FOR = 10.0


class GameWatch:
    """Fed the live race's status at each frame; says when TSU, once seen, has been gone for
    GONE_FOR seconds without a break. Started before TSU, TurboHUD waits for it as before."""

    def __init__(self, gone_for=GONE_FOR):
        self.gone_for = gone_for
        self.seen = False  # TSU was read at least once this session
        self.gone_since = None  # when it was last found gone, while it still is

    def gone(self, status, now):
        """True once TSU, seen before, has been gone `gone_for` seconds by `now`."""
        if status != WAITING_FOR_GAME:
            self.seen = True
            self.gone_since = None
            return False
        if not self.seen:
            return False
        if self.gone_since is None:
            self.gone_since = now
        return now - self.gone_since >= self.gone_for
