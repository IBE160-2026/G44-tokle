---
title: 'Story 4.7: The real Wallets around the Cut-off Date'
type: 'feature'
created: '2026-11-27'
status: 'done'
baseline_commit: '50f931b2385e6e77b312f6c8fd7a53af21280297'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The real Sample Wallets' files hold only their lookup window (latest 2,000 bets), and the offline funnel lists only the 3 synthetic anchor Markets, so an offline Scan never finds a real Wallet and could not read its before or after part; Story 5.2 needs the real Wallets' Hold-up result from an offline Scan (FR-12, AD-14).

**Approach:** `build-sample` also walks 8 real Wallets' before and after windows around 1 July 2025 with Story 4.1's `positions_near`, keeps what all three walks read, and replays all three from the written file; it also writes a real funnel file from the capture's own funnel list (the Markets the real Wallets were picked from), so the normal offline Scan finds the real Wallets as it found them on 21 October.

## Boundaries & Constraints

**Always:**
- **Measured before planning (2026-11-27):** 8 of the 10 real Wallets add almost nothing (their lookup window already covers both sides). 0xd218e4 and 0x63d43b do not: their capture holds activity only from 29 May / 9 May 2025, so their before part would read as wholly "not fully read" (an oldest-first read cannot skip the missing start), while holding both windows would add an estimated 30,000 to 85,000 list rows and as many Market records each (tens of MB, and a fetch of about 0xd218e4's whole CLOSED list, whose capture has a gap from February to November 2026).
- **Decision Q1 (Edvard, 2026-11-27, AI rec a): the heavy two are left out.** 0xd218e4 and 0x63d43b get no before/after windows and are in no real funnel row: they stay lookup-only Sample Wallets (files unchanged in what they replay). The other **8 real Wallets** get both windows and are in the offline Scan. README, epics 4.7 and 5.2 ("the 10 real Sample Wallets" → "the 8 real Sample Wallets in the Scan") and AD-14 say why. Rejected: both in full (60–130 MB, limit raised, big fetch); after part only (unused: they are in no Hold-up group). The 50 MB limit stays.
- **Decision Q2 (Edvard, 2026-11-27, AI rec a, HE ADDED the no-peeking check): real holder rows are copied from the capture.** `sample_data/real/funnel-markets.json`, written by `build-sample` from the capture's `sample/funnel_markets_20250701.json` and `sample/market_*.json`: every completely read funnel Market held by one of the 8, with its Gamma volume, and those Wallets' rows as Polymarket listed them (realised PnL, shares held, average price; token = the one whose final price equals the row's). Measured: 50 Markets, 65 rows; with the 3 anchors, 53, all inside the top 100. Offline holder lists = derived rows of synthetic files (as 4.6) + these stored rows; `holder_rows` stays TRADE-only, synthetic only. Rejected: deriving real rows from trades (wrong where activity was not fully captured).
- **No-peeking check (Edvard's condition on Q2):** the build stops (BuildError) unless every copied row's Market resolved before 1 July 2025, its final price is exactly 0 or 1, and the Wallet's capture has no TRADE, SPLIT, MERGE or CONVERSION row in that Market at or after the earlier of its resolution and the cut-off. Only redemptions may come later; they pay at the outcome known before the cut-off, so they add nothing a Scan on that date could not know (a row may read CLOSED where it read OPEN then, as a live Scan reads it today; the pre-filter's value is the same for a bet held to resolution, not exactly when part of it was sold before the date) (wording changed by Edvard, 2026-11-27, after review; Spec Change Log). Measured on the capture 2026-11-27: all 100 funnel Markets resolved before the cut-off, 0 late rows, prices only 0 and 1. A test plants a late trade and expects the build to stop.
- **Replay check:** every written file of the 8 must give the same lookup, before and after window as the full capture; otherwise nothing is kept (as Story 2.6). Same bytes on a re-run. `dataset.json` records the before/after windows' counts per Wallet and the two left out, with the reason.
- **Offline Scan:** finds the 8 real Wallets; the round-trip test (AD-14) and the FR-16 check still hold; the expected test counts change from 1,004 tested to 1,012.
- **Spec kept whole (Edvard, 2026-11-27, AI rec)** at about 2,000 tokens. Helpers for review only (Edvard, 2026-11-27, AI rec).
- Plan first: epics 4.7 and 5.2, FR-12 coverage line, epic-4 context, AD-14, PRD decision log, memlogs. README: offline Scan includes 8 real Wallets, the two left out and why.
- Read-only, network-blocked tests, each naming its FR or AD.

**Never:** no change to `positions_near`, the Scan, the store or the schema; no hand edits in `sample_data/`; no lucky streak or Hold-up Test (Epic 5); no Copy Test prices (Epic 6).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Build | capture zip + additions, `build-sample` | 8 real files with three windows each, the heavy two lookup-only, real funnel file, `dataset.json` counts | N/A |
| Replay differs | a written file gives another before/after window | build stops, `sample_data/real/` unchanged | BuildError naming the Wallet and side |
| Late row | a copied holder row's Market has a trade after the cut-off, or a final price not 0/1 | build stops, nothing kept | BuildError naming the Wallet and Market |
| Heavy two | 0xd218e4 or 0x63d43b in an offline Scan | not a candidate (no funnel row); lookup unchanged | N/A |
| Market record missing | a walk asks about a Market the additions lack | build stops: run `build-sample --fetch` (read-only, adds the records) | BuildError, as Story 2.6 |
| Offline Scan | sample loaded, Start Scan | real Wallets scanned; partly read ones flagged "not fully read" | N/A |
| Lookup | a real Wallet looked up offline | same Verdict as before this story | N/A |

</frozen-after-approval>

## Code Map

- `data/real_sample.py` -- `build`, `_written` (replay check: add before/after), `_trimmed` + `_Recorder` (record the rows and Markets of three walks; union = the deepest CLOSED prefix read, OPEN rows, every Market asked), `_cap_prefix` (lookup-only rule; keep), `_dataset`, `fetch_additions` (walk all three windows so `--fetch` adds missing Gamma records), `CUTOFF`, `PICK`.
- `data/window.py` -- `positions_near(client, wallet, cutoff, side)`, `cutoff_at`; unchanged.
- `data/offline.py` -- `OfflineClient(funnel=)` takes one path: accept the real funnel file too; `_volumes`, `_holders` (stored real rows + derived synthetic rows, oldest first), `sample_funnel`, `NOT_WALLET_FILES` (same file name in `real/`), `holder_rows` docstring.
- `data/sample_json.py` -- `write_funnel`/`read_funnel` (strict): extend or add a real-funnel reader/writer with holder rows.
- `__main__.py` -- `open_sources` passes the funnel path(s); `build_sample`.
- `sample_data/real/*` -- regenerated by the script only.
- Capture row layout (`spike/sample_pick.py:122`): `[wallet, status, realized_pnl, current_size, cur_price, avg_price]`, no token id.
- Tests: `tests/test_real_sample.py` (build, replay, re-run identical), `tests/test_offline.py` (funnel merge, holder rows, offline Scan counts, 50 MB test at line 236), `tests/test_scans_page.py`/`test_watchlist.py` if counts are asserted.

## Tasks & Acceptance

**Execution:**
- [x] Plan: `epics.md`, `epic-4-context.md`, AD-14, PRD decision log, memlogs -- decisions before code.
- [x] `data/real_sample.py`, `data/sample_json.py` -- three-window trim + replay, real funnel file -- FR-12, AD-14.
- [x] `data/offline.py`, `__main__.py` -- offline funnel and holders include the real Wallets -- AD-14, AD-21.
- [x] Run `build-sample` on the capture zip (and `--fetch` only if a record is missing); commit `sample_data/real/`.
- [x] `README.md` -- offline Scan line and the real Wallets' limits.
- [x] Tests: build replay per side (planted mismatch stops it), no-peeking check (planted late trade and price 0.5 stop it), re-run identical, real funnel rows, offline Scan finds the 8 and not the heavy two, every matrix row.

**Acceptance Criteria:**
- Given the capture zip, when `build-sample` runs twice, then `sample_data/real/` is byte-identical and the Sample Dataset stays under 50 MB.
- Given Offline Mode with the sample loaded, when a Scan with the default date finishes, then 1,012 Wallets are tested (the 8 real among them) and the Watchlist still lists the four Synthetic Wallets, with sockets blocked.
- Given the whole suite with `CI=true`, then every test passes, 0 skipped.

## Implementation Notes

- Built in this session without a helper (Edvard chose helpers for review only). Plan edits first: PRD decision log, epics 4.7 (new AC and settled open items), the stage 2 minimum and Story 5.2 (8 real Wallets), `prd.md` §6.1 2b, AD-14, epic-4 context, PRD and architecture memlogs. The UX documents are untouched (no page changes).
- `data/real_sample.py`: `LOOKUP_ONLY` (the two, with reasons), `SIDES`, `sides_of`, `FUNNEL_LIST`/`MARKET_LIST`/`FUNNEL_FILE`, `HOLDING_TYPES`. `_trimmed` walks each side with a `_Recorder` and keeps rows by the identity of the full capture's row objects: lookup = the old rule (cap-prefix OPEN rows), before/after = every row read; rows keep the read order, so lookup-only files come out byte-identical (0xd218e4 and 0x63d43b, and also 0xcf0d7f, 0x091596 and 0x29306d, whose lookup window already covered both parts). `activity_until` = the earliest second any read was cut short in (the replay check guards it). `_written` replays every side, naming it on failure; `Built.parts` and `dataset.json` `parts`/`lookup_only`. `real_funnel` + `_holder` (token = the one with the row's final price; the no-peeking check; the token must be on the Wallet's lists; every listed Market must be in a written file). `fetch_additions` walks the same sides.
- `data/sample_json.py`: `FunnelFile`; `write_funnel(path, volumes, holders=None)` (no `holders` key for the synthetic list, so its bytes are unchanged); `read_funnel` returns `FunnelFile`, strict, refusing holder rows for an unlisted Market.
- `data/offline.py`: `funnels=` (a sequence) and `sample_funnels(root)` (synthetic, real); `_funnel()` merges the lists and refuses a Market on both; `_holders` = stored rows first, then rows derived from synthetic files only (`_is_real`, shared with `real_addresses`).
- Build on the capture (2026-11-27, 16 s, no network): every replay identical, no Market record missing (no `--fetch` needed), no-peeking check clean: 50 Markets, 65 rows. Real files 40.6 MB (35.6 before), Sample Dataset 41 MB; a second run byte-identical. Parts: 0xcf0d7f 177/6, 0x736483 1,236/13, 0xd3a6e5 654/423, 0x94884d 2,000/16, 0x729806 907/408, 0x0f4b0a 112/118, 0x091596 40/22, 0x29306d 11/12.
- Side effect: 0x0f4b0a's file now also holds 9 OPEN rows in unresolved Markets (the before/after walks read the whole OPEN list). The independent Real PnL script (Story 2.7) reads every row, so its CSV lists them as left out (21 to 30); resolved 210, fees $0.53 and Real PnL -$188.77 are unchanged. The CSV was regenerated by the script, not edited. Lookup Verdicts of all 10 are unchanged (`RECORDED` test).
- Real app check (2026-11-27): `load-sample` 1,018 Wallets (25 s); an offline Scan started through `ScansPage` and run by the `Worker` finished in about 64 s: "Scan of 1,012 Wallets", 53 of 53 Markets used, the 8 real candidates and not the heavy two, 10 on the Watchlist (the four and 6 coin-flippers, no real Wallet), only 0x729806 not fully read. Before-part Verdicts: 0xcf0d7f Likely skilled; 0x0f4b0a, 0x736483, 0x94884d, 0xd3a6e5 No evidence of skill; 0x091596, 0x29306d, 0x729806 Not enough data. So Epic 5's README result will have no real Passer and 5 real Wallets in the Comparison Group. The Scan list still says 1,018 (the four small Synthetic Wallets with no anchor bets and the heavy two are counted in N), against "Scan of 1,012".
- Tests: `test_real_sample.py` +13 (both parts replayed, a planted wrong part per side, lookup-only Wallet, the copied rows, late redemption allowed, five no-peeking stops, fetch walks the parts, missing funnel list / Market in no file); test ids now differ in their first 18 characters (the capture names Market lists by them; the first version of the copy test passed nothing because the test zip overwrote one list with another). `test_offline.py` +7 (stored real holder lists, committed rows checked for peeking, the offline Scan over the committed files finds the 8 and not the two, a Market on two lists, strict reading). Five planted bugs (no late-row check, late counted from the cut-off only, real rows derived too, parts not walked, token from the wrong price) each fail a test.
- Real Wallets' Scan Verdict pages (review BH7), by URL on a Scan of the committed files: 0xcf0d7f "Likely skilled", the two-window line, "Computed on 183 bets around the Cut-off Date 1 July 2025 · Seed 44", the back link; 0x729806 "Not enough data" with the "Not fully read" tag. Both 200.
- Review pass 1 patches (2026-11-27): the no-peeking check now also matches conversions by the event id, combo trades, a capture that did not read from `late` on, and the funnel's own close time; a shared list name stops the build; `dataset.json` records the real volume list; docstrings corrected; 9 tests added (7 no-peeking cases, the list name, the `open_sources` wiring) and the Scan count asserted. The build still passes on the capture, byte-identical twice. Five planted gaps each fail a test.
- AI slips: the long bash heredoc for the review patches broke again (switched to Write + run file); a first full-suite run used a pytest flag this project does not have (`-n 0`) and did not run; the "token not held" test case first hit the resolution check instead; the check script for the real Scan used a wrong field name.

## Spec Change Log

- **2026-11-27, after review pass 1 (Edvard changed the frozen intent).** Trigger: review findings BH2 and EC11 showed that the no-peeking bullet's "so the pre-filter's value is the same as at the cut-off" overstates the point: a redemption after the cut-off turns an OPEN row into a CLOSED one, and AD-21's pre-filter then counts any shares sold before the date, which it would not have counted on the OPEN row. Amended: that sentence only, now "they add nothing a Scan on that date could not know", with the exact limit stated. Edvard approved the change ("go ahead n fix that sentence in the spec, im ok with it, just note the change in the change log"). Known-bad state avoided: the plan claiming an equality the data does not guarantee. KEEP: the rule itself is unchanged (only redemptions may come after the earlier of resolution and the cut-off). Review pass 1 also tightened the check in code (conversions matched by the event id, combo trades, a capture that did not read from then on, the funnel's own close time), recorded in the triage log; those extend the rule's intent and needed no change here.

## Review Triage Log

Pass 1 (2026-11-27): three reviewers (blind, edge case, verification gap), 31 findings (with the gap reviewer's two other findings); 0 intent gaps, 0 bad spec, 19 patched in 12 fixes, 1 deferred, the rest rejected or false. The real capture was checked for every claimed leak before patching: 47 of the 50 funnel Markets are neg-risk, none has a late conversion in its event, there are no late combo rows, and every holder's capture covers the time after the cut-off; the stricter check still passes on it.

| # | Finding | Verdict | Evidence / route |
|---|---------|---------|------------------|
| VG1 / VG-o1 | A CONVERSION row carries the neg-risk event's id, not the Market's, so the late-row check could never match one; no test planted a late split, merge or conversion | medium | Confirmed (`records.py` ActivityRow, `window._rows_of`). **patch**: the check matches the Market id and its `neg_risk_id`; cases for a late SPLIT, MERGE and CONVERSION (by event id). Planted back: fails. |
| EC2 | Combo rows are dropped when activity is parsed, so a late combo trade escapes the check | medium | Confirmed (`parse_activity_row` returns None for `is_combo`). **patch**: `Captured.combos` keeps each combo row's Market and time; a late one stops the build; test case. Planted back: fails. |
| BH1 / EC1 | The check only sees what the capture read; a cut-short activity read passes silently | medium | Confirmed for a future capture (none of the 8 is cut short after `late`). **patch**: the build stops unless the capture read activity from `late` on (`activity_until` unset, `activity_from` not later); test case. Planted back: fails. |
| BH4 / VG2 | The resolution check's Gamma side (closed on/after the cut-off, not resolved) and the 0/1 price half are untested | low | Confirmed. **patch**: cases for a Gamma record closed at the cut-off and one never resolved. Planted (Gamma side dropped): 2 fail. |
| EC3 | `late` ignores the funnel list's `closedTime` when it is earlier than Gamma's | low | Real, a direct correction. **patch**: `late = min(Gamma close, funnel close, cut-off)`. |
| BH3 / EC8 / VG3 | `test_ad21_committed_real_rows_hold_nothing_from_after_the_cutoff` cannot see late rows (the committed files keep only window activity) and does not check the 0/1 price | low | Confirmed. **patch**: docstring says it re-checks only the kept rows (the build's check on the whole capture is the guard); asserts each token's final price is 0 or 1. |
| BH5 / EC10 | No test pins the tested count (1,012) | low | Confirmed. **patch**: the committed-files Scan test asserts "Scan of 12 Wallets" (8 real + the four); 1,012 with the coin-flippers was checked by hand (Implementation Notes). |
| VG-o2 / BH12 | `open_sources` passing both volume lists is untested; a missing real list would silently drop the real Wallets | low | Wiring confirmed untested. **patch**: `test_ad13_offline_sources_read_both_volume_lists` (53 Markets through `open_sources`). Logging a missing file: rejected (same rule as the synthetic list; the test guards the wiring). |
| BH9 | Two funnel Markets sharing the first 18 characters would silently get the same list | low | Real for another capture (the test-zip slip showed it is silent). **patch**: the build stops on a shared list name; test. Planted back: fails. |
| BH8 | `dataset.json` says nothing about the real volume list; `neg_risk_markets` 7,376 -> 7,542 unexplained | low | **patch**: `dataset.json` `funnel` (source, file, 50 Markets, 65 rows). The neg-risk count rose because the files now keep the before/after parts' Market records (noted here). |
| BH14 | `market_holders` docstring still says oldest first | low | **patch**: stored real rows keep Polymarket's list order (no last-event time stored), derived rows follow oldest first. |
| BH2 / EC11 | "The row's numbers are what they were at the Cut-off Date" is not exact: a later redemption turns OPEN into CLOSED, and AD-21's pre-filter can then count partial sells it would not have counted | low | True; no information from after the cut-off enters (the outcome was known), and a live Scan today reads the same post-redemption rows. **patch**: `_holder` docstring corrected. The frozen spec's "the pre-filter's value is the same as at the cut-off" carried the same overstatement: reported to Edvard, who had it corrected (Spec Change Log). |
| BH6 | The Scan list says 1,018 while the Watchlist says "Scan of 1,012" | low | Pre-existing since Story 4.6 (1,018 vs 1,004; N = every Sample Wallet, frozen there); **defer**. |
| BH7 | The planned manual check "open a real Wallet's Scan Verdict" cannot be reached from the Watchlist (no real Wallet on it) | low | True; the fix would edit the spec, rejected. Checked by URL instead (Implementation Notes): both pages open. |
| BH10 / EC9 | A held funnel Market with no Gamma record stops the build, and `--fetch` would not add it | low | True in principle; cannot happen with this capture (all 50 found) and the fix adds fetch code; rejected. |
| BH11 | `_funnel()` rereads both volume lists on every call | low | Small files, about 54 reads in a minute-long Scan; a duplicate already raises; rejected. |
| BH13 | Kept OPEN rows in unresolved Markets; the reference CSV calls them "sources disagree" | low | The Story 2.7 script is independent by design and its reason is its own; Real PnL unchanged (Implementation Notes); rejected. |
| BH15 | Spec says in-review while sprint status says in-progress; no full-suite result recorded | false | The sprint status moves at presentation (step 5); the result is recorded in Verification. |
| EC4 | A malformed funnel entry gives a raw traceback | low | The capture is checked against its SHA-256 before use; rejected. |
| EC5 | A Market with several outcomes at price 0 would pick the first token | low | Funnel Markets are binary (`Market.resolved` needs {0, 1}; every neg-risk Market is Yes/No, `dataset.json` neg-risk check); rejected. |
| EC6 | No check that a listed Market is inside the 90-day window | low | The list is the capture's own funnel, built with that window; rejected. |
| EC7 | The written volume list is never read back | low | One serializer, strict reader tested; rejected. |

## Design Notes

- The capture's funnel list is the real Scan funnel of 21 October (AD-21's rule, Gamma volumes), so listing those Markets offline reproduces how the real Wallets were found, without inventing volumes or anchor bets for real Wallets.

## Verification

**Commands:**
- `uv run liquidoracle build-sample ../G44-tokle-data/sample-capture-cutoff-2025-07-01.zip` twice -- expected: no git diff the second time.
- `uv run pytest` with `CI=true` -- expected: all pass, 0 skipped.
- Result (2026-11-27, after review pass 1): 1,577 passed, 0 skipped, 3 deselected, 270 s; `build-sample` twice: byte-identical, Sample Dataset 41 MB.
- Result (2026-11-27, before review): 1,568 passed, 0 skipped, 3 deselected (the `online` tests), 273 s.

**Manual checks:**
- `load-sample`, `run --offline`, start a Scan: the Watchlist header counts the real Wallets; open a real Wallet's Scan Verdict.
