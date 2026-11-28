"""The SQLite store: the only module that runs SQL (AD-6).

Plain `sqlite3`, WAL mode, a busy timeout, foreign keys on, one connection per thread, and every
write transaction opened with `BEGIN IMMEDIATE` and kept short. The schema is `schema.sql`, and
its version is `PRAGMA user_version`.

A Wallet is written as a snapshot (AD-19): `begin_snapshot` gives a `fetch_id`, rows are added
under it, and `finish_snapshot` makes it visible in one final step, deleting that Wallet's older
snapshots in the same transaction (Edvard, 2026-11-19, Story 1.6). Readers see only complete
snapshots. `wallet_lock` lets one fetch of a Wallet run at a time, across every thread that
shares this Store (AD-19). `serving_snapshot` is the one answer to "which snapshot serves this
window" (AD-4): a snapshot's key is its Wallet, window limit, Cut-off Date and side, so a lookup
never reads a Scan's part or the reverse (Story 4.3). Jobs (AD-5, Story 2.5) are rows the worker
claims with one atomic update. A Scan (Story 4.3) is stored step by step as it runs, so Resume
continues from what is stored; its snapshots are never deleted, and a schema change keeps them.
Price history (Story 6.1) is stored by token: the windows that were asked and their one-minute
points, kept for good and at every schema change (AD-4, AD-24).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from bisect import bisect_right
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from liquidoracle.records import (
    HOLDUP_AFTER,  # AD-22: the scope of a Scan's Hold-up group results (FR-17)
    HOLDUP_GROUPS,
    PRICE_ROUTES,
    ActivityRow,
    Candidate,
    FunnelMarket,
    GroupResult,
    ListedPosition,
    Market,
    PricePoint,
    Verdict,
    unread_positions,
)

log = logging.getLogger(__name__)

# 2: the Wallet window (Story 2.2); 3: Market events (Story 2.4); 4: jobs (Story 2.5); 5: window_capped (Story 3.3);
# 6: Scans and the snapshot key (Story 4.3); 7: Hold-up group results (Story 5.1); 8: price history (Story 6.1)
SCHEMA_VERSION = 8
FIRST_KEEPING_VERSION = 6  # AD-6: from this version on, a schema change keeps the Scans (Story 4.3)
BUSY_TIMEOUT_SECONDS = 5.0  # [ASSUMPTION] AD-6: long enough for the worker's short writes
SCHEMA_FILE = Path(__file__).with_name("schema.sql")

# AD-13: Offline Mode and live runs never share a database file. Relative to the repository folder.
OFFLINE_DB = Path("instance") / "offline.db"
LIVE_DB = Path("instance") / "live.db"

# The error a broken, locked or full database file raises, so callers can catch it without
# importing sqlite3 themselves (only this module runs SQL, AD-6).
StoreError = sqlite3.Error


@dataclass(frozen=True, slots=True)
class Snapshot:
    """One complete fetch of one Wallet's window (AD-8, AD-19), with the Markets its rows refer to.

    `activity_read_until` is None when the activity read was complete (AD-7). `window_capped` is True
    when the window's limit left older Positions out (FR-11, Story 3.3).
    """

    fetch_id: int
    wallet: str
    completed_at: int
    positions: tuple[ListedPosition, ...]
    activity: tuple[ActivityRow, ...]
    markets: tuple[Market, ...]
    window_limit: int
    activity_read_until: int | None
    window_capped: bool = False
    cutoff: int | None = None  # 00:00 UTC epoch of the Cut-off Date; None for a lookup's window (AD-4)
    side: str | None = None  # "before" or "after"; None for a lookup's window

    def not_fully_read(self) -> tuple[ListedPosition, ...]:
        """The window's Positions whose Market resolved in or after the last activity row's second (AD-7, AD-11)."""
        return unread_positions(self.positions, self.markets, self.activity_read_until)


class JobStatus(StrEnum):
    """AD-5's job states."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    INTERRUPTED = "interrupted"  # the app was closed while it ran
    STOPPED = "stopped"  # Polymarket did not answer
    FAILED = "failed"  # an unexpected error, logged


LOOKUP = "lookup"  # a lookup that needs a fetch (Story 2.5)
SCAN = "scan"  # one run of a Scan (Story 4.3)
NO_HISTORY = "no_history"  # a finished lookup's result when Polymarket has no positions for the address
_OPEN = (JobStatus.QUEUED.value, JobStatus.RUNNING.value)
_RESUMABLE = (JobStatus.STOPPED, JobStatus.INTERRUPTED)  # AD-5: a failed Scan has no Resume
INTERRUPTED_MESSAGE = "Interrupted: the app was closed"  # the progress message of an interrupted job

BEFORE, AFTER = "before", "after"  # the two parts of a Cut-off Date (AD-7)
SCAN_BEFORE, SCAN_WHOLE = "scan_before", "scan_whole"  # AD-22's result scopes of a Scan


class ScanStep(StrEnum):
    """How far a Scan got (Story 4.3). Each step is stored in the transaction that finishes it."""

    CREATED = "created"
    MARKETS = "markets"  # the Market set is stored
    SHORTLISTED = "shortlisted"  # the 3 x N shortlist is stored
    RANKED = "ranked"  # every shortlisted Wallet is read and the top N marked
    DONE = "done"  # every phase finished (AD-5)


class WalletOutcome(StrEnum):
    """How a shortlisted Wallet's before part was read (AD-9)."""

    RANKED = "ranked"
    NO_HISTORY = "no_history"  # $0, not flagged
    REFUSED = "refused"  # Polymarket refused it: $0, kept and flagged "not fully read"
    CONTRACT = "contract"  # a protocol contract address: dropped and counted


# AD-6: the tables a schema change copies into the new schema, in this order. The other rows of the job,
# snapshot, row and market tables are dropped; every other table is rebuilt empty.
_SCAN_TABLES = ("scan", "scan_market", "scan_candidate", "scan_wallet", "scan_result", "group_result")
_SNAPSHOT_TABLES = ("snapshot", "listed_position", "activity_row", "market")
_PRICE_TABLES = ("price_window", "price_point")  # AD-24: stored prices never expire; copied whole
KEPT_TABLES = (*_SCAN_TABLES, "job", *_SNAPSHOT_TABLES, *_PRICE_TABLES)
# Kept tables an older file may lack: `group_result` came with version 7, so a version 6 file's Scans are
# kept without Hold-up rows (Story 5.1); the price tables came with version 8 (Story 6.1).
_ADDED_LATER = frozenset({"group_result", *_PRICE_TABLES})
_FROZEN_IDS = (
    "SELECT before_fetch_id FROM scan_wallet WHERE before_fetch_id IS NOT NULL"
    " UNION SELECT after_fetch_id FROM scan_wallet WHERE after_fetch_id IS NOT NULL"
    " UNION SELECT fetch_id FROM scan_result WHERE fetch_id IS NOT NULL"
    " UNION SELECT after_fetch_id FROM scan_result WHERE after_fetch_id IS NOT NULL"
)


