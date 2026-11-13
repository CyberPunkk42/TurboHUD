import math
import sys
from collections import OrderedDict
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QTextLayout,
)

from turbohud.core.hud import (
    FLAG_WIDTH,
    MARGIN,
    TYRE_WIDTH,
    before_right,
    blend,
    middle_right,
    overall_right,
    snug_width,
    steady_text,
    tag_left,
    tyre_right,
)

# On Linux the desktop's default font may be a monospace or icon font; prefer a plain
# sans-serif one. Qt uses the first that is installed. Windows and macOS keep their
# system font, which draws well.
AHEAD_COLOR = '#5ee07a'  # the delta when faster than the best lap
BAR_OFF = (110, 110, 110, 170)  # a pedal bar with no input: grey
LIFT_COLOR = '#ffe14d'  # the speed while lifting (no throttle, no brake)
DRAFT_COLOR = '#5ec8ff'  # the slipstream (draft section)
BEHIND_COLOR = '#ff6b6b'  # and when slower
DELTA_BAR_TRACK = (0, 0, 0, 130)  # behind the delta bar's fill
DELTA_BAR_INSET = 2  # pixels between the delta bar and its box
DELTA_BAR_TEXT = 0.6  # the delta's text height, as a share of the bar's
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


@lru_cache(maxsize=32)
def _metrics(size):
    return QFontMetricsF(hud_font(size))


@lru_cache(maxsize=4096)
def text_advance(text, size):
    """How far the pen moves for `text`, spaces included (where the next text starts).
    Kept: the lap times and the player list measure each column's texts every frame, and
    the same texts come back (with digits as zeros, the steady ones are a handful); asking
    Qt each time was the largest part of drawing them (2026-11-12)."""
    return _metrics(size).horizontalAdvance(text)


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


def outline_width(size):
    """The width of the stroke round a letter, half of it outside: enough to read light text
    on the game's light road and sky, also without the tint behind it, and in step with the
    font, as a thick one fills in small letters (seen in the lists and the draft section)."""
    return max(1.2, size / 7)


@lru_cache(maxsize=512)
def outline_path(text, size):
    """The dark outline round a line of text, as a shape to fill. Stroking the text
    each time it is drawn took most of a frame with many texts (the lap times list);
    filling a kept shape is about five times quicker."""
    stroker = QPainterPathStroker()
    stroker.setWidth(outline_width(size))
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
    found = composed_image(text, size, color, outline, ratio) if composable(text) and have_fonts() else None
    found = found or _filled_image(text, size, color, outline, ratio)
    _images[key] = found
    _images_size += found[0].sizeInBytes()
    while _images_size > IMAGES_LIMIT and len(_images) > 1:
        _images_size -= _images.popitem(last=False)[1][0].sizeInBytes()
    return found


def _filled_image(text, size, color, outline, ratio):
    """text_image's (image, left, top), filled from the text's shapes: the names and labels."""
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
    return image, left, top


# Running times and gaps change every frame, and each new one took about 0.9 ms to fill at 2x
# (0.6 ms of it the outline): 17 a frame in the lap times and the player list, about 12 ms a
# frame in the tester's log (2026-11-12). Such texts are put together from images of their
# glyphs, each filled once: about 0.05 ms. Qt still shapes the text (its spacing, even digits,
# the colon raised between digits), and a glyph is placed to 1/GLYPH_PHASES of a device pixel,
# so only a few edge pixels differ, by a little (at most 28 of 255 in a check of 45 texts).
COMPOSED_CHARACTERS = frozenset('0123456789:.,+-−()%/ sLPITCUJMFinkmh')  # times, gaps, timers, speeds
GLYPH_PHASES = 64  # places kept for a glyph within a device pixel
PIECES_LIMIT = 16 * 1024 * 1024  # bytes of glyph images kept
_pieces = OrderedDict()  # (font, glyph, size, ratio, phase, outline?) -> (image, left, top) or None
_pieces_size = 0


@lru_cache(maxsize=1)
def have_fonts():
    """Whether Qt found any font. Without one (Qt's offscreen platform on Windows, as the
    tests run it) the fallback font's glyphs crash Python when asked their font's name
    (seen 2026-11-12), so texts are then filled whole as before composed_image."""
    return bool(QFontDatabase.families())


def composable(text):
    """Whether `text` is drawn from glyph images (composed_image): a changing number."""
    return bool(text) and COMPOSED_CHARACTERS.issuperset(text)


