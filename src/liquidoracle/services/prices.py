"""Fetching price history for the Copy Test (FR-18c, AD-4, AD-14, AD-24).

`plan` says which price requests one token still needs for a set of buy fills, and `fetch` makes one
of them and stores its answer. One request is one unit of the Scan's Copy phase, so the worker can
run a waiting lookup between two of them (AD-5; the phase itself is Story 6.2). Prices are stored by
token, not by Scan or Wallet, so a Scan that finished before the Copy Test existed only needs its
prices fetched, never its Wallets again.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from liquidoracle.core.prices import fill_windows, inside, pack, uncovered
from liquidoracle.data.client import PriceClient
from liquidoracle.data.errors import PolymarketBadRequest
from liquidoracle.data.store import Store
from liquidoracle.records import ROUTE_REFUSED, PriceRequest

log = logging.getLogger(__name__)


def plan(store: Store, token_id: str, fill_times: Iterable[int]) -> tuple[PriceRequest, ...]:
    """The price requests still needed to cover every buy fill's window of one token, oldest first.

    A window that is already stored is not asked for again (AD-4), so a stored token gives no
    request and a resumed run goes on where it stopped.
    """
    missing = uncovered(fill_windows(fill_times), store.price_windows(token_id))
    return tuple(PriceRequest(token_id, group) for group in pack(missing))


def fetch(client: PriceClient, store: Store, request: PriceRequest) -> str:
    """Make one price request and store its answer; returns the route that answered (AD-24).

    Only the points inside the request's short windows are stored (AD-14). A request Polymarket
    refuses is stored with no points and the route `refused`, so one odd token does not end a long
    run: its buys are left out and counted, like any buy with no price (FR-18c). When Polymarket
    does not answer, `PolymarketUnavailable` goes up and nothing is stored, so a Resume asks again.
    """
    try:
        read = client.price_history(request.token_id, request.start, request.end)
    except PolymarketBadRequest as error:
        log.warning("Polymarket refused the price history of token %s (%s); stored as no price", request.token_id, error)
        store.save_prices(request.token_id, request.windows, (), ROUTE_REFUSED)
        return ROUTE_REFUSED
    store.save_prices(request.token_id, request.windows, inside(read.points, request.windows), read.route)
    return read.route
