"""Linux and other systems. No system-wide shortcuts yet; the tray icon's menu switches
move mode instead.

On Hyprland (Wayland), where Qt cannot keep a window on top, TurboHUD asks Hyprland at
runtime to float, place and pin its own window, and gives the keyboard focus back to
the window that had it (turbohud.overlay.hyprland). Elsewhere Qt's stay-on-top hint does
the work, as it does on X11.
"""

import logging
import os

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

from turbohud.overlay import hyprland

APP_ID = 'TurboHUD'  # the Wayland app id, which desktops show as the window's class
FIND_TRIES = 40  # times 50 ms: how long to wait for the window to appear in Hyprland
FIND_STEP_MS = 50
PLACE_TRIES = 3  # Hyprland may refuse requests for a window that has only just appeared
PLACE_RETRY_MS = 250

log = logging.getLogger(__name__)


class Native:
    name = 'Linux'

    def __init__(self, hypr='detect'):
        """`hypr`: a turbohud.overlay.hyprland.Hyprland, None for none, or 'detect'."""
        if hypr == 'detect':
            hypr = hyprland.Hyprland() if hyprland.available() else None
        self.hypr = hypr
        self.address = None  # TurboHUD's window in Hyprland, once found
        self.previous = None  # the window that had the focus before TurboHUD appeared
        # Wayland: switching click-through must not re-create the window, which would
        # make Hyprland tile it again.
        self.input_in_place = False
        # Lock move mode when another window becomes active (the Mac's way)? Not on
        # Hyprland: there the focus follows the mouse, which would end move mode at once.
        self.auto_lock = self.hypr is None
        self.last_placement = None

    def prepare_app(self):
        QGuiApplication.setDesktopFileName(APP_ID)
        self.input_in_place = QGuiApplication.platformName() == 'wayland'
        if self.hypr is not None:
            self.previous = self.hypr.active_window()

    def raise_window(self, widget):
        if self.hypr is None:
            return 'always on top through Qt'
        target = (widget.x(), widget.y(), widget.width(), widget.height())
        self.last_placement = target
        QTimer.singleShot(FIND_STEP_MS, lambda: self._place(widget, target, FIND_TRIES))
        return 'Hyprland: floating, pinned, no keyboard focus (requests for its own window only)'

    def _place(self, widget, target, tries, place_tries=PLACE_TRIES):
        address = self.hypr.own_window(os.getpid(), widget.windowTitle())
        if address is None:
            if tries > 1:
                QTimer.singleShot(FIND_STEP_MS, lambda: self._place(widget, target, tries - 1))
            else:
                log.info('Hyprland: TurboHUD window not found; it may not stay on top')
            return
        self.address = address
        ok = self.hypr.place(address, *target)
        if not ok and place_tries > 1:
            log.info('Hyprland: trying again')
            QTimer.singleShot(PLACE_RETRY_MS, lambda: self._place(widget, target, 1, place_tries - 1))
            return
        log.info('Hyprland: window %s placed at %s%s', address, target, '' if ok else ' (some requests refused)')
        self.give_focus_back()

    def placement(self, widget):
        """Where the window really is: on Wayland, Qt does not know its position. Once
        the window is gone (Qt closes it when quitting), the last known place."""
        if self.hypr is None or self.address is None:
            return None
        if widget.isVisible():
            self.last_placement = self.hypr.geometry(self.address) or self.last_placement
        return self.last_placement

    def take_focus(self):
        pass

    def give_focus_back(self):
        if self.hypr is not None and self.previous and self.previous != self.address:
            self.hypr.focus(self.previous)

    def register_hotkeys(self, on_hotkey):
        return False

    def unregister_hotkeys(self):
        pass
