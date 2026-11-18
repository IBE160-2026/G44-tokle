---
title: 'Story 1.4: The Skill Test'
type: 'feature'
created: '2026-11-18'
status: 'in-review'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'e6a35b5ed22a0a67b9e9967939374ef621d2fc2a'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nothing yet turns a Wallet's Positions into a p-value and a Verdict. Story 1.3's Synthetic Wallets and `expected.json` wait for a Skill Test to check.

**Approach:** Add `core/rng.py` (AD-15 generators) and `core/skilltest.py`: exact Real PnL, 10,000 Simulations with one shared draw per Market, a whole-cent tie count for the p-value, the Verdict, and the chart bins. One public function always applies the 30-bet minimum; a private engine function skips it for the hand-check only.

## Boundaries & Constraints

**Always:**
- Real PnL = fsum of s·(o − p) − Own Fees over tested Positions **and Slivers**; Slivers are simulated too but never counted toward 30 (Story 1.2).
- Sort by (`condition_id`, `token_id`); one `SeedSequence(seed, spawn_key=rng.spawn_key("skilltest", unit_id))` per Wallet; one U per Market per Simulation.
- p = (1 + Simulations ≥ real) / 10,001 on whole-cent integers without fees; the shown Real PnL is the exact sum.
- Verdict strings exactly as in `expected.json`. Every Story 1.3 answer is met, including the stop-loss trader reading *Skilled (high confidence)* (the FR-11 limit, on purpose).
- `core` imports only `records`, stdlib, numpy; no settings; never `random`, numpy global state or `hash()`. Every test names its FR/AD.

**Never:**
- No store, phrases, pages, `load-sample`, Own Fee schedule check, negative-risk or ladder coupling (Stories 1.5–1.7, Epic 2).
- No parameter or setting on the public function that skips the minimum. No `git add .`, no merge, no `gh`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Hand-check (engine) | 10 at 0.50, all won | 0.0003 ≤ p ≤ 0.002 | N/A |
| Sharp / favourite / stop-loss | their files | p < 0.01 / p ≥ 0.05 / p < 0.01, Verdicts as `expected.json` | N/A |
| 29 vs 30 tested | thin wallet; 30 bets | *Not enough data*, no p, no bins / a Verdict | N/A |
| Fixed fee on every Position | sharp trader + $1.50 each | Real PnL −$150.00 exactly; same p and Verdict | N/A |
| Many fractional amounts | 2,000 × 1 share at 0.335, won | exact $1,330.00; rounded sum differs | N/A |
| All won near 1 | 30 bets at 0.97–0.99 | p within 4 SD of Π prices | N/A |
| Coin-flippers | 1,000 (100 off the Linux 3.14 job) | p < 0.05 ≤ 7%, p < 0.01 ≤ 2% | N/A |
| Same data, Seed; two `PYTHONHASHSEED` subprocesses; golden counts | small Wallets + 3 coin-flippers, Seed 44 | identical results; stored counts reproduced exactly | N/A |
| Bad input | o or p missing; 3 tokens in one Market | — | ValueError |

