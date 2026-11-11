# Windows, and TurboHUD inside CrossOver

State: 2026-11-09. Two connected questions: what TurboHUD still needs on Windows, and whether
TurboHUD on the Mac could run as a Windows app inside TSU's CrossOver bottle instead of as a
native Mac app beside it. Nothing here is built yet; this is the analysis and the plan.

## Windows today

| Part | State |
| --- | --- |
| Overlay windows (Qt: on top, see-through, click-through) | built, not yet run over TSU on Windows |
| Shortcuts (`turbohud/overlay/windows.py`: `RegisterHotKey`, focus hand-back) | built, run only on a build machine |
| Reading TSU (`turbohud/tsu/winmemory.py`: `find_process`, `WindowsProcess`, page cache, paced search, `connect`) | built and used daily, but only inside the bottle by `bottle_reader.py` |
| Live race in the app | built 2026-11-11, not yet run on Windows: `start_live_race` starts the Rust reader (`reader/`) beside TSU (`LocalReader` in `turbohud/tsu/bottle.py`; the pipe's answers taken by a thread, as Windows cannot select on a pipe), else, where it is missing, reads in Python from TurboHUD itself (`winmemory.connect`). The Windows build ships the Rust reader |
| Gamepad triggers | Linux only (`/dev/input/js*`); on Windows XInput would be the way |
| Builds | `tools/build_app.py` makes a Windows ZIP, built on Windows |

Windows lets a program read another of the same user (`OpenProcess` with `PROCESS_VM_READ`,
`ReadProcessMemory`), so no probe and no launch option are needed. Wiring the live race is mostly
a `win32` branch in `start_live_race` that gives `LiveRace` a connect function built on
`winmemory.connect`, in the app's own process. This is backlog item 2, and the same step is
needed before TurboHUD can be tried inside the bottle (below).

To do on Windows (backlog item 2):
1. Over TSU, windowed, Fullscreen and Fullscreen Exclusive: the built app, the Qt probe
   (`experiments/run_qt_overlay_probe.cmd`) and the original probe; results in
   `experiments/README.md`. Expected: windowed and Fullscreen work; Exclusive may not, and an
   overlay that injects into the game is out of scope.
2. The shortcuts with TSU in front.
3. Live data in-process, as above; then a race offline, hosting, and as an online client.

## The Mac today: two parts

- **The overlay**: a native Mac Qt app outside the bottle, at window level 1000 (above TSU's
  Fullscreen, which is level 26), on every Space, with Carbon hotkeys.
- **The reader**: `turbohud/tsu/bottle_reader.py`, run by a portable Windows Python inside the
  bottle, reading TSU with `winmemory.py`. The app starts it with CrossOver's `wine --bottle`
  and asks it over a pipe (`turbohud/tsu/bottle.py`). macOS refuses a Mac program access to
  TSU's memory (CrossOver's loader has the hardened runtime), so the reading has to happen in
  the bottle.

## The option: all of TurboHUD inside the bottle

The Windows build of TurboHUD (Qt for Windows) started in TSU's bottle: it reads TSU itself with
`winmemory.py` and draws its windows through Wine.

### What is already known
The plain Win32 overlay probe inside CrossOver, over TSU (2026-10-23, `experiments/README.md`):

| TSU display setting | Overlay inside the bottle |
| --- | --- |
| Windowed | works: see-through, click-through, Ctrl+Shift+L and Q arrive |
| Fullscreen Exclusive, with Fullscreen off | works |
| Fullscreen (with or without Exclusive) | never visible |

In Fullscreen TSU's window is at Mac level 26; a Wine window reaches level 3 at most. Windows'
own window order (as Wine reports it) has the overlay in front, but the Mac still draws the game
above it. TurboHUD cannot change that from its side. The tester plays in Fullscreen, as did the
user's FPS tests.

### What it would gain
1. One app for Windows and the Mac: tests on the Mac would also run much of the Windows code
   (Wine is not Windows, so it narrows the Windows testing, it does not replace it).
2. Fewer parts: no looking for CrossOver and the bottle (and no wrong pick when there are two
   CrossOver copies), no pipe, no separate reader, no Windows Python inside the Mac app.
3. Perhaps the pad's real throttle and brake through XInput in Wine, instead of TSU's thirds.
   Not tested.

Not a gain: speed of the reads. Each read is a round trip through the Wine server (about
225 µs) either way; the pipe adds little. A race read stays near 20 ms.

### What it would cost or risk
1. No overlay over TSU's Fullscreen (tested, above). So at best a second mode, for players who
   run TSU windowed or with Fullscreen off.
2. Frames: every Wine window is still a Mac window above the game, so the window count costs
   as before (17 windows 85 FPS, one 115, on the user's Mac), perhaps more, as Wine draws each
   window and copies it into a Mac one. The one-window canvas (`HudCanvas`) would need turning
   on for the Windows path too; it is on only for the Mac's native code now.
3. Load on the Wine server: TSU uses the same server, and the reads already slow down when the
   game is busy. A whole Qt app in the bottle (windows, timers, messages) sends it far more
   than the reader does. Not measured.
4. Text on Retina screens: with CrossOver's High Resolution Mode off (the default), Wine apps
   see the screen in points and Qt draws at 1x, so the text is soft. Turning the mode on is a
   setting of the whole bottle and changes how TSU draws too, so it is the player's choice,
   never TurboHUD's.
5. Qt 6 under Wine is not proven here: only the plain Win32 probe ran in the bottle, never
   PySide6. To check: windows with per-pixel alpha, the tray icon (Wine puts it in the menu
   bar), the screen scale, and handing the focus back to the game.
6. Installing: players would put TurboHUD into the bottle, against the rule so far that nothing
   is installed there. Logs and crashes inside Wine are harder to read.
7. TSU sometimes freezes on quitting (`docs/CONTINUE_HERE.md`, "Other points"), cause not known.
   More of TurboHUD in the bottle makes it harder to rule TurboHUD out.

### Plan to try it, cheapest first
1. **Probe.** Run `experiments/qt_overlay_probe.py` in the bottle, with PySide6 in a separate
   copy of `.buildtools/win-python` (the embeddable Python has no pip, so the wheels are
   unpacked there by hand). With TSU windowed and with Fullscreen off, check: visible,
   click-through, shortcuts, crisp text, the tray icon, and FPS with the Metal HUD. About an
   hour. If Qt does not work in Wine, stop here.
2. **Fair comparison.** TSU windowed, the Metal HUD: the native TurboHUD against the probe in
   the bottle, with the same boxes, once as many windows and once as one window.
3. **Only if 1 and 2 look good.** Wire up Windows live data in-process (needed for Windows
   anyway, backlog item 2), turn on the one-window canvas for the Windows path, and run the
   real app in the bottle as an option ("inside CrossOver, TSU windowed only").
4. **Decide from the numbers.** As fast as the native app when windowed: keep it as an option.
   The main Mac version: only if windowed TSU turns out to be how most Mac players play.

Rules for the trial: nothing in the bottle's settings, the game's folders or the system is
changed; PySide6 and the probe stay in `.buildtools/` and `experiments/`.
