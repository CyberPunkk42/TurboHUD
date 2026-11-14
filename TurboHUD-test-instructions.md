# TurboHUD: test for the Mac, step by step

Nov 14, 2026 · build 2026.11.14 · about 65 minutes

> **Before you start:** please free at least **20 to 30 GB** on the Mac's disk (System Settings → General → Storage) and restart the Mac. With only 2 to 3 GB free, macOS has no room to swap when memory runs out, and games stutter badly.
>
> **The stutter, first (about 15 minutes).** Build 2026.11.14 writes down in its log every moment TurboHUD freezes for a split second, and why. Please:
>
> 1. Install it (Part 2), start TSU and TurboHUD, and drive **one race** (offline is fine) of at least **10 minutes**.
> 2. Every time you feel a stutter, look at the Mac's clock and **✏️ write down the time** (hours, minutes, seconds if you can): ______
> 3. Was it a **short hitch** (a jump, then smooth again) or the game **slow for a while**? ______
> 4. Right after the race, copy the log as in **Part 7** and send it with the times.
> 5. Then drive a few minutes of the **same track with TurboHUD closed** (**Control + Shift + Q**). **✏️ Write down:** did the stutter still come? ______
>
> If you only have time for this part, that's already a big help.

Thank you for testing again. This build has everything from 2026.11.11.4 (the fixes for races joined online, yellow flags, the gliding delta bar, the tidier panel), and much more:

- **The flags are TSU's own**: the player list and lap times show the same flag pictures as the game, all the same size, instead of the Mac's emoji. TurboHUD reads them from your copy of TSU when it starts (only reading).
- **Yellow flags, more of them**: a car going the **wrong way** shows as such; the yellow box keeps the **same size** whatever it lists, with **YELLOW - Sector N** in the middle; and the sector with the incident turns **yellow on the track map**.
- **Hazard ahead**: when a car stopped on the track, or one going the wrong way, is a few seconds ahead of you, the yellow box says **CAR STOPPED AHEAD** or **WRONG WAY AHEAD**.
- **Shortcut penalty**: on tracks with shortcuts TSU slows you for, an orange box says **SHORTCUT** with the seconds left, and the lap times show an orange **CUT** for any driver being slowed. A false start shows **JUMP START** in the same box while you hold the throttle on the red lights, and 1.5 seconds more.
- **Classes**: in a race where drivers use clan tags such as **[GT3]** and **[LMP]**, the lap times are grouped by class, each under a line with its name.
- **The track map** is learnt from three clean laps (a lap through a shortcut is left out), and the TurboHUD icon's menu has **Relearn this track's map** for a map learnt wrong.
- The app is smaller: 32 MB instead of 45.

New since 2026.11.11.7:

- **Your own yellow flag**: when **you** go off, spin or stop, your own HUD shows the yellow box too, and your dot on the track map gets a yellow ring.
- **Your dot on the track map** is a little smaller than the others and always on top, so you can still see it when a car is right next to you.
- **A car driving backwards**: the yellow sector on the map now follows the car, instead of staying where it turned round.
- **The radar** no longer zooms far out: it shows about six car lengths ahead and behind, so the cars stay big. A car further away shows as a small arrow at the top or bottom edge.
- **Classes on the radar**: in a race with classes, cars of another class than yours are coloured (blue, green, purple or pink), with red or yellow round them when close.
- **Clan tags in the lap times**: in a race without classes, each driver's clan tag shows in its own column after the name. The TurboHUD icon's menu has **Clan tags in the lap times** to turn it off.

New since 2026.11.11.9:

- **The player list shows the cars around you on the track**: 4 in front and 3 behind, with you always in the middle row, whatever lap each car is on. A name is orange when that car is a lap or more ahead of you in the race, blue when a lap or more behind.
- **Tire compounds**: the lap times and the player list show each driver's tire as a letter in a coloured ring, as in F1 (S red, M yellow, H white). On a wet track (one whose name has **(WET)**, **(RW)**, **(QW)** or **(W)**) every car shows a blue **W**.
- **Car classes in colour**: in a race with classes, each class in the lap times has its own colour (prototypes purple, GT blue, formula cars red ...). **Settings… > Car classes...** lists every class. The class codes are shorter now: **LDH**, **LM1** to **LM3**, **GLM**.
- **The lap times' columns are options**: the settings window turns the flag, lap number, tire, best lap and current lap columns on and off.
- **The radar's arrows** at the top and bottom edge are bigger and clearer.

