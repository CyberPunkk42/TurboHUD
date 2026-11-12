# TurboHUD: where things stand

## Current state
- Stack (`docs/STACK.md`): Python with Qt (PySide6), shipped as a bundled app for
  Windows, macOS and Linux, with small ctypes parts for what Qt lacks (Mac window level
  above Fullscreen, global shortcuts).
- App skeleton in `turbohud/` (see `README.md` and the structure in `docs/STACK.md`): the
  overlay with locked and move mode, Ctrl+Shift+L / Ctrl+Shift+Q, a tray icon (the TSU
  TurboHUD image in `assets/`), saved placement and theme, tested by hand on the Mac.
  On Linux, with TSU started through the memory probe (README: "Live lap times on
  Linux"), the HUD shows the live race in movable sections: lap and time left, running
  lap, delta to the best lap, last and best lap, fuel, fuel to finish, tires, health,
  draft, speed with pedal bars, the player list (flags, PIT with its timers, live gaps), the lap times
  list (lap number, best and running lap of every driver, PIT with its timers), blue flag,
  proximity radar, track map and local time. It works offline, in hotlaps, hosting online and as
  an online client (guest, or hosting with only AI). How it works and what it does to
  RAM and the game: `docs/HOW_IT_WORKS.md`. On macOS, with TSU in CrossOver, the same HUD
  reads the race through a reader in the bottle (`turbohud/tsu/bottle.py`), with no setup; since
  2026-11-10 that reader is a Windows program in Rust (`reader/`), the Python one kept as a fallback;
  the race tests (offline with 19 AI, Fullscreen, hosting online, spectating) were confirmed
  by the user on 2026-11-08. While locked, on the Mac, all sections are drawn in one window
  per screen (2026-11-09), for the frames; seen over TSU on 2026-11-10, with no gain showing yet. On Windows it
  reads the race through the Rust reader started beside TSU (first run on 2026-11-11: an online race found once a hang in the search was fixed). Start from the source with
  `run_turbohud.sh` / `run_turbohud.cmd`.
- Layout, in the move-mode panel: a text section's box fits closely round its text, three
  presets (Ctrl+Shift+1, 2, 3 load them; Linux: `--preset`), groups that move and resize
  together and can match their text size and width, Centre buttons for every section, and
  Centre text, and Undo. Checked by hand on the Mac.
- Builds: `tools/build_app.py` (PyInstaller) makes a Windows ZIP and a Mac disk image (each with the
  Rust reader; the Mac one 32.5 MB, no Windows Python since 2026-11-11) and a Linux `.tar.gz`, run locally on each system.
  The repository is kept in step with a private GitHub repository (since 2026-11-11; remote
  `github` on the Mac, `origin` on the Windows PC), so the Windows PC can pull it; `.github/workflows/build.yml` runs only for a
  release tag, a pull request or by hand.
- The overlay probe (`experiments/overlay_probe.py`, see `experiments/README.md`) answered
  whether a see-through, click-through, always-on-top window can sit over TSU:
  - macOS (CrossOver): yes when TSU runs windowed or with Fullscreen off; never with TSU's
    Fullscreen setting on.
  - macOS (native, `experiments/mac_overlay_probe.py`): yes, also over TSU's Fullscreen.
    A plain Mac window at the screen-saver level, outside the bottle, needing no
    permission. So TurboHUD's Mac overlay must be native, while reading the game's files
    and the HUD logic can be shared.
  - Windows: not tested yet.
  - Qt, the chosen stack (`experiments/qt_overlay_probe.py`): works over TSU on the Mac
    in Fullscreen, with and without Exclusive: crisp text, click-through, shortcuts,
    move mode, no stutter.
- Overlay behaviour settled by the probe: a move mode (tinted, draggable, resizable, with
  Lock and Close buttons) and a locked mode (background hidden, click-through, only the
  content shows). Ctrl+Shift+L toggles, Ctrl+Shift+Q quits; no Alt, which Mac keyboards
  lack. Position and size are remembered. Move mode ends by itself when the game becomes
  active again.
- Tests: `/opt/homebrew/bin/python3.13 -B -m unittest discover -s tests` (Windows:
  `py -3 -B -m unittest discover -s tests`). The Rust reader's: `eval "$(sh tools/get_rust.sh --env)"`,
  then `cargo test --offline` in `reader/` (Windows: `cargo +1.99.1 test --offline --target x86_64-pc-windows-gnullvm`);
  `sh tools/get_rust.sh` builds it (Mac, and Windows in Git Bash since 2026-11-12).
- Lint and format: `.buildtools/ruff-venv/bin/ruff check .` and `ruff format --check .`
  (Linux; a separate tools environment, never part of the app). Both pass.

## Next steps
**Start with `docs/CONTINUE_HERE.md`**: what is left to test. Then `docs/IMPROVEMENT_BACKLOG.md`. In short:
- First (where the session of 2026-11-10 stopped): the one-window HUD works on the Mac but showed no gain
  in FPS; compare it with a window each in the same race (`docs/CONTINUE_HERE.md`, "Next session"). Build
  2026.11.10 went to the tester with new instructions (the same comparison, and the Rust reader). Race reads merge pages further apart since 2026-11-10 (31
  to 49 reads of the game a read and 16 to 22 ms, from 84 to 88 and 26 to 29 ms). Online, the search from the last race found
  three races in a row in 0.4 s (2026-11-10).
1. Windows: the overlay over TSU (windowed, Fullscreen, Fullscreen Exclusive), and the live data
   through the Rust reader (built 2026-11-11, not yet run there).
   Also a trial of all of TurboHUD inside the CrossOver bottle (backlog item 1b,
   `docs/WINDOWS_AND_CROSSOVER.md`): first the Qt probe in the bottle.
2. macOS: live data is connected; check it in races (offline and online), over
   Fullscreen, and listen for stutter while the race is searched for.
3. Layout: checked by hand on the Mac; what is left is in races, on Linux and on Windows
   (backlog item 3).
4. Builds and release: bundled apps with the probe, an AppImage; before the repository
   goes public, the privacy check, a licence and a README for players.
5. Linux: try TurboHUD on KDE or GNOME (it runs through XWayland there now).

## Recent changes
- 2026-11-12: Car classes in colour, asked for by the user: a registry of the classes a clan tag can name
  (`turbohud/core/class_registry.py`): the 115 codes the user listed in 8 categories, each with its colour (Prototype
  purple, GT blue, Formula red ...), and the 11 codes from before that list lacks, in the closest category; matched
  without brackets and in any case (`[GrT]`, `grt`). In a multi-class race the lap times keep their grouping, and
  each class's line and the tag column (empty there before) show the class in its colour: the driver's own tag, or
  paler the class their car gives them; a driver of no class keeps their clan tag, plain. Two classes of one
  category (GT3 and GT4): the one first in the registry keeps the colour, the other takes the next category's free
  colour (`class_colors`, the user's choice). The radar keeps its own class colours. A settings file saved with the
  old 28-code list reads the registry; the list is saved only when it is the user's own. Also, asked for by the
  user: a class sheet (`turbohud/overlay/class_sheet.py`), opened by Car classes... in the settings window, lists
  every code and name in its category's colour. Tests (the user's cases A to I). Seen offscreen with Windows'
  fonts; not yet in a race.
- 2026-11-12: AGENTS.md names the GitHub remote by its address, asked for by the user: the Windows PC's clone came
  from GitHub, so its GitHub remote is `origin`, where AGENTS.md said `github` and that `origin` is the old bundle
  (true only on the Mac). Agents now check `git remote -v` and push only to the GitHub address.
- 2026-11-12: `releases/` is ignored as a whole, asked for by the user: the built archives and their checksums
  were ignored by name, but an unpacked build there showed up as untracked. Nothing in it was tracked.
- 2026-11-12: Windows build 2026.11.12.3 to share, asked for by the user: `releases/TurboHUD-2026.11.12.3-windows-x64.zip`
  (42.1 MB), as 2026.11.12.2 with this morning's fixes from GitHub, chiefly the flags found where Steam is installed
  outside Program Files. The zip's reader is the one built from `main` (unchanged since .2, checked byte for byte).
  Smoke test passed with TurboHUD closed; the zip and the Python modules packed in `TurboHUD.exe` checked for the
  privacy terms, none. It replaces 2026.11.12.2; both older builds are still in `releases/`, to be removed by hand.
- 2026-11-12: Windows finds TSU's flags where Steam is installed outside Program Files. A tester
  on Windows 10 saw the country codes (DE) instead of flags: TurboHUD looked for Steam only under
  Program Files. It now reads Steam's folder from the registry first (`SteamPath`, then the
  installer's `InstallPath`), then Program Files, each listed once. Where TSU is still not found,
  the log's `flags:` line names the Steam libraries searched. Tests; not yet run on Windows.
- 2026-11-12: Fixed: running the tests while TurboHUD runs switched it to move mode
  (it happened mid-race on 2026-11-03). One test, run only without Qt, calls the app's
  start, which first asks a running TurboHUD over the real command socket and then
  sends it "move". The test now answers that question itself (none running). The fix
  was made on Linux on 2026-11-04 and lost in the move to GitHub; brought back.
- 2026-11-12: The move-mode panel is the same size on Linux as on the Mac: its text is held at
  13 px (`PANEL_FONT_PX`) where the system's is larger. Linux desktops use about 15 px (Adwaita
  Sans 11 pt) and give buttons and lists that font on their own, so the panel was 866 px tall
  and failed its under-800 test; now 771 px. Set in the panel's style sheet, which reaches those
  widgets; Windows' smaller text is unchanged. A test copies Linux's fonts on every system.
- 2026-11-12: Windows build 2026.11.12.2 to share, asked for by the user: `releases/TurboHUD-2026.11.12.2-windows-x64.zip`
  (42.1 MB), as 2026.11.12 with the race search reading with 4 threads (the zip's reader is the one built from
  `main` by `tools/get_rust.sh`, checked byte for byte). Smoke test passed with TurboHUD closed (started as
  2026.11.12.2, quit cleanly); the zip checked for the privacy terms, none. It replaces 2026.11.12, still in
  `releases/`, to be removed by hand.
- 2026-11-12: A faster race search on Windows, asked for by the user (could Rust do better?): measured on the user's
  PC, a whole search of TSU's 4.3 GB took 18.8 s through the Rust reader, and as long in Python, as the time is
  Windows copying another program's memory (`ReadProcessMemory`), not the scan (comparing words as numbers changed
  nothing). That copying runs in parallel: 1 thread 19.9 s, 2 10.4 s, 4 5.7 s, 8 3.4 s. So outside Wine the reader
  reads 16 pieces in a step with 4 threads (`SEARCH_BATCH`, `SEARCH_THREADS` in `reader/src/memory.rs`;
  `Process::read_many`, threaded in `WindowsProcess`), in the same order, stopping at the first good hit as before.
  Seen against the user's TSU: 5.75 s a whole search, from 18.86 s, the same 42 hits. In Wine (the Mac) nothing
  changes: one piece at a time, paced. `tools/get_rust.sh` now also sets up Rust and llvm-mingw on Windows (Git
  Bash; llvm-mingw's Windows zip pinned by GitHub's SHA256), the same Rust 1.99.1 and target as on the Mac. Rust
  tests (40, one reading the test's own memory with 4 threads). Not yet seen: whether TSU stutters during the 6 s.
- 2026-11-12: The first Windows build to share, asked for by the user: `releases/TurboHUD-2026.11.12-windows-x64.zip`
  (42.1 MB, with the Rust reader and texture2ddecoder; built on the Windows PC with PyInstaller 6.22.2 in
  `.buildtools/win-build-venv`), from `main` with the Windows race search fix, the race recorder and the surface
  rule. Smoke test passed with TurboHUD closed (the app started as 2026.11.12 and quit cleanly); every file in the
  zip, the packed Python modules too, checked for the privacy terms: none. Not signed: Windows SmartScreen asks once
  (More info, Run anyway).
- 2026-11-11: Off the track by the surface's layer, reported by the user: the wide plastic kerbs of a circuit raised
  yellow flags. Their grip is 0.9 (stored as 0.8999), just under the 0.9 limit, and TurboHUD took all four wheels
  under it as off the track. Read with the user driving over every surface (TSU's Unity layers from its
  globalgamemanagers: 13 Asphalt, 15 Dirt, 16 Pit, 17 Curb, 18 Terrain, 22 Concrete, 24 Plastic ...): the grass was
  Terrain (0.5), the plastic kerbs and concrete run-off are driven as track. Each surface's layer is now read with its
  grip (`PlayerState.wheel_layers`), and only Terrain counts as off (`OFF_TRACK_LAYERS`, asked for by the user:
  concrete may be a track's own surface;
  `trackmap.off_the_track`), for the yellow flags, the hazard warning (a car stopped on plastic stands on the road)
  and the track map's clean laps; Dirt counts as track (rallycross). Where a layer is not read, the grip rule as
  before. Also a new incident, asked for by the user: wrecked, a car that lost all its hit points (damage on;
  `PlayerState.wrecked`), at once and first. Slow, spun, stopped (on or off the track), wrong way and respawned
  stay as they were. Tests. Not yet seen in a race.
- 2026-11-11: The race recorder on Windows, and each event's mode, asked for by the user to gather data from the
  special events (Sumo, King of the Hill, Capture the flag ...): `experiments/tsu_race_recorder.py` reads TSU straight
  on Windows (`%APPDATA%\TurboHUD\recordings`), writes each event's type, and twice a second the changed fields of
  the event's state, controller, logic and settings and of the mode objects they lead to, also while the race cannot
  be read. Tried on the user's PC in an online Battle event (`TS.BattleEventMode`, level 6): capture time, capturing
  player and team, players alive and rounds are there (`experiments/README.md`). The file is saved every 5 s, as a
  recorder stopped from outside left an empty file (a race event, 22:34 to 22:35). Tests. Built on
  `fix/windows-race-search`, which it needs on Windows.
- 2026-11-11: The online race search never ended on Windows, found on the user's first Windows run (TSU's own build
  on Windows, the Rust reader beside it): with a race running, the search stopped at a stale pointer to the
  controller's class, and its event state led to memory whose "parents" went round in a circle, so reading its fields
  never ended. TurboHUD hung in that search (4 minutes and on) and showed only the clock. A class's fields and parents
  are now bounded (`FIELDS_MOST`, `PARENTS_MOST` in `turbohud/core/il2cpp.py`): memory past them is not a class, and
  the search goes on to the next hit. Checked against the user's race: the search then found the race (9 players,
  the user driving) after about 24 s. Without a race, the 6 hits were such stale pointers too ("no race"). Tests (they
  hang without the fix). Also seen: Ctrl+Shift+L was taken by AMD Adrenalin (error 1409) until the user unbound it
  there; TSU's Windows log names sessions, not events, so TurboHUD searches without it. 9 tests fail on Windows on
  `main` already (Unix sockets, symlinks, fonts), none touched here.
