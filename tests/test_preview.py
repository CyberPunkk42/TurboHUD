"""Move mode's preview race at Laguna Seca (turbohud.core.preview)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import preview, race
from turbohud.core.hud import CLOCK_SECTIONS, RACE_SECTIONS
from turbohud.core.trackmap import path_length

DRAWN = {'blueflag': 'blue', 'deltabar': 'deltaview', 'radar': 'radar', 'trackmap': 'trackmap'}


def text(row):
    return ''.join(str(part or '') for part in (row.text, row.tail, row.middle, row.right))


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.sections = preview.preview_sections()

    def test_every_section_has_something_to_show(self):
        for section in RACE_SECTIONS:
            if section in CLOCK_SECTIONS:
                continue
            with self.subTest(section=section.name):
                key = DRAWN.get(section.name, section.name)
                self.assertTrue(self.sections.get(key), key)

    def test_lap_ten_of_fifteen_in_sixth_place(self):
        # 15 laps or 21 minutes, as the real race; the leader has just begun lap 11.
        title = self.sections['lap'][0]
        self.assertRegex(title.text, r'^Lap 10/15  -  7:\d\d left$')
        self.assertEqual(title.tail.strip(' ·'), 'Leader 11')
        rows = self.sections['laptimes']
        self.assertEqual(len(rows), 1 + len(preview.RESULTS))  # a heading and 20 drivers
        self.assertIn('6. You', rows[1 + preview.LOCAL].text)

    def test_the_real_races_best_laps(self):
        rows = self.sections['laptimes'][1:]
        for index in range(3):
            best = race.format_time(round(preview.RESULTS[index][1] * race.UNITS_PER_SECOND))
            self.assertEqual(rows[index].middle, best)

    def test_only_made_up_names(self):
        names = set(preview.NAMES)
        for row in self.sections['laptimes'][1:] + self.sections['players']:
            shown = row.text.split('. ', 1)[1].removesuffix('…')  # cut short beside a pit time
            self.assertTrue(any(name.startswith(shown) for name in names), shown)
        self.assertEqual(len(names), len(preview.RESULTS))

    def test_every_kind_of_entry_the_standings_make_room_for(self):
        # So the columns' room is seen filled (asked for by the user on 2026-11-15).
        rows = {row.text.split('. ', 1)[1]: row for row in self.sections['laptimes'][1:]}
        pitted = rows[preview.NAMES[preview.PITTED]]
        self.assertEqual((pitted.middle, pitted.right), ('PIT 24.6s', '(8.20s)'))
        self.assertEqual(rows[preview.NAMES[preview.IN_PIT]].right, 'PIT')
        self.assertEqual(rows[preview.NAMES[preview.CUT]].right, 'CUT 2.4s')
        self.assertEqual(rows[preview.NAMES[preview.RETIRED]].right, race.DNF_TEXT)

    def test_a_car_close_by_shows_its_pit_times(self):
        tails = [row.tail for row in self.sections['players']]
        self.assertIn('  PIT 24.6s (8.20s)', tails)

    def test_with_classes_a_two_class_race(self):
        from turbohud.core.settings import Settings

        classed = preview.preview_sections(classes=True, class_tags=tuple(Settings().class_tags))
        rows = classed['laptimes'][1:]
        self.assertEqual([row.rule for row in rows if row.rule], ['GT3', 'GT4'])
        self.assertEqual(rows[-1].overall, 'P20')
        self.assertIn('GT3 P6', [row.tag for row in classed['players']])
        # Without GT3 and GT4 among the class tags: one class, as before.
        self.assertFalse(any(row.overall for row in preview.preview_sections(classes=True)['laptimes']))

    def test_cars_close_by(self):
        self.assertTrue(self.sections['radar'].blips)
        roles = {dot.role for dot in self.sections['trackmap'].dots}
        self.assertLessEqual({'me', 'leader', 'ahead', 'behind'}, roles)

    def test_the_players_options(self):
        without = preview.preview_sections(gear=False, clan_tags=False, columns=('flag', 'best'))
        self.assertEqual(len(without['speed']), 1)  # no gear row
        self.assertEqual(len(self.sections['speed']), 2)
        self.assertNotIn('APX', ''.join(text(row) for row in without['laptimes']))
        self.assertIn('APX', ''.join(row.tag or '' for row in self.sections['laptimes']))
        self.assertIn('mph', text(preview.preview_sections(speed_unit='mph')['speed'][-1]))

    def test_nearby_cars_short_list(self):
        # Since 2026-11-15: the leader, the car ahead, you and the car behind.
        self.assertEqual(len(preview.preview_sections(nearby_short=True)['players']), 4)
        self.assertEqual(len(self.sections['players']), 8)

    def test_the_track_is_laguna_seca_as_learnt(self):
        points, start = preview.track()
        self.assertGreater(len(points), 500)
        self.assertAlmostEqual(path_length(points), 3551, delta=5)  # metres
        self.assertLess(
            abs(points[0][0] - start[0][0]) + abs(points[0][1] - start[0][1]), 10
        )  # from the start line


if __name__ == '__main__':
    unittest.main()


class StandingsSectionTests(unittest.TestCase):
    """The standings' box follows the columns shown (asked for by the user on 2026-11-15)."""

    def setUp(self):
        from turbohud.core.hud import RACE_SECTIONS

        self.base = next(s for s in RACE_SECTIONS if s.name == 'laptimes')

    def width(self, section):
        from turbohud.core.hud import content_size

        return content_size(section.samples[0], 1.0, lambda text, size: len(text) * size * 0.6)[0]

    def test_every_column_left_out_makes_it_narrower(self):
        everything = race.standings_section(self.base)
        self.assertEqual(self.width(everything), self.width(self.base))
        fewer = race.standings_section(self.base, ('flag', 'best', 'current'))
        fewest = race.standings_section(self.base, ('flag', 'current'))
        self.assertLess(self.width(fewer), self.width(everything))
        self.assertLess(self.width(fewest), self.width(fewer))

    def test_tags_and_the_overall_place_go_with_their_options(self):
        rows = race.standings_section(self.base, classes=False).samples[0]
        self.assertTrue(all(not row.overall for row in rows))
        self.assertTrue(any(row.tag for row in rows))  # the clan tags still show
        rows = race.standings_section(self.base, clan_tags=False, classes=False).samples[0]
        self.assertTrue(all(not row.tag for row in rows))
        rows = race.standings_section(self.base, clan_tags=False, classes=True).samples[0]
        self.assertTrue(any(row.tag for row in rows))  # in a race with classes, the class goes there


