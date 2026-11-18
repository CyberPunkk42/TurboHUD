"""The battle warning (turbohud.core.battle), the first part of the Race Director mode (asked for by
the user on 2026-11-16)."""

import os
import sys
import unittest

from turbohud.core import battle
from turbohud.core.battle import Battles


class Car:
    """What Battles reads of a player: its name, the checkpoints passed, finished, in the pits, the
    laps done (past the opening lap by default)."""

    def __init__(self, name, passed=2, finished=False, in_pit=False, laps_completed=1):
        self.name = name
        self.passed = (0,) * passed
        self.finished = finished
        self.in_pit = in_pit
        self.laps_completed = laps_completed


A, B, C, D, E, F = (Car(name) for name in ('Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot'))


def gaps(**by_pair):
    """gap_of from {'AB': seconds}: the gap of each pair by the cars' first letters; else far apart."""

    def gap_of(ahead, behind):
        return by_pair.get(ahead.name[0] + behind.name[0], 5.0)

    return gap_of


def run(battles, order, gap_at, until, start=0.0, step=0.5, out=frozenset()):
    """Feed one read every `step` seconds from `start` to `until`; `gap_at(clock)` gives the gap_of.
    The battles seen, by time."""
    seen = []
    clock = start
    while clock <= until + 1e-9:
        seen.append((clock, battles.update(order, clock, gap_at(clock), out)))
        clock += step
    return seen


def closing(pair, start_gap, per_second, floor=0.0):
    """A gap_at for one pair whose gap shrinks by `per_second` from `start_gap`."""
    return lambda clock: gaps(**{pair: max(start_gap - per_second * clock, floor)})


def starts(seen):
    """When a banner began: at no opacity, where nothing showed the read before, or another pair's
    banner had just faded out."""

    def began(before, now):
        if now is None or now.opacity != 0.0:
            return False
        return (
            before is None
            or before.opacity == 0.0
            and (before.ahead, before.behind) != (now.ahead, now.behind)
        )

    return [clock for (_, before), (clock, now) in zip([(None, None), *seen], seen) if began(before, now)]


def first_shown(seen):
    return next(((clock, b) for clock, b in seen if b is not None), (None, None))


