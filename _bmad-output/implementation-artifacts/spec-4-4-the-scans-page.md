---
title: 'Story 4.4: The Scans page'
type: 'feature'
created: '2026-11-26'
status: 'done'
baseline_commit: '60a44e1e4b2a87e4f3b83ecb0a538195911d22f9'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 4.3 can run, stop and resume a Scan, but only from code. The user has no page to start one, watch it or come back to it (FR-16, UX-DR30 to UX-DR32).

**Approach:** A server-rendered Scans page at `/scans` (top bar link *Scan wallets*): the New Scan form, the Scan list with status and Resume, and a live progress bar. A small `scans.js` only enhances it (live time estimate, live warning, progress polling); without JavaScript everything still works by reloading.

## Boundaries & Constraints

**Always:**
- **Form** `POST /scans` (Cut-off Date `date` field, Number of Wallets `number` field default 200, button "Start Scan"), then redirect to `/scans` (post/redirect/get). Errors word for word: missing or unreadable date "Choose a Cut-off Date."; today (UTC) or later "The Cut-off Date must be in the past."; anything but a whole number 10 to 500 "Enter a whole number from 10 to 500.". Errors follow the Lookup form's pattern (under the field, `aria-describedby`, `aria-invalid`, hidden "Error:", focus to the first field in error), the page answers 400, values are kept, nothing starts.
- **Warning** when the date is less than 90 days before today: "Very few bets were resolved after this date, so the Hold-up Test and Copy Test may have too little to test." Without JS, the first submit shows it under the date with the values kept, and a second "Start Scan" starts (a hidden `confirmed` field). With JS it shows as soon as the date is chosen and sets `confirmed`.
- **Time estimate** under the number, labelled rough: "Rough estimate: about 2 hours at 5 requests per second". JS updates it from `GET /scans/estimate?wallets=N` (JSON `{text}`), so every word stays in Python (AD-25).
- **Running Scan:** info box "A Scan is running (Reading Markets: 34 of 100). You can start a new one when it finishes." with the job's own step text; "Start Scan" stays focusable with `aria-disabled="true"` and a POST is refused. A real progress bar (`<progress>`, `aria-valuetext` = step text such as "84 of 200 Wallets checked"; no value while the total is 0).
- **Scan list,** newest first, a table in a focusable named scroll area: run date ("26 Nov 2026"), Cut-off Date ("1 July 2025"), Wallets (N), Watchlist size (Skilled (high confidence) `scan_whole` results; "—" with hidden "not finished" until done), status: "Finished", "Waiting to start", "Running: <step text>", "Interrupted at 120 of 200", "Stopped at 120 of 200: Polymarket did not answer" (no "at …" while the total is 0), "Failed", "Data rebuilt, cannot resume". Resume button `POST /scans/<id>/resume` named "Resume Scan (Cut-off Date 1 July 2025)" for interrupted and stopped Scans only. No results of an unfinished Scan.
- **Empty state:** "No Scans yet. A Scan checks the top Wallets by profit made before a date you choose."
- **Polling** (`scans.js`): GET `/jobs/<id>/progress` once a second; updates bar, info text and step; a polite live region announces only when the step changes, at each new 10% and once at the end; at the end it refetches `/scans` and swaps `main` in (as `progress.js` does).
- **Titles:** "Scans · LiquidOracle"; while a Scan runs "84/200 · Scan · LiquidOracle" from the job's done/total, server-rendered and updated by JS. **Decision (Edvard, 2026-11-26, AI rec):** the tab-title counter is built now; the favicon progress ring slips to deferred work and the plan says so. Rejected: both now (time), both later.
- **Estimate counts only what a Scan does today (Edvard, 2026-11-26, AI rec):** the Gamma list, 100 Market reads, 3 × N before parts and N after parts. Once a live Scan has finished, it is recalibrated from that Scan's own time per planned request and says "based on your last Scan". Epic 6 adds the Copy Sample price term with its phase. Rejected: a guessed price term now (counts work the app cannot do yet).
- **Spec kept whole (Edvard, 2026-11-26, AI rec)** at about 2,400 tokens: one goal. Rejected: a split into form/list and live progress.
- **Offline Mode:** read-only fields (1 July 2025; "Whole Sample Dataset"), info box "Offline Mode scans the whole Sample Dataset with its Cut-off Date, 1 July 2025.", no estimate. Until Story 4.6 adds an offline worker, "Start Scan" is unavailable (focusable, `aria-disabled`) with "Offline Scans are not ready yet." and the POST is refused; 4.6 removes that line.
- **POSTs** are refused (403) when an `Origin` header is present and is not this app's own origin, so another web page cannot start a Scan.
- Words, dates and numbers come from `core/phrases.py` or the new service; templates only place them. Existing tokens, interaction states and 900/640/400 px breakpoints; forced colours and reduced motion like the other pages. Tests network-blocked, each naming its FR, UX-DR or AD.

