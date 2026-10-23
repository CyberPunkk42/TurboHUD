# Progress

Every finished change, oldest first. `RESUME.md` keeps the most recent ones at the top of
its "Recent changes".

- 2026-10-23: Overlay probe. A test overlay for TSU, with a launcher that runs it in the
  CrossOver bottle using a portable Windows Python. On the Mac it works over TSU except in
  TSU's Fullscreen mode, where no window from inside CrossOver can show.
- 2026-10-23: Native Mac overlay probe (`experiments/mac_overlay_probe.py`). A plain Mac
  program outside CrossOver, at a window level above full-screen windows. It shows over
  TSU in Fullscreen, lets clicks through, and has the same shortcuts and move mode, with
  no permission needed. The Mac overlay for Fullscreen must therefore be native.
- 2026-10-23: Stack chosen (`docs/STACK.md`): Python with Qt (PySide6), shipped as a
  ready-to-run app for Windows, macOS and Linux, so players install nothing else. Chosen
  for good-looking, customisable HUD graphics drawn once for all systems. Linux limits
  (Wayland, Steam Deck) noted.
- 2026-10-23: Qt overlay probe (`experiments/qt_overlay_probe.py`) on the chosen stack:
  a test HUD (outlined text, clock, bar, small map) in a transparent, click-through Qt
  window with move mode and the shortcuts, raised above Fullscreen on the Mac through
  ctypes. Runners set up the pinned PySide6 in `.buildtools/qt-venv`. Starts on the Mac;
  not yet tested over TSU.
- 2026-10-24: Qt overlay probe tested over TSU on the Mac (Fullscreen on, Exclusive
  off): the HUD shows, text is crisp, clicks pass through, shortcuts and move mode work,
  and the game does not stutter. Qt is confirmed for the Mac overlay; Windows is next.
