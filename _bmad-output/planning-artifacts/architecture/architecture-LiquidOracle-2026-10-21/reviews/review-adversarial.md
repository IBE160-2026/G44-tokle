# Adversarial review of the architecture spine (2026-10-21)

Independent reviewer (subagent with no part in writing the spine). Read: ARCHITECTURE-SPINE.md, .memlog.md, PRD (glossary, FR-1 to FR-24), EXPERIENCE.md, spike/FINDINGS.md, reviews/review-inline-gate.md. No files changed except this one.

**Verdict:** not safe to build on yet. Several data definitions that decide the Verdict are still open: shares held, which Wallets and Positions survive a cap or a partial read, and how outcomes are drawn. Two stories can each follow every AD to the letter and still give wrong Verdicts.

Each hole below names two units built by people who never talk, the ADs both obey, how they diverge, the consequence, a severity and the smallest rule that closes it.

---

## 1. "Shares held at resolution" has no formula, and one reading drops every unredeemed loser (critical)

- **Units:** `core/positions` (story A, Skill Test input) and the activity-reading code in `data/polymarket.py` plus the Sample Dataset builder (story B).
- **Both obey:** AD-10 (held shares come from activity rows of types TRADE, REDEEM, SPLIT, MERGE), AD-11.
- **Divergence:** A computes held = Σ BUY size − Σ SELL size. B takes held = the REDEEM row's size, because REDEEM is listed as a source and "redeemed shares" reads as "held at resolution". An unredeemed loser has no REDEEM row, so B gives s = 0. On the rank-339 spike Wallet, 837 of 1,196 Positions are unredeemed losers.
- **Second divergence:** AD-11 stores the positions-vs-activity share gap "as its size, not as a flag" but never says what happens above the line. The memlog says such a Position is marked. The spine says only "stored". Story A keeps a Position with a 100% gap and uses the activity count. Story C leaves it out. Neg-risk CONVERSION rows are not among AD-10's activity types, so a converted Position shows bought = 0 in activity and s ≤ 0.
- **Consequence:** under B, losses vanish from both Real PnL and the Simulations (s = 0 adds nothing to either), so a Wallet that leaves its losers unredeemed reads as *Skilled*. This is the survivor bias FR-3 exists to stop. Under A with CONVERSION rows missing, s can be 0 or negative.
- **Fix (tighten AD-10/AD-11):** held = Σ BUY − Σ SELL + SPLIT-in − MERGE-out per token, from activity rows. REDEEM rows are never a share source. Require 0 < s ≤ shares bought (positions list). Anything else gets the stored exclusion reason "shares not explained by activity". A gap above the gap setting at build time also gets that exclusion reason, and it counts toward the 10% note. Either add CONVERSION to the activity types or leave out neg-risk-converted Markets with their own reason.

## 2. A partial Market read, sorted by time, brings survivor bias back into the candidate list (critical)

- **Units:** `data/polymarket.py` Market-anchored list function (A) and `services/scan` candidate builder (B).
- **Both obey:** AD-9 (always `sort_by=TIMESTAMP`, partial reads stored and shown), AD-3 (a timed-out page is re-requested smaller, then fails).
- **Divergence:** AD-9 fixes the sort field, not its direction, and assumes time order is neutral about outcome. It is not. On a resolved Market, a redeemed winner's event time is its redemption, after resolution. An unredeemed loser's is its last buy, before resolution. A capped DESC read of a $400M Market (only 100-row pages work, and the read is cut off at some depth) keeps mostly winners. An ASC read keeps mostly losers. B adds every Wallet in the read rows to the candidates and shows the Market as "partial". That follows AD-9, but the candidate list is now picked partly on outcome. The Markets that go partial are the biggest ones, which matter most.
- **Error-path divergence:** after AD-3's retries, A raises `PolymarketUnavailable`. One scan story turns this into job `stopped` (AD-5), so a single 503 on one Market halts a 70-minute Scan. Another treats it as `partial` and goes on (AD-9). The same choice applies to a candidate Wallet whose own fetch fails. Skipping that Wallet drops mostly big Wallets, because they are the ones that time out.
- **Consequence:** winners in the largest Markets are over-represented among candidates, so profit-ranked selection leans on luck more than the Minimum Luck Passes note admits. Scan behaviour on errors depends on which story you read.
- **Fix (tighten AD-9):** a partial Market read gives no candidates. The Market is counted and shown as "not used: partial". Candidates come only from full CLOSED+OPEN reads. Name the direction (ASC) anyway. A failed Market read is marked partial and the Scan goes on. A failed Wallet fetch stops the job (resumable). A Wallet is never skipped silently.

