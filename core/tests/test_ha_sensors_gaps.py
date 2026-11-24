"""The hub readings the "All sensors" level used to miss: the new rows' catalogue and bridge tests.

T-27, the guard, comes first and was written before any other change: every entity kind that existed before is built
from the recorded local message, and its config and state are pinned as literals. It must stay green unedited."""

import json
import pathlib
from zoneinfo import ZoneInfo

from embertide import ha_sensors as hs
from embertide.drivers.orion_mqtt import OrionMqtt, parse_status

TZ = ZoneInfo("America/New_York")
PREFIX = "homeassistant"
TS = 1_800_000_000.0
DEVICE = {"identifiers": ["embertide_bed"], "name": "Bed"}     # a stand-in Bed device block
REAL = json.loads((pathlib.Path(__file__).parent / "fixtures" / "orion_fw262_frames.json").read_text(encoding="utf-8"))


class LocalDriver:
    """A driver with the local driver's capabilities and zones, holding no connection."""
    id, name = "fake-local", "Fake local"
    capabilities = set(OrionMqtt.capabilities)
    zones = list(OrionMqtt.zones)

    def __init__(self, frame=None):
        self.frame = frame

    def latest(self):
        return self.frame


def local_frame(kind="valid", ts=TS):
    _, f = parse_status("orion/AABBCCDDEEFF/out", REAL[kind].encode("utf-8"), ts)
    return f


def local_extras(f=None, announced=()):
    f = local_frame() if f is None else f
    return {e.key: e for e in hs.extras(LocalDriver(f), f, TZ, announced, prefix=PREFIX, device=DEVICE)}


