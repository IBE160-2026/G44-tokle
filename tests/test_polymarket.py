"""The Polymarket client: read-only, polite, typed (AD-2, AD-3, AD-17, NFR-6, NFR-11).

Everything runs on a fake transport and a fake clock, with sockets blocked. Rows are shaped like
the real capture of 2026-10-21 (spike/raw/sample/capture/, not committed).
"""

from __future__ import annotations

import ast
import logging
import threading
from pathlib import Path

import pytest
from fake_polymarket import NO_CONNECTION, TIMEOUT, FakeClock, FakeTransport, ok, page, status

from liquidoracle.data import polymarket
from liquidoracle.data.errors import PolymarketBadRequest, PolymarketUnavailable, ProtocolContractAddress
from liquidoracle.data.polymarket import (
    DATA_API,
    GAMMA_API,
    MAX_RETRY_AFTER,
    PolymarketClient,
    RateLimiter,
    check_url,
    parse_time,
)
from liquidoracle.records import ActivityRow, ListedPosition, Market

WALLET = "0x29306ddc4724e24a23bf1c8679aa034376ea9dcb"
SOURCE = Path(polymarket.__file__)


def client(transport: FakeTransport, clock: FakeClock | None = None, rate: float = 5.0) -> PolymarketClient:
    clock = clock or transport.clock or FakeClock()
    transport.clock = clock
    return PolymarketClient(rate, transport=transport, clock=clock, sleep=clock.sleep, wall_clock=lambda: 1_700_000_000.0)


def position_row(n: int, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "proxy_wallet": WALLET,
        "token_id": f"{n}0269394787426036382252331335096996451032723075155478969082890672527854496788",
        "condition_id": f"0x{n:064x}",
        "total_size": 333.3333,
        "avg_price": 0.4499,  # never used (AD-10)
        "first_entry_at": 1730151964 + n,
        "last_event_at": 1730595608 + n,
        "status": "CLOSED",
        "entry_fees_usdc": 0.0,  # never used (AD-12)
    }
    row.update(extra)
    return row


def trade_row(n: int, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "proxy_wallet": WALLET,
        "timestamp": 1751575249 + n,
        "condition_id": f"0x{n:064x}",
        "type": "TRADE",
        "size": 11190.27,
        "usdc_size": 42.43045,
        "price": 0.0037917271,
        "token_id": "55521932285795162785021453883006752950146484427600962329699824656682037578903",
        "side": "SELL",
        "outcome_index": 0,
    }
    row.update(extra)
    return row


def gamma_market(condition_id: str, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "conditionId": condition_id,
        "closed": True,
        "closedTime": "2025-04-17 08:51:19+00",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0", "1"]',
        "clobTokenIds": '["4125767081787631735", "6337766885333966690"]',
        "feesEnabled": False,
    }
    row.update(extra)
    return row


# --- AD-2: only GET, only Data API v2 and Gamma ----------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        f"{DATA_API}/positions",  # Data API v1
        f"{DATA_API}/activity",
        f"{DATA_API}/trades",
        f"{DATA_API}/v1/positions",
        "http://data-api.polymarket.com/v2/positions",  # not HTTPS
        "https://clob.polymarket.com/prices-history",  # another host (Epic 6 adds price history)
        "https://example.com/v2/positions",
        "https://data-api.polymarket.com.evil.example/v2/positions",
        f"{DATA_API}/v2/positions?user=x",  # parameters go through `params`, never the URL
    ],
)
def test_url_guard_refuses_v1_and_other_hosts(url: str) -> None:
    """AD-2, NFR-11: a v1 URL or any other host is refused before anything is sent."""
    with pytest.raises(ValueError, match="refused URL"):
        check_url(url)


def test_url_guard_runs_before_sending() -> None:
    """AD-2: a refused URL never reaches the transport."""
    transport = FakeTransport()
    with pytest.raises(ValueError):
        client(transport)._get_json(f"{DATA_API}/positions", [])
    assert transport.calls == []


@pytest.mark.parametrize("url", [f"{DATA_API}/v2/positions", f"{DATA_API}/v2/activity", f"{GAMMA_API}/markets"])
def test_url_guard_allows_v2_and_gamma(url: str) -> None:
    """AD-2: the routes the client uses pass."""
    check_url(url)


# Calls that could send something other than a GET. `get` is the only HTTP call the module makes.
NON_GET_CALLS = {"post", "put", "patch", "delete", "request", "head", "options", "send", "Request", "PreparedRequest"}


def non_get_calls(source: str) -> list[str]:
    """AD-2: names of calls in `source` that could send a non-GET request."""
    names = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
            if name in NON_GET_CALLS:
                names.append(name)
    return names


def test_client_module_only_sends_get() -> None:
    """AD-2, NFR-11: the module calls no write method of any HTTP library (a non-GET request fails here)."""
    assert non_get_calls(SOURCE.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "source",
    ["session.post(url, data=x)\n", "requests.request('POST', url)\n", "session.send(prepared)\n", "requests.Request('POST', url)\n"],
)
def test_planted_non_get_is_caught(source: str) -> None:
    """AD-2: the check above fails on a planted POST, a generic request, or a hand-built request."""
    assert non_get_calls(source) != []


