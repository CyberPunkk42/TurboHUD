# Choosing TurboHUD's stack

Status: **decided: B, Python with Qt (PySide6), shipped as a ready-to-run app for each
system.** Chosen 2026-10-23; merging the pull request that adds this file confirms it.

## What the stack has to do

From the two overlay probes (`experiments/README.md`) and the user's priorities:
- **Looks good and is easy to read over the game,** with HUD graphics the player can
  customise: colours, fonts, size, opacity, layout.
- **Installs on Windows, macOS and Linux with nothing else to install first.** No Python,
  no packages, no command line for the player.
- **The overlay window is different on each system.**
  - Windows: an always-on-top, click-through window. Tested on the Mac inside CrossOver
    so far; the test on Windows itself is backlog item 1.
  - Mac: a native macOS window outside CrossOver, at a window level above 26 (TSU's in
    Fullscreen). A window from inside the bottle never shows over TSU's Fullscreen.
- **The same behaviour everywhere:** move mode (tinted, draggable, resizable) and locked
  mode (background hidden, click-through), the shortcuts Ctrl+Shift+L and Ctrl+Shift+Q
  without Alt, remembered position and size.
- **Everything else can be shared:** finding TSU's data folder (on the Mac inside the
  bottle; on Linux TSU has a native build with its data in
  `~/.config/unity3d/Turbo Sliders/Unlimited/<SteamID>/`), reading the game's files, the
  HUD's maths, and what the HUD shows where.
- **Linux.** Written when Linux was planned for later and thought to run TSU through
  Proton; TSU has a native Linux build, and Linux is now where TurboHUD shows live race
  data (2026-11-03). Whether an overlay can sit on top depends on the desktop more than
  on the stack:
  - X11, and X11 apps under Wayland (XWayland): an always-on-top, click-through window
    is possible. Whether it shows over a full-screen game needs testing, as on the Mac.
  - Native Wayland: an ordinary app can neither stay on top nor place itself. Only the
    layer-shell extension allows it (KDE, Sway, Hyprland; not GNOME). System-wide
    shortcuts need the GlobalShortcuts portal. As built: on Hyprland TurboHUD asks
    Hyprland at runtime to float and pin its own windows; on other Wayland desktops it
    runs through XWayland; instead of shortcuts, `run_turbohud.sh --toggle` and the
    other commands can be bound to a key in the desktop's own settings.
  - Steam Deck in Game Mode (gamescope): outside windows do not show over the game.

  These limits are the same for every option below.
- **Possibly per system later:** reading the player's controls (keyboard, gamepad), if a
  feature needs it. On the Mac, watching the keyboard from another app needs the Input
  Monitoring permission; gamepads probably do not.
- **Light while racing:** a few updates per second, no stutter in the game.

## Options

