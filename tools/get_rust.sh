#!/bin/sh
# Make sure the tools that build the reader inside TSU's CrossOver bottle (reader/, a
# Windows program in Rust) are in .buildtools (gitignored), never anywhere else:
# - Rust, through rustup, in .buildtools/rust (RUSTUP_HOME and CARGO_HOME point there; the
#   shell profile is not changed), with the x86_64-pc-windows-gnullvm target;
# - llvm-mingw, the linker for that target, in .buildtools/llvm-mingw: a pinned download
#   from its GitHub releases, checked against its SHA256.
# Then builds the reader: .buildtools/reader/turbohud-reader.exe.
#   sh tools/get_rust.sh            set up if needed, and build
#   sh tools/get_rust.sh --env      print the variables for running cargo by hand
set -eu

repo="$(cd "$(dirname "$0")/.." && pwd)"
tools="$repo/.buildtools"
download="$tools/download"
rust_version=1.99.1
target=x86_64-pc-windows-gnullvm
mingw_version=20261020
mingw_name="llvm-mingw-$mingw_version-ucrt-macos-universal"
mingw_sha256=e9c13e4ede38e715003ffc674d4d00a1088df8235439d1f0c16188ff0704c17e

export RUSTUP_HOME="$tools/rust/rustup"
export CARGO_HOME="$tools/rust/cargo"
export PATH="$CARGO_HOME/bin:$tools/llvm-mingw/bin:$PATH"
export CARGO_TARGET_X86_64_PC_WINDOWS_GNULLVM_LINKER="$tools/llvm-mingw/bin/x86_64-w64-mingw32-clang"
export CARGO_TARGET_DIR="$tools/reader-target"

if [ "${1:-}" = "--env" ]; then
    echo "export RUSTUP_HOME='$RUSTUP_HOME' CARGO_HOME='$CARGO_HOME' CARGO_TARGET_DIR='$CARGO_TARGET_DIR'"
    echo "export CARGO_TARGET_X86_64_PC_WINDOWS_GNULLVM_LINKER='$CARGO_TARGET_X86_64_PC_WINDOWS_GNULLVM_LINKER'"
    echo "export PATH='$CARGO_HOME/bin:$tools/llvm-mingw/bin':\"\$PATH\""
    exit 0
fi

if [ "$(uname -s)" != "Darwin" ]; then
    echo "This sets up the Mac build only (the reader runs in CrossOver on the Mac)." >&2
    exit 1
fi
mkdir -p "$download"

if [ ! -x "$CARGO_HOME/bin/cargo" ]; then
    init="$download/rustup-init"
    echo "Downloading rustup-init from rust-lang.org ..."
    curl -sfL -o "$init" "https://static.rust-lang.org/rustup/dist/aarch64-apple-darwin/rustup-init"
    sum="$(curl -sfL "https://static.rust-lang.org/rustup/dist/aarch64-apple-darwin/rustup-init.sha256" | cut -d' ' -f1)"
    if ! echo "$sum  $init" | shasum -a 256 -c - >/dev/null; then
        echo "rustup-init's SHA256 does not match; not using it." >&2
        rm -f "$init"
        exit 1
    fi
    chmod +x "$init"
    "$init" -y --no-modify-path --profile minimal --default-toolchain "$rust_version"
fi
rustup toolchain install "$rust_version" --profile minimal >/dev/null
rustup target add --toolchain "$rust_version" "$target" >/dev/null

if [ ! -x "$tools/llvm-mingw/bin/x86_64-w64-mingw32-clang" ]; then
    archive="$download/$mingw_name.tar.xz"
    if [ ! -f "$archive" ]; then
        echo "Downloading llvm-mingw $mingw_version from GitHub ..."
        curl -sfL -o "$archive" \
            "https://github.com/mstorsjo/llvm-mingw/releases/download/$mingw_version/$mingw_name.tar.xz"
    fi
    if ! echo "$mingw_sha256  $archive" | shasum -a 256 -c - >/dev/null; then
        echo "llvm-mingw's SHA256 does not match; not using it." >&2
        rm -f "$archive"
        exit 1
    fi
    rm -rf "$tools/llvm-mingw.partial"
    mkdir -p "$tools/llvm-mingw.partial"
    tar -xJf "$archive" -C "$tools/llvm-mingw.partial" --strip-components 1
    rm -rf "$tools/llvm-mingw"
    mv "$tools/llvm-mingw.partial" "$tools/llvm-mingw"
fi

cd "$repo/reader"
cargo +"$rust_version" build --release --locked --target "$target"
mkdir -p "$tools/reader"
cp "$CARGO_TARGET_DIR/$target/release/turbohud-reader.exe" "$tools/reader/turbohud-reader.exe"
echo "Built $tools/reader/turbohud-reader.exe"
