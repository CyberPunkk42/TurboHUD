# TurboHUD - Quick Start

TurboHUD is an overlay for Turbo Sliders Unlimited: lap times, the cars around you, fuel,
tires, health, a track map, flags and more, on top of the running game. It only reads the
game; it never changes it.

## 1. Install

**Windows**
1. Right-click the downloaded ZIP and choose **Extract All** (starting it from inside the
   ZIP does not work).
2. Open the extracted `TurboHUD` folder and double-click `TurboHUD.exe`.
3. If "Windows protected your PC" appears: **More info**, then **Run anyway** (only the
   first time; TurboHUD is not signed with a paid certificate yet).

**macOS** (TSU in CrossOver): open the disk image, drag `TurboHUD.app` onto
**Applications**, and follow `Read Me First.txt` for the first start.

**Linux**: unpack the `.tar.gz` and start `TurboHUD`. Live race data needs TSU started with a
launch option: see the README.

## 2. First start

- TurboHUD has no window of its own. You see a small HUD at the top left of the screen and
  the TurboHUD icon in the taskbar's notification area (Windows; maybe behind the **^**
  arrow) or in the menu bar (Mac).
- Start TSU, before or after TurboHUD. The race sections appear when the cars stand on the
  grid. Online and in replays, finding the race takes up to about 10 seconds.
- Not showing up? Rest the pointer on the TurboHUD icon: it says what TurboHUD is waiting
  for ("waiting for a race", "racing", "replay" ...).

## 3. Place your HUD (move mode)

1. Press **Ctrl+Shift+L** (or choose **Move mode** in the icon's menu).
2. Drag each section where you want it. Drag its bottom-right corner: taller or shorter
   makes the text bigger or smaller, wider gives it room.
3. The panel that opens shows or hides each section, and keeps up to three layouts
   (**Save** / **Load** presets 1 to 3). **Undo** goes back a step.
4. Press **Ctrl+Shift+L** again (or **Lock**) to finish. Your layout is saved.

## 4. Settings

Icon menu, **Settings...**: text colours, all sections bigger or smaller, km/h or mph, a
light tint behind the sections, which columns the lap times show (flag, lap, tire, best,
last), when the blue flag and the radar warn, and **Car classes...**, a list of every car
class you can put in your clan tag (such as [GT3] or [LMP]) with its colour. **About...**
(also **About TurboHUD...** in the icon's menu) shows the version you have.

## What it shows

Every part of the HUD is a section you can show, hide, move and size in move mode. They are
listed in the panel under four headings:

**Timing**
- **Lap and time left**, **Running lap**: the lap you are on, the race time left, and your
  current lap's time.
- **Delta to best** and **Delta bar**: how far ahead (minus, the bar fills right) or behind
  (plus) your best lap you are, live. The bar is green while you gain time, red while you lose it.
- **Last and best lap**: with sector bars below, coloured as on F1 timing screens (purple
  the fastest of the race, green your own best, yellow slower).
- **Lap times**: every driver's best and last lap, the race's fastest in purple, the tire
  compound as a coloured ring (S red, M yellow, H white), **CUT** for a shortcut penalty,
  **JUMP** for a false start and **PIT** with the time in the pits.

**Car**
- **Fuel** and **Fuel to finish**: fuel left, how many laps it lasts, and whether it lasts to
  the end (green: laps to spare; red: you need to pit).
- **Tires** and **Health**: tire wear and damage left, where the event has them on.
- **Draft**: how much you are in someone's slipstream.
- **Speed**: with throttle and brake bars.

**Race**
- **Players**: the leader on top, then the 3 cars ahead of and the 3 behind you on the track,
  with the gap to each.
- **Track map**: learnt from three clean laps of yours; the cars as dots, incidents ringed.
- **Proximity radar**: cars close to you, red right beside you and yellow closing in, with the
  slipstream behind the cars ahead; arrows at its edge for cars just out of view.
- **Blue flag**: a faster car about to lap you.
- **Yellow flag**: trouble ahead (a car stopped, spun, off the track, the wrong way round or
  wrecked) and in which sector.
- **Penalties**: an orange box counting down while TSU slows you for a shortcut, and JUMP
  START for a false start.

**Other**: **Local time** and **Session time** (how long TurboHUD has been running).

## Keyboard shortcuts

| Keys | Does | Where |
|---|---|---|
| **Ctrl+Shift+L** | Move mode on / off (unlock and lock the HUD) | Windows, Mac |
| **Ctrl+Shift+F12** | The same, if another program has Ctrl+Shift+L (see below) | Windows |
| **Ctrl+Shift+1**, **2**, **3** | Load layout preset 1, 2 or 3, also during a race | Windows, Mac |
| **Ctrl+Shift+Q** | Quit TurboHUD | Windows, Mac |

They work while you play: you don't need to leave the game. Linux has no shortcuts: use the
icon's menu, or `run_turbohud.sh --toggle`, `--preset 1` and `--quit` (a key on your desktop
can run them).

## Ctrl+Shift+L does nothing? (AMD graphics cards)

AMD Software: Adrenalin Edition occupies **Ctrl+Shift+L** with a shortcut of its own. While it
does, Windows gives that key to AMD, and TurboHUD cannot use it. To use Ctrl+Shift+L with
TurboHUD:

1. Open **AMD Software: Adrenalin Edition**.
2. Click the gear icon (**Settings**) and open **Hotkeys**.
3. Find the entry set to **Ctrl+Shift+L**, and remove that binding (or give it other keys).
4. **Quit TurboHUD and start it again**: it can only take the key when it starts.
5. Ctrl+Shift+L now switches move mode.

Until then, **Ctrl+Shift+F12** does the same on Windows, and **Move mode** in the TurboHUD
icon's menu always works. The icon's tooltip says when Ctrl+Shift+L is taken. Other overlays
(recording, chat, streaming tools) can occupy keys the same way.

## Good to know

- **Names in the players list**: orange are a lap or more ahead of you in the race (let them
  by), blue a lap or more behind.
- **Car classes**: put a class code in your clan tag in TSU, such as `[GT3]`. With two or
  more classes in a race, the lap times are grouped by class, each in its colour.
- **Wet races**: on a track whose name has `(WET)`, `(RW)`, `(QW)` or `(W)`, every car shows
  a blue **W** tire.
- **Replays**: TurboHUD also works in TSU's replays, as if you were driving the car the
  camera follows.
- **Settings and the log** (`settings.json`, `turbohud.log`): Windows `%APPDATA%\TurboHUD`,
  macOS `~/Library/Application Support/TurboHUD`, Linux `~/.config/TurboHUD`. When reporting
  a problem, send `turbohud.log` right after it happened: it is replaced at the next start.
