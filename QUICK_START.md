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
class you can put in your clan tag (such as [GT3] or [LMP]) with its colour.

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

AMD Software: Adrenalin Edition uses **Ctrl+Shift+L** for a shortcut of its own, and
Windows then gives it to AMD, not to TurboHUD. Other overlays (recording, chat, streaming
tools) can do the same.

- **Use Ctrl+Shift+F12** instead: it does the same, and TurboHUD always offers it. When
  Ctrl+Shift+L is taken, the TurboHUD icon's tooltip says so, and the move-mode panel names
  Ctrl+Shift+F12.
- **Or free Ctrl+Shift+L:** open AMD Software, click the gear icon (**Settings**), open
  **Hotkeys**, find the entry set to **Ctrl+Shift+L**, and change or clear it. Then quit
  TurboHUD and start it again.
- **Move mode** in the TurboHUD icon's menu always works, whatever the keys.

## Good to know

- **Players list**: the race leader on top, then the 3 cars ahead of you and the 3 behind
  you on the track, with the gap to each. Orange names are a lap or more ahead of you in the
  race (let them by), blue ones a lap or more behind.
- **Car classes**: put a class code in your clan tag in TSU, such as `[GT3]`. With two or
  more classes in a race, the lap times are grouped by class, each in its colour.
- **Wet races**: on a track whose name has `(WET)`, `(RW)`, `(QW)` or `(W)`, every car shows
  a blue **W** tire.
- **Replays**: TurboHUD also works in TSU's replays, as if you were driving the car the
  camera follows.
- **Settings and the log** (`settings.json`, `turbohud.log`): Windows `%APPDATA%\TurboHUD`,
  macOS `~/Library/Application Support/TurboHUD`, Linux `~/.config/TurboHUD`. When reporting
  a problem, send `turbohud.log` right after it happened: it is replaced at the next start.
