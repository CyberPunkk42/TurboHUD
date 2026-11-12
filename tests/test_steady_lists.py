"""The lap times and the player list keep their size and their columns' places as the content
changes (reported by the user on 2026-11-12: a CUT or a longer gap made them jump)."""

import dataclasses
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import class_registry as reg
from turbohud.core import hud


def measure(text, size):
    return len(text) * size * 0.55


def section(name):
    return next(s for s in hud.RACE_SECTIONS if s.name == name)


def rows_like_sample(name, **changes):
    return [dataclasses.replace(row, **changes) for row in section(name).samples[0]]


class SteadyWidthTests(unittest.TestCase):
    def test_a_cut_or_pit_does_not_make_the_lap_times_wider(self):
        laps = section('laptimes')
        usual = hud.content_size(hud.widest_rows(laps, list(laps.samples[0]), 1.0, measure), 1.0, measure)[0]
        short = [dataclasses.replace(r, text='1. Al') for r in laps.samples[0][1:]]
        for entry in ('CUT 12.3s', 'JUMP', 'PIT', '(12.03s)', 'Fin'):
            rows = [laps.samples[0][0], *[dataclasses.replace(r, right=entry) for r in short]]
            widest = hud.widest_rows(laps, rows, 1.0, measure)
            self.assertEqual(hud.content_size(widest, 1.0, measure)[0], usual, entry)

    def test_wider_than_the_usual_content_still_counts(self):
        laps = section('laptimes')
        long = rows_like_sample('laptimes', text='1. ' + 'W' * 40)
        usual = hud.content_size(hud.widest_rows(laps, list(laps.samples[0]), 1.0, measure), 1.0, measure)[0]
        self.assertGreater(
            hud.content_size(hud.widest_rows(laps, long, 1.0, measure), 1.0, measure)[0], usual
        )

    def test_the_player_lists_usual_content_has_room_for_the_longest_class(self):
        players = section('players')
        self.assertTrue(all(len(r.tag) >= len('PROAM P20') for r in players.samples[0]))


class SteadyColumnTests(unittest.TestCase):
    def columns(self, rows, reserve):
        lines = hud.hud_lines(rows) + hud.hud_lines(reserve)
        middle = hud.middle_right(lines, 500, 14, measure)
        tyre = hud.tyre_right(lines, middle, measure)
        return middle, tyre, hud.tag_left(lines, hud.before_right(lines, middle, measure, tyre), measure)

    def test_a_longer_gap_or_tag_keeps_the_columns_in_place(self):
        reserve = list(section('players').samples[0])
        base = rows_like_sample('players', middle='+0.100', tag='GT3 P2')
        changed = rows_like_sample('players', middle='-12.345', tag='GT4 P12')
        self.assertEqual(self.columns(base, reserve), self.columns(changed, reserve))


class PaceCarTests(unittest.TestCase):
    def test_safety_and_pace_cars_are_classes(self):
        self.assertEqual(reg.car_class('SC').name, 'Safety Car')
        self.assertEqual(reg.car_class('[pc]').name, 'Pace Car')
        self.assertEqual(reg.car_class('SC').category, reg.CUSTOM)


if __name__ == '__main__':
    unittest.main()
