---
title: 'Story 6.2: Follower PnL'
type: 'feature'
created: '2026-11-28'
status: 'done'
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
- An unexpected error in the Copy phase of a new Scan (a bug, not an outage) does not fail the Scan: it is logged and the Scan finishes without a Copy Test, which a Copy Test job can add later (Edvard, 2026-11-28, after the review; rejected: failing the Scan like any other phase).
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
| A bug in the Copy phase of a new Scan | an unexpected error while the phase runs | the Scan finishes with its Watchlist and Hold-up results and no Copy Test; a Copy Test job can give it one later (Edvard, 2026-11-28, after the review) | error logged; the job is `done` |
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
- [x] `_bmad-output/planning-artifacts/epics.md`, `ARCHITECTURE-SPINE.md` (AD-5, AD-6, AD-15, source tree), `EXPERIENCE.md` (time estimate), memlogs, `deferred-work.md`, `sprint-status.yaml` -- record the decisions of this spec before any code; 6-2 `in-progress` -- plan first.
- [x] `tests/reference/follower-pnl-set.json`, `tests/reference/follower-pnl-*` -- the hand-made set (one Market with a fee, three Positions, one bought in three fills, one partly sold, price points) and a fresh helper's worked calculation and notes -- committed before its test.
- [x] `src/liquidoracle/records.py`, `core/rng.py` -- `FollowerResult` (delay, priced, left out, Follower PnL, money spent, own Real PnL; Follower Return derived) and `CopyResult` (Wallet, after Positions, sampled, flag, the three delays); purpose `copysample`.
- [x] `src/liquidoracle/core/copytest.py` -- `COPY_DELAYS`, `MAIN_COPY_DELAY`, `SPREAD_ALLOWANCE`, `SAMPLE_SIZE`; `copy_sample`, `buy_fills`, `follower_fee`, `copy_wallet` -- pure.
- [x] `src/liquidoracle/data/schema.sql`, `data/store.py` -- version 9: `scan.copied_at`, `copy_sample`, `copy_result` (kept at a schema change); `finish_scan(scan_id, groups, copies)`, `save_copy_test`, `copy_results`, `queue_copy_test`; job kind `copy`; one open Scan or Copy Test job at a time.
- [x] `src/liquidoracle/data/client.py`, `services/scan.py`, `services/jobs.py` -- `ScanClient`; the Copy phase and `run_copy_test`; `Jobs.start_copy_test`; the worker runs kind `copy`.
- [x] `src/liquidoracle/services/scans_page.py` -- the estimate counts the price requests ([ASSUMPTION] 50 per Wallet, from the measurement above), and calibrates on a last Scan with them only when that Scan has a Copy Test.
- [x] `tests/test_copytest.py` (new), `tests/test_reference_follower.py` (new), `tests/test_scan_job.py`, `tests/test_store.py`, `tests/test_holdup.py`, `tests/test_scans_page.py`, `tests/fake_polymarket.py` -- every matrix row; the two Synthetic Wallet checks; the reference; determinism under two `PYTHONHASHSEED` values; the version 8 file.
- [x] `README.md` -- what the Copy phase adds to a Scan and to its time; the Follower Fee's limit.

**Acceptance Criteria:**
- Given the Synthetic Wallets of Story 4.6 copied offline, when their Copy results are computed, then the speed trader's Follower PnL at 5 minutes is at most 0 and the forecaster's at 30 minutes is above 0.
- Given the hand-made set, when the app computes Follower PnL and Follower Return at each Copy Delay, then they equal the helper's numbers to the cent, the test file names the helper as their source, and `git log` shows the helper's files in an earlier commit than the test.
- Given a duplicate of the kept live database, when the new code opens it, then it is at version 9, `check_readme_live_scan.py --db` reports no miss, and one real Passer's Copy Sample is planned, fetched and computed with a second plan needing 0 requests.
- Given an offline Scan run by the worker, when it finishes, then it has Copy results for its priced Wallets and its Watchlist and Hold-up results equal those of the same Scan before this story.
- Given the full test suite with sockets blocked, when it runs, then it passes, and the layer and "only the store runs SQL" tests still hold.

