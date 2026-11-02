# How TurboHUD works

TurboHUD is an overlay for Turbo Sliders Unlimited (TSU): small see-through boxes on
top of the game that show race information the game does not show itself, or not as
clearly. This document explains what it shows, where the data comes from, and what it
does (and does not do) to the game, to your RAM and to your system.

State: 2026-11-01. Live race data works on Linux (the native TSU build). On Windows
and macOS TurboHUD so far shows only a session clock and the local time.

## What it shows

Each part of the HUD is its own box ("section"). In move mode you drag, resize, hide,
group and centre them; their places are saved.

| Section | What it shows |
|---|---|
| Lap and time left | Lap 2/3, and the time left in a timed race |
| Running lap | the current lap time, counting |
| Delta to best | ahead (green) or behind (red) your best lap, live between checkpoints |
| Last and best lap | your last and best lap times |
| Fuel | fuel left, laps it lasts at your recent use, fuel saved or burnt this lap; a level bar |
| Fuel to finish | laps of fuel to spare (green) or missing (red) for the finish |
| Tires | tire life left and the laps it lasts; a level bar |
| Health | car health as the game counts it; yellow with less downforce, red when slowed; a level bar |
| Draft | how strong the slipstream is (of the event's most), with a bar; the downforce it costs; the event's drafting at the start, then the last lap's time in a slipstream; who drafts you |
| Speed | km/h or mph, yellow while coasting; throttle and brake bars beside it |
| Players | position, flag, name, PIT, and the live gap to you (or +1 L for laps) |
| Blue flag | a navy bar that fades in when a car about to lap you is within 2 s |
| Proximity radar | your car and the cars around you, when one is within 0.5 s behind, beside or ahead; the slipstream behind cars ahead |
| Local time | the clock |

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
2. **The probe** (`turbohud/tsu/probe.py`, started by `experiments/tsu_memory_probe.py`).
   A small Python program that Steam runs through the launch option. It starts TSU as
   its own child process, and then answers read-only questions about the game's memory
   from TurboHUD. That is all it does.
3. **TurboHUD** (`turbohud/`). The overlay app you start with `run_turbohud.sh`. It
   asks the probe for the race data about 20 times a second, works out what to show and
   draws the sections.

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

## How it finds the race in the game's memory

TSU is made with Unity using IL2CPP: its code is compiled, but it keeps a description of
all its classes and fields (`global-metadata.dat`), which is loaded into memory. Every
class the game uses has a record pointing to its name and to its fields, each with its
name and position. So TurboHUD needs no fixed addresses (those change with every start
and every game update): it looks everything up by name each time the game starts.

The race data is found along this path of objects:

```
TS.Services.sm_instance          (a static field: always findable)
  .m_activeServer.m_eventListener  the race controller (offline, hotlap, hosted online)
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

### Online races

When you join an online race, or host one that only has AI drivers, your game runs as
a client: the race is then in a `TS.ClientEventController` that no static field leads
to. TurboHUD finds it by its class, with one `search` of the game's memory, then keeps
using the object it found until the race ends.

A search reads all of the game's data once (about 1.5 to 2 seconds, one CPU core
busy). So TurboHUD searches only when it has to: when there is no offline or hosted
race, and TSU's own log file says an event is running (TSU writes "Event started." and
"Event ended." into `Logs/log.*.txt` as it happens; TurboHUD only reads that file). In
menus and lobbies it does not search at all. While an event runs without a race found
yet, it searches at most every 10 seconds.

When you host an online race with other players, TSU runs the server inside your game,
and the race is found the normal way, with no search.

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

**Files TurboHUD writes**, all its own, in `~/.config/TurboHUD/`:

- `settings.json`: section places, sizes, groups, shown or hidden, mph, light tint
- `turbohud.log`: what TurboHUD did in this run (replaced at each start)
- `memory_probe.log`: written by the probe: the game it found, errors

It writes nothing into the game's folders and changes nothing in the system.

## Fairness online

Everything TurboHUD shows comes from your own game's memory: what your game already
knows to run the race (where the cars are, their checkpoint times, your car's state).
It does not change the game, does not send anything to other players or servers, and
gives no control over the car.

## Limits and what is not checked yet

- Live data on Linux only. Windows and macOS need their own way to read the game's
  memory.
- In online races where your game is a client (joining someone else's server, or
  hosting with only AI drivers), the game keeps no car positions where the offline
  race has them. TurboHUD takes them from the game's replay recorder instead (TSU
  records every race and keeps each car's last recorded position). If recording is
  off, it works them out from the last checkpoint and the velocity, for a live delta
  and gaps, and the radar does not show.
- The car size on the radar (4.0 x 1.4 units) was measured with one car model (Tatuus
  FA01); other models may differ a little.
- A game update can rename classes or fields. TurboHUD then shows "waiting" instead of
  wrong numbers, and the names need updating.

## Where to look in the code

| File | What it does |
|---|---|
| `turbohud/tsu/probe.py` | the probe: starts TSU, serves read-only questions |
| `turbohud/tsu/client.py` | talks to the probe, reads the race in a background thread |
| `turbohud/tsu/gamelog.py` | reads TSU's log to know whether an event runs |
| `turbohud/tsu/controller.py` | reads the gamepad's triggers |
| `turbohud/core/il2cpp.py` | finds classes and fields by name in an IL2CPP game |
| `turbohud/core/race.py` | reads the race and works out what each section shows |
| `turbohud/core/hud.py` | the sections, their sizes, places and layout |
| `turbohud/overlay/` | the windows; Hyprland, Windows and macOS specifics |
| `turbohud/app.py` | starts everything: settings, windows, tray menu, shortcuts |
