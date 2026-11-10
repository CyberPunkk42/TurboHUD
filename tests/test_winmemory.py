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
        self.assertEqual(reader.last_read, (2, 0.5, None))
        self.assertEqual(reader.read(), 'state')
        self.assertEqual(reader.last_read, (2, 0.5, None))

    def test_a_failed_read_says_so_too(self):
        cache = wm.PageCache(lambda address, size: bytes(size))

        class Reader:
            def read(self):
                cache.read(0, 8)
                raise OSError('gone')

        reader = wm.CachedReader(Reader(), cache)
        with self.assertRaises(OSError):
            reader.read()
        self.assertEqual(reader.last_read, (1, None, None))


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


class SpansTests(unittest.TestCase):
    def test_pages_close_together_share_a_read(self):
        self.assertEqual(wm.spans([1, 2, 5, 40, 41], gap=4), [(1, 5), (40, 41)])

    def test_order_and_repeats_do_not_matter(self):
        self.assertEqual(wm.spans([5, 1, 2, 2], gap=4), [(1, 5)])

    def test_a_read_covers_at_most_most_pages(self):
        self.assertEqual(wm.spans(range(10), gap=1, most=4), [(0, 3), (4, 7), (8, 9)])

    def test_nothing_wanted_nothing_read(self):
        self.assertEqual(wm.spans([]), [])

    def test_pages_up_to_192_kib_apart_share_a_read(self):
        self.assertEqual(wm.spans([100, 148, 197]), [(100, 148), (197, 197)])

    def test_a_read_covers_at_most_2_mib(self):
        self.assertEqual(wm.spans(range(0, 600, 40)), [(0, 480), (520, 560)])

    def test_two_pages_with_a_break_between_them_do_not_share_a_read(self):
        self.assertEqual(wm.spans([1, 2, 5, 6], gap=4, breaks={(2, 5)}), [(1, 2), (5, 6)])


