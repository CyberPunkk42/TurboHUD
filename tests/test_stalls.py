import gc
import time
import unittest

from turbohud.core import hud, stalls

WALL = time.mktime((2026, 11, 13, 18, 20, 41, 0, 0, -1)) + 0.123  # 18:20:41.123 local time


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class GcWatchTests(unittest.TestCase):
    def setUp(self):
        self.clock, self.lines = Clock(), []
        self.watch = stalls.GcWatch(self.clock, lambda: WALL, lambda text, *a: self.lines.append(text % a))

    def collect(self, generation, seconds, collected=0):
        self.watch.callback('start', {'generation': generation})
        self.clock.now += seconds
        self.watch.callback('stop', {'generation': generation, 'collected': collected})

    def test_a_slow_collection_is_logged_at_once_with_its_time(self):
        self.collect(0, 0.001)
        self.assertEqual(self.lines, [])  # quick ones only in the summary
        self.collect(2, 0.180, 4321)
        self.assertEqual(
            self.lines,
            ['slow garbage collection: generation 2, 180 ms, ended 18:20:41.123 (4321 objects freed)'],
        )

    def test_the_summary_counts_each_generation_then_starts_again(self):
        for generation, seconds in ((0, 0.001), (0, 0.002), (1, 0.005), (2, 0.030)):
            self.collect(generation, seconds)
        self.lines.clear()
        self.watch.flush()
        self.assertEqual(len(self.lines), 1)
        self.assertIn('4 in', self.lines[0])
        self.assertIn('(generation 0: 2, 1: 1, 2: 1), 38 ms in all, slowest 30 ms', self.lines[0])
        self.watch.flush()
        self.assertEqual(len(self.lines), 1)  # none since: no line

    def test_it_tells_how_much_of_a_span_was_collecting(self):
        start = self.clock.now
        self.clock.now += 0.05
        self.collect(2, 0.15)  # 100.05 to 100.20
        self.clock.now += 0.1
        self.assertAlmostEqual(self.watch.during(start, self.clock.now), 0.15)
        self.assertAlmostEqual(self.watch.during(100.1, 100.3), 0.10)  # only the part inside
        self.assertEqual(self.watch.during(100.2, 100.3), 0.0)

    def test_it_hears_python_s_own_collections(self):
        watch = stalls.GcWatch(log_line=lambda *_a: None)
        watch.install()
        watch.install()  # once only
        self.addCleanup(watch.uninstall)
        self.assertEqual(gc.callbacks.count(watch.callback), 1)
        gc.collect()
        self.assertEqual(sum(watch._counts), 1)
        watch.uninstall()
        self.assertNotIn(watch.callback, gc.callbacks)

    def test_the_time_to_the_millisecond(self):
        self.assertEqual(stalls.clock_text(WALL), '18:20:41.123')


class SlowFrameTests(unittest.TestCase):
    def setUp(self):
        self.clock, self.lines, self.parts = Clock(), [], {}
        self.frames = hud.FrameTimes(
            self.clock,
            lambda text, *a: self.lines.append(text % a),
            gc_during=lambda start, end: 0.12 if end - start > 0.2 else 0.0,
            wall=lambda: WALL,
            parts=self.take,
            on_flush=lambda: self.lines.append('flushed'),
        )

    def take(self):
        taken, self.parts = self.parts, {}
        return taken

    def test_a_slow_frame_is_logged_at_once_with_the_collection_in_it(self):
        self.frames.frame(0.001, 0.005)
        self.clock.now += 0.05
        self.frames.frame(0.001, 0.005)
        self.assertEqual(self.lines, [])
        self.clock.now += 0.345
        self.frames.frame(0.002, 0.009)
        self.assertEqual(
            self.lines,
            [
                (
                    'slow frame: 345 ms after the last, ended 18:20:41.123; garbage collection in it 120 ms; '
                    'this frame: content 2.0 ms, drawing 9.0 ms'
                )
            ],
        )

    def test_a_slow_frame_without_a_new_read_is_left_to_the_reads(self):
        # At a race's end, frames came every 100 to 150 ms with nothing new read (2026-11-13).
        self.frames.frame(0.001, 0.005)
        for _ in range(5):
            self.clock.now += 0.15
            self.frames.frame(0.0001, 0.0, fresh=False)
        self.assertEqual(self.lines, [])
        self.clock.now += 0.3
        self.frames.frame(0.001, 0.005)  # a new read 300 ms after the last frame: TurboHUD itself was held
        self.assertEqual(len(self.lines), 1)
        self.assertTrue(self.lines[0].startswith('slow frame: 300 ms'))

    def test_the_summary_names_the_costliest_sections(self):
        for _ in range(4):
            self.parts['laptimes'] = self.parts.get('laptimes', 0.0) + 0.004
            self.parts['players'] = self.parts.get('players', 0.0) + 0.002
            self.parts['speed'] = self.parts.get('speed', 0.0) + 0.0005
            self.frames.frame(0.001, 0.0065)
            self.clock.now += 0.05
        self.frames.flush()
        self.assertTrue(self.lines[0].startswith('HUD frames: 3 in'))  # four frames, three gaps
        self.assertEqual(
            self.lines[1], 'drawing by section, ms a frame: laptimes 4.0, players 2.0, speed 0.5'
        )
        self.assertEqual(self.lines[2], 'flushed')

    def test_drawing_outside_a_race_is_not_counted_in_the_next(self):
        self.parts['laptimes'] = 9.0
        self.frames.flush()  # not racing: no frames
        self.assertEqual(self.lines, [])
        self.assertEqual(self.parts, {})

    def test_the_costliest_parts_by_name(self):
        self.assertEqual(stalls.slowest_parts({'a': 0.01, 'b': 0.03, 'c': 0.0}, 10), 'b 3.0, a 1.0')
        self.assertEqual(stalls.slowest_parts({}, 10), '')


class SlowReadTests(unittest.TestCase):
    def test_a_slow_read_says_what_part_was_the_game_and_what_a_collection(self):
        from turbohud.tsu.client import ReadTimes

        clock = Clock()
        times = ReadTimes(
            clock, gc_during=lambda start, end: 0.18 if end - start > 0.1 else 0.0, wall=lambda: WALL
        )
        with self.assertLogs('turbohud.tsu.client', 'INFO') as logs:
            times.add(0.003, (1, 0.0012, 27))
            clock.now += 0.2
            times.add(0.197, (1, 0.0013, 27))
        self.assertEqual(len(logs.output), 1)
        self.assertIn(
            "slow race read: 197 ms, ended 18:20:41.123; 1 trips, 1.3 ms on the game's memory; "
            'garbage collection in it 180 ms',
            logs.output[0],
        )

    def test_a_slow_read_without_details(self):
        from turbohud.tsu.client import ReadTimes

        times = ReadTimes(Clock(), wall=lambda: WALL)
        with self.assertLogs('turbohud.tsu.client', 'INFO') as logs:
            times.add(0.25)
        self.assertIn("? trips, ? on the game's memory; garbage collection in it 0 ms", logs.output[0])


if __name__ == '__main__':
    unittest.main()
