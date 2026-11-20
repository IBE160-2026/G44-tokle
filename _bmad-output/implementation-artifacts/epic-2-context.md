# Epic 2 Context: Check a real Wallet

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

The user pastes any Polymarket address and gets a Verdict from live data. A second lookup within 24 hours is instant and makes no network call, Polymarket outages are handled without a raw error, and the 10 real Sample Wallets work offline. The epic also proves the app's Real PnL against numbers that do not come from the app, and brings in linked-bet handling (negative-risk events, ladders, and the measured share of links not detected). It is part of stage 1, which must stand alone. Its target was 11 to 19 November 2026, so it starts late. If it runs late, ladder detection slips first; negative-risk coupling never slips.

## Stories

- Story 2.1: Polymarket client, read-only and polite
- Story 2.2: A Wallet's bets as one complete snapshot
- Story 2.3: Every exclusion and fee on real data
- Story 2.4: Linked bets on real data
- Story 2.5: Look up a live Wallet
- Story 2.6: Real Wallets in the Sample Dataset
- Story 2.7: Real PnL checked by hand

## Requirements & Constraints

- Read-only toward Polymarket: GET requests to public endpoints only, no keys, no orders, nothing that touches funds. Data API v2, Gamma and (later) price-history routes; never Data API v1, which retired on 2026-10-24.
- Polite: requests are paced at no more than `POLYMARKET_REQUESTS_PER_SECOND` (default 5; a value above 5 is refused at startup). A lookup of a Wallet already stored and fresh makes 0 network calls.
- Fresh means a complete stored snapshot under 24 hours old whose own range covers the requested window. Rows are never merged across snapshots.
- When Polymarket does not answer, the page says so and offers stored data only from a snapshot of the same view, labelled with its date. No page ever shows a raw exception.
- A valid address with no Polymarket history gets its own message and the hint to use the address from the Polymarket profile page.
- The window for a lookup is the latest 2,000 Positions in resolved Markets, by resolution time, capped before exclusions.
- Every Position the test cannot judge fairly is left out with one stored reason, counted, and reported; the same rules apply before and after the Cut-off Date.
- A Wallet with up to 1,000 Resolved Positions gets its Verdict within 10 seconds from stored data.
- Real results are recorded whatever they come out as; nothing is tuned to match an estimate.

## Technical Decisions

- **One client:** only `data/polymarket.py` talks to Polymarket. It returns `records` types; nothing above `data/` sees raw JSON. A cursor walk sends identical parameters on every page apart from the cursor (tested).
- **One limiter:** every request passes one process-wide limiter guarded by a lock, shared by web threads and the worker.
- **One retry policy:** timeouts, 429, 500, 502, 503, 504, failed connections, a Gamma or CloudFront 403, and an empty Gamma 404 on a list route are retried, at most 3 tries in all. A `Retry-After` header is waited out exactly instead of the client's own back-off, unless it is over 60 s, which gives up at once; each wait counts as a try. After the third try, `PolymarketUnavailable` (stops a job as resumable). Any other 4xx raises `PolymarketBadRequest` and is logged; a 400 "protocol contract address" is its own kind, used by the Scan. A page that times out mid-walk restarts the walk with a smaller `limit`; if that fails too, the read is partial.
- **Errors:** `data/` raises typed errors; `services/` turns them into the EXPERIENCE.md messages.
- **Resolved:** Gamma says closed, outcome prices exactly {0, 1}, and a `closedTime`. Resolution time is `closedTime`, never the Wallet's `last_event_at`.
- **One source per number:** positions lists (`/v2/positions`, OPEN and CLOSED) say which Positions exist and shares bought; activity rows (`/v2/activity`, types TRADE, REDEEM, SPLIT, MERGE, CONVERSION, `start` and `limit` always sent, `is_combo` rows dropped) give Entry Price, shares held, first buy, Own Fees, splits and merges; Gamma gives resolution, outcomes, fee schedule, start date and tags (20 Markets per request, `include_tag=true`). REDEEM rows are never a share source; v2 `entry_fees_usdc` is never used.
- **Own Fees:** cash paid − shares × price, checked against the Market's Gamma `feeSchedule` with a rounding tolerance; a failing fee counts as 0, is stored with its value, and its Position stays in the test.
- **One window function:** `positions_near(wallet, cutoff, side, limit)`. Activity for the window is read from the earliest Gamma start date to the latest `closedTime`, capped by `ACTIVITY_ROW_CAP`; on a cap, exactly the Positions resolving after the last row read are left out as "not fully read".
- **Snapshots:** each Wallet fetch writes a snapshot with a `fetch_id` that becomes visible in one final step; a per-Wallet lock allows one fetch of a Wallet at a time. New tables go in `schema.sql` with a raised `user_version`. Only `data/store.py` runs SQL.
- **Jobs:** a lookup that needs a fetch is a `job` row run by the one daemon worker thread (started only by `liquidoracle run`), lookups before Scan work; pages poll `GET /jobs/<id>/progress` returning `{status, phase, done, total, message}`.
- **Linked bets:** a negative-risk event shares one uniform draw split into disjoint intervals by price; a ladder shares one draw with nested intervals; the share of tested Positions with an uncoupled event-mate is stored for an honesty note above 20%.
- **Tests:** every test runs with sockets blocked; the client is tested against a fake transport and a fake clock. Online smoke tests live in `tests/online/` and never run in CI. Fixtures are cut from the real capture by a script.
- **Sample Dataset:** the 10 real Wallets are rebuilt from the raw capture zip (outside the repo, checked against its SHA-256) by one script, through the app's own rules, written with the one serializer; same zip gives identical output; committed set under 25 MB; never edited by hand.

## UX & Interaction Patterns

- Fetching state: heading "Checking 0x7c3a…d3f5", a fetching indicator and "Fetching trades from Polymarket…"; when done, the Verdict replaces the block and focus moves to the Verdict heading; without JavaScript a plain link reloads the page.
- Stored data is shown with "Data stored …" and the snapshot's date.
- Outage page: heading "Polymarket did not answer", with "Show stored data from …" only when a same-view snapshot exists, otherwise "Try again in a few minutes."
- No-history page: heading "No Polymarket history found", the profile-page hint, and a link back to *Check a wallet*.
- In Offline Mode the Sample Wallets list gains a *Real Wallets* group with shortened addresses.

## Cross-Story Dependencies

- 2.1 (client, limiter, retries) comes first; 2.2 builds the window and snapshot on it; 2.3 and 2.4 extend Epic 1's Position builder and Skill Test; 2.5 wires live lookups into Epic 1's pages; 2.6 needs 2.2 and 2.3's rules to build the real Sample Wallets; 2.7 checks Real PnL on three of them.
- 2.2's Gamma read must not run on the Sample Wallets until Edvard's Domain definitions and hand labels are committed (Epic 7 rule, 2026-11-05).
- Epic 4's Scan reuses the client, the "protocol contract address" error kind and the snapshot freezing.
