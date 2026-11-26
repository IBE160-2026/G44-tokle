# Deferred work

Findings and goals set aside by `bmad-build`, each with where it came from.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-positions-from-fills.md`
  summary: A SELL before any BUY of the same token is only caught when the net total goes negative; a running balance would catch shares that came from outside the activity rows.
  evidence: Review finding 11 (maybe-false, unverified medium). Settle it by counting, on the captured Sample Wallets in Story 2.3, how many tokens have a running balance below zero while the net stays positive. If any, a rule change to AD-11 goes to Edvard.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-positions-from-fills.md`
  summary: Exit PnL ignores sell fees, and split-or-merged Positions carry an Exit PnL against a buy-only Entry Price.
  evidence: Review findings 12 and 13. The PRD Glossary defines Exit PnL as shares sold x (sell price - p) and Own Fees on buys only, so the builder follows the plan. Decide when the Exit PnL card (FR-11, Story 1.7) sums it: whether split-or-merged Positions are in the total, and whether sell fees count.
  resolved: Story 3.3 (Edvard, 2026-11-24): the Exit PnL total sums tested Positions, Slivers and Positions sold before resolution, with the Glossary formula (no sell fees); split-or-merged and other left-out Positions are out. PRD FR-11 and decision-log.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-positions-from-fills.md`
  summary: No test can show that `core/positions` sorts fills before summing.
  evidence: Review finding 21. Python's `sum()` is compensated since 3.12, so no realistic input differs. Revisit only if the sums move to numpy or another summation.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-4-the-skill-test.md`
  summary: The Skill Test accepts a negative Own Fee, which adds money to Real PnL.
  evidence: Review finding 7 (low). Own Fees are cash paid minus shares x price on buys (AD-12), so a rounding gap in real data can make one slightly negative; refusing it would crash a real lookup. The fee-schedule check that Epic 2 adds (Story 2.2, FR-4: a fee that fails the check counts as 0) is the place to catch it.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-1-polymarket-client-read-only-and-polite.md`
  summary: Find out what Data API v2 answers for a valid address with no Polymarket history (empty list, 404 or 400), so Story 2.5 can show "No Polymarket history found" instead of treating it as a bad request.
  evidence: maybe-false, would be medium. The Story 2.1 client raises PolymarketBadRequest on a 404 from the Data API; if v2 answers 404 for an unknown user, Story 2.5 cannot tell it from a real bug. One live request with an unused address settles it (add it to tests/online/).
  resolved: Story 2.5 (2026-11-21): one live probe with a random unused address got 200 and empty data on both positions lists and on activity, so "no history" = both lists empty (`NoPolymarketHistory`); an online test in `tests/online/` checks it.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-2-a-wallet-s-bets-as-one-complete-snapshot.md`
  summary: The negative Own Fee entry above (from spec-1-4) now belongs to Story 2.3, not Story 2.2: the fee-schedule check is built in 2.3 (Edvard, 2026-11-20; epics.md 2.3 states it).
  evidence: Story 2.2 review, blind hunter: the older entry still named Story 2.2. Entries here are never edited, so this one points onward.
- source_spec: `_bmad-output/implementation-artifacts/spec-2-2-a-wallet-s-bets-as-one-complete-snapshot.md`
  summary: A real Sample Wallet whose capture stopped at the 150,000-row cap could read as complete offline but capped live, because OfflineClient only knows the rows in its file.
  evidence: maybe-false, would be medium for Story 2.6 (0xd218e4 and 0x63d43b hit the cap in the capture). Settle it when 2.6 writes the real Wallets: store where each capture stopped and make OfflineClient's activity read incomplete past it.
  resolved: Story 2.6 (2026-11-23): each real Wallet's file stores `activity_from` / `activity_until`; OfflineClient answers a read starting before the first or reaching the second as cut short, so 0xd218e4, 0x63d43b and 0x729806 come out "not fully read" offline, as a live lookup of 0x63d43b does.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-3-every-exclusion-and-fee-on-real-data.md`
  summary: Neg-risk conversion outputs (listed Positions with no TRADE row whose shares came from a CONVERSION in another Market of the same event) are left out as "share gap"; Story 2.4, which reads the events, should decide whether they belong under "split or merged" instead.
  evidence: Story 2.3 review (blind hunter). 0x091596 has 21 of them, which alone puts it over the 10% note. They are left out either way; only the label and the reason counts on the card would change.
  resolved: Story 2.4 (Edvard, 2026-11-21): a CONVERSION names its neg-risk event, so every Position of that event is now "split or merged", outputs and the converted input alike.
