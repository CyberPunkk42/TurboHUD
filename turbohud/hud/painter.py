import math
import sys
from collections import OrderedDict
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
)

from turbohud.core.hud import FLAG_WIDTH, MARGIN, middle_right, steady_text

# On Linux the desktop's default font may be a monospace or icon font; prefer a plain
# sans-serif one. Qt uses the first that is installed. Windows and macOS keep their
# system font, which draws well.
AHEAD_COLOR = '#5ee07a'  # the delta when faster than the best lap
BAR_OFF = (110, 110, 110, 170)  # a pedal bar with no input: grey
LIFT_COLOR = '#ffe14d'  # the speed while lifting (no throttle, no brake)
DRAFT_COLOR = '#5ec8ff'  # the slipstream (draft section)
BEHIND_COLOR = '#ff6b6b'  # and when slower
LINUX_FAMILIES = ['Noto Sans', 'DejaVu Sans', 'Liberation Sans', 'Cantarell', 'Ubuntu', 'Arial']


@lru_cache(maxsize=32)
def hud_font(size):
    font = QFont()
    if sys.platform.startswith('linux'):
        font.setFamilies(LINUX_FAMILIES)
    font.setPixelSize(size)
    font.setBold(True)
    # Digits all as wide, where the font can: a running number then does not push what
    # follows it, or shake when it is centred or at the right.
    font.setFeature(QFont.Tag('tnum'), 1)
    return font


def text_advance(text, size):
    """How far the pen moves for `text`, spaces included (where the next text starts)."""
    return QFontMetricsF(hud_font(size)).horizontalAdvance(text)


@lru_cache(maxsize=512)
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


@lru_cache(maxsize=512)
def outline_path(text, size):
    """The dark outline round a line of text, as a shape to fill. Stroking the text
    each time it is drawn took most of a frame with many texts (the lap times list);
    filling a kept shape is about five times quicker."""
    stroker = QPainterPathStroker()
    stroker.setWidth(max(2.0, size / 10))
    stroker.setCapStyle(Qt.RoundCap)
    stroker.setJoinStyle(Qt.RoundJoin)
    return stroker.createStroke(text_path(text, size))


IMAGES_LIMIT = 64 * 1024 * 1024  # bytes of text images kept: large fonts take far more than small
_images = OrderedDict()  # (text, size, color, outline, ratio) -> (image, left, top), oldest first
_images_size = 0


def text_image(text, size, color, outline, ratio):
    """(image, left, top) of a line of outlined text, for `ratio` device pixels to a pixel;
    `left` and `top` are from the text's start on its baseline to the image's corner.
    `color` and `outline` are QColor.rgba() values.

    Filling the shapes of a letter holds Python's lock and takes long on a real window: at
    20 frames a second with many sections it left the thread reading the race a second
    behind (found with a profile of a race on the Mac). The texts come back, as a lap
    runs through the same times, so each is filled once and then only copied."""
    global _images_size
    key = (text, size, color, outline, ratio)
    found = _images.get(key)
    if found is not None:
        _images.move_to_end(key)
        return found
    shape, edge = text_path(text, size), outline_path(text, size)
    box = shape.boundingRect().united(edge.boundingRect())
    left, top = math.floor(box.left() * ratio) / ratio, math.floor(box.top() * ratio) / ratio
    width = max(1, math.ceil((box.right() - left) * ratio))
    height = max(1, math.ceil((box.bottom() - top) * ratio))
    image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(ratio)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.translate(-left, -top)
    painter.fillPath(edge, QColor.fromRgba(outline))
    painter.fillPath(shape, QColor.fromRgba(color))
    painter.end()
    found = _images[key] = (image, left, top)
    _images_size += image.sizeInBytes()
    while _images_size > IMAGES_LIMIT and len(_images) > 1:
        _images_size -= _images.popitem(last=False)[1][0].sizeInBytes()
    return found


def outlined_text(painter, x, y, text, size, color, outline):
    """Text with a dark outline, readable over any part of the game, on whole device
    pixels: the same text then looks the same wherever it is."""
    ratio = painter.device().devicePixelRatioF()
    image, left, top = text_image(text, size, color.rgba(), outline.rgba(), ratio)
    painter.drawImage(QPointF(round((x + left) * ratio) / ratio, round((y + top) * ratio) / ratio), image)


def cap_height(size):
    """How tall a capital letter or digit of the HUD's font is, in pixels."""
    return QFontMetricsF(hud_font(size)).capHeight()


def text_ink(text, size):
    """How far a line of HUD text reaches (above, below) its baseline, with its outline."""
    box = text_path(text, size).boundingRect()
    outline = max(2.0, size / 10) / 2
    return -box.top() + outline, box.bottom() + outline


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


