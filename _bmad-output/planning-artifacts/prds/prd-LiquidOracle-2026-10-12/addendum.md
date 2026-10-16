# Addendum: LiquidOracle PRD

Material that belongs to architecture rather than the PRD itself. All of it except Storage is a proposal to confirm in `bmad-architecture`.

## Proposed technology `[ASSUMPTION]`

- **Language**: Python, with numpy for the Simulations. 10,000 Simulations × 1,000 Positions is one vectorised array operation, well within the 10-second target (SM-3).
- **Web page**: a small local web app (e.g. FastAPI or Flask with server-rendered pages, or Streamlit). Chosen in architecture; the course feedback asks for the simplest stack that does the job.
- **Storage** (decided, not an assumption): SQLite, through Python's built-in `sqlite3`, for cached Polymarket data, Domain labels, Scans and Watchlists. The Sample Dataset stays as plain files in the repository (FR-12) and is loaded into the same database in Offline Mode.
- **Sample Dataset size**: store only the price points near each buy (a window around the buy time, not the whole price history), so the repository stays small. The limit is decided after the data spike (PRD Open Question 3).
- **Tests**: pytest. The Skill Test module is pure functions (Positions in, result out), tested without network.
- **Language model**: a small, cheap model (e.g. Claude Haiku) for Domain labels and Explanations, behind one interface that Mock LLM Mode also implements. To confirm in architecture; cost is small because each Market is classified once.

## Polymarket data `[ASSUMPTION, to verify in a data spike]`

- Public, keyless APIs: the Data API (trades, positions and activity per user address) and the Gamma API (Market questions, outcomes, resolution).
- Questions for the spike: how closed and redeemed positions appear, whether average entry price is given or must be computed from trades, and how negative-risk (multi-outcome) markets are represented.

## Sources

- **Yale SOM study** (cited in SM-C1 and the brief: about 3% of Polymarket accounts show skill). Gomez-Cram, Guo, Kung and Jensen, *Prediction Market Accuracy: Crowd Wisdom or Informed Minority?*, SSRN working paper, April 2026. Title, authors and date as given by Edvard (2026-10-16). The data (Polymarket trades 2023 to 2025) and the figure (about 3.14% of accounts are "skilled winners") match the press coverage ([Yale Insights](https://insights.som.yale.edu/insights/wisdom-of-the-few-prediction-markets-are-driven-by-small-number-of-skilled-traders), [The Block](https://www.theblock.co/post/398902/skilled-polymarket-traders-are-a-3-minority-and-everyone-else-funds-their-gains-study)). **To do before the PRD is final:** add the SSRN link, and check the ~3% figure against the paper itself.

## Why the Skill Test simulates outcomes instead of shuffling trades

Recorded in the brief's revision (2026-10-12): simulating each Outcome at its Entry Price has one formula and hand-checkable small cases, so the tests can prove the implementation right. Shuffling the buy/sell sequence was the original plan; the course feedback named the risk that a shuffle test can look right and still be wrong.
