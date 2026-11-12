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
    def test_a_car_about_to_be_lapped_is_just_ahead_on_the_track(self):
        me = car('Me', 40_000, 10, local=True)  # at 90 s: a lap and two checkpoints further
        slow = car('Slow', 60_000, 6)  # a lap down, at the same checkpoint 1.5 s earlier
        self.assertEqual(race.gap(slow, me), ('laps', 1))  # in the race: a lap behind
        self.assertEqual(race.track_gap(slow, me), ('time', -15_000))  # on the track: just ahead

    def test_a_car_a_lap_up_coming_up_behind_is_behind(self):
        me = car('Me', 60_000, 6, local=True)
        fast = car('Fast', 40_000, 10)
        self.assertEqual(race.gap(fast, me), ('laps', -1))
        self.assertEqual(race.track_gap(fast, me), ('time', 15_000))


class RelativeTests(unittest.TestCase):
    def field(self, ahead=6, behind=6):
        """Me with cars spread out in front of and behind me on the same lap."""
        me = car('Me', 40_000, 8, local=True, start=0)
        cars = [car(f'A{i}', 40_000, 8, start=-1000 * i) for i in range(1, ahead + 1)]  # earlier: ahead
        cars += [car(f'B{i}', 40_000, 8, start=1000 * i) for i in range(1, behind + 1)]
        return me, cars

    def test_four_ahead_three_behind_and_me_in_the_middle(self):
        me, cars = self.field()
        rows = race.players_rows([me, *cars])
        names = [row.text.split('. ', 1)[1] for row in rows]
        self.assertEqual(names, ['A4', 'A3', 'A2', 'A1', 'Me', 'B1', 'B2', 'B3'])
        self.assertEqual(rows[race.RELATIVE_AHEAD].color, 'accent')
        self.assertEqual(rows[3].middle, '-0.100')
        self.assertEqual(rows[5].middle, '+0.100')

    def test_with_fewer_cars_ahead_blank_rows_keep_me_in_the_middle(self):
        me, cars = self.field(ahead=1, behind=5)
        rows = race.players_rows([me, *cars])
        self.assertEqual([row.text for row in rows[:3]], ['', '', ''])
        self.assertTrue(rows[race.RELATIVE_AHEAD].text.endswith('Me'))
        self.assertEqual(len(rows), race.RELATIVE_AHEAD + 1 + race.RELATIVE_BEHIND)

    def test_the_leader_sees_the_backmarkers_ahead_on_the_track(self):
        me = car('Me', 40_000, 10, local=True)
        slow = car('Slow', 60_000, 6)
        rows = race.players_rows([me, slow])
        ahead = rows[race.RELATIVE_AHEAD - 1]
        self.assertTrue(ahead.text.endswith('Slow'))
        self.assertEqual(ahead.color, race.LAPPED_COLOR)  # a lap down
        self.assertEqual(ahead.middle, '-1.500')
        self.assertTrue(rows[race.RELATIVE_AHEAD].text.startswith(race.numbered(1, '', 2)[:2]))  # P1

    def test_a_car_a_lap_up_is_in_the_warm_colour(self):
        me = car('Me', 60_000, 6, local=True)
        fast = car('Fast', 40_000, 10)
        behind = race.players_rows([me, fast])[race.RELATIVE_AHEAD + 1]
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
        rows = race.players_rows([me, lmp, gt], class_tags=('LMP', 'GT3'), compounds=3, order=[lmp, me, gt])
        shown = {row.text.split('. ', 1)[1]: row for row in rows if row.text}
        self.assertEqual((shown['Proto'].tag, shown['Proto'].tag_color), ('LMP P1', '#805AD5'))
        self.assertEqual(shown['Me'].tag, 'GT3 P1')
        self.assertEqual(shown['Gt'].tag, 'GT3 P2')
        self.assertEqual([shown[n].tyre for n in ('Proto', 'Me', 'Gt')], ['H', 'S', 'M'])
        plain = race.players_rows([me, lmp, gt], clan_tags=True)
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