**Never:** no Watchlist page or link (4.5; the Watchlist size is plain text until then), no offline Scan running (4.6), no Hold-up or Copy Test phase (Epics 5–6), no change to how a Scan runs (4.3).

</frozen-after-approval>

## Code Map

- `web/__init__.py` -- `create_app(settings, lookup)`; add `scans` (the new service) as a parameter and routes `GET/POST /scans`, `POST /scans/<int:id>/resume`, `GET /scans/estimate`. `/jobs/<id>/progress` already serves scan jobs. 404/405 handler stays.
- `web/templates/base.html` -- nav gets "Scan wallets"; replace the `nav_current` block with a `nav` variable so each link can be current.
- `web/templates/check.html` -- the form/error pattern to copy (`field-label`, `text-input`, `error-message`, `hint`, `info-box`).
- `web/static/js/progress.js` -- pattern for polling and swapping `main`; leave it unchanged.
- `web/static/css/app.css` -- tokens, `.info-box`, `.btn-primary`, breakpoints; no table styles yet.
- `services/jobs.py` -- `Jobs.start_scan(cutoff: date, size, *, seed)` (None while another Scan runs), `Jobs.resume_scan(scan_id)`; `FINISHED` messages.
- `data/store.py` -- `Scan`, `Job`, `JobStatus`, `scan()`, `scan_results()`; add `scans()` (every Scan with its latest job, newest first). `INTERRUPTED_MESSAGE` overwrites the step text, so status text uses done/total.
- `services/scan.py` -- `MARKET_COUNT`, `SHORTLIST_FACTOR`, progress messages; `core/funnel.py` untouched.
- `services/lookup.py` -- pattern for a page service with finished text; `short_address`.
- `__main__.py:serve` -- build the new service (live: with `Jobs`, `settings.seed`, `settings.polymarket_requests_per_second`; offline: without).
- `core/phrases.py` -- add `long_date` ("1 July 2025"), `short_date` ("26 Nov 2026"), `rough_time`.
- `records.Verdict.SKILLED` -- the Watchlist size counts this verdict.
- `tests/test_web.py` (`every_page` frame/heading/label checks, `live` fixture), `tests/browser/` (`live_app`, `pages.py`) -- patterns.

## Tasks & Acceptance

**Execution:**
- [x] `epics.md`, `EXPERIENCE.md`, `epic-4-context.md`, `deferred-work.md` (favicon ring), memlogs -- the tab-progress and estimate decisions and the interim offline line -- plan before code.
- [x] `core/phrases.py` -- dates and `rough_time` (minutes rounded to 5 under an hour, half hours above) -- AD-25.
- [x] `data/store.py` -- `scans()` -- FR-16.
- [x] `services/scans_page.py` (new) -- form check, list rows with status text, estimate, start/resume; constants `MARKET_REQUESTS = 15`, `PART_REQUESTS = 40` `[ASSUMPTION]` -- FR-16, UX-DR30, UX-DR31.
- [x] `web/__init__.py`, `templates/base.html`, `templates/scans.html` (new), `static/js/scans.js` (new), `static/css/app.css`, `__main__.py` -- the page -- UX-DR30 to UX-DR32.
- [x] `tests/test_phrases.py`, `tests/test_scans_page.py` (new), `tests/test_web.py`, `tests/browser/test_scans_script.py` (new) -- every matrix row below, the frame/heading/label checks for `/scans`, polling, announcements and title in a real browser.

