# Epic 5 Context: Does the skill last? Hold-up Test

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

The user compares the Before-Cut-off Passers with the Comparison Group on the bets made after the Cut-off Date, to see whether skill found before the date lasted or was a lucky streak. Stories 5.1 and 5.2 close the stage 2 minimum (Epics 4 and 5 passing their checks offline on the Sample Dataset) and never slip; if they run late, Epic 6 starts later. Story 5.3, a live Hold-up run, is beyond the minimum and may run after the 1 December code stop because it adds no code. The target was 27 to 28 November 2026. A result showing that skill does not last is a valid outcome, never a failure, and is reported whichever way it comes out.

## Stories

- Story 5.1: The two groups and their test
- Story 5.2: The Hold-up Test page
- Story 5.3: Hold-up Test on a live Scan (beyond the minimum)

## Requirements & Constraints

- **Groups from the before part only:** Before-Cut-off Passers are the Scan's Wallets rated *Skilled (high confidence)* on the before part. The Comparison Group is those rated *Likely skilled* or *No evidence of skill* on the same part. *Not enough data* is in neither, and no Wallet is in both. No Position from after the Cut-off Date decides membership; a Wallet that passes only when after Positions are included is not a Passer. This differs from the Watchlist, which uses both windows.
- **After part:** a Wallet's first 2,000 Positions in resolved Markets bought on or after the Cut-off Date `[ASSUMPTION: 2,000]`, the same cap as the before part, and the page says so.
- **Minimum After-bets = 10 `[ASSUMPTION]`:** a Wallet counts in its group's result only with at least 10 tested Positions in its after part, by the same rule in both groups. Each group's result shows Wallets in the group, Wallets dropped for too few after bets, Resolved Positions counted, and Wallets "not fully read".
- **Dropped-share flag:** when the share of Wallets dropped differs by more than 20 percentage points `[ASSUMPTION]` between the groups, the result carries a flag and the page warns: "More Wallets were dropped in one group than in the other. Wallets that stop betting may be the ones that lost, so the group with more dropped Wallets may look better than it is."
- **Pooled test:** each group's after parts are pooled and run through the Skill Test with one draw per Market shared across all the group's Wallets, so Passers betting in the same Markets are not independent evidence. Each group result has Resolved Positions, Real PnL, p-value and Verdict. A group with fewer than 30 Resolved Positions after the cut-off shows *Not enough data*.
- **Checks:** steady-sharp Synthetic Wallets are *Skilled (high confidence)* on their after part; lucky-streak Wallets that passed before are *No evidence of skill* on theirs; a planted 60% vs 10% dropped example sets the flag and equal shares do not; 7 coin-flipper Passers holding the same side of the same 40 Markets get p < 0.05 in at most 7% of 1,000 planted runs.
- **Lucky streak (generator):** a separate group of 1,000 Wallets built from the coin-flipper rules, with bets on both sides of the default Cut-off Date (1 July 2025) and fair odds after it. Epic 1's coin-flippers and their golden result stay unchanged. They are for the checks only: built by the generator in the tests, never written to disk, not loaded into the Sample Dataset and not in the offline Scan (Edvard, 2026-11-27, Story 5.1).
- **The offline warning is real and stays (Edvard, 2026-11-27):** the 1,000 coin-flippers in the offline Scan have no bets after the Cut-off Date, so all are dropped (6 as Passers, 994 in the Comparison Group) and the dropped-share flag is set offline. The rule is not changed to hide it; Story 5.2 says why it shows.
- **"Not fully read" in a group:** the count covers every Wallet in the group whose before or after part was not fully read.
- **Real-data result for the README:** the offline Hold-up result covering the 8 real Sample Wallets in the offline Scan, with its limits stated (only 8 Wallets, picked for the Sample Dataset, not a full Scan; two large Wallets stay outside the Scan).
- **Same exclusions on both sides, read-only, network-blocked tests;** each test names its FR or AD.

## Technical Decisions