**Decisions (Edvard, 2026-11-18):**
- Chart bins (AI's option A): 40 equal bars on a round dollar axis centred on $0, wide enough for the Real PnL and the middle 99.8% of the Simulations, plus the two end bars holding everything beyond the axis. Rejected: an axis covering every Simulation (one far-out replay squeezes the curve).
- Subagents for the review only, as in Stories 1.1 to 1.3.

</frozen-after-approval>

## Code Map

- `src/liquidoracle/records.py` -- add `Verdict` (StrEnum), `ChartBin`, `SkillTestResult`; stdlib only.
- `src/liquidoracle/core/positions.py` -- `PositionSet.tested/slivers`; reuse, do not change.
- `src/liquidoracle/data/synthetic.py` -- `small_wallets()`, `coin_flipper(i)`, `coin_flippers(n)` for test inputs.
- `tests/test_synthetic.py` -- `positions(wallet)` helper and the AST ban-test pattern to copy.
- `tests/conftest.py` -- `repetitions` fixture (100 default, 1000 on CI Linux 3.14); `slow` marker exists.
- `tests/test_architecture.py` -- AD-1 tables already allow `core` → records + numpy; planted `core/skilltest.py` cases exist.

## Tasks & Acceptance

**Execution:**
- [x] plan first -- spine memlog: the side rule (Design Notes) and the bins rule from Q1 -- CLAUDE.md: plan before code.
- [x] `src/liquidoracle/records.py` -- result types -- AD-22, AD-25.
- [x] `src/liquidoracle/core/rng.py` -- `spawn_key(purpose, id)`, `generator(seed, purpose, id)` (PCG64) -- AD-15.
- [x] `src/liquidoracle/core/skilltest.py` -- `skill_test(position_set, *, seed, unit_id)` and private `_engine(...)`; Simulations in row chunks -- FR-4 to FR-7, AD-20.
- [x] `tests/test_skilltest.py` -- the matrix, Verdict thresholds, engine-reference rule test (with a planted case), randomness ban for `core`, golden counts, NFR-10 timing (1,000 Positions < 10 s) -- FR-4 to FR-7, FR-13, AD-15, AD-17.
- [ ] `sprint-status.yaml` -- 1-4 to `review` at the end.

**Acceptance Criteria:**
- Given `uv run pytest`, then all tests pass with sockets blocked, and with `--repetitions 1000`.
- Given a 1,000-Position Wallet, then its time is measured and noted (NFR-10).

## Implementation Notes

- Implemented directly in the main session; subagents only for the review (Edvard, 2026-11-18).
- Plan commit 480380c (spine AD-20 side rule, AD-25 bins, memlog), spec 559efd3.
- First run met every `expected.json` answer with Seed 44: hand-check p 0.0009 (engine), favourite buyer p 0.58, sharp trader p 0.0002, thin wallet *Not enough data*, stop-loss trader p 1/10,001 (no Simulation reached $1,650), *Skilled (high confidence)* as planned.
- Coin-flippers: p < 0.05 for 3.6% and p < 0.01 for 0.6% of 1,000 (3% and 1% of the first 100). Below 5% / 1% because ties count against the Wallet and the cent amounts are discrete.
- NFR-10: a 1,000-Position Wallet takes about 0.09 s on Edvard's laptop (budget 10 s); the test asserts < 10 s.
- Golden counts (`GOLDEN` in the test file) come from this code's first run: the five small Wallets plus coin-flippers 0 to 2.
- Not in the plan, added by the AI: `verdict_for` is public (Story 1.7 and Epic 5 need it); `_engine` refuses an empty list; `PURPOSES` holds only `skilltest` so far.
- Found by the AI's own check before review: the first Sliver test used one winning and one losing Sliver, so the money it checked summed to $0 and proved nothing; now both win (+$0.90) and leaving them out changes the count. The helper `tested()` was collected by pytest as a test; renamed `position_set()`.
- Full suite: 228 passed, 1 deselected; `tests/test_skilltest.py` also passes at `--repetitions 1000`.
- After review: 293 passed, 1 deselected; 119 in `tests/test_skilltest.py` at `--repetitions 1000`. While patching, the AI's new bar-edge test failed on a total of exactly $2.00; the code was right (the last bar holds its top edge, finding 10) and the test was corrected.

## Spec Change Log

## Review Triage Log

Review pass 1 (2026-11-18). Three subagent reviewers on the diff since the baseline (spec and sprint status left out): blind (B), edge-case (E) and verification-gap (V). V planted each claimed bug in a copy and ran the tests.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | V, B: the "other side wins on U > 1 − p" branch is never run by a test that could fail | medium | V: `draws > price` instead of `draws > high_bar` passed all 54 tests; the side-1 test held one Position, so it was always the smaller token | patch: a two-sided Market at 0.60 / 0.30; side 1 wins ~30%, either side ~90% |
| 2 | V: swapping `min` for `max` in the side rule passes every test | low | True; same distribution for one Wallet, but group tests (Epic 5) share draws | patch: golden count for a 40-Market two-sided set |
| 3 | V: the bins are never checked with Own Fees | medium | V: dropping `- own_fees` passed all tests | patch: $2 fees shift every bar's count by two $100 bars on the same axis |
| 4 | V: nothing checks the axis is the tightest round width | medium | V: a width 10× too wide passed all tests | patch: `_nice` table and a tightness check where the Real PnL sets the axis |
| 5 | V, B, E: the public `skill_test` is never tested with bad input; a three-outcome Market passes below 30 bets and is refused at 30 | medium | V: deleting `_check` from `skill_test` passed; the outcome check sat only in `_engine` | patch: all checks in `_check`; bad-input test runs both functions |
| 6 | B, E: `own_fees` None or NaN, or infinite shares, give TypeError / OverflowError / NaN results, not ValueError | low | True; the JSON reader refuses NaN and Infinity, but the core takes any Position | patch: finite checks in the existing guard |
| 7 | B, E: a negative Own Fee is accepted and adds money | low | True; a rounding gap in real fee rows can make one slightly negative, so refusing would crash a real lookup | defer: Story 2.2 fee-schedule check (`deferred-work.md`) |
| 8 | B, E: a 2.5-cent bar width gives unequal bars once edges are rounded to cents | low | True for a reach of $0.40 to $0.50 | patch: whole-cent widths only (2.5¢ skipped) |
| 9 | E: `floor(total / width)` puts a total on an edge in the bar below | medium | Reproduced: `floor(0.3 / 0.1)` is 2 | patch: sort totals against the stored edges (`searchsorted`) |
| 10 | B, E: a value exactly on the axis edge (the Real PnL or tied totals at the 99.9% point) lands in the end bar | low | Not reproduced with the reviewers' inputs, but true by construction when the reach is already a round width | patch: the last bar on the axis holds its top edge; end bars hold only what is strictly beyond |
| 11 | B, V, E: the randomness ban misses `from numpy import random` and `import numpy.random as npr` | medium | V: both planted forms passed | patch: AST walk extended; 8 planted forms and an allowed form tested |
| 12 | B: "smaller `token_id`" can be read as a number; the code compares text | low | True; Polymarket ids are decimal strings of different lengths | patch: spine AD-20 wording and a memlog entry |
| 13 | B: the subprocess script hard-codes Seed 44 | low | True | patch: formatted from `SEED` |
| 14 | B: `SkillTestResult` docstring says it records "the set it was computed on" | low | True; it holds no set identity | patch: docstring names the store key (Story 1.6) |
| 15 | B: no `unit_id` field, so a result cannot be replayed | false | For a lookup the random unit is the Wallet's address (AD-15), which is the store's key | rejected |
| 16 | B: no field for the share of tested Positions with undetected links (AD-20) | false | Epics move that measurement to Epic 2 with ladders (Story 2.4) | rejected |
| 17 | B: Entry Prices of exactly 0 or 1 are accepted | false | The maths is right: a bet at 0 that won truly had no chance under no skill; Polymarket fills are never at 0 or 1 | rejected |
| 18 | B: the marker uses the exact Real PnL, the count the whole-cent sum | false | By design: Conventions › Money "two sums" (Edvard, 2026-11-05); the UX says the count is never read from the bars | rejected |
| 19 | B: `epic-1-context.md` describes fee checks and phrases as if built | false | The file lists the epic's requirements, not what the code does now | rejected |
| 20 | B: `_check` runs twice through `skill_test` | low | Harmless and cheap | rejected |
| 21 | B: `scope` is a free string | low | Only `lookup` exists; group scopes arrive with Epic 5 | rejected |

After the patches, the five demonstrations (#1 `draws > price`, #2 `max`, #3 no fee in bins, #4 width 10× too wide, #9 the old `floor`) each fail a test.

## Design Notes

- Side rule (AI choice, user never sees it): in each Market, the smaller `token_id` in the test wins on U < p, any other on U > 1 − p, so both win with probability p and the rule is the same across Wallets (Hold-up).
- Win/loss in cents: `round(s·(1−p)·100)` and `round(−s·p·100)`, once per Position; a Simulation's total = Σ losses + wins · (win − loss), integer math, order-free.
- Bins use the Simulation totals in dollars minus total Own Fees; the marker count is the exact integer count.

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass
- `uv run pytest --repetitions 1000 tests/test_skilltest.py` -- expected: all pass
