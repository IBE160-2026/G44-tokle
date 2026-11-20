"""The one Polymarket client: read-only, polite, typed (AD-2, AD-3, NFR-6, NFR-11).

Only this module talks to Polymarket. It sends GET requests to Data API v2 and Gamma, with no
keys, and refuses every other URL before anything is sent (Data API v1 retired on 2026-10-24).
Every request, retries included, waits its turn at one locked rate limiter. Failures follow the
one retry policy of AD-3 and end as typed errors from `data/errors.py`. Replies are turned into
`records` types here, so nothing above `data/` sees raw JSON.

The app builds one client per process (Story 2.5, in `open_sources`), which makes its limiter
the process-wide one. Story 2.2 builds the Wallet window (`positions_near`) on these reads.
"""

from __future__ import annotations

import json
import logging
import math
import re
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

import requests

from liquidoracle.data.errors import PolymarketBadRequest, PolymarketUnavailable, ProtocolContractAddress
from liquidoracle.records import ActivityRow, ListedPosition, Market, Read
from liquidoracle.settings import MAX_REQUESTS_PER_SECOND

log = logging.getLogger(__name__)

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
_ALLOWED_HOSTS = {urlsplit(DATA_API).netloc, urlsplit(GAMMA_API).netloc}
_GAMMA_HOST = urlsplit(GAMMA_API).netloc

# No keys and no auth headers; a generic name, nothing about the user (AD-2).
HEADERS = {"User-Agent": "liquidoracle/0.1 (student project)", "Accept": "application/json"}

TRIES = 3  # AD-3: at most 3 tries in all, then PolymarketUnavailable
BACKOFF = (1.0, 2.0)  # [ASSUMPTION] seconds before try 2 and try 3 when there is no Retry-After
MAX_RETRY_AFTER = 60.0  # [ASSUMPTION] AD-3 (Edvard, 2026-11-20): a longer Retry-After is not waited out
CONNECT_TIMEOUT, READ_TIMEOUT = 5.0, 30.0  # [ASSUMPTION] seconds
# AD-3 (Edvard, 2026-11-20): 500, 502 and 504 are retried like 503.
RETRIED_STATUS = frozenset({429, 500, 502, 503, 504})

PAGE_LIMIT = 1000  # rows per page; the cursor fixes it for the whole walk (AD-3)
GAMMA_BATCH = 20  # Markets per Gamma request; repeat `condition_ids`, a comma list returns nothing
ACTIVITY_TYPES = "TRADE,REDEEM,SPLIT,MERGE,CONVERSION"  # AD-10
LIST_STATUSES = frozenset({"CLOSED", "OPEN"})  # AD-10: OPEN also holds settled losers nobody redeemed
_WALLET = re.compile(r"0x[0-9a-f]{40}")  # FR-1: a proxy-wallet address, lower case


# --- Transport: the only part that touches the network -------------------------------------


@dataclass(frozen=True, slots=True)
class Response:
    """One HTTP answer. `headers` keys are lower case."""

    status: int
    headers: Mapping[str, str]
    body: bytes


class TransportTimeout(Exception):
    """The request timed out (connecting or reading)."""


class TransportConnectionError(Exception):
    """No connection could be made: no internet, a DNS failure, a refused connection."""


class Transport(Protocol):
    def get(self, url: str, params: Sequence[tuple[str, str]], headers: Mapping[str, str]) -> Response:
        """Send one GET. Raises TransportTimeout or TransportConnectionError."""
        ...


