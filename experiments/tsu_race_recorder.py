r"""Record every car of a race, and each event's mode, to work out yellow flags and the arena modes.

What TurboHUD would need for a yellow flag is the state of the other cars: off the track, slow or
stopped, spun, wrecked. This records, while the user drives:

- 10 times a second, what TurboHUD reads of every car (position, velocity, the way its nose points,
  in the pits, laps and checkpoints), as the HUD sees it;
- the track's checkpoint lines (whether they reach the track's edges is one of the questions);
- twice a second, every simple field of each car's TS.EventPlayer, TS.Vehicle, its state and its
  state updater, and of the objects they point to whose names sound useful (wreck, stuck, respawn,
  wrong way, surface, wheels, shortcut): only the fields that changed, so the file stays small;
- for every event, its type (`kind: event`: mode, level type, the classes of its objects), and twice
  a second every simple field of the event's state, controller, logic and settings, and of the
  objects they point to whose names sound like a mode's (score, team, flag, hill, zone, ball, goal,
  round): only the fields that changed, as `player: -1`. Also while the race itself cannot be read,
  as may be so in an arena mode (Sumo, King of the Hill, Capture the flag, Battle, Soccer, Tag).

Afterwards the file tells which of TSU's fields change for which cars (the local one, AI, other
players online) when a car leaves the track, stops, spins or is wrecked, and what each event mode
keeps (scores, the hill, the flags).

Start TSU (TurboHUD may run too: both only read), then from the repository:

    .buildtools/venv/bin/python -B experiments/tsu_race_recorder.py              # Mac, until Ctrl+C
    .buildtools\venv\Scripts\python.exe -B experiments\tsu_race_recorder.py     # Windows
    ... --minutes 15                                                             # stop after 15 min

On the Mac it reads through the reader in the bottle, on Windows TSU straight. It waits for a race,
records until Ctrl+C (or the minutes are up), and writes `race-<date>-<time>.jsonl.gz` to
~/Library/Application Support/TurboHUD/recordings (Mac) or %APPDATA%\TurboHUD\recordings
(Windows). That file holds player names: it stays on this computer and never goes into the
repository. Only reads TSU's memory.
"""

import argparse
import gzip
import json
import logging
import os
import re
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core.il2cpp import SIMPLE_TYPES, TYPE_VALUETYPE, NotFound, ReadError

RACE_EVERY = 0.1  # seconds between race reads
FIELDS_EVERY = 0.5  # seconds between looks at the raw fields
REFERENCE_TYPES = (0x12, 0x15, 0x1C)  # class, generic instance, object
TYPE_STRING = 0x0E
DEPTH = 2  # steps from a car's own objects that are followed, by interesting names
# Objects one step from a car's own that are worth a look, by the name of the field leading there.
INTERESTING = re.compile(
    r'wreck|stuck|respawn|wrongway|surface|wheel|shortcut|damage|health|ground|recorder', re.IGNORECASE
)
# Objects one step from the event's own that are worth a look, by the name of the field leading there.
EVENT_INTERESTING = re.compile(
    r'mode|score|team|flag|hill|zone|ball|goal|round|point|tag|sumo|arena|battle|collect|capture|king',
    re.IGNORECASE,
)
EVENT_PLAYER = -1  # the `player` of the event's own records


def folder(platform=sys.platform, environ=None, home=None):
    """Where recordings go: beside TurboHUD's settings, never in the repository."""
    environ = os.environ if environ is None else environ
    home = Path(home or Path.home())
    if platform == 'win32':
        return Path(environ.get('APPDATA') or home) / 'TurboHUD' / 'recordings'
    return home / 'Library' / 'Application Support' / 'TurboHUD' / 'recordings'


def rounded(value):
    return round(value, 4) if isinstance(value, float) else value


