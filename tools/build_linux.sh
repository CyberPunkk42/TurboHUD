#!/bin/sh
# Build the Linux app in an Ubuntu 22.04 container, so it starts on every Linux with glibc 2.35
# or newer (built on a new distro it would start only there). PySide6 6.11 itself needs 2.34.
#
#     sh tools/build_linux.sh 2026.11.14           (Podman, or Docker for a user in its group)
#     sudo sh tools/build_linux.sh 2026.11.14      (Docker otherwise; the files still become yours)
#
# The container gets the committed files only (git archive HEAD: nothing local or untracked),
# runs tools/build_app.py --smoke there and puts the archive and its .sha256 into releases/.
# Nothing is installed on this PC; Docker or Podman keeps the image (turbohud-linux-build).
set -eu
cd "$(dirname "$0")/.."
version=${1:-dev}
engine=${CONTAINER_ENGINE:-$(command -v podman || command -v docker || true)}
if [ -z "$engine" ]; then
    echo 'Needs Podman or Docker.' >&2
    exit 1
fi
image=turbohud-linux-build:22.04
owner="${SUDO_UID:-$(id -u)}:${SUDO_GID:-$(id -g)}"
mkdir -p releases
chown "$owner" releases 2>/dev/null || true  # under sudo mkdir made it root's

# Python 3.13 from deadsnakes; the libraries Qt's X11 and Wayland plugins load, which
# PyInstaller packs into the app (as in .github/workflows/build.yml); binutils for PyInstaller.
"$engine" build -t "$image" - <<'EOF'
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends software-properties-common gpg-agent \
    && add-apt-repository -y ppa:deadsnakes/ppa && apt-get update \
    && apt-get install -y --no-install-recommends python3.13 python3.13-venv python3.13-dev binutils \
       libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 \
       libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-shape0 libxcb-util1 \
       libxcb-xkb1 libwayland-client0 libwayland-cursor0 libwayland-egl1 \
    && rm -rf /var/lib/apt/lists/*
EOF

git archive --format=tar HEAD | "$engine" run --rm -i \
    -e VERSION="$version" -e OWNER="$owner" -e QT_QPA_PLATFORM=offscreen \
    -v "$PWD/releases:/out" "$image" sh -euc '
        mkdir /work && cd /work && tar -x
        python3.13 -m venv /venv
        /venv/bin/pip install --quiet --disable-pip-version-check -r requirements-build.txt
        /venv/bin/python -B tools/build_app.py --version "$VERSION" --smoke
        for file in releases/TurboHUD-*; do
            cp "$file" /out/ && chown "$OWNER" "/out/$(basename "$file")"
        done
        echo "glibc in the build: $(ldd --version | head -n 1)"
    '
