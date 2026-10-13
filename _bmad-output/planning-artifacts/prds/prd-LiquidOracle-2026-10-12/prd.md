---
title: "PRD: LiquidOracle"
status: draft
created: 2026-10-12
updated: 2026-10-12
---

# PRD: LiquidOracle

## 0. Document Purpose

This PRD turns the revised product brief (`_bmad-output/planning-artifacts/briefs/brief-LiquidOracle-2026-09-16/brief.md`, revised 2026-10-12 after the course feedback) into numbered, testable requirements. Architecture, epics and stories build on it. Terms in §3 Glossary are used exactly as defined. Features are grouped in §4 with globally numbered requirements (FR-1 …). Guesses made while drafting are tagged `[ASSUMPTION]` inline and listed in §10. Technology choices live in `addendum.md`, not here.

## 1. Vision

LiquidOracle tells a Polymarket trader whether a wallet is actually good or just lucky. The user pastes a wallet address and gets a **Verdict** (*Skilled (high confidence)*, *Likely skilled*, *No evidence of skill* or *Not enough data*), the number of bets it rests on, and the odds in plain words: "a trader with no edge would do this well about 1 time in 300."

Existing tools rank wallets by raw profit, which rewards one lucky bet as much as years of real edge. LiquidOracle instead asks whether the wallet beat the odds the market itself offered, more often than luck explains. It answers with a statistical test whose correctness is proven by automated tests against wallets with known answers.

v1 is built in three stages, each a working app: (1) a verdict for the whole wallet; (2) whether skill is worth following: a scan of the top wallets into a private watchlist, a test of whether their skill lasts, and a paper test of what a follower arriving late would have made; (3) verdicts per market domain, bot and market-maker flags, and a plain-language explanation.

## 2. Target User

### 2.1 Jobs To Be Done

