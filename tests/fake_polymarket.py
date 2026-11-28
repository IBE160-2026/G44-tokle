"""A fake transport and a fake clock for the Polymarket client's tests (AD-17).

No socket is opened: the transport answers from a script and records every call, and the clock
only moves when something sleeps.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from liquidoracle.data.polymarket import (
    PROBE_END,
    PROBE_START,
    PROBE_TOKEN,
    Response,
    TransportConnectionError,
    TransportTimeout,
)

TIMEOUT = "timeout"  # script entry: the transport raises TransportTimeout
NO_CONNECTION = "no connection"  # script entry: the transport raises TransportConnectionError


def ok(document: Any) -> Response:
    return Response(200, {}, json.dumps(document).encode())


def status(code: int, body: bytes = b"", **headers: str) -> Response:
    return Response(code, {k.replace("_", "-").lower(): v for k, v in headers.items()}, body)


def page(rows: list[dict[str, Any]], next_cursor: str | None = None) -> Response:
    """One Data API page; `next_cursor` None means the last page."""
    return ok({"data": rows, "pagination": {"has_more": next_cursor is not None, "next_cursor": next_cursor}})


@dataclass
class Call:
    url: str
    params: list[tuple[str, str]]
    headers: dict[str, str]
    at: float  # fake-clock time the request was sent

    @property
    def query(self) -> dict[str, str]:
        return dict(self.params)

    def without_cursor(self) -> list[tuple[str, str]]:
        return [(k, v) for k, v in self.params if k != "cursor"]


class FakeClock:
    """Monotonic time that moves only by `sleep`. Thread-safe."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self.now

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self.sleeps.append(seconds)
            self.now += seconds


@dataclass
class FakeTransport:
    """Answers each GET with the next scripted entry: a Response, TIMEOUT or NO_CONNECTION.

    With `answer`, every call is answered by that function instead of the script.
    """

    script: list[Response | str] = field(default_factory=list)
    clock: FakeClock | None = None
    answer: Callable[[str, list[tuple[str, str]]], Response] | None = None
    calls: list[Call] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get(self, url: str, params: Sequence[tuple[str, str]], headers: Mapping[str, str]) -> Response:
        with self._lock:
            at = self.clock() if self.clock else 0.0
            self.calls.append(Call(url, list(params), dict(headers), at))
            if self.answer is not None:
                return self.answer(url, list(params))
            if not self.script:
                raise AssertionError(f"unexpected request {url} {list(params)}")
            entry = self.script.pop(0)
        if entry == TIMEOUT:
            raise TransportTimeout("fake timeout")
        if entry == NO_CONNECTION:
            raise TransportConnectionError("fake: no connection")
        assert isinstance(entry, Response)
        return entry


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "capture"


class FakePolymarket:
    """A routed stand-in for Data API v2 and Gamma, serving one fixture Wallet (AD-17).

    Use it as `FakeTransport(answer=FakePolymarket("small-clean"))`. It filters, sorts and pages
    like the real routes: `/v2/positions` by `status`, `sort_by=TIMESTAMP` on `last_event_at`;
    `/v2/activity` by `start`/`end` (both included) and `type`; Gamma `/markets` by repeated
    `condition_ids` and `closed`. The cursor is the offset of the next row as text. Fixtures are
    cut from the real capture by `tests/fixtures/cut_from_capture.py`.

    `timeout_from_page[key]` makes every page from that index on time out, where key is CLOSED,
    OPEN or ACTIVITY; `timeouts_left[key]` limits how many such timeouts happen before the pages
    are served again (a busy spell that passes). `gamma_timeouts` times out that many Gamma
    requests after `gamma_after` of them have been answered.
    """

    def __init__(self, name: str) -> None:
        document = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        self.wallet: str = document["wallet"]
        self.lists = {"CLOSED": document["positions_closed"], "OPEN": document["positions_open"]}
        self.activity: list[dict[str, Any]] = document["activity"]
        self.gamma: list[dict[str, Any]] = document["gamma"]
        self.timeout_from_page: dict[str, int] = {}  # CLOSED/OPEN/ACTIVITY -> first page index (0-based) that times out
        self.timeouts_left: dict[str, int] = {}  # key -> how many timeouts before serving again (absent: for ever)
        self.gamma_after = 0  # Gamma requests answered before the timeouts start
        self.gamma_timeouts = 0
        self._gamma_seen = 0
        self.page_size: int | None = None  # serve at most this many rows per page, like a smaller API page
        self.before_activity: Callable[[], None] | None = None  # runs before each activity page is served

    def __call__(self, url: str, params: list[tuple[str, str]]) -> Response:
        query = dict(params)
        if url.endswith("/v2/positions"):
            assert query["user"] == self.wallet
            rows = list(self.lists[query["status"]])
            if query.get("sort_by") == "TIMESTAMP":
                rows.sort(key=lambda row: row["last_event_at"], reverse=query.get("sort_direction") == "DESC")
            return self._page(rows, query, timeout_key=query["status"])
        if url.endswith("/v2/activity"):
            assert query["user"] == self.wallet and "start" in query and "limit" in query
            if self.before_activity is not None:
                self.before_activity()
            types = set(query["type"].split(","))
            start, end = int(query["start"]), int(query["end"]) if "end" in query else None
            rows = [
                row for row in self.activity
                if row["type"] in types and row["timestamp"] >= start and (end is None or row["timestamp"] <= end)
            ]
            rows.sort(key=lambda row: row["timestamp"], reverse=query.get("sort_direction") == "DESC")
            return self._page(rows, query, timeout_key="ACTIVITY")
        if url.endswith("/markets"):
            self._gamma_seen += 1
            if self._gamma_seen > self.gamma_after and self.gamma_timeouts > 0:
                self.gamma_timeouts -= 1
                raise TransportTimeout("fake Gamma timeout")
            wanted = [value for key, value in params if key == "condition_ids"]
            closed = query["closed"] == "true"
            return ok([m for m in self.gamma if m["conditionId"] in wanted and m["closed"] == closed])
        raise AssertionError(f"unexpected request {url}")

    def _page(self, rows: list[dict[str, Any]], query: dict[str, str], timeout_key: str | None = None) -> Response:
        size = int(query["limit"]) if self.page_size is None else min(int(query["limit"]), self.page_size)
        offset = int(query.get("cursor", "0"))
        if timeout_key is not None and timeout_key in self.timeout_from_page:
            left = self.timeouts_left.get(timeout_key)
            if offset // size >= self.timeout_from_page[timeout_key] and (left is None or left > 0):
                if left is not None:
                    self.timeouts_left[timeout_key] = left - 1
                raise TransportTimeout("fake timeout")
        chunk = rows[offset : offset + size]
        more = offset + size < len(rows)
        return page(chunk, str(offset + size) if more else None)


