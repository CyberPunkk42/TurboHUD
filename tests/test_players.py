import dataclasses
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


N = 4  # checkpoints per lap in these tests


class BlueFlagTests(unittest.TestCase):
    """The local player has done one lap and 3 of 4 checkpoints of the next; a car a lap
    ahead comes up behind them."""

    me = player('Me', [lap(0), lap(400_000, 10_000, 3)], local=True)  # 40.0, 41.0, 42.0 s

    def test_a_car_a_lap_ahead_close_behind_on_track(self):
        # Its last checkpoint is my second of this lap (41.0 s), which it passed at 42.2 s.
        fast = player('Fast', [lap(0, 40_000), lap(160_000, 40_000), (405_000, 422_000)], laps=2)
        # theirs: 4 + 4 + 2 = 10 checkpoints, mine 4 + 3 = 7: 3 ahead, 1 behind on the track.
        self.assertAlmostEqual(race.blue_flag([self.me, fast], now=425_000), 1.2)

    def test_the_gap_grows_while_it_does_not_reach_my_next_checkpoint(self):
        fast = player('Fast', [lap(0, 40_000), lap(160_000, 40_000), (405_000, 422_000)], laps=2)
        # I passed my third at 42.0 s; at 43.5 s it still has not: at least 1.5 s behind.
        self.assertAlmostEqual(race.blue_flag([self.me, fast], now=435_000), 1.5)
        self.assertIsNone(race.blue_flag([self.me, fast], now=445_000))  # over 2 s

    def test_at_my_checkpoint_it_has_not_passed_yet(self):
        fast = player('Fast', [lap(0, 40_000), lap(160_000, 40_000), (405_000, 411_000, 421_000)], laps=2)
        self.assertAlmostEqual(race.blue_flag([self.me, fast], now=422_000), 0.1)

    def test_gone_once_it_passed(self):
        fast = player('Fast', [lap(0, 40_000), lap(160_000, 40_000), (405_000, 411_000, 421_000, 424_000)], laps=2)
        self.assertIsNone(race.blue_flag([self.me, fast], now=425_000))

    def test_a_car_on_the_same_lap_just_ahead_is_no_blue_flag(self):
        near = player('Near', [lap(0), lap(390_000, 10_000)])
        self.assertIsNone(race.blue_flag([self.me, near], now=430_000))

    def test_any_car_counts_and_the_nearest_wins(self):
        first = player('First', [lap(0, 40_000), lap(160_000, 40_000), (405_000, 422_000)], laps=2)
        second = player('Second', [lap(0, 40_000), lap(160_000, 40_000), (404_000, 418_000)], laps=2)
        self.assertAlmostEqual(race.blue_flag([self.me, first, second], now=421_000), 0.8)

    def test_none_before_anyone_completed_a_lap_or_in_the_pits(self):
        start = player('Me', [lap(0, count=3)], local=True)
        other = player('Other', [lap(0, count=2)])
        self.assertIsNone(race.blue_flag([start, other], now=300_000))
        fast = player('Fast', [lap(0, 40_000), lap(160_000, 40_000), (405_000, 422_000)], laps=2, in_pit=True)
        self.assertIsNone(race.blue_flag([self.me, fast], now=425_000))

    def test_opacity_from_faint_at_two_seconds_to_full_at_half_a_second(self):
        self.assertIsNone(race.blue_flag_opacity(None))
        self.assertIsNone(race.blue_flag_opacity(2.01))
        self.assertAlmostEqual(race.blue_flag_opacity(2.0), race.BLUE_FAINT)
        self.assertAlmostEqual(race.blue_flag_opacity(1.25), (race.BLUE_FAINT + 1) / 2)
        self.assertEqual(race.blue_flag_opacity(0.5), 1.0)
        self.assertEqual(race.blue_flag_opacity(0.0), 1.0)


class BlueFlagSectionTests(unittest.TestCase):
    def test_race_sections_carry_the_opacity_only_while_a_car_comes(self):
        me = player('Me', [lap(0), lap(400_000, 10_000, 3)], local=True)
        fast = player('Fast', [lap(0, 40_000), lap(160_000, 40_000), (405_000, 422_000)], laps=2)
        state = race.LapState(lap_starts=(0, 400_000), laps_completed=1, laps_to_finish=5, clock=425_000,
                              time_limit=0, checkpoints=(), players=(me, fast))
        snapshot = race.Snapshot(status=race.RACING, state=state, running=False, read_at=10.0, moved_at=10.0)
        sections = race.race_sections(snapshot, 10.5)
        self.assertAlmostEqual(sections['blue'], race.blue_flag_opacity(1.2))
        alone = race.Snapshot(status=race.RACING, state=dataclasses.replace(state, players=(me,)), moved_at=10.0)
        self.assertNotIn('blue', race.race_sections(alone, 10.5))


