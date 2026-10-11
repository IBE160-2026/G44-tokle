---
title: "Product Brief: LiquidOracle"
status: final
created: 2026-09-16
updated: 2026-10-12
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

## Executive Summary

Prediction markets like Polymarket publish every trader's positions and PnL in the open, but raw PnL is a terrible proxy for skill. A wallet can look brilliant after one lucky binary bet, and roughly a quarter of all historical Polymarket volume is estimated to be wash trading rather than real conviction. Every existing tool (Polymarket's own leaderboard, Dune dashboards, third-party sites like polywallet.app and polymarketanalytics.com) ranks wallets by raw PnL, ROI or volume. None of them ask the harder question: *is this wallet actually good, or did it just get lucky, run a bot, or fake its numbers?*

LiquidOracle answers that question. It ingests a wallet's Polymarket trades and resolved outcomes. It then runs a statistical test of whether the wallet beat the odds that the market itself offered, more often than luck explains, in the spirit of the 2026 Yale SOM study that found only ~3% of Polymarket accounts show skill beyond chance. Later stages split the verdict by market domain (politics, sports, crypto, macro), flag likely bots and market makers, and use a language model to classify markets and explain each verdict in plain language.

This is built as the deliverable for IBE160 (Programming with AI) at Høgskolen i Molde: a solo, free-choice course project delivered in this repository.

## The Problem

Traders on Polymarket who want to follow "smart money" have no reliable way to find it. Today they're stuck with:

