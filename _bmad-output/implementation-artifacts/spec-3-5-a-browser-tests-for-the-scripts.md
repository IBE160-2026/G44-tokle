---
title: 'Story 3.5 part A: browser tests for the scripts'
type: 'chore'
created: '2026-11-24'
status: 'done'
baseline_commit: 'e8d99ba241a0c8870117ee8e8cb4f6a1764884bc'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `chart.js` and `progress.js` run in no automated test: the 45 `chart.js` checks of Story 3.2 ran once in a throwaway script, and `progress.js` (polling, the swap, focus, giving up) was only ever checked by hand. Nothing tests the copy button on a Verdict that `progress.js` swapped in, or the forced-colours rules (deferred from Stories 2.5, 3.2, 3.4).

**Approach:** Extend Story 3.4's `tests/browser/` with a `chart.js` file and a `progress.js` file. For `progress.js` the browser fixture gets a live app: the real job queue and worker, with a stand-in Polymarket that serves the Synthetic Wallets and that each test can hold back or make fail. Add a forced-colours run. Bugs the tests find in the scripts are fixed here.

**Decisions (Edvard, 2026-11-24):** Story 3.5 is built in two parts; this is part A (AI rec). Part B (accessibility checks, the checklist walked by browser tests in place of his own NVDA walk-through, his change, and the stage 1 close) follows in its own spec.

## Boundaries & Constraints

**Always:** Tests drive the real pages in Chrome or Edge as in Story 3.4 (CI fails, never skips; every request outside the app fails the test; sockets to 127.0.0.1 only). Timing uses Playwright's paused clock or retrying `expect`, never fixed sleeps that depend on machine speed. Each test docstring names its FR/UX-DR/AD id (NFR-7 test). The stand-in Polymarket never touches the network.

**Never:** Change what the pages show or say. Move words into a script. Test what the Python tests already prove (bins, counts, sentences).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Slider keys | Tab to "Replays by result", every key | Left/Down, Right/Up one bar, Page Down/Up ten, Home/End the ends; value text = tooltip text | stops at both ends |
| Tooltip | point at a bar, leave | range + count; still there at 299 ms, gone after 300 ms; Esc hides at once; never over the marker's dot or label at 1280, 600, 360 px | N/A |
| Marker | focus/hover; Enter; Esc; click twice; a slider step | tail lit from `data-tail-from`; pinned with "Highlight on: …" in the live region, `aria-pressed`; unpinned with "Highlight off" | stop-loss-trader: tail label "No replay…", no bar lit |
| Build-up | chart scrolled into view | bars grow once, `is-building` gone within 1 s; with reduced motion never | N/A |
| No JS | script blocked | slider, button, tooltip hidden; hint without JS shown | N/A |
| Live lookup | stand-in held back, then released | fetching page polls; on release the Verdict replaces it, tab title and address change, focus on the h1, chart enhanced, copy button copies | N/A |
| Polymarket down / no history | stand-in fails or finds nothing | the matching message page swapped in, focus on its h1 | N/A |
| Progress keeps failing | progress replies fail | 30 failed polls, then no more; the reload link still there | N/A |
| Forced colours | `forced_colors="active"` | copied, hover and focus on copy, theme and primary buttons show a `Highlight` border; tail and active bars `Highlight` | N/A |

</frozen-after-approval>

## Code Map

