"""The Scans page: the New Scan form, the Scan list and the running Scan (FR-16, UX-DR30 to UX-DR32; Story 4.4).

The service is tested over a real store and job queue with a fixed clock; no worker runs, so each test moves
the Scan's job by hand (how a Scan runs is tested in test_scan_job.py). The pages are tested through Flask's
test client.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from liquidoracle.core import phrases
from liquidoracle.data.offline import OfflineClient
from liquidoracle.data.store import JobStatus, Store
from liquidoracle.data.window import cutoff_at
from liquidoracle.records import Verdict
from liquidoracle.services import scans_page as sp
from liquidoracle.services.jobs import Jobs
from liquidoracle.services.lookup import Lookup
from liquidoracle.services.scans_page import ScansPage, Submitted
from liquidoracle.settings import Settings
from liquidoracle.web import create_app

TODAY = date(2026, 11, 26)
NOW = int(datetime(2026, 11, 26, 12, 0, tzinfo=UTC).timestamp())
SEED = 44
OLD = "2025-07-01"  # far enough back: no warning


class Clock:
    def __init__(self) -> None:
        self.now = float(NOW)

    def __call__(self) -> float:
        return self.now


@dataclass
class Rig:
    path: Path
    clock: Clock
    store: Store
    jobs: Jobs
    page: ScansPage

    def sql(self, statement: str, *args: object) -> None:
        """Set a state no worker reaches here (finished, rebuilt, results): the test's own write."""
        with sqlite3.connect(self.path) as db:
            db.execute(statement, args)

    def start(self, day: str = OLD, size: str = "200") -> int:
        outcome, _ = self.page.submit(day, size, confirmed=False)
        assert outcome is Submitted.STARTED
        return self.store.scans()[0].scan_id

    def end(self, scan_id: int, status: JobStatus, done: int = 0, total: int = 0, message: str = "x") -> None:
        """Claim the Scan's job, report progress, then end it as `status` (keeping its progress)."""
        job = self.store.scan(scan_id).job
        assert job is not None and self.store.claim_job(job.id)
        self.store.update_progress(job.id, phase="ranking", done=done, total=total, message=message)
        if status is JobStatus.INTERRUPTED:
            self.store.interrupt_running_jobs()
        elif status is not JobStatus.RUNNING:
            self.store.finish_job(job.id, status, message=message, keep_progress=True)

    def finish(self, scan_id: int, verdicts: tuple[str, ...] = (), *, copied: bool = True) -> None:
        """Finish the Scan; `copied` False leaves it without a Copy Test, like a Scan from before Story 6.2."""
        self.end(scan_id, JobStatus.DONE)
        self.sql("UPDATE scan SET step = 'done', copied_at = ? WHERE scan_id = ?", NOW if copied else None, scan_id)
        for i, verdict in enumerate(verdicts):
            for scope in ("scan_whole", "scan_before"):
                self.sql(
                    "INSERT INTO scan_result (scan_id, wallet, scope, cutoff, seed, verdict, p_value, tested_count,"
                    " real_pnl, not_fully_read) VALUES (?, ?, ?, 0, 44, ?, 0.001, 100, 10.0, 0)",
                    scan_id, f"0x{i:040x}", scope, verdict,
                )


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    clock = Clock()
    path = tmp_path / "live.db"
    store = Store(path, clock=clock)
    jobs = Jobs(store)
    yield Rig(path, clock, store, jobs, ScansPage(store, jobs=jobs, seed=SEED, rate=5.0))
    store.close()


