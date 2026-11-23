---
title: 'Story 2.8: The fee check accepts an earlier rate'
type: 'feature'
created: '2026-11-23'
status: 'done'
baseline_commit: 'b959f4410f28dbd486d3b4aec4ae15dea56f7d91'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The fee check compares each Own Fee with the rate Gamma lists today, but Polymarket changes rates, so fees that were real when paid fail and count as 0. Story 2.7 found 9 such fees (0x0f4b0a 7, $0.28; 0x091596 2, $44.48), all fitting the fee formula at 4%, 5% or 7% instead of the listed 1% or 3%, so Real PnL looks slightly better than it was.

**Approach:** A fee passes when it fits shares × rate × (p(1 − p))^exponent within the $0.0001 tolerance, with the listed exponent and either the listed rate or any whole-percent rate from 1% to 10% `[ASSUMPTION]` (PRD FR-4, AD-12; Edvard, 2026-11-23, reversing Story 2.3's strict check). The independent reference script gets the same rule from a fresh AI helper that sees only the script, its notes, the two Wallet files and the new FR-4 sentence, never the app's code, as in Story 2.7.

## Boundaries & Constraints

**Always:** Negative fees, fees that fit no allowed rate, fees above the 10% rate, and non-zero fees in a Market with no schedule still fail, count as 0, keep their Position in the test and are counted for the card. A maker fill (|fee| ≤ $0.0001) still counts as exactly 0. The reference script keeps its own tolerance (J3: any tolerance in a wide range gives the same split). Reference CSVs are the helper's output, copied unchanged and committed before the app change; the old reference values are never edited by hand. The `test_window.py` numbers come from what the fixtures themselves hold (Gamma fetched 2026-11-20, rates differ from the committed real files in 5 Markets), worked out on the fixtures, never copied from the full Wallets (Edvard, at approval).

**Never:** Show the helper `src/`, the app's tests or results. Touch the committed Sample Dataset, `core/skilltest.py`, or the Follower Fee (Epic 6). Look up rate history from Polymarket.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Listed rate | 100 shares at 0.50, listed 3%, fee 0.75 | passes, counts | N/A |
| Earlier rate | same fill, fee 1.25 (5%) | passes, counts | N/A |
| Between rates | fee 0.875 (3.5%) or 0.7502 | fails, counts 0, recorded | N/A |
| Above the cap | fee 2.75 (11%) | fails | N/A |
| Cap edge | fee 2.50 (10%) | passes | N/A |
| Listed rate above 10% or not whole | listed 0.125, fee 3.125 | passes | N/A |
| Exponent 2 | listed (0.03, 2), fee at 5% with exponent 2 | passes; same fee with exponent 1 fails | N/A |
| No schedule / negative | fee 0.75 / −0.50 | fails | N/A |

</frozen-after-approval>

## Code Map

- `src/liquidoracle/core/positions.py:28-60` -- `FEE_TOLERANCE`, `fee_passes(fee, shares, price, market)`: the only place the rule lives; `_check_fees` (line 172) calls it and needs no change.
- `tests/test_positions.py:494-540` -- fee unit tests; `test_a_fee_off_schedule_fails` uses 1.25 as "5% in a 3% Market", which now passes and must change. Helpers `fee_buy`, `market(fees=True, schedule=(rate, exp))`.
- `tests/test_window.py:469` and `:524` -- assert the 2.3 strict failures on fixtures `fees-and-open` (0x091596, 1 fail $44.31) and `fees` (0x0f4b0a, 7 fails $0.28); rewrite to "all pass".
- `tests/reference/real_pnl_reference.py` (`check_fee` line 133, `schedule_fee` line 114), `script-notes.md`, `0x0f4b0a-*.csv`, `0x091596-*.csv` -- the helper's files. Story 2.7's A1 alternative already gives the expected totals: −188.77 and −49,615.70.
- `tests/test_reference_pnl.py` -- reads the CSVs' TOTAL rows; no change expected beyond docstrings. 0x29306d has Own Fees 0, so it is unaffected but still compared.
- `tests/test_real_sample.py:536` `RECORDED` and `docs/real-wallets.md` table -- per-Wallet Verdict, tested count, Real PnL (rounded to the dollar) and fees; update every value that moves.

## Tasks & Acceptance

**Execution:**
- [x] scratchpad `helper-2-8/` -- copy the reference script, `script-notes.md`, `fields.md`, the two Wallet files and the new FR-4 sentence; a fresh helper (Opus, extra-high effort) changes `check_fee` to the new rule, re-runs, and adds a dated change section to `script-notes.md` with the new totals -- independence.
- [x] `tests/reference/` -- copy the helper's files unchanged after checking its file list and a re-run; commit before the app change.
- [x] `src/liquidoracle/core/positions.py` -- `fee_passes` accepts the listed rate or any k/100 for k = 1..10 with the listed exponent; constant for the cap with an `[ASSUMPTION]` comment; docstring names FR-4/AD-12.
- [x] `tests/test_positions.py` -- one test per matrix row (replace the old off-schedule test).
- [x] `tests/test_window.py` -- both fee Wallets: every fee passes, failed count 0, Own Fees rise by $44.48 and $0.28.
- [x] `tests/test_real_sample.py`, `docs/real-wallets.md` -- update moved values.

**Acceptance Criteria:**
- Given the committed references, when `uv run pytest` runs offline, then the app equals 0x0f4b0a −188.77, 0x091596 −49,615.70 and 0x29306d 295.06 to the cent, with failed fee counts 0, and the suite is green.
- Given any reference value differs from the A1 totals, when found, then the cause is logged here before anything changes.

## Implementation Notes

- Built directly in this session, as in Story 2.7; subagents only for the Epic 2 context refresh, the independent helper and the review.
- **Fixture numbers (Edvard, at approval):** worked out on the fixtures, not the full Wallets. `fees-and-open` (Gamma of 20 Nov) had only 1 failing fee ($44.3074; the full file has 2, $44.48, because 0xf7b7e74c's rate changed between 20 and 23 Nov). Own Fees 1,087.5154 -> 1,131.8228; that Sliver's own fees 151.7974 -> 196.1048 (its other fees passed already, which the first test draft missed). `fees`: 7 fails $0.27793, Own Fees 0.2521 -> 0.5300.
- **Helper:** read only its folder (file list in its report). New totals: 0x0f4b0a -188.77 (Own Fees 0.53), 0x091596 -49,615.70 (1,131.82), failed 0 on both; equal to its 2.7 A1 totals in every digit. Fitted rates: 0x0f4b0a 6 at 5%, 1 at 4% (listed 1%); 0x091596 7% (listed 1%) and 5% (listed 3%). Two runs byte-identical. Files copied unchanged.
- **No mismatch** between app and reference (897 tests pass: 894 + 3).
- **Surprise: a third Wallet moved.** 0xd3a6e5's Own Fees were 0 under the strict check: all 26 of its fees ($461.79; 24 at 4%, 2 at 5%) are in Markets Gamma lists at 1%. Real PnL $118,065.40 -> $117,603.61. Verdict and p-value unchanged on all three (FR-5). `RECORDED` and `docs/real-wallets.md` updated with the old values kept beside them.
- **Script vs app (no effect on the data):** the helper also tries whole-percent rates where a Market has no fee or no schedule; the app ignores fees in Markets without fees (AD-12) and fails a non-zero fee with no schedule. Neither case occurs in the two files (largest no-fee-Market fee 0.0000045). Deferred.

## Spec Change Log

## Review Triage Log

Pass 1 (2026-11-23): blind hunter (BH), edge-case hunter (ECH), verification-gap reviewer (VG; no gaps, two other findings). 20 findings.

| # | Layer | Finding | Verdict | Evidence / route |
|---|-------|---------|---------|------------------|
| 1 | ECH, BH | On tiny fills (shares x p(1-p) <= 0.02) the whole-percent fees lie within 2 x $0.0001 of each other, so almost any fee up to 10% + $0.0001 passes | low | Real, but at most about $0.002 per such fill; the strict check was as loose there (±$0.0001). Fix (relative tolerance) adds rules. Rejected; noted for the AI log. |
| 2 | ECH | Price outside (0, 1) with a fractional exponent gives a complex number | false | Pre-existing expression; fill prices are in (0, 1) and every real exponent is 1. |
| 3 | ECH | A Market listed at rate 0 with fees enabled now accepts 1-10% fees | false | Intended: FR-4 accepts any whole-percent rate because listed rates change; none seen in the data. |
| 4 | ECH | Window tests dropped the check that left-out Positions carry no failed fee | low | Patch: both fixture tests assert no failed fee in `left_out`. |
| 5 | BH | AC "failed fee counts 0" not compared with the reference on the full Wallets | medium | Patch: the counts test also compares the app's failed-fee count with the reference's FAILED rows on counted Positions; planted strict rule fails it (2 vs 0). Stored result lacks the count (Epic 3 deferral), so the test builds the Positions as `test_window` does. |
| 6 | BH | `test_reference_pnl.py` docstring silent on the 2.8 re-run and says mismatches go in the 2.7 spec | low | Patch: docstring names the third helper, its inputs (FR-4 at b959f44) and the commit order. |
| 7 | BH | Rule also accepts rates below the listed one; epic context says rates were "lowered" | low | Rates move both ways (Story 2.6 note: 4% to 1% and 4% to 5%); PRD says "changes". Patch: epic context wording. |
| 8 | BH | The 1% floor is untested | low | Patch: 0.125 (0.5%) added to the failing cases. |
| 9 | BH | Names `fee_at_rate_1` and `EARLIER_RATES` mislead | low | Patch: `fee_per_unit_rate`, `WHOLE_PERCENT_RATES`. |
| 10 | BH | 0xd3a6e5's new fees pinned only by a dollar-rounded Real PnL | low | The $462 move is caught by `RECORDED`; detail in Implementation Notes. Rejected. |
| 11 | BH | Other seven Wallets might move under $0.50 unseen | false | Checked in this session: exact Real PnL and Own Fees compared under both rules, all seven unchanged. |
| 12 | BH | "With the listed exponent" is an unlabelled assumption | low | AD-12 and this spec state it; the helper chose the same. Rejected. |
| 13 | BH | `script-notes.md` cites `fr-4.md` and a scratch folder not in the repo | low | Helper's words kept unedited (2.7 rule); docstring (row 6) gives the input and repo command. |
| 14 | BH, VG | First task unticked; Code Map line numbers stale; Tasks line says $44.48 for the fixture | false | Spec bookkeeping, not code; box ticked; the fixture figure is in Implementation Notes. |
| 15 | BH | Sprint status says in-progress while the spec is in review | false | Synced at the end of the build (step 5). |

## Verification

**Commands:**
- `uv run pytest tests/test_positions.py tests/test_window.py tests/test_reference_pnl.py tests/test_real_sample.py -v` -- expected: all pass.
- `uv run pytest` -- expected: whole suite green.
