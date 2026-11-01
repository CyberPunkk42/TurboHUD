import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import il2cpp as il
from turbohud.core import race

HEAP = (0x1000_0000, 0x1010_0000)
MANAGED = (0x7F00_0000_0000, 0x7F00_0010_0000)
METADATA_BASE = 0x7F10_0000_0000


class FakeGame:
    """A tiny IL2CPP-shaped memory: metadata strings, class and field records, objects."""

    def __init__(self):
        self.mem = {}
        self.strings = b'\0'
        self.heap_next = HEAP[0]
        self.obj_next = MANAGED[0]
        self.static_type = self.alloc_heap(16)
        self.put(self.static_type + il.TYPE_ATTRS, struct.pack('<H', il.FIELD_ATTRIBUTE_STATIC))
        self.instance_type = self.alloc_heap(16)
        self.put(self.instance_type + il.TYPE_ATTRS, struct.pack('<H', 0))
        self.typed = {}
        for code in (0x08, 0x0C):  # int, float
            record = self.alloc_heap(16)
            self.put(record + il.TYPE_ATTRS, struct.pack('<HB', 0, code))
            self.typed[code] = record

    def string(self, text):
        index = self.strings.find(b'\0' + text.encode() + b'\0')
        if index < 0:
            index = len(self.strings) - 1
            self.strings += text.encode() + b'\0'
        return METADATA_BASE + index + 1

    def put(self, address, data):
        for i, byte in enumerate(data):
            self.mem[address + i] = byte

    def q(self, address, value):
        self.put(address, struct.pack('<Q', value))

    def alloc_heap(self, size):
        address = self.heap_next
        self.heap_next += (size + 15) & ~15
        return address

    def alloc_obj(self, klass, size=0x100):
        address = self.obj_next
        self.obj_next += size
        self.q(address, klass)
        return address

    def klass(self, namespace, name, fields, statics=None, parent=0):
        klass = self.alloc_heap(0x100)
        self.q(klass + il.CLASS_NAME, self.string(name))
        self.q(klass + il.CLASS_NAMESPACE, self.string(namespace))
        self.q(klass + il.CLASS_PARENT, parent)
        entries = self.alloc_heap(il.FIELD_INFO_SIZE * (len(fields) + 1))
        self.q(klass + il.CLASS_FIELDS, entries)
        for i, (field_name, offset, is_static, *code) in enumerate(fields):
            entry = entries + il.FIELD_INFO_SIZE * i
            self.q(entry, self.string(field_name))
            self.q(entry + 8, self.static_type if is_static else self.typed[code[0]] if code else self.instance_type)
            self.q(entry + 16, klass)
            self.put(entry + 24, struct.pack('<iI', offset, 0x04000001))
        if statics is not None:
            self.q(klass + il.CLASS_STATIC_FIELDS, statics)
        return klass

    def list_of(self, values, element_size=8):
        array = self.alloc_obj(0, 0x20 + element_size * max(len(values), 1) + 16)
        for i, value in enumerate(values):
            fmt = '<Q' if element_size == 8 else '<I'
            self.put(array + il.ARRAY_DATA + element_size * i, struct.pack(fmt, value))
        lst = self.alloc_obj(self.list_class)
        self.q(lst + il.LIST_ITEMS, array)
        self.put(lst + il.LIST_SIZE, struct.pack('<i', len(values)))
        return lst

    def read(self, address, size):
        if METADATA_BASE <= address < METADATA_BASE + len(self.strings):
            start = address - METADATA_BASE
            return self.strings[start : start + size].ljust(size, b'\0')
        if address not in self.mem and not (HEAP[0] <= address < HEAP[1]):
            raise OSError(14, 'Bad address')
        return bytes(self.mem.get(address + i, 0) for i in range(size))

    def memory(self):
        regions = [(*HEAP, 'rw-p', 0, '[heap]'), (*MANAGED, 'rw-p', 0, '')]
        return il.Memory(self.read, regions)