def days_ago(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


# --- the form (UX-DR30) --------------------------------------------------------------------------


def test_ux_dr30_a_new_page_has_the_blank_form_the_estimate_and_the_empty_state(rig: Rig) -> None:
    """UX-DR30, UX-DR4: a new Scans page has the blank form (200 Wallets), the rough estimate and the empty state."""
    view = rig.page.view()
    assert (view.form.cutoff, view.form.size, view.form.today) == ("", "200", "2026-11-26")
    assert view.form.estimate == "Rough estimate: about 2.5 hours at 5 requests per second"  # EXPERIENCE.md's example
    assert not view.form.blocked and not view.form.read_only
    assert view.rows == () and view.empty == sp.NO_SCANS and view.running is None
    assert view.title == "Scans · LiquidOracle"


@pytest.mark.parametrize(
    ("cutoff", "size", "cutoff_error", "size_error"),
    [
        ("", "200", sp.NO_DATE, None),
        ("not a date", "200", sp.NO_DATE, None),
        ("2026-02-30", "200", sp.NO_DATE, None),
        ("20250701", "200", sp.NO_DATE, None),
        (TODAY.isoformat(), "200", sp.NOT_PAST, None),
        ("2027-01-01", "200", sp.NOT_PAST, None),
        (OLD, "9", None, sp.BAD_SIZE),
        (OLD, "501", None, sp.BAD_SIZE),
        (OLD, "10.5", None, sp.BAD_SIZE),
        (OLD, "abc", None, sp.BAD_SIZE),
        (OLD, "", None, sp.BAD_SIZE),
        (OLD, "-20", None, sp.BAD_SIZE),
        ("", "0", sp.NO_DATE, sp.BAD_SIZE),
    ],
)
def test_ux_dr30_each_bad_input_names_its_field_and_nothing_starts(
    rig: Rig, cutoff: str, size: str, cutoff_error: str | None, size_error: str | None
) -> None:
    """UX-DR30, UX-DR13: each bad input gets its field's sentence, what was typed stays, and no Scan starts."""
    outcome, view = rig.page.submit(cutoff, size, confirmed=True)
    assert outcome is Submitted.INVALID and view is not None
    assert (view.form.cutoff_error, view.form.size_error) == (cutoff_error, size_error)
    assert (view.form.cutoff, view.form.size) == (cutoff.strip(), size.strip())  # what was typed stays
    assert rig.store.scans() == ()


def test_ux_dr30_limits_and_spaces_are_accepted(rig: Rig) -> None:
    """UX-DR30: 10 and 500 are allowed, and spaces around the values are ignored."""
    assert rig.page.submit(f"  {OLD} ", " 10 ", confirmed=False)[0] is Submitted.STARTED
    assert rig.store.scans()[0].size == 10
    assert sp._check_size("500") == (500, None)


@pytest.mark.parametrize(("back", "warned"), [(1, True), (30, True), (89, True), (90, False), (400, False)])
def test_ux_dr30_a_recent_date_warns_once_then_starts(rig: Rig, back: int, warned: bool) -> None:
    """UX-DR30 (Edvard, 2026-10-24): less than 90 days back warns; the user can still start (a second submit)."""
    outcome, view = rig.page.submit(days_ago(back), "50", confirmed=False)
    if not warned:
        assert outcome is Submitted.STARTED
        return
    assert outcome is Submitted.WARNED and view is not None
    assert view.form.warning == sp.FEW_AFTER and view.form.confirmed and view.form.cutoff_error is None
    assert rig.store.scans() == ()
    assert rig.page.submit(days_ago(back), "50", confirmed=True)[0] is Submitted.STARTED


def test_fr16_start_queues_a_scan_with_the_cutoff_size_and_seed(rig: Rig) -> None:
    """FR-16, AD-15: Start Scan queues a Scan with the chosen Cut-off Date (00:00 UTC), size and the settings' Seed."""
    scan_id = rig.start("2025-07-01", "120")
    scan = rig.store.scan(scan_id)
    assert (scan.cutoff, scan.size, scan.seed) == (cutoff_at(date(2025, 7, 1)), 120, SEED)
    assert scan.job is not None and scan.job.status is JobStatus.QUEUED


def test_ux_dr30_one_scan_at_a_time(rig: Rig) -> None:
    """UX-DR30, AD-5: while a Scan runs, the button is unavailable and a second start is refused."""
    rig.start()
    view = rig.page.view()
    assert view.form.blocked  # the running box says why
    assert rig.page.submit(OLD, "200", confirmed=False) == (Submitted.REFUSED, None)
    assert len(rig.store.scans()) == 1


# --- the running Scan (UX-DR32) ------------------------------------------------------------------


def test_ux_dr32_the_running_scan_names_its_step_and_counts_in_the_title(rig: Rig) -> None:
    """UX-DR32: the running Scan's info box and progress name its step; the tab title counts once there is a total."""
    scan_id = rig.start()
    view = rig.page.view()
    assert view.running is not None and view.running.total == 0
    assert view.title == "Scans · LiquidOracle"  # nothing to count yet
    assert view.rows[0].status == "Waiting to start"
    rig.end(scan_id, JobStatus.RUNNING, 34, 100, "Reading Markets: 34 of 100")
    view = rig.page.view()
    assert view.running.step == "Reading Markets: 34 of 100" and (view.running.done, view.running.total) == (34, 100)
    assert "".join((view.running.info[0], view.running.step, view.running.info[1])) == (
        "A Scan is running (Reading Markets: 34 of 100). You can start a new one when it finishes."
    )
    assert view.title == "34/100 · Scan · LiquidOracle"
    assert view.rows[0].status == "Running: Reading Markets: 34 of 100"


# --- the Scan list (UX-DR31) ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "done", "total", "text", "resumable"),
    [
        (JobStatus.INTERRUPTED, 120, 200, "Interrupted at 120 of 200", True),
        (JobStatus.INTERRUPTED, 0, 0, "Interrupted", True),
        (JobStatus.STOPPED, 1200, 1800, "Stopped at 1,200 of 1,800: Polymarket did not answer", True),
        (JobStatus.STOPPED, 0, 0, "Stopped: Polymarket did not answer", True),
        (JobStatus.FAILED, 3, 100, "Failed", False),
    ],
)
def test_ux_dr31_status_text_and_resume(
    rig: Rig, status: JobStatus, done: int, total: int, text: str, resumable: bool
) -> None:
    """UX-DR31, AD-5: each stopped state's status text, and Resume for interrupted and stopped Scans only."""
    scan_id = rig.start()
    rig.end(scan_id, status, done, total, "Polymarket did not answer")
    row = rig.page.view().rows[0]
    assert row.status == text
    assert row.watchlist is None  # no results of an unfinished Scan
    assert row.resume_label == ("Resume Scan (Cut-off Date 1 July 2025)" if resumable else None)
    assert rig.page.resume(scan_id) is resumable


