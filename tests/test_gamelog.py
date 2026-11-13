import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.tsu import gamelog

ID = '76561197960265728'  # placeholder Steam ID


class EventLogTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        (self.folder / ID / 'Logs').mkdir(parents=True)
        self.now = [0.0]

    def write(self, name, text, age=0):
        path = self.folder / ID / 'Logs' / name
        path.write_text(text)
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))
        return path

    def log(self):
        return gamelog.EventLog(self.folder, clock=lambda: self.now[0])

    def test_running_between_started_and_ended(self):
        self.assertTrue(gamelog.running_in(b'2026-11-01 23:33:21: Event started.\n[x] A disconnected.\n'))
        self.assertFalse(gamelog.running_in(b'Event started.\nEvent ended.\nSession ended.\n'))
        self.assertFalse(gamelog.running_in(b'Event ended.\n'))

    def test_a_log_without_an_event_says_nothing(self):
        # A tester's Mac (2026-11-11): TSU's newest log held only these two lines.
        self.assertIsNone(gamelog.running_in(b'2026-11-08 21:54:56: Log started.\n21:54:57: Log ended.\n'))
        self.assertIsNone(gamelog.running_in(b'Event 1 / 5 is about to start in X.\n'))
        self.write('log.20261108.215456.txt', 'Log started.\nLog ended.\n')
        self.assertIsNone(self.log().running())  # so the search goes ahead

    def test_a_log_from_before_tsu_started_says_nothing(self):
        self.write('log.20261108.214000.txt', 'Event started.\nEvent ended.\n', age=3 * 86400)
        started = time.time() - 600
        self.assertIsNone(gamelog.EventLog(self.folder, since=started).running())

    def test_a_log_written_since_tsu_started_counts(self):
        self.write('log.20261111.002007.txt', 'Event started.\n', age=60)
        started = time.time() - 600
        self.assertTrue(gamelog.EventLog(self.folder, since=started).running())
        self.assertTrue(gamelog.EventLog(self.folder, since=None).running())  # start not known

    def test_the_newest_log_counts(self):
        self.write('log.20261101.210000.txt', 'Event started.\n', age=3600)
        path = self.write('log.20261101.231030.txt', 'Event started.\nEvent ended.\n')
        log = self.log()
        self.assertFalse(log.running())
        with open(path, 'a') as handle:
            handle.write('Event started.\n')
        self.assertTrue(log.running())  # read again once it changed

    def test_the_running_games_log_counts_over_an_older_copy(self):
        # A new run with no dated copy yet: `Logs` still says the last event ended.
        self.write('log.20261101.210000.txt', 'Event started.\nEvent ended.\n', age=3600)
        (self.folder / ID / 'log.txt').write_text('Event started.\n')
        self.assertTrue(self.log().running())

    def test_a_newer_copy_counts_over_an_older_running_log(self):
        live = self.folder / ID / 'log.txt'
        live.write_text('Event started.\n')
        stamp = time.time() - 3600
        os.utime(live, (stamp, stamp))
        self.write('log.20261101.210000.txt', 'Event started.\nEvent ended.\n')
        self.assertFalse(self.log().running())

    def test_the_log_beside_the_accounts_is_not_a_players(self):
        (self.folder / 'log.txt').write_text('Event started.\n')
        self.assertIsNone(self.log().running())

    def test_no_log_is_not_known(self):
        self.assertIsNone(gamelog.EventLog(Path(tempfile.mkdtemp())).running())


class RecordingWatchTests(unittest.TestCase):
    """A recording TSU opened, from its access time: TSU's log says nothing of replays
    (reported by the user on 2026-11-13). Placeholder files only, never real recordings."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.recordings = self.folder / ID / gamelog.RECORDINGS
        (self.recordings / 'Saved').mkdir(parents=True)
        self.now = [0.0]
        self.written = time.time() - 3600

    def recording(self, name, opened=None, inside=''):
        path = self.recordings / inside / name
        path.write_bytes(b'placeholder')
        os.utime(path, (self.written if opened is None else opened, self.written))
        return path

    def watch(self):
        return gamelog.RecordingWatch(self.folder, clock=lambda: self.now[0])

    def test_only_a_recording_read_after_it_was_written_counts(self):
        self.recording('20261113.0018.Track.tsz')  # as recording it leaves it
        self.assertEqual(gamelog.last_opened(self.folder), 0.0)
        self.recording('20261112.2138.Track.tsz', opened=self.written + 600)
        self.recording('notes.txt', opened=self.written + 900)  # not a recording
        self.assertAlmostEqual(gamelog.last_opened(self.folder), self.written + 600, places=0)

    def test_the_saved_recordings_count_too(self):
        self.recording('Kept.tsz', opened=self.written + 60, inside='Saved')
        self.assertAlmostEqual(gamelog.last_opened(self.folder), self.written + 60, places=0)

    def test_no_data_folder_says_nothing(self):
        self.assertIsNone(gamelog.last_opened(self.folder / 'missing'))
        self.assertFalse(gamelog.RecordingWatch(None).opened())

    def test_the_first_look_only_notes_what_is_there(self):
        self.recording('Old.tsz', opened=self.written + 60)
        watch = self.watch()
        self.assertFalse(watch.opened())
        self.now[0] += watch.LOOK_EVERY
        self.assertFalse(watch.opened())

    def test_an_opening_is_told_once(self):
        watch = self.watch()
        self.assertFalse(watch.opened())  # no recording opened yet
        path = self.recording('Watched.tsz', opened=self.written + 600)
        self.assertFalse(watch.opened())  # within LOOK_EVERY: not looked at again
        self.now[0] += watch.LOOK_EVERY
        self.assertTrue(watch.opened())
        self.now[0] += watch.LOOK_EVERY
        self.assertFalse(watch.opened())
        os.utime(path, (self.written + 1200, self.written))  # watched again
        self.now[0] += watch.LOOK_EVERY
        self.assertTrue(watch.opened())
