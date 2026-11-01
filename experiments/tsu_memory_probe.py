"""Memory probe: can TurboHUD read TSU's memory on Linux, and only TSU's?

Linux (Yama, ptrace_scope 1) lets a program read another program's memory only if it
started that program, directly or further up the chain. So this probe starts TSU itself:
Steam runs it in place of the game, and it starts the game. Then it may read TSU's
memory, and nothing else's. No sudo, no setcap, no change to the system: the permission
exists only while the probe is TSU's parent, and ends when the game quits.

Set it up once, in Steam: right-click Turbo Sliders Unlimited > Properties > General >
Launch Options:
    python3 /home/<user>/Work/workspace/tsu_repositories/TurboHUD/experiments/tsu_memory_probe.py %command%
Clear the field again to start TSU normally.

When TSU is running, the probe finds the game's process (TSU.x64), reads the first bytes
of the game's code in memory (GameAssembly.so) and checks they are what the file on
disk starts with. It only reads, never writes, and never pauses the game. The result
goes to ~/.config/TurboHUD/memory_probe.log. If anything goes wrong, the game still
starts and runs as usual.

Without Steam: `python3 experiments/tsu_memory_probe.py --self-test` starts a small
program, reads its memory (should work) and tries to read the terminal's (should be
refused, showing the system's protection is untouched).
"""

import ctypes
import ctypes.util
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

GAME_EXE = 'TSU.x64'
GAME_CODE = 'GameAssembly.so'
FIND_TIMEOUT = 180.0
ELF_MAGIC = b'\x7fELF'


class IoVec(ctypes.Structure):
    _fields_ = [('iov_base', ctypes.c_void_p), ('iov_len', ctypes.c_size_t)]


def _libc():
    libc = ctypes.CDLL(ctypes.util.find_library('c') or 'libc.so.6', use_errno=True)
    libc.process_vm_readv.argtypes = [
        ctypes.c_int,
        ctypes.POINTER(IoVec),
        ctypes.c_ulong,
        ctypes.POINTER(IoVec),
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    libc.process_vm_readv.restype = ctypes.c_ssize_t
    return libc


def read_memory(pid, address, size):
    """Read `size` bytes at `address` in process `pid`. Raises OSError when refused."""
    buffer = ctypes.create_string_buffer(size)
    local = IoVec(ctypes.cast(buffer, ctypes.c_void_p), size)
    remote = IoVec(ctypes.c_void_p(address), size)
    count = _libc().process_vm_readv(pid, ctypes.byref(local), 1, ctypes.byref(remote), 1, 0)
    if count < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return buffer.raw[:count]


def parse_maps(text):
    """Turn /proc/<pid>/maps text into (start, end, perms, offset, path) tuples."""
    regions = []
    for line in text.splitlines():
        parts = line.split(None, 5)
        if len(parts) < 5:
            continue
        start, end = (int(value, 16) for value in parts[0].split('-'))
        path = parts[5].strip() if len(parts) == 6 else ''
        regions.append((start, end, parts[1], int(parts[2], 16), path))
    return regions


def module_base(regions, name):
    """Where the file `name` starts in memory (its mapping at file offset 0), or None."""
    for start, _end, _perms, offset, path in regions:
        if offset == 0 and os.path.basename(path) == name:
            return start
    return None


def descendants(root_pid, proc_root='/proc'):
    """Process ids below `root_pid`, read from the parent ids in /proc/<pid>/stat."""
    children = {}
    for entry in os.listdir(proc_root):
        if not entry.isdigit():
            continue
        try:
            stat = Path(proc_root, entry, 'stat').read_text()
        except OSError:
            continue
        # The command name in brackets may contain spaces; the parent id follows it.
        ppid = int(stat.rsplit(')', 1)[1].split()[1])
        children.setdefault(ppid, []).append(int(entry))
    found, todo = [], [root_pid]
    while todo:
        for child in children.get(todo.pop(), []):
            found.append(child)
            todo.append(child)
    return found


def process_name(pid, proc_root='/proc'):
    try:
        return Path(proc_root, str(pid), 'comm').read_text().strip()
    except OSError:
        return ''


def find_game(root_pid, timeout=FIND_TIMEOUT, proc_root='/proc'):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for pid in descendants(root_pid, proc_root):
            # comm is cut to 15 characters, which "TSU.x64" fits.
            if process_name(pid, proc_root) == GAME_EXE:
                return pid
        time.sleep(1.0)
    return None


def check_read(pid, module):
    """Read the start of `module` in process `pid`; return a line for the log."""
    regions = parse_maps(Path(f'/proc/{pid}/maps').read_text())
    base = module_base(regions, module)
    if base is None:
        return f'FAIL: {module} not found in process {pid}'
    try:
        data = read_memory(pid, base, 16)
    except OSError as error:
        return f'FAIL: reading {module} in process {pid} was refused ({error.strerror})'
    if data[:4] == ELF_MAGIC:
        return f'OK: read {len(data)} bytes of {module} in process {pid} at {base:#x}'
    return f'FAIL: unexpected bytes {data[:4]!r} at the start of {module}'


def log_path():
    base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return base / 'TurboHUD' / 'memory_probe.log'


def log(lines, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y-%m-%d %H:%M:%S')
    with path.open('a', encoding='utf-8') as file:
        for line in lines:
            file.write(f'{stamp}: {line}\n')


def run_game(command):
    """Start the game as our child, check the read once, then wait for the game."""
    game = subprocess.Popen(command)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, lambda number, _frame: game.send_signal(number))
    path = log_path()
    try:
        log([f'Started: {" ".join(command)}'], path)
        pid = find_game(game.pid)
        if pid is None:
            log([f'FAIL: no {GAME_EXE} process appeared below the probe'], path)
        else:
            log([f'Found {GAME_EXE} as process {pid}'], path)
            # Give the game a moment to load its code.
            time.sleep(5.0)
            log([check_read(pid, GAME_CODE)], path)
    except Exception as error:  # The game must keep running whatever happens here.
        try:
            log([f'FAIL: probe error {error!r}'], path)
        except OSError:
            pass
    return game.wait()


def self_test():
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    try:
        time.sleep(0.5)
        exe = os.path.basename(os.path.realpath(f'/proc/{child.pid}/exe'))
        print('Own child:', check_read(child.pid, exe))
    finally:
        child.kill()
        child.wait()
    parent = os.getppid()
    exe = os.path.basename(os.path.realpath(f'/proc/{parent}/exe'))
    result = check_read(parent, exe)
    expected = 'refused' in result
    print('Terminal (should be refused):', result, '-> as expected' if expected else '-> NOT refused')
    return 0


def main(argv):
    if not sys.platform.startswith('linux'):
        print('This probe is for Linux only.')
        return 1
    if argv == ['--self-test']:
        return self_test()
    if not argv:
        print(__doc__)
        return 1
    return run_game(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
