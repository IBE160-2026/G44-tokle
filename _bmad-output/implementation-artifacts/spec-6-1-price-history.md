---
title: 'Story 6.1: Price history'
type: 'feature'
created: '2026-11-28'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '982febb7933dbc73d57d0c9e5b8af76a8b9d2e24'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-6-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Copy Test needs the market price a few minutes after each of a Wallet's buys, and the app cannot fetch, store or look up prices yet (FR-18c, AD-24). The live Scan of Story 5.3 must not have to be redone to get a Copy Test (Edvard, 2026-11-28).

**Approach:** One client function for one-minute price history, one pure rule `price_at`, price windows packed into requests of at most 14 days and stored for good, keyed by token so any Scan can use them. The store's schema rises to version 8 and keeps every Scan; that is proven on a duplicate of the real database.

## Boundaries & Constraints

**Always:**
- Only GET, no keys. The CLOB host is allowed for the path `/prices-history` and nothing else.
- Never a grain coarser than one minute: coarser points are dropped, never used.
- "One-minute" is the daily route check's rule (at least 40 points in its hour, median gap at most 90 seconds), from one place in the code, and a test runs the workflow's own script on the same answers and requires the same class.
- Only a definitive answer is stored. When Polymarket does not answer, nothing is stored and `PolymarketUnavailable` goes up, so a Resume fetches it again.
- A stored window is never fetched again: 0 requests.
- A schema change keeps Scans, their results, their frozen snapshots and all stored prices.
- The kept copy `live-scan-200-cutoff-2025-07-01.db` is never opened for writing: work on a duplicate.
- Decided with this story and written into the plan (Edvard, 2026-11-28): a finished Scan that has no Copy Test shows a "Run Copy Test" button; the app never starts it by itself. It is built in Stories 6.2 to 6.4, not here.

**Never:**
- No Copy Sample, Follower PnL, Scan phase, page or time-estimate change (Stories 6.2 to 6.4). No price windows in the Sample Dataset's real Wallets (Story 6.5).
- No change to how a Scan runs today, and no second Scan.
- If the duplicate of the real database does not come through the schema change whole, stop and ask Edvard; do not start the app on `instance/live.db` with the new code before that check passes.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Price at a time | points at t−30 s; at exactly t; at t−120 s | that point's price | N/A |
| Too old, or only later points | newest point at or before t is 121 s old; or every point is after t; or no points | `None` (the buy is left out by Story 6.2) | N/A |
| Windows of one token | fills 10 minutes apart; 2 days apart; 20 days apart | one merged window, one request; two windows, one request; two requests | N/A |
| A merged window over 14 days | fills every 20 minutes for 15 days | split into requests of at most 14 days each | N/A |
| Old route answers one-minute | probe class `one-minute` | CLOB `/prices-history`, `fidelity=1`; points returned, route `clob` | N/A |
| Old route coarse, empty or gone | probe class is anything else | `/v2/prices-history` with `bucket_seconds=60`; rows with `resolution_seconds` above 60 dropped; route `v2` | warning logged with the class |
| Old route turns coarse mid-run | an answer of 2 or more points with a median gap above 90 s | the check's request is sent again; if it no longer gets one-minute points, that answer is not used and the replacement route is asked instead; if it still does, the route is fine and the answer is used (Edvard, 2026-11-28, after the review) | warning logged when the route is left |
| Polymarket does not answer | 5xx or timeouts on every try | `PolymarketUnavailable`; nothing stored | job stops, Resume offered (as today) |
| A request Polymarket refuses | a 4xx that is not "route gone" and not a block | the window is stored with no points, route `refused` | warning logged; the run goes on |
| Polymarket blocks the client | a 401, 403, 407 or 451 on the check's request, a price request or the replacement route | `PolymarketUnavailable`; nothing stored (Edvard, 2026-11-28, after the review) | job stops, Resume offered |
| Window already stored | wanted window inside stored windows | 0 requests | N/A |
| Only points inside the short windows | a 14-day answer | points outside [fill − 2 min, fill + 32 min] are not stored | N/A |
| Version 7 file with a finished Scan | opened by the new code | version 8; Scan `done`, not `data_rebuilt`; results, Hold-up rows and snapshots as before; price tables empty | N/A |

</frozen-after-approval>

## Code Map

