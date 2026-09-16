---
title: "Product Brief: LiquidOracle"
status: final
created: 2026-09-16
updated: 2026-09-16
---

# Product Brief: LiquidOracle

## Executive Summary

Prediction markets like Polymarket publish every trader's positions and PnL in the open — but raw PnL is a terrible proxy for skill. A wallet can look brilliant after one lucky binary bet, and roughly a quarter of all historical Polymarket volume is estimated to be wash trading rather than real conviction. Every existing tool (Polymarket's own leaderboard, Dune dashboards, third-party sites like polywallet.app and polymarketanalytics.com) ranks wallets by raw PnL, ROI, or volume. None of them ask the harder question: *is this wallet actually good, or did it just get lucky, run a bot, or fake its numbers?*

LiquidOracle answers that question. It ingests Polymarket trade and position data, runs a statistical randomization test — the same approach a 2026 Yale SOM study used to find that only ~3% of Polymarket accounts show skill beyond chance — to separate genuine predictive edge from noise, and applies behavioral heuristics to flag likely bots and market makers so they don't pollute the skill signal. An LLM classifies each market by domain (politics, sports, crypto, macro), so a wallet's edge is measured where it actually has one, and generates a plain-language explanation of each verdict a trader can act on.

This is built as the deliverable for IBE160 (Programming with AI) at Høgskolen i Molde — a solo, free-choice course project graded 70% on the working code and 30% on a reflection report documenting the AI-assisted development process, both delivered in this repository. Difficulty and the presence of a genuine, load-bearing AI component (not a bolted-on chatbot) count toward the grade, which shapes the scope choices below.

## The Problem

Traders on Polymarket who want to follow "smart money" have no reliable way to find it. Today they're stuck with:

- **Raw leaderboards** (Polymarket's own, Dune boards, polywallet.app, polycopy.app) that rank by lifetime PnL or ROI — indistinguishable between a wallet that called ten close elections correctly through real analysis and one that made a single leveraged bet on a coin flip and got lucky.
- **"Smart money" / "insider" labels** on third-party sites, which turn out to be simple size or PnL thresholds, not statistical inference — a large position isn't evidence of skill, just of size.
- **No visibility into fake signal.** A 2025 Columbia study found ~25% of Polymarket's historical volume (~$4.5B) is likely wash trading, spiking to ~60%/week during airdrop-farming periods on certain markets. A leaderboard that doesn't account for this is actively misleading — a top-ranked wallet may just be farming rewards with sybil-controlled accounts, not trading with insight.
- **No domain granularity.** A wallet that's genuinely sharp on macro markets but mediocre on sports gets one blended score, hiding exactly the information a follower needs (where is this wallet's edge real?).

The cost of this is direct: traders copying "top" wallets on faith are as likely to be copying luck, bot activity, or farmed volume as real skill.

## The Solution

LiquidOracle is a web app that takes a Polymarket wallet address (or browses a curated set) and returns a skill verdict, not just a PnL number:

1. **Data ingestion** — pulls trade history, positions, and resolved outcomes for a wallet via Polymarket's public Data API / subgraph.
2. **Skill scoring** — runs a randomization test: shuffles the wallet's actual buy/sell sequence against the same markets thousands of times to build a null distribution of possible PnL outcomes, then reports how the wallet's real performance compares (a statistical "this beats chance" verdict, not just a raw number).
3. **Domain-aware scoring** — an LLM classifies each market question into a domain (politics, sports, crypto, macro, etc.), so the skill test runs per-domain. A wallet can be "skilled in crypto markets, no signal in sports."
4. **Bot / market-maker filtering** — behavioral heuristics (inventory skew, two-sided quoting pattern, position holding duration) flag wallets that look like automated market-making or arbitrage rather than directional, opinionated trading, so they're excluded from — or separately labeled in — skill rankings.
5. **Plain-language verdicts** — an LLM turns the statistical output into a short, readable explanation ("this wallet's crypto-market performance beats random chance at 95% confidence across 40 resolved trades; its sports performance does not").

The experience is: enter or pick a wallet, get a verdict with confidence and domain breakdown, not a mystery score.

## What Makes This Different

