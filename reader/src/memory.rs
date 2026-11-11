//! The reader's pure parts, as in `turbohud/tsu/winmemory.py`: memory regions, reading
//! many pages in few calls, and a paced search that hands out its hits one by one.
//! They run and test on any system; the Windows calls are in `win32.rs`.

use std::collections::{BTreeMap, HashSet, VecDeque};
use std::io;
use std::time::{Duration, Instant};

pub const PAGE: u64 = 4096;
pub const CHUNK: u64 = 1 << 20; // bytes a search reads at once
pub const MERGE_GAP: u64 = 48; // pages: wanted pages at most this far apart (192 KiB) share a read
pub const SPAN_MOST: u64 = 512; // pages a merged read covers at most (2 MiB)
pub const BREAKS_MOST: usize = 4096; // gaps kept as not readable across; forgotten all at once beyond
pub const WINE_SEARCH_SHARE: f64 = 0.5; // in Wine, the share of the time a search may read
// Outside Wine (TSU's own Windows build) a search reads this many pieces in one step, with
// SEARCH_THREADS threads (win32.rs): measured on the user's PC on 2026-11-12, all of TSU's
// 4.3 GB took 19.9 s with one thread, 10.4 s with 2, 5.7 s with 4 and 3.4 s with 8, as
// Windows copies another program's memory slowly but in parallel. Four leave TSU the rest.
pub const SEARCH_BATCH: usize = 16;
pub const SEARCH_THREADS: usize = 4;

pub const MEM_COMMIT: u32 = 0x1000;
pub const MEM_IMAGE: u32 = 0x100_0000;
pub const MEM_MAPPED: u32 = 0x4_0000;
pub const MEM_PRIVATE: u32 = 0x2_0000;
pub const PAGE_GUARD: u32 = 0x100;
const READ: [u32; 6] = [0x02, 0x04, 0x08, 0x20, 0x40, 0x80];
const WRITE: [u32; 4] = [0x04, 0x08, 0x40, 0x80];
const EXECUTE: [u32; 4] = [0x10, 0x20, 0x40, 0x80];

/// A region in the form of a Linux memory map line, as `winmemory.region` gives it.
#[derive(Clone, Debug, PartialEq)]
pub struct Region {
    pub start: u64,
    pub end: u64,
    pub perms: String,
    pub path: String,
}

pub fn region(start: u64, size: u64, protect: u32, kind: u32, path: &str) -> Region {
    let base = protect & 0xFF;
    let mut perms = String::with_capacity(4);
    perms.push(if READ.contains(&base) { 'r' } else { '-' });
    perms.push(if WRITE.contains(&base) { 'w' } else { '-' });
    perms.push(if EXECUTE.contains(&base) { 'x' } else { '-' });
    perms.push(if kind == MEM_PRIVATE { 'p' } else { 's' });
    let path = if kind == MEM_PRIVATE { "[heap]".to_string() } else { path.to_string() };
    Region { start, end: start + size, perms, path }
}

pub fn readable(state: u32, protect: u32) -> bool {
    state == MEM_COMMIT && READ.contains(&(protect & 0xFF)) && protect & PAGE_GUARD == 0
}

/// What the reader needs of TSU: the parts `win32::WindowsProcess` has, so tests can
/// stand in for it.
pub trait Process {
    fn read(&self, address: u64, size: usize) -> io::Result<Vec<u8>>;
    fn regions(&self) -> Vec<Region>;
    fn alive(&self) -> bool;

    /// Several reads, answered in their order: one after another here; a process may do
    /// them at once (WindowsProcess, outside Wine).
    fn read_many(&self, pieces: &[(u64, usize)]) -> Vec<io::Result<Vec<u8>>> {
        pieces.iter().map(|&(address, size)| self.read(address, size)).collect()
    }
}

/// (first, last) page numbers of the reads that cover `pages` (sorted, no repeats): pages
/// at most `gap` apart share a read, which covers at most `most` pages; two pages whose
/// pair is in `breaks` never share one.
pub fn spans(pages: &[u64], gap: u64, most: u64, breaks: &HashSet<(u64, u64)>) -> Vec<(u64, u64)> {
    let mut found: Vec<(u64, u64)> = Vec::new();
    for &number in pages {
        if let Some(last) = found.last_mut() {
            if number - last.1 <= gap && number - last.0 < most && !breaks.contains(&(last.1, number)) {
                last.1 = number;
                continue;
            }
        }
        found.push((number, number));
    }
    found
}

