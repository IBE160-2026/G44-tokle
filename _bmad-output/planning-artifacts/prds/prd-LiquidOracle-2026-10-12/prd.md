---
title: "PRD: LiquidOracle"
status: final
created: 2026-10-12
updated: 2026-11-18
---

# PRD: LiquidOracle

## 0. Document Purpose

This PRD turns the product brief (`_bmad-output/planning-artifacts/briefs/brief-LiquidOracle-2026-09-16/brief.md`) into numbered, testable requirements. Architecture, epics and stories build on it. Terms in §3 Glossary are used exactly as defined. Features are grouped in §4 with globally numbered requirements (FR-1 …). Starting values that are not measured are tagged `[ASSUMPTION]` inline and listed in §10.

Three companion files hold what is not a requirement:
- `decision-log.md`: why each decision was made, when and by whom, and the earlier wording of every line this PRD has since changed or moved.
- `addendum.md`: technology and Polymarket data-source details.
- `.memlog.md`: the running audit trail of the BMAD workflow.

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
  1. Jonas opens the Scan page, sets the Cut-off Date to 1 June and starts a Scan of the top 200 Wallets by profit made before June.
  2. When it finishes, the Watchlist shows 7 Wallets rated *Skilled (high confidence)*, with the note "at least about 2 of 200 would pass by luck alone, probably more, because these Wallets were picked for high profit".
  3. Re-rated on only the bets that resolved before June, all 7 still pass: they are the Before-Cut-off Passers. The other scanned Wallets, rated on the same bets, that did not pass form the Comparison Group.
  4. The Hold-up Test: on the bets opened after June, the Passers kept beating the odds (*Skilled (high confidence)* on 640 later bets); the Comparison Group did not.
  5. The Copy Test: a follower copying the Passers 5 minutes late, after fees, would have earned an average return that only 0.4% of 10,000 random groups of 7 Wallets from the same Scan matched (*Beat random picks*).
  6. Per Wallet, 5 of the 7 still make money at 5 minutes; on the other 2 the profit vanishes already at a 1-minute delay: speed traders. The page notes that these single-Wallet numbers are not luck-checked. He keeps the 5 forecasters on his list.

- **UJ-5. Jonas sees where the edge is** (stage 3).
  For a wallet with 352 resolved bets, the page adds a domain table: crypto *Skilled (high confidence)* on 180 bets, sports *No evidence of skill* on 150, politics *Not enough data* on 22. Under the Verdict card sits a 45-word Explanation. Another wallet shows "Likely market maker (heuristic, may be wrong)" beside its Verdict, which stays unchanged.

## 3. Glossary

Definitions only. The rules that use a term are in the FR named after it.

