import dataclasses
import importlib.util
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import race, trackmap

LINES = 8  # checkpoints a lap on the test track
RADIUS = 100.0


def circle_gates(lines=LINES, radius=RADIUS, half_width=5.0):
    """A round track: `lines` checkpoint lines across it, anticlockwise from (radius, 0)."""
    gates = []
    for step in range(lines):
        turn = 2 * math.pi * step / lines
        nx, nz = math.cos(turn), math.sin(turn)
        gates.append(
            (
                ((radius - half_width) * nx, (radius - half_width) * nz),
                ((radius + half_width) * nx, (radius + half_width) * nz),
            )
        )
    return tuple(gates)


GATES = circle_gates()


def on_track(checkpoints):
    """A point on the test track a little after the line of the last checkpoint passed."""
    turn = 2 * math.pi * ((checkpoints - 1) % LINES + 0.3) / LINES
    return (RADIUS * math.cos(turn), RADIUS * math.sin(turn))


def car(name, checkpoints, local=False, start=0, in_pit=False, finished=False, position=True):
    """A player that passed `checkpoints` lines (one every second from `start`), laps
    after one another as the game keeps them."""
    times = [start + i * 10_000 for i in range(checkpoints)]
    laps = tuple(tuple(times[i : i + LINES]) for i in range(0, checkpoints, LINES))
    return race.PlayerState(
        name,
        0,
        max(len(laps) - 1, 0),
        laps,
        finished,
        in_pit,
        local,
        on_track(checkpoints) if position else None,
    )


def state(players, gates=GATES):
    return race.LapState(0, 0, 0, 0, [], gates=gates, players=tuple(players))


def roles(view):
    return {dot.role: dot for dot in view.dots}


def driver(name, u, local=False, in_pit=False, estimated=False, radius=RADIUS, **more):
    """A car `u` checkpoints round the test track (it passed line 0 at u = 0): on the
    circle of `radius`, anticlockwise from (radius, 0)."""
    count = math.floor(u) + 1
    times = [i * 10_000 for i in range(count)]
    laps = tuple(tuple(times[i : i + LINES]) for i in range(0, count, LINES))
    turn = 2 * math.pi * u / LINES
    position = (radius * math.cos(turn), radius * math.sin(turn))
    return race.PlayerState(
        name, 0, max(len(laps) - 1, 0), laps, False, in_pit, local, position, estimated=estimated, **more
    )


def drive(track_map, until, gates=GATES, step=0.05, since=0.0, **kwargs):
    """Feed `track_map` one car driving from `since` to `until` checkpoints round."""
    view = None
    u = since
    while u <= until:
        me = driver('Trainer', u, local=True, **kwargs)
        view = track_map.update(state([me], gates), [me])
        u += step
    return view


def learnt_map(others=False):
    """A TrackMap that has learnt the test track from a car's lap."""
    track_map = trackmap.TrackMap(others)
    drive(track_map, LINES + 1.5)
    assert track_map.learned is not None
    return track_map


def view_of(players, others=False):
    return learnt_map(others).update(state(players), race.ranked(players))


# Long checkpoint lines all off to the outside of the road, as on some real tracks:
# their middles lie 100 units off the road.
OFF_GATES = tuple(
    (
        (RADIUS * math.cos(2 * math.pi * i / LINES), RADIUS * math.sin(2 * math.pi * i / LINES)),
        (3 * RADIUS * math.cos(2 * math.pi * i / LINES), 3 * RADIUS * math.sin(2 * math.pi * i / LINES)),
    )
    for i in range(LINES)
)


