# Addendum: LiquidOracle PRD

Material that belongs to architecture rather than the PRD itself. It was a proposal until `bmad-architecture`, which settled it on 2026-10-21. The binding version is the architecture spine, `../../architecture/architecture-LiquidOracle-2026-10-21/ARCHITECTURE-SPINE.md` (rules AD-1 to AD-25, pinned versions); its memlog holds the reasons. This page is the short summary.

## Technology (settled in architecture, 2026-10-21)

- **Language**: Python 3.12 or newer (numpy 2.5 needs 3.12), with numpy for the Simulations. 10,000 Simulations × 1,000 Positions is one vectorised array operation, well within the 10-second target (SM-3).
- **Web page**: Flask with server-rendered Jinja2 pages, the luck chart as server-drawn SVG, and a few small plain JavaScript files that only enhance a page that works without them. No Node and no build step. FastAPI, Streamlit and a JavaScript single-page app were weighed and not chosen.
- **Code shape**: one program in layers, a pure core (Skill Test, Hold-up and Copy Test maths) with no network, database, web or model code, enforced by a test.
- **Storage**: SQLite through Python's built-in `sqlite3`, for cached Polymarket data, Domain labels, Scans, Watchlists and results. Online runs and Offline Mode use separate database files. The Sample Dataset stays as plain files in the repository (FR-12) and is loaded into the offline database by `load-sample`.
- **Long work**: one background worker thread inside the app, one thing at a time, lookups first; Scans can be left running and resumed.
- **Sample Dataset size**: only the price points near each buy fill are stored: one window from 2 minutes before to 32 minutes after each fill, merged where they overlap. Fetching packs a token's windows into requests of up to 14 days (measured on the typical Wallet: 1.06 requests per outcome, about 1.1 MB for its whole history). The 1,000 coin-flippers are regenerated, not committed. The committed Sample Dataset stays under 25 MB, with no Git LFS.
- **Install and tests**: uv with a committed lockfile; three README commands on every system. pytest with the whole suite run network-blocked (pytest-socket); GitHub Actions on Windows, macOS and Linux with Python 3.12 and 3.14.
- **Language model**: Claude Haiku 5.5 (`claude-haiku-5-5`) as a setting, with structured outputs for Domain labels, behind one interface that Mock LLM Mode also implements. FR-19's 80% check on hand labels decides; if Haiku misses it, a larger model is tried. Cost is small because each Market is classified once and the label is stored.
- **Font**: IBM Plex Serif (SIL Open Font License), bundled and served locally (DESIGN.md).

## Polymarket data (data spike 2026-10-21, re-checked on Data API v2 in architecture the same day)

Details, limits and evidence: `spike/FINDINGS.md`; the scripts and small samples are in `spike/` (`arch_probe*.py` for the v2 checks). All keyless and read-only.

- **Data API v2** (`data-api.polymarket.com/v2`): Data API v1 is retired on 2026-10-24, so the app uses v2 only. `/v2/positions` serves a Wallet's or a Market's positions by status (CLOSED, OPEN, which includes settled but unredeemed ones), 1,000 rows per page, cursor-paged, with time filters on the row's last event. `/v2/activity` serves a Wallet's trades, splits, merges, conversions and redemptions with time filters. The Scan's candidates come from Market-anchored position lists, not from trades: a Market's trades ignore the end-time filter on v2. The leaderboard has no date setting.
- **Gamma API** (`gamma-api.polymarket.com`): Markets with resolution time, outcomes, token ids and the fee schedule (rate and exponent); closed Markets must be asked for explicitly; 20 Markets per request. The resolution time always comes from here: v2's position timestamp is the Wallet's last event, up to days after resolution.
- **Price history**: the CLOB route (`clob.polymarket.com/prices-history`) gives one-minute points for resolved Markets from mid-2023, up to 14 days per request. On 2026-09-04 Polymarket named `/v2/prices-history` its replacement, which keeps one-minute points for at least 7 days only (5-minute for 60, 30-minute for 90; 3-hour and 12-hour for good). The old route still answers, with no end date announced, so the Sample Dataset's price history is fetched early and kept.
- **Rate limits** (published, per 10 seconds): 800 for all of Data API v2, 200 each for `/v2/positions`, `/v2/activity` and `/v2/prices-history`, 300 for Gamma `/markets`, 1,000 for CLOB `/prices-history`. Requests over the limit are slowed or queued; under heavy load v2 answers 429 with `Retry-After`. The app paces itself at 5 per second, as a setting.
- **Fees**: a Wallet's own fee is the cash paid minus shares × price on its activity rows; v2 gives the same fee as v1 on all 25 fee fills checked. The positions list's own fee field is not used (it disagreed in 3 of 7 checks).
- Keep all API access in one module (AD-2): v1 was retired at short notice, the price-history route is being replaced, and the documentation and the live behaviour differed on one limit.
- Negative-risk Markets: positions created by conversion are left out of the Skill Test and counted; the linked Markets of one negative-risk event share one random draw in the Simulations (AD-20).

## Sources

- **Yale SOM study** (cited in SM-C1 and the brief: around 3% of Polymarket accounts show skill). Gomez-Cram, Guo, Kung and Jensen, *Prediction Market Accuracy: Crowd Wisdom or Informed Minority?*, SSRN working paper: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6617059>. Version used: 25 June 2026 (the first version is from April 2026). Read by Edvard on 2026-10-16; the figures below are as he reported them from that version.
  - **Share skilled:** around 3% of accounts in the abstract, 3.2% in the introduction. The "about 3%" in SM-C1 and the brief matches the abstract.
  - **Persistence:** 46% of the skilled accounts stay skilled out of sample, against 10% for mutual funds (the paper's comparison). Context for the Hold-up Test (SM-5); not a target, see SM-C2.
  - **Older figure, not used here:** 3.14% is from the April version, which The Block covered ([The Block](https://www.theblock.co/post/398902/skilled-polymarket-traders-are-a-3-minority-and-everyone-else-funds-their-gains-study)). The Yale SOM write-up ([Yale Insights](https://insights.som.yale.edu/insights/wisdom-of-the-few-prediction-markets-are-driven-by-small-number-of-skilled-traders)) says "just 3%".

## Why the Skill Test simulates outcomes instead of shuffling trades

Recorded in the brief's revision (2026-10-12): simulating each Outcome at its Entry Price has one formula and hand-checkable small cases, so the tests can prove the implementation right. Shuffling the buy/sell sequence was the original plan; the course feedback named the risk that a shuffle test can look right and still be wrong.