def test_ux_dr31_a_rebuilt_scan_says_so_and_cannot_resume(rig: Rig) -> None:
    """UX-DR31, AD-6: a Scan whose data was rebuilt says "Data rebuilt, cannot resume" and has no Resume."""
    scan_id = rig.start()
    rig.end(scan_id, JobStatus.STOPPED, 5, 100)
    rig.sql("UPDATE scan SET data_rebuilt = 1 WHERE scan_id = ?", scan_id)
    row = rig.page.view().rows[0]
    assert (row.status, row.resume_label) == ("Data rebuilt, cannot resume", None)
    assert rig.page.resume(scan_id) is False


def test_ux_dr31_rows_newest_first_with_dates_and_watchlist_size(rig: Rig) -> None:
    """UX-DR31, FR-16: newest first, dates written out, and the Watchlist size counts only finished Scans' Skilled (high confidence) results."""
    first = rig.start("2025-07-01", "50")
    rig.finish(first, (Verdict.SKILLED.value, Verdict.SKILLED.value, Verdict.LIKELY_SKILLED.value))
    rig.clock.now += 86_400
    second = rig.start("2025-03-15", "200")
    rows = rig.page.view().rows
    assert [r.scan_id for r in rows] == [second, first]
    assert rows[1].status == "Finished" and rows[1].watchlist == "2"  # Skilled (high confidence) only
    assert (rows[1].cutoff, rows[1].wallets, rows[1].run_date) == ("1 July 2025", "50", phrases.run_date(NOW))
    assert rows[0].cutoff == "15 March 2025" and rows[0].watchlist is None


def test_ux_dr31_no_resume_button_while_another_scan_runs(rig: Rig) -> None:
    """UX-DR31, AD-5: no Resume while another Scan runs (one Scan at a time)."""
    stopped = rig.start()
    rig.end(stopped, JobStatus.STOPPED, 1, 100)
    rig.start()
    assert rig.page.view().rows[1].resume_label is None
    assert rig.page.resume(stopped) is False


