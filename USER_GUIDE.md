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
  opens (see section 4). On Windows and the Mac, move mode brings TurboHUD in front, so the
  mouse pointer shows over the game even mid-race; locking hands the game its focus back.
- **When the race sections show.** While TurboHUD waits for TSU, nothing shows but its icon.
  Once TSU runs, the **Clock** shows, also in the menus and the lobby. The race sections
  appear when the cars stand on the grid, before the lights, stay after you finish until
  the race is over, and go away in the lobby and the menus. Online, finding the race takes a
  few seconds after the event starts.
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
  - **One tint for each group** (Mac and Windows): sections in the same group with their tint
    on share one tint while locked, the room between them too, so the group reads as one box.
    On by default on the Mac; off by default on Windows for now, so tick it to try it there.
    Off, each section has its own tint, as before. On Linux each section keeps its own tint
    for now.
  - **Move mode grid**: the faint grid on the main screen in move mode. On by default; off,
    move mode shows no grid.
  - **Slipstream cones on the radar**: the slipstream behind each car ahead.
  - **Radar in every camera**: the radar also shows in the views from behind and outside
    the car (third person). Off by default: then it shows only while TSU's camera sits at
    the driver (first person, "CAM 5").
  - **Sector bars in My laps**: the small coloured bars, one per sector.
  - **Yellow flags**: the **Yellow flag** section and the yellow rings on the track map.
  - **Gear and revs in the speed section**: the gear above the speed and rev lights below it.
  - **Classes in the standings**: in a race with car classes, the standings grouped by class.
  - **Clan tags in the standings**: in a race without classes, each driver's clan tag in a
    column of its own.
  - **Nearby cars: only the leader and the cars next to you**: Nearby cars shows the leader,
    the car ahead, you and the car behind (4 rows). On by default; off, it shows the 3 cars
    ahead and the 3 behind.
  - **Other cars on the track map**: every other car as a faint grey dot.
- **Relearn this track's map**: during a race, forgets the map of this track (the saved one
  too); the map is then learnt again from the next whole clean lap.
- **Settings…**: opens the settings window (section 6).
- **About TurboHUD…**: the name and the version you have.
- **Quit TurboHUD**: quits it (the same as Ctrl+Shift+Q).

Only one TurboHUD runs at a time. Starting it again says "TurboHUD is already running"; on
the Mac and Linux it also switches the running one to move mode.


## 3. The sections

In move mode the panel lists the sections under four headings, in both its tabs (section 4):
**Timing**, **Car**, **Race** and **Other**. Hover over a section's name in the panel, or over the section itself in
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
Every driver in race order (in qualifying, which TSU runs as hotlapping, by best lap); at the
start, before anyone reaches the first checkpoint, in grid order, by who is furthest ahead. The
place and the name always show; every other column can be turned off under **Settings…**:
- the place, the country flag, the name (up to 18 letters, as in Nearby cars; a longer one
  ends in "…") and, in a race without classes, the clan tag (`FTR` for `[FTR]`)
- the lap each driver is on (`L3`)
- the gap to the leader (`+7.231`, or `+1 L` a lap or more behind; nothing for the leader
  and for a car out of the race). In a race with classes, the gap to that class's leader.
- the tire compound as a letter in a coloured ring, as in F1: **S** red, **M** yellow,
  **H** white; on a wet track (one whose name has `(WET)`, `(RW)`, `(QW)` or `(W)`) every
  car shows a blue **W**
- the best lap, purple for the fastest in the race (or in the class). While you watch (a
  replay, or spectating) with the **Best** column off, the name of the driver holding the fastest
  lap is purple instead, so you still see who has it. Move mode's made-up race shows it the same
  way (there the 19th car, slowed in the pits, has the fastest lap)
- the last lap, or instead: **PIT** while in the pits, then the time from pit entry to pit
  exit with the time standing in the box in brackets; an orange **CUT** with the seconds
  left while TSU slows that driver for a shortcut; an orange **JUMP** for a false start;
  **DNF** for a car out of the race.
