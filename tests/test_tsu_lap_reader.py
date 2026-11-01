import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))

import tsu_lap_reader as lr

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
        self.put(self.static_type + lr.TYPE_ATTRS, struct.pack('<H', lr.FIELD_ATTRIBUTE_STATIC))
        self.instance_type = self.alloc_heap(16)
        self.put(self.instance_type + lr.TYPE_ATTRS, struct.pack('<H', 0))

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
        self.q(klass + lr.CLASS_NAME, self.string(name))
        self.q(klass + lr.CLASS_NAMESPACE, self.string(namespace))
        self.q(klass + lr.CLASS_PARENT, parent)
        entries = self.alloc_heap(lr.FIELD_INFO_SIZE * (len(fields) + 1))
        self.q(klass + lr.CLASS_FIELDS, entries)
        for i, (field_name, offset, is_static) in enumerate(fields):
            entry = entries + lr.FIELD_INFO_SIZE * i
            self.q(entry, self.string(field_name))
            self.q(entry + 8, self.static_type if is_static else self.instance_type)
            self.q(entry + 16, klass)
            self.put(entry + 24, struct.pack('<iI', offset, 0x04000001))
        if statics is not None:
            self.q(klass + lr.CLASS_STATIC_FIELDS, statics)
        return klass

    def list_of(self, values, element_size=8):
        array = self.alloc_obj(0, 0x20 + element_size * max(len(values), 1) + 16)
        for i, value in enumerate(values):
            fmt = '<Q' if element_size == 8 else '<I'
            self.put(array + lr.ARRAY_DATA + element_size * i, struct.pack(fmt, value))
        lst = self.alloc_obj(self.list_class)
        self.q(lst + lr.LIST_ITEMS, array)
        self.put(lst + lr.LIST_SIZE, struct.pack('<i', len(values)))
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
        return lr.Memory(self.read, regions)


def build(lap_starts, laps_completed, clock, limit, local_index=0):
    g = FakeGame()
    g.list_class = g.klass('System.Collections.Generic', 'List`1', [])
    statics = g.alloc_heap(16)
    services_class = g.klass('TS', 'Services', [('sm_instance', 0, True), ('m_activeServer', 0x10, False)], statics)
    server_class = g.klass('TS', 'Server', [('m_eventListener', 0x18, False)])
    base_controller = g.klass('TS', 'EventController', [('m_eventState', 0x48, False)])
    controller_class = g.klass('TS', 'HostEventController', [('m_server', 0x60, False)], parent=base_controller)
    state_class = g.klass('TS', 'EventState', [('players', 0x28, False), ('times', 0x58, False)])
    player_class = g.klass('TS', 'EventPlayer', [('m_stats', 0x30, False), ('m_localHumanIndex', 0x50, False)])
    stats_class = g.klass(
        'TS',
        'PlayerRaceStats',
        [('m_checkpointTimesForLaps', 0x18, False), ('m_lapsToFinish', 0x28, False), ('m_lapsCompleted', 0x32, False)],
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
    g.put(stats + 0x32, struct.pack('<H', laps_completed))

    remote = g.alloc_obj(player_class)
    g.put(remote + 0x50, struct.pack('<i', -1))
    local = g.alloc_obj(player_class)
    g.put(local + 0x50, struct.pack('<i', local_index))
    g.q(local + 0x30, stats)
    g.q(state + 0x28, g.list_of([remote, local]))

    il = lr.Il2Cpp(g.memory(), g.strings, METADATA_BASE)
    return lr.LapReader(il)


class LapStateTests(unittest.TestCase):
    def test_times_from_lap_starts(self):
        state = lr.LapState(
            clock=2_000_000, time_limit=12_610_000, laps_completed=2, laps_to_finish=13,
            lap_starts=[10_000, 944_595, 1_785_545],
        )
        self.assertEqual(state.lap_times, [934_595, 840_950])
        self.assertEqual(state.last_lap, 840_950)
        self.assertEqual(state.best_lap, 840_950)
        self.assertEqual(state.current_lap, 2_000_000 - 1_785_545)
        self.assertEqual(state.time_left, 10_610_000)

    def test_before_the_first_lap_is_done(self):
        state = lr.LapState(clock=50_000, time_limit=0, laps_completed=0, laps_to_finish=13, lap_starts=[10_000])
        self.assertEqual(state.lap_times, [])
        self.assertIsNone(state.last_lap)
        self.assertIsNone(state.best_lap)
        self.assertIsNone(state.time_left)
        self.assertEqual(state.current_lap, 40_000)

    def test_an_unfinished_lap_is_not_a_lap_time(self):
        # After the finish TSU may already hold the next lap's start; laps_completed caps it.
        state = lr.LapState(clock=0, time_limit=0, laps_completed=1, laps_to_finish=1, lap_starts=[0, 900_000, 950_000])
        self.assertEqual(state.lap_times, [900_000])

    def test_format_time(self):
        self.assertEqual(lr.format_time(996_479), '1:39.648')
        self.assertEqual(lr.format_time(84_950), '0:08.495')
        self.assertEqual(lr.format_time(-5_000), '-0:00.500')
        self.assertEqual(lr.format_time(None), '-')


class ReaderTests(unittest.TestCase):
    def test_follows_the_chain_by_name_to_the_local_player(self):
        reader = build([10_000, 944_595, 1_785_545], laps_completed=2, clock=2_000_000, limit=12_610_000)
        state = reader.read()
        self.assertEqual(state.lap_starts, [10_000, 944_595, 1_785_545])
        self.assertEqual(state.laps_completed, 2)
        self.assertEqual(state.laps_to_finish, 13)
        self.assertEqual(state.clock, 2_000_000)
        self.assertEqual(state.time_limit, 12_610_000)

    def test_fields_of_a_parent_class_are_found(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        self.assertEqual(reader.read().current_lap, 10_000)

    def test_no_local_player_is_reported(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0, local_index=-1)
        with self.assertRaises(lr.NotFound):
            reader.read()

    def test_unknown_class_is_reported(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        with self.assertRaises(lr.NotFound):
            reader.il.find_class('TS', 'NoSuchClass')


class ConnectTests(unittest.TestCase):
    def test_without_the_probe_connect_fails_cleanly(self):
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(OSError):
                lr.connect(Path(folder, 'missing.sock'))

    def test_a_refused_read_is_a_read_error_and_an_os_error(self):
        self.assertTrue(issubclass(lr.ReadError, OSError))

    def test_state_line(self):
        state = lr.LapState(clock=50_000, time_limit=0, laps_completed=0, laps_to_finish=13, lap_starts=[10_000])
        self.assertEqual(lr.format_state(state), 'lap 1/13  current 0:04.000  last -  best -  time left -')


if __name__ == '__main__':
    unittest.main()