class BattlesTest(unittest.TestCase):
    def test_a_car_closing_in_within_a_second_shows_after_the_hold(self):
        battles = Battles()
        # B closes on A from 0.95 s at 0.1 s a second: closing from 1.5 s on (half the span compared),
        # so a battle then, and shown 2 s later.
        clock, shown = first_shown(run(battles, [A, B], closing('AB', 0.95, 0.1), 10.0))
        self.assertEqual(clock, 3.5)
        self.assertEqual((shown.place, shown.ahead, shown.behind), (1, 'Alpha', 'Bravo'))
        self.assertEqual(shown.title, 'Battle for P1')
        self.assertFalse(shown.winner)

    def test_a_steady_gap_under_a_second_is_no_battle(self):
        seen = run(Battles(), [A, B], lambda clock: gaps(AB=0.8), 20.0)
        self.assertIsNone(first_shown(seen)[0])

    def test_a_car_falling_back_is_no_battle(self):
        seen = run(Battles(), [A, B], lambda clock: gaps(AB=0.5 + 0.05 * clock), 10.0)
        self.assertIsNone(first_shown(seen)[0])

    def test_right_behind_is_a_battle_without_closing(self):
        clock, shown = first_shown(run(Battles(), [A, B, C], lambda clock: gaps(BC=0.3), 10.0))
        self.assertEqual(clock, 2.0)  # the hold only
        self.assertEqual((shown.place, shown.ahead, shown.behind), (2, 'Bravo', 'Charlie'))

    def test_a_moment_close_shows_nothing(self):
        # Right behind for 1.5 s only, then far again: shorter than the hold.
        seen = run(Battles(), [A, B], lambda clock: gaps(AB=0.3 if 3.0 <= clock < 4.5 else 2.0), 20.0)
        self.assertIsNone(first_shown(seen)[0])

    def test_the_highest_place_shows(self):
        _clock, shown = first_shown(run(Battles(), [A, B, C, D], lambda clock: gaps(AB=0.3, CD=0.2), 10.0))
        self.assertEqual(shown.place, 1)

    def test_it_fades_in_and_out_over_six_seconds(self):
        seen = dict(run(Battles(), [A, B], lambda clock: gaps(AB=0.3), 12.0))
        self.assertEqual(seen[2.0].opacity, 0.0)
        self.assertEqual(seen[2.5].opacity, 0.5)
        self.assertEqual(seen[4.0].opacity, 1.0)
        self.assertEqual(seen[7.5].opacity, 0.5)
        self.assertIsNone(seen[8.5])

    def test_the_same_pair_not_again_for_a_minute(self):
        seen = dict(run(Battles(), [A, B], lambda clock: gaps(AB=0.3), 70.0))
        again = starts(list(seen.items()))
        self.assertEqual(again, [2.0, 62.0])

    def test_another_battle_shows_after_the_first(self):
        # A and B fight from the start, C and D from 1 s: theirs shows once the first is over.
        seen = run(Battles(), [A, B, C, D], lambda clock: gaps(AB=0.3, CD=0.3 if clock >= 1.0 else 3.0), 12.0)
        found = [(clock, shown.place) for clock, shown in seen if clock in starts(seen)]
        self.assertEqual(found, [(2.0, 1), (8.5, 3)])

    def test_none_for_cars_in_the_pits_finished_or_out(self):
        for order, out in (
            ([A, Car('Bravo', in_pit=True)], frozenset()),
            ([Car('Alpha', finished=True), B], frozenset()),
            ([A, B], frozenset({'Bravo'})),
            ([A, Car('Bravo', passed=1)], frozenset()),  # before the first checkpoint: the grid
        ):
            seen = run(Battles(), order, lambda clock: gaps(AB=0.3), 10.0, out=out)
            self.assertIsNone(first_shown(seen)[0])

    def test_none_in_the_opening_lap(self):
        # Reported by the user on 2026-11-18: too many while the cars were still close from the start.
        for order in ([Car('Alpha', laps_completed=0), B], [A, Car('Bravo', laps_completed=0)]):
            seen = run(Battles(), order, lambda clock: gaps(AB=0.3), 10.0)
            self.assertIsNone(first_shown(seen)[0])

    def test_three_cars_each_within_a_second_are_a_group(self):
        clock, shown = first_shown(run(Battles(), [A, B, C, D, E], lambda clock: gaps(BC=0.9, CD=0.8), 10.0))
        self.assertEqual(clock, 2.0)
        self.assertEqual(shown.place, 2)
        self.assertEqual(shown.group, ('Bravo', 'Charlie', 'Delta'))
        self.assertEqual((shown.ahead, shown.behind), ('Bravo', 'Charlie'))

    def test_a_group_ends_where_a_gap_is_over_a_second(self):
        seen = run(Battles(), [A, B, C, D], lambda clock: gaps(AB=0.9, BC=1.1, CD=0.9), 10.0)
        self.assertIsNone(first_shown(seen)[0])  # two steady pairs, no group, nobody closing

    def test_a_group_takes_the_place_of_the_pairs_in_it(self):
        # B right behind A would be a pair; with C close behind them it is a group of three, shown once.
        seen = run(Battles(), [A, B, C], lambda clock: gaps(AB=0.3, BC=0.6), 70.0)
        shown = [s for _c, s in seen if s is not None]
        self.assertTrue(all(s.group == ('Alpha', 'Bravo', 'Charlie') for s in shown))
        self.assertEqual(starts(seen), [2.0, 62.0])

    def test_a_pair_from_a_group_shown_waits_its_minute(self):
        # A group of three, then C drops back: A and B, still right together, are not told again at once.
        seen = run(Battles(), [A, B, C], lambda clock: gaps(AB=0.3, BC=0.6 if clock < 10 else 3.0), 40.0)
        self.assertEqual(starts(seen), [2.0])

    def test_a_long_group_has_every_driver(self):
        _clock, shown = first_shown(
            run(
                Battles(), [A, B, C, D, E, F], lambda clock: gaps(AB=0.5, BC=0.5, CD=0.5, DE=0.5, EF=0.5), 5.0
            )
        )
        self.assertEqual(shown.group, ('Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot'))
        self.assertEqual(shown.place, 1)

    def test_an_unknown_gap_is_no_battle(self):
        seen = run(Battles(), [A, B], lambda clock: lambda ahead, behind: None, 10.0)
        self.assertIsNone(first_shown(seen)[0])

    def test_a_clock_going_back_starts_afresh(self):
        battles = Battles()
        run(battles, [A, B], lambda clock: gaps(AB=0.3), 70.0)
        # Rewound to the start: the same pair shows again, without waiting for the minute.
        clock, shown = first_shown(run(battles, [A, B], lambda clock: gaps(AB=0.3), 10.0))
        self.assertEqual(clock, 2.0)
        self.assertIsNotNone(shown)

    def test_a_paused_clock_holds_it(self):
        battles = Battles()
        run(battles, [A, B], lambda clock: gaps(AB=0.3), 4.0)
        held = [battles.update([A, B], 4.0, gaps(AB=0.3)).opacity for _ in range(20)]
        self.assertEqual(set(held), {1.0})

    def test_the_numbers(self):
        self.assertEqual(battle.GROUP_GAP, 1.0)
        self.assertEqual(battle.GROUP_CARS, 3)
        self.assertEqual(battle.BATTLE_GAP, 1.0)
        self.assertEqual(battle.BATTLE_CLOSE, 0.4)
        self.assertEqual(battle.BATTLE_HOLD, 2.0)
        self.assertEqual(battle.BATTLE_AGAIN, 60.0)


