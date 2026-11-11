# Story 1.1: project skeleton

## 2026-11-11 kl. 17:13 — Edvard Tokle

### Oppgave
Edvard asked the AI to pull `main` (local was 23 commits behind) and build Story 1.1 with `bmad-build`, that story only, on its own branch, with commits along the way and no merge, since he opens the PR himself. He handed the uv version choice to the AI ("just tell me what you picked"), and asked it to check with him first if anything didn't make sense.

### Plan
- `bmad-build` on branch `story-1-1-project-skeleton` from a fresh `main`. Spec: [spec-1-1-project-skeleton-that-starts.md](../../_bmad-output/implementation-artifacts/spec-1-1-project-skeleton-that-starts.md); Epic 1 context: [epic-1-context.md](../../_bmad-output/implementation-artifacts/epic-1-context.md).
- Edvard's answers: put the missing BMAD setting in the committed team file, write the README in English, keep the spec whole, use subagents for the review, approve and continue.
- The AI wrote the code itself, since subagents were okayed for the review only. Three reviewer subagents checked the diff, and each finding was verified before it was fixed.
- Edvard sees the logs before they are committed, which takes priority over this skill's automatic commit.

### Resultat
- **Built:** the `src/liquidoracle/` layers, a frozen settings object (flag, then `.env`, then default; a pace above 5 is refused), a `liquidoracle` command (`run` serves http://127.0.0.1:8044; `load-sample` and `make-synthetic` say "not built yet"), `pyproject.toml` + `uv.lock` with the pinned stack, `.python-version` 3.14, `.env.example`, `instance/` git-ignored, an English README, and CI `.github/workflows/tests.yml` (3 OS × Python 3.12/3.14).
- **Tests:** 84 pass with the network blocked, on 3.14 and 3.12, and also with `--repetitions 1000`. The rule tests were checked by planting real violations. A fresh clone runs `uv sync --locked`, the tests and the page.
- **uv:** settled at 0.13.4 as the spine pins. The local install was upgraded from 0.12.15. Closes the issue.
- **Bugs in the AI's code:**
  - Windows double start on a busy port, found by the AI's own smoke test.
  - A dead error branch, because Werkzeug exits itself.
  - `.env` `${VAR}` reading the system environment.
  - A crash on a non-UTF-8 `.env`.
  - A gap in the import rule.
  - Tests that could not fail.

  All fixed. 26 review findings: 17 fixed, 2 false, 7 rejected with a reason (spec's Review Triage Log).
- **Commits:** 674e714, e6969b5, 968bb89, f3e7849, 9c0eb1f, abe1fdb, 5cec466, af7217d, 1da3adf, 9bf2834 (memlog). `sprint-status.yaml`: epic-1 `in-progress`, 1-1 `review`.
- **AI log:** `docs/ai-logs/2026-11-11-story-1-1.md` (shown to Edvard before commit).

### Åpne punkter
- First CI run on GitHub: check that all six jobs run and pass in the course organisation (Story 1.1's acceptance criterion; raise with Edvard if Actions blocks it).
- Story 1.1 moves to `done` in `sprint-status.yaml` when the PR is merged.