def test_no_keys_and_a_generic_user_agent() -> None:
    """AD-2: requests carry no key or auth header, and nothing about the user."""
    transport = FakeTransport([page([])])
    client(transport).positions_list(WALLET, "CLOSED")
    headers = {k.lower(): v for k, v in transport.calls[0].headers.items()}
    assert "authorization" not in headers and "cookie" not in headers
    assert headers["user-agent"] == "liquidoracle/0.1 (student project)"


@pytest.mark.parametrize("wallet", ["0x29306DDC4724E24A23BF1C8679AA034376EA9DCB", "0x123", "", "29306ddc4724e24a23bf1c8679aa034376ea9dcb00"])
def test_badly_formed_wallet_is_refused(wallet: str) -> None:
    """FR-1: only a lower-case proxy-wallet address is sent."""
    transport = FakeTransport()
    with pytest.raises(ValueError):
        client(transport).positions_list(wallet, "CLOSED")
    assert transport.calls == []


# --- AD-2, AD-3: the cursor walk -------------------------------------------------------------


def test_walk_reads_every_page_with_identical_parameters() -> None:
    """AD-2: pages 2 and 3 send page 1's parameters plus `cursor`, nothing else changes."""
    transport = FakeTransport([
        page([position_row(1), position_row(2)], "c1"),
        page([position_row(3)], "c2"),
        page([position_row(4)]),
    ])
    read = client(transport).positions_list(WALLET, "CLOSED", sort_by="TIMESTAMP", sort_direction="DESC")
    assert read.complete is True
    assert [p.first_entry_at for p in read.rows] == [1730151965, 1730151966, 1730151967, 1730151968]
    first = transport.calls[0].params
    assert "cursor" not in dict(first)
    assert dict(first) == {"user": WALLET, "status": "CLOSED", "sort_by": "TIMESTAMP", "sort_direction": "DESC", "limit": "1000"}
    assert [c.without_cursor() for c in transport.calls] == [first, first, first]
    assert [c.query.get("cursor") for c in transport.calls] == [None, "c1", "c2"]
    assert all(c.url == f"{DATA_API}/v2/positions" for c in transport.calls)


def test_identical_parameter_check_catches_a_dropped_filter() -> None:
    """AD-2: the comparison used above fails when a later page loses a parameter."""
    transport = FakeTransport([page([], "c1"), page([])])
    client(transport).positions_list(WALLET, "OPEN")
    transport.calls[1].params = [p for p in transport.calls[1].params if p[0] != "status"]
    assert transport.calls[1].without_cursor() != transport.calls[0].params


def test_more_promised_without_a_cursor_is_partial() -> None:
    """AD-3: `has_more` with no new cursor is not passed off as a whole read."""
    transport = FakeTransport([page([position_row(1)], "c1"), ok({"data": [position_row(2)], "pagination": {"has_more": True}})])
    read = client(transport).positions_list(WALLET, "CLOSED")
    assert read.complete is False
    assert len(read.rows) == 2


def test_a_repeated_cursor_ends_the_walk_as_partial() -> None:
    """AD-3: a cursor seen before would loop for ever; the read stops and says it is partial."""
    transport = FakeTransport([page([position_row(1)], "c1"), page([position_row(2)], "c1")])
    read = client(transport).positions_list(WALLET, "CLOSED")
    assert read.complete is False
    assert len(transport.calls) == 2


def test_mid_walk_timeout_restarts_once_with_half_the_limit() -> None:
    """AD-3: a later page that keeps timing out restarts the walk from the start with a smaller `limit`."""
    transport = FakeTransport([
        page([position_row(1)], "c1"), TIMEOUT, TIMEOUT, TIMEOUT,  # page 2 fails 3 tries
        page([position_row(1)], "d1"), page([position_row(2)]),  # the restart reads it all
    ])
    read = client(transport).positions_list(WALLET, "CLOSED")
    assert read.complete is True
    assert [p.first_entry_at for p in read.rows] == [1730151965, 1730151966]  # no rows doubled
    limits = [c.query["limit"] for c in transport.calls]
    assert limits == ["1000", "1000", "1000", "1000", "500", "500"]
    assert transport.calls[4].query.get("cursor") is None  # restarted from the start


def test_mid_walk_timeout_twice_gives_a_partial_read() -> None:
    """AD-3: if the restarted walk also times out mid-walk, the rows read so far come back partial."""
    transport = FakeTransport([
        page([position_row(1)], "c1"), TIMEOUT, TIMEOUT, TIMEOUT,
        page([position_row(1)], "d1"), page([position_row(2)], "d2"), TIMEOUT, TIMEOUT, TIMEOUT,
    ])
    read = client(transport).positions_list(WALLET, "CLOSED")
    assert read.complete is False
    assert len(read.rows) == 2
    assert transport.script == []


def test_first_page_timeout_raises() -> None:
    """AD-3: when the first page cannot be read, nothing was read: PolymarketUnavailable."""
    transport = FakeTransport([TIMEOUT, TIMEOUT, TIMEOUT])
    with pytest.raises(PolymarketUnavailable):
        client(transport).positions_list(WALLET, "CLOSED")
    assert len(transport.calls) == 3


def test_mid_walk_503_is_not_turned_into_a_partial_read() -> None:
    """AD-3: only timeouts restart the walk; an outage mid-walk raises, so a Scan can stop and resume."""
    transport = FakeTransport([page([position_row(1)], "c1"), status(503), status(503), status(503)])
    with pytest.raises(PolymarketUnavailable):
        client(transport).positions_list(WALLET, "CLOSED")


