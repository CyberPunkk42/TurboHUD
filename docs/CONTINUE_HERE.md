# Continue here

Where the work stopped on 2026-11-05, on the Mac. Everything below was merged into `main`
and nothing was pushed or tagged. Delete a point when it is settled, and this file when
none is left.

## Decision waiting for the user
**Race start online.** The HUD shows 7 to 12 s after an online race starts; this was the
user's complaint. Proposal, not yet answered:
1. Remove the "last place" shortcut (`LapReader._race_at_last_place` and
   `_last_controller` in `turbohud/core/race.py`, with its tests).
2. Set `WINE_SEARCH_SHARE` in `turbohud/tsu/winmemory.py` from 0.25 to 0.5. Expected: about
   4 to 6 s. Risk: a little stutter in the first seconds. Going back is one small change.

What is known:
- The shortcut does not work. The new race was `not where the last one was` in all three
  races logged after it went in. The equal hit counts (42) that suggested it were a coincidence
  of how many leftovers there are, not the same address.
- One search measured apart: 1.48 GiB in 608 regions, the race at hit 42 of 42, at 18% of
  the data, 6 s in. The other 41 hits are freed controllers of earlier races.
- A full-speed search was seen to make TSU stutter in earlier checks (`experiments/README.md`).
- If half speed is not enough: search from a better starting point (log where the race is
  relative to the data first), or look for a pointer path to the controller.

## Not yet seen in a race
- The radar without its fill, its larger cars, and the two warning times in the settings
  window (blue flag 1 to 10 s, radar 0.2 to 3 s). A long radar time zooms the radar out.
- Dragging the settings window with a real mouse (tested only with a stand-in).
- The race reads at 20 a second: the logged race ran at about 18 a second, 30 to 45 ms a read,
  with HUD frames 50 ms apart. Check `race reads` and `HUD frames` in `turbohud.log` again.

## Test list: what is left
Done by the user on the Mac: all of the layout list (tight boxes, centring, groups, presets
with Ctrl+Shift+1, 2, 3, Undo). AI races online ran many times while fixing the reads, but
the list below was not gone through.

1. Bin button: greyed out while empty; deleting leaves the sections where they are; Undo
   brings the preset back; still gone after a restart.
2. Offline race, 19 AI if the event allows: sections on the grid, lap times match the game's,
   fuel, tires, health and speed, pedal bars, track map and radar, players show 8 rows, lap
   times list all 20 drivers without overlapping what is below; preset shortcuts during the race
   (no hitch, the game does not react to the keys).
3. Same race in Fullscreen: sections over the game, clicks and steering reach it.
4. Online, hosting about 13 AI, as a driver: player list, gaps, map, radar.
5. Spectating: "Spectating" shows, lap times update, map dots follow the road, joining as a
   driver brings the normal HUD, what a fun mode shows. TSU may not allow spectating one's own
   AI event; then a public session.
6. Later: a race on someone else's server, ideally 20 players. Hyprland: `--preset`, group
   resizing, Undo, the bin. Windows: none of this has run there, and live data is not built.

The most valuable are 2 and 4. Ask the user to say when done before restarting TurboHUD: the
log is replaced at each start.

## Smaller open points
- Stutter with many AI: the user has "similar stutters" without TurboHUD, from memory, not a
  side-by-side test. Reads are not known to add to it, and now run more often, so listen for it.
- Text got smaller when the size stopped following the digits (draft most). The user's draft
  box is narrow: about 400 px wide gives it 23 px text, against 16 px now. Told to the user;
  they found the result "much better" afterwards, but may not have widened it.
- Offers not taken up yet: a leader-only blue flag; the settings window remembering where it
  was dragged; slots for other numbers (fuel and tires move by a digit at 100 to 99%).
- `releases/TurboHUD-dev-macos-arm64.zip` is older than all of this; rebuild it from `main`
  when wanted. Test with `run_turbohud.sh` until then.

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
