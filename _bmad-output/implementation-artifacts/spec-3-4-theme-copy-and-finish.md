---
title: 'Story 3.4: Theme, copy and finish'
type: 'feature'
created: '2026-11-24'
status: 'done'
baseline_commit: '32405d714d0f48ca57920882df571eb7f0275a1e'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The pages work but do not feel finished: nothing reacts to hover, buttons never lift, the address card has no copy button (UX-DR21), and below 900 px the Verdict header keeps two columns, so at 360 and 600 px the page scrolls sideways and the odds line wraps one word per line (UX-DR10; deferred from Stories 1.7, 3.1, 3.3). No JavaScript file runs in any automated test (deferred item from 2.5 and 3.2).

**Approach:** Add `copy-address.js` and the address card's copy button as in `mockups/verdict.html`; add DESIGN.md's interaction states (hover = focus, 120 ms, 1 px lift on buttons, nothing moves with reduced motion); add the three breakpoints' rules from EXPERIENCE.md › Responsive & Platform to `app.css`.

**Decisions (Edvard, 2026-11-24, at spec time):**
- JavaScript is tested with browser tests (option A, AI rec): Playwright for Python as a pinned dev dependency; `tests/browser/` starts the app on 127.0.0.1 and drives the installed Chrome or Edge. They cover the copy button (works, refused), no sideways scroll at 320, 360, 600 and 900 px on the Lookup and Verdict pages, and no lift with reduced motion. Plan first: AD-17 gets one exception (sockets to 127.0.0.1 only, in `tests/browser/`), the Stack table gains Playwright. Porting the 45 throwaway `chart.js` checks and testing `progress.js` moves to Story 3.5. Rejected: no runner (nothing would prove "no sideways scroll").
- HE ADDED: on GitHub the browser tests must run, and fail if they cannot, never skip quietly, or the green check proves nothing. So with `CI` set (GitHub sets `CI=true`) a missing browser is a test failure; on a computer without `CI` they skip with a reason saying which browsers were tried.
- The spec is kept whole (about 1,900 tokens; AI rec).

## Boundaries & Constraints

**Always:** Only clickable things react (links, buttons, Sample Wallets items, About summary, chart bars and marker); every hover rule sits in `@media (hover: hover)` and has a matching `:focus-visible` rule. Lift = `translateY(-1px)` + lift shadow (light `0 3px 8px rgba(20,25,34,.10)`, dark `0 3px 10px rgba(0,0,0,.45)`), buttons only, back down on `:active`. Breakpoints 900, 640, 400 px only. No sideways page scroll at 320 px on any page. The copy button is hidden in the HTML and shown by the script, so without JavaScript nothing is dead (AD-18). `copy-address.js` holds no user-facing words: it reads "Copied", "Address copied" and both error sentences (Ctrl+C, ⌘C) from the page (the AD-25 scan covers `.js`). Copy error in `--error`, with a hidden "Error: ". Forced colours: the copied state and the lift stay visible without colour.

**Never:** Change any Verdict, number or sentence on the cards. Change the chart's behaviour or the theme logic. Add Node or a bundler. Hover effects on cards, stats or text.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Copy works | click the copy button | full address on the clipboard; button shows "Copied" on `accent-tint` for 2 s; status line announces "Address copied" | a second click within 2 s restarts the 2 s |
| Copy refused | clipboard missing or rejects | error under the card "Copy failed. Select the address and press Ctrl+C." (⌘C on a Mac), announced; address text selected | a later successful copy hides the error |
| No JavaScript | script blocked | address shown, no copy button | N/A |
| Reduced motion | system setting on | no lift, no transitions; colours still change | N/A |
| 900 px and wider | Verdict page | header and stats row in two columns, honesty notes in three | N/A |
| 640–899 px | Verdict page | address card under the hero, warning under the stats | N/A |
| 400–639 px | any page | Verdict 40 px, page title 36 px, ledes 21 px, odds 21 px, 16 px side margins, "Check wallet" button under the field, top bar tools on their own row | N/A |
| Below 400 px | any page | Verdict 34 px; still no sideways scroll at 320 px | N/A |

</frozen-after-approval>

## Code Map

- `src/liquidoracle/web/templates/verdict.html:19-22` -- address card: add `.address-row` with `<code id="wallet-address">`, the `.icon-button#copy-address` (copy SVG and `#copy-label`, from the mockup lines 411-421) `hidden`, `#copy-error` (`hidden`) and the `aria-live` `#copy-status`; words in `data-` attributes; load `copy-address.js` with `defer` once.
- `src/liquidoracle/web/static/js/copy-address.js` (new) -- based on the mockup script (lines 662-690); show the button; Mac check by `navigator.platform`/`userAgentData`; IIFE + `"use strict"` like `theme.js`.
- `src/liquidoracle/web/static/css/app.css` -- `.icon-button`, `.is-copied`, `.copy-error`, `.address-row`; `--lift-shadow` in both theme blocks; hover/focus block from mockup lines 301-321 (brand, mainnav, theme toggle, icon button, About summary, `.wallet-link` as the row, `.btn-primary` with `--accent-hover` `#1C5396`/`#7DB0EE`); 120 ms transitions; reduced-motion block; rules at 899/639/399 px (merge into the existing `@media (max-width: 899px)`, `639px`, `399px`; `.verdict-head` stacks).
- `src/liquidoracle/web/templates/check.html`, `samples.html` -- no markup change expected; CSS only.
- `tests/test_web.py:90-110, 352, 438` -- existing patterns for script tags, CSS reads and the "no words in JS" check; add the copy button checks there.
- `README.md:40-44` -- add `copy-address.js` to the JavaScript list.
- Do not touch: `chart.js`, `theme.js`, `progress.js`, `core/`, `services/`.

