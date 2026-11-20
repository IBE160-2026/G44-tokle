"""A fake transport and a fake clock for the Polymarket client's tests (AD-17).

No socket is opened: the transport answers from a script and records every call, and the clock
only moves when something sleeps.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from liquidoracle.data.polymarket import Response, TransportConnectionError, TransportTimeout

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
