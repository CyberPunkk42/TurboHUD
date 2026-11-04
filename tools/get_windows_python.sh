#!/bin/sh
# Make sure the portable Windows Python that runs TurboHUD's reader inside TSU's CrossOver
# bottle (turbohud/tsu/bottle.py) is in .buildtools/win-python (gitignored): a pinned
# download from python.org, checked against its SHA256. Nothing is installed into a bottle.
#   sh tools/get_windows_python.sh
set -eu

repo="$(cd "$(dirname "$0")/.." && pwd)"
version=3.13.17
zip_name="python-$version-embed-amd64.zip"
zip_sha256=9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38
python_dir="$repo/.buildtools/win-python"
download="$repo/.buildtools/download"

if [ -f "$python_dir/python.exe" ]; then
    exit 0
fi
mkdir -p "$download"
if [ ! -f "$download/$zip_name" ]; then
    echo "Downloading Windows Python $version from python.org ..."
    curl -sfL -o "$download/$zip_name" "https://www.python.org/ftp/python/$version/$zip_name"
fi
if ! echo "$zip_sha256  $download/$zip_name" | shasum -a 256 -c - >/dev/null; then
    echo "The download's SHA256 does not match; not using it." >&2
    rm -f "$download/$zip_name"
    exit 1
fi
mkdir -p "$python_dir"
unzip -q -o "$download/$zip_name" -d "$python_dir"
