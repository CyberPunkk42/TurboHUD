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

    def test_a_preset_file_keeps_the_standings_columns(self):
        places = {
            'laptimes': place(10, 20, 400, 300, columns=('lap', 'best')),
            'lap': place(10, 400, 300, 40),
        }
        path = Path(tempfile.mkdtemp()) / 'mine.json'
        presets.save_file(path, places, (1920, 1080), 17)
        _size, read = presets.load_file(path)
        self.assertEqual(read['laptimes'].columns, ('lap', 'best'))
        self.assertIsNone(read['lap'].columns)

    def test_nearby_cars_raised_to_the_standings_size_between_its_neighbours(self):
        sections = SECTIONS
        places = {
            'laptimes': place(0, 0, 400, 600, font=14),
            'delta': place(500, 800, 200, 30, font=14),  # stacked right above it
            'players': place(500, 830, 260, 90, font=8),
            'times': place(500, 920, 260, 30, font=14),  # right below it
            'radar': place(1500, 100, 200, 200),  # elsewhere
        }
        raised = presets.readable_nearby(
            places, (1920, 1080), sections, lambda t, s: len(t) * s * 0.6, lambda t, s: (0, s)
        )
        nearby = raised['players']
        self.assertEqual(nearby.font, 14)
        self.assertLessEqual(nearby.y + nearby.height, 920)  # never into the row below
        self.assertLessEqual(raised['delta'].y + raised['delta'].height, nearby.y + presets.STACKED)
        self.assertEqual(raised['radar'], places['radar'])
        self.assertEqual(raised['times'], places['times'])

    def test_nearby_cars_already_large_enough_stays(self):
        places = {'laptimes': place(0, 0, 400, 600, font=14), 'players': place(500, 830, 260, 90, font=16)}
        self.assertEqual(presets.readable_nearby(places, (1920, 1080), {}, None, None), places)

    def test_starting_presets_file_round_trip(self):
        kept = {
            1: {'laptimes': place(10, 20, 400, 300, font=20, columns=('flag',))},
            4: {'lap': place(5, 5, 300, 40, font=30)},
        }
        data = presets.starting_data(
            kept, (5120, 1440), 18, {1: 'Recording', 4: 'Race', 3: 'Gone'}, {'race': 4, 'special': 5}
        )
        path = Path(tempfile.mkdtemp()) / 'presets.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        size, read, names, auto = presets.read_starting(path)
        self.assertEqual((tuple(size), sorted(read)), ((5120, 1440), [1, 4]))
        self.assertEqual(read[1]['laptimes'].columns, ('flag',))
        self.assertEqual(names, {1: 'Recording', 4: 'Race'})  # only for presets it has
        self.assertEqual(auto, {'race': 4})
        path.write_text('{"presets": 3}', encoding='utf-8')
        self.assertIsNone(presets.read_starting(path))

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

    def test_nearby_cars_never_too_small(self):
        # A player found Nearby cars' text too small at 8 px (2026-11-15). The user's designs (2026-11-20)
        # have it a little smaller than the Standings', never below 10 px; the fitted ones as large.
        for size in presets.SCREENS:
            with self.subTest(size=size):
                sections = json.loads((FOLDER / presets.file_name(size)).read_text(encoding='utf-8'))[
                    'sections'
                ]
                self.assertGreaterEqual(sections['players']['font'], 10)

    def test_nearby_cars_is_made_for_its_short_list(self):
        # On by default since 2026-11-15: the shipped boxes as tall as its 4 rows (as Qt measures them,
        # within a few pixels of the offscreen font here).
        for size in presets.SCREENS:
            with self.subTest(size=size):
                sections = json.loads((FOLDER / presets.file_name(size)).read_text(encoding='utf-8'))[
                    'sections'
                ]
                players = sections['players']
                self.assertLess(players['height'], players['font'] * players['spacing'] * 2.2 * 4)

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
                            'columns',  # the Standings' (2026-11-20)
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
        self.assertEqual(
            exact, presets.on_screen(presets.load_file(FOLDER / '2560x1440.json')[1], (2560, 1440))
        )
        wide = presets.default_for((5120, 1440), FOLDER, SECTIONS, measure, ink)
        self.assertTrue(all(p.x >= 0 and p.y >= 0 for p in wide.values()))  # wholly on the screen
        other = presets.default_for((1366, 768), FOLDER, SECTIONS, measure, ink)
        for name, (x, y, w, h) in boxes(other).items():
            self.assertTrue(x + w <= 1366 and y + h <= 768, name)


