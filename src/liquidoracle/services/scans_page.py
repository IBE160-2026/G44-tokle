"""The Scans page: the New Scan form, the Scan list and the running Scan's progress (FR-16, UX-DR30 to
UX-DR32; Story 4.4).

The page calls this module only. It checks the form, starts or resumes a Scan through the job queue
(`services.jobs`, Story 4.3) and turns the stored Scans into finished text, taking dates and numbers
from `core/phrases` (AD-25). How a Scan runs is not here: that is `services.scan`. Its name is
`scans_page`, not `scans`, so it is not mixed up with that module.

Offline Mode has no job queue yet (Story 4.6 adds it), so the form is shown read-only and nothing starts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum

from liquidoracle.core import phrases
from liquidoracle.data.polymarket import GAMMA_LIST_PAGES
from liquidoracle.data.real_sample import CUTOFF as SAMPLE_CUTOFF
from liquidoracle.data.store import Job, JobStatus, Scan, ScanStep, Store
from liquidoracle.data.window import cutoff_day
from liquidoracle.records import Verdict
from liquidoracle.services.jobs import FINISHED, Jobs
from liquidoracle.services.scan import DEFAULT_SIZE, MARKET_COUNT, SHORTLIST_FACTOR

# The form's limits and messages, word for word from EXPERIENCE.md (UX-DR30).
MIN_SIZE, MAX_SIZE = 10, 500  # [ASSUMPTION] EXPERIENCE.md: revisit after real Scans
WARN_DAYS = 90  # a Cut-off Date fewer days back than this gets the warning (Edvard, 2026-10-24)
NO_DATE = "Choose a Cut-off Date."
NOT_PAST = "The Cut-off Date must be in the past."
BAD_SIZE = f"Enter a whole number from {MIN_SIZE} to {MAX_SIZE}."
FEW_AFTER = "Very few bets were resolved after this date, so the Hold-up Test and Copy Test may have too little to test."
NO_SCANS = "No Scans yet. A Scan checks the top Wallets by profit made before a date you choose."
OFFLINE_INFO = (
    "Offline Mode scans the whole Sample Dataset with its Cut-off Date, "
    f"{phrases.long_date(date.fromisoformat(SAMPLE_CUTOFF))}."
)
OFFLINE_NOT_READY = "Offline Scans are not ready yet."  # until Story 4.6 adds an offline worker (Edvard, 2026-11-26)
WHOLE_SAMPLE = "Whole Sample Dataset"
PAGE_TITLE = "Scans · LiquidOracle"  # UX-DR8
RUNNING_INFO = ("A Scan is running (", "). You can start a new one when it finishes.")  # EXPERIENCE.md
RUNNING_TITLE = "Scan · LiquidOracle"  # after "84/200 · " while a Scan runs (EXPERIENCE.md)

# The rough time estimate (UX-DR30): the requests a Scan plans today, at the set pace (Edvard, 2026-11-26).
MARKET_REQUESTS = 15  # [ASSUMPTION] typical pages for one Market's two holder lists (at most 30)
PART_REQUESTS = 40  # [ASSUMPTION] typical requests for one Wallet part: positions pages, Gamma batches, activity pages
_DAY = timedelta(days=1)
_WHOLE = re.compile(r"\d{1,9}")
_ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


class Submitted(StrEnum):
    """What a form POST led to."""

    STARTED = "started"  # a new Scan was queued: back to the list
    INVALID = "invalid"  # errors under the fields, nothing started
    WARNED = "warned"  # valid but recent: the warning shows and a second submit starts it
    REFUSED = "refused"  # Offline Mode or a Scan already running: nothing started


@dataclass(frozen=True, slots=True)
class NewScanForm:
    """The New Scan form's values and messages (UX-DR30). Values are the text the user typed."""

    cutoff: str
    size: str
    cutoff_error: str | None = None
    size_error: str | None = None
    warning: str | None = None  # FEW_AFTER when the date is recent
    confirmed: bool = False  # the warning was shown, so the next submit starts
    estimate: str | None = None
    read_only: bool = False  # Offline Mode
    blocked: bool = False  # "Start Scan" cannot start now: shown unavailable but focusable (UX-DR9)
    blocked_reason: str | None = None  # the line under the button saying why; a running Scan's info box says it instead
    today: str = ""  # "2026-11-26": today in UTC, for scans.js's warning
    latest: str = ""  # "2026-11-25": the latest day allowed, the date field's `max`