- 2026-11-11: Build 2026.11.11.9 for the tester (`releases/`, macOS 27, `--any-macos`, smoke test passed with
  TurboHUD closed; 32.4 MB), asked for by the user: the same app as 2026.11.11.8 (only docs changed since), under a
  new number. The test sheet names it. The 2026.11.11.8 image is still in `releases/`.
- 2026-11-11: A private GitHub repository for the Mac and the Windows PC, asked for by the user (remote `github`,
  `https://github.com/CyberPunkk42/TurboHUD.git`). Before the first push every file, path and commit of the history was
  checked for personal data: the files had only placeholders, but 299 commits had the user's real name as author
  (Git took it from the Mac account, as no Git name was set) and 115 a personal email. The history was rewritten so
  every author and committer is CyberPunkk42 with the GitHub noreply email (files, messages and dates the same,
  checked commit by commit; a backup of the old history outside the project). This clone's `user.name` is now set,
  the hook's local terms list the real name, the email and the Mac's computer names, and AGENTS.md says what may be
  pushed where.
- 2026-11-11: Build 2026.11.11.8 for the tester (`releases/`, macOS 27, `--any-macos`, smoke test passed with
  TurboHUD closed; 32.4 MB), as 2026.11.11.7 with the own yellow flag and ring, the smaller own dot, the yellow sector
  following a car backwards, the radar's zoom cap with edge arrows, classes on the radar and clan tags in the lap
  times. The test sheet names it, says what's new and checks them (Part 4 points 10 to 13, Part 6). The 2026.11.11.4
  to .7 images are still in `releases/`, to be removed by hand.
- 2026-11-11: Clan tags in the lap times, asked for by the user: outside a multi-class race (where the tags name the
  classes), each driver's clan tag shows in a column of its own after the name, lined up on the left, cut to 5
  characters (`MAX_TAG_SHOWN`); a driver without one shows nothing there. A new column in the layout (`Row.tag`,
  `tag_left`), and an option, Clan tags in the lap times, in the menu and Settings (on by default, `clan_tags`). The
  box keeps its size: with tags the text gets a little smaller where it would not fit. Tests; drawn off screen;
  TurboHUD started from source for 6 s, no error. Not yet seen in a race.
- 2026-11-11: Classes on the proximity radar, asked for by the user: in a multi-class race (classes from the clan
  tags, as in the lap times; off with them), a car of another class than the player's is filled in its class's colour
  (`RADAR_CLASS_COLORS`: blue, green, purple, pink, given out by the class's name so each keeps it all race; none the
  radar already uses), with the red (beside) or yellow (closing in) as a thick outline. The player's own class and
  Other look as before. Merged with the radar's zoom cap: a car of another class past the edge is an arrow in its
  class's colour. Tests; drawn off screen; TurboHUD started from source for 6 s, no error. Not yet seen in a race.
- 2026-11-11: The proximity radar no longer zooms out to fit a far car, reported by the user (players found the
  cars too small): it zoomed out with speed and the warning time (at 3 s, about 190 units each way, cars a few pixels).
  It now shows at most `RADAR_VIEW_MAX` (24 units, six car lengths; 38 before at racing speed with the default 0.5 s),
  so on a 200 px radar a car is about 8 by 23 px, a third larger. A car that counts beyond that is an arrow at the top
  or bottom edge in its usual colour, fainter the further off it is (`radar_reach` for what counts). Tests; drawn off
  screen. Not yet seen in a race.
- 2026-11-11: A yellow flag's sector follows the car on the road, reported by the user: a car driving backwards kept
  the yellow sector it turned round in, on the map and in the box, as the sector came from the last checkpoint it
  crossed, and a car going backwards crosses none. Once the track is learnt, the sector now comes from where the car
  is on the learnt road (`TrackMap.gate_at`, from the point the wrong-way check already follows each car to, read by
  read, so a track that crosses itself keeps it on its own stretch); before that, as before. Tests; TurboHUD started
  from source for 6 s, no error. Not yet seen in a race.
- 2026-11-11: Your own dot on the track map, asked for by the user: ringed in yellow when you caused a yellow
  flag (an outline, so a car under you still shows; the entry before this one said the map ringed it, which it did
  not until now), and a little smaller than the other cars (0.9 of them, from 1.15), so over one, your white ring
  shows inside that car's dot. It was already drawn last, on top. Tests; drawn off screen. Not yet seen in a race.
- 2026-11-11: The yellow flag also shows for the driver who caused it, asked for by the user: the local car's
  incidents (off track, slow, stopped, spun, wrong way, respawned) count like everyone else's, so its own HUD shows
  the box with its name, the map rings it and turns its sector yellow. Not in the pits, as for every car. The
  hazard warning (CAR STOPPED AHEAD, WRONG WAY AHEAD) leaves the local car out. Tests. Not yet seen in a race.
- 2026-11-11: The blue and yellow flags in one spot are combined, not stacked, reported by the user: stacked,
  they covered twice as much of the track. While both are out and their boxes overlap, the yellow box, where
  and as large as it is, gets a blue frame (the blue flag's colour and fade; wide at the sides, in the margin, thin at the
  top and bottom so it never covers the text; `_paint_blue_frame`) and the blue bar is not drawn (`flagstack.combined`). Nothing is moved any more: the
  stacking (`FlagStack`) is gone. Placed apart, each shows in its own spot. Tests; drawn off screen.
- 2026-11-11: Build 2026.11.11.7 for the tester (`releases/`, macOS 27, `--any-macos`, 32.4 MB), as 2026.11.11.6
  with JUMP START shown while TSU flags it, then 1.5 s. Built without `--smoke`, as the user's TurboHUD was running
  (the smoke test would only have switched that one to move mode): to start once with TurboHUD closed. The test
  sheet names it. The 2026.11.11.4 to .6 images are still in `releases/`, to be removed by hand.
- 2026-11-11: JUMP START shows while TSU's false-start flag is on, then 1.5 s (`JUMP_START_SHOWN`, from 5 s), asked
  for by the user: the flag is on while the throttle is held on the red lights, and as they go out (TSU holds the
  car). The test sheet (build 2026.11.11.6 has the 5 s) and README say so. Test.
- 2026-11-11: Build 2026.11.11.6 for the tester (`releases/`, macOS 27, `--any-macos`, smoke test passed with
  TurboHUD closed: the Rust reader read the user's race, no error; 32.4 MB), as 2026.11.11.5 with JUMP START. The
  test sheet names it, the box is Penalties in move mode, and Part 4 asks for a false start. The 2026.11.11.4
  and .5 images are still in `releases/`, to be removed by hand.
- 2026-11-11: JUMP START, asked for by the user: TSU's false-start penalty (`VehicleState.startPenaltyOn`, seen
  for half a second on the user's car at a start in a recording) shows in the orange penalty box, renamed
  Penalties, for 5 s from when it was last seen (`JUMP_START_SHOWN`), and as an orange JUMP in the lap times
  for any driver TSU flags. A shortcut countdown goes first, though none comes at a start. Tests; the per-frame
  code run against the user's live race (the flag read for 20 cars, no error). Not yet seen with a false start.
- 2026-11-11: Build 2026.11.11.5 for the tester (`releases/`, macOS 27, `--any-macos`, smoke test passed: the Rust
  reader read the user's race, no error; the app holds the reader and texture2ddecoder, no Windows Python;
  32.4 MB). Everything since 2026.11.11.4. `TurboHUD-test-instructions.md` for it: what's new, Part 4 looks at
  TSU's flags, the yellow sector on the map and the steady box, CAR STOPPED AHEAD and the Shortcut penalty box,
  Part 6 at classes (if the host asks), Part 3 may be skipped if done with 2026.11.11.4; the help for the old
  Python reader is gone (the app has none). The 2026.11.11.4 image is still in `releases/`, to be removed by hand.
- 2026-11-11: TurboHUD failed at every frame with the shortcut penalty merged, reported by the user (an
  AttributeError, hundreds of times in the terminal): the app called its ShortcutPenalties `shortcuts`, a name
  the same function gives later to whether the hotkeys are registered (True), which replaced it. Renamed
  `shortcut_penalties`. Checked by starting TurboHUD from the source with a race running: no error, and it
  quit at `--seconds` as it should (it could not before, as every frame failed). The tests had not caught it:
  none goes through the app's own call of race_sections.
- 2026-11-11: Shortcut penalties, asked for by the user: TSU slows a car that takes a shortcut its track
  defines ("Shortcut detected!"). Found in a race recorded with cuts (only reading): a car is slowed while
  `CarStateUpdater.m_shortuctMaxSpeedWithoutLimitedGas` (TSU's spelling) is a speed cap (about 28) instead
  of no limit, for every car (the AI's too); the length is `EventState.shortcutSlowdownUpdater.m_slowdownTicks`
  (150 there) at 50 ticks a second (measured). A new section, Shortcut penalty (orange box, dark text:
  SHORTCUT 2.4 s, counting down from when it began; `ShortcutPenalties`, `shortcut_rows`), and CUT 2.4s in
  orange in the lap times in place of the lap. The move-mode panel's spacing is a little tighter to keep it
  under 800 px with the new row (788 off screen). Also seen: `VehicleState.startPenaltyOn` for a false start.
  Tests; read from the user's race (3.0 s, a slowed AI car seen). Not yet seen in the HUD; online as a client
  not yet checked.
- 2026-11-11: Hazard ahead, asked for by the user in place of an automatic full course yellow (which a car
  left by a player who quit, lost the connection or a gamepad would set off for everyone): the yellow box's
  heading becomes CAR STOPPED AHEAD or WRONG WAY AHEAD, with that car first, while a stopped car on the
  tarmac (a wheel on tarmac or kerb grip; parked on the grass it is ignored) or one going the wrong way is
  up to 5 s ahead on the road at the player's speed (`YellowFlags.hazard`, `HAZARD_*`; the distance along the
  learnt road, `TrackMap.road_ahead`). It stays at least 2 s, so it never blinks. Only the player's own HUD;
  off with Yellow flags. No new reads of the game. Tests; not yet seen in a race.
- 2026-11-11: The blue and yellow flags stack when both are out in the same spot, asked for by the user:
  `turbohud/core/flagstack.py` keeps the flag that came first at its own place and puts the second right
  next to it (blue below the yellow box, yellow above the blue flag; the other side at a screen edge). A
  flag on the screen never moves; one moved away goes back once it has gone, unseen. Only while locked;
  move mode and saving use each flag's own place. The yellow flag system itself was confirmed in a race by
  the user the same day (heading centred, steady box, the sector yellow on the map). Tests for the rules;
  not yet seen in a race with both flags out.
- 2026-11-11: The screenshot shortcut removed, asked for by the user: it saved nothing on the user's Mac
  (macOS's tool, started from TurboHUD, gave no file). Ctrl+Shift+S, the menu's two items, `--screenshot`,
  `screenshot_folder` and `turbohud/screenshot.py` are gone; Ctrl+Shift+S is TSU's again. A settings file
  that still names `screenshot_folder` loads as before (the key is ignored, and gone at the next save). For screenshots: macOS's
  Cmd+Shift+3 or 4.
- 2026-11-11: The yellow flag's heading (YELLOW - Sector N) in the middle of its box, asked for by the user;
  the drivers' lines stay on the left. A row can be centred on its own (`Row.centred`), whatever the rest of
  the section does. Test; drawn off screen.
- 2026-11-11: A sector under a yellow flag turns yellow on the track map, asked for by the user: each
  sector with an incident (any kind) has its stretch of the learnt road drawn yellow over the usual road, all
  round the track (`yellow_sector_spans` in race.py, `TrackMap.yellow_stretches`). The sectors are the
  track's sector lines as for the sector bars; where the road crosses each checkpoint line is worked out once
  per track (`gate_marks`: nearest to the line, not its middle, which can lie far off the road). Only once a
  whole lap is learnt; off with Yellow flags. Tests; drawn off screen. Not yet seen in a race.
- 2026-11-11: The yellow flag's box keeps its size, reported by the user: it was drawn only as large as its
  text, so it grew and shrank with each incident listed. A section with a background of its own now fills
  its whole window with it (`_paint_backdrop`), the size given in move mode; the text keeps its size in it,
  as it is worked out from the section's sample rows. Test (one incident and three: the same box and text size).
- 2026-11-11: Screenshots that were not saved, reported by the user: Ctrl+Shift+S started macOS's
  `screencapture` twice, but no file came, and the tool's errors were thrown away. Most likely the Screen
  Recording permission: now TurboHUD asks macOS first (`CGPreflightScreenCaptureAccess`; when not allowed,
  `CGRequestScreenCaptureAccess` and a tray message saying where to allow it), and waits for the tool aside,
  logging `screenshot saved: <path>` or `screenshot not saved (<the tool's words>)`. Started from the source,
  the permission belongs to the terminal app. Tests.
- 2026-11-11: A screenshot shortcut, Ctrl+Shift+S, asked for by the user: Steam's F12 did nothing, as Steam's
  overlay never shows in TSU's bottle with D3DMetal (its log: no frame from Steam's UI; screenshots last
  worked on 20 October). Ctrl+Shift+S is free: TSU's bindings know only Ctrl as a modifier (its editor saves
  with Ctrl+S; S is player 2's brake and Backwards in menus, without modifiers), and macOS and Windows use
  it for nothing. `turbohud/screenshot.py` saves the screen most shown sections are on to Pictures/TurboHUD
  (`screenshot_folder` in the settings), named by the time: macOS's `screencapture -D`, with its camera sound
  (Screen Recording asked for once); Linux `grim`, else Qt; Windows Qt. Also in the icon's menu (Take a
  screenshot, Open the screenshots folder) and `run_turbohud.sh --screenshot`. Tests. Not yet tried by hand.
- 2026-11-11: The Mac app without the Windows Python, asked for by the user: the Rust reader ran in online races
  on the tester's Mac (builds from 2026.11.11 use it only: had it failed, no HUD would have shown). The app ships
  only `turbohud-reader.exe`; with it missing the start says so, with no Python in its place. The Python reader
  stays for a start from the source with `TURBOHUD_PY_READER=1` and a Windows Python set up by hand, and as
  Windows' fallback. `run_turbohud.sh` builds the reader on the Mac where it is missing. Also: a build stops
  when a package of requirements.txt is not installed (`missing_requirements`): the build environment lacked
  texture2ddecoder, so the app would have had no game flags; without it they stay emoji. The disk image: 32.5 MB
  from 44.7 MB. Tests; built (not started) and its contents checked.
- 2026-11-11: Live race data on Windows, asked for by the user, with the Rust reader: on Windows the reader
  (`reader/`, already a Windows program that finds TSU.exe and knows when it runs under Wine) is started
  straight beside TSU by `LocalReader` (`turbohud/tsu/bottle.py`), no CrossOver or bottle, with no console
  window; while TSU does not run it is tried again every 2 s. Windows cannot wait on a pipe with select, so
  there a thread takes the reader's answers (`Pipe(threaded=...)`); starting a reader moved to
  `spawn_reader`. Where the reader is missing, TurboHUD reads TSU itself in Python (`winmemory.connect`). The
  Windows build ships the reader where it is built. Tests; the threaded way checked against the user's race
  on the Mac through the bottle (20 players, 9 ms a read). Not yet run on Windows.
- 2026-11-11: Clan tags and car names are read again every 5 s (`LABEL_REFRESH`), reported by the user: with
  the AI's clan tag forced and their own changed in a race against AI, the lap times did not split, as
  TurboHUD had read every tag once, before the change, and kept it for good (a fresh reader saw LMP and
  GT3). A car's object may also come back as another car in a later race. Kept 5 s, a race read still
  seldom asks the game for them. Test.
- 2026-11-11: In a multi-class race, a driver without a class tag takes the class of their car, asked for by
  the user: each car's name is read once per car (`TS.Vehicle.m_vehicleModel.m_properties.name`, found in a
  race against AI the same day: 'Ligier JS320 P3 v2'; every car has a model object of its own, so the name
  is what tells cars apart). `car_classes` gives an untagged driver (or one with a tag that is no class) the
  class most tagged drivers in the same car have in this race, the first seen on a tie; the tag always goes
  first; a car no tagged driver drives stays Other; no tags, no classes. No list of TSU's cars needed. Tests;
  read through the real reader in the user's race (20 cars, the names and the tag; 13 ms a race read).
