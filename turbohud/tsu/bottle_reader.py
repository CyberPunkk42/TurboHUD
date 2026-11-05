"""The reader inside TSU's CrossOver bottle: answers read-only questions over a pipe.

macOS refuses a Mac program access to TSU's memory, but a Windows program in the same
bottle may read it (see `turbohud/tsu/winmemory.py`). So TurboHUD (`turbohud/tsu/bottle.py`)
starts this file there with a portable Windows Python and asks it through its standard
input and output, in place of the Linux probe's socket. Only TurboHUD holds the pipe, so
there is no port and no secret, and nothing else can ask.

It can only read: the memory list, bytes, the game's metadata file, whether TSU's log
says an event runs, and a search that goes on only as far as its hits are taken. It ends
when the pipe closes (TurboHUD quit or was killed) or TSU has quit.

Standard library and `winmemory` only: it runs apart from the app. The pure parts run and
test on any system.
"""

import json
import struct
import sys
import time
from pathlib import Path

if __name__ == '__main__':
    # Started as a file: the app's folder holds the package, this file's folder only
    # modules that must not be taken for others.
    sys.path[:] = [p for p in sys.path if Path(p or '.').resolve() != Path(__file__).resolve().parent]
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from turbohud.tsu.gamelog import EventLog
from turbohud.tsu.winmemory import (
    WINE_SEARCH_SHARE,
    WindowsProcess,
    find_process,
    metadata_base,
    metadata_path,
    search,
    tsu_data,
    under_wine,
)

READY = 'turbohud-bottle-reader'  # first message: the pipe really reaches the reader
MAX_READ = 64 * 1024 * 1024
HEADER = struct.Struct('<II')  # sizes of the JSON part and of the bytes after it


def pack(header, payload=b''):
    """One message: the sizes, a JSON header and raw bytes."""
    body = json.dumps(header).encode()
    return HEADER.pack(len(body), len(payload)) + body + payload


def receive(source):
    """(header, payload) of the next message from a binary stream; None once it ended."""
    sizes = source.read(HEADER.size)
    if len(sizes) < HEADER.size:
        return None
    body_size, payload_size = HEADER.unpack(sizes)
    body = source.read(body_size)
    payload = source.read(payload_size) if payload_size else b''
    if len(body) < body_size or len(payload) < payload_size:
        return None
    return json.loads(body), payload


class Service:
    """Answers one request at a time for one open process."""

    def __init__(self, process, metadata_file, event_running, share=1.0):
        self.process = process
        self.metadata_file = metadata_file
        self.event_running = event_running
        self.share = share
        self._search = None

    def handle(self, request):
        """(header, payload) for one request."""
        op = request.get('op')
        if op == 'maps':
            return {'ok': True, 'regions': self.process.regions()}, b''
        if op == 'read':
            size = int(request['size'])
            if not 0 < size <= MAX_READ:
                return {'ok': False, 'error': 'size out of range'}, b''
            began = time.perf_counter()
            data = self.process.read(int(request['address']), size)
            return {'ok': True, 'took': time.perf_counter() - began}, data
        if op == 'metadata':
            metadata = Path(self.metadata_file()).read_bytes()
            base = metadata_base(self.process.regions(), self.process.read, metadata)
            if base is None:
                return {'ok': False, 'error': 'the game metadata is not mapped yet', 'not_ready': True}, b''
            return {'ok': True, 'base': base}, metadata
        if op == 'event_running':
            return {'ok': True, 'running': self.event_running()}, b''
        if op == 'search':
            # Starts a search and replaces any earlier one, which may have been left
            # after its first good hit; nothing is read until the first search_next.
            regions = [(int(start), int(end)) for start, end in request['regions']]
            self._search = search(self.process.read, regions, int(request['value']), share=self.share)
            return {'ok': True}, b''
        if op == 'search_next':
            hit = next(self._search, None) if self._search is not None else None
            return {'ok': True, 'hit': hit}, b''
        return {'ok': False, 'error': f'unknown op {op!r}'}, b''

    def serve(self, source, sink):
        """Answer until the pipe closes, or until a request fails because TSU has quit
        (TurboHUD then sees the pipe close, and looks for the game again)."""
        while True:
            message = receive(source)
            if message is None:
                return
            try:
                header, payload = self.handle(message[0])
            except Exception as error:  # noqa: BLE001 - a failed read is an answer, not an end.
                if not self.process.alive():
                    return
                header, payload = {'ok': False, 'error': str(error)}, b''
            sink.write(pack(header, payload))
            sink.flush()


def main():
    source, sink = sys.stdin.buffer, sys.stdout.buffer
    sys.stdout = sys.stderr  # standard output is the pipe: nothing else may write there
    pid = find_process('TSU.exe')
    if pid is None:
        sink.write(pack({'ok': False, 'error': 'TSU.exe is not running in this bottle'}))
        sink.flush()
        return 1
    process = WindowsProcess(pid)
    try:
        sink.write(pack({'ok': True, 'ready': READY}))
        sink.flush()
        service = Service(
            process,
            lambda: metadata_path(process.image_path()),
            EventLog(tsu_data()).running,
            WINE_SEARCH_SHARE if under_wine() else 1.0,
        )
        service.serve(source, sink)
    finally:
        process.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
