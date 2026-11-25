# Epic 3 Context: A Verdict you can trust

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

The user sees, on the Verdict page, the luck chart with the Wallet's marker and its always-visible text alternative, and the honesty notes that say what the test cannot see. The page works by keyboard and screen reader, in both themes and at any width. Stage 1 is done at the end of this epic: all tests pass in CI and the README covers every stage 1 feature, so the project could be handed in here. Its target was 20 to 23 November 2026. If it runs late, the chart's build-up animation slips first, then the tooltip details; the text alternative and the honesty notes never slip.

## Stories

- Story 3.1: The luck chart
- Story 3.2: Exploring the chart
- Story 3.3: The honesty notes
- Story 3.4: Theme, copy and finish
- Story 3.5: Accessibility check, and stage 1 done

## Requirements & Constraints

- **Luck chart:** a histogram of the Luck Distribution in dollars with the Real PnL marked. The axis always includes the Real PnL; when the Real PnL is beyond every Simulation the marker reads "above all 10,000 Simulations" (or "below …"). Checked by a planted Real PnL above the largest Simulation.
- **Not enough data:** shows the count and how many more bets are needed; no odds phrase and no chart. The honesty notes are still shown.
- **Honesty notes on every Verdict card:** share of Real PnL from the largest Position; N of M held to resolution and Exit PnL; a warning when Exit PnL < 0; the 2,000-window line ("Based on the latest 2,000 bets; older results are not included."; "first 2,000" for an after part; no total, since the window stops reading at 2,000); M counts bets read in full, N those of them not sold before resolution; Exit PnL sums tested bets, Slivers and bets sold before resolution; left-out counts per reason and the over-10% sentence; fees that failed the fee check with their total; the over-20% undetected-links note; the Seed; the fixed limits note and "This is not financial advice." Checked: the stop-loss Synthetic Wallet shows the warning; Exit PnL ≥ 0 or no sales shows none.
- **Accessibility (target WCAG 2.1 AA):** the Verdict is always text, never colour alone; the chart has a visible text alternative with the Real PnL and the odds phrase; bars and axes are hidden from screen readers. One main heading per page, headings in order, labels tied to fields, `lang="en"`, skip link first, forced-colours rules, no page needing JavaScript.
- **Words:** on screen a Simulation is a "replay" (except the FR-9 marker label, which keeps "Simulations"), a Position is a "bet" or "resolved bet". Banned and avoided words are tested.
- **Read-only:** no Copy or Follow buttons, alerts or advice.
- **Stage end:** all tests pass in CI on the three systems; the README lists every stage 1 feature, the commands, how keys are set in `.env`, and each JavaScript file and what it does.

## Technical Decisions

- **Server-rendered first:** Flask + Jinja2 pages are complete without JavaScript; the luck chart is server-rendered SVG. Plain JS files in `web/static/js/` only enhance: `chart.js` (build-up, explore, marker), `copy-address.js`, `theme.js`, `progress.js`. No Node, no bundler.
- **Chart data comes from core, stored with the result:** `core` returns the chart bins and the exact count of Simulations at or above the Real PnL, and a result stores them outright. Templates never recompute bins or counts. The bins are 40 equal bars on a round dollar axis centred on $0, wide enough for the Real PnL and the middle 99.8% of the Simulations, plus two end bars holding everything beyond the axis. They count the Simulation totals with Own Fees taken off.
- **One phrase module:** every user-facing number phrase (odds phrase, money as `$12,340` / `−$1,240` with a real minus and no colour, counts, the largest-bet sentence and its edge cases, the *Not enough data* sentence) comes from `core/phrases.py`.
- **One Position builder:** honesty-note numbers (window size, left out per reason, tested count, failed fees, left-out share, uncoupled share) come from the one Position builder's record, not from the template.
- **Stored lookup (resolved in Story 3.3):** the stored lookup now also returns the Position set and whether the window was capped, so the honesty notes read failed fees, left-out share and the rest from it.
- **Result keys:** every result carries a scope (`lookup` here), cut-off, Seed (44 for the Sample Dataset) and `fetch_id`; pages read by the full key and show "Computed on … · Seed 44" from the result itself.

## UX & Interaction Patterns

- **Verdict page order:** Verdict card, (Explanation, stage 3), chart card, honesty notes card, (Domain table, stage 3).
- **Chart card:** title "Simulated results" with "(10,000 replays with no edge)" in small text; "About this chart" disclosure top right, in place, closed by default, three plain sentences (what one replay is, what the bars count, what the blue "This Wallet" line is, and that numbers show by pointing or with the arrow keys); the chart; a one-line muted hint; the text alternative in its own neutral-tint box: "This Wallet made $X on N resolved bets. In 10,000 replays with no edge, a result this good came up {odds phrase}.", plus "That is below all 10,000 replays." when the Real PnL is below every Simulation (Edvard, 2026-11-25)
- **Luck chart look:** grey bars just reaching 3:1 contrast, faint gridlines, y-axis "Number of replays", x-axis in dollars; the marker is a 3 px accent line with a 12 px dot and the semibold accent label "This Wallet: $X" above it. About 240 px tall (200 px below 640 px). Below 640 px short axis labels ("−$100k") and every other tick dropped; below 400 px the two end labels are hidden. End bars labelled "−$195,000 or less" / "$195,000 or more". Forced colours: bars in `CanvasText`, tail and active bars in `Highlight`. Blue carries no profit/loss meaning; no green, no red, no gradients.
- **Exploring (JS):** bar tooltip with range and count, stays on hover and 300 ms after, Esc hides, never covers the marker; bars are one keyboard slider "Replays by result"; the marker is a button that lights the tail bars and shows "2,500 of 10,000 replays did this well or better" (from the stored exact count), pinned by click/Enter with "Highlight on"/"Highlight off". Build-up once per view under a second; nothing moves with reduced motion.
- **Honesty notes card** "What this test can't see": always shown, never collapsed, three columns stacking below 900 px, then the "Left out of the test" line, then "Computed on … · Seed 44". Exit PnL warning box beside the stats with a hidden "Warning:".
- **Interaction states:** only clickable things react; hover and focus look the same plus a 2 px accent focus ring; 120 ms transitions; buttons lift 1 px; breakpoints 900, 640, 400 px only.

## Cross-Story Dependencies

- 3.1 draws the chart from the bins and exact count stored since Story 1.4; 3.2's `chart.js` enhances 3.1's SVG and must not be needed for the card to be complete.
- 3.3 needs the stored lookup to expose the Position builder's figures (failed fees, left-out share, uncoupled share, window size) from Epic 2.
- 3.4 builds on the theme and toggle already done in Story 1.7.
- 3.5 closes stage 1: it depends on 3.1 to 3.4. It is built in two parts: A, browser tests for `chart.js`, `progress.js` and the copy button on a swapped-in Verdict, plus a forced-colours run; B, the accessibility checks, where browser tests walk the 12-item checklist with the keyboard and read what a screen reader is given (replacing Edvard's own NVDA walk-through, his call of 2026-11-24), recorded in `docs/accessibility-check.md`, and the stage 1 close.
