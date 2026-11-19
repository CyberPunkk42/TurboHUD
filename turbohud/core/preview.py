"""Move mode's preview: one moment of a made-up race at Laguna Seca, so every section shows
what it shows in a race while the player places it (asked for by the user on 2026-11-15).

The race is built as the live reader would read it (LapState, PlayerState, CarState) and goes
through race_sections like a real one, so each section looks exactly as it does in a race.
Its numbers come from a real race: WT Raceway Laguna Seca v1.0 with the Tatuus FA01, 20 drivers
over 15 laps (2026-11-14, from TSU's own results): each driver's best lap and race time, here
lap 10 of 15. The track is the map TurboHUD learnt from three clean laps there
(assets/preview/laguna_seca.json). Every name, clan tag and flag is made up: never a real
player's (AGENTS.md).
"""

import functools
import json
import math
from dataclasses import replace

from turbohud.core import race
from turbohud.core.battle import OVERTAKE
from turbohud.core.flags import FLAGS
from turbohud.core.hud import BANNER_TEXT, OVERTAKE_COLOUR, Row
from turbohud.core.trackmap import TrackMap, outline_from_path
from turbohud.core.watched import WATCHING

TRACK_NAME = 'WT Raceway Laguna Seca v1.0'
LAPS = 15
GATES = 30  # checkpoint lines, evenly along the lap
SECTOR_LINES = (10, 20)  # three sectors
GATE_HALF_WIDTH = 9.0  # metres either side of the road's middle
UNIT = race.UNITS_PER_SECOND
LOCAL = 5  # the player: P6 (index in the order below)
NOW_LAP = 10  # laps the leader has done: it has just begun lap 11, the player is on lap 10
LEADER_INTO = 2.5  # seconds into its lap: "Leader 11" shows after the player's lap and time left
TIME_LIMIT = 21 * 60  # seconds: the real race was 15 laps or 21 minutes

# The real race's results, without names: (race time in seconds, best lap in seconds, laps), in
# finishing order. The 19th lost about 40 s in the pits; the 20th was lapped twice.
RESULTS = (
    (1233.7065, 81.1634, 15),
    (1238.3962, 81.2190, 15),
    (1238.6097, 81.2844, 15),
    (1240.6518, 81.3845, 15),
    (1243.3959, 81.4240, 15),
    (1245.8959, 81.5692, 15),
    (1246.2386, 81.6493, 15),
    (1246.5267, 81.3982, 15),
    (1248.1904, 81.4193, 15),
    (1249.2703, 81.5890, 15),
    (1254.0747, 81.9475, 15),
    (1257.0025, 81.5443, 15),
    (1257.6468, 81.4183, 15),
    (1260.7913, 82.1001, 15),
    (1261.1290, 81.8385, 15),
    (1261.2839, 82.4651, 15),
    (1268.3546, 82.5638, 15),
    (1290.8706, 82.7218, 15),
    (1307.7802, 81.0582, 15),
    (1275.3227, 81.1540, 13),
)
# Made up, as are the tags; the flags are spread over the field.
NAMES = (
    'Mika Lindqvist',
    'Sofia Marques',
    'Jonas Brandt',
    'Ellie Hartwell',
    'Kenji Arata',
    'You',
    'Lucas Moreau',
    'Nora Vestby',
    'Pablo Ferrer',
    'Anja Kowalska',
    'Theo Visser',
    'Rafael Duarte',
    'Ida Holm',
    'Marco Bellini',
    'Liam Oconnell',
    'Hana Novak',
    'Oskar Berg',
    'Chloe Dubois',
    'Diego Alvarez',
    'Sam Whitlock',
)
# With the classes option on, a two-class race: these clan tags name the drivers' classes, so the
# standings come by class with the overall place, and the nearby cars show class and place in it.
CLASS_TAGS = tuple('GT3' if index < 12 else 'GT4' for index in range(20))
TAGS = (
    'APX',
    '',
    'VLT',
    'APX',
    '',
    '',
    'NRG',
    '',
    'VLT',
    '',
    'NRG',
    '',
    '',
    'APX',
    '',
    '',
    '',
    'NRG',
    '',
    '',
)
COUNTRIES = (
    'Finland',
    'Portugal',
    'Germany',
    'United_Kingdom',
    'Japan',
    'Netherlands',
    'France',
    'Norway',
    'Spain',
    'Poland',
    'Netherlands',
    'Brazil',
    'Sweden',
    'Italy',
    'Ireland',
    'Czech_Republic',
    'Sweden',
    'Belgium',
    'Argentina',
    'Canada',
)
COMPOUNDS = (1, 1, 0, 1, 1, 0, 1, 2, 1, 1, 0, 1, 2, 1, 1, 1, 0, 2, 0, 1)  # 0 soft, 1 medium, 2 hard
IN_PIT = 18  # the driver who lost time in the pits is in them now
# So that every kind of entry the standings can show is there, as their columns make room for them
# (asked for by the user on 2026-11-15): a car just out of the pits with its times, a shortcut
# penalty, and a car out of the race.
PITTED = 7  # out of the pits, close behind the player: PIT 24.6s for the stop, (8.20s) in the box
PITTED_TIMES = (24.6, 8.2)
CUT = 14  # slowed for a shortcut, with the seconds left
CUT_LEFT = 2.4
RETIRED = 19  # out of the race: DNF


