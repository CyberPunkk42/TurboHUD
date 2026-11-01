import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from turbohud.core import hud


class ClockTests(unittest.TestCase):
    def test_clock(self):
        self.assertEqual(hud.clock(0), '0:00')
        self.assertEqual(hud.clock(83.9), '1:23')
        self.assertEqual(hud.clock(600), '10:00')


def measure(text, size):
    """A stand-in for Qt's text width: every letter 0.6 of the font size wide."""
    return len(text) * size * 0.6


class NewSectionPlaceTests(unittest.TestCase):
    def test_new_sections_go_below_the_placed_ones(self):
        placed = {'lap': (2000, 100, 200, 40), 'delta': (2500, 900, 300, 60)}
        sizes = {'fuel': (220, 30), 'tires': (230, 30)}
        new = [s for s in hud.RACE_SECTIONS if s.name in sizes]
        places = hud.below(new, placed, sizes, gap=8)
        self.assertEqual(places['fuel'], (2000, 968, 220, 30))
        self.assertEqual(places['tires'], (2000, 1006, 230, 30))


class NewSectionsAtTheBottomTests(unittest.TestCase):
    def test_a_new_column_when_there_is_no_room_below(self):
        # As on the player's screen: the lowest section ends at y 1436 of a 1440 high screen.
        placed = {'lap': (1093, 5, 583, 120), 'fuel': (1445, 1357, 309, 79)}
        sizes = {'tires': (242, 63), 'speed': (121, 63)}
        new = [s for s in hud.RACE_SECTIONS if s.name in sizes]
        places = hud.below(new, placed, sizes, screens=[(0, 0, 5120, 1440)], gap=8)
        self.assertEqual(places['tires'], (1762, 5, 242, 63))
        self.assertEqual(places['speed'], (1762, 76, 121, 63))


class NewSectionsWithOthersOnAnotherMonitorTests(unittest.TestCase):
    def test_sections_on_another_monitor_do_not_count(self):
        # As the player had it: tires and speed on the upper monitor (y -1400).
        placed = {
            'lap': (1093, 5, 583, 120), 'fuel': (1445, 1357, 309, 79),
            'tires': (1320, -1400, 242, 63), 'speed': (1320, -1400, 121, 63),
        }
        screens = [(1280, -1440, 2560, 1440), (0, 0, 5120, 1440)]
        clock = [s for s in hud.RACE_SECTIONS if s.name == 'localtime']
        place = hud.below(clock, placed, {'localtime': (81, 62)}, screens=screens)['localtime']
        self.assertEqual(place, (1762, 5, 81, 62))  # main monitor, right of the others


class FirstLaunchTests(unittest.TestCase):
    SIZES = {s.name: (300, 70) for s in hud.RACE_SECTIONS}

    def test_one_column_at_the_left_centred_in_1080_without_overlap(self):
        places = hud.first_launch(hud.RACE_SECTIONS, self.SIZES)
        boxes = [places[s.name] for s in hud.RACE_SECTIONS if not s.bar]
        self.assertNotIn('blueflag', places)  # a bar: top centre instead
        self.assertTrue(all(x == 40 for x, *_ in boxes))
        for (_, y1, _, h1), (_, y2, _, _) in zip(boxes, boxes[1:]):
            self.assertGreaterEqual(y2, y1 + h1)  # below, not overlapping
        top, bottom = boxes[0][1], boxes[-1][1] + boxes[-1][3]
        self.assertAlmostEqual(top - 40, 1040 - bottom, delta=1)  # centred
        self.assertLessEqual(bottom, 1080 - 40)

    def test_the_blue_flag_bar_goes_top_centre(self):
        blue = next(s for s in hud.RACE_SECTIONS if s.name == 'blueflag')
        size = hud.base_size(blue, 1.0, lambda text, size: len(text) * size)
        self.assertEqual(size, (480, 24))
        self.assertEqual(hud.top_centre(size, (0, 0, 1920, 1080)), (720, 40, 480, 24))
        self.assertEqual(hud.top_centre(size, (100, -1440, 2560, 1440)), (1140, -1400, 480, 24))

    def test_on_the_main_screen_from_its_corner(self):
        screens = [(1280, -1440, 2560, 1440), (0, 0, 5120, 1440)]  # the player's two monitors
        self.assertEqual(hud.main_screen(screens), (0, 0, 5120, 1440))
        moved = hud.first_launch(hud.RACE_SECTIONS, self.SIZES, origin=(1000, 200))
        plain = hud.first_launch(hud.RACE_SECTIONS, self.SIZES)
        self.assertEqual(moved['lap'][:2], (plain['lap'][0] + 1000, plain['lap'][1] + 200))

    def test_too_tall_for_one_column_starts_another(self):
        tall = {s.name: (300, 200) for s in hud.RACE_SECTIONS}
        places = hud.first_launch(hud.RACE_SECTIONS, tall)
        xs = sorted({x for x, *_ in places.values()})
        self.assertEqual(xs[:2], [40, 40 + 300 + 8])
        self.assertTrue(all(y + h <= 1040 for _x, y, _w, h in places.values()))


