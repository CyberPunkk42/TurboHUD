# Improvement backlog

Open items, most valuable first. Finished items move to `docs/PROGRESS.md`.

## 1. Tests must not reach a running TurboHUD
Running the tests while TurboHUD runs (found 2026-11-03, mid-race) switched the real
one to move mode: a test starts the app's main path, which finds the running copy
through the command socket in `$XDG_RUNTIME_DIR` and sends it "move". Until fixed, run
the tests with `XDG_RUNTIME_DIR` set to an empty private folder. Fix: give that test
its own runtime folder (or a fake `send`).

## 2. Windows: the overlay, then live data
Over TSU on Windows, in windowed, Fullscreen and Fullscreen Exclusive: the built app
(`tools/build_app.py`), the Qt probe (`experiments/run_qt_overlay_probe.cmd`) and the
original probe. Add the results to `experiments/README.md`. Check the shortcuts
especially: the Windows hotkey code has only run on a build machine. Expected: windowed
and Fullscreen work; Exclusive may not, and an overlay that injects into the game is out
of scope.
Then live data: Windows lets a program read another of the same user
(`OpenProcess` with `PROCESS_VM_READ`, `ReadProcessMemory`), so no probe or launch
option should be needed; the lookup by name (`turbohud/core`) stays as it is.

## 3. macOS: live data in CrossOver
Answered 2026-11-04 (`experiments/README.md`, "Memory inside the CrossOver bottle"):
macOS refuses `task_for_pid` on CrossOver's signed Wine loader, but a Windows program
inside the bottle can read TSU with `ReadProcessMemory`, and TurboHUD's lookup by name
works there unchanged (checked in TSU's menu). Next:
- Check race reads in the bottle (`sh experiments/run_bottle_memory_probe_mac.sh` with
  a race on): lap times, positions, how long a read takes.
- A bottle reader in place of the Linux probe: the same read-only questions (`maps`,
  `read`, `read_many`, `search`) over a local socket that only this user can use
  (TCP on 127.0.0.1 with a secret in a private file), shared with the Windows reader
  of item 2.
- How it starts: by hand, or by TurboHUD through CrossOver's `wine --bottle` (finding
  CrossOver and the bottle), and which Windows Python or build runs it.
- TSU's log in the bottle (`gamelog.py` reads the Linux folder) for the online search.

## 4. Builds and release
Bundled apps from `tools/build_app.py` with the probe and clear launch-option steps for
Linux; an AppImage instead of the `.tar.gz`. Before the repository goes public for the
TSU community: the privacy check (pre-push hook), a licence, a README for players.

## 5. Linux: other desktops
Commands for the running TurboHUD (`run_turbohud.sh --toggle` and so on) are done, and
on Wayland desktops other than Hyprland TurboHUD runs through XWayland, where staying on
top should work. Still to try on KDE and GNOME: on top over the game, clicks going
through. If XWayland is not enough there, the layer-shell extension (KDE, Sway; not
GNOME) would need a library outside PySide6.

## 6. Track map: check in races
The user saw it work in a race (2026-11-03), and the track is now learnt from the cars
(checked live in an AI event; the user confirmed it works). Still to check: the track's shape (tight
hairpins, tracks that cross themselves, point-to-point tracks), the road's width, the
dots changing over at an overtake, backmarkers, and as an online client. Possible
later: an arrow for the direction of travel, the pit lane, a hotlap alone (the map
then needs one whole lap of your own first).

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
