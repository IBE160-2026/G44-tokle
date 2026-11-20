"""The SQLite store (AD-6) and Wallet snapshots (AD-19). Every test uses its own database file."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from liquidoracle.data import store as store_module
from liquidoracle.data import synthetic
from liquidoracle.data.store import SCHEMA_VERSION, Store
from liquidoracle.records import ActivityRow, ListedPosition, Market

WALLET = "0x" + "ab" * 20
MARKET = Market("0xm1", closed=True, closed_time=1_700_000_000, token_ids=("11", "22"),
                outcome_prices=(1.0, 0.0), fees_enabled=True, start_time=1_698_000_000, fee_rate=0.04,
                fee_exponent=1.0, tags=("Politics", "Elections"))
FILL = ActivityRow("TRADE", "0xm1", 1_699_000_000, 10.0, 4.37, 0.43, token_id="11", side="BUY")
LISTED = ListedPosition("0xm1", "11", "CLOSED", 10.0, 1_699_000_000, 1_700_050_000)
LIMIT = 2_000


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    db = Store(tmp_path / "instance" / "test.db", clock=lambda: 1_800_000_000.0)
    yield db
    db.close()


def write(db: Store, wallet: str = WALLET, *, fills: tuple[ActivityRow, ...] = (FILL,), finish: bool = True) -> int:
    fetch_id = db.begin_snapshot(wallet, window_limit=LIMIT)
    db.add_positions(fetch_id, (LISTED,))
    db.add_activity(fetch_id, fills)
    db.save_markets((MARKET,))
    if finish:
        db.finish_snapshot(fetch_id)
    return fetch_id


def raw(db: Store, sql: str) -> list[tuple]:
    return db._connection().execute(sql).fetchall()


def test_connection_uses_wal_busy_timeout_and_foreign_keys(store: Store) -> None:
    """AD-6, NFR-4: WAL mode, a busy timeout and foreign keys on every connection."""
    assert raw(store, "PRAGMA journal_mode") == [("wal",)]
    assert raw(store, "PRAGMA busy_timeout") == [(int(store_module.BUSY_TIMEOUT_SECONDS * 1000),)]
    assert raw(store, "PRAGMA foreign_keys") == [(1,)]


def test_new_file_gets_the_schema_and_its_version(store: Store) -> None:
    """AD-6: schema.sql creates the four fetched-data tables, and user_version records the schema."""
    tables = {name for (name,) in raw(store, "SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables - {"sqlite_sequence"} == {"snapshot", "listed_position", "activity_row", "market"}
    assert raw(store, "PRAGMA user_version") == [(SCHEMA_VERSION,)]


@pytest.mark.parametrize("old_version", [0, 99])
def test_another_schema_version_is_rebuilt(tmp_path: Path, old_version: int) -> None:
    """AD-6: a file with another user_version gets the current tables; its fetched data is dropped."""
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as old:
        old.execute("CREATE TABLE leftover (x)")
        old.execute("CREATE TABLE snapshot (fetch_id INTEGER PRIMARY KEY, wallet TEXT)")
        old.execute("CREATE TABLE child (fetch_id REFERENCES snapshot (fetch_id))")
        old.execute("INSERT INTO snapshot VALUES (1, 'w')")
        old.execute("INSERT INTO child VALUES (1)")
        old.execute(f"PRAGMA user_version = {old_version}")
    old.close()
    db = Store(path)
    try:
        assert raw(db, "PRAGMA user_version") == [(SCHEMA_VERSION,)]
        tables = {name for (name,) in raw(db, "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "leftover" not in tables and "child" not in tables and "market" in tables
        assert db.latest_snapshot("w") is None
    finally:
        db.close()


def test_reopening_the_same_version_keeps_the_data(tmp_path: Path) -> None:
    """AD-6: a file already at the current version is left as it is."""
    first = Store(tmp_path / "keep.db")
    write(first)
    first.close()
    second = Store(tmp_path / "keep.db")
    try:
        assert second.latest_snapshot(WALLET) is not None
    finally:
        second.close()


def test_snapshot_round_trips_its_records_exactly(store: Store) -> None:
    """AD-19, AD-2: what is written comes back as the same records, in the same order."""
    fills = (FILL, ActivityRow("REDEEM", "0xm1", 1_700_100_000, 10.0, 10.0, 1.0))
    fetch_id = write(store, fills=fills)
    snapshot = store.latest_snapshot(WALLET)
    assert snapshot is not None
    assert (snapshot.fetch_id, snapshot.wallet, snapshot.completed_at) == (fetch_id, WALLET, 1_800_000_000)
    assert snapshot.positions == (LISTED,)
    assert snapshot.activity == fills
    assert snapshot.markets == (MARKET,)
    assert (snapshot.window_limit, snapshot.activity_read_until) == (LIMIT, None)


def test_identical_rows_stay_separate_fills(store: Store) -> None:
    """AD-19: two identical-looking activity rows are two fills, never de-duplicated."""
    write(store, fills=(FILL, FILL, FILL))
    snapshot = store.latest_snapshot(WALLET)
    assert snapshot is not None and snapshot.activity == (FILL, FILL, FILL)


def test_rows_added_in_pages_keep_their_order(store: Store) -> None:
    """AD-19: a fetch may add rows in several steps; they come back in the order added."""
    second = ActivityRow("TRADE", "0xm1", 1_699_000_100, 5.0, 2.0, 0.4, token_id="11", side="SELL")
    fetch_id = store.begin_snapshot(WALLET, window_limit=LIMIT)
    store.add_activity(fetch_id, (FILL,))
    store.add_activity(fetch_id, (second,))
    store.add_positions(fetch_id, (LISTED,))
    store.save_markets((MARKET,))
    store.finish_snapshot(fetch_id)
    snapshot = store.latest_snapshot(WALLET)
    assert snapshot is not None and snapshot.activity == (FILL, second)


def test_half_written_snapshot_is_never_read(store: Store) -> None:
    """AD-19: readers see only complete snapshots; a begun one stays invisible."""
    write(store, finish=False)
    assert store.latest_snapshot(WALLET) is None
    complete = write(store)
    write(store, fills=(FILL, FILL), finish=False)
    snapshot = store.latest_snapshot(WALLET)
    assert snapshot is not None and snapshot.fetch_id == complete and snapshot.activity == (FILL,)


def test_finishing_deletes_older_snapshots_of_that_wallet_only(store: Store) -> None:
    """AD-19 (Edvard, 2026-11-19): a new snapshot replaces the Wallet's older ones; other Wallets stay."""
    other = "0x" + "cd" * 20
    write(store, other)
    write(store, finish=False)  # abandoned
    write(store)
    newest = write(store, fills=(FILL, FILL))
    assert raw(store, f"SELECT fetch_id FROM snapshot WHERE wallet = '{WALLET}'") == [(newest,)]
    assert raw(store, f"SELECT COUNT(*) FROM activity_row WHERE fetch_id <> {newest}") == [(1,)]  # the other's
    assert store.latest_snapshot(other) is not None
    assert store.wallet_count() == 2


