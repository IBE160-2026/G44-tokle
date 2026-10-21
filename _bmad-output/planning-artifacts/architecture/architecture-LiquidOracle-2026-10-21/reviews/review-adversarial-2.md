# Adversarial review 2 of the architecture spine (AD-1 to AD-25), 2026-10-21

Independent reviewer (subagent, read-only, did not write the spine). Read: ARCHITECTURE-SPINE.md, .memlog.md, the four earlier reviews and triage.md, PRD (Glossary, FR-1 to FR-24, s8), EXPERIENCE.md, spike/FINDINGS.md. Pending PLAN CHANGES listed in the memlog are not counted as findings.

**Verdict:** most earlier holes are closed, and none of the holes left is critical. But the new rules add eight high-severity holes, where two stories can obey every AD and still double-count fills, lose reproducibility across restarts, pass the Copy Test by luck, or fail the offline Scan. Each one closes with a small rule edit.

---

## High

### 1. A cache hit can be put together from two snapshots, and fills can never be de-duplicated

- **Units:** `data/store.py` coverage check (A); `services/scan` fetch step (B).
- **Both obey:** AD-4 (a hit when "the stored ranges cover the requested window"), AD-19 (each fetch is its own snapshot), FR-16 ("only Wallets not seen before are fetched").
- **Divergence:** at 10:00 a lookup stores snapshot F1 for Wallet W (latest 2,000, from 2026-03 to now). At 11:00 a Scan with cut-off 2026-06-01 needs W's before window (2025-11 to 2026-06). A computes coverage as the union of every stored range, so B fetches only the missing gap, 2025-11 to 2026-03, as snapshot F2. The reader then merges the rows of F1 and F2. FINDINGS says the row at the boundary second appears in both reads, and identical rows are separate fills. So the boundary fills are counted twice, held shares go up, and a Position either passes with the wrong *s* or is dropped by the 1% gap rule. A different B re-fetches the whole window as one snapshot. Both builds follow AD-4 and AD-19.
- **Error path:** FR-2 says that when Polymarket does not answer, the app "offers the stored data". AD-4 controls only hits. A failed lookup therefore offers the Scan's 2025 snapshot under the "latest 2,000" label, which is the old hole 6 coming back.
- **Consequence:** wrong shares and Verdicts with 0 network calls, or a Verdict on the wrong window, and nothing on screen looks wrong.
- **Smallest fix (AD-4/AD-19):** a read is served by exactly one complete snapshot whose own range covers the window. Rows are never merged across snapshots, and partial gap fetches are not allowed. The FR-2 fallback offers only a snapshot whose range matches the view, labelled with its fetch date. Otherwise it says there is no stored data for this view.

### 2. AD-15's `spawn_key` takes integers, the ids are strings, and the obvious mapping changes between runs

- **Units:** `core/skilltest` (A); `core/copytest` (B).
- **Both obey:** AD-15 (`SeedSequence(SEED, spawn_key=(purpose, id))`), FR-7.
- **Divergence:** NumPy's `spawn_key` accepts only integers. `purpose` is a string, and `condition_id` and the Wallet address are hex strings. A uses `hash(purpose)` and `hash(wallet)`. Python salts string hashes per process, so the same data and Seed give a different p-value after every restart. A same-process FR-7 test still passes, so the suite stays green. B uses `zlib.crc32`, which is stable, so the two stories draw from different streams for the same unit. Separately, AD-20 says one U per Market is "shared by every Position … across all Wallets", while AD-15 says "a generator is never shared between Wallets". Read literally, one story cannot obey both. AD-15's sort covers Positions only, so the Random Group Check draws Wallets in database row order.
- **Consequence:** FR-7 and FR-18 reproducibility break across restarts and resumes, and no test notices. A Verdict near 0.01 can flip between *Skilled* and *Likely skilled* on reload.
- **Smallest fix (AD-15):** one pure function `core.rng.spawn_key(purpose, id)` with fixed integer codes for each purpose and `int.from_bytes(sha256(id)[:8])` for ids. The random unit of a group test is the test itself, and every Wallet in it uses the same per-Market U. Wallets are sorted by address before group draws. One FR-7 test runs in two subprocesses with different `PYTHONHASHSEED` values.

