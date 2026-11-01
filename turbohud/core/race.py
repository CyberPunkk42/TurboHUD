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

import dataclasses
import math
import struct
import time
from dataclasses import dataclass

from turbohud.core.flags import flag_code, flag_text
from turbohud.core.hud import Row, clock, local_time_rows
from turbohud.core.il2cpp import ARRAY_DATA, LIST_ITEMS, SIMPLE_TYPES, NotFound, ReadError

UNITS_PER_SECOND = 10_000
# EventState.times: ticks, time, ..., time limit (int32 each).
TIMES_TICKS, TIMES_NOW, TIMES_LIMIT = 0, 4, 20
# How far the HUD runs the current lap on by itself between two reads.
MAX_EXTRAPOLATION = 1.0  # seconds

# What the live reader is doing, for Snapshot.status.
EVEN = 5  # under half a millisecond: shown as 0.000, neither ahead nor behind
NO_CHECKPOINT = 0xFFFF_FFFF  # how a missed checkpoint may be marked

WAITING_FOR_GAME = 'waiting for game'
WAITING_FOR_RACE = 'waiting for race'
STARTING = 'race starting'  # a session is on and its race is being set up (loading, grid)
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
    car: 'CarState | None' = None  # fuel, tires and speed, where the game has them
    players: tuple = ()  # every player in the race (PlayerState), the local one included

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

    def stretch(self):
        """Where the car is in the current lap, for live comparisons with the best lap:
        (first line of the run just passed, line passed last, next line with a time of
        its own, last line of that run, share of the way from one to the next), or None
        without position, track or a best lap. The next line is len(best) for the finish.
        """
        best_index = self.best_lap_index
        if best_index is None or len(self.checkpoints) < 2 or best_index >= len(self.checkpoints) - 1:
            return None
        current, best = self.checkpoints[-1], self.checkpoints[best_index]
        k = len(current) - 1  # the last line passed in this lap
        if self.position is None or len(self.gates) != len(best) or k >= len(best):
            return None
        # Some lines record the same time as the one before (lines 1 and 119 on the tracks
        # seen): TSU counts them passed together, before the car is really there. The
        # stretch then starts at the first line of such a run.
        start = k
        while start > 0 and current[start] == current[start - 1]:
            start -= 1
        # The next line with a time of its own: a line at the same spot as the one just
        # passed (lines 7, 13, 24 ... on the tracks seen) gets the same time but is only
        # written when the car reaches the line after it.
        following = k + 1
        while following < len(best) and best[following] == best[k]:
            following += 1
        end = following
        while end + 1 < len(best) and best[end + 1] == best[following]:
            end += 1
        # A checkpoint can be several line pieces with the same time (a wide track split
        # in two, or one line twice): the nearest piece counts.
        behind = [self.gates[i] for i in range(start, k + 1)]
        ahead = [self.gates[i % len(self.gates)] for i in range(following, end + 1)]
        return start, k, following, end, gate_share(behind, ahead, self.position)

    def _live_delta(self, current, best, best_index):
        place = self.stretch()
        if place is None:
            return None
        start, _k, following_line, _end, share = place
        if not (_passed(current, start) and _passed(best, start)):
            return None
        if following_line == len(best):
            following = self.lap_starts[best_index + 1]  # the next line is the finish
        elif _passed(best, following_line):
            following = best[following_line]
        else:
            return None
        best_here = best[start] + share * (following - best[start]) - best[0]
        elapsed = self.clock - current[0]
        return round(elapsed - best_here) if elapsed > 0 else None

    def live_fuel_trend(self, marks, starts, laps=None):
        """Like fuel_trend, but the recent laps' use is taken at the car's place between
        two checkpoints (as for the live delta), not at the last checkpoint: otherwise
        this lap's use, which keeps growing, is held against a fixed number until the
        next line, and the balance swings at every checkpoint. None where the place is
        not known (then fuel_trend, by checkpoint, serves)."""
        car, place = self.car, self.stretch()
        if car is None or place is None:
            return None
        laps = laps or PER_LAP_LAPS
        start, k, following, end, share = place
        lap = len(self.checkpoints) - 1
        lap_length = len(self.checkpoints[self.best_lap_index])
        if k < MIN_TREND_CHECKPOINT or lap not in starts or car.fuel_used < starts[lap]:
            return None
        references = []
        for earlier in range(lap - 1, -1, -1):
            if len(references) == laps or earlier not in starts:
                break
            next_start = starts.get(earlier + 1)
            if next_start is None or next_start < starts[earlier]:
                break  # refuelled since then
            mark = marks.get(earlier, {})
            # Lines passed together have one mark, under whichever of them was seen.
            before = next((mark[i] for i in range(start, k + 1) if i in mark), None)
            if following == lap_length:
                after = next_start  # the next line is the finish
            else:
                after = next((mark[i] for i in range(following, end + 1) if i in mark), None)
            if before is None or after is None or not starts[earlier] <= before <= after:
                continue
            references.append(before + share * (after - before) - starts[earlier])
        if not references:
            return None
        return (car.fuel_used - starts[lap]) - sum(references) / len(references)

    @property
    def laps_to_go(self):
        """Laps still to drive, the current one's rest included: by the lap limit, and
        by the time limit at the recent lap times (the lap in which time runs out is
        finished); the smaller. None without a limit or a lap time to go by."""
        times = self.lap_times[-PER_LAP_LAPS:]
        if not times or self.current_lap is None:
            return None
        lap_time = sum(times) / len(times)
        progress = min(max(self.current_lap / lap_time, 0.0), 0.99)
        options = []
        if self.laps_to_finish:
            options.append(self.laps_to_finish - self.laps_completed - progress)
        if self.time_limit > 0:
            left = max(self.time_limit - self.clock, 0)
            options.append(math.ceil(progress + left / lap_time) - progress)
        return max(min(options), 0.0) if options else None

    @property
    def time_left(self):
        return self.time_limit - self.clock if self.time_limit > 0 else None

    @property
    def lap_number(self):
        return min(self.laps_completed + 1, self.laps_to_finish) if self.laps_to_finish else self.laps_completed + 1


