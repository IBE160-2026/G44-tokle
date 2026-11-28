"""The Scan as a resumable job: phases, stored state, Resume, lookups first, results (FR-16, AD-5, AD-6, AD-19, AD-22).

The worker runs Scans on the routed fake from `test_scan.py` (`scenario()`: four Markets in the set,
two of them partial, eight candidates, real Wallets cut from the capture). Tests call
`Worker.run_once()` instead of starting the thread. No socket is opened (AD-17).
"""

from __future__ import annotations

import dataclasses
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fake_polymarket import FakePolymarket, FakeScan, FakeTransport, status
from test_scan import (
    CONTRACT,
    CUT,
    DAY,
    FEES,
    LOSERS,
    REFUSED,
    SMALL,
    TIMED,
    USED_1,
    USED_2,
    funnel_market,
    holder,
    live,
    scenario,
    verdict_real_pnl,
)

from liquidoracle.core import funnel
from liquidoracle.data import store as store_module
from liquidoracle.data import synthetic
from liquidoracle.data.polymarket import PROBE_TOKEN
from liquidoracle.data.store import (
    AFTER,
    BEFORE,
    SCAN_BEFORE,
    SCAN_WHOLE,
    JobStatus,
    ScanStep,
    ScanWallet,
    Snapshot,
    Store,
    WalletOutcome,
)
from liquidoracle.data.window import WINDOW_LIMIT, cutoff_at
from liquidoracle.records import Market, MarketHolder, PricePoint, SampleWallet, Verdict
from liquidoracle.services import scan as scan_module
from liquidoracle.services.fetch import fetch_wallet
from liquidoracle.services.jobs import FINISHED, Jobs, Worker
from liquidoracle.services.scan import fetch_part, read_candidates, run_funnel, scan_results

SEED = 44
SIZE = 3  # every candidate is shortlisted (8 < 9)
SHORTLIST = 8
HOUR = 3600
CAPPED_FIRST = scenario().funnel[3]["conditionId"]  # the highest-volume Market in the set (capped)


class Clock:
    """The store's wall clock: a number the test moves."""

    def __init__(self) -> None:
        self.now = 1_790_000_000.0

    def __call__(self) -> float:
        return self.now


@dataclasses.dataclass
class Rig:
    store: Store
    jobs: Jobs
    worker: Worker
    server: FakeScan
    transport: FakeTransport
    clock: Clock


def rig_for(path: Path, server: FakeScan | None = None) -> Rig:
    server = server or scenario()
    client, transport = live(server)
    clock = Clock()
    store = Store(path, clock=clock)
    jobs = Jobs(store)
    return Rig(store, jobs, Worker(client, jobs), server, transport, clock)


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    made = rig_for(tmp_path / "scan.db")
    yield made
    made.store.close()


def start(rig: Rig, size: int = SIZE) -> tuple[int, int]:
    started = rig.jobs.start_scan(DAY, size, seed=SEED)
    assert started is not None
    return started


def results_without_ids(store: Store, scan_id: int) -> list[tuple[Any, ...]]:
    return [(r.wallet, r.scope, r.verdict, r.p_value, r.tested_count, r.real_pnl, r.not_fully_read)
            for r in store.scan_results(scan_id)]


def user_calls(transport: FakeTransport, wallet: str, since: int = 0) -> int:
    return sum(1 for c in transport.calls[since:] if c.query.get("user") == wallet)


NINTH = "0x" + "9" * 40  # a ninth candidate, so N = 3 shortlists 9 (3 x N), as in the spec's matrix


def nine_candidates() -> FakeScan:
    """`scenario()` with a ninth candidate (no Polymarket history) at the bottom of the shortlist."""
    server = scenario()
    server.holders[(USED_1, "CLOSED")].append(holder(NINTH, USED_1, "12", pnl=-10))
    return server


def uninterrupted(tmp_path: Path, server: FakeScan | None = None) -> list[tuple[Any, ...]]:
    """The results of the same Scan run in one go on fresh fake data."""
    other = rig_for(tmp_path / "uninterrupted.db", server)
    try:
        scan_id, _ = start(other)
        assert other.worker.run_once()
        return results_without_ids(other.store, scan_id)
    finally:
        other.store.close()


# --- the happy path ----------------------------------------------------------------------------------


def test_fr16_a_scan_runs_both_phases_and_stores_its_results(rig: Rig) -> None:
    """FR-16, AD-5, AD-22: one job runs ranking, Skill Tests and the Hold-up Test; the Scan is done only then, its
    top N equals the in-memory funnel's, and each top Wallet has a `scan_before` and a `scan_whole` result with the
    Scan's key."""
    scan_id, job_id = start(rig)
    assert rig.worker.run_once()
    job = rig.store.job(job_id)
    assert job is not None and job.status is JobStatus.DONE and job.message == FINISHED[JobStatus.DONE]
    assert (job.kind, job.scan_id, job.wallet) == ("scan", scan_id, None)
    scan = rig.store.scan(scan_id)
    assert scan is not None and scan.step is ScanStep.DONE
    assert (scan.cutoff, scan.size, scan.seed, scan.as_of) == (CUT, SIZE, SEED, int(rig.clock.now))

    expected = run_funnel(live(scenario())[0], DAY, SIZE)
    wallets = rig.store.scan_wallets(scan_id)
    assert [(w.wallet, w.estimate) for w in wallets] == [(c.wallet, c.estimate) for c in expected.shortlist]
    assert {w.wallet for w in wallets if w.top} == {w.wallet for w in expected.top}
    assert scan.candidate_count == expected.candidate_count == 8
    states = {m.condition_id: m.state for m in rig.store.scan_markets(scan_id)}
    assert {cid for cid, state in states.items() if state == "partial"} == set(expected.partial)
    assert {w.wallet: w.real_pnl for w in wallets if w.outcome is not WalletOutcome.CONTRACT} == {
        w.wallet: w.real_pnl for w in expected.ranked
    }

    results = rig.store.scan_results(scan_id)
    top = {w.wallet for w in expected.top}
    assert {(r.wallet, r.scope) for r in results} == {(w, s) for w in top for s in (SCAN_BEFORE, SCAN_WHOLE)}
    stored = rig.store._connection().execute(
        "SELECT DISTINCT scan_id, cutoff, seed FROM scan_result"
    ).fetchall()
    assert stored == [(scan_id, CUT, SEED)]  # AD-22: every result carries the Scan, cut-off and Seed


