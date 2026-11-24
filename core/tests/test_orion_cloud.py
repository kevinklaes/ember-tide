"""The cloud driver's parsing, on Python dicts shaped as the community-documented live response. No network."""

import copy

from embertide.drivers.base import Cap
from embertide.drivers.orion_cloud import OrionCloud, parse_live

ZONES = {"left": "zone_a", "right": "zone_b"}
TS = 1_800_000_000.0
SERIAL = "AABBCCDDEEFF"

EX6 = {
    "zones": [{"id": "zone_a", "on": True, "temp": 20.5}, {"id": "zone_b", "on": False, "temp": 25.0}],
    "status": {
        "online": True,
        "firmware": {"cb": "2.6.0", "ib": "2.5.0"},
        "network": {"rssi": -58, "uptime": 266238, "name": "Home network", "ip": "192.0.2.10", "mac": "02:00:00:00:00:01"},
        "safety": {"error": False, "error_codes": []},
    },
}


def ex7():
    p = copy.deepcopy(EX6)
    p["status"]["safety"] = {"error": True, "error_codes": ["FAN_OFF_TEC_ON", "SOMETHING_NEW"]}
    return p


def ex9():
    return {
        "model": "OSCT001-1",
        "water_fill": "unknown",
        "is_in_water_fill_mode": False,
        "status": {
            "pending_update": {"is_available": True},
            "firmware_update": {"in_progress": False},
            "zones": [{"id": "zone_a", "temp": 21.9, "thermal_state": "standby"}],
            "sensors": {"sensor1": {"is_working": True, "firmware_version": "11.00.04", "hardware_version": "01.00.00"}},
        },
    }


def cloud():
    return OrionCloud("not-a-real-key", serial=SERIAL)      # never started: no request is sent


# T-7
def test_ex6_hub_health():
    f = parse_live(copy.deepcopy(EX6), ZONES, TS)
    h = f.hub
    assert f.firmware == "2.6.0" and h.fw_version == "2.6.0"
    assert h.fw_panel == "2.5.0"
    assert h.wifi_dbm == -58
    assert h.uptime_s == 266238
    assert h.safety_ok is True
    assert h.faults == []
    assert f.online is True
    assert h.water_ok is None and h.water_raw == {}


def test_top_level_firmware_wins():
    p = copy.deepcopy(EX6)
    p["firmware"] = {"version": "2.7.1"}
    f = parse_live(p, ZONES, TS)
    assert f.firmware == "2.7.1" and f.hub.fw_version == "2.7.1"
    assert f.hub.fw_panel == "2.5.0"


# T-8
def test_ex7_faults():
    h = parse_live(ex7(), ZONES, TS).hub
    assert h.faults == [("fan_stopped", None), ("unknown", None)]
    assert h.safety_ok is False


def test_zone_fault_flag_has_its_side():
    p = ex7()
    p["status"]["safety"]["error_codes"] = ["ltec_fault_detected", " RTEC_FAULT_DETECTED "]
    assert parse_live(p, ZONES, TS).hub.faults == [("zone_fault", "left"), ("zone_fault", "right")]


# T-9
def test_online_flag():
    p = copy.deepcopy(EX6)
    p["status"]["online"] = False
    assert parse_live(p, ZONES, TS).online is False
    for v in (None, True, "false", 0):
        p["status"]["online"] = v
        assert parse_live(p, ZONES, TS).online is True
    del p["status"]["online"]
    assert parse_live(p, ZONES, TS).online is True


# T-10
def test_ex9_model_water_update_thermal_sensor():
    f = parse_live(ex9(), ZONES, TS)
    h = f.hub
    assert f.model == "OSCT001-1"
    assert h.fill_state is None
    assert h.filling is False
    assert h.update_available is True
    assert h.updating is False
    assert f.zones["left"].thermal_state == "standby"
    assert f.zones["right"].thermal_state is None
    s = f.zones["left"].sensor
    assert s.working is True and s.fw_version == "11.00.04" and s.hw_version == "01.00.00"
    assert s.algo_version is None and s.powered is None
    r = f.zones["right"].sensor
    assert r.working is None and r.fw_version is None and r.hw_version is None


