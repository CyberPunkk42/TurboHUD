"""Starting TurboHUD: settings, log, the overlay window, shortcuts and the tray icon."""

import argparse
import logging
import os
import shutil
import signal
import sys
import time
from dataclasses import replace
from functools import partial
from pathlib import Path

from turbohud import __version__
from turbohud.core.hud import CLOCK_SECTIONS, RACE_SECTIONS, tight_place
from turbohud.core.settings import (
    LAYOUT_VERSION,
    LOG_FILE,
    PRESETS,
    SETTINGS_FILE,
    SectionPlace,
    fit_on_screens,
    load_settings,
    preset_places,
    save_settings,
    settings_dir,
)

FRAME_MS = 50  # redraw interval: 20 times a second, as often as the race is read
PLACEMENT_EVERY = 1.0  # seconds between position checks in move mode
MIN_SECTION = 20  # pixels: the smallest a section gets from Smaller in the settings
GROUP_EVERY = 0.2  # seconds between position checks in move mode while sections are grouped
ICON = 'tsu_turbo_hud_00.png'  # in assets/, also the bundled app's icon
log = logging.getLogger('turbohud')


def upgrade_layout(settings, path, ink):
    """The settings with sections saved in an older layout converted, once, and written
    back; the file as it was stays beside it. `ink` is turbohud.hud.painter.text_ink."""
    if settings.layout_version >= LAYOUT_VERSION:
        return settings
    known = {section.name: section for section in (*RACE_SECTIONS, *CLOCK_SECTIONS)}
    places = {}
    for name, place in settings.sections.items():
        if name in known:
            box = (place.x, place.y, place.width, place.height)
            x, y, width, height = tight_place(known[name], box, settings.theme.scale, ink)
            place = replace(place, x=x, y=y, width=width, height=height)
        places[name] = place
    settings = replace(settings, sections=places, layout_version=LAYOUT_VERSION)
    if places:
        try:
            shutil.copy2(path, path.with_name(f'{path.stem}.before-layout-{LAYOUT_VERSION}{path.suffix}'))
            save_settings(path, settings)
            log.info('section sizes converted to layout %d', LAYOUT_VERSION)
        except OSError as error:
            log.warning('could not save the converted section sizes: %s', error)
    return settings


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
    parser.add_argument(
        '--move',
        action='store_true',
        help='start in move mode instead of locked (or switch a running TurboHUD to it)',
    )
    commands = parser.add_mutually_exclusive_group()
    commands.add_argument(
        '--toggle', action='store_true', help='switch a running TurboHUD\'s move mode on or off'
    )
    commands.add_argument('--lock', action='store_true', help='end a running TurboHUD\'s move mode')
    commands.add_argument(
        '--settings', action='store_true', help='open a running TurboHUD\'s settings window'
    )
    commands.add_argument(
        '--preset', type=int, choices=PRESETS, help='load a layout preset in a running TurboHUD'
    )
    commands.add_argument('--quit', action='store_true', help='quit a running TurboHUD')
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
    """Start reading TSU's race: on Linux through the memory probe (TSU started from Steam
    with the launch option), on the Mac through a reader in TSU's CrossOver bottle. None
    elsewhere, where the HUD keeps its session clock."""
    if platform == 'darwin':
        from turbohud.tsu.bottle import Bottle
        from turbohud.tsu.client import LiveRace

        bottle = Bottle()
        live = LiveRace(connect=bottle.connect, close=bottle.close)
        way = 'a reader in the CrossOver bottle'
    elif platform.startswith('linux'):
        from turbohud.tsu.client import LiveRace

        live = LiveRace()
        way = 'the memory probe'
    else:
        return None
    live.start()
    log.info('reading TSU live through %s', way)
    return live


