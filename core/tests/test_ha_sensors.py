"""The "All sensors" catalogue (ha_sensors.py): which extra Home Assistant entities exist, their form and their values.

These tests work on the catalogue's plain functions with the simulator and hand-built frames; the bridge's use of the
catalogue (publishing, the rate limit, removal) is tested separately."""

import json
from zoneinfo import ZoneInfo

import pytest

from embertide import ha_sensors as hs
from embertide.drivers.base import BedFrame, Cap, HubHealth, SensorFrame, ZoneFrame
from embertide.ha_bridge import HaBridge
from test_scenarios import Night

TZ = ZoneInfo("America/New_York")
PREFIX = "homeassistant"
NET_NAME, NET_ADDR = "Home network", "192.0.2.10"     # the simulator's stand-ins

PINNED_FIXED = ["problem", "status", "water_problem", "safety", "fan_power", "quiet_fan", "humidity",
                "room_temperature", "wifi_signal", "last_restart", "free_memory", "firmware", "firmware_build",
                "panel_firmware", "last_command", "online", "system_state", "light_brightness", "light_color"]
FIXED_DOMAINS = {"problem": "binary_sensor", "water_problem": "binary_sensor", "safety": "binary_sensor",
                 "quiet_fan": "binary_sensor", "online": "binary_sensor"}

# D-4: (device_class, unit, state_class, diagnostic, rate limited) for every row
FORM = {
    "problem": ("problem", None, None, False, False),
    "status": (None, None, None, True, False),
    "water_problem": ("problem", None, None, False, False),
    "water_reservoir": (None, None, "measurement", True, True),
    "safety": ("safety", None, None, True, False),
    "fan_left_rpm": (None, "rpm", "measurement", True, True),
    "fan_right_rpm": (None, "rpm", "measurement", True, True),
    "fan_power": (None, "%", "measurement", True, True),
    "quiet_fan": (None, None, None, True, False),
    "humidity": ("humidity", "%", "measurement", False, True),
    "wifi_signal": ("signal_strength", "dBm", "measurement", True, True),
    "last_restart": ("timestamp", None, None, True, False),
    "free_memory": ("data_size", "kB", "measurement", True, True),
    "firmware": (None, None, None, True, False),
    "firmware_build": (None, None, None, True, False),
    "panel_firmware": (None, None, None, True, False),
    "last_command": (None, None, None, True, False),
    "online": ("connectivity", None, None, True, False),
    "system_state": (None, None, None, True, False),
    "light_brightness": (None, "%", "measurement", True, True),
    "light_color": (None, None, None, True, False),
}
for _z in ("left", "right"):
    FORM.update({
        f"{_z}_temperature": ("temperature", "°C", "measurement", False, True),
        f"{_z}_setpoint": ("temperature", "°C", "measurement", False, True),
        f"{_z}_power": ("power", None, None, False, False),
        f"{_z}_sensor_state": (None, None, None, True, False),
        f"{_z}_heart_rate": (None, "bpm", "measurement", False, True),
        f"{_z}_breathing_rate": (None, "br/min", "measurement", False, True),
    })


def bed_device(n):
    """The Bed device block as Basic announces it (on leak_hold)."""
    b = HaBridge(n.c, "mqtt://x")
    return next(c for t, c in b.discovery() if t.endswith("/embertide_leak_hold/config"))["device"]


def cat(n, announced=(), driver=None, frame="latest", **kw):
    f = n.bed.latest() if frame == "latest" else frame
    return {e.key: e for e in hs.extras(driver or n.bed, f, TZ, announced, prefix=PREFIX, device=bed_device(n), **kw)}


class FakeDriver:
    """A driver that returns a hand-built frame, so each reading is exactly what the test says."""
    id, name = "fake", "Fake"

    def __init__(self, caps=None, zones=("left", "right"), frame=None):
        self.capabilities = set(caps if caps is not None else Cap)
        self.zones = list(zones)
        self.frame = frame

    def latest(self):
        return self.frame


def frame(**hub):
    h = HubHealth(**{"water_ok": True, "safety_ok": True, "uptime_s": 100, **hub})
    zones = {z: ZoneFrame(on=True, setpoint_c=20.0, measured_c=21.04, sensor=SensorFrame(status=0, hr=60, br=14))
             for z in ("left", "right")}
    return BedFrame(ts=1_800_000_000.0, zones=zones, system_state="SYSTEM_ON", firmware="fw-1", quiet_mode=False,
                    brightness=30, rgb=(1, 2, 255), fault=False, online=True, hub=h)