def _font_key(raw):
    return raw.familyName(), raw.styleName(), raw.weight(), raw.pixelSize()


_glyph_shapes = {}  # (_font_key, glyph, size) -> (shape, outline)


def _glyph_paths(font, raw_font, glyph, size):
    """(shape, outline) of one glyph, as text_path and outline_path make them for text.
    `font` is _font_key(raw_font). Kept: a few hundred at most (digits and signs per size)."""
    found = _glyph_shapes.get((font, glyph, size))
    if found is not None:
        return found
    path = raw_font.pathForGlyph(glyph)
    path.setFillRule(Qt.WindingFill)
    shape = path.simplified()
    stroker = QPainterPathStroker()
    stroker.setWidth(outline_width(size))
    stroker.setCapStyle(Qt.RoundCap)
    stroker.setJoinStyle(Qt.RoundJoin)
    found = _glyph_shapes[(font, glyph, size)] = (shape, stroker.createStroke(shape))
    return found


def _glyph_piece(raw_font, glyph, size, ratio, phase, edge):
    """(image, left, top) of a glyph's outline (`edge`) or its letter, white, `phase` of
    GLYPH_PHASES right of a whole device pixel; None for an empty glyph (a space)."""
    global _pieces_size
    font = _font_key(raw_font)
    key = (font, glyph, size, ratio, phase, edge)
    if key in _pieces:
        _pieces.move_to_end(key)
        return _pieces[key]
    shape, outline = _glyph_paths(font, raw_font, glyph, size)
    path = outline if edge else shape
    shift = phase / GLYPH_PHASES / ratio
    box = path.boundingRect().translated(shift, 0)
    found = None
    if not box.isEmpty():
        left, top = math.floor(box.left() * ratio) / ratio, math.floor(box.top() * ratio) / ratio
        image = QImage(
            max(1, math.ceil((box.right() - left) * ratio)),
            max(1, math.ceil((box.bottom() - top) * ratio)),
            QImage.Format_ARGB32_Premultiplied,
        )
        image.setDevicePixelRatio(ratio)
        image.fill(0)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(shift - left, -top)
        painter.fillPath(path, QColor(Qt.white))
        painter.end()
        found = (image, left, top)
        _pieces_size += image.sizeInBytes()
    _pieces[key] = found
    while _pieces_size > PIECES_LIMIT and len(_pieces) > 1:
        dropped = _pieces.popitem(last=False)[1]
        if dropped is not None:
            _pieces_size -= dropped[0].sizeInBytes()
    return found


def _shaped(text, size):
    """[(raw font, glyph, x, y)] of `text` as Qt lays it out, from its start on the baseline."""
    layout = QTextLayout(text, hud_font(size))
    layout.beginLayout()
    line = layout.createLine()
    layout.endLayout()
    ascent = line.ascent()
    glyphs = []
    for run in layout.glyphRuns():
        raw_font = run.rawFont()
        for glyph, at in zip(run.glyphIndexes(), run.positions()):
            glyphs.append((raw_font, glyph, at.x(), at.y() - ascent))
    return glyphs


def composed_image(text, size, color, outline, ratio):
    """text_image's (image, left, top), put together from glyph images: the outlines first,
    as one shape given the outline's colour (overlapping outlines do not darken), then the
    letters. None where Qt gives no glyphs."""
    parts = {True: [], False: []}
    for raw_font, glyph, x, y in _shaped(text, size):
        whole = math.floor(x * ratio)
        phase = min(round((x * ratio - whole) * GLYPH_PHASES), GLYPH_PHASES - 1)
        for edge in (True, False):
            found = _glyph_piece(raw_font, glyph, size, ratio, phase, edge)
            if found is not None:
                image, left, top = found
                parts[edge].append((image, whole / ratio + left, y + top))
    every = parts[True] + parts[False]
    if not every:
        return None
    left = min(x for _image, x, _top in every)
    top = min(y for _image, _x, y in every)
    right = max(x + image.width() / ratio for image, x, _top in every)
    bottom = max(y + image.height() / ratio for image, _x, y in every)
    width, height = max(1, round((right - left) * ratio)), max(1, round((bottom - top) * ratio))
    layers = []
    for edge, rgba in ((True, outline), (False, color)):
        layer = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        layer.setDevicePixelRatio(ratio)
        layer.fill(0)
        painter = QPainter(layer)
        for image, x, y in parts[edge]:
            painter.drawImage(QPointF(x - left, y - top), image)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)  # the white takes the colour
        painter.fillRect(layer.rect(), QColor.fromRgba(rgba))
        painter.end()
        layers.append(layer)
    painter = QPainter(layers[0])
    painter.drawImage(0, 0, layers[1])
    painter.end()
    return layers[0], left, top


