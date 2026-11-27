"""The player's own fonts (asked for by the user on 2026-11-16): customization/fonts, the font
the HUD draws with, and its choice in the settings window."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import fonts, settings

# A monospace font the system has, to try a font file with (none is shipped for tests): its
# letters are wider than the usual font's, so the change shows in what is measured.
SYSTEM_MONOSPACE = (
    '/System/Library/Fonts/Supplemental/Andale Mono.ttf',
    '/System/Library/Fonts/Supplemental/Courier New.ttf',
    'C:/Windows/Fonts/cour.ttf',
    'C:/Windows/Fonts/consola.ttf',
    '/usr/share/fonts/TTF/DejaVuSansMono.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
    '/usr/share/fonts/liberation/LiberationMono-Regular.ttf',
)


def a_system_font():
    return next((Path(p) for p in SYSTEM_MONOSPACE if Path(p).is_file()), None)


class FolderTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)

    def test_beside_the_display_presets(self):
        presets = self.folder / 'customization' / 'display_presets'
        self.assertEqual(fonts.fonts_folder(presets), self.folder / 'customization' / 'fonts')

    def test_made_with_a_read_me(self):
        made = fonts.ready_fonts_folder(self.folder / 'fonts')
        self.assertEqual(made, self.folder / 'fonts')
        self.assertIn('.ttf', (made / fonts.README).read_text(encoding='utf-8'))
        (made / fonts.README).write_text('mine', encoding='utf-8')
        fonts.ready_fonts_folder(made)
        self.assertEqual((made / fonts.README).read_text(encoding='utf-8'), 'mine')  # kept

    def test_only_font_files_by_name(self):
        for name in ('b.OTF', 'a.ttf', 'notes.txt', 'c.woff', 'README.txt'):
            (self.folder / name).write_bytes(b'')
        (self.folder / 'd.ttf').mkdir()
        self.assertEqual([p.name for p in fonts.font_files(self.folder)], ['a.ttf', 'b.OTF'])
        self.assertEqual(fonts.font_files(self.folder / 'missing'), [])


class AddFontTests(unittest.TestCase):
    """Add font... copies a chosen file into the fonts folder (2026-11-17): the folder window
    opened beneath TurboHUD's."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.folder = self.root / 'fonts'
        self.downloads = self.root / 'Downloads'
        self.downloads.mkdir()

    def font(self, name='Nice.ttf', data=b'font one'):
        path = self.downloads / name
        path.write_bytes(data)
        return path

    def test_copied_into_the_folder(self):
        copied = fonts.add_font_file(self.font(), self.folder)
        self.assertEqual(copied, self.folder / 'Nice.ttf')
        self.assertEqual(copied.read_bytes(), b'font one')
        self.assertTrue((self.downloads / 'Nice.ttf').exists())  # the player's file stays

    def test_the_same_file_again_is_not_copied_twice(self):
        fonts.add_font_file(self.font(), self.folder)
        self.assertEqual(fonts.add_font_file(self.font(), self.folder), self.folder / 'Nice.ttf')
        self.assertEqual([p.name for p in fonts.font_files(self.folder)], ['Nice.ttf'])

    def test_another_file_of_the_same_name_is_kept_beside(self):
        fonts.add_font_file(self.font(), self.folder)
        copied = fonts.add_font_file(self.font(data=b'font two'), self.folder)
        self.assertEqual(copied, self.folder / 'Nice (2).ttf')
        self.assertEqual((self.folder / 'Nice.ttf').read_bytes(), b'font one')  # never replaced

    def test_a_file_already_in_the_folder(self):
        self.folder.mkdir()
        inside = self.folder / 'Here.otf'
        inside.write_bytes(b'x')
        self.assertEqual(fonts.add_font_file(inside, self.folder), inside)
        self.assertEqual([p.name for p in fonts.font_files(self.folder)], ['Here.otf'])

    def test_no_font_file_is_refused(self):
        self.assertIsNone(fonts.add_font_file(self.font('notes.txt'), self.folder))
        self.assertIsNone(fonts.add_font_file(self.downloads / 'gone.ttf', self.folder))
        self.assertFalse(self.folder.exists())

    def test_the_file_window_shows_font_files(self):
        self.assertEqual(fonts.font_filter(), 'Fonts (*.ttf *.otf *.ttc *.otc)')


