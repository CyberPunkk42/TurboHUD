"""Hyprland: keep TurboHUD's own window floating, pinned and above the game.

On Wayland a window cannot put itself on top; Qt's stay-on-top hint is ignored, and
Hyprland tiles TurboHUD like any other window. So TurboHUD asks Hyprland at runtime,
through `hyprctl`, to float, place and pin its own window and never give it the keyboard
focus. Every command names TurboHUD's own window by its address; nothing else is
touched, and no Hyprland configuration is read or changed. The requests end with the
window.

Hyprland 0.55 and later take Lua commands (`hl.dsp.window.pin({...})`); older versions
the classic ones (`pin address:0x...`). Each command is tried in the Lua form first.
"""

import json
import logging
import os
import shutil
import subprocess

log = logging.getLogger(__name__)
TIMEOUT = 2.0  # seconds for one hyprctl call
# Properties of TurboHUD's own window: (Lua name, classic name, value). No keyboard
# focus, so the game keeps it; and none of the desktop's frame, shadow, blur, animation
# or see-through for inactive windows, so only the HUD's text shows.
WINDOW_PROPS = [
    ('no_focus', 'nofocus', '1'),
    ('decorate', 'decorate', '0'),
    ('border_size', 'bordersize', '0'),
    ('no_shadow', 'noshadow', '1'),
    ('no_blur', 'noblur', '1'),
    ('no_anim', 'noanim', '1'),
    ('opacity', 'alpha', '1.0'),
]


def available(environ=None, which=shutil.which):
    """Whether TurboHUD runs on Hyprland with hyprctl at hand."""
    environ = os.environ if environ is None else environ
    return bool(environ.get('HYPRLAND_INSTANCE_SIGNATURE')) and which('hyprctl') is not None


def _run(args):
    result = subprocess.run(['hyprctl', *args], capture_output=True, text=True, timeout=TIMEOUT)
    return result.stdout.strip()


def place_commands(window, x, y, width, height):
    """(lua, classic) command pairs that float, size, place and pin `window`
    ('address:0x...'), put it in front and keep the keyboard focus away from it."""
    return [
        (f"hl.dsp.window.float({{ action = 'enable', window = '{window}' }})", f'setfloating {window}'),
        (
            f"hl.dsp.window.resize({{ x = {width}, y = {height}, window = '{window}' }})",
            f'resizewindowpixel exact {width} {height},{window}',
        ),
        (f"hl.dsp.window.move({{ x = {x}, y = {y}, window = '{window}' }})", f'movewindowpixel exact {x} {y},{window}'),
        (f"hl.dsp.window.pin({{ action = 'enable', window = '{window}' }})", f'pin {window}'),
        (f"hl.dsp.window.alter_zorder({{ mode = 'top', window = '{window}' }})", f'alterzorder top,{window}'),
    ] + [
        (f"hl.dsp.window.set_prop({{ prop = '{prop}', value = '{value}', window = '{window}' }})", f'setprop {window} {old} {value}')
        for prop, old, value in WINDOW_PROPS
    ]


def focus_command(window):
    return (f"hl.dsp.focus({{ window = '{window}' }})", f'focuswindow {window}')


class Hyprland:
    def __init__(self, run=_run):
        self.run = run

    def dispatch(self, command):
        """Run a (lua, classic) pair; True if Hyprland answered ok to either."""
        lua, classic = command
        for text in (lua, classic):
            try:
                if self.run(['dispatch', text]) == 'ok':
                    return True
            except (OSError, subprocess.SubprocessError) as error:
                log.info('hyprctl failed: %s', error)
                return False
        log.info('Hyprland refused: %s', classic)
        return False

    def _json(self, what):
        try:
            return json.loads(self.run(['-j', what]) or 'null')
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            log.info('hyprctl %s failed: %s', what, error)
            return None

    def own_window(self, pid, title):
        """The address ('0x...') of this process's window with that title, or None."""
        for client in self._json('clients') or []:
            if client.get('pid') == pid and client.get('title') == title and client.get('mapped', True):
                return client.get('address')
        return None

    def active_window(self):
        active = self._json('activewindow')
        return active.get('address') if isinstance(active, dict) else None

    def geometry(self, address):
        """(x, y, width, height) of a window as Hyprland has it, or None."""
        for client in self._json('clients') or []:
            if client.get('address') == address:
                (x, y), (width, height) = client['at'], client['size']
                return (x, y, width, height)
        return None

    def place(self, address, x, y, width, height):
        """Float, place and pin the window; True if every command was taken."""
        window = f'address:{address}'
        return all([self.dispatch(command) for command in place_commands(window, x, y, width, height)])

    def focus(self, address):
        return self.dispatch(focus_command(f'address:{address}'))
