"""Layout presets as files and fitting them to other screens (asked for by the user on 2026-11-13)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import hud, presets
from turbohud.core.settings import SectionPlace

SECTIONS = {section.name: section for section in hud.RACE_SECTIONS}
FOLDER = Path(__file__).resolve().parents[1] / 'assets' / 'presets'


def measure(text, size):
    return len(text) * size * 0.6


def ink(_text, size):
    return size * 0.7, size * 0.2


def place(x, y, width, height, font=None, **more):
    return SectionPlace(x, y, width, height, font=font, **more)


def boxes(places):
    return {name: (p.x, p.y, p.width, p.height) for name, p in places.items() if p.visible}


class FileTests(unittest.TestCase):
    def test_a_preset_file_round_trip_with_every_text_size_written_out(self):
        places = {'lap': place(10, 20, 300, 40, font=None), 'radar': place(900, 500, 240, 240)}
        data = presets.preset_data(places, (1920, 1080), 17)
        self.assertEqual(data['sections']['lap']['font'], 17)  # the global size, written out
        path = Path(tempfile.mkdtemp()) / 'mine.json'
        presets.save_file(path, places, (1920, 1080), 17)
        size, read = presets.load_file(path)
        self.assertEqual(size, (1920, 1080))
        self.assertEqual(read['lap'].font, 17)
        self.assertEqual((read['radar'].x, read['radar'].width), (900, 240))

    def test_what_is_not_a_preset_is_refused(self):
        self.assertIsNone(presets.read_preset({'format': 99, 'screen': [1920, 1080], 'sections': {}}))
        self.assertIsNone(presets.read_preset({'format': 1, 'screen': [0, 1080], 'sections': {'lap': {}}}))
        self.assertIsNone(presets.read_preset('text'))
        path = Path(tempfile.mkdtemp()) / 'broken.json'
        path.write_text('{ not json', encoding='utf-8')
        self.assertIsNone(presets.load_file(path))

    def test_moved_to_a_screen_and_back(self):
        places = {'lap': place(5130, 20, 300, 40)}
        screen = (5120, -100, 2560, 1440)
        on_it = presets.relative(places, screen)
        self.assertEqual((on_it['lap'].x, on_it['lap'].y), (10, 120))
        self.assertEqual(presets.absolute(on_it, screen), places)

    def test_the_shipped_presets_hold_nothing_but_the_layout(self):
        for size in presets.SCREENS:
            with self.subTest(size=size):
                data = json.loads((FOLDER / presets.file_name(size)).read_text(encoding='utf-8'))
                self.assertEqual(set(data), {'format', 'screen', 'sections'})
                self.assertEqual(tuple(data['screen']), size)
                self.assertTrue(set(data['sections']) <= set(SECTIONS))
                for entry in data['sections'].values():
                    self.assertTrue(
                        set(entry)
                        <= {
                            'x',
                            'y',
                            'width',
                            'height',
                            'visible',
                            'group',
                            'text_centred',
                            'tint',
                            'font',
                            'spacing',
                        }
                    )


class FitTests(unittest.TestCase):
    """The order kept: the sections scaled by the heights' ratio, the room between them shared."""

    WIDE = (5120, 1440)
    LAYOUT: ClassVar[
        dict
    ] = {  # a wide screen's layout: the lap times at the left, the speed in the middle, the time at the right
        'laptimes': place(0, 100, 800, 1300, font=18),
        'speed': place(2400, 1200, 300, 120, font=20),
        'radar': place(2450, 500, 240, 240),
        'localtime': place(4900, 1360, 200, 70, font=16),
    }

    def fitted(self, size):
        return presets.fit_layout(self.LAYOUT, self.WIDE, size, SECTIONS, measure, ink)

    def test_on_every_screen_inside_it_without_new_overlaps(self):
        for size in presets.SCREENS:
            with self.subTest(size=size):
                result = self.fitted(size)
                for name, (x, y, w, h) in boxes(result).items():
                    self.assertTrue(0 <= x and x + w <= size[0] and 0 <= y and y + h <= size[1], name)
                self.assertEqual(presets._overlaps(boxes(result)), set())

    def test_the_order_and_the_edges_are_kept(self):
        result = self.fitted((1920, 1080))
        self.assertEqual(result['laptimes'].x, 0)  # still at the left edge
        self.assertGreater(result['localtime'].x + result['localtime'].width, 1920 - 40)  # still at the right
        self.assertLess(result['laptimes'].x, result['speed'].x)
        self.assertLess(result['speed'].x, result['localtime'].x)
        self.assertLess(result['radar'].y, result['speed'].y)  # the radar still above the speed

    def test_text_scales_with_the_height_where_it_fits(self):
        result = self.fitted((3840, 2160))  # as wide a shape: 1.5 times as high
        self.assertEqual(result['speed'].font, 30)
        self.assertEqual(result['radar'].width, 360)

    def test_smaller_where_the_sections_would_not_fit_side_by_side(self):
        wide = {  # side by side across most of the wide screen: 3300 of 5120 covered
            'laptimes': place(0, 100, 800, 1300, font=18),
            'players': place(900, 1000, 1400, 300, font=16),
            'speed': place(2400, 1200, 300, 120, font=20),
            'trackmap': place(2800, 800, 800, 500),
        }
        result = presets.fit_layout(wide, self.WIDE, (1920, 1080), SECTIONS, measure, ink)
        self.assertLess(result['speed'].font, round(20 * 1080 / 1440))
        self.assertGreaterEqual(result['speed'].font, hud.FONT_SIZES[0])
        self.assertEqual(presets._overlaps(boxes(result)), set())

    def test_the_same_screen_keeps_the_layout(self):
        result = self.fitted(self.WIDE)
        for name in self.LAYOUT:
            self.assertLessEqual(abs(result[name].x - self.LAYOUT[name].x), 1, name)
            self.assertEqual(result[name].font, self.LAYOUT[name].font)


class DefaultTests(unittest.TestCase):
    def test_the_nearest_screen(self):
        shipped = list(presets.SCREENS)
        self.assertEqual(presets.nearest((2560, 1440), shipped), (2560, 1440))
        self.assertEqual(presets.nearest((3440, 1440), shipped), (2560, 1440))  # 21:9: nearer 16:9 than 32:9
        self.assertEqual(presets.nearest((3840, 1080), shipped), (5120, 1440))  # 32:9
        self.assertEqual(presets.nearest((1680, 1050), shipped), (2560, 1600))  # 16:10
        self.assertEqual(presets.nearest((1366, 768), shipped), (1920, 1080))
        self.assertIsNone(presets.nearest((1920, 1080), []))

    def test_a_default_for_every_screen(self):
        exact = presets.default_for((2560, 1440), FOLDER, SECTIONS, measure, ink)
        self.assertEqual(exact, presets.load_file(FOLDER / '2560x1440.json')[1])
        other = presets.default_for((1366, 768), FOLDER, SECTIONS, measure, ink)
        for name, (x, y, w, h) in boxes(other).items():
            self.assertTrue(x + w <= 1366 and y + h <= 768, name)


if __name__ == '__main__':
    unittest.main()
