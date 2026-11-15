# TurboHUD - User Guide

This guide explains every part of TurboHUD: what each section on the screen shows, what
every menu item, button and option does, and where TurboHUD keeps its files. For the short
version (install, first start, shortcuts), see `Quick Start.txt`.

TurboHUD is an overlay for Turbo Sliders Unlimited (TSU). It sits on top of the running
game, lets every click through to it, and only reads the game: it never changes it, sends
nothing to other players or servers, and gives no control over the car.


## 1. How TurboHUD works on screen

- **Sections.** The HUD is made of small boxes called sections: the lap, the fuel, the
  track map and so on. Each one can be shown or hidden, moved and sized on its own.
- **Locked and move mode.** Normally the HUD is **locked**: only the text and drawings
  show, and clicks go straight through to the game. In **move mode** every section gets a
  blue tint and can be dragged and sized, and a panel with all the settings for the layout
  opens (see section 4).
- **When the race sections show.** Without a race, only **Time since start** and **Clock
  time** show. The race sections appear when the cars stand on the grid, before the
  lights, stay after you finish until the race is over, and go away in the lobby and the
  menus. Online, finding the race takes a few seconds after the event starts.
- **What TurboHUD is waiting for.** Rest the pointer on the TurboHUD icon: its tooltip says
  "TurboHUD - " and what it is doing ("waiting for game", "waiting for race", racing,
  replay ...), and warns when something is wrong (for example when another program has
  taken Ctrl+Shift+L, or on the Mac when the CrossOver bottle is not set to D3DMetal).
- **Where it works.** Offline races, hotlaps, Custom races, online races as a guest or a
  host, spectating online, and TSU's replays (the HUD then follows the car the camera
  follows, as if you were driving it).


## 2. The TurboHUD icon and its menu

TurboHUD has no window of its own and no Dock or taskbar button. Its icon (a speedometer)
sits in the menu bar on the Mac, in the notification area of the taskbar on Windows (maybe
behind the **^** arrow), and in the tray of your desktop's panel on Linux. Its menu:

- **Move mode**: switches move mode on or off (the same as Ctrl+Shift+L).
- **Options**: the on/off options for the whole HUD, the same as in the settings window:
  - **Speed in mph**: the speed in mph instead of km/h.
  - **Light tint behind all sections**: a faint dark box behind every section's text, for
    reading it on bright tracks. Each section also has its own **Tint** in move mode.
  - **Slipstream cones on the radar**: the slipstream behind each car ahead.
  - **Radar only in cockpit cameras**: the radar shows only while TSU's camera
    sits at the driver (a first-person view), not in the views from outside the car. On
    by default.
  - **Sector bars in My laps**: the small coloured bars, one per sector.
  - **Yellow flags**: the **Yellow flag** section and the yellow rings on the track map.
  - **Gear and revs in the speed section**: the gear above the speed and rev lights below it.
  - **Classes in the standings**: in a race with car classes, the standings grouped by class.
  - **Clan tags in the standings**: in a race without classes, each driver's clan tag in a
    column of its own.
  - **Other cars on the track map**: every other car as a faint grey dot.
- **Relearn this track's map**: during a race, forgets the map of this track (the saved one
  too); the map is then learnt again from the next whole clean lap.
- **Settings…**: opens the settings window (section 6).
- **About TurboHUD…**: the name and the version you have.
- **Quit TurboHUD**: quits it (the same as Ctrl+Shift+Q).

Only one TurboHUD runs at a time. Starting it again says "TurboHUD is already running"; on
the Mac and Linux it also switches the running one to move mode.


## 3. The sections

In move mode the panel lists the sections under four headings: **Timing**, **Car**,
**Race** and **Other**. Hover over a section's name in the panel, or over the section itself in
move mode, for a line on what it shows. The colours below are the default ones; the text, highlight and
outline colours can be changed in the settings.

### Timing

**Race progress**
Your lap ("Lap 2/13") and, in a timed race, the time left. For a few seconds after the
leader starts a new lap that you are not on yet, "Leader 4" fades in at its end, and
"Final lap" when the leader starts the last one. Before a race it may say what TurboHUD
is waiting for. Spectating, it says "Spectating" with the leader's lap.

