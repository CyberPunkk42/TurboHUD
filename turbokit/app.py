"""Starting TurboKit: settings, log, the overlay window, shortcuts and the tray icon."""

import argparse
import logging
import signal
import sys

from turbokit import __version__
from turbokit.core.settings import (
    LOG_FILE,
    SETTINGS_FILE,
    fit_on_screens,
    load_settings,
    save_settings,
    settings_dir,
)

FRAME_MS = 100  # redraw interval
log = logging.getLogger('turbokit')


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog='TurboKit', description='A HUD overlay for Turbo Sliders Unlimited.'
    )
    parser.add_argument('--version', action='version', version=f'TurboKit {__version__}')
    parser.add_argument('--move', action='store_true', help='start in move mode instead of locked')
    parser.add_argument('--seconds', type=float, help='quit after this many seconds (for tests)')
    args = parser.parse_args(argv)
    if args.seconds is not None and args.seconds <= 0:
        parser.error('--seconds must be positive')
    return args


def setup_log(folder):
    """Log to the terminal and to turbokit.log in the settings folder, replaced each run."""
    handlers = [logging.StreamHandler()] if sys.stderr else []  # a windowed app has no terminal
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(folder / LOG_FILE, mode='w', encoding='utf-8'))
    except OSError:
        pass  # the terminal still gets the log
    logging.basicConfig(
        level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S', handlers=handlers
    )


def run(args, folder):
    import PySide6
    from PySide6.QtCore import QRectF, Qt, QTimer
    from PySide6.QtGui import QAction, QColor, QFont, QGuiApplication, QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    from turbokit.overlay import HOTKEY_LOCK, HOTKEY_QUIT, native_for
    from turbokit.overlay.window import OverlayWindow

    app = QApplication([sys.argv[0]])
    app.setApplicationName('TurboKit')
    app.setQuitOnLastWindowClosed(False)
    native = native_for()()
    native.prepare_app()
    path = folder / SETTINGS_FILE
    settings = load_settings(path)
    log.info(
        'TurboKit %s on %s, Python %s, PySide6 %s',
        __version__,
        native.name,
        sys.version.split()[0],
        PySide6.__version__,
    )
    log.info('Qt platform: %s', QGuiApplication.platformName())

    overlay = OverlayWindow(native, settings.theme)
    screens = [screen.geometry().getRect() for screen in QGuiApplication.screens()]
    placement = fit_on_screens(settings.placement, screens)
    overlay.setGeometry(*placement)
    overlay.show_on_top()
    log.info('overlay at %s', placement)

    def save():
        nonlocal settings
        settings = type(settings)(placement=overlay.placement(), theme=settings.theme)
        try:
            save_settings(path, settings)
        except OSError as error:
            log.warning('could not save the settings: %s', error)

    def toggle():
        overlay.set_locked(not overlay.locked)

    # Tray icon (menu bar on the Mac): the way to move mode where there are no shortcuts.
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(settings.theme.accent_color))
    painter.drawRoundedRect(QRectF(4, 4, 56, 56), 14, 14)
    font = QFont()
    font.setPixelSize(40)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor(20, 20, 20))
    painter.drawText(QRectF(0, 0, 64, 64), Qt.AlignCenter, 'T')
    painter.end()
    tray = QSystemTrayIcon(QIcon(pixmap))
    tray.setToolTip('TurboKit')
    menu = QMenu()
    move_action = QAction('Move mode', menu, checkable=True)
    move_action.triggered.connect(lambda checked: overlay.set_locked(not checked))
    quit_action = QAction('Quit TurboKit', menu)
    quit_action.triggered.connect(app.quit)
    menu.addAction(move_action)
    menu.addSeparator()
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.show()
    else:
        log.info('no tray on this desktop')

    def on_hotkey(number):
        # Leave the system's callback first, then act.
        if number == HOTKEY_LOCK:
            log.info('Ctrl+Shift+L pressed')
            QTimer.singleShot(0, toggle)
        elif number == HOTKEY_QUIT:
            log.info('Ctrl+Shift+Q pressed')
            QTimer.singleShot(0, app.quit)

    overlay.shortcuts = native.register_hotkeys(on_hotkey)
    log.info('Ctrl+Shift+L and Ctrl+Shift+Q registered' if overlay.shortcuts else 'no system-wide shortcuts')

    was_active = False  # in move mode: whether TurboKit has been the active app yet

    def on_locked(locked):
        nonlocal was_active
        move_action.setChecked(not locked)
        was_active = False
        if locked:
            save()

    overlay.locked_changed.connect(on_locked)
    overlay.close_requested.connect(app.quit)

    def on_state(state):
        nonlocal was_active
        if overlay.locked:
            return
        if state == Qt.ApplicationActive:
            was_active = True
        elif was_active:
            # Another app (the game, usually) became active: move mode is over. Playing
            # while the overlay is the active app upsets the game's mouse handling.
            log.info('another app became active; locking')
            overlay.set_locked(True)

    app.applicationStateChanged.connect(on_state)

    def tick():
        overlay.update()
        if args.seconds is not None and overlay.elapsed() >= args.seconds:
            log.info('time is up')
            app.quit()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(FRAME_MS)  # also lets Python see Ctrl+C between frames
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    if args.move or not overlay.shortcuts and not tray.isVisible():
        overlay.set_locked(False)  # without shortcuts or tray, locked could not be undone
    app.exec()
    if not overlay.locked:
        overlay.set_locked(True)  # saves and hands the focus back
    else:
        save()
    native.unregister_hotkeys()
    tray.hide()
    log.info('done')
    return 0


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        import PySide6  # noqa: F401 - only checks that Qt is there
    except ImportError:
        print('TurboKit needs PySide6. Start it with run_turbokit.sh (macOS, Linux) or', file=sys.stderr)
        print('run_turbokit.cmd (Windows), which set it up first.', file=sys.stderr)
        return 2
    folder = settings_dir()
    setup_log(folder)
    return run(args, folder)