class _Penalties:
    """Stands in for race.ShortcutPenalties: one car slowed for a shortcut."""

    def left(self, _state):
        return {NAMES[CUT]: CUT_LEFT}

    def jump_starts(self, _state):
        return frozenset()


class _Retired:
    """Stands in for race.Retirements: one car out of the race."""

    def update(self, _state):
        return frozenset({NAMES[RETIRED]})


def _flag(country):
    names = [name for name, _code in FLAGS]
    return names.index(country) if country in names else 0


@functools.cache
def track(folder=None):
    """(points, start mark) of the preview's track, from its asset file (`folder`: where the
    app's assets are; default the repository's)."""
    from pathlib import Path

    base = Path(folder) if folder else Path(__file__).resolve().parents[2] / 'assets'
    data = json.loads((base / 'preview' / 'laguna_seca.json').read_text(encoding='utf-8'))
    points = [(float(x), float(z)) for x, z in data['points']]
    x, z, dx, dz = data['start']
    # From the start line, in driving order.
    first = min(range(len(points)), key=lambda i: math.dist(points[i], (x, z)))
    points = points[first:] + points[:first]
    return tuple(points), ((x, z), (dx, dz))


class Lap:
    """Where on the lap a share of it is: the point, the way the road goes."""

    def __init__(self, points):
        self.points = points
        self.along = [0.0]
        for a, b in zip(points, points[1:] + points[:1]):
            self.along.append(self.along[-1] + math.dist(a, b))
        self.length = self.along[-1]

    def at(self, share):
        """((x, z), (dx, dz)) at `share` (0 to 1) of the lap."""
        goal = (share % 1.0) * self.length
        lo, hi = 0, len(self.points)
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.along[mid] <= goal:
                lo = mid
            else:
                hi = mid
        a, b = self.points[lo], self.points[(lo + 1) % len(self.points)]
        part = (goal - self.along[lo]) / max(self.along[lo + 1] - self.along[lo], 1e-9)
        point = (a[0] + (b[0] - a[0]) * part, a[1] + (b[1] - a[1]) * part)
        length = max(math.dist(a, b), 1e-9)
        return point, ((b[0] - a[0]) / length, (b[1] - a[1]) / length)

    def gate(self, share):
        """A checkpoint line across the road at `share` of the lap."""
        (x, z), (dx, dz) = self.at(share)
        nx, nz = -dz * GATE_HALF_WIDTH, dx * GATE_HALF_WIDTH
        return ((x - nx, z - nz), (x + nx, z + nz))


def _lap_times(index):
    """One driver's lap times in seconds: its average lap from the race time, a slow first
    lap from the grid, small changes lap to lap, and its best lap as in the real race."""
    total, best, laps = RESULTS[index]
    average = total / laps
    times = []
    for lap in range(laps):
        wobble = math.sin(1.7 * lap + index) * 0.35 + math.cos(0.9 * lap * (index + 1)) * 0.2
        times.append(average + wobble + (2.5 if lap == 0 else -0.18))
    times[3 + index % 5] = best  # its best lap, on an early lap
    if index == IN_PIT:
        times[NOW_LAP - 1] += 38.0  # the pit stop
    return times


