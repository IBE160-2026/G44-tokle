# Deferred work

Findings and goals set aside by `bmad-build`, each with where it came from.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-positions-from-fills.md`
  summary: A SELL before any BUY of the same token is only caught when the net total goes negative; a running balance would catch shares that came from outside the activity rows.
  evidence: Review finding 11 (maybe-false, unverified medium). Settle it by counting, on the captured Sample Wallets in Story 2.3, how many tokens have a running balance below zero while the net stays positive. If any, a rule change to AD-11 goes to Edvard.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-positions-from-fills.md`
  summary: Exit PnL ignores sell fees, and split-or-merged Positions carry an Exit PnL against a buy-only Entry Price.
  evidence: Review findings 12 and 13. The PRD Glossary defines Exit PnL as shares sold x (sell price - p) and Own Fees on buys only, so the builder follows the plan. Decide when the Exit PnL card (FR-11, Story 1.7) sums it: whether split-or-merged Positions are in the total, and whether sell fees count.
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
- source_spec: `_bmad-output/implementation-artifacts/spec-2-6-real-wallets-in-the-sample-dataset.md`
  summary: 0x091596's Real PnL from the committed real file is -49,571.22, while Story 2.4 noted -49,571.39 on its fixture (cut from the same capture, Gamma fetched 2026-11-20); find the 17-cent cause when Story 2.7 checks this Wallet against the independent script.
  evidence: Story 2.6 build (2026-11-23). Own Fees 1,087.34 here. Likely a fee-schedule or Gamma difference between the two fetches, or a Position on the edge of the window; not checked yet. Story 2.7 compares to the cent, so it must be explained there.