def build(lap_starts, laps_completed, clock, limit, local_index=0, finished=False, car=None, gates=(), pedals=None):
    """A fake race; `car` is the car's (x, z) and `gates` the checkpoint lines, both
    optional like in a game without them."""
    g = FakeGame()
    g.list_class = g.klass('System.Collections.Generic', 'List`1', [])
    statics = g.alloc_heap(16)
    services_class = g.klass('TS', 'Services', [('sm_instance', 0, True), ('m_activeServer', 0x10, False)], statics)
    server_class = g.klass('TS', 'Server', [('m_eventListener', 0x18, False)])
    base_controller = g.klass('TS', 'EventController', [('m_eventState', 0x48, False)])
    controller_class = g.klass('TS', 'HostEventController', [('m_server', 0x60, False)], parent=base_controller)
    state_class = g.klass('TS', 'EventState', [('players', 0x28, False), ('times', 0x58, False)])
    player_fields = [('m_stats', 0x30, False), ('m_localHumanIndex', 0x50, False)]
    if car is not None:
        player_fields += [('m_vehicle', 0x20, False), ('m_statsUpdater', 0x38, False)]
    player_class = g.klass('TS', 'EventPlayer', player_fields)
    stats_class = g.klass(
        'TS',
        'PlayerRaceStats',
        [
            ('m_checkpointTimesForLaps', 0x18, False),
            ('m_lapsToFinish', 0x28, False),
            ('m_finished', 0x31, False),
            ('m_lapsCompleted', 0x32, False),
        ],
    )
    times_class = g.klass('TS', 'CheckpointTimes', [('m_times', 0x10, False)])

    services = g.alloc_obj(services_class)
    g.q(statics, services)
    server = g.alloc_obj(server_class)
    g.q(services + 0x10, server)
    controller = g.alloc_obj(controller_class)
    g.q(server + 0x18, controller)
    state = g.alloc_obj(state_class)
    g.q(controller + 0x48, state)
    g.put(state + 0x58, struct.pack('<6i', clock // 200, clock, 10000, 10000, 10000, limit))

    stats = g.alloc_obj(stats_class)
    laps = []
    for start in lap_starts:
        entry = g.alloc_obj(times_class)
        g.q(entry + 0x10, g.list_of([start, start, start + 5000], element_size=4))
        laps.append(entry)
    g.q(stats + 0x18, g.list_of(laps))
    g.put(stats + 0x28, struct.pack('<H', 13))
    g.put(stats + 0x31, bytes([finished]))
    g.put(stats + 0x32, struct.pack('<H', laps_completed))

    remote = g.alloc_obj(player_class)
    g.put(remote + 0x50, struct.pack('<i', -1))
    local = g.alloc_obj(player_class)
    g.put(local + 0x50, struct.pack('<i', local_index))
    g.q(local + 0x30, stats)
    g.q(state + 0x28, g.list_of([remote, local]))
    if car is not None:
        vehicle = g.alloc_obj(g.klass('TS', 'Vehicle', [
            ('m_state', 0x30, False), ('m_stateUpdater', 0x38, False), ('m_statsNewPosition', 0x64, False)]))
        g.put(vehicle + 0x64, struct.pack('<3f', car[0], 10.0, car[1]))
        state = g.alloc_obj(g.klass('TS', 'VehicleState', [('fuelConsumption', 0x40, False), ('tireWear', 0x48, False)]))
        g.put(state + 0x40, struct.pack('<i', 42_000))
        g.put(state + 0x48, struct.pack('<i', 576_000))
        g.q(vehicle + 0x30, state)
        updater = g.alloc_obj(g.klass('TS', 'CarStateUpdater', [
            ('m_fuelSettings', 0x18, False), ('m_controls', 0x28, False), ('m_fuelEnabled', 0x50, False),
            ('m_tireWearEnabled', 0x51, False),
            ('m_forwardSpeed', 0x60, False)]))
        g.put(updater + 0x50, bytes([1, 1]))
        g.q(updater + 0x28, 0)  # no controls object unless given
        if pedals is not None:
            if all(isinstance(value, float) for value in pedals):
                controls_class = g.klass('TS', 'CarControls', [('gas', 0x10, False, 0x0C), ('brake', 0x14, False, 0x0C)])
                fmt = '<2f'
            else:
                controls_class = g.klass('TS', 'CarControls', [
                    ('gasInThirds', 0x18, False, 0x08), ('gas', 0x10, False, 0x08),
                    ('brakeInThirds', 0x1C, False, 0x08), ('brake', 0x14, False, 0x08)])
                fmt = '<2i'
            controls = g.alloc_obj(controls_class)
            g.put(controls + 0x10, struct.pack(fmt, *pedals))
            if fmt == '<2i':
                g.put(controls + 0x18, struct.pack('<2i', *pedals))
            g.q(updater + 0x28, controls)
        g.put(updater + 0x60, struct.pack('<f', 50.0))
        g.q(vehicle + 0x38, updater)
        fuel = g.alloc_obj(g.klass('TS', 'FuelSettings', [('maxFuelConsumptionInEvent', 0x14, False)]))
        g.put(fuel + 0x14, struct.pack('<i', 168_000))
        g.q(updater + 0x18, fuel)
        g.q(local + 0x20, vehicle)
        updater = g.alloc_obj(g.klass('TS', 'PlayerRaceStatsUpdater', [('m_checkpoints', 0x18, False)]))
        g.q(local + 0x38, updater)
        track = g.alloc_obj(g.klass('TS', 'Checkpoints', [('m_checkpoints', 0x10, False)]))
        g.q(updater + 0x18, track)
        point_class = g.klass('TS', 'Checkpoint', [('m_properties', 0x20, False)])
        properties_class = g.klass('TS', 'CheckpointProperties', [('position1', 0x10, False), ('position2', 0x1C, False)])
        items = []
        for (x1, z1), (x2, z2) in gates:
            properties = g.alloc_obj(properties_class)
            g.put(properties + 0x10, struct.pack('<6f', x1, 0.0, z1, x2, 0.0, z2))
            checkpoint = g.alloc_obj(point_class)
            g.q(checkpoint + 0x20, properties)
            items.append(checkpoint)
        g.q(track + 0x10, g.list_of(items))
    g.laps = laps

    runtime = il.Il2Cpp(g.memory(), g.strings, METADATA_BASE)
    reader = race.LapReader(runtime)
    reader.game = g
    return reader


class LapStateTests(unittest.TestCase):
    def test_times_from_lap_starts(self):
        state = race.LapState(
            clock=2_000_000, time_limit=12_610_000, laps_completed=2, laps_to_finish=13,
            lap_starts=[10_000, 944_595, 1_785_545],
        )
        self.assertEqual(state.lap_times, [934_595, 840_950])
        self.assertEqual(state.last_lap, 840_950)
        self.assertEqual(state.best_lap, 840_950)
        self.assertEqual(state.current_lap, 2_000_000 - 1_785_545)
        self.assertEqual(state.time_left, 10_610_000)

    def test_before_the_first_lap_is_done(self):
        state = race.LapState(clock=50_000, time_limit=0, laps_completed=0, laps_to_finish=13, lap_starts=[10_000])
        self.assertEqual(state.lap_times, [])
        self.assertIsNone(state.last_lap)
        self.assertIsNone(state.best_lap)
        self.assertIsNone(state.time_left)
        self.assertEqual(state.current_lap, 40_000)

    def test_an_unfinished_lap_is_not_a_lap_time(self):
        # After the finish TSU may already hold the next lap's start; laps_completed caps it.
        state = race.LapState(clock=0, time_limit=0, laps_completed=1, laps_to_finish=1, lap_starts=[0, 900_000, 950_000])
        self.assertEqual(state.lap_times, [900_000])

    def test_format_time(self):
        self.assertEqual(race.format_time(996_479), '1:39.648')
        self.assertEqual(race.format_time(84_950), '0:08.495')
        self.assertEqual(race.format_time(-5_000), '-0:00.500')
        self.assertEqual(race.format_time(None), '-')


class ReaderTests(unittest.TestCase):
    def test_follows_the_chain_by_name_to_the_local_player(self):
        reader = build([10_000, 944_595, 1_785_545], laps_completed=2, clock=2_000_000, limit=12_610_000)
        state = reader.read()
        self.assertEqual(state.lap_starts, [10_000, 944_595, 1_785_545])
        self.assertEqual(state.laps_completed, 2)
        self.assertEqual(state.laps_to_finish, 13)
        self.assertEqual(state.clock, 2_000_000)
        self.assertEqual(state.time_limit, 12_610_000)

    def test_finished_flag(self):
        self.assertFalse(build([10_000], laps_completed=0, clock=20_000, limit=0).read().finished)
        self.assertTrue(build([10_000], laps_completed=0, clock=20_000, limit=0, finished=True).read().finished)

    def test_fields_of_a_parent_class_are_found(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        self.assertEqual(reader.read().current_lap, 10_000)

    def test_no_local_player_is_reported(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0, local_index=-1)
        with self.assertRaises(il.NotFound):
            reader.read()

    def test_field_list_gives_names_offsets_and_types(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        runtime = reader.il
        _state, player = reader.local_player()
        stats = runtime.ref(player, 'm_stats')
        listed = {name: (offset, static) for name, offset, static, _code in runtime.field_list(runtime.memory.u64(stats))}
        self.assertEqual(listed['m_lapsCompleted'], (0x32, False))
        self.assertEqual(runtime.class_name(stats), 'TS.PlayerRaceStats')

    def test_unknown_class_is_reported(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        with self.assertRaises(il.NotFound):
            reader.il.find_class('TS', 'NoSuchClass')


def racing(state, running=False, read_at=100.0, moved_at=100.0):
    return race.Snapshot(race.RACING, state, running, read_at, moved_at=moved_at)


MID_RACE = race.LapState(
    clock=2_000_000, time_limit=12_610_000, laps_completed=2, laps_to_finish=13,
    lap_starts=[10_000, 944_595, 1_785_545],
)


class DeltaTests(unittest.TestCase):
    # Two finished laps (the second, 80 s, is the best) and the current lap.
    LAPS = (
        (0, 0, 300_000, 600_000),
        (900_000, 900_000, 1_150_000, 1_400_000),
        (1_700_000, 1_700_000, 1_960_000),
    )

    def state(self, checkpoints=LAPS, laps_completed=2):
        return race.LapState(
            clock=1_980_000, time_limit=0, laps_completed=laps_completed, laps_to_finish=13,
            lap_starts=[lap[0] for lap in checkpoints], checkpoints=checkpoints,
        )

    def test_compares_the_last_checkpoint_passed_with_the_best_lap(self):
        state = self.state()
        self.assertEqual(state.best_lap_index, 1)
        # This lap 26.0 s at checkpoint 2, the best lap 25.0 s there: 1 s behind.
        self.assertEqual(state.delta_to_best, 10_000)

    def test_ahead_is_negative(self):
        laps = self.LAPS[:2] + ((1_700_000, 1_700_000, 1_940_000),)
        self.assertEqual(self.state(laps).delta_to_best, -10_000)

    def test_none_on_the_first_lap_and_at_the_start_of_a_lap(self):
        self.assertIsNone(self.state(((0, 0, 300_000),), laps_completed=0).delta_to_best)
        laps = self.LAPS[:2] + ((1_700_000, 1_700_000),)
        self.assertIsNone(self.state(laps).delta_to_best)

    def test_a_missed_checkpoint_is_skipped(self):
        laps = (self.LAPS[0], (900_000, 900_000, race.NO_CHECKPOINT, 1_400_000), (1_700_000, 1_700_000, 1_960_000))
        state = self.state(laps)
        # Checkpoint 2 is missing in the best lap: compare checkpoint 1 (both 0 s in): none.
        self.assertIsNone(state.delta_to_best)

    def test_reader_reads_every_checkpoint(self):
        reader = build([10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0)
        state = reader.read()
        self.assertEqual(state.checkpoints[0], (10_000, 10_000, 15_000))
        self.assertEqual(state.lap_starts, [10_000, 944_595])


# A straight track along z: checkpoint lines across it every 100 units.
STRAIGHT = tuple(((-10.0, 100.0 * i), (10.0, 100.0 * i)) for i in range(3))


class LiveDeltaTests(unittest.TestCase):
    # Three checkpoints a lap. Best lap (the second): 10 s to the first line, 20 s to the
    # second, finish at 30 s. The current lap passed its first line after 11 s.
    LAPS = ((0, 110_000, 220_000), (400_000, 500_000, 600_000), (700_000, 810_000))

    def state(self, clock, z, laps=LAPS):
        return race.LapState(
            clock=clock, time_limit=0, laps_completed=2, laps_to_finish=13,
            lap_starts=[lap[0] for lap in laps], checkpoints=laps, position=(0.0, z), gates=STRAIGHT,
        )

    def test_gate_share(self):
        self.assertAlmostEqual(race.gate_share(STRAIGHT[1], STRAIGHT[2], (5.0, 125.0)), 0.25)
        self.assertEqual(race.gate_share(STRAIGHT[0], STRAIGHT[1], (0.0, 0.0)), 0.0)

    def test_at_a_line_it_matches_the_checkpoint_delta(self):
        self.assertEqual(self.state(clock=810_000, z=100.0).delta_to_best, 10_000)

    def test_between_lines_it_moves_with_the_car(self):
        # Halfway to the second line: the best lap was there at 15 s. This lap is at 16 s.
        self.assertEqual(self.state(clock=860_000, z=150.0).delta_to_best, 10_000)
        # Still at the halfway point a second later: one more second lost.
        self.assertEqual(self.state(clock=870_000, z=150.0).delta_to_best, 20_000)
        # Gained on the best lap: there at 16 s, but already 3/4 of the way.
        self.assertEqual(self.state(clock=860_000, z=175.0).delta_to_best, -15_000)

    def test_the_last_stretch_runs_to_the_finish(self):
        # The start and finish line (checkpoint 0) at z 300, lines 1 and 2 at z 100 and 200.
        loop = (((-10.0, 300.0), (10.0, 300.0)), STRAIGHT[1], STRAIGHT[2])
        laps = self.LAPS[:2] + ((700_000, 810_000, 910_000),)
        state = race.LapState(
            clock=960_000, time_limit=0, laps_completed=2, laps_to_finish=13,
            lap_starts=[lap[0] for lap in laps], checkpoints=laps, position=(0.0, 250.0), gates=loop,
        )
        # Halfway from the last line to the finish: the best lap was there at 25 s (20 s at
        # the line, finish at 30 s); this lap is at 26 s.
        self.assertEqual(state.delta_to_best, 10_000)

    def test_lines_passed_together_count_as_one_stretch(self):
        # Lines 0 and 1 get the same time when the lap starts (as in TSU); the car is
        # really between line 0 (z 0) and line 1 (z 100). Line 2 at z 200.
        gates = STRAIGHT
        laps = (
            (0, 0, 200_000),
            (400_000, 400_000, 600_000),  # best: 20 s from the line to line 2
            (700_000, 700_000),  # this lap: just started
        )
        state = race.LapState(
            clock=750_000, time_limit=0, laps_completed=2, laps_to_finish=13,
            lap_starts=[lap[0] for lap in laps], checkpoints=laps, position=(0.0, 50.0), gates=gates,
        )
        # A quarter of the way from line 0 to line 2: the best lap was there at 5 s; this
        # lap is at 5 s too. Taking line 1 as passed would have said +5 s.
        self.assertEqual(state.delta_to_best, 0)

    def test_gate_share_follows_the_path_in_a_bend(self):
        # A right-angle bend: line A across x at z 0, line B across z at x 100. Their
        # extensions cross at (0, 0)... the projection stays sensible on the path.
        a = ((-10.0, 0.0), (10.0, 0.0))
        b = ((100.0, 90.0), (100.0, 110.0))
        self.assertAlmostEqual(race.gate_share(a, b, (50.0, 50.0)), 0.5)

    def test_a_line_at_the_same_spot_is_skipped_ahead(self):
        # Lines 1 and 2 at the same spot (z 100) with the same time; TSU writes line 2's
        # time only when the car reaches line 3 (z 200). Best lap: 10 s to z 100, 20 s to
        # z 200. This lap passed z 100 after 10 s; halfway to z 200 at 15 s: even.
        gates = (((-10.0, 0.0), (10.0, 0.0)), ((-10.0, 100.0), (10.0, 100.0)), ((-10.0, 100.0), (10.0, 100.0)),
                 ((-10.0, 200.0), (10.0, 200.0)))
        laps = ((0, 100_000, 100_000, 200_000), (300_000, 400_000, 400_000, 500_000), (600_000, 700_000))
        state = race.LapState(
            clock=750_000, time_limit=0, laps_completed=2, laps_to_finish=13,
            lap_starts=[lap[0] for lap in laps], checkpoints=laps, position=(0.0, 150.0), gates=gates,
        )
        self.assertEqual(state.delta_to_best, 0)

    def test_a_long_line_crossed_far_from_its_middle(self):
        # Line 1 is 200 units long; the car drives along z 10, far from its middle.
        line0 = ((0.0, 0.0), (0.0, 20.0))
        line1 = ((100.0, 0.0), (100.0, 200.0))
        self.assertAlmostEqual(race.gate_share(line0, line1, (50.0, 10.0)), 0.5)

    def test_a_split_line_counts_its_nearest_piece(self):
        # The next checkpoint is two pieces at x 100 (z 0-20 and z 20-200).
        pieces = [((100.0, 20.0), (100.0, 200.0)), ((100.0, 0.0), (100.0, 20.0))]
        self.assertAlmostEqual(race.gate_share([((0.0, 0.0), (0.0, 20.0))], pieces, (75.0, 10.0)), 0.75)

    def test_without_position_it_falls_back_to_checkpoints(self):
        state = race.LapState(
            clock=860_000, time_limit=0, laps_completed=2, laps_to_finish=13,
            lap_starts=[lap[0] for lap in self.LAPS], checkpoints=self.LAPS,
        )
        self.assertEqual(state.delta_to_best, 10_000)


class CachingReaderTests(unittest.TestCase):
    def test_reads_the_car_and_the_track(self):
        reader = build([10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, car=(1.0, 2.0), gates=STRAIGHT)
        state = reader.read()
        self.assertEqual(state.position, (1.0, 2.0))
        self.assertEqual(state.gates, STRAIGHT)

    def test_finished_laps_are_read_once(self):
        reader = build([10_000, 944_595, 1_785_545], laps_completed=2, clock=2_000_000, limit=0)
        first = reader.read()
        # Change what the game holds for a finished lap: the reader keeps what it read.
        times = reader.il.memory.u64(reader.game.laps[0] + 0x10)
        array = reader.il.memory.u64(times + il.LIST_ITEMS)
        reader.game.put(array + il.ARRAY_DATA, struct.pack('<I', 1))
        self.assertEqual(reader.read().checkpoints[0], first.checkpoints[0])


class CarTests(unittest.TestCase):
    def car(self, **changes):
        values = dict(fuel_on=True, fuel_used=42_000, fuel_tank=168_000, tires_on=True, tire_wear=576_000, speed=50.0)
        values.update(changes)
        return race.CarState(**values)

    def test_what_is_left(self):
        car = self.car(fuel_per_lap=10_500, wear_per_lap=144_000)
        self.assertAlmostEqual(car.fuel_left, 0.75)
        self.assertAlmostEqual(car.tires_left, 0.9)
        self.assertAlmostEqual(car.fuel_laps, 12.0)
        self.assertAlmostEqual(car.tire_laps, 36.0)
        self.assertAlmostEqual(car.kmh, 180.0)

    def test_off_in_the_event(self):
        car = self.car(fuel_on=False, tires_on=False)
        self.assertIsNone(car.fuel_left)
        self.assertIsNone(car.tire_laps)
        self.assertEqual(set(race.car_sections(car)), {'speed', 'pedals'})  # no fuel, no tires

    def test_per_lap_averages_the_last_laps_and_restarts_after_a_pit_stop(self):
        self.assertIsNone(race.per_lap([0]))
        self.assertEqual(race.per_lap([0, 11_000, 21_000, 31_000, 41_000]), 10_000)  # last 3 laps
        self.assertEqual(race.per_lap([0, 11_000, 21_000, 2_000, 12_000]), 10_000)  # refuelled after lap 2
        self.assertIsNone(race.per_lap([0, 11_000, 21_000, 2_000]))

    def test_section_texts(self):
        sections = race.car_sections(self.car(fuel_per_lap=10_500))
        fuel = sections['fuel'][0]
        self.assertEqual((fuel.text, fuel.tail, fuel.tail_color), ('Fuel 75.0%', '  ~12.0 laps', 'text'))
        self.assertEqual(sections['tires'][0].text, 'Tires 90%')  # no lap measured yet
        self.assertEqual(sections['speed'][0].text, '180 km/h')

    def test_the_fuel_saved_or_burnt_this_lap(self):
        saved = race.car_sections(self.car(fuel_per_lap=10_000, fuel_trend=-300))['fuel'][0]
        burnt = race.car_sections(self.car(fuel_per_lap=10_000, fuel_trend=210))['fuel'][0]
        unknown = race.car_sections(self.car(fuel_per_lap=10_000))['fuel'][0]
        self.assertEqual(saved.tail, '  ~12.6 laps  +0.18%')  # 300 of a 168,000 tank
        self.assertEqual(burnt.tail, '  ~12.6 laps  -0.12%')
        self.assertEqual(unknown.tail, '  ~12.6 laps')

    def test_one_decimal(self):
        self.assertEqual(race.car_sections(self.car(fuel_used=39_312))['fuel'][0].text, 'Fuel 76.6%')

    def test_laps_are_green_when_saving_and_red_when_not(self):
        saving = race.car_sections(self.car(fuel_per_lap=10_000, fuel_trend=-300))['fuel'][0]
        wasting = race.car_sections(self.car(fuel_per_lap=10_000, fuel_trend=300))['fuel'][0]
        even = race.car_sections(self.car(fuel_per_lap=10_000, fuel_trend=50))['fuel'][0]
        self.assertEqual([saving.tail_color, wasting.tail_color, even.tail_color], ['ahead', 'behind', 'text'])

    def test_fuel_trend_compares_the_same_checkpoint_in_recent_laps(self):
        starts = {0: 0, 1: 10_000, 2: 20_000}
        marks = {0: {10: 1_000}, 1: {10: 11_200}, 2: {}}
        # Lap 2 used 900 by checkpoint 10; laps 0 and 1 used 1,000 and 1,200: saving 200.
        self.assertEqual(race.fuel_trend(marks, starts, 2, 10, 20_900), -200)
        # A checkpoint missed in a read: the one before counts.
        self.assertEqual(race.fuel_trend({0: {9: 1_000}, 1: {10: 11_000}}, starts, 2, 10, 21_100), 100)

    def test_no_fuel_trend_early_first_lap_or_across_a_pit_stop(self):
        starts = {0: 0, 1: 10_000, 2: 3_000}  # refuelled during lap 1
        marks = {0: {10: 1_000}, 1: {10: 11_000}}
        self.assertIsNone(race.fuel_trend(marks, starts, 2, 10, 4_000))
        self.assertIsNone(race.fuel_trend(marks, {0: 0, 1: 10_000}, 1, 1, 10_100))  # too early
        self.assertIsNone(race.fuel_trend({}, {0: 0}, 0, 10, 1_000))  # nothing to compare

    def test_reader_reads_the_car_and_the_use_per_lap(self):
        reader = build([10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, car=(0.0, 0.0), gates=STRAIGHT)
        car = reader.read().car
        self.assertEqual((car.fuel_used, car.fuel_tank, car.tire_wear), (42_000, 168_000, 576_000))
        self.assertTrue(car.fuel_on and car.tires_on)
        self.assertAlmostEqual(car.speed, 50.0)
        self.assertIsNone(car.fuel_per_lap)  # one lap start seen so far

    def test_speed_is_yellow_while_lifting(self):
        def colour(throttle, brake, kmh=150):
            car = self.car(speed=kmh / 3.6, throttle=throttle, brake=brake)
            return race.car_sections(car)['speed'][0].color
        self.assertEqual(colour(0.0, 0.0), 'lift')
        self.assertEqual(colour(1.0, 0.0), 'text')  # on the throttle
        self.assertEqual(colour(0.0, 1.0), 'text')  # braking
        self.assertEqual(colour(0.0, 0.0, kmh=2), 'text')  # standing
        self.assertEqual(colour(None, None), 'text')  # inputs unknown

    def test_reader_reads_throttle_and_brake(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0, car=(0.0, 0.0), gates=STRAIGHT, pedals=(1.0, 0.0))
        car = reader.read().car
        self.assertEqual((car.throttle, car.brake), (1.0, 0.0))
        self.assertEqual(race.car_sections(car)['pedals'], (1.0, 0.0))

    def test_whole_number_pedals_are_read_as_thirds(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0, car=(0.0, 0.0), gates=STRAIGHT, pedals=(2, 3))
        car = reader.read().car
        self.assertAlmostEqual(car.throttle, 2 / 3)
        self.assertEqual(car.brake, 1.0)

    def test_without_controls_the_pedals_are_unknown(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0, car=(0.0, 0.0), gates=STRAIGHT)
        car = reader.read().car
        self.assertEqual((car.throttle, car.brake), (None, None))

    def test_without_car_data_there_are_no_car_sections(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        self.assertIsNone(reader.read().car)


class LiveFuelTests(unittest.TestCase):
    # Start and finish at z 300, lines 1 and 2 at z 100 and 200. The second lap (index 1)
    # is the best; this lap has passed line 2 and drives on to the finish.
    GATES = (((-10.0, 300.0), (10.0, 300.0)), STRAIGHT[1], STRAIGHT[2])
    LAPS = ((0, 110_000, 220_000), (400_000, 500_000, 600_000), (700_000, 810_000, 910_000))

    def state(self, z, used, laps=LAPS):
        car = race.CarState(True, used, 168_000, True, 0, 0.0, fuel_per_lap=3_000)
        return race.LapState(
            clock=960_000, time_limit=0, laps_completed=2, laps_to_finish=13,
            lap_starts=[lap[0] for lap in laps], checkpoints=laps, position=(0.0, z), gates=self.GATES, car=car,
        )

    def test_the_recent_laps_are_taken_at_the_same_place_between_lines(self):
        starts = {0: 0, 1: 3_000, 2: 6_000}
        marks = {0: {2: 2_000}, 1: {2: 5_000}}  # both used 2,000 by line 2, 3,000 per lap
        # Halfway from line 2 to the finish: the recent laps had used 2,500 there.
        self.assertEqual(self.state(250.0, 6_000 + 2_500).live_fuel_trend(marks, starts), 0)
        self.assertEqual(self.state(250.0, 6_000 + 2_300).live_fuel_trend(marks, starts), -200)

    def test_no_swing_while_driving_a_stretch_at_the_usual_use(self):
        starts = {0: 0, 1: 3_000, 2: 6_000}
        marks = {0: {2: 2_000}, 1: {2: 5_000}}
        trends = [self.state(z, 6_000 + 2_000 + round((z - 200) * 10)).live_fuel_trend(marks, starts) for z in (200.0, 225.0, 275.0)]
        self.assertEqual(trends, [0, 0, 0])

    def test_a_pit_stop_ends_the_comparison(self):
        starts = {0: 0, 1: 3_000, 2: 500}  # refuelled
        marks = {0: {2: 2_000}, 1: {2: 5_000}}
        self.assertIsNone(self.state(250.0, 3_000).live_fuel_trend(marks, starts))


class FuelFinishTests(unittest.TestCase):
    def state(self, laps_completed, current_lap, laps_to_finish=13, time_limit=0, clock=0):
        lap_starts = [i * 800_000 for i in range(laps_completed + 1)]
        clock = clock or lap_starts[-1] + current_lap
        return race.LapState(clock, time_limit, laps_completed, laps_to_finish, lap_starts)

    def test_laps_to_go_by_the_lap_limit(self):
        # 4 of 13 done, a quarter into the fifth (80 s laps): 8.75 to go.
        self.assertAlmostEqual(self.state(4, 200_000).laps_to_go, 8.75)

    def test_laps_to_go_by_the_time_limit(self):
        # 5 minutes left at 80 s laps: 3.75 laps fit; the lap in which time runs out is
        # finished, so 4 more laps from the start of this one, a quarter of it driven.
        state = self.state(4, 200_000, laps_to_finish=99, time_limit=4 * 800_000 + 200_000 + 3_000_000)
        self.assertAlmostEqual(state.laps_to_go, 3.75)

    def test_unknown_before_a_lap_time(self):
        self.assertIsNone(self.state(0, 100_000).laps_to_go)

    def test_margin_and_section(self):
        car = race.CarState(True, 42_000, 168_000, True, 0, 0.0, fuel_per_lap=10_000)  # 12.6 laps of fuel
        self.assertAlmostEqual(race.fuel_margin(car, 8.6), 4.0)
        spare = race.car_sections(car, 8.6)['fuelfinish'][0]
        short = race.car_sections(car, 14.0)['fuelfinish'][0]
        self.assertEqual((spare.text, spare.color), ('Finish +4.0 laps', 'ahead'))
        self.assertEqual((short.text, short.color), ('Finish -1.4 laps', 'behind'))
        self.assertEqual(race.car_sections(car)['fuelfinish'][0].text, 'Finish -')


class RowsTests(unittest.TestCase):
    def test_format_tenths_cuts_off(self):
        self.assertEqual(race.format_tenths(365_459), '0:36.5')
        self.assertEqual(race.format_tenths(599_999), '0:59.9')
        self.assertEqual(race.format_tenths(600_000), '1:00.0')
        self.assertEqual(race.format_tenths(-10), '0:00.0')
        self.assertEqual(race.format_tenths(None), '-:--.-')

    def test_mid_race(self):
        rows = race.race_rows(racing(MID_RACE), now=100.0)
        self.assertEqual([row.text for row in rows], [
            'Lap 3/13  -  17:41 left',
            '0:21.4',
            'vs best  -',
            'Last 1:24.095   Best 1:24.095',
        ])
        self.assertEqual(rows[1].color, 'accent')

    def test_the_time_left_rounds_up_like_a_countdown(self):
        state = race.LapState(clock=1, time_limit=10_002, laps_completed=0, laps_to_finish=5, lap_starts=[0])
        self.assertIn('0:02 left', race.race_rows(racing(state), 0)[0].text)

    def test_time_is_up(self):
        state = race.LapState(clock=20, time_limit=10, laps_completed=0, laps_to_finish=5, lap_starts=[0])
        self.assertIn('time is up', race.race_rows(racing(state), 0)[0].text)

    def test_no_time_limit(self):
        state = race.LapState(clock=20, time_limit=0, laps_completed=0, laps_to_finish=5, lap_starts=[0])
        self.assertEqual(race.race_rows(racing(state), 0)[0].text, 'Lap 1/5')

    def test_the_current_lap_runs_on_between_reads_while_racing(self):
        self.assertEqual(race.current_lap_now(racing(MID_RACE, running=True), 100.5), 214_455 + 5_000)
        # Not further than a second past the read; not at all while the clock stands.
        self.assertEqual(race.current_lap_now(racing(MID_RACE, running=True), 105), 214_455 + 10_000)
        self.assertEqual(race.current_lap_now(racing(MID_RACE, running=False), 100.5), 214_455)

    def test_finished(self):
        state = race.LapState(
            clock=1_800_000, time_limit=0, laps_completed=2, laps_to_finish=2, lap_starts=[0, 900_000, 1_700_000, 1_750_000]
        )
        rows = race.race_rows(racing(state), 0)
        self.assertTrue(rows[0].text.startswith('Finished'))
        self.assertEqual(rows[1].text, '1:20.000')

    def test_delta_row_is_green_ahead_and_red_behind(self):
        ahead = race.LapState(1, 0, 1, 13, [0, 900_000], checkpoints=((0, 300_000), (900_000, 1_199_000)))
        row = race.race_rows(racing(ahead), 0)[2]
        self.assertEqual((row.text, row.color), ('-0.100 vs best', 'ahead'))
        behind = race.LapState(1, 0, 1, 13, [0, 900_000], checkpoints=((0, 300_000), (900_000, 1_202_340)))
        row = race.race_rows(racing(behind), 0)[2]
        self.assertEqual((row.text, row.color), ('+0.234 vs best', 'behind'))

    def test_a_delta_too_small_to_show_is_even(self):
        self.assertEqual(race.format_delta(-3), '0.000')
        self.assertEqual(race.format_delta(5), '+0.001')
        even = race.LapState(1, 0, 1, 13, [0, 900_000], checkpoints=((0, 300_000), (900_000, 1_199_997)))
        row = race.race_rows(racing(even), 0)[2]
        self.assertEqual((row.text, row.color), ('0.000 vs best', 'text'))

    def test_the_local_time_shows_once_tsu_runs(self):
        import time

        now = time.struct_time((2026, 11, 1, 18, 7, 0, 6, 305, 0))
        self.assertNotIn('localtime', race.with_local_time({}, race.Snapshot(race.WAITING_FOR_GAME), now))
        menu = race.with_local_time({}, race.Snapshot(race.WAITING_FOR_RACE), now)
        self.assertEqual(menu['localtime'][0].text, '18:07')
        self.assertIn('localtime', race.with_local_time({}, race.Snapshot(race.STARTING), now))

    def test_nothing_before_the_grid(self):
        for status in (race.WAITING_FOR_GAME, race.WAITING_FOR_RACE, race.STARTING):
            with self.subTest(status=status):
                self.assertEqual(race.race_sections(race.Snapshot(status), 0), {})
        lobby = race.LapState(clock=0, time_limit=0, laps_completed=0, laps_to_finish=13, lap_starts=[])
        self.assertEqual(race.race_sections(racing(lobby), 0), {})  # race made, clock not running

    def test_everything_from_the_grid_on(self):
        grid = race.LapState(clock=2_800, time_limit=12_660_000, laps_completed=0, laps_to_finish=13, lap_starts=[])
        sections = race.race_sections(racing(grid), 0)
        self.assertEqual(sections['lap'][0].text, 'Lap 1/13  -  21:06 left')
        self.assertEqual(sections['current'][0].text, '-:--.-')

    def test_a_standing_clock_hides_the_hud(self):
        # A finished race left in memory while the lobby waits for the next one.
        old = race.LapState(clock=9_000_000, time_limit=0, laps_completed=13, laps_to_finish=13, lap_starts=[0])
        self.assertEqual(race.race_sections(racing(old, moved_at=100.0), 103.0), {})
        self.assertNotEqual(race.race_sections(racing(old, moved_at=100.0), 101.0), {})

    def test_status_for_the_tray(self):
        self.assertIn('launch option', race.status_text(race.Snapshot(race.WAITING_FOR_GAME)))
        self.assertEqual(race.status_text(race.Snapshot(race.WAITING_FOR_RACE)), 'waiting for a race')
        self.assertEqual(race.status_text(race.Snapshot(race.STARTING)), 'race being set up')
        import time

        self.assertEqual(race.status_text(racing(MID_RACE, moved_at=time.monotonic())), 'racing')


class LiveRaceTests(unittest.TestCase):
    def setUp(self):
        from turbohud.tsu import client

        self.client = client
        self.now = 50.0

    def live(self, connect):
        return self.client.LiveRace(connect=connect, clock=lambda: self.now)

    def test_without_tsu_it_waits_for_the_game(self):
        def connect():
            raise FileNotFoundError('no socket')

        live = self.live(connect)
        self.assertEqual(live.step(), self.client.WAIT_INTERVAL)
        self.assertEqual(live.snapshot().status, race.WAITING_FOR_GAME)

    def test_while_a_race_is_set_up_it_says_race_starting(self):
        class Reader:
            def read(self):
                raise il.NotFound('m_eventListener is null')

        live = self.live(lambda: (Reader(), None))
        self.assertEqual(live.step(), self.client.READ_INTERVAL)
        self.assertEqual(live.snapshot().status, race.STARTING)

    def test_in_the_menu_it_waits_for_a_race_and_keeps_the_connection(self):
        calls = []

        class Reader:
            def read(self):
                raise il.NotFound('m_activeServer is null')

        def connect():
            calls.append(1)
            return Reader(), None

        live = self.live(connect)
        live.step()
        live.step()
        self.assertEqual(live.snapshot().status, race.WAITING_FOR_RACE)
        self.assertEqual(len(calls), 1)

    def test_racing_notices_whether_the_clock_moves(self):
        clocks = iter([1000, 1200, 1200])

        class Reader:
            def read(self):
                return race.LapState(next(clocks), 0, 0, 13, [0])

        live = self.live(lambda: (Reader(), None))
        self.assertEqual(live.step(), self.client.READ_INTERVAL)
        self.assertFalse(live.snapshot().running)  # nothing to compare with yet
        live.step()
        self.assertTrue(live.snapshot().running)
        live.step()
        self.assertFalse(live.snapshot().running)
        self.assertEqual(live.snapshot().read_at, 50.0)

    def test_it_notes_when_the_clock_last_moved(self):
        clocks = iter([1000, 1200, 1200])

        class Reader:
            def read(self):
                return race.LapState(next(clocks), 0, 0, 13, [0])

        live = self.live(lambda: (Reader(), None))
        live.step()
        self.now = 51.0
        live.step()
        self.now = 55.0
        live.step()
        self.assertEqual(live.snapshot().moved_at, 51.0)

    def test_when_tsu_quits_it_reconnects(self):
        attempts = []

        class Gone:
            def read(self):
                raise ConnectionError('closed')

        def connect():
            attempts.append(1)
            return Gone(), None

        live = self.live(connect)
        live.step()
        live.step()
        self.assertEqual(live.snapshot().status, race.WAITING_FOR_GAME)
        self.assertEqual(len(attempts), 2)

    def test_the_thread_starts_and_stops(self):
        def connect():
            raise FileNotFoundError('no socket')

        live = self.client.LiveRace(connect=connect)
        live.start()
        live.stop()
        self.assertFalse(live._thread.is_alive())

    def test_connect_without_the_probe_fails_cleanly(self):
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(OSError):
                self.client.connect(Path(folder, 'missing.sock'))


if __name__ == '__main__':
    unittest.main()