def _segment_distance(gate, point):
    """How far `point` is from a checkpoint line piece (not the endless line through it)."""
    (x1, z1), (x2, z2) = gate
    dx, dz = x2 - x1, z2 - z1
    length = dx * dx + dz * dz
    along = 0.0 if not length else min(max(((point[0] - x1) * dx + (point[1] - z1) * dz) / length, 0.0), 1.0)
    return math.hypot(point[0] - (x1 + along * dx), point[1] - (z1 + along * dz))


def gate_share(behind, ahead, point):
    """How far `point` is from one checkpoint to the next, 0 to 1, by its distance to
    each: the line pieces just passed (`behind`) and those to come (`ahead`), a gate or
    a list of them, the nearest piece counting."""
    if behind and isinstance(behind[0][0], (int, float)):
        behind = [behind]
    if ahead and isinstance(ahead[0][0], (int, float)):
        ahead = [ahead]
    before = min(_segment_distance(gate, point) for gate in behind)
    after = min(_segment_distance(gate, point) for gate in ahead)
    return before / (before + after) if before + after else 0.0


def _passed(times, k):
    return times[k] != NO_CHECKPOINT and times[k] >= times[0]


MAX_TIRE_WEAR = 5_760_000  # TS.TireWearSettings.MaxTireWear (a constant): worn out
KMH_PER_MPH = 1.609344
SPEED_TO_KMH = 3.6  # m_forwardSpeed is taken as metres per second (not yet compared in game)
PER_LAP_LAPS = 3  # laps averaged for fuel and tire use per lap
LIFT_MIN_KMH = 5  # slower than this is standing, not lifting
EVEN_FUEL = 0.01  # a fuel trend under 1 % of a lap's use is neither saving nor not
MIN_TREND_CHECKPOINT = 2  # too early in a lap to compare before this checkpoint


