import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))

import window_count_probe as probe


class BoxesTests(unittest.TestCase):
    def test_the_boxes_are_turbohuds_sections_shown_or_not(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            sections = {
                'lap': {'x': 857, 'y': 40, 'width': 342, 'height': 47, 'visible': True},
                'current': {'x': -1, 'y': 1123, 'width': 286, 'height': 46, 'visible': False},
            }
            path.write_text(json.dumps({'sections': sections}), encoding='utf-8')
            self.assertEqual(probe.section_boxes(path), [(857, 40, 342, 47), (-1, 1123, 286, 46)])

    def test_without_the_file_a_grid_of_17(self):
        with tempfile.TemporaryDirectory() as folder:
            boxes = probe.section_boxes(Path(folder) / 'missing.json')
        self.assertEqual(len(boxes), 17)

    def test_a_broken_file_gives_the_grid_too(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text('{not json', encoding='utf-8')
            self.assertEqual(probe.section_boxes(path), probe.FALLBACK_BOXES)


class LayoutTests(unittest.TestCase):
    def test_the_one_window_holds_every_box(self):
        boxes = [(857, 40, 342, 47), (-1, 1123, 286, 46), (1706, 980, 348, 347)]
        self.assertEqual(probe.bounds(boxes), (-1, 40, 2055, 1287))

    def test_the_phases_run_from_nothing_through_both_kinds_to_nothing(self):
        plan = probe.phases(30.0, 45.0, 17)
        self.assertEqual([mode for _name, _seconds, mode in plan], [None, 'many', 'one', None])
        self.assertEqual(sum(seconds for _name, seconds, _mode in plan), 150.0)
        self.assertEqual(plan[1][0], '17 windows')

    def test_the_options(self):
        args = probe.parse_args(['--rest', '10', '--each', '20'])
        self.assertEqual((args.rest, args.each), (10.0, 20.0))
