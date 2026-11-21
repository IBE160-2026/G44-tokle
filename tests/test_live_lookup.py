"""Live lookups: jobs, the worker, freshness and the outage pages (FR-1, FR-2, AD-4, AD-5, UX-DR22, UX-DR23; Story 2.5).

The worker runs against a fake Polymarket (`tests/fake_polymarket.py`) with sockets blocked; tests call
`Worker.run_once()` instead of starting the thread, except where the thread itself is checked. The
store's clock is a plain number the tests move, so "24 hours later" takes no time.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from flask.testing import FlaskClient

import liquidoracle.__main__ as cli
from liquidoracle.core import phrases
from liquidoracle.data import synthetic
from liquidoracle.data.errors import NoPolymarketHistory
from liquidoracle.data.polymarket import PolymarketClient, TransportTimeout
from liquidoracle.data.store import INTERRUPTED_MESSAGE, LIVE_DB, NO_HISTORY, JobStatus, Store, StoreError
from liquidoracle.data.window import WINDOW_LIMIT, positions_near
from liquidoracle.services import jobs as jobs_module
from liquidoracle.services.fetch import fetch_wallet
from liquidoracle.services.jobs import FETCHING, Jobs, Worker
from liquidoracle.services.lookup import FRESH_FOR, PROFILE_HINT, RETRY_AFTER, Lookup, Outcome
from liquidoracle.settings import Settings
from liquidoracle.web import create_app
from fake_polymarket import FakeClock, FakePolymarket, FakeTransport, page, status

SEED = 44
HOUR = 60 * 60
START = 1_790_000_000  # the store clock's starting time (Sep 2026)


class Clock:
    """The store's wall clock: a number the test moves."""

    def __init__(self) -> None:
        self.now = float(START)

    def __call__(self) -> float:
        return self.now


@dataclass
class Live:
    """A live run in miniature: store, job queue, worker, lookup, pages and the fake Polymarket behind them."""

    store: Store
    clock: Clock
    transport: FakeTransport
    jobs: Jobs
    worker: Worker
    lookup: Lookup
    web: FlaskClient
    wallet: str


def live_run(tmp_path: Path, fake: Any, wallet: str) -> Live:
    clock = Clock()
    store = Store(tmp_path / "live.db", clock=clock)
    fake_clock = FakeClock()
    transport = FakeTransport(answer=fake, clock=fake_clock)
    client = PolymarketClient(5.0, transport=transport, clock=fake_clock, sleep=fake_clock.sleep)
    jobs = Jobs(store)
    lookup = Lookup(None, store, seed=SEED, jobs=jobs)
    web = create_app(Settings(offline=False), lookup).test_client()
    return Live(store, clock, transport, jobs, Worker(client, jobs), lookup, web, wallet)


@pytest.fixture
def run(tmp_path: Path) -> Iterator[Live]:
    """A live run whose Polymarket serves the real fixture Wallet 0x29306d (small-clean)."""
    fake = FakePolymarket("small-clean")
    live = live_run(tmp_path, fake, fake.wallet)
    yield live
    live.store.close()


def empty_lists(url: str, params: list[tuple[str, str]]) -> Any:
    """Polymarket's answer for an address it has never seen: 200 and no rows (checked live, 2026-11-21)."""
    if url.endswith("/v2/positions") or url.endswith("/v2/activity"):
        return page([])
    raise AssertionError(f"unexpected request {url}")


def always_times_out(url: str, params: list[tuple[str, str]]) -> Any:
    raise TransportTimeout("fake: Polymarket is down")


def html(web: FlaskClient, url: str, code: int = 200) -> str:
    reply = web.get(url)
    assert reply.status_code == code, (url, reply.status_code)
    return reply.get_data(as_text=True)


