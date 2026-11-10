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

import collections
import dataclasses
import functools
import itertools
import logging
import math
import struct
import sys
import time
from dataclasses import dataclass

from turbohud.core.flags import flag_code, flag_text
from turbohud.core.hud import Row, Sectors, blend, clock, local_time_rows
from turbohud.core.il2cpp import ARRAY_DATA, ARRAY_LENGTH, LIST_ITEMS, SIMPLE_TYPES, NotFound, ReadError

log = logging.getLogger(__name__)

UNITS_PER_SECOND = 10_000
# EventState.times: ticks, time, ..., time limit (int32 each).
TIMES_TICKS, TIMES_NOW, TIMES_LIMIT = 0, 4, 20
# How far the HUD runs the current lap on by itself between two reads.
MAX_EXTRAPOLATION = 1.0  # seconds

# What the live reader is doing, for Snapshot.status.
EVEN = 5  # under half a millisecond: shown as 0.000, neither ahead nor behind
DELTA_PLACES = 2  # the delta to the best lap in hundredths: a third digit changed at every read
DELTA_EVEN = 50  # under half a hundredth: shown as 0.00, neither ahead nor behind
SESSION_BEST_COLOR = '#c77dff'  # purple, as in F1: the fastest lap of anyone in the race
PERSONAL_BEST_COLOR = '#5ee07a'  # green: the driver's own best (the HUD's 'ahead' colour)
LAP_FLASH = 6 * UNITS_PER_SECOND  # how long the track map's road shows a fast lap's colour
NO_CHECKPOINT = 0xFFFF_FFFF  # how a missed checkpoint may be marked
SECTOR_SLOW_COLOR = '#c9a227'  # dark yellow: a sector slower than the driver's best
SECTORS_WITHOUT_LINES = 3  # sectors of a lap on a track without sector lines, as in F1
CHECKPOINT_SECTOR = 0  # TS.CheckpointType.Sector (Normal is 1, Minor 2), from the game's metadata

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
    sector_lines: tuple = ()  # the checkpoints the track's maker made sector lines, in order
    car: 'CarState | None' = None  # fuel, tires and speed, where the game has them
    players: tuple = ()  # every player in the race (PlayerState), the local one included
    draft: 'DraftSettings | None' = None  # the event's drafting, None where it is off
    spectating: bool = False  # the player only watches: no car, the lap counts are the leader's
    on_a_track: bool = True  # a race mode (a circuit, or A to B): False in arena modes, without a map

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
        return (
            min(self.laps_completed + 1, self.laps_to_finish)
            if self.laps_to_finish
            else self.laps_completed + 1
        )


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
TIRE_CHANGE_END = 2400  # where TS.VehicleState.tireCompoundAndChangeTicks ends a tire change
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
    health: float | None = None  # 0 to 1 (hit points of the most), None without damage
    downforce_from: float | None = None  # health under which the car loses downforce
    slowed_from: float | None = None  # health under which it is slower
    draft: float | None = None  # 0 to 1: how strong the slipstream is, of the event's most; None: no drafting
    draft_downforce_loss: float = 0.0  # 0 to 1: downforce lost to the slipstream now
    draft_last_lap: float | None = None  # 0 to 1: share of the last lap spent in a slipstream
    tire_change: float = 0.0  # 0 to 1: how far a tire change in the pits has come

    @property
    def damage_effect(self):
        """'slowed', 'downforce' or None: what the damage does to the car now."""
        if self.health is None:
            return None
        if self.slowed_from is not None and self.health < self.slowed_from:
            return 'slowed'
        if self.downforce_from is not None and self.health < self.downforce_from:
            return 'downforce'
        return None

    @property
    def saving(self):
        """True when this lap uses less fuel than the recent ones so far, False when more,
        None when about the same or not known yet."""
        if (
            self.fuel_trend is None
            or not self.fuel_per_lap
            or abs(self.fuel_trend) < EVEN_FUEL * self.fuel_per_lap
        ):
            return None
        return self.fuel_trend < 0

    @property
    def fuel_left(self):
        """0 to 1, or None without fuel."""
        if not self.fuel_on or self.fuel_tank <= 0:
            return None
        return min(max(1 - self.fuel_used / self.fuel_tank, 0.0), 1.0)

    @property
    def tire_wear_shown(self):
        """The wear to show: during a tire change it falls with the change's progress. The
        game holds tireWear until the change ends and only then sets it to 0."""
        return self.tire_wear * (1 - self.tire_change)

    @property
    def tires_left(self):
        if not self.tires_on:
            return None
        return min(max(1 - self.tire_wear_shown / MAX_TIRE_WEAR, 0.0), 1.0)

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
        return (MAX_TIRE_WEAR - self.tire_wear_shown) / self.wear_per_lap

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
    recent = history[start:][-(laps + 1) :]
    if len(recent) < 2:
        return None
    return (recent[-1] - recent[0]) / (len(recent) - 1)


