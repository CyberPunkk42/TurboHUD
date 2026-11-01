"""Qt overlay experiment: can a Qt (PySide6) window do what the two native probes do?

TurboHUD's stack is Python with Qt (docs/STACK.md). This probe checks the overlay window
on that stack: a transparent, click-through, always-on-top window with HUD graphics drawn
by Qt (outlined text, a bar and a small animated map), a move mode, and the shortcuts.
On the Mac it raises Qt's window to a level above TSU's Fullscreen through ctypes, as
mac_overlay_probe.py does. Start it with the runner, which sets up PySide6 first:

    experiments/run_qt_overlay_probe.sh          (macOS, Linux)
    experiments\\run_qt_overlay_probe.cmd         (Windows)

Ctrl+Shift+L switches between locked (click-through, background hidden) and move mode
(tinted; drag the box, resize at the corner, Lock and Close buttons). Move mode ends by
itself when another app, usually the game, becomes active. Ctrl+Shift+Q quits; so does
Ctrl+C in the terminal. The shortcuts are system-wide on Windows and macOS; Linux has no
shortcuts yet, so start with --move there and use the buttons.

The probe logs to the terminal and to .buildtools/qt_overlay_probe.log.
"""

import argparse
import json
import math
import signal
import sys
import time
from pathlib import Path

import mac_overlay_probe as mac

DEFAULT_PLACEMENT = (40, 40, 640, 240)  # x, y, width, height
MIN_WIDTH = 320
MIN_HEIGHT = 160
TINT = (23, 56, 97, 153)  # move mode's background: red, green, blue, opacity (0-255)
FRAME_MS = 50  # redraw interval: 20 frames a second keeps the animation smooth
HOTKEY_LOCK = 1
HOTKEY_QUIT = 2
# Windows: RegisterHotKey modifiers, virtual keys and the message it posts.
MOD_CONTROL = 0x2
MOD_SHIFT = 0x4
MOD_NOREPEAT = 0x4000
VK_L = 0x4C
VK_Q = 0x51
WM_HOTKEY = 0x0312
TOOLS = Path(__file__).resolve().parents[1] / '.buildtools'
LOG_FILE = TOOLS / 'qt_overlay_probe.log'
PLACEMENT_FILE = TOOLS / 'qt_overlay_probe.json'
_log_file = None  # set by main while the probe runs, so the log is also kept on disk


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Show a Qt test overlay over the game.')
    last = '(default: where the last run left it)'
    parser.add_argument('--x', type=int, help=f'left edge, from the screen left {last}')
    parser.add_argument('--y', type=int, help=f'top edge, from the screen top {last}')
    parser.add_argument('--width', type=int, help=f'width {last}')
    parser.add_argument('--height', type=int, help=f'height {last}')
    parser.add_argument(
        '--level', choices=mac.LEVELS, default='screensaver', help='macOS window level (default: %(default)s)'
    )
    parser.add_argument('--move', action='store_true', help='start in move mode instead of locked')
    parser.add_argument('--seconds', type=int, default=600, help='quit after this many seconds')
    args = parser.parse_args(argv)
    for name in ('width', 'height', 'seconds'):
        value = getattr(args, name)
        if value is not None and value <= 0:
            parser.error(f'--{name} must be positive')
    return args


def clamped_size(width, height):
    return max(width, MIN_WIDTH), max(height, MIN_HEIGHT)


def load_placement(path):
    """The (x, y, width, height) saved by an earlier run, or None if there is none or it
    is unreadable. A saved size below the minimum is raised to it."""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        x, y, width, height = (int(data[key]) for key in ('x', 'y', 'width', 'height'))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return (x, y, *clamped_size(width, height))


def save_placement(path, x, y, width, height):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {'x': x, 'y': y, 'width': width, 'height': height}
    path.write_text(json.dumps(data) + '\n', encoding='utf-8')


def placement(args, saved):
    """(x, y, width, height): each value from the command line if given, else from the
    saved placement, else the default."""
    base = saved or DEFAULT_PLACEMENT
    given = (args.x, args.y, args.width, args.height)
    x, y, width, height = (base[i] if value is None else value for i, value in enumerate(given))
    return (x, y, *clamped_size(width, height))


