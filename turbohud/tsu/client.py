"""TSU's live race data through the memory probe's socket (Linux).

`connect()` opens the probe's socket and returns a LapReader on the game. `LiveRace`
keeps reading in a background thread and always has the latest Snapshot ready, so the
overlay never waits for the game. Everything here only reads.
"""

import logging
import socket
import statistics
import struct
import sys
import threading
import time
from pathlib import Path

from turbohud.core import stalls
from turbohud.core.il2cpp import Il2Cpp, Memory, NotFound, ReadError
from turbohud.core.race import RACING, STARTING, WAITING_FOR_GAME, WAITING_FOR_RACE, LapReader, Snapshot
from turbohud.core.stalls import STALL, clock_text
from turbohud.tsu.gamelog import EventLog, RecordingWatch, tsu_data
from turbohud.tsu.probe import receive_message, send_message, socket_path

READ_SWITCH_INTERVAL = 0.001  # seconds a thread waits for Python's lock before it asks for it
LEAST_WAIT = 0.005  # seconds after a read that took its whole interval, for the game's sake
READ_INTERVAL = 0.05  # seconds between reads in a race: the live delta updates 20 times a second
WAIT_INTERVAL = 1.0  # seconds between tries while TSU or a race is not there
TIMEOUT = 5.0  # seconds before a silent probe counts as gone
TIMES_EVERY = 30.0  # seconds between the log's lines on how long race reads take
DETAIL_LOG_EVERY = 10.0  # seconds between lines saying why there is still no race, when that changes
# What the reader says while a session sets up its race (seen in drives): the race
# objects are not there yet. In the menu it says m_activeServer is null instead.
STARTING_SIGNS = ('m_eventListener is null', 'm_eventState is null', 'no local player')

log = logging.getLogger(__name__)


class ProbeConnection:
    """One connection to the probe; `read` and `maps` raise OSError when it is gone."""

    def __init__(self, path=None):
        self.conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.conn.settimeout(TIMEOUT)
        try:
            self.conn.connect(str(path or socket_path()))
        except OSError:
            self.conn.close()
            raise

    def ask(self, request):
        send_message(self.conn, request)
        header, data = receive_message(self.conn)
        if not header.get('ok'):
            raise ReadError(header.get('error'))
        return header, data

    def read(self, address, size):
        return self.ask({'op': 'read', 'address': address, 'size': size})[1]

    def read_many(self, addresses, size):
        values = self.ask({'op': 'read_many', 'addresses': addresses, 'size': size})[0]['values']
        return [bytes.fromhex(value) if value is not None else None for value in values]

    def maps(self):
        return self.ask({'op': 'maps'})[0]['regions']

    def find_pointers(self, value):
        """Addresses in the game's data that hold the 64-bit `value` (8-aligned), searched
        inside the probe: for finding a class's objects by their class pointer."""
        return self.ask({'op': 'search', 'patterns': [struct.pack('<Q', value).hex()], 'align': 8})[0]['hits']

    def close(self):
        self.conn.close()


def connect(path=None):
    """(LapReader, connection) on TSU through the probe. Raises OSError if TSU is not
    running through the probe."""
    conn = ProbeConnection(path)
    try:
        regions = conn.maps()
        metadata = next((r for r in regions if r[4].endswith('global-metadata.dat') and r[3] == 0), None)
        if metadata is None:
            raise NotFound('the game metadata is not mapped yet')
        memory = Memory(conn.read, regions, conn.read_many, conn.find_pointers)
        il2cpp = Il2Cpp(memory, Path(metadata[4]).read_bytes(), metadata[0])
        reader = LapReader(
            il2cpp, event_running=EventLog().running, recording_opened=RecordingWatch(tsu_data()).opened
        )
        return reader, conn
    except BaseException:
        conn.close()
        raise


class ReadTimes:
    """Logs how long race reads take every TIMES_EVERY seconds, so a drive leaves numbers
    to go by when the HUD lagged. A read longer than READ_INTERVAL misses an update.

    A read at least stalls.STALL long is also logged at once (a tester's stutter, 2026-11-13):
    its time, how much of it was the game's memory (the reader, in CrossOver's bottle on the
    Mac) and how much garbage collection (`gc_during`, on `clock`), which tell a pause in the
    bottle from one in TurboHUD."""

    def __init__(self, clock, gc_during=None, wall=time.time):
        self._clock = clock
        self._gc_during = gc_during
        self._wall = wall
        self._times = []
        self._details = []  # (trips, seconds on the game's memory or None, seconds in all, reads of it or None)
        self._since = None

    def add(self, seconds, detail=None):
        """`detail`: (trips for the game's memory, seconds on it or None[, reads of it or
        None]), where known."""
        now = self._clock()
        if self._since is None:
            self._since = now - seconds
        self._times.append(seconds)
        if seconds >= STALL:
            self._slow(seconds, now, detail)
        if detail is not None:
            trips, in_game, *more = detail
            self._details.append((trips, in_game, seconds, more[0] if more else None))
        if now - self._since >= TIMES_EVERY:
            self.flush()

    def _slow(self, seconds, now, detail):
        trips, in_game = (detail[0], detail[1]) if detail is not None else (None, None)
        log.info(
            'slow race read: %.0f ms, ended %s; %s trips, %s on the game\'s memory; garbage collection in it %.0f ms',
            seconds * 1000,
            clock_text(self._wall()),
            '?' if trips is None else trips,
            '?' if in_game is None else f'{in_game * 1000:.1f} ms',
            (self._gc_during(now - seconds, now) if self._gc_during else 0.0) * 1000,
        )

    def flush(self):
        if self._times:
            log.info(
                'race reads: %d in %.0f s, median %.1f ms, slowest %.1f ms, %d over %.0f ms%s',
                len(self._times),
                self._clock() - self._since,
                statistics.median(self._times) * 1000,
                max(self._times) * 1000,
                sum(seconds > READ_INTERVAL for seconds in self._times),
                READ_INTERVAL * 1000,
                self._detail_text(),
            )
        self._times, self._details, self._since = [], [], None

    def _detail_text(self):
        """Whether a slow read made many trips or each trip was slow, and whether that was
        the game's memory: what the times alone cannot tell."""
        trips = [detail[0] for detail in self._details if detail[0]]
        if not trips:
            return ''
        each = [detail[2] / detail[0] for detail in self._details if detail[0]]
        text = (
            f'; {statistics.median(trips):.0f} trips a read, {statistics.median(each) * 1000:.2f} ms a trip'
        )
        in_game = [detail[1] / detail[0] for detail in self._details if detail[0] and detail[1] is not None]
        if in_game:
            text += f', {statistics.median(in_game) * 1000:.2f} ms of it on the game\'s memory'
        calls = [detail[3] for detail in self._details if detail[0] and detail[3] is not None]
        if calls:
            text += f', {statistics.median(calls):.0f} reads of it a read'
        return text


