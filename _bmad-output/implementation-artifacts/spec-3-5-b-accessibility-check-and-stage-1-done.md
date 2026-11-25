---
title: 'Story 3.5 part B: accessibility check, and stage 1 done'
type: 'chore'
created: '2026-11-25'
status: 'done'
baseline_commit: 'ae6b11a20c60a2b2915c2cacba5f258c7b9455e8'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 3.5's accessibility claims are only partly proven: heading order is checked on one page, no test runs every page with JavaScript off, and most of the 12-item checklist (epics.md Story 3.5) is checked only in the HTML, never by keyboard in a browser. `docs/accessibility-check.md` does not exist, and stage 1 is not formally closed (README status, SM-1, SM-2).

**Approach:** Add Python page checks over every page the app renders, and one browser test per checklist item that uses only the keyboard and reads what the browser hands a screen reader (role, name, state, reading order, live-region text). Write `docs/accessibility-check.md` from what the tests found. Close stage 1: README, a short stage 1 note with SM-1 and SM-2, CI green on three systems. Failures the tests find are fixed here and re-checked, or listed with the reason they stay.

**Decisions (Edvard, 2026-11-25):** one spec for the checks and the stage 1 close, kept whole at about 2,100 tokens (AI recs). "Below all" (deferred since Story 3.1): option (a), AI rec, over (b) "leave it and note the gap": when the Real PnL is below every Simulation, the chart text alternative adds "That is below all 10,000 replays." (plan changed first: EXPERIENCE.md, epics.md UX-DR24 and Story 3.1, UX memlog). At the build's finding 1, the Lookup page keeps its autofocus (UX-DR16; AI rec, over removing it): its first Tab goes to "Check wallet" and the skip link is reached by Shift+Tab; checklist item 1 in epics.md says so. Earlier: browser tests replace his own NVDA walk-through (2026-11-24).

## Boundaries & Constraints