## Implementation Notes

- Built directly from the spec by the main session. One fresh helper made the reference calculation; helpers are otherwise for the review only (Edvard).
- **Order of the work, as the history shows it:** the plan (d09e895), then the reference (52f0854: the set, the field note and the helper's script, CSV and notes), then the code and tests. The app's Copy Test code was first run on the set after 52f0854 existed: its numbers equalled the helper's at all three delays on that first run (Follower PnL $232.07, $220.16, $148.55; Real PnL $238.12), so nothing in the app or the reference was changed to make them meet.
- **The helper's readings** (in `tests/reference/follower-pnl-notes.md`), all of which the app shares: a partly sold Position's held shares are split over its fills in proportion to their size; the Follower Fee is charged on the price paid (with the Spread Allowance and the cap), so a capped fill pays no fee; the exponent is applied as (p(1 − p))^exponent. The helper flagged the first as the only reading that moves the result by more than cents (taking the sell off the first or the last fill instead): the Glossary's "that fill's share of the shares held at resolution" does not say how a sell is spread. The app's reading is the one FR-3 implies (a partly sold Position is tested at the Entry Price over all its buys).
- New: `core/copytest.py` (`is_priced`, `copy_sample`, `buy_fills`, `fill_times`, `follower_fee`, `follow`, `copy_result`), `tests/test_copytest.py`, `tests/test_reference_follower.py`, `tests/reference/follower-pnl-*`. `records.py`: `FollowerResult`, `CopyResult`. `core/rng.py`: purpose `copysample`, code 3. `services/scan.py`: `CopyWallet`, `copy_wallets`, `copy_scan`, `run_copy_test`, the phase name `copy` and its progress text. `services/jobs.py`: `Jobs.start_copy_test`; the worker runs kind `copy` through the same stop and fail handling as a Scan. `data/client.py`: `ScanClient`. Schema 9: `scan.copied_at`, `copy_sample`, `copy_result`; `Store.finish_scan(scan_id, groups, copies)`, `save_copy_test`, `copy_results`, `queue_copy_test`, `Scan.copied`.
- **A Passer with no after part** (it stopped betting, or Polymarket refused its after part) still gets a row, "priced 0 of 0", so FR-18a's "for each Before-Cut-off Passer" holds; it costs no request.
- **The progress count** is every price request the samples need, with those already stored counted as done, so a resumed run goes on at "50 of 214" and not at "0 of 164". While the Copy Samples are drawn, before the requests can be counted, the bar says "Copy Test".
- **The job kind is `copy`, the store's constant is `COPY_TEST`**; `COPY` in `services/scan.py` is the phase's name. A Copy Test job is the Scan's latest job, so the Scans page shows it as the running work and blocks Start Scan through the code that already does that for a Scan; the Scan's row still says Finished. No template or route changed.
- **The time estimate.** With 50 price requests per Wallet the form's example for 200 Wallets reads "about 2.5 hours at 5 requests per second" (it was "about 2 hours"); EXPERIENCE.md's example sentence follows. A last Scan without a Copy Test is calibrated without the price requests it never made (test: 12 hours, where counting them would say 9.5).
- `tests/fake_polymarket.py`: `FakeScan` now answers the old price route (the route check's request with one-minute points; any other token from `prices`, or `price_answer`), because every Scan run on it now reaches the Copy phase.
- Existing tests changed only where they named what this story changes: the schema version and table list, the last progress steps of a Scan, `finish_scan`'s arguments, and the estimate's numbers.
- **The duplicate of the real database (2026-11-28).** A copy of the kept `live-scan-200-cutoff-2025-07-01.db` (SHA-256 checked before and after: unchanged) was opened by the new `Store`: version 7 to 9 in 64 seconds, while the test suite was running; 1.14 GB to 2.27 GB. Both Scans are `done`, not `data_rebuilt` and have no Copy Test; the row counts of the eleven kept tables are equal and the six scan tables are identical row for row; `quick_check` ok. `check_readme_live_scan.py --db <duplicate>`: no MISS.
- **One real Passer, live, counts only.** On that duplicate, the Passer with the fewest after bets that still has 10 (0x034f01): priced 32 of 32; 32 tokens, 175 buy fills, 36 price requests, answered by the old route in 7 seconds; planned again: 0 requests. Priced 32, 31 and 31 Positions at 1, 5 and 30 minutes (1 left out at the two longer delays); 27 of the 32 are in a Market with a fee; every delay has a Follower Return. Its Follower numbers were computed and not printed or read. The nine Passers have 32, 0, 330, 1,377, 713, 237, 0, 517 and 955 tested after Positions.
- For Edvard before the app is next started on `instance/live.db`: the first start converts it once from version 7 to 9 (about a minute, a log line says so), and the file about doubles. The kept copy stays as it is.

- **Where the task lines above differ from what was built** (edge-case review; the lines are not edited): the reference set has two Markets with a fee, not one, because a Market has at most two Positions of one Wallet (`epics.md` says so); and `core/copytest.py` has no `copy_wallet`: its functions are `is_priced`, `copy_sample`, `buy_fills`, `fill_times`, `follower_fee`, `follow` and `copy_result`, all pure, while `copy_wallets` in `services/scan.py` reads the store.
- **My own planted bugs (before the review).** 46 single-line bugs planted one at a time in the new code: 42 caught at once; 3 survived and got tests (a Passer whose after part was refused got no row; the "not fully read" flag was dropped; `run_copy_test` did the whole phase before refusing a Scan that has a Copy Test); 1 cannot change a result (skipping an unpriced fill instead of stopping at it: the Position is left out either way).
- **After the review (2026-11-28).** Three helpers read the diff: 26 findings (blind hunter 15, verification gap 5, edge cases 6). 21 led to fixes, 3 were rejected, 1 is recorded for Story 6.3, and 1 goes to Edvard unbuilt (below). None found a wrong Follower number. The real ones:
  - **The time estimate and Copy Test jobs** (all three helpers). Every job of a Scan counted in its time, so a stopped Copy Test job on a Scan that still had no Copy Test made the pace look slower, and one the app was closed on made the Scan's own time "unknown" for good. Now a Scan's own runs always count, and its Copy Test jobs count only once it has its Copy Test and their time is known (`Store.scan_seconds(kind=)`, `ScansPage._pace`).
  - **Two Wallets holding the same token were never run through the phase** (two helpers), though that is the normal case live. A reviewer showed a one-line bug (the last Wallet's buy times replacing the first's) that every test passed. A test now plants two Wallets that bought the same 100 tokens six hours apart.
  - **The plan still said the rejected rule** in FR-18c ("a buy ... is left out") and in three docstrings; the Glossary's fee formula had no exponent; and how a sell is spread over a Position's buy fills was written nowhere, although the helper had named it as the one reading that moves the result. All three are now in the Glossary, FR-18a, FR-18c and `epics.md`.
  - **A copy time after the Market closed** had no rule and no test. The plan as written gives one (priced if a price was recorded then, else left out); it is now said in `epics.md` and the code, with a test, and named as a question for Story 6.3 or 6.6.
  - **The Follower Fee at the cap.** With an exponent of 0 the fee at a price of exactly 1 would have been the full rate, and a negative exponent would have ended the job with a division by zero. Every Market in the Sample Dataset has exponent 1; the guard is one line.
  - **Tests that proved less than they said:** a `copied_at` compared with itself; the version 8 test claimed "asks for prices only" while nothing was asked (now the stored prices are removed first and every call is checked); and the fake Polymarket's two price hooks were unused (now a live-client Scan prices one real Position, and a 503 on the price route stops the Scan in the Copy phase).
  - README: one sentence still said the Copy Test "is not built"; the real-database proof now says nothing in the app can start the job yet and points to the AI log; the reference bullet says it covers the arithmetic only.
- **Put to Edvard (edge-case review), and built after his answer:** an unexpected error (a bug, not an outage) in the Copy phase of a new Scan fails the job, and a failed job has no Resume (AD-5), so the Scan is never finished although its Watchlist and Hold-up results were already worked out. This is AD-5's rule for every phase and what the approved spec says ("stored in the transaction that finishes it"). The alternative: on such an error finish the Scan without a Copy Test, log it, and let the Copy Test job give it one later. It changes the approved rule, so it was his call. **He chose the alternative** ("b"): `scan._copy_or_none`, `finish_scan(..., None)`, a new matrix row, AD-5 and `epics.md`; an outage still stops the job. A test plants a bug in the phase of a new Scan and then gives the Scan its Copy Test from the job.
- **Edvard also confirmed the two readings the AI wrote into the plan during the review** ("1 yes 2 yes"): a partly sold Position's held shares are split over its buy fills in proportion to their size, and a copy time after the Market closed has no rule of its own.
- **Nine more planted bugs** for the review's fixes and for Edvard's change, all caught. In all 55 planted, 54 caught, 1 without effect.

## Spec Change Log

- **2026-11-28, after review pass 1, by Edvard's decision ("b"), no loopback.** Finding EC4 (an unexpected error in the Copy phase of a new Scan failed the job, and a failed job has no Resume, so a Scan was lost at its last step with its Watchlist and Hold-up results already worked out). Amended inside the frozen block, by the human's renegotiation: a new Always line and a new matrix row "A bug in the Copy phase of a new Scan" say the error is logged and the Scan finishes without a Copy Test, which a Copy Test job can add later. Known-bad state avoided: a 2 h 45 min live Scan that cannot be finished or resumed because of a bug in the one phase that reads data the app has seen least of. KEEP: an outage in the Copy phase still stops the job with Resume and the Scan stays unfinished; an error in any earlier phase still fails the job (AD-5); in the normal case the Copy results are stored in the transaction that finishes the Scan; an empty Copy Test (no Wallet priced) is still a Copy Test, told apart from none by `copied_at`.

## Review Triage Log

Pass 1 (2026-11-28). BH = blind hunter, VG = verification gap (VG3 to VG5 are its "other findings"), EC = edge-case hunter.

| # | Finding | Verdict | Evidence and route |
|---|---------|---------|--------------------|
| BH1 | FR-18c and three docstrings still say "a buy with no price is left out", the rule Edvard rejected | medium | True: `prd.md` FR-18c, `core/prices.py`, `data/offline.py`, `services/prices.py`. Patched: FR-18a and FR-18c say the whole Position; the three docstrings follow (text only, no behaviour). |
| BH2 | The Glossary's Follower Fee formula has no place for the exponent | low | True; the helper had to guess (its reading 5). Patched: the Glossary shows (p(1 − p))^exponent at the price paid. |
| BH3 | How a sell is spread over a Position's buy fills is decided nowhere in the plan | medium | True: only this spec's notes had it. Patched in the plan (Glossary with an example, `epics.md` with the rejected readings). It is the AI's reading, so it is also put to Edvard. |
| BH4 | README line 145 still says the Copy Test "is not built" | low | True. Patched. |
| BH5 | The estimate's calibration is wrong after a Copy Test job that did not finish | medium | True: `scan_seconds` summed every job of the Scan. Patched: `scan_seconds(kind=)` and `ScansPage._pace`; two tests (stopped, failed, interrupted; a finished job's time joins the pace). |
| BH6 | A stopped, failed or interrupted Copy Test job leaves no trace on the Scans page | low | True, and outside this story (the button and its states are Story 6.4). Patched: the state is added to Story 6.4's list and EXPERIENCE.md, and a test pins what the row shows today. |
| BH7 | The Copy rows hold counts only, not which Positions or Markets were sampled | low | True by design: Story 6.3 computes the shared-Markets count in the phase, where the samples are in memory. Recorded for Story 6.3 in `deferred-work.md`, with what a Scan copied by this story's code needs. |
| BH8 | No rule or test for a copy time at or after the Market's resolution | medium | True: the plan is silent. The plan as written gives one reading (a recorded price is a price). Patched: said in `epics.md` and `follow`'s docstring, with a test of both cases; named as a question for Story 6.3 or 6.6. |
| BH9 | After parts are read twice per run by near-duplicate code; the bar shows "Copy Test" with no count meanwhile | low | The bar: true, AD-5 now says the reads are units for lookups and not counted. A shared loader for the Hold-up and Copy phases is a refactor of working, tested code for no shown fault: rejected. |
| BH10 | No test has two Wallets' samples sharing a token; the `max(...)` of the total is untested | medium | Shared token: true, patched (see VG1). The `max`: a subset of windows never packs into more requests than the whole set, so the branch cannot be reached; it stays as a guard: rejected. |
| BH11 | Two assertions prove less than they say | low | Both true. Patched: `copied_at >= as_of`; the version 8 test removes the stored prices first and checks that every call is a price request. |
| BH12 | The independent reference covers the arithmetic only | low | True (whole minutes, exponent 1, nothing missing). Patched: the test file's docstring and the README say so. |
| BH13 | The README's real-database proof cannot be reproduced from the repo; nothing in `src` calls `start_copy_test` | low | True. Patched: the README says nothing in the app starts the job yet and points to the AI log for the counts. |
| BH14 | The diff leaves out the spec and the AI log; sprint status still says in progress | false | The workflow gives the spec to the edge-case layer alone, the AI log was an unfinished draft, and the sprint status moves when the review ends. All three are committed with the story. |
| BH15 | Small code-quality points (five) | low | `_run_scan` renamed `_run_scan_job`, its docstring names the two functions: patched. A frozen record holding dicts, a bare KeyError on a state that cannot occur, the names `copied` and `COPY_TEST`/`COPY`: no named harm, rejected. |
| VG1 | Two priced Wallets that bought the same token are never run through the Copy phase | medium | Filed as a regression gap with a surviving one-line bug. Patched: `test_fr18a_two_wallets_that_bought_the_same_token_are_both_priced`; the reviewer's bug is now caught. |
| VG2 | The estimate's calibration is never run on a Scan that has a Copy Test job | medium | Filed as a regression gap with disposition defer. Not deferred: the current code already mis-timed it (VG3), so it is patched with BH5. |
| VG3 | A stopped or failed Copy Test job's time is counted while the price requests are not | medium | carried from BH5: patched. |
| VG4 | An interrupted Copy Test job makes the Scan's time unknown for good | medium | carried from BH5: patched. |
| VG5 | `FakeScan.prices` and `price_answer` are documented and never used | low | True. Patched: both are used by two new live-client tests in `test_scan_job.py`. |
| EC1 | Finished Scan with no Copy Test has a stopped or failed Copy Test job | medium | carried from BH5: patched. |
| EC2 | App closed while a Copy Test job of a finished Scan was running | medium | carried from BH5: patched. |
| EC3 | Price paid capped at exactly 1 in a Market whose exponent is 0 or negative | low | True in the formula; no such Market is known (every one in the Sample Dataset has exponent 1). The fix is a direct correction: patched, with a test for four exponents. |
| EC4 | A non-outage error in the Copy phase of a new Scan leaves it failed with no Resume | medium | True, and it was AD-5's rule for every phase and this spec's frozen rule. The fix changes approved behaviour, so it went to Edvard unbuilt; he chose it, and it was built after his answer (Spec Change Log). |
| EC5 | Claim: the task line says "one Market with a fee"; the set has two | low | True. Its fix is an edit of this spec's task line: rejected by the rule; said in the notes. |
| EC6 | Claim: the task line names `copy_wallet` in `core/copytest.py`; there is none | low | True. Rejected by the same rule; said in the notes. |

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

**Outcome (2026-11-28):** the full suite passes with sockets blocked on the final code, 1,887 tests (1,825 before the story), 4 online tests left out as always. The duplicate check reports no MISS; it was run before the review, and the schema file has not changed since. The reference commit (52f0854) is in the history before the test file, which is committed with the code. `web/` and `data/polymarket.py` are unchanged; `core/prices.py` differs by one docstring sentence (the review's BH1: "the buy's whole Position is then left out"), no code.
