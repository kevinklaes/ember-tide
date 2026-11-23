"""Garmin, through each person's own Personal API key.

The person makes a key at Garmin Connect and pastes it here. There are no owner credentials and no sign-in page: the
key is exchanged for a token (valid about 24 hours), the token is sent with each data call, and a new token is asked
for with the key when less than an hour of the old one is left. The key and the token are stored only sealed
(`sealed.py`, bound to the row `garmin:<person>`); the token's end time is kept in clear so deciding whether to renew
needs no decryption.

Every request goes through `_send()`: one fixed host, no redirects, a 20 s timeout, and one request at a time for the
whole provider with a pause between them. A 429 stops the sync and backs off; while backing off, a manual look and a
new key are refused without calling Garmin. Neither the key nor the token is ever put in a URL, a log line, an
exception text or a status.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from .base import UA, CloudConnector, CloudData, CloudError, retry_after
from .sealed import Sealer, SealError

log = logging.getLogger(__name__)

HOST = "https://personal.connectapi.garmin.com"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
SLEEP_PATH = "/sleep-service/sleep/dailySleepSummariesByDate"
RENEW_BEFORE_S = 3600
KEY_MAX = 1024
TOKEN_MAX = 8192
DEFAULT_LIFE_S = 86400.0
MAX_LIFE_S = 366 * 86400.0
TIMEOUT_S = 20.0
EXPIRY_AHEAD_DAYS = 366
EXPIRY_WARN_DAYS = 7
_VISIBLE = re.compile(r"^[\x21-\x7e]+$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

BUSY = "Garmin is busy; trying again later."
BAD_KEY = "That doesn't look like a Garmin key. Copy all of it from Garmin Connect, with no spaces, and paste it here."
BAD_DATE = "Choose the date the key runs out, from today to a year ahead."
NO_TOKEN = "Garmin didn't send a token."
UNREACHABLE = "Couldn't reach Garmin."
UNSAFE = "This server couldn't keep the key safe, so it wasn't saved. Check that its data folder can be written."
SKIP = object()                         # _get(soft=True): Garmin refused this kind of data; the caller skips it


def visible(v: object, most: int) -> bool:
    """1 to `most` visible ASCII characters: no space, no line break, nothing that could break a header."""
    return isinstance(v, str) and 0 < len(v) <= most and bool(_VISIBLE.match(v))


def claims(token: str) -> dict:
    """The JWT's claims, unchecked (the token only goes back to Garmin), or {} when they can't be read."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    try:
        raw = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        out = json.loads(raw)
    except Exception:  # noqa: BLE001  (anything unreadable means "no claims")
        return {}
    return out if isinstance(out, dict) else {}


def _num(v: object) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    v = float(v)
    return v if math.isfinite(v) else None


def lifetime(token: str, expires_in: object = None) -> float:
    """Seconds the token is good for: exp - iat, else exp - now, else expires_in, else 24 hours.

    A lifetime, not an end time: the end time is the home clock's now plus this, because the simulator's clock may
    run fast or jump while Garmin's exp is real epoch time."""
    c = claims(token)
    exp, iat = _num(c.get("exp")), _num(c.get("iat"))
    for life in ((exp - iat) if exp is not None and iat is not None else None,
                 (exp - time.time()) if exp is not None else None,
                 _num(expires_in) if not isinstance(expires_in, str) else _num(_float(expires_in))):
        if life is not None and life > 0:
            return min(life, MAX_LIFE_S)
    return DEFAULT_LIFE_S


def _float(v: str) -> float | None:
    try:
        return float(v)
    except ValueError:
        return None


