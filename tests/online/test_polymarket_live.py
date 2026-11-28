"""Live smoke test of the Polymarket client (AD-2, AD-17). Never runs in CI or by default.

Run it by hand, with the network on:  uv run pytest -m online --force-enable-socket tests/online
It sends a few GET requests (more if Polymarket is busy) to the public Data API, Gamma and the price history, with no key.
"""

from __future__ import annotations

import pytest

from liquidoracle.data.polymarket import PolymarketClient
from liquidoracle.records import ListedPosition

# A real Sample Wallet (0x29306d, 23 bets; PRD FR-12, Story 2.7).
SAMPLE_WALLET = "0x29306ddc4724e24a23bf1c8679aa034376ea9dcb"


def test_first_closed_page_of_a_sample_wallet(request: pytest.FixtureRequest) -> None:
    """AD-2, AD-7, AD-17: a known Sample Wallet's first CLOSED page comes back live, newest last event first."""
    assert request.node.get_closest_marker("online") is not None  # the conftest marks this folder
    client = PolymarketClient(1.0)
    # Its whole CLOSED list fits on the first page (limit 1000), so this is one request.
    read = client.positions_list(SAMPLE_WALLET, "CLOSED", sort_by="TIMESTAMP", sort_direction="DESC")
    assert read.complete
    assert read.rows, "the Sample Wallet has closed positions"
    assert all(isinstance(row, ListedPosition) and row.status == "CLOSED" for row in read.rows)
    assert all(row.condition_id.startswith("0x") and row.shares_bought > 0 for row in read.rows)
    # AD-7: the stop rule rests on TIMESTAMP DESC meaning newest last event first.
    times = [row.last_event_at for row in read.rows]
    assert times == sorted(times, reverse=True), "CLOSED with sort_by=TIMESTAMP DESC is not newest-first"


def test_an_unused_address_has_empty_lists_not_an_error(request: pytest.FixtureRequest) -> None:
    """FR-1, Story 2.5: Data API v2 answers a random, never-used address with 200 and empty positions
    lists (checked 2026-11-21), which the app reads as "No Polymarket history found". Two requests."""
    import secrets

    assert request.node.get_closest_marker("online") is not None
    client = PolymarketClient(1.0)
    address = "0x" + secrets.token_hex(20)  # fresh each run, so nobody can have traded from it
    for status in ("OPEN", "CLOSED"):
        read = client.positions_list(address, status)
        assert read.complete and read.rows == ()


# The smallest Market of the spike's 1 July 2025 set by holders: 18 rows when the spike read it (2026-10-21).
SMALL_FUNNEL_MARKET = "0xf86d87db5976adacb2ddf74ded65011369606d8bff3b2360350566bd88df2da8"


def test_funnel_markets_and_holders_for_the_sample_cut_off(request: pytest.FixtureRequest) -> None:
    """AD-9, AD-21, Story 4.2: the Market set for 1 July 2025 is 100 resolved Markets closed in the 90 days before it,
    highest volume first, and a small Market's two holder lists read complete. About 2 to 50 Gamma requests (1 to 2
    pages in practice) and 2 Data API requests."""
    from datetime import date

    from liquidoracle.data.window import cutoff_at

    assert request.node.get_closest_marker("online") is not None
    client = PolymarketClient(2.0)
    cut = cutoff_at(date(2025, 7, 1))
    start = cut - 90 * 86_400
    found = client.funnel_markets(start, cut, 100)
    assert len(found) == 100
    assert all(m.market.resolved and start <= (m.market.closed_time or 0) < cut for m in found)
    volumes = [m.volume for m in found]
    assert volumes == sorted(volumes, reverse=True)
    assert len({m.market.condition_id for m in found}) == 100
    for status in ("CLOSED", "OPEN"):
        read = client.market_holders(SMALL_FUNNEL_MARKET, status)
        assert read.complete, f"the {status} list of a small Market did not read complete"
        assert all(row.status == status for row in read.rows)


def test_price_history_of_the_route_checks_hour(request: pytest.FixtureRequest) -> None:
    """AD-24, FR-18c, Story 6.1: the old price route still gives one-minute points for the daily check's token and
    hour (1 July 2025), and the client returns them as the `clob` route; the replacement route answers the same
    window in a shape the client can read (measured 2026-11-28: an empty list, it keeps one-minute prices for
    about a week). Three requests: the check's request, the price request, and one to the replacement route. If the first part fails, the old route has changed: see spine AD-24 and Story 6.6."""
    from liquidoracle.data.polymarket import PROBE_END, PROBE_START, PROBE_TOKEN
    from liquidoracle.records import ROUTE_CLOB

    assert request.node.get_closest_marker("online") is not None
    client = PolymarketClient(1.0)
    read = client.price_history(PROBE_TOKEN, PROBE_START, PROBE_END)
    assert read.route == ROUTE_CLOB, "the old price route no longer gives one-minute points"
    assert len(read.points) >= 40
    times = [point.t for point in read.points]
    assert times == sorted(times) and all(PROBE_START <= t <= PROBE_END for t in times)
    assert all(0.0 <= point.price <= 1.0 for point in read.points)
    replacement = client._v2_prices(PROBE_TOKEN, PROBE_START, PROBE_END)  # empty today; fine if it ever is not
    assert all(PROBE_START <= point.t <= PROBE_END for point in replacement)
