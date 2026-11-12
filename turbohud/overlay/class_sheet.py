"""The class sheet: every car class a clan tag can name, by category in its colour, to look up
(asked for by the user on 2026-11-12). Opened from the settings window; it changes nothing."""

import html
import logging

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from turbohud.core.class_registry import sheet_columns

log = logging.getLogger(__name__)

NAME_COLOR = '#c8d0dc'  # a class's name, beside its code in the category's colour
HOW_TO = (
    'Put a class code in your clan tag in TSU, such as [GT3], with or without the brackets, in any'
    ' case. With two or more classes in a race, the lap times are grouped by class, each in its'
    " category's colour. Two classes of one category in a race: the one listed first keeps the"
    " colour, the other takes the next category's free colour. A class in a paler colour comes from"
    " the driver's car, as others in the same car named it."
)


def column_html(groups):
    """One column of the sheet as rich text: each category's name, then its codes and names."""
    parts = []
    for category, classes in groups:
        parts.append(
            f'<p style="margin: 6px 0 2px 0;"><b style="color: {category.color};">{html.escape(category.name)}</b></p>'
        )
        rows = ''.join(
            f'<tr><td style="color: {category.color}; padding-right: 8px;"><b>{html.escape(c.code)}</b></td>'
            f'<td style="color: {NAME_COLOR};">{html.escape(c.name)}</td></tr>'
            for c in classes
        )
        parts.append(f'<table cellspacing="0" cellpadding="0">{rows}</table>')
    return ''.join(parts)


class ClassSheet(QWidget):
    """The car classes, in columns by category (sheet_columns)."""

    closed = Signal()

    focusable = True  # it takes clicks on its button

    def __init__(self, native, flags):
        super().__init__(None, flags)
        self.native = native
        self.setWindowTitle('TurboHUD - car classes')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet('QLabel { color: white; }')
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.addWidget(QLabel('<b>TurboHUD - car classes</b>'))
        how_to = QLabel(HOW_TO)
        how_to.setWordWrap(True)
        column.addWidget(how_to)
        columns = QHBoxLayout()
        columns.setSpacing(18)
        for groups in sheet_columns():
            label = QLabel(column_html(groups))
            label.setTextFormat(Qt.RichText)
            label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            columns.addWidget(label, 0, Qt.AlignTop)
        column.addLayout(columns)
        how_to.setFixedWidth(columns.sizeHint().width())  # wrapped to the columns, not wider
        row = QHBoxLayout()
        row.addStretch()
        close = QPushButton('Close')
        close.clicked.connect(self.close_window)
        row.addWidget(close)
        column.addLayout(row)
        self.adjustSize()

    def mousePressEvent(self, event):
        # Dragged by its background, as the settings window is.
        if event.button() == Qt.LeftButton and self.windowHandle() is not None:
            self.windowHandle().startSystemMove()

    def show_at(self, x, y):
        self.move(x, y)
        self.show()
        log.info('class sheet: %s', self.native.raise_window(self))

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
