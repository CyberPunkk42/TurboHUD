import dataclasses
import itertools
import struct
import sys
import time
import unittest
from pathlib import Path
from typing import ClassVar
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbohud.core import il2cpp as il
from turbohud.core import race

HEAP = (0x1000_0000, 0x1010_0000)
MANAGED = (0x7F00_0000_0000, 0x7F00_0010_0000)
METADATA_BASE = 0x7F10_0000_0000


class FakeGame:
    """A tiny IL2CPP-shaped memory: metadata strings, class and field records, objects."""

    def __init__(self):
        self.mem = {}
        self.strings = b'\0'
        self.heap_next = HEAP[0]
        self.obj_next = MANAGED[0]
        self.static_type = self.alloc_heap(16)
        self.put(self.static_type + il.TYPE_ATTRS, struct.pack('<H', il.FIELD_ATTRIBUTE_STATIC))
        self.instance_type = self.alloc_heap(16)
        self.put(self.instance_type + il.TYPE_ATTRS, struct.pack('<H', 0))
        self.typed = {}
        for code in (0x02, 0x05, 0x08, 0x0C, 0x11, 0x12):  # bool, byte, int, float, enum, class
            record = self.alloc_heap(16)
            self.put(record + il.TYPE_ATTRS, struct.pack('<HB', 0, code))
            self.typed[code] = record

    def string(self, text):
        index = self.strings.find(b'\0' + text.encode() + b'\0')
        if index < 0:
            index = len(self.strings) - 1
            self.strings += text.encode() + b'\0'
        return METADATA_BASE + index + 1

    def put(self, address, data):
        for i, byte in enumerate(data):
            self.mem[address + i] = byte

    def q(self, address, value):
        self.put(address, struct.pack('<Q', value))

    def alloc_heap(self, size):
        address = self.heap_next
        self.heap_next += (size + 15) & ~15
        return address

    def alloc_obj(self, klass, size=0x100):
        address = self.obj_next
        self.obj_next += size
        self.q(address, klass)
        return address

    def klass(self, namespace, name, fields, statics=None, parent=0):
        klass = self.alloc_heap(0x100)
        self.q(klass + il.CLASS_NAME, self.string(name))
        self.q(klass + il.CLASS_NAMESPACE, self.string(namespace))
        self.q(klass + il.CLASS_PARENT, parent)
        entries = self.alloc_heap(il.FIELD_INFO_SIZE * (len(fields) + 1))
        self.q(klass + il.CLASS_FIELDS, entries)
        for i, (field_name, offset, is_static, *code) in enumerate(fields):
            entry = entries + il.FIELD_INFO_SIZE * i
            self.q(entry, self.string(field_name))
            self.q(
                entry + 8,
                self.static_type if is_static else self.typed[code[0]] if code else self.instance_type,
            )
            self.q(entry + 16, klass)
            self.put(entry + 24, struct.pack('<iI', offset, 0x04000001))
        if statics is not None:
            self.q(klass + il.CLASS_STATIC_FIELDS, statics)
        return klass

    def list_of(self, values, element_size=8):
        array = self.alloc_obj(0, 0x20 + element_size * max(len(values), 1) + 16)
        for i, value in enumerate(values):
            fmt = '<Q' if element_size == 8 else '<I'
            self.put(array + il.ARRAY_DATA + element_size * i, struct.pack(fmt, value))
        lst = self.alloc_obj(self.list_class)
        self.q(lst + il.LIST_ITEMS, array)
        self.put(lst + il.LIST_SIZE, struct.pack('<i', len(values)))
        return lst

    def read(self, address, size):
        if METADATA_BASE <= address < METADATA_BASE + len(self.strings):
            start = address - METADATA_BASE
            return self.strings[start : start + size].ljust(size, b'\0')
        if address not in self.mem and not (HEAP[0] <= address < HEAP[1]):
            raise OSError(14, 'Bad address')
        return bytes(self.mem.get(address + i, 0) for i in range(size))

    def find_pointers(self, value):
        self.searches = getattr(self, 'searches', 0) + 1
        pattern = struct.pack('<Q', value)
        return sorted(a for a in self.mem if a % 8 == 0 and self.read(a, 8) == pattern)

    def memory(self):
        regions = [(*HEAP, 'rw-p', 0, '[heap]'), (*MANAGED, 'rw-p', 0, '')]
        return il.Memory(self.read, regions, find_pointers=self.find_pointers)


