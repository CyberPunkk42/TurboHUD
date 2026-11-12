"""The lap times' tire compound column and the columns one can turn off (asked for by the user
on 2026-11-12)."""

import dataclasses
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import hud, race
from turbohud.core import settings as s
from turbohud.core.flags import FLAGS

GERMANY = [name for name, _code in FLAGS].index('Germany')


def driver(name, compound=None, start=0):
    laps = [tuple(start + i * 10_000 for i in range(4)), (start + 40_000,)]
    return dataclasses.replace(
        race.PlayerState(name, GERMANY, 1, tuple(laps), False, False, False), compound=compound
    )


class CompoundMarkTests(unittest.TestCase):
    def test_as_in_f1_softest_first(self):
        self.assertEqual(race.compound_mark(0, 1), ('M', '#d4a20f'))  # one compound: a darker yellow
        self.assertEqual([race.compound_mark(i, 2) for i in range(2)], [('S', race.SOFT), ('H', race.HARD)])
        self.assertEqual([race.compound_mark(i, 3)[0] for i in range(3)], ['S', 'M', 'H'])
        self.assertEqual(race.compound_mark(1, 3)[1], race.MEDIUM)
        self.assertEqual([race.compound_mark(i, 5)[0] for i in range(5)], ['X', 'U', 'S', 'M', 'H'])

    def test_a_count_not_known_is_the_fewest_that_hold_the_index(self):
        self.assertEqual(race.compound_mark(0, None)[0], 'M')
        self.assertEqual(race.compound_mark(1, None)[0], 'H')  # 2 at least
        self.assertEqual(race.compound_mark(2, 2)[0], 'H')  # 3 at least: the hardest of 3

    def test_nothing_without_a_compound(self):
        self.assertIsNone(race.compound_mark(None, 3))
        self.assertIsNone(race.compound_mark(-1, 3))
        self.assertIsNone(race.compound_mark(7, None))


class WetTests(unittest.TestCase):
    """A track whose name marks a wet race: every car on a blue W (asked for by the user on 2026-11-12)."""

    def test_a_wet_marker_in_brackets_in_any_case(self):
        for name in ('Spa (WET)', 'Monza (RW)', 'Imola (QW)', 'Suzuka (W)', 'Spa (wet)', 'Spa ( Rw )'):
            self.assertTrue(race.is_wet(name), name)
        for name in ('Spa WET', 'Wet Hills', 'Spa (Dry)', 'Spa (WETTER)', 'Spa (W2)', 'Spa', '', None):
            self.assertFalse(race.is_wet(name), name)

    def test_every_car_on_a_blue_w(self):
        players = [driver('A', 0), driver('B', 2, 100), driver('C', None, 200)]
        rows = race.lap_times_rows(players, clock=50_000, compounds=3, wet=True)
        self.assertEqual({(r.tyre, r.tyre_color) for r in rows[1:]}, {race.WET_MARK})
        self.assertEqual(race.WET_MARK[0], 'W')
        dry = race.lap_times_rows(players, clock=50_000, compounds=3)
        self.assertNotIn(race.WET_MARK, {(r.tyre, r.tyre_color) for r in dry})

    def test_the_player_list_too(self):
        me = dataclasses.replace(driver('Me', 0), local=True)
        rows = race.players_rows([me, driver('B', 1, 100)], compounds=2, wet=True)
        self.assertEqual({r.tyre for r in rows if r.text}, {'W'})


