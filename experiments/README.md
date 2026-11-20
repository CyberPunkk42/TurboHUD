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

Question: can a Qt (PySide6) window, TurboHUD's chosen stack (`docs/HOW_IT_WORKS.md`), do what
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
values: `TireWearSettings.MaxTireWear` = 5,760,000 (so 2.6 % a lap; on 2026-11-17 found to be only the most
endurance, 7200 s x `StandardTireWearPerSecond` 800: a tire is worn out at its compound's endurance x 800),
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

## Window count probe (`window_count_probe.py`, macOS, Windows and Linux)
Do 17 small overlay windows cost the game more frames than one large window holding the same 17
boxes, or one window the size of the screen? On the user's Mac (2026-11-09, Metal HUD) TSU ran at
120 FPS with TurboHUD closed or one section shown, and at 80 to 110 with all 17; this probe then gave
17 windows 85 FPS and one window 115, so locked the Mac draws every section in one window per screen.
On Windows and Linux each section still has a window of its own: since 2026-11-15 the probe runs there
too, to tell whether one window would help there (and make a tint across a group of sections easy).

1. Quit TurboHUD. Turn on an FPS counter: on the Mac the Metal HUD ("FPS on the
   user's Mac with the Metal HUD" below); on Windows and Linux Steam's own (Steam > Settings > In Game >
   In-game FPS counter), or MangoHud on Linux. Start TSU as you play it (Fullscreen or windowed) and
   start a race, best offline with AI so the race does not end during the run.
2. From the repository folder (`cd` into it first):
   - macOS, Linux: `.buildtools/venv/bin/python -B experiments/window_count_probe.py`
   - Windows (PowerShell): `.\.buildtools\venv\Scripts\python.exe -B experiments\window_count_probe.py`

   (`.buildtools/venv` is the environment the start script `run_turbohud.sh` / `run_turbohud.cmd`
   sets up on its first run.)
3. It runs by itself for about 3 minutes and quits: nothing (30 s), 17 small windows (45 s), one
   large window with all 17 boxes (45 s), one window per screen (45 s), nothing again (30 s). The
   windows are see-through, so the three middle phases look alike: the same boxes in the same
   places, only the name in them changes. The boxes show the phase's name; the terminal prints each phase's start. Note the FPS in each (the
   lowest and highest it shows). `--rest` and `--each` change the times; Ctrl+C quits early.

The boxes have the places and sizes of TurboHUD's sections, read (only read) from its settings file
in its usual folder on each system, and change 20 times a second. The windows let clicks through and
stay on top as TurboHUD's do: on Hyprland each is floated and pinned through requests for the probe's
own windows only (each has its own title, `TurboHUD probe 1` and on); on other Wayland desktops it
runs through XWayland, as TurboHUD does. Checked 2026-11-15 on the Mac (all five phases, quits by
itself; the last phase was cut short before, as closing the windows quit the program). Not yet run
on Linux.

Windows (2026-11-16, the user's PC, TSU in Fullscreen without Exclusive, a 5120x1440 screen, 19 boxes,
one window 5116x1440): every phase showed over TSU's Fullscreen (screenshots in each phase: the boxes over
the race, the probe's windows visible and topmost), and Steam's counter read 120 FPS in each, TSU's cap on
that PC, with one dip to 80 as the one large window appeared. With the FPS capped, the cost was measured as
well, twice, per phase (Windows' performance counters, the first 3 s after each switch left out):

| Phase | DWM's GPU | DWM's CPU (of one core) | the probe's CPU |
| --- | --- | --- | --- |
| nothing | 0.1% | 1 to 5% | - |
| 19 windows | 1.3% | 8 to 13% | 5% |
| one window | 3.9% | 7 to 8% | 7% |
| one per screen | 3.9 to 4.0% | 8 to 9% | 5% |

So on Windows one window costs the compositor about three times the GPU of a window per section (it
blends the whole large window over the game), and no less CPU: the opposite of the Mac. Small on that PC,
but the ratio holds on weaker GPUs, so Windows keeps a window per section (decided with the user on
2026-11-16), and one tint per group there is a small window of its own behind each group.

## Every car of a race, for yellow flags (`tsu_race_recorder.py`, macOS and Windows)

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

On Windows (2026-11-11) it reads TSU straight, as TurboHUD's Python reader does, and writes to
`%APPDATA%\TurboHUD\recordings`:

    .buildtools\venv\Scripts\python.exe -B experiments\tsu_race_recorder.py [--minutes 15]

It also records each event's mode, for the arena modes (Sumo, King of the Hill, Capture the flag,
Battle, Soccer, Tag): a `kind: event` line with the mode, the level type and the classes of the event's
state, controller, logic and settings, then twice a second the fields of those objects (and of the
ones they point to with a mode's name: score, team, flag, hill, zone, ball, goal, round) that changed,
as `player: -1`. While the race cannot be read (an arena mode may have no laps), the event is still
recorded.
The file is brought up to date every 5 s (`SAVE_EVERY`), so a recorder stopped from outside keeps all
but its last seconds (on 2026-11-11 a killed one left an empty file); `read_records` reads such a file.

### First look at an arena event (2026-11-11, Windows, online, 1.4 min)
- A Battle event: `TS.BattleEventMode`, level type 6, logic `TS.BattleLogic` (as seen on the Mac for a
  capture event). The race reads worked in it (617).
- `TS.EventSettings` holds every mode's settings side by side: `battle`, `sumo`, `tag`, `collector`,
  `hill`, `teams`. The logic keeps `m_battleStats` (`m_captureTime`, `m_capturePlayerIndex`,
  `m_captureTeamId`, `m_lastRoundWonTime`, `m_startedRoundsCount`, `m_ranking` with `m_aliveCount`),
  `m_collectorStats` (ranking, team ranking), `m_baseTeams` and `m_tagObjectProperties`.
- Still to record: Sumo, King of the Hill, Soccer, Tag and a special event.

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

## Measurements in races (macOS, the tester's stutter)
Numbers taken in real races, kept for the next time the HUD lags or TSU stutters. The changes they
led to are in `docs/CHANGELOG.md`; what is still open is backlog item 0 and 2 (`docs/BACKLOG.md`).

### The tester's Mac
The tester's Mac: MacBook Pro 14" (M3 Pro), built-in screen 3024x1964 at 120 Hz, no second screen,
Fullscreen, D3DMetal, FPS read with the in-game / CrossOver HUD.

#### FPS (2026-11-08, build 2026.11.08.2)
| # | TurboHUD | Old build (11-07) | 2026.11.08.2 |
| --- | --- | --- | --- |
| 1 | closed | 110 | 115 |
| 2 | every section unticked, 20 reads | 78 | 107 |
| 3 | every section unticked, 5 reads | - | ~100 (90-115) |
| 4 | lap and delta, 5 reads | - | ~90 (85-107) |
| 5 | lap and delta, 20 reads | 62 | ~95 (82-110) |
| 6 | all sections, 20 reads | 58 | ~63, steady near 60 |

- Unticked windows leaving the screen gave back most of the loss with nothing shown (78 to 107).
- The reads are not the cost: 5 a second was no better than 20. TurboHUD with nothing shown costs about 8
  FPS (the reader next to the game in the Wine server, or run-to-run noise).
- Windows above the game are: the more sections, the more frames miss the screen's 8.3 ms refresh, until
  nearly all do and the game holds near 60 (120 / 2) with all sections. Likely macOS compositing the game
  with the windows in step with the refresh, instead of showing it directly. Not known yet: whether the
  number of windows or their area matters more.
- In #5 a big stutter, then about 25 FPS less for 10 s; one read that run took 177 ms. Cause not known.
- The tester's log (19:54 to 20:01, measurements 5 and 6): 20 to 21 trips a read all along (the user's race
  with AI: about 88), so few or no other cars. With lap and delta a read took 17 to 19 ms (0.80 to 0.95 ms a
  trip); with all sections, the game near 60, 8 ms (0.40 ms a trip). The game leaves the Wine server more
  room when it waits for the refresh: the busy game slows the reads, not the reads the game. Once or twice
  in 30 s a read took 150 to 210 ms; whether those are the stutters felt (a game hitch also holds a read up)
  is not known, and #6 had such reads but no stutter. The reader's log was empty, as on the user's Mac.
- Still to get from the tester (nice to have): measurement 7 (closed again at the end), and whether
  `pgrep -fl bottle_reader` printed nothing.

#### CPU per section on the user's Mac (2026-11-09)
Recorded with `top` every 2 s during a race against AI, matched with the log's tick changes; one
section shown at a time (the screen at "more space": 2056 x 1329 for Qt). Averages, 100 = one core:

| Shown | WindowServer | TurboHUD |
| --- | --- | --- |
| TurboHUD closed (perhaps not racing yet) | 41 | - |
| nothing | 42 | 7 |
| local time (changes once a minute) | 48 | 9 |
| running lap (20 times a second) | 48 | 10 |
| track map | 49 | 23 |
| any other single section | 48 to 49 | 9 to 17 |

Each window adds about the same to WindowServer, whatever it shows and however often it changes: a
window's being there costs, not its redraws. So drawing some sections less often would not help; all
sections in one window might. CPU is not FPS: the Metal HUD below is to confirm it in frames. TSU's
own CPU was 243 before TurboHUD started and about 360 after, but the user was probably not racing yet.

#### FPS on the user's Mac with the Metal HUD (2026-11-09)
Apple's Metal Performance HUD (`MTL_HUD_ENABLED=1`, which D3DMetal honours) shows FPS inside the game's
own picture, adding no window above it; nothing in the bottle or the system changes. How to start it:
quit TurboHUD, TSU and Steam in the bottle (`pgrep -fl 'steam.exe|TSU.exe|bottle_reader'` must print
nothing, or the running Steam takes the start without the variable), then, leaving that Terminal open:
`MTL_HUD_ENABLED=1 ~/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine --bottle Steam "C:\\Program Files (x86)\\Steam\\steam.exe"`,
and start TSU from that Steam. If no HUD shows, the user may add `"MTL_HUD_ENABLED" = "1"` under
`[EnvironmentVariables]` in the bottle's `cxbottle.conf` themselves, and remove it after.

In a race against AI on the 120 Hz built-in screen:

| TurboHUD | FPS |
| --- | --- |
| closed | 120 (the screen's most) |
| running, only the local time shown | 120 |
| running, every section shown | 80 to 110, unsteady |

One window costs nothing that shows here; all 17 cost 10 to 40 FPS. With the CPU recording above, the
number of windows is what costs, not what they show. TSU has room to spare on this Mac, so the cost shows
only with many windows; on the tester's it shows sooner. Not measured: every section hidden, and closed
again at the end (TSU froze then, see below).

The probe (`experiments/window_count_probe.py`, 2026-11-09, the user's layout, one large window
nearly the whole screen): nothing 120 FPS, 17 windows 85, one window 115, nothing again 120. So the
number of windows costs, not their area.

Built the same day (backlog item 2): locked, on the Mac, every section is drawn in one window per screen
(`HudCanvas` in `turbohud/overlay/window.py`); move mode keeps a window per section. Not yet seen over
TSU. To check: the Metal HUD with every section shown (expected near 115 to 120, from 80 to 110); move
mode as before (drag, resize, groups, Undo); while locked, a preset shortcut and "bigger"/"smaller" in
the settings moving the sections with nothing left behind; the tint and the theme; the map and the
radar. If anything is wrong, `TURBOHUD_ONE_WINDOW=0 sh run_turbohud.sh` goes back to a window each.

#### One-window HUD and reads on the user's Mac (2026-11-10)
A race against AI with the Metal HUD, read by eye by the user; `main` with the one-window HUD:

| TurboHUD | FPS |
| --- | --- |
| closed | 85 to 120 |
| every section unticked | 100 and more, all the time |
| one section shown, each in turn | about 80, from below 70 to 120 |
| every section shown | about 85 (70 to 100) |

- Closed was 120 all the time on 2026-11-09 and 85 to 120 now, so this race was heavier for TSU and the
  numbers do not compare with that day's. Within this race: showing anything costs about 15 to 20 FPS, one
  section as much as all, and nothing shown costs little or nothing. On 2026-11-09 one section cost
  nothing. Not known: whether the canvas was on (the log's `canvas:` line was not copied), and whether a
  canvas the size of the screen costs when one small part of it changes 20 times a second (the probe's one
  large window lost 5 FPS). The comparison in `RESUME.md`, "To try", is to tell.
- A second race the same evening, the canvas on by the log: only the local time shown gave about 85 FPS
  (70 to 120), as much as every section. The local time changes once a minute, so the canvas costs by
  being there, not by what is drawn in it; with a window each, on 2026-11-09, the local time alone cost
  nothing (in a race with more room to spare). Closed was not noted in this race.
- It looked as before, and move mode, the preset shortcuts and "bigger"/"smaller" worked.
- The track map's kept road: TurboHUD's CPU with only the map shown was 8.2 to 8.8% of a core (about 23%
  before).
- The log (20:13 to 20:17): 1 trip a read, as meant, but a median read of 26.5 to 29.3 ms, 25 to 28 ms of
  it on the game's memory in 84 to 88 reads of it, so about 0.3 ms each: the number of reads of the game is
  the whole cost, and the reader spends about half of its time in them (a read every 54 ms). One to three
  reads in 30 s took over 50 ms (95 to 141 ms). So merging pages further apart ("Offered next") is the
  next step for the reads. HUD frames: content 2% and drawing 16 to 19% of the time.
- TSU quit normally, with TurboHUD quit first and Steam started from Terminal with the Metal HUD.
- No online race could be driven, so the search from the last race is not seen yet.

#### Other points
- Custom races are read since 2026-11-13 (`TS.HostEventController`, found by the search); a Single
  Player event is still to see.
- TSU freezing when it is quit. Seen twice, each time with TurboHUD quit first:

  | When | TurboHUD | Steam started | TSU |
  | --- | --- | --- | --- |
  | tester, 2026-11-06 | quit first | normally | froze on a black screen (Steam's Stop) |
  | user, 2026-11-08, twice | quit first, and TSU first | normally | quit normally |
  | tester, 2026-11-08 | quit first | normally | quit cleanly, no reader left |
  | user, 2026-11-09, 01:10 | quit first (reader ended at once) | from Terminal, Metal HUD | froze, between the race and quitting |
  | user, 2026-11-10 | quit first | from Terminal, Metal HUD | quit normally |
  | user, 2026-11-10, 22:11, Rust reader | quit first | normally | quit normally |

  When frozen: TSU at about 1% CPU (about 300% while running), steam.exe at about 100%, no reader left.
  The reader opens TSU only to read memory and ask for its layout (`PROCESS_VM_READ`,
  `PROCESS_QUERY_LIMITED_INFORMATION`), pausing, attaching to or changing nothing; it ends within a
  second. So no way in the code for it to freeze TSU is known. To tell: the user notes, at each quit of
  TSU, whether it froze and whether TurboHUD ran; and one session with TurboHUD never started.
- The tester's Mac had two CrossOver copies; TurboHUD takes the one in `~/Applications` first, whichever
  TSU runs from (not fixed, did not stop the reader there).

### The tester's stutter, his logs (2026-11-12 to 2026-11-16)
Reported 2026-11-12, after the day's features (class colours, tire column, the player list around the player).
His log (four online races): reads of 4 ms, frames 53 ms apart, content 2 to 4% and drawing 20 to 24% of the
time (16 to 19% on 2026-11-10), about the same with the lap times hidden; no CrossOver graphics warning.
Done (`fix/lap-list-frame-cost`): the lap times and the player list measure less, the Mac's one window draws
again only the sections that changed, and running times and gaps come from kept glyph images (0.06 ms a new text,
from about 0.9 ms at 2x; a few edge pixels differ a little). In build 2026.11.12.6 for the tester. Left:
his log's drawing share (was 20 to 24%), and ask whether the stutter is while
driving or between races (the search from the last race reads for 8 to 11 s).
His log with 2026.11.12.6 (evening of 2026-11-12, stutter mostly while racing): drawing 11 to 19%, frames steady
at 10 a second; but each race read grew from 23 to about 82 reads of TSU's memory (3 to 13 ms), ten a second
through Wine, and one read about every 30 s took 100 to 230 ms. Done (`fix/lighter-race-reads`): other cars'
slow state once a second, with a page plan per kind of read; in build 2026.11.12.7 for him (and 2026.11.13). Left: measure the reads before and after in a race;
what the slow read every 30 s is; TSU's log not found in his bottle ("not known"), so between races it searches
every 10 s for 10 s (Spanish Windows in the bottle?); the search every 10 s after a race could rely on quick looks.
Stutter again with 2026.11.13.3 (2026-11-13): reads cheap, but about once a minute a read and a frame stop
together for 0.15 to 0.35 s (already in the .6 log); drawing 19 to 21% locked. Build 2026.11.13.4 logs each such
freeze with its time and the garbage collection in it, slow collections, and the costliest sections to draw. Next:
his log and stutter times from it; if the freezes are collections, `gc.freeze()` after start (and fewer kept objects);
if the reader's side, CrossOver; whether the stutter stays with TurboHUD closed.
His log with 2026.11.13.4: not garbage collection; one read stalls 140 to 190 ms on an exact 30 s beat from the
reader's start (mostly in reading TSU's memory through Wine), none for 10 minutes in the second race. Next: his
stutter times against :07 and :37; the same track with TurboHUD closed; if only with TurboHUD, fewer reads a second;
why the fuel section costs the most to draw (1.5 to 1.9 ms a frame).
With 2026.11.13.5 (2026-11-13): an evening of huge stutters (two online races, 15 minutes) whose log has no slow
read (slowest 26 ms), no slow frame and collections of 0 to 10 ms, so TSU stuttered while TurboHUD ran smoothly;
5 reads a second stuttered the same as 20. Later the same night, one online race with the user (22 minutes, the
user's log as clean, reads 4 ms): at most one stutter, the same build and settings. His race reads cost about twice
the user's (33 to 54 reads of the game, 7 to 8 ms, against 25 to 28 and 4 ms), and on the bad evening his race data
spread at times over 3,090 MiB (the user's: 375 to 435). His Mac: M3 Pro, 18 GB of memory, about 3 GB left with TSU,
CrossOver and TurboHUD running, and only 2 to 3 GB of disk free: macOS then has no room for swap when memory runs
out, which fits stutters on some evenings and not others. Asked of him: free at least 20 to 30 GB, restart, race
again. On hold until he reports. If the huge stutters come back with that free: TurboHUD closed (does it stay?),
Activity Monitor's Memory Pressure, Swap Used and the largest processes (TurboHUD's own memory, not yet measured
in a race), and the clock times with the log; if only with TurboHUD, its windows over the game (the old FPS cost),
not the reads.
His log with 2026.11.14 (received 2026-11-15, one online race of about 11 minutes, after he freed his disk to
about 244 GB): TurboHUD ran clean. Drawing 9 to 16% of the time (10% once the track map was learnt; was 19 to 24%),
frames steady 53 to 54 ms apart, collections of at most 6 ms, and no stall on the 30 s beat (slowest read 18 to
64 ms, 3 over 50 ms). Left to look at:
- TSU's race data spread from 350 to 417 MiB to 3,086 to 3,110 MiB at one moment (20:51:55 in his log) and stayed
  there, as on his evening of huge stutters (the user's: 375 to 435). TSU's own memory likely grows during his
  sessions. The slowest frames went from 60 to 75 ms to 90 to 95 ms just after. Ask whether his stutter began then.
- One frame 103 ms late (20:57:26 in his log) with 6.3 ms of TurboHUD's own work and no collection: the system did
  not run TurboHUD for about 0.1 s, a hitch of the whole Mac (memory pressure or swap), not TurboHUD's.
- His race reads cost about twice those with 2026.11.13.5: 57 to 69 reads of the game and about 15 ms a read (were
  33 to 54 and 7 to 8 ms), from just after the track map was learnt (107 to 128 pages). At 20 a second the reader
  reads TSU's memory about 30% of the time: the first thing to cut if the stutter comes only with TurboHUD (fewer
  reads a second, fewer pages).
- Searches are long: 13 to 16 s each while on a server with no race (were 8 to 10 s), 10 to 60 s apart, and 38.5 s
  for the search from the last race after it ended. The suspect if his stutter is in the lobby or between races.
Asked of him: whether this session stuttered, at what clock times, while driving or between races; Activity
Monitor's Memory Pressure, Swap Used and TSU's (wine) and TurboHUD's memory in a race; if it stutters, the same
race with TurboHUD closed. With the disk free, swap no longer runs short; the next suspect is memory (18 GB, about
3 GB left) and TSU's growth.
His log with 2026.11.16 (received 2026-11-16, about 11 minutes from 00:54 by his clock: two online races, with
move mode, presets and the new options tried): no error or warning. TurboHUD ran smoothly: frames 53 to 54 ms
apart (about 19 a second), collections of at most 2 ms, drawing 8 to 21% of the time locked (the standings 2 to
3 ms a frame, then Nearby cars and the track map). The new parts worked: layout 8, the race recognised for the
presets by mode ("no preset chosen for it"), presets saved, loaded and named, the short Nearby cars switch, the
standings columns. Left to look at:
- The stall on the 30 s beat is back: one read of 150 to 225 ms (1 trip, nearly all of it in TSU's memory through
  Wine) at :04 and :34 past the minute, eight times (00:55:34 to 01:01:34); none in his log with 2026.11.14. Other
  reads 5 to 11 ms (median), 36 to 57 reads of the game, 71 to 100 pages.
- He reads the race 20 times a second: his own saved setting (the default is 10 since 2026-11-15). Ten halves the
  reader's work and is the first thing to try if TSU stutters.
- TSU's race data within 342 to 345 MiB, 428 MiB near the end (01:05:42): far from the 3,090 MiB of his bad
  evenings.
- Move mode had slow frames of 106 to 215 ms (a window per section there), as expected.
Asked of him: whether this session stuttered, at what clock times (on :04 and :34 would point at the 30 s read),
and the same races with Race reads a second at 10.

### How the slow reads were found (2026-11-04)
Worth keeping for the next time the HUD lags. What fooled the first attempts: offscreen drawing
is far cheaper than real Mac windows, so benchmarks without real windows looked fine.
- Compare with a second connection: `Bottle().connect()` from a script reads the same race
  without the overlay. 28 ms there against 1030 ms in the app showed the app was the cause.
- Profile the real app in a real race: quit TurboHUD, run
  `.buildtools/venv/bin/python -B -m cProfile -o app.prof launch_turbohud.py`, race, then
  `run_turbohud.sh --quit` and read `app.prof`. It showed 122 of 207 s in `QPainter.fillPath`.
- The log's `race reads` line gives trips a read, ms a trip and how much of that is on the
  game's memory; `HUD frames` gives the overlay's side.

## TurboHUD's own memory on Linux (2026-11-20, the user in a session of 5 races)

The log's `memory:` line rose from 189 MB at the start to 542 MB after 18 minutes and never went down:
205 to 469 MB in about 4 minutes of hotlapping on a first track, to 513 MB in a race with about 20 cars, flat
at 513-514 MB on the next two tracks, then to 542 MB on the last. Garbage collections were few and quick (no
generation 2). Fast at first, then slower and flat: more like caches filling than an endless leak.
- The drawn text images (`hud/painter.py`, capped at 64 MB of pixels) and glyph images (16 MB): drawing
  180,000 different lap times and gaps in three sizes offscreen raised the resident size by 97-99 MB, flat
  after the first 30,000. So about 100 MB of the growth is these caches, as meant. About 250 MB is not
  explained yet.
- To find the rest, the 30 s summary has a second line, `memory parts:` (Python's blocks in use, glibc's heap
  in use and freed but held, the drawn-text caches). With `TURBOHUD_TRACE_MEMORY=1` set before starting, it
  also lists the places in the code where Python's memory grew most since the last summary (`memory grew:`,
  tracemalloc; slower). Which of the three grows says where to look: Python's blocks (objects kept), the heap
  in use (Qt's or Python's data), or freed but held (memory freed in pieces glibc keeps, more with threads).
- A race with that line (Coco Jambo, about 20 cars, 3 minutes): 234, 381, 420, 448, 453, 463 MB; glibc's heap in
  use grew with it (133 to 363 MB), freed but held stayed 3-8 MB (no fragmentation). The biggest step (+147 MB in
  30 s) came as the text outline cache filled from 182 to 512. Measured: a text's stroked outline with round
  joins is 4,600-7,400 curve pieces, about 220 KB, and 512 of them held about 114 MB, to fill text images that
  are kept anyway. Outlines are no longer kept (`outline_path`): 512 names now take about 8 MB. Once every cache
  was full the total levelled off (453, 463 MB). Python's blocks still rise slowly (6,000-8,000 every 30 s,
  under 1 MB a minute): to trace.

## TSU's sun, for a compass with north from it (2026-11-20, Windows, the user in a session of 4 races)

Asked for by the user: could the compass take north from the game's sun? TSU's metadata (read only) has
`TS.LocationProperties.sunDirection` (one number, 0 by default) and `time` (10.0 by default), reached as
`EventState.m_level.m_nature.m_locationProperties`; TurboHUD logs them once an event (`sun: track ...`,
`chore/log-sun`). `LevelProperties.location` is no plain number or string (not read; not needed). The user drove
and reported the compass's heading (degrees clockwise from up on the track map) and where the sun or the car's
shadow was, read against the log:

| Track | `time` | `sunDirection` | Sun seen at (heading, what was seen) |
|---|---|---|---|
| Abu Dhabi GP v1.03 | 16.95 | 107.7 | ~110-130° (141°: ahead, slightly left; low, seen from the cockpit) |
| WT Raceway Laguna Seca v1.0 | 15 | 300 | ~300° (181°: right; 308°: dead ahead; high) |
| Sebring International Raceway | 10 | 75 | ~235-270° (0°: shadow to the south-east; 260° and 270°: shadow straight behind; 165°: shadow left, a little back; high, shadow nearly under the car) |
| Coco Jambo Club Layout v1.2 | 15.8 | 0 | ~0° (98°: sun left, slightly back, shadow right and long), predicted before looking |

What it means: TSU's sun crosses the sky in a straight line, rising opposite `sunDirection`, passing nearly
overhead around midday and setting at `sunDirection`. In the afternoon (15, 15.8, 16.95) it stands on the
`sunDirection` side, lower the later; in the morning (Sebring at 10) on the opposite side, already high. So
`sunDirection` is west, in the compass's own degrees (clockwise from up on the map, +z), on every track, and
**north is `sunDirection` + 90°**. Its height follows `time` (not modelled; a compass needs only the side).
Sebring alone looked wrong until the model took the morning into account; Coco Jumbo was predicted before the
user looked and matched. A track left at the default 0 has its sun all the same (Coco Jumbo).

Checked with the compass taking north from the sun (`feature/compass-north-from-sun`; 2026-11-20, Linux, the
user in a session of 5 races of 2 laps). Headings are now the compass's own, from north; the sun's bearing is
worked out from what was seen, to about ±20°:

| Track | `time` | `sunDirection` | Heading, what was seen | Sun at | Expected |
|---|---|---|---|---|---|
| MR Road Atlanta (PLM '26) R v3 | 10 | 0 | 109° E: shadow straight behind (337° NW also read) | ~109° | east (morning) |
| Coco Jambo Club Layout v1.2 | 15.8 | 0 | 157° SE: shadow to the left | ~247° | west (afternoon) |
| Giza International Circuit V1.01 | 16.6 | 352 | 263°: sun ahead, slightly right | ~270-280° | west |
| Abu Dhabi GP v1.03 | 16.95 | 107.7 | 303°: sun ahead, slightly left | ~280-290° | west |
| Sebring International Raceway | 10 | 75 | 285°: sun behind | ~105° | east (morning) |

All five match: the afternoon sun in the west, the morning sun in the east, on tracks with the default sun and
with one turned by the track's maker (Giza, Abu Dhabi). Around midday the sun stands a little to the south
(~247° and ~109° at 15.8 and 10), as on a real track in the northern hemisphere.
