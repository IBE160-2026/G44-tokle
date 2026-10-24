---
title: "PRD: LiquidOracle"
status: final
created: 2026-10-12
updated: 2026-10-24
---

# PRD: LiquidOracle

## 0. Document Purpose

This PRD turns the revised product brief (`_bmad-output/planning-artifacts/briefs/brief-LiquidOracle-2026-09-16/brief.md`, revision 7 of 2026-10-16; the first revision, 2026-10-12, answered the course feedback) into numbered, testable requirements. Architecture, epics and stories build on it. Terms in §3 Glossary are used exactly as defined. Features are grouped in §4 with globally numbered requirements (FR-1 …). Guesses made while drafting are tagged `[ASSUMPTION]` inline and listed in §10. Technology choices live in `addendum.md`, not here.

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
  The examiner clones the repository, follows the README, and starts the app in Offline Mode. With no network and no keys, they pick wallets from the sample dataset, including the synthetic ones, and see the verdicts the tests expect (the sharp trader is *Skilled (high confidence)*, the coin-flipper *No evidence of skill*). They run the test suite and it passes.

- **UJ-4. Jonas looks for wallets worth following** (stage 2).
  Jonas opens the Scan page, sets the Cut-off Date to 1 June and starts a scan of the top 200 wallets by profit made before June. When it finishes, the Watchlist shows 7 wallets rated *Skilled (high confidence)*, with the note "at least about 2 of 200 would pass by luck alone, probably more, because these Wallets were picked for high profit". The app has also re-rated every scanned wallet using only the bets that resolved before June, and all 7 still pass (the Before-Cut-off Passers). The other scanned wallets that were rated on the same bets and did not pass form the Comparison Group. The Hold-up Test shows that on the bets opened after June the Passers kept beating the odds (*Skilled (high confidence)* on 640 later bets) while the Comparison Group did not. The Copy Test shows that a follower copying the Passers 5 minutes late, after fees, would have earned an average return that only 0.4% of 10,000 random groups of 7 Wallets from the same Scan matched (*Beat random picks*). Per Wallet, 5 of the 7 still make money at 5 minutes; on the other 2 the profit vanishes already at a 1-minute delay: speed traders. The page notes that these single-Wallet numbers are not luck-checked. He keeps the 5 forecasters on his list.

- **UJ-5. Jonas sees where the edge is** (stage 3).
  For a wallet with 352 resolved bets, the page adds a domain table: crypto *Skilled (high confidence)* on 180 bets, sports *No evidence of skill* on 150, politics *Not enough data* on 22. Under the Verdict card sits a 45-word Explanation. Another wallet shows "Likely market maker (heuristic, may be wrong)" beside its Verdict, which stays unchanged.

## 3. Glossary

