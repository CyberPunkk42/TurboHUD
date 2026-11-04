#!/bin/sh
# Start TurboHUD from the source folder on macOS or Linux. The first run sets up PySide6
# in a virtual environment in .buildtools/venv (gitignored); later runs reuse it.
#   sh run_turbohud.sh [--move]
# Python is TURBOHUD_PYTHON if set, else Homebrew's python3.13, else python3 (3.10+).
set -eu

repo="$(cd "$(dirname "$0")" && pwd)"
venv="$repo/.buildtools/venv"
requirements="$repo/requirements.txt"

python="${TURBOHUD_PYTHON:-}"
if [ -z "$python" ]; then
    if [ -x /opt/homebrew/bin/python3.13 ]; then
        python=/opt/homebrew/bin/python3.13
    else
        python=python3
    fi
fi

if [ ! -x "$venv/bin/python" ]; then
    echo "Setting up Python with Qt in $venv ..."
    "$python" -m venv "$venv"
fi
# Install again whenever the pinned version changes.
if ! cmp -s "$requirements" "$venv/requirements.txt"; then
    "$venv/bin/python" -m pip install --quiet --disable-pip-version-check -r "$requirements"
    cp "$requirements" "$venv/requirements.txt"
fi

# On the Mac, live race data needs a Windows Python to run in TSU's CrossOver bottle. Without
# it (no network on the first start) the HUD still starts, and its tray icon says what is
# missing.
if [ "$(uname -s)" = Darwin ]; then
    sh "$repo/tools/get_windows_python.sh" || echo "No Windows Python: no live race data for now." >&2
fi

exec "$venv/bin/python" -B "$repo/launch_turbohud.py" "$@"
