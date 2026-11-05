TurboHUD: a test version for Turbo Sliders Unlimited on the Mac
==================================================================

TurboHUD draws lap times, fuel, tires, a track map, a radar and more on top of TSU. It only
reads what the game shows; it changes nothing in the game or in its CrossOver bottle.

WHAT YOU NEED
- A Mac with Apple silicon (M1 or newer) and macOS {minimum} or newer
- TSU running in CrossOver (TurboHUD itself needs no setup in CrossOver)


INSTALL
1. Drag TurboHUD onto the Applications folder in this window.
2. Open Applications and double-click TurboHUD.
3. macOS says it "could not verify" TurboHUD, as this test version is not signed with a paid
   Apple certificate. Click Done (not Move to Trash).
4. Open System Settings > Privacy & Security and scroll down to Security. Next to "TurboHUD
   was blocked", click Open Anyway, enter your password, and click Open Anyway once more.

From then on, a double-click is enough. Only open it this way if you trust the person who
gave it to you.

If there is no Open Anyway button, type this in Terminal and press Return, then try again:
    xattr -dr com.apple.quarantine /Applications/TurboHUD.app


WHAT TO EXPECT
TurboHUD opens no window and has no Dock icon. You should see its icon in the menu bar (black,
"TSU TurboHUD") and a small clock at the top left of the screen.

Start TSU, in either order. The race sections appear when the cars stand on the grid. Online,
finding the race can take a few seconds after the start. Hover over the menu bar icon to see
what TurboHUD is waiting for.


USE
- Ctrl+Shift+L, or the menu bar icon: move mode. Drag and resize the sections, and tick off the
  ones you do not want. Press it again to go back to the game.
- Ctrl+Shift+1, 2, 3: load a saved layout (presets).
- Ctrl+Shift+Q, or the menu bar icon: quit.


IF TSU STUTTERS
In CrossOver, set the graphics of TSU's bottle to D3DMetal and restart TSU. On the Mac this was
developed on, that cured it. TurboHUD warns on its menu bar icon when the setting is different.
An unsteady Wi-Fi connection may also play a part when you join a server.


IF THERE IS MORE THAN ONE BOTTLE
If TurboHUD cannot tell which bottle holds TSU, quit it and start it from Terminal, with your
bottle's name in place of Steam:
    TURBOHUD_BOTTLE=Steam /Applications/TurboHUD.app/Contents/MacOS/TurboHUD


WHAT IS NOT FINISHED
- The throttle and brake bars move in TSU's steps (thirds) on the Mac.
- Spectating, and races with many real players, have had little testing.


REPORTING A PROBLEM
Say what you did and what you saw, and send these two files from
~/Library/Application Support/TurboHUD
(in Finder: Go > Go to Folder, and paste that line):
    turbohud.log
    bottle_reader.log (if it is there)
turbohud.log is replaced at each start, so copy it before you start TurboHUD again. The logs can
hold player names and the folders on your Mac: look through them first if you like.


REMOVING IT
Quit TurboHUD and move it from Applications to the Bin. Its settings are in the folder above.
