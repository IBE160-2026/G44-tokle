# AI session log, 2026-10-16: the five low findings and the mechanical notes of the PRD validation

- **Tool**: Claude Code (model Claude Sonnet 5.5) in the VS Code extension.
- **Student**: Edvard Tokle (G44).
- **What this covers**: the five low findings that were still open in `prds/prd-LiquidOracle-2026-10-12/validation-report.md` (the sixth, §6.2 "sold positions", was fixed earlier) and the report's mechanical notes. Changes to the PRD, the addendum and the brief (revision 6, wording only). Prompts are the student's own wording. Where the AI proposed something and the student changed it, that is marked.

## 1. How the session worked

**Prompt**: "new chat, read HANDOFF.local.md first. the medium findings pr is merged, so pull main and make a new branch. next do the 5 low findings, same as before, one at a time, wait for my ok before editing"

The AI pulled main (PR #3 merged), made the branch `prd-low-findings`, and went through the findings in the order of the handoff. For each one it described the problem, the change and the reason, with a recommendation, and edited only after the student's answer. Every finding has its own memlog entry in the PRD `.memlog.md`.

For the mechanical notes the student asked for them to be done in one go ("then do the mechanical notes from the report, and show me the diff n the log when ur done"), so those were not reviewed item by item. The diff is shown before anything is committed.

## 2. The five findings, and what the student decided

| # | Finding | What the AI proposed | The student's decision |
|---|---|---|---|
| 1 | Open Question 4 ("which language model?") answers itself | Keep Q4 at its number (Q6 and the addendum refer to question numbers) but turn it into a real question: is Mock LLM Mode acceptable for the examiner? Move the model choice and the cost note to the addendum as "to confirm in architecture". | Approved, and **answered the question himself**: yes, as long as the README says exactly how to set a key. Q4 is closed in place with that answer. |
| 2 | SM-7 ("every shown Explanation passes the check") is true by construction | Measure the replacement rate (share of Explanations the check replaces by the template), report it in the README, no target; add a counting bullet to FR-24. | Approved. |
| 3 | The luck chart has no checkable consequence (FR-9) | Axis in dollars with a range that always includes the Real PnL; marker labelled "above all 10,000 Simulations" (or "below"); a test with a planted Real PnL above the largest Simulation. | Approved. |
| 4 | "About 1 time in N" has no rounding rule or floor (FR-8) | N = 1 / p rounded to 2 significant figures; "fewer than 1 time in 10,000" when no Simulation reached the Real PnL; "more than 1 time in 2" when p is above 0.5; FR-24 compares "the same odds phrase". | Approved with one **change**: "more than half the time" instead of "more than 1 time in 2". |
| 5 | Pages, navigation and accessibility are not mentioned (§8) | One §8 bullet: pages and navigation are specified in the UX step (with a list it must cover); the Verdict is never shown by colour alone; the luck chart has a text alternative. The handoff tells the UX session to read it first. | Approved. |

## 3. The mechanical notes

All done in one pass, then shown to the student:

- **Assumptions Index roundtrip**: FR-16's 200 Wallets got an inline `[ASSUMPTION]` tag; the FR-3 tag and the Minimum After-bets tag (same defect, not in the report) now carry their text. The "runs locally as a web page" entry pointed at sections that never said it, so §8 got a "Runs locally" bullet and the index points there. Now 10 inline tags, 10 index entries, one for one.
- **Glossary drift**: SM-C1 says *Skilled (high confidence)*. The brief's success criteria 2 and 10 had the same drift, so they were reworded (brief revision 6, wording only).
- **Terms not in the glossary**: "top Wallets by profit" now points at Open Question 2, which also asks over what period the profit is measured (see below). The Domain *other* was already in the glossary and FR-20, so nothing was done.
- **Proxy wallet**: one sentence added to Open Question 1 for the data spike.
- **Yale SOM source**: a Sources entry in the addendum (see below).
- **Memlog**: the old "draft written" entry has out-of-date counts; the log is append-only, so a correction line was added.

## 4. Things the AI did that went a little beyond the question, and what was caught

- **Renumbering would have broken references**: deleting Open Question 4 and renumbering was the obvious fix. The AI checked first, found that the PRD refers to §9 Q6 and the addendum to Open Question 3, and kept the number.
- **A real method problem found while doing a "mechanical" note**: asked "over what period is top-by-profit measured?", the AI saw that if the Scan's Wallets are ranked by profit that includes the after-Cut-off part, then the choice of Wallets has already leaned on after-Cut-off results, even though the two groups are picked from the before part only. It did **not** decide this; it put it into Open Question 2 and asked. The student decided it in the same session (section 6).
- **The Yale figure is not verified from the original**: the AI searched for the study and found only press coverage (The Block, BeInCrypto), not the paper, and did not invent a title. The student then supplied the title and authors (section 6).
- **Beyond the report**: the Minimum After-bets tag, the "Runs locally" bullet and the brief wording edit were the AI's own additions in the mechanical pass; the student sees them in the diff.
- **Numbers that are the AI's, not measured**: none new. "2 significant figures" and "above 0.5" are display rules, not assumptions.

## 5. What changed

- **PRD** (`prd.md`, `.memlog.md`, `addendum.md`): FR-8, FR-9, FR-16, FR-24, SM-7, SM-C1, §3 (Scan, Minimum After-bets), FR-3, §8 (two new bullets), §9 (Q1, Q2, Q4), §10; addendum language-model line and Sources.
- **Brief** (`brief.md`, `.memlog.md`): revision 6 note, criteria 2 and 10.
- **Still open**: decide whether the brief gets revision 7 for the Scan/cut-off order (section 6), then finalise the PRD (Finalize steps, `status: final`) after the data spike answers Q1 to Q3 and the SSRN link is added; then `bmad-ux`, `bmad-architecture`, `bmad-create-epics-and-stories`.

## 6. After the diff review

The student read the summary of changes and answered:

- **Open Question 2, decided by the student**: "the scan ranks only on profit from before the cut-off, otherwise the hold-up test is rigged." Recorded in Q2 and in the Scan glossary entry. The AI had raised the leak but had not proposed which way to resolve it.
- **Added by the student, not raised by the AI**: today's leaderboard shows only survivors (Wallets still active and profitable), so the data spike needs an older list of Wallets too. Written into Q2 as part of what the spike must find.
- **Knock-on the AI flagged and did not apply at once**: with the ranking tied to the Cut-off Date, the Scan has to know the date before it runs. FR-16, FR-17 and UJ-4 had the Scan first and the date after. The AI proposed: the Scan takes the date when it starts, and a new date means a new Scan. The student agreed ("yes do it ur way") and asked to see all three rewordings in one go before anything was edited. The AI showed the exact old and new sentences, the student approved, and the three were changed in a separate commit. The AI also found that the brief (sections on the Scan and the Hold-up Test) still describes the Scan first and the date after; it did not edit the brief and proposed a revision 7 instead.
- **Yale paper, supplied by the student**: Gomez-Cram, Guo, Kung and Jensen, *Prediction Market Accuracy: Crowd Wisdom or Informed Minority?*, SSRN, April 2026. The AI put it in the addendum and checked it against press coverage (authors, data period and the 3.14% figure match). It did not find the SSRN page, so the link and a check of the figure against the paper are still to do.
