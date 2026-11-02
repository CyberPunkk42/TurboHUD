"""Starts TurboHUD's memory probe (turbohud/tsu/probe.py); see its notes.

This path is what Steam's launch option names, so it stays here:
    python3 /home/<user>/Work/workspace/tsu_repositories/TurboHUD/experiments/tsu_memory_probe.py %command%
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.tsu.probe import main

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
