"""The game controller's triggers, read straight from the device (Linux), for pedal bars
that follow every bit of trigger travel.

TSU rounds throttle and brake to thirds before the car gets them (checked in a drive:
only 0, 1/3, 2/3 and 1 occur), so its own values move in steps. The controller reports
its triggers finely. This reads a gamepad through the Linux joystick interface
(`/dev/input/js*`), which the logged-in user may read; it never opens a keyboard. With
Steam Input the game sees a virtual "X-Box 360 pad": throttle on the right trigger
(axis 5), brake on the left (axis 2), each from -32767 (released) to 32767 (pressed).
"""

import array
import fcntl
import glob
import logging
import os
import re
import select
import struct
import threading
import time

THROTTLE_AXIS = 5  # right trigger on an Xbox-style pad
BRAKE_AXIS = 2  # left trigger
AXIS_MIN, AXIS_MAX = -32767, 32767
PAD_NAMES = re.compile(r'x-?box|gamepad|game ?pad|controller|wheel|\bpad\b', re.IGNORECASE)
RESCAN_SECONDS = 2.0
FRESH_SECONDS = 1.0  # a pad that has said nothing for longer may be gone

JS_EVENT_AXIS = 0x02
JSIOCGNAME = 0x80806A13  # name, 128 bytes

log = logging.getLogger(__name__)


def trigger(value):
    """0 (released) to 1 (pressed) for a trigger axis value."""
    return min(max((value - AXIS_MIN) / (AXIS_MAX - AXIS_MIN), 0.0), 1.0)


def device_name(fd):
    name = array.array('B', [0] * 128)
    fcntl.ioctl(fd, JSIOCGNAME, name)
    return bytes(name).split(b'\0', 1)[0].decode('utf-8', 'replace')


def is_pad(name):
    return bool(PAD_NAMES.search(name))


class Pad:
    """Reads the first gamepad found in a background thread; `pedals()` gives the latest
    (throttle, brake), or None without a pad."""

    def __init__(
        self,
        pattern='/dev/input/js*',
        throttle_axis=THROTTLE_AXIS,
        brake_axis=BRAKE_AXIS,
        clock=time.monotonic,
    ):
        self.pattern = pattern
        self.throttle_axis = throttle_axis
        self.brake_axis = brake_axis
        self._clock = clock
        self._axes = {}
        self._heard = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def pedals(self):
        with self._lock:
            if not self._heard or self._clock() - self._heard > FRESH_SECONDS:
                return None
            if self.throttle_axis not in self._axes or self.brake_axis not in self._axes:
                return None
            return trigger(self._axes[self.throttle_axis]), trigger(self._axes[self.brake_axis])

    def feed(self, data):
        """Take raw joystick events (8 bytes each: time, value, type, number)."""
        with self._lock:
            for index in range(0, len(data) - 7, 8):
                _time, value, kind, number = struct.unpack_from('<IhBB', data, index)
                if kind & JS_EVENT_AXIS:
                    self._axes[number] = value
            self._heard = self._clock()

    def start(self):
        self._thread = threading.Thread(target=self._run, name='turbohud-pad', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _open(self):
        for path in sorted(glob.glob(self.pattern)):
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                continue
            try:
                name = device_name(fd)
            except OSError:
                name = ''
            if is_pad(name):
                log.info('pedal bars: reading the triggers of %s (%s)', name, path)
                return fd
            os.close(fd)
        return None

    def _run(self):
        fd = None
        while not self._stop.is_set():
            if fd is None:
                fd = self._open()
                if fd is None:
                    self._stop.wait(RESCAN_SECONDS)
                    continue
            try:
                if select.select([fd], [], [], 0.2)[0]:
                    self.feed(os.read(fd, 8 * 256))
            except BlockingIOError:
                continue
            except OSError:
                # Unplugged, or Steam took its virtual pad away: look again.
                os.close(fd)
                fd = None
                with self._lock:
                    self._axes, self._heard = {}, 0.0
        if fd is not None:
            os.close(fd)


def combined(game, pad):
    """The pedal bars' (throttle, brake): the greater of the game's value and the pad's,
    so a pad shows its full travel and a keyboard still shows through the game."""
    if pad is None:
        return game
    if game is None:
        return pad
    return tuple(None if g is None and p is None else max(g or 0.0, p or 0.0) for g, p in zip(game, pad))