- source_spec: `_bmad-output/implementation-artifacts/spec-2-3-every-exclusion-and-fee-on-real-data.md`
  summary: The card's "Left out of the test" line (EXPERIENCE.md) has six labels for seven reasons; Epic 3 must show both "only in activity rows" and "share gap" as "Polymarket's two lists disagree", and read the Position set (left-out share, flag, failed fees) from the stored lookup, which today returns only the Skill Test result.
  evidence: Story 2.3 review (blind hunter). Pre-existing in the UX plan: AD-11 always had both list reasons. `services/fetch.stored_result` drops the Position set; no page reads these numbers until Epic 3.
- source_spec: `_bmad-output/implementation-artifacts/spec-2-4-linked-bets-on-real-data.md`
  summary: A CONVERSION is matched through `Market.neg_risk_id`, which is set only for Yes/No negRisk Markets with two tokens; a negRisk Market of another shape would have its event's CONVERSION dropped and its converted Positions tested.
  evidence: maybe-false, would be medium (Story 2.4 review, all three reviewers). 108 of 108 negRisk Markets in the raw Gamma data are Yes/No, and Polymarket's negative-risk events are built from Yes/No Markets; such a Market is now logged ("left uncoupled"). Settle it in Story 2.6 by checking the outcomes of every negRisk Market in the 10 real Sample Wallets' Gamma records; if any is not Yes/No, keep the raw negRiskMarketID for CONVERSION matching apart from the coupling.
  resolved: Story 2.6 (2026-11-23): all 7,376 negRisk Markets in the 10 real Wallets' files are Yes/No (`neg_risk_check` in `sample_data/real/dataset.json`); nothing to change.
