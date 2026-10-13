# AI session log, 2026-10-12 to 2026-10-13: validating the PRD and fixing the findings

- **Tool**: Claude Code (model Claude Sonnet 5.5) in the VS Code extension.
- **Student**: Edvard Tokle (G44).
- **What this covers**: a review of the PRD draft with the BMAD checklist reviewer, and the changes made to the PRD, the addendum and the brief after it. Prompts are the student's own wording. Where the AI proposed something and the student changed it, that is marked.

## 1. Running the review

**Prompt**: "let's review the PRD, just the checklist reviewer, no extra agents"

**AI**: used the `bmad-prd` skill in Validate mode and ran only its rubric walker (the "checklist reviewer": seven dimensions, scored strong / adequate / thin / broken). No other reviewers are configured for this PRD, and the AI ran the walk itself in the main session instead of starting a subagent, because the prompt said no extra agents. It read the PRD, the addendum, the memlog and the brief the PRD builds on.

**Result**: grade **Fair**, 16 findings (0 critical, 3 high, 7 medium, 6 low). Files: `validation-report.html`, `validation-report.md` and `review-rubric.md` in the PRD folder. The three high findings:

1. No database requirement in the PRD, although the teacher requires one (17 Sept); the addendum still allowed "local files".
2. Positions sold before resolution are left out of the Skill Test, and this can make a wallet look better than it is (a trader who sells losers early keeps only the winners in the sample).
3. The Hold-up Test is defined on two different groups of wallets ("the Watchlist" versus wallets that passed on bets before the cut-off date), so it could grade wallets on the same bets that selected them.

## 2. Decisions, one finding at a time

**Finding 1, database.** AI proposed a line in §8, "stored in the database" in FR-2 and FR-16, and SQLite in the addendum, tagged as an assumption.
**Prompt**: "yes, and drop the [ASSUMPTION] tag on SQLite, that's decided"
**Decision (student)**: accepted, and **changed** the proposal: SQLite is a decision, not an assumption. The addendum now says so.

**Finding 2, sold positions.** AI recommended accepting the limit in v1 and making it visible: a note at FR-3, "N of M held to resolution" and the realised PnL of the sold positions on the card (named Exit PnL), a stop-loss synthetic wallet to demonstrate it, and a wording fix in §6.2.
**Prompt**: "yes, and add: if the positions sold before resolution lost money in total, the card shows a visible warning next to the verdict"
**Decision (student)**: accepted, and **added** a requirement of their own: a visible warning next to the Verdict when Exit PnL is below zero. It is now in FR-11 with a test (the stop-loss wallet shows it; wallets with no early sales show none).

**Finding 3, Hold-up Test.** AI proposed a new term, Before-Cut-off Passers (wallets rated using only bets that resolved before the cut-off date), and the rule that the after part is bets opened on or after the date.
**Prompt**: "yes go for it. also make sure the comparison group is picked the same way, only from bets before the date, and checked on the same later bets, otherwise it's not a fair comparison. and yeah add the stop-loss wallet to the brief too"
**Decision (student)**: accepted, and **added** that the Comparison Group follows the same rule, plus the stop-loss wallet in the brief's synthetic-wallet table. The brief also got a revision note.

**Fairness of the after part.**
**Prompt**: "the wallets need the same rules for the bets after the date too, like the same minimum number of bets to count, and the ones that stop betting get treated the same in both groups. otherwise the winners might just be the ones who bet more."
**Decision (student)**: new requirement in FR-17. The same Minimum After-bets applies to both groups, wallets that stop betting are dropped by the same rule in both, and each group's result shows wallets counted, wallets dropped and positions counted. The number 10 is the AI's placeholder and is tagged `[ASSUMPTION]`.

**Follow-up** (next day)
**Prompt**: "10 is fine for now but write a line on why 10. also if way more wallets get dropped in one group than the other, the page should say that, cuz the ones who quit might be the ones who lost."
**Decision (student)**: kept 10 and asked for the reason to be written down. The AI wrote it honestly as a round starting value that is not measured and is to be revisited with real data. The student also **added** a new requirement: the page must say so when the share of dropped wallets differs a lot between the groups. "A lot" was left to the AI, which proposed 20 percentage points, tagged `[ASSUMPTION]` (the AI's number, not the student's).

## 3. Things the AI chose that the student should check

- The Comparison Group is defined as scanned wallets rated *Likely skilled* or *No evidence of skill*; wallets with *Not enough data* before the date are in neither group.
- FR-17 now says *Skilled (high confidence)* where it said *Skilled* (wording drift found by the review).
- The reasoning behind finding 2 (selection bias from early exits) and the finding that "about 2 of 200 would pass by luck alone" is a floor, not an estimate, is the AI's argument. It has not been checked by simulation. The second one is still open.

## 4. Where this leaves the plan

- Files changed: `prd.md`, `addendum.md`, the PRD memlog, `brief.md` and the brief memlog. Every change has a memlog line with the reason.
- Still open from the review: 7 medium and 5 low findings (the report said 6 low; one of them, §6.2 versus FR-3, was fixed along the way, which the student checked). Next up (student's call): a luck check on the Copy Test.
- Housekeeping the student asked for: the FR-11 stop-loss check was moved out of the list of things the card shows into its own "Checks" list; the generated HTML report is kept out of git because the `.md` has the same content.
