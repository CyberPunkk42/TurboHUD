# Improvement backlog

Open items, most valuable first. Finished items move to `docs/PROGRESS.md`. Where the work
last stopped: `docs/CONTINUE_HERE.md`.

## 0. The tester's stutter with build 2026.11.12.4 (macOS)
Reported 2026-11-12, after the day's features (class colours, tire column, the player list around the player).
His log (four online races): reads of 4 ms, frames 53 ms apart, content 2 to 4% and drawing 20 to 24% of the
time (16 to 19% on 2026-11-10), about the same with the lap times hidden; no CrossOver graphics warning.
Done (`fix/lap-list-frame-cost`): the lap times and the player list measure less, the Mac's one window draws
again only the sections that changed, and running times and gaps come from kept glyph images (0.06 ms a new text,
from about 0.9 ms at 2x; a few edge pixels differ a little). In build 2026.11.12.6 for the tester. Left:
his log's drawing share (was 20 to 24%), and ask whether the stutter is while
driving or between races (the search from the last race reads for 8 to 11 s).

## 1. Windows: the overlay, then live data
Over TSU on Windows, in windowed, Fullscreen and Fullscreen Exclusive: the built app
(`tools/build_app.py`), the Qt probe (`experiments/run_qt_overlay_probe.cmd`) and the
original probe. Add the results to `experiments/README.md`. Check the shortcuts
especially: the Windows hotkey code has only run on a build machine. Expected: windowed
and Fullscreen work; Exclusive may not, and an overlay that injects into the game is out
of scope.
Then live data: built 2026-11-11 with the Rust reader started beside TSU (`LocalReader`), the
same reader and questions as on the Mac, so no probe or launch option; Python in TurboHUD itself
where the reader is missing. To try on a Windows PC: a race offline, hosting and as an online
client, and the log's `reading TSU through the Rust reader` and `race reads` lines.
First run on the user's PC (2026-11-11): the reader started, Ctrl+Shift+L worked once AMD
Adrenalin let go of it, and an online race was found once a hang in the search was fixed. Still to
see: the HUD through a whole race, offline and hosting, and the overlay over Fullscreen Exclusive.
Also: a spare shortcut when another app holds Ctrl+Shift+L, and the 9 tests that fail on Windows.
The race search reads with 4 threads on Windows since 2026-11-12 (about 6 s for all of TSU's data, from 19 s):
listen for stutter in those seconds at the start of an online race.
What is built and what is left on Windows: `docs/WINDOWS_AND_CROSSOVER.md`.

## 1b. CrossOver: all of TurboHUD inside the bottle (a trial)
Asked for by the user (2026-11-09): try TurboHUD as a Windows app inside TSU's bottle instead of a
native Mac app with a reader in the bottle. Analysis and plan: `docs/WINDOWS_AND_CROSSOVER.md`. A
window from inside CrossOver never shows over TSU's Fullscreen (tested 2026-10-23), so at best a
second mode for windowed TSU. Next: the Qt overlay probe in the bottle (plan step 1), then FPS
against the native app with TSU windowed. Needs item 1's live data in-process for the real app.

## 2. macOS: live data in CrossOver
Answered 2026-11-04 (`experiments/README.md`, "Memory inside the CrossOver bottle"):
macOS refuses `task_for_pid` on CrossOver's signed Wine loader, but a Windows program
inside the bottle can read TSU with `ReadProcessMemory`, and TurboHUD's lookup by name
works there unchanged, race reads too: alone 17 ms a read; online as a client (13 AI)
the race is found after about 15 s and read in about 20 ms
(`turbohud/tsu/winmemory.py`: page cache, paced search that stops at the first good
hit). The Mac app now does this by itself (`turbohud/tsu/bottle.py`, the Rust reader in
`reader/` inside the app; no Windows Python since 2026-11-11). Still to do:
- The tester's FPS (`docs/CONTINUE_HERE.md`, "Tester's Mac"): unticked sections leaving the screen
  gave back most of the loss with nothing shown (2026-11-08: 107 of 115 FPS, from 78). Shown sections still
  cost frames, to about 60 with all: the windows above the game, not the reads. A CPU recording on the
  user's Mac (2026-11-09) has each window cost the same, whatever it shows: so not fewer redraws but fewer
  windows. The Metal HUD on the user's Mac (2026-11-09): 120 FPS closed and with one section, 80 to 110
  with all; the window count probe: 17 windows 85, one window 115. Built: locked, on the Mac, all sections
  in one window per screen. Seen over TSU on 2026-11-10: it works, but no gain showed (about 85 FPS with
  every section, in a race that ran 85 to 120 without TurboHUD; one section cost as much as all). Next:
  one window against a window each in the same race (`docs/CONTINUE_HERE.md`), then the tester's build.
  TSU froze once more on quitting, with TurboHUD quit first (`docs/CONTINUE_HERE.md`, "Other points").
- Race reads in one go: 1 trip a read (seen 2026-11-10), but still 26 to 29 ms a read in 84 to 88 reads
  of the game, about 0.3 ms each. Built 2026-11-10: pages up to 192 KiB apart in one read of up to
  2 MiB (`MERGE_GAP`, `SPAN_MOST`). Seen the same day: 31 to 49 reads of the game, 16 to 22 ms a read.
  The pages lie far apart, so what is left is the price of a call; fewer pages would be the next step.
- Races on the Mac: confirmed by the user on 2026-11-08, offline with 19 AI, in Fullscreen and
  hosting about 13 AI online (`docs/CONTINUE_HERE.md`, "Test list"). As a driver online the race
  showed 1.4 s after the start.
- The reader in Rust (2026-11-10, `reader/`): a race read in 8.7 to 10.5 ms, from 16 to 22 ms with the
  Python reader. It ran online as a client on the tester's Mac (2026-11-11, builds from 2026.11.11 use it
  only), and the Mac app ships without the Windows Python since then.
