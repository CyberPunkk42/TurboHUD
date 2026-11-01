"""TSU's race data from memory, and what the HUD shows of it.

The reader follows the game's own objects by name (see turbohud.core.il2cpp):

    TS.Services (static sm_instance)
      .m_activeServer.m_eventListener          the event controller
      .m_eventState                            TS.EventState
          .times                               race clock: ticks, time, time limit
          .players[i]                          TS.EventPlayer; the local one has
                                               m_localHumanIndex >= 0
              .m_stats                         TS.PlayerRaceStats
                  .m_lapsCompleted, .m_lapsToFinish, .m_finished
                  .m_checkpointTimesForLaps[lap].m_times      when each checkpoint of
                                               that lap was passed; [0] is the lap's start

All times are whole numbers in steps of 0.1 ms. A lap's time is the start of the next
lap minus its own start; the current lap is the race clock minus its start. A lap has a
fixed number of checkpoints (120 on the tracks seen); the current lap's list grows as
they are passed, so comparing the same checkpoint with the best lap gives the delta. Checked
against the game's own lap times on 2026-11-01: they match exactly.
"""

import math
import struct
from dataclasses import dataclass

from turbohud.core.hud import Row, clock
from turbohud.core.il2cpp import ARRAY_DATA, LIST_ITEMS, NotFound

UNITS_PER_SECOND = 10_000
# EventState.times: ticks, time, ..., time limit (int32 each).
TIMES_TICKS, TIMES_NOW, TIMES_LIMIT = 0, 4, 20
# How far the HUD runs the current lap on by itself between two reads.
MAX_EXTRAPOLATION = 1.0  # seconds

# What the live reader is doing, for Snapshot.status.
NO_CHECKPOINT = 0xFFFF_FFFF  # how a missed checkpoint may be marked

WAITING_FOR_GAME = 'waiting for game'
WAITING_FOR_RACE = 'waiting for race'
RACING = 'racing'


@dataclass(frozen=True)
class LapState:
    clock: int  # race clock, 0.1 ms
    time_limit: int
    laps_completed: int
    laps_to_finish: int
    lap_starts: list  # when each started lap began, 0.1 ms
    finished: bool = False
    checkpoints: tuple = ()  # per started lap, when each checkpoint was passed, 0.1 ms
    position: tuple | None = None  # the car's (x, z)
    gates: tuple = ()  # the checkpoint lines, ((x1, z1), (x2, z2)), in checkpoint order

    @property
    def lap_times(self):
        return [b - a for a, b in zip(self.lap_starts, self.lap_starts[1:])][: self.laps_completed]

    @property
    def current_lap(self):
        return self.clock - self.lap_starts[-1] if self.lap_starts else None

    @property
    def last_lap(self):
        return self.lap_times[-1] if self.lap_times else None

    @property
    def best_lap(self):
        return min(self.lap_times) if self.lap_times else None

    @property
    def best_lap_index(self):
        times = self.lap_times
        return times.index(min(times)) if times else None

    @property
    def delta_to_best(self):
        """This lap against the best lap: negative is ahead, positive behind; None on the
        first lap or before the first checkpoint.

        Live where the car's position and the checkpoint lines are known: how far the car
        is between the last line passed and the next gives the moment the best lap was at
        the same place (between its times at those lines), compared with the race clock.
        Otherwise at the last checkpoint both laps passed."""
        best_index = self.best_lap_index
        if best_index is None or len(self.checkpoints) < 2 or best_index >= len(self.checkpoints) - 1:
            return None
        current, best = self.checkpoints[-1], self.checkpoints[best_index]
        live = self._live_delta(current, best, best_index)
        if live is not None:
            return live
        for k in range(min(len(current), len(best)) - 1, 0, -1):
            if _passed(current, k) and _passed(best, k):
                elapsed = current[k] - current[0]
                return elapsed - (best[k] - best[0]) if elapsed > 0 else None
        return None

    def _live_delta(self, current, best, best_index):
        k = len(current) - 1  # the last line passed in this lap
        if self.position is None or len(self.gates) != len(best) or k >= len(best):
            return None
        if not (_passed(current, k) and _passed(best, k)):
            return None
        if k + 1 == len(best):
            following = self.lap_starts[best_index + 1]  # the next line is the finish
        elif _passed(best, k + 1):
            following = best[k + 1]
        else:
            return None
        share = gate_share(self.gates[k], self.gates[(k + 1) % len(self.gates)], self.position)
        best_here = best[k] + share * (following - best[k]) - best[0]
        elapsed = self.clock - current[0]
        return round(elapsed - best_here) if elapsed > 0 else None

    @property
    def time_left(self):
        return self.time_limit - self.clock if self.time_limit > 0 else None

    @property
    def lap_number(self):
        return min(self.laps_completed + 1, self.laps_to_finish) if self.laps_to_finish else self.laps_completed + 1


