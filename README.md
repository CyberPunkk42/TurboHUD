# TurboKit

A HUD overlay for Turbo Sliders Unlimited (TSU): it sits on top of the running game,
lets every click through, and shows information while you race. It works with TSU's
Fullscreen mode too.

Early version: for now the HUD shows a session clock. Fuel estimate, minimap and lap
times are planned.

## Install and first start

Nothing else needs to be installed: Python and Qt are inside the download. TurboKit is
not signed with a paid certificate yet, so Windows and macOS ask once whether to trust
it. After that it starts with a double-click.

**What to expect:** TurboKit opens no window and has no Dock or taskbar button. When it
runs, you see:
- the HUD at the top left of the screen ("TurboKit - session time" and a clock)
- a yellow **T** icon in the menu bar (Mac) or in the taskbar's notification area
  (Windows; it may be hidden behind the **^** arrow)

### macOS (Apple silicon)
1. Download `TurboKit-<version>-macos-arm64.zip` and double-click it in Downloads. You get
   `TurboKit.app`.
2. Drag `TurboKit.app` into **Applications**.
3. Double-click it. macOS says it "could not verify" TurboKit: click **Done** (not Move to
   Trash).
4. Open **System Settings > Privacy & Security** and scroll down to **Security**. Next to
   "TurboKit was blocked", click **Open Anyway**, enter your password, and click **Open
   Anyway** once more.
5. TurboKit starts: look for the HUD at the top left and the **T** in the menu bar. From
   now on, a double-click is enough.

### Windows
1. Download `TurboKit-<version>-windows-x64.zip`.
2. Right-click it, choose **Extract All**, and extract it, for example to your Desktop.
   Starting it from inside the ZIP without extracting does not work.
3. Open the extracted `TurboKit` folder and double-click `TurboKit.exe`.
4. If "Windows protected your PC" appears, click **More info**, then **Run anyway**.
5. TurboKit starts: look for the HUD at the top left and the **T** in the notification
   area.

### Linux
1. Download `TurboKit-<version>-linux-x64.tar.gz` and unpack it:
   `tar -xzf TurboKit-<version>-linux-x64.tar.gz`
2. Start it: `./TurboKit/TurboKit`
3. Linux has no shortcuts yet: use the **T** icon's menu for move mode. The overlay needs
   X11, or XWayland on a Wayland desktop.

### Trying a test build from a pull request
Before a release, every pull request that changes the app builds it for all three
systems. On the pull request page, open **Checks**, then **Build**, and download
**TurboKit-macOS**, **TurboKit-Windows** or **TurboKit-Linux** under **Artifacts**.
GitHub packs the download into one more ZIP: unpack it first, then follow the steps for
your system above with the file inside.

## Use

- The HUD starts at the top left, **locked**: clicks go through it to the game.
- **Ctrl+Shift+L** switches to **move mode**: the box gets a blue tint; drag it, resize
  it at the bottom-right corner, then press **Lock** (or Ctrl+Shift+L again). Clicking
  back into the game also locks it.
- **Ctrl+Shift+Q** quits.
- The **T** icon in the taskbar tray or menu bar has the same: **Move mode** and
  **Quit**. On Linux the shortcuts are not available yet; use the icon.

The position, size and look are saved in `settings.json`, with a log of the last run in
`turbokit.log`:
- Windows: `%APPDATA%\TurboKit`
- macOS: `~/Library/Application Support/TurboKit`
- Linux: `~/.config/TurboKit`

In `settings.json`, `theme` sets the text colour, accent colour, outline colour
(`#rrggbb` or `#rrggbbaa`) and `scale` (0.5 to 3). Change it while TurboKit is closed.

## Run from the source

For development, or to try a change without building. Needs Python 3.10 or later and a
copy of this repository. The start script sets up Qt (PySide6) in `.buildtools/venv` on
the first run, which takes a minute; later starts are quick.
- macOS, Linux: in a terminal, in the repository folder: `sh run_turbokit.sh`
- Windows: in a command prompt, in the repository folder: `run_turbokit.cmd`

The terminal shows TurboKit's log while it runs; Ctrl+C there quits it.

Tests: `python3 -B -m unittest discover -s tests` (Windows: `py -3 -B -m unittest
discover -s tests`). Builds: `python tools/build_app.py --smoke` with the packages in
`requirements-build.txt`; GitHub Actions builds all three systems
(`.github/workflows/build.yml`).