async def sim_night(tmp_path, command=True):
    n = Night(tmp_path, "2026-11-05T23:30")
    if command:
        await n.bed.command("IB DIMMER 20")       # so last_command is set
    n.bed._tick()
    return n


# ---------- the level ----------
def test_resolve_level_saved_beats_env_beats_basic():
    assert hs.LEVELS == ("basic", "all")
    assert hs.resolve_level(None, None) == "basic"
    assert hs.resolve_level({}, "all") == "all"
    assert hs.resolve_level({"sensors": "basic"}, "all") == "basic"
    assert hs.resolve_level({"sensors": "all"}, "basic") == "all"
    assert hs.resolve_level({"sensors": "most"}, "all") == "all"
    assert hs.resolve_level({"sensors": "most"}, "everything") == "basic"
    assert hs.resolve_level({"url": "mqtt://x"}, None) == "basic"
    assert hs.MIN_INTERVAL_S == 30.0


# ---------- T-2: the simulator at level all ----------
async def test_simulator_extras_have_the_table_form(tmp_path):
    n = await sim_night(tmp_path)
    dev = bed_device(n)
    ex = cat(n)
    expected = set(FORM) - {"room_temperature"}
    assert set(ex) == expected and len(ex) == 33
    for key, e in ex.items():
        dc, unit, sc, diag, lim = FORM[key]
        cfg = e.config
        assert cfg["device"] == dev, key
        assert cfg["availability_topic"] == "embertide/status"
        assert cfg["unique_id"] == f"embertide_hub_{key}"
        assert cfg["default_entity_id"] == f"{e.domain}.embertide_hub_{key}"
        assert cfg["state_topic"] == f"embertide/bed/hub/{key}" == e.state_topic
        assert e.config_topic == f"{PREFIX}/{e.domain}/embertide_hub_{key}/config"
        assert cfg.get("device_class") == dc, key
        assert cfg.get("unit_of_measurement") == unit, key
        assert cfg.get("state_class") == sc, key
        assert (cfg.get("entity_category") == "diagnostic") == diag, key
        assert e.limited == lim, key
        assert not any("command" in k for k in cfg), key       # read-only (BR-4)
        if e.domain == "binary_sensor":
            assert cfg["payload_on"] == "ON" and cfg["payload_off"] == "OFF"
        assert cfg["name"]
    assert ex["fan_left_rpm"].state == "1800"
    assert ex["fan_right_rpm"].state == "1790"
    assert ex["humidity"].state == "42"
    assert ex["water_reservoir"].state == "1"
    assert ex["light_color"].state == "#e2a878"
    assert ex["online"].state == "ON"
    assert ex["last_command"].state == "IB DIMMER 20"
    assert ex["problem"].state == "OFF" and ex["status"].state == "All good"
    assert ex["problem"].config["json_attributes_topic"] == "embertide/bed/hub/problem/attributes"


async def test_simulator_has_32_extras_before_any_command(tmp_path):
    n = await sim_night(tmp_path, command=False)
    ex = cat(n)
    assert "last_command" not in ex and len(ex) == 32


def test_values_are_formatted_plainly():
    d = FakeDriver(frame=frame(humidity=41.26, fan_pwm=40, free_memory_kb=57, wifi_dbm=-52, fw_version=" v2 ",
                               water_raw={"Reservoir": 0.55}, fan_rpm={"left": 1800}))
    ex = {e.key: e for e in hs.extras(d, d.frame, TZ)}
    assert ex["humidity"].state == "41.3"
    assert ex["left_temperature"].state == "21"
    assert ex["left_setpoint"].state == "20"
    assert ex["water_reservoir"].state == "0.6"
    assert ex["firmware"].state == "v2"
    assert ex["light_color"].state == "#0102ff"
    assert ex["left_power"].state == "ON"
    assert ex["left_sensor_state"].state == "in bed"
    assert ex["last_restart"].state == "2027-01-15T02:58:20-05:00"     # frame time minus 100 s uptime, to the second
    long = FakeDriver(frame=frame(last_command="X" * 400))
    assert {e.key: e for e in hs.extras(long, long.frame, TZ)}["last_command"].state == "X" * 250