@dataclass(frozen=True, slots=True)
class Job:
    """One job row (AD-5). `done`, `total`, `phase` and `message` are its progress."""

    id: int
    kind: str
    wallet: str | None
    status: JobStatus
    phase: str
    done: int
    total: int
    message: str
    result: str | None
    created_at: int
    finished_at: int | None
    scan_id: int | None = None


@dataclass(frozen=True, slots=True)
class Scan:
    """One Scan row (FR-16, AD-19). `cutoff` is 00:00 UTC epoch, `as_of` when it was created.
    `job` is its latest job (Resume adds one), whose status is the Scan's."""

    scan_id: int
    cutoff: int
    size: int
    seed: int
    as_of: int
    step: ScanStep
    candidate_count: int | None
    data_rebuilt: bool
    job: Job | None


@dataclass(frozen=True, slots=True)
class ScanMarket:
    """A Market of a Scan's set (AD-21); `state` is None until read, then "used" or "partial" (AD-9)."""

    seq: int
    condition_id: str
    volume: float
    state: str | None


@dataclass(frozen=True, slots=True)
class ScanWallet:
    """A shortlisted Wallet of a Scan and how it ranked (AD-9, AD-19); `outcome` None until read."""

    seq: int
    wallet: str
    estimate: float
    outcome: WalletOutcome | None
    real_pnl: float | None
    not_fully_read: bool
    before_fetch_id: int | None
    after_fetch_id: int | None
    top: bool


@dataclass(frozen=True, slots=True)
class ScanResult:
    """One stored Skill Test result of a Scan (AD-22). `fetch_id` is the before part's snapshot and
    `after_fetch_id` the after part's (`scan_whole` only); None when the Wallet had nothing to read."""

    wallet: str
    scope: str
    verdict: str
    p_value: float | None
    tested_count: int
    real_pnl: float
    not_fully_read: bool
    fetch_id: int | None
    after_fetch_id: int | None


