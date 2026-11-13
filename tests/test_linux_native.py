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

    def geometries(self, addresses):
        return {address: self.where for address in addresses}

    def move(self, address, x, y):
        self.moved = (address, x, y)
        return True

    def place(self, address, x, y, width, height, focusable=False):
        self.placed = (address, x, y, width, height, focusable)
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
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def native(self, hypr):
        from turbohud.overlay.linux import Native

        return Native(hypr)

    def test_without_hyprland_qt_does_it(self):
        self.assertIsNone(self.native(None).placement(FakeWidget()))

    def test_the_last_known_place_is_kept_once_the_window_is_gone(self):
        hypr = FakeHypr()
        native = self.native(hypr)
        widget = FakeWidget()
        native.addresses[id(widget)] = '0xaaa'
        self.assertEqual(native.placement(widget), (300, 200, 450, 220))
        hypr.where, widget.visible = None, False
        self.assertEqual(native.placement(widget), (300, 200, 450, 220))

    def test_focus_goes_back_to_the_window_that_had_it(self):
        hypr = FakeHypr()
        native = self.native(hypr)
        native.prepare_app()
        native.addresses[1] = '0xaaa'
        native.give_focus_back()
        self.assertEqual(hypr.focused, ['0xgame'])


if __name__ == '__main__':
    unittest.main()

    def test_group_moves_on_hyprland(self):
        hypr = FakeHypr()
        native = self.native(hypr)
        widget = FakeWidget()
        widget.locked = False
        native.addresses[id(widget)] = '0xaaa'
        self.assertEqual(native.placements([widget]), {id(widget): (300, 200, 450, 220)})
        native.move_window(widget, (350, 220, 450, 220))
        self.assertEqual(hypr.moved, ('0xaaa', 350, 220))
        self.assertEqual(native.placement(FakeWidget()), None)  # unknown window: nothing
        native.move_window(widget, (350, 220, 450, 220), settle=True)
        self.assertEqual(hypr.placed, ('0xaaa', 350, 220, 450, 220, True))  # still movable
