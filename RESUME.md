# TurboKit: where things stand

## Current state
- No app code yet. Stack and entry point are still open.
- The overlay probe (`experiments/overlay_probe.py`, see `experiments/README.md`) answered
  whether a see-through, click-through, always-on-top window can sit over TSU:
  - macOS (CrossOver): yes when TSU runs windowed or with Fullscreen off; never with TSU's
    Fullscreen setting on. A Fullscreen-capable Mac overlay must be a native macOS window,
    outside the bottle.
  - Windows: not tested yet.
- Overlay behaviour settled by the probe: a move mode (tinted, draggable, resizable, with
  Lock and Close buttons) and a locked mode (background hidden, click-through, only the
  content shows). Ctrl+Shift+L toggles, Ctrl+Shift+Q quits; no Alt, which Mac keyboards
  lack. Position and size are remembered.
- Tests: `/opt/homebrew/bin/python3.13 -B -m unittest discover -s tests` (Windows:
  `py -3 -B -m unittest discover -s tests`).

## Next steps
See `docs/IMPROVEMENT_BACKLOG.md`. In short:
1. Run the probe on Windows over TSU in windowed, Fullscreen and Fullscreen Exclusive.
2. Try a native macOS overlay window (above full-screen apps) over TSU in Fullscreen.
3. Decide the stack from those results.

## Recent changes
- 2026-10-23: Overlay probe. A test overlay for TSU, with a launcher that runs it in the
  CrossOver bottle using a portable Windows Python. On the Mac it works over TSU except in
  TSU's Fullscreen mode, where no window from inside CrossOver can show.
