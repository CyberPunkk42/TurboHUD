import dataclasses
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import hud, race
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


class PassedTests(unittest.TestCase):
    def test_every_checkpoint_in_one_row_worked_out_once(self):
        p = player('P', [lap(0), lap(40_000, count=2)])
        self.assertEqual(p.passed, (0, 10_000, 20_000, 30_000, 40_000, 50_000))
        self.assertIs(p.passed, p.passed)  # kept: the frame asks for it many times
        # A new read (a changed copy) works it out afresh.
        later = dataclasses.replace(p, checkpoints=(lap(0), lap(40_000, count=3)))
        self.assertEqual(len(later.passed), 7)


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


SECOND = race.UNITS_PER_SECOND


def in_pits(name='Car', moving=False, in_pit=True):
    velocity = (19.0, 3.0) if moving else (0.0, 0.0)
    return race.PlayerState(name, GERMANY, 1, (lap(0),), False, in_pit, False, velocity=velocity)


class PitStopTests(unittest.TestCase):
    def visit(self, pits, stood, rolling=10):
        """In at 0, rolling for `rolling` s, standing for `stood`, out; the car at the exit."""
        pits.update([in_pits(moving=True)], 0)
        pits.update([in_pits()], rolling * SECOND)
        end = (rolling + stood) * SECOND
        pits.update([in_pits(moving=True)], end)
        return pits.update([in_pits(moving=True, in_pit=False)], end + 5 * SECOND)[0]

    def test_the_first_timer_runs_from_the_entry(self):
        pits = race.PitStops()
        self.assertEqual(pits.update([in_pits(moving=True)], 7 * SECOND)[0].pit_seconds, 0.0)
        car = pits.update([in_pits(moving=True)], 10 * SECOND)[0]
        self.assertEqual((car.pit_seconds, car.pit_stopped), (3.0, 0.0))

    def test_nothing_outside_the_pits(self):
        car = race.PitStops().update([in_pits(moving=True, in_pit=False)], SECOND)[0]
        self.assertIsNone(car.pit_seconds)

    def test_the_second_timer_runs_only_while_standing(self):
        pits = race.PitStops()
        pits.update([in_pits(moving=True)], 0)
        pits.update([in_pits()], 10 * SECOND)
        standing = pits.update([in_pits()], 13 * SECOND)[0]
        self.assertEqual((standing.pit_seconds, standing.pit_stopped), (13.0, 3.0))
        pits.update([in_pits(moving=True)], 22 * SECOND)
        rolling = pits.update([in_pits(moving=True)], 25 * SECOND)[0]
        self.assertEqual((rolling.pit_seconds, rolling.pit_stopped), (25.0, 12.0))

    def test_standing_twice_adds_up(self):
        pits = race.PitStops()
        for at, moving in ((0, False), (2, True), (4, False), (7, True)):
            car = pits.update([in_pits(moving=moving)], at * SECOND)[0]
        self.assertEqual(car.pit_stopped, 5.0)

    def test_both_stay_for_six_seconds_after_the_exit(self):
        pits = race.PitStops()
        self.visit(pits, 12)  # the exit is read at 27
        kept = pits.update([in_pits(moving=True, in_pit=False)], 32 * SECOND)[0]
        self.assertEqual((kept.pit_seconds, kept.pit_stopped), (27.0, 12.0))

    def test_they_go_six_seconds_after_the_exit_was_read(self):
        pits = race.PitStops()
        pits.update([in_pits()], 0)
        pits.update([in_pits(moving=True)], 3 * SECOND)
        out = in_pits(moving=True, in_pit=False)
        self.assertEqual(pits.update([out], 4 * SECOND)[0].pit_seconds, 4.0)
        self.assertEqual(pits.update([out], 10 * SECOND - 1)[0].pit_seconds, 4.0)
        self.assertIsNone(pits.update([out], 10 * SECOND)[0].pit_seconds)

    def test_standing_over_45_seconds_shows_plain_pit(self):
        pits = race.PitStops()
        pits.update([in_pits()], 0)
        self.assertEqual(pits.update([in_pits()], 45 * SECOND)[0].pit_stopped, 45.0)
        car = pits.update([in_pits()], 46 * SECOND)[0]
        self.assertIsNone(car.pit_seconds)
        self.assertTrue(car.in_pit)
        self.assertEqual(race.players_rows([car])[0].tail, '  PIT')
        self.assertIsNone(pits.update([in_pits(moving=True, in_pit=False)], 47 * SECOND)[0].pit_seconds)

    def test_a_new_visit_starts_afresh(self):
        pits = race.PitStops()
        self.visit(pits, 12)
        pits.update([in_pits(moving=True, in_pit=False)], 30 * SECOND)
        car = pits.update([in_pits(moving=True)], 31 * SECOND)[0]
        self.assertEqual((car.pit_seconds, car.pit_stopped), (0.0, 0.0))

    def test_each_car_has_its_own_timers(self):
        pits = race.PitStops()
        pits.update([in_pits('A'), in_pits('B', moving=True, in_pit=False)], 0)
        pits.update([in_pits('A'), in_pits('B')], 2 * SECOND)
        a, b = pits.update([in_pits('A'), in_pits('B')], 5 * SECOND)
        self.assertEqual((a.pit_seconds, b.pit_seconds), (5.0, 3.0))

    def test_without_a_velocity_the_second_timer_goes_on_as_it_was(self):
        pits = race.PitStops()
        pits.update([in_pits()], 0)
        unknown = dataclasses.replace(in_pits(), velocity=None)
        self.assertEqual(pits.update([unknown], SECOND)[0].pit_stopped, 1.0)

    def test_the_player_list_shows_the_timers_next_to_pit(self):
        car = player('Me', [lap(0)], local=True, in_pit=True)
        self.assertEqual(race.players_rows([car])[0].tail, '  PIT')
        rolling = dataclasses.replace(car, pit_seconds=8.44)
        self.assertEqual(race.players_rows([rolling])[0].tail, '  PIT 8.4s')
        standing = dataclasses.replace(rolling, pit_seconds=24.5, pit_stopped=12.034)
        self.assertEqual(race.players_rows([standing])[0].tail, '  PIT 24.5s (12.03s)')
        out = dataclasses.replace(standing, in_pit=False)
        self.assertEqual(race.players_rows([out])[0].tail, '  PIT 24.5s (12.03s)')

    def test_a_passing_hold_up_gets_no_bracket(self):
        car = dataclasses.replace(
            player('Me', [lap(0)], local=True, in_pit=True), pit_seconds=8.0, pit_stopped=0.1
        )
        self.assertEqual(race.players_rows([car])[0].tail, '  PIT 8.0s')

    def test_the_bracket_takes_its_room_from_a_long_name(self):
        car = dataclasses.replace(player('A' * 30, [lap(0)], local=True), pit_seconds=24.5, pit_stopped=12.0)
        row = race.players_rows([car])[0]
        room = len('1. ') + race.MAX_NAME_SHOWN + len(race.PIT_TAIL_ROOM)
        self.assertEqual(len(row.text + row.tail), room)


