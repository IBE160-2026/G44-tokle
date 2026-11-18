---
title: 'Story 1.5: Number phrases in one place'
type: 'feature'
created: '2026-11-18'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '0a467aa00e1ed0d95c4079a788c68960e36663c6'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 1.4 returns a p-value, a Real PnL and a tested count, but nothing turns them into the words the user reads. If each page phrased them itself, the card, the chart text and later the Explanation and its FR-24 check could disagree.

**Approach:** Add one pure module `core/phrases.py` (AD-25) with three functions: the FR-8 odds phrase, the UX-DR14 money format, and the FR-10 *Not enough data* sentence. Later stories add their phrases here.

## Boundaries & Constraints

**Always:**
- Odds (FR-8): N = 1/p; N ≥ 10 to 2 significant figures, N < 10 to a whole number; digits grouped with commas ("about 1 time in 2,500"). "fewer than 1 time in 10,000" when p ≤ 1/10,001 **or** N rounds to 10,000 or more, so "about 1 time in 10,000" never appears. "more than half the time" when p > 0.5; exactly 0.5 is "about 1 time in 2".
- Money (UX-DR14): `$` with comma groups, a real minus sign U+2212 before the `$`, no "+" and no colour. Zero is `$0`, never `−$0`.
- *Not enough data* (FR-10): "12 resolved bets; at least 30 are needed for a Verdict (18 more)"; one bet reads "1 resolved bet". The 30 and the 10,000 come from `core/skilltest` (`MIN_RESOLVED`, `SIMULATIONS`), not typed again.
- Rounding halves go away from zero (decimal), never Python's round-half-to-even.
- `core` stays pure: stdlib and `records` and `core` only (AD-1). Every test names its FR/AD.

**Never:**
- No templates, Jinja filters or pages (Story 1.7), no Copy Test, Follower Return, Minimum Luck Passes or largest-bet phrases (their own stories add them).
- No `git add .`, no merge, no `gh`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| FR-8 examples | p 0.0033, 0.0099, 0.25, 0.27, 0.45, 0.11 | about 1 time in 300 / 100 / 4 / 4 / 2 / 9 | N/A |
| Floor | p 1/10,001; p 0.0001; p 0.0001004 (N 9,960) / p 0.000101 | fewer than 1 time in 10,000 (first three) / about 1 time in 9,900 | N/A |
| Large N | p 2/10,001; p 0.0004 | about 1 time in 5,000 / 2,500 | N/A |
| Half | p 0.5; p 0.5001; p 1.0 | about 1 time in 2 / more than half the time / more than half the time | N/A |
| Near 10 | p 0.104 (N 9.6) | about 1 time in 10 | N/A |
| Money | 12340; −1240; 0; −0.4; 1650; 40180.5; −0.5 | `$12,340`, `−$1,240`, `$0`, `$0`, `$1,650`, `$40,181`, `−$1` | N/A |
| Not enough data | 12; 1; 0; 29 | "… (18 more)"; "1 resolved bet; … (29 more)"; "0 resolved bets; … (30 more)"; "… (1 more)" | N/A |
| Bad input | p ≤ 0, > 1, NaN, None; money NaN/inf; count < 0 or ≥ 30, bool | — | ValueError |