class RaceBattleTest(unittest.TestCase):
    """The battle warning through the race sections: only while watching."""

    def players(self, behind_by=2000):
        from turbohud.core import race

        # Two checkpoints each; the gap at the last one both passed is `behind_by` (0.1 ms).
        ahead = race.PlayerState('Speedy Driver', 0, 1, ((0, 10_000, 20_000),))
        behind = race.PlayerState('A' * 30, 0, 1, ((0, 10_000 + behind_by, 20_000 + behind_by),))
        return ahead, behind

    def snapshot(self, clock, **state):
        from turbohud.core import race

        lap = race.LapState(clock, 0, 0, 5, [0], players=self.players(), **state)
        return race.Snapshot(race.RACING, lap, True, 0.0, moved_at=0.0)

    def watch(self, **state):
        from turbohud.core import race

        battles = Battles()
        units = race.UNITS_PER_SECOND
        shown = {}
        for tenth in range(25, 60, 5):  # 2.5 s to 5.5 s of race clock
            shown = race.race_sections(self.snapshot(tenth * units // 10, **state), 0.0, battles=battles)
        return shown

    def test_spectating_it_shows_its_three_rows(self):
        from turbohud.core.hud import OVERTAKE_COLOUR

        shown = self.watch(spectating=True)
        self.assertEqual(shown['battlebanner'].place, 1)
        title, overtake, names = shown['battle']
        self.assertEqual(title.text, 'Battle for P1')
        self.assertEqual((overtake.text, overtake.color), ('Possible Overtake', OVERTAKE_COLOUR))
        self.assertEqual(names.text, f'Speedy Driver  vs  {"A" * 17}…')  # cut as in the lists
        self.assertTrue(all(row.centred for row in shown['battle']))

    def test_a_groups_rows(self):
        from turbohud.core import race
        from turbohud.core.battle import Battle

        class Shown:
            def __init__(self, battle):
                self.battle = battle

            def update(self, *args):
                return self.battle

        state = race.LapState(50_000, 0, 0, 5, [0], players=self.players(), spectating=True)
        names = ('Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot')
        rows = race.battle_banner(state, None, 50_000, Shown(Battle(4, 'Alpha', 'Bravo', 1.0, group=names)))
        self.assertEqual(
            [row.text for row in rows['battle']],
            ['Battle for P4', 'Group around Alpha', 'Bravo  ·  Charlie  ·  Delta  ·  +2'],
        )
        three = race.battle_banner(
            state, None, 50_000, Shown(Battle(1, 'Alpha', 'Bravo', 1.0, group=names[:3]))
        )
        self.assertEqual(three['battle'][2].text, 'Bravo  ·  Charlie')

    def test_in_a_replay_it_shows(self):
        self.assertIn('battle', self.watch(replay=True))

    def test_never_while_driving(self):
        self.assertNotIn('battle', self.watch())

    def test_none_in_hotlapping_nor_in_an_arena(self):
        from turbohud.core import race

        for kwargs in ({'hotlapping': True}, {'on_a_track': False}):
            state = race.LapState(50_000, 0, 0, 5, [0], players=self.players(), spectating=True, **kwargs)
            self.assertEqual(race.battle_banner(state, None, 50_000, Battles()), {})

    def test_none_without_a_follower(self):
        from turbohud.core import race

        state = race.LapState(50_000, 0, 0, 5, [0], players=self.players(), spectating=True)
        self.assertEqual(race.battle_banner(state, None, 50_000, None), {})


class BattleSectionTest(unittest.TestCase):
    """The Battle section: under Race in the panel, a banner, first placed below the race leader's."""

    def sections(self):
        from turbohud.core.hud import RACE_SECTIONS

        return {s.name: s for s in RACE_SECTIONS}

    def test_it_is_under_race_in_the_panel(self):
        from turbohud.core.hud import PANEL_CATEGORIES

        self.assertIn('battle', dict(PANEL_CATEGORIES)['Race'])

    def test_a_banner_without_a_flag(self):
        section = self.sections()['battle']
        self.assertTrue(section.banner)
        self.assertEqual(section.end, 0.0)
        self.assertEqual(len(section.samples[0]), 3)

    def test_it_starts_below_the_race_leader_banner(self):
        from turbohud.core import hud

        screen = (0, 0, 1920, 1080)
        sections = self.sections()
        leader = hud.drawing_place(sections['leader'], (600, 40), screen)
        x, y, width, _height = hud.drawing_place(sections['battle'], (600, 100), screen)
        self.assertEqual(x + width // 2, 960)
        self.assertGreater(y, leader[1] + leader[3])

    def test_in_every_shipped_layout_below_the_leader_and_clear_of_the_rest(self):
        import json
        from pathlib import Path

        folder = Path(__file__).resolve().parent.parent / 'assets' / 'presets'
        for path in sorted(folder.glob('*.json')):
            with self.subTest(path.name):
                places = json.loads(path.read_text(encoding='utf-8'))['sections']
                mine, leader = places['battle'], places['leader']
                self.assertGreaterEqual(mine['y'], leader['y'] + leader['height'])
                for name, other in places.items():
                    if name == 'battle':
                        continue
                    apart = (
                        other['x'] + other['width'] <= mine['x']
                        or mine['x'] + mine['width'] <= other['x']
                        or other['y'] + other['height'] <= mine['y']
                        or mine['y'] + mine['height'] <= other['y']
                    )
                    self.assertTrue(apart, name)


class BattleDrawingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Offscreen, as the drawing tests (test_painter): this file runs first, and the Qt it starts
        # is the one every later test draws with.
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_drawn_as_a_banner_that_fades_as_one(self):
        from turbohud.core import race
        from turbohud.core.battle import Battle
        from turbohud.core.hud import RACE_SECTIONS, text_box
        from turbohud.core.settings import Theme
        from turbohud.hud.painter import text_ink, text_width
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        section = next(s for s in RACE_SECTIONS if s.name == 'battle')
        window = SectionWindow(Native(), Theme(), section)
        self.addCleanup(window.close)
        window.font = 26
        box = text_box(section, (0, 0, 10, 10), 26, text_width, text_ink)
        window.resize(box[2], box[3])
        window.set_locked(True)
        shown = {}
        battles = Battles()
        players = RaceBattleTest().players(1000)
        for clock in range(25_000, 60_000, 5000):
            state = race.LapState(clock, 0, 0, 5, [0], players=players, spectating=True)
            shown = race.battle_banner(state, None, clock, battles) or shown
        for opacity, top in ((1.0, 255), (0.5, 130)):
            window.show_content(shown['battle'], None, None, banner=Battle(1, 'a', 'b', opacity))
            image = window.grab().toImage()
            alphas = [
                image.pixelColor(x, y).alpha() for x in range(image.width()) for y in range(image.height())
            ]
            self.assertLessEqual(max(alphas), top)
            self.assertGreater(max(alphas), top - 20)
            if opacity == 1.0:  # the gold letters of "Possible Overtake", in its middle row
                middle = image.height() // 2
                gold = [
                    (x, y)
                    for x in range(image.width())
                    for y in range(middle - 4, middle + 4)
                    if image.pixelColor(x, y).red() > 200 and image.pixelColor(x, y).blue() < 80
                ]
                self.assertTrue(gold)


if __name__ == '__main__':
    unittest.main()