class LearntTrackTests(unittest.TestCase):
    def radii(self, outline):
        return [math.hypot(x, z) for x, z in outline.points]

    def test_a_whole_lap_gives_a_closed_loop_on_the_road_not_the_lines(self):
        track_map = trackmap.TrackMap()
        drive(track_map, LINES - 0.5, OFF_GATES)
        self.assertIsNone(track_map.learned)  # not a whole lap yet
        view = drive(track_map, LINES + 1.5, OFF_GATES, since=LINES - 0.45)
        outline = view.outline
        self.assertIs(outline, track_map.learned)
        self.assertTrue(outline.closed)
        self.assertTrue(all(RADIUS - 1 < r <= RADIUS for r in self.radii(outline)))
        self.assertLess(abs(len(outline.points) - 2 * trackmap.MAP_POINTS), 10)  # one round of smoothing

    def test_before_a_whole_lap_the_stretch_driven_so_far_shows(self):
        track_map = trackmap.TrackMap()
        view = drive(track_map, LINES / 2, OFF_GATES)
        self.assertFalse(view.outline.closed)
        self.assertTrue(all(RADIUS - 1 < r <= RADIUS + 1e-9 for r in self.radii(view.outline)))
        _min_x, min_z, _max_x, _max_z = view.outline.bounds
        self.assertGreaterEqual(min_z, -1e-9)  # only the half driven: z from 0 up

    def test_the_start_line_is_where_line_0_was_crossed_across_the_way_driven(self):
        outline = learnt_map().learned
        (x, z), (fx, fz) = outline.start
        self.assertAlmostEqual(math.hypot(x - RADIUS, z), 0, delta=0.01)  # on line 0
        self.assertAlmostEqual(fx, 0, delta=0.1)  # anticlockwise from (100, 0): up the z axis
        self.assertAlmostEqual(fz, 1, delta=0.1)

    def test_where_the_path_misses_the_start_line_the_count_places_the_mark(self):
        path = [(0.0, float(z)) for z in range(10)]
        short_line = ((5.0, 4.5), (6.0, 4.5))  # off to the side: never crossed
        self.assertEqual(trackmap.start_mark(path, short_line, 5), ((0.0, 4.5), (0.0, 1.0)))
        self.assertEqual(trackmap.start_mark(path, ((-1.0, 4.5), (1.0, 4.5))), ((0.0, 4.5), (0.0, 1.0)))
        self.assertIsNone(trackmap.start_mark(path, short_line))

    def test_pits_and_worked_out_positions_do_not_count(self):
        track_map = trackmap.TrackMap()
        drive(track_map, 4.0)
        drive(track_map, 4.1, since=4.05, in_pit=True)  # the path starts afresh after the pits
        drive(track_map, LINES + 1.5, since=4.15)
        self.assertIsNone(track_map.learned)
        estimated = trackmap.TrackMap()
        self.assertIsNone(drive(estimated, LINES + 1.5, estimated=True))

    def test_a_jump_starts_the_path_afresh(self):
        track_map = trackmap.TrackMap()
        drive(track_map, 4.0)
        drive(track_map, 4.0, since=4.0, radius=RADIUS + trackmap.JUMP + 10)  # put back elsewhere
        drive(track_map, LINES + 1.5, since=4.05)
        self.assertIsNone(track_map.learned)

    def test_a_trip_over_the_grass_is_not_learnt_as_the_track(self):
        # Asked for by the user on 2026-11-11: such a first lap was learnt and kept.
        track_map = trackmap.TrackMap()
        drive(track_map, 4.0)
        drive(track_map, 4.3, since=4.05, wheel_grips=(0.5,) * 4)  # all four wheels on the grass
        drive(track_map, LINES + 1.5, since=4.35)
        self.assertIsNone(track_map.learned)  # the path started afresh there: no whole lap yet
        drive(track_map, 2 * LINES + 5, since=LINES + 1.55)
        self.assertIsNotNone(track_map.learned)  # the next clean lap is

    def test_standing_or_going_backwards_starts_the_path_afresh(self):
        for speed in (0.2, -3.0):
            track_map = trackmap.TrackMap()
            drive(track_map, 4.0, forward_speed=30.0)
            drive(track_map, 4.1, since=4.05, forward_speed=speed)
            drive(track_map, LINES + 1.5, since=4.15, forward_speed=30.0)
            self.assertIsNone(track_map.learned, speed)

    def test_kerbs_a_wheel_off_or_in_the_air_still_count_as_clean(self):
        for grips in ((0.93,) * 4, (1.0, 0.5, 0.5, 0.5), (0.0, 0.5, 0.5, 0.5)):
            track_map = trackmap.TrackMap()
            drive(track_map, LINES + 1.5, wheel_grips=grips, forward_speed=30.0)
            self.assertIsNotNone(track_map.learned, grips)

    def test_a_track_saved_before_clean_laps_shows_until_a_clean_lap_replaces_it(self):
        with tempfile.TemporaryDirectory() as folder:
            drive(trackmap.TrackMap(folder=folder), LINES + 1.5)
            file = Path(folder) / trackmap.TRACKS_FOLDER / f'{trackmap.track_key(GATES)}.json'
            data = json.loads(file.read_text())
            self.assertIs(data.pop('clean'), True)
            data['points'] = [[x * 1.5, z * 1.5] for x, z in data['points']]  # an older, wrong one
            file.write_text(json.dumps(data))
            again = trackmap.TrackMap(folder=folder)
            me = driver('Me', 0.5, local=True)
            older = again.update(state([me]), [me]).outline
            self.assertGreater(max(math.hypot(x, z) for x, z in older.points), RADIUS * 1.4)  # shown
            view = drive(again, LINES + 1.5, since=0.55)
            self.assertLess(max(math.hypot(x, z) for x, z in view.outline.points), RADIUS + 1)  # replaced
            self.assertIs(json.loads(file.read_text())['clean'], True)

    def test_a_learnt_track_is_saved_and_known_at_once_next_time(self):
        with tempfile.TemporaryDirectory() as folder:
            first = trackmap.TrackMap(folder=folder)
            drive(first, LINES + 1.5)
            files = list((Path(folder) / trackmap.TRACKS_FOLDER).iterdir())
            self.assertEqual([f.name for f in files], [f'{trackmap.track_key(GATES)}.json'])
            again = trackmap.TrackMap(folder=folder)
            me = driver('Me', 0.5, local=True)
            view = again.update(state([me]), [me])
            self.assertTrue(view.outline.closed)
            self.assertEqual(len(view.outline.points), len(first.learned.points))
            other_track = trackmap.TrackMap(folder=folder)
            self.assertIsNone(other_track.update(state([me], OFF_GATES), [me]))  # a different track
            files[0].write_text('{broken')
            self.assertIsNone(trackmap.TrackMap(folder=folder).update(state([me]), [me]))

    def test_relearn_forgets_the_track_saved_too_and_learns_it_from_the_next_clean_lap(self):
        # Asked for by the user on 2026-11-11, for a map learnt wrong.
        with tempfile.TemporaryDirectory() as folder:
            tracks = Path(folder) / trackmap.TRACKS_FOLDER
            other = trackmap.TrackMap(folder=folder)
            drive(other, LINES + 1.5, OFF_GATES)  # another track's map stays
            track_map = trackmap.TrackMap(folder=folder)
            self.assertFalse(track_map.has_track)
            self.assertFalse(track_map.relearn())  # no track known yet
            drive(track_map, LINES + 1.5)
            file = tracks / f'{trackmap.track_key(GATES)}.json'
            self.assertTrue(file.exists())
            self.assertTrue(track_map.has_track)
            self.assertTrue(track_map.relearn())
            self.assertFalse(file.exists())
            self.assertTrue((tracks / f'{trackmap.track_key(OFF_GATES)}.json').exists())
            self.assertIsNone(track_map.learned)
            me = driver('Me', 0.5, local=True)
            self.assertIsNone(trackmap.TrackMap(folder=folder).update(state([me]), [me]))  # nothing saved
            view = drive(track_map, LINES + 4, since=LINES + 1.55)
            self.assertFalse(view.outline.closed)  # the stretch driven since, not the old map
            drive(track_map, 2 * LINES + 3, since=LINES + 4.05)
            self.assertIsNotNone(track_map.learned)  # the next whole clean lap
            self.assertTrue(file.exists())
            self.assertTrue(track_map.relearn())  # a second time, and with no file left, too
            file.unlink(missing_ok=True)
            self.assertTrue(track_map.relearn())

    def test_one_read_is_no_map(self):
        me = car('Me', 3, local=True)
        self.assertIsNone(trackmap.TrackMap().update(state([me]), [me]))

    def test_evened_points(self):
        self.assertEqual(
            trackmap.evened([(0.0, 0.0), (10.0, 0.0)], 2.5),
            [(0.0, 0.0), (2.5, 0.0), (5.0, 0.0), (7.5, 0.0), (10.0, 0.0)],
        )

    def test_fits_the_box_the_same_both_ways_with_z_up(self):
        scale, x_off, y_off = trackmap.map_transform((-100, -50, 100, 50), (240, 240), 20)
        self.assertAlmostEqual(scale, 1.0)  # 200 wide into 200 pixels
        self.assertAlmostEqual(x_off + -100 * scale, 20)  # left edge at the padding
        self.assertAlmostEqual(y_off - 50 * scale, 70)  # top (most z) centred down the box
        self.assertAlmostEqual(y_off - -50 * scale, 170)

    def test_the_road_grows_with_the_map_but_never_vanishes(self):
        self.assertEqual(trackmap.road_width(10), trackmap.LEAST_ROAD)
        self.assertAlmostEqual(trackmap.road_width(240), 240 * trackmap.ROAD_SHARE)


