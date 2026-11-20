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
from functools import partial
from pathlib import Path

import pytest
from fake_polymarket import FakeClock, FakePolymarket, FakeTransport

from liquidoracle.core.positions import build_positions
from liquidoracle.data import offline as offline_module
from liquidoracle.data import sample_json
from liquidoracle.data.errors import PolymarketUnavailable
from liquidoracle.data.offline import OfflineClient
from liquidoracle.data.polymarket import PolymarketClient
from liquidoracle.data.store import Store
from liquidoracle.data.window import ACTIVITY_ROW_CAP, positions_near
from liquidoracle.records import ExclusionReason, ListedPosition, Market, SampleWallet
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

    built = build_positions(window.activity, {m.condition_id: m for m in window.markets}, not_fully_read=unread)
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
    built = build_positions(expected.activity, {m.condition_id: m for m in expected.markets},
                            not_fully_read=expected.not_fully_read())
    assert stored is not None and stored.result.tested_count == built.tested_count


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
    """AD-10: the positions lists say which Positions exist; 0x091596's two activity-only Markets (unknown
    to Gamma too) are never asked for and stay outside the window (Story 2.3 counts such tokens)."""
    client, transport, server = live("fees-and-open")
    listed = {r["condition_id"] for r in server.lists["CLOSED"] + server.lists["OPEN"]}
    only_in_activity = {r["condition_id"] for r in server.activity} - listed
    assert len(only_in_activity) == 2 and not only_in_activity & {m["conditionId"] for m in server.gamma}
    window = positions_near(client, server.wallet)
    asked = {v for c in transport.calls if c.url.endswith("/markets") for k, v in c.params if k == "condition_ids"}
    assert not only_in_activity & asked
    assert not only_in_activity & {r.condition_id for r in window.activity}


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
    expected = [
        r for r in server.activity
        if r["condition_id"] in ids and r.get("is_combo") is not True
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


def test_a_cut_off_date_is_not_built_yet() -> None:
    """AD-8: the before and after parts come with Story 4.1."""
    client, _, server = live("small-clean")
    with pytest.raises(NotImplementedError, match="4.1"):
        positions_near(client, server.wallet, cutoff=1_751_328_000, side="before")


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
    built = build_positions(window.activity, {m.condition_id: m for m in window.markets},
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
        assert {key for row in document["gamma"] for key in row} <= {*cut.GAMMA_KEYS, "tags"}
        assert all(set(tag) == {"label"} for row in document["gamma"] for tag in row["tags"])
