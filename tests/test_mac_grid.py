"""Move mode's grid beneath the sections on the Mac (reported by the user on 2026-11-17: every section
lay behind it). Seen with real windows in macOS's own window order; here the call it rests on."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@unittest.skipUnless(sys.platform == 'darwin' and importlib.util.find_spec('PySide6'), 'the Mac, with Qt')
class MacGridTests(unittest.TestCase):
    def test_to_the_back_of_turbohuds_level(self):
        from turbohud.overlay import macos

        native = macos.Native.__new__(macos.Native)
        grid = mock.Mock(winId=mock.Mock(return_value=7))
        calls = []

        def send(receiver, selector, *args, **_kinds):
            calls.append((selector, args))
            return 'window' if selector == 'window' else None

        with mock.patch.object(macos, 'send', side_effect=send):
            self.assertEqual(native.place_below(grid, [object()]), "beneath TurboHUD's windows")
            self.assertEqual(native.place_below(grid, []), 'nothing to go below')
        self.assertEqual(calls[-1], ('orderWindow:relativeTo:', (macos.NS_WINDOW_BELOW, 0)))
        self.assertEqual(len(calls), 2)  # nothing sent with no section shown


if __name__ == '__main__':
    unittest.main()
