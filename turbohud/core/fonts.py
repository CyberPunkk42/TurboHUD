"""The player's own fonts (asked for by the user on 2026-11-16): font files put in
customization/fonts, beside customization/display_presets, which the settings window offers
for the whole HUD. Only the folder and its files here; Qt reads them in turbohud.hud.painter."""

import shutil
from pathlib import Path

FONTS_FOLDER = 'fonts'
FONT_FILES = ('.ttf', '.otf', '.ttc', '.otc')
README = 'README.txt'
README_TEXT = """TurboHUD fonts

Put font files (.ttf or .otf) here to draw the HUD with them. Then open TurboHUD's settings
(the icon's menu > Settings...) and choose the font under Look > Font. Fonts added while the
settings window is open show the next time it opens. "Add font..." in the settings copies a
font file here and chooses it at once. Delete a file here to remove its font.

TurboHUD draws its text bold, so a font with a bold style looks best; it makes one where the
font has none. Letters a font lacks come from the system's font. "System font" goes back to
the usual one.
"""


def fonts_folder(presets_folder):
    """customization/fonts: beside `presets_folder` (presets.custom_folder)."""
    return Path(presets_folder).parent / FONTS_FOLDER


def ready_fonts_folder(folder):
    """Make `folder` with its read-me where missing; the folder, or None where it cannot be made."""
    try:
        Path(folder).mkdir(parents=True, exist_ok=True)
        readme = Path(folder) / README
        if not readme.exists():
            readme.write_text(README_TEXT, encoding='utf-8')
    except OSError:
        return None
    return Path(folder)


def font_files(folder):
    """The font files in `folder`, by name; none where it is missing or cannot be read."""
    try:
        return sorted(
            (p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in FONT_FILES),
            key=lambda p: p.name.lower(),
        )
    except OSError:
        return []


def font_filter():
    """The file window's filter for font files."""
    return 'Fonts (' + ' '.join(f'*{suffix}' for suffix in FONT_FILES) + ')'


def add_font_file(source, folder):
    """Copy the font file `source` into `folder` (Add font..., 2026-11-17): the copy's path, the
    file already there where it is the same one, or None where `source` is no font file or the copy
    failed. A different file of the same name is kept as "name (2).ttf" and so on, never replaced."""
    source, folder = Path(source), Path(folder)
    if source.suffix.lower() not in FONT_FILES or not source.is_file():
        return None
    try:
        if source.resolve().parent == folder.resolve():
            return source
        target = folder / source.name
        number = 2
        while target.exists():
            if target.read_bytes() == source.read_bytes():
                return target
            target = folder / f'{source.stem} ({number}){source.suffix}'
            number += 1
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    except OSError:
        return None
    return target