# ---------- T-27: the guard ----------
# Built at commit c589a77 from the recorded `valid` message: every entity kind that existed then, as it was then.
GUARD = \
{'problem': {'domain': 'binary_sensor',
             'config_topic': 'homeassistant/binary_sensor/embertide_hub_problem/config',
             'state_topic': 'embertide/bed/hub/problem',
             'state': 'OFF',
             'limited': False,
             'config': {'availability_topic': 'embertide/status',
                        'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                        'name': 'Hub problem',
                        'unique_id': 'embertide_hub_problem',
                        'default_entity_id': 'binary_sensor.embertide_hub_problem',
                        'state_topic': 'embertide/bed/hub/problem',
                        'device_class': 'problem',
                        'payload_on': 'ON',
                        'payload_off': 'OFF',
                        'json_attributes_topic': 'embertide/bed/hub/problem/attributes'}},
 'status': {'domain': 'sensor',
            'config_topic': 'homeassistant/sensor/embertide_hub_status/config',
            'state_topic': 'embertide/bed/hub/status',
            'state': 'All good',
            'limited': False,
            'config': {'availability_topic': 'embertide/status',
                       'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                       'name': 'Hub status',
                       'unique_id': 'embertide_hub_status',
                       'default_entity_id': 'sensor.embertide_hub_status',
                       'state_topic': 'embertide/bed/hub/status',
                       'entity_category': 'diagnostic'}},
 'water_problem': {'domain': 'binary_sensor',
                   'config_topic': 'homeassistant/binary_sensor/embertide_hub_water_problem/config',
                   'state_topic': 'embertide/bed/hub/water_problem',
                   'state': 'OFF',
                   'limited': False,
                   'config': {'availability_topic': 'embertide/status',
                              'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                              'name': 'Water problem',
                              'unique_id': 'embertide_hub_water_problem',
                              'default_entity_id': 'binary_sensor.embertide_hub_water_problem',
                              'state_topic': 'embertide/bed/hub/water_problem',
                              'device_class': 'problem',
                              'payload_on': 'ON',
                              'payload_off': 'OFF'}},
 'safety': {'domain': 'binary_sensor',
            'config_topic': 'homeassistant/binary_sensor/embertide_hub_safety/config',
            'state_topic': 'embertide/bed/hub/safety',
            'state': 'OFF',
            'limited': False,
            'config': {'availability_topic': 'embertide/status',
                       'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                       'name': 'Hub safety check',
                       'unique_id': 'embertide_hub_safety',
                       'default_entity_id': 'binary_sensor.embertide_hub_safety',
                       'state_topic': 'embertide/bed/hub/safety',
                       'device_class': 'safety',
                       'payload_on': 'ON',
                       'payload_off': 'OFF',
                       'entity_category': 'diagnostic'}},
 'fan_power': {'domain': 'sensor',
               'config_topic': 'homeassistant/sensor/embertide_hub_fan_power/config',
               'state_topic': 'embertide/bed/hub/fan_power',
               'state': '100',
               'limited': True,
               'config': {'availability_topic': 'embertide/status',
                          'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                          'name': 'Fan power',
                          'unique_id': 'embertide_hub_fan_power',
                          'default_entity_id': 'sensor.embertide_hub_fan_power',
                          'state_topic': 'embertide/bed/hub/fan_power',
                          'unit_of_measurement': '%',
                          'state_class': 'measurement',
                          'entity_category': 'diagnostic'}},
 'quiet_fan': {'domain': 'binary_sensor',
               'config_topic': 'homeassistant/binary_sensor/embertide_hub_quiet_fan/config',
               'state_topic': 'embertide/bed/hub/quiet_fan',
               'state': 'OFF',
               'limited': False,
               'config': {'availability_topic': 'embertide/status',
                          'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                          'name': 'Quiet fan',
                          'unique_id': 'embertide_hub_quiet_fan',
                          'default_entity_id': 'binary_sensor.embertide_hub_quiet_fan',
                          'state_topic': 'embertide/bed/hub/quiet_fan',
                          'payload_on': 'ON',
                          'payload_off': 'OFF',
                          'entity_category': 'diagnostic'}},
 'humidity': {'domain': 'sensor',
              'config_topic': 'homeassistant/sensor/embertide_hub_humidity/config',
              'state_topic': 'embertide/bed/hub/humidity',
              'state': '41.9',
              'limited': True,
              'config': {'availability_topic': 'embertide/status',
                         'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                         'name': 'Room humidity',
                         'unique_id': 'embertide_hub_humidity',
                         'default_entity_id': 'sensor.embertide_hub_humidity',
                         'state_topic': 'embertide/bed/hub/humidity',
                         'device_class': 'humidity',
                         'unit_of_measurement': '%',
                         'state_class': 'measurement'}},
 'wifi_signal': {'domain': 'sensor',
                 'config_topic': 'homeassistant/sensor/embertide_hub_wifi_signal/config',
                 'state_topic': 'embertide/bed/hub/wifi_signal',
                 'state': '-37',
                 'limited': True,
                 'config': {'availability_topic': 'embertide/status',
                            'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                            'name': 'Hub Wi-Fi signal',
                            'unique_id': 'embertide_hub_wifi_signal',
                            'default_entity_id': 'sensor.embertide_hub_wifi_signal',
                            'state_topic': 'embertide/bed/hub/wifi_signal',
                            'device_class': 'signal_strength',
                            'unit_of_measurement': 'dBm',
                            'state_class': 'measurement',
                            'entity_category': 'diagnostic'}},
 'last_restart': {'domain': 'sensor',
                  'config_topic': 'homeassistant/sensor/embertide_hub_last_restart/config',
                  'state_topic': 'embertide/bed/hub/last_restart',
                  'state': '2027-01-15T02:59:34-05:00',
                  'limited': False,
                  'config': {'availability_topic': 'embertide/status',
                             'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                             'name': 'Hub last restart',
                             'unique_id': 'embertide_hub_last_restart',
                             'default_entity_id': 'sensor.embertide_hub_last_restart',
                             'state_topic': 'embertide/bed/hub/last_restart',
                             'device_class': 'timestamp',
                             'entity_category': 'diagnostic'}},
 'free_memory': {'domain': 'sensor',
                 'config_topic': 'homeassistant/sensor/embertide_hub_free_memory/config',
                 'state_topic': 'embertide/bed/hub/free_memory',
                 'state': '57',
                 'limited': True,
                 'config': {'availability_topic': 'embertide/status',
                            'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                            'name': 'Hub free memory',
                            'unique_id': 'embertide_hub_free_memory',
                            'default_entity_id': 'sensor.embertide_hub_free_memory',
                            'state_topic': 'embertide/bed/hub/free_memory',
                            'device_class': 'data_size',
                            'unit_of_measurement': 'kB',
                            'state_class': 'measurement',
                            'entity_category': 'diagnostic'}},
 'firmware': {'domain': 'sensor',
              'config_topic': 'homeassistant/sensor/embertide_hub_firmware/config',
              'state_topic': 'embertide/bed/hub/firmware',
              'state': '2.6.2',
              'limited': False,
              'config': {'availability_topic': 'embertide/status',
                         'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                         'name': 'Hub firmware',
                         'unique_id': 'embertide_hub_firmware',
                         'default_entity_id': 'sensor.embertide_hub_firmware',
                         'state_topic': 'embertide/bed/hub/firmware',
                         'entity_category': 'diagnostic'}},
 'firmware_build': {'domain': 'sensor',
                    'config_topic': 'homeassistant/sensor/embertide_hub_firmware_build/config',
                    'state_topic': 'embertide/bed/hub/firmware_build',
                    'state': 'Jun 29 2026 16:52:50',
                    'limited': False,
                    'config': {'availability_topic': 'embertide/status',
                               'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                               'name': 'Hub firmware build',
                               'unique_id': 'embertide_hub_firmware_build',
                               'default_entity_id': 'sensor.embertide_hub_firmware_build',
                               'state_topic': 'embertide/bed/hub/firmware_build',
                               'entity_category': 'diagnostic'}},
 'panel_firmware': {'domain': 'sensor',
                    'config_topic': 'homeassistant/sensor/embertide_hub_panel_firmware/config',
                    'state_topic': 'embertide/bed/hub/panel_firmware',
                    'state': '2.6.1',
                    'limited': False,
                    'config': {'availability_topic': 'embertide/status',
                               'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                               'name': 'Light panel firmware',
                               'unique_id': 'embertide_hub_panel_firmware',
                               'default_entity_id': 'sensor.embertide_hub_panel_firmware',
                               'state_topic': 'embertide/bed/hub/panel_firmware',
                               'entity_category': 'diagnostic'}},
 'online': {'domain': 'binary_sensor',
            'config_topic': 'homeassistant/binary_sensor/embertide_hub_online/config',
            'state_topic': 'embertide/bed/hub/online',
            'state': 'ON',
            'limited': False,
            'config': {'availability_topic': 'embertide/status',
                       'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                       'name': 'Hub online',
                       'unique_id': 'embertide_hub_online',
                       'default_entity_id': 'binary_sensor.embertide_hub_online',
                       'state_topic': 'embertide/bed/hub/online',
                       'device_class': 'connectivity',
                       'payload_on': 'ON',
                       'payload_off': 'OFF',
                       'entity_category': 'diagnostic'}},
 'system_state': {'domain': 'sensor',
                  'config_topic': 'homeassistant/sensor/embertide_hub_system_state/config',
                  'state_topic': 'embertide/bed/hub/system_state',
                  'state': 'SYSTEM_OFF',
                  'limited': False,
                  'config': {'availability_topic': 'embertide/status',
                             'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                             'name': 'Hub system state',
                             'unique_id': 'embertide_hub_system_state',
                             'default_entity_id': 'sensor.embertide_hub_system_state',
                             'state_topic': 'embertide/bed/hub/system_state',
                             'entity_category': 'diagnostic'}},
 'light_brightness': {'domain': 'sensor',
                      'config_topic': 'homeassistant/sensor/embertide_hub_light_brightness/config',
                      'state_topic': 'embertide/bed/hub/light_brightness',
                      'state': '0',
                      'limited': True,
                      'config': {'availability_topic': 'embertide/status',
                                 'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                 'name': 'Hub light brightness',
                                 'unique_id': 'embertide_hub_light_brightness',
                                 'default_entity_id': 'sensor.embertide_hub_light_brightness',
                                 'state_topic': 'embertide/bed/hub/light_brightness',
                                 'unit_of_measurement': '%',
                                 'state_class': 'measurement',
                                 'entity_category': 'diagnostic'}},
 'light_color': {'domain': 'sensor',
                 'config_topic': 'homeassistant/sensor/embertide_hub_light_color/config',
                 'state_topic': 'embertide/bed/hub/light_color',
                 'state': '#ffffff',
                 'limited': False,
                 'config': {'availability_topic': 'embertide/status',
                            'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                            'name': 'Hub light colour',
                            'unique_id': 'embertide_hub_light_color',
                            'default_entity_id': 'sensor.embertide_hub_light_color',
                            'state_topic': 'embertide/bed/hub/light_color',
                            'entity_category': 'diagnostic'}},
 'fan_left_rpm': {'domain': 'sensor',
                  'config_topic': 'homeassistant/sensor/embertide_hub_fan_left_rpm/config',
                  'state_topic': 'embertide/bed/hub/fan_left_rpm',
                  'state': '0',
                  'limited': True,
                  'config': {'availability_topic': 'embertide/status',
                             'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                             'name': 'Fan speed (left)',
                             'unique_id': 'embertide_hub_fan_left_rpm',
                             'default_entity_id': 'sensor.embertide_hub_fan_left_rpm',
                             'state_topic': 'embertide/bed/hub/fan_left_rpm',
                             'unit_of_measurement': 'rpm',
                             'state_class': 'measurement',
                             'entity_category': 'diagnostic'}},
 'fan_right_rpm': {'domain': 'sensor',
                   'config_topic': 'homeassistant/sensor/embertide_hub_fan_right_rpm/config',
                   'state_topic': 'embertide/bed/hub/fan_right_rpm',
                   'state': '0',
                   'limited': True,
                   'config': {'availability_topic': 'embertide/status',
                              'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                              'name': 'Fan speed (right)',
                              'unique_id': 'embertide_hub_fan_right_rpm',
                              'default_entity_id': 'sensor.embertide_hub_fan_right_rpm',
                              'state_topic': 'embertide/bed/hub/fan_right_rpm',
                              'unit_of_measurement': 'rpm',
                              'state_class': 'measurement',
                              'entity_category': 'diagnostic'}},
 'water_ctank_left': {'domain': 'sensor',
                      'config_topic': 'homeassistant/sensor/embertide_hub_water_ctank_left/config',
                      'state_topic': 'embertide/bed/hub/water_ctank_left',
                      'state': '1',
                      'limited': True,
                      'config': {'availability_topic': 'embertide/status',
                                 'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                 'name': 'Water reading (ctank left)',
                                 'unique_id': 'embertide_hub_water_ctank_left',
                                 'default_entity_id': 'sensor.embertide_hub_water_ctank_left',
                                 'state_topic': 'embertide/bed/hub/water_ctank_left',
                                 'state_class': 'measurement',
                                 'entity_category': 'diagnostic'}},
 'water_ctank_left_filtered': {'domain': 'sensor',
                               'config_topic': 'homeassistant/sensor/embertide_hub_water_ctank_left_filtered/config',
                               'state_topic': 'embertide/bed/hub/water_ctank_left_filtered',
                               'state': '1',
                               'limited': True,
                               'config': {'availability_topic': 'embertide/status',
                                          'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                          'name': 'Water reading (ctank left filtered)',
                                          'unique_id': 'embertide_hub_water_ctank_left_filtered',
                                          'default_entity_id': 'sensor.embertide_hub_water_ctank_left_filtered',
                                          'state_topic': 'embertide/bed/hub/water_ctank_left_filtered',
                                          'state_class': 'measurement',
                                          'entity_category': 'diagnostic'}},
 'water_ctank_right': {'domain': 'sensor',
                       'config_topic': 'homeassistant/sensor/embertide_hub_water_ctank_right/config',
                       'state_topic': 'embertide/bed/hub/water_ctank_right',
                       'state': '1',
                       'limited': True,
                       'config': {'availability_topic': 'embertide/status',
                                  'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                  'name': 'Water reading (ctank right)',
                                  'unique_id': 'embertide_hub_water_ctank_right',
                                  'default_entity_id': 'sensor.embertide_hub_water_ctank_right',
                                  'state_topic': 'embertide/bed/hub/water_ctank_right',
                                  'state_class': 'measurement',
                                  'entity_category': 'diagnostic'}},
 'water_ctank_right_filtered': {'domain': 'sensor',
                                'config_topic': 'homeassistant/sensor/embertide_hub_water_ctank_right_filtered/config',
                                'state_topic': 'embertide/bed/hub/water_ctank_right_filtered',
                                'state': '1',
                                'limited': True,
                                'config': {'availability_topic': 'embertide/status',
                                           'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                           'name': 'Water reading (ctank right filtered)',
                                           'unique_id': 'embertide_hub_water_ctank_right_filtered',
                                           'default_entity_id': 'sensor.embertide_hub_water_ctank_right_filtered',
                                           'state_topic': 'embertide/bed/hub/water_ctank_right_filtered',
                                           'state_class': 'measurement',
                                           'entity_category': 'diagnostic'}},
 'water_reservoir': {'domain': 'sensor',
                     'config_topic': 'homeassistant/sensor/embertide_hub_water_reservoir/config',
                     'state_topic': 'embertide/bed/hub/water_reservoir',
                     'state': '1',
                     'limited': True,
                     'config': {'availability_topic': 'embertide/status',
                                'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                'name': 'Water reading (reservoir)',
                                'unique_id': 'embertide_hub_water_reservoir',
                                'default_entity_id': 'sensor.embertide_hub_water_reservoir',
                                'state_topic': 'embertide/bed/hub/water_reservoir',
                                'state_class': 'measurement',
                                'entity_category': 'diagnostic'}},
 'left_temperature': {'domain': 'sensor',
                      'config_topic': 'homeassistant/sensor/embertide_hub_left_temperature/config',
                      'state_topic': 'embertide/bed/hub/left_temperature',
                      'state': '23.5',
                      'limited': True,
                      'config': {'availability_topic': 'embertide/status',
                                 'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                 'name': 'Left pad temperature',
                                 'unique_id': 'embertide_hub_left_temperature',
                                 'default_entity_id': 'sensor.embertide_hub_left_temperature',
                                 'state_topic': 'embertide/bed/hub/left_temperature',
                                 'device_class': 'temperature',
                                 'unit_of_measurement': '°C',
                                 'state_class': 'measurement'}},
 'left_setpoint': {'domain': 'sensor',
                   'config_topic': 'homeassistant/sensor/embertide_hub_left_setpoint/config',
                   'state_topic': 'embertide/bed/hub/left_setpoint',
                   'state': '27.5',
                   'limited': True,
                   'config': {'availability_topic': 'embertide/status',
                              'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                              'name': 'Left pad setpoint',
                              'unique_id': 'embertide_hub_left_setpoint',
                              'default_entity_id': 'sensor.embertide_hub_left_setpoint',
                              'state_topic': 'embertide/bed/hub/left_setpoint',
                              'device_class': 'temperature',
                              'unit_of_measurement': '°C',
                              'state_class': 'measurement'}},
 'left_power': {'domain': 'binary_sensor',
                'config_topic': 'homeassistant/binary_sensor/embertide_hub_left_power/config',
                'state_topic': 'embertide/bed/hub/left_power',
                'state': 'OFF',
                'limited': False,
                'config': {'availability_topic': 'embertide/status',
                           'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                           'name': 'Left pad power',
                           'unique_id': 'embertide_hub_left_power',
                           'default_entity_id': 'binary_sensor.embertide_hub_left_power',
                           'state_topic': 'embertide/bed/hub/left_power',
                           'device_class': 'power',
                           'payload_on': 'ON',
                           'payload_off': 'OFF'}},
 'left_sensor_state': {'domain': 'sensor',
                       'config_topic': 'homeassistant/sensor/embertide_hub_left_sensor_state/config',
                       'state_topic': 'embertide/bed/hub/left_sensor_state',
                       'state': 'None',
                       'limited': False,
                       'config': {'availability_topic': 'embertide/status',
                                  'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                  'name': 'Left pad sensor',
                                  'unique_id': 'embertide_hub_left_sensor_state',
                                  'default_entity_id': 'sensor.embertide_hub_left_sensor_state',
                                  'state_topic': 'embertide/bed/hub/left_sensor_state',
                                  'entity_category': 'diagnostic'}},
 'left_heart_rate': {'domain': 'sensor',
                     'config_topic': 'homeassistant/sensor/embertide_hub_left_heart_rate/config',
                     'state_topic': 'embertide/bed/hub/left_heart_rate',
                     'state': 'None',
                     'limited': True,
                     'config': {'availability_topic': 'embertide/status',
                                'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                'name': 'Left pad heart rate',
                                'unique_id': 'embertide_hub_left_heart_rate',
                                'default_entity_id': 'sensor.embertide_hub_left_heart_rate',
                                'state_topic': 'embertide/bed/hub/left_heart_rate',
                                'unit_of_measurement': 'bpm',
                                'state_class': 'measurement'}},
 'left_breathing_rate': {'domain': 'sensor',
                         'config_topic': 'homeassistant/sensor/embertide_hub_left_breathing_rate/config',
                         'state_topic': 'embertide/bed/hub/left_breathing_rate',
                         'state': 'None',
                         'limited': True,
                         'config': {'availability_topic': 'embertide/status',
                                    'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                    'name': 'Left pad breathing rate',
                                    'unique_id': 'embertide_hub_left_breathing_rate',
                                    'default_entity_id': 'sensor.embertide_hub_left_breathing_rate',
                                    'state_topic': 'embertide/bed/hub/left_breathing_rate',
                                    'unit_of_measurement': 'br/min',
                                    'state_class': 'measurement'}},
 'right_temperature': {'domain': 'sensor',
                       'config_topic': 'homeassistant/sensor/embertide_hub_right_temperature/config',
                       'state_topic': 'embertide/bed/hub/right_temperature',
                       'state': '23.4',
                       'limited': True,
                       'config': {'availability_topic': 'embertide/status',
                                  'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                  'name': 'Right pad temperature',
                                  'unique_id': 'embertide_hub_right_temperature',
                                  'default_entity_id': 'sensor.embertide_hub_right_temperature',
                                  'state_topic': 'embertide/bed/hub/right_temperature',
                                  'device_class': 'temperature',
                                  'unit_of_measurement': '°C',
                                  'state_class': 'measurement'}},
 'right_setpoint': {'domain': 'sensor',
                    'config_topic': 'homeassistant/sensor/embertide_hub_right_setpoint/config',
                    'state_topic': 'embertide/bed/hub/right_setpoint',
                    'state': '27.5',
                    'limited': True,
                    'config': {'availability_topic': 'embertide/status',
                               'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                               'name': 'Right pad setpoint',
                               'unique_id': 'embertide_hub_right_setpoint',
                               'default_entity_id': 'sensor.embertide_hub_right_setpoint',
                               'state_topic': 'embertide/bed/hub/right_setpoint',
                               'device_class': 'temperature',
                               'unit_of_measurement': '°C',
                               'state_class': 'measurement'}},
 'right_power': {'domain': 'binary_sensor',
                 'config_topic': 'homeassistant/binary_sensor/embertide_hub_right_power/config',
                 'state_topic': 'embertide/bed/hub/right_power',
                 'state': 'OFF',
                 'limited': False,
                 'config': {'availability_topic': 'embertide/status',
                            'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                            'name': 'Right pad power',
                            'unique_id': 'embertide_hub_right_power',
                            'default_entity_id': 'binary_sensor.embertide_hub_right_power',
                            'state_topic': 'embertide/bed/hub/right_power',
                            'device_class': 'power',
                            'payload_on': 'ON',
                            'payload_off': 'OFF'}},
 'right_sensor_state': {'domain': 'sensor',
                        'config_topic': 'homeassistant/sensor/embertide_hub_right_sensor_state/config',
                        'state_topic': 'embertide/bed/hub/right_sensor_state',
                        'state': 'empty',
                        'limited': False,
                        'config': {'availability_topic': 'embertide/status',
                                   'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                   'name': 'Right pad sensor',
                                   'unique_id': 'embertide_hub_right_sensor_state',
                                   'default_entity_id': 'sensor.embertide_hub_right_sensor_state',
                                   'state_topic': 'embertide/bed/hub/right_sensor_state',
                                   'entity_category': 'diagnostic'}},
 'right_heart_rate': {'domain': 'sensor',
                      'config_topic': 'homeassistant/sensor/embertide_hub_right_heart_rate/config',
                      'state_topic': 'embertide/bed/hub/right_heart_rate',
                      'state': 'None',
                      'limited': True,
                      'config': {'availability_topic': 'embertide/status',
                                 'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                 'name': 'Right pad heart rate',
                                 'unique_id': 'embertide_hub_right_heart_rate',
                                 'default_entity_id': 'sensor.embertide_hub_right_heart_rate',
                                 'state_topic': 'embertide/bed/hub/right_heart_rate',
                                 'unit_of_measurement': 'bpm',
                                 'state_class': 'measurement'}},
 'right_breathing_rate': {'domain': 'sensor',
                          'config_topic': 'homeassistant/sensor/embertide_hub_right_breathing_rate/config',
                          'state_topic': 'embertide/bed/hub/right_breathing_rate',
                          'state': 'None',
                          'limited': True,
                          'config': {'availability_topic': 'embertide/status',
                                     'device': {'identifiers': ['embertide_bed'], 'name': 'Bed'},
                                     'name': 'Right pad breathing rate',
                                     'unique_id': 'embertide_hub_right_breathing_rate',
                                     'default_entity_id': 'sensor.embertide_hub_right_breathing_rate',
                                     'state_topic': 'embertide/bed/hub/right_breathing_rate',
                                     'unit_of_measurement': 'br/min',
                                     'state_class': 'measurement'}}}