class RequestsTransport:
    """The real transport, on `requests`. One session per thread, since a session is not thread-safe.

    Only the one worker thread fetches (AD-5), so in practice there is one session.
    """

    def __init__(self) -> None:
        self._local = threading.local()

    def get(self, url: str, params: Sequence[tuple[str, str]], headers: Mapping[str, str]) -> Response:
        session = getattr(self._local, "session", None)
        if session is None:
            session = self._local.session = requests.Session()
        try:
            reply = session.get(
                url,
                params=list(params),
                headers=dict(headers),
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                allow_redirects=False,  # a redirect could lead off the allowed hosts
            )
        except requests.Timeout as error:  # before ConnectionError: ConnectTimeout is both
            raise TransportTimeout(str(error)) from error
        except requests.ConnectionError as error:
            # A timeout while reading the body arrives as ConnectionError wrapping urllib3's
            # ReadTimeoutError (requests' iter_content); it is still a timeout (AD-3).
            if any(type(arg).__name__ == "ReadTimeoutError" for arg in error.args):
                raise TransportTimeout(str(error)) from error
            raise TransportConnectionError(str(error)) from error
        except requests.RequestException as error:  # e.g. the connection broke mid-body
            raise TransportConnectionError(str(error)) from error
        return Response(reply.status_code, {k.lower(): v for k, v in reply.headers.items()}, reply.content)


# --- Rate limiter ---------------------------------------------------------------------------