def test_fill_state_word():
    p = ex9()
    for word in ("UNKNOWN", " Unknown "):
        p["water_fill"] = word
        assert parse_live(p, ZONES, TS).hub.fill_state is None
    p["water_fill"] = " normal "
    assert parse_live(p, ZONES, TS).hub.fill_state == "normal"


# T-11
def test_existing_readings_unchanged():
    p = {
        "zones": [{"id": "zone_a", "on": True, "temp": 19.5}, {"id": "zone_b", "on": False, "temp": 30.0}],
        "status": {
            "zones": [{"id": "zone_a", "temp": 22.4}, {"id": "zone_b", "temp": 24.1}],
            "sensors": {"sensor1": {"status": 0, "heart_rate": 62, "breath_rate": 14},
                        "sensor2": {"status": 5, "heart_rate": 0, "breath_rate": 255}},
        },
        "firmware": {"version": "2.6.0"},
        "quiet_mode": True,
        "led_brightness": 40,
    }
    f = parse_live(p, ZONES, TS)
    left, right = f.zones["left"], f.zones["right"]
    assert (left.on, left.setpoint_c, left.measured_c) == (True, 19.5, 22.4)
    assert (right.on, right.setpoint_c, right.measured_c) == (False, 30.0, 24.1)
    assert (left.sensor.status, left.sensor.hr, left.sensor.br, left.sensor.clock) == (0, 62, 14, (TS,))
    assert (right.sensor.status, right.sensor.hr, right.sensor.br) == (5, None, None)
    assert f.ts == TS and f.firmware == "2.6.0" and f.quiet_mode is True and f.brightness == 40
    # a non-default zone map
    g = parse_live(p, {"left": "zone_b", "right": "zone_a"}, TS)
    assert (g.zones["left"].setpoint_c, g.zones["left"].measured_c) == (30.0, 24.1)
    assert (g.zones["right"].setpoint_c, g.zones["right"].measured_c) == (19.5, 22.4)


# T-12
def test_tolerance():
    assert parse_live({"status": [1, 2]}, ZONES, TS).hub.safety_ok is None
    assert parse_live({}, ZONES, TS).zones["left"].on is None
    assert parse_live(None, ZONES, TS).online is True
    p = {
        "zones": ["zone_a", None, {"id": "zone_b", "on": True, "temp": 21.0}],
        "model": "OSCT001-AABBCCDDEEFF",
        "status": {
            "zones": [3, {"id": "zone_a", "temp": 22.0, "thermal_state": ["heating"]}],
            "sensors": "sensor1",
            "safety": {"error": "yes", "error_codes": "FAN_OFF_TEC_ON"},
            "network": {"rssi": 12, "uptime": -5},
            "firmware": {"cb": 26, "ib": ""},
        },
    }
    f = parse_live(p, ZONES, TS, SERIAL)
    assert f.zones["right"].on is True and f.zones["right"].setpoint_c == 21.0
    assert f.zones["left"].measured_c == 22.0 and f.zones["left"].thermal_state is None
    assert f.zones["left"].sensor.status is None and f.zones["left"].sensor.clock == (TS,)
    h = f.hub
    assert h.safety_ok is None and h.faults == []
    assert h.wifi_dbm is None and h.uptime_s is None
    assert f.firmware is None and h.fw_version is None and h.fw_panel is None
    assert f.model is None
    # non-text fault entries are skipped, the text ones read; at most 32 are read
    p["status"]["safety"] = {"error": False, "error_codes": [None, 7, {"x": 1}, "PUMP_CURRENT", " "]}
    assert parse_live(p, ZONES, TS).hub.faults == [("pump", None)]
    p["status"]["safety"]["error_codes"] = ["FAN_OFF_TEC_ON"] * 50
    assert len(parse_live(p, ZONES, TS).hub.faults) == 32
    # garbled versions
    q = ex9()
    q["status"]["sensors"]["sensor1"].update(firmware_version="11.00\n.04", hardware_version="x" * 33, is_working="yes")
    s = parse_live(q, ZONES, TS).zones["left"].sensor
    assert s.fw_version is None and s.hw_version is None and s.working is None
    # non-finite and boolean numbers
    q = copy.deepcopy(EX6)
    q["status"]["network"].update(rssi=float("-inf"), uptime=True)
    h = parse_live(q, ZONES, TS).hub
    assert h.wifi_dbm is None and h.uptime_s is None and h.fw_panel == "2.5.0"


