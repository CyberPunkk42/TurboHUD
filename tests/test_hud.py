import itertools
import sys
import unittest
from pathlib import Path
from typing import ClassVar

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


class CentredTextTests(unittest.TestCase):
    ROW: ClassVar = [hud.Row('123 km/h', 'medium')]  # 20 px at scale 1, baseline at 34

    def place(self, size, rows=None, least_left=0, scale=1.0):
        return hud.centred_text(size, rows or self.ROW, scale, measure, lambda font: font * 0.7, least_left)

    def test_the_text_is_centred_both_ways(self):
        # 96 wide and 28 of margins: 124; from 20 (the cap height's top) to 34 (the baseline).
        self.assertEqual(self.place((324, 100)), (100, 23))

    def test_it_stays_centred_when_shrunk(self):
        left, down = self.place((324, 30), scale=0.5)  # 10 px, margins of 7
        self.assertEqual(left, (324 - (48 + 14)) // 2)
        self.assertEqual(down, 15 - 13)  # from 10 to 17: its middle is 13.5, rounded evenly

    def test_digits_do_not_move_it(self):
        def proportional(text, size):
            return sum(0.2 if letter == '1' else 0.6 for letter in text) * size

        places = {
            hud.centred_text((300, 60), [hud.Row(text, 'medium')], 1.0, proportional, lambda _size: 14, 0)
            for text in ('111 km/h', '123 km/h', '888 km/h')
        }
        self.assertEqual(len(places), 1)

    def test_it_stays_clear_of_what_is_at_the_side(self):
        self.assertEqual(self.place((100, 60), least_left=28)[0], 28)


def ink(_text, size):
    """A stand-in for Qt's letters: as tall as 0.7 of the font size, nothing below."""
    return size * 0.7, 0


class SteadySizeTests(unittest.TestCase):
    SECTIONS: ClassVar = {section.name: section for section in hud.RACE_SECTIONS}

    @staticmethod
    def proportional(text, size):
        return sum(0.3 if letter == '1' else 0.6 for letter in text) * size

    def scale_of(self, name, text, box, style='medium'):
        section = self.SECTIONS[name]
        normal = hud.tight_height(section, 1.0, ink)
        return hud.drawn_scale(section, box, [hud.Row(text, style)], normal, 1.0, ink, self.proportional)

    def test_digits_do_not_change_the_text_size(self):
        for name, style, first, second in (
            ('current', 'big', '1:11.1', '8:88.8'),
            ('delta', 'medium', '+1.111 vs best', '+8.888 vs best'),
        ):
            normal = hud.tight_height(self.SECTIONS[name], 1.0, ink)
            for box in ((120, 200), (200, 60), (300, normal * 3)):
                with self.subTest(section=name, box=box):
                    self.assertEqual(
                        self.scale_of(name, first, box, style), self.scale_of(name, second, box, style)
                    )

    def test_short_text_is_not_larger_than_the_usual_text(self):
        box = (300, 90)
        self.assertEqual(
            self.scale_of('times', 'Last -   Best -', box),
            self.scale_of('times', 'Last 1:23.456   Best 1:22.000', box),
        )

    def test_longer_text_than_usual_still_fits(self):
        section = self.SECTIONS['delta']
        row = hud.Row('Something much longer than the usual text of this section', 'medium')
        scale = self.scale_of('delta', row.text, (200, 90))
        self.assertLessEqual(hud.content_size([row], scale, self.proportional)[0], 200)
        self.assertIs(section, self.SECTIONS['delta'])

    def test_no_rows_measure_nothing(self):
        self.assertEqual(hud.widest_rows(self.SECTIONS['delta'], [], 1.0, self.proportional), [])

    def test_every_column_counts_as_steady(self):
        row = hud.Row('1', 'small', tail='2', middle='3', right='4')
        steady = hud.steady_rows([row])[0]
        self.assertEqual((steady.text, steady.tail, steady.middle, steady.right), ('0', '0', '0', '0'))


class TextCanCentreTests(unittest.TestCase):
    def test_sections_with_plain_text_can(self):
        can = {section.name for section in hud.RACE_SECTIONS if hud.text_can_centre(section)}
        self.assertEqual(
            can,
            {
                'lap',
                'current',
                'delta',
                'times',
                'fuel',
                'fuelfinish',
                'tires',
                'health',
                'draft',
                'localtime',
            },
        )

    def test_digits_do_not_change_what_is_measured(self):
        self.assertEqual(hud.steady_text('Fuel 81.9%'), hud.steady_text('Fuel 00.0%'))


class TightBoxTests(unittest.TestCase):
    TIME: ClassVar = next(section for section in hud.RACE_SECTIONS if section.name == 'localtime')
    FUEL: ClassVar = next(section for section in hud.RACE_SECTIONS if section.name == 'fuel')
    SPEED: ClassVar = next(section for section in hud.RACE_SECTIONS if section.name == 'speed')
    LAP: ClassVar = next(section for section in hud.RACE_SECTIONS if section.name == 'lap')

    def test_the_box_fits_closely_round_the_text(self):
        # A 20 px font: from 20 to 34, and 3 px of room at each edge.
        self.assertEqual(hud.ink_span(self.TIME, 1.0, ink), (20.0, 34))
        self.assertEqual(hud.tight_height(self.TIME, 1.0, ink), 20)

    def test_the_box_includes_the_level_bar(self):
        self.assertEqual(hud.ink_span(self.FUEL, 1.0, ink), (20.0, 49))

    def test_room_is_kept_for_letters_below_the_line_where_there_are_letters(self):
        def hanging(text, size):
            return size * 0.7, size * 0.2 if 'g' in text else 0

        self.assertEqual(hud.ink_span(self.TIME, 1.0, hanging)[1], 34)  # digits only
        self.assertEqual(hud.ink_span(self.LAP, 1.0, hanging)[1], 30 + 16 * 0.2)

    def test_rounding_cannot_make_a_long_list_stick_out(self):
        times = next(section for section in hud.RACE_SECTIONS if section.name == 'laptimes')
        normal = hud.tight_height(times, 1.0, ink)
        for share in (0.45, 0.6, 0.77, 1.3, 2.2):
            with self.subTest(share=share):
                height = round(normal * share)
                top, bottom = hud.ink_span(times, hud.fitted_scale(times, height, share, ink), ink)
                self.assertLessEqual(bottom - top + hud.FIT_ROOM, height)

    def test_text_wider_than_in_proportion_shrinks_to_its_box(self):
        def wide_when_small(text, size):
            return len(text) * size * (0.6 if size >= 20 else 0.9)

        times = next(section for section in hud.RACE_SECTIONS if section.name == 'times')
        rows = [hud.Row('Last 0:48.442   Best 0:48.442', 'medium')]
        scale = hud.fitted_scale(times, 100, 0.8, ink, 300, rows, wide_when_small)
        self.assertLess(scale, 0.8)
        self.assertLessEqual(hud.content_size(rows, scale, wide_when_small)[0], 300)

    def test_text_that_fits_its_width_keeps_its_scale(self):
        times = next(section for section in hud.RACE_SECTIONS if section.name == 'times')
        rows = [hud.Row('Last', 'medium')]
        self.assertEqual(hud.fitted_scale(times, 100, 1.0, ink, 900, rows, measure), 1.0)

    def test_the_pedal_bars_count_across(self):
        speed = next(section for section in hud.RACE_SECTIONS if section.name == 'speed')
        rows = [hud.Row('000 km/h', 'medium')]
        scale = hud.fitted_scale(speed, 100, 1.0, ink, 150, rows, measure)
        self.assertLessEqual(hud.content_size(rows, scale, measure)[0] + hud.pedal_space(scale), 150)

    def test_content_that_fits_keeps_its_scale(self):
        self.assertEqual(hud.fitted_scale(self.TIME, 100, 1.0, ink), 1.0)

    def test_the_content_is_centred_in_its_box(self):
        self.assertEqual(hud.content_shift(self.TIME, 20, 1.0, ink), -17)  # 3 px left above
        self.assertEqual(hud.content_shift(self.TIME, 54, 1.0, ink), 0)
        self.assertEqual(hud.content_shift(self.TIME, 10, 0.5, ink), -8)

    def test_a_saved_box_becomes_tight_with_the_text_as_it_was(self):
        # Local time at 2.5 times its old normal height of 62: a 50 px font, from 50 to 85.
        x, y, width, height = hud.tight_place(self.TIME, (100, 200, 300, 155), 1.0, ink)
        self.assertEqual((x, width, height), (100, 300, 50))
        self.assertEqual(height / hud.tight_height(self.TIME, 1.0, ink), 2.5)
        # It is drawn with 8 px left above the digits now: they stay where they were.
        drawn = 2.5
        top = hud.ink_span(self.TIME, drawn, ink)[0]
        self.assertEqual(top, 50.0)
        self.assertEqual(y + top + hud.content_shift(self.TIME, height, drawn, ink), 200 + top)

    def test_a_saved_speed_box_keeps_its_middle(self):
        x, y, width, height = hud.tight_place(self.SPEED, (100, 200, 300, 155), 1.0, ink)
        self.assertAlmostEqual(y + height / 2, 200 + 155 / 2, delta=1)
        self.assertEqual((x, width), (100, 300))

    def test_a_drawing_keeps_its_place(self):
        radar = next(section for section in hud.RACE_SECTIONS if section.name == 'radar')
        self.assertEqual(hud.tight_place(radar, (1, 2, 316, 316), 1.0, ink), (1, 2, 316, 316))


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
            'lap': (1093, 5, 583, 120),
            'fuel': (1445, 1357, 309, 79),
            'tires': (1320, -1400, 242, 63),
            'speed': (1320, -1400, 121, 63),
        }
        screens = [(1280, -1440, 2560, 1440), (0, 0, 5120, 1440)]
        clock = [s for s in hud.RACE_SECTIONS if s.name == 'localtime']
        place = hud.below(clock, placed, {'localtime': (81, 62)}, screens=screens)['localtime']
        self.assertEqual(place, (1762, 5, 81, 62))  # main monitor, right of the others


