"""scans.js in a real browser: the live estimate and warning, and following a running Scan (UX-DR30, UX-DR32;
Story 4.4).

The app here is a live run with a real job queue but no worker, so nothing reaches Polymarket: the test
moves the Scan's job itself (claim, progress, stop) and watches the page follow it.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from conftest import serving
from pages import MakePage, assert_no_sideways_scroll
from playwright.sync_api import Page, expect

from liquidoracle.data.store import JobStatus, Store
from liquidoracle.services.jobs import Jobs
from liquidoracle.services.lookup import Lookup
from liquidoracle.services.scans_page import FEW_AFTER, ScansPage
from liquidoracle.settings import Settings
from liquidoracle.web import create_app

WAIT = 10_000  # ms: a poll comes once a second


@dataclass
class ScansApp:
    url: str
    store: Store
    jobs: Jobs

    def running(self) -> int:
        """A Scan whose job is claimed but has reported nothing yet: its job id."""
        started = self.jobs.start_scan(date(2025, 7, 1), 200, seed=44)
        assert started is not None and self.store.claim_job(started[1])
        return started[1]

    def report(self, job_id: int, done: int, total: int, message: str) -> None:
        self.store.update_progress(job_id, phase="ranking", done=done, total=total, message=message)


@pytest.fixture
def scans_app(tmp_path: Path) -> Iterator[ScansApp]:
    store = Store(tmp_path / "live.db")
    jobs = Jobs(store)
    app = create_app(Settings(offline=False), Lookup(None, store, seed=44, jobs=jobs),
                     ScansPage(store, jobs=jobs, seed=44, rate=5.0))
    try:
        with serving(app) as url:
            yield ScansApp(url, store, jobs)
    finally:
        store.close()


@pytest.fixture
def make(make_page: MakePage, scans_app: ScansApp) -> MakePage:
    def make_scans(**options) -> Page:
        return make_page("/scans", base=scans_app.url, **options)
    return make_scans


def test_ux_dr30_the_estimate_follows_the_number(make: MakePage) -> None:
    """UX-DR30: scans.js updates the rough estimate as the Number of Wallets changes, and hides it for a number not allowed."""
    page = make()
    estimate = page.locator("#wallets-estimate")
    expect(estimate).to_have_text("Rough estimate: about 2 hours at 5 requests per second")
    page.fill("#wallets", "10")
    expect(estimate).to_have_text("Rough estimate: about 10 minutes at 5 requests per second", timeout=WAIT)
    page.fill("#wallets", "5000")
    expect(estimate).to_be_hidden(timeout=WAIT)
    page.fill("#wallets", "500")
    expect(estimate).to_have_text("Rough estimate: about 4.5 hours at 5 requests per second", timeout=WAIT)


def test_ux_dr30_the_warning_shows_when_a_recent_date_is_chosen_and_one_submit_starts(
    make: MakePage, scans_app: ScansApp
) -> None:
    """UX-DR30: with scans.js the warning shows as soon as a recent date is chosen, is tied to the field, and one submit starts."""
    page = make()
    today = datetime.now(UTC).date()
    warning = page.locator("#cutoff-warning")
    expect(warning).to_be_hidden()
    page.fill("#cutoff", (today - timedelta(days=10)).isoformat())
    expect(warning).to_be_visible()
    expect(warning).to_contain_text(FEW_AFTER)
    expect(page.locator("#cutoff")).to_have_attribute("aria-describedby", "cutoff-warning")
    page.fill("#cutoff", "2025-07-01")
    expect(warning).to_be_hidden()
    expect(page.locator("#cutoff")).not_to_have_attribute("aria-describedby", "cutoff-warning")
    page.fill("#cutoff", (today - timedelta(days=10)).isoformat())
    page.click("#start-scan")
    expect(page.locator(".scan-running")).to_be_visible(timeout=WAIT)  # started on the first press
    assert len(scans_app.store.scans()) == 1


def test_ux_dr32_the_page_follows_a_running_scan_to_its_end(make: MakePage, scans_app: ScansApp) -> None:
    """UX-DR32, UX-DR9: bar, step and tab title follow the job; announcements only per new step or 10% and at the end; the form keeps its input."""
    job = scans_app.running()
    page = make()
    bar = page.locator("#scan-progress")
    expect(page).to_have_title("Scans · LiquidOracle")
    expect(bar).not_to_have_attribute("value", "0")  # no count yet: an indeterminate bar

    scans_app.report(job, 34, 100, "Reading Markets: 34 of 100")
    expect(page).to_have_title("34/100 · Scan · LiquidOracle", timeout=WAIT)
    expect(bar).to_have_attribute("aria-valuetext", "Reading Markets: 34 of 100")
    assert bar.evaluate("b => [b.value, b.max]") == [34, 100]
    expect(page.locator("#running-step")).to_have_text("Reading Markets: 34 of 100")

    announced = page.locator("#scan-announce")
    scans_app.report(job, 52, 100, "Reading Markets: 52 of 100")  # a new 10% step: announced
    expect(announced).to_have_text("Reading Markets: 52 of 100", timeout=WAIT)
    scans_app.report(job, 58, 100, "Reading Markets: 58 of 100")  # the same 10% step: not announced
    expect(page).to_have_title("58/100 · Scan · LiquidOracle", timeout=WAIT)
    expect(announced).to_have_text("Reading Markets: 52 of 100")
    scans_app.report(job, 100, 100, "Reading Markets: 100 of 100")
    expect(announced).to_have_text("Reading Markets: 100 of 100", timeout=WAIT)
    scans_app.report(job, 0, 100, "Fetching Wallets: 0 of 100")  # a new step with the same total: still announced
    expect(announced).to_have_text("Fetching Wallets: 0 of 100", timeout=WAIT)
    scans_app.report(job, 3, 600, "Fetching Wallets: 3 of 600")  # a new step: announced
    expect(announced).to_have_text("Fetching Wallets: 3 of 600", timeout=WAIT)

    page.fill("#wallets", "321")  # typed while the Scan runs: kept when the page updates
    page.focus("#start-scan")  # unavailable but focusable (UX-DR9); Enter sends nothing
    page.keyboard.press("Enter")
    assert len(scans_app.store.scans()) == 1

    page.focus(".table-scroll")  # a keyboard user is in the list when it is replaced
    scans_app.store.finish_job(job, JobStatus.STOPPED, message="Polymarket did not answer", keep_progress=True)
    stopped = "Stopped at 3 of 600: Polymarket did not answer"
    expect(page.locator("#scan-list .scan-status")).to_have_text(stopped, timeout=WAIT)
    expect(announced).to_have_text(stopped)
    expect(page).to_have_title("Scans · LiquidOracle")
    expect(page.locator(".scan-running")).to_have_count(0)
    expect(page.locator("#start-scan")).not_to_have_attribute("aria-disabled", "true")
    expect(page.get_by_role("button", name="Resume Scan (Cut-off Date 1 July 2025)")).to_be_visible()
    expect(page.locator("#wallets")).to_have_value("321")
    expect(page.locator("#scan-list-title")).to_be_focused()  # focus moved on purpose, not lost to the page


@pytest.mark.parametrize("width", [1280, 640, 400])
def test_ux_dr10_the_scans_page_fits_every_width(make: MakePage, scans_app: ScansApp, width: int) -> None:
    """UX-DR10: the Scans page with a list and a running Scan never scrolls sideways at 1280, 640 and 400 px."""
    job = scans_app.running()
    scans_app.store.finish_job(job, JobStatus.STOPPED, message="Polymarket did not answer", keep_progress=True)
    scans_app.running()
    page = make(width=width)
    expect(page.locator(".scan-table")).to_be_visible()
    assert_no_sideways_scroll(page, f"/scans at {width} px")
