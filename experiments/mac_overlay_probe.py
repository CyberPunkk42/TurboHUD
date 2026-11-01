"""Mac overlay experiment: can a native macOS window show over TSU's Fullscreen mode?

A window from inside CrossOver never shows over TSU when its Fullscreen setting is on
(see experiments/README.md). This probe runs outside the bottle, as a plain Mac program:
a transparent, click-through window with a line of text and a seconds counter, put at a
window level above full-screen windows and allowed on every Space, including a
full-screen one. It calls macOS directly through ctypes (standard library only).

    /opt/homebrew/bin/python3.13 -B experiments/mac_overlay_probe.py

Ctrl+Shift+L switches to move mode (tinted; drag the box, and the overlay becomes the
active app so the pointer shows) and back to locked; locking hands the focus back to the
game and remembers the position. Ctrl+Shift+Q quits. Both are system-wide hotkeys, which
need no permission. Ctrl+C in the terminal also quits.

The probe logs what macOS reports, to the terminal and to .buildtools/mac_overlay_probe.log:
whether macOS counts the overlay as visible, the large windows on screen (TSU's among
them) with their owner and window level, front to back, and the hotkeys it receives.
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Window levels (NSWindowLevel / CGWindowLevel); higher is further in front.
LEVELS = {
    'floating': 3,  # NSFloatingWindowLevel: what an ordinary always-on-top window gets
    'menu': 24,  # NSMainMenuWindowLevel: the menu bar
    'status': 25,  # NSStatusWindowLevel
    'popup': 101,  # NSPopUpMenuWindowLevel
    'screensaver': 1000,  # NSScreenSaverWindowLevel
    'shielding': None,  # CGShieldingWindowLevel(), above a captured display; read at runtime
}
NS_WINDOW_STYLE_BORDERLESS = 0
NS_BACKING_STORE_BUFFERED = 2
NS_ACTIVATION_POLICY_ACCESSORY = 1
NS_WINDOW_OCCLUSION_STATE_VISIBLE = 1 << 1
# NSWindowCollectionBehavior: on every Space, allowed next to a full-screen window, and
# left alone by Mission Control and window cycling.
COLLECTION_BEHAVIOR = (1 << 0) | (1 << 4) | (1 << 6) | (1 << 8)
NS_EVENT_MASK_ANY = 0xFFFFFFFFFFFFFFFF
CG_WINDOW_LIST_ON_SCREEN_ONLY = 1 << 0
CG_WINDOW_LIST_EXCLUDE_DESKTOP = 1 << 4
CF_NUMBER_SINT64 = 4
CF_STRING_ENCODING_UTF8 = 0x08000100
LARGE_SHARE = 0.9  # a window at least this share of the screen's width and height is "large"
TINT = (0.09, 0.22, 0.38, 0.6)  # move mode's background: red, green, blue, opacity
# Carbon hotkeys: virtual key codes (kVK_ANSI_*) and modifier flags (controlKey, shiftKey).
KEY_L = 0x25
KEY_Q = 0x0C
CARBON_CONTROL = 1 << 12
CARBON_SHIFT = 1 << 9
HOTKEY_LOCK = 1
HOTKEY_QUIT = 2
NS_APPLICATION_ACTIVATE_IGNORING_OTHER_APPS = 1 << 1
TOOLS = Path(__file__).resolve().parents[1] / '.buildtools'
LOG_FILE = TOOLS / 'mac_overlay_probe.log'
POSITION_FILE = TOOLS / 'mac_overlay_probe.json'
_log_file = None  # set by main while the probe runs, so the log is also kept on disk


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Show a native Mac test overlay over the game.')
    last = '(default: where the last run left it)'
    parser.add_argument('--x', type=int, help=f'left edge, in points from the screen left {last}')
    parser.add_argument('--y', type=int, help=f'top edge, in points from the screen top {last}')
    parser.add_argument('--width', type=int, default=640)
    parser.add_argument('--height', type=int, default=120)
    parser.add_argument(
        '--level', choices=LEVELS, default='screensaver', help='window level (default: %(default)s)'
    )
    parser.add_argument('--seconds', type=int, default=600, help='quit after this many seconds')
    args = parser.parse_args(argv)
    if args.width <= 0 or args.height <= 0 or args.seconds <= 0:
        parser.error('--width, --height and --seconds must be positive')
    return args


def level_value(name, shielding):
    """The numeric window level for a --level name; `shielding` is CGShieldingWindowLevel()."""
    value = LEVELS[name]
    return shielding + 1 if value is None else value


def cocoa_frame(x, y, width, height, screen_height):
    """(x, y, width, height) with y measured from the screen's bottom, as Cocoa wants it,
    for a box whose top-left corner is (x, y) measured from the screen's top-left.
    The same formula converts a Cocoa frame back."""
    return (x, screen_height - y - height, width, height)


def move_mode_check(front_pid, own_pid, was_front):
    """(was_front, lock) for one look at the active app while in move mode.

    Move mode makes the overlay the active app. Once it has been, another app becoming
    active (the game, usually) ends move mode. Before that, another active app only means
    the switch has not happened yet.
    """
    if front_pid == own_pid:
        return True, False
    return was_front, was_front


def fourcc(code):
    """A four-character code such as 'keyb' as the 32-bit number Carbon uses."""
    if len(code) != 4:
        raise ValueError(f'a four-character code needs 4 characters: {code!r}')
    return int.from_bytes(code.encode('ascii'), 'big')


def load_position(path):
    """The (x, y) saved by an earlier run, or None if there is none or it is unreadable."""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return int(data['x']), int(data['y'])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_position(path, x, y):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'x': x, 'y': y}) + '\n', encoding='utf-8')


def window_summary(windows, screen_width, screen_height, own_pid):
    """Lines describing the overlay and the large windows, front to back.

    `windows` are dicts with owner, pid, layer, width and height, in the front-to-back
    order macOS lists them. The overlay is the window owned by `own_pid`.
    """
    lines = []
    for window in windows:
        ours = window['pid'] == own_pid
        large = (
            window['width'] >= LARGE_SHARE * screen_width and window['height'] >= LARGE_SHARE * screen_height
        )
        if ours or large:
            name = 'this overlay' if ours else window['owner']
            lines.append(f'{name}: level {window["layer"]}, {window["width"]}x{window["height"]}')
    return lines


def overlay_in_front(windows, screen_width, screen_height, own_pid):
    """True if the overlay comes before every large window of another program, False if
    one is in front of it, None if the overlay is not on screen."""
    if not any(window['pid'] == own_pid for window in windows):
        return None
    for window in windows:
        if window['pid'] == own_pid:
            return True
        if window['width'] >= LARGE_SHARE * screen_width and window['height'] >= LARGE_SHARE * screen_height:
            return False


def log(message):
    line = f'[{time.strftime("%H:%M:%S")}] {message}'
    print(line, flush=True)
    if _log_file is not None:
        _log_file.write(line + '\n')
        _log_file.flush()


def run(args, position_file=POSITION_FILE):
    import ctypes
    import ctypes.util
    import os
    from ctypes import c_bool, c_char_p, c_double, c_int32, c_int64, c_long, c_uint32, c_ulong, c_void_p

    objc = ctypes.CDLL('/usr/lib/libobjc.A.dylib')
    ctypes.CDLL(ctypes.util.find_library('AppKit'))  # registers the AppKit classes
    cg = ctypes.CDLL(ctypes.util.find_library('CoreGraphics'))
    cf = ctypes.CDLL(ctypes.util.find_library('CoreFoundation'))
    carbon = ctypes.CDLL(ctypes.util.find_library('Carbon'))

    objc.objc_getClass.restype = c_void_p
    objc.objc_getClass.argtypes = [c_char_p]
    objc.sel_registerName.restype = c_void_p
    objc.sel_registerName.argtypes = [c_char_p]
    msg_send = ctypes.cast(objc.objc_msgSend, c_void_p).value

    class CGRect(ctypes.Structure):
        _fields_ = [('x', c_double), ('y', c_double), ('width', c_double), ('height', c_double)]

    def send(receiver, selector, *args, restype=c_void_p, argtypes=()):
        """Send an Objective-C message. arm64 needs the exact prototype, so give it."""
        function = ctypes.CFUNCTYPE(restype, c_void_p, c_void_p, *argtypes)(msg_send)
        return function(receiver, objc.sel_registerName(selector.encode()), *args)

    def cls(name):
        return objc.objc_getClass(name.encode())

    def nsstring(text):
        return send(cls('NSString'), 'stringWithUTF8String:', text.encode(), argtypes=[c_char_p])

    cg.CGShieldingWindowLevel.restype = ctypes.c_int32
    cg.CGWindowListCopyWindowInfo.restype = c_void_p
    cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    cg.CGRectMakeWithDictionaryRepresentation.restype = c_bool
    cg.CGRectMakeWithDictionaryRepresentation.argtypes = [c_void_p, ctypes.POINTER(CGRect)]
    cf.CFArrayGetCount.restype = c_long
    cf.CFArrayGetCount.argtypes = [c_void_p]
    cf.CFArrayGetValueAtIndex.restype = c_void_p
    cf.CFArrayGetValueAtIndex.argtypes = [c_void_p, c_long]
    cf.CFDictionaryGetValue.restype = c_void_p
    cf.CFDictionaryGetValue.argtypes = [c_void_p, c_void_p]
    cf.CFNumberGetValue.restype = c_bool
    cf.CFNumberGetValue.argtypes = [c_void_p, c_long, c_void_p]
    cf.CFStringGetCString.restype = c_bool
    cf.CFStringGetCString.argtypes = [c_void_p, c_char_p, c_long, ctypes.c_uint32]
    cf.CFRelease.argtypes = [c_void_p]
    keys = {
        name: c_void_p.in_dll(cg, f'kCGWindow{name}').value
        for name in ('OwnerName', 'OwnerPID', 'Layer', 'Bounds')
    }

    def cf_number(ref):
        value = c_int64()
        return (
            value.value if ref and cf.CFNumberGetValue(ref, CF_NUMBER_SINT64, ctypes.byref(value)) else None
        )

    def cf_text(ref):
        buffer = ctypes.create_string_buffer(512)
        if ref and cf.CFStringGetCString(ref, buffer, len(buffer), CF_STRING_ENCODING_UTF8):
            return buffer.value.decode('utf-8', 'replace')
        return '(unknown)'

    def on_screen_windows():
        """The windows on screen, front to back. Window titles are not read."""
        options = CG_WINDOW_LIST_ON_SCREEN_ONLY | CG_WINDOW_LIST_EXCLUDE_DESKTOP
        array = cg.CGWindowListCopyWindowInfo(options, 0)
        if not array:
            return []
        windows = []
        try:
            for index in range(cf.CFArrayGetCount(array)):
                info = cf.CFArrayGetValueAtIndex(array, index)
                bounds = CGRect()
                cg.CGRectMakeWithDictionaryRepresentation(
                    cf.CFDictionaryGetValue(info, keys['Bounds']), ctypes.byref(bounds)
                )
                windows.append({
                    'owner': cf_text(cf.CFDictionaryGetValue(info, keys['OwnerName'])),
                    'pid': cf_number(cf.CFDictionaryGetValue(info, keys['OwnerPID'])),
                    'layer': cf_number(cf.CFDictionaryGetValue(info, keys['Layer'])),
                    'width': int(bounds.width),
                    'height': int(bounds.height),
                })  # fmt: skip
        finally:
            cf.CFRelease(array)
        return windows

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

    def make_label(content, text, color, frame):
        label = send(cls('NSTextField'), 'labelWithString:', nsstring(text), argtypes=[c_void_p])
        send(label, 'setTextColor:', send(cls('NSColor'), color), argtypes=[c_void_p])
        font = send(cls('NSFont'), 'boldSystemFontOfSize:', 16.0, argtypes=[c_double])
        send(label, 'setFont:', font, argtypes=[c_void_p])
        send(label, 'setFrame:', frame, restype=None, argtypes=[CGRect])
        send(content, 'addSubview:', label, restype=None, argtypes=[c_void_p])
        return label

    app = send(cls('NSApplication'), 'sharedApplication')
    send(app, 'setActivationPolicy:', NS_ACTIVATION_POLICY_ACCESSORY, restype=c_bool, argtypes=[c_long])
    send(app, 'finishLaunching', restype=None)

    screen = send(cls('NSScreen'), 'mainScreen')
    screen_frame = send(screen, 'frame', restype=CGRect)
    level = level_value(args.level, cg.CGShieldingWindowLevel())
    saved = load_position(position_file) or (40, 40)
    x = saved[0] if args.x is None else args.x
    y = saved[1] if args.y is None else args.y
    frame = CGRect(*cocoa_frame(x, y, args.width, args.height, screen_frame.height))
    window = send(
        send(cls('NSWindow'), 'alloc'), 'initWithContentRect:styleMask:backing:defer:',
        frame, NS_WINDOW_STYLE_BORDERLESS, NS_BACKING_STORE_BUFFERED, False,
        argtypes=[CGRect, c_ulong, c_ulong, c_bool],
    )  # fmt: skip
    send(window, 'setReleasedWhenClosed:', False, restype=None, argtypes=[c_bool])
    send(window, 'setOpaque:', False, restype=None, argtypes=[c_bool])
    send(window, 'setBackgroundColor:', send(cls('NSColor'), 'clearColor'), restype=None, argtypes=[c_void_p])
    send(window, 'setHasShadow:', False, restype=None, argtypes=[c_bool])
    send(window, 'setIgnoresMouseEvents:', True, restype=None, argtypes=[c_bool])
    send(window, 'setLevel:', level, restype=None, argtypes=[c_long])
    send(window, 'setCollectionBehavior:', COLLECTION_BEHAVIOR, restype=None, argtypes=[c_ulong])

    content = send(window, 'contentView')
    inner = CGRect(12, 0, args.width - 12, args.height - 10)
    # A black copy one point down and right is the shadow that keeps the text readable.
    shadow = make_label(
        content, '', 'blackColor', CGRect(inner.x + 1, inner.y - 1, inner.width, inner.height)
    )
    text = make_label(content, '', 'whiteColor', inner)
    send(window, 'orderFrontRegardless', restype=None)

    # was_front: in move mode, whether this overlay has been the active app yet
    state = {'locked': True, 'quit': False, 'previous_app': None, 'was_front': False}
    clear = send(cls('NSColor'), 'clearColor')
    tint = send(cls('NSColor'), 'colorWithCalibratedRed:green:blue:alpha:', *TINT, argtypes=[c_double] * 4)
    send(tint, 'retain')

    def top_left():
        current = send(window, 'frame', restype=CGRect)
        left, top, _, _ = cocoa_frame(
            current.x, current.y, current.width, current.height, screen_frame.height
        )
        return int(left), int(top)

    def set_locked(locked):
        state['locked'] = locked
        send(window, 'setIgnoresMouseEvents:', locked, restype=None, argtypes=[c_bool])
        send(window, 'setMovableByWindowBackground:', not locked, restype=None, argtypes=[c_bool])
        send(window, 'setBackgroundColor:', clear if locked else tint, restype=None, argtypes=[c_void_p])
        if locked:
            left, top = top_left()
            try:
                save_position(position_file, left, top)
            except OSError as error:
                log(f'could not save the position: {error}')
            previous = state['previous_app']
            state['previous_app'] = None
            if previous:
                options = NS_APPLICATION_ACTIVATE_IGNORING_OTHER_APPS
                send(previous, 'activateWithOptions:', options, restype=c_bool, argtypes=[c_ulong])
                send(previous, 'release', restype=None)
            log(f'locked at x={left} y={top}: click-through, focus handed back')
        else:
            # Become the active app, so the game (which hides the pointer) is not.
            workspace = send(cls('NSWorkspace'), 'sharedWorkspace')
            previous = send(workspace, 'frontmostApplication')
            state['previous_app'] = send(previous, 'retain') if previous else None
            send(app, 'activateIgnoringOtherApps:', True, restype=None, argtypes=[c_bool])
            state['was_front'] = False
            log('move mode: drag the box, then Ctrl+Shift+L locks it')

    def on_hotkey(_call, event, _data):
        try:
            hotkey = EventHotKeyID()
            carbon.GetEventParameter(
                event, fourcc('----'), fourcc('hkid'), None, ctypes.sizeof(hotkey), None, ctypes.byref(hotkey)
            )
            if hotkey.id == HOTKEY_LOCK:
                log('Ctrl+Shift+L pressed')
                set_locked(not state['locked'])
            elif hotkey.id == HOTKEY_QUIT:
                log('Ctrl+Shift+Q pressed')
                state['quit'] = True
        except Exception as error:  # noqa: BLE001 - an exception must not cross back into Carbon
            log(f'hotkey handling failed: {error!r}')
        return 0

    handler = HANDLER(on_hotkey)  # keep a reference while the handler is installed
    spec = EventTypeSpec(fourcc('keyb'), 5)  # kEventClassKeyboard, kEventHotKeyPressed
    target = carbon.GetApplicationEventTarget()
    status = carbon.InstallEventHandler(target, handler, 1, ctypes.byref(spec), None, None)
    hotkeys = []
    for name, key, number in (('Ctrl+Shift+L', KEY_L, HOTKEY_LOCK), ('Ctrl+Shift+Q', KEY_Q, HOTKEY_QUIT)):
        ref = c_void_p()
        hotkey_id = EventHotKeyID(fourcc('TKit'), number)
        result = carbon.RegisterEventHotKey(
            key, CARBON_CONTROL | CARBON_SHIFT, hotkey_id, target, 0, ctypes.byref(ref)
        )
        if status == 0 and result == 0:
            hotkeys.append(ref)
            log(f'{name} registered')
        else:
            log(f'{name} not available (handler {status}, hotkey {result})')

    own_pid = os.getpid()
    log(f'running on macOS {os.uname().release}, Python {sys.version.split()[0]}')
    log(f'screen {int(screen_frame.width)}x{int(screen_frame.height)} points')
    log(f'overlay at x={x} y={y}, {args.width}x{args.height}, level {args.level} ({level})')
    log(
        f'level of the menu bar is {LEVELS["menu"]}; a captured display shields at {cg.CGShieldingWindowLevel()}'
    )

    mode = nsstring('kCFRunLoopDefaultMode')
    started = time.monotonic()
    last_tick = None
    seen = {'visible': None, 'summary': None, 'front': None}
    try:
        while True:
            pool = send(send(cls('NSAutoreleasePool'), 'alloc'), 'init')
            until = send(cls('NSDate'), 'dateWithTimeIntervalSinceNow:', 0.25, argtypes=[c_double])
            event = send(
                app, 'nextEventMatchingMask:untilDate:inMode:dequeue:',
                NS_EVENT_MASK_ANY, until, mode, True,
                argtypes=[ctypes.c_uint64, c_void_p, c_void_p, c_bool],
            )  # fmt: skip
            if event:
                send(app, 'sendEvent:', event, restype=None, argtypes=[c_void_p])
            if not state['locked']:
                front = send(send(cls('NSWorkspace'), 'sharedWorkspace'), 'frontmostApplication')
                front_pid = send(front, 'processIdentifier', restype=c_int32) if front else None
                state['was_front'], leave = move_mode_check(front_pid, own_pid, state['was_front'])
                if leave:
                    # Another app (the game, usually) became active: move mode is over. Locking
                    # activates it again properly, which keeps its mouse handling in step.
                    log('another app became active; locking')
                    set_locked(True)
            elapsed = int(time.monotonic() - started)
            if elapsed != last_tick:
                last_tick = elapsed
                if state['locked']:
                    keys_text = 'Ctrl+Shift+L: move mode. Ctrl+Shift+Q quits.'
                else:
                    keys_text = 'Move mode: drag the box. Ctrl+Shift+L locks.'
                message = nsstring(
                    f'TurboHUD native Mac overlay test (level {args.level}), {elapsed} s\n{keys_text}'
                )
                for label in (shadow, text):
                    send(label, 'setStringValue:', message, restype=None, argtypes=[c_void_p])
                occlusion = send(window, 'occlusionState', restype=c_ulong)
                visible = bool(occlusion & NS_WINDOW_OCCLUSION_STATE_VISIBLE)
                if visible != seen['visible']:
                    seen['visible'] = visible
                    log(
                        'macOS counts the overlay as visible'
                        if visible
                        else 'macOS counts the overlay as hidden'
                    )
                windows = on_screen_windows()
                size = (screen_frame.width, screen_frame.height)
                summary = window_summary(windows, *size, own_pid)
                if summary != seen['summary']:
                    seen['summary'] = summary
                    log('windows, front to back: ' + ('; '.join(summary) or '(none)'))
                front = overlay_in_front(windows, *size, own_pid)
                if front != seen['front']:
                    seen['front'] = front
                    log({True: 'the overlay is in front', False: 'a large window is in front of the overlay'}.get(
                        front, 'the overlay is not on screen'
                    ))  # fmt: skip
            send(pool, 'drain', restype=None)
            if state['quit']:
                break
            if elapsed >= args.seconds:
                log('time is up')
                break
    except KeyboardInterrupt:
        log('Ctrl+C pressed')
    if not state['locked']:
        set_locked(True)  # saves the position and hands the focus back
    else:
        try:
            save_position(position_file, *top_left())
        except OSError as error:
            log(f'could not save the position: {error}')
    for ref in hotkeys:
        carbon.UnregisterEventHotKey(ref)
    send(window, 'orderOut:', None, restype=None, argtypes=[c_void_p])
    log('done')


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if sys.platform != 'darwin':
        print('This probe uses macOS calls; on Windows use overlay_probe.py.')
        return 2
    global _log_file
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open('w', encoding='utf-8') as _log_file:
        try:
            run(args)
        finally:
            _log_file = None
    return 0


if __name__ == '__main__':
    sys.exit(main())