class HelpLinesTests(unittest.TestCase):
    def test_move_mode_says_how_to_finish(self):
        self.assertIn('Ctrl+Shift+L', hud.help_lines(shortcuts=True)[-1])
        without = ' '.join(hud.help_lines(shortcuts=False))
        self.assertIn('Lock', without)
        self.assertNotIn('Ctrl', without)


class HudLinesTests(unittest.TestCase):
    def test_session_rows(self):
        lines = hud.hud_lines(hud.session_rows(65))
        self.assertEqual([line.color for line in lines], ['text', 'accent'])
        self.assertEqual(lines[1].text, '1:05')

    def test_rows_use_their_style_and_colour(self):
        lines = hud.hud_lines([hud.Row('a', 'title'), hud.Row('b', 'medium', 'accent')])
        sizes = hud.Sizes.for_scale(1)
        self.assertEqual([(line.size, line.color) for line in lines], [(sizes.title, 'text'), (sizes.medium, 'accent')])

    def test_lines_go_down_and_grow_with_the_scale(self):
        normal = hud.hud_lines(hud.session_rows(0))
        double = hud.hud_lines(hud.session_rows(0), scale=2)
        self.assertLess(normal[0].baseline, normal[1].baseline)
        for one, two in zip(normal, double, strict=True):
            self.assertAlmostEqual(two.size, 2 * one.size, delta=1)
            self.assertAlmostEqual(two.baseline, 2 * one.baseline, delta=2)


class LocalTimeTests(unittest.TestCase):
    def test_hours_and_minutes_in_24_hours(self):
        import time

        self.assertEqual(hud.local_time_rows(time.struct_time((2026, 11, 1, 17, 5, 59, 6, 305, 0)))[0].text, '17:05')
        self.assertEqual(hud.local_time_rows(time.struct_time((2026, 11, 1, 0, 0, 0, 6, 305, 0)))[0].text, '00:00')

    def test_on_every_system(self):
        for layout in (hud.RACE_SECTIONS, hud.CLOCK_SECTIONS):
            self.assertIn('localtime', [section.name for section in layout])


class PedalBarTests(unittest.TestCase):
    def test_bars_are_as_tall_as_the_section_left_green_right_red(self):
        throttle, brake = hud.pedal_bars(200, 60, 1, throttle=1.0, brake=0.0)
        self.assertEqual((throttle.x, throttle.color, throttle.fill), (4, 'ahead', 1.0))
        self.assertEqual((brake.x + brake.width, brake.color, brake.fill), (196, 'behind', 0.0))
        self.assertEqual(throttle.height, 60 - 8)

    def test_unknown_or_out_of_range_input_is_clamped(self):
        throttle, brake = hud.pedal_bars(200, 60, 1, throttle=None, brake=1.7)
        self.assertEqual((throttle.fill, brake.fill), (0.0, 1.0))

    def test_the_speed_section_makes_room_for_its_bars(self):
        speed = next(s for s in hud.RACE_SECTIONS if s.name == 'speed')
        self.assertTrue(speed.pedals)
        text_width = hud.content_size(speed.samples[0], 1, measure)[0]
        self.assertEqual(hud.base_size(speed, 1, measure)[0], text_width + hud.pedal_space(1))


