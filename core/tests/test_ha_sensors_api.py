"""The Basic / All sensors setting: the saved choice, the route, ET_HA_SENSORS and the demo. Everything here is
synthetic (the simulator, made-up broker names)."""

import logging

import pytest
from fastapi.testclient import TestClient

from embertide.app import create_app
from embertide.config import Config
from embertide.ha_sensors import resolve_level

H = {"X-Embertide": "1"}
PW = "correct horse battery"


def make(tmp_path, auth=False, **over):
    cfg = Config()
    cfg.data_dir, cfg.tz, cfg.bed, cfg.web_dir, cfg.llm_url, cfg.auth, cfg.ha_mqtt_url = tmp_path, "America/New_York", "sim", tmp_path / "noweb", None, auth, None
    for k, v in over.items():
        setattr(cfg, k, v)
    return TestClient(create_app(cfg))


def saved(c) -> dict:
    return c.app.state.ha.c.store.get("ha_bridge", {}) or {}


def test_default_is_basic_and_choosing_all_saves_and_applies(tmp_path):
    with make(tmp_path) as c:
        assert c.get("/api/integrations/ha").json()["sensors"] == "basic"
        basic = c.get("/api/integrations/ha/entities").json()
        r = c.put("/api/integrations/ha/sensors", json={"level": "all"}, headers=H)
        assert r.status_code == 200, r.text
        assert r.json()["sensors"] == "all"
        assert saved(c)["sensors"] == "all"
        assert c.app.state.ha.level == "all"
        assert c.get("/api/integrations/ha").json()["sensors"] == "all"
        ids = {e["entity_id"] for e in c.get("/api/integrations/ha/entities").json()}
        assert len(ids) > len(basic)
        assert "sensor.embertide_hub_fan_left_rpm" in ids
        # and back to Basic, with the bridge off (no broker): set_level still works
        assert c.put("/api/integrations/ha/sensors", json={"level": "basic"}, headers=H).json()["sensors"] == "basic"
        assert c.get("/api/integrations/ha/entities").json() == basic


def test_broker_save_keeps_the_level_and_level_save_keeps_the_broker(tmp_path):
    with make(tmp_path) as c:
        assert c.put("/api/integrations/ha/sensors", json={"level": "all"}, headers=H).status_code == 200
        r = c.put("/api/integrations/ha", json={"host": "broker.invalid", "port": 1884, "username": "ha-user",
                                               "password": "s3cret", "prefix": "hass"}, headers=H)
        assert r.status_code == 200, r.text
        assert saved(c)["sensors"] == "all" and c.app.state.ha.level == "all"
        before = c.get("/api/integrations/ha").json()
        rec = dict(saved(c))
        assert c.put("/api/integrations/ha/sensors", json={"level": "basic"}, headers=H).status_code == 200
        after = c.get("/api/integrations/ha").json()
        for k in ("host", "port", "username", "password_saved", "prefix"):
            assert after[k] == before[k], k
        assert after["host"] == "broker.invalid" and after["port"] == 1884 and after["username"] == "ha-user"
        assert after["password_saved"] is True and after["prefix"] == "hass"
        assert {k: v for k, v in saved(c).items() if k != "sensors"} == {k: v for k, v in rec.items() if k != "sensors"}
        assert saved(c)["sensors"] == "basic"
        # keep_password on a later broker save still finds the password, and the level stays
        assert c.put("/api/integrations/ha", json={"host": "broker.invalid", "port": 1884, "username": "ha-user",
                                                  "keep_password": True, "prefix": "hass"}, headers=H).status_code == 200
        assert "s3cret" in saved(c)["url"] and saved(c)["sensors"] == "basic"


def test_level_route_works_when_the_broker_comes_from_the_environment(tmp_path):
    with make(tmp_path, ha_mqtt_url="mqtt://127.0.0.1:9") as c:
        r = c.put("/api/integrations/ha", json={"host": "broker.invalid", "prefix": "homeassistant"}, headers=H)
        assert r.status_code == 409
        r = c.put("/api/integrations/ha/sensors", json={"level": "all"}, headers=H)
        assert r.status_code == 200, r.text
        assert r.json()["sensors"] == "all" and r.json()["from_env"] is True
        assert c.app.state.ha.level == "all" and saved(c)["sensors"] == "all"


