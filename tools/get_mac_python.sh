#!/bin/sh
# Make sure the Python that builds the Mac app is in .buildtools/mac-build-venv (gitignored).
# Homebrew's Python is made for the macOS it runs on, so an app built with it does not start
# on an older one; this one is a pinned download from python-build-standalone, checked against
# its SHA256, made to run on older systems too.
#   sh tools/get_mac_python.sh
#   .buildtools/mac-build-venv/bin/python tools/build_app.py --version YYYY.MM.DD --smoke
set -eu

repo="$(cd "$(dirname "$0")/.." && pwd)"
version=3.13.18
tag=20261026
archive="cpython-$version+$tag-aarch64-apple-darwin-install_only.tar.gz"
archive_sha256=e5af2fde6a937a0e0c795a0c595c4efb70578d57463a2657c819992b9b9acbac
url="https://github.com/astral-sh/python-build-standalone/releases/download/$tag/cpython-$version%2B$tag-aarch64-apple-darwin-install_only.tar.gz"
python_dir="$repo/.buildtools/mac-python"
venv="$repo/.buildtools/mac-build-venv"
download="$repo/.buildtools/download"

if [ ! -x "$python_dir/python/bin/python3" ]; then
    mkdir -p "$download"
    if [ ! -f "$download/$archive" ]; then
        echo "Downloading Python $version for building the Mac app ..."
        curl -sfL -o "$download/$archive" "$url"
    fi
    if ! echo "$archive_sha256  $download/$archive" | shasum -a 256 -c - >/dev/null; then
        echo "The download's SHA256 does not match; not using it." >&2
        rm -f "$download/$archive"
        exit 1
    fi
    mkdir -p "$python_dir"
    tar -xzf "$download/$archive" -C "$python_dir"
fi
if [ ! -x "$venv/bin/python" ]; then
    "$python_dir/python/bin/python3" -m venv "$venv"
fi
"$venv/bin/python" -m pip install --quiet --disable-pip-version-check -r "$repo/requirements-build.txt"
