import importlib.util
import math
import os
import sys
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


def view_of(players, others=False):
    return trackmap.TrackMap(others).update(state(players), race.ranked(players))


class OutlineTests(unittest.TestCase):
    def test_a_round_track_is_a_closed_smooth_loop(self):
        outline = trackmap.track_outline(GATES)
        self.assertTrue(outline.closed)
        self.assertEqual(len(outline.points), LINES * 4)  # two rounds of corner cutting
        self.assertAlmostEqual(outline.width, 10.0)
        self.assertEqual(outline.start, GATES[0])
        min_x, min_z, max_x, max_z = outline.bounds
        self.assertTrue(-RADIUS <= min_x < -80 and 80 < max_x <= RADIUS)
        self.assertTrue(-RADIUS <= min_z < -80 and 80 < max_z <= RADIUS)

    def test_lines_at_the_same_spot_and_lines_in_two_pieces_are_one(self):
        (a, b) = GATES[2]
        middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        split = (a, middle), (middle, b)  # one line in two pieces
        gates = GATES[:2] + split + GATES[2:3] + GATES[3:]  # and the same line once more
        merged = trackmap.merged_gates(gates)
        self.assertEqual(len(merged), LINES)
        ends = sorted(merged[2])
        self.assertEqual(ends, sorted(GATES[2]))

    def test_one_line_after_another_stays_apart(self):
        straight = tuple(((float(z), -5.0), (float(z), 5.0)) for z in range(0, 50, 5))
        self.assertEqual(len(trackmap.merged_gates(straight)), len(straight))

    def test_a_point_to_point_track_stays_open_and_keeps_its_ends(self):
        straight = tuple(((-5.0, float(z)), (5.0, float(z))) for z in range(0, 200, 10))
        outline = trackmap.track_outline(straight)
        self.assertFalse(outline.closed)
        self.assertEqual(outline.points[0], (0.0, 0.0))
        self.assertEqual(outline.points[-1], (0.0, 190.0))

    def test_too_few_lines_give_no_map(self):
        self.assertIsNone(trackmap.track_outline(GATES[:2]))
        self.assertIsNone(trackmap.TrackMap().update(state([car('Me', 3, local=True)], ()), []))

    def test_fits_the_box_the_same_both_ways_with_z_up(self):
        scale, x_off, y_off = trackmap.map_transform((-100, -50, 100, 50), (240, 240), 20)
        self.assertAlmostEqual(scale, 1.0)  # 200 wide into 200 pixels
        self.assertAlmostEqual(x_off + -100 * scale, 20)  # left edge at the padding
        self.assertAlmostEqual(y_off - 50 * scale, 70)  # top (most z) centred down the box
        self.assertAlmostEqual(y_off - -50 * scale, 170)

    def test_the_road_is_never_lost_nor_too_fat(self):
        outline = trackmap.track_outline(GATES)
        self.assertEqual(trackmap.road_width(outline, 0.01, 240), trackmap.ROAD_PIXELS[0])
        self.assertAlmostEqual(trackmap.road_width(outline, 10.0, 240), 240 * trackmap.ROAD_PIXELS[1])

    def test_the_outline_is_kept_for_the_same_track(self):
        track_map = trackmap.TrackMap()
        first = track_map.outline(GATES)
        self.assertIs(track_map.outline(tuple(GATES)), first)
        self.assertIsNot(track_map.outline(circle_gates(radius=50.0)), first)


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
        sections = race.race_sections(snapshot, 1.0, track_map=trackmap.TrackMap())
        self.assertEqual([d.role for d in sections['trackmap'].dots], ['leader', 'me'])
        self.assertNotIn('trackmap', race.race_sections(snapshot, 1.0))


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
