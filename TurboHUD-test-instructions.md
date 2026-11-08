# TurboHUD: test for the Mac, step by step

Nov 8, 2026 · build 2026.11.08.2 · about 30 minutes

Thank you for testing again. Last time, TSU ran at about 110 FPS without TurboHUD and about 58 FPS with it. This test finds out which part of TurboHUD costs the frames. You don't need to understand any of it: just do the steps in order and write down the numbers.

Go through it from top to bottom. Every step is one thing to do. Where it says **✏️ Write down**, fill in the answer on this sheet.

TurboHUD only reads what the game shows. It changes nothing in TSU or in CrossOver.

---

## Part 1: Get ready (5 minutes)

You need:

- [ ] The file `TurboHUD-2026.11.08.2-macos-arm64.dmg`
- [ ] TSU in CrossOver, as last time
- [ ] The same way of reading TSU's FPS as last time
- [ ] The Terminal app (in **Applications > Utilities**)

**✏️ Write down before you start:**

| Question | Your answer |
| --- | --- |
| Is a second screen connected to the Mac (another monitor, a TV, or an iPad used as a screen)? | |
| If yes: which screen does TSU run on? | |
| Was a second screen connected during your last test too? | |
| Did anything else change since last time (Mac, screen, TSU's graphics settings)? | |

Pick one track and one car, and use them for every step. Keep TSU in **Fullscreen**, as last time.

---

## Part 2: Install the new TurboHUD (5 minutes)

1. If TurboHUD is running, quit it: press **Control + Shift + Q**.
2. Double-click `TurboHUD-2026.11.08.2-macos-arm64.dmg`. A window opens.
3. Drag **TurboHUD** onto **Applications**. If asked, choose **Replace**.
4. Close the window. In Finder, click the eject button next to **TurboHUD** in the sidebar.
5. **Don't open TurboHUD yet.** The first measurement is without it.

Your layout and settings from last time stay.

---

## Part 3: Measure the frame rate (7 measurements, about 15 minutes)

Each measurement is the same:

> Drive for **about one minute** on your track, then write down the **average FPS** and whether anything stuttered.

Do them in this order. Don't skip ahead.

### Shortcuts you'll need

| To do this | Press |
| --- | --- |
| Open or close move mode (where the tick boxes are) | **Control + Shift + L** |
| Quit TurboHUD | **Control + Shift + Q** |

In move mode, a panel with tick boxes appears. Each box is called **Show** and then the section's name, for example **Show lap and time left**. The panel also has a **Settings…** button.

Always close move mode (**Control + Shift + L**) before you drive.

---

### Measurement 1: without TurboHUD

1. Make sure TurboHUD is **not** running.
2. Start TSU and start a race on your track.
3. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

---

### Measurement 2: TurboHUD on, everything hidden

1. Stay in the race (or start a new one on the same track).
2. Open **Applications** and double-click **TurboHUD**.
   - If macOS says it "could not verify" TurboHUD, see **Help** at the end, then come back here.
3. Wait until the lap and the times show on the screen. This can take up to a minute.
4. Press **Control + Shift + L**. The panel appears.
5. Click **Settings…**. Next to **Race reads a second**, check that **20** is selected (click it if not). Click **Close**.
6. In the panel, **untick every "Show …" box**, including **Show local time**. Nothing of TurboHUD should be left on the screen except the panel.
7. Press **Control + Shift + L** to close move mode.
8. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

---

### Measurement 3: everything hidden, fewer reads

1. Press **Control + Shift + L**.
2. Click **Settings…**, click **5** next to **Race reads a second**, then click **Close**.
3. Press **Control + Shift + L** to close move mode.
4. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

---

### Measurement 4: lap and delta only, fewer reads

1. Press **Control + Shift + L**.
2. Tick **Show lap and time left** and **Show delta to best**. Leave all other boxes unticked.
3. Press **Control + Shift + L** to close move mode.
4. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

---

### Measurement 5: lap and delta only, normal reads

1. Press **Control + Shift + L**.
2. Click **Settings…**, click **20** next to **Race reads a second**, then click **Close**.
3. Press **Control + Shift + L** to close move mode.
4. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

---

### Measurement 6: everything shown

1. Press **Control + Shift + L**.
2. **Tick every "Show …" box.**
3. Press **Control + Shift + L** to close move mode.
4. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

**Stay in the race now and go to Part 4.** Don't quit or restart TurboHUD yet.

---

## Part 4: Copy TurboHUD's log (2 minutes)

TurboHUD keeps a log, and it's replaced each time TurboHUD starts. So copy it now, while TurboHUD is still running.

1. Open **Terminal**.
2. Copy all the lines in the box below, paste them into Terminal, and press **Return**:

```
T=~/Library/Application\ Support/TurboHUD
echo "--- version"; grep -m1 'TurboHUD 2026' "$T/turbohud.log"
echo "--- reads and frames"; grep -E 'race reads|HUD frames|search:|connection dropped' "$T/turbohud.log" | tail -30
echo "--- reader"; tail -20 "$T/bottle_reader.log"
echo "--- graphics"; grep -h CX_GRAPHICS_BACKEND ~/Library/Application\ Support/CrossOver/Bottles/Steam/cxbottle.conf
echo "--- screens"; system_profiler SPDisplaysDataType | grep -E 'Chipset|Resolution|UI Looks|Main Display'
```

3. Select all the text Terminal printed, copy it, and save it in a note or an email to send back.

This only reads information and changes nothing. It may include player names and your Mac's user name: look it over before you send it.

(If TSU is in a CrossOver bottle with a name other than **Steam**, change the word `Steam` in the fourth line to your bottle's name.)

---

## Part 5: Quit, and the last measurement (3 minutes)

Last time, TSU froze on a black screen after TurboHUD was quit. This part checks that.

1. Press **Control + Shift + Q** to quit TurboHUD.
2. In Terminal, paste this and press **Return**:

   ```
   pgrep -fl bottle_reader
   ```

3. Wait 5 seconds, then press **↑** (up arrow) and **Return** to run it again.

**✏️ Write down:** Did either run print anything? If yes, what? ______

### Measurement 7: without TurboHUD again

This checks whether the Mac got slower because it warmed up.

1. TurboHUD is now closed. Stay in the race, or start a new one on the same track.
2. Drive for one minute.

**✏️ Write down:** FPS: ______ Stutter? ______

### Quit TSU

1. Quit TSU the normal way, from its menu.

**✏️ Write down:** Did TSU quit normally, or freeze? ______

If TSU freezes: quit it with **Stop** in Steam, as last time. Then, only if you have time: start TSU **without** TurboHUD, do one race, quit TSU again, and write down whether it froze that time too. ______

---

## Part 6 (only with a second screen, optional, 3 minutes)

Skip this part if no second screen is connected.

1. Unplug the second screen, or turn off the iPad's screen.
2. Do **Measurement 1** again (without TurboHUD).
   **✏️ Write down:** FPS: ______
3. Start TurboHUD from Applications, wait for the lap to show, and do **Measurement 6** again (everything shown).
   **✏️ Write down:** FPS: ______
4. Quit TurboHUD with **Control + Shift + Q**.

---

## Part 7: Put things back (1 minute)

Next time you use TurboHUD:

1. Press **Control + Shift + L**, click **Settings…**, and make sure **20** is selected next to **Race reads a second**.
2. Tick the sections you like to use, then press **Control + Shift + L**.

TurboHUD remembers both.

---

## What to send back

- [ ] This sheet with everything you wrote down (or just the answers)
- [ ] The Terminal text from Part 4
- [ ] How you read the FPS, if it wasn't the same way as last time

### Summary table (copy your numbers here)

| # | Setup | FPS | Stutter? |
| --- | --- | --- | --- |
| 1 | No TurboHUD | | |
| 2 | TurboHUD, everything hidden, 20 reads | | |
| 3 | TurboHUD, everything hidden, 5 reads | | |
| 4 | Lap and delta, 5 reads | | |
| 5 | Lap and delta, 20 reads | | |
| 6 | Everything shown, 20 reads | | |
| 7 | No TurboHUD again | | |
| 1b | No TurboHUD, second screen off (optional) | | |
| 6b | Everything shown, second screen off (optional) | | |

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
| Only a clock, during a race | Wait a minute. If nothing changes, do Part 4 and send the text. |
| A warning that the graphics setting is not D3DMetal | In CrossOver, set the bottle's graphics to **D3DMetal**, restart TSU, and tell us you changed it. |
| Can't tell which bottle TSU runs in | Quit TurboHUD and start it with the command below, using your bottle's name instead of `Steam`. |
| TurboHUD won't open | Do the **Open Anyway** steps above again. |

```
TURBOHUD_BOTTLE=Steam /Applications/TurboHUD.app/Contents/MacOS/TurboHUD
```

**Removing TurboHUD:** quit it and move it from Applications to the Bin. Its settings and logs are in `~/Library/Application Support/TurboHUD`.