# T-13
def test_network_identity_never_read():
    f = parse_live(copy.deepcopy(EX6), ZONES, TS, SERIAL)
    text = repr(f)
    for secret in ("Home network", "192.0.2.10", "02:00:00:00:00:01", SERIAL):
        assert secret not in text
    assert f.hub.wifi_name is None and f.hub.wifi_address is None


def test_capabilities():
    assert {Cap.HUB_HEALTH, Cap.FAULTS} <= OrionCloud.capabilities
    for cap in (Cap.WATER_STATUS, Cap.LED_RGB, Cap.REBOOT, Cap.WATER_FILL, Cap.RAW_CONSOLE):
        assert cap not in OrionCloud.capabilities


def test_version_hold():
    d = cloud()
    d._frame = d._parse(ex9())
    bad = ex9()
    bad["status"]["sensors"]["sensor1"].update(firmware_version="11.0#\x00", hardware_version="")
    d._frame = d._parse(bad)
    s = d._frame.zones["left"].sensor
    assert s.fw_version == "11.00.04" and s.hw_version == "01.00.00"
    newer = ex9()
    newer["status"]["sensors"]["sensor1"]["firmware_version"] = "11.00.05"
    d._frame = d._parse(newer)
    assert d._frame.zones["left"].sensor.fw_version == "11.00.05"


def test_status_carry_over():
    d = cloud()
    first = ex7()
    first["model"] = "OSCT001-1"
    first["status"]["zones"] = [{"id": "zone_a", "temp": 21.9, "thermal_state": "heating"}]
    first["status"]["sensors"] = {"sensor1": {"status": 0, "is_working": False, "firmware_version": "11.00.04",
                                              "hardware_version": "01.00.00"}}
    first["status"]["online"] = False
    d._frame = d._parse(first)
    reply = {"zones": [{"id": "zone_a", "on": True, "temp": 18.0}]}     # what a set_zone reply may carry
    f = d._parse(reply)
    assert f.hub.faults == [("fan_stopped", None), ("unknown", None)]
    assert f.hub.safety_ok is False and f.hub.wifi_dbm == -58
    assert f.model == "OSCT001-1" and f.online is False
    left = f.zones["left"]
    assert left.thermal_state == "heating"
    assert left.sensor.working is False and left.sensor.fw_version == "11.00.04" and left.sensor.hw_version == "01.00.00"
    assert left.on is True and left.setpoint_c == 18.0
    assert left.measured_c is None and left.sensor.status is None
    # with no previous frame the same body gives an unset hub and no error
    g = cloud()._parse(reply)
    assert g.hub.faults == [] and g.hub.safety_ok is None and g.hub.wifi_dbm is None
    assert g.online is True and g.model is None
    assert g.zones["left"].thermal_state is None and g.zones["left"].sensor.working is None


def test_poll_with_status_does_not_carry_over():
    d = cloud()
    d._frame = d._parse(ex7())
    f = d._parse(copy.deepcopy(EX6))
    assert f.hub.faults == [] and f.hub.safety_ok is True
