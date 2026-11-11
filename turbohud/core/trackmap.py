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
        """(points, start index) of a whole lap driven by one car, or None. A car's
        path is a whole lap once it has passed one more line than a lap from where it
        begins (so it has surely come round past its first point); the lap ends at its
        point nearest the first, a lap on."""
        if laps < 2:
            return None
        for path in self.paths.values():
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
            return points, start
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
        self.clean = False  # whether `learned` came from a clean lap (an older file may not have)
        self.paths = TrackPaths()
        self._partial = None  # (path length, TrackOutline) while no lap is known

    def _file(self, gates):
        return self.folder / TRACKS_FOLDER / f'{track_key(gates)}.json' if self.folder else None

    def _load(self, gates):
        """(the saved outline or None, whether it was learnt from a clean lap)."""
        path = self._file(gates)
        if path is None:
            return None, False
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            points = [(float(x), float(z)) for x, z in data['points']]
            mark = data.get('start')
            start = ((float(mark[0]), float(mark[1])), (float(mark[2]), float(mark[3]))) if mark else None
            outline = outline_from_path(points, data.get('closed') is True, start)
            clean = data.get('clean') is True
        except (OSError, ValueError, KeyError, TypeError):
            return None, False
        if outline is not None:
            later = '' if clean else ', from before clean laps: learnt again from the next one'
            log.info('track map: learnt track loaded (%s)%s', path.name, later)
        return outline, clean

    def _save(self, gates, points, start):
        path = self._file(gates)
        if path is None:
            return
        mark = [*start[0], *start[1]] if start else None
        data = {
            'points': [[round(x, 2), round(z, 2)] for x, z in points],
            'closed': True,
            'start': mark,
            'clean': True,
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + '.tmp')
            temporary.write_text(json.dumps(data) + '\n', encoding='utf-8')
            os.replace(temporary, path)
            log.info('track map: track learnt and saved (%s)', path.name)
        except OSError as error:
            log.warning('track map: could not save the learnt track: %s', error)

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
        self.learned, self.clean = None, False
        self.paths, self._partial = TrackPaths(), None
        log.info('track map: forgotten, learnt again from the next clean lap')
        return True

    def outline(self, players, gates, laps):
        """The outline to draw: the learnt lap, or the longest stretch driven so far."""
        if gates != self._gates:
            self._gates, self.paths, self._partial = gates, TrackPaths(), None
            self.learned, self.clean = self._load(gates) if gates else (None, False)
        if self.learned is not None and self.clean:
            return self.learned
        self.paths.add(players, laps)
        lap = self.paths.lap(laps)
        if lap is not None:
            points, index = lap
            start = start_mark(points, gates[0], index)
            learned = outline_from_path(points, True, start)
            if learned is not None:
                self.learned, self.clean = learned, True
                self._save(gates, points, start)
                return self.learned
        if self.learned is not None:
            return self.learned  # an older one, until a clean lap takes its place
        longest = self.paths.longest()
        if self._partial is None or len(longest) != self._partial[0]:
            self._partial = (len(longest), outline_from_path(longest, False))
        return self._partial[1]

    def update(self, state, order, yellow=frozenset()):
        """The view for the race `state` (LapState) with its players in race `order`,
        or None without a track, or without a local player unless spectating. The cars
        named in `yellow` are ringed, and shown even where other cars are not."""
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
            return TrackMapView(outline, tuple(dots))
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
        return TrackMapView(outline, tuple(dots))
