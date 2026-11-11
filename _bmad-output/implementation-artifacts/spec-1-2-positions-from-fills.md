---
title: 'Story 1.2: Positions from fills'
type: 'feature'
created: '2026-11-11'
status: 'in-review'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '056c33b3cbba672f2ad38bf5b8c377127f288f95'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Skill Test (Story 1.4) and the Synthetic Wallets (Story 1.3) need a Wallet's fills turned into bets by one set of rules. Nothing builds Positions yet, and `records` has no types.

**Approach:** Add the shared record types to `records` and one pure builder, `core/positions.build_positions(fills, markets)`. It groups TRADE fills by token into Positions, decides which Markets are resolved, applies the four Epic 1 exclusions with one reason each, sets Slivers apart, and returns the window size, the count per reason, the tested Positions and the Slivers (FR-3, AD-7, AD-10, AD-11, AD-12).

## Boundaries & Constraints

**Always:**
- Entry Price p = share-weighted average price of the Position's BUY fills; sells never change it. Shares held s = Σ bought − Σ sold, from TRADE rows only; REDEEM rows are never a share source.
- Resolved = Market closed, outcome prices exactly {0, 1}, and a resolution time. A closed Market that fails this is "unclear resolution".
- One reason per left-out Position, checked in this order: unclear resolution, split or merged, sold before resolution (s = 0), not explained (0 < s ≤ shares bought fails).
- A Position that passes those but has s < 1% of shares bought and s < 1 share is a Sliver: returned apart, neither tested nor left out.
- Own Fee per BUY fill = cash paid − shares × price, only in Markets with fees enabled; 0 elsewhere.
- Exit PnL = Σ shares sold × (sell price − p), kept on every Position.
- Pure function: no I/O, no settings, no randomness. Output order is fixed (by Market, then token).
- Every test names its FR or AD.

**Never:**
- No fee-schedule check (Story 2.3), no positions-list cross-checks ("token only in activity", 1% gap) and no "not fully read" (Stories 2.2, 2.3), no 2,000 cap (AD-8 lives in the data client).
- No store, client, Synthetic Wallets or Skill Test code.
- No `git add .`, no merge, no `gh`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Several buys | BUY 100 @ 0.40, BUY 300 @ 0.60, same token, resolved | One Position, p = 0.55, s = 400 | N/A |
| Partly sold | BUY 100 @ 0.40, SELL 40 @ 0.70 | Tested, s = 60, p = 0.40, Exit PnL = 12.00 | N/A |
| Fully sold | BUY 100, SELL 100 | "sold before resolution", Exit PnL kept | N/A |
| Sliver | BUY 1,000, SELL 999.5 | Sliver, s = 0.5 | N/A |
| Sliver edges | BUY 1,000, SELL 995 (0.5% left, but 5 shares); BUY 20, SELL 19.5 (0.5 share, but 2.5% left) | Both tested: a Sliver needs both limits | N/A |
| Oversold | BUY 100, SELL 120 | "not explained" | N/A |
| Split Market | any SPLIT / MERGE / CONVERSION row in the Market | All its Positions "split or merged" | N/A |
| 50-50 Market | closed, prices {0.5, 0.5} | "unclear resolution" | N/A |
| Open Market | not closed, or no Market record | Outside the window, not counted | N/A |
| Redeem only | REDEEM row for the token | Changes nothing | N/A |
| Fee fill | fees on, 100 shares @ 0.50, cash 50.75 | Own Fee 0.75 | N/A |
| No fills | empty input | window 0, tested 0 | N/A |

**Decisions (Edvard, 2026-11-11):** Entry Price comes from the BUY fills, not Polymarket's `avg_price` (AI's recommendation). Slivers: under 1% of bought **and** under 1 share (Edvard added the second limit and kept their money in Real PnL; on follow-up he chose "at most $1 if it won" and that Slivers are also simulated). Plan changed first: commit 056c33b.

</frozen-after-approval>

## Code Map

