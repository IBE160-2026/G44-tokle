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