/// ({page number: its bytes}, reads made) for the `pages` that can be read, as
/// `winmemory.read_pages`: pages close together come from one call; a call that fails is
/// tried again as two, cut at its widest gap, down to single pages; a gap whose two sides
/// could be read goes into `breaks`, so later reads do not try across it again.
pub fn read_pages(
    read: &dyn Fn(u64, usize) -> io::Result<Vec<u8>>,
    pages: &[u64],
    breaks: &mut HashSet<(u64, u64)>,
) -> (BTreeMap<u64, Vec<u8>>, u64) {
    let mut wanted: Vec<u64> = pages.to_vec();
    wanted.sort_unstable();
    wanted.dedup();
    let mut found = BTreeMap::new();
    let mut calls = 0;
    let groups = spans(&wanted, MERGE_GAP, SPAN_MOST, breaks);
    let mut position = 0;
    for (_first, last) in groups {
        let mut end = position;
        while end < wanted.len() && wanted[end] <= last {
            end += 1;
        }
        fetch(read, &wanted[position..end], &mut found, &mut calls, breaks);
        position = end;
    }
    (found, calls)
}

/// Whether all of `group` (wanted pages, ascending) could be read.
fn fetch(
    read: &dyn Fn(u64, usize) -> io::Result<Vec<u8>>,
    group: &[u64],
    found: &mut BTreeMap<u64, Vec<u8>>,
    calls: &mut u64,
    breaks: &mut HashSet<(u64, u64)>,
) -> bool {
    let first = group[0];
    let last = group[group.len() - 1];
    *calls += 1;
    if let Ok(data) = read(first * PAGE, ((last - first + 1) * PAGE) as usize) {
        for &number in group {
            let offset = ((number - first) * PAGE) as usize;
            found.insert(number, data[offset..offset + PAGE as usize].to_vec());
        }
        return true;
    }
    if group.len() == 1 {
        return false;
    }
    // The widest gap, the first of them if two are as wide (as Python's max).
    let mut cut = 1;
    for index in 2..group.len() {
        if group[index] - group[index - 1] > group[cut] - group[cut - 1] {
            cut = index;
        }
    }
    let below = fetch(read, &group[..cut], found, calls, breaks);
    let above = fetch(read, &group[cut..], found, calls, breaks);
    if below && above {
        if breaks.len() >= BREAKS_MOST {
            breaks.clear();
        }
        breaks.insert((group[cut - 1], group[cut]));
    }
    false
}

/// `regions` in the order a search from `address` takes them: upwards from there, then
/// round from the lowest up to it; a region `address` lies in is cut in two there.
pub fn starting_at(regions: &[(u64, u64)], address: u64) -> Vec<(u64, u64)> {
    let mut sorted = regions.to_vec();
    sorted.sort_unstable();
    let (mut later, mut earlier) = (Vec::new(), Vec::new());
    for (start, end) in sorted {
        if end <= address {
            earlier.push((start, end));
        } else if start >= address {
            later.push((start, end));
        } else {
            later.push((address, end));
            earlier.push((start, address));
        }
    }
    later.extend(earlier);
    later
}

/// A search for the 64-bit `value` at 8-aligned addresses, read `CHUNK` bytes at a time,
/// as `winmemory.search`: it reads on only as far as its hits are taken, and with `share`
/// below 1 pauses after each piece so that reading takes about that share of the time.
pub struct Search {
    regions: Vec<(u64, u64)>,
    index: usize,
    address: Option<u64>,
    hits: VecDeque<u64>,
    value: u64,
    share: f64,
    batch: usize, // pieces read in one step (1: one at a time)
}

pub const ALIGN: u64 = 8;

impl Search {
    pub fn new(regions: &[(u64, u64)], value: u64, share: f64, first: Option<u64>) -> Search {
        let regions = match first {
            None => {
                let mut sorted = regions.to_vec();
                sorted.sort_unstable();
                sorted
            }
            Some(address) => starting_at(regions, address),
        };
        Search { regions, index: 0, address: None, hits: VecDeque::new(), value, share, batch: 1 }
    }

