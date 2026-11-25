# Epic 4 Context: Scan for skilled Wallets

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

The user chooses a Cut-off Date, starts a Scan of the top Wallets by Real PnL made before that date, and sees the Watchlist sorted by p-value, with the Minimum Luck Passes and the population tested. The Scan runs in the background and can be left, interrupted and resumed. This is the first half of the stage 2 minimum: Epics 4 and 5 must pass their checks offline on the Sample Dataset. The target was 24 to 26 November 2026, and 1 December is a hard stop for code. If the epic runs late, the favicon progress ring and the tab-title counter slip first. The funnel's leak rules (4.2) and Resume (4.3) never slip.

## Stories

- Story 4.1: Before and after the Cut-off Date
- Story 4.2: The Scan funnel
- Story 4.3: The Scan as a resumable job
- Story 4.4: The Scans page
- Story 4.5: The Watchlist
- Story 4.6: Offline Scan with Synthetic Wallets

## Requirements & Constraints

- **Cut-off Date (Glossary):** splits a Wallet's history into a *before* part, used to judge skill (Positions whose Market resolved before the date), and an *after* part, used to check it (Positions opened on or after the date). A Position bought before the date and resolved after it is in neither part. The date is chosen when a Scan starts. It means 00:00 UTC on that date and is converted in one place. The Sample Dataset's default date is 1 July 2025.
- **No leak:** only Positions resolved before the cut-off decide which Wallets are scanned and how they rank. A test proves that changing outcomes after the cut-off cannot change the scanned set.
- **Windows of 2,000 `[ASSUMPTION]`:** the before part is the latest 2,000 Positions by resolution time; the after part is the first 2,000 by first-buy time. Big Wallets are kept, not dropped, and ranked and tested on their window.
- **Same exclusions on both sides:** each reason is counted and stored, and thresholds use the tested count.
- **Funnel:** the Market set is the Markets resolved in the 90 days before the cut-off, top 100 by volume, chosen without looking at outcomes and stored with the Scan. Candidates come from complete Market reads only. The shortlist is 3 × N by a cheap pre-filter. The shortlist is then fetched in full and ranked by Real PnL, and the top N are kept (default 200). `[ASSUMPTION: 90, 100, 3×, 200]`
- **Partial reads:** a partial Market read gives no candidates and is shown as "not used: partial". A Wallet that is refused or capped is kept and flagged "not fully read" everywhere it is counted; in the ranking it is ranked on what was read ($0 when nothing was) (Edvard, 2026-11-25, Story 4.2). A protocol contract address is dropped and counted, not flagged. Only Polymarket not answering stops a Scan, and the Scan can be resumed.
- **Scans:** a new Cut-off Date means a new Scan, and stored Wallet data is reused. The Watchlist is stored with its Scan date and Cut-off Date and is never sent anywhere. An empty Watchlist is a valid result (SM-C2).
- **Minimum Luck Passes** = Wallets tested × 0.01, shown as a floor ("probably more"), with one decimal under 2.
- **Offline check:** an offline Scan with the default date puts at least sharp trader, steady sharp, forecaster and speed trader on the Watchlist.
- **Read-only:** GET only, at most 5 requests per second, network-blocked tests. Each test names its FR or AD.

## Technical Decisions

