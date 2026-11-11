"""The track map: the track's shape, learnt from where the cars drive, and where the cars
that matter are on it.

The track's own checkpoint lines are no good for its shape: on some tracks they are
long (up to 300 units) and set well off to one side, so their middles lie far from the
road (seen on 2026-11-03 in an AI event: cars up to 67 units from a line through the
middles). So the map follows the cars instead. TrackMap records every car's path (where
the game gives real positions; not worked-out ones, not in the pits); once any car has
driven a whole lap without a break, that lap is the track. Until then the longest
stretch driven so far shows. A learnt track is saved in TurboHUD's own folder, under a
name made from the track's checkpoint lines, so the next race there has it at once.

Only a clean lap counts (asked for by the user on 2026-11-11: a first lap with a trip over
the grass was learnt, and kept, as the track): a car's path starts afresh while it has all
four wheels off the tarmac, nearly stands or goes backwards, as when it is put back on the
track. A track saved before that is still shown, and learnt again from the next clean lap.

Several clean laps are compared before one is saved (asked for by the user on 2026-11-11:
a shortcut on tarmac or kerbs is clean, so a first lap through it was learnt). The first
shows at once; once LEARN_LAPS are in, laps clearly shorter than the longest are left out
(a shortcut saves distance) and of the rest the one nearest the others is kept and saved
(see choose_lap). One lap a car while there are enough cars, so one driver who cuts every
lap is outvoted. A track saved from a single lap is still shown, and learnt again this way.

A spectator sees every car, with the leader marked. On the map otherwise: the local player, the race leader, the next car ahead and the next car
behind in the race order (the player list's, held steady while cars pass), and smaller
dots for backmarkers (cars the local player is about to lap) on the road between the
local player and the next car ahead (a backmarker is never the "next car behind", even
when it comes next in the race order: it is ahead on the road). The other cars are
faint grey dots, if the player turns them on.
"""

import hashlib
import itertools
import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path

SMOOTHING = 1  # rounds of corner cutting on the learnt line
MAP_POINTS = 300  # a learnt line is evened out to about this many points ...
LEAST_SPACING = 2.0  # ... but no closer than this (game units)
JUMP = 40.0  # a car this far from its last position (game units) was put back on the track: its path starts afresh
ROAD_SHARE = 0.03  # the road's width on the map, as a share of the map
LEAST_ROAD = 2.5  # pixels
LAPPING_SHARE = 0.5  # a car more than half a lap behind in the race and ahead on the road is a backmarker
TRACKS_FOLDER = 'tracks'
CLEAN_GRIP = 0.9  # all four wheels on less grip than this: off the tarmac (as race.YELLOW_OFF_GRIP)
CLEAN_SPEED = 1.0  # slower than this along the car (or backwards): not driving the track
LEARN_LAPS = 3  # clean laps compared before a track is saved
SHORT_LAP = 0.985  # a lap shorter than this share of the longest is left out: a shortcut
COMPARE_POINTS = 100  # laps are compared at about this many points each
HEADING_SEARCH = 20  # points of the learnt line searched each way from a car's last one (of about 600)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrackOutline:
    """The track for the map: its line (x, z) through the road, whether it is a loop
    (a whole lap learnt), the start line as (point, direction of travel) or None, and
    its bounds (min x, min z, max x, max z)."""

    points: tuple
    closed: bool
    start: tuple | None
    bounds: tuple


@dataclass(frozen=True)
class MapDot:
    """A car on the map. `role`: 'me', 'leader', 'ahead', 'behind', 'backmarker', 'other'
    or, for a spectator, 'car'. `ahead_too`: the leader is also the next car ahead.
    `yellow`: the yellow flag is out for it (turbohud.core.race.YellowFlags)."""

    position: tuple
    role: str
    in_pit: bool = False
    ahead_too: bool = False
    yellow: bool = False


@dataclass(frozen=True)
class TrackMapView:
    outline: TrackOutline
    dots: tuple  # MapDot, drawn in this order (the local player last, on top)
    road: str = ''  # the road's colour for a moment after a fast lap ('#rrggbb'); '' is the usual
    yellow: tuple = ()  # stretches of the road ((x, z) points each) in a sector under a yellow flag


