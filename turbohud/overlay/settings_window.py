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
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from turbohud.core.hud import beside
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
# Where each option goes: under its heading, in this order. Options not named here show under More.
GROUPS = {
    'look': ('backdrop', 'group_tint', 'mph'),
    'standings': ('classes', 'clan_tags'),
    'sections': ('nearby_short', 'sector_bars', 'gear', 'map_others'),
    'radar': ('radar_cone',),
    'flags': ('yellow_flags',),
}
# The radar's cameras (asked for by the user on 2026-11-15: in the views from outside the car too):
# (radar_cockpit_only, button, tooltip)
CAMERA_CHOICES = (
    (True, 'Cockpit cameras', 'Only while the camera sits at the driver: first person, "CAM 5"'),
    (False, 'Every camera', 'Also in the views from behind and outside the car (third person)'),
)
COLUMNS_PER_ROW = 4  # the standings' column switches in a row
HEADING = '#9fb8d8'  # the headings, as in the move-mode panel
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
    """Colours for text, highlight and outline; all sections bigger or smaller; the options
    for the whole HUD; when the blue flag and the proximity radar show; how often a race is
    read (where one can be); reset."""

    theme_changed = Signal(object)  # the new Theme
    resize_requested = Signal(float)  # factor for every section's size
    blue_seconds_changed = Signal(float)
    radar_seconds_changed = Signal(float)
    reads_changed = Signal(int)
    option_changed = Signal(str, bool)  # an option's key (see `options`), on or off
    about_requested = Signal()  # About...: the app's name and version
    closed = Signal()

    focusable = True  # it takes clicks on its buttons

    def __init__(
        self, native, flags, theme, blue_seconds=2.0, radar_seconds=0.5, reads_per_second=None, options=()
    ):
        """`options` are tick boxes for the whole HUD: (key, label, on, tooltip) each; a
        change says its key through option_changed."""
        super().__init__(None, flags)
        self.native = native
        self.flags = flags
        self.theme = theme
        self.class_sheet = None  # made when first opened (open_class_sheet)
        self.setWindowTitle('TurboHUD - Settings')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet('QLabel { color: white; }')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.addWidget(QLabel('<b>TurboHUD - Settings</b>'))
        columns = QHBoxLayout()
        columns.setSpacing(24)
        left, right = QVBoxLayout(), QVBoxLayout()
        for side in (left, right):
            side.setSpacing(6)  # not the columns' gap, which a layout inside would take on
        columns.addLayout(left)
        columns.addLayout(right)
        outer.addLayout(columns)
        listed = {key: (label, on, tip) for key, label, on, tip in options}
        self.options = {}
        self.camera_buttons = {}

        left.addWidget(self._heading('Look'))
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
        left.addLayout(grid)
        size = QHBoxLayout()
        size.addWidget(QLabel('All sections:'))
        smaller, bigger = QPushButton('Smaller'), QPushButton('Bigger')
        smaller.clicked.connect(lambda: self.resize_requested.emit(1 / SIZE_STEP))
        bigger.clicked.connect(lambda: self.resize_requested.emit(SIZE_STEP))
        size.addWidget(smaller)
        size.addWidget(bigger)
        size.addStretch()
        left.addLayout(size)
        self._boxes(left, listed, GROUPS['look'])

        standings = [key for key in GROUPS['standings'] if key in listed]
        column_keys = [key for key in listed if key.startswith('column_')]
        if standings or column_keys:
            left.addWidget(self._heading('Standings'))
            self._boxes(left, listed, standings)
            if column_keys:
                # Rows of COLUMNS_PER_ROW, so the window keeps its width as columns are added.
                grid = QGridLayout()
                grid.setHorizontalSpacing(14)
                grid.addWidget(QLabel('Columns:'), 0, 0)
                for index, key in enumerate(column_keys):
                    row, place = divmod(index, COLUMNS_PER_ROW)
                    grid.addWidget(self._box(key, *listed[key]), row, place + 1)
                grid.setColumnStretch(COLUMNS_PER_ROW + 1, 1)
                left.addLayout(grid)
        if any(key in listed for key in GROUPS['sections']):
            left.addWidget(self._heading('Sections'))
            self._boxes(left, listed, GROUPS['sections'])
        left.addStretch()

        right.addWidget(self._heading('Radar'))
        if 'radar_cockpit_only' in listed:
            right.addLayout(self._camera_row(*listed['radar_cockpit_only']))
        self._boxes(right, listed, GROUPS['radar'])
        timing = QGridLayout()
        self.radar_seconds = self._seconds_box(radar_seconds, RADAR_SECONDS, self.radar_seconds_changed)
        self.radar_seconds.setToolTip('How far ahead of or behind you a car shows the radar')
        timing.addWidget(QLabel('Shows a car within:'), 0, 0)
        timing.addWidget(self.radar_seconds, 0, 1)
        right.addLayout(timing)

        right.addWidget(self._heading('Flags'))
        self._boxes(right, listed, GROUPS['flags'])
        blue = QGridLayout()
        self.blue_seconds = self._seconds_box(blue_seconds, BLUE_SECONDS, self.blue_seconds_changed)
        self.blue_seconds.setToolTip('How far behind you a car about to lap you shows the blue flag')
        blue.addWidget(QLabel('Blue flag for a car within:'), 0, 0)
        blue.addWidget(self.blue_seconds, 0, 1)
        right.addLayout(blue)

        # Anything not placed above (a new option) still shows, at the end.
        rest = [key for key in listed if key not in self.options and key != 'radar_cockpit_only']
        if rest:
            right.addWidget(self._heading('More'))
            self._boxes(right, listed, rest)

        self.read_buttons = {}
        if reads_per_second is not None:
            right.addWidget(self._heading('Reading the race'))
            right.addLayout(self._reads_row(reads_per_second))
        right.addStretch()
        row = QHBoxLayout()
        reset, close = QPushButton('Reset colours'), QPushButton('Close')
        reset.clicked.connect(self.reset)
        close.clicked.connect(self.close_window)
        classes = QPushButton('Car classes...')
        classes.setToolTip('Every car class a clan tag can name, in its colour')
        classes.clicked.connect(self.open_class_sheet)
        about = QPushButton('About...')
        about.setToolTip("TurboHUD's name and version")
        about.clicked.connect(self.about_requested)
        row.addWidget(reset)
        row.addWidget(classes)
        row.addWidget(about)
        row.addStretch()
        row.addWidget(close)
        outer.addLayout(row)
        self.show_chosen()
        self.adjustSize()

    @staticmethod
    def _heading(text):
        label = QLabel(f'<small><b>{text.upper()}</b></small>')
        label.setStyleSheet(f'color: {HEADING}; padding-top: 6px;')
        return label

    def _box(self, key, label, on, tip):
        box = QCheckBox(label)
        box.setStyleSheet('QCheckBox { color: white; }')
        box.setChecked(on)
        box.setToolTip(tip)
        box.toggled.connect(lambda checked, k=key: self.option_changed.emit(k, checked))
        self.options[key] = box
        return box

    def _boxes(self, layout, listed, keys):
        for key in keys:
            if key in listed and key not in self.options:
                layout.addWidget(self._box(key, *listed[key]))

    def _camera_row(self, _label, cockpit_only, tip):
        """The radar's cameras as a choice of two: in the cockpit cameras only, or in every
        camera, the views from behind the car too (radar_cockpit_only)."""
        row = QHBoxLayout()
        row.addWidget(QLabel('Show in:'))
        group = QButtonGroup(self)
        for only, text, about in CAMERA_CHOICES:
            button = QPushButton(text)
            button.setCheckable(True)
            button.setChecked(only == cockpit_only)
            button.setStyleSheet(READS_BUTTON)
            button.setToolTip(about)
            group.addButton(button)
            button.clicked.connect(
                lambda _checked=False, o=only: self.option_changed.emit('radar_cockpit_only', o)
            )
            row.addWidget(button)
            self.camera_buttons[only] = button
        row.addStretch()
        return row

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

    def set_option(self, key, on):
        """Show an option changed elsewhere (the menu, the panel), saying nothing back."""
        if key == 'radar_cockpit_only' and self.camera_buttons:
            self.camera_buttons[bool(on)].setChecked(True)  # a button group: the other goes off
            return
        box = self.options.get(key)
        if box is not None and box.isChecked() != on:
            box.blockSignals(True)
            box.setChecked(on)
            box.blockSignals(False)

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

    def open_class_sheet(self):
        """The class sheet beside this window: on its right, or on its left where the screen
        ends; it stays open until closed."""
        from turbohud.overlay.class_sheet import ClassSheet

        if self.class_sheet is None:
            self.class_sheet = ClassSheet(self.native, self.flags)
        sheet = self.class_sheet
        anchor = self.frameGeometry().getRect()
        screen = self.screen().availableGeometry().getRect() if self.screen() is not None else anchor
        sheet.show_at(*beside((sheet.width(), sheet.height()), anchor, screen))

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
