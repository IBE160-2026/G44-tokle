---
title: 'Story 5.2: The Hold-up Test page'
type: 'feature'
created: '2026-11-27'
status: 'done'
baseline_commit: 'c54c5b57907e4484b707dd2ed8394696d1e25e6a'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-5-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A finished Scan stores its two Hold-up group results (Story 5.1), but no page shows them: the Scan tabs hold only the Watchlist, and the README does not report the offline result on the real Wallets, which closes the stage 2 minimum (FR-17, UX-DR35, NFR-13, PRD §6.1 2b).

**Approach:** A read-only *Hold-up Test* page per finished Scan, at `/scans/<id>/hold-up`, shows the stored `holdup_after` rows as two group cards under the Scan header and tabs it shares with the Watchlist. The README gets the offline result, its limits and why the dropped-share warning shows.

## Boundaries & Constraints

**Always:**
- **Stored rows only (AD-22):** the page reads `store.group_results(scan_id)` and derives the flag with `holdup.dropped_shares_differ`. Nothing is computed again, fetched or written.
- **Header and tabs (UX-DR33):** the same Scan header as the Watchlist, from one shared template part. Tabs *Watchlist* · *Hold-up Test* in the navigation region named "Scan", the current one marked. Tab title "Hold-up Test · 1 Jul 2025 · LiquidOracle". Server-rendered, no new JavaScript (AD-18).
- **Group cards (UX-DR35):** *Before-Cut-off Passers* first, then *Comparison Group*; side by side from 900 px, stacked below. Each: the Verdict pill (dots and text; *No evidence of skill* on the neutral tint; *Not enough data* dashed with no dots), the odds sentence of the Verdict card, then five small figures: Resolved bets counted, Real PnL, Wallets in the group, Wallets dropped (fewer than 10 bets after the Cut-off Date), Wallets not fully read.
- **Under the cards, word for word:** "Each Wallet's bets after the Cut-off Date are capped at its first 2,000. Bets in the same Market are simulated together, not as separate evidence." and the Seed.
- **Warning (FR-17):** when the flag is set, a warning box above both cards, word for word: "More Wallets were dropped in one group than in the other. Wallets that stop betting may be the ones that lost, so the group with more dropped Wallets may look better than it is."
- **Decision Q1 (Edvard, 2026-11-27, AI rec a, with his own addition): the offline info box.** In Offline Mode an info box sits above the cards, under the warning. Its first sentence is his addition, so the Passers card does not read as a real skilled trader found: "On the Sample Dataset, the Passers tested here are made-up Wallets built to have skill, not real traders: no real Wallet passed before the Cut-off Date." Its second sentence shows only with the warning: "The warning above is expected: the 1,000 coin-flipper Wallets have no bets after the Cut-off Date, so all of them are dropped, and nearly all of them are in the Comparison Group." The README says both too. Rejected: the README only (someone who only runs the app sees a warning with no reason).
- **Added by Edvard at approval (2026-11-27): a test must fail if the box's first sentence stops being true.** In an offline Scan of the committed Sample Dataset, a test checks that no real Wallet is rated *Skilled (high confidence)* before the Cut-off Date and that every Passer that is tested is a made-up Wallet built to have skill.
- **Decision Q2 (Edvard, 2026-11-27, AI rec a): a Scan with no Passers.** The Passers card holds only "No Wallet passed on its bets before the Cut-off Date, so the Hold-up Test and Copy Test have nothing to test." and the Comparison Group card still shows its own result. Rejected: the sentence alone with no cards (hides a stored result).
- **Added by Edvard after the review (2026-11-27, AI rec): who is in each group.** Under each card's title one line: "Wallets rated *Skilled (high confidence)* on their bets before the Cut-off Date." and "Wallets rated *Likely skilled* or *No evidence of skill* on their bets before the Cut-off Date." Also on a card with no Wallets (Spec Change Log).
- **States:** an empty Comparison Group card says "No Wallets in this group: every scanned Wallet passed or had *Not enough data* before the Cut-off Date."; a group with fewer than 30 pooled bets shows *Not enough data* with the FR-10 sentence for its count, and its figures.
- **Older Scan** (finished before the Hold-up Test existed, no stored rows): its Watchlist shows no *Hold-up Test* tab and the address is *Page not found* (Story 5.1's matrix). So is an unknown or unfinished Scan.
- **README (NFR-13):** the offline result for both groups, whichever way it came out, with its limits: 8 real Wallets, picked for the Sample Dataset, not a full Scan; no real Wallet is a Passer (the three Passers tested are made-up); 5 real Wallets are in the Comparison Group and its result rests on 3 of them, 307 of 409 bets from one; and why the warning shows offline (the 1,000 coin-flippers have no bets after the Cut-off Date; the rule is not changed to hide it). The status line says the stage 2 minimum is done.
- **The AI's choices, accepted by Edvard (2026-11-27):** five figures per card (DESIGN.md said four and is corrected); the cards reuse the Verdict card's odds sentence; the limit that Wallets on opposite sides of one Market each keep their own price as win chance goes into the README's limits, not onto the page.
- **Spec kept whole (Edvard, 2026-11-27, AI rec)** at about 3,000 tokens. Helpers for review only (Edvard, 2026-11-27, AI rec).
- Every number and phrase comes from `core/phrases` and the existing constants (AD-25). Plan documents first. Tests name their FR, AD or UX-DR and open no socket.

**Never:** no change to how the groups are formed, tested or stored; no Copy Test tab; no list of the Wallets in a group; no link to the page from the Scan list; no live Scan (Story 5.3).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Offline Scan | the stored rows Story 5.1 measured | Passers: *Skilled (high confidence)*, "fewer than 1 time in 10,000", 300 bets, $6,000, 10 Wallets, 7 dropped, 0 not fully read. Comparison Group: *No evidence of skill*, "more than half the time", 409, −$19,217, 999, 996, 0. Warning shown | N/A |
| Shares close | dropped shares within 20 points | no warning box; offline, the info box holds only its first sentence | N/A |
| Live run | not Offline Mode | no info box, with or without the warning | N/A |
| No Passers | 0 Wallets in the Passers group | its card holds only the Q2 sentence; the Comparison Group card shows its result; no warning | N/A |
| Empty Comparison Group | 0 Wallets in it | its card holds only the sentence above | N/A |
| Group too small | 12 pooled bets | *Not enough data* pill, "12 resolved bets; at least 30 are needed for a Verdict (18 more)", the five figures | N/A |
| Older Scan | `done`, no group rows | Watchlist with one tab; `/hold-up` not found | 404 page |
| Unknown or unfinished Scan | any other id or step | not found | 404 page |

</frozen-after-approval>

## Code Map

- `services/watchlist.py` -- `Watchlists._header` builds `ScanHeader`; make it a module function `scan_header(store, scan)` both pages call, and give `ScanHeader` a `has_holdup` flag (the Scan has both group rows). `EYEBROW`, `TAB_WATCHLIST`, `_wallets`, `Watchlists._finished` are the patterns to reuse.
- `services/holdup.py` (new) -- `HoldUps(store).view(scan_id) -> HoldUpView | None`; `GroupCard` (title, verdict, filled dots or None, odds line, figures, empty sentence); the page's fixed sentences as constants. Reuse `lookup.FILLED_DOTS`, `phrases.odds_sentence`, `not_enough_data`, `count`, `money`, `short_date`, `core.holdup.MIN_AFTER_BETS`, `dropped_shares_differ`, `records.PASSERS`/`COMPARISON`.
- `data/store.py` -- `group_results(scan_id)` gives (Passers, Comparison Group) or `()`; `scan(scan_id)`, `ScanStep.DONE`. No change.
- `web/__init__.py` -- route `GET /scans/<int:scan_id>/hold-up` beside `watchlist`; `not_found()` for None. Every template already gets `offline` (the context processor that shows the Offline pill; `web` is the one layer besides `settings` and `__main__` allowed to read the mode, `tests/test_architecture.py` line 210): the info box uses it, so no service reads the mode. The 1,000 comes from `data/synthetic.py`'s coin-flipper count through `phrases.count`.
- `web/templates/watchlist.html` lines 5-32 -- the header and tabs move to a new `scan_head.html` included by both pages; new `holdup.html`. Warning markup as in `verdict.html` lines 59-62 (`warning.svg.html`, hidden "Warning:").
- `web/static/css/app.css` -- `.verdict-pill` (line 550) has only the accent tint: add the neutral and dashed variants (DESIGN.md Verdict pill); a two-column `.group-cards` grid stacking at 899 px, written after the base rule; figures as a `dl` like `.scan-summary`; forced-colours rules beside the existing ones (line 575).
- `README.md` -- status line (9), "Stage 2 so far" (21), a new section for the Hold-up result.
- Plan: `DESIGN.md` line 432 (four figures, should be five), `EXPERIENCE.md` lines 107 and 137 to 140, `epics.md` Story 5.2, the UX `.memlog.md` (through `_bmad/scripts/memlog.py`), `deferred-work.md` line 87 (the "first 2,000" line is now shown).
- Tests: `tests/test_watchlist.py` (`hand_scan`, `Row`, `web_over`, `text`: add a helper writing `group_result` rows), `tests/test_web.py` (`every_page`, `EVERY_PAGE`), `tests/browser/test_watchlist_page.py` (the fixture pattern), `tests/test_holdup.py` line 786 (the offline Scan's pinned numbers).

## Tasks & Acceptance

**Execution:**
- [x] Plan: `DESIGN.md`, `EXPERIENCE.md`, `epics.md` 5.2, the architecture spine's AD-13 line (the mode also shows the offline info box), memlogs, `deferred-work.md` -- decisions Q1 and Q2, five figures, the older-Scan rule -- the plan before code.
- [x] `services/watchlist.py`, `services/holdup.py` -- shared `scan_header`, `has_holdup`, the Hold-up view -- FR-17, UX-DR33, UX-DR35.
- [x] `web/__init__.py`, `web/templates/scan_head.html`, `holdup.html`, `watchlist.html`, `web/static/css/app.css` -- the route, the page, the tabs, the pill variants, the card grid -- UX-DR33, UX-DR35, UX-DR10, UX-DR12.
- [x] `tests/test_holdup_page.py` (new), `tests/test_web.py`, `tests/browser/test_holdup_cards.py` (new) -- every matrix row, the fixed sentences, the tabs on both pages, the page only reads, the heading and label checks on the new pages, no sideways scroll at 320, 400 and 900 px, cards side by side only from 900 px, forced colours, JavaScript off.
- [x] `README.md` -- the offline Hold-up result, its limits, why the warning shows, the status line and feature paragraph; a test ties the README's numbers to the pinned ones.
- [x] Real app check: `load-sample`, `run --offline`, a new Scan, open the tab in both themes and at phone width; compare with the stored rows.

**Acceptance Criteria:**
- Given the offline Scan of the loaded Sample Dataset, when its *Hold-up Test* tab is opened, then both cards show the numbers stored for that Scan and the warning box stands above them.
- Given the Watchlist of a Scan with Hold-up rows, when it is opened, then it has both tabs with *Watchlist* current, and the Hold-up page has both with *Hold-up Test* current.
- Given the whole suite with `CI=true`, then every test passes with 0 skipped, and no earlier test's expectation changed except the tab markup.

## Implementation Notes

- Built in this session without a helper (Edvard chose helpers for review only). Plan edits first: DESIGN.md (five figures, the offline info box), EXPERIENCE.md (the group cards row with the box's words, *No Before-Cut-off Passers*, *Group too small*, a new row for a Scan from before the Hold-up Test), epics 5.2 (an open-items paragraph), the spine's AD-13 (the template shows the box from the value that shows the Offline pill), the UX and architecture memlogs.
- `services/watchlist.py`: `Watchlists._header` became the module function `scan_header(store, scan, whole)`, with `finished_scan` and `whole_results` beside it; `ScanHeader` gained `eyebrow` and `tabs` (`ScanTab(label, page)`; the Hold-up tab only when both group rows are stored). **Deviation from the Code Map:** `tabs` instead of a `has_holdup` flag. A tab's `page` is the name the web layer gives its route (`watchlist`, `hold_up`), so `scan_head.html` marks the current tab by comparing it with `request.endpoint` and no page passes a "current" value.
- `services/holdup.py` (new): `HoldUps(store).view(scan_id)`, `HoldUpView`, `GroupCard`, `Figure`, the fixed sentences as constants. The 2,000 is `data.window.WINDOW_LIMIT`, the 10 `core.holdup.MIN_AFTER_BETS`, the 1,000 `data.synthetic.COIN_FLIPPERS`. The view carries `offline_notes`, the sentences that apply in Offline Mode; the template shows them only when `offline` is set, so no service reads the mode (AD-13).
- **A choice inside decision Q1:** the box's first sentence ("the Passers tested here …") is left out when no Passer is tested (no Passers, or all dropped), because it would then describe nothing. It cannot happen on the Sample Dataset; the test `test_fr17_the_box_does_not_speak_of_tested_passers_when_none_is_tested` pins it.
- `web/__init__.py`: route `GET /scans/<id>/hold-up` (`hold_up`). `web/templates/scan_head.html` (new, the header and tabs, included by `watchlist.html` and the new `holdup.html`). `app.css`: `.verdict-pill.is-neutral` and `.is-none`, `.group-cards` (two columns, one below 900 px), `.group-figures` (a `dl` in two columns, one below 400 px), `.group-warning`, `.group-odds`, `.group-note`, `.figure-rule`. No JavaScript added.
- `README.md`: the status line, the stage 2 paragraph, a new section "The Hold-up Test on the Sample Dataset" (the result table, five limits, Story 5.3 not run), and the browser tests' list.
- **Edvard's test** (`tests/test_holdup.py`, `test_fr17_no_real_wallet_is_a_passer_in_the_offline_scan`): on a real offline Scan of the committed Sample Wallets and 40 coin-flippers, no real Wallet is a Passer by the app's own rule (`core.holdup.group_of`), and the Passers that are tested are exactly steady sharp, forecaster and speed trader. The Scan moved into a module fixture (`offline_scan`) that Story 5.1's offline test now shares; that test's checks are unchanged. Planted (a rule that also lets *Likely skilled* pass): it fails and names 0xcf0d7f.
- Tests: `tests/test_holdup_page.py` (new, 28 cases: every matrix row, the fixed sentences, the pill per Verdict, the tabs on both pages, the page only reads, the README's numbers and limits), `tests/browser/test_holdup_cards.py` (new, 16 cases: side by side only from 900 px in both themes, no sideways scroll at 320 to 1280 px, the tabs by keyboard, what a screen reader is given, JavaScript off, forced colours, the pill tints), `tests/test_web.py` (four Hold-up pages in the every-page heading and label checks).
- **Real app check (2026-11-27):** the offline app over `instance/offline.db`, screenshots in the dark and light theme at 1280 px, at 700 px and at 360 px. Scan 2 (run by Story 5.1) shows the stored rows: Passers *Skilled (high confidence)*, 300, $6,000, 10, 7, 0; Comparison Group *No evidence of skill*, 409, −$19,217, 999, 996, 0; the warning and the info box above them. Scan 1 (from before Story 5.1) has one tab and its Hold-up address gives 404.
- **Found on the screenshots:** "Wallets dropped" has a two-line label, so its number stood lower than "Wallets in the group" beside it. Fixed in CSS (the number sits at the bottom of its cell) and pinned by a browser test.
- Planted bugs: 29, one at a time. 27 caught at once. One was a real gap: a group whose Wallets were all dropped (Wallets but no bets) could be shown as an empty group and no test noticed; `test_fr17_passers_that_all_stopped_betting_are_not_an_empty_group` now pins it. One did not apply the first time (the script matched `\n` in a file with Windows line ends) and was caught on the re-run.
- AI slips: a long bash heredoc with Python broke again (switched to Write + run file, as the handoff says); the browser test file first had the same name as the unit test file, so pytest could not import it (renamed `test_holdup_cards.py`); the README first said the coin-flippers' bets run from January to April 2025, copied from the decision log, but since Story 4.6 they also hold the anchor Markets that resolve in June (checked against the generator and corrected); the spec size was first given as 2,400 to 2,600 tokens and came to about 3,000 after the answers were written in (told Edvard).
- Review pass 1 patches (2026-11-27). `services/holdup.py`: the box's second sentence shows only when the warning is set because the Comparison Group was dropped more; the five labels are paired with their rules (`FIGURES`) instead of by position; the row count is `len(HOLDUP_GROUPS)`. `services/watchlist.py`: one `_skilled` rule for the Watchlist's rows and the header's count; the `_finished` wrapper is gone. `app.css`: the figures use two columns only while each has room for a nine-digit amount on one line, otherwise one, never three (the 400 px rule is gone, the grid decides); in forced colours every Verdict pill gets an outline. README: the stage 2 paragraph is a list, the result is its own section before *Settings and keys*, and three sentences were made exact (who the 7 and the 996 dropped Wallets are; "have bets after the date and are tested").
- Review pass 1 tests. `tests/test_holdup.py`: `LUCKY_COIN_FLIPPERS` (87, 236, 319, 730, 828, 880: found by running the Skill Test over all 1,000, the same six a full Scan stores) with a `slow` check against the generator; the README's group sizes are built from that list; the offline Scan now runs with 90 coin-flippers, so its stored Verdicts must agree on the first lucky one; no real Wallet passes before the date under four other Seeds, and the three built Wallets pass under each; 0xd3a6e5 is pinned as the Wallet with 307 bets and the sharp trader with none. `tests/test_holdup_page.py`: the box and the direction of the warning, the offline page's headings, the read-only test now forbids the Scan's Hold-up phase itself. `tests/browser/test_holdup_cards.py`: nine-digit amounts at nine widths (one line, inside their cell, no sideways scroll, not split even in a squeezed cell), two columns at 899 and 1280 px and one at 320 and 400 px, the pill outline in forced colours.
- Planted bugs after the review: 11 against the fixes; 9 caught at once and 2 not (three columns allowed in a wide stacked card; the amount allowed to wrap), each closed with an assertion and then caught. Planting the first CSS back confirmed the reviewers' point: with two fixed columns "−$123,456,789" made the page scroll 9 px sideways at 320 px and ran past its cell at 360 and 400 px.
- AI slip in the review round: the new other-Seeds test was not run before the full suite and failed there on the AI's own wrong expectation (it assumed one real Wallet had no stored bets to test again; all 8 have). The check itself held; the expectation was corrected.
- **Taken to Edvard, then built:** a reviewer missed a line on each card saying who is in the group. The plan (UX-DR35) had no such line, so the AI asked instead of building it; he said yes (Spec Change Log). Plan first (EXPERIENCE.md, DESIGN.md, epics 5.2, UX memlog), then `WHO` and `GroupCard.who` in `services/holdup.py`, one line in `holdup.html`, and `test_fr17_each_card_says_who_is_in_the_group`, which checks the Verdicts the line names against `core.holdup.group_of`. A screenshot then showed the Comparison Group's longer line pushing that card's rows lower than the Passers'; from 900 px both lines now keep room for two lines, pinned by a browser test (the AI's first value was 1.5 px short, and that test caught it).

## Spec Change Log
- **2026-11-27, after review pass 1 (Edvard added to the frozen intent).** Trigger: review finding BH13 (the page never says who is in each group). The plan had no such line, so the AI did not build it and asked him with a recommendation; he answered "yeah add the line". Amended: one line in the frozen block (above), EXPERIENCE.md's group cards row, DESIGN.md, epics 5.2 and the UX memlog first; then `services/holdup.py` (`WHO`, `GroupCard.who`), `holdup.html`, one CSS rule and the tests. Known-bad state avoided: a page that names "Passers" without saying what one is. KEEP: everything else in the build and the review fixes is unchanged; the line's Verdicts are tested against `core.holdup.group_of`, so it cannot drift from the rule.

## Review Triage Log

Pass 1 (2026-11-27): three reviewers (blind hunter BH, edge case hunter EC, verification gap VG), 30 findings; 0 intent gaps, 0 bad spec. 22 patched (some in part), 7 rejected, 1 taken to Edvard (BH13); 1 part deferred (in BH21). No reviewer found a wrong number on the page.

| # | Finding | Verdict | Evidence / route |
|---|---------|---------|------------------|
| VG1 / BH4 / EC4 | The README's group sizes (10, 7, 999, 996) and "6 coin-flippers" are checked only against numbers typed into the same test file | medium | Pre-verified by the reviewer: every Scan in the tests had 40 coin-flippers. **patch**: `LUCKY_COIN_FLIPPERS` with a `slow` check over the generator (all 1,000 on CI Linux), the sizes built from the list, the offline Scan raised to 90 coin-flippers so it holds the first lucky one. Planted (one index removed; README "5"; README sizes changed): each fails. |
| BH16 / EC2 | Large amounts are untested in the figure cells and `nowrap` can push them out of the card | medium | Confirmed by planting the first CSS back: 9 px of sideways scroll at 320 px, the amount past its cell at 360 and 400 px. **patch**: the grid gives two columns only while each has 11.5rem, else one; a browser test with nine-digit amounts at nine widths. |
| VG2 | "A negative Real PnL stays on one line" was asserted with `getClientRects`, which is 1 for any block | low | Pre-verified by the reviewer's probe. **patch**: the amount is squeezed into a 3rem cell and must keep one line's height. Planted (`nowrap` removed): fails. |
| VG3 | No test sees the figures go to one column on a phone | low | Pre-verified. **patch**: the width test compares the first figures' places at 320, 400, 899 and 1280 px. Planted (three columns allowed): fails at 899 px. |
| BH1 / VG4 | "No real Wallet passed before the Cut-off Date" is shown for any Seed but tested for Seed 44 only | low | True: the Seed is a setting. **patch** (test): each real Wallet's bets before the date, from the Scan's frozen snapshots, tested again under four other Seeds; none passes (the closest, 0xcf0d7f, is *Likely skilled* at p about 0.046 against the 0.01 a Passer needs). |
| BH2 | The box's second sentence blames the Comparison Group's coin-flippers even when the Passers were dropped more | low | Confirmed; the AI's own test pinned that case. Cannot happen on the Sample Dataset. **patch**: the sentence needs the Comparison Group's dropped share to be the larger. Planted (condition removed, and reversed): both fail. |
| EC1 | With fewer than 1,000 coin-flipper files (an interrupted `load-sample`) the box still says 1,000 | low | Rejected: it needs a half-written Sample Dataset, which `load-sample` replaces on the next run, and the guard would test a state nobody has shown. |
| BH3 | Leaving out the first sentence when no Passer is tested changes decision Q1 and is not in the plan | low | True: it was only in the Implementation Notes. **patch** (plan): EXPERIENCE.md, epics 5.2 and the UX memlog name both left-out cases as the AI's choices; shown to Edvard in the review summary. |
| BH5 | Two README sentences are looser than the data; 0xd3a6e5 and the sharp trader's bets are not pinned | low | True. **patch**: the sentences say who the 7 and the 996 are; tests pin 0xd3a6e5 at 307 bets and the sharp trader at none. "Resolve in June 2025" was checked against the generator (last Market closes 15 June). |
| BH6 | The read-only test forbids names the page's service never imports, and its docstring says the Scan's Wallets are not read | low | True: the header counts the shortlist. **patch**: the test forbids `services.scan.hold_up_scan` and `hold_up_members`, both Skill Test entry points, snapshots and `finish_scan`; the docstring says what the header reads. Planted (the page calls `hold_up_scan`): fails. |
| BH7 | The "rated Skilled" rule is written twice in `watchlist.py`; `_finished` is a one-line wrapper; two length checks differ; `group_results` is read twice | low | First three confirmed and **patched** (`_skilled`, wrapper removed, `len(HOLDUP_GROUPS)`). The second read is one small query: rejected. |
| BH8 | A service module holds the web layer's route names | low | True, and a renamed route already fails every Scan page test at render. The reviewer's fix (a map in `web`) is more surface: rejected. **patch** (plan): the coupling is in the architecture memlog. |
| BH9 | `offline_notes` is built in live runs too | false | Nothing is shown: `test_ad13_a_live_run_never_shows_the_offline_info_box` pins it, and AD-13 says the template decides. |
| BH10 | The architecture memlog entry tags the AI's design choices as the user's decision | low | True. **patch**: a correction entry (the log is append-only) saying what Edvard decided and what the AI chose. |
| BH11 | The spec says `in-review`, sprint status `in-progress`, and the README already says the stage 2 minimum is done | false | Sprint status moves to `review` when the story is presented. The README is the repository's state at merge, and the PR is merged only on a green CI run; told Edvard. |
| BH12 | `deferred-work.md` says "still open" and "closed" in one entry; epics 5.2 is headed "Open items, decided while planning" | low | First confirmed and **patched** (reworded). The heading is the one Story 5.1 uses: rejected. |
| BH13 | The page does not say who is in each group; "Wallets not fully read" has no explanation | low | True, and not in the plan (UX-DR35 lists the card's parts). A plan change is Edvard's call: **taken to Edvard** with a recommendation. |
| BH14 | The No Passers sentence names the Copy Test, which is not built | false | They are the plan's own words (EXPERIENCE.md, epics 5.2, the frozen spec). Rejected. |
| BH15 | The drop rule reads "bets" on the page and "resolved bets" in the README | low | Both are true; the page's words are in the frozen spec and the README's are the more exact. Rejected. |
| BH17 | In forced colours the accent and neutral pills lose their tint and have no outline | low | Confirmed (the Watchlist's pill had the same gap). **patch**: a `CanvasText` outline, dashed for *Not enough data*; browser test. Planted: fails. |
| BH18 | The fifth figure stands alone; DESIGN.md carries change history and no word on one column | low | Cosmetic. **patch** (plan): DESIGN.md says how the columns behave and that the fifth stands alone; the history is in the memlog. |
| BH19 | The dropped rule is tied to label number 3; `NO_PASSERS` is padded with empty strings | low | First confirmed and **patched** (`FIGURES` pairs each label with its rule; planted: fails). The padding keeps one shape for both empty sentences: rejected. |
| BH20 | Test files import helpers from each other; `services.holdup` has three import names | low | The repository's habit since Story 4.5 (`hand_scan`), with no import-time cycle. Rejected. |
| BH21 | Missing: the offline page in the heading checks; the Scan pages in `docs/accessibility-check.md`; an AI log | low / false | First **patched** (the offline page's headings are asserted). The document covers stage 1 and misses every Scan page since Epic 4: **deferred** (`deferred-work.md`). The AI log comes in its own commit after Edvard has seen it: false. |
| BH22 | The README's stage 2 text is one 250-word paragraph, and the result sits under *Install and run* | low | True. **patch**: a list like the stage 1 list, and the result as its own section. |
| EC3 | The spec's task line says `has_holdup`; the code has `tabs` | low | Rejected: the fix would edit this spec; the deviation is in the Implementation Notes and `epic-5-context.md` names the function Epic 6 extends. |

After Edvard's answer (2026-11-27): BH13's first half is built (the line under each title; Spec Change Log). Its second half, an explanation for "Wallets not fully read", was not asked for and is not built.

## Design Notes

- The header and tabs live in one template part, so the two Scan pages cannot drift apart; Epic 6 adds the Copy Test tab there.
- The odds sentence is the Verdict card's own ("a trader with no edge would do this well …"): the plan asks for "the odds phrase", and a second wording for groups would be new text nobody approved.
- One limit from the Story 5.1 review goes into the README's limits, not onto the page: Wallets on opposite sides of one Market each keep their own price as their win chance.

## Verification

**Commands:**
- `uv run pytest` with `CI=true` -- expected: all pass, 0 skipped.
- `uv run pytest tests/test_holdup_page.py tests/browser/test_holdup_cards.py` -- expected: all pass.
- Result (2026-11-27, final, with the line Edvard added after the review): 1,702 passed, 0 skipped, 3 deselected, 368 s.
- Result (2026-11-27, after review pass 1): 1,701 passed, 0 skipped, 3 deselected, 360 s; `tests/test_holdup.py` with `--repetitions 1000`: 60 passed, 115 s (the three `slow` checks 91 s).
- Result (2026-11-27, before review): 1,688 passed, 0 skipped, 3 deselected (the `online` tests), 344 s (1,636 before this story).

**Manual checks:**
- Offline app, a finished Scan: the *Hold-up Test* tab in the dark and light theme, at 1280 and 360 px; the older Scan (Scan 1 in `instance/offline.db`) has no such tab.
