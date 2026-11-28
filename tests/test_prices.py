"""Price history for the Copy Test (Story 6.1): the pure rules, the client's route rule, the store and the
fetch service (FR-18c, AD-4, AD-14, AD-24). No socket is opened: the client talks to a fake transport."""

from __future__ import annotations

import inspect
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fake_polymarket import TIMEOUT, FakeClock, FakeTransport, ok, page, status

from liquidoracle.core.prices import AFTER_FILL, BEFORE_FILL, MAX_AGE, fill_windows, inside, pack, price_at, uncovered
from liquidoracle.data import synthetic
from liquidoracle.data.client import PriceClient
from liquidoracle.data.errors import PolymarketBadRequest, PolymarketUnavailable
from liquidoracle.data.offline import OfflineClient, sample_files
from liquidoracle.data.polymarket import (
    CLOB_API,
    CLOB_PRICES_PATH,
    DATA_API,
    ONE_MINUTE_GAP,
    ONE_MINUTE_POINTS,
    PROBE_END,
    PROBE_EVERY,
    PROBE_REQUESTS,
    PROBE_START,
    PROBE_TOKEN,
    PROBE_TRUSTED,
    PolymarketClient,
    one_minute_grain,
    route_class,
)
from liquidoracle.data.store import Store
from liquidoracle.records import (
    PRICE_REQUEST_SPAN,
    ROUTE_CLOB,
    ROUTE_REFUSED,
    ROUTE_SAMPLE,
    ROUTE_V2,
    PricePoint,
    PriceRead,
    PriceRequest,
)
from liquidoracle.services import prices as price_service

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "price-route-check.yml"
TOKEN = "7001"
T0 = 1_751_400_000  # a buy fill, 1 July 2025
DAY = 86_400
CLOB_URL = CLOB_API + CLOB_PRICES_PATH
V2_URL = f"{DATA_API}/v2/prices-history"


def points(*pairs: tuple[int, float], token: str = TOKEN) -> tuple[PricePoint, ...]:
    return tuple(PricePoint(token, t, price) for t, price in pairs)


# --- price_at (AD-24) ------------------------------------------------------------------------------


@pytest.mark.parametrize("age", [0, 30, MAX_AGE])
def test_ad24_price_at_is_the_last_point_at_or_before_t(age: int) -> None:
    """AD-24, FR-18c (matrix "Price at a time"): a point 30 seconds old, exactly at t, or exactly 2 minutes old
    is the price at t."""
    assert price_at(points((T0 - 500, 0.10), (T0 - age, 0.42)), T0) == 0.42


@pytest.mark.parametrize(
    "stored",
    [
        points((T0 - MAX_AGE - 1, 0.42)),  # 121 seconds old
        points((T0 + 1, 0.42), (T0 + 60, 0.50)),  # only later points
        points((T0 - MAX_AGE - 1, 0.42), (T0 + 1, 0.99)),  # too old before, and one a second after
        (),
    ],
    ids=["121-seconds-old", "only-later", "old-then-later", "none"],
)
def test_ad24_no_price_when_the_last_point_is_too_old_or_later(stored: tuple[PricePoint, ...]) -> None:
    """AD-24, FR-18c (matrix "Too old, or only later points"): a point 121 seconds old is no price at t, and a
    point after t is never used, however close: the follower cannot buy at a price that had not happened yet."""
    assert price_at(stored, T0) is None


def test_ad24_price_at_never_takes_a_closer_later_point() -> None:
    """AD-24: with a point 100 seconds before t and one 1 second after it, the earlier one is the price."""
    assert price_at(points((T0 - 100, 0.30), (T0 + 1, 0.90)), T0) == 0.30


# --- windows and requests (AD-14) -------------------------------------------------------------------


def test_ad14_a_fills_window_runs_from_two_minutes_before_to_32_after() -> None:
    """AD-14: one buy fill gives the window [fill - 2 min, fill + 32 min], which holds every Copy Delay's time
    (1, 5 and 30 minutes) and a point up to 2 minutes older."""
    assert (BEFORE_FILL, AFTER_FILL) == (120, 1920)
    assert fill_windows([T0]) == ((T0 - 120, T0 + 1920),)
    assert T0 + 30 * 60 + MAX_AGE <= T0 + AFTER_FILL


def test_ad14_fills_close_together_share_a_window_and_a_request() -> None:
    """AD-14 (matrix "Windows of one token"): fills 10 minutes apart merge into one window; fills 2 days apart are
    two windows in one request; fills 20 days apart need two requests."""
    near = fill_windows([T0, T0 + 600, T0])  # the same fill twice counts once
    assert near == ((T0 - 120, T0 + 600 + 1920),)
    two_days = fill_windows([T0 + 2 * DAY, T0])
    assert two_days == ((T0 - 120, T0 + 1920), (T0 + 2 * DAY - 120, T0 + 2 * DAY + 1920))
    assert pack(two_days) == (two_days,)
    far = fill_windows([T0, T0 + 20 * DAY])
    assert pack(far) == ((far[0],), (far[1],))


def test_ad14_a_window_longer_than_14_days_is_cut_into_requests() -> None:
    """AD-14 (matrix "A merged window over 14 days"): fills every 20 minutes for 15 days merge into one window of
    more than 14 days; it is cut so every request covers at most 14 days, with no second lost or asked twice."""
    fills = range(T0, T0 + 15 * DAY, 20 * 60)
    (window,) = fill_windows(fills)
    assert window[1] - window[0] > PRICE_REQUEST_SPAN
    groups = pack([window])
    assert len(groups) == 2
    assert all(group[-1][1] - group[0][0] <= PRICE_REQUEST_SPAN for group in groups)
    pieces = [piece for group in groups for piece in group]
    assert pieces[0][0] == window[0] and pieces[-1][1] == window[1]
    assert all(later[0] == earlier[1] + 1 for earlier, later in zip(pieces, pieces[1:], strict=False))


def test_ad14_a_request_never_spans_more_than_14_days() -> None:
    """AD-14: windows exactly 14 days from the first start to the last end share a request; one second more and
    the last window starts a new one."""
    first = (T0, T0 + 100)
    fits = (T0 + PRICE_REQUEST_SPAN - 50, T0 + PRICE_REQUEST_SPAN)
    over = (T0 + PRICE_REQUEST_SPAN - 50, T0 + PRICE_REQUEST_SPAN + 1)
    assert pack([first, fits]) == ((first, fits),)
    assert pack([first, over]) == ((first,), (over,))


