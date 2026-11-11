# Story 1.2: positions from fills

## 2026-11-11 kl. 19:43 — Edvard Tokle

### Oppgave
After PR #16 (Story 1.1) was merged, Edvard asked the AI to pull `main`, start a new branch whose first commit sets 1.1 to `done`, and build Story 1.2 with `bmad-build`: that story only, commits along the way, no merge (he opens the PR). Ask him first if something doesn't make sense, show him the logs before committing them, and tell him how to see it working.

### Plan
- Branch `story-1-2-positions-from-fills` from `main` at 44af47f. Spec: [spec-1-2-positions-from-fills.md](../../_bmad-output/implementation-artifacts/spec-1-2-positions-from-fills.md).
- Before writing the spec, the AI checked the plan against the captured Sample Wallets and found two gaps, which Edvard decided (Entry Price from the buy fills; Slivers). The plan was changed first (PRD, spine AD-10/AD-11, epics, both memlogs), then the spec.
- As in Story 1.1, the AI wrote the code itself and used three reviewer subagents for the review only (Edvard's choice).

### Resultat
- **Plan change (056c33b):** Entry Price is the share-weighted average of the BUY fills, not Polymarket's `avg_price`, which moves on sells (0x736483: 986 of 1,388 sold Positions differ). New Glossary term Sliver: under 1% of bought **and** under 1 share left; its money stays in Real PnL and every Simulation, but it is not counted as a bet. The AI proposed under 1%; Edvard added the 1-share limit and kept the money in, then chose "at most $1 if it won" and "also in the replays" on follow-up questions.
- **Built:** record types in `src/liquidoracle/records.py` (43e88e2); `core/positions.py` with `is_resolved` and `build_positions` (f93fd97): one reason per left-out Position (unclear resolution, split or merged, sold before resolution, not explained), Slivers apart, Own Fees in fee Markets, Exit PnL.
- **Tests:** 39 in `tests/test_positions.py`; full suite 123 passed, 1 deselected. Planted bugs each fail a test, except removing the input sort, which no input can show since Python 3.12's `sum()`.
- **Real-data smoke run** (one-off script outside the repo): 0x29306d has 23 Positions in resolved Markets = 18 tested + 3 Slivers + 2 sold.
- **Review (108a5d6, 40d6eff):** 21 findings: 9 patched, 8 rejected with evidence, 4 deferred to `deferred-work.md`. Bug in the AI's code: exactly 1% left became a Sliver for some sizes (0.01 × 70 = 0.7000000000000001). One of the AI's own fixes missed (a test for misaligned Market lists that the old code already passed); caught by rechecking with the planted bug.
- **Commits:** fd0e826 (1.1 done), 056c33b, cf7a427, 43e88e2, f93fd97, 108a5d6, 40d6eff, 3fc022f. `sprint-status.yaml`: 1-1 `done`, 1-2 `review`.
- Closes the issues item "set Story 1.1 to `done`".

### Åpne punkter
- Story 2.7: Edvard's hand calculation of 0x29306d must follow the Sliver rule (3 Slivers: money in Real PnL, not counted as bets); the "23 bets" in the story is the window, of which 18 are tested.
- Story 2.3: count on the Sample Wallets whether any token sells before it buys (running balance below zero) while the net looks fine; if so, a rule change to AD-11 goes to Edvard (deferred-work.md).
- Story 1.7 (Exit PnL on the card): decide whether split-or-merged Positions are in the Exit PnL total and whether sell fees count (deferred-work.md).
