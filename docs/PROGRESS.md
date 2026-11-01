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