- `src/liquidoracle/data/polymarket.py` -- the one client. `_get_json` (retry policy), `_walk` (cursor pages: the replacement route has the same `data`/`pagination` shape), `check_url` and `_ALLOWED_HOSTS` (today Data API v2 and Gamma only), module docstring. Reuse; do not add a second transport.
- `src/liquidoracle/data/client.py` -- client protocols; add `PriceClient`.
- `src/liquidoracle/data/offline.py` -- `OfflineClient`, `_Index`, `_build_index`; `SampleWallet.prices` is already loaded (forecaster and speed trader hold one point a minute from −2 to +32 around each later buy).
- `src/liquidoracle/records.py` -- `PricePoint(token_id, t, price)` exists; add `PriceRead(points, route)`.
- `src/liquidoracle/data/schema.sql`, `data/store.py` -- `SCHEMA_VERSION = 7`, `KEPT_TABLES`, `_ADDED_LATER`, `_copy_scans`, `_prepare_schema` (rename, copy by shared columns, one transaction). Only the store runs SQL.
- `src/liquidoracle/core/` -- pure layer (imports `records` and numpy only); new `prices.py`.
- `.github/workflows/price-route-check.yml` -- the route check: token, hour, classes and the 40/90 rule inside its inline Python. Not changed.
- `tests/fake_polymarket.py` (`FakeTransport`, `ok`, `status`, `page`), `tests/test_polymarket.py` (URL guard tests near line 95: the CLOB URL is in the refused list today), `tests/test_scan_job.py` lines 478 to 600 (schema-change tests with `NEXT_VERSION`, the version 6 file test to model on), `tests/online/` (live tests, never in CI).
- `../G44-tokle-data/check_readme_live_scan.py <repo> --db <file>` -- checks every README number of the live Scan against a database, read-only.
- Measured 2026-11-28: the old route gives 60 points for the check's hour and 19,615 for a 14-day window (`{"history":[{"t","p"}]}`). The replacement route is `data-api.polymarket.com/v2/prices-history?token_id=&start=&end=&bucket_seconds=60`, answers `{"data":[{"timestamp","price","resolution_seconds"}],"pagination":{...}}`, refuses `market=` with 400, and gives an empty list for July 2025. The kept copy: both Scans `done`, 200 of 200 after snapshots present, 118 Wallets with 10 or more after Positions, at most 9,644 Positions to price.

## Tasks & Acceptance

