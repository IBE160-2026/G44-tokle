# AI session log, 2026-11-18: the teacher's PRD feedback

- **Tool**: Claude Code (model Claude Opus 5.5) in the VS Code extension, using the `bmad-prd` skill (Update intent).
- **Student**: Edvard Tokle (G44).
- **What this covers**: handling the teacher's formative feedback on the PRD (`tilbakemelding-prd.md`, 12 November), on branch `prd-feedback`, made from `main` after PR #18 (Story 1.3) was merged.
- **Result**: the PRD has a stage 2 minimum, FR-18 is split in three, FR-19 says what happens when the model fails, FR-24 points to a full word list, §9 is tidied, and technology details moved to the addendum. A new `decision-log.md` keeps every line that was changed or removed, word for word. The PRD went from 11,530 to 9,660 words. The epics and the architecture spine follow the same day.

## 1. The prompt

Edvard asked the AI to read the handoff note, then the teacher's feedback and the PRD, and to work through the feedback's points in the order the AI thought best. He wanted to hear every change *before* it was made. He set four rules: anything split or moved must still match the epics, since Stories 1.1 to 1.3 are already built on the PRD; the "why we decided this" notes must move to a decision log, not be deleted, because he wants to keep that history; for the stage 2 minimum the AI should suggest one but let him decide what counts as good enough; and the feedback's two reflection questions are his to answer, so the AI leaves them alone.

The AI read the feedback, the PRD, the addendum, the epics, and every place where code, tests, the spine and the UX documents cite PRD numbers. It then proposed a plan in four parts (scope, content, structure, tidying) and asked about the four points that needed Edvard's call.

## 2. Decisions

| # | Question | AI's recommendation | Edvard's decision |
|---|---|---|---|
| 1 | Stage 2 minimum: what counts as "good enough" if time runs short? | 2a Scan + Watchlist and 2b Hold-up Test, *including* one live real-data Hold-up run, because the Hold-up Test is stage 2's core question and needs no price history | **Changed:** 2a + 2b *offline only*; the live real-data run and the Copy Test are extra |
| 2 | Follow-up: offline only cuts less than it sounds (see section 3). Keep it? | (Information, no new recommendation) | **Kept offline only** |
| 3 | Should the README report the offline Hold-up result for the 10 real Sample Wallets, whichever way it comes out? | Yes: it is free and keeps some real data in the minimum | Yes |
| 4 | FR-19: what happens when the model fails or answers with something that is not one of the five Domains? The feedback suggested labelling the Market *Other* with source `fallback` | Reject that: it would quietly fill the *Other* Domain and skew its Domain Verdict. Instead at most 3 tries, never store a bad answer, and show "Domains are not available" instead of the table | Agreed (**rejects part of the teacher's suggestion**) |
| 5 | Length: the feedback's target was under about 6,000 words | Stop around 8,000 and keep every test check, since the checks are what the feedback praised and what the epics and code trace to | Agreed |
| 6 | Where do the moved notes go? | A new `decision-log.md` in the PRD folder; the addendum keeps technology only | Agreed |
| 7 | Plan as proposed: FR-18 split into 18a/18b/18c with "FR-18" kept as the group name; FR-24 points to the existing list in `EXPERIENCE.md`; §9 tidied; conventions marked; UJ-4 in steps; technology to the addendum | Approve | Approved |

The FR-24 point needed no new list: the UX step had already written the full one (banned plus "also avoided" words). The PRD now points to it, and the test must use every word on it.

## 3. Where the AI was wrong or had to correct itself

| Found by | Problem | What happened |
|---|---|---|
| The AI, before any edit | Its option "2a + 2b, offline only" said the live Scan funnel would be "extra". But the architecture says an offline Scan runs the same funnel as a live one (AD-14, "no offline branch"), so no Scan code is saved, only the live run and its write-up | The AI read Epic 4 again and told Edvard before writing anything. He kept his choice with the correct picture. The AI also found that the offline Scan already covers the 10 real Sample Wallets, which led to decision 3 |
| The AI, after the edit | It estimated the PRD would land around 8,000 words. It landed at 9,660 | Reported to Edvard and written into the decision log. Nothing more was cut without his say |
| The AI, planning | If the Copy Test (Epic 6) is dropped, the live real-data Hold-up run in Story 6.6 would be dropped with it | The live Hold-up run moved to a new Story 5.3, so it no longer depends on the Copy Test |
| Edvard, reviewing the log drafts | He had asked for a plain-words walkthrough before the commits. The AI made the commits and drafted the logs without giving it | The AI gave the walkthrough (stage 2 minimum, FR-18 split, FR-19 rule) before the logs were committed |

To keep "word for word" honest, the decision log's history part was not retyped: a script compared the old and new PRD and copied every changed or removed line under its old heading (96 lines in 23 sections).

## 4. Downstream checks

- **Epics:** the stage 2 minimum is in the slipping rules. Story 5.2 closes it, including the README report of the 10 real Sample Wallets. New Story 5.3 holds the live Hold-up run, and Story 6.6 is now the Copy Test only. Epic 6, the inventory and the coverage map cite FR-18a/b/c. Story 7.2 has the FR-19 failure and cost rule, and Story 8.2 tests every listed word.
- **Spine:** AD-16 got one line for model failures and the word-list source, logged in the architecture memlog.
- **Built code (Stories 1.1 to 1.3):** nothing changes. The code cites "PRD Glossary, Sliver", "PRD §9 Q6" and "FR-18". All three still exist, because FR-18 was kept as the group name and Q6 kept its number.

## 5. Not done here

- The feedback's two reflection questions are Edvard's, for the reflection report.
- Edvard skipped a full diff review. He asked instead for a plain-words walkthrough of the stage 2 minimum, the FR-18 split and the FR-19 rule (given late, see section 3).

## 6. Commits (branch `prd-feedback`)

- f1d81c1 Mark Story 1.3 done in sprint status
- 59c4c38 Update the PRD from the teacher's feedback (12 November)
- 9750800 Carry the PRD update into the epics and the spine
