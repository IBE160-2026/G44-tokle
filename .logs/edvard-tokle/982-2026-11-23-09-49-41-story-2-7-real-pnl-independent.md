# Story 2.7: Real PnL checked independently

## 2026-11-23 kl. 09:49 — Edvard Tokle

### Oppgave
Pull main after PR #29 (2.6) and start Story 2.7. Edvard did not want to do the 0x29306d spreadsheet by hand: a fresh AI helper does it from the PRD and the raw data only, never the app's code, its CSV saved before any test, and the story wording changed to match. The same rule later for the Copy Test (6.x).

### Plan
- Change the plan first (PRD FR-4, SM-1, FR-18a; epics 2.7, 6.x, FR lines; memlog), then helper 1 for 0x29306d, commit its CSV.
- `bmad-build` for the rest: spec [spec-2-7-real-pnl-checked-independently.md](../../_bmad-output/implementation-artifacts/spec-2-7-real-pnl-checked-independently.md). Helper 2 writes a stdlib-only script for 0x0f4b0a and 0x091596 from `prd.md` + `fields.md` (field meanings only, Edvard's condition); commit it before the comparison test; three-layer review.

### Resultat
- References: 0x29306d $295.06 (helper 1), 0x0f4b0a −$188.49 and 0x091596 −$49,571.22 (helper 2's script). All match the app to the cent, plus tested count, Sliver count and Own Fees. Planted bugs (Own Fees halved, reference +1 cent, edited fee-check row) all failed the test.
- `tests/reference/` (CSVs, notes, both scripts, `fields.md`), `tests/test_reference_pnl.py` (16 tests; scripts re-run with `python -I -S` so the app cannot load). 894 tests pass (878 before).
- Review: 29 findings, 8 groups fixed, 3 deferred, rest rejected (spec triage log).
- Commits: 0fa12df (2.6 done), 57eed2f, e85f083, 4810a37, e9d332d, 3cec1f3, 263d6e9, 35c4db1 (AI log). Pushed. Story 2.7 is `review`.
- Closed older issues: the 0x29306d Sliver rule, 0x091596's $44.31 fee as 0, its Romania event left out, frozen Gamma used, 2.6 set `done`, and the hand-calculation item (replaced by helpers).

### Åpne punkter
- Fee check against today's rate drops fees that fit an older rate (0x091596 44.48, 0x0f4b0a 0.28): Edvard decides in its own session, before Epic 3 (`deferred-work.md`).
- Decide whether Own Fees on shares later sold should count in full (636.90 of 0x091596's 1,087.34) (`deferred-work.md`).
- PRD FR-3 wording: "converted shares in that Market" should say the whole negative-risk event (Edvard's 2.4 call) (`deferred-work.md`).
- Story 6.x: the Copy Test three-Position reference is made by a fresh helper from the PRD and the set's data, committed before its test.
- Edvard opens the PR as Cludegruppa22; after merge, set Story 2.7 to `done` in `sprint-status.yaml`.