class FirstLaunchTests(unittest.TestCase):
    SIZES: ClassVar[dict] = {s.name: (300, 60) for s in hud.RACE_SECTIONS}

    def test_one_column_at_the_left_centred_in_1080_without_overlap(self):
        places = hud.first_launch(hud.RACE_SECTIONS, self.SIZES)
        boxes = [places[s.name] for s in hud.RACE_SECTIONS if not s.bar]
        self.assertNotIn('blueflag', places)  # a bar: top centre instead
        self.assertTrue(all(x == 40 for x, *_ in boxes))
        for (_, y1, _, h1), (_, y2, _, _) in itertools.pairwise(boxes):
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

    def test_the_radar_starts_centred_below_the_middle(self):
        radar = next(s for s in hud.RACE_SECTIONS if s.name == 'radar')
        self.assertNotIn('radar', hud.first_launch(hud.RACE_SECTIONS, self.SIZES))
        self.assertEqual(hud.drawing_place(radar, (160, 160), (0, 0, 1920, 1080)), (880, 648, 160, 160))

    def test_the_track_map_starts_at_the_right_half_way_down(self):
        track_map = next(s for s in hud.RACE_SECTIONS if s.name == 'trackmap')
        self.assertEqual(hud.base_size(track_map, 1.0, lambda text, size: 0), (240, 240))
        self.assertNotIn('trackmap', hud.first_launch(hud.RACE_SECTIONS, self.SIZES))
        place = hud.drawing_place(track_map, (240, 240), (0, 0, 1920, 1080))
        self.assertEqual(place, (1640, 420, 240, 240))

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
        self.assertEqual(
            [(line.size, line.color) for line in lines], [(sizes.title, 'text'), (sizes.medium, 'accent')]
        )

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

        self.assertEqual(
            hud.local_time_rows(time.struct_time((2026, 11, 1, 17, 5, 59, 6, 305, 0)))[0].text, '17:05'
        )
        self.assertEqual(
            hud.local_time_rows(time.struct_time((2026, 11, 1, 0, 0, 0, 6, 305, 0)))[0].text, '00:00'
        )

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
        self.assertEqual(
            names,
            [
                'lap',
                'current',
                'delta',
                'times',
                'fuel',
                'fuelfinish',
                'tires',
                'health',
                'draft',
                'speed',
                'localtime',
                'players',
                'laptimes',
                'blueflag',
                'radar',
                'trackmap',
            ],
        )
        self.assertEqual(len(set(names)), len(names))

    def test_a_middle_column_lines_up_before_the_right_one(self):
        rows = [
            hud.Row('Driver', 'small', middle='Best', right='Lap'),
            hud.Row('1. Somebody', 'small', middle='1:23.456', right='0:12.3'),
        ]
        lines = hud.hud_lines(rows)
        size = lines[0].size
        gap = hud.COLUMN_GAP * size
        expected = (
            measure('1. Somebody', size) + gap + measure('1:23.456', size) + gap + measure('0:12.3', size)
        )
        self.assertEqual(hud.lines_width(lines, measure), expected)
        # The middle column ends one gap before the widest right column.
        self.assertEqual(hud.middle_right(lines, 500, 14, measure), 500 - 14 - measure('0:12.3', size) - gap)

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
        seen = {
            'lap': (10, 10, 100, 40),
            'delta': (10, 60, 100, 30),
            'speed': (10, 100, 100, 30),
            'fuel': (300, 10, 100, 30),
            'tires': (300, 60, 100, 30),
        }
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

    def test_an_ungrouped_section_moves_nobody(self):
        mover, seen = self.start()
        seen['tires'] = (400, 400, 100, 30)  # no group
        self.assertEqual(self.look(mover, seen, 0.2), {})

    def test_resizing_one_resizes_its_group_by_the_same_factors(self):
        mover, seen = self.start()
        seen['lap'] = (10, 10, 200, 80)  # twice as wide and as tall, at its corner
        self.assertEqual(
            self.look(mover, seen, 0.2), {'delta': (10, 60, 200, 60), 'speed': (10, 100, 200, 60)}
        )

    def test_the_followers_arriving_at_their_size_is_not_taken_for_a_resize(self):
        mover, seen = self.start()
        seen['lap'] = (10, 10, 200, 80)
        moves = self.look(mover, seen, 0.2)
        seen.update(moves)
        self.assertEqual(self.look(mover, seen, 0.4), {})
        self.assertEqual(mover.pending, {})
        self.assertEqual(mover.known['delta'], (10, 60, 200, 60))

    def test_a_follower_not_at_its_size_yet_is_still_on_its_way(self):
        mover, seen = self.start()
        seen['lap'] = (10, 10, 200, 80)
        self.look(mover, seen, 0.2)
        seen['delta'] = (10, 60, 110, 35)  # moved a little, not there: not a resize of its own
        self.assertEqual(self.look(mover, seen, 0.4), {})
        self.assertIn('delta', mover.pending)

    def test_sizes_come_from_the_start_of_a_resize_so_rounding_does_not_add_up(self):
        mover = hud.GroupMover()
        groups = {'a': 'A', 'b': 'A'}
        seen = {'a': (0, 0, 100, 100), 'b': (0, 200, 33, 33)}
        mover.follow(dict(seen), groups, 0.0)
        now = 0.0
        for height in range(101, 301):
            now += 0.2
            seen['a'] = (0, 0, 100, height)
            seen.update(mover.follow(dict(seen), groups, now))
        self.assertEqual(seen['b'][3], 99)
        self.assertEqual(seen['b'][2], 33)

    def test_a_new_resize_starts_from_the_sizes_at_that_time(self):
        mover, seen = self.start()
        seen['lap'] = (10, 10, 200, 80)
        seen.update(self.look(mover, seen, 0.2))
        self.look(mover, seen, 0.4)  # it stopped
        self.assertEqual(mover.resizing, {})
        seen['delta'] = (10, 60, 400, 60)  # now another one, twice as wide
        self.assertEqual(self.look(mover, seen, 0.6)['lap'], (10, 10, 400, 80))

    def test_two_sections_changing_at_once_move_nobody(self):
        mover, seen = self.start()
        seen['lap'] = (10, 10, 200, 80)
        seen['delta'] = (10, 60, 200, 60)
        self.assertEqual(self.look(mover, seen, 0.2), {})

    def test_dragging_keeps_the_sizes(self):
        mover, seen = self.start()
        seen['lap'] = (20, 20, 100, 40)
        self.assertEqual(self.look(mover, seen, 0.2)['delta'], (20, 70, 100, 30))