- `src/liquidoracle/records.py` -- docstring only. Add the types here (stdlib only; the AD-1 rule test already enforces no app imports).
- `src/liquidoracle/core/__init__.py` -- layer docstring. New module `core/positions.py`.
- `tests/test_architecture.py` -- layer rules; `core` may import `records`, stdlib, numpy. Do not change.
- Real field shapes (`spike/raw/sample/capture/*/activity_*.json`, git-ignored): TRADE rows carry `token_id`, `side`, `size`, `usdc_size`, `price`, `timestamp`, `condition_id`; SPLIT/MERGE/CONVERSION/REDEEM rows have `token_id` "" and are matched by `condition_id`. Gamma gives `closed`, `closedTime`, `outcomePrices` and `clobTokenIds` as aligned lists.

## Tasks & Acceptance

**Execution:**
- [x] `src/liquidoracle/records.py` -- frozen dataclasses `ActivityRow`, `Market`, `PricePoint`, `Position`, `PositionSet`, and `ExclusionReason` (StrEnum, four values) -- AD-1, AD-10.
- [x] `src/liquidoracle/core/positions.py` -- `is_resolved(market)` and `build_positions(fills, markets) -> PositionSet` -- FR-3, AD-7, AD-11, AD-12.
- [x] `tests/test_positions.py` -- one test per matrix row and per rule, plus purity (shuffled input, same output) -- FR-3, AD-7, AD-10, AD-11, AD-12.

**Acceptance Criteria:**
- Given any fills, when built, then window size = tested + Slivers + Σ left-out counts, and `PositionSet` exposes each.
- Given `uv run pytest`, then all tests pass with sockets blocked.

## Implementation Notes