class FakeScan:
    """A routed stand-in for everything the Scan funnel reads (AD-9, AD-17, AD-21).

    Use it as `FakeTransport(answer=FakeScan([...fixture names]))`. Its routes:

    - Gamma's volume-ordered list (`/markets` with `order`): `funnel`, raw Gamma Markets with a
      `volumeNum`, filtered on `closed`, highest volume first, paged by `offset` and `limit`.
    - Gamma by id (`/markets` with `condition_ids`): every served Wallet's Gamma records and `funnel`.
    - A Market's lists (`/v2/positions?condition=`): `holders[(condition_id, status)]`, paged by
      cursor. It asserts the AD-9 sort, so a Market-anchored request built otherwise fails here.
      `holder_answers[(condition_id, status)]` answers every such request instead (TIMEOUT or a Response).
    - A Wallet's lists and activity (`user=`): that Wallet's `FakePolymarket`; `refuse[address]`
      answers instead (a 400, say); any other address has no history (empty lists).
    - Price history (the old CLOB route, `/prices-history`, Story 6.2's Copy phase): the route check's own
      request gets one-minute points, so the client stays on this route; any other token gets its
      `prices[token_id]` ((time, price) pairs) inside the asked window, none when it has none.
      `price_answer` answers every such request instead (TIMEOUT or a Response).
    """

    def __init__(self, wallets: Sequence[str] = ()) -> None:
        self.wallets: dict[str, FakePolymarket] = {}
        for name in wallets:
            server = FakePolymarket(name)
            assert server.wallet not in self.wallets, f"two fixtures share Wallet {server.wallet}"
            self.wallets[server.wallet] = server
        self.funnel: list[dict[str, Any]] = []
        self.holders: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.holder_answers: dict[tuple[str, str], Response | str] = {}
        self.refuse: dict[str, Response] = {}
        self.prices: dict[str, list[tuple[int, float]]] = {}
        self.price_answer: Response | str | None = None

    def __call__(self, url: str, params: list[tuple[str, str]]) -> Response:
        query = dict(params)
        if url.endswith("/markets"):
            if "order" in query:
                return self._funnel_page(query)
            wanted = [value for key, value in params if key == "condition_ids"]
            closed = query["closed"] == "true"
            known = [m for server in self.wallets.values() for m in server.gamma] + self.funnel
            return ok([m for m in known if m["conditionId"] in wanted and m["closed"] == closed])
        if url.endswith("/v2/positions") and "condition" in query:
            assert "user" not in query
            assert (query.get("sort_by"), query.get("sort_direction")) == ("TIMESTAMP", "ASC"), "AD-9 sort missing"
            key = (query["condition"], query["status"])
            answer = self.holder_answers.get(key)
            if answer == TIMEOUT:
                raise TransportTimeout("fake timeout")
            if isinstance(answer, Response):
                return answer
            rows = self.holders.get(key, [])
            size, offset = int(query["limit"]), int(query.get("cursor", "0"))
            more = offset + size < len(rows)
            return page(rows[offset : offset + size], str(offset + size) if more else None)
        if url.endswith(("/v2/positions", "/v2/activity")):
            user = query["user"]
            if user in self.refuse:
                return self.refuse[user]
            if user in self.wallets:
                return self.wallets[user](url, params)
            assert url.endswith("/v2/positions"), "a Wallet with no positions has no activity to read"
            return page([])
        if url.endswith("/prices-history"):
            if query["market"] == PROBE_TOKEN:
                return ok({"history": [{"t": t, "p": 0.5} for t in range(PROBE_START + 6, PROBE_END, 60)]})
            if self.price_answer == TIMEOUT:
                raise TransportTimeout("fake timeout")
            if isinstance(self.price_answer, Response):
                return self.price_answer
            start, end = int(query["startTs"]), int(query["endTs"])
            points = self.prices.get(query["market"], [])
            return ok({"history": [{"t": t, "p": price} for t, price in points if start <= t <= end]})
        raise AssertionError(f"unexpected request {url}")

    def _funnel_page(self, query: dict[str, str]) -> Response:
        closed = query["closed"] == "true"
        rows = sorted((m for m in self.funnel if m["closed"] == closed), key=lambda m: -m["volumeNum"])
        offset, limit = int(query["offset"]), int(query["limit"])
        return ok(rows[offset : offset + limit])
