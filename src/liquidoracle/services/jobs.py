"""Background work: the job queue and the one worker thread (AD-5; Stories 2.5 and 4.3).

A lookup that needs a fetch is a `job` row. `Jobs.queue_lookup` inserts it (or joins the Wallet's
open job) and wakes the worker; the page then polls the job's progress. A Scan is a `scan` row
and a job (`Jobs.start_scan`); Resume adds a new job for the same Scan (`Jobs.resume_scan`). The
`Worker` is one daemon thread, started only by `liquidoracle run` (AD-23), that claims one queued
job at a time with an atomic update. Between two units of a Scan's work it runs every waiting
lookup first.
"""

from __future__ import annotations

import logging
import threading
from datetime import date

from liquidoracle.data.client import FunnelClient
from liquidoracle.data.errors import NoPolymarketHistory, PolymarketUnavailable
from liquidoracle.data.store import LOOKUP, NO_HISTORY, SCAN, Job, JobStatus, Store
from liquidoracle.data.window import cutoff_at
from liquidoracle.services.fetch import fetch_wallet
from liquidoracle.services.scan import RANKING, STARTING, run_scan

log = logging.getLogger(__name__)

# Progress messages (the `message` of GET /jobs/<id>/progress). The fetching one is EXPERIENCE.md's.
FETCHING = "Fetching trades from Polymarket…"
FINISHED = {
    JobStatus.DONE: "Done",
    JobStatus.STOPPED: "Polymarket did not answer",
    JobStatus.FAILED: "Something went wrong",
}
NO_HISTORY_MESSAGE = "No Polymarket history found"
RESUMING = "Resuming"  # a resumed Scan's message until its first unit of work reports
IDLE_WAIT = 1.0  # [ASSUMPTION] seconds the worker sleeps when nothing is queued; a new job wakes it at once


class Jobs:
    """The job queue over one store, with the signal that wakes the worker. Safe to share between threads."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self._wake = threading.Event()

    def queue_lookup(self, wallet: str) -> int:
        """A lookup job for the Wallet (its queued or running one, if any) and wake the worker (AD-5)."""
        job_id = self.store.queue_lookup(wallet, message=FETCHING)
        self.wake()
        return job_id

    def start_scan(self, cutoff: date, size: int, *, seed: int) -> tuple[int, int] | None:
        """A new Scan of the top `size` Wallets for this Cut-off Date, as (scan_id, job_id), and wake the worker.

        None while another Scan is queued or running: one Scan at a time (EXPERIENCE.md).
        """
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            raise ValueError(f"the number of Wallets must be a whole number of 1 or more, not {size!r}")
        started = self.store.create_scan(cutoff_at(cutoff), size, seed, phase=RANKING, message=STARTING)
        if started is not None:
            self.wake()
        return started

    def resume_scan(self, scan_id: int) -> int | None:
        """Resume a stopped or interrupted Scan with a new job (AD-5); None when it cannot resume."""
        job_id = self.store.resume_scan(scan_id, phase=RANKING, message=RESUMING)
        if job_id is not None:
            self.wake()
        return job_id

    def wake(self) -> None:
        """Wake the worker if it is waiting."""
        self._wake.set()

    def wait(self, seconds: float) -> None:
        """Block until a job is queued or `seconds` pass (the worker's idle wait)."""
        self._wake.wait(seconds)
        self._wake.clear()


class Worker:
    """The one worker thread (AD-5). Tests call `run_once` directly instead of starting the thread."""

    def __init__(self, client: FunnelClient, jobs: Jobs) -> None:
        self._client = client
        self._jobs = jobs
        self._store = jobs.store
        self._stopping = threading.Event()

    def start(self) -> threading.Thread:
        """Start the daemon thread. Only `liquidoracle run` calls this (AD-23), never the app factory."""
        thread = threading.Thread(target=self._loop, name="liquidoracle-worker", daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        """Ask the thread to stop after its current job (used by tests; the app just exits)."""
        self._stopping.set()
        self._jobs.wake()

    def run_once(self) -> bool:
        """Claim and run one queued job. False when nothing was queued."""
        job = self._store.claim_next_job()
        if job is None:
            return False
        self._run(job)
        return True

    def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                worked = self.run_once()
            except Exception:  # e.g. the database file broke: log it and keep the thread alive
                log.exception("the worker could not claim or finish a job")
                worked = False
            if not worked:
                self._jobs.wait(IDLE_WAIT)

    def _run(self, job: Job) -> None:
        if job.kind == SCAN and job.scan_id is not None:
            self._run_scan(job, job.scan_id)
        elif job.kind == LOOKUP and job.wallet is not None:
            self._run_lookup(job, job.wallet)
        else:
            self._store.finish_job(job.id, JobStatus.FAILED, message=FINISHED[JobStatus.FAILED])
            log.error("job %d (%s) names no Wallet or Scan", job.id, job.kind)

    def run_waiting_lookups(self) -> None:
        """Claim and run every queued lookup: what a Scan does between two units of its work (AD-5)."""
        while (job := self._store.claim_next_lookup()) is not None:
            self._run(job)

    def _run_scan(self, job: Job, scan_id: int) -> None:
        """One run of a Scan (Story 4.3): `stopped` keeps its progress so the page can say how far it got."""
        try:
            run_scan(self._client, self._store, scan_id, job_id=job.id, between=self.run_waiting_lookups)
        except PolymarketUnavailable as error:
            log.warning("Scan %d stopped: %s", scan_id, error)
            self._store.finish_job(job.id, JobStatus.STOPPED, message=FINISHED[JobStatus.STOPPED], keep_progress=True)
        except Exception:  # a bug, or a database that broke: logged, never shown raw; no Resume (AD-5)
            log.exception("Scan %d failed", scan_id)
            self._store.finish_job(job.id, JobStatus.FAILED, message=FINISHED[JobStatus.FAILED], keep_progress=True)
        else:
            self._store.finish_job(job.id, JobStatus.DONE, message=FINISHED[JobStatus.DONE])

    def _run_lookup(self, job: Job, wallet: str) -> None:
        try:
            fetch_wallet(self._client, self._store, wallet)
        except NoPolymarketHistory:
            self._store.finish_job(job.id, JobStatus.DONE, message=NO_HISTORY_MESSAGE, result=NO_HISTORY)
        except PolymarketUnavailable as error:
            log.warning("lookup of %s stopped: %s", wallet, error)
            self._store.finish_job(job.id, JobStatus.STOPPED, message=FINISHED[JobStatus.STOPPED])
        except Exception:  # PolymarketBadRequest or a bug: logged, never shown raw (Conventions › Errors)
            log.exception("lookup of %s failed", wallet)
            self._store.finish_job(job.id, JobStatus.FAILED, message=FINISHED[JobStatus.FAILED])
        else:
            self._store.finish_job(job.id, JobStatus.DONE, message=FINISHED[JobStatus.DONE])