    /// The same search, reading `batch` pieces in each step (with Process::read_many):
    /// it then reads that far ahead of the hits taken.
    pub fn batched(mut self, batch: usize) -> Search {
        self.batch = batch.max(1);
        self
    }

    /// The next hit, or None once all the regions are read (one piece at a time: the tests).
    #[cfg(test)]
    pub fn next_hit(
        &mut self,
        read: &dyn Fn(u64, usize) -> io::Result<Vec<u8>>,
        sleep: &mut dyn FnMut(Duration),
    ) -> Option<u64> {
        self.next_hit_many(&|pieces| pieces.iter().map(|&(a, s)| read(a, s)).collect(), sleep)
    }

    /// next_hit, with the pieces of a step read by `read_many` (Process::read_many).
    pub fn next_hit_many(
        &mut self,
        read_many: &dyn Fn(&[(u64, usize)]) -> Vec<io::Result<Vec<u8>>>,
        sleep: &mut dyn FnMut(Duration),
    ) -> Option<u64> {
        loop {
            if let Some(hit) = self.hits.pop_front() {
                return Some(hit);
            }
            let pieces = self.next_pieces();
            if pieces.is_empty() {
                return None;
            }
            let began = Instant::now();
            let found = read_many(&pieces);
            for (&(address, _size), data) in pieces.iter().zip(found) {
                self.scan(address, &data.unwrap_or_default());
            }
            if self.share < 1.0 {
                sleep(began.elapsed().mul_f64((1.0 - self.share) / self.share));
            }
        }
    }

    /// The next `batch` pieces to read, in order: (address, size) each, a piece reading 7
    /// bytes past its end so that a word starting in it is whole. Empty once all are read.
    fn next_pieces(&mut self) -> Vec<(u64, usize)> {
        let mut pieces = Vec::with_capacity(self.batch);
        while pieces.len() < self.batch {
            let Some(&(start, end)) = self.regions.get(self.index) else { break };
            let address = *self.address.get_or_insert(start);
            if address >= end {
                self.index += 1;
                self.address = None;
                continue;
            }
            pieces.push((address, (CHUNK + 7).min(end - address) as usize));
            self.address = Some(address + CHUNK);
        }
        pieces
    }

    /// Note the hits in a piece read at `address`: each aligned word that starts in it, as
    /// a number (the words of the next piece's first bytes, read along, are its own).
    fn scan(&mut self, address: u64, data: &[u8]) {
        let skip = ((ALIGN - address % ALIGN) % ALIGN) as usize;
        let words = data.get(skip..).unwrap_or_default().chunks_exact(8);
        for (index, word) in words.enumerate() {
            let offset = skip + 8 * index;
            if offset as u64 >= CHUNK {
                break;
            }
            if u64::from_le_bytes(word.try_into().unwrap()) == self.value {
                self.hits.push_back(address + offset as u64);
            }
        }
    }
}

/// Where the game's `global-metadata.dat` (its bytes: `metadata`) is mapped: by its file
/// name where Windows gives one, else by its first bytes in shared (mapped) memory.
pub fn metadata_base(regions: &[Region], process: &dyn Process, metadata: &[u8]) -> Option<u64> {
    let named = regions
        .iter()
        .filter(|r| r.path.to_lowercase().ends_with("global-metadata.dat"))
        .map(|r| r.start)
        .min();
    if named.is_some() {
        return named;
    }
    let head = &metadata[..metadata.len().min(64)];
    regions
        .iter()
        .filter(|r| r.perms.ends_with('s'))
        .find(|r| process.read(r.start, head.len()).map(|data| data == head).unwrap_or(false))
        .map(|r| r.start)
}

#[cfg(test)]
pub mod tests {
    use super::*;
    use std::cell::RefCell;

    /// Bytes at `base`, readable only inside; keeps (page, pages) of each read.
    pub struct FakeMemory {
        pub base: u64,
        pub data: Vec<u8>,
        pub calls: RefCell<Vec<(u64, u64)>>,
    }

    impl FakeMemory {
        pub fn new(base: u64, data: Vec<u8>) -> FakeMemory {
            FakeMemory { base, data, calls: RefCell::new(Vec::new()) }
        }

        pub fn read(&self, address: u64, size: usize) -> io::Result<Vec<u8>> {
            self.calls.borrow_mut().push((address, size as u64));
            if address < self.base || address - self.base + size as u64 > self.data.len() as u64 {
                return Err(io::Error::other(format!("cannot read {size} bytes at {address:#x}")));
            }
            let start = (address - self.base) as usize;
            Ok(self.data[start..start + size].to_vec())
        }
    }

