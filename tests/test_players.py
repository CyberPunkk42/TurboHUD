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
        self.assertEqual(flag_emoji('DE'), '\U0001f1e9\U0001f1ea')
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
        # A 2-lap race: two are in, one is still on its last lap.
        done_late = player('Late', [lap(0), lap(40_000), lap(90_000, count=1)], laps=2, finished=True)
        done_early = player('Early', [lap(0), lap(40_000), lap(85_000, count=1)], laps=2, finished=True)
        racing = player('Racing', [lap(0), lap(42_000, count=3)], laps=1)
        self.assertEqual(
            [p.name for p in race.ranked([racing, done_late, done_early])], ['Early', 'Late', 'Racing']
        )

    def test_a_lapped_car_finishing_behind_the_winner_stays_behind_the_lead_lap(self):
        # A 3-lap race seen in a drive: the winner is in, and the lapped car (2 laps)
        # finishes right after, before the others on the lead lap come in.
        winner = player(
            'Winner', [lap(0), lap(40_000), lap(80_000), lap(120_000, count=1)], laps=3, finished=True
        )
        lapped = player('Lapped', [lap(0), lap(60_000), lap(121_000, count=1)], laps=2, finished=True)
        second = player(
            'Second', [lap(0), lap(41_000), lap(81_000), lap(125_000, count=1)], laps=3, finished=True
        )
        third = player('Third', [lap(0), lap(42_000), lap(82_000, count=3)], laps=2)
        self.assertEqual(
            [p.name for p in race.ranked([lapped, third, second, winner])],
            ['Winner', 'Second', 'Third', 'Lapped'],
        )


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
        self.assertEqual(
            (rows[0].flag, rows[0].tail, rows[0].right, rows[0].right_color),
            ('DE', '  PIT', '-0.200', 'behind'),
        )
        self.assertEqual((rows[1].color, rows[1].right), ('accent', ''))

    def test_many_players_show_the_leader_and_those_around_me(self):
        players = [
            player(f'P{i}', [lap(0), lap(40_000 + i * 100, count=3)], local=(i == 12)) for i in range(20)
        ]
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
        fast = player(
            'Fast', [lap(0, 40_000), lap(160_000, 40_000), (405_000, 411_000, 421_000, 424_000)], laps=2
        )
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
        state = race.LapState(
            lap_starts=(0, 400_000),
            laps_completed=1,
            laps_to_finish=5,
            clock=425_000,
            time_limit=0,
            checkpoints=(),
            players=(me, fast),
        )
        snapshot = race.Snapshot(status=race.RACING, state=state, running=False, read_at=10.0, moved_at=10.0)
        sections = race.race_sections(snapshot, 10.5)
        self.assertAlmostEqual(sections['blue'], race.blue_flag_opacity(1.2))
        alone = race.Snapshot(
            status=race.RACING, state=dataclasses.replace(state, players=(me,)), moved_at=10.0
        )
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
            others = [
                car(name, (x, z + (speed * t if others_move else 0.0))) for name, (x, z) in others_at.items()
            ]
            view = radar.update([me, *others], t)
        return view

    def test_nothing_without_a_car_close_behind(self):
        self.assertIsNone(self.drive({}))
        self.assertIsNone(self.drive({'Far': (0.0, -40.0)}))  # 1 s behind
        self.assertIsNone(self.drive({'Far ahead': (0.0, 40.0)}))  # 0.9 s ahead

    def test_a_car_close_ahead_counts_too(self):
        # 10 ahead: nose to tail 10 less a car length, at 40 a second.
        view = self.drive({'Ahead': (0.0, 10.0)})
        self.assertAlmostEqual(view.blips[0].seconds, (10 - race.CAR_LENGTH) / 40, places=3)
        self.assertGreater(view.opacity, 0.85)  # 0.15 s: close to full

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


def moving(name, position, velocity, local=False):
    return race.PlayerState(name, GERMANY, 1, (lap(0),), False, False, local, position, velocity, (0.0, 1.0))


