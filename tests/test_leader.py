"""The race leader banner (turbohud.core.leader, asked for by the user on 2026-11-16)."""

import unittest

from turbohud.core import leader
from turbohud.core.leader import Banner, LeadChanges, banner_opacity


class Car:
    """What LeadChanges reads of a player: its name, whether it finished, the checkpoints passed."""

    def __init__(self, name, passed=2, finished=False):
        self.name = name
        self.passed = (0,) * passed
        self.finished = finished


def run(changes, orders, start=0.0, step=0.5):
    """Feed `orders` (lists of cars) one read every `step` seconds; the banners seen, by time."""
    seen = []
    for index, order in enumerate(orders):
        clock = start + index * step
        seen.append((clock, changes.update(order, clock)))
    return seen


class OpacityTest(unittest.TestCase):
    def test_it_fades_in_stays_and_fades_out_over_six_seconds(self):
        self.assertIsNone(banner_opacity(-0.1))
        self.assertEqual(banner_opacity(0.0), 0.0)
        self.assertAlmostEqual(banner_opacity(0.5), 0.5)
        self.assertEqual(banner_opacity(1.0), 1.0)
        self.assertEqual(banner_opacity(3.0), 1.0)
        self.assertAlmostEqual(banner_opacity(5.5), 0.5)
        self.assertEqual(banner_opacity(6.0), 0.0)
        self.assertIsNone(banner_opacity(6.01))
        self.assertIsNone(banner_opacity(None))

    def test_the_titles(self):
        self.assertEqual(Banner('A', False, 1.0).title, 'New Race Leader')
        self.assertEqual(Banner('A', True, 1.0).title, 'Race Winner')


class LeadChangesTest(unittest.TestCase):
    def setUp(self):
        self.a, self.b, self.c = Car('Alpha'), Car('Bravo'), Car('Charlie')

    def test_the_first_leader_is_no_change(self):
        seen = run(LeadChanges(), [[self.a, self.b]] * 30)
        self.assertTrue(all(banner is None for _clock, banner in seen))

    def test_a_new_leader_shows_after_leading_five_seconds(self):
        changes = LeadChanges()
        changes.update([self.a, self.b], 0.0)
        self.assertIsNone(changes.update([self.b, self.a], 10.0))  # takes the lead
        self.assertIsNone(changes.update([self.b, self.a], 14.9))  # not yet 5 s
        banner = changes.update([self.b, self.a], 15.0)
        self.assertEqual(banner, Banner('Bravo', False, 0.0))  # fading in from here
        self.assertEqual(changes.update([self.b, self.a], 17.0).opacity, 1.0)
        self.assertIsNone(changes.update([self.b, self.a], 21.5))  # over after 6 s
        self.assertIsNone(changes.update([self.b, self.a], 40.0))  # and once only

    def test_a_lead_lost_again_within_five_seconds_shows_nothing(self):
        changes = LeadChanges()
        changes.update([self.a, self.b], 0.0)
        changes.update([self.b, self.a], 10.0)
        changes.update([self.a, self.b], 13.0)  # back to Alpha
        for clock in (15.0, 16.0, 20.0, 30.0):
            self.assertIsNone(changes.update([self.a, self.b], clock))

    def test_a_third_car_taking_the_lead_starts_the_wait_again(self):
        changes = LeadChanges()
        changes.update([self.a, self.b, self.c], 0.0)
        changes.update([self.b, self.a, self.c], 10.0)
        changes.update([self.c, self.b, self.a], 13.0)  # Charlie passes them both
        self.assertIsNone(changes.update([self.c, self.b, self.a], 17.0))  # Charlie 4 s only
        self.assertEqual(changes.update([self.c, self.b, self.a], 18.0).name, 'Charlie')

    def test_no_change_counts_on_the_grid(self):
        changes = LeadChanges()
        on_grid = Car('Alpha', passed=1), Car('Bravo', passed=1)
        changes.update(list(on_grid), 0.0)
        # The order settles before the first checkpoint (online, positions come late).
        for clock in (1.0, 3.0, 7.0):
            self.assertIsNone(changes.update(list(reversed(on_grid)), clock))
        # Bravo then leads through the first checkpoint: the leader from the start, no change.
        for clock in (8.0, 12.0, 20.0):
            self.assertIsNone(changes.update([self.b, self.a], clock))

    def test_the_winner_shows_at_once(self):
        changes = LeadChanges()
        changes.update([self.a, self.b], 100.0)
        winner = Car('Alpha', finished=True)
        banner = changes.update([winner, self.b], 101.0, lambda player: 100.9)
        self.assertEqual(banner, Banner('Alpha', True, 0.0))
        self.assertEqual(changes.update([winner, self.b], 103.0).opacity, 1.0)
        self.assertIsNone(changes.update([winner, self.b], 107.5))

    def test_the_winner_replaces_a_lead_banner_and_ends_lead_changes(self):
        changes = LeadChanges()
        changes.update([self.a, self.b], 0.0)
        changes.update([self.b, self.a], 10.0)
        self.assertEqual(changes.update([self.b, self.a], 15.0).name, 'Bravo')
        winner = Car('Bravo', finished=True)
        self.assertTrue(changes.update([winner, self.a], 16.0).winner)
        # Later finishers, or an order shuffled after the finish, tell nothing more.
        for clock in (23.0, 30.0, 40.0):
            self.assertIsNone(changes.update([Car('Alpha', finished=True), winner], clock))

    def test_a_winner_long_in_is_not_told(self):
        changes = LeadChanges()
        winner = Car('Alpha', finished=True)
        self.assertIsNone(changes.update([winner, self.b], 200.0, lambda player: 120.0))

    def test_a_new_race_starts_afresh(self):
        changes = LeadChanges()
        changes.update([Car('Alpha', finished=True), self.b], 300.0)
        # The next race: its clock starts again, and its first leader is no change.
        self.assertIsNone(changes.update([self.b, self.a], 1.0))
        self.assertIsNone(changes.update([self.a, self.b], 10.0))
        self.assertEqual(changes.update([self.a, self.b], 15.0).name, 'Alpha')

    def test_reset_takes_the_leader_then_as_known(self):
        changes = LeadChanges()
        changes.update([self.a, self.b], 0.0)
        changes.update([self.b, self.a], 10.0)
        changes.reset()  # the section unticked
        for clock in (11.0, 16.0, 30.0):
            self.assertIsNone(changes.update([self.b, self.a], clock))

    def test_the_hold_is_five_seconds_and_the_banner_six(self):
        self.assertEqual(leader.LEAD_HOLD, 5.0)
        self.assertEqual(leader.BANNER_SHOWN, 6.0)


