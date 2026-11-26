"""The Wallet window, `positions_near`, and the snapshot it is saved as (AD-4, AD-7, AD-8, AD-13, AD-19).

Every test reads real rows cut from the Sample Dataset capture (`tests/fixtures/cut_from_capture.py`)
through the real client and a routed fake transport; no socket is opened (AD-17).
"""

from __future__ import annotations

import importlib.util
import json
import logging
import threading
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from fake_polymarket import FakeClock, FakePolymarket, FakeTransport

from liquidoracle.core.positions import build_positions, mostly_left_out
from liquidoracle.core.skilltest import uncoupled_share
from liquidoracle.data import offline as offline_module
from liquidoracle.data import sample_json
from liquidoracle.data.errors import NoPolymarketHistory, PolymarketUnavailable
from liquidoracle.data.offline import OfflineClient
from liquidoracle.data.polymarket import GAMMA_BATCH, PolymarketClient, parse_time
from liquidoracle.data.real_sample import CUTOFF as SAMPLE_CUTOFF
from liquidoracle.data.store import Store
from liquidoracle.data.window import ACTIVITY_ROW_CAP, cutoff_at, positions_near
from liquidoracle.records import ExclusionReason, ListedPosition, Market, PositionSet, Read, SampleWallet, Window
from liquidoracle.services import fetch as fetch_module
from liquidoracle.services.fetch import fetch_wallet, stored_result

# The fixture script's key lists, so the fixture check reads the same lists the script cuts with.
_spec = importlib.util.spec_from_file_location("cut_from_capture", Path(__file__).parent / "fixtures" / "cut_from_capture.py")
assert _spec is not None and _spec.loader is not None
cut = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cut)


def live(name: str) -> tuple[PolymarketClient, FakeTransport, FakePolymarket]:
    server = FakePolymarket(name)
    clock = FakeClock()
    transport = FakeTransport(clock=clock, answer=server)
    return PolymarketClient(5.0, transport=transport, clock=clock, sleep=clock.sleep), transport, server


def every_record(client: PolymarketClient, wallet: str) -> tuple[list[ListedPosition], dict[str, Market]]:
    """Both whole lists and every Market, read without the window, to compute expectations by hand."""
    rows = [*client.positions_list(wallet, "OPEN").rows, *client.positions_list(wallet, "CLOSED").rows]
    markets = {m.condition_id: m for m in client.markets(sorted({r.condition_id for r in rows}))}
    return rows, markets


def expected_window(rows: list[ListedPosition], markets: dict[str, Market], limit: int) -> list[ListedPosition]:
    """AD-7, AD-8 by hand: Positions in closed Markets with a resolution time, one per token (OPEN first),
    newest resolution first, whole Markets while they fit under `limit`."""
    candidates: dict[str, ListedPosition] = {}
    for r in rows:
        m = markets.get(r.condition_id)
        if m is not None and m.closed and m.closed_time is not None:
            candidates.setdefault(r.token_id, r)
    order = sorted({r.condition_id for r in candidates.values()}, key=lambda c: (-(markets[c].closed_time or 0), c))
    chosen: list[ListedPosition] = []
    for c in order:
        group = [r for r in candidates.values() if r.condition_id == c]
        if len(chosen) + len(group) > limit:
            break
        chosen += group
    return chosen


def calls_to(transport: FakeTransport, path: str) -> list[dict[str, str]]:
    return [call.query for call in transport.calls if call.url.endswith(path)]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    db = Store(tmp_path / "live.db")
    yield db
    db.close()


def test_small_wallet_window_reads_each_list_once_and_covers_the_window_with_activity() -> None:
    """AD-7, AD-8, AD-10: OPEN in full, CLOSED newest first with no `end`, Gamma with tags, activity over the window."""
    client, transport, server = live("small-clean")
    window = positions_near(client, server.wallet)

    rows, markets = every_record(*live("small-clean")[:1], server.wallet)
    in_window = [r for r in rows if markets.get(r.condition_id) and markets[r.condition_id].closed
                 and markets[r.condition_id].closed_time is not None]
    assert len(in_window) == 23 and len(rows) == 24  # one Market is still open: outside the window
    assert set(window.positions) == set(in_window)
    assert window.limit == 2_000 and window.activity_read_until is None
    assert window.capped is False  # FR-11 (Story 3.3): every Position fits, so no window line

    closed = calls_to(transport, "/v2/positions")
    assert [c["status"] for c in closed] == ["OPEN", "CLOSED"]
    assert closed[1]["sort_by"] == "TIMESTAMP" and closed[1]["sort_direction"] == "DESC" and "end" not in closed[1]
    assert all(c["include_tag"] == "true" for c in calls_to(transport, "/markets"))
    (activity,) = calls_to(transport, "/v2/activity")
    window_markets = {m.condition_id: m for m in window.markets}
    starts = [m.start_time for m in window.markets] + [p.first_entry_at for p in window.positions]
    assert int(activity["start"]) == min(starts)
    assert int(activity["end"]) == max(m.closed_time for m in window.markets)
    assert activity["type"] == "TRADE,REDEEM,SPLIT,MERGE,CONVERSION" and activity["limit"]
    assert window.activity and {row.condition_id for row in window.activity} <= set(window_markets)
    assert all(m.tags for m in window.markets)  # include_tag brought the event tags