def _line_distance(gate, point):
    (x1, z1), (x2, z2) = gate
    length = math.hypot(x2 - x1, z2 - z1)
    if not length:
        return math.hypot(point[0] - x1, point[1] - z1)
    return abs((x2 - x1) * (point[1] - z1) - (z2 - z1) * (point[0] - x1)) / length


def gate_share(gate, next_gate, point):
    """How far `point` is from one checkpoint line to the next, 0 to 1, by its distance
    to each line."""
    before, after = _line_distance(gate, point), _line_distance(next_gate, point)
    return before / (before + after) if before + after else 0.0


def _passed(times, k):
    return times[k] != NO_CHECKPOINT and times[k] >= times[0]


class LapReader:
    """Reads the race. What does not change during a race (field positions, the local
    player, finished laps, the track's checkpoint lines) is kept between reads, so a read
    asks the game only for what moves: about twenty small reads."""

    def __init__(self, il2cpp):
        self.il = il2cpp
        self.services_class = il2cpp.find_class('TS', 'Services')
        self._state = None  # the TS.EventState the caches below belong to
        self._offsets = {}  # (role, field) -> offset
        self._player = None
        self._laps = {}  # finished lap object -> its checkpoint times
        self._gates = None  # checkpoint lines, ((x1, z1), (x2, z2)) each

    def event_state(self):
        services = self.il.static_ref(self.services_class, 'sm_instance')
        return self.il.ref(services, 'm_activeServer', 'm_eventListener', 'm_eventState')

    def local_player(self):
        """(event state, local TS.EventPlayer); raises NotFound outside a race."""
        il, memory = self.il, self.il.memory
        state = self.event_state()
        for player in il.list_items(il.ref(state, 'players')):
            if player and memory.i32(player + il.offset(player, 'm_localHumanIndex')) >= 0:
                return state, player
        raise NotFound('no local player')

    def _offset(self, role, obj, name):
        key = (role, name)
        if key not in self._offsets:
            self._offsets[key] = self.il.offset(obj, name)
        return self._offsets[key]

    def _ref(self, role, obj, name):
        value = self.il.memory.u64(obj + self._offset(role, obj, name))
        if not value:
            raise NotFound(f'{name} is null')
        return value

    def _u32_list(self, lst):
        header = self.il.memory.read(lst + LIST_ITEMS, 12)
        array, size = struct.unpack('<Qi', header)
        if not 0 <= size <= 4096:
            raise NotFound('implausible list size')
        if not size:
            return ()
        return struct.unpack(f'<{size}I', self.il.memory.read(array + ARRAY_DATA, 4 * size))

    def read(self):
        il, memory = self.il, self.il.memory
        state = self.event_state()
        if state != self._state:
            # A new event (or the first read): start the caches afresh.
            self._state, self._offsets, self._laps, self._gates = state, {}, {}, None
            self._player = self.local_player()[1]
        player = self._player
        times = state + self._offset('state', state, 'times')
        span = struct.unpack('<5i', memory.read(times + TIMES_NOW, TIMES_LIMIT - TIMES_NOW + 4))
        clock, time_limit = span[0], span[-1]  # one read for the clock and the time limit
        stats = self._ref('player', player, 'm_stats')
        laps_completed = memory.u16(stats + self._offset('stats', stats, 'm_lapsCompleted'))
        laps_to_finish = memory.u16(stats + self._offset('stats', stats, 'm_lapsToFinish'))
        try:
            finished = bool(memory.u8(stats + self._offset('stats', stats, 'm_finished')))
        except NotFound:
            finished = False
        laps = il.list_items(self._ref('stats', stats, 'm_checkpointTimesForLaps'))
        checkpoints = []
        for index, lap in enumerate(laps):
            if not lap:
                continue
            passed = self._laps.get(lap)
            if passed is None:
                passed = self._u32_list(self._ref('lap', lap, 'm_times'))
                if index < laps_completed:
                    self._laps[lap] = passed  # a finished lap does not change any more
            if passed:
                checkpoints.append(passed)
        position, gates = self._position_and_gates(player)
        return LapState(
            clock=clock,
            time_limit=time_limit,
            laps_completed=laps_completed,
            laps_to_finish=laps_to_finish,
            lap_starts=[passed[0] for passed in checkpoints],
            finished=finished,
            checkpoints=tuple(checkpoints),
            position=position,
            gates=gates,
        )

    def _read_gates(self, player):
        """The track's checkpoint lines, in a few batched reads (120 checkpoints, each
        with its properties object)."""
        il, memory = self.il, self.il.memory
        track = il.ref(self._ref('player', player, 'm_statsUpdater'), 'm_checkpoints')
        checkpoints = [c for c in il.list_items(il.ref(track, 'm_checkpoints')) if c]
        if not checkpoints:
            return ()
        to_properties = self._offset('checkpoint', checkpoints[0], 'm_properties')
        properties = []
        for data in memory.read_many([c + to_properties for c in checkpoints], 8):
            if data is None:
                raise NotFound('checkpoint not readable')
            properties.append(struct.unpack('<Q', data)[0])
        one = self._offset('properties', properties[0], 'position1')
        two = self._offset('properties', properties[0], 'position2')
        gates = []
        ends = zip(memory.read_many([p + one for p in properties], 12), memory.read_many([p + two for p in properties], 12))
        for first, second in ends:
            if first is None or second is None:
                raise NotFound('checkpoint line not readable')
            x1, _, z1 = struct.unpack('<3f', first)
            x2, _, z2 = struct.unpack('<3f', second)
            gates.append(((x1, z1), (x2, z2)))
        return tuple(gates)

    def _position_and_gates(self, player):
        """The car's (x, z) and the track's checkpoint lines, for the live delta; (None,
        ()) where the game does not have them."""
        il, memory = self.il, self.il.memory
        try:
            vehicle = self._ref('player', player, 'm_vehicle')
            x, _y, z = struct.unpack('<3f', memory.read(vehicle + self._offset('vehicle', vehicle, 'm_statsNewPosition'), 12))
            if self._gates is None:
                self._gates = self._read_gates(player)
            return (x, z), self._gates
        except NotFound:
            return None, ()


