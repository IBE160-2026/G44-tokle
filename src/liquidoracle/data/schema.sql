-- The SQLite schema (AD-6). `data/store.py` runs it and sets PRAGMA user_version to
-- store.SCHEMA_VERSION. Later stories add their tables here and raise the version. On a version mismatch the
-- cache is rebuilt, while the Scans (the scan tables and scan jobs), the snapshots they name, those snapshots'
-- Market records and all stored prices are copied into the new tables by their shared columns
-- (store.KEPT_TABLES, Stories 4.3 and 6.1).

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
-- kind 'scan', wallet NULL, scan_id set: Resume adds a new row for the same Scan). Kind 'copy' (Story 6.2) runs
-- only the Copy phase, for a Scan that was finished without a Copy Test.
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
-- copied_at is when its Copy Test results were stored (Story 6.2); NULL for a Scan with no Copy Test, which is
-- how a Scan finished before version 9 comes out of the schema change.
CREATE TABLE scan (
    scan_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    cutoff          INTEGER NOT NULL,
    size            INTEGER NOT NULL,
    seed            INTEGER NOT NULL,
    as_of           INTEGER NOT NULL,
    step            TEXT    NOT NULL,
    candidate_count INTEGER,
    data_rebuilt    INTEGER NOT NULL DEFAULT 0,
    copied_at       INTEGER
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

-- A Scan's Copy Test, one row per priced Wallet (FR-18a, AD-22): every Before-Cut-off Passer and every other
-- top-N Wallet with at least the Minimum After-bets. after_positions is M, the tested Positions of its after
-- part as the Scan froze it; sampled is N, its Copy Sample ("priced N of M"), drawn with the Scan's Seed.
-- not_fully_read: its before or after part was not fully read (AD-9).
CREATE TABLE copy_sample (
    scan_id         INTEGER NOT NULL REFERENCES scan (scan_id) ON DELETE CASCADE,
    wallet          TEXT    NOT NULL,
    cutoff          INTEGER NOT NULL,
    seed            INTEGER NOT NULL,
    after_positions INTEGER NOT NULL,
    sampled         INTEGER NOT NULL CHECK (sampled BETWEEN 0 AND after_positions),
    not_fully_read  INTEGER NOT NULL,
    PRIMARY KEY (scan_id, wallet)
);

-- That Wallet's result at one Copy Delay (seconds: 60, 300, 1800). priced are the Copy Sample Positions whose
-- every buy fill has a recorded price one delay later; left_out the others, which are in none of the sums.
-- follower_pnl and spent are the Follower PnL and the money the follower spent (Spread Allowance and Follower
-- Fee included); the Follower Return is their ratio. own_pnl is the Wallet's own Real PnL on the priced Positions.
CREATE TABLE copy_result (
    scan_id      INTEGER NOT NULL,
    wallet       TEXT    NOT NULL,
    delay        INTEGER NOT NULL CHECK (delay > 0),
    priced       INTEGER NOT NULL CHECK (priced >= 0),
    left_out     INTEGER NOT NULL CHECK (left_out >= 0),
    follower_pnl REAL    NOT NULL,
    spent        REAL    NOT NULL CHECK (spent >= 0),
    own_pnl      REAL    NOT NULL,
    PRIMARY KEY (scan_id, wallet, delay),
    FOREIGN KEY (scan_id, wallet) REFERENCES copy_sample (scan_id, wallet) ON DELETE CASCADE
);

-- Price history for the Copy Test (FR-18c, AD-24): the one-minute price points of one outcome token, kept for
-- good (AD-4) and shared by every Scan and Wallet, because a price belongs to a token and a time only.
-- A price_window row says that [start_at, end_at] was asked and answered, also when no point came back, so it is
-- never asked again. route is where that answer came from: 'clob' (the old route), 'v2' (its replacement),
-- 'sample' (the Sample Dataset) or 'refused' (Polymarket refused the request; no points). Each asked window keeps
-- its own row, so a later, wider request never relabels an earlier answer.
CREATE TABLE price_window (
    token_id   TEXT    NOT NULL,
    start_at   INTEGER NOT NULL,
    end_at     INTEGER NOT NULL CHECK (end_at >= start_at),
    route      TEXT    NOT NULL CHECK (route IN ('clob', 'v2', 'sample', 'refused')),
    fetched_at INTEGER NOT NULL,
    PRIMARY KEY (token_id, start_at, end_at)
) WITHOUT ROWID;

-- One price of one outcome token at one second, inside a stored window.
CREATE TABLE price_point (
    token_id TEXT    NOT NULL,
    t        INTEGER NOT NULL,
    price    REAL    NOT NULL CHECK (price BETWEEN 0 AND 1),
    PRIMARY KEY (token_id, t)
) WITHOUT ROWID;
