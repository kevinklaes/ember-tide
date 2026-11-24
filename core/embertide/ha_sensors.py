"""The extra Home Assistant entities: everything the hub reports, for the "All sensors" level.

The bridge (`ha_bridge.py`) publishes each person's side and the bed's care jobs at every level ("Basic"). At level
`all` it also publishes the entities this module lists, built from the driver's latest frame. This module is plain
functions: no network, no store, no logging. The bridge imports it; it imports nothing from the bridge.

Names (fixed forever; only the display names may change):

  entity id      <domain>.embertide_hub_<key>         (domain: sensor or binary_sensor)
  unique_id      embertide_hub_<key>
  config topic   <prefix>/<domain>/embertide_hub_<key>/config
  state topic    embertide/bed/hub/<key>

Privacy: the hub's network name and address are never part of an entity, a state, an attribute or a topic. They
are read only to withhold a "last command" that repeats them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, tzinfo
from typing import Any, Callable, Iterable

from . import hub as hublib
from .drivers.base import BedFrame, Cap, HubHealth, ZoneFrame
from .engine.presence import STATUS_TEXT

# ---------- the level ----------
LEVELS = ("basic", "all")
DEFAULT_LEVEL = "basic"

# ---------- publishing ----------
MIN_INTERVAL_S = 30.0       # a rate-limited reading is published at most once per this many seconds
RESTART_JITTER_S = 60.0     # how far the computed restart time must move before it is published again

# ---------- names and limits ----------
BASE = "embertide"
STATE_BASE = f"{BASE}/bed/hub"
ID_PREFIX = "embertide_hub_"
AVAILABILITY_TOPIC = f"{BASE}/status"
KEY_PART_MAX = 32           # a part of a key taken from the driver (zone, fan side, water key) is cut to this
MAX_WATER = 8               # water readings: at most this many entities
MAX_FANS = 4                # fan speeds: at most this many entities
TEXT_MAX = 250              # text states are cut to this many characters (HA's limit is 255)
DOMAINS = ("sensor", "binary_sensor")
MISSING = "None"            # the state text HA shows as unknown (Basic uses the same)


def resolve_level(saved: dict | None, default: str | None) -> str:
    """The level to run at: the owner's saved choice, else the environment's default, else Basic."""
    choice = (saved or {}).get("sensors") if isinstance(saved, dict) else None
    if isinstance(choice, str) and choice in LEVELS:
        return choice
    if isinstance(default, str) and default in LEVELS:
        return default
    return DEFAULT_LEVEL


# ---------- keys and topics ----------
def key_part(raw: Any) -> str:
    """A driver-supplied part of a key, reduced to lower-case letters, digits and `_` (the bridge's slug rule) and cut
    to 32 characters. Empty when nothing usable is left: such a reading gets no entity."""
    s = re.sub(r"[^a-z0-9]+", "_", str(raw).lower()).strip("_")
    return s[:KEY_PART_MAX].strip("_")


def unique_id(key: str) -> str:
    return f"{ID_PREFIX}{key}"


def entity_id(domain: str, key: str) -> str:
    return f"{domain}.{ID_PREFIX}{key}"


def config_topic(prefix: str, domain: str, key: str) -> str:
    return f"{prefix}/{domain}/{ID_PREFIX}{key}/config"


def state_topic(key: str) -> str:
    return f"{STATE_BASE}/{key}"


def attributes_topic(key: str) -> str:
    return f"{STATE_BASE}/{key}/attributes"


_CONFIG_RE = re.compile(r"^(?P<prefix>.+)/(?P<domain>sensor|binary_sensor)/" + ID_PREFIX + r"(?P<key>[a-z0-9_]+)/config$")


def parse_config_topic(topic: str) -> tuple[str, str, str] | None:
    """(prefix, domain, key) of a topic KNOWN to be an extra's config topic (one from `extras()` or from the bridge's
    record of announced extras), else None. It cannot tell an extra from a Basic entity by itself: a person named
    "Hub" has Basic topics such as `<prefix>/sensor/embertide_hub_phase/config` that look the same. To know whether
    a topic is an extra, ask `extras()` or the record, never the topic's text."""
    m = _CONFIG_RE.match(topic)
    if not m or m["key"] != m["key"].strip("_"):
        return None
    return m["prefix"], m["domain"], m["key"]


