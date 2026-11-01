import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import race
from turbohud.core.flags import FLAGS, flag_code, flag_emoji, flag_text

GERMANY = [name for name, _code in FLAGS].index('Germany')
NORTHERN_CYPRUS = [name for name, _code in FLAGS].index('Northern_Cyprus')


def lap(start, step=10_000, count=4):
    return tuple(start + i * step for i in range(count))


def player(name, checkpoints, laps=None, local=False, finished=False, in_pit=False, flag=GERMANY):
    laps = len(checkpoints) - 1 if laps is None else laps
    return race.PlayerState(name, flag, laps, tuple(checkpoints), finished, in_pit, local)


class FlagTests(unittest.TestCase):
    def test_codes_and_emoji(self):
        self.assertEqual(len(FLAGS), 222)
        self.assertEqual(flag_code(GERMANY), 'DE')
        self.assertEqual(flag_emoji('DE'), '\U0001F1E9\U0001F1EA')
        self.assertIsNone(flag_code(0))
        self.assertIsNone(flag_code(999))

    def test_places_without_a_code_show_three_letters(self):
        self.assertIsNone(flag_code(NORTHERN_CYPRUS))
        self.assertEqual(flag_text(NORTHERN_CYPRUS), 'NCY')
        self.assertEqual(flag_text(0), '')


class RankingTests(unittest.TestCase):
    def test_more_checkpoints_first_then_who_got_there_first(self):
        a = player('A', [lap(0), lap(40_000, count=3)])
        b = player('B', [lap(0), lap(41_000, count=3)])
        c = player('C', [lap(0), lap(40_500, count=2)])
        self.assertEqual([p.name for p in race.ranked([c, b, a])], ['A', 'B', 'C'])

    def test_finished_players_lead_by_finish_time(self):
        done_late = player('Late', [lap(0), lap(50_000)], laps=1, finished=True)
        done_early = player('Early', [lap(0), lap(45_000)], laps=1, finished=True)
        racing = player('Racing', [lap(0), lap(40_000), lap(80_000, count=2)], laps=2)
        self.assertEqual([p.name for p in race.ranked([racing, done_late, done_early])], ['Early', 'Late', 'Racing'])


class GapTests(unittest.TestCase):
    def test_at_the_last_checkpoint_both_passed(self):
        me = player('Me', [lap(0), lap(40_000, count=3)], local=True)
        ahead = player('Ahead', [lap(0), lap(38_000)])
        behind = player('Behind', [lap(0), lap(41_500, count=2)])
        self.assertEqual(race.gap(ahead, me), ('time', -2_000))
        self.assertEqual(race.gap(behind, me), ('time', 1_500))

    def test_a_lap_or_more_apart(self):
        me = player('Me', [lap(0), lap(40_000), lap(80_000, count=2)], local=True)
        lapped = player('Lapped', [lap(0), lap(40_000, count=1)])
        self.assertEqual(race.gap(lapped, me), ('laps', 1))
        self.assertEqual(race.gap(me, lapped), ('laps', -1))

    def test_texts(self):
        self.assertEqual(race.gap_text(('time', -12_345)), '-1.234')
        self.assertEqual(race.gap_text(('laps', 2)), '+2 L')
        self.assertEqual(race.gap_text(None), '')


class RowsTests(unittest.TestCase):
    def test_rows_show_position_flag_name_pit_and_gap(self):
        me = player('Me', [lap(0), lap(40_000, count=3)], local=True)
        ahead = player('Ahead', [lap(0), lap(38_000)], in_pit=True)
        rows = race.players_rows([me, ahead])
        self.assertEqual([r.text for r in rows], ['1. Ahead', '2. Me'])
        self.assertEqual((rows[0].flag, rows[0].tail, rows[0].right, rows[0].right_color), ('DE', '  PIT', '-0.200', 'behind'))
        self.assertEqual((rows[1].color, rows[1].right), ('accent', ''))

    def test_many_players_show_the_leader_and_those_around_me(self):
        players = [player(f'P{i}', [lap(0), lap(40_000 + i * 100, count=3)], local=(i == 12)) for i in range(20)]
        shown = race.shown_players(players)
        positions = [pos for pos, _p in shown]
        self.assertEqual(len(shown), race.MAX_PLAYER_ROWS)
        self.assertEqual(positions[0], 1)
        self.assertIn(13, positions)  # me (P12) is 13th
        self.assertEqual(positions[1:], list(range(10, 17)))

    def test_long_names_are_cut(self):
        rows = race.players_rows([player('A' * 30, [lap(0)], local=True)])
        self.assertEqual(len(rows[0].text), len('1. ') + race.MAX_NAME_SHOWN)


class SpeedUnitTests(unittest.TestCase):
    def test_mph(self):
        car = race.CarState(True, 0, 1, True, 0, 200 / 3.6)
        self.assertEqual(race.car_sections(car)['speed'][0].text, '200 km/h')
        self.assertEqual(race.car_sections(car, speed_unit='mph')['speed'][0].text, '124 mph')


if __name__ == '__main__':
    unittest.main()
