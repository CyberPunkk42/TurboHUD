# Experiments

Throwaway probes that answer one question each before TurboHUD's design is fixed.
They are not part of the app.

## Overlay probe (`overlay_probe.py`)

Question: can a see-through, click-through, always-on-top window sit over TSU? On the
Mac this also decides whether one Windows app can serve both systems by running inside
CrossOver.

The probe shows a dark, semi-transparent box with a seconds counter. It uses plain Win32
calls and only Python's standard library.

### Run it
1. Start TSU in a window, or on the Mac with Fullscreen off (see Results), and drive
   onto a track.
2. Start the probe:
   - Mac: `sh experiments/run_overlay_probe_mac.sh`. The first run downloads a portable
     Windows Python (3.13, checked against its SHA256) into `.buildtools/win-python`.
     It runs in the `Steam` bottle; set `TURBOHUD_BOTTLE` for another one.
   - Windows: `py -3 -B experiments\overlay_probe.py`
3. The box starts in move mode (lighter blue, with **Lock** and **Close** buttons at the
   bottom left and a resize grip in the bottom-right corner). Drag the box to move it,
   drag the grip to make it bigger or smaller, then press **Lock**. Locked, the blue
   tint and buttons disappear and only the text shows (with a thin shadow). The box is
   then click-through, so the mouse can no longer reach it:
   - **Ctrl+Shift+L** unlocks it (and locks it again)
   - **Ctrl+Shift+Q** quits
   No Alt key is needed, so this works on a Mac keyboard.
4. If the shortcuts do not arrive, quit with Ctrl+C in the terminal, or wait (10 minutes
   by default).

Position and size are saved when you lock or quit, in `.buildtools/overlay_probe.json`
(gitignored), and the next run starts there. The first run is 640x240 at the top left.

Options: `--x`, `--y`, `--width`, `--height` (pixels, instead of the saved ones),
`--alpha` (opacity of the move-mode tint, 0-255), `--seconds`, and `--locked` to start
click-through.

### What to check
| Check | Pass when |
| --- | --- |
| Visible | The box shows over the game while you drive. |
| See-through | In move mode the game shows through the blue tint; locked, only the text shows. |
| Movable | In move mode the box follows the mouse while you drag it, and the grip resizes it. |
| Pointer | The mouse pointer shows over the box in move mode (the log says when the game hides it). |
| Stays on top | The box stays visible after clicking into the game and while driving. |
| Click-through | Locked, clicking on the box steers or clicks the game; "clicks received" stays at 0. |
| Shortcuts | Ctrl+Shift+L and Ctrl+Shift+Q work while the game has focus (the log shows them). |
| Live updates | The seconds counter keeps counting while the game runs. |
| Game unaffected | No stutter or lost keyboard input in the game. |

The terminal log is also saved to `.buildtools/overlay_probe.log` (gitignored, replaced
on each run). It shows the window styles Wine or Windows kept, the result of a hit test
at the box's centre, each change of the focused window (its size and whether it keeps
itself on top), whether the mouse pointer is shown, and each time the game came in front
of the overlay. The probe then puts the overlay back on top.

### Results

**macOS, CrossOver (2026-10-23).** Tested by hand over TSU in the `Steam` bottle.

| TSU display setting | Overlay |
| --- | --- |
| Windowed | Works |
| Fullscreen Exclusive, with Fullscreen off | Works |
| Fullscreen (with or without Exclusive) | Never visible |

Where it works: the box shows over the game, moves and resizes. Locked, its background
is fully hidden and clicks pass through to the game. Ctrl+Shift+L and Ctrl+Shift+Q arrive
while TSU has focus.

In Fullscreen, TSU makes its window always-on-top and covers the whole screen. The probe
puts itself back in front, and Windows' window order (as Wine reports it) then has the
overlay in front. Still, the Mac never shows it, not even when the overlay itself covers
the whole screen. So the macOS window level Wine gives a full-screen window is above
anything another Wine window can reach. **An overlay that works over TSU's Fullscreen
mode on the Mac cannot come from inside CrossOver.** It needs a native macOS window
outside the bottle.

Other findings:
- A box that takes the mouse (move mode) blocks the game's mouse input under it: with a
  near-screen-sized box, TSU's menu cursor seemed to freeze until the box was locked. Move
  mode should be a short, deliberate step.
- TSU hides the system pointer at times. The overlay must set its own pointer in move
  mode, or there is none.

