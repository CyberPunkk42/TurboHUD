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

from turbohud.core.hud import hud_lines, min_size, session_rows
from turbohud.hud.painter import draw_hud

TINT = (23, 56, 97, 153)  # move mode's background: red, green, blue, opacity (0-255)
BORDER = (120, 170, 230)

log = logging.getLogger(__name__)


class OverlayWindow(QWidget):
    locked_changed = Signal(bool)
    close_requested = Signal()

    def __init__(self, native, theme, content=None):
        """`content()` gives the rows to show (turbohud.core.hud.Row); without it the
        overlay shows how long it has been running."""
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if sys.platform != 'darwin':
            flags |= Qt.Tool  # no taskbar button; on the Mac a tool window hides when inactive
        super().__init__(None, flags)
        self.native = native
        self.theme = theme
        self.locked = True
        self.shortcuts = False
        self.started = time.monotonic()
        self.content = content or (lambda: session_rows(self.elapsed()))
        self.setWindowTitle('TurboHUD')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
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
        # Height of the button row at the bottom; the move-mode hint stays above it.
        self.controls_height = lock.sizeHint().height() + column.contentsMargins().bottom()
        self.setMinimumSize(*min_size(theme.scale, self.controls_height))

    def elapsed(self):
        return time.monotonic() - self.started

    def placement(self):
        # On Wayland only the desktop knows where the window is; ask it where possible.
        native = getattr(self.native, 'placement', None)
        return (native and native(self)) or (self.x(), self.y(), self.width(), self.height())

    def show_on_top(self):
        self.show()
        log.info('native: %s', self.native.raise_window(self))

    def set_locked(self, locked):
        if locked == self.locked:
            return
        self.locked = locked
        in_place = getattr(self.native, 'input_in_place', False) and self.windowHandle() is not None
        if in_place:
            # Wayland: change click-through on the shown window. Re-creating it would
            # make the desktop treat it as a new window (Hyprland would tile it again).
            self.windowHandle().setFlag(Qt.WindowTransparentForInput, locked)
        else:
            self.setWindowFlag(Qt.WindowTransparentForInput, locked)
        for control in self.controls:
            control.setVisible(not locked)
        self.setCursor(Qt.ArrowCursor if locked else Qt.OpenHandCursor)
        if not in_place:
            self.show_on_top()  # changing a window flag hides the window
        if locked:
            self.native.give_focus_back()
            log.info('locked at %s', self.placement())
        else:
            self.native.take_focus()
            if not in_place:
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
        hint_bottom = self.height() - self.controls_height
        lines = hud_lines(self.content(), self.locked, self.shortcuts, self.theme.scale, hint_bottom)
        draw_hud(painter, lines, self.theme)
        painter.end()