def test_ad4_only_windows_not_completely_stored_are_asked_for() -> None:
    """AD-4 (matrix "Window already stored"): a wanted window inside the stored windows is not asked for again,
    also when two stored windows that follow each other cover it together; a partly stored one is asked whole."""
    have = [(100, 200), (201, 300), (1000, 1100)]
    assert uncovered([(150, 250)], have) == ()
    assert uncovered([(100, 300), (1000, 1100)], have) == ()
    assert uncovered([(250, 301)], have) == ((250, 301),)
    assert uncovered([(99, 150)], have) == ((99, 150),)
    assert uncovered([(500, 600), (150, 160)], have) == ((500, 600),)
    assert uncovered([(5, 6)], []) == ((5, 6),)


def test_ad14_only_points_inside_the_windows_are_kept() -> None:
    """AD-14 (matrix "Only points inside the short windows"): of a long answer, the points outside the fills'
    windows are dropped; both ends of a window count as inside."""
    windows = ((100, 200), (500, 600))
    answer = points((99, 0.1), (100, 0.2), (150, 0.3), (200, 0.4), (201, 0.5), (499, 0.6), (600, 0.7), (601, 0.8))
    assert [p.t for p in inside(answer, windows)] == [100, 150, 200, 600]


# --- the client: which route, and never a coarser grain (AD-24) -------------------------------------


def history(times: list[int], price: float = 0.5) -> dict[str, list[dict[str, float]]]:
    return {"history": [{"t": t, "p": price} for t in times]}


PROBE_OK = ok(history(list(range(PROBE_START + 6, PROBE_END, 60))))  # 60 points a minute apart, as measured


def make_client(*script: object) -> tuple[PolymarketClient, FakeTransport, FakeClock]:
    clock = FakeClock()
    transport = FakeTransport(script=list(script), clock=clock)  # type: ignore[arg-type]
    client = PolymarketClient(5.0, transport=transport, clock=clock, sleep=clock.sleep, wall_clock=lambda: 1.8e9)
    return client, transport, clock


def v2_row(t: int, price: float = 0.5, resolution: int = 60) -> dict[str, float]:
    return {"timestamp": t, "price": price, "resolution_seconds": resolution}


def test_ad24_the_old_route_is_used_while_the_checks_request_gets_one_minute_points() -> None:
    """AD-24, FR-18c (matrix "Old route answers one-minute"): the client first sends the daily check's own request;
    with one-minute points back it asks the CLOB route at fidelity 1 and returns its points, oldest first. The
    check's request is not sent again for the next token."""
    client, transport, _ = make_client(
        PROBE_OK, ok(history([T0 + 120, T0, T0 + 60], 0.25)), ok(history([T0 + 60, T0 + 120]))
    )
    read = client.price_history(TOKEN, T0, T0 + 600)
    assert read == PriceRead(points((T0, 0.25), (T0 + 60, 0.25), (T0 + 120, 0.25)), ROUTE_CLOB)
    probe, asked = transport.calls
    assert probe.url == asked.url == CLOB_URL
    assert probe.query == {
        "market": PROBE_TOKEN, "startTs": str(PROBE_START), "endTs": str(PROBE_END), "fidelity": "1",
    }
    assert asked.query == {"market": TOKEN, "startTs": str(T0), "endTs": str(T0 + 600), "fidelity": "1"}
    assert client.price_history("7002", T0, T0 + 600).route == ROUTE_CLOB
    assert len(transport.calls) == 3


def test_ad24_the_checks_request_is_sent_again_after_an_hour_of_use() -> None:
    """AD-24: an answer of 0 or 1 points proves nothing about the grain, so the check's request is repeated once
    the last one is an hour old."""
    client, transport, clock = make_client(PROBE_OK, ok(history([T0])), PROBE_OK, ok(history([])))
    assert client.price_history(TOKEN, T0, T0 + 600).points == points((T0, 0.5))  # one point: accepted
    clock.sleep(PROBE_EVERY)
    assert client.price_history(TOKEN, T0, T0 + 600) == PriceRead((), ROUTE_CLOB)
    assert [call.query["market"] for call in transport.calls] == [PROBE_TOKEN, TOKEN, PROBE_TOKEN, TOKEN]


@pytest.mark.parametrize(
    ("probe", "found"),
    [
        (ok(history([PROBE_START, PROBE_START + 1800])), "coarse"),
        (ok(history(list(range(PROBE_START, PROBE_START + 39 * 60, 60)))), "coarse"),  # 39 points: under 40
        (ok(history([])), "empty"),
        (status(404, b"<html>404 Not Found</html>"), "gone-404"),
        (status(400, b'{"error": "bad"}'), "gone-400"),
    ],
    ids=["coarse", "39-points", "empty", "gone-404", "gone-400"],
)
def test_ad24_any_other_class_sends_the_client_to_the_replacement_route(
    probe: object, found: str, caplog: pytest.LogCaptureFixture
) -> None:
    """AD-24, FR-18c (matrix "Old route coarse, empty or gone"): when the check's request does not get one-minute
    points, the replacement route is asked with `bucket_seconds=60` sent explicitly, rows coarser than one minute
    are dropped, and the class is logged. The old route is not asked for the token at all."""
    rows = [v2_row(T0, 0.4), v2_row(T0 + 60, 0.41), v2_row(T0 + 300, 0.9, resolution=300)]
    client, transport, _ = make_client(probe, page(rows))
    with caplog.at_level(logging.WARNING, logger="liquidoracle.data.polymarket"):
        read = client.price_history(TOKEN, T0, T0 + 600)
    assert read == PriceRead(points((T0, 0.4), (T0 + 60, 0.41)), ROUTE_V2)
    asked = transport.calls[1]
    assert asked.url == V2_URL
    assert asked.query == {
        "token_id": TOKEN, "start": str(T0), "end": str(T0 + 600), "bucket_seconds": "60", "limit": "10000",
    }
    assert repr(found) in caplog.text and "dropped 1 price points coarser than one minute" in caplog.text


