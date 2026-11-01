# Progress

Every finished change, oldest first. `RESUME.md` keeps the most recent ones at the top of
its "Recent changes".

- 2026-10-23: Overlay probe. A test overlay for TSU, with a launcher that runs it in the
  CrossOver bottle using a portable Windows Python. On the Mac it works over TSU except in
  TSU's Fullscreen mode, where no window from inside CrossOver can show.
- 2026-10-23: Native Mac overlay probe (`experiments/mac_overlay_probe.py`). A plain Mac
  program outside CrossOver, at a window level above full-screen windows. It shows over
  TSU in Fullscreen, lets clicks through, and has the same shortcuts and move mode, with
  no permission needed. The Mac overlay for Fullscreen must therefore be native.
- 2026-10-23: Stack chosen (`docs/STACK.md`): Python with Qt (PySide6), shipped as a
  ready-to-run app for Windows, macOS and Linux, so players install nothing else. Chosen
  for good-looking, customisable HUD graphics drawn once for all systems. Linux limits
  (Wayland, Steam Deck) noted.
- 2026-10-23: Qt overlay probe (`experiments/qt_overlay_probe.py`) on the chosen stack:
  a test HUD (outlined text, clock, bar, small map) in a transparent, click-through Qt
  window with move mode and the shortcuts, raised above Fullscreen on the Mac through
  ctypes. Runners set up the pinned PySide6 in `.buildtools/qt-venv`. Starts on the Mac;
  not yet tested over TSU.
- 2026-10-24: Qt overlay probe tested over TSU on the Mac, in Fullscreen with and
  without Fullscreen Exclusive: the HUD shows, text is crisp, clicks pass through,
  shortcuts and move mode work, and the game does not stutter. Qt is confirmed for the
  Mac overlay; Windows is next.
- 2026-10-24: App skeleton and bundled builds. `turbohud/` holds the overlay (locked and
  move mode, shortcuts, tray icon, saved placement and theme) with a session clock as the
  first HUD. `tools/build_app.py` builds a ready-to-run app with PyInstaller (Mac: 27 MB
  ZIP); GitHub Actions builds and smoke-tests Windows, macOS and Linux. `README.md`
  explains install, first start (step by step per system) and use. Tested by hand on the
  Mac. On Omarchy Linux it runs but does not stay on top of TSU (backlog).
- 2026-10-24: HUD text and app icon. The move-mode hint now sits on its own two lines
  above the Lock and Close buttons, and the box's minimum size grows with the theme's
  scale so nothing overlaps. Text outlines are filled by winding and merged, which fixes
  letters built from overlapping parts (a hole in "+", the broken-looking "4" on Linux);
  Linux prefers a plain sans-serif font. The TSU TurboHUD image is the app, window and
  tray icon (Pillow converts it for Windows and macOS builds). Checked by hand on the Mac
  and on Omarchy Linux.
