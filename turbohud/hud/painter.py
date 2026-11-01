import sys
from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainterPath, QPen

from turbohud.core.hud import MARGIN

# On Linux the desktop's default font may be a monospace or icon font; prefer a plain
# sans-serif one. Qt uses the first that is installed. Windows and macOS keep their
# system font, which draws well.
AHEAD_COLOR = '#5ee07a'  # the delta when faster than the best lap
BAR_OFF = (110, 110, 110, 170)  # a pedal bar with no input: grey
BEHIND_COLOR = '#ff6b6b'  # and when slower
LINUX_FAMILIES = ['Noto Sans', 'DejaVu Sans', 'Liberation Sans', 'Cantarell', 'Ubuntu', 'Arial']


@lru_cache(maxsize=32)
def hud_font(size):
    font = QFont()
    if sys.platform.startswith('linux'):
        font.setFamilies(LINUX_FAMILIES)
    font.setPixelSize(size)
    font.setBold(True)
    return font


def text_advance(text, size):
    """How far the pen moves for `text`, spaces included (where the next text starts)."""
    return QFontMetricsF(hud_font(size)).horizontalAdvance(text)


@lru_cache(maxsize=256)
def text_path(text, size):
    """The outline of a line of text, with its baseline at y 0.

    Some fonts build a letter from overlapping parts (the two bars of a plus, the strokes
    of a 4). Qt fills text paths odd-even, which turns the overlaps into holes, and the
    outline traces their inner edges, so letters look broken. Filling by winding and
    simplified() merge the parts into one clean outline.
    """
    path = QPainterPath()
    path.addText(0, 0, hud_font(size), text)
    path.setFillRule(Qt.WindingFill)
    return path.simplified()


def outlined_text(painter, x, y, text, size, color, outline):
    """Text with a dark outline, readable over any part of the game."""
    path = text_path(text, size).translated(x, y)
    width = max(2.0, size / 10)
    painter.strokePath(path, QPen(outline, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.fillPath(path, color)


def text_width(text, size):
    """How wide a line of HUD text is, in pixels, with its outline."""
    return text_path(text, size).boundingRect().right() + max(2.0, size / 10)


def draw_bars(painter, bars):
    """Pedal bars from turbohud.core.hud.pedal_bars: grey, lit from the bottom."""
    colors = {'ahead': QColor(AHEAD_COLOR), 'behind': QColor(BEHIND_COLOR)}
    painter.setPen(QPen(QColor(0, 0, 0, 160), 1))
    for bar in bars:
        rect = QRectF(bar.x, bar.y, bar.width, bar.height)
        painter.setBrush(QColor(*BAR_OFF))
        painter.drawRoundedRect(rect, 3, 3)
        if bar.fill > 0:
            lit = bar.height * bar.fill
            painter.setBrush(colors[bar.color])
            painter.drawRoundedRect(QRectF(bar.x, bar.y + bar.height - lit, bar.width, lit), 3, 3)


def draw_hud(painter, lines, theme, scale=None, left=0):
    """Draw the lines from turbohud.core.hud.hud_lines with the theme's colours, at
    `scale` (the theme's own by default)."""
    colors = {
        'text': QColor(theme.text_color),
        'accent': QColor(theme.accent_color),
        'ahead': QColor(AHEAD_COLOR),
        'behind': QColor(BEHIND_COLOR),
    }
    outline = _rgba(theme.outline_color)
    x = left + round(MARGIN * (theme.scale if scale is None else scale))
    for line in lines:
        outlined_text(painter, x, line.baseline, line.text, line.size, colors[line.color], outline)
        if line.tail:
            tail_x = x + text_advance(line.text, line.size)
            outlined_text(painter, tail_x, line.baseline, line.tail, line.size, colors[line.tail_color], outline)


def _rgba(text):
    """A QColor from '#rrggbb' or '#rrggbbaa' (Qt reads 8 digits as #aarrggbb)."""
    color = QColor(text[:7])
    if len(text) == 9:
        color.setAlpha(int(text[7:], 16))
    return color
