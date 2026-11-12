"""TSU's own flag images, for the player list and lap times (asked for by the user on
2026-11-11, instead of the system's emoji flags, which Windows cannot show at all).

The flags are not shipped with TurboHUD: they are TSU's art. Each player's TurboHUD reads
them from that player's own copy of the game, only reading, and keeps them, made small,
in TurboHUD's own folder (`flags/`, a PNG a flag, named by the code the HUD's rows carry:
ISO code, or TEXT_FLAGS's for places without one). They are read again when the game's
files change (an update).

The game keeps them as Texture2D objects named as TS.Flag's values (core.flags.FLAGS),
mostly in `resources.assets` (Finland in `sharedassets0.assets`), as crunched DXT1 or DXT5
whose bytes lie in the `.resS` file beside it. TSU is built with Unity 2021.3 without type
trees, so the layout of a Texture2D is the one written out here (read_texture); another
Unity version is not read (the HUD keeps the emoji flags). The crunched images are
unpacked by texture2ddecoder (MIT).
"""

import json
import logging
import os
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from turbohud.core.flags import FLAGS, TEXT_FLAGS

log = logging.getLogger(__name__)

GAME_FOLDER = 'Turbo Sliders Unlimited'
FLAGS_FOLDER = 'flags'
STAMP_FILE = 'source.json'
FLAG_HEIGHT = 48  # pixels a flag is kept at: about twice the largest it is drawn
UNITY_VERSIONS = ('2021.3.',)  # the Texture2D layout below is this version's
TEXTURE2D = 28  # Unity's class id
FORMAT_RGB24, FORMAT_RGBA32, FORMAT_DXT1, FORMAT_DXT5 = 3, 4, 10, 12
FORMAT_DXT1_CRUNCHED, FORMAT_DXT5_CRUNCHED = 28, 29
STAMP_VERSION = 1  # raise to read the flags again after a change here
BOTTLES = Path('Library') / 'Application Support' / 'CrossOver' / 'Bottles'


class Unsupported(ValueError):
    """A file TurboHUD cannot read the flags from."""


@dataclass(frozen=True)
class Texture:
    name: str
    width: int
    height: int
    format: int
    data: bytes  # the image bytes (all its mipmaps), from the file or its .resS


