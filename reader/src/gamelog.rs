//! Whether TSU has an event running, from its own log, as `turbohud/tsu/gamelog.py`.
//!
//! TSU writes "<time>: Event started." when a race (or hotlap) begins and "<time>: Event
//! ended." when it is over, into `log.txt` in each account's folder (dated copies in
//! `Logs/`). Only read, never written.
//!
//! A TSU may also stop writing them (a tester's Mac, 2026-11-11: the newest log days old, with
//! only "Log started." and "Log ended."). So a log says something only when it was written since
//! TSU started and names an event; else it is not known, and the search goes ahead.

use std::fs::{self, File};
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, SystemTime};

const TAIL: u64 = 64 * 1024; // the end of the log that is read: the latest lines
const STARTED: &[u8] = b"Event started.";
const ENDED: &[u8] = b"Event ended.";
const LOOK_EVERY: Duration = Duration::from_secs(5);
const SINCE_SLACK: Duration = Duration::from_secs(2); // a log may seem this much older than TSU's start

/// TSU's data folder on Windows (and in a CrossOver bottle), one folder per Steam account.
pub fn tsu_data() -> PathBuf {
    let home = std::env::var_os("USERPROFILE").unwrap_or_default();
    Path::new(&home).join("AppData").join("LocalLow").join("Turbo Sliders").join("Unlimited")
}

/// The most recently written log of any account, or None.
pub fn newest_log(folder: &Path) -> Option<PathBuf> {
    let mut logs = Vec::new();
    for account in fs::read_dir(folder).ok()?.flatten() {
        let account = account.path();
        logs.push(account.join("log.txt"));
        if let Ok(dated) = fs::read_dir(account.join("Logs")) {
            for entry in dated.flatten() {
                let name = entry.file_name().to_string_lossy().to_string();
                if name.starts_with("log.") && name.ends_with(".txt") && name.len() > 8 {
                    logs.push(entry.path());
                }
            }
        }
    }
    let mut newest: Option<(SystemTime, PathBuf)> = None;
    for path in logs {
        let Ok(info) = fs::metadata(&path) else { continue };
        if !info.is_file() {
            continue;
        }
        let Ok(written) = info.modified() else { continue };
        if newest.as_ref().is_none_or(|(best, _)| written > *best) {
            newest = Some((written, path));
        }
    }
    newest.map(|(_, path)| path)
}

fn rfind(text: &[u8], word: &[u8]) -> Option<usize> {
    text.windows(word.len()).rposition(|window| window == word)
}

/// True if the last event in the log text started and has not ended yet, false if it
/// ended, None if the text names no event at all.
pub fn running_in(text: &[u8]) -> Option<bool> {
    match (rfind(text, STARTED), rfind(text, ENDED)) {
        (Some(started), Some(ended)) => Some(started > ended),
        (Some(_), None) => Some(true),
        (None, Some(_)) => Some(false),
        (None, None) => None,
    }
}

/// `running()`: Some(true) while TSU's log says an event runs, Some(false) when it says
/// none does, None with no log to go by: none, one with no event in it, or one last written
/// before `since` (when TSU started; None where not known). Looks for the newest log at most
/// every 5 s, and reads its end only when it has changed.
pub struct EventLog {
    folder: PathBuf,
    since: Option<SystemTime>,
    log: Option<PathBuf>,
    looked: Option<Instant>,
    seen: Option<(PathBuf, u64, Option<SystemTime>)>,
    running: Option<bool>,
}

impl EventLog {
    pub fn new(folder: PathBuf, since: Option<SystemTime>) -> EventLog {
        EventLog { folder, since, log: None, looked: None, seen: None, running: None }
    }

    pub fn running(&mut self) -> Option<bool> {
        if self.looked.is_none_or(|at| at.elapsed() >= LOOK_EVERY) {
            self.looked = Some(Instant::now());
            self.log = newest_log(&self.folder);
        }
        let path = self.log.clone()?;
        let info = fs::metadata(&path).ok()?;
        if let (Some(since), Ok(written)) = (self.since, info.modified()) {
            if written + SINCE_SLACK < since {
                return None; // from an earlier run: TSU has not written it since it started
            }
        }
        let seen = (path.clone(), info.len(), info.modified().ok());
        if self.seen.as_ref() != Some(&seen) {
            let mut file = File::open(&path).ok()?;
            file.seek(SeekFrom::Start(info.len().saturating_sub(TAIL))).ok()?;
            let mut text = Vec::new();
            file.read_to_end(&mut text).ok()?;
            self.running = running_in(&text);
            self.seen = Some(seen);
        }
        self.running
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_last_event_decides() {
        assert_eq!(running_in(b"1: Event started.\n"), Some(true));
        assert_eq!(running_in(b"1: Event started.\n2: Event ended.\n"), Some(false));
        assert_eq!(running_in(b"1: Event started.\n2: Event ended.\n3: Event started.\n"), Some(true));
        assert_eq!(running_in(b"2: Event ended.\n"), Some(false));
    }

    #[test]
    fn a_log_without_an_event_says_nothing() {
        assert_eq!(running_in(b"1: Log started.\n2: Log ended.\n"), None);
    }

    #[test]
    fn a_log_from_before_tsu_started_says_nothing() {
        let folder = temporary("stale");
        let account = folder.join("76561197960265728");
        fs::create_dir_all(&account).unwrap();
        fs::write(account.join("log.txt"), "1: Event started.\n2: Event ended.\n").unwrap();
        let later = SystemTime::now() + Duration::from_secs(60);
        assert_eq!(EventLog::new(folder.clone(), Some(later)).running(), None);
        let earlier = SystemTime::now() - Duration::from_secs(60);
        assert_eq!(EventLog::new(folder.clone(), Some(earlier)).running(), Some(false));
        fs::remove_dir_all(&folder).unwrap();
    }

    fn temporary(name: &str) -> PathBuf {
        let folder = std::env::temp_dir().join(format!("turbohud-reader-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&folder);
        fs::create_dir_all(&folder).unwrap();
        folder
    }

    #[test]
    fn reads_the_newest_log_of_any_account() {
        let folder = temporary("gamelog");
        let account = folder.join("76561197960265728");
        fs::create_dir_all(account.join("Logs")).unwrap();
        fs::write(account.join("Logs").join("log.2026.11.10.txt"), "1: Event started.\n").unwrap();
        std::thread::sleep(Duration::from_millis(20));
        fs::write(account.join("log.txt"), "1: Event started.\n2: Event ended.\n").unwrap();
        assert_eq!(newest_log(&folder), Some(account.join("log.txt")));
        let mut log = EventLog::new(folder.clone(), None);
        assert_eq!(log.running(), Some(false));
        fs::write(account.join("log.txt"), "1: Event started.\n2: Event ended.\n3: Event started.\n").unwrap();
        assert_eq!(log.running(), Some(true)); // the same log, changed: read again
        fs::remove_dir_all(&folder).unwrap();
    }

    #[test]
    fn no_log_is_not_known() {
        let folder = temporary("nolog");
        assert_eq!(EventLog::new(folder.clone(), None).running(), None);
        assert_eq!(EventLog::new(folder.join("missing"), None).running(), None);
        fs::remove_dir_all(&folder).unwrap();
    }
}