def test_ad5_resume_queues_a_new_job_for_the_same_scan(rig: Rig) -> None:
    """AD-5: Resume queues a new job for the same Scan, which then shows as waiting."""
    scan_id = rig.start()
    rig.end(scan_id, JobStatus.INTERRUPTED, 84, 200)
    assert rig.page.resume(scan_id)
    view = rig.page.view()
    assert view.running is not None and view.running.scan_id == scan_id
    assert view.rows[0].status == "Waiting to start"


# --- the estimate (UX-DR30; Edvard, 2026-11-26) --------------------------------------------------


def test_ux_dr30_the_estimate_counts_what_a_scan_plans_today(rig: Rig) -> None:
    """UX-DR30 (Edvard, 2026-11-26; Story 6.2): the estimate counts the Gamma list, 100 Markets, 4 x N Wallet parts
    and the Copy phase's price requests, 50 per Wallet, at the set pace."""
    without = 50 + 100 * sp.MARKET_REQUESTS + 4 * 200 * sp.PART_REQUESTS
    assert sp.planned_requests(200, copy=False) == without and sp.COPY_REQUESTS == 50
    assert sp.planned_requests(200) == without + 200 * sp.COPY_REQUESTS == 43_550
    assert rig.page.estimate("10") == "Rough estimate: about 10 minutes at 5 requests per second"
    assert rig.page.estimate("500") == "Rough estimate: about 6 hours at 5 requests per second"
    assert rig.page.estimate("9") is None and rig.page.estimate("x") is None
    one = ScansPage(rig.store, jobs=rig.jobs, seed=SEED, rate=1.0)
    assert one.estimate("10").endswith("at 1 request per second")


def test_ux_dr30_the_estimate_is_recalibrated_from_the_last_finished_scan(rig: Rig) -> None:
    """UX-DR30 (Edvard, 2026-10-24): after a finished Scan, the estimate uses that Scan's own time per planned request."""
    scan_id = rig.start(size="100")
    rig.clock.now += sp.planned_requests(100)  # one second per planned request: half the set pace
    rig.finish(scan_id)
    assert rig.store.scan_seconds(scan_id) == sp.planned_requests(100)
    assert rig.page.estimate("200") == "Rough estimate: about 12 hours, based on your last Scan"


def test_ux_dr30_a_last_scan_without_a_copy_test_is_calibrated_without_the_price_requests(rig: Rig) -> None:
    """UX-DR30 (Story 6.2): a Scan that finished without a Copy Test took its time without the price requests, so
    its pace is its time over the requests it made; the new Scan's estimate still counts its own price requests.
    At one second per request that is the same 12 hours for 200 Wallets; counting price requests the old Scan
    never made would say 9.5."""
    scan_id = rig.start(size="100")
    rig.clock.now += sp.planned_requests(100, copy=False)  # one second per request it made
    rig.finish(scan_id, copied=False)
    assert not rig.store.scan(scan_id).copied
    assert rig.page.estimate("200") == "Rough estimate: about 12 hours, based on your last Scan"


def copy_test_job(rig: Rig, scan_id: int, seconds: int, status: JobStatus) -> None:
    """A Copy Test job for the Scan that runs for `seconds` and ends as `status`."""
    job_id = rig.jobs.start_copy_test(scan_id)
    assert job_id is not None and rig.store.claim_job(job_id)
    rig.clock.now += seconds
    if status is JobStatus.INTERRUPTED:
        rig.store.interrupt_running_jobs()
    else:
        rig.store.finish_job(job_id, status, message="x", keep_progress=True)


def test_ux_dr30_a_copy_test_job_that_gave_no_copy_test_does_not_change_the_pace(rig: Rig) -> None:
    """UX-DR30 (Story 6.2 review): a Copy Test job that stopped or failed, or that the app was closed on, leaves a
    Scan without a Copy Test, so its time is not part of the Scan's pace: the estimate stays what the Scan's own
    run gives, and an interrupted Copy Test job does not make the Scan's own time unknown."""
    scan_id = rig.start(size="100")
    own = sp.planned_requests(100, copy=False)
    rig.clock.now += own  # one second per request the Scan made
    rig.finish(scan_id, copied=False)
    twelve = "Rough estimate: about 12 hours, based on your last Scan"
    assert rig.page.estimate("200") == twelve
    for status in (JobStatus.STOPPED, JobStatus.FAILED, JobStatus.INTERRUPTED):
        copy_test_job(rig, scan_id, 30_000, status)
        assert rig.page.estimate("200") == twelve, status
    assert rig.store.scan_seconds(scan_id) == own and rig.store.scan_seconds(scan_id, kind="copy") is None
    # Even once the Scan has its Copy Test: with an interrupted Copy Test job their time is not known, so the
    # pace is still the Scan's own run, measured without the price requests.
    rig.sql("UPDATE scan SET copied_at = ? WHERE scan_id = ?", NOW, scan_id)
    assert rig.page.estimate("200") == twelve


