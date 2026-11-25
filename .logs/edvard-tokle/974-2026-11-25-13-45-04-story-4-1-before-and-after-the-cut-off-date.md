# Story 4.1: before and after the Cut-off Date

## 2026-11-25 kl. 13:45 — Edvard Tokle

### Oppgave
Stage 1 is closed (PR #38 merged). Switch to main, pull, and start Epic 4 with Story 4.1: split a Wallet's bets at a Cut-off Date into a before part (judges skill) and an after part (checks it), with no bet on the wrong side.

### Plan
- Pulled main (6fded84), made branch `story-4-1-before-and-after-the-cut-off-date`. A helper compiled `epic-4-context.md`.
- Edvard's calls:
  - Helpers for the summary, the build AND the review. **He changed the AI's recommendation**, which was summary and review only.
  - A mixed Market (one side bought before the date, the other after) is in neither part (AI rec).
  - The spec is kept whole (AI rec).
  - After review pass 1, two choices (both AI rec): rank the after part by `first_entry_at`, not the first buy; and a bet fully closed before the date does not make its Market mixed.
  - Before approving the revised spec, **HE ASKED** whether a bet bought after the date could reach the before part. It could. He chose "neither part" for such Markets (AI rec), and asked for the share-count leftover to be noted, not changed.
  - "ok commit and push".
- `bmad-build` with spec [spec-4-1-before-and-after-the-cut-off-date.md](../../_bmad-output/implementation-artifacts/spec-4-1-before-and-after-the-cut-off-date.md). Two build passes by fresh helpers, two review passes of three reviewers each.

### Resultat
- **Plan, committed before any code:**
  - 0452c06: AD-7 after-part rules, the mixed-Market decision, the Epic 4 context, and the sprint status set to in-progress.
  - 37897cc: AD-7 and AD-10 after the review decisions (first entry, closed-early rule, the "neither part" rule for Markets resolved before the date but bought after it, the share-count note), plus epics.md 4.1 and the memlog.
- **Code and tests (cc1521d):**
  - `data/window.py`: `cutoff_at`, `positions_near(cutoff: date, side)`, the before part through `_resolved_part`, the after part through `_after_part`/`_eligible_after`, and the shared helpers `_with_activity`, `_rows_of` and `_cap(key=)`.
  - `records.Window` gains the `cutoff` and `side` fields.
  - New fixture `tests/fixtures/capture/after-part.json`, cut from 0x729806 with Gamma from the frozen additions file and no network. It holds the 20 tokens that only look new, 3 Markets entered by conversion, and 1 Market closed before the date but bought after it.
  - Many new tests in `tests/test_window.py`. The clients are unchanged: the pass-1 `until` stop rule was dropped.
- **Spec, review log and sprint status (116aa1e):** Story 4-1 set to `review`. AI log `docs/ai-logs/2026-11-25-story-4-1.md` (76fb742).
- **Review:**
  - Pass 1: 18 findings. The rule had a hole (352 Markets of 0x729806 vanished), and there was a real bug (Markets in both parts). That loop went back to Edvard, and the code was reverted and rebuilt.
  - Pass 2: 22 findings, 8 fixed (two test gaps proven by mutation, 6 small fixes), 14 rejected. 0 deferred.
- **Tests:** 1,252 pass, 2 deselected (online), none skipped. The count was 1,207 before.

### Åpne punkter
- Set Story 4.1 to `done` in `sprint-status.yaml` when the PR is merged (first commit of the Story 4.2 branch).
- Story 4.3: a Scan fetches both parts of each Wallet. The after part's CLOSED walk reads the same pages as the before walk, so share them to save requests on big Wallets.
- Epic 4 is past its 24–26 Nov target, and code freeze is 1 Dec. Six days remain for Stories 4.2–4.6 and 5.1–5.2 (the stage 2 minimum), so decide early what slips (the favicon ring and tab-title counter slip first, per epics.md).