**Execution:**
- [x] `_bmad-output/planning-artifacts/epics.md`, `ARCHITECTURE-SPINE.md` (AD-5, AD-6, AD-24), memlogs, `sprint-status.yaml` -- record before any code: the finished-Scan requirement, the replacement route's measured shape, the probe rule, what is stored, the kept price tables; 6-1 and epic-6 `in-progress` -- plan first.
- [x] `src/liquidoracle/core/prices.py` -- `price_at`, `fill_windows`, `uncovered`, `pack` with their constants (2 min, 32 min, 14 days) -- pure rules.
- [x] `src/liquidoracle/records.py`, `data/client.py` -- `PriceRead`, `PriceClient` protocol.
- [x] `src/liquidoracle/data/polymarket.py` -- `price_history(token_id, start, end)`, `route_class`, the probe (the route check's request, repeated after an hour of use), the per-answer guard, the replacement route through `_walk`, `check_url` for the one CLOB path; docstring.
- [x] `src/liquidoracle/data/offline.py` -- `price_history` from the Sample files' points, route `sample`.
- [x] `src/liquidoracle/data/schema.sql`, `data/store.py` -- version 8: `price_window` (token, start, end, route, fetched_at) and `price_point` (token, t, price); `save_prices` (one transaction), `price_windows`, `prices`; both tables kept at a schema change; a log line when a kept database is converted.
- [x] `src/liquidoracle/services/prices.py` -- `plan(store, token_id, fill_times)` (the requests still needed) and `fetch(client, store, request)` (one request, one unit of work for Story 6.2's phase).
- [x] `tests/test_prices.py`, `tests/test_polymarket.py`, `tests/test_store.py`, `tests/test_scan_job.py`, `tests/test_offline.py`, `tests/online/test_polymarket_live.py` -- every matrix row; the workflow-agreement test; URL guard (CLOB `/prices-history` allowed, any other CLOB path refused); prices kept across a later schema change; one live test of both routes.
- [x] `README.md` -- only where it names what the app contacts, if it does.

**Acceptance Criteria:**
- Given the route check's workflow file, when its inline script and `route_class` classify the same answers (one-minute, coarse, empty, gone), then they give the same class.
- Given a duplicate of the kept live database, when the new code opens it, then it is at version 8, `check_readme_live_scan.py --db` reports no miss, and the time and file size of the change are noted here.
- Given that converted duplicate and the network, when the price windows of one after-part token of Scan 2 are planned and fetched, then its points are stored, a second plan needs 0 requests, and `price_at` gives a price 5 minutes after one of its buys.
- Given the full test suite with sockets blocked, when it runs, then it passes, and the layer and "only the store runs SQL" tests still hold.

## Implementation Notes

- Built directly from the spec, with no helper for the build (Edvard: helpers for the review only).
- New: `core/prices.py` (`price_at`, `fill_windows`, `uncovered`, `pack`, `inside`), `services/prices.py` (`plan`, `fetch`), `tests/test_prices.py`. `records.py` gained `PriceRead`, `PriceRequest`, the route names and `PRICE_REQUEST_SPAN` (the 14 days live there because `data` may not import `core`). `PolymarketClient.price_history`, `route_class`, `one_minute_grain`; `OfflineClient.price_history`; `sample_json.read_ids` now also returns the tokens that have price points, for the offline index. Schema 8: `price_window`, `price_point`; `Store.save_prices`, `price_windows`, `prices`.
- **Changed while building, inside the frozen intent:** the first version treated any old-route answer with a median gap above 90 seconds as "the route has turned coarse" and went to the replacement route for the next hour. One of the story's own tests (two points 10 minutes apart on a healthy route) showed what that would do: one thin token would send every later token to a route that has no prices for 2025, and their empty answers would be stored for good. Now such an answer makes the client send the check's request again at once; the old route is left only if that request no longer gets one-minute points, and the thin answer is used if it still does. The matrix row "Old route turns coarse mid-run" holds as written. `epics.md` and AD-24 say it this way.
- A request the old route answers with 404 or 410 counts as "route gone" (the replacement is asked); any other 4xx is a refusal of that request.
- Where the client is stricter than the workflow: a 200 answer that is not JSON, or a 3xx, is "empty" or "gone" to the workflow but stops the job in the client (`PolymarketUnavailable`), because nothing may be stored as "no price" on an answer the client cannot read. The agreement test covers the classes both can see: one-minute, coarse, empty and gone on a 4xx.
- An unknown token offline gives no points instead of `NotAvailableOffline`, as live when Polymarket has no price, so the buy is left out and counted. The real Sample Wallets have no stored points until Story 6.5.
- README: it names no Polymarket host or route, so nothing changed there.
- **The duplicate of the real database (2026-11-28).** A copy of the kept `live-scan-200-cutoff-2025-07-01.db` (SHA-256 checked against its file before and after: unchanged) was opened by the new `Store`: version 7 to 8 in 70 seconds, while the test suite was also running. Both Scans are `done` and not `data_rebuilt`; the six scan tables are identical row for row (2 Scans, 200 set Markets, 378,172 candidates, 630 shortlisted Wallets, 420 results, 4 group results), as are the 3 scan jobs, the 799 frozen snapshots, their 200,333 positions and 4,635,147 activity rows; `quick_check` ok. The file grows from 1.14 GB to 2.27 GB, because the change copies the kept tables and SQLite keeps the freed space for reuse. `check_readme_live_scan.py --db <duplicate>`: 20 checks, no miss.
- **One real token, live.** On that duplicate: an after-part token of Scan 2 with 64 buy fills needed 1 price request (after the check's request), answered by the old route; 50 points stored; planning the same fills again needs 0 requests; all 64 buys have a price 5 minutes later (for example 0.165 one and five minutes after the first buy, 0.006 after thirty).
- For Edvard before the app is next started on `instance/live.db`: the first start converts it once (about a minute, a log line says so) and the file roughly doubles to about 2.3 GB. The kept copy stays as it is.
- **After the review (2026-11-28).** Three helpers read the diff: 41 findings (blind hunter 16, verification gap 7, edge cases 18). 33 led to fixes, 4 were rejected, 2 were deferred with a third part, and 2 go to Edvard because they touch the approved table (below). None found a wrong price or a lost Scan row; the serious ones were all one fault, seen from three sides: the client could leave the old price route, or store "no price" for good, on too little evidence.
  - A 404 or 410 on one token moved every later token to the replacement route for an hour. Now it only sends the check's request again, like a thin answer does.
  - A 200 answer to the check's request in another shape was classed "empty" and left the route. Now it is unreadable, like any such answer.
  - A block (401, 403, 407, 451) was stored as "refused, no price" window after window, and on the check's request it read as "route gone". Now it stops the job like an outage and stores nothing.
  - The check was repeated only hourly, and a whole Copy phase fits in an hour. Now also after 200 price requests; and a check younger than a minute settles a doubt without another request.
  - The store relabelled a window's route when a wider window with the same start was stored. Now each asked window is its own row. The tables got CHECK constraints.
  - Found on the way, in code from Story 4.3 that this story is the first to run on a 1 GB file: any database error while the snapshots were copied (a full disk, not only a schema mismatch) marked the Scans "data rebuilt" and dropped their snapshots. Now only a constraint failure does that; anything else rolls the whole change back and leaves the file as it was. A test plants a "disk is full" error and opens the file again.
  - Offline: the same refusals as live for a bad request, files written after the start are found, two different prices for one second are an error. `PriceRequest` checks itself. `route_class` says `unreachable` for a 5xx, as the workflow does.
  - Plan: the "Run Copy Test" button now has acceptance criteria under Stories 6.2 and 6.4, a row in EXPERIENCE.md and a sentence in FR-18; Story 6.1 has a criterion for what is stored and kept. README: a paragraph on the first start after an update.
- **Two places where the code differed from the approved table; Edvard accepted both on 2026-11-28 ("1 yes 2 yes"), and the frozen block and the Spec Change Log now say so.** As they were put to him:
  1. Row "Old route turns coarse mid-run" says an answer with a median gap above 90 seconds is not used. Built: it is not used when the check's request then fails; when the check still passes, the route is fine and the thin answer is used. My earlier note here that the row "holds as written" was too generous: for a thin answer on a healthy route it does not.
  2. Row "A request Polymarket refuses" says any 4xx that is not "route gone" is stored with no points. Built: 401, 403, 407 and 451 are not stored; they stop the job, because they say nothing about the token ("Only a definitive answer is stored").
- The offline price tests are in `tests/test_prices.py`, not `tests/test_offline.py` as the task line says (edge-case review); `test_offline.py` is unchanged.
- **Proof repeated on the final code** (the price tables changed in the review): a fresh duplicate converted in 61 seconds, all Scan facts identical, the kept copy's checksum unchanged, `check_readme_live_scan.py` 20 checks and no miss, and the same token fetched live again (1 request, 50 points, 0 requests when planned again, 64 of 64 buys priced at 5 minutes).

## Spec Change Log

- **2026-11-28, after review pass 1, by Edvard's decision ("1 yes 2 yes"), no loopback.** Findings BH5 and EC18 (the thin-answer rule did not match the frozen row "Old route turns coarse mid-run") and BH3, VG5 and EC9 (a block was stored as "refused, no price", against "Only a definitive answer is stored"). Amended inside the frozen block, by the human's renegotiation: that row now says the check's request is sent again and the answer is used when it still passes; the row "A request Polymarket refuses" excludes blocks; a new row "Polymarket blocks the client" says a 401, 403, 407 or 451 stores nothing and stops the job. Known-bad states avoided: one thin token sending every later token to a route with no prices for 2025, and a blocked run that "finishes" with every window stored as no price. KEEP: leaving the old route always rests on the daily check's own rule; nothing is stored on an answer that is not about the token; the proof on a duplicate of the real database before the app touches `instance/live.db`.

## Review Triage Log

Pass 1 (2026-11-28). BH = blind hunter, VG = verification gap (VG5 to VG7 are its "other findings"), EC = edge-case hunter.

| # | Finding | Verdict | Evidence and route |
|---|---------|---------|--------------------|
| BH1 | A 404 or 410 on one token marks the old route gone with no re-check | high | True at `price_history`: `_set_old_route("gone-…")` ran on one answer; an hour of tokens would go to a route with nothing for 2025 and be stored empty. Patched: the check's request is sent again first; test for both statuses and for the next token. |
| BH2 | An old route that turns empty or coarse mid-run is not noticed for an hour | medium | True: 0 or 1 points pass the grain rule and 3,600 s is more than the whole phase. Patched: the check is also sent again after 200 price requests (`PROBE_REQUESTS`), with a test. |
| BH3 | Answers that are not definitive are stored for good: empty v2 windows, 401/403 as refused, a 403 on the check as gone; no circuit breaker; the route column is never read | high | Blocks: true, patched (`BLOCKED_STATUS` raises `PolymarketUnavailable` on the check, a price request and the replacement route; 12 test cases). Narrows a frozen matrix row: to Edvard. Empty v2 windows for old dates: the plan's stated behaviour (FR-18c), marked by their route; rejected. Circuit breaker and reading the route: rejected as low, the block fix removes the case and a later story reads the column. |
| BH4 | The check's answer is read more loosely than a price answer: another shape is classed empty or coarse | medium | True at `_old_route_class`. Patched: not a history list of rows with whole-second times is unreadable (`PolymarketUnavailable`); six test cases. |
| BH5 | The thin-answer rule departs from the frozen matrix row while the notes say it does not | medium | True: the row says such an answer is not used; the code uses it when the check still passes. Not patched: it is the human's call. Notes corrected; question to Edvard. |
| BH6 | Each thin answer costs one extra request, with no cooldown | low | True (7 calls for 3 thin tokens). Patched: a check younger than 60 s (`PROBE_TRUSTED`) settles a doubt; the thin-answer test asserts the second thin token sends no check. |
| BH7 | A window's route label can end up wrong after an upsert | medium | True: the conflict clause overwrote `route` while old points stayed. Patched: the key is (token, start, end), each asked window its own row; test with three routes. |
| BH8 | Adding two empty tables rewrites the whole live Scan; no additive path, no disk check, no README line | medium | Copy cost true (61 to 70 s, file doubles). README paragraph added. Disk: `_copy_scans` caught every `sqlite3.Error`, so a full disk would have dropped the snapshots; patched to `IntegrityError` only, with a planted disk-full test. The additive path changes AD-6: deferred. |
| BH9 | The offline client accepts bad input the live one refuses; conflicting points; cache eviction | low | True. Patched: token, whole seconds and the 14-day span are checked offline too; two prices for one second raise. The one-slot cache re-read is rejected: no shared tokens exist before Story 6.5, where the files are built. |
| BH10 | The Run Copy Test button has no owner in the plan | medium | True: only in the Epic 6 intro, AD-5 and a memlog. Patched in the plan: criteria under Stories 6.2 and 6.4, an EXPERIENCE.md row, a sentence in FR-18, the epic context; its states are named as open for Story 6.4's planning. |
| BH11 | `route_class` claims to be the workflow's rule but gives gone-503 for a 5xx | low | True. Patched: a status of 500 or more is `unreachable`; two rows added to the agreement test. |
| BH12 | Missing tests: route recovery, the warning once per change, 410, a 400 and a first-page timeout on the replacement route, a row without its resolution, the migration log line; two weak tests | medium | True for each (none existed). All added; the interface test now compares signatures; the live test no longer requires the replacement route to be empty. |
| BH13 | `PriceRequest` accepts states its docstring rules out | low | True (empty windows gave IndexError). Patched: `__post_init__` refuses no window, windows out of order or overlapping, and a span over 14 days; test. |
| BH14 | The price tables have no constraints, and `save_prices` checks points slowly | low | True. Patched: CHECK on route, window order and price 0 to 1 (test); the point check uses bisect and handles overlapping windows (test). |
| BH15 | The dropped-points count can double after a restarted walk; a deterministic missing cursor loops on Resume | low | Count: only a log number, and resetting it needs a change inside `_walk`; rejected. Missing cursor: a loud failure on a case never shown to happen; rejected. |
| BH16 | Planning documents disagree with the code and each other | low | True for the epic context ("one definition") and the missing 6.1 criterion: both patched. Sprint status is set to `review` with the spec at the end of the workflow. |
| VG1 | A 410 on a real request and the gone state after a 404 are not pinned | medium | Filed as a regression gap. Patched with BH1: tests for 404 and 410, the next token, and the case where the check still passes. |
| VG2 | A window stored again: the route and fetch time are not asserted | medium | Filed as a regression gap. Patched with BH7: the route of each row is read back after three saves and after a replace. |
| VG3 | The log line when a kept database is converted has no test | low | Filed as a regression gap. Patched: the version 7 test asserts the line and that a new file does not log it. |
| VG4 | The live test of the replacement route can only see an empty list | medium | Filed as a broken-verification gap with disposition defer: a real row needs a token traded in the last week. Deferred (`deferred-work.md`); unverified here. |
| VG5 | A refusal that is not about one token (401/403) is stored as no price for good | high | carried from BH3: patched, to Edvard. |
| VG6 | A 200 check answer of another shape is read as empty; workflow and client can differ on rows without `t` or float times | medium | carried from BH4: patched. The client is stricter than the workflow by choice (it stops instead of leaving the route); stated in the notes. |
| VG7 | `OfflineClient.price_history` does not list the files again on a miss and accepts requests the live client refuses | low | True. Patched: `_refresh` on a miss (test with a file written after the start) and the live client's refusals. |
| EC1 | Check answers 200 with no history list, or rows with float or missing `t` | medium | carried from BH4: patched. |
| EC2 | One token's 404 or 410 with no re-check | high | carried from BH1: patched. |
| EC3 | Route turned coarse; a single-window answer holds 0 or 1 points | medium | carried from BH2: patched. |
| EC4 | Many thin tokens each send the check again | low | carried from BH6: patched. |
| EC5 | Old route answers 3xx, 429 or a CloudFront 403 for good: the job stops on every Resume and never falls to the replacement | low | True, by choice: the client stops rather than store empty answers on something it cannot read. The replacement route has nothing for 2025 anyway, and Story 6.6 then uses the insurance pool. Rejected: the fix adds failure counting for no gain. |
| EC6 | One history row without `t`, or all float times: workflow and client class differently | low | carried from BH4: the client now refuses both as unreadable. The remaining difference is stated in the notes. |
| EC7 | `route_class` called with a 5xx | low | carried from BH11: patched. |
| EC8 | `start` or `end` is None, a float or a numeric string | low | True: `int()` truncated 1.9 and accepted '3'. Patched: whole numbers only, in both clients; four test cases. |
| EC9 | A 4xx not about this token: 401, a plain 403, 451 | high | carried from BH3: patched in the client, to Edvard. |
| EC10 | A stored token id that is not 1 to 100 digits makes the job fail without Resume | false | Token ids come from Polymarket's own trade rows and are decimal numbers (the Synthetic Wallets' too); no path was shown that stores another. A loud failure on a state never shown to be reachable; rejected. |
| EC11 | A window with stored points is re-asked wider and refused or answered by v2 | medium | carried from BH7: patched. |
| EC12 | A version 8 file opened by version 7 code loses both price tables | medium | True, and older than this story: any other version is rebuilt (AD-6, Story 1.6, with a test at version 99). Refusing a newer file changes that rule. Deferred, with the advice not to start an older checkout on a converted `instance/live.db`. |
| EC13 | `PriceRequest` with empty or overlapping windows | low | carried from BH13: patched. |
| EC14 | A token's Sample file written after the index was built | low | carried from VG7: patched. |
| EC15 | An offline window over 14 days or a token id that is not a number | low | carried from BH9: patched. |
| EC16 | Two Sample files hold different prices for one token and second | low | carried from BH9: patched. |
| EC17 | Claim: the tasks line names `tests/test_offline.py`, which the diff does not change | low | True: the offline price tests are in `tests/test_prices.py`. Its fix is an edit of this spec's task line: rejected by the rule; said in the notes instead. |
| EC18 | Claim: the matrix row "Old route turns coarse mid-run" no longer matches the code and its test | medium | carried from BH5: true; to Edvard. |

## Design Notes

- The probe makes the client's test the same as the daily check's: an alert from the workflow means the client would also leave the old route. The per-answer median-gap guard covers a change inside the hour between probes; an answer of 0 or 1 points proves nothing about grain, which is why the probe is repeated.
- Prices belong to a token, not to a Scan or a Wallet, so the finished live Scan needs nothing fetched again except prices. How a finished Scan gets its Copy Test (Stories 6.2 to 6.4) is recorded in the plan with this story.
- Windows are stored unmerged with their route, so empty windows that came from the replacement route or a refusal can be told apart later.

## Verification

**Commands:**
- `uv run pytest` with `CI=true` -- expected: all pass (1,702 before this story, plus the new ones).
- `uv run pytest -m online --force-enable-socket tests/online -k price` -- expected: pass (by hand, network on).
- `python -I ../G44-tokle-data/check_readme_live_scan.py . --db <duplicate>` after the new `Store` has opened the duplicate -- expected: no MISS.
- `git diff main --stat -- src/liquidoracle/services/scan.py src/liquidoracle/web` -- expected: empty.

**Outcome (2026-11-28):** the full suite passes with sockets blocked, 1,825 tests (1,702 before the story), 4 online tests left out as always; the live price test passes by hand; the duplicate check reports no MISS (20 checks) on the final code; `scan.py` and `web/` are unchanged.