class LapTimesPitAndLapTests(unittest.TestCase):
    def row(self, car):
        return race.lap_times_rows([car], clock=50_000)[1]

    def test_each_driver_shows_the_lap_it_is_on(self):
        car = player('Me', [lap(0), lap(40_000), lap(80_000)], laps=2, local=True)
        self.assertEqual((self.row(car).before, self.row(car).tail), ('L3', ''))

    def test_a_finished_driver_shows_the_laps_it_drove(self):
        car = player('Me', [lap(0), lap(40_000), lap(80_000)], laps=2, local=True, finished=True)
        self.assertEqual((self.row(car).before, self.row(car).right), ('L2', 'Fin'))

    def test_the_timers_stand_in_the_columns_while_they_show(self):
        car = dataclasses.replace(
            player('Me', [lap(0)], laps=0, local=True, in_pit=True), pit_seconds=24.5, pit_stopped=12.034
        )
        row = self.row(car)
        self.assertEqual((row.middle, row.middle_color), ('PIT 24.5s', 'lift'))
        self.assertEqual((row.right, row.right_color), ('(12.03s)', 'lift'))

    def test_before_it_stands_the_running_time_stays(self):
        car = dataclasses.replace(player('Me', [lap(0)], laps=0, local=True, in_pit=True), pit_seconds=3.0)
        row = self.row(car)
        self.assertEqual((row.middle, row.right, row.right_color), ('PIT 3.0s', '0:05.0', 'text'))

    def test_plain_pit_after_a_long_stand(self):
        row = self.row(player('Me', [lap(0)], laps=0, local=True, in_pit=True))
        self.assertEqual((row.right, row.right_color), ('PIT', 'lift'))

    def test_otherwise_as_ever(self):
        row = self.row(player('Me', [lap(0)], laps=0, local=True))
        self.assertEqual((row.right, row.right_color), ('0:05.0', 'text'))


SEC = race.UNITS_PER_SECOND


class Lapping:
    """A stand-in for LapState, as much as the delta bar needs."""

    def __init__(self, clock, delta, laps=2):
        self.clock, self.delta_to_best, self.laps_completed = clock, delta, laps