def fuel_trend(marks, starts, lap, checkpoint, used, laps=PER_LAP_LAPS):
    """This lap's fuel use so far minus the average of the last `laps` laps' use up to
    the same checkpoint. `marks` is {lap: {checkpoint: fuel used when it was passed}},
    `starts` {lap: fuel used when it began}. None too early in a lap, without earlier
    laps to compare, or across a pit stop (fuel used went down)."""
    if checkpoint < MIN_TREND_CHECKPOINT or lap not in starts or used < starts[lap]:
        return None
    references = []
    for earlier in range(lap - 1, -1, -1):
        if len(references) == laps or earlier not in starts:
            break
        following = starts.get(earlier + 1)
        if following is None or following < starts[earlier]:
            break  # refuelled since then
        mark = marks.get(earlier, {})
        passed = mark.get(checkpoint, mark.get(checkpoint - 1))
        if passed is None or passed < starts[earlier]:
            continue
        references.append(passed - starts[earlier])
    if not references:
        return None
    return (used - starts[lap]) - sum(references) / len(references)


@dataclass(frozen=True)
class CarState:
    """The local car: what it has used up and how fast it goes."""

    fuel_on: bool
    fuel_used: int  # TS.VehicleState.fuelConsumption: 150 a second at full throttle
    fuel_tank: int  # a full tank in the same units (the event's fuel settings)
    tires_on: bool
    tire_wear: int  # TS.VehicleState.tireWear, worn out at MAX_TIRE_WEAR
    speed: float  # forward speed, game units (metres) a second
    fuel_per_lap: float | None = None  # average of the last laps, same units
    wear_per_lap: float | None = None
    fuel_trend: float | None = None  # this lap's use so far minus the recent laps' at the same checkpoint
    throttle: float | None = None  # 0 to 1, None where unknown
    brake: float | None = None

    @property
    def saving(self):
        """True when this lap uses less fuel than the recent ones so far, False when more,
        None when about the same or not known yet."""
        if self.fuel_trend is None or not self.fuel_per_lap or abs(self.fuel_trend) < EVEN_FUEL * self.fuel_per_lap:
            return None
        return self.fuel_trend < 0

    @property
    def fuel_left(self):
        """0 to 1, or None without fuel."""
        if not self.fuel_on or self.fuel_tank <= 0:
            return None
        return min(max(1 - self.fuel_used / self.fuel_tank, 0.0), 1.0)

    @property
    def tires_left(self):
        if not self.tires_on:
            return None
        return min(max(1 - self.tire_wear / MAX_TIRE_WEAR, 0.0), 1.0)

    @property
    def fuel_laps(self):
        """How many laps the fuel lasts at the recent use, or None."""
        if self.fuel_left is None or not self.fuel_per_lap:
            return None
        return (self.fuel_tank - self.fuel_used) / self.fuel_per_lap

    @property
    def tire_laps(self):
        if self.tires_left is None or not self.wear_per_lap:
            return None
        return (MAX_TIRE_WEAR - self.tire_wear) / self.wear_per_lap

    @property
    def kmh(self):
        return abs(self.speed) * SPEED_TO_KMH

    @property
    def lifting(self):
        """Rolling on without throttle or brake (coasting); False when not known."""
        if self.throttle is None or self.brake is None:
            return False
        return self.throttle == 0 and self.brake == 0 and self.kmh >= LIFT_MIN_KMH


def per_lap(history, laps=PER_LAP_LAPS):
    """Average use per lap from `history`, the used amounts at the start of each lap
    (oldest first), over the last `laps` laps; None before a whole lap. A drop (a pit
    stop that refilled or changed tires) starts the average afresh."""
    start = 0
    for index in range(1, len(history)):
        if history[index] < history[index - 1]:
            start = index
    recent = history[start:][-(laps + 1):]
    if len(recent) < 2:
        return None
    return (recent[-1] - recent[0]) / (len(recent) - 1)


STRING_LENGTH, STRING_CHARS = 0x10, 0x14  # System.String: length, then UTF-16 text
MAX_NAME = 64