def help_text(locked, shortcuts):
    if not shortcuts:
        if locked:
            return 'No shortcuts here yet: Ctrl+C in the terminal quits.'
        return 'Move mode: drag the box, then Lock or Close.'
    if locked:
        return 'Ctrl+Shift+L: move mode. Ctrl+Shift+Q quits.'
    return 'Move mode: drag the box. Ctrl+Shift+L locks.'


def clock(seconds):
    """'m:ss' for a number of seconds, like a lap time."""
    minutes, seconds = divmod(int(seconds), 60)
    return f'{minutes}:{seconds:02d}'


def map_dot(seconds, period=8.0):
    """Where the demo car is on the demo track, as (x, y) between -1 and 1: once around
    an oval every `period` seconds."""
    angle = 2 * math.pi * (seconds % period) / period
    return math.cos(angle), 0.6 * math.sin(angle)


def log(message):
    line = f'[{time.strftime("%H:%M:%S")}] {message}'
    print(line, flush=True)
    if _log_file is not None:
        _log_file.write(line + '\n')
        _log_file.flush()


def mac_native(level_name):
    """What Qt cannot do on the Mac: the window level, the app's activation, and Carbon's
    system-wide hotkeys. Uses the same calls as mac_overlay_probe.py."""
    import ctypes
    import ctypes.util
    from ctypes import c_bool, c_char_p, c_int32, c_long, c_uint32, c_ulong, c_void_p

    objc = ctypes.CDLL('/usr/lib/libobjc.A.dylib')
    cg = ctypes.CDLL(ctypes.util.find_library('CoreGraphics'))
    carbon = ctypes.CDLL(ctypes.util.find_library('Carbon'))
    objc.objc_getClass.restype = c_void_p
    objc.objc_getClass.argtypes = [c_char_p]
    objc.sel_registerName.restype = c_void_p
    objc.sel_registerName.argtypes = [c_char_p]
    msg_send = ctypes.cast(objc.objc_msgSend, c_void_p).value
    cg.CGShieldingWindowLevel.restype = c_int32

    def send(receiver, selector, *args, restype=c_void_p, argtypes=()):
        function = ctypes.CFUNCTYPE(restype, c_void_p, c_void_p, *argtypes)(msg_send)
        return function(receiver, objc.sel_registerName(selector.encode()), *args)

    def cls(name):
        return objc.objc_getClass(name.encode())

    class EventTypeSpec(ctypes.Structure):
        _fields_ = [('eventClass', c_uint32), ('eventKind', c_uint32)]

    class EventHotKeyID(ctypes.Structure):
        _fields_ = [('signature', c_uint32), ('id', c_uint32)]

    handler_type = ctypes.CFUNCTYPE(c_int32, c_void_p, c_void_p, c_void_p)
    carbon.GetApplicationEventTarget.restype = c_void_p
    carbon.InstallEventHandler.restype = c_int32
    carbon.InstallEventHandler.argtypes = [
        c_void_p, handler_type, c_ulong, ctypes.POINTER(EventTypeSpec), c_void_p, ctypes.POINTER(c_void_p),
    ]  # fmt: skip
    carbon.RegisterEventHotKey.restype = c_int32
    carbon.RegisterEventHotKey.argtypes = [
        c_uint32, c_uint32, EventHotKeyID, c_void_p, c_uint32, ctypes.POINTER(c_void_p),
    ]  # fmt: skip
    carbon.UnregisterEventHotKey.argtypes = [c_void_p]
    carbon.GetEventParameter.restype = c_int32
    carbon.GetEventParameter.argtypes = [c_void_p, c_uint32, c_uint32, c_void_p, c_ulong, c_void_p, c_void_p]

    level = mac.level_value(level_name, cg.CGShieldingWindowLevel())
    app = send(cls('NSApplication'), 'sharedApplication')
    state = {'previous': None, 'handler': None, 'hotkeys': []}

    class Native:
        name = 'macOS'

        @staticmethod
        def prepare_app():
            # An accessory app: no Dock icon, and it may show over another app's full screen.
            send(
                app,
                'setActivationPolicy:',
                mac.NS_ACTIVATION_POLICY_ACCESSORY,
                restype=c_bool,
                argtypes=[c_long],
            )

        @staticmethod
        def raise_window(widget):
            window = send(c_void_p(int(widget.winId())), 'window')
            send(window, 'setLevel:', level, restype=None, argtypes=[c_long])
            send(window, 'setCollectionBehavior:', mac.COLLECTION_BEHAVIOR, restype=None, argtypes=[c_ulong])
            send(window, 'setHidesOnDeactivate:', False, restype=None, argtypes=[c_bool])
            return f'window level {level_name} ({level})'

        @staticmethod
        def take_focus():
            # Become the active app, so the game (which hides the pointer) is not.
            workspace = send(cls('NSWorkspace'), 'sharedWorkspace')
            previous = send(workspace, 'frontmostApplication')
            state['previous'] = send(previous, 'retain') if previous else None
            send(app, 'activateIgnoringOtherApps:', True, restype=None, argtypes=[c_bool])

        @staticmethod
        def give_focus_back():
            previous, state['previous'] = state['previous'], None
            if previous:
                options = mac.NS_APPLICATION_ACTIVATE_IGNORING_OTHER_APPS
                send(previous, 'activateWithOptions:', options, restype=c_bool, argtypes=[c_ulong])
                send(previous, 'release', restype=None)

        @staticmethod
        def register_hotkeys(on_hotkey):
            def handle(_call, event, _data):
                try:
                    hotkey = EventHotKeyID()
                    carbon.GetEventParameter(
                        event, mac.fourcc('----'), mac.fourcc('hkid'), None,
                        ctypes.sizeof(hotkey), None, ctypes.byref(hotkey),
                    )  # fmt: skip
                    on_hotkey(hotkey.id)
                except Exception as error:  # noqa: BLE001 - an exception must not cross back into Carbon
                    log(f'hotkey handling failed: {error!r}')
                return 0

            state['handler'] = handler_type(handle)  # keep a reference while it is installed
            spec = EventTypeSpec(mac.fourcc('keyb'), 5)  # kEventClassKeyboard, kEventHotKeyPressed
            target = carbon.GetApplicationEventTarget()
            status = carbon.InstallEventHandler(target, state['handler'], 1, ctypes.byref(spec), None, None)
            ok = status == 0
            for key, number in ((mac.KEY_L, HOTKEY_LOCK), (mac.KEY_Q, HOTKEY_QUIT)):
                ref = c_void_p()
                result = carbon.RegisterEventHotKey(
                    key, mac.CARBON_CONTROL | mac.CARBON_SHIFT, EventHotKeyID(mac.fourcc('TKit'), number),
                    target, 0, ctypes.byref(ref),
                )  # fmt: skip
                if result == 0:
                    state['hotkeys'].append(ref)
                ok = ok and result == 0
            return ok

        @staticmethod
        def unregister_hotkeys():
            for ref in state['hotkeys']:
                carbon.UnregisterEventHotKey(ref)
            state['hotkeys'].clear()

    return Native


