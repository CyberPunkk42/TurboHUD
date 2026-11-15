"""Window count experiment: do 17 small overlay windows cost the game more frames than one
large window holding the same 17 boxes, or than one window the size of the screen?

TurboHUD draws each section in its own window. On the Mac, 120 FPS with TurboHUD closed or
one section shown fell to 80 to 110 with all 17 shown (2026-11-09, Metal HUD), and each
window added about the same to WindowServer whatever it showed. So, locked, the Mac draws
every section in one window per screen (HudCanvas). On Windows and Linux each section still
has its own window: this measures there (since 2026-11-15) whether one window would help.

It runs by itself through these phases, then quits:

    1. nothing shown          (--rest seconds, 30 by default)
    2. 17 small windows       (--each seconds, 45 by default), as TurboHUD on Windows and Linux
    3. one large window       (--each seconds), all 17 boxes in it, only as large as they need
    4. one window per screen  (--each seconds), as TurboHUD locked on the Mac
    5. nothing shown          (--rest seconds)

The boxes take the places and sizes of TurboHUD's own sections, read from its settings
file (only read). Each shows the phase's name and a counter changing 20 times a second,
like the running lap. The windows let clicks through and stay above the game as TurboHUD's
do: on the Mac above TSU's Fullscreen, on Hyprland floating and pinned (requests for the
probe's own windows only). Quit TurboHUD first. Start it from the repository:

    macOS, Linux:  .buildtools/venv/bin/python -B experiments/window_count_probe.py
    Windows:       .buildtools\\venv\\Scripts\\python.exe -B experiments\\window_count_probe.py

and watch the game's FPS in each phase (the Metal HUD on the Mac; Steam's in-game FPS counter
on Windows and Linux). Ctrl+C in the terminal quits early.
"""

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core.settings import SETTINGS_FILE, settings_dir

