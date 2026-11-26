# Story 4.3: the Scan as a resumable job

## 2026-11-26 kl. 13:21 — Edvard Tokle

### Oppgave
PR #40 (Story 4.2) is merged. Switch to main, pull, mark 4.2 done, and build Story 4.3: a Scan that runs in the background, survives closing the app or an outage, and stores its results.

### Plan
- Pulled main (3b14790). CI on main: every test job green; the macOS 3.12 job was cancelled before any step (runner problem). Made branch `story-4-3-the-scan-as-a-resumable-job` and set 4.2 to `done` (6a23bd1).
- Edvard's calls, all AI recs:
  - Reuse a Wallet's stored part only for the same date and side, while under 24 hours old; never fetch a Market record twice. FR-16 reworded.
  - A unit of work is a whole Market, as 4.2 built it. AD-5 reworded.
  - The spec is kept whole (about 2,400 tokens).
  - Helpers for the review only.
  - "approve and continue". After the review: "ok commit and push", "yes fix the spec line", the validation reports left out.
- `bmad-build` with spec [spec-4-3-the-scan-as-a-resumable-job.md](../../_bmad-output/implementation-artifacts/spec-4-3-the-scan-as-a-resumable-job.md).

### Resultat
- **Plan, committed before any code (99a84aa):** PRD FR-16 and its decision log, spine AD-4/5/6/19, epics 4.3, the Epic 4 context and both memlogs.
- **Code and tests (2d558fc):**
  - Schema v6 with five scan tables. Snapshots are keyed by Cut-off Date and side. A schema change keeps Scans, their snapshots and the id counters.
  - `services/scan.run_scan` runs the two phases (ranking, then Skill Tests) and stores each unit as it finishes. Results `scan_before` and `scan_whole` carry the as-of filter.
  - `services/jobs`: `start_scan`, `resume_scan`, lookups between units, one Scan at a time.
  - The unknown-token check, which resolves 4.2's deferred item.
  - New `tests/test_scan_job.py` and new store and phrase tests.
- **Review fixes:**
  - The as-of time was saved but never used; it is now applied.
  - Id reuse after a rebuilt schema is prevented.
  - Progress now ends at the total.
  - Six tests were missing and are added.
  - The plan's "6 seconds" claim is corrected (78857f9), and so is the frozen spec line, with Edvard's approval.
- **Spec, review log (28 findings: 11 fixed, none deferred, the rest rejected) and sprint status 4-3 `review` (bf97050).** AI log `docs/ai-logs/2026-11-26-story-4-3.md` (dc2c2de).
- **Planted bugs:** 16 in all (8 during the build, 8 for the review tests), all caught by tests.
- **Tests:** 1,369 pass, 3 deselected (online). The count was 1,330 before.
- **Closed issues:** the token-mismatch item and the "units are whole Markets or Wallets" item.

### Åpne punkter
- After the PR is merged: set Story 4.3 to `done` in sprint-status.
- Story 4.4: the form must check the Cut-off Date (in the past) and the Number of Wallets (10 to 500) before `start_scan`, because the service only checks for a whole number of 1 or more.
- Story 4.6: `start_scan` has no Offline Mode guard; offline Scans arrive with the anchor Markets.
