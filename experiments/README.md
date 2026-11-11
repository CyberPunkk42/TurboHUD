# Experiments

Throwaway probes that answer one question each before TurboHUD's design is fixed.
They are not part of the app, with one exception: `tsu_memory_probe.py` is what the
Steam launch option runs on Linux (it only starts the app's probe, see below), so it
must stay where it is.

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

### Fuel, tires and speed: confirmed in a drive (2026-11-01)
With fuel and tire wear on, `TS.VehicleState.fuelConsumption` and `.tireWear` count what
is used up, from 0. Per lap (about 1:22) they grew by about 10,100 and 151,000; the
player saw about 6 % fuel and 2.5 % tires per lap. Constants from the metadata's default
values: `TireWearSettings.MaxTireWear` = 5,760,000 (so 2.6 % a lap),
`FuelSettings.MaxFuelConsumptionPerSecond` = 150 (3 a tick at full throttle); the tank is
the event's `FuelSettings.maxFuelConsumptionInEvent` (reached through
`CarStateUpdater.m_fuelSettings`), not yet read live. `CarStateUpdater.m_forwardSpeed`
peaked at about 57, taken as metres a second (205 km/h), not yet compared in game.
Some checkpoints are two lines at the same spot (6/7, 12/13, 23/24, 28/29 on the track
driven) or one line in two pieces (109/110, 111/112), with the same time.

### Throttle and brake (2026-11-01)
`TS.CarControls` (`CarStateUpdater.m_controls`): `gas` and `brake` are floats but only
take 0, 1/3, 2/3 and 1 (also kept as `gasInThirds`/`brakeInThirds`, int 0-3): TSU rounds
input to thirds. Sampled together with the Steam Input virtual pad (`/dev/input/js1`,
"Microsoft X-Box 360 pad"): game throttle follows axis 5 (right trigger, correlation
0.97), brake axis 2 (left trigger, 0.8); triggers run from -32767 to 32767.
While a race is set up the reader reports `m_eventListener is null`; in the menu
`m_activeServer is null`.

## Memory inside the CrossOver bottle (`bottle_memory_probe.py`, macOS)

Question: can TurboHUD read TSU's memory on the Mac, where TSU runs as a Windows game
in a CrossOver bottle, without weakening the system?

From outside the bottle, no. TSU's Mac process is CrossOver's `wineloader`, signed by
CodeWeavers with the hardened runtime and without `get-task-allow`, so macOS refuses
`task_for_pid` on it (checked: KERN_FAILURE, 5) unless System Integrity Protection is
turned off or CrossOver is signed again. Neither is acceptable.

From inside the bottle, yes. There every program is a Windows program under the same
Wine server, which already holds each bottle process's task port, so `OpenProcess`
(PROCESS_VM_READ) and `ReadProcessMemory` work as on Windows, for programs of the same
bottle only. TSU's own `UnityCrashHandler64.exe` and Steam's overlay already do this.

The probe runs in the bottle with the portable Windows Python of the overlay probe. It
only reads: finds TSU.exe, lists its memory (VirtualQueryEx), finds the mapped
`global-metadata.dat`, times reads, then runs TurboHUD's own lookup by name
(`turbohud/core/il2cpp.py`, `race.py`) and, if a race is on, reads it as the HUD would.
It prints no player names or IDs.

### Run it
1. Start TSU in CrossOver (any screen; for the race reads, drive onto a track).
2. `sh experiments/run_bottle_memory_probe_mac.sh` (`--reads N` for the number of race
   reads, 40 by default). Bottle `Steam` unless `TURBOHUD_BOTTLE` names another.

### Results
**macOS 27.2, CrossOver 26.3, TSU in its main menu (2026-11-04):**
- TSU.exe found and opened for reading; 1040 readable regions, 0.93 GiB, listed in
  0.12 s.
- `global-metadata.dat`: Wine gives no mapped file name, so it is found by its first
  bytes; its first 4 KiB match the file in the game's folder.
