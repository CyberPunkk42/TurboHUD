"""Whether TSU has an event running, from its own log (Linux).

TSU writes a text log into its data folder as things happen: "<time>: Event started."
when a race (or hotlap) begins, "<time>: Event ended." when it is over. The running game
keeps it in `log.txt`; dated copies are in `Logs/log.<date>.<time>.txt`, and a run may have
none yet (seen in CrossOver: `Logs` still ended with the last run's "Event ended" four
minutes into a new event). TurboHUD only reads them, to know when a search of the game's
memory for an online race is worth it; it never writes to the game's folders.

A TSU may also stop writing them: on a tester's Mac (seen 2026-11-11) the newest log was days
old and held only "Log started." and "Log ended.", so TurboHUD took it that no event ever ran
and never looked for a race joined online. So a log says something only when it was written
since TSU started and holds an event line; else it is not known, and the search goes ahead.

A replay leaves no line in the log at all, so a log that last said "Event ended." says nothing
of one playing. Opening a recording does leave its access time on the file, though, which
`RecordingWatch` looks at (only listing the folders, never opening or changing a file).
"""

import os
import time
from pathlib import Path

TAIL = 64 * 1024  # the end of the log that is read: the latest lines
SINCE_SLACK = 2.0  # seconds a log may seem older than TSU's start and still count (clock steps)
STARTED, ENDED = b'Event started.', b'Event ended.'
RECORDINGS, RECORDING_SUFFIX = 'Recordings', '.tsz'  # TSU's replays, in each account's folder
OPENED_SLACK = 2.0  # seconds a recording's access may follow its last write and still be that write


def tsu_data(home=None):
    """TSU's data folder on Linux, holding one folder per Steam account."""
    return Path(home or Path.home()) / '.config' / 'unity3d' / 'Turbo Sliders' / 'Unlimited'


def newest_log(folder):
    """The most recently written log of any account, or None."""
    folder = Path(folder)
    logs = [*folder.glob('*/log.txt'), *folder.glob('*/Logs/log.*.txt')]
    return max(logs, key=lambda path: path.stat().st_mtime, default=None)


def running_in(text):
    """True if the last event in the log text started and has not ended yet, False if it
    ended, None if the text names no event at all."""
    started, ended = text.rfind(STARTED), text.rfind(ENDED)
    if started < 0 and ended < 0:
        return None
    return started > ended


class EventLog:
    """`running()`: True while TSU's log says an event runs, False when it says none
    does, None when there is no log to go by: none, one with no event in it, or one last
    written before `since` (when TSU started, as time.time(); None where not known). Looks
    for the newest log at most every LOOK_EVERY seconds, and reads its end only when it has
    changed."""

    LOOK_EVERY = 5.0

    def __init__(self, folder=None, clock=time.monotonic, since=None):
        self.folder = folder or tsu_data()
        self._clock = clock
        self._since = since
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
            if self._since is not None and info.st_mtime < self._since - SINCE_SLACK:
                return None  # from an earlier run: TSU has not written it since it started
            seen = (self._log, info.st_size, info.st_mtime)
            if seen != self._seen:
                with open(self._log, 'rb') as handle:
                    handle.seek(max(info.st_size - TAIL, 0))
                    self._running = running_in(handle.read())
                self._seen = seen
            return self._running
        except OSError:
            return None


def last_opened(folder):
    """When a recording was last opened after it was written: the latest access time of
    the .tsz files in each account's Recordings folder and the folders in it (Saved,
    Demo), counting only accesses later than the file's last write (as recording it
    leaves them). 0.0 when none was; None when TSU's data folder cannot be listed."""
    newest = 0.0
    try:
        accounts = [entry.path for entry in os.scandir(folder) if entry.is_dir()]
    except OSError:
        return None
    folders = [(os.path.join(account, RECORDINGS), 0) for account in accounts]
    while folders:
        path, depth = folders.pop()
        try:
            entries = list(os.scandir(path))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir():
                    if depth == 0:  # the folders TSU makes in it (Saved, Demo), not deeper
                        folders.append((entry.path, 1))
                    continue
                if not entry.name.lower().endswith(RECORDING_SUFFIX):
                    continue
                info = entry.stat()
            except OSError:
                continue
            if info.st_atime > info.st_mtime + OPENED_SLACK:
                newest = max(newest, info.st_atime)
    return newest


class RecordingWatch:
    """`opened()`: True when TSU opened one of its recordings since the look before, from
    the recordings' access times (last_opened); the first look only notes them. It plays
    a replay then, which TSU's log says nothing of (seen 2026-11-13). Only a hint: Windows
    writes an access time at most about once an hour, Linux (relatime) and macOS more
    rarely still, and a PC may have them turned off. Looks at most every LOOK_EVERY
    seconds, listing the folders without opening a file."""

    LOOK_EVERY = 2.0

    def __init__(self, folder, clock=time.monotonic):
        self.folder = folder
        self._clock = clock
        self._looked = None
        self._newest = None  # the latest opening seen so far

    def opened(self):
        now = self._clock()
        if self._looked is not None and now - self._looked < self.LOOK_EVERY:
            return False
        self._looked = now
        newest = last_opened(self.folder) if self.folder is not None else None
        if newest is None:
            return False
        before, self._newest = self._newest, newest if self._newest is None else max(self._newest, newest)
        return before is not None and newest > before
