# Data spike findings (PRD §9 Q1, Q2, Q3)

Status: Q2 and Q1 done 2026-10-21 (Q1 re-checked after Edvard's question on lost bets); Q3 done 2026-10-21. Draft for Edvard, not yet in the PRD memlog.
**Update 2026-10-21 (architecture):** Data API v1 is retired on 2026-10-24. The load-bearing findings were re-checked on v2; see *Re-check on Data API v2* at the end. Where it differs from the tables below, the v2 section wins.
Method: `spike/*.py`, read-only calls to public endpoints, no keys, 1.5 s between requests, about 650 requests, no rate limiting or unexpected errors (the 400s were deliberate cap tests). Raw dumps are in `spike/raw/` (git-ignored); small trimmed samples are in `spike/samples/`. Official docs were read through a page-to-text tool, so quoted limits are as that tool reported them. Where the live API differs from the docs, both are noted.

## Q2: a list of wallets for a Scan, as they were before the Cut-off Date

| Question | Answer | Evidence |
|---|---|---|
| Does the leaderboard take a date? | No. Parameters are `category`, `timePeriod` (DAY, WEEK, MONTH, ALL), `orderBy`, `limit` (max 50), `offset`, `user`, `userName`. | Official docs list no date parameter; four guessed date parameters were ignored. |
| How deep does it go? | Docs say offset max 1000; offset 5000 worked live. It ranks millions of wallets (`user=` returns a rank for any wallet, e.g. rank 704,637 with $582 volume). | `q2_probe2.py`, `q1_proxy.py` |
| Is there an older snapshot? | None found. The leaderboard is today's survivors only. | |
| Can we list wallets from markets that closed before the cut-off? | Yes. Gamma `/markets?closed=true&end_date_max=…&order=volumeNum` lists the markets. Data API `/trades?market=<conditionId>&end=<unix time>&limit=…` lists who traded, back to 2022. | `q2_probe4.py` to `q2_probe8.py` |
| Limit on that? | One market's trades are capped (offset max 10,000, limit up to 10,000). Moving `end` back walks further. | `q2_probe5.py`, `q2_probe6.py` |
| Does the sampling window change the pool? | Yes. 10 big markets, 1,000 trades each: last 1,000 before close gave 5,259 wallets, 331 in 2+ markets; spread over each market's whole life gave 4,920 wallets, 216 in 2+ markets. Only 1,079 wallets in both. | `q2_probe7.py`, `q2_probe8.py` |
| Pool composition | Mixed. A random draw from the 2+ market spread pool gave: rank 339 ($120M volume), rank 1321 ($152k profit), rank 704,637 ($582 volume), and negative-profit small wallets. | `q1_proxy.py`, `q1_probe1.py` |

Conclusion: listing candidates is cheap. Ranking them by profit before the cut-off costs per-wallet history requests (Q1 below). The leaderboard is not usable for a Scan.

## Q1: bets, entry price, fees, sells, proxy wallet

| Question | Answer | Evidence |
|---|---|---|
| Proxy wallet | One address everywhere: `/trades`, `/positions`, `/closed-positions`, `/activity`, Gamma `/public-profile` and the leaderboard all use the proxy and return it in `proxyWallet`. The profile does not expose the signing account, so the app cannot map one to the other. | `q1_proxy.py` (3 wallets) |
| Resolved bets with entry price | `/closed-positions`: one row per position with `avgPrice` (entry), `totalBought`, `realizedPnl`, `curPrice`, `timestamp`. Max 50 rows per page. `sortBy=TIMESTAMP&sortDirection=ASC` works, so a pre-cutoff scan can stop at the cut-off. | `q1_probe2.py`, `q1_probe3.py` |
| What does "closed" mean? | Not only resolved markets. Rows with `curPrice` strictly between 0 and 1 are fully exited positions in unresolved markets. Resolved ones have `curPrice` 0 or 1. For resolved markets `timestamp` equals the market's Gamma `closedTime` to within seconds (3 of 3 checked). | `q1_probe2.py` |
| Lost bets included? | Only partly. The typical wallet has 25 losses in 356 closed rows (93% wins), and that is real: it buys at an average of about 0.98 and has nothing left in `/positions`. But on the rank-339 pool wallet, 837 of its 1,196 positions are lost (price 0, redeemable) and unredeemed. They sit in `/positions`; an exact check by market found only 7 of 30 (23%) also in `/closed-positions`. Won-but-unredeemed positions (295) are mostly in both (13 of 15). So `/closed-positions` alone hides most losses for wallets that leave them unredeemed, and **FR-3 needs both sources**. | `q1_probe4.py` to `q1_probe7.py` |
| Splits and merges | Positions made by a split show `avgPrice` 0.5, `realizedPnl` 0 and no matching trade rows (5 rows in the typical wallet: two market pairs bought by SPLIT and sold by MERGE, plus one 10-token split). `/positions` has no resolution date, only the market `endDate`; the resolution time comes from Gamma `closedTime`, which can be fetched for 20 markets per request (repeat `condition_ids`; a comma list returns nothing). | `q1_probe8.py`, `q1_probe7.py` |
| `totalBought` vs trades | 347 of 356 match the sum of BUY sizes to 0.01. Of the other 9: 5 are explained by SPLITs (no BUY rows, or +10 from a 10-token SPLIT). 3 are not: `totalBought` is smaller than the BUY rows by 0.007%, 2.2% and 4.0%, with no split, merge or conversion in those markets. 1 traded token is in neither list (cause not found). Under 1% of rows, so entry prices look usable, but treat it as an unexplained error margin. | `q1_probe8.py` |
| Does `/activity` cut off history on a big wallet? | Offset max is 5000, so one query reaches 5,500 rows at most (limit 500). Past that the live API returns 400. Fix: repeat the query with `end=` set to the oldest timestamp seen. Tested on a wallet with 8,008 trades (17 requests): history reached back to 3 days after the profile was created, so nothing was lost. The row at the boundary second appears in both windows and must be taken from the later window only. | `q1_probe2.py`, `q1_analyse2.py` |
| Identical rows: separate fills? | Yes. 8 groups of identical-looking rows (28 rows, up to 11 in one group) exist. Keeping all rows matches `totalBought` for 347 positions; collapsing identical rows breaks 7 more. Never de-duplicate on values. | `q1_analyse2.py` |
| Sells and Exit PnL (FR-11) | Sells are `TRADE` rows with `side=SELL`, `price`, `size`. Exit price per sell is available. Closed-positions has only the entry average. | `q1_probe2.py` |
| Fees: which markets | Gamma markets carry `feesEnabled`, `feeType` and `feeSchedule {rate, exponent, takerOnly, rebateRate}`. Rare before late 2025, common by April 2026 (sports, politics, economics); crypto and culture too; some are `zero_fees`. | `q1_fees_markets.py`, `q1_fees_trades.py` |
| Fees: formula | `fee = shares × rate × p × (1 − p)`, exponent 1, taker only. Rates seen: 0.03, 0.04, 0.05. Matches the docs and trade rows to four decimals. | docs; 25 fee rows in one wallet |
| Fees in the data | In a fee-bearing taker trade, `usdcSize = size × price + fee` for a BUY and `− fee` for a SELL. First such row in the sample: 2026-06-09. `realizedPnl` is net of fees (7 of 9 fee positions reproduce to the cent; the 2 that don't are rows with the `totalBought` gap). | `q1_probe2.py` |
| Rate limits | Docs: 150 to 1,000 requests per 10 s depending on endpoint, throttled not rejected. We used 1 request per 1.5 s with no errors. Burst limits not tested. | docs page |
| API risk | Docs list `/v2/activity`; it works and pages by cursor only (no `offset`), with snake_case fields (`condition_id`, `token_id`, `usdc_size`, `proxy_wallet`). The old `/activity` still works today and could be retired, so keep API access in one layer. Whether the cursor has a depth cap is untested. | `q1_v2_check.py` |

### Cost per wallet (measured)

| Wallet | Closed positions | Trade rows | Requests to fetch all |
|---|---|---|---|
| Typical (rank 1321) | 356 | 8,008 | 8 + 17 |
| Rank 1 (Theo4) | 22 | more than 5,500 | 1 + 11 or more |
| Small (rank 704,637) | 13 | 28 | 1 + 1 |
| Rank 2 (swisstony) | more than 100,000 | far more | 2,000 or more |

Reading: `/closed-positions` plus `/positions` (500 rows per page, 3 pages for 1,196 positions) are cheap and cover the Skill Test and the profit ranking; the rank-339 wallet needed 3 pages of `/positions` against 60+ pages of closed rows (its closed list was not read to the end). The trade rows are what is expensive, and only the Copy Test and Exit PnL should need them. Market makers cannot be fetched in full and will need a cap per wallet.

## Q3: minute-level prices for resolved markets

Endpoint: CLOB `GET /prices-history?market=<token id>&startTs=&endTs=&fidelity=<minutes>`. The token id is the `asset` in trade rows or `clobTokenIds` in Gamma. Each point is only `{t, p}`.

| Question | Answer | Evidence |
|---|---|---|
| Minute-level prices for resolved markets? | Yes. `fidelity=1` returns one point per minute (120 points for a 2 h window) for resolved markets of all sizes, from 8 ages between August 2024 and September 2026, including a $10k-volume market. Points are one per minute even in thin markets, so they are filled-in prices, not proof of a trade that minute. | `q3_probe1.py`, `q3_probe2.py` |
| How far back? | Minute data exists from mid-2023 (markets closed in July 2023 had 240 points in 4 h). Markets closed in 2022 and January 2023 returned 0 points at every resolution tried (1, 60 and 720 minutes), so coarser data is not an alternative there. `interval=max` returned nothing for resolved markets. | `q3_probe3.py` |
| Window length | One request covers 14 days at 1-minute resolution (20,154 points). 30 days is rejected (400, "interval is too long"). | `q3_probe2.py` |
| Rate limit | Docs: 1,000 requests per 10 s for this endpoint. Not stressed. | docs |
| Buy vs sell gap, large markets | The history price sits at the midpoint of what buyers and sellers paid. Trump 2024: BUY-SELL gap 0.2 c median; Korean election (price 0.93): 1.0 c. Liverpool, Michigan State and a Trump-visit market (prices 0.47 to 0.76, $7.6M to $8.2M volume): 1.0 c median, 90th percentile 1.0 to 3.0 c. Buyers paid about 0.5 c above the history price. | `q3_probe4.py`, `q3_probe5.py` |
| The typical wallet's own fills | Near the history price: BUY median -0.05 c, SELL +0.10 c, 90th percentile of the gap 1.0 to 1.4 c (33 buys and 7 sells, median fill price 0.97, median size $312). These are near-certain markets where the spread is tiny. | `q3_probe5.py` |
| Thin markets | Not measurable. Of 9 markets tried, 5 gave a gap; 3 had too few trades to compare buys and sells (a $10k market, a $1k market and an NBA long shot priced near 0), and there is no historical order book. The gap in thin markets is unknown and likely larger. | `q3_probe4.py`, `q3_probe5.py` |
| Bad window | One market failed only because my request covered 37 days (rejected, see window length). Not a data gap. | |

Reading for the Copy Test (FR-18): the history price is a fair midpoint, not a price a copier can trade at. A copier pays roughly half the gap above it when buying and gets half below when selling: about 0.5 c in liquid mid-priced markets, up to 1.5 c at the 90th percentile, and unknown in thin ones. On entries near 0.98 this barely matters; near 0.5 it can be a large share of a small edge. A spread allowance on top of the Follower Fee would be a plan change (FR-18); that is Edvard's decision.

Request cost: one request returns up to 14 days of one token at 1-minute resolution, so requests are per token, not per bet, and can be cached and shared between wallets. The number of distinct tokens in a Copy Pool was not measured.

### Copy Pool and Scan cost estimate (`q3_copy_pool_estimate.py`, 305 requests)

Seven pool wallets ranked in the top 3,000 all-time (60 random draws gave only 7, not the 10 asked for). Closed positions read oldest first, capped at 2,000 rows per wallet.

| Result | Value |
|---|---|
| Wallets that hit the 2,000-row cap | 6 of 7 (the seventh had 206) |
| Outcomes shared between the 7 wallets | about 5% (12,206 summed, 11,573 distinct) |
| Outcomes after the example cut-off (2025-06-30) | 145, 551 and 1,292 for the three wallets whose later positions were reached; the other four read as 0 only because the cap stopped the reading, so all counts are floors |
| Price windows per outcome (typical wallet, real buy times) | 1.06 (336 of 352 outcomes need one 14-day window) |

Reading: a Copy Pool of a whole 200-wallet Scan is roughly 30,000 to more than 250,000 price requests (200 wallets times 145 to 1,292 outcomes), which is hours to days at one request per 1.5 s, against a published limit that would allow about 100 per second. Separately, the Scan itself costs up to 40 closed-position requests per wallet at the 2,000-position limit, about 8,000 for 200 wallets, and the limit leaves out most top wallets. Edvard decided on 2026-10-21 (PRD memlog): a capped Copy Sample of 100 after positions per wallet plus a faster pace, and big wallets kept and ranked on their latest 2,000 positions instead of dropped.

## Re-check on Data API v2 (architecture, 2026-10-21)

Why: Polymarket's migration guide says Data API v1 is retired on 2026-10-24, and everything above was measured on v1. Edvard: no point designing on v1 data. Method as above: read-only, no keys, 1.5 s between requests. Scripts `spike/arch_probe1.py` to `arch_probe8.py` (37 requests) and `spike/arch_cost_fills.py` (0 requests, saved data). Every filter was proven by a control: the same request with a made-up parameter, which v2 ignores and answers with the unfiltered list.

| Question | Answer on v2 | Evidence |
|---|---|---|
| Closed and open positions | One route, `/v2/positions`, with `status` (CLOSED, OPEN, REDEEMABLE, REDEEMABLE_LOST, MERGEABLE). OPEN is the superset and includes settled but unredeemed positions. Fields are snake_case (`token_id`, `condition_id`, `avg_price`, `total_size`, `realized_pnl`, `last_event_at`, `first_entry_at`, `entry_fees_usdc`, `negative_risk`). | OpenAPI `data-api.polymarket.com/v2/openapi.json`; `arch_probe1.py` |
| Page size | 1,000 rows per page, also on the cursor page (v1: 50 closed, 500 open). Cursor-only, no offset. The typical wallet's 356 closed positions come in one page. | `arch_probe3.py` (rank-339 wallet: 1,000 + 1,000) |
| Time filter on positions | `start`/`end` filter on `last_event_at` and really work: the control returned the identical list; `end=` gave a different list, every row within the bound, starting exactly where the unfiltered list crosses it; `start=` oldest-first gave exactly the unfiltered rows from the bound on (the first order check failed only on 22 tied timestamps). | `arch_probe1.py` |
| Is `last_event_at` the resolution time? | No. It is the wallet's last event (e.g. redemption): 0 to 85 hours after the Market's Gamma `closedTime` in 5 of 5 checks. Resolution time must come from Gamma. (v1's closed-list timestamp matched `closedTime`; v2's does not.) | `arch_probe1.py` |
| Walking back a Market's trades (the Scan method, Q2) | Does not work. `/v2/trades?condition=…` ignores `end=` (identical rows to the control); the docs say time filters apply to a user only. The cursor goes back about 9 hours per 1,000 rows on the $400M inauguration Market. A 2022 Market returns 0 trades even with `start=1`. | `arch_probe2.py`, `arch_probe3.py` |
| Fallback for the Scan's candidates | `/v2/positions?condition=…` with no user lists the Market's wallets. CLOSED: 1,000 rows, 995 wallets, 874 with a realized loss on a $71M 2025 Market; it reaches a September 2023 Market. OPEN on the same resolved Market: 54 holders, 44 of them holding the losing outcome (unredeemed losers). `limit=1000` timed out (503, retryable) on the $400M Market; `limit=100` worked. The first 100 CLOSED rows there had 0 losers: the default order is by profit (OpenAPI: REALIZED_PNL for CLOSED), so a capped read must sort by time. REDEEMABLE_LOST needs a user. | `arch_probe3.py`, `arch_probe4.py` |
| Splits and merges | `/v2/activity?type=SPLIT,MERGE` filters for real: 15 rows (10 MERGE, 5 SPLIT) in 4 Markets for the typical wallet; the control returned 1,000 rows, mostly TRADE. An omitted `start` floors to three years back, so `start` must be sent. | `arch_probe5.py` |
| Time filter on activity | `start`/`end` work on a wallet's activity: the control was identical; `end=` gave every unfiltered row up to the bound; `start=` oldest-first gave every row from the bound on, in order. | `arch_probe7.py` |
| Wallet's own fee | `entry_fees_usdc` is not reliable: it disagreed with the trade rows in 3 of 7 fee positions (0.0038 vs 0.0218, 0.0001 vs 16.08, 0 vs 2.70). `entry_cost_usdc` and `total_cost_usdc` hold only cents. `realized_pnl` cannot be rebuilt from a closed row alone (it mixes sell profit and payout; a closed row has shares bought, not shares held). | `arch_probe6.py` |
| Fee from activity rows | v2 activity TRADE rows equal the v1 trade rows saved the same day one to one: 1,549 rows since 2026-06-01, every key and count; all 25 fee fills give the same fee to the cent (total $1,392.30), with clean implied rates of 0.03 to 0.05. The cash-minus-shares×price method holds on v2. | `arch_probe8.py` (2 requests, run before v1's retirement) |
| CLOB price history | Unchanged: the spike's saved points are identical, and a 14-day window at 1-minute resolution is accepted (11,056 points because that window ran past the Market's resolution). But Polymarket's changelog (2026-09-04) names `/v2/prices-history` its replacement, which keeps 1-minute data for at least 7 days only (5-minute 60 days, 30-minute 90, 3-hour and 12-hour for good; explicit windows up to 15 days). The CLOB route still answers, with no end date announced. | `arch_probe3.py`; changelog and OpenAPI |
| Cost of copying every buy fill | Unchanged if packed: the typical wallet has 352 bought tokens and 5,087 buy fills (14.5 per token). One request per short window [fill − 2 min, fill + 32 min], merged where they overlap, would be 3.90 requests per token; packed into 14-day requests it is 1.06, the same as the per-outcome estimate above. Storing only the short windows takes 66,542 minute points, about 1.1 MB for the whole wallet. | `arch_cost_fills.py` |
| Rate limits (docs, checked 2026-10-21) | Per 10 s: 800 for all of v2; 200 each for `/v2/positions`, `/v2/activity`, `/v2/prices-history`; 300 for Gamma `/markets`; 1,000 for CLOB `/prices-history`. Over the limit, requests are slowed or queued; under heavy load v2 answers 429 or 503 with `Retry-After`. Gamma once answered 403 (CloudFront) during the probes and worked earlier the same day. | docs.polymarket.com rate-limits page; `arch_probe4.py` |

Reading: v2 is better for this app than v1 was: lost unredeemed bets have their own status, pages are 20 times larger, and a Market's own position list gives every wallet that held a position, losers included, instead of a sample of trades. Three things changed the plan: the Scan's candidate method (now Market-anchored position lists), the source of the resolution time (now always Gamma), and the price-history risk (fetch the Sample Dataset's windows early). All three are in the architecture spine (`_bmad-output/planning-artifacts/architecture/architecture-LiquidOracle-2026-10-21/`) and the PRD memlog.

## Sample Dataset pick and price capture (2026-10-21 to 2026-10-23)

Why: PRD §9 Q5 (which 10 real Wallets) and Q6 (default Cut-off Date), then the price-window capture while the old CLOB `/prices-history` route still answers (spine AD-24, AD-14). Decided by Edvard: Cut-off Date **1 July 2025**, the AI's suggested 10, plus spares as insurance (PRD memlog, 2026-10-23). Read-only, no keys, 4 requests per second. Scripts `sample_pick.py`, `sample_sold.py`, `sample_table.py`, `sample_capture.py`; raw output in `spike/raw/sample/` (git-ignored, about 1 GB). About 8,900 requests in all.

**How the Wallets were picked (no after-the-date results used).** Same funnel as a Scan (FR-16, AD-21): Markets resolved in the 90 days before the date, top 100 by volume (Gamma). Candidates from each Market's CLOSED and OPEN position lists; 77 of 100 Markets read in full (23 had more than 15,000 rows and were left out, as AD-9). 189,085 candidates. A seeded draw of 100 (top 15 and ranks 16-55 by profit on those Markets, active, losers, mid-size, random, heavy), 98 profiled on the before part: latest 2,000 Positions in Markets resolved before the date, outcomes read only for those Markets. Today's leaderboard was not used (it ranks on after-the-date results). Only after-the-date data used: activity counts (bets opened, any fee paid) to check FR-12 and FR-4. Addresses only, no names.

**Picked** (estimate on the before part, Positions held to resolution, rough: independent draws, no fees):

| Wallet | Estimated before-part Verdict | Covers |
|---|---|---|
| 0xcf0d7f69cf162918b33fc1ea7449583fa537132d | Likely skilled | Before-date Passer dropped by Minimum After-bets (7 after bets) |
| 0x73648309111de9f9d4e2a58a50f803fa7d30d44e | Likely skilled | Skill with tiny profit, favourite buyer; reaches the Hold-up Test |
| 0xd218e474776403a330142299f7796e8ba32eb5c9 | No evidence | Big profit, no evidence of skill; 2,000 cap; fees |
| 0xd3a6e523c440f94f9259398fbcf7b5cc5ccffd55 | No evidence | Profit from selling early (Exit PnL) |
| 0x63d43bbb87f85af03b8f2f9e2fad7b54334fa2f1 | No evidence | Big loser on near-certainties; 2,000 cap; fees |
| 0x94884db79666a1a34c46d03fb4f8e9cbcaf6b5a6 | No evidence | Longshot buyer with 776 unredeemed losers (OPEN list) |
| 0x7298060b1844a4c4ca0578146ab3f5e76aa1fcfc | No evidence | Many split and merge Positions (exclusions) |
| 0x0f4b0a6b7f82108924ac9c8320ed91028f504183 | No evidence | Hand calculation with fees |
| 0x0915962b4c6bc4505e7434a0de815a596a6667c3 | Not enough data | Hand calculation with large fees ($1,138); longshot buyer (swapped in for 0x8861f0) |
| 0x29306ddc4724e24a23bf1c8679aa034376ea9dcb | Not enough data | Hand calculation, small and clean (swapped in for 0xeb214d) |

Spares, captured as insurance only: 0xdc5378f70875715c333a3e4c4bf37183fe1f8a11, 0x8861f0bb5e0c19474ba73beeadc13ed8915beed6, 0xeb214d487c4f531ef7a3398631d56d3de5e08145. Swaps, both for the hand calculation (FR-4) and both logged in the PRD memlog: 0x29306d in for 0xeb214d (crypto already covered by 0x736483, 0x63d43b and 0x94884d, with 164, 287 and 87 crypto bets before the date), and 0x091596 in for 0x8861f0 (10,132 trade rows, too many to calculate by hand). Both used counts only (positions, trades, fees, splits), never an after-the-date result. No real Wallet was estimated *Skilled (high confidence)*; the Synthetic Wallets cover it.

**Capture result.** Per Wallet: positions (v2 CLOSED, OPEN), activity read in two parts (before the date newest-first, from the date oldest-first, each capped at 150,000 rows), and one-minute price windows [t − 2 min, t + 32 min] per buy fill for the after part (first 2,000 tokens in resolved Markets by first buy), packed into requests of at most 14 days.

| Wallet | After tokens | Buy fills | Price requests | Failed | Not 1-minute | Caps hit |
|---|---|---|---|---|---|---|
| 0xcf0d7f | 7 | 31 | 7 | 0 | 0 | none |
| 0x736483 | 13 | 19 | 13 | 0 | 0 | none |
| 0xd218e4 | 2,000 | 59,448 | 2,300 | 0 | 0 | activity both sides, positions |
| 0xd3a6e5 | 412 | 11,600 | 452 | 0 | 0 | none |
| 0x63d43b | 2,000 | 42,135 | 2,392 | 0 | 0 | activity both sides |
| 0x94884d | 16 | 129 | 16 | 0 | 0 | none |
| 0x729806 | 21 | 128 | 23 | 0 | 0 | activity before |
| 0x0f4b0a | 116 | 131 | 118 | 0 | 0 | none |
| 0x091596 | 22 | 54 | 24 | 0 | 0 | none |
| 0x29306d | 12 | 12 | 12 | 0 | 0 | none |
| spare 0xdc5378 | 27 | 29 | 27 | 0 | 0 | none |
| spare 0x8861f0 | 3 | 14 | 4 | 0 | 0 | none |
| spare 0xeb214d | 56 | 126 | 58 | 0 | 0 | none |

Every token got one-minute points; no request failed.

**Found on the way (for the epics):**
- A Market's position list includes Polymarket's own contracts; `/v2/positions?user=` refuses them (400, "protocol contract address"). The Scan must drop them.
- Gamma was down for about 2 minutes (2026-10-21, 15:35-15:37 UTC): every route answered an empty 404 from CloudFront. The client should retry this like a 503.
- A p-value bug in the AI's own estimate: Python's `sum()` and `+=` round floats differently, so a simulation equal to the real result never counted as a tie (p 0.74 came out as 0.0002). The Skill Test must compare in whole cents.
- Selling early is common: in the median profiled Wallet about half the before-part Positions were not held to resolution, and treating them as held gave PnL off by millions. The PRD's rules (fully sold left out, partly sold tested on shares held, Exit PnL shown) are needed.
- **First buy after the date needs the positions list too.** On the three Wallets whose before-read hit the cap, 165, 46 and 20 tokens looked first-bought after the date but the positions list's `first_entry_at` is before it: their earlier buys were beyond the cap. AD-7 reads the after part from the date forward, so the app has the same blind spot unless it checks `first_entry_at`. The capture now checks it and refills the window; spine AD-7 now requires both checks (Edvard, 2026-10-23).
- **One-way door.** On the two biggest Wallets, 150,000 activity rows after the date reached only 12 and 20 August 2025, so 808 and 418 kept tokens may miss later fills. AD-11's cap rule leaves those Positions out. Completing them is possible with `/v2/activity?condition=` (tested with a control) but costs thousands of requests, and Edvard declined it (2026-10-23). If the cap rule ever changes, these two Wallets cannot be fixed: the old one-minute price route will be gone by then. Stated as a limitation in PRD FR-12.
- `/v2/activity` filters by Market with `condition` (`market` is refused with 400), and `end` with `sort_direction=DESC` works (tested with a control).
- Size: the raw capture is about 1 GB, 0xd218e4 and 0x63d43b about 370 MB each. The committed Sample Dataset (25 MB, FR-12) must be a trimmed subset, for example each Wallet's Copy Sample; it is rebuilt by one script from the raw capture, never trimmed by hand (spine AD-14, Edvard, 2026-10-23); which subset is a decision for the Sample Dataset story.
- Backup: the raw capture is zipped (176 MB, 271 files, SHA-256 file alongside) outside the repository in `../G44-tokle-data/`. A second copy on another disk is pending.