- **One window function:** `positions_near(wallet, cutoff, side, limit)` lives in `data/window.py` and runs on any client's three raw reads (positions list, activity rows, Markets). The live client and `OfflineClient` therefore take the same path, with no offline branch.
  - **Already built (lookup, no cut-off):** `positions_near` reads OPEN in full, then CLOSED newest-first by `TIMESTAMP` with no `end`, using the `until` stop rule (a page's oldest `last_event_at` is older than the limit-th latest resolution collected). `_cap` keeps whole Markets only and never exceeds the limit. `capped` is set for the window line. Activity is read from the earliest Gamma start (or first buy) to the latest `closedTime`, under `ACTIVITY_ROW_CAP` = 150,000 (`activity_read_until` marks the Positions that are not fully read). CONVERSION rows are kept through `neg_risk_id`. `_MarketBook` gives resolved status and times from Gamma, and stored resolved Markets are never fetched again.
  - **What 4.1 adds:** today any `cutoff` or `side` raises `NotImplementedError`. The **before** side follows the same path, but only Positions whose Gamma `closedTime` is before the cut-off, in Markets whose Positions were all first entered before it, count, both for the window and for the stop rule's limit-th time. The **after** side takes Markets resolved on or after the cut-off whose Positions held at the cut-off were all first entered on or after it, ranked by the positions list's `first_entry_at` and taken whole up to 2,000; their activity is then read from the cut-off to the latest `closedTime` among them. A Market with one side bought before the cut-off and the other after is in neither part; a CLOSED Position fully closed before the cut-off does not make its Market mixed (Edvard, 2026-11-25, Story 4.1 and its review; spine AD-7).
- **Resolved / time:** a Market is resolved when Gamma says it is closed, its outcome prices are exactly {0, 1}, and it has a `closedTime`. The positions list's `last_event_at` is the Wallet's last event, not the resolution time. Times are UTC epoch `int` everywhere. Gamma text is converted in `data/` (`polymarket.parse_time`).
  - **Cut-off conversion:** no function exists yet. Today the Sample Dataset's date lives only as the string `real_sample.CUTOFF = "2025-07-01"`.
- **Why both after-part checks:** an activity read that starts at the cut-off cannot see older buys. In the capture, 165, 46 and 20 tokens on three capped Wallets looked new but had an earlier `first_entry_at`. Test fixtures are cut from the raw capture by `tests/fixtures/cut_from_capture.py` (the capture is git-ignored), not written by hand.
- **One builder:** `core/positions.build_positions` is already side-agnostic. It takes the window's fills, Markets, listed rows and not-fully-read rows, and applies the exclusion reasons in their fixed order. Both parts go through it unchanged, and pages print only from its record.
- **OfflineClient:** pages the lists at the live page size so `until` stops on the same page. Its `activity_rows` honours a real Wallet's `activity_from`/`activity_until`: a read starting earlier, or reaching that second, comes back cut short, so the normal "not fully read" rule applies.
- **Snapshots and results:** a fetch is a complete snapshot with a `fetch_id`, and there is a per-Wallet fetch lock. A Scan freezes the `fetch_id` per Wallet plus an as-of time, and resume and later phases read only those snapshots.
  - **Cache key:** today `store.serving_snapshot` keys only on `window_limit`. A lookup must never reuse a Scan's cut-off window or the reverse, so cut-off windows need their own key.
  - **Result keys:** results carry a scope (`scan_whole` = the Watchlist, both windows; `scan_before` = Passers), plus `scan_id`, cut-off, Seed and `fetch_id`, and pages read them by the full key.
- **Jobs:** a Scan is a `job` with phases (ranking, Skill Tests, then Hold-up and Copy Test in Epics 5–6). The progress JSON is `{status, phase, done, total, message}`. Between any two units of work (one Market-list page, one Wallet fetch, one price request), the worker runs a waiting lookup first. States are `queued/running/done/interrupted/stopped/failed`.
- **Schema:** Scan tables go into `schema.sql` with a raised `user_version`. On a version mismatch the cache tables are rebuilt, and Scans, Watchlists, results and the snapshots they refer to are migrated and kept. Only `data/store.py` runs SQL.
- **Market-anchored client function:** takes no sort argument and always sends `sort_by=TIMESTAMP&sort_direction=ASC` (enforced by a test). It reads `/v2/positions?condition=…` with CLOSED and OPEN, under `MARKET_ROW_CAP` = 15,000 rows per list `[ASSUMPTION]` (Edvard, 2026-11-25, Story 4.2).
- **Pre-filter:** Σ CLOSED `realized_pnl` + Σ OPEN (resolved value − cost), so unredeemed losers count.
- **Phrases:** the Minimum Luck Passes sentence and every other number phrase come from `core/phrases.py`.
- **Offline data:** the generator adds steady sharp, forecaster and speed trader with price paths. Watchlist Wallets also hold one small, fully sold Position in each of a fixed set of high-volume synthetic anchor Markets inside the default funnel window. `build-sample` is extended to write the real Wallets' before and after windows with 4.1's rules, rebuilt from the capture zip and never trimmed by hand.

## UX & Interaction Patterns

- **Top bar:** the link *Scan wallets* appears now.
- **Scans page:** URL `/scans`.
  - **New Scan form:** Cut-off Date and Number of Wallets (10 to 500, default 200), with the primary button "Start Scan".
  - **Errors:** "Choose a Cut-off Date.", "The Cut-off Date must be in the past.", "Enter a whole number from 10 to 500.". Each error is tied to its field, and focus goes to the first field in error.
  - **Warning:** when the date is less than 90 days ago: "Very few bets were resolved after this date, so the Hold-up Test and Copy Test may have too little to test." The user can still start.
  - **Time estimate:** a rough estimate sits under the number, computed from the planned request count at the set pace.
  - **Offline Mode:** the fields are read-only (1 July 2025, the whole Sample Dataset), with an info box.
  - **While a Scan runs:** an info box and an unavailable but focusable button.
  - **Empty state:** "No Scans yet. A Scan checks the top Wallets by profit made before a date you choose."
- **Scan list:**
  - **Columns:** run date, Cut-off Date, Wallets, Watchlist size and status text (Finished / Running with step / Interrupted / Stopped … / Failed / "Data rebuilt, cannot resume").
  - **Resume:** buttons named uniquely, "Resume Scan (Cut-off Date …)".
  - **Unfinished Scans:** no results shown.
- **Progress:** a real progress bar read as "84 of 200 Wallets checked" that names the step. Announcements come at most every 10% and at the end. The tab title "84/200 · Scan · LiquidOracle" and the favicon ring come from `progress.js`.
- **Watchlist:** URL `/scans/<id>/watchlist`.
  - **Header:** eyebrow "WALLET SCAN", "Scan of N Wallets", Cut-off Date and run date, the population line with "N of 100 Markets used · Seed 44", a summary card, and a disclosure listing Markets "not used: partial".
  - **Scan tabs:** links in a navigation region named "Scan", with the current page marked. This is not an ARIA tab list.
  - **Table:** "Wallets rated Skilled (high confidence)" with the columns Wallet (link "Open Verdict for Wallet …"), Verdict pill, Odds, Resolved bets and Real PnL. There is no rank column. A caption explains the p-value sort. The "Not fully read" tag carries its tooltip.
  - **Info box:** the Minimum Luck Passes sentence, above the table.
  - **Empty Watchlist:** "No Wallet in this Scan was rated *Skilled (high confidence)*."
- **Verdict from a Scan:** shows that Scan's `scan_whole` result, with "← Back to Watchlist (Cut-off Date …)".
- **Server-rendered:** every page is complete without JavaScript. Use the existing tokens, interaction states and the 900/640/400 px breakpoints. Wide tables scroll in a focusable, named area.

## Cross-Story Dependencies

- **4.1 first:** 4.2, 4.3, 4.6 and Epic 5's Hold-up Test all call `positions_near` with a side, and the exclusion counts on both sides come from the one builder.
- **4.2 → 4.3:** 4.2's funnel runs as 4.3's job phases. 4.3 owns the schema change, snapshot freezing and Resume, and the cut-off windows' snapshot key (see Technical Decisions) has to be settled by then.
- **4.4 and 4.5 read 4.3's records.** The honesty notes' "first 2,000" line and the Watchlist's two-window line were deferred from Story 3.3 to the first story that stores a `scan_whole` / `scan_before` result.
- **4.6 needs 4.1 to 4.5:** it extends the generator, the anchor Markets, `build-sample` and the round-trip test.
  - **Open item for 4.6:** for 0xd218e4 and 0x63d43b the capture holds trades only from May 2025, so their before part may come out entirely "not fully read". Count this before planning Epic 5's real-data checks.
- **Epic 5 builds on this epic:** it adds the Hold-up Test phase and tab and reads the Scan's frozen snapshots and `scan_before` result.