- 2026-11-11: Multi-class lap times, asked for by the user (as in real multi-class racing): each driver's
  clan tag is read (`TS.PlayerProfile.teamTag`, found in a race the same day: 'FTR' for [FTR]; read once per
  profile, so a race read asks no more of the game). With two or more classes among the tags in
  `class_tags` (settings; a default list of LMP, GT3, GT4 ...), the lap times come by class (`car_classes`,
  `by_class`): the class whose leader is furthest ahead first, untagged drivers last as Other, numbered and
  with the fastest lap purple within each class, and each class below a thin line labelled with its name,
  drawn in the gap above its first row (`Row.rule`, `draw_rule`), so the box keeps its size and all 20
  drivers. **Classes in the lap times** in the menu and Settings (on by default). The Settings window takes
  no typing (an overlay without focus), so other tags go in the settings file. Tests; drawn off screen. Not
  yet seen in a race with class tags.
- 2026-11-11: TSU's own flags in the player list and lap times, asked for by the user (the emoji flags
  depend on the system, and Windows shows none): `turbohud/tsu/gameflags.py` finds TSU's `_Data` folder
  (Steam's libraries; on the Mac inside the CrossOver bottles), reads the 221 flag textures by TS.Flag's
  names from `resources.assets` and `sharedassets0.assets` (only reading; a reader of its own for Unity
  2021.3's files without type trees, another version is left alone) and unpacks the crunched DXT with
  `texture2ddecoder` (MIT, new in `requirements.txt`, 0.2 MB; UnityPy would have added about 27 MB). They are
  kept 48 px high as PNGs in TurboHUD's folder (`flags/`, 0.9 MB) with the game files' sizes and times, and
  read again only after they change; at start in a background thread, 0.6 s on the user's Mac. Drawn in a
  box 0.7 x 1.2 font sizes, centred and level with the text, with a thin edge; emoji or code where none.
  The game's flags are never part of TurboHUD. Also found in a race (only reading): the clan tag is
  `TS.PlayerProfile.teamTag` ('FTR', without brackets). Tests with a fake game file; read from the real
  game on the Mac and drawn off screen. Not yet seen in the app, on Linux or on Windows.
- 2026-11-11: A track is learnt from three clean laps, asked for by the user: a shortcut on the tarmac or kerbs
  is a clean lap, so a first lap through one was learnt. The first clean lap still shows at once; once
  `LEARN_LAPS` (3) are in, laps under `SHORT_LAP` (98.5 %) of the longest are left out (a shortcut saves
  distance), and of the rest the one whose line runs nearest the others is kept (`choose_lap`, `lap_gap`, at
  about 100 points a lap) and saved with `laps`. One lap a car while there are three or more cars, so one
  driver who cuts every lap is outvoted; alone or with one other car, more laps of the same car count. A track
  saved from a single lap still shows and is learnt again this way. Tests. Not yet seen in a race.
- 2026-11-11: The yellow flag says **wrong way** for a car driving against the race, asked for by the user (a
  "ghost driver"): moving faster than 8 units a second with at least half its speed against the way the race
  goes there, for 1.5 s (`YELLOW_WRONG_WAY`, `_FOR`). Its velocity counts, not where it points, so a car that
  faces back but slides on is not; a short spin still shows as spun first. The way the race goes is the
  learnt track map's line, which runs in the driving direction (`TrackMap.heading`, searching near the car's
  last point): the checkpoint lines would be wrong in hairpins. So it needs the track learnt; until then no
  car is shown going the wrong way. Ranked after stopped, before spun. Tests. Not yet seen in a race.
- 2026-11-11: A track map learnt wrong can be relearnt, asked for by the user: **Relearn this track's map** in
  the TurboHUD icon's menu and **Relearn map** in the move-mode panel (beside Undo; both only with a track map,
  and enabled only while a track is known) forget the current track's map and its saved file
  (`TrackMap.relearn`); the map then grows again and the next whole clean lap any car drives is learnt and
  saved. Other tracks' maps stay. The panel is 47 px wider for the button (490 x 792 px off screen), no taller.
  Tests. Not yet seen in the app or a race.
