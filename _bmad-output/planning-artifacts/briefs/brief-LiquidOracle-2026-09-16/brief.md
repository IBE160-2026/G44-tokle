---
title: "Product Brief: LiquidOracle"
status: final
created: 2026-09-16
updated: 2026-10-14
---

# Product Brief: LiquidOracle

> **Revision 2026-10-12**, in response to the course feedback of 2026-10-06 (`tilbakemelding-product-brief.md`):
> - Success Criteria rewritten as testable, functional criteria.
> - The skill test is now specified precisely (new section *The Skill Test*). It changed from shuffling the buy/sell sequence to simulating outcomes at the market's own prices, because the new version has answers that can be checked by hand.
> - New section *How We Know the Test Is Right*: synthetic wallets with known answers.
> - New section *Running Without Keys or Live APIs*: a local sample dataset and a mock mode for the language model.
> - v1 split into three stages, each a working app.
> - One primary user; the user experience is described.
> - The claim that an in-app AI component is required for the grade is removed. The AI features stay because they add value for the user.
>
> **Revision 2026-10-12 (2)**, the student's decision in the same session (`docs/ai-logs/2026-10-12-brief-revision-and-prd.md`):
> - A new stage 2 answers the follower's real question, whether following skilled wallets pays. It adds a scan of the top wallets into a private watchlist, a hold-up test (does skill found before a cut-off date last after it?) and a paper copy test with delays (what would a follower who arrives 1, 5 or 30 minutes late have made?). New section *Is Skill Worth Following?*
> - Market domains, bot flags and explanations move to stage 3.
> - Placing real trades stays out of the project; the copy test is paper only.
>
> **Revision 2026-10-12 (3)**, after the PRD validation (`prds/prd-LiquidOracle-2026-10-12/validation-report.md`):
> - The comparison group in the hold-up test is picked the same way as the passing group, from positions resolved before the cut-off only.
> - New synthetic wallet, the stop-loss trader, and a warning on the verdict card when positions sold before resolution lost money in total.
>
> **Revision 2026-10-14 (4)**, the student's decision (`docs/ai-logs/2026-10-14-copy-test-luck-check.md`):
> - The copy test gets a luck check: the passing wallets are compared with random groups of the same size from the same scan, on profit after fees.
> - The 5-minute delay is fixed in advance as the one that decides the result; 1 and 30 minutes are shown as extra information.
> - The copy test now includes Polymarket's fees.

## Executive Summary

Prediction markets like Polymarket publish every trader's positions and PnL in the open, but raw PnL is a terrible proxy for skill. A wallet can look brilliant after one lucky binary bet, and roughly a quarter of all historical Polymarket volume is estimated to be wash trading rather than real conviction. Every existing tool (Polymarket's own leaderboard, Dune dashboards, third-party sites like polywallet.app and polymarketanalytics.com) ranks wallets by raw PnL, ROI or volume. None of them ask the harder question: *is this wallet actually good, or did it just get lucky, run a bot, or fake its numbers?*

LiquidOracle answers that question. It ingests a wallet's Polymarket trades and resolved outcomes. It then runs a statistical test of whether the wallet beat the odds that the market itself offered, more often than luck explains, in the spirit of the 2026 Yale SOM study that found only ~3% of Polymarket accounts show skill beyond chance. Stage 2 tests whether skill found this way is worth following. It scans the top wallets, checks whether the "skilled" ones kept winning after a cut-off date, and measures what a follower copying their bets a few minutes late would have made. Stage 3 splits verdicts by market domain (politics, sports, crypto, macro), flags likely bots and market makers, and uses a language model to classify markets and explain each verdict in plain language.

This is built as the deliverable for IBE160 (Programming with AI) at Høgskolen i Molde: a solo, free-choice course project delivered in this repository.

## The Problem

Traders on Polymarket who want to follow "smart money" have no reliable way to find it. Today they're stuck with:

