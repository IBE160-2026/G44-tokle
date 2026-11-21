---
title: 'Story 2.5: Look up a live Wallet'
type: 'feature'
created: '2026-11-21'
status: 'in-progress'
baseline_commit: 'd18fbe107c16fe28a75ca85bae0366b40e57d8b5'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A live run (no `--offline`) can only say "Live lookups not built yet". The client (2.1), window and snapshot (2.2) and the Position rules (2.3, 2.4) exist, but no page fetches a Wallet, nothing caches it, and outages and empty addresses have no page.

**Approach:** Opening `/wallet/<address>` in a live run serves a fresh stored snapshot at once; otherwise it queues a `job`, which one daemon worker thread runs through the existing `fetch_wallet`. The page shows the fetching state and polls the job; when it ends, the server-rendered result (Verdict, no history, outage) replaces the block.

## Boundaries & Constraints

**Always:** Fresh = one complete snapshot of the lookup view (`window_limit` = `WINDOW_LIMIT`) completed under 24 hours ago, chosen by one store function (AD-4); a fresh hit makes 0 network calls. Only the worker talks to Polymarket; a page never does. Worker claims with one atomic `UPDATE … WHERE id=? AND status='queued'`, `rowcount == 1`; lookups first (AD-5). A job left `running` at startup becomes `interrupted`. The worker starts only in `serve` (AD-23), never in `create_app`. Every page complete without JavaScript (AD-18). Words from EXPERIENCE.md; times through `core/phrases`. Offline Mode keeps Story 1.7's behaviour: no jobs, its stored snapshots never go stale (nothing to refresh from). One open `job` per Wallet: a lookup while one is queued or running joins it.

**Never:** Scan jobs, phases or Resume (Epic 4). Chart, honesty notes, copy button (Epic 3). Retrying inside a job beyond the client's own retry policy. Merging rows across snapshots. Offering a stored snapshot of another view.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First lookup | no snapshot | job `queued`, redirect to `/wallet/<a>?job=<id>`; heading "Checking 0x7c3a…d3f5", indicator, "Fetching trades from Polymarket…", link "Reload this page" | N/A |
| Second lookup | snapshot 3 h old | Verdict card, "Data stored …", no job, 0 transport calls | N/A |
| Stale | snapshot 25 h old | new job; on success the new snapshot replaces the old | N/A |
| Reload during fetch | job running | same job shown, no second job | N/A |
| No history | both positions lists empty | heading "No Polymarket history found", "No Polymarket history found for this address.", "Use the address shown on the Polymarket profile page. An address from a wallet app may show no history.", link *Check a wallet*; nothing stored | N/A |
| Only open bets | lists not empty, window empty | normal *Not enough data* Verdict (0 resolved bets) | N/A |
| Outage, old snapshot | `PolymarketUnavailable`, snapshot 3 days old | job `stopped`; heading "Polymarket did not answer", button "Show stored data from 18 Nov 2026, 14:02" → `?stored=1` shows that card | N/A |
| Outage, nothing stored | same, no snapshot | "Try again in a few minutes." | N/A |
| Unexpected error | `PolymarketBadRequest` or any other exception | job `failed`, logged; "Something went wrong" page | never a raw exception |
| Interrupted | `?job=` of an `interrupted` job | a new job is queued and shown | N/A |
| Unknown job | `/jobs/999/progress` | 404 | N/A |

**Decisions (AI, from the plan and one live probe, 2026-11-21):** (1) Data API v2 answers an unused address with 200 and empty lists (probe with a random address), so "no history" = OPEN and CLOSED both empty, raised as a new typed error from `positions_near`. (2) The profile hint is PRD §FR-1's sentence. (3) Schema version 4 (job table): `live.db` and `offline.db` are rebuilt, so `load-sample` must run once more.

**Decisions (Edvard, 2026-11-21, all AI recommendations: "yes to all three"):** (4) NFR-10 is timed now on a made-up 1,000-bet Wallet from stored data and noted; Story 2.6 times the real Wallets again. Edvard added: a hard 10 s timer can flake on a slow CI runner, so give it room or keep it local (left to the AI), and this test times only our own code, so 2.6's real check must include the Polymarket fetch. AI note for him to confirm: NFR-10 / SM-3 set 10 s for stored data only, so 2.6 measures and notes the fetch time without a 10 s target (a big Wallet's fetch alone can take 30 s at 5 requests per second). (5) Spec kept whole (about 2,100 tokens). (6) Subagents for review only.

</frozen-after-approval>

## Code Map