class RateLimiter:
    """Request start times at least 1/rate seconds apart, across all threads (AD-3, NFR-6).

    It keeps the next free slot under its lock and sleeps while holding it, so threads line up
    one after another instead of each believing it is under the limit.
    """

    def __init__(
        self,
        rate: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 0 < rate <= MAX_REQUESTS_PER_SECOND:
            raise ValueError(f"requests per second must be above 0 and at most {MAX_REQUESTS_PER_SECOND:g}, not {rate}")
        self._interval = 1.0 / rate
        self._clock = clock
        self._sleep = sleep
        self._next: float | None = None
        self._lock = threading.Lock()

    def wait(self) -> float:
        """Block until this caller may send one request. Returns the start time it was given."""
        with self._lock:
            now = self._clock()
            if self._next is not None and self._next > now:
                self._sleep(self._next - now)
                now = self._next
            self._next = now + self._interval
            return now


# --- The client -----------------------------------------------------------------------------


class _PageTimedOut(PolymarketUnavailable):
    """Every try of one request timed out. The walker restarts with a smaller `limit` (AD-3)."""


class PolymarketClient:
    """Read-only access to Data API v2 and Gamma. Safe to share between threads."""

    def __init__(
        self,
        requests_per_second: float,
        *,
        transport: Transport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self._transport = transport if transport is not None else RequestsTransport()
        self._limiter = RateLimiter(requests_per_second, clock=clock, sleep=sleep)
        self._sleep = sleep
        self._wall_clock = wall_clock  # for a Retry-After given as a date

    # The three reads ------------------------------------------------------------------------

    def positions_list(
        self,
        wallet: str,
        status: str,
        *,
        sort_by: str | None = None,
        sort_direction: str | None = None,
        limit: int = PAGE_LIMIT,
    ) -> Read[ListedPosition]:
        """One of the Wallet's positions lists, CLOSED or OPEN, every page (AD-10).

        `status` on each record is the list asked for: rows of the OPEN list may say
        REDEEMABLE, but they are still the open list (unredeemed losers live there, FR-3).
        """
        _check_wallet(wallet)
        if status not in LIST_STATUSES:
            raise ValueError(f"status must be CLOSED or OPEN, not {status!r}")
        params: list[tuple[str, str]] = [("user", wallet), ("status", status)]
        if sort_by is not None:
            params.append(("sort_by", sort_by))
        if sort_direction is not None:
            params.append(("sort_direction", sort_direction))
        return self._walk(f"{DATA_API}/v2/positions", params, limit, lambda raw: _listed_position(raw, status))

    def activity_rows(
        self,
        wallet: str,
        *,
        start: int,
        end: int | None = None,
        sort_direction: str = "ASC",
        limit: int = PAGE_LIMIT,
    ) -> Read[ActivityRow]:
        """The Wallet's activity rows of the five types, from `start` (sent explicitly), every page (AD-10).

        `is_combo` rows are dropped. Rows that look identical are kept: they are separate fills.
        """
        _check_wallet(wallet)
        params: list[tuple[str, str]] = [("user", wallet), ("type", ACTIVITY_TYPES), ("start", str(int(start)))]
        if end is not None:
            params.append(("end", str(int(end))))
        params.append(("sort_direction", sort_direction))
        return self._walk(f"{DATA_API}/v2/activity", params, limit, _activity_row)

    def markets(self, condition_ids: Iterable[str]) -> tuple[Market, ...]:
        """Gamma's records for these Markets, at most 20 per request, in the order asked (AD-7, AD-10).

        Gamma filters on `closed`, and without it returns only open Markets (checked live,
        2026-11-20), so each batch is asked with `closed=true` first and the ids still missing
        are asked again with `closed=false`. A Market Gamma returns in neither is left out; the
        caller decides what that means.
        """
        wanted = list(dict.fromkeys(condition_ids))
        found: dict[str, Market] = {}
        for i in range(0, len(wanted), GAMMA_BATCH):
            batch = wanted[i : i + GAMMA_BATCH]
            for closed in ("true", "false"):
                ask = [c for c in batch if c not in found]
                if not ask:
                    break
                params = [("condition_ids", c) for c in ask] + [("closed", closed), ("limit", str(len(ask)))]
                document = self._get_json(f"{GAMMA_API}/markets", params)
                if not isinstance(document, list):
                    raise _unreadable("Gamma /markets", "expected a list")
                for raw in document:
                    market = _parse(_market, raw, "Gamma /markets")
                    if market.condition_id in ask:
                        found[market.condition_id] = market
        return tuple(found[c] for c in wanted if c in found)

    # Paging -----------------------------------------------------------------------------------

    def _walk(
        self,
        url: str,
        params: Sequence[tuple[str, str]],
        limit: int,
        parse: Callable[[Any], Any | None],
    ) -> Read[Any]:
        """Walk a cursor-paged Data API list (AD-2, AD-3).

        Every page sends the same parameters apart from `cursor`. If a later page still times
        out after its 3 tries, the walk restarts once from the start with half the `limit`; if
        that also fails mid-walk, the rows read so far come back marked incomplete. A first page
        that fails raises, because nothing at all was read.
        """
        if limit < 1:
            raise ValueError(f"limit must be 1 or more, not {limit}")
        what = urlsplit(url).path
        for page_limit, last_attempt in ((limit, False), (max(1, limit // 2), True)):
            fixed = [*params, ("limit", str(page_limit))]
            rows: list[Any] = []
            seen: set[str] = set()
            cursor: str | None = None
            try:
                while True:
                    query = fixed if cursor is None else [*fixed, ("cursor", cursor)]
                    document = self._get_json(url, query)
                    if not isinstance(document, dict) or not isinstance(document.get("data"), list):
                        raise _unreadable(what, "expected an object with a data list")
                    for raw in document["data"]:
                        record = _parse(parse, raw, what)
                        if record is not None:
                            rows.append(record)
                    paging = document.get("pagination")
                    if not isinstance(paging, dict) or not isinstance(paging.get("has_more"), bool):
                        raise _unreadable(what, "no pagination with a true or false has_more")
                    if not paging["has_more"]:
                        return Read(tuple(rows), True)
                    cursor = paging.get("next_cursor")
                    if not isinstance(cursor, str) or not cursor or cursor in seen:
                        # More was promised but there is no new way to reach it: say so.
                        log.warning("Polymarket %s said there was more but gave no new cursor", what)
                        return Read(tuple(rows), False)
                    seen.add(cursor)
            except _PageTimedOut:
                if cursor is None:  # the first page: nothing was read
                    raise
                if last_attempt:
                    log.warning("Polymarket %s kept timing out mid-walk; the read is partial", what)
                    return Read(tuple(rows), False)
                log.info("Polymarket %s timed out mid-walk; restarting with limit %d", what, max(1, limit // 2))
        raise AssertionError("unreachable")  # pragma: no cover

    # One request, with the one retry policy ---------------------------------------------------

    def _get_json(self, url: str, params: Sequence[tuple[str, str]]) -> Any:
        check_url(url)
        what = urlsplit(url).path
        every_try_timed_out = True  # "still timing out after 3 tries" (AD-3) restarts a walk
        for attempt in range(1, TRIES + 1):
            self._limiter.wait()
            timed_out = False
            wait: float | None = None
            try:
                reply = self._transport.get(url, params, HEADERS)
            except TransportTimeout:
                timed_out = True
                reason = "timed out"
            except TransportConnectionError:
                reason = "no connection"
            else:
                if reply.status == 200:
                    try:
                        return json.loads(reply.body, parse_constant=_refuse_constant)
                    except ValueError:
                        raise _unreadable(what, "the answer is not JSON") from None
                if not _is_retried(reply, url):
                    if 400 <= reply.status < 500:
                        raise _bad_request(reply, what)
                    raise PolymarketUnavailable(f"Polymarket answered {reply.status} on {what}")
                reason = f"answered {reply.status}"
                wait = self._retry_after(reply.headers)
                if wait is not None and wait > MAX_RETRY_AFTER:
                    raise PolymarketUnavailable(f"Polymarket asked to wait {wait:.0f} s on {what}; not waiting that long")
            every_try_timed_out = every_try_timed_out and timed_out
            if attempt == TRIES:
                error_type = _PageTimedOut if every_try_timed_out else PolymarketUnavailable
                raise error_type(f"Polymarket {reason} on {what}, {TRIES} tries")
            self._sleep(wait if wait is not None else BACKOFF[attempt - 1])
        raise AssertionError("unreachable")  # pragma: no cover

    def _retry_after(self, headers: Mapping[str, str]) -> float | None:
        """Seconds the `Retry-After` header asks for, or None when absent or unreadable."""
        value = headers.get("retry-after")
        if value is None:
            return None
        value = value.strip()
        try:
            seconds = float(value)
        except ValueError:
            try:
                when = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return None
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
            seconds = when.timestamp() - self._wall_clock()
        if seconds != seconds:  # NaN
            return None
        return max(0.0, seconds)


# --- Helpers --------------------------------------------------------------------------------


def check_url(url: str) -> None:
    """AD-2: only HTTPS to Data API v2 or Gamma. Anything else is a bug and is refused before sending."""
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc not in _ALLOWED_HOSTS or parts.query or parts.fragment:
        raise ValueError(f"refused URL (not Data API v2 or Gamma): {url}")
    if parts.netloc != _GAMMA_HOST and not parts.path.startswith("/v2/"):
        raise ValueError(f"refused URL (Data API v1 is not used): {url}")


def _check_wallet(wallet: str) -> None:
    if not isinstance(wallet, str) or not _WALLET.fullmatch(wallet):
        raise ValueError(f"not a lower-case proxy-wallet address: {wallet!r}")


def _is_retried(reply: Response, url: str) -> bool:
    """AD-3: which answers are worth another try."""
    if reply.status in RETRIED_STATUS:
        return True
    gamma = urlsplit(url).netloc == _GAMMA_HOST
    if reply.status == 403:
        return gamma or _from_cloudfront(reply.headers)
    if reply.status == 404:
        # Gamma answered an empty 404 on every route during a 2-minute outage (2026-10-21).
        return gamma and reply.body.strip() in (b"", b"[]", b"{}", b"null")
    return False


def _from_cloudfront(headers: Mapping[str, str]) -> bool:
    return (
        "cloudfront" in headers.get("server", "").lower()
        or "cloudfront" in headers.get("x-cache", "").lower()
        or "x-amz-cf-id" in headers
    )


def _bad_request(reply: Response, what: str) -> PolymarketBadRequest:
    # Logged with status and path only: the body can be long and says nothing the user needs.
    log.warning("Polymarket refused %s with %d", what, reply.status)
    if reply.status == 400 and b"protocol contract address" in reply.body.lower():
        return ProtocolContractAddress(f"Polymarket refused {what}: protocol contract address", reply.status)
    return PolymarketBadRequest(f"Polymarket refused {what} with {reply.status}", reply.status)


def _unreadable(what: str, detail: str) -> PolymarketUnavailable:
    log.warning("Polymarket %s gave an answer the client cannot read: %s", what, detail)
    return PolymarketUnavailable(f"Polymarket gave an unreadable answer on {what}: {detail}")


def _refuse_constant(name: str) -> float:
    raise ValueError(f"{name} is not allowed")


def _parse(parse: Callable[[Any], Any], raw: Any, what: str) -> Any:
    try:
        if not isinstance(raw, Mapping):
            raise TypeError("a row is not an object")
        return parse(raw)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise _unreadable(what, f"a row is not as expected ({error!r})") from None


def _text(raw: Mapping[str, Any], key: str) -> str:
    value = raw[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is not text")
    return value


def _number(raw: Mapping[str, Any], key: str) -> float:
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{key} is not a number")
    return float(value)


def _whole(raw: Mapping[str, Any], key: str) -> int:
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} is not a whole number")
    return value


def _listed_position(raw: Mapping[str, Any], status: str) -> ListedPosition:
    """A `/v2/positions` row. Shares bought is `total_size` (AD-10); `avg_price` is never used."""
    return ListedPosition(
        condition_id=_text(raw, "condition_id"),
        token_id=_text(raw, "token_id"),
        status=status,
        shares_bought=_number(raw, "total_size"),
        first_entry_at=_whole(raw, "first_entry_at"),
    )


def _activity_row(raw: Mapping[str, Any]) -> ActivityRow | None:
    """A `/v2/activity` row, or None for an `is_combo` row (AD-10). Only TRADE rows keep token and side."""
    if raw.get("is_combo") is True:
        return None
    kind = _text(raw, "type")
    trade = kind == "TRADE"
    return ActivityRow(
        type=kind,
        condition_id=_text(raw, "condition_id"),
        timestamp=_whole(raw, "timestamp"),
        size=_number(raw, "size"),
        usdc_size=_number(raw, "usdc_size"),
        price=_number(raw, "price"),
        token_id=_text(raw, "token_id") if trade else None,
        side=_text(raw, "side") if trade else None,
    )


def _market(raw: Mapping[str, Any]) -> Market:
    """A Gamma Market. `clobTokenIds` and `outcomePrices` arrive as JSON text; times as ISO text (AD-7).

    `closed`, the token ids and the prices are required: they decide "Resolved", so a missing
    one is an unreadable answer, never a guess. `feesEnabled` may be absent (False).
    """
    token_ids = _json_list(raw["clobTokenIds"], "clobTokenIds")
    prices = [float(p) for p in _json_list(raw["outcomePrices"], "outcomePrices")]
    if len(token_ids) < 2 or len(token_ids) != len(prices):
        raise ValueError("clobTokenIds and outcomePrices must list the same two or more outcomes")
    if not all(math.isfinite(p) for p in prices):
        raise ValueError("outcomePrices is not finite")
    closed = raw["closed"]
    fees_enabled = raw.get("feesEnabled", False)
    if not isinstance(closed, bool) or not isinstance(fees_enabled, bool):
        raise ValueError("closed or feesEnabled is not true or false")
    closed_time = raw.get("closedTime")
    if closed_time is not None and not isinstance(closed_time, str):
        raise ValueError("closedTime is not text")
    return Market(
        condition_id=_text(raw, "conditionId"),
        closed=closed,
        closed_time=parse_time(closed_time) if closed_time else None,
        token_ids=tuple(str(t) for t in token_ids),
        outcome_prices=tuple(prices),
        fees_enabled=fees_enabled,
    )


def _json_list(value: Any, key: str) -> list[Any]:
    items = json.loads(value, parse_constant=_refuse_constant) if isinstance(value, str) else value
    if not isinstance(items, list):
        raise ValueError(f"{key} is not a JSON list")
    return items


def parse_time(text: str) -> int:
    """Gamma's time text ("2025-04-17 08:51:19+00", ISO with Z, ...) as UTC epoch seconds."""
    cleaned = text.strip().replace(" ", "T", 1)
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    elif "T" in cleaned and re.search(r"[+-]\d\d$", cleaned):  # "+00" -> "+00:00"; never a date's "-17"
        cleaned += ":00"
    moment = datetime.fromisoformat(cleaned)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return int(moment.timestamp())
