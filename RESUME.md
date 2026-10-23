# TurboKit: where things stand

## Current state
- No app code yet. Stack and entry point are still open.
- The overlay probe (`experiments/overlay_probe.py`, see `experiments/README.md`) answered
  whether a see-through, click-through, always-on-top window can sit over TSU:
  - macOS (CrossOver): yes when TSU runs windowed or with Fullscreen off; never with TSU's
    Fullscreen setting on.
  - macOS (native, `experiments/mac_overlay_probe.py`): yes, also over TSU's Fullscreen.
    A plain Mac window at the screen-saver level, outside the bottle, needing no
    permission. So TurboKit's Mac overlay must be native, while reading the game's files
    and the HUD logic can be shared.
  - Windows: not tested yet.
- Overlay behaviour settled by the probe: a move mode (tinted, draggable, resizable, with
  Lock and Close buttons) and a locked mode (background hidden, click-through, only the
  content shows). Ctrl+Shift+L toggles, Ctrl+Shift+Q quits; no Alt, which Mac keyboards
  lack. Position and size are remembered. Move mode ends by itself when the game becomes
  active again.
- Tests: `/opt/homebrew/bin/python3.13 -B -m unittest discover -s tests` (Windows:
  `py -3 -B -m unittest discover -s tests`).

## Next steps
See `docs/IMPROVEMENT_BACKLOG.md`. In short:
1. Run the probe on Windows over TSU in windowed, Fullscreen and Fullscreen Exclusive.
2. Decide the stack: a native overlay window on each system, and how the shared part
   talks to it.

## Recent changes
- 2026-10-23: Native Mac overlay probe (`experiments/mac_overlay_probe.py`). A plain Mac
  program outside CrossOver, at a window level above full-screen windows. It shows over
  TSU in Fullscreen, lets clicks through, and has the same shortcuts and move mode, with
  no permission needed. The Mac overlay for Fullscreen must therefore be native.
- 2026-10-23: Overlay probe. A test overlay for TSU, with a launcher that runs it in the
  CrossOver bottle using a portable Windows Python. On the Mac it works over TSU except in
  TSU's Fullscreen mode, where no window from inside CrossOver can show.
