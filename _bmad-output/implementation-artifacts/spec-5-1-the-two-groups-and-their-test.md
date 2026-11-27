---
title: 'Story 5.1: The two groups and their test'
type: 'feature'
created: '2026-11-27'
status: 'done'
baseline_commit: '44055cd3003f971b4c1bab837d0d85c7c5c4d663'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-5-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A finished Scan knows which Wallets passed on their bets before the Cut-off Date, but nothing tests whether that skill lasted: no groups, no test on the later bets, no stored result, and no lucky-streak Synthetic Wallets to check such a test against (FR-17, FR-13).

**Approach:** After a Scan's Skill Tests, a new Hold-up phase forms the Before-Cut-off Passers and the Comparison Group from the stored `scan_before` results only, pools each group's after-part bets, runs the existing Skill Test on each pool with one draw per Market shared by all its Wallets, and stores both results as `holdup_after`. The generator gains the lucky-streak group, and the FR-17 checks are added.

## Boundaries & Constraints

**Always:**
- **Groups (FR-17):** from the Scan's stored `scan_before` results: *Skilled (high confidence)* = Passers; *Likely skilled* or *No evidence of skill* = Comparison Group; *Not enough data* = neither. No after-part row and no `scan_whole` result is read to form them.
- **After bets:** a Wallet's after part is its frozen after snapshot, cut to the Scan's as-of time, through the one builder. It counts in its group with at least `MIN_AFTER_BETS` = 10 tested Positions `[ASSUMPTION]`, the same rule in both groups; otherwise it is dropped (also when it has no after part).
- **Each group's result:** Wallets in the group, Wallets dropped, Wallets not fully read (members whose before or after part was not fully read), Resolved Positions counted (tested, pooled), Real PnL (tested and Slivers), p-value, Verdict. Fewer than 30 pooled tested Positions: *Not enough data*, no p-value.
- **Pooled test (AD-20, AD-15):** the counted Wallets in address order, their Position sets pooled and run through `skill_test`; the random unit is the test (purpose `holdup`, id = the group's name), so every Wallet shares the per-Market and per-event draws. Every existing golden count stays the same.
- **Dropped-share flag:** set when the two groups' dropped shares differ by more than 20 percentage points `[ASSUMPTION]`; not at exactly 20, and not when a group has no Wallets. Derived from the stored counts.
- **Stored (AD-22):** one row per Scan and group, scope `holdup_after`, with `scan_id`, cut-off and Seed, written in the transaction that finishes the Scan: a Scan is `done` only with its Hold-up stored. Schema version 7; Scans are kept through the change. Job phase `holdup`, message "Hold-up Test". A resumed Scan gives the identical result.
- **Big pools:** Simulations are drawn in smaller blocks when a pool is large, giving the same numbers with bounded memory (a live Comparison Group can hold 100,000 bets).
- **Lucky streak (FR-13):** 1,000 Wallets from the coin-flipper rules with their own draws: 100 bets before the Cut-off Date and 100 bought from it on, one a day, at prices of 10 to 90 cents with outcomes drawn at the price. The coin-flippers' files and golden results do not change.
- **Decision Q1 (Edvard, 2026-11-27, AI rec a): the lucky-streak Wallets are for the checks only.** The tests build them from the generator; nothing writes them to disk (changed by Edvard after the review, 2026-11-27; Spec Change Log); `load-sample` does not load them and they hold no anchor bets, so they are not in the offline app or its Scan. Rejected: in the offline Scan (about 990 would join the Comparison Group and drown the real Wallets that Story 5.2's README result is about; load and Scan about twice as long); a picked handful (needs a pick rule in the generator).
- **The offline warning stays (Edvard, 2026-11-27, his own call).** Before locking Q1 he asked what happens to the coin-flippers already in the Scan. Measured: they have no bets after the Cut-off Date, so 6 are Passers and 994 are in the Comparison Group and all 1,000 are dropped; offline the Passers are 10 Wallets with 7 dropped (70%), the Comparison Group about 999 with about 995 dropped, and the dropped-share flag is set. His decision: the warning is right (those Wallets did stop betting), the rule is not bent to hide it, and **Story 5.2 must say why it shows offline, so it does not look like a bug** (written into epics 5.2 with this story's plan changes).
- **Checks:** steady sharp is *Skilled (high confidence)* on its after part; the lucky-streak Wallets rated *Skilled (high confidence)* before are *No evidence of skill* on their pooled after part; 60% against 10% dropped sets the flag, equal shares do not; 7 coin-flipper Passers on the same side of the same 40 Markets get p < 0.05 in at most 7% of the planted runs (`slow`: 1,000 on CI Linux 3.14, 100 elsewhere); changing after-part outcomes never changes a group; a Wallet *Skilled* only on `scan_whole` is not a Passer.
- **Spec kept whole (Edvard, 2026-11-27, AI rec)** at about 2,000 tokens. Helpers for review only (Edvard, 2026-11-27, AI rec).
- Plan first (epics 5.1, AD-14, AD-15, AD-22, PRD decision log, memlogs). Read-only, network-blocked tests, each naming its FR or AD.

**Never:** no Hold-up page, tab, route or template and no README result (Story 5.2); no Copy Test; no change to `positions_near`, the Position builder, the `scan_before` and `scan_whole` results, the coin-flippers or `sample_data/real/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Scan finishes | Skill Tests done | two `holdup_after` rows stored, Scan `done` | N/A |
| No Passers | no Wallet *Skilled* before | Passers row: 0 Wallets, *Not enough data*; no flag | N/A |
| Too few after bets | Wallet with 9 tested after Positions / with 10 | dropped / counted | N/A |
| No after part | after part refused or never read | dropped, and counted as not fully read when flagged | N/A |
| Small pool | 29 pooled tested Positions / 30 | *Not enough data* with its counts / a Verdict | N/A |
| Shared Market | two Passers hold the same token | they win and lose together in every Simulation | N/A |
| Interrupted | app closed during the Hold-up phase | Resume recomputes it; same rows as an uninterrupted run | N/A |
| Offline Scan | the loaded Sample Dataset, default date | Passers 10 Wallets, 7 dropped; nearly all of the Comparison Group dropped; flag set | N/A |
| Older Scan | finished under schema 6 | kept, with no Hold-up rows (Story 5.2 shows no tab for it) | N/A |
| Bad pool | a Market with three outcomes in one pool | the Scan fails | ValueError from the Skill Test's check, job `failed` |

</frozen-after-approval>

## Code Map

- `core/skilltest.py` -- `skill_test(position_set, seed, unit_id, scope)`: add a `purpose` argument passed to `_generator` (default `skilltest`); `_engine` block size `_CHUNK` = 1,000 rows of `rows x Positions` floats: make the rows per block shrink with the pool (same stream, so same numbers). `_ordered` is a stable sort by (`condition_id`, `token_id`): pool in address order. `_engine` may be named only inside this file (rule test).
- `core/rng.py` -- `PURPOSES = {"skilltest": 1}`: add `"holdup": 2`; codes never change.
- `core/holdup.py` (new, pure) -- `MIN_AFTER_BETS`, `DROPPED_GAP`, `PASSERS`, `COMPARISON`, `group_of(verdict)`, `hold_up(members, seed)` -> two `GroupResult`s, `dropped_shares_differ(passers, comparison)`.
- `records.py` -- new `GroupResult` (group, verdict, p_value, tested_count, real_pnl, wallets, dropped, not_fully_read); `Verdict`, `PositionSet`.
- `services/scan.py` -- `run_scan`: after `_test_top`, progress `HOLDUP`, then `store.finish_scan(scan_id, groups)`; `hold_up_members` and `hold_up_scan` read `store.scan_results` (`SCAN_BEFORE` for the groups, the results' `not_fully_read` for the count), `store.scan_wallets` (`after_fetch_id`) and `store.snapshot`, and reuse `as_of_part` and `parts_position_set` (the phase sits here, see Implementation Notes).
- `data/store.py`, `data/schema.sql` -- `SCHEMA_VERSION` 6 -> 7; table `group_result`; `_SCAN_TABLES`/`KEPT_TABLES` (the old file has no such table: copy it only when it exists); `finish_scan` writes the rows and advances the step in one `_write()`; `group_results(scan_id)`; `HOLDUP_AFTER`.
- `data/synthetic.py` -- `coin_flipper` (unchanged), `_two_sides`, `CUTOFF`, `_wallet`, `write_coin_flippers`; add `lucky_streak(index)` and its writer. `data` may not import `core` or numpy.
- `__main__.py` -- unchanged in the end: `make_synthetic`, `load_sample` and `offline.SAMPLE_DIRS` never touch the lucky-streak group (Q1, as changed after the review).
- Tests: `tests/test_skilltest.py` (`bet`, `position_set`, `GOLDEN`, the `slow` + `repetitions` pattern at line 211), `tests/test_scan_job.py` (`Rig`, `start`, schema-change tests at 448-555, progress test at 209), `tests/test_store.py`, `tests/test_synthetic.py`, `tests/conftest.py` (`--repetitions`), `tests/test_architecture.py` (every test names an FR/AD).

## Tasks & Acceptance

**Execution:**
- [x] Plan: `epics.md` 5.1 and 5.2 (5.2 explains why the dropped-share warning shows offline), FR-13's lucky-streak row, AD-14, AD-15, AD-22, PRD decision log, `epic-5-context.md`, memlogs -- the decisions before code.
- [x] `core/rng.py`, `core/skilltest.py` -- `holdup` purpose; blocks sized to the pool -- AD-15, AD-20.
- [x] `records.py`, `core/holdup.py` -- groups, drop rule, pooled test, flag -- FR-17.
- [x] `data/schema.sql`, `data/store.py` -- `group_result`, version 7, kept through schema changes -- AD-22, AD-6.
- [x] `services/scan.py` -- the Hold-up phase of the Scan job -- AD-5, AD-19.
- [x] `data/synthetic.py` -- the lucky-streak group -- FR-13.
- [x] Tests: `tests/test_holdup.py` (every matrix row, the checks, the planted `slow` run, the leak tests), plus store, scan job, synthetic and skilltest additions; README test instructions if a command changes.

**Acceptance Criteria:**
- Given an offline Scan of the loaded Sample Dataset, when it finishes, then its two `holdup_after` rows are stored and read back by their full key.
- Given the same Scan run twice, or interrupted and resumed, then the stored rows are identical.
- Given the whole suite with `CI=true`, then every test passes, 0 skipped, and every earlier golden count is unchanged.

## Implementation Notes

- Built in this session without a helper (Edvard chose helpers for review only). Plan edits first: PRD decision log (new 2026-11-27 section), FR-13's lucky-streak row, epics 5.1 (open items) and 5.2 (a new line: it says why the dropped-share warning shows offline), AD-14, AD-15, AD-22, the new `epic-5-context.md`, PRD and architecture memlogs. The UX documents are untouched (no page changes).
- **Deviation from the Code Map: no `services/holdup.py` yet.** The phase (`hold_up_members`, `hold_up_scan`) sits in `services/scan.py` beside `_test_top`: it needs that module's `as_of_part` and `parts_position_set`, and `run_scan` needs the phase, so a separate module would import in a circle. `services/holdup.py` arrives with Story 5.2's page, which only reads the stored rows. `hold_up_members` is public because Epic 6's Copy Test needs the same Passers.
- `core/holdup.py`: `group_of`, `counts`, `hold_up`, `dropped_shares_differ` (whole-number arithmetic, so exactly 20 points is never "more"; floats would call 90% against 70% more than 20), `Member`. The pool is one `PositionSet` of the counted Wallets' tested Positions and Slivers (not their left-out rows, which stay with each Wallet's own result), run through `skill_test(..., purpose="holdup", unit_id=<group>)`.
- `core/skilltest.py`: `purpose` argument on `skill_test`/`_engine`/`_generator`; `_block_rows` (at most 2,000,000 draws held at once; up to 2,000 Positions still 1,000 rows, so every Wallet's own test is drawn exactly as before). `core/rng.py`: purpose `holdup` = 2.
- `data/schema.sql`, `data/store.py`: table `group_result`, version 7, `finish_scan(scan_id, groups)` (rows and the `done` step in one transaction), `group_results`, `HOLDUP_AFTER`; `_ADDED_LATER` lets a version 6 file keep its Scans (it has no such table).
- `data/synthetic.py`: `_fair_bet` (the coin-flipper rule, shared), `lucky_streak`, `lucky_streaks`, `write_lucky_streaks`; `coin_flipper` output unchanged (golden counts and committed files identical). `__main__.make_synthetic` writes the group; `load_sample` and `offline.SAMPLE_DIRS` untouched.
- **Measured (2026-11-27).** Lucky streaks: 7 of the 1,000 are *Skilled (high confidence)* before the cut-off (indices 201, 259, 543, 817, 861, 889, 985; 27 more *Likely skilled*); their 700 pooled after bets: *No evidence of skill*, p = 0.62. All 1,000 as one planted Scan: Comparison Group 993 Wallets, 99,300 bets, p = 0.51, tested in 22 s with bounded memory. Planted shared-Market runs: p < 0.05 in 6 of the first 100 and 37 of 1,000 (limit 7%); counted as 280 separate bets instead, 28 of 100 and 249 of 1,000.
- **Real app check (2026-11-27):** `load-sample` (1,018 Wallets, 25 s) moved `instance/offline.db` to version 7 and kept the older Scan, with no Hold-up rows. A new offline Scan through `ScansPage` and the `Worker`: 51 s (ranking 12 s, Skill Tests 39 s, Hold-up 0.3 s), "Hold-up Test" as its last step. Stored rows: **Passers** 10 Wallets, 7 dropped (sharp trader and 6 coin-flippers), 300 bets, Real PnL $6,000, p = 0.0001, *Skilled (high confidence)*. **Comparison Group** 999 Wallets, 996 dropped (994 coin-flippers; 0x94884d with 9 after bets, 0xcf0d7f with 4), 409 bets from 3 real Wallets (0x0f4b0a 89, 0x736483 13, 0xd3a6e5 307), Real PnL -$19,217, p = 0.56, *No evidence of skill*. Dropped shares 70% against 99.7%: the flag is set, as Edvard decided it should be. No Wallet in either group is flagged not fully read (0x729806 has *Not enough data* before, so it is in neither).
- **Was open for Edvard, now settled:** the first build had `make-synthetic` write about 200 MB of lucky-streak files to `instance/` that nothing reads (the tests build the Wallets from the generator). He had them dropped after the review (Spec Change Log): `write_lucky_streaks`, `LUCKY_STREAK_DIR` and the command's two lines are gone, so the `data/synthetic.py` and `__main__.py` lines above describe the first build.
- Tests: `tests/test_holdup.py` (35 test functions before the review, 39 and 57 cases after it: groups, the 10 and 30 rules, the flag, the pooled draw, purposes, block sizes, three golden counts, the FR-17 checks, two `slow` checks, the Scan phase through real offline Scans of planted Wallets, the store's transaction, the offline Scan with 40 coin-flippers and the committed real Wallets). Changed: `test_scan_job.py` (schema-change tests now use the next version; two new: group rows kept, a version 6 file kept without them; the progress test ends on the Hold-up step), `test_store.py`, `test_synthetic.py`, `test_skilltest.py` (the signature pin now lists `purpose` and checks 29 bets give *Not enough data* under every purpose).
- Planted bugs: 30 planted one at a time, 27 caught at once. One was a real gap (the Scan's Seed could be replaced by 0 unnoticed; a test now pins it). Two change nothing a test could see: the flag's empty-group guard was dead code (both sides of the comparison are 0 anyway) and was removed; pooling without the address sort gives the same result, because the engine's sums do not depend on order (the sort stays, as AD-15 asks).
- AI slips: the first `finish`-less version of a test popped from an empty list; a long bash heredoc broke again (switched to Write + run file, as the handoff says); the guessed golden count for the shared-Market run was wrong (pinned from the first run instead); one full-suite run had a browser test fail on `net::ERR_NO_BUFFER_SPACE` (Windows ran out of socket buffers; all 33 tests of that file pass on a re-run and in the next full run).
- Review pass 1 patches (2026-11-27): `records.py` now holds `PASSERS`, `COMPARISON`, `HOLDUP_GROUPS` and `HOLDUP_AFTER` (one copy for `core` and `data`; the unused `GROUPS` and the second scope string are gone). `finish_scan` takes exactly the two groups once each, moves the step first and then inserts, so a Scan at another step gets the plain "not at step" error and a failed insert rolls the step back. `group_results` returns the Passers first, as `hold_up` does. `skill_test` refuses an unknown purpose before the 30-bet check. The last progress write comes before `finish_scan`. The `make-synthetic` message no longer says the files are for the tests. Tests added or tightened: the rollback, the wrong group lists, `between` in the phase (through `run_scan` too), a Scan with Seed 7, a negative-risk event pooled across two Wallets, opposite sides at 0.50, 0.70 and 0.30, an unknown purpose at 0, 29 and 30 bets, the pooled path in the two-`PYTHONHASHSEED` check, and the offline Scan's real Comparison Group pinned (409 bets, 5,573 Simulations at or above, Real PnL -$19,216.76, the five real Wallets' after-bet counts). The reviewers' eight planted bugs each fail a test now.
- Plan documents corrected after the review: AD-5 (a group's pooled test is one unit: 22 s for 99,300 bets), AD-22 (the two rows, their order, a failed phase), the spine's module tree and FR-17 row and the architecture memlog (the phase is in `services/scan.py`), the decision log (memory wording; the limits for Story 5.2), FR-13's lucky-streak row (7 of 1,000 by luck, not "by construction"), epics 5.2 (no real Passer; the Comparison Group rests on 3 real Wallets), `epic-5-context.md`.

## Spec Change Log
- **2026-11-27, after review pass 1 (Edvard changed the frozen intent).** Trigger: review finding BH11 and the AI's own measurement after building: writing the lucky-streak Wallets as files costs about 200 MB in `instance/` and 8 seconds in every test run, and nothing reads the files (the tests build the Wallets from the generator). Reported to Edvard with the recommendation to drop them; he decided "drop the files". Amended: Decision Q1's sentence in the frozen block (no file writing), the Code Map line for `__main__.py`, one task line, one Verification line. Code: `write_lucky_streaks`, `LUCKY_STREAK_DIR` and the two `make-synthetic` lines removed; the README sentence, `test_synthetic.py` and one `test_holdup.py` test changed to say and check that nothing is written. Plan: AD-14, FR-13's row, epics 5.1, the decision log, `epic-5-context.md`, memlogs. Known-bad state avoided: 200 MB of files with no reader, and a plan promising them. KEEP: the generator's `lucky_streak`, `lucky_streaks` and `LUCKY_STREAKS`, the seven listed Passers, and every FR-17 check are unchanged.

## Review Triage Log

Pass 1 (2026-11-27): three reviewers (blind hunter BH, edge case hunter EC, verification gap VG), 23 findings; 0 intent gaps, 0 bad spec. 15 patched (some in part), 7 rejected, 1 taken to Edvard (BH11); 0 deferred. No reviewer found a wrong result.

| # | Finding | Verdict | Evidence / route |
|---|---------|---------|------------------|
| VG1 | The "one transaction" test never rolls back inserted rows; splitting `finish_scan` into two transactions passed the suite | medium | Pre-verified by a mutation run. **patch**: the test plants a row that makes the insert fail and expects the step back at `ranked`; a Scan at `shortlisted` with rows given is refused with no row left. Planted back: fails. |
| VG2 | No test sees the Hold-up phase call `between()` | medium | Pre-verified. **patch**: `test_ad5_a_waiting_lookup_can_run_between_two_wallets_of_the_holdup_phase` counts 5 calls in phase `holdup` through `run_scan` and 5 from `hold_up_members`. Planted back (no call; not handed on): both fail. |
| VG3 | The Seed test cannot tell the Scan's Seed from the default 44 | medium | Pre-verified. **patch**: the planted Scan runs with Seed 7; result must equal `hold_up(members, seed=7)`, differ from 0, 44 and 8, and the row's Seed is 7. Planted back (`seed=44`): fails. |
| EC1 / BH4 | `finish_scan` stores no rows, one group or an unknown name and still marks the Scan done; the docstring promised more | low | Confirmed (only duplicates were refused). **patch**: exactly the two groups once each, five wrong lists tested. Planted back: fails. |
| BH5 | `GROUPS` unused; the scope string exists twice (`holdup.SCOPE`, `store.HOLDUP_AFTER`) and could drift | low | Confirmed. **patch**: one copy of the names and the scope in `records.py`, used by both layers. |
| BH6 | `hold_up` returns (passers, comparison) but `group_results` returned alphabetical (comparison, passers); Story 5.2 could swap the cards | low | Confirmed; the tests were already working around it. **patch**: `group_results` returns the Passers first; tests unpack directly. Planted back (alphabetical): fails. |
| EC5 | A progress write after `finish_scan` that raised would mark the job failed although the Scan is done | low | Possible (the write can fail on a locked database). **patch**: the last progress write comes before `finish_scan`. |
| EC6 | An unknown purpose with fewer than 30 bets returned *Not enough data* silently | low | Confirmed (the purpose was only read when drawing). **patch**: refused first; test at 0, 29 and 30 bets. Planted back: fails. |
| BH10 | The numbers written into the plan come from a hand run no test reproduces; "995" against the measured 996 | medium | True. The dropped Wallets add nothing to a pool, so the 40-coin-flipper test's Comparison Group is the full Scan's. **patch**: that test pins 409 bets, 5,573 at or above, Real PnL -$19,216.76 and the real Wallets' after-bet counts (4, 9, 13, 89, 307); the parametrised case says 996. The frozen spec's "about 995" was an estimate before the run and stays. |
| BH7 | The both-sides test holds only at 0.50; at 0.70 and 0.70 both sides win in about 40% of draws, the normal case in a pool | low | True, and it is AD-20's rule (each Position keeps its Entry Price as its win chance). **patch**: a test pins 0.50, 0.70 and 0.30 for two Wallets and names the limit. A line in the user-facing limits belongs to Story 5.2's page. |
| BH8 / EC4 | No test pools a negative-risk event across Wallets; in a pool region lengths past 1 wrap, so two Markets of one event can win together | low | The wrap is AD-20's written rule (Story 2.4), now more likely in a pool; reporting such Positions as uncoupled would be a plan change: rejected. **patch** (test only): two Wallets in one event at 0.30 and 0.40 never both win, each at its own price. Planted (events ignored): fails. |
| BH9 | The pooled path is not in the two-`PYTHONHASHSEED` check | low | Confirmed. **patch**: the subprocess script also runs `hold_up` over the small Wallets. |
| BH1 | The offline result has no real Passer, and the plan's limits for Story 5.2 do not say so | low | True and already an open point from Story 4.7; now measured. **patch** (plan): epics 5.2 and the decision log name it, with the 3 real Wallets and the 307 of 409 bets. |
| BH12 | Plan documents put the orchestration in `services/holdup`; the code is in `services/scan.py` | low | Confirmed (context file, spine tree and FR-17 row). **patch** (plan): all three corrected, deviation in the architecture memlog. |
| BH13 | Text drift: "large groups are regenerated by load-sample"; "Pass before by construction"; sprint status `in-progress`; README 90 to 100 MB | low / false | First two confirmed and corrected. Sprint status moves to `review` at presentation (false). The README number was stale (measured 103 MB); said in the commit message. |
| BH14 | Six details: `_ADDED_LATER` not tied to a version; `DROP TABLE IF EXISTS` for every kept table; the version 6 file is made by dropping a table; the refused-after test edits rows; a refused Wallet counts as "stopped betting"; `PURPOSES ==` will fail in Epic 6; docstring "always has them" | low | **patch**: the purposes assert checks the two codes only; the docstring names the older-file exception. Rejected: the first two are harmless on any file this app wrote; schema 7 is schema 6 plus one appended table, so dropping it gives exactly a version 6 file; the edited rows are what `_test_top` stores for a refused after part (`save_results`, `scan_results`); the dropped rule is FR-17's (noted in the decision log). |
| EC2 / BH2 | Each group's pooled test runs with no `between()` and no progress; a very large live Scan could take minutes | low | True: 22 s for 99,300 bets, 0.3 s offline. A lookup waits, nothing breaks, and AD-5 already accepts a long unit behind a big Wallet. A per-block callback into the engine is new surface: rejected. The limit is written into AD-5; watch it on the live Scan (Story 5.3). |
| EC3 / BH2 | Every member's Position set is held at once; `_BLOCK_CELLS` bounds only the draws; the after snapshots are rebuilt | low | True: a few hundred MB only at 500 Wallets with 2,000 later bets each. Rejected (rare, and the fix adds code); the decision log's memory sentence was corrected. Rebuilding is what makes Resume give the same result. |
| BH3 | A failure in the new last phase leaves the Scan unfinished with no Resume, so a complete Watchlist is not shown | low | By AD-5 (a Scan is finished only when every phase is done; `failed` has no Resume) and the approved matrix row "Bad pool". The phase runs the engine and checks each Wallet's own tests already passed, and a binary Market cannot give a pool three outcomes. Rejected; written into AD-22 and told to Edvard. |
| BH11 | `make-synthetic` writes about 200 MB that nothing reads; its test writes 2,000 files on every CI job; the message said "for the tests only" | low | True (199 MB measured from the generator; the test took 8 s). The file writing is in the frozen spec (Decision Q1), so only Edvard can change it: **taken to Edvard** with a recommendation: he had the files dropped (Spec Change Log). |

## Design Notes

- Pooling reuses `skill_test` whole: a pooled `PositionSet` (the tested Positions and Slivers of the counted Wallets put together) gives the 30 minimum, Real PnL, p-value and Verdict from the one engine, so the Hold-up Test cannot drift from the Skill Test.
- The group's name as the random unit id keeps the result a function of the data and the Seed alone, so the same Scan data gives the same result under any `scan_id`.

## Verification

**Commands:**
- `uv run pytest` with `CI=true` -- expected: all pass, 0 skipped.
- Result (2026-11-27, after the files were dropped): 1,636 passed, 0 skipped, 3 deselected, 302 s.
- Result (2026-11-27, after review pass 1): 1,636 passed, 0 skipped, 3 deselected, 310 s; the two `slow` checks with `--repetitions 1000`: passed, 73 s.
- Result (2026-11-27, before review): 1,632 passed, 0 skipped, 3 deselected (the `online` tests), 313 s; the two `slow` checks with `--repetitions 1000`: passed, 125 s.
- `uv run pytest tests/test_holdup.py --repetitions 1000` -- expected: the planted check passes in full.
- `uv run liquidoracle make-synthetic` twice -- expected: identical files, no git diff in `sample_data/synthetic/` (covered by `test_make_synthetic_writes_both_groups`, which compares the written small Wallets with the committed bytes; the command writes nothing for the lucky streaks).

**Manual checks:**
- `load-sample`, `run --offline`, start a Scan: the progress names "Hold-up Test" and the Scan finishes; read the two stored rows.
