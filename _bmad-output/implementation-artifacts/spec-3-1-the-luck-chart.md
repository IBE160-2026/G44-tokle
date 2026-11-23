---
title: 'Story 3.1: The luck chart'
type: 'feature'
created: '2026-11-23'
status: 'done'
baseline_commit: '63d3462ef49361d8442ddf4526a78272cdb2939b'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Verdict page shows only the Verdict card. The user cannot see where the Wallet's Real PnL sits among the 10,000 replays, and the page has no text alternative for that picture (FR-9, PRD §8).

**Approach:** Under the Verdict card, a chart card (UX-DR24) with a server-rendered SVG luck chart (UX-DR25) drawn from the 42 bins and the exact counts the Skill Test already returns (AD-25). A pure `services/chart.py` turns a result into finished geometry and words (phrases from `core/phrases`), so the template only places them. No JavaScript in this story; `chart.js` is Story 3.2.

**Decisions (Edvard, 2026-11-23, at spec time; all AI recommendations):**
- Hint and About say only what is true without JavaScript; Story 3.2 adds the pointing/arrow-keys sentence and shows its hint only when `chart.js` runs. Hint: "Each bar is a range of results. The taller the bar, the more replays ended there." About, three paragraphs: (1) "Each replay (a Simulation) keeps this Wallet's N resolved bets, prices and stakes, but lets every bet win or lose by chance, at the odds its price implied. That is one way a trader with no edge could have done." (2) "The bars count how many of the 10,000 replays ended at each result. On average, luck alone lands at $0." — when Own Fees round to a non-zero dollar amount: "On average, luck alone lands at −$F, what this Wallet paid in fees." (3) "The blue line labelled "This Wallet" is this Wallet's Real PnL: what it made on the N bets it held to resolution. The more of the curve lies to its left, the harder the result is to explain by luck."
- Beyond every Simulation the marker label has two lines: "This Wallet: $X", then "above all 10,000 Simulations" (or "below …").
- The spec is kept whole (about 1,650 tokens).

## Boundaries & Constraints

**Always:** Bars, gridlines and marker line are one SVG (`preserveAspectRatio="none"`, `aria-hidden="true"`); text (ticks, marker label, end labels, y labels) is HTML placed by percent so it never stretches, all `aria-hidden`. Order of slots: low end bar, gap, 40 axis bars, gap, high end bar. Bar heights scale to a round y-maximum with gridlines. Marker x comes from the Real PnL on the axis (core already widens the axis to hold it). "Above all" means `at_or_above == 0`; "below all" means no Simulation at or below the Real PnL, from a new exact count `at_or_below` returned by core next to `at_or_above` (a Wallet that lost every bet ties the lowest replay and is not "below all"). Ticks every 5 axis bars (9); below 640 px every other one is hidden and short labels ("−$100k") shown; below 400 px the end labels are hidden; 200 px tall below 640. Every money or count text comes from `core/phrases`; tick values that are not whole dollars keep their cents ("$12.50"). Forced colours: bars `CanvasText`, marker `Highlight`. No inline `style` text containing a banned word (the wording test scans templates).

**Never:** Recompute bins or counts outside core. Add JavaScript, tooltips, the slider or the tail highlight (Story 3.2). Touch the honesty notes or the stored-lookup gap in `deferred-work.md` (Story 3.3). Show a chart card for *Not enough data*.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal | sharp-trader: Real PnL $2,000, at_or_above 1 | marker at the right axis edge, label "This Wallet: $2,000" | N/A |
| Above all | stop-loss-trader: $1,650, at_or_above 0 | label adds "above all 10,000 Simulations" | N/A |
| Below all | planted: every Simulation above the Real PnL | label adds "below all 10,000 Simulations"; axis holds the Real PnL | N/A |
| Ties lowest | planted: all bets lost | no "below all" | N/A |
| Real PnL $0 / −$0.00 | favourite-buyer | "$0", marker at centre | N/A |
| Marker near an edge | marker in outer 15% | label anchored to its inner side, never off the card | N/A |
| Not enough data | thin-wallet | no chart card | N/A |
| Tiny Wallet | bar width $0.25 | ticks "$1.25", end labels "−$5 or less" | N/A |

