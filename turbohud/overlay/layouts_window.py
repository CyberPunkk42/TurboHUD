"""The layouts window, opened from the move-mode panel: the presets, each with a name, which
preset loads by itself as an event of each mode begins, layout files and the design screen.

Asked for by players on 2026-11-15: five presets that can be named (for recordings, practice,
qualifying, racing ...), loaded by themselves by the kind of event; and the user: the presets and
the design screen in a window of their own, so the panel is not crowded. Like the settings window,
choices are buttons rather than drop-downs where it can be (a drop-down's list is one more window,
which a tiling desktop could place anywhere); only Design for keeps its list of sizes.
"""

import logging

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from turbohud.core.presets import SCREENS
from turbohud.core.settings import EVENT_MODES, PRESET_NAME_MOST, PRESETS, preset_label, preset_name
from turbohud.overlay.settings_window import HEADING, READS_BUTTON

log = logging.getLogger(__name__)

WORD_BUTTON = 54  # as the panel's word buttons (window.PANEL_WORD_BUTTON)
NAME_WIDTH = 150  # the name boxes: about PRESET_NAME_MOST letters
OFF = 0  # a mode's choice when no preset loads for it
# What each mode covers, for its tooltip.
MODE_TIPS = {
    'recording': 'A recording (replay) TSU plays',
    'hotlapping': 'A hotlapping event, as qualifying is run',
    'race': 'A race: laps of a circuit, or from A to B',
    'special': 'An arena event: Battle (deathmatch), Sumo, King of the Hill, Tag, Soccer and the others',
}