class Store:
    """One SQLite database file. Safe to share between threads: each thread gets its own connection."""

    def __init__(self, path: Path, *, clock: Callable[[], float] = time.time) -> None:
        self.path = Path(path)
        self._clock = clock
        self._local = threading.local()
        self._connections: list[tuple[threading.Thread, sqlite3.Connection]] = []
        self._lock = threading.Lock()
        self._wallet_locks: dict[str, threading.Lock] = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prepare_schema()

    # --- writing a snapshot (AD-19) -------------------------------------------------------------

    @contextmanager
    def wallet_lock(self, wallet: str) -> Iterator[None]:
        """Hold the Wallet's lock: one fetch of a Wallet at a time, for web threads and the worker alike (AD-19).

        The locks belong to this Store object; the app opens one Store per database file (AD-13).
        """
        with self._lock:
            lock = self._wallet_locks.setdefault(wallet, threading.Lock())
        with lock:
            yield

    def begin_snapshot(
        self, wallet: str, *, window_limit: int, cutoff: int | None = None, side: str | None = None
    ) -> int:
        """Start a snapshot of `wallet`'s window; it stays invisible until `finish_snapshot`.

        `cutoff` (00:00 UTC epoch) and `side` name the part of a Cut-off Date it is; both None for a lookup (AD-4).
        """
        _check_key(cutoff, side)
        with self._write() as db:
            cursor = db.execute(
                "INSERT INTO snapshot (wallet, window_limit, started_at, cutoff, side) VALUES (?, ?, ?, ?, ?)",
                (wallet, window_limit, self._now(), cutoff, side),
            )
            return int(cursor.lastrowid)

    def add_positions(self, fetch_id: int, rows: Sequence[ListedPosition]) -> None:
        with self._write() as db:
            seq = self._next_seq(db, "listed_position", fetch_id)
            db.executemany(
                "INSERT INTO listed_position (fetch_id, seq, condition_id, token_id, status, shares_bought,"
                " first_entry_at, last_event_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (fetch_id, seq + i, r.condition_id, r.token_id, r.status, r.shares_bought, r.first_entry_at,
                     r.last_event_at)
                    for i, r in enumerate(rows)
                ),
            )

    def add_activity(self, fetch_id: int, rows: Sequence[ActivityRow]) -> None:
        """Add activity rows in order. Identical-looking rows stay separate fills (AD-19)."""
        with self._write() as db:
            seq = self._next_seq(db, "activity_row", fetch_id)
            db.executemany(
                "INSERT INTO activity_row (fetch_id, seq, type, condition_id, timestamp, size, usdc_size, price,"
                " token_id, side) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (fetch_id, seq + i, r.type, r.condition_id, r.timestamp, r.size, r.usdc_size, r.price,
                     r.token_id, r.side)
                    for i, r in enumerate(rows)
                ),
            )

    def save_markets(self, markets: Iterable[Market]) -> None:
        """Store Market records, one per `condition_id`, shared by every snapshot (AD-4)."""
        now = self._now()
        with self._write() as db:
            db.executemany(
                f"INSERT OR REPLACE INTO market ({_MARKET_COLUMNS}, fetched_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (m.condition_id, int(m.closed), m.closed_time, json.dumps(list(m.token_ids)),
                     json.dumps(list(m.outcome_prices)), int(m.fees_enabled), m.start_time, m.fee_rate,
                     m.fee_exponent, json.dumps(list(m.tags)), m.event_id, m.neg_risk_id, now)
                    for m in markets
                ),
            )

    def resolved_markets(self, condition_ids: Sequence[str]) -> dict[str, Market]:
        """The stored records of those Markets that are resolved; they never expire (AD-4).

        Open or unclear Markets are left out, so the caller fetches them again.
        """
        found: dict[str, Market] = {}
        db = self._connection()
        ids = list(dict.fromkeys(condition_ids))
        for i in range(0, len(ids), 500):  # SQLite allows a limited number of ? per statement
            chunk = ids[i : i + 500]
            marks = ", ".join("?" for _ in chunk)
            for row in db.execute(f"SELECT {_MARKET_COLUMNS} FROM market WHERE condition_id IN ({marks})", chunk):
                market = _market(row)
                if market.resolved:
                    found[market.condition_id] = market
        return found

    def finish_snapshot(
        self, fetch_id: int, *, activity_read_until: int | None = None, window_capped: bool = False
    ) -> None:
        """Make the snapshot visible and delete the Wallet's older snapshots of the same part, in one transaction.

        `activity_read_until` is the time of the last activity row read when the read was capped
        or cut short (AD-7), None when it was complete. `window_capped` says the window's limit
        left older Positions out (FR-11, Story 3.3). Refused when the snapshot is unknown or
        already finished, or when one of its rows names a Market that is not stored, so a visible
        snapshot is always complete. A CONVERSION row names its negative-risk event instead, which
        must be the `neg_risk_id` of a stored Market (AD-11, Story 2.4).
        """
        with self._write() as db:
            row = db.execute(
                "SELECT wallet, cutoff, side FROM snapshot WHERE fetch_id = ? AND completed_at IS NULL", (fetch_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"snapshot {fetch_id} does not exist or is already finished")
            missing = db.execute(
                "SELECT condition_id FROM (SELECT condition_id FROM listed_position WHERE fetch_id = ?"
                " UNION SELECT condition_id FROM activity_row WHERE fetch_id = ? AND type != 'CONVERSION')"
                " WHERE condition_id NOT IN (SELECT condition_id FROM market)"
                " UNION SELECT condition_id FROM activity_row WHERE fetch_id = ? AND type = 'CONVERSION'"
                " AND condition_id NOT IN (SELECT condition_id FROM market)"
                " AND condition_id NOT IN (SELECT neg_risk_id FROM market WHERE neg_risk_id IS NOT NULL) LIMIT 1",
                (fetch_id, fetch_id, fetch_id),
            ).fetchone()
            if missing is not None:
                raise ValueError(f"snapshot {fetch_id} refers to Market {missing[0]}, which is not stored")
            db.execute(
                "UPDATE snapshot SET completed_at = ?, activity_read_until = ?, window_capped = ? WHERE fetch_id = ?",
                (self._now(), activity_read_until, int(window_capped), fetch_id),
            )
            # Older snapshots with this key go, and any abandoned one of the Wallet; their rows follow (ON DELETE
            # CASCADE). A snapshot a Scan refers to is never deleted (AD-6, AD-19; Story 4.3).
            db.execute(
                "DELETE FROM snapshot WHERE wallet = ? AND fetch_id < ?"
                " AND ((cutoff IS ? AND side IS ?) OR completed_at IS NULL)"
                f" AND fetch_id NOT IN ({_FROZEN_IDS})",
                (row[0], fetch_id, row[1], row[2]),
            )

    # --- reading ------------------------------------------------------------------------------

    def latest_snapshot(self, wallet: str) -> Snapshot | None:
        """The Wallet's newest complete lookup snapshot, or None. Half-written snapshots are never returned."""
        return self.serving_snapshot(wallet)

    def serving_snapshot(
        self,
        wallet: str,
        *,
        window_limit: int | None = None,
        max_age: float | None = None,
        cutoff: int | None = None,
        side: str | None = None,
    ) -> Snapshot | None:
        """AD-4: the one snapshot that serves this window, or None.

        The Wallet's newest complete snapshot of this part (`cutoff` and `side`; a lookup's window
        when both are None) whose own window is `window_limit` (any, when None) and that was
        completed less than `max_age` seconds ago (any age, when None). A lookup never reads a
        Scan's part, nor a Scan another date's (Story 4.3). Rows are never merged across
        snapshots: a snapshot serves the whole window or nothing.
        """
        _check_key(cutoff, side)
        where = "wallet = ? AND completed_at IS NOT NULL AND cutoff IS ? AND side IS ?"
        args: list[object] = [wallet, cutoff, side]
        if window_limit is not None:
            where += " AND window_limit = ?"
            args.append(window_limit)
        if max_age is not None:
            where += " AND completed_at > ?"
            args.append(self._now() - max_age)
        db = self._connection()
        db.execute("BEGIN")  # one read transaction, so a finish in another thread cannot cut it in half
        try:
            head = db.execute(
                f"SELECT fetch_id FROM snapshot WHERE {where} ORDER BY fetch_id DESC LIMIT 1",  # fixed text above
                args,
            ).fetchone()
            return None if head is None else _read_snapshot(db, int(head[0]))
        finally:
            if db.in_transaction:
                db.execute("COMMIT")

    def snapshot(self, fetch_id: int) -> Snapshot | None:
        """One complete snapshot by its `fetch_id`, whatever its age: how a Scan reads its frozen snapshots (AD-19)."""
        db = self._connection()
        db.execute("BEGIN")
        try:
            return _read_snapshot(db, fetch_id)
        finally:
            if db.in_transaction:
                db.execute("COMMIT")

    def has_snapshot(self, wallet: str) -> bool:
        """True when the Wallet has a complete lookup snapshot (Story 1.7's Lookup page), without reading its rows."""
        row = self._connection().execute(
            "SELECT 1 FROM snapshot WHERE wallet = ? AND cutoff IS NULL AND completed_at IS NOT NULL LIMIT 1", (wallet,)
        ).fetchone()
        return row is not None

    def snapshot_time(self, wallet: str, *, window_limit: int) -> int | None:
        """When the Wallet's newest complete lookup snapshot of this window was completed, or None (AD-4's outage offer)."""
        row = self._connection().execute(
            "SELECT MAX(completed_at) FROM snapshot WHERE wallet = ? AND window_limit = ? AND cutoff IS NULL"
            " AND completed_at IS NOT NULL",
            (wallet, window_limit),
        ).fetchone()
        return None if row[0] is None else int(row[0])

    def wallet_count(self) -> int:
        """How many Wallets have a complete lookup snapshot."""
        row = self._connection().execute(
            "SELECT COUNT(DISTINCT wallet) FROM snapshot WHERE cutoff IS NULL AND completed_at IS NOT NULL"
        ).fetchone()
        return int(row[0])

    # --- jobs (AD-5) -----------------------------------------------------------------------------

    def queue_lookup(self, wallet: str, *, message: str) -> int:
        """A lookup job for the Wallet: its queued or running one if it has one, else a new `queued` row."""
        with self._write() as db:
            row = db.execute(
                "SELECT id FROM job WHERE kind = ? AND wallet = ? AND status IN (?, ?) ORDER BY id DESC LIMIT 1",
                (LOOKUP, wallet, *_OPEN),
            ).fetchone()
            if row is not None:
                return int(row[0])
            cursor = db.execute(
                "INSERT INTO job (kind, wallet, status, phase, done, total, message, created_at)"
                " VALUES (?, ?, ?, 'fetch', 0, 1, ?, ?)",
                (LOOKUP, wallet, JobStatus.QUEUED.value, message, self._now()),
            )
            return int(cursor.lastrowid)

    def claim_job(self, job_id: int) -> bool:
        """AD-5: take a queued job with one atomic update; True only for the one caller that got it."""
        with self._write() as db:
            cursor = db.execute(
                "UPDATE job SET status = ? WHERE id = ? AND status = ?",
                (JobStatus.RUNNING.value, job_id, JobStatus.QUEUED.value),
            )
            return cursor.rowcount == 1

    def claim_next_job(self) -> Job | None:
        """The next queued job, claimed, or None: lookups first, then oldest first (AD-5).

        The queue is read once and each job tried in turn; a job another claimer took in between is
        skipped. When none can be claimed it returns None and the worker looks again after its wait,
        so a claim that keeps failing can never spin for ever (Edvard, 2026-11-21, Story 2.5).
        """
        queued = self._connection().execute(
            "SELECT id FROM job WHERE status = ? ORDER BY kind != ?, id",
            (JobStatus.QUEUED.value, LOOKUP),
        ).fetchall()
        for (job_id,) in queued:
            if self.claim_job(int(job_id)):
                return self.job(int(job_id))
        return None

    def claim_next_lookup(self) -> Job | None:
        """The next queued lookup, claimed, or None: what a Scan runs between two units of its work (AD-5)."""
        queued = self._connection().execute(
            "SELECT id FROM job WHERE status = ? AND kind = ? ORDER BY id", (JobStatus.QUEUED.value, LOOKUP)
        ).fetchall()
        for (job_id,) in queued:
            if self.claim_job(int(job_id)):
                return self.job(int(job_id))
        return None

    def update_progress(self, job_id: int, *, phase: str, done: int, total: int, message: str) -> None:
        """A running job's progress, the `{phase, done, total, message}` of GET /jobs/<id>/progress (AD-5)."""
        with self._write() as db:
            db.execute(
                "UPDATE job SET phase = ?, done = ?, total = ?, message = ? WHERE id = ? AND status = ?",
                (phase, done, total, message, job_id, JobStatus.RUNNING.value),
            )

    def finish_job(
        self, job_id: int, status: JobStatus, *, message: str, result: str | None = None, keep_progress: bool = False
    ) -> None:
        """End a running job: its final status, progress complete, and an optional result.

        With `keep_progress` the job keeps its `done` count, so a stopped Scan can say how far it got
        ("Stopped at 120 of 200", EXPERIENCE.md). Only a `running` job changes, so a job already
        marked otherwise (e.g. `interrupted`) keeps its status.
        """
        if status in (JobStatus.QUEUED, JobStatus.RUNNING):
            raise ValueError(f"a job cannot finish as {status}")
        done = "done" if keep_progress else "total"
        with self._write() as db:
            db.execute(
                f"UPDATE job SET status = ?, result = ?, message = ?, done = {done}, finished_at = ?"  # fixed text
                " WHERE id = ? AND status = ?",
                (status.value, result, message, self._now(), job_id, JobStatus.RUNNING.value),
            )

    def interrupt_running_jobs(self) -> int:
        """AD-5: at startup, every job left `running` becomes `interrupted`. Returns how many."""
        with self._write() as db:
            cursor = db.execute(
                "UPDATE job SET status = ?, message = ?, finished_at = ? WHERE status = ?",
                (JobStatus.INTERRUPTED.value, INTERRUPTED_MESSAGE, self._now(), JobStatus.RUNNING.value),
            )
            return cursor.rowcount

    def job(self, job_id: int) -> Job | None:
        """One job row, or None when there is no such job."""
        row = self._connection().execute(f"SELECT {_JOB_COLUMNS} FROM job WHERE id = ?", (job_id,)).fetchone()
        return None if row is None else _job(row)

    # --- Scans (FR-16, AD-5, AD-19, AD-22; Story 4.3) ------------------------------------------

    def create_scan(self, cutoff: int, size: int, seed: int, *, phase: str, message: str) -> tuple[int, int] | None:
        """A new Scan and its queued job, as (scan_id, job_id); None while another Scan is queued or running.

        One Scan at a time (EXPERIENCE.md). Its as-of time is now (AD-19).
        """
        with self._write() as db:
            if self._open_scan_job(db) is not None:
                return None
            now = self._now()
            scan_id = int(db.execute(
                "INSERT INTO scan (cutoff, size, seed, as_of, step) VALUES (?, ?, ?, ?, ?)",
                (cutoff, size, seed, now, ScanStep.CREATED.value),
            ).lastrowid)
            return scan_id, self._insert_scan_job(db, scan_id, phase=phase, message=message)

    def resume_scan(self, scan_id: int, *, phase: str, message: str) -> int | None:
        """A new queued job for a stopped or interrupted Scan (AD-5), or None when it cannot resume:
        unknown, finished, failed, rebuilt (AD-6), already queued or running, or another Scan is."""
        with self._write() as db:
            scan = db.execute("SELECT step, data_rebuilt FROM scan WHERE scan_id = ?", (scan_id,)).fetchone()
            if scan is None or scan[0] == ScanStep.DONE.value or scan[1]:
                return None
            latest = db.execute(
                "SELECT status FROM job WHERE scan_id = ? ORDER BY id DESC LIMIT 1", (scan_id,)
            ).fetchone()
            if latest is None or JobStatus(latest[0]) not in _RESUMABLE or self._open_scan_job(db) is not None:
                return None
            return self._insert_scan_job(db, scan_id, phase=phase, message=message)

    def scan(self, scan_id: int) -> Scan | None:
        """One Scan with its latest job, or None."""
        db = self._connection()
        row = db.execute(
            "SELECT scan_id, cutoff, size, seed, as_of, step, candidate_count, data_rebuilt FROM scan WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()
        if row is None:
            return None
        job = db.execute(
            f"SELECT {_JOB_COLUMNS} FROM job WHERE scan_id = ? ORDER BY id DESC LIMIT 1", (scan_id,)
        ).fetchone()
        return Scan(*row[:5], ScanStep(row[5]), row[6], bool(row[7]), None if job is None else _job(job))

    def scans(self) -> tuple[Scan, ...]:
        """Every Scan with its latest job, newest first: the Scan list (FR-16, UX-DR31; Story 4.4)."""
        db = self._connection()
        jobs = (_job(row) for row in db.execute(
            f"SELECT {_JOB_COLUMNS} FROM job WHERE id IN (SELECT MAX(id) FROM job WHERE scan_id IS NOT NULL GROUP BY scan_id)"
        ))
        latest = {job.scan_id: job for job in jobs}
        return tuple(
            Scan(*row[:5], ScanStep(row[5]), row[6], bool(row[7]), latest.get(int(row[0])))
            for row in db.execute(
                "SELECT scan_id, cutoff, size, seed, as_of, step, candidate_count, data_rebuilt FROM scan"
                " ORDER BY scan_id DESC"
            )
        )

    def scan_seconds(self, scan_id: int) -> int | None:
        """How long the Scan's jobs took, from queued to finished, added up over Resumes (Story 4.4's estimate).

        None when a run was interrupted: its end is stamped when the app next starts, not when it closed,
        so the Scan's time is not known (Story 4.4 review).
        """
        total, interrupted = self._connection().execute(
            "SELECT COALESCE(SUM(finished_at - created_at), 0), COALESCE(SUM(status = ?), 0) FROM job"
            " WHERE scan_id = ? AND finished_at IS NOT NULL",
            (JobStatus.INTERRUPTED.value, scan_id),
        ).fetchone()
        return None if interrupted else int(total)

    def watchlist_sizes(self, verdict: str) -> dict[int, int]:
        """How many `scan_whole` results of each Scan have this Verdict (the Watchlist size, UX-DR31)."""
        return {int(scan_id): int(n) for scan_id, n in self._connection().execute(
            "SELECT scan_id, COUNT(*) FROM scan_result WHERE scope = ? AND verdict = ? GROUP BY scan_id",
            (SCAN_WHOLE, verdict),
        )}

    def set_scan_markets(self, scan_id: int, markets: Sequence[FunnelMarket]) -> None:
        """Store the Scan's Market set in volume order and their Gamma records, and move it to `markets` (AD-21)."""
        self.save_markets(m.market for m in markets)
        with self._write() as db:
            self._advance(db, scan_id, ScanStep.CREATED, ScanStep.MARKETS)
            db.executemany(
                "INSERT INTO scan_market (scan_id, seq, condition_id, volume) VALUES (?, ?, ?, ?)",
                ((scan_id, i, m.market.condition_id, m.volume) for i, m in enumerate(markets)),
            )

    def scan_markets(self, scan_id: int) -> tuple[ScanMarket, ...]:
        """The Scan's Market set in volume order."""
        return tuple(ScanMarket(*row) for row in self._connection().execute(
            "SELECT seq, condition_id, volume, state FROM scan_market WHERE scan_id = ? ORDER BY seq", (scan_id,)
        ))

    def record_market_read(self, scan_id: int, seq: int, *, used: bool, terms: dict[str, float]) -> None:
        """One Market's read, in one transaction: its state and, when used, its pre-filter terms added to each
        candidate's running estimate (AD-9, AD-21). A Market already read is refused."""
        with self._write() as db:
            cursor = db.execute(
                "UPDATE scan_market SET state = ? WHERE scan_id = ? AND seq = ? AND state IS NULL",
                ("used" if used else "partial", scan_id, seq),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Market {seq} of Scan {scan_id} does not exist or is already read")
            db.executemany(
                "INSERT INTO scan_candidate (scan_id, wallet, estimate) VALUES (?, ?, ?)"
                " ON CONFLICT (scan_id, wallet) DO UPDATE SET estimate = estimate + excluded.estimate",
                ((scan_id, wallet, term) for wallet, term in terms.items()),
            )

    def scan_candidates(self, scan_id: int) -> dict[str, float]:
        """Every candidate's pre-filter estimate (AD-21)."""
        return dict(self._connection().execute(
            "SELECT wallet, estimate FROM scan_candidate WHERE scan_id = ?", (scan_id,)
        ).fetchall())

    def set_shortlist(self, scan_id: int, shortlist: Sequence[Candidate], *, candidate_count: int) -> None:
        """Store the 3 x N shortlist in estimate order and the candidate count; the Scan moves to `shortlisted`."""
        with self._write() as db:
            self._advance(db, scan_id, ScanStep.MARKETS, ScanStep.SHORTLISTED)
            db.execute("UPDATE scan SET candidate_count = ? WHERE scan_id = ?", (candidate_count, scan_id))
            db.executemany(
                "INSERT INTO scan_wallet (scan_id, seq, wallet, estimate) VALUES (?, ?, ?, ?)",
                ((scan_id, i, c.wallet, c.estimate) for i, c in enumerate(shortlist)),
            )

    def scan_wallets(self, scan_id: int) -> tuple[ScanWallet, ...]:
        """The Scan's shortlist in estimate order, with how each Wallet ranked so far."""
        return tuple(
            ScanWallet(seq, wallet, estimate, None if outcome is None else WalletOutcome(outcome), real_pnl,
                       bool(unread), before, after, bool(top))
            for seq, wallet, estimate, outcome, real_pnl, unread, before, after, top in self._connection().execute(
                "SELECT seq, wallet, estimate, outcome, real_pnl, not_fully_read, before_fetch_id, after_fetch_id, top"
                " FROM scan_wallet WHERE scan_id = ? ORDER BY seq",
                (scan_id,),
            )
        )

    def record_ranking(
        self,
        scan_id: int,
        wallet: str,
        *,
        outcome: WalletOutcome,
        real_pnl: float | None,
        not_fully_read: bool,
        fetch_id: int | None,
    ) -> None:
        """How one shortlisted Wallet's before part was read, frozen to its snapshot (AD-9, AD-19)."""
        with self._write() as db:
            cursor = db.execute(
                "UPDATE scan_wallet SET outcome = ?, real_pnl = ?, not_fully_read = ?, before_fetch_id = ?"
                " WHERE scan_id = ? AND wallet = ? AND outcome IS NULL",
                (outcome.value, real_pnl, int(not_fully_read), fetch_id, scan_id, wallet),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"{wallet} is not an unread Wallet of Scan {scan_id}")

    def mark_top(self, scan_id: int, wallets: Sequence[str]) -> None:
        """Mark the top N; the Scan moves to `ranked` (AD-21)."""
        with self._write() as db:
            self._advance(db, scan_id, ScanStep.SHORTLISTED, ScanStep.RANKED)
            db.executemany(
                "UPDATE scan_wallet SET top = 1 WHERE scan_id = ? AND wallet = ?", ((scan_id, w) for w in wallets)
            )

    def save_results(self, scan_id: int, wallet: str, *, after_fetch_id: int | None, results: Sequence[ScanResult]) -> None:
        """A top-N Wallet's frozen after part and its Skill Test results, in one transaction (AD-19, AD-22)."""
        with self._write() as db:
            scan = db.execute("SELECT cutoff, seed FROM scan WHERE scan_id = ?", (scan_id,)).fetchone()
            cursor = db.execute(
                "UPDATE scan_wallet SET after_fetch_id = ? WHERE scan_id = ? AND wallet = ? AND top = 1",
                (after_fetch_id, scan_id, wallet),
            )
            if scan is None or cursor.rowcount != 1:
                raise ValueError(f"{wallet} is not a top Wallet of Scan {scan_id}")
            db.executemany(
                "INSERT INTO scan_result (scan_id, wallet, scope, cutoff, seed, fetch_id, after_fetch_id, verdict,"
                " p_value, tested_count, real_pnl, not_fully_read) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (scan_id, wallet, r.scope, scan[0], scan[1], r.fetch_id, r.after_fetch_id, r.verdict, r.p_value,
                     r.tested_count, r.real_pnl, int(r.not_fully_read))
                    for r in results
                ),
            )

    def scan_results(self, scan_id: int) -> tuple[ScanResult, ...]:
        """Every stored result of the Scan, by Wallet and scope (AD-22)."""
        return tuple(
            ScanResult(wallet, scope, verdict, p_value, tested, real_pnl, bool(unread), before, after)
            for wallet, scope, verdict, p_value, tested, real_pnl, unread, before, after in self._connection().execute(
                "SELECT wallet, scope, verdict, p_value, tested_count, real_pnl, not_fully_read, fetch_id, after_fetch_id"
                " FROM scan_result WHERE scan_id = ? ORDER BY wallet, scope",
                (scan_id,),
            )
        )

    def tested_wallets(self, scan_id: int) -> set[str]:
        """The Wallets of the Scan whose results are stored."""
        return {w for (w,) in self._connection().execute(
            "SELECT DISTINCT wallet FROM scan_result WHERE scan_id = ?", (scan_id,)
        )}

    def finish_scan(self, scan_id: int, groups: Sequence[GroupResult]) -> None:
        """Every phase is done: the Scan's two Hold-up group results are stored and it moves to `done`, in one
        transaction, so a Scan finished from this version on always has both (AD-5, AD-22, FR-17). Only a Scan
        kept from a file older than version 7 is `done` without them."""
        if sorted(g.group for g in groups) != sorted(HOLDUP_GROUPS):
            raise ValueError("a Scan finishes with the Passers' and the Comparison Group's results, once each")
        with self._write() as db:
            scan = db.execute("SELECT cutoff, seed FROM scan WHERE scan_id = ?", (scan_id,)).fetchone()
            if scan is None:
                raise ValueError(f"no Scan {scan_id}")
            self._advance(db, scan_id, ScanStep.RANKED, ScanStep.DONE)  # first: a Scan at another step is refused
            db.executemany(
                "INSERT INTO group_result (scan_id, scope, group_name, cutoff, seed, verdict, p_value, tested_count,"
                " real_pnl, wallets, dropped, not_fully_read) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (scan_id, HOLDUP_AFTER, g.group, scan[0], scan[1], g.verdict.value, g.p_value, g.tested_count,
                     g.real_pnl, g.wallets, g.dropped, g.not_fully_read)
                    for g in groups
                ),
            )

    def group_results(self, scan_id: int, scope: str = HOLDUP_AFTER) -> tuple[GroupResult, ...]:
        """The Scan's stored group results of one scope (AD-22): the Passers' then the Comparison Group's, the
        order `core/holdup` gives them in; none for a Scan finished before they existed (Story 5.1)."""
        stored = {
            group: GroupResult(group, Verdict(verdict), p_value, tested, real_pnl, wallets, dropped, unread)
            for group, verdict, p_value, tested, real_pnl, wallets, dropped, unread in self._connection().execute(
                "SELECT group_name, verdict, p_value, tested_count, real_pnl, wallets, dropped, not_fully_read"
                " FROM group_result WHERE scan_id = ? AND scope = ?",
                (scan_id, scope),
            )
        }
        return tuple(stored[group] for group in HOLDUP_GROUPS if group in stored)

    # --- price history (AD-24, Story 6.1) -------------------------------------------------------

    def save_prices(
        self, token_id: str, windows: Sequence[tuple[int, int]], points: Sequence[PricePoint], route: str
    ) -> None:
        """Store one answered price request in one transaction: the windows it covered and the points in them.

        Every point must be of `token_id` and lie inside one of `windows`, so nothing outside the short
        windows is ever stored (AD-14). Each asked window keeps its own row with its route, so a later,
        wider request never relabels an earlier answer; the same window asked again replaces its row.
        Windows with no points are stored too: they were asked, and are never asked again (AD-4).
        """
        if route not in PRICE_ROUTES:
            raise ValueError(f"unknown price route {route!r}")
        if not windows or any(end < start for start, end in windows):
            raise ValueError("a price request covers at least one window, each ending at or after its start")
        ordered = sorted(windows)
        starts = [start for start, _ in ordered]
        reach = []  # the latest end among the windows up to each one, so overlapping windows are handled too
        for _, end in ordered:
            reach.append(end if not reach else max(reach[-1], end))
        for point in points:
            at = bisect_right(starts, point.t) - 1
            if point.token_id != token_id or at < 0 or point.t > reach[at]:
                raise ValueError(f"a price point of token {point.token_id} at {point.t} is outside the stored windows")
        now = self._now()
        with self._write() as db:
            db.executemany(
                "INSERT OR REPLACE INTO price_window (token_id, start_at, end_at, route, fetched_at) VALUES (?, ?, ?, ?, ?)",
                ((token_id, start, end, route, now) for start, end in windows),
            )
            db.executemany(
                "INSERT OR REPLACE INTO price_point (token_id, t, price) VALUES (?, ?, ?)",
                ((token_id, point.t, point.price) for point in points),
            )

    def price_windows(self, token_id: str) -> tuple[tuple[int, int], ...]:
        """The stored windows [start, end] of one token, oldest first: what need not be asked again (AD-4)."""
        return tuple(
            (start, end)
            for start, end in self._connection().execute(
                "SELECT start_at, end_at FROM price_window WHERE token_id = ? ORDER BY start_at, end_at", (token_id,)
            )
        )

    def prices(self, token_id: str, start: int | None = None, end: int | None = None) -> tuple[PricePoint, ...]:
        """The stored price points of one token, oldest first; with `start` and `end`, only those inside them."""
        low = -(2**62) if start is None else start
        high = 2**62 if end is None else end
        return tuple(
            PricePoint(token_id, t, price)
            for t, price in self._connection().execute(
                "SELECT t, price FROM price_point WHERE token_id = ? AND t BETWEEN ? AND ? ORDER BY t",
                (token_id, low, high),
            )
        )

    @staticmethod
    def _advance(db: sqlite3.Connection, scan_id: int, current: ScanStep, following: ScanStep) -> None:
        cursor = db.execute(
            "UPDATE scan SET step = ? WHERE scan_id = ? AND step = ?", (following.value, scan_id, current.value)
        )
        if cursor.rowcount != 1:
            raise ValueError(f"Scan {scan_id} is not at step {current}")

    @staticmethod
    def _open_scan_job(db: sqlite3.Connection) -> int | None:
        row = db.execute("SELECT id FROM job WHERE kind = ? AND status IN (?, ?) LIMIT 1", (SCAN, *_OPEN)).fetchone()
        return None if row is None else int(row[0])

    def _insert_scan_job(self, db: sqlite3.Connection, scan_id: int, *, phase: str, message: str) -> int:
        return int(db.execute(
            "INSERT INTO job (kind, scan_id, status, phase, done, total, message, created_at)"
            " VALUES (?, ?, ?, ?, 0, 0, ?, ?)",
            (SCAN, scan_id, JobStatus.QUEUED.value, phase, message, self._now()),
        ).lastrowid)

    def close(self) -> None:
        """Close every connection this store opened, in any thread. Call it at shutdown only."""
        with self._lock:
            for _, connection in self._connections:
                connection.close()
            self._connections.clear()
        self._local = threading.local()

    # --- connections and transactions (AD-6) --------------------------------------------------

    def _connection(self) -> sqlite3.Connection:
        connection = getattr(self._local, "connection", None)
        if connection is None:
            # isolation_level=None: transactions are opened explicitly below, never implicitly.
            # check_same_thread=False only so close() can close them all; each thread still uses its own.
            connection = sqlite3.connect(
                self.path, timeout=BUSY_TIMEOUT_SECONDS, isolation_level=None, check_same_thread=False
            )
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA foreign_keys = ON")
            self._local.connection = connection
            with self._lock:
                # Web servers start a thread per request: close the connections of threads that ended.
                for _, old in [entry for entry in self._connections if not entry[0].is_alive()]:
                    old.close()
                self._connections = [entry for entry in self._connections if entry[0].is_alive()]
                self._connections.append((threading.current_thread(), connection))
        return connection

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        db = self._connection()
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.execute("COMMIT")
        except BaseException:
            # A failed COMMIT, or an error SQLite already rolled back, must not leave the
            # connection inside a transaction or hide the first error.
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise

    def _prepare_schema(self) -> None:
        """Create the tables, or rebuild them when the file has another schema version (AD-6).

        The cache (lookup snapshots, Market records, lookup jobs) is dropped: a lookup or
        `load-sample` fetches it again. From version 6 on, the Scans are kept: the scan tables,
        scan jobs, every snapshot a Scan names with its rows, and those snapshots' and Market sets'
        Market records are copied into the new tables by the columns both versions share, and so
        are all stored prices (Story 6.1). When the
        snapshots cannot be copied (a new column with no default, say), the Scans are kept without
        them and marked `data_rebuilt`: they cannot resume (Story 4.3).
        """
        with self._write() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version == SCHEMA_VERSION:
                return
            db.execute("PRAGMA defer_foreign_keys = ON")  # drop in any order inside this transaction
            for (name,) in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL"
            ).fetchall():
                db.execute(f'DROP INDEX "{name}"')  # names from sqlite_master, so the new schema can reuse them
            tables = [name for (name,) in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()]
            keep = version >= FIRST_KEEPING_VERSION and set(KEPT_TABLES) - _ADDED_LATER <= set(tables)
            if keep:
                log.warning(
                    "Updating %s from database version %d to %d and keeping its Scans; a large file can take"
                    " a few minutes", self.path, version, SCHEMA_VERSION,
                )
            for name in tables:
                if keep and name in KEPT_TABLES:
                    db.execute(f'ALTER TABLE "{name}" RENAME TO "old_{name}"')
                else:
                    db.execute(f'DROP TABLE "{name}"')
            for statement in _statements(SCHEMA_FILE.read_text(encoding="utf-8")):
                db.execute(statement)
            if keep:
                _copy_scans(db)
                _carry_sequences(db)
                for name in KEPT_TABLES:
                    db.execute(f'DROP TABLE IF EXISTS "old_{name}"')
            db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @staticmethod
    def _next_seq(db: sqlite3.Connection, table: str, fetch_id: int) -> int:
        finished = db.execute(
            "SELECT completed_at IS NOT NULL FROM snapshot WHERE fetch_id = ?", (fetch_id,)
        ).fetchone()
        if finished is None or finished[0]:
            raise ValueError(f"snapshot {fetch_id} does not exist or is already finished")
        # `table` is one of two fixed names above, never user input.
        return int(db.execute(f"SELECT COALESCE(MAX(seq), -1) + 1 FROM {table} WHERE fetch_id = ?",
                              (fetch_id,)).fetchone()[0])

    def now(self) -> int:
        """The store's clock in epoch seconds: the time it writes into rows."""
        return int(self._clock())

    def _now(self) -> int:
        return self.now()


