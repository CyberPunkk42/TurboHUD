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
        self.addresses = {}  # id(widget) -> its window in Hyprland, once found
        self.previous = None  # the window that had the focus before TurboHUD appeared
        # Wayland: switching click-through must not re-create the window, which would
        # make Hyprland tile it again.
        self.input_in_place = False
        # Lock move mode when another window becomes active (the Mac's way)? Not on
        # Hyprland: there the focus follows the mouse, which would end move mode at once.
        self.auto_lock = self.hypr is None
        self.last_placements = {}  # id(widget) -> where it was last seen

    def prepare_app(self):
        QGuiApplication.setDesktopFileName(APP_ID)
        self.input_in_place = QGuiApplication.platformName() == 'wayland'
        if self.hypr is not None:
            self.previous = self.hypr.active_window()

    def raise_window(self, widget):
        if self.hypr is None:
            return 'always on top through Qt'
        target = (widget.x(), widget.y(), widget.width(), widget.height())
        self.last_placements[id(widget)] = target
        QTimer.singleShot(FIND_STEP_MS, lambda: self._place(widget, target, FIND_TRIES))
        focus = 'takes clicks' if getattr(widget, 'focusable', False) else 'no keyboard focus'
        return f'Hyprland: floating, pinned, {focus} (requests for its own window only)'

    def _place(self, widget, target, tries, place_tries=PLACE_TRIES):
        address = self.hypr.own_window(os.getpid(), widget.windowTitle())
        if address is None:
            if tries > 1:
                QTimer.singleShot(FIND_STEP_MS, lambda: self._place(widget, target, tries - 1))
            else:
                log.info('Hyprland: TurboHUD window not found; it may not stay on top')
            return
        self.addresses[id(widget)] = address
        ok = self.hypr.place(address, *target, focusable=getattr(widget, 'focusable', False))
        if not ok and place_tries > 1:
            log.info('Hyprland: trying again')
            QTimer.singleShot(PLACE_RETRY_MS, lambda: self._place(widget, target, 1, place_tries - 1))
            return
        log.info(
            'Hyprland: window %s placed at %s%s', address, target, '' if ok else ' (some requests refused)'
        )
        if not getattr(widget, 'locked', True):
            self.hypr.set_focusable(address, True)  # move mode began before it was placed
        self.give_focus_back()

    def set_movable(self, widget, movable):
        """Move mode on or off for a shown window: on Hyprland it must take the mouse to
        be dragged, and must not when locked."""
        address = self.addresses.get(id(widget))
        if self.hypr is not None and address is not None:
            self.hypr.set_focusable(address, movable)

    def placement(self, widget):
        """Where the window really is: on Wayland, Qt does not know its position. Once
        the window is gone (Qt closes it when quitting), the last known place."""
        address = self.addresses.get(id(widget))
        if self.hypr is None or address is None:
            return None
        if widget.isVisible():
            seen = self.hypr.geometry(address)
            if seen:
                self.last_placements[id(widget)] = seen
        return self.last_placements.get(id(widget))

    def placements(self, widgets):
        """{id(widget): place} for shown windows, with one question to Hyprland for all
        of them (move mode asks a few times a second while sections are grouped)."""
        if self.hypr is None:
            return {id(w): (w.x(), w.y(), w.width(), w.height()) for w in widgets}
        addresses = {self.addresses.get(id(w)): w for w in widgets if w.isVisible()}
        addresses.pop(None, None)
        for address, place in self.hypr.geometries(set(addresses)).items():
            self.last_placements[id(addresses[address])] = place
        return {id(w): self.last_placements[id(w)] for w in widgets if id(w) in self.last_placements}

    def move_window(self, widget, place, settle=False):
        """Move a window to `place` (x, y, width, height), for a group following a drag.
        `settle` once the drag is over: on Hyprland it then also gets its workspace and pin
        again, in case it went to another monitor."""
        x, y, width, height = place
        if self.hypr is None:
            widget.setGeometry(x, y, width, height)
            return
        address = self.addresses.get(id(widget))
        if address is None:
            return
        self.last_placements[id(widget)] = tuple(place)
        if settle:
            self.hypr.place(address, x, y, width, height, focusable=not getattr(widget, 'locked', True))
        else:
            self.hypr.move(address, x, y)

    def take_focus(self):
        pass

    def give_focus_back(self):
        if self.hypr is not None and self.previous and self.previous not in self.addresses.values():
            self.hypr.focus(self.previous)

    def register_hotkeys(self, on_hotkey):
        self.lock_keys = []
        return False

    def unregister_hotkeys(self):
        pass
