# Story 3.2: exploring the chart

## 2026-11-23 kl. 12:46 — Edvard Tokle

### Oppgave
Switch to main after PR #32 (3.1) was merged and build Story 3.2: make the luck chart explorable (tooltip, keyboard slider, marker button with the tail highlight, build-up animation).

### Plan
- First commit set 3.1 `done` (caae91f).
- `bmad-build` with spec [spec-3-2-exploring-the-chart.md](../../_bmad-output/implementation-artifacts/spec-3-2-exploring-the-chart.md). Adapted the approved prototype script in `mockups/verdict.html`. Edvard's calls: 1a (with JavaScript the hint swaps and About gets a fourth paragraph), 2a (build-up now), 3a (no JS test runner yet; Python tests + scripted Edge check + his own check), spec kept whole (~1,900 tokens). Built in the main session; helpers only for review.

### Resultat
- New `static/js/chart.js`; the server writes every word and number (per-bar range and count, marker bar, first lit bar, tail sentence, Highlight on/off), so the script writes none. `aria-hidden` moved from the whole chart onto each drawing part. `progress.js` hands a swapped-in Verdict to `chart.js`. README lists `chart.js`.
- Browser (throwaway Playwright script driving Edge, Offline Mode, not in the repo): 45 + 17 checks pass. Found and fixed there: the marker button's focus ring crossed the "This Wallet" label.
- Review: 26 findings, 9 groups fixed (tooltip stays on the card, Esc keeps the slider's place, touch tap shows the tapped bar and keeps it, print draws the chart, modifier keys left to the browser, README, tests), 1 deferred (JS test, joins the 2.5 item), rest rejected. 967 tests pass (942 before).
- Kept as in the prototype: the bar right under the marker is covered by the marker button; the arrow keys reach it.
- Edvard's own check: asked why "1 of 10,000" and "about 1 in 5,000" differ (count vs p-value with +1); chose to note it for Story 3.3.
- Commits: caae91f, 3da1531 (code + tests), f4bfef2 (spec, review log, deferred), c76e39a (AI log). Story 3.2 is `review`.
- Closed: set 3.1 `done` (caae91f).

### Åpne punkter
- Story 3.3: the tail label's raw count ("1 of 10,000") vs the odds line's p-value ("about 1 time in 5,000"); decide whether to explain the +1 (Edvard's call c, `deferred-work.md`).
- Story 3.4: `chart.js` has no automated test either; added to the existing `progress.js` item (`deferred-work.md`).
- Set Story 3.2 to `done` in `sprint-status.yaml` when its PR is merged.
