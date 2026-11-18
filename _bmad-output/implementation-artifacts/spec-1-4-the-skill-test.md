---
title: 'Story 1.4: The Skill Test'
type: 'feature'
created: '2026-11-18'
status: 'in-progress'
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
- [ ] plan first -- spine memlog: the side rule (Design Notes) and the bins rule from Q1 -- CLAUDE.md: plan before code.
- [ ] `src/liquidoracle/records.py` -- result types -- AD-22, AD-25.
- [ ] `src/liquidoracle/core/rng.py` -- `spawn_key(purpose, id)`, `generator(seed, purpose, id)` (PCG64) -- AD-15.
- [ ] `src/liquidoracle/core/skilltest.py` -- `skill_test(position_set, *, seed, unit_id)` and private `_engine(...)`; Simulations in row chunks -- FR-4 to FR-7, AD-20.
- [ ] `tests/test_skilltest.py` -- the matrix, Verdict thresholds, engine-reference rule test (with a planted case), randomness ban for `core`, golden counts, NFR-10 timing (1,000 Positions < 10 s) -- FR-4 to FR-7, FR-13, AD-15, AD-17.
- [ ] `sprint-status.yaml` -- 1-4 to `review` at the end.

**Acceptance Criteria:**
- Given `uv run pytest`, then all tests pass with sockets blocked, and with `--repetitions 1000`.
- Given a 1,000-Position Wallet, then its time is measured and noted (NFR-10).

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Design Notes

- Side rule (AI choice, user never sees it): in each Market, the smaller `token_id` in the test wins on U < p, any other on U > 1 − p, so both win with probability p and the rule is the same across Wallets (Hold-up).
- Win/loss in cents: `round(s·(1−p)·100)` and `round(−s·p·100)`, once per Position; a Simulation's total = Σ losses + wins · (win − loss), integer math, order-free.
- Bins use the Simulation totals in dollars minus total Own Fees; the marker count is the exact integer count.

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass
- `uv run pytest --repetitions 1000 tests/test_skilltest.py` -- expected: all pass