**Current lap**
The time of the lap you are driving, counting up.

**Delta to best**
How far ahead (minus, green) or behind (plus, red) your best lap of this race you are,
right now, in hundredths of a second. It is live between checkpoints, worked out from
where your car is.

**Delta bar**
The same delta as a bar from the middle: to the right when you are ahead, to the left
when behind. It is green while you are gaining time and red while you are losing it; the
colour turns once the delta has moved 0.05 s the other way for a quarter of a second, so
a slow, steady loss turns it red too.

**My laps**
Your last and your best lap time. The best is purple when it is the fastest lap of anyone
in the race, green when it is your own best but someone has gone faster, and white for a
slower last lap. Below them, small **sector bars**, one per stretch of the track between
TSU's sector lines, are coloured the same way for each sector of your last lap (purple,
green, or dark yellow when slower than your best). After you set such a lap, the track
map's road shows purple or green for 6 seconds.

**Standings**
Every driver in race order (in qualifying, which TSU runs as hotlapping, by best lap). Each
row has, as chosen under **Settings…**:
- the place, the country flag, the name (up to 20 letters) and, in a race without classes,
  the clan tag (`FTR` for `[FTR]`)
- the lap each driver is on (`L3`)
- the tire compound as a letter in a coloured ring, as in F1: **S** red, **M** yellow,
  **H** white; on a wet track (one whose name has `(WET)`, `(RW)`, `(QW)` or `(W)`) every
  car shows a blue **W**
- the best lap, purple for the fastest in the race (or in the class)
- the last lap, or instead: **PIT** while in the pits, then the time from pit entry to pit
  exit with the time standing in the box in brackets; an orange **CUT** with the seconds
  left while TSU slows that driver for a shortcut; an orange **JUMP** for a false start;
  **DNF** for a car out of the race.
Your own row is in the highlight colour. With more than 20 drivers it shows the leader and
the drivers around you. While clan tags show, the list's text may get a little smaller to
fit its box.

The **country flags** here and in **Nearby cars** are TSU's own pictures: at its start
TurboHUD reads them from your copy of the game (only reading) and keeps them, made small,
in its own folder. Where the game is not found, the system's emoji flags show (on Windows,
which has none, the country code).

