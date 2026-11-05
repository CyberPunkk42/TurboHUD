"""The HUD's windows: one per section, frameless, transparent and always on top, and the
small panel that shows in move mode.

Locked, a section lets every click through and shows only its content. In move mode it
gets a tint, can be dragged, and resized at its corner, which scales its content. A text
section's box fits closely round its text, so its name shows only when the pointer rests
on it; the others show their name. The panel says what to do, shows or hides sections, and locks or quits.
"""

import logging
import math
import sys
import time
from dataclasses import replace

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from turbohud.core.hud import (
    MARGIN,
    base_size,
    centred_text,
    content_shift,
    content_size,
    drawn_scale,
    help_lines,
    hud_lines,
    level_bar,
    level_space,
    pedal_bars,
    pedal_space,
    steady_rows,
    text_can_centre,
    tight_height,
)
from turbohud.core.race import RADAR_FULL, Blip, DeltaBarView, RadarView, radar_car_size
from turbohud.core.settings import GROUPS, PRESETS
from turbohud.core.trackmap import MapDot, TrackMapView, map_transform, outline_from_path, road_width
from turbohud.hud.painter import (
    AHEAD_COLOR,
    BEHIND_COLOR,
    DRAFT_COLOR,
    LIFT_COLOR,
    cap_height,
    draw_bars,
    draw_delta_bar,
    draw_hud,
    draw_level,
    text_ink,
    text_width,
)

TINT = (23, 56, 97, 153)  # move mode's background: red, green, blue, opacity (0-255)
BORDER = (120, 170, 230)
LABEL_COLOR = (200, 220, 245)
MIN_WIDTH = 40
MIN_HEIGHT = 10  # a text section's box: any shorter and there is nothing left to grab
BLUE_FLAG = (0, 0, 128)  # navy
BLUE_FLAG_EDGE = (0, 0, 64)  # its outline, a darker blue
BLUE_FLAG_EDGE_WIDTH = 2
PEDAL_INSET = 4  # pedal_bars' default inset
BACKDROP = (0, 0, 0, 40)  # the light tint behind a section's text (option), RGBA
BLUE_SAMPLE = 0.6  # the bar's opacity in move mode, to place it
DELTA_BAR_SAMPLE = DeltaBarView(-0.4, 0.85, '\u22120.400')  # the delta bar in move mode
LEVEL_SAMPLE = (0.7, 'ahead')  # a level bar in move mode, to place the section
RADAR_CAR_AT = 0.5  # the local car's height in the radar, from the top: the middle
CONE_STEPS = 8  # points along a slipstream cone's far edge
CONE_OUT, CONE_IN = 30, 80  # a slipstream cone's opacity (0-255): elsewhere, local car in it
RADAR_EDGE = (120, 130, 150, 200)
RADAR_LINES = (120, 130, 150, 90)
RADAR_ME = '#f2f2f2'
RADAR_OTHER = '#8c95a3'  # a car near but not counting (far to the side, or further away)
# In move mode: one car beside, one closing in behind, one ahead.
RADAR_SAMPLE = (
    Blip(-1.0, 3.0, 0.0, 0.0),
    Blip(-9.5, -1.0, 0.1, 0.3),
    Blip(11.0, 0.5, -0.05, None, False),
)
MAP_BACK = (10, 14, 22, 110)  # behind the track map, RGBA
MAP_ROAD = (205, 212, 224, 210)
MAP_ROAD_EDGE = (0, 0, 0, 170)
MAP_START = '#ffffff'
MAP_PADDING = 0.08  # room round the track, as a share of the map
MAP_DOT = 0.026  # a car's dot radius, as a share of the map
MAP_COLORS = {
    'me': '#ffffff',
    'leader': '#ffc61a',  # gold
    'ahead': BEHIND_COLOR,  # red, as a gap ahead in the player list
    'behind': AHEAD_COLOR,  # green, as a gap behind
    'backmarker': '#5b8cff',  # bluish: about to be lapped
    'other': '#8c95a3',
    'car': '#e6ebf2',  # a spectator's map: every car
}
MAP_SIZES = {
    'me': 1.15,
    'leader': 1.0,
    'ahead': 1.0,
    'behind': 1.0,
    'backmarker': 0.65,
    'other': 0.55,
    'car': 0.8,
}
MAP_OTHER_ALPHA = 150  # the other cars are faint
MAP_PIT_OPACITY = 0.4  # a car in the pits is dimmed
MAP_RING = 0.4  # the local player's ring: its width, as a share of its radius