def listen_for_commands(app, on_command):
    """Answer commands from turbohud.control on its socket; True if listening."""
    from PySide6.QtNetwork import QLocalServer

    from turbohud import control

    path = control.control_path()
    if path is None:
        return False
    try:
        control.prepare_folder(path)
    except OSError as error:
        log.info('no command socket: %s', error)
        return False
    QLocalServer.removeServer(str(path))  # left behind by a TurboHUD that is gone (none answered)
    server = QLocalServer(app)
    if not server.listen(str(path)):
        log.info('no command socket: %s', server.errorString())
        return False

    def connected():
        conn = server.nextPendingConnection()

        def read():
            if not conn.canReadLine():
                return
            command = bytes(conn.readLine()).decode('utf-8', 'replace').strip()
            conn.write((on_command(command) + '\n').encode())
            conn.flush()
            conn.disconnectFromServer()

        conn.readyRead.connect(read)
        conn.disconnected.connect(conn.deleteLater)

    server.newConnection.connect(connected)
    app.aboutToQuit.connect(server.close)
    return True


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
        centred,
        drawing_place,
        first_launch,
        free_spot,
        local_time_rows,
        main_screen,
        match_sizes,
        screen_of,
        session_rows,
    )
    from turbohud.hud.painter import text_ink, text_width
    from turbohud.overlay import HOTKEY_LOCK, HOTKEY_PRESETS, HOTKEY_QUIT, choose_platform, native_for
    from turbohud.overlay.settings_window import SettingsWindow
    from turbohud.overlay.window import MovePanel, SectionWindow, window_flags

    platform = choose_platform()
    if platform is not None:
        os.environ['QT_QPA_PLATFORM'] = platform
    app = QApplication([sys.argv[0]])
    if platform is not None:
        log.info('Wayland without Hyprland: running through XWayland, where staying on top works')
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
        if sys.platform.startswith('linux'):  # the Linux joystick interface
            from turbohud.tsu.controller import Pad, combined

            pad = Pad()
            pad.start()
        from turbohud.core.trackmap import TrackMap

        standings = Standings()
        radar = Radar()
        track_map = TrackMap(settings.map_others, folder)  # learnt tracks beside the settings

        def contents():
            snapshot = live.snapshot()
            track_map.others = settings.map_others
            current = race_sections(
                snapshot, time.monotonic(), settings.speed_unit, standings, radar, track_map
            )
            if pad is not None and 'pedals' in current:
                current['pedals'] = combined(current['pedals'], pad.pedals())
            return with_local_time(current, snapshot, time.localtime())

    else:
        layout = CLOCK_SECTIONS

        def contents():
            return {
                'clock': session_rows(time.monotonic() - started),
                'localtime': local_time_rows(time.localtime()),
            }

    started = time.monotonic()
    screens = [screen.geometry().getRect() for screen in QGuiApplication.screens()]
    settings = upgrade_layout(settings, path, text_ink)
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
        if section.bar:  # the blue flag, the radar and the track map: their own spots
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
        write_settings()

    def write_settings():
        try:
            save_settings(path, settings)
        except OSError as error:
            log.warning('could not save the settings: %s', error)

    def panel_spot():
        """Where the move-mode panel goes: on the screen that holds the first shown
        section, near the middle a third down, but never over a shown section (it would
        hide it from dragging)."""
        shown = [w for w in windows.values() if w.wanted] or list(windows.values())
        boxes = [w.placement() for w in shown]
        x, y = boxes[0][:2]
        for screen in screens:
            sx, sy, sw, sh = screen
            if sx <= x < sx + sw and sy <= y < sy + sh:
                wanted = (sx + (sw - panel.width()) // 2, sy + sh // 3)
                return free_spot((panel.width(), panel.height()), screen, boxes, wanted)
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

    def set_map_others(others):
        nonlocal settings
        settings = replace(settings, map_others=others)
        map_others_action.setChecked(others)
        panel.set_map_others(others)
        save()
        log.info('other cars on the track map %s', 'on' if others else 'off')

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
            window.setGeometry(*place)

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

    def align(name, across, down):
        """Centre a section on the screen that holds it (the panel's Centre buttons)."""
        window = windows[name]
        place = tuple(window.placement())
        screen = screen_of(place, screens)
        if screen is None:
            return
        target = centred(place, screen, across, down)
        move_window(window, target, settle=True)
        mover.known[name] = target  # TurboHUD moved it: its group stays where it is
        mover.pending[name] = (target[:2], time.monotonic() + 1.0)
        log.info(
            'section %s centred%s%s at %s', name, ' across' if across else '', ' down' if down else '', target
        )

    def set_theme(theme):
        """New colours from the settings window: every section draws with them."""
        nonlocal settings
        settings = replace(settings, theme=theme)
        for window in windows.values():
            window.theme = theme
            window.update()
        save()
        log.info(
            'colours: text %s, highlight %s, outline %s',
            theme.text_color,
            theme.accent_color,
            theme.outline_color,
        )

    def resize_all(factor):
        """Every section bigger or smaller by `factor`, from its top-left corner."""
        for name, window in windows.items():
            x, y, width, height = window.placement()
            place = (x, y, max(MIN_SECTION, round(width * factor)), max(MIN_SECTION, round(height * factor)))
            move_window(window, place, settle=True)
            mover.known[name] = place  # TurboHUD resized it: not a drag
        save()
        log.info('all sections %s', 'bigger' if factor > 1 else 'smaller')

    settings_window = None

    def open_settings():
        nonlocal settings_window
        if settings_window is None:
            settings_window = SettingsWindow(native, window_flags(), settings.theme)
            settings_window.theme_changed.connect(set_theme)
            settings_window.resize_requested.connect(resize_all)
        if not settings_window.isVisible():
            x, y = panel_spot()
            settings_window.show_at(x + panel.width() + 20, y)

    def set_wanted(name, wanted):
        windows[name].set_wanted(wanted)
        log.info('section %s %s', name, 'shown' if wanted else 'hidden')

    def match_group(group):
        """The group's text sections get the same text size and width (the panel's Match).
        The settings take these places, not what the desktop says yet (see load_preset)."""
        nonlocal settings
        sized = {
            window.section: tuple(window.placement())
            for window in windows.values()
            if window.group == group and not window.section.drawing
        }
        if len(sized) < 2:
            return
        until = time.monotonic() + 1.0
        places = dict(settings.sections)
        for name, box in match_sizes(sized, settings.theme.scale, text_width, text_ink).items():
            window = windows[name]
            move_window(window, box, settle=True)
            mover.known[name] = box  # TurboHUD resized it: not a drag
            mover.pending[name] = (box, until)
            x, y, width, height = box
            places[name] = SectionPlace(x, y, width, height, window.wanted, window.group)
        settings = replace(settings, sections=places)
        write_settings()
        log.info('group %s: same text size and width', group)

    def save_preset(number):
        """Keep the layout as it is now in a preset, and in the settings as well."""
        nonlocal settings
        save()
        presets = {**settings.presets, number: {name: settings.sections[name] for name in windows}}
        settings = replace(settings, presets=presets)
        write_settings()
        panel.set_preset_saved(number)
        log.info('preset %d saved', number)

    def load_preset(number):
        """Put every section as the preset has it. What the desktop reports may lag behind
        the move (Wayland), so the settings take the preset's places, not what it says."""
        nonlocal settings
        places = preset_places(settings.presets.get(number, {}), windows, screens)
        if not places:
            log.info('preset %d is empty', number)
            return
        until = time.monotonic() + 1.0
        for name, place in places.items():
            window = windows[name]
            box = (place.x, place.y, place.width, place.height)
            move_window(window, box, settle=True)
            mover.known[name] = box  # TurboHUD moved it: its group stays where it is
            mover.pending[name] = (box[:2], until)
            window.set_wanted(place.visible)
            window.group = place.group
            panel.set_wanted(name, place.visible)
            panel.set_group(name, place.group)
        settings = replace(settings, sections={**settings.sections, **places})
        write_settings()
        log.info('preset %d loaded', number)

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
    map_others_action = QAction('Other cars on the track map', menu, checkable=True)
    map_others_action.setChecked(settings.map_others)
    map_others_action.triggered.connect(lambda checked: set_map_others(checked))
    if any(section.drawing == 'map' for section in layout):
        menu.addAction(map_others_action)
    settings_action = QAction('Settings…', menu)
    settings_action.triggered.connect(lambda: open_settings())
    menu.addAction(settings_action)
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
        elif number in HOTKEY_PRESETS:
            preset = HOTKEY_PRESETS[number]
            log.info('Ctrl+Shift+%d pressed', preset)
            QTimer.singleShot(0, lambda: load_preset(preset))

    shortcuts = native.register_hotkeys(on_hotkey)
    log.info('Ctrl+Shift+L and Ctrl+Shift+Q registered' if shortcuts else 'no system-wide shortcuts')

    def on_command(command):
        """A command from the command line (turbohud.control): 'ok' or an error text."""
        actions = {
            'ping': lambda: None,
            'toggle': lambda: set_locked(not locked),
            'move': lambda: set_locked(False),
            'lock': lambda: set_locked(True),
            'settings': open_settings,
            'quit': app.quit,
            **{f'preset{number}': partial(load_preset, number) for number in PRESETS},
        }
        action = actions.get(command)
        if action is None:
            return f'unknown command {command!r}'
        for number in PRESETS:
            if command == f'preset{number}' and number not in settings.presets:
                return f'preset {number} is empty: save it first'
        log.info('command: %s', command)
        QTimer.singleShot(0, action)  # answer first, then act
        return 'ok'

    commands = listen_for_commands(app, on_command)
    log.info('commands: run_turbohud.sh --toggle / --quit' if commands else 'no command socket')
    panel = MovePanel(
        native,
        layout,
        shortcuts,
        settings.speed_unit == 'mph',
        settings.backdrop,
        commands,
        settings.map_others,
        tuple(settings.presets),
    )
    panel.preset_save_requested.connect(save_preset)
    panel.preset_load_requested.connect(load_preset)
    panel.match_requested.connect(match_group)
    panel.mph_changed.connect(set_mph)
    panel.backdrop_changed.connect(set_backdrop)
    panel.map_others_changed.connect(set_map_others)
    panel.settings_requested.connect(open_settings)
    for name, window in windows.items():
        panel.set_wanted(name, window.wanted)
    panel.lock_requested.connect(lambda: set_locked(True))
    panel.quit_requested.connect(app.quit)
    panel.wanted_changed.connect(set_wanted)
    panel.group_changed.connect(set_group)
    panel.align_requested.connect(align)
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
            if window.show_content(
                current.get(name, []),
                current.get('pedals'),
                current.get('blue'),
                current.get('radar'),
                current.get('trackmap'),
                current.get('levels', {}).get(name),
            ):
                window.update()  # only what changed: drawing every section each frame stutters
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


def command_of(args):
    """The command for a running TurboHUD that the arguments ask for, or None."""
    for name in ('toggle', 'lock', 'settings', 'quit'):
        if getattr(args, name):
            return name
    return f'preset{args.preset}' if args.preset else None


def tell_running(args, send=None):
    """Pass a command to a running TurboHUD (see turbohud.control). Returns an exit code
    when that is all there is to do, or None to start TurboHUD: no command and none
    running, or --move with none running."""
    from turbohud import control

    send = send or control.send
    command = command_of(args)
    if command is None:
        # A plain start (or --move) while TurboHUD runs: move mode there, no second copy.
        if send('ping') != 'ok':
            return None
        send('move')
        print('TurboHUD is already running: switched it to move mode (quit it with --quit).')
        return 0
    answer = send(command)
    if answer is None:
        print('TurboHUD is not running.', file=sys.stderr)
        return 1
    if answer != 'ok':
        print(f'TurboHUD: {answer}', file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    code = tell_running(args)
    if code is not None:
        return code
    try:
        import PySide6  # noqa: F401 - only checks that Qt is there
    except ImportError:
        print('TurboHUD needs PySide6. Start it with run_turbohud.sh (macOS, Linux) or', file=sys.stderr)
        print('run_turbohud.cmd (Windows), which set it up first.', file=sys.stderr)
        return 2
    folder = settings_dir()
    setup_log(folder)
    return run(args, folder)
