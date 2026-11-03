#!/bin/sh
# Run bottle_memory_probe.py inside TSU's CrossOver bottle, using a portable Windows Python
# kept in .buildtools/win-python (gitignored). Nothing is installed into the bottle.
#   sh experiments/run_bottle_memory_probe_mac.sh [--reads N]
# The bottle is "Steam" unless TURBOHUD_BOTTLE names another one.
set -eu

repo="$(cd "$(dirname "$0")/.." && pwd)"
bottle="${TURBOHUD_BOTTLE:-Steam}"
version=3.13.17
zip_name="python-$version-embed-amd64.zip"
zip_sha256=9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38
python_dir="$repo/.buildtools/win-python"

wine=""
for app in "$HOME/Applications/CrossOver.app" /Applications/CrossOver.app \
    "$(mdfind "kMDItemCFBundleIdentifier == 'com.codeweavers.CrossOver'" | head -n 1)"; do
    if [ -n "$app" ] && [ -x "$app/Contents/SharedSupport/CrossOver/bin/wine" ]; then
        wine="$app/Contents/SharedSupport/CrossOver/bin/wine"
        break
    fi
done
if [ -z "$wine" ]; then
    echo "CrossOver was not found." >&2
    exit 1
fi

if [ ! -f "$python_dir/python.exe" ]; then
    download="$repo/.buildtools/download"
    mkdir -p "$download"
    echo "Downloading Windows Python $version from python.org ..."
    curl -sfL -o "$download/$zip_name" "https://www.python.org/ftp/python/$version/$zip_name"
    if ! echo "$zip_sha256  $download/$zip_name" | shasum -a 256 -c - >/dev/null; then
        echo "The download's SHA256 does not match; not using it." >&2
        rm -f "$download/$zip_name"
        exit 1
    fi
    mkdir -p "$python_dir"
    unzip -q -o "$download/$zip_name" -d "$python_dir"
fi

# Wine sees the Mac's file system as drive Z:.
probe="Z:$(printf '%s' "$repo/experiments/bottle_memory_probe.py" | tr / '\\')"
"$wine" --bottle "$bottle" "$python_dir/python.exe" -B "$probe" "$@" 2>&1 | grep -v -i fixme