def _check_key(cutoff: int | None, side: str | None) -> None:
    """A snapshot's part: a Cut-off Date and its side together, or neither (a lookup's window)."""
    if (cutoff is None) != (side is None):
        raise ValueError("a Cut-off Date and its side come together, or not at all")
    if side is not None and side not in (BEFORE, AFTER):
        raise ValueError(f"side must be 'before' or 'after', not {side!r}")


def _read_snapshot(db: sqlite3.Connection, fetch_id: int) -> Snapshot | None:
    """One complete snapshot with its rows and Markets, read inside the caller's transaction."""
    head = db.execute(
        "SELECT wallet, completed_at, window_limit, activity_read_until, window_capped, cutoff, side FROM snapshot"
        " WHERE fetch_id = ? AND completed_at IS NOT NULL",
        (fetch_id,),
    ).fetchone()
    if head is None:
        return None
    wallet, completed_at, window_limit, activity_read_until, window_capped, cutoff, side = head
    positions = tuple(
        ListedPosition(*row)
        for row in db.execute(
            "SELECT condition_id, token_id, status, shares_bought, first_entry_at, last_event_at FROM listed_position"
            " WHERE fetch_id = ? ORDER BY seq",
            (fetch_id,),
        )
    )
    activity = tuple(
        ActivityRow(*row)
        for row in db.execute(
            "SELECT type, condition_id, timestamp, size, usdc_size, price, token_id, side FROM activity_row"
            " WHERE fetch_id = ? ORDER BY seq",
            (fetch_id,),
        )
    )
    markets = tuple(
        _market(row)
        for row in db.execute(
            f"SELECT {_MARKET_COLUMNS} FROM market"
            " WHERE condition_id IN (SELECT condition_id FROM listed_position WHERE fetch_id = ?"
            " UNION SELECT condition_id FROM activity_row WHERE fetch_id = ?) ORDER BY condition_id",
            (fetch_id, fetch_id),
        )
    )
    return Snapshot(
        fetch_id, wallet, completed_at, positions, activity, markets, window_limit, activity_read_until,
        bool(window_capped), cutoff, side,
    )