class DefaultFilesTests(unittest.TestCase):
    """TurboHUD's own layouts in customization/display_presets (asked for by the user on 2026-11-15)."""

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp()) / 'customization' / 'display_presets'

    def test_every_shipped_layout_written_under_its_own_name(self):
        written = presets.default_files(self.folder, FOLDER)
        self.assertEqual(sorted(written), sorted(presets.default_name(size) for size in presets.SCREENS))
        self.assertIn('1920x1080 (TurboHUD default).json', written)
        for size in presets.SCREENS:
            copy = self.folder / presets.default_name(size)
            self.assertEqual(copy.read_bytes(), (FOLDER / presets.file_name(size)).read_bytes())
        self.assertTrue((self.folder / presets.CUSTOM_README).exists())

    def test_only_missing_or_older_ones_written_again(self):
        presets.default_files(self.folder, FOLDER)
        self.assertEqual(presets.default_files(self.folder, FOLDER), [])
        old = self.folder / presets.default_name((1920, 1080))
        old.write_text('{"an older version": 1}', encoding='utf-8')
        self.assertEqual(presets.default_files(self.folder, FOLDER), [old.name])
        self.assertEqual(old.read_bytes(), (FOLDER / '1920x1080.json').read_bytes())

    def test_the_players_own_files_never_touched(self):
        self.folder.mkdir(parents=True)
        own = self.folder / '1920x1080.json'
        presets.save_file(own, {'speed': SectionPlace(10, 20, 30, 40)}, (1920, 1080), 13)
        before = own.read_bytes()
        presets.default_files(self.folder, FOLDER)
        self.assertEqual(own.read_bytes(), before)

    def test_a_folder_that_cannot_be_made(self):
        blocker = Path(tempfile.mkdtemp()) / 'a file'
        blocker.write_text('x', encoding='utf-8')
        self.assertIsNone(presets.default_files(blocker / 'display_presets', FOLDER))

    def test_default_files_are_not_ones_own(self):
        presets.default_files(self.folder, FOLDER)
        self.assertIsNone(presets.custom_for((1920, 1080), self.folder))
        self.assertTrue(presets.is_default_file(self.folder / '2560x1440 (TurboHUD default).json'))
        self.assertFalse(presets.is_default_file(self.folder / '2560x1440.json'))

    def test_own_file_of_any_name_wins_over_them(self):
        presets.default_files(self.folder, FOLDER)
        own = {'speed': SectionPlace(10, 20, 30, 40)}
        presets.save_file(self.folder / 'zz mine.json', own, (1920, 1080), 13)
        _digest, found = presets.custom_for((1920, 1080), self.folder)
        self.assertEqual(found['speed'].x, 10)


if __name__ == '__main__':
    unittest.main()


