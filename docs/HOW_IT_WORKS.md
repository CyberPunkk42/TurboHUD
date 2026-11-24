# How TurboHUD works

TurboHUD is an overlay for Turbo Sliders Unlimited (TSU): small see-through boxes on
top of the game that show race information the game does not show itself, or not as
clearly. This document explains what it shows, where the data comes from, and what it
does (and does not do) to the game, to your RAM and to your system; then, for developers, why it
is built with Python and Qt, how it is built and shipped, the rules for the overlay and where
everything is in the code.

State: 2026-11-15. Live race data works on Linux (the native TSU build), on macOS (TSU in
CrossOver; see "On macOS" below) and on Windows (see "On Windows" below). The rest of this
document describes Linux where they differ.

## What it shows

Each part of the HUD is its own box ("section"). In move mode you drag, resize, hide,
group and centre them; their places are saved. In move mode each section has a window of
its own. While locked, on the Mac, all of them are drawn in one see-through window per
screen instead: every window above the game costs it frames (17 windows took a Mac from
120 to 85 FPS, one window with the same boxes to 115). `TURBOHUD_ONE_WINDOW=0` turns this
off. On Linux and Windows each section keeps its own window for now.

| Section | What it shows |
|---|---|
| Race progress | Lap 2/3, and the time left in a timed race |
| Current lap | the current lap time, counting |
| Delta to best | ahead (green) or behind (red) your best lap, live between checkpoints |
| Delta bar | the same as a bar, right when ahead, green while gaining and red while losing time |
| My laps | your last and best lap times (purple the race's fastest, green your own best), with a bar per sector below |
| Fuel | fuel left, laps it lasts at your recent use, fuel saved or burnt this lap; a level bar |
| Fuel to finish | laps of fuel to spare (green) or missing (red) for the finish |
| Tire wear | tire life left and the laps it lasts; a level bar |
| Car health | car health as the game counts it; yellow with less downforce, red when slowed; a level bar |
| Car status | health, tires, fuel and fuel to finish in one box, a level bar under each of the first three (`Row.level`, `hud.row_bars`); only the rows the event has (`race.car_status_rows`), its tint ending below the last (`hud.tint_height`); off at first (`hud.OFF_AT_FIRST`), at Fuel's place |
| Slipstream | how strong the slipstream is (of the event's most), with a bar; the downforce it costs; the event's drafting at the start ("Up to -10% drag, -80% downforce, 30 m, 20°": the most it takes off the air resistance and the downforce, how far behind a car it reaches and how far off its line), then the last lap's time in a slipstream; who drafts you |
| Speed and pedals | km/h or mph, yellow while coasting; throttle and brake bars beside it; as an option the gear and rev lights |
| Nearby cars | the leader, then the car ahead of and the car behind you on the track (3 of each with its short list off): position, flag, name, PIT with its timers, clan tag (or class and place in it), tire, and the live gap to you (or +1 L for laps), DNF, DSQ or AFK in the gap's place |
| Standings | every driver in race order (by class, under class lines, in a multi-class race) with place and name, and as chosen: flag, clan tag or class, overall place, lap, gap to the leader (of the class), tire, best lap (the race's fastest in purple) and last lap, or CUT, JUMP, PIT, DNF (TSU's Retired flag on the car, `VehicleState.disabled`), DSQ (its Disqualified flag) or AFK (under 10 km/h for over a minute) |
| Blue flag | a navy bar that fades in when a car about to lap you is within 2 s |
| Yellow flag | a car off the track, slow, stopped, spun, the wrong way or put back in your sector or the next, by sector and driver; CAR STOPPED AHEAD or WRONG WAY AHEAD for one up to 5 s ahead on the road |
| Penalties | SHORTCUT with the seconds TSU slows you for a shortcut; JUMP START for a false start |
| Race leader | a grey banner (`LEADER_GREY`) for 6 s, fading in and out over 0.67 s (`LEADER_FADE`): "New Race Leader - name" once a new driver has led for 5 s (not the player's own car while driving: `leader_banner`), "Race Winner - name" on a black banner with a waving checkered flag (the user's picture, `assets/resources/banner_winner.png`) as the winner finishes; from the standings' order, with no read of its own |
| Battle | only while watching (a replay, or spectating): "Battle for P<n>", "Possible Overtake" and "name vs name" on the same banner, when a car within 1 s of the one ahead has gained 0.1 s over 3 s or sits within 0.4 s, for 2 s, or "Group around name" and the drivers behind for 3 cars or more each within 1 s of the one ahead; not in the opening lap; one at a time, the highest place, 6 s, the same two not again for a minute; from the standings' order and live gaps, with no read of its own |
| Watched driver | only while watching: "Watching" and "P<n>  name" on the same banner each time the camera turns to another driver and stays on them for 1 s (in a replay the replay camera's driver, `_followed`; spectating the one the spectator camera follows, `spectated_driver`: the cockpit view's camera, `m_targetChooser.m_target`); 6 s, at once in place of one showing, the same driver not again until the camera turned away; no place in an arena event |
| Compass (built, not offered yet: `hud.COMPASS_AVAILABLE`) | your car's heading (`compass_view`: its `forward`, else its velocity) in whole degrees clockwise from north: by default from the track's sun (`sun_north`: TSU's `LocationProperties.sunDirection`, read once an event with the track's name, is where the sun sets, so north is it + 90°), with a small sun by the readout; with **Compass north from the sun** off, up on the track map (+z; the map never turns a track): a dial that turns under a fixed red needle and line, and "047° NE"; the needle and N sky blue with the colour-blind option |
| Radar | your car and the cars around you, when one is within 0.5 s behind, beside or ahead: red beside, yellow closing in, grey not counting, a class colour for another class, arrows for cars past its edge; the slipstream behind cars ahead and the car you draft outlined; cars at their real size, zoomed in on the closest car, to 3.5 car lengths at the closest (cars further behind arrows at its edge), out quickly and in gently; every car's position read in one request at the end of a read, so all are of the same moment; by default only in cockpit cameras |
| Track map | the track from above, with you, the race leader (gold), the next car ahead (red), the next car behind (green), backmarkers between you and the car ahead (small, bluish), and as an option the other cars (faint grey) |
| Clock | your computer's clock, once TSU runs |
| Time since start | how long TurboHUD has run; only on a system TurboHUD cannot read TSU on, instead of the race sections |

Spectating an online race, only Race progress (with "Spectating" and the leader's lap),
Nearby cars (gaps to the leader), Standings, the track map (every car), the Race leader,
Battle and Watched driver banners and the Clock show.

The race sections appear once the cars are on the grid and go away in the lobby. In
the menus only the Clock shows; while TurboHUD waits for TSU, nothing does.

## The three parts

```
 Steam ──starts──▶ probe (python3) ──starts──▶ TSU.x64 (the game)
                     │   reads the game's memory, read-only
                     │   answers questions over a private socket
                     ▼
                 TurboHUD (the overlay app, Qt) ──draws──▶ the HUD windows
```

1. **The game, TSU.** Unchanged. Nothing is installed into it, injected into it or
   patched in it. TurboHUD never writes to the game's memory or to its folders.
2. **The probe** (`turbohud/tsu/probe.py`; the downloaded app is the probe itself with
   `--probe`, a start from the source uses `experiments/tsu_memory_probe.py`).
   A small Python program that Steam runs through the launch option. It starts TSU as
   its own child process, and then answers read-only questions about the game's memory
   from TurboHUD. That is all it does.
3. **TurboHUD** (`turbohud/`). The overlay app you start with `run_turbohud.sh`. It
   asks the probe for the race data about 10 times a second (20 or 5 if set so in the
   settings window), works out what to show and draws the sections. A section that is
   unticked is not drawn; on the Mac its window also leaves the screen.

You can start and quit TurboHUD at any time; the game does not notice. The probe lives
as long as the game: it starts with it and ends with it.

## Why there is a probe: the permission

Linux (with the Yama setting most systems use, `ptrace_scope = 1`) lets a program read
another program's memory only if it started that program. TurboHUD itself did not start
TSU, so it may not read it. The probe did: Steam starts the probe, the probe starts TSU.
So the probe may read TSU's memory, and only TSU's.

This needs no `sudo`, no `setcap`, no root, and no change to the system's security
settings. Nothing else on the PC gains any permission.

The probe talks to TurboHUD over a private socket in your user's runtime folder
(`/run/user/<uid>/turbohud/tsu-memory.sock`, only your user can open it, and the probe
also checks the connecting program belongs to you). There is no network connection:
nothing leaves your PC.

The probe understands four questions, all read-only:

| Question | What it does |
|---|---|
| `maps` | lists the game's memory areas (like `/proc/<pid>/maps`) |
| `read` | copies some bytes from one address |
| `read_many` | copies the same number of bytes from many addresses at once |
| `search` | finds where a value is stored (used to find an online race, see below) |

Reading uses the Linux call `process_vm_readv`: it copies bytes out of the game's
memory into the probe's. It cannot change anything in the game.

## On macOS: a reader in the bottle

TSU runs in a CrossOver bottle. macOS refuses a Mac program access to its memory
(CrossOver's Wine loader is signed with the hardened runtime), and TurboHUD does not ask
anyone to turn that protection off. Inside the bottle, a Windows program may read another
with `ReadProcessMemory`. So:

```
 CrossOver ──runs──▶ TSU.exe (the game)
                       ▲ read-only
 turbohud-reader.exe ──┘  (a Windows program in Rust, in the same bottle)
       ▲ questions and answers over its standard input and output
 TurboHUD (the native Mac overlay app, outside the bottle)
```

TurboHUD looks for `TSU.exe` among the running programs, finds CrossOver and the bottle,
and starts the reader there: `turbohud-reader.exe`, a Windows program in Rust (`reader/`; in
the app, or for a start from the source in `.buildtools/reader`, built by `tools/get_rust.sh`).
The older reader in Python (`turbohud/tsu/bottle_reader.py`, with a Windows Python set up by
hand) is only for a start from the source with `TURBOHUD_PY_READER=1`; the app has shipped
without it since 2026-11-11. Nothing is installed into the
bottle. Only TurboHUD holds the pipe, so there is no port, no socket and no secret. The
reader ends when the pipe closes or TSU quits.

It answers the same kind of read-only questions as the Linux probe. A read of the game
costs about 250 µs there (a round trip through the Wine server, which also serves the
game), so TurboHUD reads each 4 KiB page once per race read: about 20 ms. As the game keeps
its objects in place during a race, each race read starts with one question for all the
pages the read before used, and the reader reads pages close together in one call. A search reads
in 1 MiB pieces, half of the time, and takes about 15 s if it has to cover all the data; it
stops at the first good hit, so a race is expected within about 4 to 6 s (worked out from a
search at a quarter of the time; not yet seen in a race).

## On Windows: a reader beside the game

Windows lets a program read another of the same user (`OpenProcess` with `PROCESS_VM_READ`,
then `ReadProcessMemory`), so there is no probe and no launch option. TurboHUD starts the same
Rust reader as on the Mac (`turbohud-reader.exe`, in the download), as an ordinary program
beside TSU, and asks it over a pipe; where it is missing, TurboHUD reads in Python itself
(`turbohud/tsu/winmemory.py`). A search reads with 4 threads: about 6 s for all of TSU's data.

Also on Windows: shortcuts through `RegisterHotKey` (`turbohud/overlay/windows.py`); AMD Software
takes Ctrl+Shift+L on some PCs, so Ctrl+Shift+F12 is the spare. Move mode brings its panel to the
front, so TSU lets go of the pointer it hides in a race, and locking gives TSU the focus back. Each
section keeps its own window (one window per screen cost the compositor about three times the GPU,
2026-11-16), and one tint per group is a small window behind each group. One TurboHUD runs at a time
(`turbohud.lock`); Windows has no command socket, so a second start only says so. The gamepad's
triggers are not read (XInput would be the way).

## How it finds the race in the game's memory

TSU is made with Unity using IL2CPP: its code is compiled, but it keeps a description of
all its classes and fields (`global-metadata.dat`), which is loaded into memory. Every
class the game uses has a record pointing to its name and to its fields, each with its
name and position. So TurboHUD needs no fixed addresses (those change with every start
and every game update): it looks everything up by name each time the game starts.

The race data is found along this path of objects:

```
TS.Services.sm_instance          (a static field: always findable)
  .m_activeServer.m_eventListener  the race controller (offline, hotlap, hosted online;
                                   in a Custom race see "Online races" below)
  .m_eventState                    the race
      .times                       race clock and time limit
      .players[i]                  every player (the local one is marked)
          .m_stats                 laps, checkpoint times, finished
          .m_playerInfo.m_profile  name and flag
          .m_vehicle               the car: position, fuel, tire wear, health,
                                   speed, throttle and brake, pit flags,
                                   velocity and direction
```

A lap has 120 checkpoints on the tracks seen. Each player's list of checkpoint times is
the backbone: lap times, the delta to your best lap, the player order and the gaps
between players all come from it, made live between checkpoints by the cars'
positions.

TurboHUD reads the game's memory while the game runs, so a list can be read halfway through
TSU adding to it: the newest checkpoint time may still be 0. A lap's times therefore stop
before a time not yet written (`race.written_times`; a real time is 0 only at the very start
of a race), and a finished lap read so is read again instead of kept. Without that, a gap to
the leader showed about minus the race clock for a frame or two.

What does not change during a race (field positions, finished laps, the track's
checkpoint lines) is read once and kept. A normal update then needs about twenty small
reads and takes about 10 ms.

### The track map

The track map's shape is learnt from where the cars drive, not from the checkpoint
lines: on some tracks those are long and set off to one side, far from the road.
TurboHUD records each car's path, and once any car has driven a whole clean lap (not
through the pits, never with all four wheels off the tarmac, standing or going
backwards: each of those starts its path afresh), that lap is the track. Until then the map shows the longest stretch driven so
far; with AI or other players on track it is learnt within about a lap. The learnt
track is saved (see the files below), so the next race on that track has its map at
once. No track file of the game is read, so it works on every track, online too.

### Online races

When you join an online race, or host one that only has AI drivers, your game runs as
a client: the race is then in a `TS.ClientEventController` that no static field leads
to. TurboHUD finds it by its class, with one `search` of the game's memory, then keeps
using the object it found until the race ends.

As a client the game keeps no car positions where the offline race has them. TSU
records every race for its replays, though, and its recorder
(`TS.EventRecorder.m_lastQuantizedVehicleStates`) holds each car's last recorded
position, which TurboHUD reads instead. If recording is off, it works the positions
out from the checkpoints and each car's velocity (see the limits below).

A search reads all of the game's data once (on Linux about 1.5 to 2 seconds, one CPU
core busy; on Windows about 6 s with 4 threads; on the Mac, through Wine, longer). So TurboHUD searches only when it has to: when there is no offline or hosted
race, and TSU's own log file says an event is running (TSU writes "Event started." and
"Event ended." into `log.txt` as it happens, with dated copies in `Logs/`; TurboHUD only
reads them, and goes by the newest). In
menus and lobbies it does not search at all. A log counts only when TSU wrote it since it
started and it names an event: some players' TSU stops writing it, and then TurboHUD
searches anyway, as it does with no log at all, on the waits below. Then, between
searches, it also takes a quick look every 2 seconds where the last race was (256 MiB
from just below it, a few percent of the data), as TSU tends to put the next race there. While an event runs without a race found
yet, it waits 10 seconds after each search before the next; after a minute of searches that
find nothing, the wait doubles up to 60 s, and ends at once when TSU's log newly says an
event runs.

When you spectate, the race is there but has no local player. A search then finds no
race of yours to stop at, so it reads all the data once and takes the race it found to
watch. TurboHUD keeps reading that race as long as its clock runs, with no more searches,
and each read would see you join it. Once its clock has stood for 5 s the race counts as
over, and TurboHUD searches again every 30 s while TSU's log says an event runs. The HUD
then shows the race without a car: the leader's lap, the gaps to the leader, the lap times
and every car on the map.

When you host an online race with other players, TSU runs the server inside your game,
and the race is found the normal way, with no search.

A Custom race (and, expected the same, a Single Player event) has no active server: its race
is in a `TS.HostEventController` with the same fields as the client's, and the same search
finds it. A search looks for an online race's, a hosted race's and a replay player's class in one pass
through the game's memory (since 2026-11-18 also with the Rust reader, on the Mac and Windows; it took
three passes there, 12 to 15 s in CrossOver). A reader built before then is asked one class a pass, as
before (`Pipe.find_pointers_any`).

