---
title: "Story 2.2: A Wallet's bets as one complete snapshot"
type: 'feature'
created: '2026-11-20'
status: 'done'
baseline_commit: '8732a8801aa3ac5ae38f36bc076c4b000ab6650f'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A fetch today reads a Wallet's whole history and every Market in it. Epic 2 needs the AD-7/AD-8 window: the latest 2,000 Positions in resolved Markets, with Gamma's resolution time, fee schedule, start date and tags, and an activity read that covers the window, saved as one complete snapshot.

**Approach:** One function, `positions_near(client, wallet, cutoff=None, side=None, limit=2000)` in `data/window.py`, built on three raw reads that both `PolymarketClient` and `OfflineClient` offer, so live and offline take the same path (AD-13). `services/fetch.fetch_wallet` runs it under a per-Wallet lock and writes the result as one snapshot.

## Boundaries & Constraints

**Always:** OPEN list read in full; CLOSED list `sort_by=TIMESTAMP&sort_direction=DESC`, no `end`, stopping after a page whose oldest `last_event_at` is earlier than the `limit`-th latest `closedTime` collected (AD-7). Window = Positions whose Market Gamma calls closed with a `closedTime` (unclear resolution stays in, left out later by the builder, AD-11), ordered by `closedTime` newest first, capped before exclusions (AD-8). Gamma: 20 per request, `include_tag=true`; stored resolved Markets are reused, never refetched (AD-4). Activity: the five types, `start` and `limit` sent, `is_combo` dropped, identical rows kept, from the earliest window Market start to the latest window `closedTime`; on the cap or a partial read, Positions whose Market `closedTime` is after the last row read are left out as "not fully read". Snapshot visible in one final step; one fetch per Wallet at a time; schema `user_version` raised. Tests run through a fake transport on fixtures cut by a script; each test names its AD.

**Never:** A Cut-off Date side (Story 4.1: a `cutoff` raises `NotImplementedError`). Wiring live lookups or the job worker (Story 2.5). Fee checks, share gaps, activity-only tokens (Story 2.3). Event coupling (Story 2.4). Merging rows across snapshots.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Small Wallet | fixture 0x29306d, limit 2000 | all resolved Positions; one CLOSED page; activity range = earliest start to latest `closedTime` | N/A |
| Stop rule | limit 5, page size 4, CLOSED newest first | walk stops after the first page whose oldest `last_event_at` < 5th-latest `closedTime`; later pages never requested | N/A |
| Boundary Market | the `limit`-th place falls inside a Market's Positions | that Market is dropped whole (window ≤ limit, both sides of a Market stay together for AD-20) | N/A |
| Activity cap | cap 10 on a 51-row read | rows 1–10 kept; Positions with `closedTime` > row 10's time left out as "not fully read", counted | N/A |
| Partial positions list | CLOSED or OPEN read comes back incomplete | no snapshot written, older snapshot kept | `PolymarketUnavailable` |
| Stored Markets | second fetch, Markets resolved and stored | Gamma asked only for the rest | N/A |
| Two fetches | two threads fetch one Wallet | second waits for the first; both snapshots complete, rows never mixed | N/A |
| Reader mid-fetch | snapshot begun, not finished | readers get the previous complete snapshot | N/A |

**Decisions (Edvard, 2026-11-20, all AI recommendations):** (1) `ACTIVITY_ROW_CAP` = 150,000, the same cap as the Sample Dataset capture, so live and offline match and the PRD's stated limitation holds; about 30 s worst case, and only the biggest Wallets reach it. (2) The negative Own Fee moves to Story 2.3, where the fee-schedule check is built. (3) The fixture cut script fetches the real Gamma records for 0x29306d's and 0x091596's Markets once (read-only, raw kept in git-ignored `spike/raw/`); his 5 Nov rule is met, since his definitions and labels are committed. (4) Spec kept whole at about 2,200 tokens. Subagents for review only.

</frozen-after-approval>

## Code Map

