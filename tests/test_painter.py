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
        window.show_content([], delta_view=DeltaBarView(-0.5, 0.0, ''))
        white = window.grab().toImage().pixelColor(120, 20)
        self.assertTrue(white.red() > 240 and white.green() > 240 and white.blue() > 240)  # steady
        window.show_content([])
        self.assertEqual(window.grab().toImage().pixelColor(200, 20).alpha(), 0)  # no delta, no bar

    def test_the_delta_bar_colour_goes_gradually_from_white(self):
        from turbohud.hud.painter import AHEAD_COLOR, BEHIND_COLOR, DELTA_STEADY_COLOR, delta_bar_color

        self.assertEqual(delta_bar_color(0.0), DELTA_STEADY_COLOR)
        self.assertEqual(delta_bar_color(-1.0), AHEAD_COLOR)
        self.assertEqual(delta_bar_color(1.0), BEHIND_COLOR)
        half = delta_bar_color(-0.5)
        self.assertNotIn(half, (DELTA_STEADY_COLOR, AHEAD_COLOR))  # in between

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
            if min(image.pixelColor(x, y).getRgb()) >= 150
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

    def drawn(self, name, rows, size, backdrop=False):
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
        window.show_content(rows)
        return window.grab().toImage()

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
            if section.bar:
                continue
            for share in (1.0, 2.0, 0.6):
                with self.subTest(section=section.name, share=share):
                    (_left, top, _right, bottom), (_width, height) = self.text_box(
                        section.name, list(section.samples[0]), share
                    )
                    self.assertGreaterEqual(top, 1)
                    self.assertLessEqual(bottom, height - 2)


class MovePanelPresetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
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
        for text in ('Centre ↔', 'Centre ↕'):
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
        self.assertFalse(panel.preset_deletes[2].icon().isNull())

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

    def test_text_sections_have_a_tint_tick_box_and_drawings_none(self):
        from turbohud.core.hud import RACE_SECTIONS

        panel = self.panel()
        got = []
        panel.tint_changed.connect(lambda *change: got.append(change))
        self.assertEqual(set(panel.tints), {s.name for s in RACE_SECTIONS if not s.drawing})
        panel.tints['fuel'].setChecked(True)
        self.assertEqual(got, [('fuel', True)])
        panel.set_tint('fuel', False)  # from a preset or Undo: no change to report
        self.assertEqual(got, [('fuel', True)])
        self.assertFalse(panel.tints['fuel'].isChecked())
        panel.set_tint('radar', True)  # none: nothing happens

    def test_load_names_its_shortcut_where_there_are_shortcuts(self):
        self.assertIn('Ctrl+Shift+2', self.button(self.panel(), 2, 'Load').toolTip())


if __name__ == '__main__':
    unittest.main()
