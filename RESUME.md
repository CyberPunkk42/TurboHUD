# TurboHUD: where things stand

Kept short: the state now and what to do next. Every change, with how it was checked, is in
`docs/CHANGELOG.md`; open work in `docs/BACKLOG.md`; how it works in `docs/HOW_IT_WORKS.md`.

## Current state (2026-11-21)
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
  window. None of these is seen over TSU yet (To try next).
- **Builds**: `tools/build_app.py` (PyInstaller) on each system: a Windows ZIP and a Mac disk image with
  the Rust reader, and a Linux `.tar.gz` built in Ubuntu 22.04 (`sh tools/build_linux.sh <version>`).
  The repository is kept in step with a private GitHub repository.

## To try next (most recent first)
Details of each: its entry in `docs/CHANGELOG.md`. Checks on the Mac and Windows, and rare cases not yet seen:
backlog item 14.
1. **Radar zoom**: zoomed in on a car right beside you, about 3.5 car lengths ahead and behind (was 2.5).
2. **Standings steady**: in an online race with many cars, no gap below zero and the Gap and Best columns never
   jumping out for a moment (a tester's video, 2026-11-21: a time not yet written read as 0).
3. **The preset in use in the layouts window**: under Presets, the same line as the panel's (Preset: 3 Race,
   (changed), Preset: none), changing as you load, save and drag.
4. **Colours** (2026-11-21): Settings > Colours: colour-blind friendly colours for All sections, then Chosen; are
   the colours told apart over TSU? TSU Legacy colours: the car sections' bars as dark as in TSU's HUD?
5. **Car status**: tick it in move mode (untick the four it stands for): Health, Tires, Fuel, Finish in one
   box with a bar under each of the first three, only the rows the event has, the tint ending below the last. The four separate ones at one
   text size look the same too, also with ~100 laps of tires (shown whole from 100 on).
6. **Ungroup all**: in move mode, the button at the end of the group row ungroups every section; Undo brings
   the groups back.
7. **A preset by hand kept for the session**: load 5 by hand in a race; later races start in 5, hotlapping
   keeps its own; 5 s in TSU's menu ends the session (log: `preset 5 for every race this session`, `the session
   is over`).
8. **TurboHUD's memory** (backlog item 10): a session started as `TURBOHUD_TRACE_MEMORY=1 sh run_turbohud.sh`;
   the `memory grew:` lines say where Python's slow rise is.
9. **Watching (Race Director mode)**: in a replay and spectating online, the battle warning's moments and
   groups, and the watched driver's banner at each camera switch (log: `the camera follows player N`).
10. **Presets**: the panel's "Preset: 3 Race" right after a load on Hyprland (or "(changed)"?); the Recording
   and Spectating presets loading by themselves.
11. **A font per section and per preset**: their own fonts kept by presets and Undo; is the panel's Font column
   wide enough on Linux?
12. **Banners**: none for your own car taking the lead; "Race Winner" with your flag picture at the finish.
13. **Tire wear**: TurboHUD's Tires percent the same as TSU's (log: `tires: ... worn out at ...`).

The Race Director mode (backlog item 8) has all its planned parts: what is left is tuning from what you see.

## Working notes
- Tests: `.buildtools/venv/bin/python -B -m unittest discover -s tests` (macOS, Linux; Windows:
  `.buildtools\venv\Scripts\python.exe -B -m unittest discover -s tests`; not `py -3`, which has no
  PySide6), best while TurboHUD is closed. On the Linux PC two fail before any change, as on `main`:
  `test_a_warning_on_top_too` (a Mac-only raise) and `test_each_font_has_its_own_measures_the_same_each_time`
  (two fonts 0.97 px apart there). The Rust reader's:
  `eval "$(sh tools/get_rust.sh --env)"`, then `cargo test --offline` in `reader/` (Windows:
  `cargo +1.99.1 test --offline --target x86_64-pc-windows-gnullvm`).
- Lint and format: `.buildtools/ruff-venv/bin/ruff check .` and `ruff format --check .`.
- After a change to `turbohud/app.py`: start TurboHUD for 6 s (`sh run_turbohud.sh --seconds 6`) and
  look for tracebacks; unit tests do not go through the app's own wiring.
- The log (`turbohud.log` in the settings folder) is replaced at each start: ask the user to send it
  before TurboHUD is started again.
- `releases/` is local to each machine (gitignored).
- If the HUD lags: `experiments/README.md`, "How the slow reads were found".