- Searches that begin where the last race was (2026-11-10): seen the same day, three races in a row
  found after 0.4 s at the first hit, within 0.5 MiB of the last one. Still to see: another session and a
  spectator (`docs/CONTINUE_HERE.md`, "Not yet seen in a race").
- Listen for stutter while the reader searches (in an online event, the first seconds; a
  search of all the data at once made TSU stutter). It now reads half of the time, up from a
  quarter (2026-11-05), to show the HUD sooner.
- Throttle and brake on the Mac move in TSU's thirds: the pad's triggers are read through
  the Linux joystick interface only.
- The spectator HUD: seen in public sessions on 2026-11-08 ("Spectating", the map; no map in an
  arena mode). Still to see: joining as a driver from spectating.

## 3. Layout: what is left to check
The user went through it all by hand on the Mac on 2026-11-05 and it worked: the tight boxes,
presets with their shortcuts, groups, the Centre buttons, Centre text and Undo. Still to see:
- Confirmed on 2026-11-08: the lap times list with 20 drivers, and the preset shortcuts with TSU
  in front during a race.
- Linux: `--preset`, and moving and resizing through Hyprland (followers take their size when
  a resize ends), and Undo there.
  The move-mode panel's text is held at 13 px there since 2026-11-12 (771 px tall, was 866):
  check it reads well over TSU.
- Windows has run none of this (its shortcut code has only ever run on a build machine).

## 4. Builds and release
The Mac app for a tester (2026-11-06): build with `sh tools/get_mac_python.sh`, then
`.buildtools/mac-build-venv/bin/python tools/build_app.py --version YYYY.MM.DD --smoke`. That Python has
not been tried yet; with Homebrew's, the app needs macOS 27 (`--any-macos`). A Developer ID
certificate and notarisation would remove the Open Anyway step.
Bundled apps from `tools/build_app.py` with the probe and clear launch-option steps for
Linux; an AppImage instead of the `.tar.gz`. Before the repository goes public for the
TSU community: the privacy check (pre-push hook), a licence, a README for players.

## 5. Linux: other desktops
Commands for the running TurboHUD (`run_turbohud.sh --toggle` and so on) are done, and
on Wayland desktops other than Hyprland TurboHUD runs through XWayland, where staying on
top should work. Still to try on KDE and GNOME: on top over the game, clicks going
through. If XWayland is not enough there, the layer-shell extension (KDE, Sway; not
GNOME) would need a library outside PySide6.

## 6. Track map: only in races and special events
Asked for by the user (2026-11-08), built the same day: the map shows, and a track is learnt, only in
TS.RaceEventMode (regular races; special events from A to B are expected to be the same mode). The arena
modes (Battle, Collector, Hill, Soccer, Sumo, Tag) have none. Seen: a capture event is
`TS.BattleEventMode`, level type 6. A regular online race gave `TS.RaceEventMode`, level type 0, logic TS.RaceLogic
(2026-11-10). Still to see in the log's `event type:` line: a
special event giving `TS.RaceEventMode` (if a special event is another mode, add it to `TRACK_MODES` in
`turbohud/core/race.py`), and one of King of the Hill or Sumo.
Since 2026-11-11 `experiments/tsu_race_recorder.py` records each event's mode and its mode objects (also on
Windows): record Sumo, King of the Hill, Soccer, Tag and a special event, for the event type and what an
arena HUD could show (Battle's capture and rounds: `experiments/README.md`).

## 6b. Track map: check in races
The user saw it work in a race (2026-11-03), and the track is now learnt from the cars
(checked live in an AI event; the user confirmed it works). Still to check: the track's shape (tight
hairpins, tracks that cross themselves, point-to-point tracks), the road's width, the
dots changing over at an overtake, backmarkers, and as an online client. A map learnt wrong can be relearnt
(Relearn map, 2026-11-11; still to try in a race), and a track is chosen from three clean laps (2026-11-11):
still to see on a track with a shortcut on tarmac, and whether SHORT_LAP (0.985) leaves out a good lap. Possible
later: an arrow for the direction of travel, the pit lane, a hotlap alone (the map
then needs one whole lap of your own first).

## 7. Replays: check in TSU, then the Mac
Built 2026-11-12 (`feature/replays`, asked for by the user): the race under TSU's replay player
(`TS.EventRecordingPlayer`), the driver its camera follows as "you", positions from the recording, and the HUD
kept while a replay is paused. Still to see in a replay: every section with the followed driver (lap times, player
list, fuel, tires, health, track map, flags, shortcuts, jump starts, pit times), switching drivers, pausing, and
the end of a replay. Left: on the Mac the Rust reader searches one value a pass, so a replay costs a second pass
there when no online race is found (teach it several values, as `winmemory.search` does); and the Mac's check of
TSU's log may say no event runs during a replay, which would stop the search there (to try).

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