def test_unknown_sensor_code_reads_its_number():
    f = frame()
    f.zones["left"].sensor.status = 42
    d = FakeDriver(frame=f)
    assert {e.key: e for e in hs.extras(d, f, TZ)}["left_sensor_state"].state == "code 42"


def test_firmware_falls_back_to_the_frame():
    d = FakeDriver(caps={Cap.ZONE_TEMP}, frame=frame(fw_version="hub-fw"))
    assert {e.key: e for e in hs.extras(d, d.frame, TZ)}["firmware"].state == "fw-1"


# ---------- T-3: ids are fixed and unique ----------
async def test_fixed_ids_are_pinned_and_unique_with_a_person_named_hub(tmp_path):
    assert list(hs.FIXED_KEYS) == PINNED_FIXED
    for key in PINNED_FIXED:
        dom = FIXED_DOMAINS.get(key, "sensor")
        assert hs.unique_id(key) == f"embertide_hub_{key}"
        assert hs.entity_id(dom, key) == f"{dom}.embertide_hub_{key}"
        assert hs.config_topic(PREFIX, dom, key) == f"homeassistant/{dom}/embertide_hub_{key}/config"
        assert hs.state_topic(key) == f"embertide/bed/hub/{key}"
    n = await sim_night(tmp_path)
    n.p1.name = "Hub"
    b = HaBridge(n.c, "mqtt://x")
    assert b.oid(n.p1) == "embertide_hub"
    basic = b.discovery()
    extra = list(cat(n).values())
    # (Basic on its own has one clash with this household's default names, the bed's right_guest and the person
    # "Right"'s guest sensor; that predates the extras and is not theirs to fix. The extras add none.)
    for field in ("unique_id", "default_entity_id"):
        mine = [e.config[field] for e in extra]
        assert len(mine) == len(set(mine)), field
        assert not set(mine) & {c[field] for _, c in basic}, field
    topics = [e.config_topic for e in extra] + [e.state_topic for e in extra]
    assert len(topics) == len(set(topics))
    assert not set(topics) & ({t for t, _ in basic} | set(b.states(n.c.snapshot())))
    # a Basic topic of the person "Hub" looks like an extra's: only the catalogue's own list says what is an extra
    assert f"{PREFIX}/sensor/embertide_hub_phase/config" in {t for t, _ in basic}
    assert "phase" not in cat(n)


def test_driver_text_cannot_add_topic_levels_or_unbounded_entities():
    raw = {f"k{i}": i for i in range(20)} | {"a/b/#": 1, "+": 2, "x" * 80: 3, "A B": 4, "a_b": 5}
    d = FakeDriver(frame=frame(water_raw=raw, fan_rpm={f"s{i}": 1000 + i for i in range(9)} | {"#": 1}))
    ex = hs.extras(d, d.frame, TZ)
    water = [e for e in ex if e.key.startswith("water_") and e.key != "water_problem"]
    fans = [e for e in ex if e.key.startswith("fan_") and e.key.endswith("_rpm")]
    assert len(water) == hs.MAX_WATER and len(fans) == hs.MAX_FANS
    for e in ex:
        assert "/" not in e.key and "+" not in e.key and "#" not in e.key
        assert e.state_topic.count("/") == 3
        assert len(e.key) <= len("breathing_rate") + 1 + hs.KEY_PART_MAX + 6
    assert hs.key_part("x" * 80) == "x" * 32
    assert hs.key_part("a/b/#") == "a_b"
    assert hs.key_part("+") == ""


def test_a_water_key_named_problem_does_not_clash():
    d = FakeDriver(frame=frame(water_raw={"problem": 3, "level": 1}))
    ex = hs.extras(d, d.frame, TZ)
    assert [e.domain for e in ex if e.key == "water_problem"] == ["binary_sensor"]
    assert len({e.unique_id for e in ex}) == len(ex)


# ---------- T-4: capability gating ----------
async def test_reduced_capability_simulator(tmp_path):
    n = await sim_night(tmp_path)
    n.bed.capabilities = set(n.bed.capabilities) - {Cap.HUB_HEALTH, Cap.FAULTS, Cap.WATER_STATUS}
    ex = cat(n)
    for gone in ("fan_left_rpm", "fan_right_rpm", "fan_power", "wifi_signal", "free_memory", "water_reservoir",
                 "water_problem", "status", "humidity", "last_restart", "last_command", "safety", "firmware_build",
                 "panel_firmware"):
        assert gone not in ex, gone
    for kept in ("left_temperature", "right_temperature", "left_heart_rate", "right_breathing_rate", "quiet_fan",
                 "light_brightness", "light_color", "online", "firmware", "system_state"):
        assert kept in ex, kept
    assert ex["problem"].state == "OFF"          # from BedFrame.fault, which the simulator reports