**Acceptance Criteria:**
- Given each invalid form input, when submitted, then the right sentence shows under its field with focus there, and no `scan` row exists.
- Given a running Scan, when the page is open with JS, then the bar, step text and tab title follow the job and the page shows the list when it finishes, with at most one announcement per 10% step.
- Given a stopped Scan, when its Resume button is pressed, then a new job is queued for it and the list shows it running; given a failed or rebuilt Scan, no Resume button exists and a forged POST changes nothing.
- Given the whole suite, when it runs network-blocked, then every test passes.

## Implementation Notes

- Built in this session without a helper (Edvard chose helpers for review only). Files: `core/phrases.py` (`long_date`, `run_date`, `rough_time`), `data/store.py` (`scans`, `scan_seconds`, `watchlist_sizes`), `services/scans_page.py` (new), `services/lookup.py` (`store`, `jobs` read-only properties so `create_app` can build the Scans service when none is passed), `web/__init__.py`, `templates/base.html` (a second nav block, `nav_scans_current`), `templates/scans.html`, `static/js/scans.js`, `static/css/app.css`, `__main__.py`, README (`scans.js` line).
- Choices the spec left open: Resume buttons are hidden while another Scan runs (one at a time; the running box says why). A queued job reads "Waiting to start". The list's heading is "Your Scans". `scan_seconds` leaves interrupted runs out (their end is stamped at the next start). When the job ends, `scans.js` swaps only the running box, the list and the button state, not the whole `main`, so a half-typed form is kept.
- Found while building: the hidden labels in the table escaped its scroll box at 400 px (23 px sideways scroll), fixed with `position: relative`; the Status column squeezed to one letter on a phone, fixed with a minimum width so the table scrolls in its box; focus to the first field in error was missing at first (caught in the diff check), added with `autofocus`.
- Tests: `tests/test_scans_page.py` (45), `tests/browser/test_scans_script.py` (6), Scans pages added to `test_web.py`'s every-page checks, phrase tests. Full suite 1,442 passed with `CI=true`; affected files re-run after the autofocus fix.

- After review: `data/window.cutoff_day` (the inverse of `cutoff_at`) replaces both `fromtimestamp(scan.cutoff)` calls; POSTs also need a local host name (`LOCAL_NAMES`); the date field's `max` is yesterday (`NewScanForm.latest`); `scan_seconds` is None for a Scan with an interrupted run, and the estimate takes the newest finished Scan whose time is known; `scans.js` keeps focus, names a step by its words too, resets the 10% bucket and restores the title when it gives up; `__main__` no longer builds the Scans service itself (one construction site, in `create_app`). EXPERIENCE.md and epics UX-DR31 name "Waiting to start" and "Your Scans". Full suite 1,445 passed with `CI=true`.

## Spec Change Log

## Review Triage Log

Pass 1 (2026-11-26): three reviewers (blind, edge case, verification gap), 31 findings; 16 fixed as patches, 15 rejected, 0 deferred, no loopback.