class DotTests(unittest.TestCase):
    def test_leader_next_ahead_next_behind_and_me(self):
        players = [
            car('Leader', 20),
            car('Ahead', 14),
            car('Me', 13, local=True),
            car('Behind', 12),
            car('Last', 11),
        ]
        dots = roles(view_of(players))
        self.assertEqual(set(dots), {'leader', 'ahead', 'me', 'behind'})  # others hidden by default
        self.assertEqual(dots['me'].position, on_track(13))
        self.assertEqual(dots['ahead'].position, on_track(14))
        self.assertEqual(dots['leader'].position, on_track(20))
        self.assertEqual(view_of(players).dots[-1].role, 'me')  # drawn last, on top

    def test_after_an_overtake_the_next_car_ahead_shows(self):
        before = [car('Leader', 20), car('Second', 15), car('Third', 14), car('Me', 13, local=True)]
        dots = roles(view_of(before))
        self.assertEqual(dots['ahead'].position, on_track(14))
        self.assertNotIn('behind', dots)
        after = [car('Leader', 20), car('Second', 16), car('Third', 14), car('Me', 15, local=True)]
        dots = roles(view_of(after))
        self.assertEqual(dots['ahead'].position, on_track(16))  # Second, now the car ahead
        self.assertEqual(dots['behind'].position, on_track(14))  # Third, passed

    def test_the_leader_right_ahead_is_one_dot_with_both_marks(self):
        dots = view_of([car('Leader', 14), car('Me', 13, local=True)]).dots
        self.assertEqual([d.role for d in dots], ['leader', 'me'])
        self.assertTrue(dots[0].ahead_too)

    def test_leading_shows_no_car_ahead_and_no_leader(self):
        dots = roles(view_of([car('Me', 20, local=True), car('Second', 18)]))
        self.assertEqual(set(dots), {'me', 'behind'})

    def test_a_backmarker_between_me_and_the_car_ahead(self):
        # Me: lap 3 (17 lines); a car a lap down on the road just ahead (11 lines: 6
        # behind in the race, 2 ahead on the road); the car ahead 4 lines up the road.
        players = [
            car('Leader', 30),
            car('Ahead', 21),
            car('Me', 17, local=True),
            car('Lapped', 11),
            car('Chaser', 5),  # 1.5 laps down, beyond the car ahead on the road
        ]
        dots = view_of(players).dots
        self.assertEqual([d.role for d in dots], ['backmarker', 'behind', 'ahead', 'leader', 'me'])
        self.assertEqual(dots[0].position, on_track(11))
        self.assertEqual(dots[1].position, on_track(5))  # next behind: not the backmarker

    def test_a_backmarker_past_the_car_ahead_is_not_marked(self):
        players = [car('Ahead', 18), car('Me', 17, local=True), car('Lapped', 12)]
        self.assertNotIn('backmarker', roles(view_of(players)))

    def test_a_car_close_behind_in_the_race_is_no_backmarker(self):
        players = [car('Me', 17, local=True), car('Behind', 16), car('Far', 14)]
        self.assertNotIn('backmarker', roles(view_of(players)))

    def test_when_leading_backmarkers_up_to_half_a_lap_ahead(self):
        players = [car('Me', 17, local=True), car('Second', 16), car('Near', 11), car('Far', 13)]
        dots = view_of(players).dots
        marked = [d.position for d in dots if d.role == 'backmarker']
        self.assertEqual(marked, [on_track(11)])  # 13 is 4 lines ahead: half the lap, not less

    def test_other_cars_only_when_turned_on(self):
        players = [car('Leader', 30), car('Middle', 25), car('Ahead', 21), car('Me', 20, local=True)]
        self.assertNotIn('other', roles(view_of(players)))
        dots = view_of(players, others=True).dots
        self.assertEqual(dots[0].role, 'other')  # drawn first, under the rest
        self.assertEqual(dots[0].position, on_track(25))

    def test_pits_dim_and_cars_without_a_position_are_left_out(self):
        players = [
            car('Leader', 20),
            car('Ahead', 14, in_pit=True),
            car('Me', 13, local=True),
            car('Behind', 12, position=False),
        ]
        dots = roles(view_of(players))
        self.assertTrue(dots['ahead'].in_pit)
        self.assertNotIn('behind', dots)

    def test_road_progress_counts_the_share_to_the_next_line(self):
        me = car('Me', 3, local=True)
        self.assertAlmostEqual(trackmap.road_progress(me, GATES), 3.3, places=1)
        self.assertEqual(trackmap.road_progress(car('X', 3, position=False), GATES), 3.0)