class RaceBannerTest(unittest.TestCase):
    """The banner through race.leader_banner, as the race sections get it."""

    def state(self, players, clock, **kwargs):
        from turbohud.core import race

        return race.LapState(clock, 0, 1, 5, [0, 0], players=tuple(players), **kwargs)

    def players(self, leader_first=True, finished=False):
        from turbohud.core import race

        ahead = race.PlayerState('Speedy Driver', 0, 1, ((0, 1000), (2000,)), finished=finished)
        behind = race.PlayerState('Me', 0, 1, ((0, 1100), (2100,)), local=True)
        return (ahead, behind) if leader_first else (behind, ahead)

    def test_the_row_and_the_banner(self):
        from turbohud.core import race

        changes = LeadChanges()
        units = race.UNITS_PER_SECOND
        first = self.players(leader_first=False)
        self.assertEqual(race.leader_banner(self.state(first, units), first, units, changes), {})
        now = self.players()
        race.leader_banner(self.state(now, 10 * units), now, 10 * units, changes)
        shown = race.leader_banner(self.state(now, 16 * units), now, 16 * units, changes)
        self.assertEqual(shown['banner'].name, 'Speedy Driver')
        (row,) = shown['leader']
        self.assertEqual(row.text, 'New Race Leader  -  Speedy Driver')
        self.assertTrue(row.centred)

    def test_a_long_name_is_cut_as_in_the_lists(self):
        from turbohud.core import race

        changes = LeadChanges()
        long = race.PlayerState('A' * 30, 0, 1, ((0, 1000), (2000,)), finished=True)
        shown = race.leader_banner(self.state((long,), 5000), (long,), 5000, changes)
        self.assertEqual(shown['leader'][0].text, f'Race Winner  -  {"A" * 17}…')

    def test_none_in_hotlapping_nor_in_an_arena(self):
        from turbohud.core import race

        winner = self.players(finished=True)
        for kwargs in ({'hotlapping': True}, {'on_a_track': False}):
            state = self.state(winner, 5000, **kwargs)
            self.assertEqual(race.leader_banner(state, winner, 5000, LeadChanges()), {})

    def test_none_without_a_follower(self):
        from turbohud.core import race

        winner = self.players(finished=True)
        self.assertEqual(race.leader_banner(self.state(winner, 5000), winner, 5000, None), {})

    def test_without_an_order_it_ranks_the_cars_itself(self):
        from turbohud.core import race

        winner = self.players(finished=True)
        shown = race.leader_banner(self.state(winner, 5000), None, 5000, LeadChanges())
        self.assertTrue(shown['banner'].winner)


