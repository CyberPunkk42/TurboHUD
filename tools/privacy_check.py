"""Block pushes that contain the user's personal data (Git pre-push hook).

What counts as personal is worked out on this PC at run time, so the patterns are
never stored in the repository:
- every Steam account folder name under AppData/LocalLow/Turbo Sliders/Unlimited
  (TSU names them after the Steam ID), plus the short account number. On a Mac the
  same folders are searched inside every CrossOver bottle, on Linux in the native
  and Proton locations;
- the Windows user name and the computer name;
- terms listed in the clone's own `.git/privacy_terms.txt`, which is never committed.
  On a PC without TSU (a Mac, say), list the Steam ID and the Windows user name there,
  one per line. A line `allow: <text>` marks public text, such as the GitHub account
  name, that may appear even though it contains a term.

Install once per clone (Git runs hooks with its sh; on Windows that is Git's own):
    py -3 -B tools/privacy_check.py --install      (macOS/Linux: python3)
Check commits by hand:
    py -3 -B tools/privacy_check.py <commit-or-range> ...
Check release ZIPs (or any files) before publishing them, including every file inside:
    py -3 -B tools/privacy_check.py --files releases/<name>.zip ...
"""

import io
import os
import re
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

STEAM_BASE = 76561197960265728
# The hook runs its own copy in .git/hooks, so it works on every branch.
# `py` is Windows' Python launcher; elsewhere python3. If neither runs, the push fails.
HOOK = (
    '#!/bin/sh\n# Installed by tools/privacy_check.py --install\n'
    'check="$(dirname "$0")/privacy_check.py"\n'
    'if command -v py >/dev/null 2>&1; then exec py -3 -B "$check" --pre-push "$@"; fi\n'
    'exec python3 -B "$check" --pre-push "$@"\n'
)
TERMS_FILE = 'privacy_terms.txt'


def add_steam_id(terms, name):
    if name.isdigit() and int(name) > STEAM_BASE:
        terms.add(name)
        terms.add(str(int(name) - STEAM_BASE))


def local_terms(path):
    """Extra terms and allowed public text from the clone's untracked terms file."""
    terms, allowed = set(), set()
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines()
    except OSError:
        return terms, allowed
    for line in (line.strip() for line in lines):
        if not line or line.startswith('#'):
            continue
        if line.lower().startswith('allow:'):
            if line[6:].strip():
                allowed.add(line[6:].strip())
        elif line.isdigit():
            add_steam_id(terms, line)
        elif len(line) >= 4:
            terms.add(line)
    return terms, allowed


def terms_path():
    path = Path(git('rev-parse', '--git-path', TERMS_FILE).strip())
    return path if path.is_absolute() else Path.cwd() / path


def unlimited_folders():
    """TSU's per-account data folders (as in game_paths.py; this file must run on its own
    as a copy in .git/hooks, so it cannot import the app)."""
    home = Path.home()
    local = os.environ.get('LOCALAPPDATA')
    tail = Path('AppData', 'LocalLow', 'Turbo Sliders', 'Unlimited')
    yield (Path(local).parent if local else home / 'AppData') / 'LocalLow' / 'Turbo Sliders' / 'Unlimited'
    yield home / '.config' / 'unity3d' / 'Turbo Sliders' / 'Unlimited'
    for steam in (home / '.steam' / 'steam', home / '.local' / 'share' / 'Steam'):
        yield (
            steam / 'steamapps' / 'compatdata' / '1478340' / 'pfx' / 'drive_c' / 'users' / 'steamuser' / tail
        )
    bottles = home / 'Library' / 'Application Support' / 'CrossOver' / 'Bottles'
    yield from bottles.glob('*/drive_c/users/*/' + tail.as_posix())


def personal_terms():
    terms = set()
    for unlimited in unlimited_folders():
        try:
            for folder in unlimited.iterdir():
                add_steam_id(terms, folder.name)
        except OSError:
            pass
    for name in (Path.home().name, os.environ.get('USERNAME'), os.environ.get('COMPUTERNAME')):
        if name and len(name) >= 4:
            terms.add(name)
    return sorted(terms)


def git(*args, binary=False):
    # Git runs hooks from the top of the working tree; manual runs start there too.
    result = subprocess.run(['git', *args], capture_output=True, check=True)
    return result.stdout if binary else result.stdout.decode('utf-8', 'replace')