- **Wallet**: a Polymarket account, identified by its public address.
- **Market**: one Polymarket question (e.g. "Will X win the election?"). Has one or more outcomes and, once settled, a resolution.
- **Position**: all of one Wallet's buys of one outcome in one Market, combined. One Position = one bet, however many fills it was bought in.
- **Resolved Position**: a Position still held when its Market resolved. Only Resolved Positions enter the Skill Test. A Sliver is not counted as one.
- **Sliver**: a Position with less than 1% `[ASSUMPTION]` of its bought shares, and fewer than 1 share, still held when its Market resolved. Its money counts, but it is not counted as a bet (FR-3).
- **Entry Price** (*p*): the average price paid per share of a Position, between 0 and 1: the share-weighted average of its buy fills, which sells do not change. Read as the market's probability for that outcome.
- **Shares** (*s*): the number of shares held in a Position at resolution.
- **Outcome** (*o*): 1 if the Position's outcome happened, 0 if not.
- **Own Fees**: the taker fees a Wallet paid on the buys of a Position, as Polymarket recorded them; 0 in Markets that charge no fee and on fills where the Wallet was the maker (FR-4).
- **Real PnL**: Σ *s* · (*o* − *p*) over a Wallet's Resolved Positions and Slivers, minus the Own Fees on those Positions. The profit the Wallet actually kept.
- **Exit PnL**: the PnL realised on shares a Wallet sold before resolution: Σ (shares sold) · (sell price − *p*). Shown, never part of the Skill Test.
- **Simulation**: one replay of a Wallet's Resolved Positions and Slivers in which each Outcome is drawn at random, coming true with probability equal to its Entry Price; linked bets share one draw (FR-5).
- **Luck Distribution**: the Real PnL formula applied to 10,000 Simulations.
- **p-value**: (1 + number of Simulations with PnL ≥ Real PnL) / (1 + 10,000). The chance that a trader with no edge does at least this well.
- **Verdict**: one of *Skilled (high confidence)* (p < 0.01), *Likely skilled* (p < 0.05), *No evidence of skill*, or *Not enough data* (fewer than 30 Resolved Positions). The thresholds are conventions (§10).
- **Skill Test**: the procedure that produces the Luck Distribution, p-value and Verdict for a set of Resolved Positions.
- **Seed**: the number that fixes the random draws, so a Skill Test can be repeated exactly.
- **Scan**: running the Skill Test in one go on the top Wallets (default 200) by Real PnL from Positions resolved before the Cut-off Date. How the Wallets are found and ranked is in FR-16.
- **Watchlist**: the Wallets from a Scan rated *Skilled (high confidence)* on everything the Scan fetched for them: the before part and the after part together ("whole history" below means this, not the Wallet's whole life on Polymarket). Private: stored only on the machine running the app.
- **Minimum Luck Passes**: the fewest Wallets expected to pass a Scan by luck alone: number of Wallets tested × 0.01. A floor, not an estimate: the Scan picks Wallets for high profit, so more than this pass by luck.
- **Cut-off Date**: the date that splits a Wallet's history into a *before* part (used to judge skill) and an *after* part (used to check it). The before part is the Positions that resolved before the date; the after part is the Positions opened on or after it. A Position opened before the date and resolved after it is in neither part. It is chosen when a Scan starts.
- **Before-Cut-off Passers**: the Wallets from a Scan rated *Skilled (high confidence)* when the Skill Test uses only the before part. Unlike the Watchlist (whole history), nothing after the Cut-off Date decides who is in this group.
- **Comparison Group**: the other Wallets from the same Scan, rated on the same before part: those rated *Likely skilled* or *No evidence of skill*. Wallets with *Not enough data* in the before part are in neither group.
- **Hold-up Test**: the Skill Test run on the pooled after part, as Resolved Positions, of the Before-Cut-off Passers (and, the same way, of the Comparison Group).
- **Minimum After-bets**: the fewest Resolved Positions in its after part that a Wallet needs to be counted in the Hold-up Test and the Copy Pool: 10. `[ASSUMPTION: 10]`
- **Copy Delay**: how long after a Wallet's buy a follower buys: 1, 5 or 30 minutes.
- **Main Copy Delay**: 5 minutes, fixed before any data is looked at. Only this delay gives a Copy Verdict (FR-18b).
- **Spread Allowance**: half a cent (0.005) added to the price a follower pays, because the recorded price history is the midpoint between what buyers and sellers paid, not a price a follower can trade at. `[ASSUMPTION: 0.5 cent]`
- **Follower Fee**: the fee Polymarket would charge the follower for buying *s* shares at *p*<sub>delay</sub> in that Market: *s* · rate · *p* · (1 − *p*), with the rate and exponent from the Market's fee schedule; 0 in Markets that charge no fee.
- **Follower PnL**: Σ (*s* · (*o* − *p*<sub>delay</sub>) − Follower Fee), summed over each buy fill of the Position, where *s* is that fill's share of the shares held at resolution and *p*<sub>delay</sub> is the market price of the same outcome one Copy Delay after that fill, plus the Spread Allowance (capped at 1). A Position bought in 12 fills is copied 12 times, each at its own time.
- **Follower Return**: a Wallet's Follower PnL at one Copy Delay ÷ the money the follower spent on the same Positions, Σ (*s* · *p*<sub>delay</sub> + Follower Fee). Profit per dollar, so Wallets of very different sizes can be compared.
- **Copy Sample**: for each Wallet, the Resolved Positions in its after part that the Copy Test prices: all of them if there are at most 100, otherwise 100 drawn at random with the Seed, by the same rule for every Wallet. `[ASSUMPTION: 100 Positions per Wallet]`
- **Copy Pool**: every Wallet from the Scan with at least the Minimum After-bets Resolved Positions in its Copy Sample that have a recorded price at the Main Copy Delay. The Before-Cut-off Passers who meet this rule are in it too.
- **Random Group Check**: the luck check on the Copy Test: the Passers' average Follower Return compared with that of 10,000 random groups of the same size from the Copy Pool (FR-18b).
- **Copy Test**: Follower PnL and Follower Return at each Copy Delay over the Copy Sample of each Before-Cut-off Passer, plus the Random Group Check. Paper only.
- **Domain**: the category of a Market: politics, sports, crypto, macro or other.
- **Domain Verdict**: a Verdict from the Skill Test on only one Domain's Resolved Positions, with the Bonferroni correction (FR-20).
- **Sample Dataset**: Wallet histories on both sides of a default Cut-off Date, Market data, and the recorded prices around each buy fill, saved in the repository so the app can run without the network (FR-12).
- **Synthetic Wallet**: a made-up Wallet with a known correct Verdict, generated by script with a fixed Seed. Types: see the table under FR-13.
- **Offline Mode**: the app reads only the Sample Dataset and makes no network calls.
- **Mock LLM Mode** (stage 3): the language model is replaced by tag rules (a fixed map from Polymarket's event tags to Domains) and text templates, so no key is needed.
- **Flag**: a label marking a Wallet as a likely bot or market maker (stage 3).
- **Explanation**: a short plain-language text describing a Wallet's Verdict (stage 3).

## 4. Features

### 4.1 Wallet Lookup and Data (stage 1)

**Description:** The user enters a Wallet address. The app fetches the Wallet's trades and positions plus the Markets they belong to, stores them in the database, and builds the Wallet's Positions. Realizes UJ-1, UJ-2.

#### FR-1: Look up a Wallet
The user can enter a Wallet address on the start page and get its result page. Realizes UJ-1.
- An address that is not a valid address format shows an error message and fetches nothing.
- A valid address with no Polymarket history shows "No Polymarket history found for this address", with the hint to use the address shown on the Polymarket profile page.
- The address is the one on the Polymarket profile page (the proxy wallet). An address from a wallet app may show no history.

#### FR-2: Fetch and cache data
The system fetches a Wallet's trades, positions and the related Markets from Polymarket's public APIs and stores them in the database.
- A second lookup of the same Wallet within 24 hours uses stored data and makes no network call. `[ASSUMPTION: 24 hours is fresh enough]`
- If Polymarket does not answer, the page says so and offers the stored data if any exists.
- Requests are paced so the app never exceeds Polymarket's published rate limits.

#### FR-3: Build Positions
The system combines a Wallet's fills into Positions and marks which are Resolved Positions.
- Several buys of the same outcome in the same Market become one Position, with Entry Price = the share-weighted average price.
- Positions come from both the closed and the open positions; both are required, because a losing Position that was never redeemed is worth 0 and appears only among the open ones. A loss counts like any other.
- A Market is resolved when the Market data says it is closed, its outcome prices are exactly 0 and 1, and it has a resolution time. The resolution time always comes from the Market data, never from the Wallet's own rows. A Market that resolved any other way (for example 50-50) is left out as "unclear resolution".
- The shares held at resolution are the Wallet's bought shares minus its sold shares, from its own buys and sells. Redemptions are never used to count shares, because an unredeemed loser has none.
- Besides fully sold Positions, a Position is left out of the Skill Test, counted, and shown with its reason when: the Wallet split, merged or converted shares in that Market; the token appears only in the activity rows; its shares held are not between 0 and the shares bought; the two sources disagree on shares bought by more than 1% `[ASSUMPTION]` (the size of the gap is stored); its Market has an unclear resolution; or the Wallet's history could not be read in full (FR-16). The same rules apply before and after the Cut-off Date.
- A Position fully sold before resolution is not a Resolved Position. It is counted and shown, but left out of the Skill Test.
- A Position partly sold down to a Sliver is not counted as a bet: not in the number of Resolved Positions, the 30 minimum, the held count (N of M) or the left-out counts. Its money stays in Real PnL and in every Simulation.
- A Position partly sold before resolution enters the Skill Test with the shares still held at resolution, at the original Entry Price. `[ASSUMPTION: testing the shares still held, at the original Entry Price, is a fair way to treat a partly sold Position]` The shares sold count toward Exit PnL.
- **Known limit (decided):** which Positions reach resolution is the trader's choice and can depend on how the price moved after the buy. A trader who sells losers early and keeps the rest looks better in the Skill Test than they are. v1 accepts this and makes it visible (FR-11); handling it in the test is deferred to v2 (§6.2).

### 4.2 Skill Test (stage 1)

**Description:** The core of the product: the method in the brief's *The Skill Test* section, implemented as a separate module with no network or web code in it, so it can be tested on its own. Realizes UJ-1, UJ-3.

#### FR-4: Real PnL
The system computes Real PnL from a Wallet's Resolved Positions and Slivers.
- Own Fees are checked against the Market's fee schedule. A fee that fails the check is not counted (it counts as 0) and is shown on the Verdict card (FR-11).
- For three Wallets in the Sample Dataset, Real PnL equals a reference calculation stored with the tests (to the cent), made from the PRD's definitions and the Wallet's data alone, without the app's code. At least one of the three paid trading fees, and its reference calculation subtracts them.

#### FR-5: Luck Distribution and p-value
The system runs 10,000 Simulations and computes the p-value.
- Bets that depend on the same result share one random draw: all Positions in one Market (also across Wallets, in the Hold-up Test), the Markets of one negative-risk event (only one can win), and a detectable ladder (same underlying, same resolution date). Each Position still comes true with probability equal to its Entry Price; linked bets win and lose together instead of counting as separate evidence.
- The Own Fees are charged in every Simulation exactly as in the real result, so they lower both by the same amount and the p-value does not change.

Checks:
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
- Below 10, N is rounded to a whole number, so the phrase never shows a decimal: 0.45 is shown as "about 1 time in 2", 0.27 as "about 1 time in 4", 0.11 as "about 1 time in 9".
- When no Simulation reached the Real PnL (p-value 1/10,001), the card says "fewer than 1 time in 10,000", never "about 1 time in 10,000": 10,000 Simulations cannot show a smaller chance than that.
- When the p-value is above 0.5, the card says "more than half the time".

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
- when a Wallet has more than 2,000 Resolved Positions in the part tested, the line "Based on the latest 2,000 of N Resolved Positions; older results are not included." For the after part the line says "first 2,000" instead; a Watchlist result says it rests on the two windows around the Cut-off Date, and that Positions bought before the date and resolved after it are in neither;
- how many Positions were left out of the test, for each reason (FR-3), and, when more than 10% `[ASSUMPTION]` of the Positions were left out for any reason together, a plain sentence that only part of the Wallet's activity was judged;
- how many fees failed the check against the Market's fee schedule, with their recorded total (FR-4);
- when more than 20% `[ASSUMPTION]` of the tested Positions sit in an event with another tested Position whose link the app cannot detect, a note that some bets may depend on each other and the result can look stronger than it is;
- the Seed the result was computed with (also on the Scan, Hold-up Test and Copy Test pages);
- a short fixed note on the test's limits (long shots tend to be overpriced; the Verdict covers only bets held to resolution, so early exits are not measured and can make a Wallet look better or worse than it is; Wallets are often looked up because they already looked good, and picking by results makes luck look more like skill) and that this is not financial advice.

Checks:
- The stop-loss Synthetic Wallet (FR-13) shows the warning. A Wallet with Exit PnL ≥ 0, or with no early sales, shows none.

### 4.4 Offline Running and Test Data (stage 1)

**Description:** Lets the examiner run and check the app without our keys or a working Polymarket API. Realizes UJ-3.

#### FR-12: Sample Dataset
The repository contains stored data for about 10 real Wallets (a mix of Verdicts, including at least one *Not enough data*) and the Synthetic Wallets, each with its Positions and the recorded price history around each buy fill. Large synthetic groups (the 1,000 coin-flippers) are not committed: loading the Sample Dataset regenerates them from the generator's fixed Seed. The committed Sample Dataset stays under 50 MB `[ASSUMPTION]` (raised from 25 MB by Edvard, 2026-11-23, Story 2.6: the 10 real Wallets' needed rows come to about 35 MB), checked by a test, so cloning needs no extra tools such as Git LFS.
- The real Wallets' price history is captured as early as possible and kept for good, because one-minute prices for past dates may stop being available (addendum).
- The Sample Dataset has one default Cut-off Date, 1 July 2025 (§9 Q6). The real Wallets have Positions both before and after it, so the Hold-up Test and Copy Test run offline with that date. Online, the user can choose any date (FR-16).
- Stated limitation, one-way: for the two largest real Wallets (0xd218e4…, 0x63d43b…), the captured activity after the Cut-off Date stops at the 150,000-row cap (12 and 20 August 2025), so 808 and 418 of their 2,000 after-part Positions may miss later buy fills and are left out under the cap rule (FR-3). This cannot be repaired later: if the cap rule changes, the missing price windows can no longer be fetched once one-minute prices for those dates are gone. For the lookup window (the latest 2,000 Positions, Story 2.6) the capture holds too little for three Wallets: those two, and 0x729806…, whose activity before the Cut-off Date also stopped at the cap (from November 2024). Each window's trades start before what the capture holds, so every Position is "not fully read" and the three show *Not enough data* offline (recorded in `docs/real-wallets.md`, 2026-11-23).

#### FR-13: Synthetic Wallets
A script generates the Synthetic Wallets in the table below from a fixed Seed. It also generates the price paths: forecaster, slow drift towards the Outcome over hours; speed trader, a jump to the Outcome seconds after the buy; coin-flippers, no edge. Running it twice gives identical files.

| Synthetic Wallet | How it is built | Expected result | Used by |
|---|---|---|---|
| Hand-check | 10 bets at 50¢, all won | Only "all 10 won" beats or ties it, so the exact answer is 1/1024 ≈ 0.001; the simulated p must land between 0.0003 and 0.002. Engine-level test, bypassing the 30-bet minimum | FR-5 |
| Coin-flipper | 1,000 wallets of 100 bets each, random prices between 10¢ and 90¢, outcomes drawn at those prices | *Likely skilled* or better for at most 7% of wallets (5% expected by design), *Skilled (high confidence)* for at most 2% | FR-5, FR-17, FR-18b, FR-22, UJ-3 |
| Favourite-buyer | 100 bets at 90¢, wins 90 | *No evidence of skill* | FR-5 |
| Sharp trader | 100 bets at 50¢, wins exactly 70 | *Skilled (high confidence)* (exact binomial p ≈ 0.00004) | FR-5, FR-16, FR-22, UJ-3 |
| Thin wallet | 29 resolved bets | *Not enough data* | FR-6, FR-10 |
| Steady sharp (stage 2) | 100 bets at 50¢ winning 70 before the cut-off, the same after | Passes before; still *Skilled (high confidence)* on its after-cut-off bets | FR-16, FR-17 |
| Lucky streak (stage 2) | The coin-flippers that happen to pass before the cut-off; after it, outcomes drawn at fair odds | Pass before by construction; pooled after-cut-off bets show *No evidence of skill* | FR-17 |
| Forecaster (stage 2) | Buys at 50¢, wins 70%; the price drifts slowly towards the outcome over hours | Copy-test profit stays positive at a 30-minute delay | FR-16, FR-18a, FR-18b |
| Speed trader (stage 2) | Buys at 50¢ seconds before the price jumps to the outcome | Copy-test profit is zero or negative at a 5-minute delay | FR-16, FR-18a |
| Stop-loss trader (stage 1) | 100 bets at 50¢ with no edge; bets whose price has fallen are sold before resolution, the rest are held to resolution. The price moves fairly and the stop is 25¢: 67 bets fall to 25¢ and are sold there (17 of them in Markets their side later won), 33 are held and all win, so the total is about zero (−$25) | The card shows how many bets were held, the negative realised PnL of the sold ones, and a visible warning next to the verdict. The verdict itself may read skilled: that is the known limit | FR-11 |
| Market maker (stage 3) | Many small buys and sells on both sides of the same markets, flat inventory | Flagged as likely market maker | FR-22 |
| Split-domain trader (stage 3) | 60 bets at 50¢ in crypto, exactly 42 won; 60 bets at 50¢ in sports, exactly 30 won | Crypto *Skilled (high confidence)*, sports *No evidence of skill* | FR-20 |

#### FR-14: Offline Mode
One setting makes the app use only the Sample Dataset.
- In Offline Mode, every Wallet in the Sample Dataset can be looked up with the network disconnected.
- Looking up a Wallet outside the Sample Dataset in Offline Mode shows "Not available offline".
- Offline Mode never calls the language model, even when a key is set: it uses the stored Domain labels and the templates. It keeps its data apart from the data of online runs, so an online lookup never appears offline and sample data never appears online.

### 4.5 Is Skill Worth Following? (stage 2)

**Description:** Answers the follower's question: which wallets are worth following, does their skill last, and does it survive being copied late. Everything here is computed on recorded data; nothing places orders. Built in three milestones, 2a to 2c, with a defined minimum (§6.1). Realizes UJ-4.

#### FR-16: Scan and Watchlist (milestone 2a)
The user chooses a Cut-off Date, starts a Scan of the top Wallets by Real PnL (after their own fees) made before that date (default 200), and sees the Watchlist, sorted by p-value, with the Minimum Luck Passes shown next to it. `[ASSUMPTION: 200 Wallets is a sensible default Scan size]`
- Only Positions resolved before the Cut-off Date count toward the profit that ranks the Wallets, so nothing after the date decides who is scanned.
- The candidate Wallets are every Wallet that held a Position in a chosen set of Markets resolved before the Cut-off Date, closed or still held (which includes unredeemed losers), so Wallets that later went quiet or lost money are in the list too. Polymarket's leaderboard is not used: it has no date setting and shows only today's survivors.
- The funnel: the Markets resolved in the 90 days before the Cut-off Date, top 100 by volume, chosen without looking at outcomes; from their candidates, a shortlist of 3 × the Scan size by a quick profit estimate that also counts unredeemed losses; then each shortlisted Wallet's full data, ranked by Real PnL. `[ASSUMPTION: 90 days, 100 Markets, 3 ×]` The Scan page states the population tested ("Markets resolved in the 90 days before the Cut-off Date, top 100 by volume"), how many of the 100 Markets were used, and that the shortlist estimate is approximate.
- A Market whose list could not be read in full gives no candidates and is shown as "not used: partial", because a partly read list leans towards winners or losers. A Wallet whose history could not be read in full is kept, marked "not fully read" everywhere it is counted (ranking, Watchlist, Passers, Hold-up groups, Copy Pool), and its unread Positions are left out (FR-3). Only Polymarket not answering stops a Scan; it can then be resumed.
- A Wallet with more than 2,000 Resolved Positions before the Cut-off Date is not left out: it is ranked, and Skill Tested, on its latest 2,000 of them (those resolved last before the date), and its Verdict card says so (FR-11). Its after part is likewise capped at the first 2,000 after the date (FR-17). This is a stated limitation: older results do not count, so such a Wallet can look better or worse than its whole history would show. `[ASSUMPTION: 2,000 Positions]`
- A different Cut-off Date means a new Scan, because the list of Wallets changes with it. Stored Wallet data is reused (FR-2), so only Wallets not seen before are fetched.
- Every result names the set of Positions it was computed on, so a Watchlist row and the Verdict page it opens show the same result.
- The page shows progress during a Scan; an interrupted Scan resumes without re-fetching finished Wallets.
- The Watchlist is stored in the database with the Scan date and its Cut-off Date, and is never sent anywhere.

Checks:
- A Scan of the Sample Dataset in Offline Mode, with its default Cut-off Date (FR-12), puts at least the sharp-trader, steady-sharp, forecaster and speed-trader Synthetic Wallets on the Watchlist.
- A Scan of 200 Wallets shows "at least about 2 of 200 would pass by luck alone, probably more, because these Wallets were picked for high profit".

#### FR-17: Hold-up Test (milestone 2b)
The user sees the Hold-up Test result, for the Cut-off Date the Scan was started with (FR-16), for the Before-Cut-off Passers and for the Comparison Group: Resolved Positions in the after part, Real PnL, p-value and Verdict for each group.
- Both groups are picked from the same Scan by the same rule, using only the before part, and both are tested on the after part. No Position from after the Cut-off Date decides who is in either group, nor which Wallets are in the Scan itself (FR-16). A Wallet that passes only when Positions from after the Cut-off Date are included is not in the Before-Cut-off Passers. Each Wallet is in at most one of the two groups.
- A Wallet's after part is its first 2,000 Positions in resolved Markets bought on or after the Cut-off Date, the same cap as the before part, and the page says so.
- A Wallet counts in its group's result only if it has at least the Minimum After-bets Resolved Positions in the after part, by the same rule in both groups: Wallets that stop betting after the Cut-off Date are dropped in both, never kept in one and dropped in the other. Each group's result shows Wallets in the group, Wallets dropped for too few after bets, Resolved Positions counted, and how many of its Wallets are "not fully read" (FR-16).
- If the share of Wallets dropped differs by more than 20 percentage points between the two groups, the page says so next to the results: "More Wallets were dropped in one group than in the other. Wallets that stop betting may be the ones that lost, so the group with more dropped Wallets may look better than it is." `[ASSUMPTION: 20 percentage points is "way more"]`
- The pooled after part is simulated with linked bets sharing one draw (FR-5): Passers who bet in the same Markets are not counted as independent evidence.
- A group with fewer than 30 Resolved Positions in the after part shows *Not enough data*.

Checks:
- The steady-sharp Synthetic Wallets are rated *Skilled (high confidence)* on their after part.
- The lucky-streak Synthetic Wallets (coin-flippers that passed before the Cut-off Date) are rated *No evidence of skill* on their after part.
- A planted example with 60% dropped in one group and 10% in the other shows the dropped-share message; equal shares show none.
- 7 coin-flipper Passers holding the same side of the same 40 Markets get p < 0.05 in at most 7% of 1,000 runs.

#### FR-18: Copy Test (milestone 2c)
For each Before-Cut-off Passer, the Copy Test shows what a follower copying its buys late would have made (FR-18a), and checks the Passers as a group against random picks from the same Scan (FR-18b), on recorded prices (FR-18c). The page shows the Random Group Check first, then the per-Wallet numbers.

##### FR-18a: Follower PnL and Follower Return
For each Before-Cut-off Passer, over its Copy Sample, the system shows Follower PnL and Follower Return at each Copy Delay next to the Wallet's own Real PnL over the same Positions.
- Every buy fill is copied at its own time plus the Copy Delay. A Position with no recorded price at a Copy Delay is left out of that delay's sum, and the count of left-out Positions is shown.
- Every Wallet is priced on its Copy Sample; the page shows "priced N of M after Positions" and says the numbers rest on a sample. A Wallet with 250 after Positions shows "priced 100 of 250"; the same Seed gives the same sample.
- Follower PnL includes the Spread Allowance. The page states its limits: the allowance comes from large liquid Markets, where the gap between buyers and sellers had a median of 1 cent and a 90th percentile of 3 cents; thin Markets were not measured and may cost more; and the follower's own price impact is ignored. Follower PnL is therefore still an upper bound.
- The per-Wallet numbers are marked as not luck-checked; only the Random Group Check is. The 1- and 30-minute results are marked as extra information, with no Copy Verdict.

Checks:
- The speed-trader Synthetic Wallet has Follower PnL ≤ 0 at a 5-minute Copy Delay.
- The forecaster Synthetic Wallet has Follower PnL > 0 at a 30-minute Copy Delay.
- For a hand-made set of three Positions in a Market with a fee, including the Spread Allowance and a Position bought in more than one fill, Follower PnL and Follower Return equal a reference calculation stored with the tests (to the cent), made from the PRD's definitions and the set's data alone, without the app's code.

##### FR-18b: Random Group Check
At the Main Copy Delay, the Passers' score is the average Follower Return of the Passers in the Copy Pool, each Wallet counting equally. The system draws 10,000 random groups of the same size from the Copy Pool (no Wallet twice in one group) and scores each the same way. Copy p-value = (1 + number of random groups scoring ≥ the Passers) / (1 + 10,000). Copy Verdict: *Beat random picks* (Copy p-value < 0.05), *No better than random picks*, or *Not enough data* when no Passer is in the Copy Pool or fewer than 1,000 different groups of that size can be drawn from it. `[ASSUMPTION: 1,000]` It runs with a Seed, like the Skill Test.
- Only the Main Copy Delay gives a Copy Verdict: testing three delays would give luck three chances to pass.
- The page shows the Copy p-value as "random groups did as well in X% of draws". When no random group scores as well as the Passers, it says "no random group did as well in 10,000 draws", never a percentage (the floor of 1/10,001 would read as a false "0.01% of draws").
- The page shows how many of the Passers' Copy Sample Markets are shared by two or more Passers.

Checks:
- A planted Scan of 10 forecaster Passers and 100 coin-flipper Wallets (copy prices give the coin-flippers no edge) gets a Copy p-value < 0.01.
- Across 1,000 planted Scans of 110 coin-flipper Wallets, each with 10 of them picked at random as the Passers, the Copy p-value is < 0.05 in at most 7%.
- Shared-Markets gate: across 1,000 planted Scans in which 10 coin-flipper Passers hold the same side of the same 40 Markets, the Copy p-value is < 0.05 in at most 7%. If the gate fails, the Random Group Check must be changed to account for shared Markets before a Copy Verdict is shown; that is a plan change.
- A Copy Pool of 6 Wallets with 3 Passers (20 possible groups) shows *Not enough data*.
- The same data with the same Seed gives the identical Copy p-value.

##### FR-18c: Price history and fallback
The Copy Test prices come from Polymarket's recorded price history at one-minute grain.
- The app never silently uses coarser prices: a buy with no one-minute price is left out of that delay and counted (FR-18a). Fetched price history is kept for good.
- One-minute prices for past dates may stop being available (addendum), so the source is checked daily.
- **Fallback:** if one-minute prices for the default Cut-off Date can no longer be fetched when the real-data run is made (SM-5), the Copy Test runs on a frozen insurance pool of 50 Wallets for that date, picked by a rule written down and committed before the capture (`spike/INSURANCE-RULE.md`) and captured with every after-part buy fill's price window. Passers, Copy Samples and the Random Group Check are computed by the app as usual, and the page and the README state the limits: a pool of 50 fixed in advance, not the app's Scan; the pool was ranked by the spike's estimate, not the app's final Real PnL; and with fewer than 2 Passers the Copy Verdict is *Not enough data*, reported as it comes out.

### 4.6 Language Model and Domains (stage 3)

**Description:** Splits the Skill Test by Domain so the user sees where the edge is. The language model behind it can be replaced by Mock LLM Mode, so stage 3 also runs with no key. Realizes UJ-5.

#### FR-15: Mock LLM Mode
One setting replaces the language model with tag rules (Domain) and templates (Explanation). It is on by default when no key is set. The ID is kept from when this requirement sat in stage 1.
- With no key set, FR-19 and FR-23 run in Mock LLM Mode and their tests pass.
- The tag rules give each Market exactly one Domain from its event's tags, settling overlaps by Edvard's Domain definitions (FR-19). A Market whose tags are all off the map gets *Other*.

#### FR-19: Classify Markets
The system assigns each Market a Domain using the language model (or Mock LLM Mode).
- Each Market is classified once; the label is stored with its source (model name or tag rules) and date, and reused. Classifying again is a deliberate action, never a side effect, because the model's answers can differ between runs.
- **Domain definitions and hand labels.** Edvard defines the five Domains himself, one line each saying where the overlap cases go (the AI suggests none). In the same sitting he labels a set of 50 Markets blind: he sees only each Market's question, with no tag-rule label, model label, category or tag field. Definitions and labels are committed together before either labeller runs on these 50, and never edited afterwards. No tag is read for the events behind the 50 before that commit. The model's prompt quotes the definitions word for word, and the tag rules are written from them.
- **The 80% gate.** The language model agrees with the hand labels on at least 80% of the 50 Markets. `[ASSUMPTION: 80% is a sensible bar]` If the default model misses it, a larger model is tried and both results are reported. The tag rules of Mock LLM Mode are checked on other Markets than these 50.
- **Failures.** A Market gets at most 3 tries. An answer that is not one of the five Domains is never stored and counts as a failure. If any of a Wallet's Markets is still unlabelled, the Domain table is replaced by "Domains are not available: the language model did not answer."; no Market is put in a Domain it was not labelled with.
- **Cost.** One model call per Market, stored and reused. The README states how many calls the Sample Dataset needs and an estimate of their cost.

Checks:
- A planted model answer that is not one of the five Domains is not stored, and the Wallet's Domain table shows the message above.

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
- If the model does not answer, the template text is shown.

#### FR-24: Explanation check
Before an Explanation is shown, code checks that it names the same Verdict and the same odds phrase as the card (FR-8), and contains none of the banned or avoided words. An Explanation that fails is replaced by the template text.
- The words are listed once, in the UX specification (`EXPERIENCE.md`, *Voice and Tone*: the banned words and the "also avoided" words). The code keeps them as one list, and the FR-24 test uses the whole list.
- Each replacement is counted, so the replacement rate (SM-7) can be reported.

Checks:
- A planted Explanation with a wrong Verdict is replaced by the template.
- For each word on the list, a planted Explanation containing it is replaced by the template.

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
- **Stage 2:** FR-16 to FR-18, built in three milestones, each done when its checks pass and the README is updated:
  - **2a Scan and Watchlist** (FR-16): FR-16's checks pass, including the offline Scan of the Sample Dataset that puts the four expected Synthetic Wallets on the Watchlist.
  - **2b Hold-up Test** (FR-17): FR-17's checks pass, and the README reports the offline Hold-up result for the 10 real Sample Wallets whichever way it comes out, with its limits (only 10 Wallets, picked for the Sample Dataset, not a full Scan).
  - **2c Copy Test** (FR-18a to FR-18c): their checks pass.
  - **Minimum (good enough): 2a + 2b, offline.** Everything they need runs on the Sample Dataset. The Copy Test (2c) and a live real-data Scan (SM-5) come on top if time allows; whatever is not reached is stated in the README with the reason.
- **Stage 3:** FR-15 and FR-19 to FR-24 (Mock LLM Mode, Domains, Flags, Explanations). Trimmed first if time runs short. **Parked, not deleted** (Edvard, 2026-11-20): stage 1 was not done by the 20 November checkpoint, so stage 3 is not started now; it is picked back up if all of stage 2, the Copy Test (2c) included, is done before the code freeze on 1 December.

Each stage ends with all its tests passing and the README updated, so the project is deliverable after any stage, or after the stage 2 minimum.

### 6.2 Out of Scope for v1

- Positions fully sold before resolution in the Skill Test (shown with their Exit PnL, not tested). Deferred to v2.
- Sybil-cluster detection. Deferred to v2: the feature most likely to blow the timeline.
- Kalshi, Manifold and other venues. Deferred to v2.
- A measured luck-pass rate for top-by-profit picks: running the same top-by-profit selection on coin-flipper Synthetic Wallets and showing the share that pass, next to the Minimum Luck Passes. Revisit only if time allows after stage 2.

## 7. Success Metrics

**Primary**
- **SM-1**: All Skill Test correctness tests pass (hand-check, coin-flipper, sharp trader, favourite-buyer, thin wallet, reproducibility, independently calculated Real PnL). Validates FR-4 to FR-7.
- **SM-2**: The examiner can run the app and the tests from the README with no network and no keys. Validates FR-12 to FR-14.

**Secondary**
- **SM-3**: A lookup of a Wallet with up to 1,000 Resolved Positions returns a Verdict within 10 seconds on an ordinary laptop (stored data). Validates FR-5.
- **SM-4**: The Hold-up Test and Copy Test synthetic checks pass (steady sharp vs lucky streak; forecaster vs speed trader; Random Group Check on planted Scans). Validates FR-17, FR-18.
- **SM-5**: A Hold-up Test and a Copy Test have been run on a live real-data Scan, and the result is reported in the README and the reflection report, whichever way it comes out. Validates FR-16 to FR-18. Beyond the stage 2 minimum (§6.1): if it is not reached, the README says so, and the minimum's 10-Wallet Hold-up result is the only real-data result.
- **SM-6**: Stage 3 Domain labels agree with hand labels on at least 80% of 50 Markets. Validates FR-19.
- **SM-7**: The replacement rate: the share of Explanations that fail the Explanation check and are replaced by the template, counted over the Sample Dataset's Wallets and Domain Verdicts and reported in the README. In Mock LLM Mode it should be 0 (a template that fails the check is a bug). With a real model it is expected to be above 0, and the number is reported whichever way it comes out. No target. Validates FR-24.

**Counter-metrics (do not optimise)**
- **SM-C1**: The share of real Wallets rated *Skilled (high confidence)*. A test that calls more wallets skilled is not better; the Yale SOM study found only ~3% of accounts show skill (source: `addendum.md`). Counterbalances SM-1.
- **SM-C2**: The size of the Watchlist and how good the Hold-up and Copy results look. A real result showing that skill does not last, or cannot be copied, is a valid outcome, not a failure. Counterbalances SM-5.
- **SM-C3**: How confident or persuasive Explanations sound. They must never claim more than the test shows. Counterbalances SM-7.

## 8. Cross-Cutting Requirements

- **Runnable from the README**: from a fresh clone, with one documented install tool (addendum), the app starts in at most 3 documented commands (install dependencies, load the Sample Dataset, start the app) on Windows, macOS and Linux. The README lists the prerequisites, the exact commands, the address to open, how keys are set in `.env`, and where each JavaScript file is and what it does. A CI job runs these exact commands on a fresh checkout and checks a Sample Wallet's Verdict.
- **Runs on Windows, macOS and Linux**: on every push, CI installs the dependencies and runs the test suite on all three systems, with the oldest and newest supported Python versions (addendum). The whole test suite runs with network access blocked, which also proves Offline Mode on every push. A failing run on any of them counts as a failing build.
- **Runs locally**: the app runs on the user's or examiner's laptop as a web page opened in a browser; it is not hosted publicly. `[ASSUMPTION: local only is enough; the course does not require hosting]`
- **Database**: cached Polymarket data, Domain labels, Scans and Watchlists are kept in a database (a local SQLite file is enough, nothing to install or host). Reason: course requirement.
- **Secrets**: the language-model key is read from `.env`, which is never committed; the repository contains `.env.example`.
- **Polite to Polymarket**: a lookup of a Wallet already stored makes 0 network calls (FR-2). Requests are paced at no more than 5 per second, well under Polymarket's published rate limits (addendum). `[ASSUMPTION: 5 requests per second]` The pace is one setting that can be turned down, and values above 5 per second are refused.
- **Testable core**: the Skill Test module has no network, web or language-model code, and every FR with consequences has at least one automated test.
- **Wording**: the app never uses the banned or avoided words of the UX specification (`EXPERIENCE.md`, *Voice and Tone*; for example "guaranteed", "insider", "will win") about a Wallet. The code keeps them as one list, checked by a test over every template and fixed text (FR-24).
- **Pages, navigation and accessibility**: which pages exist and how the user moves between them is specified in the UX step (`bmad-ux`), not here. It has to cover at least: lookup, Verdict result, Scan, Watchlist, Hold-up Test and Copy Test. Two rules hold from now on: the Verdict is always shown as text, never by colour alone; and the luck chart (FR-9) has a text alternative that states the Real PnL and the odds phrase from FR-8.

## 9. Open Questions

**Remaining open: none.** Every question below is settled. The full history of each, with the evidence, is in `decision-log.md`.

1. ~~Which Polymarket data sources give a Wallet's positions, fees, splits, merges and sells, and which address do they use?~~ **Closed (data spike and architecture, 2026-10-21).** Answers in FR-1, FR-3 and the addendum.
2. ~~Which public source lists the top Wallets by profit for a Scan?~~ **Closed (2026-10-16 to 2026-10-23).** None that fits: a Scan ranks only on profit from Positions resolved before the Cut-off Date, from the app's own candidate list (FR-16). Polymarket's leaderboard is used neither for Scans nor to pick the Sample Dataset.
3. ~~Does Polymarket have minute-level price history for resolved Markets, far enough back for the Copy Test?~~ **Closed (2026-10-21).** Yes, from mid-2023. The Copy Delays stay as they are; the request cost is handled by the Copy Sample and the 2,000-Position cap (FR-16, FR-18).
4. ~~Is the app acceptable to examine in Mock LLM Mode?~~ **Closed (Edvard, 2026-10-16): yes**, as long as the README says exactly how to set a key.
5. ~~Which 10 real Wallets go into the Sample Dataset?~~ **Closed (Edvard, 2026-10-23):** 10 Wallets from the Scan funnel for the default Cut-off Date, picked on the before part only. Method and list: `spike/FINDINGS.md`, *Sample Dataset pick*.
6. ~~Which Cut-off Date for the real-data Hold-up Test?~~ **Closed (Edvard, 2026-10-23): 1 July 2025**, the Sample Dataset's one default Cut-off Date. Online, any date can be chosen.
7. ~~A measured luck-pass rate for top-by-profit picks~~ was a "maybe later" idea, not a question. **Moved to §6.2** (2026-11-18).

## 10. Assumptions Index

Each is a starting value, not measured. Edvard confirms or changes it with real data; a change goes in the memlog first.

- §4.1 FR-2: stored data counts as fresh for 24 hours.
- §3, §4.1 FR-3: a gap above 1% between the two sources' shares bought leaves a Position out.
- §3 Sliver, §4.1 FR-3: less than 1% of the bought shares (and fewer than 1 share) left at resolution makes a Position a Sliver, not a counted bet.
- §4.1 FR-3: partly sold Positions enter the Skill Test with the shares held at resolution, at the original Entry Price.
- §4.3 FR-11: more than 10% of Positions left out gets a plain sentence; more than 20% in events with undetected links gets a note.
- §4.4 FR-12: the committed Sample Dataset stays under 50 MB (25 MB until 2026-11-23).
- §4.5 FR-16: 200 Wallets is a sensible default Scan size.
- §4.5 FR-16: the Scan funnel uses Markets resolved in the 90 days before the Cut-off Date, the top 100 by volume, and a shortlist of 3 × the Scan size.
- §4.5 FR-16, FR-11: a Wallet with more than 2,000 Resolved Positions is ranked and Skill Tested on its latest 2,000.
- §3, §4.5 FR-17: a Wallet needs at least 10 Resolved Positions in the after part to count in the Hold-up Test (Minimum After-bets).
- §4.5 FR-17: a difference of more than 20 percentage points in the share of Wallets dropped between the two groups is "way more" and gets a message.
- §3, §4.5 FR-18: the Copy Sample is at most 100 after Positions per Wallet.
- §3, §4.5 FR-18a: the Spread Allowance is half a cent (0.005) per share; measured in large liquid Markets only.
- §4.5 FR-18b: the Random Group Check needs at least 1,000 different possible groups to give a Copy Verdict.
- §4.6 FR-19: 80% agreement with hand labels is a sensible bar for Domain classification.
- §4.7 FR-22: Flag rules (at least 2 of 3: both outcomes in at least 30% of Markets; sold at least 80% of shares bought; median buy-to-sell time under 1 hour) are starting values, to tune on the synthetic market maker.
- §4.7 FR-23: an Explanation of at most 60 words is enough.
- §8: requests are paced at no more than 5 per second.
- §8: the app runs locally on the user's or examiner's laptop as a web page; it is not hosted publicly.

**Conventions** (chosen by statistical habit, not measured, and not tuned to the data):
- §3, FR-6: at least 30 Resolved Positions for a Verdict.
- §3, FR-6: p < 0.01 for *Skilled (high confidence)* and p < 0.05 for *Likely skilled* (and p < 0.05 for *Beat random picks*, FR-18b).
- §3, FR-5: 10,000 Simulations (and 10,000 random groups, FR-18b).
