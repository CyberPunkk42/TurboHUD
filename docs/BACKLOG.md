# Backlog

Open work, most valuable first, a few lines each. The numbers stay as they are (the changelog
refers to them). What was done and found is in `docs/CHANGELOG.md`; the race measurements in
`experiments/README.md`; what to try next in `RESUME.md`. A finished item leaves this file.

## 0. The tester's stutter (macOS): waiting on him
TurboHUD's side is clean in his latest log (build 2026.11.16): frames steady about 19 a second, drawing 8
to 21% of the time, collections of at most 2 ms. Left: one read of 150 to 225 ms on an exact 30 s beat (at
:04 and :34 past the minute), nearly all of it in TSU's memory through Wine; and on his bad evenings TSU's
race data spread to about 3,090 MiB (normally 340 to 430). His Mac: M3 Pro, 18 GB, about 3 GB free with
everything running; his disk was nearly full until 2026-11-15.
Asked of him: whether that session stuttered and at what clock times (on :04 and :34 would point at the
30 s read), and the same races with Race reads a second at 10 (his saved setting is 20).
If it stutters only with TurboHUD: fewer reads a second and fewer pages first, then the long searches
between races (13 to 38 s). His logs, one by one: `experiments/README.md`, "The tester's stutter".

## 1. Windows: Fullscreen Exclusive and whole races
Built and used since 2026-11-11: live data through the Rust reader beside TSU (Python where it is
missing), the overlay over TSU's Fullscreen without Exclusive (2026-11-16), shortcuts (Ctrl+Shift+F12
where AMD Software has Ctrl+Shift+L), Custom races, one tint per group (off by default). Still to see:
- The overlay over Fullscreen Exclusive, and windowed (the app, `experiments/run_qt_overlay_probe.cmd`).
  Exclusive may not work; an overlay that injects into the game is out of scope.
- A whole race offline and hosting; a Single Player event; stutter during the search at an online
  race's start (4 threads, about 6 s).
- The layout list there: presets, groups, Undo, the design screen, the Layouts window, Ctrl+Shift+1 to 5.
- One tint per group over TSU; if right, on by default there (`group_tint_default`).

## 1b. CrossOver: all of TurboHUD inside the bottle (a trial)
Asked for by the user (2026-11-09): the Windows build inside TSU's bottle instead of the Mac app with a
reader there. At best a second mode: a window from inside CrossOver never shows over TSU's Fullscreen
(tested 2026-10-23; it does windowed and with Fullscreen off).
- Would gain: one app for Windows and the Mac, no looking for CrossOver and the bottle, no pipe;
  perhaps the pad's real throttle and brake through XInput. Not faster reads (the Wine server either way).
- Would cost: no overlay over Fullscreen; frames (each Wine window is still a Mac window, so it needs the
  one-window canvas); more load on the Wine server TSU uses; soft text on Retina unless the player turns
  on CrossOver's High Resolution Mode (never TurboHUD's choice); Qt 6 under Wine unproven; installing into
  the bottle; harder to rule TurboHUD out when TSU freezes on quitting.
- Plan, cheapest first: (1) `experiments/qt_overlay_probe.py` in the bottle with PySide6 in a copy of
  `.buildtools/win-python`, TSU windowed: visible, click-through, shortcuts, crisp text, tray, FPS with the
  Metal HUD; stop if Qt fails. (2) TSU windowed: the native app against the probe, as many windows and as
  one. (3) Only then the real app in the bottle as an option. (4) Decide from the numbers.
- Rules: nothing in the bottle's settings, the game's folders or the system is changed; PySide6 and the
  probe stay in `.buildtools/` and `experiments/`.

## 1c. One window on Linux: measure first
Run `experiments/window_count_probe.py` over TSU in a race on Hyprland and note the FPS of each phase (and
the compositor's load if it can be had). If one window wins there, turn on the canvas on Linux (`one_window`
in the Native) and the Mac's group tint comes with it; else a window per group as on Windows (item 3b).
Windows was measured on 2026-11-16: a window per section stays there.