@dataclass(frozen=True)
class PlayerState:
    """One player in the race, for the player list."""

    name: str
    flag: int  # TS.Flag value (turbohud.core.flags), 0 for none
    laps_completed: int
    checkpoints: tuple  # per started lap, when each checkpoint was passed, 0.1 ms
    finished: bool = False
    in_pit: bool = False
    local: bool = False

    @property
    def passed(self):
        """Every checkpoint time of the race in one row (laps one after another)."""
        return tuple(time for lap in self.checkpoints for time in lap)

    @property
    def finish_time(self):
        """When the last lap ended (the next lap's start), for a finished player."""
        if not self.finished or len(self.checkpoints) <= self.laps_completed:
            return None
        return self.checkpoints[self.laps_completed][0]


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
        self._fuel_history = {}  # lap index -> fuel used when it started
        self._wear_history = {}  # lap index -> tire wear when it started
        self._fuel_marks = {}  # lap index -> {checkpoint: fuel used when passed}
        self._types = {}  # (role, field) -> (offset, type code)

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
            self._fuel_history, self._wear_history, self._fuel_marks, self._types = {}, {}, {}, {}
            self._player = self.local_player()[1]
        player = self._player
        state_object = state
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
        car = self._car(player, len(checkpoints) - 1, len(checkpoints[-1]) - 1 if checkpoints else -1)
        state = LapState(
            clock=clock,
            time_limit=time_limit,
            laps_completed=laps_completed,
            laps_to_finish=laps_to_finish,
            lap_starts=[passed[0] for passed in checkpoints],
            finished=finished,
            checkpoints=tuple(checkpoints),
            position=position,
            gates=gates,
            car=car,
        )
        state = dataclasses.replace(state, players=self._players(state_object))
        live = state.live_fuel_trend(self._fuel_marks, self._fuel_history)
        if live is not None:
            state = dataclasses.replace(state, car=dataclasses.replace(car, fuel_trend=live))
        return state

    def _car(self, player, lap, checkpoint):
        """Fuel, tires and speed of the local car, or None where the game lacks them."""
        memory = self.il.memory
        try:
            vehicle = self._ref('player', player, 'm_vehicle')
            state = self._ref('vehicle', vehicle, 'm_state')
            updater = self._ref('vehicle', vehicle, 'm_stateUpdater')
            fuel_used = memory.i32(state + self._offset('vstate', state, 'fuelConsumption'))
            tire_wear = memory.i32(state + self._offset('vstate', state, 'tireWear'))
            fuel_on = bool(memory.u8(updater + self._offset('updater', updater, 'm_fuelEnabled')))
            tires_on = bool(memory.u8(updater + self._offset('updater', updater, 'm_tireWearEnabled')))
            speed = memory.f32(updater + self._offset('updater', updater, 'm_forwardSpeed'))
            settings = self._ref('updater', updater, 'm_fuelSettings')
            tank = memory.i32(settings + self._offset('fuel', settings, 'maxFuelConsumptionInEvent'))
        except NotFound:
            return None
        throttle, brake = self._pedals(updater)
        trend = None
        if lap >= 0:
            self._fuel_history.setdefault(lap, fuel_used)
            self._wear_history.setdefault(lap, tire_wear)
            self._fuel_marks.setdefault(lap, {}).setdefault(checkpoint, fuel_used)
            trend = fuel_trend(self._fuel_marks, self._fuel_history, lap, checkpoint, fuel_used)
        fuel_starts = [self._fuel_history[i] for i in sorted(self._fuel_history)]
        wear_starts = [self._wear_history[i] for i in sorted(self._wear_history)]
        return CarState(
            fuel_on=fuel_on, fuel_used=fuel_used, fuel_tank=tank, tires_on=tires_on, tire_wear=tire_wear,
            speed=speed, fuel_per_lap=per_lap(fuel_starts), wear_per_lap=per_lap(wear_starts), fuel_trend=trend,
            throttle=throttle, brake=brake,
        )

    def _string(self, address):
        if not address:
            return ''
        length = self.il.memory.i32(address + STRING_LENGTH)
        if not 0 <= length <= MAX_NAME:
            return ''
        return self.il.memory.read(address + STRING_CHARS, 2 * length).decode('utf-16-le', 'replace')

    def _players(self, state):
        """Every player of the race (PlayerState); empty where the game has no list."""
        il, memory = self.il, self.il.memory
        try:
            players = il.list_items(self._ref('state', state, 'players'))
        except (NotFound, OSError):
            return ()
        found = []
        for player in players:
            if not player:
                continue
            try:
                found.append(self._player_state(player))
            except (NotFound, OSError):
                continue  # one unreadable player must not hide the others
        return tuple(found)

    def _player_state(self, player):
        il, memory = self.il, self.il.memory
        local = memory.i32(player + self._offset('player', player, 'm_localHumanIndex')) >= 0
        name, flag = '', 0
        try:
            profile = il.ref(self._ref('player', player, 'm_playerInfo'), 'm_profile')
            name = self._string(memory.u64(profile + self._offset('profile', profile, 'm_name')))
            flag = memory.i32(profile + self._offset('profile', profile, 'flag'))
        except NotFound:
            pass
        stats = self._ref('player', player, 'm_stats')
        laps_completed = memory.u16(stats + self._offset('stats', stats, 'm_lapsCompleted'))
        try:
            finished = bool(memory.u8(stats + self._offset('stats', stats, 'm_finished')))
        except NotFound:
            finished = False
        checkpoints = []
        for index, lap in enumerate(il.list_items(self._ref('stats', stats, 'm_checkpointTimesForLaps'))):
            if not lap:
                continue
            passed = self._laps.get(lap)
            if passed is None:
                passed = self._u32_list(self._ref('lap', lap, 'm_times'))
                if index < laps_completed:
                    self._laps[lap] = passed
            if passed:
                checkpoints.append(passed)
        in_pit = False
        try:
            updater = self._ref('vehicle', self._ref('player', player, 'm_vehicle'), 'm_stateUpdater')
            in_pit = bool(memory.u8(updater + self._offset('updater', updater, 'inPit')))
        except (NotFound, ReadError):
            pass
        return PlayerState(name, flag, laps_completed, tuple(checkpoints), finished, in_pit, local)

    def _number(self, role, obj, name):
        """A simple field read by the type the game gives it (int, float, ...)."""
        key = (role, name)
        if key not in self._types:
            found = {n: (offset, code) for n, offset, static, code in self.il.field_list(self.il.memory.u64(obj)) if not static}
            if name not in found or found[name][1] not in SIMPLE_TYPES:
                raise NotFound(f'no simple field {name}')
            self._types[key] = found[name]
        offset, code = self._types[key]
        fmt = SIMPLE_TYPES[code][1]
        return struct.unpack(fmt, self.il.memory.read(obj + offset, struct.calcsize(fmt)))[0]

    def _pedals(self, updater):
        """(throttle, brake), 0 to 1, from TS.CarControls (CarStateUpdater.m_controls):
        `gas` and `brake` where they are fractions, else the whole thirds TSU also keeps."""
        try:
            controls = self._ref('updater', updater, 'm_controls')
            values = []
            for name in ('gas', 'brake'):
                value = self._number('controls', controls, name)
                if isinstance(value, float):
                    values.append(min(max(value, 0.0), 1.0))
                else:
                    values.append(min(max(self._number('controls', controls, f'{name}InThirds') / 3, 0.0), 1.0))
            return tuple(values)
        except (NotFound, ReadError):
            return None, None  # optional: the rest of the race reads on without it

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
    """'-0.412' ahead, '+1.230' behind, '0.000' when too small to show."""
    if abs(units) < EVEN:
        return '0.000'
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
    moved_at: float = 0.0  # time.monotonic() when the race clock last moved