    fn pages_16_to_23() -> FakeMemory {
        let data: Vec<u8> = (0..8 * PAGE as usize).map(|i| (i % 256) as u8).collect();
        FakeMemory::new(16 * PAGE, data)
    }

    #[test]
    fn region_names_private_memory_heap() {
        let r = region(0x1000, 0x2000, 0x04, MEM_PRIVATE, "x");
        assert_eq!(r, Region { start: 0x1000, end: 0x3000, perms: "rw-p".into(), path: "[heap]".into() });
        assert_eq!(region(0, 4096, 0x20, MEM_IMAGE, "a.dll").perms, "r-xs");
        assert!(readable(MEM_COMMIT, 0x04));
        assert!(!readable(MEM_COMMIT, 0x04 | PAGE_GUARD));
        assert!(!readable(MEM_COMMIT, 0x01));
    }

    #[test]
    fn spans_merge_close_pages() {
        let none = HashSet::new();
        assert_eq!(spans(&[1, 2, 5, 40, 41], 4, 64, &none), vec![(1, 5), (40, 41)]);
        assert_eq!(spans(&(0..10).collect::<Vec<_>>(), 1, 4, &none), vec![(0, 3), (4, 7), (8, 9)]);
        assert_eq!(spans(&[100, 148, 197], MERGE_GAP, SPAN_MOST, &none), vec![(100, 148), (197, 197)]);
        let every_40: Vec<u64> = (0..600).step_by(40).collect();
        assert_eq!(spans(&every_40, MERGE_GAP, SPAN_MOST, &none), vec![(0, 480), (520, 560)]);
        let breaks = HashSet::from([(2, 5)]);
        assert_eq!(spans(&[1, 2, 5, 6], 4, 64, &breaks), vec![(1, 2), (5, 6)]);
    }

    #[test]
    fn close_pages_come_from_one_read() {
        let memory = pages_16_to_23();
        let (found, calls) = read_pages(&|a, s| memory.read(a, s), &[18, 16, 16], &mut HashSet::new());
        assert_eq!(calls, 1);
        assert_eq!(*memory.calls.borrow(), vec![(16 * PAGE, 3 * PAGE)]);
        assert_eq!(found.keys().copied().collect::<Vec<_>>(), vec![16, 18]);
        assert_eq!(found[&18], memory.data[2 * PAGE as usize..3 * PAGE as usize]);
    }

    #[test]
    fn a_read_that_fails_is_tried_again_in_halves() {
        let memory = pages_16_to_23();
        let mut breaks = HashSet::new();
        let (found, calls) = read_pages(&|a, s| memory.read(a, s), &[22, 23, 24], &mut breaks);
        assert_eq!(found.keys().copied().collect::<Vec<_>>(), vec![22, 23]);
        assert_eq!(calls, 5); // all, 22, then 23 and 24, then 23, 24
        assert!(breaks.is_empty()); // no gap to blame: page 24 itself cannot be read
    }

    fn two_islands() -> (impl Fn(u64, usize) -> io::Result<Vec<u8>>, std::rc::Rc<RefCell<Vec<(u64, u64)>>>) {
        let low = FakeMemory::new(16 * PAGE, vec![0; 4 * PAGE as usize]);
        let high = FakeMemory::new(40 * PAGE, vec![1; 4 * PAGE as usize]);
        let calls = std::rc::Rc::new(RefCell::new(Vec::new()));
        let seen = calls.clone();
        let read = move |address: u64, size: usize| {
            seen.borrow_mut().push((address / PAGE, size as u64 / PAGE));
            low.read(address, size).or_else(|_| high.read(address, size))
        };
        (read, calls)
    }

    #[test]
    fn a_failed_read_is_cut_at_its_widest_gap_and_remembered() {
        let (read, calls) = two_islands();
        let mut breaks = HashSet::new();
        let (found, made) = read_pages(&read, &[16, 19, 40, 43], &mut breaks);
        assert_eq!(found.keys().copied().collect::<Vec<_>>(), vec![16, 19, 40, 43]);
        assert_eq!(*calls.borrow(), vec![(16, 28), (16, 4), (40, 4)]);
        assert_eq!(made, 3);
        assert_eq!(found[&40], vec![1; PAGE as usize]);
        assert_eq!(breaks, HashSet::from([(19, 40)]));
        calls.borrow_mut().clear();
        let (_found, made) = read_pages(&read, &[16, 19, 40, 43], &mut breaks);
        assert_eq!(*calls.borrow(), vec![(16, 4), (40, 4)]);
        assert_eq!(made, 2);
    }

