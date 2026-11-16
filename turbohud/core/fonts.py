"""The player's own fonts (asked for by the user on 2026-11-16): font files put in
customization/fonts, beside customization/display_presets, which the settings window offers
for the whole HUD. Only the folder and its files here; Qt reads them in turbohud.hud.painter."""

from pathlib import Path

FONTS_FOLDER = 'fonts'
FONT_FILES = ('.ttf', '.otf', '.ttc', '.otc')
README = 'README.txt'
README_TEXT = """TurboHUD fonts

Put font files (.ttf or .otf) here to draw the HUD with them. Then open TurboHUD's settings
(the icon's menu > Settings...) and choose the font under Look > Font. Fonts added while the
settings window is open show the next time it opens.

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
