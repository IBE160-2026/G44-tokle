-- The SQLite schema (AD-6). `data/store.py` runs it and sets PRAGMA user_version to
-- store.SCHEMA_VERSION. Epic 1 holds fetched data only, so a version mismatch rebuilds it.
-- Later stories add their tables here and raise the version.

-- One fetch of one Wallet (AD-19). Readers see it only once completed_at is set.
CREATE TABLE snapshot (
    fetch_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet       TEXT    NOT NULL,
    started_at   INTEGER NOT NULL,
    completed_at INTEGER
);
CREATE INDEX snapshot_by_wallet ON snapshot (wallet, completed_at);

-- A Wallet's positions-list rows (AD-10), in the order the client returned them.
CREATE TABLE listed_position (
    fetch_id       INTEGER NOT NULL REFERENCES snapshot (fetch_id) ON DELETE CASCADE,
    seq            INTEGER NOT NULL,
    condition_id   TEXT    NOT NULL,
    token_id       TEXT    NOT NULL,
    status         TEXT    NOT NULL,
    shares_bought  REAL    NOT NULL,
    first_entry_at INTEGER NOT NULL,
    PRIMARY KEY (fetch_id, seq)
);

-- A Wallet's activity rows (AD-10). Identical-looking rows are separate fills; `seq` keeps them.
CREATE TABLE activity_row (
    fetch_id     INTEGER NOT NULL REFERENCES snapshot (fetch_id) ON DELETE CASCADE,
    seq          INTEGER NOT NULL,
    type         TEXT    NOT NULL,
    condition_id TEXT    NOT NULL,
    timestamp    INTEGER NOT NULL,
    size         REAL    NOT NULL,
    usdc_size    REAL    NOT NULL,
    price        REAL    NOT NULL,
    token_id     TEXT,
    side         TEXT,
    PRIMARY KEY (fetch_id, seq)
);

-- Gamma Market records, one per Market, shared by every snapshot (AD-4).
-- token_ids and outcome_prices are JSON arrays, aligned by position.
CREATE TABLE market (
    condition_id   TEXT    PRIMARY KEY,
    closed         INTEGER NOT NULL,
    closed_time    INTEGER,
    token_ids      TEXT    NOT NULL,
    outcome_prices TEXT    NOT NULL,
    fees_enabled   INTEGER NOT NULL,
    fetched_at     INTEGER NOT NULL
);
