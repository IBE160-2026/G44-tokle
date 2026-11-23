# The 10 real Sample Wallets: what the app says about them

Story 2.6, 23 November 2026. The Verdicts below come from the committed files in `sample_data/real/`, built by `uv run liquidoracle build-sample` (see the README) and looked up in Offline Mode with the default Seed (44). They are recorded as they came out; nothing was tuned to match the pick's estimate (NFR-13).

The pick's estimates (from [`spike/FINDINGS.md`](../spike/FINDINGS.md), 23 October 2026) were made on a different slice of each Wallet: the latest 2,000 Positions resolved **before** the Cut-off Date (1 July 2025), held to resolution, with independent draws and no fees. The app's lookup window is the latest 2,000 Positions resolved by the time of the capture (23 October 2026), with every exclusion rule. So a different Verdict is not by itself a mistake.

## Verdicts

| Wallet | Pick's estimate (before the date) | App's Verdict | Tested bets | Left out | Real PnL | p-value | Uncoupled share | Verdict time |
|---|---|---|---|---|---|---|---|---|
| 0xcf0d7f | Likely skilled | **Likely skilled** | 139 (+27 Slivers) | 61 of 227: 46 split or merged, 15 sold | $822,007 | 0.048 | 2.9% | 0.08 s |
| 0x736483 | Likely skilled | **No evidence of skill** | 229 (+700 Slivers) | 535 of 1,464: 527 sold, 8 split or merged | −$633 | 1.00 | 5.2% | 0.28 s |
| 0xd218e4 | No evidence | **Not enough data** | 0 | 2,000 of 2,000: not fully read | $0 | none | 0% | 0.02 s |
| 0xd3a6e5 | No evidence | **No evidence of skill** | 641 (+139 Slivers) | 393 of 1,173: 287 split or merged, 95 sold, 6 share gap, 5 unclear | $117,604 (fees $462) | 0.19 | 16.4% | 0.23 s |
| 0x63d43b | No evidence | **Not enough data** | 0 | 2,000 of 2,000: not fully read | $0 | none | 0% | 0.02 s |
| 0x94884d | No evidence | **No evidence of skill** | 1,423 (+321 Slivers) | 256 of 2,000: sold | −$1,103 | 0.99 | 7.9% | 0.46 s |
| 0x729806 | No evidence | **Not enough data** | 0 | 1,483 of 1,483: not fully read | $0 | none | 0% | 0.02 s |
| 0x0f4b0a | No evidence | **No evidence of skill** | 210 (+43 Slivers) | 21 of 274: sold | −$189 (fees $0.53) | 1.00 | 16.2% | 0.05 s |
| 0x091596 | Not enough data | **Not enough data** | 14 (+24 Slivers) | 26 of 64: 25 split or merged (its Romania event, Story 2.4), 1 sold | −$49,616 (fees $1,132) | none | 14.3% | 0.00 s |
| 0x29306d | Not enough data | **Not enough data** | 18 (+3 Slivers) | 2 of 23: sold | $295 | none | 0% | 0.00 s |

- **Fees** (Story 2.8, 23 November 2026): Real PnL counts fees paid at an earlier whole-percent rate (FR-4). Before, they counted as 0: 0xd3a6e5 $118,065 with fees $0 (all 26 fees, $461.79, were paid at 4-5% in Markets Gamma now lists at 1%), 0x0f4b0a −$188 (fees $0.25), 0x091596 −$49,571 (fees $1,087). No Verdict or p-value changed: fees shift the real result and every replay equally (FR-5).
- **Uncoupled share** (AD-20, moved here from Story 2.4): the share of tested bets whose Gamma event holds another tested bet the app does not couple with it. All 10 are under the 20% honesty-note line.
- **Verdict time** (NFR-10): from stored data on this laptop (Windows, Python 3.14), measured by the test `test_nfr10_each_real_wallet_gets_its_verdict_within_10_seconds`. The slowest is 0.46 s against the 10 s requirement.

## Why three Wallets get *Not enough data*

The capture read at most 150,000 trade rows per Wallet in each direction from the Cut-off Date. 0xd218e4 and 0x63d43b hit that limit on both sides (it covers only May to August 2025 for them), and 0x729806 hit it before the date (it covers only from November 2024). Each window's trade read starts before the part the capture holds, so every bet is "not fully read" and left out (FR-12's one-way limitation, never patched by hand). A live lookup of 0x63d43b hits the same limit and gives the same answer (below).

0xd218e4's newest CLOSED positions were missing from the capture (it kept only the oldest 60,000). They were fetched on 23 November 2026, so this Wallet's data comes from two dates: positions closed by 23 November, trades and open positions as of 23 October (Edvard, 2026-11-23).

## Live lookups, including the Polymarket fetch

Measured on 23 November 2026 with `uv run liquidoracle run` (5 requests a second at most). The fetch time has no 10-second target; NFR-10 covers stored data (Edvard, 2026-11-21).

| Wallet | Fetch and Verdict | Verdict | Second lookup (stored) |
|---|---|---|---|
| 0xd3a6e5 (about 1,000 Markets) | 21.7 s | No evidence of skill, 649 bets, Real PnL $223,018 | 0.26 s, no fetch |
| 0x63d43b (the largest) | 298 s | Not enough data, 0 bets (trade read capped at 150,000 rows) | 0.03 s, no fetch |

The live 0xd3a6e5 result differs from the stored one (649 bets and $223,018 against 641 and $118,065, both under the strict fee check before Story 2.8) because live data is a month newer: Markets resolved since 23 October move into the latest 2,000.

## Checks closed by this story

- **negRisk outcomes** (Story 2.4's open check): all 7,376 negRisk Markets in the 10 Wallets' files are Yes/No, so no conversion is lost to a Market of another shape (`neg_risk_check` in `sample_data/real/dataset.json`).
- **Capped capture offline** (Story 2.2's open check): each file stores where the capture's trade reads stopped, and `OfflineClient` answers past that point as a cut-short read, so the normal "not fully read" rule applies offline.
- **A bug in the client found by real data:** Gamma leaves `outcomePrices` out for an open Market it has not priced yet (found among 0xd218e4's Markets). The client from Story 2.1 rejected the whole answer, so any live lookup touching such a Market failed as "Polymarket did not answer". Now an open Market without prices is read with none; a closed one without prices is still refused.
