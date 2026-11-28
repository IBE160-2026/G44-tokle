---
title: 'Story 5.3: Hold-up Test on a live Scan'
type: 'chore'
created: '2026-11-27'
status: 'done'
baseline_commit: '49ae83bd89c9c8890bd5cc45326ac07068fa50db'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-5-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The README's only Hold-up result comes from the Sample Dataset: its tested Passers are made-up Wallets and its Comparison Group rests on 3 real Wallets. SM-5 asks for the Hold-up Test on a live Scan of real Wallets, reported whichever way it comes out. No live Scan has ever been run with this app.

**Approach:** Run the app online, scan with the default Cut-off Date (1 July 2025) and the default Seed (44), and write what the app stored into the README and the reflection notes. Keep the Scan for Story 6.6. No code is added.

## Boundaries & Constraints

**Always:**
- The result is reported as it comes out (NFR-13, SM-C2): Hold-up result of both groups, Scan size, Markets used, Wallets not fully read, the date and how long it took.
- Every live run is reported, also one that was stopped or failed. Which run is "the result" is decided before any run starts, so it cannot be picked afterwards.
- Numbers are copied from the app's own pages or its database by a script, never typed from memory, and checked against the page.
- Addresses only, no trader names. The app stays read-only at 5 requests a second or fewer.
- The Scan is kept: `instance/live.db` is copied to `../G44-tokle-data/` with a SHA-256 file after the run.

**Ask First:** if a live run fails because of a bug in the app, stop and tell Edvard. A fix is its own small change (plan first, a test that fails before the fix), allowed until the 1 December code stop.

**Never:** no change under `src/` or `tests/` in this story; no second run with another Seed, date or size to get a nicer result; `instance/live.db` is never committed; no Copy Test (Epic 6).

