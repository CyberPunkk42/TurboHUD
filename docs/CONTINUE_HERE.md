# Continue here

Where the work stopped on 2026-11-05, on the Mac. Everything below was merged into `main`
and nothing was pushed or tagged. Delete a point when it is settled, and this file when
none is left.

## Not yet seen in a race
- Joining a public session mid-race (2026-11-08): a spectator's search now stops at the first race to
  watch, seen at 2.9 to 4.7 s (it took 15 to 21 s). Still to see: `has not run: searching past it` (an old
  race picked first), the HUD switching to the car with no search when the player drives the next race,
  and the 10 s waits for the first minute of empty searches while a race joined in progress is set up.
- The track map only in races (2026-11-08, backlog item 7): read the log's `event type:` line in a
  regular race and a special event (expected `TS.RaceEventMode`, with the map) and in King of the Hill
  or Sumo (no map).
- Race start online: the search reads half of the time instead of a quarter. As a driver the race was
  found 1.4 s after the start on 2026-11-08 (goal: 4 to 6 s, where it took 7 to 12 s). Still to listen
  for: stutter in the first seconds. A full-speed search made TSU stutter in earlier checks
  (`experiments/README.md`). If it stutters, go back with `WINE_SEARCH_SHARE` in
  `turbohud/tsu/winmemory.py`. If half speed is not fast enough: search from a better starting point,
  or look for a pointer path to the controller. One search measured apart at a quarter: 1.48 GiB in 608
  regions, the race at hit 42 of 42, at 18% of the data, 6 s in. Nearly all the other hits are not
  controllers at all (seen 2026-11-05 in a TSU's first event: tables and code bytes that hold the
  class's address), so they do not come from earlier races.
- A search at TSU's start: TSU's log can still say an event runs, from before TSU started, so
  TurboHUD searches for about 10 s with no event on (log: `search: no race` right after the
  reader starts). No longer harmful (see the entry of 2026-11-05 in `RESUME.md` on classes not
  yet set up), but needless; not fixed yet.
- The radar without its fill, its larger cars, and the two warning times in the settings
  window (blue flag 1 to 10 s, radar 0.2 to 3 s). A long radar time zooms the radar out.
- The settings window: it opens beside the move-mode panel and wholly on its screen (2026-11-08,
  it went past the right edge before), also with the panel dragged elsewhere; dragging it with a real
  mouse (tested only with a stand-in).

## Race start and the map, not yet seen
- Track map: a frame now comes with each new read (`hud.FramePacer`). The user found it smooth on
  2026-11-05, hosting with AI; the log's `HUD frames` lines had 0 or 1 frames with no new read in
  30 s. Not seen online as a client, where the other cars' positions come from the recorder.
- Pit stops: the user confirmed the timers, AI cars, tires, fuel, health and the pit entry on
  2026-11-05. Not tried: another tire compound (`tireCompoundAndChangeTicks` holds it too, how is
  not known; above 2400 the bar jumps at the end of the change, as before).

## Delta bar and radar option
The user confirmed both work on 2026-11-05. If the bar's colour ever flickers or lags, tune
`DELTA_TREND_WINDOW` and `DELTA_STEADY` in `turbohud/core/race.py`.

## Leader's lap, not yet seen in a race
See it lapped, also as a client, and when the leader finishes: whether the `/20` then still says
what the driver has left is not known.

## Tester's Mac
The tester's Mac: MacBook Pro 14" (M3 Pro), built-in screen 3024x1964 at 120 Hz, no second screen,
Fullscreen, D3DMetal, FPS read with the in-game / CrossOver HUD.

### FPS (2026-11-08, build 2026.11.08.2)
| # | TurboHUD | Old build (11-07) | 2026.11.08.2 |
| --- | --- | --- | --- |
| 1 | closed | 110 | 115 |
| 2 | every section unticked, 20 reads | 78 | 107 |
| 3 | every section unticked, 5 reads | - | ~100 (90-115) |
| 4 | lap and delta, 5 reads | - | ~90 (85-107) |
| 5 | lap and delta, 20 reads | 62 | ~95 (82-110) |
| 6 | all sections, 20 reads | 58 | ~63, steady near 60 |

- Unticked windows leaving the screen gave back most of the loss with nothing shown (78 to 107).
- The reads are not the cost: 5 a second was no better than 20. TurboHUD with nothing shown costs about 8
  FPS (the reader next to the game in the Wine server, or run-to-run noise).
- Windows above the game are: the more sections, the more frames miss the screen's 8.3 ms refresh, until
  nearly all do and the game holds near 60 (120 / 2) with all sections. Likely macOS compositing the game
  with the windows in step with the refresh, instead of showing it directly. Not known yet: whether the
  number of windows or their area matters more.
- In #5 a big stutter, then about 25 FPS less for 10 s; one read that run took 177 ms. Cause not known.
- The tester's log (19:54 to 20:01, measurements 5 and 6): 20 to 21 trips a read all along (the user's race
  with AI: about 88), so few or no other cars. With lap and delta a read took 17 to 19 ms (0.80 to 0.95 ms a
  trip); with all sections, the game near 60, 8 ms (0.40 ms a trip). The game leaves the Wine server more
  room when it waits for the refresh: the busy game slows the reads, not the reads the game. Once or twice
  in 30 s a read took 150 to 210 ms; whether those are the stutters felt (a game hitch also holds a read up)
  is not known, and #6 had such reads but no stutter. The reader's log was empty, as on the user's Mac.
