from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen

from turbokit.core.hud import MARGIN


def outlined_text(painter, x, y, text, size, color, outline):
    """Text with a dark outline, readable over any part of the game."""
    font = QFont()
    font.setPixelSize(size)
    font.setBold(True)
    path = QPainterPath()
    path.addText(QPointF(x, y), font, text)
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
