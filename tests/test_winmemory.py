import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from turbohud.core.il2cpp import Memory
from turbohud.tsu import winmemory as wm


class CachedReaderDetailTests(unittest.TestCase):
    def test_it_says_what_the_latest_read_took(self):
        spent = [0.0]
        cache = wm.PageCache(lambda address, size: bytes(size))

        class Reader:
            def read(self):
                cache.read(0, 8)
                cache.read(wm.PAGE * 5, 8)
                spent[0] += 0.5
                return 'state'

        reader = wm.CachedReader(Reader(), cache, lambda: spent[0])
        self.assertEqual(reader.read(), 'state')
        self.assertEqual(reader.last_read, (2, 0.5))
        self.assertEqual(reader.read(), 'state')
        self.assertEqual(reader.last_read, (2, 0.5))

    def test_a_failed_read_says_so_too(self):
        cache = wm.PageCache(lambda address, size: bytes(size))

        class Reader:
            def read(self):
                cache.read(0, 8)
                raise OSError('gone')

        reader = wm.CachedReader(Reader(), cache)
        with self.assertRaises(OSError):
            reader.read()
        self.assertEqual(reader.last_read, (1, None))


class FakeMemory:
    """Bytes at `base`, readable only inside; counts reads."""

    def __init__(self, base, data):
        self.base, self.data = base, bytearray(data)
        self.calls = []

    def read(self, address, size):
        self.calls.append((address, size))
        start = address - self.base
        if start < 0 or start + size > len(self.data):
            raise OSError(f'cannot read {size} bytes at {address:#x}')
        return bytes(self.data[start : start + size])


class RegionTests(unittest.TestCase):
    def test_private_memory_reads_as_the_c_heap(self):
        self.assertEqual(
            wm.region(0x1000, 0x2000, 0x04, wm.MEM_PRIVATE), (0x1000, 0x3000, 'rw-p', 0, '[heap]')
        )

    def test_mapped_and_image_memory_keep_their_path(self):
        self.assertEqual(
            wm.region(0x5000, 0x1000, 0x02, wm.MEM_MAPPED, 'C:\\m.dat'),
            (0x5000, 0x6000, 'r--s', 0, 'C:\\m.dat'),
        )
        self.assertEqual(wm.region(0x5000, 0x1000, 0x20, wm.MEM_IMAGE)[2], 'r-xs')

    def test_readable_needs_committed_readable_unguarded_pages(self):
        self.assertTrue(wm.readable(wm.MEM_COMMIT, 0x04))
        self.assertFalse(wm.readable(0x2000, 0x04))  # reserved only
        self.assertFalse(wm.readable(wm.MEM_COMMIT, 0x01))  # no access
        self.assertFalse(wm.readable(wm.MEM_COMMIT, 0x04 | wm.PAGE_GUARD))

    def test_searchable_is_writable_private_memory(self):
        self.assertTrue(wm.searchable(wm.region(0, 4096, 0x04, wm.MEM_PRIVATE)))
        self.assertFalse(wm.searchable(wm.region(0, 4096, 0x02, wm.MEM_PRIVATE)))
        self.assertFalse(wm.searchable(wm.region(0, 4096, 0x04, wm.MEM_MAPPED)))


class PageCacheTests(unittest.TestCase):
    def setUp(self):
        self.memory = FakeMemory(0x10000, bytes(range(256)) * 64)  # 16 KiB
        self.cache = wm.PageCache(self.memory.read, page=4096, largest=8192)

    def test_small_reads_on_one_page_read_it_once(self):
        first = self.cache.read(0x10010, 8)
        second = self.cache.read(0x10100, 4)
        self.assertEqual(first, bytes(range(16, 24)))
        self.assertEqual(second, bytes(range(4)))
        self.assertEqual(self.memory.calls, [(0x10000, 4096)])

    def test_a_read_across_two_pages_joins_them(self):
        data = self.cache.read(0x10FFC, 8)
        self.assertEqual(data, self.memory.data[0xFFC:0x1004])
        self.assertEqual(self.memory.calls, [(0x10000, 4096), (0x11000, 4096)])

    def test_clear_reads_the_page_again(self):
        self.cache.read(0x10000, 8)
        self.memory.data[0] = 0xAA
        self.assertEqual(self.cache.read(0x10000, 1), b'\x00')
        self.cache.clear()
        self.assertEqual(self.cache.read(0x10000, 1), b'\xaa')

    def test_large_reads_go_straight_through(self):
        self.cache.read(0x10000, 12000)
        self.assertEqual(self.memory.calls, [(0x10000, 12000)])

    def test_a_page_that_cannot_be_read_whole_reads_just_the_bytes(self):
        memory = FakeMemory(0x10000, bytes(100))  # less than a page
        cache = wm.PageCache(memory.read, page=4096)
        self.assertEqual(cache.read(0x10010, 8), bytes(8))
        self.assertEqual(memory.calls, [(0x10000, 4096), (0x10010, 8)])

    def test_a_read_outside_still_fails(self):
        with self.assertRaises(OSError):
            self.cache.read(0x40000, 8)