def test_the_closed_walk_stops_at_the_limit_th_resolution_time() -> None:
    """AD-7: after a CLOSED page whose oldest last event is older than the limit-th latest resolution time,
    no further page is asked for; the window is still the latest `limit` by resolution time."""
    client, transport, server = live("fees-and-open")
    server.page_size = 4
    limit = 5
    window = positions_near(client, server.wallet, limit=limit)

    # The expectation, worked out from the whole lists.
    reference, _, _ = live("fees-and-open")
    open_rows = list(reference.positions_list(server.wallet, "OPEN").rows)
    closed_rows = sorted(reference.positions_list(server.wallet, "CLOSED").rows, key=lambda r: -r.last_event_at)
    markets = {m.condition_id: m for m in reference.markets(sorted({r.condition_id for r in open_rows + closed_rows}))}

    def resolved_time(row: ListedPosition) -> int | None:
        m = markets.get(row.condition_id)
        return m.closed_time if m is not None and m.closed and m.closed_time is not None else None

    collected = [t for t in map(resolved_time, open_rows) if t is not None]
    pages = 0
    for i in range(0, len(closed_rows), 4):
        pages += 1
        chunk = closed_rows[i : i + 4]
        collected += [t for t in map(resolved_time, chunk) if t is not None]
        times = sorted(collected, reverse=True)
        if len(times) >= limit and min(r.last_event_at for r in chunk) < times[limit - 1]:
            break
    closed_calls = [c for c in calls_to(transport, "/v2/positions") if c["status"] == "CLOSED"]
    assert len(closed_calls) == pages < -(-len(closed_rows) // 4)  # stopped early
    expected = expected_window(open_rows + closed_rows[: pages * 4], markets, limit)
    assert expected and window.positions == tuple(expected)
    assert window.capped is True  # FR-11 (Story 3.3): older Positions were left out


def test_a_market_straddling_the_limit_is_left_out_whole() -> None:
    """AD-8, AD-20: when the limit-th place falls inside a Market's Positions, that whole Market is left out."""
    reference, _, server = live("fees-and-open")
    rows, markets = every_record(reference, server.wallet)
    candidates = [r for r in rows if markets.get(r.condition_id) and markets[r.condition_id].closed
                  and markets[r.condition_id].closed_time is not None]
    candidates.sort(key=lambda r: (-markets[r.condition_id].closed_time, r.condition_id))
    per_market: dict[str, int] = {}
    for r in candidates:
        per_market[r.condition_id] = per_market.get(r.condition_id, 0) + 1
    first_pair = next(i for i, r in enumerate(candidates) if per_market[r.condition_id] == 2)
    limit = first_pair + 1  # the limit-th place is the first of the pair

    client, _, _ = live("fees-and-open")
    window = positions_near(client, server.wallet, limit=limit)
    assert set(window.positions) == set(candidates[:first_pair])
    assert candidates[first_pair].condition_id not in {m.condition_id for m in window.markets}
    assert window.capped is True and len(window.positions) < limit  # FR-11: capped, though under the limit


def test_an_activity_cap_leaves_out_later_positions_as_not_fully_read(store: Store) -> None:
    """AD-7, AD-11: on the cap, exactly the Positions whose Market resolved after the last row read are
    left out as "not fully read", counted even when none of their fills was read."""
    client, transport, server = live("small-clean")
    window = positions_near(client, server.wallet, activity_row_cap=10)
    assert len(window.activity) <= 10
    (activity,) = calls_to(transport, "/v2/activity")
    every_row = sorted(
        (r for r in server.activity if int(activity["start"]) <= r["timestamp"] <= int(activity["end"])),
        key=lambda r: r["timestamp"],
    )
    assert window.activity_read_until == every_row[9]["timestamp"]
    unread = window.not_fully_read()
    closed_at = {m.condition_id: m.closed_time for m in window.markets}
    assert unread and set(unread) == {p for p in window.positions if closed_at[p.condition_id] >= window.activity_read_until}

    built = build_positions(window.activity, {m.condition_id: m for m in window.markets}, listed=window.positions,
                            not_fully_read=unread)
    assert built.excluded_counts[ExclusionReason.NOT_FULLY_READ] == len(unread)
    assert built.window_size == len(window.positions)  # nothing silently missing


def test_a_capped_fetch_is_saved_with_where_it_stopped(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-7, AD-11, AD-19 (review): a capped read goes through `fetch_wallet` into the snapshot, and the
    stored Skill Test leaves the unread Positions out."""
    monkeypatch.setattr(fetch_module, "positions_near", partial(positions_near, activity_row_cap=10))
    client, _, server = live("small-clean")
    expected = positions_near(live("small-clean")[0], server.wallet, activity_row_cap=10)
    fetch_wallet(client, store, server.wallet)
    snapshot = store.latest_snapshot(server.wallet)
    assert snapshot is not None and expected.activity_read_until is not None
    assert snapshot.activity_read_until == expected.activity_read_until
    assert set(snapshot.not_fully_read()) == set(expected.not_fully_read())
    stored = stored_result(store, server.wallet, seed=44)
    built = build_positions(expected.activity, {m.condition_id: m for m in expected.markets}, listed=expected.positions,
                            not_fully_read=expected.not_fully_read())
    assert stored is not None and stored.result.tested_count == built.tested_count
    assert stored.positions == built and stored.capped is False  # FR-11, AD-11: the honesty notes' record (Story 3.3)


class _TwoPageClient:
    """A CLOSED list of two pages; like both real clients, it asks `until` only while another page exists."""

    def __init__(self) -> None:
        def row(n: int, last_event: int) -> ListedPosition:
            return ListedPosition(f"0xm{n}", f"{n}", "CLOSED", 10.0, 100, last_event)

        self.pages = [(row(1, 1_100), row(2, 800)), (row(3, 400),)]
        self.closed_at = {"0xm1": 1_000, "0xm2": 900, "0xm3": 500}

    def positions_list(self, wallet, status, *, sort_by=None, sort_direction=None, until=None):  # noqa: ANN001, ANN201
        if status == "OPEN":
            return Read((), True)
        rows: list[ListedPosition] = []
        for i, page in enumerate(self.pages):
            rows += page
            if i + 1 < len(self.pages) and until is not None and until(page):
                break
        return Read(tuple(rows), True)

    def activity_rows(self, wallet, *, start, end=None, row_cap=None):  # noqa: ANN001, ANN201
        return Read((), True)

    def markets(self, condition_ids):  # noqa: ANN001, ANN201
        return tuple(
            Market(c, closed=True, closed_time=self.closed_at[c], token_ids=(c[3:], "x"), outcome_prices=(1.0, 0.0))
            for c in condition_ids
        )


def test_a_walk_stopped_with_exactly_the_limit_is_still_capped() -> None:
    """FR-11, AD-7 (Story 3.3 review): the CLOSED walk stops after page one with exactly `limit` Positions, none cut;
    page two's older Position was never read, so the window is capped all the same."""
    window = positions_near(_TwoPageClient(), "0xw", limit=2)
    assert {p.token_id for p in window.positions} == {"1", "2"}
    assert window.capped is True
    whole = positions_near(_TwoPageClient(), "0xw", limit=3)  # page two is read: every Position fits
    assert len(whole.positions) == 3 and whole.capped is False


def test_a_capped_window_reaches_the_stored_result(store: Store) -> None:
    """FR-11 (Story 3.3): a window cut at its limit goes through `fetch_wallet`, so the stored result knows."""
    client, _, server = live("fees-and-open")
    fetch_wallet(client, store, server.wallet, limit=5)
    stored = stored_result(store, server.wallet, seed=44)
    assert stored is not None and stored.capped is True and stored.positions.window_size <= 5


def test_the_activity_cap_is_the_sample_capture_cap() -> None:
    """AD-7 (Edvard, 2026-11-20): `ACTIVITY_ROW_CAP` is 150,000 rows, the Sample Dataset capture's cap."""
    assert ACTIVITY_ROW_CAP == 150_000


def test_an_activity_read_cut_short_by_timeouts_is_treated_as_a_cap() -> None:
    """AD-3, AD-7: activity pages that keep timing out even after the restart give a partial read, and the
    Positions resolved from the last row's second on are not fully read."""
    client, _, server = live("fees-and-open")
    server.page_size = 50
    server.timeout_from_page["ACTIVITY"] = 2
    window = positions_near(client, server.wallet)
    assert window.activity_read_until is not None
    assert window.not_fully_read()
    assert all(r.timestamp <= window.activity_read_until for r in window.activity)


def test_a_restarted_closed_walk_still_stops_at_the_right_page() -> None:
    """AD-3, AD-7 (review): a CLOSED page that times out mid-walk restarts the walk at half the limit; the
    stop rule is asked again from the first page and the window comes out the same."""
    reference, _, reference_server = live("fees-and-open")
    reference_server.page_size = 4
    expected = positions_near(reference, reference_server.wallet, limit=5)
    client, transport, busy = live("fees-and-open")
    busy.page_size = 4
    busy.timeout_from_page["CLOSED"] = 1
    busy.timeouts_left["CLOSED"] = 3  # one page's 3 tries, then Polymarket answers again
    window = positions_near(client, busy.wallet, limit=5)
    limits = [c["limit"] for c in calls_to(transport, "/v2/positions") if c["status"] == "CLOSED"]
    assert "500" in limits  # the walk restarted at half the limit
    assert window == expected


def test_a_gamma_outage_inside_the_stop_rule_is_an_outage_not_a_restart() -> None:
    """AD-3 (review): Gamma timing out while the CLOSED walk checks its stop rule raises PolymarketUnavailable;
    it never restarts the walk or drops those Markets' Positions silently."""
    client, transport, server = live("fees-and-open")
    server.page_size = 4
    server.gamma_after = 2  # the OPEN list's and the first CLOSED page's Markets are answered, then Gamma stops
    server.gamma_timeouts = 3
    with pytest.raises(PolymarketUnavailable, match="markets"):
        positions_near(client, server.wallet, limit=5)
    limits = {c["limit"] for c in calls_to(transport, "/v2/positions") if c["status"] == "CLOSED"}
    assert limits == {"1000"}  # never restarted


def test_a_token_on_both_lists_is_kept_once_from_open() -> None:
    """AD-7, AD-8 (review): a token on the OPEN and the CLOSED list counts once, as its OPEN row."""
    client, _, server = live("fees-and-open")
    moved = dict(server.lists["CLOSED"][0])
    server.lists["OPEN"] = [*server.lists["OPEN"], moved]
    window = positions_near(client, server.wallet)
    rows = [p for p in window.positions if p.token_id == moved["token_id"]]
    assert len(rows) == 1 and rows[0].status == "OPEN"


@pytest.mark.parametrize(("status", "page_size"), [("CLOSED", 10), ("OPEN", 3)])
def test_a_positions_list_that_cannot_be_read_whole_writes_no_snapshot(store: Store, status: str, page_size: int) -> None:
    """AD-3, AD-19: a list still timing out mid-walk after the restart raises PolymarketUnavailable,
    and the Wallet's previous snapshot stays."""
    client, _, server = live("fees-and-open")
    first = fetch_wallet(client, store, server.wallet)
    broken, _, broken_server = live("fees-and-open")
    broken_server.page_size = page_size
    broken_server.timeout_from_page[status] = 1
    with pytest.raises(PolymarketUnavailable, match=status):
        fetch_wallet(broken, store, server.wallet)
    snapshot = store.latest_snapshot(server.wallet)
    assert snapshot is not None and snapshot.fetch_id == first


def test_stored_resolved_markets_are_not_fetched_again(store: Store) -> None:
    """AD-4: a second fetch asks Gamma only for Markets that are not stored as resolved."""
    client, transport, server = live("fees-and-open")
    fetch_wallet(client, store, server.wallet)
    stored = {m.condition_id: m for m in store.latest_snapshot(server.wallet).markets}  # type: ignore[union-attr]
    again, again_transport, _ = live("fees-and-open")
    fetch_wallet(again, store, server.wallet)
    asked = {value for call in again_transport.calls if call.url.endswith("/markets")
             for key, value in call.params if key == "condition_ids"}
    resolved = {c for c, m in stored.items() if m.resolved}
    assert resolved and not asked & resolved
    assert asked  # the open and unclear Markets are asked again


def test_markets_only_in_activity_are_never_asked_for() -> None:
    """AD-10: the positions lists say which Positions exist; 0x091596's two activity-only ids (unknown to Gamma
    as Markets) are never asked for. The TRADE one stays outside the window (Story 2.3 counts such tokens); the
    other is a CONVERSION naming a window Market's negative-risk event, which the window keeps (AD-11, Story 2.4)."""
    client, transport, server = live("fees-and-open")
    listed = {r["condition_id"] for r in server.lists["CLOSED"] + server.lists["OPEN"]}
    only_in_activity = {r["condition_id"] for r in server.activity} - listed
    assert len(only_in_activity) == 2 and not only_in_activity & {m["conditionId"] for m in server.gamma}
    window = positions_near(client, server.wallet)
    asked = {v for c in transport.calls if c.url.endswith("/markets") for k, v in c.params if k == "condition_ids"}
    assert not only_in_activity & asked
    kept = [r for r in window.activity if r.condition_id in only_in_activity]
    assert [r.type for r in kept] == ["CONVERSION"]
    assert kept[0].condition_id in {m.neg_risk_id for m in window.markets}


def test_only_a_conversion_row_may_name_an_event() -> None:
    """AD-11 (Story 2.4): a CONVERSION names its negative-risk event; any other row type naming that id is not a row of
    the window's Markets and stays out."""
    client, _, server = live("fees-and-open")
    conversion = next(r for r in server.activity if r["type"] == "CONVERSION")
    server.activity.append({**conversion, "type": "MERGE"})
    window = positions_near(client, server.wallet)
    assert [r.type for r in window.activity if r.condition_id == conversion["condition_id"]] == ["CONVERSION"]


def test_a_listed_market_gamma_does_not_know_is_outside_the_window(caplog: pytest.LogCaptureFixture) -> None:
    """AD-7: a Market on the positions lists that Gamma returns no record of is not in the window, and it is logged."""
    client, _, server = live("small-clean")
    dropped = server.gamma.pop(0)["conditionId"]
    with caplog.at_level(logging.WARNING, logger="liquidoracle.data.window"):
        window = positions_near(client, server.wallet)
    assert dropped not in {m.condition_id for m in window.markets}
    assert dropped not in {p.condition_id for p in window.positions}
    assert "Gamma has no record of 1 Market(s)" in caplog.text


def test_identical_rows_stay_separate_fills() -> None:
    """AD-10, AD-19: rows that look the same are separate fills; every copy reaches the window."""
    client, transport, server = live("fees-and-open")
    window = positions_near(client, server.wallet)
    (activity,) = calls_to(transport, "/v2/activity")
    ids = {m.condition_id for m in window.markets}
    events = {m.neg_risk_id for m in window.markets if m.neg_risk_id}
    expected = [
        r for r in server.activity
        if (r["condition_id"] in ids or (r["type"] == "CONVERSION" and r["condition_id"] in events))
        and r.get("is_combo") is not True
        and int(activity["start"]) <= r["timestamp"] <= int(activity["end"])
    ]
    copies = Counter(json.dumps(r, sort_keys=True) for r in expected)
    assert sum(n - 1 for n in copies.values()) >= 1  # the fixture has identical rows inside the window
    assert len(window.activity) == len(expected)
    # Combo rows are dropped by the client (test_polymarket); this fixture's one combo row is in a
    # Market outside the window.
    assert any(r.get("is_combo") for r in server.activity)


def test_two_fetches_of_one_wallet_run_one_after_the_other(store: Store) -> None:
    """AD-19: while one fetch of a Wallet runs, a second waits; readers meanwhile see the previous snapshot."""
    first_client, _, server = live("small-clean")
    earlier = fetch_wallet(first_client, store, server.wallet)

    a_client, _, a_server = live("small-clean")
    b_client, b_transport, _ = live("small-clean")
    reading = threading.Event()
    release = threading.Event()

    def pause() -> None:
        reading.set()
        assert release.wait(5)

    a_server.before_activity = pause
    results: dict[str, int] = {}
    a = threading.Thread(target=lambda: results.setdefault("a", fetch_wallet(a_client, store, server.wallet)))
    b = threading.Thread(target=lambda: results.setdefault("b", fetch_wallet(b_client, store, server.wallet)))
    a.start()
    assert reading.wait(5)
    b.start()
    b.join(timeout=0.3)
    assert b.is_alive() and b_transport.calls == []  # waiting for the Wallet's lock, nothing sent
    snapshot = store.latest_snapshot(server.wallet)
    assert snapshot is not None and snapshot.fetch_id == earlier  # mid-fetch: the previous one
    release.set()
    a.join(5)
    b.join(5)
    assert results["a"] < results["b"]
    final = store.latest_snapshot(server.wallet)
    assert final is not None and final.fetch_id == results["b"]
    assert len(final.activity) == len(snapshot.activity)  # rows of one fetch, never two mixed


@pytest.mark.parametrize(("page", "limit", "cap"), [(1_000, 20, ACTIVITY_ROW_CAP), (4, 5, 10)])
def test_offline_and_live_give_the_same_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, page: int, limit: int, cap: int
) -> None:
    """AD-13, AD-14: the same records served by OfflineClient give the same window as the live client,
    also when the stop rule ends the CLOSED walk early and the activity read is capped (review)."""
    reference, _, server = live("fees-and-open")
    rows, markets = every_record(reference, server.wallet)
    activity = reference.activity_rows(server.wallet, start=0).rows
    sample = SampleWallet(server.wallet, "fixture", activity, tuple(rows), tuple(markets.values()))
    sample_json.write_wallet(tmp_path / "fixture.json", sample)

    monkeypatch.setattr(offline_module, "PAGE_LIMIT", page)
    client, _, live_server = live("fees-and-open")
    live_server.page_size = page
    offline_window = positions_near(OfflineClient([tmp_path / "fixture.json"]), server.wallet, limit=limit,
                                    activity_row_cap=cap)
    assert offline_window == positions_near(client, server.wallet, limit=limit, activity_row_cap=cap)
    assert offline_window.positions


def test_the_stored_result_leaves_out_unread_positions(store: Store) -> None:
    """AD-11, FR-11: the Skill Test on a capped snapshot counts the unread Positions as left out."""
    client, _, server = live("small-clean")
    window = positions_near(client, server.wallet, activity_row_cap=10)
    fetch_id = store.begin_snapshot(server.wallet, window_limit=window.limit)
    store.add_positions(fetch_id, window.positions)
    store.add_activity(fetch_id, window.activity)
    store.save_markets(window.markets)
    store.finish_snapshot(fetch_id, activity_read_until=window.activity_read_until)
    result = stored_result(store, server.wallet, seed=44)
    assert result is not None
    built = build_positions(window.activity, {m.condition_id: m for m in window.markets}, listed=window.positions,
                            not_fully_read=window.not_fully_read())
    assert result.result.tested_count == built.tested_count
    assert built.excluded_counts[ExclusionReason.NOT_FULLY_READ] == len(window.not_fully_read()) > 0


def test_fixtures_are_cut_by_the_script() -> None:
    """AD-17: each fixture names its source and holds only fields the client reads."""
    folder = Path(__file__).parent / "fixtures" / "capture"
    for path in sorted(folder.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        assert "spike/raw/sample/capture" in document["source"]
        for section, keys in (("positions_closed", cut.POSITION_KEYS), ("positions_open", cut.POSITION_KEYS),
                              ("activity", cut.ACTIVITY_KEYS)):
            assert {key for row in document[section] for key in row} <= set(keys), (path.name, section)
        assert {key for row in document["gamma"] for key in row} <= {*cut.GAMMA_KEYS, "tags", "events"}
        assert all(set(tag) == {"label"} for row in document["gamma"] for tag in row["tags"])
        assert all(set(event) == {"id"} for row in document["gamma"] for event in row.get("events", []))


# --- Story 2.3: exclusions and fees on the real fixtures ------------------------------------

def built_from(name: str) -> tuple[PositionSet, Window]:
    """A fixture's window through the live client, then the builder, exactly as a lookup does it."""
    client, _, server = live(name)
    window = positions_near(client, server.wallet)
    built = build_positions(window.activity, {m.condition_id: m for m in window.markets}, listed=window.positions,
                            not_fully_read=window.not_fully_read())
    assert built.window_size == len(window.positions)  # every listed Position comes out, none vanish
    return built, window


def test_split_and_merge_markets_are_left_out_on_real_data() -> None:
    """AD-11, FR-3: 0x729806's three MERGE Markets and three SPLIT Markets: every Position 'split or merged'.
    One SPLIT Market (0x0f49db97) is still open in Gamma, so it is outside the window (AD-7)."""
    built, window = built_from("split-merge")
    assert len({p.condition_id for p in window.positions}) == 5
    assert not any(p.condition_id.startswith("0x0f49db97") for p in window.positions)
    assert built.excluded_counts[ExclusionReason.SPLIT_OR_MERGED] == built.window_size == 10
    assert (built.left_out_share, mostly_left_out(built)) == (1.0, True)


def test_unredeemed_losers_from_the_open_list_count_as_losses() -> None:
    """AD-10, FR-3: 0x94884d's five losers still on the OPEN list (never redeemed) are tested, outcome 0, with their shares."""
    built, window = built_from("open-losers")
    open_tokens = {p.token_id for p in window.positions if p.status == "OPEN"}
    losers = [p for p in built.tested if p.token_id in open_tokens]
    assert len(open_tokens) == len(losers) == 5
    assert all(p.outcome == 0.0 and p.shares_held > 0 for p in losers)
    assert {p.outcome for p in built.tested if p.token_id not in open_tokens} == {1.0}


def test_real_fees_pass_also_one_charged_before_the_rate_changed() -> None:
    """FR-4, AD-12 (Edvard, 2026-11-23, Story 2.8; strict until then): on this 0x091596 fixture (Gamma of 20 Nov)
    every fee passes, also the $44.31 paid at 5% on 11 July 2026 in a Market Gamma lists at 3% (a Sliver here),
    which failed under Story 2.3's strict check. Own Fees 1,087.52 + 44.31 = 1,131.82, worked out on the fixture."""
    built, window = built_from("fees-and-open")
    counted = (*built.tested, *built.slivers)
    rates = {m.condition_id: m.fee_rate for m in window.markets}
    earlier = [p for p in built.slivers if p.condition_id.startswith("0x375409bc")]
    assert len(earlier) == 1 and rates[earlier[0].condition_id] == 0.03
    assert earlier[0].own_fees == pytest.approx(151.7974 + 44.3074, abs=1e-4)  # its other fees passed already
    assert (built.failed_fee_count, built.failed_fee_total) == (0, 0.0)
    assert not any(p.failed_fee_count for p in built.left_out)  # no fee fails anywhere in the window
    assert sum(p.own_fees for p in counted) == pytest.approx(1131.8228, abs=1e-4)


def test_a_conversion_leaves_out_its_whole_event_on_real_data() -> None:
    """AD-11 (Edvard, 2026-11-21, Story 2.4): 0x091596's CONVERSION names the Romania event (0x5b32843a...). Every
    Position of that event is 'split or merged': the 21 conversion outputs (share gaps in Story 2.3), the converted
    NO (1,666.67 shares at 0.36, which was tested as a held winner), and the rest. Over 10% is still left out."""
    built, window = built_from("fees-and-open")
    event = "0x5b32843a079e064277a5ddb822a3094e2ee747d0ebae8500918717076de14e00"
    in_event = [p for p in (*built.tested, *built.slivers, *built.left_out) if p.neg_risk_id == event]
    assert len(in_event) == 25 and all(p.reason is ExclusionReason.SPLIT_OR_MERGED for p in in_event)
    assert len([p for p in in_event if p.entry_price is None and p.share_gap == 1.0]) == 21
    converted = [p for p in in_event if p.shares_held == pytest.approx(1666.666665) and p.outcome == 1.0]
    assert len(converted) == 1 and not converted[0].yes_side and converted[0].entry_price == pytest.approx(0.36, abs=0.01)
    assert built.excluded_counts[ExclusionReason.SHARE_GAP] == 0
    assert (built.tested_count, built.excluded_counts[ExclusionReason.SPLIT_OR_MERGED]) == (14, 25)
    assert mostly_left_out(built)


# AD-20 (Story 2.4): the uncoupled share on the fixture Wallets, recorded as it came out (the 10 real Sample
# Wallets' share comes with Story 2.6). 0x091596: Spain vs. Argentina's O/U 5.5 and Team to Advance share a Gamma
# event that is not negative-risk. 0x0f4b0a: three "Who will die in The Boys" Markets, not negative-risk either;
# at 27% it is the one fixture over the 20% line, so its card would show the honesty note (Epic 3). split-merge has
# no tested Position, so its row only checks the empty case.
UNCOUPLED = {"small-clean": (0, 18), "fees-and-open": (2, 14), "fees": (3, 11), "open-losers": (0, 9), "split-merge": (0, 0)}


@pytest.mark.parametrize("name", sorted(UNCOUPLED))
def test_the_uncoupled_share_on_real_data(name: str) -> None:
    """AD-20: tested Positions with an uncoupled event-mate, per fixture; negative-risk event-mates are coupled."""
    built, _ = built_from(name)
    linked, tested = UNCOUPLED[name]
    assert built.tested_count == tested
    assert uncoupled_share(built.tested) == (linked / tested if tested else 0.0)


def test_a_stored_lookup_carries_the_uncoupled_share(store: Store) -> None:
    """AD-20, AD-19: the stored snapshot keeps the Markets' events, so the stored result has the same share."""
    client, _, server = live("fees-and-open")
    fetch_wallet(client, store, server.wallet)
    stored = stored_result(store, server.wallet, seed=44)
    assert stored is not None and stored.result.uncoupled_share == 2 / 14


def test_the_second_fee_wallet_counts_fees_from_before_a_rate_cut() -> None:
    """FR-4, AD-12 (Edvard, 2026-11-23, Story 2.8; strict until then): on this 0x0f4b0a fixture the 7 fees ($0.28)
    charged at 4-5% in Markets Gamma lists at 1%, which failed under Story 2.3, now pass and count: Own Fees
    0.2521 + 0.2779 = 0.5300, worked out on the fixture."""
    built, window = built_from("fees")
    rates = {m.condition_id: m.fee_rate for m in window.markets}
    counted = (*built.tested, *built.slivers)
    at_one_percent = [p for p in counted if rates[p.condition_id] == 0.01 and p.own_fees > 0]
    assert len(at_one_percent) == 7
    assert (built.failed_fee_count, built.failed_fee_total) == (0, 0.0)
    assert not any(p.failed_fee_count for p in built.left_out)  # no fee fails anywhere in the window
    assert sum(p.own_fees for p in counted) == pytest.approx(0.5300, abs=1e-4)


def test_a_stored_lookup_applies_the_list_checks(store: Store) -> None:
    """AD-11, AD-19: `stored_result` passes the snapshot's listed Positions, so the share gaps count there too."""
    client, _, server = live("fees-and-open")
    fetch_wallet(client, store, server.wallet)
    stored = stored_result(store, server.wallet, seed=44)
    built, _ = built_from("fees-and-open")
    assert stored is not None and stored.result.tested_count == built.tested_count == 14  # 17 before Story 2.4


# --- Story 4.1: before and after the Cut-off Date -------------------------------------------

SAMPLE_DAY = date.fromisoformat(SAMPLE_CUTOFF)  # the Sample Dataset's Cut-off Date, 1 July 2025
# small-clean on 1 March 2025: 4 Positions in Markets resolved before it, 4 bought before and resolved after it
# (straddlers), 15 bought after it, and 1 in a Market still open.
SPLIT_DAY = date(2025, 3, 1)


def gamma_time(epoch: int) -> str:
    """An epoch second as Gamma writes `closedTime`."""
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%d %H:%M:%S+00")


def one_by_prefix(rows: list[dict[str, Any]], key: str, prefix: str) -> dict[str, Any]:
    (row,) = [r for r in rows if r[key].startswith(prefix)]
    return row


def built_window(window: Window) -> PositionSet:
    """A part through the one builder (AD-11); every listed Position comes out, none vanish."""
    built = build_positions(window.activity, {m.condition_id: m for m in window.markets}, listed=window.positions,
                            not_fully_read=window.not_fully_read())
    assert built.window_size == len(window.positions)
    return built


def reasons(built: PositionSet) -> dict[str, int]:
    return {reason.name: n for reason, n in built.excluded_counts.items() if n}


def closed_at(server: FakePolymarket) -> dict[str, int]:
    """Gamma's resolution time of every closed Market of the fixture that has one."""
    return {m["conditionId"]: parse_time(m["closedTime"]) for m in server.gamma if m["closed"] and m.get("closedTime")}


def after_part_by_hand(server: FakePolymarket, cut: int) -> tuple[list[str], list[str], dict[str, list[dict[str, Any]]]]:
    """AD-7 by hand on the raw rows. The rows that count are OPEN and CLOSED with a last event on or after the cut-off,
    one per token (OPEN first). Returns the Markets whose counted rows were all first entered on or after the cut-off,
    ranked by their earliest entry then id; those of them resolved on or after it (the eligible ones), in rank order;
    and each Market's counted rows."""
    counted: dict[str, dict[str, Any]] = {}
    for r in server.lists["OPEN"] + [r for r in server.lists["CLOSED"] if r["last_event_at"] >= cut]:
        counted.setdefault(r["token_id"], r)
    rows_of: dict[str, list[dict[str, Any]]] = {}
    for r in counted.values():
        rows_of.setdefault(r["condition_id"], []).append(r)
    entered = {c: min(r["first_entry_at"] for r in rows) for c, rows in rows_of.items()
               if all(r["first_entry_at"] >= cut for r in rows)}
    fresh = sorted(entered, key=lambda c: (entered[c], c))
    resolved = closed_at(server)
    return fresh, [c for c in fresh if c in resolved and resolved[c] >= cut], rows_of


def test_the_cut_off_date_is_00_00_utc_converted_in_one_place() -> None:
    """AD-7 (Story 4.1): `cutoff_at` turns a date into 00:00 UTC epoch seconds; a datetime, or a number handed to
    `positions_near`, is refused before any request."""
    assert cutoff_at(SAMPLE_DAY) == 1_751_328_000
    with pytest.raises(TypeError):
        cutoff_at(datetime(2025, 7, 1, tzinfo=UTC))
    client, transport, server = live("small-clean")
    with pytest.raises(TypeError):
        positions_near(client, server.wallet, 1_751_328_000, "before")  # type: ignore[arg-type]
    assert transport.calls == []


@pytest.mark.parametrize(("cutoff", "side"), [(SAMPLE_DAY, None), (None, "before"), (SAMPLE_DAY, "during")])
def test_a_cut_off_date_and_its_side_come_together(cutoff: date | None, side: str | None) -> None:
    """AD-7 (Story 4.1): a date without a side, a side without a date, or an unknown side is refused before any request."""
    client, transport, server = live("small-clean")
    with pytest.raises(ValueError, match="side"):
        positions_near(client, server.wallet, cutoff, side)
    assert transport.calls == []


def test_before_and_after_parts_partition_a_wallet() -> None:
    """AD-7, AD-11 (Story 4.1): on small-clean at 1 March 2025 no Position is in both parts, the 4 bought before and
    resolved after are in neither, and every other Position of the window is in one. Both parts go through the one
    builder; counts as they came out: before 4 tested, after 13 tested and 2 sold before resolution."""
    cut = cutoff_at(SPLIT_DAY)
    reference, _, server = live("small-clean")
    rows, markets = every_record(reference, server.wallet)
    in_window = {r for r in rows if markets[r.condition_id].closed and markets[r.condition_id].closed_time is not None}
    straddlers = {r for r in in_window if r.first_entry_at < cut <= (markets[r.condition_id].closed_time or 0)}
    before = positions_near(live("small-clean")[0], server.wallet, SPLIT_DAY, "before")
    after = positions_near(live("small-clean")[0], server.wallet, SPLIT_DAY, "after")

    assert (len(before.positions), len(straddlers), len(after.positions), len(in_window)) == (4, 4, 15, 23)
    assert not set(before.positions) & set(after.positions)
    assert not straddlers & (set(before.positions) | set(after.positions))
    assert set(before.positions) | set(after.positions) | straddlers == in_window
    assert all((markets[p.condition_id].closed_time or cut) < cut for p in before.positions)
    assert all(p.first_entry_at >= cut for p in after.positions)
    assert all(r.timestamp < cut for r in before.activity) and all(r.timestamp >= cut for r in after.activity)
    assert (before.cutoff, before.side, after.cutoff, after.side) == (cut, "before", cut, "after")
    assert not before.capped and not after.capped
    assert before.activity_read_until is None and after.activity_read_until is None

    built_before, built_after = built_window(before), built_window(after)
    assert (built_before.tested_count, reasons(built_before)) == (4, {})
    assert (built_after.tested_count, reasons(built_after)) == (13, {"SOLD_BEFORE_RESOLUTION": 2})


@pytest.mark.parametrize(("offset", "inside"), [(-1, True), (0, False)])
def test_the_before_part_ends_just_before_the_cut_off(offset: int, inside: bool) -> None:
    """AD-7 (Story 4.1): a Market resolved one second before the cut-off is in the before part; one resolved at it is not."""
    cut = cutoff_at(SPLIT_DAY)
    client, _, server = live("small-clean")
    market = one_by_prefix(server.gamma, "conditionId", "0xc3d41551")
    market["closedTime"] = gamma_time(cut + offset)
    window = positions_near(client, server.wallet, SPLIT_DAY, "before")
    assert (market["conditionId"] in {m.condition_id for m in window.markets}) is inside
    assert len(window.positions) == (4 if inside else 3)


@pytest.mark.parametrize(("offset", "inside"), [(0, True), (-1, False)])
def test_the_after_part_starts_at_the_cut_off(offset: int, inside: bool) -> None:
    """AD-7 (Story 4.1): a Position first entered exactly at the cut-off is in the after part; one second earlier it
    is not (it is a straddler)."""
    cut = cutoff_at(SPLIT_DAY)
    client, _, server = live("small-clean")
    row = one_by_prefix(server.lists["CLOSED"], "condition_id", "0x9d2399f7")
    row["first_entry_at"] = cut + offset
    window = positions_near(client, server.wallet, SPLIT_DAY, "after")
    assert (row["condition_id"] in {m.condition_id for m in window.markets}) is inside
    assert len(window.positions) == (15 if inside else 14)


def test_markets_that_only_look_new_are_not_in_the_after_part() -> None:
    """AD-7 (Story 4.1 acceptance): 0x729806 bought 41 tokens on or after 1 July 2025, but 20 of them were first
    entered before it (`first_entry_at`), which an activity read from the cut-off cannot see. None of their Markets is
    in the after part; every other eligible Market is, whole, also the 3 entered without a buy (by CONVERSION), which
    the builder leaves out with their reason. The CLOSED list comes in pages of 4 and stops at the cut-off. Counts as
    they came out: 24 Markets, 36 Positions, all split or merged (a split-and-merge Wallet)."""
    cut = cutoff_at(SAMPLE_DAY)
    client, transport, server = live("after-part")
    server.page_size = 4
    window = positions_near(client, server.wallet, SAMPLE_DAY, "after")

    _, eligible, rows_of = after_part_by_hand(server, cut)
    listed = server.lists["CLOSED"] + server.lists["OPEN"]
    buys = [r for r in server.activity if r["type"] == "TRADE" and r["side"] == "BUY" and r["timestamp"] >= cut]
    bought = {r["token_id"] for r in buys}
    looks_new_tokens = {r["token_id"] for r in listed if r["token_id"] in bought and r["first_entry_at"] < cut}
    looks_new = {r["condition_id"] for r in listed if r["token_id"] in looks_new_tokens}
    no_buy = set(eligible) - {r["condition_id"] for r in buys}
    assert (len(bought), len(looks_new_tokens), len(no_buy)) == (41, 20, 3)

    chosen = {m.condition_id for m in window.markets}
    assert not chosen & looks_new
    assert chosen == set(eligible) and no_buy <= chosen
    assert {p.token_id for p in window.positions} == {r["token_id"] for c in eligible for r in rows_of[c]}
    assert (len(chosen), len(window.positions)) == (24, 36)
    assert not window.capped and window.activity_read_until is None
    closed_calls = [c for c in calls_to(transport, "/v2/positions") if c["status"] == "CLOSED"]
    newest_first = sorted(server.lists["CLOSED"], key=lambda r: -r["last_event_at"])
    stop_page = next(i // 4 + 1 for i in range(0, len(newest_first), 4)
                     if min(r["last_event_at"] for r in newest_first[i : i + 4]) < cut)
    assert len(closed_calls) == stop_page < -(-len(newest_first) // 4)  # stopped at the cut-off, not a full read

    built = built_window(window)
    entered_by_conversion = [p for p in built.left_out if p.condition_id in no_buy]
    assert entered_by_conversion and all(p.reason is ExclusionReason.SPLIT_OR_MERGED for p in entered_by_conversion)
    assert (built.tested_count, reasons(built)) == (0, {"SPLIT_OR_MERGED": 36})


def test_a_market_resolved_before_but_entered_after_is_in_neither_part() -> None:
    """AD-7 (Edvard, 2026-11-25, Story 4.1): a Market Gamma closed before the cut-off whose Positions were first entered
    on or after it is in neither part, so no bet made after the date reaches the before part."""
    cut = cutoff_at(SAMPLE_DAY)
    _, _, server = live("after-part")
    early = {c for c, t in closed_at(server).items() if t < cut}
    listed = server.lists["CLOSED"] + server.lists["OPEN"]
    assert len(early) == 1 and all(r["first_entry_at"] >= cut for r in listed if r["condition_id"] in early)
    before = positions_near(live("after-part")[0], server.wallet, SAMPLE_DAY, "before")
    after = positions_near(live("after-part")[0], server.wallet, SAMPLE_DAY, "after")
    assert not early & {m.condition_id for m in (*before.markets, *after.markets)}


@pytest.mark.parametrize("entered", [0, 60])
@pytest.mark.parametrize("status", ["CLOSED", "OPEN"])
def test_one_later_position_takes_its_market_out_of_the_before_part(status: str, entered: int) -> None:
    """AD-7 (Edvard, 2026-11-25, Story 4.1): on small-clean, one Position of the other token first entered at or after
    the cut-off, on either list, takes its before-part Market out of the before part whole; it is in neither part."""
    split = cutoff_at(SPLIT_DAY)
    client, _, small = live("small-clean")
    market = one_by_prefix(small.gamma, "conditionId", "0xc3d41551")
    (held,) = [r for r in small.lists["CLOSED"] if r["condition_id"] == market["conditionId"]]
    other = next(t for t in json.loads(market["clobTokenIds"]) if t != held["token_id"])
    small.lists[status].append({"condition_id": market["conditionId"], "token_id": other, "total_size": 10.0,
                                "first_entry_at": split + entered, "last_event_at": split + 120})
    window = positions_near(client, small.wallet, SPLIT_DAY, "before")
    assert market["conditionId"] not in {m.condition_id for m in window.markets} and len(window.positions) == 3
    assert all(p.first_entry_at < split for p in window.positions)
    after_small = positions_near(live("small-clean")[0], small.wallet, SPLIT_DAY, "after")
    assert market["conditionId"] not in {m.condition_id for m in after_small.markets}


@pytest.mark.parametrize("page_size", [1, 1_000])
def test_the_before_walk_counts_a_later_position_before_it_stops(page_size: int) -> None:
    """AD-7 (Story 4.1): the CLOSED stop rule of the before part leaves out a Market entered after the cut-off from the
    page it is read on. On small-clean with a limit of 1, the latest-resolved before Market (0xde8ca3cc) gets a later
    Position, and a row of a Market Gamma does not know sits just above 0xc3d41551's row; walking one row a page, the
    walk must not stop before 0xc3d41551 is read. The part is its one Position, at either page size."""
    split = cutoff_at(SPLIT_DAY)
    client, _, small = live("small-clean")
    small.page_size = page_size
    latest = one_by_prefix(small.gamma, "conditionId", "0xde8ca3cc")
    kept = one_by_prefix(small.gamma, "conditionId", "0xc3d41551")
    (latest_row,) = [r for r in small.lists["CLOSED"] if r["condition_id"] == latest["conditionId"]]
    (kept_row,) = [r for r in small.lists["CLOSED"] if r["condition_id"] == kept["conditionId"]]
    other = next(t for t in json.loads(latest["clobTokenIds"]) if t != latest_row["token_id"])
    small.lists["CLOSED"].append({"condition_id": latest["conditionId"], "token_id": other, "total_size": 10.0,
                                  "first_entry_at": split + 60, "last_event_at": split + 120})
    small.lists["CLOSED"].append({"condition_id": "0x" + "ee" * 32, "token_id": "123", "total_size": 1.0,
                                  "first_entry_at": kept_row["last_event_at"] - 10,
                                  "last_event_at": kept_row["last_event_at"] + 1})
    window = positions_near(client, small.wallet, SPLIT_DAY, "before", limit=1)
    assert [p.token_id for p in window.positions] == [kept_row["token_id"]]


@pytest.mark.parametrize("limit", [1, 2, 3, 4, 5, 8, 13, 21, 35, 36, 37])
def test_the_after_part_takes_the_earliest_whole_markets(limit: int) -> None:
    """AD-7, AD-8 (Story 4.1 review): eligible Markets rank by their earliest `first_entry_at`, then id, and are taken
    whole while they fit under the limit. `capped` is exact: True when an eligible Position was left out (35), False
    with exactly the limit and nothing more eligible (36). A first Market bigger than the limit empties the part (1)."""
    cut = cutoff_at(SAMPLE_DAY)
    client, transport, server = live("after-part")
    window = positions_near(client, server.wallet, SAMPLE_DAY, "after", limit=limit)

    _, eligible, rows_of = after_part_by_hand(server, cut)
    taken: list[str] = []
    for c in eligible:
        if sum(len(rows_of[t]) for t in taken) + len(rows_of[c]) > limit:
            break
        taken.append(c)
    total = sum(len(rows_of[c]) for c in eligible)
    held = sum(len(rows_of[c]) for c in taken)
    assert total == 36
    assert {m.condition_id for m in window.markets} == set(taken)
    assert len(window.positions) == held <= limit
    assert window.capped is (held < total)
    activity = calls_to(transport, "/v2/activity")
    if taken:
        assert {(int(c["start"]), int(c["end"])) for c in activity} == {(cut, max(m.closed_time or 0 for m in window.markets))}
    else:
        assert activity == [] and window.activity == ()


def test_the_after_part_asks_gamma_in_rank_order_only_until_it_is_full() -> None:
    """AD-7, AD-10 (Story 4.1 review): Gamma is asked for the Markets entered on or after the cut-off, in rank order and
    in batches, until the part is full and one more eligible Market is known; never for the Markets entered before."""
    cut = cutoff_at(SAMPLE_DAY)

    def asked(transport: FakeTransport) -> list[str]:
        ids = [v for c in transport.calls if c.url.endswith("/markets") for k, v in c.params if k == "condition_ids"]
        return list(dict.fromkeys(ids))

    client, transport, server = live("after-part")
    fresh, _, _ = after_part_by_hand(server, cut)
    assert len(fresh) > GAMMA_BATCH
    positions_near(client, server.wallet, SAMPLE_DAY, "after", limit=3)
    assert asked(transport) == fresh[:GAMMA_BATCH]
    client, transport, server = live("after-part")
    positions_near(client, server.wallet, SAMPLE_DAY, "after")
    assert asked(transport) == fresh


@pytest.mark.parametrize("held_at_cut", [False, True])
def test_a_position_closed_before_the_cut_off_does_not_make_its_market_mixed(held_at_cut: bool) -> None:
    """AD-7 (Edvard, 2026-11-25, Story 4.1 review): a CLOSED Position of the other token, first entered before the
    cut-off and fully closed before it, leaves its Market in the after part, the same at every page size. Still held at
    the cut-off, it makes the Market mixed: in neither part."""
    cut = cutoff_at(SAMPLE_DAY)
    windows: list[Window] = []
    for size in (1, 4, 1_000):
        client, _, server = live("after-part")
        server.page_size = size
        market = one_by_prefix(server.gamma, "conditionId", "0x1c79659a")
        (held,) = [r for r in server.lists["CLOSED"] + server.lists["OPEN"] if r["condition_id"] == market["conditionId"]]
        other = next(t for t in json.loads(market["clobTokenIds"]) if t != held["token_id"])
        server.lists["CLOSED"].append({"condition_id": market["conditionId"], "token_id": other, "total_size": 10.0,
                                       "first_entry_at": cut - 1_000, "last_event_at": cut + 10 if held_at_cut else cut - 10})
        windows.append(positions_near(client, server.wallet, SAMPLE_DAY, "after"))
    assert windows[0] == windows[1] == windows[2]
    assert (market["conditionId"] in {m.condition_id for m in windows[0].markets}) is not held_at_cut
    assert other not in {p.token_id for p in windows[0].positions}


def test_an_activity_cap_in_the_after_part_marks_positions_not_fully_read() -> None:
    """AD-7, AD-11 (Story 4.1): an activity cap never changes which Markets are in the after part; it sets
    `activity_read_until`, and the usual "not fully read" rule leaves out the Positions resolved from then on."""
    full = positions_near(live("after-part")[0], FakePolymarket("after-part").wallet, SAMPLE_DAY, "after")
    client, _, server = live("after-part")
    window = positions_near(client, server.wallet, SAMPLE_DAY, "after", activity_row_cap=3_000)

    assert (window.positions, window.markets, window.capped) == (full.positions, full.markets, full.capped)
    until = window.activity_read_until
    assert until is not None and all(r.timestamp <= until for r in window.activity)
    assert [r for r in full.activity if r.timestamp < until] == [r for r in window.activity if r.timestamp < until]
    unread = window.not_fully_read()
    closed_time = {m.condition_id: m.closed_time or 0 for m in window.markets}
    assert set(unread) == {p for p in window.positions if closed_time[p.condition_id] >= until}
    assert 0 < len(unread) < len(window.positions)
    assert built_window(window).excluded_counts[ExclusionReason.NOT_FULLY_READ] == len(unread)


@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize(("status", "page_size"), [("CLOSED", 10), ("OPEN", 3)])
def test_a_part_rests_only_on_whole_lists(side: str, status: str, page_size: int) -> None:
    """AD-3, AD-7 (Story 4.1): a positions list still timing out after the restart raises PolymarketUnavailable on
    either side, before any activity is read."""
    client, transport, server = live("after-part")
    server.page_size = page_size
    server.timeout_from_page[status] = 1
    with pytest.raises(PolymarketUnavailable, match=status):
        positions_near(client, server.wallet, SAMPLE_DAY, side)
    assert calls_to(transport, "/v2/activity") == []


@pytest.mark.parametrize("side", ["before", "after"])
def test_two_empty_lists_are_no_history_on_either_side(side: str) -> None:
    """FR-1 (Story 4.1): both lists empty raises NoPolymarketHistory, before Gamma or activity is asked."""
    client, transport, server = live("small-clean")
    server.lists = {"CLOSED": [], "OPEN": []}
    with pytest.raises(NoPolymarketHistory):
        positions_near(client, server.wallet, SAMPLE_DAY, side)
    assert [call.url.rsplit("/", 1)[-1] for call in transport.calls] == ["positions", "positions"]


def test_an_after_part_with_nothing_eligible_is_empty() -> None:
    """AD-7 (Story 4.1): with no Position entered on or after the cut-off the after part is empty and not capped, and
    neither Gamma nor activity is asked."""
    day = date(2030, 1, 1)
    client, transport, server = live("small-clean")
    window = positions_near(client, server.wallet, day, "after")
    assert window == Window(server.wallet, 2_000, (), (), (), None, False, cutoff_at(day), "after")
    assert calls_to(transport, "/markets") == [] and calls_to(transport, "/v2/activity") == []


@pytest.mark.parametrize("change", ["changed", "removed"])
@pytest.mark.parametrize(("name", "day"), [("small-clean", SPLIT_DAY), ("after-part", SAMPLE_DAY)])
def test_nothing_after_the_cut_off_changes_the_before_part(name: str, day: date, change: str) -> None:
    """AD-7, no leak (Story 4.1): with the outcomes of later Markets, every fill and every Position first entered after
    the cut-off (also those in a Market resolved before it, on after-part) changed or removed, the before part is
    exactly the same. Removed, a Position entered before the cut-off stays listed, as it existed then, but its later
    Market's Gamma record is gone; that also keeps after-part's lists from becoming empty."""
    cut = cutoff_at(day)
    expected = positions_near(live(name)[0], FakePolymarket(name).wallet, day, "before")
    client, _, server = live(name)
    resolved = closed_at(server)
    later = {m["conditionId"] for m in server.gamma if m["conditionId"] not in resolved or resolved[m["conditionId"]] >= cut}
    entered_after = [r for rows in server.lists.values() for r in rows if r["first_entry_at"] >= cut]
    assert later and entered_after
    if name == "after-part":  # the Market resolved before the cut-off but entered after it
        assert any(resolved.get(r["condition_id"], cut) < cut for r in entered_after)
    else:
        assert expected.positions
    if change == "changed":
        for m in server.gamma:
            if m["conditionId"] in later:
                m["outcomePrices"] = json.dumps(list(reversed(json.loads(m["outcomePrices"]))))
        for r in server.activity:
            if r["timestamp"] >= cut:
                r["size"], r["usdc_size"] = r["size"] * 3, r["usdc_size"] * 2
        for rows in server.lists.values():
            for r in rows:
                if r["condition_id"] in later or r["first_entry_at"] >= cut:
                    r["total_size"] *= 5
                if r["first_entry_at"] >= cut:
                    r["first_entry_at"] += 86_400
                    r["last_event_at"] += 86_400
    else:
        server.gamma = [m for m in server.gamma if m["conditionId"] not in later]
        server.activity = [r for r in server.activity if r["timestamp"] < cut]
        server.lists = {
            s: [r for r in rows if r["first_entry_at"] < cut]
            for s, rows in server.lists.items()
        }
    assert positions_near(client, server.wallet, day, "before") == expected


@pytest.mark.parametrize(("name", "day", "side", "page", "limit"), [
    ("small-clean", SPLIT_DAY, "before", 4, 3),
    ("small-clean", SPLIT_DAY, "after", 4, 3),
    ("after-part", SAMPLE_DAY, "after", 4, 5),
])
def test_offline_and_live_give_the_same_parts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, day: date, side: str, page: int, limit: int
) -> None:
    """AD-13 (Story 4.1): the same records served by OfflineClient give the same before and after parts as the live
    client, also when the lists come in small pages and the part is capped."""
    reference, _, server = live(name)
    rows, markets = every_record(reference, server.wallet)
    activity = reference.activity_rows(server.wallet, start=0).rows
    sample = SampleWallet(server.wallet, "fixture", activity, tuple(rows), tuple(markets.values()))
    sample_json.write_wallet(tmp_path / "fixture.json", sample)

    monkeypatch.setattr(offline_module, "PAGE_LIMIT", page)
    client, _, live_server = live(name)
    live_server.page_size = page
    offline_window = positions_near(OfflineClient([tmp_path / "fixture.json"]), server.wallet, day, side, limit=limit)
    assert offline_window == positions_near(client, server.wallet, day, side, limit=limit)
    assert offline_window.positions and offline_window.capped


def test_ad7_cutoff_day_is_cutoff_at_backwards():
    """AD-7 (Story 4.4 review): a stored Cut-off Date turns back into the same date, also long before 1970,
    where Windows' `fromtimestamp` refuses."""
    from datetime import date

    from liquidoracle.data.window import cutoff_at, cutoff_day

    for day in (date(1, 1, 1), date(1960, 1, 1), date(1970, 1, 1), date(2025, 7, 1), date(9999, 12, 31)):
        assert cutoff_day(cutoff_at(day)) == day
