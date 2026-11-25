"""The one Polymarket client: read-only, polite, typed (AD-2, AD-3, NFR-6, NFR-11).

Only this module talks to Polymarket. It sends GET requests to Data API v2 and Gamma, with no
keys, and refuses every other URL before anything is sent (Data API v1 retired on 2026-10-24).
Every request, retries included, waits its turn at one locked rate limiter. Failures follow the
one retry policy of AD-3 and end as typed errors from `data/errors.py`. Replies are turned into
`records` types here, so nothing above `data/` sees raw JSON.

The app builds one client per process (Story 2.5, in `open_sources`), which makes its limiter
the process-wide one. `data/window.positions_near` builds the Wallet window on these reads.
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
from liquidoracle.records import ActivityRow, FunnelMarket, ListedPosition, Market, MarketHolder, Read
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
_CONDITION = re.compile(r"0x[0-9a-f]{64}")  # a Market's condition id, lower case

# AD-9 (Edvard, 2026-11-25, Story 4.2): a Market-anchored list that reaches this many rows is partial
# [ASSUMPTION]. The Sample Dataset pick's limit: 77 of 100 Markets used on 1 July 2025.
MARKET_ROW_CAP = 15_000
# AD-9: Market-anchored lists are always read oldest first; never by profit, the route's default.
MARKET_SORT = (("sort_by", "TIMESTAMP"), ("sort_direction", "ASC"))

# AD-21: the Market set's Gamma list, as the spike proved it (spike/sample_pick.py, 2026-10-21).
# Gamma filters on the scheduled end date, not `closedTime`, so the date range is widened on both sides.
GAMMA_LIST_PAGE = 100  # Markets per page of the volume-ordered list
GAMMA_LIST_PAGES = 50  # at most this many pages
END_DATE_BEFORE = 120 * 86_400  # seconds the end-date range starts before the window
END_DATE_AFTER = 400 * 86_400  # seconds it ends after it


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
        until: Callable[[tuple[ListedPosition, ...]], bool] | None = None,
        limit: int = PAGE_LIMIT,
    ) -> Read[ListedPosition]:
        """One of the Wallet's positions lists, CLOSED or OPEN, every page (AD-10).

        `status` on each record is the list asked for: rows of the OPEN list may say
        REDEEMABLE, but they are still the open list (unredeemed losers live there, FR-3).
        `until` sees each page's rows once it is read; when it says True the walk stops there
        and the read counts as complete (AD-7's stop rule).
        """
        _check_wallet(wallet)
        if status not in LIST_STATUSES:
            raise ValueError(f"status must be CLOSED or OPEN, not {status!r}")
        params: list[tuple[str, str]] = [("user", wallet), ("status", status)]
        if sort_by is not None:
            params.append(("sort_by", sort_by))
        if sort_direction is not None:
            params.append(("sort_direction", sort_direction))
        return self._walk(
            f"{DATA_API}/v2/positions", params, limit, lambda raw: _listed_position(raw, status), until=until
        )

    def activity_rows(
        self,
        wallet: str,
        *,
        start: int,
        end: int | None = None,
        sort_direction: str = "ASC",
        row_cap: int | None = None,
        limit: int = PAGE_LIMIT,
    ) -> Read[ActivityRow]:
        """The Wallet's activity rows of the five types, from `start` (sent explicitly), every page (AD-10).

        `is_combo` rows are dropped. Rows that look identical are kept: they are separate fills.
        With `row_cap`, the walk stops once that many rows are read and the read is incomplete
        (AD-7, `ACTIVITY_ROW_CAP`).
        """
        _check_wallet(wallet)
        params: list[tuple[str, str]] = [("user", wallet), ("type", ACTIVITY_TYPES), ("start", str(int(start)))]
        if end is not None:
            params.append(("end", str(int(end))))
        params.append(("sort_direction", sort_direction))
        return self._walk(f"{DATA_API}/v2/activity", params, limit, _activity_row, row_cap=row_cap)

    def markets(self, condition_ids: Iterable[str]) -> tuple[Market, ...]:
        """Gamma's records for these Markets, in the order asked; see `raw_markets` (AD-7, AD-10)."""
        return tuple(_parse(_market, raw, "Gamma /markets") for raw in self.raw_markets(condition_ids))

    def raw_markets(self, condition_ids: Iterable[str]) -> tuple[Mapping[str, Any], ...]:
        """Gamma's raw answers for these Markets, at most 20 per request, in the order asked (AD-7, AD-10).

        Each answer is checked with the Market parser before it is kept. The build-sample script
        stores these raw answers once next to the capture (Story 2.6); the app uses `markets`.

        Every request sends `include_tag=true`, so the event tags come with the Market (AD-10).

        Gamma filters on `closed`, and without it returns only open Markets (checked live,
        2026-11-20), so each batch is asked with `closed=true` first and the ids still missing
        are asked again with `closed=false`. A Market Gamma returns in neither is left out; the
        caller decides what that means.
        """
        wanted = list(dict.fromkeys(condition_ids))
        found: dict[str, Mapping[str, Any]] = {}
        for i in range(0, len(wanted), GAMMA_BATCH):
            batch = wanted[i : i + GAMMA_BATCH]
            for closed in ("true", "false"):
                ask = [c for c in batch if c not in found]
                if not ask:
                    break
                params = [("condition_ids", c) for c in ask] + [
                    ("closed", closed),
                    ("include_tag", "true"),
                    ("limit", str(len(ask))),
                ]
                document = self._get_json(f"{GAMMA_API}/markets", params)
                if not isinstance(document, list):
                    raise _unreadable("Gamma /markets", "expected a list")
                for raw in document:
                    market = _parse(_market, raw, "Gamma /markets")
                    if market.condition_id in ask:
                        found[market.condition_id] = raw
        return tuple(found[c] for c in wanted if c in found)

    # The Scan funnel's two reads (Story 4.2) ----------------------------------------------------

    def market_holders(
        self,
        condition_id: str,
        status: str,
        *,
        row_cap: int = MARKET_ROW_CAP,
        limit: int = PAGE_LIMIT,
    ) -> Read[MarketHolder]:
        """One of a Market's positions lists, CLOSED or OPEN: the Wallets that hold or held it (AD-9, AD-21).

        It takes no sort argument: every page sends `sort_by=TIMESTAMP&sort_direction=ASC` (AD-9),
        because the route's default order is by profit, and a capped read would then keep the winners.

        A read that reaches `row_cap` rows is partial, even when nothing was left to read. A read
        whose every try timed out comes back partial and empty instead of raising, so the Scan goes
        on without that Market (AD-9); any other `PolymarketUnavailable` is raised.
        """
        if not isinstance(condition_id, str) or not _CONDITION.fullmatch(condition_id):
            raise ValueError(f"not a lower-case condition id: {condition_id!r}")
        if status not in LIST_STATUSES:
            raise ValueError(f"status must be CLOSED or OPEN, not {status!r}")
        params = [("condition", condition_id), ("status", status), *MARKET_SORT]
        try:
            read = self._walk(
                f"{DATA_API}/v2/positions", params, limit, lambda raw: _market_holder(raw, condition_id, status),
                row_cap=row_cap,
            )
        except _PageTimedOut:
            log.warning("Polymarket kept timing out on the %s list of Market %s; the read is partial", status, condition_id)
            return Read((), False)
        if read.complete and len(read.rows) >= row_cap:
            log.info("the %s list of Market %s reached the cap of %d rows; the read is partial", status, condition_id, row_cap)
            return Read(read.rows, False)
        return read

    def funnel_markets(self, closed_from: int, closed_until: int, count: int) -> tuple[FunnelMarket, ...]:
        """The Market set: up to `count` resolved Markets whose `closed_time` is in [closed_from, closed_until),
        the highest volume first (AD-7, AD-21).

        Gamma's closed Markets are asked for in volume order, `GAMMA_LIST_PAGE` at a time by offset.
        Gamma filters on the scheduled end date, not on `closedTime`, so that range is widened by
        120 days before and 400 days after; a Market whose end date lies outside it is missed. A
        Market that is not resolved (AD-7) or resolved outside the window is passed over and the next
        by volume taken: volume decides the order, outcomes are never looked at. The walk stops at
        `count`, at an empty page or after `GAMMA_LIST_PAGES` pages, so fewer may come back.
        """
        if count < 1:
            raise ValueError(f"count must be 1 or more, not {count}")
        if closed_from >= closed_until:
            raise ValueError("the window must end after it starts")
        fixed = [
            ("closed", "true"),
            ("order", "volumeNum"),
            ("ascending", "false"),
            ("limit", str(GAMMA_LIST_PAGE)),
            ("end_date_min", _gamma_time(closed_from - END_DATE_BEFORE)),
            ("end_date_max", _gamma_time(closed_until + END_DATE_AFTER)),
        ]
        found: dict[str, FunnelMarket] = {}
        for page_index in range(GAMMA_LIST_PAGES):
            document = self._get_json(f"{GAMMA_API}/markets", [*fixed, ("offset", str(page_index * GAMMA_LIST_PAGE))])
            if not isinstance(document, list):
                raise _unreadable("Gamma /markets", "expected a list")
            if not document:
                break
            for raw in document:
                entry: FunnelMarket = _parse(_funnel_market, raw, "Gamma /markets")
                market = entry.market
                in_window = market.closed_time is not None and closed_from <= market.closed_time < closed_until
                if market.resolved and in_window:
                    found.setdefault(market.condition_id, entry)  # offset pages can repeat a Market
            if len(found) >= count:
                break
        ordered = sorted(found.values(), key=lambda entry: (-entry.volume, entry.market.condition_id))
        return tuple(ordered[:count])

    # Paging -----------------------------------------------------------------------------------

    def _walk(
        self,
        url: str,
        params: Sequence[tuple[str, str]],
        limit: int,
        parse: Callable[[Any], Any | None],
        *,
        until: Callable[[tuple[Any, ...]], bool] | None = None,
        row_cap: int | None = None,
    ) -> Read[Any]:
        """Walk a cursor-paged Data API list (AD-2, AD-3).

        Every page sends the same parameters apart from `cursor`. If a later page still times
        out after its 3 tries, the walk restarts once from the start with half the `limit`; if
        that also fails mid-walk, the rows read so far come back marked incomplete. A first page
        that fails raises, because nothing at all was read.

        `until(page_rows)` True stops the walk as complete; reaching `row_cap` rows stops it as
        incomplete, keeping exactly `row_cap` rows (AD-7). A restarted walk asks `until` again
        from its first page.
        """
        if limit < 1:
            raise ValueError(f"limit must be 1 or more, not {limit}")
        if row_cap is not None and row_cap < 1:
            raise ValueError(f"row_cap must be 1 or more, not {row_cap}")
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
                    page_rows: list[Any] = []
                    for raw in document["data"]:
                        record = _parse(parse, raw, what)
                        if record is not None:
                            page_rows.append(record)
                    rows.extend(page_rows)
                    paging = document.get("pagination")
                    if not isinstance(paging, dict) or not isinstance(paging.get("has_more"), bool):
                        raise _unreadable(what, "no pagination with a true or false has_more")
                    if row_cap is not None and len(rows) >= row_cap:
                        complete = len(rows) == row_cap and not paging["has_more"]
                        if not complete:
                            log.info("Polymarket %s reached the cap of %d rows", what, row_cap)
                        return Read(tuple(rows[:row_cap]), complete)
                    if not paging["has_more"] or (until is not None and self._ask_until(until, page_rows)):
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

    @staticmethod
    def _ask_until(until: Callable[[tuple[Any, ...]], bool], page_rows: list[Any]) -> bool:
        """Run `until`. A request it makes itself (the window asks Gamma there) that keeps timing
        out is an outage, never this list's page timing out, so it must not restart the walk (review, Story 2.2)."""
        try:
            return until(tuple(page_rows))
        except _PageTimedOut as error:
            raise PolymarketUnavailable(str(error)) from error

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
        last_event_at=_whole(raw, "last_event_at"),
    )


