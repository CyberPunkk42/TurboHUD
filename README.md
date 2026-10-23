# TurboKit

A HUD overlay for Turbo Sliders Unlimited (TSU): it sits on top of the running game,
lets every click through, and shows information while you race. It works with TSU's
Fullscreen mode too.

Early version: for now the HUD shows a session clock. Fuel estimate, minimap and lap
times are planned.

## Install

Download the archive for your system from the release page and unpack it. Nothing else
needs to be installed.

- **Windows:** unpack `TurboKit-<version>-windows-x64.zip` and start
  `TurboKit\TurboKit.exe`. Windows may warn about an unknown app the first time: choose
  **More info**, then **Run anyway**.
- **macOS (Apple silicon):** unpack `TurboKit-<version>-macos-arm64.zip` and move
  `TurboKit.app` to Applications. The first start is blocked because the app is not
  signed: open **System Settings > Privacy & Security** and choose **Open Anyway**.
  TurboKit has no Dock icon; it shows a **T** in the menu bar.
- **Linux:** unpack `TurboKit-<version>-linux-x64.tar.gz` and start `TurboKit/TurboKit`.
  The overlay needs X11, or XWayland on a Wayland desktop.

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

Needs Python 3.10 or later. The start script sets up Qt (PySide6) in `.buildtools/venv`
on the first run:
- macOS, Linux: `sh run_turbokit.sh`
- Windows: `run_turbokit.cmd`

Tests: `python3 -B -m unittest discover -s tests` (Windows: `py -3 -B -m unittest
discover -s tests`). Builds: `python tools/build_app.py --smoke` with the packages in
`requirements-build.txt`; GitHub Actions builds all three systems
(`.github/workflows/build.yml`).