class LayoutsWindow(QWidget):
    """Presets 1 to 5 with a name, Save, Load and Delete each; per event mode the preset that
    loads as such an event begins (or Off); Load screen default, Export and Import; the design
    screen. The move-mode panel passes its signals on to the app."""

    preset_save_requested = Signal(int)  # the preset's number
    preset_load_requested = Signal(int)
    preset_delete_requested = Signal(int)
    preset_renamed = Signal(int, str)  # the preset's number, its name ('' for none)
    auto_preset_changed = Signal(str, int)  # an event mode (EVENT_MODES), the preset (OFF: none)
    screen_default_requested = Signal()
    export_requested = Signal()
    import_requested = Signal()
    design_requested = Signal(int, int)  # width, height
    design_save_requested = Signal()
    design_cancel_requested = Signal()

    focusable = True  # it takes clicks and typed names

    def __init__(self, native, flags, shortcuts, saved_presets=(), names=None, auto_presets=None):
        super().__init__(None, flags)
        self.native = native
        self.shortcuts = shortcuts
        self.saved = set(saved_presets)
        self.names = dict(names or {})
        self.setWindowTitle('TurboHUD - Layouts')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet('QLabel { color: white; }')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(6)
        outer.addWidget(QLabel('<b>TurboHUD - Layouts</b>'))

        outer.addWidget(self._heading('Presets'))
        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(3)
        self.name_boxes, self.preset_saves, self.preset_loads, self.preset_deletes = {}, {}, {}, {}
        for line, number in enumerate(PRESETS):
            grid.addWidget(QLabel(f'<b>{number}</b>'), line, 0, Qt.AlignRight)
            name = QLineEdit(self.names.get(number, ''))
            name.setMaxLength(PRESET_NAME_MOST)
            name.setPlaceholderText('Name')
            name.setFixedWidth(NAME_WIDTH)
            name.setToolTip(f'A name for preset {number}, such as Race or Recordings')
            name.editingFinished.connect(lambda n=number: self._renamed(n))
            grid.addWidget(name, line, 1)
            self.name_boxes[number] = name
            for column, (text, store, signal) in enumerate(
                (
                    ('Save', self.preset_saves, self.preset_save_requested),
                    ('Load', self.preset_loads, self.preset_load_requested),
                    ('Delete', self.preset_deletes, self.preset_delete_requested),
                ),
                start=2,
            ):
                button = QPushButton(text)
                button.setMinimumWidth(WORD_BUTTON)
                button.clicked.connect(lambda _checked=False, n=number, s=signal: s.emit(n))
                grid.addWidget(button, line, column)
                store[number] = button
            self.preset_deletes[number].setAccessibleName(f'Delete preset {number}')
        grid.setColumnStretch(5, 1)
        outer.addLayout(grid)

        outer.addWidget(self._heading('Load by itself'))
        outer.addWidget(QLabel('As an event begins, the preset chosen for its mode:'))
        modes = QGridLayout()
        modes.setHorizontalSpacing(4)
        modes.setVerticalSpacing(3)
        self.auto_buttons = {}
        chosen = dict(auto_presets or {})
        for line, (mode, text) in enumerate(EVENT_MODES):
            label = QLabel(text)
            label.setToolTip(MODE_TIPS[mode])
            modes.addWidget(label, line, 0)
            group = QButtonGroup(self)
            self.auto_buttons[mode] = {}
            for column, number in enumerate((OFF, *PRESETS), start=1):
                button = QPushButton('Off' if number == OFF else str(number))
                button.setCheckable(True)
                button.setChecked(chosen.get(mode, OFF) == number)
                button.setStyleSheet(READS_BUTTON)
                group.addButton(button, number)
                modes.addWidget(button, line, column)
                self.auto_buttons[mode][number] = button
            group.idClicked.connect(lambda number, m=mode: self.auto_preset_changed.emit(m, number))
        modes.setColumnStretch(len(PRESETS) + 2, 1)
        outer.addLayout(modes)

        outer.addWidget(self._heading('Files and screens'))
        files = QHBoxLayout()
        self.layout_buttons = {}
        for text, tip, signal in (
            (
                'Load screen default',
                (
                    "The layout TurboHUD comes with for this screen's size (fitted where none is made for it);"
                    ' one step for Undo'
                ),
                self.screen_default_requested,
            ),
            ('Export…', 'Save the layout to a file, to share it or keep it', self.export_requested),
            (
                'Import…',
                'Load a layout from a file, fitted to this screen if made for another; one step for Undo',
                self.import_requested,
            ),
        ):
            button = QPushButton(text)
            button.setMinimumWidth(WORD_BUTTON)
            button.setToolTip(tip)
            button.clicked.connect(signal)
            files.addWidget(button)
            self.layout_buttons[text] = button
        files.addStretch()
        outer.addLayout(files)

        outer.addWidget(self._heading('Design'))
        designing = QHBoxLayout()
        designing.addWidget(QLabel('Design for:'))
        self.design_size = QComboBox()
        # As wide as its longest size, "(this screen)" included (set_own_screen).
        self.design_size.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        for width, height in SCREENS:
            self.design_size.addItem(f'{width}x{height}', (width, height))
        self.design_size.setToolTip('A screen size to make the layout for, shown to scale on this screen')
        designing.addWidget(self.design_size)
        self.design = QPushButton('Design')
        self.design.setToolTip('Show that screen size as a frame here, its layout inside to arrange')
        self.design.clicked.connect(lambda: self.design_requested.emit(*self.design_size.currentData()))
        self.design_save = QPushButton('Save design…')
        self.design_save.setToolTip(
            'Save the layout in the frame, at full size, as a file for that screen size'
        )
        self.design_save.clicked.connect(self.design_save_requested)
        self.design_cancel = QPushButton('Cancel')
        self.design_cancel.setToolTip('Leave the design screen; your own layout comes back')
        self.design_cancel.clicked.connect(self.design_cancel_requested)
        for button in (self.design, self.design_save, self.design_cancel):
            button.setMinimumWidth(WORD_BUTTON)
            designing.addWidget(button)
        designing.addStretch()
        outer.addLayout(designing)

        row = QHBoxLayout()
        row.addStretch()
        close = QPushButton('Close')
        close.clicked.connect(self.hide)
        row.addWidget(close)
        outer.addLayout(row)
        self.set_designing(False)
        self._show_presets()
        self.adjustSize()

    @staticmethod
    def _heading(text):
        label = QLabel(f'<small><b>{text.upper()}</b></small>')
        label.setStyleSheet(f'color: {HEADING}; padding-top: 6px;')
        return label

    def _renamed(self, number):
        box = self.name_boxes[number]
        name = preset_name(box.text())
        if box.text() != name:
            box.setText(name)
        if self.names.get(number, '') == name:
            return
        self.names = {n: kept for n, kept in self.names.items() if n != number}
        if name:
            self.names[number] = name
        self._show_presets()
        self.preset_renamed.emit(number, name)

    def _show_presets(self):
        """Load and Delete only for a saved preset; the tooltips with each preset's name."""
        for number in PRESETS:
            called = preset_label(number, self.names)
            saved = number in self.saved
            self.preset_saves[number].setToolTip(
                f'Keep the layout as it is now in preset {called}, replacing what was there'
            )
            load = self.preset_loads[number]
            load.setEnabled(saved)
            load.setToolTip(
                f'Put the sections as preset {called} has them'
                + (f', also with Ctrl+Shift+{number}' if self.shortcuts else '')
            )
            self.preset_deletes[number].setEnabled(saved)
            self.preset_deletes[number].setToolTip(f'Delete preset {called}; Undo brings it back')
            for buttons in self.auto_buttons.values():
                buttons[number].setToolTip(
                    f'Preset {called}' + ('' if saved else ' (empty: save it first, or nothing loads)')
                )
        for buttons in self.auto_buttons.values():
            buttons[OFF].setToolTip('No preset loads by itself for this mode')

    def set_presets_saved(self, numbers):
        self.saved = set(numbers)
        self._show_presets()

    def set_preset_names(self, names):
        """Show the presets' names (set elsewhere), saying nothing back."""
        self.names = dict(names)
        for number, box in self.name_boxes.items():
            if box.text() != self.names.get(number, ''):
                box.setText(self.names.get(number, ''))
        self._show_presets()

    def set_auto_preset(self, mode, number):
        """Show a mode's choice (OFF: none), saying nothing back."""
        buttons = self.auto_buttons.get(mode, {})
        button = buttons.get(number) or buttons.get(OFF)
        if button is not None:
            button.setChecked(True)  # a button group: the others go off

    def set_designing(self, designing):
        """Save design and Cancel only while the design screen shows; meanwhile Load screen default
        and Import... are off (they would put a full-size layout over the design). Export... then
        saves the design (the app does it)."""
        self.design_save.setEnabled(designing)
        self.design_cancel.setEnabled(designing)
        for text in ('Load screen default', 'Import…'):
            self.layout_buttons[text].setEnabled(not designing)

    def set_own_screen(self, size):
        """The Design for list with this screen's `size` (width, height) chosen, so Design shows
        one's own layout at 100% straight away (asked for by the user on 2026-11-15); a size the
        list lacks is put in it, in order. It is marked "(this screen)"."""
        own = tuple(size)
        sizes = sorted(set(SCREENS) | {own})
        self.design_size.clear()
        for width, height in sizes:
            mark = ' (this screen)' if (width, height) == own else ''
            self.design_size.addItem(f'{width}x{height}{mark}', (width, height))
        self.design_size.setCurrentIndex(sizes.index(own))
        # The list is wider now: the window grows with it, or the buttons beside it were cut off
        # (reported by the user on 2026-11-15).
        self.design_size.updateGeometry()
        self.layout().invalidate()
        self.layout().activate()
        self.resize(self.sizeHint())

    def mousePressEvent(self, event):
        # Dragged by its background, out of the way of a section if need be.
        if event.button() == Qt.LeftButton and self.windowHandle() is not None:
            self.windowHandle().startSystemMove()

    def show_at(self, x, y):
        self.move(x, y)
        self.show()
        log.info('layouts: %s', self.native.raise_window(self))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(120, 170, 230), 2))
        painter.setBrush(QColor(15, 30, 55, 235))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10)
        painter.end()
