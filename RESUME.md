# TurboHUD: where things stand

Kept short: the state now and what to do next. Every change, with how it was checked, is in
`docs/CHANGELOG.md`; open work in `docs/BACKLOG.md`; how it works in `docs/HOW_IT_WORKS.md`.

## Current state (2026-11-18)
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
  and yellow flags, penalties, the race leader banner, the battle warning (while watching), radar,
  track map, clock.
- **Layout**: tight boxes, groups that move and size together, Centre, Undo and Redo, text sizes per
  section, a grid, five named presets (Ctrl+Shift+1 to 5) and a preset per kind of event, shipped
  layouts per screen size, Export and Import, the design screen, one's own fonts.
- **Builds**: `tools/build_app.py` (PyInstaller) on each system: a Windows ZIP and a Mac disk image with
  the Rust reader, and a Linux `.tar.gz` built in Ubuntu 22.04 (`sh tools/build_linux.sh <version>`).
  The repository is kept in step with a private GitHub repository.

## To try next (most recent first)
1. **The battle warning** (`feature/battle-warning`, the Race Director mode's first part): in a replay with
   close racing, and spectating online, "Battle for P<n> / Possible Overtake / name vs name" when a car
   closes within 1 s of the one ahead or sits within 0.4 s; never while driving. Does it come at the right
   moments, too often or too seldom? Where does it sit on your screen (below the Race leader banner)?
2. **Tire wear as TSU counts it** (`fix/tire-wear-per-compound`): in an event with tire wear, TurboHUD's Tires
   percent should match TSU's own (it was 97 against 95); the log says `tires: ... worn out at ...` once an
   event. Try a softer and a harder compound if the event has more.
3. **The race leader banner** (`fix/banner-fade-as-one`): it now fades in and out as one picture, its colours
   as when it is full (they looked off while fading, reported on 2026-11-18). Also: "New Race Leader"
   about 5 s after a pass that holds (none for one undone, none at the start), "Race Winner" with your flag picture as the winner crosses the line; online too;
   how it reads over TSU. In move mode, the panel's 🏁 switches between the two; the text is in the middle.
4. **The log's slow-frame lines**: at 10 reads a second only real hitches (150 ms and more).
5. **One tint per group on Windows**: tick it in Settings > Look, lock, look at a group over TSU; if
   right, on by default there.
6. **The place label in move mode** (`X  Y  width×height`): on the Mac and Hyprland; the designed
   size's numbers on the design screen; none after a preset, Undo or Redo.
7. **TurboHUD's own memory** in the log: on Linux, and in a long race on each system (does it grow?).
8. **One window on Linux** (backlog item 1c): the window count probe over TSU on Hyprland.
9. **The tester** (backlog item 0): his stutter times and a try at 10 reads a second.
10. **Not yet seen**: a Single Player event and Custom races on the Mac and Linux; a replay after a race
    in the same session; the delta bar turning red on a slow loss; the HUD coming at once when TSU's log
    newly says an event runs; yellow flags (thresholds `YELLOW_*` in `turbohud/core/race.py`); a broken
    track map mending after a clean lap; a purple sector turning green; a special event, King of the Hill
    or Sumo; a track without sector lines (3 even bars); joining as a driver after spectating.

Then the Race Director mode's next parts (backlog item 8): the watched driver's banner in a recording.

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