def test_ux_dr30_a_finished_copy_test_jobs_time_joins_the_scans_pace(rig: Rig) -> None:
    """UX-DR30 (Story 6.2 review): when a Scan got its Copy Test from its own job, the pace is the Scan's run plus
    its Copy Test jobs (a stopped one and the one that finished) over all the requests, price requests included."""
    scan_id = rig.start(size="100")
    own = sp.planned_requests(100, copy=False)
    rig.clock.now += own
    rig.finish(scan_id, copied=False)
    copy_test_job(rig, scan_id, 4_000, JobStatus.STOPPED)
    copy_test_job(rig, scan_id, 6_000, JobStatus.DONE)  # 10,000 s for 5,000 price requests: slower than the Scan
    rig.sql("UPDATE scan SET copied_at = ? WHERE scan_id = ?", NOW, scan_id)
    assert rig.store.scan_seconds(scan_id, kind="copy") == 10_000
    expected = phrases.rough_time(sp.planned_requests(200) * (own + 10_000) / sp.planned_requests(100))
    assert expected == "about 15 hours"
    assert rig.page.estimate("200") == f"Rough estimate: {expected}, based on your last Scan"


def test_an_interrupted_run_makes_the_scan_time_unknown(rig: Rig) -> None:
    """UX-DR30, AD-5 (Story 4.4 review): an interrupted run's end is stamped at the next start, so a finished Scan
    with one has no known time and the estimate falls back to the set pace."""
    scan_id = rig.start(size="100")
    rig.end(scan_id, JobStatus.RUNNING)
    rig.clock.now += 10_000  # the app was closed: this gap is not Scan time
    rig.store.interrupt_running_jobs()
    assert rig.store.scan_seconds(scan_id) is None
    assert rig.page.resume(scan_id)
    rig.finish(scan_id)
    assert rig.page.estimate("200") == "Rough estimate: about 2.5 hours at 5 requests per second"


def test_ux_dr30_recalibration_follows_the_newest_usable_scan_and_adds_up_resumes(rig: Rig) -> None:
    """UX-DR30 (Edvard, 2026-10-24; Story 4.4 review): the newest finished Scan sets the estimate, a rebuilt one is
    skipped, and a stopped then resumed Scan's time is both runs added up."""
    slow = rig.start(size="100")
    rig.clock.now += 2 * sp.planned_requests(100)  # 2 s per planned request
    rig.finish(slow)
    fast = rig.start(size="100")
    rig.clock.now += sp.planned_requests(100) // 2  # 0.5 s per planned request
    rig.finish(fast)
    assert rig.page.estimate("100") == f"Rough estimate: {phrases.rough_time(sp.planned_requests(100) / 2)}, based on your last Scan"
    rig.sql("UPDATE scan SET data_rebuilt = 1 WHERE scan_id = ?", fast)
    assert rig.page.estimate("100") == f"Rough estimate: {phrases.rough_time(2 * sp.planned_requests(100))}, based on your last Scan"

    resumed = rig.start(size="100")
    rig.clock.now += 1_000
    rig.end(resumed, JobStatus.STOPPED, 5, 100)
    rig.clock.now += 50_000  # the user waited before pressing Resume: not Scan time
    assert rig.page.resume(resumed)
    rig.clock.now += 3_000
    rig.finish(resumed)
    assert rig.store.scan_seconds(resumed) == 4_000