def state_topics_for(config: str) -> list[str]:
    """The state and attributes topics belonging to an extra's config topic from the record (to clear them when the
    extra is removed). Clearing a topic that was never used is harmless."""
    p = parse_config_topic(config)
    return [] if p is None else [state_topic(p[2]), attributes_topic(p[2])]


# ---------- values ----------
def number_text(v: Any) -> str:
    """Whole numbers as integers, other numbers rounded to one decimal; a missing reading is "None"."""
    if v is None or isinstance(v, bool):
        return MISSING
    try:
        x = round(float(v), 1)
    except (TypeError, ValueError):
        return MISSING
    if x != x or x in (float("inf"), float("-inf")):
        return MISSING
    return str(int(x)) if x == int(x) else str(x)


def text_value(v: Any) -> str:
    if v is None:
        return MISSING
    s = str(v).strip()
    return s[:TEXT_MAX] if s else MISSING


def binary_value(v: bool | None) -> str:
    return MISSING if v is None else ("ON" if v else "OFF")


def color_value(rgb: Any) -> str:
    try:
        r, g, b = (max(0, min(255, int(c))) for c in rgb)
    except (TypeError, ValueError):
        return MISSING
    return f"#{r:02x}{g:02x}{b:02x}"


def timestamp_value(ts: float | None, tz: tzinfo) -> str:
    if ts is None:
        return MISSING
    return datetime.fromtimestamp(int(ts), tz).isoformat()


def restart_time(frame: BedFrame | None) -> float | None:
    """When the hub last started: the frame's time minus its uptime. None while unknown or offline."""
    h = frame.hub if frame is not None else None
    if frame is None or not frame.online or h is None or h.uptime_s is None:
        return None
    return float(frame.ts) - float(h.uptime_s)


def stable_restart(previous: float | None, frame: BedFrame | None) -> float | None:
    """The restart time to report: the remembered one unless the newly computed one moved more than
    RESTART_JITTER_S (a real restart). While nothing new is known the remembered one is kept."""
    now = restart_time(frame)
    if now is None:
        return previous
    if previous is None or abs(now - previous) > RESTART_JITTER_S:
        return now
    return previous


def last_command_value(h: HubHealth | None) -> str:
    """The hub's "last command", withheld if it ever repeats the network name or address."""
    if h is None or h.last_command is None:
        return MISSING
    low = str(h.last_command).lower()
    for secret in (h.wifi_name, h.wifi_address):
        if secret and str(secret).strip() and str(secret).strip().lower() in low:
            return MISSING
    return text_value(h.last_command)


# ---------- the catalogue ----------
@dataclass(frozen=True)
class Extra:
    """One extra entity as it exists right now: its config and its current state."""
    key: str
    domain: str
    name: str
    config_topic: str
    config: dict
    state_topic: str
    state: str
    limited: bool                          # held to one publish per MIN_INTERVAL_S
    attributes_topic: str | None = None
    attributes: str | None = None          # a JSON payload (only "problem" has one)

    @property
    def entity_id(self) -> str:
        return entity_id(self.domain, self.key)

    @property
    def unique_id(self) -> str:
        return unique_id(self.key)


@dataclass
class _Ctx:
    caps: set
    frame: BedFrame | None
    tz: tzinfo
    restart_ts: float | None

    @property
    def online(self) -> bool:
        return self.frame is not None and bool(self.frame.online)

    @property
    def hub(self) -> HubHealth | None:
        return self.frame.hub if self.frame is not None else None

    def h(self, name: str) -> Any:
        h = self.hub
        return getattr(h, name) if h is not None else None


