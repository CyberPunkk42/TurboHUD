"""Linux and other systems.

On Hyprland (Wayland), where Qt cannot keep a window on top, TurboHUD asks Hyprland at
runtime to float, place and pin its own window, and gives the keyboard focus back to
the window that had it (turbohud.overlay.hyprland). Elsewhere Qt's stay-on-top hint does
the work, as it does on X11.

Shortcuts: on Hyprland, the same keys as on Windows and the Mac, added to Hyprland's live
keymap while TurboHUD runs (turbohud.overlay.hyprland). Elsewhere none; the tray icon's menu
and the command line (turbohud.control) do it, and a player can bind those to keys.
"""

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from turbohud.overlay import LOCK_KEY, LOCK_KEY_BACKUP, hyprland

APP_ID = 'TurboHUD'  # the Wayland app id, which desktops show as the window's class
FIND_TRIES = 40  # times 50 ms: how long to wait for the window to appear in Hyprland
FIND_STEP_MS = 50
PLACE_TRIES = 3  # Hyprland may refuse requests for a window that has only just appeared
PLACE_RETRY_MS = 250
REBIND_MS = 200  # after Hyprland reloaded its config, which drops TurboHUD's keys
# A window opening on Hyprland keeps its size this long, so that Hyprland floats it at once, at its
# size, not tiled first and then floated (Hyprland floats a window of a fixed size as it opens).
FIXED_AT_OPEN_MS = 500
SHORTCUT_NAMES = {'--toggle': 'move mode', '--quit': 'quit', '--preset': 'layout'}

log = logging.getLogger(__name__)


