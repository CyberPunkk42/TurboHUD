# Improvement backlog

Open items, most valuable first. Finished items move to `docs/PROGRESS.md`.

## 1. TurboKit and the probes on Windows
Over TSU on Windows, in windowed, Fullscreen and Fullscreen Exclusive: the built app
(`TurboKit.exe` from the Windows build of `.github/workflows/build.yml`), the Qt probe
(`experiments/run_qt_overlay_probe.cmd`) and the original probe. Add the results to
`experiments/README.md`. Check the shortcuts especially: the Windows hotkey code has only
run on a build machine. Expected: windowed and Fullscreen work; Exclusive may not, and an
overlay that injects into the game is out of scope.

## 2. Move-mode hint overlaps the buttons
In move mode, the hint ("Drag to move, resize at the corner...") is drawn over the Lock
and Close buttons. Put it at the bottom of the box, on its own line next to or above the
buttons, so it is easy to read and nothing overlaps; check it at the minimum size and at
larger theme scales.

## 3. First real HUD data
Pick the first feature (lap times, fuel estimate or minimap), find the game data it
needs, and show it in place of the session clock. Read the game's files only.

## 4. Customising the look in the app
A small settings window (from the tray menu) for the theme's colours and scale, instead
of editing `settings.json` by hand.

## 5. Linux: shortcuts and AppImage
System-wide shortcuts on X11, and an AppImage instead of the `.tar.gz`. Test on a Linux
desktop with TSU under Proton.

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