def test_t27_existing_entity_kinds_are_unchanged_for_the_local_frame():
    ex = local_extras()
    missing = [k for k in GUARD if k not in ex]
    assert not missing, missing
    for key, want in GUARD.items():
        e = ex[key]
        got = {"domain": e.domain, "config_topic": e.config_topic, "state_topic": e.state_topic, "state": e.state,
               "limited": e.limited, "config": e.config}
        assert got == want, key


# ═════════════════ WU-3: the new rows in the catalogue (T-14 to T-22) ═════════════════
from embertide.drivers.base import Cap                       # noqa: E402
from embertide.drivers.orion_cloud import OrionCloud                      # noqa: E402
from embertide.ha_bridge import HaBridge                                  # noqa: E402
from test_ha_sensors import FakeDriver, bridge, ct, fake_night, frame, sim_night, st, tick   # noqa: E402

OLD_FIXED = ["problem", "status", "water_problem", "safety", "fan_power", "quiet_fan", "humidity", "room_temperature",
             "wifi_signal", "last_restart", "free_memory", "firmware", "firmware_build", "panel_firmware",
             "last_command", "online", "system_state", "light_brightness", "light_color"]
NEW_FIXED = ["internal_temperature", "fan_running", "fan_target_power", "air_valve", "fill_valve", "fill_in_progress",
             "light_on", "light_blinking", "setup_mode", "model", "fill_state", "update_available", "updating"]