- `data/errors.py` -- add `NoPolymarketHistory(LookupError)`.
- `data/window.py:56-73` `positions_near` -- raise it when `open_list.rows` and `closed_list.rows` are both empty.
- `data/schema.sql`, `data/store.py` -- `job` table (id, kind, wallet, status, phase, done, total, message, result, created_at, finished_at); `SCHEMA_VERSION` 4. New: `serving_snapshot(wallet, window_limit, max_age)` (AD-4, one function), `stored_snapshot_time(wallet, window_limit)` for the outage button, `queue_lookup(wallet) -> id` (joins an open job, in one write), `claim_next_job()`, `finish_job(id, status, result)`, `job(id)`, `interrupt_running_jobs()`.
- `services/jobs.py` (new) -- `Worker(client, store, wake)`: daemon thread; `run_once()` claims one job and runs `fetch_wallet`; maps `NoPolymarketHistory` → `done`/`no_history`, `PolymarketUnavailable` → `stopped`, anything else → `failed` (logged). Tests call `run_once()` directly.
- `services/lookup.py` -- `Lookup(client, store, *, seed, jobs=None)`; `client` stays the Offline Sample client only (so Sample list and "not loaded" box stay off in live runs: closes the 2.1 issue). Live: `wallet_page(address, job=None, stored=False)` returns outcomes VERDICT, FETCHING, NO_HISTORY, UNAVAILABLE (with optional stored time), FAILED, or a redirect target. Remove `LIVE_NOT_BUILT`. Reuse `stored_result`.
- `services/fetch.py` -- `stored_result` takes the snapshot to use (fresh or stored fallback) instead of always the latest.
- `core/phrases.py` -- `stored_on(t)` ("18 Nov 2026, 14:02"), shared with `stored_at`.
- `__main__.py` -- `Sources` + `jobs`; live: `PolymarketClient(settings.polymarket_requests_per_second)`; `serve` interrupts running jobs, starts the worker when `sources.jobs` is set.
- `web/__init__.py` -- `/wallet/<a>` handles `job`/`stored` args and redirects; `GET /jobs/<id>/progress` JSON `{status, phase, done, total, message}`.
- `web/templates/fetching.html`, `unavailable.html` (new), `message.html` (hint line), `web/static/js/progress.js` (new: polls every 1 s, on end fetches the page, swaps `<main>`, focuses the h1), `static/css/app.css` (dots pulse; none with reduced motion).
- `README.md` -- live lookup works; `progress.js` listed; schema note (rerun `load-sample`).
- Reuse `tests/fake_polymarket.py` (`FakeTransport(answer=FakePolymarket(...))`) and its call list for the 0-call check; `tests/test_web.py` `live` fixture.

## Tasks & Acceptance

**Execution:**
- [x] `epics.md`, spine AD-5 (no-history = `done` with result), `deferred-work.md` (no-history item resolved), `.memlog.md` -- plan first.
- [x] `data/errors.py`, `data/window.py`, `data/schema.sql`, `data/store.py` -- no-history error, job table, freshness function.
- [x] `services/jobs.py`, `services/fetch.py`, `services/lookup.py`, `core/phrases.py` -- worker and live outcomes.
- [x] `__main__.py`, `web/__init__.py`, templates, `progress.js`, `app.css`, `README.md` -- wiring and pages.
- [x] tests -- every matrix row; atomic claim (two claimers, one wins); interrupt at startup; worker started only by `serve`; 0 calls on a fresh hit; progress JSON keys; architecture rules still pass; NFR-10 per Open Question 1.

**Acceptance Criteria:**
- Given `uv run pytest` with sockets blocked, then all pass.
- Given `uv run liquidoracle load-sample` then `run --offline`, then the Sample Wallets show as before.
- Given `uv run liquidoracle run` with the network on, when a real address is looked up twice, then the first shows the fetching state then a Verdict, and the second is instant (manual check, noted).

## Implementation Notes

- Written by the main session directly (subagents for review only, Edvard's call). 797 tests pass (769 before), 2 online tests deselected; both online tests passed live (3 requests). `load-sample`: 1,005 Wallets in 18 s on schema 4.
- Plan first: epics.md 2.5 (made-up 1,000-Position Wallet, no-history and offline notes) and 2.6 (real Wallets timed again, plus one live lookup with the fetch, no 10 s target), AD-4 (Offline Mode never goes stale) and AD-5 (lookup jobs) lines, two memlog entries, deferred-work no-history item resolved, Epic 2 context line.
- **NFR-10:** the made-up 1,000-Position Wallet gets its Verdict from stored data in 0.20 s on this laptop (Windows, Python 3.14). The test's limit is the requirement itself (10 s), about 50 times the measured time, so a slow CI runner does not make it flaky (Edvard's concern); it runs everywhere.
- **Live check (manual, 2026-11-21 17:24):** `run --port 8099`, real Sample Wallet 0x29306d: fetching page, job done after 1.8 s, then *Not enough data*, 18 resolved bets, Real PnL $295, "Data stored 21 Nov 2026, 17:24"; the second lookup answered in 0.003 s with no job. `progress.js` was not clicked through in a browser (no browser available in this session): Edvard should open one live lookup in a browser.
- Small choices: a page asks for `?job=<id>` and `?stored=1`; a job of another Wallet, a missing job or a non-number is ignored (usual lookup). A done job shows the fresh snapshot or queues again; stopped and failed jobs show their pages only while no fresh snapshot exists. The upper-case redirect keeps only `job` and `stored` (found while re-reading the diff: passing every query key could crash on `?raw=`). `Lookup` takes exactly one of the Offline client and the job queue, so the Sample list and the "not loaded" box stay off in live runs (closes the 2.1 issue). The worker's idle wait is 1 s [ASSUMPTION]; a new job wakes it at once.
- **Deviation from the Code Map:** no separate `queue_lookup` progress updates during the fetch (`done`/`total` go 0/1 to 1/1): `fetch_wallet` has no progress hook, and the page shows a fixed line anyway. `stored_snapshot_time` is named `snapshot_time`.
- AI slip: a bash heredoc with a long Python edit broke on quoting again (as the handoff warned); the edits went through script files in the scratchpad.

## Spec Change Log

## Review Triage Log

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass (769 before, 797 after).
- `uv run liquidoracle load-sample` -- expected: 1,005 Sample Wallets loaded.

**Manual checks:**
- Live run: one real Sample Wallet address looked up twice (fetching, then Verdict; then instant with "Data stored").