**Decided (Edvard, 2026-11-27):**
- The Scan that counts is 200 Wallets, the app's default (the AI's recommendation; rejected: 50, where the Passers may end at *Not enough data*, and 500).
- A trial Scan of 10 Wallets runs first, to find live-only bugs while fixes are still allowed and to measure time and disk use. Its result is reported in the README in one line; the 200-Wallet Scan is the result, named before either starts (the AI's recommendation; rejected: straight to the big Scan).
- The AI runs the trial from the session; Edvard starts the 200-Wallet Scan in his own terminal and browser, so it keeps running if the chat closes (the AI's recommendation; rejected: the AI starts both).
- The spec is kept whole at about 1,950 tokens (over the 1,600 guideline).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Scan finishes | live Scan, 1 July 2025, Seed 44 | README section with both groups' rows, as the page shows them | N/A |
| No Passers, or a group under 30 bets | finished Scan | reported as it is (*Not enough data*, or "no Wallet passed") | N/A: a valid result (SM-C2) |
| Polymarket stops answering | Scan `stopped` | *Resume Scan*; the README says it was resumed | if it cannot finish: the README says how far it got and why |
| The app fails on live data | Scan `failed` | stop, tell Edvard | Ask First rule above |

</frozen-after-approval>

## Code Map

- `README.md` line 9 (status), line 21 ("Stage 2 so far"), line 114 ("A Hold-up Test on a live Scan … has not been run."): a new section `## The Hold-up Test on a live Scan` goes after the Sample Dataset section. `tests/test_holdup_page.py` line 488 reads the Sample section only up to the next `## `, so a new section does not touch what the tests pin.
- `src/liquidoracle/__main__.py` `open_sources`: a live run uses `instance/live.db`. Today that file is on layout 4 (23 November: 3 looked-up Wallets, no Scan); the first start rebuilds it. Nothing in it is needed.
- `services/scans_page.py`: the live form takes `cutoff` (blank by default, so 2025-07-01 is typed in) and `wallets` (10 to 500, default 200); `planned_requests` = 50 + 100 × 15 + 4 × N × 40 `[ASSUMPTION]`; after one finished live Scan the estimate is recalibrated from it.
- `services/scan.py` `run_scan`: 100 Markets (up to 30 pages each), 3 × N before parts, N after parts, then the Hold-up phase. Wallet parts under 24 hours old are reused by a later Scan with the same date. `PolymarketUnavailable` stops the Scan; *Resume Scan* carries on.
- Where the numbers are: `/scans/<id>/hold-up` (both group cards), `/scans/<id>/watchlist` (population line "N of 100 Markets used", Watchlist size, luck count), tables `scan`, `scan_market`, `scan_wallet`, `scan_result`, `group_result`, `job` in `instance/live.db`.
- Open item from Story 5.1 (`.logs/edvard-tokle/issues.md` line 116): time the Hold-up step and watch memory on the live Scan (22 s per 99,300 pooled bets offline).
- Plan: `epics.md` Story 5.3 (open-items paragraph), `sprint-status.yaml` (5-3, epic-5), the PRD `decision-log.md` through `_bmad/scripts/memlog.py`, `../IBE160-kursfiler/refleksjon-notater.md`.

## Tasks & Acceptance

**Execution:**
- [x] `instance/live.db` -- run the app online and the Scan(s) as decided in Q1 to Q3; note start, end, requests refused, stops and resumes -- the run itself
- [x] scratchpad script -- read the stored result read-only from `instance/live.db` and compare it with the Hold-up page and the Watchlist page -- numbers copied, not typed
- [x] `README.md` -- new section with the result table (same columns as the Sample one), Scan size, Markets used, Wallets not fully read, Watchlist size, run date and time taken, and what the result can and cannot tell; status line and stage 2 list updated; line 114 replaced -- SM-5, NFR-13
- [x] `../G44-tokle-data/` -- copy of `live.db` with a SHA-256 file -- the Scan is kept for Story 6.6
- [x] `_bmad-output/planning-artifacts/epics.md`, decision log, `sprint-status.yaml` -- what was decided and how it went -- plan stays current
- [x] `../IBE160-kursfiler/refleksjon-notater.md` -- the result and what the first live run taught -- the story's second acceptance line

**Acceptance Criteria:**
- Given the app online, when the Scan with Cut-off Date 1 July 2025 has finished, then the README states its Hold-up result for both groups, the Scan size, Markets used and Wallets not fully read, exactly as the app shows them.
- Given the finished Scan, when the app is started again, then the Scan is still in *Your Scans* with its Watchlist and Hold-up Test tabs, and a checked copy of the database lies outside the repository.
- Given this story's commits, when `git diff main --stat` is read, then nothing under `src/` or `tests/` changed, and `uv run pytest` with `CI=true` still passes.

## Implementation Notes

- Run in this session without a helper: the work is running the app and writing up, and the AI has to answer for the numbers itself. Plan first (commit bbca83f, before any run): the epics' open items for 5.3, the PRD memlog and the sprint status, so the 200-Wallet Scan is on record as the result before the trial started.
- **Before the first run:** `instance/live.db` was on database layout 4 (23 November, 3 looked-up Wallets, no Scan). Starting the app rebuilt it, as the app does for an old layout. No live Scan had been run before.
- **Trial Scan (Scan 1 in `instance/live.db`): 10 Wallets, Cut-off Date 1 July 2025, Seed 44, started 27 November 2026 16:43 (15:43:57 UTC), finished 19:04, 2 hours 20 minutes of running in two runs.** The app's estimate had been "about 10 minutes".
  - Markets: 20 minutes. 77 of 100 used, 23 not used (over 15,000 rows), 189,086 candidates. The data spike in October found 77 and 189,085.
  - Shortlist of 30: one Polymarket contract address (0xa5ef39) dropped, 29 ranked, 5 of them not fully read.
  - **Stopped once.** The second Wallet, 0xd218e4 (the very large Sample Wallet, more than 60,000 closed bets), took 39 minutes and then Polymarket answered 503 three times on `/v2/activity`. The Scan stopped as designed (`stopped`, "Polymarket did not answer"), and what had been read for that Wallet was discarded, because a part is stored whole or not at all. The AI pressed *Resume Scan* at 17:45 (the matrix row for a stop). The second attempt took about 38 minutes and went through; the Wallet is ranked on $0 and flagged not fully read, as in the Sample Dataset.
  - The other 28 Wallets' before parts took about 39 minutes together, most of it on a few large ones (0x63d43b among them). The 10 after parts took about 3 minutes. The Hold-up step took under 20 seconds on 2,072 pooled bets (the open item from Story 5.1).
  - Disk: 191 MB for 39 stored parts (the app held about 300 MB of memory while reading 0xd218e4).
  - **Result, as the pages show it:** no Wallet rated *Skilled (high confidence)*, so the Watchlist is empty and there are no Before-Cut-off Passers ("No Wallet passed on its bets before the Cut-off Date…"). Before the date: 2 *Likely skilled*, 5 *No evidence of skill*, 3 *Not enough data*. Comparison Group: 7 Wallets, 2 dropped, 1 not fully read, *No evidence of skill* on 2,072 resolved bets, "about 1 time in 9" (p = 0.109), Real PnL $1,178,200. No dropped-share warning (it is not set when a group has no Wallets).
  - After the trial the app's own estimate for 200 Wallets reads "about 25 hours, based on your last Scan". That figure counts both runs, the lost 39 minutes included.
- **What the trial showed about the app (no code changed):** the time estimate is far too low for a shortlist headed by very large Wallets; one such Wallet costs about 40 minutes before its part is stored; a single run of 503 answers loses that Wallet's work and stops the Scan until someone presses Resume.
- **Edvard's call after the trial (2026-11-27): a helper presses Resume overnight.** The AI gave three ways to handle stops in the long Scan: a small script outside the repository that presses *Resume Scan* (the AI's recommendation), pressing it by hand, or changing the app to retry by itself (new code, its own story). He chose the script. It is `../G44-tokle-data/resume_scan.py`, not part of the app and not in the repository: it reads `instance/live.db` read-only and sends the button's own POST two minutes after a stop, at most 30 times, never for a `failed` or `interrupted` Scan, and logs every press. Tried against a throwaway database and a stand-in app (five cases: waits for a new Scan, resumes with the app's own Origin, leaves `failed` and `interrupted` alone, gives up with no app, keeps the limit). The README will say how many times the Scan was resumed.
- **The 200-Wallet Scan (Scan 2 in `instance/live.db`), the result that counts: started by Edvard in his own terminal 27 November 2026 19:24:12 (18:24:12 UTC), finished 22:08:09, 9,837 seconds = 2 hours 44 minutes, one run.** Cut-off Date 2025-07-01 00:00 UTC, 200 Wallets, Seed 44, all three read back from the database when it started. Polymarket did not stop it; the helper's log ends "Resume was pressed 0 time(s)".
  - Markets: 19 minutes, 77 used, 23 partial, 189,086 candidates (the same as the trial).
  - Shortlist of 600: 1 contract address dropped, 599 ranked. 570 before parts fetched in 1 hour 53 minutes; 29 reused from the trial (under 24 hours old, same date and side), 0xd218e4 among them, so its 40 minutes were not paid again. 190 after parts fetched in 32 minutes, 10 reused. Hold-up step: about 10 seconds on 30,592 pooled bets. Database: 1.1 GB, 799 stored parts.
  - **Result, as the pages show it:** Before-Cut-off Passers *Skilled (high confidence)*, "fewer than 1 time in 10,000" (p = 0.0001, no replay of 10,000 did as well), 4,161 resolved bets, Real PnL $3,439,086, 9 Wallets, 2 dropped, 1 not fully read. Comparison Group *No evidence of skill*, "about 1 time in 20" (p = 0.0503, with *Likely skilled* starting below 0.05), 26,431 resolved bets, Real PnL $3,096,636, 62 Wallets, 10 dropped, 3 not fully read. No dropped-share warning (22% against 16%). Before the date: 9 *Skilled (high confidence)*, 14 *Likely skilled*, 48 *No evidence of skill*, 129 *Not enough data*. Watchlist: 10 Wallets, 8 of them also Passers. 7 of the 200 Wallets not fully read (before or after part).
  - **How the README numbers were checked:** a script (kept as `../G44-tokle-data/check_readme_live_scan.py`, not part of the app) reads the stored Scan read-only, asserts each number, and checks that the README's two table rows and the page's two cards say the same; 0 misses. The bets after the date per Wallet (whole-history count minus before count) add up to the stored 4,161 for the Passers; the largest share is 0x68c24b with 1,377. The app stores no Verdict for one Wallet's after bets, so the README says the result is about the group only.
  - **Kept for Story 6.6:** copied with SQLite's backup while the app was still open (the database is in WAL mode, so a plain file copy could miss rows) to `../G44-tokle-data/live-scan-200-cutoff-2025-07-01.db`, 1,145 MB; `quick_check` ok, row counts of seven tables equal to the source, SHA-256 `eebdfbef1ba629b376e1570409a001841feb56e778704b8803faf774d3a52a22` in the file beside it. The copy is set read-only; Story 6.6 works on a duplicate, because opening it with the app would change it.