### 3. The Copy Test's Random Group Check still treats Passers as independent

- **Units:** `core/copytest` Random Group Check (A); `core/skilltest` with AD-20 (B).
- **Both obey:** AD-20, which binds FR-5, FR-17 and FR-20 but not FR-18, and the PRD's Random Group Check.
- **Divergence:** AD-20 fixed shared Markets for the Hold-up Test only. The Copy Test compares the Passers' average Follower Return with random groups of Wallets. Say 7 Passers hold the same side in the same 40 after-part Markets, and the Pool Wallets are mostly independent. Then the Passers' average has spread about σ, while a random group of 7 has about σ/√7 = 0.38σ. With no follower edge, the chance that the Passers beat the 95th percentile is P(Z ≥ 1.645 × 0.38) ≈ 27%, not 5%. Even with partial overlap (ρ = 0.3) it is about 16%. The FR-18 check over 1,000 planted coin-flipper Scans uses independent Wallets, so it cannot catch this.
- **Consequence:** *Beat random picks*, the stage-2 headline, can come from luck in shared Markets. This is the same fake significance AD-20 was written to stop.
- **Smallest fix:** extend AD-20 to FR-18. The Copy Test page shows how many of the Passers' Copy Sample Markets are shared by two or more Passers. Add a planted check: 10 coin-flipper Passers on the same side of the same 40 Markets must get Copy p < 0.05 in at most 7% of 1,000 runs. If the check fails, the Copy Verdict needs a Market-level null, which is a PLAN CHANGE.

### 4. The offline Scan cannot meet FR-16 through AD-21 without a mode branch, and the synthetic Market layout breaks either FR-5 or FR-16

- **Units:** synthetic generator `data/synthetic.py` (A); `services/scan` funnel run on `OfflineClient` (B).
- **Both obey:** AD-13 ("nothing else branches on a mode"), AD-14 (fills first, then everything else derived from them), AD-20, AD-21 (top 100 Markets by volume resolved in the 90 days before the cut-off).
- **Divergence:** FR-16 needs the sharp, steady-sharp, forecaster and speed-trader Synthetic Wallets on the offline Watchlist. B finds candidates only from the top 100 synthetic Markets inside the funnel window. Generator A1 gives every synthetic Position its own Market, which FR-5 needs: coin-flippers' outcomes are "drawn at those prices", and a Market has one resolution. Most synthetic Wallets then hold nothing in the top 100, and the Watchlist comes out empty. Generator A2 shares a pool of Markets instead. Then coin-flippers who buy YES at 0.20 and at 0.70 in a Market with one drawn outcome are no longer at fair odds, the FR-5 7% check is invalid, and AD-20 couples the lucky-streak Wallets' draws, which changes FR-17. UX says the offline Scan covers "the whole Sample Dataset". A story that skips the funnel offline to get there breaks AD-13.
- **Consequence:** the offline stage-2 path (UJ-4, SM-4) fails, or passes only through a hidden offline branch.
- **Smallest fix (AD-14):** every tested synthetic Position gets its own Market. The Scan-relevant Synthetic Wallets also hold one small Position in each of a fixed set of synthetic anchor Markets with high volume inside the default funnel window, and those Positions are fully sold before resolution. They are then candidates, but AD-11 leaves them out of every Skill Test. The offline N is passed in by the form, not chosen by mode. The round-trip test runs the offline Scan through AD-21 and checks the FR-16 list.

### 5. A schema bump deletes the snapshots that Scans and results are frozen to