@dataclass(frozen=True, slots=True)
class RunningScan:
    """The Scan whose job is queued or running, for the info box, the progress bar and the tab title."""

    scan_id: int
    job_id: int
    step: str  # the job's progress text: "Reading Markets: 34 of 100", "84 of 200 Wallets checked"
    done: int
    total: int  # 0 while the step has no count yet: the bar then shows no value
    info: tuple[str, str]  # the words around the step: "A Scan is running (" … "). You can start a new one when it finishes."
    title: str  # "84/200 · Scan · LiquidOracle"


@dataclass(frozen=True, slots=True)
class ScanRow:
    """One line of the Scan list (UX-DR31)."""

    scan_id: int
    run_date: str  # "26 Nov 2026"
    cutoff: str  # "1 July 2025"
    wallets: str  # "200"
    watchlist: str | None  # "3"; None until the Scan is finished
    status: str
    resume_label: str | None  # "Resume Scan (Cut-off Date 1 July 2025)" when it can resume now


@dataclass(frozen=True, slots=True)
class ScansView:
    form: NewScanForm
    rows: tuple[ScanRow, ...]
    running: RunningScan | None
    empty: str = NO_SCANS

    @property
    def title(self) -> str:
        return self.running.title if self.running is not None else PAGE_TITLE


class ScansPage:
    """One run's Scans page over its store (AD-13). `jobs` is a live run's job queue; None in Offline Mode."""

    def __init__(self, store: Store, *, jobs: Jobs | None, seed: int, rate: float) -> None:
        self._store = store
        self._jobs = jobs
        self._seed = seed
        self._rate = rate

    def view(self, form: NewScanForm | None = None) -> ScansView:
        """The whole page: the form (blank, or as submitted), the Scan list and the running Scan."""
        scans = self._store.scans()
        running = next((s for s in scans if _open(s)), None)
        sizes = self._store.watchlist_sizes(Verdict.SKILLED.value)
        rows = tuple(self._row(s, sizes.get(s.scan_id, 0), resumable=running is None) for s in scans)
        progress = None if running is None or running.job is None else _running(running.scan_id, running.job)
        return ScansView(self._form(form, running=progress is not None), rows, progress)

    def submit(self, cutoff: str, size: str, *, confirmed: bool) -> tuple[Submitted, ScansView | None]:
        """The form POST (UX-DR30): start a Scan, or the page again with what stopped it."""
        cutoff, size = cutoff.strip(), size.strip()
        day, cutoff_error = self._check_date(cutoff)
        number, size_error = _check_size(size)
        warning = FEW_AFTER if day is not None and cutoff_error is None and self._recent(day) else None
        form = NewScanForm(cutoff, size, cutoff_error, size_error, warning, confirmed=warning is not None)
        if self._jobs is None:
            return Submitted.REFUSED, None
        if cutoff_error or size_error:
            return Submitted.INVALID, self.view(form)
        if warning and not confirmed:
            return Submitted.WARNED, self.view(form)
        if day is None or number is None:  # never: both were checked above
            return Submitted.INVALID, self.view(form)
        started = self._jobs.start_scan(day, number, seed=self._seed)
        return (Submitted.STARTED if started is not None else Submitted.REFUSED), None

    def resume(self, scan_id: int) -> bool:
        """Resume a stopped or interrupted Scan (AD-5); False when it cannot (or in Offline Mode)."""
        return self._jobs is not None and self._jobs.resume_scan(scan_id) is not None

    def estimate(self, size: str) -> str | None:
        """The rough time estimate for this many Wallets, or None when the number is not allowed or offline."""
        number, error = _check_size(size.strip())
        if self._jobs is None or error is not None or number is None:
            return None
        planned = planned_requests(number)
        for scan in self._store.scans():  # newest first: the last finished Scan whose time is known
            finished = scan.step is ScanStep.DONE and not scan.data_rebuilt
            seconds = self._store.scan_seconds(scan.scan_id) if finished else None
            if seconds:
                time = phrases.rough_time(planned * seconds / planned_requests(scan.size))
                return f"Rough estimate: {time}, based on your last Scan"
        unit = "request" if self._rate == 1 else "requests"
        return f"Rough estimate: {phrases.rough_time(planned / self._rate)} at {self._rate:g} {unit} per second"

    # --- helpers ---------------------------------------------------------------------------------

    def _today(self) -> date:
        return datetime.fromtimestamp(self._store.now(), UTC).date()

    def _check_date(self, text: str) -> tuple[date | None, str | None]:
        if not _ISO_DAY.fullmatch(text):
            return None, NO_DATE
        try:
            day = date.fromisoformat(text)
        except ValueError:
            return None, NO_DATE
        return day, NOT_PAST if day >= self._today() else None

    def _recent(self, day: date) -> bool:
        return (self._today() - day) < WARN_DAYS * _DAY

    def _form(self, form: NewScanForm | None, *, running: bool) -> NewScanForm:
        today = self._today()
        days = {"today": today.isoformat(), "latest": (today - _DAY).isoformat()}
        if self._jobs is None:  # Offline Mode: fixed values, read-only, no estimate (UX-DR30)
            return NewScanForm(
                SAMPLE_CUTOFF, WHOLE_SAMPLE, read_only=True, blocked=True, blocked_reason=OFFLINE_NOT_READY, **days
            )
        form = form or NewScanForm("", str(DEFAULT_SIZE))
        return replace(form, estimate=self.estimate(form.size), blocked=running, **days)

    def _row(self, scan: Scan, watchlist: int, *, resumable: bool) -> ScanRow:
        cutoff = phrases.long_date(cutoff_day(scan.cutoff))
        finished = scan.step is ScanStep.DONE
        can_resume = (
            resumable and not finished and not scan.data_rebuilt and scan.job is not None
            and scan.job.status in (JobStatus.STOPPED, JobStatus.INTERRUPTED)
        )
        return ScanRow(
            scan.scan_id,
            phrases.run_date(scan.as_of),
            cutoff,
            phrases.count(scan.size),
            phrases.count(watchlist) if finished else None,
            status_text(scan),
            f"Resume Scan (Cut-off Date {cutoff})" if can_resume else None,
        )