- `tests/browser/test_pages.py:50-95` -- `make_page` fixture (route guard, platform script, theme, clock), `box`, `style`, `assert_no_sideways_scroll`: move to `conftest.py`/a helper module so new files reuse them; `make_page` takes another base URL for the live app. Existing tests keep their calls.
- `tests/browser/conftest.py` -- `app_url` (Offline Mode, session). Add a function-scoped live app: `Store`, `Jobs`, `Lookup(None, store, seed=44, jobs=jobs)`, `create_app(Settings(offline=False), …)`, `Worker(stand_in, jobs).start()`, stopped after.
- `src/liquidoracle/services/jobs.py:54-108` -- `Worker` calls `fetch_wallet(client, …)`; `NoPolymarketHistory` → no-history result, `PolymarketUnavailable` → stopped.
- `src/liquidoracle/data/client.py:16-45` -- `WalletClient` protocol (`positions_list`, `activity_rows`, `markets`); the stand-in wraps `OfflineClient` over `synthetic.write_small` files, waits on a `threading.Event` in `positions_list`, or raises per test.
- `src/liquidoracle/web/static/js/chart.js` -- behaviour under test (header comment lists it); `window.LiquidOracleChart.enhance`.
- `src/liquidoracle/web/static/js/progress.js` -- `POLL_MS` 1000, `MAX_FAILURES` 30, swap of `#content`, `replaceState`, h1 focus.
- `src/liquidoracle/web/templates/verdict.html`, `fetching.html` -- selectors: `.chart-explore`, `.chart-marker-button`, `.chart-tail-label`, `.chart-tip`, `.chart-live` (`data-highlight-on/off`), `[data-explore]`, `[data-no-explore]`, `#job-block`.
- `src/liquidoracle/web/static/css/app.css` -- `@media (forced-colors: active)` rules under test.
- `tests/test_live_lookup.py:67-77` -- how a live run is assembled in Python tests (reuse the shape, not the HTTP fake).
- Do not touch: `core/`, `services/` (other than a fix a test proves), templates' words.

## Tasks & Acceptance

**Execution:**
- [x] `tests/browser/conftest.py`, `tests/browser/pages.py` (new) -- shared `make_page` and helpers; live-app fixture with the stand-in Polymarket.
- [x] `tests/browser/test_chart_script.py` (new) -- matrix rows Slider keys, Tooltip, Marker, Build-up, No JS; Tab order (slider then button); sharp-trader, stop-loss-trader, favourite-buyer.
- [x] `tests/browser/test_progress_script.py` (new) -- matrix rows Live lookup, Polymarket down / no history, Progress keeps failing; fetching and unavailable pages do not scroll sideways at 320 px (Story 3.4 review B7).
- [x] `tests/browser/test_pages.py` -- forced-colours run; import the moved helpers.
- [x] `src/liquidoracle/web/static/js/*.js`, `app.css` -- only fixes a failing test proves needed; each logged in Implementation Notes.
- [x] `README.md` -- what the browser tests cover.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- resolve the 2.5/3.2 JS-test item and the two Story 3.4 items.

**Acceptance Criteria:**
- Given `CI=true uv run pytest`, when it runs, then every test passes and none is skipped.
- Given each new test, when the behaviour it checks is broken on purpose (one planted break per test group), then that test fails.

## Spec Change Log

## Review Triage Log