- **Units:** `data/store.py` migration (A); Scan Resume, Hold-up and Copy Test, and the Verdict page re-drawing a chart (B).
- **Both obey:** AD-6 ("on a version mismatch the cache tables are rebuilt; Scans, Watchlists and results are kept"), AD-19 (Scans read only their `fetch_id` snapshots), AD-25 (a result stores the chart bins "or enough to recompute them").
- **Divergence:** FETCH_SNAPSHOT, POSITION and ACTIVITY_ROW are cache tables, so A drops them when stage 3 adds a table. B then resumes a stage-2 Scan, or runs its Copy Test, against `fetch_id`s that no longer exist. It either crashes (`failed`) or silently re-fetches under the old `scan_id`. A result that stored only its Seed can no longer redraw its chart. AD-4 also never says whether snapshots older than 24 hours may be pruned, and a pruning story causes the same loss.
- **Consequence:** the SM-5 real-data runs cannot be resumed or reproduced, or they quietly mix data.
- **Smallest fix (AD-6/AD-19):** a snapshot referenced by a Scan or a stored result is not cache. It is migrated, never dropped or pruned. Each result stores its bins and counts outright. A Scan whose snapshots are gone shows "data rebuilt, cannot resume".

### 6. Market reads have no row cap, and a 400 on one Wallet either loops Resume for ever or kills the Scan

- **Units:** `data/polymarket.py` Market-anchored reader (A); `services/scan` (B).
- **Both obey:** AD-3 (any other 4xx raises `PolymarketBadRequest`), AD-5 (`stopped` can be resumed, `failed` cannot), AD-9 (a partial read is one that "timed out … or capped"; a failed Wallet stops the job; no silent skips), AD-21.
- **Divergence (cap):** no AD gives a number for "capped". A1 reads every row: the top-100 Markets can hold 10k to 100k+ positions each, and the $400M Market only works at `limit=100`, so this takes hours and the 70-minute plan is gone. A2 caps at 10,000 rows, so most big Markets are "not used: partial", and the population line ("top 100 by volume") misdescribes a Scan resting on maybe 40 Markets.
- **Divergence (400):** the v2 cursor depth cap is untested (Deferred), and the old offset cap gave a 400. If a market maker's activity walk gets a 400, B1 treats it as a fetch failure: `stopped`, then Resume hits the same 400 again, for ever. B2 treats it as an unexpected error: `failed`, so a 70-minute Scan is lost with no Resume. B3 skips the Wallet, which AD-9 forbids.
- **Consequence:** the Scan's runtime and population depend on the story, and one bad Wallet can block or destroy the Scan.
- **Smallest fix (AD-9):** add a `MARKET_ROW_CAP` setting `[ASSUMPTION]` and a request budget per phase. The Scan page shows "N of 100 Markets used". A Wallet whose read gets a `PolymarketBadRequest` or hits a cap is kept with its partial read: its Positions are excluded with a stored reason (AD-11), and it is shown on the Scan page as "not fully read". Only `PolymarketUnavailable` stops the job.

### 7. The activity read bounds cut off fills of Positions inside the window, and the window's unit is not computable at fetch time

- **Units:** `positions_near()` and the activity reader in `data/` (A); `core/positions` (B).
- **Both obey:** AD-7 (after part: read activity oldest-first from the cut-off "until 2,000 Resolved Positions have their first buy"; before part: start at the earliest Gamma start date, no end stated), AD-8 (cap first, on Resolved Positions), AD-10 (held = Σ buys − Σ sells), AD-11 (0 < s ≤ bought; 1% gap; "or the activity read hit its cap").
- **Divergence (after part):** A stops at the 2,000th first buy, on 5 March. Position #1,990 was fully bought by 4 March, half sold on 20 March, and resolved on 1 April. The sell is never read, so *s* = 300 instead of 150. That passes 0 < s ≤ bought, and the gap check compares only bought shares, so it passes too. The Position enters the Hold-up Test with double its real shares. Sells before resolution tend to follow the price, so the error leans on outcome.
- **Divergence (unit):** "Resolved Position" means held at resolution, which is known only once every sell has been read. So A has to cap on "Positions in resolved Markets" (fully sold ones included), while B counts held Positions. The two counts differ, and so do the FR-11 line "latest 2,000 of N" and Minimum After-bets.
- **Divergence (before part):** no end bound is given. One long-dated Market from 2022 in the window pulls the start back to 2022. An oldest-first read then hits `ACTIVITY_ROW_CAP` before it reaches the window's newest Markets. B1 excludes every Position of the Wallet (*Not enough data*, and the Wallet drops out of the Scan ranking unseen). B2 excludes only some, and which ones is not defined.
- **Smallest fix (AD-7/AD-8/AD-11):** the window unit is "Positions in Resolved Markets" (AD-7), and a fully sold Position is an exclusion inside it. Once the window is chosen, the activity read continues to the latest `closedTime` among its Markets, since no fill can come after resolution. The before-part read ends there too. On a cap, exclude exactly the Positions whose Market `closedTime` lies after the last row read.

