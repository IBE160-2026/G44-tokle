# AI session log, 2026-10-21: architecture (bmad-architecture)

- **Tool**: Claude Code (model Claude Opus 5.5) in the VS Code extension, with subagents for the independent reviews.
- **Student**: Edvard Tokle (G44).
- **What this covers**: the BMAD architecture step: the big technical choices one at a time, read-only re-checks of the data on Polymarket's Data API v2, the architecture spine (25 rules), three independent reviews plus a second adversarial pass, and the plan changes that followed (PRD, addendum, brief revision 8, UX, data findings).
- **Transcript**: the full chat is saved as `transcripts/2026-10-21-architecture-transcript.md`, with tool output shortened.
- **Result**: `_bmad-output/planning-artifacts/architecture/architecture-LiquidOracle-2026-10-21/` (spine, memlog, reviews); `spike/arch_probe1.py` to `arch_probe8.py` and `arch_cost_fills.py`; the v2 section in `spike/FINDINGS.md`; PRD, addendum, brief, UX updated through their memlogs; branch `architecture`.

## 1. The prompt and the plan

> "new chat, read HANDOFF.local.md first. the data spike pr is merged, pull main n make a new branch. next step is bmad-architecture. read part 8 to 10 of the prd n spike/FINDINGS.md first, the open items from the spike go in here. lets go thru the big choices together before u write anything, one at a time with ur recommendation"