OLD_SIDE = ["temperature", "setpoint", "power", "sensor_state", "heart_rate", "breathing_rate"]
NEW_SIDE = ["inlet_temperature", "thermal_state", "sensor_powered", "sensor_problem", "sensor_firmware",
            "sensor_hardware", "sensor_algorithm"]
CLOUD_CAPS = set(OrionCloud.capabilities) | {Cap.HUB_HEALTH, Cap.FAULTS}   # the list WU-2 gives the cloud driver

B, S = "binary_sensor", "sensor"
# (domain, device_class, unit, state_class, diagnostic, rate limited, state from the recorded `valid` message)
NEW_LOCAL = {
    "internal_temperature": (S, "temperature", "°C", "measurement", True, True, "28.2"),
    "fan_running": (B, "running", None, None, True, False, "OFF"),
    "fan_target_power": (S, None, "%", "measurement", True, True, "100"),
    "air_valve": (B, "opening", None, None, True, False, "OFF"),
    "fill_valve": (B, "opening", None, None, True, False, "OFF"),
    "fill_in_progress": (B, "running", None, None, True, False, "OFF"),
    "light_on": (B, "light", None, None, True, False, "OFF"),
    "light_blinking": (B, None, None, None, True, False, "OFF"),
    "setup_mode": (B, None, None, None, True, False, "OFF"),
    "tilt_x": (S, None, "°", "measurement", True, True, "1.1"),
    "tilt_y": (S, None, "°", "measurement", True, True, "-0.6"),
    "tilt_z": (S, None, "°", "measurement", True, True, "88.7"),
}
for _s in ("left", "right"):
    NEW_LOCAL.update({
        f"pump_{_s}_running": (B, "running", None, None, True, False, "OFF"),
        f"pump_{_s}_state": (S, None, None, None, True, False, "OFF"),
        f"pump_{_s}_load": (S, None, None, "measurement", True, True, "0"),
        f"{_s}_inlet_temperature": (S, "temperature", "°C", "measurement", True, True,
                                    "23.3" if _s == "left" else "23"),
        f"{_s}_sensor_powered": (B, "power", None, None, True, False, "ON"),
        f"{_s}_sensor_firmware": (S, None, None, None, True, False, "11.00.09"),
        f"{_s}_sensor_hardware": (S, None, None, None, True, False, "01.00.00"),
        f"{_s}_sensor_algorithm": (S, None, None, None, True, False, "02.02.06"),
    })
