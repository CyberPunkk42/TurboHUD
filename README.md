# TurboHUD

A HUD overlay for Turbo Sliders Unlimited (TSU): it sits on top of the running game,
lets every click through, and shows information while you race. It works with TSU's
Fullscreen mode too.

Early version: for now the HUD shows a session clock. Fuel estimate, minimap and lap
times are planned.

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
4. Known issue: on Wayland desktops (for example Omarchy with Hyprland), TurboHUD runs but
   does not yet stay on top of the game. On X11 it should.

## Use

- The HUD starts at the top left, **locked**: clicks go through it to the game.
- **Ctrl+Shift+L** switches to **move mode**: the box gets a blue tint; drag it, resize
  it at the bottom-right corner, then press **Lock** (or Ctrl+Shift+L again). Clicking
  back into the game also locks it.
- **Ctrl+Shift+Q** quits.
- The TurboHUD icon in the taskbar tray or menu bar has the same: **Move mode** and
  **Quit**. On Linux the shortcuts are not available yet; use the icon.

The position, size and look are saved in `settings.json`, with a log of the last run in
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