def test_ad24_the_client_returns_to_the_old_route_when_the_check_passes_again(caplog: pytest.LogCaptureFixture) -> None:
    """AD-24: while the check's request does not get one-minute points, every token goes to the replacement route and
    the warning is logged once, not per token; an hour later the check is sent again, and when it passes the old
    route is used again."""
    coarse = ok(history([PROBE_START, PROBE_START + 1800]))
    client, transport, clock = make_client(coarse, page([]), page([]), PROBE_OK, ok(history([T0])))
    with caplog.at_level(logging.WARNING, logger="liquidoracle.data.polymarket"):
        assert client.price_history(TOKEN, T0, T0 + 600).route == ROUTE_V2
        assert client.price_history("7002", T0, T0 + 600).route == ROUTE_V2
        clock.sleep(PROBE_EVERY)
        assert client.price_history("7003", T0, T0 + 600) == PriceRead(points((T0, 0.5), token="7003"), ROUTE_CLOB)
    assert caplog.text.count("not one-minute") == 1
    assert [call.url for call in transport.calls] == [CLOB_URL, V2_URL, V2_URL, CLOB_URL, CLOB_URL]


def test_ad24_the_check_is_sent_again_after_200_price_requests() -> None:
    """AD-24: an answer of 0 or 1 points proves nothing about the grain, and a whole Copy phase can run inside one
    hour, so the check's request is also sent again after `PROBE_REQUESTS` price requests to the old route: a route
    that has turned coarse or empty is noticed within about a minute, not after every window is stored."""
    clock = FakeClock()
    probe_body, price_body = PROBE_OK, ok(history([T0]))
    transport = FakeTransport(clock=clock, answer=lambda url, params: probe_body if dict(params)["market"] == PROBE_TOKEN else price_body)
    client = PolymarketClient(5.0, transport=transport, clock=clock, sleep=clock.sleep, wall_clock=lambda: 1.8e9)
    for _ in range(PROBE_REQUESTS + 1):
        assert client.price_history(TOKEN, T0, T0 + 600).route == ROUTE_CLOB
    asked = [call.query["market"] for call in transport.calls]
    assert asked.count(PROBE_TOKEN) == 2 and asked.count(TOKEN) == PROBE_REQUESTS + 1
    assert asked[PROBE_REQUESTS + 1] == PROBE_TOKEN  # sent before price request number 201
    assert clock.now - 1000.0 < PROBE_EVERY  # by the count, not by the hour


@pytest.mark.parametrize(
    "probe",
    [
        ok([]),
        ok({"error": "moved"}),
        ok({"history": "none"}),
        ok({"history": [{"t": PROBE_START, "p": 0.5}, {"p": 0.5}]}),  # one row without a time
        ok({"history": [{"t": PROBE_START + 0.5, "p": 0.5}]}),  # a time that is not a whole second
        ok({"history": [7]}),
    ],
    ids=["a-list", "no-history", "history-not-a-list", "row-without-t", "float-t", "row-not-an-object"],
)
def test_ad24_an_unreadable_answer_to_the_check_is_not_a_class(probe: object) -> None:
    """AD-2, AD-24 (review, Story 6.1): a 200 answer to the check's request that is not a history list of rows
    with whole-second times is unreadable, like any other answer the client cannot read. It is never classed
    "empty" or "coarse", which would send an hour of tokens to a route with no old prices; the next call sends
    the check again."""
    client, transport, _ = make_client(probe, PROBE_OK, ok(history([T0])))
    with pytest.raises(PolymarketUnavailable):
        client.price_history(TOKEN, T0, T0 + 600)
    assert len(transport.calls) == 1
    assert client.price_history(TOKEN, T0, T0 + 600).route == ROUTE_CLOB


@pytest.mark.parametrize("code", [401, 403, 407, 451])
@pytest.mark.parametrize("failing", ["probe", "request", "replacement"])
def test_ad3_a_block_is_an_outage_never_a_refusal_or_a_gone_route(code: int, failing: str) -> None:
    """AD-3, AD-24 (review, Story 6.1): a 401, 403, 407 or 451 is Polymarket not letting the client in, not an
    answer about a token or a route. On the check's request, on a price request or on the replacement route it
    raises `PolymarketUnavailable`, so nothing is stored as "no price" and the job stops with Resume; it does
    not class the old route "gone" either."""
    blocked = status(code, b"<html>Access denied</html>")
    script = {
        "probe": [blocked, PROBE_OK, ok(history([T0]))],
        "request": [PROBE_OK, blocked, ok(history([T0]))],
        "replacement": [status(404), blocked, page([v2_row(T0)])],  # the check's answer (gone) is kept
    }[failing]
    client, transport, clock = make_client(*script)
    with pytest.raises(PolymarketUnavailable, match=str(code)):
        client.price_history(TOKEN, T0, T0 + 600)
    clock.sleep(PROBE_TRUSTED)
    again = client.price_history(TOKEN, T0, T0 + 600)
    assert again.points == points((T0, 0.5)) and again.route == (ROUTE_V2 if failing == "replacement" else ROUTE_CLOB)
    assert transport.script == []


def test_ad24_an_old_route_answer_that_is_coarse_is_not_used() -> None:
    """AD-24, FR-18c (matrix "Old route turns coarse mid-run"): the check's request passed earlier, but this answer's
    points are 12 hours apart. The check's request is sent again and now gets coarse points too, so the answer is
    not used; the replacement route is asked instead, and for the next token too, without asking the old route."""
    coarse = ok(history([T0, T0 + 43_200, T0 + 86_400], 0.77))
    probe_coarse = ok(history([PROBE_START, PROBE_START + 1800]))
    client, transport, clock = make_client(
        PROBE_OK, ok(history([T0])), coarse, probe_coarse, page([v2_row(T0)]), page([])
    )
    assert client.price_history("7000", T0, T0 + 600).route == ROUTE_CLOB
    clock.sleep(PROBE_TRUSTED)
    assert client.price_history(TOKEN, T0, T0 + 2 * DAY) == PriceRead(points((T0, 0.5)), ROUTE_V2)
    assert client.price_history("7002", T0, T0 + 600) == PriceRead((), ROUTE_V2)
    assert [call.url for call in transport.calls] == [CLOB_URL] * 4 + [V2_URL, V2_URL]
    assert transport.calls[3].query["market"] == PROBE_TOKEN


