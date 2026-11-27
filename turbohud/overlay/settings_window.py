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
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from turbohud.core.hud import LEGACY_BARS, beside
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
    'look': ('backdrop', 'group_tint', 'grid', 'mph'),
    'colours': ('legacy_colours',),
    'standings': ('classes', 'clan_tags'),
    'sections': ('nearby_short', 'sector_bars', 'gear', 'map_others', 'compass_colourblind', 'compass_sun'),
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
# Options that do something only with another on (reported by the user on 2026-11-20: Class and
# Overall looked the same as Classes in the standings): greyed out, their tick kept, while it is off.
NEEDS = {'column_class': 'classes', 'column_overall': 'classes'}
NEEDS_TIP = 'Only in a race with classes: turn on Classes in the standings'
UNUSABLE = '#5d7799'  # a greyed-out option's name: the move-mode panel's faint blue (PANEL_EMPTY)
SYSTEM_FONT = 'System font'  # the font choice for the system's own font
HEADING = '#9fb8d8'  # the headings, as in the move-mode panel
SIZE_STEP = 1.1  # Bigger: 10 % larger; Smaller: the same back
SECTIONS_PER_ROW = 3  # the Colours tab's section ticks in a row
# Colour-blind friendly colours: (Settings.colour_blind, button, tooltip)
COLOUR_BLIND_CHOICES = (
    ('off', 'Off', "TurboHUD's own colours (or TSU's Legacy colours where on)"),
    ('all', 'All sections', 'Every section but the blue and yellow flags in colour-blind friendly colours'),
    ('chosen', 'Chosen sections', 'Only the sections ticked below in colour-blind friendly colours'),
)
COLOUR_BLIND_NOTE = (
    'Green turns sky blue, red orange, purple reddish purple: told apart with the common kinds of colour'
    ' blindness. The blue and yellow flags keep their colours.'
)
TAB_EDGE = 'rgb(120, 170, 230)'  # the window's border colour (paintEvent)
# Tabs that read as tabs, as move mode's panel has them (window.MovePanel): bold, boxed, the open one filled.
TAB_STYLE = (
    f'QTabWidget::pane {{ border: none; border-top: 2px solid {TAB_EDGE}; background: transparent;'
    ' padding-top: 4px; }'
    f' QTabBar::tab {{ color: {HEADING}; background: rgba(120, 170, 230, 35); border: 1px solid {TAB_EDGE};'
    ' border-bottom: none; border-top-left-radius: 5px; border-top-right-radius: 5px; padding: 5px 18px;'
    ' margin-right: 4px; font-weight: bold; }'
    f' QTabBar::tab:selected {{ color: #0f1e37; background: {TAB_EDGE}; }}'
    ' QTabBar::tab:!selected:hover { color: white; background: rgba(120, 170, 230, 80); }'
)
TAB_PAGE = 'tab_page'  # each tab's page, see-through to the window's own background (_tab)
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
    # Colour-blind friendly colours: 'off', 'all' or 'chosen' (hud.COLOUR_BLIND_MODES), and the sections chosen.
    colour_blind_changed = Signal(str, tuple)
    about_requested = Signal()  # About: the app's name and version
    font_chosen = Signal(str)  # a font family from customization/fonts, '' for the system's
    fonts_folder_requested = Signal()  # Fonts folder...: open customization/fonts
    add_font_requested = Signal()  # Add font...: pick a font file, copied into customization/fonts
    closed = Signal()

    focusable = True  # it takes clicks on its buttons

    def __init__(
        self,
        native,
        flags,
        theme,
        blue_seconds=2.0,
        radar_seconds=0.5,
        reads_per_second=None,
        options=(),
        colours=None,
    ):
        """`options` are tick boxes for the whole HUD: (key, label, on, tooltip) each; a
        change says its key through option_changed. `colours`: (mode, chosen sections, [(name, label)
        of each section that can have colour-blind friendly colours]) for the Colours tab, or None."""
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
        listed = {key: (label, on, tip) for key, label, on, tip in options}
        self.options = {}
        self.camera_buttons = {}
        # Tabs, as move mode's panel has (asked for by the user on 2026-11-21: a tidier window): each a
        # column of headings, in the order a player looks for them.
        self.tabs = QTabWidget()
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.setStyleSheet(TAB_STYLE)
        outer.addWidget(self.tabs)

        look = self._tab('Look', 'Text colours, size and font, and how the sections look')
        look.addWidget(self._heading('Text colours'))
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
        look.addLayout(grid)
        reset = QPushButton('Reset colours')
        reset.setToolTip('Text, highlight and outline back to TurboHUD\'s own')
        reset.clicked.connect(self.reset)
        look.addLayout(self._row(reset))
        look.addWidget(self._heading('Size and font'))
        smaller, bigger = QPushButton('Smaller'), QPushButton('Bigger')
        smaller.clicked.connect(lambda: self.resize_requested.emit(1 / SIZE_STEP))
        bigger.clicked.connect(lambda: self.resize_requested.emit(SIZE_STEP))
        look.addLayout(self._row(QLabel('All sections:'), smaller, bigger))
        # The player's own fonts (asked for by the user on 2026-11-16): those in customization/fonts.
        self.font_choice = QComboBox()
        self.font_choice.setToolTip(
            'The font of every section: one of yours from the fonts folder, or the system font'
        )
        self.font_choice.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.font_choice.currentIndexChanged.connect(self._font_picked)
        # Add font... opens a file window above TurboHUD's; the folder opens in the system's file
        # manager, beneath TurboHUD's windows, so that one first closes this window and leaves move
        # mode (reported by the user on 2026-11-17).
        add = QPushButton('Add font...')
        add.setToolTip('Choose a font file (.ttf, .otf): it is copied into the fonts folder and used at once')
        add.clicked.connect(self.add_font_requested)
        folder = QPushButton('Fonts folder...')
        folder.setToolTip(
            'Open the fonts folder, to add or delete font files; this window closes and move mode ends,'
            ' so the folder can be seen'
        )
        folder.clicked.connect(self.fonts_folder_requested)
        look.addLayout(self._row(QLabel('Font:'), self.font_choice, add, folder))
        self.set_fonts({}, '')
        if any(key in listed for key in GROUPS['look']):
            look.addWidget(self._heading('Sections'))
            self._boxes(look, listed, GROUPS['look'])
        look.addStretch()

        self.colour_boxes = {}
        self.colour_buttons = {}
        if colours is not None or any(key in listed for key in GROUPS['colours']):
            tab = self._tab(
                'Colours', 'Colour-blind friendly colours, and TSU\'s Legacy colours for the car sections'
            )
            if colours is not None:
                self._colour_blind(tab, *colours)
            if any(key in listed for key in GROUPS['colours']):
                tab.addWidget(self._heading('TSU Legacy colours'))
                self._boxes(tab, listed, GROUPS['colours'])
                tab.addLayout(self._legacy_swatches())
            tab.addStretch()

        sections = self._tab('Sections', 'Standings, nearby cars, the radar, flags and the other sections')
        standings = [key for key in GROUPS['standings'] if key in listed]
        column_keys = [key for key in listed if key.startswith('column_')]
        if standings or column_keys:
            sections.addWidget(self._heading('Standings'))
            self._boxes(sections, listed, standings)
            if column_keys:
                # Rows of COLUMNS_PER_ROW, so the window keeps its width as columns are added.
                grid = QGridLayout()
                grid.setHorizontalSpacing(14)
                grid.addWidget(QLabel('Columns:'), 0, 0)
                for index, key in enumerate(column_keys):
                    row, place = divmod(index, COLUMNS_PER_ROW)
                    grid.addWidget(self._box(key, *listed[key]), row, place + 1)
                grid.setColumnStretch(COLUMNS_PER_ROW + 1, 1)
                sections.addLayout(grid)
            self._follow_needs()
        if any(key in listed for key in GROUPS['sections']):
            sections.addWidget(self._heading('Sections'))
            self._boxes(sections, listed, GROUPS['sections'])
        sections.addWidget(self._heading('Radar'))
        if 'radar_cockpit_only' in listed:
            sections.addLayout(self._camera_row(*listed['radar_cockpit_only']))
        self._boxes(sections, listed, GROUPS['radar'])
        self.radar_seconds = self._seconds_box(radar_seconds, RADAR_SECONDS, self.radar_seconds_changed)
        self.radar_seconds.setToolTip('How far ahead of or behind you a car shows the radar')
        sections.addLayout(self._row(QLabel('Shows a car within:'), self.radar_seconds))
        sections.addWidget(self._heading('Flags'))
        self._boxes(sections, listed, GROUPS['flags'])
        self.blue_seconds = self._seconds_box(blue_seconds, BLUE_SECONDS, self.blue_seconds_changed)
        self.blue_seconds.setToolTip('How far behind you a car about to lap you shows the blue flag')
        sections.addLayout(self._row(QLabel('Blue flag for a car within:'), self.blue_seconds))
        sections.addStretch()

        # Anything not placed above (a new option) still shows, in the last tab.
        rest = [key for key in listed if key not in self.options and key != 'radar_cockpit_only']
        self.read_buttons = {}
        if rest or reads_per_second is not None:
            race = self._tab('Race', 'How often the race is read, and any other option')
            if reads_per_second is not None:
                race.addWidget(self._heading('Reading the race'))
                race.addLayout(self._reads_row(reads_per_second))
            if rest:
                race.addWidget(self._heading('More'))
                self._boxes(race, listed, rest)
            race.addStretch()
        row = QHBoxLayout()
        close = QPushButton('Close')
        close.clicked.connect(self.close_window)
        # Without the three dots (asked for by the user on 2026-11-20), as the move-mode panel's buttons.
        classes = QPushButton('Car classes')
        classes.setToolTip('Every car class a clan tag can name, in its colour')
        classes.clicked.connect(self.open_class_sheet)
        about = QPushButton('About')
        about.setToolTip("TurboHUD's name and version")
        about.clicked.connect(self.about_requested)
        row.addWidget(classes)
        row.addWidget(about)
        row.addStretch()
        row.addWidget(close)
        outer.addLayout(row)
        self.show_chosen()
        self.adjustSize()

    def set_fonts(self, families, chosen):
        """Offer `families` ({family: file name}) and the system font, `chosen` ('' for the system's)
        picked; a chosen family no longer there is listed as missing."""
        self.font_choice.blockSignals(True)
        self.font_choice.clear()
        self.font_choice.addItem(SYSTEM_FONT, '')
        for family, file in families.items():
            self.font_choice.addItem(family, family)
            self.font_choice.setItemData(self.font_choice.count() - 1, file, Qt.ToolTipRole)
        if chosen and chosen not in families:
            self.font_choice.addItem(f'{chosen} (missing)', chosen)
        self.font_choice.setCurrentIndex(max(self.font_choice.findData(chosen), 0))
        self.font_choice.blockSignals(False)

    def _font_picked(self, index):
        family = self.font_choice.itemData(index)
        if family is not None:
            self.font_chosen.emit(family)

    def _tab(self, name, tip):
        """A new tab named `name`: its column, to fill from the top."""
        page = QWidget()
        # The page alone see-through: a rule without a selector reached its buttons, drop-down and
        # number boxes too, leaving their dark text on the window's navy on Linux (reported by the
        # user on 2026-11-28), while Close beneath the tabs kept its button face.
        page.setObjectName(TAB_PAGE)
        page.setStyleSheet(f'#{TAB_PAGE} {{ background: transparent; }}')
        column = QVBoxLayout(page)
        column.setContentsMargins(2, 0, 2, 0)
        column.setSpacing(6)
        self.tabs.addTab(page, name)
        self.tabs.setTabToolTip(self.tabs.count() - 1, tip)
        return column

    @staticmethod
    def _row(*widgets):
        """`widgets` side by side from the left."""
        row = QHBoxLayout()
        for widget in widgets:
            row.addWidget(widget)
        row.addStretch()
        return row

    def _colour_blind(self, column, mode, chosen, sections):
        """Colour-blind friendly colours as Off, All sections or Chosen sections, with a tick for each section
        (asked for by the user on 2026-11-21: for all of them or for the ones chosen)."""
        column.addWidget(self._heading('Colour-blind friendly colours'))
        group = QButtonGroup(self)
        buttons = []
        for key, text, about in COLOUR_BLIND_CHOICES:
            button = QPushButton(text)
            button.setCheckable(True)
            button.setChecked(key == mode)
            button.setStyleSheet(READS_BUTTON)
            button.setToolTip(about)
            group.addButton(button)
            button.clicked.connect(lambda _checked=False: self._colour_blind_picked())
            self.colour_buttons[key] = button
            buttons.append(button)
        column.addLayout(self._row(*buttons))
        note = QLabel(COLOUR_BLIND_NOTE)
        note.setWordWrap(True)
        note.setStyleSheet(f'color: {HEADING};')
        column.addWidget(note)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        for index, (name, label) in enumerate(sections):
            box = QCheckBox(label)
            box.setStyleSheet(f'QCheckBox {{ color: white; }} QCheckBox:disabled {{ color: {UNUSABLE}; }}')
            box.setChecked(name in chosen)
            box.setToolTip(f'{label} in colour-blind friendly colours (with Chosen sections)')
            box.toggled.connect(lambda _checked: self._colour_blind_picked())
            row, place = divmod(index, SECTIONS_PER_ROW)
            grid.addWidget(box, row, place)
            self.colour_boxes[name] = box
        grid.setColumnStretch(SECTIONS_PER_ROW, 1)
        column.addLayout(grid)
        self._follow_colour_blind()

    def colour_blind(self):
        """(mode, chosen sections) as the Colours tab shows them."""
        mode = next((key for key, button in self.colour_buttons.items() if button.isChecked()), 'off')
        return mode, tuple(name for name, box in self.colour_boxes.items() if box.isChecked())

    def _follow_colour_blind(self):
        """The section ticks usable only with Chosen sections (their ticks kept)."""
        chosen = self.colour_blind()[0] == 'chosen'
        for box in self.colour_boxes.values():
            box.setEnabled(chosen)

    def _colour_blind_picked(self):
        self._follow_colour_blind()
        self.colour_blind_changed.emit(*self.colour_blind())

    @staticmethod
    def _legacy_swatches():
        """TSU's colours, to see what Legacy colours draws: each value's name on its colour."""
        row = QHBoxLayout()
        for kind, colour in LEGACY_BARS.items():
            label = QLabel(kind.capitalize())
            label.setStyleSheet(f'background: {colour}; color: white; border-radius: 4px; padding: 2px 10px;')
            label.setToolTip(f"TSU's {kind} colour, {colour}")
            row.addWidget(label)
        row.addStretch()
        return row

    @staticmethod
    def _heading(text):
        label = QLabel(f'<small><b>{text.upper()}</b></small>')
        label.setStyleSheet(f'color: {HEADING}; padding-top: 6px;')
        return label

    def _box(self, key, label, on, tip):
        box = QCheckBox(label)
        box.setStyleSheet(f'QCheckBox {{ color: white; }} QCheckBox:disabled {{ color: {UNUSABLE}; }}')
        box.setChecked(on)
        box.setToolTip(tip)
        box.setProperty('tip', tip)  # its own tooltip, back once what it needs is on (_follow_needs)
        box.toggled.connect(lambda checked, k=key: self.option_changed.emit(k, checked))
        box.toggled.connect(lambda _checked: self._follow_needs())
        self.options[key] = box
        return box

    def _follow_needs(self):
        """Grey out each option whose NEEDS is off (keeping its tick), with NEEDS_TIP as its tooltip."""
        for key, needed in NEEDS.items():
            box, other = self.options.get(key), self.options.get(needed)
            if box is None or other is None:
                continue
            usable = other.isChecked()
            box.setEnabled(usable)
            box.setToolTip(box.property('tip') if usable else NEEDS_TIP)

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
            self._follow_needs()  # its signals were held: the options that need it follow here

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