CLOUD_ONLY = ["model", "fill_state", "update_available", "updating", "left_thermal_state", "right_thermal_state",
              "left_sensor_problem", "right_sensor_problem"]


def cloud_like_frame():
    """A hand-built frame with the readings the cloud driver fills (the cloud payload tests are WU-4's)."""
    f = frame(filling=False, fill_state="filled", update_available=True, updating=False)
    f.model = "OSCT001-1"
    for z in f.zones.values():
        z.thermal_state = "standby"
        z.sensor.working, z.sensor.fw_version, z.sensor.hw_version = True, "11.00.09", "01.00.00"
    return f


def every_new_topic():
    """The config topics of every new row (fixed, per side, one key of each family), as if all were announced."""
    out = [hs.config_topic(PREFIX, FIXED_DOMAINS_NEW[k], k) for k in NEW_FIXED]
    out += [hs.config_topic(PREFIX, NEW_LOCAL[k][0], k) for k in NEW_LOCAL if k.startswith(("tilt_", "pump_"))]
    out += [hs.config_topic(PREFIX, s.domain, s.key) for z in ("left", "right") for s in hs.zone_specs(z)[6:]]
    return out


FIXED_DOMAINS_NEW = {k: (B if k in ("fan_running", "air_valve", "fill_valve", "fill_in_progress", "light_on",
                                    "light_blinking", "setup_mode", "update_available", "updating") else S)
                     for k in NEW_FIXED}


# ---------- T-14: appended, never reordered ----------
def test_t14_new_keys_are_appended_after_the_old_ones():
    assert list(hs.FIXED_KEYS) == OLD_FIXED + NEW_FIXED
    assert [s.key for s in hs.zone_specs("left")] == [f"left_{k}" for k in OLD_SIDE + NEW_SIDE]
    assert all(s.reported for s in hs.zone_specs("left")[6:])
    assert not any(s.reported for s in hs.zone_specs("left")[:6])
    assert {s.key: s.domain for s in hs.FIXED if s.key in NEW_FIXED} == FIXED_DOMAINS_NEW


# ---------- T-15: the local frame's 28 new entities ----------
def test_t15_the_local_frame_gives_exactly_the_new_rows_in_their_form():
    ex = local_extras()
    new = {k: e for k, e in ex.items() if k not in GUARD}
    assert set(new) == set(NEW_LOCAL) and len(new) == 28
    for key, (dom, dc, unit, sc, diag, lim, state) in NEW_LOCAL.items():
        e = new[key]
        cfg = e.config
        assert e.domain == dom, key
        assert e.entity_id == f"{dom}.embertide_hub_{key}" == cfg["default_entity_id"]
        assert cfg["unique_id"] == f"embertide_hub_{key}" == e.unique_id
        assert e.config_topic == f"homeassistant/{dom}/embertide_hub_{key}/config"
        assert e.state_topic == f"embertide/bed/hub/{key}" == cfg["state_topic"]
        assert cfg["device"] == DEVICE and cfg["availability_topic"] == "embertide/status"
        assert cfg.get("device_class") == dc, key
        assert cfg.get("unit_of_measurement") == unit, key
        assert cfg.get("state_class") == sc, key
        assert (cfg.get("entity_category") == "diagnostic") == diag, key
        assert e.limited == lim, key
        assert e.state == state, key
        assert cfg["name"] and not any("command" in k for k in cfg), key
        if dom == B:
            assert cfg["payload_on"] == "ON" and cfg["payload_off"] == "OFF"
        else:
            assert "payload_on" not in cfg
        assert e.attributes is None and "json_attributes_topic" not in cfg


def test_t15_a_pump_running_and_powered_off_sensor_read_on_and_off():
    f = local_frame()
    f.hub.pump_on["left"], f.zones["right"].sensor.powered = True, False
    ex = local_extras(f)
    assert ex["pump_left_running"].state == "ON" and ex["pump_right_running"].state == "OFF"
    assert ex["right_sensor_powered"].state == "OFF"


