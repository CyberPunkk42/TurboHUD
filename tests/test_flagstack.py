import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core.flagstack import combined, overlap

YELLOW = (800, 100, 320, 110)
BLUE = (820, 120, 480, 24)  # put in the same spot by the player
APART = (800, 900, 480, 24)


class CombinedTests(unittest.TestCase):
    """Reported by the user on 2026-11-11: stacked, the two flags covered twice the track.
    Both out in one spot: the yellow box with a blue frame; apart: each in its place."""

    def test_both_out_in_one_spot_are_combined(self):
        self.assertTrue(combined(YELLOW, BLUE, True, True))

    def test_one_out_or_apart_are_not(self):
        self.assertFalse(combined(YELLOW, BLUE, True, False))
        self.assertFalse(combined(YELLOW, BLUE, False, True))
        self.assertFalse(combined(YELLOW, APART, True, True))
        self.assertFalse(overlap(YELLOW, (1120, 100, 50, 50)))  # touching edges is not overlapping


class BlueFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_the_yellow_box_gets_a_blue_frame_and_keeps_its_size(self):
        from turbohud.core import race
        from turbohud.core.hud import RACE_SECTIONS
        from turbohud.core.settings import Theme
        from turbohud.overlay.window import SectionWindow

        class Native:
            def raise_window(self, window):
                return 'test'

        section = next(s for s in RACE_SECTIONS if s.name == 'yellowflag')
        window = SectionWindow(Native(), Theme(), section)
        self.addCleanup(window.close)
        window.resize(*window.base)
        window.set_locked(True)
        me = race.PlayerState('Me', 0, 1, ((0,), (0, 1000)), local=True)
        state = race.LapState(0, 0, 1, 5, [0, 0], players=(me,), gates=(((0, 0), (1, 1)),) * 9)
        rows = race.yellow_rows((race.Incident('Someone', 'stopped', 0),), state)

        def edge(opacity):
            window.show_content(rows, None, opacity)
            image = window.grab().toImage()
            return image.pixelColor(3, image.height() // 2), image.size()

        plain, size = edge(None)
        framed, framed_size = edge(1.0)
        self.assertGreater(plain.red(), 200)  # yellow at the edge
        self.assertLess(framed.red(), 60)  # navy at the edge
        self.assertGreater(framed.blue(), framed.red())
        self.assertEqual(size, framed_size)  # no larger


if __name__ == '__main__':
    unittest.main()