def windows_native():
    """What Qt cannot do on Windows: system-wide hotkeys, and handing the focus back."""
    import ctypes
    from ctypes import wintypes

    from PySide6.QtCore import QAbstractNativeEventFilter

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    state = {'previous': None, 'filter': None}

    class HotkeyFilter(QAbstractNativeEventFilter):
        def __init__(self, on_hotkey):
            super().__init__()
            self.on_hotkey = on_hotkey

        def nativeEventFilter(self, event_type, message):
            # Hotkeys registered without a window arrive as thread messages, which Qt's
            # event loop passes here as a pointer to the MSG.
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                self.on_hotkey(int(msg.wParam))
                return True, 0
            return False, 0

    class Native:
        name = 'Windows'

        @staticmethod
        def prepare_app():
            pass

        @staticmethod
        def raise_window(widget):
            return 'always on top through Qt'

        @staticmethod
        def take_focus():
            state['previous'] = user32.GetForegroundWindow()

        @staticmethod
        def give_focus_back():
            previous, state['previous'] = state['previous'], None
            if previous:
                user32.SetForegroundWindow(previous)

        @staticmethod
        def register_hotkeys(on_hotkey):
            from PySide6.QtCore import QCoreApplication

            state['filter'] = HotkeyFilter(on_hotkey)
            QCoreApplication.instance().installNativeEventFilter(state['filter'])
            modifiers = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
            results = [user32.RegisterHotKey(None, number, modifiers, key) for key, number in (
                (VK_L, HOTKEY_LOCK), (VK_Q, HOTKEY_QUIT),
            )]  # fmt: skip
            return all(results)

        @staticmethod
        def unregister_hotkeys():
            for number in (HOTKEY_LOCK, HOTKEY_QUIT):
                user32.UnregisterHotKey(None, number)

    return Native


