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

    def test_the_phases_run_from_nothing_through_the_three_kinds_to_nothing(self):
        # Since 2026-11-15 also one window per screen, as TurboHUD locked on the Mac.
        plan = probe.phases(30.0, 45.0, 17)
        self.assertEqual([mode for _name, _seconds, mode in plan], [None, 'many', 'one', 'screen', None])
        self.assertEqual(sum(seconds for _name, seconds, _mode in plan), 195.0)
        self.assertEqual(plan[1][0], '17 windows')

    def test_one_window_per_screen_that_has_boxes(self):
        left, right, unused = (0, 0, 1920, 1080), (1920, 0, 2560, 1440), (0, 1080, 1920, 1080)
        boxes = [(10, 10, 300, 40), (2000, 50, 300, 40), (1900, 500, 100, 40), (-500, -500, 50, 50)]
        held = probe.screens_with_boxes([left, right, unused], boxes)
        # A box goes by its middle (1950: the right screen); one on no screen to the first.
        self.assertEqual(
            held,
            [
                (left, [(10, 10, 300, 40), (-500, -500, 50, 50)]),
                (right, [(2000, 50, 300, 40), (1900, 500, 100, 40)]),
            ],
        )
        self.assertEqual(probe.screens_with_boxes([], boxes), [])

    def test_it_reads_turbohuds_settings_on_every_system(self):
        # Since 2026-11-15 on Windows and Linux too, not only the Mac's folder.
        from turbohud.core.settings import SETTINGS_FILE, settings_dir

        self.assertEqual(probe.SETTINGS, settings_dir() / SETTINGS_FILE)
        self.assertEqual(probe.parse_args([]).settings, probe.SETTINGS)
        for platform in ('darwin', 'win32', 'linux'):
            self.assertIn(platform, probe.FPS_COUNTERS)

    def test_the_options(self):
        args = probe.parse_args(['--rest', '10', '--each', '20'])
        self.assertEqual((args.rest, args.each), (10.0, 20.0))