class SectionTests(unittest.TestCase):
    def test_race_sections_have_distinct_names(self):
        names = [section.name for section in hud.RACE_SECTIONS]
        self.assertEqual(names, ['lap', 'current', 'delta', 'times', 'fuel', 'fuelfinish', 'tires', 'speed', 'localtime', 'players', 'blueflag'])
        self.assertEqual(len(set(names)), len(names))

    def test_content_size_fits_the_text(self):
        width, height = hud.content_size([hud.Row('0:00.0', 'big')], 1, measure)
        sizes = hud.Sizes.for_scale(1)
        self.assertEqual(width, round(6 * 40 * 0.6 + 2 * sizes.margin))
        self.assertGreater(height, sizes.big)

    def test_base_size_is_as_wide_as_the_usual_content_and_as_tall_as_the_tallest(self):
        lap = hud.RACE_SECTIONS[0]
        width, height = hud.base_size(lap, 1, measure)
        self.assertEqual(width, hud.content_size(lap.samples[0], 1, measure)[0])
        self.assertEqual(height, max(hud.content_size(rows, 1, measure)[1] for rows in lap.samples))

    def test_the_height_sets_the_text_size(self):
        self.assertEqual(hud.section_scale((500, 50), 50), 1.0)
        self.assertEqual(hud.section_scale((500, 150), 50), 3.0)
        # Wider alone changes nothing.
        self.assertEqual(hud.section_scale((900, 50), 50), 1.0)

    def test_text_shrinks_only_when_the_box_is_too_narrow_for_it(self):
        self.assertEqual(hud.section_scale((300, 100), 50, needed_width=100), 2.0)  # fits
        self.assertEqual(hud.section_scale((150, 100), 50, needed_width=100), 1.5)  # too narrow
        self.assertEqual(hud.section_scale((10, 5), 50), 0.3)  # never below 0.3

    def test_first_start_stacks_the_sections_where_the_hud_was(self):
        sizes = {'lap': (200, 40), 'current': (150, 60), 'delta': (180, 30), 'times': (300, 30)}
        places = hud.stacked(hud.RACE_SECTIONS[:4], 40, 40, sizes, gap=8)
        self.assertEqual(places['lap'], (40, 40, 200, 40))
        self.assertEqual(places['current'], (40, 88, 150, 60))
        self.assertEqual(places['times'][1], 40 + 40 + 8 + 60 + 8 + 30 + 8)


class CoreIsQtFreeTests(unittest.TestCase):
    def test_core_does_not_use_qt(self):
        for path in (ROOT / 'turbohud' / 'core').glob('*.py'):
            with self.subTest(path=path.name):
                self.assertNotIn('PySide6', path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()


MOVER_GROUPS = {'lap': 'A', 'delta': 'A', 'speed': 'A', 'fuel': 'B', 'tires': ''}


class GroupMoverTests(unittest.TestCase):

    def look(self, mover, seen, now):
        return mover.follow(dict(seen), MOVER_GROUPS, now)

    def start(self):
        mover = hud.GroupMover()
        seen = {'lap': (10, 10, 100, 40), 'delta': (10, 60, 100, 30), 'speed': (10, 100, 100, 30),
                'fuel': (300, 10, 100, 30), 'tires': (300, 60, 100, 30)}
        self.assertEqual(self.look(mover, seen, 0.0), {})  # first look: nothing to compare
        return mover, seen

    def test_dragging_one_moves_its_group_only(self):
        mover, seen = self.start()
        seen['delta'] = (60, 80, 100, 30)  # dragged 50 right, 20 down
        moves = self.look(mover, seen, 0.2)
        self.assertEqual(moves, {'lap': (60, 30, 100, 40), 'speed': (60, 120, 100, 30)})

    def test_the_followers_arriving_is_not_taken_for_a_drag(self):
        mover, seen = self.start()
        seen['delta'] = (60, 80, 100, 30)
        self.look(mover, seen, 0.2)
        seen.update(lap=(60, 30, 100, 40), speed=(61, 120, 100, 30))  # arrived (within a pixel)
        self.assertEqual(self.look(mover, seen, 0.4), {})
        self.assertEqual(mover.pending, {})

    def test_a_follower_on_its_way_is_not_a_drag_and_the_drag_goes_on(self):
        mover, seen = self.start()
        seen['delta'] = (60, 80, 100, 30)
        self.look(mover, seen, 0.2)
        seen['delta'] = (70, 80, 100, 30)  # still dragging; the others have not arrived yet
        moves = self.look(mover, seen, 0.4)
        self.assertEqual(moves, {'lap': (70, 30, 100, 40), 'speed': (70, 120, 100, 30)})

    def test_a_follower_that_never_arrives_is_taken_where_it_is(self):
        mover, seen = self.start()
        seen['delta'] = (60, 80, 100, 30)
        self.look(mover, seen, 0.2)
        self.assertEqual(self.look(mover, seen, 2.0), {})  # lap and speed stayed: no pull back
        self.assertEqual(mover.known['lap'], (10, 10, 100, 40))

    def test_resizing_or_ungrouped_moves_nobody(self):
        mover, seen = self.start()
        seen['lap'] = (10, 10, 200, 80)  # resized at its corner
        seen['tires'] = (400, 400, 100, 30)  # no group
        self.assertEqual(self.look(mover, seen, 0.2), {})
