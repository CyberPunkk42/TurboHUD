"""The player list as the cars around the local one on the track, and the lap times' classes in
the class list's order (asked for by the user on 2026-11-12)."""

import dataclasses
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import race
from turbohud.core.flags import FLAGS

GERMANY = [name for name, _code in FLAGS].index('Germany')
LAP = 4  # checkpoints a lap


def car(name, lap_time, passes, local=False, tag='', compound=None, start=0):
    """A car that passes a checkpoint every lap_time / LAP from `start`, `passes` times so far."""
    step = lap_time // LAP
    times = [start + i * step for i in range(passes)]
    laps = tuple(tuple(times[i : i + LAP]) for i in range(0, len(times), LAP))
    completed = max(len(laps) - 1, 0)
    return dataclasses.replace(
        race.PlayerState(name, GERMANY, completed, laps, False, False, local), tag=tag, compound=compound
    )


class TrackGapTests(unittest.TestCase):
    """Cars placed by where they are on the track and the gap worked out at the car behind's pace
    (reported by the user on 2026-11-12: a stopped car put others minutes away and out of order)."""

    def test_a_car_about_to_be_lapped_is_just_ahead_on_the_track(self):
        me = car('Me', 40_000, 10, local=True)  # at 90 s: just past a checkpoint
        slow = car('Slow', 60_000, 6)  # a lap down, 15 s past the same checkpoint: nearly at the next
        self.assertEqual(race.gap(slow, me), ('laps', 1))  # in the race: a lap behind
        self.assertEqual(race.track_gap(slow, me, clock=90_000), ('time', -9_900))  # 0.99 of my 10 s

    def test_a_car_a_lap_up_coming_up_behind_is_behind(self):
        me = car('Me', 60_000, 6, local=True)
        fast = car('Fast', 40_000, 10)
        self.assertEqual(race.gap(fast, me), ('laps', -1))
        self.assertEqual(race.track_gap(fast, me, clock=90_000), ('time', 9_900))  # at its own pace

    def test_a_stopped_car_keeps_a_sensible_gap_and_its_place(self):
        # Standing at a checkpoint for minutes: before, those passing it later were minutes "behind".
        me = car('Me', 40_000, 6, local=True)  # last pass at 50 s, then stopped
        ahead = car('Ahead', 40_000, 7, start=290_000 - 60_000)  # a checkpoint further, passed at 290 s
        behind = car('Behind', 40_000, 5, start=290_000 - 40_000)  # a checkpoint short of me
        self.assertGreater(race.track_offset(ahead, me, clock=300_000)[0], 0)
        self.assertLess(race.track_offset(behind, me, clock=300_000)[0], 0)
        for other in (ahead, behind):
            found = race.track_offset(other, me, clock=300_000)[1]
            self.assertLess(abs(found[1]), 40_000)  # within a lap's time, not minutes

    def test_a_cars_splits_are_worked_out_once_a_lap(self):
        fast = car('Fast', 40_000, 23)
        self.assertIs(race.lap_splits(fast, LAP), race.lap_splits(fast, LAP))
        self.assertEqual(race.lap_splits(fast, LAP), [10_000] * LAP)
        self.assertIsNone(race.lap_splits(car('New', 40_000, 3), LAP))  # no whole lap yet