def _sample_map():
    """A track map to place the section in move mode: an oval with a car of each kind."""

    def at(step):
        turn = 2 * math.pi * step / 40
        return (100 * math.cos(turn), 60 * math.sin(turn))

    outline = outline_from_path([at(step) for step in range(40)], True, (at(0), (0.0, 1.0)))

    roles = (('leader', 30), ('backmarker', 9), ('ahead', 13), ('behind', 2), ('me', 6))
    return TrackMapView(outline, tuple(MapDot(at(step), role) for role, step in roles))


log = logging.getLogger(__name__)


def window_flags():
    flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    if sys.platform != 'darwin':
        flags |= Qt.Tool  # no taskbar button; on the Mac a tool window hides when inactive
    return flags


def _set_input(widget, native, transparent):
    """Make a shown window click-through or not. True if it was done in place; False if
    the flag change hid the window (then it must be shown again)."""
    if getattr(native, 'input_in_place', False) and widget.windowHandle() is not None:
        # Wayland: change it on the shown window. Re-creating it would make the desktop
        # treat it as a new window (Hyprland would tile it again).
        widget.windowHandle().setFlag(Qt.WindowTransparentForInput, transparent)
        return True
    widget.setWindowFlag(Qt.WindowTransparentForInput, transparent)
    return False