def test_ad24_one_thin_answer_does_not_send_the_client_off_the_old_route() -> None:
    """AD-24, FR-18c: an answer whose points are far apart makes the client send the check's request again; when
    that still gets one-minute points the route is fine, the thin answer is used, and the next token is asked of
    the old route. (Otherwise one thin token would send every later token to a route with no old prices, and
    their empty answers would be stored for good.) A second thin answer inside the next minute does not send the
    check again, so a run of thin tokens does not double its requests."""
    thin = ok(history([T0, T0 + 600], 0.2))
    client, transport, clock = make_client(PROBE_OK, ok(history([T0])), thin, PROBE_OK, thin, ok(history([T0])))
    assert client.price_history("7000", T0, T0 + 600).route == ROUTE_CLOB
    clock.sleep(PROBE_TRUSTED)
    assert client.price_history(TOKEN, T0, T0 + 600) == PriceRead(points((T0, 0.2), (T0 + 600, 0.2)), ROUTE_CLOB)
    assert client.price_history("7002", T0, T0 + 600).points == points((T0, 0.2), (T0 + 600, 0.2), token="7002")
    assert client.price_history("7003", T0, T0 + 600).route == ROUTE_CLOB
    assert [call.query["market"] for call in transport.calls] == [PROBE_TOKEN, "7000", TOKEN, PROBE_TOKEN, "7002", "7003"]


def test_ad24_the_grain_rule_is_a_median_gap_of_at_most_90_seconds() -> None:
    """AD-24: an answer is one-minute when the median gap between its points is at most 90 seconds, so a few
    missing minutes do not make it coarse; fewer than two points prove nothing and pass."""
    assert one_minute_grain([0, 60, 120, 600, 660])  # gaps 60, 60, 480, 60
    assert one_minute_grain([0, ONE_MINUTE_GAP]) and not one_minute_grain([0, ONE_MINUTE_GAP + 1])
    assert not one_minute_grain([0, 300, 600, 900])
    assert one_minute_grain([]) and one_minute_grain([5])


@pytest.mark.parametrize("code", [404, 410])
def test_ad24_a_route_gone_on_a_real_request_means_the_replacement_route(code: int) -> None:
    """AD-24 (review, Story 6.1): a 404 or 410 on a price request looks like the old route is gone, so the check's
    request is sent again. When that is refused too, the route is gone: the replacement route is asked, for this
    token and the next, and the old route is not asked again."""
    gone = status(code, b"gone")
    client, transport, clock = make_client(
        PROBE_OK, ok(history([T0])), gone, gone, page([v2_row(T0, 0.6)]), page([])
    )
    assert client.price_history("7000", T0, T0 + 600).route == ROUTE_CLOB
    clock.sleep(PROBE_TRUSTED)
    assert client.price_history(TOKEN, T0, T0 + 600) == PriceRead(points((T0, 0.6)), ROUTE_V2)
    assert client.price_history("7002", T0, T0 + 600) == PriceRead((), ROUTE_V2)
    assert [call.url for call in transport.calls] == [CLOB_URL] * 4 + [V2_URL, V2_URL]


@pytest.mark.parametrize("code", [404, 410])
def test_ad24_one_404_does_not_send_the_client_off_the_old_route(code: int) -> None:
    """AD-24 (review, Story 6.1): a 404 or 410 on one token while the check's request still gets one-minute points
    is a refusal of that request (`PolymarketBadRequest`), not the route going away: the next token is asked of
    the old route. Leaving the old route always rests on the check's own rule."""
    client, transport, clock = make_client(PROBE_OK, ok(history([T0])), status(code), PROBE_OK, ok(history([T0])))
    assert client.price_history("7000", T0, T0 + 600).route == ROUTE_CLOB
    clock.sleep(PROBE_TRUSTED)
    with pytest.raises(PolymarketBadRequest):
        client.price_history(TOKEN, T0, T0 + 600)
    assert client.price_history("7002", T0, T0 + 600).route == ROUTE_CLOB
    assert [call.query.get("market") for call in transport.calls] == [PROBE_TOKEN, "7000", TOKEN, PROBE_TOKEN, "7002"]


def test_ad24_a_refused_price_request_is_a_bad_request() -> None:
    """AD-3, AD-24 (matrix "A request Polymarket refuses"): a 400 on a price request is `PolymarketBadRequest`;
    the old route stays in use."""
    client, transport, _ = make_client(PROBE_OK, status(400, b'{"error": "bad token"}'), ok(history([T0])))
    with pytest.raises(PolymarketBadRequest):
        client.price_history(TOKEN, T0, T0 + 600)
    assert client.price_history("7002", T0, T0 + 600).route == ROUTE_CLOB
    assert len(transport.calls) == 3


@pytest.mark.parametrize("failing", ["probe", "request"])
def test_ad3_an_outage_raises_and_is_not_read_as_no_price(failing: str) -> None:
    """AD-3, AD-24 (matrix "Polymarket does not answer"): three 503 answers on the check's request or on the price
    request raise `PolymarketUnavailable`; they are never read as "route gone" or as "no price". The next call
    starts with the check's request again when that was what failed."""
    outage = [status(503)] * 3
    script = [*outage, PROBE_OK, ok(history([T0]))] if failing == "probe" else [PROBE_OK, *outage, ok(history([T0]))]
    client, transport, _ = make_client(*script)
    with pytest.raises(PolymarketUnavailable):
        client.price_history(TOKEN, T0, T0 + 600)
    assert client.price_history(TOKEN, T0, T0 + 600) == PriceRead(points((T0, 0.5)), ROUTE_CLOB)
    assert transport.script == []


def test_ad24_the_replacement_route_is_read_page_by_page_or_not_at_all() -> None:
    """AD-3, AD-24: the replacement route's pages are all read; an answer that says there is more but gives no
    way to reach it raises `PolymarketUnavailable`, so a partly read window is never stored as the whole one."""
    gone = status(404)
    client, transport, _ = make_client(gone, page([v2_row(T0)], "c1"), page([v2_row(T0 + 60)]))
    assert [p.t for p in client.price_history(TOKEN, T0, T0 + 600).points] == [T0, T0 + 60]
    assert transport.calls[2].query["cursor"] == "c1"
    broken = ok({"data": [v2_row(T0)], "pagination": {"has_more": True, "next_cursor": None}})
    client, _, _ = make_client(gone, broken)
    with pytest.raises(PolymarketUnavailable):
        client.price_history(TOKEN, T0, T0 + 600)