| | A. Python, standard library + ctypes | B. Python + Qt (PySide6) | C. Web UI (Electron or Tauri) | D. Native per system (C# + Swift) |
| --- | --- | --- | --- | --- |
| Overlay on Windows | Proven by the probe (inside CrossOver) | Qt flags for on-top, click-through and a transparent background | Built in | Native |
| Overlay over Mac Fullscreen | Proven by the probe | A few lines of ctypes on top of Qt (level above 3) | Built in (Electron's `screen-saver` level) | Native |
| Overlay on Linux | A third platform file (X11 through ctypes); untested | Qt on X11 and XWayland | Electron on X11 and XWayland; Tauri depends on WebKitGTK, whose transparency is less reliable | A third native app, or C# with Avalonia for Windows and Linux |
| Drawing the HUD | Each system's own drawing calls, written three times | Qt painting, smooth and the same everywhere | HTML and canvas, easiest | Native, written per system |
| Global shortcuts | ctypes per system | ctypes per system (Qt has none) | Built in | Native |
| Shared code | One codebase | One codebase | One codebase (JavaScript/TypeScript) | Two or three languages |
| Install for players | Python needed on Mac and Linux | Bundled app, nothing to install | Bundled app, nothing to install | Bundled app per system |
| Size | Small | About 60-150 MB per bundle | 100-200 MB (Electron) | Small |
| Main risk | Much hand-written drawing and window code | Bundle size; Qt on the Mac needs native help | A browser engine running beside the game | Every feature built two or three times |

## Why B

- **Best looks for the effort.** Qt draws smooth text, shadows, lines, shapes and images
  with transparency on all three systems, from one implementation. Themes the player can
  change (colours, fonts, size, opacity, which widgets show where) are ordinary settings.
  Qt Quick (QML) is there if the HUD later wants animations.
- **One language and one codebase,** the same as LiveryStudio: Python, unittest, Ruff.
- **Small native part.** Only what Qt lacks stays per system: the Mac window level above
  Fullscreen (from the Mac probe) and the global shortcuts (from both probes, plus X11 on
  Linux).
- **Lighter than C** while the game runs: no browser engine.
- **Far less work than D,** which would build every feature two or three times.

Costs accepted:
- Each download is larger, roughly 60-150 MB instead of a few MB.
- Releases need a build on each system (see below), instead of a plain source ZIP.
- TurboHUD no longer uses only the standard library. LiveryStudio keeps its own rule.

## How players install it

Each release is a ready-to-run app with Python and Qt inside, built by PyInstaller:
- **Windows:** a ZIP with `TurboHUD.exe`. Unpack and run.
- **macOS:** `TurboHUD.app` in a ZIP or disk image. Drag to Applications.
- **Linux:** a `.tar.gz` for now (an AppImage is planned, backlog item 3). Unpack and
  run.

PyInstaller builds only for the system it runs on, so each release is built locally
with `tools/build_app.py` on each system, from `main`. (A GitHub Actions workflow was
planned for this; it is kept in `.github/workflows/build.yml` for reference but no
longer runs, as nothing goes to GitHub.)

Without paid code signing, each system warns once on first start:
- Windows SmartScreen: **More info**, then **Run anyway**.
- macOS: the app is blocked first; allow it under **System Settings > Privacy &
  Security > Open Anyway**. An Apple Developer account (paid yearly) removes this.
- Linux: no warning.

## Suggested structure

Built on 2026-10-24; as of 2026-11-03:

```
launch_turbohud.py      start file; the bundles run the same code
run_turbohud.sh/.cmd    start from the source, setting up PySide6 in .buildtools/venv;
                        also --toggle, --move, --lock, --settings, --quit (Linux, macOS)
requirements.txt        PySide6, pinned; requirements-build.txt adds PyInstaller
turbohud/
  app.py                start-up: settings, log, section windows, tray menu, shortcuts,
                        commands, the live race
  control.py            the command socket (run_turbohud.sh --toggle and the rest)
  core/                 shared, no Qt
    settings.py         settings and theme, where they live on each system
    hud.py              the sections, their sizes, places and first-launch layout
    il2cpp.py           finds the game's classes and fields by name
    race.py             reads the race and works out what each section shows
    trackmap.py         the track map: the learnt track and which cars show
    flags.py            TSU's flags as country codes
  tsu/                  Linux: the game
    probe.py            the memory probe (started with TSU by the launch option)
    client.py           talks to the probe, reads the race in a background thread
    gamelog.py          TSU's log: whether an event runs
    controller.py       the gamepad's triggers
  hud/painter.py        Qt drawing of text, bars and flags
  overlay/
    window.py           the section windows (drawings: blue flag, radar, track map) and
                        the move-mode panel
    settings_window.py  colours and size
    windows.py          Win32: RegisterHotKey, focus hand-back
    macos.py            Cocoa: window level above Fullscreen, all Spaces; Carbon hotkeys
    linux.py            Linux: Hyprland or XWayland, no shortcuts
    hyprland.py         asks Hyprland to float, place and pin TurboHUD's own windows
experiments/            the probes that settled the design; tsu_memory_probe.py is what
                        the Steam launch option runs
tools/build_app.py      PyInstaller build, archive and smoke test for this system
tools/privacy_check.py  the pre-push hook that keeps personal data out of commits
tests/                  unit tests on any system
```

A tray icon (the menu bar on the Mac) offers Move mode, Settings…, the options and Quit;
on Linux, which has no shortcuts, the commands above can be bound to a key in the
desktop's own settings. First build sizes: Windows 40 MB ZIP, Mac 28 MB ZIP (75 MB
unpacked), Linux 74 MB `.tar.gz` (with Qt's X11 libraries packed in).

## Still to check
1. The overlay probe on Windows itself (backlog item 1), especially over Fullscreen
   Exclusive.
2. The Qt overlay probe (`experiments/qt_overlay_probe.py`) over TSU on Windows. On the
   Mac it works in Fullscreen and Fullscreen Exclusive (2026-10-24).
3. Linux on X11 and XWayland (KDE, GNOME). Hyprland on Wayland works (2026-11-01).
4. Reading the player's controls on the Mac from a background app, once a feature needs
   it.

## Decision
2026-10-23: **B, Python with Qt (PySide6)**, shipped as a bundled app for Windows,
macOS and Linux. Chosen for good-looking, customisable HUD graphics from one drawing
implementation, and an install that needs nothing else. C was the alternative for
styling, but runs a browser engine beside the game; A would mean writing the drawing
once per system and asking Mac and Linux players to install Python.
