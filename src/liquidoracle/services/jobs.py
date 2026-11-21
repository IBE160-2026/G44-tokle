"""Background work: the job queue and the one worker thread (AD-5; Story 2.5).

A lookup that needs a fetch is a `job` row. `Jobs.queue_lookup` inserts it (or joins the Wallet's
open job) and wakes the worker; the page then polls the job's progress. The `Worker` is one daemon
thread, started only by `liquidoracle run` (AD-23), that claims one queued job at a time with an
atomic update and runs it through the same fetch pipeline as `load-sample`.
"""

from __future__ import annotations

import logging
import threading

from liquidoracle.data.client import WalletClient
from liquidoracle.data.errors import NoPolymarketHistory, PolymarketUnavailable
from liquidoracle.data.store import NO_HISTORY, Job, JobStatus, Store
from liquidoracle.services.fetch import fetch_wallet

log = logging.getLogger(__name__)

# Progress messages (the `message` of GET /jobs/<id>/progress). The fetching one is EXPERIENCE.md's.
FETCHING = "Fetching trades from Polymarket…"
FINISHED = {
    JobStatus.DONE: "Done",
    JobStatus.STOPPED: "Polymarket did not answer",
    JobStatus.FAILED: "Something went wrong",
}
NO_HISTORY_MESSAGE = "No Polymarket history found"
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

    def wake(self) -> None:
        """Wake the worker if it is waiting."""
        self._wake.set()

    def wait(self, seconds: float) -> None:
        """Block until a job is queued or `seconds` pass (the worker's idle wait)."""
        self._wake.wait(seconds)
        self._wake.clear()


class Worker:
    """The one worker thread (AD-5). Tests call `run_once` directly instead of starting the thread."""

    def __init__(self, client: WalletClient, jobs: Jobs) -> None:
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
        if job.wallet is None:  # only lookup jobs exist so far, and each names its Wallet
            self._store.finish_job(job.id, JobStatus.FAILED, message=FINISHED[JobStatus.FAILED])
            log.error("job %d has no Wallet", job.id)
            return
        try:
            fetch_wallet(self._client, self._store, job.wallet)
        except NoPolymarketHistory:
            self._store.finish_job(job.id, JobStatus.DONE, message=NO_HISTORY_MESSAGE, result=NO_HISTORY)
        except PolymarketUnavailable as error:
            log.warning("lookup of %s stopped: %s", job.wallet, error)
            self._store.finish_job(job.id, JobStatus.STOPPED, message=FINISHED[JobStatus.STOPPED])
        except Exception:  # PolymarketBadRequest or a bug: logged, never shown raw (Conventions › Errors)
            log.exception("lookup of %s failed", job.wallet)
            self._store.finish_job(job.id, JobStatus.FAILED, message=FINISHED[JobStatus.FAILED])
        else:
            self._store.finish_job(job.id, JobStatus.DONE, message=FINISHED[JobStatus.DONE])