def current_lap_now(snapshot, now):
    """The current lap at monotonic time `now`: the last read value, run on by the time
    since the read while the race clock is moving (reads come a few times a second, the
    HUD draws ten)."""
    current = snapshot.state.current_lap
    if current is None or not snapshot.running:
        return current
    ahead = min(max(now - snapshot.read_at, 0.0), MAX_EXTRAPOLATION)
    return current + int(ahead * UNITS_PER_SECOND)


def clock_now(snapshot, now):
    """The race clock at monotonic time `now`, run on like current_lap_now."""
    clock = snapshot.state.clock
    if not snapshot.running:
        return clock
    return clock + int(min(max(now - snapshot.read_at, 0.0), MAX_EXTRAPOLATION) * UNITS_PER_SECOND)


STILL_SECONDS = 2.0  # a race clock standing this long: not on the grid (lobby, pause)


def on_grid(snapshot, now=None):
    """Whether the cars stand on the grid or race: the race exists and its clock runs
    (it starts when the grid is set, before the lights). Not in the menus, while a race
    loads, or in the lobby, where a finished race may linger with its clock standing.
    `now` (time.monotonic()) checks that the clock moved lately; without it, only that
    it has started."""
    if snapshot.status != RACING or snapshot.state is None or snapshot.state.clock <= 0:
        return False
    return now is None or now - snapshot.moved_at < STILL_SECONDS


