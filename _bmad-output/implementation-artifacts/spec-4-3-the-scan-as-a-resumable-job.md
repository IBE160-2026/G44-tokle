---
title: 'Story 4.3: The Scan as a resumable job'
type: 'feature'
created: '2026-11-26'
status: 'done'
baseline_commit: '6a23bd1be0a74551cf044eba3f7fcb711d8a19a2'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 4.2's funnel runs only in memory, in one call. A Scan takes up to an hour, so it must run in the worker, survive closing the app or an outage, and leave stored results that the Scans page (4.4) and Watchlist (4.5) can read (FR-16, AD-5, AD-19, AD-22).

**Approach:** A Scan is a `scan` row plus a `job` of kind `scan` with two phases: `ranking` (4.2's funnel steps, each Market and each Wallet stored as it finishes) and `skill_tests` (each top-N Wallet's after part, then its `scan_before` and `scan_whole` results). Every Wallet window is a stored snapshot keyed by cut-off and side, frozen to the Scan. Resume runs the same job again and skips what is stored.

## Boundaries & Constraints

**Always:**
- **Schema v6** (`user_version` 5 → 6): `snapshot` gets `cutoff` and `side` (both NULL for a lookup's window). New tables `scan`, `scan_market`, `scan_candidate`, `scan_wallet`, `scan_result`; `job` gets `scan_id`.
- **Kept on a version mismatch (AD-6):** the scan tables, scan jobs, every snapshot a `scan_wallet` or `scan_result` names (with its rows), and the Market records those snapshots and `scan_market` name, copied by their shared columns. Everything else is rebuilt. If that copy fails, the scan rows are kept and marked `data_rebuilt`, shown as "Data rebuilt, cannot resume", with no Resume.
- **Snapshot key (AD-4, AD-19):** a lookup reads only lookup windows (`cutoff IS NULL`); a Scan reads only its own cut-off and side. `finish_snapshot` deletes only older snapshots with the same wallet, cut-off and side that no Scan names.
- **Ranking phase:** Market set stored first (`scan_market`, volume order); then each Market's two lists in order, its used/partial state and its pre-filter terms (added to `scan_candidate`) written in one transaction; then the 3 × N shortlist (`scan_wallet`); then each shortlisted Wallet's before part saved as a snapshot, its `fetch_id`, outcome, Real PnL and flag written; then the top N marked. Same results as `run_funnel` for the same reads.
- **Skill Tests phase:** per top-N Wallet, the after part saved as a snapshot; `scan_before` = Skill Test on the before snapshot, `scan_whole` = on both snapshots' Positions together. Each stored with `scan_id`, cut-off, Seed and both `fetch_id`s, plus verdict, p-value, tested count, Real PnL and the not-fully-read flag (AD-22). A Scan is `done` only after this phase.
- **Progress** `{status, phase, done, total, message}`: "Reading Markets: 34 of 100", "Fetching Wallets: 84 of 600", "Ranking", "84 of 200 Wallets checked" (EXPERIENCE.md).
- **Reuse (Edvard, 2026-11-26, AI rec):** a Wallet window is reused only for the same Wallet, Cut-off Date and side, when it is under 24 hours old (AD-4) or already frozen to this Scan; resolved Market records are never fetched again. A new Cut-off Date fetches the Wallet's windows again; FR-16 and AD-4 are reworded to say so. Rejected: building a new date's window from another date's stored window (new, risky logic before the code freeze).
- **Between two units of work** (one whole Market with both its lists, or one Wallet), the worker runs every waiting lookup first (AD-5). **Decision (Edvard, 2026-11-26, AI rec):** a unit is a whole Market, as 4.2 built it, and AD-5 is reworded; a Market unit is up to 30 pages, about 6 seconds, while a big Wallet's part is one unit too and can take longer (corrected by Edvard, 2026-11-26, after the review). Rejected: page by page (needs a paging API on the client and changes 4.2's code).
- **Spec kept whole (Edvard, 2026-11-26, AI rec)** at about 2,400 tokens: one goal. Rejected: a part A/B split.
- **States:** Polymarket not answering → `stopped`; app closed → `interrupted` (existing startup rule); any other error → `failed`, logged, no Resume. Resume queues a new job for the same Scan and never fetches a Wallet or Market already stored for it.
- **One Scan at a time:** starting one while another is queued or running is refused.
- **Token check (deferred from 4.2):** an OPEN holder row whose token is not one of the Market's outcomes makes that Market "not used: partial" instead of ending the Scan.
- **as-of time** = when the Scan was created; Seed = the settings' Seed.
- Tests network-blocked, each naming its FR/AD.