def _to_segment(point, segment):
    """How far `point` is from the line `segment` ((x, z), (x, z))."""
    (x1, z1), (x2, z2) = segment
    dx, dz = x2 - x1, z2 - z1
    length = dx * dx + dz * dz
    share = 0.0 if length == 0 else min(max(((point[0] - x1) * dx + (point[1] - z1) * dz) / length, 0.0), 1.0)
    return math.dist(point, (x1 + share * dx, z1 + share * dz))


def gate_marks(points, gates):
    """For each checkpoint line in `gates`, the index of the point of the learnt line
    (`points`) nearest to it: where the road crosses it. A line, unlike its middle, crosses
    the road even where it reaches far to one side."""
    return tuple(min(range(len(points)), key=lambda i, g=gate: _to_segment(points[i], g)) for gate in gates)


def stretch(points, start, end):
    """The points of a closed line from index `start` to `end`, going forwards (round the
    end of the list where need be); the whole line when they meet."""
    count = len(points)
    steps = (end - start) % count or count
    return tuple(points[(start + step) % count] for step in range(steps + 1))


def _middle(gate):
    (x1, z1), (x2, z2) = gate
    return ((x1 + x2) / 2, (z1 + z2) / 2)


def smoothed(points, closed, rounds=SMOOTHING):
    """The line through `points` with its corners cut (Chaikin): each round puts two
    points on every piece, a quarter from each end. An open line keeps its ends."""
    points = list(points)
    for _ in range(rounds):
        if len(points) < 3:
            break
        pairs = list(zip(points, points[1:] + points[:1])) if closed else list(itertools.pairwise(points))
        cut = []
        for (x1, z1), (x2, z2) in pairs:
            cut.append((0.75 * x1 + 0.25 * x2, 0.75 * z1 + 0.25 * z2))
            cut.append((0.25 * x1 + 0.75 * x2, 0.25 * z1 + 0.75 * z2))
        points = cut if closed else [points[0], *cut, points[-1]]
    return points


def evened(points, spacing):
    """Points along the line through `points`, `spacing` apart (and its last point)."""
    if len(points) < 2:
        return list(points)
    result, carry = [points[0]], 0.0
    for (x1, z1), (x2, z2) in itertools.pairwise(points):
        length = math.hypot(x2 - x1, z2 - z1)
        along = spacing - carry
        while along <= length:
            share = along / length
            result.append((x1 + (x2 - x1) * share, z1 + (z2 - z1) * share))
            along += spacing
        carry = length - (along - spacing)
    if result[-1] != points[-1]:
        result.append(points[-1])
    return result


def _unit(dx, dz):
    length = math.hypot(dx, dz)
    return (dx / length, dz / length) if length > 0 else None


def start_mark(path, gate, index=None):
    """The start line's mark on a driven `path`: (point, direction of travel) where the
    path first crosses the start line `gate` ((x1, z1), (x2, z2)). Where it does not
    (a line too short), between the points before and after `index`, the first point
    after the game counted the line; else None."""
    (ax, az), (bx, bz) = gate
    for (x1, z1), (x2, z2) in itertools.pairwise(path):
        rx, rz, sx, sz = x2 - x1, z2 - z1, bx - ax, bz - az
        cross = rx * sz - rz * sx
        if cross == 0:
            continue
        t = ((ax - x1) * sz - (az - z1) * sx) / cross  # along the path's piece
        u = ((ax - x1) * rz - (az - z1) * rx) / cross  # along the line
        direction = _unit(rx, rz)
        if 0 <= t <= 1 and 0 <= u <= 1 and direction is not None:
            return ((x1 + rx * t, z1 + rz * t), direction)
    if index is None or not 0 < index < len(path):
        return None
    (x1, z1), (x2, z2) = path[index - 1], path[index]
    direction = _unit(x2 - x1, z2 - z1)
    return (((x1 + x2) / 2, (z1 + z2) / 2), direction) if direction is not None else None


def outline_from_path(path, closed, start=None):
    """The TrackOutline for a driven `path` [(x, z)]: evened out and smoothed a little;
    `start` is the start line's mark (see start_mark) or None. None with too short a
    path."""
    if len(path) < 3:
        return None
    total = sum(math.dist(a, b) for a, b in itertools.pairwise(path))
    if total <= 0:
        return None
    spacing = max(total / MAP_POINTS, LEAST_SPACING)
    points = evened(path, spacing)
    if closed and len(points) > 2 and math.dist(points[-1], points[0]) < spacing:
        points.pop()  # the lap ends where it began
    points = tuple(smoothed(points, closed))
    xs, zs = [x for x, _z in points], [z for _x, z in points]
    return TrackOutline(points, closed, start, (min(xs), min(zs), max(xs), max(zs)))