def _copy_scans(db: sqlite3.Connection) -> None:
    """AD-6: copy the Scans from the renamed `old_*` tables into the new ones, by shared columns.

    The scan tables, scan jobs and stored prices must copy (a failure is a schema change that needs
    its own migration, so it is raised). The frozen snapshots, their rows and their Market records copy
    inside a savepoint; if the new schema does not take them (a constraint fails) they are dropped and
    every Scan is marked `data_rebuilt`. Any other failure there, a full disk for one, is raised instead:
    the whole change is then rolled back and the file stays as it was, Scans and snapshots included
    (Story 6.1 review: a 1 GB copy must never lose a live Scan's data over a disk error).
    """
    frozen = _FROZEN_IDS  # the scan tables are already copied
    for name in _SCAN_TABLES:
        _copy(db, name)
    _copy(db, "job", "WHERE scan_id IS NOT NULL")
    for name in _PRICE_TABLES:
        _copy(db, name)
    db.execute("SAVEPOINT snapshots")
    try:
        _copy(db, "snapshot", f"WHERE fetch_id IN ({frozen}) AND completed_at IS NOT NULL")
        _copy(db, "listed_position", "WHERE fetch_id IN (SELECT fetch_id FROM snapshot)")
        _copy(db, "activity_row", "WHERE fetch_id IN (SELECT fetch_id FROM snapshot)")
        _copy(db, "market", (
            "WHERE condition_id IN (SELECT condition_id FROM listed_position UNION SELECT condition_id FROM activity_row"
            " UNION SELECT condition_id FROM scan_market)"
            " OR neg_risk_id IN (SELECT condition_id FROM activity_row WHERE type = 'CONVERSION')"
        ))
    except sqlite3.IntegrityError:
        db.execute("ROLLBACK TO snapshots")
        db.execute("UPDATE scan SET data_rebuilt = 1")
    db.execute("RELEASE snapshots")