def _driver(index, clock, lap, tags=TAGS):
    """A PlayerState for driver `index` at race clock `clock` (seconds)."""
    times = _lap_times(index)
    starts = [0.0]
    for seconds in times:
        starts.append(starts[-1] + seconds)
    done = max(i for i in range(len(starts)) if starts[i] <= clock)
    done = min(done, len(times))
    checkpoints = []
    for number in range(done + 1):
        began, length = starts[number], times[number] if number < len(times) else times[-1]
        passed = tuple(
            round((began + length * gate / GATES) * UNIT)
            for gate in range(GATES)
            if began + length * gate / GATES <= clock
        )
        checkpoints.append(passed)
    share = (clock - starts[done]) / times[min(done, len(times) - 1)]
    point, way = lap.at(share)
    speed = lap.length / times[min(done, len(times) - 1)]
    in_pit = index == IN_PIT
    if in_pit:
        speed *= 0.3
    return race.PlayerState(
        name=NAMES[index],
        flag=_flag(COUNTRIES[index]),
        laps_completed=done,
        checkpoints=tuple(checkpoints),
        in_pit=in_pit,
        local=index == LOCAL,
        position=point,
        velocity=(way[0] * speed, way[1] * speed),
        forward=way,
        forward_speed=speed,
        tag=tags[index],
        # Classes need cars of their own (race.car_classes): one car for all names no classes.
        car=f'{tags[index]} car' if tags is CLASS_TAGS else 'Tatuus FA01',
        compound=COMPOUNDS[index],
        in_box=in_pit,
        pit_seconds=PITTED_TIMES[0] if index == PITTED else None,
        pit_stopped=PITTED_TIMES[1] if index == PITTED else 0.0,
    )


DRAFTER_BEHIND = 12.0  # metres behind the player: the car drafting it (the draft section's big row)
DRAFTER_DRAG = 0.95  # its air resistance in the slipstream: 50 % of the event's most (-10 %)


def _with_drafter(players, local):
    """`players` with the car nearest behind the player put in its slipstream: DRAFTER_BEHIND
    metres back on its line, drafting, so the draft section shows who drafts you (2026-11-15)."""
    me = players[local]
    (x, z), (fx, fz) = me.position, me.forward

    def behind(player):
        return -((player.position[0] - x) * fx + (player.position[1] - z) * fz)

    near = [i for i, p in enumerate(players) if i != local and not p.in_pit and behind(p) > 0]
    if not near:
        return players
    index = min(near, key=lambda i: behind(players[i]))
    chaser = replace(
        players[index],
        position=(x - fx * DRAFTER_BEHIND, z - fz * DRAFTER_BEHIND),
        forward=me.forward,
        velocity=me.velocity,
        draft_drag=DRAFTER_DRAG,
    )
    return players[:index] + (chaser,) + players[index + 1 :]


def preview_state(folder=None, gear=True, classes=False):
    """The preview race's LapState: lap 10 of 15, the player 6th."""
    points, start = track(folder)
    lap = Lap(list(points))
    leader_times = _lap_times(0)
    clock = sum(leader_times[:NOW_LAP]) + LEADER_INTO
    tags = CLASS_TAGS if classes else TAGS
    players = tuple(_driver(index, clock, lap, tags) for index in range(len(RESULTS)))
    players = _with_drafter(players, LOCAL)
    me = players[LOCAL]
    my_times = _lap_times(LOCAL)
    lap_starts = [0]
    for seconds in my_times[: me.laps_completed]:
        lap_starts.append(lap_starts[-1] + round(seconds * UNIT))
    gates = tuple(lap.gate(gate / GATES) for gate in range(GATES))
    car = race.CarState(
        fuel_on=True,
        fuel_used=34_200,
        fuel_tank=90_000,
        tires_on=True,
        tire_wear=round(race.MAX_TIRE_WEAR * 0.38),
        speed=me.forward_speed,
        fuel_per_lap=5_650.0,
        wear_per_lap=race.MAX_TIRE_WEAR * 0.041,
        fuel_trend=-60.0,
        throttle=0.85,
        brake=0.0,
        health=0.78,
        downforce_from=0.8,
        slowed_from=0.4,
        draft=0.46,
        draft_downforce_loss=0.12,
        draft_last_lap=0.21,
        gear=5 if gear else None,  # read only with its option on (LapReader.read_gear)
        revs=0.72 if gear else None,
    )
    return race.LapState(
        clock=round(clock * UNIT),
        time_limit=round(TIME_LIMIT * UNIT),
        laps_completed=me.laps_completed,
        laps_to_finish=LAPS,
        lap_starts=lap_starts,
        checkpoints=me.checkpoints,
        position=me.position,
        gates=gates,
        sector_lines=SECTOR_LINES,
        car=car,
        players=players,
        draft=race.DraftSettings(0.12, 0.3, 30.0, 20.0),
        compounds=3,
        track=TRACK_NAME,
        cockpit=True,
    ), (points, start)