- Reads: about 225 µs each whatever the size up to 4 KiB (a round trip through the Wine
  server), 0.7 to 0.9 GiB/s for large ones. A race read (about twenty small reads) so
  comes to about 5 ms, fine at 20 a second; the online search reads 1 GiB in about
  1.5 s.
- TurboHUD's lookup unchanged: `TS.Services` found in 1.7 s (the class records are in
  Windows' private heap memory, used where Linux has `[heap]`), its 17 fields and
  `sm_instance` read. The IL2CPP layouts match the Linux build.
- No race was on (`m_activeServer is null`). A race the game runs as a client (online,
  or hosted with only AI) is found by a search, which the probe first left out.

**The same, in a race alone (2026-11-04, 1 player, lap 2 of 3):** memory 2.01 GiB,
`TS.Services` found in 4.6 s. 40 race reads at 20 a second through `LapReader`,
unchanged: median 17.2 ms, the first (with the lookups it keeps) 559 ms. Laps, race
clock, the car's position and its state (fuel, tires, speed) all read. A read costs the
same up to 4 KiB, and a race read makes about 70 small ones, so reading larger blocks
(and serving small reads from them) should make it several times quicker.

**Online, hosting with 13 AI (the game a client; 2026-11-04):** the search found the
race (`TS.ClientEventController`) in 4.1 s over 1.78 GiB; all 14 players, the race
clock, laps, positions (from the replay recorder) and the car read. The first read took
9 s (the search and the lookups it keeps). After that a race read took 113 ms
(median): too slow for 20 a second. It made 451 small reads, but on only 72 pages of
4 KiB, so reading each page once per race read would bring it to about 72 reads, some
18 ms. That page cache is needed before the Mac HUD reads online races. The searches
(about 4 s each, reading all the game's data at once) made TSU stutter.

**With TurboHUD's Windows reader (`turbohud/tsu/winmemory.py`, same online event type,
2026-11-04):** the probe now connects as the app will.
- Page cache (each 4 KiB page read once per race read): 74 to 77 reads of the game
  per race read instead of 451, 19.7 ms (median, slowest 26 ms) instead of 113 ms.
- Paced search (1 MiB pieces, reading a quarter of the time, so the Wine server is
  never held long): no stutter noticed for sure, but searching all 1.61 GiB took
  about 35 s, three times over, so the race showed only after about 110 s.
- Where the hits are, in address order: the TS.Services class record within the first
  0.04 GiB of the searched memory, TS.ClientEventController's within 0.11 GiB, the
  online race controller within 0.31 GiB. So the search now goes from the lowest
  address up and stops at the first good hit: connected in 1.0 s, the online race read
  after 14 s, and 60 reads at 19.7 ms.