def test_open_list_rows_keep_the_list_name() -> None:
    """AD-10, FR-3: OPEN rows that say REDEEMABLE are still the OPEN list (unredeemed losers live there)."""
    transport = FakeTransport([page([position_row(1, status="REDEEMABLE")])])
    read = client(transport).positions_list(WALLET, "OPEN")
    assert read.rows == (
        ListedPosition(
            condition_id=f"0x{1:064x}",
            token_id=position_row(1)["token_id"],
            status="OPEN",
            shares_bought=333.3333,
            first_entry_at=1730151965,
            last_event_at=1730595609,
        ),
    )


def test_unknown_list_status_is_refused() -> None:
    """AD-10: only the CLOSED and OPEN lists are read."""
    with pytest.raises(ValueError):
        client(FakeTransport()).positions_list(WALLET, "REDEEMABLE")


# --- activity rows ---------------------------------------------------------------------------


def test_activity_sends_types_start_and_limit_and_drops_combo_rows() -> None:
    """AD-10: the five types, `start` and `limit` always sent; `is_combo` rows dropped; look-alike rows kept."""
    same = trade_row(1)
    transport = FakeTransport([page([same, dict(same), trade_row(2, is_combo=True)])])
    read = client(transport).activity_rows(WALLET, start=1751328000, end=1760000000, sort_direction="DESC")
    query = transport.calls[0].query
    assert query == {
        "user": WALLET,
        "type": "TRADE,REDEEM,SPLIT,MERGE,CONVERSION",
        "start": "1751328000",
        "end": "1760000000",
        "sort_direction": "DESC",
        "limit": "1000",
    }
    assert transport.calls[0].url == f"{DATA_API}/v2/activity"
    assert len(read.rows) == 2  # identical-looking fills are separate fills, never de-duplicated
    assert read.rows[0] == ActivityRow(
        type="TRADE",
        condition_id=f"0x{1:064x}",
        timestamp=1751575250,
        size=11190.27,
        usdc_size=42.43045,
        price=0.0037917271,
        token_id=same["token_id"],
        side="SELL",
    )


def test_activity_start_zero_is_still_sent() -> None:
    """AD-10: `start` is sent explicitly even when it is 0."""
    transport = FakeTransport([page([])])
    client(transport).activity_rows(WALLET, start=0)
    assert transport.calls[0].query["start"] == "0"
    assert "end" not in transport.calls[0].query


def test_non_trade_rows_carry_no_token_or_side() -> None:
    """AD-10: only TRADE rows keep a token and a side (REDEEM rows are never a share source)."""
    rows = [trade_row(1, type=kind, side="", token_id="") for kind in ("REDEEM", "SPLIT", "MERGE", "CONVERSION")]
    rows.append(trade_row(2, type="REDEEM", token_id="123", side=""))  # 8 such rows in the capture
    read = client(FakeTransport([page(rows)])).activity_rows(WALLET, start=1)
    assert [(r.type, r.token_id, r.side) for r in read.rows] == [
        ("REDEEM", None, None), ("SPLIT", None, None), ("MERGE", None, None), ("CONVERSION", None, None), ("REDEEM", None, None)
    ]


@pytest.mark.parametrize(
    "bad",
    [
        {"timestamp": "1751575249"},
        {"size": None},
        {"size": True},
        {"condition_id": ""},
        {"token_id": None},
    ],
)
def test_malformed_row_is_an_unreadable_answer(bad: dict[str, object]) -> None:
    """AD-2, AD-3: a row not shaped as expected stops the read with PolymarketUnavailable, never a guess."""
    transport = FakeTransport([page([trade_row(1, **bad)])])
    with pytest.raises(PolymarketUnavailable, match="unreadable"):
        client(transport).activity_rows(WALLET, start=1)


@pytest.mark.parametrize("body", [b"<html>oops</html>", b'{"rows": []}', b"[]"])
def test_unreadable_page_raises(body: bytes) -> None:
    """AD-3: an answer that is not JSON, or not a page, is an unreadable answer."""
    from liquidoracle.data.polymarket import Response

    transport = FakeTransport([Response(200, {}, body)])
    with pytest.raises(PolymarketUnavailable):
        client(transport).activity_rows(WALLET, start=1)
    assert len(transport.calls) == 1


# --- Gamma Markets ---------------------------------------------------------------------------


def gamma_like(open_ids: set[str] = frozenset(), missing: set[str] = frozenset()):
    """A fake Gamma that filters on `closed` as the real one does (checked live, 2026-11-20)."""

    def answer(url: str, params: list[tuple[str, str]]):
        asked = [v for k, v in params if k == "condition_ids"]
        want_closed = dict(params).get("closed", "false") == "true"
        rows = [
            gamma_market(c, closed=False, closedTime=None, outcomePrices='["0.4", "0.6"]') if c in open_ids else gamma_market(c)
            for c in reversed(asked)  # Gamma answers in its own order
            if c not in missing and (c not in open_ids) == want_closed
        ]
        return ok(rows)

    return answer


def ids_in(call) -> list[str]:
    return [v for k, v in call.params if k == "condition_ids"]


