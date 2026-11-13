---
title: 'Story 1.3: Synthetic Wallets with known answers'
type: 'feature'
created: '2026-11-13'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '8e55120f1d4ca2d79babeb449ee56c3b96ac19e9'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Skill Test (Story 1.4) must be checked against answers fixed before it exists. No made-up Wallets, no Sample Dataset file format and no `make-synthetic` command exist yet.

**Approach:** Add one serializer for Sample Dataset files (AD-14) and a generator, `data/synthetic.py`, that writes the stage 1 Synthetic Wallets of FR-13 as fills first, then derives each Wallet's Markets, positions lists and price paths from them. Commit the small Wallets plus a hand-written `expected.json` with each type's intended bets and FR-13 answer. The 1,000 coin-flippers go to `instance/` only.

## Boundaries & Constraints

**Always:**
- Types and counts: hand-check 10 at 0.50, all won; favourite buyer 100 at 0.90, exactly 90 won; sharp trader 100 at 0.50, exactly 70 won; thin wallet 29 resolved; stop-loss trader 100 at 0.50, no edge; coin-flippers 1,000 × 100, price uniform in whole cents 0.10–0.90, won when a draw < price.
- 100 shares per bet, fees off, every bet in its own two-outcome Market, resolved, all times before the default Cut-off Date (2025-07-01).
- A fixed generator constant, never the `SEED` setting; never `random`, numpy's global state or `hash()`.
- Output is byte-identical on every run, OS and Python version: sorted keys, LF line endings, written as bytes.
- `expected.json` is written by hand, never by the generator.
- Every test names its FR or AD.

**Never:**
- No Skill Test, Verdict, store, `OfflineClient` or `load-sample` code (Stories 1.4, 1.6).
- No stage 2/3 types, anchor Markets or Copy Test price windows.
- No coin-flipper file in the repository. No `git add .`, no merge, no `gh`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Hand-check via builder | its file | 10 tested, all o = 1, p = 0.50, Real PnL $500.00 | N/A |
| Sharp trader | its file | 100 tested, 70 won, Real PnL $2,000.00 | N/A |
| Favourite buyer | its file | 100 tested at 0.90, 90 won, Real PnL $0.00 | N/A |
| Thin wallet | its file | 29 tested | N/A |
| Stop-loss trader | its file | 33 tested, all won; 67 "sold before resolution" at 0.25, each Exit PnL −$25.00 (17 of them in Markets their side won) | N/A |
| Coin-flipper | any one | 100 tested, prices in whole cents within [0.10, 0.90]; total wins over 100 Wallets within 4 SD of Σp | N/A |
| Run twice | `make-synthetic` | identical bytes; committed files equal fresh output | N/A |
| Round trip | load(dump(w)) | equals w | N/A |

