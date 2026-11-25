import json

import pytest

from embertide.drivers.base import CommandError
from embertide.drivers.orion_mqtt import parse_status, validate


def payload(**over):
    s1 = [4, 5, 20, 19, 0, 0, 0, 14, 1, 1, 0, 10, 20, 30, 40, 58, 14, 0, 0, 0, 0, 0, 0, 0]
    s2 = [4, 6, 20, 19, 0, 0, 0, 14, 1, 1, 0, 11, 21, 31, 41, 0, 0, 5, 0, 0, 0, 0, 0, 0]
    d = {"type": "status", "serial": "OSCT123", "system_state": "SYSTEM_ON", "fw": {"version": "2.6.2"},
         "tec": {"left": {"setpoint": 17.22, "control_enabled": True}, "right": {"setpoint": 22.0, "control_enabled": False}},
         "temps": {"ib_left": 18.1, "ib_right": 21.4}, "fans": {"quiet_mode": True},
         "led": {"led_brightness": 20, "idle_r": 226, "idle_g": 168, "idle_b": 120},
         "sensors": {"sensor1": s1, "sensor2": s2}, "errors": {"e1": 0}}
    d.update(over)
    return json.dumps(d).encode()


def test_parse_status():
    serial, f = parse_status("orion/OSCT123/out", payload(), 1.0)
    assert serial == "OSCT123" and f.firmware == "2.6.2" and f.quiet_mode is True
    assert f.zones["left"].on is True and f.zones["left"].setpoint_c == 17.22 and f.zones["left"].measured_c == 18.1
    assert f.zones["left"].sensor.status == 0 and f.zones["left"].sensor.hr == 58 and f.zones["left"].sensor.br == 14
    assert f.zones["right"].sensor.status == 5 and f.zones["right"].sensor.hr is None
    assert f.rgb == (226, 168, 120) and f.fault is False


def test_parse_rejects_wrong_topic_or_serial():
    assert parse_status("orion/OTHER/out", payload(), 1.0) is None
    assert parse_status("orion/OSCT123/in", payload(), 1.0) is None
    assert parse_status("orion/OSCT123/out", b"not json", 1.0) is None


def test_validate_allowlist():
    assert validate("set left 17.2222") == "SET LEFT 17.22"
    assert validate("SET BOTH 18 22") == "SET BOTH 18 22"
    assert validate("clear right") == "CLEAR RIGHT"
    for bad in ("OTA http://x/fw.bin", "ERASE WIFI", "IB UPDATE", "SET LEFT 60", "LPUMP OFF", "SET LEFT 18 19"):
        with pytest.raises(CommandError):
            validate(bad)


# ---- real frames captured from firmware 2.6.2 (serial, Wi-Fi name and IP replaced) ----
import json as _json
import pathlib as _pl

REAL = _json.loads((_pl.Path(__file__).parent / "fixtures" / "orion_fw262_frames.json").read_text(encoding="utf-8"))


def test_real_frames_all_parse():
    from embertide.drivers.orion_mqtt import parse_status
    assert parse_status("orion/AABBCCDDEEFF/out", REAL["online"].encode(), 0) is None   # the bed's hello message
    for kind, payload in REAL.items():
        if kind == "online":
            continue
        r = parse_status("orion/AABBCCDDEEFF/out", payload.encode("utf-8"), 0)
        assert r is not None, kind                      # nan and garbled version strings no longer lose the frame
        serial, f = r
        assert serial == "AABBCCDDEEFF" and f.firmware == "2.6.2"


def test_empty_sensor_block_is_not_someone_in_bed():
    from embertide.drivers.orion_mqtt import parse_status
    _, f = parse_status("orion/AABBCCDDEEFF/out", REAL["valid"].encode(), 0)
    assert f.zones["left"].sensor.status is None        # sensor1 = all zeros: no report, NOT status 0 ("in bed")
    assert f.zones["right"].sensor.status in (None, 5)  # sensor2 real report: not in bed


def test_booting_zero_temperature_is_ignored():
    from embertide.drivers.orion_mqtt import parse_status
    _, f = parse_status("orion/AABBCCDDEEFF/out", REAL["nan"].encode(), 0)
    assert f.zones["left"].measured_c is None or f.zones["left"].measured_c > 1