### 8. `load-sample` has no fixed target database, and the CI job cannot tell

- **Units:** `__main__ load-sample` (A); `run --offline` (B); the README CI job (C).
- **Both obey:** AD-13 (one database file per mode; mode set only by `--offline`/`OFFLINE`; nothing else branches on a mode), AD-14 (`load-sample` uses `OfflineClient`; large synthetic groups are regenerated from "the Seed"), AD-17 (the CI job runs the three README commands and requests the start page).
- **Divergence:** the README runs `uv run liquidoracle load-sample` with no `--offline` flag. A builds settings normally, which gives live mode, so it writes `live.db`. B then starts with `--offline`, reads an empty `offline.db`, and every sample Wallet shows "Not available offline". C requests only the start page, which renders fine, so CI is green. AD-14 also does not say where the regenerated coin-flipper files go: written into `sample_data/`, they make stray files and trip the 25 MB test on a developer machine. They are built from "the Seed", meaning the `SEED` setting, so changing the Seed to re-check a Verdict also changes the dataset.
- **Consequence:** the examiner path (SM-2, UJ-3) can be broken while CI passes.
- **Smallest fix:** `load-sample` always targets `offline.db`, as a command that is offline by definition. Regenerated files go to `instance/` (git-ignored) or stay in memory. The generator uses its own fixed constant, not `SEED`. The CI job requests one Sample Wallet's Verdict page and checks the expected Verdict text.

## Medium

### 9. Domain results have no base set and no label source in their key

- **Units:** stage-3 Domain story (A); Verdict page opened from the Watchlist (B).
- **Both obey:** AD-22 (scope `domain:<d>`, plus `scan_id`, cut-off, Seed, `fetch_id`), AD-16 (labels keyed by Market and source), AD-13 (a tag names the label source shown), AD-25.
- **Divergence:** A computes Domain Verdicts on the lookup set. B shows the `scan_whole` Verdict with a Domain table read by `domain:<d>`, which does not say which set it splits, so it shows the lookup's Domains under a Scan Verdict. Second case: Domain results computed with keyword labels in Mock LLM Mode keep the same key after a key is set and model labels arrive. The table then shows keyword-based Verdicts under a "model" tag, or overwrites them. AD-25 also does not say whether the Domain odds phrase uses the raw p or the Bonferroni-adjusted p, and FR-24 compares phrases exactly.
- **Smallest fix (AD-22):** scope = (base set, Domain), for example `scan_whole/domain:crypto`. Add the label source to the result key. `core/phrases` takes the adjusted p for Domain Verdicts.

### 10. The shortlist pre-filter counts unredeemed losers as zero

- **Units:** `services/scan` shortlist step (A); the PRD's "top Wallets by profit" (B).
- **Both obey:** AD-21 step 3 ("sum of `realized_pnl` on their Market-anchored rows"), AD-9 (OPEN rows hold the unredeemed losers).
- **Divergence:** an unredeemed loser has no realised PnL. Wallet X redeemed winners for +$40k and left −$60k of losers unredeemed: its Real PnL is −$20k but its pre-filter score is +$40k. Wallet Y redeems everything for a Real PnL of +$15k and scores +$15k. X gets the shortlist place, Y may not, and step 4 only re-sorts the shortlist. `realized_pnl` also includes sell profit (Exit PnL), which the PRD keeps out of profit. This is survivor bias moved to the shortlist step, the same pattern AD-9 was written to stop.
- **Smallest fix (AD-21):** pre-filter = Σ CLOSED `realized_pnl` + Σ OPEN (resolved value − cost) on the same rows, which is cheap and counts the losers. The Scan page says the shortlist number is approximate.