- **Statistical rigor where competitors use heuristics.** Every existing Polymarket analytics tool ranks by raw PnL/ROI/volume. LiquidOracle is — as far as the research for this brief could establish — the first to apply a formal skill-vs-luck test (randomization/permutation against a null distribution) in this space, following a methodology validated in the 2026 Yale SOM academic study of the full Polymarket trade history.
- **Domain-specific edge, not a blended score.** Splitting skill by market domain surfaces information that flat leaderboards structurally can't.
- **Honest about what it can't fully solve.** Bot/market-maker detection from public on-chain data has known accuracy limits (one 2026 arXiv microstructure study found naive taker/maker labeling only ~59% accurate against ground truth). LiquidOracle states its filtering as a heuristic with disclosed confidence, not a solved classifier — a deliberate differentiator from tools that imply certainty they don't have. Sybil-cluster detection (multiple wallets controlled by one actor) is explicitly out of v1 scope — see below.
- **No moat claimed beyond the above.** Polymarket's data is public to anyone; the differentiation is entirely in the analytical method, not in data access or execution speed.
- **Genuine difficulty profile.** The build combines external API ingestion, a statistical method run over large trade histories, two distinct LLM roles (domain classification and verdict explanation), and per-domain analysis — a materially harder scope than a CRUD app or a single-prompt AI wrapper.

## Who This Serves

- **Primary: other Polymarket traders** deciding whose positions are worth following. They currently rely on raw PnL or gut instinct; LiquidOracle gives them a defensible signal — a wallet with disclosed statistical confidence, not just a big number.
- **Primary: the author**, using it as a personal research tool for his own trading decisions.
- **Not served (deliberately): the general public / vanity-leaderboard browsers.** This is not a "top 100 wallets" spectacle site — the product is the classification and explanation, not a public ranking. No public leaderboard is planned.

## Success Criteria

**Course deliverable (primary, since this is the graded artifact):**
- Working code that demonstrably runs the randomization-based skill test against real Polymarket data and produces per-domain verdicts.
- A real, load-bearing AI component (LLM domain classification + verdict explanation) that the reflection report can honestly describe as central to the product, not decorative.
- A reflection report that documents the AI-assisted development process credibly, including this brief's known limitations (bot-filtering accuracy, no sybil detection in v1) as evidence of honest scoping rather than gaps to hide.

**Product signal (secondary, self-assessed):**
- Given a known set of wallets, the skill score's high-confidence "skilled" wallets should hold up out-of-sample better than raw-PnL top wallets would (mirroring the Yale study's finding that 60% of top-PnL wallets failed out-of-sample replication) — even an informal backtest against this bar is meaningful evidence the tool works.
- The author would actually trust and use a "skilled, high confidence" verdict to inform his own trading.

## Scope

**In for v1:**
- Wallet data ingestion from Polymarket's public API/subgraph (trades, positions, resolved outcomes).
- Randomization-based skill scoring (shuffle-and-compare against null distribution) with a stated confidence level per wallet.
- LLM-based market domain classification (politics/sports/crypto/macro/etc.) and per-domain skill scoring.
- Bot / market-maker filtering via behavioral heuristics, clearly labeled as heuristic with disclosed limitations — not a validated classifier.
- LLM-generated plain-language verdict explanations.
- A web UI to look up a wallet and see its verdict, confidence, and domain breakdown.

**Explicitly out of v1 (deferred to v2):**
- **Sybil-cluster detection** — identifying groups of wallets controlled by one actor (common-funding-source graph tracing, temporal clustering). Named out loud so it doesn't creep back in: this is the single feature most likely to blow the timeline, and shipping a solid v1 without it is better than an unfinished v2-scope build.
- Public leaderboard / social features (following, sharing, notifications).
- Coverage of prediction markets beyond Polymarket (Kalshi, Manifold, etc.).
- Any live trading, copy-trading execution, or financial advice functionality — this is an analytics tool, not a trading agent.

## Vision

If the core method holds up, LiquidOracle's randomization-based skill test and domain-aware scoring generalize beyond Polymarket to any prediction market with public trade history (Kalshi, Manifold) and, further out, to sybil-cluster detection that would let it flag coordinated wash-trading and airdrop-farming rings in near real time — turning it from a wallet-lookup tool into a trust layer for prediction markets generally. For now, the near-term goal is narrower and more honest: prove the skill/luck separation works on Polymarket data, with a genuine AI component at its core, well enough to earn both a strong grade and the author's own trust as a trading tool.
