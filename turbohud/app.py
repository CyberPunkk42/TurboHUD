"""Starting TurboHUD: settings, log, the overlay window, shortcuts and the tray icon."""

import argparse
import logging
import signal
import sys
import time
from dataclasses import replace
from pathlib import Path

from turbohud import __version__
from turbohud.core.settings import (
    LOG_FILE,
    SETTINGS_FILE,
    SectionPlace,
    fit_on_screens,
    load_settings,
    save_settings,
    settings_dir,
)

FRAME_MS = 50  # redraw interval: 20 times a second, as often as the race is read
PLACEMENT_EVERY = 1.0  # seconds between position checks in move mode
GROUP_EVERY = 0.2  # seconds between position checks in move mode while sections are grouped
ICON = 'tsu_turbo_hud_00.png'  # in assets/, also the bundled app's icon
log = logging.getLogger('turbohud')


def asset_path(name, bundle=None):
    """A file from assets/: next to the source, or inside the bundled app, whose folder
    PyInstaller gives as sys._MEIPASS."""
    bundle = getattr(sys, '_MEIPASS', None) if bundle is None else bundle
    return Path(bundle or Path(__file__).resolve().parents[1]) / 'assets' / name


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog='TurboHUD', description='A HUD overlay for Turbo Sliders Unlimited.'
    )
    parser.add_argument('--version', action='version', version=f'TurboHUD {__version__}')
    parser.add_argument('--move', action='store_true', help='start in move mode instead of locked')
    parser.add_argument('--seconds', type=float, help='quit after this many seconds (for tests)')
    args = parser.parse_args(argv)
    if args.seconds is not None and args.seconds <= 0:
        parser.error('--seconds must be positive')
    return args


def setup_log(folder):
    """Log to the terminal and to turbohud.log in the settings folder, replaced each run."""
    handlers = [logging.StreamHandler()] if sys.stderr else []  # a windowed app has no terminal
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(folder / LOG_FILE, mode='w', encoding='utf-8'))
    except OSError:
        pass  # the terminal still gets the log
    logging.basicConfig(
        level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S', handlers=handlers
    )


def start_live_race(platform=sys.platform):
    """On Linux, start reading TSU's race through the memory probe (TSU started from
    Steam with the launch option); None elsewhere, where the HUD keeps its session clock."""
    if not platform.startswith('linux'):
        return None
    from turbohud.tsu.client import LiveRace

    live = LiveRace()
    live.start()
    log.info('reading TSU live through the memory probe')
    return live