class TyreColumnTests(unittest.TestCase):
    def rows(self, columns=s.LAP_COLUMNS, compounds=3):
        players = [driver('A', 0), driver('B', 2, 100), driver('C', None, 200)]
        return race.lap_times_rows(players, clock=50_000, columns=columns, compounds=compounds)

    def test_each_drivers_compound_in_its_colour(self):
        rows = self.rows()
        self.assertEqual(
            [(r.tyre, r.tyre_color) for r in rows], [('', ''), ('S', race.SOFT), ('H', race.HARD), ('', '')]
        )

    def test_one_compound_is_a_darker_medium(self):
        rows = race.lap_times_rows([driver('A', 0)], clock=50_000, compounds=1)
        self.assertEqual((rows[1].tyre, rows[1].tyre_color), ('M', '#d4a20f'))

    def test_the_column_lies_between_the_lap_number_and_the_best_lap(self):
        def measure(text, size):
            return len(text) * size / 2

        lines = hud.hud_lines(self.rows())
        middle_end = hud.middle_right(lines, 400, 14, measure)
        tyre_end = hud.tyre_right(lines, middle_end, measure)
        before_end = hud.before_right(lines, middle_end, measure)
        self.assertLess(tyre_end, middle_end)
        self.assertAlmostEqual(tyre_end - before_end, (hud.TYRE_WIDTH + hud.COLUMN_GAP) * lines[1].size)
        without = hud.hud_lines(self.rows(columns=('flag', 'lap', 'best', 'current')))
        self.assertEqual(hud.before_right(without, middle_end, measure), tyre_end)  # no room kept
        self.assertGreater(hud.lines_width(lines, measure), hud.lines_width(without, measure))

    def test_the_lap_number_s_place_is_the_same_with_the_tire_column_s_end_given(self):
        # draw_hud works tyre_right out once and hands it on, so the middle column is
        # measured once a frame, not twice (2026-11-12).
        measured = []

        def measure(text, size):
            measured.append(text)
            return len(text) * size / 2

        lines = hud.hud_lines(self.rows())
        middle_end = hud.middle_right(lines, 400, 14, measure)
        tyre_end = hud.tyre_right(lines, middle_end, measure)
        measured.clear()
        given = hud.before_right(lines, middle_end, measure, tyre_end)
        self.assertEqual(measured, [])
        self.assertEqual(given, hud.before_right(lines, middle_end, measure))


class ColumnTests(unittest.TestCase):
    def rows(self, columns):
        players = [driver('A', 0), driver('B', 1, 100)]
        return race.lap_times_rows(players, clock=50_000, columns=columns, compounds=2)

    def test_all_shown_by_default(self):
        row = self.rows(s.LAP_COLUMNS)[1]
        self.assertTrue(row.flag and row.before and row.tyre and row.middle and row.right)

    def test_each_can_be_turned_off(self):
        row = self.rows(('lap', 'tyre', 'best', 'current'))[1]
        self.assertEqual(row.flag, '')
        self.assertEqual(self.rows(('flag', 'tyre', 'best', 'current'))[1].before, '')
        self.assertEqual(self.rows(('flag', 'lap', 'best', 'current'))[1].tyre, '')
        self.assertEqual(self.rows(('flag', 'lap', 'tyre', 'best'))[1].right, '')

    def test_without_the_best_lap_the_current_one_takes_its_place(self):
        full = self.rows(s.LAP_COLUMNS)
        rows = self.rows(('flag', 'lap', 'tyre', 'current'))
        self.assertEqual([(r.middle, r.right) for r in rows], [(r.right, '') for r in full])
        self.assertEqual(rows[0].middle, 'Last')  # the heading too
        bare = self.rows(('flag',))
        self.assertEqual({(r.middle, r.right, r.before, r.tyre) for r in bare}, {('', '', '', '')})


class SettingsTests(unittest.TestCase):
    def test_the_shown_columns_are_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text(json.dumps({}))
            self.assertEqual(s.load_settings(path).lap_columns, s.LAP_COLUMNS)  # all, as they came
            s.save_settings(path, s.Settings(lap_columns=('tyre', 'best')))
            self.assertEqual(s.load_settings(path).lap_columns, ('tyre', 'best'))
            s.save_settings(path, s.Settings(lap_columns=()))
            self.assertEqual(s.load_settings(path).lap_columns, ())  # all off stays off
            path.write_text(json.dumps({'lap_columns': ['best', 'nonsense', 'flag', 7]}))
            self.assertEqual(s.load_settings(path).lap_columns, ('flag', 'best'))  # in order, known only


if __name__ == '__main__':
    unittest.main()
