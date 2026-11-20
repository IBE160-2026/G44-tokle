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

- source_spec: `_bmad-output/implementation-artifacts/spec-2-2-a-wallet-s-bets-as-one-complete-snapshot.md`
  summary: The negative Own Fee entry above (from spec-1-4) now belongs to Story 2.3, not Story 2.2: the fee-schedule check is built in 2.3 (Edvard, 2026-11-20; epics.md 2.3 states it).
  evidence: Story 2.2 review, blind hunter: the older entry still named Story 2.2. Entries here are never edited, so this one points onward.
- source_spec: `_bmad-output/implementation-artifacts/spec-2-2-a-wallet-s-bets-as-one-complete-snapshot.md`
  summary: A real Sample Wallet whose capture stopped at the 150,000-row cap could read as complete offline but capped live, because OfflineClient only knows the rows in its file.
  evidence: maybe-false, would be medium for Story 2.6 (0xd218e4 and 0x63d43b hit the cap in the capture). Settle it when 2.6 writes the real Wallets: store where each capture stopped and make OfflineClient's activity read incomplete past it.
