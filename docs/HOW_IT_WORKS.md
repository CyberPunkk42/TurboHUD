# How TurboHUD works

TurboHUD is an overlay for Turbo Sliders Unlimited (TSU): small see-through boxes on
top of the game that show race information the game does not show itself, or not as
clearly. This document explains what it shows, where the data comes from, and what it
does (and does not do) to the game, to your RAM and to your system.

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
| Slipstream | how strong the slipstream is (of the event's most), with a bar; the downforce it costs; the event's drafting at the start ("Up to -10% drag, -80% downforce, 30 m, 20°": the most it takes off the air resistance and the downforce, how far behind a car it reaches and how far off its line), then the last lap's time in a slipstream; who drafts you |
| Speed and pedals | km/h or mph, yellow while coasting; throttle and brake bars beside it; as an option the gear and rev lights |
| Nearby cars | the leader, then the 3 cars ahead of and 3 behind you on the track: position, flag, name, tire, PIT, and the live gap to you (or +1 L for laps), DNF for a car out of the race |
| Standings | every driver in race order (by class in a multi-class race) with flag, name and clan tag or class, lap, tire, their best lap (the race's fastest in purple) and their last lap, or CUT, JUMP, PIT or DNF |
| Blue flag | a navy bar that fades in when a car about to lap you is within 2 s |
| Yellow flag | a car off the track, slow, stopped, spun, the wrong way or put back in your sector or the next, by sector and driver; CAR STOPPED AHEAD or WRONG WAY AHEAD for one up to 5 s ahead on the road |
| Penalties | SHORTCUT with the seconds TSU slows you for a shortcut; JUMP START for a false start |
| Radar | your car and the cars around you, when one is within 0.5 s behind, beside or ahead; the slipstream behind cars ahead; by default only in cockpit cameras |
| Track map | the track from above, with you, the race leader (gold), the next car ahead (red), the next car behind (green), backmarkers between you and the car ahead (small, bluish), and as an option the other cars (faint grey) |
| Clock | the clock |
| Time since start | how long TurboHUD has run (shown while there is no race) |

Spectating an online race, only the lap section (with "Spectating" and the leader's lap),
the player list (gaps to the leader), the lap times, the track map (every car) and the
local time show.

The race sections appear once the cars are on the grid and go away in the lobby. In
the menus only the local time shows.

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
finds it (one pass with both classes on Windows, a second pass elsewhere).

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
runs it adds Ctrl+Shift+L, Q, 1, 2 and 3 to Hyprland's live keys (`hyprctl eval` with
`hl.bind`, on older Hyprland `hyprctl keyword bindd`), each running the command below. It
first looks at `hyprctl binds` and leaves every key something else has (Ctrl+Shift+F12 for
move mode where Ctrl+Shift+L is taken). Its binds are labelled "TurboHUD shortcut", and it
removes only those at quit. They live in Hyprland's memory only: a reload of Hyprland's
settings drops them, and TurboHUD, listening on Hyprland's event socket, adds them again; a
restart of Hyprland ends them, also after TurboHUD crashed. A TurboHUD that did not quit
leaves them until then (pressing them does nothing), and the next start
takes them over.

## Commands from the command line (Linux, macOS)

`run_turbohud.sh --toggle`, `--move`, `--lock`, `--settings`, `--preset 1` (or 2, or 3)
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
| TurboHUD | about 180 MB | about 4 % of one core |
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
  go by if the HUD lags: every 30 s in a race how long its reads took, and when each
  search for an online race ran and what it found. No names or IDs of players.
- `memory_probe.log` (Linux): written by the probe: the game it found, errors
- `bottle_reader.log` (macOS): the reader's errors

Your own layouts go in `customization/display_presets` beside TurboHUD (in the settings folder
where that one cannot be written to): layout files with places and sizes only. TurboHUD's own
layouts per screen size are there too, as `<width>x<height> (TurboHUD default).json`: in the
Windows and Linux downloads, and written again from the ones inside the app at each start where
missing or older. A first start takes the one for the main screen; they never replace sections
already placed, nor a layout file of the player's own.

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
- The car size on the radar (4.0 x 1.4 units) was measured with one car model (Tatuus
  FA01); other models may differ a little.
- A game update can rename classes or fields. TurboHUD then shows "waiting" instead of
  wrong numbers, and the names need updating.

## Where to look in the code

| File | What it does |
|---|---|
| `turbohud/tsu/probe.py` | the probe: starts TSU, serves read-only questions |
| `turbohud/tsu/client.py` | talks to the probe, reads the race in a background thread |
| `turbohud/tsu/bottle.py` | macOS: finds TSU's bottle and starts the reader there; Windows: starts it beside TSU; asks it over the pipe |
| `reader/` | the read-only reader in Rust (a Windows program) |
| `turbohud/tsu/bottle_reader.py` | the same reader in Python, the fallback (`TURBOHUD_PY_READER=1`) |
| `turbohud/tsu/winmemory.py` | reading TSU as a Windows program: regions, page cache, paced search |
| `turbohud/tsu/gamelog.py` | reads TSU's log to know whether an event runs |
| `turbohud/tsu/gameflags.py` | TSU's own flag images, from the player's copy of the game |
| `turbohud/tsu/controller.py` | reads the gamepad's triggers |
| `turbohud/core/il2cpp.py` | finds classes and fields by name in an IL2CPP game |
| `turbohud/core/race.py` | reads the race and works out what each section shows |
| `turbohud/core/preview.py` | move mode's preview: one moment of a made-up race at Laguna Seca (`assets/preview`), run through `race.py` like a real one |
| `turbohud/core/trackmap.py` | the track map: the track's shape and which cars show |
| `turbohud/core/hud.py` | the sections, their sizes, places and layout |
| `turbohud/core/presets.py` | layout files per screen size, and fitting them to another |
| `turbohud/overlay/` | the windows; Hyprland, Windows and macOS specifics |
| `turbohud/app.py` | starts everything: settings, windows, tray menu, shortcuts |
| `turbohud/control.py` | the command socket for `run_turbohud.sh --toggle` and the rest |
