# TurboKit: where things stand

## Current state
- Stack (`docs/STACK.md`): Python with Qt (PySide6), shipped as a bundled app for
  Windows, macOS and Linux, with small ctypes parts for what Qt lacks (Mac window level
  above Fullscreen, global shortcuts).
- App skeleton in `turbokit/` (see `README.md` and the structure in `docs/STACK.md`): the
  overlay with locked and move mode, Ctrl+Shift+L / Ctrl+Shift+Q, a tray icon, saved
  placement and theme. The HUD shows only a session clock so far. Start from the source
  with `run_turbokit.sh` / `run_turbokit.cmd`.
- Builds: `tools/build_app.py` (PyInstaller) makes a Windows ZIP, a Mac app ZIP and a
  Linux `.tar.gz`; `.github/workflows/build.yml` builds and smoke-tests all three on pull
  requests that touch the app, and drafts a GitHub release for a `v*` tag.
- The overlay probe (`experiments/overlay_probe.py`, see `experiments/README.md`) answered
  whether a see-through, click-through, always-on-top window can sit over TSU:
  - macOS (CrossOver): yes when TSU runs windowed or with Fullscreen off; never with TSU's
    Fullscreen setting on.
  - macOS (native, `experiments/mac_overlay_probe.py`): yes, also over TSU's Fullscreen.
    A plain Mac window at the screen-saver level, outside the bottle, needing no
    permission. So TurboKit's Mac overlay must be native, while reading the game's files
    and the HUD logic can be shared.
  - Windows: not tested yet.
  - Qt, the chosen stack (`experiments/qt_overlay_probe.py`): works over TSU on the Mac
    in Fullscreen, with and without Exclusive: crisp text, click-through, shortcuts,
    move mode, no stutter.
- Overlay behaviour settled by the probe: a move mode (tinted, draggable, resizable, with
  Lock and Close buttons) and a locked mode (background hidden, click-through, only the
  content shows). Ctrl+Shift+L toggles, Ctrl+Shift+Q quits; no Alt, which Mac keyboards
  lack. Position and size are remembered. Move mode ends by itself when the game becomes
  active again.
- Tests: `/opt/homebrew/bin/python3.13 -B -m unittest discover -s tests` (Windows:
  `py -3 -B -m unittest discover -s tests`).

## Next steps
See `docs/IMPROVEMENT_BACKLOG.md`. In short:
1. Test TurboKit and the probes on Windows over TSU in windowed, Fullscreen and
   Fullscreen Exclusive.
2. Move the move-mode hint so it no longer overlaps the Lock and Close buttons.
3. The first real HUD data (lap times, fuel estimate or minimap).
4. A settings window for the look; Linux shortcuts and AppImage.

## Recent changes
- 2026-10-24: App skeleton and bundled builds. `turbokit/` holds the overlay (locked and
  move mode, shortcuts, tray icon, saved placement and theme) with a session clock as the
  first HUD. `tools/build_app.py` builds a ready-to-run app with PyInstaller (Mac: 27 MB
  ZIP); GitHub Actions builds and smoke-tests Windows, macOS and Linux. `README.md`
  explains install, first start (step by step per system) and use.
- 2026-10-24: Qt overlay probe tested over TSU on the Mac, in Fullscreen with and
  without Fullscreen Exclusive: the HUD shows, text is crisp, clicks pass through,
  shortcuts and move mode work, and the game does not stutter. Qt is confirmed for the
  Mac overlay; Windows is next.
- 2026-10-23: Qt overlay probe (`experiments/qt_overlay_probe.py`) on the chosen stack:
  a test HUD (outlined text, clock, bar, small map) in a transparent, click-through Qt
  window with move mode and the shortcuts, raised above Fullscreen on the Mac through
  ctypes. Runners set up the pinned PySide6 in `.buildtools/qt-venv`. Starts on the Mac;
  not yet tested over TSU.
- 2026-10-23: Stack chosen (`docs/STACK.md`): Python with Qt (PySide6), shipped as a
  ready-to-run app for Windows, macOS and Linux, so players install nothing else. Chosen
  for good-looking, customisable HUD graphics drawn once for all systems. Linux limits
  (Wayland, Steam Deck) noted.
- 2026-10-23: Native Mac overlay probe (`experiments/mac_overlay_probe.py`). A plain Mac
  program outside CrossOver, at a window level above full-screen windows. It shows over
  TSU in Fullscreen, lets clicks through, and has the same shortcuts and move mode, with
  no permission needed. The Mac overlay for Fullscreen must therefore be native.
- 2026-10-23: Overlay probe. A test overlay for TSU, with a launcher that runs it in the
  CrossOver bottle using a portable Windows Python. On the Mac it works over TSU except in
  TSU's Fullscreen mode, where no window from inside CrossOver can show.