def test_markets_in_batches_of_20_in_the_order_asked() -> None:
    """AD-7, AD-10: at most 20 ids per request, `condition_ids` repeated; order kept; missing ids skipped."""
    ids = [f"0x{i:064x}" for i in range(45)]
    missing = ids[7]
    transport = FakeTransport(answer=gamma_like(missing={missing}))
    markets = client(transport).markets([*ids, ids[3]])  # a repeat is asked once
    # closed=true for each batch; only the batch with the missing id asks again with closed=false
    assert [(len(ids_in(c)), c.query["closed"]) for c in transport.calls] == [(20, "true"), (1, "false"), (20, "true"), (5, "true")]
    assert all(c.url == f"{GAMMA_API}/markets" for c in transport.calls)
    assert all(c.query["limit"] == str(len(ids_in(c))) for c in transport.calls)
    assert [m.condition_id for m in markets] == [c for c in ids if c != missing]


def test_open_markets_are_asked_for_with_closed_false() -> None:
    """AD-4, AD-10: Gamma returns only open Markets without `closed`, so ids not found closed are asked again open."""
    ids = ["0xa", "0xb", "0xc"]
    transport = FakeTransport(answer=gamma_like(open_ids={"0xb"}))
    markets = client(transport).markets(ids)
    assert [(ids_in(c), c.query["closed"]) for c in transport.calls] == [(ids, "true"), (["0xb"], "false")]
    assert [(m.condition_id, m.closed) for m in markets] == [("0xa", True), ("0xb", False), ("0xc", True)]


def test_a_market_not_asked_for_is_ignored() -> None:
    """AD-10: only the Markets asked for come back, whatever else Gamma sends."""
    transport = FakeTransport([ok([gamma_market("0xother"), gamma_market("0xabc")])])
    assert [m.condition_id for m in client(transport).markets(["0xabc"])] == ["0xabc"]


def test_gamma_market_is_parsed() -> None:
    """AD-7: closedTime text becomes UTC epoch seconds; token ids and prices stay aligned."""
    transport = FakeTransport([ok([gamma_market("0xabc", feesEnabled=True)])])
    (market,) = client(transport).markets(["0xabc"])
    assert market == Market(
        condition_id="0xabc",
        closed=True,
        closed_time=1744879879,
        token_ids=("4125767081787631735", "6337766885333966690"),
        outcome_prices=(0.0, 1.0),
        fees_enabled=True,
    )


def test_open_gamma_market_has_no_closed_time() -> None:
    """AD-7: an open Market has no resolution time."""
    transport = FakeTransport([ok([]), ok([gamma_market("0xabc", closed=False, closedTime=None, outcomePrices='["0.4", "0.6"]')])])
    (market,) = client(transport).markets(["0xabc"])
    assert (market.closed, market.closed_time, market.outcome_prices) == (False, None, (0.4, 0.6))


def test_gamma_market_with_mismatched_outcomes_is_unreadable() -> None:
    """AD-2: token ids and prices must line up, or the answer is not trusted."""
    transport = FakeTransport([ok([gamma_market("0xabc", outcomePrices='["1"]')])])
    with pytest.raises(PolymarketUnavailable):
        client(transport).markets(["0xabc"])


def test_no_ids_no_request() -> None:
    """NFR-6: nothing to ask, nothing sent."""
    transport = FakeTransport()
    assert client(transport).markets([]) == ()
    assert transport.calls == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2025-04-17 08:51:19+00", 1744879879),
        ("2025-04-17T08:51:19Z", 1744879879),
        ("2025-04-17T08:51:19.5+00:00", 1744879879),
        ("2025-04-17T10:51:19+02", 1744879879),
        ("2025-04-17 08:51:19", 1744879879),  # no zone: UTC
    ],
)
def test_gamma_times_become_utc_epoch_seconds(text: str, expected: int) -> None:
    """AD-7, Conventions › Time: Gamma's ISO text is converted in `data/` to UTC epoch seconds."""
    assert parse_time(text) == expected


# --- AD-3: the one retry policy --------------------------------------------------------------


@pytest.mark.parametrize(
    "failure",
    [
        TIMEOUT,
        NO_CONNECTION,
        status(429),
        status(500),
        status(502),
        status(503),
        status(504),
        status(403, server="CloudFront"),
        status(403, x_amz_cf_id="abc"),
    ],
    ids=["timeout", "no-connection", "429", "500", "502", "503", "504", "403-cloudfront", "403-cf-id"],
)
def test_retried_failure_is_tried_3_times_then_unavailable(failure) -> None:
    """AD-3 (Edvard, 2026-11-20 for 500/502/504 and no connection): 3 tries in all, back-off 1 s then 2 s."""
    clock = FakeClock()
    transport = FakeTransport([failure, failure, failure], clock)
    with pytest.raises(PolymarketUnavailable):
        client(transport, clock).positions_list(WALLET, "CLOSED")
    assert len(transport.calls) == 3
    assert [round(c.at - transport.calls[0].at, 6) for c in transport.calls] == [0.0, 1.0, 3.0]


@pytest.mark.parametrize("failure", [status(503), TIMEOUT, NO_CONNECTION, status(403, b"")], ids=["503", "timeout", "no-connection", "gamma-403"])
def test_retried_failure_then_success(failure) -> None:
    """AD-3: a retried failure followed by an answer gives the answer."""
    transport = FakeTransport([failure, ok([gamma_market("0xabc")])])
    assert [m.condition_id for m in client(transport).markets(["0xabc"])] == ["0xabc"]
    assert len(transport.calls) == 2


