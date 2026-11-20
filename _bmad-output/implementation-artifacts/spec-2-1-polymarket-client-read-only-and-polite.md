---
title: 'Story 2.1: Polymarket client, read-only and polite'
type: 'feature'
created: '2026-11-20'
status: 'done'
baseline_commit: '7b821aec0f15902d3dedde842e287798809ec367'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The app cannot read live Polymarket data yet. Epic 2 needs one careful client that only reads public data, keeps to the rate limit across threads, survives outages, and hands typed records to the rest of the app.

**Approach:** Add `data/polymarket.py`: an HTTP layer you can swap out (a real `requests` one and a fake one for tests), one locked rate limiter, the one retry policy, a cursor walker, and parsers into `records` types. It offers three reads: one positions list (CLOSED or OPEN), activity rows, and Gamma Markets. Nothing in the app calls it until Story 2.2 (window) and Story 2.5 (live lookups).

## Boundaries & Constraints

**Always:** Only GET requests to `https://data-api.polymarket.com/v2/...` and `https://gamma-api.polymarket.com/...`. The client checks every URL before sending and refuses anything else, including Data API v1 (any data-api path not under `/v2/`). No keys, no auth headers; User-Agent `liquidoracle/0.1 (student project)`. Every request (retries too) passes the one limiter at `settings.polymarket_requests_per_second`. A cursor walk sends identical parameters on every page apart from `cursor`; `limit` is always sent. Raw JSON never leaves `data/`. Time comes back as epoch seconds (`closedTime` "2025-04-17 08:51:19+00" is parsed in `data/`). Each test names its AD.

**Never:** Wiring the client into `open_sources` or the pages (Story 2.5). Window logic, `positions_near`, `ACTIVITY_ROW_CAP`, snapshots or new tables (Story 2.2). Gamma `include_tag` (Story 2.2). Fee checks (Story 2.3). Real sockets in normal tests.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy walk | 3 pages, `has_more` false on the last | All rows as records, `complete=True`; pages 2 and 3 send page 1's params plus `cursor` | N/A |
| Retried error | timeout, failed connection, 429, 500, 502, 503, 504, Gamma 403, any 403 marked CloudFront, Gamma 404 with empty body | Up to 3 tries in all; back-off 1 s then 2 s | 3rd failure → `PolymarketUnavailable` |
| Retry-After | 429 with `Retry-After: 7` | Waits exactly 7 s (fake clock), that wait counts as a try | as above |
| Long Retry-After | 503 with `Retry-After: 61` | No wait, no further try | `PolymarketUnavailable` at once |
| Mid-walk timeout | page ≥ 2 still timing out after 3 tries | Walk restarts once from the start with `limit` halved | Fails again mid-walk → rows so far, `complete=False`; failing on page 1 → `PolymarketUnavailable` |
| Bad request | other 4xx | `PolymarketBadRequest`, logged (status, path, not the body) | 400 containing "protocol contract address" → `ProtocolContractAddress` (a kind of `PolymarketBadRequest`) |
| Two threads | 2 threads × 10 requests, rate 5 | Request start times at least 0.2 s apart (fake clock) | N/A |
| Combo rows | activity row with `is_combo: true` | Dropped | N/A |
| Gamma batch | 45 condition ids | 3 requests of at most 20 ids (`condition_ids` repeated), Markets back in asked order, missing ids skipped | N/A |

**Decisions (Edvard, 2026-11-20):** (1) a `Retry-After` over 60 s is not waited out; `PolymarketUnavailable` is raised at once, because nobody waits minutes for a page. (2) 500, 502, 504 and a failed connection are retried like 503, because no internet is the same as an outage to the user. Both written into AD-3 first. (3) Spec kept whole at about 2,200 tokens.

</frozen-after-approval>

## Code Map

