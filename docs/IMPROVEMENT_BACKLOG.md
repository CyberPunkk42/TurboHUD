# Improvement backlog

Open items, most valuable first. Finished items move to `docs/PROGRESS.md`.

## 1. Windows: the overlay, then live data
Over TSU on Windows, in windowed, Fullscreen and Fullscreen Exclusive: the built app
(`tools/build_app.py`), the Qt probe (`experiments/run_qt_overlay_probe.cmd`) and the
original probe. Add the results to `experiments/README.md`. Check the shortcuts
especially: the Windows hotkey code has only run on a build machine. Expected: windowed
and Fullscreen work; Exclusive may not, and an overlay that injects into the game is out
of scope.
Then live data: Windows lets a program read another of the same user
(`OpenProcess` with `PROCESS_VM_READ`, `ReadProcessMemory`), so no probe or launch
option should be needed; the lookup by name (`turbohud/core`) stays as it is.

## 2. macOS: live data in CrossOver
TSU runs as a Windows game in a CrossOver bottle. Reading its memory from outside needs
`task_for_pid`, which macOS allows only with special rights. Find out what is possible
without weakening the system; until then the Mac shows the session clock.

## 3. Builds and release
Bundled apps from `tools/build_app.py` with the probe and clear launch-option steps for
Linux; an AppImage instead of the `.tar.gz`. Before the repository goes public for the
TSU community: the privacy check (pre-push hook), a licence, a README for players.

## 4. Linux: shortcuts, other Wayland desktops
On top of the game on Hyprland works (runtime requests for TurboHUD's own windows).
Shortcuts: Linux has none yet (Ctrl+Shift+L and Ctrl+Shift+Q do nothing there); the tray
menu switches move mode. Options: X11 key grabs under XWayland; on Wayland, a command
such as `TurboHUD --toggle` that tells the running TurboHUD what to do, which the
player binds to a key themselves, or the GlobalShortcuts portal where the desktop has
it. Other Wayland desktops (KDE, GNOME) ignore Qt's on-top hint: the layer-shell
extension (KDE, Sway; not GNOME) would need a library outside PySide6.

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