**Never:**
- No pages, routes or templates (Story 4.4 and 4.5). No OfflineClient support (Story 4.6). No Hold-up or Copy Test phase (Epics 5 and 6).
- No sharing of CLOSED pages between the before and after reads (a later speed-up).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | Fake Polymarket, N = 3 | `done`; 3 `scan_before` + 3 `scan_whole` results; top N equals `run_funnel`'s | N/A |
| Outage in Wallet phase | Unavailable on the 5th Wallet | `stopped` at "Fetching Wallets: 4 of 9" | Resume fetches from the 5th Wallet on; Wallets 1–4 make no request |
| App closed | job left `running` | `interrupted` at startup | Resume as above |
| Bug | an unexpected exception | `failed`, logged | no Resume |
| Lookup waiting | lookup queued during the Market phase | runs before the next Market | N/A |
| Lookup after a Scan | Wallet has a Scan snapshot only | lookup fetches its own window | N/A |
| Schema 6 → 7 | DB with a finished Scan | Scan, results, frozen snapshots kept; other rows rebuilt | copy fails → `data_rebuilt` |
| Second Scan | one is running | refused | N/A |
| Unknown token | OPEN row on a token not in the Market | Market partial | N/A |

</frozen-after-approval>

## Code Map

- `src/liquidoracle/data/schema.sql`, `data/store.py:30` (`SCHEMA_VERSION`), `:441` (`_prepare_schema` drops every table today) -- v6 tables; keep-and-copy migration; `data_rebuilt`.
- `data/store.py:194` `finish_snapshot` (deletes all older snapshots of the Wallet today), `:237` `serving_snapshot`, `:233` `latest_snapshot`, `:299-319` `has_snapshot`/`snapshot_time`/`wallet_count` -- add the cut-off/side key; lookup readers filter `cutoff IS NULL` (otherwise a Scan's window would show on the lookup page).
- `data/store.py:323-396` jobs -- add `queue_scan`, `claim_next_lookup`, `update_progress`, scan reads/writes. Only `store.py` runs SQL.
- `services/fetch.py:18` `fetch_wallet` -- add `cutoff`/`side`; reuse via `serving_snapshot(..., max_age=24 h)`; `result_of` (:60) is the pattern for building a Position set from a snapshot.
- `services/scan.py` -- keep `choose_markets`, `read_candidates`, `shortlist`, `rank_wallet`, `run_funnel`; add the job runner (`ScanRunner` or functions) driven by stored state, with a `between_units` callback. `rank_wallet` takes a stored snapshot instead of calling `positions_near` itself.
- `core/funnel.py:16` `estimates` -- split into per-Market terms so stored and in-memory runs add the same numbers in the same order.
- `services/jobs.py` -- `Jobs.queue_scan`, `Jobs.resume_scan`; `Worker._run` dispatches on `kind`; scan errors map to `stopped`/`failed`; `between_units` runs claimed lookups.
- `core/skilltest.py:45` `skill_test(..., scope=)`; `core/positions.py:69` `build_positions` -- unchanged.
- `records.py:278` `SkillTestResult`, `:416` `ScanFunnel` -- add a stored-result and scan-status record if needed.
- `tests/fake_polymarket.py` (condition + Gamma routes from 4.2), `tests/test_scan.py`, `tests/test_store.py`, `tests/test_live_lookup.py` (worker and `run_once`) -- patterns.

## Tasks & Acceptance

**Execution:** (the plan task is done by the orchestrator and committed first)
- [x] `ARCHITECTURE-SPINE.md` (AD-4, AD-5, AD-6, AD-19), `prd.md` FR-16 (+ its decision log), `.memlog.md` files, `epic-4-context.md` -- the reuse rule, the whole-Market unit, the snapshot key and the kept tables -- plan before code.
- [x] `data/schema.sql`, `data/store.py` -- v6, keep-and-copy migration, snapshot key, scan and job methods -- AD-6, AD-19, AD-22.
- [x] `core/funnel.py`, `services/fetch.py`, `services/scan.py` -- per-Market terms, keyed fetch with reuse, the two-phase runner, token check -- FR-16, AD-5, AD-9, AD-21.
- [x] `services/jobs.py` -- scan jobs, Resume, lookups between units, one Scan at a time -- AD-5.
- [x] `tests/test_store.py`, `tests/test_scan.py`, `tests/test_scan_job.py` (new) -- every matrix row; a migration test from a hand-built v6 file to a test-only v7; the Resume test counts requests per Wallet.

**Acceptance Criteria:**
- Given a stopped or interrupted Scan, when it is resumed and finishes, then its results equal those of an uninterrupted run on the same fake data, and no finished Wallet or Market was requested twice.
- Given a finished Scan, when a lookup of one of its Wallets runs, then the Scan's snapshots and results are unchanged.
- Given the whole suite, when it runs network-blocked, then every test passes.

## Design Notes

- **Why store pre-filter terms per Wallet, not holder rows:** up to 30,000 rows per Market × 100 Markets would be millions of rows; one running estimate per Wallet is small, and Markets are always added in the same order, so a resumed Scan gets the same sums.
- **Cost:** 100 Markets (each up to 30 pages), 3 × N before parts, N after parts.

## Verification

**Commands:**
- `uv run pytest tests/test_store.py tests/test_scan.py tests/test_scan_job.py -v` -- expected: all pass.
- `uv run pytest` -- expected: whole suite green.

## Implementation Notes

**Plan commit:** 99a84aa (PRD FR-16 + decision log, AD-4/5/6/19, epics 4.3, epic-4 context, memlogs, sprint 4-3 in-progress).

**Choices made while building (none changes the frozen intent):**
- **Row records live in `data/store.py`** beside `Snapshot` and `Job`: `Scan`, `ScanMarket`, `ScanWallet`, `ScanResult`, `ScanStep` and `WalletOutcome`.
- **`FRESH_FOR` moved to `services/fetch.py`** so the lookup and the Scan share one 24-hour rule; `lookup.py` imports it.
- **Progress text comes from `phrases.of_total`** (AD-25). Before the Market set is known the message is "Reading Markets". A stopped or failed Scan keeps its `done` count (`finish_job(keep_progress=True)`) and the message "Polymarket did not answer" / "Something went wrong", so Story 4.4 can write "Stopped at 4 of 9: Polymarket did not answer"; an interrupted one keeps it too (the startup rule never touched `done`).
- **Resume adds a new job row** for the same Scan; the Scan's status is its latest job's. A queued, finished, failed, rebuilt or unknown Scan does not resume, nor any Scan while another is queued or running.
- **A top Wallet with no before snapshot** (refused, or no history) gets no after read; both its results are *Not enough data* on nothing, with its flag kept. A refused after part keeps the Wallet flagged on `scan_whole`.
- **`estimates` now adds each Market's exact sum in set order** (`market_terms`), the way the store adds them one Market at a time; the stored estimates equal `run_funnel`'s bit for bit (tested). 4.2's tests are unchanged and pass.
- **The migration** drops every index, renames the ten kept tables to `old_*`, creates the new schema, copies by shared columns (scan tables and scan jobs must copy; the snapshot family copies inside a savepoint, else every Scan is marked `data_rebuilt`), then drops `old_*`. A file older than version 6 is rebuilt as before.
- **An abandoned (never finished) snapshot of the Wallet, of any part, is deleted** when the Wallet's next snapshot finishes, as before; only finished snapshots are keyed.
- **The matrix's outage row** is tested with a ninth candidate added to the 4.2 scenario, so N = 3 shortlists 9 and the Scan stops at "4 of 9".

**Test checks.** Eight planted bugs were each caught by a new test: frozen snapshots deleted by a newer fetch, the lookup reading a Scan's part, Resume reading finished Wallets again, no lookups between units (caught by the lookup test alone too), a stopped Scan losing its count, a schema change dropping the Scans, the token check missing, and `scan_whole` ignoring the after part (first missed: the fixture Wallets' after parts are empty or all split-or-merged, so a test splits the sharp trader into two parts).

