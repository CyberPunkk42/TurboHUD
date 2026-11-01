"""The HUD's windows: one per section, frameless, transparent and always on top, and the
small panel that shows in move mode.

Locked, a section lets every click through and shows only its content. In move mode it
gets a tint and its name, can be dragged, and resized at its corner, which scales its
content. The panel says what to do, shows or hides sections, and locks or quits.
"""

import logging
import sys

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QSizeGrip, QVBoxLayout, QWidget

from turbohud.core.hud import base_size, content_size, help_lines, hud_lines, pedal_bars, pedal_space, section_scale
from turbohud.hud.painter import draw_bars, draw_hud, text_width

TINT = (23, 56, 97, 153)  # move mode's background: red, green, blue, opacity (0-255)
BORDER = (120, 170, 230)
LABEL_COLOR = (200, 220, 245)
LABEL_SPACE = 14  # room below the content for the section's name in move mode, at scale 1
MIN_WIDTH = 40

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
        self.locked = True
        self.wanted = True  # the player wants it shown
        self.setWindowTitle(f'TurboHUD - {section.label}')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowTransparentForInput, True)
        width, height = base_size(section, theme.scale, text_width)
        self.base = (width, height + round(LABEL_SPACE * theme.scale))
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
        rows = self.rows
        if not self.locked:
            painter.setPen(QPen(QColor(*BORDER), 2))
            painter.setBrush(QColor(*TINT))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
            rows = rows or list(self.section.samples[0])  # something to place, also before a race
        bars = pedal_space(self.theme.scale) if self.section.pedals else 0
        needed = content_size(rows, self.theme.scale, text_width)[0] + bars if rows else None
        scale = self.theme.scale * section_scale((self.width(), self.height()), self.base[1], needed)
        left = 0
        if self.section.pedals:
            throttle, brake = self.pedals or (None, None)
            draw_bars(painter, pedal_bars(self.width(), self.height(), scale, throttle, brake))
            left = pedal_space(scale) // 2
        draw_hud(painter, hud_lines(rows, scale), self.theme, scale, left)
        if not self.locked:
            painter.setPen(QColor(*LABEL_COLOR))
            font = painter.font()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(self.rect().adjusted(6, 0, -20, -3), Qt.AlignBottom | Qt.AlignLeft, self.section.label)
        painter.end()


class MovePanel(QWidget):
    """Shown in move mode: what to do, a tick box per section, Lock and Quit."""

    lock_requested = Signal()
    quit_requested = Signal()
    wanted_changed = Signal(str, bool)  # section name, shown

    focusable = True  # it takes clicks on its tick boxes and buttons

    def __init__(self, native, sections, shortcuts):
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
        for section in sections:
            box = QCheckBox(f'Show {section.label.lower()}')
            box.toggled.connect(lambda checked, name=section.name: self.wanted_changed.emit(name, checked))
            column.addWidget(box)
            self.boxes[section.name] = box
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
