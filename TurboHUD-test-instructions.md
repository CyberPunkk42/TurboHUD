# TurboHUD: test instructions for the Mac

Nov 6, 2026

## What this test is for

This test finds out why TSU drops from about 97 FPS to about 60 FPS while TurboHUD runs. It takes about 15 minutes, and each measurement takes about a minute.

You need:

- A Mac with Apple silicon and macOS 27.0 or newer
- TSU running in CrossOver
- The file `TurboHUD-2026.11.06.2-macos-arm64.dmg`
- A way to read TSU's FPS, the same one each time

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

## Run the frame rate test

Run all four steps in a **real race**, on the same track with the same car and the same graphics settings. A custom session has no race for TurboHUD to read, so only the clock shows there.

To tick or untick sections, press **Control + Shift + L** for move mode, change the tick boxes, then press **Control + Shift + L** again. To quit TurboHUD, press **Control + Shift + Q**.

Drive for about a minute at each step, then write down the average FPS in the table.

| Step | Setup | Average FPS | Any stutter? |
| --- | --- | --- | --- |
| 1 | TurboHUD not running |  |  |
| 2 | TurboHUD running, every section unticked |  |  |
| 3 | TurboHUD running, only lap and delta ticked |  |  |
| 4 | TurboHUD running, all sections ticked |  |  |

After step 4, stay in the race and run the command in the next section. If you have time, also repeat steps 1 and 4 in a custom session, because the search for a race has changed there.

## What to send back

Send the filled-in table, the details below, and the output of the Terminal command.

- Your Mac's model, such as MacBook Pro M3
- The screen you play on, its resolution and its refresh rate, from **System Settings > Displays**
- Whether TSU runs windowed or in Fullscreen
- How you measured FPS

Run this while you are still in the race, **before you restart TurboHUD**, because each start replaces its log. It only reads information and changes nothing:

```
T=~/Library/Application\ Support/TurboHUD
echo "--- version"; grep -m1 'TurboHUD 2026' "$T/turbohud.log"
echo "--- reads and frames"; grep -E 'race reads|HUD frames|search:' "$T/turbohud.log" | tail -12
echo "--- reader"; tail -20 "$T/bottle_reader.log"
echo "--- graphics"; grep -h CX_GRAPHICS_BACKEND ~/Library/Application\ Support/CrossOver/Bottles/Steam/cxbottle.conf
echo "--- screens"; system_profiler SPDisplaysDataType | grep -E 'Chipset|Resolution|UI Looks|Main Display'
```

The command assumes TSU is in a bottle called `Steam`. If yours has another name, change that word. The output can include player names and your Mac's user name, so look it over before you send it.

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