def feed(bar, start, seconds, delta_at, laps=2):
    """Reads at 20 a second from race time `start` for `seconds`, the delta (in seconds) from
    `delta_at(t)`, t from the start; the last view."""
    view = None
    for i in range(round(seconds * 20) + 1):
        t = i / 20
        view = bar.update(Lapping(round((start + t) * SEC), round(delta_at(t) * SEC), laps))
    return view


class DeltaColourTests(unittest.TestCase):
    """Green while gaining and red while losing, keeping its colour while steady, and turning
    only on a clear move the other way (asked for by the user on 2026-11-11: white while steady
    showed more than the colours and hid the text; on 2026-11-08 a hard switch flickered)."""

    def test_a_lap_starts_green_when_ahead_and_red_when_behind(self):
        self.assertEqual(feed(race.DeltaBar(), 10, 0, lambda t: -0.3).trend, -1.0)
        self.assertEqual(feed(race.DeltaBar(), 10, 0, lambda t: 0.3).trend, 1.0)

    def test_steady_it_keeps_its_colour(self):
        for delta, colour in ((-0.5, -1.0), (0.5, 1.0)):
            self.assertEqual(feed(race.DeltaBar(), 10, 4, lambda t, d=delta: d).trend, colour)

    def test_a_slow_drift_the_other_way_does_not_turn_it(self):
        view = feed(race.DeltaBar(), 10, 4, lambda t: -0.5 + 0.03 * t)  # losing 0.03 s a second
        self.assertEqual(view.trend, -1.0)

    def test_a_short_wobble_does_not_turn_it(self):
        bar = race.DeltaBar()
        feed(bar, 10, 2, lambda t: -0.5)
        # 0.04 s lost and won back within 0.2 s: past DELTA_SWITCH only for a moment
        view = feed(bar, 12, 2, lambda t: -0.5 + (0.04 * min(t, 0.2 - t) / 0.1 if t < 0.2 else 0.0))
        self.assertEqual(view.trend, -1.0)

    def test_a_clear_loss_turns_it_red_with_a_fade(self):
        bar = race.DeltaBar()
        feed(bar, 10, 2, lambda t: -0.5)
        trends = [feed(bar, 12 + i / 20, 0, lambda t, i=i: -0.5 + 0.2 * i / 20).trend for i in range(1, 31)]
        self.assertEqual(trends[2], -1.0)  # not at once
        self.assertGreater(trends[-1], 0.9)  # red after 1.5 s
        self.assertTrue(any(-0.9 < t < 0.9 for t in trends))  # through the colours in between
        self.assertEqual(trends, sorted(trends))  # one way, no flicker

    def test_and_a_clear_gain_turns_it_back_green(self):
        bar = race.DeltaBar()
        feed(bar, 10, 2, lambda t: 0.5)
        view = feed(bar, 12, 1.5, lambda t: 0.5 - 0.2 * t)
        self.assertLess(view.trend, -0.9)