- Implemented directly in the main session; Edvard approved subagents for the review only (as in Story 1.1).
- Commits: 43e88e2 record types, f93fd97 builder and 32 tests. Full suite: 116 passed, 1 deselected.
- Matrix audit: every row has a passing test in `tests/test_positions.py` (several buys, partly sold, fully sold, Sliver, Sliver edges, oversold, split/merge/conversion, 50-50 and four other unclear cases, open and unknown Markets, REDEEM, fee fill, no fills).
- Planted bugs: Sliver `and` -> `or`, no 6-decimal rounding, fees in every Market, split checked after sold, open Markets counted, `<=` at the 1% limit: each failed a test. Removing the input sort did not: Python's `sum()` has been compensated (nearly order-independent) since 3.12, so no realistic input shows it. The sort stays as a cheap guarantee for exact repeats.
- Not in the plan, added by the AI: malformed rows (TRADE without token or side, unknown type) raise `ValueError`, so a data-layer bug cannot become a silent wrong count; a token with sells only has p and Exit PnL `None` and is 'not explained'.
- Smoke run on the captured Sample Wallets (one-off script outside the repo, Markets rebuilt from the spike's Gamma cache): 0x29306d window 23 (the '23 bets' in Story 2.7) = 18 tested + 3 Slivers + 2 sold; 0x0f4b0a 209 tested, 42 Slivers, 21 sold; 0x729806 649 'not explained' because its capture was cut at 150,000 rows and lacks old buys, which Story 2.2's 'not fully read' rule covers.

## Spec Change Log

## Review Triage Log

Review pass 1 (2026-11-11). Three subagent reviewers: blind (B), edge-case (E) and verification-gap (V), on the `src/` and `tests/` diff since the baseline.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | B, E: exactly 1% left becomes a Sliver for some sizes | medium | Verified: 0.01 * 70 = 0.7000000000000001, so BUY 70, SELL 69.3 gave a Sliver; the old test used 90, which happens to work | patch: limit rounded to 6 decimals; test over 35, 57, 70, 90 |
| 2 | B, V: the 1-share limit has no edge test | medium | V: `<` to `<=` passed all 32 tests | patch: BUY 1,000, SELL 999 stays tested |
| 3 | B, V: the token/price length check in `is_resolved` is untested | medium | V: deleting it passed all tests; 3 tokens with 2 prices then raise IndexError instead of "unclear resolution" | patch: misaligned Market case (the AI's first version of the test missed it; rechecked) |
| 4 | V: a TRADE row with token "" is untested | low | V: `is None` instead of `not` passed; "" is the real shape of non-TRADE rows | patch: case added |
| 5 | B: no losing Sliver test | low | True; Story 1.4 needs Slivers' losses too | patch: test added |
| 6 | B, E: `assert` in `excluded_counts` vanishes under `-O` | low | True | patch: explicit ValueError |
| 7 | E: Position takes `market.condition_id`, not the fills' key | low | A mismatched mapping key would mislabel the Position | patch: uses the key |
| 8 | V: empty sums give the int 0 | low | Verified: `exit_pnl` was `0` with no sells | patch: sums start at 0.0 + test |
| 9 | B: a test docstring claims "pages print only from this record" | low | Nothing in the test checks it | patch: clause removed |
| 10 | B: fills with no Market record are dropped silently | false | By design (Design Notes): activity is read by time, so fills of Markets outside the window must be ignored; a failed Gamma read is a data-layer error (AD-3, AD-9) | rejected |
| 11 | B: a sell before any buy goes unnoticed (net check only) | maybe-false | Needs shares from outside the activity (a transfer); whether it happens is unmeasured; a running-balance rule would change AD-11 | defer |
| 12 | B: sell fees are not counted; Exit PnL ignores cash received | low | True, but the PRD Glossary defines Own Fees on buys and Exit PnL as shares sold x (sell price - p) | defer (plan question for the Exit PnL card) |
| 13 | B: split-or-merged Positions get an Exit PnL against buy-only p | low | True; harmless until a total is shown | defer (Exit PnL card) |
| 14 | B: tokens only received by SPLIT make no Position | low | True; the positions-list join in Story 2.3 brings them in | rejected (Story 2.3 by the plan) |
| 15 | B, E: money is not rounded; Own Fee can be slightly negative | low | Convention: money is float, rounded only for display. Measured on 792,027 captured fills: 4,135 negative fees, all above -0.00001, total -$0.00016; Story 2.3's fee check with tolerance covers them | rejected |
| 16 | E: zero-size, negative, NaN or out-of-range fills are not refused | low | Measured: none among 792,027 captured TRADE rows; the data layer types the rows (Story 2.1) | rejected |
| 17 | E: duplicate fills are counted twice | false | Story 2.2: identical-looking rows are separate fills, never de-duplicated | rejected |
| 18 | E: Markets with more than two outcomes are always unclear | false | A Polymarket condition is binary; multi-outcome events are sets of binary Markets (AD-20), and AD-7 says exactly {0, 1} | rejected |
| 19 | E: a token listed twice in a Market | low | Malformed Gamma data, not seen | rejected |
| 20 | B: `type` and `side` are plain strings, not enums | low | Style; no named harm | rejected |
| 21 | V: removing the input sort fails no test | low | Already in Implementation Notes: `sum()` is compensated since Python 3.12 | defer |

After the patches: 123 passed, 1 deselected. The reviewers' planted bugs (#2, #3, #4, #1 unrounded) each fail a test now.

## Design Notes

- The window is "Positions in closed Markets" (AD-7's unit). Fills in Markets that are not closed, or with no Market record, are outside it and not counted, so open bets never show as "unclear resolution". A token missing from its Market's token list counts as "unclear resolution".
- Shares are rounded to 6 decimals (Polymarket's share precision) before the s checks: real Wallets have 13 to 22 tokens each where bought − sold leaves float noise like 3e-15.
- `Position` carries o (1.0 or 0.0, None when unclear), p, shares bought, sold and held, Own Fees, Exit PnL and `reason` (None = tested or Sliver). Left-out Positions keep their values (AD-11), so Story 1.3's stop-loss trader can show negative Exit PnL.

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass
- `uv sync --locked` -- expected: no lock change
