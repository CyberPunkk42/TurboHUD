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
        for i, (field_name, offset, is_static) in enumerate(fields):
            entry = entries + il.FIELD_INFO_SIZE * i
            self.q(entry, self.string(field_name))
            self.q(entry + 8, self.static_type if is_static else self.instance_type)
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


def build(lap_starts, laps_completed, clock, limit, local_index=0, finished=False, car=None, gates=()):
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
        vehicle = g.alloc_obj(g.klass('TS', 'Vehicle', [('m_statsNewPosition', 0x64, False)]))
        g.put(vehicle + 0x64, struct.pack('<3f', car[0], 10.0, car[1]))
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


def racing(state, running=False, read_at=100.0):
    return race.Snapshot(race.RACING, state, running, read_at)


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
        state = race.LapState(clock=0, time_limit=10_001, laps_completed=0, laps_to_finish=5, lap_starts=[0])
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
            clock=0, time_limit=0, laps_completed=2, laps_to_finish=2, lap_starts=[0, 900_000, 1_700_000, 1_750_000]
        )
        rows = race.race_rows(racing(state), 0)
        self.assertTrue(rows[0].text.startswith('Finished'))
        self.assertEqual(rows[1].text, '1:20.000')

    def test_delta_row_is_green_ahead_and_red_behind(self):
        ahead = race.LapState(0, 0, 1, 13, [0, 900_000], checkpoints=((0, 300_000), (900_000, 1_199_000)))
        row = race.race_rows(racing(ahead), 0)[2]
        self.assertEqual((row.text, row.color), ('-0.100 vs best', 'ahead'))
        behind = race.LapState(0, 0, 1, 13, [0, 900_000], checkpoints=((0, 300_000), (900_000, 1_202_340)))
        row = race.race_rows(racing(behind), 0)[2]
        self.assertEqual((row.text, row.color), ('+0.234 vs best', 'behind'))

    def test_waiting_texts_fit_the_lap_section(self):
        from turbohud.core.hud import RACE_SECTIONS

        widest = max(len(rows[0].text) for rows in RACE_SECTIONS[0].samples)
        for status in (race.WAITING_FOR_GAME, race.WAITING_FOR_RACE):
            with self.subTest(status=status):
                text = race.race_sections(race.Snapshot(status), 0)['lap'][0].text
                self.assertLessEqual(len(text), widest)

    def test_waiting(self):
        game = race.race_rows(race.Snapshot(race.WAITING_FOR_GAME), 0)
        self.assertIn('launch option', game[-1].text)
        waiting = race.race_rows(race.Snapshot(race.WAITING_FOR_RACE), 0)
        self.assertIn('Waiting for a race', waiting[-1].text)


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