class DeltaBarTests(unittest.TestCase):
    def run_bar(self, *samples, laps=2):
        bar = race.DeltaBar()
        view = None
        for seconds, delta in samples:
            view = bar.update(Lapping(round(seconds * SEC), round(delta * SEC), laps))
        return view, bar

    def test_nothing_without_a_delta(self):
        self.assertIsNone(race.DeltaBar().update(Lapping(SEC, None)))

    def test_ahead_it_fills_right_with_a_minus(self):
        # Improving goes to the right, as in sim racing (the user, 2026-11-08).
        view, _bar = self.run_bar((10.0, -0.25))
        self.assertEqual((view.fill, view.text), (0.25, '\u22120.25'))

    def test_behind_it_fills_left_with_a_plus(self):
        view, _bar = self.run_bar((10.0, 0.5))
        self.assertEqual((view.fill, view.text), (-0.5, '+0.50'))

    def test_the_fill_glides_while_the_number_is_exact(self):
        # Asked for by the user on 2026-11-11: a smooth bar rather than one that jumps.
        bar = race.DeltaBar()
        feed(bar, 10, 1, lambda t: 0.0)
        view = bar.update(Lapping(round(11.05 * SEC), round(-0.5 * SEC)))  # half a second ahead at once
        self.assertEqual(view.text, '\u22120.50')  # the number at once
        self.assertGreater(view.fill, 0.0)
        self.assertLess(view.fill, 0.5)  # the bar on its way
        view = feed(bar, 11.1, 0.2, lambda t: -0.5)
        self.assertGreater(view.fill, 0.45)  # nearly there 0.25 s on

    def test_a_steady_change_is_followed_closely(self):
        bar = race.DeltaBar()
        view = feed(bar, 10, 3, lambda t: -0.1 * t)  # gaining 0.1 s a second, read 20 times a second
        self.assertAlmostEqual(view.fill, 0.3, delta=0.01)  # under 0.1 s behind: 0.008 s of delta

    def test_a_new_lap_puts_the_fill_where_the_delta_is(self):
        bar = race.DeltaBar()
        feed(bar, 10, 1, lambda t: 0.5)
        view = bar.update(Lapping(11 * SEC, round(-0.2 * SEC), laps=3))
        self.assertEqual(view.fill, 0.2)

    def test_the_fill_stops_at_the_end(self):
        self.assertEqual(self.run_bar((10.0, 5.0))[0].fill, -1.0)
        self.assertEqual(self.run_bar((10.0, -5.0))[0].fill, 1.0)

    def test_gaining_on_a_positive_delta_goes_green(self):
        view, _bar = self.run_bar((10.0, 0.6), (10.5, 0.5), (11.0, 0.4))
        self.assertLess(view.trend, 0.0)
        self.assertEqual(view.text, '+0.40')

    def test_losing_on_a_negative_delta_goes_red(self):
        view, _bar = self.run_bar((10.0, -0.6), (10.5, -0.5), (11.0, -0.4))
        self.assertGreater(view.trend, 0.0)
        self.assertEqual(view.text, '\u22120.40')

    def test_the_colour_follows_the_trend_within_a_second_or_so(self):
        bar = race.DeltaBar()
        trend = 0.0
        for i in range(21):  # a second gaining 0.2 s
            trend = bar.update(Lapping(round((10 + i / 20) * SEC), round((0.5 - i / 100) * SEC))).trend
        self.assertLess(trend, 0.0)  # gaining
        for i in range(1, 31):  # then losing as fast, for 1.5 s
            trend = bar.update(Lapping(round((11 + i / 20) * SEC), round((0.3 + i / 100) * SEC))).trend
        self.assertGreater(trend, 0.0)  # losing

    def test_a_new_lap_starts_afresh(self):
        bar = race.DeltaBar()
        bar.update(Lapping(10 * SEC, 1 * SEC, laps=2))
        view = bar.update(Lapping(11 * SEC, -1 * SEC, laps=3))
        self.assertEqual(view.trend, -1.0)  # green for ahead: the 2 s jump is not the driver gaining
        self.assertEqual(len(bar._history), 1)

    def test_the_history_stays_small(self):
        bar = race.DeltaBar()
        for i in range(10_000):
            bar.update(Lapping(i * 500, 0))
        self.assertLessEqual(len(bar._history), 21)  # a second of reads at 20 a second

    def test_it_works_once_a_read(self):
        bar = race.DeltaBar()
        first = bar.update(Lapping(SEC, SEC))
        self.assertIs(bar.update(Lapping(SEC, SEC)), first)


class LeaderLapTests(unittest.TestCase):
    def state(self, laps, leader_laps, to_finish=20, time_limit=0, leader_finished=False):
        players = (
            player('Leader', [lap(0)] * (leader_laps + 1), laps=leader_laps, finished=leader_finished),
            player('Me', [lap(0)] * (laps + 1), laps=laps, local=True),
        )
        return race.LapState(
            clock=0,
            time_limit=time_limit,
            laps_completed=laps,
            laps_to_finish=to_finish,
            lap_starts=[0],
            players=players,
        )

    def test_a_lapped_driver_sees_the_leaders_lap(self):
        self.assertEqual(race._lap_title(self.state(8, 11)), 'Lap 9/20 · Leader 12')

    def test_on_the_leaders_lap_it_is_left_out(self):
        self.assertEqual(race._lap_title(self.state(8, 8)), 'Lap 9/20')

    def test_it_is_left_out_while_leading(self):
        self.assertEqual(race._lap_title(self.state(8, 3)), 'Lap 9/20')

    def test_a_finished_leader_counts_the_laps_it_drove(self):
        title = race._lap_title(self.state(15, 20, leader_finished=True))
        self.assertEqual(title, 'Lap 16/20 · Leader 20')

    def test_the_leaders_lap_stops_at_the_last_lap(self):
        self.assertEqual(race._lap_title(self.state(15, 25)), 'Lap 16/20 · Leader 20')

    def test_it_goes_before_the_time_left(self):
        state = dataclasses.replace(self.state(8, 11), time_limit=600_000)
        self.assertEqual(race._lap_title(state), 'Lap 9/20 · Leader 12  -  1:00 left')

    def test_without_a_lap_limit(self):
        self.assertEqual(race._lap_title(self.state(8, 11, to_finish=0)), 'Lap 9 · Leader 12')

    def test_without_players(self):
        state = dataclasses.replace(self.state(8, 11), players=())
        self.assertEqual(race._lap_title(state), 'Lap 9/20')


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