- **Raw leaderboards** (Polymarket's own, Dune boards, polywallet.app, polycopy.app) that rank by lifetime PnL or ROI. These can't tell apart a wallet that called ten close elections through real analysis from one that made a single big bet on a coin flip and got lucky.
- **"Smart money" / "insider" labels** on third-party sites, which turn out to be simple size or PnL thresholds, not statistical inference. A large position isn't evidence of skill, just of size.
- **No visibility into fake signal.** A 2025 Columbia study found ~25% of Polymarket's historical volume (~$4.5B) is likely wash trading, spiking to ~60% per week during airdrop-farming periods on certain markets. A leaderboard that doesn't account for this is actively misleading: a top-ranked wallet may just be farming rewards, not trading with insight.
- **No domain granularity.** A wallet that's genuinely sharp on macro markets but mediocre on sports gets one blended score, hiding exactly what a follower needs to know: where is this wallet's edge real?

The cost is direct: traders copying "top" wallets on faith are as likely to be copying luck, bot activity or farmed volume as real skill.

## The Solution

LiquidOracle is a web app. The user pastes a Polymarket wallet address and gets a skill verdict, not just a PnL number.

**What the user sees:**

1. **A verdict card**: one of *Skilled (high confidence)*, *Likely skilled*, *No evidence of skill* or *Not enough data*, with the number of resolved bets it is based on and the wallet's PnL.
2. **The odds in plain words**: "A trader with no edge would do this well about 1 time in 300."
3. **A chart of luck**: the spread of profits a no-skill trader could have made with the same bets, with the wallet's real result marked on it.
4. **When there is too little data**: no verdict, just how many resolved bets the wallet has and how many more are needed.
5. Later stages add a table of verdicts per domain, bot or market-maker flags, and a short AI-written explanation.

**How it works:**

1. **Data ingestion**: pulls trade history, positions and resolved outcomes for the wallet from Polymarket's public Data API / subgraph, and caches them locally.
2. **Skill test**: compares the wallet's real profit with 10,000 simulated "no-skill" versions of the same bets (see *The Skill Test*).
3. **Domain-aware scoring** (stage 2): a language model classifies each market question into a domain, and the skill test runs per domain. A wallet can be "skilled in crypto markets, no signal in sports."
4. **Bot / market-maker filtering** (stage 3): behavioural heuristics (inventory skew, two-sided quoting, holding duration) flag wallets that look like automated market making or arbitrage rather than opinionated trading.
5. **Plain-language verdicts** (stage 3): a language model turns the statistical output into a short explanation. It may only restate what the test found, and this is checked (see *Success Criteria*).

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
8. **Per domain** (stage 2): the same test on each domain with at least 30 resolved positions. Testing several domains gives luck several chances, so each domain's p-value is multiplied by the number of domains tested (Bonferroni correction) before the verdict is chosen.
9. **Reproducibility**: the random generator takes a seed. The seed is stored with each result, so the same wallet with the same seed gives the same verdict.

**Why this method rather than shuffling the trade sequence.** The original brief proposed shuffling each wallet's buy/sell sequence. The feedback identified the risk that a shuffle test can look right and still be wrong, for example by shuffling the wrong thing or computing PnL differently for real and shuffled data. The simulation above has one ingredient (the price paid), one formula, and small cases that can be worked out by hand. That makes it possible to prove the implementation correct with tests.

**Known limitations, stated in the app:**
- Market prices are not perfectly fair. Long shots tend to be overpriced on prediction markets, so a wallet that mostly buys favourites can look slightly skilled.
- Positions exited before resolution are ignored in v1, so skill at timing exits is not measured.
- One very large bet can dominate a wallet's PnL. The page shows the share of PnL coming from the largest position.

## How We Know the Test Is Right

The biggest risk in this project is a statistics engine that runs and produces plausible numbers but is wrong. We control that with **synthetic wallets whose correct answer is known in advance**. They are generated by a script with a fixed seed, stored in the repository, and used both as automated tests and as a demo for the examiner.

| Synthetic wallet | How it is built | Expected result |
|---|---|---|
| Hand-check | 10 bets at 50¢, all won | Only "all 10 won" beats or ties it, so the exact answer is 1/1024 ≈ 0.001; the simulated p must land between 0.0003 and 0.002. Engine-level test, bypassing the 30-bet minimum |
| Coin-flipper | 1,000 wallets of 100 bets each, random prices between 10¢ and 90¢, outcomes drawn at those prices | *Skilled* or *Likely skilled* for at most 7% of wallets (5% expected by design), *Skilled (high confidence)* for at most 2% |
| Favourite-buyer | 100 bets at 90¢, wins 90 | *No evidence of skill* |
| Sharp trader | 100 bets at 50¢, wins exactly 70 | *Skilled (high confidence)* (exact binomial p ≈ 0.00004) |
| Thin wallet | 29 resolved bets | *Not enough data* |
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
- **Not served (deliberately): leaderboard browsers.** This is not a "top 100 wallets" site; the product is the verdict on a wallet the user asks about. No public leaderboard is planned.

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
9. **Stage 2**: every saved market has a domain label, and each domain with 30+ resolved positions gets its own verdict with the correction from *The Skill Test*, step 8.
10. **Stage 3**: the explanation states the same verdict and the same p-value (rounded) as the test. This is checked in code on every explanation; an explanation that disagrees is replaced by the template text.
11. **Stage 3**: the synthetic market-maker wallet is flagged, and the coin-flipper and sharp-trader wallets are not.

**Course deliverable:** the README lets the examiner install and run the app with the saved data, and the repository shows the path from this brief through PRD, architecture and stories to the code.

## Scope

**v1, built in three stages. Each stage ends with a working, tested app.**

- **Stage 1 (minimum version)**: wallet ingestion with local caching; the skill test on the whole wallet; synthetic test wallets and tests; offline mode; a web page with the verdict card and the luck chart.
- **Stage 2**: domain classification of markets by language model, with the mock mode and stored labels; verdict per domain.
- **Stage 3**: bot and market-maker heuristics; plain-language explanations with the consistency check.

**Explicitly out of v1 (deferred to v2):**
- **Sybil-cluster detection**: identifying groups of wallets controlled by one actor (common funding sources, timing clusters). Named out loud so it doesn't creep back in: this is the feature most likely to blow the timeline.
- Positions exited before resolution in the skill test.
- Public leaderboard and social features (following, sharing, notifications).
- Prediction markets other than Polymarket (Kalshi, Manifold).
- Any live trading, copy-trading or financial advice. This is an analytics tool, not a trading agent.

## Vision

If the core method holds up, LiquidOracle's skill test and domain-aware scoring carry over to any prediction market with public trade history (Kalshi, Manifold). Further out, sybil-cluster detection could flag coordinated wash-trading and airdrop-farming rings, turning a wallet-lookup tool into a trust layer for prediction markets. The near-term goal is narrower: prove that the skill/luck separation works on Polymarket data, and prove with tests that the implementation is right.