class SpectatorDotTests(unittest.TestCase):
    def view(self, *players):
        return learnt_map().update(dataclasses.replace(state(players), spectating=True), players)

    def test_every_car_shows_with_the_leader_on_top(self):
        leader, second, third = driver('A', 30), driver('B', 20), driver('C', 10)
        view = self.view(leader, second, third)
        self.assertEqual([dot.role for dot in view.dots], ['car', 'car', 'leader'])
        self.assertEqual(view.dots[-1].position, leader.position)

    def test_a_car_without_a_position_has_no_dot(self):
        view = self.view(driver('A', 30), car('B', 20, position=False))
        self.assertEqual([dot.role for dot in view.dots], ['leader'])

    def test_no_local_player_and_not_spectating_shows_nothing(self):
        leader = driver('A', 30)
        self.assertIsNone(learnt_map().update(state([leader]), [leader]))


class RaceSectionsTests(unittest.TestCase):
    def test_the_map_is_a_race_section_in_the_player_lists_order(self):
        players = (car('Ahead', 14), car('Me', 13, local=True))
        lap_state = race.LapState(
            clock=130_000,
            time_limit=0,
            laps_completed=1,
            laps_to_finish=3,
            lap_starts=[0, 80_000],
            checkpoints=players[1].checkpoints,
            gates=GATES,
            players=players,
        )
        snapshot = race.Snapshot(race.RACING, lap_state, True, 1.0, moved_at=1.0)
        sections = race.race_sections(snapshot, 1.0, track_map=learnt_map())
        self.assertEqual([d.role for d in sections['trackmap'].dots], ['leader', 'me'])
        self.assertNotIn('trackmap', race.race_sections(snapshot, 1.0))

    def arena(self, spectating=False):
        players = (car('Ahead', 14), car('Me', 13, local=not spectating))
        lap_state = race.LapState(
            clock=130_000,
            time_limit=0,
            laps_completed=1,
            laps_to_finish=3,
            lap_starts=[] if spectating else [0, 80_000],
            checkpoints=() if spectating else players[1].checkpoints,
            gates=GATES,
            players=players,
            spectating=spectating,
            on_a_track=False,  # battle, capture the flag, King of the Hill, Sumo ...
        )
        return race.Snapshot(race.RACING, lap_state, True, 1.0, moved_at=1.0)

    def test_no_map_and_no_track_learnt_in_an_arena_mode(self):
        class Watched:
            calls = 0

            def update(self, *_args):
                Watched.calls += 1

        for spectating in (False, True):
            sections = race.race_sections(self.arena(spectating), 1.0, track_map=Watched())
            self.assertNotIn('trackmap', sections)
        self.assertEqual(Watched.calls, 0)  # update learns the track: not even called


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class MapWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def window(self):
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            name = 'test'

        section = next(s for s in RACE_SECTIONS if s.name == 'trackmap')
        window = SectionWindow(Native(), Theme(), section)
        window.resize(300, 240)  # wider than tall: the map stays square in the middle
        return window

    def test_draws_the_road_and_the_leader_in_gold(self):
        from PySide6.QtGui import QColor

        from turbohud.overlay.window import MAP_COLORS

        window = self.window()
        window.trackmap = view_of([car('Leader', 20), car('Ahead', 14), car('Me', 13, local=True)])
        image = window.grab().toImage()
        gold = QColor(MAP_COLORS['leader'])
        found = [
            (x, y)
            for x in range(0, image.width(), 2)
            for y in range(0, image.height(), 2)
            if image.pixelColor(x, y).rgb() == gold.rgb()
        ]
        self.assertTrue(found)
        self.assertTrue(all(30 <= x <= 270 for x, _y in found))  # inside the square

    def test_a_spectators_map_draws_its_cars(self):
        from PySide6.QtGui import QColor

        from turbohud.overlay.window import MAP_COLORS

        window = self.window()
        players = (driver('A', 30), driver('B', 20))
        window.trackmap = learnt_map().update(dataclasses.replace(state(players), spectating=True), players)
        image = window.grab().toImage()
        colour = QColor(MAP_COLORS['car']).rgb()
        pixels = (image.pixelColor(x, y).rgb() for x in range(image.width()) for y in range(image.height()))
        self.assertIn(colour, pixels)

    def test_a_car_under_the_local_player_still_shows(self):
        from PySide6.QtGui import QColor

        from turbohud.overlay.window import MAP_COLORS

        window = self.window()
        # The leader a whole lap ahead, at the same spot as the local player.
        window.trackmap = view_of([car('Leader', 21), car('Me', 13, local=True)])
        me = next(d for d in window.trackmap.dots if d.role == 'me')
        self.assertEqual(me.position, window.trackmap.dots[0].position)
        image = window.grab().toImage()
        gold = QColor(MAP_COLORS['leader']).rgb()
        self.assertTrue(
            any(
                image.pixelColor(x, y).rgb() == gold
                for x in range(image.width())
                for y in range(image.height())
            )
        )

    def test_nothing_when_locked_without_a_race_and_a_sample_in_move_mode(self):
        window = self.window()
        image = window.grab().toImage()
        self.assertEqual(image.pixelColor(150, 120).alpha(), 0)
        window.locked = False
        image = window.grab().toImage()
        self.assertGreater(
            sum(image.pixelColor(x, y).alpha() > 0 for x in range(0, 300, 10) for y in range(0, 240, 10)), 50
        )


if __name__ == '__main__':
    unittest.main()
