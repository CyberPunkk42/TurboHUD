"""The settings window: the HUD's colours and the size of all sections.

Colours are picked from a few swatches rather than a colour dialog: a dialog would be
one more window, which a tiling desktop (Hyprland) could place anywhere. Every change
applies at once and is saved by the app.
"""

import logging
from dataclasses import replace

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from turbohud.core.settings import BLUE_SECONDS, RADAR_SECONDS, READS_PER_SECOND, Theme

log = logging.getLogger(__name__)

# (label, Theme field, swatches as '#rrggbb' or '#rrggbbaa')
COLOURS = (
    ('Text', 'text_color', ('#ffffff', '#d9dee6', '#ffd65a', '#ffa64d', '#5ec8ff', '#5ee07a', '#ff8fd0')),
    (
        'Highlight',
        'accent_color',
        ('#ffd65a', '#ffffff', '#ffa64d', '#5ec8ff', '#5ee07a', '#ff6b6b', '#c79bff'),
    ),
    ('Outline', 'outline_color', ('#000000ff', '#000000c8', '#00000080', '#0b1e3dc8', '#00000000')),
)
SIZE_STEP = 1.1  # Bigger: 10 % larger; Smaller: the same back
SWATCH = 22  # pixels
CHOSEN_RING = (120, 190, 255)
# On the Mac a plain checkable button looks the same checked or not.
READS_BUTTON = (
    'QPushButton { color: white; background: transparent; border: 1px solid white;'
    ' border-radius: 6px; padding: 3px 14px; }'
    f' QPushButton:checked {{ color: black; background: rgb{CHOSEN_RING}; border-color: rgb{CHOSEN_RING}; }}'
)


def _qcolor(text):
    """A QColor from '#rrggbb' or '#rrggbbaa'."""
    color = QColor(text[:7])
    if len(text) == 9:
        color.setAlpha(int(text[7:], 16))
    return color