class StandingsTests(unittest.TestCase):
    def test_a_swap_shows_only_once_it_lasted(self):
        a = player('A', [lap(0), lap(40_000, count=3)])
        b = player('B', [lap(0), lap(40_500, count=3)])
        swapped_b = player('B', [lap(0), lap(40_500, count=4)])  # B passed one more: ahead
        standings = race.Standings(hold=0.3)
        self.assertEqual([p.name for p in standings.order([a, b], 10.0)], ['A', 'B'])
        self.assertEqual([p.name for p in standings.order([a, swapped_b], 10.1)], ['A', 'B'])  # held
        self.assertEqual([p.name for p in standings.order([a, b], 10.2)], ['A', 'B'])  # swapped back
        self.assertEqual([p.name for p in standings.order([a, swapped_b], 10.3)], ['A', 'B'])
        self.assertEqual([p.name for p in standings.order([a, swapped_b], 10.5)], ['A', 'B'])
        shown = standings.order([a, swapped_b], 10.65)
        self.assertEqual([p.name for p in shown], ['B', 'A'])  # lasted 0.3 s
        self.assertIs(shown[0], swapped_b)  # the latest data, for live gaps

    def test_held_order_keeps_the_latest_data(self):
        a = player('A', [lap(0), lap(40_000, count=3)])
        b = player('B', [lap(0), lap(40_500, count=4)])
        standings = race.Standings()
        standings.order([a, player('B', [lap(0), lap(40_500, count=2)])], 0.0)
        held = standings.order([a, b], 0.1)
        self.assertEqual([p.name for p in held], ['A', 'B'])
        self.assertIs(held[1], b)

    def test_joining_players_show_at_once(self):
        a = player('A', [lap(0), lap(40_000, count=3)])
        c = player('C', [lap(0), lap(39_000, count=4)])
        standings = race.Standings()
        standings.order([a], 0.0)
        self.assertEqual([p.name for p in standings.order([a, c], 0.1)], ['C', 'A'])


def car(name, position, local=False, in_pit=False):
    return race.PlayerState(name, GERMANY, 1, (lap(0),), False, in_pit, local, position)


class RadarTests(unittest.TestCase):
    """The local car drives north (+z) at 40 a second; reads come every 0.05 s."""

    def drive(self, others_at, steps=4, speed=40.0, others_move=True):
        radar = race.Radar()
        view = None
        for step in range(steps):
            t = step * 0.05
            me = car('Me', (0.0, speed * t), local=True)
            others = [car(name, (x, z + (speed * t if others_move else 0.0))) for name, (x, z) in others_at.items()]
            view = radar.update([me, *others], t)
        return view

    def test_nothing_without_a_car_close_behind(self):
        self.assertIsNone(self.drive({}))
        self.assertIsNone(self.drive({'Far': (0.0, -40.0)}))  # 1 s behind
        self.assertIsNone(self.drive({'Ahead': (0.0, 10.0)}))  # ahead does not count

    def test_faint_at_half_a_second_full_from_a_tenth(self):
        # Behind by 0.5 s: nose to tail 20 at 40 a second; centres are a car length more apart.
        half = self.drive({'Behind': (0.0, -(20.0 + race.CAR_LENGTH))})
        self.assertAlmostEqual(half.opacity, race.RADAR_FAINT, places=2)
        tenth = self.drive({'Behind': (0.0, -(4.0 + race.CAR_LENGTH))})
        self.assertAlmostEqual(tenth.opacity, 1.0)
        beside = self.drive({'Beside': (3.0, 0.0)})
        self.assertEqual(beside.opacity, 1.0)
        self.assertEqual(beside.blips[0].seconds, 0.0)

    def test_sides_and_directions(self):
        view = self.drive({'Right': (3.0, -1.0)})
        blip = view.blips[0]
        self.assertAlmostEqual(blip.side, 3.0)  # on the right: positive
        self.assertAlmostEqual(blip.ahead, -1.0)
        self.assertAlmostEqual(blip.angle, 0.0)  # same direction

    def test_far_to_the_side_does_not_count(self):
        # Another part of the track next to this one, 15 to the side.
        self.assertIsNone(self.drive({'Other road': (15.0, -2.0)}))

    def test_standing_still_or_in_the_pits_shows_nothing(self):
        self.assertIsNone(self.drive({'Beside': (3.0, 0.0)}, speed=0.0))
        radar = race.Radar()
        for step in range(4):
            t = step * 0.05
            me = car('Me', (0.0, 40 * t), local=True)
            view = radar.update([me, car('Pit', (3.0, 40 * t), in_pit=True)], t)
        self.assertIsNone(view)

    def test_opacity_curve(self):
        self.assertIsNone(race.radar_opacity(None))
        self.assertIsNone(race.radar_opacity(0.51))
        self.assertAlmostEqual(race.radar_opacity(0.3), (race.RADAR_FAINT + 1) / 2)
        self.assertEqual(race.radar_opacity(0.05), 1.0)