def test_finished_snapshot_cannot_change(store: Store) -> None:
    """AD-19: rows cannot be added to a finished snapshot, and it cannot be finished twice."""
    fetch_id = write(store)
    with pytest.raises(ValueError, match="already finished"):
        store.add_activity(fetch_id, (FILL,))
    with pytest.raises(ValueError, match="already finished"):
        store.finish_snapshot(fetch_id)
    with pytest.raises(ValueError, match="does not exist"):
        store.add_positions(9999, (LISTED,))


def test_snapshot_naming_an_unstored_market_cannot_finish(store: Store) -> None:
    """AD-19: a snapshot whose rows name a Market that is not stored is incomplete and stays invisible."""
    fetch_id = store.begin_snapshot(WALLET, window_limit=LIMIT)
    store.add_activity(fetch_id, (FILL,))
    with pytest.raises(ValueError, match="0xm1"):
        store.finish_snapshot(fetch_id)
    assert store.latest_snapshot(WALLET) is None


def test_a_failed_write_is_rolled_back(store: Store) -> None:
    """AD-6: a write that fails part-way leaves nothing behind."""
    fetch_id = store.begin_snapshot(WALLET, window_limit=LIMIT)
    bad = ActivityRow("TRADE", "0xm1", 1, 1.0, 1.0, 1.0, token_id="11", side="BUY")
    with pytest.raises(sqlite3.Error):
        store.add_activity(fetch_id, (bad, ActivityRow(None, "0xm1", 1, 1.0, 1.0, 1.0)))  # type: ignore[arg-type]
    assert raw(store, "SELECT COUNT(*) FROM activity_row") == [(0,)]


def test_each_thread_gets_its_own_connection_and_writes_do_not_collide(store: Store) -> None:
    """AD-6, NFR-4: one connection per thread; parallel snapshot writes all succeed (BEGIN IMMEDIATE + timeout)."""
    connections: list[sqlite3.Connection] = []
    errors: list[BaseException] = []

    def work(i: int) -> None:
        try:
            connections.append(store._connection())
            for _ in range(5):
                write(store, "0x" + f"{i:02d}" * 20)
        except BaseException as error:  # pragma: no cover - reported below
            errors.append(error)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len({id(c) for c in connections}) == 4
    assert store.wallet_count() == 4


