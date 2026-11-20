# Story 2.2: A Wallet's bets as one complete snapshot

## 2026-11-21 kl. 00:09 — Edvard Tokle

### Oppgave
Edvard said PR #24 (Story 2.1) was merged and CI passed, and asked to do Story 2.2: a lookup reads the latest 2,000 bets in resolved Markets, with Gamma's facts and the activity they need, saved as one complete snapshot.

### Plan
- Branch `story-2-2-one-complete-snapshot` from `main` at 8732a88; first commit sets 2.1 to `done`.
- `bmad-build`: Epic 2 context patched for the AD-3 wording, spec [spec-2-2-a-wallet-s-bets-as-one-complete-snapshot.md](../../_bmad-output/implementation-artifacts/spec-2-2-a-wallet-s-bets-as-one-complete-snapshot.md).
- Edvard's calls (all AI recommendations): `ACTIVITY_ROW_CAP` 150,000 (same as the Sample capture); negative Own Fee moved to Story 2.3; fixtures get the real Gamma records, fetched once; spec kept whole (~2,200 tokens); subagents for review only. AD-7, AD-8, epics.md and the memlog changed before code.
- Code by the main session; three review subagents only.

### Resultat
- `data/window.py` (`positions_near`, `WINDOW_LIMIT`, `ACTIVITY_ROW_CAP`); client walk with stop rule and row cap, Gamma `include_tag`, Market start/fee schedule/tags, `ListedPosition.last_event_at`; `OfflineClient` serves the same raw reads; store schema version 2 (`activity_read_until`, `resolved_markets`, `wallet_lock`); builder leaves out "not fully read" Positions; Synthetic files regenerated.
- Tests: fixture script `tests/fixtures/cut_from_capture.py` + two fixtures (0x29306d, 0x091596) with real Gamma records (one fetch, ~10 requests); routed fake server; `test_window.py`. 695 tests pass (650 before); online test passed live and now checks CLOSED by TIMESTAMP DESC is newest first. load-sample: 1,005 Wallets.
- Review: 27 findings, 10 groups fixed, 2 deferred, rest rejected. Real bug: a Gamma timeout inside the CLOSED stop rule restarted the walk and silently dropped those Markets' Positions. AD-7 now also counts the cap's last second as unread.
- Commits (pushed): 72427a1, b26e853, 4cc85c7, 41a05c4, c74fa23, AI log 62b1d15.
- Closed from issues.md: README CI job first run (Edvard: CI passed), 2.1 done (72427a1), `last_event_at` added (4cc85c7), negative Own Fee (moved to 2.3, epics.md b26e853).

### Åpne punkter
- Set Story 2.2 to `done` in `sprint-status.yaml` when its PR is merged.
- Story 2.3: the fee-schedule check must also handle a negative Own Fee (moved from 2.2).
- Story 3.x: the Verdict card's "latest 2,000" line needs to know whether the cap applied; the snapshot does not store that yet (review BH7, rejected for now).
- Story 2.6: a real Wallet whose capture stopped at the 150,000 cap could read as complete offline (`deferred-work.md`).
- Story 7.1: one committed fixture Market (0x07faaf…) is among the 50 hand-label Markets; score tag rules only on Markets outside the 50.
