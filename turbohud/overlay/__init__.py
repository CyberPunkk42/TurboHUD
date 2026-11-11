"""The overlay window and the per-system parts Qt cannot do.

Each system module has a `Native` class with the same methods:
- prepare_app(): before the first window shows
- raise_window(widget): keep the window above the game; returns a line for the log
- take_focus() / give_focus_back(): around move mode, so the game gets its focus back
- register_hotkeys(on_hotkey) -> bool, unregister_hotkeys()
"""

import os
import sys

HOTKEY_LOCK = 1
HOTKEY_QUIT = 2
HOTKEY_PRESETS = {3: 1, 4: 2, 5: 3}  # hotkey number -> the layout preset it loads
HOTKEY_SCREENSHOT = 6  # Ctrl+Shift+S: a screenshot of the game with the HUD (turbohud.screenshot)


def choose_platform(environ=None, platform=sys.platform):
    """The Qt platform to use, or None for Qt's own choice. On Linux under Wayland
    without Hyprland (KDE, GNOME ...), Qt's stay-on-top hint is ignored, so TurboHUD
    runs through XWayland ('xcb'), where those desktops honour it. Not on Hyprland,
    where TurboHUD asks Hyprland itself; not when the player set QT_QPA_PLATFORM, or
    TURBOHUD_PLATFORM=wayland to keep Wayland."""
    environ = os.environ if environ is None else environ
    if not platform.startswith('linux') or 'QT_QPA_PLATFORM' in environ:
        return None
    if environ.get('TURBOHUD_PLATFORM') == 'wayland':
        return None
    wayland = environ.get('WAYLAND_DISPLAY') or environ.get('XDG_SESSION_TYPE') == 'wayland'
    if wayland and not environ.get('HYPRLAND_INSTANCE_SIGNATURE') and environ.get('DISPLAY'):
        return 'xcb'
    return None


def native_for(platform=sys.platform):
    """The Native class for a system (sys.platform value)."""
    if platform == 'darwin':
        from turbohud.overlay.macos import Native
    elif platform == 'win32':
        from turbohud.overlay.windows import Native
    else:
        from turbohud.overlay.linux import Native
    return Native
