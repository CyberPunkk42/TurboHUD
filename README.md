# TurboHUD

A HUD overlay for Turbo Sliders Unlimited (TSU): it sits on top of the running game,
lets every click through, and shows information while you race. It works with TSU's
Fullscreen mode too.

Early version. On Linux the HUD shows live lap times (lap and time left, the running
lap, the delta to your best lap, last and best lap) when TSU is started through TurboHUD's memory probe, see
[Live lap times on Linux](#live-lap-times-on-linux). On Windows and macOS it shows a
session clock for now. Fuel estimate, speed and minimap are planned.

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
3. Linux has no shortcuts yet: Ctrl+Shift+L and Ctrl+Shift+Q do nothing there. Use the
   TurboHUD icon's menu (in the tray or status bar) instead: **Move mode** shows the blue
   box with the **Lock** and **Close** buttons, **Quit TurboHUD** quits. Where the
   desktop has no tray, TurboHUD starts in move mode, so **Close** quits it.
4. On Hyprland (for example Omarchy), TurboHUD asks Hyprland to float and pin its own
   window above the game, without a frame and without taking the keyboard focus; your
   Hyprland settings are not changed. On X11 Qt keeps it on top. Other Wayland desktops
   (GNOME, KDE) do not keep it on top yet.

### Live lap times on Linux
Linux lets a program read another program's memory only if it started that program.
So TurboHUD's small memory probe starts TSU: then it may read TSU's memory, and nothing
else's, with no sudo and no change to the system. It only reads and never pauses the
game.
1. In Steam, right-click Turbo Sliders Unlimited > **Properties** > **General** >
   **Launch Options**, and enter (with the path to your copy of this folder):
   `python3 /home/<user>/Work/workspace/tsu_repositories/TurboHUD/experiments/tsu_memory_probe.py %command%`
2. Start TSU from Steam, and start TurboHUD (before or after; it finds the game).
3. The race sections appear when the cars stand on the grid, before the lights; in the
   menus, the lobby and while a race loads only the local time shows (hover over the
   TurboHUD icon to see what it waits for). In a race it shows the lap
   and time left, the running lap time, how far ahead (green) or behind (red) your best
   lap you are at the last checkpoint, and the last and best lap.

Clear the launch option to start TSU without the probe. The probe writes what it did to
`~/.config/TurboHUD/memory_probe.log`.

## Use

- The HUD is made of sections, each in its own small box: lap and time left, the running
  lap, the delta to your best lap, last and best lap, fuel and tires left (with the laps
  they last), the fuel to spare or short for the finish, speed with throttle and brake
  bars (km/h or mph), the player list with flags, pit status and gaps, the local time
  (on Windows and macOS for now the session clock and the local time), and a blue flag
  bar. On the first start they sit one below the other at the left of your largest
  screen (laid out as on a 1920x1080 screen), the blue flag at its top centre,
  **locked**: clicks go through them to the game.
- The **blue flag** is a navy bar that shows when a car about to lap you is within 2
  seconds behind: faint at 2 s, fully visible from 0.5 s, gone once it has passed.
- **Light tint behind the sections** (TurboHUD icon's menu, or the move-mode panel) puts
  a faint dark box behind each section's text, for reading it on bright tracks.
- The **proximity radar** shows your car and the cars around you when one is within
  half a second behind (faint) up to alongside (fully visible): red beside you, yellow
  closing in.
- **Groups:** in the move-mode panel, put sections in the same group (A to D). Dragging
  one of them then moves the whole group; the others follow a moment later.
- **Ctrl+Shift+L** (or **Move mode** in the TurboHUD icon's menu) switches to **move
  mode**: every section gets a blue tint and its name. Drag a section anywhere, for
  example to the edges of a wide screen. At its bottom-right corner, making it taller or
  shorter makes its text bigger or smaller; making it wider gives the text room (text
  only shrinks when the box is too narrow for it). A panel lets you show or hide each section, and **Lock** (or
  Ctrl+Shift+L again) ends move mode. On the Mac, clicking back into the game also locks.
- **Ctrl+Shift+Q** quits; the panel and the icon's menu have **Quit** as well. On Linux
  the shortcuts are not available yet; use the icon.

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
