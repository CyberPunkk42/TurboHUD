"""Windows: system-wide hotkeys and handing the focus back, through ctypes."""

import ctypes
import logging
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

from turbohud.overlay import (
    HOTKEY_LOCK,
    HOTKEY_LOCK_BACKUP,
    HOTKEY_PRESETS,
    HOTKEY_QUIT,
    LOCK_KEY,
    LOCK_KEY_BACKUP,
)

MOD_CONTROL = 0x2
MOD_SHIFT = 0x4
MOD_NOREPEAT = 0x4000
VK_L = 0x4C
VK_F12 = 0x7B
VK_Q = 0x51
VK_ZERO = 0x30  # the keys 1, 2 and 3 follow it
WM_HOTKEY = 0x0312
GW_HWNDNEXT = 2
SWP_NOSIZE = 0x1
SWP_NOMOVE = 0x2
SWP_NOACTIVATE = 0x10
SWP_NOOWNERZORDER = 0x200
MOST_WINDOWS = 100_000  # a walk down the window order stops here, whatever happens

log = logging.getLogger(__name__)
user32 = ctypes.WinDLL('user32', use_last_error=True)
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetTopWindow.argtypes = [wintypes.HWND]
user32.GetTopWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


def lowest(order, wanted):
    """The last of `wanted` in `order` (the windows, front first), or None if none is there."""
    found = None
    for hwnd in order:
        if hwnd in wanted:
            found = hwnd
    return found


def window_order():
    """Every top-level window's handle, front first."""
    hwnd = user32.GetTopWindow(None)
    for _ in range(MOST_WINDOWS):
        if not hwnd:
            return
        yield hwnd
        hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)


class _HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, on_hotkey):
        super().__init__()
        self.on_hotkey = on_hotkey

    def nativeEventFilter(self, event_type, message):
        # Hotkeys registered without a window arrive as thread messages, which Qt's event
        # loop passes here as a pointer to the MSG.
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
            self.on_hotkey(int(msg.wParam))
            return True, 0
        return False, 0


class Native:
    name = 'Windows'
    # A window per section stays (one per screen cost DWM three times the GPU, 2026-11-16), so one tint
    # for each group is a window of its own behind each group (turbohud.overlay.window.GroupTints).
    group_tint_windows = True

    def __init__(self):
        self.previous = None
        self.filter = None

    def prepare_app(self):
        pass

    def raise_window(self, widget):
        return 'always on top through Qt'

    def place_below(self, widget, above):
        """`widget`'s window just beneath the lowest of the `above` windows, without taking the
        focus: a group's tint below the sections. All are always on top, so it stays above the game."""
        wanted = {int(window.winId()) for window in above}
        under = lowest(window_order(), wanted)
        if under is None:
            return 'nothing to go below'
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER
        if user32.SetWindowPos(int(widget.winId()), under, 0, 0, 0, 0, flags):
            return 'below its sections'
        return f'not placed (error {ctypes.get_last_error()})'

    def take_focus(self):
        self.previous = user32.GetForegroundWindow()

    def activate(self, widget):
        """Move mode: `widget` (the panel) in front with the focus, so TSU is no longer the
        foreground window. While it is, a race keeps its own pointer hidden and held, so move mode
        showed no pointer until TSU's menu (ESC) let go of it (reported by players, 2026-11-16).
        Windows may refuse a foreground change to a program that did not get the last input (a
        hotkey counts, mostly); then once more with TurboHUD's input joined to the game's."""
        hwnd = int(widget.winId())
        if user32.SetForegroundWindow(hwnd):
            return 'in front'
        front = user32.GetForegroundWindow()
        theirs = user32.GetWindowThreadProcessId(front, None) if front else 0
        ours = kernel32.GetCurrentThreadId()
        if not theirs or theirs == ours:
            return f'not in front (error {ctypes.get_last_error()})'
        user32.AttachThreadInput(ours, theirs, True)
        try:
            done = user32.SetForegroundWindow(hwnd)
        finally:
            user32.AttachThreadInput(ours, theirs, False)
        if done:
            return "in front, joined to the game's input"
        return f'not in front (error {ctypes.get_last_error()})'

    def give_focus_back(self):
        previous, self.previous = self.previous, None
        if previous:
            user32.SetForegroundWindow(previous)

    def register_hotkeys(self, on_hotkey):
        self.filter = _HotkeyFilter(on_hotkey)
        QCoreApplication.instance().installNativeEventFilter(self.filter)
        modifiers = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT

        def register(key, number):
            if user32.RegisterHotKey(None, number, modifiers, key):
                return True
            log.warning('hotkey %d not available (error %d)', number, ctypes.get_last_error())
            return False

        # Move mode on either key: the second is there when another program has the first.
        self.lock_keys = [
            name
            for name, key, number in (
                (LOCK_KEY, VK_L, HOTKEY_LOCK),
                (LOCK_KEY_BACKUP, VK_F12, HOTKEY_LOCK_BACKUP),
            )
            if register(key, number)
        ]
        ok = bool(self.lock_keys) and register(VK_Q, HOTKEY_QUIT)
        # Not in `ok`: without them, a preset still loads from the panel.
        for number, preset in HOTKEY_PRESETS.items():
            if not user32.RegisterHotKey(None, number, modifiers, VK_ZERO + preset):
                log.warning('hotkey %d not available (error %d)', number, ctypes.get_last_error())
        return ok

    def unregister_hotkeys(self):
        for number in (HOTKEY_LOCK, HOTKEY_LOCK_BACKUP, HOTKEY_QUIT, *HOTKEY_PRESETS):
            user32.UnregisterHotKey(None, number)