Three reviewers (blind B, edge case E, verification gap V), 23 findings in 17 groups: 9 fixed, 2 deferred, 6 rejected. After the fixes 1,144 pass with `CI=true`, 0 skipped.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| B1, E6 | The stand-in's `hold()`/`fail_with()` gate only `positions_list`, though the docstrings say every read | low | `activity_rows` and `markets` read straight through | patch: one `_gate()` in all three reads |
| B2, E5 | Teardown closes the store without checking the worker stopped | low | `join(timeout)` result never checked | patch: assert the thread is not alive |
| B3, V2, E8 | "The address bar changes to the result" is never observed: here the reply's URL equals the fetching URL | medium | `fetching.html` `data-page` is the `?job=` URL itself; a `replaceState(pageUrl)` would pass | patch: wording in the test and deferred-work; the redirected case is deferred |
| B4 | progress.js's 404 "gone" path and the failure count resetting after a good reply are untested | low | read progress.js: both branches exist, no test reaches them | patch: two tests |
| V1 | The marker tail's 300 ms stay and hovering onto the tail label are untested | gap | the test used a retrying expect on the real clock | patch: paused-clock test |
| B6 | Tooltip "hoverable" (1.4.13), click on a bar unpinning, slider blur, the Alt guard untested | low | listeners exist in chart.js, no test drives them | patch: two tests |
| B9, E2, E3 | Tests rely on the Synthetic Wallets' shape (marker ≥ 11, > 30 bars, tail_from > 0) without saying so | low | a data change would fail as a confusing chart.js bug | patch: precondition asserts |
| E4 | Build-up test could scroll back before the observer saw the chart leave, so no second crossing (intermittent timeout) | medium | `scrollTo(0, 0)` was not waited on | patch: OBSERVE counts leaving; test waits for it |
| E7 | The 30-poll loop is a fixed 900 steps; route lag on a slow machine could end it early | low | steps can pass with no poll timer pending | patch: loop until 30 failures or 60 s real time |
| B12 | README browser-test paragraph too dense, no command for the browser tests alone | low | one long paragraph; README is read by newcomers | patch: intro, command, four bullets |
| V2 (rest), B4 (rest) | A result fetch ending at another URL (re-queued job), `start()` following a new fetching block, and the `location.assign` fallbacks run in no test | gap | needs a job that ends without a snapshot; more than this port | defer |
| E1 | `clock.pause_at(START + 5 s)` after `goto` throws if a page takes over 5 real seconds to load | low | moved unchanged from Story 3.4's `make_page`; pre-existing | defer |
| B5 | Giving up silently after 30 polls is a UX gap; the route is set after the first poll may fire | false | the silent stop with the reload link is the planned design (Story 2.5, AD-18); the early poll answers "running", which only resets the count (Implementation Notes) | reject |
| B7 | The 45 checks are not traceable; planted breaks not recorded | false | Implementation Notes list every planted break; the spec is committed with the code | reject |
| B8 | Placement test checks only horizontal on-card and only the keyboard | false | the pointer path calls the same `placeTip(i)`; chart.js's own `onCard` is horizontal and the title sits above the plot | reject |
| B10 | The forced-colours rule probe misses nested rules or longhands | low | the app's rules are top-level `border-color`; a rewrite would fail loudly, not pass silently; fix adds a recursive walker | reject |
| B11, B13 | Part B entry has `source_spec: none`; sprint key not split; exact class-string asserts; redundant `hold()` | false | `none` is the split format of step 1; epics says 3.5 is done after part B; exact strings are intended (also prove no `is-building`) | reject |

## Design Notes

