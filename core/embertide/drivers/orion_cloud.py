"""Orion topper through Orion's cloud API with a personal API key (app.orionsleep.com/api-keys).

The easy path for most people: no DNS changes. Needs internet. Routes and shapes follow the community-documented
contract (github.com/borski/orion-sleep-api). The API rejects requests without a User-Agent.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time

import httpx

from . import profiles
from .base import BedFrame, Cap, CommandError, HubHealth, SensorFrame, ZoneFrame
from .orion_mqtt import clean_version, fault_for

log = logging.getLogger(__name__)
API = "https://api1.orionbed.com"
UA = "okhttp/4.12.0 embertide"
MAX_FAULTS = 32      # at most this many fault codes are read from one response


def _get(d, *path):
    """The value at `path`, or None when a level is missing or is not an object."""
    v = d
    for k in path:
        if not isinstance(v, dict):
            return None
        v = v.get(k)
    return v


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _txt(v, n=64):
    v = v.strip() if isinstance(v, str) else None
    return v[:n] if v else None


def _yes_no(v):
    return v if isinstance(v, bool) else None


def _objects(v):
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _firmware(live: dict) -> str | None:
    """The control unit's firmware: the top-level `firmware.version` when present, else `status.firmware.cb`."""
    return _txt(_get(live, "firmware", "version")) or _txt(_get(live, "status", "firmware", "cb"))


def _cloud_hub(live: dict) -> HubHealth:
    """The control unit's health from one live response. The network name, address and hardware address are never read."""
    t = HubHealth()
    t.fw_version = _firmware(live)
    t.fw_panel = _txt(_get(live, "status", "firmware", "ib"))
    rssi = _num(_get(live, "status", "network", "rssi"))
    t.wifi_dbm = int(rssi) if rssi is not None and rssi < 0 else None
    up = _num(_get(live, "status", "network", "uptime"))
    t.uptime_s = int(up) if up is not None and up >= 0 else None
    error = _get(live, "status", "safety", "error")
    t.safety_ok = (not error) if isinstance(error, bool) else None
    codes = _get(live, "status", "safety", "error_codes")
    if isinstance(codes, list):
        for c in codes[:MAX_FAULTS]:
            if isinstance(c, str) and c.strip():
                t.faults.append(fault_for(c.strip().upper()))
    t.filling = _yes_no(live.get("is_in_water_fill_mode"))
    fill = _txt(live.get("water_fill"))
    t.fill_state = fill if fill and fill.lower() != "unknown" else None
    t.update_available = _yes_no(_get(live, "status", "pending_update", "is_available"))
    t.updating = _yes_no(_get(live, "status", "firmware_update", "in_progress"))
    return t


def parse_live(live: dict, zone_map: dict[str, str], ts: float, serial: str | None = None) -> BedFrame:
    """One bed frame from the `response` object of the live call. Pure: no I/O, no clock. A value of the wrong type
    reads as not reported; nothing raises. `serial` is used only to keep it out of the model name."""
    if not isinstance(live, dict):
        live = {}
    inv = {v: k for k, v in zone_map.items()}
    zones = {"left": ZoneFrame(), "right": ZoneFrame()}
    for z in _objects(live.get("zones")):
        side = inv.get(z.get("id"))
        if side:
            zones[side].on, zones[side].setpoint_c = z.get("on"), z.get("temp")
    st = live.get("status")
    st = st if isinstance(st, dict) else {}
    for z in _objects(st.get("zones")):
        side = inv.get(z.get("id"))
        if side:
            zones[side].measured_c = z.get("temp")
            zones[side].thermal_state = _txt(z.get("thermal_state"), 32)
    for side, key in (("left", "sensor1"), ("right", "sensor2")):
        s = _get(st, "sensors", key)
        s = s if isinstance(s, dict) else {}
        hr, br = s.get("heart_rate"), s.get("breath_rate")
        zones[side].sensor = SensorFrame(status=s.get("status") if isinstance(s.get("status"), int) else None,
                                         hr=hr if isinstance(hr, int) and 0 < hr < 255 else None,
                                         br=br if isinstance(br, int) and 0 < br < 255 else None,
                                         clock=(ts,),
                                         working=_yes_no(s.get("is_working")),
                                         fw_version=clean_version(s.get("firmware_version")),
                                         hw_version=clean_version(s.get("hardware_version")))
    model = _txt(live.get("model"))
    if model and serial and serial.lower() in model.lower():
        model = None
    return BedFrame(ts=ts, zones=zones, firmware=_firmware(live),
                    quiet_mode=live.get("quiet_mode"), brightness=live.get("led_brightness"),
                    online=st.get("online") is not False, hub=_cloud_hub(live), model=model)


