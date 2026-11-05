"""TSU's live race on the Mac, through a reader inside its CrossOver bottle.

macOS refuses a Mac program access to TSU's memory (CrossOver's Wine loader is signed
with the hardened runtime), so TurboHUD looks for TSU among the running programs, finds
CrossOver and the bottle, and starts `turbohud/tsu/bottle_reader.py` there with a
portable Windows Python. `Bottle.connect` then gives `LiveRace` a race reader, as the
Linux probe's `connect` does. The page cache is on this side: a question through the pipe
costs about 15 µs, a read of the game about 250 µs.

Nothing here changes the bottle: the reader is run from outside it, and installs nothing.
"""

import json
import logging
import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path

from turbohud.core.il2cpp import Il2Cpp, Memory, NotFound, ReadError
from turbohud.core.race import LapReader
from turbohud.core.settings import settings_dir
from turbohud.tsu.bottle_reader import HEADER, READY, pack
from turbohud.tsu.winmemory import CachedReader, PageCache, searchable

START_TIMEOUT = 30.0  # seconds for a reader to start: a sleeping bottle wakes up slowly
TIMEOUT = 5.0  # seconds before a silent reader counts as stuck
SEARCH_TIMEOUT = 300.0  # a paced search of all the game's data takes under a minute
RETRY_START = 10.0  # seconds before trying again after a reader failed to start: each try wakes Wine
READER_LOG = 'bottle_reader.log'  # beside the settings: Python's errors from the bottle
WINE = 'Contents/SharedSupport/CrossOver/bin/wine'
BOTTLES = Path('Library') / 'Application Support' / 'CrossOver' / 'Bottles'
TSU_PROCESS = re.compile(r'^\s*(\d+)\s+[A-Za-z]:\\.*\\TSU\.exe(\s|$)', re.IGNORECASE | re.MULTILINE)
BOTTLE_PATH = re.compile(r'/Bottles/([^/\n]+)/')

log = logging.getLogger(__name__)


def tsu_pid(listing):
    """The process ID of TSU in `ps -axo pid=,args=` text, or None. Wine shows a Windows
    program by its Windows path, so only the game itself matches, not what mentions it."""
    found = TSU_PROCESS.search(listing)
    return int(found.group(1)) if found else None


def bottle_named_in(files):
    """The bottle in a process's list of open files (`lsof -Fn`), or None."""
    found = BOTTLE_PATH.search(files)
    return found.group(1) if found else None


def windows_path(path):
    """A Mac path as Wine sees it: the whole disk is drive Z:."""
    return 'Z:' + str(path).replace('/', '\\')


def find_crossover(home=None, spotlight=None):
    """CrossOver's `wine` launcher: in the usual places, then wherever Spotlight knows."""
    home = Path(home or Path.home())
    for app in (home / 'Applications' / 'CrossOver.app', Path('/Applications/CrossOver.app')):
        if (app / WINE).exists():
            return app / WINE
    spotlight = spotlight or _spotlight
    for line in spotlight().splitlines():
        if line and (Path(line) / WINE).exists():
            return Path(line) / WINE
    return None


def _spotlight():
    query = "kMDItemCFBundleIdentifier == 'com.codeweavers.CrossOver'"
    return _output(['mdfind', query])


def _output(command):
    try:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            errors='replace',
            timeout=TIMEOUT,
            check=False,
        ).stdout
    except subprocess.TimeoutExpired:
        raise TimeoutError(f'{command[0]} does not answer') from None


def app_files(bundle=None):
    """(Windows Python, the reader's file): inside the bundled app, or for a start from
    the source in `.buildtools/win-python` (set up by `tools/get_windows_python.sh`)."""
    bundle = getattr(sys, '_MEIPASS', None) if bundle is None else bundle
    if bundle:
        return Path(bundle) / 'win-python' / 'python.exe', Path(
            bundle
        ) / 'turbohud' / 'tsu' / 'bottle_reader.py'
    root = Path(__file__).resolve().parents[2]
    return root / '.buildtools' / 'win-python' / 'python.exe', root / 'turbohud' / 'tsu' / 'bottle_reader.py'


class Pipe:
    """Questions to a reader over its standard input and output. Raises ConnectionError
    when it has ended, TimeoutError when it has gone silent, ReadError when it refuses."""

    def __init__(self, sink, source_fd, on_close=None):
        self.sink = sink
        self.source_fd = source_fd
        self.on_close = on_close
        self.metadata = None  # (base, bytes), kept while this reader lasts
        self.in_game = 0.0  # seconds its reads have spent on the game's memory, for the log

    def _take(self, size, timeout):
        chunks = []
        while size:
            ready, _, _ = select.select([self.source_fd], [], [], timeout)
            if not ready:
                raise TimeoutError('the reader in the bottle does not answer')
            chunk = os.read(self.source_fd, min(size, 1 << 20))
            if not chunk:
                raise ConnectionError('the reader in the bottle has ended')
            chunks.append(chunk)
            size -= len(chunk)
        return b''.join(chunks)

    def receive(self, timeout=TIMEOUT):
        body_size, payload_size = HEADER.unpack(self._take(HEADER.size, timeout))
        header = json.loads(self._take(body_size, timeout))
        return header, self._take(payload_size, timeout)

    def ask(self, request, timeout=TIMEOUT):
        try:
            self.sink.write(pack(request))
            self.sink.flush()
        except BrokenPipeError:
            raise ConnectionError('the reader in the bottle has ended') from None
        header, payload = self.receive(timeout)
        if not header.get('ok'):
            if header.get('not_ready'):
                raise NotFound(header.get('error'))
            raise ReadError(header.get('error'))
        return header, payload

    def read(self, address, size):
        header, payload = self.ask({'op': 'read', 'address': address, 'size': size})
        self.in_game += header.get('took', 0.0)
        return payload

    def maps(self):
        """The game's memory as it is now: it grows as the game goes from menu to race."""
        return [tuple(item) for item in self.ask({'op': 'maps'})[0]['regions']]

    def event_running(self):
        return self.ask({'op': 'event_running'})[0]['running']

    def search(self, regions, value):
        """Addresses holding the 64-bit `value`, lowest first. Asks for one hit at a time,
        so a lookup that stops at its first good hit leaves the rest of the game unread."""
        self.ask({'op': 'search', 'regions': [list(r[:2]) for r in regions], 'value': value})
        while True:
            hit = self.ask({'op': 'search_next'}, SEARCH_TIMEOUT)[0]['hit']
            if hit is None:
                return
            yield hit

    def find_pointers(self, value):
        return self.search([r for r in self.maps() if searchable(r)], value)

    def game_metadata(self):
        """(where it is mapped, its bytes)."""
        if self.metadata is None:
            header, payload = self.ask({'op': 'metadata'}, START_TIMEOUT)
            self.metadata = header['base'], payload
        return self.metadata

    def close(self):
        if self.on_close is not None:
            self.on_close()
            self.on_close = None


