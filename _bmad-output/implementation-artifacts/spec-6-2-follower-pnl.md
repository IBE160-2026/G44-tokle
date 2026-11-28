---
title: 'Story 6.2: Follower PnL'
type: 'feature'
created: '2026-11-28'
status: 'in-progress'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '93bc7ac11b0a4ede4bdf98ff77067e7824d7e6c6'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-6-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The app can fetch and store prices (Story 6.1) but cannot yet say what a follower who copied a Wallet's buys 1, 5 or 30 minutes late would have made (FR-18a), and no job computes it. The live Scan of Story 5.3 is finished and must get its Copy Test without being redone (Edvard, 2026-11-28).

**Approach:** Pure Copy Test maths in `core/copytest` (Copy Sample, Follower PnL, Follower Fee, Follower Return). A Copy phase as the last phase of a new Scan, and a job of its own kind that runs only that phase on a finished Scan. The results are stored per Wallet and Copy Delay; the schema rises to version 9 and keeps every Scan and every stored price.

## Boundaries & Constraints

**Always:**
- The Copy Sample is drawn from the tested Positions of a Wallet's frozen after part, cut to the Scan's as-of time, sorted by (condition, token) before the draw; its random stream is its own purpose with the Wallet as the unit (AD-15, AD-19).
- Priced are every Before-Cut-off Passer and every other top-N Wallet with at least the Minimum After-bets (10) tested after Positions. The others can never be in the Copy Pool and get no rows and no price requests.
- A Position is priced at a Copy Delay only when every one of its buy fills has a price at that delay; otherwise the whole Position is left out of that delay and counted (Edvard, 2026-11-28: FR-18a's wording; rejected: leaving out only the fills without a price).
- The Follower Fee uses the Market's listed rate and exponent, which is the rate Gamma gives today, and the README says so (Edvard, 2026-11-28; rejected: the rate the copied Wallet's own fill fitted).
- Prices come only through `services/prices.plan` and `fetch`: one price request is one unit of work, and waiting lookups run between units. A stored window is never asked again.
- A new Scan's Copy results are stored in the transaction that finishes it. A Scan that stops in the Copy phase is not finished and resumes like any other stop.
- The reference calculation is made by a fresh helper from the PRD and the set's data alone, and is committed before the commit that adds its test.
- The schema change is proven on a duplicate of the kept live database before the app is started on `instance/live.db`; the kept copy is never opened for writing.
- One real Passer is copied live on that duplicate to prove the path end to end. Only its counts are read and written down (requests, Positions priced, left out); its Follower numbers are not looked at before Story 6.6.

**Never:**
- No Random Group Check, Copy Pool result or Copy Verdict (Story 6.3). No Copy Test page, tab, "Run Copy Test" button or route (Story 6.4). No price windows for the real Sample Wallets (Story 6.5). No full Copy Test run on the live Scan (Story 6.6).
- No Wallet, Market or holder list is fetched by the Copy phase. A finished Scan's other results are not changed by it.
- No change to `price_at`, to the price client or to what a stored window means.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Small after part | 60 tested after Positions | Copy Sample is all 60: "priced 60 of 60" | N/A |
| Large after part | 250 tested after Positions | 100 drawn with the Seed: "100 of 250"; the same Seed gives the same 100 whatever order the Positions arrive in; another Seed gives another sample | N/A |
| One buy, no fee | 100 shares bought and held, outcome 1, price 0.60 five minutes after the buy | paid 0.605; Follower PnL $39.50; spent $60.50; Follower Return 65.3% | N/A |
| Part sold before resolution | 100 bought in one fill, 40 held | the fill counts with s = 40 | N/A |
| One fill of three has no price | a Position bought in three fills; the second has no price at 5 minutes but all three have one at 1 minute | left out at 5 minutes and counted there; priced in full at 1 minute | N/A |
| Price close to 1 | price 0.998 at the delay, outcome 1 | paid 1.00 (capped); Follower PnL $0 for that fill | N/A |
| Market with a fee | rate and exponent on the Market | Follower Fee = s · rate · (p(1 − p))^exponent at the price paid; taken off the PnL and added to the money spent | N/A |
| Market with no fee | fees off, or no schedule | Follower Fee 0 | N/A |
| Nothing priced at a delay | no Position has a price at 30 minutes | Follower PnL $0, money spent $0, no Follower Return (never a division by zero); all counted as left out | N/A |
| Who is priced | Passer with 4 after bets; other Wallet with 9; other Wallet with 10 | priced; not priced (no rows, no requests); priced | N/A |
| A new Scan | reaches the end of the Hold-up phase | Copy phase runs; progress "Copy Test: 12 of 300 prices"; results stored when the Scan finishes | N/A |
| Polymarket stops answering in the Copy phase | a price request fails on every try | the job stops, the Scan is not finished; Resume asks only for the windows not yet stored | Resume offered (as today) |
| Finished Scan with no Copy Test | a Copy Test job is queued for it | only the Copy phase runs: no Wallet, Market or holder request; Watchlist and Hold-up results unchanged; Copy results stored and the Scan marked as having a Copy Test | N/A |
| That job stops | outage part-way | the Scan stays finished with no Copy Test; a new Copy Test job goes on from the stored prices | job `stopped` |
| A Copy Test job that may not start | unknown Scan; not finished; data rebuilt; already has a Copy Test; a Scan or Copy Test job is queued or running | nothing is queued | N/A |
| Version 8 file with a finished Scan | opened by the new code | version 9; the Scan is `done` with no Copy Test; results, snapshots and stored prices as before | N/A |

