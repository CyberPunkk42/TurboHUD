TurboHUD: a test version for Turbo Sliders Unlimited on Linux
================================================================

TurboHUD draws lap times, fuel, tires, a track map, a radar and more on top of TSU. It only
reads what the game shows; it changes nothing in the game, in Steam or in your system.

WHAT YOU NEED
- A 64-bit PC with a Linux from 2022 or newer: Ubuntu 22.04, Linux Mint 21, Debian 12,
  Fedora 36, SteamOS 3.5, Arch or newer (glibc 2.35 or newer)
- TSU's native Linux version in Steam (not the Windows version through Proton)


INSTALL
1. Unpack this folder somewhere it can stay, for example your home folder:
       tar -xzf TurboHUD-*-linux-x64.tar.gz -C ~
   Everything TurboHUD needs is inside the folder; nothing else is installed.
2. Start ~/TurboHUD/TurboHUD (a double-click in your file manager, or from a terminal).


LIVE RACE DATA: ONE STEP IN STEAM
Linux lets a program read another program's memory only if it started that program. So TSU
has to be started through TurboHUD: then TurboHUD may read TSU's memory, and nothing else's.
No sudo, and no change to your system.

1. In a terminal, run (with the folder where you unpacked TurboHUD):
       ~/TurboHUD/TurboHUD --launch-option
   It prints a line like this one:
       "/home/you/TurboHUD/TurboHUD" --probe %command%
2. In Steam, right-click Turbo Sliders Unlimited > Properties > General > Launch Options,
   and paste that line (with the quotes).
3. Start TSU from Steam as usual, and start TurboHUD (before or after; it finds the game).

If you move the TurboHUD folder, do step 1 and 2 again. To start TSU without TurboHUD, clear
the Launch Options field. What the probe did goes to ~/.config/TurboHUD/memory_probe.log; if
anything goes wrong there, the game still starts as usual.


WHAT TO EXPECT
TurboHUD opens no window. You see its icon in the tray of your desktop's panel (black,
"TSU TurboHUD") and a small clock at the top left of the screen. On GNOME the tray needs the
"AppIndicator and KStatusNotifierItem Support" extension (Ubuntu has it already).

The race sections appear when the cars stand on the grid. Online, finding the race can take
a few seconds after the start. Hover over the tray icon to see what TurboHUD is waiting for.


USE
Linux has no global shortcuts in TurboHUD. Use the tray icon's menu, or these commands (you can
put them on keys in your desktop's keyboard settings):
    ~/TurboHUD/TurboHUD --toggle       move mode on or off: drag and resize the sections,
                                       tick off the ones you do not want
    ~/TurboHUD/TurboHUD --preset 1     load a saved layout (1, 2 or 3)
    ~/TurboHUD/TurboHUD --quit         quit
More in "Quick Start.txt".


WHAT IS NOT FINISHED
- Developed on Hyprland (Wayland). On KDE, GNOME and other desktops TurboHUD runs through
  XWayland or X11: staying on top of the game and letting clicks through have had little
  testing there. If the HUD hides behind the game, try TSU in a window or borderless.
- Spectating, and races with many real players, have had little testing.


REPORTING A PROBLEM
Say what you did and what you saw, your Linux and desktop (for example "Fedora 41, KDE"), and
send these files from ~/.config/TurboHUD:
    turbohud.log
    memory_probe.log
turbohud.log is replaced at each start, so copy it before you start TurboHUD again. The logs
can hold player names and the folders on your PC: look through them first if you like.


REMOVING IT
Clear TSU's Launch Options in Steam, quit TurboHUD and delete its folder. Its settings are in
~/.config/TurboHUD.
