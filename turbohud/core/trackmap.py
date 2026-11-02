"""The track map: the track's shape from its checkpoint lines, and where the cars that
matter are on it.

TurboHUD already reads every checkpoint line of the track (both ends, about 120 a lap)
for the live delta. Their middles trace the track, so the map needs no track file and
works on every track, online too. The cars come from the race (LapState.players): their
positions where the game keeps them, else the worked-out ones (race.DeadReckoning), which
are close enough at a map's scale.

On the map: the local player, the race leader, the next car ahead and the next car
behind in the race order (the player list's, held steady while cars pass), and smaller
dots for backmarkers (cars the local player is about to lap) on the road between the
local player and the next car ahead (a backmarker is never the "next car behind", even
when it comes next in the race order: it is ahead on the road). The other cars are faint grey dots, if the player
turns them on.
"""

import itertools
import math
import statistics
from dataclasses import dataclass

SAME_LINE_SLANT = 0.2  # two lines this little apart in direction (sine of the angle) ...
SAME_LINE_OFFSET = 1.0  # ... and this close to each other's line (game units) are one
CLOSED_STEPS = 3.0  # first and last middle within this many usual steps: the track is a loop
SMOOTHING = 2  # rounds of corner cutting on the centre line
ROAD_PIXELS = (2.5, 0.06)  # the road's least width in pixels, and its most as a share of the map
LAPPING_SHARE = 0.5  # a car more than half a lap behind in the race and ahead on the road is a backmarker


@dataclass(frozen=True)
class TrackOutline:
    """The track for the map: its centre line (x, z) after smoothing, whether it is a
    loop, its usual width, its start line's two ends and its bounds (min x, min z, max
    x, max z)."""

    points: tuple
    closed: bool
    width: float
    start: tuple
    bounds: tuple


@dataclass(frozen=True)
class MapDot:
    """A car on the map. `role`: 'me', 'leader', 'ahead', 'behind', 'backmarker' or
    'other'. `ahead_too`: the leader is also the next car ahead."""

    position: tuple
    role: str
    in_pit: bool = False
    ahead_too: bool = False


@dataclass(frozen=True)
class TrackMapView:
    outline: TrackOutline
    dots: tuple  # MapDot, drawn in this order (the local player last, on top)


def _middle(gate):
    (x1, z1), (x2, z2) = gate
    return ((x1 + x2) / 2, (z1 + z2) / 2)


def _length(gate):
    (x1, z1), (x2, z2) = gate
    return math.hypot(x2 - x1, z2 - z1)


def _same_line(first, second):
    """Whether two checkpoint lines are one line: the same line twice (two checkpoints
    at the same spot), or one line in two pieces. Both lie along one straight line;
    two checkpoints one after another are parallel but apart."""
    (ax, az), (bx, bz) = first
    length = math.hypot(bx - ax, bz - az)
    other = _length(second)
    if length == 0 or other == 0:
        return length == other == 0 and _middle(first) == _middle(second)
    ux, uz = (bx - ax) / length, (bz - az) / length
    (cx, cz), (dx, dz) = second
    vx, vz = (dx - cx) / other, (dz - cz) / other
    if abs(ux * vz - uz * vx) > SAME_LINE_SLANT:
        return False
    mx, mz = _middle(second)
    return abs((mx - ax) * uz - (mz - az) * ux) <= SAME_LINE_OFFSET


def _span(first, second):
    """One line over both: the two ends farthest apart."""
    ends = [*first, *second]
    return max(
        ((a, b) for i, a in enumerate(ends) for b in ends[i + 1 :]),
        key=lambda pair: math.hypot(pair[1][0] - pair[0][0], pair[1][1] - pair[0][1]),
    )


def merged_gates(gates):
    """The checkpoint lines with each line that is one with the one before (see
    _same_line) joined into it, so the centre line does not zigzag."""
    merged = []
    for gate in gates:
        if merged and _same_line(merged[-1], gate):
            merged[-1] = _span(merged[-1], gate)
        else:
            merged.append(gate)
    return merged


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


def track_outline(gates):
    """The TrackOutline for checkpoint lines `gates` (race order, ((x1, z1), (x2, z2))
    each), or None with fewer than three distinct lines."""
    lines = merged_gates(gates)
    if len(lines) > 2 and _same_line(lines[-1], lines[0]):
        lines.pop()  # the last line is the start line again
    if len(lines) < 3:
        return None
    middles = [_middle(gate) for gate in lines]
    steps = [math.dist(a, b) for a, b in itertools.pairwise(middles)]
    usual = statistics.median(steps)
    closed = math.dist(middles[-1], middles[0]) <= CLOSED_STEPS * max(usual, 1e-9)
    points = tuple(smoothed(middles, closed))
    width = statistics.median(_length(gate) for gate in lines)
    xs, zs = [x for x, _z in points], [z for _x, z in points]
    return TrackOutline(points, closed, width, lines[0], (min(xs), min(zs), max(xs), max(zs)))


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


def road_width(outline, scale, map_size):
    """The road's width on the map in pixels: its usual width at `scale`, at least
    visible and at most a small share of the map."""
    least, most = ROAD_PIXELS
    return min(max(outline.width * scale, least), max(least, most * map_size))


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


class TrackMap:
    """Gives the track map (a TrackMapView) for the race: the outline is worked out
    once per track and kept. `others`: the other cars show as faint grey dots."""

    def __init__(self, others=False):
        self.others = others
        self._gates = None
        self._outline = None

    def outline(self, gates):
        if gates != self._gates:
            self._gates, self._outline = gates, track_outline(gates) if gates else None
        return self._outline

    def update(self, state, order):
        """The view for the race `state` (LapState) with its players in race `order`,
        or None without a track or a local player."""
        outline = self.outline(state.gates)
        order = list(order)
        me = next((p for p in order if p.local), None)
        if outline is None or me is None:
            return None
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
                if roles.get(player.name, 'other') != role or (role == 'other' and not self.others):
                    continue
                ahead_too = role == 'leader' and ahead is not None and ahead.name == player.name
                dots.append(MapDot(player.position, role, player.in_pit, ahead_too))
        if me.position is not None:
            dots.append(MapDot(me.position, 'me', me.in_pit))
        return TrackMapView(outline, tuple(dots))