class RadarClassTests(unittest.TestCase):
    """Asked for by the user on 2026-11-11: in a multi-class race, cars of another class show on
    the radar in their class's colour."""

    def drive(self, me_tag, other_tag, classes_on=True):
        me = lambda t: dataclasses.replace(moving('Me', (0.0, 40.0 * t), (0.0, 40.0), local=True), tag=me_tag)
        other = lambda t: dataclasses.replace(
            moving('Other', (2.0, 40.0 * t - 6.0), (0.0, 40.0)), tag=other_tag
        )
        third = lambda t: dataclasses.replace(
            moving('Third', (40.0, 40.0 * t), (0.0, 40.0)), tag='GT3' if me_tag == 'LMP2' else 'LMP2'
        )
        radar = race.Radar()
        view = None
        for step in range(4):
            t = step * 0.05
            players = [me(t), other(t), third(t)]
            tags = ('LMP2', 'GT3') if classes_on else ()
            view = radar.update(players, t, None, race.car_classes(players, tags))
        return view

    def test_another_class_gets_its_colour_and_mine_none(self):
        colors = race.radar_class_colors({1: 'LMP2', 2: 'GT3', 3: race.OTHER_CLASS})
        self.assertEqual(colors, {'GT3': race.RADAR_CLASS_COLORS[0], 'LMP2': race.RADAR_CLASS_COLORS[1]})
        (blip,) = self.drive('LMP2', 'GT3').blips
        self.assertEqual(blip.class_color, colors['GT3'])
        (blip,) = self.drive('LMP2', 'LMP2').blips
        self.assertIsNone(blip.class_color)  # my own class: as before

    def test_no_colours_with_classes_off_or_in_a_one_class_race(self):
        (blip,) = self.drive('LMP2', 'GT3', classes_on=False).blips
        self.assertIsNone(blip.class_color)
        self.assertEqual(race.radar_class_colors({}), {})


class WarningTimeTests(unittest.TestCase):
    def test_the_blue_flag_can_show_earlier(self):
        self.assertIsNone(race.blue_flag_opacity(3.0))
        self.assertAlmostEqual(race.blue_flag_opacity(3.0, 3.0), race.BLUE_FAINT)
        self.assertIsNone(race.blue_flag_opacity(3.1, 3.0))
        self.assertEqual(race.blue_flag_opacity(0.5, 3.0), 1.0)

    def test_the_radar_can_show_earlier_and_later(self):
        self.assertIsNone(race.radar_opacity(1.0))
        self.assertAlmostEqual(race.radar_opacity(1.0, 1.0), race.RADAR_FAINT)
        self.assertIsNone(race.radar_opacity(0.3, 0.2))
        self.assertEqual(race.radar_opacity(0.05, 0.2), 1.0)

    def test_a_car_at_the_warning_time_counts_but_the_radar_never_zooms_out_too_far(self):
        # Asked for by the user on 2026-11-11: players found the cars too small.
        speed = 80.0
        me = ((0.0, 0.0), (0.0, 1.0))
        for within in (0.2, 0.5, 1.5, 3.0):
            self.assertLessEqual(race.radar_view(speed, within), race.RADAR_VIEW_MAX)
            self.assertGreaterEqual(race.radar_reach(speed, within), speed * within)
            behind = (0.0, -(speed * within + race.CAR_LENGTH) + 1.0)  # just within the warning time
            (blip,) = race.radar_blips(me, speed, [(behind, (0.0, 1.0))], within=within)
            self.assertLessEqual(blip.seconds, within)
        self.assertEqual(race.radar_view(10.0, 0.5), race.RADAR_VIEW)  # slow: as before

    def test_a_radar_tells_its_view_when_a_car_counts(self):
        def me(t):
            return moving('Me', (0.0, 40.0 * t), (0.0, 40.0), local=True)

        def other(t):
            return moving('Far', (2.0, 40.0 * t - 34.0), (0.0, 40.0))  # 0.75 s behind

        for within, shown in ((0.5, False), (1.0, True)):
            radar = race.Radar(within)
            view = None
            for step in range(4):
                t = step * 0.05
                view = radar.update([me(t), other(t)], t)
            with self.subTest(within=within):
                self.assertEqual(view is not None, shown)
                if shown:
                    self.assertEqual(view.within, 1.0)

    def test_cars_are_drawn_larger_and_never_too_small(self):
        width, length = race.radar_car_size(7.9, 316)
        self.assertAlmostEqual(width, race.CAR_WIDTH * 7.9 * race.RADAR_CAR_SCALE)
        self.assertAlmostEqual(length / width, race.CAR_LENGTH / race.CAR_WIDTH)
        self.assertEqual(race.radar_car_size(0.5, 316)[0], 316 * race.RADAR_CAR_LEAST)


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


