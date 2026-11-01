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
- 2026-10-24: Qt overlay probe tested over TSU on the Mac, in Fullscreen with and
  without Fullscreen Exclusive: the HUD shows, text is crisp, clicks pass through,
  shortcuts and move mode work, and the game does not stutter. Qt is confirmed for the
  Mac overlay; Windows is next.
- 2026-10-24: App skeleton and bundled builds. `turbohud/` holds the overlay (locked and
  move mode, shortcuts, tray icon, saved placement and theme) with a session clock as the
  first HUD. `tools/build_app.py` builds a ready-to-run app with PyInstaller (Mac: 27 MB
  ZIP); GitHub Actions builds and smoke-tests Windows, macOS and Linux. `README.md`
  explains install, first start (step by step per system) and use. Tested by hand on the
  Mac. On Omarchy Linux it runs but does not stay on top of TSU (backlog).
- 2026-10-24: HUD text and app icon. The move-mode hint now sits on its own two lines
  above the Lock and Close buttons, and the box's minimum size grows with the theme's
  scale so nothing overlaps. Text outlines are filled by winding and merged, which fixes
  letters built from overlapping parts (a hole in "+", the broken-looking "4" on Linux);
  Linux prefers a plain sans-serif font. The TSU TurboHUD image is the app, window and
  tray icon (Pillow converts it for Windows and macOS builds). Checked by hand on the Mac
  and on Omarchy Linux.
- 2026-11-01: Renamed TurboKit to TurboHUD (package `turbohud/`, `launch_turbohud.py`,
  `run_turbohud.sh` / `.cmd`, settings folder `TurboHUD`). The project is now local only:
  nothing is pushed to GitHub (the remote's push URL is disabled), changes are approved by
  a local merge, and the folder will be shared over the local network later. The icon
  image still reads "TurboKit" and needs a new version.
- 2026-11-01: Memory probe for Linux (`experiments/tsu_memory_probe.py`). Steam starts
  TSU through it, so it may read TSU's memory and nothing else's, with no sudo, setcap or
  system change. It checks one read of the game's code and logs the result to
  `~/.config/TurboHUD/memory_probe.log`. Self-test passes on Omarchy; not yet tried with
  TSU.
