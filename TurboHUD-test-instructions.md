# TurboHUD: test instructions for the Mac

Nov 8, 2026

## What this test is for

Your last test showed TSU dropping from about 110 FPS to 78 FPS with TurboHUD running and every section unticked, and to 58 FPS with all sections. So most of the cost comes before TurboHUD shows anything. This version changes two things, so we can tell where the cost comes from:

- An unticked section now leaves the screen completely. Before, its empty window stayed above the game.
- The settings window has a new setting, **Race reads a second**: 20, 10 or 5. It sets how often TurboHUD reads the race from TSU. 20 is the default.

The test takes about 20 minutes, and each measurement takes about a minute. There is also a short test at the end about TSU hanging on exit.

You need:

- A Mac with Apple silicon and macOS 27.0 or newer
- TSU running in CrossOver
- The file `TurboHUD-2026.11.08-macos-arm64.dmg`
- A way to read TSU's FPS, the same one as last time

TurboHUD only reads what the game shows. It changes nothing in TSU or in its CrossOver bottle.

## Install the new version

This version replaces the one you have, and your layout and settings stay.

1. Quit TurboHUD: press **Control + Shift + Q**, or use **Quit** in its menu bar icon's menu.
2. Double-click the `.dmg` file. A window opens.
3. Drag **TurboHUD** onto **Applications**, and choose **Replace** when asked.
4. Eject the disk image.
5. Double-click TurboHUD in Applications.
6. If macOS says it "could not verify" TurboHUD, click **Done**, not Move to Trash. Then open **System Settings > Privacy & Security**, scroll to **Security**, and click **Open Anyway** next to TurboHUD. Enter your password and click **Open Anyway** again.

This prompt appears because the test version is not signed with a paid Apple certificate. Only open it if you trust the person who sent it.

If there is no **Open Anyway** button, run this in Terminal, then try again:

```
xattr -dr com.apple.quarantine /Applications/TurboHUD.app
```

TurboHUD opens no window and has no Dock icon. Look for its black icon in the menu bar and a small clock at the top left of the screen.

## How to change the setup between steps

- **Tick or untick sections:** press **Control + Shift + L** for move mode, change the tick boxes, then press **Control + Shift + L** again.
- **Change the race reads:** in move mode, click **Settings…** in the panel. Click **20**, **10** or **5** next to **Race reads a second**. The change applies at once. Click **Close**, then press **Control + Shift + L** to leave move mode.
- **Quit TurboHUD:** press **Control + Shift + Q**.

Close the settings window and leave move mode before you measure, because both are windows above the game.

## Run the frame rate test

Run every step in a **real race**, on the same track with the same car and the same graphics settings, with TSU in Fullscreen as last time. A custom session has no race for TurboHUD to read, so only the clock shows there.

Drive for about a minute at each step, then write down the average FPS. The steps are in an order that keeps the switching short.

| Step | TurboHUD | Sections ticked | Race reads a second | Average FPS | Any stutter? |
| --- | --- | --- | --- | --- | --- |
| 1 | Not running | – | – |  |  |
| 2 | Running | None | 20 |  |  |
| 3 | Running | None | 5 |  |  |
| 4 | Running | Only lap and delta | 5 |  |  |
| 5 | Running | Only lap and delta | 20 |  |  |
| 6 | Running | All | 20 |  |  |
| 7 | Not running | – | – |  |  |

Step 7 repeats step 1, in case the Mac has warmed up and runs slower by the end. For step 7, quit TurboHUD the way the hang test below describes, and write down what happens.

"None" means every section unticked, the clock and the local time too. For step 1, start the race with TurboHUD not running. For step 2, start TurboHUD while you are in the race. It may take up to a minute to find the race. Wait until the lap section shows before you untick everything, and drive the minute after that.

After step 6, stay in the race and run the command in **What to send back** before you quit TurboHUD.

## Test TSU hanging on exit

Last time TSU hung on a black screen after TurboHUD was quit first. Do this after you run the command in **What to send back**:

1. Quit TurboHUD with **Control + Shift + Q**.
2. In Terminal, run this, wait 5 seconds, and run it again:

   ```
   pgrep -fl bottle_reader
   ```

   Note what each run prints. Nothing printed means no TurboHUD reader is left running.
3. Do step 7 of the frame rate test.
4. Quit TSU the normal way, from its menu.
5. Write down whether TSU quits normally or hangs.

If TSU hangs, quit it with Steam's **Stop** as before. Then, if you have time, start TSU with TurboHUD **not running**, do one race, and quit TSU. Write down whether it hangs then too. That tells us whether TurboHUD causes the hang at all.

## What to send back

Send the filled-in table, the results of the hang test, and the output of the Terminal command below.

- Whether anything about the Mac, the screen or TSU's settings changed since last time. Last time you sent: MacBook Pro M3 Pro, 120 Hz, Fullscreen, D3DMetal.
- How you measured FPS, if it was not the same way as last time

Run this while you are still in the race at step 6, **before you quit or restart TurboHUD**, because each start replaces its log. It only reads information and changes nothing:

```
T=~/Library/Application\ Support/TurboHUD
echo "--- version"; grep -m1 'TurboHUD 2026' "$T/turbohud.log"
echo "--- reads and frames"; grep -E 'race reads|HUD frames|search:' "$T/turbohud.log" | tail -30
echo "--- reader"; tail -20 "$T/bottle_reader.log"
echo "--- graphics"; grep -h CX_GRAPHICS_BACKEND ~/Library/Application\ Support/CrossOver/Bottles/Steam/cxbottle.conf
echo "--- screens"; system_profiler SPDisplaysDataType | grep -E 'Chipset|Resolution|UI Looks|Main Display'
```

The command assumes TSU is in a bottle called `Steam`. If yours has another name, change that word. The output can include player names and your Mac's user name, so look it over before you send it.

When you are done, set **Race reads a second** back to **20** and tick the sections you use. TurboHUD remembers both.

## If something goes wrong

Hover over the TurboHUD menu bar icon first, because its text says what TurboHUD is waiting for.

| What you see | What it means | What to do |
| --- | --- | --- |
| Only the clock, and you are in a menu, lobby or custom session | There is no race to read | Nothing is wrong: enter a race and wait for the grid |
| Only the clock, and you are in a race | TurboHUD has not found the race | Wait a minute, then send the output of the command above |
| Cannot tell which bottle TSU runs in | You have more than one bottle | Quit TurboHUD, then start it with the command below |
| A warning that the graphics setting is not D3DMetal | TSU may stutter on this setting | Set the bottle's graphics to D3DMetal in CrossOver and restart TSU, then tell us you changed it |
| TurboHUD will not open | macOS is blocking it | Repeat the **Open Anyway** step in the install section |

To choose the bottle yourself, run this with your bottle's name in place of `Steam`:

```
TURBOHUD_BOTTLE=Steam /Applications/TurboHUD.app/Contents/MacOS/TurboHUD
```

To remove TurboHUD, quit it and move it from Applications to the Bin. Its settings and logs are in `~/Library/Application Support/TurboHUD`.
