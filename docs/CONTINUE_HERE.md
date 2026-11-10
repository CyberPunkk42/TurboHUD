# Continue here

Where the work stopped on 2026-11-10, on the Mac. Everything below was merged into `main`
and nothing was pushed or tagged. Delete a point when it is settled, and this file when
none is left.

## Next session
1. The one-window HUD gave no gain that showed on 2026-11-10 ("One-window HUD and reads on the user's
   Mac" below), though it looks and works as before. To tell whether it helps at all: in one race, with the
   Metal HUD, a minute each of TurboHUD closed, every section shown, the same with
   `TURBOHUD_ONE_WINDOW=0 sh run_turbohud.sh`, one section shown in each of the two, and closed again.
2. Build 2026.11.09.2 went to the tester (2026-11-09) with the shorter `TurboHUD-test-instructions.md`. Put
   their results under "Tester's Mac": FPS without TurboHUD and with every section shown (63 before), the
   quick look, the log, whether a reader was left and whether TSU froze on quitting.
3. At each quit of TSU the user notes whether it froze and whether TurboHUD ran ("Other points").
4. When one comes up: a special event (map expected), King of the Hill or Sumo (no map), a track without
   sector lines (3 even sector bars expected), joining as a driver after spectating.
5. Online: two or more races in a session, for the search from the last race ("Not yet seen in a race");
   not possible on 2026-11-10.
6. Then a new build for the tester, with everything since 2026.11.09.2 (one-window HUD, batched reads,
   the kept map road, the sector bars by the track's sector lines).

Offered next (2026-11-10), most value first: the one-window canvas only as large as the sections; the
one-window canvas on Linux and Windows; sector times as numbers. Built from this list: race reads that
merge pages further apart, and online searches that begin where the last race was ("Not yet seen in a
race"). Windows and the CrossOver trial: `docs/WINDOWS_AND_CROSSOVER.md`.

The user likes a plain, numbered to-do list at each step, and merges each branch by saying "merge".
Run the tests only while TurboHUD is not running (`pgrep -fl launch_turbohud`), as one of them can
switch a running TurboHUD to move mode. The same goes for a build's `--smoke`: with TurboHUD running, the
built app only hands it "move" and quits, so the smoke test passes without starting the new app.

## Not yet seen in a race
- Race reads that merge pages further apart (2026-11-10), seen the same day in a race against AI (the log,
  20:38 to 20:41; the canvas was on): a read wants 69 to 89 pages lying across 305 to 406 MiB, and makes 31
  to 49 reads of the game for them (84 to 88 before, in a race that may have had more cars), with a median
  of 16 to 22 ms (26 to 29 before) and at most 2 reads in 30 s over 50 ms. A read of the game now costs
  about 0.45 ms (0.3 before), as it carries more. The pages lie in 30 to 50 groups far apart, so a larger
  `MERGE_GAP` would gain little: what is left is the price of a call, about 0.3 ms each. Fewer calls would
  need fewer pages (reading what seldom changes less often). Still to see: FPS with every section unticked
  against TurboHUD closed, which says whether the reads cost frames at all.
- Searches from where the last race was (2026-11-10, Mac): online, from the second race of a session on, the
  log should say `searching for the online race, from where the last one was`, then `race found (+… MiB
  from the last one), after … s`. Expected: found in under a second, with a distance near 0 or within some
  MiB. A distance below -32 MiB, or a search no quicker than the session's first, means TSU puts the next
  race elsewhere: then widen `SEARCH_BEFORE` in `turbohud/tsu/winmemory.py`, or drop the idea. Also as a
  spectator (`watching the race at hit … (… MiB from the last one)`), and listen for stutter as before.
- Race reads in one go (2026-11-09): seen on 2026-11-10, 1 trip a read, but the read is no shorter, as its
  84 to 88 reads of the game are the cost ("One-window HUD and reads on the user's Mac"). Still to see:
  the same line on the tester's Mac.
- The sector bars below the last and best lap (2026-11-09, by the track's sectors since 2026-11-10): one per
  sector, purple, green, dark yellow or grey. Seen by the user on 2026-11-10: 4 bars on a track with 3 sector
  lines (at 24, 45 and 58% of the lap), which they found fine as it is. Still to see: 3 bars on a track
  without sector lines, and online as a client, where the other drivers' checkpoint times come from the
  server a little late. TSU's own checkpoint-to-sector lists (`TS.Checkpoints.m_checkpointToSectorInfo`)
  held no sensible values in a race, so they are not read.
- The track map's Tint tick box (2026-11-09): unticked, only the road and the dots over the game, also
  while locked on the one-window canvas; ticked, the dark square as before.
- The last and best lap's colours (2026-11-09): purple for the race's fastest lap, green for a personal
  best short of it, white for a slower last lap. Online as a client the other drivers' lap times come from
  the server a little late, so a best lap may turn green a moment after their lap ends. The lap times
  list shows the fastest lap in purple, and the map's road is purple or green for 6 s after a fast lap
  (on the green road the green dot of the car behind stands out less).
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
- The settings window: dragging it with a real mouse (tested only with a stand-in). The panel and the
  settings window opening wholly on the screen were confirmed by the user on 2026-11-09.

## Race start and the map, not yet seen
- Track map: a frame now comes with each new read (`hud.FramePacer`). The user found it smooth on
  2026-11-05, hosting with AI; the log's `HUD frames` lines had 0 or 1 frames with no new read in
  30 s. Not seen online as a client, where the other cars' positions come from the recorder.
- Pit stops: the user confirmed the timers, AI cars, tires, fuel, health and the pit entry on
  2026-11-05. Not tried: another tire compound (`tireCompoundAndChangeTicks` holds it too, how is
  not known; above 2400 the bar jumps at the end of the change, as before).

## Delta bar and radar option
The user confirmed both work on 2026-11-05. On 2026-11-08 the bar was turned round (right when ahead,
as in sim racing) and its colour made gradual (white when steady, towards green or red as time is
gained or lost), asked for by the user as it flickered. Then, as it needed to be smoother: the delta
in hundredths (bar and delta section; the player list's gaps keep thousandths), the trend over 1 s,
and the colour easing over about 0.5 s. The user found it better and smooth enough in a race (2026-11-08).
To tune, if needed later, in `turbohud/core/race.py`:
`DELTA_STEADY` (white up to this rate, 0.02 s a second), `DELTA_RATE_FULL` (full colour, 0.15 s a
second), `DELTA_TREND_WINDOW` (1 s) and `DELTA_COLOUR_EASE` (0.5 s).

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

### CPU per section on the user's Mac (2026-11-09)
Recorded with `top` every 2 s during a race against AI, matched with the log's tick changes; one
section shown at a time (the screen at "more space": 2056 x 1329 for Qt). Averages, 100 = one core:

| Shown | WindowServer | TurboHUD |
| --- | --- | --- |
| TurboHUD closed (perhaps not racing yet) | 41 | - |
| nothing | 42 | 7 |
| local time (changes once a minute) | 48 | 9 |
| running lap (20 times a second) | 48 | 10 |
| track map | 49 | 23 |
| any other single section | 48 to 49 | 9 to 17 |

Each window adds about the same to WindowServer, whatever it shows and however often it changes: a
window's being there costs, not its redraws. So drawing some sections less often would not help; all
sections in one window might. CPU is not FPS: the Metal HUD below is to confirm it in frames. TSU's
own CPU was 243 before TurboHUD started and about 360 after, but the user was probably not racing yet.

### FPS on the user's Mac with the Metal HUD (2026-11-09)
Apple's Metal Performance HUD (`MTL_HUD_ENABLED=1`, which D3DMetal honours) shows FPS inside the game's
own picture, adding no window above it; nothing in the bottle or the system changes. How to start it:
quit TurboHUD, TSU and Steam in the bottle (`pgrep -fl 'steam.exe|TSU.exe|bottle_reader'` must print
nothing, or the running Steam takes the start without the variable), then, leaving that Terminal open:
`MTL_HUD_ENABLED=1 ~/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine --bottle Steam "C:\\Program Files (x86)\\Steam\\steam.exe"`,
and start TSU from that Steam. If no HUD shows, the user may add `"MTL_HUD_ENABLED" = "1"` under
`[EnvironmentVariables]` in the bottle's `cxbottle.conf` themselves, and remove it after.

In a race against AI on the 120 Hz built-in screen:

| TurboHUD | FPS |
| --- | --- |
| closed | 120 (the screen's most) |
| running, only the local time shown | 120 |
| running, every section shown | 80 to 110, unsteady |

One window costs nothing that shows here; all 17 cost 10 to 40 FPS. With the CPU recording above, the
number of windows is what costs, not what they show. TSU has room to spare on this Mac, so the cost shows
only with many windows; on the tester's it shows sooner. Not measured: every section hidden, and closed
again at the end (TSU froze then, see below).

The probe (`experiments/window_count_probe.py`, 2026-11-09, the user's layout, one large window
nearly the whole screen): nothing 120 FPS, 17 windows 85, one window 115, nothing again 120. So the
number of windows costs, not their area.

Built the same day (backlog item 3): locked, on the Mac, every section is drawn in one window per screen
(`HudCanvas` in `turbohud/overlay/window.py`); move mode keeps a window per section. Not yet seen over
TSU. To check: the Metal HUD with every section shown (expected near 115 to 120, from 80 to 110); move
mode as before (drag, resize, groups, Undo); while locked, a preset shortcut and "bigger"/"smaller" in
the settings moving the sections with nothing left behind; the tint and the theme; the map and the
radar. If anything is wrong, `TURBOHUD_ONE_WINDOW=0 sh run_turbohud.sh` goes back to a window each.

### One-window HUD and reads on the user's Mac (2026-11-10)
A race against AI with the Metal HUD, read by eye by the user; `main` with the one-window HUD:

| TurboHUD | FPS |
| --- | --- |
| closed | 85 to 120 |
| every section unticked | 100 and more, all the time |
| one section shown, each in turn | about 80, from below 70 to 120 |
| every section shown | about 85 (70 to 100) |

- Closed was 120 all the time on 2026-11-09 and 85 to 120 now, so this race was heavier for TSU and the
  numbers do not compare with that day's. Within this race: showing anything costs about 15 to 20 FPS, one
  section as much as all, and nothing shown costs little or nothing. On 2026-11-09 one section cost
  nothing. Not known: whether the canvas was on (the log's `canvas:` line was not copied), and whether a
  canvas the size of the screen costs when one small part of it changes 20 times a second (the probe's one
  large window lost 5 FPS). The comparison in "Next session", point 1, is to tell.
- It looked as before, and move mode, the preset shortcuts and "bigger"/"smaller" worked.
- The track map's kept road: TurboHUD's CPU with only the map shown was 8.2 to 8.8% of a core (about 23%
  before).
- The log (20:13 to 20:17): 1 trip a read, as meant, but a median read of 26.5 to 29.3 ms, 25 to 28 ms of
  it on the game's memory in 84 to 88 reads of it, so about 0.3 ms each: the number of reads of the game is
  the whole cost, and the reader spends about half of its time in them (a read every 54 ms). One to three
  reads in 30 s took over 50 ms (95 to 141 ms). So merging pages further apart ("Offered next") is the
  next step for the reads. HUD frames: content 2% and drawing 16 to 19% of the time.
- TSU quit normally, with TurboHUD quit first and Steam started from Terminal with the Metal HUD.
- No online race could be driven, so the search from the last race is not seen yet.

### Other points
- Custom sessions show only the clock: no race is found in them. Not looked into: what such a session
  holds, and whether the HUD could read it.
- TSU freezing when it is quit. Seen twice, each time with TurboHUD quit first:

  | When | TurboHUD | Steam started | TSU |
  | --- | --- | --- | --- |
  | tester, 2026-11-06 | quit first | normally | froze on a black screen (Steam's Stop) |
  | user, 2026-11-08, twice | quit first, and TSU first | normally | quit normally |
  | tester, 2026-11-08 | quit first | normally | quit cleanly, no reader left |
  | user, 2026-11-09, 01:10 | quit first (reader ended at once) | from Terminal, Metal HUD | froze, between the race and quitting |
  | user, 2026-11-10 | quit first | from Terminal, Metal HUD | quit normally |

  When frozen: TSU at about 1% CPU (about 300% while running), steam.exe at about 100%, no reader left.
  The reader opens TSU only to read memory and ask for its layout (`PROCESS_VM_READ`,
  `PROCESS_QUERY_LIMITED_INFORMATION`), pausing, attaching to or changing nothing; it ends within a
  second. So no way in the code for it to freeze TSU is known. To tell: the user notes, at each quit of
  TSU, whether it froze and whether TurboHUD ran; and one session with TurboHUD never started.
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
- `releases/` holds only the latest build, 2026.11.09.2 (needs macOS 27): see backlog item 5 for what it
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