@pytest.mark.parametrize("body", [b"", b"[]", b"{}", b"  "])
def test_empty_gamma_404_is_retried(body: bytes) -> None:
    """AD-3: Gamma answered an empty 404 on every route during an outage (2026-10-21); it is retried."""
    transport = FakeTransport([status(404, body), status(404, body), ok([gamma_market("0xabc")])])
    assert [m.condition_id for m in client(transport).markets(["0xabc"])] == ["0xabc"]
    assert len(transport.calls) == 3


def test_gamma_404_with_a_body_is_a_bad_request() -> None:
    """AD-3: only an empty Gamma 404 means an outage."""
    transport = FakeTransport([status(404, b'{"error": "not found"}')])
    with pytest.raises(PolymarketBadRequest):
        client(transport).markets(["0xabc"])
    assert len(transport.calls) == 1


@pytest.mark.parametrize("failure", [status(403), status(404)], ids=["403", "404"])
def test_data_api_403_or_404_without_cloudfront_is_a_bad_request(failure) -> None:
    """AD-3: a plain 403 or 404 from the Data API is not an outage and is not retried."""
    transport = FakeTransport([failure])
    with pytest.raises(PolymarketBadRequest) as caught:
        client(transport).positions_list(WALLET, "CLOSED")
    assert caught.value.status == failure.status
    assert len(transport.calls) == 1


def test_retry_after_is_waited_out_exactly() -> None:
    """AD-3: a `Retry-After` is waited out exactly instead of the back-off, and counts as a try."""
    clock = FakeClock()
    transport = FakeTransport([status(429, retry_after="7"), status(503, retry_after="2.5"), page([])], clock)
    read = client(transport, clock).positions_list(WALLET, "CLOSED")
    assert read.complete is True
    assert [round(c.at - transport.calls[0].at, 6) for c in transport.calls] == [0.0, 7.0, 9.5]


def test_retry_after_on_the_third_try_does_not_wait() -> None:
    """AD-3: after the third try there is no fourth, so no wait either."""
    clock = FakeClock()
    transport = FakeTransport([status(429, retry_after="7")] * 3, clock)
    with pytest.raises(PolymarketUnavailable):
        client(transport, clock).positions_list(WALLET, "CLOSED")
    assert clock.sleeps.count(7.0) == 2


@pytest.mark.parametrize("code", [429, 503])
@pytest.mark.parametrize("value", [f"{MAX_RETRY_AFTER + 1:g}", "3600", "inf", "Wed, 15 Nov 2023 00:00:00 GMT"])
def test_long_retry_after_gives_up_at_once(value: str, code: int) -> None:
    """AD-3 (Edvard, 2026-11-20): a `Retry-After` over 60 s is not waited out: PolymarketUnavailable at once."""
    clock = FakeClock()
    transport = FakeTransport([status(code, retry_after=value)], clock)
    with pytest.raises(PolymarketUnavailable, match="not waiting"):
        client(transport, clock).positions_list(WALLET, "CLOSED")
    assert len(transport.calls) == 1
    assert clock.sleeps == []


def test_retry_after_of_exactly_60_seconds_is_waited() -> None:
    """AD-3: 60 s is still waited out; only longer is refused."""
    clock = FakeClock()
    transport = FakeTransport([status(503, retry_after="60"), page([])], clock)
    client(transport, clock).positions_list(WALLET, "CLOSED")
    assert 60.0 in clock.sleeps


@pytest.mark.parametrize(("value", "wait"), [("soon", 1.0), ("Tue, 14 Nov 2023 22:13:10 GMT", 0.2), ("-5", 0.2)])
def test_unreadable_or_past_retry_after(value: str, wait: float) -> None:
    """AD-3: an unreadable `Retry-After` falls back to the back-off; a past date or negative value waits 0 s
    (so only the limiter's 0.2 s at 5 per second is left)."""
    clock = FakeClock()
    transport = FakeTransport([status(429, retry_after=value), page([])], clock)
    client(transport, clock).positions_list(WALLET, "CLOSED")
    assert round(transport.calls[1].at - transport.calls[0].at, 6) == wait


def test_other_4xx_is_a_logged_bad_request(caplog: pytest.LogCaptureFixture) -> None:
    """AD-3: any other 4xx raises PolymarketBadRequest, is logged with status and path, and is not retried."""
    transport = FakeTransport([status(400, b"a long body with details")])
    with caplog.at_level(logging.WARNING, logger="liquidoracle.data.polymarket"):
        with pytest.raises(PolymarketBadRequest) as caught:
            client(transport).positions_list(WALLET, "CLOSED")
    assert type(caught.value) is PolymarketBadRequest
    assert caught.value.status == 400
    assert len(transport.calls) == 1
    assert "/v2/positions" in caplog.text and "400" in caplog.text
    assert "long body" not in caplog.text and WALLET not in caplog.text


def test_protocol_contract_address_is_its_own_kind() -> None:
    """AD-9: a 400 "protocol contract address" is raised as its own kind, for the Scan."""
    transport = FakeTransport([status(400, b'{"error": "user is a protocol contract address"}')])
    with pytest.raises(ProtocolContractAddress) as caught:
        client(transport).positions_list(WALLET, "CLOSED")
    assert isinstance(caught.value, PolymarketBadRequest)


@pytest.mark.parametrize("code", [301, 302, 501, 204])
def test_unexpected_status_is_unavailable_without_retry(code: int) -> None:
    """AD-3: an answer that is neither data, a retried failure nor a 4xx is not usable: PolymarketUnavailable."""
    transport = FakeTransport([status(code)])
    with pytest.raises(PolymarketUnavailable):
        client(transport).positions_list(WALLET, "CLOSED")
    assert len(transport.calls) == 1