def _market_holder(raw: Mapping[str, Any], condition_id: str, status: str) -> MarketHolder:
    """A `/v2/positions?condition=…` row (AD-9). A row of another Market means the filter was dropped: unreadable."""
    if _text(raw, "condition_id") != condition_id:
        raise ValueError("a row of another Market")
    wallet = _text(raw, "proxy_wallet").lower()
    if not _WALLET.fullmatch(wallet):
        raise ValueError("proxy_wallet is not an address")
    return MarketHolder(
        wallet=wallet,
        token_id=_text(raw, "token_id"),
        status=status,
        realized_pnl=_number(raw, "realized_pnl"),
        current_size=_number(raw, "current_size"),
        avg_price=_number(raw, "avg_price"),
    )


def _funnel_market(raw: Mapping[str, Any]) -> FunnelMarket:
    """A Market of Gamma's volume-ordered list and its `volumeNum` (AD-21)."""
    return FunnelMarket(market=_market(raw), volume=_number(raw, "volumeNum"))


def _gamma_time(epoch: int) -> str:
    """Epoch seconds as the ISO text Gamma's date filters take."""
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_listed_position(raw: Mapping[str, Any], status: str) -> ListedPosition:
    """A positions-list row the Data API sent earlier, for the build-sample script (Story 2.6)."""
    return _parse(lambda row: _listed_position(row, status), raw, "a captured positions-list row")


