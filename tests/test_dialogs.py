"""File and message windows above TurboHUD's own on the Mac (reported by the user on 2026-11-15:
the save window opened behind the layouts window)."""

import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class Native:
    def __init__(self, on_top):
        self.dialogs_on_top = on_top
        self.raised = []

    def raise_window(self, widget):
        self.raised.append(widget)
        return 'test'

    def activate(self, widget):
        self.raised.append(('in front', widget))
        return 'test'


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'needs Qt')
class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        if sys.platform == 'win32':  # offscreen finds no fonts there without this
            # The first Qt tests in a full run: without it the font tests after them crashed.
            os.environ.setdefault(
                'QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _until(self, done, seconds=2.0):
        """Qt's events run until `done()`: a 0 ms timer may not fire in the first round (Linux)."""
        end = time.monotonic() + seconds
        while not done() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.005)

    def test_on_the_mac_qts_own_window_raised_to_turbohuds_level(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QFileDialog

        from turbohud.overlay.dialogs import on_top

        native = Native(True)
        dialog = on_top(QFileDialog(), native)
        self.addCleanup(dialog.close)
        self.assertTrue(dialog.testOption(QFileDialog.DontUseNativeDialog))  # the system's cannot be raised
        self.assertTrue(dialog.windowFlags() & Qt.WindowStaysOnTopHint)
        self.assertTrue(dialog.focusable)  # a name is typed in it
        self.assertEqual(native.raised, [])
        self._until(lambda: len(native.raised) >= 2)  # as exec() runs: raised once shown
        # then in front of TurboHUD's windows on that level: raised alone, it went behind the
        # settings window (Add font..., 2026-11-17)
        self.assertEqual(native.raised, [dialog, ('in front', dialog)])

    def test_elsewhere_the_systems_own_as_before(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        from turbohud.overlay.dialogs import on_top

        native = Native(False)
        for dialog in (QFileDialog(), QMessageBox()):
            self.addCleanup(dialog.close)
            on_top(dialog, native)
            self.app.processEvents()
        self.assertFalse(QFileDialog().testOption(QFileDialog.DontUseNativeDialog))
        self.assertEqual(native.raised, [])
        self.assertEqual(on_top(QMessageBox(), object()).windowTitle(), '')  # a Native without it: no change

    def test_the_chosen_path_or_nothing(self):
        from PySide6.QtWidgets import QFileDialog

        from turbohud.overlay.dialogs import open_path, save_path

        with tempfile.TemporaryDirectory() as folder:
            suggested = Path(folder) / '2560x1440.json'
            with mock.patch.object(QFileDialog, 'exec', return_value=QFileDialog.Accepted):
                chosen = save_path(
                    None, Native(True), 'Export layout', suggested, 'TurboHUD layouts (*.json)'
                )
            self.assertEqual(Path(chosen).name, '2560x1440.json')
            with mock.patch.object(QFileDialog, 'exec', return_value=QFileDialog.Rejected):
                self.assertEqual(open_path(None, Native(True), 'Import layout', folder, '*.json'), '')

    def test_a_warning_on_top_too(self):
        from PySide6.QtWidgets import QMessageBox

        from turbohud.overlay.dialogs import warn

        native = Native(True)
        shown = []
        with mock.patch.object(QMessageBox, 'exec', lambda box: shown.append(box.text()) or 0):
            warn(None, native, 'That file is not a TurboHUD layout.')
        self._until(lambda: len(native.raised) >= 2)  # one round was too soon for it on Linux
        self.assertEqual(shown, ['That file is not a TurboHUD layout.'])
        self.assertEqual(native.raised[1:], [('in front', native.raised[0])])  # raised, then in front

    def test_the_mac_asks_for_it(self):
        if sys.platform != 'darwin':
            self.skipTest('the Mac')
        from turbohud.overlay.macos import Native as MacNative

        self.assertTrue(MacNative.dialogs_on_top)


if __name__ == '__main__':
    unittest.main()
