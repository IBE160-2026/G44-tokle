# Story 2.8: the fee check accepts an earlier rate

## 2026-11-23 kl. 11:13 — Edvard Tokle

### Oppgave
Pull main after PR #30 (2.7) and settle the fee-rate question before Epic 3: the strict check threw out fees that fit an older rate, because Gamma lists only today's rate. Edvard asked for the AI's call, then chose its recommended option 1: a fee passes at the listed rate or any whole-percent rate from 1% to 10%. This reverses his 21 Nov "stay strict" call.

### Plan
- Plan first, committed on its own: PRD FR-4 + Assumptions Index + decision log, AD-12, epics Story 2.8, both memlogs (b959f44).
- `bmad-build`: spec [spec-2-8-the-fee-check-accepts-an-earlier-rate.md](../../_bmad-output/implementation-artifacts/spec-2-8-the-fee-check-accepts-an-earlier-rate.md). A fresh helper changes the independent script's fee rule (never sees the app's code); its output is committed before the app change. Edvard's condition at approval: window tests use the fixtures' own numbers, not the full Wallets.

### Resultat
- `fee_passes` (`core/positions.py`) tries the listed rate and 1%–10% with the listed exponent and the $0.0001 tolerance.
- References: 0x0f4b0a −188.77, 0x091596 −49,615.70 (= the 2.7 script's "failed fees counted" totals); app matches to the cent, failed fees 0. 0x29306d unchanged.
- 0xd3a6e5 also moved: all 26 of its fees ($461.79, at 4–5% in Markets now at 1%) had failed; Real PnL $118,065 → $117,604. Other seven Wallets unchanged; no Verdict or p-value changed. `docs/real-wallets.md` and `RECORDED` updated.
- Fixture check (Edvard's condition) mattered: the 0x091596 fixture has 1 failing fee, not 2 (Gamma of 20 Nov).
- Review: 20 findings, 6 fixed (incl. the reference test now compares the failed-fee count), rest rejected with reasons. 897 tests pass (894 before).
- Commits: 48fe6c9 (2.7 done), b959f44 (plan), 28c4c49 (helper's references), 0c13893 (app + tests), a42d379 (spec, deferred), d3f32fb (AI log). Story 2.8 is `review`.
- Closed: the 2.7 fee-rate item and setting 2.7 to `done`.

### Åpne punkter
- Epic 6: the Follower Fee also uses today's listed rate (`deferred-work.md`).
- The reference script also tries whole-percent rates in Markets without fees or without a schedule, where the app ignores or fails the fee; matters only for a new reference Wallet (`deferred-work.md`).
- Set Story 2.8 to `done` in `sprint-status.yaml` when its PR is merged.
