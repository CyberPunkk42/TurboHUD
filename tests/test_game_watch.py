"""Quit with TSU (asked for by drivers on 2026-11-28): when the game, once seen, is gone."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core.game_watch import GONE_FOR, GameWatch
from turbohud.core.race import RACING, STARTING, WAITING_FOR_GAME, WAITING_FOR_RACE


class GameWatchTests(unittest.TestCase):
    def test_started_before_tsu_it_waits_for_it(self):
        watch = GameWatch()
        for second in range(0, 600, 5):
            self.assertFalse(watch.gone(WAITING_FOR_GAME, float(second)))

    def test_tsu_gone_long_enough_after_it_was_seen(self):
        watch = GameWatch()
        self.assertFalse(watch.gone(WAITING_FOR_RACE, 0.0))  # TSU's menu: the game is there
        self.assertFalse(watch.gone(WAITING_FOR_GAME, 100.0))
        self.assertFalse(watch.gone(WAITING_FOR_GAME, 100.0 + GONE_FOR - 0.1))
        self.assertTrue(watch.gone(WAITING_FOR_GAME, 100.0 + GONE_FOR))

    def test_a_connection_made_again_at_once_is_not_a_quit(self):
        watch = GameWatch()
        watch.gone(RACING, 0.0)
        watch.gone(WAITING_FOR_GAME, 1.0)  # a read failed: the connection was dropped
        self.assertFalse(watch.gone(STARTING, 3.0))  # and made again: the game is still there
        self.assertFalse(watch.gone(WAITING_FOR_GAME, 4.0))  # gone again: the time starts afresh
        self.assertFalse(watch.gone(WAITING_FOR_GAME, 4.0 + GONE_FOR - 1))
        self.assertTrue(watch.gone(WAITING_FOR_GAME, 4.0 + GONE_FOR))

    def test_every_status_but_waiting_for_the_game_means_tsu_is_there(self):
        for status in (RACING, STARTING, WAITING_FOR_RACE):
            watch = GameWatch(gone_for=0.0)
            self.assertFalse(watch.gone(status, 0.0))
            self.assertTrue(watch.seen)
            self.assertTrue(watch.gone(WAITING_FOR_GAME, 1.0))


if __name__ == '__main__':
    unittest.main()
