"""Overlay experiment: can a see-through, click-through, always-on-top window sit over TSU?

Opens a small semi-transparent box with a seconds counter, using plain Win32 calls
(ctypes, standard library only). Run it while TSU is running in a window or borderless:
- on Windows:              py -3 -B experiments/overlay_probe.py
- on the Mac (CrossOver):  see experiments/README.md; it must run in TSU's bottle.

The box starts in move mode: drag it into place with the mouse, drag its bottom-right
corner to resize it, then press its Lock button. Locked, it is click-through, and
Ctrl+Shift+L unlocks it again. Close (or Ctrl+Shift+Q) quits. The keys avoid Alt, which
a Mac keyboard does not have. Position and size are remembered for the next run.

Then check by eye: is the box visible over the game, does the game show through it, does
it stay on top when the game has focus, and do clicks on the locked box reach the game?

The probe also prints what Windows (or Wine) reports: the window styles it kept, whether
a hit test at the box's centre finds the box, clicks that reached the locked box, whether
the keyboard shortcuts arrive, every change of the focused window (its size and whether
it keeps itself on top), whether the mouse pointer is shown or hidden, and each time the
game came in front of the overlay (the probe then puts the overlay back on top). The log
is also written to .buildtools/overlay_probe.log.
"""

import argparse
import json
import sys
import time
from pathlib import Path

WS_POPUP = 0x80000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
GWL_EXSTYLE = -20
LWA_COLORKEY = 0x1
LWA_ALPHA = 0x2
# Locked, the box's background is painted in this colour and the system leaves it out, so
# only the text shows. Nearly black, so the edges of smoothed text blend into a dark rim.
KEY_COLOR = 0x00010101  # COLORREF is 0x00BBGGRR
SW_SHOWNOACTIVATE = 4
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
WM_DESTROY = 0x0002
WM_PAINT = 0x000F
WM_SETCURSOR = 0x0020
WM_TIMER = 0x0113
WM_HOTKEY = 0x0312
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_CAPTURECHANGED = 0x0215
HTCLIENT = 1
IDC_ARROW = 32512
IDC_SIZENWSE = 32642
IDC_SIZEALL = 32646
IDC_HAND = 32649
CURSOR_SHOWING = 0x1
MOD_CONTROL = 0x2
MOD_SHIFT = 0x4
MOD_NOREPEAT = 0x4000
VK_L = 0x4C
VK_Q = 0x51
HOTKEY_LOCK = 1
HOTKEY_QUIT = 2
TRANSPARENT_BK = 1
DT_CENTER = 0x0001
DT_VCENTER = 0x0004
DT_LEFT_WORDBREAK = 0x0010
DT_SINGLELINE = 0x0020
CLASS_NAME = 'TurboKitOverlayProbe'
DEFAULT_PLACEMENT = (40, 40, 640, 240)  # x, y, width, height
MIN_WIDTH = 320
MIN_HEIGHT = 120
BUTTON_WIDTH = 80
BUTTON_HEIGHT = 28
BUTTON_MARGIN = 10
GRIP_SIZE = 20
PLACEMENT_FILE = Path(__file__).resolve().parents[1] / '.buildtools' / 'overlay_probe.json'
LOG_FILE = PLACEMENT_FILE.with_name('overlay_probe.log')
GW_HWNDPREV = 3
HWND_TOPMOST = -1
_log_file = None  # set by main while the probe runs, so the log is also kept on disk


def ex_style(click_through):
    """Extended window style for the overlay: layered, on top, kept out of the taskbar."""
    style = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    if click_through:
        style |= WS_EX_TRANSPARENT
    return style


def style_report(requested, actual):
    """Names of the requested extended styles that the window did not keep."""
    names = {
        WS_EX_LAYERED: 'layered',
        WS_EX_TOPMOST: 'topmost',
        WS_EX_TRANSPARENT: 'click-through',
        WS_EX_TOOLWINDOW: 'tool window',
        WS_EX_NOACTIVATE: 'no-activate',
    }
    return [name for flag, name in names.items() if requested & flag and not actual & flag]


def layered_attributes(locked, alpha):
    """(colour key, opacity, flags) for SetLayeredWindowAttributes: locked, the background
    vanishes and the text is solid; in move mode the whole box is tinted at `alpha`."""
    if locked:
        return KEY_COLOR, 255, LWA_COLORKEY
    return 0, alpha, LWA_ALPHA


