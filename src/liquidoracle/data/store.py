"""The SQLite store: the only module that runs SQL (AD-6).

Plain `sqlite3`, WAL mode, a busy timeout, foreign keys on, one connection per thread, and every
write transaction opened with `BEGIN IMMEDIATE` and kept short. The schema is `schema.sql`, and
its version is `PRAGMA user_version`.

A Wallet is written as a snapshot (AD-19): `begin_snapshot` gives a `fetch_id`, rows are added
under it, and `finish_snapshot` makes it visible in one final step, deleting that Wallet's older
snapshots in the same transaction (Edvard, 2026-11-19, Story 1.6). Readers see only complete
snapshots. `wallet_lock` lets one fetch of a Wallet run at a time, across every thread that
shares this Store (AD-19). `serving_snapshot` is the one answer to "which snapshot serves this
window" (AD-4). Jobs (AD-5, Story 2.5) are rows the worker claims with one atomic update.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from liquidoracle.records import ActivityRow, ListedPosition, Market, unread_positions

SCHEMA_VERSION = 4  # 2: the Wallet window (Story 2.2); 3: Market events (Story 2.4); 4: jobs (Story 2.5)
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

    `activity_read_until` is None when the activity read was complete (AD-7).
    """

    fetch_id: int
    wallet: str
    completed_at: int
    positions: tuple[ListedPosition, ...]
    activity: tuple[ActivityRow, ...]
    markets: tuple[Market, ...]
    window_limit: int
    activity_read_until: int | None

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