def status_text(snapshot):
    """What TurboHUD is waiting for, for the tray icon's tooltip."""
    if snapshot.status == WAITING_FOR_GAME:
        return 'waiting for TSU (start it with the launch option)'
    if on_grid(snapshot, time.monotonic()):
        return 'racing'
    if snapshot.status in (STARTING, RACING):
        return 'race being set up'
    return 'waiting for a race'


def race_sections(snapshot, now, speed_unit='kmh', standings=None):
    """{section name: rows} for a live-reader snapshot (see core.hud.RACE_SECTIONS); a
    section with nothing to show has no rows. Nothing before the grid: in the menus, the
    lobby and while a race loads the HUD keeps out of the way (status_text says why).
    `standings` (a Standings) holds the player list's order steady while cars pass."""
    if not on_grid(snapshot, now):
        return {}
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
        color = 'text' if abs(delta) < EVEN else 'ahead' if delta < 0 else 'behind'
        delta_row = Row(f'{format_delta(delta)} vs best', 'medium', color)
    sections = {
        'lap': [Row(title, 'title')],
        'current': [Row(format_tenths(current_lap_now(snapshot, now)), 'big', 'accent')],
        'delta': [delta_row],
        'times': [Row(f'Last {format_time(state.last_lap)}   Best {format_time(state.best_lap)}', 'medium')],
    }
    sections.update(car_sections(state.car, state.laps_to_go, speed_unit))
    if state.players:
        order = standings.order(state.players, now) if standings is not None else None
        sections['players'] = players_rows(state.players, order)
        opacity = blue_flag_opacity(blue_flag(state.players, clock_now(snapshot, now)))
        if opacity is not None:
            sections['blue'] = opacity
    return sections


def _laps_text(laps):
    return f'  ~{laps:.1f} laps' if laps is not None else ''


def fuel_margin(car, laps_to_go):
    """Laps of fuel beyond what the rest of the race needs at the recent use: plus is
    to spare, minus is short (save or stop for fuel). None when not known yet."""
    if car is None or car.fuel_laps is None or laps_to_go is None:
        return None
    return car.fuel_laps - laps_to_go


def _balance_text(car):
    """'  +0.18%': fuel saved this lap so far against the recent laps, in % of the tank
    (minus: burnt more); empty without a comparison."""
    if car.fuel_trend is None or car.fuel_tank <= 0:
        return ''
    balance = -car.fuel_trend / car.fuel_tank * 100
    return f'  {"+" if balance >= 0 else "-"}{abs(balance):.2f}%'