- `src/liquidoracle/data/errors.py` -- has `NotAvailableOffline`; its docstring already promises the two Polymarket errors here.
- `src/liquidoracle/records.py` -- `ActivityRow`, `ListedPosition`, `Market` are what the parsers return, unchanged. `last_event_at` (Story 2.2's stop rule) is not added here: the strict Sample JSON reader wants exactly the record's fields, so a new field changes the committed files; Story 2.2 adds it with that change.
- `src/liquidoracle/data/client.py` -- `WalletClient` protocol. Don't change it here; Story 2.2 reworks it around `positions_near`.
- `src/liquidoracle/settings.py` -- `polymarket_requests_per_second` is already checked (≤ 5); reuse it, no new setting.
- `src/liquidoracle/__main__.py` `open_sources` -- leave live mode as it is (`client None`).
- `tests/test_architecture.py` -- `ALLOWED_THIRD_PARTY["data"]` allows `requests` for the whole `data` layer; narrow that to `data/polymarket.py` (and `anthropic` to `data/model.py`).
- `tests/online/` -- conftest marks everything here `online`; `test_online_marker.py` is a placeholder.
- Real field names (from the capture, `spike/raw/sample/capture/`, git-ignored): positions `{data: [...], pagination: {has_more, next_cursor}}` with `token_id, condition_id, total_size, first_entry_at, last_event_at`; activity rows `type, condition_id, timestamp, size, usdc_size, price, token_id, side, is_combo`; Gamma `conditionId, closed, closedTime, clobTokenIds` (JSON string), `outcomePrices` (JSON string), `feesEnabled`.

## Tasks & Acceptance

**Execution:**
- [x] `src/liquidoracle/data/errors.py` -- add `PolymarketUnavailable`, `PolymarketBadRequest`, `ProtocolContractAddress(PolymarketBadRequest)` -- typed errors (Conventions › Errors).
- [x] `src/liquidoracle/records.py` -- add `Read` (frozen: `rows: tuple`, `complete: bool`) -- a capped or failed walk stays visible (AD-3).
- [x] `src/liquidoracle/data/polymarket.py` -- `Transport` protocol + `RequestsTransport` (timeout 5 s to connect, 30 s to read; only `Session.get`); `RateLimiter(rate, clock, sleep)` with a lock; `PolymarketClient(rate, transport=None, clock=..., sleep=...)` with `positions_list(wallet, status, *, sort_by=None, sort_direction=None, limit=1000) -> Read[ListedPosition]`, `activity_rows(wallet, *, start, end=None, sort_direction="ASC", limit=1000) -> Read[ActivityRow]` (types TRADE, REDEEM, SPLIT, MERGE, CONVERSION), `markets(condition_ids) -> tuple[Market, ...]` -- AD-2, AD-3.
- [x] `tests/fake_polymarket.py` -- fake transport (scripted responses, records each call's URL, method and params) and fake clock -- tests without sockets (AD-17).
- [x] `tests/test_polymarket.py` -- every row of the I/O matrix, plus: URL guard refuses a v1 path, another host and a non-GET; the module has no `post/put/patch/delete` call; parsers on rows shaped like the capture -- AD-2, AD-3, AD-17.
- [x] `tests/test_architecture.py` -- only `data/polymarket.py` may import `requests` -- AD-2.
- [x] `tests/online/test_polymarket_live.py` -- one smoke test: first CLOSED page (`limit=5`) of Sample Wallet 0x29306d… comes back as `ListedPosition`s; replaces the placeholder -- AD-17.
- [x] `README.md` -- one line under Tests on running the online test by hand.

**Acceptance Criteria:**
- Given the full test suite, when it runs with sockets blocked, then every new test passes on the fake transport and the online test is deselected.
- Given `uv run pytest -m online --force-enable-socket tests/online`, when Edvard runs it by hand, then the smoke test passes against live Polymarket.

## Implementation Notes

- Written by the main session directly (subagents for review only, as in earlier stories). 609 tests pass (507 before), also on Python 3.12; the online test passed live once (2026-11-20).
- **Live finding (2026-11-20):** without a `closed` parameter Gamma `/markets?condition_ids=...` returns only open Markets; `closed=true&closed=false` returns only closed ones and `closed=all` is refused (422). So `markets()` asks each batch with `closed=true`, then asks the ids still missing with `closed=false`. Usually one request per batch, since window Markets are resolved. Checked with a 4-request probe script in the scratchpad (not committed); the spike always sent `closed=true`, so it never saw this.
- `ListedPosition.last_event_at` was not added (see Code Map): the strict Sample JSON reader wants exactly the record's fields, so the field would change the committed Sample files. Story 2.2 adds it together with that change.
- Choices within the spec: `RateLimiter.wait()` returns the start time it granted (so the two-thread test reads the limiter's own slots, not a fake-clock time that moves while the other thread sleeps); an answer that is neither 200, retried nor 4xx (3xx, 501, 204) raises `PolymarketUnavailable` without a retry; a 200 that is not JSON, or rows not shaped as expected, raise `PolymarketUnavailable` ("unreadable answer"), never a guess; `has_more` without a new cursor (or a repeated cursor) gives a partial read instead of looping; a mid-walk 503 raises (only timeouts restart the walk); a past or negative `Retry-After` waits 0 s; redirects are not followed (they could leave the allowed hosts); one `requests.Session` per thread.
- The online smoke test first used `limit=5`, which walked several pages instead of reading only the first; it now reads the default page size (this Wallet's whole CLOSED list fits on page 1) and checks `complete`. Caught by the AI while writing the README line.
- `tests/online/test_online_marker.py` (placeholder) removed; `test_architecture.py` now checks the deselection with the live test.

## Spec Change Log

## Review Triage Log

Pass 1 (2026-11-20). Three reviewers: verification gap (VG), blind hunter (BH), edge-case hunter (EC). 44 findings → 14 fix groups patched, 1 deferred, the rest rejected. No loopback: no finding traced back to the frozen intent or the spec.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| VG1 | The two-thread limiter tests pass with the lock removed | medium | Reviewer's probe: 0 failures in 300 runs with the lock replaced by a no-op; a fake sleep never blocks, so the threads never overlap | patch: new test checks that the clock is read, and sleep called, only while the lock is held (an attempt to force a race failed, since the second thread still saw the first one's slot) |
| VG2 | `RequestsTransport` is never run by a normal test | medium | Only the online test builds it; swapping the two `except` clauses or dropping `.lower()` would pass CI | patch: monkeypatched `Session.get` tests for timeout/redirect arguments, header case, error mapping, one session per thread |
| VG3 | A row that is not an object, or a numeric `closedTime`, escapes as a raw `AttributeError` | medium | `_parse` caught only KeyError/TypeError/ValueError; `raw.get` and `text.strip` raise AttributeError | patch (group with BH1, EC9, EC10, EC11): `_parse` checks Mapping and catches AttributeError; `closedTime` must be text |
| VG4 | The planted-POST test checks its own predicate, not the real scan | low | The test rebuilt the check inline | patch (group with BH6, EC22): one `non_get_calls` helper used by both tests; adds `send`, `Request`, `PreparedRequest` |
| VG5 | `ALLOWED_THIRD_PARTY["data"]` not narrowed as the Code Map said | low | The table is per layer, not per module; `client_violations` enforces the same rule and has planted tests | reject: the rule holds; the fix would only edit the spec |
| BH1 | Raw exceptions escape the parsers | medium | Same as VG3 | patch (VG3 group) |
| BH2 | Gamma parser guesses missing `closed`, `feesEnabled`, outcome lists | medium | A Market with no outcomes passed as valid, and a missing `closed` read as open; these decide "Resolved" (AD-7). All 22 full Gamma Markets in the spike carry `closed` and both lists | patch: `closed` and both lists required (two or more outcomes, finite prices); `feesEnabled` optional, False when absent, must be true/false |
| BH3 | A 429's `Retry-After` pauses only the thread that got it | low | Only the one worker thread fetches (AD-5: a lookup that needs a fetch is a job), so no other thread sends meanwhile | reject: low, and the fix adds limiter state |
| BH4 | One `requests.Session` per thread, never closed | low | Same: only the worker thread uses the client (AD-5); one session in practice | reject: low; docstring now says so |
| BH5 | `RequestsTransport` untested | medium | Same as VG2 | patch (VG2 group) |
| BH6 | The non-GET guard is weaker than the spec says; its self-test proves nothing | low | Same as VG4; `check_url` never sees the method (the transport protocol only has `get`) | patch (VG4 group); spec wording left as approved |
| BH7 | Sprint status says in-progress while the spec says in-review | false | Step 5 of the workflow sets sprint status to `review` when the spec is done | reject |
| BH8 | Task line still says `limit=5`; README and test docstring disagree on request count | low | Implementation Notes record the `limit=5` change; README said "one request", docstring "three if busy" | patch: README now says "one request, or three if Polymarket is busy". Task line: reject (spec edit) |
| BH9 | Choices beyond AD-3 written only in code; AD-3 wording no longer matches ("other 5xx", "(a 429 or a 503)") | low | AD-3 read as if every other 5xx were retried; the code obeys Retry-After on any retried answer | patch: AD-3 wording fixed, memlog entry lists the build assumptions |
| BH10 | Only the last try decides whether a page "timed out" | low | "503, 503, timeout" restarted the walk; "timeout, timeout, 503" raised | patch (group with EC3): restart only when every try timed out; tested on three mixed sequences |
| BH11 | Nothing tells Story 2.5 to lower-case addresses | false | `services/lookup.py:130` already returns `text.lower()` after the FR-1 check | reject |
| BH12 | What v2 answers for an address with no history is not known | maybe-false | Would be medium for Story 2.5 if the answer is a 404 (it would raise PolymarketBadRequest) | defer: deferred-work.md, one live request settles it |
| BH13 | AD-3 variants half-tested: Gamma 403 failing 3 tries, long Retry-After on 429, `inf`; thread tests swallow errors | low | Each is a missing test case, not a code fault | patch: cases added; thread tests check `is_alive()` and collect worker errors |
| BH14 | No AI log or session log in the change set | false | Logs are written at the end of the session, after this review (CLAUDE.md working rules) | reject |
| BH15 | Sort parameters not checked | low | Story 2.2 is the only caller and passes fixed values; a typo shows as PolymarketBadRequest | reject: low, adds guards |
| EC1 | `ChunkedEncodingError` / `ContentDecodingError` escape raw | medium | They are `RequestException` subclasses, not `ConnectionError` | patch (with EC24): any other `RequestException` becomes a failed connection |
| EC2 | A timeout while reading the body arrives as `ConnectionError` and loses the mid-walk restart | medium | Checked: requests' `iter_content` raises `ConnectionError(ReadTimeoutError)` | patch: that case becomes `TransportTimeout` (matched by name, since `data/` may not import urllib3) |
| EC3 | Mixed failures: order decides restart or raise | low | Same as BH10 | patch (BH10 group) |
| EC4 | Restart pass failing on its first page throws away the first pass's rows | low | Matches the approved matrix ("failing on page 1 → PolymarketUnavailable"); needs sustained timeouts on two walks; the job stops as resumable | reject: low, adds a branch |
| EC5 | Restart pass failing mid-walk may return fewer rows than the first pass | low | Both are partial either way; rare (two failing walks) | reject: low, adds a branch |
| EC6 | `limit == 1` restarts with the same limit | low | No caller uses limit 1 | reject |
| EC7 | Missing pagination counts as complete; `has_more: "false"` read as true | low | A page that does not say whether more follows was taken as the last page | patch: pagination must be an object with a true/false `has_more`, else unreadable |
| EC8 | Endless `has_more` with new cursors never stops | low | Needs Polymarket to misbehave; Story 2.2 adds `ACTIVITY_ROW_CAP` and the window stop | reject |
| EC9 | A list element that is not an object raises AttributeError | medium | Same as VG3 | patch (VG3 group) |
| EC10 | Numeric `closedTime` raises AttributeError | medium | Same as VG3 | patch (VG3 group) |
| EC11 | `_parse` does not catch AttributeError | medium | Same as VG3 | patch (VG3 group) |
| EC12 | NaN or Infinity in JSON enter records | low | `json.loads` accepts them by default; the Sample JSON reader already refuses them | patch (with EC13): `parse_constant` refuses them; `_number` requires finite |
| EC13 | `outcomePrices` text "NaN" becomes a float NaN | low | `float("NaN")` parses | patch (EC12 group) |
| EC14 | `is_combo: "false"` drops a normal row | low | Truthiness check | patch: only `is True` drops |
| EC15 | Unknown activity type or side passes unchecked | low | The `type` parameter limits the types; 792,027 TRADE rows in the capture are all BUY or SELL | reject |
| EC16 | `markets("0xabc")` iterates characters | low | Programmer error; no caller does it | reject |
| EC17 | `limit` = ids asked could cut requested Markets if Gamma adds others | maybe-false | Would be low; Gamma filters on `condition_ids` | reject: low |
| EC18 | 408 / 425 not retried | low | Not seen from Polymarket; AD-3 lists the retried answers | reject |
| EC19 | Dot segments could pass the v1 guard | false | Every URL is built from module constants; no caller passes a path | reject |
| EC20 | Activity range not checked | low | Story 2.2 computes it | reject |
| EC21 | Fake transport does not record the method | low | The transport has only `get`, so every call is a GET | reject |
| EC22 | Non-GET guard is only an AST scan; planted test is a tautology | low | Same as VG4 | patch (VG4 group) |
| EC23 | Task line says `limit=5` | low | Same as BH8 | reject (spec edit) |
| EC24 | Other `RequestException` subclasses escape raw | medium | Same as EC1 | patch (EC1 group) |

After the patches: 650 tests pass, 1 online test deselected.

## Design Notes

The limiter keeps the next free time slot under its lock and sleeps inside the lock, so threads line up one after another: `wait = next_slot - now; next_slot = max(now, next_slot) + 1/rate`. The app is meant to build exactly one client per process (Story 2.5 does that in `open_sources`). That makes the limiter process-wide without a global variable that tests would have to reset.

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass (507 before), online test deselected.
- `uv run pytest -m online --force-enable-socket tests/online` -- expected: 1 passed (run once by hand, network on).
