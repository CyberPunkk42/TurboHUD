"""The watched driver's banner (turbohud.core.watched), the Race Director mode's second part (asked for
by the user on 2026-11-16)."""

import json
import unittest
from pathlib import Path

from turbohud.core import watched
from turbohud.core.watched import WatchedDriver


def run(driver, name_at, until, start=0.0, step=0.5):
    """Feed one read every `step` seconds from `start` to `until`; `name_at(clock)` gives the driver
    followed. [(clock, Watched or None)]."""
    seen = []
    clock = start
    while clock <= until + 1e-9:
        seen.append((clock, driver.update(name_at(clock), clock)))
        clock += step
    return seen


def shown(seen):
    """{clock: name} where the banner shows."""
    return {clock: banner.name for clock, banner in seen if banner is not None}


class WatchedDriverTest(unittest.TestCase):
    def test_the_first_driver_is_named_after_the_hold(self):
        seen = run(WatchedDriver(), lambda clock: 'Alpha', 3.0)
        self.assertNotIn(0.5, shown(seen))
        self.assertEqual(shown(seen)[1.0], 'Alpha')
        self.assertEqual(dict(seen)[1.0].opacity, 0.0)  # fading in from there

    def test_it_fades_in_and_out_over_six_seconds(self):
        seen = dict(run(WatchedDriver(), lambda clock: 'Alpha', 9.0))
        self.assertEqual(seen[1.5].opacity, 0.5)
        self.assertEqual(seen[4.0].opacity, 1.0)
        self.assertEqual(seen[6.5].opacity, 0.5)
        self.assertIsNone(seen[7.5])

    def test_the_same_driver_not_again_while_followed(self):
        seen = run(WatchedDriver(), lambda clock: 'Alpha', 60.0)
        self.assertEqual(max(shown(seen)), 7.0)

    def test_a_turn_to_another_driver_names_it(self):
        seen = run(WatchedDriver(), lambda clock: 'Alpha' if clock < 20 else 'Bravo', 30.0)
        self.assertEqual(shown(seen)[21.0], 'Bravo')
        self.assertNotIn(20.5, shown(seen))

    def test_flicking_through_names_only_the_one_stopped_at(self):
        names = ['Bravo', 'Charlie', 'Delta']

        def name_at(clock):
            if clock < 20:
                return 'Alpha'
            if clock < 21.5:
                return names[int((clock - 20) * 2) % 3]  # a new one each read
            return 'Echo'

        seen = run(WatchedDriver(), name_at, 30.0)
        self.assertEqual({name for name in shown(seen).values()}, {'Alpha', 'Echo'})

    def test_a_driver_turned_to_while_one_shows_takes_its_place_at_once(self):
        seen = dict(run(WatchedDriver(), lambda clock: 'Alpha' if clock < 3 else 'Bravo', 12.0))
        self.assertEqual(seen[3.5].name, 'Alpha')
        self.assertEqual((seen[4.0].name, seen[4.0].opacity), ('Bravo', 1.0))  # no fade in again
        self.assertIsNone(seen[10.0])

    def test_back_to_the_first_driver_names_it_again(self):
        def name_at(clock):
            return 'Bravo' if 20 <= clock < 30 else 'Alpha'

        seen = run(WatchedDriver(), name_at, 40.0)
        self.assertEqual(shown(seen)[31.0], 'Alpha')

    def test_no_driver_known_shows_nothing_and_keeps_the_last(self):
        seen = run(WatchedDriver(), lambda clock: None if 20 <= clock < 25 else 'Alpha', 40.0)
        self.assertEqual(max(shown(seen)), 7.0)

    def test_a_clock_going_back_names_the_driver_again(self):
        driver = WatchedDriver()
        run(driver, lambda clock: 'Alpha', 30.0)
        seen = run(driver, lambda clock: 'Alpha', 5.0, start=2.0)
        self.assertEqual(shown(seen)[3.0], 'Alpha')

    def test_a_paused_clock_holds_it(self):
        driver = WatchedDriver()
        run(driver, lambda clock: 'Alpha', 3.0)
        for _ in range(100):
            banner = driver.update('Alpha', 3.0)
        self.assertEqual((banner.name, banner.opacity), ('Alpha', 1.0))

    def test_the_numbers(self):
        self.assertEqual(watched.WATCH_HOLD, 1.0)
        self.assertEqual(watched.WATCHING, 'Watching')