## Tasks & Acceptance

**Execution:**
- [x] `_bmad-output/planning-artifacts/epics.md` (3.4 note; 3.5 gains the chart.js/progress.js port), `ARCHITECTURE-SPINE.md` AD-17 + Stack, memlogs -- plan first: record the test-runner decision.
- [x] `src/liquidoracle/web/templates/verdict.html`, `static/js/copy-address.js` -- copy button, error, status line, script.
- [x] `src/liquidoracle/web/static/css/app.css` -- interaction states, lift, reduced motion, three breakpoints, forced colours for the copy states.
- [x] `tests/test_web.py` -- button hidden without JS, words on the page not in the script, script loaded once, error has hidden "Error: ", status line is `aria-live`.
- [x] `pyproject.toml`, `uv.lock`, `tests/browser/` -- Playwright dev dependency pinned; a `browser` fixture that tries Chrome then Edge, skips without `CI` and fails with `CI`; browser tests for the matrix rows; sockets allowed to 127.0.0.1 only there.
- [x] `.github/workflows/tests.yml` -- check that `CI` reaches pytest and the browser tests run on all three systems (no skips in the log).
- [x] `README.md` -- `copy-address.js`; the browser tests, that they need Chrome or Edge, skip locally without one and fail on GitHub.
- [x] `deferred-work.md` -- update the 2.5/3.2 JS-test item and close the header-stacking item.

**Acceptance Criteria:**
- Given any page at 320, 360, 600 and 900 px wide, when it renders, then the page does not scroll sideways and the odds line wraps as normal text.
- Given every hover rule in `app.css`, when it is listed, then it is inside `@media (hover: hover)` and a `:focus-visible` rule gives the same look.
- Given `uv run pytest`, when it runs on the three systems in CI, then every test passes and no browser test is skipped.
- Given `CI` is set and no Chrome or Edge can start, when the browser tests run, then they fail with a message naming the browsers tried; without `CI` they skip with that message.

## Implementation Notes

