# AI session log, 2026-10-12: brief revision and PRD draft

- **Tool**: Claude Code (model Claude Opus 5.5) in the Claude desktop app.
- **Student**: Edvard Tokle (G44).
- **Note on the format**: this session also covered work outside the course, so the full transcript is not in the repository. This file is the course part: the student's prompts (lightly condensed, original wording kept), what the AI proposed, and what the student decided. From the next session on, school work runs in a separate chat whose transcripts are saved here in full.

## 1. Setting up the repository

**Prompt**: "I want to work on my school project, which is on a different GitHub account. Can we keep my personal projects and the school account separate, but still work on the school project from here?"

**AI**: found that every commit on the PC used the school email, set git to use the personal identity by default and the school identity (Cludegruppa22) for everything under `Desktop/school/`, and cloned this repository there.

**Decision (student)**: tried VS Code with the Claude Code extension, found it clunky, and chose to keep working in the Claude desktop app instead.

## 2. Revising the product brief after the feedback

**AI**: read `tilbakemelding-product-brief.md` and summarised the three must-fix points: testable success criteria, a way to verify that the randomisation test is implemented correctly, and an app the examiner can run without our keys or a live API.

**Prompt**: "What do you mean 'fix it', did you have a solution?"

**AI proposed**:
- Concrete, testable criteria (random wallets must not be called skilled; too little data shows "not enough data"; same seed gives the same result; the AI explanation must match the statistics).
- **Replacing the shuffle test** with a simulation at the price paid. A no-skill trader wins as often as the market price says, so the test simulates outcomes at those odds 10,000 times. Reason: one formula, and small cases can be checked by hand, so tests can prove the code right. This answers the feedback's point that a shuffle test "can look right and still be wrong".
- Synthetic test wallets with known answers, a saved sample dataset, and a mock mode for the language model.
- Splitting v1 into three stages and choosing one primary user.

**Prompt**: "Yeah go ahead, write it in English."

**AI checked its own numbers before committing**: the first draft required the hand-check wallet's p-value to be within ±0.0005 of 0.001. That tolerance was too tight for a 10,000-run simulation (it would fail roughly 1 run in 10), so it was widened to 0.0003–0.002. The sharp-trader figure (70 of 100 wins at 50¢ by luck: p ≈ 0.00004) was verified with an exact binomial calculation.

**Result**: commit `39ba982` "Revider product brief etter tilbakemelding".

## 3. Starting the PRD

**AI**: started the BMAD PRD workflow (`bmad-prd`, Create intent) and asked about working mode.

**Prompt**: "Just draft the whole thing and I'll review it."

**Decision (student)**: fast path. The AI drafts the full PRD from the brief with `[ASSUMPTION]` tags, and the student reviews.

## 4. Changing direction: making the tool useful for real trading

**Prompt** (condensed): "Can we make this something that's actually useful for trading on Polymarket, not just a school exercise? It feels like the plan has drifted a bit from the original idea. Let's talk it through before we commit and push anything."

**AI proposed**:
- Keep stage 1 (one wallet, one verdict) as the safety net.
- Add a new **stage 2** answering the money question: a **scan** of the top wallets that produces a private watchlist of the ones that pass the test; a **hold-up test** (judge wallets on bets before a cut-off date, then check whether the "skilled" ones kept winning after it); and a **copy test** on paper (what a follower would have made copying each bet 1, 5 and 30 minutes late at the real price then).
- Move market domains, bot flags and AI explanations to stage 3.
- **No automated on-chain trading** in the project: the examiner must be able to run the app without our keys or money, and an analysis tool should not place trades.

**Prompt** (condensed): "Paper results can differ from real execution: there's latency, and some wallets' edge is pure speed. Let's test it properly on paper first."

**Decision (student)**: agreed. The copy test with delays covers the latency question on paper; real-money testing is outside the project. The student asked the AI to make the stage-2 call: **adopted**.

## 5. Checking the grading rules

**Prompt**: "Does the course want the AI chat logs handed in? Can you check?"

**AI**: read the course's Canvas pages and the grading guide for part 1. Findings: saved prompts and AI sessions in the repository are graded under "Prosess og KI-styring" (30% of part 1); so are BMAD documents that are actually updated, small commits over time, and documented decisions.

**Decisions (student)**:
- Save this log.
- Add a `CLAUDE.md` with the grading rules (the teacher's tip).
- Update the brief and the PRD with the new stage 2.
- Push it in small commits.
- Run future school work in its own chat so full transcripts can be saved.