New since 2026.11.12.4:

- **Smoother**: TurboHUD draws its running times and gaps about 20 times faster, and redraws only the parts of the screen that changed. This is for the stutter you saw with 2026.11.12.4. The numbers look the same.
- **A car left standing**: a car that stays slower than 29 km/h for over a minute (its driver left, or walked away) no longer keeps the yellow flag out. It counts again once it drives faster than 29 km/h.

New since 2026.11.12.6:

- **Lighter on TSU**: TurboHUD reads less from the game each time (other cars' pit, damage and tire state once a second instead of ten times). This is for the stutter while racing. A PIT or a wreck of another car can show up to a second later.
- **The player list, new order**: the race leader on top, then the 3 cars ahead of you and the 3 behind you on the track, with you always in the 5th row. The order follows where the cars really are on the track.
- **The lap times show each driver's last lap** (column **Last**) instead of the running time. A driver with no lap done yet shows **-**.
- **Steadier lists**: the lap times and the player list no longer change width or move their columns when someone pits, cuts or gets a longer gap. The player list's tint covers the whole box. The delta bar's number glides instead of jumping.
- **Replays**: TurboHUD also shows in TSU's replays, around the driver the camera follows.
- The disk image has a **Quick Start.txt**: a one-page guide for players.

New since 2026.11.12.7:

- **Text sizes in pixels**: in move mode, each text section has a **Size px** box (**global** follows the **Global text size** below the list; **All global** puts every section back on it). Dragging a text section's top or bottom edge, or a corner, sizes its text; its left or right edge adds room (longer bars). Sections with several rows have a **Lines %** box for the space between rows. Your saved layout is converted once, so it should look as before.
- **Resizing at every edge**: the radar, track map, delta bar and blue flag resize at any edge or corner in move mode.
- **Move mode stays on** when you click elsewhere; it ends with **Control + Shift + L**, **Lock**, or by itself when a race you drive begins.
- **Gear and rev lights**: the speed section can show your gear above the speed (R in reverse) and rev lights below it, green, yellow and red. It is on; **Settings…** has **Gear and revs in the speed section** to turn it off.
- **The radar only in cockpit cameras** (a setting, on by default): with a camera outside the car it hides. Its arrows now only point to cars **behind** you.
- **DNF**: a car out of the race (standing still for a minute outside the pits) shows **DNF** in the lap times and the player list.
- **Pit stops**: the stop time counts only while a car stands in its pit box; a car standing a minute anywhere in the pits shows plain **PIT** without timers.
- **Lap times**: names have a fixed 20-letter field with the columns right after it; in a race with classes an **Ovr** column shows the overall place; drivers all in the same car are no longer split into classes; in qualifying the lists go by best lap.
- **Replays**: a replay watched after a race in the same TSU session shows the HUD, and after a rewind it is back within a moment, without false wrong-way yellow flags.

New since 2026.11.13:

- **A new icon**, and **About TurboHUD…** in the TurboHUD icon's menu (also an **About...** button in **Settings…**): it shows the version.
- **Only one TurboHUD at a time**: starting it a second time no longer opens a second copy.
- **Arrow keys in move mode**: click a section (it gets a coloured frame), then the arrow keys move it 1 pixel, with **Shift** 10 pixels.
- **Layouts for screen sizes**: the move-mode panel has **Load screen default** (a ready-made layout for your screen size), **Export…** and **Import…** (a layout as a file, to share), and **Redo** beside **Undo**.
- **The lap title**: with the leader a lap ahead it is no longer cut off; the leader's lap fades in at its end, and shows for 6 seconds as the leader crosses the line ("Final lap" on the last one).

New since 2026.11.13.2:

- **The move-mode panel fits your screen**: on a smaller screen, the list of sections scrolls, and the buttons at the bottom (**Lock**, **Settings…**, **Quit TurboHUD**) always show.

New since 2026.11.13.3:

- Nothing new to see: the log now notes each moment TurboHUD freezes for a split second, and which parts of the HUD take the longest to draw. This is for the stutter.

New since 2026.11.13.4:

- Nothing new to see: the log no longer fills up with slow frames at the end of a race, so the real freezes stand out.

New since 2026.11.13.5 (this build is 2026.11.14):

- **Custom race and Single Player**: TurboHUD now shows in both (from TSU's main menu), not only online and in offline races. Please try one of each for a lap or two: do the lap, the times and the player list show? **✏️ Write down:** ______

This test checks those, and measures which of two ways of drawing TurboHUD costs TSU fewer frames. If you already did the measurements with 2026.11.11.4, send those too and you can skip Part 3.

Go through it from top to bottom. Every step is one thing to do. Where it says **✏️ Write down**, fill in the answer on this sheet.

TurboHUD only reads what the game shows. It changes nothing in TSU or in CrossOver.

---

## Part 1: Get ready (2 minutes)

You need:

- [ ] The file `TurboHUD-2026.11.14-macos-arm64.dmg`
- [ ] TSU in CrossOver, as last time
- [ ] The same way of reading TSU's FPS as last time
- [ ] The Terminal app (in **Applications > Utilities**)
- [ ] For Part 6: an online race to join, someone else's server (we can host one for you)

Pick one track and one car, and use them for Parts 3 and 4. Keep TSU in **Fullscreen**, as last time. Race against AI, offline, so every measurement has the same cars.

For fair FPS numbers: keep the Mac on its **power adapter**, with **Low Power Mode off**, and don't change **System Settings > Displays > Refresh rate** during the test (ProMotion is best).

**✏️ Write down:** Refresh rate setting: ______ On the power adapter? ______

**✏️ Write down:** Did anything change since last time (Mac, screen, TSU's graphics settings)? ______

---

## Part 2: Install the new TurboHUD (3 minutes)

In our session TurboHUD ran straight from the disk image. Please install it, as below.

1. If TurboHUD is running, quit it: press **Control + Shift + Q**.
2. Double-click `TurboHUD-2026.11.14-macos-arm64.dmg`. A window opens.
3. Drag **TurboHUD** onto **Applications**. If asked, choose **Replace**.
4. Close the window. In Finder, click the eject button next to **TurboHUD** in the sidebar. **Always eject it**: TurboHUD must start from Applications, never from the disk image.
5. **Don't open TurboHUD yet.** The first measurement is without it.

Your layout and settings from last time stay.

---

## Part 3: Measure the frame rate (5 measurements, about 12 minutes)

Each measurement is the same:

> Drive for **about one minute**, then write down the **average FPS** and whether anything stuttered.

Stay in the same race for all five if you can.

### Shortcuts you'll need

| To do this | Press |
| --- | --- |
| Open or close move mode (where the tick boxes are) | **Control + Shift + L** |
| Quit TurboHUD | **Control + Shift + Q** |

Always close move mode (**Control + Shift + L**) before you drive.

### Measurement 1: without TurboHUD

1. Make sure TurboHUD is **not** running.
2. Start TSU and start a race against AI on your track.
3. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

### Measurement 2: everything shown

1. Open **Applications** and double-click **TurboHUD**.
   - If macOS says it "could not verify" TurboHUD, see **Help** at the end, then come back here.
2. Wait until the lap and the times show on the screen.
3. Press **Control + Shift + L**. Click **All** next to "Show" at the top of the panel: every box is ticked. Press **Control + Shift + L** again.
4. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

### Measurement 3: only the local time

1. Press **Control + Shift + L**. Click **None** next to "Show", then tick **Local time** (under OTHER). Press **Control + Shift + L** again.
2. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

### Measurement 4: the other way of drawing, everything shown

1. Press **Control + Shift + Q** to quit TurboHUD.
2. Open **Terminal**, paste this, and press **Return**. Leave Terminal open:

   ```
   TURBOHUD_ONE_WINDOW=0 /Applications/TurboHUD.app/Contents/MacOS/TurboHUD
   ```

3. Wait until the lap and the times show. Press **Control + Shift + L**, click **All** next to "Show", and press **Control + Shift + L** again.
4. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

### Measurement 5: the other way of drawing, only the local time

1. Press **Control + Shift + L**. Click **None**, then tick **Local time**. Press **Control + Shift + L** again.
2. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

---

## Part 4: A quick look at what's new (10 minutes)

1. Press **Control + Shift + Q** to quit TurboHUD, then open it again from **Applications** (the normal way).
2. Press **Control + Shift + L**. Look at the panel: are all its buttons readable (All, None, Save, Load, Delete, Undo, Lock ...)? Click **None**, then **Undo**: everything should come back in one go. Click **All**, then press **Control + Shift + L**.
3. Keep driving and look at TurboHUD. Is everything there and updating (lap, times, the bars, the track map, the radar)?
4. Look at the **delta bar** (the bar under the top centre, with your time against your best lap). From your second lap on it should be:
   - round at both ends
   - always **green** or **red**, never white: green while you gain on your best lap, red while you lose
   - easy to read, and moving smoothly rather than jumping
5. **Yellow flag**: when an AI car ahead of you goes off, spins or stops, a yellow box with **YELLOW - Sector N** and its name should show, and the track map should ring it in yellow and turn its sector yellow. It goes about 3 seconds after the car is back up to speed. The box should keep its size the whole time.
6. **Flags**: look at the player list and the lap times. The flags should look like TSU's own, all the same size.
7. If a car stops on the track just ahead of you, the yellow box should say **CAR STOPPED AHEAD**.
8. If your track has shortcuts that TSU slows you for: take one. An orange **SHORTCUT** box should count down, and the lap times should show **CUT** next to you. (First place the box: in move mode, tick **Penalties** under RACE and drag it where you like.)
9. In one race against AI, hold the throttle while the red lights are on (a false start). The orange box should say **JUMP START** while you hold it, and go 1.5 seconds after you let go or the lights go out.
10. **Your own yellow flag**: drive off the track with all four wheels onto the grass for a second (or spin). The yellow box should show **your** name, and your dot on the track map should get a yellow ring. There should be **no** CAR STOPPED AHEAD for your own car.
11. **Your dot**: when you are right behind or beside a car, can you still see your own dot (the white ring) on the track map?
12. **Driving backwards**: turn round and drive back a little into the sector before. Your yellow sector on the map should move back with you.
13. **The radar**: are the cars big enough to read at a glance? When a car is a bit further behind, does an arrow show at the bottom edge (and none at the top for cars ahead)? Is it easy to see? Switch to a camera outside the car: does the radar hide, and come back in the cockpit view?
14. **The player list**: is the race leader on top, and are you in the 5th row, with the 3 cars just in front of you on the track above and the 3 just behind below? When you lap a car or are lapped, does its name turn blue or orange?
15. **Tires**: is there a coloured ring with a letter next to each driver in the lap times and the player list? Which letters and colours do you see? If you change tires in the pits, does yours change?
16. **Settings**: open **Settings…** from the TurboHUD icon's menu. Turn **Lap times: tire compound** off and on again: the ring column should go and come back. Click **Car classes...**: a sheet with every class in its colour should open.
17. If you can, run one race on a track whose name has **(WET)**, **(RW)**, **(QW)** or **(W)**: every car should show a blue **W**.
18. **Lap times, Last column**: does each driver show their last lap time (not a running clock)? Does a driver with no lap done show **-**?
19. **Steady lists**: when a car goes into the pits (PIT with a timer), do the lap times and the player list keep their width, with the columns staying where they are?
20. **Replay** (if you know how to watch a replay in TSU): open one. Does TurboHUD show, around the driver the camera follows? Switch to another driver: does the HUD follow? Rewind it: does the HUD come back quickly, with no yellow WRONG WAY for cars driving normally?
21. **Text sizes** (before a race, in move mode): type a size in one section's **Size px** box, then drag another section's bottom edge. Does the text grow and shrink, with the box staying tight round it? Change **Global text size**: do the sections without their own size follow?
22. **Move mode**: open it, click on the desktop or the game. It should stay open. Then start a race: it should close by itself when the race begins.
23. **Gear and revs** (on unless you turned off **Gear and revs in the speed section** in **Settings…**): while driving, does the gear change and the rev lights fill up to red before each shift? In reverse, does it show **R**?
24. **Pits**: stop in your pit box. Does the stop timer run only while you stand in the box?
25. **About**: open **About TurboHUD…** from the TurboHUD icon's menu. Does it show the new icon and **2026.11.14**? Then try to start TurboHUD a second time from Applications: no second copy should open.
26. **Arrow keys** (in move mode): click one section, then press the arrow keys, and **Shift** + an arrow key. Does it move a little, and more with Shift? Press **Undo**: does it go back?
27. **Lap title**: when the leader is a lap ahead of you, can you read the whole lap title? When the leader crosses the line, does their lap show for a few seconds?
28. **The panel on your screen** (in move mode): can you see the whole panel, down to **Quit TurboHUD**? If the list of sections scrolls, can you scroll it to **Local time** at the bottom?

**✏️ Write down:** Panel buttons readable? None and Undo worked? ______

**✏️ Write down:** Everything there and updating? ______ The delta bar: ______

**✏️ Write down:** Yellow flag: did it show when a car had trouble? Too often, too late, or about right? Did its sector turn yellow on the map? ______

**✏️ Write down:** Flags like TSU's, all the same size? ______

**✏️ Write down:** CAR STOPPED AHEAD, SHORTCUT or JUMP START seen? Did they look right? ______

**✏️ Write down:** Your own yellow flag (box and ring)? Your dot visible next to a car? The sector following you backwards? ______

**✏️ Write down:** The radar: cars big enough? Arrows at the bottom edge seen, and clear? Hidden outside the cockpit? ______

**✏️ Write down:** Player list: leader on top, you in the 5th row, cars in the right order? Blue and orange names seen? ______

**✏️ Write down:** Tires: which letters and colours? Did yours change after a pit stop? A wet track tried (blue W)? ______

**✏️ Write down:** Settings: the tire column went and came back? The class sheet opened? ______

**✏️ Write down:** Last column right? Lists steady when a car pits? ______

**✏️ Write down:** Replay: did TurboHUD show and follow the driver? Back quickly after a rewind? (or "not tried") ______

**✏️ Write down:** Text sizes: Size px, edges and global size worked? Your layout looked as before? ______

**✏️ Write down:** Move mode stayed open on a click, and closed when the race began? ______

**✏️ Write down:** Gear and rev lights right? R in reverse? Pit stop timer only in the box? ______

**✏️ Write down:** About showed the icon and 2026.11.14? No second copy? ______

**✏️ Write down:** Arrow keys moved the section (more with Shift)? Undo worked? Lap title whole, leader's lap shown? ______

**✏️ Write down:** Whole panel on the screen, down to Quit? Did the list scroll? ______

---

## Part 5: Quit the offline race (1 minute)

Leave TurboHUD running. Leave the race, and get ready to join an online race.

---

## Part 6: Races joined online (about 15 minutes)

This checks the fixes. Stay in the same session for at least **three races**, as in our session.

1. In TSU, join an online session on someone else's server (one we host, or the event server).
2. In each race, drive and look at TurboHUD. Note roughly how many seconds after the start the lap, the times and the other sections show. In the first race of the session, allow **up to one minute**.
3. Stay for the next race, and the one after, and do the same.

**✏️ Write down:** Race 1: did the HUD show? After about how many seconds? ______

**✏️ Write down:** Race 2: ______ Race 3: ______ (more if you raced more)

**✏️ Write down:** If you joined while a race was already running: did it show? ______

**✏️ Write down:** Online, did the yellow flag show when other drivers went off or spun? ______

**✏️ Write down:** If a driver stopped on the track and left: did the yellow flag go away after about a minute? ______

**✏️ Write down:** Did TSU stutter? If yes: **while driving**, or **between races / at the start** of a race? ______

If the host asks: set your clan tag in TSU to the class you're given (for example **GT3**). With two classes in the race, the lap times should be grouped by class, each under a line with its name.

**✏️ Write down:** Classes in the lap times (if tried): ______ Cars of another class coloured on the radar? ______

In a race without classes where drivers have clan tags: the lap times should show each tag in its own column after the name.

**✏️ Write down:** Clan tags in the lap times: shown, and readable? ______

Stay in the race and go to Part 7.

---

## Part 7: Copy TurboHUD's log (2 minutes)

TurboHUD keeps a log, and it's replaced each time TurboHUD starts. So copy it now, while TurboHUD is still running.

1. Switch to Terminal (**Command + Tab**) and press **Command + N** for a new window.
2. Copy all the lines in the box below, paste them into the new window, and press **Return**:

```
T=~/Library/Application\ Support/TurboHUD
echo "--- version"; grep -m1 'TurboHUD 2026' "$T/turbohud.log"
echo "--- running from"; pgrep -fl 'MacOS/TurboHUD'
echo "--- reader"; grep -E 'reading TSU through|canvas' "$T/turbohud.log" | head -5
echo "--- race"; grep -E "TSU:|TSU's log|search|quick look|watching|event type|track map|connection dropped" "$T/turbohud.log" | tail -40
echo "--- reads"; grep -E 'race reads|race pages' "$T/turbohud.log" | tail -10
echo "--- frames"; grep 'HUD frames' "$T/turbohud.log" | tail -15
echo "--- freezes"; grep -E 'slow |garbage collections|drawing by section' "$T/turbohud.log" | tail -60
echo "--- reader errors"; tail -20 "$T/bottle_reader.log" 2>/dev/null
```

3. Select all the text Terminal printed, copy it, and save it in a note or an email to send back.

This only reads information and changes nothing. It may include player names and your Mac's user name: look it over before you send it.

---

## Part 8: Quit (3 minutes)

This checks that nothing is left running and that TSU quits normally.

1. Press **Control + Shift + Q** to quit TurboHUD.
2. In Terminal, paste this and press **Return**:

   ```
   pgrep -fl 'turbohud-reader|bottle_reader'
   ```

3. Wait 5 seconds, then press **↑** (up arrow) and **Return** to run it again.

**✏️ Write down:** Did either run print anything? If yes, what? ______

4. Quit TSU the normal way, from its menu.

**✏️ Write down:** Did TSU quit normally, or freeze? ______

If TSU freezes: quit it with **Stop** in Steam, as last time.

---

## What to send back

- [ ] This sheet with everything you wrote down (or just the answers)
- [ ] The Terminal text from Part 7
- [ ] The times you felt a stutter, and whether it still came with TurboHUD closed (the part at the top)

### Summary (copy your answers here)

| # | What | Answer |
| --- | --- | --- |
| 1 | FPS without TurboHUD | |
| 2 | FPS, everything shown | |
| 3 | FPS, only the local time | |
| 4 | FPS, other way, everything shown | |
| 5 | FPS, other way, only the local time | |
| | Stutter in any of them? Which? | |
| | Panel buttons readable? None and Undo worked? | |
| | Everything there and updating? | |
| | The delta bar (round, green or red, readable, smooth)? | |
| | Yellow flag offline: shows when it should? Sector yellow on the map? | |
| | Flags like TSU's, all the same size? | |
| | CAR STOPPED AHEAD / SHORTCUT / JUMP START seen and right? | |
| | Own yellow flag, own dot, sector following a car backwards? | |
| | Radar: cars big enough, arrows at the bottom clear, hidden outside the cockpit? | |
| | Player list: leader on top, you 5th, right order, blue and orange names? | |
| | Tires: letters and colours, changed after a pit stop, wet track? | |
| | Settings: tire column off and on, class sheet? | |
| | Lap times Last column, lists steady when a car pits? | |
| | Replay: HUD shown, following the driver, back quickly after a rewind? | |
| | Text sizes: Size px, edges, global size; layout as before? | |
| | Move mode: stays on a click, closes when the race begins? | |
| | Gear and rev lights, R in reverse, pit timer only in the box? | |
| | About: icon and version right, no second copy? | |
| | Arrow keys and Undo in move mode? Lap title whole? | |
| | Whole panel on the screen? List scrolled? | |
| | Online race 1: did the HUD show? After how many seconds? | |
| | Online races 2, 3 ...: after how many seconds? | |
| | Online, joined during a race: did it show? | |
| | Online yellow flags? | |
| | A car left standing: flag gone after a minute? | |
| | Online stutter: while driving, or between races / at the start? | |
| | Classes in the lap times (in colour) and on the radar (if tried)? | |
| | Clan tags in the lap times? | |
| | Anything left after quitting TurboHUD? | |
| | TSU quit normally? | |

---

## Help

**macOS says it "could not verify" TurboHUD**

1. Click **Done** (not Move to Trash).
2. Open **System Settings > Privacy & Security**.
3. Scroll down to **Security** and click **Open Anyway** next to TurboHUD.
4. Enter your password and click **Open Anyway** again.

This happens because the test version isn't signed with a paid Apple certificate. Only open it if you trust the person who sent it.

If there's no **Open Anyway** button, open TurboHUD once more and look again (the button shows only for a while after a try). If it's still not there, paste this into Terminal, press **Return**, and try again:

```
xattr -dr com.apple.quarantine /Applications/TurboHUD.app
```

If you clicked **Move to Trash**: install it again from the disk image (Part 2), then follow the steps above.

**Other problems**

| What you see | What to do |
| --- | --- |
| No window, no Dock icon after starting TurboHUD | That's normal. Look for its black icon in the menu bar. |
| Only a clock, in a menu, lobby or custom session | That's normal: there's no race to read. Start a real race. |
| Only a clock, during a race | Wait a minute. If nothing changes, copy the log (Part 7) and tell us. |
| A warning that the graphics setting is not D3DMetal | In CrossOver, set the bottle's graphics to **D3DMetal**, restart TSU, and tell us you changed it. |
| TurboHUD won't open | Do the **Open Anyway** steps above again. |

**Removing TurboHUD:** quit it and move it from Applications to the Bin. Its settings and logs are in `~/Library/Application Support/TurboHUD`.
