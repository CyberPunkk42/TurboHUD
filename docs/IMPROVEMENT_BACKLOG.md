# Improvement backlog

Open items, most valuable first. Finished items move to `docs/PROGRESS.md`.

## 1. TurboKit and the probes on Windows
Over TSU on Windows, in windowed, Fullscreen and Fullscreen Exclusive: the built app
(`TurboKit.exe` from the Windows build of `.github/workflows/build.yml`), the Qt probe
(`experiments/run_qt_overlay_probe.cmd`) and the original probe. Add the results to
`experiments/README.md`. Check the shortcuts especially: the Windows hotkey code has only
run on a build machine. Expected: windowed and Fullscreen work; Exclusive may not, and an
overlay that injects into the game is out of scope.

## 2. First real HUD data
Pick the first feature (lap times, fuel estimate or minimap), find the game data it
needs, and show it in place of the session clock. Read the game's files only.

## 3. Customising the look in the app
A small settings window (from the tray menu) for the theme's colours and scale, instead
of editing `settings.json` by hand.

## 4. Linux: on top of the game, shortcuts and AppImage
Tested on Omarchy Linux (Hyprland, a Wayland desktop) on 2026-10-24: TurboKit runs, but
does not stay on top of TSU. Most likely Qt runs as a native Wayland app there, where
"stay on top" is ignored. Options, to try in this order:
- Start Qt through XWayland (`QT_QPA_PLATFORM=xcb`), where Qt's on-top hint works, and
  check over TSU windowed and fullscreen.
- Hyprland window rules for TurboKit (float, pin, no focus); document them for players.
- The layer-shell extension (Hyprland, KDE, Sway support it; GNOME does not), which puts
  a window above fullscreen ones; it needs a library outside PySide6.
Move mode ends at once: on Omarchy, choosing Move mode from the tray icon tints the box,
but the first mouse movement locks it again. Hyprland gives focus to the window under the
mouse, so moving the pointer off the box makes the game active, and TurboKit's auto-lock
(added for the Mac, where playing during move mode upset TSU's mouse handling) ends move
mode. Fix: on desktops where focus follows the mouse, lock only on a click into another
window, or not automatically at all; keep the Mac behaviour.

Shortcuts: Linux has none yet (Ctrl+Shift+L and Ctrl+Shift+Q do nothing there), and on
Omarchy it was not clear how to switch move mode or quit. Options: X11 key grabs under
XWayland; on Wayland, the desktop's own key bindings starting a command such as
`TurboKit --toggle` that tells the running TurboKit what to do (for Hyprland, a `bind`
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
