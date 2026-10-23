# Experiments

Throwaway probes that answer one question each before TurboKit's design is fixed.
They are not part of the app.

## Overlay probe (`overlay_probe.py`)

Question: can a see-through, click-through, always-on-top window sit over TSU? On the
Mac this also decides whether one Windows app can serve both systems by running inside
CrossOver.

The probe shows a dark, semi-transparent box with a seconds counter. It uses plain Win32
calls and only Python's standard library.

### Run it
1. Start TSU in a window, or on the Mac with Fullscreen off (see Results), and drive
   onto a track.
2. Start the probe:
   - Mac: `sh experiments/run_overlay_probe_mac.sh`. The first run downloads a portable
     Windows Python (3.13, checked against its SHA256) into `.buildtools/win-python`.
     It runs in the `Steam` bottle; set `TURBOKIT_BOTTLE` for another one.
   - Windows: `py -3 -B experiments\overlay_probe.py`
3. The box starts in move mode (lighter blue, with **Lock** and **Close** buttons at the
   bottom left and a resize grip in the bottom-right corner). Drag the box to move it,
   drag the grip to make it bigger or smaller, then press **Lock**. Locked, the blue
   tint and buttons disappear and only the text shows (with a thin shadow). The box is
   then click-through, so the mouse can no longer reach it:
   - **Ctrl+Shift+L** unlocks it (and locks it again)
   - **Ctrl+Shift+Q** quits
   No Alt key is needed, so this works on a Mac keyboard.
4. If the shortcuts do not arrive, quit with Ctrl+C in the terminal, or wait (10 minutes
   by default).

Position and size are saved when you lock or quit, in `.buildtools/overlay_probe.json`
(gitignored), and the next run starts there. The first run is 640x240 at the top left.

Options: `--x`, `--y`, `--width`, `--height` (pixels, instead of the saved ones),
`--alpha` (opacity of the move-mode tint, 0-255), `--seconds`, and `--locked` to start
click-through.

### What to check
| Check | Pass when |
| --- | --- |
| Visible | The box shows over the game while you drive. |
| See-through | In move mode the game shows through the blue tint; locked, only the text shows. |
| Movable | In move mode the box follows the mouse while you drag it, and the grip resizes it. |
| Pointer | The mouse pointer shows over the box in move mode (the log says when the game hides it). |
| Stays on top | The box stays visible after clicking into the game and while driving. |
| Click-through | Locked, clicking on the box steers or clicks the game; "clicks received" stays at 0. |
| Shortcuts | Ctrl+Shift+L and Ctrl+Shift+Q work while the game has focus (the log shows them). |
| Live updates | The seconds counter keeps counting while the game runs. |
| Game unaffected | No stutter or lost keyboard input in the game. |

The terminal log is also saved to `.buildtools/overlay_probe.log` (gitignored, replaced
on each run). It shows the window styles Wine or Windows kept, the result of a hit test
at the box's centre, each change of the focused window (its size and whether it keeps
itself on top), whether the mouse pointer is shown, and each time the game came in front
of the overlay. The probe then puts the overlay back on top.

### Results

**macOS, CrossOver (2026-10-23).** Tested by hand over TSU in the `Steam` bottle.

| TSU display setting | Overlay |
| --- | --- |
| Windowed | Works |
| Fullscreen Exclusive, with Fullscreen off | Works |
| Fullscreen (with or without Exclusive) | Never visible |

Where it works: the box shows over the game, moves and resizes. Locked, its background
is fully hidden and clicks pass through to the game. Ctrl+Shift+L and Ctrl+Shift+Q arrive
while TSU has focus.

In Fullscreen, TSU makes its window always-on-top and covers the whole screen. The probe
puts itself back in front, and Windows' window order (as Wine reports it) then has the
overlay in front. Still, the Mac never shows it, not even when the overlay itself covers
the whole screen. So the macOS window level Wine gives a full-screen window is above
anything another Wine window can reach. **An overlay that works over TSU's Fullscreen
mode on the Mac cannot come from inside CrossOver.** It needs a native macOS window
outside the bottle.

Other findings:
- A box that takes the mouse (move mode) blocks the game's mouse input under it: with a
  near-screen-sized box, TSU's menu cursor seemed to freeze until the box was locked. Move
  mode should be a short, deliberate step.
- TSU hides the system pointer at times. The overlay must set its own pointer in move
  mode, or there is none.

Not tested yet: Windows; stutter or lost input over a long drive.