def part_rects(width, height):
    """The move-mode controls as {name: (left, top, right, bottom)}: the Lock and Close
    buttons at the bottom left and the resize grip in the bottom-right corner."""
    top = height - BUTTON_MARGIN - BUTTON_HEIGHT
    lock_left = BUTTON_MARGIN
    close_left = lock_left + BUTTON_WIDTH + BUTTON_MARGIN
    return {
        'lock': (lock_left, top, lock_left + BUTTON_WIDTH, top + BUTTON_HEIGHT),
        'close': (close_left, top, close_left + BUTTON_WIDTH, top + BUTTON_HEIGHT),
        'resize': (width - GRIP_SIZE, height - GRIP_SIZE, width, height),
    }


def part_at(x, y, width, height):
    """Name of the control under the point (client pixels), or None for the rest of the box."""
    for name, (left, top, right, bottom) in part_rects(width, height).items():
        if left <= x < right and top <= y < bottom:
            return name
    return None


def resized(width, height, dx, dy):
    """The size after dragging the grip by (dx, dy), never below the minimum."""
    return max(MIN_WIDTH, width + dx), max(MIN_HEIGHT, height + dy)


def client_point(lparam):
    """The (x, y) packed into a mouse message's lparam; both are signed 16-bit values."""
    x = lparam & 0xFFFF
    y = (lparam >> 16) & 0xFFFF
    return (x - 0x10000 if x & 0x8000 else x, y - 0x10000 if y & 0x8000 else y)


def load_placement(path):
    """The (x, y, width, height) saved by an earlier run, or None if there is none or it
    is unreadable. A saved size below the minimum is raised to it."""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        x, y, width, height = (int(data[key]) for key in ('x', 'y', 'width', 'height'))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return (x, y, *resized(width, height, 0, 0))


def save_placement(path, x, y, width, height):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {'x': x, 'y': y, 'width': width, 'height': height}
    path.write_text(json.dumps(data) + '\n', encoding='utf-8')


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Show a test overlay box over the game.')
    last = '(default: as left by the last run)'
    parser.add_argument('--x', type=int, help=f'left edge on screen, in pixels {last}')
    parser.add_argument('--y', type=int, help=f'top edge on screen, in pixels {last}')
    parser.add_argument('--width', type=int, help=f'in pixels {last}')
    parser.add_argument('--height', type=int, help=f'in pixels {last}')
    parser.add_argument(
        '--alpha', type=int, default=170, help='opacity in move mode, 0 (invisible) to 255 (solid)'
    )
    parser.add_argument('--seconds', type=int, default=600, help='quit after this many seconds')
    parser.add_argument('--locked', action='store_true', help='start locked (click-through)')
    args = parser.parse_args(argv)
    if not 0 <= args.alpha <= 255:
        parser.error('--alpha must be between 0 and 255')
    if args.seconds <= 0:
        parser.error('--seconds must be positive')
    if (args.width is not None and args.width < MIN_WIDTH) or (
        args.height is not None and args.height < MIN_HEIGHT
    ):
        parser.error(f'the box needs at least {MIN_WIDTH}x{MIN_HEIGHT} pixels for its text and buttons')
    return args


def log(message):
    line = f'[{time.strftime("%H:%M:%S")}] {message}'
    print(line, flush=True)
    if _log_file is not None:
        _log_file.write(line + '\n')
        _log_file.flush()


