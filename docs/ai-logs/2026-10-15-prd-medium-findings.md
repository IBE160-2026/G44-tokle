# AI session log, 2026-10-15: the remaining medium findings of the PRD validation

- **Tool**: Claude Code (model Claude Sonnet 5.5) in the VS Code extension.
- **Student**: Edvard Tokle (G44).
- **What this covers**: the six medium findings that were still open in `prds/prd-LiquidOracle-2026-10-12/validation-report.md` (the seventh, the Copy Test luck check, was done on 2026-10-14, see `2026-10-14-copy-test-luck-check.md`). Changes to the PRD, the addendum and the brief (revision 5). Prompts are the student's own wording. Where the AI proposed something and the student changed it, that is marked.

## 1. How the session worked

**Prompt**: "the luck check pr is merged, so pull main and make a new branch. also yes to the comparison group like u set it up. next do the remaining medium findings from the validation report. go thru them one at a time, tell me what u'd change and why, and wait for my ok before editing"

The AI pulled main (PR #2 merged), made the branch `prd-medium-findings`, and recorded the student's yes to the Comparison Group in the PRD memlog. Then for each finding it described the problem, the change and the reason, with a recommendation, and edited only after the student's answer. Every finding has its own memlog entry in the PRD `.memlog.md`.

## 2. The six findings, and what the student decided

| # | Finding | What the AI proposed | The student's decision |
|---|---|---|---|
| 1 | "About 2 of 200" is a floor, not an estimate | Rename Expected Luck Passes to **Minimum Luck Passes**, word it as "at least about 2 of 200, probably more", add a clause on selection to the FR-11 limits note. Skip the optional calibration run on fake coin-flippers. | Approved all four edits. **Added**: the calibration idea goes in as Open Question 7, "maybe later", so it is not forgotten. |
| 2 | Mock LLM Mode is built in stage 1 but used in stage 3 | Move FR-15 to stage 3. Two options for the ID: **A** keep FR-15, **B** renumber stage 2. AI recommended A (the public logs already say FR-18 = Copy Test). Also fix the brief's success criterion 7. | Chose **A** and approved the brief fix. |
| 3 | Sample Dataset has no price history or after-cut-off bets | Add price history and both sides of the Cut-off Date to the glossary term and FR-12, price paths to FR-13, speed trader to FR-16, a size note in the addendum with no number. | Approved. |
| 4 | Stage 3 requirements are looser than stages 1 and 2 | Concrete wording for FR-20, FR-22 (three Flag rules, at least 2 must hold), FR-23 (60 words), FR-24 and UJ-5. The AI offered to drop the inventory rule to keep it simpler, and recommended keeping all three. | Chose **all 3 rules**. |
| 5 | Section 8 requirements are adjectives | At most 3 commands from a fresh clone; 0 network calls for a stored Wallet and a placeholder N for a first lookup; README must list prerequisites, commands and keys. Platforms: "tested on Windows 11, macOS and Linux expected to work, not verified". | Approved, 3 commands is fine. **Changed** the platform line: instead of "not verified", a GitHub Actions workflow runs the tests on Windows, macOS and Linux on every push, so it is verified. Requirement only; the workflow is built later. |
| 6 | Synthetic Wallet table only in the brief | Copy the 11 rows into the PRD with a "Used by" column, add a Split-domain trader row for FR-20, leave the brief alone. | Approved. **Changed**: the new row goes into the brief table too, so the two tables match. |

## 3. Things the AI did that went a little beyond the question, and what was caught

- **Brief criterion 9** said "expected number of luck passes", which would contradict the renamed term. The AI fixed that phrase together with the criterion 7 fix, and told the student in the next reply ("the two brief phrases").
- **UJ-5 arithmetic**: while rewriting UJ-5 the AI noticed that its domain rows (180 + 150 + 22) did not add up to the 400 bets in the text, and changed the total to 352.
- **A slip, caught by a check**: when copying the brief's table into the PRD the AI changed two result cells to the glossary names (*Likely skilled* or better; *Skilled (high confidence)*), so the tables no longer matched, which the student had just asked for. The AI compared the two tables with a short script, found the differences, and changed the same two cells in the brief. FR-13 also still said "plus one the brief does not list" (the stop-loss trader, which the brief has listed since revision 3); that sentence was removed.
- **"Used by" column**: the AI's chat proposal for the column left FR-22 off the coin-flipper and sharp-trader rows; the file has it, because FR-22 says neither is Flagged.
- **Numbers that are the AI's, not measured**: the three Flag thresholds (30%, 80%, 1 hour) and the 60 words are tagged `[ASSUMPTION]` and listed in the Assumptions Index. The Split-domain trader's 42 of 60 and 30 of 60 are the AI's fixture design: p is about 0.001 for crypto (about 0.002 after the correction for two domains), and 30 of 60 is plainly luck.

## 4. What changed

- **PRD** (`prd.md`, `.memlog.md`, `addendum.md`): Minimum Luck Passes; FR-15 moved to §4.6 with its ID kept; UJ-3 and SM-2 and §6.1 follow; Sample Dataset term, FR-12, FR-13, FR-16; the Synthetic Wallet table under FR-13; FR-20 and FR-22 to FR-24 and UJ-5; §8; Open Question 7; two new Assumptions Index lines.
- **Brief** (`brief.md`, `.memlog.md`): revision 5 note at the top, criteria 7 and 9, the Split-domain row, two cells aligned with the glossary.
- **Still open** from the validation report: the 5 low findings and the mechanical notes (Assumptions Index roundtrip, glossary drift).
