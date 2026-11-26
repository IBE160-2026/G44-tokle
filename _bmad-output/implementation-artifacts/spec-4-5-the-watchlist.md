---
title: 'Story 4.5: The Watchlist'
type: 'feature'
created: '2026-11-26'
status: 'done'
baseline_commit: '6f33357db9de0fa6944a2212681743f6fe542a0b'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A finished Scan stores its results (Story 4.3) and the Scans page lists it (4.4), but the user cannot see which Wallets passed, how strong the evidence is, or how many would pass by luck alone (FR-16, UX-DR33, UX-DR34, UX-DR37, AD-21, AD-22).

**Approach:** A server-rendered Watchlist page per finished Scan at `/scans/<id>/watchlist`, linked from the Scan list's Watchlist size, and a Verdict page opened from it that shows that Scan's own `scan_whole` result, recomputed from its frozen snapshots, with a back link.

## Boundaries & Constraints

**Always:**
- **Scan header** (UX-DR33): eyebrow "WALLET SCAN", `h1` "Scan of N Wallets", lede "Cut-off Date 1 July 2025 · run 26 Nov 2026", second line "Markets resolved in the 90 days before the Cut-off Date, top 100 by volume · 97 of 100 Markets used · Seed 44" (90/100 from `services/scan` constants, "of M" = the Scan's stored Market set), and the Scan summary card: Wallets scanned, rated *Skilled (high confidence)*, Scan run date. When any Market is "partial", a `<details>` disclosure under the lede lists them as "not used: partial"; none, no disclosure. **Decision (Edvard, 2026-11-26, AI rec 4a):** each partial Market is named by its short condition ID, volume and resolution date; no schema change. Rejected: storing Gamma's question text (schema v7) for a rare case.
- **Shortlist line (Edvard, 2026-11-26, AI rec 3a):** a third header line "Shortlist of about 600 by a quick profit estimate · 4 Wallets not fully read" (shortlist = the stored shortlist length; not fully read = flagged Wallets among the Scan's top N), so the page states what AD-21 and FR-16 promise. Rejected: dropping them from AD-21 and the PRD.
- **Scan tabs:** `<nav aria-label="Scan">` with links; only *Watchlist* exists now, marked `aria-current="page"`. Not an ARIA tab list.
- **Info box** above the table: the Minimum Luck Passes sentence from `core/phrases`: "At least about 2 of the 200 Wallets with a Verdict would pass by luck alone, probably more, because these Wallets were picked for high profit." = Wallets tested × 0.01 as a whole number, halves up ("about 2 of the 150 Wallets with a Verdict") (AD-25). **Decision D (Edvard, 2026-11-26, after review: "make the small numbers read like a person would say it"; the AI chose the wording):** below 100 Wallets with a Verdict, "About 1 in 100 Wallets would pass by luck alone, probably more, because these Wallets were picked for high profit. With only 37 Wallets with a Verdict, even one passing could be luck." Rejected: "0.4 of the 37" (the earlier one-decimal rule). **Decision (Edvard, 2026-11-26, AI rec 7a):** "with a Verdict" is added so a number different from the heading explains itself. Rejected: the plan's sentence word for word. **Decision (Edvard, 2026-11-26, changed the AI rec 2a to 2b):** "Wallets tested" counts only Wallets whose `scan_whole` result has a Verdict (a p-value); *Not enough data* cannot pass, so it is left out. "Scan of N Wallets" and "Wallets scanned" still count every Wallet the Scan tested. Rejected: counting *Not enough data* too (AI rec; matched the PRD check's "2 of 200" literally).
- **Table** "Wallets rated Skilled (high confidence)" in a card and a focusable named scroll area: Wallet (short address, monospace, in-app link named "Open Verdict for Wallet 0x1a2b…9f0e", no external-link icon), Verdict pill (small: dots + Verdict), Odds (`phrases.odds`, header "Odds (with no edge)"), Resolved bets, Real PnL (monospace, right-aligned). Rows = `scan_whole` results with Verdict *Skilled (high confidence)*, sorted by p-value, then larger Real PnL, then address. No rank column. Caption: "Sorted by p-value, smallest first. A smaller p-value means stronger evidence of skill, not a bigger edge." A flagged Wallet carries the info tag "Not fully read" in its Wallet cell, with the tooltip "Polymarket's data for this Wallet could not be read in full; the unread bets are left out." shown on hover and keyboard focus, hoverable, Esc hides it (WCAG 1.4.13); the sentence is in the page without JS. Whole row hover; the address is the row's one link.
- **Decision C (Edvard, 2026-11-26, review loop 1, AI rec a):** when no Wallet of the Scan got a Verdict, the info box is left out (the empty-Watchlist sentence already says nobody passed). Rejected: "0.0 of the 0 Wallets".
- **Empty Watchlist** (valid, SM-C2): "No Wallet in this Scan was rated *Skilled (high confidence)*." in place of the table; info box still shown.
- **Scan list link:** a finished Scan's Watchlist size (also 0) becomes a link to its Watchlist, named with its Cut-off Date so each is unique ("3 Wallets on the Watchlist (Cut-off Date 1 July 2025)" style, visible number included).
- **Verdict from a Scan** at `/scans/<id>/wallet/<address>`: the full Verdict page (card, chart, honesty notes) from the Scan's frozen before and after snapshots with `as_of = scan.as_of` and the Scan's Seed, through the same builder `services/scan.scan_results` uses, so its Verdict, p-value, bets and Real PnL equal the stored row (AD-22). Above the eyebrow "← Back to Watchlist (Cut-off Date 1 July 2025)". "Data stored" = the later part's completion time. **Decision (Edvard, 2026-11-26, AI rec 1a):** the honesty notes always show, for a Scan result, the window line "Based on two windows around the Cut-off Date: up to the latest 2,000 bets resolved before it and up to the first 2,000 bought after it. Bets bought before the date and resolved after it are in neither." and the last line "Computed on 1,234 bets around the Cut-off Date 1 July 2025 · Seed 44" (the tested-set size as lookups count it). Rejected: only when a part was capped. **Decision A (Edvard, 2026-11-26, review loop 1, AI rec a):** when the after part could not be read (Polymarket refused it: a before part but no after part) the line is "Based on the latest 2,000 bets resolved before the Cut-off Date; the bets bought after it could not be read."; when nothing was read (no part), there is no window line. Rejected: the two-window line always.
- **Decision B (Edvard, 2026-11-26, review loop 1, AI rec a):** a Verdict from a Scan whose stored `scan_whole` row is flagged not fully read shows the info tag "Not fully read" with its tooltip (the same words and behaviour as on the Watchlist) beside the stats, so a Wallet-level flag (a refused part) is never lost. Rejected: nothing on the Verdict page.
- **Spec kept whole (Edvard, 2026-11-26, AI rec)** at about 2,400 tokens: one goal. Helpers for review only.
- **Titles:** "Watchlist · 1 Jul 2025 · LiquidOracle"; the Verdict keeps "Verdict · 0x7c3a…d3f5 · LiquidOracle".
- **Not found** (404, the usual page): an unknown Scan, a Scan not finished (unfinished results are never shown), an address with no `scan_whole` result in that Scan, a malformed address, or a frozen snapshot that is missing.
- Read-only: these pages read the store only; no request leaves the app and nothing is written. Cut-off text via `phrases.long_date(window.cutoff_day(scan.cutoff))`, never `fromtimestamp` on a cut-off. Words and numbers from `core/phrases` or the new service; templates only place them. Existing tokens, interaction states, 900/640/400 px breakpoints, forced colours, reduced motion. Tests network-blocked, each naming its FR, UX-DR or AD.

**Never:** no Hold-up Test or Copy Test tab (Epics 5–6), no offline Scan (4.6), no change to how a Scan runs or what it stores, no schema change, no change to lookup Verdict pages beyond what sharing the builders needs.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Watchlist | finished Scan, 3 Skilled of 200 | header, info box "about 2 of the 200 Wallets with a Verdict", 3 rows by p-value | N/A |
| Empty | finished, none Skilled | empty sentence, info box, no table | N/A |
| Small Scan | 150 with a Verdict | "At least about 2 of the 150 Wallets with a Verdict …" | N/A |
| Tiny Scan | 37 with a Verdict | "About 1 in 100 Wallets would pass … With only 37 Wallets with a Verdict, even one passing could be luck." | N/A |
| Thin Wallets | 200 in the Scan, 13 *Not enough data* | "Scan of 200 Wallets"; sentence counts 187 | N/A |
| Partial Markets | 3 of 100 partial | "97 of 100 Markets used", disclosure lists 3 | N/A |
| Unfinished | running/stopped Scan | 404; Scan list shows "—", no link | N/A |
| Flagged Wallet | `not_fully_read` row | "Not fully read" tag with tooltip | N/A |
| Verdict from Scan | Watchlist row link | same Verdict/odds/bets/PnL as the row, back link | missing snapshot → 404 |
| Wrong Wallet | address not in that Scan | 404 | N/A |
| After part refused | before part, no after part, row flagged | one-window line; "Not fully read" tag beside the stats | N/A |
| Nothing read | no part | *Not enough data*, no window line | N/A |
| None with a Verdict | every Wallet *Not enough data* | no info box; empty sentence | N/A |

</frozen-after-approval>

## Code Map

- `services/scans_page.py` -- page-service pattern to copy; `ScanRow.watchlist`, `_row` (add the Watchlist URL/label); `status_text`, `_open`.
- `services/scan.py:346 scan_results`, `as_of_part` -- the Scan's Skill Test; factor out the `scan_whole` Position set so the Verdict page reuses it unchanged. `MARKET_DAYS`, `MARKET_COUNT`.
- `services/fetch.py` -- `StoredResult` (result, stored_at, positions, capped, listed); `result_of` pattern.
- `services/lookup.py` -- `_verdict` builds `VerdictCard`/`WalletPage`; reuse it (make the card builder callable for a Scan result), `short_address`, `FILLED_DOTS`.
- `services/honesty.py` -- `honesty_notes(stored)`; window/computed_on lines vary by scope.
- `core/phrases.py` -- `odds`, `money`, `count`, `long_date`, `run_date`, `window_line`, `computed_on` (raises for non-`lookup` scope today: extend); add the Minimum Luck Passes phrase and a short date ("1 Jul 2025").
- `data/store.py` -- `scan`, `scan_markets` (state "partial"), `scan_wallets` (shortlist length, `not_fully_read`), `scan_results` (scope `SCAN_WHOLE`), `snapshot(fetch_id)`; `ScanStep.DONE` = finished. No SQL elsewhere; add a read method only if needed.
- `data/window.py` -- `cutoff_day`.
- `web/__init__.py` -- add `GET /scans/<int:id>/watchlist`, `GET /scans/<int:id>/wallet/<path:raw>` (lower-case redirect like `/wallet`); 404 handler.
- `web/templates/verdict.html` -- add the optional back link above the eyebrow; `scans.html` -- link the Watchlist cell; new `watchlist.html`.
- `web/static/css/app.css` -- `.info-tag`, `.table-scroll`, `.scan-table`, `.info-box`, tokens; add header/summary card, tabs, pill, tooltip styles.
- `tests/test_scans_page.py`, `tests/test_web.py` (`every_page` checks), `tests/browser/` -- patterns; store fixtures with finished Scans.

## Tasks & Acceptance

**Execution:**
- [x] `epics.md` (4.5, UX-DR33/34/37), `EXPERIENCE.md`, `ARCHITECTURE-SPINE.md` AD-8/AD-21, `prd.md` FR-11 (Scan window words), FR-16 (shortlist line; "Wallets tested" = with a Verdict, check example and sentence reworded) and Glossary, `epic-4-context.md`, `deferred-work.md` (resolve the 3.3 two-window item), memlogs -- plan before code.
- [x] `core/phrases.py` -- Minimum Luck Passes, short date, Scan window and computed-on lines -- FR-11, FR-16, AD-25.
- [x] `services/scan.py` -- shared `scan_whole` Position set -- AD-22.
- [x] `services/watchlist.py` (new) -- Watchlist view and Verdict-from-Scan page -- FR-16, UX-DR33, UX-DR34, UX-DR37.
- [x] `services/honesty.py`, `services/lookup.py`, `services/scans_page.py` -- scope-aware lines, reusable card builder, Watchlist link.
- [x] `web/__init__.py`, `templates/watchlist.html` (new), `verdict.html`, `scans.html`, `static/css/app.css`, small script for the tooltip's Esc if needed -- the pages.
- [x] `tests/test_phrases.py`, `tests/test_watchlist.py` (new), `tests/test_scans_page.py`, `tests/test_web.py`, `tests/browser/` -- every matrix row, Verdict-from-Scan equals the stored row, frame/heading/label checks, tooltip by hover, focus and Esc.

**Acceptance Criteria:**
- Given a finished Scan, when its Watchlist and a row's Verdict page open, then both show the same Verdict, odds, resolved bets and Real PnL, and the back link returns to the Watchlist.
- Given the pages without JavaScript, then every word and link works, and the tag's sentence is in the page.
- Given the whole suite, when it runs network-blocked with `CI=true`, then every test passes, 0 skipped.

## Implementation Notes

- Built in this session without a helper (Edvard chose helpers for review only). Files: `core/phrases.py` (`luck_passes`, `short_date`, `SCAN_WINDOW_LINE`, `computed_on` for `scan_whole` with `cutoff`), `services/scan.py` (`parts_position_set`, shared by `scan_results` and the page), `services/fetch.py` (`StoredResult.cutoff`), `services/honesty.py` (scope-aware window line), `services/lookup.py` (`verdict_page` as a module function), `services/watchlist.py` (new: `Watchlists.view`, `.verdict`, `scan_whole_result`, `watchlist_label`), `services/scans_page.py` (`ScanRow.watchlist_label`), `web/__init__.py` (two routes), templates `watchlist.html` (new), `verdict.html` (back link; "Scan wallets" marked `aria-current="true"` when opened from a Scan), `scans.html` (link), `app.css`, `static/js/tag-tip.js` (new), README (sixth script).
- Choices the spec left open: the Watchlist and a Verdict from a Scan mark *Scan wallets* with `aria-current="true"` (a section, not the page; the nav style now matches any `aria-current`). "1.0 of the 100" keeps its decimal (the rule says one decimal under 2). The population line's words are one constant `POPULATION`, and `test_wording.py` allows exactly "top {markets} by volume" (AD-21's factual definition, like "top Wallets by profit").
- Found while building: the 900 px stacking rule sat before the base `.scan-head` rule, so it never applied (summary card beside the title, 24 px sideways scroll at 320 px), caught by the new browser test and moved after it; the table caption scrolled away inside the table's box at 400 px and the absolutely placed tooltip was clipped by that box (screenshots), so the caption is a `<p>` tied by `aria-describedby` and the tooltip opens in the row's flow, with the Wallet column given room for it so no column moves; an odds phrase in a code comment tripped the AD-25 guard; hover rules needed `:focus-visible` twins (UX-DR9 test), so the row highlight uses `tr:has(.row-link:hover)`.
- Found by the second full run: `tag-tip.js` cleared Esc's dismissal on `focusout` after a 0 ms timer, which raced the focus move in Chrome, so Tab back to the tag sometimes left it hidden; it now clears on `focusin` and `pointerover` of the tag (8 browser tests passed 3 runs in a row). `test_progress_script.py::test_ux_dr22_live_lookup_swaps_in_the_verdict` (Story 3.5) failed once under the full run's load and passed 3 times alone.
- Review pass 1 sent the story back to Edvard (two intent gaps); the code was reverted to the baseline and the pass-1 code kept in the session's scratchpad to re-derive from.
- Tests: `tests/test_watchlist.py` (21), `tests/browser/test_watchlist_page.py` (8), phrase and honesty tests, three pages added to `test_web.py`'s every-page checks. Full suite with `CI=true`: see Verification.
- Re-derived after review loop 1 (2026-11-26) from the kept pass-1 code: `phrases.SCAN_BEFORE_ONLY_LINE`; `StoredResult.sides` (the parts read) so `honesty._window` names both windows, the before window alone, or none (Decision A); `ScanVerdict.tag` and the tag beside the stats in `verdict.html`, with `tag-tip.js` loaded only then (Decision B); `WatchlistView.luck` empty and no info box when no Wallet got a Verdict (Decision C). Patches: `.info-tag:focus + .tooltip` for a tap (EC6), `hand_scan` closes its connection (EC7), README stage 2 paragraph (BH11), import order (BH14a), DESIGN.md Scan header and Info tag, EXPERIENCE.md UJ-4 date (BH9, BH10), and tests for the capped count (VG1) and "Data stored" (VG2). Six planted bugs (window always two, luck sentence for 0, `cut` -> `parts`, `max` -> `min`, tag never shown, no `:focus` rule) each fail a test; `max` -> `min` first slipped through (both fake parts complete in the same second), so a test with two different times was added.
- Review pass 2 patches (2026-11-26): the tag is a `<button type="button">`; `tag-tip.js` loads only with a flagged row; `verdict_page` builds `WalletPage` itself; `hand_scan` takes a Seed; a Skilled Wallet under Seed 7 proves row and page agree (planted `seed=44` fails it); plan sentences reordered (AD-8, EXPERIENCE, epics FR-11), PRD FR-16 checks added, decision-log paragraph moved.
- After the review (2026-11-26), Decision D: `phrases.luck_passes` gives a whole number from 100 Wallets with a Verdict and the rate sentence below 100; tests in `test_phrases.py` (no decimal below 100) and `test_watchlist.py`.

