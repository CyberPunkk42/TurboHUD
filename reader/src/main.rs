//! TurboHUD's reader inside TSU's CrossOver bottle, in Rust: the same answers over the
//! same pipe as `turbohud/tsu/bottle_reader.py`, without a Windows Python.
//!
//! macOS refuses a Mac program access to TSU's memory, but a Windows program in the same
//! bottle may read it. TurboHUD (`turbohud/tsu/bottle.py`) starts this program there and
//! asks it through its standard input and output. Only TurboHUD holds the pipe, so there
//! is no port and no secret, and nothing else can ask.
//!
//! It can only read: the memory list, bytes (also many pages at once), the game's metadata
//! file, whether TSU's log says an event runs, and a search that goes on only as far as its
//! hits are taken. It ends when the pipe closes (TurboHUD quit or was killed) or TSU has
//! quit. Built by `tools/get_rust.sh`; the pure parts test on any system (`cargo test`).

// On other systems only the tests use these: the program itself runs on Windows.
#![cfg_attr(not(windows), allow(dead_code))]

mod gamelog;
mod json;
mod memory;
mod service;
#[cfg(windows)]
mod win32;

#[cfg(windows)]
fn main() {
    std::process::exit(run());
}

#[cfg(windows)]
fn run() -> i32 {
    use std::fs::File;
    use std::io::{BufReader, Write};
    use std::os::windows::io::{AsRawHandle, FromRawHandle};

    use json::{object, Value};
    use memory::WINE_SEARCH_SHARE;
    use service::{failure, pack, Service, READY};

    // Standard output is the pipe, written whole, a message at a time: no line buffering,
    // and nothing else may write there (errors go to standard error, the reader's log).
    let mut sink = unsafe { File::from_raw_handle(std::io::stdout().as_raw_handle()) };
    let mut source = BufReader::with_capacity(1 << 16, std::io::stdin());
    let mut say = |header: &Value| {
        let _ = sink.write_all(&pack(header, b"")).and_then(|_| sink.flush());
    };
    let Some(process_id) = win32::find_process("TSU.exe") else {
        say(&failure("TSU.exe is not running in this bottle"));
        return 1;
    };
    let process = match win32::WindowsProcess::open(process_id) {
        Ok(process) => process,
        Err(error) => {
            say(&failure(&error.to_string()));
            return 1;
        }
    };
    say(&object([("ok", Value::Bool(true)), ("ready", Value::Str(READY.into()))]));
    let mut events = gamelog::EventLog::new(gamelog::tsu_data());
    let share = if win32::under_wine() { WINE_SEARCH_SHARE } else { 1.0 };
    let process_ref = &process;
    let mut service = Service::new(
        process_ref,
        Box::new(move || {
            let image = process_ref.image_path()?;
            let folder = image.parent().map(|p| p.to_path_buf()).unwrap_or_default();
            Ok(folder.join("TSU_Data").join("il2cpp_data").join("Metadata").join("global-metadata.dat"))
        }),
        Box::new(move || events.running()),
        share,
    );
    match service.serve(&mut source, &mut sink) {
        Ok(()) => 0,
        Err(error) => {
            eprintln!("turbohud-reader: {error}");
            1
        }
    }
}

#[cfg(not(windows))]
fn main() {
    eprintln!("turbohud-reader runs inside TSU's CrossOver bottle: build it with tools/get_rust.sh");
    std::process::exit(1);
}
