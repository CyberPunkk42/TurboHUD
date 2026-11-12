"""The car classes clan tags name, and their colours in the lap times (asked for by the user on
2026-11-12). The cases A to I are those of the user's request."""

import dataclasses
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import class_registry as reg
from turbohud.core import race
from turbohud.core import settings as s
from turbohud.core.hud import hud_lines

PURPLE, BLUE, RED, GREEN, GOLD = '#805AD5', '#2586CC', '#D9514B', '#269B76', '#D6A238'


def driver(name, tag, start=0, car=''):
    laps = [tuple(start + i * 10_000 for i in range(4)), (start + 40_000,)]
    return dataclasses.replace(
        race.PlayerState(name, 0, 1, tuple(laps), False, False, False), tag=tag, car=car
    )


def drivers(*tags):
    return [driver(f'P{i}', tag, start=i * 100) for i, tag in enumerate(tags)]


def tags_shown(players, clan_tags=True):
    """{driver's name: (tag column, its colour)} in the lap times, with the registry's classes."""
    rows = race.lap_times_rows(players, clock=50_000, class_tags=reg.CLASS_TAGS, clan_tags=clan_tags)
    return {row.text.split('. ', 1)[1]: (row.tag, row.tag_color) for row in rows[1:]}


def multi_class(players):
    return bool(race.car_classes(players, reg.CLASS_TAGS))


class RegistryTests(unittest.TestCase):
    def test_every_code_is_one_of_a_kind_and_fits_a_clan_tag(self):
        self.assertEqual(len(reg.BY_TAG), len(reg.CLASSES))  # none the same in capitals
        self.assertTrue(all(0 < len(c.code) <= reg.MAX_CLASS_TAG for c in reg.CLASSES))
        self.assertTrue(all(c.category in reg.CATEGORIES for c in reg.CLASSES))

    def test_the_requested_codes_and_their_categories(self):
        self.assertEqual(reg.car_class('[GT3]').category, reg.GT)
        self.assertEqual(reg.car_class('LMP').category, reg.PROTOTYPE)
        self.assertEqual(reg.car_class('grt').code, 'GrT')  # shown as the registry writes it
        self.assertEqual(reg.car_class('GrT').category, reg.TOURING)
        self.assertEqual(reg.car_class('GT8').name, 'Toyota GT86')
        self.assertEqual(reg.car_class('MIN').category, reg.ONE_MAKE)
        self.assertEqual(reg.car_class('911').category, reg.ONE_MAKE)
        self.assertEqual(reg.car_class('LM2').category, reg.PROTOTYPE)  # LMP2 before
        self.assertEqual(reg.car_class('LDH').name, 'LMDh Prototype')
        self.assertEqual(reg.car_class('GLM').category, reg.GT)

    def test_the_long_forms_are_no_class_any_more(self):
        for gone in ('HYPER', 'LMDH', 'LMP1', 'LMP2', 'LMP3', 'GTLM'):
            self.assertNotIn(gone, reg.BY_TAG)
        self.assertNotIn('ABC', reg.BY_TAG)
        self.assertEqual(reg.car_class('ABC').category, reg.CUSTOM)  # only from the settings file's list

    def test_the_category_colours(self):
        self.assertEqual(
            [c.color for c in reg.CATEGORIES],
            [PURPLE, BLUE, RED, GREEN, '#D69635', '#BC6747', GOLD, '#7E879A'],
        )


class ColourTests(unittest.TestCase):
    def test_each_category_its_colour(self):
        self.assertEqual(reg.class_colors({'GT3', 'LMP'}), {'GT3': BLUE, 'LMP': PURPLE})

    def test_a_second_class_of_a_category_takes_the_next_free_colour(self):
        self.assertEqual(reg.class_colors({'LMP', 'GT3', 'GT4'}), {'LMP': PURPLE, 'GT3': BLUE, 'GT4': RED})
        # Formula's red is taken by F1, so GT4 takes the next: Touring's green.
        self.assertEqual(reg.class_colors({'GT3', 'GT4', 'F1'}), {'GT3': BLUE, 'GT4': GREEN, 'F1': RED})

    def test_the_registry_order_decides_who_keeps_the_colour(self):
        self.assertEqual(reg.class_colors({'GT4', 'GT3'})['GT3'], BLUE)  # GT3 is before GT4
        three = reg.class_colors({'GT2', 'GT3', 'GT4'})
        self.assertEqual(three['GT2'], BLUE)
        self.assertEqual(len(set(three.values())), 3)

    def test_more_classes_than_colours_reuse_their_own(self):
        many = [c.code.upper() for c in reg.CLASSES if c.category == reg.GT][:10]
        colours = reg.class_colors(many)
        self.assertEqual(len(set(colours.values())), len(reg.CATEGORIES))
        self.assertEqual(colours[many[-1]], BLUE)

    def test_paler_goes_towards_white(self):
        self.assertEqual(reg.paler('#000000'), '#808080')
        self.assertEqual(reg.paler('#ffffff'), '#ffffff')


