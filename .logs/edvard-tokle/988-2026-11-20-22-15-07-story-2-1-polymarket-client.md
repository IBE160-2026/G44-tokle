# Story 2.1: Polymarket client, read-only and polite

## 2026-11-20 kl. 22:15 — Edvard Tokle

### Oppgave
Edvard said PR #23 (Story 1.7) was merged and asked to get going on Epic 2. Build Story 2.1: the app's only connection to Polymarket, read-only, rate-limited across threads, with one retry policy and typed records out.

### Plan
- Branch `story-2-1-polymarket-client` from `main` at 7b821ae; first commit sets 1.7 and Epic 1 to `done`. The optional Epic 1 retrospective was skipped (Edvard said go on Epic 2).
- `bmad-build`: Epic 2 context compiled (`_bmad-output/implementation-artifacts/epic-2-context.md`), spec [spec-2-1-polymarket-client-read-only-and-polite.md](../../_bmad-output/implementation-artifacts/spec-2-1-polymarket-client-read-only-and-polite.md).
- Edvard's calls: Retry-After over 60 s gives up at once (1A); 500/502/504 and no connection retried like 503 (2A); spec kept whole (~2,200 tokens). AD-3, epics.md and the memlog updated before code.
- Code by the main session; three review subagents only.

### Resultat
- `src/liquidoracle/data/polymarket.py` (new): URL guard (only HTTPS Data API v2 and Gamma), `RateLimiter` with a lock, retry policy, cursor walker with one restart at half the limit and partial reads (`records.Read`), parsers to `ListedPosition`, `ActivityRow`, `Market`. `data/errors.py`: `PolymarketUnavailable`, `PolymarketBadRequest`, `ProtocolContractAddress`.
- Live finding: Gamma `/markets?condition_ids=` without `closed` returns only open Markets; the client asks `closed=true`, then `closed=false` for ids still missing.
- Tests: `tests/test_polymarket.py`, `tests/fake_polymarket.py`, rule test (only `data/polymarket.py` imports requests), live smoke test `tests/online/test_polymarket_live.py` (passed by hand). 650 tests pass (507 before), also on Python 3.12.
- Review: 44 findings → 14 groups fixed, 1 deferred, rest rejected (triage table in the spec).
- Commits: 27f0419, 0baa32d, 9a6754a, 82bf229, 950700e, AI log 43e3ac4 (`docs/ai-logs/2026-11-20-story-2-1.md`). Branch pushed with Edvard's ok.
- Closed in issues.md: 1.7 set to `done` (27f0419). The "live mode must not show the Sample list" item moved to Story 2.5, where the client is wired in.

### Åpne punkter
- Set Story 2.1 to `done` in `sprint-status.yaml` when its PR is merged.
- Story 2.5: once live runs get the client, the lookup service must not show the Sample list or the "not loaded" box in live mode (moved from 2.1).
- Story 2.5: find out what Data API v2 answers for an address with no history (empty list, 404 or 400) (`deferred-work.md`).
- Story 2.2: add `ListedPosition.last_event_at` together with the Sample JSON change it needs.
