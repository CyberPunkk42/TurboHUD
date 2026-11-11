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
# On Windows (since 2026-11-12, in Git Bash) the same with the Windows downloads of rustup and
# llvm-mingw: the same Rust and target, so the reader is built as on the Mac. No Visual Studio
# is needed, as the toolchain's host is that target too.
set -eu

case "$(uname -s)" in
    Darwin) system=mac ;;
    MINGW* | MSYS*) system=windows ;;
    *) system=other ;;
esac
if [ "$system" = windows ]; then
    repo="$(cd "$(dirname "$0")/.." && pwd -W)"  # C:/..., as the Windows programs below want it
    mingw_name="llvm-mingw-20261020-ucrt-x86_64"
    mingw_kind=zip
    mingw_sha256=fd5462b7f5d93b2ff981fcd3f9c7e427e47f3203c64ea91c27bcc444eebd74cd  # GitHub's digest
    rustup_url="https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe"
    exe=.exe
else
    repo="$(cd "$(dirname "$0")/.." && pwd)"
    mingw_name="llvm-mingw-20261020-ucrt-macos-universal"
    mingw_kind=tar.xz
    mingw_sha256=e9c13e4ede38e715003ffc674d4d00a1088df8235439d1f0c16188ff0704c17e
    rustup_url="https://static.rust-lang.org/rustup/dist/aarch64-apple-darwin/rustup-init"
    exe=
fi
tools="$repo/.buildtools"
download="$tools/download"
rust_version=1.99.1
target=x86_64-pc-windows-gnullvm
mingw_version=20261020

export RUSTUP_HOME="$tools/rust/rustup"
export CARGO_HOME="$tools/rust/cargo"
# The shell's own paths for PATH (Git Bash wants /c/..., not C:/...).
shell_tools="$(cd "$(dirname "$0")/.." && pwd)/.buildtools"
export PATH="$shell_tools/rust/cargo/bin:$shell_tools/llvm-mingw/bin:$PATH"
export CARGO_TARGET_X86_64_PC_WINDOWS_GNULLVM_LINKER="$tools/llvm-mingw/bin/x86_64-w64-mingw32-clang$exe"
export CARGO_TARGET_DIR="$tools/reader-target"

if [ "${1:-}" = "--env" ]; then
    echo "export RUSTUP_HOME='$RUSTUP_HOME' CARGO_HOME='$CARGO_HOME' CARGO_TARGET_DIR='$CARGO_TARGET_DIR'"
    echo "export CARGO_TARGET_X86_64_PC_WINDOWS_GNULLVM_LINKER='$CARGO_TARGET_X86_64_PC_WINDOWS_GNULLVM_LINKER'"
    echo "export PATH='$shell_tools/rust/cargo/bin:$shell_tools/llvm-mingw/bin':\"\$PATH\""
    exit 0
fi

if [ "$system" = other ]; then
    echo "This sets up the Mac and Windows builds only (the reader is a Windows program)." >&2
    exit 1
fi
mkdir -p "$download"

check_sha256() {  # expected-sum file
    if command -v shasum >/dev/null 2>&1; then
        echo "$1  $2" | shasum -a 256 -c - >/dev/null
    else
        echo "$1  $2" | sha256sum -c - >/dev/null
    fi
}

if [ ! -x "$CARGO_HOME/bin/cargo$exe" ]; then
    init="$download/rustup-init$exe"
    echo "Downloading rustup-init from rust-lang.org ..."
    curl -sfL -o "$init" "$rustup_url"
    sum="$(curl -sfL "$rustup_url.sha256" | cut -d' ' -f1)"
    if ! check_sha256 "$sum" "$init"; then
        echo "rustup-init's SHA256 does not match; not using it." >&2
        rm -f "$init"
        exit 1
    fi
    chmod +x "$init"
    if [ "$system" = windows ]; then
        "$init" -y --no-modify-path --profile minimal --default-toolchain "$rust_version" --default-host "$target"
    else
        "$init" -y --no-modify-path --profile minimal --default-toolchain "$rust_version"
    fi
fi
rustup toolchain install "$rust_version" --profile minimal >/dev/null
rustup target add --toolchain "$rust_version" "$target" >/dev/null

if [ ! -x "$tools/llvm-mingw/bin/x86_64-w64-mingw32-clang$exe" ]; then
    archive="$download/$mingw_name.$mingw_kind"
    if [ ! -f "$archive" ]; then
        echo "Downloading llvm-mingw $mingw_version from GitHub ..."
        curl -sfL -o "$archive" \
            "https://github.com/mstorsjo/llvm-mingw/releases/download/$mingw_version/$mingw_name.$mingw_kind"
    fi
    if ! check_sha256 "$mingw_sha256" "$archive"; then
        echo "llvm-mingw's SHA256 does not match; not using it." >&2
        rm -f "$archive"
        exit 1
    fi
    rm -rf "$tools/llvm-mingw.partial" "$tools/llvm-mingw"
    mkdir -p "$tools/llvm-mingw.partial"
    if [ "$mingw_kind" = zip ]; then
        # The zip holds one folder named after it: that folder, renamed once, is the result
        # (a second rename of freshly unpacked programs was refused on Windows, 2026-11-12).
        unzip -q "$archive" -d "$tools/llvm-mingw.partial"
        mv "$tools/llvm-mingw.partial/$mingw_name" "$tools/llvm-mingw"
        rm -rf "$tools/llvm-mingw.partial"
    else
        tar -xJf "$archive" -C "$tools/llvm-mingw.partial" --strip-components 1
        mv "$tools/llvm-mingw.partial" "$tools/llvm-mingw"
    fi
fi

cd "$repo/reader"
cargo +"$rust_version" build --release --locked --target "$target"
mkdir -p "$tools/reader"
cp "$CARGO_TARGET_DIR/$target/release/turbohud-reader.exe" "$tools/reader/turbohud-reader.exe"
echo "Built $tools/reader/turbohud-reader.exe"