**Car classes (multi-class races).** Drivers name their class with their clan tag in TSU
(`[GT3]`, `[LMP]`, `[LMP2]` ...). With two or more classes in a race, the standings come by
class, each below a thin line with its name in the class's colour, numbered within the
class, with the class's fastest lap in purple and the overall place (`P7`) in an **Ovr**
column. A driver without a class tag (or with a team's tag) gets the class most tagged
drivers in the same car have; drivers in a car no one tagged come last under **Other**.
**Settings… > Car classes...** lists every class a tag can name, in its colour. The tags
that count are in `settings.json` as `class_tags` (change it while TurboHUD is closed).

### Car

**Fuel**
The fuel left in percent, how many laps it lasts at your recent use (`~6.2 laps`), and how
much you saved (green) or burnt more (red) on this lap than usual. The bar below goes from
green through yellow to red, and turns red when the fuel does not last to the finish.

**Fuel to finish**
Laps of fuel to spare (`Finish +1.4 laps`, green) or missing (`Finish -0.8 laps`, red) for
the end of the race: red means you have to pit for fuel.

**Tire wear**
Tire life left in percent and the laps it lasts, with a bar. Only in events with tire wear.

**Car health**
Your car's health as the game counts it, with a bar. Yellow with "less downforce" when the
damage costs grip, red with "slowed" when it makes the car slower. Only in events with
damage.

**Slipstream**
How strong the slipstream you are in is (of the most this event gives), with a bar, and
the downforce it costs when that is 5% or more. At the start of a race it shows the
event's drafting settings, later your time in a slipstream on the last lap, and who is
drafting you.

**Speed and pedals**
Your speed in km/h or mph (yellow while you roll without throttle or brake), with throttle
and brake bars beside it. With **Gear and revs in the speed section**, the gear above it (R
only while reversing, red near the shift) and rev lights below it. On Linux the bars follow
your gamepad's triggers smoothly; on the Mac and Windows they move in TSU's own steps
(thirds).

### Race

**Nearby cars**
The race leader on top, then the 3 cars ahead of you and the 3 behind you on the track,
with you always in the same row, whatever lap each car is on. Each row has the place, the
flag, the name, the tire compound, **PIT** with its timers while in the pits, and the live
gap to you (or `+1 L` for a lap). A name in orange is a lap or more ahead of you in the race
(let it by), in blue a lap or more behind. **DNF** marks a car out of the race. Spectating,
it shows the gaps to the leader.

**Track map**
The track from above, with you as a white ring (always on top, ringed in yellow when you
caused a yellow flag), the race leader in gold, the next car ahead in red and the next car
behind in green; when you pass a car, the next one ahead takes the red dot. Small bluish
dots are backmarkers between you and the car ahead. **Other cars on the track map** adds
everyone else as faint grey dots. Cars in a yellow flag are ringed in yellow and their
sector's road turns yellow.
The map is learnt from where the cars drive: on a track new to TurboHUD it grows during the
first lap and is complete once a car has driven a whole clean lap (not through the grass
with all four wheels, not standing or going backwards). TurboHUD compares three clean laps
and keeps the one nearest the others, so a shortcut is not learnt unless most cars take it.
The map is saved and shows at once the next time. If it was learnt wrong, use **Relearn
this track's map**. Only in races and special events, not in the arena modes. Its **Tint**
in move mode turns its dark square on (the default) or off. It is square: size it at a
corner.

**Radar**
Your car and the cars around you, when one is within half a second behind or ahead (faint)
up to alongside (fully visible): red right beside you, yellow closing in. It shows about six
car lengths ahead and behind; a car further behind that already counts is an arrow at the
bottom edge, fainter the further away. In a multi-class race a car of another class is
filled in its class's colour. With **Slipstream cones on the radar**, the
slipstream behind each car ahead shows as a cone. By default it shows only in the cockpit
cameras. How soon it shows is set under **Settings…**.

**Blue flag**
A navy bar that fades in when a car about to lap you is within 2 seconds behind (faint at
2 s, fully visible from 0.5 s), and goes once it has passed. How soon it shows is set under
**Settings…**.

**Yellow flag**
A yellow box when a car (yours too) has an incident in your sector or the next one, as
marshals show it: all four wheels off the tarmac, slow, stopped, spun (going backwards),
driving the wrong way (once the map has learnt the track), wrecked, or put back on the
track. It says **YELLOW - Sector 3** and lists each car with its sector and what happened.
It goes 3 seconds after the car is back on the track and up to speed; not for cars in the
pits. When a car stopped on the tarmac, or one going the wrong way, is up to 5 seconds
ahead of you on the road, it says **CAR STOPPED AHEAD** or **WRONG WAY AHEAD** instead.
Placed where the blue flag is, while both are out the yellow box gets a thick blue frame
instead of a second box. Only your own HUD warns: nothing changes for anyone else.

**Penalties**
An orange box: **SHORTCUT** with the seconds left while TSU slows you for taking a
shortcut (on tracks whose maker defined shortcuts), and **JUMP START** while TSU holds you
for a false start (throttle on the red lights) and 1.5 s more.

### Other

**Clock**
Your computer's clock.

**Time since start**
"TurboHUD - time since start": how long TurboHUD has been running. It shows while there is no
race.


## 4. Move mode and the panel

Press **Ctrl+Shift+L** (Windows, Mac, Hyprland), choose **Move mode** in the icon's menu, or
on other Linux desktops run `TurboHUD --toggle`. Every section gets a blue tint, a faint **grid** on the
screen most of them are on helps line them up (a line every 20 px, a stronger one every 100 px, the screen's
middle in yellow), and the panel opens.

Outside a race, every section shows a **preview**: one moment of a made-up race at Laguna
Seca, lap 10 of 15 with 20 drivers and you in 6th, so you see each section as it looks in a
race while you place it. Its lap times and gaps come from a real race there; the names are
made up. It follows your options (columns, clan tags, sector bars, gear, km/h or mph). In a
race, the sections show the race instead.

**On the screen**
- **Drag** a section to move it anywhere, also to another screen.
- **Click** a section to select it (a frame in the highlight colour), then **nudge** it with
  the arrow keys: 1 px, with Shift 10 px.
- **Drag a corner** to make its text bigger or smaller; **drag an edge** to give it more
  room. Rest the pointer on a section to see its name.

**The panel's columns**, one row per section, under the headings Timing, Car, Race, Other:
- **Show**: tick to show the section. **All** and **None** show or hide every section at once.
- **Group**: put sections in the same group (A to D) to move them together; resizing one
  resizes the others by the same amount.
- **Centre**: **↔** centres the section across the screen it is on, **↕** down it.
- **Mid text**: puts the text in the middle of its box instead of at the left.
- **Tint**: a light tint behind this section's text while locked; for the track map, its
  dark square.
- **Size px**: this section's text size in pixels, or **global** to follow the global size.
  Flags, tire rings and bars grow with it.
- **Lines %**: the room between its rows, in percent of the usual.

**Below the rows**
- **Same text size and width, group:** **A**, **B**, **C** or **D** gives that group's text
  sections the largest text size among them and one width (save a preset first to be able
  to go back).
- **Global text size (px)**: the text size of every section set to global. **All global**
  sets every text section back to the global size.
- **Presets** (1, 2, 3): **Save** keeps the layout as it is now in that preset (replacing
  what was there), **Load** puts the sections back as it has them (also Ctrl+Shift+1, 2, 3,
  at any time, also during a race), **Delete** deletes it. A preset holds where each
  section sits, its size, whether it shows and its group; colours and options stay as they
  are.
- **Load screen default**: TurboHUD's layout for this screen's size (your own for that
  size first, see section 5).
- **Export…** saves the layout to a file, to share or keep. **Import…** loads one, fitted
  to this screen if it was made for another.
- **Design for:** picks a screen size, this screen's first, marked "(this screen)".
  **Design** shows that size as a frame on your screen, to scale, with its layout inside to
  arrange; **Save design…** saves it at full size as a file for that size, and **Cancel**
  brings your own layout back.
- **Undo** goes back one change to the layout at a time (moving, sizing, showing, groups,
  centring, matching, presets); a drag or a run of nudges is one change. **Redo** goes
  forward again. Colours and options are not in it, and it starts afresh at each start.
- **Relearn map**: the same as **Relearn this track's map** in the icon's menu.
- **Lock** ends move mode. **Settings…** opens the settings window. **Quit TurboHUD** quits.

Move mode ends with Ctrl+Shift+L, **Lock**, or when a race begins; a click on the game does
not end it. Your layout is saved as you change it.


## 5. Layouts for every screen size

TurboHUD comes with layouts for 1920x1080, 2560x1440, 2560x1600, 3840x2160 and 5120x1440.
They are in the **`customization/display_presets`** folder beside TurboHUD: beside
`TurboHUD.exe` on Windows, beside the `TurboHUD` program on Linux; on the Mac, and wherever
that folder cannot be written to, in TurboHUD's settings folder (section 8). They are named
like `2560x1440 (TurboHUD default).json`.

- **First start.** When your main screen has one of those sizes, TurboHUD lays out the HUD as
  that layout has it; for another size it takes the nearest one, fitted to your screen.
- **Your own layout always wins.** Once you have placed sections, TurboHUD's layouts never
  move them again, also not after an update. A layout file of your own for your screen's
  size in that folder (any name without "(TurboHUD default)") is taken instead of
  TurboHUD's: at a start it is taken once, and again each time the file changes, so moving
  sections afterwards sticks.
- **TurboHUD's own files** are written again by every new version (and come back when
  deleted). To change one, arrange the HUD and save it under another name: **Export…** does.

