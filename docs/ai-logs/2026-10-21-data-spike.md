# AI session log, 2026-10-21: data spike (PRD Open Questions 1, 2, 3)

- **Tool**: Claude Code (model Claude Sonnet 5.5) in the VS Code extension.
- **Student**: Edvard Tokle (G44).
- **What this covers**: the "what data can we actually get" step before architecture: read-only probes of Polymarket's public APIs (Data, Gamma, CLOB), the findings, and the changes to the PRD that follow from them.
- **Transcript**: the full chat is saved as `transcripts/2026-10-21-data-spike-transcript.md`, with tool output shortened.
- **Result**: `spike/` (probe scripts, trimmed samples, `FINDINGS.md`); PRD and addendum updated through the memlog (19 new entries); branch `data-spike`.

## 1. The prompt and the plan

> "new chat, read HANDOFF.local.md first. the ux pr is merged, pull main n make a new branch. next step is the data spike from the prd (Q1, Q2, Q3), what data can we actually get. lets go thru it together before u write anything"

The AI pulled main, made the branch, read PRD §9, and explained the three questions in plain words before writing anything: what each asks, what the spike would test, and a plan (throwaway script in `spike/`, a handful of wallets from the leaderboard, short findings file, answers into the PRD through the memlog, read-only and no keys).

The student agreed to the order (Q2, Q1, Q3) and **changed the plan in these ways**:
- keep the scripts in `spike/`, but **commit only small trimmed JSON samples** and git-ignore the big raw dumps;
- pull the wallets from the leaderboard, the AI's choice which;
- **three extra checks he added**: for Q2, whether a wallet list can be built from who traded in markets that closed before the cut-off; for Q1, whether the activity endpoints cut off history on big wallets and whether identical rows are separate fills; for Q3, how big the gap between buy and sell prices is, because price history is an average, not what a copier pays;
- go slow on requests (the helper waits 1.5 seconds between calls), and show him the Q2 findings before moving on.

## 2. Q2: where does a Scan get its wallets?

**What the AI found**: the leaderboard shows only today's ranking, with no date setting. Four guessed date parameters were ignored. Wallets can instead be listed from the trades in markets that closed before the cut-off (the trade list takes an end time). A first test with 10 big markets gave 5,259 wallets, and 331 of them traded in two or more of the markets. The AI said the real cost is not listing candidates but fetching each one's history.

**What the student then asked for** (before Q1), and what came of it:
1. **"Skim the official docs once for a date param, so 'found none' becomes 'there is none'."** The documented parameters have no date. (The docs also say offset max 1000, but 5000 worked live.)
2. **"The 1000 trades were the last ones before close, mostly late buyers and bots. Redo it spread over each market's whole life."** His suspicion was right: the spread sample gave 4,920 wallets and only 216 in two or more markets, and just 1,079 wallets were in both samples.
3. **"Check the wallet address in /trades is the same one positions and activity use."** All sources use the proxy wallet; the profile exposes no signing account.

**A mistake the AI made and corrected**: it called one random pool wallet "typical" and wanted a second one "not on the leaderboard". The leaderboard lookup by address returns a rank for any wallet (ranks go past 2 million), so none of the draws were unranked. The pool is a mix from rank 339 with $120M volume to rank 704,637 with $582 volume. The AI said so in its report and kept both a mid and a tiny wallet.

## 3. Q1: bets, entry price, fees, sells

Main results: closed positions carry entry price and resolution time and can be read oldest first; the activity endpoint reaches 5,500 rows per query and needs end-time windows beyond that (tested on 8,008 trades, nothing lost); identical-looking fills are separate fills (keeping all rows matches position sizes for 347 of 356 positions, collapsing them breaks 7 more); fees are visible in trade rows and realized PnL is net of them.

**The student's challenge**: "25 losses out of 356 is a 93% win rate for a typical wallet, sounds too good. My guess is losing bets never get redeemed so they sit in /positions."
- The AI first pointed out the wallet buys at about 0.98 on average, so 93% is plausible, and then tested the guess instead of arguing. On the typical and the tiny wallet `/positions` was empty, so nothing was hidden there.
- It then tested wallets that do hold tokens. His guess held: on one pool wallet 837 of 1,196 positions were lost and unredeemed, and an exact check by market found only 7 of 30 of them in the closed list. **FR-3 needs both sources.**
- He also asked whether the 4% size gaps were merges, splits or conversions. Splits explain six of the nine odd rows; three rows (under 1%) stay unexplained, and that is written down as open rather than guessed.

**Smaller AI errors caught while working**: a console encoding crash on non-English market names; Gamma returning nothing for closed markets unless asked for them; two figures in the findings file that did not agree (page counts), fixed after rereading.

## 4. Q3: prices

