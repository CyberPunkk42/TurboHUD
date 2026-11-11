# TurboHUD

A HUD overlay for Turbo Sliders Unlimited (TSU): it sits on top of the running game,
lets every click through, and shows information while you race. It works with TSU's
Fullscreen mode too.

Early version. On Linux, with TSU started through TurboHUD's memory probe (see
[Live lap times on Linux](#live-lap-times-on-linux)), the HUD shows the live race: lap
times and the delta to your best lap, fuel, tires, health, the draft, speed with pedal
bars, the player list with gaps, yellow and blue flags, a proximity radar and a track map (see
[Use](#use)). It works offline, in hotlaps and online. On macOS, with TSU in CrossOver,
the same HUD needs no setup (see [Live race data on macOS](#live-race-data-on-macos)). On
Windows it reads the race the same way, with a small read-only reader started beside TSU (Windows
lets a program read another of the same user): built, not yet tried on a Windows PC.

## Install and first start

Nothing else needs to be installed: Python and Qt are inside the download. TurboHUD is
not signed with a paid certificate yet, so Windows and macOS ask once whether to trust
it. After that it starts with a double-click.

**What to expect:** TurboHUD opens no window and has no Dock or taskbar button. When it
runs, you see:
- the HUD at the top left of the screen ("TurboHUD - session time" and a clock)
- the TurboHUD icon (black, "TSU TurboHUD") in the menu bar (Mac) or in the taskbar's
  notification area (Windows; it may be hidden behind the **^** arrow)

### macOS (Apple silicon)
Needs macOS as said in the download's `Read Me First.txt`.
1. Download `TurboHUD-<version>-macos-arm64.dmg` and double-click it. A window opens with
   `TurboHUD.app` and a link to **Applications**.
2. Drag `TurboHUD.app` onto **Applications**, then eject the disk image.
3. Double-click it. macOS says it "could not verify" TurboHUD: click **Done** (not Move to
   Trash).
4. Open **System Settings > Privacy & Security** and scroll down to **Security**. Next to
   "TurboHUD was blocked", click **Open Anyway**, enter your password, and click **Open
   Anyway** once more.
5. TurboHUD starts: look for the HUD at the top left and the TurboHUD icon in the menu
   bar. From now on, a double-click is enough.

### Windows
1. Download `TurboHUD-<version>-windows-x64.zip`.
2. Right-click it, choose **Extract All**, and extract it, for example to your Desktop.
   Starting it from inside the ZIP without extracting does not work.
3. Open the extracted `TurboHUD` folder and double-click `TurboHUD.exe`.
4. If "Windows protected your PC" appears, click **More info**, then **Run anyway**.
5. TurboHUD starts: look for the HUD at the top left and the TurboHUD icon in the
   notification area.

### Linux
1. Download `TurboHUD-<version>-linux-x64.tar.gz` and unpack it:
   `tar -xzf TurboHUD-<version>-linux-x64.tar.gz`
2. Start it: double-click `TurboHUD` in the unpacked `TurboHUD` folder, or in a terminal
   `./TurboHUD/TurboHUD`.
3. Linux has no shortcuts of its own (Ctrl+Shift+L and Ctrl+Shift+Q do nothing there).
   Use the TurboHUD icon's menu (in the tray or status bar): **Move mode**, **Settings…**,
   **Quit TurboHUD**. Or tell the running TurboHUD from a terminal, in a few hundredths
   of a second:

   | Command | Does |
   |---|---|
   | `run_turbohud.sh --toggle` | move mode on or off |
   | `run_turbohud.sh --move` / `--lock` | move mode on / off |
   | `run_turbohud.sh --settings` | open the settings window |
   | `run_turbohud.sh --preset 1` | load layout preset 1 (or 2, or 3) |
   | `run_turbohud.sh --quit` | quit TurboHUD |

   Starting TurboHUD again while it runs opens no second copy: it switches the running
   one to move mode. To have a key for it, bind the command in your desktop's own key
   settings yourself (TurboHUD changes none), on a combination that is still free
   (`hyprctl binds` lists the taken ones). On Omarchy, whose bindings are in Lua, a line
   in `~/.config/hypr/bindings.lua`:
   `o.bind("SUPER + SHIFT + H", "TurboHUD move mode", "sh /home/<user>/<folder>/TurboHUD/run_turbohud.sh --toggle")`.
   With a classic `hyprland.conf`:
   `bind = SUPER SHIFT, H, exec, sh /home/<user>/<folder>/TurboHUD/run_turbohud.sh --toggle`.
   Where the desktop has no tray, TurboHUD starts in move mode, so **Close** quits it.
4. On Hyprland (for example Omarchy), TurboHUD asks Hyprland to float and pin its own
   window above the game, without a frame and without taking the keyboard focus; your
   Hyprland settings are not changed. On X11 Qt keeps it on top. On other Wayland
   desktops (KDE, GNOME ...) TurboHUD runs through XWayland, where those desktops keep
   a window on top (not yet tried there; `TURBOHUD_PLATFORM=wayland` keeps Wayland).

### Live lap times on Linux
Linux lets a program read another program's memory only if it started that program.
So TurboHUD's small memory probe starts TSU: then it may read TSU's memory, and nothing
else's, with no sudo and no change to the system. It only reads and never pauses the
game. How it all works, and what it does to RAM and the game:
[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).
1. In Steam, right-click Turbo Sliders Unlimited > **Properties** > **General** >
   **Launch Options**, and enter (with the path to your copy of this folder):
   `python3 /home/<user>/Work/workspace/tsu_repositories/TurboHUD/experiments/tsu_memory_probe.py %command%`
2. Start TSU from Steam, and start TurboHUD (before or after; it finds the game).
3. The race sections appear when the cars stand on the grid, before the lights; in the
   menus, the lobby and while a race loads only the local time shows (hover over the
   TurboHUD icon to see what it waits for). In a race the sections described under
   [Use](#use) show, and stay after you finish until the race is over.

Clear the launch option to start TSU without the probe. The probe writes what it did to
`~/.config/TurboHUD/memory_probe.log`.

### Live race data on macOS
TSU runs in a CrossOver bottle, and macOS lets no Mac program read its memory. A Windows
program in the same bottle may, so TurboHUD runs a small read-only reader there (a Windows
program written in Rust, inside the app); nothing is installed into the bottle, and there is
no launch option.
1. Start TSU in CrossOver and start TurboHUD, in either order.
2. The race sections appear when the cars stand on the grid. Online, finding the race
   takes about 5 s after the event starts. Hover over the TurboHUD icon in the menu bar
   to see what it waits for.

If TSU stutters, try setting the graphics of its bottle to D3DMetal in CrossOver and restarting
TSU. On the one Mac where this was tried, TSU stuttered on the default and ran well on D3DMetal.
TurboHUD only reads this setting: while it is anything else, `turbohud.log` and the text on the
menu bar icon say so.

If TSU's bottle cannot be told apart from others, set `TURBOHUD_BOTTLE` to its name. The
throttle and brake bars move in TSU's own steps (thirds) on the Mac, as the pad's
triggers are read only on Linux. The reader's errors are in `bottle_reader.log`, next to
`turbohud.log`. If the HUD lags or TSU stutters, `turbohud.log` shows how long the race
reads took and when each search ran; it is replaced at the next start, so look before
starting TurboHUD again.

## Use

- The HUD is made of sections, each in its own small box: lap and time left, the running
  lap, the delta to your best lap, last and best lap (purple for the race's fastest lap,
  green for your best short of it, white for a slower lap; the track map's road shows
  the same purple or green for 6 seconds after such a lap; small bars below them, one per
  stretch between checkpoints, colour each sector the same way, dark yellow when slower; **Sector bars below the last
  and best lap** in the menu or the settings turns them off), fuel and tires left (with the laps
  they last), health (in events with damage), the draft (slipstream) with the downforce it costs, the fuel to spare or short for the finish, speed with throttle and brake
  bars (km/h or mph), the player list with flags, pit status and gaps, the lap times
  (every driver's best lap and running lap), the local time, a blue flag
  bar, a proximity radar and a track map. On the first start they sit one below the other at the left of your largest
  screen (laid out as on a 1920x1080 screen), the blue flag at its top centre,
  **locked**: clicks go through them to the game.
- **Spectating** an online race, you have no car, so the sections about one stay away:
  the lap section says "Spectating" with the leader's lap, the player list shows the gaps
  to the leader, the lap times list every driver, and the track map shows every car with
  the leader in gold.
- The **country flags** in the player list and lap times are TSU's own: at its start TurboHUD reads them
  from your copy of the game (only reading; a fraction of a second, and only again after a game update)
  and keeps them, made small, in its own folder (`flags/`). They are not part of TurboHUD. Each fits the
  same box, so a square or narrow flag is no larger than the others. Where the game is not found, the
  system's emoji flags show (Windows has none: the country code).
- **Multi-class races**: drivers name their class with their clan tag in TSU (`[GT3]`, `[LMP]`,
  `[LMP2]` ...). With two or more classes in the race, the lap times list comes by class, each below a
  thin line labelled with its name, numbered within its class and with the class's fastest lap in purple.
  A driver without a class tag (or with a team's, such as `[FTR]`) gets the class of the car they
  drive: the class most tagged drivers in that car have in this race. Drivers in a car no one tagged
  drives come last under **Other**. **Classes in the
  lap times** (TurboHUD icon's menu or Settings) turns it off. The tags that count are listed in the
  settings file as `class_tags` (LMP, LMP1 to LMP3, LMH, LMDH, HYPER, GTP, DPI, GT1 to GT4, GTE, GTLM, GTD,
  GTC, GTS, TCR, CUP, F1 to F4, PRO, AM, PROAM, SILV by default).
- **Settings…** sets how soon the blue flag and the radar show, and how many times a second
  the race is read (20, 10 or 5). Fewer reads ask less of the game, but the delta and the
  track map move less smoothly, and a track first learnt at 5 gets a coarser line.
- The **blue flag** is a navy bar that shows when a car about to lap you is within 2
  seconds behind: faint at 2 s, fully visible from 0.5 s, gone once it has passed.
- The **yellow flag**, dark text on a yellow box, shows when a car, yours too, has an incident in your sector or
  the next one, as marshals show it: all four wheels off the tarmac, slow, stopped,
  spun (going backwards), driving the wrong way (against the race, for 1.5 s; once the track
  map has learnt the track) or put back on the track. It names the sector and the
  drivers, and the track map rings those cars in yellow and turns their sector's road yellow (once
  it has learnt the track). It goes 3 seconds after the car is
  back on the track and up to speed; not for cars in the pits. **Yellow flags** in the
  TurboHUD icon's menu or under **Settings…** turns them off (the section and the rings). Placed in the
  same spot as the blue flag, while both are out the yellow box gets a thick blue frame instead of a
  second box, so nothing more of the track is covered; placed apart, each shows in its own spot. When a car
  stopped on the tarmac, or one going the wrong way, is up to 5 seconds ahead of you on the road, the
  box says **CAR STOPPED AHEAD** or **WRONG WAY AHEAD** instead, with that car first (once the track is
  learnt; a car parked on the grass is ignored; your own car never counts as ahead). Only your own HUD warns: nothing changes for anyone else.
- **Shortcut penalty**: on tracks whose maker defined shortcuts, TSU slows a car that takes one for a
  few seconds (the track's setting; 3 s on the one tried). While it slows you, an orange box says
  **SHORTCUT** with the seconds left; in the lap times any driver it slows shows an orange **CUT** with the
  seconds left, in place of the lap time. Cuts TSU does not penalise (over the grass elsewhere) are not
  shown here: the yellow flags show those as off track. The same box says **JUMP START** while
  TSU holds you for a false start (throttle on the red lights, or as they go out) and 1.5 s more (and the lap times show an orange **JUMP** for that driver);
  in move mode it is **Penalties**.
- **Settings…** (TurboHUD icon's menu, or the move-mode panel) picks the text,
  highlight and outline colours, makes all sections bigger or smaller at once, and holds
  the options for the whole HUD: mph, the tint behind all sections, the radar's
  slipstream cones, other cars on the track map and the sector bars (also in the TurboHUD
  icon's menu).
- **Tint**, for each text section in the move-mode panel, or **Light tint behind all sections**
  for all of them at once (in the settings and the TurboHUD icon's menu), puts
  a faint dark box behind each section's text, for reading it on bright tracks. The track
  map's **Tint** turns its dark square on (the default) or off.
- The **proximity radar** shows your car and the cars around you when one is within
  half a second behind or ahead (faint) up to alongside (fully visible): red beside you, yellow
  closing in. It shows at most about six car lengths ahead and behind, so the cars stay large; a car
  further off that already counts (with a longer warning time in **Settings…**) is an arrow at the
  top or bottom edge, fainter the further away it is.
- The **track map** shows the track from above with you (a white ring), the race leader
  (gold), the next car ahead (red) and the next car behind (green); when you pass a
  car, the next one ahead takes the red dot. Smaller bluish dots are backmarkers (cars
  you are about to lap) on the road between you and the car ahead. **Other cars on the
  track map** (TurboHUD icon's menu, or the settings) adds everyone else as faint
  grey dots. It is square; resize it at its corner in move mode. The track's shape
  is learnt from where the cars drive: on a track new to TurboHUD the map grows during
  the first lap and is complete once any car has driven a whole clean lap (not through the
  grass with all four wheels, nor standing or going backwards). TurboHUD then compares three
  clean laps, from different cars where there are enough, and keeps the one that runs nearest
  the others, leaving out laps clearly shorter than the rest: so a shortcut on the tarmac is
  not learnt unless most laps take it. That lap is saved and shows at once next time. A map
  saved by an older TurboHUD shows, and is learnt again this way.
  If a map was learnt wrong, **Relearn this track's map** (TurboHUD icon's menu) or
  **Relearn map** (move-mode panel), during a race on that track, forgets it, the saved
  one too: the map then grows again and is learnt from the next whole clean lap.
- The move-mode panel lists the sections under Timing, Car, Race and Other. **All** and
  **None** next to **Show** show or hide every section at once (one step for **Undo**).
- Every section has **↔** and **↕** buttons under **Centre** in the move-mode panel: they
  centre its box across or down the screen it is on. **Mid text** puts a section's text
  in the middle of its box instead of at the left, so with both the text is in the middle
  of the screen.
- **Groups:** in the move-mode panel, put sections in the same group (A to D). Dragging
  one of them then moves the whole group; the others follow a moment later.
- **Ctrl+Shift+L** (or **Move mode** in the TurboHUD icon's menu) switches to **move
  mode**: every section gets a blue tint; a text section's box fits closely round its
  text, so rest the pointer on it to see its name. Drag a section anywhere, for
  example to the edges of a wide screen. At its bottom-right corner, making it taller or
  shorter makes its text bigger or smaller; making it wider gives the text room (text
  only shrinks when the box is too narrow for it). A panel lets you show or hide each section, and **Lock** (or
  Ctrl+Shift+L again) ends move mode. On the Mac, clicking back into the game also locks.
- **Groups**: sections with the same group in the panel move together, and resizing one at
  its corner resizes the others by the same factors. **Same text size and width: Group A**
  (or B, C, D) gives the group's text sections the largest text size among them and one
  width. They stay where they are, and sections with bars or several rows stay taller. Save
  a preset first to be able to go back.
- **Undo** in the panel goes back one change to the layout at a time until none is left:
  moving, resizing, showing or hiding, groups, centring, matching, and loading or saving a
  preset. A drag counts as one change. Colours and options are not in it, and it starts
  afresh when TurboHUD starts.
- **Layout presets**: the panel can keep three layouts: where each section sits, its size,
  whether it shows, and its group. **Save** keeps the layout as it is now in that preset,
  replacing what was there; **Load** puts the sections back as it has them; **Delete** deletes
  it, and **Undo** brings it back. **Ctrl+Shift+1**,
  **2** and **3** load one at any time, also during a race (Linux: `run_turbohud.sh --preset
  1`, which a key can run). Colours and the other options stay as they are.
- **Ctrl+Shift+Q** quits; the panel and the icon's menu have **Quit** as well. On Linux
  there are no shortcuts: use the icon, or `run_turbohud.sh --toggle` / `--quit` (see
  Linux above).

Where each section sits, its size, whether it shows, and the look are saved in
`settings.json`, with a log of the last run in
`turbohud.log`:
- Windows: `%APPDATA%\TurboHUD`
- macOS: `~/Library/Application Support/TurboHUD`
- Linux: `~/.config/TurboHUD`

In `settings.json`, `theme` sets the text colour, accent colour, outline colour
(`#rrggbb` or `#rrggbbaa`) and `scale` (0.5 to 3). Change it while TurboHUD is closed.

## Run from the source

For development, or to try a change without building. Needs Python 3.10 or later and a
copy of this repository. The start script sets up Qt (PySide6) in `.buildtools/venv` on
the first run, which takes a minute; later starts are quick.
- macOS, Linux: in a terminal, in the repository folder: `sh run_turbohud.sh`
- Windows: in a command prompt, in the repository folder: `run_turbohud.cmd`

The terminal shows TurboHUD's log while it runs; Ctrl+C there quits it.

Tests: `python3 -B -m unittest discover -s tests` (Windows: `py -3 -B -m unittest
discover -s tests`). Builds: `python tools/build_app.py --smoke` with the packages in
`requirements-build.txt`, run on each system you want a build for.