def _carry_sequences(db: sqlite3.Connection) -> None:
    """Give each kept AUTOINCREMENT table (scan, job, snapshot) at least its old next id, so a new row never takes
    the id of a dropped one: a rebuilt Scan's stale `fetch_id` must not name another Wallet's new snapshot, nor an
    old job id a new job (review, Story 4.3)."""
    for (old_name, seq) in db.execute("SELECT name, seq FROM sqlite_sequence WHERE name LIKE 'old\\_%' ESCAPE '\\'").fetchall():
        name = old_name.removeprefix("old_")
        if db.execute("SELECT 1 FROM sqlite_sequence WHERE name = ?", (name,)).fetchone() is None:
            db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (name, seq))
        else:
            db.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = ?", (seq, name))


def _copy(db: sqlite3.Connection, name: str, where: str = "") -> None:
    """Copy `old_<name>` into `<name>` by the columns both have; `where` filters the old rows (fixed text).

    A table the old file did not have yet (`_ADDED_LATER`) has nothing to copy."""
    new = [row[1] for row in db.execute(f'PRAGMA table_info("{name}")')]
    old = {row[1] for row in db.execute(f'PRAGMA table_info("old_{name}")')}
    if not old and name in _ADDED_LATER:
        return
    columns = ", ".join(f'"{c}"' for c in new if c in old)
    db.execute(f'INSERT INTO "{name}" ({columns}) SELECT {columns} FROM "old_{name}" {where}')


