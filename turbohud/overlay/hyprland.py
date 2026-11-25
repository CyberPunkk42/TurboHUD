"""Hyprland: keep TurboHUD's own window floating, pinned and above the game.

On Wayland a window cannot put itself on top; Qt's stay-on-top hint is ignored, and
Hyprland tiles TurboHUD like any other window. So TurboHUD asks Hyprland at runtime,
through `hyprctl`, to float, place and pin its own window and never give it the keyboard
focus. Every command names TurboHUD's own window by its address; nothing else is
touched, and no Hyprland configuration file is read or changed. The requests end with the
window.

Shortcuts (asked for by the user on 2026-11-15): Wayland lets no app catch keys meant for
another window, so while TurboHUD runs it adds its own keys to Hyprland's live keymap
(Ctrl+Shift+L, Q, 1, 2, 3, as on Windows and the Mac), each running TurboHUD's command line
(turbohud.control). Only keys nothing else uses get one; at quit TurboHUD takes them away
again. They live in Hyprland's memory only: a config reload drops them (TurboHUD adds them
again), and a restart of Hyprland ends them, also after a crash of TurboHUD.

Hyprland 0.55 and later take Lua commands (`hl.dsp.window.pin({...})`); older versions
the classic ones (`pin address:0x...`). Each command is tried in the Lua form first.

Placing a window takes a dozen commands. Each hyprctl call is a process of its own, so they
go in one `hyprctl --batch` call (a preset load froze the HUD 1.2-1.4 s with one call each
for 23 sections, seen 2026-11-20); where the batch is not taken in full, one by one as before.
"""

import json
import logging
import os
import shlex
import shutil
import subprocess
import time

from turbohud.core.system_env import system_env

log = logging.getLogger(__name__)
TIMEOUT = 2.0  # seconds for one hyprctl call
MONITORS_KEPT = 1.0  # seconds the monitor list is kept: a preset load places 23 windows at once
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


# TurboHUD's keys: (Hyprland's name, the command line's arguments). Ctrl+Shift+F12 switches move
# mode where something else has Ctrl+Shift+L (as on Windows).
LOCK_BIND = 'CTRL + SHIFT + L'
LOCK_BIND_BACKUP = 'CTRL + SHIFT + F12'
SHORTCUTS = (
    (LOCK_BIND, ('--toggle',)),
    ('CTRL + SHIFT + Q', ('--quit',)),
    ('CTRL + SHIFT + 1', ('--preset', '1')),
    ('CTRL + SHIFT + 2', ('--preset', '2')),
    ('CTRL + SHIFT + 3', ('--preset', '3')),
    ('CTRL + SHIFT + 4', ('--preset', '4')),
    ('CTRL + SHIFT + 5', ('--preset', '5')),
)
BIND_LABEL = 'TurboHUD shortcut'  # the binds' description: how TurboHUD knows its own
MODS = {'SHIFT': 1, 'CAPS': 2, 'CTRL': 4, 'ALT': 8, 'MOD2': 16, 'MOD3': 32, 'SUPER': 64, 'MOD5': 128}


def key_of(keys):
    """(modmask, key) of 'CTRL + SHIFT + L', as `hyprctl binds -j` lists a bind."""
    *mods, key = [part.strip().upper() for part in keys.split('+')]
    return sum(MODS[mod] for mod in mods), key


def lua_string(text):
    if '\n' in text or '\r' in text:
        raise ValueError('no line breaks in a bind')
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'


def bind_commands(keys, command, what):
    """(lua, classic) ways to bind `keys` to run `command` (a list of arguments)."""
    line = shlex.join(command)
    label = f'{BIND_LABEL}: {what}'
    return (
        f'hl.bind({lua_string(keys)}, hl.dsp.exec_cmd({lua_string(line)}), {{ description = {lua_string(label)} }})',
        f'{classic_keys(keys)}, {label}, exec, {line}',
    )


def unbind_commands(keys):
    return (f'hl.unbind({lua_string(keys)})', classic_keys(keys))


def classic_keys(keys):
    """'CTRL + SHIFT + L' as older Hyprland writes it: 'CTRL SHIFT, L'."""
    *mods, key = [part.strip() for part in keys.split('+')]
    return f'{" ".join(mods)}, {key}'


def event_socket(environ=None):
    """Hyprland's event socket (it says `configreloaded>>` after a reload), or None."""
    environ = os.environ if environ is None else environ
    signature = environ.get('HYPRLAND_INSTANCE_SIGNATURE')
    runtime = environ.get('XDG_RUNTIME_DIR')
    if not signature:
        return None
    for folder in ([os.path.join(runtime, 'hypr')] if runtime else []) + ['/tmp/hypr']:
        path = os.path.join(folder, signature, '.socket2.sock')
        if os.path.exists(path):
            return path
    return None


