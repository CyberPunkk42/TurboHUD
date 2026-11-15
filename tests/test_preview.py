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
        self.assertEqual(self.sections['lap'][0].text, 'Lap 10/15')
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
            shown = row.text.split('. ', 1)[1]
            self.assertIn(shown, names)
        self.assertEqual(len(names), len(preview.RESULTS))

    def test_one_car_in_the_pits_and_cars_close_by(self):
        rows = self.sections['laptimes'][1:]
        self.assertEqual(sum('PIT' in text(row) for row in rows), 1)
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

    def test_the_track_is_laguna_seca_as_learnt(self):
        points, start = preview.track()
        self.assertGreater(len(points), 500)
        self.assertAlmostEqual(path_length(points), 3551, delta=5)  # metres
        self.assertLess(
            abs(points[0][0] - start[0][0]) + abs(points[0][1] - start[0][1]), 10
        )  # from the start line


if __name__ == '__main__':
    unittest.main()
