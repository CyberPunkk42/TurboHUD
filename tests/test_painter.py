import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class TextPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_overlapping_parts_of_a_letter_are_filled(self):
        # A plus is two overlapping bars in many fonts; filled odd-even, its centre was
        # a hole, which is what made letters such as the 4 look broken.
        from turbohud.hud.painter import text_path

        path = text_path('+', 80)
        self.assertTrue(path.contains(path.boundingRect().center()))

    def test_paths_are_reused(self):
        from turbohud.hud.painter import text_path

        self.assertIs(text_path('0:44', 40), text_path('0:44', 40))

    def test_outlines_are_kept_and_go_round_the_text(self):
        from turbohud.hud.painter import outline_path, text_path

        outline = outline_path('0:44', 40)
        self.assertIs(outline, outline_path('0:44', 40))
        # The outline reaches a little beyond the letters on every side.
        self.assertTrue(outline.boundingRect().contains(text_path('0:44', 40).boundingRect()))

    def test_measures_are_kept_and_the_same_as_qt_s(self):
        # The lap times and the player list measure their columns every frame: asking Qt
        # each time took most of their drawing (2026-11-12).
        from PySide6.QtGui import QFontMetricsF

        from turbohud.hud.painter import cap_height, hud_font, text_advance, text_ink, text_path, text_width

        metrics = QFontMetricsF(hud_font(17))
        self.assertEqual(text_advance('+00.000', 17), metrics.horizontalAdvance('+00.000'))
        self.assertEqual(cap_height(17), metrics.capHeight())
        box = text_path('L12', 17).boundingRect()
        self.assertEqual(text_width('L12', 17), box.right() + 17 / 7)
        self.assertAlmostEqual(text_ink('L12', 17)[0], -box.top() + 17 / 14)
        hits = text_advance.cache_info().hits
        text_advance('+00.000', 17)
        self.assertEqual(text_advance.cache_info().hits, hits + 1)


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class OutlineTests(unittest.TestCase):
    def test_the_outline_is_thick_enough_to_read_without_the_tint(self):
        from turbohud.hud.painter import outline_width

        self.assertEqual(outline_width(70), 10.0)

    def test_small_text_keeps_a_thin_outline_that_leaves_its_letters_open(self):
        from turbohud.hud.painter import outline_width

        self.assertEqual(outline_width(5), 1.2)
        self.assertAlmostEqual(outline_width(10), 10 / 7)
        self.assertLess(outline_width(13), 2.0)
        self.assertLess(outline_width(15), 2.2)


class TextImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_a_text_is_filled_once_and_then_copied(self):
        from turbohud.hud.painter import text_image

        first = text_image('1:23.4', 40, 0xFFFFFFFF, 0xC8000000, 1.0)
        self.assertIs(text_image('1:23.4', 40, 0xFFFFFFFF, 0xC8000000, 1.0), first)
        self.assertIsNot(text_image('1:23.4', 40, 0xFFFF0000, 0xC8000000, 1.0), first)
        self.assertIsNot(text_image('1:23.4', 40, 0xFFFFFFFF, 0xC8000000, 2.0), first)

    def test_large_images_cannot_fill_the_memory(self):
        from turbohud.hud import painter

        limit = painter.IMAGES_LIMIT
        self.addCleanup(setattr, painter, 'IMAGES_LIMIT', limit)
        painter.IMAGES_LIMIT = 200 * 1024
        first = painter.text_image('oldest', 60, 0xFFFFFFFF, 0xC8000000, 2.0)
        for number in range(40):
            painter.text_image(f'{number:04d}', 60, 0xFFFFFFFF, 0xC8000000, 2.0)
        self.assertLessEqual(painter._images_size, 200 * 1024 + 500 * 1024)
        self.assertEqual(
            painter._images_size, sum(entry[0].sizeInBytes() for entry in painter._images.values())
        )
        self.assertIsNot(painter.text_image('oldest', 60, 0xFFFFFFFF, 0xC8000000, 2.0), first)


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class ComposedTextTests(unittest.TestCase):
    """Running times and gaps put together from glyph images, each filled once (the tester's
    stutter, 2026-11-12: about 0.9 ms a new text at 2x, 17 new texts a frame)."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def placed(found, ratio):
        """{device pixel from the text's start: (r, g, b, a)}, as outlined_text places the image."""
        image, left, top = found
        x0, y0 = round(left * ratio), round(top * ratio)
        pixels = {}
        for y in range(image.height()):
            for x in range(image.width()):
                color = image.pixelColor(x, y)
                if color.alpha():
                    pixels[(x0 + x, y0 + y)] = color.getRgb()
        return pixels

    def differences(self, text, size, ratio):
        from turbohud.hud.painter import _filled_image, composed_image

        filled = self.placed(_filled_image(text, size, 0xFFFFFFFF, 0xC8000000, ratio), ratio)
        composed = self.placed(composed_image(text, size, 0xFFFFFFFF, 0xC8000000, ratio), ratio)
        blank = (0, 0, 0, 0)
        return [
            max(abs(a - b) for a, b in zip(filled.get(at, blank), composed.get(at, blank)))
            for at in set(filled) | set(composed)
        ]

    def test_numbers_are_composed_and_names_are_filled(self):
        from turbohud.hud.painter import composable

        for text in ('1:23.456', '+0.123', '−0.250', '(12.03s)', 'PIT 24.5s', 'CUT 3.0s', 'L12', '+2 L'):
            self.assertTrue(composable(text), text)
        for text in ('Driver01', 'Lap 12/30', 'GT3 P12', ''):
            self.assertFalse(composable(text), text)

    def test_a_composed_number_looks_as_a_filled_one(self):
        # The same places and shapes: only a few edge pixels a little lighter or darker. A
        # colon on its own sits lower than between digits; drawn so, it was off by 255.
        for ratio in (1.0, 2.0):
            for text in ('1:23.456', '+0.123', '(23.45s)', 'PIT 12.3s', '−0.250'):
                for size in (13, 20):
                    differences = self.differences(text, size, ratio)
                    self.assertLess(max(differences), 80, (text, size, ratio))
                    off = sum(d > 8 for d in differences)
                    self.assertLess(off, len(differences) * 0.05, (text, size, ratio))

    def test_without_fonts_a_number_is_filled_whole(self):
        # Qt's offscreen platform on Windows has no fonts unless given a folder, and its fallback
        # font's glyphs crashed Python when composed (2026-11-12): such texts are filled instead.
        from unittest import mock

        from turbohud.hud import painter

        with (
            mock.patch.object(painter, 'have_fonts', return_value=False),
            mock.patch.object(painter, 'composed_image', side_effect=AssertionError('composed')),
        ):
            image, _left, _top = painter.text_image('9:87.654', 19, 0xFFFFFFFF, 0xC8000000, 1.0)
        self.assertGreater(image.width(), 0)
        self.assertTrue(painter.have_fonts())  # these tests give Qt the system's fonts

    def test_glyphs_are_kept_so_a_new_number_fills_nothing(self):
        from turbohud.hud import painter

        painter.text_image('0:12.345', 17, 0xFFFFFFFF, 0xC8000000, 2.0)
        kept = len(painter._pieces)
        for number in range(30):
            painter.text_image(f'0:12.{number:03d}', 17, 0xFFFFFFFF, 0xC8000000, 2.0)
        # Only glyphs at places within a device pixel not seen yet: far fewer than 30 texts' worth.
        self.assertLess(len(painter._pieces) - kept, 30)

    def test_glyph_images_cannot_fill_the_memory(self):
        from turbohud.hud import painter

        limit = painter.PIECES_LIMIT
        self.addCleanup(setattr, painter, 'PIECES_LIMIT', limit)
        painter.PIECES_LIMIT = 100 * 1024
        for size in range(30, 60):
            painter.composed_image('0123456789', size, 0xFFFFFFFF, 0xC8000000, 2.0)
        self.assertLessEqual(painter._pieces_size, 100 * 1024 + 60 * 1024)
        self.assertEqual(
            painter._pieces_size, sum(found[0].sizeInBytes() for found in painter._pieces.values() if found)
        )

    def test_it_holds_the_whole_text_and_its_outline_for_the_screen(self):
        from turbohud.hud.painter import outline_path, text_image

        image, left, top = text_image('Fuel', 20, 0xFFFFFFFF, 0xC8000000, 2.0)
        self.assertEqual(image.devicePixelRatio(), 2.0)
        box = outline_path('Fuel', 20).boundingRect()
        self.assertLessEqual(left, box.left())
        self.assertLessEqual(top, box.top())
        self.assertGreaterEqual(left + image.width() / 2, box.right())
        self.assertGreaterEqual(top + image.height() / 2, box.bottom())

    def draw(self, draw_it, ratio=1.0):
        from PySide6.QtGui import QImage, QPainter

        image = QImage(round(300 * ratio), round(60 * ratio), QImage.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(ratio)
        image.fill(0)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        draw_it(painter)
        painter.end()
        return image

    def test_it_looks_as_filling_the_shapes_did(self):
        from PySide6.QtGui import QColor

        from turbohud.hud.painter import outline_path, outlined_text, text_path

        white, dark = QColor('#ffffff'), QColor(0, 0, 0, 200)

        def by_shapes(painter):
            painter.translate(10, 40)
            painter.fillPath(outline_path('Lap 3/13', 24), dark)
            painter.fillPath(text_path('Lap 3/13', 24), white)

        for ratio in (1.0, 2.0):
            with self.subTest(ratio=ratio):
                shapes = self.draw(by_shapes, ratio)
                copied = self.draw(lambda p: outlined_text(p, 10, 40, 'Lap 3/13', 24, white, dark), ratio)
                differ = 0
                for x in range(shapes.width()):
                    for y in range(shapes.height()):
                        one, two = shapes.pixelColor(x, y), copied.pixelColor(x, y)
                        if max(abs(a - b) for a, b in zip(one.getRgb(), two.getRgb())) > 12:
                            differ += 1
                self.assertLess(differ, 8)


class RedrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_the_radar_has_no_fill_behind_it(self):
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.race import Blip, RadarView
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        window = SectionWindow(Native(), Theme(), next(s for s in RACE_SECTIONS if s.name == 'radar'))
        self.addCleanup(window.close)
        window.resize(200, 200)
        window.show_content([], radar=RadarView(1.0, (Blip(10.0, 0.0, 0.0, 0.3),)))
        image = window.grab().toImage()
        self.assertEqual(image.pixelColor(40, 40).alpha(), 0)  # away from the lines and the cars
        self.assertGreater(image.pixelColor(100, 100).alpha(), 0)  # the local car, in the middle

    def test_a_car_past_the_radars_edge_is_an_arrow_there(self):
        # Asked for by the user on 2026-11-11: the radar no longer zooms out to fit a far car.
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.race import RADAR_VIEW_MAX, Blip, RadarView
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        window = SectionWindow(Native(), Theme(), next(s for s in RACE_SECTIONS if s.name == 'radar'))
        self.addCleanup(window.close)
        window.resize(200, 200)

        def shown(ahead, rows):
            view = RadarView(1.0, (Blip(ahead, 0.0, 0.0, 0.2),), RADAR_VIEW_MAX, within=1.0)
            window.show_content([], radar=view)
            image = window.grab().toImage()
            return sum(image.pixelColor(x, y).alpha() > 0 for x in range(85, 116) for y in rows)

        top, bottom = range(3, 14), range(186, 197)
        none = shown(0.0, bottom)  # a car on the local one: what the bottom edge shows anyway
        self.assertGreater(shown(-RADAR_VIEW_MAX * 2, bottom), none + 20)  # far behind: an arrow there
        # Far ahead: no arrow at the top edge (asked for by the user on 2026-11-13).
        self.assertEqual(shown(RADAR_VIEW_MAX * 2, top), shown(0.0, top))

    def test_a_car_of_another_class_is_its_class_colour_with_the_warning_round_it(self):
        # Asked for by the user on 2026-11-11.
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.race import RADAR_CLASS_COLORS, Blip, RadarView
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        window = SectionWindow(Native(), Theme(), next(s for s in RACE_SECTIONS if s.name == 'radar'))
        self.addCleanup(window.close)
        window.resize(200, 200)
        blue = RADAR_CLASS_COLORS[0]
        window.show_content([], radar=RadarView(1.0, (Blip(10.0, 0.0, 0.0, 0.3, None, blue),), within=1.0))
        image = window.grab().toImage()
        pixels = [image.pixelColor(x, y) for x in range(80, 121) for y in range(20, 80)]
        self.assertTrue(any(c.blue() > 200 and c.red() < 120 for c in pixels))  # the class colour
        self.assertTrue(
            any(c.red() > 200 and c.green() > 160 and c.blue() < 100 for c in pixels)
        )  # yellow warning

    def test_the_move_mode_sample_follows_the_cone_option(self):
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        window = SectionWindow(Native(), Theme(), next(s for s in RACE_SECTIONS if s.name == 'radar'))
        self.addCleanup(window.close)
        window.resize(200, 200)
        window.set_locked(False)

        with_cone = window.grab().toImage()
        window.radar_cone = False
        without = window.grab().toImage()
        self.assertNotEqual(with_cone, without)  # only the cone differs between them
        window.radar_cone = True
        self.assertEqual(window.grab().toImage(), with_cone)

    def test_the_delta_bar_fills_from_the_middle_towards_the_right_side(self):
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.race import DeltaBarView
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        window = SectionWindow(Native(), Theme(), next(s for s in RACE_SECTIONS if s.name == 'deltabar'))
        self.addCleanup(window.close)
        window.resize(400, 40)
        window.set_locked(True)
        self.assertTrue(window.show_content([], delta_view=DeltaBarView(0.5, -1.0, '')))
        image = window.grab().toImage()
        green = image.pixelColor(280, 20)
        self.assertGreater(green.green(), green.red())  # ahead and gaining: on the right, green
        self.assertLess(image.pixelColor(100, 20).alpha(), 200)  # the left stays the dark track
        window.show_content([], delta_view=DeltaBarView(-0.5, 1.0, ''))
        image = window.grab().toImage()
        red = image.pixelColor(120, 20)
        self.assertGreater(red.red(), red.green())  # behind and losing: on the left, red
        self.assertLess(
            max(red.red(), red.green(), red.blue()), 230
        )  # never near white: the text reads on it
        window.show_content([], delta_view=DeltaBarView(-1.0, 1.0, ''))
        image = window.grab().toImage()
        self.assertEqual(image.pixelColor(3, 3).alpha(), 0)  # round ends, even filled to the end
        self.assertGreater(image.pixelColor(20, 20).red(), 150)  # but filled inside them
        window.show_content([])
        self.assertEqual(window.grab().toImage().pixelColor(200, 20).alpha(), 0)  # no delta, no bar

    def test_the_delta_bar_colour_fades_from_green_to_red_through_yellow(self):
        from PySide6.QtGui import QColor

        from turbohud.hud.painter import AHEAD_COLOR, BEHIND_COLOR, delta_bar_color

        self.assertEqual(delta_bar_color(-1.0), AHEAD_COLOR)
        self.assertEqual(delta_bar_color(1.0), BEHIND_COLOR)
        half = QColor(delta_bar_color(0.0))
        self.assertGreater(min(half.red(), half.green()), 150)  # yellowish on the way, never white
        self.assertLess(half.blue(), 150)

    def test_the_radar_has_an_outline_only_in_move_mode(self):
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.race import Blip, RadarView
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        window = SectionWindow(Native(), Theme(), next(s for s in RACE_SECTIONS if s.name == 'radar'))
        self.addCleanup(window.close)
        window.resize(200, 200)
        window.show_content([], radar=RadarView(1.0, (Blip(10.0, 0.0, 0.0, 0.3),)))
        window.locked = True
        image = window.grab().toImage()
        self.assertEqual(image.pixelColor(40, 1).alpha(), 0)  # on the top edge, away from the lines
        self.assertEqual(image.pixelColor(1, 40).alpha(), 0)  # on the left edge
        self.assertGreater(image.pixelColor(100, 100).alpha(), 0)  # the cars still show
        window.locked = False
        image = window.grab().toImage()
        self.assertGreater(image.pixelColor(40, 1).alpha(), 0)
        self.assertGreater(image.pixelColor(1, 40).alpha(), 0)

    def test_a_section_is_drawn_again_only_when_its_content_changes(self):
        from turbohud.core.hud import RACE_SECTIONS, Row
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        window = SectionWindow(Native(), Theme(), RACE_SECTIONS[0])
        self.addCleanup(window.close)
        rows = [Row('Lap 1/3', 'title')]
        self.assertTrue(window.show_content(rows))
        self.assertFalse(window.show_content([Row('Lap 1/3', 'title')]))  # equal, not the same list
        self.assertTrue(window.show_content([Row('Lap 2/3', 'title')]))
        self.assertTrue(window.show_content(window.rows, level=(0.5, 'ahead')))
        self.assertEqual(window.level, (0.5, 'ahead'))

    def section_window(self, **native):
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        fake = Native()
        vars(fake).update(native)
        window = SectionWindow(fake, Theme(), RACE_SECTIONS[0])
        self.addCleanup(window.close)
        return window

    def test_a_hidden_section_keeps_its_content_but_needs_no_drawing(self):
        from turbohud.core.race import Row

        window = self.section_window()
        window.set_wanted(False)
        self.assertFalse(window.show_content([Row('Lap 1/3', 'title')]))
        self.assertEqual(window.rows, [Row('Lap 1/3', 'title')])
        window.set_wanted(True)
        self.assertEqual(window.rows, [Row('Lap 1/3', 'title')])  # what showing it draws
        self.assertTrue(window.show_content([Row('Lap 2/3', 'title')]))

    def test_where_the_system_says_so_a_hidden_section_leaves_the_screen(self):
        window = self.section_window(hides_windows=True)
        window.setGeometry(50, 60, 300, 80)
        window.show_on_top()
        window.set_wanted(False)
        self.assertFalse(window.isVisible())
        window.set_locked(False)  # move mode does not bring it back
        self.assertFalse(window.isVisible())
        window.set_locked(True)
        window.set_wanted(True)
        self.assertTrue(window.isVisible())
        self.assertEqual(window.size().toTuple(), (300, 80))
        self.assertEqual(window.pos().toTuple(), (50, 60))

    def test_elsewhere_a_hidden_section_keeps_its_window_on_the_screen(self):
        window = self.section_window()
        window.show_on_top()
        window.set_wanted(False)
        self.assertTrue(window.isVisible())

    def text_box(self, name, rows, size_share=1.0, height=None, centred=False, wider=1.0):
        """(left, top, right, bottom) of the bright pixels in a section at that share of
        its size, and the window's size: the text is white, the pedal bars are not, and
        text this small has hardly a pixel of its exact colour."""
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        section = next(section for section in RACE_SECTIONS if section.name == name)
        window = SectionWindow(Native(), Theme(), section)
        self.addCleanup(window.close)
        window.text_centred = centred
        window.resize(round(window.base[0] * wider), height or round(window.base[1] * size_share))
        window.show_content(rows)
        image = window.grab().toImage()
        found = [
            (x, y)
            for x in range(image.width())
            for y in range(image.height())
            # Bright and solid: white text, and coloured text (the yellow flag's) too.
            if max(image.pixelColor(x, y).getRgb()[:3]) >= 150 and image.pixelColor(x, y).alpha() >= 150
        ]
        xs, ys = [x for x, _y in found], [y for _x, y in found]
        return (min(xs), min(ys), max(xs), max(ys)), (image.width(), image.height())

    def test_the_speed_stays_centred_between_its_bars_when_shrunk(self):
        from turbohud.core.hud import Row

        for share in (1.0, 0.6, 0.35):
            with self.subTest(share=share):
                # Digits only: it centres on their height.
                (left, top, right, bottom), (width, height) = self.text_box(
                    'speed', [Row('000', 'medium')], share
                )
                self.assertLessEqual(abs(left - (width - 1 - right)), 3)
                self.assertLessEqual(abs(top - (height - 1 - bottom)), 3)

    def test_text_without_bars_keeps_to_the_left_when_shrunk(self):
        from turbohud.core.hud import MARGIN, Row

        (left, _top, _right, _bottom), _size = self.text_box('localtime', [Row('12:34', 'medium')], 0.5)
        self.assertLessEqual(left, MARGIN + 3)

    def test_centred_text_sits_in_the_middle_of_a_wide_box(self):
        from turbohud.core.hud import Row

        rows = [Row('00:00', 'medium')]
        (left, _top, right, _bottom), (width, _height) = self.text_box(
            'localtime', rows, centred=True, wider=4.0
        )
        self.assertLessEqual(abs(left - (width - 1 - right)), 4)
        (left, _top, _right, _bottom), _size = self.text_box('localtime', rows, wider=4.0)
        self.assertLessEqual(left, 18)  # without the option

    def test_digits_do_not_move_centred_text(self):
        from turbohud.core.hud import Row, hud_lines
        from turbohud.hud.painter import centred_x

        narrow, wide = (hud_lines([Row(text, 'medium')])[0] for text in ('11:11', '00:00'))
        self.assertEqual(centred_x(narrow, 400, 14), centred_x(wide, 400, 14))

    def test_text_stays_inside_narrow_boxes_at_any_size(self):
        from PySide6.QtGui import QColor

        from turbohud.core.hud import RACE_SECTIONS, Row
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        section = next(s for s in RACE_SECTIONS if s.name == 'times')
        rows = [Row('Last 0:48.442   Best 0:48.442', 'medium')]
        for width, height in ((120, 60), (160, 60), (200, 120), (240, 40), (284, 69), (391, 88)):
            with self.subTest(width=width, height=height):
                window = SectionWindow(Native(), Theme(), section)
                self.addCleanup(window.close)
                window.resize(width, height)
                window.show_content(rows)
                image = window.grab().toImage()
                # The window cuts the text off at its edge: look for ink in its last column.
                edge = [image.pixelColor(image.width() - 1, y) for y in range(image.height())]
                self.assertEqual([c for c in edge if c.alpha() > 0 and c != QColor(0, 0, 0, 0)], [])

    def drawn(self, name, rows, size, backdrop=False, locked=True):
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        window = SectionWindow(Native(), Theme(), next(s for s in RACE_SECTIONS if s.name == name))
        self.addCleanup(window.close)
        window.resize(*size)
        window.backdrop = backdrop
        window.locked = locked
        window.show_content(rows)
        return window.grab().toImage()

    def test_the_maps_tint_is_its_dark_square(self):
        from PySide6.QtGui import QColor

        from turbohud.overlay.window import MAP_BACK

        def corner(backdrop):
            image = self.drawn('trackmap', [], (240, 240), backdrop=backdrop, locked=False)
            return image.pixelColor(14, 14)

        self.assertGreater(corner(True).alpha(), 0)
        self.assertEqual(corner(True).alpha(), QColor(*MAP_BACK).alpha())
        self.assertEqual(corner(False).alpha(), 0)

    def test_the_maps_road_takes_a_fast_laps_colour(self):
        from dataclasses import replace

        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow, _sample_map

        class Native:
            def raise_window(self, window):
                return 'test'

        def purple_pixels(road):
            window = SectionWindow(Native(), Theme(), next(s for s in RACE_SECTIONS if s.name == 'trackmap'))
            self.addCleanup(window.close)
            window.resize(240, 240)
            window.show_content([], trackmap=replace(_sample_map(), road=road))
            image = window.grab().toImage()
            colours = (image.pixelColor(x, y) for x in range(0, 240, 2) for y in range(0, 240, 2))
            return sum(
                1 for c in colours if c.alpha() > 0 and c.red() > c.green() + 60 and c.blue() > c.green() + 60
            )

        self.assertGreater(purple_pixels('#c77dff'), 50)
        self.assertEqual(purple_pixels(''), 0)

    def map_window(self):
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        window = SectionWindow(Native(), Theme(), next(s for s in RACE_SECTIONS if s.name == 'trackmap'))
        self.addCleanup(window.close)
        window.resize(240, 240)
        return window

    def test_the_maps_road_is_drawn_once_while_only_the_cars_move(self):
        from dataclasses import replace

        from turbohud.core.trackmap import MapDot
        from turbohud.overlay.window import _sample_map

        window = self.map_window()
        sample = _sample_map()
        for step in range(5):
            dot = MapDot(sample.outline.points[step * 7], 'me')
            window.show_content([], trackmap=replace(sample, dots=(dot,)))
            window.grab()
        self.assertEqual(window.road_draws, 1)

    def test_my_own_dot_stays_on_top_and_its_yellow_ring_covers_no_car_below(self):
        # Asked for by the user on 2026-11-11: my dot a little smaller and on top, ringed in yellow
        # when I caused a flag.
        from dataclasses import replace

        from turbohud.core.trackmap import MapDot
        from turbohud.overlay.window import MAP_PADDING, MAP_SIZES, _sample_map, map_transform

        self.assertLess(MAP_SIZES['me'], MAP_SIZES['ahead'])
        window = self.map_window()
        sample = _sample_map()
        where = sample.outline.points[0]
        dots = (MapDot(where, 'ahead'), MapDot(where, 'me', yellow=True))
        window.show_content([], trackmap=replace(sample, dots=dots))
        image = window.grab().toImage()
        size = min(window.width(), window.height())
        scale, x_off, y_off = map_transform(sample.outline.bounds, (size, size), size * MAP_PADDING)
        left, top = (window.width() - size) / 2, (window.height() - size) / 2
        x, y = round(left + x_off + where[0] * scale), round(top + y_off - where[1] * scale)
        middle = image.pixelColor(x, y)
        self.assertGreater(middle.red(), 150)  # the red car below still shows in my ring's middle
        self.assertLess(middle.green(), 120)
        yellow = 0
        for dx in range(-14, 15):
            for dy in range(-14, 15):
                c = image.pixelColor(x + dx, y + dy)
                yellow += c.red() > 200 and c.green() > 180 and c.blue() < 80
        self.assertGreater(yellow, 10)  # the yellow ring round it

    def test_the_maps_road_is_drawn_again_when_what_it_shows_changes(self):
        from dataclasses import replace

        from turbohud.core.trackmap import outline_from_path
        from turbohud.overlay.window import _sample_map

        window = self.map_window()
        sample = _sample_map()
        window.show_content([], trackmap=sample)
        window.grab()
        changes = (
            ('size', lambda: window.resize(200, 200)),
            ('tint', lambda: setattr(window, 'backdrop', True)),
            ('road colour', lambda: window.show_content([], trackmap=replace(sample, road='#c77dff'))),
            (
                'track',
                lambda: window.show_content(
                    [],
                    trackmap=replace(sample, outline=outline_from_path([(0, 0), (50, 10), (90, 40)], False)),
                ),
            ),
        )
        for count, (what, change) in enumerate(changes, start=2):
            with self.subTest(what=what):
                change()
                window.grab()
                self.assertEqual(window.road_draws, count)

    def test_the_kept_road_shows_the_same_map(self):
        from turbohud.overlay.window import _sample_map

        window = self.map_window()
        window.backdrop = True
        window.show_content([], trackmap=_sample_map())
        first = window.grab().toImage()
        second = window.grab().toImage()
        self.assertEqual(window.road_draws, 1)
        self.assertEqual(first, second)
        road = [first.pixelColor(x, 120) for x in range(240)]
        self.assertTrue(
            any(c.alpha() > 200 and c.red() > 150 for c in road)
        )  # the light road crosses the middle row

    def test_sector_bars_turned_off_are_not_drawn(self):
        from turbohud.core.hud import RACE_SECTIONS, Row, Sectors
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        def purple_pixels(shown):
            window = SectionWindow(Native(), Theme(), next(s for s in RACE_SECTIONS if s.name == 'times'))
            self.addCleanup(window.close)
            window.resize(400, 60)
            window.sector_bars = shown
            window.show_content(
                [Row('Last 1:20.000   Best 1:19.000', 'medium')], level=Sectors(('#c77dff',) * 3)
            )
            image = window.grab().toImage()
            colours = (image.pixelColor(x, y) for x in range(0, 400, 2) for y in range(0, 60, 2))
            return sum(
                1 for c in colours if c.alpha() > 0 and c.red() > c.green() + 60 and c.blue() > c.green() + 60
            )

        self.assertGreater(purple_pixels(True), 20)
        self.assertEqual(purple_pixels(False), 0)

    def test_only_the_number_changes_and_the_label_stays(self):
        from turbohud.core.hud import Row

        def picture(number):
            row = Row(number, 'medium', 'ahead', tail=' vs best', tail_color='ahead', slot='+00.000')
            return self.drawn('delta', [row], (300, 40))

        first = picture('+1.111')
        # The label starts past the widest number, whatever the size the box gives.
        from turbohud.core.hud import MARGIN, RACE_SECTIONS, drawn_scale, hud_lines, tight_height
        from turbohud.hud.painter import text_advance, text_ink, text_width

        section = next(s for s in RACE_SECTIONS if s.name == 'delta')
        normal = tight_height(section, 1.0, text_ink)
        row = Row('+1.111', 'medium', tail=' vs best', slot='+00.000')
        scale = drawn_scale(section, (300, 40), [row], normal, 1.0, text_ink, text_width)
        size = hud_lines([row], scale)[0].size
        from_x = round(MARGIN * scale + text_advance('+00.000 ', size))  # past the space before it
        for number in ('+8.888', '\u22120.505', '+7.417', '+10.250', '\u221212.000', '0.000'):
            other = picture(number)
            with self.subTest(number=number):
                differ = sum(
                    first.pixelColor(x, y) != other.pixelColor(x, y)
                    for x in range(from_x, first.width())
                    for y in range(first.height())
                )
                self.assertEqual(differ, 0)
        self.assertNotEqual(first, picture('+8.888'))

    def test_digits_are_all_as_wide_in_the_hud_s_font(self):
        from PySide6.QtGui import QFontInfo

        from turbohud.hud.painter import hud_font, text_advance

        widths = {round(text_advance(digit, 40), 2) for digit in '0123456789'}
        if len(widths) > 1 and QFontInfo(hud_font(40)).family() != '.AppleSystemUIFont':
            self.skipTest('this font has no digits of one width')
        self.assertEqual(len(widths), 1)

    def test_a_running_number_keeps_its_height_on_screen(self):
        from turbohud.core.hud import Row

        def tall(text, style, name, size):
            image = self.drawn(name, [Row(text, style)], size)
            rows = [
                y
                for y in range(image.height())
                if any(image.pixelColor(x, y).alpha() > 40 for x in range(image.width()))
            ]
            return rows[-1] - rows[0]

        for name, style, first, second, size in (
            ('current', 'big', '1:11.1', '8:00.8', (210, 46)),
            ('delta', 'medium', '+1.111 vs best', '+8.800 vs best', (230, 26)),
        ):
            with self.subTest(section=name):
                # Within a pixel: round digits reach a little further than flat ones.
                self.assertAlmostEqual(
                    tall(first, style, name, size), tall(second, style, name, size), delta=1
                )

    def test_the_tint_does_not_follow_the_digits(self):
        from turbohud.core.hud import Row

        def tint_right(text):
            image = self.drawn('current', [Row(text, 'big')], (400, 46), backdrop=True)
            return max(x for x in range(image.width()) if image.pixelColor(x, 2).alpha() > 0)

        self.assertEqual(tint_right('1:11.1'), tint_right('8:88.8'))

    def test_each_line_is_centred_on_its_own(self):
        from turbohud.core.hud import Row

        rows = [Row('Draft 000%', 'medium'), Row('Another line of small text', 'small')]
        (left, _t, right, _b), (width, _h) = self.text_box('draft', rows, centred=True, wider=2.0)
        self.assertLessEqual(abs(left - (width - 1 - right)), 6)

    def test_the_speed_and_a_list_ignore_the_option(self):
        from turbohud.core.hud import Row

        rows = [Row('1. Somebody', 'small', right='+1.000')]
        self.assertEqual(self.text_box('players', rows, centred=True), self.text_box('players', rows))
        rows = [Row('000', 'medium')]
        self.assertEqual(self.text_box('speed', rows, centred=True), self.text_box('speed', rows))

    def test_a_full_lap_times_list_fits_its_box(self):
        from turbohud.core.hud import Row

        rows = [Row('Driver', 'small', 'accent', middle='Best', right='Lap')]
        rows += [
            Row(f'{n}. Driver', 'small', flag='DE', middle='0:00.000', right='0:00.0') for n in range(1, 21)
        ]
        (_left, top, _right, bottom), (_width, height) = self.text_box('laptimes', rows)
        self.assertGreaterEqual(top, 1)
        self.assertLessEqual(bottom, height - 2)

    def test_the_text_shrinks_with_the_box(self):
        from turbohud.core.hud import Row

        rows = [Row('12:34', 'medium')]

        def tall(share):
            # Wide enough for the height to set the size.
            (_left, top, _right, bottom), _size = self.text_box('localtime', rows, share, wider=3.0)
            return bottom - top

        self.assertGreater(tall(2.0), tall(1.0))
        self.assertLess(tall(0.7), tall(1.0))

    def test_every_text_section_fits_closely_in_its_box(self):
        from turbohud.core.hud import RACE_SECTIONS

        for section in RACE_SECTIONS:
            if section.bar or section.background:  # a bright box, not text: see the yellow flag's test
                continue
            for share in (1.0, 2.0, 0.6):
                with self.subTest(section=section.name, share=share):
                    (_left, top, _right, bottom), (_width, height) = self.text_box(
                        section.name, list(section.samples[0]), share
                    )
                    self.assertGreaterEqual(top, 1)
                    self.assertLessEqual(bottom, height - 2)


class YellowFlagLookTests(unittest.TestCase):
    """The yellow flag on a yellow box with dark text (asked for by the user on 2026-11-11)."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_a_yellow_box_behind_dark_text_only_while_there_is_a_flag(self):
        from turbohud.core import race
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        section = next(s for s in RACE_SECTIONS if s.name == 'yellowflag')
        window = SectionWindow(Native(), Theme(), section)
        self.addCleanup(window.close)
        window.resize(*window.base)
        window.set_locked(True)
        rows = race.yellow_rows((race.Incident('Someone', 'stopped', 0),), self._state())
        window.show_content(rows)
        image = window.grab().toImage()
        colours = [image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height())]
        yellow = [
            c for c in colours if c.alpha() > 200 and c.red() > 220 and c.green() > 180 and c.blue() < 80
        ]
        dark = [c for c in colours if c.alpha() > 200 and max(c.red(), c.green(), c.blue()) < 60]
        self.assertGreater(len(yellow), len(colours) // 10)  # a solid yellow box
        self.assertGreater(len(dark), 50)  # with dark text on it
        window.show_content([])
        self.assertEqual(
            window.grab().toImage().pixelColor(window.width() // 2, 10).alpha(), 0
        )  # no flag, no box

    def test_the_box_keeps_its_size_and_the_text_too_whatever_is_listed(self):
        # Reported by the user on 2026-11-11: the box grew and shrank with each incident.
        from turbohud.core import race
        from turbohud.core.hud import RACE_SECTIONS, drawn_scale, tight_height
        from turbohud.core.settings import Theme
        from turbohud.hud.painter import text_ink, text_width
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        section = next(s for s in RACE_SECTIONS if s.name == 'yellowflag')
        window = SectionWindow(Native(), Theme(), section)
        self.addCleanup(window.close)
        window.resize(*window.base)
        window.set_locked(True)

        def yellow_box(names, kind):
            rows = race.yellow_rows(tuple(race.Incident(n, kind, 0) for n in names), self._state())
            window.show_content(rows)
            image = window.grab().toImage()
            spots = [
                (x, y)
                for x in range(image.width())
                for y in range(image.height())
                if image.pixelColor(x, y).alpha() > 200
                and image.pixelColor(x, y).blue() < 80
                and image.pixelColor(x, y).red() > 220
            ]
            xs, ys = [x for x, _y in spots], [y for _x, y in spots]
            scale = drawn_scale(
                section,
                (window.width(), window.height()),
                rows,
                tight_height(section, 1.0, text_ink),
                1.0,
                text_ink,
                text_width,
            )
            return (min(xs), min(ys), max(xs), max(ys)), scale

        one, one_scale = yellow_box(['A'], 'slow')
        three, three_scale = yellow_box(['Someone', 'Somebody else', 'Third driver'], 'respawned')
        self.assertEqual(one, three)
        self.assertGreater(one[2] - one[0], window.width() - 4)  # the whole box, as move mode sized it
        self.assertGreater(one[3] - one[1], window.height() - 4)
        self.assertEqual(one_scale, three_scale)  # the text keeps its size

    def test_the_heading_is_in_the_middle_and_the_drivers_on_the_left(self):
        # Asked for by the user on 2026-11-11.
        from turbohud.core import race
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        section = next(s for s in RACE_SECTIONS if s.name == 'yellowflag')
        window = SectionWindow(Native(), Theme(), section)
        self.addCleanup(window.close)
        window.resize(*window.base)
        window.set_locked(True)
        rows = race.yellow_rows((race.Incident('Ab', 'slow', 0),), self._state())
        self.assertEqual([row.centred for row in rows], [True, False])
        window.show_content(rows)
        image = window.grab().toImage()
        dark = [
            (x, y)
            for x in range(image.width())
            for y in range(image.height())
            if image.pixelColor(x, y).alpha() > 200 and max(image.pixelColor(x, y).getRgb()[:3]) < 60
        ]
        middle_y = (min(y for _x, y in dark) + max(y for _x, y in dark)) / 2
        heading = [x for x, y in dark if y < middle_y]
        driver = [x for x, y in dark if y > middle_y]
        self.assertAlmostEqual((min(heading) + max(heading)) / 2, image.width() / 2, delta=6)
        self.assertLess(min(driver), image.width() / 6)  # the driver's line starts on the left

    def _state(self):
        from turbohud.core import race

        me = race.PlayerState('Me', 0, 1, ((0,), (0, 1000)), local=True)
        return race.LapState(
            clock=0,
            time_limit=0,
            laps_completed=1,
            laps_to_finish=5,
            lap_starts=[0, 0],
            players=(me,),
            gates=(((0, 0), (1, 1)),) * 9,
        )


class MovePanelPresetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def panel(self, **options):
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.overlay.window import MovePanel

        class Native:
            def raise_window(self, window):
                return 'test'

        panel = MovePanel(Native(), RACE_SECTIONS, True, **options)
        self.addCleanup(panel.close)
        return panel

    def button(self, panel, number, text):
        from PySide6.QtWidgets import QPushButton

        found = [
            b for b in panel.findChildren(QPushButton) if b.text() == text and str(number) in b.toolTip()
        ]
        self.assertEqual(len(found), 1)
        return found[0]

    def test_only_a_saved_preset_can_be_loaded(self):
        panel = self.panel(saved_presets=(2,))
        self.assertFalse(self.button(panel, 1, 'Load').isEnabled())
        self.assertTrue(self.button(panel, 2, 'Load').isEnabled())
        panel.set_presets_saved((1, 2))
        self.assertTrue(self.button(panel, 1, 'Load').isEnabled())

    def test_the_buttons_say_which_preset(self):
        panel = self.panel(saved_presets=(1, 2, 3))
        saved, loaded = [], []
        panel.preset_save_requested.connect(saved.append)
        panel.preset_load_requested.connect(loaded.append)
        self.button(panel, 2, 'Save').click()
        self.button(panel, 3, 'Load').click()
        self.assertEqual((saved, loaded), ([2], [3]))

    def test_a_text_section_draws_at_its_text_size_whatever_its_box(self):
        from turbohud.core.hud import RACE_SECTIONS, Row
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        def inked(font, size):
            window = SectionWindow(Native(), Theme(), next(s for s in RACE_SECTIONS if s.name == 'localtime'))
            self.addCleanup(window.close)
            window.font = font
            window.resize(*size)
            window.show_content([Row('12:34', 'medium')])
            image = window.grab().toImage()
            return sum(
                image.pixelColor(x, y).alpha() > 0
                for x in range(image.width())
                for y in range(image.height())
            )

        self.assertEqual(inked(20, (200, 80)), inked(20, (400, 300)))  # a bigger box: no bigger text
        self.assertGreater(inked(30, (400, 300)), inked(20, (400, 300)) * 1.5)
        drawn = {'deltabar', 'trackmap', 'radar', 'blueflag'}
        by_text = {s.name for s in RACE_SECTIONS if SectionWindow(Native(), Theme(), s).text}
        self.assertEqual(by_text, {s.name for s in RACE_SECTIONS} - drawn)

    def test_text_sizes_per_section_and_global(self):
        # Asked for by the user on 2026-11-13: a text size per section, or the global one.
        from turbohud.core.hud import FONT_SIZES, RACE_SECTIONS, is_text_section

        panel = self.panel()
        self.assertEqual(set(panel.font_sizes), {s.name for s in RACE_SECTIONS if is_text_section(s)})
        own, every, back = [], [], []
        panel.font_size_changed.connect(lambda name, px: own.append((name, px)))
        panel.global_font_changed.connect(every.append)
        panel.all_global_requested.connect(lambda: back.append(True))
        box = panel.font_sizes['laptimes']
        panel.set_font_size('laptimes', None)  # shown: no request back
        self.assertEqual((box.text(), own), ('global', []))
        box.setValue(17)
        box.setValue(FONT_SIZES[0] - 1)  # down to global again
        self.assertEqual(own, [('laptimes', 17), ('laptimes', 0)])
        panel.set_global_font(15)
        self.assertEqual(every, [])
        panel.global_size.setValue(18)
        next(b for b in panel.findChildren(type(panel.undo)) if b.text() == 'All global').click()
        self.assertEqual((every, back), ([18], [True]))

    def test_match_works_from_two_text_sections_in_a_group(self):
        panel = self.panel()
        got = []
        panel.match_requested.connect(got.append)
        self.assertFalse(panel.matches['A'].isEnabled())
        panel.set_group('lap', 'A')
        panel.set_group('radar', 'A')  # a drawing has no text to match
        self.assertFalse(panel.matches['A'].isEnabled())
        panel.groups['delta'].setCurrentText('A')  # changed by the player
        self.assertTrue(panel.matches['A'].isEnabled())
        self.assertFalse(panel.matches['B'].isEnabled())
        panel.matches['A'].click()
        self.assertEqual(got, ['A'])

    def test_a_matched_group_is_drawn_at_one_font_size(self):
        from turbohud.core import hud
        from turbohud.core.settings import Theme
        from turbohud.hud.painter import text_ink, text_width

        by_name = {section.name: section for section in hud.RACE_SECTIONS}
        groups = (
            ('localtime', 'delta', 'fuel', 'speed'),
            ('lap', 'current', 'times', 'tires', 'draft'),
            ('localtime', 'players', 'laptimes'),
        )
        theme = Theme()
        for names in groups:
            places = {}
            for name in names:
                section = by_name[name]
                width = hud.base_size(section, theme.scale, text_width)[0]
                places[section] = (0, 0, width, hud.tight_height(section, theme.scale, text_ink))
            matched = hud.match_sizes(places, theme.scale, text_width, text_ink)
            fonts = set()
            for name, box in matched.items():
                section = by_name[name]
                base = hud.tight_height(section, theme.scale, text_ink)
                # As paintEvent works it out.
                rows = list(section.samples[0])
                scale = hud.drawn_scale(section, box[2:], rows, base, theme.scale, text_ink, text_width)
                fonts.add(hud.hud_lines(list(section.samples[0]), scale)[0].size)
            with self.subTest(group=names):
                self.assertEqual(len(fonts), 1, matched)
                self.assertEqual(len({box[2] for box in matched.values()}), 1)

    def test_every_section_can_be_centred_both_ways(self):
        from PySide6.QtWidgets import QPushButton

        from turbohud.core.hud import RACE_SECTIONS

        panel = self.panel()
        got = []
        panel.align_requested.connect(lambda *request: got.append(request))
        for text in ('↔', '↕'):
            for button in panel.findChildren(QPushButton):
                if button.text() == text:
                    button.click()
        names = [section.name for section in RACE_SECTIONS]
        self.assertEqual(
            sorted(got),
            sorted([(name, True, False) for name in names] + [(name, False, True) for name in names]),
        )

    def test_the_option_shows_where_it_works_and_says_which_section(self):
        from turbohud.core.hud import RACE_SECTIONS, text_can_centre

        panel = self.panel()
        got = []
        panel.text_centred_changed.connect(lambda *change: got.append(change))
        self.assertEqual(
            set(panel.centres), {section.name for section in RACE_SECTIONS if text_can_centre(section)}
        )
        panel.centres['lap'].setChecked(True)
        self.assertEqual(got, [('lap', True)])
        panel.set_text_centred('lap', False)  # from a preset: no change to report
        self.assertEqual(got, [('lap', True)])
        self.assertFalse(panel.centres['lap'].isChecked())
        panel.set_text_centred('speed', True)  # not one of them: nothing happens

    def test_only_a_saved_preset_can_be_deleted(self):
        panel = self.panel(saved_presets=(2,))
        got = []
        panel.preset_delete_requested.connect(got.append)
        self.assertFalse(panel.preset_deletes[1].isEnabled())
        self.assertTrue(panel.preset_deletes[2].isEnabled())
        panel.preset_deletes[2].click()
        self.assertEqual(got, [2])
        panel.set_presets_saved(())
        self.assertFalse(panel.preset_deletes[2].isEnabled())
        self.assertEqual(panel.preset_deletes[2].text(), 'Delete')  # a word, as Save and Load

    def test_a_preset_can_go_back_to_empty(self):
        panel = self.panel(saved_presets=(1, 2))
        panel.set_presets_saved((2,))
        self.assertFalse(self.button(panel, 1, 'Load').isEnabled())
        self.assertTrue(self.button(panel, 2, 'Load').isEnabled())

    def test_undo_starts_greyed_out_and_asks_when_clicked(self):
        panel = self.panel()
        got = []
        panel.undo_requested.connect(lambda: got.append(True))
        self.assertFalse(panel.undo.isEnabled())
        panel.set_undo_available(True)
        panel.undo.click()
        self.assertEqual(got, [True])

    def test_the_lap_times_keep_their_font_size_through_the_conversion(self):
        from dataclasses import replace

        from turbohud.core import hud
        from turbohud.hud.painter import text_ink

        section = next(s for s in hud.RACE_SECTIONS if s.name == 'laptimes')
        old = replace(section, samples=(section.samples[0][:17],))
        old_normal = hud.tight_height(old, 1.0, text_ink)
        for height in (old_normal, 357, 500, 200):
            with self.subTest(height=height):
                box = hud.more_lap_rows_place(section, (0, 0, 2000, height), 1.0, text_ink)
                before = hud.fitted_scale(old, height, height / old_normal, text_ink)
                now = hud.fitted_scale(
                    section, box[3], box[3] / hud.tight_height(section, 1.0, text_ink), text_ink
                )
                self.assertEqual(hud.Sizes.for_scale(before).small, hud.Sizes.for_scale(now).small)

    def test_text_sections_and_the_map_have_a_tint_tick_box_and_other_drawings_none(self):
        from turbohud.core.hud import RACE_SECTIONS

        panel = self.panel()
        got = []
        panel.tint_changed.connect(lambda *change: got.append(change))
        tinted = {
            s.name for s in RACE_SECTIONS if not s.drawing and not s.background
        }  # a background is its own
        self.assertEqual(set(panel.tints), tinted | {'trackmap'})
        panel.tints['trackmap'].setChecked(True)
        self.assertEqual(got.pop(), ('trackmap', True))
        panel.tints['fuel'].setChecked(True)
        self.assertEqual(got, [('fuel', True)])
        panel.set_tint('fuel', False)  # from a preset or Undo: no change to report
        self.assertEqual(got, [('fuel', True)])
        self.assertFalse(panel.tints['fuel'].isChecked())
        panel.set_tint('radar', True)  # none: nothing happens

    def test_select_all_and_deselect_all_tick_every_box_in_one_request(self):
        from PySide6.QtWidgets import QPushButton

        panel = self.panel()
        one_by_one, at_once = [], []
        panel.wanted_changed.connect(lambda *change: one_by_one.append(change))
        panel.all_wanted.connect(at_once.append)
        buttons = {b.text(): b for b in panel.findChildren(QPushButton) if b.text() in ('All', 'None')}
        buttons['All'].click()
        self.assertTrue(all(box.isChecked() for box in panel.boxes.values()))
        buttons['None'].click()
        self.assertFalse(any(box.isChecked() for box in panel.boxes.values()))
        self.assertEqual(at_once, [True, False])  # one request each: one step for Undo
        self.assertEqual(one_by_one, [])

    def test_the_sections_are_listed_under_headings(self):
        from PySide6.QtWidgets import QLabel

        from turbohud.core.hud import RACE_SECTIONS

        panel = self.panel()
        texts = [label.text() for label in panel.findChildren(QLabel)]
        for heading in ('TIMING', 'CAR', 'RACE', 'OTHER'):
            self.assertTrue(any(heading in text for text in texts), heading)
        self.assertEqual(len(panel.boxes), len(RACE_SECTIONS))  # every section still there

    def test_every_word_button_is_wide_enough_for_its_word(self):
        # Reported by the user on 2026-11-11: with a fixed width macOS cut "None" and "Delete" short.
        from PySide6.QtWidgets import QPushButton

        panel = self.panel(saved_presets=(1,))
        panel.show()
        words = (
            'All',
            'None',
            'Save',
            'Load',
            'Delete',
            'Undo',
            'Relearn map',
            'Lock',
            'Settings…',
            'Quit TurboHUD',
        )
        buttons = [b for b in panel.findChildren(QPushButton) if b.text() in words]
        self.assertEqual({b.text() for b in buttons}, set(words))
        for button in buttons:
            self.assertGreaterEqual(button.width(), button.sizeHint().width(), button.text())

    def test_relearn_map_works_only_while_a_track_is_known(self):
        from turbohud.core.hud import CLOCK_SECTIONS
        from turbohud.overlay.window import MovePanel

        panel = self.panel()
        self.assertFalse(panel.relearn.isEnabled())
        asked = []
        panel.relearn_requested.connect(lambda: asked.append(True))
        panel.set_relearn_available(True)
        self.assertTrue(panel.relearn.isEnabled())
        panel.relearn.click()
        self.assertEqual(asked, [True])
        clock = MovePanel(
            type('Native', (), {'raise_window': lambda self, w: 'test'})(), CLOCK_SECTIONS, True
        )
        self.addCleanup(clock.close)
        self.assertIsNone(clock.relearn)  # no track map, no button
        clock.set_relearn_available(True)

    def test_the_panel_stays_compact(self):
        # It was 675 x 978 px with the options and a row per preset: most of a laptop's screen.
        panel = self.panel()
        self.assertLess(panel.height(), 800)
        self.assertLess(panel.width(), 600)
        self.assertFalse(hasattr(panel, 'mph'))  # the options for the whole HUD are in the settings

    def test_the_panel_stays_compact_with_linux_sized_text(self):
        # Linux desktops use about 15 px text, also given to buttons and lists on their own,
        # which made the panel 866 px tall (2026-11-12). Its text is held at the Mac's 13 px.
        from PySide6.QtGui import QFontInfo
        from PySide6.QtWidgets import QApplication, QComboBox, QPushButton

        from turbohud.overlay.window import PANEL_FONT_PX

        before = QApplication.font()
        self.addCleanup(QApplication.setFont, before)
        large = QApplication.font()
        large.setPixelSize(15)
        QApplication.setFont(large)
        for kind in ('QPushButton', 'QComboBox', 'QCheckBox'):
            self.addCleanup(QApplication.setFont, QApplication.font(kind), kind)
            QApplication.setFont(large, kind)
        panel = self.panel()
        self.assertLess(panel.height(), 800)
        for widget in (*panel.findChildren(QPushButton), *panel.findChildren(QComboBox)):
            self.assertLessEqual(QFontInfo(widget.font()).pixelSize(), PANEL_FONT_PX)

    def test_load_names_its_shortcut_where_there_are_shortcuts(self):
        self.assertIn('Ctrl+Shift+2', self.button(self.panel(), 2, 'Load').toolTip())


if __name__ == '__main__':
    unittest.main()


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class CanvasTests(unittest.TestCase):
    """Locked, every section drawn in one window per screen (asked for on 2026-11-09: on a
    Mac 17 windows cost 35 FPS where one window with the same boxes cost 5)."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.race import DeltaBarView
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import HudCanvases, SectionWindow

        class Native:
            hides_windows = True
            one_window = True

            def raise_window(self, window):
                return 'test'

        self.native = Native()
        self.bar = SectionWindow(self.native, Theme(), next(s for s in RACE_SECTIONS if s.name == 'deltabar'))
        self.addCleanup(self.bar.close)
        self.bar.setGeometry(100, 100, 400, 40)
        self.canvases = HudCanvases(self.native, [(0, 0, 800, 600)], [self.bar])
        self.canvas = self.canvases.canvases[0]
        self.addCleanup(self.canvas.close)
        self.bar.canvas = self.canvases
        self.bar.show_on_top()
        self.bar.show_content([], delta_view=DeltaBarView(0.5, -1.0, ''))
        self.bar.update()

    def pixel(self, x, y):
        return self.canvas.grab().toImage().pixelColor(x, y)

    def test_the_canvas_draws_the_section_at_its_place_and_its_window_stays_hidden(self):
        green = self.pixel(100 + 280, 120)  # ahead and gaining: the right half, green
        self.assertGreater(green.green(), green.red())
        self.assertEqual(self.pixel(50, 50).alpha(), 0)  # elsewhere the game shows through
        self.assertFalse(self.bar.isVisible())

    def test_a_redraw_while_locked_goes_to_the_canvas(self):
        asked = []
        self.bar.canvas = type('Canvas', (), {'redraw': lambda _self, window: asked.append(window)})()
        self.bar.update()
        self.assertEqual(asked, [self.bar])

    def test_a_moved_section_leaves_nothing_where_it_was(self):
        self.pixel(0, 0)  # drawn once at (100, 100)
        self.bar.setGeometry(100, 300, 400, 40)
        self.bar.update()
        self.assertEqual(self.pixel(100 + 280, 120).alpha(), 0)
        moved = self.pixel(100 + 280, 320)
        self.assertGreater(moved.green(), moved.red())

    def test_a_hidden_window_moved_without_a_redraw_is_still_drawn_where_it_now_is(self):
        # As a preset or "all sections bigger" moves it while locked: the canvas draws from
        # where the window is, not from where it was last asked to.
        self.bar.setGeometry(300, 400, 400, 40)
        moved = self.pixel(300 + 280, 420)
        self.assertGreater(moved.green(), moved.red())

    def test_a_section_hidden_by_its_tick_box_goes_from_the_canvas(self):
        self.bar.set_wanted(False)
        self.assertEqual(self.pixel(100 + 280, 120).alpha(), 0)

    def test_in_move_mode_the_section_has_its_own_window_again(self):
        self.bar.set_locked(False)
        self.assertTrue(self.bar.isVisible())
        self.bar.set_locked(True)
        self.assertFalse(self.bar.isVisible())

    def test_it_is_on_where_the_platform_says_so_unless_turned_off(self):
        from turbohud.app import one_window_wanted

        self.assertTrue(one_window_wanted(self.native, {}))
        self.assertFalse(one_window_wanted(self.native, {'TURBOHUD_ONE_WINDOW': '0'}))
        self.assertFalse(one_window_wanted(object(), {}))  # Linux and Windows: not yet

    def test_only_the_changed_sections_are_drawn_again_not_those_between_them(self):
        # Two sections far apart changed: the one between them, inside the rectangle round
        # both, stays as it is (the tester's layout drew most of the screen each frame, 2026-11-12).
        from PySide6.QtCore import QPoint, QRect
        from PySide6.QtGui import QImage, QRegion
        from PySide6.QtWidgets import QWidget

        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.race import DeltaBarView
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import HudCanvases, SectionWindow

        section = next(s for s in RACE_SECTIONS if s.name == 'deltabar')
        bars = []
        for y in (0, 280, 560):
            bar = SectionWindow(self.native, Theme(), section)
            self.addCleanup(bar.close)
            bar.setGeometry(100 + y, y, 200, 40)
            bars.append(bar)
        canvases = HudCanvases(self.native, [(0, 0, 900, 600)], bars)
        canvas = canvases.canvases[0]
        self.addCleanup(canvas.close)
        drawn = []
        for bar in bars:
            bar.canvas = canvases
            bar.show_on_top()
            bar.show_content([], delta_view=DeltaBarView(0.5, -1.0, ''))
            bar.draw = lambda painter, bar=bar, draw=bar.draw: (drawn.append(bar), draw(painter))
        top, middle, bottom = bars
        changed = QRegion()
        for bar in (top, bottom):
            changed = changed.united(QRect(bar.x() - 2, bar.y() - 2, bar.width() + 4, bar.height() + 4))
        image = QImage(900, 600, QImage.Format_ARGB32_Premultiplied)
        image.fill(0)
        canvas.render(image, QPoint(), changed, QWidget.RenderFlag(0))
        self.assertEqual(drawn, [top, bottom])
        colors = [image.pixelColor(x, top.y() + 20) for x in range(top.x(), top.x() + top.width())]
        self.assertTrue(any(c.alpha() == 255 and c.green() > c.red() for c in colors))  # green: drawn
        self.assertEqual(image.pixelColor(middle.x() + 20, middle.y() + 20).alpha(), 0)  # not drawn again


class ResizeCursorTests(unittest.TestCase):
    def test_every_edge_and_corner_has_its_cursor(self):
        from turbohud.overlay.window import RESIZE_CURSORS, RESIZE_FLAGS

        corners = {
            frozenset(c) for c in (('left', 'top'), ('left', 'bottom'), ('right', 'top'), ('right', 'bottom'))
        }
        self.assertEqual(set(RESIZE_CURSORS), {frozenset({e}) for e in RESIZE_FLAGS} | corners)


class TextResizeTests(unittest.TestCase):
    """A text section dragged at its edges (asked for by the user on 2026-11-13): height sets
    its text size, width adds room, never narrower than its text."""

    @classmethod
    def setUpClass(cls):
        MovePanelPresetTests.setUpClass()

    def window(self, name='players', font=13):
        from turbohud.core.hud import RACE_SECTIONS, text_box
        from turbohud.core.settings import Theme
        from turbohud.hud.painter import text_ink, text_width
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        window = SectionWindow(Native(), Theme(), next(s for s in RACE_SECTIONS if s.name == name))
        self.addCleanup(window.close)
        window.font = font
        box = text_box(window.section, (100, 100, 0, 0), font, text_width, text_ink)
        window.setGeometry(*box)
        return window, box

    def test_the_bottom_edge_sets_the_text_size_and_the_box_stays_tight(self):
        window, box = self.window()
        window._resize_text(('bottom',), box, 0, box[3])  # twice as tall
        self.assertGreater(window.font, 20)
        self.assertEqual(window.own_font, window.font)
        self.assertEqual(window.geometry().getRect()[:2], box[:2])
        from turbohud.core.hud import text_box
        from turbohud.hud.painter import text_ink, text_width

        self.assertEqual(window.height(), text_box(window.section, box, window.font, text_width, text_ink)[3])

    def test_the_top_edge_keeps_the_bottom_in_place(self):
        window, box = self.window()
        window._resize_text(('top',), box, 0, -box[3])
        _x, y, _width, height = window.geometry().getRect()
        self.assertEqual(y + height, box[1] + box[3])

    def test_the_side_edges_add_room_and_keep_the_text_size(self):
        window, box = self.window()
        window._resize_text(('right',), box, 80, 0)
        self.assertEqual((window.font, window.width(), window.height()), (13, box[2] + 80, box[3]))
        window._resize_text(('right',), box, -500, 0)  # never narrower than its text
        self.assertEqual(window.width(), box[2])
        window._resize_text(('left',), box, -40, 0)
        self.assertEqual(window.geometry().getRect()[0] + window.width(), box[0] + box[2])

    def test_lines_boxes_for_sections_of_several_rows(self):
        from turbohud.core.hud import RACE_SECTIONS, is_text_section
        from turbohud.overlay.window import MovePanel

        class Native:
            def raise_window(self, window):
                return 'test'

        panel = MovePanel(Native(), RACE_SECTIONS, True)
        self.addCleanup(panel.close)
        several = {s.name for s in RACE_SECTIONS if is_text_section(s) and len(s.samples[0]) > 1}
        self.assertEqual(set(panel.spacings), several)
        self.assertIn('laptimes', several)
        got = []
        panel.spacing_changed.connect(lambda name, pct: got.append((name, pct)))
        panel.spacings['laptimes'].setValue(150)
        panel.set_spacing('laptimes', 2.0)  # shown: no request back
        self.assertEqual((got, panel.spacings['laptimes'].value()), ([('laptimes', 150)], 200))