## 3. Fetch bounds use an event time that depends on the outcome, and the after-part window depends on itself (high)

- **Units:** `positions_near()` in `data/` (A) and `core/positions` plus the activity read (B).
- **Both obey:** AD-7 (`end` = cut-off + 30 days only narrows the fetch), AD-8 (before = latest 2,000 by Gamma resolution time; after = first 2,000 by first entry time), AD-10 (first entry time comes only from activity rows; the activity read is "limited to the AD-8 window").
- **Divergence (a):** the 30-day margin filters on `last_event_at`. A winner that resolved on day −1 and was redeemed on day +45 has `last_event_at` = cut-off + 44 days and is not fetched. An unredeemed loser in the same Market has `last_event_at` before resolution and is always fetched. The "late-redemption miss" that AD-7 plans to measure is not random noise. It removes winners only.
- **Divergence (b):** A has to choose the first 2,000 after-part Positions by first entry time. AD-10 allows that time only from activity rows, and the activity read is limited to the window A is trying to choose. A falls back to v2 `first_entry_at` (forbidden, and can be 0, which sorts first) or reads unbounded activity (breaks the cap). In the before part, B limits activity to the window's resolution-time range. It then misses buys made months earlier for Positions that resolve inside the window, so held shares come out short or negative.
- **Consequence:** the before part is biased against skill and against the Scan ranking of Wallets that redeem late. The after window is chosen on a forbidden or missing key. Held shares are wrong for long-dated Markets.
- **Fix (rewrite AD-7/AD-8 fetch rule):** read the OPEN list in full. Read CLOSED newest-first with no `end` bound, and stop when a page's oldest `last_event_at` is earlier than the 2,000th-latest resolution time collected so far. This is safe because a held-to-resolution CLOSED row always has `last_event_at` ≥ resolution. For the after part, read activity ASC from `start` = cut-off and keep going until 2,000 Resolved Positions have their first buy. Every after-part buy is at or after the cut-off. For the before part, start the activity read at the earliest Gamma Market start date among the window's Markets, not at a resolution time.

## 4. The Simulations draw each Position on its own, but Positions share Markets (high)

