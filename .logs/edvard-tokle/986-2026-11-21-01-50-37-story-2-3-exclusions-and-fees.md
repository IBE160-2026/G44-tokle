# Story 2.3: every exclusion and fee on real data

## 2026-11-21 kl. 01:50 — Edvard Tokle

### Oppgave
Edvard asked for the state from the handoff note (PR #25 for 2.2 merged, CI passed) and to build Story 2.3: leave out and count every bet the Skill Test cannot judge fairly, and check fees against the Market's schedule, tested on real data.

### Plan
- `bmad-build` on branch `story-2-3-every-exclusion-and-fee-on-real-data`, from `main` at 0bf136a. Spec: [spec-2-3-every-exclusion-and-fee-on-real-data.md](../../_bmad-output/implementation-artifacts/spec-2-3-every-exclusion-and-fee-on-real-data.md).
- Measure the raw capture first; four questions to Edvard (all AI recs): sold-before-bought left out as "not explained", strict fee check, one-off Gamma fetch, spec kept whole with review-only subagents.
- Plan documents (AD-11, AD-12, epics.md, memlog) before code; three reviewers after.

### Resultat
- Commits: 92bdd0a (2.2 done), 3d58134 (plan), 7fd1d3f (builder), a560094 (tests + three fixtures), 154e4c8 (spec built, story `review`), b0650f7 (AI log `docs/ai-logs/2026-11-21-story-2-3.md`).
- `core/positions.build_positions` takes the listed Positions: every one is counted (21 of 0x091596 used to vanish), new reasons "only in activity rows" and "share gap", sold-before-bought is "not explained", one reason each in a fixed order. Buy-fill fees are checked against Gamma's schedule ($0.0001 tolerance); failures count 0 and are recorded. `PositionSet.left_out_share`, `failed_fee_count/total`, `mostly_left_out`. The Skill Test refuses a negative fee.
- A second fee finding went to Edvard mid-build: 7 of 0x0f4b0a's fees ($0.28) also fail (rates lowered later); he kept the check strict.
- Fixtures cut from the capture: split-merge (0x729806), open-losers (0x94884d), fees (0x0f4b0a); Gamma fetched once, 4 requests. 725 tests pass (695 before); `load-sample` 1,005 Wallets.
- Review: 25 findings, 6 fix groups, 2 deferred, rest rejected (spec's triage table).
- Closed in issues.md: 2.2 set to done, the negative Own Fee, and the 1.2 question on tokens that sell before they buy.

### Åpne punkter
- Set Story 2.3 to `done` in `sprint-status.yaml` when its PR is merged.
- Story 2.4: decide whether neg-risk conversion outputs (listed, no trades) stay "share gap" or become "split or merged" (deferred-work).
- Epic 3: the card shows both list reasons as "Polymarket's two lists disagree" and needs the Position set from the stored lookup (left-out share, flag, failed fees) (deferred-work).
- Story 2.7: the 0x091596 hand calculation must follow the strict fee rule (its $44.31 fee counts as 0).
