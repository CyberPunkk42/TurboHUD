"""Show the local car's state from TSU's memory, to find fuel, tire wear and speed (Linux).

From the game's type information: the local TS.EventPlayer has `m_vehicle` (TS.Vehicle),
whose `m_state` (TS.VehicleState) has fuelConsumption, tireWear and hitPoints, and whose
`m_stateUpdater` (TS.CarStateUpdater) has m_forwardSpeed and other driving values. Their
types and units are what this tool is for.

Start TSU from Steam with the launch option (see turbohud/tsu/probe.py), start a race
(with fuel and tire wear on, if the event allows), then:

    python3 -B experiments/tsu_vehicle_dump.py          # every simple field once
    python3 -B experiments/tsu_vehicle_dump.py --watch  # the likely ones, twice a second

Only reads.
"""

import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core.il2cpp import SIMPLE_TYPES, TYPE_VALUETYPE, NotFound
from turbohud.tsu.client import connect

# (object, field) pairs to watch while driving.
WATCH = [
    ('state', 'fuelConsumption'),
    ('state', 'tireWear'),
    ('state', 'hitPoints'),
    ('updater', 'm_forwardSpeed'),
    ('updater', 'm_speedOnFrontSurface'),
    ('updater', 'm_oldSpeed3d'),
    ('updater', 'inPit'),
]


def value(il, obj, offset, code):
    """A field's value as text: simple types as numbers, structs as three floats."""
    if code in SIMPLE_TYPES:
        _name, fmt = SIMPLE_TYPES[code]
        number = struct.unpack(fmt, il.memory.read(obj + offset, struct.calcsize(fmt)))[0]
        return f'{number:.4f}' if isinstance(number, float) else str(number)
    if code == TYPE_VALUETYPE:
        x, y, z = struct.unpack('<3f', il.memory.read(obj + offset, 12))
        return f'({x:.3f}, {y:.3f}, {z:.3f})?'
    return None


def objects(reader):
    il = reader.il
    _state, player = reader.local_player()
    vehicle = il.ref(player, 'm_vehicle')
    return {
        'player': player,
        'vehicle': vehicle,
        'state': il.ref(vehicle, 'm_state'),
        'updater': il.ref(vehicle, 'm_stateUpdater'),
    }


def dump(reader):
    il = reader.il
    for label, obj in objects(reader).items():
        print(f'== {label}: {il.class_name(obj)}')
        for name, offset, is_static, code in il.field_list(il.memory.u64(obj)):
            if is_static:
                continue
            shown = value(il, obj, offset, code)
            if shown is not None:
                print(f'  {offset:#06x} {name:<50} {shown}')


def watch(reader, interval=0.5):
    il = reader.il
    print('  '.join(field for _label, field in WATCH))
    while True:
        found = objects(reader)
        fields = {label: {f[0]: f for f in il.field_list(il.memory.u64(obj))} for label, obj in found.items()}
        parts = []
        for label, field in WATCH:
            info = fields[label].get(field)
            parts.append(value(il, found[label], info[1], info[3]) if info else '-')
        print('  '.join(f'{part:>12}' for part in parts), flush=True)
        time.sleep(interval)


def main(argv):
    try:
        reader, _conn = connect()
    except OSError:
        print('TSU is not running through TurboHUD. Start TSU from Steam (with the launch option).')
        return 1
    try:
        watch(reader) if argv == ['--watch'] else dump(reader)
    except NotFound as error:
        print(f'No race yet ({error}). Start a race and try again.')
        return 1
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        pass
