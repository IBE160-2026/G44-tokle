---
title: 'Story 4.2: The Scan funnel'
type: 'feature'
created: '2026-11-25'
status: 'done'
baseline_commit: '025c10c97e870b055d427c26be560cf1c5170b72'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A Scan needs its list of Wallets, picked only from what happened before the Cut-off Date (FR-16, FR-17). Nothing in the app can list a date window's Markets by volume, read a Market's holders, or rank Wallets yet.

**Approach:** The AD-21 funnel as plain functions that Story 4.3 later runs as job phases: choose the Market set, read each Market's holders, shortlist 3 × N by the pre-filter, read each shortlisted Wallet's before part (4.1) and keep the top N by Real PnL. The result is one in-memory record, `ScanFunnel`; storing it, the job and Resume are 4.3's.

## Boundaries & Constraints

**Always:**
- **Market set:** Gamma closed Markets in volume order whose `closed_time` is in [cutoff − 90 days, cutoff) and that are `resolved` (AD-7), top 100 `[ASSUMPTION]`. Volume decides the order; outcomes are never looked at.
- **Holders read:** one client function, `market_holders(condition_id, status)`. It takes no sort argument and always sends `sort_by=TIMESTAMP&sort_direction=ASC` (AD-9). A Market is used only when both its CLOSED and OPEN reads are complete and under `MARKET_ROW_CAP`. **Decision (Edvard, 2026-11-25, AI rec):** `MARKET_ROW_CAP` = 15,000 rows per list `[ASSUMPTION]`, the Sample Dataset pick's limit (77 of 100 Markets used on 1 July 2025; worst case about 10 minutes). Rejected: 30,000 (about 20 minutes) and 5,000 (too many skipped). Otherwise it is "not used: partial" and gives no candidates. A read whose every try timed out counts as partial; any other `PolymarketUnavailable` stops the funnel.
- **Pre-filter:** per Wallet, over the used Markets only: Σ CLOSED `realized_pnl` + Σ OPEN `size` × (the token's Gamma outcome price − `avg_price`), so unredeemed losers count. The shortlist is the top 3 × N, ties broken by address.
- **Ranking:** `positions_near(side="before", limit=WINDOW_LIMIT)`, then `build_positions`, then Real PnL from one public function that `skill_test` also uses (AD-10). The top N are kept, ties broken by address.
- **Wallet outcomes:**
  - `ProtocolContractAddress`: dropped and counted.
  - Other `PolymarketBadRequest`: kept and flagged `not_fully_read`. **Decision (Edvard, 2026-11-25, AI rec):** it is ranked on what was read ($0 when nothing was), the same rule as every Wallet, and counted in the record. Rejected: always keeping it in the top N.
  - Any Position not fully read: flagged.
  - `NoPolymarketHistory`: Real PnL $0, not flagged.
  - `PolymarketUnavailable`: propagates.
- **`ScanFunnel` holds:** cutoff, N, the Market set with each Market's volume and used/partial state, the candidate count, the contracts dropped, the shortlist with estimates, and every ranked Wallet (Real PnL, flag), with the top N marked.
- Tests are network-blocked and name their FR/AD. The leak test changes the outcome of every Market resolved on or after the cut-off, in both the shortlisted Wallets' data and the Gamma answers, and the funnel's result must not change.

**Never:**
- No store, schema, job, page or `fetch_wallet` change (Story 4.3 and 4.4).
- No OfflineClient support (Story 4.6 adds it with the anchor Markets).
- No `/v2/activity?condition=` or `/v2/trades` reads.
- No Polymarket leaderboard.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Window edge | closed at cutoff − 90 d / at cutoff − 1 s / at cutoff | in / in / out | N/A |
| Unclear Market | closed, prices not {0, 1} | not in the set, next by volume taken | N/A |
| Fewer Markets | Gamma's pages run out below 100 | the set holds what was found | N/A |
| Capped holders | CLOSED read reaches `MARKET_ROW_CAP` | Market partial, 0 candidates, even though rows were read | N/A |
| Unredeemed loser | OPEN row on the losing token | estimate −size × `avg_price` | N/A |
| Few candidates | fewer than 3 × N, or fewer than N ranked | all of them are kept | N/A |
| Contract | `ProtocolContractAddress` on the user read | dropped, counted, not ranked | N/A |
| Outage | `PolymarketUnavailable` (not all timeouts) | — | propagates; Story 4.3 makes it `stopped` |

</frozen-after-approval>

## Code Map

- `src/liquidoracle/data/polymarket.py`:
  - `positions_list` (:180) and `_walk` (:273) are the patterns. `_walk` takes `row_cap`, restarts once at half the limit on a timeout, and returns `Read(complete=False)`.
  - `_PageTimedOut` (:157), `_bad_request` (:447), `check_url` (:412) and `raw_markets` (:236). The `GAMMA_BATCH` pattern is for the `/markets` list.
  - Add `market_holders(condition_id, status, *, row_cap=MARKET_ROW_CAP, limit=PAGE_LIMIT) -> Read[MarketHolder]`. Raw fields: `proxy_wallet`, `token_id`, `realized_pnl`, `current_size`, `avg_price` (field names as used by `spike/sample_pick.py:112`).
  - Add `funnel_markets(closed_from, closed_until, count) -> tuple[FunnelMarket, ...]`: Gamma `/markets` with `closed=true`, `order=volumeNum`, `ascending=false`, offset pages of 100, and `end_date_min` = from − 120 d / `end_date_max` = until + 400 d. It filters by `closed_time`, stops at `count` or after 50 pages. This is the spike's proven query, `spike/sample_pick.py:94`.
- `src/liquidoracle/data/client.py:16`: `WalletClient` stays as it is. Add a `FunnelClient` Protocol (the two new methods plus `WalletClient`'s) that only `PolymarketClient` implements for now.
- `src/liquidoracle/records.py`: add `MarketHolder`, `FunnelMarket(market, volume)`, `RankedWallet` and `ScanFunnel` near `Window` (:321).
- `src/liquidoracle/core/skilltest.py:242`: make `_real_pnl` public (e.g. `real_pnl(position_set)`) and use it in `skill_test`, so ranking and Verdict share one source.
- `src/liquidoracle/core/funnel.py` (new, pure): the pre-filter and the 3 × N shortlist.
- `src/liquidoracle/services/scan.py` (new):
  - `choose_markets`, `read_candidates`, `shortlist`, `rank_wallet` and `run_funnel(client, cutoff: date, size)`.
  - Each unit of work is its own call, so 4.3 can run waiting lookups in between (AD-5).
  - The ranking path follows `services/fetch.py:60` (`result_of`).
  - Constants: `MARKET_DAYS = 90`, `MARKET_COUNT = 100`, `SHORTLIST_FACTOR = 3`, `DEFAULT_SIZE = 200`, each `[ASSUMPTION]`. `MARKET_ROW_CAP` lives in `data/polymarket.py`.
- `src/liquidoracle/data/window.py:50`: `positions_near`, `cutoff_at`, `WINDOW_LIMIT`. Unchanged.
- `tests/fake_polymarket.py`: `FakeTransport`, `Call.query`, `page`, `ok`. `FakePolymarket` asserts `user == wallet`; extend it with a `condition` route and a Gamma list route for the funnel tests.
- `tests/test_polymarket.py:175-198`: the identical-params-per-page tests are the pattern for the sort rule.
- `tests/fixtures/capture/*.json`: the real Wallets serve as shortlisted Wallets in the ranking and leak tests.
- `tests/online/test_polymarket_live.py`: never in CI.

## Tasks & Acceptance

**Execution:** (the plan task is done by the orchestrator and committed first; leave every other change uncommitted, and run git only read-only)
- [x] `ARCHITECTURE-SPINE.md` AD-9 + `.memlog.md` -- `MARKET_ROW_CAP` = 15,000 per list; a refused Wallet is ranked on what was read; one memlog entry per decision via `_bmad/scripts/memlog.py append` -- plan before code.
- [x] `records.py`, `core/skilltest.py` -- the new records; public Real PnL used by `skill_test` -- AD-10.
- [x] `data/polymarket.py`, `data/client.py` -- `market_holders`, `funnel_markets`, `MARKET_ROW_CAP`, `FunnelClient` -- AD-9, AD-21, AD-2.
- [x] `core/funnel.py`, `services/scan.py` -- the funnel steps and `run_funnel` -- FR-16, AD-21, AD-9.
- [x] `tests/fake_polymarket.py`, `tests/test_polymarket.py`, `tests/test_funnel.py`, `tests/test_scan.py` -- every matrix row:
  - The sort rule, by request and by signature.
  - Partial on cap and on all-timeouts.
  - The leak test.
  - Contract and bad-request outcomes.
  - Ranking on 2+ real fixture Wallets.
  - `skill_test`'s Real PnL unchanged.
- [x] `tests/online/test_polymarket_live.py` -- `funnel_markets` for 1 July 2025 returns 100 resolved Markets in the window, volumes descending; one small Market's holders read complete. Run it once and compare its 100 ids with the spike's frozen `funnel_markets_20250701.json`; record the result in Implementation Notes.

**Acceptance Criteria:**
- Given any Market-anchored request the client builds, when it is sent, then it carries `sort_by=TIMESTAMP&sort_direction=ASC`, and a test fails otherwise.
- Given a funnel run, when outcomes of Markets resolved on or after the cut-off change, then the Market set, shortlist and top N are identical.
- Given the whole suite, when it runs network-blocked, then every existing test passes.

## Design Notes

- **Why no OfflineClient yet:** the Sample Dataset has no Market volumes and no holder rows. Story 4.6 builds both with the anchor Markets, and the funnel then runs unchanged through `FunnelClient` (AD-14, no offline branch).
- **Known limit of the Market query:** Gamma filters by the scheduled end date, not by `closedTime`. A Market whose end date was more than 120 days before its resolution, or more than 400 days after the cut-off, is missed. The spike found the full 100 on 1 July 2025 this way.
- **Cost:** at most 100 Markets × 2 lists × cap/1,000 pages, plus about 3 × N Wallet reads.

## Verification

**Commands:**
- `uv run pytest tests/test_polymarket.py tests/test_funnel.py tests/test_scan.py tests/test_skilltest.py -v` -- expected: all pass.
- `uv run pytest` -- expected: whole suite green.
- `uv run pytest -m online --force-enable-socket tests/online -k funnel` -- run once by hand; expected: pass.

## Implementation Notes

**Live check (2026-11-25).** `funnel_markets` for 1 July 2025 returned 100 resolved Markets. It matches the spike's frozen `funnel_markets_20250701.json` exactly: the same 100 condition ids in the same order, with the same volumes. The online test (`-k funnel`) passed in about 6 s. Both lists of the small Market (`0xf86d87db…`, 18 rows in the spike) read complete. The strict parsers held on live data: every Gamma list row parsed, and every holder row had a `condition_id` and number values for `realized_pnl`, `current_size` and `avg_price`.

**Choices made while building (none changes the frozen intent):**
- **One more record, `Candidate(wallet, estimate)`.** It holds the shortlist with its estimates; the spec named four records.
- **`SHORTLIST_FACTOR` lives in `services/scan.py`,** as the spec lists it, so `core/funnel.shortlist(estimate_of, count)` takes the count (3 × N).
- **The cap is decided in the client.** `market_holders` returns a read that reaches `row_cap` as partial, even when nothing was left to read ("under `MARKET_ROW_CAP`"). It also turns a read whose every try timed out into `Read((), False)`. Every other `PolymarketUnavailable` is raised.
- **A Market list refused with a 4xx** (`PolymarketBadRequest`) leaves the Market "not used: partial" instead of stopping the Scan. This follows the "otherwise partial" rule; the matrix has no row for it.
- **The OPEN list is skipped** when the CLOSED list is already partial, to save requests.
- **A holder row of another Market is an unreadable answer.** This guards against Polymarket dropping the `condition` filter. `proxy_wallet` is lower-cased and checked as an address.
- **`funnel_markets` keeps a Market once** when offset pages repeat it, and orders the set by volume (ties by condition id).
- **`ScanFunnel.cutoff` is epoch seconds (00:00 UTC),** like `Window.cutoff`. `partial` holds condition ids and `contracts` holds addresses.
- **A refused Wallet always ranks on $0.** `positions_near` is all-or-nothing, so nothing is read when Polymarket refuses.
- **One unit of work is one Market (both lists) or one Wallet,** not one list page. Story 4.3 can run waiting lookups between them. Interleaving page by page would need a paging API on the client.

**Test checks.** The leak test has a planted twin: ranking on a lookup window (no cut-off) changes with flipped outcomes, so the leak test would catch it. Hand mutations were each caught by the new tests: dropping the AD-9 sort, not treating the cap as partial, using partial Markets, not flagging a refused Wallet, and raising on all-timeouts.

## Review Triage Log

Pass 1 (2026-11-25): blind hunter (B), edge-case hunter (E), verification gap (V). Checked against the code.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| B2 = E1 | `funnel_markets` cuts to `count` before sorting by volume | low | The loop stops only after a whole page, so `found` can hold more than `count`; the cut keeps Gamma's arrival order, and ties at the boundary follow it, not condition id | patch |
| V1 | A not-fully-read Wallet's Real PnL is not pinned | medium (pre-verified) | The test only asserts it differs from the full value; ranking it on $0 or dropping `not_fully_read=` from `build_positions` leaves the suite green | patch (test) |
| V-o1 = E6 | A refusal after the first request gives $0, not "what was read" | low | `positions_near` is all-or-nothing, so any 400 discards what was read; no 400 after a first good answer has been seen (refusals come on the `user=` request); a partial return would change `positions_near` | patch (docstring states it); behaviour kept |
| V-o2 = B5 = E2 | An OPEN holder row whose token is not one of the Market's outcomes ends the Scan with `ValueError` | maybe-false | Whether Polymarket ever sends such a row is unknown: the spike kept no token ids; if it does, a Scan fails instead of marking the Market partial (would be medium) | defer |
| B1 | The spec is not in the diff | false | Left out on purpose (it is the edge-case layer's claims file); it is committed with the code | reject |
| B3 | `funnel_markets` lets `True`/`2.5` through as `count` | low | Only caller passes the constant `MARKET_COUNT`; fix adds a type guard | reject |
| B4 | One extra Gamma request after a short page | low | One request per Scan; stopping on a short page assumes Gamma never sends short middle pages | reject |
| B6 | A refused Wallet can take a top-N seat on a $0 tie | low | Needs fewer than N Wallets above $0 among 3 × N; Edvard's rule is "the same rule as every Wallet" | reject |
| B7 | Not-fully-read counts cover every ranked Wallet, not the top N | low | No consumer yet; 4.4 can count `funnel.top`; no named harm | reject |
| B8 | No stored reason per partial Market | false | AD-9 asks only for "not used: partial" and "N of 100 Markets used" | reject |
| B9 | The 10-minute estimate leaves out the Wallet phase | false | The memlog entry states it for the Market reads under the row cap; the Wallet phase is AD-5's Scan cost, 4.4's time estimate | reject |
| B10 | `rank_wallet` throws away the fetched window | false | Snapshots and their reuse are Story 4.3's (frozen Never: no store or `fetch_wallet` change) | reject |
| B11 | `run_funnel` repeats `_check_size` | low | Cosmetic; it refuses before any request, which `top_n`'s check cannot | reject |
| B12 | An offline Scan would crash with `AttributeError` | false | Nothing calls `run_funnel` with `OfflineClient`; Story 4.6 adds it | reject |
| B13 | CLOSED refused/timed-out, OPEN capped, missing Market untested | low | CLOSED capped (and OPEN skipped) is tested; the others share the same `complete` check | reject |
| B14 | `>= 19` and the online test's exact 100 are loose or brittle | low | The online test is run by hand on frozen 2025 data; it passed | reject |
| B15 | The leak test only flips outcomes | low | Story 4.1's leak test removes every post-cut-off fill and listed row and pins the before window, which is all the ranking reads | reject |
| E3 | A Gamma `conditionId` not lower-case hex ends the Scan | low | Not seen in Gamma data; fix adds a guard | reject |
| E4 | A token on both a Market's lists is counted twice in the estimate | maybe-false | The window keeps such a token once (seen on user lists); whether `realized_pnl` then double-counts is unknown; the pre-filter is approximate by design (AD-21), so at most low | reject |
| E5 | `estimates` raises a bare `KeyError` for a read with no Market | low | Unreachable: `shortlist` builds both maps from the same set | reject |