- **Functional**: before copying a wallet's trades, find out whether its profit reflects skill or luck.
- **Functional**: find out whether following skilled wallets would actually have paid, given that a follower always arrives late.
- **Functional**: find out *where* a wallet's edge is (politics, sports, crypto, macro), not one blended number.
- **Emotional**: trust the answer. That means seeing how many bets it rests on, how strong the evidence is, and what the test can't see.
- **For the examiner** (the course's sensor): run the app from the README on their own machine and see that the method is tested and correct.

### 2.2 Non-Users (v1)

- Leaderboard browsers. There is no "top wallets" list; the user asks about one wallet at a time.
- Anyone wanting trade signals, copy-trading or financial advice.

### 2.3 Key User Journeys

- **UJ-1. Jonas checks a wallet before copying it.**
  Jonas trades on Polymarket and saw a wallet with $40k profit recommended on X. He opens LiquidOracle on his laptop and pastes the address. The app fetches the wallet's history and shows the Verdict card: *No evidence of skill*, 212 resolved bets, "a trader with no edge would do this well about 1 time in 4". The luck chart shows the wallet's result inside the normal range of luck, and the card notes that 70% of the profit came from one bet. Jonas decides not to copy it. **Edge case:** the address has no Polymarket history, and the app says so instead of showing an empty verdict.

- **UJ-2. Jonas looks up a new wallet with few bets.**
  The wallet has 12 resolved bets. The app shows *Not enough data*: "12 resolved bets; at least 30 are needed for a verdict", with no p-value and no chart.

- **UJ-3. The examiner runs the app offline.**
  The examiner clones the repository, follows the README, and starts the app in offline mode with the mock language model. With no network and no keys, they pick wallets from the sample dataset, including the synthetic ones, and see the verdicts the tests expect (the sharp trader is *Skilled (high confidence)*, the coin-flipper *No evidence of skill*). They run the test suite and it passes.

- **UJ-4. Jonas looks for wallets worth following** (stage 2).
  Jonas opens the Scan page and starts a scan of the top 200 wallets by profit. When it finishes, the Watchlist shows 7 wallets rated *Skilled (high confidence)*, with the note "about 2 of 200 would pass by luck alone". He sets the Cut-off Date to 1 June. The app re-rates every scanned wallet using only the bets that resolved before June, and all 7 still pass (the Before-Cut-off Passers). The other scanned wallets that were rated on the same bets and did not pass form the Comparison Group. The Hold-up Test shows that on the bets opened after June the Passers kept beating the odds (*Skilled (high confidence)* on 640 later bets) while the Comparison Group did not. The Copy Test shows that a follower copying 5 minutes late would still have made money on 5 of the 7, but on 2 of them the profit vanishes after a 1-minute delay: speed traders. He keeps the 5 forecasters on his list.

- **UJ-5. Jonas sees where the edge is** (stage 3).
  For a wallet with 400 resolved bets, the page adds a domain table: crypto *Skilled (high confidence)* on 180 bets, sports *No evidence of skill* on 150, politics *Not enough data* on 22.

## 3. Glossary

- **Wallet**: a Polymarket account, identified by its public address.
- **Market**: one Polymarket question (e.g. "Will X win the election?"). Has one or more outcomes and, once settled, a resolution.
- **Position**: all of one Wallet's buys of one outcome in one Market, combined. One Position = one bet, however many fills it was bought in.
- **Resolved Position**: a Position still held when its Market resolved. Only Resolved Positions enter the Skill Test.
- **Entry Price** (*p*): the average price paid per share of a Position, between 0 and 1. Read as the market's probability for that outcome.
- **Shares** (*s*): the number of shares held in a Position at resolution.
- **Outcome** (*o*): 1 if the Position's outcome happened, 0 if not.
- **Real PnL**: Σ *s* · (*o* − *p*) over a Wallet's Resolved Positions.
- **Exit PnL**: the PnL realised on shares a Wallet sold before resolution: Σ (shares sold) · (sell price − *p*). Shown, never part of the Skill Test.
- **Simulation**: one replay of a Wallet's Resolved Positions in which each Outcome is drawn at random, coming true with probability equal to its Entry Price.
- **Luck Distribution**: the Real PnL formula applied to 10,000 Simulations.
- **p-value**: (1 + number of Simulations with PnL ≥ Real PnL) / (1 + 10,000). The chance that a trader with no edge does at least this well.
- **Verdict**: one of *Skilled (high confidence)* (p < 0.01), *Likely skilled* (p < 0.05), *No evidence of skill*, or *Not enough data* (fewer than 30 Resolved Positions).
- **Skill Test**: the procedure that produces the Luck Distribution, p-value and Verdict for a set of Resolved Positions.
- **Seed**: the number that fixes the random draws, so a Skill Test can be repeated exactly.
- **Scan**: running the Skill Test on the top Wallets by profit (default 200) in one go.
- **Watchlist**: the Wallets from a Scan rated *Skilled (high confidence)*. Private: stored only on the machine running the app.
- **Expected Luck Passes**: the number of Wallets expected to pass a Scan by luck alone: number of Wallets tested × 0.01.
- **Cut-off Date**: the date that splits a Wallet's history into a *before* part (used to judge skill) and an *after* part (used to check it). The before part is the Positions that resolved before the date; the after part is the Positions opened on or after it. A Position opened before the date and resolved after it is in neither part.
- **Before-Cut-off Passers**: the Wallets from a Scan rated *Skilled (high confidence)* when the Skill Test uses only the before part. Unlike the Watchlist (whole history), nothing after the Cut-off Date decides who is in this group.
- **Hold-up Test**: the Skill Test run on the pooled after part, as Resolved Positions, of the Before-Cut-off Passers.
- **Minimum After-bets**: the fewest Resolved Positions in its after part that a Wallet needs to be counted in the Hold-up Test: 10. `[ASSUMPTION]` The same number applies to the Before-Cut-off Passers and the Comparison Group. Why 10: a round starting value, high enough that one lucky bet is not a Wallet's whole after part and low enough that Wallets that kept betting still count. It is not measured; revisit with real data (§9 Q6).
- **Comparison Group**: the other Wallets from the same Scan, picked the same way (same Cut-off Date, only the before part): those rated *Likely skilled* or *No evidence of skill*. Wallets with *Not enough data* in the before part are in neither group. The Comparison Group's after part is tested the same way as the Passers', with the same Minimum After-bets.
- **Copy Delay**: how long after a Wallet's buy a follower buys: 1, 5 or 30 minutes.
- **Follower PnL**: Σ *s* · (*o* − *p*<sub>delay</sub>), where *p*<sub>delay</sub> is the market price of the same outcome one Copy Delay after the Wallet bought.
- **Copy Test**: computing Follower PnL for each Copy Delay over the Resolved Positions in a Wallet's after part. Paper only.
- **Domain**: the category of a Market: politics, sports, crypto, macro or other.
- **Domain Verdict**: a Verdict from the Skill Test on only one Domain's Resolved Positions, with the Bonferroni correction (FR-20).
- **Sample Dataset**: Wallet histories and Market data saved in the repository, so the app can run without the network.
- **Synthetic Wallet**: a made-up Wallet with a known correct Verdict, generated by script with a fixed Seed.
- **Offline Mode**: the app reads only the Sample Dataset and makes no network calls.
- **Mock LLM Mode**: the language model is replaced by keyword rules and text templates, so no key is needed.
- **Flag**: a label marking a Wallet as a likely bot or market maker (stage 3).
- **Explanation**: a short plain-language text describing a Wallet's Verdict (stage 3).

## 4. Features

### 4.1 Wallet Lookup and Data (stage 1)

**Description:** The user enters a Wallet address. The app fetches the Wallet's trades and positions plus the Markets they belong to, stores them in the database, and builds the Wallet's Positions. Realizes UJ-1, UJ-2.

#### FR-1: Look up a Wallet
The user can enter a Wallet address on the start page and get its result page. Realizes UJ-1.
- An address that is not a valid address format shows an error message and fetches nothing.
- A valid address with no Polymarket history shows "No Polymarket history found for this address".

#### FR-2: Fetch and cache data
The system fetches a Wallet's trades, positions and the related Markets from Polymarket's public APIs and stores them in the database.
- A second lookup of the same Wallet within 24 hours uses stored data and makes no network call. `[ASSUMPTION: 24 hours is fresh enough]`
- If Polymarket does not answer, the page says so and offers the stored data if any exists.
- Requests are paced so the app never exceeds Polymarket's published rate limits.

#### FR-3: Build Positions
The system combines a Wallet's fills into Positions and marks which are Resolved Positions.
- Several buys of the same outcome in the same Market become one Position, with Entry Price = the share-weighted average price.
- A Position fully sold before resolution is not a Resolved Position. It is counted and shown, but left out of the Skill Test.
- A Position partly sold before resolution enters the Skill Test with the shares still held at resolution, at the original Entry Price. `[ASSUMPTION]` The shares sold count toward Exit PnL.
- `[NOTE FOR PM]` Which Positions reach resolution is the trader's choice and can depend on how the price moved after the buy. A trader who sells losers early and keeps the rest looks better in the Skill Test than they are. v1 accepts this and makes it visible (FR-11); handling it in the test is deferred to v2 (§6.2).

### 4.2 Skill Test (stage 1)

**Description:** The core of the product: the method in the brief's *The Skill Test* section, implemented as a separate module with no network or web code in it, so it can be tested on its own. Realizes UJ-1, UJ-3.

#### FR-4: Real PnL
The system computes Real PnL from a Wallet's Resolved Positions.
- For three Wallets in the Sample Dataset, Real PnL equals a hand calculation stored with the tests (to the cent).

#### FR-5: Luck Distribution and p-value
The system runs 10,000 Simulations and computes the p-value.
- Hand-check Synthetic Wallet (10 bets at 0.50, all won): p-value between 0.0003 and 0.002 (exact answer 1/1024 ≈ 0.001).
- Sharp-trader Synthetic Wallet (100 bets at 0.50, exactly 70 won): p-value < 0.01.
- Favourite-buyer Synthetic Wallet (100 bets at 0.90, exactly 90 won): p-value ≥ 0.05.
- Across 1,000 coin-flipper Synthetic Wallets (100 bets each, Entry Prices random between 0.10 and 0.90, Outcomes drawn at those prices): p < 0.05 for at most 7% and p < 0.01 for at most 2%.

#### FR-6: Verdict
The system turns the p-value into a Verdict using the thresholds in §3.
- A Wallet with 29 Resolved Positions gets *Not enough data* and no p-value; one with 30 gets a Verdict.

#### FR-7: Reproducibility
Each Skill Test runs with a Seed that is stored with the result.
- The same Wallet data with the same Seed gives the identical p-value and Verdict.

### 4.3 Verdict Page (stage 1)

**Description:** What the user sees after a lookup. Realizes UJ-1, UJ-2.

#### FR-8: Verdict card
The page shows the Verdict, the number of Resolved Positions, Real PnL, and the p-value in plain words ("about 1 time in N").
- A p-value of 0.0033 is shown as "about 1 time in 300".

#### FR-9: Luck chart
The page shows the Luck Distribution as a histogram with the Wallet's Real PnL marked on it.

#### FR-10: Too little data
For *Not enough data*, the page shows the number of Resolved Positions and how many more are needed, and shows no chart. Realizes UJ-2.

#### FR-11: Honesty notes
Every Verdict card shows:
- the share of Real PnL coming from the single largest Position;
- how many Positions were held to resolution out of all Positions (N of M), and the Exit PnL;
- a visible warning next to the Verdict when Exit PnL is below zero: "Positions this Wallet sold before resolution lost money in total. This Verdict covers only bets held to resolution.";
- a short fixed note on the test's limits (long shots tend to be overpriced; the Verdict covers only bets held to resolution, so early exits are not measured and can make a Wallet look better or worse than it is) and that this is not financial advice.

Checks:
- The stop-loss Synthetic Wallet (FR-13) shows the warning. A Wallet with Exit PnL ≥ 0, or with no early sales, shows none.

### 4.4 Offline Running and Test Data (stage 1)

**Description:** Lets the examiner run and check the app without our keys or a working Polymarket API. Realizes UJ-3.

#### FR-12: Sample Dataset
The repository contains stored data for about 10 real Wallets (a mix of Verdicts, including at least one *Not enough data*) and all Synthetic Wallets.

#### FR-13: Synthetic Wallets
A script generates the Synthetic Wallets in the brief's table from a fixed Seed, plus one the brief does not list: a stop-loss trader with no edge, who sells Positions whose price has fallen and holds the rest to resolution (added after the PRD validation, see FR-11). Running it twice gives identical files.

#### FR-14: Offline Mode
One setting makes the app use only the Sample Dataset.
- In Offline Mode, every Wallet in the Sample Dataset can be looked up with the network disconnected.
- Looking up a Wallet outside the Sample Dataset in Offline Mode shows "Not available offline".

#### FR-15: Mock LLM Mode
One setting replaces the language model with keyword rules (Domain) and templates (Explanation). It is on by default when no key is set.

### 4.5 Is Skill Worth Following? (stage 2)

**Description:** Answers the follower's question: which wallets are worth following, does their skill last, and does it survive being copied late. Everything here is computed on recorded data; nothing places orders. Realizes UJ-4.

#### FR-16: Scan and Watchlist
The user can start a Scan of the top Wallets by profit (default 200) and see the Watchlist, sorted by p-value, with the Expected Luck Passes shown next to it.
- A Scan of the Sample Dataset in Offline Mode puts the sharp-trader, steady-sharp and forecaster Synthetic Wallets on the Watchlist.
- A Scan of 200 Wallets shows "about 2 of 200 would pass by luck alone".
- The page shows progress during a Scan; an interrupted Scan resumes without re-fetching finished Wallets.
- The Watchlist is stored in the database with the Scan date and is never sent anywhere.

#### FR-17: Hold-up Test
The user can choose a Cut-off Date and see the Hold-up Test result for the Before-Cut-off Passers and for the Comparison Group: Resolved Positions in the after part, Real PnL, p-value and Verdict for each group.
- Both groups are picked from the same Scan by the same rule, using only the before part, and both are tested on the after part. No Position from after the Cut-off Date decides who is in either group.
- A Wallet that passes only when Positions from after the Cut-off Date are included is not in the Before-Cut-off Passers.
- Each Wallet is in at most one of the two groups.
- A Wallet counts in its group's result only if it has at least the Minimum After-bets Resolved Positions in the after part. The same minimum applies to both groups.
- Wallets that stop betting after the Cut-off Date (none, or fewer than the minimum) are dropped by that same rule in both groups, never kept in one and dropped in the other. Each group's result shows Wallets in the group, Wallets dropped for too few after bets, and Resolved Positions counted.
- If the share of Wallets dropped differs by more than 20 percentage points between the two groups, the page says so next to the results: "More Wallets were dropped in one group than in the other. Wallets that stop betting may be the ones that lost, so the group with more dropped Wallets may look better than it is." `[ASSUMPTION: 20 percentage points is "way more"]` A planted example (60% dropped in one group, 10% in the other) shows the message; equal shares show none.
- The steady-sharp Synthetic Wallets are rated *Skilled (high confidence)* on their after part.
- The lucky-streak Synthetic Wallets (coin-flippers that passed before the Cut-off Date) are rated *No evidence of skill* on their after part.
- A group with fewer than 30 Resolved Positions in the after part shows *Not enough data*.

#### FR-18: Copy Test
For each of the Before-Cut-off Passers, over the Positions in its after part, the system shows Follower PnL at each Copy Delay next to the Wallet's own Real PnL over the same positions, using Polymarket's recorded price history.
- The speed-trader Synthetic Wallet has Follower PnL ≤ 0 at a 5-minute Copy Delay.
- The forecaster Synthetic Wallet has Follower PnL > 0 at a 30-minute Copy Delay.
- A position with no recorded price at a Copy Delay is left out of that delay's sum, and the count of left-out positions is shown.
- The page states that Follower PnL ignores spread, fees and the follower's own price impact, so it is an upper bound.

### 4.6 Domains (stage 3)

**Description:** Splits the Skill Test by Domain so the user sees where the edge is. Realizes UJ-5.

#### FR-19: Classify Markets
The system assigns each Market a Domain using the language model (or Mock LLM Mode).
- Each Market is classified once; the label is stored and reused.
- Classification of a hand-labelled set of 50 Markets agrees with the hand labels on at least 80%. `[ASSUMPTION: 80% is a sensible bar]`

#### FR-20: Domain Verdicts
The system runs the Skill Test per Domain with at least 30 Resolved Positions, multiplying each p-value by the number of Domains tested (Bonferroni correction, capped at 1) before choosing the Verdict.
- A Synthetic Wallet that is sharp in one Domain and a coin-flipper in another gets *Skilled (high confidence)* in the first and *No evidence of skill* in the second.

#### FR-21: Domain table
The Verdict page shows one row per Domain: Domain, Resolved Positions, Domain Verdict.

### 4.7 Flags and Explanations (stage 3)

**Description:** Marks wallets whose profit comes from bots or market making rather than opinions, and explains the Verdict in plain language.

#### FR-22: Bot and market-maker Flag
The system Flags Wallets whose behaviour matches heuristics for market making or automated trading (e.g. buying both sides of the same Markets, flat inventory, very short holding times). The Flag is shown as "heuristic, may be wrong", never as a fact.
- The synthetic market-maker Wallet is Flagged; the coin-flipper and sharp-trader Synthetic Wallets are not.

#### FR-23: Explanation
The system generates a short Explanation of the Verdict (and Domain Verdicts) with the language model, or from a template in Mock LLM Mode.

#### FR-24: Explanation check
Before an Explanation is shown, code checks that it states the same Verdict and the same p-value (rounded) as the Skill Test, and makes no claim the test doesn't support (e.g. "will", "guaranteed"). An Explanation that fails is replaced by the template text.
- A planted Explanation with a wrong Verdict is replaced by the template.

## 5. Non-Goals

- No trading, automated copy-trading, alerts or anything that touches a wallet's funds or keys. The Copy Test is a paper calculation on recorded prices.
- No financial advice. Verdicts describe past performance only.
- No public leaderboard or social features. The Watchlist is private to the machine running the app.
- No detection of sybil clusters (many wallets run by one person) in v1.
- No markets other than Polymarket in v1.
- No user accounts or login.

## 6. MVP Scope

### 6.1 In Scope

- **Stage 1 (MVP, must be finished first):** FR-1 to FR-15. A complete, tested app that gives a whole-wallet Verdict and runs offline.
- **Stage 2:** FR-16 to FR-18 (Scan, Hold-up Test, Copy Test).
- **Stage 3:** FR-19 to FR-24 (Domains, Flags, Explanations). Trimmed first if time runs short.

Each stage ends with all its tests passing and the README updated, so the project is deliverable after any stage.

### 6.2 Out of Scope for v1

- Positions fully sold before resolution in the Skill Test (shown with their Exit PnL, not tested). Deferred to v2.
- Sybil-cluster detection. Deferred to v2: the feature most likely to blow the timeline.
- Kalshi, Manifold and other venues. Deferred to v2.

## 7. Success Metrics

**Primary**
- **SM-1**: All Skill Test correctness tests pass (hand-check, coin-flipper, sharp trader, favourite-buyer, thin wallet, reproducibility, hand-calculated Real PnL). Validates FR-4 to FR-7.
- **SM-2**: The examiner can run the app and the tests from the README with no network and no keys. Validates FR-12 to FR-15.

**Secondary**
- **SM-3**: A lookup of a Wallet with up to 1,000 Resolved Positions returns a Verdict within 10 seconds on an ordinary laptop (stored data). Validates FR-5.
- **SM-4**: The Hold-up Test and Copy Test synthetic checks pass (steady sharp vs lucky streak; forecaster vs speed trader). Validates FR-17, FR-18.
- **SM-5**: A Hold-up Test and a Copy Test have been run on real data, and the result is reported in the README and the reflection report, whichever way it comes out. Validates FR-16 to FR-18.
- **SM-6**: Stage 3 Domain labels agree with hand labels on at least 80% of 50 Markets. Validates FR-19.
- **SM-7**: Every shown Explanation passes the Explanation check. Validates FR-24.

**Counter-metrics (do not optimise)**
- **SM-C1**: The share of real Wallets rated *Skilled*. A test that calls more wallets skilled is not better; the Yale SOM study found only ~3% of accounts show skill. Counterbalances SM-1.
- **SM-C2**: The size of the Watchlist and how good the Hold-up and Copy results look. A real result showing that skill does not last, or cannot be copied, is a valid outcome, not a failure. Counterbalances SM-5.
- **SM-C3**: How confident or persuasive Explanations sound. They must never claim more than the test shows. Counterbalances SM-7.

## 8. Cross-Cutting Requirements

- **Runnable from the README**: install and start with a few documented commands on Windows, macOS and Linux.
- **Database**: cached Polymarket data, Domain labels, Scans and Watchlists are kept in a database (a local SQLite file is enough, nothing to install or host). Reason: course requirement (teacher, 17 Sept 2026).
- **Secrets**: the language-model key is read from `.env`, which is never committed; the repository contains `.env.example`.
- **Polite to Polymarket**: pacing and local storage so a lookup makes as few requests as possible.
- **Testable core**: the Skill Test module has no network, web or language-model code, and every FR with consequences has at least one automated test.
- **Wording**: the app never uses words like "guaranteed", "insider" or "will win" about a Wallet.

## 9. Open Questions

1. Which Polymarket endpoints give resolved and closed positions per Wallet with Entry Price, and how are fees, splits, merges and redemptions represented? Do sell fills give the Exit PnL (FR-11)? To be settled by a short data spike before architecture. (Owner: Edvard, before architecture.)
2. Which public endpoint lists the top Wallets by profit for a Scan, and how far back does it go? (Data spike, before architecture.)
3. Does Polymarket's price history have minute-level prices for resolved Markets, far enough back for the Copy Test? If only coarser data exists, the Copy Delays change. (Data spike, before architecture.)
4. Which language model for stage 3? `addendum.md` proposes one; cost is small because each Market is classified once.
5. Which 10 real Wallets go into the Sample Dataset? They should cover each Verdict.
6. Which Cut-off Date for the real-data Hold-up Test? It must leave enough bets in the after part and enough in the before part, and the Minimum After-bets should not drop most of the Passers.

## 10. Assumptions Index

- §4.1 FR-2: stored data counts as fresh for 24 hours.
- §4.1 FR-3: partly sold Positions enter the Skill Test with the shares held at resolution, at the original Entry Price.
- §4.6 FR-19: 80% agreement with hand labels is a sensible bar for Domain classification.
- §3, §4.5 FR-17: a Wallet needs at least 10 Resolved Positions in the after part to count in the Hold-up Test (Minimum After-bets).
- §4.5 FR-17: a difference of more than 20 percentage points in the share of Wallets dropped between the two groups is "way more" and gets a message.
- §4.5 FR-16: 200 Wallets is a sensible default Scan size (fetch time and Polymarket's rate limits not yet measured).
- §1, §6: the app runs locally on the user's or examiner's laptop as a web page; it is not hosted publicly.