class FieldReader:
    """Reads every instance field of an object in one go, by its class's field list.
    `text` reads a System.String at an address (LapReader._string)."""

    def __init__(self, il, text):
        self.il = il
        self.text = text
        self.layouts = {}  # class -> (name of the class, [(name, offset, code)], bytes to read)

    def layout(self, obj):
        klass = self.il.memory.u64(obj)
        if klass not in self.layouts:
            fields = [(n, o, c) for n, o, static, c in self.il.field_list(klass) if not static and o < 0x2000]
            size = max((o for _n, o, _c in fields), default=0) + 16
            self.layouts[klass] = (self.il.class_name(obj), fields, size)
        return self.layouts[klass]

    def values(self, obj):
        """{field: (value, referenced address or None)}: numbers for simple fields, three
        floats for a struct (often a Vector3), the text of a string, and for a reference the
        address it holds in hex (which object, so a change of object shows)."""
        _name, fields, size = self.layout(obj)
        data = self.il.memory.read(obj, size)
        found = {}
        for name, offset, code in fields:
            if code in SIMPLE_TYPES:
                fmt = SIMPLE_TYPES[code][1]
                found[name] = (rounded(struct.unpack_from(fmt, data, offset)[0]), None)
            elif code == TYPE_VALUETYPE and offset + 12 <= len(data):
                found[name] = ([rounded(v) for v in struct.unpack_from('<3f', data, offset)], None)
            elif code in REFERENCE_TYPES and offset + 8 <= len(data):
                address = struct.unpack_from('<Q', data, offset)[0]
                found[name] = (f'{address:x}' if address else None, address or None)
            elif code == TYPE_STRING and offset + 8 <= len(data):
                address = struct.unpack_from('<Q', data, offset)[0]
                try:
                    found[name] = (self.text(address) if address else None, None)
                except (NotFound, ReadError, OSError, UnicodeDecodeError):
                    found[name] = ('?', None)
        return found


class Recorder:
    def __init__(self, live, out):
        self.live = live  # the race reader (winmemory.CachedReader around a LapReader)
        self.reader = live.reader
        self.il = self.reader.il
        self.fields = FieldReader(self.il, self.reader._string)
        self.out = out
        self.gates = None
        self.seen = {}  # (player index, role) -> last values written
        self.classes = set()
        self.event = None  # the event state whose event was written last

    def write(self, **record):
        self.out.write(json.dumps(record, separators=(',', ':')) + '\n')

    def race(self, now):
        state = self.live.read()
        if state.gates != self.gates:
            self.gates = state.gates
            self.write(kind='track', t=now, gates=state.gates, sector_lines=state.sector_lines)
        players = []
        for p in state.players:
            players.append(
                {
                    'name': p.name,
                    'local': p.local,
                    'laps': p.laps_completed,
                    'passed': len(p.checkpoints[-1]) if p.checkpoints else 0,
                    'pos': p.position,
                    'vel': p.velocity,
                    'fwd': p.forward,
                    'est': p.estimated,
                    'pit': p.in_pit,
                    'done': p.finished,
                }
            )
        self.write(kind='race', t=now, clock=state.clock, players=players)
        return state

    def roots(self, player):
        """{role: object} for one car: its EventPlayer, vehicle, state and state updater."""
        il = self.il
        found = {'player': player}
        for role, path in (('vehicle', ('m_vehicle',)), ('state', ('m_vehicle', 'm_state'))):
            try:
                found[role] = il.ref(player, *path)
            except (NotFound, ReadError, OSError):
                pass
        try:
            found['updater'] = il.ref(player, 'm_vehicle', 'm_stateUpdater')
        except (NotFound, ReadError, OSError):
            pass
        return found

    def raw_fields(self, now, clock):
        il = self.il
        event_state = self.reader._state
        if event_state is None:
            return
        try:
            players = [p for p in il.list_items(il.ref(event_state, 'players')) if p]
        except (NotFound, ReadError, OSError):
            return
        for index, player in enumerate(players):
            try:
                name = self.reader._player_state(player).name
            except (NotFound, ReadError, OSError):
                name = None
            level, done = list(self.roots(player).items()), set()
            for _step in range(DEPTH + 1):
                following = []
                for role, obj in level:
                    if obj in done:
                        continue
                    done.add(obj)
                    try:
                        values = self.fields.values(obj)
                    except (NotFound, ReadError, OSError, UnicodeDecodeError):
                        continue
                    for field, (_value, address) in values.items():
                        if address and INTERESTING.search(field):
                            following.append((f'{role}.{field}', address))
                    self.emit(now, clock, index, name, role, obj, values)
                level = following

    def event_roots(self):
        """{role: object} of the event: its state, controller, logic and settings."""
        il, reader = self.il, self.reader
        found = {}
        if reader._state:
            found['event.state'] = reader._state
        if reader._listener:
            found['event.controller'] = reader._listener
            try:
                found['event.logic'] = il.ref(reader._listener, 'm_eventLogic')
                found['event.settings'] = il.ref(found['event.logic'], 'm_eventSettings')
            except (NotFound, ReadError, OSError):
                pass
        return found

    def event_fields(self, now, clock):
        """The event's type once per event, then its objects' changed fields (see the top)."""
        if self.reader._state is None:
            return
        roots = self.event_roots()
        if self.reader._state != self.event:
            self.event = self.reader._state
            # Nothing kept from the event before: the same roles hold other objects now.
            self.seen = {key: value for key, value in self.seen.items() if key[0] != EVENT_PLAYER}
            classes = {}
            for role, obj in roots.items():
                try:
                    classes[role] = self.il.class_name(obj)
                except (NotFound, ReadError, OSError, UnicodeDecodeError):
                    pass
            event_type = self.reader.event_type
            self.write(
                kind='event',
                t=now,
                clock=clock,
                mode=event_type and event_type[0],
                level_type=event_type and event_type[1],
                classes=classes,
            )
            print(f'event: {event_type or "type not found"}, logic {classes.get("event.logic")}', flush=True)
        level, done = list(roots.items()), set()
        for _step in range(DEPTH + 1):
            following = []
            for role, obj in level:
                if obj in done:
                    continue
                done.add(obj)
                try:
                    values = self.fields.values(obj)
                except (NotFound, ReadError, OSError, UnicodeDecodeError):
                    continue
                for field, (_value, address) in values.items():
                    if address and EVENT_INTERESTING.search(field):
                        following.append((f'{role}.{field}', address))
                self.emit(now, clock, EVENT_PLAYER, None, role, obj, values)
            level = following

    def emit(self, now, clock, index, name, role, obj, values):
        class_name, fields, _size = self.fields.layout(obj)
        if (class_name, role) not in self.classes:
            self.classes.add((class_name, role))
            self.write(kind='schema', role=role, cls=class_name, fields=[[n, o, c] for n, o, c in fields])
        plain = {field: value for field, (value, _address) in values.items()}
        last = self.seen.get((index, role))
        changed = plain if last is None else {k: v for k, v in plain.items() if last.get(k) != v}
        self.seen[(index, role)] = plain
        if changed:
            self.write(
                kind='fields',
                t=now,
                clock=clock,
                player=index,
                name=name,
                role=role,
                cls=class_name,
                changed=changed,
            )