def _statements(script: str) -> Iterator[str]:
    """Split schema.sql into single statements (`executescript` would commit the open transaction)."""
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            yield buffer.strip()
            buffer = ""


_JOB_COLUMNS = "id, kind, wallet, status, phase, done, total, message, result, created_at, finished_at, scan_id"


def _job(row: tuple) -> Job:
    return Job(row[0], row[1], row[2], JobStatus(row[3]), *row[4:])


_MARKET_COLUMNS = (
    "condition_id, closed, closed_time, token_ids, outcome_prices, fees_enabled, start_time, fee_rate,"
    " fee_exponent, tags, event_id, neg_risk_id"
)


def _market(row: tuple) -> Market:
    (condition_id, closed, closed_time, token_ids, outcome_prices, fees_enabled, start, rate, exponent, tags,
     event, neg) = row
    return Market(
        condition_id=condition_id,
        closed=bool(closed),
        closed_time=closed_time,
        token_ids=tuple(json.loads(token_ids)),
        outcome_prices=tuple(float(p) for p in json.loads(outcome_prices)),
        fees_enabled=bool(fees_enabled),
        start_time=start,
        fee_rate=rate,
        fee_exponent=exponent,
        tags=tuple(json.loads(tags)),
        event_id=event,
        neg_risk_id=neg,
    )
