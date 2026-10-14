# AI session log, 2026-10-14: a luck check for the Copy Test

- **Tool**: Claude Code (model Claude Opus 5.5) in the VS Code extension.
- **Student**: Edvard Tokle (G44).
- **What this covers**: one of the medium findings from the PRD validation (`prds/prd-LiquidOracle-2026-10-12/validation-report.md`): "The Copy Test reports profit without a luck check". Changes to the brief (revision 4) and the PRD (FR-18 and the terms around it). Prompts are the student's own wording. Where the AI proposed something and the student changed it, that is marked.

## 1. The task

**Prompt**: "next up is the luck check on the copy test. compare the passers to random groups of the same size picked from the scanned wallets, do it a bunch of times and see how often a random group does just as good. use profit after fees, not win rate, win rate can look good even when they lose money. tell me ur plan before u change anything"

The validation report had suggested a different fix: run the Skill Test on the follower's prices (the price 1, 5 or 30 minutes after the wallet bought) and give each delay its own p-value. The student chose his own method instead: compare the passing wallets with random groups of wallets from the same scan. The AI recommended going with the student's method, because it answers the follower's actual question ("is copying these wallets better than copying wallets picked at random?").

## 2. The AI's plan and four decisions

The AI proposed the method in five steps: a pool of scanned wallets with enough later bets (the Passers included), the Passers' score after fees at each delay, 10,000 random groups of the same size, a p-value with the same "+1" formula as the Skill Test, and a seed so the result can be repeated. It asked about four points, giving a recommendation for each:

1. **Score = average return per wallet** (profit after fees ÷ money spent), not total dollars. Reason: with total dollars, one very large wallet in a random group decides the result, and the test measures wallet size instead of skill.
2. **Fees**: the follower pays Polymarket's fee at the market's recorded rate, 0 where there is none. The exact formula is left to the data spike (PRD Open Question 1).
3. **Not enough data** when fewer than 1,000 different groups can be drawn. Otherwise almost every random group is the Passers themselves and the test means nothing. The 1,000 is the AI's placeholder, tagged `[ASSUMPTION]`.
4. **Per-wallet copy profits stay on the page**, but marked as not luck-checked. Only the group result is.

The AI also pointed out a cost: minute-level prices are now needed for every wallet in the pool (about 200), not just the Passers. That means more requests and a bigger sample dataset. This was added to Open Question 3.

## 3. The student's decision and correction

**Prompt**: "yes to all 4. one thing tho, with 3 delays we get 3 tries, so one could pass just by luck. pick one main delay before we look at any data, i'd say 5 min, and the result only counts on that one. the other 2 just show on the page as extra info. go ahead after that"

**Decision (student)**: accepted the four proposals, and **corrected** a gap the AI's plan had missed. The plan gave a luck check at each of the three delays, which gives luck three chances to pass. The student fixed the 5-minute delay in advance as the **Main Copy Delay**, the only one that gives a verdict. The 1- and 30-minute delays now only show the profit and return, marked as extra information. If the data spike shows that only coarser prices exist, a new main delay must also be chosen before any data is looked at.

## 4. What changed

- **Brief**, revision 4: a new step 4 in *Is Skill Worth Following?* (the luck check), fees included in the copy test, the limitation line no longer says fees are ignored, and success criterion 11 got the two planted-scan checks.
- **PRD**:
  - New glossary terms: Main Copy Delay, Follower Fee, Follower Return, Copy Pool and Random Group Check. Follower PnL and Copy Test are updated.
  - FR-18 got new test bullets: a hand-calculated fee example; a planted scan of forecasters against coin-flippers must give p < 0.01; across 1,000 planted scans of coin-flippers only, p < 0.05 at most 7% of the time (so the check doesn't call luck skill too often); a too-small pool shows *Not enough data*; the same seed gives the same result; only the main delay gives a verdict.
  - Also updated: UJ-4, SM-4, Open Questions 1 and 3, and the assumptions index.
- **Memlogs**: one entry each in the brief and PRD `.memlog.md`, naming which parts came from the student and which from the AI.