def test_driver_holds_last_report_across_empty_blocks():
    from embertide.drivers.base import BedFrame, SensorFrame, ZoneFrame
    from embertide.drivers.orion_mqtt import OrionMqtt
    d = OrionMqtt("mqtt://x")
    real = SensorFrame(status=5, clock=(1, 2, 3, 4))
    f1 = d._hold_sensors(BedFrame(ts=100, zones={"right": ZoneFrame(sensor=real)}))
    f2 = d._hold_sensors(BedFrame(ts=105, zones={"right": ZoneFrame(sensor=SensorFrame())}))
    assert f2.zones["right"].sensor.status == 5         # gap bridged
    f3 = d._hold_sensors(BedFrame(ts=120, zones={"right": ZoneFrame(sensor=SensorFrame())}))
    assert f3.zones["right"].sensor.status is None       # quiet for too long: unknown


# ---- the hub readings the "All sensors" level used to miss (ha-hub-gaps, T-1 to T-6) ----
def _real(kind, ts=0):
    from embertide.drivers.orion_mqtt import parse_status
    _, f = parse_status("orion/AABBCCDDEEFF/out", REAL[kind].encode("utf-8"), ts)
    return f


VERSIONS = ("11.00.09", "01.00.00", "02.02.06")


def _versions(f, side):
    s = f.zones[side].sensor
    return s.fw_version, s.hw_version, s.algo_version


def test_t1_valid_message_new_local_fields():
    f = _real("valid")
    h = f.hub
    assert h.internal_c == 28.21
    assert h.tilt == {"x": 1.15, "y": -0.55, "z": 88.72}
    assert h.fan_on is False and h.fan_target_pwm == 100
    assert h.pump_on == {"left": False, "right": False}
    assert h.pump_state == {"left": "OFF", "right": "OFF"}
    assert h.pump_load == {"left": 0.0, "right": 0.0}
    assert h.air_valve_open is False and h.fill_valve_open is False
    assert h.filling is False and h.setup_mode is False
    assert f.light_on is False and f.light_blinking is False
    assert f.zones["left"].inlet_c == 23.3 and f.zones["right"].inlet_c == 23.0
    for side in ("left", "right"):
        assert f.zones[side].sensor.powered is True
        assert _versions(f, side) == VERSIONS
    # cloud-only readings stay unset for the local driver
    assert f.model is None
    assert h.fill_state is None and h.update_available is None and h.updating is None
    for side in ("left", "right"):
        assert f.zones[side].thermal_state is None and f.zones[side].sensor.working is None


def test_t2_nan_message_leaves_the_unreadable_values_unset():
    f = _real("nan")
    h = f.hub
    assert h.internal_c is None and h.tilt == {}
    assert f.zones["left"].inlet_c is None and f.zones["right"].inlet_c is None
    assert h.pump_state == {"left": "DEFAULT", "right": "DEFAULT"}
    for side in ("left", "right"):
        assert f.zones[side].sensor.powered is True
        assert _versions(f, side) == (None, None, None)
    assert f.firmware == "2.6.2" and set(f.zones) == {"left", "right"}       # the frame and its old fields still parse


def test_t3_garbage_message_blanks_every_version():
    f = _real("garbage")
    assert f.hub.internal_c == 28.27 and f.hub.tilt["z"] == 88.71
    for side in ("left", "right"):          # the message repair blanks the left sensor's good strings too
        assert _versions(f, side) == (None, None, None)


def test_t4_wrong_types_and_out_of_range_values_are_not_reported():
    from embertide.drivers.orion_mqtt import parse_status
    s1 = [4, 5, 20, 19, 0, 0, 0, 14, 1, 1, 0, 10, 20, 30, 40, 58, 14, 0, 0, 0, 0, 0, 0, 0]
    bad = payload(
        temps={"ib_left": 18.1, "ib_right": 21.4, "cb_filtered": "hot", "ib_left_in": "warm", "ib_right_in": 150},
        angles=[1, 2, 3],
        fans={"quiet_mode": True, "enabled": 2, "target_pwm": 250},
        actuators={"lpump": 2, "rpump": "yes", "airvalve": None, "fillvalve": "open"},
        pumps={"left": "OFF", "right": {"status": "   ", "filtered": "0.5"}},
        filling_with_pumps_on="sometimes", ble_provisioning=5,
        led={"led_brightness": 20, "idle_r": 226, "idle_g": 168, "idle_b": 120, "led_state": [], "blink_enabled": "x"},
        sensors={"sensor1": s1, "sensor2": s1, "poweredSensor1": "on", "poweredSensor2": 7,
                 "sensor1FirmwareVersion": "11.00 09", "sensor1HardwareVersion": "1" * 33,
                 "sensor1AlgorithmVersion": "02.02\n06", "sensor2FirmwareVersion": 11,
                 "sensor2HardwareVersion": "", "sensor2AlgorithmVersion": None},
    )
    _, f = parse_status("orion/OSCT123/out", bad, 1.0)
    h = f.hub
    assert h.internal_c is None and h.tilt == {}
    assert h.fan_on is None and h.fan_target_pwm is None
    assert h.pump_on == {} and h.pump_state == {} and h.pump_load == {}
    assert h.air_valve_open is None and h.fill_valve_open is None
    assert h.filling is None and h.setup_mode is None
    assert f.light_on is None and f.light_blinking is None
    for side in ("left", "right"):
        assert f.zones[side].inlet_c is None
        assert f.zones[side].sensor.powered is None
        assert _versions(f, side) == (None, None, None)
    # the existing readings of the same message are intact
    assert f.firmware == "2.6.2" and f.quiet_mode is True and f.rgb == (226, 168, 120)
    assert f.zones["left"].measured_c == 18.1 and f.zones["left"].sensor.hr == 58