class SearchTests(unittest.TestCase):
    VALUE = 0x1122334455667788

    def memory_with(self, *offsets):
        data = bytearray(64 * 1024)
        for offset in offsets:
            data[offset : offset + 8] = struct.pack('<Q', self.VALUE)
        return FakeMemory(0x100000, data)

    def test_finds_aligned_values_only(self):
        memory = self.memory_with(0x10, 0x23, 0x800)
        hits = list(wm.search(memory.read, [(0x100000, 0x110000)], self.VALUE, chunk=4096))
        self.assertEqual(hits, [0x100010, 0x100800])

    def test_finds_a_value_across_two_pieces_once(self):
        memory = self.memory_with(4096 - 4)
        hits = list(wm.search(memory.read, [(0x100000, 0x110000)], self.VALUE, align=4, chunk=4096))
        self.assertEqual(hits, [0x100000 + 4096 - 4])

    def test_skips_what_cannot_be_read(self):
        memory = self.memory_with(0x40)
        hits = list(wm.search(memory.read, [(0x0, 0x2000), (0x100000, 0x110000)], self.VALUE, chunk=4096))
        self.assertEqual(hits, [0x100040])

    def test_pauses_so_reading_takes_its_share_of_the_time(self):
        memory = self.memory_with()
        ticks = iter([0.0, 0.002, 1.0, 1.002])  # each piece takes 2 ms to read
        slept = []
        list(
            wm.search(
                memory.read,
                [(0x100000, 0x102000)],
                self.VALUE,
                chunk=4096,
                share=0.25,
                sleep=slept.append,
                clock=lambda: next(ticks),
            )
        )
        self.assertEqual(len(slept), 2)
        for pause in slept:
            self.assertAlmostEqual(pause, 0.006)  # 2 ms reading, 6 ms left to the game

    def test_in_wine_a_search_reads_half_the_time(self):
        memory = self.memory_with(0x10, 0x2000)
        ticks = iter([0.0, 0.002])  # the piece takes 2 ms to read
        slept = []
        list(
            wm.search(
                memory.read,
                [(0x100000, 0x101000)],
                self.VALUE,
                chunk=4096,
                share=wm.WINE_SEARCH_SHARE,
                sleep=slept.append,
                clock=lambda: next(ticks),
            )
        )
        self.assertEqual(len(slept), 1)
        self.assertAlmostEqual(slept[0], 0.002)  # as long left to the game as spent reading

    def test_reads_only_as_far_as_hits_are_taken(self):
        memory = self.memory_with(0x10, 0x8000)
        hits = wm.search(memory.read, [(0x100000, 0x110000)], self.VALUE, chunk=4096)
        self.assertEqual(next(hits), 0x100010)
        self.assertEqual(len(memory.calls), 1)  # the first piece only, of 16

    def test_lowest_regions_first(self):
        memory = self.memory_with(0x10, 0x8000)
        hits = wm.search(memory.read, [(0x108000, 0x110000), (0x100000, 0x108000)], self.VALUE, chunk=4096)
        self.assertEqual(list(hits), [0x100010, 0x108000])

    def test_no_pauses_at_full_share(self):
        memory = self.memory_with()
        slept = []
        list(wm.search(memory.read, [(0x100000, 0x102000)], self.VALUE, chunk=4096, sleep=slept.append))
        self.assertEqual(slept, [])


class MetadataTests(unittest.TestCase):
    METADATA = b'\xaf\x1b\xb1\xfa\x1d\x00\x00\x00' + bytes(range(56)) + b'rest of the file'

    def test_by_mapped_file_name(self):
        regions = [wm.region(0x9000, 0x1000, 0x02, wm.MEM_MAPPED, r'\Device\x\global-metadata.dat')]
        self.assertEqual(wm.metadata_base(regions, None, self.METADATA), 0x9000)

    def test_by_first_bytes_in_mapped_memory(self):
        memory = FakeMemory(0x20000, self.METADATA)
        regions = [
            wm.region(0x0, 0x1000, 0x02, wm.MEM_MAPPED),  # unreadable here
            wm.region(0x20000, 0x1000, 0x04, wm.MEM_PRIVATE),  # a private copy: not it
            wm.region(0x20000, 0x1000, 0x02, wm.MEM_MAPPED),
        ]
        self.assertEqual(wm.metadata_base(regions, memory.read, self.METADATA), 0x20000)

    def test_none_when_not_mapped(self):
        memory = FakeMemory(0x20000, bytes(128))
        regions = [wm.region(0x20000, 0x1000, 0x02, wm.MEM_MAPPED)]
        self.assertIsNone(wm.metadata_base(regions, memory.read, self.METADATA))


class ConnectPartsTests(unittest.TestCase):
    def test_tsu_data_is_under_the_user_profile(self):
        folder = wm.tsu_data({'USERPROFILE': 'C:\\users\\crossover'})
        self.assertEqual(folder.parts[-3:], ('LocalLow', 'Turbo Sliders', 'Unlimited'))

    def test_cached_reader_clears_the_cache_before_each_read(self):
        memory = FakeMemory(0x10000, bytes(4096))
        cache = wm.PageCache(memory.read)

        class Reader:
            def read(self):
                return cache.read(0x10000, 8)

        reader = wm.CachedReader(Reader(), cache)
        reader.read()
        reader.read()
        self.assertEqual(len(memory.calls), 2)

    def test_memory_hands_searches_to_the_searcher(self):
        asked = []
        memory = Memory(None, [], searcher=lambda regions, value: asked.append((regions, value)) or [0x40])
        self.assertEqual(memory.search([(0, 8)], 7), [0x40])
        self.assertEqual(asked, [([(0, 8)], 7)])


if __name__ == '__main__':
    unittest.main()
