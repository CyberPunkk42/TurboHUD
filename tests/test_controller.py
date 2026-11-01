import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.tsu import controller


def event(number, value, kind=0x02):
    return struct.pack('<IhBB', 0, value, kind, number)


class TriggerTests(unittest.TestCase):
    def test_released_half_and_pressed(self):
        self.assertEqual(controller.trigger(-32767), 0.0)
        self.assertAlmostEqual(controller.trigger(0), 0.5)
        self.assertEqual(controller.trigger(32767), 1.0)

    def test_only_gamepads_are_read(self):
        self.assertTrue(controller.is_pad('Microsoft X-Box 360 pad 0'))
        self.assertTrue(controller.is_pad('Logitech G29 Driving Force Racing Wheel'))
        self.assertFalse(controller.is_pad('2.4G Dongle'))
        self.assertFalse(controller.is_pad('Razer Basilisk V3 X HyperSpeed Keyboard'))


class PadTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.pad = controller.Pad(clock=lambda: self.now)

    def test_nothing_before_the_pad_said_anything(self):
        self.assertIsNone(self.pad.pedals())

    def test_triggers_from_events(self):
        self.pad.feed(event(5, 16383) + event(2, -32767) + event(0, 1200) + event(3, 1, kind=0x01))
        throttle, brake = self.pad.pedals()
        self.assertAlmostEqual(throttle, 0.75, places=3)
        self.assertEqual(brake, 0.0)

    def test_a_silent_pad_counts_as_gone(self):
        self.pad.feed(event(5, 32767) + event(2, -32767))
        self.now += 5
        self.assertIsNone(self.pad.pedals())


class CombinedTests(unittest.TestCase):
    def test_the_greater_of_game_and_pad(self):
        self.assertEqual(controller.combined((1 / 3, 0.0), (0.4, 0.1)), (0.4, 0.1))
        self.assertEqual(controller.combined((1.0, 0.0), (0.2, 0.0)), (1.0, 0.0))  # keyboard

    def test_either_alone(self):
        self.assertEqual(controller.combined((1.0, 0.0), None), (1.0, 0.0))
        self.assertEqual(controller.combined(None, (0.5, 0.0)), (0.5, 0.0))
        self.assertEqual(controller.combined((None, None), (0.5, 0.2)), (0.5, 0.2))


if __name__ == '__main__':
    unittest.main()