# --- AD-3, NFR-6: one locked rate limiter ----------------------------------------------------


def test_requests_are_paced_at_the_setting() -> None:
    """NFR-6: one thread's requests start at least 1/rate apart."""
    clock = FakeClock()
    transport = FakeTransport([page([], "c1"), page([], "c2"), page([])], clock)
    client(transport, clock, rate=2.0).positions_list(WALLET, "CLOSED")
    gaps = [b.at - a.at for a, b in zip(transport.calls, transport.calls[1:])]
    assert gaps == [pytest.approx(0.5), pytest.approx(0.5)]


def test_two_threads_share_one_limiter() -> None:
    """AD-3, NFR-6: two threads at once stay at or below the combined pace (fake clock)."""
    clock = FakeClock()
    transport = FakeTransport(answer=lambda url, params: page([]), clock=clock)
    shared = client(transport, clock, rate=5.0)
    # Record the start time the limiter grants each request: the fake clock moves while the
    # other thread sleeps, so the transport's own timestamp would be a little late.
    granted: list[float] = []
    limiter_wait = shared._limiter.wait

    def recording_wait() -> float:
        slot = limiter_wait()
        granted.append(slot)
        return slot

    shared._limiter.wait = recording_wait  # type: ignore[method-assign]
    start = threading.Barrier(2)

    errors: list[BaseException] = []

    def worker() -> None:
        try:
            start.wait()
            for _ in range(10):
                shared.positions_list(WALLET, "CLOSED")
        except BaseException as error:  # a thread's exception is otherwise lost
            errors.append(error)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
        assert not t.is_alive()
    assert errors == []
    assert len(transport.calls) == 20
    times = sorted(granted)
    assert len(times) == 20
    assert all(b - a >= 0.2 - 1e-9 for a, b in zip(times, times[1:]))


def test_retries_wait_their_turn_at_the_limiter() -> None:
    """AD-3: a retry is a request too and passes the limiter (back-off never shortens the pace)."""
    clock = FakeClock()
    transport = FakeTransport([status(429, retry_after="0"), page([])], clock)
    client(transport, clock, rate=1.0).positions_list(WALLET, "CLOSED")
    assert transport.calls[1].at - transport.calls[0].at >= 1.0


@pytest.mark.parametrize("rate", [0, -1, 5.01, 100])
def test_limiter_refuses_a_pace_outside_the_limit(rate: float) -> None:
    """NFR-6: the limiter never runs above 5 per second, or at 0."""
    with pytest.raises(ValueError):
        RateLimiter(rate)


def test_first_request_does_not_wait() -> None:
    """NFR-6: the limiter only spaces requests; the first one goes at once."""
    clock = FakeClock()
    assert RateLimiter(5.0, clock=clock, sleep=clock.sleep).wait() == 1000.0
    assert clock.sleeps == []


def test_limiter_alone_with_two_threads() -> None:
    """AD-3: the lock lines threads up; granted start times are at least 1/rate apart."""
    clock = FakeClock()
    limiter = RateLimiter(4.0, clock=clock, sleep=clock.sleep)
    granted: list[float] = []
    lock = threading.Lock()

    def worker() -> None:
        for _ in range(25):
            slot = limiter.wait()
            with lock:
                granted.append(slot)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
        assert not t.is_alive()
    times = sorted(granted)
    assert len(times) == 50
    assert all(b - a >= 0.25 - 1e-9 for a, b in zip(times, times[1:]))


# --- Review fixes (Story 2.1 review, 2026-11-20) ---------------------------------------------


def test_limiter_reads_the_clock_and_sleeps_only_under_its_lock() -> None:
    """AD-3, NFR-6: the next free slot is read, waited for and moved only while the lock is held.

    A fake sleep never blocks, so two threads on a fake clock almost never overlap and a race
    test could pass without the lock (Story 2.1 review). This checks the lock itself instead.
    """
    clock = FakeClock()
    held: list[bool] = []
    limiter: RateLimiter

    def watched_clock() -> float:
        held.append(limiter._lock.locked())
        return clock()

    def watched_sleep(seconds: float) -> None:
        held.append(limiter._lock.locked())
        clock.sleep(seconds)

    limiter = RateLimiter(5.0, clock=watched_clock, sleep=watched_sleep)
    for _ in range(3):
        limiter.wait()
    assert clock.sleeps == [pytest.approx(0.2), pytest.approx(0.2)]  # the sleeps happened
    assert held == [True] * 5  # 3 clock reads and 2 sleeps, all under the lock
    assert not limiter._lock.locked()


class _Reply:
    def __init__(self, status: int, headers: dict[str, str], content: bytes) -> None:
        self.status_code, self.headers, self.content = status, headers, content