**Export…**, **Import…** and **Save design…** open that folder. A layout file holds only
places, sizes, text sizes and options: nothing personal, so it can be shared.


## 6. The settings window

Open it with **Settings…** in the icon's menu or in the move-mode panel.

- **Text**, **Highlight** and **Outline**: the colours of the text, of the highlighted
  parts (your own row, headings) and of the thin outline that keeps text readable over
  the game. **Reset colours** puts the defaults back.
- **All sections:** **Smaller** and **Bigger** make every section 10% smaller or bigger.
- The on/off options, the same as under **Options** in the icon's menu (section 2).
- The standings' columns: **Standings: flag**, **Standings: lap number**, **Standings: tire
  compound**, **Standings: best lap** and **Standings: last lap**.
- **Blue flag when a car about to lap you is within:** 1 to 10 seconds (2 by default).
- **Radar when a car is within:** 0.2 to 3 seconds (0.5 by default); a longer
  time zooms the radar out.
- **Race reads a second:** 20, 10 or 5. Fewer ask less of the game, but the delta and the
  track map move less smoothly, and a track first learnt at 5 gets a coarser line.
- **Car classes...**: every car class a clan tag can name, by category in its colour.
- **About...**: the name and the version. **Close** closes the window.


## 7. Keyboard shortcuts and commands

