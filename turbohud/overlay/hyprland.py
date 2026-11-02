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
    result = subprocess.run(['hyprctl', *args], capture_output=True, text=True, timeout=TIMEOUT, check=False)
    return result.stdout.strip()


def place_commands(window, x, y, width, height, workspace=None, focusable=False):
    """(lua, classic) command pairs that float, size, place and pin `window`
    ('address:0x...'), put it in front and keep the keyboard focus away from it.

    A window opens on the monitor that has the focus, and a pinned window only shows
    on its own monitor; so it first moves, without following, to `workspace`: the one
    shown on the monitor that holds (x, y). A `focusable` window (one with buttons) keeps
    the keyboard focus it is given."""
    to_workspace = []
    if workspace is not None:
        to_workspace = [
            (
                f"hl.dsp.window.move({{ workspace = {workspace}, follow = false, window = '{window}' }})",
                f'movetoworkspacesilent {workspace},{window}',
            )
        ]
    return [
        # A window that appears while a game runs fullscreen may be made fullscreen too;
        # end that for this window only (classic commands cannot name a window for it).
        (f"hl.dsp.window.fullscreen({{ action = 'unset', window = '{window}' }})", None),
        (f"hl.dsp.window.float({{ action = 'enable', window = '{window}' }})", f'setfloating {window}'),
        *to_workspace,
        (
            f"hl.dsp.window.resize({{ x = {width}, y = {height}, window = '{window}' }})",
            f'resizewindowpixel exact {width} {height},{window}',
        ),
        (
            f"hl.dsp.window.move({{ x = {x}, y = {y}, window = '{window}' }})",
            f'movewindowpixel exact {x} {y},{window}',
        ),
        (f"hl.dsp.window.pin({{ action = 'enable', window = '{window}' }})", f'pin {window}'),
        (f"hl.dsp.window.alter_zorder({{ mode = 'top', window = '{window}' }})", f'alterzorder top,{window}'),
    ] + [
        (
            f"hl.dsp.window.set_prop({{ prop = '{prop}', value = '{value}', window = '{window}' }})",
            f'setprop {window} {old} {value}',
        )
        for prop, old, value in WINDOW_PROPS
        if not (focusable and prop == 'no_focus')
    ]


def focus_command(window):
    return (f"hl.dsp.focus({{ window = '{window}' }})", f'focuswindow {window}')


class Hyprland:
    def __init__(self, run=_run):
        self.run = run

    def dispatch(self, command):
        """Run a (lua, classic) pair; True if Hyprland answered ok to either."""
        lua, classic = command
        answers = []
        for text in (lua, classic) if classic else (lua,):
            try:
                answer = self.run(['dispatch', text])
            except (OSError, subprocess.SubprocessError) as error:
                log.info('hyprctl failed: %s', error)
                return False
            if answer == 'ok':
                return True
            answers.append(answer.splitlines()[0] if answer else '(no answer)')
        log.info('Hyprland refused %s: %s', lua, ' / '.join(answers))
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
        """(x, y, width, height) of a floating window as Hyprland has it, or None. A tiled
        window's place is the layout's, not TurboHUD's, so it is never taken."""
        for client in self._json('clients') or []:
            if client.get('address') == address and client.get('floating'):
                (x, y), (width, height) = client['at'], client['size']
                return (x, y, width, height)
        return None

    def geometries(self, addresses):
        """{address: (x, y, width, height)} of those floating windows, in one request."""
        found = {}
        for client in self._json('clients') or []:
            if client.get('address') in addresses and client.get('floating'):
                (x, y), (width, height) = client['at'], client['size']
                found[client['address']] = (x, y, width, height)
        return found

    def move(self, address, x, y):
        """Move the window only (a group mate following a drag); True if taken."""
        window = f'address:{address}'
        return self.dispatch(
            (
                f"hl.dsp.window.move({{ x = {x}, y = {y}, window = '{window}' }})",
                f'movewindowpixel exact {x} {y},{window}',
            )
        )

    def workspace_at(self, x, y):
        """The id of the workspace shown on the monitor that holds the point, or None."""
        for monitor in self._json('monitors') or []:
            mx, my, width, height = monitor['x'], monitor['y'], monitor['width'], monitor['height']
            scale = monitor.get('scale') or 1
            if mx <= x < mx + width / scale and my <= y < my + height / scale:
                return monitor.get('activeWorkspace', {}).get('id')
        return None

    def place(self, address, x, y, width, height, focusable=False):
        """Float, place and pin the window; True if every command was taken."""
        window = f'address:{address}'
        commands = place_commands(window, x, y, width, height, self.workspace_at(x, y), focusable)
        # A step without a classic form is a best effort: older Hyprland lacks it.
        results = [self.dispatch(command) or command[1] is None for command in commands]
        return all(results)

    def set_focusable(self, address, focusable):
        """Let the window take the mouse and focus (move mode) or not (locked). Hyprland's
        no_focus keeps the mouse away too, so a window with it cannot be dragged."""
        window = f'address:{address}'
        value = '0' if focusable else '1'
        return self.dispatch(
            (
                f"hl.dsp.window.set_prop({{ prop = 'no_focus', value = '{value}', window = '{window}' }})",
                f'setprop {window} nofocus {value}',
            )
        )

    def focus(self, address):
        return self.dispatch(focus_command(f'address:{address}'))