class Bottle:
    """Starts the reader for the running TSU and connects to it. Its reader stays up
    while a game loads, so each new try does not start another."""

    def __init__(self, environ=None, home=None, output=_output, start=None, clock=time.monotonic):
        self.environ = os.environ if environ is None else environ
        self.home = Path(home or Path.home())
        self.output = output
        self.start = start or self._start
        self.clock = clock
        self.pipe = None
        self.failed = None  # (when to try again, why the last start failed)

    def bottle_of(self, pid):
        """The bottle TSU runs in: as asked for, else from its open files, else the only
        one there is."""
        name = self.environ.get('TURBOHUD_BOTTLE')
        if name:
            return name
        name = bottle_named_in(self.output(['lsof', '-p', str(pid), '-Fn']))
        if name:
            return name
        try:
            bottles = sorted(path.name for path in (self.home / BOTTLES).iterdir() if path.is_dir())
        except OSError:
            bottles = []
        if len(bottles) == 1:
            return bottles[0]
        raise OSError('cannot tell which CrossOver bottle TSU runs in (set TURBOHUD_BOTTLE)')

    def _start(self, bottle):
        """A new reader in `bottle`: Popen, its Pipe."""
        wine = find_crossover(self.home)
        if wine is None:
            raise OSError('CrossOver was not found')
        python, reader = app_files()
        if not python.exists():
            raise OSError(f'the Windows Python is missing: {python}')
        command = [str(wine), '--bottle', bottle, str(python), '-I', '-B', windows_path(reader)]
        try:
            folder = settings_dir()
            folder.mkdir(parents=True, exist_ok=True)
            errors = (folder / READER_LOG).open('wb')
        except OSError:
            errors = subprocess.DEVNULL
        try:
            # WINEDEBUG: Wine's own notes would fill the log with lines about the bottle.
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=errors,
                bufsize=0,
                env={**self.environ, 'WINEDEBUG': '-all'},
            )
        finally:
            if errors is not subprocess.DEVNULL:
                errors.close()

        def finish():
            # The pipe closing ends the reader, however TurboHUD ends.
            for stream in (process.stdin, process.stdout):
                stream.close()
            try:
                process.wait(2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

        return Pipe(process.stdin, process.stdout.fileno(), finish)

    def _open(self):
        if self.pipe is not None:
            return self.pipe
        pid = tsu_pid(self.output(['ps', '-axww', '-o', 'pid=,args=']))
        if pid is None:
            self.failed = None  # a game started later starts afresh
            raise OSError('TSU is not running in CrossOver')
        if self.failed is not None and self.clock() < self.failed[0]:
            raise OSError(self.failed[1])
        started = self.clock()
        try:
            bottle = self.bottle_of(pid)
            pipe = self.start(bottle)
            try:
                header, _payload = pipe.receive(START_TIMEOUT)
                if not header.get('ok') or header.get('ready') != READY:
                    raise OSError(header.get('error') or 'an unknown answer from the bottle')
            except BaseException:
                pipe.close()
                raise
        except OSError as error:
            log.warning('the reader in the bottle did not start: %s', error)
            self.failed = self.clock() + RETRY_START, str(error)
            raise
        log.info(
            'reading TSU through a reader in the CrossOver bottle %s, started in %.1f s',
            bottle,
            self.clock() - started,
        )
        self.failed = None
        self.pipe = pipe
        return pipe

    def connect(self):
        """(race reader, this Bottle) for `LiveRace`. Raises OSError while TSU does not
        run or the reader cannot start, NotFound while the game is still loading."""
        pipe = self._open()
        try:
            base, metadata = pipe.game_metadata()
            cache = PageCache(pipe.read)
            memory = Memory(
                cache.read,
                pipe.maps,  # listed anew for each search: see Pipe.maps
                find_pointers=pipe.find_pointers,
                searcher=pipe.search,
            )
            reader = LapReader(Il2Cpp(memory, metadata, base), event_running=pipe.event_running)
            return CachedReader(reader, cache, lambda: pipe.in_game), self
        except (NotFound, ReadError):
            raise  # the game is loading: the same reader tries again
        except BaseException as error:
            log.warning('the reader in the bottle failed: %s', error)
            self.close()
            raise

    def close(self):
        if self.pipe is not None:
            log.info('closing the reader in the bottle')
            self.pipe.close()
            self.pipe = None
