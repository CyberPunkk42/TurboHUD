"""macOS: what Qt cannot do, through ctypes. The window level above TSU's Fullscreen (26
while TSU is active) and on every Space, the app's activation around move mode, and
Carbon's system-wide hotkeys, which need no permission. Proven by the probes in
experiments/."""

import ctypes
import ctypes.util
import logging
from ctypes import c_bool, c_char_p, c_int32, c_long, c_uint32, c_ulong, c_void_p

from turbohud.overlay import HOTKEY_LOCK, HOTKEY_PRESETS, HOTKEY_QUIT

WINDOW_LEVEL = 1000  # NSScreenSaverWindowLevel
NS_ACTIVATION_POLICY_ACCESSORY = 1
NS_APPLICATION_ACTIVATE_IGNORING_OTHER_APPS = 1 << 1
# NSWindowCollectionBehavior: on every Space, allowed next to a full-screen window, and
# left alone by Mission Control and window cycling.
COLLECTION_BEHAVIOR = (1 << 0) | (1 << 4) | (1 << 6) | (1 << 8)
# Carbon hotkeys: virtual key codes (kVK_ANSI_*) and modifier flags (controlKey, shiftKey).
KEY_L = 0x25
KEY_Q = 0x0C
KEYS_PRESET = {1: 0x12, 2: 0x13, 3: 0x14}  # the keys 1, 2 and 3
CARBON_CONTROL = 1 << 12
CARBON_SHIFT = 1 << 9

log = logging.getLogger(__name__)


def fourcc(code):
    """A four-character code such as 'keyb' as the 32-bit number Carbon uses."""
    if len(code) != 4:
        raise ValueError(f'a four-character code needs 4 characters: {code!r}')
    return int.from_bytes(code.encode('ascii'), 'big')


objc = ctypes.CDLL('/usr/lib/libobjc.A.dylib')
carbon = ctypes.CDLL(ctypes.util.find_library('Carbon'))
objc.objc_getClass.restype = c_void_p
objc.objc_getClass.argtypes = [c_char_p]
objc.sel_registerName.restype = c_void_p
objc.sel_registerName.argtypes = [c_char_p]
_msg_send = ctypes.cast(objc.objc_msgSend, c_void_p).value


def send(receiver, selector, *args, restype=c_void_p, argtypes=()):
    """Send an Objective-C message. arm64 needs the exact prototype, so give it."""
    function = ctypes.CFUNCTYPE(restype, c_void_p, c_void_p, *argtypes)(_msg_send)
    return function(receiver, objc.sel_registerName(selector.encode()), *args)


def cls(name):
    return objc.objc_getClass(name.encode())


class EventTypeSpec(ctypes.Structure):
    _fields_ = [('eventClass', c_uint32), ('eventKind', c_uint32)]


class EventHotKeyID(ctypes.Structure):
    _fields_ = [('signature', c_uint32), ('id', c_uint32)]


HANDLER = ctypes.CFUNCTYPE(c_int32, c_void_p, c_void_p, c_void_p)
carbon.GetApplicationEventTarget.restype = c_void_p
carbon.InstallEventHandler.restype = c_int32
carbon.InstallEventHandler.argtypes = [
    c_void_p, HANDLER, c_ulong, ctypes.POINTER(EventTypeSpec), c_void_p, ctypes.POINTER(c_void_p),
]  # fmt: skip
carbon.RegisterEventHotKey.restype = c_int32
carbon.RegisterEventHotKey.argtypes = [
    c_uint32, c_uint32, EventHotKeyID, c_void_p, c_uint32, ctypes.POINTER(c_void_p),
]  # fmt: skip
carbon.UnregisterEventHotKey.argtypes = [c_void_p]
carbon.GetEventParameter.restype = c_int32
carbon.GetEventParameter.argtypes = [c_void_p, c_uint32, c_uint32, c_void_p, c_ulong, c_void_p, c_void_p]


class Native:
    name = 'macOS'
    hides_windows = True  # a hidden section leaves the screen; showing it again stays in place

    def __init__(self):
        self.app = send(cls('NSApplication'), 'sharedApplication')
        self.previous = None
        self.handler = None
        self.hotkeys = []

    def prepare_app(self):
        # An accessory app: no Dock icon, and it may show over another app's full screen.
        # The bundled app says the same in its Info.plist (LSUIElement).
        send(
            self.app,
            'setActivationPolicy:',
            NS_ACTIVATION_POLICY_ACCESSORY,
            restype=c_bool,
            argtypes=[c_long],
        )

    def raise_window(self, widget):
        window = send(c_void_p(int(widget.winId())), 'window')
        send(window, 'setLevel:', WINDOW_LEVEL, restype=None, argtypes=[c_long])
        send(window, 'setCollectionBehavior:', COLLECTION_BEHAVIOR, restype=None, argtypes=[c_ulong])
        send(window, 'setHidesOnDeactivate:', False, restype=None, argtypes=[c_bool])
        return f'window level {WINDOW_LEVEL}, on every Space'

    def take_focus(self):
        # Become the active app, so the game (which hides the pointer) is not.
        workspace = send(cls('NSWorkspace'), 'sharedWorkspace')
        previous = send(workspace, 'frontmostApplication')
        self.previous = send(previous, 'retain') if previous else None
        send(self.app, 'activateIgnoringOtherApps:', True, restype=None, argtypes=[c_bool])

    def give_focus_back(self):
        previous, self.previous = self.previous, None
        if previous:
            options = NS_APPLICATION_ACTIVATE_IGNORING_OTHER_APPS
            send(previous, 'activateWithOptions:', options, restype=c_bool, argtypes=[c_ulong])
            send(previous, 'release', restype=None)

    def register_hotkeys(self, on_hotkey):
        def handle(_call, event, _data):
            try:
                hotkey = EventHotKeyID()
                carbon.GetEventParameter(
                    event,
                    fourcc('----'),
                    fourcc('hkid'),
                    None,
                    ctypes.sizeof(hotkey),
                    None,
                    ctypes.byref(hotkey),
                )
                on_hotkey(hotkey.id)
            except Exception:  # an exception must not cross back into Carbon
                log.exception('hotkey handling failed')
            return 0

        self.handler = HANDLER(handle)  # keep a reference while it is installed
        spec = EventTypeSpec(fourcc('keyb'), 5)  # kEventClassKeyboard, kEventHotKeyPressed
        target = carbon.GetApplicationEventTarget()
        status = carbon.InstallEventHandler(target, self.handler, 1, ctypes.byref(spec), None, None)

        def register(key, number):
            ref = c_void_p()
            hotkey_id = EventHotKeyID(fourcc('TKit'), number)
            result = carbon.RegisterEventHotKey(
                key, CARBON_CONTROL | CARBON_SHIFT, hotkey_id, target, 0, ctypes.byref(ref)
            )
            if result == 0:
                self.hotkeys.append(ref)
            else:
                log.warning('hotkey %d not available (error %d)', number, result)
            return result == 0

        # Both, whatever the first gives. Only these two say whether there are shortcuts:
        # without one, move mode needs another way; a preset still loads from the panel.
        lock, quit_ = register(KEY_L, HOTKEY_LOCK), register(KEY_Q, HOTKEY_QUIT)
        for number, preset in HOTKEY_PRESETS.items():
            register(KEYS_PRESET[preset], number)
        return status == 0 and lock and quit_

    def unregister_hotkeys(self):
        for ref in self.hotkeys:
            carbon.UnregisterEventHotKey(ref)
        self.hotkeys.clear()
