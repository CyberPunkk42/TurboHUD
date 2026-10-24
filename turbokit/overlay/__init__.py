"""The overlay window and the per-system parts Qt cannot do.

Each system module has a `Native` class with the same methods:
- prepare_app(): before the first window shows
- raise_window(widget): keep the window above the game; returns a line for the log
- take_focus() / give_focus_back(): around move mode, so the game gets its focus back
- register_hotkeys(on_hotkey) -> bool, unregister_hotkeys()
"""

import sys

HOTKEY_LOCK = 1
HOTKEY_QUIT = 2


def native_for(platform=sys.platform):
    """The Native class for a system (sys.platform value)."""
    if platform == 'darwin':
        from turbokit.overlay.macos import Native
    elif platform == 'win32':
        from turbokit.overlay.windows import Native
    else:
        from turbokit.overlay.linux import Native
    return Native