def path_length(points, closed=True):
    total = sum(math.dist(a, b) for a, b in itertools.pairwise(points))
    return total + (math.dist(points[-1], points[0]) if closed and len(points) > 1 else 0.0)


def lap_gap(first, second):
    """How far apart two laps' lines run: the mean distance from each point of one to the
    nearest point of the other, both ways. A shortcut gives a large gap where the others
    go round and it does not."""

    def one_way(points, other):
        return sum(min(math.dist(p, q) for q in other) for p in points) / len(points)

    return (one_way(first, second) + one_way(second, first)) / 2


def choose_lap(laps):
    """The index of the lap (each a list of (x, z)) to keep as the track: of the laps at
    least SHORT_LAP as long as the longest, the one whose lines run nearest the others."""
    lengths = [path_length(lap) for lap in laps]
    longest = max(lengths)
    kept = [i for i, length in enumerate(lengths) if length >= SHORT_LAP * longest]
    if len(kept) < 3:
        return max(kept, key=lambda i: lengths[i])  # no majority to go by: the longest
    sparse = {}
    for i in kept:
        spacing = max(lengths[i] / COMPARE_POINTS, LEAST_SPACING)
        sparse[i] = evened(laps[i], spacing)
    return min(kept, key=lambda i: sum(lap_gap(sparse[i], sparse[j]) for j in kept if j != i))


def track_key(gates):
    """A name for the track from its checkpoint lines, for its saved file."""
    text = ';'.join(f'{x:.1f},{z:.1f}' for gate in gates for x, z in gate)
    return hashlib.sha1(text.encode('ascii')).hexdigest()[:16]


def map_transform(bounds, size, padding):
    """(scale, x offset, y offset) that fits `bounds` (min x, min z, max x, max z)
    into a `size` (width, height) box, `padding` pixels in from each edge, the same
    scale both ways and centred. Seen from above: x to the right, z up the screen, so
    a point goes to (x offset + x * scale, y offset - z * scale)."""
    min_x, min_z, max_x, max_z = bounds
    width, height = size
    room_x, room_y = max(width - 2 * padding, 1), max(height - 2 * padding, 1)
    scale = min(room_x / max(max_x - min_x, 1e-9), room_y / max(max_z - min_z, 1e-9))
    return scale, width / 2 - (min_x + max_x) / 2 * scale, height / 2 + (min_z + max_z) / 2 * scale


def road_width(map_size):
    """The road's width on the map in pixels."""
    return max(LEAST_ROAD, ROAD_SHARE * map_size)


def lap_length(players, gates=()):
    """Checkpoints per lap: from a lap someone has completed, else the track's lines."""
    done = next((len(p.checkpoints[0]) for p in players if len(p.checkpoints) > 1), 0)
    return done or len(gates)


def road_progress(player, gates):
    """How far `player` has come, in checkpoints: those it passed, plus its share of
    the way from the last line it passed to the next (from its position)."""
    count = len(player.passed)
    if not count or not gates or player.position is None:
        return float(count)
    last, after = _middle(gates[(count - 1) % len(gates)]), _middle(gates[count % len(gates)])
    dx, dz = after[0] - last[0], after[1] - last[1]
    length = dx * dx + dz * dz
    if length == 0:
        return float(count)
    px, pz = player.position[0] - last[0], player.position[1] - last[1]
    return count + min(max((px * dx + pz * dz) / length, 0.0), 0.999)


def backmarkers(order, me, ahead, gates, laps):
    """The cars in `order` (race order) that the local player `me` is about to lap and
    that are on the road between it and the next car ahead `ahead` (or within half a
    lap ahead when it leads): more than half a lap behind in the race, but ahead on the
    road. `laps` is the checkpoints per lap."""
    if laps < 2:
        return []
    mine = road_progress(me, gates)
    if ahead is not None:
        reach = (road_progress(ahead, gates) - mine) % laps
    else:
        reach = laps * LAPPING_SHARE
    found = []
    for player in order[order.index(me) + 1 :]:
        if player.finished or player.position is None:
            continue
        behind_by = mine - road_progress(player, gates)
        on_road = -behind_by % laps
        if behind_by > laps * LAPPING_SHARE and 0 < on_road < reach:
            found.append(player)
    return found