def test_requests_transport_passes_timeouts_and_refuses_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-2, AD-3: the real transport sends a GET with the (5 s, 30 s) timeout, no redirects, and lower-cases headers."""
    import requests

    seen: dict[str, object] = {}

    def fake_get(self, url, **kwargs):
        seen.update(kwargs, url=url)
        return _Reply(429, {"Retry-After": "7", "Content-Type": "application/json"}, b"{}")

    monkeypatch.setattr(requests.Session, "get", fake_get)
    reply = polymarket.RequestsTransport().get(f"{DATA_API}/v2/positions", [("user", WALLET)], {"User-Agent": "x"})
    assert (reply.status, reply.headers["retry-after"], reply.body) == (429, "7", b"{}")
    assert seen["timeout"] == (polymarket.CONNECT_TIMEOUT, polymarket.READ_TIMEOUT)
    assert seen["allow_redirects"] is False
    assert seen["params"] == [("user", WALLET)]


class ReadTimeoutError(Exception):
    """Stands in for urllib3's ReadTimeoutError, which requests wraps in ConnectionError mid-body."""


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        ("ConnectTimeout", polymarket.TransportTimeout),  # both Timeout and ConnectionError
        ("ReadTimeout", polymarket.TransportTimeout),
        ("body-read-timeout", polymarket.TransportTimeout),
        ("ConnectionError", polymarket.TransportConnectionError),
        ("ChunkedEncodingError", polymarket.TransportConnectionError),
        ("ContentDecodingError", polymarket.TransportConnectionError),
    ],
)
def test_requests_transport_maps_errors(monkeypatch: pytest.MonkeyPatch, raised: str, expected: type) -> None:
    """AD-3: every requests failure becomes a timeout or a failed connection, never a raw requests error."""
    import requests

    def fake_get(self, url, **kwargs):
        if raised == "body-read-timeout":
            raise requests.ConnectionError(ReadTimeoutError("read timed out"))
        raise getattr(requests.exceptions, raised)("boom")

    monkeypatch.setattr(requests.Session, "get", fake_get)
    with pytest.raises(expected):
        polymarket.RequestsTransport().get(f"{DATA_API}/v2/positions", [], {})


def test_requests_transport_one_session_per_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-3: each thread gets its own session (a requests session is not thread-safe)."""
    import requests

    sessions: list[int] = []

    def fake_get(self, url, **kwargs):
        sessions.append(id(self))
        return _Reply(200, {}, b"{}")

    monkeypatch.setattr(requests.Session, "get", fake_get)
    transport = polymarket.RequestsTransport()
    transport.get(f"{DATA_API}/v2/positions", [], {})
    transport.get(f"{DATA_API}/v2/positions", [], {})
    other = threading.Thread(target=lambda: transport.get(f"{DATA_API}/v2/positions", [], {}))
    other.start()
    other.join(timeout=10)
    assert len(sessions) == 3 and sessions[0] == sessions[1] and sessions[2] != sessions[0]


@pytest.mark.parametrize("row", ["a string", 42, None, ["a", "list"]])
def test_a_row_that_is_not_an_object_is_unreadable(row: object) -> None:
    """AD-2, AD-3: a list element that is not an object is an unreadable answer, never a raw AttributeError."""
    with pytest.raises(PolymarketUnavailable, match="unreadable"):
        client(FakeTransport([page([row])])).activity_rows(WALLET, start=1)  # type: ignore[list-item]
    with pytest.raises(PolymarketUnavailable, match="unreadable"):
        client(FakeTransport([ok([row])])).markets(["0xabc"])


@pytest.mark.parametrize(
    "bad",
    [
        {"closedTime": 1744879879},  # a number, not text
        {"closed": None},
        {"closed": "true"},
        {"feesEnabled": "false"},
        {"clobTokenIds": None},
        {"outcomePrices": ""},
        {"clobTokenIds": '["1"]', "outcomePrices": '["1"]'},  # one outcome
        {"outcomePrices": '["NaN", "1"]'},
        {"outcomePrices": "[NaN, 1]"},
        {"startDate": 1744879879},  # a number, not text
        {"feeSchedule": "0.04"},  # not an object
        {"feeSchedule": {"rate": 0.04}},  # no exponent
        {"feeSchedule": {"rate": "0.04", "exponent": 1}},
        {"tags": "Politics"},  # not a list
        {"tags": [{"slug": "politics"}]},  # a tag without a label
    ],
)
def test_gamma_market_not_as_expected_is_unreadable(bad: dict[str, object]) -> None:
    """AD-7: closed, the outcomes and their prices decide "Resolved", so a missing or odd one is never guessed."""
    transport = FakeTransport([ok([gamma_market("0xabc", **bad)])])
    with pytest.raises(PolymarketUnavailable, match="unreadable"):
        client(transport).markets(["0xabc"])


def test_gamma_market_without_fees_enabled_has_no_fees() -> None:
    """AD-12: a Market with no `feesEnabled` key is read as fees off."""
    row = gamma_market("0xabc")
    del row["feesEnabled"]
    (market,) = client(FakeTransport([ok([row])])).markets(["0xabc"])
    assert market.fees_enabled is False


@pytest.mark.parametrize("body", [b'{"data": [], "pagination": {"has_more": NaN}}', b'{"data": [{"size": Infinity}]}'])
def test_nan_or_infinity_in_an_answer_is_unreadable(body: bytes) -> None:
    """AD-3: Python's JSON reader accepts NaN and Infinity; the client refuses them."""
    from liquidoracle.data.polymarket import Response

    with pytest.raises(PolymarketUnavailable, match="unreadable"):
        client(FakeTransport([Response(200, {}, body)])).activity_rows(WALLET, start=1)


@pytest.mark.parametrize(
    "document",
    [{"data": []}, {"data": [], "pagination": None}, {"data": [], "pagination": {"has_more": "false"}}],
)
def test_page_without_a_clear_has_more_is_unreadable(document: dict[str, object]) -> None:
    """AD-3: a page that does not say plainly whether more follows is not taken as the last page."""
    with pytest.raises(PolymarketUnavailable, match="unreadable"):
        client(FakeTransport([ok(document)])).positions_list(WALLET, "CLOSED")


