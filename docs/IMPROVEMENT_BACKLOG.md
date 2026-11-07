# Improvement backlog

Open items, most valuable first. Finished items move to `docs/PROGRESS.md`. Where the work
last stopped: `docs/CONTINUE_HERE.md`.

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
works there unchanged, race reads too: alone 17 ms a read; online as a client (13 AI)
the race is found after about 15 s and read in about 20 ms
(`turbohud/tsu/winmemory.py`: page cache, paced search that stops at the first good
hit). The Mac app now does this by itself (`turbohud/tsu/bottle.py`, reader in
`bottle_reader.py`, Windows Python inside the app). Still to do:
- Find what costs a tester's Mac about 50 FPS, and why TSU hung on exit with TurboHUD quit first
  (`docs/CONTINUE_HERE.md`, "Tester's Mac"). Done so far (2026-11-07): unticked sections are no longer
  redrawn and leave the screen, and the settings window sets the race reads a second, to compare.
- Check in races on the Mac, going through the list in `docs/CONTINUE_HERE.md`: offline and
  online, the sections over TSU's Fullscreen, how long the race takes to show, the track map
  and the radar. AI races online have run many times, but the list has not been gone through.
- Listen for stutter while the reader searches (in an online event, the first seconds; a
  search of all the data at once made TSU stutter). It now reads half of the time, up from a
  quarter (2026-11-05), to show the HUD sooner.
- See that race reads now stay quick in a race with AI (2026-11-05: they took about 1000 ms a
  read while driving, 28 ms from a separate connection, 14 ms a trip of which 0.37 ms on the
  game's memory). The fix is in; the log's `race reads` line tells. The stutter came from
  CrossOver's graphics setting, not the many AI: D3DMetal cured it (2026-11-05).
- Throttle and brake on the Mac move in TSU's thirds: the pad's triggers are read through
  the Linux joystick interface only.
- Check the spectator HUD while watching a real race (built 2026-11-04, seen only with a
  fake game and offscreen): whether the replay recorder runs for a spectator, so the map's
  dots and the live gaps use real positions; and what fun-mode events show.

## 4. Layout: what is left to check
The user went through it all by hand on the Mac on 2026-11-05 and it worked: the tight boxes,
presets with their shortcuts, groups, the Centre buttons, Centre text and Undo. Still to see:
- The lap times list with 20 drivers in a race: does it fit, and does a race read stay quick?
- The preset shortcuts with TSU in front, during a race (a hitch when switching?).
- Linux: `--preset`, and moving and resizing through Hyprland (followers take their size when
  a resize ends), and Undo there.
- Windows has run none of this (its shortcut code has only ever run on a build machine).

## 5. Builds and release
The Mac app for a tester (2026-11-06): build with `sh tools/get_mac_python.sh`, then
`.buildtools/mac-build-venv/bin/python tools/build_app.py --version YYYY.MM.DD --smoke`. That Python has
not been tried yet; with Homebrew's, the app needs macOS 27 (`--any-macos`). A Developer ID
certificate and notarisation would remove the Open Anyway step.
Bundled apps from `tools/build_app.py` with the probe and clear launch-option steps for
Linux; an AppImage instead of the `.tar.gz`. Before the repository goes public for the
TSU community: the privacy check (pre-push hook), a licence, a README for players.

## 6. Linux: other desktops
Commands for the running TurboHUD (`run_turbohud.sh --toggle` and so on) are done, and
on Wayland desktops other than Hyprland TurboHUD runs through XWayland, where staying on
top should work. Still to try on KDE and GNOME: on top over the game, clicks going
through. If XWayland is not enough there, the layer-shell extension (KDE, Sway; not
GNOME) would need a library outside PySide6.

## 7. Track map: check in races
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
