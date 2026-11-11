//! The Windows calls the reader makes, as in `turbohud/tsu/winmemory.py`. Only reads:
//! TSU is opened with PROCESS_VM_READ and PROCESS_QUERY_LIMITED_INFORMATION, which allow
//! reading its memory and asking for its layout, and nothing else.

use std::ffi::{c_void, OsString};
use std::io;
use std::os::windows::ffi::OsStringExt;
use std::path::PathBuf;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use crate::memory::{readable, region, Process, Region, MEM_IMAGE, MEM_MAPPED};

type Handle = *mut c_void;

const PROCESS_VM_READ: u32 = 0x0010;
const PROCESS_QUERY_LIMITED_INFORMATION: u32 = 0x1000;
const TH32CS_SNAPPROCESS: u32 = 0x2;
const STILL_ACTIVE: u32 = 259;
const INVALID_HANDLE_VALUE: Handle = -1isize as Handle;
const ADDRESS_TOP: u64 = 1 << 47; // the end of a program's own memory
const FILETIME_EPOCH: u64 = 11_644_473_600; // seconds from 1601 (Windows' FILETIME) to 1970

#[repr(C)]
struct ProcessEntry32W {
    size: u32,
    usage: u32,
    process_id: u32,
    default_heap_id: usize,
    module_id: u32,
    threads: u32,
    parent_process_id: u32,
    priority: i32,
    flags: u32,
    exe_file: [u16; 260],
}

#[repr(C)]
#[derive(Default)]
struct MemoryBasicInformation {
    base_address: usize,
    allocation_base: usize,
    allocation_protect: u32,
    partition_id: u16,
    region_size: usize,
    state: u32,
    protect: u32,
    kind: u32,
}

#[link(name = "kernel32")]
extern "system" {
    fn CreateToolhelp32Snapshot(flags: u32, process_id: u32) -> Handle;
    fn Process32FirstW(snapshot: Handle, entry: *mut ProcessEntry32W) -> i32;
    fn Process32NextW(snapshot: Handle, entry: *mut ProcessEntry32W) -> i32;
    fn OpenProcess(access: u32, inherit: i32, process_id: u32) -> Handle;
    fn CloseHandle(handle: Handle) -> i32;
    fn ReadProcessMemory(process: Handle, address: *const c_void, buffer: *mut c_void, size: usize, done: *mut usize) -> i32;
    fn VirtualQueryEx(process: Handle, address: *const c_void, info: *mut MemoryBasicInformation, size: usize) -> usize;
    fn QueryFullProcessImageNameW(process: Handle, flags: u32, name: *mut u16, size: *mut u32) -> i32;
    fn GetExitCodeProcess(process: Handle, code: *mut u32) -> i32;
    fn GetProcessTimes(process: Handle, created: *mut u64, exited: *mut u64, kernel: *mut u64, user: *mut u64) -> i32;
    fn K32GetMappedFileNameW(process: Handle, address: *const c_void, name: *mut u16, size: u32) -> u32;
    fn GetModuleHandleW(name: *const u16) -> Handle;
    fn GetProcAddress(module: Handle, name: *const u8) -> *const c_void;
}

fn wide_text(units: &[u16]) -> String {
    let end = units.iter().position(|&u| u == 0).unwrap_or(units.len());
    String::from_utf16_lossy(&units[..end])
}

/// True when this program runs in Wine (CrossOver).
pub fn under_wine() -> bool {
    let name: Vec<u16> = "ntdll\0".encode_utf16().collect();
    unsafe {
        let ntdll = GetModuleHandleW(name.as_ptr());
        !ntdll.is_null() && !GetProcAddress(ntdll, b"wine_get_version\0".as_ptr()).is_null()
    }
}

/// The process ID of the first running program called `name`, or None.
pub fn find_process(name: &str) -> Option<u32> {
    unsafe {
        let snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if snapshot == INVALID_HANDLE_VALUE {
            return None;
        }
        let mut entry: ProcessEntry32W = std::mem::zeroed();
        entry.size = std::mem::size_of::<ProcessEntry32W>() as u32;
        let mut found = None;
        let mut ok = Process32FirstW(snapshot, &mut entry);
        while ok != 0 {
            if wide_text(&entry.exe_file).to_lowercase() == name.to_lowercase() {
                found = Some(entry.process_id);
                break;
            }
            ok = Process32NextW(snapshot, &mut entry);
        }
        CloseHandle(snapshot);
        found
    }
}

/// Another program of this user, opened for reading only. `threads`: how many reads
/// read_many does at once (1: one after another).
pub struct WindowsProcess {
    handle: Handle,
    pub threads: usize,
}

/// `size` bytes at `address` of the process behind `handle`.
fn read_at(handle: Handle, address: u64, size: usize) -> io::Result<Vec<u8>> {
    let mut buffer = vec![0u8; size];
    let mut done = 0usize;
    let ok =
        unsafe { ReadProcessMemory(handle, address as *const c_void, buffer.as_mut_ptr().cast(), size, &mut done) };
    if ok == 0 || done != size {
        let error = io::Error::last_os_error();
        return Err(io::Error::other(format!("cannot read {size} bytes at {address:#x} ({error})")));
    }
    Ok(buffer)
}