## Other inputs

- **Gamepad, for the throttle and brake bars.** TSU rounds throttle and brake to
  thirds, so the bars would move in steps. TurboHUD therefore also reads your gamepad's
  triggers through the Linux joystick interface (`/dev/input/js*`), which your user may
  read anyway. It opens only devices that name themselves a gamepad or controller,
  never a keyboard.
- **TSU's log file**, read-only, as above.

## The windows (Hyprland)

On Hyprland (Wayland), Qt alone cannot keep a window on top of a fullscreen game. So
TurboHUD asks Hyprland, at runtime, to float, place, pin and raise its own windows and
to keep the keyboard focus away from them (`hyprctl dispatch`, aimed only at
TurboHUD's own windows by their address). It does not change any Hyprland or Omarchy
configuration file or setting, and nothing it asks for outlives TurboHUD. In move mode
it lets its windows take the mouse so they can be dragged; when locked they let every
click through to the game.

Shortcuts: Wayland lets no program catch keys meant for another window, so while TurboHUD
runs it adds Ctrl+Shift+L, Q and 1 to 5 to Hyprland's live keys (`hyprctl eval` with
`hl.bind`, on older Hyprland `hyprctl keyword bindd`), each running the command below. It
first looks at `hyprctl binds` and leaves every key something else has (Ctrl+Shift+F12 for
move mode where Ctrl+Shift+L is taken). Its binds are labelled "TurboHUD shortcut", and it
removes only those at quit. They live in Hyprland's memory only: a reload of Hyprland's
settings drops them, and TurboHUD, listening on Hyprland's event socket, adds them again; a
restart of Hyprland ends them, also after TurboHUD crashed. A TurboHUD that did not quit
leaves them until then (pressing them does nothing), and the next start
takes them over.