class DesignScreenTests(unittest.TestCase):
    """The design screen: another screen size shown to scale in a frame (asked for by the user on
    2026-11-13), and back at full size."""

    MINE = (0, 0, 5120, 1440)

    def test_the_frame_fits_the_screen_in_the_middle(self):
        frame, scale = presets.design_frame((3840, 2160), self.MINE)
        self.assertAlmostEqual(scale, 1440 * presets.DESIGN_ROOM[1] / 2160)
        x, y, width, height = frame
        self.assertEqual((width, height), (round(3840 * scale), round(2160 * scale)))
        self.assertLessEqual(abs(x + width / 2 - 2560), 1)  # in the middle, to a pixel
        self.assertLessEqual(abs(y + height / 2 - 720), 1)
        _frame, full = presets.design_frame((1920, 1080), self.MINE)
        self.assertEqual(full, 1.0)  # fits at full size: not larger

    def test_the_own_screen_size_is_shown_at_full_size(self):
        """Reported by users on 2026-11-15: their own size came out at 88%."""
        screen = (0, 0, 2560, 1440)
        frame, scale = presets.design_frame((2560, 1440), screen)
        self.assertEqual(scale, 1.0)
        self.assertEqual(frame, screen)  # the whole screen
        frame, scale = presets.design_frame((2560, 1080), screen)  # fits, though wider than 94%
        self.assertEqual((scale, frame), (1.0, (0, 180, 2560, 1080)))
        _frame, scale = presets.design_frame((2560, 1441), screen)  # a pixel too tall: shrunk
        self.assertAlmostEqual(scale, 1440 * presets.DESIGN_ROOM[1] / 1441)

    def test_into_the_frame_and_back(self):
        size = (3840, 2160)
        frame, scale = presets.design_frame(size, self.MINE)
        places = {
            'lap': place(100, 50, 900, 80, font=26),
            'radar': place(1800, 1000, 360, 360),
            'localtime': place(3600, 2080, 240, 80, font=20),
        }
        shown = presets.into_frame(places, frame, scale)
        self.assertEqual(shown['lap'].font, round(26 * scale))
        self.assertTrue(frame[0] <= shown['radar'].x <= frame[0] + frame[2])
        back = presets.out_of_frame(shown, frame, scale, size)
        for name, original in places.items():
            self.assertLessEqual(abs(back[name].x - original.x), 2, name)
            self.assertLessEqual(abs(back[name].width - original.width), 2, name)
            if original.font:
                self.assertLessEqual(abs(back[name].font - original.font), 1, name)
        self.assertLessEqual(back['localtime'].x + back['localtime'].width, size[0])


class CustomFolderTests(unittest.TestCase):
    """customization/display_presets beside the app (asked for by the user on 2026-11-13)."""

    def test_app_folder(self):
        self.assertEqual(presets.app_folder(frozen=False, source='/src'), Path('/src'))
        exe = Path(tempfile.mkdtemp()) / 'TurboHUD' / 'TurboHUD.exe'
        self.assertEqual(presets.app_folder(frozen=True, executable=exe), exe.resolve().parent)
        mac = Path(tempfile.mkdtemp()) / 'TurboHUD.app' / 'Contents' / 'MacOS' / 'TurboHUD'
        self.assertEqual(presets.app_folder(frozen=True, executable=mac), mac.resolve().parents[3])

    def test_custom_folder_beside_the_app(self):
        start = Path(tempfile.mkdtemp())
        self.assertEqual(
            presets.custom_folder('/settings', start), start / 'customization' / 'display_presets'
        )

    def test_custom_folder_in_settings_where_not_writable(self):
        missing = Path(tempfile.mkdtemp()) / 'not there'
        self.assertEqual(
            presets.custom_folder('/settings', missing), Path('/settings') / presets.CUSTOM_FOLDER
        )

    def test_ready_folder_writes_its_read_me(self):
        folder = Path(tempfile.mkdtemp()) / 'customization' / 'display_presets'
        self.assertEqual(presets.ready_folder(folder), folder)
        self.assertIn('2560x1440.json', (folder / 'README.txt').read_text(encoding='utf-8'))

    def test_custom_for_exact_size_only(self):
        folder = Path(tempfile.mkdtemp())
        places = {'speed': SectionPlace(10, 20, 30, 40)}
        self.assertIsNone(presets.custom_for((1920, 1080), folder))
        presets.save_file(folder / 'mine.json', places, (1920, 1080), 13)
        presets.save_file(folder / '2560x1440.json', places, (2560, 1440), 13)
        (folder / 'broken.json').write_text('{', encoding='utf-8')
        digest, found = presets.custom_for((1920, 1080), folder)
        self.assertEqual(found['speed'].x, 10)
        self.assertEqual(len(digest), 64)
        self.assertIsNone(presets.custom_for((3840, 2160), folder))

    def test_layout_for_prefers_own(self):
        folder, shipped = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        presets.save_file(
            folder / '1920x1080.json', {'speed': SectionPlace(10, 20, 30, 40)}, (1920, 1080), 13
        )
        sections = {s.name: s for s in hud.RACE_SECTIONS}
        laid = presets.layout_for((1920, 1080), folder, shipped, sections, len, lambda _t, s: (s, 0))
        self.assertEqual(laid['speed'].x, 10)
        self.assertIsNone(
            presets.layout_for((1920, 1080), None, shipped, sections, len, lambda _t, s: (s, 0))
        )