# Where TSU keeps the event's type: m_eventMode in TS.EventSettings (seen 2026-11-08 in an online
# race); the others are names from its metadata, in case a version moves it.
EVENT_TYPE_FIELDS = ('m_eventMode', 'm_eventType', 'eventType', 'eventMode', 'm_gameMode', 'gameMode')
# Logged next to it: what kind of level the event runs on (a track, an arena), perhaps the better sign.
LEVEL_TYPE_FIELD = 'm_initializedLevelType'
# The event modes driven on a track; TSU's others: Battle, Collector, Hill, Soccer, Sumo, Tag.
TRACK_MODES = ('TS.RaceEventMode',)
REFERENCE_TYPES = (0x12, 0x15, 0x1C)  # class, generic instance, object: a field holding an address
CLIENT_SEARCH_EVERY = 10.0  # seconds between searches for an online race while there is none
CLIENT_SEARCH_MOST = 60.0  # the wait doubles up to this while an event holds no race to read
# For this long after a search first found nothing, the wait stays CLIENT_SEARCH_EVERY: a player
# joining a race in progress sees it set up a little later. Only then does the wait grow, for
# sessions that hold no race at all (a custom session).
CLIENT_SEARCH_QUICK_FOR = 60.0
CLIENT_SPECTATE_EVERY = 30.0  # the same while the race last watched has its clock standing
SPECTATE_STILL = 5.0  # seconds a watched race's clock may stand before it counts as over
CLIENT_LOG_EVERY = 2.0  # seconds between looks at TSU's log while it says no event runs
QUANTIZED_ZERO, QUANTIZED_SCALE = 1 << 20, 1024  # TS.QuantizedVehicleState positions
RECORDER_STALE = 10_000  # race clock (1 s) without a new recorder tick: it does not run
PIT_STOPPED_SPEED = 0.5  # game units a second: slower than this in the pits, the car stands
PIT_STOP_LEAST = 0.25  # seconds standing before the bracket shows: less is a passing hold-up
PIT_STOP_MOST = 45.0  # seconds standing: longer shows plain PIT, the driver may have retired
PIT_TIME_SHOWN = 6  # seconds the times stay next to PIT once the car has left the pits
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
    position: tuple | None = None  # the car's (x, z) on the ground plane, for the radar
    velocity: tuple | None = None  # its (x, z) velocity, game units a second
    forward: tuple | None = None  # the (x, z) way its nose points
    estimated: bool = False  # the position is worked out (DeadReckoning), not read
    draft_drag: float | None = None  # its air resistance multiplier: under 1 while it drafts
    pit_seconds: float | None = None  # seconds from pit entry to pit exit, while that is shown
    pit_stopped: float = 0.0  # of those, seconds standing still (refuelling, tires, repairs)

    @functools.cached_property
    def passed(self):
        """Every checkpoint time of the race in one row (laps one after another). Worked
        out once per read and kept: it grows by a lap's checkpoints every lap, and the
        order, gaps and blue flag ask for it many times a frame (rebuilt each time, it
        took 7 ms a frame after an hour's race)."""
        return tuple(itertools.chain.from_iterable(self.checkpoints))

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

    def __init__(self, il2cpp, clock=time.monotonic, event_running=None):
        """`event_running`: a callable saying whether TSU has an event running (True,
        False, or None for not known), so the game's memory is only searched for an
        online race while there is one (turbohud.tsu.gamelog)."""
        self.il = il2cpp
        self._event_running = event_running
        self.services_class = il2cpp.find_class('TS', 'Services')
        self._clock = clock
        self._reckoning = DeadReckoning()  # positions where the game keeps none (online client)
        self._listener = None  # the race controller (TS.EventController) of the event state
        self._draft = None  # the event's drafting settings, once read (False: none)
        self.event_type = None  # the event's (mode, level type), once read
        self._draft_time = {}  # lap index -> race time spent in a slipstream (0.1 ms)
        self._draft_clock = None  # race clock at the read before, for that time
        self._player_indices = []
        self._recorder_tick, self._recorder_moved = None, 0
        self._client_class = None  # TS.ClientEventController, once looked up
        self._controller = None  # the online race's event controller, once found
        self._spectated = None  # a controller whose race the player only watches
        self._found_at = None  # where the last race read or watched was: the next search begins there
        self._watched_clock, self._watched_at = None, 0.0  # its race clock, and since when
        self._watched_moved = False  # whether that clock has run since the race was picked
        self._searched_past = False  # a search past a picked race that never ran, done once
        self._next_search = 0.0  # when to look for it again
        self._search_wait = CLIENT_SEARCH_EVERY  # how long after a search that found nothing
        self._empty_since = None  # when the searches began to find nothing, while they do
        self._state = None  # the TS.EventState the caches below belong to
        self._offsets = {}  # (role, field) -> offset
        self._player = None
        self._laps = {}  # finished lap object -> its checkpoint times
        self._gates = None  # checkpoint lines, ((x1, z1), (x2, z2)) each
        self._sector_lines = ()  # the checkpoints of type Sector (TS.CheckpointType), read with the lines
        self._fuel_history = {}  # lap index -> fuel used when it started
        self._wear_history = {}  # lap index -> tire wear when it started
        self._fuel_marks = {}  # lap index -> {checkpoint: fuel used when passed}
        self._types = {}  # (role, field) -> (offset, type code)

    def event_state(self):
        """The race's TS.EventState. A race the game runs itself (offline, hotlap) is
        under TS.Services.m_activeServer. In an online race, also one the player hosts,
        the game is a client: the race is then in a TS.ClientEventController that no
        static field leads to, so it is found by its class (see _online_event_state)."""
        services = self.il.static_ref(self.services_class, 'sm_instance')
        try:
            self._listener = self.il.ref(services, 'm_activeServer', 'm_eventListener')
            return self.il.ref(self._listener, 'm_eventState')
        except NotFound as error:
            if 'm_activeServer is null' not in str(error):
                raise
            state = self._online_event_state(error)
            self._listener = self._online_controller
            return state

    @property
    def _online_controller(self):
        return self._controller or self._spectated

    def _event_type(self):
        """The event's type, logged once per event: (mode, level type), or None. TSU keeps the
        mode in TS.EventSettings.m_eventMode, an object (seen 2026-11-08) whose class names
        it, and the level type (track, arena ...) as a number next to it. Which is which mode
        is not known yet: the log is to tell, before the track map is kept to races. Where
        the field is not found, the log lists the fields there are, to look for it."""
        il = self.il
        try:
            logic = il.ref(self._listener, 'm_eventLogic')
            objects = [('settings', il.ref(logic, 'm_eventSettings')), ('logic', logic)]
            logic_class = il.class_name(logic)
        except (NotFound, OSError) as error:
            log.info('event type: no event settings (%s)', error)
            return None
        listed = []
        for role, obj in objects:
            try:
                fields = {
                    n: (offset, code)
                    for n, offset, static, code in il.field_list(il.memory.u64(obj))
                    if not static
                }
            except (NotFound, OSError):
                fields = {}
            listed.append((role, fields))
            for name in EVENT_TYPE_FIELDS:
                if name not in fields:
                    continue
                offset, code = fields[name]
                detail = ''
                try:
                    if code in REFERENCE_TYPES:  # an object: its class says the mode
                        mode = il.memory.u64(obj + offset)
                        if not mode:
                            continue
                        value = il.class_name(mode)
                        names = [n for n, _o, static, _c in il.field_list(il.memory.u64(mode)) if not static]
                        detail = f' (fields: {", ".join(names[:40]) or "none"})'
                    else:  # an enum is a value type (0x11) holding an int; a plain int too
                        value = il.memory.i32(obj + offset)
                except (NotFound, OSError):
                    continue
                level = None
                if LEVEL_TYPE_FIELD in fields:
                    try:
                        level = il.memory.i32(obj + fields[LEVEL_TYPE_FIELD][0])
                    except OSError:
                        pass
                log.info(
                    'event type: %s.%s = %s%s, %s = %s, logic %s',
                    role,
                    name,
                    value,
                    detail,
                    LEVEL_TYPE_FIELD,
                    level,
                    logic_class,
                )
                return value, level
        for role, fields in listed:
            log.info('event type: not found; %s fields: %s', role, ', '.join(list(fields)[:80]) or 'none')
        return None

    def _on_a_track(self):
        """Whether the event is driven on a track: a race (laps of a circuit) or a special
        event (from A to B), both TS.RaceEventMode. Battle, capture the flag, King of the
        Hill, Sumo, Soccer and Tag are played in arenas, where a track map would show a
        scribble of where the cars went. True when the mode is not known, as before."""
        return self.event_type is None or self.event_type[0] in TRACK_MODES

    def _draft_settings(self):
        """The event's DraftSettings (TS.EventSettings.drafting, through the race
        controller's event logic), or None where drafting is off or not found. Read once
        per event."""
        if self._draft is None:
            self._draft = False
            try:
                settings = self.il.ref(self._listener, 'm_eventLogic', 'm_eventSettings', 'drafting')
                if self._number('draft', settings, 'draftingOn'):
                    speed = self._number('draft', settings, 'draftingSpeedEffect')
                    downforce = self._number('draft', settings, 'draftingDownforceReduction')
                    try:
                        reach = self._number('draft', settings, 'maxDraftingDistance')
                        angle = self._number('draft', settings, 'maxDraftingAngle')
                    except (NotFound, OSError):
                        reach = angle = None
                    if speed > 0:
                        self._draft = DraftSettings(speed / 100, downforce / 100, reach, angle)
            except (NotFound, OSError):
                pass
        return self._draft or None

    def _online_event_state(self, error):
        """The online race's event state, from the controller found before while it is
        still that controller; else, at most every CLIENT_SEARCH_EVERY seconds, from a
        search of the game's data for objects of class TS.ClientEventController (one
        request the probe answers in about 1.5 s). Raises `error` when there is none."""
        il, memory = self.il, self.il.memory
        if self._controller is not None:
            try:
                if memory.u64(self._controller) == self._client_class:
                    state = il.ref(self._controller, 'm_eventState')
                    if il.list_items(il.ref(state, 'players')):
                        return state
            except (NotFound, OSError):
                pass
            self._controller = None
            self._next_search = 0.0  # gone (race over): look again at once
            self._empty_since = None
        if self._spectated is not None:
            # The race the player watches, while its clock runs: no search is needed, and
            # one would hold the reads up for as long as it takes. A look at it each read
            # is cheap, and sees the player join.
            try:
                if memory.u64(self._spectated) != self._client_class:
                    raise NotFound('that race is gone')
                state, driving = self._race_of(self._spectated)
                if driving:
                    self._controller, self._spectated = self._spectated, None
                    return state
                if self._watched_clock_runs(state):
                    return state
                if not self._watched_moved and not self._searched_past:
                    # Its clock never ran: likely an old race the search stopped at, with the
                    # race to read (maybe one the player drives) further on. Search past it at
                    # once, not after CLIENT_SPECTATE_EVERY; only once, as a race still on its
                    # grid looks the same.
                    log.info('the watched race has not run: searching past it')
                    self._searched_past = True
                    self._next_search = 0.0
            except (NotFound, OSError) as gone:
                log.info('the watched race is gone (%s)', gone)
                self._spectated = None
                self._next_search, self._empty_since = 0.0, None
        find = memory.find_pointers
        if find is None:
            raise error
        if self._clock() < self._next_search:
            # A long wait ends with the event, so that the next race is found soon.
            long_wait = self._search_wait > CLIENT_SEARCH_EVERY and self._event_running is not None
            if long_wait and self._event_running() is False:
                self._search_wait, self._empty_since = CLIENT_SEARCH_EVERY, None
                self._next_search = self._clock() + CLIENT_LOG_EVERY
            raise error
        if self._event_running is not None and self._event_running() is False:
            # Menus and lobbies: no event, nothing to search for (a search reads all
            # of the game's data and keeps a CPU core busy for over a second).
            self._search_wait, self._empty_since = CLIENT_SEARCH_EVERY, None
            self._next_search = self._clock() + CLIENT_LOG_EVERY
            raise error
        if self._client_class is None:
            self._client_class = il.find_class('TS', 'ClientEventController')
        watchable = []  # (controller, event state, hit) of races without the player
        started, hits, result = self._clock(), 0, 'stopped by an error'
        # The game tends to put a new race's objects where the last one's were, so the
        # search begins there, where the reader can (a search from the lowest address had
        # the race at 18% of the data, 6 s in).
        last = self._found_at if memory.find_pointers_from is not None else None
        log.info('searching for the online race%s', '' if last is None else ', from where the last one was')
        try:
            for candidate in (
                find(self._client_class)
                if last is None
                else memory.find_pointers_from(self._client_class, last)
            ):
                hits += 1
                try:
                    state, driving = self._race_of(candidate)
                except (NotFound, OSError):
                    continue  # a freed controller of an earlier race
                if driving:
                    self._controller, self._spectated = candidate, None
                    self._searched_past = False
                    result = 'race found' + self._from_the_last(candidate)
                    self._found_at = candidate
                    return state
                watchable.append((candidate, state, hits))
                if candidate != self._spectated:
                    # The first race to watch: the rest of the game's data stays unread (the
                    # race was at 18% of it in one search, which takes about 20 s in all).
                    break
            result = 'a race to watch, no local player' if watchable else 'no race'
        finally:
            # Counted from the search's end: in a CrossOver bottle a search of all the
            # data takes longer than the wait, and would start again at once.
            wait = CLIENT_SPECTATE_EVERY if watchable else self._search_wait
            ended = self._clock()
            self._next_search = ended + wait
            # An event may hold no race to read at all (a custom session), and in a bottle
            # a search takes over 20 s: over and over, it would never leave the game alone.
            # Not at first, though: a race joined in progress is set up a little later.
            if result == 'no race':
                if self._empty_since is None:
                    self._empty_since = started
                quick = ended - self._empty_since < CLIENT_SEARCH_QUICK_FOR
                self._search_wait = CLIENT_SEARCH_EVERY if quick else min(wait * 2, CLIENT_SEARCH_MOST)
            else:
                self._empty_since = None
                if result.startswith('race found'):
                    self._search_wait = CLIENT_SEARCH_EVERY
            log.info('search: %s, after %.1f s and %d hits', result, ended - started, hits)
        if not watchable:
            self._spectated = None
            raise error
        # Not the one whose clock stood still, if there is another: an old race can linger.
        self._spectated, state, hit = next((w for w in watchable if w[0] != self._spectated), watchable[0])
        self._watched_clock, self._watched_moved = None, False
        # Where it was among the hits: a search stops at the first race to watch, past the one
        # whose clock stood or never ran.
        log.info(
            'search: watching the race at hit %d of %d, %d races to watch%s',
            hit,
            hits,
            len(watchable),
            self._from_the_last(self._spectated),
        )
        self._found_at = self._spectated
        return state

    def _from_the_last(self, controller):
        """For the log: how far a race found is from the last one, which tells whether
        beginning the search there helps."""
        if self._found_at is None:
            return ''
        return f' ({(controller - self._found_at) / (1 << 20):+.1f} MiB from the last one)'

    def _watched_clock_runs(self, state):
        """Whether the watched race's clock moved within SPECTATE_STILL."""
        times = state + self._offset('state', state, 'times')
        clock = self.il.memory.i32(times + TIMES_NOW)
        now = self._clock()
        if clock != self._watched_clock:
            if self._watched_clock is not None:
                self._watched_moved, self._searched_past = True, False
            self._watched_clock, self._watched_at = clock, now
        return now - self._watched_at < SPECTATE_STILL

    def _race_of(self, controller):
        """(a controller's event state, whether the player drives in it). Raises NotFound
        or OSError when it holds no race."""
        il, memory = self.il, self.il.memory
        state = il.ref(controller, 'm_eventState')
        players = [player for player in il.list_items(il.ref(state, 'players')) if player]
        if not players:
            raise NotFound('no players')
        driving = any(memory.i32(p + il.offset(p, 'm_localHumanIndex')) >= 0 for p in players)
        return state, driving

    def local_player(self):
        """(event state, local TS.EventPlayer); raises NotFound outside a race."""
        state = self.event_state()
        player = self._local_in(state)
        if player is None:
            raise NotFound('no local player')
        return state, player

    def _local_in(self, state):
        """The event state's local TS.EventPlayer, or None: the player only watches."""
        il, memory = self.il, self.il.memory
        for player in il.list_items(il.ref(state, 'players')):
            if player and memory.i32(player + il.offset(player, 'm_localHumanIndex')) >= 0:
                return player
        return None

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
            self._sector_lines = ()
            self._reckoning = DeadReckoning()
            self._pit_stops = PitStops()
            self._recorder_tick, self._recorder_moved = None, 0
            self._draft, self._draft_time, self._draft_clock = None, {}, None
            self._fuel_history, self._wear_history, self._fuel_marks, self._types = {}, {}, {}, {}
            self._player = None
            self.event_type = self._event_type()
        if self._player is None:
            self._player = self._local_in(state)  # looked for anew: a spectator may join
        player = self._player
        if player is None:
            return self._watched_race(state)
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
            sector_lines=self._sector_lines,
            car=car,
        )
        players = self._players_with_positions(state_object, gates, clock)
        if position is None:
            # Online, as a client, the game keeps no position: the delta and the fuel
            # trend use the worked-out one.
            position = next((p.position for p in players if p.local), None)
        state = dataclasses.replace(
            state,
            players=players,
            position=position,
            draft=self._draft_settings(),
            on_a_track=self._on_a_track(),
        )
        live = state.live_fuel_trend(self._fuel_marks, self._fuel_history)
        if live is not None:
            state = dataclasses.replace(state, car=dataclasses.replace(car, fuel_trend=live))
        if state.car is not None and state.car.draft is not None:
            share = self._count_draft(state)
            state = dataclasses.replace(state, car=dataclasses.replace(state.car, draft_last_lap=share))
        return state

    def _players_with_positions(self, state, gates, clock):
        """Every player, with a position from the replay recorder or worked out where
        the game keeps none."""
        players = self._players(state)
        if any(p.position is None for p in players):
            recorded = self._recorded_positions(clock)
            if recorded:
                players = tuple(
                    dataclasses.replace(p, position=recorded[i])
                    if p.position is None and i in recorded
                    else p
                    for p, i in zip(players, self._player_indices)
                )
        return self._pit_stops.update(self._reckoning.fill(players, gates, clock), clock)

    def _watched_race(self, state):
        """The race as a spectator sees it: all the players and no car of the player's
        own. The lap count is the leader's, the rest comes from the first driver with
        statistics, as the limit and the track are the same for all."""
        il, memory = self.il, self.il.memory
        times = state + self._offset('state', state, 'times')
        span = struct.unpack('<5i', memory.read(times + TIMES_NOW, TIMES_LIMIT - TIMES_NOW + 4))
        clock, time_limit = span[0], span[-1]
        laps_to_finish, gates = 0, ()
        for player in il.list_items(self._ref('state', state, 'players')):
            if not player:
                continue
            try:
                stats = self._ref('player', player, 'm_stats')
                laps_to_finish = memory.u16(stats + self._offset('stats', stats, 'm_lapsToFinish'))
                gates = self._position_and_gates(player)[1]
            except (NotFound, OSError):
                continue
            if gates or self._gates is not None:
                break
        players = self._players_with_positions(state, gates, clock)
        return LapState(
            clock=clock,
            time_limit=time_limit,
            laps_completed=max((p.laps_completed for p in players), default=0),
            laps_to_finish=laps_to_finish,
            lap_starts=[],
            gates=gates,
            players=players,
            spectating=True,
            on_a_track=self._on_a_track(),
        )

    def _count_draft(self, state):
        """Add the race time since the last read to this lap's time in a slipstream (when
        the draft is at least DRAFT_COUNTS); the share of the last lap spent in one, or
        None before a lap is done."""
        lap = len(state.checkpoints) - 1
        last_clock, self._draft_clock = self._draft_clock, state.clock
        moved = last_clock is not None and 0 < state.clock - last_clock <= UNITS_PER_SECOND
        if moved and lap >= 0 and state.car.draft >= DRAFT_COUNTS:
            self._draft_time[lap] = self._draft_time.get(lap, 0) + state.clock - last_clock
        times = state.lap_times
        if lap < 1 or len(times) < lap or times[lap - 1] <= 0:
            return None
        return min(self._draft_time.get(lap - 1, 0) / times[lap - 1], 1.0)

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
        health, downforce_from, slowed_from = self._health(state, updater)
        draft, downforce_loss = self._drafting(updater)
        trend = None
        if lap >= 0:
            self._fuel_history.setdefault(lap, fuel_used)
            self._wear_history.setdefault(lap, tire_wear)
            self._fuel_marks.setdefault(lap, {}).setdefault(checkpoint, fuel_used)
            trend = fuel_trend(self._fuel_marks, self._fuel_history, lap, checkpoint, fuel_used)
        fuel_starts = [self._fuel_history[i] for i in sorted(self._fuel_history)]
        wear_starts = [self._wear_history[i] for i in sorted(self._wear_history)]
        return CarState(
            fuel_on=fuel_on,
            fuel_used=fuel_used,
            fuel_tank=tank,
            tires_on=tires_on,
            tire_wear=tire_wear,
            speed=speed,
            fuel_per_lap=per_lap(fuel_starts),
            wear_per_lap=per_lap(wear_starts),
            fuel_trend=trend,
            throttle=throttle,
            brake=brake,
            health=health,
            downforce_from=downforce_from,
            slowed_from=slowed_from,
            draft=draft,
            draft_downforce_loss=downforce_loss,
            tire_change=self._tire_change(state),
        )

    def _tire_change(self, state):
        """How far a tire change has come, 0 to 1. tireCompoundAndChangeTicks counted from 0
        to TIRE_CHANGE_END in the stops seen (12 s), with the compound in the same field.
        Above that it holds another compound's bits, not seen yet: 0, so the bar stays true."""
        try:
            ticks = self._number('vstate', state, 'tireCompoundAndChangeTicks')
        except (NotFound, ReadError):
            return 0.0
        return ticks / TIRE_CHANGE_END if 0 < ticks <= TIRE_CHANGE_END else 0.0

    def _drafting(self, updater):
        """(draft 0 to 1, downforce lost 0 to 1) of the local car, or (None, 0.0) without
        drafting. TS.CarStateUpdater keeps the slipstream's effect as multipliers: on the
        air resistance (m_draftingViscosityFactor, 1 - speed effect x draft) and on the
        downforce (m_draftingDownforceFactor, 1 - downforce reduction x draft); checked
        online: 0.927 and 0.418 at 10 % and 80 %, both a draft of 0.73."""
        settings = self._draft_settings()
        if settings is None:
            return None, 0.0
        speed_effect = settings.speed_effect
        try:
            drag = self._number('updater', updater, 'm_draftingViscosityFactor')
            downforce = self._number('updater', updater, 'm_draftingDownforceFactor')
        except (NotFound, ReadError):
            return None, 0.0
        draft = min(max((1 - drag) / speed_effect, 0.0), 1.0)
        return draft, min(max(1 - downforce, 0.0), 1.0)

    def _health(self, state, updater):
        """(health, downforce_from, slowed_from), each 0 to 1, or Nones in an event without
        damage. Health is TS.VehicleState.hitPoints of maxHitPoints; the limits are the
        game's own (CarStateUpdater: hit points to relative health multipliers, which are
        1 / the hit points where the effect starts)."""
        try:
            most = self._number('vstate', state, 'maxHitPoints')
            points = self._number('vstate', state, 'hitPoints')
            enabled = self._number('updater', updater, 'm_gradualDamageEnabled')
        except (NotFound, ReadError):
            return None, None, None
        if most <= 0 or not (enabled or points < most):
            return None, None, None

        def limit(name):
            try:
                multiplier = self._number('updater', updater, name)
            except (NotFound, ReadError):
                return None
            return min(1 / multiplier / most, 1.0) if multiplier > 0 else None

        return (
            min(max(points / most, 0.0), 1.0),
            limit('m_hitPointsToRelativeHealthMultiplierForDownforceLoss'),
            limit('m_hitPointsToRelativeHealthMultiplierForAcceleration'),
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
        il = self.il
        try:
            players = il.list_items(self._ref('state', state, 'players'))
        except (NotFound, OSError):
            return ()
        found, indices = [], []
        for index, player in enumerate(players):
            if not player:
                continue
            try:
                found.append(self._player_state(player))
                indices.append(index)
            except (NotFound, OSError):
                continue  # one unreadable player must not hide the others
        self._player_indices = indices  # each one's place in the game's list
        return tuple(found)

    def _recorded_positions(self, clock):
        """{place in the game's player list: (x, z)} from the replay recorder of an
        online race the game runs as a client, which keeps no other car positions.

        TS.EventRecorder.m_lastQuantizedVehicleStates holds each car's last recorded
        state, in the order of the player list, with the position in whole numbers:
        (value - 2**20) / 1024 (checked online: cars crossing a checkpoint line were
        0.8 from it on average). Empty when the recorder does not run (its tick stands
        still for RECORDER_STALE) or has no states."""
        if self._online_controller is None:
            return {}
        memory = self.il.memory
        try:
            recorder = self._ref('client', self._online_controller, 'm_eventRecorder')
            tick = memory.i32(recorder + self._offset('recorder', recorder, 'm_stateTick'))
            states = self._ref('recorder', recorder, 'm_lastQuantizedVehicleStates')
            count = memory.u64(states + ARRAY_LENGTH)
            if not 0 < count <= 256:
                return {}
            elements = struct.unpack(f'<{count}Q', memory.read(states + ARRAY_DATA, 8 * count))
            first = next((e for e in elements if e), None)
            if first is None:
                return {}
            to_position = self._offset('qstate', first, 'm_positionX')
        except (NotFound, OSError):  # optional: the race reads on without it
            return {}
        if tick != self._recorder_tick:
            self._recorder_tick, self._recorder_moved = tick, clock
        elif clock - self._recorder_moved > RECORDER_STALE:
            return {}
        found = {}
        for index, (element, data) in enumerate(
            zip(elements, memory.read_many([e + to_position for e in elements], 12))
        ):
            if not element or data is None:
                continue
            x, _y, z = struct.unpack('<3I', data)
            if x or z:
                found[index] = (
                    (x - QUANTIZED_ZERO) / QUANTIZED_SCALE,
                    (z - QUANTIZED_ZERO) / QUANTIZED_SCALE,
                )
        return found

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
        in_pit, position, velocity, forward, draft_drag = False, None, None, None, None
        try:
            vehicle = self._ref('player', player, 'm_vehicle')
        except NotFound:
            vehicle = None
        if vehicle is not None:
            updater = None
            try:
                updater = self._ref('vehicle', vehicle, 'm_stateUpdater')
                in_pit = bool(memory.u8(updater + self._offset('updater', updater, 'inPit')))
            except (NotFound, ReadError):
                pass
            try:
                # The whole pit area, from its entrance to its exit, not only the pit box.
                state = self._ref('vehicle', vehicle, 'm_state')
                in_pit = in_pit or bool(memory.u8(state + self._offset('vstate', state, 'inPitArea')))
            except (NotFound, ReadError):
                pass
            if updater is not None:
                velocity, forward = (
                    self._flat(updater, 'm_oldVelocity3d'),
                    self._flat(updater, 'm_oldForwardDirection'),
                )
                try:
                    draft_drag = self._number('updater', updater, 'm_draftingViscosityFactor')
                except (NotFound, ReadError):
                    pass
            try:
                where = vehicle + self._offset('vehicle', vehicle, 'm_statsNewPosition')
                x, _y, z = struct.unpack('<3f', memory.read(where, 12))
                position = _known_position(x, z)
            except (NotFound, ReadError):
                pass
        return PlayerState(
            name,
            flag,
            laps_completed,
            tuple(checkpoints),
            finished,
            in_pit,
            local,
            position,
            velocity,
            forward,
            draft_drag=draft_drag,
        )

    def _flat(self, obj, name):
        """A Vector3 field of a CarStateUpdater as (x, z), or None where it is missing."""
        try:
            x, _y, z = struct.unpack('<3f', self.il.memory.read(obj + self._offset('updater', obj, name), 12))
        except (NotFound, ReadError):
            return None
        return (x, z) if math.isfinite(x) and math.isfinite(z) else None

    def _number(self, role, obj, name):
        """A simple field read by the type the game gives it (int, float, ...)."""
        key = (role, name)
        if key not in self._types:
            found = {
                n: (offset, code)
                for n, offset, static, code in self.il.field_list(self.il.memory.u64(obj))
                if not static
            }
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
                    values.append(
                        min(max(self._number('controls', controls, f'{name}InThirds') / 3, 0.0), 1.0)
                    )
            return tuple(values)
        except (NotFound, ReadError):
            return None, None  # optional: the rest of the race reads on without it

    def _read_gates(self, player):
        """The track's checkpoint lines, in a few batched reads (120 checkpoints, each
        with its properties object). Also keeps which checkpoints are sector lines
        (`_sector_lines`): a track's maker can make any of them one."""
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
        ends = zip(
            memory.read_many([p + one for p in properties], 12),
            memory.read_many([p + two for p in properties], 12),
        )
        for first, second in ends:
            if first is None or second is None:
                raise NotFound('checkpoint line not readable')
            x1, _, z1 = struct.unpack('<3f', first)
            x2, _, z2 = struct.unpack('<3f', second)
            gates.append(((x1, z1), (x2, z2)))
        self._sector_lines = self._read_sector_lines(properties)
        return tuple(gates)

    def _read_sector_lines(self, properties):
        """The checkpoints whose `type` (TS.CheckpointType, one byte) is Sector; () where
        the game has no such field or it cannot be read: the bars then split the lap evenly."""
        memory = self.il.memory
        try:
            to_type = self._offset('properties', properties[0], 'type')
        except NotFound:
            return ()
        lines = []
        for number, data in enumerate(memory.read_many([p + to_type for p in properties], 1)):
            if data is None:
                return ()
            if data[0] == CHECKPOINT_SECTOR:
                lines.append(number)
        return tuple(lines)

    def _position_and_gates(self, player):
        """The car's (x, z) and the track's checkpoint lines, for the live delta; (None,
        ()) where the game does not have them."""
        memory = self.il.memory
        try:
            vehicle = self._ref('player', player, 'm_vehicle')
            x, _y, z = struct.unpack(
                '<3f', memory.read(vehicle + self._offset('vehicle', vehicle, 'm_statsNewPosition'), 12)
            )
            if self._gates is None:
                self._gates = self._read_gates(player)
            return _known_position(x, z), self._gates
        except NotFound:
            return None, ()


@dataclass(frozen=True)
class DraftSettings:
    """An event's drafting (TS.DraftingSettings): the most it takes off the air
    resistance and the downforce (0 to 1), and how far behind and how far off a car's
    line (degrees) the slipstream reaches (None where not read)."""

    speed_effect: float
    downforce: float
    reach: float | None = None
    angle: float | None = None


ANCHOR_WEIGHT = 0.4  # how much a checkpoint line's anchor moves to the newest crossing


def _on_segment(gate, point):
    """The point of a checkpoint line piece nearest to `point`."""
    (x1, z1), (x2, z2) = gate
    dx, dz = x2 - x1, z2 - z1
    length = dx * dx + dz * dz
    along = 0.0 if not length else min(max(((point[0] - x1) * dx + (point[1] - z1) * dz) / length, 0.0), 1.0)
    return (x1 + along * dx, z1 + along * dz)


class DeadReckoning:
    """Positions for cars whose position the game does not keep (online, when the game
    is a client and the race is not recorded: it stays at (0, 0)), worked out for the
    live delta and gaps. Each car starts at the checkpoint line it passed last, at the
    moment it passed it (its checkpoint time), and moves on by its velocity (which the
    game does keep) until the next line starts it again: about a second, so it cannot
    drift far. Where across the track it is stays unsure, so the radar does not use
    these.

    Where on the line: a car followed from its last line goes on from where its
    worked-out position meets the new line (the line's nearest point). That removes
    the error across the line's direction at every line, and the error along a line
    shrinks in every bend (the next line points another way), so a car's place settles
    onto the road within about a lap, even where the lines are long and set off to one
    side (on some tracks their middles lie far off the road). Once a car has been
    followed for a whole lap, each of its crossings also moves the line's anchor towards
    it (recent ones count most); a car seen for the
    first time, or after missing lines, starts at the anchor, which is the line's middle
    until cars have crossed it."""

    def __init__(self):
        self.cars = {}  # name -> (checkpoints passed, (x, z), race clock, lines followed in a row)
        self.anchors = {}  # line index -> (x, z): where cars cross it, recent crossings counting most

    def anchor(self, gates, index):
        """Where cars cross checkpoint line `index` (0 to len(gates) - 1)."""
        known = self.anchors.get(index)
        if known is not None:
            return known
        (x1, z1), (x2, z2) = gates[index]
        return ((x1 + x2) / 2, (z1 + z2) / 2)

    def _learn(self, gates, index, point, settled):
        """Where a car followed from its last line meets line `index`. A car followed
        for a whole lap (`settled`) has settled onto the road: the line's anchor moves
        towards where it crosses."""
        crossed = _on_segment(gates[index], point)
        if not settled:
            return crossed
        known = self.anchors.get(index)
        if known is None:
            self.anchors[index] = crossed
        else:
            ax, az = known
            self.anchors[index] = (
                ax + (crossed[0] - ax) * ANCHOR_WEIGHT,
                az + (crossed[1] - az) * ANCHOR_WEIGHT,
            )
        return crossed

    def position(self, player, gates, clock):
        passed = player.passed
        if player.velocity is None or not gates or not passed or passed[-1] == NO_CHECKPOINT:
            return None
        vx, vz = player.velocity
        count = len(passed)
        known = self.cars.get(player.name)
        followed = known[3] if known is not None else 0
        if known is not None and known[0] == count and clock >= known[2]:
            _count, (x, z), since, _followed = known
        else:
            index = (count - 1) % len(gates)
            if known is not None and known[0] == count - 1:
                # Followed from its last line to this one: it goes on from where its
                # worked-out place meets the line (which keeps where across the road it
                # is), and that teaches the line's anchor.
                _count, (x, z), since, _followed = known
                seconds = (passed[-1] - since) / UNITS_PER_SECOND
                followed += 1
                x, z = self._learn(gates, index, (x + vx * seconds, z + vz * seconds), followed > len(gates))
            else:
                x, z = self.anchor(gates, index)  # new, or lines missed: where cars cross
                followed = 0
            since = passed[-1]
        seconds = max(clock - since, 0) / UNITS_PER_SECOND
        x, z = x + vx * seconds, z + vz * seconds
        self.cars[player.name] = (count, (x, z), clock, followed)
        return (x, z)

    def fill(self, players, gates, clock):
        """`players` with a worked-out position where the game gave none."""
        filled = []
        for player in players:
            if player.position is None:
                worked_out = self.position(player, gates, clock)
                if worked_out is not None:
                    player = dataclasses.replace(player, position=worked_out, estimated=True)
            filled.append(player)
        return tuple(filled)


class PitStops:
    """Two timers for each car in the pits: from pit entry to pit exit, and how long it
    stood still in all, both live and kept for PIT_TIME_SHOWN after the exit. Standing over
    PIT_STOP_MOST shows neither: the driver may have retired. Timed with the race clock
    from the pit area and the velocity, which every car has, online too."""

    def __init__(self):
        self._visits = {}  # name: [race clock at entry, seconds stood, race clock when it stopped or None]
        self._kept = {}  # name: (seconds in the pits, seconds stood, race clock when to stop showing them)

    def update(self, players, clock):
        """`players` with the pit timers set on those to show them. Call once per read."""
        return tuple(self._updated(player, clock) for player in players)

    def _updated(self, player, clock):
        name = player.name
        visit = self._visits.get(name)
        if player.in_pit:
            self._kept.pop(name, None)
            if visit is None:
                visit = self._visits[name] = [clock, 0.0, None]
            self._stand(visit, player, clock)
            seconds, stood = (clock - visit[0]) / UNITS_PER_SECOND, _stood(visit, clock)
            if stood > PIT_STOP_MOST:
                return player
            return dataclasses.replace(player, pit_seconds=seconds, pit_stopped=stood)
        if visit is not None:
            del self._visits[name]
            seconds, stood = (clock - visit[0]) / UNITS_PER_SECOND, _stood(visit, clock)
            if stood <= PIT_STOP_MOST:
                self._kept[name] = (seconds, stood, clock + PIT_TIME_SHOWN * UNITS_PER_SECOND)
        kept = self._kept.get(name)
        if kept is None:
            return player
        if clock >= kept[2]:
            del self._kept[name]
            return player
        return dataclasses.replace(player, pit_seconds=kept[0], pit_stopped=kept[1])

    @staticmethod
    def _stand(visit, player, clock):
        """Note in `visit` whether the car stands now. Without a velocity it goes on as it was."""
        if player.velocity is None:
            return
        standing = math.hypot(*player.velocity) < PIT_STOPPED_SPEED
        if standing and visit[2] is None:
            visit[2] = clock
        elif not standing and visit[2] is not None:
            visit[1], visit[2] = _stood(visit, clock), None


def _stood(visit, clock):
    """The seconds a car in the pits has stood still so far."""
    return visit[1] + ((clock - visit[2]) / UNITS_PER_SECOND if visit[2] is not None else 0.0)


def _known_position(x, z):
    """(x, z), or None where the game does not keep it: in online races the position
    field stays at (0, 0), and the HUD then works without it."""
    if not (math.isfinite(x) and math.isfinite(z)) or (x == 0.0 and z == 0.0):
        return None
    return (x, z)


def format_time(units):
    """'1:24.095' for a time in 0.1 ms steps; '-' for None."""
    if units is None:
        return '-'
    sign, units = ('-' if units < 0 else ''), abs(units)
    minutes, rest = divmod(units, 60 * UNITS_PER_SECOND)
    return f'{sign}{minutes}:{rest / UNITS_PER_SECOND:06.3f}'


def format_delta(units, places=3):
    """'-0.412' ahead, '+1.230' behind, '0.000' when too small to show; with `places` 2,
    '-0.41', '+1.23' and '0.00'."""
    if abs(units) * 10**places < UNITS_PER_SECOND / 2:
        return f'{0:.{places}f}'
    return f'{"-" if units < 0 else "+"}{abs(units) / UNITS_PER_SECOND:.{places}f}'


DELTA_BAR_FULL = 1.0  # seconds of delta that fill the bar to its end
DELTA_TREND_WINDOW = 1.0  # seconds over which the bar's colour looks at how the delta moves
DELTA_COLOUR_EASE = 0.5  # seconds the bar's colour takes to go most of the way to a new one
DELTA_TREND_LEAST = 0.2  # seconds of this lap's delta before that counts
DELTA_STEADY = 0.02  # seconds gained or lost a second that still count as steady: white
DELTA_RATE_FULL = 0.15  # seconds gained or lost a second that give the full green or red


@dataclass(frozen=True)
class DeltaBarView:
    """The delta bar: the live delta to the best lap as a bar from the middle."""

    fill: float  # -1 to 1: how far it reaches, right when ahead of the best lap, left when behind
    trend: float  # -1 gaining fast (green) through 0 steady (white) to 1 losing fast (red)
    text: str  # the delta, as the delta section shows it


def delta_trend(rate):
    """The bar's colour, from `rate` in seconds lost a second: 0 (white) while steady, then
    more and more towards -1 (green) when gaining or 1 (red) when losing, full from
    DELTA_RATE_FULL. Gradual, so the colour does not flick between green and red as the
    rate wavers round nothing, as in sim racing delta bars."""
    share = (abs(rate) - DELTA_STEADY) / (DELTA_RATE_FULL - DELTA_STEADY)
    share = min(max(share, 0.0), 1.0)
    return -share if rate < 0 else share


class DeltaBar:
    """Follows the live delta through a lap to give the delta bar (a DeltaBarView), or None
    without a delta. A new lap starts afresh: the delta jumps there, which is not the driver
    gaining or losing."""

    def __init__(self):
        self._lap = self._clock = self._view = None
        self._history = collections.deque()  # (race clock, delta) over DELTA_TREND_WINDOW
        self._trend = 0.0  # the colour shown, easing towards the latest trend

    def update(self, state):
        """The view for the race `state`; at most once a read does it work anything out."""
        if state.clock == self._clock and state.laps_completed == self._lap:
            return self._view
        delta = state.delta_to_best
        if state.laps_completed != self._lap or delta is None:
            self._history.clear()
            self._trend = 0.0  # white at a lap's start: its jump is not the driver gaining
        last_clock = self._clock if self._history else None
        self._lap, self._clock, self._view = state.laps_completed, state.clock, None
        if delta is None:
            return None
        history = self._history
        history.append((state.clock, delta))
        while state.clock - history[0][0] > DELTA_TREND_WINDOW * UNITS_PER_SECOND:
            history.popleft()
        span = (state.clock - history[0][0]) / UNITS_PER_SECOND
        rate = (delta - history[0][1]) / UNITS_PER_SECOND / span if span >= DELTA_TREND_LEAST else 0.0
        seconds = delta / UNITS_PER_SECOND
        if last_clock is not None and state.clock > last_clock:
            # Eased, so that the colour drifts rather than jumps as the trend wavers.
            elapsed = (state.clock - last_clock) / UNITS_PER_SECOND
            self._trend += (delta_trend(rate) - self._trend) * (1 - math.exp(-elapsed / DELTA_COLOUR_EASE))
        self._view = DeltaBarView(
            min(max(-seconds / DELTA_BAR_FULL, -1.0), 1.0),  # ahead (improving) to the right
            self._trend,
            format_delta(delta, DELTA_PLACES).replace('-', '\u2212'),
        )
        return self._view


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


def status_text(snapshot, platform=sys.platform):
    """What TurboHUD is waiting for, for the tray icon's tooltip. On the Mac TurboHUD
    finds TSU by itself, so what is in the way is the reader's own message."""
    if snapshot.status == WAITING_FOR_GAME:
        if platform == 'darwin':
            return f'waiting: {snapshot.detail or "TSU is not running in CrossOver"}'
        return 'waiting for TSU (start it with the launch option)'
    if on_grid(snapshot, time.monotonic()):
        return 'spectating' if snapshot.state.spectating else 'racing'
    if snapshot.status in (STARTING, RACING):
        return 'race being set up'
    return 'waiting for a race'


BLUE_FROM = 2.0  # seconds: a car about to lap the local player this close shows the flag


def race_sections(
    snapshot,
    now,
    speed_unit='kmh',
    standings=None,
    radar=None,
    track_map=None,
    blue_within=BLUE_FROM,
    delta_bar=None,
    sector_bars=True,
):
    """{section name: rows} for a live-reader snapshot (see core.hud.RACE_SECTIONS); a
    section with nothing to show has no rows. Nothing before the grid: in the menus, the
    lobby and while a race loads the HUD keeps out of the way (status_text says why).
    `standings` (a Standings) holds the player list's order steady while cars pass;
    `radar` (a Radar) follows the cars' movement for the proximity radar; `track_map`
    (a core.trackmap.TrackMap) gives the track map, in the player list's order;
    `blue_within` is how many seconds behind a car shows the blue flag; `delta_bar` (a
    DeltaBar) gives the delta bar, under 'deltaview'; `sector_bars` False leaves the sector
    bars out (an option)."""
    if not on_grid(snapshot, now):
        return {}
    state = snapshot.state
    if state.spectating:
        return _watching_sections(snapshot, now, standings, track_map)
    if state.finished or state.laps_to_finish and state.laps_completed >= state.laps_to_finish:
        # Finished: the lap sections say so, and the rest stays (the player list above
        # all) while the others race on, until the race is over and the clock stops.
        sections = {
            'lap': [Row(f'Finished - {state.laps_completed} laps', 'title')],
            'current': [Row(format_time(state.best_lap), 'big', 'accent')],
            'times': [
                Row(
                    'Best lap   ',
                    'medium',
                    tail=f'Last {format_time(state.last_lap)}',
                    tail_color=_last_colour(state),
                )
            ],
        }
    else:
        sections = _racing_sections(snapshot, now)
        view = delta_bar.update(state) if delta_bar is not None else None
        if view is not None:
            sections['deltaview'] = view
    sections.update(car_sections(state.car, state.laps_to_go, speed_unit))
    sectors = sector_colours(state) if sector_bars else None
    if sectors is not None:
        sections['levels'] = {**sections.get('levels', {}), 'times': Sectors(sectors)}
    if 'draft' in sections and state.draft is not None:
        sections['draft'] = sections['draft'] + draft_rows(state)
    if state.players:
        order = standings.order(state.players, now) if standings is not None else None
        sections['players'] = players_rows(state.players, order, state.clock, state.gates)
        sections['laptimes'] = lap_times_rows(state.players, order, clock_now(snapshot, now))
        opacity = blue_flag_opacity(
            blue_flag(state.players, clock_now(snapshot, now), blue_within), blue_within
        )
        if opacity is not None:
            sections['blue'] = opacity
        view = radar.update(state.players, snapshot.read_at, state.draft) if radar is not None else None
        if view is not None:
            sections['radar'] = view
        if track_map is not None and state.on_a_track:  # no map, nor a track learnt, in an arena
            shown = track_map.update(state, order if order is not None else ranked(state.players))
            if shown is not None:
                flash = lap_flash(state)
                sections['trackmap'] = dataclasses.replace(shown, road=flash) if flash else shown
    return sections


def _watching_sections(snapshot, now, standings, track_map):
    """What a spectator sees: the race, with the leader's lap, the player list with the
    gaps to the leader, the lap times and the map; nothing about a car of their own."""
    state = snapshot.state
    sections = {'lap': [Row(f'Spectating  -  {_lap_title(state)}', 'title')]}
    if state.players:
        order = standings.order(state.players, now) if standings is not None else ranked(state.players)
        sections['players'] = players_rows(state.players, order, state.clock, state.gates, watching=True)
        sections['laptimes'] = lap_times_rows(state.players, order, clock_now(snapshot, now))
        if track_map is not None and state.on_a_track:
            shown = track_map.update(state, order)
            if shown is not None:
                sections['trackmap'] = shown
    return sections


def leader_lap(state):
    """The lap the race's furthest driver is on, or None without players."""
    lap = max((player_lap_number(player) for player in state.players), default=None)
    if lap is None:
        return None
    return min(lap, state.laps_to_finish) if state.laps_to_finish else lap


def _lap_title(state):
    title = (
        f'Lap {state.lap_number}/{state.laps_to_finish}'
        if state.laps_to_finish
        else f'Lap {state.lap_number}'
    )
    leader = leader_lap(state)
    if leader is not None and leader > state.lap_number:  # the player's own lap says it otherwise
        title += f' · Leader {leader}'
    left = state.time_left
    if left is not None:
        title += f'  -  {clock(math.ceil(left / UNITS_PER_SECOND))} left' if left > 0 else '  -  time is up'
    return title


def _racing_sections(snapshot, now):
    """The lap sections while the local player races."""
    state = snapshot.state
    title = _lap_title(state)
    delta = state.delta_to_best
    if delta is None:
        delta_row = Row('vs best  -', 'medium')
    else:
        color = 'text' if abs(delta) < DELTA_EVEN else 'ahead' if delta < 0 else 'behind'
        # The number on its own, with a true minus, as wide as a plus: only the number changes.
        number = format_delta(delta, DELTA_PLACES).replace('-', '\u2212')
        delta_row = Row(number, 'medium', color, tail=' vs best', tail_color=color, slot=DELTA_SLOT)
    return {
        'lap': [Row(title, 'title')],
        'current': [Row(format_tenths(current_lap_now(snapshot, now)), 'big', 'accent')],
        'delta': [delta_row],
        'times': [times_row(state)],
    }


def _best_and_when(times, starts):
    """The fastest of `times` and when it was set (the start of the lap after it), or
    (None, None); the first of equal times counts, as it was set first."""
    if not times:
        return None, None
    index = times.index(min(times))
    return times[index], starts[index + 1] if index + 1 < len(starts) else None


def _player_best_and_when(player):
    """As _best_and_when, from a player's start-line passes (see player_lap_times)."""
    starts = [lap[0] if lap else NO_CHECKPOINT for lap in player.checkpoints[: player.laps_completed + 1]]
    best = None
    for start, end in itertools.pairwise(starts):
        if NO_CHECKPOINT not in (start, end) and end > start and (best is None or end - start < best[0]):
            best = (end - start, end)
    return best or (None, None)


def lap_colours(state):
    """(last lap's colour, best lap's colour) for the local player, as on F1's timing
    screens: the best lap is purple while no one else in the race has gone faster (a time
    as fast counts for whoever set it first), else green. The last lap is the best's
    colour when it is the player's best lap, else white: no better than the best before.
    (None, None) before the first lap is done."""
    best, best_at = _best_and_when(state.lap_times, state.lap_starts)
    if best is None:
        return None, None
    session = True
    for player in state.players:
        if player.local:
            continue
        theirs, theirs_at = _player_best_and_when(player)
        if theirs is None:
            continue
        if theirs < best or (
            theirs == best and theirs_at is not None and best_at is not None and theirs_at < best_at
        ):
            session = False
            break
    best_colour = SESSION_BEST_COLOR if session else 'ahead'
    last_is_best = state.best_lap_index == len(state.lap_times) - 1
    return (best_colour if last_is_best else 'text'), best_colour


def _last_colour(state):
    return lap_colours(state)[0] or 'text'


def lap_flash(state):
    """The track map road's colour for LAP_FLASH after the local player ends a lap: purple
    for the race's fastest lap, green for a best of their own; '' otherwise (a slower
    lap, or after that time)."""
    if not state.lap_times or len(state.lap_starts) <= len(state.lap_times):
        return ''
    if not 0 <= state.clock - state.lap_starts[len(state.lap_times)] < LAP_FLASH:
        return ''
    last = lap_colours(state)[0]
    return (
        SESSION_BEST_COLOR if last == SESSION_BEST_COLOR else PERSONAL_BEST_COLOR if last == 'ahead' else ''
    )


def sector_starts(count, lines=()):
    """The checkpoint each sector starts at, for a lap of `count` checkpoints (the start
    line is checkpoint 0): at the start line and at each of the track's sector `lines`
    (checkpoints its maker made sector lines; TSU's own split times use them). A track
    without any is split into SECTORS_WITHOUT_LINES even sectors, as on F1's screens."""
    count = max(count, 0)
    marked = sorted({line for line in lines if 0 < line < count})
    if marked:
        return (0, *marked)
    parts = min(SECTORS_WITHOUT_LINES, count)
    return tuple(sorted({count * part // parts for part in range(parts)}))


def _sector_times(laps, index, starts):
    """[(time, when it ended) or None] for each sector of lap `index` of `laps` (each a
    lap's checkpoint times); the last sector ends at the next lap's start line. None for a
    sector not driven yet, or with a missed checkpoint."""
    passes = laps[index]
    line = laps[index + 1][0] if index + 1 < len(laps) and laps[index + 1] else None
    times = []
    for number, start in enumerate(starts):
        begin = passes[start] if start < len(passes) else None
        if number + 1 < len(starts):
            end = passes[starts[number + 1]] if starts[number + 1] < len(passes) else None
        else:
            end = line
        known = begin is not None and end is not None and NO_CHECKPOINT not in (begin, end) and end > begin
        times.append((end - begin, end) if known else None)
    return times


def sector_colours(state):
    """The colours of the sector bars below the last and best lap, or None: for the lap
    being driven, and for LAP_FLASH after the start line the lap just ended (until a
    sector of the new one is done). Each sector as on F1's timing screens: purple when
    faster than anyone else in the race had driven it by then and than the driver's own
    earlier laps, green when only the latter, dark yellow when slower than the driver's
    best; None while still to come."""
    laps = state.checkpoints
    count = len(state.gates) or max((len(lap) for lap in laps[: state.laps_completed]), default=0)
    starts = sector_starts(count, state.sector_lines)
    if not starts or not laps:
        return None
    current = state.laps_completed
    driving = current < len(laps) and not state.finished
    shown = current if driving else None
    if current >= 1 and current - 1 < len(laps):
        ended = state.lap_starts[current] if current < len(state.lap_starts) else None
        recent = ended is not None and 0 <= state.clock - ended < LAP_FLASH
        if recent and not (driving and any(_sector_times(laps, current, starts))):
            shown = current - 1
    if shown is None:
        return None
    mine = _sector_times(laps, shown, starts)
    earlier = [_sector_times(laps, index, starts) for index in range(shown)]
    others = []
    for player in state.players:
        if not player.local:
            theirs = player.checkpoints[: player.laps_completed + 1]
            others.extend(_sector_times(theirs, index, starts) for index in range(len(theirs)))
    colours = []
    for number, sector in enumerate(mine):
        if sector is None:
            colours.append(None)
            continue
        time, end = sector
        own = [lap[number][0] for lap in earlier if lap[number] is not None]
        personal = not own or time < min(own)
        before = [lap[number][0] for lap in others if lap[number] is not None and lap[number][1] < end]
        if personal and (not before or time < min(before)):
            colours.append(SESSION_BEST_COLOR)
        else:
            colours.append(PERSONAL_BEST_COLOR if personal else SECTOR_SLOW_COLOR)
    return tuple(colours)


def times_row(state):
    """The last and best lap, each in its colour (see lap_colours)."""
    last_colour, best_colour = lap_colours(state)
    return Row(
        f'Last {format_time(state.last_lap)}   ',
        'medium',
        last_colour or 'text',
        tail=f'Best {format_time(state.best_lap)}',
        tail_color=best_colour or 'text',
    )


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
            sections['fuelfinish'] = [
                Row(f'Finish {margin:+.1f} laps', 'medium', 'ahead' if margin >= 0 else 'behind')
            ]
    levels = {}
    if car.fuel_left is not None:
        margin = fuel_margin(car, laps_to_go)
        levels['fuel'] = (
            car.fuel_left,
            'behind' if margin is not None and margin < 0 else _level_color(car.fuel_left),
        )
    if car.tires_left is not None:
        sections['tires'] = [Row(f'Tires {car.tires_left * 100:.0f}%{_laps_text(car.tire_laps)}', 'medium')]
        levels['tires'] = (car.tires_left, _level_color(car.tires_left))
    if car.health is not None:
        effect = car.damage_effect
        color = {'slowed': 'behind', 'downforce': 'lift', None: 'text'}[effect]
        tail = {'slowed': '  slowed', 'downforce': '  less downforce', None: ''}[effect]
        # Rounded up as the game shows it (126 of 500 is 26 %): 0 % only when wrecked.
        shown = math.ceil(round(car.health * 100, 6))
        sections['health'] = [Row(f'Health {shown}%', 'medium', color, tail=tail, tail_color=color)]
        levels['health'] = (car.health, {'slowed': 'behind', 'downforce': 'lift', None: 'ahead'}[effect])
    if car.draft is not None:
        warn = car.draft_downforce_loss >= DRAFT_DOWNFORCE_WARN
        tail = f'  -{car.draft_downforce_loss * 100:.0f}% downforce' if warn else ''
        color = 'draft' if car.draft > 0 else 'text'
        sections['draft'] = [
            Row(f'Draft {car.draft * 100:.0f}%', 'medium', color, tail=tail, tail_color='lift')
        ]
        levels['draft'] = (car.draft, 'draft')
    if levels:
        sections['levels'] = levels  # {section: (0 to 1, colour)} for the bars below the text
    return sections


DELTA_SLOT = '+00.00'  # the delta's widest number
DRAFT_DOWNFORCE_WARN = 0.05  # downforce lost to the slipstream from which the draft section warns
DRAFT_COUNTS = 0.05  # a draft at least this strong counts as time in a slipstream
DRAFT_CARD_SECONDS = 20  # the race clock up to which the draft section shows the event's settings
DRAFTED_FROM = 0.05  # a car behind drafting at least this strongly shows as drafting you
DRAFTED_FROM_COLOR = '#5ec8ff'  # a car drafting the local player weakly: the draft's cyan
DRAFTED_CLOSE_COLOR = '#ff3b3b'  # ... at full strength (right behind): red
DRAFT_ANGLE_SPARE = 5  # degrees beyond the event's angle still taken as behind (positions lag a little)
LEVEL_LOW = 0.15  # below this the level bar is red
LEVEL_HALF = 0.35  # below this it is yellow


def _level_color(left):
    return 'behind' if left < LEVEL_LOW else 'lift' if left < LEVEL_HALF else 'ahead'


def with_local_time(sections, snapshot, now_struct):
    """`sections` plus the local time once TSU is running (its menus included); while
    TurboHUD waits for the game the clock stays away too."""
    if snapshot.status == WAITING_FOR_GAME:
        return sections
    return {**sections, 'localtime': local_time_rows(now_struct)}


MAX_PLAYER_ROWS = 8  # more players: the leader and those around the local player
MAX_NAME_SHOWN = 18


def ranked(players):
    """Players in race order: by how far they got (checkpoints passed, a finish
    counting as the next lap's start line), and as far by who got there first. So a
    lapped car that finishes right after the winner (once the winner is in, everyone
    finishes at their next crossing) stays behind the cars on the lead lap, finished or
    not, rather than coming second."""

    def key(player):
        finish = player.finish_time
        if finish is not None:
            # Up to the finish line only: the laps done, and the finish itself.
            reached = sum(len(lap) for lap in player.checkpoints[: player.laps_completed]) + 1
            return (-reached, finish)
        passed = player.passed
        return (-len(passed), passed[-1] if passed else 0)

    return sorted(players, key=key)


def live_gap(ahead, behind, clock, gates):
    """How far (0.1 ms) `behind` is behind `ahead` right now, live like the delta to
    the best lap: how far `behind` is from its last checkpoint to the next (by its
    position and the checkpoint lines `gates`) gives the moment `ahead` was at the same
    place, which is that long before `clock`. None without position or lines, or when
    `ahead` has not passed that place's next checkpoint yet."""
    if behind.position is None or not gates:
        return None
    lines = len(gates)
    first, second = ahead.passed, behind.passed
    k = len(second) - 1
    if k < 0 or len(first) < k + 1:
        return None
    if len(first) == k + 1:
        return _same_stretch_gap(ahead, behind, clock, gates)
    # As in LapState.stretch: a run of lines passed together starts the stretch, and a
    # line at the same spot as the one passed (same time for the car ahead) is skipped.
    start = k
    while start > 0 and second[start] == second[start - 1]:
        start -= 1
    following = k + 1
    while following < len(first) and first[following] == first[k]:
        following += 1
    if following >= len(first) or NO_CHECKPOINT in (first[start], first[following]):
        return None
    end = following
    while end + 1 < len(first) and first[end + 1] == first[following]:
        end += 1
    share = gate_share(
        [gates[i % lines] for i in range(start, k + 1)],
        [gates[i % lines] for i in range(following, end + 1)],
        behind.position,
    )
    there = first[start] + share * (first[following] - first[start])
    return max(round(clock - there), 0)


def _same_stretch_gap(ahead, behind, clock, gates):
    """live_gap while both cars are between the same two checkpoints (the one ahead
    has not reached the next yet): it went from that stretch's first line, at its time
    there, to where it is now; the moment it was where `behind` is now is that share of
    the way. None without its position or when it is not further on."""
    if ahead.position is None:
        return None
    lines = len(gates)
    k = len(behind.passed) - 1
    start = k
    while start > 0 and behind.passed[start] == behind.passed[start - 1]:
        start -= 1
    passed_at = ahead.passed[start]
    if passed_at == NO_CHECKPOINT or clock <= passed_at:
        return None
    back = [gates[i % lines] for i in range(start, k + 1)]
    next_line = [gates[(k + 1) % lines]]
    theirs = gate_share(back, next_line, ahead.position)
    mine = gate_share(back, next_line, behind.position)
    if theirs <= mine or theirs <= 0:
        return None
    there = passed_at + mine / theirs * (clock - passed_at)
    return max(round(clock - there), 0)


def gap(player, me, clock=None, gates=()):
    """`player` against `me`: ('time', 0.1 ms; negative: they are ahead), or ('laps',
    n) a lap or more apart (negative: ahead), or None before a comparison. Live (see
    live_gap) with the race `clock` and the checkpoint lines `gates` where the cars'
    positions are known; otherwise at the last checkpoint both passed."""
    theirs, mine = player.passed, me.passed
    lap_length = len(me.checkpoints[0]) if me.checkpoints and len(me.checkpoints) > 1 else 0
    difference = len(theirs) - len(mine)
    if lap_length and abs(difference) >= lap_length:
        laps = abs(difference) // lap_length
        return ('laps', -laps if difference > 0 else laps)
    common = min(len(theirs), len(mine)) - 1
    if common < 1:
        return None
    if clock is not None:
        they_lead = difference > 0 or difference == 0 and theirs[-1] < mine[-1]
        live = live_gap(player, me, clock, gates) if they_lead else live_gap(me, player, clock, gates)
        if live is not None:
            return ('time', -live if they_lead else live)
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
    return [order[0]] + order[first : first + around]


PIT_TAIL = '  PIT'
PIT_TAIL_ROOM = '  PIT 00.0s'  # what the player list's sample leaves room for


def _pit_time(player):
    """The time from pit entry to pit exit, for the lists."""
    return f'PIT {player.pit_seconds:.1f}s'


def _pit_bracket(player):
    """The time it stood still, in brackets, or nothing yet."""
    return f'({player.pit_stopped:.2f}s)' if player.pit_stopped >= PIT_STOP_LEAST else ''


def _pit_tail(player):
    """PIT with its timers for the player list, also for a while after the pit exit."""
    if player.pit_seconds is None:
        return PIT_TAIL if player.in_pit else ''
    return f'  {_pit_time(player)} {_pit_bracket(player)}'.rstrip()


def players_rows(players, order=None, clock=None, gates=(), watching=False):
    """The player list: position, flag, name, PIT, and the gap to the local player
    (live with the race `clock` and the checkpoint lines `gates`, see gap). `watching`:
    a spectator has no car, so the gaps are to the leader."""
    me = next((p for p in players if p.local), None)
    if watching:
        me = (ranked(players) if order is None else order)[0]
    rows = []
    for position, player in shown_players(players, order=order):
        tail = _pit_tail(player)
        # The section is sized for a full name and the first timer: the bracket takes its
        # room from the name.
        most = MAX_NAME_SHOWN - max(len(tail) - len(PIT_TAIL_ROOM), 0)
        name = player.name or '?'
        if len(name) > most:
            name = name[: most - 1] + '…'
        found = gap(player, me, clock, gates) if me is not None and player is not me else None
        color = (
            'text' if watching or found is None or found[1] == 0 else ('behind' if found[1] < 0 else 'ahead')
        )
        rows.append(
            Row(
                f'{position}. {name}',
                'small',
                'accent' if player.local else 'text',
                tail=tail,
                tail_color='lift',
                flag=flag_code(player.flag) or flag_text(player.flag),
                right=gap_text(found),
                right_color=color,
            )
        )
    return rows


MAX_LAP_TIME_ROWS = 20  # drivers in the lap times list; more: the leader and those around me


def player_lap_times(player):
    """A player's finished laps, 0.1 ms each: from one pass of the start line (each
    lap's first checkpoint) to the next. Laps with a missed start line are left out."""
    starts = [lap[0] if lap else NO_CHECKPOINT for lap in player.checkpoints[: player.laps_completed + 1]]
    return [
        end - start
        for start, end in itertools.pairwise(starts)
        if NO_CHECKPOINT not in (start, end) and end > start
    ]


def player_current_lap(player, clock):
    """How long `player` has been on its current lap at race `clock`, or None (finished,
    before its first start line, or a missed one)."""
    if player.finished or not player.checkpoints or not player.checkpoints[-1]:
        return None
    start = player.checkpoints[-1][0]
    if start == NO_CHECKPOINT or start > clock:
        return None
    return clock - start


def lap_times_rows(players, order=None, clock=0):
    """The lap times list: a heading, then each driver in race order with flag and name,
    their best lap and the running time of their current lap ('Fin' once finished) at
    race `clock`. The race's fastest lap is purple, as in F1. Up to MAX_LAP_TIME_ROWS drivers."""
    shown = shown_players(players, MAX_LAP_TIME_ROWS, order)
    bests = {id(player): min(player_lap_times(player), default=None) for _pos, player in shown}
    fastest = min((best for best in bests.values() if best is not None), default=None)
    rows = [
        Row(
            'Driver',
            'small',
            'accent',
            middle='Best',
            middle_color='accent',
            right='Lap',
            right_color='accent',
        )
    ]
    for position, player in shown:
        name = player.name or '?'
        if len(name) > MAX_NAME_SHOWN:
            name = name[: MAX_NAME_SHOWN - 1] + '…'
        best = bests[id(player)]
        running = player_current_lap(player, clock)
        timed = player.pit_seconds is not None and not player.finished
        plain_pit = player.in_pit and not player.finished and not timed
        bracket = _pit_bracket(player) if timed else ''
        time_now = 'Fin' if player.finished else format_tenths(running) if running is not None else '-'
        rows.append(
            Row(
                f'{position}. {name}',
                'small',
                'accent' if player.local else 'text',
                before=f'L{player_lap_number(player)}',
                flag=flag_code(player.flag) or flag_text(player.flag),
                middle=_pit_time(player) if timed else format_time(best),
                middle_color=(
                    'lift'
                    if timed
                    else SESSION_BEST_COLOR
                    if best is not None and best == fastest
                    else 'text'
                ),
                right='PIT' if plain_pit else bracket or time_now,
                right_color='lift' if plain_pit or bracket else 'text',
            )
        )
    return rows


def player_lap_number(player):
    """The lap `player` is on, counted from 1; once finished, the laps it drove."""
    return player.laps_completed if player.finished else player.laps_completed + 1


BLUE_FULL = 0.5  # seconds: this close or closer, the flag is fully visible
BLUE_FAINT = 0.2  # the flag's opacity at BLUE_FROM: faint, but visible


def blue_flag(players, now, within=BLUE_FROM):
    """Seconds until the nearest car that is about to lap the local player reaches them
    on the track, or None when no such car is `within` that many seconds. `now` is the
    race clock.

    A car is about to lap the local player when it is ahead in the race but behind on
    the track: it has passed more checkpoints, and the difference, taken round a lap, is
    more than half a lap (so it is nearer behind than ahead). Exactly whole laps ahead,
    it stands at the local player's last checkpoint: behind if it got there after the
    local player, else already past (driving just ahead), which is no flag. Any
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
        if units < 0:
            # It got to that checkpoint before the local player: it is already past,
            # driving just ahead (a whole lap ahead in count, but in front on the track).
            continue
        if same + 1 < len(mine) and mine[same + 1] != NO_CHECKPOINT:
            units = max(units, now - mine[same + 1])
        seconds = units / UNITS_PER_SECOND
        if seconds <= within and (nearest is None or seconds < nearest):
            nearest = seconds
    return nearest


def blue_flag_opacity(seconds, within=BLUE_FROM):
    """How visible the blue flag is (0 to 1) for a car `seconds` behind, from `within`: BLUE_FAINT at
    BLUE_FROM, rising evenly to 1 at BLUE_FULL; None (no flag) without a car."""
    if seconds is None or seconds > within:
        return None
    share = min(max((within - seconds) / max(within - BLUE_FULL, 1e-6), 0.0), 1.0)
    return BLUE_FAINT + (1 - BLUE_FAINT) * share


# Proximity radar. Positions and speeds are in the game's own unit, so the time gap
# (distance / speed) needs no scale. The car's size was measured in an online race with
# 13 AI cars (Tatuus FA01, 630 reads): cars in line got no closer than about 4.0 centre
# to centre, cars side by side about 1.3 to 1.4. Other car models may differ a little.
CAR_LENGTH = 4.0
CAR_WIDTH = 1.4
RADAR_FROM = 0.5  # seconds behind or ahead: the radar appears, faint
RADAR_FULL = 0.1  # seconds behind or alongside: fully visible
RADAR_FAINT = 0.2  # its opacity at RADAR_FROM
RADAR_CAR_SCALE = 1.4  # cars are drawn this much larger than their real size on the radar
RADAR_CAR_LEAST = 0.03  # and at least this wide, as a share of the radar
RADAR_SIDE = 8.0  # sideways reach: a car farther to the side (another part of the track) does not count
RADAR_VIEW = 20.0  # the radar shows at least this far behind; more at speed (radar_view)
RADAR_MIN_SPEED = 3.0  # slower (standing on the grid): no radar, the direction is unknown
HEADING_SPAN = 0.3  # seconds of movement a car's direction and speed are taken from (no game values)
MAX_CARRY = 0.25  # seconds a car's position is carried on along its velocity since its last update
RADAR_HOLD = 0.4  # seconds the radar stays (fading) after the last car that counted
RADAR_EASE = 0.35  # share of the way to a lower opacity it goes per read
HEADING_KEEP = 1.0  # seconds of positions kept per car


@dataclass(frozen=True)
class Blip:
    """Another car on the radar: `ahead` and `side` (right positive) from the middle
    of the local car, in game units along its direction; `angle` its direction against
    the local car's, in radians; `seconds` the time gap if it counts (behind, beside or ahead)."""

    ahead: float
    side: float
    angle: float
    seconds: float | None
    in_cone: bool | None = None  # a car ahead's slipstream: whether the local car is in it; None: not drawn


@dataclass(frozen=True)
class RadarView:
    opacity: float  # 0 to 1 for the whole radar
    blips: tuple  # Blip
    view: float = RADAR_VIEW  # how far behind the local car the radar reaches
    cone: tuple | None = None  # (reach, angle in degrees) of the slipstream behind cars ahead
    within: float = RADAR_FROM  # seconds: a car this close counts


def radar_view(speed, within=RADAR_FROM):
    """How far behind (and ahead) the radar reaches at `speed`: a car `within` seconds away
    still shows, with room to spare."""
    return max(RADAR_VIEW, speed * within + 2 * CAR_LENGTH)


def radar_car_size(per_unit, box):
    """(width, length) of a car on a radar `box` wide with `per_unit` pixels to the game's
    unit: larger than life, to see it at a glance, and never so small that a radar zoomed
    out for a long warning time loses it."""
    width = max(CAR_WIDTH * per_unit * RADAR_CAR_SCALE, box * RADAR_CAR_LEAST)
    return width, width * CAR_LENGTH / CAR_WIDTH


def _heading(history, now):
    """(direction unit vector, speed) from a car's recent (time, (x, z)), or None."""
    if len(history) < 2:
        return None
    last_time, last = history[-1]
    first = next(((t, p) for t, p in history if last_time - t <= HEADING_SPAN), history[-2])
    if first[0] >= last_time:
        first = history[-2]
    dt = last_time - first[0]
    dx, dz = last[0] - first[1][0], last[1] - first[1][1]
    length = math.hypot(dx, dz)
    if dt <= 0 or length <= 0:
        return None
    return (dx / length, dz / length), length / dt


def radar_opacity(seconds, within=RADAR_FROM):
    """How visible the radar is for the nearest counting car `seconds` away: None (not
    shown) past `within`, RADAR_FAINT there, rising evenly to 1 at RADAR_FULL."""
    if seconds is None or seconds > within:
        return None
    share = min(max((within - seconds) / max(within - RADAR_FULL, 1e-6), 0.0), 1.0)
    return RADAR_FAINT + (1 - RADAR_FAINT) * share


def in_slipstream(ahead, side, angle, draft):
    """Whether the local car (at the radar's middle) is in the slipstream of a car
    `ahead` and `side` from it, heading `angle` against it: within the event's reach
    behind that car's tail and its angle off that car's line."""
    back = (-math.sin(angle), -math.cos(angle))  # behind that car, in the local car's frame
    tail = (side + back[0] * CAR_LENGTH / 2, ahead + back[1] * CAR_LENGTH / 2)
    to_me = (-tail[0], -tail[1])
    distance = math.hypot(*to_me)
    if distance == 0:
        return True
    if distance > draft.reach:
        return False
    off_line = math.degrees(
        math.acos(max(-1.0, min(1.0, (to_me[0] * back[0] + to_me[1] * back[1]) / distance)))
    )
    return off_line <= draft.angle


def drafted_by(players, draft):
    """(name, strength 0 to 1) of the strongest car behind the local player that is
    in its slipstream (within the event's reach and angle behind it) and drafting, or
    None. Only cars with read positions count."""
    me = next((p for p in players if p.local), None)
    if draft is None or draft.reach is None or me is None or me.position is None or me.estimated:
        return None
    heading = me.forward or me.velocity
    if heading is None or not any(heading):
        return None
    length = math.hypot(*heading)
    fx, fz = heading[0] / length, heading[1] / length
    found = None
    for player in players:
        if player.local or player.position is None or player.estimated or player.draft_drag is None:
            continue
        strength = min(max((1 - player.draft_drag) / draft.speed_effect, 0.0), 1.0)
        if strength < DRAFTED_FROM:
            continue
        dx, dz = player.position[0] - me.position[0], player.position[1] - me.position[1]
        behind = -(dx * fx + dz * fz) - CAR_LENGTH / 2  # from my tail
        side = dx * fz - dz * fx
        if behind <= 0 or behind > draft.reach + CAR_LENGTH:
            continue
        if math.degrees(math.atan2(abs(side), behind)) > draft.angle + DRAFT_ANGLE_SPARE:
            continue
        if found is None or strength > found[1]:
            found = (player.name, strength)
    return found


def draft_rows(state):
    """The draft section's small rows below the meter: the event's drafting at the
    start, then the last lap's time in a slipstream; and who drafts the local player."""
    draft, car = state.draft, state.car
    rows = []
    if state.clock < DRAFT_CARD_SECONDS * UNITS_PER_SECOND:
        text = f'Max -{draft.speed_effect * 100:.0f}% drag  -{draft.downforce * 100:.0f}% downforce'
        if draft.reach is not None and draft.angle is not None:
            text += f'  reach {draft.reach:g}  {draft.angle:g}°'
        rows.append(Row(text, 'small'))
    elif car is not None and car.draft_last_lap is not None:
        rows.append(Row(f'Last lap {car.draft_last_lap * 100:.0f}% in a slipstream', 'small'))
    who = drafted_by(state.players, draft)
    if who is not None:
        name, strength = who
        if len(name) > MAX_NAME_SHOWN:
            name = name[: MAX_NAME_SHOWN - 1] + '…'
        # From the draft's cyan to red, the stronger its slipstream from the local car
        # (the closer it is behind).
        color = blend(DRAFTED_FROM_COLOR, DRAFTED_CLOSE_COLOR, strength)
        rows.append(Row(f'{name} drafts you {strength * 100:.0f}%', 'small', color))
    return rows


def radar_blips(me, speed, others, draft=None, within=RADAR_FROM):
    """Blips for `others` [(position, direction or None)] around the local car at `me`
    ((x, z), direction) at `speed`. A car counts when it is no more than RADAR_SIDE to
    the side, behind, beside or ahead: beside (overlapping in length) is 0 s, behind or
    ahead is the gap between the two cars' ends over the local speed. With the event's
    `draft` (DraftSettings with reach and angle), cars ahead get their slipstream drawn,
    and whether the local car is in it."""
    (mx, mz), (fx, fz) = me
    cone = draft is not None and draft.reach is not None and draft.angle is not None
    blips = []
    for (x, z), direction in others:
        dx, dz = x - mx, z - mz
        ahead = dx * fx + dz * fz
        side = dx * fz - dz * fx  # right of the direction of travel (x right, z forward)
        view = radar_view(speed, within)
        if abs(ahead) > view * 1.5 or abs(side) > view:
            continue
        angle = 0.0
        if direction is not None:
            angle = math.atan2(direction[0] * fz - direction[1] * fx, direction[0] * fx + direction[1] * fz)
        seconds = None
        if abs(side) <= RADAR_SIDE:
            gap = abs(ahead) - CAR_LENGTH  # nose to tail; under 0: overlapping
            seconds = max(gap, 0.0) / speed
        in_cone = in_slipstream(ahead, side, angle, draft) if cone and ahead > CAR_LENGTH / 2 else None
        blips.append(Blip(ahead, side, angle, seconds, in_cone))
    return tuple(blips)


class Radar:
    """Follows every car to give the proximity radar (a RadarView) for the latest read,
    or None when no car is close enough behind, beside or ahead to show it.

    The game moves a car's position on only every other read or so (about ten times a
    second, seen on a hosted online race), so positions are carried on along each car's
    velocity between its updates, and direction and speed come from the game's own
    values (CarStateUpdater: forward direction and velocity) where it has them, else
    from the car's movement. The radar shows at once when a car comes close; when none
    counts any more it stays for RADAR_HOLD and fades, so it does not blink."""

    def __init__(self, within=RADAR_FROM):
        self.within = within  # seconds: a car this close counts (a setting)
        self.cone = True  # draw the slipstream behind cars ahead (a setting)
        self.tracks = {}  # player name -> [(read time, (x, z))], only when it changed
        self.read_at = None
        self.opacity = 0.0
        self.counted_at = None  # read time a car last counted

    def _record(self, players, read_at):
        names = set()
        for player in players:
            if player.position is None:
                continue
            names.add(player.name)
            track = self.tracks.setdefault(player.name, [])
            if not track or track[-1][1] != player.position:
                track.append((read_at, player.position))
            while len(track) > 2 and read_at - track[0][0] > HEADING_KEEP:
                track.pop(0)
        for name in set(self.tracks) - names:
            del self.tracks[name]

    def _motion(self, player, now):
        """(position now, direction, speed) of a car, or None without enough to go on."""
        track = self.tracks.get(player.name)
        if not track:
            return None
        changed_at, position = track[-1]
        velocity = player.velocity
        if velocity is None:
            moved = _heading(track, now)
            if moved is None:
                return None
            (fx, fz), speed = moved
            velocity = (fx * speed, fz * speed)
        speed = math.hypot(*velocity)
        ahead = min(max(now - changed_at, 0.0), MAX_CARRY)
        position = (position[0] + velocity[0] * ahead, position[1] + velocity[1] * ahead)
        direction = player.forward
        if direction is None or not any(direction):
            if speed <= 0:
                return None
            direction = (velocity[0] / speed, velocity[1] / speed)
        else:
            length = math.hypot(*direction)
            direction = (direction[0] / length, direction[1] / length)
        return position, direction, speed

    def update(self, players, read_at, draft=None):
        if not self.cone:
            draft = None
        fresh = read_at != self.read_at
        if fresh:
            self.read_at = read_at
            self._record(players, read_at)
        players = [p for p in players if not p.estimated]  # not exact enough for the radar
        me = next((p for p in players if p.local), None)
        mine = None if me is None or me.in_pit or me.finished else self._motion(me, read_at)
        if mine is None or mine[2] < RADAR_MIN_SPEED:
            self.opacity, self.counted_at = 0.0, None
            return None
        position, direction, speed = mine
        others = []
        for player in players:
            if player.local or player.in_pit or player.finished:
                continue
            theirs = self._motion(player, read_at)
            if theirs is not None:
                others.append((theirs[0], theirs[1]))
        blips = radar_blips((position, direction), speed, others, draft, self.within)
        if fresh:
            nearest = min((b.seconds for b in blips if b.seconds is not None), default=None)
            target = radar_opacity(nearest, self.within)
            if target is not None:
                self.counted_at = read_at
                # Up at once (a car beside matters now), down gently.
                self.opacity = (
                    target if target >= self.opacity else self.opacity + (target - self.opacity) * RADAR_EASE
                )
            elif self.counted_at is not None and read_at - self.counted_at <= RADAR_HOLD:
                self.opacity = max(RADAR_FAINT, self.opacity + (RADAR_FAINT - self.opacity) * RADAR_EASE)
            else:
                self.opacity, self.counted_at = 0.0, None
        if self.opacity <= 0:
            return None
        cone = (draft.reach, draft.angle) if draft is not None and draft.reach is not None else None
        return RadarView(self.opacity, blips, radar_view(speed, self.within), cone, self.within)


def race_rows(snapshot, now):
    """All sections' rows in one list, top to bottom (for the terminal and tests)."""
    sections = race_sections(snapshot, now)
    order = (
        'lap',
        'current',
        'delta',
        'times',
        'fuel',
        'fuelfinish',
        'tires',
        'health',
        'draft',
        'speed',
        'players',
    )
    return [row for name in order for row in sections.get(name, [])]
