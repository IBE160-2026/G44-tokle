---
title: 'Story 5.3: Hold-up Test on a live Scan'
type: 'chore'
created: '2026-11-27'
status: 'in-progress'
baseline_commit: '49ae83bd89c9c8890bd5cc45326ac07068fa50db'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-5-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The README's only Hold-up result comes from the Sample Dataset: its tested Passers are made-up Wallets and its Comparison Group rests on 3 real Wallets. SM-5 asks for the Hold-up Test on a live Scan of real Wallets, reported whichever way it comes out. No live Scan has ever been run with this app.

**Approach:** Run the app online, scan with the default Cut-off Date (1 July 2025) and the default Seed (44), and write what the app stored into the README and the reflection notes. Keep the Scan for Story 6.6. No code is added.

## Boundaries & Constraints

**Always:**
- The result is reported as it comes out (NFR-13, SM-C2): Hold-up result of both groups, Scan size, Markets used, Wallets not fully read, the date and how long it took.
- Every live run is reported, also one that was stopped or failed. Which run is "the result" is decided before any run starts, so it cannot be picked afterwards.
- Numbers are copied from the app's own pages or its database by a script, never typed from memory, and checked against the page.
- Addresses only, no trader names. The app stays read-only at 5 requests a second or fewer.
- The Scan is kept: `instance/live.db` is copied to `../G44-tokle-data/` with a SHA-256 file after the run.

**Ask First:** if a live run fails because of a bug in the app, stop and tell Edvard. A fix is its own small change (plan first, a test that fails before the fix), allowed until the 1 December code stop.

**Never:** no change under `src/` or `tests/` in this story; no second run with another Seed, date or size to get a nicer result; `instance/live.db` is never committed; no Copy Test (Epic 6).

**Decided (Edvard, 2026-11-27):**
- The Scan that counts is 200 Wallets, the app's default (the AI's recommendation; rejected: 50, where the Passers may end at *Not enough data*, and 500).
- A trial Scan of 10 Wallets runs first, to find live-only bugs while fixes are still allowed and to measure time and disk use. Its result is reported in the README in one line; the 200-Wallet Scan is the result, named before either starts (the AI's recommendation; rejected: straight to the big Scan).
- The AI runs the trial from the session; Edvard starts the 200-Wallet Scan in his own terminal and browser, so it keeps running if the chat closes (the AI's recommendation; rejected: the AI starts both).
- The spec is kept whole at about 1,950 tokens (over the 1,600 guideline).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Scan finishes | live Scan, 1 July 2025, Seed 44 | README section with both groups' rows, as the page shows them | N/A |
| No Passers, or a group under 30 bets | finished Scan | reported as it is (*Not enough data*, or "no Wallet passed") | N/A: a valid result (SM-C2) |
| Polymarket stops answering | Scan `stopped` | *Resume Scan*; the README says it was resumed | if it cannot finish: the README says how far it got and why |
| The app fails on live data | Scan `failed` | stop, tell Edvard | Ask First rule above |

</frozen-after-approval>

## Code Map

- `README.md` line 9 (status), line 21 ("Stage 2 so far"), line 114 ("A Hold-up Test on a live Scan … has not been run."): a new section `## The Hold-up Test on a live Scan` goes after the Sample Dataset section. `tests/test_holdup_page.py` line 488 reads the Sample section only up to the next `## `, so a new section does not touch what the tests pin.
- `src/liquidoracle/__main__.py` `open_sources`: a live run uses `instance/live.db`. Today that file is on layout 4 (23 November: 3 looked-up Wallets, no Scan); the first start rebuilds it. Nothing in it is needed.
- `services/scans_page.py`: the live form takes `cutoff` (blank by default, so 2025-07-01 is typed in) and `wallets` (10 to 500, default 200); `planned_requests` = 50 + 100 × 15 + 4 × N × 40 `[ASSUMPTION]`; after one finished live Scan the estimate is recalibrated from it.
- `services/scan.py` `run_scan`: 100 Markets (up to 30 pages each), 3 × N before parts, N after parts, then the Hold-up phase. Wallet parts under 24 hours old are reused by a later Scan with the same date. `PolymarketUnavailable` stops the Scan; *Resume Scan* carries on.
- Where the numbers are: `/scans/<id>/hold-up` (both group cards), `/scans/<id>/watchlist` (population line "N of 100 Markets used", Watchlist size, luck count), tables `scan`, `scan_market`, `scan_wallet`, `scan_result`, `group_result`, `job` in `instance/live.db`.
- Open item from Story 5.1 (`.logs/edvard-tokle/issues.md` line 116): time the Hold-up step and watch memory on the live Scan (22 s per 99,300 pooled bets offline).
- Plan: `epics.md` Story 5.3 (open-items paragraph), `sprint-status.yaml` (5-3, epic-5), the PRD `decision-log.md` through `_bmad/scripts/memlog.py`, `../IBE160-kursfiler/refleksjon-notater.md`.

## Tasks & Acceptance

**Execution:**
- [ ] `instance/live.db` -- run the app online and the Scan(s) as decided in Q1 to Q3; note start, end, requests refused, stops and resumes -- the run itself
- [ ] scratchpad script -- read the stored result read-only from `instance/live.db` and compare it with the Hold-up page and the Watchlist page -- numbers copied, not typed
- [ ] `README.md` -- new section with the result table (same columns as the Sample one), Scan size, Markets used, Wallets not fully read, Watchlist size, run date and time taken, and what the result can and cannot tell; status line and stage 2 list updated; line 114 replaced -- SM-5, NFR-13
- [ ] `../G44-tokle-data/` -- copy of `live.db` with a SHA-256 file -- the Scan is kept for Story 6.6
- [ ] `_bmad-output/planning-artifacts/epics.md`, decision log, `sprint-status.yaml` -- what was decided and how it went -- plan stays current
- [ ] `../IBE160-kursfiler/refleksjon-notater.md` -- the result and what the first live run taught -- the story's second acceptance line

**Acceptance Criteria:**
- Given the app online, when the Scan with Cut-off Date 1 July 2025 has finished, then the README states its Hold-up result for both groups, the Scan size, Markets used and Wallets not fully read, exactly as the app shows them.
- Given the finished Scan, when the app is started again, then the Scan is still in *Your Scans* with its Watchlist and Hold-up Test tabs, and a checked copy of the database lies outside the repository.
- Given this story's commits, when `git diff main --stat` is read, then nothing under `src/` or `tests/` changed, and `uv run pytest` with `CI=true` still passes.

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Verification

**Commands:**
- `git diff main --stat -- src tests` -- expected: empty.
- `uv run pytest` with `CI=true` -- expected: all pass, 0 skipped (1,702 before this story).

**Manual checks:**
- The README's live table against `/scans/<id>/hold-up` and `/scans/<id>/watchlist` in the running live app, cell by cell.