- **Units:** `core/holdup` (pools the Passers' after parts, A) and `core/skilltest` (draws each Outcome independently at its Entry Price, per the Glossary, B).
- **Both obey:** AD-11 (one builder), AD-15 (seeded), the PRD Simulation definition.
- **Divergence:** Scan candidates come from the same Markets by construction (AD-9). Say 7 Passers each hold YES in the same 40 after-part Markets at 0.50 and win 26. As 40 real events that is z ≈ 1.9, about p ≈ 0.04 (*Likely skilled*). B treats it as 280 separate coin flips, 182 won, z ≈ 5.0, p < 0.0001 (*Skilled (high confidence)*). The same fault hits one Wallet holding YES and NO of one Market (FR-22's market maker): B can let both sides win in a Simulation, which reality never does. Split/merge Markets are already left out, but a Wallet that simply bought both sides is not.
- **Consequence:** the luck spread is too narrow, so p-values are far too small. The Hold-up Test, the stage-2 headline, can read *Skilled (high confidence)* on luck.
- **Fix (new AD on Simulations):** each Simulation draws one uniform U per Market, shared by every Position in that Market across all Wallets. A YES-side Position wins when U < p, a NO-side Position when U > 1 − p. Each Position still wins with probability equal to its Entry Price, so the FR-5 checks are unchanged, and the two sides of one Market can no longer both win. Neg-risk sibling Markets stay independent and are noted as a limit.

## 5. The Scan funnel is unspecified: which Markets, how many candidates, and what ranks them (high)

- **Units:** `services/scan` Market enumerator (A) and `services/scan` ranker (B).
- **Both obey:** AD-9 ("for each Market resolved before the cut-off"), AD-10, Glossary (ranked by Real PnL from the Wallet's own Positions), AD-5.
- **Divergence:** "each Market resolved before the cut-off" covers every Market Polymarket has ever had. A limits it to "top 500 by volume in the 90 days before the cut-off" (a filter nobody chose). That gives around 100,000 candidate Wallets. B needs Real PnL for each, and Real PnL needs each Wallet's activity rows for held shares and fees (about 20+ requests per Wallet at 5/s), which is days of work. So B ranks on the sum of v2 `realized_pnl` over the Market-anchored rows. That number is not Real PnL: it includes sell profit (Exit PnL), the memlog calls it not reproducible, it covers only the scanned Markets, and AD-10 does not list it.
- **Consequence:** the top 200 are picked on a number the PRD does not define, or the Scan runs far longer than 70 minutes. The progress contract (`done/total` Wallets) also has no phase for listing candidates, so "84 of 200" means nothing while Markets are still being read.
- **Fix (new AD):** the Market set is the Markets resolved in [cut-off − L, cut-off), top M by volume (`[ASSUMPTION]` L, M), picked without looking at outcomes and stored with the Scan. Stage 1 shortlists K = 3 × N candidates by a stated cheap number. Stage 2 fetches the shortlist and ranks it by Real PnL (AD-10 sources). Both limits are shown on the Scan page. Progress reports a phase field.

## 6. One per-Wallet cache, two different windows (high)

- **Units:** `services/lookup` (A) and `services/scan` (B), sharing `data/store.py`.
- **Both obey:** AD-4 (a Wallet's lists are fresh for 24 hours, so a lookup makes 0 calls), AD-8 (lookup = latest 2,000 overall; Scan = 2,000 each side of the cut-off).
- **Divergence:** at 10:00, B fetches Wallet W's 2,000 + 2,000 Positions around a June 2025 cut-off. At 11:00 the user opens W's Verdict page from the Watchlist. AD-4 says W is fresh, so A makes no calls and builds the Verdict from whatever is stored: Positions around June 2025, not the latest 2,000. The FR-11 line "Based on the latest 2,000 of N" is then false. The reverse also happens: a lookup's latest-2,000 cache makes a later Scan's before part look fresh but empty.
- **Consequence:** a wrong Verdict with a false honesty note, and 0 network calls, so nothing looks wrong.
- **Fix (tighten AD-4):** freshness is kept per (Wallet, list, covered time range). A read is fresh only if the stored ranges cover the window asked for and were fetched less than 24 hours ago. `positions_near` records what range it covered.

## 7. Partial or doubled writes pass as a fresh cache, and a Scan does not freeze its data (high)

- **Units:** the job worker (A), web-request lookups (B), and the Hold-up and Copy Test jobs (C).
- **Both obey:** AD-5 (resume from the first unfinished Wallet, reusing the cache), AD-6 (short write transactions), AD-4 (24 hours).
- **Divergence (a):** A is writing W's activity pages in short transactions when the app is closed. On resume the cache holds half of W's rows and reads as fresh, so held shares are short. AD-11's "incomplete" flag covers only the API's cap, not a write that was cut off. Separately, B looks up W while A fetches it, and both insert rows. FINDINGS says identical activity rows are separate fills and must never be de-duplicated by value, so the doubled rows cannot be cleaned up. Shares and Real PnL double.
- **Divergence (b):** a Scan is interrupted Monday at 84/200 and resumed Wednesday. The ranking used Monday's data, but the 116 remaining Wallets are fetched again Wednesday. The Copy Test job runs a week later. The after parts have grown with new resolutions, so the Copy Pool rests on different Positions than the Hold-up Test, and "same Seed, same sample" (FR-18) fails.
- **Consequence:** silently wrong Verdicts, and Hold-up and Copy Test results for one Scan that do not rest on the same data.
- **Fix (new AD):** each Wallet fetch writes a snapshot with a `fetch_id`, made visible in one final step. Readers see only complete snapshots. Fetching any one Wallet is guarded by a per-Wallet lock shared by web threads and the worker. A Scan stores the `fetch_id` it used for each Wallet and an as-of time. Resume, Hold-up Test and Copy Test read only those snapshots and ignore anything resolved after the as-of time.

## 8. "Watchlist", "Passers" and the Verdict page rate a Wallet on three different Position sets, and SKILL_RESULT cannot tell them apart (high)

- **Units:** `services/scan` + Watchlist template (A), `services/lookup` + Verdict page (B).
- **Both obey:** the PRD (Glossary: Watchlist is whole history; FR-16: Scan Skill Tests the before part), AD-8 (lookup = latest 2,000 overall), the ER diagram (WALLET has many SKILL_RESULT; columns deferred to the first story).
- **Divergence:** A stores the before-part result as the Wallet's SKILL_RESULT and lists it on the Watchlist (p = 0.004, *Skilled*). The user clicks the row (UX: it opens the Verdict page). B reads "the latest SKILL_RESULT for the Wallet" and shows the Scan's before-part result under the lookup's "latest 2,000" note. Or B recomputes on the latest 2,000 overall (all after the cut-off) and shows *No evidence of skill* with no explanation. The PRD itself conflicts here: the Glossary says the Watchlist is rated on whole history, while FR-16 says before part only. The spine does not settle it.
- **Consequence:** two contradictory Verdicts for one Wallet on adjacent pages, or one result shown under another's label.
- **Fix (new AD + PRD change first):** every SKILL_RESULT carries a scope (`lookup`, `scan_before`, `scan_whole`, `holdup_after`, `domain:<d>`), `scan_id`, cut-off, Seed and `fetch_id`, and every page reads by the full key. Edvard decides whether the Watchlist is `scan_whole` or `scan_before`, and the Glossary or FR-16 changes to match. The Verdict page opened from a Scan shows that Scan's scope and says so.

## 9. "Resolved" and "Outcome" have two sources, and the PRD still names the forbidden one (medium)

- **Units:** `core/positions` (A) and the Gamma market cache in `data/store.py` (B).
- **Both obey:** AD-10 (outcomes and resolution time from Gamma), PRD FR-3 ("a Position in a resolved Market (price exactly 0 or 1) from either source"; resolution time = "the closed list's own timestamp"), AD-4 ("Resolved Markets ... never expire").
- **Divergence:** A marks a Position resolved when the positions list shows `cur_price` 1. B holds a Gamma record for that Market, fetched while it was still open, and has no expiry rule for open Markets, so `closedTime` is null and AD-7 cannot place the Position. A Market that resolved 50-50 has outcome prices 0.5/0.5: A sets o = 0.5, but the Simulation draws o from {0, 1}, so the real result and the Simulations differ in kind. A Market disputed after reaching price 1 counts as resolved on one path and not on the other. FR-3's "closed list timestamp" is v2 `last_event_at`, which AD-7 forbids, and the PRD still says it.
- **Consequence:** Positions stuck as unresolved for ever, or put on the wrong side of the cut-off, and 50-50 Markets distorting both Real PnL and the p-value.
- **Fix:** Resolved means Gamma says closed, with outcome prices exactly {0, 1} and a `closedTime`. Anything else gets a stored exclusion "unclear resolution" (AD-11). Gamma records are cached for ever only once resolved; open ones expire with the Wallet lists. Change PRD FR-3 to Gamma resolution time (plan change first).

## 10. The order of cap and exclusions is not fixed, so every count has two denominators (medium)

- **Units:** `positions_near` (cap, A) and `core/positions` (exclusions, B), read by the Hold-up Test, the Copy Pool and the Verdict card.
- **Both obey:** AD-8 (2,000 Resolved Positions), AD-11 (exclusions; the 10% note), PRD Minimum After-bets, 30-minimum, FR-11 lines.
- **Divergence:** a market maker has 5,000 before-part Resolved Positions, 40% of them in split/merge Markets. A caps to 2,000, then B leaves out 800, so 1,200 are tested. A different story leaves out first and then caps, so 2,000 are tested. A Wallet with 12 after-part Resolved Positions, 3 of them left out, counts toward a Hold-up group (12 ≥ 10) but adds only 9 Positions. The 10% note uses the window on one path and the whole Wallet (unknown, not fetched) on another. FR-11's "latest 2,000 of N" is printed for the after part too, where it should read "first 2,000".
- **Consequence:** Wallets in the wrong Hold-up group or Copy Pool, a different count of Wallets dropped between the two groups (the FR-17 20-point warning moves), and false honesty lines.
- **Fix (tighten AD-8/AD-11):** cap first, on Resolved Positions before exclusions. Then exclude. Every threshold (30, Minimum After-bets, Copy Pool, 10%) uses the count tested after exclusions within the window. `core/positions` returns one record with window size, excluded counts by reason, and tested count, and pages print only from it. The after part gets its own FR-11 wording.

## 11. Offline data cannot feed the pipeline the spine requires (medium)

- **Units:** Synthetic Wallet generator plus serializer (A) and `OfflineClient` plus `core/copytest` (B).
- **Both obey:** AD-14 (serialized client records, normal pipeline, 25 MB limit, price windows "wide enough for the 30-minute Copy Delay"), AD-10, AD-13.
- **Divergence:** A writes positions-list rows for each synthetic bet, as the FR-13 table describes them. B needs activity rows for held shares (AD-10), Gamma lists of resolved Markets and Market-anchored lists for an offline Scan (AD-9). Without them every synthetic Position is incomplete, or the offline Scan raises `NotAvailableOffline`. Size: FR-12 commits "all Synthetic Wallets", including 1,000 coin-flippers. At about 200 Positions each, with activity rows and price windows, that is roughly 100 MB or more, which breaks the 25 MB test. Price lookup: the window ends at buy + 30 min, and B takes "the first point at or after buy + delay". A buy at 12:00:40 needs the point at 12:31:00, which falls outside the window. Live works, offline drops every 30-minute price, and the forecaster check can fail offline only.
- **Consequence:** the offline examiner path (UJ-3) or CI fails, or it passes on a dataset different from the one the tests describe.
- **Fix (tighten AD-14):** A generates fills (activity rows) first and derives every other list from them with the same serializer. Large synthetic groups are regenerated from the Seed by `load-sample`, not committed. Only those files count toward the size limit. One core `price_at(points, t)` rule (last point at or before t, at most 2 minutes old) is used both live and offline. Windows are [first buy − 2 min, last buy + 32 min]. A round-trip test checks: generator, then `OfflineClient`, then pipeline, gives the intended bets and Verdicts.

## 12. One Seed, but random results depend on the order of draws (medium)

- **Units:** `services/copytest` (A) and `core/skilltest` called from a lookup and from a Scan resume (B).
- **Both obey:** AD-15 (core functions take `seed` and build their own Generator; one `SEED` setting; Seed stored).
- **Divergence:** A builds one `Generator(SEED)` and draws Copy Samples for the Pool's Wallets in turn. Wallet X's sample then depends on which Wallets came before it, so a resumed or re-ordered Copy Pool gives X a different sample under the same Seed. B gets the Positions in SQLite row order, which changes after a re-fetch. The same data and the same Seed then give a different p-value, which breaks FR-7.
- **Consequence:** results cannot be repeated, and FR-7/FR-18 reproducibility tests are flaky or wrong across runs.
- **Fix (tighten AD-15):** `core` sorts its input by (`condition_id`, `token_id`) before any draw. Each random unit gets its own generator from `numpy.random.SeedSequence(SEED, spawn_key=(purpose, wallet or scan id))`. A Generator is never shared between Wallets or purposes.