def connect(platform=sys.platform):
    """(race reader, something with close() for the end): on Windows TSU read straight,
    else through the reader in the CrossOver bottle."""
    if platform == 'win32':
        from turbohud.tsu import winmemory

        attempt, where = winmemory.connect, 'TSU'
    else:
        from turbohud.tsu.bottle import Bottle

        bottle = Bottle()

        def attempt():
            return bottle.connect()[0], bottle

        where = 'TSU in CrossOver'
    while True:
        try:
            return attempt()
        except (NotFound, ReadError) as error:
            print(f'TSU is loading ({error}) ...', flush=True)
        except OSError as error:
            print(f'waiting for {where} ({error}) ...', flush=True)
        time.sleep(2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--minutes', type=float, default=None, help='stop after this long (default: Ctrl+C)')
    args = parser.parse_args(argv)
    # The reader's own lines (the search, the event type) on the console, as in TurboHUD's log.
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
    out_folder = folder()
    out_folder.mkdir(parents=True, exist_ok=True)
    path = out_folder / time.strftime('race-%Y%m%d-%H%M%S.jsonl.gz')
    live, bottle = connect()
    print(f'Recording to {path}', flush=True)
    print('Start a race. Ctrl+C ends the recording.', flush=True)
    started = time.monotonic()
    records = racing = 0
    waiting_said = None
    try:
        with gzip.open(path, 'wt', encoding='utf-8') as out:
            recorder = Recorder(live, out)
            recorder.write(kind='start', t=0.0, wall=time.time())
            next_fields = 0.0
            while args.minutes is None or time.monotonic() - started < args.minutes * 60:
                began = time.monotonic()
                now = round(began - started, 3)
                try:
                    state = recorder.race(now)
                    racing += 1
                    if began >= next_fields:
                        next_fields = began + FIELDS_EVERY
                        recorder.raw_fields(now, state.clock)
                        recorder.event_fields(now, state.clock)
                    if waiting_said is not None:
                        print('race found: recording', flush=True)
                        waiting_said = None
                except (NotFound, ReadError) as error:
                    if waiting_said != str(error):
                        print(f'no race to read yet ({error})', flush=True)
                        waiting_said = str(error)
                    if recorder.reader._state is None:
                        time.sleep(1.0)
                        continue
                    # The event is there, but not a race to read (an arena mode?): the event itself.
                    if began >= next_fields:
                        next_fields = began + FIELDS_EVERY
                        try:
                            recorder.event_fields(now, None)
                        except (NotFound, ReadError, OSError):
                            pass
                    time.sleep(FIELDS_EVERY)
                    continue
                records += 1
                if records % 600 == 0:
                    print(f'{now / 60:.1f} min, {racing} race reads', flush=True)
                time.sleep(max(RACE_EVERY - (time.monotonic() - began), 0.0))
    except KeyboardInterrupt:
        pass
    finally:
        bottle.close()
    print(f'Done: {racing} race reads in {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