class RequestedCaseTests(unittest.TestCase):
    """The user's cases A to I."""

    def test_a_ordinary_tags(self):
        players = drivers('ABC', 'XYZ', 'DOG')
        self.assertFalse(multi_class(players))
        self.assertEqual(set(tags_shown(players).values()), {('ABC', ''), ('XYZ', ''), ('DOG', '')})

    def test_b_one_class(self):
        players = drivers('GT3', 'GT3', 'GT3')
        self.assertFalse(multi_class(players))
        self.assertEqual(set(tags_shown(players).values()), {('GT3', '')})  # as a plain tag

    def test_c_two_classes(self):
        shown = tags_shown(drivers('[GT3]', '[LMP]', 'GT3'))
        self.assertEqual(shown, {'P0': ('[GT3]', BLUE), 'P1': ('[LMP]', PURPLE), 'P2': ('GT3', BLUE)})

    def test_d_one_category_three_classes(self):
        players = drivers('GT2', 'GT3', 'GT4')
        classes = race.car_classes(players, reg.CLASS_TAGS)
        self.assertEqual(sorted(classes.values()), ['GT2', 'GT3', 'GT4'])
        colours = [color for _tag, color in tags_shown(players).values()]
        self.assertEqual(colours[0], BLUE)
        self.assertEqual(len(set(colours)), 3)  # told apart, as the user asked

    def test_e_classes_and_a_team_tag(self):
        shown = tags_shown(drivers('GT3', 'LMP', 'ABC'))
        self.assertEqual(shown, {'P0': ('GT3', BLUE), 'P1': ('LMP', PURPLE), 'P2': ('ABC', '')})

    def test_f_mixed_case(self):
        shown = tags_shown(drivers('GrT', 'MIN'))
        self.assertEqual(shown, {'P0': ('GrT', GREEN), 'P1': ('MIN', GOLD)})
        rows = race.lap_times_rows(drivers('grt', 'MIN'), clock=50_000, class_tags=reg.CLASS_TAGS)
        self.assertEqual({row.rule for row in rows} - {''}, {'GrT', 'MIN'})  # labelled as registered

    def test_g_back_to_ordinary_tags(self):
        self.assertTrue(multi_class(drivers('GT3', 'LMP')))
        later = drivers('ABC', 'XYZ')
        self.assertFalse(multi_class(later))
        self.assertEqual(tags_shown(later), {'P0': ('ABC', ''), 'P1': ('XYZ', '')})
        rows = race.lap_times_rows(later, clock=50_000, class_tags=reg.CLASS_TAGS, clan_tags=True)
        self.assertEqual({(row.rule, row.rule_color) for row in rows}, {('', '')})

    def test_h_unregistered(self):
        players = drivers('XYZ', 'QQQ', '123')
        self.assertFalse(multi_class(players))
        self.assertEqual({color for _tag, color in tags_shown(players).values()}, {''})

    def test_i_short_codes(self):
        self.assertEqual(tags_shown(drivers('F1', 'F2'))['P0'], ('F1', RED))
        self.assertTrue(multi_class(drivers('F1', 'F2')))


class LapTimesTests(unittest.TestCase):
    def test_a_class_from_the_car_is_paler_and_named_by_the_registry(self):
        players = [
            driver('Tagged', 'GT3', car='Porsche'),
            driver('Untagged', '', start=100, car='Porsche'),
            driver('Proto', 'LMP', start=200, car='Ligier'),
        ]
        shown = tags_shown(players)
        self.assertEqual(shown['Tagged'], ('GT3', BLUE))
        self.assertEqual(shown['Untagged'], ('GT3', reg.paler(BLUE)))

    def test_each_class_line_in_its_colour(self):
        rows = race.lap_times_rows(drivers('GT3', 'LMP', 'FTR'), clock=50_000, class_tags=reg.CLASS_TAGS)
        ruled = {row.rule: row.rule_color for row in rows if row.rule}
        self.assertEqual(ruled, {'LMP': PURPLE, 'GT3': BLUE, race.OTHER_CLASS: ''})
        lines = hud_lines(rows)
        self.assertEqual([line.tag_color for line in lines], [row.tag_color for row in rows])
        self.assertEqual([line.rule_color for line in lines], [row.rule_color for row in rows])

    def test_a_tag_that_cannot_be_read_is_no_class(self):
        players = drivers('GT3', 'LMP', None)
        self.assertEqual(tags_shown(players)['P2'], ('', ''))


class SettingsTests(unittest.TestCase):
    def test_a_file_with_the_old_default_list_reads_the_registry(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text(json.dumps({'class_tags': list(s.OLD_CLASS_TAGS)}))
            self.assertEqual(s.load_settings(path).class_tags, reg.CLASS_TAGS)

    def test_the_list_is_saved_only_when_it_is_its_own(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            s.save_settings(path, s.Settings())
            self.assertNotIn('class_tags', json.loads(path.read_text()))
            s.save_settings(path, s.Settings(class_tags=('GT3', 'ABC')))
            self.assertEqual(json.loads(path.read_text())['class_tags'], ['GT3', 'ABC'])
            self.assertEqual(s.load_settings(path).class_tags, ('GT3', 'ABC'))


if __name__ == '__main__':
    unittest.main()