def test_t4_odd_axes_and_flag_shapes():
    from embertide.drivers.orion_mqtt import _flag, clean_version, parse_status
    _, f = parse_status("orion/OSCT123/out", payload(
        angles={"angle_x_filtered": 181, "angle_y_filtered": "1", "angle_z_filtered": -180},
        actuators={"lpump": 1, "rpump": 0}, filling_with_pumps_on=1, temps={"cb_filtered": 1}), 1.0)
    assert f.hub.tilt == {"z": -180}
    assert f.hub.pump_on == {"left": True, "right": False} and f.hub.filling is True
    assert f.hub.internal_c is None                         # 1 is not above 1
    assert [_flag(v) for v in (True, False, "true", "false", 0, 1, 2, "yes", None, "1")] == \
        [True, False, True, False, False, True, None, None, None, None]
    assert clean_version(" 11.00.09 ") == "11.00.09" and clean_version("a" * 32) == "a" * 32
    assert clean_version("a" * 33) is None and clean_version('11"x') is None and clean_version("") is None


def test_t5_versions_and_block_readings_are_held_without_sharing_objects():
    from embertide.drivers.orion_mqtt import OrionMqtt
    d = OrionMqtt("mqtt://127.0.0.1:1883")
    f1 = d._hold_sensors(_real("valid", 100))
    assert f1.zones["right"].sensor.status == 5
    for side in ("left", "right"):
        assert _versions(f1, side) == VERSIONS

    g = _real("garbage", 101)
    assert g.zones["right"].sensor.status is None              # an empty block in this message
    g.zones["right"].sensor.powered = False                   # a fresh reading the hold must not overwrite
    f2 = d._hold_sensors(g)
    assert f2.zones["right"].sensor.status == 5                # held block reading
    assert f2.zones["right"].sensor.powered is False           # fresh, not the held object's
    assert f2.zones["right"].sensor is not f1.zones["right"].sensor
    for side in ("left", "right"):
        assert _versions(f2, side) == VERSIONS

    f2.zones["right"].sensor.status = 99                       # changing a frame never changes what is held
    f2.zones["right"].sensor.fw_version = "changed"
    f3 = d._hold_sensors(_real("valid", 102))
    for side in ("left", "right"):
        assert _versions(f3, side) == VERSIONS
    f4 = d._hold_sensors(_real("garbage", 103))
    assert f4.zones["right"].sensor.status == 5
    assert _versions(f4, "right") == VERSIONS


def test_t6_commands_stay_refused_and_faults_map_as_before():
    from embertide.drivers.orion_mqtt import BLOCKED, fault_for, parse_hub
    assert BLOCKED == ("OTA", "ERASE", "IB UPDATE", "FILLVALVE", "AIRVALVE", "RPUMP", "LPUMP", "RTEC", "LTEC", "FAN PWM")
    for bad in ("LPUMP ON", "RPUMP ON", "FILLVALVE OPEN", "AIRVALVE OPEN", "OTA http://x/fw.bin"):
        with pytest.raises(CommandError):
            validate(bad)
    for flag, pair in (("FAN_OFF_TEC_ON", ("fan_stopped", None)), ("LTEC_FAULT_DETECTED", ("zone_fault", "left")),
                       ("SOMETHING_NEW", ("unknown", None))):
        assert fault_for(flag) == pair
        assert parse_hub({"errors": {flag: 1}}).faults == [pair]