def test_ad7_a_scan_long_before_1970_still_lists(rig: Rig, web: FlaskClient) -> None:
    """AD-7, UX-DR31 (Story 4.4 review): a Cut-off Date long before 1970 is stored and listed; on Windows the old
    `fromtimestamp` call broke the whole Scans page for good."""
    rig.start("1960-01-01", "10")
    assert rig.page.view().rows[0].cutoff == "1 January 1960"
    assert web.get("/scans").status_code == 200


# --- Offline Mode (UX-DR30; Edvard, 2026-11-26; Story 4.6) --------------------------------------

SAMPLE_WALLETS = 1_018  # what `sample_size` counts in these tests


def offline_page(rig: Rig) -> ScansPage:
    return ScansPage(rig.store, jobs=rig.jobs, seed=SEED, rate=5.0, sample_size=lambda: SAMPLE_WALLETS)


def test_ux_dr30_offline_the_form_is_fixed_and_starts_a_scan_of_the_whole_sample(rig: Rig) -> None:
    """UX-DR30, AD-13, FR-16 (Story 4.6): Offline Mode's form is fixed and read-only, with no estimate, and
    "Start Scan" starts a Scan of the default Cut-off Date over every Sample Wallet."""
    offline = offline_page(rig)
    form = offline.view().form
    assert (form.cutoff, form.size, form.read_only) == ("2025-07-01", "Whole Sample Dataset", True)
    assert not form.blocked and form.estimate is None
    assert sp.OFFLINE_INFO == "Offline Mode scans the whole Sample Dataset with its Cut-off Date, 1 July 2025."
    assert not hasattr(sp, "OFFLINE_NOT_READY")
    assert offline.submit(OLD, "Whole Sample Dataset", confirmed=False) == (Submitted.STARTED, None)
    (scan,) = rig.store.scans()
    assert (scan.cutoff, scan.size, scan.seed) == (cutoff_at(date(2025, 7, 1)), SAMPLE_WALLETS, SEED)
    assert offline.estimate("200") is None


@pytest.mark.parametrize(("cutoff", "size"), [(days_ago(10), "37"), ("", ""), ("not a date", "9999"), (OLD, "200")])
def test_ux_dr30_offline_posted_values_are_ignored(rig: Rig, cutoff: str, size: str) -> None:
    """UX-DR30 (Story 4.6, matrix "Posted values"): whatever an offline POST says, the fixed date and the whole
    Sample Dataset are used; no error, no recent-date warning."""
    assert offline_page(rig).submit(cutoff, size, confirmed=False) == (Submitted.STARTED, None)
    (scan,) = rig.store.scans()
    assert (scan.cutoff, scan.size) == (cutoff_at(date(2025, 7, 1)), SAMPLE_WALLETS)


def test_ux_dr30_offline_a_running_scan_blocks_a_new_one(rig: Rig) -> None:
    """UX-DR30 (Story 4.6, matrix "Scan running"): offline, a queued or running Scan blocks "Start Scan" with the
    running info box, as live, and a second POST starts nothing."""
    offline = offline_page(rig)
    assert offline.submit(OLD, "", confirmed=False)[0] is Submitted.STARTED
    view = offline.view()
    assert view.form.blocked and view.form.read_only and view.running is not None
    assert offline.submit(OLD, "", confirmed=False) == (Submitted.REFUSED, None)
    assert len(rig.store.scans()) == 1


def test_ad5_offline_an_interrupted_scan_resumes(rig: Rig) -> None:
    """AD-5 (Story 4.6, matrix "App closed mid-Scan"): an offline Scan cut off by closing the app is interrupted
    and can be resumed with a new job."""
    offline = offline_page(rig)
    offline.submit(OLD, "", confirmed=False)
    scan_id = rig.store.scans()[0].scan_id
    rig.end(scan_id, JobStatus.INTERRUPTED, done=3, total=10)
    (row,) = offline.view().rows
    assert row.resume_label == "Resume Scan (Cut-off Date 1 July 2025)"
    assert offline.resume(scan_id) is True
    assert rig.store.scan(scan_id).job.status is JobStatus.QUEUED


def test_no_job_queue_starts_nothing(rig: Rig) -> None:
    """AD-5: a Scans page built without a job queue (no worker) starts and resumes nothing."""
    page = ScansPage(rig.store, jobs=None, seed=SEED, rate=5.0, sample_size=lambda: SAMPLE_WALLETS)
    assert page.submit(OLD, "200", confirmed=True) == (Submitted.REFUSED, None)
    assert page.resume(1) is False and rig.store.scans() == ()


