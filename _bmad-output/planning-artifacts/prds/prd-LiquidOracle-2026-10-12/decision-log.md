# Decision log: LiquidOracle PRD

Why the PRD says what it says. The PRD itself keeps only the requirements (`prd.md`); this file keeps the reasons, dates and earlier wording that used to sit inside it. The full audit trail of the BMAD workflow, one line per decision, is `.memlog.md` in this folder; git history has every earlier version of `prd.md`.

## 2026-11-20: stage 3 parked at the checkpoint

The plan's rule (Edvard, 2026-11-05) was that stage 3 is dropped if stage 1 is not done by 20 November. On that day Epic 1 had just been built and Epics 2 and 3 (also stage 1) had not started. Edvard decided that stage 3 is **parked, not deleted**: FR-15 and FR-19 to FR-24 stay in the PRD, Epics 7 and 8 stay in the epics, and they are picked back up if all of stage 2, the Copy Test (2c) included, is done before the code freeze on 1 December (the AI recommended the whole of stage 2 rather than the minimum, since stage 3 is the first thing cut; Edvard agreed). If they are not reached, the README says so with this reason (NFR-12).

## 2026-11-18: update from the teacher's PRD feedback

Source: `tilbakemelding-prd.md` (Bård, 2026-11-12). The AI proposed a change for each point; Edvard approved, changed or rejected it before any edit.

