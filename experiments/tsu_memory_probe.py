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

While the game runs, the probe also answers read-only requests on a local socket that
only this user can open (`$XDG_RUNTIME_DIR/turbohud/tsu-memory.sock`): the memory
map, reading bytes, and searching for byte patterns, all in TSU only. The search tool
`experiments/tsu_memory_scan.py` uses it. The socket goes away when the game quits.

Without Steam: `python3 experiments/tsu_memory_probe.py --self-test` starts a small
program, reads its memory (should work) and tries to read the terminal's (should be
refused, showing the system's protection is untouched).
"""

import ctypes
import ctypes.util
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import threading
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


CHUNK = 16 * 1024 * 1024
MAX_READ = 64 * 1024 * 1024
MAX_HITS = 200_000


def searchable(region):
    """Writable private memory, where the game keeps its data; no device mappings."""
    _start, _end, perms, _offset, path = region
    return perms.startswith('rw') and perms.endswith('p') and not path.startswith(('/dev/', '['))


def search(pid, regions, patterns, align=4):
    """Addresses in `regions` of `pid` where any of `patterns` (bytes) starts."""
    hits = []
    longest = max(len(pattern) for pattern in patterns)
    for start, end, *_ in regions:
        address = start
        while address < end:
            size = min(CHUNK + longest - 1, end - address)
            try:
                data = read_memory(pid, address, size)
            except OSError:
                address += CHUNK
                continue
            for pattern in patterns:
                index = data.find(pattern)
                while index != -1:
                    if index < CHUNK and (address + index) % align == 0:
                        hits.append(address + index)
                        if len(hits) >= MAX_HITS:
                            return sorted(hits)
                    index = data.find(pattern, index + 1)
            address += CHUNK
    return sorted(hits)


def handle(pid, request):
    """Answer one request; returns (json_header, payload_bytes)."""
    op = request.get('op')
    if op == 'maps':
        regions = parse_maps(Path(f'/proc/{pid}/maps').read_text())
        return {'ok': True, 'regions': regions}, b''
    if op == 'read':
        size = int(request['size'])
        if not 0 < size <= MAX_READ:
            return {'ok': False, 'error': 'size out of range'}, b''
        data = read_memory(pid, int(request['address']), size)
        return {'ok': True, 'size': len(data)}, data
    if op == 'read_many':
        size = int(request['size'])
        if not 0 < size <= 4096:
            return {'ok': False, 'error': 'size out of range'}, b''
        values = []
        for address in request['addresses'][:MAX_HITS]:
            try:
                values.append(read_memory(pid, int(address), size).hex())
            except OSError:
                values.append(None)
        return {'ok': True, 'values': values}, b''
    if op == 'search':
        patterns = [bytes.fromhex(pattern) for pattern in request['patterns']]
        if not patterns or not all(patterns):
            return {'ok': False, 'error': 'no patterns'}, b''
        regions = [r for r in parse_maps(Path(f'/proc/{pid}/maps').read_text()) if searchable(r)]
        hits = search(pid, regions, patterns, int(request.get('align', 4)))
        return {'ok': True, 'hits': hits, 'capped': len(hits) >= MAX_HITS}, b''
    return {'ok': False, 'error': f'unknown op {op!r}'}, b''


def socket_path():
    base = os.environ.get('XDG_RUNTIME_DIR') or f'/tmp/turbohud-{os.getuid()}'
    return Path(base) / 'turbohud' / 'tsu-memory.sock'


def send_message(conn, header, payload=b''):
    body = json.dumps(header).encode()
    conn.sendall(struct.pack('<II', len(body), len(payload)) + body + payload)


def receive_exact(conn, size):
    chunks = []
    while size:
        chunk = conn.recv(min(size, 1 << 20))
        if not chunk:
            raise ConnectionError('closed')
        chunks.append(chunk)
        size -= len(chunk)
    return b''.join(chunks)


def receive_message(conn):
    body_size, payload_size = struct.unpack('<II', receive_exact(conn, 8))
    return json.loads(receive_exact(conn, body_size)), receive_exact(conn, payload_size)


def serve(pid, path, log_file):
    """Answer requests for process `pid` until the game quits. Only this user may connect."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    if path.exists():
        path.unlink()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old_mask = os.umask(0o177)
    try:
        server.bind(str(path))
    finally:
        os.umask(old_mask)
    server.listen(4)
    log([f'Serving read-only requests on {path}'], log_file)

    def client(conn):
        with conn:
            # Only processes of the same user, never anyone else.
            _pid, uid, _gid = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != os.getuid():
                return
            try:
                while True:
                    request, _ = receive_message(conn)
                    try:
                        header, payload = handle(pid, request)
                    except (OSError, KeyError, ValueError) as error:
                        header, payload = {'ok': False, 'error': str(error)}, b''
                    send_message(conn, header, payload)
            except (ConnectionError, struct.error):
                pass

    def accept_loop():
        while True:
            try:
                conn, _ = server.accept()
            except OSError:
                return
            threading.Thread(target=client, args=(conn,), daemon=True).start()

    threading.Thread(target=accept_loop, daemon=True).start()
    return server


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
    server = None
    try:
        log([f'Started: {" ".join(command)}'], path)
        pid = find_game(game.pid)
        if pid is None:
            log([f'FAIL: no {GAME_EXE} process appeared below the probe'], path)
        else:
            log([f'Found {GAME_EXE} as process {pid}'], path)
            # Give the game a moment to load its code.
            time.sleep(5.0)
            result = check_read(pid, GAME_CODE)
            log([result], path)
            if result.startswith('OK'):
                server = serve(pid, socket_path(), path)
    except Exception as error:  # The game must keep running whatever happens here.
        try:
            log([f'FAIL: probe error {error!r}'], path)
        except OSError:
            pass
    code = game.wait()
    if server is not None:
        server.close()
        try:
            socket_path().unlink()
        except OSError:
            pass
        log(['Game quit; socket closed'], path)
    return code


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