class OrionCloud:
    id = "orion-cloud"
    name = "Orion topper (cloud API key)"
    capabilities = {Cap.ZONE_TEMP, Cap.ZONE_POWER, Cap.MEASURED_TEMP, Cap.OCCUPANCY, Cap.BIO_HR, Cap.BIO_BR, Cap.LED_DIM, Cap.FAN_QUIET,
                    Cap.HUB_HEALTH, Cap.FAULTS}
    zones = ["left", "right"]
    profile = profiles.ORION      # care tasks and the hub light guide (drivers/profiles.py)

    def __init__(self, api_key: str, serial: str | None = None, zone_map: dict[str, str] | None = None, poll_s: float = 10) -> None:
        self.serial = serial
        self.zone_map = zone_map or {"left": "zone_a", "right": "zone_b"}
        self.poll_s = poll_s
        self._http = httpx.AsyncClient(base_url=API, timeout=20, headers={"Authorization": f"Bearer {api_key}", "User-Agent": UA})
        self._frame: BedFrame | None = None
        self._task: asyncio.Task | None = None
        self._state = "starting"
        self._versions: dict[tuple[str, str], str] = {}          # (side, field) -> last good pad-sensor version

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        await self._http.aclose()

    def latest(self) -> BedFrame | None:
        return self._frame

    def status(self) -> dict:
        f = self._frame
        return {"driver": self.id, "name": self.name, "online": bool(f and time.time() - f.ts < 3 * self.poll_s + 10),
                "detail": self._state, "serial": self.serial, "age_s": round(time.time() - f.ts, 1) if f else None}

    async def _run(self) -> None:
        while True:
            try:
                if not self.serial:
                    r = await self._http.get("/v1/devices")
                    r.raise_for_status()
                    devices = r.json().get("response", {}).get("devices", [])
                    if not devices:
                        raise CommandError("no devices on this account")
                    self.serial = devices[0]["serial_number"]
                r = await self._http.get(f"/v1/devices/{self.serial}/live")
                r.raise_for_status()
                self._frame = self._parse(r.json().get("response", {}))
                self._state = "connected"
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                self._state = f"error ({type(e).__name__})"
                log.warning("orion cloud: %s", e)
            await asyncio.sleep(self.poll_s)

    def _parse(self, live: dict) -> BedFrame:
        frame = parse_live(live, self.zone_map, time.time(), self.serial)
        prev = self._frame
        if prev is not None and not isinstance(live.get("status") if isinstance(live, dict) else None, dict):
            # A response without a status object (a set_zone reply may carry only zones): keep the hub's state from
            # the previous frame instead of blanking it until the next poll.
            frame.hub, frame.model, frame.online = prev.hub, prev.model, prev.online
            for side, z in frame.zones.items():
                p = prev.zones.get(side)
                if p is not None:
                    z.thermal_state = p.thermal_state
                    z.sensor.working = p.sensor.working
                    z.sensor.fw_version, z.sensor.hw_version = p.sensor.fw_version, p.sensor.hw_version
        for side, z in frame.zones.items():      # the version hold: a garbled string keeps the last good one
            for name in ("fw_version", "hw_version"):
                v = getattr(z.sensor, name)
                if v is not None:
                    self._versions[(side, name)] = v
                elif (side, name) in self._versions:
                    setattr(z.sensor, name, self._versions[(side, name)])
        return frame

    async def set_zone(self, zone: str, *, on: bool, temp_c: float | None = None) -> bool:
        if not self.serial:
            raise CommandError("bed not found yet")
        body: dict = {"id": self.zone_map[zone], "on": on}
        if on and temp_c is not None:
            body["temp"] = round(min(45.0, max(10.0, temp_c)), 2)
        r = await self._http.put(f"/v1/devices/{self.serial}/live", json={"zones": [body]})
        r.raise_for_status()
        self._frame = self._parse(r.json().get("response", {}))
        return True

    async def command(self, raw: str) -> str:
        raise CommandError("the cloud driver has no raw console; use the local MQTT driver")
