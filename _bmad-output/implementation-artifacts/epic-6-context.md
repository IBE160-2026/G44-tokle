# Epic 6 Context: Could a late follower have profited? Copy Test

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

For each Before-Cut-off Passer of a finished Scan, show what a follower copying its buys 1, 5 or 30 minutes late would have made after fees (Follower PnL and Follower Return), and check the Passers as a group against random groups from the same Scan (the Random Group Check), on Polymarket's recorded one-minute prices. The epic closes stage 2 and ends with a Copy Test run on real data, reported whichever way it comes out. It is beyond the stage 2 minimum: if it is not reached before the code freeze on 1 December 2026, the README says so. The real-data run adds no code and may happen after the freeze. Paper only: the app never trades.

## Stories

- Story 6.1: Price history
- Story 6.2: Follower PnL
- Story 6.3: The Random Group Check
- Story 6.4: The Copy Test page
- Story 6.5: Copy windows in the Sample Dataset
- Story 6.6: Real data, reported either way

## Requirements & Constraints

- Copy Delays are 1, 5 and 30 minutes. Only the Main Copy Delay, 5 minutes, gives a Copy Verdict; 1 and 30 are extra information.
- Every buy fill of a Position is copied at its own time plus the delay. The follower's price is the recorded price at that time plus the Spread Allowance of half a cent, capped at 1. Follower Fee = s · rate · p · (1 − p) from the Market's fee schedule, 0 where none. Follower PnL = Σ (s · (o − p_delay) − Follower Fee), where s is the fill's share of the shares held at resolution. Follower Return = Follower PnL ÷ Σ (s · p_delay + Follower Fee).
- Copy Sample: all of a Wallet's Resolved after-part Positions if at most 100, else 100 drawn with the Seed by one rule for every Wallet; the page says "priced N of M".
- Copy Pool: every Scan Wallet with at least 10 Copy Sample Positions priced at 5 minutes, Passers included.
- Random Group Check: the Passers' average Follower Return (each Wallet equal) against 10,000 random groups of the same size from the Pool, no Wallet twice in a group. Copy p-value = (1 + groups scoring ≥ the Passers) / 10,001. *Beat random picks* below 0.05, else *No better than random picks*; *Not enough data* when no Passer is in the Pool or fewer than 1,000 different groups exist.
- Prices are never silently coarser than one minute. A buy with no one-minute price is left out of that delay and counted on the page. Fetched price history is kept for good.
- Checks that are never cut: the speed trader has Follower PnL ≤ 0 at 5 minutes, the forecaster > 0 at 30; a three-Position reference calculation made by a fresh helper from the plan alone, committed before its test; planted Scans for the Random Group Check, including the shared-Markets gate (at most 7% false passes, or no Copy Verdict is shown and the method goes back to the plan).
- The same data and Seed give identical results. At most 5 requests per second to Polymarket, through the one shared limiter. Tests run with sockets blocked.
- The committed Sample Dataset stays under 50 MB (41 MB before this epic) and is rebuilt by script from the raw capture, never by hand.
- If the old price route is gone when the real-data run is made, the Copy Test runs on the frozen 50-Wallet insurance pool, with its limits stated.

## Technical Decisions

- One client function returns price points for a token and window: the old CLOB route at one-minute fidelity while it answers with one-minute points, else the replacement route with a 60-second bucket sent explicitly. Only the Polymarket client module calls Polymarket.
- One pure rule, `price_at(points, t)`, in the core: the last point at or before t that is at most 2 minutes old; the same live and offline.
- Price history is stored as one short window per buy fill, from 2 minutes before to 32 minutes after, merged where they overlap. Fetching packs one token's windows into requests of at most 14 days and stores only the points inside the short windows. Stored windows never expire.
- Whether the old route still gives one-minute prices is decided by the daily route check's own request and rule (at least 40 points in its hour, median gap at most 90 seconds), sent before use and again after an hour or 200 price requests. A single answer that looks coarse or gone (median gap above 90 seconds; a 404 or 410) only triggers that check again; it never moves the client off the old route by itself.
- What is stored, and what Story 6.2 builds on: only definitive answers. An outage, an unreadable answer or a block (401, 403, 407, 451) stores nothing and stops the job with Resume. A request refused for itself is stored as a window with no points (route `refused`); an empty window is final and is never asked again. Each asked window is its own row with its route (`clob`, `v2`, `sample`, `refused`). `services/prices.plan` gives the requests a token still needs; `fetch` makes one.
- The Copy Test is a phase of the Scan job, after the Hold-up Test; one price request is one unit of work, and waiting lookups run between units. It reads only the snapshots the Scan froze and ignores anything resolved after the Scan's as-of time.
- **The Copy Test must run on a Scan that is already finished** (Edvard, 2026-11-28): the live Scan of Story 5.3 is not to be redone. A schema change keeps Scans, results and their snapshots, and a finished Scan without Copy Test rows must be able to get them.
- Only the store module runs SQL; the schema version rises with each table change. Copy maths lives in the core (`core/copytest`), orchestration in services; the core has no network, database or web code.
- Randomness: Wallets sorted by address and Positions by (condition, token) before any draw; each purpose has its own stream; the Seed is stored with every result and shown on the page.
- Number phrases have one home (`core/phrases`).

## UX & Interaction Patterns

- *Copy Test* is the third Scan tab, sharing the Scan header with Watchlist and Hold-up Test.
- A finished Scan that has no Copy Test shows a "Run Copy Test" button; the app never starts it by itself. Its place and states are settled when the page story is planned.
- Top: the Copy Verdict pill (no dots) and "random groups did as well in X% of draws" (one decimal under 10%), or "no random group did as well in 10,000 draws", never a percentage for that case. Under it: how many of the Passers' Markets are shared by two or more Passers, and how many Pool Wallets are not fully read. *Not enough data* gives its reason.
- Below: the per-Wallet table (Follower PnL and Follower Return at 1, 5, 30 minutes beside the Wallet's own Real PnL on the same Positions), captioned as not luck-checked, with "Extra information" tags on 1 and 30 minutes, positions left out per delay, and the upper-bound sentence. Follower Return is a percentage with one decimal and a real minus sign.
- A Wallet row opens its Verdict page, which shows "← Back to Copy Test (Cut-off Date …)".
- The Scan progress bar names the phase: "Copy Test: 1,200 of 18,000 prices". The Scans page's time estimate gains the price requests with this phase.
- Banned and avoided words about a Wallet still apply; the test's own names are allowed.

## Cross-Story Dependencies

- 6.1 gives 6.2 the price client, `price_at` and stored windows. 6.2 gives 6.3 the per-Wallet Follower Return. 6.4 shows what 6.2 and 6.3 store. 6.5 needs 6.2's Copy Sample rule to know which windows to keep. 6.6 needs all of them and the old route, or the insurance pool.
- The synthetic price paths and the after parts come from Epic 4; the Passers and the Comparison Group from Epic 5. The offline Scan has 3 synthetic Passers and 3 real Wallets with enough after bets, and the coin-flippers have none.
- The daily route-check workflow and the insurance pool were set up in October 2026.
