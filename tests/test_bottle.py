import io
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))

import build_app

from turbohud import app
from turbohud.core.il2cpp import NotFound, ReadError
from turbohud.tsu import bottle as bt
from turbohud.tsu import bottle_reader as br
from turbohud.tsu.client import LiveRace

TSU_LISTING = (
    '  101 /Applications/Other.app/Contents/MacOS/Other --open TSU.exe\n'
    '  102 Z:\\repo\\python.exe -I -B Z:\\repo\\bottle_reader.py\n'
    '  103 C:\\Program Files (x86)\\Steam\\steamapps\\common\\TSU\\TSU.exe -logFile x\n'
)


class FakeProcess:
    """Bytes at `base`, as `WindowsProcess` reads them."""

    def __init__(self, base=0x10000, data=bytes(64 * 1024), alive=True):
        self.base, self.data, self.is_alive = base, data, alive
        self.reads = 0

    def read(self, address, size):
        self.reads += 1
        start = address - self.base
        if start < 0 or start + size > len(self.data):
            raise OSError(f'cannot read {size} bytes at {address:#x}')
        return self.data[start : start + size]

    def regions(self):
        return [(self.base, self.base + len(self.data), 'rw-p', 0, '[heap]')]

    def alive(self):
        return self.is_alive


class PartsTests(unittest.TestCase):
    def test_tsu_pid_is_the_game_only(self):
        self.assertEqual(bt.tsu_pid(TSU_LISTING), 103)

    def test_tsu_pid_without_the_game(self):
        self.assertIsNone(bt.tsu_pid('  101 /bin/zsh\n  102 grep TSU.exe\n'))

    def test_bottle_from_open_files(self):
        files = 'p103\nn/Users/x/Library/Application Support/CrossOver/Bottles/My Games/drive_c/a\n'
        self.assertEqual(bt.bottle_named_in(files), 'My Games')
        self.assertIsNone(bt.bottle_named_in('p103\nn/usr/lib/dyld\n'))

    def test_windows_path_is_on_drive_z(self):
        self.assertEqual(bt.windows_path('/Volumes/a b/c.py'), 'Z:\\Volumes\\a b\\c.py')

    def test_files_from_the_source_folder(self):
        python, reader = bt.app_files(bundle='')
        self.assertEqual(python, ROOT / '.buildtools' / 'win-python' / 'python.exe')
        self.assertEqual(reader, ROOT / 'turbohud' / 'tsu' / 'bottle_reader.py')

    def test_files_inside_the_bundle(self):
        python, reader = bt.app_files(bundle='/b')
        self.assertEqual(python, Path('/b/win-python/python.exe'))
        self.assertEqual(reader, Path('/b/turbohud/tsu/bottle_reader.py'))

    def test_a_tool_that_hangs_counts_as_an_os_error(self):
        with (
            mock.patch.object(bt.subprocess, 'run', side_effect=subprocess.TimeoutExpired('lsof', 5)),
            self.assertRaises(OSError),
        ):
            bt._output(['lsof'])