def size_measure(text, size):
    return len(text) * size * 0.6


class MatchSizesTests(unittest.TestCase):
    SECTIONS: ClassVar = {section.name: section for section in hud.RACE_SECTIONS}

    def match(self, **boxes):
        places = {self.SECTIONS[name]: box for name, box in boxes.items()}
        return hud.match_sizes(places, 1.0, size_measure, ink)

    def normal(self, name, share=1.0):
        section = self.SECTIONS[name]
        return (
            0,
            0,
            hud.base_size(section, 1.0, size_measure)[0],
            round(hud.tight_height(section, 1.0, ink) * share),
        )

    def font(self, name, box):
        section = self.SECTIONS[name]
        rows = list(section.samples[0])
        normal = hud.tight_height(section, 1.0, ink)
        return hud._first_font(
            section, hud.drawn_scale(section, box[2:], rows, normal, 1.0, ink, size_measure)
        )

    def test_every_section_gets_the_largest_font_and_one_width(self):
        boxes = {
            'localtime': self.normal('localtime', 3.0),
            'delta': self.normal('delta'),
            'fuel': self.normal('fuel'),
        }
        largest = self.font('localtime', boxes['localtime'])
        matched = self.match(**boxes)
        self.assertEqual({box[2] for box in matched.values()}, {max(box[2] for box in matched.values())})
        for name, box in matched.items():
            with self.subTest(section=name):
                self.assertEqual(self.font(name, box), largest)

    def test_rows_of_different_styles_get_the_same_font_size(self):
        matched = self.match(current=self.normal('current'), players=self.normal('players'))
        self.assertEqual(self.font('current', matched['current']), self.font('players', matched['players']))
        self.assertEqual(self.font('players', matched['players']), 40)

    def test_they_stay_where_they_are(self):
        matched = self.match(localtime=(5, 6, 100, 30), delta=(70, 80, 300, 30))
        self.assertEqual(matched['localtime'][:2], (5, 6))
        self.assertEqual(matched['delta'][:2], (70, 80))

    def test_matching_again_changes_nothing(self):
        once = self.match(localtime=self.normal('localtime', 2.0), speed=self.normal('speed'))
        again = self.match(**once)
        self.assertEqual(again, once)


