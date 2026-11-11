import importlib.util
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.tsu import gameflags


def aligned_text(text):
    data = text.encode()
    out = struct.pack('<i', len(data)) + data
    return out + b'\0' * (-len(out) % 4)


def texture_bytes(name, width, height, fmt, image=b'', stream=(0, 0, '')):
    """A Texture2D's bytes in Unity 2021.3's layout."""
    out = aligned_text(name)
    out += struct.pack('<i??', 4, False, True) + b'\0\0'  # fallback format, two bools, aligned
    out += struct.pack('<iiIiii', width, height, len(image), 0, fmt, 1)
    out += struct.pack('<????', False, False, False, False)
    out += struct.pack('<iii', 0, 1, 2)
    out += struct.pack('<iifiii', 1, 1, 0.0, 1, 1, 0)
    out += struct.pack('<ii', 6, 1)
    out += struct.pack('<i', 0)  # platform blob
    image_part = struct.pack('<i', len(image)) + image
    out += image_part + b'\0' * (-len(image_part) % 4)
    out += struct.pack('<QI', stream[0], stream[1]) + aligned_text(stream[2])
    return out


def serialized_file(objects, unity='2021.3.27f1', type_tree=False):
    """A format 22 serialized file holding `objects`: [(class id, bytes)]."""
    class_ids = sorted({class_id for class_id, _data in objects})
    meta = unity.encode() + b'\0' + struct.pack('<i?', 19, type_tree)
    meta += struct.pack('<i', len(class_ids))
    for class_id in class_ids:
        meta += struct.pack('<i?h', class_id, False, -1)
        if class_id == 114:
            meta += b'\x11' * 16
        meta += b'\x22' * 16
    meta += struct.pack('<i', len(objects))
    data, starts = b'', []
    for _class_id, blob in objects:
        starts.append(len(data))
        data += blob + b'\0' * (-len(blob) % 8)
    for (class_id, blob), start in zip(objects, starts, strict=True):
        meta += b'\0' * (-(48 + len(meta)) % 4)
        meta += struct.pack('<qqIi', len(starts), start, len(blob), class_ids.index(class_id))
    meta += struct.pack('<ii', 0, 0)  # scripts, externals
    data_offset = 48 + len(meta)
    data_offset += -data_offset % 16
    head = struct.pack('>4I', 0, 0, 22, 0) + b'\0\0\0\0'
    head += struct.pack('>IqqQ', len(meta), data_offset + len(data), data_offset, 0)
    return head + meta + b'\0' * (data_offset - 48 - len(meta)) + data


RED_RGBA = bytes([255, 0, 0, 255]) * 4  # 2 x 2, red
BLUE_BOTTOM_RGB = (
    bytes([0, 0, 255]) * 4 + bytes([255, 255, 255]) * 4
)  # 4 x 2: blue row first (Unity's bottom)


