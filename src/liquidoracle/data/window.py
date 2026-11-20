"""The Wallet window: the one client function `positions_near` (AD-7, AD-8).

It runs on any `WalletClient`'s three raw reads, so the live client and `OfflineClient` take the
same path (AD-13). A lookup's window is the latest `limit` Positions in resolved Markets, by
Gamma's resolution time, capped before any exclusion; then every activity row of those Markets
is read, from the earliest start to the latest resolution, up to `ACTIVITY_ROW_CAP`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping, Sequence

from liquidoracle.data.client import WalletClient
from liquidoracle.data.errors import PolymarketUnavailable
from liquidoracle.records import ListedPosition, Market, Window

log = logging.getLogger(__name__)

WINDOW_LIMIT = 2_000  # [ASSUMPTION] AD-8
# [ASSUMPTION] AD-7: the Sample Dataset capture's cap, about 30 s at 5 requests per second
# (Edvard, 2026-11-20, Story 2.2).
ACTIVITY_ROW_CAP = 150_000

StoredMarkets = Callable[[Sequence[str]], Mapping[str, Market]]


def positions_near(
    client: WalletClient,
    wallet: str,
    cutoff: int | None = None,
    side: str | None = None,
    limit: int = WINDOW_LIMIT,
    *,
    stored_markets: StoredMarkets | None = None,
    activity_row_cap: int = ACTIVITY_ROW_CAP,
) -> Window:
    """The Wallet's window and every activity row of its Markets (AD-7, AD-8).

    `stored_markets(ids)` gives the resolved Markets already stored, which are never fetched
    again (AD-4). A positions list that cannot be read whole raises `PolymarketUnavailable`:
    a Verdict never rests on half a list. A Cut-off Date side comes with Story 4.1.
    """
    if cutoff is not None or side is not None:
        raise NotImplementedError("the before and after parts of a Cut-off Date come with Story 4.1")
    if limit < 1:
        raise ValueError(f"limit must be 1 or more, not {limit}")
    markets = _MarketBook(client, stored_markets)

    # OPEN in full: it holds unredeemed losers and winners (FR-3, AD-7).
    open_list = client.positions_list(wallet, "OPEN")
    _require_whole(open_list.complete, "OPEN")
    markets.learn(row.condition_id for row in open_list.rows)

    # CLOSED newest first, no `end`, until a page's oldest last event is older than the
    # limit-th latest resolution time collected (AD-7).
    seen: dict[str, ListedPosition] = {row.token_id: row for row in open_list.rows}

    def enough(page: tuple[ListedPosition, ...]) -> bool:
        if not page:
            return False
        markets.learn(row.condition_id for row in page)
        for row in page:
            seen.setdefault(row.token_id, row)  # a restarted walk sends its pages again
        times = sorted((markets.resolved_at(row) for row in seen.values() if markets.in_window(row)), reverse=True)
        return len(times) >= limit and min(row.last_event_at for row in page) < times[limit - 1]

    closed_list = client.positions_list(wallet, "CLOSED", sort_by="TIMESTAMP", sort_direction="DESC", until=enough)
    _require_whole(closed_list.complete, "CLOSED")
    markets.learn(row.condition_id for row in closed_list.rows)  # the last page never reaches `enough`

    candidates: dict[str, ListedPosition] = {}
    for row in (*open_list.rows, *closed_list.rows):
        if markets.in_window(row):
            candidates.setdefault(row.token_id, row)  # a token on both lists is kept once, from OPEN
    chosen = _cap(list(candidates.values()), markets, limit)
    if not chosen:
        return Window(wallet, limit, (), (), (), None)
    window_markets = tuple(markets.get(c) for c in sorted({row.condition_id for row in chosen}))

    # Every fill of the window: from the earliest start (or first buy, if earlier or the start is
    # unknown) to the latest resolution; no fill comes after resolution (AD-7).
    start = min(
        [m.start_time for m in window_markets if m.start_time is not None] + [row.first_entry_at for row in chosen]
    )
    end = max(markets.resolved_at(row) for row in chosen)
    read = client.activity_rows(wallet, start=start, end=end, row_cap=activity_row_cap)
    read_until = None
    if not read.complete:
        read_until = read.rows[-1].timestamp if read.rows else start - 1
        log.info("activity of %s read only up to %d; later Positions are not fully read", wallet, read_until)
    ids = {m.condition_id for m in window_markets}
    activity = tuple(row for row in read.rows if row.condition_id in ids)
    return Window(wallet, limit, tuple(chosen), window_markets, activity, read_until)


def _cap(candidates: list[ListedPosition], markets: _MarketBook, limit: int) -> list[ListedPosition]:
    """The latest `limit` Positions by resolution time, whole Markets only (AD-8).

    A Market whose Positions straddle the limit-th place is left out, with everything older,
    so the window never splits a Market (AD-20 couples its sides) and never exceeds `limit`.
    """
    by_market: dict[str, list[ListedPosition]] = {}
    for row in candidates:
        by_market.setdefault(row.condition_id, []).append(row)
    order = sorted(by_market, key=lambda c: (-markets.resolved_at(by_market[c][0]), c))
    chosen: list[ListedPosition] = []
    for condition_id in order:
        rows = by_market[condition_id]
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
