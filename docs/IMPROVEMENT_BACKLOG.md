# Improvement backlog

Open items, most valuable first. Finished items move to `docs/PROGRESS.md`.

## 1. Overlay probe on Windows
Run `experiments/overlay_probe.py` over TSU on Windows in windowed, Fullscreen and
Fullscreen Exclusive, and add the results to `experiments/README.md`. Expected: windowed
and Fullscreen work; Exclusive may not, and an overlay that injects into the game is out
of scope.

## 2. Choose the stack and entry point
Depends on 1. The Mac overlay must be a native macOS window outside CrossOver (done:
`experiments/mac_overlay_probe.py` works over TSU's Fullscreen). Decide how the overlay
window is made on each system, and how the shared part (game files, HUD logic) talks to
it.

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
