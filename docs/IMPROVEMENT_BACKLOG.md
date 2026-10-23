# Improvement backlog

Open items, most valuable first. Finished items move to `docs/PROGRESS.md`.

## 1. Overlay probe on Windows
Run `experiments/overlay_probe.py` over TSU on Windows in windowed, Fullscreen and
Fullscreen Exclusive, and add the results to `experiments/README.md`. Expected: windowed
and Fullscreen work; Exclusive may not, and an overlay that injects into the game is out
of scope.

## 2. Native macOS overlay over TSU's Fullscreen
On the Mac, no window from inside CrossOver shows over TSU's Fullscreen mode. Try a native
macOS window at a level above full-screen apps (click-through, transparent background)
over TSU in Fullscreen. If it works, TurboKit's Mac overlay runs outside the bottle, while
reading the game's files and the HUD logic can stay shared.

## 3. Choose the stack and entry point
Depends on 1 and 2: how the overlay window is made on each system, and how the shared
part talks to it.

## Design notes for the real overlay
- Move mode is a short, deliberate step: while the overlay takes the mouse, the game gets
  no mouse input under it. Consider relocking by itself after a while.
- Set the pointer explicitly in move mode; TSU hides the system pointer at times.
- Locked: hide the background completely and show only the content, with a shadow for
  readability.
- Keyboard shortcuts must work on Mac keyboards (no Alt).