@pytest.mark.parametrize(
    ("answers", "error"),
    [
        ([status(400, b'{"error": "bad"}')], PolymarketBadRequest),
        ([TIMEOUT, TIMEOUT, TIMEOUT], PolymarketUnavailable),
        ([page([{"timestamp": T0, "price": 0.5}])], PolymarketUnavailable),  # no resolution_seconds
        ([page([{"timestamp": T0, "price": "0.5", "resolution_seconds": 60}])], PolymarketUnavailable),
    ],
    ids=["refused", "first-page-times-out", "row-without-resolution", "price-as-text"],
)
def test_ad24_the_replacement_routes_failures_are_typed(answers: list[object], error: type[Exception]) -> None:
    """AD-3, AD-24 (review, Story 6.1): on the replacement route a 400 is `PolymarketBadRequest`, a first page that
    keeps timing out is `PolymarketUnavailable`, and a row without its resolution or with a price that is not a
    number is an unreadable answer, never a price of unknown grain."""
    client, _, _ = make_client(status(404), *answers)
    with pytest.raises(error):
        client.price_history(TOKEN, T0, T0 + 600)


@pytest.mark.parametrize(
    "answer",
    [
        ok({"history": [{"t": T0, "p": 1.5}]}),  # not a price
        ok({"history": [{"t": "soon", "p": 0.5}]}),
        ok({"history": [{"t": T0}]}),
        ok({"prices": []}),
        ok([]),
    ],
    ids=["price-above-1", "time-not-a-number", "no-price", "no-history", "a-list"],
)
def test_ad2_an_unreadable_price_answer_is_never_guessed_at(answer: object) -> None:
    """AD-2, AD-24: a price row that is not a whole second with a price from 0 to 1, or an answer of another
    shape, is an unreadable answer (`PolymarketUnavailable`), not a price."""
    client, _, _ = make_client(PROBE_OK, answer)
    with pytest.raises(PolymarketUnavailable):
        client.price_history(TOKEN, T0, T0 + 600)


def test_ad24_points_outside_the_asked_window_are_dropped() -> None:
    """AD-24: only points inside [start, end] come back, one per second."""
    client, _, _ = make_client(PROBE_OK, ok({"history": [
        {"t": T0 - 1, "p": 0.1}, {"t": T0, "p": 0.2}, {"t": T0, "p": 0.3}, {"t": T0 + 60, "p": 0.4}, {"t": T0 + 61, "p": 0.5},
    ]}))
    assert client.price_history(TOKEN, T0, T0 + 60).points == points((T0, 0.3), (T0 + 60, 0.4))


@pytest.mark.parametrize(
    ("token", "start", "end"),
    [
        (TOKEN, T0, T0 + PRICE_REQUEST_SPAN + 1), (TOKEN, T0 + 1, T0), ("0xabc", T0, T0 + 60), ("", T0, T0 + 60),
        (TOKEN, float(T0), T0 + 60), (TOKEN, T0, str(T0 + 60)), (TOKEN, None, T0), (TOKEN, True, T0),
    ],
    ids=["over-14-days", "ends-before-start", "not-a-token", "empty-token", "float", "text", "none", "bool"],
)
def test_ad14_a_bad_price_request_is_refused_before_anything_is_sent(token: str, start: object, end: object) -> None:
    """AD-14, AD-2: a window over 14 days, a window that ends before it starts, a time that is not a whole number
    or a token id that is not a number is a bug in the caller: ValueError, and no request is sent. The offline
    client refuses the same requests, so an offline run catches such a caller too (review, Story 6.1)."""
    client, transport, _ = make_client()
    with pytest.raises(ValueError):
        client.price_history(token, start, end)  # type: ignore[arg-type]
    assert transport.calls == []
    with pytest.raises(ValueError):
        OfflineClient(()).price_history(token, start, end)  # type: ignore[arg-type]


def test_ad24_a_request_of_exactly_14_days_is_sent() -> None:
    """AD-14: the longest request, 14 days, is allowed (measured live: 19,615 points)."""
    client, transport, _ = make_client(PROBE_OK, ok(history([])))
    assert client.price_history(TOKEN, T0, T0 + PRICE_REQUEST_SPAN).points == ()
    assert len(transport.calls) == 2


def test_ad24_both_clients_are_price_clients() -> None:
    """AD-2, AD-24: the live and the offline client offer the one price function, with the same arguments as the
    `PriceClient` interface and the same return type."""
    wanted = inspect.signature(PriceClient.price_history)
    for client_type in (PolymarketClient, OfflineClient):
        found = inspect.signature(client_type.price_history)
        assert list(found.parameters) == list(wanted.parameters) == ["self", "token_id", "start", "end"]
        assert found.return_annotation == wanted.return_annotation == "PriceRead"
    assert OfflineClient(()).price_history(TOKEN, T0, T0 + PRICE_REQUEST_SPAN) == PriceRead((), ROUTE_SAMPLE)


def test_ad14_a_price_request_cannot_be_built_wrong() -> None:
    """AD-14 (review, Story 6.1): a `PriceRequest` with no window, windows out of order or overlapping, or a span
    over 14 days is refused where it is built, so a planning bug never becomes a request that stores a window as
    asked without having asked for all of it."""
    assert PriceRequest(TOKEN, ((10, 20), (21, 30))).end == 30
    for windows in [(), ((10, 20), (5, 8)), ((10, 20), (20, 30)), ((20, 10),), ((0, 10), (PRICE_REQUEST_SPAN, PRICE_REQUEST_SPAN + 1))]:
        with pytest.raises(ValueError):
            PriceRequest(TOKEN, windows)


# --- the daily route check and the client agree (AD-24) ---------------------------------------------


def workflow_script() -> str:
    """The Python inside the route check's workflow, between `<<'PY'` and `PY`."""
    text = WORKFLOW.read_text(encoding="utf-8")
    body = re.search(r"<<'PY'\n(.*?)\n\s*PY\n", text, flags=re.DOTALL)
    assert body is not None, "the workflow no longer holds its inline script"
    return textwrap.dedent(body.group(1))


