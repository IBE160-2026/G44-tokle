---
title: 'Story 3.2: Exploring the chart'
type: 'feature'
created: '2026-11-23'
status: 'done'
baseline_commit: 'caae91f0a3671e4ce7ab4e55305d485237fe5669'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The luck chart from Story 3.1 is a still picture. The user cannot see how many replays a bar holds, step through the bars by keyboard, or see which replays did as well as this Wallet (UX-DR26, UX-DR27, UX-DR28).

**Approach:** A plain `web/static/js/chart.js` enhances the server-rendered card, following the approved prototype script in `mockups/verdict.html`: a bar tooltip, the bars as one keyboard slider "Replays by result", the Wallet marker as a button that lights the tail bars and shows the tail label, and a one-time build-up. Every word and number it shows is rendered by the server from `core/phrases`; the script only shows, hides and moves things. Without JavaScript the card is exactly as in 3.1.

**Decisions (Edvard, 2026-11-23, at spec time; all AI recommendations):**
- With JavaScript the hint line becomes "Point at a bar, or use the arrow keys, to see how many replays ended there.", and About gets a fourth paragraph, shown only with JavaScript: "Point at a bar, or step through the bars with the arrow keys, to see its range and how many replays ended there. Point at or select the blue line to light up the replays that did as well as this Wallet or better." Without JavaScript both stay as in 3.1.
- The build-up animation is built now; it slips to Story 3.4 only if it fights the stretched SVG.
- `chart.js` is tested through Python tests of everything the server renders for it, a scripted headless-Edge check, and Edvard's own browser check; no JavaScript test runner now (that choice stays with Story 3.4, and `chart.js` joins the existing deferred item).
- The spec is kept whole (about 1,900 tokens).

## Boundaries & Constraints

**Always:** Tail label = the stored `at_or_above` ("2,500 of 10,000 replays did this well or better"; 0 → "No replay did this well or better", no bar lit; 10,000 → "All 10,000 replays did this well or better", every bar lit), never summed from bars. Lit bars run from the bar holding the Real PnL to the high end bar; the server computes that first index. Slider: Left/Down and Right/Up one bar, Page Down/Up ten, Home/End the ends; value text "$30,000 to $35,000: 289 replays" (end bars use the end labels). Tooltip: range, then the count in semibold; stays while pointed at and 300 ms after; Esc hides it; within 3 bars of the marker it moves aside, never over the dot or label. Marker button: hover or focus lights the tail, the marker and tail label are one hover area; click/Enter pins and announces "Highlight on: {tail sentence}"; second click, Esc or a slider step unpins and announces "Highlight off". Slider, button, tail label and explore hint are rendered `hidden` and shown only by `chart.js`. The drawing stays `aria-hidden`; the slider and button sit outside the hidden part. Colours: tail `--chart-tail`, active bar `--chart-active` (DESIGN.md, both themes); forced colours: both `Highlight`. Reduced motion: no build-up, no marker drop; colour changes instant. README lists `chart.js:` (AD-18).

**Never:** Money, counts or sentences written in `chart.js` (the AD-25 scan covers `.js`). Recompute bins or counts outside core. Change the text alternative. Touch honesty notes (3.3) or hover/lift polish (3.4). Add Node or a bundler.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal | sharp-trader, at_or_above 1 | "1 of 10,000 replays did this well or better", bars from the marker's bar lit | N/A |
| None reached | stop-loss-trader, at_or_above 0 | "No replay did this well or better", no bar lit | N/A |
| All reached | planted all-lost Wallet tying the lowest, at_or_above 10,000 | "All 10,000 …", all 42 lit | N/A |
| Real PnL on the top axis edge | marker x at the last axis edge | first lit index = last axis bar | N/A |
| No JS | script blocked | card identical to 3.1, no focusable slider or button | N/A |
| Not enough data | thin-wallet | no card, no script | N/A |
| Live lookup swap | fetching page replaced by the Verdict via `progress.js` | chart still enhanced | N/A |

</frozen-after-approval>

