# TurboHUD: where things stand

Kept short: the state now and what to do next. Every change, with how it was checked, is in
`docs/CHANGELOG.md`; open work in `docs/BACKLOG.md`; how it works in `docs/HOW_IT_WORKS.md`.

## Current state (2026-11-17)
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
  bars, fuel, fuel to finish, tires, health, slipstream, speed with pedals, Nearby cars, Standings, blue
  and yellow flags, penalties, the race leader banner, radar, track map, clock.
- **Layout**: tight boxes, groups that move and size together, Centre, Undo and Redo, text sizes per
  section, a grid, five named presets (Ctrl+Shift+1 to 5) and a preset per kind of event, shipped
  layouts per screen size, Export and Import, the design screen, one's own fonts.
- **Builds**: `tools/build_app.py` (PyInstaller) on each system: a Windows ZIP and a Mac disk image with
  the Rust reader, and a Linux `.tar.gz` built in Ubuntu 22.04 (`sh tools/build_linux.sh <version>`).
  The repository is kept in step with a private GitHub repository.

## To try next (most recent first)
1. **Move mode's pointer on Windows** (`fix/move-mode-pointer-windows`, reported by players): in a race,
   Ctrl+Shift+L should show the pointer at once, without ESC, and locking hand TSU the mouse back (the
   log: `move mode: panel in front`). On Hyprland: does the pointer show in move mode mid-race?
2. **One's own fonts**: Settings > **Add font...** in move mode: the file window shows above the sections,
   the chosen .ttf or .otf is used at once and every box fits; System font goes back. **Fonts folder...**
   closes the settings, ends move mode and the folder shows.
3. **The radar** at the cars' real size, zoomed in when they are close: is the zoom steady, are the cars
   large enough?
4. **The race leader banner**: "New Race Leader" about 5 s after a pass that holds (none for one undone,
   none at the start), "Race Winner" as the winner crosses the line; online too; how it reads over TSU.
5. **The log's slow-frame lines**: at 10 reads a second only real hitches (150 ms and more).
6. **One tint per group on Windows**: tick it in Settings > Look, lock, look at a group over TSU; if
   right, on by default there.
7. **The place label in move mode** (`X  Y  width×height`): on the Mac and Hyprland; the designed
   size's numbers on the design screen; none after a preset, Undo or Redo.
8. **TurboHUD's own memory** in the log: on Linux, and in a long race on each system (does it grow?).
9. **One window on Linux** (backlog item 1c): the window count probe over TSU on Hyprland.
10. **The tester** (backlog item 0): his stutter times and a try at 10 reads a second.
11. **Not yet seen**: a Single Player event and Custom races on the Mac and Linux; a replay after a race
    in the same session; the delta bar turning red on a slow loss; the HUD coming at once when TSU's log
    newly says an event runs; yellow flags (thresholds `YELLOW_*` in `turbohud/core/race.py`); a broken
    track map mending after a clean lap; a purple sector turning green; a special event, King of the Hill
    or Sumo; a track without sector lines (3 even bars); joining as a driver after spectating.

Then the Race Director mode (backlog item 8), starting with the battle warning, when the user says go.

## Working notes
- Tests: `.buildtools/venv/bin/python -B -m unittest discover -s tests` (macOS, Linux; Windows:
  `py -3 -B -m unittest discover -s tests`), only while TurboHUD is closed. The Rust reader's:
  `eval "$(sh tools/get_rust.sh --env)"`, then `cargo test --offline` in `reader/` (Windows:
  `cargo +1.99.1 test --offline --target x86_64-pc-windows-gnullvm`).
- Lint and format: `.buildtools/ruff-venv/bin/ruff check .` and `ruff format --check .`.
- After a change to `turbohud/app.py`: start TurboHUD for 6 s (`sh run_turbohud.sh --seconds 6`) and
  look for tracebacks; unit tests do not go through the app's own wiring.
- The log (`turbohud.log` in the settings folder) is replaced at each start: ask the user to send it
  before TurboHUD is started again.
- `releases/` is local to each machine (gitignored).
- If the HUD lags: `experiments/README.md`, "How the slow reads were found".
