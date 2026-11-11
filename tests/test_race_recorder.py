import contextlib
import gzip
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tsu_race_recorder as recorder  # noqa: E402
from test_race import build  # noqa: E402


class _Live:
    def __init__(self, reader):
        self.reader = reader

    def read(self):
        return self.reader.read()


def records(out):
    return [json.loads(line) for line in out.getvalue().splitlines()]


class FolderTests(unittest.TestCase):
    def test_windows_records_beside_turbohuds_settings(self):
        found = recorder.folder('win32', {'APPDATA': r'C:\Users\x\AppData\Roaming'})
        self.assertEqual(found, Path(r'C:\Users\x\AppData\Roaming') / 'TurboHUD' / 'recordings')

    def test_the_mac_records_in_application_support(self):
        found = recorder.folder('darwin', {}, home='/Users/x')
        self.assertEqual(found, Path('/Users/x/Library/Application Support/TurboHUD/recordings'))


class EventTests(unittest.TestCase):
    def setUp(self):
        self.reader = build([10_000], laps_completed=0, clock=20_000, limit=0, event_type=('BattleEventMode', 6))
        self.reader.read()
        self.out = io.StringIO()
        self.recorder = recorder.Recorder(_Live(self.reader), self.out)
        quiet = contextlib.redirect_stdout(io.StringIO())  # its 'event:' line
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def test_the_event_type_is_written_once_per_event(self):
        self.recorder.event_fields(1.0, 20_000)
        self.recorder.event_fields(1.5, 20_000)
        events = [r for r in records(self.out) if r['kind'] == 'event']
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]['mode'], events[0]['level_type']), ('TS.BattleEventMode', 6))
        self.assertEqual(events[0]['classes']['event.state'], 'TS.EventState')

    def test_the_events_own_fields_are_written_as_player_minus_one_and_only_when_changed(self):
        self.recorder.event_fields(1.0, 20_000)
        first = [r for r in records(self.out) if r['kind'] == 'fields']
        self.assertTrue(first)
        self.assertTrue(all(r['player'] == recorder.EVENT_PLAYER for r in first))
        self.assertIn('event.settings', {r['role'] for r in first})
        self.recorder.event_fields(1.5, 20_000)  # nothing moved
        self.assertEqual(len([r for r in records(self.out) if r['kind'] == 'fields']), len(first))


class SavingTests(unittest.TestCase):
    def test_a_recording_stopped_from_outside_keeps_what_was_saved(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        now = [0.0]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'race.jsonl.gz'
            out = gzip.open(path, 'wt', encoding='utf-8')
            rec = recorder.Recorder(_Live(reader), out, clock=lambda: now[0])
            rec.write(kind='start', t=0.0)
            now[0] = recorder.SAVE_EVERY  # the next line brings the file up to date
            rec.write(kind='race', t=5.0)
            killed = path.read_bytes()  # as a kill would leave it: never closed
            out.close()
            path.write_bytes(killed)
            self.assertEqual([r['kind'] for r in recorder.read_records(path)], ['start', 'race'])

    def test_a_closed_recording_reads_in_full(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'race.jsonl.gz'
            with gzip.open(path, 'wt', encoding='utf-8') as out:
                out.write('{"kind":"start"}\n{"kind":"race"}\n')
            self.assertEqual(len(recorder.read_records(path)), 2)


if __name__ == '__main__':
    unittest.main()