class LiveRace:
    """Reads the race in a background thread; `snapshot()` gives the latest result."""

    def __init__(self, connect=connect, clock=time.monotonic, close=None, warning=None):
        self._connect = connect
        self.warning = warning or (lambda: None)  # what to tell the player, for the tray icon
        self._clock = clock
        self.read_interval = READ_INTERVAL  # seconds between reads in a race; may change at any time
        self._close = close  # what stays open between connects, to end at stop()
        self.on_read = None  # called from the reading thread after each race read
        self._times = ReadTimes(clock, stalls.watch.during if clock is time.monotonic else None)
        self._lock = threading.Lock()
        self._snapshot = Snapshot()
        self._stop = threading.Event()
        self._thread = None
        self._reader = self._conn = None
        self._detail_logged = (None, None)  # (the detail, when) last logged while waiting

    def snapshot(self):
        with self._lock:
            return self._snapshot

    def start(self):
        # This thread lets go of Python's lock at every trip to the game's memory. By default
        # it then waits 5 ms for it while the overlay draws, about a second for a race read
        # of 70 trips (seen in races on the Mac).
        sys.setswitchinterval(READ_SWITCH_INTERVAL)
        self._thread = threading.Thread(target=self._run, name='tsu-live-race', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._times.flush()
        self._drop()
        if self._close is not None:
            self._close()

    def _set(self, snapshot):
        with self._lock:
            old = self._snapshot
            self._snapshot = snapshot
        now = self._clock()
        if old.status != snapshot.status:
            if old.status == RACING:
                self._times.flush()  # the race's last numbers, before what follows it
            log.info('TSU: %s%s', snapshot.status, f' ({snapshot.detail})' if snapshot.detail else '')
            self._detail_logged = (snapshot.detail, now)
        # Still no race, for another reason: worth a line, as a race found but not read
        # (seen 2026-11-11) looked like waiting all along. Not more often than this, as a
        # reason can come and go with each read.
        elif (
            snapshot.status != RACING
            and snapshot.detail != self._detail_logged[0]
            and (self._detail_logged[1] is None or now - self._detail_logged[1] >= DETAIL_LOG_EVERY)
        ):
            log.info('TSU: still %s (%s)', snapshot.status, snapshot.detail)
            self._detail_logged = (snapshot.detail, now)

    def _drop(self):
        if self._conn is not None:
            self._conn.close()
        self._reader = self._conn = None

    def step(self):
        """One read; returns the seconds to wait before the next."""
        began = self._clock()
        try:
            if self._reader is None:
                self._reader, self._conn = self._connect()
            started = self._clock()
            state = self._reader.read()
            if self.snapshot().status == RACING:  # a race's first read also finds the race
                self._times.add(self._clock() - started, getattr(self._reader, 'last_read', None))
        except (NotFound, ReadError) as error:
            # In the menu (no session: no active server), or a session whose race is
            # being set up, or a pointer led nowhere between two states.
            status = STARTING if any(sign in str(error) for sign in STARTING_SIGNS) else WAITING_FOR_RACE
            self._set(Snapshot(status, read_at=self._clock(), detail=str(error)))
            return WAIT_INTERVAL if status == WAITING_FOR_RACE else self.read_interval
        except (OSError, ValueError, KeyError, StopIteration) as error:
            # Not started through the probe, or TSU quit (the socket closed).
            if self._conn is not None:
                # A connection that worked is closed: say why, as the status may not change
                # (TSU just started) and would then log nothing.
                log.info('TSU: connection dropped (%s: %s)', type(error).__name__, error)
            self._drop()
            self._set(Snapshot(WAITING_FOR_GAME, read_at=self._clock(), detail=str(error)))
            return WAIT_INTERVAL
        previous = self.snapshot()
        before = previous.state
        running = before is not None and state.clock > before.clock
        now = self._clock()
        moved_at = now if running or before is None else previous.moved_at
        self._set(Snapshot(RACING, state, running, now, moved_at=moved_at))
        if self.on_read is not None:
            self.on_read()
        # read_interval from the start of this read to the start of the next.
        return max(self.read_interval - (now - began), LEAST_WAIT)

    def _run(self):
        while not self._stop.is_set():
            try:
                wait = self.step()
            except Exception:  # The overlay must keep running whatever the game does.
                log.exception('reading TSU failed')
                self._drop()
                wait = WAIT_INTERVAL
            self._stop.wait(wait)