</frozen-after-approval>

## Code Map

- `src/liquidoracle/core/skilltest.py:110-130` `_engine`/`_Run`, `skill_test` -- add `at_or_below = count(totals <= real_cents)` beside `at_or_above`; None for *Not enough data*. `_bins` (line 247) is done: 42 `ChartBin`s, axis covers the Real PnL.
- `src/liquidoracle/records.py:225-262` `ChartBin`, `SkillTestResult` -- add `at_or_below: int | None` (only constructed in skilltest.py).
- `src/liquidoracle/core/phrases.py` -- add `axis_money(amount, short=False)`, the end-bar label, the marker label lines, the text alternative "This Wallet made $X on N resolved bets. In 10,000 replays with no edge, a result this good came up {odds}." and the About/hint sentences. A test forbids minus-sign amounts and odds phrases elsewhere under `src/`.
- `src/liquidoracle/services/lookup.py:111-122, 298-310` `VerdictCard`, `_verdict` -- add `chart: LuckChart | None` to `WalletPage` (None for *Not enough data*).
- `src/liquidoracle/web/templates/verdict.html` -- append the chart card section after `.verdict-card`.
- `src/liquidoracle/web/static/css/app.css` -- `--chart-bar` in both theme blocks (`test_ux_dr1_colour_tokens_match_design_md` checks against DESIGN.md); chart-card rules from `mockups/verdict.html:169-252`.
- `tests/test_web.py` -- `SHARP`, `THIN`, `FakeLookup`; stop-loss address via `synthetic.address_of("stop-loss-trader")`.

## Tasks & Acceptance

**Execution:**
- [x] `records.py`, `core/skilltest.py` -- `at_or_below` field and count -- exact "below all".
- [x] `core/phrases.py` + `tests/test_phrases.py` -- chart phrases and their tests.
- [x] `services/chart.py` (new) + `tests/test_chart.py` -- `luck_chart(result) -> LuckChart` (slots, bar heights %, y gridlines, ticks, marker x %, label anchor, end labels, words); matrix rows as tests, incl. planted above/below/tie Position sets through `skill_test`.
- [x] `services/lookup.py` -- attach the chart to the Verdict page.
- [x] `templates/verdict.html`, `static/css/app.css` -- chart card, About `<details>`, hint, text alternative box, breakpoints, forced colours.
- [x] `tests/test_web.py` -- card on sharp-trader and stop-loss-trader pages, none on thin-wallet, SVG and labels hidden from screen readers, no `<script>` added.

**Acceptance Criteria:**
- Given any Verdict with a p-value, when the page renders without JavaScript, then the chart card shows the title, About (closed), chart, hint and text alternative, in that order after the Verdict card.
- Given the same result twice, when the chart is built, then the output is identical and every bar count equals the stored bin's count.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (897 before).
- `uv run ruff check src tests` -- expected: clean.

**Manual checks:**
- `uv run liquidoracle run --offline`: sharp-trader, stop-loss-trader, favourite-buyer, a real Wallet; both themes; widths 1200, 600, 360 px.

## Implementation Notes

- Built directly in the main session (Edvard: helper agents for review only). 937 tests pass (897 before).
- `at_or_below` is counted in `_engine` with the same integer totals as `at_or_above`; no stored data or golden count changed.
- Layout: the SVG (view box 44 x 100, stretched) holds the bars, gridlines and the 3 px marker line (`vector-effect="non-scaling-stroke"`); the 12 px dot, the marker label, y labels, ticks and end labels are HTML placed by percent, so text never stretches. End labels sit on their own row under the ticks, so they never collide with the axis-end ticks.
- Gridlines use steps of 1, 2 or 5 times a power of ten, at most four above 0.
- Manual look (headless Edge, app in Offline Mode): stop-loss-trader at 1200, 600 px and inside 360/420 px frames (headless Edge will not open a window under about 500 px); coin-flipper in the light theme with About open. Chart correct in all. Seen but not part of this story: the Verdict header does not stack below 900 px, so at phone widths the page scrolls sideways; UX-DR10 responsive details are planned for Story 3.4.
- Two of my first test expectations were wrong and were corrected (not the code): the "below all" marker is not at the very edge because the round axis is wider than the Real PnL; favourite-buyer's Real PnL is -1.6e-13, not exactly 0.
- The phrase guard (`test_ad25_phrases_live_only_in_core_phrases`) caught example amounts with a minus sign in `services/chart.py` comments; changed to plain examples.

