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
from dataclasses import dataclass

from turbohud.core.hud import Row, clock
from turbohud.core.il2cpp import NotFound

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
        """This lap against the best lap at the last checkpoint both passed: negative is
        ahead, positive behind; None on the first lap or before the first checkpoint."""
        best_index = self.best_lap_index
        if best_index is None or len(self.checkpoints) < 2 or best_index >= len(self.checkpoints) - 1:
            return None
        current, best = self.checkpoints[-1], self.checkpoints[best_index]
        for k in range(min(len(current), len(best)) - 1, 0, -1):
            if _passed(current, k) and _passed(best, k):
                elapsed = current[k] - current[0]
                return elapsed - (best[k] - best[0]) if elapsed > 0 else None
        return None

    @property
    def time_left(self):
        return self.time_limit - self.clock if self.time_limit > 0 else None

    @property
    def lap_number(self):
        return min(self.laps_completed + 1, self.laps_to_finish) if self.laps_to_finish else self.laps_completed + 1


def _passed(times, k):
    return times[k] != NO_CHECKPOINT and times[k] >= times[0]


class LapReader:
    def __init__(self, il2cpp):
        self.il = il2cpp
        self.services_class = il2cpp.find_class('TS', 'Services')

    def local_player(self):
        """(event state, local TS.EventPlayer); raises NotFound outside a race."""
        il, memory = self.il, self.il.memory
        services = il.static_ref(self.services_class, 'sm_instance')
        state = il.ref(services, 'm_activeServer', 'm_eventListener', 'm_eventState')
        for player in il.list_items(il.ref(state, 'players')):
            if player and memory.i32(player + il.offset(player, 'm_localHumanIndex')) >= 0:
                return state, player
        raise NotFound('no local player')

    def read(self):
        il, memory = self.il, self.il.memory
        state, player = self.local_player()
        times = state + il.offset(state, 'times')
        stats = il.ref(player, 'm_stats')
        checkpoints = []
        for lap in il.list_items(il.ref(stats, 'm_checkpointTimesForLaps')):
            if lap:
                passed = il.u32_list(il.ref(lap, 'm_times'))
                if passed:
                    checkpoints.append(passed)
        try:
            finished = bool(memory.u8(stats + il.offset(stats, 'm_finished')))
        except NotFound:
            finished = False
        return LapState(
            clock=memory.i32(times + TIMES_NOW),
            time_limit=memory.i32(times + TIMES_LIMIT),
            laps_completed=memory.u16(stats + il.offset(stats, 'm_lapsCompleted')),
            laps_to_finish=memory.u16(stats + il.offset(stats, 'm_lapsToFinish')),
            lap_starts=[passed[0] for passed in checkpoints],
            finished=finished,
            checkpoints=tuple(checkpoints),
        )


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


def race_rows(snapshot, now):
    """What the HUD shows for a live-reader snapshot."""
    if snapshot.status == WAITING_FOR_GAME:
        return [Row('TurboHUD', 'title'), Row('Start TSU from Steam with the launch option.', 'small')]
    if snapshot.status != RACING or snapshot.state is None:
        return [Row('TurboHUD', 'title'), Row('Waiting for a race...', 'small')]
    state = snapshot.state
    times = f'Last {format_time(state.last_lap)}   Best {format_time(state.best_lap)}'
    if state.finished or state.laps_to_finish and state.laps_completed >= state.laps_to_finish:
        return [
            Row(f'Finished - {state.laps_completed} laps', 'title'),
            Row(format_time(state.best_lap), 'big', 'accent'),
            Row(f'Best lap   Last {format_time(state.last_lap)}', 'medium'),
        ]
    title = f'Lap {state.lap_number}/{state.laps_to_finish}' if state.laps_to_finish else f'Lap {state.lap_number}'
    left = state.time_left
    if left is not None:
        title += f'  -  {clock(math.ceil(left / UNITS_PER_SECOND))} left' if left > 0 else '  -  time is up'
    delta = state.delta_to_best
    if delta is None:
        delta_row = Row('vs best  -', 'medium')
    else:
        delta_row = Row(f'{format_delta(delta)} vs best', 'medium', 'ahead' if delta < 0 else 'behind')
    return [
        Row(title, 'title'),
        Row(format_tenths(current_lap_now(snapshot, now)), 'big', 'accent'),
        delta_row,
        Row(times, 'medium'),
    ]