- `records.py` -- `ListedPosition` + `last_event_at: int`; `Market` + `start_time: int|None`, `fee_rate: float|None`, `fee_exponent: float|None`, `tags: tuple[str, ...]` (Gamma `startDate`, `feeSchedule.rate/exponent`, tag labels); `ExclusionReason.NOT_FULLY_READ`; new `Window` record.
- `data/polymarket.py` -- `_walk` gains `until(page_rows) -> bool` (stop, complete) and `row_cap` (stop, incomplete); `markets()` sends `include_tag=true`; parsers read the new fields. Constants stay the 2.1 ones.
- `data/client.py` -- protocol becomes the three raw reads: `positions_list(wallet, status, *, sort_by, sort_direction, until)`, `activity_rows(wallet, *, start, end, row_cap)`, `markets(ids)`.
- `data/offline.py` -- implements the raw reads over the Sample file: filter, sort, pages of `PAGE_LIMIT` with `until`, cap; keeps `NotAvailableOffline`.
- `data/sample_json.py`, `data/synthetic.py` -- new fields (strict reader); synthetic `last_event_at` = sell time, else resolution (CLOSED) or last buy (OPEN); Market start = first buy − 1 day; no fees, no tags. Regenerate `sample_data/synthetic/*.json` with `make-synthetic`; `expected.json` must still hold.
- `data/schema.sql`, `data/store.py` -- `SCHEMA_VERSION` 2; new columns; snapshot stores `window_limit` and `activity_read_until` (NULL = complete); `resolved_markets(ids)`; `wallet_lock(wallet)` (one lock per address, shared by every thread using the Store).
- `core/positions.py` -- `build_positions(fills, markets, *, not_fully_read=())`: listed Positions of unread Markets come back left out as NOT_FULLY_READ, their fills ignored.
- `services/fetch.py` -- `fetch_wallet` under the lock; `stored_result` passes the unread Positions. `services/lookup.py:206` asks `positions_list(address, "CLOSED")` instead of `positions`.
- `__main__.py` `load_sample` -- unchanged call; check it still loads 1,005 Wallets.

## Tasks & Acceptance

**Execution:**
- [x] `records.py`, `data/sample_json.py`, `data/synthetic.py`, `sample_data/synthetic/` -- new fields, regenerate -- AD-14.
- [x] `data/polymarket.py`, `data/client.py`, `data/offline.py` -- raw reads with `until`/`row_cap`, Gamma fields -- AD-2, AD-7, AD-10.
- [x] `data/window.py` -- `positions_near` + `ACTIVITY_ROW_CAP` -- AD-7, AD-8.
- [x] `data/schema.sql`, `data/store.py`, `core/positions.py`, `services/fetch.py`, `services/lookup.py` -- snapshot, lock, cache, not-fully-read -- AD-4, AD-6, AD-11, AD-19.
- [x] `tests/fixtures/cut_from_capture.py` + `tests/fixtures/capture/*.json` -- cut 0x29306d and 0x091596 (positions, activity, Gamma) to raw API shape -- AD-17.
- [x] `tests/fake_polymarket.py` -- a routed fake server that pages and filters the fixtures like the API -- AD-17.
- [x] `tests/test_window.py` + updates to store/offline/positions/polymarket/synthetic tests -- every matrix row -- AD-7, AD-8, AD-19.
- [x] `tests/online/test_polymarket_live.py` -- CLOSED `TIMESTAMP DESC` comes back with non-increasing `last_event_at` -- AD-7.

**Acceptance Criteria:**
- Given `uv run pytest`, when it runs with sockets blocked, then all tests pass and `expected.json` still holds.
- Given `uv run liquidoracle load-sample`, when it runs, then all Sample Wallets load through `positions_near`.

## Implementation Notes