**Decisions (Edvard, 2026-11-13):**
- Stop-loss trader: fair price path with a stop at 0.25 (AI's option A). Of 100 bets at 0.50, 67 fall to 0.25 and are sold there, 17 of them in Markets their side later won; 33 are held and all win. Total −$25, about zero, but the held bets alone read *Skilled (high confidence)*: the FR-11 limit. Rejected: selling only the losers at 0.30 (the trader would "know" them).
- Generator randomness: uniform draws from sha256 of (constant, Wallet, bet, purpose), standard library only (AI's option A), because the spine puts the generator in `data/`, whose import rule bans numpy. Files never change with a numpy upgrade. AD-15 gets a note. Rejected: allowing numpy in `data`.
- Subagents for the review only, as in Stories 1.1 and 1.2.

</frozen-after-approval>

## Code Map

- `src/liquidoracle/records.py` -- add `ListedPosition` (condition_id, token_id, status CLOSED/OPEN, shares_bought, first_entry_at) and `SampleWallet` (address, name, activity, positions, markets, prices). Stdlib only.
- `src/liquidoracle/core/positions.py` -- `build_positions(fills, markets)`; reuse, do not change.
- `src/liquidoracle/__main__.py` -- `make-synthetic` stub prints "not built yet"; replace it.
- `tests/test_architecture.py` -- `data` may import records, settings, requests, anthropic; every test must name an FR/AD.
- `.gitignore` -- `instance/` already ignored. No `.gitattributes`; local `core.autocrlf=true` would turn committed LF JSON into CRLF.

## Tasks & Acceptance

**Execution:**
- [x] plan first -- epics Story 1.3 gets the stop-loss counts; spine AD-15 note on the sha256 draws and AD-14 names the serializer module; memlog entries -- CLAUDE.md: plan before code.
- [x] `src/liquidoracle/records.py` -- the two types -- AD-10, AD-14.
- [x] `src/liquidoracle/data/sample_json.py` -- `dumps(wallet, compact)` / `loads(text)`, the one serializer -- AD-14.
- [x] `src/liquidoracle/data/synthetic.py` -- one function per type, `small_wallets()`, `coin_flipper(i)`, `write_all(sample_dir, instance_dir)` -- FR-13, AD-14, AD-15.
- [x] `src/liquidoracle/__main__.py` -- `make-synthetic` writes `sample_data/synthetic/*.json` and `instance/synthetic/coin-flippers/` -- FR-13.
- [x] `sample_data/synthetic/expected.json` -- by hand: counts, Real PnL, FR-13 Verdict and p range per type; coin-flipper limits 7% / 2% -- FR-5, FR-6, FR-11, FR-13.
- [x] `.gitattributes` -- `sample_data/**/*.json` as LF -- FR-13.
- [x] `tests/test_synthetic.py` -- the matrix, plus own-Market check and no-coin-flipper-in-repo check -- FR-13, AD-14, AD-15.

**Acceptance Criteria:**
- Given `uv run liquidoracle make-synthetic`, then the five small files and `expected.json` sit in `sample_data/synthetic/`, the 1,000 coin-flippers in `instance/`, and `git status` shows no coin-flipper.
- Given `uv run pytest`, then all tests pass with sockets blocked.

## Implementation Notes

- Implemented directly in the main session; subagents only for the review (Edvard, 2026-11-13).
- Commits: 449a6cd plan, 8266aa6 spec, da430d0 serializer and record types, 8cb019a hand-written `expected.json`, 07b25a0 generator, command, committed Wallets and 33 tests. Full suite 155 passed, 1 deselected; the two slow coin-flipper checks also pass at `--repetitions 1000`.
- `make-synthetic` takes about 2.6 s; committed Wallets about 400 KB; the 1,000 coin-flippers about 87 MB in `instance/` (compact JSON).
- Matrix audit: every row has a passing test in `tests/test_synthetic.py` (`test_wallet_gives_the_intended_bets` for the four exact Wallets, the two stop-loss tests, the two slow coin-flipper tests, `test_two_runs_give_identical_bytes`, `test_committed_files_equal_fresh_output`, `test_serializer_round_trip`).
- Planted bugs, each failed a test: coin-flipper wins at 1 − p (caught only by the price-band check: over all prices 1 − p and p have the same total), price 0.90 never drawn, 16 instead of 17 stop-loss winners sold, held losers not OPEN, CRLF file endings, times after the Cut-off Date, a price path that never falls, a lenient `bool("false")`.
- Not in the plan, added by the AI: `make-synthetic` refuses to run outside the repository folder (no `sample_data/`), so it never scatters files; the serializer refuses unknown or missing keys; the old Story 1.1 test "make-synthetic says not built yet" became a load-sample-only test.
- Choices: the generator picks which bets win with a sha256 ranking, so winners are spread over time, not the first 70.
- Deviation from the task line: `write_all(sample_dir, instance_dir)` became `write_small(root)` and `write_coin_flippers(root, count)`, so Story 1.6's `load-sample` can regenerate the coin-flippers alone.
- After review: 174 passed, 1 deselected (see the triage log).

## Spec Change Log

## Review Triage Log

Review pass 1 (2026-11-13). Three subagent reviewers on the diff since the baseline (the five generated Wallet files left out; they are compared byte for byte by a test): blind (B), edge-case (E) and verification-gap (V).

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | V: coin-flipper prices could stop being uniform and no test would notice | medium | V showed `u*u` (prices lean low, mean 0.36) passes both coin-flipper tests | patch: test counts all 81 cent values over the first 100 coin-flippers (5 SD) |
| 2 | V, B: `read_wallet`'s "names the file" path is untested; a test docstring claims it | low | True: the test called `loads` | patch: tests on a malformed and a non-UTF-8 file |
| 3 | V, E, B: the reader converts wrong types silently (null → "None", 1.9 → 1, true → 1.0, `side: "buy"`, any `status`, `token_ids` as a string) and accepts NaN | medium | Reproduced; the docstring promised strict reading | patch: strict type checks, BUY/SELL and OPEN/CLOSED only, NaN and Infinity refused; 9 new refusal cases |
| 4 | E: `Infinity` in a time field escapes as OverflowError, not ValueError | medium | Reproduced: `json.loads` accepts Infinity, `int(inf)` raises OverflowError | patch: same root cause as #3 |
| 5 | E: `uniform()` can round to exactly 1.0 (64-bit int / 2**64) | low | True for draws within 2**-54 of the top; fix is a direct correction | patch: 53-bit draw; committed files unchanged |
| 6 | E, B: any folder with a `sample_data/` passes the repository check | low | True; direct fix | patch: also requires `pyproject.toml` |
| 7 | E: the git test fails in a zip download or without git | low | True: `git check-ignore` returns 128 outside a checkout | patch: skip with a reason |
| 8 | E: any tracked path containing "coin-flipper" (a log name) would fail the check | low | True; direct fix | patch: checks only `sample_data/` and `instance/` |
| 9 | E: with `--repetitions` 1 the 0.10/0.90 end check can fail | low | True (100 draws from 81 values) | patch: ends checked in the fixed 100-Wallet uniformity test (#1) |
| 10 | B: README still says make-synthetic is not built | medium | True (README line 30); README is graded | patch: README explains the command and the 90 MB in `instance/` |
| 11 | B: stop-loss has no p range; coin-flipper requirements list shorter than the PRD row | low | True | patch: `p_below` 0.01; FR-17, FR-18, FR-22, UJ-3 added |
| 12 | B: the stop-loss total (−$25) exists only as prose | low | True | patch: `total_pnl` in expected.json and tested |
| 13 | B: stop-loss path test does not check the stop price or that held paths stay above it | low | True | patch: sells exactly at 0.25, no point below before the sell, held paths stay above |
| 14 | B: the randomness ban test misses `from liquidoracle import settings`, `os`, `__import__`, and skips `sample_json.py` | medium | True: the alias form passed | patch: all three caught, both modules scanned |
| 15 | B: spine AD-14 does not name the coin-flipper folder; sprint-status time 13:00 does not match the commits (18:09) | low | True; the AI had guessed the time | patch: spine line; time corrected |
| 16 | B: `ListedPosition.status` is a free string | low | Same root as #3 at the reader; `ActivityRow.type`/`side` are plain strings too (Story 1.2 review #20) | patch via #3; no type change |
| 17 | E: `read_wallet` lets FileNotFoundError / PermissionError through | false | A missing file failing loudly with its own error is correct behaviour; nothing calls it on a missing path | rejected |
| 18 | E, B: an OSError (disk full, read-only) in make-synthetic ends in a traceback | low | Real but rare, and the fix is a new guard | rejected |
| 19 | E: no `write_all(sample_dir, instance_dir)` as the spec's task line said | low | Built as `write_small` and `write_coin_flippers` so Story 1.6 can regenerate the coin-flippers alone; noted in Implementation Notes | rejected |
| 20 | E: Market outcomes and price paths come from the bet list, not the fills | false | Fills cannot carry outcomes; AD-14 says the other lists are derived from the fills plus the generator's known answers | rejected |
| 21 | B: no AI log for the session | false | The log is written at the end of the session, after Edvard sees it | rejected |
| 22 | B: coin-flippers have no price paths though FR-13 lists them | false | They are for the Copy Test: epics Story 6.5 adds "the Synthetic Wallets' price paths"; spec Never excludes Copy Test windows | rejected |
| 23 | B: the stop-loss price path is a three-point sketch, not a fair random walk | false | The fairness is in the counts (2 in 3 touch 0.25 from 0.50; 1 in 4 of those win), which the tests check; the path only explains each sell | rejected |
| 24 | B: `_stop_loss_bets` hard-codes 33/17/50 instead of deriving them from the stop | false | Intended: the counts are Edvard's decided answer, fixed in the plan and in expected.json | rejected |
| 25 | B: `test_hand_values_agree_with_the_counts` writes 100, not `synthetic.SHARES` | false | Intended: the hand fixture must not lean on the generator's constant | rejected |
| 26 | V, B: the slow tests use `--repetitions` as a number of coin-flippers | false | Epics Story 1.4 says the coin-flipper check runs on 1,000 on one CI job and 100 elsewhere: the count is the planned meaning | rejected |
| 27 | B: the unmarked make-synthetic test writes all 1,000 coin-flippers each run | low | About 2.5 s; it checks the real command | rejected |
| 28 | B: stale coin-flipper files are never cleared | low | Only matters if the count changes; it is a fixed constant | rejected |

After the patches: 174 passed, 1 deselected; the slow checks pass at `--repetitions 1000`. The reviewers' demonstrations (#1 `u*u` prices, #2 no file name, #14 alias import, #3 NaN and unchecked side, #13 a held path dipping below the stop) each fail a test now.

## Design Notes

- Positions lists derived from fills: held winners and sold bets are CLOSED; held losers are OPEN (Polymarket's unredeemed losers), so both lists are exercised (FR-3).
- Price paths only where needed (stop-loss): buy price, the sell point, then the outcome at resolution.
- AI choices: 100 shares per bet (clean hand values); thin wallet 20 of 29 won, so a good-looking record still gets *Not enough data*; addresses `0x` + sha256 of the name.

## Verification

**Commands:**
- `uv run liquidoracle make-synthetic` then `git status` -- expected: no change to committed files
- `uv run pytest` -- expected: all pass