SETTINGS = settings_dir() / SETTINGS_FILE
FALLBACK_BOXES = [(40 + (i % 4) * 420, 60 + (i // 4) * 220, 380, 120) for i in range(17)]
TICK_MS = 50  # 20 changes a second, as TurboHUD's fastest sections
BOX_FILL = (0, 0, 0, 90)
TEXT = (255, 255, 255, 230)
TITLE = 'TurboHUD probe'  # each window's title has its number: Hyprland finds a window by its title
# Where to read the game's FPS, by system (sys.platform's start).
FPS_COUNTERS = {
    'darwin': 'the Metal HUD',
    'win32': "Steam's in-game FPS counter (Steam > Settings > In Game > In-game FPS counter)",
    'linux': "Steam's in-game FPS counter (Steam > Settings > In Game), or MangoHud",
}


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description='17 small overlay windows against one large one and one per screen'
    )
    parser.add_argument(
        '--settings', type=Path, default=SETTINGS, help="TurboHUD's settings file (read only)"
    )
    parser.add_argument(
        '--rest', type=float, default=30.0, help='seconds with nothing shown, at the start and end'
    )
    parser.add_argument(
        '--each', type=float, default=45.0, help='seconds for each of the three window phases'
    )
    return parser.parse_args(argv)


def section_boxes(path):
    """(x, y, width, height) of each section in TurboHUD's settings file, shown or not, in
    its order; the fallback grid of 17 boxes when the file is missing or has none."""
    try:
        sections = json.loads(Path(path).read_text(encoding='utf-8')).get('sections') or {}
        boxes = [(int(s['x']), int(s['y']), int(s['width']), int(s['height'])) for s in sections.values()]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        boxes = []
    return boxes or list(FALLBACK_BOXES)


def bounds(boxes):
    """The smallest (x, y, width, height) holding all of `boxes`."""
    left = min(x for x, _y, _w, _h in boxes)
    top = min(y for _x, y, _w, _h in boxes)
    right = max(x + w for x, _y, w, _h in boxes)
    bottom = max(y + h for _x, y, _w, h in boxes)
    return left, top, right - left, bottom - top


def screens_with_boxes(screens, boxes):
    """[(screen, the boxes whose middle is on it)] for each screen (x, y, width, height) that
    has any, as TurboHUD's one window per screen; a box on no screen goes to the first."""
    held = {screen: [] for screen in screens}
    for box in boxes:
        x, y, w, h = box
        middle = (x + w / 2, y + h / 2)
        on = next(
            (s for s in screens if s[0] <= middle[0] < s[0] + s[2] and s[1] <= middle[1] < s[1] + s[3]),
            screens[0] if screens else None,
        )
        if on is not None:
            held[on].append(box)
    return [(screen, inside) for screen, inside in held.items() if inside]


def phases(rest, each, count):
    """[(name, seconds, mode)], mode None (nothing), 'many', 'one' or 'screen'."""
    return [
        ('nothing', rest, None),
        (f'{count} windows', each, 'many'),
        ('one window', each, 'one'),
        ('one per screen', each, 'screen'),
        ('nothing again', rest, None),
    ]


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    from PySide6.QtCore import QRectF, Qt, QTimer
    from PySide6.QtGui import QColor, QFont, QPainter
    from PySide6.QtWidgets import QApplication, QWidget

    from turbohud.overlay import choose_platform, native_for

    platform = choose_platform()  # as TurboHUD: through XWayland on Wayland desktops other than Hyprland
    if platform is not None:
        os.environ['QT_QPA_PLATFORM'] = platform
    app = QApplication(sys.argv[:1])
    # Closing the windows for the last phase must not quit it (found 2026-11-15: "nothing again" was
    # cut short); it quits by itself when the phases are over.
    app.setQuitOnLastWindowClosed(False)
    native = native_for()()
    native.prepare_app()
    boxes = section_boxes(args.settings)
    plan = phases(args.rest, args.each, len(boxes))
    state = {'label': '', 'count': 0}
    made = {'windows': 0}

    class Overlay(QWidget):
        """A see-through, click-through window drawing `boxes` (screen places) in it."""

        focusable = False  # as TurboHUD's locked sections: no keyboard focus

        def __init__(self, place, inner):
            super().__init__(
                None,
                Qt.FramelessWindowHint
                | Qt.WindowStaysOnTopHint
                | Qt.WindowTransparentForInput
                | (Qt.Tool if sys.platform != 'darwin' else Qt.Widget),
            )
            made['windows'] += 1
            self.setWindowTitle(f'{TITLE} {made["windows"]}')
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating)
            self.setGeometry(*place)
            self.inner = [(x - place[0], y - place[1], w, h) for x, y, w, h in inner]

        def paintEvent(self, _event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            font = QFont()
            font.setPixelSize(18)
            painter.setFont(font)
            text = f'{state["label"]}  {state["count"] / 20:.1f}'
            for x, y, w, h in self.inner:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(*BOX_FILL))
                painter.drawRoundedRect(QRectF(x, y, w, h), 6, 6)
                painter.setPen(QColor(*TEXT))
                painter.drawText(QRectF(x + 8, y, w - 16, h), Qt.AlignVCenter | Qt.AlignLeft, text)

    shown = []

    def show(mode):
        for window in shown:
            window.close()
        shown.clear()
        if mode == 'many':
            shown.extend(Overlay(box, [box]) for box in boxes)
        elif mode == 'one':
            shown.append(Overlay(bounds(boxes), boxes))
        elif mode == 'screen':
            screens = [s.geometry().getRect() for s in app.screens()]
            shown.extend(Overlay(screen, inside) for screen, inside in screens_with_boxes(screens, boxes))
        for window in shown:
            window.show()
            native.raise_window(window)

    started = time.monotonic()
    ends = []
    total = 0.0
    for name, seconds, mode in plan:
        total += seconds
        ends.append((total, name, mode))
    current = {'index': -1}

    def tick():
        elapsed = time.monotonic() - started
        index = next((i for i, (end, _n, _m) in enumerate(ends) if elapsed < end), None)
        if index is None:
            print(f'{time.strftime("%H:%M:%S")} done', flush=True)
            app.quit()
            return
        if index != current['index']:
            current['index'] = index
            _end, name, mode = ends[index]
            state['label'] = name
            show(mode)
            print(f'{time.strftime("%H:%M:%S")} {name} ({len(shown)} shown): note the FPS now', flush=True)
        state['count'] += 1
        for window in shown:
            window.update()

    counter = next(
        (text for start, text in FPS_COUNTERS.items() if sys.platform.startswith(start)), 'an FPS counter'
    )
    print(f'{len(boxes)} boxes from {args.settings}; area of the one window: {bounds(boxes)}', flush=True)
    print(f'{native.name}, Qt platform {app.platformName()}; read the FPS with {counter}', flush=True)
    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(TICK_MS)
    signal.signal(signal.SIGINT, lambda *_: app.quit())  # Ctrl+C; the timer lets Python see it
    tick()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