A heading row names the columns (**Driver**, **Ovr**, **Gap**, **Best**, **Last**). Your own
row is in the highlight colour. With more than 20 drivers it shows the leader and the
drivers around you. Every column keeps room for its widest entry, so a pit stop, a penalty
or a DNF never moves the others, and the box is only as wide as the columns you show.

The **country flags** here and in **Nearby cars** are TSU's own pictures: at its start
TurboHUD reads them from your copy of the game (only reading) and keeps them, made small,
in its own folder. Where the game is not found, the system's emoji flags show (on Windows,
which has none, the country code).

**Car classes (multi-class races).** Drivers name their class with their clan tag in TSU
(`[GT3]`, `[LMP]`, `[LMP2]` ...). With two or more classes in a race, the standings come by
class, each below a thin line with its name in the class's colour, numbered within the
class, with the class's fastest lap in purple, each driver's class after the name and the
overall place (`P7`) in an **Ovr** column. The **Class code** and **Overall place** columns can be
turned off under **Settings…**; the class lines still divide the list. A driver without a class tag
(or with a team's tag) gets the class most tagged drivers in the same car have; drivers in a
car no one tagged come last under **Other**. Classes need two different cars: when everyone
drives the same car, the tags name no classes.
**Settings… > Car classes** lists every class a tag can name, in its colour. The tags
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
The percent is TSU's own: it counts against how long the compound on your car lasts in this event.

**Car health**
Your car's health as the game counts it, with a bar. Yellow with "less downforce" when the
damage costs grip, red with "slowed" when it makes the car slower. Only in events with
damage.

**Slipstream**
Driving close behind another car, you are in its slipstream (draft): less air resistance, so
more speed on the straights, but also less downforce, so less grip in the corners. The
section shows, with the bar below:

- **Draft 46%**: how strong the slipstream you are in is now, as a share of the most this
  event gives. It is strongest close behind a car and straight in line with it.
- **-12% downforce**: the grip that slipstream takes from you now (shown from 5%).
- **Nora Vest… drafts you 42%**, in the same big text: the car behind you in your
  slipstream (its name cut to 10 letters) and how strong your slipstream is for it; its colour
  goes from cyan to red the closer it gets. Nobody there, the line stays empty, so nothing
  in the section moves.
- Below, in small text: at the start of a race, the event's drafting settings, as the host
  set them, for example
  **Up to -10% drag, -80% downforce, 30 m, 20°**:
  - **-10% drag**: at its strongest, a slipstream takes up to 10% off your air resistance;
  - **-80% downforce**: and up to 80% off your downforce;
  - **30 m**: it reaches up to 30 m behind a car (in TSU's units, which are its metres);
  - **20°**: and up to 20° off the line straight behind that car: further to the side, you
    are out of it.
- Later in the race, instead: **Last lap 21% in a slipstream**, the share of your last lap
  you spent in one.

Only in events with drafting on.

**Speed and pedals**
Your speed in km/h or mph (yellow while you roll without throttle or brake), with throttle
and brake bars beside it. With **Gear and revs in the speed section**, the gear above it (R
only while reversing, red near the shift) and rev lights below it. On Linux the bars follow
your gamepad's triggers smoothly; on the Mac and Windows they move in TSU's own steps
(thirds).

### Race

**Nearby cars**
The race leader on top, then the car ahead of you and the car behind you on the track, with
you always in the same row, whatever lap each car is on. With **Nearby cars: only the leader
and the cars next to you** turned off (the icon's Options menu, or the settings window), it
shows the 3 cars ahead and the 3 behind instead, and its box grows to their rows. Each row has the place, the
flag, the name (up to 18 letters), **PIT** with its timers while in the pits (the name then
gives up letters to them and ends in "…"), the clan tag (in a race with classes: the class
and the place in it, `GT3 P7`, in the class's colour), the tire compound, and the live gap to
you (or `+1 L` for a lap). A name in orange is a lap or more ahead of you in the race (let it
by), in blue a lap or more behind. **DNF** marks a car out of the race. Spectating, it shows
the gaps to the leader. In the layouts TurboHUD comes with, its text is as large as the
standings' or a little smaller (never below 10 px); to make it larger in your own layout, set
its **Size px** in move mode, or drag a corner of it.

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
The cars around you, seen from above, so you know where they are without looking round:
your car in the middle, heading up; what is above the middle line is ahead of you, below it
behind. The cars are drawn at their real size, so cars that touch on the radar touch in the
game. It shows up to six car lengths ahead and behind, and zooms in when cars are close (down
to about two and a half car lengths), so the room between you and them is easy to see; it
zooms out again at once when a car comes up from further back.

It appears only when a car is close: faintly once one is within half a second behind or
ahead of you, fully once it is alongside or within a tenth of a second, and it fades away
again shortly after the last one has gone. Standing (on the grid) it stays away. How soon it
appears is set under **Settings…** (**Shows a car within:**, 0.5 s by default).

What you see on it:

| On the radar | Means |
|---|---|
| Light grey car in the middle | You |
| **Red** car | Right beside you, or less than 0.1 s behind: no room there |
| **Yellow** car | Closing in, within the time set (0.5 s by default) |
| **Grey** car | Near but no danger: far to the side (another part of the track) or further off |
| Car filled in a **class colour** (blue, green, purple or pink) | In a race with classes, a car of another class than yours; red or yellow round it when it is close, as above |
| **Cyan cone** behind a car ahead | Its slipstream, as far and as wide as the event has it; brighter while you are in it |
| **Cyan outline** round a car ahead | The car whose slipstream you are in now |
| **Arrow** at the top or bottom edge | A car that already counts but is further away than the radar shows, ahead or behind: coloured as a car would be, fainter the further off it is |

The cones can be turned off with **Slipstream cones on the radar**. By default the radar
shows only in the cockpit cameras; **Every camera** in the settings window (or **Radar in
every camera** in the icon's menu) shows it in the views from outside the car too. In move
mode the preview shows each of these at once.

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

**Race leader**
A banner shaded from grey to black, as on F1's TV graphics: **New Race Leader - name** when
another driver takes the lead and keeps it for 5 seconds (so a lead that changes hands and
back, or a moment's shuffle in the order, shows nothing; none when you take the lead yourself
while driving), and **Race Winner - name**, your own win too, on a black
banner with a waving checkered flag at its right end as soon as the winner crosses the line. The
text is always in the middle of the banner (of the room before the flag on the winner's). In move
mode, the **🏁** button in the Race leader row of the panel's **Text** tab switches the banner shown between a new
leader's and the winner's, to see both while placing it. Each fades in, stays and fades out, 6
seconds in all. Not at the start (the leader off the grid is no change), nor in hotlapping or
the arena modes; spectating, it shows too. Between banners nothing of it is drawn. Untick it
in the panel if you do not want it; ticked again, it starts from the leader at that moment.

**Battle**
The first part of a Race Director mode: only while you watch, in a replay or spectating, never
while you drive. On the same grey-to-black banner, in three rows: **Battle for P3**, **Possible
Overtake** in gold, and the two drivers, **name vs name**, the car ahead first. It shows when a car
is within 1 second of the car ahead and has gained at least 0.1 s on it over the last 3 seconds, or
sits within 0.4 s of it, and stays so for 2 seconds (a gap that flickers for a moment shows nothing).
Three cars or more in a row, each within 1 second of the car ahead, are a group instead: **Battle
for P5**, **Group around name** (the group's first driver) and the drivers behind it (three names,
then "+2" for more). One battle at a time, the one for the highest place; each fades in, stays and
fades out, 6 seconds in all, and the same two cars (or a group with the same first driver) not again
for a minute. Nothing in the opening lap, while the cars are still close from the start, nor for
cars in the pits, finished or out of the race, nor in hotlapping or the arena modes. Where it
starts depends on the layout for your screen; in move mode, place it like any section.

**Watched driver**
The Race Director mode's second part: only while you watch, in a replay or spectating an online
race, never while you drive. Each time the camera turns to another driver, the same grey-to-black banner names them in two rows:
**Watching** in gold, and the driver with their place, **P3 name** (no place in the arena modes).
The camera must stay on a driver for 1 second first, so flicking through the drivers names only
the one you stop at. It fades in, stays and fades out, 6 seconds in all; a driver you turn to while
it shows takes its place at once. The same driver is not named again until the camera has turned
away from them; rewound, the replay names the driver again. Spectating, it shows only where
TurboHUD can tell which car TSU's spectator camera follows. Where it starts depends on the
layout for your screen; in move mode, place it like any section.

### Other

**Clock**
Your computer's clock.

**Time since start**
"TurboHUD - time since start": how long TurboHUD has been running. It shows, instead of the
race sections, only on a system TurboHUD cannot read TSU on; on Windows, the Mac and Linux
you do not see it.


## 4. Move mode and the panel

Press **Ctrl+Shift+L** (Windows, Mac, Hyprland), choose **Move mode** in the icon's menu, or
on other Linux desktops run `TurboHUD --toggle`. Every section gets a blue tint, a faint **grid** on the
screen most of them are on helps line them up (a line every 20 px, a stronger one every 100 px, the screen's
middle in yellow; **Move mode grid** in the settings or the icon's Options turns it off), and the panel opens.

Outside a race, every section shows a **preview**: one moment of a made-up race at Laguna
Seca, 15 laps or 21 minutes, lap 10 with 20 drivers and you in 6th, just as the leader begins
lap 11. You see each section as it looks in a race while you place it, with everything it can
show, so the room it keeps is filled: pit times, a car in the pits, a shortcut penalty (CUT), a
car out of the race (DNF), a yellow flag. With **Classes in the standings** on it is a race of
two classes (GT3 and GT4), with the overall places. Its lap times and gaps come from a real
race there; the names are made up. It follows your options (columns, clan tags, classes,
sector bars, gear, km/h or mph). In a race, the sections show the race instead.

A name too long for its room ends in "…": in **Nearby cars** a car's pit times take their room
from its name while they show, and no name ever runs into the next column.

**On the screen**
- **Drag** a section to move it anywhere, also to another screen.
- **Click** a section to select it (a frame in the highlight colour), then **nudge** it with
  the arrow keys: 1 px, with Shift 10 px.
- **Drag a corner**, or the top or bottom edge, to make its text bigger or smaller; **drag a
  side edge** to give it more room. A box is never narrower than its text needs at its size:
  a side dragged further in springs back. The standings are always exactly as wide as their
  columns. Rest the pointer on a section to see its name and what it shows.
- **Where it is**: while you move, size or nudge a section, and when you click it, a small
  label at its top left shows its place and size, for example **X 1580  Y 1110  506×270**:
  X and Y count in pixels from the top-left corner of the screen it is on, then its width ×
  height. It goes 2 seconds after the last move, and never shows while locked. On the design
  screen it gives the place and size on the screen size you design for, as **Save design**
  writes them. Sections TurboHUD moves itself (a preset, **Undo**, **Redo**, the design
  screen opening or closing) show no label.

**The panel's tabs.** The panel has two tabs, **General** and **Text**, each with one row per
section, the same sections in the same order, under the headings Timing, Car, Race, Other. The
**Show** column is in both, and the same in both:
- **Show**: tick to show the section. **All** and **None** show or hide every section at once.

**General** has where each section goes and its tint:
- **Group**: put sections in the same group (A to G) to move them together; resizing one
  resizes the others by the same amount.
- **Centre**: **↔** centres the section across the screen it is on, **↕** down it.
- **Tint**: a light tint behind this section's text while locked; for the track map, its
  dark square.

**Text** has its text:
- **Mid text**: puts the text in the middle of its box instead of at the left. The Race leader,
  Battle and Watched driver banners' text is always in the middle; the Race leader row has **🏁** there instead,
  which shows the winner's banner in move mode (pressed again, a new leader's).
- **Size px**: this section's text size in pixels, or **global** to follow the global size.
  Flags, tire rings and bars grow with it.
- **Lines %**: the room between its rows, in percent of the usual.
- **Font**: this section's own font, or **global** (the default) to follow the global font (below,
  and Settings > Look > Font). The list has **System font** and your own fonts (section 6); a font
  whose file is gone shows as "(missing)", and the section is drawn in the system font until it
  comes back. Its box is fitted to the font at once.

**Below the tabs** (the same whichever tab is open)
- **Same text size and width, group:** **A** to **G** gives that group's text
  sections the largest text size among them and one width (save a preset first to be able
  to go back).
- **Global text size (px)**: the text size of every section set to global. **All global**
  sets every text section back to the global size.
- **Global font**: the font of every section whose **Font** is global, the same as Settings >
  Look > Font: change it here to change them all at once. **All global** beside it sets every
  text section back to the global font. Both are a step for **Undo**.
- **Layouts** opens the layouts window beside the panel: the presets, which preset loads
  for each kind of event, layout files and the design screen (see below).
- The line above the buttons, in electric blue, says which preset the layout is in now, such as **Preset: 3 Race**:
  the one whose sections are all where they are now (loaded, saved, or put back by Undo).
  **(changed)** after it: you have moved on from the preset loaded or saved last (save it again to
  keep the change). **Preset: none**: the layout is in none of them.
- **Undo** goes back one change to the layout at a time (moving, sizing, showing, groups,
  centring, matching, fonts, presets); a drag or a run of nudges is one change. **Redo** goes
  forward again. Colours and options are not in it, and it starts afresh at each start.
- **Relearn map**: the same as **Relearn this track's map** in the icon's menu.
- **Lock** ends move mode. **Settings** opens the settings window. **Quit TurboHUD** quits.

Move mode ends with Ctrl+Shift+L, **Lock**, or when a race begins; a click on the game does
not end it. Your layout is saved as you change it.

**The layouts window** (**Layouts** in the panel; it closes with **Close**, and when move
mode ends):
- **Presets** (1 to 5): each has a **Name** box: call it what it is for, such as Race,
  Hotlapping, Practice or Recordings (up to 24 letters). **Enter** (or clicking elsewhere) keeps
  the name. **Save** keeps the layout as it is now in that preset (replacing what was there),
  **Load** puts the sections back as it has them (also Ctrl+Shift+1 to 5, at any time, also
  during a race), **Delete** deletes it. An electric blue line below the presets confirms each for a few
  seconds, such as "✓ Preset 2 named Race" or "✓ Preset 2 Race saved". A preset holds where
  each section sits, its size, whether it shows and its group, which **Standings** columns
  show (Settings > Standings > Columns), so each preset can have its own standings, and the
  fonts: the global font and each section's own **Font**, so each preset can have its own look;
  other colours and options stay as they are. A preset saved before 2026-11-20 keeps no columns
  and no fonts: loading it shows every column and leaves the global font as it is, until you
  save it again.
- **Load by itself**: "As an event begins, the preset chosen for its mode". For each kind of
  event, pick a preset (**1** to **5**) or **Off** (all are Off at first):
  - **Recording**: a recording (replay) TSU plays.
  - **Spectating**: an online event you only watch, with no car of your own (of any kind: a
    race, hotlapping or an arena event). Joining it as a driver then loads the preset for its
    kind.
  - **Hotlapping**: a hotlapping event, which is how qualifying is run.
  - **Race**: laps of a circuit, or a race from A to B.
  - **Special event**: an arena event: Battle (deathmatch and team deathmatch), Sumo, King of
    the Hill, Tag, Soccer and the others.

  The preset loads once, as an event of another kind than the last one begins (also one
  already running when TurboHUD starts). So a section you move during a race stays where you
  put it through the next races, until an event of another kind comes. Nothing loads in move
  mode, or when the chosen preset is empty. TurboHUD cannot tell practice from a race, so a
  practice preset is one you load yourself.

  The **Race** preset is also the default layout: TurboHUD starts in it, whatever layout it had
  when it was last quit. With Race on **Off** (or its preset empty), it starts as it was left.
- **Files and screens**: **Load screen default** is TurboHUD's layout for this screen's size
  (your own for that size first, see section 5). **Export…** saves the layout to a file, to
  share or keep. **Import…** loads one, fitted to this screen if it was made for another.
- **Design**: **Design for:** picks a screen size, this screen's first, marked "(this
  screen)". **Design** shows that size as a frame on your screen, to scale, with its layout
  inside to arrange; **Save design…** saves it at full size as a file for that size, and
  **Cancel** brings your own layout back. The sections stay in the frame: one dragged or sized
  out of it goes back in as soon as you let go (a group as a whole, keeping its shape), the
  arrow keys stop at its edge, and **Centre** centres in the frame. The panel and TurboHUD's
  other windows can go anywhere.


## 5. Layouts for every screen size

TurboHUD comes with layouts for 1920x1080, 2294x1490 (a Mac's), 2560x1440, 2560x1600, 3840x2160 and
5120x1440, each designed for its size on the design screen. For any other size TurboHUD fits the
nearest one to your screen, and then the **Nearby cars** text is never smaller than the
**Standings**' text.
They are in the **`customization/display_presets`** folder beside TurboHUD: beside
`TurboHUD.exe` on Windows, beside the `TurboHUD` program on Linux; on the Mac, and wherever
that folder cannot be written to, in TurboHUD's settings folder (section 8). They are named
like `2560x1440 (TurboHUD default).json`.

- **First start.** When your main screen has one of those sizes, TurboHUD lays out the HUD as
  that layout has it; for another size it takes the nearest one, fitted to your screen. It also
  fills the five presets with ready-made ones, fitted to your screen: **1 Recording**,
  **2 Spectator/RD**, **3 Practice/Hotlapping**, **4 Race** and **5 Special Event**, each with
  its own Standings columns, and chooses them under **Load by itself** for those kinds of event
  (Race also being the layout TurboHUD starts in). Save over any of them, rename them or set
  **Load by itself** to **Off**: presets and choices of your own are never replaced.
- **Your own layout always wins.** Once you have placed sections, TurboHUD's layouts never
  move them again, also not after an update. A layout file of your own for your screen's
  size in that folder (any name without "(TurboHUD default)") is taken instead of
  TurboHUD's: at a start it is taken once, and again each time the file changes, so moving
  sections afterwards sticks.
- **TurboHUD's own files** are written again by every new version (and come back when
  deleted). To change one, arrange the HUD and save it under another name: **Export…** does.

**Export…**, **Import…** and **Save design…** open that folder. A layout file holds only
places, sizes, text sizes, fonts and options: nothing personal, so it can be shared. Its fonts
are names: the font files themselves are not in it, so whoever imports it needs the same fonts
in their fonts folder (else those sections show the system font, and the **Font** list says
"(missing)"). Imported, the sections that followed the global font of the file's maker get
that font as their own, so the layout looks as it was made, and your global font stays as it is.


## 6. The settings window

Open it with **Settings…** in the icon's menu or **Settings** in the move-mode panel.

The window has two columns, under headings. The on/off options are the same as under
**Options** in the icon's menu (section 2).

**Look**
- **Text**, **Highlight** and **Outline**: the colours of the text, of the highlighted
  parts (your own row, headings) and of the thin outline that keeps text readable over
  the game. **Reset colours** puts the defaults back.
- **All sections:** **Smaller** and **Bigger** make every section 10% smaller or bigger.
- **Font:** the global font, for every section whose own **Font** in move mode is global (all
  of them, until you give one its own): **System font** (the usual one), or a font of your
  own. The move-mode panel's **Global font** is the same setting. **Add font...** opens a file window: choose a font file (`.ttf` or `.otf`) and it is copied
  into the **`customization/fonts`** folder (beside `customization/display_presets`, section 5)
  and used at once; your own file stays where it was. **Fonts folder...** opens that folder, to
  add files by hand or delete one to remove its font. As the folder's window would open beneath
  TurboHUD's, the settings window closes and move mode ends first. Fonts put in the folder by
  hand show the next time the settings window opens. Every section's box is fitted to
  the new font at once. TurboHUD draws its text bold, so a font with a bold style looks best;
  letters a font lacks come from the system font. A chosen font whose file is gone shows as
  "(missing)", and the system font is drawn until it comes back.
- **Light tint behind all sections**, **One tint for each group** (Mac and Windows; see section 2),
  **Move mode grid** and **Speed in mph**.

**Standings**
- **Classes in the standings** and **Clan tags in the standings**.
- **Columns:** **Flag**, **Lap** (the lap each driver is on), **Tire**, **Gap** (to the
  leader), **Best**, **Last** (the last lap), **Class code** and **Overall place** (in a race with
  classes): which columns the standings show. The place and the name always show. Each
  column left out makes the box narrower. **Class code** and **Overall place** are greyed out
  while **Classes in the standings** is off, as they show only in a race grouped by class; they
  keep their tick for when it is on again. **Classes in the standings** is what groups the race
  by class; **Class code** only shows each driver's class after the name, the class lines
  dividing the list either way. A preset keeps the columns shown when it was saved and
  loads them again (see the layouts window), as do layout files (**Export…**, **Import…**).

**Sections**
- **Nearby cars: only the leader and the cars next to you**, **Sector bars in My laps**,
  **Gear and revs in the speed section** and **Other cars on the track map**.

**Radar**
- **Show in:** **Cockpit cameras** (the default: only while TSU's camera sits at the driver,
  first person or "CAM 5") or **Every camera** (also the views from behind and outside the
  car, third person).
- **Slipstream cones on the radar**.
- **Shows a car within:** 0.2 to 3 seconds (0.5 by default); a longer time zooms the radar
  out.

**Flags**
- **Yellow flags**.
- **Blue flag for a car within:** how far behind you a car about to lap you shows the blue
  flag, 1 to 10 seconds (2 by default).

**Reading the race**
- **Race reads a second:** 20, 10 (the default) or 5. Fewer ask less of the game, but the delta and the
  track map move less smoothly, and a track first learnt at 5 gets a coarser line.

At the bottom:
- **Car classes**: every car class a clan tag can name, by category in its colour.
- **About**: the name and the version. **Close** closes the window.


## 7. Keyboard shortcuts and commands

| Keys | Does | Where |
|---|---|---|
| **Ctrl+Shift+L** | Move mode on / off | Windows, Mac, Hyprland |
| **Ctrl+Shift+F12** | The same, when another program has Ctrl+Shift+L | Windows, Hyprland |
| **Ctrl+Shift+1** to **Ctrl+Shift+5** | Load layout preset 1 to 5 | Windows, Mac, Hyprland |
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
| `TurboHUD --preset 1` | load layout preset 1 (or 2 to 5) |
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
`memory_probe.log` on Linux. Beside TurboHUD (or in that folder, as section 5 says) it makes
`customization/`, with your layouts in `display_presets` and your fonts in `fonts`. It writes
nothing into the game's folders.

When reporting a problem, say what you did and what you saw, and send `turbohud.log` right
after it happened: it is replaced at the next start. The logs can hold player names and
folder names: look through them first if you like.
