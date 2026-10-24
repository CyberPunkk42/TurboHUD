"""The overlay window: frameless, transparent and always on top.

Locked, it lets every click through and shows only the HUD. In move mode it gets a tint,
can be dragged and resized, and shows Lock and Close buttons.
"""

import logging
import sys
import time

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizeGrip, QVBoxLayout, QWidget

from turbokit.core.hud import hud_lines
from turbokit.core.settings import MIN_HEIGHT, MIN_WIDTH
from turbokit.hud.painter import draw_hud

TINT = (23, 56, 97, 153)  # move mode's background: red, green, blue, opacity (0-255)
BORDER = (120, 170, 230)

log = logging.getLogger(__name__)


class OverlayWindow(QWidget):
    locked_changed = Signal(bool)
    close_requested = Signal()

    def __init__(self, native, theme):
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if sys.platform != 'darwin':
            flags |= Qt.Tool  # no taskbar button; on the Mac a tool window hides when inactive
        super().__init__(None, flags)
        self.native = native
        self.theme = theme
        self.locked = True
        self.shortcuts = False
        self.started = time.monotonic()
        self.setWindowTitle('TurboKit')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self.setWindowFlag(Qt.WindowTransparentForInput, True)

        lock = QPushButton('Lock')
        close = QPushButton('Close')
        lock.clicked.connect(lambda: self.set_locked(True))
        close.clicked.connect(self.close_requested)
        grip = QSizeGrip(self)
        row = QHBoxLayout()
        row.addWidget(lock)
        row.addWidget(close)
        row.addStretch()
        row.addWidget(grip, 0, Qt.AlignBottom | Qt.AlignRight)
        column = QVBoxLayout(self)
        column.addStretch()
        column.addLayout(row)
        self.controls = (lock, close, grip)
        for control in self.controls:
            control.setVisible(False)

    def elapsed(self):
        return time.monotonic() - self.started

    def placement(self):
        return (self.x(), self.y(), self.width(), self.height())

    def show_on_top(self):
        self.show()
        log.info('native: %s', self.native.raise_window(self))

    def set_locked(self, locked):
        if locked == self.locked:
            return
        self.locked = locked
        self.setWindowFlag(Qt.WindowTransparentForInput, locked)
        for control in self.controls:
            control.setVisible(not locked)
        self.setCursor(Qt.ArrowCursor if locked else Qt.OpenHandCursor)
        self.show_on_top()  # changing a window flag hides the window
        if locked:
            self.native.give_focus_back()
            log.info('locked at %s', self.placement())
        else:
            self.native.take_focus()
            self.activateWindow()
            self.raise_()
            log.info('move mode')
        self.update()
        self.locked_changed.emit(locked)

    def mousePressEvent(self, event):
        if not self.locked and event.button() == Qt.LeftButton:
            self.windowHandle().startSystemMove()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.locked:
            painter.setPen(QPen(QColor(*BORDER), 2))
            painter.setBrush(QColor(*TINT))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10)
        lines = hud_lines(self.elapsed(), self.locked, self.shortcuts, self.theme.scale)
        draw_hud(painter, lines, self.theme)
        painter.end()