A native Mac program can talk to one in the bottle over TCP on 127.0.0.1 (Wine uses the
Mac's own sockets): 78 µs per round trip, measured with a small echo server.

**So live data on the Mac can work like on Linux:** a small reader inside the bottle (in
place of the Linux probe) answers the same read-only questions over a local socket, and
the native TurboHUD asks them and draws, with no system change. The same Windows reading
code serves TurboHUD on Windows itself, there without a socket.

Settled and built (2026-11-04, `turbohud/tsu/bottle.py`, `bottle_reader.py`): TurboHUD
starts the reader with CrossOver's `wine --bottle` and asks it over its standard input and
output, so there is no socket, port or secret.

## Window count probe (`window_count_probe.py`)
Do 17 small overlay windows cost the game more frames than one large window holding the same 17
boxes? TurboHUD draws each section in its own window; on the user's Mac (2026-11-09, Metal HUD) TSU
ran at 120 FPS with TurboHUD closed or one section shown, and at 80 to 110 with all 17. The probe
answers whether rebuilding the overlay as one window would help, or whether one large, mostly
see-through window costs by its area instead.

1. Quit TurboHUD. Start TSU with the Metal HUD (`docs/CONTINUE_HERE.md`, "FPS on the user's Mac with
   the Metal HUD"), in Fullscreen, and start a race.
2. From the repository: `.buildtools/venv/bin/python -B experiments/window_count_probe.py`
3. It runs by itself and quits: nothing (30 s), 17 small windows (45 s), one large window with all 17
   boxes (45 s), nothing again (30 s). The boxes show the phase's name; the terminal prints each
   phase's start. Note the FPS in each. `--rest` and `--each` change the times; Ctrl+C quits early.

The boxes have the places and sizes of TurboHUD's sections, read (only read) from its settings file,
and change 20 times a second. With the user's layout the one window is nearly the whole screen
(2055 x 1290). Checked 2026-11-09 with real windows on the Mac (all four phases, quits by itself); not
yet measured over TSU.

## Every car of a race, for yellow flags (`tsu_race_recorder.py`, macOS)

Asked for by the user (2026-11-11): yellow flags as in F1, DTM or GT racing need the state of the
other cars (off the track, slow or stopped, spun, wrecked). TSU has no flags of its own (its only
"Yellow" names are colours). The recorder reads, through the reader in the bottle and only reading:
10 times a second every car as TurboHUD sees it (position, velocity, heading, pits, checkpoints) and
the checkpoint lines; twice a second every field of each car's `TS.EventPlayer`, `TS.Vehicle`,
`TS.VehicleState` and `TS.CarStateUpdater`, and of the objects two steps on whose field names sound
useful (wreck, stuck, respawn, wrong way, surface, wheel, shortcut, damage), only what changed. It
writes `~/Library/Application Support/TurboHUD/recordings/race-<date>-<time>.jsonl.gz` (player names:
never in the repository). Close TurboHUD first; Ctrl+C ends it.

    .buildtools/venv/bin/python -B experiments/tsu_race_recorder.py [--minutes 15]

### First look (2026-11-11, a race on the user's Mac with one other car, 6 s)
- Each car's wheels: `TS.CarStateUpdater.wheels` is a `TS.WheelUpdater` with
  `m_surfaceMaterialFront1/2` and `m_surfaceMaterialBack1/2`, the four wheels' surfaces, each a
  `TS.TSMaterialProperties` (`grip`, `braking`, `acceleration`, `steering`, `viscosity`,
  `extraTireWear`, `dust`, `leaveSkidmark`, `leaveTrail`, `pit`, `damage`, `m_layer`). One car was on
  grip 1.0 with skid marks (tarmac), the other on all four wheels with grip 0.5, braking 0.5, extra
  tire wear 1.0, dust and a trail (grass or dirt). Filled in for both cars, not only the local one.
  Also `allWheelsG`, `frontWheelsG`, `backWheelsG` (about 0.5 to 1.3, meaning not known yet).
- `TS.VehicleState`: `hitPoints`, `disabled`, `reversing`, `inPitArea`, `spawnTick`, `spawnCount`
  (a respawn?).
- The checkpoint line at the start was 100 game units across: whether the lines reach the track's
  edges or beyond is still to see.
- Still to record: a race against AI with the local car off the track, stopped and spun; then online
  as a client, where the other cars' fields may never be filled in (only the server runs them).

### Online as a client (2026-11-11, the user's Mac, 3 min, one other driver)
A session hosted by someone else, the other car a human on their own computer (the user's word); both
cars' positions came the client way (TSU's recorder, on its 1/1024 grid). For that other car the
client had, live: the four wheel surfaces (1,331 wheel readings on tarmac, layer 13, grip 1.0; 38 on
layer 18, grip 0.5 with dust and extra tire wear; 38 on layer 17, grip 0.93, likely kerbs; a few on
layers 0 with grip 0, likely a wheel in the air, and 22 and 24 with grip 1.0), `m_forwardSpeed` (19.7
to 61.3), `m_sliding` (0 to 0.96), and `allWheelsG`, `frontWheelsG`, `backWheelsG` (0.04 to 1.7; 0
for the local car when in the air, it seems). The local car (one respawn, some reversing) had
`VehicleState.spawnCount` 0 to 1, `spawnTick` set and `reversing` going on and off; the other car did
neither, so whether those come through online for others is not known yet. `hitPoints` stayed 500 for
both (no damage in the event?). So a yellow flag can go by each car's wheel surfaces (all four off
the tarmac), speed (slow, stopped, backwards) and sliding (spun), online too.