def workflow_class(folder: Path, code: int, body: object) -> str:
    """Run the workflow's own script on one answer, as the workflow does, and return the class it prints."""
    (folder / "body.json").write_text(json.dumps(body), encoding="utf-8")
    (folder / "state.json").unlink(missing_ok=True)
    script = folder / "check.py"
    script.write_text(workflow_script(), encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-I", str(script), str(code)], cwd=folder, capture_output=True, text=True, timeout=60,
        env={**os.environ, "GITHUB_OUTPUT": str(folder / "output.txt")},
    )
    assert done.returncode == 0, done.stderr
    found = re.search(r"class ([\w-]+),", done.stdout)
    assert found is not None, done.stdout
    return found.group(1)


MINUTES = list(range(PROBE_START + 6, PROBE_END, 60))
ROUTE_ANSWERS = [
    (200, MINUTES, "one-minute"),
    (200, MINUTES[:ONE_MINUTE_POINTS], "one-minute"),  # exactly 40 points
    (200, MINUTES[: ONE_MINUTE_POINTS - 1], "coarse"),  # 39
    (200, [PROBE_START + i * ONE_MINUTE_GAP for i in range(45)], "one-minute"),  # gaps of exactly 90 s
    (200, [PROBE_START + i * (ONE_MINUTE_GAP + 1) for i in range(45)], "coarse"),
    (200, [PROBE_START, PROBE_START + 1800], "coarse"),
    (200, [PROBE_START], "coarse"),
    (200, [], "empty"),
    (404, [], "gone-404"),
    (400, [], "gone-400"),
    (410, [], "gone-410"),
    (403, [], "gone-403"),  # the workflow alerts; the client stops the job instead of leaving the route (a block)
    (503, [], "unreachable"),  # the workflow does not alert on these; the client retries, then stops the job
    (502, MINUTES, "unreachable"),
]


@pytest.mark.parametrize(("code", "times", "expected"), ROUTE_ANSWERS, ids=[f"{c}-{len(t)}-{e}" for c, t, e in ROUTE_ANSWERS])
def test_ad24_the_route_checks_script_and_the_client_give_the_same_class(
    tmp_path: Path, code: int, times: list[int], expected: str
) -> None:
    """AD-24, FR-18c: the daily route check's own script and the client's `route_class` give the same class for
    the same answer (the 40-point and 90-second rule), so an alert from the workflow means the client leaves the
    old route too."""
    assert route_class(code, times) == expected
    assert workflow_class(tmp_path, code, history(times)) == expected


def test_ad24_the_client_sends_the_route_checks_own_request() -> None:
    """AD-24: the client's check request is the workflow's: the same host and path, token, hour and fidelity."""
    text = WORKFLOW.read_text(encoding="utf-8")
    url = re.search(r'URL="([^"]+)"', text)
    assert url is not None
    assert url.group(1) == (
        f"{CLOB_URL}?market={PROBE_TOKEN}&startTs={PROBE_START}&endTs={PROBE_END}&fidelity=1"
    )
    assert PROBE_END - PROBE_START == 3600


# --- the store (AD-4, AD-6, AD-24) ------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    db = Store(tmp_path / "instance" / "prices.db", clock=lambda: 1_800_000_000.0)
    yield db
    db.close()


def test_ad4_stored_prices_come_back_by_token_and_time(store: Store) -> None:
    """AD-4, AD-24: an answered request is stored as its windows and points; they come back by token, oldest
    first, also for a part of the time, and another token's points never mix in."""
    store.save_prices(TOKEN, ((100, 200), (500, 600)), points((150, 0.3), (100, 0.2), (600, 0.7)), ROUTE_CLOB)
    store.save_prices("7002", ((100, 200),), points((150, 0.9), token="7002"), ROUTE_V2)
    assert store.price_windows(TOKEN) == ((100, 200), (500, 600))
    assert store.prices(TOKEN) == points((100, 0.2), (150, 0.3), (600, 0.7))
    assert store.prices(TOKEN, 150, 600) == points((150, 0.3), (600, 0.7))
    assert store.prices(TOKEN, 151, 599) == () and store.prices("7003") == ()
    assert store.prices("7002") == points((150, 0.9), token="7002")
    rows = store._connection().execute("SELECT token_id, route, fetched_at FROM price_window ORDER BY token_id, start_at")
    assert rows.fetchall() == [(TOKEN, "clob", 1_800_000_000), (TOKEN, "clob", 1_800_000_000), ("7002", "v2", 1_800_000_000)]


def test_ad4_a_window_with_no_points_is_stored_as_asked(store: Store) -> None:
    """AD-4, FR-18c: a window that came back empty is stored, so it is never asked for again."""
    store.save_prices(TOKEN, ((100, 200),), (), ROUTE_CLOB)
    assert store.price_windows(TOKEN) == ((100, 200),) and store.prices(TOKEN) == ()


def test_ad24_each_asked_window_keeps_its_own_route(store: Store) -> None:
    """AD-4, AD-24 (review, Story 6.1): a window with the same start but another end is its own row, so a later
    request never relabels an earlier answer: the old route's window keeps `clob` when a wider one is refused.
    The very same window stored again replaces its row, and a point stored twice is kept once, the newer price."""
    store.save_prices(TOKEN, ((100, 300),), points((150, 0.3)), ROUTE_CLOB)
    store.save_prices(TOKEN, ((100, 400),), (), ROUTE_REFUSED)
    store.save_prices(TOKEN, ((100, 200),), points((150, 0.31), (160, 0.4)), ROUTE_V2)
    assert store.price_windows(TOKEN) == ((100, 200), (100, 300), (100, 400))
    assert store.prices(TOKEN) == points((150, 0.31), (160, 0.4))
    routes = "SELECT end_at, route FROM price_window WHERE token_id = ? ORDER BY end_at"
    assert store._connection().execute(routes, (TOKEN,)).fetchall() == [(200, "v2"), (300, "clob"), (400, "refused")]
    store.save_prices(TOKEN, ((100, 400),), points((390, 0.9)), ROUTE_CLOB)
    assert store._connection().execute(routes, (TOKEN,)).fetchall() == [(200, "v2"), (300, "clob"), (400, "clob")]
    assert uncovered([(100, 400)], store.price_windows(TOKEN)) == ()


