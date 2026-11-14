"""Short freezes of the whole HUD, for the log.

A tester's log (macOS, 2026-11-13, and already with build 2026.11.12.6) had a read of the race
and a frame of the HUD stop together for 0.15 to 0.35 s, about once a minute: something held
all of TurboHUD at once. Python's garbage collector does that (it holds Python's lock while it
looks through the objects); so does the whole system or CrossOver pausing. These lines tell
them apart: each slow collection, each slow read and frame with its exact time and how much of
it was a collection, and how much of a slow read was the game's memory (the reader, in the
bottle).
"""

import gc
import logging
import time
from collections import deque

STALL = 0.1  # a read or frame at least this slow is logged on its own, with its time
GC_SLOW = 0.02  # a garbage collection at least this slow is logged on its own
GC_KEPT = 512  # the latest collections kept, to tell how much of a slow read or frame they were

log = logging.getLogger(__name__)


def clock_text(wall):
    """`wall` (seconds since the epoch) as the local time to the millisecond: 18:20:41.123."""
    return time.strftime('%H:%M:%S', time.localtime(wall)) + f'.{int(wall * 1000) % 1000:03d}'


class GcWatch:
    """Times Python's garbage collections (gc.callbacks), logs a slow one at once and a summary
    on flush(), and tells how much of a span of time went on them (during)."""

    def __init__(self, clock=time.monotonic, wall=time.time, log_line=None):
        self._clock = clock
        self._wall = wall
        self._log_line = log_line or log.info
        self._spans = deque(maxlen=GC_KEPT)  # (start, end) on `clock`
        self._started = None  # (clock, generation) of the collection under way
        self._installed = False
        self.clear()

    def clear(self):
        self._counts = [0, 0, 0]
        self._total = self._slowest = 0.0
        self._since = self._clock()

    def install(self):
        if not self._installed:
            gc.callbacks.append(self.callback)
            self._installed = True

    def uninstall(self):
        if self._installed:
            gc.callbacks.remove(self.callback)
            self._installed = False

    def callback(self, phase, info):
        """gc.callbacks' call before ('start') and after ('stop') each collection."""
        if phase == 'start':
            self._started = (self._clock(), info.get('generation', 0))
            return
        if self._started is None:
            return
        began, generation = self._started
        self._started = None
        ended = self._clock()
        seconds = ended - began
        self._spans.append((began, ended))
        self._counts[min(generation, 2)] += 1
        self._total += seconds
        self._slowest = max(self._slowest, seconds)
        if seconds >= GC_SLOW:
            self._log_line(
                'slow garbage collection: generation %d, %.0f ms, ended %s (%d objects freed)',
                generation,
                seconds * 1000,
                clock_text(self._wall()),
                info.get('collected', 0),
            )

    def during(self, start, end):
        """Seconds of garbage collection between `start` and `end` (on this watch's clock)."""
        return sum(max(0.0, min(end, stop) - max(start, began)) for began, stop in self._spans)

    def flush(self):
        """The collections since the last flush, in one line; nothing where there were none."""
        if sum(self._counts):
            self._log_line(
                'garbage collections: %d in %.0f s (generation 0: %d, 1: %d, 2: %d), %.0f ms in all, '
                'slowest %.0f ms',
                sum(self._counts),
                self._clock() - self._since,
                *self._counts,
                self._total * 1000,
                self._slowest * 1000,
            )
        self.clear()


watch = GcWatch()  # TurboHUD's own, installed by the app; reads and frames ask it


def slowest_parts(parts, frames, most=4):
    """'laptimes 4.1, players 2.0' from {name: seconds} over `frames` frames: the `most`
    costliest in milliseconds a frame, the largest first."""
    ranked = sorted(parts.items(), key=lambda item: -item[1])[:most]
    return ', '.join(
        f'{name} {seconds / max(frames, 1) * 1000:.1f}' for name, seconds in ranked if seconds > 0
    )