def status_text(scan: Scan) -> str:
    """The Scan list's status column (UX-DR31, EXPERIENCE.md *Scan stopped*)."""
    job = scan.job
    if scan.step is ScanStep.DONE:
        return "Finished"
    if scan.data_rebuilt:
        return "Data rebuilt, cannot resume"
    if job is None or job.status is JobStatus.QUEUED:
        return "Waiting to start"
    if job.status is JobStatus.RUNNING:
        return f"Running: {job.message}"
    at = f" at {phrases.of_total(job.done, job.total)}" if job.total > 0 else ""
    if job.status is JobStatus.INTERRUPTED:
        return f"Interrupted{at}"
    if job.status is JobStatus.STOPPED:
        return f"Stopped{at}: {FINISHED[JobStatus.STOPPED]}"
    return "Failed"  # failed, or a job marked done on a Scan that never finished


def planned_requests(size: int) -> int:
    """The requests a Scan of `size` Wallets plans today (Edvard, 2026-11-26): the Gamma list, the Market
    reads, 3 x N before parts and N after parts. Epic 6 adds the Copy Sample prices with its phase."""
    return GAMMA_LIST_PAGES + MARKET_COUNT * MARKET_REQUESTS + (SHORTLIST_FACTOR + 1) * size * PART_REQUESTS


def _check_size(text: str) -> tuple[int | None, str | None]:
    if not _WHOLE.fullmatch(text) or not MIN_SIZE <= int(text) <= MAX_SIZE:
        return None, BAD_SIZE
    return int(text), None


def _open(scan: Scan) -> bool:
    return scan.job is not None and scan.job.status in (JobStatus.QUEUED, JobStatus.RUNNING)


def _running(scan_id: int, job: Job) -> RunningScan:
    title = f"{job.done}/{job.total} · {RUNNING_TITLE}" if job.total > 0 else PAGE_TITLE
    return RunningScan(
        scan_id, job.id, job.message, job.done, job.total,
        RUNNING_INFO, title,
    )
