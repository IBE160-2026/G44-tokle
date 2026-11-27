-- The SQLite schema (AD-6). `data/store.py` runs it and sets PRAGMA user_version to
-- store.SCHEMA_VERSION. Later stories add their tables here and raise the version. On a version mismatch the
-- cache is rebuilt, while the Scans (the scan tables and scan jobs), the snapshots they name and those snapshots'
-- Market records are copied into the new tables by their shared columns (store.KEPT_TABLES, Story 4.3).

-- One fetch of one Wallet's window (AD-7, AD-8, AD-19). Readers see it only once completed_at is set.
-- activity_read_until is NULL when the activity read was complete; otherwise the time of the last
-- row read, after which the window's Positions are "not fully read" (AD-7, AD-11).
-- window_capped is 1 when window_limit left older Positions out, for FR-11's window line (Story 3.3).
-- cutoff (00:00 UTC epoch) and side ('before' or 'after') name the part of a Cut-off Date the window is;
-- both are NULL for a lookup's window. With wallet and window_limit they are the snapshot's key (AD-4, Story 4.3).
CREATE TABLE snapshot (
    fetch_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet              TEXT    NOT NULL,
    window_limit        INTEGER NOT NULL,
    started_at          INTEGER NOT NULL,
    completed_at        INTEGER,
    activity_read_until INTEGER,
    window_capped       INTEGER NOT NULL DEFAULT 0,
    cutoff              INTEGER,
    side                TEXT
);
CREATE INDEX snapshot_by_wallet ON snapshot (wallet, cutoff, side, completed_at);

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

-- Background work (AD-5): one row per lookup that needs a fetch (Story 2.5) and per run of a Scan (Story 4.3;
-- kind 'scan', wallet NULL, scan_id set: Resume adds a new row for the same Scan).
-- status: queued, running, done, interrupted, stopped, failed. result: 'no_history' when a finished
-- lookup found no Polymarket history (nothing is stored then). done, total, phase and message are the
-- progress JSON of GET /jobs/<id>/progress.
CREATE TABLE job (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT    NOT NULL,
    wallet      TEXT,
    scan_id     INTEGER,
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
CREATE INDEX job_by_scan ON job (scan_id, id);

-- One Scan (FR-16, AD-19, AD-21). cutoff is 00:00 UTC epoch; size is N; as_of is when it was created (AD-19).
-- step is how far it got: created, markets (the Market set is stored), shortlisted, ranked (top N marked),
-- done (every phase finished). candidate_count counts the Wallets in the used Markets, set with the shortlist.
-- data_rebuilt is 1 when a schema change could not keep its snapshots: it cannot resume (AD-6).
CREATE TABLE scan (
    scan_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    cutoff          INTEGER NOT NULL,
    size            INTEGER NOT NULL,
    seed            INTEGER NOT NULL,
    as_of           INTEGER NOT NULL,
    step            TEXT    NOT NULL,
    candidate_count INTEGER,
    data_rebuilt    INTEGER NOT NULL DEFAULT 0
);

-- The Scan's Market set in volume order (AD-21). state is NULL until both lists are read, then 'used' or
-- 'partial' ("not used: partial", AD-9). The Market's record is in `market`.
CREATE TABLE scan_market (
    scan_id      INTEGER NOT NULL REFERENCES scan (scan_id) ON DELETE CASCADE,
    seq          INTEGER NOT NULL,
    condition_id TEXT    NOT NULL,
    volume       REAL    NOT NULL,
    state        TEXT,
    PRIMARY KEY (scan_id, seq)
);

-- Each candidate's running pre-filter estimate (AD-21): every used Market adds its terms in set order.
CREATE TABLE scan_candidate (
    scan_id  INTEGER NOT NULL REFERENCES scan (scan_id) ON DELETE CASCADE,
    wallet   TEXT    NOT NULL,
    estimate REAL    NOT NULL,
    PRIMARY KEY (scan_id, wallet)
);

-- The 3 x N shortlist in estimate order (seq) and how each Wallet ranked (AD-9). outcome is NULL until it is read:
-- 'ranked', 'no_history', 'refused' (kept, not fully read) or 'contract' (dropped). before_fetch_id and
-- after_fetch_id are the snapshots frozen to this Scan (AD-19); top marks the N kept.
CREATE TABLE scan_wallet (
    scan_id         INTEGER NOT NULL REFERENCES scan (scan_id) ON DELETE CASCADE,
    seq             INTEGER NOT NULL,
    wallet          TEXT    NOT NULL,
    estimate        REAL    NOT NULL,
    outcome         TEXT,
    real_pnl        REAL,
    not_fully_read  INTEGER NOT NULL DEFAULT 0,
    before_fetch_id INTEGER,
    after_fetch_id  INTEGER,
    top             INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (scan_id, seq),
    UNIQUE (scan_id, wallet)
);

-- A top-N Wallet's Skill Test results (AD-22): scope 'scan_before' (the before part: Passers) or 'scan_whole'
-- (both parts: the Watchlist), with the Scan, cut-off, Seed and the snapshots they rest on (NULL when the
-- Wallet had nothing to read). p_value is NULL for Not enough data.
CREATE TABLE scan_result (
    scan_id        INTEGER NOT NULL REFERENCES scan (scan_id) ON DELETE CASCADE,
    wallet         TEXT    NOT NULL,
    scope          TEXT    NOT NULL,
    cutoff         INTEGER NOT NULL,
    seed           INTEGER NOT NULL,
    fetch_id       INTEGER,
    after_fetch_id INTEGER,
    verdict        TEXT    NOT NULL,
    p_value        REAL,
    tested_count   INTEGER NOT NULL,
    real_pnl       REAL    NOT NULL,
    not_fully_read INTEGER NOT NULL,
    PRIMARY KEY (scan_id, wallet, scope)
);

-- A Scan's Hold-up Test results (FR-17, AD-22): one row per group ('passers', 'comparison') with scope
-- 'holdup_after', the Scan, its cut-off and Seed. wallets are the Wallets in the group, dropped those with too few
-- bets after the cut-off, not_fully_read those whose before or after part was not fully read; tested_count and
-- real_pnl cover the pooled after-part bets of the Wallets that were not dropped. p_value is NULL for Not enough
-- data. The rows are written in the transaction that moves the Scan to 'done' (Story 5.1).
CREATE TABLE group_result (
    scan_id        INTEGER NOT NULL REFERENCES scan (scan_id) ON DELETE CASCADE,
    scope          TEXT    NOT NULL,
    group_name     TEXT    NOT NULL,
    cutoff         INTEGER NOT NULL,
    seed           INTEGER NOT NULL,
    verdict        TEXT    NOT NULL,
    p_value        REAL,
    tested_count   INTEGER NOT NULL,
    real_pnl       REAL    NOT NULL,
    wallets        INTEGER NOT NULL,
    dropped        INTEGER NOT NULL,
    not_fully_read INTEGER NOT NULL,
    PRIMARY KEY (scan_id, scope, group_name)
);