class ReadPagesTests(unittest.TestCase):
    def setUp(self):
        self.memory = FakeMemory(0x10000, bytes(range(256)) * 16 * 8)  # pages 16 to 23

    def test_close_pages_come_from_one_read(self):
        found, calls = wm.read_pages(self.memory.read, [16, 18])
        self.assertEqual(calls, 1)
        self.assertEqual(self.memory.calls, [(16 * 4096, 3 * 4096)])
        self.assertEqual(sorted(found), [16, 18])
        self.assertEqual(found[18], bytes(self.memory.data[2 * 4096 : 3 * 4096]))

    def test_a_read_that_fails_is_tried_again_in_halves(self):
        found, calls = wm.read_pages(self.memory.read, [22, 23, 24])  # 24 is not there
        self.assertEqual(sorted(found), [22, 23])
        self.assertEqual(calls, 5)  # all, 22, 23 and 24, 23, 24
        self.assertEqual(found[23], bytes(self.memory.data[7 * 4096 :]))

    def two_islands(self):
        """Pages 16 to 19 and 40 to 43, with nothing between them."""
        low, high = FakeMemory(16 * 4096, bytes(4 * 4096)), FakeMemory(40 * 4096, b'\x01' * 4 * 4096)
        calls = []

        def read(address, size):
            calls.append((address // 4096, size // 4096))
            try:
                return low.read(address, size)
            except OSError:
                return high.read(address, size)

        return read, calls

    def test_a_read_that_fails_is_cut_at_its_widest_gap(self):
        read, calls = self.two_islands()
        breaks = set()
        found, made = wm.read_pages(read, [16, 19, 40, 43], breaks=breaks)
        self.assertEqual(sorted(found), [16, 19, 40, 43])
        self.assertEqual(calls, [(16, 28), (16, 4), (40, 4)])
        self.assertEqual(made, 3)
        self.assertEqual(found[40], b'\x01' * 4096)
        self.assertEqual(breaks, {(19, 40)})

    def test_the_next_read_does_not_try_across_a_gap_that_failed(self):
        read, calls = self.two_islands()
        breaks = set()
        wm.read_pages(read, [16, 19, 40, 43], breaks=breaks)
        calls.clear()
        found, made = wm.read_pages(read, [16, 19, 40, 43], breaks=breaks)
        self.assertEqual(calls, [(16, 4), (40, 4)])
        self.assertEqual((sorted(found), made), ([16, 19, 40, 43], 2))

    def test_a_page_that_is_gone_leaves_no_break(self):
        breaks = set()
        found, _calls = wm.read_pages(self.memory.read, [22, 23, 24], breaks=breaks)  # 24 is not there
        self.assertEqual(sorted(found), [22, 23])
        self.assertEqual(breaks, set())  # no gap to blame: the page itself cannot be read

    def test_the_breaks_kept_are_limited(self):
        read, _calls = self.two_islands()
        breaks = {(n, n + 1) for n in range(1000, 1000 + wm.BREAKS_MOST)}
        wm.read_pages(read, [16, 19, 40, 43], breaks=breaks)
        self.assertEqual(breaks, {(19, 40)})

    def test_a_single_page_that_fails_is_left_out(self):
        self.assertEqual(wm.read_pages(self.memory.read, [100]), ({}, 1))


class PrefetchTests(unittest.TestCase):
    def setUp(self):
        self.memory = FakeMemory(0x10000, bytes(range(256)) * 16 * 8)
        self.fetched = []

        def fetch_many(pages):
            self.fetched.append(list(pages))
            return wm.read_pages(self.memory.read, pages)[0]

        self.cache = wm.PageCache(self.memory.read, page=4096, fetch_many=fetch_many)

    def test_the_next_read_fetches_the_pages_used_in_one_go(self):
        self.cache.read(0x10010, 8)
        self.cache.read(0x13000, 8)
        self.cache.clear()
        self.memory.calls.clear()
        self.cache.prefetch()
        self.assertEqual(self.fetched, [[16, 19]])
        self.memory.data[0x10] = 0xAA  # changed after the prefetch: this read sees it as fetched
        self.assertEqual(self.cache.read(0x10010, 1), b'\x10')
        self.cache.read(0x13000, 8)
        self.assertEqual(self.memory.calls, [(16 * 4096, 4 * 4096)])

    def test_pages_no_longer_used_are_not_fetched_again(self):
        self.cache.read(0x10010, 8)
        self.cache.clear()
        self.cache.prefetch()
        self.cache.read(0x12000, 8)  # this read used another page only
        self.cache.clear()
        self.cache.prefetch()
        self.assertEqual(self.fetched, [[16], [18]])

    def test_a_page_the_fetch_missed_is_read_on_its_own(self):
        self.cache.read(0x10010, 8)
        self.cache.clear()
        self.cache.prefetch = lambda: None  # as if the fetch got nothing
        self.memory.calls.clear()
        self.cache.read(0x10010, 8)
        self.assertEqual(self.memory.calls, [(16 * 4096, 4096)])

    def test_nothing_to_fetch_asks_nothing(self):
        self.cache.clear()
        self.cache.prefetch()
        self.assertEqual(self.fetched, [])
        self.assertEqual(self.cache.reads, 0)

    def test_a_cached_reader_makes_one_trip_for_what_it_read_before(self):
        cache = self.cache

        class Reader:
            def read(self):
                return cache.read(0x10010, 8) + cache.read(0x14000, 8)

        reader = wm.CachedReader(Reader(), cache, game_reads=lambda: len(self.memory.calls))
        reader.read()
        self.assertEqual(reader.last_read, (2, None, 2))
        reader.read()
        self.assertEqual(reader.last_read, (1, None, 1))


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

    def test_a_search_from_an_address_goes_up_from_there_and_comes_round(self):
        memory = self.memory_with(0x10, 0x800, 0x3008, 0x9000)
        regions = [(0x100000, 0x110000)]
        hits = list(wm.search(memory.read, regions, self.VALUE, chunk=4096, first=0x103008))
        self.assertEqual(hits, [0x103008, 0x109000, 0x100010, 0x100800])

    def test_a_search_from_an_address_reads_there_first(self):
        memory = self.memory_with(0x10, 0x3008)
        hits = wm.search(memory.read, [(0x100000, 0x110000)], self.VALUE, chunk=4096, first=0x103000)
        self.assertEqual(next(hits), 0x103008)
        self.assertEqual([address for address, _size in memory.calls], [0x103000])

    def test_a_value_just_below_the_address_is_found_on_the_way_round(self):
        memory = self.memory_with(0x2FF8)
        hits = list(wm.search(memory.read, [(0x100000, 0x110000)], self.VALUE, chunk=4096, first=0x103000))
        self.assertEqual(hits, [0x102FF8])

    def test_starting_at_orders_the_regions_from_an_address(self):
        regions = [(0x5000, 0x6000, 'x'), (0x1000, 0x2000, 'x'), (0x3000, 0x4000, 'x')]
        self.assertEqual(
            wm.starting_at(regions, 0x3000), [(0x3000, 0x4000), (0x5000, 0x6000), (0x1000, 0x2000)]
        )
        self.assertEqual(
            wm.starting_at(regions, 0x3800),
            [(0x3800, 0x4000), (0x5000, 0x6000), (0x1000, 0x2000), (0x3000, 0x3800)],
        )
        # Between two regions, below them all and above them all.
        self.assertEqual(wm.starting_at(regions, 0x2800)[0], (0x3000, 0x4000))
        self.assertEqual(wm.starting_at(regions, 0), [(0x1000, 0x2000), (0x3000, 0x4000), (0x5000, 0x6000)])
        self.assertEqual(wm.starting_at(regions, 0x9000)[0], (0x1000, 0x2000))

    def test_a_search_for_the_next_race_begins_a_little_below_the_last(self):
        self.assertEqual(wm.search_start(0x40000000 + 0x123), 0x40000000 - wm.SEARCH_BEFORE)
        self.assertEqual(wm.search_start(0x2000), 0)

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
