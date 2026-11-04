"""Whether TSU has an event running, from its own log (Linux).

TSU writes a text log into its data folder as things happen: "<time>: Event started."
when a race (or hotlap) begins, "<time>: Event ended." when it is over. The running game
keeps it in `log.txt`; dated copies are in `Logs/log.<date>.<time>.txt`, and a run may have
none yet (seen in CrossOver: `Logs` still ended with the last run's "Event ended" four
minutes into a new event). TurboHUD only reads them, to know when a search of the game's
memory for an online race is worth it; it never writes to the game's folders.
"""

import time
from pathlib import Path

TAIL = 64 * 1024  # the end of the log that is read: the latest lines
STARTED, ENDED = b'Event started.', b'Event ended.'


def tsu_data(home=None):
    """TSU's data folder on Linux, holding one folder per Steam account."""
    return Path(home or Path.home()) / '.config' / 'unity3d' / 'Turbo Sliders' / 'Unlimited'


def newest_log(folder):
    """The most recently written log of any account, or None."""
    folder = Path(folder)
    logs = [*folder.glob('*/log.txt'), *folder.glob('*/Logs/log.*.txt')]
    return max(logs, key=lambda path: path.stat().st_mtime, default=None)


def running_in(text):
    """True if the last event in the log text started and has not ended yet."""
    started = text.rfind(STARTED)
    return started >= 0 and started > text.rfind(ENDED)


class EventLog:
    """`running()`: True while TSU's log says an event runs, False when it says none
    does, None when there is no log to go by. Looks for the newest log at most every
    LOOK_EVERY seconds, and reads its end only when it has changed."""

    LOOK_EVERY = 5.0

    def __init__(self, folder=None, clock=time.monotonic):
        self.folder = folder or tsu_data()
        self._clock = clock
        self._log = None
        self._looked = None
        self._seen = None  # (path, size, mtime) last read
        self._running = None

    def running(self):
        now = self._clock()
        try:
            if self._looked is None or now - self._looked >= self.LOOK_EVERY:
                self._looked = now
                self._log = newest_log(self.folder)
            if self._log is None:
                return None
            info = self._log.stat()
            seen = (self._log, info.st_size, info.st_mtime)
            if seen != self._seen:
                with open(self._log, 'rb') as handle:
                    handle.seek(max(info.st_size - TAIL, 0))
                    self._running = running_in(handle.read())
                self._seen = seen
            return self._running
        except OSError:
            return None
