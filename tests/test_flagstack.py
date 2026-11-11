import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core.flagstack import GAP, FlagStack, overlap

YELLOW = (800, 100, 320, 110)
BLUE = (820, 120, 480, 24)  # put in the same spot by the player
SCREEN = (0, 0, 1920, 1080)
BLUE_BELOW = (820, 100 + 110 + GAP, 480, 24)
YELLOW_ABOVE = (800, 120 - GAP - 110, 320, 110)


class FlagStackTests(unittest.TestCase):
    """Asked for by the user on 2026-11-11: both flags in one spot stay visible, stacked,
    and a flag on the screen never moves."""

    def homes(self, blue=BLUE):
        return {'yellowflag': YELLOW, 'blueflag': blue}

    def test_one_flag_stays_at_its_own_place(self):
        stack = FlagStack()
        self.assertEqual(stack.places(self.homes(), {'blueflag'}, SCREEN), {'blueflag': BLUE})
        self.assertEqual(stack.places(self.homes(), set(), SCREEN), {})

    def test_the_blue_flag_that_comes_second_goes_below_the_yellow_box(self):
        stack = FlagStack()
        stack.places(self.homes(), {'yellowflag'}, SCREEN)
        places = stack.places(self.homes(), {'yellowflag', 'blueflag'}, SCREEN)
        self.assertEqual(places, {'yellowflag': YELLOW, 'blueflag': BLUE_BELOW})
        self.assertFalse(overlap(places['yellowflag'], places['blueflag']))

    def test_the_yellow_box_that_comes_second_goes_above_the_blue_flag(self):
        stack = FlagStack()
        stack.places(self.homes(), {'blueflag'}, SCREEN)
        places = stack.places(self.homes(), {'yellowflag', 'blueflag'}, SCREEN)
        self.assertEqual(places, {'blueflag': BLUE, 'yellowflag': YELLOW_ABOVE})

    def test_a_flag_on_the_screen_never_moves(self):
        stack = FlagStack()
        stack.places(self.homes(), {'yellowflag'}, SCREEN)
        stack.places(self.homes(), {'yellowflag', 'blueflag'}, SCREEN)
        # The yellow flag goes: the blue one stays below, where it is, until it goes too.
        self.assertEqual(stack.places(self.homes(), {'blueflag'}, SCREEN), {'blueflag': BLUE_BELOW})
        # A new yellow flag while that blue one is out: above the blue flag where it now is.
        places = stack.places(self.homes(), {'yellowflag', 'blueflag'}, SCREEN)
        self.assertEqual(places['blueflag'], BLUE_BELOW)
        self.assertEqual(places['yellowflag'], (800, BLUE_BELOW[1] - GAP - 110, 320, 110))
        # Both gone: each comes back at its own place next time.
        stack.places(self.homes(), set(), SCREEN)
        self.assertEqual(stack.places(self.homes(), {'blueflag'}, SCREEN), {'blueflag': BLUE})

    def test_both_at_once_the_yellow_box_stays_and_the_blue_flag_goes_below(self):
        places = FlagStack().places(self.homes(), {'yellowflag', 'blueflag'}, SCREEN)
        self.assertEqual(places, {'yellowflag': YELLOW, 'blueflag': BLUE_BELOW})

    def test_flags_apart_stay_where_they_are(self):
        apart = (800, 900, 480, 24)
        places = FlagStack().places(self.homes(apart), {'yellowflag', 'blueflag'}, SCREEN)
        self.assertEqual(places, {'yellowflag': YELLOW, 'blueflag': apart})

    def test_the_other_side_where_one_would_leave_the_screen(self):
        low_yellow = (800, 1000, 320, 70)
        homes = {'yellowflag': low_yellow, 'blueflag': (820, 1010, 480, 24)}
        places = FlagStack().places(homes, {'yellowflag', 'blueflag'}, SCREEN)
        self.assertEqual(places['blueflag'], (820, 1000 - GAP - 24, 480, 24))  # above it
        top_blue = (820, 0, 480, 24)
        stack = FlagStack()
        stack.places({'yellowflag': YELLOW, 'blueflag': top_blue}, {'blueflag'}, SCREEN)
        homes = {'yellowflag': (800, 5, 320, 110), 'blueflag': top_blue}
        places = stack.places(homes, {'yellowflag', 'blueflag'}, SCREEN)
        self.assertEqual(places['yellowflag'], (800, 24 + GAP, 320, 110))  # below it

    def test_reset_brings_them_home(self):
        stack = FlagStack()
        stack.places(self.homes(), {'yellowflag', 'blueflag'}, SCREEN)
        stack.reset()
        self.assertEqual(stack.places(self.homes(), {'blueflag'}, SCREEN), {'blueflag': BLUE})


if __name__ == '__main__':
    unittest.main()