def test_every_write_opens_begin_immediate() -> None:
    """AD-6: every write method goes through the one `_write` transaction, which starts BEGIN IMMEDIATE."""
    source = Path(store_module.__file__).read_text(encoding="utf-8")
    assert source.count('db.execute("BEGIN IMMEDIATE")') == 1
    for method in ("begin_snapshot", "add_positions", "add_activity", "save_markets", "finish_snapshot"):
        body = source.split(f"def {method}(", 1)[1].split("\n    def ", 1)[0]
        assert "with self._write() as db:" in body, method


def test_a_synthetic_wallet_round_trips_through_the_store(store: Store) -> None:
    """AD-14, AD-19: a generated Wallet's lists come back from the store unchanged."""
    wallet = synthetic.small_wallets()[-1]  # the stop-loss trader: buys and sells
    fetch_id = store.begin_snapshot(wallet.address, window_limit=LIMIT)
    store.add_positions(fetch_id, wallet.positions)
    store.add_activity(fetch_id, wallet.activity)
    store.save_markets(wallet.markets)
    store.finish_snapshot(fetch_id)
    snapshot = store.latest_snapshot(wallet.address)
    assert snapshot is not None
    assert snapshot.positions == wallet.positions
    assert snapshot.activity == wallet.activity
    assert sorted(snapshot.markets, key=lambda m: m.condition_id) == sorted(wallet.markets, key=lambda m: m.condition_id)


def test_a_write_takes_the_write_lock_before_its_first_read(store: Store) -> None:
    """AD-6: `_write` opens BEGIN IMMEDIATE, so another writer is shut out from the start, not mid-way."""
    other = sqlite3.connect(store.path, timeout=0, isolation_level=None)
    try:
        with store._write():
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                other.execute("BEGIN IMMEDIATE")
        other.execute("BEGIN IMMEDIATE")  # free again once the write has committed
        other.execute("ROLLBACK")
    finally:
        other.close()


def test_a_write_waits_for_another_writer_instead_of_failing(store: Store) -> None:
    """AD-6, NFR-4: while another connection holds the write lock, a write waits (busy timeout) and then succeeds."""
    other = sqlite3.connect(store.path, isolation_level=None)
    other.execute("BEGIN IMMEDIATE")
    done: list[int] = []
    writer = threading.Thread(target=lambda: done.append(store.begin_snapshot(WALLET, window_limit=LIMIT)))
    writer.start()
    writer.join(timeout=0.3)
    assert done == [] and writer.is_alive()  # still waiting for the lock
    other.execute("COMMIT")
    other.close()
    writer.join(timeout=5)
    assert len(done) == 1


def test_a_failed_commit_leaves_the_connection_usable(store: Store) -> None:
    """AD-6: when COMMIT itself fails, the transaction is rolled back and the next write works."""
    with pytest.raises(sqlite3.IntegrityError):
        with store._write() as db:
            db.execute("PRAGMA defer_foreign_keys = ON")  # the orphan row below fails at COMMIT, not at INSERT
            db.execute("INSERT INTO listed_position VALUES (999, 0, 'c', 't', 'OPEN', 1.0, 1, 1)")
    assert not store._connection().in_transaction
    assert raw(store, "SELECT COUNT(*) FROM listed_position") == [(0,)]
    write(store)
    assert store.latest_snapshot(WALLET) is not None


def test_connections_of_ended_threads_are_closed(store: Store) -> None:
    """AD-6: one connection per thread, and a thread-per-request server does not pile them up."""
    store._connection()  # this thread's own connection
    for _ in range(5):
        thread = threading.Thread(target=store._connection)
        thread.start()
        thread.join()
    # Each new thread's first use closes the connections of threads that ended before it, so only
    # this thread's and the last thread's remain: 2, not 6.
    assert len(store._connections) == 2
    assert all(thread.is_alive() for thread, _ in store._connections[:1])


def test_a_capped_read_is_stored_and_names_its_unread_positions(store: Store) -> None:
    """AD-7, AD-11: the snapshot keeps where a capped activity read stopped; Positions resolved later are unread."""
    later = Market("0xm2", closed=True, closed_time=1_700_200_000, token_ids=("33", "44"), outcome_prices=(0.0, 1.0))
    listed_later = ListedPosition("0xm2", "33", "OPEN", 5.0, 1_699_500_000, 1_699_500_000)
    fetch_id = store.begin_snapshot(WALLET, window_limit=LIMIT)
    store.add_positions(fetch_id, (LISTED, listed_later))
    store.add_activity(fetch_id, (FILL,))
    store.save_markets((MARKET, later))
    store.finish_snapshot(fetch_id, activity_read_until=1_700_000_001)
    snapshot = store.latest_snapshot(WALLET)
    assert snapshot is not None and snapshot.activity_read_until == 1_700_000_001
    assert snapshot.not_fully_read() == (listed_later,)  # MARKET resolved a second before the last row: read