# kinds of state: how a raw reading becomes text
NUMBER, TEXT, BINARY, TIMESTAMP, COLOR = "number", "text", "binary", "timestamp", "color"


@dataclass(frozen=True)
class Spec:
    """One row of the entity table. `read` returns the raw reading (or, for TEXT rows, the finished text)."""
    key: str
    domain: str
    name: str
    kind: str
    read: Callable[[_Ctx], Any]
    needs: Cap | None = None
    reported: bool = False
    diag: bool = False
    limited: bool = False
    form: dict = field(default_factory=dict)
    source: str = ""                         # the field it reads (for the docs and the tests)


def _problem(c: _Ctx) -> bool | None:
    if Cap.HUB_HEALTH in c.caps:
        return hublib.needs_attention(c.hub) if c.hub is not None else None
    return c.frame.fault if c.frame is not None else None


def _firmware(c: _Ctx) -> Any:
    fw = c.h("fw_version") if Cap.HUB_HEALTH in c.caps else None
    return fw or (c.frame.firmware if c.frame is not None else None)


def _not(v: bool | None) -> bool | None:
    return None if v is None else not v


TEMP = {"device_class": "temperature", "unit_of_measurement": "°C", "state_class": "measurement"}
MEASURE = {"state_class": "measurement"}

# The fixed rows, in the table's order. Per-side, fan and water rows are expanded below.
FIXED: tuple[Spec, ...] = (
    Spec("problem", "binary_sensor", "Hub problem", BINARY, _problem, needs=Cap.HUB_HEALTH,
         form={"device_class": "problem"}, source="HubHealth.faults/water_ok/safety_ok; BedFrame.fault"),
    Spec("status", "sensor", "Hub status", TEXT, lambda c: text_value(hublib.status_line(c.hub)), needs=Cap.HUB_HEALTH,
         diag=True, source="hub.status_line"),
    Spec("water_problem", "binary_sensor", "Water problem", BINARY, lambda c: _not(c.h("water_ok")),
         needs=Cap.WATER_STATUS, reported=True, form={"device_class": "problem"}, source="HubHealth.water_ok"),
    Spec("safety", "binary_sensor", "Hub safety check", BINARY, lambda c: _not(c.h("safety_ok")),
         needs=Cap.HUB_HEALTH, reported=True, diag=True, form={"device_class": "safety"}, source="HubHealth.safety_ok"),
    Spec("fan_power", "sensor", "Fan power", NUMBER, lambda c: c.h("fan_pwm"), needs=Cap.HUB_HEALTH, reported=True,
         diag=True, limited=True, form={"unit_of_measurement": "%", **MEASURE}, source="HubHealth.fan_pwm"),
    Spec("quiet_fan", "binary_sensor", "Quiet fan", BINARY, lambda c: c.frame.quiet_mode if c.frame else None,
         needs=Cap.FAN_QUIET, reported=True, diag=True, source="BedFrame.quiet_mode"),
    Spec("humidity", "sensor", "Room humidity", NUMBER, lambda c: c.h("humidity"), needs=Cap.HUB_HEALTH, reported=True,
         limited=True, form={"device_class": "humidity", "unit_of_measurement": "%", **MEASURE}, source="HubHealth.humidity"),
    Spec("room_temperature", "sensor", "Room temperature", NUMBER, lambda c: c.h("room_c"), needs=Cap.HUB_HEALTH,
         reported=True, limited=True, form=dict(TEMP), source="HubHealth.room_c"),
    Spec("wifi_signal", "sensor", "Hub Wi-Fi signal", NUMBER, lambda c: c.h("wifi_dbm"), needs=Cap.HUB_HEALTH,
         reported=True, diag=True, limited=True,
         form={"device_class": "signal_strength", "unit_of_measurement": "dBm", **MEASURE}, source="HubHealth.wifi_dbm"),
    Spec("last_restart", "sensor", "Hub last restart", TIMESTAMP, lambda c: c.restart_ts, needs=Cap.HUB_HEALTH,
         reported=True, diag=True, form={"device_class": "timestamp"}, source="HubHealth.uptime_s"),
    Spec("free_memory", "sensor", "Hub free memory", NUMBER, lambda c: c.h("free_memory_kb"), needs=Cap.HUB_HEALTH,
         reported=True, diag=True, limited=True,
         form={"device_class": "data_size", "unit_of_measurement": "kB", **MEASURE}, source="HubHealth.free_memory_kb"),
    Spec("firmware", "sensor", "Hub firmware", TEXT, lambda c: text_value(_firmware(c)), reported=True, diag=True,
         source="HubHealth.fw_version, else BedFrame.firmware"),
    Spec("firmware_build", "sensor", "Hub firmware build", TEXT, lambda c: text_value(c.h("fw_build")),
         needs=Cap.HUB_HEALTH, reported=True, diag=True, source="HubHealth.fw_build"),
    Spec("panel_firmware", "sensor", "Light panel firmware", TEXT, lambda c: text_value(c.h("fw_panel")),
         needs=Cap.HUB_HEALTH, reported=True, diag=True, source="HubHealth.fw_panel"),
    Spec("last_command", "sensor", "Hub last command", TEXT, lambda c: last_command_value(c.hub), needs=Cap.HUB_HEALTH,
         reported=True, diag=True, source="HubHealth.last_command"),
    Spec("online", "binary_sensor", "Hub online", BINARY, lambda c: c.online, diag=True,
         form={"device_class": "connectivity"}, source="BedFrame.online"),
    Spec("system_state", "sensor", "Hub system state", TEXT,
         lambda c: text_value(c.frame.system_state if c.frame else None), reported=True, diag=True,
         source="BedFrame.system_state"),
    Spec("light_brightness", "sensor", "Hub light brightness", NUMBER, lambda c: c.frame.brightness if c.frame else None,
         needs=Cap.LED_DIM, reported=True, diag=True, limited=True, form={"unit_of_measurement": "%", **MEASURE},
         source="BedFrame.brightness"),
    Spec("light_color", "sensor", "Hub light colour", COLOR, lambda c: c.frame.rgb if c.frame else None,
         needs=Cap.LED_RGB, reported=True, diag=True, source="BedFrame.rgb"),
)

