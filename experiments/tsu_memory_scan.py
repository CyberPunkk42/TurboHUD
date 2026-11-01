"""Find where TSU keeps a lap time in memory, through the memory probe's socket.

TSU stores lap times as whole numbers in steps of 0.1 ms (its `lapTimeIn100us`), so a
lap of 1:35.421 is 954210 to 954219: easy to search for exactly. Start TSU through
`tsu_memory_probe.py` (see experiments/README.md), drive a lap, then:

    python3 -B experiments/tsu_memory_scan.py find 1:35.421     # the lap time the game showed
    (drive another lap)
    python3 -B experiments/tsu_memory_scan.py refine 1:34.870   # keep places that now hold it
    python3 -B experiments/tsu_memory_scan.py show              # list what is left

`find` also takes several times at once (for example best and last lap). Candidates are
kept in .buildtools/memory_scan.json (gitignored). Only reads; never writes to the game.
"""

import json
import re
import socket
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tsu_memory_probe as probe

STATE = Path(__file__).resolve().parents[1] / '.buildtools' / 'memory_scan.json'
UNITS_PER_SECOND = 10_000


def parse_lap_time(text):
    """'1:35.421' -> range of 100 µs values it may stand for (more digits, narrower range)."""
    match = re.fullmatch(r'(?:(\d+):)?(\d+)(?:\.(\d{1,4}))?', text.strip())
    if not match:
        raise ValueError(f'not a lap time: {text!r} (use m:ss.fff)')
    minutes, seconds, fraction = match.groups()
    fraction = fraction or ''
    whole = (int(minutes or 0) * 60 + int(seconds)) * UNITS_PER_SECOND
    step = 10 ** (4 - len(fraction))
    low = whole + int(fraction.ljust(4, '0') or 0)
    return range(low, low + step)


def int32_patterns(values):
    return [struct.pack('<i', value).hex() for value in values]


class Client:
    def __init__(self, path=None):
        self.conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.conn.connect(str(path or probe.socket_path()))
        except OSError:
            sys.exit('No memory probe running. Start TSU through tsu_memory_probe.py first.')

    def ask(self, **request):
        probe.send_message(self.conn, request)
        header, payload = probe.receive_message(self.conn)
        if not header.get('ok'):
            sys.exit(f'Probe error: {header.get("error")}')
        return header, payload


def load_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state))


def keep_matching(addresses, values, wanted):
    """Addresses whose int32 value (hex strings from read_many) lies in `wanted`."""
    kept = []
    for address, value in zip(addresses, values):
        if value is not None and struct.unpack('<i', bytes.fromhex(value))[0] in wanted:
            kept.append(address)
    return kept


def describe(client, addresses, limit=40):
    regions = client.ask(op='maps')[0]['regions']
    values = client.ask(op='read_many', addresses=addresses[:limit], size=4)[0]['values']
    for address, value in zip(addresses[:limit], values):
        number = struct.unpack('<i', bytes.fromhex(value))[0] if value else None
        where = next((r for r in regions if r[0] <= address < r[1]), None)
        label = (where[4] or 'anonymous') if where else '?'
        shown = f'{number / UNITS_PER_SECOND:.4f} s' if number is not None else 'unreadable'
        print(f'{address:#014x}  {shown:>14}  {label}')
    if len(addresses) > limit:
        print(f'... and {len(addresses) - limit} more')


def main(argv):
    if not argv or argv[0] not in ('find', 'refine', 'show'):
        print(__doc__)
        return 1
    command, times = argv[0], argv[1:]
    client = Client()
    if command == 'find':
        if not times:
            sys.exit('Give the lap time the game showed, e.g. 1:35.421')
        wanted = [value for text in times for value in parse_lap_time(text)]
        header, _ = client.ask(op='search', patterns=int32_patterns(wanted), align=4)
        save_state({'addresses': header['hits']})
        print(f'{len(header["hits"])} places hold {", ".join(times)}' + (' (capped)' if header['capped'] else ''))
    elif command == 'refine':
        if not times:
            sys.exit('Give the new lap time, e.g. 1:34.870')
        addresses = load_state().get('addresses', [])
        wanted = {value for text in times for value in parse_lap_time(text)}
        values = client.ask(op='read_many', addresses=addresses, size=4)[0]['values']
        kept = keep_matching(addresses, values, wanted)
        save_state({'addresses': kept})
        print(f'{len(kept)} of {len(addresses)} places now hold {", ".join(times)}')
    addresses = load_state().get('addresses', [])
    if command == 'show' or len(addresses) <= 40:
        describe(client, addresses)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
