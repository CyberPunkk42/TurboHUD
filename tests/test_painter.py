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
class RedrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

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

    def test_the_text_shrinks_with_the_box(self):
        from turbohud.core.hud import Row

        rows = [Row('12:34', 'medium')]

        def tall(share):
            (_left, top, _right, bottom), _size = self.text_box('localtime', rows, share)
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
                needed = hud.base_size(section, theme.scale, text_width)[0]
                # As paintEvent works it out.
                scale = theme.scale * hud.section_scale(box[2:], base, needed)
                scale = hud.fitted_scale(section, box[3], scale, text_ink)
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

    def test_load_names_its_shortcut_where_there_are_shortcuts(self):
        self.assertIn('Ctrl+Shift+2', self.button(self.panel(), 2, 'Load').toolTip())


if __name__ == '__main__':
    unittest.main()