- Written by the main session directly (subagents for review only, Edvard's call). 684 tests pass (650 before), 1 online test deselected; the online test passed live (2026-11-20) and now also checks that CLOSED with `sort_by=TIMESTAMP&sort_direction=DESC` comes back newest last event first, which the stop rule rests on. `load-sample`: 1,005 Wallets in 21 s (15 s before).
- Plan first: AD-7 has the cap value (150,000), AD-8 says where `positions_near` lives and the whole-Market boundary rule; epics.md 2.2 has the value and 2.3 the negative Own Fee; two memlog entries.
- Gamma fetched once for the fixtures (20 Nov): 0x29306d 24 of 24 Markets, 0x091596 64 of 66 (two activity-only Markets unknown to Gamma). Raw kept in `spike/raw/sample/gamma_fixture/` (git-ignored). One fixture Market (0x07faaf…) is among Edvard's 50 hand-label Markets; its tags are now in a committed fixture. That does not touch the blind labels (committed 5 Nov); Story 7.1 must still score tag rules only on Markets outside the 50.
- Choices within the spec: the activity read starts at the earliest of the window Markets' start dates AND the window Positions' `first_entry_at`, so a missing or late Gamma start date cannot drop a buy; `Market.resolved` moved into `records` so the store's never-expire check and the builder share one rule (`core.positions.is_resolved` now calls it); the store's `wallet_lock` is a per-address `threading.Lock` held by `fetch_wallet` for the whole fetch; a row cap reached exactly at the end of a list counts as complete; `OfflineClient` serves pages of the live size (1,000) so `until` stops at the same place; a `ListedPosition` the cap left with no fill read becomes a left-out Position with only its shares bought; `.gitattributes` keeps the fixture JSON at LF.
- AI slip caught by its own test: a test assumed 0x091596's two Gamma-unknown Markets would be logged as missing; they are activity-only, so the window never asks Gamma about them (correct, AD-10). Split into two tests: activity-only Markets never asked, a listed Market Gamma does not know is logged and left out.
- Deliberate-break check before review: removing the stop rule, splitting a Market at the limit, skipping the store's Market cache and removing the Wallet lock each made a test fail.

## Spec Change Log

## Review Triage Log

Pass 1 (2026-11-20/21). Three reviewers: blind hunter (BH), edge-case hunter (EC), verification gap (VG). The diff sent to them left out the generated JSON (Sample files, fixtures), which they could read in the repo. 27 findings → 10 fix groups patched, 2 deferred, the rest rejected. No loopback: no finding traced back to the frozen intent or the spec.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| EC1 | A Gamma timeout inside the CLOSED walk's stop rule is taken for a page timeout: the walk restarts, and the ids already marked "asked" are never asked again, so their Positions drop out silently | medium | `_walk` caught `_PageTimedOut` from the whole loop, `until` included; `_MarketBook.learn` marked ids before fetching. Old code passed the new test only when the timeout hit page 1 | patch (group with BH3): `_ask_until` turns it into `PolymarketUnavailable`; `learn` marks ids only after Gamma answers; test aimed at page 2 fails on the old code |
| BH3 | The restarted CLOSED walk with `until` is untested | low | No test timed out a CLOSED page and then checked the stop rule | patch (EC1 group): restart test, the window equals the one without the timeout |
| BH1 | A Market resolved in the second the cap cut can keep half its fills and count as fully read | low | The cap can cut inside a second; `>` left that Market in. Fix is one character | patch (group with EC2, VG-o1): `>=`; AD-7 wording and memlog changed first; store test for that second |
| EC2 | Same as BH1 | low | Same | patch (BH1 group) |
| VG-o1 | Same as BH1 | low | Same | patch (BH1 group) |
| VG1 | A capped read never goes through `fetch_wallet`; dropping `activity_read_until=` passes every test | medium | Confirmed by mutation | patch: test with `positions_near` capped at 10 through `fetch_wallet` and `stored_result` (mutation now fails) |
| VG2 | No test opens a schema-version-1 database | medium | Only versions 0 and 99 were tested | patch: an Epic 1 database is rebuilt and takes a window snapshot |
| VG3 | "A token on both lists is kept once, from OPEN" is untested | low | No fixture has a shared token | patch: test moves a CLOSED row onto OPEN |
| VG4 | OfflineClient's paging, sort and cap are never run | medium | Parity test stayed on one page; mutation "offline ignores until" passed even the new two-page parity test | patch (group with BH6): parity test at page 4, limit 5, cap 10, plus direct OfflineClient tests (mutation now fails) |
| BH6 | OfflineClient untested and accepts `row_cap` 0 | low | Same; live refuses 0 | patch (VG4 group): offline refuses a cap below 1 |
| BH2 | An activity read cut short by timeouts is never tested | low | The fake could time out only positions pages | patch: fake times out activity pages; test |
| BH4 | The stop-rule test passes on an empty window | low | Both sides of its last assert could be `[]` | patch: compares the exact expected window |
| BH5 | The combo/identical-rows test checks neither claim | low | Lengths only; no proof the fixture has duplicates | patch: asserts duplicates exist in range and all copies arrive; combo dropping stays in test_polymarket |
| BH15 | One test mixes three checks | low | Cap test also did a fetch and pinned the constant | patch: split into three tests |
| BH16 | Fixture check reads only the CLOSED keys | low | OPEN, activity and Gamma never checked | patch: checks all sections against the script's own key lists |
| BH10 | deferred-work still sends the negative Own Fee to Story 2.2; no memlog for decision 2 | low | Confirmed | patch: a new deferred-work entry points to 2.3; memlog entry added |
| BH13 | `not_fully_read` method and module function share a name | low | Reads like recursion | patch: function renamed `unread_positions` |
| BH14 | `finish_snapshot` docstring badly wrapped | low | Confirmed | patch |
| BH9 | `wallet_lock` has no timeout, its table never shrinks, and it is per Store | low | Only the one worker thread fetches (AD-5); a lock per address is bytes; the app opens one Store per file | patch: docstring says the locks belong to the Store; the rest rejected (adds a timeout path with no user seen) |
| VG-o2 | A capture that stopped at the cap reads as complete offline | maybe-false | Would be medium for Story 2.6 (two capped Wallets) | defer: deferred-work.md |
| BH7 | The snapshot cannot tell whether the 2,000 cap applied (needed for the "latest 2,000" line) | low | No page shows the line yet (Epic 3); a later schema bump rebuilds the cache tables anyway | reject: low, adds a column with no reader; noted for Story 3.x in issues.md |
| BH8 | A malformed tag or fee schedule fails the whole lookup | low | Same strict rule as Story 2.1 for every Gamma field ("unreadable answer, never a guess"); 88 of 88 real Markets parse | reject |
| BH11 | Spec status and sprint status disagree | false | Step 5 sets sprint status to `review` when the spec is done | reject |
| BH12 | `offline.py` imports `polymarket.py` for two constants | low | Importing opens no connection; `requests` is a dependency anyway | reject |
| EC3 | Cap reached exactly with only combo rows left marks the read incomplete | low | Needs Polymarket to end a list on combo rows exactly at 150,000; fix adds a page read | reject |
| EC4 | The newest Market alone above `limit` gives an empty window | false | A tested Market has at most 2 outcomes and the limit is 2,000 | reject |
| EC5 | Unclear-resolution Markets take window places | false | Deliberate: AD-7 makes them part of the window and AD-11 leaves them out with a reason (memlog 2026-11-20) | reject |

After the patches: 695 tests pass, 1 online test deselected; load-sample 1,005 Wallets.

## Design Notes

The stop rule can miss a fully sold Position whose last event came before the 2,000th resolution time but whose Market resolved after it; such a Position would only be an exclusion (AD-7 accepts this). A token on both lists is kept once, from OPEN. A Market Gamma does not return is outside the window (logged).

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass (650 before, 695 after review).
- `uv run liquidoracle load-sample` -- expected: 1,005 Sample Wallets loaded.
- `uv run pytest -m online --force-enable-socket tests/online` -- expected: passes (by hand).