The AI pulled main, made the branch `architecture`, read PRD §8–10, the spike findings, the addendum and the UX items left for architecture, and proposed nine choices in order. Each came with a recommendation, the alternatives it ruled out, and a yes/no/change question. The deliverable was the spine only (the AI's recommendation, not objected to).

## 2. The nine choices

| # | Choice | AI recommendation | Student's decision and additions |
|---|---|---|---|
| 1 | Shape of the code | One Python program in layers, a pure core with no network, database or web code | Yes. **Added**: make the import rule a test that fails, not just a written rule |
| 2 | Web stack | Flask, server-rendered pages, a little plain JavaScript (FastAPI, Streamlit, React weighed) | Yes. **Added**: the README and reflection say where the JavaScript is and what it does; and "a Scan runs 70 min, that can't live inside a request" |
| 3 | Long jobs | One worker thread in the app, job state in SQLite (Celery/Redis weighed) | Yes. **Added two traps to design for**: Flask's auto-reloader starts the app twice (two workers on one job), and SQLite's "database is locked" (WAL mode, short writes, one connection per thread) |
| 4 | Data layer | One client module, one shared rate limiter, two cache lifetimes, plain `sqlite3` | Yes. **Added**: the limiter needs a lock or both threads think they are under the limit; and 5 per second is still an assumption, so make it one setting that can be turned down |
| 5 | Spike open items | See section 4 | Section 4 |
| 6 | Offline and Mock LLM Mode | One settings object; offline swaps in a different client instead of `if offline:` checks | Yes. **Added**: run the network-blocked test in CI on every push; and the page must show which mode is on, so an examiner with no key does not mistake template text for model output (the AI checked the UX docs: the gap was the Domain table) |
| 7 | Language model | Model as a setting; FR-19's 80% test decides; the AI laid out Haiku, Sonnet and Opus with prices | **Haiku 5.5 with the 80% gate; if it fails, bump and re-run, "that path is worth showing anyway"**. Added: make the hand labels before seeing any model output and never touch them. **Also asked to pin a dated model ID; the AI corrected this** (see section 7), and he accepted the alternative: store every label with its model and date and reuse it. He called that "better than what I asked for" |
| 8 | Font | IBM Plex Serif (Source Serif 4 weighed) | Yes. **Added**: a system serif after it and `font-display: swap`, so a missing font file never leaves headlines blank |
| 9 | Install and CI | uv with a lockfile, CI on three systems × two Python versions | Yes. **Added**: a CI job that runs the exact three README commands on a fresh checkout; and watch the Sample Dataset's size, because Git LFS would be an extra install step for whoever clones it |

## 3. Data API v1 is being retired: re-checking on v2

While checking whether the closed-positions list takes a date filter (choice 5), the AI found in Polymarket's docs that **Data API v1, which the whole data spike used, is retired on 24 October**, three days later.

The student's direction: "v1 dies saturday so theres no point designing on v1 data. test the market trades walkback first, thats the one that kills the scan method if it doesnt work, n if it fails find the fallback before we go on." He also asked to **prove every filter actually did something rather than accept a status 200**, since APIs often ignore unknown parameters. Every check from then on used a control: the same request with a made-up parameter.

- **The date filter on positions works**, and the control showed the trap he described: a made-up parameter returned the identical list.
- **v2's position timestamp is not the resolution time**: it is the wallet's last event, 0 to 85 hours later. Resolution time now always comes from the market data.
- **The Scan's walkback failed**: a market's trades ignore the end time on v2. **The fallback**: list each market's own positions, closed and still held. On a $71M market, 874 of 995 wallets had lost, so it includes losers. The student: "better than what we had since it gets losers too."
- **Page sizes and price history** (the 70-minute estimate rests on them): pages are now 1,000 rows, and the old price-history data was unchanged.
- In all, 37 read-only requests at one every 1.5 seconds.

His additions to the fallback:
- A market read that times out or is capped is marked partial and never counted as full coverage.
- "Sort by time, never by profit" is enforced in code like the import rule, "thats the line that sneaks survivor bias back in".

## 4. The spike's open items

| Item | AI recommendation | Student's decision and additions |
|---|---|---|
| Big wallets | One rule: the 2,000 positions closest to the cut-off on each side | Yes, and the after part is the *first* 2,000 after, not the latest. **Added**: for big wallets both sides are now a window, so this must be a stated limitation on the Verdict, not just in the memlog |
| Splits and merges | Leave them out of the Skill Test, count them, show the count | Yes, after a 2-request proof that the filter works. **Added**: apply it the same before and after the cut-off; and if a wallet has a big share left out (a market maker), the Verdict must say so |
| Unexplained size gaps | One source per number; record the gaps | Yes. **Added**: store the actual gap size, not a flag, so the 1% line can move without refetching; and tokens that only appear in trades go through the same "big share left out" rule |
| The wallet's own fee | From the trade rows, after a probe showed v2's fee field was wrong in 3 of 7 cases. The AI flagged that this exposed a hole: nothing gave the shares held at resolution | Yes, including the adjustment. **Added**: a wallet whose activity read hits the cap gets its shares-held count marked incomplete; fees are sanity-checked against the published band; and prove the activity time filter the same way, with a control |

## 5. Writing the spine and the reviews

The AI wrote the spine from the decision log and checked it itself. The student then corrected one of the AI's proposals:

- **His correction**: a fee outside the band does not make the size or entry price wrong, so the position should stay in the test, and only things that use the fee should leave it out.
- **The AI's reply**: Real PnL does subtract the fee, and Real PnL and the simulations must cover the same positions. So it proposed that the bad fee counts as 0 instead of dropping the position. He accepted.

He also asked for **an independent review "since u just reviewed ur own work n thats the doc everything else builds on"**. The AI ran three reviewers with fresh context (rubric, verification, adversarial). They found what the self-check had missed: 2 critical holes, plus 6 high in the adversarial pass. The AI checked the biggest claim itself before passing it on: Polymarket had replaced the price-history route on 4 September with one that keeps minute prices for only 7 days.

| # | Review finding | AI recommendation | Student's decision |
|---|---|---|---|
| 1 | Price-history route replaced | One function hides both routes; fetch the Sample Dataset's windows early | Yes. "v1 gave us 3 days warning so no shutdown date announced means nothing" |
| 2 | Bets in the same market simulated as independent: 7 passers in the same 40 markets counted as 280 coin flips | One random draw per market | Yes: **"exactly the fake significance this app is supposed to catch"** |
| 3 | Watchlist defined two ways in the PRD | Watchlist = both fetched windows; every result names its set | Yes |
| 4 | How a Scan narrows candidates to 200 | 90 days, top 100 markets by volume, shortlist, then rank | Yes. **Added**: the Scan page itself states the population tested |
| 5 | A partial market read can lean on winners | A partial market gives no candidates | Yes |
| 6 | No formula for shares held (redeem rows would hide losses) | Buys minus sells, never redeems | Yes. **Added**: these exclusions count toward the same "big share left out" note |
| 7 | A lookup would wait behind a Scan | Lookups jump the queue | Yes |
| 8 | Fee band out of date | Check against each market's own schedule | Yes, **overriding his own earlier band** |
| 9 | v2 fees never compared with v1 | 2 requests before Saturday | Yes, and it matched to the cent on all 25 fee fills |

The spine went from 18 to 25 rules. The student asked for a **second adversarial pass "because the doc thats been reviewed isnt the doc we have now"**. It found no criticals but 8 high holes:
- a cache hit stitched from two snapshots;
- the seed mapping changing between restarts;
- the same fake-significance problem in the Copy Test (false passes about 27% instead of 5%);
- the offline Scan;
- a schema change deleting frozen data;
- one bad wallet blocking a Scan;
- the activity read missing later sells;
- `load-sample` writing to the wrong database.

His decisions:
- The Copy Test gets a planted gate test ("27% false passes would make the copy verdict meaningless").
- Correlated "ladder" markets share one draw when detectable (**his rider**: same underlying, same resolution date), with a note for the rest.
- A wallet that can't be read in full is kept and flagged. **His rider**: the flag goes "everywhere its counted, not just its own page, a half read book can pass on luck of which half".
- Every buy fill is copied. **His rider**: re-measure the Scan cost. The AI measured it offline: unchanged when requests are packed (1.06 requests per outcome; one request per window would be 3.9).

## 6. Plan changes

Each one was shown to the student before anything was committed:
- **PRD**, through its memlog: 11 entries and the text.
- **Brief, revision 8.** The student: "dont let the prd carry it alone. step 5 is the method section thats read first". The method step now says linked bets share one draw, with a revision note.
- **Addendum**, rewritten as settled technology. **The student caught a leftover**: PRD §8 still justified 5 per second as a third of the old v1 limit. It now cites v2's 200 per 10 seconds, so 5 per second is a quarter.
- **UX**: the population line, a "left out of the test" line, the Seed on results pages, the "not fully read" tag, the label source and the new Scan statuses. **His addition**: a dated note next to the mockups saying they predate these changes and the written spec wins, "else someone builds the old screen later".
- **A v2 section in `spike/FINDINGS.md`.**

## 7. AI mistakes caught

- **Dated model ID.** The student asked to pin "the exact dated model id". The AI checked Anthropic's reference: Haiku 5.5 has no dated ID, and it rejects temperature 0, so pinning would not give the same labels anyway. It proposed stored labels instead.
- **AD-20's first wording** said both sides of a market "can never win together". The second review showed this is false when the two prices add up to more than 1. Reworded.
- **AD-15's first version** would have used Python's `hash()`, which changes on every restart. Caught by the second review; now a fixed sha256 mapping with a two-process test.
- **AD-3 said a timed-out page is re-requested with a smaller page size.** The verification review showed the cursor fixes the page size. It now restarts the walk.
- **The 30-day margin** the AI first put on the before-part fetch would have dropped only late-redeemed winners (the first adversarial review). Withdrawn.
- **numpy 2.5 needs Python 3.12**, which broke the "3.11 or newer" the student had approved. The AI flagged it instead of deciding; he accepted 3.12.
- **One spine rewrite failed to save.** The file had changed on disk since it was read. The linter then checked the old version, and the decision log briefly said "rewritten" before it was. The AI noticed, re-read the file and wrote it again.

## 8. Commits on branch `architecture`

1. Architecture probes and v2 re-check in `spike/` (scripts and FINDINGS section)
2. Architecture spine, decision log and reviews
3. PRD and addendum: plan changes from architecture
4. Brief revision 8
5. UX: architecture follow-ups and mockup note
6. AI log and transcript

Then push. The student opens the pull request on GitHub.

## 9. Next

The student picks the 10 real wallets for the Sample Dataset and the default Cut-off Date (PRD Q5, Q6) next session, and the price-window capture runs straight after, while the old price route still answers. Then `bmad-create-epics-and-stories`.