@pytest.mark.parametrize("body", [{"level": "most"}, {"level": "ALL"}, {"level": 1}, {"level": None}, {}])
def test_an_unknown_level_gets_a_plain_message(tmp_path, body):
    with make(tmp_path) as c:
        r = c.put("/api/integrations/ha/sensors", json=body, headers=H)
        assert r.status_code == 422
        assert r.json() == {"detail": "Choose Basic or All sensors."}
        assert "sensors" not in saved(c) and c.app.state.ha.level == "basic"


def test_only_the_owner_can_choose(tmp_path):
    with make(tmp_path, auth=True) as owner:
        assert owner.post("/api/auth/setup", json={"username": "alex", "password": PW, "person": "p1"}).status_code == 200
        code = owner.post("/api/auth/invites", json={"person": "p2", "role": "sleeper"}, headers=H).json()["code"]
        sleeper = TestClient(owner.app)
        assert sleeper.post("/api/auth/accept", json={"code": code, "username": "sam", "password": PW}).status_code == 200
        r = sleeper.put("/api/integrations/ha/sensors", json={"level": "all"}, headers=H)
        assert r.status_code == 403 and r.json()["detail"] == "Only the owner can do that."
        assert owner.app.state.ha.level == "basic"
        assert owner.put("/api/integrations/ha/sensors", json={"level": "all"}, headers=H).status_code == 200


def test_environment_default_applies_until_the_owner_chooses(tmp_path):
    with make(tmp_path, ha_sensors="all") as c:
        assert c.app.state.ha.level == "all"
        assert c.get("/api/integrations/ha").json()["sensors"] == "all"
        assert c.put("/api/integrations/ha/sensors", json={"level": "basic"}, headers=H).status_code == 200
    with make(tmp_path, ha_sensors="all") as c:       # same data folder: the saved choice wins
        assert c.app.state.ha.level == "basic"
        assert c.get("/api/integrations/ha").json()["sensors"] == "basic"


def test_et_ha_sensors_is_read_trimmed_and_checked(monkeypatch, caplog):
    monkeypatch.delenv("ET_HA_SENSORS", raising=False)
    assert Config().ha_sensors == "basic"
    monkeypatch.setenv("ET_HA_SENSORS", "  All ")
    assert Config().ha_sensors == "all"
    monkeypatch.setenv("ET_HA_SENSORS", "everything")
    with caplog.at_level(logging.WARNING, logger="embertide.config"):
        assert Config().ha_sensors == "basic"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "ET_HA_SENSORS" in r.getMessage()]
    assert len(warnings) == 1


@pytest.mark.parametrize("saved_rec, default, want", [
    (None, None, "basic"), ({}, "basic", "basic"), ({}, "all", "all"), ({}, "bogus", "basic"),
    ({"sensors": "basic"}, "all", "basic"), ({"sensors": "all"}, "basic", "all"), ({"sensors": "all"}, None, "all"),
    ({"sensors": "most"}, "all", "all"), ({"sensors": "most"}, None, "basic"), ({"url": "mqtt://x:1883"}, "all", "all"),
])
def test_resolve_level_combinations(saved_rec, default, want):
    assert resolve_level(saved_rec, default) == want


def test_demo_is_always_basic_and_refuses_the_route(tmp_path, monkeypatch):
    monkeypatch.setenv("ET_HA_SENSORS", "all")
    cfg = Config(data_dir=tmp_path, tz="America/New_York", demo=True, web_dir=tmp_path / "noweb")
    assert cfg.ha_sensors == "basic"
    cfg.ha_sensors = "all"                             # even if set after construction, the app's demo setup wins
    with TestClient(create_app(cfg)) as c:
        assert c.app.state.ha.level == "basic"
        r = c.put("/api/integrations/ha/sensors", json={"level": "all"}, headers=H)
        assert r.status_code == 403 and r.json() == {"detail": "Not available in the demo."}
        assert c.app.state.ha.level == "basic"
