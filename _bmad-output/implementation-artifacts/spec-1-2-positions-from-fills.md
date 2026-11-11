---
title: 'Story 1.2: Positions from fills'
type: 'feature'
created: '2026-11-11'
status: 'in-progress'
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
- [ ] `src/liquidoracle/records.py` -- frozen dataclasses `ActivityRow`, `Market`, `PricePoint`, `Position`, `PositionSet`, and `ExclusionReason` (StrEnum, four values) -- AD-1, AD-10.
- [ ] `src/liquidoracle/core/positions.py` -- `is_resolved(market)` and `build_positions(fills, markets) -> PositionSet` -- FR-3, AD-7, AD-11, AD-12.
- [ ] `tests/test_positions.py` -- one test per matrix row and per rule, plus purity (shuffled input, same output) -- FR-3, AD-7, AD-10, AD-11, AD-12.

**Acceptance Criteria:**
- Given any fills, when built, then window size = tested + Slivers + Σ left-out counts, and `PositionSet` exposes each.
- Given `uv run pytest`, then all tests pass with sockets blocked.

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Design Notes

- The window is "Positions in closed Markets" (AD-7's unit). Fills in Markets that are not closed, or with no Market record, are outside it and not counted, so open bets never show as "unclear resolution". A token missing from its Market's token list counts as "unclear resolution".
- Shares are rounded to 6 decimals (Polymarket's share precision) before the s checks: real Wallets have 13 to 22 tokens each where bought − sold leaves float noise like 3e-15.
- `Position` carries o (1.0 or 0.0, None when unclear), p, shares bought, sold and held, Own Fees, Exit PnL and `reason` (None = tested or Sliver). Left-out Positions keep their values (AD-11), so Story 1.3's stop-loss trader can show negative Exit PnL.

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass
- `uv sync --locked` -- expected: no lock change
