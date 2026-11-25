"""The Wallet window: the one client function `positions_near` (AD-7, AD-8).

It runs on any `WalletClient`'s three raw reads, so the live client and `OfflineClient` take the
same path (AD-13). A lookup's window is the latest `limit` Positions in resolved Markets, by
Gamma's resolution time, capped before any exclusion; then every activity row of those Markets
is read, from the earliest start to the latest resolution, up to `ACTIVITY_ROW_CAP`.

A Cut-off Date splits the Wallet in two (AD-7, Story 4.1). The *before* part is a lookup over only
the Markets resolved before the cut-off whose Positions were all first entered before it. The
*after* part is the first `limit` Positions by `first_entry_at`, in Markets resolved on or after
the cut-off whose Positions were all first entered on or after it, except that a CLOSED Position
fully closed before the cut-off does not count (Edvard, 2026-11-25); it is chosen from the positions
lists and Gamma alone, then its activity is read from the cut-off. A Market with a Position on
each side is in neither part, so the window never splits a Market (AD-20).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime

from liquidoracle.data.client import WalletClient
from liquidoracle.data.errors import NoPolymarketHistory, PolymarketUnavailable
from liquidoracle.data.polymarket import GAMMA_BATCH
from liquidoracle.records import ActivityRow, ListedPosition, Market, Window

log = logging.getLogger(__name__)

WINDOW_LIMIT = 2_000  # [ASSUMPTION] AD-8
# [ASSUMPTION] AD-7: the Sample Dataset capture's cap, about 30 s at 5 requests per second
# (Edvard, 2026-11-20, Story 2.2).
ACTIVITY_ROW_CAP = 150_000
SIDES = ("before", "after")  # AD-7: the two parts of a Cut-off Date

StoredMarkets = Callable[[Sequence[str]], Mapping[str, Market]]


def cutoff_at(day: date) -> int:
    """The Cut-off Date as 00:00 UTC on that day, in epoch seconds: the one place it is converted (AD-7).

    A `datetime` is refused, though Python counts it as a `date`: its time of day would be dropped
    without a word.
    """
    if isinstance(day, datetime) or not isinstance(day, date):
        raise TypeError(f"a Cut-off Date is a date, not {type(day).__name__}")
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


def positions_near(
    client: WalletClient,
    wallet: str,
    cutoff: date | None = None,
    side: str | None = None,
    limit: int = WINDOW_LIMIT,
    *,
    stored_markets: StoredMarkets | None = None,
    activity_row_cap: int = ACTIVITY_ROW_CAP,
) -> Window:
    """The Wallet's window and every activity row of its Markets (AD-7, AD-8).

    With no `cutoff` and `side` it is a lookup's window. With both, it is the `"before"` or
    `"after"` part of that Cut-off Date (Story 4.1); one without the other raises `ValueError`.

    `stored_markets(ids)` gives the resolved Markets already stored, which are never fetched
    again (AD-4). A positions list that cannot be read whole raises `PolymarketUnavailable`:
    a Verdict never rests on half a list. Both lists empty raises `NoPolymarketHistory` (FR-1);
    lists with no Position in the window give an empty window.
    """
    if (cutoff is None) != (side is None):
        raise ValueError("a Cut-off Date and its side come together, or not at all")
    if side is not None and side not in SIDES:
        raise ValueError(f"side must be 'before' or 'after', not {side!r}")
    cut = None if cutoff is None else cutoff_at(cutoff)
    if limit < 1:
        raise ValueError(f"limit must be 1 or more, not {limit}")
    markets = _MarketBook(client, stored_markets)
    if cut is not None and side == "after":
        return _after_part(client, wallet, cut, limit, markets, activity_row_cap)
    return _resolved_part(client, wallet, cut, side, limit, markets, activity_row_cap)


def _resolved_part(
    client: WalletClient,
    wallet: str,
    cut: int | None,
    side: str | None,
    limit: int,
    markets: _MarketBook,
    activity_row_cap: int,
) -> Window:
    """A lookup's window (`cut` None) or the before part: the latest `limit` Positions by resolution time."""
    # The before part: Markets resolved before the cut-off whose listed Positions were all first entered
    # before it, so no bet made after the date reaches it (AD-7; Edvard, 2026-11-25). The filter holds for
    # the stop rule, the candidates and so the activity range. A row first entered on or after the cut-off
    # has last_event_at >= the cut-off, so the newest-first walk reads it before it can stop.
    entered_late: set[str] = set()

    def note(rows: Iterable[ListedPosition]) -> None:
        if cut is not None:
            entered_late.update(row.condition_id for row in rows if row.first_entry_at >= cut)

    def in_part(row: ListedPosition) -> bool:
        if not markets.in_window(row):
            return False
        return cut is None or (markets.resolved_at(row) < cut and row.condition_id not in entered_late)

    # OPEN in full: it holds unredeemed losers and winners (FR-3, AD-7).
    open_list = client.positions_list(wallet, "OPEN")
    _require_whole(open_list.complete, "OPEN")
    markets.learn(row.condition_id for row in open_list.rows)
    note(open_list.rows)

    # CLOSED newest first, no `end`, until a page's oldest last event is older than the
    # limit-th latest resolution time collected (AD-7).
    seen: dict[str, ListedPosition] = {row.token_id: row for row in open_list.rows}
    stopped_early = False  # both clients ask `enough` only while more pages exist, so True means pages were left unread

    def enough(page: tuple[ListedPosition, ...]) -> bool:
        nonlocal stopped_early
        if not page:
            return False
        markets.learn(row.condition_id for row in page)
        note(page)
        for row in page:
            seen.setdefault(row.token_id, row)  # a restarted walk sends its pages again
        times = sorted((markets.resolved_at(row) for row in seen.values() if in_part(row)), reverse=True)
        stop = len(times) >= limit and min(row.last_event_at for row in page) < times[limit - 1]
        stopped_early = stopped_early or stop
        return stop

    closed_list = client.positions_list(wallet, "CLOSED", sort_by="TIMESTAMP", sort_direction="DESC", until=enough)
    _require_whole(closed_list.complete, "CLOSED")
    if not open_list.rows and not closed_list.rows:
        raise NoPolymarketHistory(f"Polymarket has no positions for {wallet}")
    markets.learn(row.condition_id for row in closed_list.rows)  # the last page never reaches `enough`
    note(closed_list.rows)

    candidates: dict[str, ListedPosition] = {}
    for row in (*open_list.rows, *closed_list.rows):
        if in_part(row):
            candidates.setdefault(row.token_id, row)  # a token on both lists is kept once, from OPEN
    chosen = _cap(
        list(candidates.values()), limit, key=lambda rows: (-markets.resolved_at(rows[0]), rows[0].condition_id)
    )
    # FR-11's window line (Story 3.3): older Positions were left out, by the cap or by the walk stopping early
    # with exactly `limit` collected (Story 3.3 review).
    capped = stopped_early or len(chosen) < len(candidates)
    if not chosen:
        return Window(wallet, limit, (), (), (), None, capped, cut, side)
    window_markets = tuple(markets.get(c) for c in sorted({row.condition_id for row in chosen}))

    # Every fill of the window: from the earliest start (or first buy, if earlier or the start is
    # unknown) to the latest resolution; no fill comes after resolution (AD-7).
    start = min(
        [m.start_time for m in window_markets if m.start_time is not None] + [row.first_entry_at for row in chosen]
    )
    end = max(markets.resolved_at(row) for row in chosen)
    return _with_activity(
        client, wallet, limit, chosen, window_markets, start, end, activity_row_cap, capped, cut, side
    )