def test_ad22_results_rest_on_the_frozen_snapshots(rig: Rig) -> None:
    """AD-19, AD-22: `scan_before` is the before part's Skill Test (the very Real PnL ranking used); `scan_whole`
    rests on both frozen snapshots, and each result names them."""
    scan_id, _ = start(rig)
    rig.worker.run_once()
    by_wallet = {w.wallet: w for w in rig.store.scan_wallets(scan_id)}
    small = by_wallet[SMALL]
    assert small.top and small.before_fetch_id is not None and small.after_fetch_id is not None
    before = rig.store.snapshot(small.before_fetch_id)
    after = rig.store.snapshot(small.after_fetch_id)
    assert before is not None and (before.cutoff, before.side) == (CUT, BEFORE)
    assert after is not None and (after.cutoff, after.side) == (CUT, AFTER)
    results = {r.scope: r for r in rig.store.scan_results(scan_id) if r.wallet == SMALL}
    assert results[SCAN_BEFORE].real_pnl == small.real_pnl == verdict_real_pnl("small-clean")
    assert (results[SCAN_BEFORE].fetch_id, results[SCAN_BEFORE].after_fetch_id) == (small.before_fetch_id, None)
    assert (results[SCAN_WHOLE].fetch_id, results[SCAN_WHOLE].after_fetch_id) == (
        small.before_fetch_id, small.after_fetch_id,
    )


def test_ad22_a_top_wallet_with_nothing_read_is_tested_on_nothing_and_stays_flagged(tmp_path: Path) -> None:
    """AD-9, AD-22: a refused Wallet that makes the top N (here N = 2) has no snapshot; both its results are
    Not enough data, still flagged "not fully read", and no after part is asked for."""
    rig = rig_for(tmp_path / "scan.db")
    try:
        scan_id, _ = start(rig, size=2)
        rig.worker.run_once()
        refused = {w.wallet: w for w in rig.store.scan_wallets(scan_id)}[REFUSED]
        assert refused.top and refused.outcome is WalletOutcome.REFUSED and refused.not_fully_read
        assert refused.before_fetch_id is None and refused.after_fetch_id is None
        results = [r for r in rig.store.scan_results(scan_id) if r.wallet == REFUSED]
        assert {r.verdict for r in results} == {Verdict.NOT_ENOUGH_DATA.value}
        assert all(r.not_fully_read and r.tested_count == 0 and r.fetch_id is None for r in results)
        assert user_calls(rig.transport, REFUSED) == 1  # the one refused request of the ranking phase
    finally:
        rig.store.close()


