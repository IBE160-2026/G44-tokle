"""Live smoke test of the Polymarket client (AD-2, AD-17). Never runs in CI or by default.

Run it by hand, with the network on:  uv run pytest -m online --force-enable-socket tests/online
It sends three GET requests (more if Polymarket is busy) to the public Data API, with no key.
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
