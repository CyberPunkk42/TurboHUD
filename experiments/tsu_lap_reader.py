"""Print TSU's live lap data in the terminal, twice a second (Linux).

TurboHUD shows the same data in its overlay; this is for checking by hand. It reads
through the memory probe (TSU started from Steam with the launch option, see
turbohud/tsu/probe.py) and only reads. Run it while driving:

    python3 -B experiments/tsu_lap_reader.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core.race import RACING, WAITING_FOR_GAME, format_time
from turbohud.tsu.client import LiveRace

NOT_CONNECTED = 'TSU is not running through TurboHUD. Start TSU from Steam (with the launch option).'
NO_RACE = 'TSU is running, but no race is on yet (menu or loading). Waiting...'


def format_state(state):
    return (
        f'lap {state.lap_number}/{state.laps_to_finish}  '
        f'current {format_time(state.current_lap)}  last {format_time(state.last_lap)}  '
        f'best {format_time(state.best_lap)}  time left {format_time(state.time_left)}'
    )


def main(interval=0.5):
    live, shown = LiveRace(), None
    while True:
        live.step()
        snapshot = live.snapshot()
        if snapshot.status == RACING:
            print(format_state(snapshot.state), flush=True)
            shown = None
        else:
            text = NOT_CONNECTED if snapshot.status == WAITING_FOR_GAME else NO_RACE
            if text != shown:
                print(text + (f' ({snapshot.detail})' if snapshot.detail else ''), flush=True)
                shown = text
        time.sleep(interval)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