def test_a_market_resolved_in_the_cap_second_is_not_fully_read(store: Store) -> None:
    """AD-7 (review, Story 2.2): a cap can cut inside a second, so a Market resolved in the last row's
    second counts as not fully read."""
    fetch_id = store.begin_snapshot(WALLET, window_limit=LIMIT)
    store.add_positions(fetch_id, (LISTED,))
    store.add_activity(fetch_id, (FILL,))
    store.save_markets((MARKET,))
    store.finish_snapshot(fetch_id, activity_read_until=MARKET.closed_time)
    snapshot = store.latest_snapshot(WALLET)
    assert snapshot is not None and snapshot.not_fully_read() == (LISTED,)


def test_only_resolved_markets_are_served_from_the_store(store: Store) -> None:
    """AD-4: stored resolved Markets never expire; open or unclear ones are fetched again."""
    open_market = Market("0xopen", closed=False, closed_time=None, token_ids=("1", "2"), outcome_prices=(0.4, 0.6))
    unclear = Market("0xhalf", closed=True, closed_time=1_700_000_000, token_ids=("3", "4"), outcome_prices=(0.5, 0.5))
    store.save_markets((MARKET, open_market, unclear))
    assert store.resolved_markets(["0xm1", "0xopen", "0xhalf", "0xnever"]) == {"0xm1": MARKET}
    many = [f"0x{i:04x}" for i in range(1_200)] + ["0xm1"]  # more ids than one statement takes
    assert store.resolved_markets(many) == {"0xm1": MARKET}


def test_the_wallet_lock_lets_one_fetch_of_a_wallet_run_at_a_time(store: Store) -> None:
    """AD-19: a second fetch of the same Wallet waits for the first; another Wallet does not wait."""
    inside = threading.Event()
    release = threading.Event()
    order: list[str] = []

    def first() -> None:
        with store.wallet_lock(WALLET):
            order.append("first in")
            inside.set()
            release.wait(5)
            order.append("first out")

    def second() -> None:
        with store.wallet_lock(WALLET):
            order.append("second in")

    one = threading.Thread(target=first)
    one.start()
    assert inside.wait(5)
    two = threading.Thread(target=second)
    two.start()
    two.join(timeout=0.2)
    assert two.is_alive()  # waiting for the first fetch
    with store.wallet_lock("0x" + "cd" * 20):  # another Wallet is not held up
        order.append("other")
    release.set()
    one.join(5)
    two.join(5)
    assert order == ["first in", "other", "first out", "second in"]


EPIC_1_SCHEMA = """
CREATE TABLE snapshot (fetch_id INTEGER PRIMARY KEY AUTOINCREMENT, wallet TEXT NOT NULL,
    started_at INTEGER NOT NULL, completed_at INTEGER);
CREATE TABLE listed_position (fetch_id INTEGER NOT NULL REFERENCES snapshot (fetch_id) ON DELETE CASCADE,
    seq INTEGER NOT NULL, condition_id TEXT NOT NULL, token_id TEXT NOT NULL, status TEXT NOT NULL,
    shares_bought REAL NOT NULL, first_entry_at INTEGER NOT NULL, PRIMARY KEY (fetch_id, seq));
CREATE TABLE market (condition_id TEXT PRIMARY KEY, closed INTEGER NOT NULL, closed_time INTEGER,
    token_ids TEXT NOT NULL, outcome_prices TEXT NOT NULL, fees_enabled INTEGER NOT NULL, fetched_at INTEGER NOT NULL);
INSERT INTO snapshot VALUES (1, 'w', 1, 2);
INSERT INTO market VALUES ('0xold', 1, 1, '["1","2"]', '[1.0,0.0]', 0, 1);
PRAGMA user_version = 1;
"""


def test_an_epic_1_database_is_rebuilt_and_takes_a_window_snapshot(tmp_path: Path) -> None:
    """AD-6 (review, Story 2.2): a database from Epic 1 (schema version 1) gets the new tables, keeps none of
    its fetched rows, and a window snapshot can be written and read back."""
    path = tmp_path / "epic1.db"
    with sqlite3.connect(path) as old:
        old.executescript(EPIC_1_SCHEMA)
    old.close()
    db = Store(path)
    try:
        assert raw(db, "PRAGMA user_version") == [(SCHEMA_VERSION,)] and SCHEMA_VERSION == 2
        assert db.latest_snapshot("w") is None and db.resolved_markets(["0xold"]) == {}
        write(db)
        snapshot = db.latest_snapshot(WALLET)
        assert snapshot is not None and snapshot.positions == (LISTED,) and snapshot.markets == (MARKET,)
    finally:
        db.close()