def test_per_side_rows_follow_the_driver_zones_and_caps():
    d = FakeDriver(caps={Cap.MEASURED_TEMP}, zones=["left"], frame=frame())
    keys = {e.key for e in hs.extras(d, d.frame, TZ)}
    assert "left_temperature" in keys and "right_temperature" not in keys
    assert "left_heart_rate" not in keys and "left_setpoint" not in keys


# ---------- T-5: "reported" ----------
async def test_never_reported_creates_nothing_and_missing_keeps_the_entity(tmp_path):
    n = await sim_night(tmp_path)
    ex = cat(n)
    assert "room_temperature" not in ex and "humidity" in ex
    announced = {e.config_topic for e in ex.values()}
    f = n.bed.latest()
    f.hub.humidity = None
    again = cat(n, announced)
    assert again["humidity"].state == "None"
    fresh = cat(n)                                # never announced and missing: no entity
    assert "humidity" not in fresh


def test_a_remembered_water_key_stays_after_a_restart():
    announced = {hs.config_topic(PREFIX, "sensor", "water_reservoir"), hs.config_topic(PREFIX, "sensor", "fan_left_rpm")}
    d = FakeDriver(frame=None)
    ex = {e.key: e for e in hs.extras(d, None, TZ, announced)}
    assert ex["water_reservoir"].state == "None" and ex["fan_left_rpm"].state == "None"
    other = {e.key for e in hs.extras(d, None, TZ, {hs.config_topic("other", "sensor", "water_x")})}
    assert "water_x" not in other                 # another prefix's record is not this one's


def test_a_water_key_that_appears_mid_run_is_added():
    d = FakeDriver(frame=frame(water_raw={"a": 1}))
    first = hs.extras(d, d.frame, TZ)
    d.frame.hub.water_raw = {"a": 1, "b": 2}
    second = {e.key for e in hs.extras(d, d.frame, TZ, {e.config_topic for e in first})}
    assert {"water_a", "water_b"} <= second


def test_empty_collections_and_empty_text_are_not_reported():
    d = FakeDriver(frame=frame(water_raw={}, fan_rpm={}, last_command="", fw_build="  "))
    keys = {e.key for e in hs.extras(d, d.frame, TZ)}
    assert not any(k.startswith("fan_") and k.endswith("_rpm") for k in keys)
    assert not any(k.startswith("water_") and k != "water_problem" for k in keys)
    assert "last_command" not in keys and "firmware_build" not in keys


# ---------- T-6: problem, status and water in the app's words ----------
async def test_fault_and_low_water_in_plain_words(tmp_path):
    n = await sim_night(tmp_path)
    n.bed.inject_fault("fan_stopped", "left")
    n.bed._tick()
    ex = cat(n)
    assert ex["problem"].state == "ON"
    assert ex["status"].state == "Fan isn't running"
    attrs = json.loads(ex["problem"].attributes)
    assert attrs == {"status": "Fan isn't running", "faults": [{"name": "Fan isn't running", "code": "fan_stopped", "side": "left"}]}
    n.bed.clear_faults()
    n.bed.low_water = True
    n.bed._tick()
    ex = cat(n)
    assert ex["problem"].state == "ON" and ex["water_problem"].state == "ON"
    assert ex["status"].state == "Check the water"
    assert ex["water_reservoir"].state == "0"
    n.bed.low_water = False
    n.bed._tick()
    ex = cat(n)
    assert ex["problem"].state == "OFF" and ex["water_problem"].state == "OFF"
    assert ex["status"].state == "All good"
    assert json.loads(ex["problem"].attributes) == {"status": "All good", "faults": []}


async def test_hub_hot_fails_the_safety_check(tmp_path):
    n = await sim_night(tmp_path)
    n.bed.inject_fault("hub_hot")
    n.bed._tick()
    ex = cat(n)
    assert ex["safety"].state == "ON" and ex["problem"].state == "ON"


