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
  reads the race through a reader in the bottle (`turbohud/tsu/bottle.py`), with no setup;
  online AI races have run on it, while the race test list is still to do. On Windows it
  still shows a session clock and the local time. Start from the source with
  `run_turbohud.sh` / `run_turbohud.cmd`.
- Layout, in the move-mode panel: a text section's box fits closely round its text, three
  presets (Ctrl+Shift+1, 2, 3 load them; Linux: `--preset`), groups that move and resize
  together and can match their text size and width, Centre buttons for every section, and
  Centre text, and Undo. Checked by hand on the Mac.
- Builds: `tools/build_app.py` (PyInstaller) makes a Windows ZIP, a Mac app ZIP (with the
  reader and its Windows Python, 39 MB) and a Linux `.tar.gz`, run locally on each system.
  Nothing goes to GitHub any more; the old `.github/workflows/build.yml` is kept for
  reference only.
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
  `py -3 -B -m unittest discover -s tests`).
- Lint and format: `.buildtools/ruff-venv/bin/ruff check .` and `ruff format --check .`
  (Linux; a separate tools environment, never part of the app). Both pass.

## Next steps
**Start with `docs/CONTINUE_HERE.md`**: what is left to test. Then `docs/IMPROVEMENT_BACKLOG.md`. In short:
- First: the windows above the game cost the tester's Mac its frames (down to about 60 with all
  sections). Measure it on the user's Mac with the Metal HUD, then windows against one window
  (`docs/CONTINUE_HERE.md`, "Tester's Mac", TODO).
0. Tests: keep them from reaching a running TurboHUD (until then run them with
   `XDG_RUNTIME_DIR` set to an empty private folder).
1. Windows: the overlay over TSU (windowed, Fullscreen, Fullscreen Exclusive), then
   live data (reading memory as the same user, without a probe).
2. macOS: live data is connected; check it in races (offline and online), over
   Fullscreen, and listen for stutter while the race is searched for.
3. Layout: checked by hand on the Mac; what is left is in races, on Linux and on Windows
   (backlog item 4).
4. Builds and release: bundled apps with the probe, an AppImage; before the repository
   goes public, the privacy check, a licence and a README for players.
5. Linux: try TurboHUD on KDE or GNOME (it runs through XWayland there now).

## Recent changes
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