Not tested yet: Windows; stutter or lost input over a long drive.

## Native Mac overlay probe (`mac_overlay_probe.py`)

Question: can a native macOS window, outside CrossOver, show over TSU when its
Fullscreen setting is on?

The probe is a plain Mac program: a transparent, click-through window with white text and
a seconds counter, at a window level above full-screen windows and allowed on every
Space. It calls macOS through ctypes and needs only Python's standard library.

### Run it
1. Set TSU to **Fullscreen** and drive onto a track.
2. In a terminal: `/opt/homebrew/bin/python3.13 -B experiments/mac_overlay_probe.py`
3. Look for the text at the top left of the screen.
4. **Ctrl+Shift+L** switches to move mode: the box gets a blue tint, the overlay becomes
   the active app (so the pointer shows), and you can drag the box. Ctrl+Shift+L again
   locks it, saves the position and hands the focus back to the game. Going back to the
   game in another way (clicking into it) locks the box too: the game's mouse handling
   gets out of step if it is played while the overlay is in move mode.
5. Quit with **Ctrl+Shift+Q**, with Ctrl+C in the terminal (when the terminal has
   focus), or wait (10 minutes by default).

Both shortcuts are system-wide hotkeys, which need no permission.

Options: `--x`, `--y` (points from the top left, instead of the saved position),
`--width`, `--height`, `--seconds`,
and `--level` (`floating`, `menu`, `status`, `popup`, `screensaver` (default) or
`shielding`, which is above even a captured display).