def draw_level(painter, bar):
    """A level bar from turbohud.core.hud.level_bar: grey, lit from the left."""
    colors = {
        'ahead': QColor(AHEAD_COLOR),
        'behind': QColor(BEHIND_COLOR),
        'lift': QColor(LIFT_COLOR),
        'draft': QColor(DRAFT_COLOR),
    }
    radius = min(bar.height / 2, 3)
    painter.setPen(QPen(QColor(0, 0, 0, 160), 1))
    painter.setBrush(QColor(*BAR_OFF))
    painter.drawRoundedRect(QRectF(bar.x, bar.y, bar.width, bar.height), radius, radius)
    if bar.fill > 0:
        painter.setBrush(colors[bar.color])
        painter.drawRoundedRect(QRectF(bar.x, bar.y, bar.width * bar.fill, bar.height), radius, radius)


EMOJI_FAMILIES = ['Noto Color Emoji', 'Apple Color Emoji', 'Segoe UI Emoji', 'Twemoji']


@lru_cache(maxsize=1)
def emoji_family():
    """An installed colour emoji font for flags, or None (flags then show as codes)."""
    from PySide6.QtGui import QFontDatabase

    installed = set(QFontDatabase.families())
    return next((family for family in EMOJI_FAMILIES if family in installed), None)


def draw_flag(painter, x, baseline, code, size, outline):
    """A country flag from its ISO code: as an emoji where a colour emoji font is
    installed, else the code as text."""
    from turbohud.core.flags import flag_emoji

    family = emoji_family()
    if family and len(code) == 2 and code.isalpha():
        font = QFont(family)
        font.setPixelSize(max(1, round(size * 1.1)))
        painter.setFont(font)
        painter.setPen(QColor('white'))
        painter.drawText(QPointF(x, baseline), flag_emoji(code))
    else:
        outlined_text(painter, x, baseline, code, max(1, round(size * 0.55)), QColor('white'), outline)


def centred_x(line, width, margin):
    """Where a line starts in the middle of a box `width` wide, between its margins."""
    steady = text_advance(steady_text(line.text + line.tail), line.size)
    return max(round((width - steady) / 2), margin)


def draw_hud(painter, lines, theme, scale=None, left=0, width=None, centre=False):
    """Draw the lines from turbohud.core.hud.hud_lines with the theme's colours, at
    `scale` (the theme's own by default). `centre`: each line in the middle of a box
    `width` wide, for lines without columns."""
    colors = {
        'text': QColor(theme.text_color),
        'accent': QColor(theme.accent_color),
        'ahead': QColor(AHEAD_COLOR),
        'behind': QColor(BEHIND_COLOR),
        'lift': QColor(LIFT_COLOR),
        'draft': QColor(DRAFT_COLOR),
    }
    outline = _rgba(theme.outline_color)
    margin = round(MARGIN * (theme.scale if scale is None else scale))
    x = left + margin
    middle_end = middle_right(lines, width, margin, text_advance) if width is not None else None
    for line in lines:
        text_x = centred_x(line, width, margin) if centre else x
        if line.flag:
            draw_flag(painter, x, line.baseline, line.flag, line.size, outline)
            text_x = x + FLAG_WIDTH * line.size
        outlined_text(
            painter, text_x, line.baseline, line.text, line.size, _pick(colors, line.color), outline
        )
        if line.right and width is not None:
            right_x = width - margin - text_advance(line.right, line.size)
            outlined_text(
                painter,
                right_x,
                line.baseline,
                line.right,
                line.size,
                _pick(colors, line.right_color),
                outline,
            )
        if line.middle and middle_end is not None:
            outlined_text(
                painter,
                middle_end - text_advance(line.middle, line.size),
                line.baseline,
                line.middle,
                line.size,
                _pick(colors, line.middle_color),
                outline,
            )
        if line.tail:
            # From the width with digits as zeros, so that the tail stays as a number runs.
            tail_x = text_x + text_advance(steady_text(line.text), line.size)
            outlined_text(
                painter, tail_x, line.baseline, line.tail, line.size, _pick(colors, line.tail_color), outline
            )


def _pick(colors, name):
    """The QColor for a row's colour: a theme name ('text', 'ahead' ...) or a colour of
    its own, '#rrggbb' (such as a blend from turbohud.core.hud.blend)."""
    if name.startswith('#'):
        return QColor(name)
    return colors[name]


def _rgba(text):
    """A QColor from '#rrggbb' or '#rrggbbaa' (Qt reads 8 digits as #aarrggbb)."""
    color = QColor(text[:7])
    if len(text) == 9:
        color.setAlpha(int(text[7:], 16))
    return color