def driving_clean(player):
    """Whether the car drives the track: False with all four wheels off the tarmac (kerbs
    and a wheel in the air do not count), nearly standing or going backwards; True where
    that is not known."""
    grips = player.wheel_grips
    if grips is not None and all(0.0 < grip < CLEAN_GRIP for grip in grips):
        return False
    return player.forward_speed is None or player.forward_speed >= CLEAN_SPEED


class TrackPaths:
    """Every car's path as it drives: (checkpoints passed, (x, z)) whenever its
    position changes. A path starts afresh in the pits, when the car is put back on the
    track (a jump), when it leaves the track or stands (see driving_clean), or when its
    count goes back (a new race). Only the last lap is
    kept. `lap()` gives the first whole lap any car has driven."""

    def forget(self, name):
        """Start the car's path afresh (its lap was taken: the next one is a new lap)."""
        self.paths.pop(name, None)

    def __init__(self):
        self.paths = {}

    def add(self, players, laps):
        for player in players:
            if player.position is None or player.estimated or player.finished:
                continue
            if player.in_pit or not driving_clean(player):
                self.paths.pop(player.name, None)
                continue
            count, position = len(player.passed), player.position
            path = self.paths.setdefault(player.name, [])
            if path:
                last_count, last = path[-1]
                if position == last:
                    continue
                if count < last_count or math.dist(position, last) > JUMP:
                    path.clear()
            path.append((count, position))
            while laps and len(path) > 2 and path[-1][0] - path[1][0] > laps:
                path.pop(0)  # still more than a lap without the first point: not needed

    def lap(self, laps):
        """(the car's name, points, start index) of a whole lap driven by one car, or None. A car's
        path is a whole lap once it has passed one more line than a lap from where it
        begins (so it has surely come round past its first point); the lap ends at its
        point nearest the first, a lap on."""
        if laps < 2:
            return None
        for name, path in self.paths.items():
            first_count, first = path[0]
            if len(path) < 3 or path[-1][0] - first_count <= laps:
                continue
            ends = [i for i, (count, _p) in enumerate(path) if count == first_count + laps]
            if not ends:
                continue
            end = min(ends, key=lambda i: math.dist(path[i][1], first))
            points = [position for _count, position in path[:end]]
            start = next(
                (i for i in range(1, end) if path[i][0] != path[i - 1][0] and (path[i][0] - 1) % laps == 0),
                None,
            )
            return name, points, start
        return None

    def longest(self):
        """The longest path so far (points), for the map before a whole lap."""
        best = max(self.paths.values(), key=len, default=[])
        return [position for _count, position in best]