## 2. macOS: the one-window HUD, and what is left of live data
Live data works in CrossOver (the Rust reader in the bottle; races offline, online, Fullscreen and
spectating confirmed by the user on 2026-11-08). Left:
- The one-window HUD showed no FPS gain on 2026-11-10. To tell: one race with the Metal HUD, a minute
  each of TurboHUD closed, every section, the same with `TURBOHUD_ONE_WINDOW=0 sh run_turbohud.sh`, one
  section in each, and closed again. Then keep it, make it only as large as its sections, or go back.
- Race reads: 31 to 49 reads of the game, 16 to 22 ms a read; what is left is the price of a call, so
  fewer pages would be next.
- The search from the last race in another session and as a spectator; joining as a driver from
  spectating; stutter in an online event's first seconds while the reader searches (half of the time).
- Throttle and brake move in TSU's thirds (the pad is read on Linux only).
- TSU froze on quitting twice with TurboHUD quit first; no cause known (`experiments/README.md`). The
  user notes at each quit whether it froze and whether TurboHUD ran.

## 3. Layout: what is left to check
Checked by hand on the Mac (2026-11-05 and later). Still to try:
- Linux: `--preset`, moving and resizing through Hyprland (followers sized when a resize ends), Undo; the
  move-mode panel's 13 px text over TSU.
