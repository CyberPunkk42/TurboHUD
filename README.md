# TurboHUD

A HUD overlay for Turbo Sliders Unlimited (TSU): it sits on top of the running game,
lets every click through, and shows information while you race. It works with TSU's
Fullscreen mode too.

Early version. On Linux, with TSU started through TurboHUD's memory probe (see
[Live lap times on Linux](#live-lap-times-on-linux)), the HUD shows the live race: lap
times and the delta to your best lap, fuel, tires, health, the draft, speed with pedal
bars, the player list with gaps, yellow and blue flags, a proximity radar and a track map (see
[Use](#use)). It works offline, in hotlaps, in a Custom race, online (as a guest, as a host
and as a spectator) and in TSU's replays. On macOS, with TSU in CrossOver,
the same HUD needs no setup (see [Live race data on macOS](#live-race-data-on-macos)). On
Windows it reads the race with a small read-only reader started beside TSU (Windows lets a
program read another of the same user), also with no setup: it has read online and Custom races
there; the overlay over TSU's Fullscreen modes on Windows is still to be tried.

New here? [QUICK_START.md](QUICK_START.md) is a one-page guide: install, first start, placing
the HUD, all keyboard shortcuts, and what to do when AMD Software takes Ctrl+Shift+L. Every
download has it as `Quick Start.txt`, and [USER_GUIDE.md](USER_GUIDE.md) (`User Guide.txt`)
explains every section, menu item, button and option.

## Install and first start

Nothing else needs to be installed: Python and Qt are inside the download. TurboHUD is
not signed with a paid certificate yet, so Windows and macOS ask once whether to trust
it. After that it starts with a double-click.

**What to expect:** TurboHUD opens no window and has no Dock or taskbar button. When it
runs, you see:
- a small HUD: "TurboHUD - session time" and the local time (until a race shows the rest)
- the TurboHUD icon (a speedometer) in the menu bar (Mac) or in the taskbar's
  notification area (Windows; it may be hidden behind the **^** arrow)

Only one TurboHUD runs at a time: starting it again says "TurboHUD is already running" (on
macOS and Linux it also switches the running one to move mode). **About TurboHUD…** in the
icon's menu shows the version you have.

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
5. TurboHUD starts: look for the session time on the screen and the TurboHUD icon in the menu
   bar. From now on, a double-click is enough.

### Windows
1. Download `TurboHUD-<version>-windows-x64.zip`.
2. Right-click it, choose **Extract All**, and extract it, for example to your Desktop.
   Starting it from inside the ZIP without extracting does not work.
3. Open the extracted `TurboHUD` folder and double-click `TurboHUD.exe`.
4. If "Windows protected your PC" appears, click **More info**, then **Run anyway**.
5. TurboHUD starts: look for the session time on the screen and the TurboHUD icon in the
   notification area.

### Linux
Needs a 64-bit Linux with glibc 2.35 or newer (Ubuntu 22.04, Linux Mint 21, Debian 12,
Fedora 36, SteamOS 3.5, Arch or newer) and TSU's native Linux version. The download's
`Read Me First.txt` has these steps too.
1. Download `TurboHUD-<version>-linux-x64.tar.gz` and unpack it where it can stay:
   `tar -xzf TurboHUD-<version>-linux-x64.tar.gz -C ~`
2. Start it: double-click `TurboHUD` in the unpacked `TurboHUD` folder, or in a terminal
   `./TurboHUD/TurboHUD`.
3. On Hyprland (for example Omarchy) the shortcuts are the same as on Windows: while it
   runs, TurboHUD adds Ctrl+Shift+L, Q, 1, 2 and 3 to Hyprland's keys, only where nothing
   else has them (Ctrl+Shift+F12 for move mode where Ctrl+Shift+L is taken), and takes them
   away at quit. No Hyprland file is changed; after a reload of Hyprland's settings they
   come back within a moment. Other desktops have no shortcuts in TurboHUD (Ctrl+Shift+L
   and Ctrl+Shift+Q do nothing there).
   Everywhere, use the TurboHUD icon's menu (in the tray or status bar): **Move mode**, **Options**,
   **Settings…**, **Quit TurboHUD**. Or tell the running TurboHUD from a terminal, in a few
   hundredths of a second (with the download, `~/TurboHUD/TurboHUD --toggle` and so on; from
   the source, `run_turbohud.sh`):

   | Command | Does |
   |---|---|
   | `TurboHUD --toggle` | move mode on or off |
   | `TurboHUD --move` / `--lock` | move mode on / off |
   | `TurboHUD --settings` | open the settings window |
   | `TurboHUD --preset 1` | load layout preset 1 (or 2, or 3) |
   | `TurboHUD --quit` | quit TurboHUD |

   Starting TurboHUD again while it runs opens no second copy: it switches the running
   one to move mode. To have a key for it on another desktop, or another key on Hyprland,
   bind the command in your desktop's own key settings yourself, on a combination that is still free
   (`hyprctl binds` lists the taken ones). On Omarchy, whose bindings are in Lua, a line
   in `~/.config/hypr/bindings.lua`:
   `o.bind("SUPER + SHIFT + H", "TurboHUD move mode", "sh /home/<user>/<folder>/TurboHUD/run_turbohud.sh --toggle")`.
   With a classic `hyprland.conf`:
   `bind = SUPER SHIFT, H, exec, sh /home/<user>/<folder>/TurboHUD/run_turbohud.sh --toggle`.
   Where the desktop has no tray, TurboHUD starts in move mode, so **Close** quits it.
4. On Hyprland (for example Omarchy), TurboHUD asks Hyprland to float and pin its own
   window above the game, without a frame and without taking the keyboard focus, and adds
   its shortcuts while it runs; your Hyprland files are not changed. On X11 Qt keeps it on top. On other Wayland
   desktops (KDE, GNOME ...) TurboHUD runs through XWayland, where those desktops keep
   a window on top (not yet tried there; `TURBOHUD_PLATFORM=wayland` keeps Wayland).

### Live lap times on Linux
Linux lets a program read another program's memory only if it started that program.
So TurboHUD's small memory probe starts TSU: then it may read TSU's memory, and nothing
else's, with no sudo and no change to the system. It only reads and never pauses the
game. How it all works, and what it does to RAM and the game:
[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).
1. In Steam, right-click Turbo Sliders Unlimited > **Properties** > **General** >
   **Launch Options**, and enter the line for your TurboHUD. With the download,
   `~/TurboHUD/TurboHUD --launch-option` prints it, for example
   `"/home/<user>/TurboHUD/TurboHUD" --probe %command%` (do it again if you move the folder).
   From the source folder (with the path to your copy of it):
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

### Live race data on Windows
Windows lets a program read another of the same user, so there is no launch option: TurboHUD
starts its small read-only reader (`turbohud-reader.exe`, in the download) beside TSU.
1. Start TSU and TurboHUD, in either order.
2. The race sections appear when the cars stand on the grid; online, finding the race takes a
   few seconds after the event starts (a search of the game's data, about 6 s at most).

## Use

The full guide to every section, menu item, button and option is
[USER_GUIDE.md](USER_GUIDE.md) (in every download as `User Guide.txt`). In short:

- The HUD is made of **sections** (lap, delta, fuel, tires, player list, lap times, flags,
  radar, track map and more), each in its own box. Locked, clicks go through them to the game.
- **Ctrl+Shift+L** (or **Move mode** in the TurboHUD icon's menu; on Linux outside
  Hyprland `TurboHUD --toggle`) switches to **move mode**: drag, nudge and size the sections, and use
  the panel to show or hide them, group and centre them, set text sizes, keep three presets
  (**Ctrl+Shift+1**, **2**, **3** load them) and load, share or design layouts per screen size.
  **Lock** or Ctrl+Shift+L again ends it, and so does a race beginning.
- **Settings…** sets the colours, the size of all sections, the lap times' columns, the
  warning times, the race reads a second and the on/off options (also under **Options** in
  the icon's menu).
- **Ctrl+Shift+Q** quits; on Windows **Ctrl+Shift+F12** is a spare for Ctrl+Shift+L.

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
`requirements-build.txt`, run on each system you want a build for; the Rust reader for
Windows and the Mac first with `sh tools/get_rust.sh`. The Linux build is made in an Ubuntu
22.04 container with `sh tools/build_linux.sh <version>`, so it starts on glibc 2.35 and newer.