- source_spec: `_bmad-output/implementation-artifacts/spec-2-5-look-up-a-live-wallet.md`
  summary: `progress.js` (polling, swapping in the result, focus on the new heading, giving up after 30 failed polls) runs in no automated test; only the Python side of the progress contract is tested.
  evidence: Story 2.5 review (verification gap, blind hunter). The repo has no JavaScript test runner. Edvard checks one live lookup in a browser; a browser test belongs with Story 3.4's layout and accessibility pass if a runner is added then.
  update: Story 3.2 (2026-11-23, Edvard's call 3a) adds `chart.js` (tooltip, slider keys, marker pin/unpin, Esc, build-up, enhancing after the `progress.js` swap) to this item. Python tests cover everything the page hands the script; the behaviour was checked once with a throwaway Playwright script driving the installed Edge (45 checks, not in the repo). If 3.4 adds a runner, port those checks.
  update: Story 3.4 (Edvard, 2026-11-24) adds the runner: browser tests in `tests/browser/` (Playwright for Python driving the installed Chrome or Edge; on CI they fail rather than skip when no browser starts). They cover `copy-address.js`, the breakpoints and hover/reduced motion. Porting the 45 `chart.js` checks and testing `progress.js` is now part of Story 3.5 (epics).
  resolved: Story 3.5 part A (2026-11-24): `tests/browser/test_chart_script.py` (slider keys, tooltip timing and placement at 1280, 600 and 360 px, marker light/pin/unpin, build-up once and never with reduced motion, the page without the script) and `tests/browser/test_progress_script.py` (a live lookup swapped in with focus, title and chart; the result is served at the fetching page's own URL, so only that same-URL case is checked: replaceState is called with the reply's URL and a reload shows the Verdict; a 404 from the progress URL; Polymarket down and no history; giving up after 30 failed polls in a row), against a live app with the real job queue and worker and a stand-in Polymarket. Each test group failed on a planted break; they found no bug in the scripts.
- source_spec: `_bmad-output/implementation-artifacts/spec-2-6-real-wallets-in-the-sample-dataset.md`
  summary: 0x091596's Real PnL from the committed real file is -49,571.22, while Story 2.4 noted -49,571.39 on its fixture (cut from the same capture, Gamma fetched 2026-11-20); find the 17-cent cause when Story 2.7 checks this Wallet against the independent script.
  evidence: Story 2.6 build (2026-11-23). Own Fees 1,087.34 here. Likely a fee-schedule or Gamma difference between the two fetches, or a Position on the edge of the window; not checked yet. Story 2.7 compares to the cent, so it must be explained there.
- source_spec: `_bmad-output/implementation-artifacts/spec-2-6-real-wallets-in-the-sample-dataset.md`
  summary: The 17-cent gap above is explained: between the Gamma fetches of 20 and 23 November 2026, Polymarket changed the fee rate of 5 of 0x091596's Markets (for example 4% to 1%, 4% to 5%), and the strict fee check compares each fee with today's rate, so a different set of fees passes. Story 2.7 must compute its reference values from the committed real file's frozen Gamma records, not from a new fetch or the 2.4 fixture.
  evidence: Story 2.6 review (blind hunter asked to check the obvious cause): the fixture's and the additions file's feeSchedule differ for 0x1480b819d0, 0x2053d8515f, 0x5ec80dc407, 0xce9a5fa30f and 0xf7b7e74caa; positions are identical (66 tokens).
- source_spec: `_bmad-output/implementation-artifacts/spec-2-6-real-wallets-in-the-sample-dataset.md`
  summary: Story 4.6 builds before and after windows around 1 July 2025 from the same capture; for 0xd218e4 and 0x63d43b the capture holds trades only from May 2025, so their before part may also come out entirely "not fully read", which the Hold-up Test (Epic 5) would feel.
  evidence: maybe-false, would be medium (Story 2.6 review, blind hunter). Settle it in Story 4.6 by running its before window on the capture and counting not-fully-read Positions per Wallet before planning the Hold-up Test's real-data checks.
- source_spec: `_bmad-output/implementation-artifacts/spec-2-7-real-pnl-checked-independently.md`
  summary: Every fee that fails the strict check fits Polymarket's fee formula at 1.67x to 7x the Market's listed rate, so the check (against today's rate) drops fees that were real when paid; Own Fees are then too low for 0x0f4b0a (7 fees, 0.28) and 0x091596 (2 fees, 44.48).
  evidence: Story 2.7 review; helper 2's `tests/reference/*-fee-check.csv` and `script-notes.md`; ties to the Story 2.6 rate-change entry. Needs Edvard's call on whether FR-4's check should allow a rate that was listed when the fee was paid.
  resolved: Story 2.8 (Edvard, 2026-11-23): FR-4 and AD-12 now pass a fee at the listed rate or any whole-percent rate from 1% to 10%; all 9 fees pass, plus 0xd3a6e5's 26 ($461.79), and the references moved to -188.77 and -49,615.70.
- source_spec: `_bmad-output/implementation-artifacts/spec-2-7-real-pnl-checked-independently.md`
  summary: Own Fees count the fee on every buy of a Position, also on shares later sold; for 0x091596 that is 636.90 of 1,087.34 (about 510 on five Slivers), while FR-3 puts sold shares in Exit PnL.
  evidence: Story 2.7 review; helper 2's judgment call J6. App and reference agree (Glossary: fees "paid on the buys of a Position"), so nothing fails; whether the Glossary means this is Edvard's call.
- source_spec: `_bmad-output/implementation-artifacts/spec-2-7-real-pnl-checked-independently.md`
  summary: FR-3 says a Position is left out when the Wallet "converted shares in that Market", but a CONVERSION row names the negative-risk event, and the app (Edvard, Story 2.4) leaves out the whole event; the PRD wording could say so.
  evidence: Story 2.7 review; helper 2's judgment call J9 reached the same reading from the data alone.
- source_spec: `_bmad-output/implementation-artifacts/spec-2-8-the-fee-check-accepts-an-earlier-rate.md`
  summary: The Follower Fee (Glossary, FR-18a) uses the Market's listed rate, which Gamma gives only for today; a follower's fee in the past may have been charged at an earlier rate, as Story 2.8 found for Own Fees.
  evidence: Story 2.8 planning. Settle it in Epic 6: either accept the listed rate as the simulated follower's cost and say so, or use the rate the copied Wallet's own fill in that Market fitted.
- source_spec: `_bmad-output/implementation-artifacts/spec-2-8-the-fee-check-accepts-an-earlier-rate.md`
  summary: The independent reference script also tries whole-percent rates in a Market without fees or without a schedule, where the app ignores the fee (no fees) or fails it (no schedule).
  evidence: Story 2.8, the helper's unclear point 1. No such fee exists in the two reference Wallets (largest 0.0000045), so the totals agree; it would matter only for a new reference Wallet.
- source_spec: `_bmad-output/implementation-artifacts/spec-3-1-the-luck-chart.md`
  summary: The Verdict header (Verdict and address card) does not stack below 900 px, so at phone widths the whole Verdict page scrolls sideways.
  evidence: Seen in Story 3.1's 360 and 600 px screenshots; the grid `.verdict-head` has a 300 px minimum column from Story 1.7. Story 3.4 already plans "two-column parts stack below 900 px" (UX-DR10).
  resolved: Story 3.4 (2026-11-24): `.verdict-head` stacks below 900 px; browser tests check that no page scrolls sideways at 320, 360, 600 and 900 px (they fail on the old stylesheet for every Verdict page at 320, 360 and 600 px).
- source_spec: `_bmad-output/implementation-artifacts/spec-3-1-the-luck-chart.md`
  summary: For Story 3.5 (Edvard, 2026-11-23): a screen reader never hears "below all 10,000 Simulations", because the marker label is inside the chart's aria-hidden block and the text alternative (PRD §8 sentence) then says only "more than half the time"; decide whether the text alternative gets a beyond clause.
  evidence: Story 3.1 review finding 7. "Above all" is carried by the odds phrase ("fewer than 1 time in 10,000"), "below all" is not. Rare: it needs a Wallet worse than every replay. Changing the sentence changes the planned wording (FR-9, UX-DR24), so it is Edvard's call.
  resolved: Story 3.5 part B (Edvard, 2026-11-25, option a): the text alternative adds "That is below all 10,000 replays." when the Real PnL is below every Simulation (EXPERIENCE.md, epics.md UX-DR24 and Story 3.1 changed first); `phrases.chart_text(below_all=…)`, tested in test_phrases.py, test_chart.py and test_web.py.
- source_spec: `_bmad-output/implementation-artifacts/spec-3-2-exploring-the-chart.md`
  summary: The tail label gives the raw count ("1 of 10,000 replays did this well or better") while the odds line gives the p-value ("about 1 time in 5,000", PRD: (1 + count) / (1 + 10,000)), so with a small count the two look like they disagree; decide in Story 3.3 whether the honesty notes (or About) explain the +1.
  evidence: Edvard noticed it on sharp-trader in the browser (2026-11-23) and chose to note it for Story 3.3 (option c) over leaving it or adding an About line now. Both numbers are correct and planned (PRD p-value definition, UX-DR27 exact count).
  resolved: Story 3.3 (Edvard, 2026-11-24): About's JavaScript-only paragraph ends with a sentence on the +1 (EXPERIENCE.md, About this chart).
- source_spec: `_bmad-output/implementation-artifacts/spec-3-3-the-honesty-notes.md`
  summary: The honesty notes' window and computed-on lines exist only for the `lookup` scope; the after part's "first 2,000" line and the Watchlist's two-window line (FR-11, epics Story 3.3 AC) are not built, and `phrases.computed_on` refuses any other scope.
  evidence: Story 3.3 review (blind hunter). No after part or Watchlist result exists before Epic 4 (scan scopes) and Epic 5 (Hold-up), so there is nothing to show yet; build the wording with the first story that stores a `scan_whole`, `scan_before` or `holdup_after` result.
- source_spec: `_bmad-output/implementation-artifacts/spec-3-4-theme-copy-and-finish.md`
  summary: No browser test clicks the copy button on a Verdict that `progress.js` swapped in after a live lookup, the case the page-wide click listener in `copy-address.js` was built for.
  evidence: Story 3.4 review (verification gap, blind hunter). The browser tests open only Offline Mode pages; a live job needs a fake Polymarket in the browser fixture, which Story 3.5's `progress.js` tests build anyway. Added to the Story 3.5 note in epics.md.
  resolved: Story 3.5 part A (2026-11-24): `test_ux_dr22_live_lookup_swaps_in_the_verdict` clicks the copy button on the swapped-in Verdict and reads the clipboard.
- source_spec: `_bmad-output/implementation-artifacts/spec-3-4-theme-copy-and-finish.md`
  summary: The new forced-colours rules (Highlight border for the copied state and for hover and focus on the copy, theme and primary buttons) run in no test; Playwright's `forced_colors="active"` can check them.
  evidence: Story 3.4 review (verification gap). Story 3.5's first acceptance criterion covers forced-colours rules; added to its note in epics.md.
  resolved: Story 3.5 part A (2026-11-24): three forced-colours tests in `tests/browser/test_pages.py` (the copied border, hover and focus on the three buttons, tail and active bars in Highlight). Chrome and Edge draw a Highlight border on a hovered or focused button by themselves, so the hover/focus test also checks that the app's own rule applies.
- source_spec: none
  summary: Story 3.5 part B: the accessibility checks (automated page checks, the 12-item checklist walked by browser tests that read what a screen reader is given, `docs/accessibility-check.md`, the "below all" decision) and the stage 1 close (CI on three systems, README, SM-1 and SM-2 noted).
  evidence: Split from Story 3.5 at its build (Edvard, 2026-11-24): part A (browser tests for the scripts) is built first so that bugs it finds are fixed before part B's checks; both parts are in epics.md Story 3.5.
  resolved: Story 3.5 part B (2026-11-25): `tests/test_web.py` (headings and labels on 14 pages), `tests/browser/test_checklist.py` (the 12 items by keyboard, Real Wallets links, every page without JavaScript), `docs/accessibility-check.md` (one finding stays: the Lookup page's autofocus means its first Tab is not the skip link), the "below all" sentence, `docs/stage-1-check.md` and the README. The CI run on three systems is checked on the pushed branch.
- source_spec: `_bmad-output/implementation-artifacts/spec-3-5-a-browser-tests-for-the-scripts.md`
  summary: No browser test makes `progress.js` meet a result fetch that ends at another URL (a re-queued job redirecting to `?job=<new id>`), follow the new fetching block with `start()`, or fall back to `location.assign` when the page has no `#content` or the fetch fails.
  evidence: Story 3.5 part A review (verification gap, blind hunter). The live-lookup test's result URL equals the fetching URL, so `replaceState` with the wrong URL would pass; reaching the re-queue path needs a job that ends without a snapshot (a stand-in that interrupts the job).
- source_spec: `_bmad-output/implementation-artifacts/spec-3-5-a-browser-tests-for-the-scripts.md`
  summary: `make_page(clock=True)` calls `page.clock.pause_at(START + 5 s)` after `goto`; if a page takes more than 5 real seconds to load (a slow CI runner), `pause_at` targets a past time and the test errors.
  evidence: Story 3.5 part A review (edge case hunter); the code moved unchanged from Story 3.4. No run has hit it (pages load in well under a second); settle it if a clock test ever fails on CI with a pause_at error, by pausing before `goto`.
- source_spec: `_bmad-output/implementation-artifacts/spec-4-2-the-scan-funnel.md`
  summary: An OPEN holder row whose token is not one of its Market's Gamma outcomes ends the Scan funnel with ValueError instead of marking the Market "not used: partial".
  evidence: maybe-false (would be medium); settle it by checking the token ids of a few real Market-anchored reads against Gamma's clobTokenIds (the spike kept no token ids). Story 4.3 can turn the error into a partial Market if it is real.
  resolved: Story 4.3 (2026-11-26): `read_candidates` makes such a Market "not used: partial" instead of ending the Scan; tested by `test_ad9_an_open_row_on_an_unknown_token_makes_the_market_partial`.
