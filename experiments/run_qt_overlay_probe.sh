#!/bin/sh
# Run qt_overlay_probe.py on macOS or Linux. The first run sets up PySide6 in a virtual
# environment in .buildtools/qt-venv (gitignored); later runs reuse it.
#   sh experiments/run_qt_overlay_probe.sh [probe options, e.g. --move --x 200]
# Python is TURBOKIT_PYTHON if set, else Homebrew's python3.13, else python3 (3.10+).
set -eu

repo="$(cd "$(dirname "$0")/.." && pwd)"
venv="$repo/.buildtools/qt-venv"
requirements="$repo/experiments/requirements-qt.txt"

python="${TURBOKIT_PYTHON:-}"
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
if ! cmp -s "$requirements" "$venv/requirements-qt.txt"; then
    "$venv/bin/python" -m pip install --quiet --disable-pip-version-check -r "$requirements"
    cp "$requirements" "$venv/requirements-qt.txt"
fi

exec "$venv/bin/python" -B "$repo/experiments/qt_overlay_probe.py" "$@"