class OtherNative:
    """Linux and anything else: what Qt does alone, without shortcuts yet."""

    name = sys.platform

    @staticmethod
    def prepare_app():
        pass

    @staticmethod
    def raise_window(widget):
        return 'always on top through Qt'

    @staticmethod
    def take_focus():
        pass

    @staticmethod
    def give_focus_back():
        pass

    @staticmethod
    def register_hotkeys(on_hotkey):
        return False

    @staticmethod
    def unregister_hotkeys():
        pass


def run(args, placement_file=PLACEMENT_FILE):
    import PySide6
    from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QSizeGrip, QVBoxLayout, QWidget

    app = QApplication([sys.argv[0]])
    if sys.platform == 'darwin':
        native = mac_native(args.level)
    elif sys.platform == 'win32':
        native = windows_native()
    else:
        native = OtherNative
    native.prepare_app()

    def outlined_text(painter, point, text, size, color):
        """Text with a dark outline, readable over any part of the game."""
        font = QFont()
        font.setPixelSize(size)
        font.setBold(True)
        path = QPainterPath()
        path.addText(point, font, text)
        painter.strokePath(path, QPen(QColor(0, 0, 0, 200), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.fillPath(path, color)

    class Overlay(QWidget):
        def __init__(self):
            flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            if sys.platform != 'darwin':
                flags |= Qt.Tool  # no taskbar button; on the Mac a tool window hides when inactive
            super().__init__(None, flags)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating)
            self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
            self.locked = True
            self.was_active = False  # in move mode: whether this app has been active yet
            self.shortcuts = False
            self.started = time.monotonic()
            lock = QPushButton('Lock')
            close = QPushButton('Close')
            lock.clicked.connect(lambda: self.set_locked(True))
            close.clicked.connect(app.quit)
            self.grip = QSizeGrip(self)
            row = QHBoxLayout()
            row.addWidget(lock)
            row.addWidget(close)
            row.addStretch()
            row.addWidget(self.grip, 0, Qt.AlignBottom | Qt.AlignRight)
            column = QVBoxLayout(self)
            column.addStretch()
            column.addLayout(row)
            self.controls = (lock, close, self.grip)

        def elapsed(self):
            return time.monotonic() - self.started

        def set_locked(self, locked):
            if locked == self.locked:
                return
            self.locked = locked
            self.setWindowFlag(Qt.WindowTransparentForInput, locked)
            for control in self.controls:
                control.setVisible(not locked)
            self.setCursor(Qt.ArrowCursor if locked else Qt.OpenHandCursor)
            self.show()  # changing a window flag hides the window
            log(f'native: {native.raise_window(self)}')
            if locked:
                self.save()
                native.give_focus_back()
                log(f'locked at x={self.x()} y={self.y()}, {self.width()}x{self.height()}: click-through')
            else:
                self.was_active = False
                native.take_focus()
                self.activateWindow()
                self.raise_()
                log('move mode: drag the box, resize at the corner, then lock')
            self.update()

        def save(self):
            try:
                save_placement(placement_file, self.x(), self.y(), self.width(), self.height())
            except OSError as error:
                log(f'could not save the placement: {error}')

        def mousePressEvent(self, event):
            if not self.locked and event.button() == Qt.LeftButton:
                self.windowHandle().startSystemMove()

        def paintEvent(self, _event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            box = QRectF(self.rect()).adjusted(1, 1, -1, -1)
            if not self.locked:
                painter.setPen(QPen(QColor(120, 170, 230), 2))
                painter.setBrush(QColor(*TINT))
                painter.drawRoundedRect(box, 10, 10)
            seconds = self.elapsed()
            white = QColor(255, 255, 255)
            outlined_text(painter, QPointF(16, 34), f'TurboHUD Qt overlay test ({native.name})', 20, white)
            outlined_text(painter, QPointF(16, 84), clock(seconds), 44, QColor(255, 214, 90))
            outlined_text(painter, QPointF(16, 112), help_text(self.locked, self.shortcuts), 14, white)

            # A fuel-style bar that empties over a minute, with a gradient.
            bar = QRectF(150, 52, max(self.width() - 330, 80), 22)
            share = 1 - (seconds % 60) / 60
            painter.setPen(QPen(QColor(0, 0, 0, 200), 2))
            painter.setBrush(QColor(0, 0, 0, 90))
            painter.drawRoundedRect(bar, 6, 6)
            gradient = QLinearGradient(bar.topLeft(), bar.topRight())
            gradient.setColorAt(0, QColor(230, 70, 60))
            gradient.setColorAt(1, QColor(90, 220, 120))
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(QRectF(bar.x(), bar.y(), bar.width() * share, bar.height()), 6, 6)

            # A small map: an oval track and a dot going round.
            size = 120
            track = QRectF(self.width() - size - 30, 20, size, size * 0.6)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(0, 0, 0, 200), 7))
            painter.drawEllipse(track)
            painter.setPen(QPen(QColor(220, 220, 220), 3))
            painter.drawEllipse(track)
            dx, dy = map_dot(seconds)
            centre = track.center()
            dot = QPointF(centre.x() + dx * track.width() / 2, centre.y() + dy * track.width() / 2)
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.setBrush(QColor(255, 90, 60))
            painter.drawEllipse(dot, 6, 6)
            painter.end()

    overlay = Overlay()
    x, y, width, height = placement(args, load_placement(placement_file))
    overlay.setGeometry(x, y, width, height)
    overlay.setWindowFlag(Qt.WindowTransparentForInput, True)
    for control in overlay.controls:
        control.setVisible(False)
    overlay.show()
    log(f'running on {native.name}, Python {sys.version.split()[0]}, PySide6 {PySide6.__version__}')
    log(f'Qt platform: {QGuiApplication.platformName()}')
    log(f'overlay at x={x} y={y}, {width}x{height}')
    log(f'native: {native.raise_window(overlay)}')

    def on_hotkey(number):
        # Leave the system's callback first, then act.
        if number == HOTKEY_LOCK:
            log('Ctrl+Shift+L pressed')
            QTimer.singleShot(0, lambda: overlay.set_locked(not overlay.locked))
        elif number == HOTKEY_QUIT:
            log('Ctrl+Shift+Q pressed')
            QTimer.singleShot(0, app.quit)

    overlay.shortcuts = native.register_hotkeys(on_hotkey)
    log('Ctrl+Shift+L and Ctrl+Shift+Q registered' if overlay.shortcuts else 'no system-wide shortcuts')

    def on_state(state):
        active = state == Qt.ApplicationActive
        log('this app is active' if active else 'another app is active')
        if overlay.locked:
            return
        if active:
            overlay.was_active = True
        elif overlay.was_active:
            # Another app (the game, usually) became active: move mode is over.
            log('locking, since another app became active')
            overlay.set_locked(True)

    app.applicationStateChanged.connect(on_state)

    def tick():
        overlay.update()
        if overlay.elapsed() >= args.seconds:
            log('time is up')
            app.quit()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(FRAME_MS)  # also lets Python see Ctrl+C between frames
    signal.signal(signal.SIGINT, lambda *_: (log('Ctrl+C pressed'), app.quit()))
    if args.move:
        overlay.set_locked(False)
    app.exec()
    if not overlay.locked:
        overlay.set_locked(True)  # saves the placement and hands the focus back
    else:
        overlay.save()
    native.unregister_hotkeys()
    log('done')


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        import PySide6  # noqa: F401 - only checks that Qt is there
    except ImportError:
        print('PySide6 is missing. Start the probe with run_qt_overlay_probe.sh (macOS, Linux)')
        print('or run_qt_overlay_probe.cmd (Windows), which set it up first.')
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
