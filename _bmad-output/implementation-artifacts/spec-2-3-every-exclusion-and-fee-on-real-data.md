---
title: 'Story 2.3: Every exclusion and fee on real data'
type: 'feature'
created: '2026-11-21'
status: 'done'
baseline_commit: '0bf136a51ce4a6ac8817c708b18d4db8c9182778'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Position builder only sees activity rows. It never compares them with the positions lists, so a token missing from the lists, a share-count disagreement, or a listed Position with no fills slips through or vanishes uncounted. Own Fees are taken as they come, so a wrong or negative fee changes Real PnL.

**Approach:** `core/positions.build_positions` also takes the window's listed Positions. It adds the remaining AD-11 reasons, checks every buy fill's Own Fee against its Market's Gamma `feeSchedule` (AD-12), and reports the left-out share (with the over-10% flag) and the failed fees for the card. Tests use new fixtures cut from the real capture.

## Boundaries & Constraints

**Always:** Every listed Position in a window Market comes out of the builder (tested, Sliver or left out), so nothing vanishes. One reason per left-out Position, in this order: not fully read, unclear resolution, split or merged, only in activity rows, share gap (> 1%, gap stored), sold before resolution, not explained. Share gap = |activity bought − listed bought| ÷ the larger of the two; a listed Position with no buy fill has gap 1.0. Own Fee per buy fill = cash − shares × price, only in Markets with fees enabled; passes when within `FEE_TOLERANCE` of 0 (maker fill, counts as 0) or of shares × rate × (p(1−p))^exponent (counts as recorded); anything else fails (negative included, or no schedule): counts as 0, its count and recorded total go on the Position. The same rules on both sides of the Cut-off Date (tested). Nothing stored changes: gaps and fees are recomputed from the snapshot's rows. Plan documents changed before code.

**Never:** v2 `entry_fees_usdc`. Card or page wording (Epic 3). Event coupling (Story 2.4). A Cut-off Date side in `positions_near` (Story 4.1). Schema changes.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Activity-only token | TRADE token in a window Market, on neither list | left out "only in activity rows" | N/A |
| Share gap | listed 5,000, activity bought 4,895 | left out "share gap", `share_gap` ≈ 0.021 | N/A |
| Gap at 1% | listed 100, bought 99 | not a share gap | N/A |
| Listed, no fill | listed 1,666.67, no TRADE rows, no split | left out "share gap", gap 1.0 | N/A |
| Taker fee | 0x091596's other 39 taker fills (rates 0.03–0.07) | pass, counted | N/A |
| Second fee Wallet | 0x0f4b0a's fee fills (not checked yet) | the result is recorded as it comes out, never tuned; a new failure goes to Edvard | N/A |
| Maker fill | fee −5.1e-7 in a fee Market | pass, counts 0 | N/A |
| Negative fee | fee −0.50 | fails, counts 0, recorded −0.50 | N/A |
| Split/merge fixture | 0x729806 Markets with SPLIT or MERGE | every Position "split or merged" | N/A |
| Unredeemed losers | 0x94884d OPEN rows, outcome 0 | tested, outcome 0 (loss) | N/A |
| Left-out share | 3 of 20 left out | share 0.15, flag on; 2 of 20 → flag off | N/A |
| Sells before buying | running balance below zero, net still positive (0xd3a6e5) | left out "not explained" | N/A |
| Fee at an old rate | 0x091596, 11 Jul 2026, paid $44.31 at 5%, Gamma says 3% | fails: counts 0, count 1, recorded $44.31 | N/A |