FIXED_KEYS: tuple[str, ...] = tuple(s.key for s in FIXED)


def _zone(c: _Ctx, zone: str) -> ZoneFrame | None:
    return c.frame.zones.get(zone) if c.frame is not None else None


def _sensor_text(code: Any) -> str:
    if code is None:
        return MISSING
    return text_value(STATUS_TEXT.get(code, f"code {code}"))


def zone_specs(zone: str) -> list[Spec]:
    """The per-side rows for one zone the driver names. They need a capability but are not "reported"."""
    k = key_part(zone)
    if not k:
        return []
    side = str(zone).strip()[:KEY_PART_MAX].title() or k.title()

    def zf(attr: str):
        return lambda c: getattr(_zone(c, zone), attr) if _zone(c, zone) is not None else None

    def sf(attr: str):
        return lambda c: getattr(_zone(c, zone).sensor, attr) if _zone(c, zone) is not None else None

    return [
        Spec(f"{k}_temperature", "sensor", f"{side} pad temperature", NUMBER, zf("measured_c"), needs=Cap.MEASURED_TEMP,
             limited=True, form=dict(TEMP), source="ZoneFrame.measured_c"),
        Spec(f"{k}_setpoint", "sensor", f"{side} pad setpoint", NUMBER, zf("setpoint_c"), needs=Cap.ZONE_TEMP,
             limited=True, form=dict(TEMP), source="ZoneFrame.setpoint_c"),
        Spec(f"{k}_power", "binary_sensor", f"{side} pad power", BINARY, zf("on"), needs=Cap.ZONE_POWER,
             form={"device_class": "power"}, source="ZoneFrame.on"),
        Spec(f"{k}_sensor_state", "sensor", f"{side} pad sensor", TEXT, lambda c: _sensor_text(sf("status")(c)),
             needs=Cap.OCCUPANCY, diag=True, source="SensorFrame.status"),
        Spec(f"{k}_heart_rate", "sensor", f"{side} pad heart rate", NUMBER, sf("hr"), needs=Cap.BIO_HR, limited=True,
             form={"unit_of_measurement": "bpm", **MEASURE}, source="SensorFrame.hr"),
        Spec(f"{k}_breathing_rate", "sensor", f"{side} pad breathing rate", NUMBER, sf("br"), needs=Cap.BIO_BR,
             limited=True, form={"unit_of_measurement": "br/min", **MEASURE}, source="SensorFrame.br"),
    ]