def parse_activity_row(raw: Mapping[str, Any]) -> ActivityRow | None:
    """An activity row the Data API sent earlier, or None for a combo row (Story 2.6)."""
    return _parse(_activity_row, raw, "a captured activity row")


def parse_market(raw: Mapping[str, Any]) -> Market:
    """A Gamma Market answer stored earlier (Story 2.6)."""
    return _parse(_market, raw, "a stored Gamma Market")


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
    one is an unreadable answer, never a guess. `feesEnabled` may be absent (False). The one
    exception: an open Market Gamma has not priced yet comes without `outcomePrices` (found on
    0xd218e4, Story 2.6); it is read with no prices, since an open Market is never resolved.
    """
    closed = raw["closed"]
    fees_enabled = raw.get("feesEnabled", False)
    if not isinstance(closed, bool) or not isinstance(fees_enabled, bool):
        raise ValueError("closed or feesEnabled is not true or false")
    token_ids = _json_list(raw["clobTokenIds"], "clobTokenIds")
    unpriced = closed is False and raw.get("outcomePrices") is None  # left out (as Gamma sends it) or null
    prices = [] if unpriced else [float(p) for p in _json_list(raw["outcomePrices"], "outcomePrices")]
    if len(token_ids) < 2 or (not unpriced and len(token_ids) != len(prices)):
        raise ValueError("clobTokenIds and outcomePrices must list the same two or more outcomes")
    if not all(math.isfinite(p) for p in prices):
        raise ValueError("outcomePrices is not finite")
    fee_rate, fee_exponent = _fee_schedule(raw.get("feeSchedule"))
    return Market(
        condition_id=_text(raw, "conditionId"),
        closed=closed,
        closed_time=_optional_time(raw, "closedTime"),
        token_ids=tuple(str(t) for t in token_ids),
        outcome_prices=tuple(prices),
        fees_enabled=fees_enabled,
        start_time=_optional_time(raw, "startDate"),
        fee_rate=fee_rate,
        fee_exponent=fee_exponent,
        tags=_tag_labels(raw.get("tags")),
        event_id=_event_id(raw.get("events")),
        neg_risk_id=_neg_risk_id(raw),
    )


def _event_id(value: Any) -> str | None:
    """The Market's Gamma event (`events[0].id`, AD-20); None when Gamma lists no event."""
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("events is not a list")
    if not value:
        return None
    if not isinstance(value[0], Mapping):
        raise ValueError("an event is not an object")
    event_id = value[0].get("id")
    if event_id is None:
        return None
    if not isinstance(event_id, (str, int)) or isinstance(event_id, bool):
        raise ValueError("an event id is not text")
    return str(event_id) or None