def available(environ=None, which=shutil.which):
    """Whether TurboHUD runs on Hyprland with hyprctl at hand."""
    environ = os.environ if environ is None else environ
    return bool(environ.get('HYPRLAND_INSTANCE_SIGNATURE')) and which('hyprctl') is not None


def _run(args):
    # Not the bundled app's library path: hyprctl would load its old libstdc++ and not start.
    result = subprocess.run(
        ['hyprctl', *args], capture_output=True, text=True, timeout=TIMEOUT, check=False, env=system_env()
    )
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
    def __init__(self, run=_run, clock=time.monotonic):
        self.run = run
        self._clock = clock
        self._monitors = (None, None)  # (when asked, the list): see MONITORS_KEPT
        self._batch = True  # False once a batch was refused that the same commands one by one were not

    def dispatch_all(self, commands):
        """Run (lua, classic) pairs; True if every one was taken. First all in their Lua form in
        one hyprctl call; where that is not taken in full, one by one (dispatch), the classic
        form too, as before. A pair without a classic form is a best effort: older Hyprland
        lacks it. Where the batch failed and one by one did not (an older Hyprland, or one
        without batches), the batch is not tried again."""
        commands = list(commands)
        if self._batch and len(commands) > 1:
            text = ' ; '.join(f'dispatch {lua}' for lua, _classic in commands)
            try:
                answer = self.run(['--batch', text])
            except (OSError, subprocess.SubprocessError) as error:
                log.info('hyprctl failed: %s', error)
                return False
            # One `ok` for each, with or without blank lines between them.
            if ''.join(answer.split()) == 'ok' * len(commands):
                return True
            one_by_one = self._one_by_one(commands)
            if one_by_one:
                self._batch = False
                log.info('Hyprland: no batches, each command on its own (%s)', ' '.join(answer.split())[:80])
            return one_by_one
        return self._one_by_one(commands)

    def _one_by_one(self, commands):
        # Every command is sent, also after one is refused.
        results = [self.dispatch(command) or command[1] is None for command in commands]
        return all(results)

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

    def monitors(self):
        """Hyprland's monitors, asked again once MONITORS_KEPT has passed."""
        asked, found = self._monitors
        now = self._clock()
        if found is None or now - asked >= MONITORS_KEPT:
            found = self._json('monitors')
            self._monitors = (now, found) if found is not None else (None, None)
        return found or []

    def workspace_at(self, x, y):
        """The id of the workspace shown on the monitor that holds the point, or None."""
        for monitor in self.monitors():
            mx, my, width, height = monitor['x'], monitor['y'], monitor['width'], monitor['height']
            scale = monitor.get('scale') or 1
            if mx <= x < mx + width / scale and my <= y < my + height / scale:
                return monitor.get('activeWorkspace', {}).get('id')
        return None

    def place(self, address, x, y, width, height, focusable=False):
        """Float, place and pin the window; True if every command was taken."""
        window = f'address:{address}'
        return self.dispatch_all(
            place_commands(window, x, y, width, height, self.workspace_at(x, y), focusable)
        )

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

    def to_front(self, address):
        """In front of the other floating windows; True if taken."""
        window = f'address:{address}'
        return self.dispatch(
            (
                f"hl.dsp.window.alter_zorder({{ mode = 'top', window = '{window}' }})",
                f'alterzorder top,{window}',
            )
        )

    def focus(self, address):
        return self.dispatch(focus_command(f'address:{address}'))

    def binds(self):
        """Every bind Hyprland has now, as `hyprctl binds -j` lists them ([] if none known)."""
        found = self._json('binds')
        return found if isinstance(found, list) else []

    def bind_owner(self, keys, binds):
        """'turbohud' where the key has TurboHUD's bind, 'other' where anything else has it
        (in the main keymap), None where it is free."""
        mods, key = key_of(keys)
        owner = None
        for bind in binds:
            if bind.get('submap') or bind.get('modmask') != mods or str(bind.get('key', '')).upper() != key:
                continue
            if str(bind.get('description', '')).startswith(BIND_LABEL):
                owner = owner or 'turbohud'
            else:
                return 'other'
        return owner

    def _eval_or_keyword(self, lua, keyword, classic):
        try:
            if self.run(['eval', lua]) == 'ok':
                return True
            answer = self.run(['keyword', keyword, classic])
        except (OSError, subprocess.SubprocessError) as error:
            log.info('hyprctl failed: %s', error)
            return False
        if answer == 'ok':
            return True
        log.info('Hyprland refused %s: %s', lua, answer.splitlines()[0] if answer else '(no answer)')
        return False

    def bind(self, keys, command, what):
        """Bind keys to run command in Hyprland's live keymap; True if taken."""
        lua, classic = bind_commands(keys, command, what)
        return self._eval_or_keyword(lua, 'bindd', classic)

    def unbind(self, keys):
        lua, classic = unbind_commands(keys)
        return self._eval_or_keyword(lua, 'unbind', classic)
