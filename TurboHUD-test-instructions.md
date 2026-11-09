# TurboHUD: test for the Mac, step by step

Nov 9, 2026 · build 2026.11.09 · about 20 minutes

Thank you for testing again. Last time, with every section shown, TSU dropped from about 115 FPS to about 63. This build draws all of TurboHUD in one window instead of one window per section, which should give most of those frames back. This test checks that, and that TSU still quits normally.

Go through it from top to bottom. Every step is one thing to do. Where it says **✏️ Write down**, fill in the answer on this sheet.

TurboHUD only reads what the game shows. It changes nothing in TSU or in CrossOver.

---

## Part 1: Get ready (2 minutes)

You need:

- [ ] The file `TurboHUD-2026.11.09-macos-arm64.dmg`
- [ ] TSU in CrossOver, as last time
- [ ] The same way of reading TSU's FPS as last time
- [ ] The Terminal app (in **Applications > Utilities**)

Pick one track and one car, and use them for every step. Keep TSU in **Fullscreen**, as last time. If you can, use the same track as last time.

**✏️ Write down:** Did anything change since last time (Mac, screen, second screen, TSU's graphics settings)? ______

---

## Part 2: Install the new TurboHUD (3 minutes)

1. If TurboHUD is running, quit it: press **Control + Shift + Q**.
2. Double-click `TurboHUD-2026.11.09-macos-arm64.dmg`. A window opens.
3. Drag **TurboHUD** onto **Applications**. If asked, choose **Replace**.
4. Close the window. In Finder, click the eject button next to **TurboHUD** in the sidebar.
5. **Don't open TurboHUD yet.** The first measurement is without it.

Your layout and settings from last time stay.

---

## Part 3: Measure the frame rate (2 measurements, about 5 minutes)

Each measurement is the same:

> Drive for **about one minute** on your track, then write down the **average FPS** and whether anything stuttered.

### Shortcuts you'll need

| To do this | Press |
| --- | --- |
| Open or close move mode (where the tick boxes are) | **Control + Shift + L** |
| Quit TurboHUD | **Control + Shift + Q** |

Always close move mode (**Control + Shift + L**) before you drive.

### Measurement 1: without TurboHUD

1. Make sure TurboHUD is **not** running.
2. Start TSU and start a race on your track.
3. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

### Measurement 2: TurboHUD with everything shown

1. Stay in the race (or start a new one on the same track).
2. Open **Applications** and double-click **TurboHUD**.
   - If macOS says it "could not verify" TurboHUD, see **Help** at the end, then come back here.
3. Wait until the lap and the times show on the screen. This can take up to a minute.
4. Press **Control + Shift + L**. The panel appears.
5. Click **Settings…**. Next to **Race reads a second**, check that **20** is selected (click it if not). Click **Close**.
6. **Tick every "Show …" box.**
7. Press **Control + Shift + L** to close move mode.
8. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

**Stay in the race and go to Part 4.**

---

## Part 4: A quick look (3 minutes)

Keep driving and look at TurboHUD. You don't need to measure anything.

1. Does everything look as it did last time (text, the bars, the track map, the radar)?
   **✏️ Write down:** ______
2. Below **Last** and **Best** there is now a row of small bars, one for each part of the lap. They turn purple, green or dark yellow as you drive. Do they?
   **✏️ Write down:** ______
3. Press **Control + Shift + L**, drag one section to another place, then press **Control + Shift + L** again. Is the section in its new place, with nothing left behind where it was?
   **✏️ Write down:** ______

---

## Part 5: Copy TurboHUD's log (2 minutes)

TurboHUD keeps a log, and it's replaced each time TurboHUD starts. So copy it now, while TurboHUD is still running.

1. Open **Terminal**.
2. Copy all the lines in the box below, paste them into Terminal, and press **Return**:

```
T=~/Library/Application\ Support/TurboHUD
echo "--- version"; grep -m1 'TurboHUD 2026' "$T/turbohud.log"
echo "--- canvas"; grep -m3 -i 'canvas' "$T/turbohud.log"
echo "--- reads and frames"; grep -E 'race reads|HUD frames|search:|connection dropped' "$T/turbohud.log" | tail -30
echo "--- reader"; tail -20 "$T/bottle_reader.log"
```

3. Select all the text Terminal printed, copy it, and save it in a note or an email to send back.

This only reads information and changes nothing. It may include player names and your Mac's user name: look it over before you send it.

---

## Part 6: Quit (3 minutes)

This checks that nothing is left running and that TSU quits normally.

1. Press **Control + Shift + Q** to quit TurboHUD.
2. In Terminal, paste this and press **Return**:

   ```
   pgrep -fl bottle_reader
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
| 2 | FPS with everything shown | |
| | Stutter in 1 or 2? | |
| | Looks as before? | |
| | Sector bars colour in? | |
| | Section moved cleanly? | |
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
| Only a clock, during a race | Wait a minute. If nothing changes, do Part 5 and send the text. |
| A warning that the graphics setting is not D3DMetal | In CrossOver, set the bottle's graphics to **D3DMetal**, restart TSU, and tell us you changed it. |
| Something looks wrong after the update | Quit TurboHUD, then start it with the command below. It goes back to one window per section. Tell us what you saw. |
| TurboHUD won't open | Do the **Open Anyway** steps above again. |

```
TURBOHUD_ONE_WINDOW=0 /Applications/TurboHUD.app/Contents/MacOS/TurboHUD
```

**Removing TurboHUD:** quit it and move it from Applications to the Bin. Its settings and logs are in `~/Library/Application Support/TurboHUD`.