- 2026-11-11: Build 2026.11.11.4 for the tester (`releases/`, macOS 27, `--any-macos`, smoke test passed: the
  Rust reader read the user's race), as 2026.11.11.3 with the yellow flag as a yellow box with dark text. The
  test sheet names the build and describes the yellow box. It replaces 2026.11.11.3 in `releases/`.
- 2026-11-11: The yellow flag is a yellow box with dark text, asked for by the user: sections can have a solid
  background of their own (`hud.Section.background`, drawn where the Tint would be, also in move mode, and
  taking the Tint's place in the panel); the yellow flag's is `race.YELLOW_COLOR` with `YELLOW_TEXT`
  (#111111) text, drawn without the dark outline, which smudged the letters on the yellow. Tests, and a look
  at it drawn off the screen.
- 2026-11-11: Build 2026.11.11.3 for the tester (`releases/`, macOS 27, built with `--any-macos`, smoke test
  passed with TSU closed), with everything since 2026.11.11.2: yellow flags (and their option), the gliding
  delta bar, purple sectors turning green, the track map from clean laps, the tidier move-mode panel with All
  and None. `TurboHUD-test-instructions.md` for it: the power adapter, Low Power Mode and refresh rate noted
  in Part 1; All and None in the measurements; Part 4 looks at the panel, the delta bar and a yellow flag
  against AI; Part 6 asks about yellow flags online. It replaces 2026.11.11.2 in `releases/`.
- 2026-11-11: The move-mode panel's word buttons fit their words, reported by the user: with fixed widths
  macOS cut "None" to "lon" and "Delete" to "elete" (the off-screen render, with Qt's own style, had not
  shown it). All, None, Save, Load and Delete are now at least 54 px and as wide as the system needs
  (`PANEL_WORD_BUTTON`), with 3 px between the preset rows, whose buttons touched. Checked with the macOS
  style drawn off the screen: 400 x 914 points. A test that each word button is as wide as it needs (it
  fails with the old widths).
- 2026-11-11: The yellow flag is always a plain YELLOW, asked for by the user: no DOUBLE YELLOW for a stopped
  car (its line still says "stopped"). Tests.
- 2026-11-11: The move-mode panel tidied, asked for by the user: **All** and **None** beside the Show heading
  show or hide every section at once, one step for Undo (`MovePanel.all_wanted`, the app's `set_all_wanted`);
  the sections come under Timing, Car, Race and Other (`hud.panel_categories`); the column headings sit over
  their boxes, and a faint dot marks an option a section does not have; the presets are a small table with
  Save, Load and Delete (a word, where a bin icon was). 393 x 786 px, from 568 x 667 (still under the 800 px
  the panel is held to). Tests; the panel rendered off screen, not yet seen on the Mac's screen.
- 2026-11-11: Yellow flags can be turned off, asked for by the user: **Yellow flags** in the TurboHUD icon's
  menu and under Settings… (on by default, kept in the settings as `yellow_flags`). Off, there is no Yellow
  flag section and no yellow ring on the track map, and the cars are not followed (turned on again, it starts
  afresh). Tests for the setting and the fresh start. Not seen in the app yet: an off-screen start of the
  app crashes on the Mac with or without the change (its native window code), so a check by hand is left.
- 2026-11-11: The track map is learnt only from a clean lap, reported by the user: a first lap with a trip
  over the grass was learnt as the track and saved, so the map kept the detour in every later race there. A
  car's path now starts afresh while it has all four wheels off the tarmac (grip under 0.9; kerbs and a wheel
  in the air still count), nearly stands or goes backwards (`trackmap.driving_clean`), as after a respawn. A
  learnt track is saved with `clean`; one saved before still shows, and is learnt again and replaced from the
  next clean lap, so the tracks already saved mend themselves. Tests.
- 2026-11-11: The delta bar's fill glides, asked for by the user: it eases towards the delta in about 0.2 s
  instead of jumping to each read's value (`DELTA_FILL_EASE`, 0.08 s); the number stays exact, and a steady
  change is followed under 0.1 s behind. A new lap puts the fill where the delta is at once. It still moves
  20 times a second, as the HUD is drawn: smoother would take more redraws, which cost frames. Tests.
- 2026-11-11: Yellow flags, asked for by the user (as in F1, DTM or GT racing): a new section, Yellow flag,
  and a yellow ring on the track map. For every other car TurboHUD now reads its speed along the car
  (`m_forwardSpeed`), the grip of the surface under each wheel (`TS.WheelUpdater.m_surfaceMaterial*`, each
  material's grip read once) and its respawn count (`VehicleState.spawnCount`): all there online too
  (`experiments/README.md`). `YellowFlags` makes incidents of them once they hold: stopped (under 1 unit a
  second for 2 s, a double yellow), spun (backwards), respawned (3 s), off the track (all four wheels on
  grip under 0.9 for 0.5 s; kerbs are 0.93, a wheel in the air 0) and slow (under 8 for 1 s); not in the
  pits, finished, or before the first checkpoint. Each lasts 3 s past the car being back to normal. The
  section lists those in the player's sector and the next (`yellow_rows`), up to three, with the sector.
  Tests; not seen in a race yet, and the thresholds are first guesses to tune from races.
- 2026-11-11: Recorded online as a client with `experiments/tsu_race_recorder.py` (a session hosted by
  someone else, one other human driver): the client has the other car's four wheel surfaces, its speed
  and how much it slides, live. So yellow flags can tell off the track (all four wheels off the tarmac),
  slow or stopped, and spun for every car online too (`experiments/README.md`).
- 2026-11-11: `experiments/tsu_race_recorder.py`, for yellow flags, asked for by the user: records every car
  of a race through the reader in the bottle (only reading) to a file outside the repository. A first look:
  each car's four wheel surfaces (`TS.WheelUpdater.m_surfaceMaterial*`, each a `TS.TSMaterialProperties`
  with grip, braking, dust ...) are there for the other car too, offline, so all four wheels off the tarmac
  can be told for every car there. Online as a client is still to record (`experiments/README.md`).
- 2026-11-11: A purple sector turns green once someone else in the race goes faster in it, asked for by the
  user: it kept the colour it had when set, so the user and another driver both showed a purple first sector.
  Now only the fastest has it, as with the best lap (a time as fast counts for whoever set it first); green
  stays for a personal best, dark yellow for slower. Tests.
- 2026-11-11: Build 2026.11.11.2 for the tester (`releases/`, macOS 27, built with `--any-macos`, smoke test
  passed with TSU closed), with the three fixes of the night for races joined online: no race log to go by,
  a race found where the last one was, and the quick look near the last race. `TurboHUD-test-instructions.md`
  for it: Part 6 now asks for at least three races in one session and how many seconds each took to show,
  and the log to copy includes `quick look`. It replaces 2026.11.11 in `releases/`.
- 2026-11-11: A quick look for the next online race where the last one was, asked for by the user: on the
  tester's Mac, whose TSU writes no race log, a race showed about 10 s after its start (up to about 20 s: a
  search with no race takes 8 to 10 s there, then 10 s wait; up to a minute after a long lobby). Now, between
  searches, while there is no race and TSU's log does not say none runs, TurboHUD searches only 256 MiB
  from just below the last race (`winmemory.NEAR_SPAN`, `near`; one race lay 209.5 MiB above the last),
  every 2 s from the end of the last look (`QUICK_LOOK_EVERY`), and logs `quick look: race found ...`. Not
  before a first race was found, nor while a race is watched. The readers are unchanged: the Mac side hands
  them the shorter list of regions. Tests. Not seen in a race yet: it only comes into play where TSU's log
  says nothing, so on the tester's Mac (a new build).
- 2026-11-11: A race TSU puts where the last one was is read afresh. In a session the user hosted, the
  tester's HUD showed in the first two events with build 2026.11.11 but not in the third: the search found
  the race (`race found (-0.0 MiB from the last one)`), yet no `event type` or `TSU: racing` followed until
  the event was restarted two minutes later. The new race's event state was at the last one's address, so
  the reader took it for the same race and read it with what it kept of the last one (the local player,
  laps), and every read failed. Now a search that finds a race, or a race that is gone, forgets all that.
  The live race also logs when the reason there is no race changes (`TSU: still ...`, at most every 10 s):
  a race found but not read looked like waiting all along. Tests (both new reader tests fail without the
  fix). Not yet seen on the tester's Mac (needs a new build).
- 2026-11-11: Build 2026.11.11 for the tester (`releases/`, macOS 27, built with `--any-macos`, smoke test
  passed: the Rust reader read the user's race), with the fix for online races where TSU writes no race log
  and the new delta bar. `TurboHUD-test-instructions.md` for it: install into Applications (he ran the last
  build from the disk image), the same five FPS measurements, a quick look with the delta bar, a race joined
  online (the fix), the log (now with `TSU's log` and where TurboHUD runs from), and the quit check. It
  replaces 2026.11.10 in `releases/`.
- 2026-11-11: Online races on Macs whose TSU writes no race log, found with the tester in a session the user
  hosted: the tester saw only the clock in every race joined as a client (the user's sessions and the event
  server), in every build since 2026.11.09, and the log showed `TSU: waiting for race (m_activeServer is null)`
  with no search. His TSU had stopped writing its log on 8 Nov: the newest log held only "Log started." and
  "Log ended.", so TurboHUD took it that no event ran and never searched. Now a TSU log says something only
  when it was written since TSU started (the reader asks Windows for TSU's start, `GetProcessTimes`, with the
  read-only access it has) and names an event; else it is not known and the search goes ahead, in the Rust
  reader and the Python one. TurboHUD's log says what TSU's log says when that changes (`TSU's log: ...`).
  Checked in the bottle on the user's Mac: TSU's start matches macOS's to the second, the live log still
  counts, a log older than TSU's start does not. Not yet seen on the tester's Mac (needs a new build).
- 2026-11-11: The delta bar, asked for by the user: round ends (a pill; the fill rounds only at its outer
  end), and no white. White while steady showed more than the colours and hid the white delta on it. Now it
  is green while gaining and red while losing, keeps its colour while steady, and turns only once the delta
  has moved the other way by 0.05 s a second for 0.25 s, then fades over through yellow in about 0.4 s. A
  lap starts green when ahead and red when behind. The fill is a little darker than the text colours, so the
  delta reads on it. Checked off screen (a rendered preview); not yet seen in a race.
- 2026-11-10: Build 2026.11.10 for the tester (`releases/`, macOS 27, built with `--any-macos`, smoke test
  passed), with everything since 2026.11.09.2: the Rust reader (checked inside the built app: the same
  program, picked by the app, and started from there in the bottle), the merged race reads, the search from
  the last race, the kept map road and the sector bars by the track's sector lines; the Windows Python as
  fallback. `TurboHUD-test-instructions.md` rewritten for it: five FPS measurements in one race against AI
  (closed; one window with every section, then only the local time; a window each with the same two), a
  quick look, the log, and the quit check. It replaces 2026.11.09.2 in `releases/`.
- 2026-11-10: The Rust reader seen in a race against AI by the user (the log): a median race read of 8.7
  to 10.5 ms, where the Python reader took 16 to 22 ms, with as many reads of the game (48 to 56 a read).
  The time on the game's memory fell to 6.3 to 7 ms from 15 to 21 ms, so the Python reader, not Wine, made
  most of that cost.
- 2026-11-10: The reader in the CrossOver bottle in Rust, asked for by the user: `reader/`, a Windows
  program with no dependencies (its own small JSON, the Windows calls declared by hand), answering the
  same questions as `turbohud/tsu/bottle_reader.py` in the same way: the memory list, reads, pages read in
  few calls with the gaps that failed kept, the metadata, TSU's log, and the paced search from an address.
  `tools/get_rust.sh` puts pinned Rust 1.99.1 and llvm-mingw 20261020 into `.buildtools` (nothing in the
  shell profile, Homebrew or the system) and builds `turbohud-reader.exe`, 418 KB with only Windows' own
  DLLs, against 22 MB for the Windows Python. The Mac side starts it where it is there, the Python reader
  where it is not or with `TURBOHUD_PY_READER=1`; the log names which (`(the Rust reader)`). The Mac app
  ships both for now. Checked: 34 Rust tests and the Python ones, and both readers started in the bottle
  without TSU (the same answer, 1.1 to 1.2 s each, nearly all of it Wine's). Not yet run with TSU.
- 2026-11-10: The search for the next race begins 4 MiB below the last one, where it was 32 MiB, agreed
  with the user after the log of that day: three races in a row lay within 0.5 MiB of the one before, and
  the 0.4 s each search took was the 32 MiB read on the way (`SEARCH_BEFORE` in
  `turbohud/tsu/winmemory.py`). Expected: about 0.05 s. Not yet seen in a race.
- 2026-11-10: The search from the last race seen online by the user, as a driver in a public session (the
  log): three races in a row found after 0.4 s at the first hit, within 0.5 MiB of the last one (1.4 s
  before). A regular online race is `TS.RaceEventMode` (level type 0), as expected for the map. Online a
  read took a median of 11 to 15.5 ms in 27 to 38 reads of the game.
- 2026-11-10: The merged race reads seen in a race against AI by the user (the log): 69 to 89 pages a read,
  across 305 to 406 MiB, in 31 to 49 reads of the game (84 to 88 before), a median read of 16 to 22 ms (26
  to 29 before). The pages lie in groups far apart, so a larger gap would gain little
  (`docs/CONTINUE_HERE.md`, "Not yet seen in a race"). The one-window canvas was on (`canvas:` in the log).
- 2026-11-10: Race reads merge pages further apart, asked for by the user after the log of that day (1 trip
  a read, but 84 to 88 reads of the game in it, 26 to 29 ms): the reader now reads wanted pages up to 48
  pages (192 KiB) apart in one call of up to 2 MiB, where it was 16 pages and 256 KiB (`MERGE_GAP`,
  `SPAN_MOST` in `turbohud/tsu/winmemory.py`). By the costs measured before (about 250 µs a call, about
  0.8 GiB/s), reading up to about 200 KiB of unwanted memory is cheaper than a second call. A call that
  reaches memory that is not there fails as a whole: it is then cut in two at its widest gap, and so on,
  and a gap whose two sides could be read is kept by the reader and not read across again, so such a
  failure costs once, not at every read. Every 30 s the log has a `race pages` line (the pages of a read,
  the MiB they lie across, the reads of the game), to set the two values by. How many reads are left is not
  known: it depends on how TSU's objects lie. Not yet seen in a race.
- 2026-11-10: The user's check of `main` on the Mac, in a race against AI with the Metal HUD
  (`docs/CONTINUE_HERE.md`, "One-window HUD and reads on the user's Mac"). The one-window HUD looks and
  works as before (move mode, presets, "bigger"/"smaller"), but no gain showed: about 85 FPS with every
  section, in a race that ran 85 to 120 without TurboHUD, and one section cost as much as all (about 15 to
  20 FPS); to be compared with a window each in the same race. The map's kept road: 8.2 to 8.8% of a core
  with only the map shown (about 23%). Race reads: 1 trip a read, but still 26 to 29 ms, all of it in 84 to
  88 reads of the game. TSU quit normally. No online race, so the search from the last race is not seen yet.
- 2026-11-10: A search for the online race begins where the last race was, asked for by the user (Mac with
  CrossOver, and TurboHUD's own Windows reading): the search went through the game's data from the lowest
  address each time, with the race at 18% of it, 6 s in, in one search measured. It now begins 32 MiB below
  the place of the last race read or watched (`SEARCH_BEFORE` in `turbohud/tsu/winmemory.py`), goes up from
  there and comes round to it, so nothing is left out (`winmemory.search`'s `first`, `starting_at`; the
  reader's `search` takes `first`). The first search after TurboHUD or TSU starts is as before, and so is
  Linux, where the probe answers a whole search in about 1.5 s. The log says `searching for the online
  race, from where the last one was`, and at a race found how far it was from the last one (`+0.0 MiB from
  the last one`). That TSU puts a new race near the last one is expected, not measured: if it does not, a
  search takes as long as one of all the data up to that race. Not yet seen in a race.
- 2026-11-10: The sector bars show the track's sectors, reported by the user: they showed a bar for every
  checkpoint (68 on the track driven, up to about 120), where TSU tracks can have sector lines set by their
  maker. TSU keeps each checkpoint's kind in `TS.CheckpointProperties.type` (TS.CheckpointType, one byte:
  Sector 0, Normal 1, Minor 2, from the game's metadata), read with the checkpoint lines, once a race. A
  bar now starts at the start line and at each sector line: the track driven has sector lines at
  checkpoints 15, 28 and 38 (read live), so 4 sectors. A track without any is split into 3 even sectors, as
  in F1, asked for by the user. Seen by the user in an AI race: 4 bars there, fine as it is.
- 2026-11-09: The track map draws its road once and keeps it, asked for by the user: the square (with its
  tint), the road and the start line are drawn into an image, drawn again only when the track, the
  section's size, the tint or the road's colour changes; each frame then only copies it and draws the
  cars. Measured offscreen at Retina scale with the user's most detailed learnt track (1427 points):
  3.30 ms a frame before, 0.35 ms after. The map was the costliest section in TurboHUD's own CPU (23% of a
  core against 9 to 17); not yet measured in a race.
- 2026-11-09: Race reads on the Mac ask the reader in the bottle for all the pages the read before used in
  one question, asked for by the user: the game keeps its objects in place during a race, so a read needs
  nearly the same pages each time. Only pages new to a read still go one at a time. The reader reads pages
  at most 16 apart (64 KiB) in one call of up to 256 KiB, as a large read costs little more than a small
  one; where such a call fails, it reads those pages one by one (`winmemory.read_pages`, `PageCache.prefetch`,
  the reader's `read_pages`). Expected: 20 to 88 trips through the pipe become 1 to 3, and fewer calls to the
  Wine server, which TSU also uses; worked out, not measured. The log's `race reads` line now also says the
  reads of the game a read makes. A binary header in place of JSON (idea 5) was left out: with one or two
  trips a read it would save microseconds. The same fetch is used by TurboHUD's own Windows reading. Not yet
  seen in a race.
- 2026-11-09: `docs/WINDOWS_AND_CROSSOVER.md`, asked for by the user: what Windows still needs (live data
  is built in `winmemory.py` but not wired into the app there), and an analysis of running all of TurboHUD
  as a Windows app inside TSU's CrossOver bottle: what it gains (one app, fewer parts), what it costs (no
  overlay over TSU's Fullscreen, tested; the window count, the Wine server, soft text on Retina) and a plan
  to try it, cheapest first (backlog item 2b).
- 2026-11-09: Build 2026.11.09.2 for the tester, with the smaller move-mode panel; it replaces 2026.11.09
  (never sent), and the test instructions name it and the panel's "Show" column.
- 2026-11-09: The move-mode panel is smaller, asked for by the user: 568 x 642 px instead of 675 x 978. The
  five options for the whole HUD (mph, tint behind all sections, radar cones, other cars on the map,
  sector bars) moved to the settings window (they stay in the TurboHUD icon's menu); each section's row
  has a tick box with its name, a narrow group list, small ↔ and ↕ buttons and unlabelled tick boxes under
  "Mid text" and "Tint" headings; the presets are on one row, and the group-match buttons are A to D. Every
  control keeps its tooltip. Drawn offscreen; not yet seen on the Mac or Hyprland.
- 2026-11-09: Build 2026.11.09 for the tester (`releases/`, macOS 27, built with `--any-macos`), with the
  one-window HUD, the map's tint, the lap colours and the sector bars. `TurboHUD-test-instructions.md`
  rewritten, shorter: FPS without TurboHUD and with every section shown, a quick look (as before, sector
  bars, a section moved), the log, and the quit check (reader left, TSU freezing).
- 2026-11-09: The sector bars can be turned off, asked for by the user: "Sector bars below the last and best
  lap" in the TurboHUD icon's menu and the move-mode panel, on by default, saved as `sector_bars`. Off, the
  room below the times stays, so their text keeps its size (make the box shorter in move mode to taste).
- 2026-11-09: Sector bars below the last and best lap, asked for by the user: one bar per stretch between
  two checkpoints (TSU has no sectors of its own), all of equal width across the section, so a track with
  10 checkpoints has 10. As on F1's timing screens, a sector is purple when faster than anyone else had
  driven it by then and than the driver's own earlier laps, green when only faster than their own, dark
  yellow when slower than their best, and grey while still to come. They show the lap being driven, and
  for 6 s after the start line the lap just ended (until a sector of the new lap is done). The gaps get
  thinner with many sectors. The section's box grows by the bars' room once (`settings.json` goes to
  layout 5, `settings.before-layout-5.json` keeps the old file), so its text keeps its size. No more reads
  of the game (`race.sector_colours`). Not yet seen in a race.
- 2026-11-09: Purple for the race's fastest lap in the lap times list (it was green), and the track map's road
  takes a fast lap's colour, both asked for by the user: for 6 s of race clock after the driver ends a lap,
  purple for the race's fastest lap, green for a best of their own, then white again; a slower lap leaves
  it white (`race.lap_flash`). Not yet seen in a race.
- 2026-11-09: The last and best lap have colours, asked for by the user, as on F1's timing screens. The best
  lap is purple while nobody else in the race has gone faster (a time as fast belongs to whoever set it
  first), else green; alone it is always purple. The last lap takes the best's colour when it is the
  driver's best lap, else white (no better than the best before, also when as fast). At the finish the last
  lap keeps its colour. The other drivers' best laps come from their start-line passes, as in the lap
  times list (`race.lap_colours`). No more reads of the game. Not yet seen in a race.
- 2026-11-09: The track map has a Tint tick box in the move-mode panel, asked for by the user, like the text
  sections: it turns the map's dark square on or off (off leaves the road and the dots). It is on by default
  and for maps saved before (`settings.json` goes to layout 4 once, `settings.before-layout-4.json` keeps the
  file as it was), kept with the section and in presets, with Undo, and "Light tint behind all sections"
  includes it. Move mode shows the choice too. Not yet seen over TSU.
- 2026-11-09: While locked, on the Mac, every section is drawn in one see-through window per screen, asked
  for by the user: a probe with their layout gave 85 FPS with 17 windows and 115 with one window (120 with
  none). Move mode keeps a window per section, so dragging, groups and Undo are as before. A section asks the
  canvas to draw it again where it is and where it was; moves and resizes while locked do too.
  `TURBOHUD_ONE_WINDOW=0` turns it off; Linux and Windows keep a window each for now. Not yet seen over TSU.
- 2026-11-09: A probe for the overlay's FPS cost, `experiments/window_count_probe.py`: 17 small windows
  against one large window holding the same 17 boxes, in TurboHUD's own layout, phase by phase on its own.
  It tells whether rebuilding the overlay as one window would help. Seen running with real windows on the
  Mac; not yet measured over TSU.
- 2026-11-09: The Metal HUD on the user's Mac, in a race against AI: 120 FPS with TurboHUD closed and with
  only the local time shown, 80 to 110 with every section. So the number of windows costs frames. TSU then
  froze around being quit, with TurboHUD quit first and its reader ended at once (TSU at 1% CPU, Steam at
  100%): the second time such a freeze was seen; no way for the reader to cause it is known yet.
- 2026-11-09: Confirmed by the user: the move-mode panel and the settings window open wholly on the screen.
  A CPU recording per section (`docs/CONTINUE_HERE.md`, "Tester's Mac"): each window adds about the same to
  WindowServer, whatever it shows and however often it changes, so a window's being there costs, not its
  redraws. Next: the Metal HUD in frames, then perhaps all sections in one window.
- 2026-11-09: The move-mode panel stays on the screen, reported by the user: it went to the bottom left
  corner, mostly off the screen. It was put on the screen holding the first shown section's top-left
  corner; the running lap's was at x = -1, on no screen, so the panel went 40 px from it, below the screen.
  The screen is now the one holding the section's middle (else the main one), and the panel and the
  settings window keep to its usable area, clear of the menu bar and the Dock (`hud.panel_place`).
- 2026-11-08: Confirmed by the user in a race: the delta bar (right when ahead, hundredths, white fading to
  green or red) is better and smooth enough for now, and the settings window opens on the screen, near the
  upper middle.
- 2026-11-08: The delta is smoother, asked for by the user: shown in hundredths in the delta bar and the
  delta section (a third digit changed at every read; the player list's gaps keep thousandths), its colour
  looks at the last second rather than half, and eases towards a new colour over about half a second
  instead of jumping. The bar's length still follows the delta at once. Not yet seen in a race.
- 2026-11-08: The delta bar goes right when ahead of the best lap, as in sim racing, and its colour is
  gradual, asked for by the user: white while neither gaining nor losing, then more and more green or red
  as time is gained or lost, full at 0.15 s a second. It switched between green and red at 0.02 s a
  second, which flickered. Not yet seen in a race.
- 2026-11-08: The settings window opens wholly on the screen, reported by the user: it went 20 px to the right
  of where the move-mode panel was meant to be (near the middle), so a wide panel put it past the right edge,
  and it did not follow a panel that was dragged. It now opens beside the panel where it is, on the right
  if it fits, else on the left, kept on that screen (`hud.beside`). Not yet seen on the Mac.
- 2026-11-08: Confirmed by the user on the Mac: the bin button, an offline race with 19 AI (every section,
  20 drivers in the lists, preset shortcuts mid-race), the same race in Fullscreen, and hosting about 13 AI
  online as a driver. The race reads stayed at about 30 ms in these races.
- 2026-11-08: The track map shows only on a track, asked for by the user: in races and special events
  (TS.RaceEventMode), not in arena modes (Battle, Collector, Hill, Soccer, Sumo, Tag), where no track is
  learnt either. TSU keeps the mode in `TS.EventSettings.m_eventMode`, an object whose class names it
  (seen in a capture event: `TS.BattleEventMode`, level type 6, logic `TS.BattleLogic`). Where the mode
  cannot be read the map stays as before. The spectator's search that stops early was seen: 2.9 to 4.7 s,
  where it took 15 to 21 s.
- 2026-11-08: The log says each event's type (`event type: settings.m_eventType = N`), the first step to
  a track map only where it helps, asked for by the user: in races and special events (A to B, across
  the finish once), not in King of the Hill, Capture the Flag or Sumo. TSU's EventType names (from its
  metadata) include Race, Points, Battle, Sumo, Tag, Soccer, Collector, Ball and Hill, but not which number
  is which; where the field is not found, the log lists the fields there are. Nothing on the HUD changes yet.
- 2026-11-08: A spectator's search stops at the first race to watch, as a driver's does at the player's
  race. In a public session the watched race was the only one, at hit 42 of 43 (21:36 and 21:39): a full
  search took 15 to 20 s, and in an earlier one the race was at 18% of the data, so about 4 s are expected.
  If the race picked never runs its clock (an old one, with the race to read, maybe the player's own,
  further on), the search goes past it at once, only once, rather than after 30 s. The other races a
  search found are no longer kept (it now stops at the first), so that fallback is gone. Not yet seen in a
  session.
- 2026-11-08: Joining a race in progress is found sooner. Seen as a spectator in a public session: two
  searches found nothing while TSU set the race up, then the wait after empty searches had grown to 50 s,
  so the HUD showed after about 2 minutes. The wait now stays 10 s for the first minute of empty searches
  and only grows after it (custom sessions are still searched less and less). The log also says where the
  watched race was among the hits (`watching the race at hit N of M`), to tell whether a spectator's search
  could stop at the first race to watch. The same session showed the new `the watched race is gone` line at
  a race's end: `no players`, the race over, not an old race lingering.
- 2026-11-08: A spectator's HUD no longer searches all of TSU's memory again when the race it watches
  goes. Seen in a public session joined mid-race, after leaving another: the search (20.5 s) found 43
  controllers, the race watched went at once, and a second search took 18 s. Likely an old race from the
  session left. The other races a search finds are now kept and tried first (a few reads), and the log
  says why a watched race was dropped (`the watched race is gone (...)`). Not yet seen in a session.
- 2026-11-08: The tester's whole log: reads stayed small (20 trips) and took half as long once the game
  was near 60 FPS with all sections, so the busy game slows the reads, not the other way round.
- 2026-11-08: The tester's results with build 2026.11.08.2 (`docs/CONTINUE_HERE.md`, "Tester's Mac"): 115 FPS
  without TurboHUD, 107 with every section unticked (78 before), about 95 with lap and delta (62), about 63
  with all (58). Fewer reads did not help; the windows above the game cost the frames, until the game holds
  near 60 on the 120 Hz screen. The exit hang did not come back. Next: the Metal HUD on the user's Mac.
- 2026-11-08: The tester's instructions rewritten as a plain step-by-step checklist, asked for by the user:
  one action a line, a place to write each answer, a summary table, and the log copied before quitting.
- 2026-11-08: `releases/` keeps only the latest build (2026.11.08.2); the older builds were deleted, asked for by the user.
- 2026-11-08: Build 2026.11.08.2 for the tester, with the reader fixes of the day; the test instructions
  name it and ask whether a second display is connected, with steps 1 and 6 again without it. The fix for the
  reader restarting when TSU starts after TurboHUD was seen working on the user's Mac.
- 2026-11-08: The reader in the bottle no longer restarts when TSU starts after TurboHUD. The new log line
  told why: `KeyError: 'sm_instance'`, as TSU had not yet set up `TS.Services`, and a missing static field
  counted as the game being gone (reader closed, started again 3 s later). It now counts as the game still
  loading, like a missing field of an object, and the same reader tries again.
- 2026-11-08: Checked on the user's Mac with build 2026.11.08 and from source: unticked sections leave the
  screen and come back in place, and the race reads switch at once (about 19 a second at 20, 5 at 5; at 5 a
  read takes about 47 ms instead of 30). Quitting TurboHUD first or TSU first, no reader was left and TSU
  quit normally, so the tester's hang did not come back here. At each start the reader was closed about a
  second after it started and started again 3 s later, with no reason in the log: a connection that worked
  and is dropped now logs why (`TSU: connection dropped (...)`).
- 2026-11-08: New test instructions for the tester's Mac (`TurboHUD-test-instructions.md`), asked for by
  the user, with build 2026.11.08 (`releases/`, macOS 27, built with `--any-macos`). Seven steps tell the
  windows from the reads: closed, every section unticked at 20 and 5 race reads a second, lap and delta at 5
  and 20, all at 20, closed again; and a test of TSU hanging on exit with TurboHUD quit first.
- 2026-11-07: Two steps towards a tester's FPS loss (Mac, about 110 FPS without TurboHUD, 78 with every
  section unticked, 62 with lap and delta, 58 with all). An unticked section was still redrawn, empty,
  whenever its content changed, and on the Mac its window stayed above the game: it is now not redrawn,
  and on the Mac its window leaves the screen. And the settings window sets the race reads a second (20,
  10 or 5, at once; 20 by default), with fewer HUD frames to match, to compare. Seen with real Mac windows
  but not over TSU: whether either gives FPS back is not measured. At 5 a second a track learnt then gets
  a coarser line.
- 2026-11-06: A second build of a day can be told apart: `tools/build_app.py --version 2026.11.06.2`.
  The tester's new version carries it, with the search fix; `RESUME.md` and the log say which they run.
- 2026-11-06: TurboHUD leaves a session alone when it holds no race to read. A tester in a custom session
  (only the clock showed) had a search of all of TSU's memory running about two thirds of the time: over
  20 s each with 10 s between, without end, as TSU's log says an event runs. The wait now doubles up to
  60 s, and goes back to 10 s when a race is found or the event ends. Whether this caused the tester's
  FPS drops is not known yet.
- 2026-11-06: The Mac app can go to a tester, asked for by the user: `tools/build_app.py` now makes a
  `.dmg` with the app, a link to Applications and `Read Me First.txt` (`tools/mac_read_me.txt`). It works
  out which macOS the bundle needs from all its programs, writes that into the app and the read-me, and
  stops if that is newer than macOS 15, as Homebrew's Python needs the macOS it was built on (27 here).
  `tools/get_mac_python.sh` fetches a pinned standalone Python that should fix that; it has not run yet, as
  running a downloaded program needs the user's approval. `--any-macos` builds anyway. PySide6 6.11 itself
  needs macOS 15. The bundle ID no longer holds the user's handle. Not signed with a paid certificate: a
  tester goes through Open Anyway once. Not tried on another Mac.
- 2026-11-05: The lap section shows the leader's lap when the driver is on an earlier lap
  (`Lap 9/20 · Leader 12`), asked for by the user: lapped many times, the driver's own count says little
  about the race. Left out on the leader's lap or in the lead. No more reads of the game.
- 2026-11-05: In the lap times list, each driver's lap (`L12`) is now a right-aligned column before
  Best, asked for by the user, so the numbers line up. The columns are placed with digits as zeros,
  so they stay put while a pit timer runs.
- 2026-11-05: The track map's dots should no longer stand still and jump, seen by the user from time
  to time. Race reads (about 19 a second) and HUD frames (20 a second) ran on separate timers, so
  about once a second a frame had nothing new. A race frame now comes with each new read, and after
  0.1 s without one for the times that run on; the log's `HUD frames` line counts frames with no new
  read. The cause was worked out from the log's rates and the code, not measured before the fix.
- 2026-11-05: Two things asked for by the user. A delta bar (a new section, on by default, top centre
  below the blue flag; `race.DeltaBar`): it fills from the middle, left when ahead of the best lap and
  right when behind, with the delta over it. It is green or red and changes at once, never in between:
  gaining over the last half second is green and losing is red, also against the sign of the delta;
  when steady (within 0.02 s a second), the delta's sign decides. These are starting values, not yet
  tuned in a race. It is full at 1 s. And an option
  to turn off the slipstream cones on the radar, in the menu and in move mode, which also takes away
  the cyan outline of a car being drafted. No more reads of the game; the bar keeps about 10 values.
- 2026-11-05: Pit stops, asked for by the user. Both lists show two live timers: `PIT 24.5s`, from
  pit entry to pit exit, and `(12.03s)`, how long the car stood still in all, kept for 6 s after the
  exit; standing over 45 s shows plain PIT, as the driver may have retired (`PitStops`: pit area and
  velocity with the race clock). In the lap times list they take the Best and running-lap columns
  meanwhile. That list shows each driver's lap (`L12`). The
  tires bar now fills during a change: three recorded stops showed the game holds `tireWear` until
  `tireCompoundAndChangeTicks` reaches 2400 (12 s) and only then sets it to 0. Fuel needed no fix:
  the game refills 5% of the tank a second (18000 of 360000 units), so stops that used 2.5% were
  full in half a second. Not seen: health (the event had no damage), AI or online cars in the pits
  (the bracket relies on their velocity), other tire compounds (the bar then behaves as before).
- 2026-11-05: TurboHUD warns when TSU's bottle is not on D3DMetal, asked for by the user: in
  `turbohud.log` and the text on the menu bar icon, read from the bottle's `cxbottle.conf` when the
  reader starts, never written. The stutter came from that setting: without TurboHUD, alone on a
  server, with the keyboard and with Sidecar off TSU still stuttered, and it ran well on D3DMetal
  (the default before; why, is not known). The README tells players; tried on the user's Mac only.
- 2026-11-05: The proximity radar has no outline in a race, as it can get in the way of the view,
  asked for by the user. It stays in move mode, to show where the radar's box is; the cross lines
  and the cars are as they were.
- 2026-11-05: Online, the HUD stayed away for a whole TurboHUD session (only the local time), seen
  by the user in the first races with the faster search: every search ended in `no race`, while
  a separate connection found the race at once (2.1 s, the user the driver among 14). The cause:
  field lists were kept for good, and a search just after TSU started read
  `TS.ClientEventController` while it and its parents were not yet set up (seen: their fields are
  empty until about a second before the event shows in TSU's log). The empty list then made every
  controller look like no race. That search ran as TSU's log still said an event was running, from
  before TSU started, so the faster search was not the cause. Field lists are now kept only once
  the class and its parents are set up. Seen with TurboHUD started first, as in the failed
  session: the same early search, then the race found in 1.5 s.
- 2026-11-05: The online race search is faster, asked for by the user as the HUD showed 7 to 12 s
  after an online race started. In CrossOver a search now reads half of the time instead of a
  quarter (expected: about 4 to 6 s; a little stutter in the first seconds is the risk, not yet
  seen in a race). The look at the last race's place is gone: the new race was elsewhere in all
  three races logged, as the equal hit counts were a coincidence.
- 2026-11-05: `docs/CONTINUE_HERE.md` notes where the work stopped, asked for by the user: the
  decision on the online race search, what has not been seen in a race, and the test list.
- 2026-11-05: The settings window can be dragged by its background, like the move-mode panel,
  reported by the user.
- 2026-11-05: The proximity radar has no fill behind it, its cars are drawn larger (1.4 times,
  and never under 3% of the radar's width), and the settings window sets when the blue flag
  (1 to 10 s, 2 s by default) and the radar (0.2 to 3 s, 0.5 s by default) show; all asked for
  by the user. A longer radar time zooms the radar out so that such a car still fits.
- 2026-11-05: A Tint tick box for each text section in the move-mode panel, asked for by the
  user: kept with the section and in presets, with Undo. The option for all sections now turns
  it on or off for every one at once; a file from before takes what it had for all.
- 2026-11-05: The outline's least width is now 1.2 px (a seventh of the font size above that),
  as 2 px still filled in the small lines of the draft section (about 10 px), said the user.
- 2026-11-05: The outline is in step with the font again at small sizes: a width of 2 px or a
  seventh of the font size. Its 3 px least made the player and lap time lists harder to read,
  said the user.
- 2026-11-05: A stronger outline round the text, as it was hard to read without the tint (the
  user): 3 px or a seventh of the font size instead of 2 px or a tenth, half of it outside the
  letter. Drawing it through the text images looked the same as filling the shapes before, so
  the images were not the cause.
- 2026-11-05: The delta's number has a slot as wide as its widest form, so " vs best" also stays
  when the number gets another digit. The log says when a race was found by search and not
  where the last one was.
- 2026-11-05: Only the number changes in the delta, reported by the user: " vs best" moved with
  the digits. The number and the label are drawn apart, the label from the width with digits
  as zeros, and the delta has a true minus, as wide as a plus. The HUD's font now asks for
  digits all of one width (`tnum`, in the Mac's system font: `1111` and `8888` alike, also for
  the fuel's and the other sections' numbers), where a font has them.
- 2026-11-05: The HUD shows sooner at the start of an online race after the first, reported by
  the user. A search took about 9 s (6 s measured apart, the race being the 42nd of 42 hits at
  18% of the data, the others left by earlier races), and every search after the first gave
  that same number of hits. So the place of the last race is looked at first, at every retry,
  with the search as before if it is not there. The log says `race found at the last one's
  place` when that works; not yet seen in a race.
- 2026-11-05: Text keeps its size as numbers run, reported by the user on the delta and the
  running lap, whose size changed with the digits while the tint behind them flickered. The
  size is now worked out from the section's usual text or the live text, whichever is wider,
  with digits as zeros, and the tint from the live text with digits as zeros. Short texts such
  as `-` no longer make the text larger.
- 2026-11-05: Text no longer runs past the side of a narrow box, reported by the user on the
  last and best lap section. Text is not as wide as its font size says (in the Mac's system
  font, a quarter wider at 8 px and 4% at 40 px than in proportion to 20 px), so scaling a
  measurement at one size could leave it wider than the box. Sections now measure it at the
  size they draw it, and so does a group's matching.
- 2026-11-05: Follow-up after a race with the fix: reads stayed at about 30 ms, down from about
  1030 ms, and the user felt it was better but not there yet. Reads now come 20 times a second
  from start to start (they waited 50 ms after each, so about 12); the text images are limited
  to 64 MB (they reached 1.3 GB at peak, as large fonts take far more than the 2048 images
  allowed for); the log has a `HUD frames` line on how the overlay draws.
- 2026-11-05: Race reads no longer fall a second behind while driving, reported by the user as
  slow sections and timings. The reads were fine (28 ms from a separate connection, 0.37 ms a
  trip on the game's memory); the thread doing them waited for Python's lock, 5 ms at a time,
  while the overlay filled the shapes of its text (122 of 207 s in a profile of a real race).
  Each text is now filled once and copied as an image (47% of the time down to 21% on real
  windows with 13 sections), the lock is handed over within 1 ms, and a trip waits once.
  With the main thread busy all the time: about 590 ms a read before, about 108 ms now. Not
  yet seen in a race. The log's `race reads` line now also says trips a read and ms a trip.
- 2026-11-05: A bin button next to each preset deletes it, asked for by the user. It is greyed
  out while the preset is empty; Undo brings a deleted preset back, so it asks nothing first.
- 2026-11-05: The user checked the layout work by hand on the Mac and it worked: tight boxes,
  presets, groups, centring and Undo. Backlog item 4 now holds only what is left: in races,
  on Linux and on Windows.
- 2026-11-05: The lap times list shows up to 20 drivers instead of 16, asked for by the user
  (events can have 20 players). With fewer, it looks the same: the box is invisible and only
  the drivers there are drawn. Saved sizes and presets are converted once, with the text the
  same size and the box growing downwards; `settings.before-layout-3.json` keeps the file as
  it was. The players list stays at 8 rows. Not yet seen with 20 cars in a race.
- 2026-11-05: Undo in the move-mode panel, asked for by the user: back one change to the
  layout at a time until none is left, also through a Save that replaced a preset. A drag
  counts as one step once it has stood still for a second; each button is a step of its own.
  It lasts as long as TurboHUD runs, and colours and options are not in it. Move mode now
  looks at the sections five times a second, also without groups. Tested through the real
  app code with a fake window layer; real dragging and Hyprland are still to be seen.
- 2026-11-05: A section's text can go in the middle of its box: a Centre text tick box per
  section in the move-mode panel, off by default, kept with the section and in presets, asked
  for by the user. Each line is centred on its own, measured with digits as zeros so that
  numbers do not make it shake. Not for the speed (always centred), the drawings, or the
  lists with columns.
- 2026-11-05: Every section can be centred across or down its screen from the move-mode
  panel, asked for by the user; only the blue flag, the radar and the track map could. Its
  group stays where it is, as with the others before.
- 2026-11-05: Sections in a group can match, asked for by the user. A button per group in
  the move-mode panel gives its text sections the largest text size among them and one
  width; they stay where they are, and heights stay as different as the content is. Resizing
  a section at its corner now resizes the rest of its group by the same factors. Tested
  through the real app code with a fake window layer; on Hyprland the followers only take
  their new size when the resize ends (written for that, not run there).
- 2026-11-05: Three layout presets, asked for by the user. The move-mode panel has Save and
  Load for each: where each section sits, its size, whether it shows and its group, kept in
  `settings.json`. Ctrl+Shift+1, 2 and 3 load one at any time (Mac, Windows); elsewhere
  `run_turbohud.sh --preset 1`. Colours and options stay global. A preset's Load is greyed
  out until it is saved; a section off every screen comes back to the default spot. Tested
  through the real app code with a fake window layer; the shortcuts were registered on the
  Mac but not pressed, and Windows has not run this.
- 2026-11-05: A text section's box now fits closely round its text at every size, and its
  height sets the text's size, so the edges are never far from the text (asked for by the
  user, replacing the closing-in box from earlier today, which did not help enlarged
  sections). Saved sizes are converted once, with the text the same size and in the same
  spot; `settings.before-layout-2.json` keeps the file as it was. The speed's pedal bars
  get shorter with the box. In a text box the name no longer fits: it shows when the
  pointer rests on the box in move mode.
- 2026-11-05: Shortening a text section below its normal height first closes the box in
  on the text, which keeps its size; only a box that fits it tightly makes it smaller
  (asked for by the user: local time shrank with the edges still far from it). Above the
  normal height, the height still sets the text's size, so an enlarged section still
  shrinks at once down to normal size. A section's name shows in move mode only where it
  fits. The shortest text box is now 10 px, as a shorter one could not be grabbed.
- 2026-11-05: The speed stays centred between its pedal bars, across and down, when the
  section is resized (it kept to the left and the top while the bars stayed at the edges).
  Digits count as zeros for this, so the text does not shake as the speed changes. Reported
  by the user. The other sections were drawn at several sizes: none has anything on both
  sides to centre between, so their text stays at the left, where stacked sections line up.
- 2026-11-04: A running game's log is read. TSU's live log is `log.txt`; only the dated
  copies in `Logs/` were read, so during a run with no new copy yet a running event looked
  ended and no search for the online race started (found live while spectating). The newest
  of both counts now. Checked on the real log: it now says an event runs.
- 2026-11-04: Spectator HUD, asked for by the user. A race without a local player (found
  while spectating an online session with 12 players) used to keep the HUD hidden. Now it
  is read without a car: "Spectating" with the leader's lap and the time left, the player
  list with the gaps to the leader, the lap times, and every car on the track map with the
  leader in gold; the sections about a car of your own stay away. While the watched race's
  clock runs there are no more searches, as one would hold the reads up for about 30 s on
  the Mac; once it has stood for 5 s TurboHUD searches every 30 s while an event runs, and
  prefers another race to the one that stood still. Joining the race needs no search.
  Tested with a fake game and drawn offscreen with 12 made-up drivers; not yet seen with a
  real race (TSU had quit). To check: whether a spectator's replay recorder gives real
  positions, and what fun-mode events show.
- 2026-11-04: Numbers in `turbohud.log` for test drives (asked for by the user before the
  first Mac race; every system). Every 30 s in a race, and when it ends: how many race
  reads, their median and slowest time, and how many took over 50 ms. Each search for an
  online race: when it started, how long it took, how many hits and what it found. The
  reader in the bottle: how long it took to start, why it was given up, when it closes.
  No names or IDs.
- 2026-11-04: macOS live race data. TurboHUD on the Mac now finds TSU in CrossOver and
  starts a read-only reader in its bottle with a portable Windows Python
  (`turbohud/tsu/bottle.py`, `bottle_reader.py`), asked over a pipe; no setup, nothing
  installed in the bottle. The Mac app carries both (`tools/build_app.py`), and a start
  from the source fetches the pinned Python (`tools/get_windows_python.sh`). A reader that
  fails to start is tried again after 10 s, and the tray icon says why. Fixed, found
  spectating an online fun-mode session: a spectator's race has no local player, so a
  search never stopped early, and as the 10 s wait counted from a search's start, while
  one takes about 30 s in the bottle, searches ran back to back. The wait now counts from
  a search's end, and a race the player only watches is remembered: looked at each read
  (which sees the player join) and searched again once a minute. Measured live: one search
  and then 18 looks of about 6 ms in 75 s. The built app ran 60 s against that session and
  quit cleanly. Not yet seen in a race on the Mac.
- 2026-11-04: Windows memory reader (`turbohud/tsu/winmemory.py`), for Windows and for
  TSU inside CrossOver: it opens TSU for reading, lists its memory in the form the
  lookup by name takes, and `connect()` gives `LiveRace` a race reader as the Linux
  probe does. Inside the bottle each read costs about 250 µs, so it reads each 4 KiB
  page once per race read (an online race read with 13 AI: 77 reads instead of 451,
  20 ms instead of 113). Its search pauses after every 1 MiB, so it reads a quarter of
  the time (a search of all the data at once made TSU stutter), and stops at the first
  good hit, from the lowest address up: the race showed after 15 s instead of 110.
  TSU's log is read in the bottle too, so it does not search in menus. Checked live
  in online events with 13 AI; unit tests with fake memory. Not yet used by the app.
- 2026-11-04: macOS live data: the way found. From outside, macOS refuses
  `task_for_pid` on TSU (CrossOver's Wine loader is signed with the hardened runtime);
  only turning off System Integrity Protection or signing CrossOver again would allow
  it. Inside the bottle a Windows program may read TSU (`ReadProcessMemory`), and
  `experiments/bottle_memory_probe.py` (run with
  `sh experiments/run_bottle_memory_probe_mac.sh`) shows it: TSU's memory listed and
  read, about 225 µs a read, TurboHUD's lookup by name unchanged (TS.Services found in
  1.7 s), and a native Mac program reaches one in the bottle over 127.0.0.1 in 78 µs.
  In a race alone the HUD's own race reader works there unchanged: laps, clock,
  position and car read, 17 ms a read (median), so 20 reads a second fit. Not yet
  checked: an online race as a client. Online, hosting with 13 AI, the search found
  the race in 4.1 s and all 14 players read, but a read took 113 ms: 451 small reads
  on only 72 pages of 4 KiB, so a cache of the pages each read touches is needed
  (about 18 ms expected).
- 2026-11-03: Long races (asked by the user: an hour or more). Each frame rebuilt
  every driver's whole list of passed checkpoints about 70 times (for the order, the
  gaps and the blue flag), and that list grows by a lap's checkpoints every lap: with
  17 drivers it took 7 ms a frame after an hour and 15 ms after two, still growing.
  Now it is worked out once per read and kept: 0.8 ms a frame after an hour, 1.7 ms
  after two, measured with made-up races. The rest does not grow with the race: the
  game's finished laps are read once, the track map keeps at most a lap of each car's
  path, the radar only its last moments.
- 2026-11-03: Fixed: every section stuttered once the lap times list was on
  (seen by the user in an online race; TurboHUD averaged 96 % of a core). Every
  section was drawn again 20 times a second, changed or not, and each text's dark
  outline was stroked anew each time: the list's 50 texts took 17 ms a frame. Now a
  section is drawn again only when its content changed, and each text's outline is
  kept as a shape to fill (about five times quicker): 8 ms in the worst frame, when
  all 17 running laps change at once. Measured offscreen; not yet in a race.
- 2026-11-03: Fixed: the player list put a lapped car that finished right after
  the winner second (seen by the user in an online race with 17 drivers: last, shown
  second). Finished drivers were ordered by finish time alone; once the winner is in,
  a lapped car finishes at its next crossing, before the cars on the lead lap come in.
  Now everyone is ordered by how far they got (a finish counts as the next lap's start
  line), then by who got there first. The track map's leader and the cars ahead and
  behind use the same order.
- 2026-11-03: Lap times list (Linux), asked for by the user. A new "Lap times"
  section beside the player list: a heading, then every driver in race order (up to
  16; with more, the leader and those around you) with flag and name, their best lap
  and the running time of their current lap ("Fin" once finished). The race's fastest
  lap is green, your name in the highlight colour. Lap times come from each driver's
  start-line passes, as for your own laps. Rows can now have a middle column, lined up
  just before the right one. Tested with unit tests and offscreen drawing; not yet
  seen in a race.
- 2026-11-03: Code layout notes brought up to date: docs/STACK.md lists the modules
  as they are now (it showed the first skeleton of 2026-10-24), docs/HOW_IT_WORKS.md
  names the command socket (turbohud/control.py), and experiments/README.md says the
  Steam launch option runs `tsu_memory_probe.py` from there.
- 2026-11-03: Outdated notes fixed. README: the intro lists what the Linux HUD shows
  now (it still called fuel, speed and a minimap planned), and "Live lap times on
  Linux" points to the sections under Use. docs/STACK.md: TSU's native Linux build
  (not Proton), how the Linux overlay was built, local builds instead of GitHub
  Actions, the `.tar.gz` until an AppImage. docs/HOW_IT_WORKS.md: dated 2026-11-03,
  and its online section explains the replay recorder's positions.
- 2026-11-03: The user confirmed in a race that the learnt track map and the
  settled worked-out positions seem to work.
- 2026-11-03: Worked-out positions (online, race not recorded) settle onto the road.
  They started each car at the middle of the checkpoint line it passed, which on some
  tracks lies far off the road. Now a car followed from line to line goes on from where
  its worked-out place meets the new line (keeping where across the road it is): the
  error shrinks at every line and in every bend, so it settles within about a lap. Cars
  followed for a whole lap teach each line an anchor (where cars cross it), where a car
  seen for the first time starts. Checked live by hiding the real positions in the AI
  event: median 1.8 units from the real place after about 45 s (90 % within 3.4),
  against 7 (and 15) the old way. The delta and gaps use these when recording is off.
- 2026-11-03: Track map learnt from where the cars drive. In an AI event the map's
  track did not match where the dots went (seen by the user): on that track the
  checkpoint lines are long (up to 300 units) and set off to one side, so a line through
  their middles lay up to 67 units from the road. Now TurboHUD records each car's path
  (real positions only, not in the pits, starting afresh after a jump) and, once any car
  has driven a whole lap, that lap is the track; before that the longest stretch driven
  so far shows. The start mark is where that lap crosses line 0. A learnt track is saved
  in `~/.config/TurboHUD/tracks/` (named from its checkpoint lines), so the next race
  there has its map at once. Checked live on a 63-checkpoint track in the AI event:
  learnt within about a lap, cars 2.3 units from the line on average, 12 at most
  (about the road's width). Dots outside the learnt track (a road from the grid) stay
  inside the map's square.
- 2026-11-03: Track map: your own marker covered cars at the same spot (seen by the
  user in a race, where the map otherwise works). It is now a white ring, open in the
  middle and drawn on top, so a car under it still shows; all dots are a little smaller
  (2.6 % of the map instead of 3.4 %).
- 2026-11-03: Track map (Linux). A new "Track map" section (240 x 240 at first, at
  the right edge of the main screen half way down; square, resizable in move mode, with
  the Centre buttons): the track seen from above, drawn from the checkpoint lines
  TurboHUD already reads (their middles, smoothed; lines at the same spot or in two
  pieces count as one; a loop is closed, a point-to-point track is not), with a white
  start line. No track file or editor export is needed, so it works on every track,
  online too. Dots: you (a white ring), the race leader (gold), the next car ahead
  (red) and the next car behind (green) in the player list's steady order, so the dots
  change over cleanly when you pass; a leader right ahead gets a red ring. Smaller
  bluish dots for backmarkers (more than half a lap behind in the race but ahead on the
  road) between you and the next car ahead, or within half a lap when you lead; a
  backmarker is never the "next car behind". Cars in the pits are dimmed. "Other cars
  on the track map" (tray menu and move-mode panel, saved as map_others, off by
  default) adds the rest as faint grey dots. Logic in turbohud/core/trackmap.py.
  Tested with unit tests and offscreen drawing; not yet seen in a race.
- 2026-11-02: The user confirmed in a race that the "drafts you" colour works.
- 2026-11-02: "<name> drafts you" changes colour with the strength of that car's
  slipstream from the local player (the closer behind, the stronger): from the draft's
  cyan through blue, violet and magenta to red (hud.blend goes round the colour wheel,
  as a straight mix turns grey halfway). Rows can now have a colour of their own
  ('#rrggbb') besides the theme's names.
- 2026-11-02: Linux commands and other desktops. `run_turbohud.sh --toggle` / `--move` /
  `--lock` / `--settings` / `--quit` tell the running TurboHUD what to do through a
  socket in the user's private runtime folder (turbohud/control.py, no Qt: answers in
  34 to 75 ms, tested end to end); a second start opens no second copy but switches the
  running one to move mode. The player can bind a command to a key in the desktop's own
  settings (README shows a Hyprland line); TurboHUD changes none. The move-mode panel
  mentions --toggle where there are no shortcuts. On Wayland desktops other than
  Hyprland (KDE, GNOME) TurboHUD now runs through XWayland, where staying on top works
  (not yet tried there; TURBOHUD_PLATFORM=wayland keeps Wayland). Hyprland unchanged.
- 2026-11-02: Open questions answered. Car size measured in an online race with 13 AI
  cars (Tatuus FA01, 630 reads of real positions): cars in line no closer than about
  4.0 centre to centre, side by side about 1.3 to 1.4; the radar now uses 4.0 x 1.4
  (was a guess of 4.5 x 2.0; `size` in CarPhysicsProperties is 4 bytes, not the size).
  Probe tested with a stand-in game: killed hard (SIGKILL, like a crash) the game keeps
  running (it goes to the system's process manager), TurboHUD then shows "waiting";
  stopped politely (SIGTERM, like Steam's Stop) it passes the stop on and the game ends.
  Fixed: stopped before the game was found, the probe looked on for up to 3 minutes;
  now it quits as soon as the program it started has ended.
- 2026-11-02: The user tested the draft extras (cones, event line, lap share, who
  drafts you) and the settings window (colours, Smaller/Bigger, saved): all seems to
  work.
- 2026-11-02: Settings window (tray menu "Settings…", or the move-mode panel's
  button): swatches for the text, highlight and outline colours, applied at once and
  saved; "Smaller" / "Bigger" resize every section by 10 % from its top-left corner;
  "Reset colours". Swatches instead of a colour dialog, which would be one more window
  for Hyprland to place. Tested offscreen; not yet on the desktop.
- 2026-11-02: Draft extras. The radar draws the slipstream behind each car ahead (the
  event's reach and angle: maxDraftingDistance, maxDraftingAngle), brighter with a cyan
  outline on the car when the local car is in it. The draft section shows, below the
  meter, the event's drafting for the first 20 s of the race clock ("Max -10% drag
  -80% downforce reach 30 20°"), then "Last lap 23% in a slipstream" (race time with a
  draft of 5 % or more), and in yellow who drafts the local player ("<name> drafts you
  45%": a car behind within the reach and angle, from its own drag multiplier). Checked
  live as a client: all 14 cars' drag multipliers read (several drafting), settings
  read; not yet seen in the HUD.
- 2026-11-02: Code formatted with Ruff throughout (16 files) and the remaining lint
  findings fixed: f-strings in the privacy check, pairwise and ClassVar in tests, the
  probe's two catch-all handlers marked as intended. No change in behaviour; all tests
  pass, the privacy check runs as before. `ruff check .` and `ruff format --check .`
  now pass.
- 2026-11-02: Notes brought up to date: RESUME's current state and next steps, and the
  backlog (Windows overlay and live data, macOS, builds and release, Linux shortcuts,
  more features); fuel, speed, guest races and the rest are done.
- 2026-11-02: The user believes the radar works as an online client too (not checked
  in detail: car places, cars ahead).
- 2026-11-02: Confirmed by the user in races: PIT over the whole pit area, health
  (number, colours, bar), the HUD staying after the finish until the race is over, and
  move mode (groups, centring, saved after a restart). Still to see: the radar as an
  online client (car places, cars ahead).
- 2026-11-02: The user confirmed the draft section works in an online race (meter and
  downforce warning).
- 2026-11-02: Draft section (slipstream). "Draft 73%" with a cyan level bar: how strong
  the slipstream is, of the most this event allows, from the car's own multipliers
  (CarStateUpdater.m_draftingViscosityFactor = 1 - speed effect x draft) and the event's
  settings read from memory (EventController.m_eventLogic.m_eventSettings.drafting; that
  server: 10 % speed effect, 80 % downforce reduction, unlike the local
  eventsettings.json of the last hosted event). A yellow "-58% downforce" while the
  slipstream takes 5 % or more (m_draftingDownforceFactor). Checked live: settings read,
  0 % out of the draft; the 73 % / 58 % match values measured while drafting earlier.
  Shown only in events with drafting on.
- 2026-11-02: The radar also reacts to cars ahead. It reacted only to cars behind or
  beside (as first asked), so closing in on a car ahead showed nothing until it was
  level. Now a car ahead counts the same way (nose to tail over the local speed: faint
  at 0.5 s, full from 0.1 s), and the local car sits in the middle of the radar so a
  car 0.5 s ahead at full speed is in view. Before that, checked as an online client:
  real positions in every read, delta steps at most 0.18 s, radar shown once, no
  blinking.
- 2026-11-02: Real car positions as an online client, from the replay recorder. TSU
  records every race; the client's TS.EventRecorder.m_lastQuantizedVehicleStates holds
  each car's last recorded state in player-list order, position as (value - 2**20) /
  1024 (found live with 13 AI: cars crossing checkpoint lines were 0.82 from them on
  average, max 2.8, against 2.1 for the next best scale). All 14 positions read; the
  radar, the delta and the gaps use them (not estimated). Not used when the recorder's
  tick stands still for 1 s (recording off): then the estimate (no radar). Left: the
  delta still jumped up to 0.76 s once in 12 s (median step 0.015 s); maybe the recorder
  stores a car's state only every few ticks. The radar has not been seen as a client.
- 2026-11-02: Checked as an online client (someone else's server, 13 AI): with the
  worked-out positions the delta ran live (138 values in 144 reads over 12 s, lap 2)
  and the gaps changed every read. Added: a live gap while both cars are between the
  same two checkpoints (the one ahead's share of the stretch since its time at the first
  line), which had held still and then jumped about 1 s. Left: jumps of 0.3 to 0.5 s
  right at some checkpoints, maybe because a client's checkpoint times come from the
  server a little late against the local race clock.
- 2026-11-02: Live delta and gaps as an online client. Joining someone else's server
  (or hosting online with only AI) the game keeps no car positions (they stay at (0, 0)),
  so the delta went in checkpoint steps. It does keep each car's velocity, so
  race.DeadReckoning starts a car at the middle of the checkpoint line it passed last, at
  its checkpoint time, and moves it on by its velocity until the next line (about a
  second). The delta, the fuel trend and the player gaps use it; the radar does not
  (where across the track a car is stays unknown). Not yet seen in a race.
- 2026-11-01: docs/HOW_IT_WORKS.md: what TurboHUD shows, its three parts (game,
  probe, overlay), the permission, how the race is found by name, online races, inputs,
  the Hyprland windows, what it does to RAM, CPU and the game (with measurements), the
  files it writes, and its limits.
- 2026-11-01: Online search made light. Measured: in menus and lobbies (no active
  server) TurboHUD searched the game's memory every 10 s for an online race, the probe
  peaking at 58 % of a core and holding 4.4 GB of RAM (peak 5.4 GB) from a new 16 MB
  buffer per chunk that the allocator kept. Now it searches only while TSU's own log
  says an event runs (turbohud/tsu/gamelog.py: last "Event started." after the last
  "Event ended."; the log is only read), and the probe reuses one buffer per connection
  (checked: 16 MB once, flat over repeated searches). The probe change needs TSU to be
  restarted (the probe starts with the game).
- 2026-11-01: Level bars below fuel, tires and health: lit from the left to what is
  left. Fuel red when it will not last to the finish, else (like tires) green, yellow
  under 35 %, red under 15 %; health green, yellow with less downforce, red when slowed.
  Saved section sizes stay, so their text gets a little smaller to make room (resize in
  move mode to taste).
- 2026-11-01: Health is rounded up as in the game: 126 of 500 hit points showed 25 %
  where TSU says 26 % (checked live). The colours keep the exact value.
- 2026-11-01: Live gaps in the player list, like the delta to the best lap. Where the
  cars' positions are known (offline, hotlap, hosted online races with other players),
  the car behind's place between two checkpoints gives the moment the car ahead was
  there (race.live_gap, with the delta's handling of lines written together), and the
  gap is the race clock since then. Without positions (online races with only AI: the
  game is a client) it stays at the last checkpoint both passed. Not yet seen in a race.
- 2026-11-01: The HUD stays after the local player finishes. It used to switch to the
  three finish sections only (laps, best lap, last lap), so the player list and the rest
  went away while others still raced. Now the lap sections show the finish and the rest
  stays until the race is over (the clock stops: lobby); the delta goes, with no lap to
  compare.
- 2026-11-01: Health section and PIT for the whole pit area (Linux). The last online
  event (3 laps, Laguna Seca, 3 players) had fuel, tire wear and collision damage on.
  New "Health" section: TS.VehicleState.hitPoints of maxHitPoints (read live: 497 of
  500), shown in events with damage (CarStateUpdater.m_gradualDamageEnabled); yellow
  "less downforce" and red "slowed" below the game's own limits (1 / the updater's hit
  points to relative health multipliers: 90 % and 75 % in that event, as in its settings).
  The player list's PIT now also shows while a car is anywhere in the pit area
  (VehicleState.inPitArea), not only in the pit box (inPit); not yet seen in the pits.
- 2026-11-01: Blue flag no longer blinks behind a lapper. Seen online: the leader, a
  lap ahead, drove just in front; each time the local player reached the checkpoint it
  had just passed, both were exactly a lap apart in count, which was taken as "behind,
  about to pass" (flag at full) until it passed the next one (17 switches in 15 s). At
  the same count the one who got to the checkpoint first is now ahead; checked live
  afterwards: no flag, no switches.
- 2026-11-01: Radar flicker fixed. On a hosted online race (TSU runs the server: the
  offline path, TS.HostEventController) car positions are read, but the game moves them
  on only about every 0.1 s while TurboHUD reads every 0.05 s; with direction and speed
  taken from the movement, every other read had none and the radar blinked. Now each
  car's velocity and nose direction come from the game (CarStateUpdater.m_oldVelocity3d,
  m_oldForwardDirection; checked online: matches the speedometer), positions are carried
  on along the velocity between updates, and the radar shows at once but stays 0.4 s and
  fades when no car counts any more. Online races with only AI drivers (the game is a
  client there) still have no positions.
- 2026-11-01: Online races (Linux), including ones the player hosts. Checked in a
  self-hosted online race with 13 AI drivers: there TS.Services.m_activeServer is null
  and the game is a client; the race is in a TS.ClientEventController, which no static
  field leads to. The reader now finds it by its class (one probe search, about 1.7 s,
  at most every 10 s while there is no race), keeps it while it lasts and reads on as
  before: lap times, delta, players (names, flags, order), speed, pedals, blue flag all
  read. The car positions stay (0, 0) online, so they count as unknown: the delta falls
  back to checkpoint steps and the radar does not show online yet (positions are only
  in Unity's own transform, still to find). Fuel and tires were empty in that event
  (maybe off there).
- 2026-11-01: Light tint fixes. The speed section's tint now reaches from the throttle
  bar to the brake bar however wide the section is (the brake bar sat outside it), and
  the tint is lighter (black at 16 % instead of 25 %).
- 2026-11-01: Centre buttons for the blue flag and the radar. In the move-mode panel,
  "Centre ↔" centres the section across the screen it is on and "Centre ↕" down it
  (hud.centred); its size stays and its group stays where it is.
- 2026-11-01: The move-mode panel no longer covers sections. It goes near the middle
  of the screen a third down as before, but moves to the nearest spot that covers no
  shown section (hud.free_spot); it had hidden the proximity radar. It can also be
  dragged by its background.
- 2026-11-01: Proximity radar (Linux). A new "Proximity radar" section (160 x 160,
  centred a little below the middle of the main screen at first, shown by default): your
  car in the middle heading up, the other cars around it in their directions. It appears
  when a car is 0.5 s behind (faint, 20 %) and is fully visible from 0.1 s or alongside;
  a car is red when beside or within 0.1 s, yellow when closing in behind, grey ahead.
  Every car's position is read (TS.Vehicle.m_statsNewPosition); direction and speed come
  from the last 0.15 s of positions, and the time gap is the distance from its nose to
  your tail over your speed. Cars more than 8 to the side (another part of the track) or
  in the pits do not count; standing still there is no radar. The car size (4.5 x 2) is
  a guess, and whether the game updates the other cars' positions is not checked yet.
- 2026-11-01: Section groups. In the move-mode panel each section can join group A, B,
  C or D (saved per section); dragging one section of a group moves the others by the
  same amount. TurboHUD looks where the sections are five times a second in move mode
  while groups exist (one hyprctl request for all of them on Hyprland), moves the rest
  with a single move request each, and once the drag stops places them fully again
  (workspace and pin, for a move to another monitor). Logic in hud.GroupMover. Ruff
  installed for the checks in its own tools environment, `.buildtools/ruff-venv`
  (ruff 0.17.3); new findings in the changed files fixed, older ones left.
- 2026-11-01: Light tint option, blue flag outline, steady player list (Linux). "Light
  tint behind the sections" (tray menu and move-mode panel, saved as backdrop, off by
  default): a faint dark box behind each section's text, only as large as the text (the
  pedal bars and the player list's right column included); in move mode the blue move
  tint replaces it. The blue flag now has a darker blue outline. The player list takes
  a new order only once it has lasted 0.3 s (race.Standings), so cars passing each
  other or a checkpoint written late do not make names jump back and forth; the gaps
  stay live.
- 2026-11-01: Blue flag (Linux). A new "Blue flag" section: a navy bar, at the top
  centre of the main screen at first, shown by default and resizable in move mode. It
  appears when a car that is about to lap you (any car, not only the leader) is within
  2 s behind on the track: faint (20 %) at 2 s, fully visible from 0.5 s, gone once the
  car passes. The gap is how much later the car passed the checkpoint it last passed,
  and grows while it does not reach your next one (turbohud/core/race.py blue_flag).
  Not yet checked in a race with other players.
- 2026-11-01: Player list and mph (Linux). New "Players" section: position, flag (as a
  colour emoji where such a font is installed, else the country code), name, PIT, and the
  gap to the local player at the last checkpoint both passed (red ahead, green behind,
  "+1 L" a lap or more apart); with more than 8 players the leader and those around the
  local one. Read per player: m_playerInfo.m_profile (m_name, flag: TS.Flag, mapped to
  ISO codes in turbohud/core/flags.py), m_stats, m_vehicle.m_stateUpdater.inPit. Speed
  in km/h or mph (tray menu and move-mode panel, saved as speed_unit). Not yet checked
  with other players in a race.
- 2026-11-01: The race sections show from the grid on: once the race exists and its
  clock runs (it starts when the grid is set, before the lights). Not while TSU starts,
  in the menus, the lobby or while a race loads (no placeholders, no waiting texts), and
  not while the clock stands (a finished race lingering in the lobby, or a pause). What
  TurboHUD waits for is in the tray icon's tooltip. The local time shows while TSU runs.
- 2026-11-01: First-launch layout: all sections one below the other at the left of the
  largest screen, laid out as on a 1920x1080 screen (40 px from the edge, vertically
  centred, a second column only if they do not fit), none overlapping. Saved places are
  kept as before; a section whose screen is gone moves to the largest screen.
- 2026-11-01: The speed section's pedal bars only show with a speed (not in the menus
  or before TSU runs; in move mode as a sample). On Linux the local time shows once TSU
  is running, from its main menu on.
- 2026-11-01: Fuel balance without blips: the recent laps' fuel use is taken at the
  car's place between two checkpoints, with the live delta's handling of lines passed
  together, same-spot and split lines (shared in LapState.stretch). Replayed over a
  recorded drive: largest jump 0.008 % of the tank (was 0.144 %). New section "Fuel to
  finish": laps of fuel to spare (green, +0.8 laps) or short (red), against the laps
  still to drive by the lap limit or, at the recent lap times, the time limit.
- 2026-11-01: While a session sets up its race (loading, grid), every section shows
  with placeholders ("Race starting..."), so the HUD is in place before the lights go
  out; in the menu only the lap section speaks. Pedal bars follow the controller's
  triggers finely: TSU rounds throttle and brake to thirds (checked in a drive: only 0,
  1/3, 2/3, 1), so TurboHUD also reads the gamepad itself through the Linux joystick
  interface (`turbohud/tsu/controller.py`; with Steam Input the virtual X-Box 360 pad,
  right trigger throttle, left brake; only gamepads, never a keyboard). A bar shows the
  greater of pad and game value, so a keyboard still works.
- 2026-11-01: The speed turns yellow while lifting: no throttle and no brake, above
  5 km/h (coasting).
- 2026-11-01: Pedal bars in the speed section: a throttle bar on its left (lights up
  green) and a brake bar on its right (red), as tall as the section, grey without input,
  filled in part for part pressure. Read from TS.CarControls (CarStateUpdater.m_controls,
  `gas` and `brake`, or the thirds TSU keeps); not yet checked in a drive.
- 2026-11-01: Hiding a section no longer closes its window: it draws nothing and lets
  clicks through, so showing it again needs no new window (Hyprland had opened the new
  one as fullscreen over the fullscreen game, where it could not be placed or pinned).
  As a safety net TurboHUD ends fullscreen for its own windows before placing them.
  New sections are placed only by the sections on the same monitor.
- 2026-11-01: The fuel line also shows how much fuel this lap has saved (+0.18%, green)
  or burnt (-0.12%, red) so far against the recent laps, in % of the tank.
- 2026-11-01: Fuel with one decimal (76.6%), and the laps it lasts in green when the
  current lap uses less fuel than the recent laps did up to the same checkpoint (lifting,
  saving fuel), red when more, white when within 1 % of a lap's use. HUD lines can now
  end in a second colour.
- 2026-11-01: Local time section ('HH:MM', 24 hours), on every system and outside races
  too. Sections new to a player go below the placed ones, or in a new column to their
  right when there is no room below (before, they could fall off the screen and end up
  on another monitor).
- 2026-11-01: Smoother live delta and fuel, tires and speed (Linux). A recorded drive
  showed where the delta jumped (up to 1.5 s): some checkpoints are two lines at the
  same spot or one line split in two pieces with the same time, and TSU writes the second
  one's time only at the next line; some lines are very long. Same-time lines now count
  as one checkpoint, and how far the car is between checkpoints comes from its distance
  to the actual line pieces. Replayed over the drive: largest jump 0.11 s (was 1.46 s),
  95 % of readings within 6 ms of the smooth curve (was 59 ms). New sections: fuel and
  tires left in % with the laps they last (average of the last 3 laps, restarting after
  a pit stop), and speed in km/h. New sections go below the ones already placed.
- 2026-11-01: Section boxes fit their content: a box's height sets the text size, and
  text only shrinks when the box is too narrow for it, so the edge shows the real size.
  Live delta: lines that TSU counts passed together (1 with 0 at the start, 119 with 118)
  now form one stretch, which removes the wrong positive deltas just after the line and
  before the finish; the car is projected onto the path between the lines' middles,
  which also holds in tight bends.
- 2026-11-01: HUD sections. The HUD is now four separate boxes (lap and time left,
  running lap, delta to best, last and best lap), each in its own window, so they can sit
  anywhere on a wide screen. Move mode unlocks them all: drag to place, resize at the
  corner to scale the text; a panel shows or hides each section and locks or quits.
  Each section's place, size and visibility are saved (`sections` in `settings.json`);
  on the first start they stack where the old HUD was. On Hyprland every section and the
  panel are floated and pinned on their own (the panel takes clicks).
- 2026-11-01: Live delta to the best lap. Between checkpoints the delta now moves with
  the car: from its position (`TS.Vehicle.m_statsNewPosition`) and the track's checkpoint
  lines (local player `m_statsUpdater.m_checkpoints`, each line's two ends), TurboHUD
  works out how far the car is from one line to the next and when the best lap was at
  the same place. Reads are much faster: the reader keeps what does not change during a
  race, field lists and checkpoint lines come in batched reads, and the probe no longer
  loads the C library for every read (4 µs instead of about 1.6 ms; takes effect when
  TSU is next started). The race is read and the HUD drawn 20 times a second.
- 2026-11-01: Delta to the best lap (Linux). Under the running lap time the HUD shows how
  far ahead (green, `-0.412 vs best`) or behind (red, `+0.230`) the current lap is
  against the best lap, at the last checkpoint passed (TSU keeps every checkpoint time,
  about 120 a lap, so it updates every second or less). Nothing on the first lap.
- 2026-11-01: TurboHUD stays on top of TSU on Hyprland (Omarchy). On Wayland Qt cannot
  keep a window on top, and Hyprland tiled TurboHUD like any window. Now TurboHUD asks
  Hyprland at runtime, for its own window only, to float, place and pin it, give it no
  keyboard focus, frame, shadow or blur, and hands the focus back
  (`turbohud/overlay/hyprland.py`; Lua commands on Hyprland 0.55+, classic ones before).
  No Hyprland or Omarchy configuration is read or changed. Switching move mode no longer
  re-creates the window, move mode no longer ends when the mouse moves, and the moved
  position is saved (only Hyprland knows it on Wayland). Checked on Hyprland 0.56 over a
  fullscreen test window; not yet over TSU itself.
- 2026-11-01: Live lap times in the overlay (Linux). With TSU started from Steam through
  the memory probe, the HUD shows the lap (3/13) and time left, the running lap time,
  and the last and best lap; at the finish, the best lap. Before that it says what it is
  waiting for. Reading runs in a background thread (`turbohud/tsu/client.py`), so the
  overlay never waits for the game; the logic is in `turbohud/core/il2cpp.py` and
  `turbohud/core/race.py`. The probe moved into the app (`turbohud/tsu/probe.py`);
  `experiments/tsu_memory_probe.py` only starts it, so the Steam launch option is
  unchanged. Windows and macOS keep the session clock.
- 2026-11-01: Live lap data from TSU's memory, found by name at every start
  (`experiments/tsu_lap_reader.py`): race clock, time left, lap count, current, last and
  best lap, through the game's own type information, with no stored addresses. Works
  live on Omarchy Linux while hosting alone; the lap times match the game's exactly.
- 2026-11-01: Memory probe for Linux (`experiments/tsu_memory_probe.py`). Steam starts
  TSU through it, so it may read TSU's memory and nothing else's, with no sudo, setcap or
  system change. It checks one read of the game's code and logs the result to
  `~/.config/TurboHUD/memory_probe.log`. Self-test passes on Omarchy; not yet tried with
  TSU.
- 2026-11-01: Renamed TurboKit to TurboHUD (package `turbohud/`, `launch_turbohud.py`,
  `run_turbohud.sh` / `.cmd`, settings folder `TurboHUD`). The project is now local only:
  nothing is pushed to GitHub (the remote's push URL is disabled), changes are approved by
  a local merge, and the folder will be shared over the local network later. The icon
  image still reads "TurboKit" and needs a new version.
- 2026-10-24: HUD text and app icon. The move-mode hint now sits on its own two lines
  above the Lock and Close buttons, and the box's minimum size grows with the theme's
  scale so nothing overlaps. Text outlines are filled by winding and merged, which fixes
  letters built from overlapping parts (a hole in "+", the broken-looking "4" on Linux);
  Linux prefers a plain sans-serif font. The TSU TurboHUD image is the app, window and
  tray icon (Pillow converts it for Windows and macOS builds). Checked by hand on the Mac
  and on Omarchy Linux.
- 2026-10-24: App skeleton and bundled builds. `turbohud/` holds the overlay (locked and
  move mode, shortcuts, tray icon, saved placement and theme) with a session clock as the
  first HUD. `tools/build_app.py` builds a ready-to-run app with PyInstaller (Mac: 27 MB
  ZIP); GitHub Actions builds and smoke-tests Windows, macOS and Linux. `README.md`
  explains install, first start (step by step per system) and use. Tested by hand on the
  Mac. On Omarchy Linux it runs but does not stay on top of TSU (backlog).
- 2026-10-24: Qt overlay probe tested over TSU on the Mac, in Fullscreen with and
  without Fullscreen Exclusive: the HUD shows, text is crisp, clicks pass through,
  shortcuts and move mode work, and the game does not stutter. Qt is confirmed for the
  Mac overlay; Windows is next.
- 2026-10-23: Qt overlay probe (`experiments/qt_overlay_probe.py`) on the chosen stack:
  a test HUD (outlined text, clock, bar, small map) in a transparent, click-through Qt
  window with move mode and the shortcuts, raised above Fullscreen on the Mac through
  ctypes. Runners set up the pinned PySide6 in `.buildtools/qt-venv`. Starts on the Mac;
  not yet tested over TSU.
- 2026-10-23: Stack chosen (`docs/STACK.md`): Python with Qt (PySide6), shipped as a
  ready-to-run app for Windows, macOS and Linux, so players install nothing else. Chosen
  for good-looking, customisable HUD graphics drawn once for all systems. Linux limits
  (Wayland, Steam Deck) noted.
- 2026-10-23: Native Mac overlay probe (`experiments/mac_overlay_probe.py`). A plain Mac
  program outside CrossOver, at a window level above full-screen windows. It shows over
  TSU in Fullscreen, lets clicks through, and has the same shortcuts and move mode, with
  no permission needed. The Mac overlay for Fullscreen must therefore be native.
- 2026-10-23: Overlay probe. A test overlay for TSU, with a launcher that runs it in the
  CrossOver bottle using a portable Windows Python. On the Mac it works over TSU except in
  TSU's Fullscreen mode, where no window from inside CrossOver can show.
