//! The pipe's messages and the answers to them, as `turbohud/tsu/bottle_reader.py`.
//!
//! A message is two little-endian u32 sizes (of a JSON header and of raw bytes after it),
//! the header, then the bytes. TurboHUD (`turbohud/tsu/bottle.py`) asks, one question at a
//! time; every question gets one answer, also when it fails.

use std::collections::HashSet;
use std::io::{self, Read, Write};
use std::path::PathBuf;
use std::time::{Duration, Instant};

use crate::json::{self, object, Value};
use crate::memory::{metadata_base, read_pages, Process, Search, PAGE};

pub const READY: &str = "turbohud-bottle-reader"; // first message: the pipe reaches the reader
pub const MAX_READ: u64 = 64 * 1024 * 1024;
const MAX_HEADER: u32 = 16 * 1024 * 1024; // a request with every page allowed is about 1.5 MiB

pub fn pack(header: &Value, payload: &[u8]) -> Vec<u8> {
    let body = header.to_json().into_bytes();
    let mut out = Vec::with_capacity(8 + body.len() + payload.len());
    out.extend_from_slice(&(body.len() as u32).to_le_bytes());
    out.extend_from_slice(&(payload.len() as u32).to_le_bytes());
    out.extend_from_slice(&body);
    out.extend_from_slice(payload);
    out
}

/// (header, payload) of the next message; None once the stream has ended.
pub fn receive(source: &mut dyn Read) -> io::Result<Option<(Value, Vec<u8>)>> {
    let mut sizes = [0u8; 8];
    if !read_all(source, &mut sizes)? {
        return Ok(None);
    }
    let body_size = u32::from_le_bytes(sizes[..4].try_into().unwrap());
    let payload_size = u32::from_le_bytes(sizes[4..].try_into().unwrap());
    if body_size > MAX_HEADER || payload_size as u64 > MAX_READ {
        return Err(io::Error::new(io::ErrorKind::InvalidData, "a message too large"));
    }
    let mut body = vec![0; body_size as usize];
    let mut payload = vec![0; payload_size as usize];
    if !read_all(source, &mut body)? || !read_all(source, &mut payload)? {
        return Ok(None);
    }
    let header = json::parse(&body).map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
    Ok(Some((header, payload)))
}

/// Fill `buffer`; false if the stream ended first.
fn read_all(source: &mut dyn Read, buffer: &mut [u8]) -> io::Result<bool> {
    let mut done = 0;
    while done < buffer.len() {
        match source.read(&mut buffer[done..]) {
            Ok(0) => return Ok(false),
            Ok(n) => done += n,
            Err(e) if e.kind() == io::ErrorKind::Interrupted => {}
            Err(e) => return Err(e),
        }
    }
    Ok(true)
}

pub fn failure(error: &str) -> Value {
    object([("ok", Value::Bool(false)), ("error", Value::Str(error.to_string()))])
}

/// Answers one request at a time for one open process.
pub struct Service<'a> {
    pub process: &'a dyn Process,
    pub metadata_file: Box<dyn Fn() -> io::Result<PathBuf> + 'a>,
    pub event_running: Box<dyn FnMut() -> Option<bool> + 'a>,
    pub share: f64,
    pub sleep: Box<dyn FnMut(Duration) + 'a>,
    search: Option<Search>,
    breaks: HashSet<(u64, u64)>, // gaps a merged read failed across: see read_pages
}

fn number(request: &Value, key: &str) -> Result<i128, String> {
    request.get(key).and_then(Value::as_int).ok_or_else(|| format!("'{key}'"))
}

fn address(request: &Value, key: &str) -> Result<u64, String> {
    u64::try_from(number(request, key)?).map_err(|_| format!("{key} out of range"))
}