# --- the pages -----------------------------------------------------------------------------------


@pytest.fixture
def web(rig: Rig) -> FlaskClient:
    return create_app(Settings(offline=False), Lookup(None, rig.store, seed=SEED, jobs=rig.jobs), rig.page).test_client()


def page_text(reply) -> str:  # noqa: ANN001
    return reply.get_data(as_text=True)


def test_ux_dr30_the_scans_page_and_its_nav_link(web: FlaskClient) -> None:
    """UX-DR30, UX-DR8: the Scans page, its tab title and the *Scan wallets* link, current only there."""
    html = page_text(web.get("/scans"))
    assert "<title>Scans · LiquidOracle</title>" in html
    assert re.search(r'<a href="/scans" aria-current="page">Scan wallets</a>', html)
    assert sp.NO_SCANS in html and 'name="wallets" type="number" value="200"' in html
    assert "Rough estimate: about 2.5 hours at 5 requests per second" in html
    assert 'id="cutoff-warning" role="note" hidden' in html
    assert 'max="2026-11-25"' in html  # the latest day allowed: today is not in the past
    home = page_text(web.get("/"))
    assert '<a href="/scans">Scan wallets</a>' in home


def test_ux_dr13_errors_are_tied_to_their_fields(web: FlaskClient, rig: Rig) -> None:
    """UX-DR13, UX-DR30: errors are tied to their fields, mark them invalid, are read with "Error:", focus goes to the
    first field in error, and the page answers 400."""
    reply = web.post("/scans", data={"cutoff": "", "wallets": "7"})
    html = page_text(reply)
    assert reply.status_code == 400
    assert 'aria-describedby="cutoff-error" aria-invalid="true"' in html
    assert 'aria-describedby="wallets-error wallets-estimate" aria-invalid="true"' in html
    assert '<span class="visually-hidden">Error: </span>Choose a Cut-off Date.' in html
    assert 'value="7"' in html and rig.store.scans() == ()
    assert html.count("autofocus") == 1 and 'aria-invalid="true" autofocus' in html.split('id="wallets"')[0]
    only_size = page_text(web.post("/scans", data={"cutoff": OLD, "wallets": "7"}))
    assert only_size.count("autofocus") == 1 and "autofocus" in only_size.split('id="wallets"')[1].split(">")[0]
    assert "autofocus" not in page_text(web.get("/scans"))  # a fresh page leaves focus alone


def test_ux_dr30_the_warning_page_then_the_second_submit(web: FlaskClient, rig: Rig) -> None:
    """UX-DR30 (Edvard, 2026-10-24): without JavaScript the warning shows first, and the confirmed second submit starts."""
    reply = web.post("/scans", data={"cutoff": days_ago(10), "wallets": "200"})
    html = page_text(reply)
    assert reply.status_code == 200 and sp.FEW_AFTER in html
    assert 'aria-describedby="cutoff-warning"' in html and 'name="confirmed" id="confirmed" value="1"' in html
    reply = web.post("/scans", data={"cutoff": days_ago(10), "wallets": "200", "confirmed": "1"})
    assert reply.status_code == 303 and reply.headers["Location"] == "/scans"
    assert len(rig.store.scans()) == 1


def test_ux_dr32_the_page_of_a_running_scan(web: FlaskClient, rig: Rig) -> None:
    """UX-DR32: the running Scan's title, real progress bar with its spoken text, and the unavailable button."""
    reply = web.post("/scans", data={"cutoff": OLD, "wallets": "200"})
    assert reply.status_code == 303
    scan = rig.store.scans()[0]
    rig.end(scan.scan_id, JobStatus.RUNNING, 84, 200, "84 of 200 Wallets checked")
    html = page_text(web.get("/scans"))
    assert "<title>84/200 · Scan · LiquidOracle</title>" in html
    assert f'data-progress="/jobs/{scan.job.id}/progress"' in html
    assert re.search(r'<progress[^>]*aria-valuetext="84 of 200 Wallets checked"\s+max="200" value="84">', html)
    assert 'aria-disabled="true" aria-describedby="running-info"' in html
    assert web.get(f"/jobs/{scan.job.id}/progress").get_json()["message"] == "84 of 200 Wallets checked"