class FloatAtOpen(QObject):
    """Each TurboHUD window that takes clicks, and each place label, is given a fixed size, its own,
    for a moment as it opens on Hyprland (FIXED_AT_OPEN_MS): Hyprland then floats it at once, where
    it would otherwise tile it, large, until TurboHUD's requests floated it, a jump from large to its
    size the player saw (reported by the user on 2026-11-20: the settings and the layouts windows).
    Only TurboHUD's own windows: an event filter on its own app, no rule in Hyprland."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.kept = {}  # id(window) -> (window, its least size, its largest size), while fixed

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Show and isinstance(watched, QWidget):
            self.fix(watched)
        return False

    def fix(self, widget):
        if not widget.isWindow() or widget.windowType() in (Qt.Popup, Qt.ToolTip) or id(widget) in self.kept:
            return
        # Windows that take clicks (the settings, the layouts, the panel, dialogs) and the place labels;
        # not the sections, which TurboHUD may size again just after they open.
        if not (
            getattr(widget, 'focusable', False)
            or getattr(widget, 'float_at_open', False)
            or isinstance(widget, QDialog)
        ):
            return
        key = id(widget)
        self.kept[key] = (widget, widget.minimumSize(), widget.maximumSize())
        widget.setFixedSize(widget.size())
        QTimer.singleShot(FIXED_AT_OPEN_MS, lambda: self.release(key))

    def release(self, key):
        """Its own least and largest sizes again (a window may be resized later)."""
        widget, least, largest = self.kept.pop(key, (None, None, None))
        if widget is None:
            return
        try:
            widget.setMinimumSize(least)
            widget.setMaximumSize(largest)
        except RuntimeError:  # closed and deleted meanwhile
            pass


def place_rank(widget):
    """Which of TurboHUD's windows Hyprland places first: those taking clicks (the panel, the settings),
    then the sections, then the place labels (empty until a drag)."""
    if getattr(widget, 'focusable', False):
        return 0
    return 2 if getattr(widget, 'float_at_open', False) else 1


def own_command(args, frozen=None, executable=None, source=None):
    """The command line that tells this TurboHUD to do something (turbohud.control): the
    bundled program itself, or from the source folder this Python with launch_turbohud.py."""
    frozen = getattr(sys, 'frozen', False) if frozen is None else frozen
    executable = executable or sys.executable
    if frozen:
        return [executable, *args]
    source = source or Path(__file__).resolve().parents[2] / 'launch_turbohud.py'
    return [executable, '-B', str(source), *args]


def shortcut_name(args):
    name = SHORTCUT_NAMES[args[0]]
    return f'{name} {args[1]}' if len(args) > 1 else name


class Native:
    name = 'Linux'
    taken_by = 'another Hyprland bind'

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
        self.last_placements = {}  # id(widget) -> where it was last seen
        self.float_at_open = None  # on Hyprland, FloatAtOpen (prepare_app)
        # Windows waiting to be placed (raise_window): id(widget) -> (rank, order, widget, target).
        self.waiting = {}
        self._order = 0
        self._run = []  # the windows placed since the line was last empty: (widget, its address)

    @property
    def keeps_labels_open(self):
        """Move mode's place labels open with it and stay open, empty between drags: on Hyprland a
        window that opens takes the focus, which ends the drag it was opened for."""
        return self.hypr is not None

    def prepare_app(self):
        QGuiApplication.setDesktopFileName(APP_ID)
        self.input_in_place = QGuiApplication.platformName() == 'wayland'
        if self.hypr is not None:
            self.previous = self.hypr.active_window()
            app = QApplication.instance()
            if app is not None and self.float_at_open is None:
                self.float_at_open = FloatAtOpen(app)
                app.installEventFilter(self.float_at_open)

    def raise_window(self, widget):
        if self.hypr is None:
            return 'always on top through Qt'
        target = (widget.x(), widget.y(), widget.width(), widget.height())
        self.last_placements[id(widget)] = target
        if not self.waiting:
            QTimer.singleShot(FIND_STEP_MS, self._place_next)
        self._order += 1
        self.waiting[id(widget)] = (place_rank(widget), self._order, widget, target)
        focus = 'takes clicks' if getattr(widget, 'focusable', False) else 'no keyboard focus'
        return f'Hyprland: floating, pinned, {focus} (requests for its own window only)'

    def _place_next(self):
        """Place the waiting window that matters most (place_rank), one each turn of Qt's loop so that
        the ones placed draw meanwhile. Move mode opens 50 windows or so on Hyprland, a dozen requests
        each: the panel, opened last, came 2 s after the key (reported by the user on 2026-11-20)."""
        if not self.waiting:
            return
        key = min(self.waiting, key=lambda k: self.waiting[k][:2])
        _rank, _order, widget, target = self.waiting.pop(key)
        self._place(widget, target, FIND_TRIES)
        if self.waiting:
            QTimer.singleShot(0, self._place_next)
            return
        self._front_again()

    def _front_again(self):
        """The line is empty: windows taking clicks placed before others go in front of them again
        (the panel above the sections opened after it)."""
        run, self._run = self._run, []
        later = False
        for widget, address in reversed(run):
            if not getattr(widget, 'focusable', False):
                later = True
            elif later and widget.isVisible():
                self.hypr.to_front(address)

    def _place(self, widget, target, tries, place_tries=PLACE_TRIES):
        address = self.hypr.own_window(os.getpid(), widget.windowTitle())
        if address is None:
            if tries > 1:
                QTimer.singleShot(FIND_STEP_MS, lambda: self._place(widget, target, tries - 1))
            else:
                log.info('Hyprland: TurboHUD window not found; it may not stay on top')
            return
        self.addresses[id(widget)] = address
        self._run.append((widget, address))
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
        if not getattr(widget, 'focusable', False):
            # It took the focus as it opened, before Hyprland was told it takes none: back to the
            # game. Not for a window that takes clicks (the settings): the focus is meant for it,
            # and focusing the game moved the mouse to the game's screen (reported on 2026-11-20).
            self.give_focus_back(only_from=address)

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
        """Move mode begins: remember the window that has the focus now (the game, usually),
        for give_focus_back; not the one from TurboHUD's start, such as the terminal it came from."""
        if self.hypr is None:
            return
        active = self.hypr.active_window()
        if active and active not in self.addresses.values():
            self.previous = active

    def activate(self, widget):
        """Nothing yet: focusing the panel on Hyprland would move the mouse onto it."""
        return 'left to the desktop'

    def give_focus_back(self, only_from=None):
        """Back to the window that had the focus, only where one of TurboHUD's own windows (the
        panel) has it now (`only_from`: only where that one has it). Hyprland moves the mouse onto
        a window it focuses, so focusing it when the focus never left made the mouse jump to it
        (reported by the user on 2026-11-15)."""
        if self.hypr is None or not self.previous or self.previous in self.addresses.values():
            return
        active = self.hypr.active_window()
        if active not in self.addresses.values() or (only_from is not None and active != only_from):
            return
        self.hypr.focus(self.previous)

    def register_hotkeys(self, on_hotkey):
        """On Hyprland, TurboHUD's keys in its live keymap, each running TurboHUD's command
        line; True if move mode and quit have one. `on_hotkey` is not called: the command
        line reaches the running TurboHUD. Elsewhere none."""
        self.lock_keys = []
        self.bound = []
        if self.hypr is None:
            return False
        shortcuts = self._bind_all()
        if self.bound:
            self._watch_reloads()
        return shortcuts

    def _bind_all(self):
        binds = self.hypr.binds()

        def take(keys, args):
            owner = self.hypr.bind_owner(keys, binds)
            if owner == 'other':
                log.warning('Hyprland: %s is bound to something else; TurboHUD leaves it', keys)
                return False
            if owner == 'turbohud':  # left by a TurboHUD that did not quit
                self.hypr.unbind(keys)
            if self.hypr.bind(keys, own_command(list(args)), shortcut_name(args)):
                self.bound.append(keys)
                return True
            return False

        (lock_keys, lock_args), (quit_keys, quit_args), *presets = hyprland.SHORTCUTS
        if take(lock_keys, lock_args):
            self.lock_keys = [LOCK_KEY]
        elif take(hyprland.LOCK_BIND_BACKUP, lock_args):
            self.lock_keys = [LOCK_KEY_BACKUP]
        quit_ok = take(quit_keys, quit_args)
        for keys, args in presets:
            take(keys, args)
        log.info('Hyprland: shortcuts %s while TurboHUD runs', ', '.join(self.bound) or 'none')
        return bool(self.lock_keys) and quit_ok

    def _watch_reloads(self):
        """Add the keys again after Hyprland reloaded its config (Omarchy does at a theme
        change, Hyprland when a config file is saved): a reload drops them."""
        from PySide6.QtNetwork import QLocalSocket

        path = hyprland.event_socket()
        if path is None:
            log.info('Hyprland: no event socket; a config reload drops the shortcuts')
            return
        self.events = QLocalSocket()
        self.event_text = ''
        self.events.readyRead.connect(self._read_events)
        self.events.connectToServer(path)

    def _read_events(self):
        self.event_text += bytes(self.events.readAll()).decode('utf-8', 'replace')
        *lines, self.event_text = self.event_text.split('\n')
        if any(line.startswith('configreloaded>>') for line in lines):
            log.info('Hyprland reloaded its config: adding the shortcuts again')
            QTimer.singleShot(REBIND_MS, self._rebind)

    def _rebind(self):
        self.bound = []
        self._bind_all()

    def unregister_hotkeys(self):
        """Take TurboHUD's keys out of Hyprland's keymap again: only those still its own."""
        events = getattr(self, 'events', None)
        if events is not None:
            events.readyRead.disconnect(self._read_events)
            events.abort()
            self.events = None
        bound = getattr(self, 'bound', [])
        if self.hypr is None or not bound:
            return
        binds = self.hypr.binds()
        for keys in bound:
            if self.hypr.bind_owner(keys, binds) == 'turbohud':
                self.hypr.unbind(keys)
        log.info('Hyprland: shortcuts removed')
        self.bound = []