class SectionWindow(QWidget):
    drawing_time = 0.0  # seconds all sections have spent drawing, for the log

    def __init__(self, native, theme, section):
        super().__init__(None, window_flags())
        self.native = native
        self.theme = theme
        self.section = section
        self.rows = []
        self.pedals = None  # (throttle, brake), 0 to 1, for a section with pedal bars
        self.opacity = None  # the blue flag's opacity, 0 to 1; None: not shown
        self.radar = None  # the radar's turbohud.core.race.RadarView; None: not shown
        self.trackmap = None  # the track map's turbohud.core.trackmap.TrackMapView; None: not shown
        self.level = None  # (0 to 1, colour) for a section with a level bar
        self.backdrop = False  # a light tint behind its text while locked (its own option)
        self.locked = True
        self.wanted = True  # the player wants it shown
        self.group = ''  # sections of the same group move together (move mode)
        self.text_centred = False  # its text in the middle of its box (an option)
        self.delta_view = None  # the delta bar's content (a DeltaBarView)
        self.radar_cone = True  # the radar's sample in move mode shows slipstream cones (an option)
        self.setWindowTitle(f'TurboHUD - {section.label}')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowTransparentForInput, True)
        width, height = base_size(section, theme.scale, text_width)
        if not section.bar:
            height = tight_height(section, theme.scale, text_ink)
            self.setToolTip(section.label)  # no room for its name in the box (move mode)
        self.base = (width, height)
        self.grip = QSizeGrip(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.addWidget(self.grip, 0, Qt.AlignBottom | Qt.AlignRight)
        self.grip.setVisible(False)
        lowest = round(self.base[1] * 0.3)
        self.setMinimumSize(MIN_WIDTH, lowest if section.bar else max(lowest, MIN_HEIGHT))

    def placement(self):
        # On Wayland only the desktop knows where the window is; ask it where possible.
        native = getattr(self.native, 'placement', None)
        return (native and native(self)) or (self.x(), self.y(), self.width(), self.height())

    def show_on_top(self):
        self.show()
        log.info('%s: %s', self.section.name, self.native.raise_window(self))

    def show_content(
        self, rows, pedals=None, opacity=None, radar=None, trackmap=None, level=None, delta_view=None
    ):
        """Take the latest content; True if it differs from what is shown, so the
        section needs drawing again. Locking, showing, the theme and the tint ask for a
        redraw themselves."""
        content = (rows, pedals, opacity, radar, trackmap, level, delta_view)
        shown = (self.rows, self.pedals, self.opacity, self.radar, self.trackmap, self.level, self.delta_view)
        if content == shown:
            return False
        self.rows, self.pedals, self.opacity, self.radar, self.trackmap, self.level, self.delta_view = content
        return True

    def set_locked(self, locked):
        if locked == self.locked:
            return
        self.locked = locked
        if not self.wanted:
            return  # hidden: stays click-through and empty in both modes
        in_place = _set_input(self, self.native, locked)
        movable = getattr(self.native, 'set_movable', None)
        if movable is not None:
            movable(self, not locked)
        self.grip.setVisible(not locked)
        self.setCursor(Qt.ArrowCursor if locked else Qt.OpenHandCursor)
        if not in_place:
            self.show_on_top()  # changing a window flag hides the window
        self.update()

    def set_wanted(self, wanted):
        """Show or hide the section (the panel's tick boxes). A hidden section keeps its
        window, draws nothing and lets every click through: showing it again then needs
        no new window, which a desktop could place anywhere, or make fullscreen over a
        fullscreen game."""
        if wanted == self.wanted:
            return
        self.wanted = wanted
        in_place = _set_input(self, self.native, self.locked or not wanted)
        movable = getattr(self.native, 'set_movable', None)
        if movable is not None:
            movable(self, wanted and not self.locked)
        self.grip.setVisible(wanted and not self.locked)
        if not in_place:
            self.show_on_top()
        self.update()

    def mousePressEvent(self, event):
        if not self.locked and event.button() == Qt.LeftButton:
            self.windowHandle().startSystemMove()

    def paintEvent(self, event):
        began = time.perf_counter()
        self._paint(event)
        SectionWindow.drawing_time += time.perf_counter() - began

    def _paint(self, _event):
        painter = QPainter(self)
        if not self.wanted:
            painter.end()
            return
        painter.setRenderHint(QPainter.Antialiasing)
        if self.section.drawing == 'radar':
            self._paint_radar(painter)
            painter.end()
            return
        if self.section.drawing == 'map':
            self._paint_map(painter)
            painter.end()
            return
        if self.section.drawing == 'delta':
            self._paint_delta(painter)
            painter.end()
            return
        if self.section.bar:
            self._paint_bar(painter)
            painter.end()
            return
        rows = self.rows
        if not self.locked:
            painter.setPen(QPen(QColor(*BORDER), 2))
            painter.setBrush(QColor(*TINT))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
            rows = rows or list(self.section.samples[0])  # something to place, also before a race
        bars = pedal_space(self.theme.scale) if self.section.pedals else 0
        scale = drawn_scale(
            self.section,
            (self.width(), self.height()),
            rows,
            self.base[1],
            self.theme.scale,
            text_ink,
            text_width,
        )
        left = 0
        down = content_shift(self.section, self.height(), scale, text_ink)
        if self.locked and self.backdrop and rows:
            self._paint_backdrop(painter, rows, scale, bars, down)
        if self.section.pedals and rows:  # no bars without a speed (menu, no game)
            throttle, brake = self.pedals or (None, None)
            draw_bars(painter, pedal_bars(self.width(), self.height(), scale, throttle, brake))
            # The bars keep to the window's edges however small the text gets.
            left, down = centred_text(
                (self.width(), self.height()), rows, scale, text_width, cap_height, pedal_space(scale) // 2
            )
        painter.translate(0, down)
        centre = self.text_centred and text_can_centre(self.section)
        draw_hud(painter, hud_lines(rows, scale), self.theme, scale, left, self.width() - left, centre)
        if self.section.level and rows:
            level = self.level or (None if self.locked else LEVEL_SAMPLE)
            if level is not None:
                content_height = content_size(rows, scale, text_width)[1]
                draw_level(painter, level_bar(self.width(), content_height, scale, *level))
        painter.translate(0, -down)
        painter.end()

    def _paint_backdrop(self, painter, rows, scale, bars, down=0):
        """The light tint, only as large as the text (and pedal bars): half the margin
        round it, moved `down` with the text and kept inside the window. A section with a
        right-hand column (the player list) is as wide as its window, where that column
        is drawn."""
        # Digits as zeros: a tint that follows them would flicker as a number runs.
        width, height = content_size(steady_rows(rows), scale, text_width)
        pad = round(MARGIN * scale / 2)
        if self.section.level:
            height += level_space(scale) + pad // 2  # the level bar, with a little room below
            width = self.width()  # the level bar spans the section
        if any(row.right for row in rows):
            width = self.width()
        else:
            width = min(width + (bars or 0), self.width())
        top = max(pad + down, 0)
        left, tall = pad, min(height - pad + down, self.height()) - top
        if self.section.pedals:
            # From the throttle bar to the brake bar, as tall as they are: the bars sit
            # at the window's edges, however wide it is.
            left, top, tall = PEDAL_INSET, PEDAL_INSET, self.height() - 2 * PEDAL_INSET
            width = self.width()
        x = left
        if self.text_centred and text_can_centre(self.section):
            x = (self.width() - width) / 2 + left  # round the text in the middle of the box
        rect = QRectF(x, top, max(width - 2 * left, 1), max(tall, 1))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(*BACKDROP))
        painter.drawRoundedRect(rect, 6, 6)

    def _paint_radar(self, painter):
        """The proximity radar: the local car in the middle heading up, the others
        where they are around it; red when beside or within RADAR_FULL behind, yellow
        when closing in behind, grey elsewhere. The whole radar fades with its opacity.
        In move mode a sample, with a border and its name."""
        view = self.radar
        if not self.locked and view is None:
            view = RadarView(BLUE_SAMPLE, RADAR_SAMPLE, cone=(30, 20))
            if not self.radar_cone:  # the sample as the race will show it
                blips = tuple(replace(blip, in_cone=None) for blip in RADAR_SAMPLE)
                view = RadarView(BLUE_SAMPLE, blips)
        if view is None:
            return
        size = min(self.width(), self.height())
        box = QRectF((self.width() - size) / 2, (self.height() - size) / 2, size, size).adjusted(1, 1, -1, -1)
        painter.setOpacity(min(max(view.opacity, 0.0), 1.0))
        painter.setBrush(Qt.NoBrush)  # no fill: the road shows through
        if not self.locked:  # to place it; in a race an outline only gets in the way of the view
            painter.setPen(QPen(QColor(*RADAR_EDGE), 1.5))
            painter.drawRoundedRect(box, 10, 10)
        # The local car sits in the middle: cars ahead count as well as those behind.
        # view.view reaches from it to the top and the bottom edge.
        centre = QPointF(box.center().x(), box.top() + box.height() * RADAR_CAR_AT)
        per_unit = box.height() * (1 - RADAR_CAR_AT) / view.view
        w, h = radar_car_size(per_unit, box.width())
        painter.setPen(QPen(QColor(*RADAR_LINES), 1))
        painter.drawLine(QPointF(centre.x(), box.top() + 6), QPointF(centre.x(), box.bottom() - 6))
        painter.drawLine(QPointF(box.left() + 6, centre.y()), QPointF(box.right() - 6, centre.y()))
        painter.setClipRect(box)

        def car(ahead, side, angle, color):
            painter.save()
            painter.translate(centre.x() + side * per_unit, centre.y() - ahead * per_unit)
            painter.rotate(math.degrees(angle))
            painter.setPen(QPen(QColor(0, 0, 0, 160), 1))
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(-w / 2, -h / 2, w, h), w / 4, w / 4)
            painter.restore()

        def cone(blip):
            """The slipstream behind a car ahead: from its tail, the event's reach long
            and its angle to each side; brighter when the local car is in it."""
            reach, spread = view.cone
            painter.save()
            painter.translate(centre.x() + blip.side * per_unit, centre.y() - blip.ahead * per_unit)
            painter.rotate(math.degrees(blip.angle))
            tail, radius = h / 2, reach * per_unit
            points = [QPointF(0, tail)]
            for step in range(CONE_STEPS + 1):
                turn = math.radians(-spread + 2 * spread * step / CONE_STEPS)
                points.append(QPointF(radius * math.sin(turn), tail + radius * math.cos(turn)))
            color = QColor(DRAFT_COLOR)
            color.setAlpha(CONE_IN if blip.in_cone else CONE_OUT)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF(points))
            painter.restore()

        if view.cone is not None:
            for blip in view.blips:
                if blip.in_cone is not None:
                    cone(blip)
        for blip in view.blips:
            if blip.seconds is not None and blip.seconds <= RADAR_FULL:
                color = BEHIND_COLOR
            elif blip.seconds is not None and blip.seconds <= view.within:
                color = LIFT_COLOR
            else:
                color = RADAR_OTHER
            car(blip.ahead, blip.side, blip.angle, color)
            if blip.in_cone:  # the car being drafted: a cyan outline
                painter.save()
                painter.translate(centre.x() + blip.side * per_unit, centre.y() - blip.ahead * per_unit)
                painter.rotate(math.degrees(blip.angle))
                painter.setPen(QPen(QColor(DRAFT_COLOR), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(QRectF(-w / 2 - 1, -h / 2 - 1, w + 2, h + 2), w / 4, w / 4)
                painter.restore()
        car(0.0, 0.0, 0.0, RADAR_ME)
        painter.setClipping(False)
        painter.setOpacity(1.0)
        if not self.locked:
            painter.setPen(QPen(QColor(*BORDER), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
            painter.setPen(QColor(*LABEL_COLOR))
            font = painter.font()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(
                self.rect().adjusted(6, 0, -20, -3), Qt.AlignBottom | Qt.AlignLeft, self.section.label
            )

    def _paint_map(self, painter):
        """The track map: the road seen from above in a square, its start line, and
        the cars as dots (see turbohud.core.trackmap). In move mode a sample oval, with
        a border and its name."""
        view = self.trackmap
        if not self.locked and view is None:
            view = _sample_map()
        if view is not None:
            size = min(self.width(), self.height())
            left, top = (self.width() - size) / 2, (self.height() - size) / 2
            box = QRectF(left, top, size, size).adjusted(1, 1, -1, -1)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(*MAP_BACK))
            painter.drawRoundedRect(box, 10, 10)
            outline = view.outline
            scale, x_off, y_off = map_transform(outline.bounds, (size, size), size * MAP_PADDING)

            def at(point):
                return QPointF(left + x_off + point[0] * scale, top + y_off - point[1] * scale)

            path = QPainterPath(at(outline.points[0]))
            for point in outline.points[1:]:
                path.lineTo(at(point))
            if outline.closed:
                path.closeSubpath()
            road = road_width(size)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(*MAP_ROAD_EDGE), road + 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)
            painter.setPen(QPen(QColor(*MAP_ROAD), road, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)
            if outline.start is not None:
                # The start line: across the road, a little wider than it.
                (sx, sz), (fx, fz) = outline.start
                reach = (road * 0.8 + 2) / scale
                ux, uz = -fz * reach, fx * reach  # across the direction of travel
                painter.setPen(QPen(QColor(MAP_START), max(2.0, road / 3), Qt.SolidLine, Qt.FlatCap))
                painter.drawLine(at((sx - ux, sz - uz)), at((sx + ux, sz + uz)))
            radius = max(2.5, size * MAP_DOT)
            painter.setClipRect(box)  # a car off the learnt track (a road from the grid) stays inside
            for dot in view.dots:
                painter.setOpacity(MAP_PIT_OPACITY if dot.in_pit else 1.0)
                color = QColor(MAP_COLORS[dot.role])
                if dot.role == 'other':
                    color.setAlpha(MAP_OTHER_ALPHA)
                r = radius * MAP_SIZES[dot.role]
                if dot.ahead_too:  # the leader is also the next car ahead: a red ring
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(MAP_COLORS['ahead']))
                    painter.drawEllipse(at(dot.position), r + 3, r + 3)
                if dot.role == 'me':
                    # A ring, open in the middle: a car under it still shows.
                    ring = max(1.5, r * MAP_RING)
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(QColor(0, 0, 0, 200), ring + 2))
                    painter.drawEllipse(at(dot.position), r, r)
                    painter.setPen(QPen(color, ring))
                    painter.drawEllipse(at(dot.position), r, r)
                    continue
                painter.setPen(QPen(QColor(0, 0, 0, 200), 1.5))
                painter.setBrush(color)
                painter.drawEllipse(at(dot.position), r, r)
            painter.setClipping(False)
            painter.setOpacity(1.0)
        if not self.locked:
            painter.setPen(QPen(QColor(*BORDER), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
            painter.setPen(QColor(*LABEL_COLOR))
            font = painter.font()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(
                self.rect().adjusted(6, 0, -20, -3), Qt.AlignBottom | Qt.AlignLeft, self.section.label
            )

    def _paint_delta(self, painter):
        """The delta bar. In move mode a sample, with a border and its name."""
        view = self.delta_view
        if not self.locked and view is None:
            view = DELTA_BAR_SAMPLE
        if view is None:
            return
        draw_delta_bar(painter, self.width(), self.height(), view.fill, view.green, view.text, self.theme)
        if not self.locked:
            painter.setPen(QPen(QColor(*BORDER), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 4, 4)
            painter.setPen(QColor(*LABEL_COLOR))
            font = painter.font()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(
                self.rect().adjusted(6, 0, -20, 0), Qt.AlignVCenter | Qt.AlignLeft, self.section.label
            )

    def _paint_bar(self, painter):
        """A plain bar filling the window (the blue flag), at its opacity; in move mode
        with a border and its name, so it can be placed while no flag is out."""
        opacity = self.opacity if self.locked else max(self.opacity or 0.0, BLUE_SAMPLE)
        if opacity is None:
            return
        alpha = round(255 * min(max(opacity, 0.0), 1.0))
        edge = BLUE_FLAG_EDGE_WIDTH
        rect = QRectF(self.rect()).adjusted(edge / 2, edge / 2, -edge / 2, -edge / 2)
        radius = min(rect.height() / 2, 4)
        # A horizontal flag: navy with a darker blue outline; in move mode the move
        # mode's light border instead, like the other sections.
        painter.setPen(
            QPen(QColor(*BORDER), 2) if not self.locked else QPen(QColor(*BLUE_FLAG_EDGE, alpha), edge)
        )
        painter.setBrush(QColor(*BLUE_FLAG, alpha))
        painter.drawRoundedRect(rect, radius, radius)
        if not self.locked:
            painter.setPen(QColor(*LABEL_COLOR))
            font = painter.font()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(
                self.rect().adjusted(6, 0, -20, 0), Qt.AlignVCenter | Qt.AlignLeft, self.section.label
            )


class MovePanel(QWidget):
    """Shown in move mode: what to do, a tick box and a group per section, the options,
    Lock and Quit. Sections in the same group move together."""

    lock_requested = Signal()
    quit_requested = Signal()
    settings_requested = Signal()
    wanted_changed = Signal(str, bool)  # section name, shown
    group_changed = Signal(str, str)  # section name, group ('' for none)
    align_requested = Signal(str, bool, bool)  # section name, centre across, centre down
    mph_changed = Signal(bool)
    backdrop_changed = Signal(bool)
    map_others_changed = Signal(bool)
    radar_cone_changed = Signal(bool)
    preset_save_requested = Signal(int)  # the preset's number
    preset_load_requested = Signal(int)
    preset_delete_requested = Signal(int)
    match_requested = Signal(str)  # the group
    undo_requested = Signal()
    tint_changed = Signal(str, bool)  # section name, a tint behind its text
    text_centred_changed = Signal(str, bool)  # section name, its text in the middle of its box

    focusable = True  # it takes clicks on its tick boxes and buttons

    def __init__(
        self,
        native,
        sections,
        shortcuts,
        mph=False,
        backdrop=False,
        commands=False,
        map_others=False,
        saved_presets=(),
        radar_cone=True,
    ):
        super().__init__(None, window_flags())
        self.native = native
        self.setWindowTitle('TurboHUD - move mode')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet('QLabel, QCheckBox { color: white; }')
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.addWidget(QLabel('<b>TurboHUD - move mode</b>'))
        for line in help_lines(shortcuts, commands):
            column.addWidget(QLabel(line))
        self.boxes = {}
        self.groups = {}
        self.centres = {}
        self.tints = {}
        grid = QGridLayout()
        grid.addWidget(QLabel('Group (moves together):'), 0, 1)
        for row, section in enumerate(sections, start=1):
            box = QCheckBox(f'Show {section.label.lower()}')
            box.toggled.connect(lambda checked, name=section.name: self.wanted_changed.emit(name, checked))
            grid.addWidget(box, row, 0)
            self.boxes[section.name] = box
            group = QComboBox()
            group.addItems(['-', *GROUPS])
            group.currentTextChanged.connect(
                lambda text, name=section.name: self.group_changed.emit(name, '' if text == '-' else text)
            )
            group.currentTextChanged.connect(lambda _text: self._update_matches())
            grid.addWidget(group, row, 1)
            self.groups[section.name] = group
            for column_, (text, tip, across, down) in enumerate(
                (
                    ('Centre ↔', 'Centre across the screen', True, False),
                    ('Centre ↕', 'Centre down the screen', False, True),
                ),
                start=2,
            ):
                button = QPushButton(text)
                button.setToolTip(tip)
                button.clicked.connect(
                    lambda _checked=False, name=section.name, a=across, d=down: self.align_requested.emit(
                        name, a, d
                    )
                )
                grid.addWidget(button, row, column_)
            if text_can_centre(section):
                centre = QCheckBox('Centre text')
                centre.setToolTip('Put the text in the middle of the box, not at its left')
                centre.toggled.connect(
                    lambda checked, name=section.name: self.text_centred_changed.emit(name, checked)
                )
                grid.addWidget(centre, row, 4)
                self.centres[section.name] = centre
            if not section.drawing:
                tint = QCheckBox('Tint')
                tint.setToolTip('A light tint behind the text of this section while locked')
                tint.toggled.connect(lambda checked, name=section.name: self.tint_changed.emit(name, checked))
                grid.addWidget(tint, row, 5)
                self.tints[section.name] = tint
        column.addLayout(grid)
        self.text_sections = [section.name for section in sections if not section.drawing]
        self.matches = {}
        matches = QHBoxLayout()
        matches.addWidget(QLabel('Same text size and width:'))
        for name in GROUPS:
            match = QPushButton(f'Group {name}')
            match.setToolTip(
                f'Give the text sections in group {name} the largest text size among them and one '
                'width. Save a preset first to be able to go back.'
            )
            match.clicked.connect(lambda _checked=False, group=name: self.match_requested.emit(group))
            matches.addWidget(match)
            self.matches[name] = match
        matches.addStretch()
        column.addLayout(matches)
        self._update_matches()
        self.mph = QCheckBox('Speed in mph')
        self.mph.setChecked(mph)
        self.mph.toggled.connect(self.mph_changed)
        column.addWidget(self.mph)
        self.backdrop = QCheckBox('Light tint behind all sections')
        self.backdrop.setChecked(backdrop)
        self.backdrop.toggled.connect(self.backdrop_changed)
        column.addWidget(self.backdrop)
        self.map_others = QCheckBox('Other cars on the track map')
        self.map_others.setChecked(map_others)
        self.map_others.toggled.connect(self.map_others_changed)
        self.radar_cone = QCheckBox('Slipstream cones on the proximity radar')
        self.radar_cone.setChecked(radar_cone)
        self.radar_cone.toggled.connect(self.radar_cone_changed)
        if any(section.drawing == 'radar' for section in sections):
            column.addWidget(self.radar_cone)
        if any(section.drawing == 'map' for section in sections):
            column.addWidget(self.map_others)
        presets = QGridLayout()
        self.preset_loads = {}
        self.preset_deletes = {}
        for row_, number in enumerate(PRESETS):
            presets.addWidget(QLabel(f'Preset {number}'), row_, 0)
            save = QPushButton('Save')
            save.setToolTip(f'Keep the layout as it is now in preset {number}, replacing what was there')
            save.clicked.connect(lambda _checked=False, n=number: self.preset_save_requested.emit(n))
            presets.addWidget(save, row_, 1)
            load = QPushButton('Load')
            load.setToolTip(
                f'Put the sections as preset {number} has them, also with Ctrl+Shift+{number}'
                if shortcuts
                else f'Put the sections as preset {number} has them'
            )
            load.setEnabled(number in saved_presets)
            load.clicked.connect(lambda _checked=False, n=number: self.preset_load_requested.emit(n))
            presets.addWidget(load, row_, 2)
            self.preset_loads[number] = load
            delete = QPushButton()
            delete.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
            delete.setAccessibleName(f'Delete preset {number}')
            delete.setToolTip(f'Delete preset {number}; Undo brings it back')
            delete.setEnabled(number in saved_presets)
            delete.clicked.connect(lambda _checked=False, n=number: self.preset_delete_requested.emit(n))
            presets.addWidget(delete, row_, 3)
            self.preset_deletes[number] = delete
        presets.setColumnStretch(4, 1)
        column.addLayout(presets)
        row = QHBoxLayout()
        self.undo = QPushButton('Undo')
        self.undo.setToolTip('Go back one change to the layout, as often as there are changes')
        self.undo.setEnabled(False)
        self.undo.clicked.connect(self.undo_requested)
        row.addWidget(self.undo)
        lock = QPushButton('Lock')
        settings = QPushButton('Settings…')
        quit_ = QPushButton('Quit TurboHUD')
        lock.clicked.connect(self.lock_requested)
        settings.clicked.connect(self.settings_requested)
        quit_.clicked.connect(self.quit_requested)
        row.addWidget(lock)
        row.addWidget(settings)
        row.addWidget(quit_)
        row.addStretch()
        column.addLayout(row)
        self.adjustSize()

    def set_wanted(self, name, wanted):
        box = self.boxes.get(name)
        if box is not None and box.isChecked() != wanted:
            box.blockSignals(True)
            box.setChecked(wanted)
            box.blockSignals(False)

    def set_group(self, name, group):
        combo = self.groups.get(name)
        text = group or '-'
        if combo is not None and combo.currentText() != text:
            combo.blockSignals(True)
            combo.setCurrentText(text)
            combo.blockSignals(False)
            self._update_matches()

    def _update_matches(self):
        """A group's button works from two text sections in it."""
        for group, button in self.matches.items():
            members = [name for name in self.text_sections if self.groups[name].currentText() == group]
            button.setEnabled(len(members) >= 2)

    def set_tint(self, name, tint):
        box = self.tints.get(name)
        if box is not None and box.isChecked() != tint:
            box.blockSignals(True)
            box.setChecked(tint)
            box.blockSignals(False)

    def set_text_centred(self, name, centred):
        box = self.centres.get(name)
        if box is not None and box.isChecked() != centred:
            box.blockSignals(True)
            box.setChecked(centred)
            box.blockSignals(False)

    def set_mph(self, mph):
        if self.mph.isChecked() != mph:
            self.mph.blockSignals(True)
            self.mph.setChecked(mph)
            self.mph.blockSignals(False)

    def set_backdrop(self, backdrop):
        if self.backdrop.isChecked() != backdrop:
            self.backdrop.blockSignals(True)
            self.backdrop.setChecked(backdrop)
            self.backdrop.blockSignals(False)

    def set_presets_saved(self, numbers):
        for number, load in self.preset_loads.items():
            load.setEnabled(number in numbers)
            self.preset_deletes[number].setEnabled(number in numbers)

    def set_undo_available(self, available):
        self.undo.setEnabled(available)

    def set_radar_cone(self, cone):
        if self.radar_cone.isChecked() != cone:
            self.radar_cone.blockSignals(True)
            self.radar_cone.setChecked(cone)
            self.radar_cone.blockSignals(False)

    def set_map_others(self, others):
        if self.map_others.isChecked() != others:
            self.map_others.blockSignals(True)
            self.map_others.setChecked(others)
            self.map_others.blockSignals(False)

    def mousePressEvent(self, event):
        # Dragged by its background, out of the way of a section if need be.
        if event.button() == Qt.LeftButton and self.windowHandle() is not None:
            self.windowHandle().startSystemMove()

    def show_at(self, x, y):
        self.move(x, y)
        self.show()
        log.info('panel: %s', self.native.raise_window(self))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(*BORDER), 2))
        painter.setBrush(QColor(15, 30, 55, 225))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10)
        painter.end()
