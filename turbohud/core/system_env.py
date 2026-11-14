"""The environment for the system's own programs that TurboHUD starts (TSU through the probe,
hyprctl on Hyprland).

Inside the bundled app PyInstaller points LD_LIBRARY_PATH at the app's own libraries (keeping
what was there in LD_LIBRARY_PATH_ORIG) and adds variables of its own. A program of the system
started with that environment loads TurboHUD's libraries in place of its own: hyprctl then found
the app's libstdc++ from Ubuntu 22.04 too old and did not start (2026-11-14, so no section was
pinned on Hyprland), and TSU could load TurboHUD's Qt. From the source folder nothing changes.
"""

import os
import sys


def system_env(environ=None, frozen=None, bundle=None):
    """A copy of `environ` (default os.environ) as it was before PyInstaller changed it."""
    env = dict(os.environ if environ is None else environ)
    if not (getattr(sys, 'frozen', False) if frozen is None else frozen):
        return env
    bundle = bundle or getattr(sys, '_MEIPASS', None)
    for name in [name for name in env if name.startswith('_PYI_') or name == '_MEIPASS2']:
        del env[name]
    original = env.pop('LD_LIBRARY_PATH_ORIG', None)
    if original is not None:
        env['LD_LIBRARY_PATH'] = original
    elif 'LD_LIBRARY_PATH' in env and bundle:  # set by PyInstaller with nothing before it
        kept = [
            part for part in env['LD_LIBRARY_PATH'].split(os.pathsep) if part and not part.startswith(bundle)
        ]
        if kept:
            env['LD_LIBRARY_PATH'] = os.pathsep.join(kept)
        else:
            del env['LD_LIBRARY_PATH']
    return env