def build(
    lap_starts,
    laps_completed,
    clock,
    limit,
    local_index=0,
    finished=False,
    car=None,
    gates=(),
    pedals=None,
    name=None,
    online=False,
    clock_fn=None,
    health=None,
    pit_area=False,
    event_running=None,
    recorded=None,
    draft=False,
    tire_ticks=0,
    event_type=None,
    gate_types=None,
    surfaces=None,
    compounds=None,
    track=None,
    replay=None,
    recording_opened=None,
    hotlapping=None,
    in_box=None,
    camera=None,
):
    """A fake race; `car` is the car's (x, z) and `gates` the checkpoint lines, both
    optional like in a game without them."""
    g = FakeGame()
    g.list_class = g.klass('System.Collections.Generic', 'List`1', [])
    statics = g.alloc_heap(16)
    services_class = g.klass(
        'TS', 'Services', [('sm_instance', 0, True), ('m_activeServer', 0x10, False)], statics
    )
    server_class = g.klass('TS', 'Server', [('m_eventListener', 0x18, False)])
    base_controller = g.klass(
        'TS', 'EventController', [('m_audio', 0x10, False), ('m_eventState', 0x48, False)]
    )
    controller_class = g.klass(
        'TS',
        'HostEventController',
        [('m_server', 0x60, False), ('m_eventLogic', 0x70, False)],
        parent=base_controller,
    )
    state_class = g.klass(
        'TS',
        'EventState',
        [
            ('players', 0x28, False),
            ('times', 0x58, False),
            ('m_level', 0x80, False),
            ('m_eventStats', 0x90, False),
        ],
    )
    player_fields = [('m_stats', 0x30, False), ('m_localHumanIndex', 0x50, False)]
    if name is not None:
        player_fields.append(('m_playerInfo', 0x40, False))
    if car is not None:
        player_fields += [('m_vehicle', 0x20, False), ('m_statsUpdater', 0x38, False)]
    player_class = g.klass('TS', 'EventPlayer', player_fields)
    stats_class = g.klass(
        'TS',
        'PlayerRaceStats',
        [
            ('m_checkpointTimesForLaps', 0x18, False),
            ('m_lapsToFinish', 0x28, False),
            ('m_finished', 0x31, False),
            ('m_lapsCompleted', 0x32, False),
        ],
    )
    times_class = g.klass('TS', 'CheckpointTimes', [('m_times', 0x10, False)])

    services = g.alloc_obj(services_class)
    g.q(statics, services)
    server = g.alloc_obj(server_class)
    g.q(services + 0x10, server)
    controller = g.alloc_obj(controller_class)
    g.q(server + 0x18, controller)
    if online:
        # An online race: no active server; the race is in a TS.ClientEventController.
        g.q(services + 0x10, 0)
        client_class = g.klass(
            'TS',
            'ClientEventController',
            [('m_client', 0x60, False), ('m_eventRecorder', 0x68, False)],
            parent=base_controller,
        )
        g.alloc_obj(client_class)  # a stale one, of an earlier race: no event state
        controller = g.alloc_obj(client_class)
        g.client_controller = controller
        if recorded is not None:
            # The replay recorder: one quantized state per player, in the list's order
            # (here the remote player first, then the local one).
            recorder_class = g.klass(
                'TS',
                'EventRecorder',
                [('m_stateTick', 0x10, False), ('m_lastQuantizedVehicleStates', 0x18, False)],
            )
            state_class_q = g.klass('TS', 'QuantizedVehicleState', [('m_positionX', 0x10, False)])
            recorder = g.alloc_obj(recorder_class)
            g.put(recorder + 0x10, struct.pack('<i', 100))
            array = g.alloc_obj(0)
            g.q(array + il.ARRAY_LENGTH, 2)
            for i, place in enumerate((None, recorded)):
                element = g.alloc_obj(state_class_q)
                if place is not None:
                    x, z = place
                    g.put(
                        element + 0x10,
                        struct.pack('<3I', int(x * 1024) + 2**20, 2**20, int(z * 1024) + 2**20),
                    )
                g.q(array + il.ARRAY_DATA + 8 * i, element)
            g.q(recorder + 0x18, array)
            g.q(controller + 0x68, recorder)
            g.recorder = recorder
    state = g.alloc_obj(state_class)
    g.q(controller + 0x48, state)
    if camera is not None:  # (cameraPosition, distance): controller.m_audio.m_raceCameras.m_cameras[0] ...
        position, distance = camera
        audio = g.alloc_obj(g.klass('TS', 'Audio', [('m_raceCameras', 0x88, False)]))
        cameras = g.alloc_obj(g.klass('TS', 'RaceCameras', [('m_cameras', 0x10, False)]))
        race_camera = g.alloc_obj(
            g.klass('TS', 'RaceCamera', [('m_cameraPropertiesUpdater', 0x100, False)]), 0x110
        )
        updater_c = g.alloc_obj(g.klass('TS', 'CameraPropertiesUpdater', [('m_properties', 0x18, False)]))
        properties = g.alloc_obj(
            g.klass(
                'TS',
                'RaceCameraProperties',
                [('cameraPosition', 0x10, False, 0x11), ('distance', 0x1C, False, 0x0C)],
            )
        )
        g.put(properties + 0x10, struct.pack('<i', position))
        g.put(properties + 0x1C, struct.pack('<f', distance))
        g.q(updater_c + 0x18, properties)
        g.q(race_camera + 0x100, updater_c)
        g.q(cameras + 0x10, g.list_of([race_camera]))
        g.q(audio + 0x88, cameras)
        g.q(controller + 0x10, audio)
    if hotlapping is not None:  # EventState.m_eventStats.raceStats.m_hotlappingOnCircuit
        stats = g.alloc_obj(g.klass('TS', 'EventStats', [('raceStats', 0x30, False)]))
        race_stats = g.alloc_obj(g.klass('TS', 'RaceStats', [('m_hotlappingOnCircuit', 0x3C, False)]))
        g.put(race_stats + 0x3C, bytes([hotlapping]))
        g.q(stats + 0x30, race_stats)
        g.q(state + 0x90, stats)
    if track is not None:  # the track's name: EventState.m_level.m_properties.name
        level = g.alloc_obj(g.klass('TS', 'Level', [('m_properties', 0x10, False)]))
        level_properties = g.alloc_obj(g.klass('TS', 'LevelProperties', [('name', 0x18, False)]))
        text = g.alloc_obj(0, 0x14 + 2 * len(track) + 2)
        g.put(text + 0x10, struct.pack('<i', len(track)) + track.encode('utf-16-le'))
        g.q(level_properties + 0x18, text)
        g.q(level + 0x10, level_properties)
        g.q(state + 0x80, level)
    if draft or event_type is not None:
        logic = g.alloc_obj(g.klass('TS', 'RaceLogic', [('m_eventSettings', 0x10, False)]))
        settings_fields = [('drafting', 0x10, False)]
        if event_type is not None:
            # (mode class name, level type): the mode an object, as in TSU (seen 2026-11-08).
            mode_name, level_type = event_type
            settings_fields.append(('m_eventMode', 0x18, False, 0x12))
            settings_fields.append(('m_initializedLevelType', 0x20, False, 0x11))
        settings = g.alloc_obj(g.klass('TS', 'EventSettings', settings_fields))
        if event_type is not None:
            mode = g.alloc_obj(g.klass('TS', mode_name, [('m_goal', 0x10, False, 0x08)]))
            g.q(settings + 0x18, mode)
            g.put(settings + 0x20, struct.pack('<i', level_type))
        g.q(logic + 0x10, settings)
        g.q(controller + 0x70, logic)
    if draft:
        drafting = g.alloc_obj(
            g.klass(
                'TS',
                'DraftingSettings',
                [
                    ('draftingOn', 0x10, False, 0x02),
                    ('draftingSpeedEffect', 0x14, False, 0x08),
                    ('draftingDownforceReduction', 0x18, False, 0x08),
                ],
            )
        )
        g.put(drafting + 0x10, bytes([1]) + bytes(3) + struct.pack('<2i', 10, 80))
        g.q(settings + 0x10, drafting)
    g.put(state + 0x58, struct.pack('<6i', clock // 200, clock, 10000, 10000, 10000, limit))

    stats = g.alloc_obj(stats_class)
    laps = []
    for start in lap_starts:
        entry = g.alloc_obj(times_class)
        g.q(entry + 0x10, g.list_of([start, start, start + 5000], element_size=4))
        laps.append(entry)
    g.q(stats + 0x18, g.list_of(laps))
    g.put(stats + 0x28, struct.pack('<H', 13))
    g.put(stats + 0x31, bytes([finished]))
    g.put(stats + 0x32, struct.pack('<H', laps_completed))

    remote = g.alloc_obj(player_class)
    g.put(remote + 0x50, struct.pack('<i', -1))
    local = g.alloc_obj(player_class)
    g.put(local + 0x50, struct.pack('<i', local_index))
    g.q(local + 0x30, stats)
    g.q(state + 0x28, g.list_of([remote, local]))
    if replay is not None:
        # A replay (`replay`: paused or not): no active server and nobody driving; the race is
        # under a TS.EventRecordingPlayer, its camera following the local car's player.
        g.q(services + 0x10, 0)
        g.put(local + 0x50, struct.pack('<i', -1))
        g.klass('TS', 'ClientEventController', [('m_client', 0x60, False)], parent=base_controller)
        replay_controller = g.alloc_obj(
            g.klass('TS', 'EventRecordingController', [('m_recording', 0x60, False)], parent=base_controller)
        )
        g.q(replay_controller + 0x48, state)
        runner = g.alloc_obj(
            g.klass(
                'TS',
                'EventRunner',
                [
                    ('m_eventController', 0x10, False),
                    ('m_state', 0x18, False),
                    ('m_raceCameras', 0x20, False),
                ],
            )
        )
        g.q(runner + 0x10, replay_controller)
        g.q(runner + 0x18, state)
        chooser = g.alloc_obj(g.klass('TS', 'TargetChooser', [('m_target', 0x10, False)]))
        g.q(chooser + 0x10, local)
        camera = g.alloc_obj(g.klass('TS', 'RaceCamera', [('m_targetChooser', 0x10, False)]))
        g.q(camera + 0x10, chooser)
        cameras = g.alloc_obj(g.klass('TS', 'RaceCameras', [('m_cameras', 0x10, False)]))
        g.q(cameras + 0x10, g.list_of([camera]))
        g.q(runner + 0x20, cameras)
        recording = g.alloc_obj(
            g.klass(
                'TS',
                'EventRecording',
                [('m_currentTick', 0x10, False), ('m_lastQuantizedVehicleStates', 0x18, False)],
            )
        )
        g.put(recording + 0x10, struct.pack('<i', 100))
        g.q(recording + 0x18, 0)
        player_class_r = g.klass(
            'TS',
            'EventRecordingPlayer',
            [
                ('m_recording', 0x10, False),
                ('m_eventRunner', 0x18, False),
                ('m_paused', 0x20, False, 0x02),
                ('m_exiting', 0x21, False, 0x02),
            ],
        )
        g.alloc_obj(player_class_r)  # one of an earlier replay: nothing filled in
        replay_player = g.alloc_obj(player_class_r)
        g.q(replay_player + 0x10, recording)
        g.q(replay_player + 0x18, runner)
        g.put(replay_player + 0x20, bytes([replay == 'paused', 0]))
        g.replay_player, g.chooser = replay_player, chooser
        g.replay_state_times = state + 0x58  # where the fake keeps the race clock's times
    if name is not None:
        info = g.alloc_obj(g.klass('TS', 'EventPlayerInfo', [('m_profile', 0x10, False)]))
        profile = g.alloc_obj(
            g.klass(
                'TS',
                'PlayerProfile',
                [('m_name', 0x10, False), ('flag', 0x40, False), ('teamTag', 0x48, False)],
            )
        )
        text = g.alloc_obj(0, 0x14 + 2 * len(name) + 2)
        g.put(text + 0x10, struct.pack('<i', len(name)) + name.encode('utf-16-le'))
        g.q(profile + 0x10, text)
        tag = g.alloc_obj(0, 0x14 + 2 * 3 + 2)
        g.put(tag + 0x10, struct.pack('<i', 3) + 'GT3'.encode('utf-16-le'))
        g.q(profile + 0x48, tag)
        g.put(profile + 0x40, struct.pack('<i', 75))  # Germany
        g.q(info + 0x10, profile)
        g.q(local + 0x40, info)
        g.q(remote + 0x40, 0)
    if car is not None:
        vehicle = g.alloc_obj(
            g.klass(
                'TS',
                'Vehicle',
                [
                    ('m_state', 0x30, False),
                    ('m_stateUpdater', 0x38, False),
                    ('m_statsNewPosition', 0x64, False),
                    ('m_vehicleModel', 0x70, False),
                ],
            )
        )
        g.put(vehicle + 0x64, struct.pack('<3f', car[0], 10.0, car[1]))
        model = g.alloc_obj(g.klass('TS', 'VehicleModel', [('m_properties', 0x18, False)]))
        properties = g.alloc_obj(g.klass('TS', 'VehicleProperties', [('name', 0x20, False)]))
        car_name = 'Ligier JS320'
        text = g.alloc_obj(0, 0x14 + 2 * len(car_name) + 2)
        g.put(text + 0x10, struct.pack('<i', len(car_name)) + car_name.encode('utf-16-le'))
        g.q(properties + 0x20, text)
        g.q(model + 0x18, properties)
        g.q(vehicle + 0x70, model)
        state = g.alloc_obj(
            g.klass(
                'TS',
                'VehicleState',
                [
                    ('fuelConsumption', 0x40, False),
                    ('tireWear', 0x48, False),
                    ('maxHitPoints', 0x50, False, 0x08),
                    ('hitPoints', 0x54, False, 0x08),
                    ('inPitArea', 0x58, False, 0x02),
                    ('tireCompoundAndChangeTicks', 0x5C, False, 0x08),
                ],
            )
        )
        g.put(state + 0x40, struct.pack('<i', 42_000))
        g.put(state + 0x5C, struct.pack('<i', tire_ticks))
        g.put(state + 0x50, struct.pack('<ii', 500, health if health is not None else 500))
        g.put(state + 0x58, bytes([pit_area]))
        g.put(state + 0x48, struct.pack('<i', 576_000))
        g.q(vehicle + 0x30, state)
        updater = g.alloc_obj(
            g.klass(
                'TS',
                'CarStateUpdater',
                [
                    ('m_fuelSettings', 0x18, False),
                    ('m_controls', 0x28, False),
                    ('m_fuelEnabled', 0x50, False),
                    ('m_tireWearEnabled', 0x51, False),
                    ('m_forwardSpeed', 0x60, False),
                    ('m_gradualDamageEnabled', 0x70, False, 0x02),
                    ('m_hitPointsToRelativeHealthMultiplierForDownforceLoss', 0x74, False, 0x0C),
                    ('m_hitPointsToRelativeHealthMultiplierForAcceleration', 0x78, False, 0x0C),
                    ('m_draftingViscosityFactor', 0x7C, False, 0x0C),
                    ('m_draftingDownforceFactor', 0x80, False, 0x0C),
                    ('wheels', 0x88, False),
                    ('m_eventSettings', 0x90, False),
                    *([('inPit', 0x98, False, 0x02)] if in_box is not None else []),
                ],
            )
        )
        if in_box is not None:  # CarStateUpdater.inPit: on a pit box
            g.put(updater + 0x98, bytes([in_box]))
        g.q(updater + 0x88, 0)  # no wheels object unless surfaces are given
        g.q(updater + 0x90, 0)  # no event settings unless the compounds are given
        if compounds is not None:  # the event's number of tire compounds
            event_settings = g.alloc_obj(g.klass('TS', 'EventSettings', [('tireWear', 0x10, False)]))
            tire_settings = g.alloc_obj(
                g.klass('TS', 'TireWearSettings', [('tireCompoundCount', 0x10, False, 0x05)])
            )
            g.put(tire_settings + 0x10, bytes([compounds]))
            g.q(event_settings + 0x10, tire_settings)
            g.q(updater + 0x90, event_settings)
        if surfaces is not None:  # (grip, layer) under each of the four wheels; None: in the air
            wheels = g.alloc_obj(
                g.klass(
                    'TS',
                    'WheelUpdater',
                    [(name, 0x10 + 8 * i, False) for i, name in enumerate(race.WHEEL_SURFACES)],
                )
            )
            material_class = g.klass(
                'TS', 'TSMaterialProperties', [('m_layer', 0x10, False, 0x08), ('grip', 0x1C, False, 0x0C)]
            )
            for i, surface in enumerate(surfaces):
                material = 0
                if surface is not None:
                    material = g.alloc_obj(material_class)
                    g.put(material + 0x10, struct.pack('<i', surface[1]))
                    g.put(material + 0x1C, struct.pack('<f', surface[0]))
                g.q(wheels + 0x10 + 8 * i, material)
            g.q(updater + 0x88, wheels)
        g.put(updater + 0x7C, struct.pack('<2f', 0.927, 0.416))
        g.put(updater + 0x70, bytes([health is not None]))
        g.put(updater + 0x74, struct.pack('<2f', 1 / 450, 1 / 375))
        g.put(updater + 0x50, bytes([1, 1]))
        g.q(updater + 0x28, 0)  # no controls object unless given
        if pedals is not None:
            if all(isinstance(value, float) for value in pedals):
                controls_class = g.klass(
                    'TS', 'CarControls', [('gas', 0x10, False, 0x0C), ('brake', 0x14, False, 0x0C)]
                )
                fmt = '<2f'
            else:
                controls_class = g.klass(
                    'TS',
                    'CarControls',
                    [
                        ('gasInThirds', 0x18, False, 0x08),
                        ('gas', 0x10, False, 0x08),
                        ('brakeInThirds', 0x1C, False, 0x08),
                        ('brake', 0x14, False, 0x08),
                    ],
                )
                fmt = '<2i'
            controls = g.alloc_obj(controls_class)
            g.put(controls + 0x10, struct.pack(fmt, *pedals))
            if fmt == '<2i':
                g.put(controls + 0x18, struct.pack('<2i', *pedals))
            g.q(updater + 0x28, controls)
        g.put(updater + 0x60, struct.pack('<f', 50.0))
        g.q(vehicle + 0x38, updater)
        fuel = g.alloc_obj(g.klass('TS', 'FuelSettings', [('maxFuelConsumptionInEvent', 0x14, False)]))
        g.put(fuel + 0x14, struct.pack('<i', 168_000))
        g.q(updater + 0x18, fuel)
        g.q(local + 0x20, vehicle)
        updater = g.alloc_obj(g.klass('TS', 'PlayerRaceStatsUpdater', [('m_checkpoints', 0x18, False)]))
        g.q(local + 0x38, updater)
        track = g.alloc_obj(g.klass('TS', 'Checkpoints', [('m_checkpoints', 0x10, False)]))
        g.q(updater + 0x18, track)
        point_class = g.klass('TS', 'Checkpoint', [('m_properties', 0x20, False)])
        fields = [('position1', 0x10, False), ('position2', 0x1C, False)]
        if gate_types is not None:  # TS.CheckpointType, one byte: 0 Sector, 1 Normal, 2 Minor
            fields.append(('type', 0x28, False))
        properties_class = g.klass('TS', 'CheckpointProperties', fields)
        items = []
        for number, ((x1, z1), (x2, z2)) in enumerate(gates):
            properties = g.alloc_obj(properties_class)
            g.put(properties + 0x10, struct.pack('<6f', x1, 0.0, z1, x2, 0.0, z2))
            if gate_types is not None:
                g.put(properties + 0x28, bytes([gate_types[number]]))
            checkpoint = g.alloc_obj(point_class)
            g.q(checkpoint + 0x20, properties)
            items.append(checkpoint)
        g.q(track + 0x10, g.list_of(items))
    g.laps = laps

    runtime = il.Il2Cpp(g.memory(), g.strings, METADATA_BASE)
    reader = race.LapReader(
        runtime,
        clock=clock_fn or time.monotonic,
        event_running=event_running,
        recording_opened=recording_opened,
    )
    reader.game = g
    return reader


class LapStateTests(unittest.TestCase):
    def test_times_from_lap_starts(self):
        state = race.LapState(
            clock=2_000_000,
            time_limit=12_610_000,
            laps_completed=2,
            laps_to_finish=13,
            lap_starts=[10_000, 944_595, 1_785_545],
        )
        self.assertEqual(state.lap_times, [934_595, 840_950])
        self.assertEqual(state.last_lap, 840_950)
        self.assertEqual(state.best_lap, 840_950)
        self.assertEqual(state.current_lap, 2_000_000 - 1_785_545)
        self.assertEqual(state.time_left, 10_610_000)

    def test_before_the_first_lap_is_done(self):
        state = race.LapState(
            clock=50_000, time_limit=0, laps_completed=0, laps_to_finish=13, lap_starts=[10_000]
        )
        self.assertEqual(state.lap_times, [])
        self.assertIsNone(state.last_lap)
        self.assertIsNone(state.best_lap)
        self.assertIsNone(state.time_left)
        self.assertEqual(state.current_lap, 40_000)

    def test_an_unfinished_lap_is_not_a_lap_time(self):
        # After the finish TSU may already hold the next lap's start; laps_completed caps it.
        state = race.LapState(
            clock=0, time_limit=0, laps_completed=1, laps_to_finish=1, lap_starts=[0, 900_000, 950_000]
        )
        self.assertEqual(state.lap_times, [900_000])

    def test_format_time(self):
        self.assertEqual(race.format_time(996_479), '1:39.648')
        self.assertEqual(race.format_time(84_950), '0:08.495')
        self.assertEqual(race.format_time(-5_000), '-0:00.500')
        self.assertEqual(race.format_time(None), '-')


class ReaderTests(unittest.TestCase):
    def test_follows_the_chain_by_name_to_the_local_player(self):
        reader = build([10_000, 944_595, 1_785_545], laps_completed=2, clock=2_000_000, limit=12_610_000)
        state = reader.read()
        self.assertEqual(state.lap_starts, [10_000, 944_595, 1_785_545])
        self.assertEqual(state.laps_completed, 2)
        self.assertEqual(state.laps_to_finish, 13)
        self.assertEqual(state.clock, 2_000_000)
        self.assertEqual(state.time_limit, 12_610_000)

    def test_finished_flag(self):
        self.assertFalse(build([10_000], laps_completed=0, clock=20_000, limit=0).read().finished)
        self.assertTrue(
            build([10_000], laps_completed=0, clock=20_000, limit=0, finished=True).read().finished
        )

    def test_fields_of_a_parent_class_are_found(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        self.assertEqual(reader.read().current_lap, 10_000)

    def test_no_local_player_is_reported(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0, local_index=-1)
        with self.assertRaises(il.NotFound):
            reader.local_player()

    def test_a_race_without_a_local_player_is_watched(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0, local_index=-1)
        self.assertTrue(reader.read().spectating)

    def test_field_list_gives_names_offsets_and_types(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        runtime = reader.il
        _state, player = reader.local_player()
        stats = runtime.ref(player, 'm_stats')
        listed = {
            name: (offset, static)
            for name, offset, static, _code in runtime.field_list(runtime.memory.u64(stats))
        }
        self.assertEqual(listed['m_lapsCompleted'], (0x32, False))
        self.assertEqual(runtime.class_name(stats), 'TS.PlayerRaceStats')

    def test_fields_of_a_class_the_game_has_not_set_up_are_not_kept(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        g, runtime = reader.game, reader.il
        parent = g.klass('TS', 'Base', [('m_base', 0x10, False)])
        child = g.klass('TS', 'Child', [('m_child', 0x18, False)], parent=parent)
        entries = runtime.memory.u64(child + il.CLASS_FIELDS)
        g.q(child + il.CLASS_FIELDS, 0)  # the parent is set up, this one not yet
        self.assertNotIn('m_child', runtime.fields(child))
        g.q(child + il.CLASS_FIELDS, entries)
        self.assertEqual(runtime.fields(child)['m_child'], (0x18, False))
        self.assertEqual(runtime.fields(child)['m_base'], (0x10, False))

    def test_a_static_field_of_a_class_not_set_up_is_not_found_and_kept_trying(self):
        # Just after TSU starts, TS.Services has no fields yet (seen on the Mac: a KeyError
        # for sm_instance restarted the reader in the bottle). The game is loading, not gone.
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        g, memory = reader.game, reader.il.memory
        entries = memory.u64(reader.services_class + il.CLASS_FIELDS)
        g.q(reader.services_class + il.CLASS_FIELDS, 0)
        with self.assertRaises(il.NotFound):
            reader.read()
        g.q(reader.services_class + il.CLASS_FIELDS, entries)
        self.assertEqual(reader.read().current_lap, 10_000)

    def test_fields_are_kept_once_the_class_is_set_up(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        g, runtime = reader.game, reader.il
        parent = g.klass('TS', 'Base', [('m_base', 0x10, False)])
        child = g.klass('TS', 'Child', [('m_child', 0x18, False)], parent=parent)
        runtime.fields(child)
        g.q(child + il.CLASS_FIELDS, 0)  # would show if it were read again
        self.assertIn('m_child', runtime.fields(child))

    def test_a_race_is_found_when_the_first_search_came_before_the_game_set_up_its_class(self):
        reader = build(
            [10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, name='Host', online=True
        )
        g = reader.game
        memory = reader.il.memory
        klass = memory.u64(g.client_controller)
        parent = memory.u64(klass + il.CLASS_PARENT)  # holds m_eventState
        entries = memory.u64(klass + il.CLASS_FIELDS), memory.u64(parent + il.CLASS_FIELDS)
        g.q(klass + il.CLASS_FIELDS, 0)  # the event has just started
        g.q(parent + il.CLASS_FIELDS, 0)
        with self.assertRaises(race.NotFound):
            reader.read()
        g.q(klass + il.CLASS_FIELDS, entries[0])
        g.q(parent + il.CLASS_FIELDS, entries[1])
        reader._next_search = 0.0
        self.assertEqual(reader.read().laps_completed, 1)

    def test_a_class_whose_parents_go_round_is_not_a_class(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        g, runtime = reader.game, reader.il
        looped = g.klass('TS', 'Looped', [('m_a', 0x10, False)])
        g.q(looped + il.CLASS_PARENT, looped)  # stale memory: it never reaches System.Object
        with self.assertRaises(il.NotFound):
            runtime.fields(looped)
        self.assertFalse(runtime._set_up(looped))

    def test_a_class_whose_fields_go_on_without_end_is_not_a_class(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        g, runtime = reader.game, reader.il
        endless = g.klass('TS', 'Endless', [(f'm_{i}', 0x10 + i, False) for i in range(80)])
        with mock.patch.object(il, 'FIELDS_MOST', 64), self.assertRaises(il.NotFound):
            runtime.fields(endless)

    def test_an_online_race_is_found_past_a_stale_hit_that_leads_to_no_class(self):
        # Seen on Windows (2026-11-11): a stale pointer to the controller's class, whose event
        # state led to memory with parents that went round, kept the search going for good.
        reader = build(
            [10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, name='Host', online=True
        )
        g, runtime = reader.game, reader.il
        klass = runtime.memory.u64(g.client_controller)
        looped = g.klass('TS', 'Looped', [('m_a', 0x10, False)])
        g.q(looped + il.CLASS_PARENT, looped)
        stale, garbage = 0x100, 0x200  # below the real controller: the search meets it first
        g.q(stale, klass)
        g.q(stale + runtime.offset(g.client_controller, 'm_eventState'), garbage)
        g.q(garbage, looped)
        self.assertEqual(reader.read().laps_completed, 1)

    def test_unknown_class_is_reported(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        with self.assertRaises(il.NotFound):
            reader.il.find_class('TS', 'NoSuchClass')


def racing(state, running=False, read_at=100.0, moved_at=100.0):
    return race.Snapshot(race.RACING, state, running, read_at, moved_at=moved_at)


MID_RACE = race.LapState(
    clock=2_000_000,
    time_limit=12_610_000,
    laps_completed=2,
    laps_to_finish=13,
    lap_starts=[10_000, 944_595, 1_785_545],
)


class EventTypeTests(unittest.TestCase):
    def test_the_event_type_is_read_and_logged_once_per_event(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0, event_type=('CollectorMode', 6))
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            reader.read()
            reader.read()
        self.assertEqual(reader.event_type, ('TS.CollectorMode', 6))
        lines = [m for m in logs.output if 'event type' in m]
        self.assertEqual(len(lines), 1)
        self.assertIn(
            'settings.m_eventMode = TS.CollectorMode (fields: m_goal), m_initializedLevelType = 6, logic TS.RaceLogic',
            lines[0],
        )

    def on_a_track(self, mode, spectating=False):
        reader = build(
            [10_000],
            laps_completed=0,
            clock=20_000,
            limit=0,
            event_type=(mode, 6),
            local_index=-1 if spectating else 0,
        )
        return reader.read().on_a_track

    def test_a_race_mode_is_on_a_track(self):
        self.assertTrue(self.on_a_track('RaceEventMode'))
        self.assertTrue(self.on_a_track('RaceEventMode', spectating=True))

    def test_the_arena_modes_are_not(self):
        for mode in (
            'BattleEventMode',
            'CollectorEventMode',
            'HillEventMode',
            'SumoEventMode',
            'TagEventMode',
        ):
            self.assertFalse(self.on_a_track(mode), mode)
        self.assertFalse(self.on_a_track('BattleEventMode', spectating=True))

    def test_an_unknown_mode_keeps_the_map(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)  # no event settings
        self.assertTrue(reader.read().on_a_track)

    def test_without_the_field_the_log_lists_the_fields_there_are(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0, draft=True)
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            reader.read()
        self.assertIsNone(reader.event_type)
        self.assertTrue(any('not found; settings fields: drafting' in m for m in logs.output))

    def test_without_event_settings_the_race_is_still_read(self):
        reader = build([10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0)
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            self.assertEqual(reader.read().laps_completed, 1)
        self.assertIsNone(reader.event_type)
        self.assertTrue(any('no event settings' in m for m in logs.output))


class DeltaTests(unittest.TestCase):
    # Two finished laps (the second, 80 s, is the best) and the current lap.
    LAPS = (
        (0, 0, 300_000, 600_000),
        (900_000, 900_000, 1_150_000, 1_400_000),
        (1_700_000, 1_700_000, 1_960_000),
    )

    def state(self, checkpoints=LAPS, laps_completed=2):
        return race.LapState(
            clock=1_980_000,
            time_limit=0,
            laps_completed=laps_completed,
            laps_to_finish=13,
            lap_starts=[lap[0] for lap in checkpoints],
            checkpoints=checkpoints,
        )

    def test_compares_the_last_checkpoint_passed_with_the_best_lap(self):
        state = self.state()
        self.assertEqual(state.best_lap_index, 1)
        # This lap 26.0 s at checkpoint 2, the best lap 25.0 s there: 1 s behind.
        self.assertEqual(state.delta_to_best, 10_000)

    def test_ahead_is_negative(self):
        laps = self.LAPS[:2] + ((1_700_000, 1_700_000, 1_940_000),)
        self.assertEqual(self.state(laps).delta_to_best, -10_000)

    def test_none_on_the_first_lap_and_at_the_start_of_a_lap(self):
        self.assertIsNone(self.state(((0, 0, 300_000),), laps_completed=0).delta_to_best)
        laps = self.LAPS[:2] + ((1_700_000, 1_700_000),)
        self.assertIsNone(self.state(laps).delta_to_best)

    def test_a_missed_checkpoint_is_skipped(self):
        laps = (
            self.LAPS[0],
            (900_000, 900_000, race.NO_CHECKPOINT, 1_400_000),
            (1_700_000, 1_700_000, 1_960_000),
        )
        state = self.state(laps)
        # Checkpoint 2 is missing in the best lap: compare checkpoint 1 (both 0 s in): none.
        self.assertIsNone(state.delta_to_best)

    def test_reader_reads_every_checkpoint(self):
        reader = build([10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0)
        state = reader.read()
        self.assertEqual(state.checkpoints[0], (10_000, 10_000, 15_000))
        self.assertEqual(state.lap_starts, [10_000, 944_595])


# A straight track along z: checkpoint lines across it every 100 units.
STRAIGHT = tuple(((-10.0, 100.0 * i), (10.0, 100.0 * i)) for i in range(3))


class LiveDeltaTests(unittest.TestCase):
    # Three checkpoints a lap. Best lap (the second): 10 s to the first line, 20 s to the
    # second, finish at 30 s. The current lap passed its first line after 11 s.
    LAPS = ((0, 110_000, 220_000), (400_000, 500_000, 600_000), (700_000, 810_000))

    def state(self, clock, z, laps=LAPS):
        return race.LapState(
            clock=clock,
            time_limit=0,
            laps_completed=2,
            laps_to_finish=13,
            lap_starts=[lap[0] for lap in laps],
            checkpoints=laps,
            position=(0.0, z),
            gates=STRAIGHT,
        )

    def test_gate_share(self):
        self.assertAlmostEqual(race.gate_share(STRAIGHT[1], STRAIGHT[2], (5.0, 125.0)), 0.25)
        self.assertEqual(race.gate_share(STRAIGHT[0], STRAIGHT[1], (0.0, 0.0)), 0.0)

    def test_at_a_line_it_matches_the_checkpoint_delta(self):
        self.assertEqual(self.state(clock=810_000, z=100.0).delta_to_best, 10_000)

    def test_between_lines_it_moves_with_the_car(self):
        # Halfway to the second line: the best lap was there at 15 s. This lap is at 16 s.
        self.assertEqual(self.state(clock=860_000, z=150.0).delta_to_best, 10_000)
        # Still at the halfway point a second later: one more second lost.
        self.assertEqual(self.state(clock=870_000, z=150.0).delta_to_best, 20_000)
        # Gained on the best lap: there at 16 s, but already 3/4 of the way.
        self.assertEqual(self.state(clock=860_000, z=175.0).delta_to_best, -15_000)

    def test_the_last_stretch_runs_to_the_finish(self):
        # The start and finish line (checkpoint 0) at z 300, lines 1 and 2 at z 100 and 200.
        loop = (((-10.0, 300.0), (10.0, 300.0)), STRAIGHT[1], STRAIGHT[2])
        laps = self.LAPS[:2] + ((700_000, 810_000, 910_000),)
        state = race.LapState(
            clock=960_000,
            time_limit=0,
            laps_completed=2,
            laps_to_finish=13,
            lap_starts=[lap[0] for lap in laps],
            checkpoints=laps,
            position=(0.0, 250.0),
            gates=loop,
        )
        # Halfway from the last line to the finish: the best lap was there at 25 s (20 s at
        # the line, finish at 30 s); this lap is at 26 s.
        self.assertEqual(state.delta_to_best, 10_000)

    def test_lines_passed_together_count_as_one_stretch(self):
        # Lines 0 and 1 get the same time when the lap starts (as in TSU); the car is
        # really between line 0 (z 0) and line 1 (z 100). Line 2 at z 200.
        gates = STRAIGHT
        laps = (
            (0, 0, 200_000),
            (400_000, 400_000, 600_000),  # best: 20 s from the line to line 2
            (700_000, 700_000),  # this lap: just started
        )
        state = race.LapState(
            clock=750_000,
            time_limit=0,
            laps_completed=2,
            laps_to_finish=13,
            lap_starts=[lap[0] for lap in laps],
            checkpoints=laps,
            position=(0.0, 50.0),
            gates=gates,
        )
        # A quarter of the way from line 0 to line 2: the best lap was there at 5 s; this
        # lap is at 5 s too. Taking line 1 as passed would have said +5 s.
        self.assertEqual(state.delta_to_best, 0)

    def test_gate_share_follows_the_path_in_a_bend(self):
        # A right-angle bend: line A across x at z 0, line B across z at x 100. Their
        # extensions cross at (0, 0)... the projection stays sensible on the path.
        a = ((-10.0, 0.0), (10.0, 0.0))
        b = ((100.0, 90.0), (100.0, 110.0))
        self.assertAlmostEqual(race.gate_share(a, b, (50.0, 50.0)), 0.5)

    def test_a_line_at_the_same_spot_is_skipped_ahead(self):
        # Lines 1 and 2 at the same spot (z 100) with the same time; TSU writes line 2's
        # time only when the car reaches line 3 (z 200). Best lap: 10 s to z 100, 20 s to
        # z 200. This lap passed z 100 after 10 s; halfway to z 200 at 15 s: even.
        gates = (
            ((-10.0, 0.0), (10.0, 0.0)),
            ((-10.0, 100.0), (10.0, 100.0)),
            ((-10.0, 100.0), (10.0, 100.0)),
            ((-10.0, 200.0), (10.0, 200.0)),
        )
        laps = ((0, 100_000, 100_000, 200_000), (300_000, 400_000, 400_000, 500_000), (600_000, 700_000))
        state = race.LapState(
            clock=750_000,
            time_limit=0,
            laps_completed=2,
            laps_to_finish=13,
            lap_starts=[lap[0] for lap in laps],
            checkpoints=laps,
            position=(0.0, 150.0),
            gates=gates,
        )
        self.assertEqual(state.delta_to_best, 0)

    def test_a_long_line_crossed_far_from_its_middle(self):
        # Line 1 is 200 units long; the car drives along z 10, far from its middle.
        line0 = ((0.0, 0.0), (0.0, 20.0))
        line1 = ((100.0, 0.0), (100.0, 200.0))
        self.assertAlmostEqual(race.gate_share(line0, line1, (50.0, 10.0)), 0.5)

    def test_a_split_line_counts_its_nearest_piece(self):
        # The next checkpoint is two pieces at x 100 (z 0-20 and z 20-200).
        pieces = [((100.0, 20.0), (100.0, 200.0)), ((100.0, 0.0), (100.0, 20.0))]
        self.assertAlmostEqual(race.gate_share([((0.0, 0.0), (0.0, 20.0))], pieces, (75.0, 10.0)), 0.75)

    def test_without_position_it_falls_back_to_checkpoints(self):
        state = race.LapState(
            clock=860_000,
            time_limit=0,
            laps_completed=2,
            laps_to_finish=13,
            lap_starts=[lap[0] for lap in self.LAPS],
            checkpoints=self.LAPS,
        )
        self.assertEqual(state.delta_to_best, 10_000)


class CachingReaderTests(unittest.TestCase):
    def test_reads_the_car_and_the_track(self):
        reader = build(
            [10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, car=(1.0, 2.0), gates=STRAIGHT
        )
        state = reader.read()
        self.assertEqual(state.position, (1.0, 2.0))
        self.assertEqual(state.gates, STRAIGHT)
        self.assertEqual(state.sector_lines, ())  # a game without the type field

    def test_reads_which_checkpoints_are_sector_lines(self):
        types = [1] * len(STRAIGHT)
        types[1] = 0
        reader = build(
            [10_000, 944_595],
            laps_completed=1,
            clock=1_000_000,
            limit=0,
            car=(1.0, 2.0),
            gates=STRAIGHT,
            gate_types=types,
        )
        self.assertEqual(reader.read().sector_lines, (1,))

    def test_finished_laps_are_read_once(self):
        reader = build([10_000, 944_595, 1_785_545], laps_completed=2, clock=2_000_000, limit=0)
        first = reader.read()
        # Change what the game holds for a finished lap: the reader keeps what it read.
        times = reader.il.memory.u64(reader.game.laps[0] + 0x10)
        array = reader.il.memory.u64(times + il.LIST_ITEMS)
        reader.game.put(array + il.ARRAY_DATA, struct.pack('<I', 1))
        self.assertEqual(reader.read().checkpoints[0], first.checkpoints[0])


class CarTests(unittest.TestCase):
    def car(self, **changes):
        values = {
            'fuel_on': True,
            'fuel_used': 42_000,
            'fuel_tank': 168_000,
            'tires_on': True,
            'tire_wear': 576_000,
            'speed': 50.0,
        }
        values.update(changes)
        return race.CarState(**values)

    def test_what_is_left(self):
        car = self.car(fuel_per_lap=10_500, wear_per_lap=144_000)
        self.assertAlmostEqual(car.fuel_left, 0.75)
        self.assertAlmostEqual(car.tires_left, 0.9)
        self.assertAlmostEqual(car.fuel_laps, 12.0)
        self.assertAlmostEqual(car.tire_laps, 36.0)
        self.assertAlmostEqual(car.kmh, 180.0)

    def test_a_tire_change_shows_as_gradual_though_the_game_holds_the_wear(self):
        self.assertAlmostEqual(self.car(tire_change=0.0).tires_left, 0.9)
        self.assertAlmostEqual(self.car(tire_change=0.5).tires_left, 0.95)
        self.assertAlmostEqual(self.car(tire_change=1.0).tires_left, 1.0)
        self.assertAlmostEqual(self.car(tire_change=0.5, wear_per_lap=144_000).tire_laps, 38.0)
        self.assertEqual(self.car(tire_change=0.5).tire_wear, 576_000)

    def test_off_in_the_event(self):
        car = self.car(fuel_on=False, tires_on=False)
        self.assertIsNone(car.fuel_left)
        self.assertIsNone(car.tire_laps)
        self.assertEqual(set(race.car_sections(car)), {'speed', 'pedals'})  # no fuel, no tires

    def test_per_lap_averages_the_last_laps_and_restarts_after_a_pit_stop(self):
        self.assertIsNone(race.per_lap([0]))
        self.assertEqual(race.per_lap([0, 11_000, 21_000, 31_000, 41_000]), 10_000)  # last 3 laps
        self.assertEqual(race.per_lap([0, 11_000, 21_000, 2_000, 12_000]), 10_000)  # refuelled after lap 2
        self.assertIsNone(race.per_lap([0, 11_000, 21_000, 2_000]))

    def test_section_texts(self):
        sections = race.car_sections(self.car(fuel_per_lap=10_500))
        fuel = sections['fuel'][0]
        self.assertEqual((fuel.text, fuel.tail, fuel.tail_color), ('Fuel 75.0%', '  ~12.0 laps', 'text'))
        self.assertEqual(sections['tires'][0].text, 'Tires 90%')  # no lap measured yet
        self.assertEqual(sections['speed'][0].text, '180 km/h')

    def test_the_fuel_saved_or_burnt_this_lap(self):
        saved = race.car_sections(self.car(fuel_per_lap=10_000, fuel_trend=-300))['fuel'][0]
        burnt = race.car_sections(self.car(fuel_per_lap=10_000, fuel_trend=210))['fuel'][0]
        unknown = race.car_sections(self.car(fuel_per_lap=10_000))['fuel'][0]
        self.assertEqual(saved.tail, '  ~12.6 laps  +0.18%')  # 300 of a 168,000 tank
        self.assertEqual(burnt.tail, '  ~12.6 laps  -0.12%')
        self.assertEqual(unknown.tail, '  ~12.6 laps')

    def test_one_decimal(self):
        self.assertEqual(race.car_sections(self.car(fuel_used=39_312))['fuel'][0].text, 'Fuel 76.6%')

    def test_laps_are_green_when_saving_and_red_when_not(self):
        saving = race.car_sections(self.car(fuel_per_lap=10_000, fuel_trend=-300))['fuel'][0]
        wasting = race.car_sections(self.car(fuel_per_lap=10_000, fuel_trend=300))['fuel'][0]
        even = race.car_sections(self.car(fuel_per_lap=10_000, fuel_trend=50))['fuel'][0]
        self.assertEqual(
            [saving.tail_color, wasting.tail_color, even.tail_color], ['ahead', 'behind', 'text']
        )

    def test_fuel_trend_compares_the_same_checkpoint_in_recent_laps(self):
        starts = {0: 0, 1: 10_000, 2: 20_000}
        marks = {0: {10: 1_000}, 1: {10: 11_200}, 2: {}}
        # Lap 2 used 900 by checkpoint 10; laps 0 and 1 used 1,000 and 1,200: saving 200.
        self.assertEqual(race.fuel_trend(marks, starts, 2, 10, 20_900), -200)
        # A checkpoint missed in a read: the one before counts.
        self.assertEqual(race.fuel_trend({0: {9: 1_000}, 1: {10: 11_000}}, starts, 2, 10, 21_100), 100)

    def test_no_fuel_trend_early_first_lap_or_across_a_pit_stop(self):
        starts = {0: 0, 1: 10_000, 2: 3_000}  # refuelled during lap 1
        marks = {0: {10: 1_000}, 1: {10: 11_000}}
        self.assertIsNone(race.fuel_trend(marks, starts, 2, 10, 4_000))
        self.assertIsNone(race.fuel_trend(marks, {0: 0, 1: 10_000}, 1, 1, 10_100))  # too early
        self.assertIsNone(race.fuel_trend({}, {0: 0}, 0, 10, 1_000))  # nothing to compare

    def test_reader_reads_the_car_and_the_use_per_lap(self):
        reader = build(
            [10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, car=(0.0, 0.0), gates=STRAIGHT
        )
        car = reader.read().car
        self.assertEqual((car.fuel_used, car.fuel_tank, car.tire_wear), (42_000, 168_000, 576_000))
        self.assertTrue(car.fuel_on and car.tires_on)
        self.assertAlmostEqual(car.speed, 50.0)
        self.assertIsNone(car.fuel_per_lap)  # one lap start seen so far

    def test_speed_is_yellow_while_lifting(self):
        def colour(throttle, brake, kmh=150):
            car = self.car(speed=kmh / 3.6, throttle=throttle, brake=brake)
            return race.car_sections(car)['speed'][0].color

        self.assertEqual(colour(0.0, 0.0), 'lift')
        self.assertEqual(colour(1.0, 0.0), 'text')  # on the throttle
        self.assertEqual(colour(0.0, 1.0), 'text')  # braking
        self.assertEqual(colour(0.0, 0.0, kmh=2), 'text')  # standing
        self.assertEqual(colour(None, None), 'text')  # inputs unknown

    def test_reader_reads_throttle_and_brake(self):
        reader = build(
            [10_000],
            laps_completed=0,
            clock=20_000,
            limit=0,
            car=(0.0, 0.0),
            gates=STRAIGHT,
            pedals=(1.0, 0.0),
        )
        car = reader.read().car
        self.assertEqual((car.throttle, car.brake), (1.0, 0.0))
        self.assertEqual(race.car_sections(car)['pedals'], (1.0, 0.0))

    def test_whole_number_pedals_are_read_as_thirds(self):
        reader = build(
            [10_000], laps_completed=0, clock=20_000, limit=0, car=(0.0, 0.0), gates=STRAIGHT, pedals=(2, 3)
        )
        car = reader.read().car
        self.assertAlmostEqual(car.throttle, 2 / 3)
        self.assertEqual(car.brake, 1.0)

    def test_without_controls_the_pedals_are_unknown(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0, car=(0.0, 0.0), gates=STRAIGHT)
        car = reader.read().car
        self.assertEqual((car.throttle, car.brake), (None, None))

    def test_reader_reads_the_players(self):
        reader = build([10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, name='Fahrer Ö')
        players = reader.read().players
        me = next(p for p in players if p.local)
        self.assertEqual((me.name, me.flag, me.laps_completed), ('Fahrer Ö', 75, 1))
        self.assertEqual(me.tag, 'GT3')  # the clan tag, read once per profile
        self.assertEqual(len(reader._tags), 1)
        self.assertEqual(next(p for p in reader.read().players if p.local).tag, 'GT3')
        self.assertEqual(me.checkpoints[0][0], 10_000)
        self.assertEqual(len(players), 1)  # the other one has no statistics: left out

    def test_a_changed_clan_tag_is_read_again_after_a_few_seconds(self):
        # Seen 2026-11-11: tags changed between races were kept from before for good.
        now = [100.0]
        reader = build(
            [10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, name='A', clock_fn=lambda: now[0]
        )
        self.assertEqual(next(p for p in reader.read().players if p.local).tag, 'GT3')
        profile = next(iter(reader._tags))
        text = reader.il.memory.u64(profile + 0x48)
        reader.game.put(text + 0x14, 'LMP'.encode('utf-16-le'))
        now[0] += 1.0
        self.assertEqual(next(p for p in reader.read().players if p.local).tag, 'GT3')  # kept a moment
        now[0] += race.LABEL_REFRESH
        self.assertEqual(next(p for p in reader.read().players if p.local).tag, 'LMP')

    def test_an_online_race_is_found_through_its_client_controller(self):
        reader = build(
            [10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, name='Host', online=True
        )
        state = reader.read()
        self.assertEqual(state.laps_completed, 1)
        self.assertEqual([p.name for p in state.players], ['Host'])
        searches = reader.game.searches
        reader.read()
        self.assertEqual(reader.game.searches, searches)  # found once, then kept

    def test_the_next_race_is_searched_for(self):
        reader = build(
            [10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, name='Host', online=True
        )
        reader.read()
        g = reader.game
        state = g.read(g.client_controller + 0x48, 8)
        g.q(g.client_controller + 0x48, 0)  # the race is over
        with self.assertRaises(race.NotFound):
            reader.read()
        reader._next_search = 0.0
        searches = g.searches
        g.put(g.client_controller + 0x48, state)  # the next race, at the same place
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            self.assertEqual(reader.read().laps_completed, 1)
        self.assertEqual(g.searches, searches + 1)
        self.assertTrue(any('race found' in line for line in logs.output))

    def test_a_race_found_where_the_last_one_was_is_read_afresh(self):
        # A tester's third event of a session (2026-11-11): TSU put the new race's event state
        # at the last one's address, and the reader went on with what it kept of the last race.
        reader = build(
            [10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, name='Host', online=True
        )
        reader.read()
        g = reader.game
        state = g.read(g.client_controller + 0x48, 8)
        g.q(g.client_controller + 0x48, 0)  # the race is over
        with self.assertRaises(race.NotFound):
            reader.read()
        reader._player = 0xDEAD0000  # what was kept of the last race no longer holds
        reader._next_search = 0.0
        g.put(g.client_controller + 0x48, state)  # the next race, at the same place
        self.assertEqual(reader.read().laps_completed, 1)
        self.assertNotEqual(reader._player, 0xDEAD0000)  # looked up anew

    def test_a_race_still_there_after_its_end_is_read_afresh_when_found_again(self):
        # The race object stayed, but the search found it anew: nothing kept counts.
        reader = build(
            [10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, name='Host', online=True
        )
        reader.read()
        reader._controller = None  # as after the race was lost
        reader._player = 0xDEAD0000
        reader._next_search = 0.0
        self.assertEqual(reader.read().laps_completed, 1)
        self.assertNotEqual(reader._player, 0xDEAD0000)

    def quick_looking(self, running=None):
        """An online reader whose race was found, then ended; the fake game can look near
        it. Returns (reader, clock, the race to put back, the quick looks made)."""
        now = [100.0]
        reader = build(
            [10_000, 944_595],
            laps_completed=1,
            clock=1_000_000,
            limit=0,
            name='Host',
            online=True,
            clock_fn=lambda: now[0],
            event_running=running,
        )
        reader.read()
        g, memory, looks = reader.game, reader.il.memory, []
        find = memory.find_pointers

        def near(value, address):
            looks.append(address)
            return find(value)

        memory.find_pointers_near = near
        state = g.read(g.client_controller + 0x48, 8)
        g.q(g.client_controller + 0x48, 0)  # the race is over
        with self.assertRaises(race.NotFound):
            reader.read()  # lost: a search at once, which finds nothing
        looks.clear()
        return reader, now, state, looks

    def test_between_searches_a_quick_look_near_the_last_race_finds_the_next(self):
        reader, now, state, looks = self.quick_looking()
        g = reader.game
        searches = g.searches
        now[0] += 3  # well before the next search, 10 s on
        g.put(g.client_controller + 0x48, state)  # the next race, where the last one was
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            self.assertEqual(reader.read().laps_completed, 1)
        self.assertEqual(looks, [g.client_controller])
        self.assertIn('quick look: race found (+0.0 MiB from the last one)', logs.output[0])
        self.assertEqual(g.searches - searches, 1)  # the fake counts the look as a search: no other
        reader.read()
        self.assertEqual(len(looks), 1)  # found: no more looks

    def test_quick_looks_come_at_most_every_2_s(self):
        reader, now, _state, looks = self.quick_looking()
        for step in (0.5, 0.5, 0.5, 0.5, 0.5):  # 2.5 s, short of the next search
            now[0] += step
            with self.assertRaises(race.NotFound):
                reader.read()
        self.assertEqual(len(looks), 2)  # at 100.5 and 102.5
        self.assertEqual(race.QUICK_LOOK_EVERY, 2.0)

    def test_no_quick_look_while_the_games_log_says_no_event_runs(self):
        says = [True]  # an event, until the race is over
        reader, now, _state, looks = self.quick_looking(running=lambda: says[0])
        says[0] = False
        now[0] += 3
        with self.assertRaises(race.NotFound):
            reader.read()
        self.assertEqual(looks, [])

    def test_no_quick_look_before_a_race_was_found(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0, online=True, clock_fn=lambda: 100.0)
        looks = []
        reader.il.memory.find_pointers_near = lambda value, address: looks.append(address) or []
        reader.game.q(reader.game.client_controller + 0x48, 0)  # no race
        for _ in range(3):
            with self.assertRaises(race.NotFound):
                reader.read()
        self.assertEqual(looks, [])  # nowhere to look yet: the searches find the first race

    def search_from(self, reader):
        """Give the fake a reader that can begin a search at an address; the list says
        where each search began (None: at the lowest address)."""
        memory, begun = reader.il.memory, []
        find = memory.find_pointers

        def from_the_lowest(value):
            begun.append(None)
            return find(value)

        def from_there(value, address):
            begun.append(address)
            hits = find(value)
            return [h for h in hits if h >= address] + [h for h in hits if h < address]

        memory.find_pointers, memory.find_pointers_from = from_the_lowest, from_there
        return begun

    def test_the_next_race_is_searched_for_from_where_the_last_one_was(self):
        reader = build(
            [10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, name='Host', online=True
        )
        begun = self.search_from(reader)
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            reader.read()
        self.assertEqual(logs.output[0], 'INFO:turbohud.core.race:searching for the online race')
        g = reader.game
        state = g.read(g.client_controller + 0x48, 8)
        g.q(g.client_controller + 0x48, 0)  # the race is over
        with self.assertRaises(race.NotFound):
            reader.read()
        reader._next_search = 0.0
        g.put(g.client_controller + 0x48, state)  # the next race, at the same place
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            self.assertEqual(reader.read().laps_completed, 1)
        # The first search and the one that found no race had no place to begin at.
        self.assertEqual(begun, [None, g.client_controller, g.client_controller])
        self.assertIn('from where the last one was', logs.output[0])
        self.assertIn('race found (+0.0 MiB from the last one), after', logs.output[1])
        self.assertEqual(reader._search_wait, race.CLIENT_SEARCH_EVERY)

    def test_a_reader_that_cannot_begin_a_search_anywhere_searches_as_before(self):
        reader = build(
            [10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, name='Host', online=True
        )
        reader.read()
        g = reader.game
        state = g.read(g.client_controller + 0x48, 8)
        g.q(g.client_controller + 0x48, 0)
        with self.assertRaises(race.NotFound):
            reader.read()
        reader._next_search = 0.0
        g.put(g.client_controller + 0x48, state)
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            self.assertEqual(reader.read().laps_completed, 1)
        self.assertEqual(logs.output[0], 'INFO:turbohud.core.race:searching for the online race')

    def test_no_search_between_events_after_a_race(self):
        running = [True]
        reader = build(
            [10_000, 944_595],
            laps_completed=1,
            clock=1_000_000,
            limit=0,
            name='Host',
            online=True,
            event_running=lambda: running[0],
        )
        reader.read()
        reader._controller = None  # dropped between events; what is there is not a new race
        reader._next_search = 0.0
        searches = reader.game.searches
        running[0] = False
        with self.assertRaises(race.NotFound):
            reader.read()
        self.assertIsNone(reader._controller)
        self.assertEqual(reader.game.searches, searches)

    def backing_off(self, running=None):
        now = [100.0]
        reader = build(
            [10_000],
            laps_completed=0,
            clock=20_000,
            limit=0,
            online=True,
            clock_fn=lambda: now[0],
            event_running=running,
        )
        reader.race_there = reader.game.read(reader.game.client_controller + 0x48, 8)
        reader.game.q(reader.game.client_controller + 0x48, 0)  # no race in it
        return reader, now

    def waits_of(self, reader, now, count):
        """The waits between `count` searches that find nothing."""
        waits = []
        for _ in range(count):
            with self.assertRaises(race.NotFound):
                reader.read()
            waits.append(reader._next_search - now[0])
            now[0] = reader._next_search
        return waits

    # Searches 10 s apart for the first minute (at 100, 110 ... 160 s): only then does the wait grow.
    QUICK = 7

    def test_an_event_without_a_race_is_searched_less_and_less_after_a_minute(self):
        reader, now = self.backing_off()
        self.assertEqual(
            self.waits_of(reader, now, self.QUICK + 4), [10.0] * self.QUICK + [20.0, 40.0, 60.0, 60.0]
        )

    def test_a_race_joined_in_progress_is_searched_for_every_10_s_at_first(self):
        # Joining a public session mid-race (2026-11-08): two searches found nothing while
        # the race was set up, then a 50 s wait held the HUD back.
        reader, now = self.backing_off()
        self.assertEqual(self.waits_of(reader, now, 3), [10.0, 10.0, 10.0])
        reader.game.put(reader.game.client_controller + 0x48, reader.race_there)
        now[0] = reader._next_search
        self.assertIsNotNone(reader.read())
        self.assertIsNone(reader._empty_since)

    def test_the_minute_counts_again_after_a_race(self):
        reader, now = self.backing_off()
        self.waits_of(reader, now, self.QUICK + 2)
        self.assertGreater(reader._search_wait, race.CLIENT_SEARCH_EVERY)
        reader.game.put(reader.game.client_controller + 0x48, reader.race_there)
        now[0] = reader._next_search
        reader.read()
        reader.game.q(reader.game.client_controller + 0x48, 0)  # that race is over
        now[0] += 1.0
        self.assertEqual(self.waits_of(reader, now, 2), [10.0, 10.0])

    def test_no_search_during_a_long_wait(self):
        reader, now = self.backing_off()
        self.waits_of(reader, now, self.QUICK + 3)  # the next wait is 60 s
        with self.assertRaises(race.NotFound):
            reader.read()
        searches = reader.game.searches
        now[0] += 59.0
        with self.assertRaises(race.NotFound):
            reader.read()
        self.assertEqual(reader.game.searches, searches)

    def test_the_end_of_the_event_ends_a_long_wait(self):
        running = [True]
        reader, now = self.backing_off(lambda: running[0])
        self.waits_of(reader, now, self.QUICK + 3)
        with self.assertRaises(race.NotFound):
            reader.read()
        self.assertGreater(reader._next_search - now[0], race.CLIENT_LOG_EVERY)
        running[0] = False
        now[0] += 1.0
        with self.assertRaises(race.NotFound):
            reader.read()
        self.assertEqual(reader._next_search - now[0], race.CLIENT_LOG_EVERY)
        self.assertEqual(reader._search_wait, race.CLIENT_SEARCH_EVERY)

    def test_a_race_found_ends_the_long_waits(self):
        reader, now = self.backing_off()
        self.waits_of(reader, now, self.QUICK + 2)
        self.assertGreater(reader._search_wait, race.CLIENT_SEARCH_EVERY)
        reader.game.put(reader.game.client_controller + 0x48, reader.race_there)
        now[0] = reader._next_search
        self.assertIsNotNone(reader.read())
        self.assertEqual(reader._search_wait, race.CLIENT_SEARCH_EVERY)

    def test_without_an_online_race_the_search_waits_between_tries(self):
        now = [100.0]
        reader = build(
            [10_000], laps_completed=0, clock=20_000, limit=0, online=True, clock_fn=lambda: now[0]
        )
        g = reader.game
        g.q(g.client_controller + 0x48, 0)  # no race in it (menu, lobby)
        with self.assertRaises(race.NotFound):
            reader.read()
        with self.assertRaises(race.NotFound):
            reader.read()
        self.assertEqual(g.searches, 1)  # not again before CLIENT_SEARCH_EVERY
        now[0] += race.CLIENT_SEARCH_EVERY
        with self.assertRaises(race.NotFound):
            reader.read()
        self.assertEqual(g.searches, 2)

    def spectated(self, now):
        """A reader in an online race where the player only watches: no local player."""
        reader = build(
            [10_000], laps_completed=0, clock=20_000, limit=0, name='A', online=True, clock_fn=lambda: now[0]
        )
        _state, player = reader.local_player()
        reader.game.put(player + 0x50, struct.pack('<i', -1))
        reader.spectator = player
        reader.times_at = _state + reader.il.offset(_state, 'times') + race.TIMES_NOW
        reader._controller, reader._next_search = None, 0.0
        reader.game.searches = 0
        return reader

    def test_spectating_reads_the_race_without_a_car(self):
        reader = self.spectated([100.0])
        state = reader.read()
        self.assertTrue(state.spectating)
        self.assertIsNone(state.car)
        self.assertEqual(state.laps_to_finish, 13)
        self.assertEqual([p.name for p in state.players], ['A'])
        self.assertFalse(state.players[0].local)

    def test_a_watched_race_with_a_running_clock_is_not_searched_again(self):
        now = [100.0]
        reader = self.spectated(now)
        reader.read()
        for _ in range(3):
            now[0] += race.SPECTATE_STILL - 1
            reader.game.put(reader.times_at, struct.pack('<i', int(now[0])))
            self.assertTrue(reader.read().spectating)
        self.assertEqual(reader.game.searches, 1)

    def test_a_watched_race_whose_clock_stands_is_searched_for_again(self):
        now = [100.0]
        reader = self.spectated(now)
        reader.read()
        reader.read()
        now[0] += 1.0
        reader.game.put(reader.times_at, struct.pack('<i', 30_000))  # it ran, then the race ended
        reader.read()
        now[0] += race.SPECTATE_STILL + 1
        with self.assertRaises(race.NotFound):  # before the next search is due
            reader.read()
        self.assertEqual(reader.game.searches, 1)
        now[0] += race.CLIENT_SPECTATE_EVERY
        reader.read()
        self.assertEqual(reader.game.searches, 2)

    def test_joining_the_spectated_race_needs_no_search(self):
        now = [100.0]
        reader = self.spectated(now)
        self.assertTrue(reader.read().spectating)
        reader.game.put(reader.spectator + 0x50, struct.pack('<i', 0))
        state = reader.read()
        self.assertFalse(state.spectating)
        self.assertEqual(state.players[0].local, True)
        self.assertEqual(reader.game.searches, 1)

    def test_a_spectated_race_that_ends_is_looked_for_again_at_once(self):
        now = [100.0]
        reader = self.spectated(now)
        reader.read()
        reader.game.q(reader.game.client_controller + 0x48, 0)  # its race is gone
        with self.assertRaises(race.NotFound):
            reader.read()
        self.assertEqual(reader.game.searches, 2)
        self.assertIsNone(reader._spectated)

    def two_to_watch(self, now):
        """A spectator with two races to watch: the first an old one, as one may linger after
        the player left a session; the search reaches it first."""
        reader = self.spectated(now)
        g = reader.game
        g.obj_next = (g.obj_next + 15) & ~15  # objects are aligned, and a search looks only there
        other = g.alloc_obj(struct.unpack('<Q', g.read(g.client_controller, 8))[0])
        g.put(other + 0x48, g.read(g.client_controller + 0x48, 8))
        reader.other = other
        return reader

    def test_a_spectators_search_stops_at_the_first_race_to_watch(self):
        now = [100.0]
        reader = self.two_to_watch(now)
        find = reader.il.memory.find_pointers
        handed = []

        def counted(value):
            for hit in find(value):
                handed.append(hit)
                yield hit

        reader.il.memory.find_pointers = counted
        self.assertTrue(reader.read().spectating)
        self.assertEqual(reader._spectated, reader.game.client_controller)
        self.assertNotIn(reader.other, handed)  # the rest of the data stayed unread

    def test_a_spectators_next_search_begins_at_the_race_watched(self):
        now = [100.0]
        reader = self.two_to_watch(now)
        begun = self.search_from(reader)
        reader.read()
        watched = reader._spectated
        reader.read()
        now[0] += race.SPECTATE_STILL + 1  # its clock stands: searched for again
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            reader.read()
        self.assertEqual(begun[-1], watched)
        self.assertEqual(reader._spectated, reader.other)  # past the one whose clock stood
        self.assertTrue(any('MiB from the last one)' in line for line in logs.output))

    def watch_a_race_that_never_runs(self, reader, now):
        reader.read()
        reader.read()
        now[0] += race.SPECTATE_STILL + 1  # its clock has not moved since it was picked

    def test_a_picked_race_that_never_runs_is_searched_past_at_once(self):
        now = [100.0]
        reader = self.two_to_watch(now)
        self.watch_a_race_that_never_runs(reader, now)
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            self.assertTrue(reader.read().spectating)
        self.assertEqual(reader.game.searches, 2)
        self.assertEqual(reader._spectated, reader.other)
        self.assertIn('has not run: searching past it', logs.output[0])

    def test_a_race_the_player_drives_further_on_is_found_soon(self):
        # The old race is reached first; the player's own race comes later in the search.
        now = [100.0]
        reader = self.two_to_watch(now)
        self.watch_a_race_that_never_runs(reader, now)
        reader.game.put(reader.spectator + 0x50, struct.pack('<i', 0))  # the player's race
        old_state = reader.game.alloc_obj(0)
        reader.game.q(reader.game.client_controller + 0x48, old_state)  # the old race keeps its own
        state = reader.read()
        self.assertFalse(state.spectating)
        self.assertEqual(reader._controller, reader.other)

    def test_a_search_past_a_race_that_never_runs_comes_only_once(self):
        now = [100.0]
        reader = self.two_to_watch(now)
        self.watch_a_race_that_never_runs(reader, now)
        reader.read()  # searched past: the other race, which does not run either
        reader.read()
        now[0] += race.SPECTATE_STILL + 1
        with self.assertRaises(race.NotFound):  # waits CLIENT_SPECTATE_EVERY now
            reader.read()
        self.assertEqual(reader.game.searches, 2)

    def test_the_log_says_how_a_search_went(self):
        now = [100.0]
        reader = build(
            [10_000], laps_completed=0, clock=20_000, limit=0, name='A', online=True, clock_fn=lambda: now[0]
        )
        find = reader.il.memory.find_pointers

        def slow(value):
            now[0] += 12.0
            return find(value)

        reader.il.memory.find_pointers = slow
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            reader.read()
        self.assertIn('searching for the online race', logs.output[0])
        self.assertIn('race found, after 12.0 s', logs.output[1])

    def test_the_log_says_when_there_is_only_a_race_to_watch(self):
        reader = self.spectated([100.0])
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            reader.read()
        self.assertIn('a race to watch', logs.output[1])

    def test_the_log_says_where_the_watched_race_was_among_the_hits(self):
        # The fake's class address is found 4 times: two tables, a stale controller, the race.
        reader = self.spectated([100.0])
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            reader.read()
        self.assertIn('watching the race at hit 4 of 4, 1 races to watch', logs.output[2])

    def test_the_log_says_when_a_search_failed(self):
        reader = self.spectated([100.0])

        def broken(_value):
            raise OSError('the reader has ended')

        reader.il.memory.find_pointers = broken
        with self.assertLogs('turbohud.core.race', 'INFO') as logs, self.assertRaises(OSError):
            reader.read()
        self.assertIn('stopped by an error', logs.output[1])

    def test_the_wait_counts_from_the_end_of_a_long_search(self):
        now = [100.0]
        reader = build(
            [10_000], laps_completed=0, clock=20_000, limit=0, online=True, clock_fn=lambda: now[0]
        )
        g = reader.game
        g.q(g.client_controller + 0x48, 0)
        searches = []

        def slow(value):
            searches.append(value)
            now[0] += 30.0  # longer than the wait, as in a CrossOver bottle
            return []

        reader.il.memory.find_pointers = slow
        with self.assertRaises(race.NotFound):
            reader.read()
        with self.assertRaises(race.NotFound):
            reader.read()
        self.assertEqual(len(searches), 1)
        now[0] += race.CLIENT_SEARCH_EVERY
        with self.assertRaises(race.NotFound):
            reader.read()
        self.assertEqual(len(searches), 2)

    def test_no_search_while_the_games_log_says_no_event_runs(self):
        running = [False]
        reader = build(
            [10_000],
            laps_completed=0,
            clock=20_000,
            limit=0,
            name='A',
            online=True,
            event_running=lambda: running[0],
        )
        with self.assertRaises(race.NotFound):
            reader.read()
        self.assertEqual(getattr(reader.game, 'searches', 0), 0)  # menus, lobby: no search
        running[0] = True
        reader._next_search = 0.0
        self.assertEqual(reader.read().laps_completed, 0)
        self.assertEqual(reader.game.searches, 1)

    def test_online_positions_come_from_the_replay_recorder(self):
        now = [0.0]
        reader = build(
            [10_000],
            laps_completed=0,
            clock=20_000,
            limit=0,
            name='A',
            online=True,
            car=(0.0, 0.0),
            gates=STRAIGHT,
            recorded=(12.5, -40.25),
            clock_fn=lambda: now[0],
        )
        state = reader.read()
        me = next(p for p in state.players if p.local)
        self.assertEqual(me.position, (12.5, -40.25))
        self.assertFalse(me.estimated)
        self.assertEqual(state.position, (12.5, -40.25))  # the delta uses it too

    def test_a_recorder_that_stands_still_is_not_used(self):
        reader = build(
            [10_000],
            laps_completed=0,
            clock=20_000,
            limit=0,
            name='A',
            online=True,
            car=(0.0, 0.0),
            gates=STRAIGHT,
            recorded=(12.5, -40.25),
        )
        reader.read()
        g = reader.game
        times = g.read(reader._state + 0x58, 24)
        g.put(
            reader._state + 0x58,
            struct.pack('<6i', 0, 20_000 + race.RECORDER_STALE + 1, *struct.unpack('<6i', times)[2:]),
        )
        me = next(p for p in reader.read().players if p.local)
        self.assertIsNone(me.position)  # its tick did not move for over a second

    def test_online_the_unkept_position_counts_as_unknown(self):
        reader = build(
            [10_000], laps_completed=0, clock=20_000, limit=0, car=(0.0, 0.0), gates=STRAIGHT, name='A'
        )
        state = reader.read()
        self.assertIsNone(state.position)
        self.assertIsNone(next(p for p in state.players if p.local).position)

    def test_reader_reads_health_with_the_games_limits(self):
        reader = build(
            [10_000], laps_completed=0, clock=20_000, limit=0, car=(1.0, 2.0), gates=STRAIGHT, health=420
        )
        car = reader.read().car
        self.assertAlmostEqual(car.health, 0.84)
        self.assertAlmostEqual(car.downforce_from, 0.9)
        self.assertAlmostEqual(car.slowed_from, 0.75)
        self.assertEqual(car.damage_effect, 'downforce')

    def test_draft_from_the_cars_multipliers_and_the_events_settings(self):
        reader = build(
            [10_000], laps_completed=0, clock=20_000, limit=0, car=(1.0, 2.0), gates=STRAIGHT, draft=True
        )
        car = reader.read().car
        self.assertAlmostEqual(car.draft, 0.73, places=3)  # 1 - 0.927 of a 10 % effect
        self.assertAlmostEqual(car.draft_downforce_loss, 0.584, places=3)

    def test_without_damage_there_is_no_health(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0, car=(1.0, 2.0), gates=STRAIGHT)
        self.assertIsNone(reader.read().car.health)
        self.assertNotIn('health', race.car_sections(reader.read().car))

    def test_pit_shows_in_the_whole_pit_area(self):
        reader = build(
            [10_000],
            laps_completed=0,
            clock=20_000,
            limit=0,
            car=(1.0, 2.0),
            gates=STRAIGHT,
            name='A',
            pit_area=True,
        )
        me = next(p for p in reader.read().players if p.local)
        self.assertTrue(me.in_pit)

    def test_the_reader_says_whether_a_car_is_on_its_pit_box(self):
        # CarStateUpdater.inPit, seen on while a car stood in its box being serviced (2026-11-13).
        def me(**fields):
            reader = build(
                [10_000], laps_completed=0, clock=20_000, limit=0, car=(1.0, 2.0), name='A', **fields
            )
            return next(p for p in reader.read().players if p.local)

        boxed = me(pit_area=True, in_box=True)
        self.assertEqual((boxed.in_pit, boxed.in_box), (True, True))
        lane = me(pit_area=True, in_box=False)
        self.assertEqual((lane.in_pit, lane.in_box), (True, False))  # the pit area, not a box
        self.assertIsNone(me(pit_area=True).in_box)  # not read: not known

    def test_reader_follows_a_tire_change(self):
        def change(ticks):
            reader = build(
                [10_000], laps_completed=0, clock=20_000, limit=0, name='A', car=(1.0, 2.0), tire_ticks=ticks
            )
            return reader.read().car.tire_change

        self.assertEqual(change(0), 0.0)
        self.assertEqual(change(600), 0.25)
        self.assertEqual(change(2400), 1.0)
        # The compound is in the lowest 2 bits (2026-11-12): compound 1 changes as compound 0.
        self.assertEqual(change(601), 0.25)
        self.assertEqual(change(2401), 1.0)
        self.assertEqual(change(2404), 0.0)  # past the end: not a measure of progress

    def test_reader_reads_each_cars_tire_compound_and_the_events_count(self):
        def read(ticks, compounds=None):
            reader = build(
                [10_000],
                laps_completed=0,
                clock=20_000,
                limit=0,
                name='A',
                car=(1.0, 2.0),
                tire_ticks=ticks,
                compounds=compounds,
            )
            state = reader.read()
            return next(p for p in state.players if p.local).compound, state.compounds

        self.assertEqual(read(0), (0, None))  # no event settings: the count is not known
        self.assertEqual(read(2, compounds=3), (2, 3))
        self.assertEqual(read(4 * 300 + 1, compounds=2), (1, 2))  # in a tire change
        self.assertEqual(read(1, compounds=9), (1, None))  # more than TSU allows: not a count

    def test_reader_reads_the_tracks_name_once_an_event(self):
        def read(track):
            reader = build(
                [10_000], laps_completed=0, clock=20_000, limit=0, name='A', car=(1.0, 2.0), track=track
            )
            return reader.read().track

        self.assertEqual(read('Spa (WET)'), 'Spa (WET)')
        self.assertEqual(read(None), '')  # not there: no name, the race still read

    def test_reader_reads_each_cars_position_for_the_radar(self):
        reader = build(
            [10_000], laps_completed=0, clock=20_000, limit=0, car=(12.5, -3.0), gates=STRAIGHT, name='A'
        )
        me = next(p for p in reader.read().players if p.local)
        self.assertEqual(me.position, (12.5, -3.0))
        self.assertEqual(me.car, 'Ligier JS320')  # its car's name, read once per vehicle
        self.assertEqual(len(reader._cars), 1)
        self.assertEqual(next(p for p in reader.read().players if p.local).car, 'Ligier JS320')

    def test_without_car_data_there_are_no_car_sections(self):
        reader = build([10_000], laps_completed=0, clock=20_000, limit=0)
        self.assertIsNone(reader.read().car)


class LiveFuelTests(unittest.TestCase):
    # Start and finish at z 300, lines 1 and 2 at z 100 and 200. The second lap (index 1)
    # is the best; this lap has passed line 2 and drives on to the finish.
    GATES = (((-10.0, 300.0), (10.0, 300.0)), STRAIGHT[1], STRAIGHT[2])
    LAPS = ((0, 110_000, 220_000), (400_000, 500_000, 600_000), (700_000, 810_000, 910_000))

    def state(self, z, used, laps=LAPS):
        car = race.CarState(True, used, 168_000, True, 0, 0.0, fuel_per_lap=3_000)
        return race.LapState(
            clock=960_000,
            time_limit=0,
            laps_completed=2,
            laps_to_finish=13,
            lap_starts=[lap[0] for lap in laps],
            checkpoints=laps,
            position=(0.0, z),
            gates=self.GATES,
            car=car,
        )

    def test_the_recent_laps_are_taken_at_the_same_place_between_lines(self):
        starts = {0: 0, 1: 3_000, 2: 6_000}
        marks = {0: {2: 2_000}, 1: {2: 5_000}}  # both used 2,000 by line 2, 3,000 per lap
        # Halfway from line 2 to the finish: the recent laps had used 2,500 there.
        self.assertEqual(self.state(250.0, 6_000 + 2_500).live_fuel_trend(marks, starts), 0)
        self.assertEqual(self.state(250.0, 6_000 + 2_300).live_fuel_trend(marks, starts), -200)

    def test_no_swing_while_driving_a_stretch_at_the_usual_use(self):
        starts = {0: 0, 1: 3_000, 2: 6_000}
        marks = {0: {2: 2_000}, 1: {2: 5_000}}
        trends = [
            self.state(z, 6_000 + 2_000 + round((z - 200) * 10)).live_fuel_trend(marks, starts)
            for z in (200.0, 225.0, 275.0)
        ]
        self.assertEqual(trends, [0, 0, 0])

    def test_a_pit_stop_ends_the_comparison(self):
        starts = {0: 0, 1: 3_000, 2: 500}  # refuelled
        marks = {0: {2: 2_000}, 1: {2: 5_000}}
        self.assertIsNone(self.state(250.0, 3_000).live_fuel_trend(marks, starts))


class FuelFinishTests(unittest.TestCase):
    def state(self, laps_completed, current_lap, laps_to_finish=13, time_limit=0, clock=0):
        lap_starts = [i * 800_000 for i in range(laps_completed + 1)]
        clock = clock or lap_starts[-1] + current_lap
        return race.LapState(clock, time_limit, laps_completed, laps_to_finish, lap_starts)

    def test_laps_to_go_by_the_lap_limit(self):
        # 4 of 13 done, a quarter into the fifth (80 s laps): 8.75 to go.
        self.assertAlmostEqual(self.state(4, 200_000).laps_to_go, 8.75)

    def test_laps_to_go_by_the_time_limit(self):
        # 5 minutes left at 80 s laps: 3.75 laps fit; the lap in which time runs out is
        # finished, so 4 more laps from the start of this one, a quarter of it driven.
        state = self.state(4, 200_000, laps_to_finish=99, time_limit=4 * 800_000 + 200_000 + 3_000_000)
        self.assertAlmostEqual(state.laps_to_go, 3.75)

    def test_unknown_before_a_lap_time(self):
        self.assertIsNone(self.state(0, 100_000).laps_to_go)

    def test_margin_and_section(self):
        car = race.CarState(True, 42_000, 168_000, True, 0, 0.0, fuel_per_lap=10_000)  # 12.6 laps of fuel
        self.assertAlmostEqual(race.fuel_margin(car, 8.6), 4.0)
        spare = race.car_sections(car, 8.6)['fuelfinish'][0]
        short = race.car_sections(car, 14.0)['fuelfinish'][0]
        self.assertEqual((spare.text, spare.color), ('Finish +4.0 laps', 'ahead'))
        self.assertEqual((short.text, short.color), ('Finish -1.4 laps', 'behind'))
        self.assertEqual(race.car_sections(car)['fuelfinish'][0].text, 'Finish -')


class LapColourTests(unittest.TestCase):
    """The last and best lap's colours, as on F1's timing screens."""

    PURPLE = race.SESSION_BEST_COLOR

    @staticmethod
    def me(*laps, others=()):
        """The local player's state after `laps` (seconds each); `others` are the other
        drivers' lap times in seconds, each a list, all starting at 0."""
        starts = [0]
        for lap in laps:
            starts.append(starts[-1] + round(lap * 10_000))
        players = []
        for times in others:
            passes = [0]
            for lap in times:
                passes.append(passes[-1] + round(lap * 10_000))
            players.append(race.PlayerState('other', 0, len(times), tuple((at, at + 1) for at in passes)))
        players.append(race.PlayerState('me', 0, len(laps), tuple((at,) for at in starts), local=True))
        return race.LapState(
            clock=starts[-1] + 1,
            time_limit=0,
            laps_completed=len(laps),
            laps_to_finish=20,
            lap_starts=starts,
            players=tuple(players),
        )

    def test_nothing_before_the_first_lap(self):
        self.assertEqual(race.lap_colours(self.me()), (None, None))

    def test_alone_every_best_lap_is_purple(self):
        self.assertEqual(race.lap_colours(self.me(80.0)), (self.PURPLE, self.PURPLE))
        self.assertEqual(race.lap_colours(self.me(80.0, 79.0)), (self.PURPLE, self.PURPLE))

    def test_a_slower_lap_is_white_and_the_best_stays_purple(self):
        self.assertEqual(race.lap_colours(self.me(79.0, 80.0, others=[[81.0]])), ('text', self.PURPLE))

    def test_a_lap_as_fast_as_the_best_is_no_improvement(self):
        self.assertEqual(race.lap_colours(self.me(79.0, 79.0)), ('text', self.PURPLE))

    def test_someone_faster_turns_the_best_green(self):
        self.assertEqual(race.lap_colours(self.me(80.0, others=[[79.0]])), ('ahead', 'ahead'))
        self.assertEqual(race.lap_colours(self.me(80.0, 81.0, others=[[79.0]])), ('text', 'ahead'))

    def test_a_personal_best_short_of_the_fastest_is_green(self):
        self.assertEqual(race.lap_colours(self.me(82.0, 80.0, others=[[79.0, 79.5]])), ('ahead', 'ahead'))

    def test_beating_the_fastest_makes_both_purple_again(self):
        self.assertEqual(
            race.lap_colours(self.me(80.0, 78.0, others=[[79.0, 79.5]])), (self.PURPLE, self.PURPLE)
        )

    def test_an_equal_time_belongs_to_whoever_set_it_first(self):
        # Theirs on their first lap (done at 79 s), mine on my second (done at 160 s).
        self.assertEqual(race.lap_colours(self.me(81.0, 79.0, others=[[79.0]])), ('ahead', 'ahead'))
        # Mine first (79 s), theirs later (181 s).
        self.assertEqual(race.lap_colours(self.me(79.0, others=[[102.0, 79.0]])), (self.PURPLE, self.PURPLE))

    def test_others_without_a_lap_change_nothing(self):
        self.assertEqual(race.lap_colours(self.me(80.0, others=[[]])), (self.PURPLE, self.PURPLE))

    @staticmethod
    def at(state, seconds):
        """`state` with the race clock `seconds` after its last lap ended."""
        return dataclasses.replace(state, clock=state.lap_starts[-1] + round(seconds * 10_000))

    def test_the_maps_road_shows_a_fast_laps_colour_for_six_seconds(self):
        fastest = self.me(80.0, 78.0, others=[[79.0]])
        self.assertEqual(race.lap_flash(self.at(fastest, 0)), self.PURPLE)
        self.assertEqual(race.lap_flash(self.at(fastest, 5.9)), self.PURPLE)
        self.assertEqual(race.lap_flash(self.at(fastest, 6.0)), '')
        personal = self.me(82.0, 80.0, others=[[79.0]])
        self.assertEqual(race.lap_flash(self.at(personal, 1)), race.PERSONAL_BEST_COLOR)

    def test_a_slower_lap_or_none_leaves_the_road_as_it_is(self):
        self.assertEqual(race.lap_flash(self.at(self.me(79.0, 80.0), 1)), '')
        self.assertEqual(race.lap_flash(self.me()), '')

    def test_the_row_has_each_time_in_its_colour(self):
        row = race.times_row(self.me(80.0, 81.0, others=[[79.0]]))
        self.assertEqual((row.text, row.color), ('Last 1:21.000   ', 'text'))
        self.assertEqual((row.tail, row.tail_color), ('Best 1:20.000', 'ahead'))
        before = race.times_row(self.me())
        self.assertEqual(
            (before.text + before.tail, before.color, before.tail_color), ('Last -   Best -', 'text', 'text')
        )


def _passes(laps, current=(), start=0):
    """Checkpoint times per lap for a track of 3 checkpoints, one sector each: `laps` are
    whole laps as [s1, s2, s3] seconds, `current` the sectors done on the lap being driven."""
    unit, at, out = 10_000, start, []
    for lap in laps:
        out.append((at, at + round(lap[0] * unit), at + round((lap[0] + lap[1]) * unit)))
        at += round(sum(lap) * unit)
    passes = [at]
    for sector in current[:2]:
        passes.append(passes[-1] + round(sector * unit))
    out.append(tuple(passes))
    return out


class SectorTests(unittest.TestCase):
    """The sector bars below the last and best lap, as on F1's timing screens."""

    PURPLE, GREEN, YELLOW = race.SESSION_BEST_COLOR, race.PERSONAL_BEST_COLOR, race.SECTOR_SLOW_COLOR
    GATES = (((0, 0), (1, 1)),) * 3

    def state(self, laps, current=(), after=1.0, others=(), finished=False, gates=GATES):
        mine = _passes(laps, current)
        players = [race.PlayerState('other', 0, len(theirs), tuple(_passes(theirs))) for theirs in others]
        players.append(race.PlayerState('me', 0, len(laps), tuple(mine), local=True))
        return race.LapState(
            clock=mine[-1][-1] + round(after * 10_000),
            time_limit=0,
            laps_completed=len(laps),
            laps_to_finish=20,
            lap_starts=[lap[0] for lap in mine],
            checkpoints=tuple(mine),
            gates=gates,
            players=tuple(players),
            finished=finished,
        )

    def test_without_sector_lines_a_lap_has_three_even_sectors(self):
        self.assertEqual(race.sector_starts(0), ())
        self.assertEqual(race.sector_starts(1), (0,))
        self.assertEqual(race.sector_starts(2), (0, 1))
        self.assertEqual(race.sector_starts(3), (0, 1, 2))
        self.assertEqual(race.sector_starts(10), (0, 3, 6))
        self.assertEqual(race.sector_starts(120), (0, 40, 80))

    def test_the_tracks_sector_lines_make_the_sectors(self):
        # As on the track seen on 2026-11-10: 68 checkpoints, sector lines at 15, 28 and 38.
        self.assertEqual(race.sector_starts(68, (15, 28, 38)), (0, 15, 28, 38))
        self.assertEqual(race.sector_starts(68, (38, 15, 28, 15)), (0, 15, 28, 38))
        # The start line is a sector's start anyway; a line past the lap's end is not one.
        self.assertEqual(race.sector_starts(68, (0, 40, 90)), (0, 40))

    def test_a_track_with_sector_lines_has_a_bar_for_each_sector(self):
        gates = (((0, 0), (1, 1)),) * 6
        state = dataclasses.replace(self.state([], [20.0, 10.0, 10.0], gates=gates), sector_lines=(2, 4))
        self.assertEqual(race.sector_colours(state), (self.PURPLE, None, None))

    def test_the_first_lap_fills_in_as_it_is_driven(self):
        self.assertEqual(race.sector_colours(self.state([])), (None, None, None))
        self.assertEqual(race.sector_colours(self.state([], [20.0])), (self.PURPLE, None, None))

    def test_slower_than_the_drivers_best_is_yellow_and_faster_purple(self):
        lap = [20.0, 30.0, 25.0]
        self.assertEqual(
            race.sector_colours(self.state([lap], [21.0, 29.0], after=7)), (self.YELLOW, self.PURPLE, None)
        )

    def test_someone_faster_before_makes_a_personal_best_green(self):
        state = self.state([], [20.0, 30.0], others=[[[19.0, 31.0, 25.0]]])
        self.assertEqual(race.sector_colours(state), (self.GREEN, self.PURPLE, None))

    def test_someone_faster_later_turns_it_green(self):
        # Their fast first sector comes on their second lap, after mine was set: only one
        # driver has the purple sector, as with the best lap (the user, 2026-11-11).
        state = self.state([], [20.0], others=[[[30.0, 30.0, 30.0]], [[30.0, 30.0, 30.0], [10.0, 1.0, 1.0]]])
        self.assertEqual(race.sector_colours(state)[0], self.GREEN)

    def test_someone_slower_later_leaves_it_purple(self):
        state = self.state([], [20.0], others=[[[30.0, 30.0, 30.0], [25.0, 1.0, 1.0]]])
        self.assertEqual(race.sector_colours(state)[0], self.PURPLE)

    def test_as_fast_counts_for_whoever_set_it_first(self):
        earlier = self.state([], [20.0], others=[[[20.0, 30.0, 30.0]]])  # theirs ended at 20 s, mine too
        self.assertEqual(race.sector_colours(earlier)[0], self.PURPLE)  # the same moment: not beaten
        later = self.state([], [20.0], others=[[[30.0, 30.0, 30.0], [20.0, 1.0, 1.0]]])  # theirs at 110 s
        self.assertEqual(race.sector_colours(later)[0], self.PURPLE)

    def test_the_lap_just_ended_shows_for_six_seconds(self):
        laps = [[20.0, 30.0, 25.0], [21.0, 29.0, 24.0]]
        self.assertEqual(
            race.sector_colours(self.state(laps, after=5.9)), (self.YELLOW, self.PURPLE, self.PURPLE)
        )
        self.assertEqual(race.sector_colours(self.state(laps, after=6.0)), (None, None, None))

    def test_a_sector_of_the_new_lap_ends_the_last_ones_showing(self):
        laps = [[20.0, 30.0, 25.0]]
        self.assertEqual(race.sector_colours(self.state(laps, [4.0], after=1.0)), (self.PURPLE, None, None))

    def test_a_track_with_two_checkpoints_has_two_sectors(self):
        state = race.LapState(
            clock=100_000,
            time_limit=0,
            laps_completed=0,
            laps_to_finish=5,
            lap_starts=[0],
            checkpoints=((0, 50_000),),
            gates=self.GATES[:2],
        )
        self.assertEqual(race.sector_colours(state), (self.PURPLE, None))

    def test_the_option_leaves_them_out_of_the_sections(self):
        snapshot = racing(self.state([], [20.0]), read_at=0.0, moved_at=0.0)
        shown = race.race_sections(snapshot, 0.0)
        self.assertEqual(shown['levels']['times'], race.Sectors((self.PURPLE, None, None)))
        hidden = race.race_sections(snapshot, 0.0, sector_bars=False)
        self.assertNotIn('times', hidden.get('levels', {}))
        self.assertIn('times', hidden)  # the times themselves stay

    def test_after_the_finish_they_go_once_the_last_lap_has_shown(self):
        laps = [[20.0, 30.0, 25.0]]
        self.assertIsNotNone(race.sector_colours(self.state(laps, after=2, finished=True)))
        self.assertIsNone(race.sector_colours(self.state(laps, after=7, finished=True)))
        self.assertIsNone(race.sector_colours(self.state([], gates=())))


class RowsTests(unittest.TestCase):
    def test_format_tenths_cuts_off(self):
        self.assertEqual(race.format_tenths(365_459), '0:36.5')
        self.assertEqual(race.format_tenths(599_999), '0:59.9')
        self.assertEqual(race.format_tenths(600_000), '1:00.0')
        self.assertEqual(race.format_tenths(-10), '0:00.0')
        self.assertEqual(race.format_tenths(None), '-:--.-')

    def test_mid_race(self):
        rows = race.race_rows(racing(MID_RACE), now=100.0)
        self.assertEqual(
            [row.text + row.tail for row in rows],
            [
                'Lap 3/13  -  17:41 left',
                '0:21.4',
                'vs best  -',
                'Last 1:24.095   Best 1:24.095',
            ],
        )
        self.assertEqual(rows[1].color, 'accent')

    def test_the_time_left_rounds_up_like_a_countdown(self):
        state = race.LapState(clock=1, time_limit=10_002, laps_completed=0, laps_to_finish=5, lap_starts=[0])
        self.assertIn('0:02 left', race.race_rows(racing(state), 0)[0].text)

    def test_time_is_up(self):
        state = race.LapState(clock=20, time_limit=10, laps_completed=0, laps_to_finish=5, lap_starts=[0])
        self.assertIn('time is up', race.race_rows(racing(state), 0)[0].text)

    def test_no_time_limit(self):
        state = race.LapState(clock=20, time_limit=0, laps_completed=0, laps_to_finish=5, lap_starts=[0])
        self.assertEqual(race.race_rows(racing(state), 0)[0].text, 'Lap 1/5')

    def test_the_current_lap_runs_on_between_reads_while_racing(self):
        self.assertEqual(race.current_lap_now(racing(MID_RACE, running=True), 100.5), 214_455 + 5_000)
        # Not further than a second past the read; not at all while the clock stands.
        self.assertEqual(race.current_lap_now(racing(MID_RACE, running=True), 105), 214_455 + 10_000)
        self.assertEqual(race.current_lap_now(racing(MID_RACE, running=False), 100.5), 214_455)

    def test_finished(self):
        state = race.LapState(
            clock=1_800_000,
            time_limit=0,
            laps_completed=2,
            laps_to_finish=2,
            lap_starts=[0, 900_000, 1_700_000, 1_750_000],
        )
        rows = race.race_rows(racing(state), 0)
        self.assertTrue(rows[0].text.startswith('Finished'))
        self.assertEqual(rows[1].text, '1:20.000')

    def test_after_the_finish_the_rest_of_the_hud_stays_while_others_race(self):
        me = race.PlayerState('Me', 0, 2, ((0,), (900_000,), (1_700_000,)), finished=True, local=True)
        other = race.PlayerState('Other', 0, 1, ((0,), (950_000,)))
        car = race.CarState(True, 50_000, 168_000, False, 0, 20.0)
        state = race.LapState(
            clock=1_800_000,
            time_limit=0,
            laps_completed=2,
            laps_to_finish=2,
            lap_starts=[0, 900_000, 1_700_000],
            finished=True,
            car=car,
            players=(me, other),
        )
        sections = race.race_sections(racing(state), 0)
        self.assertTrue(sections['lap'][0].text.startswith('Finished'))
        self.assertIn('players', sections)
        self.assertIn('fuel', sections)
        self.assertIn('speed', sections)
        self.assertNotIn('delta', sections)  # no lap to compare any more

    def test_delta_row_is_green_ahead_and_red_behind(self):
        ahead = race.LapState(1, 0, 1, 13, [0, 900_000], checkpoints=((0, 300_000), (900_000, 1_199_000)))
        row = race.race_rows(racing(ahead), 0)[2]
        self.assertEqual((row.text + row.tail, row.color), ('\u22120.10 vs best', 'ahead'))
        self.assertEqual(row.tail_color, 'ahead')
        behind = race.LapState(1, 0, 1, 13, [0, 900_000], checkpoints=((0, 300_000), (900_000, 1_202_340)))
        row = race.race_rows(racing(behind), 0)[2]
        self.assertEqual((row.text + row.tail, row.color), ('+0.23 vs best', 'behind'))  # hundredths

    def test_a_delta_too_small_to_show_is_even(self):
        self.assertEqual(race.format_delta(-3), '0.000')
        self.assertEqual(race.format_delta(5), '+0.001')  # the player list's gaps keep thousandths
        self.assertEqual(race.format_delta(-49, 2), '0.00')
        self.assertEqual(race.format_delta(50, 2), '+0.01')
        even = race.LapState(1, 0, 1, 13, [0, 900_000], checkpoints=((0, 300_000), (900_000, 1_199_970)))
        row = race.race_rows(racing(even), 0)[2]
        self.assertEqual((row.text + row.tail, row.color), ('0.00 vs best', 'text'))

    def test_the_local_time_shows_once_tsu_runs(self):
        import time

        now = time.struct_time((2026, 11, 1, 18, 7, 0, 6, 305, 0))
        self.assertNotIn('localtime', race.with_local_time({}, race.Snapshot(race.WAITING_FOR_GAME), now))
        menu = race.with_local_time({}, race.Snapshot(race.WAITING_FOR_RACE), now)
        self.assertEqual(menu['localtime'][0].text, '18:07')
        self.assertIn('localtime', race.with_local_time({}, race.Snapshot(race.STARTING), now))

    def test_nothing_before_the_grid(self):
        for status in (race.WAITING_FOR_GAME, race.WAITING_FOR_RACE, race.STARTING):
            with self.subTest(status=status):
                self.assertEqual(race.race_sections(race.Snapshot(status), 0), {})
        lobby = race.LapState(clock=0, time_limit=0, laps_completed=0, laps_to_finish=13, lap_starts=[])
        self.assertEqual(race.race_sections(racing(lobby), 0), {})  # race made, clock not running

    def test_everything_from_the_grid_on(self):
        grid = race.LapState(
            clock=2_800, time_limit=12_660_000, laps_completed=0, laps_to_finish=13, lap_starts=[]
        )
        sections = race.race_sections(racing(grid), 0)
        self.assertEqual(sections['lap'][0].text, 'Lap 1/13  -  21:06 left')
        self.assertEqual(sections['current'][0].text, '-:--.-')

    def test_a_standing_clock_hides_the_hud(self):
        # A finished race left in memory while the lobby waits for the next one.
        old = race.LapState(
            clock=9_000_000, time_limit=0, laps_completed=13, laps_to_finish=13, lap_starts=[0]
        )
        self.assertEqual(race.race_sections(racing(old, moved_at=100.0), 103.0), {})
        self.assertNotEqual(race.race_sections(racing(old, moved_at=100.0), 101.0), {})

    def test_status_for_the_tray(self):
        self.assertIn('launch option', race.status_text(race.Snapshot(race.WAITING_FOR_GAME), 'linux'))
        self.assertEqual(
            race.status_text(
                race.Snapshot(race.WAITING_FOR_GAME, detail='CrossOver was not found'), 'darwin'
            ),
            'waiting: CrossOver was not found',
        )
        self.assertIn('CrossOver', race.status_text(race.Snapshot(race.WAITING_FOR_GAME), 'darwin'))
        self.assertEqual(race.status_text(race.Snapshot(race.WAITING_FOR_RACE)), 'waiting for a race')
        self.assertEqual(race.status_text(race.Snapshot(race.STARTING)), 'race being set up')
        import time

        self.assertEqual(race.status_text(racing(MID_RACE, moved_at=time.monotonic())), 'racing')


class YellowFlagTests(unittest.TestCase):
    """Yellow flags from every car's speed, wheel surfaces and respawns (asked for by
    the user on 2026-11-11; what TSU keeps of other cars online: experiments/README.md)."""

    TARMAC, KERB, GRASS = (1.0,) * 4, (0.93,) * 4, (0.5,) * 4
    GATES = (((0, 0), (1, 1)),) * 9  # sectors start at checkpoints 0, 3 and 6

    def car(self, name='Other', speed=40.0, grips=TARMAC, passed=4, local=False, **more):
        lap = tuple(1000 * i for i in range(passed + 1))
        return race.PlayerState(
            name, 0, 1, ((0,), lap), local=local, forward_speed=speed, wheel_grips=grips, **more
        )

    def state(self, seconds, *others, me_passed=4):
        return race.LapState(
            clock=round(seconds * race.UNITS_PER_SECOND),
            time_limit=0,
            laps_completed=1,
            laps_to_finish=20,
            lap_starts=[0, 0],
            players=(*others, self.car('Me', local=True, passed=me_passed)),
            gates=self.GATES,
        )

    def drive(self, flags, seconds, *others, **more):
        return flags.update(self.state(seconds, *others, **more))

    def kinds(self, incidents):
        return [(incident.name, incident.kind) for incident in incidents]

    def test_all_four_wheels_off_the_tarmac_after_half_a_second(self):
        flags = race.YellowFlags()
        self.assertEqual(self.drive(flags, 10.0, self.car(grips=self.GRASS)), ())
        self.assertEqual(
            self.kinds(self.drive(flags, 10.6, self.car(grips=self.GRASS))), [('Other', 'off track')]
        )

    def test_kerbs_one_wheel_on_tarmac_or_a_wheel_in_the_air_are_not_off(self):
        for grips in (self.KERB, (1.0, 0.5, 0.5, 0.5), (0.0, 0.5, 0.5, 0.5)):
            flags = race.YellowFlags()
            self.drive(flags, 10.0, self.car(grips=grips))
            self.assertEqual(self.drive(flags, 12.0, self.car(grips=grips)), (), grips)

    # As read on the user's circuit (2026-11-11): grip and Unity layer of each surface.
    PLASTIC: ClassVar[dict] = {'grips': (0.8999,) * 4, 'wheel_layers': (24,) * 4}  # the wide plastic kerbs
    TERRAIN: ClassVar[dict] = {'grips': (0.5,) * 4, 'wheel_layers': (18,) * 4}  # the grass beside the track
    CONCRETE: ClassVar[dict] = {'grips': (1.0,) * 4, 'wheel_layers': (22,) * 4}  # the run-off, used as track
    CURB: ClassVar[dict] = {'grips': (0.8,) * 4, 'wheel_layers': (17,) * 4}

    def test_plastic_kerbs_curbs_and_concrete_are_track_by_their_layer(self):
        # Reported by the user: the wide plastic kerbs (grip 0.9, just under the old limit) raised
        # yellow flags. By the surface's layer they are track, as the user drives them.
        for surface in (self.PLASTIC, self.CONCRETE, self.CURB):
            flags = race.YellowFlags()
            self.drive(flags, 10.0, self.car(**surface))
            self.assertEqual(self.drive(flags, 12.0, self.car(**surface)), (), surface)

    def test_terrain_is_off_the_track_by_its_layer(self):
        flags = race.YellowFlags()
        self.drive(flags, 10.0, self.car(**self.TERRAIN))
        self.assertEqual(
            self.kinds(self.drive(flags, 10.6, self.car(**self.TERRAIN))), [('Other', 'off track')]
        )

    def test_a_wheel_on_plastic_or_in_the_air_keeps_a_car_on_the_terrain_on_the_track(self):
        for grips, layers in (
            ((0.8999, 0.5, 0.5, 0.5), (24, 18, 18, 18)),
            ((0.0, 0.5, 0.5, 0.5), (None, 18, 18, 18)),
        ):
            flags = race.YellowFlags()
            self.drive(flags, 10.0, self.car(grips=grips, wheel_layers=layers))
            self.assertEqual(self.drive(flags, 12.0, self.car(grips=grips, wheel_layers=layers)), ())

    def stand(self, flags, start, end, step=5.0, **car):
        """Drive the clock from `start` to `end` with the car as given; the last incidents."""
        found, seconds = (), start
        while seconds <= end:
            found = self.drive(flags, seconds, self.car(**car))
            seconds += step
        return self.kinds(found)

    def test_a_car_left_standing_has_no_flag_after_a_minute(self):
        # Seen by the user on 2026-11-12: a driver stopped on the track and left the race, and
        # the yellow flag stayed out for the rest of it.
        flags = race.YellowFlags()
        self.assertEqual(self.stand(flags, 10.0, 15.0, speed=0.0), [('Other', 'stopped')])
        self.assertEqual(self.stand(flags, 20.0, 65.0, speed=0.0), [('Other', 'stopped')])  # 55 s: still out
        self.assertEqual(self.stand(flags, 70.0, 80.0, speed=0.0), [])  # over a minute: idle

    def test_an_idle_car_stays_without_a_flag_until_faster_than_29_kmh(self):
        flags = race.YellowFlags()
        self.stand(flags, 10.0, 80.0, speed=0.0)
        slow = race.YELLOW_SLOW - 0.5  # rolling along, just under 29 km/h
        self.assertEqual(self.stand(flags, 85.0, 100.0, speed=slow), [])
        self.assertEqual(self.stand(flags, 105.0, 120.0, speed=0.0), [])  # stopped again: still idle
        self.assertEqual(self.stand(flags, 125.0, 130.0, speed=race.YELLOW_SLOW + 1), [])  # back racing
        stopped = self.stand(flags, 135.0, 140.0, speed=0.0)
        self.assertEqual(stopped, [('Other', 'stopped')])  # a new stop: flagged

    def test_backwards_faster_than_29_kmh_counts_as_racing_again(self):
        flags = race.YellowFlags()
        self.stand(flags, 10.0, 80.0, speed=0.0)
        backwards = -(race.YELLOW_SLOW + 1)
        self.assertEqual(self.stand(flags, 85.0, 86.0, step=0.5, speed=backwards), [('Other', 'spun')])

    def test_a_long_pit_stop_or_the_grid_does_not_make_a_car_idle(self):
        flags = race.YellowFlags()
        self.stand(flags, 10.0, 100.0, speed=0.0, in_pit=True)
        self.assertEqual(self.stand(flags, 105.0, 110.0, speed=0.0), [('Other', 'stopped')])
        flags = race.YellowFlags()
        on_grid = race.PlayerState('Other', 0, 0, ((0,),), forward_speed=0.0, wheel_grips=self.TARMAC)
        for seconds in range(10, 101, 5):  # only the start line passed: the countdown
            self.drive(flags, float(seconds), on_grid)
        self.assertEqual(self.stand(flags, 105.0, 110.0, speed=0.0), [('Other', 'stopped')])

    def test_a_speed_not_read_keeps_the_count(self):
        flags = race.YellowFlags()
        self.stand(flags, 10.0, 40.0, speed=0.0)
        self.stand(flags, 45.0, 60.0, speed=None)
        self.assertEqual(self.stand(flags, 65.0, 75.0, speed=0.0), [])  # idle since 10 s

    def test_a_car_stopped_on_plastic_stands_on_the_road(self):
        self.assertTrue(race.on_tarmac(self.car(speed=0.0, **self.PLASTIC)))
        self.assertFalse(race.on_tarmac(self.car(speed=0.0, **self.TERRAIN)))
        self.assertTrue(race.on_tarmac(self.car(speed=0.0, grips=self.TARMAC)))  # no layers: by grip
        self.assertFalse(race.on_tarmac(self.car(speed=0.0, grips=self.GRASS)))

    def test_the_reader_gives_each_wheels_grip_and_layer(self):
        plastic, terrain = (0.8999, 24), (0.5, 18)
        reader = build(
            [10_000],
            laps_completed=0,
            clock=20_000,
            limit=0,
            car=(5.0, 7.0),
            surfaces=(plastic, plastic, terrain, None),
        )
        me = next(p for p in reader.read().players if p.local)
        self.assertEqual([round(g, 4) for g in me.wheel_grips], [0.8999, 0.8999, 0.5, 0.0])
        self.assertEqual(me.wheel_layers, (24, 24, 18, None))

    def test_a_wrecked_car_counts_at_once_and_first(self):
        # Asked for by the user on 2026-11-11: a car that lost all its hit points (damage on).
        flags = race.YellowFlags()
        found = self.drive(flags, 10.0, self.car(speed=0.0, wrecked=True))
        self.assertEqual(self.kinds(found), [('Other', 'wrecked')])

    def test_the_reader_sees_a_car_with_no_hit_points_left_as_wrecked(self):
        def local(health):
            reader = build([10_000], laps_completed=0, clock=20_000, limit=0, car=(5.0, 7.0), health=health)
            return next(p for p in reader.read().players if p.local)

        self.assertTrue(local(0).wrecked)
        self.assertFalse(local(120).wrecked)
        self.assertFalse(local(None).wrecked)  # no damage: the hit points stay at the most

    def test_slow_after_a_second_stopped_after_two(self):
        flags = race.YellowFlags()
        self.drive(flags, 10.0, self.car(speed=0.2))
        self.assertEqual(self.kinds(self.drive(flags, 11.1, self.car(speed=0.2))), [('Other', 'slow')])
        stopped = self.drive(flags, 12.1, self.car(speed=0.2))
        self.assertEqual(self.kinds(stopped), [('Other', 'stopped')])

    def test_going_backwards_is_a_spin(self):
        flags = race.YellowFlags()
        self.drive(flags, 10.0, self.car(speed=-5.0))
        self.assertEqual(self.kinds(self.drive(flags, 10.4, self.car(speed=-5.0))), [('Other', 'spun')])

    def test_moving_against_the_race_for_a_second_and_a_half_is_driving_the_wrong_way(self):
        # Asked for by the user on 2026-11-11 (a "ghost driver"): the race goes along +x here.
        def heading(position, hint):
            return (1.0, 0.0), (hint or 0) + 1

        flags = race.YellowFlags()
        against = {'position': (0.0, 0.0), 'velocity': (-30.0, 5.0)}
        found = self.drive(flags, 10.0, self.car(**against))
        for seconds in (12.0, 13.0):
            found = self.drive(flags, seconds, self.car(**against))
        self.assertEqual(found, ())  # without a heading (no learnt track) it is not known
        flags = race.YellowFlags()
        for seconds in (10.0, 11.4):
            found = flags.update(self.state(seconds, self.car(**against)), heading)
        self.assertEqual(found, ())  # not yet a second and a half
        self.assertEqual(flags._cars['Other']['hint'], 2)  # the hint goes on from one look to the next
        found = flags.update(self.state(11.6, self.car(**against)), heading)
        self.assertEqual(self.kinds(found), [('Other', 'wrong way')])
        rows = race.yellow_rows(found, self.state(11.6, self.car(**against), me_passed=4))
        self.assertTrue(rows[-1].text.endswith('Other  wrong way'))

    def test_the_sector_is_where_the_car_is_once_the_road_is_known(self):
        # Reported by the user on 2026-11-11: a car driving backwards kept the yellow sector it turned
        # round in, as it crosses no line going backwards. Its last line passed is 4 (sector 2), but the
        # road puts it back past line 2 (sector 1).
        def heading(position, hint):
            return (1.0, 0.0), 20  # the race goes along +x; the learnt line's point 20

        def gate_at(point, gates):
            return 2 if point == 20 else None

        flags = race.YellowFlags()
        back = {'position': (0.0, 0.0), 'velocity': (-30.0, 0.0)}
        for seconds in (10.0, 11.6):
            found = flags.update(self.state(seconds, self.car(passed=4, **back)), heading, gate_at)
        self.assertEqual([(i.kind, i.sector) for i in found], [('wrong way', 0)])
        found = flags.update(self.state(11.7, self.car(passed=4, **back)), heading)  # no road: as before
        self.assertEqual([(i.kind, i.sector) for i in found], [('wrong way', 1)])

    def test_wrong_way_beats_a_spin_but_not_sliding_on_or_crawling_back(self):
        def heading(position, hint):
            return (1.0, 0.0), 0

        flags = race.YellowFlags()
        reversing = {'position': (0.0, 0.0), 'velocity': (-30.0, 0.0), 'speed': -30.0}
        flags.update(self.state(10.0, self.car(**reversing)), heading)
        spun = flags.update(self.state(10.4, self.car(**reversing)), heading)
        self.assertEqual(self.kinds(spun), [('Other', 'spun')])  # at first a spin
        wrong = flags.update(self.state(11.6, self.car(**reversing)), heading)
        self.assertEqual(self.kinds(wrong), [('Other', 'wrong way')])  # it goes on: the wrong way
        for car, why in (
            ({'position': (0.0, 0.0), 'velocity': (30.0, 0.0), 'speed': -30.0}, 'faces back, slides on'),
            ({'position': (0.0, 0.0), 'velocity': (-5.0, 0.0)}, 'slower than YELLOW_SLOW'),
            ({'position': (0.0, 0.0), 'velocity': (-10.0, 30.0)}, 'across the track, not against it'),
        ):
            flags = race.YellowFlags()
            for seconds in (10.0, 11.0, 12.0):
                found = flags.update(self.state(seconds, self.car(**car)), heading)
            self.assertNotIn('wrong way', [incident.kind for incident in found], why)
        flags = race.YellowFlags()
        for seconds in (10.0, 12.0):
            found = flags.update(self.state(seconds, self.car(**reversing)), lambda position, hint: None)
        self.assertEqual(self.kinds(found), [('Other', 'spun')])  # no learnt track: not known

    def test_the_sectors_with_incidents_for_the_map(self):
        state = self.state(10.0)
        starts = race.sector_starts(len(state.gates), state.sector_lines)
        spans = race.yellow_sector_spans(
            (
                race.Incident('A', 'stopped', 0),
                race.Incident('B', 'slow', 0),
                race.Incident('C', 'slow', None),
            ),
            state,
        )
        self.assertEqual(spans, {(starts[0], starts[1 % len(starts)])})
        last = len(starts) - 1
        self.assertEqual(
            race.yellow_sector_spans((race.Incident('A', 'slow', last),), state), {(starts[last], 0)}
        )
        self.assertEqual(race.yellow_sector_spans((), state), frozenset())

    def hazard_state(self, seconds, *others, me_speed=30.0):
        state = self.state(seconds, *others)
        players = tuple(
            dataclasses.replace(p, position=(0.0, 0.0), forward_speed=me_speed) if p.local else p
            for p in state.players
        )
        return dataclasses.replace(state, players=players)

    @staticmethod
    def along_x(a, b):
        return b[0] - a[0] if b[0] >= a[0] else 1000.0  # ahead on the road: further along x

    def test_a_stopped_car_on_the_tarmac_a_few_seconds_ahead_is_a_hazard(self):
        # Asked for by the user on 2026-11-11, in place of an automatic full course yellow.
        flags = race.YellowFlags()
        near = self.car('Stuck', speed=0.0, position=(100.0, 0.0))  # 100 units: 3.3 s at 30
        incident = race.Incident('Stuck', 'stopped', 0)
        state = self.hazard_state(10.0, near)
        self.assertEqual(flags.hazard(state, (incident,), self.along_x), ('CAR STOPPED AHEAD', incident))
        far = self.car('Stuck', speed=0.0, position=(200.0, 0.0))  # 6.7 s: not yet
        self.assertIsNone(race.YellowFlags().hazard(self.hazard_state(10.0, far), (incident,), self.along_x))
        behind = self.car('Stuck', speed=0.0, position=(-10.0, 0.0))
        self.assertIsNone(
            race.YellowFlags().hazard(self.hazard_state(10.0, behind), (incident,), self.along_x)
        )
        self.assertIsNone(race.YellowFlags().hazard(state, (incident,), None))  # no learnt track
        slow = race.Incident('Stuck', 'slow', 0)
        self.assertIsNone(race.YellowFlags().hazard(state, (slow,), self.along_x))  # slow is no hazard

    def test_a_car_parked_on_the_grass_is_no_hazard_but_one_going_the_wrong_way_is(self):
        parked = self.car('Afk', speed=0.0, grips=self.GRASS, position=(50.0, 0.0))
        stopped = race.Incident('Afk', 'stopped', 0)
        self.assertIsNone(
            race.YellowFlags().hazard(self.hazard_state(10.0, parked), (stopped,), self.along_x)
        )
        ghost = self.car('Ghost', speed=30.0, grips=self.GRASS, position=(50.0, 0.0))
        wrong = race.Incident('Ghost', 'wrong way', 0)
        found = race.YellowFlags().hazard(self.hazard_state(10.0, ghost), (wrong,), self.along_x)
        self.assertEqual(found, ('WRONG WAY AHEAD', wrong))

    def test_the_nearest_hazard_and_a_warning_that_never_blinks(self):
        flags = race.YellowFlags()
        a = self.car('A', speed=0.0, position=(120.0, 0.0))
        b = self.car('B', speed=0.0, position=(60.0, 0.0))
        incidents = (race.Incident('A', 'stopped', 0), race.Incident('B', 'stopped', 0))
        found = flags.hazard(self.hazard_state(10.0, a, b), incidents, self.along_x)
        self.assertEqual(found[1].name, 'B')
        gone = self.hazard_state(11.0, a, b)
        self.assertEqual(flags.hazard(gone, (), self.along_x), found)  # kept a moment
        self.assertIsNone(flags.hazard(self.hazard_state(12.1, a, b), (), self.along_x))

    def test_the_hazard_heads_the_yellow_box_with_its_car_first(self):
        state = self.state(10.0, me_passed=4)
        far = race.Incident('Far away', 'stopped', 5)  # outside the player's sectors, yet ahead
        rows = race.yellow_rows((far,), state, ('CAR STOPPED AHEAD', far))
        self.assertEqual(rows[0].text, 'CAR STOPPED AHEAD')
        self.assertTrue(rows[0].centred)
        self.assertIn('Far away  stopped', rows[1].text)
        self.assertEqual(race.yellow_rows((far,), state), [])  # without the hazard: not in its sectors

    def test_a_respawn_counts_for_three_seconds(self):
        flags = race.YellowFlags()
        self.drive(flags, 10.0, self.car(spawns=0))
        self.assertEqual(self.kinds(self.drive(flags, 10.1, self.car(spawns=1))), [('Other', 'respawned')])
        self.assertEqual(self.drive(flags, 13.2, self.car(spawns=1)), ())

    def test_the_flag_stays_three_seconds_after_the_car_is_back(self):
        flags = race.YellowFlags()
        self.drive(flags, 10.0, self.car(grips=self.GRASS))
        self.drive(flags, 10.6, self.car(grips=self.GRASS))
        self.assertEqual(len(self.drive(flags, 12.0, self.car())), 1)  # back on the tarmac 1.4 s
        self.assertEqual(self.drive(flags, 13.7, self.car()), ())

    def test_racing_cars_have_none(self):
        flags = race.YellowFlags()
        for step in range(50):
            self.assertEqual(self.drive(flags, 10 + step / 10, self.car(speed=35.0)), ())

    def test_not_for_me_in_the_pits_finished_or_on_the_grid(self):
        for car in (
            self.car(speed=0.0, in_pit=True),
            self.car(speed=0.0, finished=True),
            race.PlayerState('Other', 0, 0, ((0,),), forward_speed=0.0, wheel_grips=self.TARMAC),  # the grid
        ):
            flags = race.YellowFlags()
            self.drive(flags, 10.0, car)
            self.assertEqual(self.drive(flags, 13.0, car), ())
        flags = race.YellowFlags()
        me = race.LapState(clock=0, time_limit=0, laps_completed=1, laps_to_finish=20, lap_starts=[0, 0])
        pitted = dataclasses.replace(  # my own car counts too, but not in the pits
            me, players=(self.car('Me', speed=0.0, local=True, in_pit=True),), gates=self.GATES
        )
        flags.update(pitted)
        self.assertEqual(flags.update(dataclasses.replace(pitted, clock=3 * race.UNITS_PER_SECOND)), ())

    def test_my_own_incident_flags_me_too(self):
        # Asked for by the user on 2026-11-11: the driver who caused the flag sees it as well.
        flags = race.YellowFlags()
        me = race.LapState(
            clock=0, time_limit=0, laps_completed=1, laps_to_finish=20, lap_starts=[0, 0], gates=self.GATES
        )
        on_grass = (self.car('Me', grips=self.GRASS, local=True),)
        flags.update(dataclasses.replace(me, players=on_grass))
        later = dataclasses.replace(me, players=on_grass, clock=round(0.6 * race.UNITS_PER_SECOND))
        found = flags.update(later)
        self.assertEqual(self.kinds(found), [('Me', 'off track')])
        rows = race.yellow_rows(found, later)
        self.assertEqual(rows[0].text, 'YELLOW  -  Sector 2')
        self.assertTrue(rows[1].text.endswith('Me  off track'))

    def test_my_own_stopped_car_is_no_hazard_ahead(self):
        flags = race.YellowFlags()
        state = self.hazard_state(10.0, me_speed=0.0)
        mine = race.Incident('Me', 'stopped', 1)
        self.assertIsNone(flags.hazard(state, (mine,), self.along_x))

    def test_turned_off_and_on_again_it_starts_afresh(self):
        flags = race.YellowFlags()
        self.drive(flags, 10.0, self.car(speed=0.2))
        flags.reset()  # the option was off meanwhile
        self.assertEqual(self.drive(flags, 13.0, self.car(speed=0.2)), ())  # not stopped for 3 s: just seen
        self.assertEqual(self.kinds(self.drive(flags, 15.1, self.car(speed=0.2))), [('Other', 'stopped')])

    def test_the_section_shows_my_sector_and_the_next(self):
        state = self.state(10.0, me_passed=4)  # I am in sector 2 (checkpoints 3 to 5)
        incidents = (
            race.Incident('Far', 'stopped', 0),
            race.Incident('Here', 'off track', 1),
            race.Incident('Next', 'slow', 2),
        )
        rows = race.yellow_rows(incidents, state)
        self.assertEqual(rows[0].text, 'YELLOW  -  Sector 2')  # the stopped car is behind me
        self.assertEqual([row.text for row in rows[1:]], ['S2  Here  off track', 'S3  Next  slow'])
        self.assertEqual({row.color for row in rows}, {race.YELLOW_TEXT})  # dark, on the yellow background

    def test_a_stopped_car_ahead_is_a_plain_yellow(self):
        # Asked for by the user on 2026-11-11: no double yellow.
        rows = race.yellow_rows((race.Incident('Ahead', 'stopped', 2),), self.state(10.0, me_passed=4))
        self.assertEqual(rows[0].text, 'YELLOW  -  Sector 3')
        self.assertEqual(rows[1].text, 'S3  Ahead  stopped')

    def test_from_the_last_sector_the_next_is_the_first(self):
        rows = race.yellow_rows((race.Incident('Over the line', 'spun', 0),), self.state(10.0, me_passed=7))
        self.assertEqual(rows[1].text, 'S1  Over the line  spun')

    def test_nothing_near_no_section(self):
        self.assertEqual(
            race.yellow_rows((race.Incident('Far', 'slow', 0),), self.state(10.0, me_passed=4)), []
        )
        self.assertEqual(race.yellow_rows((), self.state(10.0)), [])

    def test_the_track_map_rings_the_car_even_with_other_cars_hidden(self):
        from turbohud.core.trackmap import TrackMap

        track_map = TrackMap(others=False, folder=None)
        players = [
            race.PlayerState(name, 0, 1, ((0,),), local=name == 'Me', position=(float(i), 0.0))
            for i, name in enumerate(['Leader', 'Me', 'Behind', 'Far back', 'Flagged'])
        ]
        state = race.LapState(clock=0, time_limit=0, laps_completed=1, laps_to_finish=5, lap_starts=[0])
        with mock.patch.object(TrackMap, 'outline', lambda self, order, gates, length: 'outline'):
            view = track_map.update(state, players, yellow=frozenset({'Flagged'}))
        flagged = [dot for dot in view.dots if dot.yellow]
        self.assertEqual([dot.position for dot in flagged], [(4.0, 0.0)])
        self.assertNotIn(
            (3.0, 0.0), [dot.position for dot in view.dots]
        )  # an unflagged other car stays hidden
        self.assertFalse(view.dots[-1].yellow)  # my own dot, not flagged
        with mock.patch.object(TrackMap, 'outline', lambda self, order, gates, length: 'outline'):
            view = track_map.update(state, players, yellow=frozenset({'Me'}))
        self.assertEqual((view.dots[-1].role, view.dots[-1].yellow), ('me', True))  # asked for by the user


class LiveRaceTests(unittest.TestCase):
    def setUp(self):
        from turbohud.tsu import client

        self.client = client
        self.now = 50.0

    def live(self, connect):
        return self.client.LiveRace(connect=connect, clock=lambda: self.now)

    def test_without_tsu_it_waits_for_the_game(self):
        def connect():
            raise FileNotFoundError('no socket')

        live = self.live(connect)
        self.assertEqual(live.step(), self.client.WAIT_INTERVAL)
        self.assertEqual(live.snapshot().status, race.WAITING_FOR_GAME)

    def test_each_race_read_is_announced_with_the_new_snapshot_in_place(self):
        class Reader:
            def read(self):
                return MID_RACE

        live = self.live(lambda: (Reader(), None))
        seen = []
        live.on_read = lambda: seen.append(live.snapshot().status)
        live.step()
        live.step()
        self.assertEqual(seen, [race.RACING, race.RACING])

    def test_no_announcement_without_a_race(self):
        def connect():
            raise FileNotFoundError('no socket')

        live = self.live(connect)
        seen = []
        live.on_read = lambda: seen.append(1)
        live.step()
        self.assertEqual(seen, [])

    def test_while_a_race_is_set_up_it_says_race_starting(self):
        class Reader:
            def read(self):
                raise il.NotFound('m_eventListener is null')

        live = self.live(lambda: (Reader(), None))
        self.assertEqual(live.step(), self.client.READ_INTERVAL)
        self.assertEqual(live.snapshot().status, race.STARTING)

    def test_a_new_reason_for_no_race_is_logged_at_most_every_10_s(self):
        reasons = ['m_activeServer is null']

        class Reader:
            def read(self):
                raise il.NotFound(reasons[0])

        live = self.live(lambda: (Reader(), None))
        with self.assertLogs('turbohud.tsu.client', 'INFO') as logs:
            live.step()
            reasons[0] = 'implausible list size'  # a race found but not read
            self.now += 1
            live.step()  # too soon after the last line
            self.now += 10
            live.step()
            live.step()  # the same reason: no line
        self.assertEqual(
            logs.output,
            [
                'INFO:turbohud.tsu.client:TSU: waiting for race (m_activeServer is null)',
                'INFO:turbohud.tsu.client:TSU: still waiting for race (implausible list size)',
            ],
        )

    def test_in_the_menu_it_waits_for_a_race_and_keeps_the_connection(self):
        calls = []

        class Reader:
            def read(self):
                raise il.NotFound('m_activeServer is null')

        def connect():
            calls.append(1)
            return Reader(), None

        live = self.live(connect)
        live.step()
        live.step()
        self.assertEqual(live.snapshot().status, race.WAITING_FOR_RACE)
        self.assertEqual(len(calls), 1)

    def test_a_dropped_connection_says_why_in_the_log(self):
        closed = []

        class Conn:
            def close(self):
                closed.append(1)

        class Reader:
            def read(self):
                raise OSError('cannot read 8 bytes at 0x10')

        live = self.live(lambda: (Reader(), Conn()))
        with self.assertLogs('turbohud.tsu.client', 'INFO') as logs:
            self.assertEqual(live.step(), self.client.WAIT_INTERVAL)
        self.assertEqual(closed, [1])
        self.assertTrue(
            any('connection dropped (OSError: cannot read 8 bytes at 0x10)' in m for m in logs.output)
        )

    def test_no_connection_to_drop_logs_no_drop(self):
        def connect():
            raise FileNotFoundError('no socket')

        live = self.live(connect)
        live.step()  # the first status change logs
        with self.assertNoLogs('turbohud.tsu.client', 'INFO'):
            live.step()

    def reading(self, durations):
        """A LiveRace whose reader takes these many seconds, one read after another."""
        durations = iter(durations)
        tester = self

        class Reader:
            def read(self):
                tester.now += next(durations)
                return race.LapState(1000, 0, 0, 13, [0])

        return self.live(lambda: (Reader(), None))

    def test_the_log_says_how_long_race_reads_take(self):
        live = self.reading([9.0, 0.01, 0.02, 0.06])  # the first also finds the race
        with self.assertLogs('turbohud.tsu.client', 'INFO') as logs:
            for _ in range(4):
                live.step()
                self.now += 15.0
        line = next(m for m in logs.output if 'race reads' in m)
        self.assertIn('3 in 30 s', line)
        self.assertIn('median 20.0 ms', line)
        self.assertIn('slowest 60.0 ms', line)
        self.assertIn('1 over 50 ms', line)

    def test_the_log_says_how_many_trips_a_read_made_where_that_is_known(self):
        from turbohud.tsu.client import ReadTimes

        times = ReadTimes(lambda: 100.0)
        for trips in (100, 100, 200):
            times.add(0.1, (trips, 0.02))
        with self.assertLogs('turbohud.tsu.client', 'INFO') as logs:
            times.flush()
        self.assertIn('100 trips a read, 1.00 ms a trip, 0.20 ms of it on the game', logs.output[0])
        self.assertNotIn('reads of it', logs.output[0])

    def test_the_log_says_how_many_reads_of_the_game_a_read_made(self):
        from turbohud.tsu.client import ReadTimes

        times = ReadTimes(lambda: 100.0)
        for calls in (8, 9, 30):
            times.add(0.01, (2, 0.008, calls))
        with self.assertLogs('turbohud.tsu.client', 'INFO') as logs:
            times.flush()
        self.assertIn(
            '2 trips a read, 5.00 ms a trip, 4.00 ms of it on the game\'s memory, 9 reads of it a read',
            logs.output[0],
        )

    def test_the_reading_thread_gets_python_s_lock_quickly(self):
        import sys

        from turbohud.tsu import client

        before = sys.getswitchinterval()
        self.addCleanup(sys.setswitchinterval, before)
        live = self.reading([0.01])
        live._run = lambda: None
        live.start()
        live._thread.join()
        self.assertEqual(sys.getswitchinterval(), client.READ_SWITCH_INTERVAL)

    def test_a_lower_read_rate_takes_effect_at_the_next_read(self):
        from turbohud.tsu.client import READ_INTERVAL

        live = self.reading([0.0, 0.0])
        self.assertEqual(live.read_interval, READ_INTERVAL)
        now = [100.0]
        live._clock = lambda: now[0]
        live.read_interval = 0.2
        self.assertAlmostEqual(live.step(), 0.2)

    def test_reads_come_at_their_interval_from_start_to_start(self):
        from turbohud.tsu.client import LEAST_WAIT, READ_INTERVAL

        live = self.reading([0.03, 0.03, 0.2])
        now = [100.0]

        def clock():
            return now[0]

        live._clock = clock
        reader = live._connect()[0]
        real = reader.read

        def timed():
            now[0] += 0.03
            return real()

        live._reader, reader.read = reader, timed
        self.assertAlmostEqual(live.step(), READ_INTERVAL - 0.03)

        def slow():
            now[0] += 0.2
            return real()

        reader.read = slow
        self.assertEqual(live.step(), LEAST_WAIT)

    def test_no_trips_in_the_line_where_they_are_not_known(self):
        from turbohud.tsu.client import ReadTimes

        times = ReadTimes(lambda: 100.0)
        times.add(0.1)
        with self.assertLogs('turbohud.tsu.client', 'INFO') as logs:
            times.flush()
        self.assertNotIn('trips', logs.output[0])

    def test_no_line_between_the_times(self):
        live = self.reading([0.01, 0.01, 0.01])
        live.step()  # the status line comes with the first read
        live.step()
        with self.assertNoLogs('turbohud.tsu.client', 'INFO'):
            live.step()

    def test_the_last_reads_are_logged_when_the_race_ends(self):
        lap = race.LapState(1000, 0, 0, 13, [0])
        results = iter([lap, lap, il.NotFound('m_activeServer is null')])

        class Reader:
            def read(self):
                result = next(results)
                if isinstance(result, Exception):
                    raise result
                return result

        live = self.live(lambda: (Reader(), None))
        with self.assertLogs('turbohud.tsu.client', 'INFO') as logs:
            for _ in range(3):
                live.step()
        self.assertTrue(any('race reads: 1 in' in m for m in logs.output))

    def test_failed_reads_do_not_count(self):
        class Reader:
            def read(self):
                raise il.NotFound('m_activeServer is null')

        live = self.live(lambda: (Reader(), None))
        with self.assertLogs('turbohud.tsu.client', 'INFO') as logs:
            live.step()
            live.stop()
        self.assertFalse(any('race reads' in m for m in logs.output))

    def test_racing_notices_whether_the_clock_moves(self):
        clocks = iter([1000, 1200, 1200])

        class Reader:
            def read(self):
                return race.LapState(next(clocks), 0, 0, 13, [0])

        live = self.live(lambda: (Reader(), None))
        self.assertEqual(live.step(), self.client.READ_INTERVAL)
        self.assertFalse(live.snapshot().running)  # nothing to compare with yet
        live.step()
        self.assertTrue(live.snapshot().running)
        live.step()
        self.assertFalse(live.snapshot().running)
        self.assertEqual(live.snapshot().read_at, 50.0)

    def test_it_notes_when_the_clock_last_moved(self):
        clocks = iter([1000, 1200, 1200])

        class Reader:
            def read(self):
                return race.LapState(next(clocks), 0, 0, 13, [0])

        live = self.live(lambda: (Reader(), None))
        live.step()
        self.now = 51.0
        live.step()
        self.now = 55.0
        live.step()
        self.assertEqual(live.snapshot().moved_at, 51.0)

    def test_when_tsu_quits_it_reconnects(self):
        attempts = []

        class Gone:
            def read(self):
                raise ConnectionError('closed')

        def connect():
            attempts.append(1)
            return Gone(), None

        live = self.live(connect)
        live.step()
        live.step()
        self.assertEqual(live.snapshot().status, race.WAITING_FOR_GAME)
        self.assertEqual(len(attempts), 2)

    def test_the_thread_starts_and_stops(self):
        def connect():
            raise FileNotFoundError('no socket')

        live = self.client.LiveRace(connect=connect)
        live.start()
        live.stop()
        self.assertFalse(live._thread.is_alive())

    def test_connect_without_the_probe_fails_cleanly(self):
        import tempfile

        with tempfile.TemporaryDirectory() as folder, self.assertRaises(OSError):
            self.client.connect(Path(folder, 'missing.sock'))


class WatchingTests(unittest.TestCase):
    """What a spectator's HUD shows."""

    def players(self):
        first = race.PlayerState(
            'First', 75, 1, ((1000, 2000, 3000), (9000, 10000)), False, False, False, (1.0, 1.0)
        )
        second = race.PlayerState(
            'Second', 75, 1, ((1000, 2500, 3500), (9500,)), False, True, False, (2.0, 2.0)
        )
        return first, second

    def watched(self, **changes):
        fields = {
            'clock': 11_000,
            'time_limit': 0,
            'laps_completed': 1,
            'laps_to_finish': 13,
            'lap_starts': [],
            'players': self.players(),
            'spectating': True,
        }
        return racing(race.LapState(**{**fields, **changes}))

    def test_shows_the_race_and_nothing_of_a_car(self):
        sections = race.race_sections(self.watched(), 100.0)
        self.assertEqual(sorted(sections), ['lap', 'laptimes', 'players'])

    def test_the_title_says_so_with_the_leaders_lap(self):
        rows = race.race_sections(self.watched(), 100.0)['lap']
        self.assertEqual(rows[0].text, 'Spectating  -  Lap 2/13')

    def test_the_title_shows_the_time_left(self):
        rows = race.race_sections(self.watched(time_limit=31_000, laps_to_finish=0), 100.0)['lap']
        self.assertEqual(rows[0].text, 'Spectating  -  Lap 2  -  0:02 left')

    def test_gaps_are_to_the_leader_without_a_colour(self):
        rows = race.race_sections(self.watched(), 100.0)['players']
        self.assertEqual(rows[0].right, '')
        self.assertTrue(rows[1].right)
        self.assertEqual(rows[1].right_color, 'text')
        self.assertEqual(rows[1].tail, '  PIT')

    def test_hidden_when_the_clock_stands(self):
        self.assertEqual(race.race_sections(self.watched(), 110.0), {})

    def test_without_readable_players_only_the_title(self):
        self.assertEqual(sorted(race.race_sections(self.watched(players=()), 100.0)), ['lap'])

    def test_the_tooltip_says_so(self):
        import time

        snapshot = racing(self.watched().state, moved_at=time.monotonic())
        self.assertEqual(race.status_text(snapshot), 'spectating')

    def test_a_driver_keeps_coloured_gaps_to_themselves(self):
        first, second = self.players()
        me = dataclasses.replace(second, local=True)
        rows = race.players_rows((first, me), None, 11_000)
        self.assertEqual(rows[race.ME_ROW].middle, '')  # me, in the middle row
        self.assertEqual(rows[race.ME_ROW - 1].middle_color, 'behind')


class LighterReadTests(unittest.TestCase):
    """Other cars' slow state once a second, the player's car every read (a tester's TSU in
    CrossOver stuttered as the reads grew, 2026-11-12)."""

    def counted(self, local_index=0):
        now = [0.0]
        reader = build(
            [10_000, 944_595],
            laps_completed=1,
            clock=1_000_000,
            limit=0,
            name='A',
            car=(1.0, 2.0),
            local_index=local_index,
            clock_fn=lambda: now[0],
        )
        calls = []
        slow = reader._slow_state

        def counting(vehicle, updater):
            calls.append(now[0])
            return slow(vehicle, updater)

        reader._slow_state = counting
        return reader, now, calls

    def read(self, reader):
        reader.plan_read()
        return reader.read()

    def test_other_cars_once_a_second(self):
        reader, now, calls = self.counted(local_index=-1)  # watched: the car is someone else's
        self.read(reader)
        for step in range(1, 10):
            now[0] = step * 0.1
            self.read(reader)
        self.assertEqual(len(calls), 1)  # the first read only
        now[0] = race.FULL_READ_EVERY
        self.read(reader)
        self.assertEqual(len(calls), 2)

    def test_kept_between_full_reads(self):
        reader, now, _calls = self.counted(local_index=-1)
        first = self.read(reader).players
        now[0] = 0.1
        again = self.read(reader).players
        self.assertEqual(
            [(p.in_pit, p.spawns, p.compound, p.wheel_grips) for p in first],
            [(p.in_pit, p.spawns, p.compound, p.wheel_grips) for p in again],
        )

    def test_the_players_own_car_every_read(self):
        reader, now, calls = self.counted()
        for step in range(5):
            now[0] = step * 0.1
            self.read(reader)
        self.assertEqual(len(calls), 5)

    def test_a_read_without_a_plan_is_full(self):
        reader, now, calls = self.counted(local_index=-1)
        reader.read()
        now[0] = 0.1
        reader.read()
        self.assertEqual(len(calls), 2)


class ReplayTests(unittest.TestCase):
    """TurboHUD in TSU's replays (asked for by the user on 2026-11-12): the race under the replay
    player, the driver its camera follows as "you", and the HUD kept while it stands paused."""

    def build(self, replay='playing', clock=None):
        return build(
            [10_000, 944_595],
            laps_completed=1,
            clock=1_000_000,
            limit=0,
            name='Followed',
            car=(5.0, 6.0),
            replay=replay,
            clock_fn=clock,
        )

    def test_a_replay_is_found_and_its_camera_driver_is_you(self):
        reader = self.build()
        state = reader.read()
        self.assertTrue(state.replay)
        self.assertFalse(state.paused)
        self.assertFalse(state.spectating)
        me = next(p for p in state.players if p.local)
        self.assertEqual(me.name, 'Followed')
        self.assertEqual(state.laps_completed, 1)  # the followed driver's own laps
        self.assertEqual(reader._replay, reader.game.replay_player)  # not the earlier one

    def test_one_pass_where_the_memory_searches_several_values(self):
        reader = self.build()
        game, calls = reader.game, []

        def any_of(values, address=None):
            calls.append(values)
            return sorted((hit, value) for value in values for hit in game.find_pointers(value))

        reader.il.memory.find_pointers_any = any_of
        self.assertTrue(reader.read().replay)
        self.assertEqual(len(calls), 1)  # the online races and the replays in one pass

    def test_the_tooltip_says_replay(self):
        reader = self.build(replay='paused')
        snapshot = racing(reader.read(), moved_at=0.0)
        self.assertEqual(race.status_text(snapshot), 'replay, paused')

    def test_found_again_without_a_search(self):
        reader = self.build()
        reader.read()
        searches = reader.game.searches
        reader.read()
        self.assertEqual(reader.game.searches, searches)

    def test_no_driver_followed_is_watched_as_a_spectator(self):
        reader = self.build()
        reader.game.q(reader.game.chooser + 0x10, 0)
        state = reader.read()
        self.assertTrue(state.replay)
        self.assertTrue(state.spectating)
        self.assertFalse(any(p.local for p in state.players))

    def test_paused_keeps_the_hud(self):
        reader = self.build(replay='paused')
        state = reader.read()
        self.assertTrue(state.paused)
        snapshot = race.Snapshot(race.RACING, state, moved_at=0.0)
        self.assertTrue(race.on_grid(snapshot, now=1000.0))  # the clock stood long: still shown
        playing = race.Snapshot(race.RACING, dataclasses.replace(state, paused=False), moved_at=0.0)
        self.assertFalse(race.on_grid(playing, now=1000.0))

    def test_a_closing_replay_is_let_go(self):
        reader = self.build()
        reader.read()
        reader.game.put(reader.game.replay_player + 0x21, bytes([1]))  # m_exiting
        with self.assertRaises((race.NotFound, OSError)):
            reader.read()
        self.assertIsNone(reader._replay)

    def test_a_replay_standing_unpaused_counts_as_closed(self):
        now = [0.0]
        reader = self.build(clock=lambda: now[0])
        reader.read()
        now[0] = race.REPLAY_STILL + 1  # the clock has not moved, and no pause
        with self.assertRaises((race.NotFound, OSError)):
            reader.read()
        self.assertIsNone(reader._replay)
        now[0] += 60  # a later search finds it again, still standing: not taken again
        with self.assertRaises((race.NotFound, OSError)):
            reader.read()
        self.assertIsNone(reader._replay)
        times = reader.game.replay_state_times
        reader.game.put(times + race.TIMES_NOW, struct.pack('<i', 1_100_000))  # it plays on
        now[0] += 60
        self.assertTrue(reader.read().replay)


class ReplayAfterARaceTests(unittest.TestCase):
    """A replay watched after a race in the same TSU session (reported by the user on
    2026-11-13): TSU's log then ends with "Event ended." and says nothing of the replay, so
    a log that says no event runs must not keep the replay from being looked for."""

    def build(self, opened=None, exiting=False):
        now = [100.0]
        reader = build(
            [10_000, 944_595],
            laps_completed=1,
            clock=1_000_000,
            limit=0,
            name='Followed',
            car=(5.0, 6.0),
            replay='playing',
            clock_fn=lambda: now[0],
            event_running=lambda: False,
            recording_opened=opened,
        )
        if exiting:  # no replay plays: the one there is closing
            reader.game.put(reader.game.replay_player + 0x21, bytes([1]))
        return reader, now

    def test_a_recording_opened_brings_the_search_on_at_once(self):
        opened = [False]
        reader, now = self.build(lambda: opened[0])
        searches = getattr(reader.game, 'searches', 0)
        with self.assertRaises(race.NotFound):
            reader.read()
        self.assertEqual(
            getattr(reader.game, 'searches', 0), searches
        )  # the log says no event: no search yet
        opened[0] = True
        now[0] += race.CLIENT_LOG_EVERY  # the next look, long before a search would come
        with self.assertLogs('turbohud.core.race', 'INFO') as logs:
            self.assertTrue(reader.read().replay)
        self.assertIn('searching for a replay (a recording was opened)', logs.output[0])

    def test_without_an_access_time_the_replay_is_found_a_little_later(self):
        reader, now = self.build()
        with self.assertRaises(race.NotFound):
            reader.read()
        now[0] += race.CLIENT_SEARCH_EVERY - 1
        with self.assertRaises(race.NotFound):
            reader.read()
        now[0] += 1
        self.assertTrue(reader.read().replay)

    def test_the_searches_for_a_replay_grow_further_apart(self):
        reader, now = self.build(exiting=True)
        searched = []
        for _ in range(400):
            searches = getattr(reader.game, 'searches', 0)
            with self.assertRaises((race.NotFound, OSError)):
                reader.read()
            if getattr(reader.game, 'searches', 0) != searches:
                searched.append(now[0])
            now[0] += 1.0
        gaps = [b - a for a, b in itertools.pairwise(searched)]
        self.assertEqual(searched[0], 100.0 + race.CLIENT_SEARCH_EVERY)
        self.assertEqual(gaps[:5], [10.0, 20.0, 40.0, 60.0, 60.0])

    def test_only_replays_are_searched_for(self):
        reader, now = self.build()
        looked_for = []
        find = reader.il.memory.find_pointers
        reader.il.memory.find_pointers = lambda value: looked_for.append(value) or find(value)
        with self.assertRaises(race.NotFound):
            reader.read()
        now[0] += race.CLIENT_SEARCH_EVERY
        self.assertTrue(reader.read().replay)
        self.assertEqual(looked_for, [reader._replay_class])

    def test_a_game_without_replays_is_left_alone(self):
        reader, now = self.build(lambda: True)
        reader._replay_class = False  # TS.EventRecordingPlayer not in the game
        searches = getattr(reader.game, 'searches', 0)
        for _ in range(3):
            with self.assertRaises(race.NotFound):
                reader.read()
            now[0] += race.REPLAY_SEARCH_MOST
        self.assertEqual(getattr(reader.game, 'searches', 0), searches)


if __name__ == '__main__':
    unittest.main()


class HotlappingTests(unittest.TestCase):
    """Qualifying, run as hotlapping (reported by the user on 2026-11-13: the list kept race
    order): TSU's RaceStats says so, and the order is by best lap."""

    def test_the_reader_reads_the_flag(self):
        for flag in (True, False):
            reader = build([10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0, hotlapping=flag)
            self.assertEqual(reader.read().hotlapping, flag)
        plain = build([10_000, 944_595], laps_completed=1, clock=1_000_000, limit=0)
        self.assertFalse(plain.read().hotlapping)  # not found: a race, as before

    def test_a_hotlapping_event_is_ranked_by_best_lap(self):
        def driver(name, laps):
            starts, at = [0], 0
            for lap_time in laps:
                at += lap_time
                starts.append(at)
            return race.PlayerState(name, 0, len(laps), tuple((t,) for t in starts), False, False, False)

        many = driver('Many laps', [70_000, 69_000, 68_000])  # furthest on: leads the race order
        fast = driver('Fast', [65_000])
        slow = driver('Slow', [75_000, 74_000])
        none = driver('No lap yet', [])
        players = [none, slow, many, fast]
        self.assertEqual(race.ranked(players)[0].name, 'Many laps')
        self.assertEqual(
            [p.name for p in race.ranked(players, hotlapping=True)],
            ['Fast', 'Many laps', 'Slow', 'No lap yet'],
        )
        standings = race.Standings()
        self.assertEqual(standings.order(players, 0.0, hotlapping=True)[0].name, 'Fast')


class CockpitCameraTests(unittest.TestCase):
    """The proximity radar only while the camera sits at the driver (asked for by the user on
    2026-11-13): TSU's camera position mode and distance, read through the race controller."""

    def state(self, camera):
        return build([10_000], laps_completed=0, clock=20_000, limit=0, name='A', camera=camera).read()

    def test_the_cameras_view(self):
        self.assertTrue(self.state((race.COCKPIT_POSITION, 1.5)).cockpit)  # AlignTarget, at the driver
        self.assertFalse(self.state((1, 35.0)).cockpit)  # BehindVelocity: following behind
        self.assertFalse(self.state((race.COCKPIT_POSITION, 30.0)).cockpit)  # turns with the car, but far
        self.assertIsNone(self.state(None).cockpit)  # not read

    def sections(self, cockpit, only=True):
        class Radar:
            def update(self, *arguments):
                return 'the radar'

        state = race.LapState(
            clock=20_000,
            time_limit=0,
            laps_completed=0,
            laps_to_finish=3,
            lap_starts=[10_000],
            players=(race.PlayerState('A', 0, 0, ((10_000,),), False, False, True),),
            cockpit=cockpit,
        )
        snapshot = race.Snapshot(race.RACING, state, running=True, read_at=5.0, moved_at=5.0)
        return race.race_sections(snapshot, 5.0, radar=Radar(), radar_cockpit_only=only)

    def test_the_radar_hides_only_outside_the_car(self):
        self.assertIn('radar', self.sections(True))
        self.assertNotIn('radar', self.sections(False))
        self.assertIn('radar', self.sections(None))  # the camera not read: as before
        self.assertIn('radar', self.sections(False, only=False))  # the setting off


class ReplayBackTests(unittest.TestCase):
    """A replay rewound or going on after standing shows again within a read, not after the
    searches (reported by the user on 2026-11-13: about 30 s after a rewind)."""

    def build(self):
        now = [0.0]
        reader = ReplayTests.build(self, clock=lambda: now[0])
        reader.read()
        return reader, now

    def searches(self, reader):
        return getattr(reader.game, 'searches', 0)

    def test_a_rewound_replay_is_taken_back_without_a_search(self):
        reader, now = self.build()
        game = reader.game
        runner = game.read(game.replay_player + 0x18, 8)
        game.q(game.replay_player + 0x18, 0)  # rewound: TSU rebuilds its race for a moment
        with self.assertRaises((race.NotFound, OSError)):
            reader.read()
        searches = self.searches(reader)
        game.put(game.replay_player + 0x18, runner)  # rebuilt
        now[0] += 1.0
        self.assertTrue(reader.read().replay)
        self.assertEqual(self.searches(reader), searches)

    def test_a_replay_going_on_after_standing_is_taken_back_without_a_search(self):
        reader, now = self.build()
        now[0] = race.REPLAY_STILL + 1  # stands, not paused: taken as closed
        with self.assertRaises((race.NotFound, OSError)):
            reader.read()
        now[0] += 5
        with self.assertRaises((race.NotFound, OSError)):
            reader.read()  # still standing where it stood: not taken back
        searches = self.searches(reader)
        reader.game.put(reader.game.replay_state_times + race.TIMES_NOW, struct.pack('<i', 1_100_000))
        now[0] += 1
        self.assertTrue(reader.read().replay)
        self.assertEqual(self.searches(reader), searches)

    def test_after_a_minute_only_a_search_finds_it(self):
        reader, now = self.build()
        game = reader.game
        runner = game.read(game.replay_player + 0x18, 8)
        game.q(game.replay_player + 0x18, 0)
        with self.assertRaises((race.NotFound, OSError)):
            reader.read()
        now[0] += race.REPLAY_BACK_FOR + 1
        game.put(game.replay_player + 0x18, runner)
        searches = self.searches(reader)
        self.assertTrue(reader.read().replay)  # found again, by a search
        self.assertGreater(self.searches(reader), searches)


class YellowFlagJumpTests(unittest.TestCase):
    """No false "wrong way" after a jump (reported by the user on 2026-11-13: drivers shown as
    driving the wrong way after a recording was started again). Where on the track a car was is
    kept to look it up quickly; after a jump it is looked up on the whole track again."""

    def car(self, position, velocity=(30.0, 0.0)):
        lap = tuple(1000 * i for i in range(5))
        return race.PlayerState(
            'Car',
            0,
            1,
            ((0,), lap),
            position=position,
            velocity=velocity,
            forward_speed=30.0,
            wheel_grips=(1.0,) * 4,
        )

    def update(self, flags, seconds, car, heading):
        state = race.LapState(
            clock=round(seconds * race.UNITS_PER_SECOND),
            time_limit=0,
            laps_completed=1,
            laps_to_finish=0,
            lap_starts=[0],
            players=(car,),
        )
        return flags.update(state, heading)

    def recorder(self, direction=(1.0, 0.0)):
        asked = []

        def heading(position, hint):
            asked.append(hint)
            return direction, 7  # the race goes this way there; the learnt point found: 7

        return heading, asked

    def test_a_car_driving_on_is_looked_up_near_where_it_was(self):
        flags = race.YellowFlags()
        heading, asked = self.recorder()
        self.update(flags, 10.0, self.car((0.0, 0.0)), heading)
        self.update(flags, 10.1, self.car((3.0, 0.0)), heading)
        self.assertEqual(asked, [None, 7])

    def test_a_car_that_jumps_is_looked_up_on_the_whole_track(self):
        flags = race.YellowFlags()
        heading, asked = self.recorder()
        self.update(flags, 10.0, self.car((0.0, 0.0)), heading)
        self.update(flags, 10.1, self.car((400.0, 250.0)), heading)  # put back elsewhere
        self.assertEqual(asked, [None, None])

    def test_a_wrong_way_building_up_ends_with_a_jump(self):
        flags = race.YellowFlags()
        heading, _asked = self.recorder(direction=(-1.0, 0.0))  # the car seems to go against the race
        self.update(flags, 10.0, self.car((0.0, 0.0)), heading)
        self.update(flags, 11.0, self.car((30.0, 0.0)), heading)
        self.update(flags, 11.2, self.car((900.0, 0.0)), heading)  # jumps
        right_way, _ = self.recorder(direction=(1.0, 0.0))
        incidents = self.update(flags, 11.8, self.car((918.0, 0.0)), right_way)
        self.assertEqual(incidents, ())

    def test_the_clock_going_back_forgets_the_cars(self):
        flags = race.YellowFlags()
        heading, asked = self.recorder(direction=(-1.0, 0.0))
        for second in (100.0, 101.0, 102.0):
            incidents = self.update(flags, second, self.car((30.0 * second, 0.0)), heading)
        self.assertEqual([i.kind for i in incidents], ['wrong way'])
        right_way, asked = self.recorder()
        self.assertEqual(self.update(flags, 5.0, self.car((10.0, 0.0)), right_way), ())  # started again
        self.assertEqual(asked, [None])  # looked up anew