## Spec Change Log

- Review loop 1 (2026-11-26): findings BH2/EC3 (two-window line without an after part) and EC4 (Wallet-level flag lost on the Verdict) were intent gaps; Edvard answered A a, B a, C a (C: BH8's "0.0 of the 0"), written into the frozen block as Decisions A to C. Known-bad state avoided: an honesty note describing data never read, and a Watchlist flag that vanishes on the page it opens. KEEP from pass 1 (in the scratchpad copy): `parts_position_set` shared with `scan_results`; `verdict_page` as a module function; `Watchlists` read-only with `scan_whole_result`; the in-flow tooltip with the Wallet column's room for it; `tag-tip.js` re-arming on `focusin`/`pointerover`; the 900 px `.scan-head` rule after its base rule; the caption as a `<p>` tied by `aria-describedby`; `POPULATION` and the wording-test allowance. Patches carried: VG1, VG2, EC6, EC7, BH9, BH10, BH11, BH14a.

## Review Triage Log

Pass 1 (2026-11-26): three reviewers (blind, edge case, verification gap), 27 findings; 2 intent gaps (loopback to Edvard), 9 patches carried into the re-derivation, 16 rejected, 0 deferred.

| # | Finding | Verdict | Evidence / route |
|---|---------|---------|------------------|
| BH2 / EC3 | The two-window line claims an after window when the after part was refused or nothing was read | medium | `_window` returns `SCAN_WINDOW_LINE` for every `scan_whole`; `scan_results` stores a result with `after_fetch_id` None when `refused_after` or before is None. The "always" decision did not cover a missing part: **intent_gap**. |
| EC4 | A Wallet flagged at Wallet level (refused after part, refused ranking) shows "Not fully read" on its row but nothing on its Verdict | medium | The row's flag comes from `wallet.not_fully_read` / `refused_after`, which the recomputed result does not carry; the page has no planned place for it: **intent_gap**. |
| VG1 | The capped computed-on count (`listed` after the as-of cut) is never asserted | medium | Gap filed with mutations that pass (`cut` -> `parts`); **patch**: exact-line test on a capped part with a late Market. |
| VG2 | "Data stored" on a Scan Verdict is never asserted | low | Gap filed; **patch**: assert `card.stored` from the later part's time. |
| EC6 | Touch users can never open the tooltip (tap gives focus, not `:focus-visible`) | medium | Chrome does not match `:focus-visible` on pointer focus of a `tabindex` span; **patch**: also show on `.info-tag:focus`. |
| EC7 | `hand_scan` never closes its sqlite connection | low | `with sqlite3.connect()` only commits; **patch** (direct correction). |
| BH9 | EXPERIENCE.md UJ-4 still writes "1 Jun 2026" in a back link | low | Real; **patch** (direct doc correction). |
| BH10 | DESIGN.md Scan header lacks the shortlist line, disclosure, tooltip and the "Not fully read" tag | low | Real (plan drift); **patch** (doc). |
| BH11 | README gives no way to reach the Watchlist | low | Real; **patch**: one line saying a finished live Scan's Watchlist size opens it (offline from Story 4.6). |
| BH14a | `markupsafe` import inside the standard-library block | low | Real; **patch**. |
| VG-o1 | The browser row-click test opens a Verdict with no snapshots | low | True, but `test_ad22…` covers the match on real snapshots; rejected. |
| BH1 / EC5 / EC8 | The recomputed Verdict is never compared with its stored row at run time; a replaced Market record or a later builder change could make them differ | low | Resolved Markets are never fetched again (`stored_markets=store.resolved_markets`), so only an unclear Market re-fetched later could change; a builder change is a developer event; the guard needs new behaviour; rejected (reported to Edvard). |
| BH3 | With no parts, "Data stored" shows the Scan's time | low | Only for Wallets with nothing read, never on the Watchlist (Skilled only), reached by typing a URL; rejected. |
| BH4 | "Data stored" choice not in the plan | false | The spec's Always section records it (AI choice). |
| BH5 | Population line uses today's constants; "top 100 … 2 of 4 Markets used" | low | Constants change only by a plan decision; "of M" is the spec's rule; rejected. |
| BH6 | Scan list "Wallets" (requested N) vs Watchlist "Scan of N" (tested) | low | Differs only when fewer Wallets were found than asked; rejected. |
| BH7 | Tie-break undocumented | false | Spec Always: "sorted by p-value, then larger Real PnL, then address". |
| BH8 | `luck_passes(0)` reads "0.0 of the 0 Wallets" | low | Only when no Wallet got a Verdict; new wording needed; rejected (asked as an optional question). |
| BH12 | AI log and spec missing from the diff | false | Committed at the end of the story, as in 4.1 to 4.4. |
| BH13 | Every-page checks see only a no-data Scan Verdict | low | `test_ux_dr37…` covers a full one; rejected. |
| BH14b | Test reads `store._connection()` | low | Same as `test_scan_job.py`; rejected. |
| BH14c | `.tooltip:focus-visible` can never apply | false | It is the UX-DR9 twin the hover test requires; harmless. |
| BH14d | `[aria-current]` would style `aria-current="false"` | low | The app never writes "false"; rejected. |
| EC1 | A data-rebuilt finished Scan links rows to a Verdict that 404s | low | Only after a failed schema copy; rejected. |
| EC2 | A scan id above 2**63 makes SQLite raise (500) | low | Same in 4.4's routes; only a hand-typed URL; rejected. |
| EC9 | Task names `test_scans_page.py`, the link test is in `test_watchlist.py` | low | Fix would edit this spec; rejected. |


Pass 2 (2026-11-26, after the loop): three reviewers, 26 findings; 0 intent gaps, 0 bad spec, 8 patched, 18 rejected or carried, 0 deferred.

| # | Finding | Verdict | Evidence / route |
|---|---------|---------|------------------|
| VG2-1 | Row/Verdict equality tested only on *Not enough data* results (the fake Scan has no Skilled Wallet), and only with Seed 44 | medium | Confirmed: all three `scanned` results have `p_value` None; **patch**: the sharp trader frozen in two parts under Seed 7, Skilled, recomputed equal to `scan_results`, page shows odds, chart and "Seed 7"; planting `seed=44` fails it. |
| VG2-o | No Scan Verdict with a chart is ever rendered | low | Same root; covered by the patch above. |
| BH2-13 | The focusable tag is a bare `span` (no role) | medium | A `tabindex` span is announced as a nameless generic; **patch**: `<button type="button">` (the WAI tooltip pattern), browser test checks role and name. |
| BH2-11 | `verdict_page` calls `Lookup._page` from outside | low | Real (a module depends on a private helper); **patch**: builds `WalletPage` itself. |
| BH2-14 | `tag-tip.js` loads on every Watchlist | low | Real; **patch**: only when a row is flagged. |
| BH2-6 | epics FR-11 line says "always" with no exception | low | Real plan drift; **patch** (memlog entries are append-only and the later entry records the exception). |
| BH2-7 | AD-8 and EXPERIENCE put the exceptions before the default in nested brackets | low | Real; **patch**: default first, then the two exceptions. |
| BH2-8 | Decision-log entry opens with the review outcome | low | Real; **patch**: moved after the planning paragraphs. |
| BH2-9 | PRD FR-16 check no longer tests the counting rule | low | Real; **patch**: a 163/13 check and a no-Verdict check added. |
| BH2-1 / EC2-3 | "0.0 of the 3" for 1 to 4 Wallets with a Verdict | low | The plan's rounding rule (one decimal under 2) is followed; Decision C covered only 0; new wording would be Edvard's; rejected (reported to him). |
| BH2-2 | Computed-on says "around the Cut-off Date" with the after part refused or nothing read | false | The bets counted are still those around the date; with none, "no bets" is true. |
| BH2-3 / EC2-6 | Population line from today's constants | low | carried BH5: rejected. |
| BH2-4 | Scan list Wallets vs "Scan of N" | low | carried BH6: rejected. |
| BH2-5 | "4 Wallets not fully read" beside the shortlist reads as "of 600" | low | The spec counts flagged top-N Wallets (Decision 3a); rejected. |
| BH2-10 / EC2-5 | "2,000" written into the Scan window lines | low | `core` cannot import `data.window`; the limit changes only by a plan decision, and the plan's wording says 2,000; rejected. |
| BH2-12 / EC2-1 | Data-rebuilt Scan: Watchlist links lead to 404 | low | carried EC1: rejected. |
| BH2-15 | Forced-colours test never meets an empty pill dot | low | The Watchlist lists only Skilled (three filled dots); rejected. |
| BH2-16 | `not_fully_read()` runs twice; `verdict` filters all results | low | A few hundred rows, local; rejected. |
| EC2-2 / EC2-8 | Market rewrites can make the Verdict differ from the row | low | carried BH1/EC5: rejected. |
| EC2-4 | scan id above 2**63 gives 500 | low | carried EC2: rejected. |
| EC2-7 | `test_scans_page.py` untouched | low | carried EC9: rejected. |

## Design Notes

- Dates: the Cut-off Date is long ("1 July 2025") in the header, back link and Scan list, as in 4.4; the tab title uses the short form from EXPERIENCE's title table.
- The Verdict page recomputes rather than reading only the stored row because the chart and honesty notes need the simulations and the Position set; the stored row stays the Watchlist's source, and a test proves they agree.

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass, 0 skipped with `CI=true`. Result (2026-11-26, after review pass 2 and Decision D): 1,505 passed, 0 skipped, 3 deselected (the `online` tests), about 250 s.

**Manual checks:**
- Screenshots of a Watchlist (full, empty, partial disclosure, flagged row) and a Verdict from a Scan, both themes and 400 px, via Playwright with installed Edge.