- **Copy button shown by a class, not by removing `hidden`.** `copy-address.js` adds `has-copy` to `<html>` and the stylesheet shows `.copy-button` only under it; clicks are caught on `document`. Reason: a Verdict swapped in by `progress.js` (live lookup) gets a working button without touching `progress.js` (the spec's "do not touch"). Without the script the button is `display: none`, so still nothing dead (AD-18). The script is loaded on the Verdict page and on the fetching page.
- **Status line** is `role="status"` (polite live region); it is emptied and filled 50 ms later so the same words are announced again on a second copy.
- **Bug found by the browser tests in the AI's own code:** the Mac check looked for "Mac" but Chrome's `userAgentData.platform` says "macOS"; now case-insensitive.
- **Bugs found in the screenshots, not by the first tests:** (1) below 640 px the stacked address field grew to about 290 px tall (`flex: 1 1 18rem` becomes a height in a column); `.field-row .text-input { flex: none; }`. (2) At 900 px the stats line folded word by word beside the warning (warning up to 620 px); stats column now `minmax(280px, 1fr)`. Browser tests added for both; both fail on the unfixed CSS.
- **Proof the sideways-scroll test catches the old bug:** on the baseline stylesheet every Verdict page fails at 320, 360 and 600 px (12 of 24); all pass now.
- **Playwright install:** `uv add` could not replace `.venv/Scripts/liquidoracle.exe`, held by an old app instance from 23 Nov (12:25); stopping it was refused by the permission check, so `pyproject.toml` was edited by hand, `uv lock` run, and the package installed with `uv pip install` (same pinned version). Tests run with `uv run --no-sync` until that app is stopped.
- **`browsers.py`** holds the Chrome-then-Edge launch and the CI fail / local skip rule, so `test_launch.py` can test it with a stand-in (two `conftest.py` files would clash on import). An architecture test checks that only `tests/browser/conftest.py` allows sockets, and only to 127.0.0.1.
- **One unexplained failure:** one full run had 1 failure that did not come back in 2 full runs and 5 browser runs; the lift test's fixed 250 ms waits were the likely cause and now use Playwright's retrying `expect`. If GitHub shows a browser failure, look here first.
- **CI:** nothing to add for `CI` (GitHub sets it); `-rs` added so skips and their reasons show in the log. That all three systems find Chrome is proven only by the first push.
- 1,086 tests passed with `CI=true` before review; after the review fixes 1,109, none skipped (1,032 before the story; 71 browser tests, about 100 s).

## Spec Change Log

## Review Triage Log

Three reviewers (blind B, edge case E, verification gap V), 34 findings in 26 groups: 17 fixed, 2 deferred to Story 3.5, 7 rejected.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| E1, E13 | Copy-refused tests expect "Ctrl+C", but on the macOS CI runner the page rightly says "⌘C" | high | `isMac()` reads the real platform; every macOS job would go red | patch: tests set the platform (Windows by default, two Mac variants) |
| B3, E2, V4 | A refusal within 2 s of a copy leaves "Copied" on the tint beside the error | medium | `failed()` did not clear label, class or timer; reproduced by a new test that fails on the old script | patch: `reset()` in `failed()` |
| B4, E4 | Two announcements within 50 ms can leave a stale message | low | the 50 ms timer was not kept; direct fix | patch: one `announceTimer`, cleared first |
| E9 | `clock.install()` without a pause keeps real time running; on a slow machine "Copied" can clear before the check (likely the one unexplained failure) | medium | Playwright's installed clock flows in real time until paused | patch: `install(time)` + `pause_at` after load |
| E14 | The odds "wraps as normal text" check measured a block box, which is always full width | medium | a word-per-line odds line in a wide column would pass | patch: counts lines against words |
| B13 | ⌘C advice for iPhone/iPad users, who have no keyboard | low | regex matched iphone/ipad; direct fix | patch: `/mac/i` only |
| V2 | Safari/Firefox fallback (`navigator.platform`) never tested | gap | all tests had `userAgentData` | patch: `MAC_SAFARI` case |
| B5 | "Copied" is not part of the button's name (WCAG 2.5.3, review-accessibility.md) | low | fixed `aria-label` + `aria-hidden` label | patch: name from the button's own text (hidden "Copy wallet address " + label) |
| B6, E11, E12 | Forced colours: hover rules outside `(hover: hover)` (sticky on touch, breaks the AC); `.btn-primary` has no state there | low | rules read as described; the AC test skipped forced colours | patch: hover part gated, `.btn-primary` added; test checks forced-colours twins too |
| B2 | "never to the network" covers only the Python process; Chrome is outside pytest-socket | medium | true for any browser process | patch: `make_page` blocks and fails on any request outside the app (also tests UX-DR3); AD-17 wording + memlog |
| B1 | Playwright bundles a Node driver; README said "nothing is downloaded" | low | the wheel holds a Node binary; `uv sync` installs ~40 MB | patch: README says so; memlog correction (AD-18's "no Node" is the app's frontend) |
| B10, E6 | `CI=false` or `CI=0` counted as CI | low | `bool(os.environ.get("CI"))`; direct fix | patch: false values skip; test parametrised |
| E10 | The socket guard does not scan `pyproject.toml` or the workflows | low | an opt-out there would lift the block silently; direct extension | patch: scanned too |
| B7 | Scroll test misses pages | low | a long invalid address is echoed back; message page untested | patch: both added; fetching/unavailable need live mode (Story 3.5) |
| B8 | Light theme never loaded in a browser; README said "any screen width" | low | all tests ran dark | patch: light scroll test + lift test in both themes; README "from 320 px wide" |
| B11 | "Cards do not react" checked two properties on three elements | low | a colour or border hover on a card would pass | patch: seven properties, honesty card and Lookup cards |
| B12 | `epic-3-context.md` dropped the "Known gap" line without saying it was resolved | low | trace lost | patch: "resolved in Story 3.3" line; the file is committed apart from the code |
| B9, V1 | Copy on a Verdict swapped in by `progress.js` is untested | gap | no browser test opens a live job | defer: Story 3.5 note in epics + deferred-work |
| V3 | New forced-colours rules run in no test | gap | grep finds no `forced_colors` | defer: Story 3.5 (its AC covers forced colours) |
| E3 | A slower, older failed copy could land after a newer success | low | needs two clicks whose promises settle out of order; fix adds a sequence guard | reject: unlikely, adds state |
| E5 | Missing `.copy-error`/`.copy-status` child throws | false | the template always renders all of them inside `.address-card` | reject |
| E7 | A broken Playwright driver errors instead of skipping | low | only with a broken install; a loud error is right then | reject |
| E8 | Store not closed if the fixture fails during setup | low | temp files of a failed run; fix adds try/finally for no user | reject |
| B14 | The copy error sits inside the card, not under it | false | `mockups/verdict.html` (the design source) puts it inside `.address-card` too, under the address row | reject |
| B15 | `uv.lock` and the spec were left out of the reviewed diff | false | left out on purpose (machine lock, claims file); pinned versions checked by hand: playwright 1.64.1, pyee 14.0.0, greenlet 3.5.6 | reject |
| V5 | Code Map still names ids and a `hidden` button | low | the fix would edit this build's spec; Implementation Notes explain the class approach | reject |

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass (1,032 before this story).

**Manual checks:**
- Headless Edge screenshots of the Lookup page and stop-loss-trader's Verdict page at 1280, 900, 600 and 360 px in both themes; Edvard's own hover, keyboard and copy check in his browser.
