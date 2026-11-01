"""TSU's live race data through the memory probe's socket (Linux).

`connect()` opens the probe's socket and returns a LapReader on the game. `LiveRace`
keeps reading in a background thread and always has the latest Snapshot ready, so the
overlay never waits for the game. Everything here only reads.
"""

import logging
import socket
import threading
import time
from pathlib import Path

from turbohud.core.il2cpp import Il2Cpp, Memory, NotFound, ReadError
from turbohud.core.race import RACING, STARTING, WAITING_FOR_GAME, WAITING_FOR_RACE, LapReader, Snapshot
from turbohud.tsu.probe import receive_message, send_message, socket_path

READ_INTERVAL = 0.05  # seconds between reads in a race: the live delta updates 20 times a second
WAIT_INTERVAL = 1.0  # seconds between tries while TSU or a race is not there
TIMEOUT = 5.0  # seconds before a silent probe counts as gone
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
        il2cpp = Il2Cpp(Memory(conn.read, regions, conn.read_many), Path(metadata[4]).read_bytes(), metadata[0])
        return LapReader(il2cpp), conn
    except BaseException:
        conn.close()
        raise


class LiveRace:
    """Reads the race in a background thread; `snapshot()` gives the latest result."""

    def __init__(self, connect=connect, clock=time.monotonic):
        self._connect = connect
        self._clock = clock
        self._lock = threading.Lock()
        self._snapshot = Snapshot()
        self._stop = threading.Event()
        self._thread = None
        self._reader = self._conn = None

    def snapshot(self):
        with self._lock:
            return self._snapshot

    def start(self):
        self._thread = threading.Thread(target=self._run, name='tsu-live-race', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._drop()

    def _set(self, snapshot):
        with self._lock:
            old = self._snapshot
            self._snapshot = snapshot
        if old.status != snapshot.status:
            log.info('TSU: %s%s', snapshot.status, f' ({snapshot.detail})' if snapshot.detail else '')

    def _drop(self):
        if self._conn is not None:
            self._conn.close()
        self._reader = self._conn = None

    def step(self):
        """One read; returns the seconds to wait before the next."""
        try:
            if self._reader is None:
                self._reader, self._conn = self._connect()
            state = self._reader.read()
        except (NotFound, ReadError) as error:
            # In the menu (no session: no active server), or a session whose race is
            # being set up, or a pointer led nowhere between two states.
            status = STARTING if any(sign in str(error) for sign in STARTING_SIGNS) else WAITING_FOR_RACE
            self._set(Snapshot(status, read_at=self._clock(), detail=str(error)))
            return WAIT_INTERVAL if status == WAITING_FOR_RACE else READ_INTERVAL
        except (OSError, ValueError, KeyError, StopIteration) as error:
            # Not started through the probe, or TSU quit (the socket closed).
            self._drop()
            self._set(Snapshot(WAITING_FOR_GAME, read_at=self._clock(), detail=str(error)))
            return WAIT_INTERVAL
        before = self.snapshot().state
        running = before is not None and state.clock > before.clock
        self._set(Snapshot(RACING, state, running, self._clock()))
        return READ_INTERVAL

    def _run(self):
        while not self._stop.is_set():
            try:
                wait = self.step()
            except Exception:  # The overlay must keep running whatever the game does.
                log.exception('reading TSU failed')
                self._drop()
                wait = WAIT_INTERVAL
            self._stop.wait(wait)
