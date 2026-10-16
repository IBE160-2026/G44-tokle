# AI session log, 2026-10-16: brief revision 7 and finalising the PRD

- **Tool**: Claude Code (model Claude Sonnet 5.5) in the VS Code extension.
- **Student**: Edvard Tokle (G44).
- **What this covers**: bringing the brief in line with the PRD (revision 7), going through everything still open in the PRD, and setting `status: final`.
- **Result**: brief revision 7 (status stays final), PRD `status: final`. Branch `brief-rev7-prd-final`.

## 1. The prompt

> "new chat, read HANDOFF.local.md first. the low findings pr is merged, so pull main and make a new branch. first do the brief revision 7 so it matches the prd. then lets finish the prd: go thru whats still open, tell me what needs my call, then mark it final. show me before committing"

The AI pulled main (PR #4 merged), made the branch, and read the brief, the PRD, the addendum and both memlogs before changing anything.

## 2. Brief revision 7

The AI read the brief and the PRD side by side. The known gap was the Scan order (the cut-off date now comes first, after the student's Q2 decision). It found three more differences, and the student's instruction was to make the brief match the PRD, so all four went into revision 7:

| What differed | Change in the brief |
|---|---|
| Scan took the cut-off date after the scan; PRD ranks only on profit before it (FR-16, FR-17) | Cut-off date picked first, ranking on profit from before it, a new date means a new scan |
| The scan description still said "about 2 are expected to pass" (revision 5 had fixed only success criterion 9) | "at least about 2, probably more, because the scan picks wallets for high profit"; same in the Solution list |
| Comparison group: PRD leaves out wallets with too few positions before the cut-off | One clause added |
| Success criterion 9 lacked the speed-trader wallet that FR-16 requires on the Watchlist | Added |

A database line was *not* added to the brief: the brief says "caches locally", the PRD §8 and the addendum name SQLite, and the brief describes the product, not the storage. The student can overrule this.

## 3. Memlog audit: a lost edit found

Before finalising, the AI checked all 39 memlog entries of the PRD against `prd.md`. **One was missing.** The FR-9 luck-chart bullets, which the student approved earlier today ("yes go ahead"), were in the memlog and in the log of the low-findings session, but had never been written to the PRD file. The AI of that session said it was applied; it was not.

- **What was done:** the approved wording was put into FR-9 unchanged, and the PRD memlog got a `correction` entry.
- **Why it was caught:** the audit is step 1 of the PRD skill's Finalize sequence. Reading the file and not the log is what found it.
- **Left as is:** the earlier log (`2026-10-16-prd-low-findings.md`) still says FR-9 was applied. Logs are not rewritten after the fact; this section is the correction.
- **Lesson for the reflection report:** an AI's "applied" is a claim, not evidence. The check that counts is reading the file.

## 4. What was still open, and the student's decisions

The AI listed what needed the student's call and recommended an answer for each.

| # | Item | AI recommendation | Student's decision |
|---|---|---|---|
| 1 | Finalise the PRD before the data spike? Q1, Q2 (a)(b) and Q3 need the spike; they block architecture, not UX. Main risk: Q2 (if no older list of wallets exists, FR-16 must change) | Yes, finalise now; if the spike changes an FR, plan first via memlog and bump `updated` | OK |
| 2 | `[NOTE FOR PM]` in FR-3 | Keep the text, drop the tag, call it "Known limit (decided)" (FR-11 and §6.2 already handle it) | OK |
| 3 | The cut-off date is now user-chosen, but FR-12 and FR-16 promise specific offline results | The Sample Dataset ships with one default cut-off date, decided in Q6; online any date | OK |
| 4 | The ~3% (Yale SOM study): check against the paper | The student opens the SSRN link, or the addendum is reworded to say the paper was not read | First: reword, say the paper was not read and add no other numbers. Later the same session: the student opened the paper himself and supplied the figures (see below) |

**Where the AI corrected the student's premise.** The student's first wording was that the 3.14% comes from the Yale write-up. The AI fetched the page before writing it: the Yale Insights article (by a journalist, quoting the authors) says "just 3%" and does not contain 3.14%. The 3.14% and the 2023-to-2025 data period are in The Block's coverage. SSRN returned an access error to the AI, so it could not read the paper. The addendum was reworded to say exactly this.

**The student then read the paper.** He opened the SSRN page and found a newer version, dated 25 June 2026: about 3% skilled in the abstract, 3.2% in the introduction, and 46% of the skilled accounts staying skilled out of sample against 10% for mutual funds. The 3.14% was in the April version that The Block covered. His instruction: use the June version in the addendum, take out the "paper not read" wording, check the brief and PRD for the old figure, and update this log.

What the AI did and did not do:
- The AI **has not read the paper**; the figures in the addendum are as the student reported them, and the addendum says he read it. They are not independently checked by the AI.
- The AI searched the brief and PRD bodies for 3.14, 3.2, 44 and 46 (the student wrote "44%" in one place and "46%" in another, so both were searched). None are there. Their "~3%" matches the abstract, so they were not changed.
- The AI added one sentence of its own to the addendum: the 46% / 10% is context for the Hold-up Test (SM-5), not a target (SM-C2 already says a negative result is valid). The student can drop it.

**Deferred, with owner and revisit condition** (logged in the memlog, a note added at the top of §10): the 10 `[ASSUMPTION]` values (Edvard, after the data spike, when real data exists); Q1, Q2 (a)(b), Q3 (data spike, before architecture); Q5 and Q6 (after the spike, when real wallets are picked); Q7 (maybe later, after stage 2); the GitHub Actions restriction (checked when the workflow is built).

**Not done:** a second reviewer pass. The checklist validation's 16 findings were fixed and seen earlier, and the AI checked the Q2 knock-on by hand against the memlog.

## 5. Result

- PRD `status: final`. Brief revision 7, status final.
- Addendum cites the 25 June 2026 version of the paper, read by the student. The PRD and brief bodies needed no change.
- A one-line note was added to the earlier log (`2026-10-16-prd-low-findings.md`) saying FR-9 was only written in this session.
- The data spike is the next step before architecture. The UX session must read PRD §8 "Pages, navigation and accessibility" first.