LOOKUP = "lookup"  # the one job kind so far; Scan jobs come with Epic 4
NO_HISTORY = "no_history"  # a finished lookup's result when Polymarket has no positions for the address
_OPEN = (JobStatus.QUEUED.value, JobStatus.RUNNING.value)


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

    def begin_snapshot(self, wallet: str, *, window_limit: int) -> int:
        """Start a snapshot of `wallet`'s window; it stays invisible until `finish_snapshot`."""
        with self._write() as db:
            cursor = db.execute(
                "INSERT INTO snapshot (wallet, window_limit, started_at) VALUES (?, ?, ?)",
                (wallet, window_limit, self._now()),
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

    def finish_snapshot(self, fetch_id: int, *, activity_read_until: int | None = None) -> None:
        """Make the snapshot visible and delete the Wallet's older snapshots, in one transaction.

        `activity_read_until` is the time of the last activity row read when the read was capped
        or cut short (AD-7), None when it was complete. Refused when the snapshot is unknown or
        already finished, or when one of its rows names a Market that is not stored, so a visible
        snapshot is always complete. A CONVERSION row names its negative-risk event instead, which
        must be the `neg_risk_id` of a stored Market (AD-11, Story 2.4).
        """
        with self._write() as db:
            row = db.execute(
                "SELECT wallet FROM snapshot WHERE fetch_id = ? AND completed_at IS NULL", (fetch_id,)
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
                "UPDATE snapshot SET completed_at = ?, activity_read_until = ? WHERE fetch_id = ?",
                (self._now(), activity_read_until, fetch_id),
            )
            # Older snapshots of this Wallet, finished or abandoned, go; their rows follow (ON DELETE CASCADE).
            # Epic 4 keeps any snapshot a Scan refers to (AD-6, AD-19).
            db.execute("DELETE FROM snapshot WHERE wallet = ? AND fetch_id < ?", (row[0], fetch_id))

    # --- reading ------------------------------------------------------------------------------

    def latest_snapshot(self, wallet: str) -> Snapshot | None:
        """The Wallet's newest complete snapshot, or None. Half-written snapshots are never returned."""
        return self.serving_snapshot(wallet)

    def serving_snapshot(
        self, wallet: str, *, window_limit: int | None = None, max_age: float | None = None
    ) -> Snapshot | None:
        """AD-4: the one snapshot that serves this window, or None.

        The Wallet's newest complete snapshot whose own window is `window_limit` (any, when None)
        and that was completed less than `max_age` seconds ago (any age, when None). Rows are never
        merged across snapshots: a snapshot serves the whole window or nothing.
        """
        where = "wallet = ? AND completed_at IS NOT NULL"
        args: list[object] = [wallet]
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
                "SELECT fetch_id, completed_at, window_limit, activity_read_until FROM snapshot"
                f" WHERE {where} ORDER BY fetch_id DESC LIMIT 1",  # `where` is fixed text built above
                args,
            ).fetchone()
            if head is None:
                return None
            fetch_id, completed_at, window_limit, activity_read_until = head
            positions = tuple(
                ListedPosition(*row)
                for row in db.execute(
                    "SELECT condition_id, token_id, status, shares_bought, first_entry_at, last_event_at"
                    " FROM listed_position"
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
                fetch_id, wallet, completed_at, positions, activity, markets, window_limit, activity_read_until
            )
        finally:
            if db.in_transaction:
                db.execute("COMMIT")

    def has_snapshot(self, wallet: str) -> bool:
        """True when the Wallet has a complete snapshot (Story 1.7's Lookup page), without reading its rows."""
        row = self._connection().execute(
            "SELECT 1 FROM snapshot WHERE wallet = ? AND completed_at IS NOT NULL LIMIT 1", (wallet,)
        ).fetchone()
        return row is not None

    def snapshot_time(self, wallet: str, *, window_limit: int) -> int | None:
        """When the Wallet's newest complete snapshot of this window was completed, or None (AD-4's outage offer)."""
        row = self._connection().execute(
            "SELECT MAX(completed_at) FROM snapshot WHERE wallet = ? AND window_limit = ? AND completed_at IS NOT NULL",
            (wallet, window_limit),
        ).fetchone()
        return None if row[0] is None else int(row[0])

    def wallet_count(self) -> int:
        """How many Wallets have a complete snapshot."""
        row = self._connection().execute(
            "SELECT COUNT(DISTINCT wallet) FROM snapshot WHERE completed_at IS NOT NULL"
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

    def finish_job(self, job_id: int, status: JobStatus, *, message: str, result: str | None = None) -> None:
        """End a running job: its final status, progress complete, and an optional result."""
        if status in (JobStatus.QUEUED, JobStatus.RUNNING):
            raise ValueError(f"a job cannot finish as {status}")
        with self._write() as db:
            db.execute(
                "UPDATE job SET status = ?, result = ?, message = ?, done = total, finished_at = ? WHERE id = ?",
                (status.value, result, message, self._now(), job_id),
            )

    def interrupt_running_jobs(self) -> int:
        """AD-5: at startup, every job left `running` becomes `interrupted`. Returns how many."""
        with self._write() as db:
            cursor = db.execute(
                "UPDATE job SET status = ?, finished_at = ? WHERE status = ?",
                (JobStatus.INTERRUPTED.value, self._now(), JobStatus.RUNNING.value),
            )
            return cursor.rowcount

    def job(self, job_id: int) -> Job | None:
        """One job row, or None when there is no such job."""
        row = self._connection().execute(
            "SELECT id, kind, wallet, status, phase, done, total, message, result, created_at, finished_at"
            " FROM job WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return Job(row[0], row[1], row[2], JobStatus(row[3]), *row[4:])

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

        Every table so far holds fetched data that `load-sample` or a lookup can fetch again, or
        jobs, which a rebuild simply forgets.
        """
        with self._write() as db:
            if db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION:
                return
            db.execute("PRAGMA defer_foreign_keys = ON")  # drop in any order inside this transaction
            tables = [name for (name,) in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )]
            for name in tables:
                db.execute(f'DROP TABLE "{name}"')
            for statement in _statements(SCHEMA_FILE.read_text(encoding="utf-8")):
                db.execute(statement)
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

    def _now(self) -> int:
        return int(self._clock())


def _statements(script: str) -> Iterator[str]:
    """Split schema.sql into single statements (`executescript` would commit the open transaction)."""
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            yield buffer.strip()
            buffer = ""


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