## Commands from the command line (Linux, macOS)

`run_turbohud.sh --toggle`, `--move`, `--lock`, `--settings`, `--preset 1` (or 2 to 5)
and `--quit` tell the running TurboHUD what to do. It listens on a socket in your user's private runtime
folder (`/run/user/<uid>/turbohud/control.sock`, only your user can open it); the
command connects, sends one word, gets "ok" and ends. A second start of TurboHUD uses
the same way to switch the running one to move mode instead of opening a second copy.

## What it does to RAM, CPU and the game

**Your RAM and hardware.** Reading another program's memory is an ordinary memory
copy, the same kind of work any program does all the time. It does not wear out RAM or
any other hardware, and it does not touch the disk. TurboHUD writes only its own small
files (below).

**The game.** The game is never paused, stopped, hooked or changed. Its memory is only
copied from. If TurboHUD or the probe hits an error, the game keeps running: the probe
answers errors with an error message and never ends the game, and TurboHUD keeps its
windows up and tries again. Tested: if the probe itself is killed or crashes while
you play, the game keeps running (TurboHUD then shows "waiting" until the next start).
When Steam stops the game, the probe passes the stop on and ends with it.

**Measured on the development PC** (Linux, 5120 x 1440, in an online race):

| Program | RAM | CPU |
|---|---|---|
| TSU (for comparison) | about 2 GB | about 46 % of one core |
| TurboHUD | about 180 MB at the start; 300-360 MB in a race of 20 cars once its text caches are full (2026-11-20) | about 4 % of one core |
| Probe, between questions | small (a Python program) | 0 % |
| Probe, during an online-race search | + 16 MB, kept for the next search | one core for about 1.5 to 2 s |