class _Bytes:
    def __init__(self, data, endian='<'):
        self.data, self.pos, self.endian = data, 0, endian

    def take(self, fmt):
        fmt = self.endian + fmt
        value = struct.unpack_from(fmt, self.data, self.pos)
        self.pos += struct.calcsize(fmt)
        return value[0] if len(value) == 1 else value

    def raw(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise Unsupported('past the end')
        value = self.data[self.pos : self.pos + count]
        self.pos += count
        return value

    def align(self):
        self.pos = (self.pos + 3) & ~3

    def text_to_null(self):
        end = self.data.index(b'\0', self.pos)
        value = self.data[self.pos : end].decode('utf-8', 'replace')
        self.pos = end + 1
        return value

    def text(self):
        value = self.raw(self.take('i')).decode('utf-8', 'replace')
        self.align()
        return value


def texture_objects(file):
    """(the file's Unity version, [(start, size)] of every Texture2D in it): from a
    serialized file of format 22 (Unity 2020.1 and later) without type trees."""
    with open(file, 'rb') as handle:
        head = handle.read(48)
        if len(head) < 48:
            raise Unsupported('too short')
        _size, _file, version, _offset = struct.unpack_from('>4I', head)
        if version < 22:
            raise Unsupported(f'format {version}')
        endian = '>' if head[16] else '<'
        metadata_size, _file_size, data_offset, _unknown = struct.unpack_from('>IqqQ', head, 20)
        meta = _Bytes(handle.read(metadata_size), endian)
    unity = meta.text_to_null()
    meta.take('i')  # target platform
    if meta.take('?'):
        raise Unsupported('type trees')  # this reader knows only files without them
    types = []
    for _ in range(meta.take('i')):
        class_id = meta.take('i')
        meta.take('?')  # stripped
        meta.take('h')  # script type index
        if class_id == 114:  # MonoBehaviour: a script id first
            meta.raw(16)
        meta.raw(16)  # type hash
        types.append(class_id)
    found = []
    for _ in range(meta.take('i')):
        meta.align()  # to 4 bytes in the whole file: the metadata starts at 48
        meta.take('q')  # path id
        start = meta.take('q')
        size = meta.take('I')
        type_index = meta.take('i')
        if 0 <= type_index < len(types) and types[type_index] == TEXTURE2D:
            found.append((data_offset + start, size))
    return unity, found


def read_texture(data, folder, wanted=None):
    """The Texture in a Texture2D's bytes (Unity 2021.3's layout), its image from the
    `.resS` file in `folder` where it is streamed; None when its name is not `wanted`."""
    reader = _Bytes(data)
    name = reader.text()
    if wanted is not None and name not in wanted:
        return None
    reader.take('i')  # forced fallback format
    reader.take('??')  # downscale fallback, alpha channel optional
    reader.align()
    width, height = reader.take('ii')
    reader.take('Ii')  # complete image size, mips stripped
    fmt = reader.take('i')
    reader.take('i')  # mip count
    reader.take('????')  # readable, preprocessed, ignore master texture limit, streaming mipmaps
    reader.align()
    reader.take('iii')  # streaming priority, image count, dimension
    reader.take('iifiii')  # texture settings
    reader.take('ii')  # lightmap format, colour space
    reader.raw(reader.take('i'))  # platform blob
    reader.align()
    image = reader.raw(reader.take('i'))
    reader.align()
    offset, size = reader.take('QI')
    path = reader.text()
    if not 0 < width <= 4096 or not 0 < height <= 4096:
        raise Unsupported(f'{name}: {width} x {height}')
    if not image and size:
        stream = Path(folder) / Path(path).name  # only ever beside the file read
        with open(stream, 'rb') as handle:
            handle.seek(offset)
            image = handle.read(size)
        if len(image) != size:
            raise Unsupported(f'{name}: short image')
    return Texture(name, width, height, fmt, image)


def to_bgra(texture):
    """The texture's first image as rows of BGRA bytes, bottom row first (as Unity keeps
    them), or None for a format not known here."""
    width, height, data = texture.width, texture.height, texture.data
    if texture.format in (FORMAT_DXT1_CRUNCHED, FORMAT_DXT5_CRUNCHED, FORMAT_DXT1, FORMAT_DXT5):
        try:
            import texture2ddecoder
        except ImportError:
            return None  # not installed: that flag stays an emoji

        if texture.format in (FORMAT_DXT1_CRUNCHED, FORMAT_DXT5_CRUNCHED):
            data = texture2ddecoder.unpack_unity_crunch(data)
        if texture.format in (FORMAT_DXT1_CRUNCHED, FORMAT_DXT1):
            return texture2ddecoder.decode_bc1(data, width, height)
        return texture2ddecoder.decode_bc3(data, width, height)
    if texture.format == FORMAT_RGBA32:
        pixels = data[: width * height * 4]
        out = bytearray(len(pixels))
        out[0::4], out[1::4], out[2::4], out[3::4] = pixels[2::4], pixels[1::4], pixels[0::4], pixels[3::4]
        return bytes(out)
    if texture.format == FORMAT_RGB24:
        pixels = data[: width * height * 3]
        out = bytearray(b'\xff' * (width * height * 4))
        out[0::4], out[1::4], out[2::4] = pixels[2::3], pixels[1::3], pixels[0::3]
        return bytes(out)
    return None


def flag_keys():
    """{TS.Flag name: the code a row carries for it (core.flags.flag_code or TEXT_FLAGS)}."""
    return {name: code or TEXT_FLAGS.get(name) for name, code in FLAGS[1:] if code or name in TEXT_FLAGS}


def game_textures(data_folder, wanted):
    """Every Texture2D named in `wanted` in the game's asset files, read only. Raises
    Unsupported for a Unity version whose layout is not known here."""
    found = {}
    files = sorted(Path(data_folder).glob('*.assets'), key=lambda p: p.name != 'resources.assets')
    for file in files:
        try:
            unity, objects = texture_objects(file)
        except (Unsupported, OSError, struct.error, ValueError) as error:
            log.info('flags: %s skipped (%s)', file.name, error)
            continue
        if not unity.startswith(UNITY_VERSIONS):
            raise Unsupported(f'Unity {unity}')
        with open(file, 'rb') as handle:
            for start, size in objects:
                handle.seek(start)
                try:
                    texture = read_texture(handle.read(size), data_folder, wanted)
                except (Unsupported, OSError, struct.error, ValueError) as error:
                    log.info('flags: a texture in %s skipped (%s)', file.name, error)
                    continue
                if texture is not None and texture.name not in found:
                    found[texture.name] = texture
        if len(found) == len(wanted):
            break
    return found


# Where Windows records Steam's folder: the user's key (written by Steam at each start), then
# the installer's. Steam may be anywhere (D:\Steam), not only under Program Files.
STEAM_REGISTRY = (
    ('HKEY_CURRENT_USER', r'Software\Valve\Steam', 'SteamPath'),
    ('HKEY_LOCAL_MACHINE', r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath'),
    ('HKEY_LOCAL_MACHINE', r'SOFTWARE\Valve\Steam', 'InstallPath'),
)


def read_registry(hive, key, name):
    """A text value from the Windows registry, or None (not there, or not on Windows)."""
    try:
        import winreg

        with winreg.OpenKey(getattr(winreg, hive), key) as handle:
            value, _kind = winreg.QueryValueEx(handle, name)
    except (ImportError, OSError):
        return None
    return value if isinstance(value, str) and value else None


def steam_libraries(platform=sys.platform, home=None, environ=None, registry=read_registry):
    """Steam's library folders where TSU may be: Steam's own folder and those its
    libraryfolders.vdf names (on the Mac, inside each CrossOver bottle, drive C only; on
    Windows, Steam's folder from the registry first, then under Program Files)."""
    home = Path.home() if home is None else Path(home)
    environ = os.environ if environ is None else environ
    roots = []
    if platform == 'darwin':
        try:
            bottles = sorted(p for p in (home / BOTTLES).iterdir() if p.is_dir())
        except OSError:
            bottles = []
        for bottle in bottles:
            for program_files in ('Program Files (x86)', 'Program Files'):
                roots.append((bottle / 'drive_c' / program_files / 'Steam', bottle / 'drive_c'))
    elif platform == 'win32':
        for hive, key, name in STEAM_REGISTRY:
            value = registry(hive, key, name)
            if value:
                roots.append((Path(value), None))
        for key in ('PROGRAMFILES(X86)', 'PROGRAMFILES'):
            if environ.get(key):
                roots.append((Path(environ[key]) / 'Steam', None))
    else:
        for root in (
            '.local/share/Steam',
            '.steam/steam',
            '.var/app/com.valvesoftware.Steam/.local/share/Steam',
        ):
            roots.append((home / root, None))
    libraries = []
    for root, drive_c in roots:
        if root in libraries or not root.is_dir():
            continue  # the registry and Program Files often name the same folder
        libraries.append(root)
        try:
            vdf = (root / 'steamapps' / 'libraryfolders.vdf').read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        for path in re.findall(r'"path"\s+"([^"]+)"', vdf):
            path = path.replace('\\\\', '\\')
            if drive_c is not None:
                if path[:3].upper() != 'C:\\':
                    continue
                library = drive_c.joinpath(*path[3:].split('\\'))
            else:
                library = Path(path)
            if library not in libraries:
                libraries.append(library)
    return libraries


def game_data_folder(platform=sys.platform, home=None, environ=None, registry=read_registry):
    """TSU's `<name>_Data` folder (with resources.assets), or None where it is not found."""
    for library in steam_libraries(platform, home, environ, registry):
        game = library / 'steamapps' / 'common' / GAME_FOLDER
        try:
            folders = sorted(game.glob('*_Data'))
        except OSError:
            continue
        for folder in folders:
            if (folder / 'resources.assets').is_file():
                return folder
    return None


def stamp(data_folder):
    """What the flags were read from: each asset file's size and change time."""
    files = {}
    for file in sorted(Path(data_folder).glob('*.assets')):
        info = file.stat()
        files[file.name] = [info.st_size, info.st_mtime_ns]
    return {'version': STAMP_VERSION, 'files': files}


def save_flags(textures, keys, folder, height=FLAG_HEIGHT):
    """Each texture as `folder/<key>.png`, `height` pixels high; returns how many."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    folder.mkdir(parents=True, exist_ok=True)
    saved = 0
    for name, texture in textures.items():
        key = keys.get(name)
        if key is None:
            continue
        try:
            pixels = to_bgra(texture)
        except (ValueError, RuntimeError) as error:  # a decoder error: that flag stays an emoji
            log.info('flags: %s not decoded (%s)', name, error)
            continue
        if pixels is None:
            log.info('flags: %s in format %d, not read', name, texture.format)
            continue
        image = QImage(pixels, texture.width, texture.height, texture.width * 4, QImage.Format_ARGB32)
        image = (
            image.flipped(Qt.Orientation.Vertical)
            if hasattr(image, 'flipped')
            else image.mirrored(False, True)
        )
        image = image.scaledToHeight(min(height, texture.height), Qt.SmoothTransformation)
        if image.save(str(folder / f'{key}.png'), 'PNG'):
            saved += 1
    return saved


def prepare_flags(settings_folder, data_folder=None):
    """Make sure `settings_folder/flags` holds the game's flags, read from the game when
    they are not there yet or the game's files changed. The folder, or None where there
    are none (no game found, an unknown Unity version). Meant for a background thread:
    no Qt GUI objects, only QImage."""
    folder = Path(settings_folder) / FLAGS_FOLDER
    data_folder = data_folder or game_data_folder()
    if data_folder is None:
        log.info(
            'flags: TSU not found in the Steam libraries %s, the emoji flags stay',
            [str(library) for library in steam_libraries()],
        )
        return folder if (folder / STAMP_FILE).exists() else None
    try:
        current = stamp(data_folder)
    except OSError as error:
        log.info('flags: the game\'s files not read (%s)', error)
        return folder if (folder / STAMP_FILE).exists() else None
    try:
        if json.loads((folder / STAMP_FILE).read_text(encoding='utf-8')) == current:
            return folder
    except (OSError, ValueError):
        pass
    keys = flag_keys()
    try:
        textures = game_textures(data_folder, set(keys))
    except Unsupported as error:
        log.info('flags: not read from the game (%s), the emoji flags stay', error)
        return None
    count = save_flags(textures, keys, folder)
    log.info('flags: %d of the game\'s %d flags read', count, len(keys))
    if count:
        (folder / STAMP_FILE).write_text(json.dumps(current) + '\n', encoding='utf-8')
        return folder
    return None