def car_sections(car, laps_to_go=None, speed_unit='kmh'):
    """{section: rows} for fuel, tires and speed; empty where the event has none.
    `laps_to_go` (LapState.laps_to_go) gives the fuel margin to the finish."""
    if car is None:
        return {}
    speed_color = 'lift' if car.lifting else 'text'
    speed = f'{car.kmh / KMH_PER_MPH:.0f} mph' if speed_unit == 'mph' else f'{car.kmh:.0f} km/h'
    sections = {'speed': [Row(speed, 'medium', speed_color)], 'pedals': (car.throttle, car.brake)}
    if car.fuel_left is not None:
        color = {True: 'ahead', False: 'behind', None: 'text'}[car.saving]
        tail = _laps_text(car.fuel_laps) + _balance_text(car)
        sections['fuel'] = [Row(f'Fuel {car.fuel_left * 100:.1f}%', 'medium', tail=tail, tail_color=color)]
    if car.fuel_left is not None:
        margin = fuel_margin(car, laps_to_go)
        if margin is None:
            sections['fuelfinish'] = [Row('Finish -', 'medium')]
        else:
            sections['fuelfinish'] = [Row(f'Finish {margin:+.1f} laps', 'medium', 'ahead' if margin >= 0 else 'behind')]
    if car.tires_left is not None:
        sections['tires'] = [Row(f'Tires {car.tires_left * 100:.0f}%{_laps_text(car.tire_laps)}', 'medium')]
    return sections


def with_local_time(sections, snapshot, now_struct):
    """`sections` plus the local time once TSU is running (its menus included); while
    TurboHUD waits for the game the clock stays away too."""
    if snapshot.status == WAITING_FOR_GAME:
        return sections
    return {**sections, 'localtime': local_time_rows(now_struct)}


MAX_PLAYER_ROWS = 8  # more players: the leader and those around the local player
MAX_NAME_SHOWN = 18


def ranked(players):
    """Players in race order: finished ones by when they finished, then the others by
    how many checkpoints they passed, and at the same checkpoint by who got there first."""
    def key(player):
        if player.finish_time is not None:
            return (0, player.finish_time, 0)
        passed = player.passed
        return (1, -len(passed), passed[-1] if passed else 0)

    return sorted(players, key=key)


def gap(player, me):
    """`player` against `me`: ('time', 0.1 ms) at the last checkpoint both passed
    (negative: they got there first, ahead), or ('laps', n) a lap or more apart (negative:
    ahead), or None before a comparison."""
    theirs, mine = player.passed, me.passed
    lap_length = len(me.checkpoints[0]) if me.checkpoints and len(me.checkpoints) > 1 else 0
    difference = len(theirs) - len(mine)
    if lap_length and abs(difference) >= lap_length:
        laps = abs(difference) // lap_length
        return ('laps', -laps if difference > 0 else laps)
    common = min(len(theirs), len(mine)) - 1
    if common < 1:
        return None
    return ('time', theirs[common] - mine[common])


def gap_text(found):
    if found is None:
        return ''
    kind, value = found
    if kind == 'laps':
        return f'{value:+d} L'
    return format_delta(value)


SWAP_HOLD = 0.3  # seconds a new order must last before the player list shows it


class Standings:
    """The player list's order, held steady: a new order shows only once it has lasted
    SWAP_HOLD. While two cars pass each other, or a checkpoint is written a moment late,
    the order can change back and forth within a few reads; then the list keeps the
    order it had and only takes the new one when it stays. A player joining or leaving
    changes the list at once. The gaps next to the names stay live all the time."""

    def __init__(self, hold=SWAP_HOLD):
        self.hold = hold
        self.shown = None  # names in the order shown
        self.pending = None  # a different order, and since when it has lasted
        self.since = 0.0

    def order(self, players, now):
        """The players in the order to show at monotonic time `now`."""
        current = ranked(players)
        names = tuple(p.name for p in current)
        if self.shown is None or sorted(names) != sorted(self.shown) or len(set(names)) != len(names):
            self.shown, self.pending = names, None
            return current
        if names == self.shown:
            self.pending = None
            return current
        if names != self.pending:
            self.pending, self.since = names, now
        if now - self.since >= self.hold:
            self.shown, self.pending = names, None
            return current
        by_name = {p.name: p for p in current}
        return [by_name[name] for name in self.shown]