class RelativeTests(unittest.TestCase):
    CLOCK = 75_000

    def field(self, ahead=6, behind=6):
        """Me with cars spread out in front of and behind me on the same lap."""
        me = car('Me', 40_000, 8, local=True, start=0)
        cars = [car(f'A{i}', 40_000, 8, start=-300 * i) for i in range(1, ahead + 1)]  # earlier: ahead
        cars += [car(f'B{i}', 40_000, 8, start=300 * i) for i in range(1, behind + 1)]
        return me, cars

    def names(self, rows):
        return [row.text.split('. ', 1)[1] if row.text else '' for row in rows]

    def test_the_leader_then_three_ahead_and_three_behind(self):
        me, cars = self.field()
        rows = race.players_rows([me, *cars], clock=self.CLOCK)
        self.assertEqual(self.names(rows), ['A6', 'A3', 'A2', 'A1', 'Me', 'B1', 'B2', 'B3'])
        self.assertEqual(rows[race.ME_ROW].color, 'accent')
        self.assertEqual(rows[3].middle, '-0.030')
        self.assertEqual(rows[5].middle, '+0.030')
        self.assertTrue(rows[0].middle.startswith('-'))  # the leader, with its race gap

    def test_a_leader_shown_below_or_me_leaves_the_top_row_empty(self):
        me, cars = self.field(ahead=1, behind=5)
        rows = race.players_rows([me, *cars], clock=self.CLOCK)
        self.assertEqual(self.names(rows)[:5], ['', '', '', 'A1', 'Me'])
        self.assertEqual(len(rows), race.ME_ROW + 1 + race.RELATIVE_BEHIND)
        me, cars = self.field(ahead=0, behind=5)
        rows = race.players_rows([me, *cars], clock=self.CLOCK)
        self.assertEqual(self.names(rows)[: race.ME_ROW + 1], ['', '', '', '', 'Me'])

    def test_the_leader_sees_the_backmarkers_ahead_on_the_track(self):
        me = car('Me', 40_000, 10, local=True)
        slow = car('Slow', 60_000, 6)
        rows = race.players_rows([me, slow], clock=90_000)
        ahead = rows[race.ME_ROW - 1]
        self.assertTrue(ahead.text.endswith('Slow'))
        self.assertEqual(ahead.color, race.LAPPED_COLOR)  # a lap down
        self.assertEqual(ahead.middle, '-0.990')
        self.assertEqual(rows[0].text, '')  # I lead: no leader's row

    def test_a_car_a_lap_up_is_in_the_warm_colour(self):
        me = car('Me', 60_000, 6, local=True)
        fast = car('Fast', 40_000, 10)
        behind = race.players_rows([me, fast], clock=90_000)[race.ME_ROW + 1]
        self.assertTrue(behind.text.endswith('Fast'))
        self.assertEqual(behind.color, race.LAPPING_COLOR)

    def test_on_the_grid_the_race_order_fills_in(self):
        me = car('Me', 40_000, 0, local=True)
        others = [car('P1', 40_000, 0), car('P3', 40_000, 0)]
        order = [others[0], me, others[1]]
        rows = race.players_rows([me, *others], order)
        self.assertEqual([row.text.split('. ', 1)[-1] for row in rows[3:6]], ['P1', 'Me', 'P3'])
        self.assertEqual({row.middle for row in rows}, {''})  # no gaps yet

    def test_each_car_with_its_class_place_and_tire(self):
        me = car('Me', 40_000, 8, local=True, tag='GT3', compound=0)
        lmp = car('Proto', 40_000, 8, tag='LMP', compound=2, start=-1000)
        gt = car('Gt', 40_000, 8, tag='GT3', compound=1, start=1000)
        rows = race.players_rows(
            [me, lmp, gt], class_tags=('LMP', 'GT3'), compounds=3, order=[lmp, me, gt], clock=self.CLOCK
        )
        shown = {row.text.split('. ', 1)[1]: row for row in rows if row.text}
        self.assertEqual((shown['Proto'].tag, shown['Proto'].tag_color), ('LMP P1', '#805AD5'))
        self.assertEqual(shown['Me'].tag, 'GT3 P1')
        self.assertEqual(shown['Gt'].tag, 'GT3 P2')
        self.assertEqual([shown[n].tyre for n in ('Proto', 'Me', 'Gt')], ['H', 'S', 'M'])
        plain = race.players_rows([me, lmp, gt], clan_tags=True, clock=self.CLOCK)
        self.assertEqual({row.tag for row in plain if row.text}, {'GT3', 'LMP'})  # no classes: clan tags

    def test_a_spectator_keeps_the_race_order(self):
        others = [car('P1', 40_000, 8), car('P2', 40_000, 8, start=1000)]
        rows = race.players_rows(others, watching=True)
        self.assertEqual([row.text for row in rows], ['1. P1', '2. P2'])


class NumberingTests(unittest.TestCase):
    def test_numbers_line_up_to_the_largest(self):
        self.assertEqual(race.numbered(9, 'A', 12), ' 9. A')
        self.assertEqual(race.numbered(12, 'A', 12), '12. A')
        self.assertEqual(race.numbered(3, 'A', 8), '3. A')


class ClassOrderTests(unittest.TestCase):
    def test_the_class_list_decides_not_the_grid(self):
        gt4 = car('Gt4', 40_000, 8, tag='GT4')
        lmp = car('Proto', 40_000, 8, tag='LMP', start=1000)  # qualified behind
        gt3 = car('Gt3', 40_000, 8, tag='GT3', start=2000)
        other = car('Team', 40_000, 8, tag='FTR', start=3000)
        rows = race.lap_times_rows(
            [gt4, lmp, gt3, other], order=[gt4, lmp, gt3, other], class_tags=race.CLASS_TAGS
        )
        self.assertEqual([row.rule for row in rows if row.rule], ['LMP', 'GT3', 'GT4', race.OTHER_CLASS])


if __name__ == '__main__':
    unittest.main()
