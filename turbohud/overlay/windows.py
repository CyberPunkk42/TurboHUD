"""Windows: system-wide hotkeys and handing the focus back, through ctypes."""

import ctypes
import logging
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

from turbohud.overlay import HOTKEY_LOCK, HOTKEY_PRESETS, HOTKEY_QUIT, HOTKEY_SCREENSHOT

MOD_CONTROL = 0x2
MOD_SHIFT = 0x4
MOD_NOREPEAT = 0x4000
VK_L = 0x4C
VK_Q = 0x51
VK_S = 0x53
VK_ZERO = 0x30  # the keys 1, 2 and 3 follow it
WM_HOTKEY = 0x0312

log = logging.getLogger(__name__)
user32 = ctypes.WinDLL('user32', use_last_error=True)
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]


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

    def __init__(self):
        self.previous = None
        self.filter = None

    def prepare_app(self):
        pass

    def raise_window(self, widget):
        return 'always on top through Qt'

    def take_focus(self):
        self.previous = user32.GetForegroundWindow()

    def give_focus_back(self):
        previous, self.previous = self.previous, None
        if previous:
            user32.SetForegroundWindow(previous)

    def register_hotkeys(self, on_hotkey):
        self.filter = _HotkeyFilter(on_hotkey)
        QCoreApplication.instance().installNativeEventFilter(self.filter)
        modifiers = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
        ok = True
        for key, number in ((VK_L, HOTKEY_LOCK), (VK_Q, HOTKEY_QUIT)):
            if not user32.RegisterHotKey(None, number, modifiers, key):
                log.warning('hotkey %d not available (error %d)', number, ctypes.get_last_error())
                ok = False
        # Not in `ok`: without them, a preset still loads from the panel.
        for number, preset in HOTKEY_PRESETS.items():
            if not user32.RegisterHotKey(None, number, modifiers, VK_ZERO + preset):
                log.warning('hotkey %d not available (error %d)', number, ctypes.get_last_error())
        if not user32.RegisterHotKey(None, HOTKEY_SCREENSHOT, modifiers, VK_S):
            log.warning('hotkey %d not available (error %d)', HOTKEY_SCREENSHOT, ctypes.get_last_error())
        return ok

    def unregister_hotkeys(self):
        for number in (HOTKEY_LOCK, HOTKEY_QUIT, *HOTKEY_PRESETS, HOTKEY_SCREENSHOT):
            user32.UnregisterHotKey(None, number)