**Decisions (Edvard, 2026-11-21, all AI recommendations):** (1) A Position whose running balance goes below zero (buys counted first within one second) is left out as "not explained", even when it ends with shares left: 4 bets of 0xd3a6e5 would otherwise enter the test with a wrong share count. AD-11 gets the line; no new label. (2) The fee check stays strict: 0x091596's $44.31 fee at 5% (Gamma now says 3%; its June fills there paid 3%, so the rate likely changed) fails, counts as 0 and is listed. The epics AC says all its other fees pass; Story 2.7's hand calculation follows the same rule. (3) Gamma is fetched once, read-only, for the new fixture Markets only (about 10 requests, raw in git-ignored `spike/raw/`). (4) Spec kept whole (about 2,200 tokens); subagents for review only.

</frozen-after-approval>

## Code Map

- `records.py` -- `ExclusionReason` + `ONLY_IN_ACTIVITY` "only in activity rows", `SHARE_GAP` "share gap". `Position` + `share_gap: float|None`, `failed_fee_count: int = 0`, `failed_fees: float = 0.0`. `PositionSet` + `left_out_share`, `failed_fee_count`, `failed_fee_total` (tested + Slivers only: left-out fees never count).
- `core/positions.py` -- `build_positions(fills, markets, *, listed, not_fully_read=())`, `listed` required. Add `SHARE_GAP_ABOVE = 0.01`, `FEE_TOLERANCE = 0.0001` [ASSUMPTION], `LEFT_OUT_NOTE_ABOVE = 0.10`, `mostly_left_out(ps)`. Reuse `_build_one`, `_unread`, `is_resolved`. `Position.shares_bought` stays activity's sum (the s ≤ bought check needs one source; the gap rule keeps the two within 1%).
- `core/skilltest.py` -- `_check` refuses a negative `own_fees` (closes deferred-work entry from spec-1-4).
- `services/fetch.py:59` -- pass `listed=snapshot.positions`.
- `tests/fixtures/cut_from_capture.py` -- per-Wallet Market filter; new fixtures `split-merge` (0x729806: its 3 MERGE Markets + 3 smallest SPLIT ones), `open-losers` (0x94884d: 5 OPEN losers + 5 CLOSED winners), `fees` (0x0f4b0a: its fee Markets). Existing two files must come out byte-identical.
- `tests/test_positions.py`, `test_skilltest.py`, `test_synthetic.py`, `test_offline.py`, `test_phrases.py`, `test_window.py` -- 18 calls need `listed=`; a test helper derives a matching list from fills.
- Planning: AD-11, AD-12, epics.md 2.3, architecture memlog.

## Tasks & Acceptance

**Execution:**
- [x] `ARCHITECTURE-SPINE.md`, `epics.md`, `.memlog.md` -- reason order, gap measure, fee tolerance and formula, decisions 1 and 2 -- plan first.
- [x] `records.py`, `core/positions.py` -- listed-Position checks, fee check, left-out share -- AD-10, AD-11, AD-12.
- [x] `core/skilltest.py`, `services/fetch.py` -- negative-fee guard, pass `listed` -- AD-12.
- [x] `tests/fixtures/cut_from_capture.py` + `tests/fixtures/capture/*.json` -- three new fixtures -- AD-17.
- [x] `tests/test_positions.py` + `tests/test_window.py` -- every matrix row; fixtures through `positions_near` and `build_positions`; both sides of the Cut-off Date -- AD-11, AD-12.

**Acceptance Criteria:**
- Given `uv run pytest`, when it runs with sockets blocked, then all tests pass and `expected.json` still holds.
- Given `uv run liquidoracle load-sample`, when it runs, then all Sample Wallets load.

## Implementation Notes

