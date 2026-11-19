---
title: 'Story 1.6: Offline Mode and loading the Sample Dataset'
type: 'feature'
created: '2026-11-19'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'c53e43cdcac03e154a569e4c9b8f33dfdabc6440'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `load-sample` only prints "not built yet", there is no database and no `OfflineClient`, so the examiner cannot run the app offline and Story 1.7 has nothing to read.

**Approach:** Add the SQLite store (`data/store.py` + `schema.sql`), an `OfflineClient` that serves the Sample Dataset JSON files, one fetch pipeline in `services/` that writes a Wallet as a snapshot, and a startup swap that gives Offline Mode the `OfflineClient` and `instance/offline.db`. `load-sample` regenerates the 1,000 coin-flippers and runs every Sample Wallet (5 small Synthetic Wallets + 1,000 coin-flippers) through that pipeline.

## Boundaries & Constraints

**Always:**
- Only `data/store.py` runs SQL: plain `sqlite3`, WAL, busy timeout, foreign keys, one connection per thread, every write in `BEGIN IMMEDIATE` (AD-6). `PRAGMA user_version` = 1; another version rebuilds the tables (all Epic 1 tables are fetched data).
- Snapshot (AD-19): a row per fetch with `fetch_id`; rows carry it; a final step marks it complete. Readers see only complete snapshots. Identical activity rows stay separate (kept in order).
- Markets are stored once per `condition_id`, shared by snapshots (AD-4).
- `OfflineClient` returns `records` types through the same methods the live client will have: `positions(wallet)`, `activity(wallet)`, `markets(condition_ids)` (AD-2). Addresses are lower-cased (FR-1). An address or Market not in the Sample Dataset raises `NotAvailableOffline` (FR-14).
- `load-sample` always writes `instance/offline.db`, whatever the flags or `.env` (AD-14), runs from the repository folder like `make-synthetic`, and prints progress and the total.
- Mode swap in one place in `__main__`: offline → `OfflineClient` + `instance/offline.db`; live → `instance/live.db` and no client until Story 2.1 (AD-13). Only `__main__` and the Offline pill in `web` read `settings.offline`; a test enforces it.
- Every test names its FR/AD; all run with sockets blocked.

**Never:**
- No pages, routes or Sample Wallets list (Story 1.7); no live client, per-Wallet lock, worker or cache freshness (Epic 2); no stored Skill Test results; no price history in the store or client (Epic 6).
- No ORM, no `git add .`, no merge, no `gh`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Load | `load-sample` in the repo folder | coin-flippers rewritten; 1,005 Wallets in `offline.db`, one complete snapshot each | N/A |
| Not repo folder | `load-sample` elsewhere | plain message, exit 2, nothing written | N/A |
| Round trip | 5 small Wallets + 3 coin-flippers → client → pipeline → store → Skill Test | stored records equal the generator's; counts, Real PnL and Verdicts match `expected.json`; hand-check and thin wallet read *Not enough data* | N/A |
| Unknown address | `0x` + 40 zeros, offline | — | `NotAvailableOffline`; no snapshot written |
| Half-written | snapshot begun, not finished | readers get the previous complete one, or None | N/A |
| Re-fetch | same Wallet fetched twice | newest complete snapshot read; the older ones deleted in the same final step | N/A |
| Old schema | db with `user_version` 0 or 99 | tables rebuilt, version 1 | N/A |
| Size | committed `sample_data/` | under 25,000,000 bytes (FR-12) | test fails above |