class SettingsTests(unittest.TestCase):
    def test_the_font_is_saved_and_read(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        path = folder / 'settings.json'
        settings.save_settings(path, settings.Settings(font_family='Andale Mono'))
        self.assertEqual(settings.load_settings(path).font_family, 'Andale Mono')
        settings.save_settings(path, settings.Settings())
        self.assertEqual(settings.load_settings(path).font_family, '')


class PainterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from turbohud.hud import painter

        self.painter = painter
        self.addCleanup(painter.set_family, '')  # the other tests draw with the usual font

    def test_unchanged_is_no_change(self):
        self.assertFalse(self.painter.set_family(''))

    def test_a_font_file_is_loaded_and_drawn_with(self):
        found = a_system_font()
        if found is None:
            self.skipTest('no monospace font file on this system')
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        copy = folder / found.name
        shutil.copy(found, copy)
        (folder / 'broken.ttf').write_bytes(b'not a font')
        families = self.painter.load_font_files(fonts.font_files(folder))
        self.assertEqual(len(families), 1)  # the broken file is left out
        ((family, file),) = families.items()
        self.assertEqual(file, found.name)
        self.assertEqual(self.painter.load_font_files(fonts.font_files(folder)), families)  # once
        usual = self.painter.text_width('Playername 1234', 20)
        self.assertTrue(self.painter.set_family(family))
        self.assertEqual(self.painter.font_family(), family)
        self.assertEqual(self.painter.hud_font(20).families()[0], family)
        self.assertNotAlmostEqual(self.painter.text_width('Playername 1234', 20), usual, delta=1.0)
        self.assertTrue(self.painter.set_family(''))
        self.assertAlmostEqual(self.painter.text_width('Playername 1234', 20), usual)


class SettingsWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def window(self):
        from turbohud.core.settings import Theme
        from turbohud.overlay.settings_window import SettingsWindow
        from turbohud.overlay.window import window_flags

        class Native:
            def raise_window(self, window):
                return 'test'

        window = SettingsWindow(Native(), window_flags(), Theme())
        self.addCleanup(window.close)
        return window

    def listed(self, window):
        choice = window.font_choice
        return [(choice.itemText(i), choice.itemData(i)) for i in range(choice.count())]

    def test_the_system_font_and_ones_own(self):
        window = self.window()
        window.set_fonts({'Alpha Sans': 'alpha.ttf', 'Beta Mono': 'beta.otf'}, 'Beta Mono')
        self.assertEqual(
            self.listed(window),
            [('System font', ''), ('Alpha Sans', 'Alpha Sans'), ('Beta Mono', 'Beta Mono')],
        )
        self.assertEqual(window.font_choice.currentData(), 'Beta Mono')

    def test_a_chosen_font_no_longer_there_is_missing(self):
        window = self.window()
        window.set_fonts({}, 'Gone Font')
        self.assertEqual(self.listed(window), [('System font', ''), ('Gone Font (missing)', 'Gone Font')])

    def test_picking_tells_the_family_but_filling_does_not(self):
        window = self.window()
        picked = []
        window.font_chosen.connect(picked.append)
        window.set_fonts({'Alpha Sans': 'alpha.ttf'}, '')
        self.assertEqual(picked, [])
        window.font_choice.setCurrentIndex(1)
        window.font_choice.setCurrentIndex(0)
        self.assertEqual(picked, ['Alpha Sans', ''])

    def test_the_folder_button(self):
        window = self.window()
        asked = []
        window.fonts_folder_requested.connect(lambda: asked.append(True))
        from PySide6.QtWidgets import QPushButton

        button = next(b for b in window.findChildren(QPushButton) if b.text() == 'Fonts folder...')
        button.click()
        self.assertEqual(asked, [True])

    def test_the_add_font_button(self):
        window = self.window()
        asked = []
        window.add_font_requested.connect(lambda: asked.append(True))
        from PySide6.QtWidgets import QPushButton

        button = next(b for b in window.findChildren(QPushButton) if b.text() == 'Add font...')
        button.click()
        self.assertEqual(asked, [True])


# A font for each section and each preset (asked for by the user on 2026-11-20).


def place(**options):
    return settings.SectionPlace(10, 20, 200, 40, **options)


class SectionFontSettingsTests(unittest.TestCase):
    def setUp(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        self.path = folder / 'settings.json'

    def round_trip(self, kept):
        settings.save_settings(self.path, kept)
        return settings.load_settings(self.path)

    def test_a_sections_own_font_is_kept_and_global_is_none(self):
        sections = {'lap': place(family='Alpha Sans'), 'fuel': place(family=''), 'tires': place()}
        read = self.round_trip(settings.Settings(sections=sections)).sections
        self.assertEqual(read['lap'].family, 'Alpha Sans')
        self.assertEqual(read['fuel'].family, '')  # the system font, chosen for this section
        self.assertIsNone(read['tires'].family)  # the global font

    def test_a_preset_keeps_its_sections_fonts_and_its_global_font(self):
        kept = settings.Settings(
            presets={2: {'lap': place(family='Beta Mono')}, 3: {'lap': place()}},
            preset_fonts={2: 'Alpha Sans', 3: ''},
        )
        read = self.round_trip(kept)
        self.assertEqual(read.presets[2]['lap'].family, 'Beta Mono')
        self.assertEqual(read.preset_fonts, {2: 'Alpha Sans', 3: ''})

    def test_a_preset_saved_before_keeps_no_font(self):
        self.path.write_text('{"presets": {"1": {"lap": {"x": 1, "y": 2, "width": 90, "height": 30}}}}')
        read = settings.load_settings(self.path)
        self.assertEqual(read.preset_fonts, {})
        self.assertIsNone(read.presets[1]['lap'].family)

    def test_a_broken_font_in_the_file_is_global(self):
        self.path.write_text(
            '{"sections": {"lap": {"x": 1, "y": 2, "width": 90, "height": 30, "family": 7}},'
            ' "preset_fonts": {"1": 3, "2": "Alpha Sans", "9": "Beta"}}'
        )
        read = settings.load_settings(self.path)
        self.assertIsNone(read.sections['lap'].family)
        self.assertEqual(read.preset_fonts, {2: 'Alpha Sans'})


class LayoutFileFontTests(unittest.TestCase):
    def test_a_sections_own_font_and_the_global_one_go_into_the_file(self):
        from turbohud.core import presets

        data = presets.preset_data(
            {'lap': place(family='Beta Mono'), 'fuel': place()}, (1920, 1080), 18, 'Alpha Sans'
        )
        self.assertEqual(data['font_family'], 'Alpha Sans')
        self.assertEqual(data['sections']['lap']['family'], 'Beta Mono')
        self.assertNotIn('family', data['sections']['fuel'])

    def test_read_the_files_global_font_is_the_font_of_the_sections_without_their_own(self):
        # So it looks as made, and the player's own global font stays as it is.
        from turbohud.core import presets

        data = presets.preset_data(
            {'lap': place(family='Beta Mono'), 'fuel': place(), 'tires': place(family='')},
            (1920, 1080),
            18,
            'Alpha Sans',
        )
        _size, places = presets.read_preset(data)
        self.assertEqual(places['lap'].family, 'Beta Mono')
        self.assertEqual(places['fuel'].family, 'Alpha Sans')
        self.assertEqual(places['tires'].family, '')

    def test_a_file_made_in_the_system_font_leaves_the_global_font(self):
        from turbohud.core import presets

        data = presets.preset_data({'fuel': place()}, (1920, 1080), 18)
        self.assertNotIn('font_family', data)
        self.assertIsNone(presets.read_preset(data)[1]['fuel'].family)


class PresetInUseFontTests(unittest.TestCase):
    def test_a_preset_counts_only_in_the_global_font_it_keeps(self):
        sections = {'lap': place()}
        kept = {1: {'lap': place()}}
        screens = [(0, 0, 1920, 1080)]
        self.assertEqual(settings.current_preset(sections, kept, screens, None, {1: 'Alpha Sans'}, ''), None)
        self.assertEqual(
            settings.current_preset(sections, kept, screens, None, {1: 'Alpha Sans'}, 'Alpha Sans'),
            (1, False),
        )
        self.assertEqual(settings.current_preset(sections, kept, screens, None, {}, 'Beta'), (1, False))

    def test_a_sections_own_font_is_part_of_the_preset(self):
        screens = [(0, 0, 1920, 1080)]
        kept = {1: {'lap': place(family='Beta Mono')}}
        self.assertEqual(settings.current_preset({'lap': place()}, kept, screens, 1), (1, True))


class SectionFontPainterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from turbohud.hud import painter

        self.painter = painter
        self.addCleanup(painter.set_family, '')
        found = a_system_font()
        if found is None:
            self.skipTest('no monospace font file on this system')
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        shutil.copy(found, folder / found.name)
        ((self.family, _file),) = painter.load_font_files(fonts.font_files(folder)).items()

    def test_a_section_draws_in_its_own_font_and_the_global_one_stays(self):
        usual = self.painter.text_width('Playername 1234', 20)
        with self.painter.using(self.family):
            self.assertEqual(self.painter.font_family(), self.family)
            own = self.painter.text_width('Playername 1234', 20)
        self.assertNotAlmostEqual(own, usual, delta=1.0)
        self.assertEqual(self.painter.font_family(), '')  # after it, the global font again
        self.assertAlmostEqual(self.painter.text_width('Playername 1234', 20), usual)

    def test_global_is_the_global_font_and_the_innermost_counts(self):
        self.painter.set_family(self.family)
        with self.painter.using(None):
            self.assertEqual(self.painter.font_family(), self.family)
            with self.painter.using(''):
                self.assertEqual(self.painter.font_family(), '')
            self.assertEqual(self.painter.font_family(), self.family)
        self.assertEqual(self.painter.global_family(), self.family)

    def test_each_font_has_its_own_measures_the_same_each_time(self):
        width, ink = self.painter.measures(self.family)
        self.assertIs(self.painter.measures(self.family)[0], width)  # core keeps box heights by them
        self.assertEqual(self.painter.measures(None), (self.painter.text_width, self.painter.text_ink))
        with self.painter.using(self.family):
            self.assertEqual(width('L12', 20), self.painter.text_width('L12', 20))
            self.assertEqual(ink('L12', 20), self.painter.text_ink('L12', 20))
        # Narrow letters: 'Playername' came out within 1 px in both fonts on Linux (2026-11-27).
        self.assertNotAlmostEqual(
            width('iiiiiiiiii', 20), self.painter.text_width('iiiiiiiiii', 20), delta=1.0
        )

    def test_a_text_image_is_kept_for_each_font(self):
        white, black = 0xFFFFFFFF, 0xFF000000
        usual = self.painter.text_image('Player', 20, white, black, 1.0)[0]
        with self.painter.using(self.family):
            own = self.painter.text_image('Player', 20, white, black, 1.0)[0]
        self.assertNotEqual(own.width(), usual.width())
        self.assertIs(self.painter.text_image('Player', 20, white, black, 1.0)[0], usual)


class PanelFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def panel(self):
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.overlay.window import MovePanel

        class Native:
            def raise_window(self, window):
                return 'test'

        panel = MovePanel(Native(), RACE_SECTIONS, True)
        self.addCleanup(panel.close)
        panel.set_fonts({'Alpha Sans': 'alpha.ttf'}, '')
        return panel

    @staticmethod
    def listed(box):
        return [box.itemText(i) for i in range(box.count())]

    def test_each_text_section_has_a_font_list_with_global_first(self):
        panel = self.panel()
        self.assertEqual(self.listed(panel.families['lap']), ['global', 'System font', 'Alpha Sans'])
        self.assertEqual(panel.families['lap'].currentText(), 'global')
        self.assertNotIn('radar', panel.families)  # a drawing has no text
        self.assertEqual(self.listed(panel.global_family), ['System font', 'Alpha Sans'])

    def test_picking_a_font_tells_the_section_and_global_is_none(self):
        panel = self.panel()
        picked = []
        panel.family_changed.connect(lambda name, family: picked.append((name, family)))
        box = panel.families['lap']
        box.setCurrentIndex(2)
        box.setCurrentIndex(1)
        box.setCurrentIndex(0)
        self.assertEqual(picked, [('lap', 'Alpha Sans'), ('lap', ''), ('lap', None)])

    def test_shown_from_the_app_says_nothing_back(self):
        panel = self.panel()
        picked = []
        panel.family_changed.connect(lambda name, family: picked.append(name))
        panel.global_family_changed.connect(picked.append)
        panel.set_family('lap', 'Alpha Sans')
        panel.set_global_family('Alpha Sans')
        self.assertEqual(picked, [])
        self.assertEqual(panel.families['lap'].currentText(), 'Alpha Sans')
        self.assertEqual(panel.global_family.currentText(), 'Alpha Sans')

    def test_a_font_no_longer_there_is_missing_and_kept(self):
        panel = self.panel()
        panel.set_family('lap', 'Gone Font')
        self.assertEqual(panel.families['lap'].currentText(), 'Gone Font (missing)')
        panel.set_fonts({'Alpha Sans': 'alpha.ttf', 'Beta Mono': 'beta.otf'}, '')
        self.assertEqual(panel.families['lap'].currentText(), 'Gone Font (missing)')  # new fonts, same pick

    def test_the_global_font_and_all_global(self):
        from PySide6.QtWidgets import QPushButton

        panel = self.panel()
        chosen, every = [], []
        panel.global_family_changed.connect(chosen.append)
        panel.all_global_family_requested.connect(lambda: every.append(True))
        panel.global_family.setCurrentIndex(1)
        self.assertEqual(chosen, ['Alpha Sans'])
        buttons = [b for b in panel.findChildren(QPushButton) if b.text() == 'All global']
        self.assertEqual(len(buttons), 2)  # one for the text size, one for the font
        buttons[1].click()
        self.assertEqual(every, [True])

    def test_the_font_buttons_in_the_text_tab(self):
        # As in the settings window (asked for by the user on 2026-11-24).
        from PySide6.QtWidgets import QPushButton

        panel = self.panel()
        asked = []
        panel.add_font_requested.connect(lambda: asked.append('add'))
        panel.fonts_folder_requested.connect(lambda: asked.append('folder'))
        for text in ('Add font...', 'Fonts folder...'):
            (button,) = [b for b in panel.findChildren(QPushButton) if b.text() == text]
            button.click()
        self.assertEqual(asked, ['add', 'folder'])


if __name__ == '__main__':
    unittest.main()
