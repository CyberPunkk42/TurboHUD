import os
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud import app, control
from turbohud.core import hud
from turbohud.overlay import choose_platform


class FakeTurboHUD:
    """A socket that answers like a running TurboHUD and notes the commands."""

    def __init__(self, path, answer='ok'):
        self.path, self.answer, self.got = path, answer, []
        control.prepare_folder(path)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(path))
        self.server.listen(4)
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with conn:
                self.got.append(conn.recv(256).decode().strip())
                conn.sendall(self.answer.encode() + b'\n')

    def close(self):
        self.server.close()


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = control.control_path({'XDG_RUNTIME_DIR': self.folder}, 'linux')

    def test_path_in_the_private_runtime_folder(self):
        self.assertEqual(self.path, Path(self.folder) / 'turbohud' / 'control.sock')
        self.assertEqual(
            control.control_path({}, 'linux', uid=1000), Path('/tmp/turbohud-1000/turbohud/control.sock')
        )
        self.assertIsNone(control.control_path({}, 'win32'))

    def test_send_reaches_the_running_turbohud(self):
        fake = FakeTurboHUD(self.path)
        try:
            self.assertEqual(control.send('toggle', self.path), 'ok')
            self.assertEqual(fake.got, ['toggle'])
            self.assertEqual(os.stat(self.path.parent).st_mode & 0o777, 0o700)
        finally:
            fake.close()

    def test_nothing_running(self):
        self.assertIsNone(control.send('quit', self.path))
        control.prepare_folder(self.path)
        self.path.write_text('')  # left behind, nobody listening
        self.assertIsNone(control.send('quit', self.path))
        with self.assertRaises(ValueError):
            control.send('format the disk', self.path)


class CommandLineTests(unittest.TestCase):
    def test_commands_go_to_the_running_turbohud(self):
        sent = []

        def send(command):
            sent.append(command)
            return 'ok'

        self.assertEqual(app.tell_running(app.parse_args(['--toggle']), send), 0)
        self.assertEqual(app.tell_running(app.parse_args(['--quit']), send), 0)
        self.assertEqual(sent, ['toggle', 'quit'])

    def test_a_second_start_switches_the_running_one_to_move_mode(self):
        sent = []

        def send(command):
            sent.append(command)
            return 'ok'

        self.assertEqual(app.tell_running(app.parse_args([]), send), 0)
        self.assertEqual(sent, ['ping', 'move'])

    def test_with_none_running_a_start_starts_and_a_command_fails(self):
        def send(command):
            return None

        self.assertIsNone(app.tell_running(app.parse_args([]), send))
        self.assertIsNone(app.tell_running(app.parse_args(['--move']), send))
        self.assertEqual(app.tell_running(app.parse_args(['--toggle']), send), 1)

    def test_one_command_at_a_time(self):
        with self.assertRaises(SystemExit):
            app.parse_args(['--toggle', '--quit'])


class PlatformTests(unittest.TestCase):
    def test_xwayland_on_wayland_desktops_other_than_hyprland(self):
        kde = {'WAYLAND_DISPLAY': 'wayland-0', 'DISPLAY': ':0', 'XDG_SESSION_TYPE': 'wayland'}
        self.assertEqual(choose_platform(kde, 'linux'), 'xcb')

    def test_left_alone_otherwise(self):
        hyprland = {'WAYLAND_DISPLAY': 'wayland-1', 'DISPLAY': ':1', 'HYPRLAND_INSTANCE_SIGNATURE': 'x'}
        self.assertIsNone(choose_platform(hyprland, 'linux'))
        self.assertIsNone(choose_platform({'DISPLAY': ':0'}, 'linux'))  # X11 session
        self.assertIsNone(
            choose_platform({'WAYLAND_DISPLAY': 'w', 'DISPLAY': ':0', 'QT_QPA_PLATFORM': 'wayland'}, 'linux')
        )
        self.assertIsNone(
            choose_platform(
                {'WAYLAND_DISPLAY': 'w', 'DISPLAY': ':0', 'TURBOHUD_PLATFORM': 'wayland'}, 'linux'
            )
        )
        self.assertIsNone(choose_platform({'WAYLAND_DISPLAY': 'w'}, 'linux'))  # no XWayland
        self.assertIsNone(choose_platform({'WAYLAND_DISPLAY': 'w', 'DISPLAY': ':0'}, 'darwin'))


class HelpTests(unittest.TestCase):
    def test_the_panel_says_how_to_switch_without_shortcuts(self):
        self.assertIn('--toggle', ' '.join(hud.help_lines(shortcuts=False, commands=True)))
        self.assertNotIn('--toggle', ' '.join(hud.help_lines(shortcuts=True, commands=True)))