class RaceWatchedTest(unittest.TestCase):
    """The banner through the race sections: only in a replay, with the driver's place."""

    def players(self, followed=1):
        from turbohud.core import race

        ahead = race.PlayerState('Speedy Driver', 0, 1, ((0, 10_000, 20_000),), local=followed == 0)
        behind = race.PlayerState('A' * 30, 0, 1, ((0, 11_000, 21_000),), local=followed == 1)
        return ahead, behind

    def watch(self, followed=1, **state):
        from turbohud.core import race

        driver = WatchedDriver()
        units = race.UNITS_PER_SECOND
        found = {}
        for tenth in range(25, 60, 5):  # 2.5 s to 5.5 s of race clock
            lap = race.LapState(tenth * units // 10, 0, 0, 5, [0], players=self.players(followed), **state)
            snapshot = race.Snapshot(race.RACING, lap, True, 0.0, moved_at=0.0)
            found = race.race_sections(snapshot, 0.0, watched=driver)
        return found

    def test_in_a_replay_it_names_the_followed_driver_and_place(self):
        from turbohud.core.hud import BANNER_TEXT, OVERTAKE_COLOUR

        found = self.watch(replay=True)
        title, name = found['watched']
        self.assertEqual((title.text, title.color), ('Watching', OVERTAKE_COLOUR))
        self.assertEqual((name.text, name.color), (f'P2  {"A" * 17}…', BANNER_TEXT))  # cut as in the lists
        self.assertTrue(title.centred and name.centred)
        self.assertEqual(found['watchedbanner'].name, 'A' * 30)

    def test_the_leader_is_p1(self):
        self.assertEqual(self.watch(0, replay=True)['watched'][1].text, 'P1  Speedy Driver')

    def test_no_place_in_an_arena_event(self):
        self.assertEqual(self.watch(0, replay=True, on_a_track=False)['watched'][1].text, 'Speedy Driver')

    def test_never_while_driving_nor_spectating(self):
        self.assertNotIn('watched', self.watch())
        self.assertNotIn('watched', self.watch(spectating=True))

    def test_none_without_a_follower(self):
        from turbohud.core import race

        state = race.LapState(50_000, 0, 0, 5, [0], players=self.players(), replay=True)
        self.assertEqual(race.watched_banner(state, None, 50_000, None), {})


class WatchedSectionTest(unittest.TestCase):
    """The Watched driver section: under Race in the panel, a banner without a flag, first placed in
    the middle below the radar."""

    def section(self):
        from turbohud.core.hud import RACE_SECTIONS

        return next(s for s in RACE_SECTIONS if s.name == 'watched')

    def test_it_is_under_race_in_the_panel(self):
        from turbohud.core.hud import PANEL_CATEGORIES

        self.assertIn('watched', dict(PANEL_CATEGORIES)['Race'])

    def test_a_banner_without_a_flag(self):
        section = self.section()
        self.assertTrue(section.banner)
        self.assertEqual(section.end, 0.0)
        self.assertEqual(len(section.samples[0]), 2)

    def test_it_starts_in_the_middle_below_the_radar(self):
        from turbohud.core import hud

        screen = (0, 0, 1920, 1080)
        radar = next(s for s in hud.RACE_SECTIONS if s.name == 'radar')
        below = hud.drawing_place(radar, radar.bar, screen)
        x, y, width, _height = hud.drawing_place(self.section(), (480, 60), screen)
        self.assertEqual(x + width // 2, 960)
        self.assertGreaterEqual(y, below[1] + below[3])

    def test_in_every_shipped_layout_centred_and_clear_of_the_rest(self):
        folder = Path(__file__).resolve().parent.parent / 'assets' / 'presets'
        for path in sorted(folder.glob('*.json')):
            with self.subTest(path.name):
                layout = json.loads(path.read_text(encoding='utf-8'))
                places = layout['sections']
                mine = places['watched']
                self.assertLessEqual(abs(mine['x'] + mine['width'] / 2 - layout['screen'][0] / 2), 1)
                for name, other in places.items():
                    if name == 'watched':
                        continue
                    apart = (
                        other['x'] + other['width'] <= mine['x']
                        or mine['x'] + mine['width'] <= other['x']
                        or other['y'] + other['height'] <= mine['y']
                        or mine['y'] + mine['height'] <= other['y']
                    )
                    self.assertTrue(apart, name)


if __name__ == '__main__':
    unittest.main()
