"""A fake Garmin Personal API for the Garmin tests (connection and data), on httpx.MockTransport.

Synthetic values only. Tokens are built while the test runs from three base64url parts, so no file holds a literal
token. It records every request and notes any request to a host other than Garmin's.
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx

HOST = "personal.connectapi.garmin.com"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
SLEEP_PATH = "/sleep-service/sleep/dailySleepSummariesByDate"
KEY = "k-synthetic-0123456789"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def make_token(n: int, life: float | None = 86400, iat: float | None = None, readable: bool = True) -> str:
    """A three-part token like Garmin's. `readable=False` gives claims that can't be decoded."""
    head = _b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    if not readable:
        body = "%%not-base64%%"
    else:
        now = time.time() if iat is None else iat
        c: dict = {"sub": f"synthetic-{n}", "n": n}
        if life is not None:
            c.update(iat=int(now), exp=int(now + life))
        body = _b64(json.dumps(c).encode())
    return f"{head}.{body}.{_b64(b'synthetic-signature-%d' % n)}"


class FakeGarmin:
    """`exchange`: "bare" (default), "json", "jsonstr", "empty", or an HTTP status to answer with.
    `refused`: keys answered 401. `data`: path -> fn(request) -> Response for data calls (default: an empty list).
    `data_401`: answer this many data calls 401 first. `always_401`: every data call is 401.
    `status_at`: {nth data call (1-based): (status, headers)}."""

    def __init__(self, data: dict[str, Callable[[httpx.Request], httpx.Response]] | None = None) -> None:
        self.calls: list[httpx.Request] = []
        self.foreign: list[str] = []
        self.exchange: str | int = "bare"
        self.life: float | None = 86400
        self.readable = True
        self.expires_in: float | None = 86400
        self.refused: set[str] = set()
        self.issued: list[str] = []
        self.valid: set[str] = set()
        self.data = data or {}
        self.data_401 = 0
        self.always_401 = False
        self.status_at: dict[int, tuple[int, dict]] = {}
        self.data_calls = 0

    # ---------- what the tests look at ----------
    def exchanges(self) -> list[httpx.Request]:
        return [r for r in self.calls if urlsplit(str(r.url)).path == TOKEN_PATH]

    def data_requests(self) -> list[httpx.Request]:
        return [r for r in self.calls if urlsplit(str(r.url)).path != TOKEN_PATH]

    def revoke_tokens(self) -> None:
        """Every token handed out so far stops working (the next data call answers 401)."""
        self.valid.clear()

    # ---------- the service ----------
    def _token(self, req: httpx.Request) -> httpx.Response:
        auth = req.headers.get("authorization", "")
        if req.method != "POST" or not auth.startswith("ApiKey ") or auth[7:] in self.refused:
            return httpx.Response(401)
        if isinstance(self.exchange, int):
            return httpx.Response(self.exchange)
        if self.exchange == "empty":
            return httpx.Response(200, content=b"")
        tok = make_token(len(self.issued) + 1, self.life, readable=self.readable)
        self.issued.append(tok)
        self.valid.add(tok)
        if self.exchange == "json":
            return httpx.Response(200, json={"access_token": tok, "expires_in": self.expires_in})
        if self.exchange == "jsonstr":
            return httpx.Response(200, json=tok)
        return httpx.Response(200, content=tok.encode(), headers={"content-type": "text/plain"})

    def _data(self, req: httpx.Request, path: str) -> httpx.Response:
        self.data_calls += 1
        if self.data_calls in self.status_at:
            status, headers = self.status_at[self.data_calls]
            return httpx.Response(status, headers=headers)
        auth = req.headers.get("authorization", "")
        if self.always_401 or not auth.startswith("Bearer ") or auth[7:] not in self.valid:
            return httpx.Response(401)
        if self.data_401 > 0:
            self.data_401 -= 1
            return httpx.Response(401)
        fn = self.data.get(path)
        if fn:
            return fn(req)
        return httpx.Response(200, json=[]) if path == SLEEP_PATH else httpx.Response(204)

    def handle(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        u = urlsplit(str(req.url))
        if u.scheme != "https" or u.netloc != HOST:
            self.foreign.append(str(req.url))
            return httpx.Response(404)
        if u.path == TOKEN_PATH:
            return self._token(req)
        return self._data(req, u.path)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle))
