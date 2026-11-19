# TurboHUD - Quick Start

TurboHUD is an overlay for Turbo Sliders Unlimited: lap times, standings, the cars around you,
fuel, tires, a track map, a radar, flags and more, on top of the running game. It only reads
the game; it never changes it. Every part is explained in detail in `User Guide.txt`.

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
launch option in Steam: `TurboHUD --launch-option` prints it, and `Read Me First.txt` says where
it goes.

## 2. First start

- TurboHUD has no window of its own: look for its icon (a speedometer) in the taskbar's
  notification area (Windows; maybe behind the **^** arrow), the menu bar (Mac) or your panel's
  tray (Linux). Once TSU runs, a small **Clock** shows.
- Start TSU, before or after TurboHUD. The race sections appear when the cars stand on the
  grid; online and in replays, finding the race takes up to about 10 seconds.
- Nothing showing? Rest the pointer on the icon: it says what TurboHUD is waiting for.

## 3. Place your HUD (move mode)

1. Press **Ctrl+Shift+L** (or **Move mode** in the icon's menu). A grid helps line things up,
   and outside a race every section shows a made-up race at Laguna Seca, so you see it filled.
2. Drag a section, or click it and nudge it with the arrow keys (Shift: 10 px). A corner sizes
   its text, an edge adds room. While it moves, a label shows its X and Y on its screen and its size.
3. The panel shows or hides each section, sets its text size and line spacing, and has **Undo**
   and **Redo**, and says which preset the layout is in (**Preset: 3 Race**). Its **Layouts…** window
   keeps five named layouts (**Save** / **Load** presets 1 to 5), can load one by itself as a recording,
   spectating, hotlapping, race or special event begins (and starts in the Race one), and has
   **Load screen default**, **Export…**, **Import…** and **Design for** for layout files per screen
   size (in `customization/display_presets`; TurboHUD's own never replace yours).
4. Press **Ctrl+Shift+L** again (or **Lock**) to finish; a race starting also locks it. Your
   layout is saved.

## 4. Settings

Icon menu, **Settings...**: colours, all sections bigger or smaller, the **Font** (your own
**Add font...** picks a `.ttf` or `.otf` file and uses it at once; **Fonts folder...** opens `customization/fonts`), km/h or mph, a tint behind
the sections, which standings columns show, the radar (cockpit cameras or every camera, its
slipstream cones, how soon it shows), the yellow and blue flags, how often the race is read,
and the on/off options also under **Options** in the icon's menu. **Car classes...** lists the
class codes you can put in your clan tag; **About...** shows your version.

## 5. What each section shows

Hover over a section's name in the move-mode panel for a short explanation.

**Timing**
- **Race progress**: your lap, the time left in a timed race, the leader's lap.
- **Current lap**: the time of the lap you are driving.
- **Delta to best** and **Delta bar**: ahead (green) or behind (red) your best lap, live.
- **My laps**: your last and best lap, with coloured sector bars (purple fastest, green yours).
- **Standings**: every driver in race order, with flag, lap, gap to the leader, tire, best and
  last lap, PIT, CUT (shortcut penalty), JUMP (false start), DNF; grouped by class in a
  multi-class race. Every column but place and name can be turned off.

**Car**
- **Fuel** and **Fuel to finish**: fuel left, laps it lasts, and whether it reaches the end.
- **Tire wear** and **Car health**: where the event has wear and damage.
- **Slipstream**: how much you are in someone's slipstream, who is in yours, and the event's
  drafting limits at the start.
- **Speed and pedals**: speed, throttle and brake, and as an option gear and rev lights.

**Race**
- **Nearby cars**: the leader, then the car ahead and the car behind you on the track (3 of
  each with **Nearby cars: only the leader and the cars next to you** off), with the gap to each; orange a lap or more ahead (let them by), blue a lap or more behind.
- **Track map**: the track learnt from where the cars drive, with you and the cars near you.
- **Radar**: cars close to you, seen from above: red beside you, yellow closing in.
- **Blue flag**: a faster car about to lap you.
- **Yellow flag**: an incident in your sector or the next, who and what.
- **Penalties**: SHORTCUT with the seconds left, or JUMP START.
- **Race leader**: a banner for 6 s, "New Race Leader - name" once another driver has kept the
  lead for 5 s (none for your own car), and "Race Winner - name" with a waving checkered flag as the winner finishes
  (the panel's **🏁** shows the winner's in move mode).
- **Battle**: only while watching a replay or spectating, a banner "Battle for P3 / Possible
  Overtake / name vs name" when a car closes in on the one ahead or sits right behind it, or
  "Group around name" for three cars or more within a second of each other; not in the opening lap.
- **Watched driver**: in a replay and spectating, a banner "Watching / P3 name" each time the camera turns
  to another driver.

**Other**
- **Clock**: your computer's clock. **Time since start** shows instead of the race sections
  only on a system TurboHUD cannot read TSU on.

## Keyboard shortcuts

| Keys | Does | Where |
|---|---|---|
| **Ctrl+Shift+L** | Move mode on / off | Windows, Mac, Hyprland |
| **Ctrl+Shift+F12** | The same, if another program has Ctrl+Shift+L (see below) | Windows, Hyprland |
| **Ctrl+Shift+1** to **Ctrl+Shift+5** | Load layout preset 1 to 5, also during a race | Windows, Mac, Hyprland |
| **Ctrl+Shift+Q** | Quit TurboHUD | Windows, Mac, Hyprland |

They work while you play. On Hyprland (Omarchy, for example) TurboHUD adds them while it runs,
on keys nothing else uses. Other Linux desktops: use the icon's menu, or `TurboHUD --toggle`,
`--preset 1` and `--quit` (a key on your desktop can run them).

## Ctrl+Shift+L does nothing? (AMD graphics cards)

AMD Software: Adrenalin Edition takes **Ctrl+Shift+L** for a shortcut of its own. To give it
back: open **AMD Software: Adrenalin Edition**, the gear icon (**Settings**), **Hotkeys**, remove
the entry set to **Ctrl+Shift+L**, then quit TurboHUD and start it again. Until then
**Ctrl+Shift+F12** does the same, and **Move mode** in the icon's menu always works.

## Good to know

- **Car classes**: put a class code in your clan tag in TSU, such as `[GT3]`; with two or more
  classes in a race, the standings come by class.
- **Wet races**: on a track whose name has `(WET)`, `(RW)`, `(QW)` or `(W)`, every car shows a
  blue **W** tire.
- **Replays and Custom races** work too; in a replay the HUD follows the car the camera follows.
- **Settings and the log** (`settings.json`, `turbohud.log`): Windows `%APPDATA%\TurboHUD`,
  macOS `~/Library/Application Support/TurboHUD`, Linux `~/.config/TurboHUD`. When reporting a
  problem, send `turbohud.log` right after it happened: it is replaced at the next start.