## Spec Change Log

## Review Triage Log

Review 1 (2026-11-23): blind hunter (12 findings), edge-case hunter (5), verification gap (3). 20 findings, 4 groups patched, 1 deferred, the rest rejected.

| # | Layer | Finding | Verdict | Evidence | Route |
|---|-------|---------|---------|----------|-------|
| 1 | edge | A centred label between 15% and 85% can spill past the card's right edge (no gutter on that side) | medium | At 360 px the plot is about 204 px; a 160 px label centred at 84% ends about 19 px past the card | patch G1 |
| 2 | edge | "Above all" inside a rounded axis sits near 73%, centred, and its two-line label overflows on phones | medium | The nice width can double the axis, so share 0.75 is reachable; a 200 px label centred there passes the card edge | patch G1 |
| 3 | edge | No "B" unit for $1 billion or more in short labels | low | No Wallet near that size; fix adds a branch | reject |
| 4 | edge | About says "blue line" but forced colours draws it in Highlight | low | True only in forced colours; wording approved by Edvard in the frozen intent | reject |
| 5 | edge | Claim: matrix says "never off the card", but only the enum is tested | medium | Same defect as 1 and 2 | patch G1 |
| 6 | blind | Spec says in-review, sprint status says in-progress | false | Step 5 of the build sets the sprint status to review; this is mid-workflow | reject |
| 7 | blind | The text alternative does not say "below all" (the label is hidden from screen readers) | low | True, but "below all" needs a Wallet worse than all 10,000 replays (rare); the fix changes the planned sentence. Told to Edvard | reject |
| 8 | blind | Marker label can run off the card at narrow widths | medium | Same defect as 1 | patch G1 |
| 9 | blind | About moves to the left when opened | low | The mockup keeps the summary right-aligned (`text-align: right`); the build dropped it | patch G3 |
| 10 | blind | About summary has no hover state | false | Hover states (UX-DR9) are planned for Story 3.4 (epics, Edvard 2026-11-20) | reject |
| 11 | blind | The no-script check only looks for chart.js | low | An inline script in the card would pass | patch G2 |
| 12 | blind | Below-all, anchor classes and short end labels untested on the page | low | Grep found no such assertions | patch G2 |
| 13 | blind | The header-not-stacking bug lives only in the spec notes | low | Pre-existing (Story 1.7 layout); Story 3.4 covers stacking below 900 px | defer |
| 14 | blind | No AI log or session log in the diff | false | Written at the end of the session, before commit (CLAUDE.md) | reject |
| 15 | blind | Chart copy in three places (hint, y title in services; title in template) | false | Matches the code base: message constants in services, fixed headings in templates; only number phrases must live in phrases.py (AD-25) | reject |
| 16 | blind | "or less"/"or more" end labels include the edge value itself | low | One cent at the edge, shown in whole dollars; wording set by the plan (UX-DR25) | reject |
| 17 | blind | A test docstring calls favourite-buyer's Real PnL "−0.0" | low | It is -1.6e-13 | patch G4 |
| 18 | verif | Bar heights and gridline labels not tied to each other in tests | low | Scaling by the peak, or wrong labels, would pass | patch G2 |
| 19 | verif | Short end labels never checked through the chart | low | Grep for low_short/high_short found nothing | patch G2 |
| 20 | verif | Anchor class and marker position not checked on the rendered page | low | Grep for "anchor-" found nothing in tests | patch G2 |

Patches: G1 `services/chart.py` edge zone 25%, and a two-line label always hangs towards the middle (+ tests; 360 px worst case checked by screenshot). G2 tests: gridline levels and labels, bar heights against the top gridline, short end labels, anchor class, marker x and no script in the card. G3 About summary right-aligned. G4 docstring.