- **Limits of this result that the plan did not foresee:** the 200-Wallet Scan reused the trial's parts, so the trial was not fully separate from the result run (same date, same data, fetched three hours earlier; no number depends on which Scan fetched a part); and the time taken understates a cold run by about 80 minutes, what those 39 parts cost the trial without the failed attempt (38 + 39 + 3; a reviewer corrected the AI's first figure of two hours, which counted the lost 39 minutes). Both are in the README.

## Spec Change Log

## Review Triage Log

Pass 1 (2026-11-28): three reviewers (blind hunter BH, edge case hunter EC, verification gap VG), 26 findings (BH 19, EC 7, VG none: "No verification gaps found", nothing behavioural in the diff, the 3 README-reading tests pass). 0 intent gaps, 0 bad spec. No reviewer found a wrong number in the README's table; the AI checked each factual claim below against `instance/live.db` (read-only) before changing anything. 24 patched (some in part), 1 rejected (BH19), 1 part taken to Edvard (in BH18): he said no to the export.

| # | Finding | Verdict | Evidence / route |
|---|---------|---------|------------------|
| BH1 | "All 200 are top earners" overstates who was tested | medium | True: 258 of the 599 ranked Wallets had a profit before the date; the 200 run from $819,053 to under one cent, the 100th $5,585, 53 under $100. Patch: README *Wallets* bullet and the "picked for profit" and "most of the 200" limits |
| BH2 | "The other 599 were read" hides the Wallets not fully read | medium | True: 15 of 599 flagged, 7 of them on exactly $0 and outside the 200, 0xd218e4 (highest estimate, $1.0M) among them. Patch: README |
| BH3 | The Comparison Group's label rests on 3 replays of 10,000 | medium | True: p = 503/10,001, 500/10,001 would be *Likely skilled*; the count's spread between Seeds is about 22. Patch: README limit rewritten ("a coin toss") |
| BH4 | The Passers' money is concentrated; the 2 dropped have 0 bets | low | True by subtraction (whole minus before, sums equal the stored 4,161 and $3,439,086): 0xbaa2bc and 0x614dc8 made $2.27M on 567 bets. Patch: README, marked as worked out, not shown by the app |
| BH5 | The sentence under the table says more than was tested | low | True: 7 of 9 and 52 of 62 are tested. Patch |
| BH6 | Markets bullet: "rows of trades" is the wrong term, the cause is inferred, the scale is missing | medium | True: `MARKET_ROW_CAP` caps a Market's positions list; the store keeps only `partial`; the 23 hold 40.5% of the volume and 4 of the 5 largest Markets. Patch |
| BH7 | The cap on bets before the date is not mentioned | low | True: the before part is the latest 2,000 Positions (`window.py`); 8 of the 200 reached it, 1 Passer. Patch |
| BH8 | No luck count for the Passers | low | True: 71 Wallets had a Verdict before the date, 71 x 0.01 is about 1. Patch, named as the page's rule applied by hand |
| BH9 | "No second run" contradicts the trial; "run once" too | low | True. Patch: intro, status line, "It is one Scan" |
| BH10 | The proof of deciding first is thinner than it reads | medium | True: bbca83f is a local commit at 16:43:41, the trial started 16:43:57, no remote has it yet; the sprint status in it says 16:45, a rounded time the AI typed just before committing. Patch: the README states it plainly. The commit must reach `main` unchanged (merge commit, no rebase or squash): told Edvard |
| BH11 | The cold-run figure counts the lost attempt; "77 minutes" mixes two attempts | low | True: 38 + 39 + 3 = 80 minutes without the failed 39. Patch: README; the note above corrected |
| BH12 | "The time estimate is far too low" is half the fault | low | True: the formula gives 10.5 minutes for 10 Wallets and 1 h 52 min for 200 (2 h 44 min measured); after the trial the page said about 25 hours. Patch: README how-to, epics, decision log, a memlog entry |
| BH13 | "Run it yourself" leaves out what a stranger needs | low | True. Patch: the date field, 200 as default, keep the terminal open, disk, *Resume Scan*. Memory left out (measured once, in the trial) |
| BH14 | `decision-log.md` has no Story 5.3 section though the task is ticked | medium | True. Patch: section added |
| BH15 | `issues.md` does not list the two faults; the Hold-up timing item is still open; no AI log | medium | True when reviewed: both are written when the session closes (session log, AI log), before the commit. Patch: done there |
| BH16 | Sprint status still `in-progress`, written before the run | low | True. Patch: `review`, new time |
| BH17 | No verification outcome recorded; acceptance 2 not tried; the trial got six sentences against "one line" | medium | True. Patch: outcomes below; the trial is one sentence again; the restart check is noted below |
| BH18 | Nothing in the repository lets anyone check the live table | medium | Partly patch: the SHA-256 is in this spec, the check script is kept beside the copy, the copy is read-only. Committing an export of the stored rows is a new file in the repository: taken to Edvard with the AI's recommendation (no). **Edvard (2026-11-28): no export**, the README and the AI log already carry the numbers |
| BH19 | Stale line numbers in the Code Map; `[ASSUMPTION]` quoted without the measurement | low | Rejected: the fix is to edit this build's spec, and the Code Map describes the files as planned. The measured estimate is in the issues list |
| EC1 | The cited commit must survive the merge | medium | Same as BH10. Patch (wording) and a merge commit, as PRs #45 to #47 |
| EC2 | The pre-run proof is an unpushed local commit time | medium | Same as BH10. Patched with it |
| EC3 | The check script lives only in a temporary folder | low | True. Patch: `../G44-tokle-data/check_readme_live_scan.py` |
| EC4 | "Rows of trades" | medium | Same as BH6. Patched with it |
| EC5 | The epics point at issues that are not listed | medium | Same as BH15 |
| EC6 | The kept copy is writable and has stray `-shm` and `-wal` files | low | True: the reviewers' read-only opens made the two files; the hash was unchanged. Patch: files removed, copy set read-only; Story 6.6 works on a duplicate |
| EC7 | Decision log and sprint status not updated | medium | Same as BH14 and BH16 |

## Verification

**Outcome (2026-11-28):**
- `git diff main --stat -- src tests`: empty.
- `uv run pytest` with `CI=true`: 1,702 passed, 3 deselected, 364 s (1,702 before this story). Run before the review; the review changed only the README's wording and plan files, and the 3 tests that read the README pass after it.
- The check script after the review: every number of the README's live section against the stored Scan and the two pages of the running app, 0 misses.
- Acceptance 2 (the Scan is still there after a restart): after Edvard had stopped the app, the AI started it again: *Your Scans* lists the 200-Wallet Scan (Watchlist 10, Finished) and the trial, both of the Scan's tabs open, the two cards read as before, and the check script passes again with 0 misses. The AI then stopped the app.

**Commands:**
- `git diff main --stat -- src tests` -- expected: empty.
- `uv run pytest` with `CI=true` -- expected: all pass, 0 skipped (1,702 before this story).

**Manual checks:**
- The README's live table against `/scans/<id>/hold-up` and `/scans/<id>/watchlist` in the running live app, cell by cell.