</frozen-after-approval>

## Code Map

- `src/liquidoracle/core/prices.py` -- `price_at`, `fill_windows`, `pack`; reuse, do not change.
- `src/liquidoracle/services/prices.py` -- `plan(store, token, fill_times)` and `fetch(client, store, request)`; the phase's only way to prices.
- `src/liquidoracle/core/holdup.py` -- `MIN_AFTER_BETS`, `group_of`; the pattern for a pure group module.
- `src/liquidoracle/core/rng.py` -- `PURPOSES` (`skilltest` 1, `holdup` 2); add `copysample` 3. A code never changes.
- `src/liquidoracle/core/skilltest.py` -- `real_pnl(PositionSet)`: the one source of Real PnL; use it for a Wallet's own PnL on the priced Positions.
- `src/liquidoracle/records.py` -- `Position` holds no fills: the buy fills are the after snapshot's `TRADE`/`BUY` activity rows of the same condition and token. `Market.fees_enabled`, `fee_rate`, `fee_exponent`. New result records go here (both `core` and `data` name them).
- `src/liquidoracle/services/scan.py` -- `run_scan` (phases; `finish_scan` is called after `hold_up_scan`), `hold_up_members` (how a phase reads frozen after parts: `_snapshot`, `as_of_part`, `parts_position_set`, `between()` per Wallet), the progress message helpers. The Copy phase goes here beside the Hold-up phase: `services/copytest` would import these helpers and `run_scan` would import it back.
- `src/liquidoracle/services/jobs.py` -- `Jobs`, `Worker._run` (dispatch by kind), `_run_scan` (stopped / failed / done handling to share).
- `src/liquidoracle/data/store.py`, `schema.sql` -- `SCHEMA_VERSION = 8`; `_SCAN_TABLES`, `_ADDED_LATER`, `_copy` (shared columns, so a new nullable column needs nothing); `finish_scan(scan_id, groups)`; `_open_scan_job` (kind `scan` only today); `Scan` and its two constructors in `scan()` and `scans()`; `scan_seconds` sums every job of the Scan.
- `src/liquidoracle/data/client.py` -- `FunnelClient`, `PriceClient`; the worker's client must be both.
- `src/liquidoracle/services/scans_page.py` -- `planned_requests(size)` and `estimate` (calibrated on the last finished Scan's time).
- `src/liquidoracle/data/synthetic.py` -- `price_path`: forecaster drifts to the outcome over 240 minutes, speed trader is at the outcome from the first minute; steady sharp has no path. Not changed.
- `tests/test_reference_pnl.py`, `tests/reference/` -- how Story 2.7 kept a helper's calculation and named its source.
- `tests/test_scan_job.py` (schema-change tests, `NEXT_VERSION`), `tests/test_holdup.py` lines 690 to 795 (`run_scan`, `finish_scan` callers), `tests/fake_polymarket.py` (`FakeScan` answers no price request today), `tests/test_prices.py` (how the route check's request is answered in tests).
- `../G44-tokle-data/check_readme_live_scan.py <repo> --db <file>` -- every README number of the live Scan against a database.
- Measured 2026-11-28 on the kept copy: 118 of 200 Wallets have 10 or more after Positions; at most 9,644 Positions to price, about one request per token.

## Tasks & Acceptance

**Execution:**
- [ ] `_bmad-output/planning-artifacts/epics.md`, `ARCHITECTURE-SPINE.md` (AD-5, AD-6, AD-15, source tree), `EXPERIENCE.md` (time estimate), memlogs, `deferred-work.md`, `sprint-status.yaml` -- record the decisions of this spec before any code; 6-2 `in-progress` -- plan first.
- [ ] `tests/reference/follower-pnl-set.json`, `tests/reference/follower-pnl-*` -- the hand-made set (one Market with a fee, three Positions, one bought in three fills, one partly sold, price points) and a fresh helper's worked calculation and notes -- committed before its test.
- [ ] `src/liquidoracle/records.py`, `core/rng.py` -- `FollowerResult` (delay, priced, left out, Follower PnL, money spent, own Real PnL; Follower Return derived) and `CopyResult` (Wallet, after Positions, sampled, flag, the three delays); purpose `copysample`.
- [ ] `src/liquidoracle/core/copytest.py` -- `COPY_DELAYS`, `MAIN_COPY_DELAY`, `SPREAD_ALLOWANCE`, `SAMPLE_SIZE`; `copy_sample`, `buy_fills`, `follower_fee`, `copy_wallet` -- pure.
- [ ] `src/liquidoracle/data/schema.sql`, `data/store.py` -- version 9: `scan.copied_at`, `copy_sample`, `copy_result` (kept at a schema change); `finish_scan(scan_id, groups, copies)`, `save_copy_test`, `copy_results`, `queue_copy_test`; job kind `copy`; one open Scan or Copy Test job at a time.
- [ ] `src/liquidoracle/data/client.py`, `services/scan.py`, `services/jobs.py` -- `ScanClient`; the Copy phase and `run_copy_test`; `Jobs.start_copy_test`; the worker runs kind `copy`.
- [ ] `src/liquidoracle/services/scans_page.py` -- the estimate counts the price requests ([ASSUMPTION] 50 per Wallet, from the measurement above), and calibrates on a last Scan with them only when that Scan has a Copy Test.
- [ ] `tests/test_copytest.py` (new), `tests/test_reference_follower.py` (new), `tests/test_scan_job.py`, `tests/test_store.py`, `tests/test_holdup.py`, `tests/test_scans_page.py`, `tests/fake_polymarket.py` -- every matrix row; the two Synthetic Wallet checks; the reference; determinism under two `PYTHONHASHSEED` values; the version 8 file.
- [ ] `README.md` -- what the Copy phase adds to a Scan and to its time; the Follower Fee's limit.

**Acceptance Criteria:**
- Given the Synthetic Wallets of Story 4.6 copied offline, when their Copy results are computed, then the speed trader's Follower PnL at 5 minutes is at most 0 and the forecaster's at 30 minutes is above 0.
- Given the hand-made set, when the app computes Follower PnL and Follower Return at each Copy Delay, then they equal the helper's numbers to the cent, the test file names the helper as their source, and `git log` shows the helper's files in an earlier commit than the test.
- Given a duplicate of the kept live database, when the new code opens it, then it is at version 9, `check_readme_live_scan.py --db` reports no miss, and one real Passer's Copy Sample is planned, fetched and computed with a second plan needing 0 requests.
- Given an offline Scan run by the worker, when it finishes, then it has Copy results for its priced Wallets and its Watchlist and Hold-up results equal those of the same Scan before this story.
- Given the full test suite with sockets blocked, when it runs, then it passes, and the layer and "only the store runs SQL" tests still hold.

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Design Notes

- Why a Copy phase inside the finishing transaction for a new Scan, and a separate job for a finished one: AD-5 says a Scan is finished only when every phase is done, so a new Scan that stops while fetching prices must stay unfinished and resumable. A Scan that was finished before the phase existed cannot go back to unfinished without hiding its Watchlist, so it keeps its state and only gains rows.
- `scan.copied_at` says a Scan has a Copy Test even when no Wallet was priced; counting rows could not tell "none priced" from "never run". Story 6.3 adds the Random Group Check to the same phase; a Scan copied by this story's code then needs the phase once more, which costs no price request.
- A Wallet's own Real PnL is stored per Copy Delay over the Positions priced at that delay, so the page compares like with like when Positions are left out.
- Offline, a token with no stored points is stored as an empty window (Story 6.1). Story 6.5 adds points for the real Wallets' tokens, so an `offline.db` that ran a Copy phase before then would never ask for them: recorded in `deferred-work.md` for Story 6.5.

## Verification

**Commands:**
- `uv run pytest` with `CI=true` -- expected: all pass (1,825 before this story, plus the new ones).
- `python -I ../G44-tokle-data/check_readme_live_scan.py . --db <duplicate>` after the new `Store` has opened the duplicate -- expected: no MISS.
- `git log --oneline -- tests/reference/follower-pnl-set.json tests/test_reference_follower.py` -- expected: the reference commit is older than the test's.
- `git diff main --stat -- src/liquidoracle/web src/liquidoracle/core/prices.py src/liquidoracle/data/polymarket.py` -- expected: empty.