class FrameTimesTests(unittest.TestCase):
    def setUp(self):
        self.now, self.lines = 0.0, []
        self.frames = hud.FrameTimes(lambda: self.now, lambda text, *args: self.lines.append(text % args))

    def run_frames(self, gap, count, worked=0.005, drawn=0.01):
        for _ in range(count):
            self.frames.frame(worked, drawn)
            self.now += gap

    def test_it_says_how_the_frames_came_every_so_often(self):
        self.run_frames(0.05, 601)
        self.assertEqual(len(self.lines), 1)
        self.assertIn('50 ms apart', self.lines[0])
        self.assertIn('content 10% and drawing 20%', self.lines[0])

    def test_a_late_frame_shows_as_the_slowest(self):
        self.run_frames(0.05, 10)
        self.now += 0.2
        self.run_frames(0.05, 3)
        self.frames.flush()
        self.assertIn('slowest 250 ms', self.lines[0])

    def test_no_line_without_frames_and_after_the_race_it_starts_afresh(self):
        self.frames.flush()
        self.assertEqual(self.lines, [])
        self.run_frames(0.05, 3)
        self.frames.flush()
        self.frames.flush()
        self.assertEqual(len(self.lines), 1)


class LayoutHistoryTests(unittest.TestCase):
    def test_undo_goes_back_one_change_at_a_time_until_none_is_left(self):
        history = hud.LayoutHistory('a')
        history.record('b')
        history.record('c')
        self.assertEqual(history.undo('c'), 'b')
        self.assertEqual(history.undo('b'), 'a')
        self.assertFalse(history.can_undo('a'))
        self.assertIsNone(history.undo('a'))
        self.assertEqual(history.current, 'a')

    def test_nothing_changed_is_no_step(self):
        history = hud.LayoutHistory('a')
        history.record('a')
        self.assertFalse(history.can_undo('a'))

    def test_a_drag_is_one_step_when_it_has_stood_still(self):
        history = hud.LayoutHistory('start')
        for now, state in ((0.2, 'x1'), (0.4, 'x2'), (0.6, 'x3'), (0.8, 'x3'), (1.5, 'x3')):
            history.look(state, now)
        self.assertEqual(history.past, [])  # not still for long enough yet
        history.look('x3', 1.6)
        self.assertEqual((history.past, history.current), (['start'], 'x3'))

    def test_undo_during_a_drag_goes_back_to_before_it(self):
        history = hud.LayoutHistory('start')
        history.look('moving', 0.2)
        self.assertTrue(history.can_undo('moving'))
        self.assertEqual(history.undo('moving'), 'start')
        self.assertFalse(history.can_undo('start'))

    def test_a_button_right_after_a_drag_is_a_step_of_its_own(self):
        history = hud.LayoutHistory('start')
        history.look('dragged', 0.2)
        history.record('dragged')  # undoable: before the button acts
        history.record('hidden')
        self.assertEqual(history.past, ['start', 'dragged'])

    def test_arriving_after_an_undo_is_no_new_step(self):
        history = hud.LayoutHistory('a')
        history.record('b')
        history.undo('b')
        for now in (0.2, 0.4, 3.0):
            history.look('a', now)
        self.assertFalse(history.can_undo('a'))

    def test_move_mode_starts_where_the_desktop_says_while_nothing_can_be_undone(self):
        history = hud.LayoutHistory('asked')
        history.resume('reported')
        self.assertFalse(history.can_undo('reported'))
        history.record('moved')
        history.resume('from a shortcut')
        self.assertEqual(history.past, ['reported', 'moved'])