class BannerSectionTest(unittest.TestCase):
    """The Race leader section: its box, its first place and how it is drawn."""

    def section(self):
        from turbohud.core.hud import RACE_SECTIONS

        return next(s for s in RACE_SECTIONS if s.name == 'leader')

    def test_it_is_under_race_in_the_panel(self):
        from turbohud.core.hud import PANEL_CATEGORIES

        self.assertIn('leader', dict(PANEL_CATEGORIES)['Race'])

    def test_its_box_has_room_for_the_flag_after_the_text(self):
        from dataclasses import replace

        from turbohud.core import hud

        def measure(text, size):
            return len(text) * size * 0.5

        section = self.section()
        width, height = hud.base_size(section, 1.0, measure)
        plain = hud.base_size(replace(section, end=0.0), 1.0, measure)[0]
        self.assertEqual(width - plain, hud.end_room(section, height))
        self.assertGreater(hud.end_room(section, height), height)  # wider than tall

    def test_it_starts_at_the_top_centre_below_the_blue_flag(self):
        from turbohud.core import hud

        screen = (0, 0, 1920, 1080)
        x, y, width, _height = hud.drawing_place(self.section(), (600, 40), screen)
        self.assertEqual(x + width // 2, 960)
        blue = next(s for s in hud.RACE_SECTIONS if s.name == 'blueflag')
        flag = hud.drawing_place(blue, (480, 24), screen)
        self.assertGreater(y, flag[1] + flag[3])


class BannerDrawingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def window(self):
        from turbohud.core.hud import RACE_SECTIONS, text_box
        from turbohud.core.settings import Theme
        from turbohud.hud.painter import text_ink, text_width
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        section = next(s for s in RACE_SECTIONS if s.name == 'leader')
        window = SectionWindow(Native(), Theme(), section)
        self.addCleanup(window.close)
        window.font = 26
        box = text_box(section, (0, 0, 10, 10), 26, text_width, text_ink)
        window.resize(box[2], box[3])
        window.set_locked(True)
        return window

    def show(self, window, winner, opacity=1.0, blue=None):
        from turbohud.core.hud import BANNER_TEXT, Row

        title = 'Race Winner' if winner else 'New Race Leader'
        window.show_content(
            [Row(f'{title}  -  Someone', 'title', BANNER_TEXT, centred=True)],
            None,
            blue,
            banner=Banner('Someone', winner, opacity),
        )
        return window.grab().toImage()

    def flag_area(self, image):
        """The colours down the middle of the flag's room at the right end."""
        x = image.width() - image.height() // 2
        return [image.pixelColor(x, y).lightness() for y in range(2, image.height() - 2)]

    def test_the_winner_has_a_checkered_flag_at_the_right(self):
        window = self.window()
        light = self.flag_area(self.show(window, True))
        self.assertGreater(max(light), 200)  # white squares
        self.assertLess(min(light), 40)  # black ones

    @staticmethod
    def text_middle(image, right=None):
        """The middle, across, of the banner's white letters (left of `right` if given)."""
        right = image.width() if right is None else right
        xs = [
            x
            for x in range(right)
            for y in range(image.height() // 4, 3 * image.height() // 4)
            if image.pixelColor(x, y).lightness() > 200
        ]
        return (min(xs) + max(xs)) / 2

    def test_a_new_leaders_text_in_the_middle_of_the_box(self):
        # It sat left of the middle by half the flag's room (reported by the user on 2026-11-17).
        window = self.window()
        image = self.show(window, False)
        # Within 1% of the width: the letters' own drawing; before, it was about 9% off.
        self.assertAlmostEqual(self.text_middle(image), image.width() / 2, delta=image.width() / 100)

    def test_the_winners_text_in_the_middle_of_the_room_before_the_flag(self):
        from turbohud.core import hud

        window = self.window()
        image = self.show(window, True)
        room = image.width() - hud.end_room(window.section, image.height())
        self.assertAlmostEqual(self.text_middle(image, room - 1), room / 2, delta=image.width() / 100)

    def test_a_new_leader_has_none(self):
        window = self.window()
        self.assertLess(max(self.flag_area(self.show(window, False))), 60)  # the black end only

    def test_it_is_shaded_grey_to_black(self):
        window = self.window()
        image = self.show(window, False)
        y = 3  # above the text
        left, right = image.pixelColor(4, y), image.pixelColor(image.width() - 4, y)
        self.assertGreater(left.lightness(), right.lightness() + 40)

    def test_the_whole_box_fades(self):
        window = self.window()
        full = self.show(window, False, 1.0).pixelColor(4, 3).alpha()
        half = self.show(window, False, 0.5).pixelColor(4, 3).alpha()
        self.assertEqual(full, 255)
        self.assertLess(half, 160)

    def test_no_blue_frame_on_it(self):
        window = self.window()
        plain = self.show(window, False).pixelColor(3, window.height() // 2)
        framed = self.show(window, False, blue=1.0).pixelColor(3, window.height() // 2)
        self.assertEqual(plain, framed)


if __name__ == '__main__':
    unittest.main()