def _keyed(raw: Iterable[Any], announced: Iterable[str], cap: int) -> dict[str, Any]:
    """Reduced key -> raw key (None for a key only remembered as announced). Keys already announced keep their place;
    new ones are added in sorted order up to `cap`. When two raw keys reduce to the same key the first wins."""
    reduced: dict[str, Any] = {}
    for r in sorted(raw, key=str):
        k = key_part(r)
        if k and k not in reduced:
            reduced[k] = r
    out: dict[str, Any] = {}
    for k in sorted(set(announced)):
        if len(out) < cap:
            out[k] = reduced.get(k)
    for k, r in reduced.items():
        if len(out) >= cap:
            break
        if k not in out:
            out[k] = r
    return out


def _announced_family(announced: Iterable[str], prefix: str, start: str, end: str = "") -> list[str]:
    out = []
    for t in announced:
        p = parse_config_topic(t)
        if p and p[0] == prefix and p[1] == "sensor" and p[2].startswith(start) and p[2].endswith(end):
            mid = p[2][len(start):len(p[2]) - len(end) if end else None]
            if mid and mid == key_part(mid):
                out.append(mid)
    return out


def specs(driver, frame: BedFrame | None, announced: Iterable[str] = (), prefix: str = "homeassistant") -> list[Spec]:
    """Every row that could apply to this driver: the fixed rows, per-side rows, and one row per fan side and water
    key that was reported (now, or before: remembered through `announced`). Capability is not checked here."""
    announced = list(announced)
    h = frame.hub if frame is not None and frame.online else None
    out = list(FIXED)
    # fans: one per side reported (now, while online, or announced before)
    fan_raw = list((h.fan_rpm or {}).keys()) if h is not None else []
    fans = _keyed(fan_raw, _announced_family(announced, prefix, "fan_", "_rpm"), MAX_FANS)
    for k, r in fans.items():
        out.append(Spec(f"fan_{k}_rpm", "sensor", f"Fan speed ({k.replace('_', ' ')})", NUMBER,
                        (lambda r: lambda c: (c.h("fan_rpm") or {}).get(r) if r is not None else None)(r),
                        needs=Cap.HUB_HEALTH, reported=True, diag=True, limited=True,
                        form={"unit_of_measurement": "rpm", **MEASURE}, source="HubHealth.fan_rpm"))
    water_raw = list((h.water_raw or {}).keys()) if h is not None else []
    water = _keyed(water_raw, _announced_family(announced, prefix, "water_"), MAX_WATER + 1)
    water.pop("problem", None)    # `water_problem` is its own row; a hub key named "problem" gets no entity
    for k, r in list(water.items())[:MAX_WATER]:
        out.append(Spec(f"water_{k}", "sensor", f"Water reading ({k.replace('_', ' ')})", NUMBER,
                        (lambda r: lambda c: (c.h("water_raw") or {}).get(r) if r is not None else None)(r),
                        needs=Cap.WATER_STATUS, reported=True, diag=True, limited=True, form=dict(MEASURE),
                        source="HubHealth.water_raw"))
    for z in getattr(driver, "zones", []) or []:
        out.extend(zone_specs(z))
    return out