The log, also saved to `.buildtools/mac_overlay_probe.log` (gitignored), shows whether
macOS counts the overlay as visible, and the large windows on screen, front to back, with
their owner and window level (TSU's shows as `TSU.exe`). Window titles are not read.

### What to check
| Check | Pass when |
| --- | --- |
| Visible | The text shows over TSU in Fullscreen, also after clicking into the game and while driving. |
| Click-through | Locked, clicks on the text reach the game. |
| Shortcuts | Ctrl+Shift+L and Ctrl+Shift+Q work while the game has focus. |
| Move mode | The pointer shows, the box can be dragged, and locking gives the game its focus back. |

### Results

**macOS (2026-10-23).** Tested by hand over TSU with its **Fullscreen** setting on.

- The text is clearly visible over the game the whole time, also while driving and after
  clicking into the game. No stutter.
- Locked, clicks pass through to the game.
- Ctrl+Shift+L and Ctrl+Shift+Q work while TSU has focus.
- Move mode works: the pointer shows and the box can be dragged. Clicking back into the
  game locks it.

Why this works where the CrossOver probe did not: in Fullscreen, TSU's window is at macOS
window level 26 while it is the active app (0 when it is not). A window inside CrossOver
reaches only level 3 (floating). The native overlay sits at level 1000.

**The overlay for TSU's Fullscreen on the Mac must be a native macOS window.** It works
outside the bottle and needs no permission (no screen recording, no accessibility).

Other findings:
- Using the game while the overlay is in move mode (the overlay is then the active app)
  puts the game's mouse handling out of step. Locking, which activates the game again,
  repairs it, so move mode now ends as soon as the game becomes active.
- In TSU's in-game menu, the pointer jumps to the Camera button and disappears for good
  once the gamepad is used. This happens without any overlay too: it is TSU's own
  behaviour and has been reported to its developer.

## Qt overlay probe (`qt_overlay_probe.py`)

Question: can a Qt (PySide6) window, TurboHUD's chosen stack (`docs/STACK.md`), do what
the two native probes do, with HUD graphics drawn by Qt?

The probe shows a test HUD: outlined text, a lap-style clock, a bar that empties once a
minute, and a small map with a dot going round. Qt makes the window transparent,
click-through and always on top. On the Mac, a few ctypes calls (from the native Mac
probe) raise it to the screen-saver level on every Space and register the shortcuts; on
Windows, ctypes registers the shortcuts. Linux has no shortcuts yet.

### Run it
1. Set TSU to the mode to test (on the Mac: **Fullscreen**) and drive onto a track.
2. Start the probe. The first run creates `.buildtools/qt-venv` (gitignored) and
   installs the pinned PySide6 from `experiments/requirements-qt.txt` into it:
   - Mac or Linux: `sh experiments/run_qt_overlay_probe.sh`
   - Windows: `experiments\run_qt_overlay_probe.cmd` (needs Python 3.10+ with the `py`
     launcher)
3. The HUD starts locked at the top left. **Ctrl+Shift+L** switches to move mode: blue
   tint, the pointer shows, drag the box, resize it at the bottom-right corner, then
   **Lock** (or Ctrl+Shift+L). Clicking back into the game also locks it.
4. Quit with **Ctrl+Shift+Q**, **Close** in move mode, Ctrl+C in the terminal, or wait
   (10 minutes by default).

Placement is saved in `.buildtools/qt_overlay_probe.json` and the log in
`.buildtools/qt_overlay_probe.log` (both gitignored). Options: `--x`, `--y`, `--width`,
`--height`, `--seconds`, `--level` (macOS, as in the native Mac probe) and `--move` to
start in move mode (needed on Linux, which has no shortcuts yet).

### What to check
| Check | Pass when |
| --- | --- |
| Visible | The HUD shows over TSU (on the Mac in Fullscreen), also after clicking into the game and while driving. |
| Looks | Text, bar and map are smooth and readable over bright and dark parts of the track. |
| Click-through | Locked, clicks on the HUD reach the game. |
| Shortcuts | Ctrl+Shift+L and Ctrl+Shift+Q work while the game has focus. |
| Move mode | The pointer shows, the box can be dragged and resized, and locking gives the game its focus back. |
| Game unaffected | No stutter or lost input while the map dot moves 20 times a second. |

### Results

**macOS (2026-10-24, PySide6 6.11.2).** Tested by hand over TSU with **Fullscreen** on, both
with Fullscreen Exclusive off and on: everything works as planned.

- The HUD shows over the game, and the text is crisp.
- Locked, clicks pass through; the shortcuts and move mode work.
- The game runs fine, with no stutter while the map dot moves.

**Qt works for TurboHUD's overlay on the Mac,** with the small ctypes part for the window
level and the shortcuts. Not tested yet: Windows, Linux.
PySide6 takes about 335 MB in the development environment on the Mac; a bundled app
would include only the parts it uses.

## Memory probe (`tsu_memory_probe.py`, Linux)

Question: can TurboHUD read TSU's memory on Linux, and only TSU's, without changing the
system?

The probe is now part of the app (`turbohud/tsu/probe.py`); `tsu_memory_probe.py` here
only starts it, so the Steam launch option keeps its path. Likewise the lap reader's
logic is in `turbohud/core/il2cpp.py` and `turbohud/core/race.py`, and
`tsu_lap_reader.py` is a terminal view of what the overlay shows.

Linux (Yama `ptrace_scope` 1) lets a program read another program's memory only if it
started it. So the probe starts TSU: Steam runs the probe, the probe runs the game. It
then may read TSU's memory and nothing else's. No sudo, no `setcap`, no system setting;
the right ends when the game quits. It only reads (`process_vm_readv`), never writes,
and never pauses the game. If the probe fails, the game still runs.

### Run it
1. Without the game: `python3 -B experiments/tsu_memory_probe.py --self-test`. It reads
   a program it started (should work) and the terminal (should be refused).
2. In Steam: Turbo Sliders Unlimited > Properties > General > Launch Options:
   `python3 /home/<user>/Work/workspace/tsu_repositories/TurboHUD/experiments/tsu_memory_probe.py %command%`
3. Start TSU from Steam and wait until the menu shows.
4. Read `~/.config/TurboHUD/memory_probe.log`. `OK: read 16 bytes of GameAssembly.so`
   means it works.
5. Clear the launch option again to start TSU without the probe.

### Finding the lap time (`tsu_memory_scan.py`)
While TSU runs through the probe, the probe answers read-only requests (memory map,
read, search) on `$XDG_RUNTIME_DIR/turbohud/tsu-memory.sock`, which only this user can
open; it goes away when the game quits. TSU keeps lap times as whole numbers in steps of
0.1 ms (`lapTimeIn100us` in its code), so a lap of 1:35.421 is one of 954210-954219.
1. Drive a lap alone (hotlap) and note the lap time the game shows.
2. `python3 -B experiments/tsu_memory_scan.py find 1:35.421`
3. Drive another lap, then `python3 -B experiments/tsu_memory_scan.py refine <new time>`.
4. Repeat until a few places remain; `show` lists them.

### Results
- 2026-11-01, Omarchy Linux: self-test passes (own child readable, terminal refused).
- 2026-11-01, Omarchy Linux, over TSU started from Steam: the probe found `TSU.x64`
  and read the start of `GameAssembly.so` (OK).
- 2026-11-01, Omarchy Linux, hotlap alone, laps 1:39.647 and 2:40.032: the lap data was
  found in memory (heap addresses, different on every start). All times are int32 in
  steps of 0.1 ms.
  - **Lap list:** an array of 12-byte entries `{flags, lap number, lap time}`, one per
    lap of the event's lap limit (the length, 13, sits 12 bytes before the first lap
    time's entry ends).
  - **Player lap state:** `{?, time the last lap finished on the race clock, best lap,
    laps completed}`, e.g. `1, 267.2984 s, 99.6479 s, 2`.
  - **Race clock:** 32 bytes after a copy of the best lap; follows real time but changes
    in irregular steps (about every 0.7-1.7 s).
  - Current lap time = race clock - time the last lap finished. Checked live.
  - Also found: a list of times 0.1025 s apart, probably the replay recording.
  - Still open: a stable way to find these places at each start (through the game's
    type information), and a smoother clock.

### Live lap data by name (`tsu_lap_reader.py`)
The addresses above change on every start. The game's IL2CPP type information is mapped
into its memory (`global-metadata.dat`), and every loaded class has a runtime record
pointing to its name, its fields (name and position) and its static fields. So the
reader finds everything by name, in about 0.1 s, with no stored addresses:
`TS.Services.sm_instance.m_activeServer.m_eventListener.m_eventState`, then
`times` (race clock, 50 ticks a second, and the event's time limit) and the local
`players[i]` (`m_localHumanIndex >= 0`) `.m_stats` (`TS.PlayerRaceStats`:
`m_lapsCompleted`, `m_lapsToFinish`, and per lap `m_checkpointTimesForLaps[lap].m_times`,
120 checkpoint times whose first is the lap's start).

`python3 -B experiments/tsu_lap_reader.py` prints lap, current, last and best lap and the
time left twice a second.

- 2026-11-01, Omarchy Linux, hosting a session alone: works live, e.g.
  `lap 3/13  current 0:36.545  last 1:24.095  best 1:24.095  time left 17:25.900`.
  Compared with the game's own lap times by the user: they match exactly. Not yet
  tried as a client on someone else's server (the event controller is then another
  class).

### Fuel, tire wear and speed: where to look (`tsu_vehicle_dump.py`)
From the class and field tables in `global-metadata.dat` (version 29, read offline;
field positions are only known at runtime):
- The local `TS.EventPlayer` has `m_vehicle` (`TS.Vehicle`). Its `m_state`
  (`TS.VehicleState`) has `fuelConsumption`, `tireWear`, `hitPoints`, `inPitArea` and
  `tireCompoundAndChangeTicks`; its `m_stateUpdater` (`TS.CarStateUpdater`) has
  `m_forwardSpeed`, `m_speedOnFrontSurface`, `m_oldSpeed3d` and `inPit`.
- `TS.AIPittingEstimator` (the AI's pit planning) keeps `m_fuelPerLap`,
  `m_tireWearPerLap`, `m_fuelConsumptionAtStartOfLap`: TurboHUD can work out the same
  per lap from the lap starts it already reads.
- Methods named `GetEstimatedLapsWithFuel`, `GetSpeedInMetersPerSecond` and the HUD texts
  "Moving: {0} / {1}Mph" hint at the units, still to be confirmed.

`python3 -B experiments/tsu_vehicle_dump.py` lists every simple field of these objects
with its value once; `--watch` prints the likely ones twice a second while driving.
Not yet run in a race.

### Live delta: car position and checkpoint lines
Found live on 2026-11-01: the local player's `m_statsUpdater` (`TS.PlayerRaceStatsUpdater`)
has `m_checkpoints` (`TS.Checkpoints`), whose `m_checkpoints` list holds the 120
`TS.Checkpoint` objects; each has `m_properties` (`TS.CheckpointProperties`) with the two
ends of its line, `position1` and `position2` (Vector3; x and z are the ground plane).
The car's position is `TS.Vehicle.m_statsNewPosition` (Vector3), updated every tick.
Checked by geometry: with 35 checkpoint times in the current lap, the car sat between
lines 34 and 35, so time i belongs to line i. Lines 1 and 119 record the same time as
their neighbours 0 and 118 (they are close to them); that does no harm.