# ---------- T-16: number precision ----------
def test_t16_pump_load_has_two_decimals_and_other_rows_keep_one():
    f = frame(pump_load={"left": 0.704, "right": 0.71, "rear": 0}, humidity=41.26)
    ex = {e.key: e for e in hs.extras(FakeDriver(frame=f), f, TZ)}
    assert ex["pump_left_load"].state == "0.7"
    assert ex["pump_right_load"].state == "0.71"
    assert ex["pump_rear_load"].state == "0"
    assert ex["humidity"].state == "41.3"
    assert hs.number_text(0.704, 2) == "0.7" and hs.number_text(41.26) == "41.3"


# ---------- T-17: never reported means no entity ----------
def test_t17_readings_never_reported_have_no_entity():
    ex = local_extras()
    assert not set(CLOUD_ONLY) & set(ex)
    f = frame()                                          # every capability, none of the new readings
    keys = {e.key for e in hs.extras(FakeDriver(frame=f), f, TZ)}
    new_kinds = set(NEW_FIXED) | {f"{z}_{k}" for z in ("left", "right") for k in NEW_SIDE}
    assert not keys & new_kinds
    assert not any(k.startswith(("tilt_", "pump_")) for k in keys)


def test_t17_without_the_capability_a_reported_reading_has_no_entity():
    f = local_frame()
    for cap, keys in ((Cap.HUB_HEALTH, ["internal_temperature", "fan_running", "tilt_x", "pump_left_running",
                                        "pump_left_state", "pump_left_load", "setup_mode"]),
                      (Cap.LED_DIM, ["light_on", "light_blinking"]),
                      (Cap.MEASURED_TEMP, ["left_inlet_temperature"]),
                      (Cap.OCCUPANCY, ["left_sensor_powered", "left_sensor_firmware", "left_sensor_algorithm"])):
        d = FakeDriver(caps=set(Cap) - {cap}, frame=f)
        got = {e.key for e in hs.extras(d, f, TZ)}
        assert not got & set(keys), cap
    cf = cloud_like_frame()
    got = {e.key for e in hs.extras(FakeDriver(caps=set(Cap) - {Cap.ZONE_TEMP}, frame=cf), cf, TZ)}
    assert "left_thermal_state" not in got and "model" in got      # the model needs no capability


# ---------- T-18: created once reported, then kept ----------
def test_t18_a_remembered_row_stays_while_its_reading_is_gone():
    f = frame()
    d = FakeDriver(frame=f)
    keys = ["internal_temperature", "left_sensor_firmware", "tilt_x", "pump_left_running", "pump_left_state",
            "pump_left_load"]
    doms = {"internal_temperature": S, "left_sensor_firmware": S, "tilt_x": S, "pump_left_running": B,
            "pump_left_state": S, "pump_left_load": S}
    announced = {hs.config_topic(PREFIX, doms[k], k) for k in keys}
    ex = {e.key: e for e in hs.extras(d, f, TZ, announced, prefix=PREFIX)}
    for k in keys:
        assert k in ex and ex[k].state == "None", k
    bare = {e.key for e in hs.extras(d, f, TZ, (), prefix=PREFIX)}
    assert not bare & set(keys)


def test_t18_families_are_remembered_across_a_restart():
    announced = {hs.config_topic(PREFIX, S, "tilt_x"), hs.config_topic(PREFIX, B, "pump_left_running"),
                 hs.config_topic(PREFIX, S, "pump_left_state"), hs.config_topic(PREFIX, S, "pump_left_load"),
                 hs.config_topic("other", S, "tilt_y"),                  # another prefix: ignored
                 hs.config_topic(PREFIX, S, "pump_right_running")}       # the wrong domain for this family
    d = FakeDriver(frame=None)
    ex = {e.key: e for e in hs.extras(d, None, TZ, announced, prefix=PREFIX)}
    for k in ("tilt_x", "pump_left_running", "pump_left_state", "pump_left_load"):
        assert k in ex and ex[k].state == "None", k
    assert ex["pump_left_running"].domain == B
    assert "tilt_y" not in ex and "pump_right_running" not in ex


# ---------- T-19: the families do not overlap and are capped ----------
def test_t19_fan_and_water_families_take_none_of_the_new_rows():
    ex = {e.key: e for e in hs.extras(FakeDriver(frame=None), None, TZ, every_new_topic(), prefix=PREFIX)}
    fans = [k for k in ex if k.startswith("fan_") and k.endswith("_rpm")]
    water = [k for k in ex if k.startswith("water_")]
    assert fans == [] and water == []
    for k in ("fill_in_progress", "fill_state", "fill_valve", "fan_running", "fan_target_power"):
        assert k in ex, k
    assert sum(1 for k in ex if k.startswith("pump_left_")) == 3
    specs = hs.specs(FakeDriver(frame=None), None, every_new_topic(), PREFIX)
    by_key = {}
    for s in specs:
        by_key.setdefault(s.key, s)
    assert by_key["fan_running"].source == "HubHealth.fan_on"
    assert by_key["fill_state"].source == "HubHealth.fill_state"


def test_t19_families_are_capped_and_keys_reduced():
    many = {f"a{i:02d}": float(i) for i in range(20)}
    f = frame(tilt=dict(many), pump_on={k: True for k in many}, pump_state={k: "OFF" for k in many},
              pump_load=dict(many))
    keys = [e.key for e in hs.extras(FakeDriver(frame=f), f, TZ)]
    assert sum(k.startswith("tilt_") for k in keys) == hs.MAX_TILT == 3
    for end in ("_running", "_state", "_load"):
        assert sum(k.startswith("pump_") and k.endswith(end) for k in keys) == hs.MAX_PUMPS == 4
    f = frame(tilt={"x/y": 1.0, "+": 2.0, "#": 3.0}, pump_on={"le+ft#": True, "/": False})
    keys = [e.key for e in hs.extras(FakeDriver(frame=f), f, TZ)]
    assert [k for k in keys if k.startswith("tilt_")] == ["tilt_x_y"]
    assert [k for k in keys if k.startswith("pump_")] == ["pump_le_ft_running"]
    assert all(set(k) <= set("abcdefghijklmnopqrstuvwxyz0123456789_") for k in keys)


# ---------- T-20: ids stay distinct ----------
async def test_t20_ids_are_distinct_with_a_person_named_hub(tmp_path):
    n = await sim_night(tmp_path)
    n.p1.name = "Hub"
    basic = HaBridge(n.c, "mqtt://x").discovery()
    for d, f in ((LocalDriver(local_frame()), local_frame()),
                 (FakeDriver(caps=CLOUD_CAPS, frame=cloud_like_frame()), cloud_like_frame())):
        extra = hs.extras(d, f, TZ, prefix=PREFIX, device=DEVICE)
        for fld in ("unique_id", "default_entity_id"):
            mine = [e.config[fld] for e in extra]
            assert len(mine) == len(set(mine)), fld
            assert not set(mine) & {c[fld] for _, c in basic}, fld
        topics = [e.config_topic for e in extra] + [e.state_topic for e in extra]
        assert len(topics) == len(set(topics))
        assert not set(topics) & {t for t, _ in basic}