A known problem, fixed on 2026-11-01: before that fix, the probe searched every 10
seconds in menus and lobbies too, and kept a new 16 MB block per searched piece of
memory, so it could grow to several GB of RAM. Now it searches only during events and
reuses one buffer (checked: RAM stays flat over repeated searches). The fix takes
effect for the probe the next time TSU is started.

**Files TurboHUD writes**, all its own, in its settings folder (Linux `~/.config/TurboHUD/`,
macOS `~/Library/Application Support/TurboHUD`, Windows `%APPDATA%\TurboHUD`):

- `settings.json`: section places, sizes, text sizes, groups, shown or hidden, presets, the
  colours and the options
- `flags/`: TSU's flag images, read from your copy of the game and made small
- `turbohud.lock`: held while TurboHUD runs, so only one runs at a time
- `tracks/`: the track map's learnt tracks, one small file per track (the line it
  draws, and the start line), named from the track's checkpoint lines
- `turbohud.log`: what TurboHUD did in this run (replaced at each start), with numbers to
  go by if the HUD lags: every 30 s in a race how long its reads took, TurboHUD's memory and where it
  is (`memory parts:`; with `TURBOHUD_TRACE_MEMORY=1` also where Python's grew), and when each
  search for an online race ran and what it found. No names or IDs of players.
- `memory_probe.log` (Linux): written by the probe: the game it found, errors
- `bottle_reader.log` (macOS): the reader's errors

Your own layouts go in `customization/display_presets` beside TurboHUD (in the settings folder
where that one cannot be written to, or is a Mac's Applications folder: an admin account can write
to `/Applications`, which is no place for a player's files; `presets.move_old_customization` moves
what an older TurboHUD put there): layout files with places and sizes only. TurboHUD's own
layouts per screen size are there too, as `<width>x<height> (TurboHUD default).json`: in the
Windows and Linux downloads, and written again from the ones inside the app at each start where
missing or older. A first start takes the one for the main screen; they never replace sections
already placed, nor a layout file of the player's own. A first start also takes the starting presets
(`assets/presets/starting/presets.json`: the user's five, with names and Load by itself choices),
fitted to the screen (`app.with_starting_presets`), where the player has none. Both are made with
`tools/make_layouts.py LAYOUT.json --settings SETTINGS.json --designed SIZE.json ...` from a layout
the user exported, their settings and the layouts they designed for other sizes (shipped as they
are); a size without one is fitted, keeping Nearby cars' text at least the Standings'
(`presets.readable_nearby`).

As an event begins, the preset for its kind (`race.event_mode`: race, hotlapping, recording, spectating,
special) loads, once a kind changes (`race.EventModes`): the player's Load by itself choice, or the one they
loaded by hand during an event of that kind this session (`race.SessionPresets`). A session is over once TSU
has had none for 5 s (its menu); the next starts with the Load by itself choices again.

It writes nothing into the game's folders and changes nothing in the system.

## Fairness online

Everything TurboHUD shows comes from your own game's memory: what your game already
knows to run the race (where the cars are, their checkpoint times, your car's state).
It does not change the game, does not send anything to other players or servers, and
gives no control over the car.

## Limits and what is not checked yet

- On macOS and Windows the throttle and brake bars move in TSU's thirds, as the pad's
  triggers are read only on Linux.
- In online races where your game is a client (joining someone else's server, or
  hosting with only AI drivers), the game keeps no car positions where the offline
  race has them. TurboHUD takes them from the game's replay recorder instead (TSU
  records every race and keeps each car's last recorded position). If recording is
  off, it works them out from the last checkpoint and the velocity, for a live delta
  and gaps, and the radar does not show. Each car goes on from where its worked-out
  place meets each new checkpoint line, so it settles onto the road within about a lap
  even where the lines are long and off to one side (checked live: about 2 units from
  the real place, against about 7 from the lines' middles).
- The car size on the radar (4.0 x 1.4 units, drawn at that size since 2026-11-16) was measured
  with one car model (Tatuus FA01); other models may differ a little. Online, the other cars'
  positions come about 10 times a second and are carried on between, so a car may sit a little
  ahead of or behind where it is.
- A game update can rename classes or fields. TurboHUD then shows "waiting" instead of
  wrong numbers, and the names need updating.

## Rules for the overlay

- Move mode is a short, deliberate step: while the overlay takes the mouse, the game gets
  no mouse input under it. Since 2026-11-13 (asked for by the user) a click on the game no
  longer ends it; it ends by its shortcut, the panel's Lock, or a race beginning.
- Set the pointer explicitly in move mode; TSU hides the system pointer at times.
- Locked: hide the background completely and show only the content, with a shadow for
  readability.
- Keyboard shortcuts must work on Mac keyboards (no Alt). On the Mac, Carbon's system-wide
  hotkeys work while TSU has focus and need no permission.
- On the Mac, put the overlay at a window level above 26 (TSU's in Fullscreen) and allow
  it on every Space; the probe uses the screen-saver level (1000).

## Why Python and Qt (decided 2026-10-23)

The stack had to draw a good-looking HUD the player can style (colours, fonts, size, layout), install
on Windows, macOS and Linux with nothing else to install first, and stay light while racing. The
overlay window differs per system (a native Mac window above TSU's Fullscreen, outside CrossOver;
always-on-top and click-through on Windows; Hyprland asked at runtime on Linux), while everything
else is shared. Chosen: **B, Python with Qt (PySide6)**, shipped as a bundled app for each system.

| | A. Python, standard library + ctypes | B. Python + Qt (PySide6) | C. Web UI (Electron or Tauri) | D. Native per system (C# + Swift) |
| --- | --- | --- | --- | --- |
| Overlay on Windows | Proven by the probe (inside CrossOver) | Qt flags for on-top, click-through and a transparent background | Built in | Native |
| Overlay over Mac Fullscreen | Proven by the probe | A few lines of ctypes on top of Qt (level above 3) | Built in (Electron's `screen-saver` level) | Native |
| Overlay on Linux | A third platform file (X11 through ctypes); untested | Qt on X11 and XWayland | Electron on X11 and XWayland; Tauri depends on WebKitGTK, whose transparency is less reliable | A third native app, or C# with Avalonia for Windows and Linux |
| Drawing the HUD | Each system's own drawing calls, written three times | Qt painting, smooth and the same everywhere | HTML and canvas, easiest | Native, written per system |
| Global shortcuts | ctypes per system | ctypes per system (Qt has none) | Built in | Native |
| Shared code | One codebase | One codebase | One codebase (JavaScript/TypeScript) | Two or three languages |
| Install for players | Python needed on Mac and Linux | Bundled app, nothing to install | Bundled app, nothing to install | Bundled app per system |
| Size | Small | About 60-150 MB per bundle | 100-200 MB (Electron) | Small |
| Main risk | Much hand-written drawing and window code | Bundle size; Qt on the Mac needs native help | A browser engine running beside the game | Every feature built two or three times |

- **Best looks for the effort.** Qt draws smooth text, shadows, lines, shapes and images
  with transparency on all three systems, from one implementation. Themes the player can
  change (colours, fonts, size, opacity, which widgets show where) are ordinary settings.
  Qt Quick (QML) is there if the HUD later wants animations.
- **One language and one codebase,** the same as LiveryStudio: Python, unittest, Ruff.
- **Small native part.** Only what Qt lacks stays per system: the Mac window level above
  Fullscreen (from the Mac probe) and the global shortcuts (from both probes, plus X11 on
  Linux).
- **Lighter than C** while the game runs: no browser engine.
- **Far less work than D,** which would build every feature two or three times.

Costs accepted:
- Each download is larger, roughly 60-150 MB instead of a few MB.
- Releases need a build on each system (see below), instead of a plain source ZIP.
- TurboHUD no longer uses only the standard library. LiveryStudio keeps its own rule.

## How it is built and shipped

Each release is a ready-to-run app with Python and Qt inside, built by PyInstaller:
- **Windows:** a ZIP with `TurboHUD.exe`. Unpack and run.
- **macOS:** `TurboHUD.app` in a ZIP or disk image. Drag to Applications.
- **Linux:** a `.tar.gz` for now (an AppImage is planned, backlog item 4), built in an
  Ubuntu 22.04 container (`tools/build_linux.sh`) so it starts on glibc 2.35 and newer.
  Unpack and run. The bundled app is also the memory probe: Steam's launch option is
  `"…/TurboHUD" --probe %command%` (`TurboHUD --launch-option` prints it).

PyInstaller builds only for the system it runs on, so each release is built locally
with `tools/build_app.py` on each system, from `main`. The Windows and Mac builds carry
the Rust reader (`tools/get_rust.sh` builds it first). A GitHub Actions workflow
(`.github/workflows/build.yml`) runs only for a release tag, a pull request or by hand,
none of which is used.

Without paid code signing, each system warns once on first start:
- Windows SmartScreen: **More info**, then **Run anyway**.
- macOS: the app is blocked first; allow it under **System Settings > Privacy &
  Security > Open Anyway**. An Apple Developer account (paid yearly) removes this.
- Linux: no warning.

## Building TurboHUD, by example

Each system builds its own app, from `main`, in the repository folder; everything the tools fetch stays in
`.buildtools/` (gitignored). The version is `dev` or the release date, `YYYY.MM.DD`, with `.2` for a second
build that day. `--smoke` starts the built app for a few seconds and fails if it does not quit cleanly (close
TurboHUD first). Each archive lands in `releases/` with a `.sha256` file beside it. The checks first: the tests
and Ruff (RESUME.md, "Working notes").

**Windows** (Git Bash for the `.sh` scripts; PowerShell or a command prompt for the rest):
1. The Rust reader, once and after a change in `reader/`: `sh tools/get_rust.sh` (fetches pinned Rust and
   llvm-mingw into `.buildtools`, builds `.buildtools/reader/turbohud-reader.exe`). Without it the app reads TSU
   in Python, slower, and the build warns.
2. The build environment, once: `py -3 -m venv .buildtools\win-build-venv`, then
   `.buildtools\win-build-venv\Scripts\python.exe -m pip install -r requirements-build.txt` (PySide6,
   PyInstaller, Pillow, pinned).
3. Build: `.buildtools\win-build-venv\Scripts\python.exe tools\build_app.py --version 2026.11.20 --smoke`
   gives `releases\TurboHUD-2026.11.20-windows-x64.zip` (`TurboHUD\TurboHUD.exe`, the reader, the guides).

**macOS** (Apple silicon, Terminal):
1. A Python for the build, once: `sh tools/get_mac_python.sh` (a pinned python-build-standalone 3.13 into
   `.buildtools/mac-build-venv`, with requirements-build.txt), so the app starts on older macOS too. Not yet tried
   (backlog item 4); with Homebrew's Python the build stops, as the app would need this Mac's macOS, unless
   `--any-macos` is given.
2. Build: `.buildtools/mac-build-venv/bin/python tools/build_app.py --version 2026.11.20 --smoke`. It runs
   `tools/get_rust.sh` itself for the reader, checks the oldest macOS the app starts on, and gives
   `releases/TurboHUD-2026.11.20-macos-arm64.dmg` (the app, a link to Applications, `Read Me First.txt`).

**Linux** (any distro with Podman, or Docker):
1. Build: `sh tools/build_linux.sh 2026.11.20` (Docker without its group: `sudo sh tools/build_linux.sh ...`).
   It builds in an Ubuntu 22.04 container from the committed files only (`git archive HEAD`: commit first), runs
   `build_app.py --smoke` there and gives `releases/TurboHUD-2026.11.20-linux-x64.tar.gz`, which starts on glibc
   2.35 and newer. Nothing is installed on the PC; the container image is kept for the next build.

## The code

```
launch_turbohud.py      start file; the bundles run the same code
QUICK_START.md, USER_GUIDE.md  the players' guides, in every download (Quick Start.txt, User Guide.txt)
run_turbohud.sh/.cmd    start from the source, setting up PySide6 in .buildtools/venv;
                        also --toggle, --move, --lock, --settings, --preset N, --quit (Linux, macOS)
requirements.txt        PySide6, pinned; requirements-build.txt adds PyInstaller
turbohud/
  app.py                start-up: settings, log, section windows, tray menu, shortcuts,
                        commands, the live race
  control.py            the command socket (run_turbohud.sh --toggle and the rest)
  core/                 shared, no Qt
    settings.py         settings and theme, where they live on each system
    hud.py              the sections, their sizes, places, nudges and the grid's screen
    presets.py          layout files per screen size, fitting one to another size, the
                        starting presets, and the design screen's frame
    fonts.py            the player's own fonts: the customization/fonts folder and its files
    il2cpp.py           finds the game's classes and fields by name
    race.py             reads the race and works out what each section shows
    preview.py          move mode's preview: a made-up race at Laguna Seca, through race.py
    trackmap.py         the track map: the learnt track and which cars show
    flags.py            TSU's flags as country codes
    flagstack.py        the blue and yellow flags combined where both are in one spot
    leader.py           the race leader banner: when a new leader or the winner shows, and its fade
    battle.py           the battle warning while watching (Race Director mode): which two cars, when
    watched.py          the watched driver's banner while watching (Race Director mode): who, and when
    class_registry.py   the car classes a clan tag can name, and their colours
    stalls.py           short freezes of the whole HUD and slow garbage collections, for the log
    memory.py           TurboHUD's own memory for the log: the total, its parts (Python, the C heap,
                        the drawn texts) and, with TURBOHUD_TRACE_MEMORY=1, where Python's grew
    system_env.py       the environment for system programs TurboHUD starts (TSU, hyprctl)
  tsu/                  the game
    probe.py            Linux: the memory probe (started with TSU by the launch option)
    client.py           the race in a background thread; Linux: talks to the probe
    gamelog.py          TSU's log: whether an event runs
    gameflags.py        TSU's own flag images, read from the player's copy of the game
    controller.py       Linux: the gamepad's triggers
    winmemory.py        Windows and CrossOver: reading TSU as a Windows program
    bottle.py           macOS: finds TSU's bottle and starts the reader there; Windows:
                        starts the reader beside TSU (LocalReader); asks it over a pipe
    bottle_reader.py    the reader in Python (with a Windows Python in the bottle):
                        the fallback, TURBOHUD_PY_READER=1
  hud/painter.py        Qt drawing of text, bars and flags; the texts kept per font, each
                        section drawn in its own font or the global one (`using`) and its
                        colour map (`colours`, `shaded`: hud.COLOUR_BLIND)
  overlay/
    window.py           the section windows (drawings: blue flag, delta bar, radar, track
                        map), the one-window canvas (Mac), the grid and the move-mode panel
                        (its General and Text tabs over the same rows of sections)
    settings_window.py  tabs Look, Colours, Sections and Race: text colours, size and font,
                        colour-blind friendly and Legacy colours, options, warning times,
                        reads a second
    layouts_window.py   presets (named, the one in use), Load by itself, layout files and the
                        design screen, opened from the move-mode panel
    class_sheet.py      the list of car classes, opened from the settings
    windows.py          Win32: RegisterHotKey, focus hand-back
    macos.py            Cocoa: window level above Fullscreen, all Spaces; Carbon hotkeys
    linux.py            Linux: Hyprland or XWayland; shortcuts on Hyprland only
    hyprland.py         asks Hyprland to float, place and pin TurboHUD's own windows, binds its keys
assets/                 the icon; presets/ (the shipped layouts per screen size, and in
                        starting/ the five starting presets); preview/ (move mode's made-up
                        race); resources/ (the winner banner's picture)
experiments/            the probes that settled the design; tsu_memory_probe.py is what
                        the Steam launch option runs from the source
reader/                 the reader in Rust (a Windows program, no dependencies): in the
                        bottle on macOS, beside TSU on Windows; answers as bottle_reader.py does
tools/build_app.py      PyInstaller build, archive and smoke test for this system
tools/make_layouts.py   the shipped layouts and starting presets from the user's own designs
tools/build_linux.sh    the Linux build in an Ubuntu 22.04 container
tools/get_rust.sh       Rust and llvm-mingw into .buildtools (pinned), then builds the Rust reader
tools/get_mac_python.sh a pinned Python for the Mac build, for older macOS versions too
tools/get_windows_python.sh  a pinned Windows Python, by hand, for the Python reader
tools/privacy_check.py  the pre-push hook that keeps personal data out of commits
tests/                  unit tests on any system
```

A tray icon (the menu bar on the Mac) offers Move mode, Options (the on/off options),
Relearn this track's map, Settings…, About and Quit;
on Linux desktops other than Hyprland, which have no shortcuts in TurboHUD, the commands
above can be bound to a key in the desktop's own settings. First build sizes: Windows 40 MB ZIP, Mac 28 MB ZIP (75 MB
unpacked), Linux 74 MB `.tar.gz` (with Qt's X11 libraries packed in).