def _state(spec: Spec, c: _Ctx) -> str:
    if spec.key != "online" and not c.online:
        return MISSING                          # offline means unknown: never the last frame's stale values
    v = spec.read(c)
    if spec.kind == NUMBER:
        return number_text(v)
    if spec.kind == BINARY:
        return binary_value(v)
    if spec.kind == TIMESTAMP:
        return timestamp_value(v, c.tz)
    if spec.kind == COLOR:
        return color_value(v) if v is not None else MISSING
    return v if isinstance(v, str) else text_value(v)


def _exists(spec: Spec, c: _Ctx, state: str, topic: str, announced: set[str]) -> bool:
    if spec.key == "problem":
        if Cap.HUB_HEALTH in c.caps:
            return True
        return topic in announced or (c.online and c.frame.fault is not None)
    if spec.needs is not None and spec.needs not in c.caps:
        return False
    if not spec.reported:
        return True
    return topic in announced or (c.online and state != MISSING)


def _config(spec: Spec, topic_key: str, device: dict | None, attrs: str | None) -> dict:
    cfg: dict = {"availability_topic": AVAILABILITY_TOPIC}
    if device is not None:
        cfg["device"] = device
    cfg.update({"name": spec.name, "unique_id": unique_id(topic_key),
                "default_entity_id": entity_id(spec.domain, topic_key), "state_topic": state_topic(topic_key)})
    cfg.update(spec.form)
    if spec.domain == "binary_sensor":
        cfg.update({"payload_on": "ON", "payload_off": "OFF"})
    if spec.diag:
        cfg["entity_category"] = "diagnostic"
    if attrs is not None:
        cfg["json_attributes_topic"] = attrs
    return cfg


def problem_attributes(c: _Ctx) -> str:
    """The status line and faults in the app's words, from `hub.summary()` (never `hub.detail()`)."""
    s = hublib.summary(c.hub) if c.online and Cap.HUB_HEALTH in c.caps else None
    if s is None:
        return json.dumps({"status": None, "faults": []})
    faults = [{"name": text_value(f["name"]), "code": text_value(f["code"]), "side": f["zone"]} for f in s["faults"]]
    return json.dumps({"status": text_value(s["line"]), "faults": faults})


def extras(driver, frame: BedFrame | None, tz: tzinfo, announced: Iterable[str] = (), *,
           prefix: str = "homeassistant", device: dict | None = None, restart_ts: float | None = None) -> list[Extra]:
    """Every extra entity that exists right now, with its config and its current state.

    `announced` is the set of extra config topics already announced (the bridge's record); a "reported" entity in it
    stays even while its reading is missing. `restart_ts` is the restart time the bridge has settled on (see
    `stable_restart`); left out, it is computed from the frame. `device` is the Bed device block."""
    announced = set(announced)
    caps = set(getattr(driver, "capabilities", set()) or set())
    if restart_ts is None:
        restart_ts = restart_time(frame)
    c = _Ctx(caps=caps, frame=frame, tz=tz, restart_ts=restart_ts)
    out: list[Extra] = []
    seen: set[str] = set()
    for spec in specs(driver, frame, announced, prefix):
        if spec.key in seen:
            continue
        topic = config_topic(prefix, spec.domain, spec.key)
        state = _state(spec, c)
        if not _exists(spec, c, state, topic, announced):
            continue
        seen.add(spec.key)
        attrs_topic = attributes_topic(spec.key) if spec.key == "problem" else None
        out.append(Extra(
            key=spec.key, domain=spec.domain, name=spec.name, config_topic=topic,
            config=_config(spec, spec.key, device, attrs_topic), state_topic=state_topic(spec.key), state=state,
            limited=spec.limited, attributes_topic=attrs_topic,
            attributes=problem_attributes(c) if attrs_topic else None))
    return out