def test_ad5_progress_names_each_step(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-5, EXPERIENCE.md: the progress JSON carries the phase and names the step: Reading Markets, Fetching
    Wallets, Ranking, "N of M Wallets checked", the Hold-up Test (Story 5.1), then the Copy Test with one step
    per price request (Story 6.2, matrix "A new Scan")."""
    seen: list[tuple[str, int, int, str]] = []
    original = rig.store.update_progress

    def record(job_id: int, *, phase: str, done: int, total: int, message: str) -> None:
        seen.append((phase, done, total, message))
        original(job_id, phase=phase, done=done, total=total, message=message)

    monkeypatch.setattr(rig.store, "update_progress", record)
    start(rig)
    rig.worker.run_once()
    messages = [m for _, _, _, m in seen]
    assert messages[0] == "Reading Markets"
    assert ("ranking", 0, 4, "Reading Markets: 0 of 4") in seen and ("ranking", 3, 4, "Reading Markets: 3 of 4") in seen
    assert ("ranking", 0, 8, "Fetching Wallets: 0 of 8") in seen and ("ranking", 7, 8, "Fetching Wallets: 7 of 8") in seen
    assert ("ranking", 1, 1, "Ranking") in seen
    assert ("skill_tests", 0, 3, "0 of 3 Wallets checked") in seen
    checked = seen.index(("skill_tests", 3, 3, "3 of 3 Wallets checked"))
    requests = sum(1 for c in rig.transport.calls if c.url.endswith("/prices-history") and c.query["market"] != PROBE_TOKEN)
    assert requests > 0
    assert seen[checked + 1:] == [
        ("holdup", 0, 1, "Hold-up Test"), ("holdup", 1, 1, "Hold-up Test"), ("copy", 0, 0, "Copy Test"),
        *(("copy", i, requests, f"Copy Test: {i} of {requests} prices") for i in range(requests + 1)),
    ]


# --- stopping, interruption, failure and Resume -------------------------------------------------------


def test_ad5_an_outage_in_the_wallet_phase_stops_the_scan_and_resume_reads_nothing_twice(tmp_path: Path) -> None:
    """FR-16, AD-5, AD-19: Polymarket not answering on the 5th of 9 Wallets makes the Scan `stopped` at "Fetching
    Wallets: 4 of 9"; Resume carries on from the 5th, reads no Market and no finished Wallet's before part again,
    and the results equal an uninterrupted run's."""
    rig = rig_for(tmp_path / "scan.db", nine_candidates())
    rig.server.refuse[REFUSED] = status(503)  # the 5th shortlisted Wallet: every try fails
    scan_id, job_id = start(rig)
    rig.worker.run_once()
    job = rig.store.job(job_id)
    assert job is not None and job.status is JobStatus.STOPPED
    assert (job.phase, job.done, job.total) == ("ranking", 4, 9)
    assert job.message == FINISHED[JobStatus.STOPPED]
    frozen = {w.wallet: w.before_fetch_id for w in rig.store.scan_wallets(scan_id) if w.outcome is not None}
    assert set(frozen) == {CONTRACT, SMALL, LOSERS, rig.store.scan_wallets(scan_id)[3].wallet}

    rig.server.refuse[REFUSED] = status(400, b'{"error": "bad request"}')  # Polymarket is back
    calls_before = len(rig.transport.calls)
    resumed = rig.jobs.resume_scan(scan_id)
    assert resumed is not None and resumed != job_id
    assert rig.worker.run_once()
    assert rig.store.job(resumed).status is JobStatus.DONE
    later = rig.transport.calls[calls_before:]
    assert not any("condition" in c.query or "order" in c.query for c in later)  # no Market read again
    for finished in (CONTRACT, LOSERS, FEES):  # finished before the stop and not in the top 3: no request at all
        assert user_calls(rig.transport, finished, calls_before) == 0, finished
    after = {w.wallet: w.before_fetch_id for w in rig.store.scan_wallets(scan_id)}
    assert all(after[w] == fetch_id for w, fetch_id in frozen.items())
    before_rows = rig.store._connection().execute(
        "SELECT wallet, COUNT(*) FROM snapshot WHERE side = 'before' GROUP BY wallet HAVING COUNT(*) > 1"
    ).fetchall()
    assert before_rows == []
    assert results_without_ids(rig.store, scan_id) == uninterrupted(tmp_path, nine_candidates())
    rig.store.close()


class AppClosed(Exception):
    """Stands in for the app being closed: the job is left `running`."""


def test_ad5_a_scan_left_running_is_interrupted_and_resumes_from_where_it_was(rig: Rig, tmp_path: Path) -> None:
    """AD-5: a Scan cut off after two Markets (the app closed) is `interrupted` at startup; Resume reads only the
    Markets not yet read and ends with the same results as an uninterrupted run."""
    scan_id, job_id = start(rig)
    job = rig.store.claim_next_job()
    assert job is not None and job.id == job_id
    units = iter(range(10))

    def close_after_two_markets() -> None:
        if next(units) == 2:  # the Market set, then two Markets
            raise AppClosed

    with pytest.raises(AppClosed):
        scan_module.run_scan(rig.worker._client, rig.store, scan_id, job_id=job_id, between=close_after_two_markets)
    assert rig.store.job(job_id).status is JobStatus.RUNNING
    assert rig.store.interrupt_running_jobs() == 1
    assert rig.store.job(job_id).status is JobStatus.INTERRUPTED
    assert [m.state is not None for m in rig.store.scan_markets(scan_id)] == [True, True, False, False]

    calls_before = len(rig.transport.calls)
    resumed = rig.jobs.resume_scan(scan_id)
    assert resumed is not None and rig.worker.run_once()
    read_again = {c.query["condition"] for c in rig.transport.calls[calls_before:] if "condition" in c.query}
    assert read_again == {USED_1, USED_2}  # the third and fourth Markets only
    assert rig.store.scan(scan_id).step is ScanStep.DONE
    assert results_without_ids(rig.store, scan_id) == uninterrupted(tmp_path)


def test_ad5_an_unexpected_error_fails_the_scan_with_no_resume(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """AD-5, Conventions › Errors: a bug makes the Scan `failed`, logged, and Resume is refused."""
    def broken(*args: object, **kwargs: object) -> object:
        raise RuntimeError("a bug in the shortlist")

    monkeypatch.setattr(scan_module.funnel, "shortlist", broken)
    scan_id, job_id = start(rig)
    rig.worker.run_once()
    job = rig.store.job(job_id)
    assert job is not None and job.status is JobStatus.FAILED and job.message == FINISHED[JobStatus.FAILED]
    assert "Scan" in caplog.text and "a bug in the shortlist" in caplog.text
    assert rig.jobs.resume_scan(scan_id) is None


def test_ad5_resume_is_refused_for_running_finished_and_unknown_scans(rig: Rig) -> None:
    """AD-5: only a stopped or interrupted Scan resumes; a queued, finished or unknown one does not."""
    scan_id, _ = start(rig)
    assert rig.jobs.resume_scan(scan_id) is None  # still queued
    rig.worker.run_once()
    assert rig.jobs.resume_scan(scan_id) is None  # finished
    assert rig.jobs.resume_scan(999) is None


def test_one_scan_at_a_time(rig: Rig) -> None:
    """FR-16, AD-5, EXPERIENCE.md ("A Scan is already running"): a second Scan is refused while one is queued or running."""
    start(rig)
    assert rig.jobs.start_scan(DAY, SIZE, seed=SEED) is None
    rig.worker.run_once()
    assert rig.jobs.start_scan(DAY, SIZE, seed=SEED) is not None  # the first one finished


@pytest.mark.parametrize("size", [0, -1, True, 2.5])
def test_a_bad_size_is_refused(rig: Rig, size: object) -> None:
    """FR-16: N is a whole number of 1 or more; nothing is stored otherwise."""
    with pytest.raises(ValueError, match="whole number"):
        rig.jobs.start_scan(DAY, size, seed=SEED)  # type: ignore[arg-type]
    assert rig.store._connection().execute("SELECT COUNT(*) FROM scan").fetchone() == (0,)


# --- lookups first ----------------------------------------------------------------------------------


def test_ad5_a_lookup_queued_during_the_market_phase_runs_before_the_next_market(rig: Rig) -> None:
    """AD-5 (Edvard, 2026-11-26): between two units of a Scan's work (here two Markets) the worker runs a waiting
    lookup first, then continues the Scan."""
    lookup_server = FakePolymarket("small-clean")
    queued: list[int] = []
    scan_answer = rig.server

    def answer(url: str, params: list[tuple[str, str]]) -> Any:
        query = dict(params)
        if query.get("condition") == CAPPED_FIRST and not queued:  # the first Market of the set is being read
            queued.append(rig.jobs.queue_lookup(SMALL))
        if query.get("user") == SMALL and "condition" not in query and not lookup_done():
            return lookup_server(url, params)
        return scan_answer(url, params)

    def lookup_done() -> bool:
        return bool(queued) and rig.store.job(queued[0]).status is JobStatus.DONE

    rig.transport.answer = answer
    start(rig)
    rig.worker.run_once()
    assert queued and rig.store.job(queued[0]).status is JobStatus.DONE
    calls = rig.transport.calls
    first_lookup = next(i for i, c in enumerate(calls) if c.query.get("user") == SMALL)
    second_market = next(i for i, c in enumerate(calls) if c.query.get("condition") == TIMED)
    assert first_lookup < second_market
    assert rig.store.latest_snapshot(SMALL) is not None  # the lookup's own window



def test_ad4_a_lookup_after_a_scan_fetches_its_own_window_and_leaves_the_scan_alone(rig: Rig) -> None:
    """AD-4, AD-19: a Wallet with only a Scan's snapshots has no lookup window; its lookup fetches one, and the
    Scan's frozen snapshots and results stay as they were."""
    scan_id, _ = start(rig)
    rig.worker.run_once()
    assert rig.store.latest_snapshot(SMALL) is None and not rig.store.has_snapshot(SMALL)
    assert rig.store.wallet_count() == 0
    results = rig.store.scan_results(scan_id)
    frozen = {(w.before_fetch_id, w.after_fetch_id) for w in rig.store.scan_wallets(scan_id) if w.wallet == SMALL}

    client, _ = live(FakePolymarket("small-clean"))
    fetch_wallet(client, rig.store, SMALL)
    lookup = rig.store.latest_snapshot(SMALL)
    assert lookup is not None and (lookup.cutoff, lookup.side) == (None, None)
    for before, after in frozen:
        assert rig.store.snapshot(before) is not None and rig.store.snapshot(after) is not None
    assert rig.store.scan_results(scan_id) == results


# --- reuse (Edvard, 2026-11-26) ----------------------------------------------------------------------


def test_fr16_a_part_is_reused_only_for_the_same_date_and_side_while_fresh(rig: Rig) -> None:
    """FR-16, AD-4 (Edvard, 2026-11-26): a Wallet's before part under 24 hours old is reused for the same date and
    side; another side, another date or 25 hours later fetches again."""
    client = rig.worker._client
    first = fetch_part(client, rig.store, SMALL, DAY, BEFORE)
    calls = len(rig.transport.calls)
    assert fetch_part(client, rig.store, SMALL, DAY, BEFORE) == first and len(rig.transport.calls) == calls
    assert fetch_part(client, rig.store, SMALL, DAY, AFTER) != first
    other_day = DAY.replace(month=6)
    other = fetch_part(client, rig.store, SMALL, other_day, BEFORE)
    assert other != first and rig.store.snapshot(other).cutoff == cutoff_at(other_day)
    rig.clock.now += 25 * HOUR
    assert fetch_part(client, rig.store, SMALL, DAY, BEFORE) not in (first, other)


def test_ad19_a_scans_frozen_snapshot_is_never_deleted_by_a_newer_fetch(rig: Rig) -> None:
    """AD-6, AD-19: a newer fetch of the same part deletes older same-key snapshots, but never one a Scan names."""
    scan_id, _ = start(rig)
    rig.worker.run_once()
    frozen = {w.wallet: w.before_fetch_id for w in rig.store.scan_wallets(scan_id)}[SMALL]
    rig.clock.now += 25 * HOUR
    newer = fetch_part(rig.worker._client, rig.store, SMALL, DAY, BEFORE)
    assert newer != frozen and rig.store.snapshot(frozen) is not None
    spare = fetch_part(rig.worker._client, rig.store, SMALL, DAY.replace(month=6), BEFORE)
    rig.clock.now += 25 * HOUR
    fetch_part(rig.worker._client, rig.store, SMALL, DAY, BEFORE)
    assert rig.store.snapshot(newer) is None  # an unfrozen older snapshot of the same part goes
    assert rig.store.snapshot(spare) is not None  # another date's part is another key


# --- the token check (deferred from 4.2) -------------------------------------------------------------


def test_ad9_an_open_row_on_an_unknown_token_makes_the_market_partial() -> None:
    """AD-9 (Story 4.2 deferred item): an OPEN holder row whose token is not one of the Market's outcomes leaves the
    Market "not used: partial" instead of ending the Scan."""
    server = FakeScan()
    server.funnel = [funnel_market(1, CUT - 86_400, 1e6)]
    server.holders = {
        (USED_1, "CLOSED"): [holder(SMALL, USED_1, "11", pnl=5)],
        (USED_1, "OPEN"): [holder(LOSERS, USED_1, "99", size=10)],
    }
    client, _ = live(server)
    market = client.funnel_markets(CUT - 90 * 86_400, CUT, 100)[0]
    read = read_candidates(client, market)
    assert (read.used, read.holders) == (False, ())


# --- the schema change keeps the Scans (AD-6) ---------------------------------------------------------


NEXT_VERSION = store_module.SCHEMA_VERSION + 1  # a schema version a later story would bring


def next_version_schema(tmp_path: Path, extra: str) -> Path:
    """schema.sql with one change, as a later story would make it."""
    text = store_module.SCHEMA_FILE.read_text(encoding="utf-8")
    text = text.replace("    side                TEXT\n);", f"    side                TEXT,\n    {extra}\n);")
    path = tmp_path / "schema_next.sql"
    path.write_text(text + "\nCREATE TABLE later_table (x INTEGER);\n", encoding="utf-8")
    return path


def finished_scan_file(tmp_path: Path) -> tuple[Path, int, list[tuple[Any, ...]], dict[str, tuple[Any, ...]]]:
    """A database with a finished Scan and a lookup snapshot; returns its path, scan id, results and frozen ids."""
    path = tmp_path / "keep.db"
    rig = rig_for(path)
    try:
        scan_id, _ = start(rig)
        rig.worker.run_once()
        fetch_wallet(live(FakePolymarket("small-clean"))[0], rig.store, SMALL)  # a lookup: cache
        frozen = {w.wallet: (w.before_fetch_id, w.after_fetch_id) for w in rig.store.scan_wallets(scan_id)}
        return path, scan_id, results_without_ids(rig.store, scan_id), frozen
    finally:
        rig.store.close()


def without_copy_test(old: sqlite3.Connection) -> None:
    """Turn a file's schema back to before Story 6.2: no Copy Test tables and no `scan.copied_at`."""
    old.execute("DROP TABLE copy_result")
    old.execute("DROP TABLE copy_sample")
    old.execute("ALTER TABLE scan DROP COLUMN copied_at")


def test_ad6_a_schema_change_keeps_scans_results_and_their_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-6: on a version mismatch the cache is rebuilt (the lookup's snapshot goes) while the Scan, its job, its
    results, its frozen snapshots with their rows and their Market records are kept."""
    path, scan_id, results, frozen = finished_scan_file(tmp_path)
    monkeypatch.setattr(store_module, "SCHEMA_VERSION", NEXT_VERSION)
    monkeypatch.setattr(store_module, "SCHEMA_FILE", next_version_schema(tmp_path, "note TEXT"))
    db = Store(path)
    try:
        assert db._connection().execute("PRAGMA user_version").fetchone() == (NEXT_VERSION,)
        scan = db.scan(scan_id)
        assert scan is not None and scan.step is ScanStep.DONE and not scan.data_rebuilt
        assert scan.job is not None and scan.job.status is JobStatus.DONE
        assert results_without_ids(db, scan_id) == results
        assert db.latest_snapshot(SMALL) is None  # the lookup's window was cache
        before, after = frozen[SMALL]
        kept = db.snapshot(before)
        assert kept is not None and kept.positions and kept.markets and db.snapshot(after) is not None
        tables = {n for (n,) in db._connection().execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "later_table" in tables and not any(n.startswith("old_") for n in tables)
        assert len(db.scan_markets(scan_id)) == 4 and len(db.scan_wallets(scan_id)) == SHORTLIST
        assert db.resolved_markets([m.condition_id for m in db.scan_markets(scan_id)]).keys() == {
            m.condition_id for m in db.scan_markets(scan_id)
        }
        # Review, Story 4.3: ids keep counting from the old file, so no id of a dropped row comes back.
        newest = max(i for pair in frozen.values() for i in pair if i is not None)
        assert fetch_wallet(live(FakePolymarket("small-clean"))[0], db, SMALL) > newest + 1
        assert Jobs(db).queue_lookup(LOSERS) > scan.job.id
    finally:
        db.close()


def test_ad6_a_schema_change_keeps_the_holdup_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-6, AD-22 (Story 5.1): a finished Scan's Hold-up group results are kept through a later schema change."""
    path = tmp_path / "groups.db"
    rig = rig_for(path)
    scan_id, _ = start(rig)
    rig.worker.run_once()
    groups = rig.store.group_results(scan_id)
    rig.store.close()
    assert [g.group for g in groups] == ["passers", "comparison"]
    monkeypatch.setattr(store_module, "SCHEMA_VERSION", NEXT_VERSION)
    monkeypatch.setattr(store_module, "SCHEMA_FILE", next_version_schema(tmp_path, "note TEXT"))
    db = Store(path)
    try:
        assert db.group_results(scan_id) == groups and db.scan(scan_id).step is ScanStep.DONE
    finally:
        db.close()


def test_ad6_a_scan_finished_before_the_holdup_test_is_kept_without_one(tmp_path: Path) -> None:
    """AD-6, FR-17 (Story 5.1, matrix "Older Scan"): a version 6 file has no `group_result` table. Its finished Scan,
    results and frozen snapshots are kept through the change to this version, with no Hold-up rows, and a new
    Scan in the same file gets its own."""
    path, scan_id, results, frozen = finished_scan_file(tmp_path)
    old = sqlite3.connect(path)
    with old:  # what Story 4.3's schema was: this one without the Hold-up table
        old.execute("DROP TABLE group_result")
        old.execute("PRAGMA user_version = 6")
    old.close()
    rig = rig_for(path)
    try:
        assert rig.store._connection().execute("PRAGMA user_version").fetchone() == (store_module.SCHEMA_VERSION,)
        scan = rig.store.scan(scan_id)
        assert scan is not None and scan.step is ScanStep.DONE and not scan.data_rebuilt
        assert results_without_ids(rig.store, scan_id) == results and rig.store.snapshot(frozen[SMALL][0]) is not None
        assert rig.store.group_results(scan_id) == ()
        new_id, _ = start(rig)
        assert rig.worker.run_once() and len(rig.store.group_results(new_id)) == 2
        assert rig.store.group_results(scan_id) == ()
    finally:
        rig.store.close()


def test_ad6_a_scan_finished_before_price_history_is_kept_whole(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AD-6, AD-24 (Story 6.1, matrix "Version 7 file with a finished Scan"): a version 7 file has no price tables.
    Opened by this version, its finished Scan is still `done` and not `data_rebuilt`, its results, Hold-up rows and
    frozen snapshots are as before, and the price tables are there and empty: the Copy Test can run on it."""
    path, scan_id, results, frozen = finished_scan_file(tmp_path)
    old = sqlite3.connect(path)
    groups = old.execute("SELECT * FROM group_result ORDER BY group_name").fetchall()
    rows = old.execute("SELECT COUNT(*) FROM activity_row WHERE fetch_id IN (SELECT after_fetch_id FROM scan_wallet)").fetchone()
    with old:  # what Story 5.1's schema was: this one without the price tables and without a Copy Test
        old.execute("DROP TABLE price_window")
        old.execute("DROP TABLE price_point")
        without_copy_test(old)
        old.execute("PRAGMA user_version = 7")
    old.close()
    assert len(groups) == 2 and store_module.SCHEMA_VERSION == 9
    with caplog.at_level(logging.WARNING, logger="liquidoracle.data.store"):
        db = Store(path)
    try:
        # The change is announced, since it takes about a minute on a large file; a new file says nothing.
        assert "from database version 7 to 9 and keeping its Scans" in caplog.text
        caplog.clear()
        Store(tmp_path / "fresh.db").close()
        assert "keeping its Scans" not in caplog.text
        assert db._connection().execute("PRAGMA user_version").fetchone() == (9,)
        scan = db.scan(scan_id)
        assert scan is not None and scan.step is ScanStep.DONE and not scan.data_rebuilt
        assert not scan.copied and db.copy_results(scan_id) == ()
        assert scan.job is not None and scan.job.status is JobStatus.DONE
        assert results_without_ids(db, scan_id) == results
        assert {w.wallet: (w.before_fetch_id, w.after_fetch_id) for w in db.scan_wallets(scan_id)} == frozen
        for before, after in frozen.values():
            assert all(db.snapshot(fetch_id) is not None for fetch_id in (before, after) if fetch_id is not None)
        connection = db._connection()
        assert connection.execute("SELECT * FROM group_result ORDER BY group_name").fetchall() == groups
        assert connection.execute(
            "SELECT COUNT(*) FROM activity_row WHERE fetch_id IN (SELECT after_fetch_id FROM scan_wallet)"
        ).fetchone() == rows
        assert db.price_windows("1") == () and db.prices("1") == ()
        db.save_prices("1", ((100, 200),), (PricePoint("1", 150, 0.5),), "clob")  # and prices can be stored in it
        assert db.prices("1") == (PricePoint("1", 150, 0.5),)
    finally:
        db.close()


def test_ad6_a_scan_finished_before_the_copy_test_is_kept_and_can_get_one(tmp_path: Path) -> None:
    """AD-6, AD-5 (Story 6.2, matrix "Version 8 file with a finished Scan"; Edvard, 2026-11-28): a version 8 file
    has stored prices but no Copy Test tables. Opened by this version, its finished Scan is still `done`, not
    `data_rebuilt` and has no Copy Test; its results, Hold-up rows, frozen snapshots and stored prices are as
    before. A Copy Test job then gives it one, asking Polymarket for prices only."""
    path, scan_id, results, frozen = finished_scan_file(tmp_path)
    old = sqlite3.connect(path)
    groups = old.execute("SELECT * FROM group_result ORDER BY group_name").fetchall()
    windows = old.execute("SELECT * FROM price_window ORDER BY token_id, start_at").fetchall()
    points = old.execute("SELECT * FROM price_point ORDER BY token_id, t").fetchall()
    with old:  # what Story 6.1's schema was
        without_copy_test(old)
        old.execute("PRAGMA user_version = 8")
    old.close()
    assert windows and store_module.SCHEMA_VERSION == 9
    rig = rig_for(path)
    try:
        db = rig.store
        connection = db._connection()
        assert connection.execute("PRAGMA user_version").fetchone() == (9,)
        scan = db.scan(scan_id)
        assert scan is not None and scan.step is ScanStep.DONE and not scan.data_rebuilt
        assert not scan.copied and db.copy_results(scan_id) == ()
        assert results_without_ids(db, scan_id) == results
        assert {w.wallet: (w.before_fetch_id, w.after_fetch_id) for w in db.scan_wallets(scan_id)} == frozen
        assert connection.execute("SELECT * FROM group_result ORDER BY group_name").fetchall() == groups
        assert connection.execute("SELECT * FROM price_window ORDER BY token_id, start_at").fetchall() == windows
        assert connection.execute("SELECT * FROM price_point ORDER BY token_id, t").fetchall() == points

        with db._write() as raw:  # as for a Scan from before any price was fetched: the job must ask for them
            raw.execute("DELETE FROM price_point")
            raw.execute("DELETE FROM price_window")
        job_id = rig.jobs.start_copy_test(scan_id)
        assert job_id is not None and rig.worker.run_once()
        assert db.job(job_id).status is JobStatus.DONE and db.scan(scan_id).copied
        asked = [call for call in rig.transport.calls if call.query["market"] != PROBE_TOKEN]
        assert len(asked) == len(windows) > 0 and db.copy_results(scan_id)
        assert all(call.url.endswith("/prices-history") for call in rig.transport.calls)  # prices and nothing else
        assert connection.execute("SELECT * FROM price_window ORDER BY token_id, start_at").fetchall() == windows
        assert results_without_ids(db, scan_id) == results
    finally:
        rig.store.close()


def test_fr18a_the_copy_phase_prices_a_real_wallet_through_the_live_client(tmp_path: Path) -> None:
    """FR-18a, AD-24 (Story 6.2 review): with the live client, a Scan's Copy phase asks the old price route for the
    sampled buys' windows and prices the Positions Polymarket has a price for. Here Polymarket has prices for one
    token only: that Position is priced at every delay, and every other one is left out and counted."""
    plain = rig_for(tmp_path / "plain.db")
    try:
        scan_id, _ = start(plain)
        plain.worker.run_once()
        assert all(r.priced == 0 for copy in plain.store.copy_results(scan_id) for r in copy.delays)
        chosen = next(w for w in scan_module.copy_wallets(plain.store, scan_id) if w.sample)
        (key, rows), *_ = chosen.fills.items()
    finally:
        plain.store.close()
    server = scenario()
    server.prices[key[1]] = [(row.timestamp + m * 60, 0.25) for row in rows for m in range(-2, 33)]
    rig = rig_for(tmp_path / "priced.db", server)
    try:
        scan_id, _ = start(rig)
        rig.worker.run_once()
        result = next(copy for copy in rig.store.copy_results(scan_id) if copy.wallet == chosen.wallet)
        assert [(r.priced, r.left_out) for r in result.delays] == [(1, result.sampled - 1)] * 3
        assert all(r.spent > 0 and r.follower_return is not None for r in result.delays)
        assert {p.price for p in rig.store.prices(key[1])} == {0.25}
        routes = rig.store._connection().execute("SELECT DISTINCT route FROM price_window").fetchall()
        assert routes == [("clob",)]
    finally:
        rig.store.close()


def test_ad5_an_outage_of_the_price_route_stops_the_scan_in_the_copy_phase(tmp_path: Path) -> None:
    """AD-5, AD-3 (Story 6.2 review): with the live client, the price route answering 503 on every try stops the
    Scan in the Copy phase with nothing stored for that request; the Scan is not finished. When Polymarket is back,
    Resume finishes it with the same results as a run with no outage."""
    rig = rig_for(tmp_path / "scan.db")
    try:
        rig.server.price_answer = status(503)
        scan_id, job_id = start(rig)
        rig.worker.run_once()
        job = rig.store.job(job_id)
        assert (job.status, job.phase, job.done) == (JobStatus.STOPPED, "copy", 0) and job.total > 0
        assert rig.store.scan(scan_id).step is ScanStep.RANKED and not rig.store.scan(scan_id).copied
        assert rig.store._connection().execute("SELECT COUNT(*) FROM price_window").fetchone() == (0,)
        rig.server.price_answer = None
        assert rig.jobs.resume_scan(scan_id) is not None and rig.worker.run_once()
        assert rig.store.scan(scan_id).step is ScanStep.DONE and rig.store.scan(scan_id).copied
        assert results_without_ids(rig.store, scan_id) == uninterrupted(tmp_path)
    finally:
        rig.store.close()


def test_ad6_a_schema_change_keeps_the_copy_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-6, AD-22 (Story 6.2): a later schema change keeps a Scan's Copy rows and the time it got them."""
    path, scan_id, results, _ = finished_scan_file(tmp_path)
    db = Store(path)
    copies, copied_at = db.copy_results(scan_id), db.scan(scan_id).copied_at
    db.close()
    assert copies and copied_at is not None
    monkeypatch.setattr(store_module, "SCHEMA_VERSION", NEXT_VERSION)
    monkeypatch.setattr(store_module, "SCHEMA_FILE", next_version_schema(tmp_path, "note TEXT"))
    db = Store(path)
    try:
        assert db._connection().execute("PRAGMA user_version").fetchone() == (NEXT_VERSION,)
        assert db.copy_results(scan_id) == copies and db.scan(scan_id).copied_at == copied_at
        assert results_without_ids(db, scan_id) == results and not db.scan(scan_id).data_rebuilt
    finally:
        db.close()


def test_ad6_a_schema_change_keeps_the_stored_prices(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-6, AD-4, AD-24 (Story 6.1): stored price windows and points never expire, so a later schema change
    keeps all of them, the empty and refused windows too, beside the Scan."""
    path, scan_id, results, _ = finished_scan_file(tmp_path)
    db = Store(path)
    db.save_prices("1", ((100, 200), (500, 600)), (PricePoint("1", 150, 0.5), PricePoint("1", 600, 0.25)), "clob")
    db.save_prices("2", ((100, 200),), (), "refused")
    windows = db._connection().execute("SELECT * FROM price_window ORDER BY token_id, start_at").fetchall()
    db.close()
    monkeypatch.setattr(store_module, "SCHEMA_VERSION", NEXT_VERSION)
    monkeypatch.setattr(store_module, "SCHEMA_FILE", next_version_schema(tmp_path, "note TEXT"))
    db = Store(path)
    try:
        assert db._connection().execute("PRAGMA user_version").fetchone() == (NEXT_VERSION,)
        assert db._connection().execute("SELECT * FROM price_window ORDER BY token_id, start_at").fetchall() == windows
        assert db.prices("1") == (PricePoint("1", 150, 0.5), PricePoint("1", 600, 0.25))
        assert db.price_windows("2") == ((100, 200),) and db.prices("2") == ()
        assert results_without_ids(db, scan_id) == results and not db.scan(scan_id).data_rebuilt
    finally:
        db.close()


def test_ad6_a_disk_error_during_the_change_leaves_the_file_as_it_was(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-6 (review, Story 6.1): only a snapshot the new schema refuses marks a Scan `data_rebuilt`. Any other
    failure while the snapshots are copied, a full disk for one, is raised and the whole change rolled back: the
    file keeps its old version, and opened again once the cause is gone, the Scan and its snapshots are all there."""
    path, scan_id, results, frozen = finished_scan_file(tmp_path)
    real_copy = store_module._copy

    def full_disk(db: sqlite3.Connection, name: str, where: str = "") -> None:
        if name == "activity_row":
            raise sqlite3.OperationalError("database or disk is full")
        real_copy(db, name, where)

    with monkeypatch.context() as patched:
        patched.setattr(store_module, "SCHEMA_VERSION", NEXT_VERSION)
        patched.setattr(store_module, "SCHEMA_FILE", next_version_schema(tmp_path, "note TEXT"))
        patched.setattr(store_module, "_copy", full_disk)
        with pytest.raises(store_module.StoreError, match="disk is full"):
            Store(path)
    db = Store(path)  # the current version again: nothing was changed
    try:
        assert db._connection().execute("PRAGMA user_version").fetchone() == (store_module.SCHEMA_VERSION,)
        scan = db.scan(scan_id)
        assert scan is not None and scan.step is ScanStep.DONE and not scan.data_rebuilt
        assert results_without_ids(db, scan_id) == results
        assert all(db.snapshot(i) is not None for pair in frozen.values() for i in pair if i is not None)
        assert db.latest_snapshot(SMALL) is not None  # even the lookup's cache is untouched
    finally:
        db.close()


def test_ad6_snapshots_that_cannot_be_copied_mark_the_scan_data_rebuilt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-6: when a schema change cannot copy the snapshots (a new column with no default), the Scans and results
    are kept without them, marked `data_rebuilt`, and cannot resume."""
    path, scan_id, results, frozen = finished_scan_file(tmp_path)
    monkeypatch.setattr(store_module, "SCHEMA_VERSION", NEXT_VERSION)
    monkeypatch.setattr(store_module, "SCHEMA_FILE", next_version_schema(tmp_path, "extra TEXT NOT NULL"))
    db = Store(path)
    try:
        scan = db.scan(scan_id)
        assert scan is not None and scan.data_rebuilt
        assert results_without_ids(db, scan_id) == results
        assert db.snapshot(frozen[SMALL][0]) is None
        assert db._connection().execute("SELECT COUNT(*) FROM snapshot").fetchone() == (0,)
        assert Jobs(db).resume_scan(scan_id) is None
        # Review, Story 4.3: a new snapshot never takes a stale frozen id of the rebuilt Scan.
        new = db._connection().execute(  # the new schema's own writer would fill `extra`
            "INSERT INTO snapshot (wallet, window_limit, started_at, extra) VALUES (?, 2000, 1, 'x')", (LOSERS,)
        ).lastrowid
        stale = {i for pair in frozen.values() for i in pair if i is not None}
        assert new > max(stale) and db.snapshot(max(stale)) is None
    finally:
        db.close()


def test_ad6_an_interrupted_scan_still_resumes_after_a_schema_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-5, AD-6: a stopped Scan kept through a schema change resumes from what was stored."""
    path = tmp_path / "stopped.db"
    rig = rig_for(path)
    rig.server.refuse[REFUSED] = status(503)
    scan_id, _ = start(rig)
    rig.worker.run_once()
    rig.store.close()
    monkeypatch.setattr(store_module, "SCHEMA_VERSION", NEXT_VERSION)
    monkeypatch.setattr(store_module, "SCHEMA_FILE", next_version_schema(tmp_path, "note TEXT"))
    rig.server.refuse[REFUSED] = status(400, b'{"error": "bad request"}')
    reopened = Store(path, clock=rig.clock)
    try:
        jobs = Jobs(reopened)
        assert jobs.resume_scan(scan_id) is not None
        assert Worker(rig.worker._client, jobs).run_once()
        assert reopened.scan(scan_id).step is ScanStep.DONE
        assert user_calls(rig.transport, CONTRACT) == 1
    finally:
        reopened.close()


# --- the pre-filter sums ------------------------------------------------------------------------------


def test_ad21_stored_estimates_equal_the_in_memory_funnels_exactly(rig: Rig) -> None:
    """AD-21, Story 4.3: Market terms added one Market at a time in the store equal `funnel.estimates` bit for bit."""
    scan_id, _ = start(rig)
    rig.worker.run_once()
    expected = run_funnel(live(scenario())[0], DAY, SIZE)
    assert rig.store.scan_candidates(scan_id) == {c.wallet: c.estimate for c in expected.shortlist}


def test_ad21_estimates_add_each_markets_terms_in_set_order() -> None:
    """AD-21: `estimates` is the sum of each Market's `market_terms`, in the order the Markets are given."""
    yes_no = Market(USED_1, True, 1, ("11", "12"), (1.0, 0.0), False)
    other = dataclasses.replace(yes_no, condition_id=USED_2, token_ids=("21", "22"))
    rows_1 = [funnel_holder(SMALL, "11", "CLOSED", pnl=0.1), funnel_holder(SMALL, "11", "CLOSED", pnl=0.2)]
    rows_2 = [funnel_holder(SMALL, "22", "OPEN", size=10, avg=0.3)]
    terms_1 = funnel.market_terms(rows_1, yes_no)
    terms_2 = funnel.market_terms(rows_2, other)
    assert terms_1 == {SMALL: pytest.approx(0.3)}
    assert terms_2 == {SMALL: pytest.approx(-3.0)}
    assert funnel.estimates({USED_1: rows_1, USED_2: rows_2}, {USED_1: yes_no, USED_2: other}) == {
        SMALL: 0.0 + terms_1[SMALL] + terms_2[SMALL]
    }


def funnel_holder(wallet: str, token: str, status_: str, *, pnl: float = 0.0, size: float = 0.0, avg: float = 0.5) -> MarketHolder:
    return MarketHolder(wallet, token, status_, pnl, size, avg)


def test_the_funnel_market_record_is_stored_with_the_scan(rig: Rig) -> None:
    """AD-21: the Market set's Gamma records are stored, so a resumed Scan prices its holders without asking again."""
    scan_id, _ = start(rig)
    rig.worker.run_once()
    ids = [m.condition_id for m in rig.store.scan_markets(scan_id)]
    assert ids[:2] == [CAPPED_FIRST, TIMED] and set(rig.store.resolved_markets(ids)) == set(ids)


def split_parts(wallet: SampleWallet) -> tuple[Snapshot, Snapshot]:
    """A Wallet's data cut into two parts at its middle Market's resolution time, as a before and an after part."""
    closed = sorted(m.closed_time or 0 for m in wallet.markets)
    middle = closed[len(closed) // 2]
    parts = []
    for fetch_id, side, keep in ((1, BEFORE, lambda at: at < middle), (2, AFTER, lambda at: at >= middle)):
        markets = tuple(m for m in wallet.markets if keep(m.closed_time or 0))
        ids = {m.condition_id for m in markets}
        parts.append(Snapshot(
            fetch_id, wallet.address, 0, tuple(p for p in wallet.positions if p.condition_id in ids),
            tuple(a for a in wallet.activity if a.condition_id in ids), markets, WINDOW_LIMIT, None, False, middle, side,
        ))
    return parts[0], parts[1]


def test_ad22_scan_whole_tests_both_parts_together() -> None:
    """AD-22, FR-16: `scan_whole` tests the before and after parts together and `scan_before` the before part alone:
    on the sharp trader split in two, the whole's tested count and Real PnL are the two parts' sums."""
    sharp = next(w for w in synthetic.small_wallets() if w.address.startswith("0x2ccde450"))
    before, after = split_parts(sharp)
    row = ScanWallet(0, sharp.address, 0.0, WalletOutcome.RANKED, 0.0, False, before.fetch_id, after.fetch_id, True)
    first, whole = scan_results(row, before, after, seed=SEED)
    only_after = scan_results(dataclasses.replace(row, before_fetch_id=after.fetch_id), after, None, seed=SEED)[0]
    assert (first.scope, whole.scope) == (SCAN_BEFORE, SCAN_WHOLE)
    assert first.tested_count > 0 and only_after.tested_count > 0
    # Every bet but the 3 anchor bets, sold before resolution (Story 4.6).
    assert whole.tested_count == first.tested_count + only_after.tested_count == len(sharp.positions) - len(synthetic.ANCHORS)
    assert whole.real_pnl == pytest.approx(first.real_pnl + only_after.real_pnl, abs=0.005)
    assert (whole.fetch_id, whole.after_fetch_id, first.after_fetch_id) == (1, 2, None)
    assert not whole.not_fully_read


# --- review, Story 4.3 ---------------------------------------------------------------------------------


def lookup_rig(rig: Rig, queue_when: Any, wallet: str) -> list[tuple[int, int]]:
    """Make the fake queue a lookup of `wallet` the first time `queue_when(query)` is true; returns
    [(lookup job id, index of the call that queued it)] once it has."""
    queued: list[tuple[int, int]] = []
    serve = rig.server

    def answer(url: str, params: list[tuple[str, str]]) -> Any:
        if not queued and queue_when(dict(params)):
            queued.append((rig.jobs.queue_lookup(wallet), len(rig.transport.calls) - 1))
        return serve(url, params)

    rig.transport.answer = answer
    return queued


def scan_phase(rig: Rig) -> str | None:
    job = rig.store._connection().execute("SELECT phase FROM job WHERE kind = 'scan' ORDER BY id DESC").fetchone()
    return None if job is None else job[0]


def test_ad5_a_lookup_queued_while_a_wallet_is_read_runs_before_the_next_wallet(rig: Rig) -> None:
    """AD-5 (review, Story 4.3): a lookup queued while the 3rd shortlisted Wallet is read runs before the 4th."""
    queued = lookup_rig(rig, lambda q: q.get("user") == LOSERS, SMALL)
    start(rig)
    rig.worker.run_once()
    assert queued and rig.store.job(queued[0][0]).status is JobStatus.DONE
    calls, at = rig.transport.calls, queued[0][1]
    lookup_call = next(i for i, c in enumerate(calls) if i > at and c.query.get("user") == SMALL)
    next_wallet = next(i for i, c in enumerate(calls) if c.query.get("user") == FEES)
    assert lookup_call < next_wallet
    assert rig.store.latest_snapshot(SMALL) is not None


def test_ad5_a_lookup_queued_during_the_skill_tests_runs_before_the_next_wallet(rig: Rig) -> None:
    """AD-5 (review, Story 4.3): a lookup queued while the first top Wallet's after part is read runs before the next
    top Wallet's after part."""
    queued = lookup_rig(rig, lambda q: scan_phase(rig) == "skill_tests" and q.get("user") == SMALL, LOSERS)
    scan_id, _ = start(rig)
    rig.worker.run_once()
    assert queued and rig.store.job(queued[0][0]).status is JobStatus.DONE
    tops = [w.wallet for w in rig.store.scan_wallets(scan_id) if w.top and w.before_fetch_id is not None]
    assert tops[0] == SMALL and len(tops) == 2
    calls, at = rig.transport.calls, queued[0][1]
    lookup_call = next(i for i, c in enumerate(calls) if i > at and c.query.get("user") == LOSERS)
    next_top = next(i for i, c in enumerate(calls) if i > at and c.query.get("user") == tops[1])
    assert lookup_call < next_top


def test_ad5_an_outage_in_the_skill_test_phase_resumes_without_testing_twice(tmp_path: Path) -> None:
    """FR-16, AD-5, AD-19 (review, Story 4.3): Polymarket not answering on the last top Wallet's after part stops the
    Scan in `skill_tests` at "2 of 3"; Resume reads no finished top Wallet again and the results equal an
    uninterrupted run's."""
    rig = rig_for(tmp_path / "scan.db")
    serve, down = rig.server, [True]
    scan_id, job_id = start(rig)
    tops: list[str] = []

    def answer(url: str, params: list[tuple[str, str]]) -> Any:
        query = dict(params)
        if down[0] and scan_phase(rig) == "skill_tests":
            if not tops:
                tops.extend(w.wallet for w in rig.store.scan_wallets(scan_id) if w.top)
            if query.get("user") == tops[-1]:
                return status(503)
        return serve(url, params)

    rig.transport.answer = answer
    rig.worker.run_once()
    job = rig.store.job(job_id)
    assert job is not None and job.status is JobStatus.STOPPED
    assert (job.phase, job.done, job.total) == ("skill_tests", 2, 3)
    assert rig.store.tested_wallets(scan_id) == set(tops[:2])

    down[0] = False
    calls_before = len(rig.transport.calls)
    assert rig.jobs.resume_scan(scan_id) is not None and rig.worker.run_once()
    assert rig.store.scan(scan_id).step is ScanStep.DONE
    for finished in tops[:2]:
        assert user_calls(rig.transport, finished, calls_before) == 0, finished
    assert results_without_ids(rig.store, scan_id) == uninterrupted(tmp_path)
    rig.store.close()


def test_fr16_a_second_scan_on_the_same_date_reuses_fresh_parts(rig: Rig) -> None:
    """FR-16, AD-4 (Edvard, 2026-11-26; review, Story 4.3): a second Scan of the same date within 24 hours reads no
    stored Wallet part again: the ranked Wallets make no request and keep their snapshots."""
    first, _ = start(rig)
    rig.worker.run_once()
    calls_before = len(rig.transport.calls)
    second, _ = start(rig)
    rig.worker.run_once()
    assert rig.store.scan(second).step is ScanStep.DONE
    stored = {w.wallet: (w.before_fetch_id, w.after_fetch_id) for w in rig.store.scan_wallets(first)}
    again = {w.wallet: (w.before_fetch_id, w.after_fetch_id) for w in rig.store.scan_wallets(second)}
    read = [w for w, (before, _) in stored.items() if before is not None]
    assert SMALL in read and LOSERS in read
    for wallet in read:
        assert user_calls(rig.transport, wallet, calls_before) == 0, wallet
        assert again[wallet] == stored[wallet]
    assert results_without_ids(rig.store, second) == results_without_ids(rig.store, first)


def test_ad9_a_refused_after_part_flags_only_the_whole_result() -> None:
    """AD-9, AD-22 (review, Story 4.3): when Polymarket refuses a top Wallet's after part, `scan_whole` rests on the
    before part alone and is flagged "not fully read"; `scan_before` is not flagged."""
    sharp = next(w for w in synthetic.small_wallets() if w.address.startswith("0x2ccde450"))
    before, _ = split_parts(sharp)
    row = ScanWallet(0, sharp.address, 0.0, WalletOutcome.RANKED, 0.0, False, before.fetch_id, None, True)
    first, whole = scan_results(row, before, None, seed=SEED, refused_after=True)
    assert not first.not_fully_read and whole.not_fully_read
    assert whole.tested_count == first.tested_count and whole.after_fetch_id is None


def test_ad19_markets_resolved_after_the_as_of_time_are_left_out(rig: Rig) -> None:
    """AD-19 (review, Story 4.3): a part's Markets resolved at or after the Scan's as-of time are left out of its
    results, so a Scan resumed days later tests what an uninterrupted run would have."""
    sharp = next(w for w in synthetic.small_wallets() if w.address.startswith("0x2ccde450"))
    before, after = split_parts(sharp)
    row = ScanWallet(0, sharp.address, 0.0, WalletOutcome.RANKED, 0.0, False, before.fetch_id, after.fetch_id, True)
    closing = sorted(m.closed_time for m in after.markets if m.closed_time is not None)
    as_of = closing[len(closing) // 2]
    first, whole = scan_results(row, before, after, seed=SEED, as_of=as_of)
    full = scan_results(row, before, after, seed=SEED)[1]
    kept = sum(1 for p in after.positions if {m.condition_id: m.closed_time for m in after.markets}[p.condition_id] < as_of)
    assert 0 < kept < len(after.positions)
    assert whole.tested_count == first.tested_count + kept < full.tested_count
    assert scan_results(row, before, after, seed=SEED, as_of=closing[-1] + 1)[1] == full


def test_ad19_run_scan_uses_the_scans_as_of_time(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-19 (review, Story 4.3): the Skill Test phase passes the Scan's own as-of time (its creation) to the results."""
    seen: list[int | None] = []
    original = scan_module.scan_results

    def spy(*args: Any, **kwargs: Any) -> Any:
        seen.append(kwargs.get("as_of"))
        return original(*args, **kwargs)

    monkeypatch.setattr(scan_module, "scan_results", spy)
    scan_id, _ = start(rig)
    rig.clock.now += 3 * 24 * HOUR  # the job runs days after the Scan was created
    rig.worker.run_once()
    assert seen and set(seen) == {rig.store.scan(scan_id).as_of}
