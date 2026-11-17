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


if __name__ == '__main__':
    unittest.main()