def game(folder, unity='2021.3.27f1'):
    """A fake TSU_Data: Germany inline (RGBA32), France streamed from the .resS (RGB24),
    a texture that is no flag, and another object."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'resources.assets.resS').write_bytes(b'xxxx' + BLUE_BOTTOM_RGB)
    objects = [
        (1, b'not a texture'),
        (28, texture_bytes('Germany', 2, 2, gameflags.FORMAT_RGBA32, RED_RGBA)),
        (28, texture_bytes('camouflage1', 2, 2, gameflags.FORMAT_RGBA32, RED_RGBA)),
        (
            28,
            texture_bytes(
                'France',
                4,
                2,
                gameflags.FORMAT_RGB24,
                stream=(4, len(BLUE_BOTTOM_RGB), 'resources.assets.resS'),
            ),
        ),
    ]
    (folder / 'resources.assets').write_bytes(serialized_file(objects, unity))
    return folder


class ReadingTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(self.temp))

    def test_textures_are_found_and_read_inline_or_from_the_ress(self):
        data = game(self.temp / 'TSU_Data')
        unity, objects = gameflags.texture_objects(data / 'resources.assets')
        self.assertEqual(unity, '2021.3.27f1')
        self.assertEqual(len(objects), 3)
        found = gameflags.game_textures(data, {'Germany', 'France', 'Nepal'})
        self.assertEqual(sorted(found), ['France', 'Germany'])
        self.assertEqual((found['Germany'].width, found['Germany'].data), (2, RED_RGBA))
        self.assertEqual(found['France'].data, BLUE_BOTTOM_RGB)

    def test_rgba_and_rgb_become_bgra(self):
        texture = gameflags.Texture('x', 2, 2, gameflags.FORMAT_RGBA32, RED_RGBA)
        self.assertEqual(gameflags.to_bgra(texture), bytes([0, 0, 255, 255]) * 4)
        texture = gameflags.Texture('x', 4, 2, gameflags.FORMAT_RGB24, BLUE_BOTTOM_RGB)
        self.assertEqual(gameflags.to_bgra(texture)[:4], bytes([255, 0, 0, 255]))
        self.assertIsNone(gameflags.to_bgra(gameflags.Texture('x', 2, 2, 999, b'')))

    def test_another_unity_version_or_type_trees_are_not_read(self):
        data = game(self.temp / 'TSU_Data', unity='2022.3.1f1')
        with self.assertRaises(gameflags.Unsupported):
            gameflags.game_textures(data, {'Germany'})
        (data / 'resources.assets').write_bytes(serialized_file([], type_tree=True))
        with self.assertRaises(gameflags.Unsupported):
            gameflags.texture_objects(data / 'resources.assets')

    def test_the_flag_keys_are_the_codes_the_rows_carry(self):
        keys = gameflags.flag_keys()
        self.assertEqual(keys['Germany'], 'DE')
        self.assertEqual(keys['Northern_Cyprus'], 'NCY')
        self.assertNotIn('None', keys)


class FindingTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(self.home))

    def test_mac_in_a_bottle_and_another_library_on_drive_c(self):
        steam = self.home / gameflags.BOTTLES / 'Steam' / 'drive_c' / 'Program Files (x86)' / 'Steam'
        (steam / 'steamapps').mkdir(parents=True)
        (steam / 'steamapps' / 'libraryfolders.vdf').write_text(
            '"libraryfolders"\n{\n "0" { "path" "C:\\\\Program Files (x86)\\\\Steam" }\n'
            ' "1" { "path" "C:\\\\Games" }\n "2" { "path" "D:\\\\Other" }\n}\n'
        )
        games = self.home / gameflags.BOTTLES / 'Steam' / 'drive_c' / 'Games'
        data = games / 'steamapps' / 'common' / gameflags.GAME_FOLDER / 'TSU_Data'
        data.mkdir(parents=True)
        (data / 'resources.assets').write_bytes(b'')
        libraries = gameflags.steam_libraries('darwin', self.home, {})
        self.assertEqual(libraries, [steam, games])  # D: is outside the bottle's drive_c
        self.assertEqual(gameflags.game_data_folder('darwin', self.home, {}), data)

    def test_linux_and_nothing_found(self):
        self.assertIsNone(gameflags.game_data_folder('linux', self.home, {}))
        data = self.home / '.local/share/Steam/steamapps/common' / gameflags.GAME_FOLDER / 'TSU_Data'
        data.mkdir(parents=True)
        (data / 'resources.assets').write_bytes(b'')
        self.assertEqual(gameflags.game_data_folder('linux', self.home, {}), data)


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class PreparingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(self.temp))

    def test_flags_are_kept_in_turbohuds_folder_and_read_again_after_a_game_update(self):
        from PySide6.QtGui import QColor, QImage

        data = game(self.temp / 'TSU_Data')
        before = sorted((p.name, p.stat().st_mtime_ns) for p in data.iterdir())
        settings = self.temp / 'settings'
        folder = gameflags.prepare_flags(settings, data)
        self.assertEqual(folder, settings / gameflags.FLAGS_FOLDER)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ['DE.png', 'FR.png', gameflags.STAMP_FILE])
        france = QImage(str(folder / 'FR.png'))
        self.assertEqual((france.width(), france.height()), (4, 2))
        self.assertEqual(
            france.pixelColor(0, 0), QColor(255, 255, 255)
        )  # Unity's bottom row is at the bottom
        self.assertEqual(france.pixelColor(0, 1), QColor(0, 0, 255))
        self.assertEqual(sorted((p.name, p.stat().st_mtime_ns) for p in data.iterdir()), before)  # only read
        (folder / 'DE.png').unlink()
        self.assertEqual(gameflags.prepare_flags(settings, data), folder)
        self.assertFalse((folder / 'DE.png').exists())  # kept from before: not read again
        stamp = json.loads((folder / gameflags.STAMP_FILE).read_text())
        stamp['files']['resources.assets'][0] += 1  # as after an update of the game
        (folder / gameflags.STAMP_FILE).write_text(json.dumps(stamp))
        gameflags.prepare_flags(settings, data)
        self.assertTrue((folder / 'DE.png').exists())

    def test_without_the_game_or_with_another_unity_the_emoji_stay(self):
        self.assertIsNone(gameflags.prepare_flags(self.temp / 'settings', self.temp / 'nowhere'))
        data = game(self.temp / 'TSU_Data', unity='2023.1.0f1')
        self.assertIsNone(gameflags.prepare_flags(self.temp / 'settings', data))

    def test_drawn_all_as_high_none_wider_than_its_box(self):
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QApplication

        from turbohud.hud import painter

        QApplication.instance() or QApplication([])
        folder = self.temp / 'flags'
        folder.mkdir()
        for code, (width, height) in {'WD': (300, 100), 'NP': (80, 100), 'DE': (160, 100)}.items():
            image = QImage(width, height, QImage.Format_ARGB32)
            image.fill(QColor('red'))
            image.save(str(folder / f'{code}.png'))
        painter.use_game_flags(folder)
        self.addCleanup(painter.use_game_flags, None)
        size = 20  # font size: a box 14 high, 24 wide
        wide, narrow, usual = (painter._flag_image(code, 14, 24) for code in ('WD', 'NP', 'DE'))
        self.assertEqual((wide.width(), wide.height()), (24, 8))  # held to the box's width
        self.assertEqual((narrow.width(), narrow.height()), (11, 14))
        self.assertEqual((usual.width(), usual.height()), (22, 14))
        self.assertIsNone(painter._flag_image('XX', 14, 24))
        box = painter.flag_box(100, 50, size, 11, 14)
        self.assertAlmostEqual(box.center().x(), 100 + painter.FLAG_BOX_WIDTH * size / 2)
        self.assertAlmostEqual(box.center().y(), 50 - painter.FLAG_MIDDLE * size)
        canvas = QImage(200, 60, QImage.Format_ARGB32)
        canvas.fill(QColor('black'))
        from PySide6.QtGui import QPainter

        drawing = QPainter(canvas)
        painter.draw_flag(drawing, 10, 40, 'DE', size, QColor(0, 0, 0, 200))
        drawing.end()
        self.assertEqual(
            canvas.pixelColor(10 + 12, 40 - 7).red(), 255
        )  # the game's flag, in the middle of its box
        painter.use_game_flags(None)
        self.assertIsNone(painter._flag_image('DE', 14, 24))  # back to the emoji


if __name__ == '__main__':
    unittest.main()