def _after_part(
    client: WalletClient, wallet: str, cut: int, limit: int, markets: _MarketBook, activity_row_cap: int
) -> Window:
    """The after part: the first `limit` Positions by `first_entry_at`, whole Markets only (AD-7, AD-8, Story 4.1).

    The window is chosen from the positions lists and Gamma alone, before any activity is read, so a
    cap on the activity read only marks Positions "not fully read" and never changes the part.
    """
    # The lists: OPEN in full, CLOSED newest first until a page's oldest last event is before the cut-off.
    # An after-part Position has last_event_at >= first_entry_at >= the cut-off, so none is missed.
    open_list = client.positions_list(wallet, "OPEN")
    _require_whole(open_list.complete, "OPEN")

    def before_cut(page: tuple[ListedPosition, ...]) -> bool:
        return bool(page) and min(row.last_event_at for row in page) < cut

    closed_list = client.positions_list(wallet, "CLOSED", sort_by="TIMESTAMP", sort_direction="DESC", until=before_cut)
    _require_whole(closed_list.complete, "CLOSED")
    if not open_list.rows and not closed_list.rows:
        raise NoPolymarketHistory(f"Polymarket has no positions for {wallet}")

    # The rows that count: OPEN, and CLOSED with a last event on or after the cut-off. A CLOSED Position fully
    # closed before the cut-off does not make its Market mixed, so the part is the same at any page size
    # (Edvard, 2026-11-25, Story 4.1 review).
    counted: dict[str, ListedPosition] = {}
    for row in (*open_list.rows, *(row for row in closed_list.rows if row.last_event_at >= cut)):
        counted.setdefault(row.token_id, row)  # a token on both lists is kept once, from OPEN
    by_market: dict[str, list[ListedPosition]] = {}
    for row in counted.values():
        by_market.setdefault(row.condition_id, []).append(row)
    # A Market with a counted Position first entered before the cut-off is in neither part as a whole, so the
    # window never splits a Market (AD-20; Edvard, 2026-11-25). An activity read from the cut-off cannot see
    # those older buys, so `first_entry_at` decides (AD-10). Markets rank by their earliest entry, so one
    # entered by a split or conversion is in the window and the builder says why it is left out.
    entered = {
        c: min(row.first_entry_at for row in rows)
        for c, rows in by_market.items()
        if all(row.first_entry_at >= cut for row in rows)
    }
    ranked = sorted(entered, key=lambda c: (entered[c], c))
    eligible = _eligible_after(ranked, by_market, markets, cut, limit)
    chosen = _cap(eligible, limit, key=lambda rows: (entered[rows[0].condition_id], rows[0].condition_id))
    # FR-11's window line: later eligible Positions were left out. Exact, since eligible Markets are known
    # until one more than the part holds (or none is left).
    capped = len(chosen) < len(eligible)
    if not chosen:
        return Window(wallet, limit, (), (), (), None, capped, cut, "after")
    window_markets = tuple(markets.get(c) for c in sorted({row.condition_id for row in chosen}))

    # Every fill of the window from the cut-off to the latest resolution (AD-7); no stop rule.
    end = max(markets.resolved_at(row) for row in chosen)
    return _with_activity(
        client, wallet, limit, chosen, window_markets, cut, end, activity_row_cap, capped, cut, "after"
    )


