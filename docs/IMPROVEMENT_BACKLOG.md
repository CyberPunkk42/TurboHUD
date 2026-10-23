# Improvement backlog

Open items, most valuable first. Finished items move to `docs/PROGRESS.md`.

## 1. Overlay probes on Windows
Run `experiments/qt_overlay_probe.py` (the chosen stack; `run_qt_overlay_probe.cmd`) and
`experiments/overlay_probe.py` over TSU on Windows in windowed, Fullscreen and
Fullscreen Exclusive, and add the results to `experiments/README.md`. Check the Qt
probe's shortcuts especially: its Windows hotkey code has not run yet. Expected: windowed
and Fullscreen work; Exclusive may not, and an overlay that injects into the game is out
of scope.

## 2. App skeleton and bundled builds
The structure in `docs/STACK.md`: `launch_turbokit.py`, `turbokit/core/`, `hud/` and
`overlay/`, a development environment with PySide6 kept out of Git, and PyInstaller
builds for Windows, macOS and Linux on GitHub Actions. Measure the bundle sizes.

## Design notes for the real overlay
- Move mode is a short, deliberate step: while the overlay takes the mouse, the game gets
  no mouse input under it. On the Mac, end move mode as soon as the game becomes active
  again; playing while the overlay is the active app upsets the game's mouse handling.
- Set the pointer explicitly in move mode; TSU hides the system pointer at times.
- Locked: hide the background completely and show only the content, with a shadow for
  readability.
- Keyboard shortcuts must work on Mac keyboards (no Alt). On the Mac, Carbon's system-wide
  hotkeys work while TSU has focus and need no permission.
- On the Mac, put the overlay at a window level above 26 (TSU's in Fullscreen) and allow
  it on every Space; the probe uses the screen-saver level (1000).
