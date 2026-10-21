# Addendum: LiquidOracle PRD

Material that belongs to architecture rather than the PRD itself. All of it except Storage is a proposal to confirm in `bmad-architecture`.

## Proposed technology `[ASSUMPTION]`

- **Language**: Python, with numpy for the Simulations. 10,000 Simulations × 1,000 Positions is one vectorised array operation, well within the 10-second target (SM-3).
- **Web page**: a small local web app (e.g. FastAPI or Flask with server-rendered pages, or Streamlit). Chosen in architecture; the course feedback asks for the simplest stack that does the job.
- **Storage** (decided, not an assumption): SQLite, through Python's built-in `sqlite3`, for cached Polymarket data, Domain labels, Scans and Watchlists. The Sample Dataset stays as plain files in the repository (FR-12) and is loaded into the same database in Offline Mode.
- **Sample Dataset size**: store only the price points near each buy (a window around the buy time, not the whole price history), so the repository stays small. The data spike (2026-10-21) found one-minute price points for resolved Markets, so a window of a few minutes around each buy is enough; the exact window is set in architecture (PRD §9 Q3).
- **Tests**: pytest. The Skill Test module is pure functions (Positions in, result out), tested without network.
- **Language model**: a small, cheap model (e.g. Claude Haiku) for Domain labels and Explanations, behind one interface that Mock LLM Mode also implements. To confirm in architecture; cost is small because each Market is classified once.

## Polymarket data (checked in the data spike, 2026-10-21)

Details, limits and evidence: `spike/FINDINGS.md`; the scripts and small samples are in `spike/`. All keyless and read-only.

- **Data API** (`data-api.polymarket.com`): closed positions (50 per request, entry price, size, realized PnL, resolution time), open positions (500 per request, includes unredeemed losing ones), activity and trades (a newer cursor-paged v2 exists), a leaderboard with no date setting, and trades per Market with an end-time filter.
- **Gamma API** (`gamma-api.polymarket.com`): Markets with resolution time, outcomes, token ids and the fee schedule; closed Markets must be asked for explicitly; 20 Markets per request.
- **CLOB API** (`clob.polymarket.com`): price history per outcome token, one-minute points, up to 14 days per request, from mid-2023.
- **Rate limits** (published): from 150 requests per 10 seconds upward, depending on the endpoint; requests are slowed, not refused.
- Keep all API access in one module: the activity endpoint has a newer version, and the documentation and the live behaviour differed on one limit.
- Not checked: how negative-risk (multi-outcome) Markets are represented; the architecture or first build story should look at it.

## Sources

- **Yale SOM study** (cited in SM-C1 and the brief: around 3% of Polymarket accounts show skill). Gomez-Cram, Guo, Kung and Jensen, *Prediction Market Accuracy: Crowd Wisdom or Informed Minority?*, SSRN working paper: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6617059>. Version used: 25 June 2026 (the first version is from April 2026). Read by Edvard on 2026-10-16; the figures below are as he reported them from that version.
  - **Share skilled:** around 3% of accounts in the abstract, 3.2% in the introduction. The "about 3%" in SM-C1 and the brief matches the abstract.
  - **Persistence:** 46% of the skilled accounts stay skilled out of sample, against 10% for mutual funds (the paper's comparison). Context for the Hold-up Test (SM-5); not a target, see SM-C2.
  - **Older figure, not used here:** 3.14% is from the April version, which The Block covered ([The Block](https://www.theblock.co/post/398902/skilled-polymarket-traders-are-a-3-minority-and-everyone-else-funds-their-gains-study)). The Yale SOM write-up ([Yale Insights](https://insights.som.yale.edu/insights/wisdom-of-the-few-prediction-markets-are-driven-by-small-number-of-skilled-traders)) says "just 3%".

## Why the Skill Test simulates outcomes instead of shuffling trades

Recorded in the brief's revision (2026-10-12): simulating each Outcome at its Entry Price has one formula and hand-checkable small cases, so the tests can prove the implementation right. Shuffling the buy/sell sequence was the original plan; the course feedback named the risk that a shuffle test can look right and still be wrong.
