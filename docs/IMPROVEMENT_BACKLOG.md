# Improvement backlog

Open items, most valuable first. Finished items move to `docs/PROGRESS.md`.

## 1. TurboHUD and the probes on Windows
Over TSU on Windows, in windowed, Fullscreen and Fullscreen Exclusive: the built app
(`TurboHUD.exe` from the Windows build of `.github/workflows/build.yml`), the Qt probe
(`experiments/run_qt_overlay_probe.cmd`) and the original probe. Add the results to
`experiments/README.md`. Check the shortcuts especially: the Windows hotkey code has only
run on a build machine. Expected: windowed and Fullscreen work; Exclusive may not, and an
overlay that injects into the game is out of scope.

## 2. More HUD data: fuel and speed, then Windows and macOS
Lap times are live on Linux (from TSU's memory, through the memory probe). Next: fuel
(left, per lap, laps it lasts) and speed, found the same way. Windows and macOS still
show the session clock: reading memory there needs its own permission route. Later,
with an event to join: the lap data as a guest on someone else's server.

## 3. Customising the look in the app
A small settings window (from the tray menu) for the theme's colours and scale, instead
of editing `settings.json` by hand.

## 4. Linux: shortcuts, AppImage, other Wayland desktops
On top of the game on Hyprland is done (2026-11-01: runtime requests for TurboHUD's own
window; move mode no longer ends when the mouse moves there). Still to check by hand:
over TSU in a race, and that clicks go through while locked. Other Wayland desktops
(KDE, GNOME) still ignore Qt's on-top hint: the layer-shell extension (KDE, Sway; not
GNOME) would need a library outside PySide6.

Shortcuts: Linux has none yet (Ctrl+Shift+L and Ctrl+Shift+Q do nothing there), and on
Omarchy it was not clear how to switch move mode or quit. Options: X11 key grabs under
XWayland; on Wayland, the desktop's own key bindings starting a command such as
`TurboHUD --toggle` that tells the running TurboHUD what to do (for Hyprland, a `bind`
line in `hyprland.conf`), or the GlobalShortcuts portal where the desktop has it. Until
then, say clearly on screen how to unlock and quit without shortcuts.
Also: an AppImage instead of the `.tar.gz`.

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
