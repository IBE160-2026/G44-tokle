---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-LiquidOracle-2026-10-12/prd.md
  - _bmad-output/planning-artifacts/prds/prd-LiquidOracle-2026-10-12/addendum.md
  - _bmad-output/planning-artifacts/architecture/architecture-LiquidOracle-2026-10-21/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/ux-designs/ux-LiquidOracle-2026-10-16/DESIGN.md
  - _bmad-output/planning-artifacts/ux-designs/ux-LiquidOracle-2026-10-16/EXPERIENCE.md
  - spike/FINDINGS.md
---

# LiquidOracle - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for LiquidOracle, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

Requirement IDs are the PRD's own (FR-1 to FR-24; FR-15 keeps its old number and belongs to stage 3; FR-18 has three parts, FR-18a to FR-18c, since 2026-11-18). Architecture rules keep their spine IDs (AD-1 to AD-25). Stage marks S1, S2, S3 follow PRD §6.1.

**Timing and slipping rules** (Edvard, 2026-10-23 and 2026-10-24):
- Build window: 5 November to 1 December 2026, moved from 2 November because no code had been started by then; nothing is built 14 to 16 November (Edvard, 2026-11-05). **1 December is a hard stop for code**: after it, only fixes that make the README commands or the tests run, each logged, and nothing new. 1 to 15 December is for the reflection report (30% of the grade), the README check and repository tidying; the repositories lock on 15 December.
- Stage 1 must stand alone as a working app and never slips. If time runs short, work is cut from stage 3 first, never from stage 1.
- Checkpoint 20 November: if stage 1 is not done by then, stage 3 is dropped entirely and the time goes to stages 1 and 2. The targets below finish stage 1 on 23 November, so this rule applies unless stage 1 finishes early (2026-11-05). **Applied on 20 November:** stage 1 was not done, and Edvard **parked stage 3, not deleted it**: Epics 7 and 8 stay here and are picked back up if all of stage 2 (Epics 4 to 6, the Copy Test included) is done before the code freeze on 1 December (Edvard, 2026-11-20).
- Inside Epic 1, only the visual polish of Story 1.7 moves later (dark theme, hover states, responsive details), staying inside stage 1; Story 1.5 stays before 1.7 because the card needs its phrases, and Story 1.4's checks are never cut (Edvard, 2026-10-24, after the final validation).
- **Stage 2 minimum** (PRD §6.1; Edvard, 2026-11-18): Epics 4 and 5 passing their checks offline on the Sample Dataset, closed by Story 5.2 with the Hold-up result of the 8 real Sample Wallets in the offline Scan in the README (0xd218e4 and 0x63d43b stay outside it, Story 4.7). Story 5.3 (a live Hold-up run) and Epic 6 (Copy Test) come on top if time allows; whatever is not reached is stated in the README with the reason.
- Inside stage 3, Epic 8 slips before Epic 7. A partial stage 3 is fine; whatever is left out is stated in the README and logged with the reason. Because stage 3 can stop after any story, each stage 3 story ends with all tests passing and the README updated (NFR-12).
- Edvard's five Domain definitions and 50 blind hand labels (Story 7.2's first step) are done early, in the Epic 1 week, and committed before any labeller runs on those Markets (Edvard, 2026-10-24).

## Requirements Inventory

### Functional Requirements

**Stage 1: Wallet lookup, Skill Test, Verdict page, offline running**