def test_t20_the_cloud_like_frame_gives_its_rows():
    f = cloud_like_frame()
    ex = {e.key: e for e in hs.extras(FakeDriver(caps=CLOUD_CAPS, frame=f), f, TZ)}
    assert ex["model"].state == "OSCT001-1" and ex["model"].domain == S
    assert ex["fill_state"].state == "filled"
    assert ex["update_available"].state == "ON" and ex["update_available"].config["device_class"] == "update"
    assert ex["updating"].state == "OFF" and ex["fill_in_progress"].state == "OFF"
    assert ex["left_thermal_state"].state == "standby"
    assert "entity_category" not in ex["left_thermal_state"].config and not ex["left_thermal_state"].limited
    assert ex["left_sensor_problem"].state == "OFF" and ex["left_sensor_problem"].config["device_class"] == "problem"
    assert ex["right_sensor_firmware"].state == "11.00.09" and ex["right_sensor_hardware"].state == "01.00.00"
    assert "left_sensor_algorithm" not in ex and "left_sensor_powered" not in ex
    f.zones["left"].sensor.working = False
    assert {e.key: e for e in hs.extras(FakeDriver(caps=CLOUD_CAPS, frame=f), f, TZ)}["left_sensor_problem"].state \
        == "ON"


# ---------- T-21: offline means unknown ----------
def test_t21_offline_every_new_row_reads_unknown():
    for f in (local_frame(), cloud_like_frame()):
        f.online = False
        ex = {e.key: e for e in hs.extras(FakeDriver(frame=f), f, TZ, every_new_topic(), prefix=PREFIX)}
        new = [k for k in ex if k not in GUARD]
        assert new
        for k in new:
            assert ex[k].state == "None", k


# ---------- T-22: the bridge publishes the new rows ----------
async def test_t22_internal_temperature_is_rate_limited(tmp_path):
    n = await fake_night(tmp_path, frame(internal_c=30.0))
    b = bridge(n, "all")
    await b.announce()
    h = n.c.driver.frame.hub
    for i in range(300):
        h.internal_c = 30.0 + (i % 50) / 10
        await tick(n, b)
    final = h.internal_c
    for _ in range(30):
        await tick(n, b)
    got = b._client.on(st("internal_temperature"))
    assert len(got) <= 11 and got[-1] == hs.number_text(final)


async def test_t22_a_pump_switching_on_is_published_at_once(tmp_path):
    n = await fake_night(tmp_path, frame(pump_on={"left": False}))
    b = bridge(n, "all")
    await b.announce()
    await tick(n, b, dt=2)
    assert b._client.on(st("pump_left_running")) == ["OFF"]
    n.c.driver.frame.hub.pump_on["left"] = True
    await tick(n, b)
    assert b._client.on(st("pump_left_running")) == ["OFF", "ON"]


async def test_t22_a_tilt_axis_appearing_mid_run_is_announced_and_remembered(tmp_path):
    n = await fake_night(tmp_path, frame(tilt={"x": 1.0}))
    b = bridge(n, "all")
    await b.announce()
    await tick(n, b)
    assert not b._client.on(ct(S, "tilt_y"))
    n.c.driver.frame.hub.tilt["y"] = -0.5
    await tick(n, b)
    assert b._client.on(ct(S, "tilt_y")) and b._client.on(st("tilt_y")) == ["-0.5"]
    assert ct(S, "tilt_y") in n.store.get("ha_extra_topics")


# ═════════════════ WU-4: end to end (T-23 to T-26, T-28) ═════════════════
import copy                                                                 # noqa: E402
import time                                                                 # noqa: E402

from embertide.drivers.orion_cloud import parse_live                        # noqa: E402
from test_orion_cloud import EX6, ZONES, ex7, ex9                           # noqa: E402
from test_scenarios import Night                                            # noqa: E402

SERIAL = "AABBCCDDEEFF"
SECRETS = ("Home network", "192.168.1.50", "192.0.2.10", "02:00:00:00:00:01", SERIAL)
CLOUD_REAL_CAPS = set(OrionCloud.capabilities)


class CloudDriver:
    """A driver with the cloud driver's capabilities and zones, holding no connection."""
    id, name = "fake-cloud", "Fake cloud"
    capabilities = CLOUD_REAL_CAPS
    zones = list(OrionCloud.zones)

    def __init__(self, frame=None):
        self.frame = frame

    def latest(self):
        return self.frame


def cloud_frame(payload=None, ts=TS):
    return parse_live(copy.deepcopy(ex9() if payload is None else payload), ZONES, ts)


def cloud_extras(f, announced=()):
    return {e.key: e for e in hs.extras(CloudDriver(f), f, TZ, announced, prefix=PREFIX, device=DEVICE)}


# ---------- T-23: the cloud payloads at All ----------
def test_t23_ex9_gives_its_rows():
    ex = cloud_extras(cloud_frame())
    assert ex["model"].state == "OSCT001-1" and ex["model"].entity_id == "sensor.embertide_hub_model"
    assert "fill_state" not in ex
    assert ex["fill_in_progress"].state == "OFF" and ex["fill_in_progress"].domain == B
    assert ex["update_available"].state == "ON" and ex["update_available"].config["device_class"] == "update"
    assert ex["updating"].state == "OFF" and ex["updating"].config["device_class"] == "running"
    assert ex["left_thermal_state"].state == "standby"
    assert ex["left_thermal_state"].entity_id == "sensor.embertide_hub_left_thermal_state"
    assert ex["left_sensor_problem"].state == "OFF" and ex["left_sensor_problem"].config["device_class"] == "problem"
    assert ex["left_sensor_firmware"].state == "11.00.04" and ex["left_sensor_hardware"].state == "01.00.00"
    for key in ("model", "left_thermal_state", "left_sensor_problem", "left_sensor_firmware"):
        cfg = ex[key].config
        assert cfg["device"] == DEVICE and cfg["availability_topic"] == "embertide/status"
        assert not any("command" in k for k in cfg)
    # the local driver's readings are never reported by the cloud driver: none of their rows exist
    for key in ("right_thermal_state", "right_sensor_problem", "left_sensor_powered", "left_sensor_algorithm",
                "left_inlet_temperature", "internal_temperature", "fan_running", "air_valve", "light_on", "setup_mode"):
        assert key not in ex, key
    assert not [k for k in ex if k.startswith(("tilt_", "pump_", "water_")) or k.endswith("_rpm")]
    assert "water_problem" not in ex