def _with_activity(
    client: WalletClient,
    wallet: str,
    limit: int,
    chosen: Sequence[ListedPosition],
    window_markets: tuple[Market, ...],
    start: int,
    end: int,
    activity_row_cap: int,
    capped: bool,
    cut: int | None,
    side: str | None,
) -> Window:
    """The window with its Markets' activity rows read from `start` to `end`, under the cap (AD-7, AD-11).

    On a cap, `activity_read_until` is the last row's second (or `start - 1` when none was read).
    """
    read = client.activity_rows(wallet, start=start, end=end, row_cap=activity_row_cap)
    read_until = None
    if not read.complete:
        read_until = read.rows[-1].timestamp if read.rows else start - 1
        log.info("activity of %s read only up to %d; later Positions are not fully read", wallet, read_until)
    activity = _rows_of(read.rows, window_markets)
    return Window(wallet, limit, tuple(chosen), window_markets, activity, read_until, capped, cut, side)


def _eligible_after(
    ranked: Sequence[str],
    by_market: Mapping[str, list[ListedPosition]],
    markets: _MarketBook,
    cut: int,
    limit: int,
) -> list[ListedPosition]:
    """The rows of the eligible Markets in rank order, until they pass `limit` or none is left.

    Gamma is asked in rank order, one batch at a time, so a big Wallet's whole list is never asked
    for at once. A Market is eligible when it is in the window and resolved on or after the cut-off.
    """
    eligible: list[ListedPosition] = []
    for i in range(0, len(ranked), GAMMA_BATCH):
        batch = ranked[i : i + GAMMA_BATCH]
        markets.learn(batch)
        for condition_id in batch:
            rows = by_market[condition_id]
            if markets.in_window(rows[0]) and markets.resolved_at(rows[0]) >= cut:
                eligible.extend(rows)
                if len(eligible) > limit:  # the part is full and one more eligible Market is known
                    return eligible
    return eligible


