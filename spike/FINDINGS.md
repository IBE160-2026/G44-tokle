# Data spike findings (PRD §9 Q1, Q2, Q3)

Status: Q2 and Q1 done 2026-10-21 (Q1 re-checked after Edvard's question on lost bets); Q3 done 2026-10-21. Draft for Edvard, not yet in the PRD memlog.
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