Minute-level history exists for resolved markets from about mid-2023 (none found for January 2023 and earlier), one request covers 14 days, and thin markets get filled-in flat prices. The history price is the midpoint of buyers' and sellers' prices: median gap 0.2 cent (Trump 2024), 1 cent (Korean election and three mid-priced markets), 90th percentile up to 3 cents. Thin markets could not be measured. A failure in one market was the AI's own request covering more than 14 days, not a data gap.

## 5. The student's decisions on the findings

| # | Item | AI recommendation | Student's decision |
|---|---|---|---|
| 1 | FR-3 sources | Use both closed and open positions | Agreed |
| 2 | FR-18 spread | Add a half-cent allowance, or only state the limitation | **Both**: add the half cent *and* write the limitation (thin markets not measured, 90th percentile 3 cents) |
| 3 | Scan design | Build the candidate list from trades in earlier markets, compute profit itself, leaderboard only for lookup and sample wallets, a per-wallet limit | Agreed |
| 4 | FR-1 address | The address is the proxy wallet on the profile page | Agreed |
| 5 | Copy Pool request cost | Not measured | **Asked for an estimate now** from about 10 pool wallets while the scripts were at hand: only 7 pool wallets in the top 3,000 turned up in 60 draws, 6 of them had more than 2,000 closed positions, and a whole-Scan Copy Pool comes out at roughly 30,000 to over 250,000 price requests. **This showed the AI's own 2,000-position limit was too tight** (see below); the PRD now says so and no requirement is changed until the student decides |
| 6 | Win rate versus profit | (not raised by the AI) | **The student's point**: 93% wins at 98-cent buys shows win rate means nothing; check the Verdict ranks on profit after costs. The AI checked the PRD: the Verdict is the p-value of profit against luck, not hit rate (no change). It found one gap: the Real PnL does not deduct a wallet's own trading fees. Written down as open for the student to decide; not changed |
| 7 | Default Cut-off Date | (not raised by the AI) | **The student's point**: no price history before mid-2023, so the default Cut-off Date must be after 1 July 2023 |

Things the AI added under these decisions that the student has not yet confirmed one by one: a 2,000-position limit per wallet ("too large to scan"), the request count in PRD §8 (about 150 for a first lookup), and the Spread Allowance value itself, all tagged as assumptions in the PRD. **The estimate then undercut the AI's limit**: 6 of 7 top-ranked wallets exceed it, so most top wallets would be left out. The AI had also written that such wallets are "mostly market makers", a claim it had no data for; it removed that sentence and tagged the limit "to revisit". The student then decided both open points; see section 6.

**AI errors in its own bookkeeping**: the memlog entry for the spread said "eight Markets"; the AI found the real count (5 measured of 9 tried) and appended two corrections, because the memlog is append-only. The correct figures are now in `FINDINGS.md`.

## 6. After the estimate: the student's decisions

The AI put the estimate and four proposals in front of the student: how to cut the Copy Test's price requests, what to do with big wallets, whether Real PnL should be net of the wallet's own fees, and a commit plan.

| # | Item | AI recommendation | Student's decision |
|---|---|---|---|
| 8 | Copy Test size | A capped sample of each wallet's after positions plus a smaller default Scan | **A mix: the capped sample and a faster pace within the published limits.** He did not pick the smaller default Scan, so 200 stays. The numbers 100 per wallet and 5 requests per second are the AI's proposals, tagged as assumptions |
| 9 | Big wallets | Raise the limit, or accept a small Scan | **Neither: keep big wallets and rank them on their latest 2,000 positions before the cut-off, noted as a limitation.** This replaced the AI's "too large to scan" |
| 10 | Real PnL and fees | (open proposal) net of the wallet's own fees | **Yes.** The AI added a point he had not asked about: because the same fee comes off the real result and every simulation, the p-value and Verdict do not change; what changes is the profit shown, the chart axis and the Scan ranking. A test for that is in the PRD |
| 11 | Commits | Three commits, then push | **Yes** |

Still open for architecture (written in the PRD): how to find where the cut-off falls in a list read newest first, the Hold-up Test's full fetch of big wallets' after part, whether a lookup of one very large wallet also uses the latest 2,000, how splits and merges count, and where in the data the wallet's own fee is read.

## 7. What changed in the repository

- `spike/`: shared request helper and 30 probe and analysis scripts, 7 small sample files, `FINDINGS.md`. Raw dumps (13 MB) are git-ignored.
- PRD: Glossary (Scan, Follower Fee, new Spread Allowance, Own Fees, Real PnL, Simulation, new Copy Sample, Copy Pool, Copy Test, Follower PnL), FR-1, FR-3, FR-4, FR-5, FR-11, FR-16, FR-18, §8, §9 (Q1, Q2 and Q3 closed, Q6 constraint added), §10 (assumptions: Spread Allowance, latest 2,000, Copy Sample 100, 5 requests per second). `updated` bumped to 2026-10-21; status stays final.
- `addendum.md`: the Polymarket data section now records what was checked.
- PRD memlog: 19 new entries, including three corrections (the market count, and the resolution-time wording).
- No application code and no tests: the spike is evidence, not product code.