def test_t23_ex6_fills_the_existing_hub_rows():
    ex = cloud_extras(cloud_frame(EX6))
    assert ex["firmware"].state == "2.6.0"
    assert ex["panel_firmware"].state == "2.5.0"
    assert ex["wifi_signal"].state == "-58"
    assert ex["last_restart"].state == hs.timestamp_value(TS - 266238, TZ)          # about 74 hours before the poll
    assert abs((TS - 266238) - (TS - 74 * 3600)) < 3600
    assert ex["online"].state == "ON"
    assert ex["problem"].state == "OFF"
    assert ex["status"].state == "All good"
    assert ex["safety"].state == "OFF"
    assert json.loads(ex["problem"].attributes) == {"status": "All good", "faults": []}
    for key in ("water_problem", "fan_power", "humidity", "room_temperature", "free_memory", "firmware_build",
                "last_command", "quiet_fan", "system_state"):
        assert key not in ex, key
    assert not [k for k in ex if k.startswith(("water_", "fan_")) and k != "fan_power"]


def test_t23_ex7_lists_the_faults():
    ex = cloud_extras(cloud_frame(ex7()))
    assert ex["problem"].state == "ON"
    names = [f["name"] for f in json.loads(ex["problem"].attributes)["faults"]]
    assert names == ["Fan isn't running", "The hub reported a problem"]
    assert ex["safety"].state == "ON"
    assert ex["status"].state == "Fan isn't running"


def test_t23_ex8_offline_reads_unknown():
    online = cloud_frame(EX6)
    announced = {e.config_topic for e in cloud_extras(online).values()}
    p = copy.deepcopy(EX6)
    p["status"]["online"] = False
    ex = cloud_extras(cloud_frame(p), announced)
    assert ex["online"].state == "OFF"
    assert set(ex) >= {"firmware", "panel_firmware", "wifi_signal", "last_restart", "problem", "status", "safety"}
    for k, e in ex.items():
        if k != "online":
            assert e.state == "None", k
    del p["status"]["online"]
    assert cloud_extras(cloud_frame(p))["online"].state == "ON"


# ---------- T-24: the privacy scan, local and cloud, Basic and All ----------
class _StatusDriver(FakeDriver):
    """A fake driver whose status() carries the serial, as the real drivers' does."""

    def status(self):
        return {"driver": self.id, "name": self.name, "online": True, "detail": "connected", "serial": SERIAL,
                "age_s": 0.0}


def _scan_text(client):
    return "\n".join(f"{t}\n{p}" for t, p, _ in client.sent)


async def test_t24_nothing_private_reaches_home_assistant(tmp_path):
    local = local_frame(ts=TS)
    local.hub.wifi_name = "Home network"                       # the fixture's address is already 192.168.1.50
    assert local.hub.wifi_address == "192.168.1.50"
    cloud = cloud_frame(EX6)
    for f, caps in ((local, set(OrionMqtt.capabilities)), (cloud, CLOUD_REAL_CAPS)):
        for level in ("basic", "all"):
            n = await fake_night(tmp_path / f"{caps is CLOUD_REAL_CAPS}-{level}", copy.deepcopy(f), caps)
            n.c.driver = _StatusDriver(caps=caps, frame=n.c.driver.frame)
            snap = n.c.snapshot()
            assert snap["system"]["serial"] == SERIAL                  # the serial is there to leak
            b = bridge(n, level)
            await b.announce()
            await b.publish_state(snap)
            await tick(n, b)
            text = _scan_text(b._client)
            assert b._client.sent
            if level == "all":
                assert "embertide_hub_" in text and st("wifi_signal") in text
            for secret in SECRETS:
                assert secret.lower() not in text.lower(), (level, secret)
            # the catalogue directly, attributes included
            ex = hs.extras(n.c.driver, n.c.driver.frame, TZ, prefix=PREFIX, device=DEVICE)
            blob = "\n".join(f"{e.config_topic}{json.dumps(e.config)}{e.state_topic}{e.state}{e.attributes or ''}"
                             for e in ex)
            for secret in SECRETS:
                assert secret.lower() not in blob.lower(), secret


# ---------- T-25: no flipping, end to end ----------
async def test_t25_versions_do_not_flip_through_the_hold_and_the_bridge(tmp_path):
    drv = OrionMqtt("mqtt://127.0.0.1:1883", serial=SERIAL)   # never started: nothing connects
    n = Night(tmp_path, "2026-11-05T23:30")
    n.c.driver = drv
    b = bridge(n, "all")
    now = time.time()
    for i, kind in enumerate(("valid", "garbage", "valid")):
        _, f = parse_status(f"orion/{SERIAL}/out", REAL[kind].encode("utf-8"), now + i)
        drv._frame = drv._hold_sensors(f)
        if i == 0:
            await b.announce()
        await tick(n, b, dt=2)
        r = drv.latest().zones["right"].sensor
        assert (r.fw_version, r.hw_version) == ("11.00.09", "01.00.00"), kind
    assert b._client.on(st("right_sensor_firmware")) == ["11.00.09"]
    assert b._client.on(st("right_sensor_hardware")) == ["01.00.00"]
    assert b._client.on(st("left_sensor_firmware")) == ["11.00.09"]


# ---------- T-26: read-only, and Basic unchanged ----------
async def test_t26_the_new_rows_take_no_command_and_basic_has_none(tmp_path):
    for e in local_extras().values():
        assert not any("command" in k for k in e.config), e.key
    n = await sim_night(tmp_path)
    before = repr(n.bed.latest()), list(getattr(n.bed, "commands", []) or [])
    b = bridge(n, "all")
    for key in ("pump_left_running", "fill_valve", "air_valve", "light_on", "setup_mode", "updating"):
        assert await b.handle(f"embertide/bed/hub/{key}/set", "ON") is None
    assert (repr(n.bed.latest()), list(getattr(n.bed, "commands", []) or [])) == before
    assert b.handled == 0
    n2 = await fake_night(tmp_path / "basic", local_frame(), set(OrionMqtt.capabilities))
    disc = bridge(n2, "basic").discovery()
    assert disc and not any("embertide_hub_" in t or "embertide_hub_" in json.dumps(c) for t, c in disc)


# ---------- T-28: the docs name the four new families ----------
def test_t28_the_docs_name_the_new_family_patterns():
    text = (pathlib.Path(__file__).resolve().parents[2] / "docs" / "integrations.md").read_text(encoding="utf-8")
    for pattern in ("sensor.embertide_hub_tilt_<axis>", "binary_sensor.embertide_hub_pump_<side>_running",
                    "sensor.embertide_hub_pump_<side>_state", "sensor.embertide_hub_pump_<side>_load"):
        assert f"`{pattern}`" in text, pattern