def _neg_risk_id(raw: Mapping[str, Any]) -> str | None:
    """The negative-risk event (`negRiskMarketID`) of a Yes/No Market Gamma marks `negRisk` (AD-20).

    Only a Market whose outcomes are exactly Yes then No is coupled, so `token_ids[0]` is Yes;
    any other shape stays uncoupled and is counted in the measured share instead of guessed at.
    """
    if raw.get("negRisk") is not True:
        return None
    neg_risk_id = raw.get("negRiskMarketID")
    outcomes = raw.get("outcomes")
    tokens = _json_list(raw["clobTokenIds"], "clobTokenIds")
    if (
        not isinstance(neg_risk_id, str) or not neg_risk_id or outcomes is None
        or _json_list(outcomes, "outcomes") != ["Yes", "No"] or len(tokens) != 2
    ):
        # 108 of 108 negRisk Markets in the raw data are Yes/No (Story 2.4 review); another shape is
        # logged, not guessed at, because its CONVERSION rows would not be matched either.
        log.warning("negRisk Market %s is not a Yes/No Market with an event id; left uncoupled", raw.get("conditionId"))
        return None
    return neg_risk_id


def _optional_time(raw: Mapping[str, Any], key: str) -> int | None:
    value = raw.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{key} is not text")
    return parse_time(value) if value else None


def _fee_schedule(value: Any) -> tuple[float | None, float | None]:
    """Gamma's `feeSchedule` {rate, exponent, ...} as (rate, exponent); (None, None) when absent (AD-12)."""
    if value is None:
        return None, None
    if not isinstance(value, Mapping):
        raise ValueError("feeSchedule is not an object")
    return _number(value, "rate"), _number(value, "exponent")


def _tag_labels(value: Any) -> tuple[str, ...]:
    """The labels of the Market's event tags (`include_tag=true`), in Gamma's order; () when absent."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("tags is not a list")
    labels: list[str] = []
    for tag in value:
        if not isinstance(tag, Mapping):
            raise ValueError("a tag is not an object")
        labels.append(_text(tag, "label"))
    return tuple(labels)


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
