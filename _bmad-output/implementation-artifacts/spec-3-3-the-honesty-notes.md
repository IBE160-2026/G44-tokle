---
title: 'Story 3.3: The honesty notes'
type: 'feature'
created: '2026-11-24'
status: 'done'
baseline_commit: '834e36b92bab14d3cfa1febcf874b0c28b334ac1'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Verdict page shows a Verdict but nothing about what the test cannot see: how much rests on one bet, early sales, bets left out, fees not counted, the 2,000 window, linked bets, the Seed (FR-11, UX-DR29, UX-DR15). The figures exist in the Position builder's record, but `services/fetch.result_of` drops that record and keeps only the Skill Test result (epic-3 known gap).

**Approach:** `result_of` also returns the Position set and whether the window was capped. A new `services/honesty.py` turns them into finished text from `core/phrases` (like `services/chart.py`), and `verdict.html` shows the Exit PnL warning in the Verdict card and the card "What this test can't see" after the chart card, also for *Not enough data*.

**Decisions (Edvard, 2026-11-24, at spec time):**
- Window line drops N (AI rec): the window stops reading at 2,000 by design (AD-7), so N is unknown. The snapshot stores a `window_capped` flag (schema 5; the local database is rebuilt, `load-sample` runs again) and the line reads "Based on the latest 2,000 bets; older results are not included." PRD FR-11, EXPERIENCE.md and epics 3.3 are updated first, with the reason. Rejected: reading the whole history (slow; impossible offline), "of at least N".
- The +1 (his 3.2 note) is explained in About's JavaScript-only paragraph (AI rec), where the tail label also appears only: "The odds above count this Wallet's own result as one more replay, so they read a little less rare than this count and never claim zero." EXPERIENCE.md updated.
- "N of M positions held to resolution" counts bets not sold (AI rec), and HE ADDED: check the example adds up (it does: 641 + 139 + 287 + 95 + 6 + 5 = 1,173; 939 held) and that still-open bets never count as held (checked: the window holds only closed Markets, 0 open on every stored Wallet; Polymarket's "OPEN" list means not redeemed). Then, on a follow-up question, not-fully-read bets are left out of both N and M (AI rec). So M = window − not fully read; N = M − sold before resolution − Slivers. M = 0 → "No bet's history was read in full, so this cannot be counted."
- Exit PnL total = tested bets, Slivers and bets sold before resolution only, no sell fees (AI rec; PRD Glossary formula). Split-or-merged and other left-out bets are out: their Entry Price is not real. Closes the Story 1.2 deferred item.
- The spec is kept whole (about 2,200 tokens; AI rec), and approved with "approve and continue".

## Boundaries & Constraints

**Always:** Every number from the Position set or the result (AD-11), every sentence from `core/phrases` (AD-25). Card always shown, never collapsed; three columns, stacking below 900 px; then the "Left out of the test" block; then "Computed on … · Seed 44" from `result.scope` and `result.seed`. Exit PnL warning only when Exit PnL in whole cents < 0, with ⚠ hidden from screen readers and a hidden "Warning: "; the over-10% sentence uses the same style and hidden word. Warning tokens `--warning-bg/-border/-ink` in both theme blocks (DESIGN.md values); forced colours keep a visible border. Limits text and "This is not financial advice." word for word from the mockup. Page order: Verdict card, chart card, honesty card (UX-DR19).

**Never:** Recompute positions or money in a template or in `services/lookup`. Change the Skill Test, the Verdict, Real PnL or the builder's rules. Touch hover/lift polish (3.4). JavaScript for this card.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Share | Real PnL > $0, share ≤ 100% | "70%" + "of the Real PnL came from the single largest bet." | N/A |
| Over 100% | coin-flipper with Real PnL $8, largest $87 | "More than all of the Real PnL came from the single largest bet ($87); the other bets lost money overall." | N/A |
| Real PnL ≤ $0 | favourite-buyer (−0.000…1), coin-flipper-0000 | "Largest single bet: $10" | Real PnL compared in whole cents |
| No bets | 0xd218e4: 2,000 not fully read | "No resolved bets to measure."; held column's M = 0 sentence; "2,000 not fully read"; over-10% sentence (100%) | N/A |
| Stop-loss | stop-loss-trader | warning; "33 of 100"; "Shares sold before resolution: −$1,675 (Exit PnL)." | N/A |
| No sales | sharp-trader | no warning; "100 of 100"; "No shares were sold before resolution." | N/A |
| Mixed reasons | 0xd3a6e5 | "939 of 1,173"; left out 5 unclear, 287 split or merged, 6 lists disagree, 95 sold; over-10% (34%) | N/A |
| Capped window | capped at 2,000 (0x94884d) | window line; "Computed on the latest 2,000 bets · Seed 44" | N/A |
| Not capped | 0xd3a6e5 | no window line; "Computed on all 1,173 bets · Seed 44" | N/A |
| Linked over 20% | uncoupled_share 0.34 | linked-bets note | N/A |
| Fees failed | 3 fees, $0.40 | "3 fees did not match the Market's fee schedule and were not counted (less than $1)." | 0 → "Every fee matched the Market's fee schedule." |

</frozen-after-approval>

## Code Map

- `src/liquidoracle/records.py` -- `PositionSet` (window_size, left_out_share, failed_fee_count/total, excluded_counts exist): add `exit_pnl`, `read_count` (M), `held_count` (N), `largest_bet` (max s(o−p) − Own Fees over tested + Slivers; None when none). `Window`: add `capped: bool = False` last.
- `src/liquidoracle/data/window.py:76-102` -- `capped = len(chosen) < len(candidates)`.
- `src/liquidoracle/data/schema.sql`, `data/store.py:29,43-58,191-223,250-290` -- `snapshot.window_capped INTEGER NOT NULL DEFAULT 0`, SCHEMA_VERSION 5, `finish_snapshot(..., window_capped=False)`, `Snapshot.window_capped`. Rebuild on mismatch exists.
- `src/liquidoracle/services/fetch.py` -- `fetch_wallet` passes `window.capped`; `StoredResult` gains `positions`, `capped`.
- `src/liquidoracle/core/phrases.py` -- every honesty sentence; `about_explore` sentence lives in `services/chart.py` → move its text to phrases if not already. `mostly_left_out` (core/positions) and `mostly_uncoupled` (core/skilltest) decide the two notes.
- `src/liquidoracle/services/honesty.py` (new) -- `HonestyNotes` + `honesty_notes(stored)`.
- `src/liquidoracle/services/lookup.py:111-133,301-314` -- `WalletPage.notes`; `_verdict` builds it for every Verdict.
- `src/liquidoracle/web/templates/verdict.html` -- warning in `.stats-row` beside `.stats`; honesty `<section aria-labelledby>` after and outside `{% if page.chart %}`.
- `src/liquidoracle/web/static/css/app.css` -- `.stats-row`, `.warning`, `.limits-grid` from `mockups/verdict.html:144-158,254-263,340-342`.
- Tests: `test_phrases.py`, `test_honesty.py` (new), `test_store.py`, `test_window.py`, `test_web.py`, `test_wording.py`.

## Tasks & Acceptance

**Execution:**
- [x] Plan docs: PRD FR-11 window line, EXPERIENCE.md (window line, About sentence, held count), epics 3.3, memlogs; deferred-work and issues.md items closed.
- [x] `records.py`, `window.py`, `schema.sql`, `store.py`, `fetch.py` + tests -- capped flag and Position set reach the page.
- [x] `phrases.py`, `chart.py` + tests -- every sentence above, edge cases, the +1 sentence.
- [x] `services/honesty.py` + `tests/test_honesty.py` -- matrix rows on Synthetic and planted Position sets.
- [x] `lookup.py`, `verdict.html`, `app.css` + `tests/test_web.py`.
- [x] `README.md` -- honesty notes in the stage 1 features; rerun `load-sample`.

**Acceptance Criteria:**
- Given any Verdict page incl. *Not enough data*, when it renders, then "What this test can't see" follows the chart card (or the Verdict card when there is no chart) with all three columns, the left-out block and the computed-on line.
- Given stop-loss-trader, when read by a screen reader, then "Warning:" comes before the warning text; sharp-trader has no warning.

## Implementation Notes

- Built directly in the main session (Edvard: helper agents for review only). 1,019 tests pass (967 before).
- Plan first: PRD FR-11 (window line, N of M, Exit PnL set) and decision-log entry, EXPERIENCE.md (About sentence, held count, window line), epics 3.3 (AC line and a "settled at spec time" note), PRD and UX memlogs; the Story 1.2 and Story 3.2 deferred items marked resolved.
- `PositionSet` gained `read_count`, `held_count`, `exit_pnl`, `any_sold`, `largest_bet`; `Window.capped` (= fewer chosen than candidates, so a straddling Market that leaves the window under 2,000 still counts as capped); `snapshot.window_capped` (schema 5); `StoredResult.positions` and `.capped`. `load-sample` rerun: 1,015 Wallets in 24 s.
- `phrases`: `share`, `small_money`, `largest_bet` (label, figure, sentence), `held`, `exit_line`/`exit_parts`, `exit_warning_applies` (whole cents), `left_out`, `fees_not_counted`, `mostly_left_out_sentence`, `linked_bets_note`, `window_line`, `computed_on` (lookup scope only; other scopes raise until Epic 4), and the fixed texts. `services/honesty.py` builds `HonestyNotes`; `WalletPage.notes` is set for every Verdict.
- Column 1 layout: the amount case shows "Largest single bet:" as a small label over the amount as the figure, so it reads as EXPERIENCE.md's "Largest single bet: $3,200" and still uses the `stat-figure` style DESIGN.md asks for. Over 100%: the amount as figure plus the sentence.
- Found on real data: 0x94884d's and 0x091596's best bet made about a cent, so the column read "Largest single bet: $0"; it now reads "a gain of less than $1", like the Exit PnL rule.
- Found in the browser: "−$1,675" broke after the minus sign in a narrow column. The amount is now a bold `nowrap` span, as in the mockup (`exit_parts`).
- The over-10% sentence shows for *Not enough data* too (0xd218e4: 100%), as FR-11 says every Verdict card.
- Browser check (throwaway Playwright script driving the installed Edge, app on port 8045 because 8044 was in use): stop-loss-trader at 1280 (dark, light), 600 and 360 px; 0xd3a6e5, 0xd218e4, thin-wallet at 1280. The honesty card fits at every width; at 360 and 600 px the page still scrolls sideways because of the Verdict header (address card beside the hero), the existing "header stacking" item deferred to Story 3.4.
- AI slips: a CSS comment with a minus-sign amount tripped the AD-25 scan (same as Story 3.1); one test patched `positions_near`'s limit, which `fetch_wallet` overrides (test corrected, code was right); the baseline hash was first typed wrong and fixed from `git rev-parse`.

## Spec Change Log

## Review Triage Log

Review 1 (2026-11-24): blind hunter (18 findings), edge-case hunter (10), verification gap (2 + 1 other). 31 findings, 8 groups patched, 1 deferred, the rest rejected.

| # | Layer | Finding | Verdict | Evidence | Route |
|---|-------|---------|---------|----------|-------|
| 1 | verif | Template branches for the "Largest single bet:" label, the window line and the linked note are never rendered in a test | medium | No Wallet in `test_web.py`'s fixture is capped, linked or shows the label; Jinja renders a wrong field as empty | patch G7 |
| 2 | verif | `any_sold` leaving out split-or-merged and unread sales is not pinned | low | The AD-11 test's set is True through the tested bet anyway | patch G7 |
| 3 | verif | Capped flag misses a walk stopped early with exactly `limit` collected | medium | Same as 6 | patch G3 |
| 4 | blind | `share()` rounds some halves down | medium | `0.285 * 100` is 28.4999…: "28%" (checked; also 0.145, 0.565) | patch G1 |
| 5 | blind | Over-100% branch can print "($0)" | low | Real PnL $0.30, largest $0.45 took that branch with `money()` | patch G2 |
| 6 | blind | `capped` misses a walk stopped early with exactly `limit` candidates | medium | Both clients ask `until` only while a page is left, so a stop means unread pages; `len(chosen) == len(candidates)` then said not capped. New stub-client test fails on the old rule | patch G3 |
| 7 | blind | Window line counts tokens found only in activity rows: "latest 2,003 bets" | medium | `window_size` includes them; 0xd3a6e5 has 30 such tokens (1,173 against 1,143 listed) | patch G4 |
| 8 | blind | With nothing read in full the card still says "No shares were sold…" and "Every fee matched…" | medium | 0xd218e4 showed both beside "cannot be counted" | patch G5 |
| 9 | blind | `held_count` counts unclear, not explained, share gap and only-in-activity bets as held | false | Edvard's spec-time decision fixes N = M − sold − Slivers (frozen); not a defect against the intent | reject |
| 10 | blind | PRD FR-11 bullet says "out of all Positions" then defines M as read ones | low | Self-contradicting sentence | patch G6 |
| 11 | blind | "missing from Polymarket's positions list" and the reason order are not in EXPERIENCE.md | low | Plan-first rule | patch G6 |
| 12 | blind | `largest_bet` repeats the per-bet PnL formula; `or 0.0` would hide a None | low | `skill_test` runs `_check` on the same bets first and refuses a missing outcome or price; a shared `Position.pnl` adds surface to Real PnL code | reject |
| 13 | blind | `exit_text` and `exit_parts` can drift | false | `exit_line` is `"".join(exit_parts(...))` | reject |
| 14 | blind | `"hidden" not in card` breaks once a card holds the over-10% warning | low | `visually-hidden` contains "hidden" | patch G7 |
| 15 | blind | Page-level cases untested | medium | Same as 1 | patch G7 |
| 16 | blind | 0xcf0d7f's −$195,091 in the decision log is not tested | low | Cheap to pin | patch G7 |
| 17 | blind | After-part and Watchlist window wording not built nor recorded | low | No such result exists before Epics 4 and 5 | defer |
| 18 | blind | The +1 sentence lives in `services/chart.py`, not `core/phrases` | false | AD-25 is about number phrases; the chart's fixed texts live in `chart.py` since Story 3.1 | reject |
| 19 | blind | Spec and logs missing from the diff | false | Spec left out on purpose; logs come at the end of the session | reject |
| 20 | blind | `SMALL.get(name) or coin_flipper(0)` hides a misspelt name | low | Direct correction | patch G7 |
| 21 | blind | `.figure-label + .figure { margin-top: 0 }` does nothing | low | `.limits-grid .figure` already sets margin 0 | patch G8 |
| 22 | edge | `share()` half rounding | medium | Same as 4 | patch G1 |
| 23 | edge | "More than all…" when the largest bet beats Real PnL by a fraction of a cent | low | Fraction compared as floats | patch G2 |
| 24 | edge | Over-100% "$0" | low | Same as 5 | patch G2 |
| 25 | edge | Real PnL $0.01–0.49 shows "$0" but gets the share sentence | low | Cents test only | patch G2 |
| 26 | edge | "10% of its bets were left out" contradicts the over-10% trigger | false | The sentence states the share, not "more than 10%", and 10.4% is truly about 10% | reject |
| 27 | edge | Window count includes activity-only tokens | medium | Same as 7 | patch G4 |
| 28 | edge | Capped with zero chosen gives "latest 0 bets" | false | Needs one Market with more Positions than the 2,000 limit; a Market has at most 2 | reject |
| 29 | edge | Claim: "$0 or below" is judged in cents, the card shows dollars | low | Same as 25 | patch G2 |
| 30 | edge | Claim: the capped flag means older results were left out, but an early stop says not capped | medium | Same as 6 | patch G3 |
| 31 | verif | (other) same early-stop case | medium | Same as 6 | patch G3 |

Patches: G1 `share()` scales in decimal. G2 `largest_bet`: the amount form when Real PnL shows as "$0", over 100% compared in cents, over-100% amount via `small_money`. G3 `positions_near` records whether `enough` stopped the CLOSED walk; capped = stopped early or cut. G4 `StoredResult.listed` (positions-list rows); a capped window line and computed-on line use it. G5 with nothing read in full the Exit PnL line is left out, and with nothing in Real PnL the fee line too. G6 PRD FR-11 bullet reworded; EXPERIENCE.md reason list and order. G7 tests: coin-flipper's amount column on the page, a capped real Wallet's page, the linked note on the page, split/unread sales, 0xcf0d7f, the hidden-attribute check, the parametrised Wallets, rounding and the new largest-bet cases, the listed count. G8 dead CSS rule removed. 1,032 tests pass.

## Design Notes

My calls: share in whole percent; under 100% never reads "100%" (99%); under 1% reads "Less than 1%". Reasons in builder order, only those above 0: "not fully read", "unclear resolution", "split or merged", "missing from Polymarket's positions list", "Polymarket's two lists disagree", "sold before resolution", "not explained by the activity"; none → "Left out of the test: none." A non-zero amount that would show as "$0" reads "less than $1" (fees) or "a loss of less than $1" / "a gain of less than $1" (Exit PnL).

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (967 before).
- `uv run liquidoracle load-sample` -- expected: rebuilds the schema-5 database.

**Manual checks:**
- `uv run liquidoracle run --offline`: stop-loss-trader, sharp-trader, thin-wallet, 0xd3a6e5, 0x94884d, 0xd218e4; both themes; 360 px; forced colours.
