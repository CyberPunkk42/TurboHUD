# TurboHUD

A HUD overlay for Turbo Sliders Unlimited (TSU): it sits on top of the running game,
lets every click through, and shows information while you race. It works with TSU's
Fullscreen mode too.

Early version. On Linux, with TSU started through TurboHUD's memory probe (see
[Live lap times on Linux](#live-lap-times-on-linux)), the HUD shows the live race: lap
times and the delta to your best lap, fuel, tires, health, the draft, speed with pedal
bars, the player list with gaps, a blue flag, a proximity radar and a track map (see
[Use](#use)). It works offline, in hotlaps and online. On macOS, with TSU in CrossOver,
the same HUD needs no setup (see [Live race data on macOS](#live-race-data-on-macos)). On
Windows it shows a session clock and the local time for now.

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
1. Download `TurboHUD-<version>-macos-arm64.zip` and double-click it in Downloads. You get
   `TurboHUD.app`.
2. Drag `TurboHUD.app` into **Applications**.
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
program in the same bottle may, so TurboHUD runs a small read-only reader there, with its
own Windows Python; nothing is installed into the bottle, and there is no launch option.
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
  lap, the delta to your best lap, last and best lap, fuel and tires left (with the laps
  they last), health (in events with damage), the draft (slipstream) with the downforce it costs, the fuel to spare or short for the finish, speed with throttle and brake
  bars (km/h or mph), the player list with flags, pit status and gaps, the lap times
  (every driver's best lap and running lap), the local time
  (on Windows for now the session clock and the local time), a blue flag
  bar, a proximity radar and a track map. On the first start they sit one below the other at the left of your largest
  screen (laid out as on a 1920x1080 screen), the blue flag at its top centre,
  **locked**: clicks go through them to the game.
- **Spectating** an online race, you have no car, so the sections about one stay away:
  the lap section says "Spectating" with the leader's lap, the player list shows the gaps
  to the leader, the lap times list every driver, and the track map shows every car with
  the leader in gold.
- **Settings…** sets how soon the blue flag and the radar show.
- The **blue flag** is a navy bar that shows when a car about to lap you is within 2
  seconds behind: faint at 2 s, fully visible from 0.5 s, gone once it has passed.
- **Settings…** (TurboHUD icon's menu, or the move-mode panel) picks the text,
  highlight and outline colours, and makes all sections bigger or smaller at once.
- **Tint**, for each text section in the move-mode panel, or **Light tint behind all sections**
  for all of them at once (also in the TurboHUD icon's menu), puts
  a faint dark box behind each section's text, for reading it on bright tracks.
- The **proximity radar** shows your car and the cars around you when one is within
  half a second behind or ahead (faint) up to alongside (fully visible): red beside you, yellow
  closing in.
- The **track map** shows the track from above with you (a white ring), the race leader
  (gold), the next car ahead (red) and the next car behind (green); when you pass a
  car, the next one ahead takes the red dot. Smaller bluish dots are backmarkers (cars
  you are about to lap) on the road between you and the car ahead. **Other cars on the
  track map** (TurboHUD icon's menu, or the move-mode panel) adds everyone else as faint
  grey dots. It is square; resize it at its corner in move mode. The track's shape
  is learnt from where the cars drive: on a track new to TurboHUD the map grows during
  the first lap and is complete once any car has driven a whole lap; after that it is
  saved and shows at once.
- Every section has **Centre ↔** and **Centre ↕** buttons in the move-mode panel: they
  centre its box across or down the screen it is on. **Centre text** puts a section's text
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
  replacing what was there; **Load** puts the sections back as it has them; the bin deletes
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
