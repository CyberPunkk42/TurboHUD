"""Starting TurboHUD: settings, log, the overlay window, shortcuts and the tray icon."""

import argparse
import logging
import os
import shutil
import signal
import sys
import threading
import time
from dataclasses import replace
from functools import partial
from pathlib import Path

from turbohud import __version__
from turbohud.core.hud import (
    CLOCK_SECTIONS,
    RACE_SECTIONS,
    common_font,
    default_tint,
    font_of_box,
    is_text_section,
    more_lap_rows_place,
    sector_bar_place,
    tight_place,
)
from turbohud.core.settings import (
    LAP_COLUMNS,
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

FRAME_MS = 50  # redraw interval, also what checks a race for a late read (hud.FramePacer)
MIN_SECTION = 20  # pixels: the smallest a section gets from Smaller in the settings
PLACEMENT_EVERY = 0.2  # seconds between position checks in move mode
ICON = 'tsu_turbo_hud_00.png'  # in assets/, also the bundled app's icon
# The settings window's switches for the lap times' columns (LAP_COLUMNS): (column, label, tooltip)
LAP_COLUMN_OPTIONS = (
    ('flag', 'Lap times: flag', "Each driver's country flag before the name"),
    ('lap', 'Lap times: lap number', 'The lap each driver is on (L3)'),
    (
        'tyre',
        'Lap times: tire compound',
        (
            "Each driver's tire compound, as in F1 (S red, M yellow, H white; a blue W where the track's"
            ' name has (WET), (RW), (QW) or (W))'
        ),
    ),
    ('best', 'Lap times: best lap', "Each driver's best lap"),
    ('current', 'Lap times: last lap', "Each driver's last lap, or CUT or PIT"),
)
log = logging.getLogger('turbohud')


def upgrade_layout(settings, path, ink, measure=None):
    """The settings with sections saved in an older layout converted, once, and written
    back; the file as it was stays beside it. `ink` is turbohud.hud.painter.text_ink and
    `measure` its text_width (a rough one where not given)."""
    measure = measure or (lambda text, size: len(text) * size * 0.6)
    version = settings.layout_version
    if version >= LAYOUT_VERSION:
        return settings
    known = {section.name: section for section in (*RACE_SECTIONS, *CLOCK_SECTIONS)}
    scale = settings.theme.scale

    def converted(sections):
        places = {}
        for name, place in sections.items():
            if name in known:
                box = (place.x, place.y, place.width, place.height)
                if version < 2:
                    box = tight_place(known[name], box, scale, ink)
                if version < 3:
                    box = more_lap_rows_place(known[name], box, scale, ink)
                if version < 5:
                    box = sector_bar_place(known[name], box, scale, ink)
                x, y, width, height = box
                place = replace(place, x=x, y=y, width=width, height=height)
                if version < 4 and known[name].drawing == 'map':
                    place = replace(place, tint=True)  # its dark square, always there before
            places[name] = place
        return places

    sections = converted(settings.sections)
    presets = {number: converted(kept) for number, kept in settings.presets.items()}
    font_size = settings.font_size
    if version < 6:
        # Text sizes: each text section keeps the size its box drew it at; the size most of
        # them have becomes the global one, which those follow; the others keep their own.
        def font(name, place):
            return font_of_box(
                known[name], (place.x, place.y, place.width, place.height), scale, measure, ink
            )

        def text(places):
            return {n: p for n, p in places.items() if n in known and is_text_section(known[n])}

        font_size = common_font([font(n, p) for n, p in text(sections).items()])

        def with_fonts(places):
            fonts = {n: font(n, p) for n, p in text(places).items()}
            return {
                n: replace(p, font=fonts[n] if fonts.get(n, font_size) != font_size else None)
                for n, p in places.items()
            }

        sections = with_fonts(sections)
        presets = {number: with_fonts(kept) for number, kept in presets.items()}
    settings = replace(
        settings, sections=sections, presets=presets, font_size=font_size, layout_version=LAYOUT_VERSION
    )
    if settings.sections or settings.presets:
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


def one_window_wanted(native, environ=os.environ):
    """Whether the sections are drawn in one window per screen while locked: where the
    platform's Native says it works (the Mac), unless TURBOHUD_ONE_WINDOW=0 turns it off."""
    return bool(getattr(native, 'one_window', False)) and environ.get('TURBOHUD_ONE_WINDOW', '1') != '0'


def taken_note(lock_keys, lock_key='Ctrl+Shift+L'):
    """What the tooltip and the log say where another program has Ctrl+Shift+L (AMD Software
    does) and the second key works instead; None where Ctrl+Shift+L works or neither does."""
    if not lock_keys or lock_key in lock_keys:
        return None
    return f'{lock_key} is taken by another program (AMD Software?): {lock_keys[0]} switches move mode'


def tray_text(status, warning=None):
    """The tray icon's tooltip: what TurboHUD is doing, and a warning if there is one."""
    return f'TurboHUD - {status}' + (f'\n{warning}' if warning else '')


def start_live_race(platform=sys.platform):
    """Start reading TSU's race: on Linux through the memory probe (TSU started from Steam
    with the launch option), on the Mac through a reader in TSU's CrossOver bottle, on
    Windows through the Rust reader started beside TSU (or, where it is missing, read from
    TurboHUD itself in Python). None elsewhere, where the HUD keeps its session clock."""
    if platform == 'darwin':
        from turbohud.tsu.bottle import Bottle
        from turbohud.tsu.client import LiveRace

        bottle = Bottle()
        live = LiveRace(connect=bottle.connect, close=bottle.close, warning=lambda: bottle.warning)
        way = 'a reader in the CrossOver bottle'
    elif platform.startswith('linux'):
        from turbohud.tsu.client import LiveRace

        live = LiveRace()
        way = 'the memory probe'
    elif platform == 'win32':
        from turbohud.tsu.bottle import LocalReader, rust_reader
        from turbohud.tsu.client import LiveRace

        if rust_reader().exists():
            reader = LocalReader()
            live = LiveRace(connect=reader.connect, close=reader.close)
            way = 'the Rust reader'
        else:
            from turbohud.tsu import winmemory

            live = LiveRace(connect=winmemory.connect)
            way = 'TurboHUD itself (the Rust reader is missing: Python)'
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
    from PySide6.QtCore import QObject, Qt, QTimer, Signal
    from PySide6.QtGui import QAction, QGuiApplication, QIcon
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    from turbohud.core.flagstack import combined
    from turbohud.core.hud import (
        CLOCK_SECTIONS,
        FONT_SIZES,
        RACE_SECTIONS,
        FramePacer,
        FrameTimes,
        GroupMover,
        LayoutHistory,
        below,
        beside,
        centred,
        drawing_place,
        first_launch,
        has_tint,
        local_time_rows,
        main_screen,
        panel_place,
        screen_of,
        session_rows,
        text_box,
    )
    from turbohud.hud.painter import text_ink, text_width, use_game_flags
    from turbohud.overlay import (
        HOTKEY_LOCK,
        HOTKEY_LOCK_BACKUP,
        HOTKEY_PRESETS,
        HOTKEY_QUIT,
        LOCK_KEY,
        choose_platform,
        native_for,
    )
    from turbohud.overlay.settings_window import SettingsWindow
    from turbohud.overlay.window import HudCanvases, MovePanel, SectionWindow, window_flags

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
    track_map = None  # the live race's TrackMap, for Relearn
    if live is not None:
        from turbohud.core.race import (
            RACING,
            DeltaBar,
            RaceStarts,
            Radar,
            Retirements,
            ShortcutPenalties,
            Standings,
            YellowFlags,
            race_sections,
            status_text,
            with_local_time,
        )

        layout = RACE_SECTIONS
        if sys.platform.startswith('linux'):  # the Linux joystick interface
            from turbohud.tsu.controller import Pad, combined

            pad = Pad()
            pad.start()
        from turbohud.core.trackmap import TrackMap

        standings = Standings()
        radar = Radar()
        delta_bar = DeltaBar()
        yellow_flags = YellowFlags()
        shortcut_penalties = (
            ShortcutPenalties()
        )  # not `shortcuts`: that name holds whether the hotkeys are there
        track_map = TrackMap(settings.map_others, folder)  # learnt tracks beside the settings
        race_starts = RaceStarts()
        retirements = Retirements()

        def contents():
            snapshot = live.snapshot()
            if race_starts.started(snapshot, time.monotonic()) and not locked:
                log.info('a race began: locking')
                set_locked(True)  # move mode forgotten: the race is no time for it
            track_map.others = settings.map_others
            radar.within = settings.radar_seconds
            radar.cone = settings.radar_cone
            current = race_sections(
                snapshot,
                time.monotonic(),
                settings.speed_unit,
                standings,
                radar,
                track_map,
                settings.blue_seconds,
                delta_bar,
                settings.sector_bars,
                yellow_flags if settings.yellow_flags else None,
                settings.class_tags if settings.classes else (),
                shortcut_penalties,
                settings.clan_tags,
                settings.lap_columns,
                retirements,
            )
            if not settings.yellow_flags:
                yellow_flags.reset()  # turned on again, it starts afresh
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
    # TSU's own flags, read from the game in the background (a fraction of a second, or
    # nothing when they are kept from before); emoji flags until then.
    game_flags = []  # the folder, once the reading is over (None: none)

    def read_game_flags():
        from turbohud.tsu.gameflags import prepare_flags

        try:
            game_flags.append(prepare_flags(folder))
        except Exception:
            log.exception('flags: not read from the game')
            game_flags.append(None)

    threading.Thread(target=read_game_flags, name='game flags', daemon=True).start()
    flags_used = False
    screens = [screen.geometry().getRect() for screen in QGuiApplication.screens()]
    # Where TurboHUD's own windows (the panel, the settings) go: not under the menu bar or Dock.
    usable = [screen.availableGeometry().getRect() for screen in QGuiApplication.screens()]
    settings = upgrade_layout(settings, path, text_ink, text_width)
    windows = {section.name: SectionWindow(native, settings.theme, section) for section in layout}
    canvas = None
    if one_window_wanted(native):
        # While locked, every section in one window per screen: one window per section cost the
        # game frames (experiments/window_count_probe.py). Before the sections are first shown.
        canvas = HudCanvases(native, screens, list(windows.values()))
        for window in windows.values():
            window.canvas = canvas
        canvas.set_shown(True)
        log.info('locked: the sections in one window per screen (%d)', len(screens))
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
        if is_text_section(window.section):
            window.own_font = saved.font if saved else None
            window.font = window.own_font or settings.font_size
            window.section = replace(window.section, spacing=saved.spacing if saved else 1.0)
            window.text_resized.connect(lambda name: resized_by_hand(name))
            place = text_box(window.section, place, window.font, text_width, text_ink)
        place = fit_on_screens(place, screens)
        window.setGeometry(*place)
        window.backdrop = saved.tint if saved else default_tint(window.section, settings.backdrop)
        window.radar_cone = settings.radar_cone
        window.sector_bars = settings.sector_bars
        window.show_on_top()
        window.set_wanted(saved.visible if saved else True)
        window.group = saved.group if saved else ''
        window.text_centred = saved.text_centred if saved else False
        log.info('section %s at %s%s', name, place, '' if window.wanted else ' (hidden)')
    shortcuts = False
    panel = None  # made once the shortcuts are known
    locked = True

    def save():
        nonlocal settings
        places = {}
        for name, window in windows.items():
            places[name] = section_place(window, window.placement())
        settings = replace(settings, sections=places, backdrop=all_tinted())
        write_settings()

    def section_place(window, box):
        """A section's SectionPlace in `box` (x, y, width, height), with its options."""
        x, y, width, height = box
        return SectionPlace(
            x,
            y,
            width,
            height,
            window.wanted,
            window.group,
            window.text_centred,
            window.backdrop,
            getattr(window, 'own_font', None),
            window.section.spacing,
        )

    def all_tinted():
        return all(w.backdrop for w in windows.values() if has_tint(w.section))

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
        return panel_place((panel.width(), panel.height()), [w.placement() for w in shown], usable)

    def set_locked(value):
        nonlocal locked
        if value == locked:
            return
        locked = value
        for window in windows.values():
            window.set_locked(value)
        if canvas is not None:
            canvas.set_shown(value)  # locked: the canvas; move mode: the sections' own windows
        move_action.setChecked(not value)
        if value:
            panel.hide()
            native.give_focus_back()
            history.record(layout_state())
            save()
            log.info('locked')
        else:
            mover.known.clear()  # compare from where the sections are now
            mover.pending.clear()
            native.take_focus()
            history.resume(layout_state())
            panel.set_undo_available(history.can_undo(history.current))
            relearn_available()
            panel.show_at(*panel_spot())
            log.info('move mode')

    def set_mph(mph):
        nonlocal settings
        settings = replace(settings, speed_unit='mph' if mph else 'kmh')
        mph_action.setChecked(mph)
        show_option('mph', mph)
        save()
        log.info('speed in %s', settings.speed_unit)

    def set_backdrop(backdrop):
        """The tint on or off for every section that has one, the track map's square too."""
        for name, window in windows.items():
            if not has_tint(window.section):
                continue
            window.backdrop = backdrop
            panel.set_tint(name, backdrop)
            window.update()
        show_all_tinted()
        save()
        log.info('tint behind all sections %s', 'on' if backdrop else 'off')

    def show_all_tinted():
        backdrop_action.setChecked(all_tinted())
        show_option('backdrop', all_tinted())

    settings_window = None  # made when first opened (open_settings)

    def show_option(key, on):
        """An option changed: the settings window's tick box shows it, where it is open."""
        if settings_window is not None:
            settings_window.set_option(key, on)

    def options():
        """The settings window's options for the whole HUD: (key, label, on, tooltip)."""
        listed = [
            ('mph', 'Speed in mph', settings.speed_unit == 'mph', 'The speed in mph instead of km/h'),
            (
                'backdrop',
                'Light tint behind all sections',
                all_tinted(),
                'A light tint behind every section; each has its own Tint in the move-mode panel',
            ),
        ]
        if any(section.drawing == 'radar' for section in layout):
            listed.append(
                (
                    'radar_cone',
                    'Slipstream cones on the proximity radar',
                    settings.radar_cone,
                    'The slipstream behind each car ahead on the radar',
                )
            )
        if any(section.drawing == 'map' for section in layout):
            listed.append(
                (
                    'map_others',
                    'Other cars on the track map',
                    settings.map_others,
                    'Every other car as a faint grey dot',
                )
            )
        if any(section.sectors for section in layout):
            listed.append(
                (
                    'sector_bars',
                    'Sector bars below the last and best lap',
                    settings.sector_bars,
                    'One bar per stretch between checkpoints: purple, green or dark yellow',
                )
            )
        if any(section.name == 'yellowflag' for section in layout):
            listed.append(
                (
                    'yellow_flags',
                    'Yellow flags',
                    settings.yellow_flags,
                    (
                        'When another car is off the track, slow, stopped, spun or going the wrong way in your sector or the next:'
                        ' the Yellow flag section and a yellow ring on the track map'
                    ),
                )
            )
        if any(section.name == 'laptimes' for section in layout):
            listed.append(
                (
                    'classes',
                    'Classes in the lap times',
                    settings.classes,
                    (
                        'In a race with two or more classes, named by the drivers\' clan tags ([GT3], [LMP], ...):'
                        " the lap times by class, each below a line with its name, and each driver's class"
                        ' in its colour after the name'
                    ),
                )
            )
            listed.append(
                (
                    'clan_tags',
                    'Clan tags in the lap times',
                    settings.clan_tags,
                    (
                        "Each driver's clan tag in a column after the name (in a race with classes: for the"
                        ' drivers of no class)'
                    ),
                )
            )
            for column, label, tip in LAP_COLUMN_OPTIONS:
                listed.append((f'column_{column}', label, column in settings.lap_columns, tip))
        return listed

    def set_radar_cone(cone):
        nonlocal settings
        settings = replace(settings, radar_cone=cone)
        radar_cone_action.setChecked(cone)
        show_option('radar_cone', cone)
        for window in windows.values():
            window.radar_cone = cone
            if window.section.drawing == 'radar':
                window.update()
        save()
        log.info('slipstream cones on the radar %s', 'on' if cone else 'off')

    def set_sector_bars(shown):
        nonlocal settings
        settings = replace(settings, sector_bars=shown)
        sector_bars_action.setChecked(shown)
        show_option('sector_bars', shown)
        for window in windows.values():
            window.sector_bars = shown
            if window.section.sectors:
                window.update()
        save()
        log.info('sector bars %s', 'on' if shown else 'off')

    def set_yellow_flags(shown):
        nonlocal settings
        settings = replace(settings, yellow_flags=shown)
        yellow_flags_action.setChecked(shown)
        show_option('yellow_flags', shown)
        save()
        log.info('yellow flags %s', 'on' if shown else 'off')

    def set_classes(shown):
        nonlocal settings
        settings = replace(settings, classes=shown)
        classes_action.setChecked(shown)
        show_option('classes', shown)
        save()
        log.info('classes in the lap times %s', 'on' if shown else 'off')

    def set_clan_tags(shown):
        nonlocal settings
        settings = replace(settings, clan_tags=shown)
        clan_tags_action.setChecked(shown)
        show_option('clan_tags', shown)
        save()
        log.info('clan tags in the lap times %s', 'on' if shown else 'off')

    def set_lap_column(column, shown):
        """A lap times column (LAP_COLUMNS) on or off, from the settings window."""
        nonlocal settings
        kept = set(settings.lap_columns) | {column} if shown else set(settings.lap_columns) - {column}
        settings = replace(settings, lap_columns=tuple(c for c in LAP_COLUMNS if c in kept))
        show_option(f'column_{column}', shown)
        save()
        log.info('lap times column %s %s', column, 'on' if shown else 'off')

    def set_map_others(others):
        nonlocal settings
        settings = replace(settings, map_others=others)
        map_others_action.setChecked(others)
        show_option('map_others', others)
        save()
        log.info('other cars on the track map %s', 'on' if others else 'off')

    def relearn_track():
        """Forget the current track's map; the next clean lap learns it again."""
        if track_map is None or not track_map.relearn():
            log.info('relearn the track map: no track known yet')

    def relearn_available():
        available = track_map is not None and track_map.has_track
        relearn_action.setEnabled(available)
        panel.set_relearn_available(available)

    mover = GroupMover()
    group_moving = False  # a group followed a drag at the last look

    history = None  # made once the panel is there

    def layout_state():
        """The sections as they are now and the presets: what Undo goes back through."""
        found = placements()
        sections = {}
        for name, window in windows.items():
            sections[name] = section_place(window, found.get(name) or window.placement())
        return sections, settings.presets, settings.font_size

    def undoable(action):
        """A change from a button or a shortcut: one step for Undo. A drag it comes right
        after counts as a step of its own."""

        def run(*arguments):
            history.record(layout_state())
            action(*arguments)
            state = layout_state()
            history.record(state)
            panel.set_undo_available(history.can_undo(state))

        return run

    @undoable
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

    def flags_combined(current):
        """Locked, both flags out and placed to overlap: the blue flag as a frame on the
        yellow box instead of a bar of its own (turbohud.core.flagstack)."""
        yellow, blue = windows.get('yellowflag'), windows.get('blueflag')
        if not locked or yellow is None or blue is None:
            return False
        return combined(
            yellow.placement(),
            blue.placement(),
            yellow.wanted and bool(current.get('yellowflag')),
            blue.wanted and current.get('blue') is not None,
        )

    def move_window(window, place, settle):
        native_move = getattr(native, 'move_window', None)
        if native_move is not None:
            native_move(window, place, settle)
        else:
            window.setGeometry(*place)
        if window.on_canvas:
            window.update()  # a hidden window does not draw itself again: the canvas does

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

    set_backdrop = undoable(set_backdrop)

    @undoable
    def set_tint(name, tint):
        windows[name].backdrop = tint
        windows[name].update()
        show_all_tinted()
        save()
        log.info('section %s: tint %s', name, 'on' if tint else 'off')

    @undoable
    def set_text_centred(name, centred):
        windows[name].text_centred = centred
        windows[name].update()
        save()
        log.info('section %s: text %s', name, 'in the middle' if centred else 'at the left')

    @undoable
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

    def set_seconds(name, seconds):
        """When the blue flag or the proximity radar shows, from the settings window."""
        nonlocal settings
        settings = replace(settings, **{name: seconds})
        save()
        log.info('%s: %.1f s', name, seconds)

    def set_reads(reads):
        """How often a race is read, from the settings window."""
        nonlocal settings
        settings = replace(settings, reads_per_second=reads)
        save()
        apply_reads()

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

    @undoable
    def resize_all(factor):
        """Every section bigger or smaller by `factor`, from its top-left corner: the text
        sections by their text sizes, the drawings by their boxes."""
        nonlocal settings

        def stepped(font):
            moved = round(font * factor)
            moved = moved if moved != font else font + (1 if factor > 1 else -1)
            return min(max(moved, FONT_SIZES[0]), FONT_SIZES[1])

        settings = replace(settings, font_size=stepped(settings.font_size))
        for window in text_windows().values():
            window.own_font = stepped(window.own_font) if window.own_font else None
            window.font = window.own_font or settings.font_size
        resize_sections({name: fitted(window) for name, window in text_windows().items()})
        show_fonts()
        for name, window in windows.items():
            if is_text_section(window.section):
                continue
            x, y, width, height = window.placement()
            place = (x, y, max(MIN_SECTION, round(width * factor)), max(MIN_SECTION, round(height * factor)))
            move_window(window, place, settle=True)
            mover.known[name] = place  # TurboHUD resized it: not a drag
        save()
        log.info('all sections %s', 'bigger' if factor > 1 else 'smaller')

    def open_settings():
        nonlocal settings_window
        if settings_window is None:
            settings_window = SettingsWindow(
                native,
                window_flags(),
                settings.theme,
                settings.blue_seconds,
                settings.radar_seconds,
                settings.reads_per_second if live is not None else None,
                options(),
            )
            setters = {
                'mph': set_mph,
                'backdrop': set_backdrop,
                'radar_cone': set_radar_cone,
                'map_others': set_map_others,
                'sector_bars': set_sector_bars,
                'yellow_flags': set_yellow_flags,
                'classes': set_classes,
                'clan_tags': set_clan_tags,
                **{f'column_{c}': (lambda shown, c=c: set_lap_column(c, shown)) for c in LAP_COLUMNS},
            }
            settings_window.option_changed.connect(lambda key, on: setters[key](on))
            settings_window.reads_changed.connect(set_reads)
            settings_window.theme_changed.connect(set_theme)
            settings_window.blue_seconds_changed.connect(lambda seconds: set_seconds('blue_seconds', seconds))
            settings_window.radar_seconds_changed.connect(
                lambda seconds: set_seconds('radar_seconds', seconds)
            )
            settings_window.resize_requested.connect(resize_all)
        if not settings_window.isVisible():
            # Beside the panel where it is (it may have been dragged), and wholly on its screen.
            anchor = panel.geometry().getRect()
            size = (settings_window.width(), settings_window.height())
            screen = screen_of(anchor, usable) or anchor
            settings_window.show_at(*beside(size, anchor, screen))

    @undoable
    def set_wanted(name, wanted):
        windows[name].set_wanted(wanted)
        log.info('section %s %s', name, 'shown' if wanted else 'hidden')

    @undoable
    def set_all_wanted(wanted):
        """Select all or Deselect all in the panel: every section, one step for Undo."""
        for window in windows.values():
            window.set_wanted(wanted)
        log.info('every section %s', 'shown' if wanted else 'hidden')

    @undoable
    def match_group(group):
        """The group's text sections get the same text size and width (the panel's Match).
        The settings take these places, not what the desktop says yet (see load_preset)."""
        members = [w for w in windows.values() if w.group == group and is_text_section(w.section)]
        if len(members) < 2:
            return
        font = max(window.font for window in members)
        for window in members:
            window.own_font = None if font == settings.font_size else font
            window.font = font
        boxes = {
            window.section.name: text_box(
                window.section, tuple(window.placement()), font, text_width, text_ink, keep_width=False
            )
            for window in members
        }
        widest = max(box[2] for box in boxes.values())
        resize_sections({name: (x, y, widest, height) for name, (x, y, _w, height) in boxes.items()})
        show_fonts()
        log.info('group %s: text size %d px, one width', group, font)

    def resize_sections(boxes):
        """Put sections in `boxes` {name: (x, y, width, height)}, resized by TurboHUD (Match,
        a text size); the settings take these places, not what the desktop says yet."""
        nonlocal settings
        until = time.monotonic() + 1.0
        places = dict(settings.sections)
        for name, box in boxes.items():
            window = windows[name]
            move_window(window, box, settle=True)
            window.update()
            mover.known[name] = box  # TurboHUD resized it: not a drag
            mover.pending[name] = (box, until)
            places[name] = section_place(window, box)
        settings = replace(settings, sections=places)
        write_settings()

    def fitted(window, keep_width=False):
        """A text section's box at its text size, where it is now."""
        return text_box(
            window.section, tuple(window.placement()), window.font, text_width, text_ink, keep_width
        )

    def text_windows():
        return {name: w for name, w in windows.items() if is_text_section(w.section)}

    @undoable
    def set_own_font(name, font):
        """A section's own text size from the move-mode panel, 0 for the global one (asked
        for by the user on 2026-11-13)."""
        window = windows[name]
        window.own_font = font or None
        window.font = window.own_font or settings.font_size
        resize_sections({name: fitted(window)})
        log.info('section %s: text size %s', name, f'{font} px' if font else 'global')

    @undoable
    def set_global_font(font):
        """The global text size, for every text section without its own."""
        nonlocal settings
        settings = replace(settings, font_size=font)
        following = {n: w for n, w in text_windows().items() if w.own_font is None}
        for window in following.values():
            window.font = font
        resize_sections({name: fitted(window) for name, window in following.items()})
        log.info('global text size %d px', font)

    @undoable
    def all_global():
        """Every text section follows the global text size."""
        for window in text_windows().values():
            window.own_font = None
            window.font = settings.font_size
        resize_sections({name: fitted(window) for name, window in text_windows().items()})
        show_fonts()
        log.info('every section: the global text size')

    def show_fonts():
        if panel is None:
            return
        panel.set_global_font(settings.font_size)
        for name, window in text_windows().items():
            panel.set_font_size(name, window.own_font)
            panel.set_spacing(name, window.section.spacing)

    @undoable
    def set_spacing(name, percent):
        """A section's line spacing from the move-mode panel (asked for by the user on 2026-11-13)."""
        window = windows[name]
        window.section = replace(window.section, spacing=percent / 100)
        resize_sections({name: fitted(window, keep_width=True)})
        log.info('section %s: line spacing %d%%', name, percent)

    def resized_by_hand(name):
        """A text section dragged at its edge: its text size or width is kept (Undo takes the
        drag as a step of its own, as any drag)."""
        window = windows[name]
        saved = settings.sections.get(name)
        if window.own_font == settings.font_size and saved is not None and saved.font is None:
            window.own_font = None  # dragged back to the global size: it follows it again
        save()
        show_fonts()
        log.info('section %s resized by hand: text size %s', name, window.own_font or 'global')

    def keep_text_boxes(found, now):
        """Move mode: a text section's box follows its text, so one the desktop resized
        (Hyprland lets one) goes back to its height, and to its width where it got narrower."""
        for name, window in text_windows().items():
            box = found.get(name)
            pending = mover.pending.get(name)
            if box is None or (pending is not None and now < pending[1]):
                continue
            right = text_box(window.section, box, window.font, text_width, text_ink)
            off = max(abs(a - b) for a, b in zip(box[2:], right[2:]))
            # Once per size: a desktop that keeps a box a pixel or two off is left alone.
            if off > 1 and refits.get(name) != tuple(box[2:]):
                refits[name] = tuple(box[2:])
                resize_sections({name: right})

    refits = {}  # section name -> the size keep_text_boxes last put back

    @undoable
    def save_preset(number):
        """Keep the layout as it is now in a preset, and in the settings as well."""
        nonlocal settings
        save()
        presets = {**settings.presets, number: {name: settings.sections[name] for name in windows}}
        settings = replace(settings, presets=presets)
        write_settings()
        panel.set_presets_saved(settings.presets)
        log.info('preset %d saved', number)

    @undoable
    def delete_preset(number):
        nonlocal settings
        presets = {kept: places for kept, places in settings.presets.items() if kept != number}
        settings = replace(settings, presets=presets)
        write_settings()
        panel.set_presets_saved(presets)
        log.info('preset %d deleted', number)

    @undoable
    def load_preset(number):
        """Put every section as the preset has it. What the desktop reports may lag behind
        the move (Wayland), so the settings take the preset's places, not what it says."""
        nonlocal settings
        places = preset_places(settings.presets.get(number, {}), windows, screens)
        if not places:
            log.info('preset %d is empty', number)
            return
        apply_places(places)
        settings = replace(settings, sections={**settings.sections, **places})
        write_settings()
        log.info('preset %d loaded', number)

    def apply_places(places):
        """Put sections as `places` {name: SectionPlace} has them, moved by TurboHUD: their
        groups stay where they are."""
        until = time.monotonic() + 1.0
        for name, place in places.items():
            window = windows[name]
            box = (place.x, place.y, place.width, place.height)
            move_window(window, box, settle=True)
            mover.known[name] = box
            mover.pending[name] = (box, until)
            window.set_wanted(place.visible)
            window.group = place.group
            window.text_centred = place.text_centred
            window.backdrop = place.tint
            if is_text_section(window.section):
                window.own_font = place.font
                window.font = place.font or settings.font_size
                window.section = replace(window.section, spacing=place.spacing)
                fixed = text_box(window.section, box, window.font, text_width, text_ink)
                if fixed != box:
                    move_window(window, fixed, settle=True)
                    mover.known[name] = fixed
                    mover.pending[name] = (fixed, until)
            window.update()
            panel.set_wanted(name, place.visible)
            panel.set_group(name, place.group)
            panel.set_text_centred(name, place.text_centred)
            panel.set_tint(name, place.tint)
        show_all_tinted()

    def undo():
        """Back one change. What the desktop reports may lag behind the move (see
        load_preset), so the settings take the earlier places, not what it says."""
        nonlocal settings
        previous = history.undo(layout_state())
        if previous is None:
            return
        sections, presets, font_size = previous
        settings = replace(settings, font_size=font_size)
        apply_places(sections)
        show_fonts()
        settings = replace(settings, sections={**settings.sections, **sections}, presets=presets)
        write_settings()
        panel.set_presets_saved(presets)
        panel.set_undo_available(history.can_undo(previous))
        log.info('undone; %d more to go back', len(history.past))

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
    backdrop_action = QAction('Light tint behind all sections', menu, checkable=True)
    backdrop_action.setChecked(settings.backdrop)
    backdrop_action.triggered.connect(lambda checked: set_backdrop(checked))
    menu.addAction(backdrop_action)
    radar_cone_action = QAction('Slipstream cones on the proximity radar', menu, checkable=True)
    radar_cone_action.setChecked(settings.radar_cone)
    radar_cone_action.triggered.connect(lambda checked: set_radar_cone(checked))
    if any(section.drawing == 'radar' for section in layout):
        menu.addAction(radar_cone_action)
    sector_bars_action = QAction('Sector bars below the last and best lap', menu, checkable=True)
    sector_bars_action.setChecked(settings.sector_bars)
    sector_bars_action.triggered.connect(lambda checked: set_sector_bars(checked))
    if any(section.sectors for section in layout):
        menu.addAction(sector_bars_action)
    yellow_flags_action = QAction('Yellow flags', menu, checkable=True)
    yellow_flags_action.setChecked(settings.yellow_flags)
    yellow_flags_action.triggered.connect(lambda checked: set_yellow_flags(checked))
    if any(section.name == 'yellowflag' for section in layout):
        menu.addAction(yellow_flags_action)
    classes_action = QAction('Classes in the lap times', menu, checkable=True)
    classes_action.setChecked(settings.classes)
    classes_action.triggered.connect(lambda checked: set_classes(checked))
    clan_tags_action = QAction('Clan tags in the lap times', menu, checkable=True)
    clan_tags_action.setChecked(settings.clan_tags)
    clan_tags_action.triggered.connect(lambda checked: set_clan_tags(checked))
    if any(section.name == 'laptimes' for section in layout):
        menu.addAction(classes_action)
        menu.addAction(clan_tags_action)
    map_others_action = QAction('Other cars on the track map', menu, checkable=True)
    map_others_action.setChecked(settings.map_others)
    map_others_action.triggered.connect(lambda checked: set_map_others(checked))
    if any(section.drawing == 'map' for section in layout):
        menu.addAction(map_others_action)
    relearn_action = QAction('Relearn this track\'s map', menu)
    relearn_action.setToolTip('Forget the map of the track being raced; the next clean lap draws it again')
    relearn_action.triggered.connect(lambda: relearn_track())
    if any(section.drawing == 'map' for section in layout):
        menu.addAction(relearn_action)
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
        if number in (HOTKEY_LOCK, HOTKEY_LOCK_BACKUP):
            log.info('%s pressed', LOCK_KEY if number == HOTKEY_LOCK else 'the second move-mode key')
            QTimer.singleShot(0, lambda: set_locked(not locked))
        elif number == HOTKEY_QUIT:
            log.info('Ctrl+Shift+Q pressed')
            QTimer.singleShot(0, app.quit)
        elif number in HOTKEY_PRESETS:
            preset = HOTKEY_PRESETS[number]
            log.info('Ctrl+Shift+%d pressed', preset)
            QTimer.singleShot(0, lambda: load_preset(preset))

    shortcuts = native.register_hotkeys(on_hotkey)
    lock_keys = getattr(native, 'lock_keys', [])
    log.info(
        'shortcuts: %s' % (', '.join([*lock_keys, 'Ctrl+Shift+Q']) if shortcuts else 'none, system-wide')
    )
    shortcut_note = taken_note(lock_keys)
    if shortcut_note:
        log.warning(shortcut_note)
        tray.setToolTip(tray_text('starting', shortcut_note))

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
        commands,
        tuple(settings.presets),
        lock_keys[0] if lock_keys else LOCK_KEY,
    )
    panel.preset_save_requested.connect(save_preset)
    panel.preset_load_requested.connect(load_preset)
    panel.preset_delete_requested.connect(delete_preset)
    panel.match_requested.connect(match_group)
    panel.font_size_changed.connect(set_own_font)
    panel.global_font_changed.connect(set_global_font)
    panel.all_global_requested.connect(all_global)
    panel.spacing_changed.connect(set_spacing)
    panel.undo_requested.connect(undo)
    panel.relearn_requested.connect(relearn_track)
    menu.aboutToShow.connect(relearn_available)
    panel.text_centred_changed.connect(set_text_centred)
    panel.tint_changed.connect(set_tint)
    panel.settings_requested.connect(open_settings)
    for name, window in windows.items():
        panel.set_wanted(name, window.wanted)
    panel.lock_requested.connect(lambda: set_locked(True))
    panel.quit_requested.connect(app.quit)
    panel.wanted_changed.connect(set_wanted)
    panel.all_wanted.connect(set_all_wanted)
    panel.group_changed.connect(set_group)
    panel.align_requested.connect(align)
    show_fonts()
    for name, window in windows.items():
        panel.set_group(name, window.group)
        panel.set_text_centred(name, window.text_centred)
        panel.set_tint(name, window.backdrop)

    history = LayoutHistory(layout_state())
    # Move mode ends only by its shortcut or the panel's Lock (asked for by the user on
    # 2026-11-13): a click elsewhere, on the game or the desktop, no longer locks it.

    last_seen = 0.0

    shown_status = None

    frames = FrameTimes(time.monotonic, log.info)
    pacer = FramePacer()
    drawn_before = 0.0

    def apply_reads():
        reads = settings.reads_per_second
        pacer.most = 2 / reads
        if live is not None:
            live.read_interval = 1 / reads
            log.info('race reads: at most %d a second', reads)

    apply_reads()

    def tick():
        nonlocal last_seen, shown_status, drawn_before, flags_used
        if game_flags and not flags_used:
            flags_used = True
            if game_flags[0] is not None:
                use_game_flags(game_flags[0])
                for window in windows.values():
                    window.update()  # drawn again with the game's flags
        racing, fresh = False, True
        if live is not None:
            snapshot = live.snapshot()
            racing = snapshot.status == RACING
            due, fresh = pacer.due(snapshot.read_at, racing, time.monotonic())
            if not due:
                return
        began = time.perf_counter()
        current = contents()
        if not locked:
            relearn_available()  # a race may start or end while the panel is open
        together = flags_combined(current)
        if live is not None:
            text = tray_text(status_text(live.snapshot()), live.warning() or shortcut_note)
            if text != shown_status:
                tray.setToolTip(text)
                shown_status = text
        for name, window in windows.items():
            blue = current.get('blue')
            if name == 'blueflag' and together:
                blue = None  # shown as the yellow box's frame instead
            elif name == 'yellowflag' and not together:
                blue = None  # no frame
            if window.show_content(
                current.get(name, []),
                current.get('pedals'),
                blue,
                current.get('radar'),
                current.get('trackmap'),
                current.get('levels', {}).get(name),
                current.get('deltaview'),
            ):
                window.update()  # only what changed: drawing every section each frame stutters
        if racing:
            frames.frame(time.perf_counter() - began, SectionWindow.drawing_time - drawn_before, fresh)
        else:
            frames.flush()
        drawn_before = SectionWindow.drawing_time
        if not locked and time.monotonic() - last_seen >= PLACEMENT_EVERY:
            # In move mode, note where the sections are: on Wayland only the desktop
            # knows, and it may no longer say once TurboHUD is quitting. Grouped sections
            # follow the one being dragged, and a drag that ends is one step for Undo.
            last_seen = time.monotonic()
            if any(w.group for w in windows.values()):
                follow_groups(last_seen)
            state = layout_state()
            keep_text_boxes({n: (p.x, p.y, p.width, p.height) for n, p in state[0].items()}, last_seen)
            history.look(state, last_seen)
            panel.set_undo_available(history.can_undo(state))
        if args.seconds is not None and time.monotonic() - started >= args.seconds:
            log.info('time is up')
            app.quit()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(FRAME_MS)  # also lets Python see Ctrl+C between frames
    if live is not None:

        class Reads(QObject):
            arrived = Signal()

        reads = Reads()
        reads.arrived.connect(tick, Qt.QueuedConnection)  # from the reading thread to this one
        live.on_read = reads.arrived.emit
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    if args.move or not shortcuts and not tray.isVisible():
        set_locked(False)  # without shortcuts or tray, locked could not be undone
    app.exec()
    if not locked:
        set_locked(True)  # saves and hands the focus back
    else:
        save()
    if live is not None:
        live.on_read = None
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
