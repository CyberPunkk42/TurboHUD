"""The HUD's windows: one per section, frameless, transparent and always on top, and the
small panel that shows in move mode.

Locked, a section lets every click through and shows only its content. In move mode it
gets a tint and its name, can be dragged, and resized at its corner, which scales its
content. The panel says what to do, shows or hides sections, and locks or quits.
"""

import logging
import math
import sys

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from turbohud.core.hud import (
    MARGIN,
    base_size,
    content_size,
    help_lines,
    hud_lines,
    pedal_bars,
    pedal_space,
    section_scale,
)
from turbohud.core.race import CAR_LENGTH, CAR_WIDTH, RADAR_FROM, RADAR_FULL, Blip, RadarView
from turbohud.core.settings import GROUPS
from turbohud.hud.painter import BEHIND_COLOR, LIFT_COLOR, draw_bars, draw_hud, text_width

TINT = (23, 56, 97, 153)  # move mode's background: red, green, blue, opacity (0-255)
BORDER = (120, 170, 230)
LABEL_COLOR = (200, 220, 245)
LABEL_SPACE = 14  # room below the content for the section's name in move mode, at scale 1
MIN_WIDTH = 40
BLUE_FLAG = (0, 0, 128)  # navy
BLUE_FLAG_EDGE = (0, 0, 64)  # its outline, a darker blue
BLUE_FLAG_EDGE_WIDTH = 2
PEDAL_INSET = 4  # pedal_bars' default inset
BACKDROP = (0, 0, 0, 40)  # the light tint behind a section's text (option), RGBA
BLUE_SAMPLE = 0.6  # the bar's opacity in move mode, to place it
RADAR_CAR_AT = 0.4  # the local car's height in the radar, from the top
RADAR_BACK = (10, 14, 22, 150)  # RGBA
RADAR_EDGE = (120, 130, 150, 200)
RADAR_LINES = (120, 130, 150, 90)
RADAR_ME = '#f2f2f2'
RADAR_OTHER = '#8c95a3'  # a car near but not behind or beside (ahead, or far to the side)
# In move mode: one car beside, one closing in behind, one ahead.
RADAR_SAMPLE = (
    Blip(-1.0, 3.0, 0.0, 0.0),
    Blip(-9.5, -1.0, 0.1, 0.3),
    Blip(11.0, 0.5, -0.05, None),
)

log = logging.getLogger(__name__)