### 11. The Copy Test does not say which buy is copied, and price windows can exceed what one request can fetch

- **Units:** `core/copytest` (A); price-window capture in AD-14/AD-24 (B).
- **Both obey:** AD-10 ("Copy Test buy times and prices: activity rows"), AD-14 (windows [first buy − 2 min, last buy + 32 min]), AD-24.
- **Divergence:** a Position bought in 12 fills over 3 weeks. A1 prices the first buy plus the delay. A2 prices each fill and takes the share-weighted average. The FR-18 hand check is written for one of them. B's window spans 3 weeks, but a request covers at most 14 days at 1-minute data (FINDINGS) or 15 days (v2). The fetch is rejected or has to be split, and 21 days of minute points per token eat into the 25 MB budget.
- **Smallest fix (AD-10/AD-14):** pick one rule (recommended: every fill is priced at fill time + delay, Follower PnL sums over fills), and capture one short window per fill, [t − 2 min, t + 32 min], merged when windows overlap.

### 12. AD-20's "both sides can never win together" is false, and correlated sibling Markets have no trigger for revisiting

- **Units:** `core/skilltest` (A); a property test written from AD-20's Prevents line (B).
- **Both obey:** AD-20.
- **Divergence:** a Wallet holds YES at 0.55 and NO at 0.52 (sum 1.07). With U in (0.48, 0.55) both win, in 7% of Simulations, a +0.93·s outcome that cannot happen. With YES at 0.30 and NO at 0.40, both lose in 30% of Simulations. B's test fails. The obvious "fix" (NO wins iff YES loses) breaks the marginal for NO and the FR-5 claim. On the stated limit: price-ladder Markets (BTC above 95k, 100k, 105k on one date) are positively correlated separate Markets. A Wallet buying the lower rungs in 30 ladder events gets about 90 correlated wins drawn as independent ones, which is the 280-flip problem inside one Wallet. "Revisit if real data shows it matters" has no measure attached.
- **Smallest fix (AD-20):** reword the claim to "both sides cannot win together when their prices sum to at most 1; AD-20 keeps each Position's marginal and maximally couples the sides". Add a measure: each result stores the share of tested Positions whose Gamma event holds another tested Position, and an honesty note appears above a set share `[ASSUMPTION]`. A planted ladder Wallet gets a test.

---

## Earlier findings whose fix does not fully close them

| Earlier finding | Still open because | See |
| --- | --- | --- |
| Adversarial 3 (fetch bounds) | The after-part stop cuts off later fills, and the before-part read has no end bound | 7 |
| Adversarial 4 / triage 2 (one draw per Market) | The "never both win" claim fails when prices sum above 1. The Copy Test is not covered. Ladders have no measure | 3, 12 |
| Adversarial 6, rubric C2 (cache window) | Coverage can union snapshots, and the FR-2 fallback still offers a different window | 1 |
| Adversarial 8, rubric H3 (scopes) | `scan_whole` has no FR-11 window line: AD-8 defines only "latest 2,000" and "first 2,000", while `scan_whole` has two windows and leaves out every Position bought before the cut-off and resolved after it, so "whole history" is not whole. Domain scope has no base set | 9 |
| Adversarial 10 (cap order) | The cap's unit, "Resolved Position", cannot be computed at fetch time | 7 |
| Adversarial 11 (offline data) | The offline Scan cannot pass through the funnel. Regenerated files have no location | 4, 8 |
| Adversarial 12 (Seed order) | `spawn_key` mapping is undefined. Wallet order for group draws is not fixed | 2 |
| Rubric C1 (lookups) | AD-5 lets a lookup in only "between two Wallets". The Market-read phase (100 Markets, possibly thousands of pages) and a single market-maker fetch have no Wallet boundary, so a lookup can wait 30+ minutes. Fix: check for waiting lookups between any two units of work (each Market read, Wallet fetch or price window) | — |
| Rubric H6 (one database per mode) | `load-sample` has no fixed target database | 8 |