class NameFieldTests(unittest.TestCase):
    """The standings' names as long as the nearby cars' (asked for by the user on 2026-11-15)."""

    def test_eighteen_letters_in_both(self):
        from turbohud.core.hud import RACE_SECTIONS

        self.assertEqual(race.LAP_NAME_SHOWN, race.MAX_NAME_SHOWN)
        self.assertEqual(race.LAP_NAME_SHOWN, 18)
        sample = next(s for s in RACE_SECTIONS if s.name == 'laptimes').samples[0][1]
        self.assertEqual(len(sample.text.split('. ', 1)[1]), race.LAP_NAME_SHOWN)

    def test_the_standings_box_is_never_wider_than_its_columns(self):
        from turbohud.core.hud import RACE_SECTIONS, text_box

        laptimes = next(s for s in RACE_SECTIONS if s.name == 'laptimes')
        players = next(s for s in RACE_SECTIONS if s.name == 'players')

        def measure(text, size):
            return len(text) * size * 0.6

        def ink(_text, size):
            return size * 0.7, 0

        exact = text_box(laptimes, (0, 0, 10, 10), 13, measure, ink, False)[2]
        self.assertEqual(text_box(laptimes, (0, 0, 2000, 10), 13, measure, ink)[2], exact)
        self.assertEqual(text_box(players, (0, 0, 2000, 10), 13, measure, ink)[2], 2000)  # room kept there


class StandingsColumnsTests(unittest.TestCase):
    """Every column but the place and the name can be turned off; the gap to the leader; the class
    lines without the class column (asked for by the user on 2026-11-15)."""

    def sections(self, columns=race.LAP_COLUMNS, classes=False):
        from turbohud.core.settings import Settings

        return preview.preview_sections(
            columns=columns, classes=classes, class_tags=tuple(Settings().class_tags)
        )

    def test_the_gap_to_the_leader(self):
        rows = self.sections()['laptimes']
        self.assertEqual(rows[0].lead, 'Gap')
        self.assertEqual(rows[1].lead, '')  # the leader
        self.assertRegex(rows[2].lead, r'^\+\d+\.\d{3}$')
        self.assertEqual(rows[-1].lead, '')  # out of the race
        self.assertFalse(any(row.lead for row in self.sections(columns=('best',))['laptimes']))

    def test_with_classes_the_gap_to_the_class_leader(self):
        rows = self.sections(classes=True)['laptimes'][1:]
        firsts = [row for row in rows if row.rule]
        self.assertEqual([row.lead for row in firsts], ['', ''])  # each class's leader

    def test_the_class_lines_stay_without_the_class_and_overall_columns(self):
        columns = tuple(c for c in race.LAP_COLUMNS if c not in ('class', 'overall'))
        rows = self.sections(columns, classes=True)['laptimes']
        self.assertEqual([row.rule for row in rows if row.rule], ['GT3', 'GT4'])
        self.assertFalse(any(row.tag or row.overall for row in rows))

    def test_with_every_column_off_the_place_and_the_name_stay(self):
        rows = self.sections(columns=())['laptimes'][1:]
        self.assertTrue(all(row.text.strip()[0].isdigit() and '. ' in row.text for row in rows))
        self.assertFalse(
            any(row.middle or row.right or row.before or row.lead or row.tyre or row.flag for row in rows)
        )


class DraftPreviewTests(unittest.TestCase):
    def test_someone_drafts_you_in_the_big_row(self):
        rows = preview.preview_sections()['draft']
        self.assertEqual(len(rows), 3)
        self.assertIn(' drafts you ', rows[1].text)
        self.assertEqual(rows[1].style, 'medium')


class RadarPreviewTests(unittest.TestCase):
    """Every kind of thing the radar shows, in move mode (asked for by the user on 2026-11-15)."""

    def test_every_kind_on_it(self):
        view = preview.preview_radar(classes=True, cone=True)
        seconds = [blip.seconds for blip in view.blips]
        self.assertIn(0.0, seconds)  # beside: red
        self.assertTrue(any(s is not None and race.RADAR_FULL < s <= view.within for s in seconds))  # yellow
        self.assertTrue(any(s is None for s in seconds))  # not counting: grey
        self.assertTrue(any(blip.in_cone for blip in view.blips))  # its slipstream, the player in it
        self.assertTrue(any(abs(blip.ahead) > view.view for blip in view.blips))  # an arrow at the edge
        self.assertTrue(any(blip.class_color for blip in view.blips))  # another class
        self.assertEqual(view.cone, (30.0, 20.0))

    def test_it_follows_the_options(self):
        view = preview.preview_radar(classes=False, cone=False)
        self.assertIsNone(view.cone)
        self.assertFalse(any(blip.in_cone is not None or blip.class_color for blip in view.blips))
        self.assertIs(preview.preview_sections()['radar'], preview.preview_sections()['radar'])
