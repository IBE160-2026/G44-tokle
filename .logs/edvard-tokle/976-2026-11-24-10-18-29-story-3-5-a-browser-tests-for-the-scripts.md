# Story 3.5 part A: browser tests for the scripts

## 2026-11-24 kl. 10:18 — Edvard Tokle

### Oppgave
Switch to main after PR #35 (3.4) was merged and start Story 3.5. The story was split in two; this session built part A: browser tests for `chart.js` and `progress.js`, the copy button on a swapped-in Verdict, and a forced-colours (High Contrast) run.

### Plan
- Checked GitHub's runs for the 3.4 branch (push and PR both passed, so the browser tests ran), pulled main, made the branch, set 3.4 `done` (e8d99ba).
- Edvard's calls: split 3.5 into part A and part B (AI rec); HE CHANGED part B: no NVDA walk-through by him, browser tests walk the checklist by keyboard and read what a screen reader is given (reverses his 24 Oct call); "approve and continue"; 3.5 stays `in-progress` until part B; "ok commit and push".
- `bmad-build` with spec [spec-3-5-a-browser-tests-for-the-scripts.md](../../_bmad-output/implementation-artifacts/spec-3-5-a-browser-tests-for-the-scripts.md); a fresh helper implemented it, three helpers reviewed.

### Resultat
- Plan (7c8a22b): epics Story 3.5 (two parts, browser tests replace the NVDA walk-through, the doc must say what they cannot prove), Epic 3 context, PRD memlog.
- Tests (83dca69): `tests/browser/pages.py` (shared helpers), live app + stand-in Polymarket in `conftest.py`, `test_chart_script.py`, `test_progress_script.py`, forced-colours tests in `test_pages.py`, README. No app code changed; the tests found no bug. Every new test failed on a planted break (31 breaks).
- Review: 23 findings, 9 groups fixed (overclaimed address-bar check reworded, missing pointer/timing/404/count-reset checks added, two possible flakes), 2 deferred, 6 rejected. Spec, review log, deferred, sprint status (837e299); AI log `docs/ai-logs/2026-11-24-story-3-5-a.md` (61a8dfd).
- 1,144 tests pass with `CI=true`, none skipped (1,109 before).
- Closed: the 3.4 CI checks (passed on PR #35), the 3.5 script-test item, setting 3.4 `done`.

### Åpne punkter
- Story 3.5 part B: the accessibility checks, the 12-item checklist walked by browser tests that read what a screen reader is given, `docs/accessibility-check.md` (with what the tests cannot prove), the "below all" decision, and the stage 1 close (CI on three systems, README, SM-1 and SM-2).
- Deferred: no browser test of a result fetch that ends at another URL (re-queued job), `start()` following a new fetching block, or the `location.assign` fallbacks in `progress.js` (`deferred-work.md`).
- Deferred: `make_page(clock=True)` pauses the clock after the page loads; a page taking over 5 s to load (slow CI) would error (`deferred-work.md`).