class TwentyDriversTests(unittest.TestCase):
    def drivers(self, count):
        return [
            player(f'P{i}', [lap(0), lap(40_000 + i * 100, count=3)], local=(i == count - 1))
            for i in range(count)
        ]

    def test_twenty_drivers_are_all_in_the_lap_times(self):
        self.assertEqual(len(race.lap_times_rows(self.drivers(20))), 1 + 20)

    def test_more_show_the_leader_and_those_around_me(self):
        shown = race.shown_players(self.drivers(25), race.MAX_LAP_TIME_ROWS)
        self.assertEqual(len(shown), 20)
        self.assertEqual(shown[0][0], 1)
        self.assertEqual(shown[-1][0], 25)

    def test_the_section_has_room_for_as_many_as_it_shows(self):
        section = next(s for s in hud.RACE_SECTIONS if s.name == 'laptimes')
        self.assertEqual(len(section.samples[0]), 1 + race.MAX_LAP_TIME_ROWS)


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

    def test_the_slipstream_on_the_radar_can_be_turned_off(self):
        def view(cone):
            radar = race.Radar()
            radar.cone = cone
            shown = None
            for i in range(6):
                t = i * 0.05
                players = [car('Me', (0.0, 40 * t), local=True), car('Ahead', (0.0, 40 * t + 12))]
                shown = radar.update(players, t, SERVER_DRAFT)
            return shown

        self.assertIsNotNone(view(True).cone)
        off = view(False)
        self.assertIsNone(off.cone)
        self.assertEqual([blip.in_cone for blip in off.blips], [None])

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
        # The race's fastest lap is purple, as in F1; my name in the accent colour.
        self.assertEqual(
            [r.middle_color for r in rows[1:]], [race.SESSION_BEST_COLOR, 'text', 'text', 'text']
        )
        self.assertEqual(rows[3].color, 'accent')

    def test_at_most_the_most_drivers_it_shows(self):
        players = [
            player(f'P{i}', [lap(0), lap(40_000 + i * 100, count=3)], local=(i == 18)) for i in range(25)
        ]
        rows = race.lap_times_rows(players, clock=50_000)
        self.assertEqual(len(rows), 1 + race.MAX_LAP_TIME_ROWS)
        self.assertEqual(rows[1].text, '1. P0')
        self.assertIn('19. P18', [r.text for r in rows])


class ClanTagColumnTests(unittest.TestCase):
    """Asked for by the user on 2026-11-11: clan tags in a column of their own, outside a
    multi-class race."""

    def driver(self, name, tag, start):
        return dataclasses.replace(player(name, [lap(start), lap(start + 40_000, count=1)], laps=1), tag=tag)

    def test_tags_show_cut_to_five_and_not_without_the_option(self):
        drivers = [self.driver('A', 'FTR', 0), self.driver('B', '', 100), self.driver('C', 'TOOLONGTAG', 200)]
        rows = race.lap_times_rows(drivers, clock=50_000, clan_tags=True)
        self.assertEqual([r.tag for r in rows[1:]], ['FTR', '', 'TOOLO'])
        rows = race.lap_times_rows(drivers, clock=50_000)
        self.assertEqual([r.tag for r in rows[1:]], ['', '', ''])

    def test_not_in_a_multi_class_race_where_the_tags_name_the_classes(self):
        drivers = [self.driver('A', 'GT3', 0), self.driver('B', 'LMP', 100)]
        rows = race.lap_times_rows(drivers, clock=50_000, class_tags=('GT3', 'LMP'), clan_tags=True)
        self.assertEqual({r.tag for r in rows}, {''})
        rows = race.lap_times_rows(drivers, clock=50_000, class_tags=(), clan_tags=True)  # classes off
        self.assertEqual([r.tag for r in rows[1:]], ['GT3', 'LMP'])