def _rows_of(rows: Iterable[ActivityRow], window_markets: Sequence[Market]) -> tuple[ActivityRow, ...]:
    """The activity rows of the window's Markets.

    A CONVERSION row names its negative-risk event, not a Market (AD-11, Story 2.4).
    """
    ids = {m.condition_id for m in window_markets}
    events = {m.neg_risk_id for m in window_markets if m.neg_risk_id is not None}
    return tuple(
        row for row in rows
        if row.condition_id in ids or (row.type == "CONVERSION" and row.condition_id in events)
    )


def _cap(
    candidates: list[ListedPosition], limit: int, *, key: Callable[[list[ListedPosition]], tuple[int, str]]
) -> list[ListedPosition]:
    """The first `limit` Positions, Market by Market in the order `key` gives their rows, whole Markets only (AD-8).

    A Market whose Positions straddle the limit-th place is left out, with everything after it,
    so the window never splits a Market (AD-20 couples its sides) and never exceeds `limit`.
    """
    by_market: dict[str, list[ListedPosition]] = {}
    for row in candidates:
        by_market.setdefault(row.condition_id, []).append(row)
    chosen: list[ListedPosition] = []
    for rows in sorted(by_market.values(), key=key):
        if len(chosen) + len(rows) > limit:
            break
        chosen.extend(rows)
    return chosen


def _require_whole(complete: bool, status: str) -> None:
    if not complete:
        raise PolymarketUnavailable(f"Polymarket's {status} positions list could not be read whole")


class _MarketBook:
    """Gamma records met so far: stored resolved ones first (AD-4), the rest fetched once each."""

    def __init__(self, client: WalletClient, stored: StoredMarkets | None) -> None:
        self._client = client
        self._stored = stored
        self._known: dict[str, Market] = {}
        self._asked: set[str] = set()

    def learn(self, condition_ids: Iterable[str]) -> None:
        wanted = [c for c in dict.fromkeys(condition_ids) if c not in self._asked]
        if not wanted:
            return
        if self._stored is not None:
            self._known.update(self._stored(wanted))
        missing = [c for c in wanted if c not in self._known]
        if missing:
            self._known.update((m.condition_id, m) for m in self._client.markets(missing))
            unknown = [c for c in missing if c not in self._known]
            if unknown:
                log.warning("Gamma has no record of %d Market(s), e.g. %s; they are outside the window", len(unknown), unknown[0])
        # Marked as asked only once Gamma has answered, so a failed request is never mistaken for an answer.
        self._asked.update(wanted)

    def get(self, condition_id: str) -> Market:
        return self._known[condition_id]

    def in_window(self, row: ListedPosition) -> bool:
        """AD-7: the window's unit is a Position in a Market Gamma calls closed, with a resolution time.

        A Market with unclear resolution is in the window; the builder leaves it out (AD-11).
        """
        market = self._known.get(row.condition_id)
        return market is not None and market.closed and market.closed_time is not None

    def resolved_at(self, row: ListedPosition) -> int:
        """The resolution time of a Position already known to be `in_window`."""
        closed_time = self._known[row.condition_id].closed_time
        if closed_time is None:
            raise ValueError(f"Market {row.condition_id} has no resolution time")
        return closed_time