def test_ad24_the_price_tables_refuse_what_cannot_be_a_price(store: Store) -> None:
    """AD-6, AD-24 (review, Story 6.1): the tables themselves refuse a price outside 0 to 1, a window that ends
    before it starts and an unknown route, whoever writes the row."""
    db = store._connection()
    for sql in [
        "INSERT INTO price_point (token_id, t, price) VALUES ('1', 5, 1.5)",
        "INSERT INTO price_window (token_id, start_at, end_at, route, fetched_at) VALUES ('1', 9, 5, 'clob', 1)",
        "INSERT INTO price_window (token_id, start_at, end_at, route, fetched_at) VALUES ('1', 5, 9, 'guess', 1)",
    ]:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(sql)
    assert store.price_windows("1") == () and store.prices("1") == ()


def test_ad14_points_are_checked_against_overlapping_windows_too(store: Store) -> None:
    """AD-14: a point is inside the stored windows when any of them holds it, also when the windows overlap or one
    lies inside another; a point past the last end is refused."""
    windows = ((100, 500), (150, 160), (600, 700))
    store.save_prices(TOKEN, windows, points((170, 0.1), (500, 0.2), (600, 0.3)), ROUTE_CLOB)
    assert len(store.prices(TOKEN)) == 3
    with pytest.raises(ValueError):
        store.save_prices(TOKEN, windows, points((501, 0.1)), ROUTE_CLOB)


@pytest.mark.parametrize(
    ("windows", "stored", "route"),
    [
        (((100, 200),), points((201, 0.5)), ROUTE_CLOB),  # outside the window
        (((100, 200),), points((150, 0.5), token="7002"), ROUTE_CLOB),  # another token
        (((200, 100),), (), ROUTE_CLOB),
        ((), (), ROUTE_CLOB),
        (((100, 200),), (), "somewhere"),
    ],
    ids=["point-outside", "other-token", "backwards-window", "no-window", "unknown-route"],
)
def test_ad14_the_store_refuses_prices_that_do_not_fit_their_windows(
    store: Store, windows: tuple, stored: tuple, route: str
) -> None:
    """AD-14, AD-24: a point outside the stored windows or of another token, a window that ends before it starts,
    a request with no window, or an unknown route is refused, and nothing is stored."""
    with pytest.raises(ValueError):
        store.save_prices(TOKEN, windows, stored, route)
    assert store.price_windows(TOKEN) == () and store.prices(TOKEN) == ()


# --- the fetch service (AD-4, AD-14, AD-24) ---------------------------------------------------------


class StubPrices:
    """A price client that answers every second of minute `:00` in the asked window, or raises."""

    def __init__(self, error: Exception | None = None, route: str = ROUTE_CLOB) -> None:
        self.asked: list[tuple[str, int, int]] = []
        self.error = error
        self.route = route

    def price_history(self, token_id: str, start: int, end: int) -> PriceRead:
        self.asked.append((token_id, start, end))
        if self.error is not None:
            raise self.error
        first = start + (-start) % 60
        return PriceRead(tuple(PricePoint(token_id, t, 0.5) for t in range(first, end + 1, 60)), self.route)


def test_ad14_one_request_covers_a_tokens_fills_and_only_their_windows_are_stored(store: Store) -> None:
    """AD-14, AD-4 (matrix "Only points inside the short windows", "Window already stored"): two fills 2 days
    apart are one request over both windows; only the points inside the two short windows are stored, and the
    same fills then need no request."""
    fills = [T0, T0 + 2 * DAY]
    (request,) = price_service.plan(store, TOKEN, fills)
    assert request == PriceRequest(TOKEN, fill_windows(fills))
    assert (request.start, request.end) == (T0 - 120, T0 + 2 * DAY + 1920)
    client = StubPrices()
    assert price_service.fetch(client, store, request) == ROUTE_CLOB
    assert client.asked == [(TOKEN, T0 - 120, T0 + 2 * DAY + 1920)]
    stored = store.prices(TOKEN)
    assert len(stored) == 2 * 35  # a 34-minute window holds 35 whole minutes, both ends counted; not the 2 days between
    assert all(any(a <= p.t <= b for a, b in request.windows) for p in stored)
    assert price_service.plan(store, TOKEN, fills) == ()
    assert price_at(stored, T0 + 5 * 60) == 0.5


def test_ad4_a_new_fill_of_a_stored_token_asks_only_for_its_own_window(store: Store) -> None:
    """AD-4: with one fill's window stored, a second Wallet's fill of the same token 3 days later asks for that
    window only; prices are shared by token, not kept per Wallet or Scan."""
    for request in price_service.plan(store, TOKEN, [T0]):
        price_service.fetch(StubPrices(), store, request)
    (request,) = price_service.plan(store, TOKEN, [T0, T0 + 60, T0 + 3 * DAY])  # T0 + 60 widens the first window
    assert request.windows == ((T0 - 120, T0 + 60 + 1920), (T0 + 3 * DAY - 120, T0 + 3 * DAY + 1920))
    price_service.fetch(StubPrices(), store, request)
    assert price_service.plan(store, TOKEN, [T0, T0 + 60, T0 + 3 * DAY]) == ()


