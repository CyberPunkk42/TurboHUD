"""File and message windows that open above TurboHUD's own windows.

On the Mac TurboHUD keeps its windows at a window level above TSU's Fullscreen (macos.WINDOW_LEVEL),
and the system's own save and open windows open at the normal level: Export, Import and Save design
opened behind the move-mode panel, the layouts window and the sections (reported by the user on
2026-11-15). Where the Native asks for it (`dialogs_on_top`, the Mac), these use Qt's own file
window, which TurboHUD can put on its level like its other windows; elsewhere the system's own, as
before.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox


def on_top(dialog, native):
    """`dialog` made to open above TurboHUD's windows where the system needs it (the Mac): on top,
    raised to TurboHUD's level as it opens, and taking the keyboard (a name is typed in it)."""
    if not getattr(native, 'dialogs_on_top', False):
        return dialog
    if isinstance(dialog, QFileDialog):
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)  # the system's own cannot be raised
    dialog.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dialog.focusable = True
    QTimer.singleShot(0, lambda: _raise(dialog, native))  # once exec() has shown it
    return dialog


def _raise(dialog, native):
    """On TurboHUD's level, then in front of its windows there: raised alone, it went behind them
    (the settings window, 2026-11-17)."""
    native.raise_window(dialog)
    activate = getattr(native, 'activate', None)
    if activate is not None:
        activate(dialog)


def save_path(parent, native, title, suggested, filter_):
    """A path to save to, chosen by the player, or '' where they cancelled."""
    dialog = QFileDialog(parent, title, str(suggested), filter_)
    dialog.setAcceptMode(QFileDialog.AcceptSave)
    dialog.selectFile(str(suggested))
    return _chosen(on_top(dialog, native))


def open_path(parent, native, title, folder, filter_):
    """A file to open, chosen by the player, or '' where they cancelled."""
    dialog = QFileDialog(parent, title, str(folder), filter_)
    dialog.setAcceptMode(QFileDialog.AcceptOpen)
    dialog.setFileMode(QFileDialog.ExistingFile)
    return _chosen(on_top(dialog, native))


def _chosen(dialog):
    if dialog.exec() != QFileDialog.Accepted:
        return ''
    files = dialog.selectedFiles()
    return files[0] if files else ''


def warn(parent, native, text):
    """A warning with an OK button, above TurboHUD's windows."""
    box = QMessageBox(QMessageBox.Warning, 'TurboHUD', text, QMessageBox.Ok, parent)
    on_top(box, native).exec()


__all__ = ['on_top', 'open_path', 'save_path', 'warn']