- **Raw leaderboards** (Polymarket's own, Dune boards, polywallet.app, polycopy.app) that rank by lifetime PnL or ROI. These can't tell apart a wallet that called ten close elections through real analysis from one that made a single big bet on a coin flip and got lucky.
- **"Smart money" / "insider" labels** on third-party sites, which turn out to be simple size or PnL thresholds, not statistical inference. A large position isn't evidence of skill, just of size.
- **No visibility into fake signal.** A 2025 Columbia study found ~25% of Polymarket's historical volume (~$4.5B) is likely wash trading, spiking to ~60% per week during airdrop-farming periods on certain markets. A leaderboard that doesn't account for this is actively misleading: a top-ranked wallet may just be farming rewards, not trading with insight.
- **No answer to the follower's real question.** Even a genuinely skilled wallet is only worth following if its edge survives being copied. A follower always arrives late, and some wallets' edge is pure speed (buying in the seconds after news, before the price moves), which no follower can copy.
- **No domain granularity.** A wallet that's genuinely sharp on macro markets but mediocre on sports gets one blended score, hiding exactly what a follower needs to know: where is this wallet's edge real?

The cost is direct: traders copying "top" wallets on faith are as likely to be copying luck, bot activity or farmed volume as real skill.

## The Solution

LiquidOracle is a web app. The user pastes a Polymarket wallet address and gets a skill verdict, not just a PnL number.

**What the user sees:**

1. **A verdict card**: one of *Skilled (high confidence)*, *Likely skilled*, *No evidence of skill* or *Not enough data*, with the number of resolved bets it is based on and the wallet's PnL.
2. **The odds in plain words**: "A trader with no edge would do this well about 1 time in 300."
3. **A chart of luck**: the spread of profits a no-skill trader could have made with the same bets, with the wallet's real result marked on it.
4. **When there is too little data**: no verdict, just how many resolved bets the wallet has and how many more are needed.
5. Stage 2 adds a **Scan** page: the private watchlist of wallets that pass, how many would pass by luck alone, the hold-up result and the copy-test profit at each delay.
6. Stage 3 adds a table of verdicts per domain, bot or market-maker flags, and a short AI-written explanation.

**How it works:**

1. **Data ingestion**: pulls trade history, positions and resolved outcomes for the wallet from Polymarket's public Data API / subgraph, and caches them locally.
2. **Skill test**: compares the wallet's real profit with 10,000 simulated "no-skill" versions of the same bets (see *The Skill Test*).
3. **Scan, hold-up test and copy test** (stage 2): see *Is Skill Worth Following?*
4. **Domain-aware scoring** (stage 3): a language model classifies each market question into a domain, and the skill test runs per domain. A wallet can be "skilled in crypto markets, no signal in sports."
5. **Bot / market-maker filtering** (stage 3): behavioural heuristics (inventory skew, two-sided quoting, holding duration) flag wallets that look like automated market making or arbitrage rather than opinionated trading.
6. **Plain-language verdicts** (stage 3): a language model turns the statistical output into a short explanation. It may only restate what the test found, and this is checked (see *Success Criteria*).

## The Skill Test

**The idea.** A Polymarket price is the market's estimate of the odds: buying "Yes" at 30¢ means the market gives the outcome a 30% chance. A trader with no edge wins exactly as often as the prices they paid say they should. A skilled trader wins more often than that. The test asks how likely it is that a no-edge trader, placing the same bets, would have made at least as much as this wallet.

**The method, precisely:**

1. **Unit of analysis**: one *position*, meaning all of a wallet's buys of one outcome in one market, combined. Many small fills of one bet count as one bet, not many independent ones.
2. **Which positions count**: positions held until the market resolved. Positions sold before resolution are shown on the page but left out of the test in v1 (a known limitation; see below).
3. **The data per position**: number of shares *s*, average price paid *p* (between 0 and 1), and outcome *o* (1 if the outcome happened, 0 if not).
4. **Real profit**: PnL = Σ *s* · (*o* − *p*).
5. **No-skill world**: for each position, draw a simulated outcome that comes true with probability *p*, then compute the simulated PnL with the same formula. Repeat 10,000 times.
6. **p-value**: (1 + number of simulations with PnL ≥ the real PnL) / (1 + 10,000). This is the chance that a no-edge trader does at least this well.
7. **Verdicts**: fewer than 30 resolved positions → *Not enough data*. Otherwise p < 0.01 → *Skilled (high confidence)*, p < 0.05 → *Likely skilled*, else *No evidence of skill*.
8. **Per domain** (stage 3): the same test on each domain with at least 30 resolved positions. Testing several domains gives luck several chances, so each domain's p-value is multiplied by the number of domains tested (Bonferroni correction) before the verdict is chosen.
9. **Reproducibility**: the random generator takes a seed. The seed is stored with each result, so the same wallet with the same seed gives the same verdict.

**Why this method rather than shuffling the trade sequence.** The original brief proposed shuffling each wallet's buy/sell sequence. The feedback identified the risk that a shuffle test can look right and still be wrong, for example by shuffling the wrong thing or computing PnL differently for real and shuffled data. The simulation above has one ingredient (the price paid), one formula, and small cases that can be worked out by hand. That makes it possible to prove the implementation correct with tests.

**Known limitations, stated in the app:**
- Market prices are not perfectly fair. Long shots tend to be overpriced on prediction markets, so a wallet that mostly buys favourites can look slightly skilled.
- Positions exited before resolution are ignored in v1, so skill at timing exits is not measured. This can also flatter a wallet that sells its losers early, so the page shows how many bets were held to resolution and the realised PnL of the exited ones, and warns when that PnL is negative.
- One very large bet can dominate a wallet's PnL. The page shows the share of PnL coming from the largest position.

## Is Skill Worth Following? (stage 2)

Passing the skill test says a wallet's past results are unlikely to be luck. A follower needs two more answers: does the skill last, and can it be copied? Stage 2 measures both on paper.

1. **Scan**: run the skill test on the top ~200 wallets by profit and list those rated *Skilled (high confidence)* in a private, local watchlist. Testing 200 wallets gives luck 200 chances: at p < 0.01, about 2 pure-luck wallets are expected to pass. The page states that number next to the list.
2. **Hold-up test**: pick a cut-off date. Run the skill test using only positions resolved before it, then pool the positions that the passing wallets opened after it and run the same test on those. If the skill was real, the passing group keeps beating the odds after the cut-off; if it was luck, its later results look like chance. The same is done for a comparison group: the other scanned wallets, picked the same way (rated on positions resolved before the cut-off only, and not passing), tested on the same kind of later positions. Nothing from after the cut-off decides who is in either group.
3. **Copy test** (paper only): for each later bet of a passing wallet, look up the market price 1, 5 and 30 minutes after the wallet bought, and compute what a follower buying the same outcome at that price would have made after Polymarket's fees: Σ *s* · (*o* − *p*<sub>delay</sub>) minus the fees. A forecaster's edge survives a delay; a speed trader's disappears within minutes.
4. **Luck check on the copy test**: a profit over a few dozen copied bets can be luck too. So the passing group is compared with random groups of the same size, drawn 10,000 times from the scanned wallets. Each group is scored on its average return after fees (profit divided by money spent, so one very large wallet cannot decide the result; win rate is not used, because it can look good while a wallet loses money). The share of random groups that do as well or better is the p-value. Only the 5-minute delay decides the result. It was chosen before looking at any data, because testing three delays would give luck three chances. The 1- and 30-minute results are shown as extra information.

**Known limitations:** the copy test uses recorded market prices, not a real order book, so it ignores the spread and the price impact of the follower's own order. It is an upper bound on what a follower could make. Testing with real money is outside the project.

## How We Know the Test Is Right

The biggest risk in this project is a statistics engine that runs and produces plausible numbers but is wrong. We control that with **synthetic wallets whose correct answer is known in advance**. They are generated by a script with a fixed seed, stored in the repository, and used both as automated tests and as a demo for the examiner.

| Synthetic wallet | How it is built | Expected result |
|---|---|---|
| Hand-check | 10 bets at 50¢, all won | Only "all 10 won" beats or ties it, so the exact answer is 1/1024 ≈ 0.001; the simulated p must land between 0.0003 and 0.002. Engine-level test, bypassing the 30-bet minimum |
| Coin-flipper | 1,000 wallets of 100 bets each, random prices between 10¢ and 90¢, outcomes drawn at those prices | *Skilled* or *Likely skilled* for at most 7% of wallets (5% expected by design), *Skilled (high confidence)* for at most 2% |
| Favourite-buyer | 100 bets at 90¢, wins 90 | *No evidence of skill* |
| Sharp trader | 100 bets at 50¢, wins exactly 70 | *Skilled (high confidence)* (exact binomial p ≈ 0.00004) |
| Thin wallet | 29 resolved bets | *Not enough data* |
| Steady sharp (stage 2) | 100 bets at 50¢ winning 70 before the cut-off, the same after | Passes before; still *Skilled* on its after-cut-off bets |
| Lucky streak (stage 2) | The coin-flippers that happen to pass before the cut-off; after it, outcomes drawn at fair odds | Pass before by construction; pooled after-cut-off bets show *No evidence of skill* |
| Forecaster (stage 2) | Buys at 50¢, wins 70%; the price drifts slowly towards the outcome over hours | Copy-test profit stays positive at a 30-minute delay |
| Speed trader (stage 2) | Buys at 50¢ seconds before the price jumps to the outcome | Copy-test profit is zero or negative at a 5-minute delay |
| Stop-loss trader (stage 1) | 100 bets at 50¢ with no edge; bets whose price has fallen are sold before resolution, the rest are held to resolution | The card shows how many bets were held, the negative realised PnL of the sold ones, and a visible warning next to the verdict. The verdict itself may read skilled: that is the known limit |
| Market maker (stage 3) | Many small buys and sells on both sides of the same markets, flat inventory | Flagged as likely market maker |

## Running Without Keys or Live APIs

The examiner must be able to run the app from the README without our API keys and without depending on Polymarket's API answering.

- **Sample data**: about 10 real wallets (fetched once, a mix of verdicts) plus all synthetic wallets, saved as files in the repository.
- **Offline mode**: one setting makes the app read only the saved data, with no network calls.
- **Mock language model**: a mode that classifies markets by keywords ("election" → politics, "bitcoin" → crypto) and fills explanation templates, so no key is needed.
- **Cost control**: each market is classified once and the label is stored, so the language model is never asked about the same market twice.
- **Secrets**: the language model key lives in `.env`, which is never committed; the repository has an `.env.example`.

## What Makes This Different

- **Statistical inference where competitors use rankings.** Every existing Polymarket analytics tool ranks by raw PnL, ROI or volume. LiquidOracle tests skill against chance, following the question asked in the 2026 Yale SOM study of the full Polymarket trade history.
- **Domain-specific edge, not a blended score.** Splitting skill by market domain surfaces information that flat leaderboards structurally can't.
- **Honest about what it can't fully solve.** Bot and market-maker detection from public on-chain data has known accuracy limits: one 2026 arXiv microstructure study found naive taker/maker labelling only ~59% accurate against ground truth. LiquidOracle labels its filtering as a heuristic, not a solved classifier. Sybil-cluster detection (many wallets controlled by one actor) is out of v1.
- **No moat claimed beyond the above.** Polymarket's data is public; the difference is entirely in the analysis, not in data access or speed.

## Who This Serves

- **Primary user: Polymarket traders deciding whose trades are worth following** (the author is one of them). To trust a verdict they need four things: the verdict itself, how many bets it rests on, the odds in plain words, and an honest statement of what the test can't see.
- **Not served (deliberately): leaderboard browsers.** This is not a public "top 100 wallets" site. The stage 2 watchlist is private to the user running the app; no public leaderboard is planned.

## Success Criteria

**Correctness of the skill test** (each one is an automated test against the synthetic wallets above):
1. The hand-check wallet gives a p-value between 0.0003 and 0.002 (exact answer 1/1024 ≈ 0.001).
2. Across 1,000 coin-flipper wallets, a *Skilled* or *Likely skilled* verdict appears for at most 7%, and *Skilled (high confidence)* for at most 2%.
3. The sharp-trader wallet is rated *Skilled (high confidence)*; the favourite-buyer wallet is rated *No evidence of skill*.
4. A wallet with fewer than 30 resolved positions shows *Not enough data* and no verdict.
5. The same wallet with the same seed gives an identical p-value and verdict.
6. Real PnL computed by the engine matches PnL computed by hand for three saved real wallets.

**The app:**
7. With offline mode and the mock language model on, every saved wallet can be looked up and shows a verdict card, with no network access and no keys.
8. A lookup of a wallet with up to 1,000 resolved positions returns a verdict within 10 seconds on an ordinary laptop.

**Stage 2:**
9. A scan of the sample dataset in offline mode lists the sharp-trader, steady-sharp and forecaster wallets, and shows the expected number of luck passes for the number of wallets tested.
10. In the hold-up test, the steady-sharp wallets are still rated *Skilled* on their after-cut-off bets, and the lucky-streak wallets show *No evidence of skill* on theirs.
11. In the copy test, the speed trader's profit at a 5-minute delay is zero or negative, and the forecaster's stays positive at 30 minutes. A planted scan where the passing group are forecasters and the rest are coin-flippers beats random groups (p < 0.01); planted scans of coin-flippers only beat random groups (p < 0.05) at most 7% of the time.

**Stage 3:**
12. Every saved market has a domain label, and each domain with 30+ resolved positions gets its own verdict with the correction from *The Skill Test*, step 8.
13. The explanation states the same verdict and the same p-value (rounded) as the test. This is checked in code on every explanation; an explanation that disagrees is replaced by the template text.
14. The synthetic market-maker wallet is flagged, and the coin-flipper and sharp-trader wallets are not.

**Course deliverable:** the README lets the examiner install and run the app with the saved data, and the repository shows the path from this brief through PRD, architecture and stories to the code.

## Scope

**v1, built in three stages. Each stage ends with a working, tested app.**

- **Stage 1 (minimum version)**: wallet ingestion with local caching; the skill test on the whole wallet; synthetic test wallets and tests; offline mode; a web page with the verdict card and the luck chart.
- **Stage 2**: the scan and private watchlist, the hold-up test and the paper copy test, with their synthetic test wallets.
- **Stage 3**: domain classification of markets by language model (with the mock mode and stored labels) and verdicts per domain; bot and market-maker heuristics; plain-language explanations with the consistency check. If time runs short, this stage is trimmed first.

**Explicitly out of v1 (deferred to v2):**
- **Sybil-cluster detection**: identifying groups of wallets controlled by one actor (common funding sources, timing clusters). Named out loud so it doesn't creep back in: this is the feature most likely to blow the timeline.
- Positions exited before resolution in the skill test.
- Public leaderboard and social features (following, sharing, notifications).
- Prediction markets other than Polymarket (Kalshi, Manifold).
- Any live trading, automated copy-trading or financial advice. The copy test is a paper calculation; this is an analytics tool, not a trading agent.

## Vision

If the core method holds up, LiquidOracle's skill test and domain-aware scoring carry over to any prediction market with public trade history (Kalshi, Manifold). Further out, sybil-cluster detection could flag coordinated wash-trading and airdrop-farming rings, turning a wallet-lookup tool into a trust layer for prediction markets. The near-term goal is narrower: prove that the skill/luck separation works on Polymarket data, and prove with tests that the implementation is right.