class RadarSteadyTests(unittest.TestCase):
    """As on a hosted online server: positions move on only every other read (0.1 s),
    reads come every 0.05 s, and the game gives each car's velocity and direction."""

    def test_no_blinking_when_positions_update_every_other_read(self):
        radar = race.Radar()
        shown = []
        for step in range(20):
            t = step * 0.05
            updated = (step // 2) * 0.1  # the time of the game's last position update
            me = moving('Me', (0.0, 40.0 * updated), (0.0, 40.0), local=True)
            behind = moving('Behind', (1.0, 40.0 * updated - 12.0), (0.0, 40.0))  # ~0.19 s behind
            view = radar.update([me, behind], t)
            shown.append(view is not None)
            if view is not None:
                blip = view.blips[0]
                self.assertAlmostEqual(blip.ahead, -12.0, delta=0.01)  # carried on together: steady
        self.assertTrue(all(shown[1:]))

    def test_it_stays_a_moment_and_fades_after_the_car_drops_back(self):
        radar = race.Radar()
        me = lambda t: moving('Me', (0.0, 40.0 * t), (0.0, 40.0), local=True)
        for step in range(3):
            t = step * 0.05
            view = radar.update([me(t), moving('Close', (3.0, 40.0 * t), (0.0, 40.0))], t)
        self.assertEqual(view.opacity, 1.0)
        gone = [
            radar.update([me(t), moving('Close', (3.0, 40.0 * t - 60), (0.0, 40.0))], t)
            for t in (0.2, 0.3, 0.4)
        ]
        self.assertTrue(all(v is not None for v in gone))  # held
        self.assertLess(gone[-1].opacity, gone[0].opacity)  # fading
        self.assertIsNone(radar.update([me(0.8), moving('Close', (3.0, 40.0 * 0.8 - 60), (0.0, 40.0))], 0.8))

    def test_a_car_beside_shows_at_once_at_full(self):
        radar = race.Radar()
        view = radar.update(
            [moving('Me', (0.0, 0.0), (0.0, 40.0), local=True), moving('B', (3.0, 0.0), (0.0, 40.0))], 0.0
        )
        self.assertEqual(view.opacity, 1.0)


class BlueFlagAfterPassingTests(unittest.TestCase):
    def test_a_lapper_just_ahead_at_the_same_checkpoint_is_no_flag(self):
        # Seen online: the leader, a lap ahead, drives just in front. Each time the local
        # player reaches the checkpoint it passed a moment before, both are exactly a lap
        # apart in count; it got there first, so it is past: no blue flag (it blinked).
        me = player('Me', [lap(0), lap(400_000, 10_000, 3)], local=True)  # last at 42.0 s
        leader = player('Leader', [lap(0, 40_000), lap(160_000, 40_000), (405_000, 411_000, 419_500)], laps=2)
        self.assertIsNone(race.blue_flag([me, leader], now=422_000))

    def test_same_count_but_it_got_there_later_is_still_a_flag(self):
        me = player('Me', [lap(0), lap(400_000, 10_000, 3)], local=True)
        lapper = player('Lapper', [lap(0, 40_000), lap(160_000, 40_000), (405_000, 411_000, 421_000)], laps=2)
        self.assertAlmostEqual(race.blue_flag([me, lapper], now=421_500), 0.1)


class HealthRowTests(unittest.TestCase):
    def car(self, health):
        return race.CarState(False, 0, 0, False, 0, 30.0, health=health, downforce_from=0.9, slowed_from=0.75)

    def test_colours_follow_the_damage_effect(self):
        self.assertEqual(race.car_sections(self.car(0.99))['health'][0].text, 'Health 99%')
        self.assertEqual(race.car_sections(self.car(126 / 500))['health'][0].text, 'Health 26%')  # as in game
        self.assertEqual(race.car_sections(self.car(1.0))['health'][0].text, 'Health 100%')
        self.assertEqual(race.car_sections(self.car(0.0))['health'][0].text, 'Health 0%')
        self.assertEqual(race.car_sections(self.car(0.99))['health'][0].color, 'text')
        row = race.car_sections(self.car(0.85))['health'][0]
        self.assertEqual((row.color, row.tail), ('lift', '  less downforce'))
        row = race.car_sections(self.car(0.6))['health'][0]
        self.assertEqual((row.color, row.tail), ('behind', '  slowed'))


# A straight track of four lines, 10 apart along z (line i at z = 10 * i).
LINES = tuple(((-5.0, 10.0 * i), (5.0, 10.0 * i)) for i in range(4))


def driving(name, times, z, local=False):
    return race.PlayerState(name, GERMANY, 0, (tuple(times),), local=local, position=(0.0, z))


class LiveGapTests(unittest.TestCase):
    def test_live_between_checkpoints_like_the_delta(self):
        leader = driving('Leader', (0, 10_000, 20_000), z=25.0)  # passed lines 0-2 at 0, 1, 2 s
        me = driving('Me', (5_000, 15_000), z=15.0, local=True)  # halfway from line 1 to line 2
        # The leader was halfway (z = 15) at 1.5 s; the clock says 2.05 s: 0.55 s behind.
        self.assertEqual(race.gap(leader, me, clock=20_500, gates=LINES), ('time', -5_500))
        # It runs on with the clock and my place, not only at checkpoints.
        later = driving('Me', (5_000, 15_000), z=18.0, local=True)
        self.assertEqual(race.gap(leader, later, clock=21_000, gates=LINES), ('time', -3_000))

    def test_a_car_behind_is_live_too(self):
        me = driving('Me', (0, 10_000, 20_000), z=25.0, local=True)
        chaser = driving('Chaser', (5_000, 15_000), z=12.0)
        # I was at z = 12 at 1.2 s; the clock says 2.0 s: it is 0.8 s behind.
        self.assertEqual(race.gap(chaser, me, clock=20_000, gates=LINES), ('time', 8_000))

    def test_without_positions_the_gap_is_at_the_last_common_checkpoint(self):
        leader = race.PlayerState('Leader', GERMANY, 0, ((0, 10_000, 20_000),))
        me = race.PlayerState('Me', GERMANY, 0, ((5_000, 15_000),), local=True)
        self.assertEqual(race.gap(leader, me, clock=20_500, gates=LINES), ('time', -5_000))
        self.assertEqual(race.gap(leader, me), ('time', -5_000))

    def test_lines_written_together_do_not_jump(self):
        # Lines 1 and 2 at the same spot (same time for the leader): my place counts
        # against line 3, the next line with a time of its own.
        lines = (LINES[0], LINES[1], LINES[1], ((-5.0, 30.0), (5.0, 30.0)))
        leader = driving('Leader', (0, 10_000, 10_000, 30_000), z=35.0)
        me = driving('Me', (5_000, 15_000), z=20.0, local=True)  # passed line 1, not yet written 2
        self.assertEqual(race.gap(leader, me, clock=30_000, gates=lines), ('time', -10_000))


class LevelBarTests(unittest.TestCase):
    def test_fuel_tires_and_health_get_levels_with_colours(self):
        car = race.CarState(
            True,
            84_000,
            168_000,
            True,
            int(race.MAX_TIRE_WEAR * 0.9),
            30.0,
            fuel_per_lap=10_000,
            health=0.6,
            downforce_from=0.9,
            slowed_from=0.75,
        )
        levels = race.car_sections(car, laps_to_go=5)['levels']
        self.assertEqual(levels['fuel'], (0.5, 'ahead'))  # 8.4 laps left for 5 to go
        self.assertAlmostEqual(levels['tires'][0], 0.1)
        self.assertEqual(levels['tires'][1], 'behind')  # under 15 %
        self.assertEqual(levels['health'], (0.6, 'behind'))  # slowed

    def test_fuel_bar_is_red_when_it_will_not_last(self):
        car = race.CarState(True, 84_000, 168_000, False, 0, 30.0, fuel_per_lap=20_000)
        self.assertEqual(race.car_sections(car, laps_to_go=5)['levels']['fuel'], (0.5, 'behind'))

    def test_the_bar_sits_below_the_text_across_the_section(self):
        from turbohud.core import hud

        bar = hud.level_bar(300, 50, 1.0, 0.4, 'lift')
        self.assertEqual((bar.x, bar.y, bar.width, bar.height), (14, 43, 272, 8))
        self.assertEqual((bar.fill, bar.color), (0.4, 'lift'))
        fuel = next(s for s in hud.RACE_SECTIONS if s.name == 'fuel')
        plain = hud.base_size(hud.RACE_SECTIONS[0], 1.0, lambda t, size: len(t) * size)
        self.assertTrue(fuel.level and not hud.RACE_SECTIONS[0].level and plain)


def client_car(name, times, velocity, local=False):
    """A car as the game keeps it online as a client: no position, but a velocity."""
    return race.PlayerState(name, GERMANY, 0, (tuple(times),), local=local, velocity=velocity)


class DeadReckoningTests(unittest.TestCase):
    def test_from_the_last_line_on_by_the_velocity(self):
        reckoning = race.DeadReckoning()
        car = client_car('Me', (0, 10_000), (0.0, 10.0), local=True)  # passed line 1 (z = 10) at 1 s
        self.assertEqual(reckoning.position(car, LINES, clock=15_000), (0.0, 15.0))  # 0.5 s later
        self.assertEqual(reckoning.position(car, LINES, clock=17_500), (0.0, 17.5))  # runs on

    def test_the_next_line_starts_it_again(self):
        reckoning = race.DeadReckoning()
        reckoning.position(
            client_car('Me', (0, 10_000), (0.0, 30.0), local=True), LINES, clock=19_000
        )  # drifted on
        car = client_car('Me', (0, 10_000, 20_000), (0.0, 10.0), local=True)
        self.assertEqual(
            reckoning.position(car, LINES, clock=21_000), (0.0, 21.0)
        )  # from line 2, not the drift

    def test_anchors_move_from_off_road_line_middles_onto_the_road(self):
        # A round road (radius 100), its 8 checkpoint lines long and all off to the
        # outside: their middles lie 100 units off the road, as on some real tracks.
        import math

        lines, radius, lap_seconds = 8, 100.0, 30.0
        gates = tuple(
            (
                (radius * math.cos(2 * math.pi * k / lines), radius * math.sin(2 * math.pi * k / lines)),
                (
                    3 * radius * math.cos(2 * math.pi * k / lines),
                    3 * radius * math.sin(2 * math.pi * k / lines),
                ),
            )
            for k in range(lines)
        )
        speed = 2 * math.pi / lap_seconds  # radians a second

        def car_at(seconds):
            turn = speed * seconds
            passed = math.floor(turn / (2 * math.pi / lines)) + 1
            times = tuple(round(k * lap_seconds / lines * 10_000) for k in range(passed))
            laps = tuple(times[i : i + lines] for i in range(0, passed, lines))
            velocity = (-radius * speed * math.sin(turn), radius * speed * math.cos(turn))
            truth = (radius * math.cos(turn), radius * math.sin(turn))
            return race.PlayerState('Guess', GERMANY, len(laps) - 1, laps, velocity=velocity), truth

        reckoning = race.DeadReckoning()
        errors = []
        for step in range(round(3 * lap_seconds * 20)):  # three laps, 20 reads a second
            seconds = step / 20
            player, truth = car_at(seconds)
            position = reckoning.position(player, gates, round(seconds * 10_000))
            errors.append(math.dist(position, truth))
        first_line = errors[: round(lap_seconds / lines * 20)]
        self.assertGreater(min(first_line), 90)  # from the line's middle: far off the road
        third_lap = errors[round(2 * lap_seconds * 20) :]
        self.assertLess(max(third_lap), 3)  # on the road
        for index in range(lines):
            # Where a new car starts: near the road (it began 100 off), still settling.
            self.assertAlmostEqual(math.hypot(*reckoning.anchor(gates, index)), radius, delta=5)

    def test_filled_in_only_where_the_game_has_none_and_not_for_the_radar(self):
        reckoning = race.DeadReckoning()
        known = race.PlayerState(
            'Known', GERMANY, 0, ((0, 10_000),), position=(1.0, 12.0), velocity=(0.0, 10.0)
        )
        filled = reckoning.fill([known, client_car('Guess', (0, 10_000), (0.0, 10.0))], LINES, clock=12_000)
        self.assertEqual(filled[0].position, (1.0, 12.0))
        self.assertFalse(filled[0].estimated)
        self.assertEqual(filled[1].position, (0.0, 12.0))
        self.assertTrue(filled[1].estimated)
        me = race.PlayerState(
            'Me',
            GERMANY,
            0,
            ((0,),),
            local=True,
            position=(0.0, 0.0),
            velocity=(0.0, 40.0),
            estimated=True,
            forward=(0.0, 1.0),
        )
        self.assertIsNone(race.Radar().update([me, filled[1]], 0.0))

    def test_the_live_delta_runs_between_checkpoints_with_it(self):
        best = (0, 10_000, 20_000, 30_000)
        reckoning = race.DeadReckoning()
        me = client_car('Me', (40_000, 49_000), (0.0, 10.0), local=True)  # 1 s faster to line 1
        position = reckoning.position(me, LINES, clock=54_000)  # z = 15, halfway to line 2
        state = race.LapState(
            clock=54_000,
            time_limit=0,
            laps_completed=1,
            laps_to_finish=3,
            lap_starts=[0, 40_000],
            checkpoints=(best, (40_000, 49_000)),
            position=position,
            gates=LINES,
        )
        # The best lap was at z = 15 after 1.5 s; this lap after 1.4 s: 0.1 s ahead.
        self.assertEqual(state.delta_to_best, -1_000)


class SameStretchGapTests(unittest.TestCase):
    def test_both_between_the_same_checkpoints(self):
        # Both passed line 1 last; the leader at 1.0 s and now at z = 18, I at 1.4 s and
        # at z = 12. Clock 2.0 s: the leader went 8 of 10 in 1 s, so it was at z = 12
        # (a quarter of its way) at 1.25 s: 0.75 s ahead.
        leader = driving('Leader', (0, 10_000), z=18.0)
        me = driving('Me', (4_000, 14_000), z=12.0, local=True)
        self.assertEqual(race.gap(leader, me, clock=20_000, gates=LINES), ('time', -7_500))

    def test_no_live_gap_when_it_is_not_further_on(self):
        leader = driving('Leader', (0, 10_000), z=11.0)
        me = driving('Me', (4_000, 14_000), z=12.0, local=True)
        self.assertIsNone(race.live_gap(leader, me, 20_000, LINES))


class DraftTests(unittest.TestCase):
    def car(self, draft, loss):
        return race.CarState(False, 0, 0, False, 0, 40.0, draft=draft, draft_downforce_loss=loss)

    def test_meter_and_downforce_warning(self):
        sections = race.car_sections(self.car(0.727, 0.582))
        row = sections['draft'][0]
        self.assertEqual(
            (row.text, row.color, row.tail, row.tail_color),
            ('Draft 73%', 'draft', '  -58% downforce', 'lift'),
        )
        self.assertEqual(sections['levels']['draft'], (0.727, 'draft'))

    def test_out_of_the_draft(self):
        row = race.car_sections(self.car(0.0, 0.0))['draft'][0]
        self.assertEqual((row.text, row.color, row.tail), ('Draft 0%', 'text', ''))

    def test_no_section_without_drafting(self):
        self.assertNotIn('draft', race.car_sections(self.car(None, 0.0)))


SERVER_DRAFT = race.DraftSettings(0.10, 0.80, 30, 20)  # the online server's: 10 %, 80 %, reach 30, 20°


def heading_north(name, position, local=False, drag=None):
    return race.PlayerState(
        name,
        GERMANY,
        1,
        ((0, 10_000),),
        local=local,
        position=position,
        velocity=(0.0, 40.0),
        forward=(0.0, 1.0),
        draft_drag=drag,
    )


class DraftExtrasTests(unittest.TestCase):
    def test_a_car_close_behind_in_line_and_drafting_drafts_you(self):
        me = heading_north('Me', (0.0, 100.0), local=True)
        chaser = heading_north('Chaser', (1.0, 85.0), drag=0.95)  # 15 behind, half the effect
        self.assertEqual(race.drafted_by([me, chaser], SERVER_DRAFT), ('Chaser', 0.5000000000000004))

    def test_not_when_off_line_too_far_or_not_drafting(self):
        me = heading_north('Me', (0.0, 100.0), local=True)
        self.assertIsNone(race.drafted_by([me, heading_north('Side', (12.0, 88.0), drag=0.95)], SERVER_DRAFT))
        self.assertIsNone(race.drafted_by([me, heading_north('Far', (0.0, 50.0), drag=0.95)], SERVER_DRAFT))
        self.assertIsNone(race.drafted_by([me, heading_north('Free', (0.0, 90.0), drag=1.0)], SERVER_DRAFT))

    def test_rows_card_at_the_start_then_the_last_lap(self):
        car = race.CarState(False, 0, 0, False, 0, 40.0, draft=0.3, draft_last_lap=0.234)
        start = race.LapState(
            clock=50_000,
            time_limit=0,
            laps_completed=0,
            laps_to_finish=3,
            lap_starts=[0],
            car=car,
            draft=SERVER_DRAFT,
        )
        self.assertEqual(
            [r.text for r in race.draft_rows(start)], ['Max -10% drag  -80% downforce  reach 30  20°']
        )
        later = dataclasses.replace(start, clock=900_000)
        self.assertEqual([r.text for r in race.draft_rows(later)], ['Last lap 23% in a slipstream'])

    def test_the_radar_draws_the_slipstream_of_cars_ahead(self):
        # A car 12 ahead in line: its tail is 9.75 ahead, well within the reach of 30.
        blips = race.radar_blips(((0.0, 0.0), (0.0, 1.0)), 40.0, [((0.0, 12.0), (0.0, 1.0))], SERVER_DRAFT)
        self.assertTrue(blips[0].in_cone)
        aside = race.radar_blips(((0.0, 0.0), (0.0, 1.0)), 40.0, [((8.0, 12.0), (0.0, 1.0))], SERVER_DRAFT)
        self.assertFalse(aside[0].in_cone)  # 39° off its line
        behind = race.radar_blips(((0.0, 0.0), (0.0, 1.0)), 40.0, [((0.0, -12.0), (0.0, 1.0))], SERVER_DRAFT)
        self.assertIsNone(behind[0].in_cone)  # cars behind get no cone


class DraftTimeTests(unittest.TestCase):
    def test_time_in_a_slipstream_per_lap(self):
        reader = race.LapReader.__new__(race.LapReader)
        reader._draft_time, reader._draft_clock = {}, None
        car = lambda draft: race.CarState(False, 0, 0, False, 0, 40.0, draft=draft)
        state = lambda clock, draft, starts: race.LapState(
            clock=clock,
            time_limit=0,
            laps_completed=len(starts) - 1,
            laps_to_finish=3,
            lap_starts=starts,
            checkpoints=tuple((s,) for s in starts),
            car=car(draft),
        )
        self.assertIsNone(reader._count_draft(state(10_000, 0.5, [0])))
        for clock in range(15_000, 100_001, 5_000):  # in a slipstream from 1 to 10 s: 9 s of a 100 s lap
            reader._count_draft(state(clock, 0.5, [0]))
        self.assertAlmostEqual(reader._count_draft(state(1_000_000, 0.0, [0, 1_000_000])), 0.09)


class DraftedColourTests(unittest.TestCase):
    def test_blend(self):
        from turbohud.core.hud import blend

        middle = blend('#5ec8ff', '#ff3b3b', 0.5)
        self.assertGreater(max(int(middle[i : i + 2], 16) for i in (1, 3, 5)), 220)  # bright, not grey
        self.assertEqual(blend('#5ec8ff', '#ff3b3b', 0.0), '#5ec8ff')
        self.assertEqual(blend('#5ec8ff', '#ff3b3b', 1.0), '#ff3b3b')
        self.assertEqual(blend('#5ec8ff', '#ff3b3b', 2.0), '#ff3b3b')  # kept within the two

    def test_the_closer_the_redder(self):
        me = heading_north('Me', (0.0, 100.0), local=True)
        car = race.CarState(False, 0, 0, False, 0, 40.0, draft=0.0)

        def colour(drag):
            chaser = heading_north('Chaser', (0.5, 90.0), drag=drag)
            state = race.LapState(
                clock=900_000,
                time_limit=0,
                laps_completed=1,
                laps_to_finish=3,
                lap_starts=[0, 800_000],
                car=car,
                draft=SERVER_DRAFT,
                players=(me, chaser),
            )
            return race.draft_rows(state)[-1].color

        weak, strong = colour(0.99), colour(0.905)  # 10 % and 95 % of the slipstream
        red = lambda c: int(c[1:3], 16) - int(c[5:7], 16)  # red over blue
        self.assertLess(red(weak), 0)  # still bluish
        self.assertGreater(red(strong), 150)  # nearly red


class LapTimesTests(unittest.TestCase):
    def test_finished_laps_and_the_running_one(self):
        # Laps start at 0, 40_000 and 78_000: two laps done (4.0 s and 3.8 s), a third running.
        p = player('P', [lap(0), lap(40_000), lap(78_000, count=2)], laps=2)
        self.assertEqual(race.player_lap_times(p), [40_000, 38_000])
        self.assertEqual(race.player_current_lap(p, 90_000), 12_000)

    def test_missed_start_lines_and_finished_players(self):
        p = player('P', [lap(0), (race.NO_CHECKPOINT, 50_000), lap(80_000, count=1)], laps=2)
        self.assertEqual(race.player_lap_times(p), [])
        done = player('Done', [lap(0), lap(40_000)], laps=1, finished=True)
        self.assertIsNone(race.player_current_lap(done, 60_000))
        self.assertIsNone(race.player_current_lap(player('Grid', []), 1_000))

    def test_rows_show_best_and_running_lap_in_race_order(self):
        me = player('Me', [lap(0), lap(42_000), lap(80_000, count=2)], laps=2, local=True)
        ahead = player('Ahead', [lap(0), lap(39_000), lap(78_000, count=3)], laps=2)
        # A 3-lap race: Done is in (laps of 3.0, 3.0 and 2.9 s); the others are on their last lap.
        done = player('Done', [lap(0), lap(30_000), lap(60_000), lap(89_000, count=1)], laps=3, finished=True)
        fresh = player('Fresh', [lap(0, count=2)], laps=0)
        rows = race.lap_times_rows([me, fresh, ahead, done], clock=90_000)
        self.assertEqual((rows[0].text, rows[0].middle, rows[0].right), ('Driver', 'Best', 'Lap'))
        self.assertEqual([r.text for r in rows[1:]], ['1. Done', '2. Ahead', '3. Me', '4. Fresh'])
        self.assertEqual([r.middle for r in rows[1:]], ['0:02.900', '0:03.900', '0:03.800', '-'])
        self.assertEqual([r.right for r in rows[1:]], ['Fin', '0:01.2', '0:01.0', '0:09.0'])
        # The race's fastest lap is green; my name in the accent colour.
        self.assertEqual([r.middle_color for r in rows[1:]], ['ahead', 'text', 'text', 'text'])
        self.assertEqual(rows[3].color, 'accent')

    def test_at_most_sixteen_drivers(self):
        players = [
            player(f'P{i}', [lap(0), lap(40_000 + i * 100, count=3)], local=(i == 18)) for i in range(20)
        ]
        rows = race.lap_times_rows(players, clock=50_000)
        self.assertEqual(len(rows), 1 + race.MAX_LAP_TIME_ROWS)
        self.assertEqual(rows[1].text, '1. P0')
        self.assertIn('19. P18', [r.text for r in rows])