def outlined_text(painter, x, y, text, size, color, outline):
    """Text with a dark outline, readable over any part of the game, on whole device
    pixels: the same text then looks the same wherever it is."""
    ratio = painter.device().devicePixelRatioF()
    image, left, top = text_image(text, size, color.rgba(), outline.rgba(), ratio)
    painter.drawImage(QPointF(round((x + left) * ratio) / ratio, round((y + top) * ratio) / ratio), image)


@lru_cache(maxsize=256)
def cap_height(size):
    """How tall a capital letter or digit of the HUD's font is, in pixels."""
    return _metrics(size).capHeight()


@lru_cache(maxsize=4096)
def text_ink(text, size):
    """How far a line of HUD text reaches (above, below) its baseline, with its outline."""
    box = text_path(text, size).boundingRect()
    outline = outline_width(size) / 2
    return -box.top() + outline, box.bottom() + outline


@lru_cache(maxsize=4096)
def text_width(text, size):
    """How wide a line of HUD text is, in pixels, with its outline."""
    return text_path(text, size).boundingRect().right() + outline_width(size)


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


def draw_sectors(painter, bars, colours):
    """The sector bars from turbohud.core.hud.sector_bars, each in its colour from
    `colours` ('#rrggbb'), grey while its sector is still to come (None)."""
    painter.setPen(QPen(QColor(0, 0, 0, 160), 1))
    for bar, colour in zip(bars, colours):
        radius = min(bar.height / 2, 3)
        painter.setBrush(QColor(colour) if colour else QColor(*BAR_OFF))
        painter.drawRoundedRect(QRectF(bar.x, bar.y, bar.width, bar.height), radius, radius)


EMOJI_FAMILIES = ['Noto Color Emoji', 'Apple Color Emoji', 'Segoe UI Emoji', 'Twemoji']


@lru_cache(maxsize=1)
def emoji_family():
    """An installed colour emoji font for flags, or None (flags then show as codes)."""
    from PySide6.QtGui import QFontDatabase

    installed = set(QFontDatabase.families())
    return next((family for family in EMOJI_FAMILIES if family in installed), None)


FLAG_HEIGHT = 0.7  # a game flag's box: this many font sizes high ...
FLAG_BOX_WIDTH = 1.2  # ... and at most this wide; FLAG_WIDTH leaves the rest before the text
FLAG_MIDDLE = 0.36  # its middle this many font sizes above the baseline, level with the letters
_flag_folder = None  # TSU's flags read by turbohud.tsu.gameflags, once they are there


def use_game_flags(folder):
    """Draw flags from the PNGs in `folder` (turbohud.tsu.gameflags); None: emoji again."""
    global _flag_folder
    _flag_folder = folder
    _flag_file.cache_clear()
    _flag_image.cache_clear()


@lru_cache(maxsize=256)
def _flag_file(code):
    if _flag_folder is None:
        return None
    image = QImage(str(_flag_folder / f'{code}.png'))
    return None if image.isNull() else image


@lru_cache(maxsize=512)
def _flag_image(code, height, most_width):
    """The game's flag for `code` fitted, keeping its shape, into `most_width` x `height`
    device pixels, or None without one."""
    image = _flag_file(code)
    if image is None:
        return None
    width = image.width() * height / image.height()
    if width > most_width:
        width, height = most_width, image.height() * most_width / image.width()
    return image.scaled(
        max(1, round(width)), max(1, round(height)), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
    )


def flag_box(x, baseline, size, image_width, image_height):
    """Where a game flag `image_width` x `image_height` (logical pixels) goes: in the
    middle of its box (FLAG_BOX_WIDTH x FLAG_HEIGHT font sizes), level with the text."""
    left = x + (FLAG_BOX_WIDTH * size - image_width) / 2
    top = baseline - FLAG_MIDDLE * size - image_height / 2
    return QRectF(left, top, image_width, image_height)