- **Wallet**: a Polymarket account, identified by its public address.
- **Market**: one Polymarket question (e.g. "Will X win the election?"). Has one or more outcomes and, once settled, a resolution.
- **Position**: all of one Wallet's buys of one outcome in one Market, combined. One Position = one bet, however many fills it was bought in.
- **Resolved Position**: a Position still held when its Market resolved. Only Resolved Positions enter the Skill Test.
- **Entry Price** (*p*): the average price paid per share of a Position, between 0 and 1. Read as the market's probability for that outcome.
- **Shares** (*s*): the number of shares held in a Position at resolution.
- **Outcome** (*o*): 1 if the Position's outcome happened, 0 if not.
- **Own Fees**: the taker fees a Wallet paid on the buys of a Position, as Polymarket recorded them; 0 in Markets that charge no fee and on fills where the Wallet was the maker. Read from the Wallet's activity rows (cash paid − shares × price) in Markets that charge fees, and checked against that Market's own fee schedule. A fee that fails the check is not counted (it counts as 0) and is shown on the Verdict card (FR-11). (Architecture, 2026-10-21.)
- **Real PnL**: Σ *s* · (*o* − *p*) over a Wallet's Resolved Positions, minus the Own Fees on those Positions. The profit the Wallet actually kept.
- **Exit PnL**: the PnL realised on shares a Wallet sold before resolution: Σ (shares sold) · (sell price − *p*). Shown, never part of the Skill Test.
- **Simulation**: one replay of a Wallet's Resolved Positions in which each Outcome is drawn at random, coming true with probability equal to its Entry Price. Bets that depend on the same result share one random draw: all Positions in one Market (also across Wallets, in the Hold-up Test), the Markets of one negative-risk event (only one can win), and a detectable ladder (same underlying, same resolution date). Each Position still comes true with probability equal to its Entry Price; what changes is that linked bets win and lose together, as they do in reality, instead of counting as separate evidence. The Own Fees are charged in every Simulation exactly as in the real result, so they lower both by the same amount and the p-value does not change.
- **Luck Distribution**: the Real PnL formula applied to 10,000 Simulations.
- **p-value**: (1 + number of Simulations with PnL ≥ Real PnL) / (1 + 10,000). The chance that a trader with no edge does at least this well.
- **Verdict**: one of *Skilled (high confidence)* (p < 0.01), *Likely skilled* (p < 0.05), *No evidence of skill*, or *Not enough data* (fewer than 30 Resolved Positions).
- **Skill Test**: the procedure that produces the Luck Distribution, p-value and Verdict for a set of Resolved Positions.
- **Seed**: the number that fixes the random draws, so a Skill Test can be repeated exactly.
- **Scan**: running the Skill Test on the top Wallets by profit (default 200) in one go. Profit counts only from Positions resolved before the Cut-off Date, so the ranking cannot lean on the results the Hold-up Test is meant to check (§9 Q2). The Wallets come from the app's own candidate list: those that traded in Markets resolved before the Cut-off Date. Polymarket's leaderboard cannot be used for this (§9 Q2). Profit means Real PnL, after the Wallet's own fees. A Wallet with more than 2,000 such Positions is ranked, and Skill Tested, on its latest 2,000 only (FR-16). How the candidates are found and narrowed to the Scan size is in FR-16.
- **Watchlist**: the Wallets from a Scan rated *Skilled (high confidence)* on everything the Scan fetched for them: the before part and the after part together ("whole history" below means this, not the Wallet's whole life on Polymarket). Private: stored only on the machine running the app. Every result names the set of Positions it was computed on, so a Watchlist row and the Verdict page it opens show the same result.
- **Minimum Luck Passes**: the fewest Wallets expected to pass a Scan by luck alone: number of Wallets tested × 0.01. A floor, not an estimate: the Scan picks Wallets for high profit, so more than this pass by luck.
- **Cut-off Date**: the date that splits a Wallet's history into a *before* part (used to judge skill) and an *after* part (used to check it). The before part is the Positions that resolved before the date; the after part is the Positions opened on or after it. A Position opened before the date and resolved after it is in neither part. It is chosen when a Scan starts.
- **Before-Cut-off Passers**: the Wallets from a Scan rated *Skilled (high confidence)* when the Skill Test uses only the before part. Unlike the Watchlist (whole history), nothing after the Cut-off Date decides who is in this group.
- **Hold-up Test**: the Skill Test run on the pooled after part, as Resolved Positions, of the Before-Cut-off Passers.
- **Minimum After-bets**: the fewest Resolved Positions in its after part that a Wallet needs to be counted in the Hold-up Test: 10. `[ASSUMPTION: 10]` The same number applies to the Before-Cut-off Passers and the Comparison Group. Why 10: a round starting value, high enough that one lucky bet is not a Wallet's whole after part and low enough that Wallets that kept betting still count. It is not measured; revisit with real data (§9 Q6).
- **Comparison Group**: the other Wallets from the same Scan, picked the same way (same Cut-off Date, only the before part): those rated *Likely skilled* or *No evidence of skill*. Wallets with *Not enough data* in the before part are in neither group. The Comparison Group's after part is tested the same way as the Passers', with the same Minimum After-bets.
- **Copy Delay**: how long after a Wallet's buy a follower buys: 1, 5 or 30 minutes.
- **Main Copy Delay**: 5 minutes, fixed before any data is looked at. Only the Random Group Check at this delay decides the Copy Test's result; the 1- and 30-minute numbers are extra information. Reason: testing three delays would give luck three chances to pass.
- **Follower Fee**: the fee Polymarket would charge the follower for buying *s* shares at *p*<sub>delay</sub> in that Market; 0 in Markets that charge no fee. A taker fee is *s* · rate · *p* · (1 − *p*), with the rate and exponent read from the Market's fee schedule (§9 Q1).
- **Spread Allowance**: half a cent (0.005) added to the price a follower pays, because the recorded price history is the midpoint between what buyers and sellers paid, not a price a follower can trade at. `[ASSUMPTION: 0.5 cent; measured gap in large liquid Markets: median 1 cent, 90th percentile 3 cents; thin Markets not measured]`
- **Follower PnL**: Σ (*s* · (*o* − *p*<sub>delay</sub>) − Follower Fee), summed over each buy fill of the Position, where *s* is that fill's share of the shares held at resolution and *p*<sub>delay</sub> is the market price of the same outcome one Copy Delay after that fill, plus the Spread Allowance (capped at 1). A Position bought in 12 fills is copied 12 times, each at its own time. (Architecture, 2026-10-21.)
- **Follower Return**: a Wallet's Follower PnL at one Copy Delay ÷ the money the follower spent on the same Positions, Σ (*s* · *p*<sub>delay</sub> + Follower Fee). Profit per dollar, so Wallets of very different sizes can be compared.
- **Copy Sample**: for each Wallet, the Resolved Positions in its after part that the Copy Test prices: all of them if there are at most 100, otherwise 100 drawn at random with the Seed, by the same rule for every Wallet. `[ASSUMPTION: 100 Positions per Wallet]` Reason: pricing every after Position of a 200-Wallet Scan would take tens of thousands of requests (§9 Q3).
- **Copy Pool**: every Wallet from the Scan with at least the Minimum After-bets Resolved Positions in its Copy Sample that have a recorded price at the Main Copy Delay. The Before-Cut-off Passers who meet this rule are in it too.
- **Random Group Check**: the luck check on the Copy Test. The Passers' score is the average Follower Return of the Passers in the Copy Pool, at the Main Copy Delay, each Wallet counting equally. The system draws 10,000 random groups of the same size from the Copy Pool (no Wallet twice in one group) and scores each the same way. Copy p-value = (1 + number of random groups scoring ≥ the Passers) / (1 + 10,000). Copy Verdict: *Beat random picks* (Copy p-value < 0.05), *No better than random picks*, or *Not enough data* when no Passer is in the Copy Pool or fewer than 1,000 different groups of that size can be drawn from it. `[ASSUMPTION: 1,000]` Runs with a Seed, like the Skill Test.
- **Copy Test**: computing Follower PnL and Follower Return for each Copy Delay over the Copy Sample of each Before-Cut-off Passer, plus the Random Group Check. Paper only.
- **Domain**: the category of a Market: politics, sports, crypto, macro or other.
- **Domain Verdict**: a Verdict from the Skill Test on only one Domain's Resolved Positions, with the Bonferroni correction (FR-20).
- **Sample Dataset**: Wallet histories (Positions from before and after its default Cut-off Date, §9 Q6), Market data, and the recorded price history around each buy fill (enough to find the price at each Copy Delay), saved in the repository so the app can run without the network. Large synthetic groups are regenerated from the generator when the Sample Dataset is loaded (FR-12).
- **Synthetic Wallet**: a made-up Wallet with a known correct Verdict, generated by script with a fixed Seed. Types: see the table under FR-13.
- **Offline Mode**: the app reads only the Sample Dataset and makes no network calls.
- **Mock LLM Mode** (stage 3): the language model is replaced by keyword rules and text templates, so no key is needed.
- **Flag**: a label marking a Wallet as a likely bot or market maker (stage 3).
- **Explanation**: a short plain-language text describing a Wallet's Verdict (stage 3).

## 4. Features

### 4.1 Wallet Lookup and Data (stage 1)

**Description:** The user enters a Wallet address. The app fetches the Wallet's trades and positions plus the Markets they belong to, stores them in the database, and builds the Wallet's Positions. Realizes UJ-1, UJ-2.

#### FR-1: Look up a Wallet
The user can enter a Wallet address on the start page and get its result page. Realizes UJ-1.
- An address that is not a valid address format shows an error message and fetches nothing.
- A valid address with no Polymarket history shows "No Polymarket history found for this address", with the hint to use the address shown on the Polymarket profile page.
- The address is the one on the Polymarket profile page (the proxy wallet). Every Polymarket data source used here (trades, positions, activity, profile) is keyed by that address, and none exposes the signing account, so an address from a wallet app may show no history. (Data spike, 2026-10-21.)

#### FR-2: Fetch and cache data
The system fetches a Wallet's trades, positions and the related Markets from Polymarket's public APIs and stores them in the database.
- A second lookup of the same Wallet within 24 hours uses stored data and makes no network call. `[ASSUMPTION: 24 hours is fresh enough]`
- If Polymarket does not answer, the page says so and offers the stored data if any exists.
- Requests are paced so the app never exceeds Polymarket's published rate limits.

#### FR-3: Build Positions
The system combines a Wallet's fills into Positions and marks which are Resolved Positions.
- Several buys of the same outcome in the same Market become one Position, with Entry Price = the share-weighted average price.
- Positions come from two sources, both required: closed positions (exited or redeemed) and open positions. A losing Position that was never redeemed is worth 0, stays in the open list and is missing from the closed list: on one pool Wallet 837 of 1,196 positions were such losses, and only 7 of 30 checked were also in the closed list. A loss counts like any other. (Data spike, 2026-10-21.)
- A Market is resolved when the Market data says it is closed, its outcome prices are exactly 0 and 1, and it has a resolution time. The resolution time (needed for the Cut-off Date) always comes from the Market data: in the current data source the closed list's own timestamp is the Wallet's last event, 0 to 85 hours after resolution. A Market that resolved any other way (for example 50-50) is left out as "unclear resolution". (Architecture, 2026-10-21.)
- The shares held at resolution are the Wallet's bought shares minus its sold shares, from its activity rows. Redemptions are never used to count shares, because an unredeemed loser has none. (Architecture, 2026-10-21.)
- Besides fully sold Positions, a Position is left out of the Skill Test, counted, and shown with its reason when: the Wallet split, merged or converted shares in that Market (the recorded entry price of such a Position is bookkeeping, not a price paid); the token appears only in the activity rows; its shares held are not between 0 and the shares bought; the two sources disagree on shares bought by more than 1% `[ASSUMPTION]` (the size of the gap is stored); its Market has an unclear resolution; or the Wallet's history could not be read in full (FR-16). The same rules apply before and after the Cut-off Date. (Architecture, 2026-10-21.)
- A Position fully sold before resolution is not a Resolved Position. It is counted and shown, but left out of the Skill Test.
- A Position partly sold before resolution enters the Skill Test with the shares still held at resolution, at the original Entry Price. `[ASSUMPTION: testing the shares still held, at the original Entry Price, is a fair way to treat a partly sold Position]` The shares sold count toward Exit PnL.
- **Known limit (decided):** which Positions reach resolution is the trader's choice and can depend on how the price moved after the buy. A trader who sells losers early and keeps the rest looks better in the Skill Test than they are. v1 accepts this and makes it visible (FR-11); handling it in the test is deferred to v2 (§6.2).

### 4.2 Skill Test (stage 1)

**Description:** The core of the product: the method in the brief's *The Skill Test* section, implemented as a separate module with no network or web code in it, so it can be tested on its own. Realizes UJ-1, UJ-3.

#### FR-4: Real PnL
The system computes Real PnL from a Wallet's Resolved Positions.
- For three Wallets in the Sample Dataset, Real PnL equals a hand calculation stored with the tests (to the cent). At least one of the three paid trading fees, and its hand calculation subtracts them.

#### FR-5: Luck Distribution and p-value
The system runs 10,000 Simulations and computes the p-value.
- Hand-check Synthetic Wallet (10 bets at 0.50, all won): p-value between 0.0003 and 0.002 (exact answer 1/1024 ≈ 0.001).
- Adding a fixed fee to every Position of a Synthetic Wallet lowers its Real PnL by exactly the total fee and leaves the p-value and Verdict unchanged for the same Seed.
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
- N is 1 divided by the p-value, rounded to 2 significant figures: 0.0033 is shown as "about 1 time in 300", 0.0099 as "about 1 time in 100", 0.25 as "about 1 time in 4".
- When no Simulation reached the Real PnL, the card says "fewer than 1 time in 10,000", never "about 1 time in 10,000": 10,000 Simulations cannot show a smaller chance than that.
- When the p-value is above 0.5, the card says "more than half the time".
- A p-value of 1/10,001 is shown as "fewer than 1 time in 10,000", and 0.0099 as "about 1 time in 100".

#### FR-9: Luck chart
The page shows the Luck Distribution as a histogram with the Wallet's Real PnL marked on it.
- The axis is in dollars, and its range always includes the Real PnL, also when it lies beyond every Simulation, above or below.
- If the Real PnL is above every Simulation, the marker is labelled "above all 10,000 Simulations" (or "below all 10,000 Simulations" if it is under every one).
- A test with a Real PnL planted above the largest Simulation checks that the range includes it and that the marker carries the label.

#### FR-10: Too little data
For *Not enough data*, the page shows the number of Resolved Positions and how many more are needed, and shows no chart. Realizes UJ-2.

#### FR-11: Honesty notes
Every Verdict card shows:
- the share of Real PnL coming from the single largest Position;
- how many Positions were held to resolution out of all Positions (N of M), and the Exit PnL;
- a visible warning next to the Verdict when Exit PnL is below zero: "Positions this Wallet sold before resolution lost money in total. This Verdict covers only bets held to resolution.";
- when a Wallet has more than 2,000 Resolved Positions in the part tested, the line "Based on the latest 2,000 of N Resolved Positions; older results are not included." Why: older Positions are not fetched, and leaving them out can make a Wallet look better or worse than it is. For the after part the line says "first 2,000" instead; a Watchlist result says it rests on the two windows around the Cut-off Date, and that Positions bought before the date and resolved after it are in neither;
- how many Positions were left out of the test, for each reason (FR-3), and, when more than 10% `[ASSUMPTION]` of the Positions were left out for any reason together, a plain sentence that only part of the Wallet's activity was judged;
- how many fees failed the check against the Market's fee schedule, with their recorded total (Glossary, Own Fees);
- when more than 20% `[ASSUMPTION]` of the tested Positions sit in an event with another tested Position whose link the app cannot detect, a note that some bets may depend on each other and the result can look stronger than it is;
- the Seed the result was computed with (also on the Scan, Hold-up Test and Copy Test pages);
- a short fixed note on the test's limits (long shots tend to be overpriced; the Verdict covers only bets held to resolution, so early exits are not measured and can make a Wallet look better or worse than it is; Wallets are often looked up because they already looked good, and picking by results makes luck look more like skill) and that this is not financial advice.

Checks:
- The stop-loss Synthetic Wallet (FR-13) shows the warning. A Wallet with Exit PnL ≥ 0, or with no early sales, shows none.

### 4.4 Offline Running and Test Data (stage 1)

**Description:** Lets the examiner run and check the app without our keys or a working Polymarket API. Realizes UJ-3.

#### FR-12: Sample Dataset
The repository contains stored data for about 10 real Wallets (a mix of Verdicts, including at least one *Not enough data*) and the Synthetic Wallets, each with its Positions and the recorded price history around each buy fill. Large synthetic groups (the 1,000 coin-flippers) are not committed: loading the Sample Dataset regenerates them from the generator's fixed Seed. The committed Sample Dataset stays under 25 MB `[ASSUMPTION]`, checked by a test, so cloning needs no extra tools such as Git LFS.
- The real Wallets' price history is fetched as early as possible: on 2026-09-04 Polymarket replaced the price-history route the Copy Test uses with one that keeps one-minute prices for at least 7 days only. The old route still answers with no end date announced, and Data API v1 was retired with three days' notice (§9 Q3). (Edvard, 2026-10-21.)
- The Sample Dataset has one default Cut-off Date (§9 Q6). The real Wallets have Positions both before and after it, so the Hold-up Test and Copy Test run offline with that date. Online, the user can choose any date (FR-16).
- Stated limitation, one-way: for the two largest real Wallets (0xd218e4…, 0x63d43b…), the captured activity after the Cut-off Date stops at the 150,000-row cap (12 and 20 August 2025), so 808 and 418 of their 2,000 after-part Positions may miss later buy fills and are left out under the cap rule (FR-3). This cannot be repaired later: if the cap rule changes, the missing price windows can no longer be fetched once the old one-minute price route is gone. (Edvard, 2026-10-23.)

#### FR-13: Synthetic Wallets
A script generates the Synthetic Wallets in the table below from a fixed Seed. It also generates the price paths: forecaster, slow drift towards the Outcome over hours; speed trader, a jump to the Outcome seconds after the buy; coin-flippers, no edge. Running it twice gives identical files.

| Synthetic Wallet | How it is built | Expected result | Used by |
|---|---|---|---|
| Hand-check | 10 bets at 50¢, all won | Only "all 10 won" beats or ties it, so the exact answer is 1/1024 ≈ 0.001; the simulated p must land between 0.0003 and 0.002. Engine-level test, bypassing the 30-bet minimum | FR-5 |
| Coin-flipper | 1,000 wallets of 100 bets each, random prices between 10¢ and 90¢, outcomes drawn at those prices | *Likely skilled* or better for at most 7% of wallets (5% expected by design), *Skilled (high confidence)* for at most 2% | FR-5, FR-17, FR-18, FR-22, UJ-3 |
| Favourite-buyer | 100 bets at 90¢, wins 90 | *No evidence of skill* | FR-5 |
| Sharp trader | 100 bets at 50¢, wins exactly 70 | *Skilled (high confidence)* (exact binomial p ≈ 0.00004) | FR-5, FR-16, FR-22, UJ-3 |
| Thin wallet | 29 resolved bets | *Not enough data* | FR-6, FR-10 |
| Steady sharp (stage 2) | 100 bets at 50¢ winning 70 before the cut-off, the same after | Passes before; still *Skilled (high confidence)* on its after-cut-off bets | FR-16, FR-17 |
| Lucky streak (stage 2) | The coin-flippers that happen to pass before the cut-off; after it, outcomes drawn at fair odds | Pass before by construction; pooled after-cut-off bets show *No evidence of skill* | FR-17 |
| Forecaster (stage 2) | Buys at 50¢, wins 70%; the price drifts slowly towards the outcome over hours | Copy-test profit stays positive at a 30-minute delay | FR-16, FR-18 |
| Speed trader (stage 2) | Buys at 50¢ seconds before the price jumps to the outcome | Copy-test profit is zero or negative at a 5-minute delay | FR-16, FR-18 |
| Stop-loss trader (stage 1) | 100 bets at 50¢ with no edge; bets whose price has fallen are sold before resolution, the rest are held to resolution | The card shows how many bets were held, the negative realised PnL of the sold ones, and a visible warning next to the verdict. The verdict itself may read skilled: that is the known limit | FR-11 |
| Market maker (stage 3) | Many small buys and sells on both sides of the same markets, flat inventory | Flagged as likely market maker | FR-22 |
| Split-domain trader (stage 3) | 60 bets at 50¢ in crypto, exactly 42 won; 60 bets at 50¢ in sports, exactly 30 won | Crypto *Skilled (high confidence)*, sports *No evidence of skill* | FR-20 |

#### FR-14: Offline Mode
One setting makes the app use only the Sample Dataset.
- In Offline Mode, every Wallet in the Sample Dataset can be looked up with the network disconnected.
- Looking up a Wallet outside the Sample Dataset in Offline Mode shows "Not available offline".
- Offline Mode never calls the language model, even when a key is set: it uses the stored Domain labels and the templates. It keeps its data apart from the data of online runs, so an online lookup never appears offline and sample data never appears online. (Architecture, 2026-10-21.)

### 4.5 Is Skill Worth Following? (stage 2)

**Description:** Answers the follower's question: which wallets are worth following, does their skill last, and does it survive being copied late. Everything here is computed on recorded data; nothing places orders. Realizes UJ-4.

#### FR-16: Scan and Watchlist
The user chooses a Cut-off Date, starts a Scan of the top Wallets by profit (after fees) made before that date (default 200), and sees the Watchlist, sorted by p-value, with the Minimum Luck Passes shown next to it. `[ASSUMPTION: 200 Wallets is a sensible default Scan size; see §9 Q3 for the measured fetch cost]`
- Only Positions resolved before the Cut-off Date count toward the profit that ranks the Wallets, so nothing after the date decides who is scanned (§9 Q2).
- The candidate Wallets are every Wallet that held a Position in a chosen set of Markets resolved before the Cut-off Date, read from each Market's list of positions (closed ones and still-held ones, which include unredeemed losers), so Wallets that later went quiet or lost money are in the list too. Polymarket's leaderboard has no date setting and shows only today's survivors. The data spike's method, walking back through a Market's trades, does not work on the current data source. (Data spike and architecture, 2026-10-21.)
- The funnel: the Markets resolved in the 90 days before the Cut-off Date, top 100 by volume, chosen without looking at outcomes; from their candidates, a shortlist of 3 × the Scan size by a quick profit estimate that also counts unredeemed losses; then each shortlisted Wallet's full data, ranked by Real PnL. `[ASSUMPTION: 90 days, 100 Markets, 3 ×]` The Scan page states the population tested ("Markets resolved in the 90 days before the Cut-off Date, top 100 by volume"), how many of the 100 Markets were used, and that the shortlist estimate is approximate. (Edvard, 2026-10-21.)
- A Market whose list could not be read in full gives no candidates and is shown as "not used: partial", because a partly read list leans towards winners or losers. A Wallet whose history could not be read in full is kept, marked "not fully read" everywhere it is counted (ranking, Watchlist, Passers, Hold-up groups, Copy Pool), and its unread Positions are left out (FR-3). Only Polymarket not answering stops a Scan; it can then be resumed. (Edvard, 2026-10-21.)
- A Wallet with more than 2,000 Resolved Positions before the Cut-off Date is not left out: it is ranked, and Skill Tested, on its latest 2,000 of them (those resolved last before the date), and its Verdict card says so (FR-11). Its after part is likewise capped at the first 2,000 after the date (FR-17). This is a stated limitation: older results do not count, so such a Wallet can look better or worse than its whole history would show. `[ASSUMPTION: 2,000 Positions; in a draw of 7 pool Wallets ranked in the top 3,000, 6 had more than 2,000 closed Positions (§9 Q3)]`
- A different Cut-off Date means a new Scan, because the list of Wallets changes with it. Stored Wallet data is reused (FR-2), so only Wallets not seen before are fetched.
- A Scan of the Sample Dataset in Offline Mode, with its default Cut-off Date (FR-12), puts at least the sharp-trader, steady-sharp, forecaster and speed-trader Synthetic Wallets on the Watchlist.
- A Scan of 200 Wallets shows "at least about 2 of 200 would pass by luck alone, probably more, because these Wallets were picked for high profit".
- The page shows progress during a Scan; an interrupted Scan resumes without re-fetching finished Wallets.
- The Watchlist is stored in the database with the Scan date and its Cut-off Date, and is never sent anywhere.

#### FR-17: Hold-up Test
The user sees the Hold-up Test result, for the Cut-off Date the Scan was started with (FR-16), for the Before-Cut-off Passers and for the Comparison Group: Resolved Positions in the after part, Real PnL, p-value and Verdict for each group.
- Both groups are picked from the same Scan by the same rule, using only the before part, and both are tested on the after part. No Position from after the Cut-off Date decides who is in either group.
- Nor does any Position from after the Cut-off Date decide which Wallets are in the Scan itself (FR-16).
- A Wallet that passes only when Positions from after the Cut-off Date are included is not in the Before-Cut-off Passers.
- Each Wallet is in at most one of the two groups.
- A Wallet counts in its group's result only if it has at least the Minimum After-bets Resolved Positions in the after part. The same minimum applies to both groups.
- Wallets that stop betting after the Cut-off Date (none, or fewer than the minimum) are dropped by that same rule in both groups, never kept in one and dropped in the other. Each group's result shows Wallets in the group, Wallets dropped for too few after bets, and Resolved Positions counted.
- If the share of Wallets dropped differs by more than 20 percentage points between the two groups, the page says so next to the results: "More Wallets were dropped in one group than in the other. Wallets that stop betting may be the ones that lost, so the group with more dropped Wallets may look better than it is." `[ASSUMPTION: 20 percentage points is "way more"]` A planted example (60% dropped in one group, 10% in the other) shows the message; equal shares show none.
- The steady-sharp Synthetic Wallets are rated *Skilled (high confidence)* on their after part.
- The lucky-streak Synthetic Wallets (coin-flippers that passed before the Cut-off Date) are rated *No evidence of skill* on their after part.
- A group with fewer than 30 Resolved Positions in the after part shows *Not enough data*.
- A Wallet's after part is its first 2,000 Positions in resolved Markets bought on or after the Cut-off Date, the same cap as the before part, and the page says so. (Edvard, 2026-10-21.)
- The pooled after part is simulated with linked bets sharing one draw (Glossary, Simulation): Passers who bet in the same Markets are not counted as independent evidence. A planted check: 7 coin-flipper Passers holding the same side of the same 40 Markets get p < 0.05 in at most 7% of 1,000 runs. (Edvard, 2026-10-21.)
- Each group's result shows how many of its Wallets are "not fully read" (FR-16).

#### FR-18: Copy Test
For each of the Before-Cut-off Passers, over its Copy Sample, the system shows Follower PnL and Follower Return at each Copy Delay next to the Wallet's own Real PnL over the same positions, using Polymarket's recorded price history. Above them it shows the Random Group Check at the Main Copy Delay: the Copy p-value as "random groups did as well in X% of draws", and the Copy Verdict.
- The speed-trader Synthetic Wallet has Follower PnL ≤ 0 at a 5-minute Copy Delay.
- The forecaster Synthetic Wallet has Follower PnL > 0 at a 30-minute Copy Delay.
- For a hand-made set of three Positions in a Market with a fee, Follower PnL and Follower Return equal a hand calculation stored with the tests (to the cent).
- A planted Scan of 10 forecaster Passers and 100 coin-flipper Wallets (copy prices give the coin-flippers no edge) gets a Copy p-value < 0.01 at the Main Copy Delay.
- Across 1,000 planted Scans of 110 coin-flipper Wallets, each with 10 of them picked at random as the Passers, the Copy p-value is < 0.05 in at most 7%.
- A Copy Pool of 6 Wallets with 3 Passers (20 possible groups) shows *Not enough data*.
- The same data with the same Seed gives the identical Copy p-value.
- When no random group scores as well as the Passers, the page says "no random group did as well in 10,000 draws", never a percentage: the Copy p-value's floor of 1/10,001 would otherwise read as "0.01% of draws", which is false.
- The Copy Verdict comes only from the Main Copy Delay. The 1- and 30-minute results show Follower PnL and Follower Return only, marked as extra information, with no Copy Verdict.
- The per-Wallet numbers are marked as not luck-checked; only the Random Group Check is.
- A position with no recorded price at a Copy Delay is left out of that delay's sum, and the count of left-out positions is shown.
- Every Wallet is priced on its Copy Sample (at most 100 after Positions, drawn with the Seed by one rule for all Wallets); the page shows "priced N of M after Positions" and says the numbers rest on a sample. A Wallet with 250 after Positions shows "priced 100 of 250"; the same Seed gives the same sample.
- Follower PnL includes the Spread Allowance (half a cent per share). The page states its limits: the allowance comes from large liquid Markets, where the gap between buyers and sellers had a median of 1 cent and a 90th percentile of 3 cents; thin Markets were not measured and may cost more; and the follower's own price impact is ignored. Follower PnL is therefore still an upper bound.
- The hand-calculated three-Position set includes the Spread Allowance.
- Every buy fill is copied at its own time plus the Copy Delay (Glossary, Follower PnL). The hand-calculated set includes a Position bought in more than one fill. (Edvard, 2026-10-21.)
- The page shows how many of the Passers' Copy Sample Markets are shared by two or more Passers. A planted gate: across 1,000 planted Scans in which 10 coin-flipper Passers hold the same side of the same 40 Markets, the Copy p-value is < 0.05 in at most 7%. If the gate fails, the Random Group Check must be changed to account for shared Markets before a Copy Verdict is shown; that is a plan change. Why: without it, Passers in shared Markets beat random groups by luck about 27% of the time instead of 5% (architecture review, 2026-10-21). (Edvard, 2026-10-21.)
- Price history comes from the old price-history route while it answers with one-minute prices, else from its replacement, which keeps one-minute prices for at least 7 days only. A buy with no one-minute price is left out of that delay and counted (above); the app never silently uses coarser prices. Fetched price history is kept for good. (Architecture, 2026-10-21.)
- **Fallback if the old route is gone (Edvard, 2026-10-24):** the old route is checked daily. Its replacement keeps one-minute prices for 7 days only, so a real-data Copy Test for a past Cut-off Date needs prices captured in advance. An insurance pool of 50 Wallets for the default Cut-off Date, picked by a rule written down and committed before the capture (`spike/INSURANCE-RULE.md`), is captured with every after-part buy fill's price window. If the route is gone when the real-data run is made (SM-5), the Copy Test runs on this frozen pool instead of a full Scan's Copy Pool: Passers, Copy Samples and the Random Group Check are computed by the app as usual, and the page and the README state the limits: a pool of 50 fixed in advance, not the app's Scan; the pool was ranked by the spike's estimate, not the app's final Real PnL; and with fewer than 2 Passers the Copy Verdict is *Not enough data*, reported as it comes out.

### 4.6 Language Model and Domains (stage 3)

**Description:** Splits the Skill Test by Domain so the user sees where the edge is. The language model behind it can be replaced by Mock LLM Mode, so stage 3 also runs with no key. Realizes UJ-5.

#### FR-15: Mock LLM Mode
One setting replaces the language model with keyword rules (Domain) and templates (Explanation). It is on by default when no key is set. The ID is kept from when this requirement sat in stage 1.
- With no key set, FR-19 and FR-23 run in Mock LLM Mode and their tests pass.

#### FR-19: Classify Markets
The system assigns each Market a Domain using the language model (or Mock LLM Mode).
- Each Market is classified once; the label is stored and reused.
- Classification of a hand-labelled set of 50 Markets agrees with the hand labels on at least 80%. `[ASSUMPTION: 80% is a sensible bar]` The hand labels are made blind and committed before any model output is seen and never edited afterwards. Blind means Edvard sees only the 50 Markets' questions: no keyword-rule label, no model label and no category field from the data, so the gate measures the model against him, not against the keyword rules. His labels are committed before either labeller runs on these 50 (Edvard, 2026-10-24). The five Domains are defined by Edvard himself, one line each saying where the overlap cases go (the AI suggests none), written first and in the same sitting as the labels, and committed together with them; the model's prompt quotes the definitions word for word and the keyword rules aim at them (Edvard, 2026-10-24). The bar applies to the language model; if the default model (Claude Haiku 5.5) misses it, a larger model is tried and both results are reported. The keyword rules of Mock LLM Mode are checked on other Markets than these 50. (Edvard, 2026-10-21.)
- Each label is stored with its source (model name or keyword rules) and date. Running the classification again is a deliberate action, never a side effect, because the model's answers can differ between runs. (Edvard, 2026-10-21.)

#### FR-20: Domain Verdicts
The system runs the Skill Test per Domain with at least 30 Resolved Positions, multiplying each p-value by the number of Domains tested (Bonferroni correction, capped at 1) before choosing the Verdict.
- Domains tested means the Domains with at least 30 Resolved Positions. A Domain with fewer is shown as *Not enough data* and does not count toward the multiplier. *Other* is a Domain like the rest.
- A Synthetic Wallet that is sharp in one Domain and a coin-flipper in another gets *Skilled (high confidence)* in the first and *No evidence of skill* in the second.

#### FR-21: Domain table
The Verdict page shows one row per Domain: Domain, Resolved Positions, Domain Verdict.

### 4.7 Flags and Explanations (stage 3)

**Description:** Marks wallets whose profit comes from bots or market making rather than opinions, and explains the Verdict in plain language.

#### FR-22: Bot and market-maker Flag
The system Flags a Wallet when at least 2 of these 3 rules hold: `[ASSUMPTION: starting values, to tune on the synthetic market maker]`
- it bought both outcomes in at least 30% of the Markets it traded;
- it sold at least 80% of the shares it bought (flat inventory);
- the median time from buy to sell, over the shares it sold, is under 1 hour.

The Flag is shown beside the Verdict as "Likely market maker (heuristic, may be wrong)", never as a fact, and does not change the Verdict.
- The synthetic market-maker Wallet is Flagged; the coin-flipper and sharp-trader Synthetic Wallets are not.

#### FR-23: Explanation
The system generates an Explanation of the Verdict (and Domain Verdicts) of at most 60 words with the language model, or from a template in Mock LLM Mode. It is shown under the Verdict card. `[ASSUMPTION: 60 words]`

#### FR-24: Explanation check
Before an Explanation is shown, code checks that it names the same Verdict and the same odds phrase as the card (FR-8), and contains none of the words banned in §8 Wording. An Explanation that fails is replaced by the template text.
- A planted Explanation with a wrong Verdict is replaced by the template.
- Each replacement is counted, so the replacement rate (SM-7) can be reported.

## 5. Non-Goals

- No trading, automated copy-trading, alerts or anything that touches a wallet's funds or keys. The Copy Test is a paper calculation on recorded prices.
- No financial advice. Verdicts describe past performance only.
- No public leaderboard or social features. The Watchlist is private to the machine running the app.
- No detection of sybil clusters (many wallets run by one person) in v1.
- No markets other than Polymarket in v1.
- No user accounts or login.

## 6. MVP Scope

### 6.1 In Scope

- **Stage 1 (MVP, must be finished first):** FR-1 to FR-14. A complete, tested app that gives a whole-wallet Verdict and runs offline.
- **Stage 2:** FR-16 to FR-18 (Scan, Hold-up Test, Copy Test).
- **Stage 3:** FR-15 and FR-19 to FR-24 (Mock LLM Mode, Domains, Flags, Explanations). Trimmed first if time runs short.

Each stage ends with all its tests passing and the README updated, so the project is deliverable after any stage.

### 6.2 Out of Scope for v1

- Positions fully sold before resolution in the Skill Test (shown with their Exit PnL, not tested). Deferred to v2.
- Sybil-cluster detection. Deferred to v2: the feature most likely to blow the timeline.
- Kalshi, Manifold and other venues. Deferred to v2.

## 7. Success Metrics

**Primary**
- **SM-1**: All Skill Test correctness tests pass (hand-check, coin-flipper, sharp trader, favourite-buyer, thin wallet, reproducibility, hand-calculated Real PnL). Validates FR-4 to FR-7.
- **SM-2**: The examiner can run the app and the tests from the README with no network and no keys. Validates FR-12 to FR-14.

**Secondary**
- **SM-3**: A lookup of a Wallet with up to 1,000 Resolved Positions returns a Verdict within 10 seconds on an ordinary laptop (stored data). Validates FR-5.
- **SM-4**: The Hold-up Test and Copy Test synthetic checks pass (steady sharp vs lucky streak; forecaster vs speed trader; Random Group Check on planted Scans). Validates FR-17, FR-18.
- **SM-5**: A Hold-up Test and a Copy Test have been run on real data, and the result is reported in the README and the reflection report, whichever way it comes out. Validates FR-16 to FR-18.
- **SM-6**: Stage 3 Domain labels agree with hand labels on at least 80% of 50 Markets. Validates FR-19.
- **SM-7**: The replacement rate: the share of Explanations that fail the Explanation check and are replaced by the template, counted over the Sample Dataset's Wallets and Domain Verdicts and reported in the README. In Mock LLM Mode it should be 0 (a template that fails the check is a bug). With a real model it is expected to be above 0, and the number is reported whichever way it comes out. No target. Validates FR-24.

**Counter-metrics (do not optimise)**
- **SM-C1**: The share of real Wallets rated *Skilled (high confidence)*. A test that calls more wallets skilled is not better; the Yale SOM study found only ~3% of accounts show skill (source: `addendum.md`). Counterbalances SM-1.
- **SM-C2**: The size of the Watchlist and how good the Hold-up and Copy results look. A real result showing that skill does not last, or cannot be copied, is a valid outcome, not a failure. Counterbalances SM-5.
- **SM-C3**: How confident or persuasive Explanations sound. They must never claim more than the test shows. Counterbalances SM-7.

## 8. Cross-Cutting Requirements

- **Runnable from the README**: from a fresh clone with uv installed (one documented install line; uv fetches Python 3.12 or newer itself if needed), the app starts in at most 3 documented commands (install dependencies, load the Sample Dataset, start the app). The README lists the prerequisites, the exact commands, the address to open, how keys are set in `.env`, and where each JavaScript file is and what it does. A CI job runs these exact commands on a fresh checkout and checks a Sample Wallet's Verdict. (Edvard, 2026-10-21.)
- **Runs on Windows, macOS and Linux**: a GitHub Actions workflow installs the dependencies and runs the test suite on all three systems, with Python 3.12 and 3.14, on every push. The whole test suite runs with network access blocked, which also proves Offline Mode on every push. A failing run on any of them counts as a failing build.
- **Runs locally**: the app runs on the user's or examiner's laptop as a web page opened in a browser; it is not hosted publicly. `[ASSUMPTION: local only is enough; the course does not require hosting]`
- **Database**: cached Polymarket data, Domain labels, Scans and Watchlists are kept in a database (a local SQLite file is enough, nothing to install or host). Reason: course requirement (teacher, 17 Sept 2026).
- **Secrets**: the language-model key is read from `.env`, which is never committed; the repository contains `.env.example`.
- **Polite to Polymarket**: a lookup of a Wallet already stored makes 0 network calls (FR-2). Requests are paced at no more than 5 per second, a quarter of the tightest published limit on the routes the app uses (200 requests per 10 seconds for each of Data API v2's `/v2/positions`, `/v2/activity` and `/v2/prices-history`; checked on docs.polymarket.com, 2026-10-21); Polymarket slows requests that go over rather than refusing them. `[ASSUMPTION: 5 requests per second; the spike only tested one request every 1.5 seconds]` A first fetch of a Wallet's Positions takes one request per 1,000 positions or activity rows and one per 20 Markets (§9 Q1); the Cut-off Date is found with the data source's own time filter (tested, 2026-10-21). The typical spike Wallet (356 closed Positions, about 8,000 trades) needs about 30. The pace is one setting that can be turned down, and values above 5 per second are refused.
- **Testable core**: the Skill Test module has no network, web or language-model code, and every FR with consequences has at least one automated test.
- **Wording**: the app never uses words like "guaranteed", "insider" or "will win" about a Wallet.
- **Pages, navigation and accessibility**: which pages exist and how the user moves between them is specified in the UX step (`bmad-ux`), not here. It has to cover at least: lookup, Verdict result, Scan, Watchlist, Hold-up Test and Copy Test. Two rules hold from now on: the Verdict is always shown as text, never by colour alone; and the luck chart (FR-9) has a text alternative that states the Real PnL and the odds phrase from FR-8.

## 9. Open Questions

1. ~~Which Polymarket endpoints give resolved and closed positions per Wallet with Entry Price, and how are fees, splits, merges and redemptions represented? Which Markets charge a taker fee, at what rate, and how is it computed (needed for the Follower Fee, FR-18)? Do sell fills give the Exit PnL (FR-11)? Also: the address on a profile page is usually a proxy wallet, not the signing account; check that FR-1's address check and the Data API lookups use the same address.~~ **Closed (data spike, 2026-10-21; details and evidence in `spike/FINDINGS.md`).** Closed positions (entry price, size, realized PnL, resolution time) come from the Data API's closed-positions list, 50 per request; open and unredeemed losing positions from its positions list, 500 per request; both are needed (FR-3). Resolution times and fee schedules come from the Gamma API, 20 Markets per request. Sells are trade rows with a price, so Exit PnL can be computed from them. Taker fee = shares × rate × price × (1 − price), rate 0.03 to 0.07 by category, makers pay none; the fee schedule is on each Market, and fee Markets are rare before late 2025 and common in 2026. Realized PnL is net of fees; a taker trade's cash amount includes the fee. Positions made by a split show an entry price of exactly 0.5 and have no buy trades. One address (the proxy wallet) is used by every source (FR-1). Still open, for the architecture: how splits and merges are treated in the Skill Test; the three unexplained cases where total bought is below the buy rows by 0.007% to 4%; and whether the older activity endpoint will be retired in favour of its cursor-paged v2. **Settled in architecture (2026-10-21; probes `spike/arch_probe1.py` to `arch_probe8.py`, 37 read-only requests):** Data API v1 is retired on 2026-10-24, so the app uses v2 only (Edvard: no point designing on v1 data). v2 serves closed and open positions from one list with a status filter, 1,000 rows per page, cursor-paged; its time filters were proven to work (a made-up parameter as control). Splits, merges and conversions are left out of the Skill Test and counted; gaps above 1% are left out with their size stored (FR-3). Own Fees come from the activity rows: v2 gave the same fee as v1 on all 25 fee fills checked.
2. Which public endpoint lists the top Wallets by profit for a Scan, and how far back does it go? **Decided (Edvard, 2026-10-16): a Scan ranks Wallets only on profit from Positions resolved before the Cut-off Date.** Ranking on all-time profit would let results after the Cut-off Date decide which Wallets are tested, and the Hold-up Test would be rigged. **Was open for the data spike (closed below, 2026-10-21):** (a) today's leaderboard shows only survivors, the Wallets that are still active and profitable, so a list taken from it is a survivor sample; the spike must also find an older list of Wallets, or another way to list Wallets as they were before the Cut-off Date; (b) whether an endpoint can rank by profit up to a date at all, or the app must compute that profit itself from each Wallet's Positions. **Knock-on, applied:** FR-16, FR-17 and UJ-4 now take the Cut-off Date when the Scan starts; a different date means a new Scan. (Data spike, before architecture.) **Closed (data spike, 2026-10-21; `spike/FINDINGS.md`; decided by Edvard the same day):** the leaderboard has no date setting (the official reference lists none) and shows only today's survivors, so it is not used for a Scan. A Scan builds its candidate list from the trades in Markets resolved before the Cut-off Date (Markets are listed through the Gamma API, traders through the Data API's trades list with an end time; one query reaches only the newest 10,000 or so trades of a Market, and moving the end time back reaches earlier ones, so large Markets are sampled across their life) and computes each candidate's profit from its closed and open Positions. This includes Wallets that later went quiet or lost money. Sampling matters: in a test on 10 large Markets, the last 1,000 trades before close gave 331 Wallets that appeared in two or more Markets, and 1,000 trades spread over each Market's life gave 216. Cost: listing candidates is cheap; the cost is fetching each candidate's history, so a first Scan is slow and a per-Wallet limit is needed (FR-16). The leaderboard is still usable for the lookup page. **Changed (Edvard, 2026-10-23):** it is not used to choose the Sample Dataset's real Wallets either, because it ranks on results from after the Cut-off Date; they come from the same funnel as a Scan, judged on the before part only (Q5). **Changed in architecture (2026-10-21):** the trade walk-back does not work on Data API v2 (a Market's trades ignore the end time; tested with a control). The candidates now come from each Market's own list of positions, closed and still held, which includes losers (on a $71M Market, 874 of 995 Wallets had lost); a partly read Market gives no candidates. The funnel is in FR-16. (Edvard: better than the old method, because it gets the losers too.)
3. ~~Does Polymarket's price history have minute-level prices for resolved Markets, far enough back for the Copy Test? The Random Group Check needs these prices for the after part of every Wallet in the Copy Pool (up to the whole Scan, about 200 Wallets), not just the Passers, so expect many more requests and a larger Sample Dataset. If only coarser data exists, the Copy Delays and the Main Copy Delay change, and the new Main Copy Delay is fixed before any data is looked at. (Data spike, before architecture.)~~ **Closed (data spike, 2026-10-21; `spike/FINDINGS.md`).** Yes: one-minute price points exist for resolved Markets from mid-2023, one request covers 14 days of one outcome, and the Copy Delays (1, 5 and 30 minutes) and the Main Copy Delay (5 minutes) stay as they are. Thin Markets get filled-in flat prices, and the history is the midpoint of buyers' and sellers' prices (FR-18 Spread Allowance). **Measured cost.** Price requests are per outcome, not per bet: for one Wallet, 336 of 352 outcomes needed a single 14-day window (1.06 requests per outcome). For 7 Wallets drawn at random from the candidate list and ranked in the top 3,000 all-time, the reading was capped at each Wallet's oldest 2,000 closed Positions, so the counts are floors: 6 of 7 hit the cap, and after-the-example-cut-off outcomes were 145, 551 and 1,292 for the three Wallets whose later Positions were read (the other four showed none only because the cap stopped the reading earlier). The 7 Wallets shared only about 5% of their outcomes. So a Copy Pool of a whole 200-Wallet Scan means roughly 30,000 to more than 250,000 price requests, which is hours to days at one request per 1.5 seconds. **Decided (Edvard, 2026-10-21): a mix.** The Copy Test prices a Copy Sample of at most 100 after Positions per Wallet (Glossary, FR-18), and requests are paced faster, at up to 5 per second (§8). That makes a 200-Wallet Copy Pool at most about 20,000 price requests, roughly 70 minutes at 5 per second, against the 30,000 to over 250,000 above. The default Scan size stays 200. **Decided the same day for big Wallets:** they are kept and ranked on their latest 2,000 Positions before the Cut-off Date, as a stated limitation (FR-16, FR-11). **Still open for architecture:** the after part of big Wallets for the Hold-up Test is still fetched in full (up to a few dozen requests per Wallet, for about 200 Wallets); whether a lookup of one very large Wallet (outside a Scan) also uses the latest 2,000 Positions. **Settled in architecture (2026-10-21, Edvard):** one rule everywhere, the 2,000 Positions closest to the Cut-off Date on each side (latest 2,000 before, first 2,000 after); a lookup uses the latest 2,000 overall. **New risk (2026-10-21):** on 2026-09-04 Polymarket replaced the price-history route with one that keeps one-minute prices for at least 7 days only (5-minute for 60 days, 30-minute for 90). The old route still answers. The Sample Dataset's price history is therefore fetched as early as possible and kept for good (FR-12, FR-18). Copying every buy fill instead of one buy per Position does not change the request count when fills are packed into 14-day requests (measured on the typical Wallet: 1.06 requests per outcome either way).
4. ~~Is the app acceptable to examine in Mock LLM Mode, which is what runs when no key is set (FR-15)?~~ **Closed (decided by Edvard, 2026-10-16): yes.** Domain labels then come from keyword rules and Explanations from templates, so stage 3 shows the structure but not the model's quality. That is acceptable as long as the README says exactly how to set a key (§8). The choice of language model is a proposal in `addendum.md`, to confirm in architecture.
5. Which 10 real Wallets go into the Sample Dataset? They should cover each Verdict. (Owner: Edvard, after the data spike, before the Sample Dataset is built.) **Decided (Edvard, 2026-10-23):** 10 Wallets from the Scan funnel for the default Cut-off Date (Markets resolved in the 90 days before it, top 100 by volume), picked on the before part only; the only after-part data used were activity counts, to check that each Wallet has bets after the date (FR-12) and that one paid fees (FR-4). No real Wallet was estimated *Skilled (high confidence)*, so the Synthetic Wallets cover that Verdict. Three spare Wallets' price windows are captured as insurance only; a later swap needs a data reason and is logged. Method, list and counts: `spike/FINDINGS.md`, *Sample Dataset pick*.
6. Which Cut-off Date for the real-data Hold-up Test? It must leave enough bets in the after part and enough in the before part, and the Minimum After-bets should not drop most of the Passers. **Decided (Edvard, 2026-10-16): the date chosen here is the Sample Dataset's one default Cut-off Date, used by the offline checks in FR-12 and FR-16; online, any date can be chosen.** The value itself is still open. **Constraint from the data spike (2026-10-21):** price history at one-minute resolution exists only from mid-2023 (Markets resolved in July 2023 had it; January 2023 and earlier had none), and the Copy Test needs prices around the buys in the after part, so the default Cut-off Date must be after 1 July 2023. (Owner: Edvard, after the data spike, when real Wallets are picked.) **Decided (Edvard, 2026-10-23): 1 July 2025**, set before any Wallet was looked at. Why: about 2 years before it and 16 months after it, all after-part buys inside the range where one-minute prices were found, and a funnel window (April to June 2025) with a normal mix of Markets instead of one event such as the 2024 US election.
7. Maybe later: should the app report a measured luck-pass rate for top-by-profit picks? Run the same top-by-profit selection on a population of coin-flipper Synthetic Wallets and show the share that pass, next to the Minimum Luck Passes. Not in v1 scope; revisit if time allows after stage 2.

## 10. Assumptions Index

Each is a starting value, not measured. Edvard confirms or changes it once real data exists (after the data spike); a change goes in the memlog first.

- §4.1 FR-2: stored data counts as fresh for 24 hours.
- §4.1 FR-3: partly sold Positions enter the Skill Test with the shares held at resolution, at the original Entry Price.
- §4.6 FR-19: 80% agreement with hand labels is a sensible bar for Domain classification.
- §4.7 FR-22: Flag rules (at least 2 of 3: both outcomes in at least 30% of Markets; sold at least 80% of shares bought; median buy-to-sell time under 1 hour) are starting values, to tune on the synthetic market maker.
- §4.7 FR-23: an Explanation of at most 60 words is enough.
- §3, §4.5 FR-17: a Wallet needs at least 10 Resolved Positions in the after part to count in the Hold-up Test (Minimum After-bets).
- §4.5 FR-17: a difference of more than 20 percentage points in the share of Wallets dropped between the two groups is "way more" and gets a message.
- §3, §4.5 FR-18: the Random Group Check needs at least 1,000 different possible groups to give a Copy Verdict.
- §4.5 FR-16: 200 Wallets is a sensible default Scan size (fetch cost now measured, §9 Q3; the value itself is not).
- §4.5 FR-16, FR-11: a Wallet with more than 2,000 Resolved Positions is ranked and Skill Tested on its latest 2,000.
- §3, §4.5 FR-18: the Copy Sample is at most 100 after Positions per Wallet.
- §8: requests are paced at no more than 5 per second (untested above one every 1.5 seconds).
- §3, §4.5 FR-18: the Spread Allowance is half a cent (0.005) per share; measured in large liquid Markets only.
- §8: the app runs locally on the user's or examiner's laptop as a web page; it is not hosted publicly.
- §3, §4.1 FR-3: a gap above 1% between the two sources' shares bought leaves a Position out.
- §4.3 FR-11: more than 10% of Positions left out gets a plain sentence; more than 20% in events with undetected links gets a note.
- §4.4 FR-12: the committed Sample Dataset stays under 25 MB.
- §4.5 FR-16: the Scan funnel uses Markets resolved in the 90 days before the Cut-off Date, the top 100 by volume, and a shortlist of 3 × the Scan size.
