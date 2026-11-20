# TurboHUD: where things stand

Kept short: the state now and what to do next. Every change, with how it was checked, is in
`docs/CHANGELOG.md`; open work in `docs/BACKLOG.md`; how it works in `docs/HOW_IT_WORKS.md`.

## Current state (2026-11-20)
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
  and yellow flags, penalties, the race leader banner, the battle warning (while watching), the
  watched driver (while watching), radar, track map, clock.
- **Layout**: tight boxes, groups that move and size together, Centre, Undo and Redo, text sizes per
  section, a grid, five named presets (Ctrl+Shift+1 to 5) and a preset per kind of event, shipped
  layouts per screen size and five starting presets (all the user's own designs), Export and Import, the design screen, one's own fonts
  (a global one, and per section and per preset), move mode's panel in General and Text tabs.
- **Builds**: `tools/build_app.py` (PyInstaller) on each system: a Windows ZIP and a Mac disk image with
  the Rust reader, and a Linux `.tar.gz` built in Ubuntu 22.04 (`sh tools/build_linux.sh <version>`).
  The repository is kept in step with a private GitHub repository.

## To try next (most recent first)
1. **The panel's General and Text tabs** (`feature/panel-text-tab`): in move mode, switch tabs: the rows
   stay put, a Show tick changes in both, the 🏁 is in Text. How the tabs look over TSU on each system.
2. **A font per section and per preset** (`feature/fonts-per-preset-and-section`): in move mode, give two or
   three sections their own **Font** in the panel and change **Global font**: only the sections on global
   change, each box fits its font. Save presets in different fonts and load them (also Ctrl+Shift+1 to 5 and
   by kind of event): each brings back its fonts; Undo goes back over a font change. In a race with two or three
   fonts, the log's `HUD frames` drawing share should stay about as before (each font keeps its own texts, in
   the same limits). The Linux and Mac panels: is the Font column (96 px, opening wider) wide enough?
3. **The Race preset at start** (`fix/race-preset-at-start`): with a Race preset chosen in Layouts > Load by
   itself, TurboHUD should start in it (log: `started in preset N, the one for a race`), and load it again as
   a race begins after a recording. If a race still keeps another layout, send the log before restarting.
4. **The preset in use in move mode** (`feature/current-preset-shown`): the panel's line above its buttons
   should say "Preset: 3 Race" after loading or saving 3, "(changed)" after a drag, and the name again after
   Undo; "Preset: none" with no preset matching. Does a desktop that puts a window a few pixels off (Hyprland,
   the Mac) show "(changed)" right after a load?
5. **A preset for spectating** (`feature/watching-presets`): in Layouts > Load by itself, pick one preset for
   Recording and another for Spectating (e.g. 1 and 5). Open a replay: the first loads; spectate an online
   race: the second; join it as a driver: the Race one. The log says `a spectating began: preset N`.
6. **No "New Race Leader" for your own car** (`fix/no-leader-banner-for-self`): take the lead in a race you
   drive and hold it: no banner. Another driver taking it still shows one, and your own win "Race Winner".
7. **The watched driver's banner while spectating** (`feature/spectator-camera-driver`, the Race Director
   mode's third part): spectate an online race and switch between drivers. The log's `spectating: the camera
   follows player N` should change at each switch, and the banner name the driver as in a replay. If it says
   `not read (...)` or stays on one player, send the log: TSU's spectator camera is then somewhere else.
8. **The watched driver's banner** (`feature/watched-driver-banner`, the Race Director mode's second part): in a
   replay, switch between drivers. "Watching / P<n> name" should come 1 s after the camera stops on a driver,
   take the place of one showing at once, and name nobody while you flick through. Is it too much with the battle warning? The log says `replay:
   the camera follows player N` at each switch.
9. **A replay found sooner** (`fix/replay-found-sooner`): on the Mac, open a replay with TurboHUD running; the
   log's `search: replay found, after N s` should say about 5 s, not 12 to 15, and the HUD come sooner. The
   reader in `.buildtools` is rebuilt on the Mac and the Windows PC (2026-11-20); a reader not rebuilt makes
   the log say `the reader searches for one value at a time`, and it works as before.
10. **The battle warning** (`feature/battle-warning`, the Race Director mode's first part): in a replay with
   close racing, and spectating online, "Battle for P<n> / Possible Overtake / name vs name" when a car
   closes within 1 s of the one ahead or sits within 0.4 s, or "Group around name" for 3 cars or more each
   within 1 s; none in the opening lap; never while driving. Right moments now, with lap 1 left out? Do
   the groups read well, and is the names row large enough with long names? Placed well (confirmed).
11. **Tire wear as TSU counts it** (`fix/tire-wear-per-compound`): in an event with tire wear, TurboHUD's Tires
   percent should match TSU's own (it was 97 against 95); the log says `tires: ... worn out at ...` once an
   event. Try a softer and a harder compound if the event has more.
12. **The race leader banner** (`fix/banner-fade-as-one`): it now fades in and out as one picture, its colours
   as when it is full (they looked off while fading, reported on 2026-11-18). Also: "New Race Leader"
   about 5 s after a pass that holds (none for one undone, none at the start), "Race Winner" with your
   flag picture as the winner crosses the line; online too; how it reads over TSU. In move mode, the panel's 🏁 switches between the two; the text is in the middle.
13. **The log's slow-frame lines**: at 10 reads a second only real hitches (150 ms and more).
14. **One tint per group on Windows**: tick it in Settings > Look, lock, look at a group over TSU; if
   right, on by default there.
15. **The place label in move mode** (`X  Y  width×height`): on the Mac and Hyprland; the designed
   size's numbers on the design screen; none after a preset, Undo or Redo.
16. **TurboHUD's own memory** in the log: on Linux, and in a long race on each system (does it grow?).
17. **One window on Linux** (backlog item 1c): the window count probe over TSU on Hyprland.
18. **The tester** (backlog item 0): his stutter times and a try at 10 reads a second.
19. **Not yet seen**: a Single Player event and Custom races on the Mac and Linux; a replay after a race
    in the same session; the delta bar turning red on a slow loss; the HUD coming at once when TSU's log
    newly says an event runs; yellow flags (thresholds `YELLOW_*` in `turbohud/core/race.py`); a broken
    track map mending after a clean lap; a purple sector turning green; a special event, King of the Hill
    or Sumo; a track without sector lines (3 even bars); joining as a driver after spectating.

The Race Director mode (backlog item 8) has all its planned parts: what is left is tuning from what you see.

## Working notes
- Tests: `.buildtools/venv/bin/python -B -m unittest discover -s tests` (macOS, Linux; Windows:
  `.buildtools\venv\Scripts\python.exe -B -m unittest discover -s tests`; not `py -3`, which has no
  PySide6), only while TurboHUD is closed. The Rust reader's:
  `eval "$(sh tools/get_rust.sh --env)"`, then `cargo test --offline` in `reader/` (Windows:
  `cargo +1.99.1 test --offline --target x86_64-pc-windows-gnullvm`).
- Lint and format: `.buildtools/ruff-venv/bin/ruff check .` and `ruff format --check .`.
- After a change to `turbohud/app.py`: start TurboHUD for 6 s (`sh run_turbohud.sh --seconds 6`) and
  look for tracebacks; unit tests do not go through the app's own wiring.
- The log (`turbohud.log` in the settings folder) is replaced at each start: ask the user to send it
  before TurboHUD is started again.
- `releases/` is local to each machine (gitignored).
- If the HUD lags: `experiments/README.md`, "How the slow reads were found".