- Written by the main session directly (subagents for review only, Edvard's call). 723 tests pass (695 before), 1 online test deselected. `load-sample`: 1,005 Wallets in 20 s.
- Plan first: AD-11 (reason order, gap measure, sold-before-bought, every listed Position counted), AD-12 (tolerance, formula, strict on rate changes), epics.md 2.3 AC, four memlog entries. Committed 92bdd0a first: Story 2.2 `done`.
- **Second fee finding went to Edvard** (matrix row "Second fee Wallet"): 0x0f4b0a fails 7 of its 19 window fee fills ($0.28), all in Markets Gamma now lists at 1% that charged 4–5% in April–May 2026. AI offered strict or "any whole-percent rate 1–10%", recommended strict (Verdict unchanged, card shows them); Edvard kept it strict. Spine, epics and memlog updated.
- Gamma fetched once (21 Nov): 6 + 10 + 14 Markets, all found, 4 requests (the open Market needed the `closed=false` ask). One split Market (0x0f49db97) is still open in Gamma, so `split-merge` has 5 Markets in its window; the test says so. The 2.2 fixtures came out byte-identical.
- Real results on the fixtures: 0x091596 window 64: 17 tested, 24 Slivers, 21 share gaps (conversion outputs, gap 1), 1 sold, 1 not explained; left out 36% (flag on); one failed fee $44.3074 (on a Sliver, so it stays in the test). 0x94884d: 5 OPEN losers tested at outcome 0. 0x729806: all 10 "split or merged".
- First reading of the frozen "no buy fill has gap 1.0": a listed Position whose list also says 0 bought got gap 0 (the two sources agree), to keep a sells-only token "not explained". **Reversed in review** (all three reviewers): a never-traded list row of 0 shares then read as "sold before resolution". Now the spec is followed as written: no buy fill is always gap 1. The 1.2 sells-only test now expects "share gap" (listed) or "only in activity rows" (unlisted).
- AI slip caught by an existing test: listed rows were first keyed by token id alone; the purity test reuses token ids across Markets and failed. Now keyed by (Market, token).
- Test Markets with fees now get a 3% schedule by default (`market(fees=True)`); before, they had none and the new check rightly failed their 0.75 fee.
- The "sells before buying" row is tested on built rows, not on a cut of 0xd3a6e5 (that would need another Gamma fetch).
- Deliberate-break check before review: 16 changes, one per new rule (no activity-only reason, no share gap, `>=` at 1%, gap unrounded, listed-only Positions dropped, no sell-before-buy check, sells first in a second, fees unchecked, maker rounding counted, negative fee passes, exponent ignored, left-out fees on the card, flag at `>=`, Skill Test takes a negative fee, sold before gap, token-only key): every one made a test fail.

## Spec Change Log

## Review Triage Log

Pass 1 (2026-11-21). Three reviewers: blind hunter (BH), edge-case hunter (EC), verification gap (VG). The diff left out the generated fixture JSON, which they could read in the repo. 25 findings: 6 fix groups patched, 2 deferred, the rest rejected. No loopback: the one deviation (EC1 group) was code leaving the frozen spec, fixed by following it.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| EC1 | A listed Position of 0 shares with no fill gets gap 0 and reads as "sold before resolution" | low | Confirmed: `_share_gap` returned 0 when both were 0, then `shares_held == 0`. The frozen spec says no buy fill = gap 1; the code had left it | patch (group with BH4, VG1): no buy fill always gives gap 1; test with a 0-share list row; sells-only test updated |
| BH4 | Same as EC1 | low | Same | patch (EC1 group) |
| VG1 | The zero-division guard in `_share_gap` is never run by a test | low | Confirmed: no 0-share list row in any test or fixture | patch (EC1 group): the guard is gone (bought > 0 before dividing); the new test fails if the no-fill branch is removed |
| BH15a | The fee test says "a Sliver here" but never checks it | low | Confirmed | patch: asserts the Position is in `built.slivers` |
| BH15b | "Not fully read" over a share gap, and a gap over "not explained", untested | low | Confirmed | patch: one test for both orders |
| BH7 | epics.md 2.3 still says the Skill Test accepts a negative fee | low | Confirmed; this story makes it refuse one | patch: parenthesis updated |
| BH8 | epic-2-context.md lacks the 2.3 rules | low | Confirmed; a story built from the context alone would use the old rules | patch: Own Fees bullet and a new Exclusions bullet |
| BH12 | `share_gap` None means two things (unlisted, or unread) | low | Confirmed for `_unread` Positions | patch: `Position` docstring names both |
| BH14 | Fixture script: `_chosen` docstring wrong for fees; a stale Gamma file could drop chosen Markets silently | low | Confirmed: fees takes every fee Market; `cut` never checked coverage | patch (group with EC6): docstring; `cut` stops when a chosen Market has no Gamma record |
| EC6 | Same as BH14 (stale Gamma file) | low | Same | patch (BH14 group) |
| BH5 | Conversion outputs as "share gap" has no tracked follow-up | low | memlog only says 2.4 "may relabel" | defer: deferred-work.md entry for Story 2.4 |
| BH6 | Six UX labels for seven reasons; "only in activity rows" has no wording | low | Pre-existing: AD-11 always had both list reasons; EXPERIENCE.md has "Polymarket's two lists disagree" | defer: deferred-work.md entry for Epic 3 (with BH1) |
| BH1 | `stored_result` drops the Position set, so the left-out share and failed fees are not reachable from the stored lookup | low | True, but no page shows them until Epic 3 (spec Never: card wording); the Position set carries them, which AD-11 makes the record pages print from | reject: adds public surface with no reader; in the Epic 3 deferred-work entry |
| BH2 | The stored-lookup test compares only the tested count | low | Dropping `listed=` is a TypeError (required); passing an empty list makes every token "only in activity", so tested 17 → 0 and the test fails | reject |
| BH3 | Duplicate listed rows make the result order-dependent | low | Real input never has them: `positions_near` keeps one row per token (OPEN first, tested in 2.2); fix adds a branch for unseen input | reject |
| EC2 | Same as BH3 | low | Same | reject |
| VG-o1 | Same as BH3 | low | Same | reject |
| EC3 | An unread token under another Market could hide a listed one | false | Polymarket token ids are unique to one Market's outcome; the same id cannot sit in two Markets | reject |
| EC4 | A negative fee exponent at price 0 or 1 divides by zero | false | Every real schedule has exponent 1; a buy at exactly 0 or 1 is not a tradable price; it would fail loudly, not silently | reject |
| EC5 | A negative fee rate or price above 1 lets a negative fee pass | false | Not shown reachable: rates seen 0.01–0.07, prices are probabilities; the Skill Test would then refuse it loudly | reject |
| BH9 | Fees in Markets with fees off are ignored | false | AD-12 reads fees only in fee Markets; on 0x091596 the 303 buys in no-fee Markets differ from shares × price by at most $0.0000045 | reject |
| BH10 | Sell fees not handled | false | Plan: Own Fees are on buys (PRD Glossary); Exit PnL and sell fees already deferred to Story 3.3 (deferred-work, spec-1-2) | reject |
| BH11 | A real taker fee of $0.0001 or less counts as 0 | low | Under a hundredth of a cent per fill | reject |
| BH13 | The 2% list/activity mismatch rate is not measured per window | low | Measured on the capture (3,724 of 3,800 CLOSED, 583 of 593 OPEN agree); the fixtures show no false gap; Story 2.6 runs the rule on all real Wallets | reject |
| BH16 | Fixture fee threshold $0.00001 differs from the $0.0001 tolerance | false | It only picks which Markets to cut; the builder's check runs on them unchanged | reject |

After the patches: 725 tests pass, 1 online test deselected; the fixtures cut again byte-identical.

## Design Notes

The 21 listed-only Positions of 0x091596 are neg-risk conversion outputs (no TRADE rows; the CONVERSION row names another Market). They come out as "share gap" now; Story 2.4 may relabel them. "Not fully read" from a capped read is already built (Story 2.2); a refused read raises and writes no snapshot, so nothing new is needed for it. The UX card shows "Polymarket's two lists disagree" for both list reasons (Epic 3).

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass (695 before, 725 after review).
- `uv run liquidoracle load-sample` -- expected: 1,005 Sample Wallets loaded.