| Feedback point | What changed in the PRD | Decided by |
|---|---|---|
| 4.1 Too long and dense | Dated notes and the §9 history moved here, word for word (below). Glossary trimmed to definitions; its rules moved into the FRs that use them (Sliver → FR-3, Simulation → FR-5, Own Fees → FR-4, Random Group Check → FR-18b). FR-18 split into FR-18a Follower PnL and Return, FR-18b Random Group Check, FR-18c Price history and fallback; "FR-18" stays as the group name, so older references stay valid. | Edvard approved the AI's plan |
| 4.1 Target under about 6,000 words | Not met: 11,530 → 9,660 words. The AI estimated about 8,000 beforehand and was wrong. What is left is requirements and their checks, which the epics and code trace to and which the feedback praised (§2, testability). | Edvard chose "stop around 8,000, keep every check" (AI's recommendation) |
| 4.2 Stage 2 has no minimum | §6.1: milestones 2a Scan and Watchlist (FR-16), 2b Hold-up Test (FR-17), 2c Copy Test (FR-18). Minimum = 2a + 2b offline, plus the offline Hold-up result for the 10 real Sample Wallets reported in the README. 2c and the live real-data Scan (SM-5) are extra. SM-5 says so. | **Edvard.** The AI recommended 2a + 2b *with* a live real-data Hold-up run; Edvard chose offline only. The AI then pointed out that offline-only cuts no Scan code (the offline Scan runs the same funnel, spine AD-14), only the live run; Edvard kept offline only. Reporting the 10 real Sample Wallets was the AI's proposal, Edvard accepted. |
| 4.3 FR-24 has no full word list | FR-24 and §8 Wording point to the list that already exists in `EXPERIENCE.md`, *Voice and Tone* (banned plus "also avoided" words); one list in the code; the FR-24 test uses all of it. | Edvard approved the AI's plan |
| 4.3 FR-19 failures and cost | FR-19 *Failures*: at most 3 tries per Market; an answer outside the five Domains is never stored; if a Wallet's Market is still unlabelled, the Domain table is replaced by the UX message. FR-19 *Cost*: one call per Market, stored; README shows count and cost. FR-23: the template is shown if the model does not answer. | **Edvard, rejecting part of the feedback.** The feedback suggested labelling a failed Market *Other* with source `fallback`. The AI recommended against it and Edvard agreed: it would quietly fill the *Other* Domain and skew its Domain Verdict. |
| 4.4 §9 not tidied | Q2, Q5, Q6 struck with one-line answers (Q6's "still open" gone); Q7 moved to §6.2; "Remaining open: none". | Edvard approved the AI's plan |
| 4.5 Technology in the requirements | uv, Python versions, API routes and request counts moved from §8, FR-1, FR-3, FR-12 and FR-18 to `addendum.md`; the PRD keeps the requirement. | Edvard approved the AI's plan |
| §5 Conventions not marked | §10 lists the 30-bet minimum, the p limits 0.01 and 0.05 and the 10,000 draws as conventions; the Verdict entry in §3 says so. | Edvard approved the AI's plan |
| §5 UJ-4 is one long paragraph | UJ-4 split into six numbered steps. | Edvard approved the AI's plan |
| §7 Reflection questions | Not answered here: they are Edvard's to answer. | Edvard |

Downstream, the same day: `epics.md` (Epic 6 stories to FR-18a/b/c, the stage 2 minimum in the slipping rules, Story 5.2 closes the minimum, new Story 5.3 for a live Hold-up run, FR-19 failures in Story 7.2) and the architecture spine (AD-16 failures line).

## Earlier wording, word for word

Every line of `prd.md` as it stood before the 2026-11-18 update (commit 8bc5384) that the update changed or removed, under its old heading. Most carry a dated note on who decided and why; the long §9 entries hold the evidence from the data spike and architecture. Lines the update kept unchanged are not repeated here.

### 0. Document Purpose

> This PRD turns the revised product brief (`_bmad-output/planning-artifacts/briefs/brief-LiquidOracle-2026-09-16/brief.md`, revision 7 of 2026-10-16; the first revision, 2026-10-12, answered the course feedback) into numbered, testable requirements. Architecture, epics and stories build on it. Terms in §3 Glossary are used exactly as defined. Features are grouped in §4 with globally numbered requirements (FR-1 …). Guesses made while drafting are tagged `[ASSUMPTION]` inline and listed in §10. Technology choices live in `addendum.md`, not here.

### 2.3 Key User Journeys

>   Jonas opens the Scan page, sets the Cut-off Date to 1 June and starts a scan of the top 200 wallets by profit made before June. When it finishes, the Watchlist shows 7 wallets rated *Skilled (high confidence)*, with the note "at least about 2 of 200 would pass by luck alone, probably more, because these Wallets were picked for high profit". The app has also re-rated every scanned wallet using only the bets that resolved before June, and all 7 still pass (the Before-Cut-off Passers). The other scanned wallets that were rated on the same bets and did not pass form the Comparison Group. The Hold-up Test shows that on the bets opened after June the Passers kept beating the odds (*Skilled (high confidence)* on 640 later bets) while the Comparison Group did not. The Copy Test shows that a follower copying the Passers 5 minutes late, after fees, would have earned an average return that only 0.4% of 10,000 random groups of 7 Wallets from the same Scan matched (*Beat random picks*). Per Wallet, 5 of the 7 still make money at 5 minutes; on the other 2 the profit vanishes already at a 1-minute delay: speed traders. The page notes that these single-Wallet numbers are not luck-checked. He keeps the 5 forecasters on his list.

### 3. Glossary

> - **Sliver**: a Position with less than 1% `[ASSUMPTION]` of its bought shares, and fewer than 1 share, still held when its Market resolved (most traders who "sell everything" keep such a remainder). Its money counts in Real PnL and in every Simulation, but it is not counted as a bet: not in the number of Resolved Positions, the 30 minimum, the held count (N of M) or the left-out counts. The 1-share limit means it can pay at most $1; it never depends on whether the bet won, so it cannot favour winners. (Edvard, 2026-11-11.)
>
> - **Entry Price** (*p*): the average price paid per share of a Position, between 0 and 1: the share-weighted average of its buy fills, which sells do not change (Polymarket's own average moves on sells; Edvard, 2026-11-11). Read as the market's probability for that outcome.
>
> - **Own Fees**: the taker fees a Wallet paid on the buys of a Position, as Polymarket recorded them; 0 in Markets that charge no fee and on fills where the Wallet was the maker. Read from the Wallet's activity rows (cash paid − shares × price) in Markets that charge fees, and checked against that Market's own fee schedule. A fee that fails the check is not counted (it counts as 0) and is shown on the Verdict card (FR-11). (Architecture, 2026-10-21.)
>
> - **Simulation**: one replay of a Wallet's Resolved Positions and Slivers in which each Outcome is drawn at random, coming true with probability equal to its Entry Price. Bets that depend on the same result share one random draw: all Positions in one Market (also across Wallets, in the Hold-up Test), the Markets of one negative-risk event (only one can win), and a detectable ladder (same underlying, same resolution date). Each Position still comes true with probability equal to its Entry Price; what changes is that linked bets win and lose together, as they do in reality, instead of counting as separate evidence. The Own Fees are charged in every Simulation exactly as in the real result, so they lower both by the same amount and the p-value does not change.
>
> - **Verdict**: one of *Skilled (high confidence)* (p < 0.01), *Likely skilled* (p < 0.05), *No evidence of skill*, or *Not enough data* (fewer than 30 Resolved Positions).
>
> - **Scan**: running the Skill Test on the top Wallets by profit (default 200) in one go. Profit counts only from Positions resolved before the Cut-off Date, so the ranking cannot lean on the results the Hold-up Test is meant to check (§9 Q2). The Wallets come from the app's own candidate list: those that traded in Markets resolved before the Cut-off Date. Polymarket's leaderboard cannot be used for this (§9 Q2). Profit means Real PnL, after the Wallet's own fees. A Wallet with more than 2,000 such Positions is ranked, and Skill Tested, on its latest 2,000 only (FR-16). How the candidates are found and narrowed to the Scan size is in FR-16.
>
> - **Watchlist**: the Wallets from a Scan rated *Skilled (high confidence)* on everything the Scan fetched for them: the before part and the after part together ("whole history" below means this, not the Wallet's whole life on Polymarket). Private: stored only on the machine running the app. Every result names the set of Positions it was computed on, so a Watchlist row and the Verdict page it opens show the same result.
>
> - **Hold-up Test**: the Skill Test run on the pooled after part, as Resolved Positions, of the Before-Cut-off Passers.
>
> - **Minimum After-bets**: the fewest Resolved Positions in its after part that a Wallet needs to be counted in the Hold-up Test: 10. `[ASSUMPTION: 10]` The same number applies to the Before-Cut-off Passers and the Comparison Group. Why 10: a round starting value, high enough that one lucky bet is not a Wallet's whole after part and low enough that Wallets that kept betting still count. It is not measured; revisit with real data (§9 Q6).
>
> - **Comparison Group**: the other Wallets from the same Scan, picked the same way (same Cut-off Date, only the before part): those rated *Likely skilled* or *No evidence of skill*. Wallets with *Not enough data* in the before part are in neither group. The Comparison Group's after part is tested the same way as the Passers', with the same Minimum After-bets.
>
> - **Main Copy Delay**: 5 minutes, fixed before any data is looked at. Only the Random Group Check at this delay decides the Copy Test's result; the 1- and 30-minute numbers are extra information. Reason: testing three delays would give luck three chances to pass.
>
> - **Follower Fee**: the fee Polymarket would charge the follower for buying *s* shares at *p*<sub>delay</sub> in that Market; 0 in Markets that charge no fee. A taker fee is *s* · rate · *p* · (1 − *p*), with the rate and exponent read from the Market's fee schedule (§9 Q1).
>
> - **Spread Allowance**: half a cent (0.005) added to the price a follower pays, because the recorded price history is the midpoint between what buyers and sellers paid, not a price a follower can trade at. `[ASSUMPTION: 0.5 cent; measured gap in large liquid Markets: median 1 cent, 90th percentile 3 cents; thin Markets not measured]`
>
> - **Follower PnL**: Σ (*s* · (*o* − *p*<sub>delay</sub>) − Follower Fee), summed over each buy fill of the Position, where *s* is that fill's share of the shares held at resolution and *p*<sub>delay</sub> is the market price of the same outcome one Copy Delay after that fill, plus the Spread Allowance (capped at 1). A Position bought in 12 fills is copied 12 times, each at its own time. (Architecture, 2026-10-21.)
>
> - **Copy Sample**: for each Wallet, the Resolved Positions in its after part that the Copy Test prices: all of them if there are at most 100, otherwise 100 drawn at random with the Seed, by the same rule for every Wallet. `[ASSUMPTION: 100 Positions per Wallet]` Reason: pricing every after Position of a 200-Wallet Scan would take tens of thousands of requests (§9 Q3).
>
> - **Random Group Check**: the luck check on the Copy Test. The Passers' score is the average Follower Return of the Passers in the Copy Pool, at the Main Copy Delay, each Wallet counting equally. The system draws 10,000 random groups of the same size from the Copy Pool (no Wallet twice in one group) and scores each the same way. Copy p-value = (1 + number of random groups scoring ≥ the Passers) / (1 + 10,000). Copy Verdict: *Beat random picks* (Copy p-value < 0.05), *No better than random picks*, or *Not enough data* when no Passer is in the Copy Pool or fewer than 1,000 different groups of that size can be drawn from it. `[ASSUMPTION: 1,000]` Runs with a Seed, like the Skill Test.
>
> - **Copy Test**: computing Follower PnL and Follower Return for each Copy Delay over the Copy Sample of each Before-Cut-off Passer, plus the Random Group Check. Paper only.
>
> - **Sample Dataset**: Wallet histories (Positions from before and after its default Cut-off Date, §9 Q6), Market data, and the recorded price history around each buy fill (enough to find the price at each Copy Delay), saved in the repository so the app can run without the network. Large synthetic groups are regenerated from the generator when the Sample Dataset is loaded (FR-12).

### FR-1: Look up a Wallet

> - The address is the one on the Polymarket profile page (the proxy wallet). Every Polymarket data source used here (trades, positions, activity, profile) is keyed by that address, and none exposes the signing account, so an address from a wallet app may show no history. (Data spike, 2026-10-21.)

### FR-3: Build Positions

> - Positions come from two sources, both required: closed positions (exited or redeemed) and open positions. A losing Position that was never redeemed is worth 0, stays in the open list and is missing from the closed list: on one pool Wallet 837 of 1,196 positions were such losses, and only 7 of 30 checked were also in the closed list. A loss counts like any other. (Data spike, 2026-10-21.)
>
> - A Market is resolved when the Market data says it is closed, its outcome prices are exactly 0 and 1, and it has a resolution time. The resolution time (needed for the Cut-off Date) always comes from the Market data: in the current data source the closed list's own timestamp is the Wallet's last event, 0 to 85 hours after resolution. A Market that resolved any other way (for example 50-50) is left out as "unclear resolution". (Architecture, 2026-10-21.)
>
> - The shares held at resolution are the Wallet's bought shares minus its sold shares, from its activity rows. Redemptions are never used to count shares, because an unredeemed loser has none. (Architecture, 2026-10-21.)
>
> - Besides fully sold Positions, a Position is left out of the Skill Test, counted, and shown with its reason when: the Wallet split, merged or converted shares in that Market (the recorded entry price of such a Position is bookkeeping, not a price paid); the token appears only in the activity rows; its shares held are not between 0 and the shares bought; the two sources disagree on shares bought by more than 1% `[ASSUMPTION]` (the size of the gap is stored); its Market has an unclear resolution; or the Wallet's history could not be read in full (FR-16). The same rules apply before and after the Cut-off Date. (Architecture, 2026-10-21.)
>
> - A Position partly sold down to a Sliver (Glossary) is not counted as a bet, but its money stays in Real PnL and in every Simulation. (Edvard, 2026-11-11.)

### FR-4: Real PnL

> The system computes Real PnL from a Wallet's Resolved Positions.

### FR-8: Verdict card

> - Below 10, N is rounded to a whole number, so the phrase never shows a decimal: 0.45 is shown as "about 1 time in 2", 0.27 as "about 1 time in 4", 0.11 as "about 1 time in 9". (Edvard, 2026-11-05.)
>
> - When no Simulation reached the Real PnL, the card says "fewer than 1 time in 10,000", never "about 1 time in 10,000": 10,000 Simulations cannot show a smaller chance than that.
>
> - A p-value of 1/10,001 is shown as "fewer than 1 time in 10,000", and 0.0099 as "about 1 time in 100".

### FR-11: Honesty notes

> - when a Wallet has more than 2,000 Resolved Positions in the part tested, the line "Based on the latest 2,000 of N Resolved Positions; older results are not included." Why: older Positions are not fetched, and leaving them out can make a Wallet look better or worse than it is. For the after part the line says "first 2,000" instead; a Watchlist result says it rests on the two windows around the Cut-off Date, and that Positions bought before the date and resolved after it are in neither;
>
> - how many fees failed the check against the Market's fee schedule, with their recorded total (Glossary, Own Fees);

### FR-12: Sample Dataset

> - The real Wallets' price history is fetched as early as possible: on 2026-09-04 Polymarket replaced the price-history route the Copy Test uses with one that keeps one-minute prices for at least 7 days only. The old route still answers with no end date announced, and Data API v1 was retired with three days' notice (§9 Q3). (Edvard, 2026-10-21.)
>
> - The Sample Dataset has one default Cut-off Date (§9 Q6). The real Wallets have Positions both before and after it, so the Hold-up Test and Copy Test run offline with that date. Online, the user can choose any date (FR-16).
>
> - Stated limitation, one-way: for the two largest real Wallets (0xd218e4…, 0x63d43b…), the captured activity after the Cut-off Date stops at the 150,000-row cap (12 and 20 August 2025), so 808 and 418 of their 2,000 after-part Positions may miss later buy fills and are left out under the cap rule (FR-3). This cannot be repaired later: if the cap rule changes, the missing price windows can no longer be fetched once the old one-minute price route is gone. (Edvard, 2026-10-23.)

### FR-13: Synthetic Wallets

> | Coin-flipper | 1,000 wallets of 100 bets each, random prices between 10¢ and 90¢, outcomes drawn at those prices | *Likely skilled* or better for at most 7% of wallets (5% expected by design), *Skilled (high confidence)* for at most 2% | FR-5, FR-17, FR-18, FR-22, UJ-3 |
>
> | Forecaster (stage 2) | Buys at 50¢, wins 70%; the price drifts slowly towards the outcome over hours | Copy-test profit stays positive at a 30-minute delay | FR-16, FR-18 |
>
> | Speed trader (stage 2) | Buys at 50¢ seconds before the price jumps to the outcome | Copy-test profit is zero or negative at a 5-minute delay | FR-16, FR-18 |
>
> | Stop-loss trader (stage 1) | 100 bets at 50¢ with no edge; bets whose price has fallen are sold before resolution, the rest are held to resolution. The price moves fairly and the stop is 25¢: 67 bets fall to 25¢ and are sold there (17 of them in Markets their side later won), 33 are held and all win, so the total is about zero (−$25) (Edvard, 2026-11-13) | The card shows how many bets were held, the negative realised PnL of the sold ones, and a visible warning next to the verdict. The verdict itself may read skilled: that is the known limit | FR-11 |

### FR-14: Offline Mode

> - Offline Mode never calls the language model, even when a key is set: it uses the stored Domain labels and the templates. It keeps its data apart from the data of online runs, so an online lookup never appears offline and sample data never appears online. (Architecture, 2026-10-21.)

### 4.5 Is Skill Worth Following? (stage 2)

> **Description:** Answers the follower's question: which wallets are worth following, does their skill last, and does it survive being copied late. Everything here is computed on recorded data; nothing places orders. Realizes UJ-4.

### FR-16: Scan and Watchlist

> The user chooses a Cut-off Date, starts a Scan of the top Wallets by profit (after fees) made before that date (default 200), and sees the Watchlist, sorted by p-value, with the Minimum Luck Passes shown next to it. `[ASSUMPTION: 200 Wallets is a sensible default Scan size; see §9 Q3 for the measured fetch cost]`
>
> - Only Positions resolved before the Cut-off Date count toward the profit that ranks the Wallets, so nothing after the date decides who is scanned (§9 Q2).
>
> - The candidate Wallets are every Wallet that held a Position in a chosen set of Markets resolved before the Cut-off Date, read from each Market's list of positions (closed ones and still-held ones, which include unredeemed losers), so Wallets that later went quiet or lost money are in the list too. Polymarket's leaderboard has no date setting and shows only today's survivors. The data spike's method, walking back through a Market's trades, does not work on the current data source. (Data spike and architecture, 2026-10-21.)
>
> - The funnel: the Markets resolved in the 90 days before the Cut-off Date, top 100 by volume, chosen without looking at outcomes; from their candidates, a shortlist of 3 × the Scan size by a quick profit estimate that also counts unredeemed losses; then each shortlisted Wallet's full data, ranked by Real PnL. `[ASSUMPTION: 90 days, 100 Markets, 3 ×]` The Scan page states the population tested ("Markets resolved in the 90 days before the Cut-off Date, top 100 by volume"), how many of the 100 Markets were used, and that the shortlist estimate is approximate. (Edvard, 2026-10-21.)
>
> - A Market whose list could not be read in full gives no candidates and is shown as "not used: partial", because a partly read list leans towards winners or losers. A Wallet whose history could not be read in full is kept, marked "not fully read" everywhere it is counted (ranking, Watchlist, Passers, Hold-up groups, Copy Pool), and its unread Positions are left out (FR-3). Only Polymarket not answering stops a Scan; it can then be resumed. (Edvard, 2026-10-21.)
>
> - A Wallet with more than 2,000 Resolved Positions before the Cut-off Date is not left out: it is ranked, and Skill Tested, on its latest 2,000 of them (those resolved last before the date), and its Verdict card says so (FR-11). Its after part is likewise capped at the first 2,000 after the date (FR-17). This is a stated limitation: older results do not count, so such a Wallet can look better or worse than its whole history would show. `[ASSUMPTION: 2,000 Positions; in a draw of 7 pool Wallets ranked in the top 3,000, 6 had more than 2,000 closed Positions (§9 Q3)]`

### FR-17: Hold-up Test

> - Both groups are picked from the same Scan by the same rule, using only the before part, and both are tested on the after part. No Position from after the Cut-off Date decides who is in either group.
>
> - Nor does any Position from after the Cut-off Date decide which Wallets are in the Scan itself (FR-16).
>
> - A Wallet that passes only when Positions from after the Cut-off Date are included is not in the Before-Cut-off Passers.
>
> - Each Wallet is in at most one of the two groups.
>
> - A Wallet counts in its group's result only if it has at least the Minimum After-bets Resolved Positions in the after part. The same minimum applies to both groups.
>
> - Wallets that stop betting after the Cut-off Date (none, or fewer than the minimum) are dropped by that same rule in both groups, never kept in one and dropped in the other. Each group's result shows Wallets in the group, Wallets dropped for too few after bets, and Resolved Positions counted.
>
> - If the share of Wallets dropped differs by more than 20 percentage points between the two groups, the page says so next to the results: "More Wallets were dropped in one group than in the other. Wallets that stop betting may be the ones that lost, so the group with more dropped Wallets may look better than it is." `[ASSUMPTION: 20 percentage points is "way more"]` A planted example (60% dropped in one group, 10% in the other) shows the message; equal shares show none.
>
> - A Wallet's after part is its first 2,000 Positions in resolved Markets bought on or after the Cut-off Date, the same cap as the before part, and the page says so. (Edvard, 2026-10-21.)
>
> - The pooled after part is simulated with linked bets sharing one draw (Glossary, Simulation): Passers who bet in the same Markets are not counted as independent evidence. A planted check: 7 coin-flipper Passers holding the same side of the same 40 Markets get p < 0.05 in at most 7% of 1,000 runs. (Edvard, 2026-10-21.)
>
> - Each group's result shows how many of its Wallets are "not fully read" (FR-16).

### FR-18: Copy Test

> For each of the Before-Cut-off Passers, over its Copy Sample, the system shows Follower PnL and Follower Return at each Copy Delay next to the Wallet's own Real PnL over the same positions, using Polymarket's recorded price history. Above them it shows the Random Group Check at the Main Copy Delay: the Copy p-value as "random groups did as well in X% of draws", and the Copy Verdict.
>
> - For a hand-made set of three Positions in a Market with a fee, Follower PnL and Follower Return equal a hand calculation stored with the tests (to the cent).
>
> - A planted Scan of 10 forecaster Passers and 100 coin-flipper Wallets (copy prices give the coin-flippers no edge) gets a Copy p-value < 0.01 at the Main Copy Delay.
>
> - When no random group scores as well as the Passers, the page says "no random group did as well in 10,000 draws", never a percentage: the Copy p-value's floor of 1/10,001 would otherwise read as "0.01% of draws", which is false.
>
> - The Copy Verdict comes only from the Main Copy Delay. The 1- and 30-minute results show Follower PnL and Follower Return only, marked as extra information, with no Copy Verdict.
>
> - The per-Wallet numbers are marked as not luck-checked; only the Random Group Check is.
>
> - A position with no recorded price at a Copy Delay is left out of that delay's sum, and the count of left-out positions is shown.
>
> - Every Wallet is priced on its Copy Sample (at most 100 after Positions, drawn with the Seed by one rule for all Wallets); the page shows "priced N of M after Positions" and says the numbers rest on a sample. A Wallet with 250 after Positions shows "priced 100 of 250"; the same Seed gives the same sample.
>
> - Follower PnL includes the Spread Allowance (half a cent per share). The page states its limits: the allowance comes from large liquid Markets, where the gap between buyers and sellers had a median of 1 cent and a 90th percentile of 3 cents; thin Markets were not measured and may cost more; and the follower's own price impact is ignored. Follower PnL is therefore still an upper bound.
>
> - The hand-calculated three-Position set includes the Spread Allowance.
>
> - Every buy fill is copied at its own time plus the Copy Delay (Glossary, Follower PnL). The hand-calculated set includes a Position bought in more than one fill. (Edvard, 2026-10-21.)
>
> - The page shows how many of the Passers' Copy Sample Markets are shared by two or more Passers. A planted gate: across 1,000 planted Scans in which 10 coin-flipper Passers hold the same side of the same 40 Markets, the Copy p-value is < 0.05 in at most 7%. If the gate fails, the Random Group Check must be changed to account for shared Markets before a Copy Verdict is shown; that is a plan change. Why: without it, Passers in shared Markets beat random groups by luck about 27% of the time instead of 5% (architecture review, 2026-10-21). (Edvard, 2026-10-21.)
>
> - Price history comes from the old price-history route while it answers with one-minute prices, else from its replacement, which keeps one-minute prices for at least 7 days only. A buy with no one-minute price is left out of that delay and counted (above); the app never silently uses coarser prices. Fetched price history is kept for good. (Architecture, 2026-10-21.)
>
> - **Fallback if the old route is gone (Edvard, 2026-10-24):** the old route is checked daily. Its replacement keeps one-minute prices for 7 days only, so a real-data Copy Test for a past Cut-off Date needs prices captured in advance. An insurance pool of 50 Wallets for the default Cut-off Date, picked by a rule written down and committed before the capture (`spike/INSURANCE-RULE.md`), is captured with every after-part buy fill's price window. If the route is gone when the real-data run is made (SM-5), the Copy Test runs on this frozen pool instead of a full Scan's Copy Pool: Passers, Copy Samples and the Random Group Check are computed by the app as usual, and the page and the README state the limits: a pool of 50 fixed in advance, not the app's Scan; the pool was ranked by the spike's estimate, not the app's final Real PnL; and with fewer than 2 Passers the Copy Verdict is *Not enough data*, reported as it comes out.

### FR-15: Mock LLM Mode

> - The tag rules give each Market exactly one Domain from its event's tags, settling overlaps by Edvard's Domain definitions. A Market whose tags are all off the map gets *Other*. (Tag rules: Edvard, 2026-11-05. One Domain per Market and the *Other* rule: AI's proposal, Edvard confirmed.)

### FR-19: Classify Markets

> - Each Market is classified once; the label is stored and reused.
>
> - Classification of a hand-labelled set of 50 Markets agrees with the hand labels on at least 80%. `[ASSUMPTION: 80% is a sensible bar]` The hand labels are made blind and committed before any model output is seen and never edited afterwards. Blind means Edvard sees only the 50 Markets' questions: no tag-rule label, no model label and no category or tag field from the data, so the gate measures the model against him, not against the tag rules. His labels are committed before either labeller runs on these 50 (Edvard, 2026-10-24). The five Domains are defined by Edvard himself, one line each saying where the overlap cases go (the AI suggests none), written first and in the same sitting as the labels, and committed together with them; the model's prompt quotes the definitions word for word (Edvard, 2026-10-24) and the tag rules are written from them, only after they are committed (Edvard, 2026-11-05). The bar applies to the language model; if the default model (Claude Haiku 5.5) misses it, a larger model is tried and both results are reported. The tag rules of Mock LLM Mode are checked on other Markets than these 50. No tag is read for the events behind these 50 until his definitions and labels are committed (Edvard, 2026-11-05). (Edvard, 2026-10-21.)
>
> - Each label is stored with its source (model name or tag rules) and date. Running the classification again is a deliberate action, never a side effect, because the model's answers can differ between runs. (Edvard, 2026-10-21.)

### FR-24: Explanation check

> Before an Explanation is shown, code checks that it names the same Verdict and the same odds phrase as the card (FR-8), and contains none of the words banned in §8 Wording. An Explanation that fails is replaced by the template text.

### 6.1 In Scope

> - **Stage 2:** FR-16 to FR-18 (Scan, Hold-up Test, Copy Test).
>
> Each stage ends with all its tests passing and the README updated, so the project is deliverable after any stage.

### 7. Success Metrics

> - **SM-5**: A Hold-up Test and a Copy Test have been run on real data, and the result is reported in the README and the reflection report, whichever way it comes out. Validates FR-16 to FR-18.

### 8. Cross-Cutting Requirements

> - **Runnable from the README**: from a fresh clone with uv installed (one documented install line; uv fetches Python 3.12 or newer itself if needed), the app starts in at most 3 documented commands (install dependencies, load the Sample Dataset, start the app). The README lists the prerequisites, the exact commands, the address to open, how keys are set in `.env`, and where each JavaScript file is and what it does. A CI job runs these exact commands on a fresh checkout and checks a Sample Wallet's Verdict. (Edvard, 2026-10-21.)
>
> - **Runs on Windows, macOS and Linux**: a GitHub Actions workflow installs the dependencies and runs the test suite on all three systems, with Python 3.12 and 3.14, on every push. The whole test suite runs with network access blocked, which also proves Offline Mode on every push. A failing run on any of them counts as a failing build.
>
> - **Database**: cached Polymarket data, Domain labels, Scans and Watchlists are kept in a database (a local SQLite file is enough, nothing to install or host). Reason: course requirement (teacher, 17 Sept 2026).
>
> - **Polite to Polymarket**: a lookup of a Wallet already stored makes 0 network calls (FR-2). Requests are paced at no more than 5 per second, a quarter of the tightest published limit on the routes the app uses (200 requests per 10 seconds for each of Data API v2's `/v2/positions`, `/v2/activity` and `/v2/prices-history`; checked on docs.polymarket.com, 2026-10-21); Polymarket slows requests that go over rather than refusing them. `[ASSUMPTION: 5 requests per second; the spike only tested one request every 1.5 seconds]` A first fetch of a Wallet's Positions takes one request per 1,000 positions or activity rows and one per 20 Markets (§9 Q1); the Cut-off Date is found with the data source's own time filter (tested, 2026-10-21). The typical spike Wallet (356 closed Positions, about 8,000 trades) needs about 30. The pace is one setting that can be turned down, and values above 5 per second are refused.
>
> - **Wording**: the app never uses words like "guaranteed", "insider" or "will win" about a Wallet.

### 9. Open Questions

> 1. ~~Which Polymarket endpoints give resolved and closed positions per Wallet with Entry Price, and how are fees, splits, merges and redemptions represented? Which Markets charge a taker fee, at what rate, and how is it computed (needed for the Follower Fee, FR-18)? Do sell fills give the Exit PnL (FR-11)? Also: the address on a profile page is usually a proxy wallet, not the signing account; check that FR-1's address check and the Data API lookups use the same address.~~ **Closed (data spike, 2026-10-21; details and evidence in `spike/FINDINGS.md`).** Closed positions (entry price, size, realized PnL, resolution time) come from the Data API's closed-positions list, 50 per request; open and unredeemed losing positions from its positions list, 500 per request; both are needed (FR-3). Resolution times and fee schedules come from the Gamma API, 20 Markets per request. Sells are trade rows with a price, so Exit PnL can be computed from them. Taker fee = shares × rate × price × (1 − price), rate 0.03 to 0.07 by category, makers pay none; the fee schedule is on each Market, and fee Markets are rare before late 2025 and common in 2026. Realized PnL is net of fees; a taker trade's cash amount includes the fee. Positions made by a split show an entry price of exactly 0.5 and have no buy trades. One address (the proxy wallet) is used by every source (FR-1). Still open, for the architecture: how splits and merges are treated in the Skill Test; the three unexplained cases where total bought is below the buy rows by 0.007% to 4%; and whether the older activity endpoint will be retired in favour of its cursor-paged v2. **Settled in architecture (2026-10-21; probes `spike/arch_probe1.py` to `arch_probe8.py`, 37 read-only requests):** Data API v1 is retired on 2026-10-24, so the app uses v2 only (Edvard: no point designing on v1 data). v2 serves closed and open positions from one list with a status filter, 1,000 rows per page, cursor-paged; its time filters were proven to work (a made-up parameter as control). Splits, merges and conversions are left out of the Skill Test and counted; gaps above 1% are left out with their size stored (FR-3). Own Fees come from the activity rows: v2 gave the same fee as v1 on all 25 fee fills checked.
>
> 2. Which public endpoint lists the top Wallets by profit for a Scan, and how far back does it go? **Decided (Edvard, 2026-10-16): a Scan ranks Wallets only on profit from Positions resolved before the Cut-off Date.** Ranking on all-time profit would let results after the Cut-off Date decide which Wallets are tested, and the Hold-up Test would be rigged. **Was open for the data spike (closed below, 2026-10-21):** (a) today's leaderboard shows only survivors, the Wallets that are still active and profitable, so a list taken from it is a survivor sample; the spike must also find an older list of Wallets, or another way to list Wallets as they were before the Cut-off Date; (b) whether an endpoint can rank by profit up to a date at all, or the app must compute that profit itself from each Wallet's Positions. **Knock-on, applied:** FR-16, FR-17 and UJ-4 now take the Cut-off Date when the Scan starts; a different date means a new Scan. (Data spike, before architecture.) **Closed (data spike, 2026-10-21; `spike/FINDINGS.md`; decided by Edvard the same day):** the leaderboard has no date setting (the official reference lists none) and shows only today's survivors, so it is not used for a Scan. A Scan builds its candidate list from the trades in Markets resolved before the Cut-off Date (Markets are listed through the Gamma API, traders through the Data API's trades list with an end time; one query reaches only the newest 10,000 or so trades of a Market, and moving the end time back reaches earlier ones, so large Markets are sampled across their life) and computes each candidate's profit from its closed and open Positions. This includes Wallets that later went quiet or lost money. Sampling matters: in a test on 10 large Markets, the last 1,000 trades before close gave 331 Wallets that appeared in two or more Markets, and 1,000 trades spread over each Market's life gave 216. Cost: listing candidates is cheap; the cost is fetching each candidate's history, so a first Scan is slow and a per-Wallet limit is needed (FR-16). The leaderboard is still usable for the lookup page. **Changed (Edvard, 2026-10-23):** it is not used to choose the Sample Dataset's real Wallets either, because it ranks on results from after the Cut-off Date; they come from the same funnel as a Scan, judged on the before part only (Q5). **Changed in architecture (2026-10-21):** the trade walk-back does not work on Data API v2 (a Market's trades ignore the end time; tested with a control). The candidates now come from each Market's own list of positions, closed and still held, which includes losers (on a $71M Market, 874 of 995 Wallets had lost); a partly read Market gives no candidates. The funnel is in FR-16. (Edvard: better than the old method, because it gets the losers too.)
>
> 3. ~~Does Polymarket's price history have minute-level prices for resolved Markets, far enough back for the Copy Test? The Random Group Check needs these prices for the after part of every Wallet in the Copy Pool (up to the whole Scan, about 200 Wallets), not just the Passers, so expect many more requests and a larger Sample Dataset. If only coarser data exists, the Copy Delays and the Main Copy Delay change, and the new Main Copy Delay is fixed before any data is looked at. (Data spike, before architecture.)~~ **Closed (data spike, 2026-10-21; `spike/FINDINGS.md`).** Yes: one-minute price points exist for resolved Markets from mid-2023, one request covers 14 days of one outcome, and the Copy Delays (1, 5 and 30 minutes) and the Main Copy Delay (5 minutes) stay as they are. Thin Markets get filled-in flat prices, and the history is the midpoint of buyers' and sellers' prices (FR-18 Spread Allowance). **Measured cost.** Price requests are per outcome, not per bet: for one Wallet, 336 of 352 outcomes needed a single 14-day window (1.06 requests per outcome). For 7 Wallets drawn at random from the candidate list and ranked in the top 3,000 all-time, the reading was capped at each Wallet's oldest 2,000 closed Positions, so the counts are floors: 6 of 7 hit the cap, and after-the-example-cut-off outcomes were 145, 551 and 1,292 for the three Wallets whose later Positions were read (the other four showed none only because the cap stopped the reading earlier). The 7 Wallets shared only about 5% of their outcomes. So a Copy Pool of a whole 200-Wallet Scan means roughly 30,000 to more than 250,000 price requests, which is hours to days at one request per 1.5 seconds. **Decided (Edvard, 2026-10-21): a mix.** The Copy Test prices a Copy Sample of at most 100 after Positions per Wallet (Glossary, FR-18), and requests are paced faster, at up to 5 per second (§8). That makes a 200-Wallet Copy Pool at most about 20,000 price requests, roughly 70 minutes at 5 per second, against the 30,000 to over 250,000 above. The default Scan size stays 200. **Decided the same day for big Wallets:** they are kept and ranked on their latest 2,000 Positions before the Cut-off Date, as a stated limitation (FR-16, FR-11). **Still open for architecture:** the after part of big Wallets for the Hold-up Test is still fetched in full (up to a few dozen requests per Wallet, for about 200 Wallets); whether a lookup of one very large Wallet (outside a Scan) also uses the latest 2,000 Positions. **Settled in architecture (2026-10-21, Edvard):** one rule everywhere, the 2,000 Positions closest to the Cut-off Date on each side (latest 2,000 before, first 2,000 after); a lookup uses the latest 2,000 overall. **New risk (2026-10-21):** on 2026-09-04 Polymarket replaced the price-history route with one that keeps one-minute prices for at least 7 days only (5-minute for 60 days, 30-minute for 90). The old route still answers. The Sample Dataset's price history is therefore fetched as early as possible and kept for good (FR-12, FR-18). Copying every buy fill instead of one buy per Position does not change the request count when fills are packed into 14-day requests (measured on the typical Wallet: 1.06 requests per outcome either way).
>
> 4. ~~Is the app acceptable to examine in Mock LLM Mode, which is what runs when no key is set (FR-15)?~~ **Closed (decided by Edvard, 2026-10-16): yes.** Domain labels then come from tag rules (keyword rules until 2026-11-05) and Explanations from templates, so stage 3 shows the structure but not the model's quality. That is acceptable as long as the README says exactly how to set a key (§8). The choice of language model is a proposal in `addendum.md`, to confirm in architecture.
>
> 5. Which 10 real Wallets go into the Sample Dataset? They should cover each Verdict. (Owner: Edvard, after the data spike, before the Sample Dataset is built.) **Decided (Edvard, 2026-10-23):** 10 Wallets from the Scan funnel for the default Cut-off Date (Markets resolved in the 90 days before it, top 100 by volume), picked on the before part only; the only after-part data used were activity counts, to check that each Wallet has bets after the date (FR-12) and that one paid fees (FR-4). No real Wallet was estimated *Skilled (high confidence)*, so the Synthetic Wallets cover that Verdict. Three spare Wallets' price windows are captured as insurance only; a later swap needs a data reason and is logged. Method, list and counts: `spike/FINDINGS.md`, *Sample Dataset pick*.
>
> 6. Which Cut-off Date for the real-data Hold-up Test? It must leave enough bets in the after part and enough in the before part, and the Minimum After-bets should not drop most of the Passers. **Decided (Edvard, 2026-10-16): the date chosen here is the Sample Dataset's one default Cut-off Date, used by the offline checks in FR-12 and FR-16; online, any date can be chosen.** The value itself is still open. **Constraint from the data spike (2026-10-21):** price history at one-minute resolution exists only from mid-2023 (Markets resolved in July 2023 had it; January 2023 and earlier had none), and the Copy Test needs prices around the buys in the after part, so the default Cut-off Date must be after 1 July 2023. (Owner: Edvard, after the data spike, when real Wallets are picked.) **Decided (Edvard, 2026-10-23): 1 July 2025**, set before any Wallet was looked at. Why: about 2 years before it and 16 months after it, all after-part buys inside the range where one-minute prices were found, and a funnel window (April to June 2025) with a normal mix of Markets instead of one event such as the 2024 US election.
>
> 7. Maybe later: should the app report a measured luck-pass rate for top-by-profit picks? Run the same top-by-profit selection on a population of coin-flipper Synthetic Wallets and show the share that pass, next to the Minimum Luck Passes. Not in v1 scope; revisit if time allows after stage 2.

### 10. Assumptions Index

> Each is a starting value, not measured. Edvard confirms or changes it once real data exists (after the data spike); a change goes in the memlog first.
>
> - §3, §4.5 FR-18: the Random Group Check needs at least 1,000 different possible groups to give a Copy Verdict.
>
> - §4.5 FR-16: 200 Wallets is a sensible default Scan size (fetch cost now measured, §9 Q3; the value itself is not).
>
> - §8: requests are paced at no more than 5 per second (untested above one every 1.5 seconds).
>
> - §3, §4.5 FR-18: the Spread Allowance is half a cent (0.005) per share; measured in large liquid Markets only.
