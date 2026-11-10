# TurboHUD: test for the Mac, step by step

Nov 10, 2026 · build 2026.11.10 · about 25 minutes

Thank you for testing again. This build reads the race about twice as fast as before, with a new reader inside CrossOver. This test checks that it works on your Mac, and measures which of two ways of drawing TurboHUD costs TSU fewer frames.

Go through it from top to bottom. Every step is one thing to do. Where it says **✏️ Write down**, fill in the answer on this sheet.

TurboHUD only reads what the game shows. It changes nothing in TSU or in CrossOver.

---

## Part 1: Get ready (2 minutes)

You need:

- [ ] The file `TurboHUD-2026.11.10-macos-arm64.dmg`
- [ ] TSU in CrossOver, as last time
- [ ] The same way of reading TSU's FPS as last time
- [ ] The Terminal app (in **Applications > Utilities**)

Pick one track and one car, and use them for every step. Keep TSU in **Fullscreen**, as last time. Race against AI, offline, so every measurement has the same cars.

**✏️ Write down:** Did anything change since last time (Mac, screen, TSU's graphics settings)? ______

---

## Part 2: Install the new TurboHUD (3 minutes)

1. If TurboHUD is running, quit it: press **Control + Shift + Q**.
2. Double-click `TurboHUD-2026.11.10-macos-arm64.dmg`. A window opens.
3. Drag **TurboHUD** onto **Applications**. If asked, choose **Replace**.
4. Close the window. In Finder, click the eject button next to **TurboHUD** in the sidebar.
5. **Don't open TurboHUD yet.** The first measurement is without it.

Your layout and settings from last time stay.

---

## Part 3: Measure the frame rate (5 measurements, about 12 minutes)

Each measurement is the same:

> Drive for **about one minute**, then write down the **average FPS** and whether anything stuttered.

Stay in the same race for all five if you can.

### Shortcuts you'll need

| To do this | Press |
| --- | --- |
| Open or close move mode (where the tick boxes are) | **Control + Shift + L** |
| Quit TurboHUD | **Control + Shift + Q** |

Always close move mode (**Control + Shift + L**) before you drive.

### Measurement 1: without TurboHUD

1. Make sure TurboHUD is **not** running.
2. Start TSU and start a race against AI on your track.
3. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

### Measurement 2: everything shown

1. Open **Applications** and double-click **TurboHUD**.
   - If macOS says it "could not verify" TurboHUD, see **Help** at the end, then come back here.
2. Wait until the lap and the times show on the screen.
3. Press **Control + Shift + L**. **Tick every box in the "Show" column.** Press **Control + Shift + L** again.
4. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

### Measurement 3: only the local time

1. Press **Control + Shift + L**. **Untick every box except "Local time".** Press **Control + Shift + L** again.
2. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

### Measurement 4: the other way of drawing, everything shown

1. Press **Control + Shift + Q** to quit TurboHUD.
2. Open **Terminal**, paste this, and press **Return**. Leave Terminal open:

   ```
   TURBOHUD_ONE_WINDOW=0 /Applications/TurboHUD.app/Contents/MacOS/TurboHUD
   ```

3. Wait until the lap and the times show. Press **Control + Shift + L**, **tick every box in the "Show" column**, and press **Control + Shift + L** again.
4. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

### Measurement 5: the other way of drawing, only the local time

1. Press **Control + Shift + L**. **Untick every box except "Local time".** Press **Control + Shift + L** again.
2. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

**Stay in the race and go to Part 4.**

---

## Part 4: A quick look (2 minutes)

1. Press **Control + Shift + L** and tick every box in the "Show" column again, then press **Control + Shift + L**.
2. Keep driving and look at TurboHUD. Is everything there and updating (lap, times, the bars, the track map, the radar)?

**✏️ Write down:** ______

---

## Part 5: Copy TurboHUD's log (2 minutes)

TurboHUD keeps a log, and it's replaced each time TurboHUD starts. So copy it now, while TurboHUD is still running.

1. In Terminal, press **Command + N** for a new window.
2. Copy all the lines in the box below, paste them into the new window, and press **Return**:

```
T=~/Library/Application\ Support/TurboHUD
echo "--- version"; grep -m1 'TurboHUD 2026' "$T/turbohud.log"
echo "--- reader"; grep -E 'reading TSU through|canvas' "$T/turbohud.log" | head -5
echo "--- reads"; grep -E 'race reads|race pages|search:|connection dropped' "$T/turbohud.log" | tail -20
echo "--- reader errors"; tail -20 "$T/bottle_reader.log"
```

3. Select all the text Terminal printed, copy it, and save it in a note or an email to send back.

This only reads information and changes nothing. It may include player names and your Mac's user name: look it over before you send it.

---

## Part 6: Quit (3 minutes)

This checks that nothing is left running and that TSU quits normally.

1. Press **Control + Shift + Q** to quit TurboHUD.
2. In Terminal, paste this and press **Return**:

   ```
   pgrep -fl 'turbohud-reader|bottle_reader'
   ```

3. Wait 5 seconds, then press **↑** (up arrow) and **Return** to run it again.

**✏️ Write down:** Did either run print anything? If yes, what? ______

4. Quit TSU the normal way, from its menu.

**✏️ Write down:** Did TSU quit normally, or freeze? ______

If TSU freezes: quit it with **Stop** in Steam, as last time.

---

## What to send back

- [ ] This sheet with everything you wrote down (or just the answers)
- [ ] The Terminal text from Part 5

### Summary (copy your answers here)

| # | What | Answer |
| --- | --- | --- |
| 1 | FPS without TurboHUD | |
| 2 | FPS, everything shown | |
| 3 | FPS, only the local time | |
| 4 | FPS, other way, everything shown | |
| 5 | FPS, other way, only the local time | |
| | Stutter in any of them? Which? | |
| | Everything there and updating? | |
| | Anything left after quitting TurboHUD? | |
| | TSU quit normally? | |

---

## Help

**macOS says it "could not verify" TurboHUD**

1. Click **Done** (not Move to Trash).
2. Open **System Settings > Privacy & Security**.
3. Scroll down to **Security** and click **Open Anyway** next to TurboHUD.
4. Enter your password and click **Open Anyway** again.

This happens because the test version isn't signed with a paid Apple certificate. Only open it if you trust the person who sent it.

If there's no **Open Anyway** button, paste this into Terminal, press **Return**, and try again:

```
xattr -dr com.apple.quarantine /Applications/TurboHUD.app
```

**Other problems**

Hover the mouse over TurboHUD's black icon in the menu bar: its text says what TurboHUD is waiting for.

| What you see | What to do |
| --- | --- |
| No window, no Dock icon after starting TurboHUD | That's normal. Look for its black icon in the menu bar. |
| Only a clock, in a menu, lobby or custom session | That's normal: there's no race to read. Start a real race. |
| Only a clock, during a race | Wait a minute. If nothing changes, try the old reader (below), and tell us. |
| A warning that the graphics setting is not D3DMetal | In CrossOver, set the bottle's graphics to **D3DMetal**, restart TSU, and tell us you changed it. |
| TurboHUD won't open | Do the **Open Anyway** steps above again. |

To try the old reader, quit TurboHUD, then paste this into Terminal and press **Return**:

```
TURBOHUD_PY_READER=1 /Applications/TurboHUD.app/Contents/MacOS/TurboHUD
```

**Removing TurboHUD:** quit it and move it from Applications to the Bin. Its settings and logs are in `~/Library/Application Support/TurboHUD`.