# ---------- T-7: privacy ----------
async def test_network_name_and_address_never_appear(tmp_path):
    n = await sim_night(tmp_path)
    n.bed.inject_fault("water_flow", "right")
    n.bed._tick()
    b = HaBridge(n.c, "mqtt://x")
    blobs = []
    for t, c in b.discovery():
        blobs += [t, json.dumps(c)]
    for t, v in b.states(n.c.snapshot()).items():
        blobs += [t, v]
    for e in hs.extras(n.bed, n.bed.latest(), TZ, prefix=PREFIX, device=bed_device(n)):
        blobs += [e.config_topic, json.dumps(e.config), e.state_topic, e.state, e.attributes_topic or "", e.attributes or ""]
    text = "\n".join(blobs)
    assert NET_NAME not in text and NET_ADDR not in text
    assert NET_NAME.lower() not in text.lower()


@pytest.mark.parametrize("cmd", [f"WIFI SET {NET_NAME}", f"ping {NET_ADDR}", "join home NETWORK now"])
def test_a_last_command_repeating_the_network_is_withheld(cmd):
    d = FakeDriver(frame=frame(last_command=cmd, wifi_name=NET_NAME, wifi_address=NET_ADDR))
    assert "last_command" not in {e.key for e in hs.extras(d, d.frame, TZ)}     # withheld: never created
    announced = {hs.config_topic(PREFIX, "sensor", "last_command")}
    assert {e.key: e for e in hs.extras(d, d.frame, TZ, announced)}["last_command"].state == "None"


def test_an_empty_network_name_does_not_withhold_everything():
    d = FakeDriver(frame=frame(last_command="FAN QUIET ON", wifi_name="", wifi_address=None))
    assert {e.key: e for e in hs.extras(d, d.frame, TZ)}["last_command"].state == "FAN QUIET ON"


# ---------- T-8: offline means unknown ----------
async def test_offline_hub_reads_unknown(tmp_path):
    n = await sim_night(tmp_path)
    announced = {e.config_topic for e in cat(n).values()}
    n.bed.restart_now()                           # the simulator goes quiet: online is false, old values remain
    f = n.bed.latest()
    assert f.online is False and f.hub.fan_rpm
    ex = cat(n, announced)
    assert set(ex) == {hs.parse_config_topic(t)[2] for t in announced}
    for key, e in ex.items():
        assert e.state == ("OFF" if key == "online" else "None"), key
    assert json.loads(ex["problem"].attributes) == {"status": None, "faults": []}


def test_offline_never_creates_a_reported_entity():
    f = frame(humidity=40.0, water_raw={"reservoir": 1}, fan_rpm={"left": 1})
    f.online = False
    d = FakeDriver(frame=f)
    keys = {e.key for e in hs.extras(d, f, TZ)}
    assert "humidity" not in keys and "water_reservoir" not in keys and "fan_left_rpm" not in keys
    assert "left_temperature" in keys and "online" in keys and "problem" in keys


def test_no_frame_at_all():
    d = FakeDriver(frame=None)
    ex = {e.key: e for e in hs.extras(d, None, TZ)}
    assert ex["online"].state == "OFF"
    assert all(e.state == "None" for k, e in ex.items() if k != "online")
    assert "humidity" not in ex


# ---------- helpers the bridge uses ----------
def test_restart_time_is_stable_within_the_jitter():
    f = frame(uptime_s=100)
    t0 = hs.restart_time(f)
    assert t0 == f.ts - 100
    f2 = frame(uptime_s=100)
    f2.ts += 3600
    f2.hub.uptime_s = 3700 - 30                    # computed start moved by 30 s: keep the old one
    assert hs.stable_restart(t0, f2) == t0
    f2.hub.uptime_s = 5                            # a real restart
    assert hs.stable_restart(t0, f2) == f2.ts - 5
    off = frame()
    off.online = False
    assert hs.stable_restart(t0, off) == t0        # kept while offline
    assert hs.stable_restart(None, None) is None


def test_state_topics_for_a_config_topic():
    t = hs.config_topic(PREFIX, "sensor", "left_heart_rate")
    assert hs.state_topics_for(t) == ["embertide/bed/hub/left_heart_rate", "embertide/bed/hub/left_heart_rate/attributes"]
    assert hs.state_topics_for("homeassistant/sensor/embertide_left_phase/config") == []
    assert hs.parse_config_topic("homeassistant/button/embertide_hub_x/config") is None