def shown_players(players, max_rows=MAX_PLAYER_ROWS, order=None):
    """(position, player) for the rows: everyone, or with more than `max_rows` the
    leader and the players around the local one. `order` is the race order to use
    (Standings.order), by default the current one."""
    order = list(enumerate(ranked(players) if order is None else order, start=1))
    if len(order) <= max_rows:
        return order
    me = next((i for i, (_pos, p) in enumerate(order) if p.local), 0)
    around = max_rows - 1
    first = min(max(me - around // 2, 1), len(order) - around)
    return [order[0]] + order[first:first + around]


def players_rows(players, order=None):
    """The player list: position, flag, name, PIT, and the gap to the local player."""
    me = next((p for p in players if p.local), None)
    rows = []
    for position, player in shown_players(players, order=order):
        name = player.name or '?'
        if len(name) > MAX_NAME_SHOWN:
            name = name[: MAX_NAME_SHOWN - 1] + '…'
        found = gap(player, me) if me is not None and not player.local else None
        color = 'text' if found is None or found[1] == 0 else ('behind' if found[1] < 0 else 'ahead')
        rows.append(Row(
            f'{position}. {name}', 'small', 'accent' if player.local else 'text',
            tail='  PIT' if player.in_pit else '', tail_color='lift',
            flag=flag_code(player.flag) or flag_text(player.flag),
            right=gap_text(found), right_color=color,
        ))
    return rows


BLUE_FROM = 2.0  # seconds: a car about to lap the local player this close shows the flag
BLUE_FULL = 0.5  # seconds: this close or closer, the flag is fully visible
BLUE_FAINT = 0.2  # the flag's opacity at BLUE_FROM: faint, but visible


def blue_flag(players, now):
    """Seconds until the nearest car that is about to lap the local player reaches them
    on the track, or None when no such car is within BLUE_FROM. `now` is the race clock.

    A car is about to lap the local player when it is ahead in the race but behind on
    the track: it has passed more checkpoints, and the difference, taken round a lap, is
    more than half a lap (so it is nearer behind than ahead). Exactly whole laps ahead,
    it stands at the local player's last checkpoint and has not passed them yet. Any
    car counts, not only the leader. The gap is how much later it passed the checkpoint
    it last passed than the local player did; once the local player has passed the next
    one and it has not, the gap is at least the time since then, so the flag fades as it
    falls back. When it passes, it is a little ahead on the track and the flag goes."""
    me = next((p for p in players if p.local), None)
    if me is None or me.finished or me.in_pit:
        return None
    lap_length = next((len(p.checkpoints[0]) for p in players if len(p.checkpoints) > 1), 0)
    if lap_length < 2:
        return None  # no lap completed by anyone yet: nobody can lap anybody
    mine = me.passed
    nearest = None
    for player in players:
        if player.local or player.finished or player.in_pit:
            continue
        theirs = player.passed
        ahead = len(theirs) - len(mine)
        rest = ahead % lap_length
        if ahead <= 0 or not (rest > lap_length // 2 or rest == 0):
            continue
        same = len(theirs) - 1 - -(-ahead // lap_length) * lap_length  # my index for their last checkpoint
        if same < 0 or NO_CHECKPOINT in (theirs[-1], mine[same]):
            continue
        units = theirs[-1] - mine[same]
        if same + 1 < len(mine) and mine[same + 1] != NO_CHECKPOINT:
            units = max(units, now - mine[same + 1])
        seconds = max(units, 0) / UNITS_PER_SECOND
        if seconds <= BLUE_FROM and (nearest is None or seconds < nearest):
            nearest = seconds
    return nearest


def blue_flag_opacity(seconds):
    """How visible the blue flag is (0 to 1) for a car `seconds` behind: BLUE_FAINT at
    BLUE_FROM, rising evenly to 1 at BLUE_FULL; None (no flag) without a car."""
    if seconds is None or seconds > BLUE_FROM:
        return None
    share = min(max((BLUE_FROM - seconds) / (BLUE_FROM - BLUE_FULL), 0.0), 1.0)
    return BLUE_FAINT + (1 - BLUE_FAINT) * share


def race_rows(snapshot, now):
    """All sections' rows in one list, top to bottom (for the terminal and tests)."""
    sections = race_sections(snapshot, now)
    order = ('lap', 'current', 'delta', 'times', 'fuel', 'fuelfinish', 'tires', 'speed', 'players')
    return [row for name in order for row in sections.get(name, [])]