- Still to get from the tester (nice to have): measurement 7 (closed again at the end), and whether
  `pgrep -fl bottle_reader` printed nothing.

### TODO: measure the windows' cost on the user's Mac with the Metal HUD
Apple's Metal Performance HUD (`MTL_HUD_ENABLED=1`, which D3DMetal honours) shows FPS and frame times
inside the game's own picture, adding no window above it. Nothing in the bottle or the system changes.
1. Quit TurboHUD, TSU and Steam in the bottle. `pgrep -fl 'steam.exe|TSU.exe|bottle_reader'` must print
   nothing (a Steam still running hands the start to itself, without the variable).
2. Start Steam in the bottle with the HUD, and leave that Terminal open:
   `MTL_HUD_ENABLED=1 ~/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine --bottle Steam "C:\\Program Files (x86)\\Steam\\steam.exe"`
3. Start TSU from that Steam; the HUD shows at the top right.
4. On one track, Fullscreen, about 30 s each: TurboHUD closed; running with every section unticked; only
   lap and time left; all sections; closed again. Note FPS, frame time, whether the frame-time graph jumps
   between about 8 and 17 ms, and any Direct / Composited line. If TSU reaches 120 alone, raise its
   graphics until it runs at about 100-110, as on the tester's Mac.
5. Afterwards quit everything; the next normal start has no HUD.
If no HUD shows: the user may add `"MTL_HUD_ENABLED" = "1"` under `[EnvironmentVariables]` in the bottle's
`cxbottle.conf` themselves, and remove it after (TurboHUD never writes there).
Then, with the same HUD: `experiments/qt_overlay_probe.py` with many small windows against one window
holding all sections, to see whether fewer windows would help before rebuilding the overlay.

### Other points
- Custom sessions show only the clock: no race is found in them. Not looked into: what such a session
  holds, and whether the HUD could read it.
- TSU hung on a black screen once, with TurboHUD quit first (2026-11-06). Not seen again: on the user's Mac
  (2026-11-08, quitting in either order) and on the tester's (2026-11-08, no reader left, TSU quit
  cleanly). Close it if it does not come back.
- The tester's Mac had two CrossOver copies; TurboHUD takes the one in `~/Applications` first, whichever
  TSU runs from (not fixed, did not stop the reader there).

## Test list: what is left
Done by the user on the Mac: all of the layout list (tight boxes, centring, groups, presets
with Ctrl+Shift+1, 2, 3, Undo), and on 2026-11-08 the bin button, an offline race with 19 AI
(lap times, fuel, tires, health, speed, pedals, map, radar, the player and lap times lists with
20 drivers, preset shortcuts mid-race), the same race in Fullscreen, and hosting about 13 AI
online as a driver.

1. Spectating, in public sessions (2026-11-08): "Spectating" shows and the map with it; a
   capture event (an arena mode) has no map. Still to see: joining as a driver brings the
   normal HUD with no search.
2. Later: a race on someone else's server, ideally 20 players. Hyprland: `--preset`, group
   resizing, Undo, the bin. Windows: none of this has run there, and live data is not built.

Ask the user to say when done before restarting TurboHUD: the log is replaced at each start.

## Smaller open points
- Stutter: settled on 2026-11-05, it was CrossOver's graphics setting. It stuttered alone on a
  server, without TurboHUD, with the keyboard and with the iPad's Sidecar screen off, and ran well
  once the bottle was on D3DMetal. Why the bottle was on the default is not known. Whether
  TurboHUD adds a little on D3DMetal has not been compared side by side.
- Text got smaller when the size stopped following the digits (draft most). The user's draft
  box is narrow: about 400 px wide gives it 23 px text, against 16 px now. Told to the user;
  they found the result "much better" afterwards, but may not have widened it.
- Offers not taken up yet: a leader-only blue flag; the settings window remembering where it
  was dragged; slots for other numbers (fuel and tires move by a digit at 100 to 99%).
- `releases/` holds only the latest build, 2026.11.08.2 (needs macOS 27): see backlog item 5 for what it
  needs before it runs on an older macOS.

## How the slow reads were found
Worth keeping for the next time the HUD lags. What fooled the first attempts: offscreen drawing
is far cheaper than real Mac windows, so benchmarks without real windows looked fine.
- Compare with a second connection: `Bottle().connect()` from a script reads the same race
  without the overlay. 28 ms there against 1030 ms in the app showed the app was the cause.
- Profile the real app in a real race: quit TurboHUD, run
  `.buildtools/venv/bin/python -B -m cProfile -o app.prof launch_turbohud.py`, race, then
  `run_turbohud.sh --quit` and read `app.prof`. It showed 122 of 207 s in `QPainter.fillPath`.
- The log's `race reads` line gives trips a read, ms a trip and how much of that is on the
  game's memory; `HUD frames` gives the overlay's side.

Run tests with `XDG_RUNTIME_DIR` set to an empty private folder and `QT_QPA_PLATFORM=offscreen`
(backlog item 1). On the Mac, the real app cannot start offscreen: `macos.py` needs real windows.