## Spec Change Log

- 2026-11-26, after review pass 1 (B4 = E6): Edvard approved correcting the frozen reuse/unit decision's wait claim. It said "a lookup waits at most about 6 seconds", true only for a Market unit; it now also says a big Wallet's part is one unit and can take longer. The decision itself (whole Markets) is unchanged. KEEP: whole-Market and whole-Wallet units.

## Review Triage Log

Pass 1 (2026-11-26): blind hunter (B), edge-case hunter (E), verification gap (V). Checked against the code.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| B1 | The Scan's as-of time is stored but never used (AD-19) | medium | After parts are fetched at Skill Test time, days later on a Resume, so `scan_whole` could count Markets resolved after the Scan started and differ from an uninterrupted run | patch: `as_of_part` leaves out Markets resolved at or after `as_of`; two tests |
| B2 = E1 | After a failed snapshot copy (`data_rebuilt`), new snapshots reuse the rebuilt Scan's frozen ids | medium | Dropping `old_snapshot` dropped its AUTOINCREMENT counter, so ids restart at 1; `store.snapshot(old id)` could return another Wallet's data and `_FROZEN_IDS` would protect it | patch: `_carry_sequences` keeps each kept table's counter; asserted in both migration tests |
| E2 | Lookup job ids are reused after a schema change | low | True before 4.3 too (every mismatch rebuilt `job`); fixed anyway by the same counter carry | patch (with B2) |
| B4 = E6 | "A lookup waits at most about 6 seconds" counts only Market units | low | A Wallet unit reads that Wallet's whole part (up to 2,000 Positions plus activity), and `choose_markets` is one unit; Wallets were whole units in AD-5 before | patch: spine AD-5 and epic-4 context reworded, memlog entry; the frozen spec line keeps the original wording (Edvard's to change) |
| B12 | Progress never shows the finished count of the Market and Wallet steps | low | Progress was written only before each unit, so the last messages were "3 of 4" and "7 of 8" | patch: a closing progress line after each loop |
| V1 | Lookups-first is not tested between Wallets or between Skill Tests | medium (pre-verified) | Removing `between()` from `_rank_wallets` and `_test_top` left the suite green | patch: two tests |
| V2 | Resume during the Skill Test phase is never run | medium (pre-verified) | Removing the `tested_wallets` skip left the suite green | patch: a stop-and-resume test in `skill_tests` |
| V3 | Reuse across two Scans is tested only on the helper | medium (pre-verified) | Replacing `fetch_part` by `fetch_wallet` in the runner left the suite green | patch: a second Scan on the same date reads no stored part |
| V4 | A refused after part is never exercised | medium (pre-verified) | Dropping the `refused_after` flag left the suite green | patch: test on `scan_results(refused_after=True)` |
| V5 | Thousands separators in the progress text are not tested | low (pre-verified) | `of_total` had no test; counts in the Scan tests stay under 10 | patch: test in `test_phrases.py` |
| B10 = E10 | The Resume test counts requests only for CONTRACT, not per finished Wallet | low | The spec's task says "counts requests per Wallet"; SMALL, LOSERS and FEES were checked only by snapshot rows | patch: zero requests asserted for every finished Wallet outside the top N |
| B3 | A file from a newer schema is downgraded silently | low | Needs running older code on a newer database; true before 4.3 too (any mismatch rebuilt); a guard adds a branch | reject |
| B5 | A resumed job starts as phase `ranking`, 0 of 0, "Resuming" | low | The first unit reports at once (milliseconds); the stopped count stays on the stopped job row, which Story 4.4 reads | reject |
| B6 = E4 | Any non-Polymarket error, including a busy database or a lookup's write failing inside `between()`, fails the Scan | low | The frozen intent says "any other error → failed"; one writer process with short writes makes a 5 s busy timeout unlikely; the fix adds guards | reject |
| B7 = E9 | Offline Mode is not guarded; an offline Scan would fail | low | Nothing calls `start_scan` yet; Offline Mode starts no worker (AD-13), and Story 4.6 adds offline Scans | reject |
| B8 = E7 | `start_scan` accepts a Cut-off Date today or later | low | Story 4.4's form checks the date ("The Cut-off Date must be in the past.") before anything starts; no other caller | reject |
| E8 | A huge `size` raises OverflowError instead of ValueError | low | No caller; Story 4.4 limits N to 10–500 | reject |
| B9 | Planning documents disagree (kept tables in epics.md; the frozen-Scan clause missing from FR-16) | false | epics.md lists the minimum and the spine adds detail; FR-16 already says a resumed Scan does not fetch finished Wallets again; no contradiction | reject |
| B11 | `_FROZEN_IDS` runs unindexed on every snapshot finish | low | A few thousand rows per Scan; a full scan of them is milliseconds; no named harm | reject |
| E3 | `finish_snapshot` deletes same-part snapshots of another window limit | false | The frozen intent says "same wallet, cut-off and side", as before 4.3; only `WINDOW_LIMIT` is ever used | reject |
| E5 | An after part raising `NoPolymarketHistory` or `ProtocolContractAddress` fails the Scan | low | Unreachable in practice: the same address had non-empty lists and was not a contract on its before read | reject |
| E11 | `tests/test_scan.py` is not where 4.3's matrix tests are | low | The spec names `test_scan_job.py` (new) for every matrix row; `test_scan.py` is the pattern | reject |
