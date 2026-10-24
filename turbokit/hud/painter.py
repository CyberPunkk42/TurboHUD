import sys
from functools import lru_cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen

from turbokit.core.hud import MARGIN

# On Linux the desktop's default font may be a monospace or icon font; prefer a plain
# sans-serif one. Qt uses the first that is installed. Windows and macOS keep their
# system font, which draws well.
LINUX_FAMILIES = ['Noto Sans', 'DejaVu Sans', 'Liberation Sans', 'Cantarell', 'Ubuntu', 'Arial']


@lru_cache(maxsize=256)
def text_path(text, size):
    """The outline of a line of text, with its baseline at y 0.

    Some fonts build a letter from overlapping parts (the two bars of a plus, the strokes
    of a 4). Qt fills text paths odd-even, which turns the overlaps into holes, and the
    outline traces their inner edges, so letters look broken. Filling by winding and
    simplified() merge the parts into one clean outline.
    """
    font = QFont()
    if sys.platform.startswith('linux'):
        font.setFamilies(LINUX_FAMILIES)
    font.setPixelSize(size)
    font.setBold(True)
    path = QPainterPath()
    path.addText(0, 0, font, text)
    path.setFillRule(Qt.WindingFill)
    return path.simplified()


def outlined_text(painter, x, y, text, size, color, outline):
    """Text with a dark outline, readable over any part of the game."""
    path = text_path(text, size).translated(x, y)
    width = max(2.0, size / 10)
    painter.strokePath(path, QPen(outline, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.fillPath(path, color)


def draw_hud(painter, lines, theme):
    """Draw the lines from turbokit.core.hud.hud_lines with the theme's colours."""
    colors = {'text': QColor(theme.text_color), 'accent': QColor(theme.accent_color)}
    outline = _rgba(theme.outline_color)
    x = round(MARGIN * theme.scale)
    for line in lines:
        outlined_text(painter, x, line.baseline, line.text, line.size, colors[line.color], outline)


def _rgba(text):
    """A QColor from '#rrggbb' or '#rrggbbaa' (Qt reads 8 digits as #aarrggbb)."""
    color = QColor(text[:7])
    if len(text) == 9:
        color.setAlpha(int(text[7:], 16))
    return color