class Swatch(QPushButton):
    """A colour button; shows a ring when it is the chosen one."""

    def __init__(self, color):
        super().__init__()
        self.color = color
        self.chosen = False
        self.setFixedSize(SWATCH, SWATCH)
        self.setToolTip(color)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        # A checked background shows how see-through an outline colour is.
        painter.setPen(Qt.NoPen)
        for i in range(2):
            for j in range(2):
                painter.setBrush(QColor(150, 150, 150) if (i + j) % 2 else QColor(90, 90, 90))
                half = rect.width() / 2
                painter.drawRect(QRectF(rect.x() + i * half, rect.y() + j * half, half, half))
        painter.setBrush(_qcolor(self.color))
        painter.setPen(QPen(QColor(0, 0, 0, 120), 1))
        painter.drawRoundedRect(rect, 3, 3)
        if self.chosen:  # a light blue ring around it, visible on every colour
            painter.setPen(QPen(QColor(*CHOSEN_RING), 2.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 5, 5)
        painter.end()


class SettingsWindow(QWidget):
    """Colours for text, highlight and outline; all sections bigger or smaller; when the blue
    flag and the proximity radar show; how often a race is read (where one can be); reset."""

    theme_changed = Signal(object)  # the new Theme
    resize_requested = Signal(float)  # factor for every section's size
    blue_seconds_changed = Signal(float)
    radar_seconds_changed = Signal(float)
    reads_changed = Signal(int)
    closed = Signal()

    focusable = True  # it takes clicks on its buttons

    def __init__(self, native, flags, theme, blue_seconds=2.0, radar_seconds=0.5, reads_per_second=None):
        super().__init__(None, flags)
        self.native = native
        self.theme = theme
        self.setWindowTitle('TurboHUD - settings')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet('QLabel { color: white; }')
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.addWidget(QLabel('<b>TurboHUD - settings</b>'))
        grid = QGridLayout()
        self.swatches = {}
        for row, (label, field, colors) in enumerate(COLOURS):
            grid.addWidget(QLabel(label), row, 0)
            line = QHBoxLayout()
            buttons = []
            for color in colors:
                button = Swatch(color)
                button.clicked.connect(lambda _checked=False, f=field, c=color: self.choose(f, c))
                line.addWidget(button)
                buttons.append(button)
            line.addStretch()
            grid.addLayout(line, row, 1)
            self.swatches[field] = buttons
        column.addLayout(grid)
        size = QHBoxLayout()
        size.addWidget(QLabel('All sections:'))
        smaller, bigger = QPushButton('Smaller'), QPushButton('Bigger')
        smaller.clicked.connect(lambda: self.resize_requested.emit(1 / SIZE_STEP))
        bigger.clicked.connect(lambda: self.resize_requested.emit(SIZE_STEP))
        size.addWidget(smaller)
        size.addWidget(bigger)
        size.addStretch()
        column.addLayout(size)
        timing = QGridLayout()
        self.blue_seconds = self._seconds_box(blue_seconds, BLUE_SECONDS, self.blue_seconds_changed)
        self.blue_seconds.setToolTip('How far behind you a car about to lap you shows the blue flag')
        timing.addWidget(QLabel('Blue flag when a car about to lap you is within:'), 0, 0)
        timing.addWidget(self.blue_seconds, 0, 1)
        self.radar_seconds = self._seconds_box(radar_seconds, RADAR_SECONDS, self.radar_seconds_changed)
        self.radar_seconds.setToolTip('How far ahead of or behind you a car shows the proximity radar')
        timing.addWidget(QLabel('Proximity radar when a car is within:'), 1, 0)
        timing.addWidget(self.radar_seconds, 1, 1)
        column.addLayout(timing)
        self.read_buttons = {}
        if reads_per_second is not None:
            column.addLayout(self._reads_row(reads_per_second))
        row = QHBoxLayout()
        reset, close = QPushButton('Reset colours'), QPushButton('Close')
        reset.clicked.connect(self.reset)
        close.clicked.connect(self.close_window)
        row.addWidget(reset)
        row.addStretch()
        row.addWidget(close)
        column.addLayout(row)
        self.show_chosen()
        self.adjustSize()

    def _reads_row(self, chosen):
        """Buttons rather than a drop-down, whose list would be one more window."""
        row = QHBoxLayout()
        row.addWidget(QLabel('Race reads a second:'))
        group = QButtonGroup(self)
        for reads in READS_PER_SECOND:
            button = QPushButton(str(reads))
            button.setCheckable(True)
            button.setChecked(reads == chosen)
            button.setStyleSheet(READS_BUTTON)
            button.setToolTip(
                'Fewer reads ask less of the game; the delta and the track map move less smoothly'
            )
            group.addButton(button, reads)
            row.addWidget(button)
            self.read_buttons[reads] = button
        group.idClicked.connect(self.reads_changed)
        row.addStretch()
        return row

    @staticmethod
    def _seconds_box(value, limits, changed):
        low, high, step = limits
        box = QDoubleSpinBox()
        box.setRange(low, high)
        box.setSingleStep(step)
        box.setDecimals(1)
        box.setSuffix(' s')
        box.setValue(value)
        box.setKeyboardTracking(False)  # the time typed, not each digit on the way
        box.valueChanged.connect(changed)
        return box

    def choose(self, field, color):
        self.theme = replace(self.theme, **{field: color})
        self.show_chosen()
        self.theme_changed.emit(self.theme)

    def reset(self):
        defaults = Theme()
        self.theme = replace(
            self.theme,
            text_color=defaults.text_color,
            accent_color=defaults.accent_color,
            outline_color=defaults.outline_color,
        )
        self.show_chosen()
        self.theme_changed.emit(self.theme)

    def show_chosen(self):
        for field, buttons in self.swatches.items():
            current = getattr(self.theme, field).lower()
            for button in buttons:
                button.chosen = button.color.lower() == current
                button.update()

    def mousePressEvent(self, event):
        # Dragged by its background, out of the way of a section if need be.
        if event.button() == Qt.LeftButton and self.windowHandle() is not None:
            self.windowHandle().startSystemMove()

    def show_at(self, x, y):
        self.move(x, y)
        self.show()
        log.info('settings: %s', self.native.raise_window(self))

    def close_window(self):
        self.hide()
        self.closed.emit()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(120, 170, 230), 2))
        painter.setBrush(QColor(15, 30, 55, 235))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10)
        painter.end()