    #[test]
    fn the_breaks_kept_are_limited() {
        let (read, _calls) = two_islands();
        let mut breaks: HashSet<(u64, u64)> = (1000..1000 + BREAKS_MOST as u64).map(|n| (n, n + 1)).collect();
        read_pages(&read, &[16, 19, 40, 43], &mut breaks);
        assert_eq!(breaks, HashSet::from([(19, 40)]));
    }

    const VALUE: u64 = 0x1122334455667788;

    fn memory_with(offsets: &[usize]) -> FakeMemory {
        let mut data = vec![0u8; 64 * 1024];
        for &offset in offsets {
            data[offset..offset + 8].copy_from_slice(&VALUE.to_le_bytes());
        }
        FakeMemory::new(0x100000, data)
    }

    fn all_hits(memory: &FakeMemory, regions: &[(u64, u64)], first: Option<u64>) -> Vec<u64> {
        let mut search = Search::new(regions, VALUE, 1.0, first);
        let mut hits = Vec::new();
        while let Some(hit) = search.next_hit(&|a, s| memory.read(a, s), &mut |_| {}) {
            hits.push(hit);
        }
        hits
    }

    #[test]
    fn a_search_finds_aligned_values_only() {
        let memory = memory_with(&[0x10, 0x23, 0x800]);
        assert_eq!(all_hits(&memory, &[(0x100000, 0x110000)], None), vec![0x100010, 0x100800]);
    }

    #[test]
    fn a_search_finds_a_value_across_two_pieces_once() {
        let mut data = vec![0u8; 3 * CHUNK as usize];
        let at = CHUNK as usize; // the first word of the second piece
        data[at - 8..at].copy_from_slice(&VALUE.to_le_bytes()); // the last word of the first
        data[at..at + 8].copy_from_slice(&VALUE.to_le_bytes());
        let memory = FakeMemory::new(0x1000_0000, data);
        let hits = all_hits(&memory, &[(0x1000_0000, 0x1000_0000 + 3 * CHUNK)], None);
        assert_eq!(hits, vec![0x1000_0000 + CHUNK - 8, 0x1000_0000 + CHUNK]);
    }

    #[test]
    fn a_search_skips_what_cannot_be_read() {
        let memory = memory_with(&[0x40]);
        assert_eq!(all_hits(&memory, &[(0x0, 0x2000), (0x100000, 0x110000)], None), vec![0x100040]);
    }

    #[test]
    fn a_search_reads_only_as_far_as_hits_are_taken() {
        let mut data = vec![0u8; 3 * CHUNK as usize];
        data[0x10..0x18].copy_from_slice(&VALUE.to_le_bytes());
        data[2 * CHUNK as usize..2 * CHUNK as usize + 8].copy_from_slice(&VALUE.to_le_bytes());
        let memory = FakeMemory::new(0x1000_0000, data);
        let mut search = Search::new(&[(0x1000_0000, 0x1000_0000 + 3 * CHUNK)], VALUE, 1.0, None);
        assert_eq!(search.next_hit(&|a, s| memory.read(a, s), &mut |_| {}), Some(0x1000_0010));
        assert_eq!(memory.calls.borrow().len(), 1);
    }

    #[test]
    fn a_search_from_an_address_goes_up_from_there_and_comes_round() {
        let memory = memory_with(&[0x10, 0x800, 0x3008, 0x9000]);
        let hits = all_hits(&memory, &[(0x100000, 0x110000)], Some(0x103008));
        assert_eq!(hits, vec![0x103008, 0x109000, 0x100010, 0x100800]);
        let memory = memory_with(&[0x2FF8]);
        assert_eq!(all_hits(&memory, &[(0x100000, 0x110000)], Some(0x103000)), vec![0x102FF8]);
    }