def test_is_combo_only_when_true() -> None:
    """AD-10: only `is_combo: true` drops a row; any other value keeps it."""
    rows = [trade_row(1, is_combo=False), trade_row(2, is_combo="false"), trade_row(3, is_combo=True)]
    read = client(FakeTransport([page(rows)])).activity_rows(WALLET, start=1)
    assert [r.timestamp for r in read.rows] == [1751575250, 1751575251]


@pytest.mark.parametrize(
    "tries",
    [[TIMEOUT, TIMEOUT, status(503)], [status(503), status(503), TIMEOUT], [TIMEOUT, NO_CONNECTION, TIMEOUT]],
    ids=["ends-503", "ends-timeout", "mixed"],
)
def test_only_a_page_that_timed_out_every_try_restarts_the_walk(tries) -> None:
    """AD-3: "still timing out after 3 tries" means every try; a page with any other failure raises."""
    transport = FakeTransport([page([position_row(1)], "c1"), *tries])
    with pytest.raises(PolymarketUnavailable):
        client(transport).positions_list(WALLET, "CLOSED")
    assert transport.script == []
    assert len(transport.calls) == 4  # no restart


def test_gamma_403_without_cloudfront_fails_after_3_tries() -> None:
    """AD-3: a Gamma 403 is retried 3 times in all, then PolymarketUnavailable."""
    transport = FakeTransport([status(403), status(403), status(403)])
    with pytest.raises(PolymarketUnavailable):
        client(transport).markets(["0xabc"])
    assert len(transport.calls) == 3


# --- Story 2.2: the window's stop rule, the activity cap and Gamma's extra fields --------------


def test_until_stops_the_walk_after_the_page_it_accepts() -> None:
    """AD-7: `until` sees each page's rows; True stops the walk there, and the read counts as complete."""
    transport = FakeTransport([page([position_row(1), position_row(2)], "c1"), page([position_row(3)], "c2")])
    seen: list[int] = []

    def until(rows: tuple[ListedPosition, ...]) -> bool:
        seen.append(len(rows))
        return True

    read = client(transport).positions_list(WALLET, "CLOSED", until=until)
    assert (len(read.rows), read.complete, seen, len(transport.calls)) == (2, True, [2], 1)


def test_until_is_not_asked_about_the_last_page() -> None:
    """AD-7: a list that ends by itself never needs the stop rule."""
    transport = FakeTransport([page([position_row(1)])])
    read = client(transport).positions_list(WALLET, "CLOSED", until=lambda rows: pytest.fail("asked"))
    assert read.complete and len(read.rows) == 1


def test_row_cap_keeps_exactly_the_cap_and_marks_the_read_incomplete() -> None:
    """AD-7: on `ACTIVITY_ROW_CAP` the walk stops, keeps the first `row_cap` rows and says it is not complete."""
    transport = FakeTransport([page([trade_row(i) for i in range(3)], "c1"), page([trade_row(i) for i in range(3, 6)], "c2")])
    read = client(transport).activity_rows(WALLET, start=0, row_cap=4)
    assert [r.timestamp for r in read.rows] == [trade_row(i)["timestamp"] for i in range(4)]
    assert read.complete is False and len(transport.calls) == 2


def test_row_cap_not_reached_is_a_complete_read() -> None:
    """AD-7: a read that ends at or under the cap is whole."""
    transport = FakeTransport([page([trade_row(i) for i in range(3)])])
    read = client(transport).activity_rows(WALLET, start=0, row_cap=3)
    assert read.complete is True and len(read.rows) == 3


def test_row_cap_below_one_is_refused() -> None:
    """AD-7: a cap of no rows is a programming error, refused before any request."""
    with pytest.raises(ValueError, match="row_cap"):
        client(FakeTransport()).activity_rows(WALLET, start=0, row_cap=0)


def test_gamma_is_asked_with_include_tag() -> None:
    """AD-10: every Gamma request asks for the event tags."""
    transport = FakeTransport(answer=gamma_like())
    client(transport).markets(["0xa"])
    assert all(call.query["include_tag"] == "true" for call in transport.calls)


def test_gamma_start_fee_schedule_and_tags_are_read() -> None:
    """AD-7, AD-10, AD-12: start date, fee schedule (rate and exponent) and tag labels come from Gamma."""
    row = gamma_market(
        "0xabc",
        feesEnabled=True,
        startDate="2025-09-19T21:22:55.165261Z",
        feeSchedule={"exponent": 1, "rate": 0.04, "takerOnly": True, "rebateRate": 0.25},
        tags=[{"id": "2", "label": "Politics", "slug": "politics"}, {"id": "9", "label": "Trump"}],
    )
    (market,) = client(FakeTransport([ok([row])])).markets(["0xabc"])
    assert (market.start_time, market.fee_rate, market.fee_exponent, market.tags) == (
        1758316975, 0.04, 1.0, ("Politics", "Trump"))


def test_gamma_market_without_start_fees_or_tags() -> None:
    """AD-12: a Market with no schedule, start date or tags has None, None and none."""
    (market,) = client(FakeTransport([ok([gamma_market("0xabc", feeSchedule=None, tags=[])])])).markets(["0xabc"])
    assert (market.start_time, market.fee_rate, market.fee_exponent, market.tags) == (None, None, None, ())