| Keys | Does | Where |
|---|---|---|
| **Ctrl+Shift+L** | Move mode on / off | Windows, Mac, Hyprland |
| **Ctrl+Shift+F12** | The same, when another program has Ctrl+Shift+L | Windows, Hyprland |
| **Ctrl+Shift+1**, **2**, **3** | Load layout preset 1, 2 or 3 | Windows, Mac, Hyprland |
| **Ctrl+Shift+Q** | Quit TurboHUD | Windows, Mac, Hyprland |
| **Arrow keys** (Shift: 10 px) | Nudge the selected section | move mode |

They work while you play. If Ctrl+Shift+L does nothing on Windows, another program has it
(AMD Software: Adrenalin Edition does by default): see `Quick Start.txt`.

On Hyprland (for example Omarchy), TurboHUD adds these keys to Hyprland while it runs and
takes them away when it quits. Only keys nothing else uses: where your own setup already has
Ctrl+Shift+L, TurboHUD takes Ctrl+Shift+F12 for move mode, and a key you use for something
else stays yours (TurboHUD's log names it). Your Hyprland files are not changed; after a
reload of Hyprland's settings (Omarchy does one when you change the theme) TurboHUD adds
the keys again within a moment.

Other Linux desktops (KDE, GNOME ...) have no shortcuts in TurboHUD. Use the icon's menu, or
these commands (on Hyprland too), which you can put on keys in your desktop's own keyboard
settings:

| Command | Does |
|---|---|
| `TurboHUD --toggle` | move mode on or off |
| `TurboHUD --move` / `--lock` | move mode on / off |
| `TurboHUD --settings` | open the settings window |
| `TurboHUD --preset 1` | load layout preset 1 (or 2, or 3) |
| `TurboHUD --quit` | quit TurboHUD |

On Linux, live race data needs TSU started through TurboHUD: `TurboHUD --launch-option`
prints the line for TSU's Launch Options in Steam (see `Read Me First.txt`).


## 8. Files, and reporting a problem

TurboHUD writes only its own files, in its settings folder:
- Windows: `%APPDATA%\TurboHUD`
- macOS: `~/Library/Application Support/TurboHUD`
- Linux: `~/.config/TurboHUD`

There you find `settings.json` (your layout, presets, colours and options), `tracks/` (the
learnt track maps), `flags/` (TSU's flag pictures, read from your copy of the game and made
small), and the logs: `turbohud.log`, plus `bottle_reader.log` on the Mac and
`memory_probe.log` on Linux. It writes nothing into the game's folders.

When reporting a problem, say what you did and what you saw, and send `turbohud.log` right
after it happened: it is replaced at the next start. The logs can hold player names and
folder names: look through them first if you like.