def h1s(text: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<h1[^>]*>(.*?)</h1>", text, re.S)]


def open_page(live: Live) -> tuple[int, str]:
    """GET /wallet/<a>: (the job id it redirected to, the fetching page)."""
    reply = live.web.get(f"/wallet/{live.wallet}")
    assert reply.status_code == 302, reply.status_code
    match = re.fullmatch(rf"/wallet/{live.wallet}\?job=(\d+)", reply.headers["Location"])
    assert match, reply.headers["Location"]
    return int(match.group(1)), html(live.web, reply.headers["Location"])


def short(address: str) -> str:
    return f"{address[:6]}…{address[-4:]}"


# --- first and second lookup (FR-2, AD-4, AD-5, UX-DR22) -----------------------------------------


def test_ux_dr22_first_lookup_queues_a_job_and_shows_the_fetching_state(run: Live) -> None:
    """AD-5, UX-DR22: no snapshot -> a queued job, and the page shows "Checking …", the indicator,
    "Fetching trades from Polymarket…" and a plain reload link for pages without JavaScript."""
    job_id, text = open_page(run)
    job = run.store.job(job_id)
    assert job is not None and (job.status, job.kind, job.wallet) == (JobStatus.QUEUED, "lookup", run.wallet)
    assert h1s(text) == [f"Checking {short(run.wallet)}"]
    assert '<span class="fetch-dots" aria-hidden="true">' in text
    assert '<p class="fetching" role="status">' in text and "Fetching trades from Polymarket…" in text
    assert f'<a href="/wallet/{run.wallet}?job={job_id}">Reload this page</a>' in text
    assert '<script src="/static/js/progress.js" defer></script>' in text
    assert f'data-progress="/jobs/{job_id}/progress"' in text
    assert run.transport.calls == []  # a page never talks to Polymarket (AD-5)


def test_fr2_worker_fetches_then_the_page_shows_the_verdict(run: Live) -> None:
    """AD-5, FR-2: the worker runs the job through the fetch pipeline; the job's page then shows the card."""
    job_id, _ = open_page(run)
    assert run.worker.run_once() is True
    job = run.store.job(job_id)
    assert job is not None and job.status is JobStatus.DONE and (job.done, job.total) == (1, 1)
    text = html(run.web, f"/wallet/{run.wallet}?job={job_id}")
    assert h1s(text)[0].startswith("Verdict: ")
    assert phrases.stored_at(START) in text
    assert run.worker.run_once() is False  # nothing left


def test_fr2_second_lookup_within_24_hours_makes_no_network_call(run: Live) -> None:
    """FR-2, AD-4: within 24 hours of a complete snapshot, the lookup shows the card at once:
    no job, and 0 calls through the fake transport."""
    assert FRESH_FOR == 24 * HOUR  # AD-4's 24 hours
    open_page(run)
    run.worker.run_once()
    calls = len(run.transport.calls)
    run.clock.now += 3 * HOUR
    assert html(run.web, f"/wallet/{run.wallet}").count("Data stored") == 1
    run.clock.now = START + 24 * HOUR - 1
    text = html(run.web, f"/wallet/{run.wallet}")
    assert h1s(text)[0].startswith("Verdict: ") and phrases.stored_at(START) in text
    assert run.store.claim_next_job() is None  # no job was queued
    assert len(run.transport.calls) == calls


def test_ad4_a_snapshot_25_hours_old_is_fetched_again_and_replaced(run: Live) -> None:
    """AD-4: a snapshot over 24 hours old is stale: a new job, and its snapshot replaces the old one."""
    open_page(run)
    run.worker.run_once()
    first = run.store.latest_snapshot(run.wallet)
    run.clock.now += 25 * HOUR
    job_id, _ = open_page(run)
    run.worker.run_once()
    second = run.store.latest_snapshot(run.wallet)
    assert first is not None and second is not None and second.fetch_id > first.fetch_id
    assert second.completed_at == START + 25 * HOUR
    assert phrases.stored_at(second.completed_at) in html(run.web, f"/wallet/{run.wallet}?job={job_id}")
    rows = sqlite3.connect(run.store.path).execute("SELECT COUNT(*) FROM snapshot").fetchone()
    assert rows == (1,)  # the old snapshot is gone (Story 1.6's rule)


def test_ad4_only_the_lookup_view_serves_a_lookup(run: Live) -> None:
    """AD-4: a snapshot of another window (e.g. a future Scan's) never serves the lookup view."""
    snapshot = positions_near(run.worker._client, run.wallet, limit=5)  # noqa: SLF001 - the test's own client
    fetch_id = run.store.begin_snapshot(run.wallet, window_limit=5)
    run.store.add_positions(fetch_id, snapshot.positions)
    run.store.add_activity(fetch_id, snapshot.activity)
    run.store.save_markets(snapshot.markets)
    run.store.finish_snapshot(fetch_id)
    assert run.store.serving_snapshot(run.wallet, window_limit=WINDOW_LIMIT, max_age=FRESH_FOR) is None
    assert run.store.snapshot_time(run.wallet, window_limit=WINDOW_LIMIT) is None
    assert run.lookup.wallet_page(run.wallet).outcome is Outcome.QUEUED


def test_ad5_reload_during_a_fetch_joins_the_same_job(run: Live) -> None:
    """AD-5: a lookup while the Wallet's job is queued or running joins it; no second job."""
    first, _ = open_page(run)
    again, _ = open_page(run)
    assert again == first
    assert run.store.claim_job(first)
    assert open_page(run)[0] == first  # running: still the same job
    assert html(run.web, f"/wallet/{run.wallet}?job={first}").count("Checking ") >= 1


# --- no history (FR-1, UX-DR23) -----------------------------------------------------------------


def test_ux_dr23_no_polymarket_history(tmp_path: Path) -> None:
    """FR-1, UX-DR23: both positions lists empty -> the job ends done with no_history, nothing is stored,
    and the page has the heading, the sentence, the profile-page hint and a link back."""
    address = "0x17cfc9628308612276a58d9b9804e40eb50707fa"  # the random address of the 2026-11-21 probe
    live = live_run(tmp_path, empty_lists, address)
    job_id, _ = open_page(live)
    live.worker.run_once()
    job = live.store.job(job_id)
    assert job is not None and (job.status, job.result) == (JobStatus.DONE, NO_HISTORY)
    assert live.store.latest_snapshot(address) is None
    text = html(live.web, f"/wallet/{address}?job={job_id}")
    assert h1s(text) == ["No Polymarket history found"]
    assert "No Polymarket history found for this address." in text
    assert PROFILE_HINT in text and PROFILE_HINT.startswith("Use the address shown on the Polymarket profile page.")
    assert '<a href="/">Check a wallet</a>' in text
    assert "verdict-card" not in text
    live.store.close()


def test_window_raises_no_history_only_when_both_lists_are_empty(tmp_path: Path) -> None:
    """FR-1: positions_near raises NoPolymarketHistory for two empty lists, before asking for any activity."""
    fake_clock = FakeClock()
    transport = FakeTransport(answer=empty_lists, clock=fake_clock)
    client = PolymarketClient(5.0, transport=transport, clock=fake_clock, sleep=fake_clock.sleep)
    with pytest.raises(NoPolymarketHistory):
        positions_near(client, "0x" + "ab" * 20)
    assert [call.url.rsplit("/", 1)[-1] for call in transport.calls] == ["positions", "positions"]


def test_only_open_bets_get_a_normal_not_enough_data_verdict(tmp_path: Path) -> None:
    """FR-1, FR-10: lists that are not empty but give an empty window (no resolved Market) are history:
    a normal *Not enough data* Verdict with 0 resolved bets, not the no-history page."""
    fake = FakePolymarket("small-clean")
    fake.gamma = []  # Gamma knows none of its Markets, so none is in the window
    live = live_run(tmp_path, fake, fake.wallet)
    job_id, _ = open_page(live)
    live.worker.run_once()
    text = html(live.web, f"/wallet/{live.wallet}?job={job_id}")
    assert h1s(text) == ["Verdict: Not enough data"]
    assert phrases.not_enough_data(0) in text
    live.store.close()


# --- Polymarket not answering (FR-2, AD-4, UX-DR23) ------------------------------------------------


def test_ux_dr23_outage_offers_the_stored_snapshot_of_this_view(tmp_path: Path) -> None:
    """FR-2, AD-4, UX-DR23: Polymarket down and a 3-day-old snapshot of this view -> the job stops, the page
    says "Polymarket did not answer" with "Show stored data from …", and the button shows that card."""
    fake = FakePolymarket("small-clean")
    live = live_run(tmp_path, fake, fake.wallet)
    open_page(live)
    live.worker.run_once()
    live.clock.now += 3 * 24 * HOUR
    live.transport.answer = always_times_out
    job_id, _ = open_page(live)
    live.worker.run_once()
    job = live.store.job(job_id)
    assert job is not None and job.status is JobStatus.STOPPED
    text = html(live.web, f"/wallet/{live.wallet}?job={job_id}")
    assert h1s(text) == ["Polymarket did not answer"]
    button = f'<a class="btn-primary btn-link" href="/wallet/{live.wallet}?stored=1">Show stored data from {phrases.stored_on(START)}</a>'
    assert button in text
    assert "Try again in a few minutes." not in text
    stored = html(live.web, f"/wallet/{live.wallet}?stored=1")
    assert h1s(stored)[0].startswith("Verdict: ") and phrases.stored_at(START) in stored
    live.store.close()


def test_ux_dr23_outage_with_nothing_stored_says_try_again(tmp_path: Path) -> None:
    """UX-DR23: Polymarket down and no snapshot of this view -> "Try again in a few minutes.", no button;
    `?stored=1` with nothing stored falls back to the usual lookup."""
    live = live_run(tmp_path, always_times_out, "0x" + "cd" * 20)
    job_id, _ = open_page(live)
    live.worker.run_once()
    text = html(live.web, f"/wallet/{live.wallet}?job={job_id}")
    assert h1s(text) == ["Polymarket did not answer"]
    assert "Try again in a few minutes." in text and "Show stored data" not in text
    assert live.web.get(f"/wallet/{live.wallet}?stored=1").status_code == 302  # nothing stored: a new lookup
    live.store.close()


def test_conventions_unexpected_errors_fail_the_job_and_show_a_plain_page(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Conventions › Errors, AD-5: a refused request (PolymarketBadRequest) fails the job, logged; the page is
    the plain "Something went wrong" page, never a raw exception."""
    live = live_run(tmp_path, lambda url, params: status(404, b"not found"), "0x" + "ef" * 20)
    job_id, _ = open_page(live)
    with caplog.at_level(logging.ERROR, logger="liquidoracle.services.jobs"):
        live.worker.run_once()
    job = live.store.job(job_id)
    assert job is not None and job.status is JobStatus.FAILED
    assert any("failed" in record.getMessage() for record in caplog.records)
    text = html(live.web, f"/wallet/{live.wallet}?job={job_id}", 500)  # like the app's own error page
    assert h1s(text) == ["Something went wrong"] and "Traceback" not in text
    live.store.close()


def test_conventions_a_bug_in_the_fetch_fails_the_job_and_the_worker_goes_on(
    run: Live, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-5: any other exception fails that job (logged); the next job still runs."""
    first, _ = open_page(run)

    def broken(*args: object, **kwargs: object) -> int:
        raise KeyError("a bug")

    monkeypatch.setattr(jobs_module, "fetch_wallet", broken)
    run.worker.run_once()
    assert run.store.job(first).status is JobStatus.FAILED  # type: ignore[union-attr]
    monkeypatch.setattr(jobs_module, "fetch_wallet", fetch_wallet)
    second, _ = open_page(run)
    assert second != first
    run.worker.run_once()
    assert run.store.job(second).status is JobStatus.DONE  # type: ignore[union-attr]


@pytest.mark.parametrize("end", ["stopped", "failed"])
def test_ux_dr23_reloading_an_old_outage_or_error_page_tries_again(tmp_path: Path, end: str) -> None:
    """UX-DR23 (review): an outage or error page reloaded within RETRY_AFTER seconds shows the same page; reloaded
    later it queues a new lookup, so "Try again in a few minutes." works by reloading the same address."""
    answer = always_times_out if end == "stopped" else (lambda url, params: status(404, b"not found"))
    live = live_run(tmp_path, answer, "0x" + "9a" * 20)
    job_id, _ = open_page(live)
    live.worker.run_once()
    url = f"/wallet/{live.wallet}?job={job_id}"
    live.clock.now += RETRY_AFTER - 1
    assert live.web.get(url).status_code == (200 if end == "stopped" else 500)
    live.clock.now += 2
    reply = live.web.get(url)
    assert reply.status_code == 302 and reply.headers["Location"] != url
    live.store.close()


@pytest.mark.parametrize("end", ["stopped", "failed", "no history"])
def test_ad4_an_ended_job_with_a_fresh_snapshot_shows_the_verdict(run: Live, end: str) -> None:
    """AD-4 (review): once a fresh snapshot exists, a stopped, failed or no-history job's page shows the Verdict,
    not its old message."""
    job_id, _ = open_page(run)
    assert run.store.claim_job(job_id)
    result = NO_HISTORY if end == "no history" else None
    status_ = JobStatus.DONE if end == "no history" else JobStatus(end)
    run.store.finish_job(job_id, status_, message="", result=result)
    fetch_wallet(run.worker._client, run.store, run.wallet)  # noqa: SLF001 - a later fetch stored fresh data
    text = html(run.web, f"/wallet/{run.wallet}?job={job_id}")
    assert h1s(text)[0].startswith("Verdict: ")


def test_ad5_a_job_ending_while_the_page_reads_queues_no_second_fetch(run: Live, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-5 (review): the page reads the job before the snapshot, so a job that ends in between shows its
    Verdict instead of queueing a second Polymarket fetch."""
    job_id, _ = open_page(run)
    real_job = run.store.job

    def finish_then_job(found_id: int) -> object:
        run.worker.run_once()  # the worker finishes just as the page asks for the job
        return real_job(found_id)

    monkeypatch.setattr(run.store, "job", finish_then_job)
    page = run.lookup.wallet_page(run.wallet, job=job_id)
    monkeypatch.setattr(run.store, "job", real_job)
    assert page.outcome is Outcome.VERDICT
    assert run.store.claim_next_job() is None  # no second job was queued


def test_ad5_finish_changes_only_a_running_job_and_interrupted_jobs_say_so(tmp_path: Path) -> None:
    """AD-5 (review): finish_job leaves a job that is no longer running as it is, and an interrupted job's
    progress message no longer says it is fetching."""
    store = Store(tmp_path / "live.db")
    job_id = store.queue_lookup("0x" + "ab" * 20, message=FETCHING)
    store.claim_job(job_id)
    store.interrupt_running_jobs()
    store.finish_job(job_id, JobStatus.DONE, message="Done")
    job = store.job(job_id)
    assert job is not None and (job.status, job.message) == (JobStatus.INTERRUPTED, INTERRUPTED_MESSAGE)
    store.close()


# --- interrupted, unknown and foreign jobs (AD-5) ---------------------------------------------


def test_ad5_running_jobs_become_interrupted_and_reopen_as_a_new_job(run: Live) -> None:
    """AD-5: at startup a job left running becomes interrupted; its page queues a fresh lookup."""
    job_id, _ = open_page(run)
    assert run.store.claim_job(job_id)
    assert run.store.interrupt_running_jobs() == 1
    assert run.store.job(job_id).status is JobStatus.INTERRUPTED  # type: ignore[union-attr]
    reply = run.web.get(f"/wallet/{run.wallet}?job={job_id}")
    assert reply.status_code == 302 and reply.headers["Location"] != f"/wallet/{run.wallet}?job={job_id}"


def test_a_job_of_another_wallet_or_no_job_is_ignored(run: Live) -> None:
    """AD-5: `?job=` naming another Wallet's job, a missing job or not a number leads to the usual lookup."""
    other = run.store.queue_lookup("0x" + "11" * 20, message=FETCHING)
    for query in (f"?job={other}", "?job=999", "?job=abc"):
        reply = run.web.get(f"/wallet/{run.wallet}{query}")
        assert reply.status_code == 302 and "job=" in reply.headers["Location"]
        assert reply.headers["Location"] != f"/wallet/{run.wallet}?job={other}"


def test_ux_dr7_upper_case_address_keeps_only_job_and_stored(run: Live) -> None:
    """UX-DR7, AD-5: the move to lower case keeps `job` and `stored` and drops anything else."""
    upper = "0x" + run.wallet[2:].upper()
    reply = run.web.get(f"/wallet/{upper}?job=3&raw=x&stored=1")
    assert reply.status_code == 301 and reply.headers["Location"] == f"/wallet/{run.wallet}?job=3&stored=1"


def test_ad5_progress_json_and_unknown_job(run: Live) -> None:
    """AD-5, Conventions › Job progress: exactly {status, phase, done, total, message}; an unknown job is a 404."""
    job_id, _ = open_page(run)
    reply = run.web.get(f"/jobs/{job_id}/progress")
    assert reply.status_code == 200 and reply.headers["Cache-Control"] == "no-store"
    assert reply.get_json() == {"status": "queued", "phase": "fetch", "done": 0, "total": 1, "message": FETCHING}
    run.worker.run_once()
    assert run.web.get(f"/jobs/{job_id}/progress").get_json()["status"] == "done"
    missing = run.web.get("/jobs/999/progress")
    assert missing.status_code == 404 and missing.get_json() == {"error": "no such job"}


# --- claiming and the worker thread (AD-5, AD-23) -------------------------------------------------


def test_ad5_two_claimers_one_job_only_one_wins(tmp_path: Path) -> None:
    """AD-5: the claim is one atomic UPDATE checking rowcount == 1, so two claimers never both get a job,
    even through two separate connections to the same file."""
    first = Store(tmp_path / "live.db")
    second = Store(tmp_path / "live.db")
    job_id = first.queue_lookup("0x" + "22" * 20, message=FETCHING)
    assert [first.claim_job(job_id), second.claim_job(job_id)] == [True, False]
    assert second.claim_next_job() is None
    first.close()
    second.close()


def test_ad5_a_job_taken_in_between_is_skipped_and_a_failing_claim_never_spins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-5 (Edvard, 2026-11-21): claim_next_job reads the queue once and tries each job in turn. A job another
    claimer takes between the read and the update is skipped for the next one; when every claim fails it
    returns None at once instead of looking again for ever (the break check found that hang)."""
    store = Store(tmp_path / "live.db")
    other = Store(tmp_path / "live.db")
    first = store.queue_lookup("0x" + "66" * 20, message=FETCHING)
    second = store.queue_lookup("0x" + "77" * 20, message=FETCHING)
    real_claim = store.claim_job
    taken: list[int] = []

    def racing(job_id: int) -> bool:
        if not taken:
            taken.append(job_id)
            assert other.claim_job(job_id)  # the other claimer gets there first
        return real_claim(job_id)

    monkeypatch.setattr(store, "claim_job", racing)
    claimed = store.claim_next_job()
    assert taken == [first] and claimed is not None and claimed.id == second
    third = store.queue_lookup("0x" + "88" * 20, message=FETCHING)
    monkeypatch.setattr(store, "claim_job", lambda job_id: False)
    assert store.claim_next_job() is None  # returns, never spins
    assert store.job(third).status is JobStatus.QUEUED  # type: ignore[union-attr]
    store.close()
    other.close()


def test_ad5_lookups_run_before_other_work(tmp_path: Path) -> None:
    """AD-5: a waiting lookup is claimed before older work of another kind (Epic 4's Scans)."""
    store = Store(tmp_path / "live.db")
    with sqlite3.connect(store.path) as raw:
        raw.execute(
            "INSERT INTO job (kind, wallet, status, phase, done, total, message, created_at)"
            " VALUES ('scan', NULL, 'queued', 'ranking', 0, 1, '', 0)"
        )
    raw.close()
    lookup_id = store.queue_lookup("0x" + "33" * 20, message=FETCHING)
    claimed = store.claim_next_job()
    assert claimed is not None and claimed.id == lookup_id
    store.close()


def test_finish_job_refuses_an_open_status(tmp_path: Path) -> None:
    """AD-5: a job can only finish as done, interrupted, stopped or failed."""
    store = Store(tmp_path / "live.db")
    job_id = store.queue_lookup("0x" + "44" * 20, message=FETCHING)
    with pytest.raises(ValueError):
        store.finish_job(job_id, JobStatus.RUNNING, message="")
    store.close()


def test_ad5_the_worker_thread_runs_queued_lookups(run: Live, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-5: the daemon thread wakes on a new job, runs it, and stops when asked. The idle wait is set far
    above the deadline, so only the wake from queue_lookup can get the job done in time (review)."""
    monkeypatch.setattr(jobs_module, "IDLE_WAIT", 60.0)
    thread = run.worker.start()
    assert thread.daemon and thread.name == "liquidoracle-worker"
    job_id, _ = open_page(run)
    deadline = time.monotonic() + 10
    while run.store.job(job_id).status is not JobStatus.DONE and time.monotonic() < deadline:  # type: ignore[union-attr]
        time.sleep(0.02)
    run.worker.stop()
    thread.join(timeout=5)
    assert run.store.job(job_id).status is JobStatus.DONE  # type: ignore[union-attr]
    assert not thread.is_alive()


def test_ad5_queueing_a_lookup_wakes_the_worker_at_once(run: Live) -> None:
    """AD-5 (review): a new job ends the worker's idle wait at once instead of after IDLE_WAIT."""
    run.jobs.wait(0)  # start from a cleared signal
    run.jobs.queue_lookup(run.wallet)
    started = time.monotonic()
    run.jobs.wait(30)
    assert time.monotonic() - started < 5


def test_ad5_the_worker_thread_survives_an_error_outside_a_job(run: Live, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-5 (review): an error while claiming (e.g. a locked database) is logged and the thread lives on, so a
    later lookup still runs."""
    real_claim = run.store.claim_next_job
    calls: list[int] = []

    def flaky() -> object:
        calls.append(1)
        if len(calls) == 1:
            raise StoreError("database is locked")
        return real_claim()

    monkeypatch.setattr(run.store, "claim_next_job", flaky)
    monkeypatch.setattr(jobs_module, "IDLE_WAIT", 0.05)
    thread = run.worker.start()
    deadline = time.monotonic() + 10
    while not calls and time.monotonic() < deadline:
        time.sleep(0.01)
    job_id, _ = open_page(run)
    while run.store.job(job_id).status is not JobStatus.DONE and time.monotonic() < deadline:  # type: ignore[union-attr]
        time.sleep(0.02)
    run.worker.stop()
    thread.join(timeout=5)
    assert run.store.job(job_id).status is JobStatus.DONE  # type: ignore[union-attr]


def test_ad23_create_app_starts_no_thread(tmp_path: Path) -> None:
    """AD-5, AD-23: building the app starts no worker; only `liquidoracle run` does."""
    store = Store(tmp_path / "live.db")
    before = {t.name for t in threading.enumerate()}
    create_app(Settings(offline=False), Lookup(None, store, seed=SEED, jobs=Jobs(store)))
    assert "liquidoracle-worker" not in {t.name for t in threading.enumerate()} - before
    store.close()


def test_ad23_serve_interrupts_old_jobs_and_starts_the_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-5, AD-23: a live `run` marks jobs left running as interrupted, then starts the one worker."""
    monkeypatch.chdir(tmp_path)
    store = Store(tmp_path / LIVE_DB)
    job_id = store.queue_lookup("0x" + "55" * 20, message=FETCHING)
    store.claim_job(job_id)
    store.close()
    started: list[Worker] = []
    monkeypatch.setattr(Worker, "start", lambda self: started.append(self))
    monkeypatch.setattr(cli, "port_in_use", lambda host, port: False)
    monkeypatch.setattr("flask.Flask.run", lambda self, **kwargs: None)
    assert cli.serve(Settings(offline=False)) == 0
    assert len(started) == 1
    check = Store(tmp_path / LIVE_DB)
    assert check.job(job_id).status is JobStatus.INTERRUPTED  # type: ignore[union-attr]
    check.close()


def test_ad23_serve_stops_plainly_when_the_database_cannot_be_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AD-6, AD-23 (review): a live.db that cannot be written at startup stops `run` with a sentence, not a traceback."""
    monkeypatch.chdir(tmp_path)

    def locked(self: Store) -> int:
        raise StoreError("database is locked")

    monkeypatch.setattr(Store, "interrupt_running_jobs", locked)
    monkeypatch.setattr(cli, "port_in_use", lambda host, port: False)
    assert cli.serve(Settings(offline=False)) == 2
    assert "cannot be written" in capsys.readouterr().err


def test_ad13_offline_run_starts_no_worker_and_never_goes_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-13, AD-4 (Story 2.5): `run --offline` starts no worker; an old offline snapshot is still served."""
    from liquidoracle.data.offline import OfflineClient, sample_files
    from liquidoracle.data.store import OFFLINE_DB

    synthetic.write_small(tmp_path)
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    clock = Clock()
    store = Store(tmp_path / OFFLINE_DB, clock=clock)
    client = OfflineClient(sample_files(tmp_path))
    sharp = synthetic.address_of("sharp-trader")
    fetch_wallet(client, store, sharp)
    clock.now += 30 * 24 * HOUR
    assert Lookup(client, store, seed=SEED).wallet_page(sharp).outcome is Outcome.VERDICT
    store.close()
    monkeypatch.chdir(tmp_path)
    started: list[Worker] = []
    monkeypatch.setattr(Worker, "start", lambda self: started.append(self))
    monkeypatch.setattr(cli, "port_in_use", lambda host, port: False)
    monkeypatch.setattr("flask.Flask.run", lambda self, **kwargs: None)
    assert cli.serve(Settings(offline=True)) == 0
    assert started == []


# --- NFR-10: a 1,000-Position Wallet from stored data (Edvard, 2026-11-21) -------------------------


def test_nfr10_a_1000_position_wallet_gets_its_verdict_within_10_seconds(tmp_path: Path) -> None:
    """NFR-10 (SM-3): a Wallet with 1,000 Resolved Positions gets its Verdict from stored data within 10 s.

    Made-up Wallet: the real Sample Wallets arrive in Story 2.6, which times them again, with the
    Polymarket fetch too (Edvard, 2026-11-21). This times only the app's own work: reading the
    snapshot, building Positions, the Skill Test and the card's words. The limit is the requirement
    itself, far above the measured time, so a slow CI runner does not make it flaky.
    """
    bets = []
    for i in range(1000):  # coin-flipper style: whole-cent prices 0.10-0.90, won when a draw < price
        price = (10 + int(synthetic.uniform("speed-check", i, "price") * 81)) / 100
        bets.append(synthetic._Bet(price, won=synthetic.uniform("speed-check", i, "outcome") < price))  # noqa: SLF001
    wallet = synthetic._wallet("speed-check", bets)  # noqa: SLF001
    store = Store(tmp_path / "live.db")
    fetch_id = store.begin_snapshot(wallet.address, window_limit=WINDOW_LIMIT)
    store.add_positions(fetch_id, wallet.positions)
    store.add_activity(fetch_id, wallet.activity)
    store.save_markets(wallet.markets)
    store.finish_snapshot(fetch_id)
    lookup = Lookup(None, store, seed=SEED, jobs=Jobs(store))
    started = time.perf_counter()
    page = lookup.wallet_page(wallet.address)
    elapsed = time.perf_counter() - started
    store.close()
    assert page.outcome is Outcome.VERDICT and page.card is not None and page.card.bets == "1,000"
    print(f"NFR-10: 1,000-Position Wallet, Verdict from stored data in {elapsed:.2f} s")
    assert elapsed < 10.0
