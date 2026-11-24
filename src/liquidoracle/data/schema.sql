-- The SQLite schema (AD-6). `data/store.py` runs it and sets PRAGMA user_version to
-- store.SCHEMA_VERSION. Every table so far holds fetched data or short-lived jobs, so a version mismatch rebuilds it.
-- Later stories add their tables here and raise the version.

-- One fetch of one Wallet's window (AD-7, AD-8, AD-19). Readers see it only once completed_at is set.
-- activity_read_until is NULL when the activity read was complete; otherwise the time of the last
-- row read, after which the window's Positions are "not fully read" (AD-7, AD-11).
-- window_capped is 1 when window_limit left older Positions out, for FR-11's window line (Story 3.3).
CREATE TABLE snapshot (
    fetch_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet              TEXT    NOT NULL,
    window_limit        INTEGER NOT NULL,
    started_at          INTEGER NOT NULL,
    completed_at        INTEGER,
    activity_read_until INTEGER,
    window_capped       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX snapshot_by_wallet ON snapshot (wallet, completed_at);

-- The window's positions-list rows (AD-10), in the order the window chose them.
CREATE TABLE listed_position (
    fetch_id       INTEGER NOT NULL REFERENCES snapshot (fetch_id) ON DELETE CASCADE,
    seq            INTEGER NOT NULL,
    condition_id   TEXT    NOT NULL,
    token_id       TEXT    NOT NULL,
    status         TEXT    NOT NULL,
    shares_bought  REAL    NOT NULL,
    first_entry_at INTEGER NOT NULL,
    last_event_at  INTEGER NOT NULL,
    PRIMARY KEY (fetch_id, seq)
);

-- The activity rows of the window's Markets (AD-10). Identical-looking rows are separate fills; `seq` keeps them.
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

-- Gamma Market records, one per Market, shared by every snapshot (AD-4). A resolved Market's
-- record is never fetched again. token_ids, outcome_prices and tags are JSON arrays.
-- event_id is Gamma's event. neg_risk_id is the negative-risk event (negRiskMarketID), set only for a Yes/No
-- negRisk Market: the key of its shared draw and the id its CONVERSION rows name (AD-20, AD-11).
CREATE TABLE market (
    condition_id   TEXT    PRIMARY KEY,
    closed         INTEGER NOT NULL,
    closed_time    INTEGER,
    token_ids      TEXT    NOT NULL,
    outcome_prices TEXT    NOT NULL,
    fees_enabled   INTEGER NOT NULL,
    start_time     INTEGER,
    fee_rate       REAL,
    fee_exponent   REAL,
    tags           TEXT    NOT NULL,
    event_id       TEXT,
    neg_risk_id    TEXT,
    fetched_at     INTEGER NOT NULL
);
CREATE INDEX market_by_neg_risk ON market (neg_risk_id);

-- Background work (AD-5): one row per lookup that needs a fetch (Story 2.5); Scan jobs come with Epic 4.
-- status: queued, running, done, interrupted, stopped, failed. result: 'no_history' when a finished
-- lookup found no Polymarket history (nothing is stored then). done, total, phase and message are the
-- progress JSON of GET /jobs/<id>/progress.
CREATE TABLE job (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT    NOT NULL,
    wallet      TEXT,
    status      TEXT    NOT NULL,
    phase       TEXT    NOT NULL,
    done        INTEGER NOT NULL,
    total       INTEGER NOT NULL,
    message     TEXT    NOT NULL,
    result      TEXT,
    created_at  INTEGER NOT NULL,
    finished_at INTEGER
);
CREATE INDEX job_by_status ON job (status, id);
CREATE INDEX job_by_wallet ON job (wallet, status);