class FindCrossoverTests(unittest.TestCase):
    def app_in(self, folder):
        wine = Path(folder) / 'CrossOver.app' / bt.WINE
        wine.parent.mkdir(parents=True)
        wine.write_text('')
        return wine

    def test_in_the_home_applications(self):
        with tempfile.TemporaryDirectory() as home:
            wine = self.app_in(Path(home) / 'Applications')
            self.assertEqual(bt.find_crossover(home, spotlight=lambda: ''), wine)

    def test_wherever_spotlight_knows(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as other:
            wine = self.app_in(other)
            found = bt.find_crossover(home, spotlight=lambda: f'{Path(other) / "CrossOver.app"}\n')
            if not Path('/Applications/CrossOver.app', bt.WINE).exists():
                self.assertEqual(found, wine)

    def test_none_without_it(self):
        with tempfile.TemporaryDirectory() as home:
            if not Path('/Applications/CrossOver.app', bt.WINE).exists():
                self.assertIsNone(bt.find_crossover(home, spotlight=lambda: ''))


class BottleOfTests(unittest.TestCase):
    def test_as_asked_for(self):
        bottle = bt.Bottle(environ={'TURBOHUD_BOTTLE': 'Mine'}, output=lambda _c: self.fail('not asked'))
        self.assertEqual(bottle.bottle_of(1), 'Mine')

    def test_from_the_open_files(self):
        bottle = bt.Bottle(environ={}, output=lambda _c: 'n/x/Bottles/Steam/drive_c\n')
        self.assertEqual(bottle.bottle_of(1), 'Steam')

    def test_the_only_one_there_is(self):
        with tempfile.TemporaryDirectory() as home:
            (Path(home) / bt.BOTTLES / 'Only').mkdir(parents=True)
            bottle = bt.Bottle(environ={}, home=home, output=lambda _c: '')
            self.assertEqual(bottle.bottle_of(1), 'Only')

    def test_refuses_to_guess(self):
        with tempfile.TemporaryDirectory() as home:
            for name in ('One', 'Two'):
                (Path(home) / bt.BOTTLES / name).mkdir(parents=True)
            bottle = bt.Bottle(environ={}, home=home, output=lambda _c: '')
            with self.assertRaises(OSError):
                bottle.bottle_of(1)


class ServiceTests(unittest.TestCase):
    def service(self, process=None, metadata_file=None, running=lambda: True):
        return br.Service(process or FakeProcess(), metadata_file, running)

    def test_a_read_says_how_long_it_took_on_the_game_s_memory(self):
        header, _ = self.service().handle({'op': 'read', 'address': 0x10010, 'size': 4})
        self.assertGreaterEqual(header['took'], 0.0)

    def test_read(self):
        process = FakeProcess(data=bytes(range(256)))
        header, payload = self.service(process).handle({'op': 'read', 'address': 0x10010, 'size': 4})
        self.assertTrue(header['ok'])
        self.assertEqual(payload, bytes(range(16, 20)))

    def test_read_size_is_limited(self):
        for size in (0, -1, br.MAX_READ + 1):
            with self.subTest(size=size):
                header, _ = self.service().handle({'op': 'read', 'address': 0, 'size': size})
                self.assertFalse(header['ok'])

    def test_no_op_writes_or_runs_anything(self):
        for op in ('write', 'exec', None):
            with self.subTest(op=op):
                header, _ = self.service().handle({'op': op})
                self.assertFalse(header['ok'])

    def test_metadata_not_mapped_yet(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'global-metadata.dat'
            file.write_bytes(b'\xaf\x1b\xb1\xfa' + bytes(100))
            header, _ = self.service(metadata_file=lambda: file).handle({'op': 'metadata'})
        self.assertFalse(header['ok'])
        self.assertTrue(header['not_ready'])

    def test_event_running(self):
        header, _ = self.service(running=lambda: False).handle({'op': 'event_running'})
        self.assertEqual(header, {'ok': True, 'running': False})

    def test_search_reads_only_as_far_as_hits_are_taken(self):
        value = 0x1122334455667788
        data = bytearray(64 * 1024)
        data[0x10:0x18] = struct.pack('<Q', value)
        data[0x8000:0x8008] = struct.pack('<Q', value)
        process = FakeProcess(data=bytes(data))
        service = self.service(process)
        service.handle({'op': 'search', 'regions': [[0x10000, 0x20000]], 'value': value})
        self.assertEqual(process.reads, 0)
        self.assertEqual(service.handle({'op': 'search_next'})[0]['hit'], 0x10010)
        self.assertEqual(service.handle({'op': 'search_next'})[0]['hit'], 0x18000)
        self.assertIsNone(service.handle({'op': 'search_next'})[0]['hit'])

    def serve(self, service, *requests):
        source = io.BytesIO(b''.join(br.pack(request) for request in requests))
        sink = io.BytesIO()
        service.serve(source, sink)
        sink.seek(0)
        answers = []
        while (message := br.receive(sink)) is not None:
            answers.append(message)
        return answers

    def test_a_failed_read_is_an_answer(self):
        answers = self.serve(
            self.service(),
            {'op': 'read', 'address': 0, 'size': 8},
            {'op': 'read', 'address': 0x10000, 'size': 8},
        )
        self.assertFalse(answers[0][0]['ok'])
        self.assertTrue(answers[1][0]['ok'])
        self.assertEqual(answers[1][1], bytes(8))

    def test_ends_once_tsu_has_quit(self):
        answers = self.serve(
            self.service(FakeProcess(alive=False)),
            {'op': 'read', 'address': 0, 'size': 8},
            {'op': 'maps'},
        )
        self.assertEqual(answers, [])

    def test_a_cut_message_ends_the_stream(self):
        whole = br.pack({'op': 'maps'}, b'bytes')
        self.assertIsNone(br.receive(io.BytesIO(whole[:-1])))
        self.assertIsNone(br.receive(io.BytesIO(b'')))


class ReaderCase(unittest.TestCase):
    """The Mac side against a real Service over real pipes."""

    def reader(self, process=None, metadata_file=None, greeting=None):
        """A Pipe to a Service running in a thread."""
        to_reader, from_mac = os.pipe()
        to_mac, from_reader = os.pipe()
        source = os.fdopen(to_reader, 'rb')
        sink = os.fdopen(from_reader, 'wb', 0)
        request_sink = os.fdopen(from_mac, 'wb', 0)
        service = br.Service(process or FakeProcess(), metadata_file, lambda: None)

        def run():
            with source, sink:
                sink.write(br.pack(greeting or {'ok': True, 'ready': br.READY}))
                service.serve(source, sink)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        def finish():
            request_sink.close()
            thread.join(5)
            os.close(to_mac)

        pipe = bt.Pipe(request_sink, to_mac, finish)
        self.addCleanup(pipe.close)
        return pipe


@unittest.skipIf(sys.platform == 'win32', 'the Mac side selects on a pipe')
class PipeTests(ReaderCase):
    def test_the_first_message_says_it_is_the_reader(self):
        header, _ = self.reader().receive()
        self.assertEqual(header['ready'], br.READY)

    def test_read_and_maps(self):
        pipe = self.reader(FakeProcess(data=bytes(range(256))))
        pipe.receive()
        self.assertEqual(pipe.read(0x10001, 2), b'\x01\x02')
        self.assertEqual(pipe.maps(), [(0x10000, 0x10100, 'rw-p', 0, '[heap]')])

    def test_a_refused_read_is_a_read_error(self):
        pipe = self.reader()
        pipe.receive()
        with self.assertRaises(ReadError):
            pipe.read(0, 8)

    def test_a_game_still_loading_is_not_found(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'global-metadata.dat'
            file.write_bytes(bytes(100))
            pipe = self.reader(metadata_file=lambda: file)
            pipe.receive()
            with self.assertRaises(NotFound):
                pipe.game_metadata()

    def test_a_large_read_arrives_whole(self):
        data = os.urandom(1 << 20)
        pipe = self.reader(FakeProcess(data=data))
        pipe.receive()
        self.assertEqual(pipe.read(0x10000, len(data)), data)

    def test_search_asks_for_one_hit_at_a_time(self):
        value = 0x1122334455667788
        data = bytearray(64 * 1024)
        data[0x10:0x18] = struct.pack('<Q', value)
        data[0x8000:0x8008] = struct.pack('<Q', value)
        process = FakeProcess(data=bytes(data))
        pipe = self.reader(process)
        pipe.receive()
        hits = pipe.search(process.regions(), value)
        self.assertEqual(next(hits), 0x10010)
        self.assertEqual(process.reads, 1)  # the first piece only
        self.assertEqual(list(hits), [0x18000])

    def test_a_reader_that_ended_is_a_connection_error(self):
        pipe = self.reader(FakeProcess(alive=False))
        pipe.receive()
        with self.assertRaises(ConnectionError):
            pipe.read(0, 8)

    def test_a_silent_reader_times_out(self):
        quiet, keep = os.pipe()
        self.addCleanup(os.close, quiet)
        self.addCleanup(os.close, keep)
        with self.assertRaises(TimeoutError):
            bt.Pipe(io.BytesIO(), quiet).receive(0.01)


@unittest.skipIf(sys.platform == 'win32', 'the Mac side selects on a pipe')
class BottleTests(ReaderCase):
    """Starting and keeping the reader."""

    def bottle(self, start, listing=TSU_LISTING, clock=None):
        return bt.Bottle(
            environ={'TURBOHUD_BOTTLE': 'Steam'},
            output=lambda _command: listing,
            start=start,
            clock=clock or (lambda: 0.0),
        )

    def test_no_reader_while_tsu_does_not_run(self):
        bottle = self.bottle(lambda _b: self.fail('started'), listing='  1 /bin/zsh\n')
        with self.assertRaisesRegex(OSError, 'not running'):
            bottle.connect()

    def test_keeps_its_reader_while_the_game_loads(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'global-metadata.dat'
            file.write_bytes(bytes(100))
            starts = []

            def start(name):
                starts.append(name)
                return self.reader(metadata_file=lambda: file)

            bottle = self.bottle(start)
            for _ in range(2):
                with self.assertRaises(NotFound):
                    bottle.connect()
            self.assertEqual(starts, ['Steam'])
            self.assertIsNotNone(bottle.pipe)
            bottle.close()
            self.assertIsNone(bottle.pipe)

    def test_a_reader_that_cannot_find_tsu_is_an_os_error(self):
        bottle = self.bottle(lambda _b: self.reader(greeting={'ok': False, 'error': 'no TSU.exe'}))
        with self.assertRaisesRegex(OSError, 'no TSU.exe'):
            bottle.connect()
        self.assertIsNone(bottle.pipe)

    def test_the_log_says_how_long_a_start_took_and_when_it_closes(self):
        now = [10.0]

        def start(_name):
            now[0] += 1.5
            return self.reader()

        bottle = self.bottle(start, clock=lambda: now[0])
        with self.assertLogs('turbohud.tsu.bottle', 'INFO') as logs:
            bottle._open()
            bottle.close()
            bottle.close()  # nothing left to close: no second line
        self.assertIn('bottle Steam, started in 1.5 s', logs.output[0])
        self.assertEqual(len(logs.output), 2)
        self.assertIn('closing the reader', logs.output[1])

    def test_the_log_says_why_a_reader_was_given_up(self):
        pipe = self.reader(FakeProcess(alive=False), metadata_file=lambda: '/none')
        bottle = self.bottle(lambda _name: pipe)
        with self.assertLogs('turbohud.tsu.bottle', 'WARNING') as logs, self.assertRaises(OSError):
            bottle.connect()
        self.assertIn('the reader in the bottle failed', logs.output[0])
        self.assertIsNone(bottle.pipe)

    def test_a_failed_start_is_not_tried_again_at_once(self):
        now = [0.0]
        starts = []

        def start(_name):
            starts.append(1)
            raise OSError('CrossOver was not found')

        bottle = self.bottle(start, clock=lambda: now[0])
        for moment in (0.0, 1.0, bt.RETRY_START - 1):
            now[0] = moment
            with self.assertRaisesRegex(OSError, 'CrossOver was not found'):
                bottle.connect()
        self.assertEqual(len(starts), 1)
        now[0] = bt.RETRY_START + 1
        with self.assertRaises(OSError):
            bottle.connect()
        self.assertEqual(len(starts), 2)

    def test_a_game_quit_after_a_failed_start_tries_at_once_next_time(self):
        def start(_name):
            raise OSError('failed')

        bottle = self.bottle(start)
        with self.assertRaises(OSError):
            bottle.connect()
        self.assertIsNotNone(bottle.failed)
        bottle.output = lambda _command: ''
        with self.assertRaisesRegex(OSError, 'not running'):
            bottle.connect()
        self.assertIsNone(bottle.failed)


class ReaderFilesTests(unittest.TestCase):
    def test_the_bundled_files_are_all_the_reader_needs(self):
        """The Mac app ships the reader as plain files beside a bare Windows Python: it must
        run with those alone, with no Qt and none of the race logic."""
        with tempfile.TemporaryDirectory() as folder:
            for name in build_app.READER_FILES:
                target = Path(folder) / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / name, target)
            code = (
                f'import sys; sys.path.insert(0, {folder!r}); import turbohud.tsu.bottle_reader; '
                'assert not [m for m in sys.modules if m.startswith(("turbohud.core", "PySide6"))]'
            )
            result = subprocess.run(
                [sys.executable, '-I', '-B', '-c', code],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_only_the_mac_app_ships_them(self):
        mac = build_app.pyinstaller_args('darwin')
        self.assertIn(f'{build_app.WIN_PYTHON}:win-python', mac)
        self.assertIn(f'{ROOT / "turbohud/tsu/bottle_reader.py"}:turbohud/tsu', mac)
        self.assertIn(f'{ROOT / "turbohud/__init__.py"}:turbohud', mac)
        self.assertFalse([arg for arg in build_app.pyinstaller_args('linux') if 'win-python' in arg])

    def test_the_bundle_paths_match_where_the_app_looks(self):
        python, reader = bt.app_files(bundle='/b')
        self.assertEqual(python.parent.name, 'win-python')
        self.assertIn('turbohud/tsu/bottle_reader.py', build_app.READER_FILES)
        self.assertEqual(reader, Path('/b/turbohud/tsu/bottle_reader.py'))


class StartLiveRaceTests(unittest.TestCase):
    def started(self, platform):
        with mock.patch.object(LiveRace, 'start') as start:
            live = app.start_live_race(platform)
        return live, start

    def test_the_mac_reads_through_the_bottle(self):
        live, start = self.started('darwin')
        start.assert_called_once()
        self.assertIsInstance(live._connect.__self__, bt.Bottle)
        self.assertEqual(live._close.__self__, live._connect.__self__)

    def test_linux_reads_through_the_probe(self):
        live, start = self.started('linux')
        start.assert_called_once()
        self.assertIsNone(live._close)

    def test_windows_keeps_the_clock_for_now(self):
        self.assertIsNone(self.started('win32')[0])

    def test_stop_ends_what_stays_open_between_connects(self):
        closed = []
        live = LiveRace(connect=lambda: None, close=lambda: closed.append(1))
        live.stop()
        self.assertEqual(closed, [1])


if __name__ == '__main__':
    unittest.main()