def run(args, placement_file=PLACEMENT_FILE):
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ('style', wintypes.UINT),
            ('lpfnWndProc', WNDPROC),
            ('cbClsExtra', ctypes.c_int),
            ('cbWndExtra', ctypes.c_int),
            ('hInstance', wintypes.HINSTANCE),
            ('hIcon', wintypes.HICON),
            ('hCursor', wintypes.HANDLE),
            ('hbrBackground', wintypes.HBRUSH),
            ('lpszMenuName', wintypes.LPCWSTR),
            ('lpszClassName', wintypes.LPCWSTR),
        ]

    class PAINTSTRUCT(ctypes.Structure):
        _fields_ = [
            ('hdc', wintypes.HDC),
            ('fErase', wintypes.BOOL),
            ('rcPaint', wintypes.RECT),
            ('fRestore', wintypes.BOOL),
            ('fIncUpdate', wintypes.BOOL),
            ('rgbReserved', ctypes.c_byte * 32),
        ]

    class CURSORINFO(ctypes.Structure):
        _fields_ = [
            ('cbSize', wintypes.DWORD),
            ('flags', wintypes.DWORD),
            ('hCursor', wintypes.HANDLE),
            ('ptScreenPos', wintypes.POINT),
        ]

    user32.DefWindowProcW.restype = LRESULT
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]  # fmt: skip
    user32.GetWindowLongW.restype = wintypes.LONG
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongW.restype = wintypes.LONG
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]  # fmt: skip
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.SetCapture.restype = wintypes.HWND
    user32.SetCapture.argtypes = [wintypes.HWND]
    user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.LoadCursorW.restype = wintypes.HANDLE
    user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPVOID]
    user32.SetCursor.restype = wintypes.HANDLE
    user32.SetCursor.argtypes = [wintypes.HANDLE]
    user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
    user32.SetLayeredWindowAttributes.argtypes = [
        wintypes.HWND,
        wintypes.COLORREF,
        wintypes.BYTE,
        wintypes.DWORD,
    ]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.BeginPaint.restype = wintypes.HDC
    user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
    user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
    user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.HBRUSH]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.DrawTextW.argtypes = [
        wintypes.HDC,
        wintypes.LPCWSTR,
        ctypes.c_int,
        ctypes.POINTER(wintypes.RECT),
        wintypes.UINT,
    ]
    user32.InvalidateRect.argtypes = [wintypes.HWND, wintypes.LPVOID, wintypes.BOOL]
    user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, wintypes.LPVOID]
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
    gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
    gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
    gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.COLORREF]
    gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

    def window_title(hwnd):
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        return buffer.value or '(no title)'

    def describe_window(hwnd):
        if not hwnd:
            return '(none)'
        rect = window_rect(hwnd)
        on_top = user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST
        size = f'{rect.right - rect.left}x{rect.bottom - rect.top}'
        return f'{window_title(hwnd)} (x={rect.left} y={rect.top}, {size}, always on top: {"yes" if on_top else "no"})'

    def is_above(upper, lower):
        """Whether `upper` comes before `lower` in the system's front-to-back window order."""
        window = user32.GetWindow(lower, GW_HWNDPREV)
        for _ in range(10000):  # guards against a list that changes while it is walked
            if not window:
                return False
            if window == upper:
                return True
            window = user32.GetWindow(window, GW_HWNDPREV)
        return False

    def window_rect(hwnd):
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return rect

    def cursor_pos():
        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        return point

    def pointer_shown():
        info = CURSORINFO(cbSize=ctypes.sizeof(CURSORINFO))
        if not user32.GetCursorInfo(ctypes.byref(info)):
            return None
        return bool(info.flags & CURSOR_SHOWING)

    def remember_placement(hwnd):
        rect = window_rect(hwnd)
        try:
            save_placement(
                placement_file, rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
            )
        except OSError as error:
            log(f'could not save the position and size: {error}')

    def placement_text(hwnd):
        rect = window_rect(hwnd)
        return f'x={rect.left} y={rect.top}, {rect.right - rect.left}x{rect.bottom - rect.top}'

    def report_styles(hwnd, requested):
        actual = user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
        missing = style_report(requested, actual)
        log('window kept all requested styles' if not missing else f'styles dropped: {", ".join(missing)}')
        rect = window_rect(hwnd)
        centre = wintypes.POINT((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
        hit = user32.WindowFromPoint(centre)
        log(f'hit test at the centre finds {"the overlay" if hit == hwnd else window_title(hit)}')

    def apply_layering(hwnd, locked):
        if not user32.SetLayeredWindowAttributes(hwnd, *layered_attributes(locked, args.alpha)):
            log(f'SetLayeredWindowAttributes failed: {ctypes.WinError(ctypes.get_last_error())}')

    def set_locked(hwnd, locked):
        state['locked'] = locked
        state['drag'] = None
        style = ex_style(click_through=locked)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ctypes.c_long(style).value)
        apply_layering(hwnd, locked)
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, flags)
        if locked:
            remember_placement(hwnd)
            log(f'locked at {placement_text(hwnd)}: click-through now; Ctrl+Shift+L unlocks')
        else:
            log('unlocked: move mode, drag the box or its corner and press Lock')
        report_styles(hwnd, style)
        user32.InvalidateRect(hwnd, None, True)

    key_brush = gdi32.CreateSolidBrush(KEY_COLOR)
    move_brush = gdi32.CreateSolidBrush(0x00603818)  # blue tint, shown only in move mode
    button_brush = gdi32.CreateSolidBrush(0x00A06830)
    cursors = {
        name: user32.LoadCursorW(None, ctypes.c_void_p(cursor_id))
        for name, cursor_id in (
            ('lock', IDC_HAND),
            ('close', IDC_HAND),
            ('resize', IDC_SIZENWSE),
            (None, IDC_SIZEALL),
        )
    }
    started = time.monotonic()
    # drag is None, or ('move' | 'resize', cursor x, cursor y, window rect) from the press
    state = {
        'foreground': None,
        'pointer': None,
        'visible': None,
        'behind': False,
        'raises': 0,
        'clicks': 0,
        'locked': args.locked,
        'drag': None,
    }

    def paint(hwnd):
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        width, height = rect.right, rect.bottom
        user32.FillRect(hdc, ctypes.byref(rect), key_brush if state['locked'] else move_brush)
        gdi32.SetBkMode(hdc, TRANSPARENT_BK)
        rect.left += 12
        rect.top += 10
        elapsed = int(time.monotonic() - started)
        if state['locked']:
            text = (
                f'TurboKit overlay test (locked, click-through)\n'
                f'Running for {elapsed} s, clicks received: {state["clicks"]}\n'
                f'Ctrl+Shift+L unlocks, Ctrl+Shift+Q quits'
            )
        else:
            text = (
                f'TurboKit overlay test (move mode, {width}x{height})\n'
                f'Drag the box to move it, drag the corner to resize it, then press Lock.\n'
                f'Running for {elapsed} s (quits after {args.seconds} s)'
            )
        if state['locked']:
            # A black shadow one pixel down and right keeps the text readable on bright track.
            shadow = wintypes.RECT(rect.left + 1, rect.top + 1, rect.right + 1, rect.bottom + 1)
            gdi32.SetTextColor(hdc, 0x00000000)
            user32.DrawTextW(hdc, text, -1, ctypes.byref(shadow), DT_LEFT_WORDBREAK)
        gdi32.SetTextColor(hdc, 0x00FFFFFF)
        user32.DrawTextW(hdc, text, -1, ctypes.byref(rect), DT_LEFT_WORDBREAK)
        if not state['locked']:
            for name, (left, top, right, bottom) in part_rects(width, height).items():
                part = wintypes.RECT(left, top, right, bottom)
                user32.FillRect(hdc, ctypes.byref(part), button_brush)
                if name != 'resize':
                    label = name.capitalize()
                    user32.DrawTextW(
                        hdc, label, -1, ctypes.byref(part), DT_CENTER | DT_VCENTER | DT_SINGLELINE
                    )
        user32.EndPaint(hwnd, ctypes.byref(ps))

    def wnd_proc(hwnd, msg, wparam, lparam):
        if msg == WM_PAINT:
            paint(hwnd)
            return 0
        if msg == WM_TIMER:
            foreground = user32.GetForegroundWindow()
            if foreground != state['foreground']:
                state['foreground'] = foreground
                log(f'focused window: {describe_window(foreground)}')
            visible = bool(user32.IsWindowVisible(hwnd))
            if visible != state['visible']:
                state['visible'] = visible
                log('overlay is visible' if visible else 'overlay was hidden')
            behind = bool(foreground) and foreground != hwnd and is_above(foreground, hwnd)
            if behind:
                if not state['behind']:
                    log(f'{describe_window(foreground)} is in front of the overlay; putting it back on top')
                state['raises'] += 1
                flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                user32.SetWindowPos(hwnd, wintypes.HWND(HWND_TOPMOST), 0, 0, 0, 0, flags)
            elif state['behind']:
                log('the overlay is in front again')
            state['behind'] = behind
            shown = pointer_shown()
            if shown != state['pointer']:
                state['pointer'] = shown
                log(
                    {True: 'mouse pointer shown', False: 'mouse pointer hidden'}.get(
                        shown, 'pointer state unknown'
                    )
                )
            if time.monotonic() - started >= args.seconds:
                log('time is up')
                user32.DestroyWindow(hwnd)
            else:
                user32.InvalidateRect(hwnd, None, True)
            return 0
        if msg == WM_SETCURSOR and not state['locked'] and lparam & 0xFFFF == HTCLIENT:
            # The class has no cursor of its own: without this the pointer keeps whatever
            # shape the game last gave it, which may be none at all.
            point = cursor_pos()
            user32.ScreenToClient(hwnd, ctypes.byref(point))
            rect = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            user32.SetCursor(cursors[part_at(point.x, point.y, rect.right, rect.bottom)])
            return 1
        if msg == WM_LBUTTONDOWN and not state['locked']:
            rect = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            x, y = client_point(lparam)
            part = part_at(x, y, rect.right, rect.bottom)
            if part == 'lock':
                set_locked(hwnd, True)
            elif part == 'close':
                log('Close pressed')
                user32.DestroyWindow(hwnd)
            else:
                cursor = cursor_pos()
                state['drag'] = ('resize' if part else 'move', cursor.x, cursor.y, window_rect(hwnd))
                user32.SetCapture(hwnd)
            return 0
        if msg == WM_MOUSEMOVE and state['drag']:
            kind, start_x, start_y, start = state['drag']
            cursor = cursor_pos()
            dx, dy = cursor.x - start_x, cursor.y - start_y
            if kind == 'move':
                flags = SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
                user32.SetWindowPos(hwnd, None, start.left + dx, start.top + dy, 0, 0, flags)
            else:
                width, height = resized(start.right - start.left, start.bottom - start.top, dx, dy)
                flags = SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE
                user32.SetWindowPos(hwnd, None, 0, 0, width, height, flags)
                user32.InvalidateRect(hwnd, None, True)
            return 0
        if msg == WM_LBUTTONUP and state['drag']:
            kind = state['drag'][0]
            state['drag'] = None
            user32.ReleaseCapture()
            log(f'{"moved" if kind == "move" else "resized"}: {placement_text(hwnd)}')
            return 0
        if msg == WM_CAPTURECHANGED:
            state['drag'] = None
            return 0
        if msg in (WM_LBUTTONDOWN, WM_RBUTTONDOWN) and state['locked']:
            state['clicks'] += 1
            log(f'a click reached the locked overlay (total {state["clicks"]})')
            user32.InvalidateRect(hwnd, None, True)
            return 0
        if msg == WM_HOTKEY:
            if wparam == HOTKEY_LOCK:
                log('Ctrl+Shift+L pressed')
                set_locked(hwnd, not state['locked'])
            elif wparam == HOTKEY_QUIT:
                log('Ctrl+Shift+Q pressed')
                user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            remember_placement(hwnd)
            user32.UnregisterHotKey(hwnd, HOTKEY_LOCK)
            user32.UnregisterHotKey(hwnd, HOTKEY_QUIT)
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    proc = WNDPROC(wnd_proc)  # keep a reference for the window's lifetime
    instance = kernel32.GetModuleHandleW(None)
    wndclass = WNDCLASSW(lpfnWndProc=proc, hInstance=instance, lpszClassName=CLASS_NAME)
    if not user32.RegisterClassW(ctypes.byref(wndclass)):
        raise ctypes.WinError(ctypes.get_last_error())

    saved = load_placement(placement_file) or DEFAULT_PLACEMENT
    given = (args.x, args.y, args.width, args.height)
    x, y, width, height = (saved[i] if value is None else value for i, value in enumerate(given))
    requested = ex_style(args.locked)
    hwnd = user32.CreateWindowExW(
        requested, CLASS_NAME, 'TurboKit overlay probe', WS_POPUP,
        x, y, width, height, None, None, instance, None,
    )  # fmt: skip
    if not hwnd:
        raise ctypes.WinError(ctypes.get_last_error())
    apply_layering(hwnd, args.locked)
    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
    user32.SetTimer(hwnd, 1, 1000, None)
    hotkeys = {
        'Ctrl+Shift+L': user32.RegisterHotKey(
            hwnd, HOTKEY_LOCK, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_L
        ),
        'Ctrl+Shift+Q': user32.RegisterHotKey(
            hwnd, HOTKEY_QUIT, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_Q
        ),
    }

    log(f'running on {sys.platform}, Python {sys.version.split()[0]}')
    log(f'overlay at x={x} y={y}, {width}x{height}, move-mode opacity {args.alpha}/255')
    log(
        'locked (click-through, background hidden)'
        if args.locked
        else 'move mode: drag the box or its corner, then press Lock'
    )
    report_styles(hwnd, requested)
    for name, registered in hotkeys.items():
        log(f'{name} registered' if registered else f'{name} not available')

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    for handle in (key_brush, move_brush, button_brush):
        gdi32.DeleteObject(handle)
    log(f'done; clicks that reached the locked overlay: {state["clicks"]}')
    log(f'times the overlay was put back on top: {state["raises"]}')


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if sys.platform != 'win32':
        print(
            'This probe uses Windows calls. On the Mac, run it in the CrossOver bottle (experiments/README.md).'
        )
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