class TrackMap:
    """Gives the track map (a TrackMapView) for the race. The track is learnt from the
    cars' paths (TrackPaths) and saved in `folder` (None: not saved). `others`: the
    other cars show as faint grey dots."""

    def __init__(self, others=False, folder=None):
        self.others = others
        self.folder = Path(folder) if folder is not None else None
        self._gates = None
        self.learned = None  # the whole lap's TrackOutline, once known
        self.settled = False  # `learned` was chosen from LEARN_LAPS clean laps (an older file's may not be)
        self.paths = TrackPaths()
        self._partial = None  # (path length, TrackOutline) while no lap is known
        self._laps = []  # the clean laps so far: (car's name, points, start mark)

    def _file(self, gates):
        return self.folder / TRACKS_FOLDER / f'{track_key(gates)}.json' if self.folder else None

    def _load(self, gates):
        """(the saved outline or None, whether it was chosen from LEARN_LAPS clean laps)."""
        path = self._file(gates)
        if path is None:
            return None, False
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            points = [(float(x), float(z)) for x, z in data['points']]
            mark = data.get('start')
            start = ((float(mark[0]), float(mark[1])), (float(mark[2]), float(mark[3]))) if mark else None
            outline = outline_from_path(points, data.get('closed') is True, start)
            laps = data.get('laps', 1 if data.get('clean') is True else 0)
            settled = data.get('clean') is True and isinstance(laps, int) and laps >= LEARN_LAPS
        except (OSError, ValueError, KeyError, TypeError):
            return None, False
        if outline is not None:
            later = (
                '' if settled else f', from under {LEARN_LAPS} clean laps: learnt again from the next ones'
            )
            log.info('track map: learnt track loaded (%s)%s', path.name, later)
        return outline, settled

    def _save(self, gates, points, start, laps):
        path = self._file(gates)
        if path is None:
            return
        mark = [*start[0], *start[1]] if start else None
        data = {
            'points': [[round(x, 2), round(z, 2)] for x, z in points],
            'closed': True,
            'start': mark,
            'clean': True,
            'laps': laps,  # clean laps it was chosen from
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + '.tmp')
            temporary.write_text(json.dumps(data) + '\n', encoding='utf-8')
            os.replace(temporary, path)
            log.info('track map: track learnt from %d clean laps and saved (%s)', laps, path.name)
        except OSError as error:
            log.warning('track map: could not save the learnt track: %s', error)

    def road_ahead(self, position, other):
        """How far `other` is ahead of `position` along the learnt road, in game units (a
        lap, going forwards), or None while no whole lap is learnt."""
        if self.learned is None or not self.learned.closed or position is None or other is None:
            return None
        points = self.learned.points
        if len(points) < 3:
            return None
        if getattr(self, '_along_for', None) is not self.learned:
            total, along = 0.0, [0.0]
            for a, b in itertools.pairwise(points):
                total += math.dist(a, b)
                along.append(total)
            self._along_for, self._along = self.learned, (along, total + math.dist(points[-1], points[0]))
        along, lap = self._along

        def nearest(point):
            return min(range(len(points)), key=lambda i: math.dist(points[i], point))

        return (along[nearest(other)] - along[nearest(position)]) % lap

    def heading(self, position, hint=None):
        """(the way the race goes at `position`, a unit (x, z), and the learnt line's point
        nearest it) or None while no whole lap is learnt. The learnt line runs in the
        driving direction. `hint`: the point found last time for this car; only the
        points near it are searched then, unless it lies at the edge of that stretch."""
        if self.learned is None or not self.learned.closed or position is None:
            return None
        points = self.learned.points
        count = len(points)
        if count < 3:
            return None

        def nearest(indices):
            return min(indices, key=lambda i: math.dist(points[i], position))

        if hint is not None and 0 <= hint < count:
            span = range(hint - HEADING_SEARCH, hint + HEADING_SEARCH + 1)
            index = nearest(i % count for i in span)
            if (index - hint) % count in (HEADING_SEARCH, count - HEADING_SEARCH):
                index = nearest(range(count))  # at the edge: it moved far, look everywhere
        else:
            index = nearest(range(count))
        (x0, z0), (x1, z1) = points[index - 1], points[(index + 1) % count]
        direction = _unit(x1 - x0, z1 - z0)
        return (direction, index) if direction is not None else None

    @property
    def has_track(self):
        """Whether a track is known now (its checkpoint lines read), so it can be relearnt."""
        return bool(self._gates)

    def relearn(self):
        """Forget the current track's map, the saved one too, so the next clean lap any
        car drives learns it again (asked for by the user on 2026-11-11, for a map learnt
        wrong). False when no track is known."""
        if not self._gates:
            return False
        path = self._file(self._gates)
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError as error:
                log.warning('track map: could not delete the learnt track: %s', error)
        self.learned, self.settled = None, False
        self.paths, self._partial, self._laps = TrackPaths(), None, []
        log.info('track map: forgotten, learnt again from the next clean lap')
        return True

    def outline(self, players, gates, laps):
        """The outline to draw: the learnt lap, or the longest stretch driven so far."""
        if gates != self._gates:
            self._gates, self.paths, self._partial, self._laps = gates, TrackPaths(), None, []
            self.learned, self.settled = self._load(gates) if gates else (None, False)
        if self.learned is not None and self.settled:
            return self.learned
        self.paths.add(players, laps)
        lap = self.paths.lap(laps)
        if lap is not None:
            self._take(lap, gates)
        if self.learned is not None:
            return self.learned  # the best lap so far, or an older saved one until a lap is in
        longest = self.paths.longest()
        if self._partial is None or len(longest) != self._partial[0]:
            self._partial = (len(longest), outline_from_path(longest, False))
        return self._partial[1]

    def _take(self, lap, gates):
        """A clean lap is in: keep it (one a car, unless there are too few cars), show the
        best so far, and once there are LEARN_LAPS, keep the chosen one and save it."""
        name, points, index = lap
        self.paths.forget(name)  # its next lap is a lap of its own
        drivers = {driver for driver, _points, _start in self._laps}
        if name in drivers and len(drivers | set(self.paths.paths)) >= LEARN_LAPS:
            return  # enough other cars to give the other laps
        self._laps.append((name, points, start_mark(points, gates[0], index)))
        chosen = choose_lap([lap_points for _name, lap_points, _start in self._laps])
        _name, best, start = self._laps[chosen]
        outline = outline_from_path(best, True, start)
        if outline is None:
            return
        self.learned = outline
        if len(self._laps) >= LEARN_LAPS:
            self.settled = True
            self._save(gates, best, start, len(self._laps))
            self._laps = []

    def yellow_stretches(self, gates, sectors):
        """The stretches of the learnt road for `sectors`, each (first checkpoint, the
        next sector's first checkpoint) of a lap: the road between where it crosses those
        lines (asked for by the user on 2026-11-11: a sector under a yellow flag turns yellow on
        the map). () while no whole lap is learnt."""
        if not sectors or self.learned is None or not self.learned.closed or not gates:
            return ()
        points = self.learned.points
        key = (id(self.learned), gates)
        if getattr(self, '_marks_key', None) != key:
            self._marks_key, self._marks = key, gate_marks(points, gates)
        found = []
        for first, after in sorted(sectors):
            if 0 <= first < len(gates) and 0 <= after % len(gates) < len(gates):
                found.append(stretch(points, self._marks[first], self._marks[after % len(gates)]))
        return tuple(found)

    def update(self, state, order, yellow=frozenset(), yellow_sectors=()):
        """The view for the race `state` (LapState) with its players in race `order`,
        or None without a track, or without a local player unless spectating. The cars
        named in `yellow` are ringed, and shown even where other cars are not; the sectors
        in `yellow_sectors` (see yellow_stretches) turn yellow on the road."""
        order = list(order)
        me = next((p for p in order if p.local), None)
        if me is None and not state.spectating:
            return None
        outline = self.outline(order, state.gates, lap_length(order, state.gates))
        if outline is None:
            return None
        if me is None:
            # No car of the player's own to relate the others to: all cars, the leader on top.
            dots = [MapDot(p.position, 'car', p.in_pit) for p in order[1:] if p.position is not None]
            if order and order[0].position is not None:
                dots.append(MapDot(order[0].position, 'leader', order[0].in_pit))
            return TrackMapView(
                outline, tuple(dots), yellow=self.yellow_stretches(state.gates, yellow_sectors)
            )
        index = order.index(me)
        leader = order[0] if index > 0 else None
        ahead = order[index - 1] if index > 0 else None
        lapped = backmarkers(order, me, ahead, state.gates, lap_length(order, state.gates))
        # The next car behind that is not about to be lapped: a backmarker is ahead on
        # the road, even when it comes next in the race order.
        behind = next((p for p in order[index + 1 :] if p not in lapped), None)
        roles = {player.name: 'backmarker' for player in lapped}
        if behind is not None:
            roles[behind.name] = 'behind'
        if ahead is not None:
            roles[ahead.name] = 'ahead'
        if leader is not None:
            roles[leader.name] = 'leader'
        dots = []
        for role in ('other', 'backmarker', 'behind', 'ahead', 'leader'):
            for player in order:
                if player.local or player.position is None:
                    continue
                flagged = player.name in yellow
                if roles.get(player.name, 'other') != role or (
                    role == 'other' and not self.others and not flagged
                ):
                    continue
                ahead_too = role == 'leader' and ahead is not None and ahead.name == player.name
                dots.append(MapDot(player.position, role, player.in_pit, ahead_too, flagged))
        if me.position is not None:
            dots.append(MapDot(me.position, 'me', me.in_pit))
        return TrackMapView(outline, tuple(dots), yellow=self.yellow_stretches(state.gates, yellow_sectors))