def format_time(units):
    """'1:24.095' for a time in 0.1 ms steps; '-' for None."""
    if units is None:
        return '-'
    sign, units = ('-' if units < 0 else ''), abs(units)
    minutes, rest = divmod(units, 60 * UNITS_PER_SECOND)
    return f'{sign}{minutes}:{rest / UNITS_PER_SECOND:06.3f}'


def format_delta(units):
    """'-0.412' ahead, '+1.230' behind."""
    return f'{"-" if units < 0 else "+"}{abs(units) / UNITS_PER_SECOND:.3f}'


def format_tenths(units):
    """'0:36.5' for a running time: tenths, cut off rather than rounded, so it never
    shows a value the clock has not reached yet."""
    if units is None:
        return '-:--.-'
    tenths = max(0, units) // 1000
    minutes, tenths = divmod(tenths, 600)
    return f'{minutes}:{tenths // 10:02d}.{tenths % 10}'


@dataclass(frozen=True)
class Snapshot:
    """The latest result of the live reader."""

    status: str = WAITING_FOR_GAME
    state: LapState | None = None
    running: bool = False  # the race clock moved since the read before
    read_at: float = 0.0  # time.monotonic() of the read
    detail: str = ''  # why it is waiting, for the log


def current_lap_now(snapshot, now):
    """The current lap at monotonic time `now`: the last read value, run on by the time
    since the read while the race clock is moving (reads come a few times a second, the
    HUD draws ten)."""
    current = snapshot.state.current_lap
    if current is None or not snapshot.running:
        return current
    ahead = min(max(now - snapshot.read_at, 0.0), MAX_EXTRAPOLATION)
    return current + int(ahead * UNITS_PER_SECOND)


def race_sections(snapshot, now):
    """{section name: rows} for a live-reader snapshot (see core.hud.RACE_SECTIONS); a
    section with nothing to show has no rows."""
    if snapshot.status == WAITING_FOR_GAME:
        return {'lap': [Row('Waiting for TSU (launch option)', 'title')]}
    if snapshot.status != RACING or snapshot.state is None:
        return {'lap': [Row('Waiting for a race...', 'title')]}
    state = snapshot.state
    if state.finished or state.laps_to_finish and state.laps_completed >= state.laps_to_finish:
        return {
            'lap': [Row(f'Finished - {state.laps_completed} laps', 'title')],
            'current': [Row(format_time(state.best_lap), 'big', 'accent')],
            'times': [Row(f'Best lap   Last {format_time(state.last_lap)}', 'medium')],
        }
    title = f'Lap {state.lap_number}/{state.laps_to_finish}' if state.laps_to_finish else f'Lap {state.lap_number}'
    left = state.time_left
    if left is not None:
        title += f'  -  {clock(math.ceil(left / UNITS_PER_SECOND))} left' if left > 0 else '  -  time is up'
    delta = state.delta_to_best
    if delta is None:
        delta_row = Row('vs best  -', 'medium')
    else:
        delta_row = Row(f'{format_delta(delta)} vs best', 'medium', 'ahead' if delta < 0 else 'behind')
    return {
        'lap': [Row(title, 'title')],
        'current': [Row(format_tenths(current_lap_now(snapshot, now)), 'big', 'accent')],
        'delta': [delta_row],
        'times': [Row(f'Last {format_time(state.last_lap)}   Best {format_time(state.best_lap)}', 'medium')],
    }


def race_rows(snapshot, now):
    """All sections' rows in one list, top to bottom (for the terminal and tests)."""
    sections = race_sections(snapshot, now)
    return [row for name in ('lap', 'current', 'delta', 'times') for row in sections.get(name, [])]