impl WindowsProcess {
    pub fn open(process_id: u32) -> io::Result<WindowsProcess> {
        let handle = unsafe { OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION, 0, process_id) };
        if handle.is_null() {
            let error = io::Error::last_os_error();
            return Err(io::Error::other(format!("cannot open process {process_id} for reading ({error})")));
        }
        Ok(WindowsProcess { handle, threads: 1 })
    }

    /// When the program started, or None where not known.
    pub fn started(&self) -> Option<SystemTime> {
        let (mut created, mut exited, mut kernel, mut user) = (0u64, 0u64, 0u64, 0u64);
        if unsafe { GetProcessTimes(self.handle, &mut created, &mut exited, &mut kernel, &mut user) } == 0 {
            return None;
        }
        let since_1601 = Duration::from_nanos(created.checked_mul(100)?);
        UNIX_EPOCH.checked_add(since_1601.checked_sub(Duration::from_secs(FILETIME_EPOCH))?)
    }

    /// The program's own file (a Windows path).
    pub fn image_path(&self) -> io::Result<PathBuf> {
        let mut name = vec![0u16; 1024];
        let mut size = name.len() as u32;
        if unsafe { QueryFullProcessImageNameW(self.handle, 0, name.as_mut_ptr(), &mut size) } == 0 {
            let error = io::Error::last_os_error();
            return Err(io::Error::other(format!("cannot get the program file ({error})")));
        }
        Ok(PathBuf::from(OsString::from_wide(&name[..size as usize])))
    }
}

impl Drop for WindowsProcess {
    fn drop(&mut self) {
        unsafe { CloseHandle(self.handle) };
    }
}

impl Process for WindowsProcess {
    fn read(&self, address: u64, size: usize) -> io::Result<Vec<u8>> {
        read_at(self.handle, address, size)
    }

    /// The reads shared out over `threads` threads, each taking every threads-th piece;
    /// answered in the pieces' order. A process handle may be used by several threads at
    /// once, and ReadProcessMemory only reads.
    fn read_many(&self, pieces: &[(u64, usize)]) -> Vec<io::Result<Vec<u8>>> {
        let threads = self.threads.min(pieces.len());
        if threads <= 1 {
            return pieces.iter().map(|&(address, size)| read_at(self.handle, address, size)).collect();
        }
        let handle = self.handle as usize; // a number, to hand to the threads
        let mut found: Vec<Option<io::Result<Vec<u8>>>> = (0..pieces.len()).map(|_| None).collect();
        std::thread::scope(|scope| {
            let workers: Vec<_> = (0..threads)
                .map(|first| {
                    scope.spawn(move || {
                        (first..pieces.len())
                            .step_by(threads)
                            .map(|index| {
                                let (address, size) = pieces[index];
                                (index, read_at(handle as Handle, address, size))
                            })
                            .collect::<Vec<_>>()
                    })
                })
                .collect();
            for worker in workers {
                for (index, result) in worker.join().expect("a read thread panicked") {
                    found[index] = Some(result);
                }
            }
        });
        found.into_iter().map(|result| result.expect("every piece read")).collect()
    }

    /// The readable memory. Wine names no mapped files, so a mapped file may come with an
    /// empty path.
    fn regions(&self) -> Vec<Region> {
        let mut found = Vec::new();
        let mut address: u64 = 0;
        let mut info = MemoryBasicInformation::default();
        let size = std::mem::size_of::<MemoryBasicInformation>();
        while unsafe { VirtualQueryEx(self.handle, address as *const c_void, &mut info, size) } != 0 {
            let start = info.base_address as u64;
            let length = info.region_size as u64;
            if readable(info.state, info.protect) {
                let mut path = String::new();
                if info.kind == MEM_MAPPED || info.kind == MEM_IMAGE {
                    let mut name = vec![0u16; 1024];
                    let length =
                        unsafe { K32GetMappedFileNameW(self.handle, start as *const c_void, name.as_mut_ptr(), 1024) };
                    if length != 0 {
                        path = wide_text(&name[..length as usize]);
                    }
                }
                found.push(region(start, length, info.protect, info.kind, &path));
            }
            address = start + length;
            if length == 0 || address >= ADDRESS_TOP {
                break;
            }
        }
        found
    }

    /// False once the program has quit: a read then fails for good, unlike a read of a
    /// stale pointer.
    fn alive(&self) -> bool {
        let mut code = 0u32;
        unsafe { GetExitCodeProcess(self.handle, &mut code) != 0 && code == STILL_ACTIVE }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn read_many_with_threads_gives_what_one_thread_reads() {
        // This test program reads its own memory, as the reader reads TSU's.
        let data: Vec<u8> = (0..40 * 4096).map(|i| (i * 7 % 251) as u8).collect();
        let base = data.as_ptr() as u64;
        let mut process = WindowsProcess::open(std::process::id()).expect("open this process");
        let pieces: Vec<(u64, usize)> = (0..10).map(|i| (base + i * 4096 * 4, 4096 * 4)).collect();
        let one: Vec<_> = process.read_many(&pieces).into_iter().map(Result::unwrap).collect();
        process.threads = 4;
        let many: Vec<_> = process.read_many(&pieces).into_iter().map(Result::unwrap).collect();
        assert_eq!(one, many);
        assert_eq!(many.concat(), data);
        let failed = process.read_many(&[(base, 16), (8, 16), (base + 16, 16)]);
        assert!(failed[0].is_ok() && failed[1].is_err() && failed[2].is_ok());
    }
}
