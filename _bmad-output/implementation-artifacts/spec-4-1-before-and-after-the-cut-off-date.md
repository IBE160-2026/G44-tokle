---
title: 'Story 4.1: Before and after the Cut-off Date'
type: 'feature'
created: '2026-11-25'
status: 'done'
baseline_commit: '6fded843185bdd5cf91468570de32f7c213cb347'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `positions_near` builds only the lookup window; any `cutoff` or `side` raises `NotImplementedError`. Stage 2 (Scan, Hold-up Test) needs each Wallet split at a Cut-off Date: a before part that judges skill and an after part that checks it, with no Position on the wrong side.

**Approach:** One conversion of the Cut-off Date to 00:00 UTC, and `positions_near(client, wallet, cutoff, side, limit)` gains `side="before"` (latest `limit` Positions in Markets resolved before the cut-off, the lookup's AD-7 fetch with that filter) and `side="after"` (first `limit` Positions by the positions list's `first_entry_at`, in Markets resolved on or after the cut-off, then their activity read from the cut-off). Both return the same `Window` the one builder already takes (AD-11).

## Boundaries & Constraints

**Always:**
- The plan changes first, in its own commits: spine AD-7 (and AD-10's source row) states the after-part rules below and where the date is converted; one architecture memlog entry per decision (`_bmad/scripts/memlog.py append`).
- The cut-off is converted only in `data/window.cutoff_at(day: date) -> int` (00:00 UTC epoch). It refuses a `datetime` (a `date` subclass) with `TypeError`. `positions_near` takes a `date`, never an int.
- `cutoff` and `side` come together or not at all (`ValueError` otherwise); `side` is `"before"` or `"after"`. With neither, the lookup window is byte-for-byte what it is today.
- Before part: a Position is in it when its Market is `in_window`, `closed_time < cutoff`, and every listed row of that Market has `first_entry_at < cutoff`. That filter applies to the CLOSED stop rule's limit-th time, the candidates and the activity range. **Decision (Edvard, 2026-11-25, before approval, AI rec):** a Market Gamma closed before the cut-off but with a Position first entered on or after it is in neither part, so no bet made after the date reaches the before part; the parts mirror each other. Rows entered after the cut-off always have `last_event_at` ≥ the cut-off, so the newest-first CLOSED walk reads them before it can stop. Noted, not changed: the positions list's share count is today's, so shares bought after a Market resolved can only make a before-part Position a share-gap exclusion, never add one or change its result.
- After part:
  - **Lists.** OPEN in full; CLOSED newest-first by TIMESTAMP, stopping when a page's oldest `last_event_at` is before the cut-off.
  - **Rows that count.** The OPEN rows, and the CLOSED rows whose `last_event_at` is on or after the cut-off. **Decision (Edvard, 2026-11-25, review, AI rec):** a CLOSED Position fully closed before the cut-off does not make its Market mixed, so the part is the same at any page size; rejected: reading every Wallet's whole CLOSED history.
  - **Eligible Market.** It is `in_window` with `closed_time >= cutoff`, and every counted row of it has `first_entry_at >= cutoff`. **Decision (Edvard, 2026-11-25, AI rec):** a Market with one side bought before the cut-off and the other after is in neither part as a whole, so the window never splits a Market (AD-20); rejected: only the later Position in the after part.
  - **Choosing.** **Decision (Edvard, 2026-11-25, review, AI rec):** eligible Markets are ranked by their earliest `first_entry_at`, then condition id, not by the first BUY in activity, so a Market entered by a split or conversion is in the window and left out by the builder with its reason, as in the before part; rejected: keep the buy-only rule. Whole Markets are taken by row count up to `limit`, as `_cap` does. Gamma is asked in rank order, in batches, only until the part is full and one more eligible Market is known (or none is left), never for every Market at once.
  - **Activity.** Once the Markets are chosen: one read from `start=cutoff` to `end` = the latest `closed_time` among them, oldest first, under `ACTIVITY_ROW_CAP`. No stop rule.
- `capped` means more Positions were eligible than the part holds: older ones for the before part, later ones for the after part (exact for the after part: `len(chosen)` < all eligible rows). `activity_read_until` keeps its meaning. ("latest"/"first" wording on pages is a later story.) `Window` gains `cutoff: int | None = None` and `side: str | None = None`; its docstring says what `capped` means on each side.
- `WalletClient` and both clients are unchanged.
- Tests are network-blocked and name their FR/AD. Fixtures are cut from the capture by `tests/fixtures/cut_from_capture.py`, never written by hand.

**Never:** no store, snapshot-key, `fetch_wallet`, job or page change (Story 4.3 owns the snapshot key); no `/v2/activity?condition=` reads; no network in the fixture cut (Gamma comes from the frozen `../G44-tokle-data/sample-additions-2026-11-23.json`); existing fixtures stay byte-identical.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Conversion | `date(2025, 7, 1)` | `1751328000` | `datetime` → `TypeError` |
| Boundary, before | Market `closed_time` = cutoff − 1 / = cutoff | in before / not in before | N/A |
| Boundary, after | `first_entry_at` exactly at cutoff / one second before | in after / not in after | N/A |
| Straddler | bought before, resolved after | in neither part | N/A |
| Looks new | BUY after cutoff, `first_entry_at` before (0x729806: 20 tokens) | Market not in after part | N/A |
| Entered without a buy | `first_entry_at` after cutoff, only SPLIT/CONVERSION rows | in after part; builder leaves it out with its reason | N/A |
| Resolved before, entered after | `closed_time` < cutoff, a `first_entry_at` ≥ cutoff (real: 0x729806, 0xd218e4) | in neither part | N/A |
| Closed early | other token's CLOSED row with `last_event_at` < cutoff | Market stays in after part, same at every page size | N/A |
| Leak | everything after cutoff changed or removed: outcomes of later Markets, every fill and listed row dated after it, and Positions first entered after it in Markets resolved before it (after-part fixture) | before window identical | N/A |
| Cap after | more eligible rows than `limit` | earliest by `first_entry_at`, whole Markets, `capped` True; exactly `limit` and nothing more eligible → `capped` False | N/A |
| Row cap after | activity cap hit | chosen Markets unchanged; `activity_read_until` set; normal not-fully-read rule counts the rest | N/A |
| Bad lists | OPEN or CLOSED cut short / both empty | — | `PolymarketUnavailable` / `NoPolymarketHistory`, as the lookup |
| Bad args | side without cutoff, unknown side | — | `ValueError` |

</frozen-after-approval>

## Code Map

- `src/liquidoracle/data/window.py` -- `positions_near` (lookup path, the stop rule's `enough`, `_cap`, `_MarketBook.in_window/resolved_at`), `WINDOW_LIMIT`, `ACTIVITY_ROW_CAP`. Reuse `_cap`, `_MarketBook` and the activity filter (window Markets + CONVERSION rows naming their `neg_risk_id`). Add `cutoff_at` here.
- `src/liquidoracle/records.py:321` -- `Window`; `unread_positions` is unchanged.
- `tests/fixtures/cut_from_capture.py` -- `WALLETS` is keyed by wallet; restructure so 0x7298060b… can have a second fixture `after-part`: the Markets of its 41 tokens with a BUY at or after 2025-07-01 in `activity_after.json` (20 of them have an earlier `first_entry_at`), plus the 3 smallest (fewest activity rows, ties by id) Markets resolved on or after the cut-off whose listed rows all have `first_entry_at` ≥ the cut-off but that have no TRADE BUY after it (the capture has 352; they enter by CONVERSION), plus the smallest of the 3 Markets Gamma closed before the cut-off whose listed rows all start on or after it (E1), all with Gamma in the additions file. Keep all their listed rows and activity rows from both capture parts, and the CONVERSION rows naming their `negRiskMarketID`. Gamma comes from the frozen additions file (its `gamma` list of raw records, after `real_sample.checked`), cut with `_gamma`. The date comes from `data/window.cutoff_at(date(2025, 7, 1))`, never a hard-coded number.
- `tests/fake_polymarket.py` -- serves the new fixture as is; `page_size` sets small pages.
- `tests/test_window.py` -- existing patterns: `live(name)`, `calls_to`, `every_record`, `built_from`, the lookup's list-failure tests (around line 288) and `test_a_walk_stopped_with_exactly_the_limit_is_still_capped` (line 237).
- `tests/test_live_lookup.py:233` -- the empty-lists `NoPolymarketHistory` pattern.
- `src/liquidoracle/core/positions.build_positions` -- the one builder; do not change it.
- **KEEP from pass 1** (reverted; reference copy outside the repo: `C:\Users\Bruker\AppData\Local\Temp\claude\319f4ffc913fed5f\95b5b008-fb13-4835-b845-e18474d3f071\scratchpad\pass1\story-4-1-pass1.diff`): `cutoff_at`, the argument checks, `_resolved_part` with its `in_part` filter for the lookup and before part, `_cap` taking a sort key, `_rows_of`, the `Window` fields, the fixture script's `FIXTURES`/`FROM_ADDITIONS`/`_additions_gamma` shape, and the tests for conversion, bad arguments, both boundaries, the small-clean partition (4 before, 4 straddlers, 15 after, 23 in window), the leak test and offline = live parity. Do NOT bring back `until` on `activity_rows` (client, offline, live, browser stand-in) or its tests: the after part no longer needs a stop rule.

## Tasks & Acceptance

**Execution:** (the plan tasks are done by the orchestrator and committed; leave every other change uncommitted, and run git only read-only)
- [x] `_bmad-output/planning-artifacts/architecture/architecture-LiquidOracle-2026-10-21/ARCHITECTURE-SPINE.md` + `.memlog.md`, `epics.md` -- AD-7 and AD-10 after the review decisions -- plan before code.
- [x] `src/liquidoracle/records.py`, `src/liquidoracle/data/window.py` -- `cutoff_at`, the `Window` fields and docstring, the before and after parts -- AD-7, AD-8.
- [x] `tests/fixtures/cut_from_capture.py` + `tests/fixtures/capture/after-part.json` -- the new fixture; rerun `cut` and check the five old files are unchanged (`git status tests/fixtures/capture`).
- [x] `tests/test_window.py` -- every matrix row; the after part checked against a by-hand set with the CLOSED list in small pages (`page_size` 4) and fewer CLOSED requests than a full read; the after-part rank order checked over several `limit` values; both `capped` cases; both parts of `small-clean` through `build_positions` with reason counts (AD-11).

**Acceptance Criteria:**
- Given the after-part fixture, when its after window is built, then none of the 20 looks-new Markets is in it, and every other eligible Market is, including the 3 entered without a buy.
- Given a lookup (no cutoff), when the whole suite runs, then every existing test passes unchanged.

## Spec Change Log

- **Loop 1 (2026-11-25), intent_gap.**
  - **Trigger:** review pass 1 found B3/E2 (Markets entered after the cut-off with no BUY vanish uncounted; 352 on 0x729806) and B6/V3 (dropping CLOSED rows closed before the cut-off contradicts the frozen mixed-Market wording).
  - **Edvard's answers:** rank by `first_entry_at`, and a Position fully closed before the cut-off does not make its Market mixed, both on the AI's recommendation. The frozen Approach, the after-part rules and the matrix were renegotiated with him; spine AD-7/AD-10, epics.md and the memlog were changed first.
  - **Known-bad states avoided:**
    - Markets vanishing from the after part with no count.
    - An after part chosen from whatever activity was read, which made `capped` wrong both ways (B1, B2, E3, E4, V4) and lost eligible Markets on a row cap.
    - An unbounded activity read to today (B4).
    - A Market resolved before the cut-off but bought after it landing in both parts (E1; 3 each on 0x729806 and 0xd218e4).
  - **Also amended:** the untested list checks, CLOSED stop rule and rank order (V1, V2, V5), the fixture's hard-coded date (B5) and the `Window` docstring (B10).
  - **`until` dropped:** it is no longer needed, so it leaves the client protocol.
  - **KEEP:** see the Code Map's KEEP entry.
  - **Before approval, Edvard asked:** can a bet bought after the date reach the before part? It could: the loop-1 matrix put "resolved before, entered after" Markets in the before part, and the leak test only touched Markets resolved after the date, so it would not catch them. **His call (AI rec):** such Markets are in neither part. The before part's `in_part` therefore also needs every listed row of the Market first entered before the cut-off (pass 1's `in_part` did not), and the leak row and test now cover these Positions. He also asked to note, not change, that today's share count can only cause a share-gap exclusion in the before part.

## Review Triage Log

Pass 1 (2026-11-25): blind hunter (B), edge-case hunter (E), verification gap (V). Checked against the code and, where marked, the real capture (`scratchpad/probe_review.py`, no network).

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| B3 = E2 | A Market entered after the cut-off with no TRADE BUY (split, conversion) is in neither part, uncounted | medium | Capture: 0x729806 has 352 resolved Markets whose listed rows all start on/after 1 July 2025 with no BUY after it; the before part counts such Markets as left out, so AD-11's "same rules on both sides" breaks | intent_gap (frozen rule "has a BUY fill") |
| B1, B2, E3, E4, V4 | After-part `capped` wrong both ways; on an activity cap, eligible Markets not yet bought vanish uncounted | medium | `capped = stopped_early or …` is False when `ACTIVITY_ROW_CAP` ends the read before later eligible Markets' first BUYs, though `rows_of` lists them; True when a stop leaves nothing eligible unread. Root cause: the window is chosen from what activity was read | with B3 |
| B4 | After read has no `end`, so it reads every row to today | medium | `activity_rows(start=cut, …)` with no `end`; with fewer eligible Positions than `limit` it reads all later trading and can hit the cap needlessly; every eligible Market's `closed_time` is known before the read | with B3 |
| B6 = V3 | Dropping CLOSED rows with `last_event_at` before the cut-off contradicts the frozen mixed-Market wording, untested | medium | Mutation removing the filter leaves the suite green (V); a Market whose earlier token was fully closed before the cut-off stays in the after part, which the frozen decision words as "neither" | intent_gap |
| E1 | A Market Gamma closed before the cut-off, bought only on/after it, lands in both parts | high | Capture: 3 such Markets on 0x729806 and 3 on 0xd218e4; `rows_of` checks `in_window` but not `closed_time >= cut` | patch |
| B8 = V2 | After part's OPEN/CLOSED whole-list checks, `NoPolymarketHistory` and the no-eligible return untested | medium | Each of the three checks deleted in turn: suite green (V) | patch |
| V1 | After part's CLOSED stop rule `before_cut` never checked against an expected part | medium | `return True` and removing `until` both leave the suite green (V); only one test has several CLOSED pages and it compares offline to live | patch |
| V5 | First-BUY ranking (`min`) not pinned | low | `min` to `max` leaves the suite green (V) | patch |
| B5 | Fixture script hard-codes `CUTOFF = 1_751_328_000` | low | Second conversion of the date, against the spec's "only in `cutoff_at`" | patch |
| B7 = E6 | Offline docstring claims pages break where live ones do | low | Live `_walk` drops `is_combo` rows after a page arrives, so live pages can be shorter; results match only because the stop rule does not depend on page breaks | patch (docstring) |
| B10 | `Window` docstring says `capped` means "older" Positions | low | For the after part it is later Positions | patch |
| B14 | `from typing import Any` out of order in test_window.py | low | Direct correction | patch |
| E5 | First eligible Market bigger than `limit` empties the part | low | Needs `limit` < a Market's listed rows (at most 2 per Wallet); `WINDOW_LIMIT` is 2,000; fix adds a branch | reject |
| B9 | No reverse leak test for the after part | false | The after part must read pre-cut-off `first_entry_at` (AD-7); no leak direction is named | reject |
| B11 | `enough` re-sorts every page | false | At most 150 pages at the cap, each sorting at most a few thousand Markets | reject |
| B12 | `side` typed `str`, not `Literal` | false | Unknown sides are refused at run time and tested; no named harm | reject |
| B13 | Fixture script `sys.path` insert, unchecked 41/20 | false | Same pattern as the existing `fetch_gamma`; the 41/20 counts are asserted in test_window.py | reject |
| B15 | Sprint status and AI log lag the spec | false | Step 5 sets sprint status; the AI log is written at the session's end | reject |

Pass 2 (2026-11-25, after loop 1): blind hunter (B2), edge-case hunter (E2), verification gap (V2). Pass-1 rows are settled by loop 1's rebuild; none is carried.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| V2-1 | An OPEN row entered after the cut-off in a Market resolved before it can reach the before part with no test failing | medium | Removing `note(open_list.rows)` leaves the suite green; every late-row test puts the row on CLOSED; `>= cut` to `> cut` also survives | patch (test) |
| V2-2 | The before part's stop rule ignoring late-entered Markets is not pinned | medium | Removing `note(page)` in `enough` leaves the suite green; the reviewer's probe (page size 1, limit 1) empties the before part | patch (test) |
| B2-7 | The after part's CLOSED stop check only asserts "fewer pages than a full read" | low | A rule stopping one page late still passes; the exact stop page is computable from the fixture | patch (test) |
| B2-5 | The activity read and cap tail is copied in `_resolved_part` and `_after_part` | low | About 8 lines identical but for `start` and `side`; the two would drift; a private helper adds no public surface | patch |
| B2-1 | The module docstring states the mixed rule without the closed-early exception | low | Lines 10–15 say "whose Positions were all first entered on or after it"; the code counts only rows held at or touched after the cut-off | patch (docstring) |
| B2-2 | `Window.activity` docstring says "every activity row of those Markets" | low | The after part's read starts at the cut-off | patch (docstring) |
| B2-11 | `SAMPLE_DAY = date(2025, 7, 1)` repeats the Sample Dataset's date in the tests | low | The fixture script reads `real_sample.CUTOFF`; a change there would cut the fixture at another date than the tests assume | patch |
| B2-9 | `_closed_at` inserts into `sys.path` once per Market | low | Hundreds of duplicate entries during `cut`; one insert is enough | patch |
| B2-3 | Positions in neither part (straddlers, mixed, resolved before but entered after) are dropped with no count | false | In neither part by design (Glossary, AD-7; Edvard's decisions); AD-8 asks the `scan_whole` result to state this, not count it; loop 1's "vanishing" was about Markets that belong in the window | reject |
| B2-4 | One late-resolving chosen Market stretches the after read to its resolution | low | AD-7 reads every fill up to the latest resolution, as the lookup does; per-Market reads are out (no `/v2/activity?condition=`); the cap rule handles a long read | reject |
| B2-6 | The after part's by-hand oracle mirrors the code | low | The acceptance facts (20 looks-new out, 3 no-buy in) come from raw `first_entry_at` and BUY rows, independent of the code | reject |
| B2-8 | The fixture picks Markets with a stricter rule than the app | false | Only decides which real Markets go in the fixture; the tests then run the app's rule on them; no named harm | reject |
| B2-10 | `after-part.json` is about 2 MB | low | Real rows of a split-and-merge Wallet, cut by the same script and format as the other fixtures (byte-identical rule); trimming changes the spec's fixture rule | reject |
| B2-12 | `cutoff` is a `date` in `positions_near` but an `int` in `Window` | low | Passing the int back raises `TypeError` before any request (tested); epoch ints are the app's time type (spine Conventions) | reject |
| B2-13 | Untested: empty before part, `stored_markets`, a later Gamma batch | low | The full after read asks every batch (`test_the_after_part_asks_gamma_in_rank_order_only_until_it_is_full`); `stored_markets` goes through the unchanged `_MarketBook`; an empty before part is the lookup's tested empty path | reject |
| E2-1 | `first_entry_at > last_event_at` would break both stop rules | false | 0 of 139,661 positions rows in the capture; Story 2.2's online test showed TIMESTAMP sorts by `last_event_at` | reject |
| E2-2 | A CLOSED Position closed before the cut-off in an after-part Market is in neither part | false | Edvard's loop-1 decision, logged in AD-7 and the memlog | reject |
| E2-3 | A Cut-off Date before 1970 gives a negative epoch | low | Unreachable from the Scans page (Story 4.4 checks the date); fix adds a guard | reject |
| E2-4 | The fixture script's `r["side"]` could raise `KeyError` | false | The capture is frozen and `cut` ran on it; every TRADE row there has `side` | reject |
| E2-5 | One existing test was removed though the AC says all pass unchanged | low | The removed test checked the `NotImplementedError` placeholder this story replaces; the fix would edit this spec | reject |

## Design Notes

- **CLOSED stop rule is complete.** A Position first entered on or after the cut-off has `last_event_at` ≥ `first_entry_at` ≥ the cut-off, so every after-part row is read before the stop.
- **Fully closed rows can't make a Market mixed.** A CLOSED row fully closed before the cut-off is dropped before the mixed check, so whether its page was read cannot change the part.
- **The window is fixed before activity is read.** The after part is chosen from the lists and Gamma alone, so the activity read is bounded (`end` = latest `closed_time` among the chosen Markets). A cap there only marks Positions not fully read, the same rule as the lookup, and never changes which Markets are in the part.
- **Cost on a big live Wallet:**
  - The lists cost every Position touched since the cut-off. A Scan's before walk passes the same pages, which Story 4.3 can share.
  - Gamma is asked only in rank order until the part is full.
- **Real data:** `first_entry_at` equals the first BUY fill's second in 6,786 of 6,967 after-part Positions of the capture.

## Verification

**Commands:**
- `uv run pytest tests/test_window.py tests/test_real_sample.py tests/test_live_lookup.py -v` -- expected: all pass.
- `uv run pytest` -- expected: whole suite green (browser tests run locally with Chrome or Edge).
- `uv run python tests/fixtures/cut_from_capture.py cut` then `git status tests/fixtures/capture` -- expected: only `after-part.json` new.