def _flags():
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
    def __init__(self, native, theme, section):
        super().__init__(None, _flags())
        self.native = native
        self.theme = theme
        self.section = section
        self.rows = []
        self.pedals = None  # (throttle, brake), 0 to 1, for a section with pedal bars
        self.opacity = None  # the blue flag's opacity, 0 to 1; None: not shown
        self.radar = None  # the radar's turbohud.core.race.RadarView; None: not shown
        self.backdrop = False  # a light tint behind the text while locked (option)
        self.locked = True
        self.wanted = True  # the player wants it shown
        self.group = ''  # sections of the same group move together (move mode)
        self.setWindowTitle(f'TurboHUD - {section.label}')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowTransparentForInput, True)
        width, height = base_size(section, theme.scale, text_width)
        self.base = (width, height + (0 if section.bar else round(LABEL_SPACE * theme.scale)))
        self.grip = QSizeGrip(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.addWidget(self.grip, 0, Qt.AlignBottom | Qt.AlignRight)
        self.grip.setVisible(False)
        self.setMinimumSize(MIN_WIDTH, round(self.base[1] * 0.3))

    def placement(self):
        # On Wayland only the desktop knows where the window is; ask it where possible.
        native = getattr(self.native, 'placement', None)
        return (native and native(self)) or (self.x(), self.y(), self.width(), self.height())

    def show_on_top(self):
        self.show()
        log.info('%s: %s', self.section.name, self.native.raise_window(self))

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

    def paintEvent(self, _event):
        painter = QPainter(self)
        if not self.wanted:
            painter.end()
            return
        painter.setRenderHint(QPainter.Antialiasing)
        if self.section.drawing == 'radar':
            self._paint_radar(painter)
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
        needed = content_size(rows, self.theme.scale, text_width)[0] + bars if rows else None
        scale = self.theme.scale * section_scale((self.width(), self.height()), self.base[1], needed)
        if self.locked and self.backdrop and rows:
            self._paint_backdrop(painter, rows, scale, bars)
        left = 0
        if self.section.pedals and rows:  # no bars without a speed (menu, no game)
            throttle, brake = self.pedals or (None, None)
            draw_bars(painter, pedal_bars(self.width(), self.height(), scale, throttle, brake))
            left = pedal_space(scale) // 2
        draw_hud(painter, hud_lines(rows, scale), self.theme, scale, left, self.width() - left)
        if not self.locked:
            painter.setPen(QColor(*LABEL_COLOR))
            font = painter.font()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(self.rect().adjusted(6, 0, -20, -3), Qt.AlignBottom | Qt.AlignLeft, self.section.label)
        painter.end()


    def _paint_backdrop(self, painter, rows, scale, bars):
        """The light tint, only as large as the text (and pedal bars): half the margin
        round it. A section with a right-hand column (the player list) is as wide as its
        window, where that column is drawn."""
        width, height = content_size(rows, scale, text_width)
        pad = round(MARGIN * scale / 2)
        if any(row.right for row in rows):
            width = self.width()
        else:
            width = min(width + (bars or 0), self.width())
        left, top, tall = pad, pad, min(height, self.height()) - 2 * pad
        if self.section.pedals:
            # From the throttle bar to the brake bar, as tall as they are: the bars sit
            # at the window's edges, however wide it is.
            left, top, tall = PEDAL_INSET, PEDAL_INSET, self.height() - 2 * PEDAL_INSET
            width = self.width()
        rect = QRectF(left, top, max(width - 2 * left, 1), max(tall, 1))
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
            view = RadarView(BLUE_SAMPLE, RADAR_SAMPLE)
        if view is None:
            return
        size = min(self.width(), self.height())
        box = QRectF((self.width() - size) / 2, (self.height() - size) / 2, size, size).adjusted(1, 1, -1, -1)
        painter.setOpacity(min(max(view.opacity, 0.0), 1.0))
        painter.setPen(QPen(QColor(*RADAR_EDGE), 1.5))
        painter.setBrush(QColor(*RADAR_BACK))
        painter.drawRoundedRect(box, 10, 10)
        # The local car sits a little above the middle: more room behind, where the
        # cars that count come from. view.view reaches from it to the bottom edge.
        centre = QPointF(box.center().x(), box.top() + box.height() * RADAR_CAR_AT)
        per_unit = box.height() * (1 - RADAR_CAR_AT) / view.view
        painter.setPen(QPen(QColor(*RADAR_LINES), 1))
        painter.drawLine(QPointF(centre.x(), box.top() + 6), QPointF(centre.x(), box.bottom() - 6))
        painter.drawLine(QPointF(box.left() + 6, centre.y()), QPointF(box.right() - 6, centre.y()))
        painter.setClipRect(box)

        def car(ahead, side, angle, color):
            painter.save()
            painter.translate(centre.x() + side * per_unit, centre.y() - ahead * per_unit)
            painter.rotate(math.degrees(angle))
            w, h = CAR_WIDTH * per_unit, CAR_LENGTH * per_unit
            painter.setPen(QPen(QColor(0, 0, 0, 160), 1))
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(-w / 2, -h / 2, w, h), w / 4, w / 4)
            painter.restore()

        for blip in view.blips:
            if blip.seconds is not None and blip.seconds <= RADAR_FULL:
                color = BEHIND_COLOR
            elif blip.seconds is not None and blip.seconds <= RADAR_FROM:
                color = LIFT_COLOR
            else:
                color = RADAR_OTHER
            car(blip.ahead, blip.side, blip.angle, color)
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
            painter.drawText(self.rect().adjusted(6, 0, -20, -3), Qt.AlignBottom | Qt.AlignLeft, self.section.label)

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
        painter.setPen(QPen(QColor(*BORDER), 2) if not self.locked else QPen(QColor(*BLUE_FLAG_EDGE, alpha), edge))
        painter.setBrush(QColor(*BLUE_FLAG, alpha))
        painter.drawRoundedRect(rect, radius, radius)
        if not self.locked:
            painter.setPen(QColor(*LABEL_COLOR))
            font = painter.font()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(self.rect().adjusted(6, 0, -20, 0), Qt.AlignVCenter | Qt.AlignLeft, self.section.label)


class MovePanel(QWidget):
    """Shown in move mode: what to do, a tick box and a group per section, the options,
    Lock and Quit. Sections in the same group move together."""

    lock_requested = Signal()
    quit_requested = Signal()
    wanted_changed = Signal(str, bool)  # section name, shown
    group_changed = Signal(str, str)  # section name, group ('' for none)
    align_requested = Signal(str, bool, bool)  # section name, centre across, centre down
    mph_changed = Signal(bool)
    backdrop_changed = Signal(bool)

    focusable = True  # it takes clicks on its tick boxes and buttons

    def __init__(self, native, sections, shortcuts, mph=False, backdrop=False):
        super().__init__(None, _flags())
        self.native = native
        self.setWindowTitle('TurboHUD - move mode')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet('QLabel, QCheckBox { color: white; }')
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.addWidget(QLabel('<b>TurboHUD - move mode</b>'))
        for line in help_lines(shortcuts):
            column.addWidget(QLabel(line))
        self.boxes = {}
        self.groups = {}
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
            grid.addWidget(group, row, 1)
            self.groups[section.name] = group
            if section.drawing:  # the blue flag and the radar can be centred on the screen
                for column_, (text, tip, across, down) in enumerate((
                    ('Centre ↔', 'Centre across the screen', True, False),
                    ('Centre ↕', 'Centre down the screen', False, True),
                ), start=2):
                    button = QPushButton(text)
                    button.setToolTip(tip)
                    button.clicked.connect(
                        lambda _checked=False, name=section.name, a=across, d=down: self.align_requested.emit(name, a, d)
                    )
                    grid.addWidget(button, row, column_)
        column.addLayout(grid)
        self.mph = QCheckBox('Speed in mph')
        self.mph.setChecked(mph)
        self.mph.toggled.connect(self.mph_changed)
        column.addWidget(self.mph)
        self.backdrop = QCheckBox('Light tint behind the sections')
        self.backdrop.setChecked(backdrop)
        self.backdrop.toggled.connect(self.backdrop_changed)
        column.addWidget(self.backdrop)
        row = QHBoxLayout()
        lock = QPushButton('Lock')
        quit_ = QPushButton('Quit TurboHUD')
        lock.clicked.connect(self.lock_requested)
        quit_.clicked.connect(self.quit_requested)
        row.addWidget(lock)
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