def test_ad24_a_refused_request_is_stored_as_no_price_and_the_run_goes_on(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """AD-24, FR-18c (matrix "A request Polymarket refuses"): a refused price request is stored as a window with
    no points and the route `refused`, logged, and not asked for again."""
    (request,) = price_service.plan(store, TOKEN, [T0])
    with caplog.at_level(logging.WARNING, logger="liquidoracle.services.prices"):
        assert price_service.fetch(StubPrices(PolymarketBadRequest("refused", 400)), store, request) == ROUTE_REFUSED
    assert "refused the price history of token 7001" in caplog.text
    assert store.prices(TOKEN) == () and price_service.plan(store, TOKEN, [T0]) == ()
    assert store._connection().execute("SELECT route FROM price_window").fetchall() == [("refused",)]


def test_ad3_an_outage_stores_nothing_so_a_resume_asks_again(store: Store) -> None:
    """AD-3, AD-24 (matrix "Polymarket does not answer"): when the client raises `PolymarketUnavailable`, it goes
    up to the job and nothing is stored, so the same request is planned again."""
    (request,) = price_service.plan(store, TOKEN, [T0])
    with pytest.raises(PolymarketUnavailable):
        price_service.fetch(StubPrices(PolymarketUnavailable("503")), store, request)
    assert store.price_windows(TOKEN) == () and price_service.plan(store, TOKEN, [T0]) == (request,)


def test_ad3_a_block_stores_nothing_through_the_real_client(store: Store) -> None:
    """AD-3, AD-24 (review, Story 6.1): a 403 on every price request (Polymarket blocking the client) stops the
    fetch with `PolymarketUnavailable` and stores no window, instead of storing each one as "refused, no price"."""
    client, _, _ = make_client(PROBE_OK, status(403, b"blocked"))
    (request,) = price_service.plan(store, TOKEN, [T0])
    with pytest.raises(PolymarketUnavailable):
        price_service.fetch(client, store, request)
    assert store.price_windows(TOKEN) == () and price_service.plan(store, TOKEN, [T0]) == (request,)


def test_ad4_stored_prices_make_no_request_through_the_real_client(store: Store) -> None:
    """AD-4, AD-24 (matrix "Window already stored"): through the real client on a fake transport, a token's
    prices are fetched once (the check's request and one price request); planning the same fills again sends
    nothing, and the stored points give the price 5 minutes after the buy."""
    minutes = list(range(T0 - 120, T0 + 1921, 60))
    client, transport, _ = make_client(PROBE_OK, ok(history(minutes, 0.37)))
    for request in price_service.plan(store, TOKEN, [T0]):
        assert price_service.fetch(client, store, request) == ROUTE_CLOB
    assert len(transport.calls) == 2
    assert price_service.plan(store, TOKEN, [T0]) == () and transport.script == []
    assert price_at(store.prices(TOKEN), T0 + 300) == 0.37
    assert len(store.prices(TOKEN)) == 35


# --- offline: the Sample Dataset's points (AD-14, AD-24) --------------------------------------------


@pytest.fixture(scope="module")
def sample_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    synthetic.write_small(root)
    return root


def later_buy(name: str) -> tuple[str, int, bool]:
    """The first buy from the Cut-off Date on of a stage 2 Synthetic Wallet: its token, time and whether it won."""
    wallet = next(w for w in synthetic.small_wallets() if w.name == name)
    fill = min((a for a in wallet.activity if a.side == "BUY" and a.timestamp >= synthetic.CUTOFF), key=lambda a: a.timestamp)
    market = next(m for m in wallet.markets if m.condition_id == fill.condition_id)
    assert fill.token_id is not None
    return fill.token_id, fill.timestamp, market.outcome_prices[market.token_ids.index(fill.token_id)] == 1.0


@pytest.mark.parametrize("name", ["forecaster", "speed-trader"])
def test_ad24_offline_prices_are_the_sample_datasets_points(sample_root: Path, name: str) -> None:
    """AD-14, AD-24, FR-13: offline, `price_history` serves the stored points of a Synthetic Wallet's token: one
    a minute from 2 minutes before the buy to 32 after, route `sample`. By `price_at` the forecaster's price has
    barely moved after 5 minutes while the speed trader's is already at the outcome after 1 minute."""
    token, bought_at, won = later_buy(name)
    client = OfflineClient(sample_files(sample_root))
    (window,) = fill_windows([bought_at])
    read = client.price_history(token, *window)
    assert read.route == ROUTE_SAMPLE
    assert [p.t - bought_at for p in read.points] == list(range(-120, 1921, 60))
    assert price_at(read.points, bought_at) == 0.5
    outcome = 1.0 if won else 0.0
    if name == "speed-trader":
        assert price_at(read.points, bought_at + 60) == outcome
    else:
        assert abs(price_at(read.points, bought_at + 300) - 0.5) < 0.02
        assert abs(price_at(read.points, bought_at + 1800) - 0.5) > 0.05
    assert client.price_history(token, window[0], bought_at - 61).points == read.points[:1]


def test_ad24_offline_a_token_without_stored_points_has_no_price(sample_root: Path) -> None:
    """AD-24, FR-18c: a token the Sample Dataset holds no points for gives none, as live when Polymarket has no
    price; nothing is raised, so its buys are left out and counted."""
    client = OfflineClient(sample_files(sample_root))
    assert client.price_history("123456", T0, T0 + 600) == PriceRead((), ROUTE_SAMPLE)
    with pytest.raises(ValueError):
        client.price_history("123456", T0 + 1, T0)


def test_ad14_offline_prices_go_through_the_same_plan_and_store(sample_root: Path, store: Store) -> None:
    """AD-14, AD-24: the offline client's points are fetched and stored by the same plan and fetch as live ones,
    and an in-memory Wallet's points are served too."""
    token, bought_at, _ = later_buy("forecaster")
    client = OfflineClient(sample_files(sample_root))
    for request in price_service.plan(store, token, [bought_at]):
        assert price_service.fetch(client, store, request) == ROUTE_SAMPLE
    assert len(store.prices(token)) == 35 and price_service.plan(store, token, [bought_at]) == ()
    wallet = next(w for w in synthetic.small_wallets() if w.name == "forecaster")
    assert len(OfflineClient.in_memory([wallet]).price_history(token, bought_at - 120, bought_at + 1920).points) == 35


def test_ad24_offline_prices_of_a_file_written_after_the_start_are_found(tmp_path: Path) -> None:
    """AD-24 (review, Story 6.1): like a Wallet or a Market, a token whose Sample file was written after the client
    listed the files is found on the miss, so it is not read (and then stored) as "no price"."""
    client = OfflineClient(sample_files(tmp_path), list_files=lambda: sample_files(tmp_path))
    token, bought_at, _ = later_buy("forecaster")
    assert client.price_history(token, bought_at - 120, bought_at + 1920).points == ()
    synthetic.write_small(tmp_path)
    assert len(client.price_history(token, bought_at - 120, bought_at + 1920).points) == 35


def test_ad24_offline_two_prices_for_one_second_are_an_error() -> None:
    """AD-14, AD-24 (review, Story 6.1): when two Sample Wallets hold different prices for the same token and
    second, the price would depend on the file order, so it is an error; the same price twice is fine."""
    wallet = next(w for w in synthetic.small_wallets() if w.name == "forecaster")
    token, bought_at, _ = later_buy("forecaster")
    same = replace(wallet, address="0x" + "1" * 40)
    assert len(OfflineClient.in_memory([wallet, same]).price_history(token, bought_at - 120, bought_at + 1920).points) == 35
    other = replace(same, prices=tuple(replace(p, price=0.123) for p in wallet.prices))
    with pytest.raises(ValueError, match="two prices"):
        OfflineClient.in_memory([wallet, other]).price_history(token, bought_at - 120, bought_at + 1920)
