"""Window count experiment: do 17 small overlay windows cost the game more frames than one
large window holding the same 17 boxes?

TurboHUD draws each section in its own window. On the Mac, 120 FPS with TurboHUD closed or
one section shown fell to 80 to 110 with all 17 shown (2026-11-09, Metal HUD), and each
window added about the same to WindowServer whatever it showed. Before the overlay is
rebuilt as one window, this measures whether one large, mostly see-through window is
cheaper, or costs by its area instead.

It runs by itself through these phases, then quits:

    1. nothing shown          (--rest seconds, 30 by default)
    2. 17 small windows       (--each seconds, 45 by default), as TurboHUD now
    3. one large window       (--each seconds), all 17 boxes in it
    4. nothing shown          (--rest seconds)

The boxes take the places and sizes of TurboHUD's own sections, read from its settings
file (only read). Each shows the phase's name and a counter changing 20 times a second,
like the running lap. The windows let clicks through and, on the Mac, sit above TSU's
Fullscreen. Quit TurboHUD first. Start it from the repository:

    .buildtools/venv/bin/python -B experiments/window_count_probe.py

and watch the game's FPS (the Metal HUD) in each phase. Ctrl+C in the terminal quits early.
"""

import argparse
import json
import signal
import sys
import time
from pathlib import Path

SETTINGS = Path.home() / 'Library' / 'Application Support' / 'TurboHUD' / 'settings.json'
FALLBACK_BOXES = [(40 + (i % 4) * 420, 60 + (i // 4) * 220, 380, 120) for i in range(17)]
TICK_MS = 50  # 20 changes a second, as TurboHUD's fastest sections
BOX_FILL = (0, 0, 0, 90)
TEXT = (255, 255, 255, 230)


def parse_args(argv):
    parser = argparse.ArgumentParser(description='17 small overlay windows against one large one')
    parser.add_argument(
        '--settings', type=Path, default=SETTINGS, help="TurboHUD's settings file (read only)"
    )
    parser.add_argument(
        '--rest', type=float, default=30.0, help='seconds with nothing shown, at the start and end'
    )
    parser.add_argument('--each', type=float, default=45.0, help='seconds for each of the two window phases')
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


def phases(rest, each, count):
    """[(name, seconds, mode)], mode None (nothing), 'many' or 'one'."""
    return [
        ('nothing', rest, None),
        (f'{count} windows', each, 'many'),
        ('one window', each, 'one'),
        ('nothing again', rest, None),
    ]


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    from PySide6.QtCore import QRectF, Qt, QTimer
    from PySide6.QtGui import QColor, QFont, QPainter
    from PySide6.QtWidgets import QApplication, QWidget

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    native = None
    if sys.platform == 'darwin':
        from turbohud.overlay.macos import Native

        native = Native()

    app = QApplication(sys.argv[:1])
    if native is not None:
        native.prepare_app()
    boxes = section_boxes(args.settings)
    plan = phases(args.rest, args.each, len(boxes))
    state = {'label': '', 'count': 0}

    class Overlay(QWidget):
        """A see-through, click-through window drawing `boxes` (screen places) in it."""

        def __init__(self, place, inner):
            super().__init__(
                None,
                Qt.FramelessWindowHint
                | Qt.WindowStaysOnTopHint
                | Qt.WindowTransparentForInput
                | (Qt.Tool if sys.platform != 'darwin' else Qt.Widget),
            )
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
        for window in shown:
            window.show()
            if native is not None:
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
            print(f'{time.strftime("%H:%M:%S")} {name}: note the FPS now', flush=True)
            show(mode)
        state['count'] += 1
        for window in shown:
            window.update()

    print(f'{len(boxes)} boxes from {args.settings}; area of the one window: {bounds(boxes)}', flush=True)
    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(TICK_MS)
    signal.signal(signal.SIGINT, lambda *_: app.quit())  # Ctrl+C; the timer lets Python see it
    tick()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