def run(args, folder):
    import PySide6
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QAction, QGuiApplication, QIcon
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    from turbohud.core.hud import (
        CLOCK_SECTIONS,
        RACE_SECTIONS,
        GroupMover,
        below,
        drawing_place,
        first_launch,
        local_time_rows,
        main_screen,
        session_rows,
    )
    from turbohud.overlay import HOTKEY_LOCK, HOTKEY_QUIT, native_for
    from turbohud.overlay.window import MovePanel, SectionWindow

    app = QApplication([sys.argv[0]])
    app.setApplicationName('TurboHUD')
    app.setQuitOnLastWindowClosed(False)
    icon = QIcon(str(asset_path(ICON)))
    if icon.isNull():
        log.warning('icon not found: %s', asset_path(ICON))
    app.setWindowIcon(icon)
    native = native_for()()
    native.prepare_app()
    path = folder / SETTINGS_FILE
    settings = load_settings(path)
    log.info(
        'TurboHUD %s on %s, Python %s, PySide6 %s',
        __version__,
        native.name,
        sys.version.split()[0],
        PySide6.__version__,
    )
    log.info('Qt platform: %s', QGuiApplication.platformName())

    live = start_live_race()
    pad = None
    if live is not None:
        from turbohud.core.race import Radar, Standings, race_sections, status_text, with_local_time

        layout = RACE_SECTIONS
        from turbohud.tsu.controller import Pad, combined

        pad = Pad()
        pad.start()
        standings = Standings()
        radar = Radar()

        def contents():
            snapshot = live.snapshot()
            current = race_sections(snapshot, time.monotonic(), settings.speed_unit, standings, radar)
            if 'pedals' in current:
                current['pedals'] = combined(current['pedals'], pad.pedals())
            return with_local_time(current, snapshot, time.localtime())

    else:
        layout = CLOCK_SECTIONS
        def contents():
            return {'clock': session_rows(time.monotonic() - started), 'localtime': local_time_rows(time.localtime())}

    started = time.monotonic()
    screens = [screen.geometry().getRect() for screen in QGuiApplication.screens()]
    windows = {section.name: SectionWindow(native, settings.theme, section) for section in layout}
    first = {name: window.base for name, window in windows.items()}
    screen = main_screen(screens)
    defaults = first_launch(layout, first, screen[:2] if screen else (0, 0))
    saved_places = {
        name: (place.x, place.y, place.width, place.height)
        for name, place in settings.sections.items()
        if name in windows
    }
    new = [section for section in layout if section.name not in saved_places and not section.bar]
    if saved_places and new:
        # Sections added in a later version: below the ones the player already placed.
        defaults.update(below(new, saved_places, first, screens))
    for section in layout:
        if section.bar:  # the blue flag and the radar: their own spots on the main screen
            defaults[section.name] = drawing_place(section, first[section.name], screen or (0, 0, 1920, 1080))
    for name, window in windows.items():
        saved = settings.sections.get(name)
        place = (saved.x, saved.y, saved.width, saved.height) if saved else defaults[name]
        place = fit_on_screens(place, screens)
        window.setGeometry(*place)
        window.backdrop = settings.backdrop
        window.show_on_top()
        window.set_wanted(saved.visible if saved else True)
        window.group = saved.group if saved else ''
        log.info('section %s at %s%s', name, place, '' if window.wanted else ' (hidden)')
    shortcuts = False
    panel = None  # made once the shortcuts are known
    locked = True

    def save():
        nonlocal settings
        places = {}
        for name, window in windows.items():
            x, y, width, height = window.placement()
            places[name] = SectionPlace(x, y, width, height, window.wanted, window.group)
        settings = replace(settings, sections=places)
        try:
            save_settings(path, settings)
        except OSError as error:
            log.warning('could not save the settings: %s', error)

    def panel_spot():
        """Where the move-mode panel goes: a third down the screen that holds the first
        shown section, in the middle."""
        shown = [w for w in windows.values() if w.wanted] or list(windows.values())
        x, y = shown[0].placement()[:2]
        for sx, sy, sw, sh in screens:
            if sx <= x < sx + sw and sy <= y < sy + sh:
                return sx + (sw - panel.width()) // 2, sy + sh // 3
        return x + 40, y + 40

    def set_locked(value):
        nonlocal locked, was_active
        if value == locked:
            return
        locked = value
        for window in windows.values():
            window.set_locked(value)
        move_action.setChecked(not value)
        was_active = False
        if value:
            panel.hide()
            native.give_focus_back()
            save()
            log.info('locked')
        else:
            mover.known.clear()  # compare from where the sections are now
            mover.pending.clear()
            native.take_focus()
            panel.show_at(*panel_spot())
            log.info('move mode')

    def set_mph(mph):
        nonlocal settings
        settings = replace(settings, speed_unit='mph' if mph else 'kmh')
        mph_action.setChecked(mph)
        panel.set_mph(mph)
        save()
        log.info('speed in %s', settings.speed_unit)

    def set_backdrop(backdrop):
        nonlocal settings
        settings = replace(settings, backdrop=backdrop)
        backdrop_action.setChecked(backdrop)
        panel.set_backdrop(backdrop)
        for window in windows.values():
            window.backdrop = backdrop
            window.update()
        save()
        log.info('tint behind the sections %s', 'on' if backdrop else 'off')

    mover = GroupMover()
    group_moving = False  # a group followed a drag at the last look

    def set_group(name, group):
        windows[name].group = group
        mover.known.clear()  # start comparing afresh
        save()
        log.info('section %s in group %s', name, group or '(none)')

    def placements():
        batch = getattr(native, 'placements', None)
        if batch is not None:
            found = batch(list(windows.values()))
            return {name: found[id(w)] for name, w in windows.items() if id(w) in found}
        return {name: w.placement() for name, w in windows.items()}

    def move_window(window, place, settle):
        native_move = getattr(native, 'move_window', None)
        if native_move is not None:
            native_move(window, place, settle)
        else:
            window.move(*place[:2])

    def follow_groups(now):
        """Move mode: move the rest of a group along with the section being dragged; once
        the drag is over, settle the moved ones (workspace and pin on Hyprland)."""
        nonlocal group_moving
        groups = {name: w.group for name, w in windows.items()}
        moves = mover.follow(placements(), groups, now)
        for name, place in moves.items():
            move_window(windows[name], place, settle=False)
        if group_moving and not moves:
            for name, window in windows.items():
                if window.group and name in mover.known:
                    move_window(window, mover.known[name], settle=True)
        group_moving = bool(moves)

    def set_wanted(name, wanted):
        windows[name].set_wanted(wanted)
        log.info('section %s %s', name, 'shown' if wanted else 'hidden')

    # Tray icon (menu bar on the Mac): the way to move mode where there are no shortcuts.
    tray = QSystemTrayIcon(icon)
    tray.setToolTip('TurboHUD')
    menu = QMenu()
    move_action = QAction('Move mode', menu, checkable=True)
    move_action.triggered.connect(lambda checked: set_locked(not checked))
    quit_action = QAction('Quit TurboHUD', menu)
    quit_action.triggered.connect(app.quit)
    menu.addAction(move_action)
    mph_action = QAction('Speed in mph', menu, checkable=True)
    mph_action.setChecked(settings.speed_unit == 'mph')
    mph_action.triggered.connect(lambda checked: set_mph(checked))
    menu.addAction(mph_action)
    backdrop_action = QAction('Light tint behind the sections', menu, checkable=True)
    backdrop_action.setChecked(settings.backdrop)
    backdrop_action.triggered.connect(lambda checked: set_backdrop(checked))
    menu.addAction(backdrop_action)
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
            QTimer.singleShot(0, lambda: set_locked(not locked))
        elif number == HOTKEY_QUIT:
            log.info('Ctrl+Shift+Q pressed')
            QTimer.singleShot(0, app.quit)

    shortcuts = native.register_hotkeys(on_hotkey)
    log.info('Ctrl+Shift+L and Ctrl+Shift+Q registered' if shortcuts else 'no system-wide shortcuts')
    panel = MovePanel(native, layout, shortcuts, settings.speed_unit == 'mph', settings.backdrop)
    panel.mph_changed.connect(set_mph)
    panel.backdrop_changed.connect(set_backdrop)
    for name, window in windows.items():
        panel.set_wanted(name, window.wanted)
    panel.lock_requested.connect(lambda: set_locked(True))
    panel.quit_requested.connect(app.quit)
    panel.wanted_changed.connect(set_wanted)
    panel.group_changed.connect(set_group)
    for name, window in windows.items():
        panel.set_group(name, window.group)

    was_active = False  # in move mode: whether TurboHUD has been the active app yet

    def on_state(state):
        nonlocal was_active
        if locked or not getattr(native, 'auto_lock', True):
            return
        if state == Qt.ApplicationActive:
            was_active = True
        elif was_active:
            # Another app (the game, usually) became active: move mode is over. Playing
            # while the overlay is the active app upsets the game's mouse handling.
            log.info('another app became active; locking')
            set_locked(True)

    app.applicationStateChanged.connect(on_state)

    last_seen = 0.0

    shown_status = None

    def tick():
        nonlocal last_seen, shown_status
        current = contents()
        if live is not None:
            text = status_text(live.snapshot())
            if text != shown_status:
                tray.setToolTip(f'TurboHUD - {text}')
                shown_status = text
        for name, window in windows.items():
            window.rows = current.get(name, [])
            window.pedals = current.get('pedals')
            window.opacity = current.get('blue')
            window.radar = current.get('radar')
            window.update()
        grouped = any(w.group for w in windows.values())
        every = GROUP_EVERY if grouped else PLACEMENT_EVERY
        if not locked and time.monotonic() - last_seen >= every:
            # In move mode, note where the sections are: on Wayland only the desktop
            # knows, and it may no longer say once TurboHUD is quitting. Grouped
            # sections follow the one being dragged.
            last_seen = time.monotonic()
            if grouped:
                follow_groups(last_seen)
            else:
                placements()
        if args.seconds is not None and time.monotonic() - started >= args.seconds:
            log.info('time is up')
            app.quit()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(FRAME_MS)  # also lets Python see Ctrl+C between frames
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    if args.move or not shortcuts and not tray.isVisible():
        set_locked(False)  # without shortcuts or tray, locked could not be undone
    app.exec()
    if not locked:
        set_locked(True)  # saves and hands the focus back
    else:
        save()
    if live is not None:
        live.stop()
    if pad is not None:
        pad.stop()
    native.unregister_hotkeys()
    tray.hide()
    log.info('done')
    return 0


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        import PySide6  # noqa: F401 - only checks that Qt is there
    except ImportError:
        print('TurboHUD needs PySide6. Start it with run_turbohud.sh (macOS, Linux) or', file=sys.stderr)
        print('run_turbohud.cmd (Windows), which set it up first.', file=sys.stderr)
        return 2
    folder = settings_dir()
    setup_log(folder)
    return run(args, folder)