def test_ad5_the_resume_button_and_a_forged_resume(web: FlaskClient, rig: Rig) -> None:
    """AD-5, UX-DR31: the uniquely named Resume button works; a forged Resume of a failed or unknown Scan changes nothing."""
    stopped = rig.start()
    rig.end(stopped, JobStatus.STOPPED, 3, 100)
    html = page_text(web.get("/scans"))
    assert f'<form action="/scans/{stopped}/resume" method="post">' in html
    assert 'aria-label="Resume Scan (Cut-off Date 1 July 2025)">Resume</button>' in html
    assert web.post(f"/scans/{stopped}/resume").status_code == 303
    assert rig.store.scan(stopped).job.status is JobStatus.QUEUED
    rig.end(stopped, JobStatus.FAILED)
    failed_job = rig.store.scan(stopped).job.id
    assert web.post(f"/scans/{stopped}/resume").status_code == 303
    assert rig.store.scan(stopped).job.id == failed_job  # nothing new queued
    assert web.post("/scans/999/resume").status_code == 303


def test_a_post_from_another_web_page_is_refused(web: FlaskClient, rig: Rig) -> None:
    """AD-23: a POST from another web page (a foreign Origin) is refused and starts nothing; the app's own origin works."""
    reply = web.post("/scans", data={"cutoff": OLD, "wallets": "200"}, headers={"Origin": "https://example.com"})
    assert reply.status_code == 403 and rig.store.scans() == ()
    for name in ("attacker.example", "attacker.example:8044"):  # DNS rebinding: a foreign name pointed at 127.0.0.1
        reply = web.post("/scans", data={"cutoff": OLD, "wallets": "200"}, base_url=f"http://{name}",
                         headers={"Origin": f"http://{name}"})
        assert reply.status_code == 403
    assert web.post("/scans", data={"cutoff": OLD, "wallets": "200"}, headers={"Origin": "null"}).status_code == 403
    assert rig.store.scans() == ()
    reply = web.post("/scans", data={"cutoff": OLD, "wallets": "200"}, headers={"Origin": "http://localhost"})
    assert reply.status_code == 303 and len(rig.store.scans()) == 1  # the test client's own origin
    reply = web.post("/scans/1/resume", base_url="http://127.0.0.1:8044", headers={"Origin": "http://127.0.0.1:8044"})
    assert reply.status_code == 303


def test_ux_dr30_the_estimate_route(web: FlaskClient) -> None:
    """UX-DR30, AD-25: GET /scans/estimate gives the estimate's finished words, or null for a number not allowed."""
    reply = web.get("/scans/estimate?wallets=10")
    assert reply.get_json() == {"text": "Rough estimate: about 10 minutes at 5 requests per second"}
    assert reply.headers["Cache-Control"] == "no-store"
    assert web.get("/scans/estimate?wallets=5000").get_json() == {"text": None}
    assert web.get("/scans/estimate").get_json() == {"text": None}


def test_ux_dr30_offline_scans_page(tmp_path: Path) -> None:
    """UX-DR30, AD-13 (Story 4.6): Offline Mode's Scans page shows the fixed read-only form and its info box with
    "Start Scan" available, and a POST starts a Scan of the whole Sample Dataset."""
    store = Store(tmp_path / "offline.db")
    try:
        jobs = Jobs(store)
        scans = ScansPage(store, jobs=jobs, seed=SEED, rate=5.0, sample_size=lambda: SAMPLE_WALLETS)
        web = create_app(Settings(offline=True), Lookup(OfflineClient([]), store, seed=SEED), scans).test_client()
        html = page_text(web.get("/scans"))
        assert sp.OFFLINE_INFO in html and "not ready" not in html
        assert 'value="2025-07-01"' in html and "readonly" in html and "Rough estimate" not in html
        assert "aria-disabled" not in html
        assert web.post("/scans", data={"cutoff": OLD, "wallets": "Whole Sample Dataset"}).status_code == 303
        assert [s.size for s in store.scans()] == [SAMPLE_WALLETS]
    finally:
        store.close()