- Windows: see item 1.
- The Mac: the move-mode panel on a small laptop screen (it scrolls); the grid letting clicks through
  (beneath the sections since `fix/grid-beneath-sections`; on Windows still to see); the Options submenu in the menu bar (and Windows' tray); the
  save and open windows above TurboHUD.
- Named presets and a preset per kind of event (2026-11-15): the Layouts window beside the panel, typing
  a name there (focus on Hyprland), Ctrl+Shift+4 and 5 on each system, and each kind in TSU (a recording,
  hotlapping, a race, an arena event; the log says `event type:` and `a ... began`).
- The place label in move mode (2026-11-16): by hand on the Mac and Hyprland; on the design screen it
  gives the designed size's numbers; none after a preset, Undo or Redo.
- The design screen opening on this screen's size at 100%; the Move mode grid switch off.

## 3b. One tint per group on Linux
Done on the Mac (2026-11-15) and Windows (2026-11-16, off by default there, item 1). Linux waits on item
1c: with one window the Mac's drawing serves; else a Native with `group_tint_windows` and `place_below`.

## 4. Builds and release
- The Mac build for older macOS: `sh tools/get_mac_python.sh`, then
  `.buildtools/mac-build-venv/bin/python tools/build_app.py --version YYYY.MM.DD --smoke` (not yet tried;
  with Homebrew's Python the app needs macOS 27, `--any-macos`). A Developer ID and notarisation would
  remove the Open Anyway step.
- Linux: the `.tar.gz` tried by players on other distros and desktops; an AppImage instead.
- Before the repository goes public: the privacy check, a licence, a README for players (`QUICK_START.md`
  and `USER_GUIDE.md` ship since 2026-11-12 and 2026-11-15).

## 5. Linux: other desktops
On Hyprland the shortcuts are in its live keymap (still to press them in a race). KDE and GNOME: on top
over the game and clicks going through under XWayland; shortcuts there through the GlobalShortcuts portal.
If XWayland is not enough, the layer-shell extension (KDE, Sway; not GNOME) needs a library outside PySide6.

## 6. Track map: the modes, and checks in races
The map shows only in `TS.RaceEventMode` (regular races; special events expected the same); the arena
modes have none. Still to see in the log's `event type:` line: a special event (if another mode, add it
to `TRACK_MODES` in `turbohud/core/race.py`), King of the Hill or Sumo. `experiments/tsu_race_recorder.py`
records each event's mode: record Sumo, King of the Hill, Soccer, Tag and a special event, for what an
arena HUD could show.
In races: tight hairpins, tracks that cross themselves, point-to-point tracks, the road's width, dots at an
overtake, backmarkers, online as a client; Relearn map; a track with a shortcut on tarmac, and whether
SHORT_LAP (0.985) leaves out a good lap. Later perhaps: an arrow for the direction, the pit lane.

## 7. Replays: check in TSU, then the Mac
Built 2026-11-12: the race under TSU's replay player, the followed driver as "you". Still to see: every
section in a replay, switching drivers, pausing, the end; a recording watched after a race in the same
session, opened from the list and again. On the Mac: whether CrossOver's files get an access time when TSU
opens a recording, and teaching the Rust reader several values a search pass (a replay costs a second pass).

## 8. Race Director mode (agreed 2026-11-16, next once the user says go)
Only while watching (a recording, or spectating live), never while driving; inside TurboHUD, kept light.
Built: (1) the battle warning (`turbohud/core/battle.py`), to see in a replay and spectating and tune
(`BATTLE_*`); (2) the watched driver's banner in a replay (`turbohud/core/watched.py`), to see; (3) the
banner while spectating, from the camera TSU's cockpit view is read from (`spectated_driver`): not yet seen
live, the log says whether it reads; (4) a Spectating kind of event for the presets (Layouts > Load by
itself), to see. What is left: nothing planned; tune the parts from what the user sees.

## 10. TurboHUD's memory grows on Linux (found 2026-11-20)
189 to 542 MB in 18 min of racing. Found: the drawn-text images (capped at 64 MB, as meant) and the text
outlines, 512 kept at about 220 KB each (about 114 MB), no longer kept: a race now levels off near 300 MB. Left: Python's
blocks rise slowly (under 1 MB a minute): a session with `TURBOHUD_TRACE_MEMORY=1` says where. Then the Mac and
Windows in a long race.

## 11. A preset loads slowly on Hyprland (found 2026-11-20)
Each preset load froze the HUD 1.2-1.4 s (the log's `slow frame` lines right after `preset N loaded`): each of the
23 sections is placed through hyprctl, about ten requests each, one after another. Send them in one
`hyprctl --batch`, or move only (no float, pin and props again) for sections already placed.

## 12. Reads ten times slower with many cars (found 2026-11-20)
A race of about 20 cars on Linux: reads took 29-41 ms (3.4 ms hotlapping alone), up to 80% of the reading time at
20 a second; each car is read in turn, several dozen requests each. Read the cars' fields in batches
(`read_many`), as their positions are since 2026-11-20.

## 13. The compass, hidden for now (2026-11-20)
Built and confirmed (north from the sun on 5 tracks), but not offered to players for now (the user's call):
`hud.COMPASS_AVAILABLE = False` leaves it out of RACE_SECTIONS, so no window, panel row or options; places in
the settings and presets are kept. To offer it: set it True, and bring back its guide text (USER_GUIDE.md's
**Compass** section and its two options, QUICK_START.md's line, README.md's lists) from commit `89cacf1`.

## 14. Checks on the Mac and Windows, and rare cases not yet seen (from RESUME.md, 2026-11-20)
Each one's details are in its changelog entry.
- **The Mac and Windows**: the radar on the closest car; TurboHUD's memory in a long race; the Race preset at
  start; the panel's General and Text tabs (Mac); the place label following a drag and staying above the
  sections (Mac); a replay found in about 5 s (Mac, reader rebuilt); one tint per group (Windows, then on by
  default there); the tester's stutter times and 10 reads a second (item 0).
- **Linux**: the window count probe over TSU on Hyprland (item 1c); the log's slow-frame lines only for real
  hitches (150 ms and more).
- **Not yet seen**: a Single Player event and Custom races on the Mac and Linux; a replay after a race in the
  same session; the delta bar red on a slow loss; the HUD at once when TSU's log says an event runs; yellow
  flags (`YELLOW_*` in `race.py`); a broken track map mending after a clean lap; a purple sector turning green;
  King of the Hill or Sumo; a track without sector lines (3 even bars); joining as a driver after spectating;
  a race leader banner for a pass undone or at the start (none).

## Nice to have (ideas, not planned)
Ideas talked over and left for later; none is being worked on. Take one up only when the user asks.
- **The `sun:` log line without the location** (`location not read (Bad address)` at every event): the compass
  does not use it.
- **Offered earlier, not taken up:** the Mac's one-window canvas only as large as its sections; the
  one-window canvas on Linux (item 1c decides); sector times as numbers; a blue flag for the leader only;
  the settings window remembering where it was dragged; fixed slots for other numbers (fuel and tires move
  by a digit going from 100 to 99%).
- **The delta against TSU's ghost:** the bar compares with the best lap of the race, not the ghost, so it
  seemed late against the tester's ghost. To follow the ghost: record a race against one with
  `experiments/tsu_race_recorder.py`, then read `EventPlayer.m_comparedTimes` /
  `m_ghostRecordingPlayerToCompareWith`.

