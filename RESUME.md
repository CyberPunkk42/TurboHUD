# TurboHUD: where things stand

Kept short: the state now and what to do next. Every change, with how it was checked, is in
`docs/CHANGELOG.md`; open work in `docs/BACKLOG.md`; how it works in `docs/HOW_IT_WORKS.md`.

## Current state (2026-11-28)
- **The app** (`turbohud/`, Python with Qt): a see-through, click-through HUD over TSU with a locked
  mode and a move mode (Ctrl+Shift+L, or Ctrl+Shift+F12; quit Ctrl+Shift+Q), a tray icon, and a
  settings window. Start from the source with `run_turbohud.sh` / `run_turbohud.cmd`.
- **Live race data on all three systems**, offline, hotlapping, Custom races, hosting and as an online
  client or spectator, and replays:
  - Linux: through the memory probe that Steam starts with TSU (launch option, README).
  - macOS (TSU in CrossOver): the Rust reader (`reader/`) inside the bottle, with no setup; races
    confirmed by the user on 2026-11-08. Locked, every section is drawn in one window per screen.
  - Windows: the same Rust reader beside TSU (since 2026-11-11); a window per section; the overlay shows
    over TSU's Fullscreen without Exclusive (2026-11-16).
- **Sections**: lap and time left, running lap, delta and delta bar, last and best lap with sector
  bars, fuel, fuel to finish, tires, health, car status (those four in one box), slipstream, speed with
  pedals, Nearby cars, Standings, blue and yellow flags, penalties, the race leader banner, the battle
  warning (while watching), the watched driver (while watching), radar, track map, clock (a compass is built, hidden for now: backlog
  item 13). In the lists DNF (retired), DSQ (disqualified), both TSU's own flags, and AFK (idle a minute);
  the time left counts from lights out.
- **Layout**: tight boxes, groups that move and size together (Ungroup all), Centre, Undo and Redo, text
  sizes per section, a grid, five named presets (Ctrl+Shift+1 to 5) and a preset per kind of event (one
  loaded by hand kept for the session), shipped layouts per screen size and five starting presets (all the
  user's own designs), Export and Import, the design screen, one's own fonts (a global one, and per section
  and per preset), move mode's panel in General and Text tabs, the preset in use shown in the panel and the
  layouts window.
- **Colours**: colour-blind friendly colours (Okabe-Ito) for every section or those chosen, never the flags;
  TSU's Legacy colours for the car sections' bars; the settings window in tabs Look, Colours, Sections, Race.
- **Latest (2026-11-20 and 21, Windows)**: Ungroup all; Car status; the car sections' text size kept with many
  laps; colour-blind friendly and Legacy colours; the settings window in tabs; the preset in use in the layouts
  window. All seen working in races by the user (2026-11-28).
- **Latest (2026-11-24, Mac)**: Add font... and Fonts folder... in the move-mode panel's Text tab too; with
  `TurboHUD.app` in Applications, `customization/` (layouts, fonts) is in the settings folder, no longer in
  `/Applications` (an old one moved at start). Both seen working (2026-11-28).
- **Latest (2026-11-25, Linux)**: race reads through the page cache, as on the Mac and Windows (one request for the
  pages instead of one a field); a window's placing commands in one `hyprctl --batch` call, so a preset load no
  longer freezes the HUD. The race reads seen working (2026-11-28); the preset load not yet (To try next).
- **Latest (2026-11-28)**: Quit TurboHUD when TSU quits, an option in Settings > Race (off by default); seen
  working by the user.
- **Builds**: `tools/build_app.py` (PyInstaller) on each system: a Windows ZIP and a Mac disk image with
  the Rust reader, and a Linux `.tar.gz` built in Ubuntu 22.04 (`sh tools/build_linux.sh <version>`).
  The repository is kept in step with a private GitHub repository.

## To try next (most recent first)
Details of each: its entry in `docs/CHANGELOG.md`. Checks on the Mac and Windows, and rare cases not yet seen:
backlog item 14.
1. **Sections whole on Hyprland**: start TurboHUD with ordinary windows on the screen (no game), and again over TSU;
   every section shows whole, in move mode and locked (was only a corner of each).
2. **A preset load on Hyprland**: Ctrl+Shift+1 to 5 in a race, the HUD should no longer freeze (was 1.2-1.4 s, the
   log's `slow frame` lines after `preset N loaded`); `Hyprland: no batches` in the log means it went one by one.
3. **TurboHUD's memory** (backlog item 10): a session started as `TURBOHUD_TRACE_MEMORY=1 sh run_turbohud.sh`;
   the `memory grew:` lines say where Python's slow rise is. Windows levels off (2026-11-28); the Mac in a long race.

Seen working in races by the user (2026-11-28): font buttons, radar zoom, steady standings, the preset in use
in the layouts window, the colours, Car status, Ungroup all, a preset kept for the session, Race Director mode
(battle warning, watched driver), presets loading by themselves, a font per section and preset, banners, tire wear;
then tick boxes on Linux, Quit TurboHUD when TSU quits, the settings window's buttons on Linux, race reads on
Linux with many cars, the customization folder in the built Mac app.

## Working notes
- Tests: `.buildtools/venv/bin/python -B -m unittest discover -s tests` (macOS, Linux; Windows:
  `.buildtools\venv\Scripts\python.exe -B -m unittest discover -s tests`; not `py -3`, which has no
  PySide6), best while TurboHUD is closed. The Rust reader's:
  `eval "$(sh tools/get_rust.sh --env)"`, then `cargo test --offline` in `reader/` (Windows:
  `cargo +1.99.1 test --offline --target x86_64-pc-windows-gnullvm`).
- Lint and format: `.buildtools/ruff-venv/bin/ruff check .` and `ruff format --check .`.
- After a change to `turbohud/app.py`: start TurboHUD for 6 s (`sh run_turbohud.sh --seconds 6`) and
  look for tracebacks; unit tests do not go through the app's own wiring.
- The log (`turbohud.log` in the settings folder) is replaced at each start: ask the user to send it
  before TurboHUD is started again.
- `releases/` is local to each machine (gitignored).
- If the HUD lags: `experiments/README.md`, "How the slow reads were found".
