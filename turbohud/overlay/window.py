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

from turbohud.core.hud import base_size, help_lines, hud_lines, section_scale
from turbohud.hud.painter import draw_hud, text_width

TINT = (23, 56, 97, 153)  # move mode's background: red, green, blue, opacity (0-255)
BORDER = (120, 170, 230)
LABEL_COLOR = (200, 220, 245)
LABEL_SPACE = 14  # room below the content for the section's name in move mode, at scale 1

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
        low = section_scale((0, 0), self.base)
        self.setMinimumSize(round(self.base[0] * low), round(self.base[1] * low))

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
            return
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
        """Show or hide the section for good (the panel's tick boxes)."""
        if wanted == self.wanted:
            return
        self.wanted = wanted
        if wanted:
            self.setWindowFlag(Qt.WindowTransparentForInput, self.locked)
            self.grip.setVisible(not self.locked)
            self.show_on_top()
        else:
            self.hide()

    def mousePressEvent(self, event):
        if not self.locked and event.button() == Qt.LeftButton:
            self.windowHandle().startSystemMove()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        scale = self.theme.scale * section_scale((self.width(), self.height()), self.base)
        rows = self.rows
        if not self.locked:
            painter.setPen(QPen(QColor(*BORDER), 2))
            painter.setBrush(QColor(*TINT))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
            rows = rows or list(self.section.samples[0])  # something to place, also before a race
        draw_hud(painter, hud_lines(rows, scale), self.theme, scale)
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