**Decisions (Edvard, 2026-11-19):**
- A second `load-sample` gives each Wallet a new snapshot and deletes its older snapshots in the same final step; nothing else in `offline.db` is touched (AI's option A). Rejected: deleting and rebuilding the whole file (a later offline Scan would be lost, and on Windows it fails while the app runs offline). Epic 4 adds "unless a Scan refers to it" (AD-19).
- Spec kept whole at about 1,800 tokens (AI's recommendation): the store, client, pipeline and swap are only testable together through the round trip.

</frozen-after-approval>

## Code Map

- `src/liquidoracle/__main__.py` -- `load-sample` stub and `make_synthetic`'s repo-folder check to reuse; add `open_sources(settings, root)` and `load_sample(root)`.
- `src/liquidoracle/data/synthetic.py` -- `write_coin_flippers(root, count)`, `COIN_FLIPPERS`, `SMALL_DIR`, `COIN_FLIPPER_DIR`; do not change.
- `src/liquidoracle/data/sample_json.py` -- `read_wallet(path)`; the only reader of Sample Dataset files.
- `src/liquidoracle/records.py` -- `ActivityRow`, `ListedPosition`, `Market`, `SampleWallet`; read only.
- `src/liquidoracle/core/positions.py` `build_positions(fills, markets)` and `core/skilltest.py` `skill_test(set, seed=, unit_id=)` -- the round trip's last two steps.
- `sample_data/synthetic/expected.json` -- hand answers; not a Wallet file, so the client skips it.
- `tests/test_architecture.py` -- `IO_STDLIB` allows `sqlite3` in `data` and `__main__`; add "only `data/store.py`".
- `tests/test_cli.py` -- `test_load_sample_says_not_built_yet` is replaced.
- `README.md:30` -- says load-sample is not built.

## Tasks & Acceptance

**Execution:**
- [x] `src/liquidoracle/data/errors.py` -- `NotAvailableOffline` -- FR-14, Conventions › Errors.
- [x] `src/liquidoracle/data/schema.sql`, `src/liquidoracle/data/store.py` -- `Store(path)`: `begin_snapshot`, `add_positions`, `add_activity`, `save_markets`, `finish_snapshot`, `latest_snapshot(wallet)` -- AD-6, AD-19.
- [x] `src/liquidoracle/data/offline.py` -- `OfflineClient(files)`, `sample_files(root)`; lazy index address → file and condition_id → file -- AD-2, AD-14, FR-14.
- [x] `src/liquidoracle/services/fetch.py` -- `fetch_wallet(client, store, wallet) -> fetch_id`; `skill_result(store, wallet, seed)` from the latest snapshot -- AD-14, AD-19.
- [x] `src/liquidoracle/__main__.py` -- `load-sample`, `open_sources` -- AD-13, AD-14.
- [x] `tests/test_store.py`, `tests/test_offline.py`, `tests/test_cli.py`, `tests/test_architecture.py` -- the matrix, the round trip, pragmas, threads, the SQL-only-in-store and mode-read rules.
- [x] `README.md` -- `load-sample` line: what it does and that it takes a while.
- [x] `sprint-status.yaml` -- 1-6 to `review` at the end.

**Acceptance Criteria:**
- Given `uv run pytest`, then all tests pass with sockets blocked.
- Given `uv run liquidoracle load-sample` on this PC, then it finishes and a second run gives the same Wallet count.

## Implementation Notes

- Implemented directly in the main session; subagents only for the review (Edvard's standing call).
- Epic 1 context refreshed first: its Money and phrases lines predated the Story 1.5 plan change (bdb7f5f).
- `data/client.py` holds the `WalletClient` protocol (three methods) so the live client in Story 2.1 implements the same interface; `data/errors.py` holds `NotAvailableOffline`.
- `data/sample_json.py` gained `read_ids(path)`: the client indexes 1,005 files by address and Market id without building every record, then reads one Wallet fully (and strictly) when it is fetched. The last file read is kept, since a fetch asks for one Wallet's three lists in a row.
- `Store.finish_snapshot` also refuses a snapshot whose rows name a Market that is not stored, so a visible snapshot is always complete (AD-19). Not in the plan; added by the AI.
- `Store.wallet_count()` added for `load-sample`'s final line and the tests.
- `open_sources` lives in `__main__` and is tested directly; Story 1.7 passes its result to the pages. Live runs get `client=None` until Story 2.1. The mode-read rule also allows `settings` (it builds the value); the first run of the new rule caught that.
- Not in the plan, added by the AI: `load-sample` stops with a plain message (exit 2) on a malformed Sample Dataset file or a file error, not a traceback.
- Measured on this PC: `load-sample` takes 15 s for 1,005 Wallets; `instance/offline.db` is about 77 MB; a second run keeps one snapshot per Wallet (1,005) and the same size. Read back with Seed 44: sharp trader *Skilled (high confidence)*, stop-loss trader *Skilled (high confidence)*, favourite buyer *No evidence of skill*, hand-check and thin wallet *Not enough data*, coin-flipper 0 *No evidence of skill*.
- Full suite: 406 passed, 1 deselected (364 before + 42 new). After review: 416 passed, 1 deselected.

## Spec Change Log

## Review Triage Log

Review pass 1 (2026-11-19). Three subagent reviewers on the diff since the baseline (code, tests, README; spec and sprint status left out): blind (B, 16 findings), edge-case (E, 24) and verification-gap (V, 2 gaps + 1 other). 43 findings, grouped below by root cause.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | B2, E1, E2, V3: `load-sample` catches only OSError and ValueError; a corrupt or locked `offline.db` (sqlite3 errors) or `NotAvailableOffline` (a LookupError) ends in a traceback | medium | Reproduced by V: a text file named `offline.db` gives `sqlite3.DatabaseError` | patch: `store.StoreError` (= `sqlite3.Error`, so only the store imports sqlite3) and LookupError caught; test with a broken `offline.db` |
| 2 | V2, E3, E4: the index checks only lower case; no test, and whitespace, empty or malformed addresses pass | low | True: `" 0xab…"` passes, then the stripped lookup misses and load-sample stops with NotAvailableOffline | patch: address must match `0x` + 40 lower-case hex; 5 planted addresses tested |
| 3 | B1, E13: one connection per thread is kept until `close()`; a thread-per-request web server piles them up | medium | True by reading `_connection`; Story 1.7 serves pages from Werkzeug's threads | patch: a new connection closes those of ended threads; test (2 left, not 6) |
| 4 | B8, E15, E16: a failed COMMIT leaves the connection inside a transaction; a ROLLBACK after SQLite already rolled back hides the first error | low | True: COMMIT was outside the try | patch: COMMIT inside the try, ROLLBACK only `if db.in_transaction`; test with a deferred foreign-key failure at COMMIT |
| 5 | V1: the thread test passes about 96% of the time without BEGIN IMMEDIATE; the other check reads source text | low | V's probe: 2 failures in 50 with plain BEGIN | patch: two lock tests (another writer is shut out from the start; a write waits and then succeeds) |
| 6 | E14: `close()` while another thread is mid-transaction | low | Only `load-sample` and tests call it, at the end | patch: docstring says shutdown only |
| 7 | B16: Edvard's decision, the AI's build choices and the 5 s [ASSUMPTION] are not in a memlog; PRD may not name SQLite | low | Memlog true (not yet written); PRD false: §8 and the addendum name SQLite | patch: three architecture memlog entries |
| 8 | B5, E17, E18, E19: two fetches of one Wallet at once delete each other's unfinished snapshot | false | Not reachable in Epic 1: `load-sample` is the only fetcher and runs on one thread; Story 2.2's per-Wallet lock (AD-19) is the planned guard | rejected |
| 9 | B3, E5, E6: Wallets or coin-flipper files removed from the Sample Dataset stay in `offline.db` and the count | low | Only if the constant or files change by hand; the fix adds a sweep | rejected |
| 10 | B4: a file that passes the index check but fails the strict read stops load-sample half-way | low | Needs a hand-broken file; the message names it and a rerun replaces every Wallet | rejected |
| 11 | B6: snapshots do not freeze their Market rows | false | By design (AD-4): resolved Market records never change; Scans use as-of times (AD-19) | rejected |
| 12 | B7, E21: any schema-version mismatch, even a newer file, rebuilds the tables | low | AD-6 says so; every Epic 1 table is re-fetchable; Epic 4 adds migration for Scans | rejected |
| 13 | B9, E12: two files with one Market: the first file wins silently | low | Synthetic Markets are unique per Wallet; Story 2.6 builds real files by script from one capture | rejected |
| 14 | B11, E8, E9, E10: Offline Mode not yet wired into `run`; empty or missing `offline.db`, wrong folder, files changed after start | false | Pages are Story 1.7 (spec Never); carried as open points for 1.7 | rejected |
| 15 | B12: README and help times and sizes differ | low | 15-30 s vs "under a minute" agree; 75 MB is the database, 90 MB the coin-flipper files | rejected |
| 16 | B13: the `.env` part of the load-sample test proves little; tests read counts through `_connection()` | low | Partly true; `live.db` not created is asserted | rejected |
| 17 | B14, E23, E24: the `.offline` rule misses `getattr`, could flag a module path, exempts all of `web` | low | No such code exists; AD-13 lets pages show the mode | rejected |
| 18 | B15: five write transactions per Wallet | low | Measured 15 s for 1,005 Wallets | rejected |
| 19 | B10: address clean-up repeated in three places, no format check at the service | low | Story 1.7 adds FR-1's format check at the lookup | rejected |
| 20 | E7: `sample_data/` present but `synthetic/` missing gives success without them | low | Not in a checkout of this repository | rejected |
| 21 | E11: a single string as `condition_ids` | false | Typed `Iterable[str]`; the one caller passes a sorted list | rejected |
| 22 | E20: `latest_snapshot` inside an open transaction | false | No caller does that | rejected |
| 23 | E22: `LIKE 'sqlite_%'` also matches names starting `sqlite` | low | Only this app's tables are in the file | rejected |

After the patches: 416 passed, 1 deselected; `load-sample` 16 s, 1,005 Wallets.

## Design Notes

- Story 2.2 will change the client's method signatures (`positions_near(wallet, cutoff, side, limit)`) in both clients; 1.6 keeps the three plain methods.
- Price points stay in the JSON files only; Story 6.5 stores them.

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass
- `uv run liquidoracle load-sample` -- expected: 1,005 Wallets loaded, time printed
