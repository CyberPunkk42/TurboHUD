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
        self.assertFalse(gamelog.running_in(b'Event 1 / 5 is about to start in X.\n'))

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