- FR-1 (S1): Look up a Wallet. The user enters an address on the start page and gets its result page. Invalid format: error, nothing fetched. Valid address with no Polymarket history: "No Polymarket history found for this address" plus the hint to use the profile-page (proxy wallet) address.
- FR-2 (S1): Fetch and cache data. Trades, positions and related Markets are fetched from Polymarket's public APIs and stored in the database. A second lookup within 24 hours `[ASSUMPTION]` makes no network call. If Polymarket does not answer, the page says so and offers stored data if any. Requests never exceed published rate limits.
- FR-3 (S1): Build Positions. Fills combine into Positions (Entry Price = share-weighted average). Both sources are required: closed and open positions (unredeemed losers live only in the open list). Resolved = Market closed, outcome prices exactly 0 and 1, has a resolution time from Market data; anything else is "unclear resolution". Shares held at resolution = bought − sold from activity rows (never redemptions). Left out of the Skill Test, counted and shown with a reason: fully sold; split/merge/conversion in that Market; token only in activity rows; shares held not in (0, shares bought]; source gap above 1% `[ASSUMPTION]` (gap stored); unclear resolution; history not read in full. Same rules before and after the Cut-off Date. Partly sold Positions are tested on shares still held at the original Entry Price `[ASSUMPTION]`; sold shares count toward Exit PnL. Known limit (early exits) is accepted and shown (FR-11).
- FR-4 (S1): Real PnL = Σ s·(o − p) over Resolved Positions minus Own Fees. Check: three Sample Dataset Wallets match a stored reference calculation, made without the app's code, to the cent; at least one paid fees.
- FR-5 (S1): Luck Distribution and p-value from 10,000 Simulations; p = (1 + #Simulations ≥ Real PnL) / 10,001. Checks: hand-check Wallet (10 at 0.50, all won) p in [0.0003, 0.002]; a fixed fee per Position lowers Real PnL by exactly the total fee and leaves p and Verdict unchanged; sharp trader (100 at 0.50, 70 won) p < 0.01; favourite buyer (100 at 0.90, 90 won) p ≥ 0.05; 1,000 coin-flippers: p < 0.05 for at most 7%, p < 0.01 for at most 2%.
- FR-6 (S1): Verdict from thresholds: *Skilled (high confidence)* p < 0.01, *Likely skilled* p < 0.05, *No evidence of skill*, *Not enough data* below 30 Resolved Positions. Check: 29 gives *Not enough data* and no p-value; 30 gives a Verdict.
- FR-7 (S1): Reproducibility. Each Skill Test runs with a stored Seed; same data and Seed give the identical p-value and Verdict.
- FR-8 (S1): Verdict card shows the Verdict, Resolved Positions, Real PnL and the odds phrase: "about 1 time in N" (N = 1/p to 2 significant figures, a whole number below 10), "fewer than 1 time in 10,000" when no Simulation reached it (and for p = 1/10,001), "more than half the time" above 0.5.
- FR-9 (S1): Luck chart. Histogram of the Luck Distribution in dollars with the Real PnL marked; the axis always includes the Real PnL; beyond every Simulation the marker reads "above all 10,000 Simulations" (or "below …"). Check: a planted Real PnL above the largest Simulation.
- FR-10 (S1): Too little data. *Not enough data* shows the count and how many more are needed; no chart.
- FR-11 (S1): Honesty notes on every Verdict card: share of Real PnL from the largest Position; N of M held to resolution and Exit PnL; a warning when Exit PnL < 0; the 2,000-window line ("latest 2,000" / "first 2,000"; a Scan's result, unless its after part could not be read or nothing was (Story 4.5 review): "Based on two windows around the Cut-off Date: up to the latest 2,000 bets resolved before it and up to the first 2,000 bought after it. Bets bought before the date and resolved after it are in neither."); left-out counts per reason and the >10% `[ASSUMPTION]` sentence; fees that failed the schedule check with their total; the >20% `[ASSUMPTION]` undetected-links note; the Seed; the fixed limits note and "not financial advice". Check: the stop-loss Synthetic Wallet shows the warning; Exit PnL ≥ 0 or no sales shows none.
- FR-12 (S1): Sample Dataset. About 10 real Wallets (decided: 10, plus 3 captured spares) and the Synthetic Wallets with Positions and price windows per buy fill; large synthetic groups regenerated, not committed; committed set under 50 MB `[ASSUMPTION]` (25 MB until Story 2.6, Edvard, 2026-11-23), checked by a test, no Git LFS. One default Cut-off Date, decided: 1 July 2025. Real Wallets have Positions on both sides of it. Stated one-way limitation on the two largest Wallets (after-date activity capped).
- FR-13 (S1, some types S2/S3): Synthetic Wallets generated by script from a fixed Seed, identical on rerun, with price paths. Types: hand-check, coin-flipper ×1,000, favourite buyer, sharp trader, thin wallet (29 bets), stop-loss trader (S1); steady sharp, lucky streak, forecaster, speed trader (S2); market maker, split-domain trader (S3).
- FR-14 (S1): Offline Mode. One setting; every Sample Dataset Wallet can be looked up with the network disconnected; anything else shows "Not available offline"; never calls the language model; its data is kept apart from online runs.

**Stage 2: Is skill worth following?**

- FR-16 (S2): Scan and Watchlist. Choose a Cut-off Date and size (default 200 `[ASSUMPTION]`), Scan the top Wallets by Real PnL before the date, see the Watchlist sorted by p-value with Minimum Luck Passes. Ranking uses only Positions resolved before the date. Candidates come from Market-anchored position lists (closed and open) of the funnel: Markets resolved in the 90 days before the date, top 100 by volume, shortlist 3 × size `[ASSUMPTION: 90, 100, 3×]`, then full fetch and ranking. The page states the population, "N of 100 Markets used", the shortlist size (approximate) and the Wallets not fully read. Minimum Luck Passes counts the Wallets that got a Verdict. Partly read Markets give no candidates ("not used: partial"); Wallets not fully read are kept and marked everywhere. Big Wallets ranked and tested on their latest 2,000 before the date. A new date means a new Scan; stored data reused. Offline Scan with the default date puts at least sharp trader, steady sharp, forecaster and speed trader on the Watchlist. Progress shown; interrupted Scans resume without refetching. The Watchlist is stored with Scan date and Cut-off Date, never sent anywhere.
- FR-17 (S2): Hold-up Test. Before-Cut-off Passers vs Comparison Group, both picked from the same Scan by the same rule on the before part only, both tested on the after part (first 2,000 per Wallet): Resolved Positions, Real PnL, p-value, Verdict per group. Minimum After-bets 10 `[ASSUMPTION]` in both groups; dropped counts shown; >20 pp `[ASSUMPTION]` difference in dropped share gives the warning (planted 60% vs 10% shows it). Steady-sharp Wallets pass after; lucky-streak Wallets show *No evidence of skill* after. Groups under 30 show *Not enough data*. The pooled after part shares one draw per Market (planted 7 Passers × 40 shared Markets: p < 0.05 in at most 7% of 1,000 runs). Not-fully-read counts shown.
- FR-18 (S2): Copy Test, in three parts. The page shows the Random Group Check first, then the per-Wallet numbers.
- FR-18a (S2): Follower PnL and Follower Return. Per Passer, over its Copy Sample (≤ 100 after Positions `[ASSUMPTION]`, drawn with the Seed), Follower PnL and Follower Return at 1, 5 and 30 minutes next to own Real PnL; each fill copied at its own time; positions with no price left out and counted; "priced N of M"; Spread Allowance 0.5 c `[ASSUMPTION]` and its limits stated (upper bound); per-Wallet numbers marked not luck-checked, 1 and 30 min marked extra with no Copy Verdict. Checks: speed trader ≤ 0 at 5 min; forecaster > 0 at 30 min; three-Position set with a fee, the Spread Allowance and a multi-fill Position matches a reference calculation made without the app's code to the cent.
- FR-18b (S2): Random Group Check at the Main Copy Delay (5 min): Passers' average Follower Return against 10,000 random groups from the Copy Pool; Copy p-value and Copy Verdict; *Not enough data* with no Passer in the Pool or fewer than 1,000 `[ASSUMPTION]` groups; only 5 min gives a Copy Verdict; "no random group did as well in 10,000 draws" wording; shared-Markets count shown. Checks: planted 10 forecasters + 100 coin-flippers p < 0.01; 1,000 planted coin-flipper Scans p < 0.05 in at most 7%; shared-Markets gate (10 Passers × 40 shared Markets ≤ 7%); Pool of 6 with 3 Passers shows *Not enough data*; same Seed same p.
- FR-18c (S2): Price history and fallback. One-minute prices only, never silently coarser, kept for good; the source checked daily; if one-minute prices for the default date are gone at the real-data run, the frozen 50-Wallet insurance pool is used, with its limits stated.

**Stage 3: Domains, Flags, Explanations**

- FR-15 (S3): Mock LLM Mode. One setting replaces the model with tag rules (a fixed map from Polymarket's event tags to Domains) and templates; on by default without a key; FR-19 and FR-23 tests pass without a key.
- FR-19 (S3): Classify Markets into politics, sports, crypto, macro, other. Each Market classified once, stored with source and date, reused; re-classifying is deliberate. 50 hand labels committed before any model output, never edited; ≥ 80% agreement `[ASSUMPTION]` for the model (if Haiku 5.5 misses, a larger model is tried and both reported); tag rules checked on other Markets. Failures: at most 3 tries per Market; an answer outside the five Domains is never stored; a Wallet with an unlabelled Market gets "Domains are not available: the language model did not answer." instead of the table (never *Other* by default; Edvard, 2026-11-18). Cost: one call per Market, stored; README shows the count and a cost estimate.
- FR-20 (S3): Domain Verdicts. Skill Test per Domain with ≥ 30 Resolved Positions, Bonferroni-corrected (× number of Domains tested, capped at 1). Split-domain Synthetic Wallet: crypto *Skilled (high confidence)*, sports *No evidence of skill*.
- FR-21 (S3): Domain table on the Verdict page: Domain, Resolved Positions, Domain Verdict.
- FR-22 (S3): Bot and market-maker Flag when at least 2 of 3 rules hold (both outcomes in ≥ 30% of Markets; sold ≥ 80% of shares bought; median buy-to-sell under 1 hour) `[ASSUMPTION]`; shown as "Likely market maker (heuristic, may be wrong)", never changes the Verdict. Synthetic market maker flagged; coin-flipper and sharp trader not.
- FR-23 (S3): Explanation of at most 60 words `[ASSUMPTION]` under the Verdict card, from the model or a template; the template if the model does not answer.
- FR-24 (S3): Explanation check. Same Verdict and odds phrase as the card, no banned words; a failing Explanation is replaced by the template and counted (SM-7). The words are the banned and "also avoided" lists in EXPERIENCE.md *Voice and Tone*, kept as one list in the code. Checks: a planted wrong Verdict is replaced; a planted Explanation with any listed word is replaced.

### NonFunctional Requirements

- NFR-1 Runnable from the README (PRD §8): from a fresh clone with uv installed, the app starts in at most 3 documented commands (install, load the Sample Dataset, start). The README lists prerequisites, exact commands, the address to open, how keys are set in `.env`, and each JavaScript file and what it does. A CI job runs these commands on a fresh checkout and checks a Sample Wallet's Verdict.
- NFR-2 Runs on Windows, macOS and Linux (PRD §8, AD-17): GitHub Actions on every push, three systems × Python 3.12 and 3.14; the whole suite runs network-blocked; any failing run fails the build.
- NFR-3 Runs locally (PRD §8, AD-23): a web page on the user's laptop, bound to 127.0.0.1, port 8044 `[ASSUMPTION]`, debug and reloader off; not hosted.
- NFR-4 Database (PRD §8, course requirement): cached Polymarket data, Domain labels, Scans and Watchlists in SQLite.
- NFR-5 Secrets (PRD §8): the model key only in `.env`, never committed; `.env.example` kept current; the key is never logged.
- NFR-6 Polite to Polymarket (PRD §8, AD-3): a stored lookup makes 0 network calls; at most 5 requests per second `[ASSUMPTION]`, one setting that can be turned down, values above 5 refused at startup.
- NFR-7 Testable core (PRD §8, AD-1): the Skill Test module has no network, web or model code; every FR with consequences has at least one automated test; each test names its FR or AD.
- NFR-8 Wording (PRD §8, UX Voice and Tone): never "guaranteed", "insider", "will win" about a Wallet, plus the UX avoided-words list; checked by a test over every template and fixed text.
- NFR-9 Accessibility (PRD §8, UX): the Verdict always as text, never by colour alone; the luck chart has a visible text alternative with Real PnL and the odds phrase; target WCAG 2.1 AA.
- NFR-10 Speed (SM-3): a lookup of a Wallet with up to 1,000 Resolved Positions from stored data returns a Verdict within 10 seconds on an ordinary laptop.
- NFR-11 Read-only (PRD §5, CLAUDE.md): only GET requests to public endpoints; no orders, no keys, nothing touching funds; no Copy or Follow buttons, alerts or advice.
- NFR-12 Each stage deliverable (PRD §6.1): a stage ends with all its tests passing and the README updated, so the project can be handed in after any stage.
- NFR-13 Honest reporting (SM-5, SM-C1 to SM-C3): every real-data result that is run (the stage 2 minimum's 10 Sample Wallets, and a live Hold-up Test and Copy Test if reached) is reported in the README whichever way it comes out; the share of Wallets rated skilled, Watchlist size and Explanation tone are never optimised.

### Additional Requirements

From the architecture spine (binding) and `spike/FINDINGS.md`:

- **No starter template.** Greenfield project from the Structural Seed: `src/liquidoracle/` with `records`, `web`, `services`, `core`, `data`; `__main__.py` with the commands `run`, `load-sample`, `make-synthetic`; `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, `README.md`; `sample_data/`, `tests/`, `tests/online/`, `.github/workflows/`. Stack pinned in the spine (Python ≥ 3.12, uv 0.13.4, Flask 3.1.3, requests 2.34.2, numpy 2.5.4, anthropic 1.17.0, python-dotenv 1.2.4, pytest 9.1.1, pytest-socket 0.8.1). This is Epic 1 Story 1.
- AD-1: one-way layer imports, enforced by a test that parses every module (no network, database, web or model library in `core`).
- AD-2: only `data/polymarket.py` calls Polymarket (GET, public, Data API v2, Gamma, price-history routes; never v1); returns `records` types; a cursor walk sends identical parameters on every page (tested); only `data/model.py` calls the model.
- AD-3: one process-wide locked rate limiter; timeouts, 429, 503 and a Gamma/CloudFront 403 retried with back-off honouring `Retry-After`, then `PolymarketUnavailable`; other 4xx → `PolymarketBadRequest`, logged; a timed-out page restarts the walk with a smaller `limit`.
- AD-4: cache hit only when one complete snapshot covers the window and is under 24 hours old; no merging across snapshots; resolved Market records, fee schedules and price windows never expire; Domain labels keyed by (Market, source).
- AD-5: jobs table and one daemon worker thread started only by `liquidoracle run`; lookups run between any two Scan units; atomic claim; phases; states `queued/running/done/interrupted/stopped/failed`; `GET /jobs/<id>/progress`.
- AD-6: plain `sqlite3`, WAL, busy timeout, one connection per thread, `BEGIN IMMEDIATE`; one `schema.sql` with `PRAGMA user_version`; cache tables rebuilt on mismatch, Scans/results/referenced snapshots migrated; only `data/store.py` runs SQL.
- AD-7: resolved from Gamma; Cut-off Date = 00:00 UTC in one place; before part = Market resolved before; after part = first buy on or after the date in activity rows **and** positions-list `first_entry_at` not before it (changed 2026-10-23); fetch rules for both parts; `ACTIVITY_ROW_CAP` `[ASSUMPTION]` with the exact cap rule.
- AD-8: windows of 2,000 on each side (latest before, first after; lookup = latest overall), one client function `positions_near(wallet, cutoff, side, limit)`, cap before exclusions, window lines on the card.
- AD-9: candidates only from complete Market reads, always `sort_by=TIMESTAMP&sort_direction=ASC` (tested); `MARKET_ROW_CAP` `[ASSUMPTION]`; partial Markets not used; Wallets not fully read kept and flagged everywhere; only `PolymarketUnavailable` stops a job.
- AD-10: one source per number (positions lists; activity rows for shares held, first buy, fees, splits, sells; Gamma for resolution, fee schedule, start date; price history for the Copy Test).
- AD-11: one Position builder (`core/positions`) applying the exclusion reasons, returning window size, excluded per reason and tested count; thresholds use the tested count.
- AD-12: Own Fees from activity rows, checked against Gamma `feeSchedule` (listed rate or any whole-percent rate 1-10%, Story 2.8); failed fees stored, counted as 0, shown; never `entry_fees_usdc`.
- AD-13: one frozen settings object (flag > `.env` > default); Offline Mode gives `OfflineClient`, `TemplateModel` and `instance/offline.db`; live uses `instance/live.db`; Mock LLM Mode gives `TemplateModel`; no other mode branches; mode indicators on the page.
- AD-14: Sample Dataset = JSON of `records` types by one serializer; the generator writes fills first; coin-flippers regenerated by `load-sample`; synthetic anchor Markets so the offline funnel finds the expected Wallets; `load-sample` always writes `instance/offline.db` through the normal pipeline; round-trip test; price windows [t − 2 min, t + 32 min] per fill, packed ≤ 14 days; 50 MB test (25 MB until Story 2.6); **the committed set is rebuilt by one script from the raw capture, never trimmed by hand** (changed 2026-10-23).
- AD-15: explicit Seed; sort before drawing; per-unit generators from `SeedSequence` with a sha256 spawn key; never `hash()`, `random` or numpy global state; subprocess test with different `PYTHONHASHSEED`; Seed stored and shown.
- AD-16: model interface (`AnthropicModel`, `TemplateModel`); `LLM_MODEL` default `claude-haiku-5-5`, effort low; structured output limited to the Domain list; labels stored per (Market, source); the 80% gate; FR-24 check in `services`.
- AD-17: `--disable-socket` by default; online tests in `tests/online/`, never in CI; CI matrix plus the README-commands job; 1,000-repetition checks marked `slow`, in full on Linux 3.14, 100 repetitions elsewhere, with the determinism checks and a golden result on every job (Edvard, 2026-10-24).
- AD-18: server-rendered Jinja2 pages complete without JavaScript; SVG luck chart; plain JS files `theme.js`, `chart.js`, `copy-address.js`, `progress.js`, no bundler; IBM Plex Serif 600/700 WOFF2 with the OFL licence, `font-display: swap`.
- AD-19: Wallet fetches as complete snapshots (`fetch_id`, visible in one final step); per-Wallet fetch lock; a Scan freezes its snapshots and an as-of time.
- AD-20: one random draw per Market across all Wallets in a test; negative-risk events and ladders share a draw; undetected links measured and shown above 20%; planted ladder test; Copy Test shared-Markets count and planted gate.
- AD-21: the fixed Scan funnel and what the Scan page states.
- AD-22: every result carries a scope (`lookup`, `scan_whole`, `scan_before`, `holdup_after`, `…/domain:x`), `scan_id`, cut-off, Seed and `fetch_id`; pages read by the full key.
- AD-23: serving rules (127.0.0.1, `PORT` 8044, no debug or reloader, `load_dotenv=False`).
- AD-24: one price-history client function (old CLOB route with 1-minute data, else `/v2/prices-history` with `bucket_seconds=60`; never coarser); `price_at(points, t)` = last point at or before t, at most 2 minutes old; windows never expire.
- AD-25: every number phrase from `core/phrases.py`; Domain phrases use the Bonferroni-adjusted p; `core` returns chart bins and the exact marker count.
- Conventions: Glossary names in code; lower-case proxy address, `condition_id`, `token_id`; UTC epoch seconds; money as float rounded only for display, tests to the cent; typed errors turned into EXPERIENCE.md messages; one progress JSON contract; settings never read deep in the code; standard logging, never the key; one banned-words list.
- From the Sample Dataset capture (2026-10-21 to 23, `spike/FINDINGS.md`), **approved by Edvard (2026-10-23) and now in the spine** (AD-3, AD-9, Conventions › Money):
  - P-1: a Market's position list contains Polymarket's own protocol contracts, which `/v2/positions?user=` refuses with 400 "protocol contract address". The Scan must drop them as candidates (not count them as "not fully read").
  - P-2: Gamma answered an empty 404 on every route during a 2-minute outage. AD-3 now retries an empty Gamma 404 on a list route like a 503, with all retries capped at 3 tries with back-off, then a clean `PolymarketUnavailable` that stops the job as resumable.
  - P-3: the p-value count "Simulations with PnL ≥ Real PnL" must count exact ties. Float sums in different order differ by tiny amounts (the AI's own estimate turned p ≈ 0.74 into 0.0002). The Skill Test should compare in whole cents (integers), which refines the "money as float" convention for the Skill Test's comparison.
- Also settled by the capture: a Market-anchored read with `sort_by=TIMESTAMP&sort_direction=ASC` works (100 Markets read; spine *Deferred* item); `/v2/activity` filters by Market with `condition` (`market` is refused) and accepts `end` with `sort_direction=DESC`.
- Sample Dataset inputs: the raw capture (about 1 GB; zip outside the repository with a SHA-256 file) is the source for the trim script; the committed dataset must be rebuilt from it by script (AD-14). CI checks only the committed set.

### UX Design Requirements

Stage marks as in EXPERIENCE.md. A page or element of a later stage is absent until that stage is built.

**Foundation (S1)**
- UX-DR1: Design tokens from DESIGN.md as CSS custom properties: every colour with its dark twin, typography roles, spacing scale, radii, breakpoints (900, 640, 400 px), component tokens; no other breakpoints; no green, no red for losses, no gradients.
- UX-DR2: Light and dark theme: starts in the dark theme (Edvard, 2026-11-20; was: the system setting); toggle button named "Dark theme" with a pressed state, 40 px round, moon/sun icon; the choice stored in the browser; still switches if storage is blocked (`theme.js`).
- UX-DR3: Bundled IBM Plex Serif (600, 700, WOFF2, OFL file beside it), first in the serif stack with the system serif fallbacks; nothing loaded from the internet.
- UX-DR4: Top bar on every page: logo and serif brand linking to *Check a wallet*; section links *Check a wallet* (S1) and *Scan wallets* (S2, absent until built), active one in accent with underline; theme toggle; Offline pill when Offline Mode is on. Below 640 px links wrap and tools move to their own row.
- UX-DR5: "Skip to content" as the first Tab stop on every page.
- UX-DR6: Logo and favicon from `mockups/logo/` (one colour, 32 px in the top bar, 16 px favicon that switches to the dark-theme blue).
- UX-DR7: Every surface has its own URL (`/`, `/wallet/0x…`, `/scans`, `/scans/<id>/watchlist`, `/hold-up`, `/copy-test`); unknown or malformed addresses show *Page not found* with a link to *Check a wallet*; browser back always works.
- UX-DR8: Page titles per surface, page name first ("Check a wallet · LiquidOracle", "Verdict · 0x7c3a…d3f5 · LiquidOracle", Scan pages with the Cut-off Date); page declares English; one main heading, headings in order; focus moves to the main heading on page change.
- UX-DR9: Interaction states: only clickable things react; hover and keyboard focus look the same plus the focus ring (2 px accent, 3 px offset); 120 ms transitions; buttons lift 1 px; one primary button per page; buttons never disabled in a way that drops focus.
- UX-DR10: Responsive: the three breakpoints' behaviour from EXPERIENCE.md; usable at 200% zoom and 320 px wide without sideways page scrolling; wide tables scroll inside a focusable, named scroll area.
- UX-DR11: Reduced motion: no fetching animation, button lift, chart build-up or marker drop; the chart shown complete.
- UX-DR12: Windows High Contrast: chart bars, evidence dots and progress fill keep their shape in system colours (`CanvasText`, `Highlight`).
- UX-DR13: Accessible forms and messages: visible labels tied to fields; error sentence under its field, tied as description, field marked invalid, read with a hidden "Error:"; focus to the first field in error; warnings read with a hidden "Warning:"; icons hidden from screen readers; polite live announcements only.
- UX-DR14: Number and phrase rules from one module (AD-25): odds phrase per FR-8; money `$12,340` / `−$1,240` with a real minus and no colour; Follower Return with one decimal and sign; counts in words and digits; the largest-bet sentence with its three edge cases.
- UX-DR15: On-screen words: "replay" for Simulation (except the FR-9 marker label), "bet"/"resolved bet" for Position/Resolved Position; Glossary terms capitalised; banned and avoided words list with its test (NFR-8).

**Lookup and Verdict page (S1)**
- UX-DR16: Lookup page: eyebrow "SKILL OR LUCK", title "Check a wallet", lede; address field card (label "Wallet address", monospace 48 px field, primary button "Check wallet", hint), 720 px column, focus in the field on open; spaces trimmed; errors "Enter a wallet address." and "This is not a valid wallet address. It should start with 0x and have 42 characters."; focus stays in the field.
- UX-DR17: Sample Wallets list (Offline Mode only): a card with two groups, *Real Wallets* (short monospace addresses) and *Synthetic Wallets* (names with the "synthetic" tag); full-width 48 px link rows with a chevron.
- UX-DR18: Offline pill "Offline Mode · sample data only" on every page in Offline Mode; "Not available offline. In Offline Mode only the Sample Wallets below can be checked."
- UX-DR19: Verdict page order: Verdict card, Explanation (S3), chart card, honesty notes card, Domain table (S3).
- UX-DR20: Verdict card: eyebrow "Wallet analysis", the Verdict hero as main heading (dots hidden from screen readers, read as "Verdict: …"; four variants including the dashed *Not enough data*), the odds phrase in the lede style, the address card on the right, a rule, the stats line ("212 resolved bets · Real PnL $40,180", "Data stored …"), the Exit PnL warning beside the stats when Exit PnL < 0; stacks below 900 px.
- UX-DR21: Address card with copy button (`copy-address.js`): "Copied" for 2 s and an announced status line; on failure the error "Copy failed. Select the address and press Ctrl+C." (⌘C on a Mac), announced, address text selected.
- UX-DR22: Fetching state: heading "Checking 0x7c3a…d3f5", pulsing dots (static with reduced motion), "Fetching trades from Polymarket…"; the page polls job progress (`progress.js`) and replaces the block with the Verdict, moving focus to the Verdict heading.
- UX-DR23: Verdict page states: no history (heading, sentence, link back); Polymarket not answering (heading; "Show stored data from …" only for a snapshot of the same view, else "Try again in a few minutes."); *Not enough data* ("12 resolved bets; at least 30 are needed for a Verdict (18 more)", no odds, no chart, honesty notes still shown); p above 0.5.
- UX-DR24: Chart card: title "Simulated results (10,000 replays with no edge)"; "About this chart" disclosure (in place, closed by default, three sentences); a hint line; the always-visible text alternative box with Real PnL and the odds phrase (plus "That is below all 10,000 replays." when the Real PnL is below every Simulation).
- UX-DR25: Luck chart as server-rendered SVG: centred on $0; axis always includes the Real PnL; end bins labelled "−$195,000 or less" / "$195,000 or more"; 3 px accent marker with dot and "This Wallet: $40,180" label; "above/below all 10,000 Simulations" when beyond; about 240 px tall (200 px below 640); short axis labels below 640 px, end labels hidden below 400 px; bars and axes hidden from screen readers.
- UX-DR26: Chart explore (`chart.js`): bar tooltip with range and count, stays on hover and 300 ms after, Esc hides (WCAG 1.4.13), never covers the marker; bars as one keyboard slider "Replays by result" (Left/Right, Page Up/Down by ten, Home/End) with a spoken value per bar.
- UX-DR27: Wallet marker button: highlights the tail bars and shows the tail label with the exact count ("2,500 of 10,000 replays did this well or better"; "No replay …"; "All 10,000 replays …"); click or Enter pins and announces "Highlight on", second click, Esc or slider unpins ("Highlight off").
- UX-DR28: Chart build-up once per view: bars grow left to right, then the marker drops in, under a second; skipped with reduced motion; complete without JavaScript.
- UX-DR29: Honesty notes card "What this test can't see": three columns (largest-bet share; "N of M positions held to resolution" and Exit PnL; fixed limits and "This is not financial advice."); then the "Left out of the test" line with counts per reason, fees not counted with total, and FR-11's sentences when they apply; then "Computed on … · Seed 44". Always shown, never collapsed; stacks below 900 px.

**Scan pages (S2)**
- UX-DR30: Scans page: New Scan form (Cut-off Date and Number of Wallets 10 to 500 `[ASSUMPTION]`, hints, "Start Scan"); errors "Choose a Cut-off Date.", "The Cut-off Date must be in the past.", "Enter a whole number from 10 to 500."; the "very few bets after this date" warning when the Cut-off Date is less than 90 days ago (Edvard, 2026-10-24); a rough time estimate under the Number of Wallets, computed from the planned request count; in Offline Mode the fields are read-only with an info box; while a Scan runs, an info box and an unavailable but focusable button; "No Scans yet …" empty state.
- UX-DR31: Scan list: run date, Cut-off Date, Wallets, Watchlist size, status text (Finished, Waiting to start, Running with step, Interrupted at, Stopped at …: Polymarket did not answer, Failed, Data rebuilt, cannot resume), under the heading "Your Scans" (Story 4.4); "Resume Scan (Cut-off Date …)" buttons with unique names for interrupted and stopped Scans; unfinished results not shown.
- UX-DR32: Scan progress: a real progress bar read as "84 of 200 Wallets checked", text naming the current step (Reading Markets, Fetching Wallets, Ranking, Hold-up Test, Copy Test with price counts); announcements at most every 10% and at the end; tab title "84/200 · Scan · LiquidOracle" while running (`scans.js`); the favicon progress ring slipped to deferred work (Edvard, 2026-11-26, Story 4.4).
- UX-DR33: Scan header and tabs: eyebrow "WALLET SCAN", title "Scan of N Wallets", ledes with Cut-off Date, run date, population, "N of 100 Markets used", Seed; a third line "Shortlist of about 600 by a quick profit estimate · 4 Wallets not fully read"; Scan summary card; a disclosure listing Markets "not used: partial"; tabs *Watchlist* · *Hold-up Test* · *Copy Test* as links in a navigation region named "Scan" with the current page marked (not an ARIA tab list).
- UX-DR34: Watchlist: table "Wallets rated Skilled (high confidence)" with Wallet (in-app link named "Open Verdict for Wallet …"), Verdict pill, Odds, Resolved bets, Real PnL; no rank column; caption on the sort; "Not fully read" tag with its tooltip; the Minimum Luck Passes info box; whole-row hover with the address as the one link; empty Watchlist sentence.
- UX-DR35: Hold-up Test: two group cards (Verdict pill, odds phrase, resolved bets counted, Real PnL, Wallets in group, dropped, not fully read), the note under them, the dropped-share warning above, and the states for no Passers, empty Comparison Group and a group too small.
- UX-DR36: Copy Test: Random Group Check first (Copy Verdict pill without dots, the Copy p-value phrase, shared-Markets line, not-fully-read count), then the per-Wallet table (1, 5, 30 min with "Extra information" tags on 1 and 30, caption "These per-Wallet numbers are not luck-checked …"), left-out counts per delay, the upper-bound sentence; *Not enough data* with its reason.
- UX-DR37: Back link on the Verdict page when opened from a Watchlist or Copy Test: "← Back to Watchlist (Cut-off Date 1 July 2025)"; Verdict pages opened from a Scan show that Scan's result for that scope (AD-22), with the two-window line and "Computed on 1,234 bets around the Cut-off Date 1 July 2025 · Seed 44" in the honesty notes (Edvard, 2026-11-26, Story 4.5).

**Stage 3 additions**
- UX-DR38: Flag: compact warning box under the odds phrase, "⚠ Likely market maker (heuristic, may be wrong)"; never changes the Verdict.
- UX-DR39: Explanation card directly under the Verdict card, at most 60 words, "Template text" info tag whenever template text is shown.
- UX-DR40: Domain table with Domain, Resolved bets, Domain Verdict pill; note "Each Domain's odds are adjusted for testing several Domains."; info tag naming the label source; *Not enough data* rows; "Domains are not available: the language model did not answer." when the model fails.

### FR Coverage Map

| FR | Epic | What |
|---|---|---|
| FR-1 | 1, 2 | Lookup form and address checks (1); "no Polymarket history" from live data (2) |
| FR-2 | 2 | Fetch, 24-hour cache, Polymarket not answering, pacing |
| FR-3 | 1, 2 | Positions from fills, shares held, resolved rule, fully sold left out (1); both position lists and every exclusion reason on real data (2) |
| FR-4 | 1, 2 | Real PnL on Synthetic Wallets (1); independent reference calculations on three real Wallets, one with fees (2) |
| FR-5 | 1 | 10,000 Simulations, p-value, the five checks |
| FR-6 | 1 | Verdict thresholds, 29 vs 30 |
| FR-7 | 1 | Seed, identical results |
| FR-8 | 1 | Verdict card and odds phrase |
| FR-9 | 3 | Luck chart |
| FR-10 | 1 | Not enough data view |
| FR-11 | 3 | Honesty notes |
| FR-12 | 1, 2 | Synthetic part and size test (1); real Wallets, trim script, default Cut-off Date (2); real Wallets' before and after windows (4, Story 4.7) |
| FR-13 | 1, 4, 5, 6, 7, 8 | S1 types (1); steady sharp, forecaster, speed trader, anchor Markets (4); lucky streak (5); forecaster and speed-trader price paths used (6); split-domain (7); market maker (8) |
| FR-14 | 1 | Offline Mode |
| FR-15 | 7 | Mock LLM Mode |
| FR-16 | 4 | Scan and Watchlist |
| FR-17 | 5 | Hold-up Test |
| FR-18a | 6 | Follower PnL and Follower Return |
| FR-18b | 6 | Random Group Check |
| FR-18c | 6 | Price history and the insurance-pool fallback |
| FR-19 | 7 | Classify Markets |
| FR-20 | 7 | Domain Verdicts |
| FR-21 | 7 | Domain table |
| FR-22 | 8 | Flag |
| FR-23 | 8 | Explanation |
| FR-24 | 8 | Explanation check |

## Epic List

### Epic 1: Check a synthetic Wallet offline (S1, target 5 to 10 Nov)
The examiner clones the repository, runs the three README commands, picks a Synthetic Wallet in Offline Mode and sees a correct Verdict card; the tests pass in CI on Windows, macOS and Linux. The Skill Test, the riskiest part, is built and proven first, on Wallets with known answers.
**FRs covered:** FR-1 (form and checks), FR-3 (basic), FR-4 (synthetic), FR-5, FR-6, FR-7, FR-8, FR-10, FR-12 (synthetic part), FR-13 (S1 types), FR-14

### Epic 2: Check a real Wallet (S1, target 11 to 13 and 17 to 19 Nov)
The user pastes any Polymarket address and gets a Verdict from live data; a second lookup is instant, outages are handled, and the 10 real Sample Wallets work offline.
**FRs covered:** FR-1 (no history), FR-2, FR-3 (all exclusions), FR-4 (independent reference calculations), FR-12 (real Wallets)

### Epic 3: A Verdict you can trust (S1, target 20 to 23 Nov)
The user sees the luck chart with the Wallet's marker and its text alternative, and the honesty notes; the page works by keyboard and screen reader, in both themes and at any width. Stage 1 is done: all tests pass and the README is updated.
**FRs covered:** FR-9, FR-11

### Epic 4: Scan for skilled Wallets (S2, target 24 to 26 Nov)
The user chooses a Cut-off Date, runs a Scan that can be left, interrupted and resumed, and sees the Watchlist with the Minimum Luck Passes and the population tested.
**FRs covered:** FR-16, FR-13 (S2 types)

### Epic 5: Does the skill last? Hold-up Test (S2, target 27 to 28 Nov)
The user compares the Before-Cut-off Passers with the Comparison Group on the bets after the Cut-off Date. Epics 4 and 5 are the stage 2 minimum (PRD §6.1).
**FRs covered:** FR-17

### Epic 6: Could a late follower have profited? Copy Test (S2, target 29 Nov to 1 Dec)
The user sees Follower PnL and Follower Return at 1, 5 and 30 minutes and the Random Group Check; a Copy Test on real data is run and reported (SM-5). Stage 2 is done. Beyond the stage 2 minimum (PRD §6.1).
**FRs covered:** FR-18a, FR-18b, FR-18c

### Epic 7: Where is the edge? Domain Verdicts (S3, parked 20 Nov: picked back up only if all of stage 2 is done before 1 Dec)
The user sees a Domain table on the Verdict page, with or without a model key.
**FRs covered:** FR-15, FR-19, FR-20, FR-21

### Epic 8: Bots and plain-language explanations (S3, parked 20 Nov: only after Epic 7, if all of stage 2 is done before 1 Dec)
The user sees a market-maker Flag where it applies and a checked Explanation of at most 60 words.
**FRs covered:** FR-22, FR-23, FR-24

## Epic 1: Check a synthetic Wallet offline

The examiner clones the repository, runs the three README commands, picks a Synthetic Wallet in Offline Mode and sees a correct Verdict card; the tests pass in CI on Windows, macOS and Linux. The Synthetic Wallets with known answers are built before the Skill Test that must match them (Edvard, 2026-10-24). If the epic runs late, only the polish in Story 1.7 moves later within stage 1; Story 1.5 stays before 1.7, because the Verdict card needs its phrases, and Story 1.4's checks are never cut.

### Story 1.1: Project skeleton that starts

As the examiner,
I want to install and start the app with a few documented commands,
So that I can see it run on my own machine before anything else is built.

**Acceptance Criteria:**

**Given** a fresh clone with uv installed
**When** I run `uv sync` and `uv run liquidoracle run`
**Then** a placeholder *Check a wallet* page is served at `http://127.0.0.1:8044`, bound to 127.0.0.1 only, with debug and the reloader off and `load_dotenv=False` (AD-23, NFR-3)
**And** the repository follows the spine's Structural Seed: `src/liquidoracle/` with `records`, `web`, `services`, `core`, `data`, `__main__.py` (commands `run`, `load-sample`, `make-synthetic`; the last two report "not built yet"), `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, `tests/`, `tests/online/`, with the pinned stack versions.

**Given** the app starts
**When** settings are read
**Then** one frozen settings object is built once, with priority command-line flag, then `.env`, then the default (AD-13), holding at least `PORT` (8044), `SEED`, `POLYMARKET_REQUESTS_PER_SECOND` (5), `OFFLINE` and `ANTHROPIC_API_KEY`
**And** a `POLYMARKET_REQUESTS_PER_SECOND` above 5 stops the start with a plain message (NFR-6)
**And** `.env.example` lists every key, and no code outside `__main__` and `settings` reads the environment.

**Given** the test suite
**When** it runs
**Then** every test runs with sockets blocked (`--disable-socket`), a planted test that opens a socket fails, and `tests/online/` is marked and excluded (AD-17)
**And** the import-rule test parses every module and fails on a planted forbidden import, such as `requests` inside `core` (AD-1).

**Given** a push to GitHub
**When** CI runs
**Then** `uv sync --locked` and `uv run pytest` run on Windows, macOS and Linux with Python 3.12 and 3.14, and a failure on any of them fails the build (NFR-2)
**And** each test names the FR or AD it checks in its docstring or marker (Conventions, NFR-7)
**And** a `slow` marker exists: marked checks run their full 1,000 repetitions on Linux with Python 3.14 and 100 repetitions on the other five jobs, set by one option, never by skipping (AD-17)
**And** if the course organisation blocks GitHub Actions, this is found on the first push and raised with Edvard (open risk from architecture).

**Given** the README
**When** a new reader opens it
**Then** it states the prerequisite (uv), the install line, the start command and the address to open.

### Story 1.2: Positions from fills

As a user checking a Wallet,
I want its fills combined into bets by one set of rules,
So that the Verdict rests on the bets the Wallet really held to resolution.

**Acceptance Criteria:**

**Given** the shared record types (`Position`, `ActivityRow`, `Market`, `PricePoint`) in `records`, with no app imports (AD-1)
**When** several BUY fills of the same outcome in the same Market are built
**Then** they form one Position whose Entry Price is the share-weighted average price of its BUY fills, which sells do not change (FR-3; AD-10, Edvard, 2026-11-11)
**And** shares held at resolution = Σ bought − Σ sold for that token, from activity rows; REDEEM rows are never a share source (AD-10).

**Given** a Market
**When** the builder decides whether it is resolved
**Then** it is resolved only when the Market data says closed, its outcome prices are exactly {0, 1}, and it has a resolution time; anything else is left out as "unclear resolution" (AD-7).

**Given** Positions with sells
**When** they are built
**Then** a fully sold Position is left out as "sold before resolution" and counted (FR-3)
**And** a partly sold Position enters with the shares still held at the original Entry Price, and its sold shares count toward Exit PnL = Σ shares sold × (sell price − p) (Glossary)
**And** a Position whose shares held are not within 0 < s ≤ shares bought is left out as "not explained" (AD-11)
**And** a Position with less than 1% of its bought shares and fewer than 1 share held is a Sliver: returned apart, its money kept for Real PnL and the Simulations, and counted neither as tested nor as left out (PRD Glossary, AD-11; Edvard, 2026-11-11).

**Given** a Market where the Wallet has a SPLIT, MERGE or CONVERSION row
**When** it is built
**Then** that Market's Positions are left out as "split or merged" (AD-11; planted rows in the test).

**Given** a buy fill in a Market with fees
**When** its Own Fee is computed
**Then** it is cash paid − shares × price (AD-12); the check against the Market's fee schedule is added in Epic 2.

**Given** any set of fills
**When** the builder runs
**Then** `core/positions` is the only code that builds Positions, and it returns the window size, the excluded count per reason, the tested count and the tested Positions (AD-11)
**And** it is a pure function with a test for each rule above.

### Story 1.3: Synthetic Wallets with known answers

As the examiner,
I want made-up Wallets whose correct Verdict is known in advance,
So that the Skill Test can be checked against answers fixed before it was written.

**Acceptance Criteria:**

**Given** `uv run liquidoracle make-synthetic`
**When** it runs
**Then** it generates the stage 1 types of FR-13: hand-check (10 bets at 0.50, all won), coin-flipper (1,000 Wallets of 100 bets, prices uniform from 0.10 to 0.90, outcomes drawn at those prices), favourite buyer (100 at 0.90, exactly 90 won), sharp trader (100 at 0.50, exactly 70 won), thin wallet (29 Resolved Positions), stop-loss trader (100 at 0.50 with no edge; the price moves fairly and bets that fall to 0.25 are sold there: 67 sold, 17 of them in Markets their side later won, and 33 held, all won; Edvard, 2026-11-13), with the price paths these need
**And** it writes fills (activity rows) first and derives the positions lists and Markets from them with the one serializer, using its own fixed constant, not the `SEED` setting (AD-14)
**And** every tested synthetic Position has its own Market.

**Given** the generator
**When** it runs twice
**Then** the output files are byte-identical (FR-13).

**Given** each generated Wallet
**When** it goes through the Story 1.2 builder
**Then** a test confirms the intended bets: sharp trader 100 Resolved Positions at 0.50 with exactly 70 won; favourite buyer 100 at 0.90 with exactly 90 won; hand-check 10 won at 0.50; thin wallet 29; stop-loss trader 33 held, all won, and 67 sold at 0.25, each with negative Exit PnL
**And** each type's expected Verdict and p-value range from the FR-13 table is stored as a fixture next to it, before the Skill Test exists.

**Given** the 1,000 coin-flippers
**When** the repository is committed
**Then** they are not in it; only the small Synthetic Wallets are, and the coin-flippers are regenerated on load (FR-12, Story 1.6).

### Story 1.4: The Skill Test

As a user,
I want a Wallet's result compared with 10,000 replays of pure luck,
So that the Verdict says how often a trader with no edge would do as well.

**Acceptance Criteria:**

**Given** a set of Resolved Positions
**When** the Skill Test runs
**Then** Real PnL = Σ s · (o − p) − Own Fees over the tested Positions and the Slivers (FR-4), equal to the Synthetic Wallets' hand values to the cent; Slivers are simulated too but never counted toward the 30 minimum (Story 1.2; Edvard, 2026-11-11)
**And** each of 10,000 Simulations draws one uniform U per Market, shared by every Position in that Market (one side wins when U < p, the other when U > 1 − p), so each Position wins with probability equal to its Entry Price (AD-20)
**And** for the p-value only, win and loss amounts are rounded to whole cents once, with Own Fees left out, and the real result and every Simulation sum those integers, so p = (1 + number of Simulations ≥ the real result) / 10,001 counts ties exactly (FR-5; Conventions › Money, P-3)
**And** the Real PnL shown and stored is the exact sum, never the rounded one, and a test on a Wallet with many small fractional amounts shows the two differ while the exact one matches its hand value to the cent (FR-4; Edvard, 2026-11-05).

**Given** the Story 1.3 fixtures
**When** the checks run
**Then** hand-check p is between 0.0003 and 0.002, checked on the engine directly because its 10 bets are below the 30-bet minimum (FR-13); sharp trader p < 0.01; favourite buyer p ≥ 0.05; across the 1,000 coin-flippers p < 0.05 for at most 7% and p < 0.01 for at most 2% (FR-5)
**And** adding a fixed fee to every Position of a Synthetic Wallet lowers Real PnL by exactly the total fee and leaves the p-value and Verdict unchanged for the same Seed (FR-5)
**And** a Wallet whose bets all won at prices near 1 gets a p-value within sampling error of the product of its prices (the tie test).

**Given** a p-value
**When** the Verdict is chosen
**Then** p < 0.01 gives *Skilled (high confidence)*, p < 0.05 *Likely skilled*, otherwise *No evidence of skill*; 29 Resolved Positions give *Not enough data* and no p-value, 30 give a Verdict (FR-6).

**Given** the engine-level path the hand-check uses to skip the 30-bet minimum
**When** any code outside the tests runs a Skill Test
**Then** it can only call the public Skill Test function, which always applies the minimum and has no parameter or setting that turns it off; the engine-level function is private to `core/skilltest` and only the tests call it
**And** a rule test fails if any module outside `core/skilltest` and the tests references the engine-level function; it covers `services` and `web` as soon as they exist (Edvard, 2026-10-24).

**Given** the same data and Seed
**When** the test runs again, also in two subprocesses with different `PYTHONHASHSEED` values
**Then** the p-value and Verdict are identical (FR-7)
**And** a stored golden result, the exact count of Simulations at or above the Real PnL for fixed Synthetic Wallets and a fixed Seed, is reproduced exactly on every CI job, so a system that sums differently fails (AD-17)
**And** the 1,000 coin-flipper check is marked `slow`; on the other jobs it runs on 100 coin-flippers with the same 10,000 Simulations each, and the determinism checks are never reduced (AD-17)
**And** Positions are sorted by (`condition_id`, `token_id`) before drawing, each random unit gets its own generator from `SeedSequence(SEED, spawn_key=core.rng.spawn_key(purpose, id))`, and neither `random`, numpy's global state nor `hash()` is used (AD-15).

**Given** `core/skilltest`
**When** the import-rule test runs
**Then** it imports only `records`, the standard library and numpy (AD-1)
**And** a result stores its Seed, scope `lookup`, counts, the chart bins and the exact count of Simulations at or above the Real PnL (AD-22, AD-25), and the time for a 1,000-Position Wallet is measured and noted (NFR-10).

### Story 1.5: Number phrases in one place

As a user,
I want odds and money written the same way everywhere,
So that the card, the chart and later the Explanation never disagree.

**Acceptance Criteria:**

**Given** `core/phrases.py` (AD-25)
**When** a p-value is phrased
**Then** it gives "about 1 time in N" with N = 1/p to 2 significant figures and a whole number below 10, so never a decimal (0.0033 gives "about 1 time in 300", 0.0099 "about 1 time in 100", 0.25 "about 1 time in 4", 0.45 "about 1 time in 2", 0.11 "about 1 time in 9"), "fewer than 1 time in 10,000" when no Simulation reached the Real PnL and for 1/10,001, and "more than half the time" above 0.5 (FR-8)
**And** money is written `$12,340` and `−$1,240` with a real minus sign (UX-DR14)
**And** the *Not enough data* sentence reads "12 resolved bets; at least 30 are needed for a Verdict (18 more)" (FR-10).

**Given** later stories that need a number phrase
**When** they add one
**Then** they add it to this module, which the templates, the FR-24 check and the tests all use.

### Story 1.6: Offline Mode and loading the Sample Dataset

As the examiner,
I want to load the Sample Dataset and run the app with no network and no keys,
So that I can check it without Polymarket or our accounts.

**Acceptance Criteria:**

**Given** `uv run liquidoracle load-sample`
**When** it runs
**Then** it always writes `instance/offline.db` (git-ignored), whatever the flags, through the normal fetch pipeline with `OfflineClient` (AD-14), and regenerates the 1,000 coin-flippers into `instance/` from the generator's constant
**And** `OfflineClient` returns the same `records` types through the same client interface the live client implements in Epic 2 (AD-2).

**Given** the store
**When** data is saved
**Then** only `data/store.py` runs SQL, with plain `sqlite3`, WAL mode, a busy timeout, one connection per thread and `BEGIN IMMEDIATE` (AD-6, NFR-4)
**And** `schema.sql` creates only the tables this epic needs, with `PRAGMA user_version`
**And** a Wallet's data is written as a snapshot with a `fetch_id` that becomes visible in one final step (AD-19).

**Given** Offline Mode (`--offline` or `OFFLINE=true`)
**When** the app runs
**Then** services get `OfflineClient` and `instance/offline.db`, nothing else branches on the mode (AD-13), and looking up an address outside the Sample Dataset raises `NotAvailableOffline` (FR-14).

**Given** the round-trip test
**When** generator → `OfflineClient` → pipeline → Skill Test runs with sockets blocked
**Then** every Synthetic Wallet gets its intended bets and its expected Verdict from the Story 1.3 fixtures (AD-14)
**And** a test fails if the committed Sample Dataset exceeds 25 MB (FR-12); raised to 50 MB in Story 2.6.

### Story 1.7: Check a wallet and see its Verdict card

As the examiner,
I want to pick a Sample Wallet on the start page and see its Verdict card,
So that I can see the app's answer for a Wallet whose correct answer I know.

**Acceptance Criteria:**

**Given** the *Check a wallet* page (UX-DR16)
**When** it opens
**Then** it shows the eyebrow "SKILL OR LUCK", the title, the lede and the address field card, with focus in the field
**And** an empty submit shows "Enter a wallet address.", a wrong format shows "This is not a valid wallet address. It should start with 0x and have 42 characters.", nothing is fetched, the field is marked invalid with the error tied to it, and focus stays in the field (FR-1, UX-DR13)
**And** leading and trailing spaces are removed, and a valid address opens `/wallet/0x…` in lower case.

**Given** Offline Mode
**When** any page opens
**Then** the top bar shows the Offline pill "Offline Mode · sample data only" (UX-DR18), and the Lookup page shows the Sample Wallets list with the *Synthetic Wallets* group, each tagged "synthetic" (UX-DR17; the *Real Wallets* group arrives in Epic 2)
**And** an address outside the Sample Dataset shows "Not available offline. In Offline Mode only the Sample Wallets below can be checked." (FR-14).

**Given** a Sample Wallet with a Verdict
**When** its Verdict page opens
**Then** the Verdict card shows the eyebrow, the Verdict hero as the page's main heading read as "Verdict: …" with the dots hidden from screen readers (all four variants), the odds phrase from `core/phrases`, and the stats line "N resolved bets · Real PnL $X" with "Data stored …" (FR-8, UX-DR20)
**And** the sharp trader shows *Skilled (high confidence)* and a coin-flipper the tests expect not to pass shows *No evidence of skill* (UJ-3).

**Given** the thin wallet
**When** its Verdict page opens
**Then** it shows the dashed *Not enough data* hero and "29 resolved bets; at least 30 are needed for a Verdict (1 more)", with no odds phrase and no chart (FR-10, UX-DR23)
**And** this proves Story 1.4's bypass is off on the normal path: the hand-check Wallet (10 bets) and the thin wallet (29) get *Not enough data* and no p-value through the lookup service and their Verdict pages (Edvard, 2026-10-24).

**Given** any page
**When** it renders
**Then** it is complete without JavaScript (AD-18), declares English, has one main heading, "Skip to content" as the first Tab stop, the top bar with the logo and the *Check a wallet* link, and its tab title (UX-DR4, UX-DR5, UX-DR8)
**And** the logo (32 px in the top bar) and the favicon come from `mockups/logo/`, one colour, the favicon switching to the dark-theme blue in a dark browser (UX-DR6)
**And** a bad address such as `/wallet/abc` shows *Page not found* with a link to *Check a wallet* (UX-DR7)
**And** colours, type and spacing come from the DESIGN.md tokens, and IBM Plex Serif 600/700 is served locally with its OFL licence, with nothing loaded from the internet (UX-DR1, UX-DR3)
**And** a test over every template and fixed text fails on a banned or avoided word (NFR-8).

**Given** a fresh checkout
**When** CI runs the README's three commands (`uv sync`, `uv run liquidoracle load-sample`, `uv run liquidoracle run --offline`) and requests the sharp trader's Verdict page
**Then** the page contains "Skilled (high confidence)" (NFR-1, AD-17)
**And** the README lists these commands, the prerequisites and the address to open.

**Polish that may move later within stage 1 if Epic 1 runs late:** the dark theme and its toggle (UX-DR2), hover and lift states (UX-DR9), and the responsive details (UX-DR10). They are then done in Epic 3. **Moved to Story 3.4** (Edvard, 2026-11-20, at the stage 1 checkpoint: Epic 1 ran late). Story 1.7 keeps a plain focus ring, because that is accessibility, not polish. **Later the same day Edvard pulled the dark theme and its toggle (UX-DR2) back into Story 1.7**, dark by default: no dark theme was a dealbreaker for him. Hover and lift (UX-DR9) and the responsive details (UX-DR10) stay in Story 3.4.

## Epic 2: Check a real Wallet

The user pastes any Polymarket address and gets a Verdict from live data; a second lookup is instant, outages are handled, and the 10 real Sample Wallets work offline. Also holds the two items moved from Epic 1: ladders and the measured share of undetected links (AD-20). If the epic runs late, ladder detection in Story 2.4 slips first, because the measured share then reports ladders as possibly linked and nothing becomes wrong; negative-risk coupling never slips (Edvard, 2026-10-24).

### Story 2.1: Polymarket client, read-only and polite

As a user,
I want the app to read Polymarket's public data carefully and never anything else,
So that lookups work, outages are handled, and the app never touches a wallet or overloads the service.

**Acceptance Criteria:**

**Given** `data/polymarket.py`
**When** any code needs Polymarket data
**Then** only this module makes the request, as a GET to a public Data API v2 or Gamma endpoint with no keys, never Data API v1 (AD-2, NFR-11); a test fails on a v1 URL or a non-GET request
**And** it returns `records` types, and nothing above `data/` sees raw JSON.

**Given** a cursor-paged list
**When** the client walks its pages
**Then** every page is requested with identical parameters apart from the cursor (AD-2, tested)
**And** a page that times out mid-walk restarts the walk with a smaller `limit`; if that also fails, the read is marked partial (AD-3).

**Given** two threads making requests
**When** they run at the same time
**Then** one process-wide limiter guarded by a lock keeps the combined pace at or below `POLYMARKET_REQUESTS_PER_SECOND` (AD-3, NFR-6, tested with a fake clock).

**Given** a timeout, 429, 503, a Gamma or CloudFront 403, or an empty Gamma 404 on a list route, or a 500, 502, 504 or failed connection (Edvard, 2026-11-20)
**When** it happens
**Then** the request is retried at most 3 tries in all; a `Retry-After` header is waited out exactly instead of the client's own back-off, unless it is longer than 60 s, which raises `PolymarketUnavailable` at once (Edvard, 2026-11-20); after the third try `PolymarketUnavailable` is raised (AD-3, the one retry policy)
**And** any other 4xx raises `PolymarketBadRequest` and is logged; a 400 "protocol contract address" is raised as its own kind, for the Scan in Epic 4 (AD-9)
**And** all of this is tested against a fake transport, with sockets blocked.

**Given** `tests/online/`
**When** a developer runs it by hand
**Then** one smoke test fetches a known Sample Wallet's first page live; it never runs in CI (AD-17).

### Story 2.2: A Wallet's bets as one complete snapshot

As a user,
I want the app to fetch a Wallet's latest 2,000 bets in resolved Markets in one complete piece,
So that the Verdict never rests on a half-finished fetch or on bets from the wrong time.

**Acceptance Criteria:**

**Given** a lookup with no Cut-off Date
**When** `positions_near(wallet, cutoff=None, side, limit=2000)` runs (AD-8, the one client function)
**Then** it reads the OPEN list in full and the CLOSED list newest-first by `TIMESTAMP` with no `end` bound, stopping when a page's oldest `last_event_at` is earlier than the 2,000th-latest resolution time collected (AD-7)
**And** the window is the latest 2,000 Positions in resolved Markets by resolution time, with the cap applied before exclusions (AD-8).

**Given** the window's Markets
**When** their data is fetched
**Then** Gamma is asked for 20 Markets per request with `include_tag=true`, and resolution, resolution time (`closedTime`, never `last_event_at`), outcomes, fee schedule, start date and event tags come only from Gamma (AD-7, AD-10; tags used from Story 7.1; AI's proposal, Edvard confirmed, 2026-11-05)
**And** this read is not run on the Sample Wallets until Edvard's definitions and labels are committed, because it would fetch tags for the events behind his 50 hand-label Markets (FR-19; Edvard's rule, 2026-11-05)
**And** records of resolved Markets and their fee schedules never expire once stored; records of open Markets expire with the Wallet lists (AD-4).

**Given** the window
**When** its activity is read
**Then** the read uses types TRADE, REDEEM, SPLIT, MERGE, CONVERSION, sends `start` and `limit` explicitly, drops `is_combo` rows, and covers the earliest Gamma start date to the latest `closedTime` among the window's Markets (AD-7, AD-10)
**And** on reaching `ACTIVITY_ROW_CAP` (150,000 rows, the Sample Dataset capture's cap; Edvard, 2026-11-20), exactly the Positions whose Market `closedTime` lies after the last row read are left out as "not fully read" (AD-7, AD-11)
**And** identical-looking rows are kept as separate fills, never de-duplicated.

**Given** a fetch
**When** it writes to the store
**Then** it is a snapshot with a `fetch_id` that becomes visible in one final step, readers see only complete snapshots, and a per-Wallet lock shared by web threads and the worker allows one fetch of a Wallet at a time (AD-19)
**And** the new tables this needs are added to `schema.sql` with a raised `user_version` (AD-6)
**And** the rules are tested on small fixtures cut from the real capture by a script, through a fake transport.

### Story 2.3: Every exclusion and fee on real data

As a user,
I want every bet the test cannot judge fairly left out, counted and named,
So that the Verdict is honest about what it rests on.

**Acceptance Criteria:**

**Given** real data
**When** the builder runs
**Then** it also leaves out, with one stored reason each: a token found only in activity rows; a Position whose share gap between the positions list and activity is above 1% `[ASSUMPTION]`, storing the gap's size; a Position left unread by a capped or refused read ("not fully read"); a Market with unclear resolution (FR-3, AD-11)
**And** the same rules apply before and after the Cut-off Date (tested on both sides).

**Given** a buy fill in a Market with fees enabled
**When** its Own Fee is checked against the Market's Gamma `feeSchedule` (rate and exponent) with a rounding tolerance
**Then** a fee that passes counts in Real PnL; a maker fill's fee of 0 passes; a negative Own Fee fails (moved here from Story 2.2, Edvard, 2026-11-20; since Story 2.3 the Skill Test also refuses one); a fee that fails is stored with its value, counts as 0, keeps its Position in the test, and is counted with its recorded total for the card (AD-12)
**And** v2's `entry_fees_usdc` is never used.

**Given** fixtures cut from the real capture
**When** the tests run
**Then** 0x729806's split and merge Markets are left out as "split or merged", 0x94884d's unredeemed losers from the OPEN list count as losses, and the fee Wallets' fees pass the schedule check, except fees paid before Polymarket lowered a Market's rate (Gamma shows only today's rate): 0x091596's $44.31 at 5% in a Market now at 3%, and 7 of 0x0f4b0a's fees ($0.28) at 4-5% in Markets now at 1%. These fail, count as 0 and are counted (Edvard, 2026-11-21: the check stays strict; reversed in Story 2.8 on 2026-11-23)
**And** the share of Positions left out is available to the card, with the over-10% flag (FR-11).

### Story 2.4: Linked bets on real data

As a user,
I want bets that depend on the same result to win and lose together in the replays,
So that a Wallet is not credited with independent evidence it does not have.

**Acceptance Criteria:**

**Given** the Markets of one negative-risk event (only one can win)
**When** the Skill Test simulates them
**Then** they share one uniform U split into disjoint intervals by price, each Market keeps a win chance equal to its price, and at most one wins per Simulation (AD-20; tested on a planted event of three Markets); this extends Story 1.4's per-Market draw and never slips
**And** a CONVERSION row, which names the event rather than a Market, is kept in the window and leaves out every Position of its event as "split or merged" (AD-11; Edvard, 2026-11-21).

**Given** a ladder (same underlying, same resolution date, different thresholds)
**When** it is detected
**Then** its Markets share one U with nested intervals ordered by price, and a planted ladder Wallet has a test (AD-20)
**And** if this part slips, ladders are simply counted in the measured share below. (Slipped, Edvard, 2026-11-21: Gamma gives no threshold number, so detection would mean parsing question text.)

**Given** a result
**When** it is stored
**Then** it stores the share of tested Positions whose Gamma event holds another tested Position not coupled above, for the FR-11 note over 20% `[ASSUMPTION]` (AD-20)
**And** the share is computed for the fixture Wallets and noted, whatever it comes out as; the 10 real Sample Wallets' share moves to Story 2.6, which first builds their Gamma records (Edvard, 2026-11-21).

### Story 2.5: Look up a live Wallet

As a user,
I want to paste any Polymarket address and get its Verdict, quickly the second time,
So that I can check a Wallet before copying it, even when Polymarket is having trouble.

**Acceptance Criteria:**

**Given** an address with no fresh stored snapshot
**When** the user looks it up
**Then** a `job` row is inserted (`queued`) and the Verdict page shows the fetching state: the heading "Checking 0x7c3a…d3f5", the fetching indicator and "Fetching trades from Polymarket…" (UX-DR22)
**And** one daemon worker thread, started only by `liquidoracle run`, claims the job with one atomic update checking `rowcount == 1`, and runs waiting lookups before anything else (AD-5)
**And** `progress.js` polls `GET /jobs/<id>/progress` (`{status, phase, done, total, message}`); when the job is done the Verdict replaces the block and focus moves to the Verdict heading; without JavaScript a plain link reloads the page
**And** a job left `running` at startup becomes `interrupted`.

**Given** a lookup of the same Wallet within 24 hours of a complete snapshot that covers the window
**When** it runs
**Then** it makes 0 network calls, counted through the fake transport (FR-2, AD-4)
**And** the card shows "Data stored …" with the snapshot's date.

**Given** a valid address with no Polymarket history
**When** it is looked up
**Then** the page shows the heading "No Polymarket history found", "No Polymarket history found for this address.", the hint to use the address on the Polymarket profile page, and a link back to *Check a wallet* (FR-1, UX-DR23).

**Given** Polymarket not answering (`PolymarketUnavailable`)
**When** a lookup needs it
**Then** the page shows the heading "Polymarket did not answer" and the button "Show stored data from …" only when a snapshot of the same view exists, otherwise "Try again in a few minutes."; a snapshot of another view is never offered (FR-2, AD-4)
**And** no page ever shows a raw exception.

**Given** a 1,000-Position Wallet's stored data (made up for the test: the real Sample Wallets arrive in Story 2.6; Edvard, 2026-11-21)
**When** its Verdict is computed
**Then** it returns its Verdict within 10 seconds, measured and noted (NFR-10); Story 2.6 measures the real Wallets again.

Notes (Story 2.5, 2026-11-21): "no history" means both positions lists are empty (Data API v2 answers an unused address with 200 and empty lists, checked live); a Wallet with only open bets gets the normal *Not enough data* Verdict. Offline Mode queues no jobs: its stored snapshots never go stale, since there is nothing to refresh them from.

### Story 2.6: Real Wallets in the Sample Dataset

As the examiner,
I want the 10 real Wallets in the Sample Dataset, built in a way I can repeat,
So that I can check real results offline and see how the committed data was made.

**Acceptance Criteria:**

**Given** the raw capture zip and its additions file (both kept outside the repository)
**When** the build-sample script runs on them
**Then** it first checks each against its SHA-256 file and refuses to run on a mismatch
**And** it reads the 10 Sample Wallets named in `spike/FINDINGS.md` (not the spares; the zip's own pick file was zipped before the 23 October swap, so it is not read; Edvard, 2026-11-23) and writes their positions lists, activity rows and Gamma Markets as `records` JSON with the one serializer into `sample_data/` (AD-14).
**And** the additions file holds what the capture lacks, fetched once, read-only, with the app's own client: the Gamma records of every Market the windows read (the capture holds none), and 0xd218e4's newest CLOSED pages (the capture kept only its oldest 60,000 CLOSED rows), so that Wallet's data comes from two dates, 23 October and 23 November 2026 (Edvard, 2026-11-23, Story 2.6).

**Given** the capture
**When** the windows are built
**Then** the lookup window (latest 2,000) is built by the app's own rules (AD-7, AD-8, AD-11), and the default Cut-off Date, 1 July 2025, is stored with the Sample Dataset (FR-12); Story 4.7 extends this same script with the before and after windows around it, once Story 4.1 exists
**And** whatever the capture lacks is left out by the normal rules, as "not fully read" for the two largest Wallets, never patched by hand (FR-12 one-way limitation); in the lookup window this leaves every Position of 0xd218e4, 0x63d43b and 0x729806 "not fully read" (Story 2.6, 2026-11-23)
**And** price windows are not included yet; Epic 6 extends this same script to add the Copy Sample's windows.

**Given** the same zip
**When** the script runs twice
**Then** the output is identical, the committed Sample Dataset stays under 50 MB (raised from 25 MB: the 10 real Wallets' needed rows come to about 35 MB; Edvard, 2026-11-23), and nothing in `sample_data/` is edited by hand (AD-14)
**And** the README says the raw capture is not in the repository and that the committed set was built by this script.

**Given** Offline Mode
**When** the examiner opens the Lookup page
**Then** the Sample Wallets list shows the *Real Wallets* group with shortened addresses, and each of the 10 can be looked up with sockets blocked (FR-12, FR-14, UX-DR17)
**And** each real Wallet's Verdict is recorded in a note next to the pick's estimate, whatever it comes out as, and nothing is tuned to match (NFR-13)
**And** each real Wallet's uncoupled share (AD-20, moved here from Story 2.4) is recorded in the same note.
**And** the Verdict time from stored data for the largest real Wallets (NFR-10, within 10 seconds), and the live lookup time including the Polymarket fetch for at least one of them, are measured and noted; the fetch time has no 10-second target, since NFR-10 covers stored data (Edvard, 2026-11-21, Story 2.5).

### Story 2.7: Real PnL checked independently

As the examiner,
I want the app's Real PnL for three real Wallets checked against numbers that do not come from the app,
So that a mistake in the app's maths cannot pass its own test.

**Acceptance Criteria:**

**Given** 0x29306d (23 bets)
**When** a fresh AI helper works out its Real PnL step by step, given only the PRD and the Wallet's file in the Sample Dataset and never the app's code, following FR-3, FR-4 and the Glossary (resolved Markets only, fully sold left out, partly sold at shares held, Own Fees subtracted)
**Then** its working is committed as CSV, one row per Position, before any test compares it with the app (Edvard, 2026-11-23; this replaces his own spreadsheet, planned on 2026-10-24).

**Given** 0x0f4b0a (fees $0.60) and 0x091596 (fees $1,138; its Romania event is left out because of a CONVERSION, Story 2.4)
**When** their reference values are computed
**Then** they come from a separate small script written from the PRD's definitions alone (Real PnL = Σ s · (o − p) − Own Fees; shares held = bought − sold; Own Fee = cash paid − shares × price), without reading the app's code, so the check cannot copy the app's mistake (Edvard, 2026-10-24)
**And** the script imports nothing from `liquidoracle`, and a rule test enforces that.

**Given** the three reference values
**When** the test runs
**Then** the app's Real PnL for each equals its reference to the cent (FR-4)
**And** the test file says which number came from where: the fresh helper's calculation for 0x29306d, the independent script for the other two
**And** if a value differs, the cause is found and logged (app, script or helper's calculation) and the expected value is never changed to match without a written reason.

### Story 2.8: The fee check accepts an earlier rate

As a user,
I want fees that were real when they were paid to count in Real PnL,
So that a Wallet's Real PnL does not look better just because Polymarket changed a Market's rate later.

**Acceptance Criteria:**

**Given** a buy fill in a Market with fees enabled and a fee schedule
**When** its Own Fee is checked (AD-12)
**Then** it passes if it equals shares × rate × (p × (1 − p))^exponent within the $0.0001 tolerance, with the listed exponent and either the listed rate or any whole-percent rate from 1% to 10% `[ASSUMPTION]` (FR-4; Edvard, 2026-11-23, reversing the strict check of Story 2.3)
**And** a negative fee, a fee that fits no such rate, a fee above the 10% rate, and a non-zero fee in a Market with no schedule still fail, count as 0 and are counted for the card.

**Given** the 9 fees that failed in Story 2.7 (7 on 0x0f4b0a, 2 on 0x091596)
**When** the reference Wallets are computed again
**Then** all 9 pass, and the independent script's fee rule is changed to the same FR-4 sentence without reading the app's code
**And** the new reference values are the script's own "failed fees counted as recorded" totals from Story 2.7 (0x0f4b0a −188.77, 0x091596 −49,615.70), the app equals them to the cent, and 0x29306d's value is checked again
**And** every Sample Dataset Wallet's stored result that changes is noted.

## Epic 3: A Verdict you can trust

The user sees the luck chart with the Wallet's marker and its text alternative, and the honesty notes; the page works by keyboard and screen reader, in both themes and at any width. Stage 1 is done at the end: all tests pass and the README is updated. If the epic runs late, the chart's build-up animation slips first, then the tooltip details in Story 3.2; the text alternative and the honesty notes never move (Edvard, 2026-10-24).

### Story 3.1: The luck chart

As a user,
I want to see where the Wallet's result sits among 10,000 replays of luck,
So that I can see with my own eyes how unusual it is.

**Acceptance Criteria:**

**Given** a Verdict with a p-value
**When** the Verdict page renders
**Then** the chart card shows the title "Simulated results (10,000 replays with no edge)", the luck chart as server-rendered SVG, a one-line hint and the always-visible text alternative "This Wallet made $X on N resolved bets. In 10,000 replays with no edge, a result this good came up {odds phrase}.", followed by "That is below all 10,000 replays." when the Real PnL is below every Simulation (Edvard, 2026-11-25, at Story 3.5) (FR-9, UX-DR24, PRD §8)
**And** the chart is centred on $0, its dollar axis always includes the Real PnL, the end bars hold everything beyond the axis and are labelled "−$195,000 or less" / "$195,000 or more" style, and the marker is a 3 px accent line with a dot and the label "This Wallet: $X" (UX-DR25)
**And** the bins and the marker count come from the stored result (AD-25), not recomputed in the template.

**Given** a Real PnL above every Simulation (or below every one)
**When** the chart renders
**Then** the axis stretches to include it and the marker label reads "above all 10,000 Simulations" (or "below …"); a planted test checks both the range and the label (FR-9).

**Given** the chart card
**When** the user opens "About this chart"
**Then** it opens in place, closed by default, with the three plain sentences of UX-DR24.

**Given** a screen reader or a narrow window
**When** the chart is shown
**Then** bars and axes are hidden from screen readers and the text alternative carries the meaning; below 640 px the axis uses short labels and below 400 px the end labels are hidden (UX-DR25)
**And** the whole card is complete without JavaScript (AD-18), and *Not enough data* shows no chart card (FR-10).

### Story 3.2: Exploring the chart

As a user,
I want to point at or step through the bars and highlight what did as well as this Wallet,
So that I can explore the evidence by mouse or keyboard.

**Acceptance Criteria:**

**Given** `web/static/js/chart.js`
**When** the user points at a bar
**Then** the tooltip shows the bar's range and number of replays, stays while the pointer moves onto it and for 300 ms after it leaves, hides on Esc, and never covers the marker's dot or label (UX-DR26, WCAG 1.4.13).

**Given** the keyboard
**When** the user focuses the bars
**Then** they are one slider named "Replays by result": Left/Right step one bar, Page Up/Down ten, Home/End jump to the ends, and each step is read ("$30,000 to $35,000: 289 replays") (UX-DR26).

**Given** the Wallet marker button
**When** it is pointed at, focused or clicked
**Then** the tail bars light up and the tail label shows the exact count of Simulations at or above the Real PnL, the same count the p-value uses and never summed from the bars, with the edge sentences "No replay did this well or better" and "All 10,000 replays did this well or better"; click or Enter pins it and announces "Highlight on", a second click, Esc or moving the slider unpins it and announces "Highlight off" (UX-DR27).

**Given** the chart scrolls into view the first time
**When** motion is allowed
**Then** the bars grow into the curve and the marker drops in, under a second in all, once per view; with reduced motion nothing moves and the chart is shown complete (UX-DR28, UX-DR11). This animation is the first thing to slip.

### Story 3.3: The honesty notes

As a user,
I want to see what the test cannot see, next to the Verdict,
So that I know how far to trust it.

**Acceptance Criteria:**

**Given** any Verdict, including *Not enough data*
**When** the Verdict page renders
**Then** the card "What this test can't see" is always shown and never collapsed, with three columns: the share of the Real PnL from the largest bet ("70% of the Real PnL came from the single largest bet.", or the amount when the Real PnL is $0 or below, or the over-100% sentence); "N of M positions held to resolution" with the Exit PnL; the fixed limits note and "This is not financial advice." (FR-11, UX-DR29, UX-DR14)
**And** under them the "Left out of the test" line with a count per reason, the fees not counted with their recorded total, and, when they apply, the over-10% sentence, the linked-bets note over 20%, and the window line ("Based on the latest 2,000 bets; older results are not included."; "first 2,000" for an after part; no total N, because the window stops reading at 2,000: Edvard, 2026-11-24)
**And** last, "Computed on … · Seed 44" with the result's own scope and Seed (FR-11, AD-22)
**And** the Verdict page keeps its fixed order: Verdict card, (Explanation in stage 3), chart card, honesty notes card, (Domain table in stage 3) (UX-DR19).

**Given** Exit PnL below zero
**When** the Verdict card renders
**Then** the warning box beside the stats reads "Positions this Wallet sold before resolution lost money in total. This Verdict covers only bets held to resolution.", read by screen readers with a hidden "Warning:" (FR-11, UX-DR15, UX-DR20)
**And** the stop-loss Synthetic Wallet shows the warning, and a Wallet with Exit PnL ≥ 0 or no early sales shows none (FR-11 check).

**Given** the honesty notes
**When** they are tested
**Then** every number comes from the one Position builder's record (AD-11) and every phrase from `core/phrases` (AD-25). This story never slips.

**Settled at spec time (Edvard, 2026-11-24):** "N of M held to resolution" counts the bets whose history was read in full (M) and those of them not sold before resolution or kept only as a Sliver (N); the Exit PnL sums the tested bets, Slivers and bets sold before resolution; About's JavaScript-only paragraph explains why the tail label's count and the odds differ (the +1, Story 3.2's note). Reasons in the PRD decision log.

### Story 3.4: Theme, copy and finish

As a user,
I want the page to feel calm and finished, in light or dark,
So that it is pleasant to use and works on any screen.

**Acceptance Criteria:**

The theme and its toggle (UX-DR2) were built in Story 1.7 (Edvard, 2026-11-20); this story keeps only the hover and focus states of the toggle.

**Given** the address card's copy button (`copy-address.js`)
**When** the user copies
**Then** it shows "Copied" for 2 seconds and announces "Address copied"; on failure it shows and announces "Copy failed. Select the address and press Ctrl+C." (⌘C on a Mac) and selects the address (UX-DR21).

**Given** any clickable element
**When** it is hovered or focused
**Then** only clickable things react, hover and focus look the same plus the focus ring, transitions take 120 ms, and buttons lift 1 px; with reduced motion nothing moves (UX-DR9, UX-DR11)
**And** the layouts follow the three breakpoints, two-column parts stack below 900 px, and anything that slipped from Story 1.7 is done here (UX-DR10).

**Settled at spec time (Edvard, 2026-11-24):** JavaScript gets browser tests (Playwright for Python, AD-17) driving the installed Chrome or Edge: the copy button, no sideways scroll at 320, 360, 600 and 900 px, no lift with reduced motion. On GitHub they must run and fail if they cannot (his addition); on a computer without Chrome or Edge they skip with a reason.

### Story 3.5: Accessibility check, and stage 1 done

As the examiner,
I want proof that the app works for keyboard and screen-reader users and that stage 1 is complete,
So that I can trust both the claims and the build.

**Acceptance Criteria:**

**Given** the stage 1 pages
**When** the automated checks run
**Then** tests confirm one main heading per page and headings in order, a label tied to every field, errors tied to their fields, `lang="en"`, the skip link first, the Verdict read as "Verdict: …", forced-colours rules present, and no page needing JavaScript (UX-DR8, UX-DR12, UX-DR13, NFR-9).

**Given** the short checklist below
**When** the browser tests walk it with the keyboard only and read what the browser hands a screen reader (each element's role, name and state, the reading order, and the text of the live regions), in Chrome or Edge
**Then** `docs/accessibility-check.md` is committed with the checklist, the test that checks each item, and what it actually found, pass or fail with what happened, including anything that failed, not just a line saying it passed
**And** each failure is either fixed (and re-checked) or listed with the reason it stays
**And** the document says what these tests cannot prove: the words NVDA itself speaks and its browse mode are not checked, since no screen reader runs in the tests.

(Edvard, 2026-11-24, at Story 3.5: replaces his own NVDA and keyboard walk-through, his call of 2026-10-24, with browser tests. Kept from that call: the checklist, and that what was found, failures included, is committed.)

Checklist:
1. First Tab stop is "Skip to content"; Enter jumps to the main content. On the Lookup page the focus starts in the address field (UX-DR16), so there the skip link is the first stop before the field, reached by Shift+Tab (Edvard, 2026-11-25).
2. Lookup: the field is read as "Wallet address"; an empty submit is read as "Error: Enter a wallet address." and focus stays in the field.
3. Verdict page: jumping by heading (H) reaches the main heading, read as "Verdict: …"; the dots are silent.
4. The odds phrase, stats and the chart's text alternative are read as plain text.
5. Chart slider "Replays by result": arrows, Page Up/Down and Home/End move and each step is read.
6. Wallet marker: its sentence is read; Enter says "Highlight on", Esc says "Highlight off".
7. Copy button: "Address copied" is announced.
8. The Exit PnL warning is read with "Warning:" first (stop-loss Synthetic Wallet).
9. "What this test can't see" is reachable by heading and read in order.
10. Theme toggle is read as "Dark theme, toggle button" with its pressed state.
11. Keyboard only: every action works, the focus ring is always visible, nothing traps focus.
12. At 200% zoom and in a 320 px wide window there is no sideways page scrolling.

**Also (Edvard, 2026-11-24, from Story 3.4):** the browser tests from Story 3.4 gain `chart.js` (tooltip, slider keys, marker pin and unpin, Esc, build-up, enhancing after the swap; the 45 checks Story 3.2 ran once in a throwaway script) and `progress.js` (polling, swapping in the result, focus on the new heading, giving up, and the copy button working on the swapped-in Verdict), plus a forced-colours run (Windows High Contrast) of the copy button's copied, hover and focus states.

**Built in two parts (Edvard, 2026-11-24):** part A is the browser tests for the scripts in the note above; part B is the accessibility checks and checklist above and closing stage 1 below. Story 3.5 is done only when part B is.

**Given** the end of stage 1
**When** it is closed
**Then** all tests pass in CI on the three systems, the README covers every stage 1 feature, the three commands, how keys are set in `.env`, and each JavaScript file and what it does (NFR-1, PRD §8), and SM-1 and SM-2 are checked and noted (NFR-12).

## Epic 4: Scan for skilled Wallets

The user chooses a Cut-off Date, runs a Scan that can be left, interrupted and resumed, and sees the Watchlist with the Minimum Luck Passes and the population tested. If the epic runs late, the favicon progress ring and the tab-title counter slip first; the funnel's leak rules (Story 4.2) and Resume (Story 4.3) never slip (Edvard, 2026-10-24).

### Story 4.1: Before and after the Cut-off Date

As a user,
I want a Wallet's bets split cleanly at the Cut-off Date,
So that the before part judges skill and the after part checks it, with no bet on the wrong side.

**Acceptance Criteria:**

**Given** a Cut-off Date
**When** it is converted
**Then** it means 00:00 UTC on that date, converted in one place (AD-7).

**Given** `positions_near(wallet, cutoff, side="before", limit=2000)`
**When** it runs
**Then** the before part is the latest 2,000 Positions whose Market resolved before the cut-off and whose Positions were all first entered before it (Edvard, 2026-11-25: no bet made after the date), by Gamma resolution time, fetched by the AD-7 rule (OPEN in full, CLOSED newest-first with the stop rule) (AD-8).

**Given** `positions_near(wallet, cutoff, side="after", limit=2000)`
**When** it runs
**Then** the after part is the first 2,000 Positions, by the positions list's `first_entry_at`, in Markets resolved on or after the cut-off whose Positions were all first entered on or after it; their activity is read oldest-first from the cut-off (AD-7, AD-8; Edvard, 2026-11-25, Story 4.1 review: first entry, not first buy, so Markets entered by a split or conversion are counted)
**And** a Position bought before the date and resolved after it is in neither part (Glossary, Cut-off Date).

**Given** fixtures cut from the real capture
**When** the tests run
**Then** tokens that look new in a capped activity read but have an earlier `first_entry_at` are kept out of the after part, as found in the capture (165, 46 and 20 on three Wallets)
**And** the same exclusion rules apply on both sides (AD-11).

### Story 4.2: The Scan funnel

As a user,
I want the Scan to pick Wallets using only what happened before the Cut-off Date,
So that the Hold-up Test is not rigged by results it is meant to check.

**Acceptance Criteria:**

**Given** a new Scan with a Cut-off Date and size N
**When** the Market set is chosen
**Then** it is the Markets resolved in the 90 days before the cut-off, the top 100 by volume `[ASSUMPTION]`, chosen without looking at outcomes and stored with the Scan (AD-21, FR-16).

**Given** each Market in the set
**When** its candidates are read
**Then** they are the union of `/v2/positions?condition=…` with `status=CLOSED` and `status=OPEN`, and the Market-anchored client function takes no sort argument and always sends `sort_by=TIMESTAMP&sort_direction=ASC`; a test fails if a Market-anchored request is built otherwise (AD-9)
**And** a read that hits `MARKET_ROW_CAP` `[ASSUMPTION]` or times out after the retries contributes no candidates and is stored as "not used: partial" (AD-9).

**Given** a candidate refused as a protocol contract address
**When** it is met
**Then** it is dropped from the candidates and counted in the Scan record, not flagged "not fully read" (AD-9, P-1).

**Given** the candidates
**When** the shortlist and ranking run
**Then** the shortlist is 3 × N `[ASSUMPTION]` by the pre-filter Σ CLOSED `realized_pnl` + Σ OPEN (resolved value − cost) on their Market-anchored rows, so unredeemed losers count (AD-21)
**And** each shortlisted Wallet's before part is fetched in full and ranked by Real PnL from the AD-10 sources; the top N are kept (FR-16)
**And** a test proves that changing outcomes after the cut-off cannot change which Wallets are scanned (FR-16, FR-17)
**And** a Wallet whose read is refused or capped is kept and flagged "not fully read" everywhere it is counted (AD-9).

### Story 4.3: The Scan as a resumable job

As a user,
I want a long Scan to run in the background and survive closing the app or an outage,
So that I never lose an hour of work.

**Acceptance Criteria:**

**Given** a started Scan
**When** it runs
**Then** it is a `job` with the phases ranking, Skill Tests, Hold-up Test and Copy Test (the last two arrive in Epics 5 and 6); the progress JSON carries `phase`, and a Scan is finished only when every phase is done (AD-5)
**And** between any two units of work (one Market with both its lists, one Wallet fetch, one price request) the worker runs any waiting lookup first (AD-5; a whole Market, not one list page: Edvard, 2026-11-26).

**Given** a Scan
**When** its Wallets are fetched
**Then** it stores the `fetch_id` used for each Wallet and an as-of time, and resume and later phases read only those snapshots (AD-19)
**And** it stores the results `scan_whole` (the Watchlist) and `scan_before` (the Passers) with `scan_id`, cut-off, Seed and `fetch_id` (AD-22).

**Given** the app closed mid-Scan, or Polymarket not answering after the 3 tries
**When** the Scan stops
**Then** it is `interrupted` or `stopped`, and Resume continues without fetching finished Wallets again (FR-16, AD-5, AD-3)
**And** an unexpected error makes it `failed` (logged, no Resume), and a Scan whose snapshots were rebuilt shows "Data rebuilt, cannot resume" (AD-6)
**And** the Scan's tables are added to `schema.sql` with a raised `user_version`; on a version mismatch the cache tables are rebuilt while Scans, Watchlists, results and every snapshot they refer to are migrated and kept (AD-6)
**And** a Scan with a different Cut-off Date is a new Scan; Market records are never fetched twice, and a Wallet's before or after part is reused for the same Cut-off Date and side when under 24 hours old, and fetched again at another date (FR-16, AD-4; Edvard, 2026-11-26).

### Story 4.4: The Scans page

As a user,
I want to start a Scan, watch it, and come back to earlier ones,
So that I can run Scans without guessing what is going on.

**Acceptance Criteria:**

**Given** the Scans page (top bar link *Scan wallets*, now shown)
**When** it opens
**Then** it shows the New Scan form (Cut-off Date, Number of Wallets default 200, "Start Scan") and the Scan list, or "No Scans yet. A Scan checks the top Wallets by profit made before a date you choose." (UX-DR30, UX-DR4).

**Given** the form
**When** it is submitted
**Then** a missing date shows "Choose a Cut-off Date.", a date today or later "The Cut-off Date must be in the past.", a number outside 10 to 500 "Enter a whole number from 10 to 500.", and nothing starts (UX-DR30, UX-DR13)
**And** a Cut-off Date less than 90 days ago shows the warning "Very few bets were resolved after this date, so the Hold-up Test and Copy Test may have too little to test." and the user can still start (Edvard, 2026-10-24)
**And** under the Number of Wallets a rough time estimate updates with the number, computed from the planned request count (Market reads, the 3 × N shortlist and the N after parts at the typical requests per Wallet part) at the set pace, labelled rough, and recalibrated once a real Scan has run (Edvard, 2026-10-24); Copy Sample prices are added by Epic 6 with the Copy Test phase, since the estimate counts only what a Scan does today (Edvard, 2026-11-26, Story 4.4).

**Given** Offline Mode or a running Scan
**When** the form shows
**Then** in Offline Mode the date is fixed to 1 July 2025 and the number to the whole Sample Dataset, read-only, with an info box saying so (from Story 4.6, "Start Scan" there starts a Scan of the whole Sample Dataset with that date; before it, "Start Scan" was unavailable with "Offline Scans are not ready yet."); while a Scan runs, an info box says "A Scan is running (84 of 200). You can start a new one when it finishes." and "Start Scan" is unavailable but focusable (UX-DR30).

**Given** the Scan list
**When** Scans exist
**Then** it shows run date, Cut-off Date, Wallets, Watchlist size and status text, a "Resume Scan (Cut-off Date …)" button for interrupted and stopped Scans, and no results of an unfinished Scan (UX-DR31)
**And** while a Scan runs, the progress bar is read as "84 of 200 Wallets checked" and names the current step, announcements come at most every 10% and at the end, and the tab title shows progress (UX-DR32). The favicon ring slipped to deferred work (Edvard, 2026-11-26: Epic 4 ran past its target, and the plan let the ring slip first).

### Story 4.5: The Watchlist

As a user,
I want to see which scanned Wallets passed, sorted by the strength of the evidence,
So that I know which ones to look at more closely, and how many would pass by luck alone.

**Acceptance Criteria:**

**Given** a finished Scan
**When** its Watchlist opens
**Then** the Scan header shows the eyebrow "WALLET SCAN", "Scan of N Wallets", the Cut-off Date and run date, the population line ("Markets resolved in the 90 days before the Cut-off Date, top 100 by volume · 97 of 100 Markets used · Seed 44"), the shortlist line ("Shortlist of about 600 by a quick profit estimate · 4 Wallets not fully read"; (Edvard, 2026-11-26, Story 4.5)), the summary card, and a disclosure listing Markets "not used: partial" by short condition ID, volume and resolution date (UX-DR33, AD-21)
**And** the Scan tabs are links in a navigation region named "Scan", with the current page marked; the Hold-up Test and Copy Test tabs appear when Epics 5 and 6 add them (UX-DR33).

**Given** the Watchlist table "Wallets rated Skilled (high confidence)"
**When** it renders
**Then** it has the columns Wallet (an in-app link named "Open Verdict for Wallet …"), Verdict pill, Odds, Resolved bets, Real PnL, no rank column, the caption on the sort by p-value, and the "Not fully read" tag where it applies (FR-16, UX-DR34)
**And** above it an info box shows the Minimum Luck Passes sentence from `core/phrases` ("At least about 2 of the 200 Wallets with a Verdict would pass by luck alone, probably more, because these Wallets were picked for high profit.", a whole number, and below 100 Wallets the rate instead: "About 1 in 100 Wallets would pass by luck alone, probably more, because these Wallets were picked for high profit. With only 37 Wallets with a Verdict, even one passing could be luck." (Edvard asked for small numbers to read the way a person says them; the AI chose the wording, 2026-11-26); only Wallets that got a Verdict count (Edvard, 2026-11-26, Story 4.5); left out when none did (Edvard, 2026-11-26, Story 4.5 review)) (FR-16, AD-25)
**And** an empty Watchlist says "No Wallet in this Scan was rated *Skilled (high confidence)*." as a valid result (SM-C2)
**And** the Watchlist is stored in the database with its Scan date and Cut-off Date and is never sent anywhere (FR-16).

**Given** a Wallet opened from the Watchlist
**When** its Verdict page opens
**Then** it shows that Scan's `scan_whole` result, recomputed from its frozen snapshots so it equals the Watchlist row, with "← Back to Watchlist (Cut-off Date …)" (UX-DR37, AD-22)
**And** a Wallet whose Watchlist row is flagged shows the info tag "Not fully read" with its tooltip beside the stats, and when its after part could not be read the window line is "Based on the latest 2,000 bets resolved before the Cut-off Date; the bets bought after it could not be read." (no line when nothing was read) (Edvard, 2026-11-26, Story 4.5 review)
**And** otherwise its honesty notes always show "Based on two windows around the Cut-off Date: up to the latest 2,000 bets resolved before it and up to the first 2,000 bought after it. Bets bought before the date and resolved after it are in neither." and "Computed on 1,234 bets around the Cut-off Date 1 July 2025 · Seed 44" (FR-11, AD-8; (Edvard, 2026-11-26, Story 4.5)).

### Story 4.6: Offline Scan with Synthetic Wallets

As the examiner,
I want an offline Scan of the Sample Dataset to find the Synthetic Wallets it should,
So that I can check the Scan without the network.

**Acceptance Criteria:**

**Given** the generator
**When** it runs
**Then** it also makes the stage 2 types steady sharp (100 at 0.50 winning 70 before the cut-off, the same after), forecaster (buys at 0.50, wins 70%, price drifts slowly towards the outcome over hours) and speed trader (buys at 0.50 seconds before the price jumps to the outcome), with their price paths (FR-13)
**And** the Wallets FR-16 expects on the offline Watchlist hold one small, fully sold Position in each of a fixed set of synthetic anchor Markets with high volume inside the default funnel window, so the normal funnel finds them while the exclusion rules keep those Positions out of every Skill Test; there is no offline branch (AD-14)
**And** the 1,000 coin-flippers hold the same anchor Positions, so the offline Scan also tests Wallets with no skill and shows some passing by luck (Edvard, 2026-11-27, Story 4.6).

**Given** Offline Mode and the default Cut-off Date 1 July 2025
**When** a Scan of the Sample Dataset runs
**Then** at least the sharp trader, steady sharp, forecaster and speed trader are on the Watchlist (FR-16)
**And** the round-trip test is extended to the offline Scan (AD-14).

### Story 4.7: The real Wallets around the Cut-off Date

Split out of Story 4.6 while planning it (Edvard, 2026-11-27): rebuilding the real Wallets' data is a separate job from the offline Scan, and Story 5.2 needs it, so it comes right after 4.6 and before Epic 5.

As the examiner,
I want the real Sample Wallets' bets before and after the default Cut-off Date in the Sample Dataset,
So that the offline Scan and Hold-up Test can use real Wallets without the network.

**Acceptance Criteria:**

**Given** the capture zip
**When** the build-sample script runs
**Then** the build-sample script from Story 2.6 is extended to write the real Wallets' before and after windows around 1 July 2025 with Story 4.1's rules, and re-run on the capture zip (AD-14).

**Given** Offline Mode and the default Cut-off Date
**When** a Scan of the Sample Dataset runs
**Then** it finds the 8 real Wallets in the Scan through the capture's own funnel list and their holder rows as Polymarket listed them, and the build stops if any of those rows could hold information from after the Cut-off Date (AD-14, AD-21).

Open items, decided while planning (Edvard, 2026-11-27, the AI's recommendations): 0xd218e4 and 0x63d43b, whose capture holds activity only from May 2025, stay lookup-only and outside the offline Scan (their before part would read as wholly "not fully read", and both windows would add an estimated 60 to 130 MB); the other 8 are in it. The offline Scan finds them through the capture's funnel list (Gamma volumes) with the holder rows copied as Polymarket listed them; Edvard added the check that nothing in those rows comes from after the Cut-off Date. The 50 MB limit stays.

## Epic 5: Does the skill last? Hold-up Test

The user compares the Before-Cut-off Passers with the Comparison Group on the bets after the Cut-off Date. Stories 5.1 and 5.2 close the stage 2 minimum (PRD §6.1; Edvard, 2026-11-18) and never slip; if they run late, Epic 6 starts later and stage 3 shrinks (Edvard, 2026-10-24). Story 5.3, a live Hold-up run, is beyond the minimum.

### Story 5.1: The two groups and their test

As a user,
I want the Wallets that passed before the Cut-off Date tested again on their later bets, next to a fair comparison group,
So that I can see whether their skill lasted or was a lucky streak.

**Acceptance Criteria:**

**Given** a finished Scan's `scan_before` results
**When** the groups are formed
**Then** the Before-Cut-off Passers are the Wallets rated *Skilled (high confidence)* on the before part, the Comparison Group those rated *Likely skilled* or *No evidence of skill*, Wallets with *Not enough data* are in neither, and no Wallet is in both (FR-17)
**And** no Position from after the Cut-off Date decides who is in either group, and a Wallet that passes only when after Positions are included is not a Passer (FR-17; tested by changing after-part outcomes).

**Given** each group
**When** its after part is tested
**Then** a Wallet counts only with at least the Minimum After-bets (10 `[ASSUMPTION]`) tested Positions in its after part (first 2,000), by the same rule in both groups, and each result shows Wallets in the group, Wallets dropped for too few after bets, Resolved Positions counted, and Wallets "not fully read" (FR-17, AD-11)
**And** the pooled after part is simulated with one draw per Market shared across all the group's Wallets, the test itself being the random unit (AD-20, AD-15)
**And** a group with fewer than 30 Resolved Positions after the cut-off shows *Not enough data*, and results are stored as `holdup_after` with `scan_id`, cut-off and Seed (FR-17, AD-22).

**Given** the share of Wallets dropped in each group
**When** they differ by more than 20 percentage points `[ASSUMPTION]`
**Then** the result carries the FR-17 message flag; a planted example with 60% and 10% dropped sets it, and equal shares do not (FR-17).

**Given** the generator
**When** it runs
**Then** it also makes a separate lucky-streak group from the coin-flipper rules, with bets on both sides of the default Cut-off Date and fair odds after it, so Epic 1's coin-flippers and their golden result stay unchanged (FR-13)
**And** the steady-sharp Synthetic Wallets are rated *Skilled (high confidence)* on their after part, and the lucky-streak Wallets that passed before are rated *No evidence of skill* on theirs (FR-17).

**Given** 1,000 planted runs in which 7 coin-flipper Passers hold the same side of the same 40 Markets
**When** the Hold-up Test runs on each
**Then** p < 0.05 in at most 7% of them (FR-17, AD-20)
**And** this check is marked `slow`: in full on Linux 3.14, 100 runs elsewhere, with the determinism checks unchanged on every job (AD-17).

Open items, decided while planning (Edvard, 2026-11-27): the lucky-streak group is 1,000 Wallets for the checks only, built by the generator in the tests and not loaded into the Sample Dataset or the offline Scan (the AI's recommendation; in the Scan they would drown the real Wallets in the Comparison Group). They are not written to disk either: Edvard dropped the files after the review, because they came to about 200 MB that nothing reads. The coin-flippers already in the offline Scan have no bets after the Cut-off Date, so all 1,000 are dropped and the dropped-share flag is set offline; Edvard decided the warning is right and stays, and Story 5.2 explains it. A group's "not fully read" count covers every Wallet in the group whose before or after part was not fully read; the Hold-up result is stored when the Scan finishes, so a Scan finished earlier has none (the AI's choices, shown at the spec checkpoint).

### Story 5.2: The Hold-up Test page

As a user,
I want the two groups side by side with what was counted and dropped,
So that I can judge the comparison myself.

**Acceptance Criteria:**

**Given** a finished Scan
**When** the user opens the *Hold-up Test* tab (now shown in the Scan tabs)
**Then** two group cards, *Before-Cut-off Passers* and *Comparison Group*, each show the Verdict pill on the after part, the odds phrase, resolved bets counted, Real PnL, Wallets in the group, Wallets dropped for too few bets after the Cut-off Date, and Wallets not fully read (FR-17, UX-DR35)
**And** under the cards: "Each Wallet's bets after the Cut-off Date are capped at its first 2,000. Bets in the same Market are simulated together, not as separate evidence."; and the Seed (FR-11, FR-17).

**Given** the dropped-share flag
**When** it is set
**Then** a warning box above both cards reads "More Wallets were dropped in one group than in the other. Wallets that stop betting may be the ones that lost, so the group with more dropped Wallets may look better than it is." (FR-17).

**Given** the edge cases
**When** they occur
**Then** no Passers shows "No Wallet passed on its bets before the Cut-off Date, so the Hold-up Test and Copy Test have nothing to test."; an empty Comparison Group card says "No Wallets in this group: every scanned Wallet passed or had *Not enough data* before the Cut-off Date."; a group too small shows *Not enough data* with its count (UX-DR35)
**And** the page title is "Hold-up Test · {Cut-off Date} · LiquidOracle" and the page works without JavaScript (UX-DR8, AD-18).

**Given** an offline Scan of the Sample Dataset with the default Cut-off Date
**When** this story is done
**Then** the Hold-up result that covers the 8 real Sample Wallets in the offline Scan is written into the README whichever way it comes out, with its limits: only 8 Wallets (0xd218e4 and 0x63d43b stay outside the Scan, Story 4.7), picked for the Sample Dataset, not a full Scan (PRD §6.1; Edvard, 2026-11-18)
**And** its limits also say what Story 5.1 measured: no real Wallet is among the Passers (none passed before the date; the Passers that are tested are made-up Wallets), and the Comparison Group's result rests on 3 real Wallets, 307 of its 409 bets from one of them (NFR-13; Story 5.1 review, 2026-11-27)
**And** it says why the dropped-share warning shows on the offline Scan, so it does not look like a bug: the 1,000 coin-flippers have no bets after the Cut-off Date, so nearly the whole Comparison Group is dropped (70% of the Passers against nearly all of the Comparison Group); the rule is not changed to hide it (Edvard, 2026-11-27, Story 5.1)
**And** the stage 2 minimum is closed: all tests pass in CI on the three systems and the README covers the Scan and the Hold-up Test (PRD §6.1, NFR-12).

Open items, decided while planning (Edvard, 2026-11-27): the reason for the offline warning is said in the README and on the page, in an info box under the warning that shows only in Offline Mode (the AI's recommendation; rejected: the README only). Edvard added that the box must also say the Passers tested offline are made-up Wallets, so the card does not read as a real skilled trader found, and, at approval, that a test must fail if "no real Wallet passed before the Cut-off Date" stops being true. A Scan with no Passers shows the sentence in the Passers card and still shows the Comparison Group's result (the AI's recommendation; rejected: the sentence alone). The AI's choices, which he accepted: five figures per card as this story lists them (DESIGN.md said four and is corrected), the cards reuse the Verdict card's odds sentence, and the limit that Wallets on opposite sides of one Market each keep their own price as win chance goes into the README, not onto the page. The page's address is `/scans/<id>/hold-up`; a Scan finished before Story 5.1 has no stored result, so it gets no tab (Story 5.1). After the review: each sentence of the offline box is left out when it would describe nothing (no Passer tested; the warning set because the Passers were dropped more), and the figures go to one column wherever two would be too narrow for a nine-digit amount (the AI's choices, shown to Edvard). A reviewer missed a word on who is in each group; Edvard had a line added under each card's title (2026-11-27, the AI's recommendation): "Wallets rated *Skilled (high confidence)* on their bets before the Cut-off Date." and "Wallets rated *Likely skilled* or *No evidence of skill* on their bets before the Cut-off Date."

### Story 5.3: Hold-up Test on a live Scan

Beyond the stage 2 minimum (PRD §6.1): done only if time allows. Moved out of Story 6.6 on 2026-11-18 so a real-data Hold-up result does not depend on the Copy Test, which needs price history.

As the examiner,
I want to see what the Hold-up Test says on a full Scan of real Wallets, whatever it is,
So that I can judge the method on reality, not only on made-up Wallets and the 10 Sample Wallets.

**Acceptance Criteria:**

**Given** the app online
**When** a real Scan with the default Cut-off Date runs
**Then** its Hold-up Test result, the Scan size, Markets used and Wallets not fully read are written into the README and the reflection notes, whichever way they come out (SM-5 for the Hold-up Test, NFR-13, SM-C2)
**And** the Scan is kept, so Story 6.6 can run the Copy Test on the same Scan.

**Given** the 1 December hard stop
**When** this story runs after it
**Then** that is allowed, because it runs the app and writes up results and adds no new code (same rule as Story 6.6).

Open items, decided while planning (Edvard, 2026-11-27, the AI's recommendations): the Scan that counts is 200 Wallets, the app's default, with Cut-off Date 1 July 2025 and Seed 44 (rejected: 50, where the Passers may end at *Not enough data*, and 500). No live Scan had been run before this story, so a trial Scan of 10 Wallets runs first, to find live-only faults while a fix is still allowed and to measure the time and disk use; its result is reported in the README in one line (NFR-13), and the 200-Wallet Scan was named as the result before either ran, so the result cannot be picked afterwards (rejected: straight to the big Scan). The AI runs the trial; Edvard starts the 200-Wallet Scan in his own terminal, so it does not depend on a chat session. No other Seed, date or size is run to get a nicer result. If the app fails on live data, the fix is its own small change with a test, not part of this story. The finished database is copied outside the repository with a SHA-256 file, so Story 6.6 can use the same Scan.

How it went (2026-11-27, written up 2026-11-28): the trial Scan of 10 Wallets took 2 hours 20 minutes against the app's estimate of about 10 minutes, and was stopped once by Polymarket (three 503 answers after 39 minutes on one very large Wallet, 0xd218e4) and resumed. After it Edvard chose, of three ways to handle stops in the long Scan, a small script outside the repository that presses *Resume Scan* (rejected: pressing by hand overnight, and changing the app to retry by itself, which would be new code). The 200-Wallet Scan then ran from 19:24 to 22:08 in one run, with no stop, and reused the trial's 39 stored Wallet parts. Result as the app shows it: Before-Cut-off Passers *Skilled (high confidence)*, fewer than 1 time in 10,000, on 4,161 bets (9 Wallets, 2 dropped, 1 not fully read); Comparison Group *No evidence of skill*, about 1 time in 20 (p = 0.0503), on 26,431 bets (62 Wallets, 10 dropped, 3 not fully read); 77 of 100 Markets used, 7 of the 200 Wallets not fully read, 10 Wallets on the Watchlist. It is in the README under *The Hold-up Test on a live Scan*, with what it can and cannot tell. No code changed. The database copy for Story 6.6 is `live-scan-200-cutoff-2025-07-01.db` in the data folder outside the repository, with its SHA-256 file. Found on live data and not fixed here (listed in `.logs/edvard-tokle/issues.md`): the time estimate was wrong both ways (about 10 minutes for the trial that took 2 hours 20 minutes, then about 25 hours for the Scan that took 2 hours 44 minutes), and a 503 in the middle of a very large Wallet throws away that Wallet's work. Three reviewers read the write-up (26 findings, none of a wrong number in the result table); the README now also says how little profit many of the 200 had, that the largest Wallets could not be read in full, and that the Comparison Group's label could flip with another Seed.

## Epic 6: Could a late follower have profited? Copy Test

The user sees Follower PnL and Follower Return at 1, 5 and 30 minutes and the Random Group Check; a Copy Test on real data is run and reported (SM-5). Stage 2 is done. Beyond the stage 2 minimum (PRD §6.1). If the epic runs late, Story 6.4's table polish slips first; Story 6.6 may run after 1 December, because it is running the app and writing up, not new code; the checks in Stories 6.2 and 6.3 are never cut (Edvard, 2026-10-24). The old price route is checked daily by a scheduled workflow, and a 50-Wallet insurance pool was captured in advance (spine AD-24, PRD FR-18c).

### Story 6.1: Price history

As a user,
I want the app to find the market price a few minutes after each of a Wallet's buys,
So that the Copy Test can price what a late follower would have paid.

**Acceptance Criteria:**

**Given** one client function for price history (AD-24)
**When** it is asked for a token and window
**Then** it uses the old CLOB `/prices-history` route at `fidelity=1` while that route answers with one-minute points, else `/v2/prices-history` with `bucket_seconds=60` sent explicitly, and never silently returns a coarser grain (FR-18c)
**And** windows of one token are packed into requests of at most 14 days, only the points inside the short windows [t − 2 min, t + 32 min] are stored, and stored windows never expire (AD-14, AD-4).

**Given** `price_at(points, t)` (pure, in `core`)
**When** a Copy Delay is priced
**Then** it returns the last point at or before t that is at most 2 minutes old, the same rule live and offline (AD-24)
**And** a buy with no such point is left out of that Copy Delay and counted (FR-18a, FR-18c).

**Given** the daily route-check workflow
**When** this story is done
**Then** its classes and the client's one-minute test agree (the same 40-point and 90-second rule), so a "coarse" or "gone" alert means the client would also stop using the old route.

### Story 6.2: Follower PnL

As a user,
I want to see what a follower copying each of a Passer's buys 1, 5 or 30 minutes late would have made, after fees,
So that I can tell forecasters from speed traders.

**Acceptance Criteria:**

**Given** a Wallet's after part
**When** its Copy Sample is drawn
**Then** it is all Resolved Positions if at most 100 `[ASSUMPTION]`, otherwise 100 drawn with the Seed by one rule for every Wallet; the same Seed gives the same sample, and a Wallet with 250 after Positions shows "priced 100 of 250" (FR-18a, AD-15).

**Given** each buy fill of a Copy Sample Position
**When** it is copied at its own time plus the Copy Delay
**Then** Follower PnL = Σ (s · (o − p_delay) − Follower Fee), where s is that fill's share of the shares held at resolution and p_delay is `price_at` plus the Spread Allowance of half a cent (capped at 1); the Follower Fee is s · rate · p · (1 − p) from the Market's fee schedule, 0 where none; Follower Return = Follower PnL ÷ Σ (s · p_delay + Follower Fee) (Glossary, FR-18a).

**Given** the Synthetic Wallets from Epic 4
**When** they are copied
**Then** the speed trader has Follower PnL ≤ 0 at 5 minutes and the forecaster Follower PnL > 0 at 30 minutes (FR-18a).

**Given** a hand-made set of three Positions in a Market with a fee, including a Position bought in more than one fill
**When** a fresh AI helper works out its Follower PnL and Follower Return step by step, given only the PRD and the set's data and never the app's code, including the Spread Allowance (same rule as FR-4: its calculation is committed before the test compares it)
**Then** the app's numbers equal the helper's to the cent, and the test file says the reference values are the helper's calculation (FR-18a; Edvard, 2026-11-23, replacing his own hand calculation planned on 2026-10-24).

### Story 6.3: The Random Group Check

As a user,
I want the Passers' copy result compared with random groups of Wallets from the same Scan,
So that I know whether following them beat picking at random, or was luck.

**Acceptance Criteria:**

**Given** a Scan's Copy Pool (every Wallet with at least the Minimum After-bets priced at the Main Copy Delay, Passers included)
**When** the Random Group Check runs at 5 minutes
**Then** the Passers' score is their average Follower Return, each Wallet counting equally; 10,000 random groups of the same size are drawn from the Pool with no Wallet twice in one group; Copy p-value = (1 + groups scoring ≥ the Passers) / 10,001; Copy Verdict *Beat random picks* below 0.05, else *No better than random picks* (FR-18b)
**And** *Not enough data* when no Passer is in the Pool or fewer than 1,000 `[ASSUMPTION]` different groups can be drawn; a Pool of 6 with 3 Passers (20 groups) shows it (FR-18b)
**And** the same data and Seed give the identical Copy p-value, and only the Main Copy Delay gives a Copy Verdict (FR-18b, AD-15).

**Given** the planted checks
**When** they run
**Then** a Scan of 10 forecaster Passers and 100 coin-flippers gets a Copy p-value < 0.01, and across 1,000 planted Scans of 110 coin-flippers with 10 picked at random as Passers the Copy p-value is < 0.05 in at most 7% (FR-18b)
**And** the shared-Markets gate holds: across 1,000 planted Scans where 10 coin-flipper Passers hold the same side of the same 40 Markets, the Copy p-value is < 0.05 in at most 7%; if it fails, no Copy Verdict is shown and the Random Group Check goes back to the plan (FR-18b, AD-20)
**And** both 1,000-run checks are marked `slow`: in full on Linux 3.14, 100 runs elsewhere, determinism checks unchanged on every job (AD-17).

### Story 6.4: The Copy Test page

As a user,
I want the luck-checked result first and the per-Wallet numbers clearly marked as not luck-checked,
So that I do not mistake a single lucky Wallet for evidence.

**Acceptance Criteria:**

**Given** a finished Scan
**When** the user opens the *Copy Test* tab (now shown in the Scan tabs)
**Then** the top shows the Random Group Check at 5 minutes: the Copy Verdict pill (no dots) and "random groups did as well in X% of draws" (one decimal under 10%), or "no random group did as well in 10,000 draws" when none did, never a percentage (FR-18b, UX-DR36, AD-25)
**And** under it "N of the Passers' Markets are shared by two or more Passers." and how many Pool Wallets are not fully read; a *Not enough data* Copy Verdict gives its reason.

**Given** the per-Wallet table
**When** it renders
**Then** it shows Follower PnL and Follower Return at 1, 5 and 30 minutes next to the Wallet's own Real PnL on the same Positions, the 1- and 30-minute columns tagged "Extra information", the caption "These per-Wallet numbers are not luck-checked. Only the Random Group Check above is.", "priced N of M" per Wallet, positions left out per delay, and "Follower PnL ignores the spread and the follower's own price impact, so it is an upper bound." with the Spread Allowance's limits (FR-18a, UX-DR36)
**And** a Wallet opens its Verdict page with "← Back to Copy Test (Cut-off Date …)" (UX-DR37), and the page shows the Seed (FR-11); the table polish is what slips first.

### Story 6.5: Copy windows in the Sample Dataset

As the examiner,
I want the Copy Test to run offline on the real Sample Wallets,
So that I can check it without the network.

**Acceptance Criteria:**

**Given** the build-sample script from Story 2.6
**When** it is extended and run on the raw capture zip (checked against its SHA-256 first)
**Then** it adds, for each of the 10 real Wallets, the price windows of its Copy Sample as drawn by the core rule with the default Seed, and the Synthetic Wallets' price paths, as `records` JSON (AD-14)
**And** the committed Sample Dataset stays under 50 MB, the output is identical on a re-run, and nothing is edited by hand (AD-14)
**And** an offline Scan with the default Cut-off Date shows a Copy Test page with sockets blocked
**And** stage 2 is closed: all tests pass in CI on the three systems and the README covers the Scan, Hold-up Test and Copy Test (NFR-12).

### Story 6.6: Real data, reported either way

As the examiner,
I want to see what the Copy Test says about real Wallets, whatever it is,
So that I can judge the method on reality, not only on made-up Wallets.

Beyond the stage 2 minimum (PRD §6.1). The live Hold-up run moved to Story 5.3 (2026-11-18).

**Acceptance Criteria:**

**Given** the old price route still answers (the daily check says one-minute)
**When** the Copy Test runs on Story 5.3's real Scan with the default Cut-off Date (or a new one, if Story 5.3 was not done)
**Then** its Copy Test results, the Scan size, Markets used and Wallets not fully read are written into the README and the reflection notes, whichever way they come out (SM-5, NFR-13, SM-C2).

**Given** the old route is gone at that time
**When** the real-data run is made
**Then** the Copy Test runs on the frozen 50-Wallet insurance pool (`spike/INSURANCE-RULE.md`, captured October 2026) with the app computing Passers, Copy Samples and the Random Group Check as usual, and the page and README state its limits: a pool of 50 fixed in advance, not the app's Scan; ranked by the spike's estimate, not the app's final Real PnL; *Not enough data* with fewer than 2 Passers, reported as it comes out (PRD FR-18c fallback)
**And** the Hold-up Test still runs on a real Scan (Story 5.3), because it needs no prices.

**Given** the 1 December hard stop
**When** this story runs after it
**Then** that is allowed, because it runs the app and writes up results and adds no new code (Edvard, 2026-10-24).

## Epic 7: Where is the edge? Domain Verdicts

The user sees a Domain table on the Verdict page, with or without a model key. Stage 3 is likely to be partial, so its stories are ordered so that stopping after any one still leaves something that works and can be demoed, and no story only makes sense once a later one lands (Edvard, 2026-10-24).

### Story 7.1: Domain Verdicts with tag labels

As a user,
I want to see in which Domains a Wallet's edge is, even without a model key,
So that "skilled" is not one blended number.

**Acceptance Criteria:**

**Given** Mock LLM Mode for Domains (on by default with no key, or `--mock-llm`)
**When** a Market needs a Domain
**Then** `TemplateModel`'s tag rules map the event tags on the stored Market record to exactly one of politics, sports, crypto, macro, other, written from Edvard's committed Domain definitions, with a Market whose tags are all off the map going to *Other*; the label is stored with source `tag-rules` and its date, keyed by (Market, source), and reused (FR-15, FR-19, AD-16; tag rules: Edvard, 2026-11-05; one Domain per Market and the *Other* rule: AI's proposal, Edvard confirmed)
**And** the tag rules are checked on a small set of Markets kept apart from the 50 hand-labelled ones, and they are never run on those 50 before Edvard's labels are committed (FR-19).

**Given** the raw capture, which holds no tags
**When** the Sample Dataset is rebuilt for Domains
**Then** a one-off script reads the Sample Wallets' event tags once from Gamma and saves them next to the capture zip with their own SHA-256 file, and the build-sample script from Story 2.6 is extended to add them to the Market records, with nothing edited by hand (AD-14; AI's proposal, Edvard confirmed, 2026-11-05)
**And** the script leaves out the events behind the 50 hand-label Markets, and adds them only once Edvard's definitions and labels are committed (FR-19; Edvard, 2026-11-05).

**Given** a Wallet's tested Positions
**When** the Domain Verdicts run
**Then** each Domain with at least 30 Resolved Positions gets its own Skill Test, its p-value multiplied by the number of Domains tested (capped at 1) before the Verdict is chosen; Domains under 30 show *Not enough data* and do not count toward the multiplier; *Other* is a Domain like the rest (FR-20)
**And** each result's scope is its base set plus the Domain, keyed with the label source (AD-22), and its phrases use the adjusted p-value (AD-25).

**Given** the generator
**When** it runs
**Then** it also makes the split-domain trader (60 bets at 0.50 in crypto with exactly 42 won; 60 at 0.50 in sports with exactly 30 won), which gets crypto *Skilled (high confidence)* and sports *No evidence of skill* (FR-13, FR-20).

**Given** the Verdict page
**When** a Wallet has Domain results
**Then** after the honesty notes the Domain table shows Domain, Resolved bets and a Domain Verdict pill per row, the note "Each Domain's odds are adjusted for testing several Domains.", and the tag "Labels: Polymarket tags" (FR-21, UX-DR40, AD-13)
**And** in Offline Mode the table uses the stored tag labels only and never calls a model (FR-14; Edvard, 2026-10-24).

**If stage 3 stops here:** the Domain table works fully online and offline with tag labels, and the split-domain check passes.

### Story 7.2: Model labels with the 80% gate

As a user,
I want Domains labelled by a language model whose accuracy was checked against a person,
So that the Domain table is trustworthy when a key is set.

**Acceptance Criteria:**

**Given** the 50 Markets in `sample_data/hand_labels/markets.csv` (drawn by `spike/hand_label_draw.py`: 5 per Sample Wallet, seeded, resolved Markets only)
**When** Edvard labels them
**Then** in one sitting he first writes a one-line definition of each Domain, saying where the overlap cases go (the AI suggests none), then labels blind: the file shows only each Market's question, with no tag-rule label, model label, category or tag field (Edvard, 2026-10-24)
**And** the definitions and the labels are committed together before either labeller (tag rules or model) runs on these 50, and are never edited afterwards (FR-19, AD-16); done 2026-11-05, with the definitions in `sample_data/hand_labels/domain-definitions.md`.

**Given** a key in `.env`
**When** a Market needs a Domain online
**Then** the key is read only from `.env` through the settings object and never logged (NFR-5), and `AnthropicModel` in `data/model.py` asks `LLM_MODEL` (default `claude-haiku-5-5`, effort low) with Edvard's Domain definitions quoted word for word in the prompt and structured output limited to the five Domains; the label is stored with the model ID and date and reused; classifying again is an explicit command, never a side effect (FR-19, AD-16).

**Given** the gate command, run by hand with a key
**When** it labels the 50 Markets with the model
**Then** agreement with Edvard's labels is computed (case-insensitive), and the result is written to a committed report (SM-6)
**And** below 80% `[ASSUMPTION]` the model setting is raised to a larger model, the check is re-run, and both results are reported (FR-19)
**And** tests run against a fake model with sockets blocked; the real model is called only by this command and in normal online use (AD-17).

**Given** the Verdict page online with model labels
**When** the Domain table renders
**Then** its tag reads "Labels: Claude Haiku 5.5" (or the model actually used); if the model does not answer, the table is replaced by "Domains are not available: the language model did not answer." (UX-DR40); with no key, Story 7.1's tag labels are used and tagged as such.

**Given** a model call for a Market's Domain
**When** it fails or answers with anything other than one of the five Domains
**Then** it is tried at most 3 times in all; an answer outside the five Domains is never stored and counts as a failure; a Wallet with any Market still unlabelled gets the "Domains are not available" message instead of the table, and no Market is put in *Other* by default (FR-19; Edvard, 2026-11-18, rejecting the feedback's "Other with source fallback" because it would skew the *Other* Domain)
**And** a test with a fake model that answers "finance" checks that nothing is stored and the message is shown (FR-19)
**And** the README states how many model calls the Sample Dataset needs (one per Market, stored and reused) and an estimate of their cost (FR-19).

**If stage 3 stops here:** the same table with model labels and a measured agreement rate; without a key it falls back to Story 7.1.

## Epic 8: Bots and plain-language explanations

The user sees a market-maker Flag where it applies and a checked Explanation of at most 60 words. Ordered by the same stop-anywhere rule as Epic 7. If time runs short, Story 8.3 slips first, then 8.2; Story 8.1 is cheap pure rules and goes last (Edvard, 2026-10-24).

### Story 8.1: The market-maker Flag

As a user,
I want to be warned when a Wallet looks like a bot or market maker,
So that I do not read its profit as forecasting skill.

**Acceptance Criteria:**

**Given** a Wallet's activity rows (AD-10)
**When** `core/flags` runs
**Then** it Flags the Wallet when at least 2 of 3 rules hold: it bought both outcomes in at least 30% of the Markets it traded; it sold at least 80% of the shares it bought; the median time from buy to sell, over the shares it sold, is under 1 hour `[ASSUMPTION: starting values]` (FR-22).

**Given** the generator
**When** it runs
**Then** it also makes the synthetic market maker (many small buys and sells on both sides of the same Markets, flat inventory), which is Flagged; the coin-flipper and sharp-trader Synthetic Wallets are not (FR-13, FR-22).

**Given** a Flagged Wallet
**When** its Verdict page renders
**Then** a compact warning box under the odds phrase reads "⚠ Likely market maker (heuristic, may be wrong)", read with a hidden "Warning:", and the Verdict is unchanged (FR-22, UX-DR38).

**If stage 3 stops here:** the Flag works on its own, with no key.

### Story 8.2: Template Explanation, checked

As a user,
I want a short plain-language sentence or two explaining the Verdict,
So that I understand it without reading the statistics.

**Acceptance Criteria:**

**Given** any Verdict (and the Domain Verdicts when Epic 7 is built)
**When** the Verdict page renders
**Then** directly under the Verdict card an Explanation of at most 60 words `[ASSUMPTION]` is built from templates that take every number and phrase from `core/phrases`, with the info tag "Template text" (FR-23, FR-15, UX-DR39, AD-25).

**Given** the Explanation check in `services` (FR-24, AD-16)
**When** any Explanation is about to be shown
**Then** code checks that it names the same Verdict and the same odds phrase as the card and contains none of the banned or avoided words; a failing Explanation is replaced by the template and the replacement is counted (FR-24)
**And** the words come from the one list in the code, copied from EXPERIENCE.md *Voice and Tone* (banned plus "also avoided"), and the test plants each word on the list in an Explanation and checks it is replaced (FR-24)
**And** across every Sample Dataset Wallet and Domain Verdict the template replacement count is 0, because a template that fails the check is a bug (SM-7).

**If stage 3 stops here:** every Verdict has a checked Explanation, with no key.

### Story 8.3: Model-written Explanations

As a user,
I want the Explanation written by the language model when a key is set, and only when it is correct,
So that it reads naturally without ever claiming more than the test shows.

**Acceptance Criteria:**

**Given** a key in `.env` and the app online
**When** an Explanation is needed
**Then** `AnthropicModel` writes it (at most 60 words), it passes through the Story 8.2 check, and a failing one is replaced by the template with the "Template text" tag and counted (FR-23, FR-24, AD-16)
**And** a planted Explanation with a wrong Verdict is replaced by the template (FR-24)
**And** if the model does not answer, the template is shown with its tag (UX-DR39).

**Given** Offline Mode
**When** an Explanation is needed
**Then** the model is never called, even with a key set; the template is used (FR-14, AD-13).

**Given** the Sample Dataset's Wallets and Domain Verdicts run online with the model
**When** the replacement rate is measured
**Then** the share of Explanations replaced is reported in the README, whichever way it comes out, with no target (SM-7, SM-C3).

**If stage 3 stops here:** the full stage 3.