**Always:** Browser tests as in part A (`tests/browser/`, Chrome or Edge, CI fails never skips, nothing outside 127.0.0.1, paused clock or retrying `expect`, no fixed sleeps). Checklist tests act by keyboard only (`page.keyboard`, no `click`). Each test docstring names its UX-DR/NFR/FR id and checklist number. The document records what each test actually found, failures included, and says what the tests cannot prove (NVDA's own speech, browse mode).

**Never:** Change page wording except where a decision below says so (plan updated first). Re-test what part A or the Python tests already prove; cite them instead. Hand-edit anything in `sample_data/`.

## I/O & Edge-Case Matrix

| Item | Page / state | Expected (what the browser hands a screen reader) |
|------|--------------|----------------------|
| 1 | Verdict, first Tab; Lookup, Shift+Tab from the autofocused field | focus on link "Skip to content"; Enter → focus in `main` |
| 2 | Lookup, empty submit by Enter | field name "Wallet address"; after reload focus in the field, its description contains "Error: Enter a wallet address.", `aria-invalid="true"` |
| 3 | Sharp Verdict | h1 name starts "Verdict: "; dots absent from the tree |
| 4 | Sharp Verdict | odds phrase, stats, chart text are plain text in reading order after h1 |
| 5 | Slider | role slider "Replays by result"; each key changes `aria-valuetext` (cite part A for keys) |
| 6 | Marker | Enter → live region "Highlight on…", Esc → "Highlight off" |
| 7 | Copy | Enter → status region "Address copied" |
| 8 | Stop-loss Verdict | warning text starts "Warning:" |
| 9 | Sharp Verdict | heading "What this test can't see" reachable; its content in DOM order |
| 10 | Any page | button "Dark theme", `aria-pressed` flips on Enter and Space |
| 11 | Lookup, Verdict | Tab walk reaches every control, visible focus ring on each, Shift+Tab walks back, no trap |
| 12 | Lookup, Verdict, Fetching | 200% zoom (device scale 2 at 640 px) and 320 px: no sideways scroll |
| JS off | every page | complete: h1, main content, forms submit |

</frozen-after-approval>

## Code Map

- `tests/test_web.py:80-111` -- `PAGES` list and `test_every_page_has_the_frame` (one h1, lang, skip link first, no inline script); heading order only at `:683` (sharp Verdict, h1/h2). Extend to every page and full h1→h2→h3 order.
- `tests/test_live_lookup.py:131,224,251,273,308` -- how fetching, no-history, not-enough, unavailable and 500 pages are rendered in Python; `tests/test_web.py:247` not-loaded, `:623` 500, `:632` 405. Reuse these builders for the heading check.
- `tests/browser/conftest.py`, `tests/browser/pages.py` -- `make_page(path, width, …, java_script_enabled=…)`, `live_app`, `StandInPolymarket.hold()`, `box`, `style`, `assert_no_sideways_scroll`. Page for a Wallet: `make_page(f"/wallet/{synthetic.address_of('stop-loss-trader')}", 1280)`.
- `tests/browser/test_chart_script.py:62-163`, `test_pages.py:36,109,195,278` -- part A coverage of items 5, 6, 7, 11 (partly), 12 (320 px); cite, add only the screen-reader reading.
- `src/liquidoracle/web/templates/base.html:2,12,21,30` -- lang, skip link, theme button, `main tabindex=-1`. `check.html:15-27` -- GET form, `novalidate`, `autofocus`, error markup. `verdict.html:10-17,34,50,85,103,105,114` -- hidden "Verdict:", dots, odds, copy status, warning, beyond label, live region, chart text, honesty card. `samples.html:8` -- Real Wallets links (short address only).
- `src/liquidoracle/core/phrases.py:134-144` -- `beyond_all`, `chart_text`; `services/chart.py:154-159,185`.
- `README.md` -- status line (Story 3.4), JS list, Tests section.
- `_bmad-output/planning-artifacts/prds/prd-LiquidOracle-2026-10-12/prd.md:396-397` -- SM-1, SM-2.

## Tasks & Acceptance

**Execution:**
- [x] `tests/test_web.py` -- every page (Lookup, Lookup error, Verdict, Not enough data, Fetching, Not available offline, not loaded, No history, Unavailable, 500, 404, 405) has one h1 first and no skipped heading level; every field has a label and every error is tied to its field.
- [x] `tests/browser/test_checklist.py` (new) -- one test per checklist item 1–12 (matrix), plus Real Wallets links: names unique, inside the list named "Real Wallets"; plus every page with JavaScript off is complete. Use `locator.aria_snapshot()` / `get_by_role` to read role, name, state and order.
- [x] `src/liquidoracle/core/phrases.py`, `services/chart.py`, `tests/test_phrases.py`, `tests/test_chart.py` -- `chart_text` gets the "below all" sentence only when the Real PnL is below every Simulation (the same condition as `beyond_all(above=False)` at `chart.py:156`); tests for below, above and inside; one rendered-page test with a planted below-all result.
- [x] `src/…` -- only fixes a failing test proves needed; each logged in Implementation Notes and in the document.
- [x] `docs/accessibility-check.md` (new) -- per item: what is checked, the test, what it found (pass, or the failure, the fix and the re-check); the AC1 page checks; Real Wallets; what the tests cannot prove.
- [x] `docs/stage-1-check.md` (new) -- SM-1: each named check mapped to its test; SM-2: the network-blocked suite, the README-commands CI job, no keys; the CI run on three systems.
- [x] `README.md` -- status "stage 1 done"; every stage 1 feature (FR-1 to FR-14) present; Tests section names the checklist tests and links both docs.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md`, `.logs/edvard-tokle/issues.md` -- resolve the part B, "below all" and Real Wallets items.

**Acceptance Criteria:**
- Given `CI=true uv run pytest -rs`, when it runs, then every test passes and none is skipped.
- Given each new browser test, when its behaviour is broken on purpose (one planted break per test), then it fails.
- Given the pushed branch, when CI runs, then all six test jobs and the README job pass.

## Design Notes

200% zoom: a 1280 px window at 200% lays out like 640 CSS px, so the test uses a 640 px viewport with `device_scale_factor=2` and checks no sideways scroll; text-only zoom is not available in Playwright and is listed under "cannot prove".

Real Wallets links (AI's call, open to change): the name is the short address the user sees ("0x7298…fcfc") inside a list named "Real Wallets"; the test checks the names are unique. No wording change unless a check fails.

## Verification

**Commands:**
- `CI=true uv run pytest -rs` -- expected: all pass, 0 skipped (1,144 before).
- `CI=true uv run pytest tests/browser/test_checklist.py -rs` -- expected: all pass.

## Implementation Notes

- Full run, Windows 11, Python 3.14, Chrome, 25 Nov 2026: `CI=true uv run pytest -rs`: 1,207 passed, 0 skipped (1,144 before).
- `tests/test_web.py`: an `every_page` fixture renders 14 pages (the matrix's 12 plus Unavailable with stored data and the 500 from a failed job); live states come from a real job queue whose jobs the test ends by hand (`Store.claim_job`/`finish_job`), with a store clock moved past `FRESH_FOR` for the stored-data case. `FakeLookup` takes an optional chart for the planted below-all page.
- `services/chart.py`: `below_all` is now one named condition (`at_or_below == 0`; the if/elif keeps "above all" first) used for both the marker line and `chart_text(below_all=…)`; behaviour of the marker line unchanged.
- Review fixes (coordinator, 2026-11-25): item 11's walk now allows off-page stops only as one run at the wrap point and names the focused element on any other stop. It showed that Chrome leaves the page once after the last control on Tab but goes from the first control straight to the last on Shift+Tab, so the Shift+Tab walk allows that. Real Wallets: count equals the committed files, name equals visible text. `wait_for_job` checks `reply.ok` and polls every 50 ms. `error_ids` finds errors by class token. New planted break: `tabindex="1"` on the theme toggle fails item 11 on all three pages.
- `tests/browser/conftest.py`: two session apps added, `not_loaded_url` (empty database) and `real_wallets_url` (the committed `sample_data/real/` files read in place, empty database).
- Finding (item 1): the Lookup page's `autofocus` (UX-DR16) puts the focus in the field, so its first Tab goes to *Check wallet*, not the skip link. Not changed (it would alter a planned behaviour); the test asserts the actual behaviour (skip link first on the Verdict page; on Lookup, reached by Shift+Tab and still first in tab order) and the document lists it as staying. Needs Edvard's yes/no.
- No `src/` fix was needed for the checklist; the only source change is the planned below-all sentence.
- Planted breaks, one per new browser test (each restored from git after): skip link to a missing id; error left out of `aria-describedby`; hidden "Verdict: " removed; chart text `aria-hidden`; chart.js not updating `aria-valuetext`; `aria-live="off"`; other copy status words; hidden "Warning: " removed; left-out block `aria-hidden`; theme.js `aria-pressed` stuck; focus ring width 0; `body { min-width: 700px }`; Real Wallets names cut short; theme toggle not hidden; form `method="post"`; reload link renamed; `below_all=False` in chart.py. Every one made its test(s) fail. Python page checks: an h4 group label and a missing `aria-invalid` also fail.
- Not done here: pushing the branch and the CI run on three systems (the third acceptance criterion); `docs/stage-1-check.md` says the run is linked from the pull request.

## Spec Change Log

## Review Triage Log

Three reviewers (blind B, edge case E, verification gap V), 23 findings: V found no gap; B 14, E 8. Grouped into 10 patch groups, 0 deferred, 5 rejected. Before the review the build's finding 1 went to Edvard (autofocus kept; frozen matrix row 1 and epics checklist item 1 changed with his approval).

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| B5, E1, E2, E8 | Checklist 11 drops every unidentified (-1) focus stop wherever it falls, skips its ring check, never asserts "leaves the page once"; a different number of presses to leave the page gives a misleading backward-walk error | medium | `reached`/`back` filter `stop >= 0`; doc claims more than the test asserts | patch |
| B4, E5, E7 | Real Wallets test asserts `count() >= 2`, not all 10; name never compared with visible text | low | a list that drops 8 links passes; doc says "the 10 names" and "the same name a sighted user sees" | patch |
| B10, E3 | `wait_for_job` polls with no pause and no `reply.ok` check | low | tight loop against the threaded test server for up to 30 s; a 404 shows as KeyError | patch |
| B12, E4 | Error-to-field check finds errors only by the exact `<p class="error-message" id=` string | low | reordered attributes or an extra class make it check nothing on 13 of 14 pages | patch |
| B1, E6 (part) | README says "by keyboard and screen reader" | low | no screen reader runs (docs/accessibility-check.md › cannot prove) | patch |
| B2, E6 | Part B closed in issues.md with the CI run pending inside the closed line | low | the README reaches `main` only after the PR's CI is green, so its status is true when read there; the pending check needs its own open item | patch (issues.md) |
| B9 | `below_all` guard `at_or_above != 0` is implied | low | at_or_above + at_or_below ≥ 10,000, so at_or_below == 0 implies at_or_above == 10,000 | patch |
| B7 | "Cannot prove" omits WCAG 1.4.12, 1.4.11, 1.3.4 | low | the doc states WCAG 2.1 AA as the target | patch |
| B11 | stage-1-check's coin-flipper row gives no limits | low | the test enforces the limits in expected.json | patch |
| B3, B14 | Real Wallets "AI's call" with no recorded approval; stray space in the stats line uncommented; docstring line length; missing space in EVERY_PAGE | low | Edvard approved the spec that states the call (checkpoint 1); the rest are direct text fixes | patch |
| B6 | Focus ring check only style/width, dark theme only | low | colour and contrast of the ring come from DESIGN.md tokens (checked by `test_ux_dr1_colour_tokens_match_design_md`); colour contrast is listed under "cannot prove"; a colour check adds complexity for a defect not met in use | reject |
| B8 | "below all 10,000 replays" vs the marker's "Simulations" | false | the word rule (epic-3-context › Words): on screen a Simulation is a "replay", except the FR-9 marker label, which keeps "Simulations" | reject |
| B12 (part) | `labelled()` accepts aria-labelledby to a missing id or an empty label | low | no page uses aria-labelledby on a field; the one label has text and is checked by test_ux_dr16; guarding adds branches | reject |
| B13 | No AI log, spec untracked, planted breaks untraced | false | the AI log and commits come at the end of the session (workflow step 5); planted breaks are listed in Implementation Notes | reject |
| B14 (part) | Stray space "bets , Real PnL" should be fixed in the markup | low | the accessibility tree joins the hidden ", " with a space; screen readers ignore it; changing markup changes a planned page for nothing heard | reject (doc note instead) |