class FreeSpotTests(unittest.TestCase):
    SCREEN = (0, 0, 5120, 1440)  # the player's main monitor

    def test_the_wanted_spot_when_it_is_free(self):
        self.assertEqual(
            hud.free_spot((400, 600), self.SCREEN, [(40, 300, 380, 60)], (2360, 480)), (2360, 480)
        )

    def test_moves_off_a_section_such_as_the_radar(self):
        radar = (2480, 864, 160, 160)
        x, y = hud.free_spot((400, 600), self.SCREEN, [radar], (2360, 480))
        self.assertEqual(hud._overlap((x, y, 400, 600), radar), 0)
        self.assertLess(abs(x - 2360) + abs(y - 480), 400)  # still near the middle

    def test_stays_on_the_screen_and_covers_least_when_nothing_is_free(self):
        everything = [(0, 0, 5120, 1440)]
        x, y = hud.free_spot((400, 600), (0, 0, 1920, 1080), everything, (760, 360))
        self.assertTrue(40 <= x <= 1920 - 40 - 400 and 40 <= y <= 1080 - 40 - 600)


class CentreTests(unittest.TestCase):
    SCREENS: ClassVar[list] = [(1280, -1440, 2560, 1440), (0, 0, 5120, 1440)]  # the player's two monitors

    def test_centre_across_down_or_both_on_its_own_screen(self):
        radar = (300, 900, 160, 160)
        screen = hud.screen_of(radar, self.SCREENS)
        self.assertEqual(screen, (0, 0, 5120, 1440))
        self.assertEqual(hud.centred(radar, screen, horizontal=True), (2480, 900, 160, 160))
        self.assertEqual(hud.centred(radar, screen, vertical=True), (300, 640, 160, 160))
        self.assertEqual(hud.centred(radar, screen, True, True), (2480, 640, 160, 160))

    def test_on_the_upper_monitor(self):
        flag = (1500, -1300, 480, 24)
        screen = hud.screen_of(flag, self.SCREENS)
        self.assertEqual(hud.centred(flag, screen, horizontal=True), (2320, -1300, 480, 24))

    def test_only_the_drawings_have_centre_buttons(self):
        self.assertEqual({s.name for s in hud.RACE_SECTIONS if s.drawing}, {'blueflag', 'radar', 'trackmap'})