class ClassTests(unittest.TestCase):
    """A multi-class race (asked for by the user on 2026-11-11): classes from the clan tags."""

    TAGS = ('LMP', 'GT3', 'GT4')

    def driver(self, name, tag, best, start=0, local=False):
        """Two laps done: the first `best` long, the second a second slower."""
        laps = [lap(start), lap(start + best, step=best // 4), lap(start + 2 * best + 1000, count=1)]
        return dataclasses.replace(player(name, laps, laps=2, local=local), tag=tag)

    def test_two_classes_are_needed_and_other_tags_are_no_class(self):
        one = [self.driver('A', 'LMP', 60_000), self.driver('B', 'FTR', 61_000)]
        self.assertEqual(race.car_classes(one, self.TAGS), {})
        two = [*one, self.driver('C', '[gt3]', 70_000)]
        classes = race.car_classes(two, self.TAGS)
        self.assertEqual(sorted(classes.values()), ['GT3', 'LMP', race.OTHER_CLASS])
        self.assertEqual(race.car_classes(two, ()), {})  # turned off

    def test_a_driver_without_a_tag_takes_the_class_of_its_car(self):
        def driver(name, tag, car):
            return dataclasses.replace(self.driver(name, tag, 60_000), car=car)

        drivers = [
            driver('Gt tagged', 'GT3', 'Porsche GT3'),
            driver('Gt untagged', '', 'Porsche GT3'),
            driver('Team tag', 'FTR', 'Porsche GT3'),  # a tag that is no class: the car's
            driver('Proto', 'LMP', 'Ligier JS320'),
            driver('Proto untagged', '', 'Ligier JS320'),
            driver('Says GT3', 'GT3', 'Ligier JS320'),  # the tag goes first
            driver('Unknown car', '', 'Tatuus'),  # no tagged driver in it
            driver('No car read', '', ''),
        ]
        classes = race.car_classes(drivers, self.TAGS)
        self.assertEqual(
            [classes[id(d)] for d in drivers],
            ['GT3', 'GT3', 'GT3', 'LMP', 'LMP', 'GT3', race.OTHER_CLASS, race.OTHER_CLASS],
        )
        # Most of the tagged drivers in a car name its class; a tie: the one seen first.
        mixed = [
            driver('A', 'LMP', 'X'),
            driver('B', 'GT3', 'X'),
            driver('C', 'GT3', 'X'),
            driver('D', '', 'X'),
        ]
        self.assertEqual(race.car_classes(mixed, self.TAGS)[id(mixed[3])], 'GT3')
        tie = [driver('A', 'LMP', 'X'), driver('B', 'GT3', 'X'), driver('D', '', 'X')]
        self.assertEqual(race.car_classes(tie, self.TAGS)[id(tie[2])], 'LMP')
        one_class = [
            driver('A', 'GT3', 'X'),
            driver('B', '', 'X'),
            driver('C', '', 'Y'),
            driver('D', 'FTR', 'Y'),
        ]
        self.assertEqual(race.car_classes(one_class, self.TAGS), {})  # one class, many cars: as before
        rows = race.lap_times_rows(one_class, clock=2_000_000, class_tags=self.TAGS)
        self.assertEqual([row.rule for row in rows], [''] * len(rows))
        untagged = [driver('A', '', 'X'), driver('B', '', 'Y')]
        self.assertEqual(race.car_classes(untagged, self.TAGS), {})  # no tags: no classes

    def test_by_class_with_places_in_each_its_fastest_lap_purple(self):
        drivers = [
            self.driver('Proto', 'LMP', 600_000),
            self.driver('Gt fast', 'GT3', 700_000, start=10),
            self.driver('Me', 'FTR', 650_000, start=20, local=True),
            self.driver('Proto 2', 'LMP', 610_000, start=30),
            self.driver('Gt slow', 'GT3', 720_000, start=40),
        ]
        rows = race.lap_times_rows(drivers, clock=2_000_000, class_tags=self.TAGS)
        self.assertEqual(
            [(row.text, row.rule) for row in rows[1:]],
            [
                ('1. Proto', 'LMP'),
                ('2. Proto 2', ''),
                ('1. Gt fast', 'GT3'),
                ('2. Gt slow', ''),
                ('1. Me', race.OTHER_CLASS),  # no class tag: last
            ],
        )
        purple = [row.text for row in rows[1:] if row.middle_color == race.SESSION_BEST_COLOR]
        self.assertEqual(purple, ['1. Proto', '1. Gt fast', '1. Me'])
        plain = race.lap_times_rows(drivers, clock=2_000_000)
        self.assertEqual([row.rule for row in plain], [''] * len(plain))  # no classes: as before
        self.assertEqual([row.text for row in plain[1:4]], ['1. Proto', '2. Proto 2', '3. Me'])  # overall

    def test_the_rule_is_kept_on_the_laid_out_line(self):
        from turbohud.core.hud import hud_lines

        rows = race.lap_times_rows(
            [self.driver('Proto', 'LMP', 600_000), self.driver('Gt', 'GT3', 700_000, start=10)],
            clock=2_000_000,
            class_tags=self.TAGS,
        )
        self.assertEqual([line.rule for line in hud_lines(rows)], ['', 'LMP', 'GT3'])


class ShortcutTests(unittest.TestCase):
    """TSU's shortcut slowdown (asked for by the user on 2026-11-11): the player's own as an
    orange box counting down, every driver's as CUT in the lap times."""

    def state(self, seconds, *players, length=3.0):
        return race.LapState(
            clock=round(seconds * race.UNITS_PER_SECOND),
            time_limit=0,
            laps_completed=1,
            laps_to_finish=5,
            lap_starts=[0, 0],
            players=tuple(players),
            shortcut_seconds=length,
        )

    def driver(self, name, shortcut, local=False):
        laps = [lap(0), lap(40_000, count=2)]
        return dataclasses.replace(player(name, laps, laps=1, local=local), shortcut=shortcut)

    def test_counts_down_from_when_it_began(self):
        penalties = race.ShortcutPenalties()
        me, other = self.driver('Me', True, local=True), self.driver('Other', False)
        self.assertEqual(penalties.left(self.state(10.0, me, other)), {'Me': 3.0})
        self.assertEqual(penalties.left(self.state(11.5, me, other)), {'Me': 1.5})
        self.assertEqual(penalties.left(self.state(14.0, me, other)), {'Me': 0.0})  # not below 0
        free = self.driver('Me', False, local=True)
        self.assertEqual(penalties.left(self.state(15.0, free, other)), {})
        self.assertEqual(penalties.left(self.state(20.0, me, other)), {'Me': 3.0})  # a new one
        unknown = race.ShortcutPenalties().left(self.state(10.0, me, length=0.0))
        self.assertEqual(unknown, {'Me': None})

    def test_the_players_own_box_and_cut_in_the_lap_times(self):
        me, other = self.driver('Me', False, local=True), self.driver('Other', True)
        state = self.state(10.0, me, other)
        self.assertEqual(race.shortcut_rows(state, {'Other': 2.0}), [])  # not the player's
        rows = race.shortcut_rows(state, {'Me': 2.44})
        self.assertEqual(rows[0].text, 'SHORTCUT  2.4 s')
        self.assertTrue(rows[0].centred)
        self.assertEqual(race.shortcut_rows(state, {'Me': None})[0].text, 'SHORTCUT')
        table = race.lap_times_rows([me, other], clock=60_000, cuts={'Other': 2.44})
        cut = next(row for row in table if 'Other' in row.text)
        self.assertEqual((cut.right, cut.right_color), ('CUT 2.4s', race.SHORTCUT_COLOR))
        plain = next(row for row in table if 'Me' in row.text)
        self.assertNotIn('CUT', plain.right)


class JumpStartTests(ShortcutTests):
    """TSU's false-start penalty (asked for by the user on 2026-11-11): JUMP START."""

    def jumper(self, name, on, local=False):
        return dataclasses.replace(self.driver(name, False, local=local), jump_start=on)

    def test_shown_while_tsu_flags_it_then_a_second_and_a_half_more(self):
        # The user (2026-11-11): while the throttle is held on the red lights, then 1.5 s.
        penalties = race.ShortcutPenalties()
        me = self.jumper('Me', True, local=True)
        for seconds in (5.0, 7.0, 9.2):  # held for seconds: shown all along
            self.assertEqual(penalties.jump_starts(self.state(seconds, me)), {'Me'})
        later = self.jumper('Me', False, local=True)
        self.assertEqual(penalties.jump_starts(self.state(10.6, later)), {'Me'})
        self.assertEqual(penalties.jump_starts(self.state(10.8, later)), frozenset())

    def test_the_box_says_jump_start_and_the_lap_times_jump(self):
        me, other = self.jumper('Me', True, local=True), self.jumper('Other', True)
        state = self.state(9.2, me, other)
        self.assertEqual(race.shortcut_rows(state, {}, {'Me'})[0].text, 'JUMP START')
        self.assertEqual(race.shortcut_rows(state, {}, {'Other'}), [])
        self.assertEqual(race.shortcut_rows(state, {'Me': 2.0}, {'Me'})[0].text, 'SHORTCUT  2.0 s')  # first
        table = race.lap_times_rows([me, other], clock=60_000, jumped={'Other'})
        row = next(r for r in table if 'Other' in r.text)
        self.assertEqual((row.right, row.right_color), ('JUMP', race.SHORTCUT_COLOR))