class Garmin(CloudConnector):
    id = "garmin"
    name = "Garmin"
    device = "Garmin"
    connect_kind = "key"
    refreshes = False
    first_days = 14
    data_version = 1
    pause_s = 0.5
    gives = "sleep and nap times with the time in each stage, heart rate and HRV through the night, resting heart rate"
    docs_url = "https://developer.garmin.com/gc-developer-program/personal/personal-api/"

    def __init__(self, controller, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(controller, client)
        self._gate = asyncio.Lock()
        self._last: float | None = None
        self._forced: dict[str, int] = {}       # forced exchanges after a 401, per person, reset at each sync
        self._sleep = asyncio.sleep
        self._mono = time.monotonic
        self._sealer: Sealer | None = None

    # ---------- what's different about a key provider ----------
    @property
    def configured(self) -> bool:
        return True                             # nothing for the owner to set up

    @property
    def reconnect_text(self) -> str:
        return "Your Garmin key has run out or was deleted. Make a new one at Garmin Connect and paste it here."

    @property
    def sealer(self) -> Sealer:
        if self._sealer is None:
            path = getattr(self.store, "path", ":memory:")
            self._sealer = Sealer(None if path == ":memory:" else Path(path).parent)
        return self._sealer

    def bound(self, pid: str) -> str:
        return f"garmin:{pid}"

    def _today(self) -> date:
        return datetime.fromtimestamp(self.c.clock.now_ts(), self.c.clock.tz).date()

    # ---------- checks ----------
    @staticmethod
    def check_key(key: object) -> str:
        if not visible(key, KEY_MAX):
            raise CloudError(BAD_KEY, 422)
        return key  # type: ignore[return-value]

    def check_expires(self, text: object) -> str | None:
        if text is None or text == "":
            return None
        if not isinstance(text, str) or not _DATE.match(text):
            raise CloudError(BAD_DATE, 422)
        try:
            d = date.fromisoformat(text)
        except ValueError:
            raise CloudError(BAD_DATE, 422) from None
        today = self._today()
        if not today <= d <= today + timedelta(days=EXPIRY_AHEAD_DAYS):
            raise CloudError(BAD_DATE, 422)
        return d.isoformat()

    def _backing_off(self, pid: str) -> bool:
        st = self.store.get(self.k("status", pid), {}) or {}
        return self.c.clock.now_ts() < (st.get("backoff_until") or 0)

    # ---------- the one door to Garmin ----------
    async def _send(self, method: str, path: str, auth: str, params: dict | None = None) -> httpx.Response:
        """One request to the fixed host. The gate is held for this request only (pause, send, read), never across a
        token exchange: `_get()` and `fresh_token()` each come through here separately."""
        async with self._gate:
            if self._last is not None and self.pause_s > 0:
                wait = self.pause_s - (self._mono() - self._last)
                if wait > 0:
                    await self._sleep(wait)
            try:
                async with self._http() as c:
                    r = await c.request(method, HOST + path, params=params, follow_redirects=False, timeout=TIMEOUT_S,
                                        headers={**UA, "Accept": "application/json", "Authorization": auth})
                    await r.aread()
            finally:
                self._last = self._mono()
        return r

    async def _exchange(self, key: str) -> tuple[str, float]:
        """The key for a token: (token, end time on the home clock)."""
        r = await self._send("POST", TOKEN_PATH, f"ApiKey {key}")
        if r.status_code == 429:
            raise CloudError(BUSY, 429, retry_after(r))
        if r.status_code in (400, 401, 403):
            raise CloudError(self.reconnect_text, 401)
        if r.status_code >= 300:
            raise CloudError(f"Garmin answered {r.status_code}.", r.status_code)
        text = r.text.strip()
        token, expires_in = text, None
        try:
            body = json.loads(text) if text else None
        except ValueError:
            body = None                          # a bare token (what Garmin sends today) isn't JSON
        if isinstance(body, dict):
            token, expires_in = body.get("access_token"), body.get("expires_in")
        elif isinstance(body, str):
            token = body
        elif body is not None:
            token = None
        if not visible(token, TOKEN_MAX):
            raise CloudError(NO_TOKEN)
        return token, self.c.clock.now_ts() + lifetime(token, expires_in)  # type: ignore[arg-type]

    def _save(self, pid: str, key: str, token: str, expires_at: float, connected_at: float) -> None:
        sealed = self.sealer.seal({"key": key, "token": token}, self.bound(pid))   # raises SealError
        self.store.put(self.k("token", pid), {"v": 1, "sealed": sealed, "expires_at": expires_at, "connected_at": connected_at})

    # ---------- per person ----------
    def connected(self, pid: str) -> bool:
        return bool((self.token(pid) or {}).get("sealed"))

    async def connect_key(self, pid: str, key: object, expires: object = None) -> None:
        """Check, exchange once, then seal and save: nothing is written unless both worked. Replaces a working key only
        once the new one has been accepted."""
        key = self.check_key(key)
        until = self.check_expires(expires)
        if self._backing_off(pid):
            raise CloudError(BUSY, 429)
        async with self._locks.setdefault(pid, asyncio.Lock()):
            try:
                token, expires_at = await self._exchange(key)
            except CloudError as e:
                if e.status == 429:
                    now = self.c.clock.now_ts()
                    self._status(pid, last_error=BUSY, backoff_until=now + (e.retry_after or 900))
                raise
            except httpx.HTTPError:
                raise CloudError(UNREACHABLE) from None
            try:
                self._save(pid, key, token, expires_at, time.time())
            except SealError:
                raise CloudError(UNSAFE) from None
            self._status(pid, needs_reconnect=False, last_error=None, key_expires=until)

    async def fresh_token(self, pid: str, force: bool = False) -> str:
        t = self.token(pid) or {}
        if not t.get("sealed"):
            raise CloudError("Garmin isn't connected.", 401)
        val = self.sealer.open(t.get("sealed"), self.bound(pid))
        if not val or not visible(val.get("key"), KEY_MAX):
            raise CloudError(self.reconnect_text, 401)         # the server's secret was lost or replaced
        tok = val.get("token")
        left = (_num(t.get("expires_at")) or 0) - self.c.clock.now_ts()
        if not force and visible(tok, TOKEN_MAX) and left > RENEW_BEFORE_S:
            return tok
        tok, expires_at = await self._exchange(val["key"])
        try:
            self._save(pid, val["key"], tok, expires_at, t.get("connected_at") or time.time())
        except SealError:
            raise CloudError(UNSAFE) from None
        return tok

    async def _get(self, pid: str, path: str, params: dict | None = None, soft: bool = False):
        """One data call: the parsed JSON body, None for no data (204, 404, empty or unreadable), or SKIP when `soft`
        and Garmin refused this kind of data (400/403). A 401 renews the token once per sync and retries once."""
        tok = await self.fresh_token(pid)
        r = await self._send("GET", path, f"Bearer {tok}", params)
        if r.status_code == 401:
            if self._forced.get(pid, 0) >= 1:
                raise CloudError(self.reconnect_text, 401)
            self._forced[pid] = self._forced.get(pid, 0) + 1
            tok = await self.fresh_token(pid, force=True)
            r = await self._send("GET", path, f"Bearer {tok}", params)
        if r.status_code == 429:
            raise CloudError(BUSY, 429, retry_after(r))
        if r.status_code == 401:
            raise CloudError(self.reconnect_text, 401)
        if r.status_code in (204, 404):
            return None
        if soft and r.status_code in (400, 403):
            log.info("garmin: a data call answered %s; skipped for this sync", r.status_code)
            return SKIP
        if r.status_code >= 300:
            raise CloudError(f"Garmin answered {r.status_code}.", r.status_code)
        if not r.content.strip():
            return None
        try:
            return r.json()
        except ValueError:
            return None

    async def fetch(self, pid: str, start: date, end: date, now: float) -> CloudData:
        """Connection half only: one sleep call for the window, nothing stored yet. The data work item fills this."""
        today = datetime.fromtimestamp(now, self.c.clock.tz).date()
        await self._get(pid, SLEEP_PATH, {"startDate": start.isoformat(), "endDate": min(end, today).isoformat()})
        return CloudData()

    async def sync(self, pid: str, days: int | None = None) -> dict:
        if self._backing_off(pid):
            raise CloudError(BUSY, 429)                        # a manual look during a back-off: no call to Garmin
        async with self._locks.setdefault(pid, asyncio.Lock()):
            self._forced[pid] = 0
            try:
                return await self._sync(pid, days)
            finally:
                self._forced.pop(pid, None)

    async def disconnect(self, pid: str) -> None:
        async with self._locks.setdefault(pid, asyncio.Lock()):   # waits for a running look, so it can't write back
            await super().disconnect(pid)                          # no revoke address: no request to Garmin

    def status(self, pid: str) -> dict:
        out = super().status(pid)
        st = self.store.get(self.k("status", pid), {}) or {}
        until = st.get("key_expires") if self.connected(pid) else None
        soon = False
        if isinstance(until, str):
            try:
                soon = (date.fromisoformat(until) - self._today()).days <= EXPIRY_WARN_DAYS
            except ValueError:
                until = None
        out.update(connect="key", key_expires=until or None, key_expires_soon=soon)
        return out