- **Where it lives:** the maths is pure code in `core/holdup` (no I/O, no SQL); the Scan job's Hold-up phase is in `services/scan` (`hold_up_members`, `hold_up_scan`: it shares that module's frozen-part helpers, and a separate module would import in a circle; Story 5.1); `services/holdup` is the page's service (Story 5.2); only `data/store.py` runs SQL. The Skill Test engine in `core/skilltest` is reused, not copied. The group names and the result scope are constants in `records.py`.
- **Random unit:** in a group test the unit is the test itself, not the Wallet: one generator from the Seed and a spawn key for the purpose and test id, so all the group's Wallets share the per-Market (and per negative-risk event) draws. Positions are sorted by (`condition_id`, `token_id`) and Wallets by address before any draw. The side whose `token_id` comes first as text wins on the low draw, the same for every Wallet in the group. `random`, numpy global state and `hash()` are never used.
- **Stored result:** scope `holdup_after`, with `scan_id`, cut-off and Seed; pages read results by the full key and name the set they show. One `group_result` row per Scan and group, written in the transaction that finishes the Scan (a Scan finished before Story 5.1 has none), shared later by the Copy Test. The dropped-share flag is worked out from the two rows. `Store.group_results` gives the Passers first, then the Comparison Group, and nothing for an older Scan.
- **Measured offline (Story 5.1, full Scan of the Sample Dataset):** Passers 10 Wallets, 7 dropped, *Skilled (high confidence)* on 300 bets of three made-up Wallets, Real PnL $6,000. Comparison Group 999 Wallets, 996 dropped, *No evidence of skill* on 409 bets of 3 real Wallets (307 from 0xd3a6e5), Real PnL about -$19,217, p = 0.56. No real Wallet is a Passer. A test pins the Comparison Group's numbers.
- **Frozen data:** the Hold-up Test reads only the snapshots the Scan froze for each Wallet (before and after side) and ignores anything resolved after the Scan's as-of time, so it and the Copy Test rest on the same data.
- **Job phase:** the Hold-up Test is a phase of the Scan job after the Skill Tests; the progress JSON carries `phase`, the progress text names the step "Hold-up Test", and a Scan counts as finished only when every phase is done.
- **One builder:** after-part Positions come from the existing window function with the after side and the one Position builder, so exclusion counts and "not fully read" mean the same on both sides. The cap applies first, then exclusions; thresholds (10, 30) use tested counts.
- **Slow checks:** the 1,000-run planted check is marked `slow`: in full once per push on Linux with Python 3.14, 100 runs on the other jobs, always with 10,000 Simulations. Determinism checks (same Seed identical; two `PYTHONHASHSEED` subprocess runs agree; stored golden counts) run unchanged on every job.
- **Generator:** standard library only (no numpy in `data`), draws from sha256 of its fixed constant, Wallet, bet and purpose; fills are written first and every other list derived by the one serializer. The coin-flippers are regenerated by `load-sample`, not committed; the lucky streaks are never loaded; the committed Sample Dataset stays under 50 MB.
- **Phrases:** every number phrase comes from `core/phrases.py`.

## UX & Interaction Patterns

- **Tab:** *Hold-up Test* joins the Scan tabs (links in a navigation region named "Scan", current page marked; not an ARIA tab list), one page per Scan. Title: "Hold-up Test · {Cut-off Date} · LiquidOracle".
- **Group cards:** two cards, *Before-Cut-off Passers* and *Comparison Group*, side by side from 900 px and stacked below: the small Verdict pill (dots plus text), the odds phrase, then small figures: Resolved bets counted, Real PnL, Wallets in the group, Wallets dropped for too few bets after the Cut-off Date, Wallets not fully read.
- **Under the cards:** "Each Wallet's bets after the Cut-off Date are capped at its first 2,000. Bets in the same Market are simulated together, not as separate evidence." and the Seed.
- **States:** the dropped-share warning box sits above both cards. No Passers: "No Wallet passed on its bets before the Cut-off Date, so the Hold-up Test and Copy Test have nothing to test." Empty Comparison Group card: "No Wallets in this group: every scanned Wallet passed or had *Not enough data* before the Cut-off Date." A group too small shows *Not enough data* with its count of resolved bets after the Cut-off Date.
- **Decided in Story 5.2 (Edvard, 2026-11-27):** five figures per card (Wallets not fully read is the fifth). With no Passers the Passers card holds the sentence and the Comparison Group card still shows its result. In Offline Mode an info box under the warning says the Passers tested are made-up Wallets, not real traders (his addition, with a test that fails if a real Wallet becomes a Passer), and why the warning shows on the Sample Dataset. A Scan finished before Story 5.1 has no tab and no page. The page is `/scans/<id>/hold-up`, built by `services/holdup.py` from the stored rows; the Scan header and tabs are one template part (`scan_head.html`) and one function (`services.watchlist.scan_header`), where Epic 6 adds the Copy Test tab.
- **Server-rendered:** complete without JavaScript, existing tokens and breakpoints.

## Cross-Story Dependencies

- **Builds on Epic 4:** the Scan's frozen snapshots, its `scan_before` results (who passed), the job phases and the Scan tabs. The after part's "first 2,000" line, deferred from Epic 4, is first shown on the Hold-up page.
- **5.1 → 5.2:** 5.1 forms the groups, runs and stores the test, and adds the lucky-streak Wallets; 5.2 only shows the stored result, and writes the real-Wallet result into the README.
- **5.3 and Epic 6:** a live Scan run for 5.3 is kept so the Copy Test can run on the same Scan; the Copy Test uses the same Passers and the same Minimum After-bets rule for its Copy Pool.