**Decisions (Edvard, 2026-11-18):**
- Money is shown in whole dollars, always (AI's option A): `$40,181`, and a Real PnL of $0.40 shows `$0`. Rejected: cents always (busier card) and cents below $100 (two looks). The stored and tested Real PnL stays exact to the cent; only the display rounds. The spine's Money line is reworded to match, with a memlog entry, before the code.

</frozen-after-approval>

## Code Map

- `src/liquidoracle/core/skilltest.py` -- `SIMULATIONS`, `MIN_RESOLVED` to import; `verdict_for` gives the Verdict, phrases never decide it.
- `src/liquidoracle/records.py` -- `SkillTestResult.p_value` (None for *Not enough data*), `tested_count`, `real_pnl`; read only.
- `tests/test_architecture.py` -- AD-1 import rule already covers `core`; line 164 already plants `records → core.phrases` as forbidden.
- `tests/test_skilltest.py` -- test naming and `pytest.mark.parametrize` style to copy.

## Tasks & Acceptance

**Execution:**
- [x] plan first -- spine Consistency Conventions › Money: "shown in whole dollars (UX-DR14)" + spine memlog entry -- CLAUDE.md: plan before code.
- [x] `src/liquidoracle/core/phrases.py` -- `odds(p)`, `money(amount)`, `not_enough_data(tested_count)` -- FR-8, FR-10, UX-DR14, AD-25.
- [x] `tests/test_phrases.py` -- the matrix; every FR-8 example from the PRD and epics; a check that the Story 1.3 Wallets' p-values phrase without error; a source scan: no other module under `src/` contains "1 time in" or U+2212 -- AD-25.
- [x] `sprint-status.yaml` -- 1-5 to `review` at the end.

**Acceptance Criteria:**
- Given `uv run pytest`, then all tests pass with sockets blocked.
- Given a phrase added outside `core/phrases.py`, then the source-scan test fails.

## Implementation Notes

- Implemented directly in the main session; subagents only for the review (Edvard's standing call).
- Plan change first: spine Money line ("shown in whole dollars by `core/phrases`") and an architecture memlog entry for Edvard's choice A.
- `core/phrases.py`: `odds`, `money`, `not_enough_data`, plus `MINUS`, `FLOOR_PHRASE`, `MORE_THAN_HALF_PHRASE` for later stories. Numbers go through `Decimal(repr(float))`, so numpy floats and ints are accepted and halves round away from zero.
- Not in the plan, added by the AI: a sweep over all 10,001 possible p-values (no decimal, never "about 1 time in 10,000"); p 0.4 reads "about 1 time in 3" (N exactly 2.5, rounded up); the scan also looks for "half the time", "&minus;" and "needed for a Verdict"; a planted-phrase test proves the scan can fail (five planted files) and that it skips `core/phrases.py`.
- With Seed 44 the Story 1.3 Wallets read: sharp trader "about 1 time in 5,000", stop-loss trader "fewer than 1 time in 10,000", favourite buyer "more than half the time", hand-check and thin wallet the Not enough data sentence (10 and 29 bets).
- Full suite: 360 passed, 1 deselected (293 before + 67 new).
- After review: 364 passed, 1 deselected. The AI's first expected value for `money(1e30)` was wrong (it guessed the float's binary value; `repr` gives exactly 10^30) and was corrected.

## Spec Change Log

## Review Triage Log

Review pass 1 (2026-11-18). Three subagent reviewers on the diff since the baseline (spec and sprint status left out): blind (B), edge-case (E) and verification-gap (V). V found no verification gaps.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | V, E, B: the module docstring says every number phrase lives here and a test catches any phrase written elsewhere; the scan cannot see a hand-made money format such as `f"${x:,.0f}"` | low | True: the markers find odds, *Not enough data* and minus text only | patch: docstring narrowed to what the scan checks, lists the phrases later stories add, and says pages must call `money()`; markers also catch `&#8722;$`, `&#x2212;$` and `−$` |
| 2 | E, B: any U+2212 under `src/` fails the scan, also a formula like `s·(o − p)` in a docstring | low | True by construction; a later story would hit it | patch: the minus markers need a following `$`; a planted formula file is allowed, a planted `−$` is caught |
| 3 | E, B: `money(1e28)` raises `decimal.InvalidOperation`, not ValueError | low | Reproduced: `quantize` passes decimal's 28 digits | patch: `to_integral_value`, which has no digit limit; tests for 1e30 and −1e28 |
| 4 | B: `odds` divides in binary floats, so a p at a halfway N can round to the wrong side | medium | Reproduced over p = k/100,000: p 0.00016 gave "about 1 time in 6,200"; N is exactly 6,250, which rounds up to 6,300 | patch: decimal division; test for 0.00016 |
| 5 | B: the spine's Money row still says the Real PnL is "shown … to the cent" | low | True, the old sentence contradicted the new opening | patch: "stored and checked to the cent, and shown from it in whole dollars"; memlog entry |
| 6 | B: AD-25 does not bind FR-10 or UX-DR14 or list the *Not enough data* sentence, so the trace stops at the story | low | True | patch: AD-25 binds FR-10 and UX-DR14 and lists the sentence; same memlog entry |
| 7 | B: the 10,001-p sweep does not check that N never grows as p grows | low | True; cheap to add to the existing loop | patch: monotonic check in the sweep |
| 8 | B: the Story 1.3 phrase test looks like a hand answer but its odds are regression values | low | True: amounts and counts are `expected.json`, the odds follow from Story 1.4's golden counts | patch: docstring says which is which |
| 9 | E: an int too large for a float (10**400) raises OverflowError, not ValueError | low | True, but no Real PnL or p-value is ever an int that size and the fix adds a try/except | rejected |
| 10 | E: a Bonferroni-adjusted p above 1 raises ValueError | false | Nothing passes adjusted p-values yet; Bonferroni values are capped at 1 by definition (min(1, m·p)), and Epic 7 builds that call | rejected |
| 11 | E: files with suffixes `.j2`, `.jinja`, `.svg`, `.json` are not scanned | low | True, but the app's templates are `.html` (Flask, AD-1) and no such files exist under `src/` | rejected |
| 12 | B: "N resolved bets" from `tested_count` could differ from the stats line's count | false | Both are the tested count: Slivers are not bets (Glossary, Story 1.2), and Story 1.7's stats line reads the same `tested_count` | rejected |
| 13 | B: chart axis labels and the chart text alternative have no route through `core/phrases` | false | No such labels exist yet; AD-25 already says every money phrase comes from this module, so Story 1.7 passes them in, and the scan will catch a `−$` written in JS | rejected |
| 14 | B: no test for Bonferroni p-values off the 10,001 grid, or for a stored p read back | false | Neither exists yet (Epic 7, Story 1.6); `odds` takes any p in (0, 1] and the matrix covers off-grid values | rejected |
| 15 | B: spec and sprint status missing from the diff; no AI log yet | false | Left out of the review diff on purpose; the AI log is written at the end of the session, before any commit | rejected |

## Design Notes

- Names are short because templates will call them (`phrases.odds(result.p_value)`).
- p is taken as given, so Domain Verdicts can pass their Bonferroni-adjusted p later (FR-20) without a new function.

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass
- `uv run pytest tests/test_phrases.py tests/test_architecture.py -v` -- expected: all pass