- 2026-11-01: Renamed TurboKit to TurboHUD (package `turbohud/`, `launch_turbohud.py`,
  `run_turbohud.sh` / `.cmd`, settings folder `TurboHUD`). The project is now local only:
  nothing is pushed to GitHub (the remote's push URL is disabled), changes are approved by
  a local merge, and the folder will be shared over the local network later. The icon
  image still reads "TurboKit" and needs a new version.
- 2026-11-01: Memory probe for Linux (`experiments/tsu_memory_probe.py`). Steam starts
  TSU through it, so it may read TSU's memory and nothing else's, with no sudo, setcap or
  system change. It checks one read of the game's code and logs the result to
  `~/.config/TurboHUD/memory_probe.log`. Self-test passes on Omarchy; not yet tried with
  TSU.
- 2026-11-01: Live lap data from TSU's memory, found by name at every start
  (`experiments/tsu_lap_reader.py`): race clock, time left, lap count, current, last and
  best lap, through the game's own type information, with no stored addresses. Works
  live on Omarchy Linux while hosting alone; the lap times match the game's exactly.
- 2026-11-01: Live lap times in the overlay (Linux). With TSU started from Steam through
  the memory probe, the HUD shows the lap (3/13) and time left, the running lap time,
  and the last and best lap; at the finish, the best lap. Before that it says what it is
  waiting for. Reading runs in a background thread (`turbohud/tsu/client.py`), so the
  overlay never waits for the game; the logic is in `turbohud/core/il2cpp.py` and
  `turbohud/core/race.py`. The probe moved into the app (`turbohud/tsu/probe.py`);
  `experiments/tsu_memory_probe.py` only starts it, so the Steam launch option is
  unchanged. Windows and macOS keep the session clock.
- 2026-11-01: TurboHUD stays on top of TSU on Hyprland (Omarchy). On Wayland Qt cannot
  keep a window on top, and Hyprland tiled TurboHUD like any window. Now TurboHUD asks
  Hyprland at runtime, for its own window only, to float, place and pin it, give it no
  keyboard focus, frame, shadow or blur, and hands the focus back
  (`turbohud/overlay/hyprland.py`; Lua commands on Hyprland 0.55+, classic ones before).
  No Hyprland or Omarchy configuration is read or changed. Switching move mode no longer
  re-creates the window, move mode no longer ends when the mouse moves, and the moved
  position is saved (only Hyprland knows it on Wayland). Checked on Hyprland 0.56 over a
  fullscreen test window; not yet over TSU itself.
- 2026-11-01: Delta to the best lap (Linux). Under the running lap time the HUD shows how
  far ahead (green, `-0.412 vs best`) or behind (red, `+0.230`) the current lap is
  against the best lap, at the last checkpoint passed (TSU keeps every checkpoint time,
  about 120 a lap, so it updates every second or less). Nothing on the first lap.
- 2026-11-01: Live delta to the best lap. Between checkpoints the delta now moves with
  the car: from its position (`TS.Vehicle.m_statsNewPosition`) and the track's checkpoint
  lines (local player `m_statsUpdater.m_checkpoints`, each line's two ends), TurboHUD
  works out how far the car is from one line to the next and when the best lap was at
  the same place. Reads are much faster: the reader keeps what does not change during a
  race, field lists and checkpoint lines come in batched reads, and the probe no longer
  loads the C library for every read (4 µs instead of about 1.6 ms; takes effect when
  TSU is next started). The race is read and the HUD drawn 20 times a second.
- 2026-11-01: HUD sections. The HUD is now four separate boxes (lap and time left,
  running lap, delta to best, last and best lap), each in its own window, so they can sit
  anywhere on a wide screen. Move mode unlocks them all: drag to place, resize at the
  corner to scale the text; a panel shows or hides each section and locks or quits.
  Each section's place, size and visibility are saved (`sections` in `settings.json`);
  on the first start they stack where the old HUD was. On Hyprland every section and the
  panel are floated and pinned on their own (the panel takes clicks).
- 2026-11-01: Section boxes fit their content: a box's height sets the text size, and
  text only shrinks when the box is too narrow for it, so the edge shows the real size.
  Live delta: lines that TSU counts passed together (1 with 0 at the start, 119 with 118)
  now form one stretch, which removes the wrong positive deltas just after the line and
  before the finish; the car is projected onto the path between the lines' middles,
  which also holds in tight bends.
- 2026-11-01: Smoother live delta and fuel, tires and speed (Linux). A recorded drive
  showed where the delta jumped (up to 1.5 s): some checkpoints are two lines at the
  same spot or one line split in two pieces with the same time, and TSU writes the second
  one's time only at the next line; some lines are very long. Same-time lines now count
  as one checkpoint, and how far the car is between checkpoints comes from its distance
  to the actual line pieces. Replayed over the drive: largest jump 0.11 s (was 1.46 s),
  95 % of readings within 6 ms of the smooth curve (was 59 ms). New sections: fuel and
  tires left in % with the laps they last (average of the last 3 laps, restarting after
  a pit stop), and speed in km/h. New sections go below the ones already placed.
- 2026-11-01: Local time section ('HH:MM', 24 hours), on every system and outside races
  too. Sections new to a player go below the placed ones, or in a new column to their
  right when there is no room below (before, they could fall off the screen and end up
  on another monitor).
- 2026-11-01: Fuel with one decimal (76.6%), and the laps it lasts in green when the
  current lap uses less fuel than the recent laps did up to the same checkpoint (lifting,
  saving fuel), red when more, white when within 1 % of a lap's use. HUD lines can now
  end in a second colour.
- 2026-11-01: The fuel line also shows how much fuel this lap has saved (+0.18%, green)
  or burnt (-0.12%, red) so far against the recent laps, in % of the tank.
- 2026-11-01: Hiding a section no longer closes its window: it draws nothing and lets
  clicks through, so showing it again needs no new window (Hyprland had opened the new
  one as fullscreen over the fullscreen game, where it could not be placed or pinned).
  As a safety net TurboHUD ends fullscreen for its own windows before placing them.
  New sections are placed only by the sections on the same monitor.
- 2026-11-01: Pedal bars in the speed section: a throttle bar on its left (lights up
  green) and a brake bar on its right (red), as tall as the section, grey without input,
  filled in part for part pressure. Read from TS.CarControls (CarStateUpdater.m_controls,
  `gas` and `brake`, or the thirds TSU keeps); not yet checked in a drive.
- 2026-11-01: The speed turns yellow while lifting: no throttle and no brake, above
  5 km/h (coasting).
- 2026-11-01: While a session sets up its race (loading, grid), every section shows
  with placeholders ("Race starting..."), so the HUD is in place before the lights go
  out; in the menu only the lap section speaks. Pedal bars follow the controller's
  triggers finely: TSU rounds throttle and brake to thirds (checked in a drive: only 0,
  1/3, 2/3, 1), so TurboHUD also reads the gamepad itself through the Linux joystick
  interface (`turbohud/tsu/controller.py`; with Steam Input the virtual X-Box 360 pad,
  right trigger throttle, left brake; only gamepads, never a keyboard). A bar shows the
  greater of pad and game value, so a keyboard still works.
- 2026-11-01: Fuel balance without blips: the recent laps' fuel use is taken at the
  car's place between two checkpoints, with the live delta's handling of lines passed
  together, same-spot and split lines (shared in LapState.stretch). Replayed over a
  recorded drive: largest jump 0.008 % of the tank (was 0.144 %). New section "Fuel to
  finish": laps of fuel to spare (green, +0.8 laps) or short (red), against the laps
  still to drive by the lap limit or, at the recent lap times, the time limit.
- 2026-11-01: The speed section's pedal bars only show with a speed (not in the menus
  or before TSU runs; in move mode as a sample). On Linux the local time shows once TSU
  is running, from its main menu on.
- 2026-11-01: First-launch layout: all sections one below the other at the left of the
  largest screen, laid out as on a 1920x1080 screen (40 px from the edge, vertically
  centred, a second column only if they do not fit), none overlapping. Saved places are
  kept as before; a section whose screen is gone moves to the largest screen.
- 2026-11-01: The race sections show from the grid on: once the race exists and its
  clock runs (it starts when the grid is set, before the lights). Not while TSU starts,
  in the menus, the lobby or while a race loads (no placeholders, no waiting texts), and
  not while the clock stands (a finished race lingering in the lobby, or a pause). What
  TurboHUD waits for is in the tray icon's tooltip. The local time shows while TSU runs.
- 2026-11-01: Player list and mph (Linux). New "Players" section: position, flag (as a
  colour emoji where such a font is installed, else the country code), name, PIT, and the
  gap to the local player at the last checkpoint both passed (red ahead, green behind,
  "+1 L" a lap or more apart); with more than 8 players the leader and those around the
  local one. Read per player: m_playerInfo.m_profile (m_name, flag: TS.Flag, mapped to
  ISO codes in turbohud/core/flags.py), m_stats, m_vehicle.m_stateUpdater.inPit. Speed
  in km/h or mph (tray menu and move-mode panel, saved as speed_unit). Not yet checked
  with other players in a race.
- 2026-11-01: Blue flag (Linux). A new "Blue flag" section: a navy bar, at the top
  centre of the main screen at first, shown by default and resizable in move mode. It
  appears when a car that is about to lap you (any car, not only the leader) is within
  2 s behind on the track: faint (20 %) at 2 s, fully visible from 0.5 s, gone once the
  car passes. The gap is how much later the car passed the checkpoint it last passed,
  and grows while it does not reach your next one (turbohud/core/race.py blue_flag).
  Not yet checked in a race with other players.
- 2026-11-01: Light tint option, blue flag outline, steady player list (Linux). "Light
  tint behind the sections" (tray menu and move-mode panel, saved as backdrop, off by
  default): a faint dark box behind each section's text, only as large as the text (the
  pedal bars and the player list's right column included); in move mode the blue move
  tint replaces it. The blue flag now has a darker blue outline. The player list takes
  a new order only once it has lasted 0.3 s (race.Standings), so cars passing each
  other or a checkpoint written late do not make names jump back and forth; the gaps
  stay live.
- 2026-11-01: Section groups. In the move-mode panel each section can join group A, B,
  C or D (saved per section); dragging one section of a group moves the others by the
  same amount. TurboHUD looks where the sections are five times a second in move mode
  while groups exist (one hyprctl request for all of them on Hyprland), moves the rest
  with a single move request each, and once the drag stops places them fully again
  (workspace and pin, for a move to another monitor). Logic in hud.GroupMover. Ruff
  installed for the checks in its own tools environment, `.buildtools/ruff-venv`
  (ruff 0.17.3); new findings in the changed files fixed, older ones left.
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