def blob_texts(commit, path):
    """The file's bytes, plus the contents of ZIP and zlib (.z) files."""
    yield from contents(git('show', commit + ':' + path, binary=True), path)


def contents(data, path):
    """`data`, unpacked when it is a zlib (.z) file; a ZIP also yields each entry's name
    and contents, unpacked the same way (.z entries, ZIPs inside ZIPs)."""
    yield data
    if path.endswith('.z'):
        try:
            yield zlib.decompress(data)
        except zlib.error:
            pass
    if data[:2] == b'PK':
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for name in archive.namelist():
                    yield name.encode()
                    if not name.endswith('/'):
                        yield from contents(archive.read(name), name)
        except zipfile.BadZipFile:
            pass


def searcher(terms, allowed=()):
    pattern = re.compile('|'.join(re.escape(term) for term in terms).encode(), re.IGNORECASE)
    # Allowed public text is blanked out first; a term elsewhere in the text still counts.
    longest = sorted(allowed, key=len, reverse=True)
    public = (
        re.compile('|'.join(re.escape(text) for text in longest).encode(), re.IGNORECASE) if longest else None
    )
    return lambda data: pattern.search(public.sub(b'', data) if public else data)


def file_findings(paths, terms, allowed=()):
    """Files (such as release ZIPs) that contain a term, by name or inside."""
    search = searcher(terms, allowed)
    return [
        str(path)
        for path in map(Path, paths)
        if search(path.name.encode()) or any(search(text) for text in contents(path.read_bytes(), path.name))
    ]


def findings(commits, terms, allowed=()):
    search = searcher(terms, allowed)
    found = []
    for commit in commits:
        short = commit[:10]
        if search(git('log', '-1', '--format=%an%n%ae%n%cn%n%ce%n%B', commit).encode()):
            found.append(short + ' commit message or author')
        changed = git(
            'diff-tree', '--root', '--no-commit-id', '-r', '--name-only', '--diff-filter=AMR', commit
        ).split('\n')
        for path in filter(None, changed):
            if search(path.encode()) or any(search(text) for text in blob_texts(commit, path)):
                found.append(short + ' ' + path)
    return found


def commits_to_push(lines, remote):
    commits = []
    for line in lines:
        parts = line.split()
        if len(parts) != 4 or set(parts[1]) == {'0'}:
            continue  # deleting a branch pushes nothing
        commits += git('rev-list', parts[1], '--not', '--remotes=' + remote).split()
    return list(dict.fromkeys(commits))


def main(argv):
    if argv[:1] == ['--install']:
        hooks = Path(git('rev-parse', '--git-path', 'hooks').strip())
        hooks = hooks if hooks.is_absolute() else Path.cwd() / hooks
        (hooks / 'privacy_check.py').write_bytes(Path(__file__).read_bytes())
        hook = hooks / 'pre-push'
        hook.write_text(HOOK, encoding='ascii', newline='\n')
        # macOS and Linux Git silently skip a hook that is not executable.
        hook.chmod(hook.stat().st_mode | 0o111)
        print('Installed', hook)
        return 0
    extra, allowed = local_terms(terms_path())
    terms = sorted(set(personal_terms()) | extra)
    if not any(term.isdigit() for term in terms):
        print(f'privacy check: no Steam ID known on this PC; add it to {terms_path()}', file=sys.stderr)
    if not terms:
        print('privacy check: no personal terms found on this PC; nothing to compare', file=sys.stderr)
        return 0
    if argv[:1] == ['--files']:
        found = file_findings(argv[1:], terms, allowed)
        for item in found:
            print('PERSONAL DATA in: ' + item, file=sys.stderr)
        if not found:
            print(f'privacy check: {len(argv[1:])} file(s) clean', file=sys.stderr)
        return 1 if found else 0
    if argv[:1] == ['--pre-push']:
        remote = argv[1] if len(argv) > 1 else 'origin'
        commits = commits_to_push(sys.stdin.read().splitlines(), remote)
    else:
        commits = []
        for item in argv:
            commits += git('rev-list', item).split() if '..' in item else [git('rev-parse', item).strip()]
    found = findings(commits, terms, allowed)
    if found:
        print('PUSH BLOCKED: personal data (Steam ID, user or computer name) in:', file=sys.stderr)
        for item in found:
            print('  ' + item, file=sys.stderr)
        return 1
    print(f'privacy check: {len(commits)} commit(s) clean', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
