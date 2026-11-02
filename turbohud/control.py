"""Telling a running TurboHUD what to do, from a command line (Linux and macOS).

    run_turbohud.sh --toggle     move mode on or off
    run_turbohud.sh --move       move mode on (a plain second start does the same)
    run_turbohud.sh --lock       move mode off
    run_turbohud.sh --settings   open the settings window
    run_turbohud.sh --quit       quit TurboHUD

Where the system has no shortcuts for TurboHUD (Linux), these can be bound to keys in
the desktop's own settings by the player; TurboHUD changes no desktop configuration.
The running TurboHUD listens on a socket in the user's private runtime folder, which
only that user can open. No Qt here: a command answers in a fraction of a second.
"""

import os
import socket
import sys
from pathlib import Path

COMMANDS = ('toggle', 'move', 'lock', 'settings', 'quit', 'ping')
TIMEOUT = 2.0  # seconds for the running TurboHUD to answer


def control_path(environ=None, platform=sys.platform, uid=None):
    """The control socket's path, or None where there is none (Windows: shortcuts)."""
    if platform == 'win32':
        return None
    environ = os.environ if environ is None else environ
    uid = os.getuid() if uid is None else uid
    base = environ.get('XDG_RUNTIME_DIR') or f'/tmp/turbohud-{uid}'
    return Path(base) / 'turbohud' / 'control.sock'


def prepare_folder(path):
    """Make the socket's folder, private to the user."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)


def send(command, path=None):
    """Send `command` to the running TurboHUD; its answer ('ok', or an error text), or
    None when none is running."""
    if command not in COMMANDS:
        raise ValueError(f'unknown command {command!r}')
    path = path or control_path()
    if path is None or not Path(path).exists():
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(TIMEOUT)
            conn.connect(str(path))
            conn.sendall(command.encode() + b'\n')
            answer = b''
            while not answer.endswith(b'\n'):
                chunk = conn.recv(256)
                if not chunk:
                    break
                answer += chunk
    except OSError:
        return None  # a socket left behind by a TurboHUD that is gone
    return answer.decode('utf-8', 'replace').strip() or None