The stand-in Polymarket sits behind the `WalletClient` protocol, not at the HTTP level: the HTTP path is already tested in `tests/test_live_lookup.py`, and serving the Synthetic Wallets gives a Verdict with a chart (the HTTP fixtures' Wallets are all *Not enough data*). The browser cannot tell the difference: it sees the same pages, job and progress replies.

## Verification

**Commands:**
- `CI=true uv run pytest -rs` -- expected: all pass, 0 skipped (1,109 before this part).
- `CI=true uv run pytest tests/browser -rs` -- expected: all pass.

## Implementation Notes

- **No script or stylesheet changed.** Every new test passed against the scripts as they were; no bug was found in `chart.js`, `progress.js`, `copy-address.js` or the forced-colours rules, so the "fixes a failing test proves" task had nothing to do.
- **Shared helpers:** `tests/browser/pages.py` holds the platform scripts, `box`, `style`, `assert_no_sideways_scroll`, `overlaps` and `opened(browser, app_url)`, which hands out `make(path, width, height=800, base=…)`. The route guard is per context and allows only the app the page was opened on (`base`, default the Offline Mode app). `conftest.py` gained `sample_root` (the Synthetic Wallets, written once per session and shared by both apps), `serving(app)`, `make_page`, `StandInPolymarket` and the function-scoped `live_app`. Existing tests keep their calls.
- **Stand-in Polymarket:** wraps `OfflineClient` behind the `WalletClient` protocol. `hold()`/`release()` use a `threading.Event` waited on in `positions_list` (at most 60 s, then `PolymarketUnavailable`, so a failed test never leaves the worker stuck); `fail_with(error)` raises on every read; an address it does not know gets empty lists, as Polymarket answers an unused address, which gives *No Polymarket history found* through the real `NoPolymarketHistory` path. Teardown releases it, stops and joins the worker, then closes the store.
- **"Address changes" (Live lookup row):** the server renders the result at the fetching page's own address (`/wallet/<a>?job=<id>`), so the address text does not change in this flow. The test records `history.replaceState` calls with an init script and checks that progress.js put the result reply's URL there, then reloads and gets the Verdict, not the fetching page.
- **Progress keeps failing:** the page clock is paused and moved in 100 ms steps while every progress reply is a 500 from a Playwright route, so no poll is skipped or doubled; after 30 failures another minute of page time brings no 31st. A first poll that fires before the route is set reaches the app and answers "running", which only resets progress.js's failure count, so the count of 30 still holds.
- **Build-up:** the test adds its own IntersectionObserver after chart.js's and waits (retrying `expect`) until it has fired, so chart.js has heard too; the paused clock then holds the animation frame, `run_for(20)` starts the build-up and `run_for(1000)` ends it. It also checks that the longest transition (last bar's delay plus duration, the marker's 560 + 260 ms) fits in 1,000 ms.
- **Forced colours, Chrome's own border:** in Chrome and Edge's forced-colours mode the browser itself gives a hovered or focused `<button>` a Highlight border, even with every app rule removed (checked by deleting the rules in the page). So the hover/focus test also checks, in the page, that one of the app's own `@media (forced-colors: active)` rules matches the button in that state and sets a Highlight border (the rule is there for other browsers). The copied-state test blurs the button first, so only the `is-copied` rule can draw its border.
- **Tooltip placement sweep:** steps through every bar with the keyboard (the same `placeTip` as pointing) for sharp-trader, stop-loss-trader and favourite-buyer at 1280, 600 and 360 px, with reduced motion so the marker's build-up offset does not move the boxes. It also checks that the tooltip stays on the card.
- **Planted breaks (spec AC 2):** each was applied alone, the matching tests run, then the file restored. All were caught: chart.js `PAGE_STEP` 5; ArrowDown stepping up; `HIDE_AFTER_MS` 250; Esc not hiding the tooltip; placement ignoring the marker (5 of 9 page/width cases fail); tail starting one bar late; Esc not unpinning; slider `tabindex="-1"`; `observer.disconnect()` removed (build-up twice); `BUILD_MS` 1500; reduced motion ignored; slider not `hidden` without JS; progress.js without the h1 focus, the chart enhance, the title or `replaceState`; `MAX_FAILURES` 31; never giving up; a 360 px `min-width` on the fetching page's address line; each of the four forced-colours rules removed.
- **After review (coordinator, 2026-11-24):** the stand-in's hold and failure now gate all three reads; the live app's teardown asserts the worker thread stopped; the live-lookup wording says only the same-URL case is checked. New tests: a 404 from the progress URL swaps the result in; one good reply resets the failure count (29 + 30 failed polls before it stops); the tail's 300 ms stay and hovering onto the tail label (paused clock); hovering onto the tooltip; a click on a bar unpinning; slider blur hiding the tooltip; Alt+ArrowLeft not stepping. Tests that depend on the Synthetic Wallets' shape assert it first. The build-up test waits for the chart to leave view before scrolling back, and the 30-poll loop runs until 30 failures or 60 s of real time. Each new test failed on its own planted break (tail 250 ms, tail label or tooltip not hoverable, click keeping the pin, blur keeping the tooltip, Alt stepping, the count never resetting, 404 treated as a failure).
- **Count:** 35 new browser tests; `CI=true uv run pytest -rs` gave 1,139 passed, 0 skipped (1,109 before) before the review additions, which add 5 more.