    #[test]
    fn starting_at_orders_the_regions_from_an_address() {
        let regions = [(0x5000, 0x6000), (0x1000, 0x2000), (0x3000, 0x4000)];
        assert_eq!(starting_at(&regions, 0x3000), vec![(0x3000, 0x4000), (0x5000, 0x6000), (0x1000, 0x2000)]);
        assert_eq!(
            starting_at(&regions, 0x3800),
            vec![(0x3800, 0x4000), (0x5000, 0x6000), (0x1000, 0x2000), (0x3000, 0x3800)]
        );
        assert_eq!(starting_at(&regions, 0x2800)[0], (0x3000, 0x4000));
        assert_eq!(starting_at(&regions, 0), vec![(0x1000, 0x2000), (0x3000, 0x4000), (0x5000, 0x6000)]);
        assert_eq!(starting_at(&regions, 0x9000)[0], (0x1000, 0x2000));
    }

    #[test]
    fn a_batched_search_finds_the_same_hits_in_the_same_order() {
        let mut data = vec![0u8; 5 * CHUNK as usize + 4096];
        for at in [0x10, CHUNK as usize - 8, CHUNK as usize, 3 * CHUNK as usize + 0x40, 5 * CHUNK as usize + 8] {
            data[at..at + 8].copy_from_slice(&VALUE.to_le_bytes());
        }
        let memory = FakeMemory::new(0x1000_0000, data);
        let regions = [(0x1000_0000, 0x1000_0000 + 5 * CHUNK + 4096)];
        let one = all_hits(&memory, &regions, None);
        for batch in [2, 3, 16] {
            let mut search = Search::new(&regions, VALUE, 1.0, None).batched(batch);
            let read_many = |pieces: &[(u64, usize)]| pieces.iter().map(|&(a, s)| memory.read(a, s)).collect();
            let mut hits = Vec::new();
            while let Some(hit) = search.next_hit_many(&read_many, &mut |_| {}) {
                hits.push(hit);
            }
            assert_eq!(hits, one, "batch {batch}");
        }
        assert_eq!(one.len(), 5);
    }

    #[test]
    fn a_batched_search_reads_one_step_ahead_at_most() {
        let mut data = vec![0u8; 8 * CHUNK as usize];
        data[0x10..0x18].copy_from_slice(&VALUE.to_le_bytes());
        let memory = FakeMemory::new(0x1000_0000, data);
        let mut search = Search::new(&[(0x1000_0000, 0x1000_0000 + 8 * CHUNK)], VALUE, 1.0, None).batched(3);
        let steps = RefCell::new(Vec::new());
        let read_many = |pieces: &[(u64, usize)]| {
            steps.borrow_mut().push(pieces.len());
            pieces.iter().map(|&(a, s)| memory.read(a, s)).collect()
        };
        assert_eq!(search.next_hit_many(&read_many, &mut |_| {}), Some(0x1000_0010));
        assert_eq!(*steps.borrow(), vec![3]); // the first good hit: the rest is not read
    }

    #[test]
    fn read_many_answers_in_the_pieces_order() {
        struct Numbered;
        impl Process for Numbered {
            fn read(&self, address: u64, size: usize) -> io::Result<Vec<u8>> {
                if address == 2 {
                    return Err(io::Error::other("not readable"));
                }
                Ok(vec![address as u8; size])
            }
            fn regions(&self) -> Vec<Region> {
                Vec::new()
            }
            fn alive(&self) -> bool {
                true
            }
        }
        let found = Numbered.read_many(&[(1, 2), (2, 2), (3, 1)]);
        assert_eq!(found[0].as_ref().unwrap(), &vec![1, 1]);
        assert!(found[1].is_err());
        assert_eq!(found[2].as_ref().unwrap(), &vec![3]);
    }

    #[test]
    fn a_search_pauses_so_reading_takes_its_share() {
        let memory = memory_with(&[]);
        let mut search = Search::new(&[(0x100000, 0x100000 + 2 * CHUNK)], VALUE, 0.25, None);
        let mut slept = Vec::new();
        let slow = |a, s| {
            std::thread::sleep(Duration::from_millis(2));
            memory.read(a, s).or(Ok(Vec::new()))
        };
        assert_eq!(search.next_hit(&slow, &mut |d| slept.push(d)), None);
        assert_eq!(slept.len(), 2);
        for pause in slept {
            assert!(pause >= Duration::from_millis(6), "{pause:?}"); // 2 ms reading, 3 times as long left
        }
    }
}