## Code Map

- `_bmad-output/planning-artifacts/ux-designs/ux-LiquidOracle-2026-10-16/mockups/verdict.html:220-243, 326-334, 545-570, 677-829` -- the approved prototype: CSS, markup and script for tooltip, slider, marker button, tail label, build-up. Adapt; its bars are divs, ours are SVG rects (build-up via `transform-box: fill-box; transform-origin: bottom`; the stretched SVG cannot move by px, so the line fades while the HTML dot and label drop 14 px).
- `src/liquidoracle/services/chart.py` -- `LuckChart`: add per-bar `range_text`/`count_text`, `tail_from` (first lit bin index; 42 = none), `tail_text`, `explore_hint`, `about_explore`, `marker_button_label` ("This Wallet: $X. Highlight the replays that did this well or better"). `_slots()` maps bins to slots.
- `src/liquidoracle/core/phrases.py:102-168` -- add `bar_range(low, high)` (via `axis_money`; end bars via `end_bar_label`), `replays(n)` ("1 replay", "289 replays"), `tail_sentence(at_or_above)`. `SIMULATIONS` from skilltest.
- `src/liquidoracle/web/templates/verdict.html:33-72` -- `.chart` is wholly `aria-hidden` today: move the attribute onto the drawing parts; add the hidden slider, button, tail label, tooltip, live region, explore hint, About paragraph; `data-range`/`data-count` on each rect; `<script src=chart.js defer>`.
- `src/liquidoracle/web/templates/fetching.html`, `static/js/progress.js` -- after its innerHTML swap (scripts inside do not run), `progress.js` calls `window.LiquidOracleChart.enhance(main)` if present; fetching page also loads `chart.js`.
- `src/liquidoracle/web/static/css/app.css:41,84,231-300,310` -- `--chart-tail`, `--chart-active` in both theme blocks (`test_ux_dr1_colour_tokens_match_design_md`), tooltip/tail-label/slider/button rules, forced colours, reduced motion.
- `tests/test_web.py:280-330` -- 3.1 tests asserting `"chart.js" not in page` and one `aria-hidden` `.chart` block must be updated, not deleted.
- `README.md:40-43` -- JS file list.

## Tasks & Acceptance

**Execution:**
- [x] `core/phrases.py` + `tests/test_phrases.py` -- range, replay count, tail sentence (three cases).
- [x] `services/chart.py` + `tests/test_chart.py` -- new fields; matrix rows incl. tail_from for normal, none, all, top edge.
- [x] `templates/verdict.html`, `templates/fetching.html`, `static/js/progress.js` -- enhancement hooks, all hidden by default.
- [x] `static/js/chart.js` (new) -- adapt the prototype; `enhance(root)` idempotent.
- [x] `static/css/app.css` -- tokens, states, build-up, reduced motion, forced colours.
- [x] `tests/test_web.py` -- rendered data, hidden parts outside `aria-hidden`, script tag, no money/phrases in `chart.js`, reduced-motion rule, README.
- [x] `README.md` -- `chart.js:` line.

**Acceptance Criteria:**
- Given a Verdict page with JavaScript, when the user tabs into the chart, then focus reaches the slider and then the marker button, each with a visible focus ring, and every step is announced.
- Given the same page without JavaScript, when it renders, then nothing focusable or hidden-by-script is visible and the card reads as in 3.1.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (942 before).
- `uv run ruff check src tests` -- expected: clean.

**Manual checks:**
- `uv run liquidoracle run --offline`: sharp-trader, stop-loss-trader, a real Wallet; mouse, keyboard, Esc, pin/unpin; both themes; reduced motion; 360 px.

## Implementation Notes