| # | Finding | Verdict | Evidence / route |
|---|---------|---------|------------------|
| VG1 | Recalibration rules untested: newest Scan, rebuilt skipped, resumed runs added | medium | Gap filed with mutations that pass; patch: `test_ux_dr30_recalibration_follows_the_newest_usable_scan_and_adds_up_resumes`. |
| VG2 | The ScansPage `serve()` builds is never tested | medium | Real; patch: the serve test now GETs `/scans` and checks a startable form at the configured pace. |
| VG3 / BH10 | ScansPage built in two places (`serve` and `create_app`) | low | Two sites could diverge; patch: `serve` uses `create_app`'s own (deletion). The fallback stays: about 20 test call sites use it. |
| BH1 / EC1 / EC2 | A Cut-off Date before 1970 makes `/scans` answer 500 for good on Windows | high | Reproduced: `fromtimestamp(-315619200, UTC)` raises OSError here; patch: `window.cutoff_day` in both places, round-trip test from year 1. |
| BH2 / EC10 | DNS rebinding passes the Origin check (Origin equals the attacker's Host) | medium | Real: `host_url` comes from the Host header; patch: POSTs also need `127.0.0.1` or `localhost`; tested with and without a port, and `Origin: null`. |
| BH3 | The 403 page says "Page not found" | low | Real but only a forged cross-site POST sees it, and a better page needs new wording; rejected. |
| BH4a / EC3 | Date field `max` is today, which the server rejects | low | Real; patch: `max` is yesterday (direct correction). |
| BH4b | "Today" is UTC, so just after local midnight yesterday's local date is refused | false | The plan's rule: a Cut-off Date is 00:00 UTC and "today or later" is refused; in UTC that date is today. |
| BH5a / EC8 | Interrupted runs dropped, so a resumed Scan's time reads too short | medium | Real; patch: `scan_seconds` is None when a run was interrupted, and the estimate uses the next finished Scan or the set pace. |
| BH5b / EC7 | Queued time counts; a job queued over a restart counts the downtime | low | Needs Resume pressed and the app closed in the second before the worker claims it; the fix needs a new column; rejected. |
| BH5c / EC9 | "Based on your last Scan" ignores a changed pace setting | low | The default is already the maximum, 5 per second, and the text says where the number comes from; the fix needs the pace stored per Scan; rejected. |
| BH6 | Keyboard focus lost when the list is replaced at the end of a Scan | medium | Real (`innerHTML` swap); patch: focus returns to the same element or the list heading; browser test. |
| BH7 / EC6 | Tab title stays "58/100" after polling gives up | low | Real, one-line fix; patch. |
| BH8 | Refused start or Resume redirects with no message | low | The list then shows the running Scan; a message needs new wording; rejected. |
| BH9 | "Waiting to start" and "Your Scans" only in code, not in the plan | low | Real (CLAUDE.md: plan first); patch: EXPERIENCE.md Scan list row and epics UX-DR31. |
| BH11 | `RunningScan.info` constant field; seven constants passed to the template | low | No named harm; rejected. |
| BH12 | Every estimate request reads the whole Scan list | low | Local SQLite with a handful of rows, debounced; rejected. |
| BH13 | `rough_time` docstring says "under 5 minutes" below 5 minutes; the cut is 2.5 | low | Real; patch: docstring corrected. |
| BH14 | Offline info box promises a Scan while the button says not ready | low | The box says what an Offline Scan covers, the line under the button says not yet; 4.6 removes that line; rejected. |
| BH15 | Spec and AI log not in the diff | false | Both are committed at the end of the story, as in 4.1 to 4.3. |
| EC4 | Two steps with the same phase and total are not announced | low | Real when the Market count equals the shortlist length; patch: the step key includes the words without counts; browser test fails on the old key (checked). |
| EC5 | A count that goes back keeps the old 10% bucket | low | Real (resumed run); patch: the bucket is always updated. |
| EC11 | Step changes announce on top of 10% steps | false | The frozen spec announces a new step, each new 10% and the end. |
| EC12 | The AC says a resumed Scan shows running, the row says "Waiting to start" | false | Queued until the worker claims it (within a second), then "Running: …". |

## Design Notes

- Estimate = (Gamma list pages + 100 × `MARKET_REQUESTS` + 4N × `PART_REQUESTS`) ÷ the set pace; for N = 200 at 5/s that is about 6,700 s, "about 2 hours", matching EXPERIENCE's example. Recalibrated: last finished live Scan's summed job time ÷ its planned requests, times the new plan, labelled "based on your last Scan".
- The service is named `scans_page` so it is not mixed up with `services/scan.py`, which runs Scans.

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass, 0 skipped with `CI=true`.

**Manual checks:**
- Screenshots of `/scans` (empty, errors, warning, running, list) in both themes and at 400 px, via Playwright with installed Edge.