impl<'a> Service<'a> {
    pub fn new(
        process: &'a dyn Process,
        metadata_file: Box<dyn Fn() -> io::Result<PathBuf> + 'a>,
        event_running: Box<dyn FnMut() -> Option<bool> + 'a>,
        share: f64,
    ) -> Service<'a> {
        Service {
            process,
            metadata_file,
            event_running,
            share,
            sleep: Box::new(std::thread::sleep),
            search: None,
            breaks: HashSet::new(),
        }
    }

    /// (header, payload) for one request; Err for a request that failed (the answer then
    /// says so, unless TSU has quit).
    pub fn handle(&mut self, request: &Value) -> Result<(Value, Vec<u8>), String> {
        let ok = || ("ok".to_string(), Value::Bool(true));
        let op = request.get("op").and_then(Value::as_str).unwrap_or("");
        match op {
            "maps" => {
                let regions = self
                    .process
                    .regions()
                    .into_iter()
                    .map(|r| {
                        Value::List(vec![
                            Value::Int(r.start as i128),
                            Value::Int(r.end as i128),
                            Value::Str(r.perms),
                            Value::Int(0),
                            Value::Str(r.path),
                        ])
                    })
                    .collect();
                Ok((Value::Object(vec![ok(), ("regions".into(), Value::List(regions))]), Vec::new()))
            }
            "read" => {
                let size = number(request, "size")?;
                if !(0 < size && size <= MAX_READ as i128) {
                    return Ok((failure("size out of range"), Vec::new()));
                }
                let began = Instant::now();
                let data = self.process.read(address(request, "address")?, size as usize).map_err(|e| e.to_string())?;
                let took = began.elapsed().as_secs_f64();
                Ok((Value::Object(vec![ok(), ("took".into(), Value::Float(took))]), data))
            }
            "read_pages" => {
                // Many 4 KiB pages in one answer: those that could be read, in the order of
                // `got`, with pages close together read in one call.
                let list = request.get("pages").and_then(Value::as_list).ok_or("'pages'")?;
                let mut pages = Vec::with_capacity(list.len());
                for item in list {
                    match item.as_int() {
                        Some(n) if n >= 0 && n <= (u64::MAX / PAGE) as i128 => pages.push(n as u64),
                        Some(_) => return Ok((failure("pages out of range"), Vec::new())),
                        None => return Err("a page is not a number".into()),
                    }
                }
                if pages.is_empty() || pages.len() as u64 > MAX_READ / PAGE {
                    return Ok((failure("pages out of range"), Vec::new()));
                }
                let began = Instant::now();
                let process = self.process;
                let (found, calls) = read_pages(&|a, s| process.read(a, s), &pages, &mut self.breaks);
                let took = began.elapsed().as_secs_f64();
                let got = found.keys().map(|&n| Value::Int(n as i128)).collect();
                let payload = found.into_values().flatten().collect();
                let header = Value::Object(vec![
                    ok(),
                    ("got".into(), Value::List(got)),
                    ("took".into(), Value::Float(took)),
                    ("calls".into(), Value::Int(calls as i128)),
                ]);
                Ok((header, payload))
            }
            "metadata" => {
                let path = (self.metadata_file)().map_err(|e| e.to_string())?;
                let metadata = std::fs::read(&path).map_err(|e| format!("{e}: {}", path.display()))?;
                match metadata_base(&self.process.regions(), self.process, &metadata) {
                    Some(base) => Ok((Value::Object(vec![ok(), ("base".into(), Value::Int(base as i128))]), metadata)),
                    None => {
                        let mut answer = failure("the game metadata is not mapped yet");
                        if let Value::Object(items) = &mut answer {
                            items.push(("not_ready".into(), Value::Bool(true)));
                        }
                        Ok((answer, Vec::new()))
                    }
                }
            }
            "event_running" => {
                let running = match (self.event_running)() {
                    Some(running) => Value::Bool(running),
                    None => Value::Null,
                };
                Ok((Value::Object(vec![ok(), ("running".into(), running)]), Vec::new()))
            }
            "search" => {
                // Starts a search and replaces any earlier one, which may have been left
                // after its first good hit; nothing is read until the first search_next.
                let list = request.get("regions").and_then(Value::as_list).ok_or("'regions'")?;
                let mut regions = Vec::with_capacity(list.len());
                for item in list {
                    let pair = item.as_list().filter(|p| p.len() >= 2).ok_or("a region is not [start, end]")?;
                    let start = pair[0].as_int().and_then(|n| u64::try_from(n).ok()).ok_or("bad region start")?;
                    let end = pair[1].as_int().and_then(|n| u64::try_from(n).ok()).ok_or("bad region end")?;
                    regions.push((start, end));
                }
                let value = number(request, "value")?;
                let value = u64::try_from(value).map_err(|_| "value out of range")?;
                let first = match request.get("first") {
                    None | Some(Value::Null) => None,
                    Some(_) => Some(address(request, "first")?),
                };
                self.search = Some(Search::new(&regions, value, self.share, first));
                Ok((Value::Object(vec![ok()]), Vec::new()))
            }
            "search_next" => {
                let process = self.process;
                let hit = match self.search.as_mut() {
                    Some(search) => search.next_hit(&|a, s| process.read(a, s), &mut *self.sleep),
                    None => None,
                };
                let hit = hit.map_or(Value::Null, |h| Value::Int(h as i128));
                Ok((Value::Object(vec![ok(), ("hit".into(), hit)]), Vec::new()))
            }
            _ => {
                let name = request.get("op").map_or("None".to_string(), |v| match v {
                    Value::Str(s) => format!("'{s}'"),
                    other => other.to_json(),
                });
                Ok((failure(&format!("unknown op {name}")), Vec::new()))
            }
        }
    }

    /// Answer until the pipe closes, or until a request fails because TSU has quit
    /// (TurboHUD then sees the pipe close, and looks for the game again).
    pub fn serve(&mut self, source: &mut dyn Read, sink: &mut dyn Write) -> io::Result<()> {
        while let Some((request, _payload)) = receive(source)? {
            let (header, payload) = match self.handle(&request) {
                Ok(answer) => answer,
                Err(error) => {
                    if !self.process.alive() {
                        return Ok(());
                    }
                    (failure(&error), Vec::new())
                }
            };
            sink.write_all(&pack(&header, &payload))?;
            sink.flush()?;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::memory::{region, Region, MEM_PRIVATE};
    use std::cell::{Cell, RefCell};
    use std::io::Cursor;

    /// Bytes at `base`, as `win32::WindowsProcess` reads them; counts reads.
    struct FakeProcess {
        base: u64,
        data: Vec<u8>,
        alive: Cell<bool>,
        reads: Cell<usize>,
        regions: RefCell<Option<Vec<Region>>>,
    }

    impl FakeProcess {
        fn new(base: u64, data: Vec<u8>) -> FakeProcess {
            FakeProcess { base, data, alive: Cell::new(true), reads: Cell::new(0), regions: RefCell::new(None) }
        }
    }

    impl Process for FakeProcess {
        fn read(&self, address: u64, size: usize) -> io::Result<Vec<u8>> {
            self.reads.set(self.reads.get() + 1);
            if address < self.base || address - self.base + size as u64 > self.data.len() as u64 {
                return Err(io::Error::other(format!("cannot read {size} bytes at {address:#x}")));
            }
            let start = (address - self.base) as usize;
            Ok(self.data[start..start + size].to_vec())
        }
        fn regions(&self) -> Vec<Region> {
            self.regions.borrow().clone().unwrap_or_else(|| {
                vec![region(self.base, self.data.len() as u64, 0x04, MEM_PRIVATE, "")]
            })
        }
        fn alive(&self) -> bool {
            self.alive.get()
        }
    }

    fn service(process: &FakeProcess) -> Service<'_> {
        Service::new(process, Box::new(|| Err(io::Error::other("no file"))), Box::new(|| Some(false)), 1.0)
    }

    fn ask(service: &mut Service, request: &str) -> (Value, Vec<u8>) {
        service.handle(&json::parse(request.as_bytes()).unwrap()).unwrap()
    }

    #[test]
    fn maps_are_lists_as_python_gives_them() {
        let process = FakeProcess::new(0x10000, vec![0; 0x100]);
        let (header, _) = ask(&mut service(&process), r#"{"op": "maps"}"#);
        assert_eq!(header.to_json(), r#"{"ok": true, "regions": [[65536, 65792, "rw-p", 0, "[heap]"]]}"#);
    }

    #[test]
    fn a_read_gives_the_bytes() {
        let process = FakeProcess::new(0x10000, (0..=255).collect());
        let (header, payload) = ask(&mut service(&process), r#"{"op": "read", "address": 65552, "size": 4}"#);
        assert_eq!(header.get("ok"), Some(&Value::Bool(true)));
        assert!(matches!(header.get("took"), Some(Value::Float(t)) if *t >= 0.0));
        assert_eq!(payload, vec![16, 17, 18, 19]);
        let (header, _) = ask(&mut service(&process), r#"{"op": "read", "address": 65552, "size": 0}"#);
        assert_eq!(header.to_json(), r#"{"ok": false, "error": "size out of range"}"#);
    }

    #[test]
    fn read_pages_answers_as_python_does() {
        let data: Vec<u8> = (0..4 * PAGE as usize).map(|i| (i % 256) as u8).collect();
        let process = FakeProcess::new(0x10000, data.clone()); // pages 16 to 19
        let (header, payload) = ask(&mut service(&process), r#"{"op": "read_pages", "pages": [19, 16, 99]}"#);
        assert_eq!(keys(&header), ["calls", "got", "ok", "took"]);
        assert_eq!(header.get("got").unwrap().to_json(), "[16, 19]");
        assert_eq!(header.get("calls"), Some(&Value::Int(2))); // 16 and 19 in one read, 99 alone
        let page = PAGE as usize;
        assert_eq!(payload, [&data[..page], &data[3 * page..]].concat());
        for request in [r#"{"op": "read_pages", "pages": []}"#, r#"{"op": "read_pages", "pages": [-1]}"#] {
            let (header, _) = ask(&mut service(&process), request);
            assert_eq!(header.to_json(), r#"{"ok": false, "error": "pages out of range"}"#);
        }
    }

    fn keys(value: &Value) -> Vec<String> {
        json::keys(value).into_keys().collect()
    }

    #[test]
    fn read_pages_remembers_a_gap_it_could_not_read_across() {
        struct Holed(FakeProcess);
        impl Process for Holed {
            fn read(&self, address: u64, size: usize) -> io::Result<Vec<u8>> {
                if address <= 18 * PAGE && 18 * PAGE < address + size as u64 {
                    return Err(io::Error::other("page 18 is not there"));
                }
                self.0.read(address, size)
            }
            fn regions(&self) -> Vec<Region> {
                self.0.regions()
            }
            fn alive(&self) -> bool {
                true
            }
        }
        let process = Holed(FakeProcess::new(0x10000, vec![0; 5 * PAGE as usize])); // pages 16 to 20
        let mut service = Service::new(&process, Box::new(|| Err(io::Error::other("-"))), Box::new(|| None), 1.0);
        let request = r#"{"op": "read_pages", "pages": [16, 17, 19, 20]}"#;
        let (first, _) = ask(&mut service, request);
        assert_eq!(first.get("got").unwrap().to_json(), "[16, 17, 19, 20]");
        assert_eq!(first.get("calls"), Some(&Value::Int(3)));
        let (second, _) = ask(&mut service, request);
        assert_eq!(second.get("calls"), Some(&Value::Int(2)));
    }

    #[test]
    fn the_metadata_is_found_by_its_first_bytes() {
        let folder = std::env::temp_dir().join(format!("turbohud-reader-metadata-{}", std::process::id()));
        std::fs::create_dir_all(&folder).unwrap();
        let file = folder.join("global-metadata.dat");
        let metadata: Vec<u8> = (0..200).map(|i| (i * 7 % 251) as u8).collect();
        std::fs::write(&file, &metadata).unwrap();
        let mut data = vec![0u8; 2 * PAGE as usize];
        data[PAGE as usize..PAGE as usize + 200].copy_from_slice(&metadata);
        let process = FakeProcess::new(0x10000, data);
        *process.regions.borrow_mut() = Some(vec![
            region(0x10000, PAGE, 0x02, 0x40000, ""),
            region(0x11000, PAGE, 0x02, 0x40000, ""),
        ]);
        let shown = file.clone();
        let mut service = Service::new(&process, Box::new(move || Ok(shown.clone())), Box::new(|| None), 1.0);
        let (header, payload) = ask(&mut service, r#"{"op": "metadata"}"#);
        assert_eq!(header.to_json(), r#"{"ok": true, "base": 69632}"#);
        assert_eq!(payload, metadata);
        *process.regions.borrow_mut() = Some(vec![region(0x10000, PAGE, 0x02, 0x40000, "")]);
        let (header, _) = ask(&mut service, r#"{"op": "metadata"}"#);
        assert_eq!(
            header.to_json(),
            r#"{"ok": false, "error": "the game metadata is not mapped yet", "not_ready": true}"#
        );
        std::fs::remove_dir_all(&folder).unwrap();
    }

    #[test]
    fn event_running_says_true_false_or_null() {
        let process = FakeProcess::new(0x10000, vec![0; 16]);
        for (running, text) in [(Some(true), "true"), (Some(false), "false"), (None, "null")] {
            let mut service = Service::new(&process, Box::new(|| Err(io::Error::other("-"))), Box::new(move || running), 1.0);
            let (header, _) = ask(&mut service, r#"{"op": "event_running"}"#);
            assert_eq!(header.to_json(), format!(r#"{{"ok": true, "running": {text}}}"#));
        }
    }

    #[test]
    fn a_search_hands_out_one_hit_at_a_time_and_can_begin_at_an_address() {
        let value: u64 = 0x1122334455667788;
        let mut data = vec![0u8; 64 * 1024];
        data[0x10..0x18].copy_from_slice(&value.to_le_bytes());
        data[0x8000..0x8008].copy_from_slice(&value.to_le_bytes());
        let process = FakeProcess::new(0x10000, data);
        let mut service = service(&process);
        let start = format!(r#"{{"op": "search", "regions": [[65536, 131072]], "value": {value}}}"#);
        ask(&mut service, &start);
        assert_eq!(process.reads.get(), 0);
        let next = r#"{"op": "search_next"}"#;
        assert_eq!(ask(&mut service, next).0.get("hit"), Some(&Value::Int(0x10010)));
        assert_eq!(ask(&mut service, next).0.get("hit"), Some(&Value::Int(0x18000)));
        assert_eq!(ask(&mut service, next).0.get("hit"), Some(&Value::Null));
        let from = format!(r#"{{"op": "search", "regions": [[65536, 131072]], "value": {value}, "first": 81920}}"#);
        ask(&mut service, &from);
        assert_eq!(ask(&mut service, next).0.get("hit"), Some(&Value::Int(0x18000)));
        assert_eq!(ask(&mut service, next).0.get("hit"), Some(&Value::Int(0x10010)));
        assert_eq!(ask(&mut service, next).0.get("hit"), Some(&Value::Null));
    }

    #[test]
    fn a_search_next_without_a_search_has_no_hit() {
        let process = FakeProcess::new(0x10000, vec![0; 16]);
        assert_eq!(ask(&mut service(&process), r#"{"op": "search_next"}"#).0.get("hit"), Some(&Value::Null));
    }

    #[test]
    fn an_unknown_op_is_an_answer() {
        let process = FakeProcess::new(0x10000, vec![0; 16]);
        let (header, _) = ask(&mut service(&process), r#"{"op": "write"}"#);
        assert_eq!(header.to_json(), r#"{"ok": false, "error": "unknown op 'write'"}"#);
    }

    fn served(process: &FakeProcess, requests: &[&str]) -> Vec<(Value, Vec<u8>)> {
        let mut source = Vec::new();
        for request in requests {
            source.extend(pack(&json::parse(request.as_bytes()).unwrap(), b""));
        }
        let mut sink = Vec::new();
        service(process).serve(&mut Cursor::new(source), &mut sink).unwrap();
        let mut answers = Vec::new();
        let mut cursor = Cursor::new(sink);
        while let Some(answer) = receive(&mut cursor).unwrap() {
            answers.push(answer);
        }
        answers
    }

    #[test]
    fn a_failed_read_is_an_answer_and_the_next_is_served() {
        let process = FakeProcess::new(0x10000, vec![7; 16]);
        let answers = served(
            &process,
            &[r#"{"op": "read", "address": 0, "size": 8}"#, r#"{"op": "read", "address": 65536, "size": 2}"#],
        );
        assert_eq!(answers.len(), 2);
        assert_eq!(answers[0].0.get("ok"), Some(&Value::Bool(false)));
        assert!(answers[0].0.get("error").and_then(Value::as_str).unwrap().contains("cannot read"));
        assert_eq!(answers[1].1, vec![7, 7]);
    }

    #[test]
    fn serving_ends_when_tsu_has_quit() {
        let process = FakeProcess::new(0x10000, vec![0; 16]);
        process.alive.set(false);
        let answers = served(&process, &[r#"{"op": "read", "address": 0, "size": 8}"#, r#"{"op": "maps"}"#]);
        assert!(answers.is_empty());
    }

    #[test]
    fn a_message_cut_short_ends_the_stream() {
        let mut whole = pack(&json::parse(br#"{"op": "maps"}"#).unwrap(), b"xy");
        assert!(receive(&mut Cursor::new(whole.clone())).unwrap().is_some());
        whole.pop();
        assert!(receive(&mut Cursor::new(whole)).unwrap().is_none());
        assert!(receive(&mut Cursor::new(Vec::new())).unwrap().is_none());
    }

    #[test]
    fn pack_matches_python() {
        // bottle_reader.pack({'ok': True, 'ready': READY}) in Python, byte for byte.
        let message = pack(&object([("ok", Value::Bool(true)), ("ready", Value::Str(READY.into()))]), b"");
        let body = br#"{"ok": true, "ready": "turbohud-bottle-reader"}"#;
        assert_eq!(&message[..4], &(body.len() as u32).to_le_bytes());
        assert_eq!(&message[4..8], &[0, 0, 0, 0]);
        assert_eq!(&message[8..], body);
    }
}
