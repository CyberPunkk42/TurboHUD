import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeHypr:
    def __init__(self):
        self.where = (300, 200, 450, 220)
        self.focused = []

    def active_window(self):
        return '0xgame'

    def geometry(self, address):
        return self.where

    def focus(self, address):
        self.focused.append(address)
        return True


class FakeWidget:
    visible = True

    def isVisible(self):
        return self.visible


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class LinuxNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtGui import QGuiApplication

        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def native(self, hypr):
        from turbohud.overlay.linux import Native

        return Native(hypr)

    def test_without_hyprland_qt_does_it_and_move_mode_locks_as_before(self):
        native = self.native(None)
        self.assertTrue(native.auto_lock)
        self.assertIsNone(native.placement(FakeWidget()))

    def test_on_hyprland_move_mode_does_not_lock_when_focus_moves(self):
        self.assertFalse(self.native(FakeHypr()).auto_lock)

    def test_the_last_known_place_is_kept_once_the_window_is_gone(self):
        hypr = FakeHypr()
        native = self.native(hypr)
        native.address = '0xaaa'
        widget = FakeWidget()
        self.assertEqual(native.placement(widget), (300, 200, 450, 220))
        hypr.where, widget.visible = None, False
        self.assertEqual(native.placement(widget), (300, 200, 450, 220))

    def test_focus_goes_back_to_the_window_that_had_it(self):
        hypr = FakeHypr()
        native = self.native(hypr)
        native.prepare_app()
        native.address = '0xaaa'
        native.give_focus_back()
        self.assertEqual(hypr.focused, ['0xgame'])


if __name__ == '__main__':
    unittest.main()