def preview_radar(classes=False, cone=True):
    """The radar with every kind of thing it can show (asked for by the user on 2026-11-15: one
    car behind, as the race had it, left most of it unseen): a car beside (red), one closing in
    behind (yellow), one ahead whose slipstream the player is in (with `cone`), one near but not
    counting, far to the side (grey), one further behind than the radar shows (an arrow at its
    bottom edge), and with `classes` one of the other class, in its colour with its warning
    round it. Ahead and side in metres from the player's car, its heading up."""
    blips = [
        race.Blip(-0.5, 3.2, 0.02, 0.0),  # beside, on the right
        race.Blip(-10.0, -1.4, 0.06, 0.32),  # closing in behind, on the left
        race.Blip(11.0, 0.6, -0.03, None, True if cone else None),  # ahead: you are in its slipstream
        race.Blip(5.0, 7.5, 0.0, None),  # near, but far to the side
        race.Blip(-27.0, 0.8, 0.0, 0.45),  # further behind than shown: an arrow at the edge
    ]
    if classes:
        gt4 = race.radar_class_colors({0: 'GT3', 1: 'GT4'})['GT4']
        blips.append(race.Blip(-4.5, -3.4, 0.0, 0.15, class_color=gt4))  # another class, close
    view = race.RADAR_VIEW
    return race.RadarView(1.0, tuple(blips), view, (30.0, 20.0) if cone else None)


@functools.cache
def preview_sections(
    folder=None,
    speed_unit='kmh',
    gear=True,
    sector_bars=True,
    clan_tags=True,
    columns=race.LAP_COLUMNS,
    radar_cone=True,
    classes=False,
    class_tags=(),
    nearby_short=False,
):
    """{section name: content} for move mode, as race_sections gives them in a race with the
    player's options, and the sections a calm moment leaves empty filled in: a yellow flag a
    sector ahead, a shortcut penalty, and the blue flag."""
    classes = classes and {'GT3', 'GT4'} <= set(class_tags)
    state, (points, start) = preview_state(folder, gear, classes)
    snapshot = race.Snapshot(race.RACING, state, True, 1.0, moved_at=1.0)
    track_map = TrackMap()
    track_map._gates = state.gates
    track_map.learned = outline_from_path(list(points), True, start)
    track_map.settled = True
    radar = race.Radar()
    delta_bar = race.DeltaBar()
    radar.within, radar.cone = race.RADAR_FROM, radar_cone
    options = {
        'delta_bar': delta_bar,
        'sector_bars': sector_bars,
        'clan_tags': clan_tags,
        'class_tags': tuple(class_tags) if classes else (),
        'columns': tuple(columns),
        'shortcuts': _Penalties(),
        'retirements': _Retired(),
        'nearby_short': nearby_short,
    }
    # Twice, as the radar and the delta bar follow the cars from one read to the next.
    race.race_sections(snapshot, 1.0, speed_unit, race.Standings(), radar, track_map, **options)
    later = replace(snapshot, read_at=1.1)
    sections = race.race_sections(later, 1.1, speed_unit, race.Standings(), radar, track_map, **options)
    if not sections.get('yellowflag'):
        sections['yellowflag'] = [
            Row('YELLOW  -  Sector 2', 'title', '#111111', centred=True),
            Row(f'S2  {NAMES[12]}  off track', 'small', '#111111'),
            Row(f'S2  {NAMES[13]}  respawned', 'small', '#111111'),
        ]
    if not sections.get('shortcut'):
        sections['shortcut'] = race.shortcut_rows(state, {NAMES[LOCAL]: 2.4})
    if not sections.get('leader'):
        sections['leader'] = [Row(f'New Race Leader  -  {NAMES[0]}', 'title', BANNER_TEXT, centred=True)]
    if not sections.get('battle'):
        sections['battle'] = [
            Row('Battle for P2', 'title', BANNER_TEXT, centred=True),
            Row(OVERTAKE, 'title', OVERTAKE_COLOUR, centred=True),
            Row(f'{NAMES[1]}  vs  {NAMES[2]}', 'title', BANNER_TEXT, centred=True),
        ]
    if not sections.get('watched'):
        sections['watched'] = [
            Row(WATCHING, 'title', OVERTAKE_COLOUR, centred=True),
            Row(f'P{LOCAL + 1}  {NAMES[LOCAL]}', 'title', BANNER_TEXT, centred=True),
        ]
    sections.setdefault('blue', 1.0)
    sections['radar'] = preview_radar(classes, radar_cone)
    return sections