def draw_flag(painter, x, baseline, code, size, outline):
    """A country flag from its code: TSU's own image where it was read from the game
    (all of the same height, and none wider than its box), else an emoji where a colour
    emoji font is installed, else the code as text."""
    from turbohud.core.flags import flag_emoji

    ratio = painter.device().devicePixelRatioF() if painter.device() is not None else 1.0
    image = _flag_image(code, round(FLAG_HEIGHT * size * ratio), round(FLAG_BOX_WIDTH * size * ratio))
    if image is not None:
        box = flag_box(x, baseline, size, image.width() / ratio, image.height() / ratio)
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.drawImage(box, image)
        edge = QColor(outline)
        edge.setAlpha(min(edge.alpha(), 140))
        painter.setPen(QPen(edge, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(box)  # a thin edge: white flags stay apart from a light game behind
        painter.restore()
        return
    family = emoji_family()
    if family and len(code) == 2 and code.isalpha():
        font = QFont(family)
        font.setPixelSize(max(1, round(size * 1.1)))
        painter.setFont(font)
        painter.setPen(QColor('white'))
        painter.drawText(QPointF(x, baseline), flag_emoji(code))
    else:
        outlined_text(painter, x, baseline, code, max(1, round(size * 0.55)), QColor('white'), outline)


RULE_LABEL = 0.62  # a class line's label, in font sizes of the row below it
RULE_MIDDLE = 1.06  # the line this many font sizes above the row's baseline: amid the gap above it


def draw_rule(painter, x, right, line, color, outline):
    """The line above a row that starts a class in the lap times: its label, then a thin
    line to `right` (the box's right margin), in the gap between the rows."""
    size = max(6, round(line.size * RULE_LABEL))
    middle = line.baseline - RULE_MIDDLE * line.size
    outlined_text(painter, x, middle + 0.36 * size, line.rule, size, color, outline)
    start = x + text_advance(line.rule, size) + 0.3 * line.size
    end = right if right is not None else start + 6 * line.size
    if end <= start:
        return
    pen_color = QColor(color)
    pen_color.setAlpha(190)
    painter.save()
    painter.setPen(QPen(pen_color, max(1.0, line.size / 13)))
    painter.drawLine(QPointF(start, middle), QPointF(end, middle))
    painter.restore()


TYRE_RING = 0.13  # a tire compound ring's line, in font sizes
TYRE_LETTER = 0.78  # its letter's size, as a share of the line's
TYRE_INSIDE = (0, 0, 0, 150)  # behind the letter, so it reads on any background


def draw_tyre(painter, right, line, outline):
    """A tire compound as in F1: its letter in a ring of its colour, the column ending at
    `right`, centred on the line's text."""
    size = line.size
    radius = (TYRE_WIDTH * size - TYRE_RING * size) / 2
    centre = QPointF(right - TYRE_WIDTH * size / 2, line.baseline - cap_height(size) / 2)
    color = QColor(line.tyre_color or '#ffffff')
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(color, max(1.5, TYRE_RING * size)))
    painter.setBrush(QColor(*TYRE_INSIDE))
    painter.drawEllipse(centre, radius, radius)
    painter.restore()
    letter = max(6, round(size * TYRE_LETTER))
    x = centre.x() - text_advance(line.tyre, letter) / 2
    outlined_text(painter, x, centre.y() + cap_height(letter) / 2, line.tyre, letter, color, outline)


def centred_x(line, width, margin):
    """Where a line starts in the middle of a box `width` wide, between its margins."""
    steady = text_advance(steady_text((line.slot or line.text) + line.tail), line.size)
    return max(round((width - steady) / 2), margin)


def draw_hud(painter, lines, theme, scale=None, left=0, width=None, centre=False, reserve=(), snug=False):
    """Draw the lines from turbohud.core.hud.hud_lines with the theme's colours, at
    `scale` (the theme's own by default). `centre`: each line in the middle of a box
    `width` wide, for lines without columns. `reserve`: lines (the section's usual content)
    whose columns are made room for too, so the columns stay put as the content changes
    (a longer gap or tag moved the player list's columns: reported by the user on 2026-11-12).
    `snug`: the columns right after the longest text, not at the box's right edge (snug_width)."""
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
    middle_end = before_end = tag_start = tyre_end = overall_end = None
    if width is not None:
        # With digits as zeros, so that the columns stay put as a timer runs.
        def steady_advance(text, size):
            return text_advance(steady_text(text), size)

        placed = list(lines) + list(reserve)
        if snug and not centre:
            width = snug_width(lines, reserve, width, margin, steady_advance)
        middle_end = middle_right(placed, width, margin, steady_advance)
        tyre_end = tyre_right(placed, middle_end, steady_advance)
        before_end = before_right(placed, middle_end, steady_advance, tyre_end)
        tag_start = tag_left(placed, before_end, steady_advance)
        overall_end = overall_right(placed, middle_end, tyre_end, before_end, tag_start, steady_advance)
    for line in lines:
        text_x = centred_x(line, width, margin) if (centre or line.centred) and width is not None else x
        if line.rule:
            right = left + width - margin if width is not None else None
            draw_rule(painter, x, right, line, _pick(colors, line.rule_color or 'accent'), outline)
        if line.flag:
            draw_flag(painter, x, line.baseline, line.flag, line.size, outline)
            text_x = x + FLAG_WIDTH * line.size
        # In a slot, the text ends where the slot does, whatever its length, and the tail
        # stays put: only the number changes.
        slot = text_advance(steady_text(line.slot), line.size) if line.slot else None
        number_x = text_x + slot - text_advance(line.text, line.size) if line.slot else text_x
        outlined_text(
            painter, number_x, line.baseline, line.text, line.size, _pick(colors, line.color), outline
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
        if line.tyre and tyre_end is not None:
            draw_tyre(painter, tyre_end, line, outline)
        if line.tag and tag_start is not None:
            tag_color = _pick(colors, line.tag_color or line.color)
            outlined_text(painter, tag_start, line.baseline, line.tag, line.size, tag_color, outline)
        if line.overall and overall_end is not None:
            outlined_text(
                painter,
                overall_end - text_advance(line.overall, line.size),
                line.baseline,
                line.overall,
                line.size,
                _pick(colors, line.color),
                outline,
            )
        if line.before and before_end is not None:
            outlined_text(
                painter,
                before_end - text_advance(line.before, line.size),
                line.baseline,
                line.before,
                line.size,
                _pick(colors, line.color),
                outline,
            )
        if line.tail:
            # From the width with digits as zeros, so that the tail stays as a number runs.
            tail_x = text_x + (slot if line.slot else text_advance(steady_text(line.text), line.size))
            outlined_text(
                painter, tail_x, line.baseline, line.tail, line.size, _pick(colors, line.tail_color), outline
            )


def delta_bar_parts(width, height, fill):
    """(the bar's rectangle, where it fills, the x of its middle) in a box of that size, as
    (x, y, width, height). `fill`: -1 to 1, left to right from the middle."""
    inset = DELTA_BAR_INSET
    inner = width - 2 * inset
    middle = width / 2
    reach = abs(fill) * inner / 2
    left = middle - reach if fill < 0 else middle
    return (inset, inset, inner, height - 2 * inset), (left, inset, reach, height - 2 * inset), middle


DELTA_BAR_DARKER = 130  # the fill a little darker than the text colours, so the white delta reads on it


def delta_bar_color(trend):
    """'#rrggbb' for a delta bar's `trend`: green at -1 (gaining), red at 1 (losing), and
    in between, through yellow, only while it fades from one to the other."""
    return blend(AHEAD_COLOR, BEHIND_COLOR, (trend + 1) / 2)


def draw_delta_bar(painter, width, height, fill, trend, text, theme):
    """The delta bar: a dark track with round ends, filled from the middle (right when
    ahead), green while gaining and red while losing, with the delta over it."""
    track, filled, middle = delta_bar_parts(width, height, fill)
    radius = track[3] / 2
    outline = QPainterPath()
    outline.addRoundedRect(QRectF(*track), radius, radius)
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(*DELTA_BAR_TRACK))
    painter.drawPath(outline)
    painter.setClipPath(outline)  # the fill's outer end follows the round end; the middle stays straight
    painter.fillRect(QRectF(*filled), QColor(delta_bar_color(trend)).darker(DELTA_BAR_DARKER))
    painter.fillRect(QRectF(middle - 1, track[1], 2, track[3]), QColor(255, 255, 255, 170))
    painter.restore()
    size = max(round(height * DELTA_BAR_TEXT), 8)
    x = (width - text_advance(steady_text(text), size)) / 2
    baseline = (height + cap_height(size)) / 2
    outlined_text(painter, x, baseline, text, size, QColor(theme.text_color), _rgba(theme.outline_color))


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
