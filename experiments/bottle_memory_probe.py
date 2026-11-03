"""Can a program inside TSU's CrossOver bottle read the game's memory? (macOS)

On the Mac, TSU runs as a Windows game inside CrossOver. A native Mac program would need
`task_for_pid` to read it, which macOS refuses for CrossOver's signed (hardened
runtime) Wine loader unless the system is weakened. Inside the bottle, though, every
program is a Windows program under the same Wine server, and Windows lets a program read
another of the same user (`OpenProcess` with PROCESS_VM_READ, `ReadProcessMemory`).

This probe runs inside the bottle (with a portable Windows Python, through
`run_bottle_memory_probe_mac.sh`), and only reads, with TurboHUD's own Windows reader
(`turbohud/tsu/winmemory.py`: page cache, paced search, TSU's log in the bottle):
1. finds TSU.exe, lists its memory and times plain reads,
2. connects as TurboHUD would and reads the race 20 times a second, if one is on:
   how long each read takes and how many reads reach the game.

It prints no player names or IDs. Windows only (also works on Windows itself).
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from turbohud.core.il2cpp import NotFound, ReadError
from turbohud.tsu import winmemory as wm


def timed(label, action, repeat):
    start = time.perf_counter()
    for _ in range(repeat):
        action()
    each = (time.perf_counter() - start) / repeat
    print(f'  {label}: {each * 1e6:.0f} us each ({repeat} times)')
    return each


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--reads', type=int, default=100, help='race reads at 20 a second')
    parser.add_argument('--wait', type=float, default=60, help='seconds to wait for a race')
    args = parser.parse_args()

    print(f'Python {sys.version.split()[0]}, {"under Wine" if wm.under_wine() else "on Windows"}.')
    pid = wm.find_process('TSU.exe')
    if pid is None:
        print('TSU.exe is not running in this bottle.')
        return 1
    process = wm.WindowsProcess(pid)
    started = time.perf_counter()
    regions = process.regions()
    took = time.perf_counter() - started
    total = sum(end - start for start, end, *_ in regions)
    data = sum(end - start for start, end, *_ in filter(wm.searchable, regions))
    print(
        f'1. TSU.exe (pid {pid}): {total / 2**30:.2f} GiB readable, '
        f'{data / 2**30:.2f} GiB of it searched; listed in {took:.2f} s.'
    )
    some = next(start for start, *_ in filter(wm.searchable, regions))
    timed('8 bytes', lambda: process.read(some, 8), 1000)
    timed('4 KiB', lambda: process.read(some, 4096), 300)
    process.close()

    print('2. Connecting as TurboHUD (paced search in Wine) ...')
    started = time.perf_counter()
    reader, process = wm.connect()
    print(f'   Connected in {time.perf_counter() - started:.1f} s (finds TS.Services).')
    cache = reader.cache
    give_up = time.perf_counter() + args.wait
    times, reads, state, first = [], [], None, None
    while len(times) < args.reads:
        began = time.perf_counter()
        before = cache.reads
        try:
            state = reader.read()
        except (NotFound, ReadError) as error:
            if time.perf_counter() > give_up:
                print(f'   No race within {args.wait:.0f} s: {error}')
                break
            time.sleep(0.5)
            continue
        took = time.perf_counter() - began
        if first is None:
            first = took
        else:
            times.append(took)
            reads.append(cache.reads - before)
        time.sleep(max(0.05 - took, 0))
    if times:
        times.sort()
        reads.sort()
        print(
            f'   First race read {first:.1f} s (with any search for an online race and the lookups '
            f'it keeps); then {len(times)} reads: median {times[len(times) // 2] * 1e3:.1f} ms, '
            f'slowest {times[-1] * 1e3:.1f} ms, {reads[len(reads) // 2]} reads of the game each (median).'
        )
        print(
            f'   Last: {state.laps_completed}/{state.laps_to_finish} laps done, '
            f'clock {state.clock / 10000:.1f} s, {len(state.players)} players, '
            f'position known: {state.position is not None}, car: {state.car is not None}.'
        )
        # Where what the searches found sits, to learn which memory to search first.
        regions = process.regions()
        searched = [r for r in regions if wm.searchable(r)]
        for label, address in (
            ('TS.Services class', reader.reader.services_class),
            ('TS.ClientEventController class', reader.reader._client_class),
            ('the online race controller', reader.reader._controller),
        ):
            if address:
                print(f'   {label}: {where(address, regions, searched)}')
    process.close()
    return 0


def where(address, regions, searched):
    """Which region holds `address`: its size, kind, and how much searched memory lies
    before it in address order."""
    for start, end, perms, _offset, _path in regions:
        if start <= address < end:
            before = sum(min(e, address) - s for s, e, *_ in searched if s < address)
            bigger = sum(1 for s, e, *_ in searched if e - s > end - start)
            return (
                f'in a {perms} region of {(end - start) / 2**20:.1f} MiB '
                f'({bigger} searched regions are bigger), {before / 2**30:.2f} GiB of searched memory before it'
            )
    return 'in no listed region'


if __name__ == '__main__':
    sys.exit(main())