- Built directly in the main session (Edvard: helper agents for review only). 967 tests pass (942 before).
- The page holds every word: each bar carries `data-range`/`data-count`; `.chart` carries `data-marker-bar` and `data-tail-from`; the live region carries `data-highlight-on`/`-off`. `chart.js` builds the tooltip from text nodes (no `innerHTML`). A test reads every string literal in `chart.js` and fails on money, counts or the chart's sentences.
- `aria-hidden` moved from the whole `.chart` block onto each drawing part (SVG, y title and labels, dot, marker label, axis, end labels, tail label, tooltip), so the slider and the marker button can be reached. The 3.1 test was rewritten to check each part.
- Tail label side: right of the marker on the left half, left of it on the right half (`tail_left`), so it stays on the card; the mockup only showed a marker in the middle.
- Tooltip: beside the bar (away from the marker) within three bars of the marker, and also whenever its box would touch the marker's dot or label (measured), because the marker label can reach several bars sideways.
- Build-up on SVG rects: `transform-box: fill-box`, `scaleY`, `--i` per bar for the 4 ms stagger, only while `is-building`, so hover colour changes are never delayed. The stretched SVG's marker line fades in; the HTML dot and label drop 14 px. Ends at about 0.82 s.
- Live lookup: scripts in HTML swapped in by `progress.js` never run, so the fetching page also loads `chart.js` and `progress.js` calls `LiquidOracleChart.enhance(main)` after the swap. `enhance` marks a chart `data-enhanced` and skips it the second time.
- Browser check (throwaway Playwright script driving the installed Edge, app in Offline Mode; not in the repo): 45 checks pass, covering no JS, reduced motion, build-up, Tab order, every slider key, tooltip text = slider text, Esc, pin/unpin by Enter, click, Esc and slider, Highlight on/off, the tail for sharp-trader, stop-loss-trader and favourite-buyer, the tail label on the card and no tooltip over the marker at 1200, 600 and 360 px, and the 300 ms delay. A simulated `progress.js` swap also enhanced the chart.
- Found in the browser and fixed: the marker button's focus ring crossed the "This Wallet" label (the button began 12 px above the plot); it now starts at the dot's top with a 1 px ring offset (1 px clear at 1200 and 360 px), and is 24 px wide below 640 px.
- Known trade-off, as in the approved prototype: the bar right under the marker (sharp-trader's bar 40) is covered by the 28 px marker button, so pointing there lights the tail instead of showing that bar's tooltip; the slider still reaches it.
- My first expectation for sharp-trader's marker bar was wrong (4 replays); the page shows the stored 0 (the one replay at $2,000 or more sits in the end bar). The test was corrected, not the code.
- `ruff` is not a project tool; with the machine-wide settings it reports 86 findings before this story and 88 after (two more `re.S` in `tests/test_web.py`, the file's existing style).

## Spec Change Log

## Review Triage Log

Review 1 (2026-11-23): blind hunter (12 findings), edge-case hunter (11), verification gap (2 + 1 other). 26 findings, 9 groups patched, 1 deferred (already recorded), the rest rejected.

| # | Layer | Finding | Verdict | Evidence | Route |
|---|-------|---------|---------|----------|-------|
| 1 | blind | A side tooltip next to the marker runs off the card at the end bars | medium | sharp-trader: marker on bar 40, bar 41's side tooltip started past the plot's right edge | patch G1 |
| 2 | blind | Esc loses the slider's place | medium | Esc set `active` to -1; the next key stepped from the marker's bar while `aria-valuenow` still named the old bar | patch G2 |
| 3 | blind | No way to explore by touch | medium | A tap sends `pointerdown` but no `pointermove`; focus then showed the marker's bar, not the tapped one | patch G3 |
| 4 | blind | Bars stay at zero height if printed before the chart scrolled into view | low | `pre-build` is removed only by the IntersectionObserver; no print rule | patch G4 |
| 5 | blind | `marker_bar` copies core's binning rule | low | True, but drift would move the lit start by one bar only for a value on an exact edge; the fix adds a stored field to `SkillTestResult` | reject |
| 6 | blind | No spec, AI log or sprint update in the diff; Playwright checks thrown away | low | The spec is left out of the review diff on purpose; AI log and sprint status come at the end of the session. Keeping the Playwright script is offered to Edvard | reject |
| 7 | blind | The no-words test only sees double-quoted strings; `list * bool` hard to read | low | `'` or template strings would pass the scan | patch G5 |
| 8 | blind | Full stop added in the template; button name drops "above all"; `tail_left=False` untested | low | Full stop and the untested side are real; "above all" reaches the screen reader through the button's description ("No replay did this well or better") | patch G5, G6 (button: reject) |
| 9 | blind | Pointing at bars does nothing while the highlight is pinned | low | Unpinning on pointer movement would end every mouse pin as the pointer leaves the button; a click or tap on a bar now unpins (G3) | reject |
| 10 | blind | "Highlight on" heard twice (pressed state and live region) | low | EXPERIENCE.md and UX-DR27 ask for the announcement | reject |
| 11 | blind | README does not say how to select or pin the marker | low | It said "point at or select" only | patch G7 |
| 12 | blind | `.chart-bar` declared twice; BUILD_MS tied to CSS timings only in prose | low | Two rules a few lines apart | patch G8 |
| 13 | edge | Side tooltip off the card at the plot edge | medium | Same defect as 1 | patch G1 |
| 14 | edge | Side placement may still touch the dot or label | low | Not reached in the 1200/600/360 px sweeps, but the new placement checks every place | patch G1 |
| 15 | edge | Arrow after Esc or the tail steps from the marker's bar | medium | Same defect as 2 | patch G2 |
| 16 | edge | Alt/Ctrl/Meta + arrow keys swallowed (Alt+Left is Back) | low | `preventDefault` on any arrow | patch G9 |
| 17 | edge | A tap shows the marker's bar | medium | Same defect as 3 | patch G3 |
| 18 | edge | Print before in view leaves no bars | low | Same defect as 4 | patch G4 |
| 19 | edge | Reduce motion switched on after load still animates once | low | Needs a setting change between load and scroll; fix adds a branch | reject |
| 20 | edge | Esc listeners pile up across `progress.js` swaps | low | One swap per lookup; a detached chart's listener returns at once | reject |
| 21 | edge | The lit bars include replays in the marker's bar that did worse | false | EXPERIENCE.md (Wallet marker): every bar from the Wallet's bar rightwards lights, and the number is never summed from the bars because that bar is only partly above | reject |
| 22 | edge | `result.simulations` may differ from `SIMULATIONS` | false | `skill_test` sets `simulations=SIMULATIONS` for every result with a p-value; only those get a chart | reject |
| 23 | edge | The moved-marker test keeps `at_or_above`, so it never reaches the none/all branches | false | Those branches are tested on real results (stop-loss-trader, the all-lost planted Wallet) | reject |
| 24 | verif | `tail_left=False` never asserted | low | Only sharp-trader's `is-left` was checked | patch G6 |
| 25 | verif | chart.js behaviour and the progress.js handoff have no automated test | medium | No JS runner (Edvard's call 3a) | defer (existing item, updated this story) |
| 26 | verif | Lit bars can show more than the sentence's count | false | Same as 21 | reject |

Patches: G1 `placeTip` tries above, beside away from the marker, then beside towards it, taking the first place on the card and clear of the dot and label. G2 the slider keeps its value (`current`) apart from the tooltip. G3 `pointerdown` shows the tapped or clicked bar and ends a pin, and a finger's `pointerleave` no longer hides the tooltip (found while checking G3: touch fires it on every tap). G4 `@media print` draws a `pre-build` chart in full. G5 tests: no `'` or template strings in chart.js; an explicit `if` in the frame test; no full stop after the tail sentence in the template. G6 `tail_left` asserted for every marker position. G7 README: Tab, Enter, click and Esc. G8 one `.chart-bar` rule; BUILD_MS notes the CSS timing. G9 modifier keys pass through. Checked again in Edge: 45 + 17 checks (every tooltip at 1200, 600, 360 px for three Wallets, Esc keeps the place, Ctrl+Right ignored, click on a bar unpins and selects it, touch tap selects the tapped bar and keeps it after 600 ms, print). 967 tests pass.
