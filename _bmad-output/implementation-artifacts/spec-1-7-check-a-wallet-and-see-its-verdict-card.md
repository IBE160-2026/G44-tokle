---
title: 'Story 1.7: Check a wallet and see its Verdict card'
type: 'feature'
created: '2026-11-20'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '86a8042bce61b486076deacb4eabfb42c203e6e2'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The app serves only a placeholder page. The examiner cannot enter an address, pick a Sample Wallet or see a Verdict, and CI does not prove the README's commands work.

**Approach:** Build the *Check a wallet* page, the Verdict page and *Page not found* as server-rendered Jinja2 pages over a new `services/lookup.py`, which reads the Wallet's stored snapshot and runs the Skill Test. Wire `open_sources` into `create_app`, bundle IBM Plex Serif and the logo, add the banned-words test and a CI job that runs the README's three commands.

## Boundaries & Constraints

**Always:**
- Every page works without JavaScript (AD-18): the form is a plain `GET /?address=…`. Pages declare English and have one `h1`; "Skip to content" is the first Tab stop; every page has the top bar (logo, brand, *Check a wallet*, plus the Offline pill in Offline Mode) and its tab title (UX-DR4/5/8).
- Lookup: trim spaces; "Enter a wallet address." when empty; "This is not a valid wallet address. It should start with 0x and have 42 characters." when not `0x` + 40 hex. The error goes under the field, the field gets `aria-invalid` with the error tied to it, focus stays in the field (`autofocus`), and nothing is fetched. A valid address redirects to `/wallet/<lower case>` (FR-1, UX-DR13/16).
- Offline: an address outside the Sample Dataset shows "Not available offline. In Offline Mode only the Sample Wallets below can be checked." on the Lookup page, and also on `/wallet/…` when it is opened directly (FR-14, UX-DR18).
- Verdict card: eyebrow "Wallet analysis"; the hero `h1` with dots `aria-hidden`, read as "Verdict: …"; all four variants (●●● / ●●○ / ○○○ / dashed *Not enough data* with no dots); the odds sentence; an address card (no copy button); the stats line "N resolved bets · Real PnL $X" and "Data stored …". *Not enough data* shows `phrases.not_enough_data`, with no odds and no p-value (FR-8, FR-10, UX-DR20/23).
- Every number and odds phrase on a page comes from `core/phrases` (AD-25). New helpers go there.
- `web` imports only `services`, `records` and `settings` (AD-1). The mode is read only in `__main__` and for the Offline pill (AD-13).
- Colours, type and spacing come from the DESIGN.md light tokens as CSS custom properties. IBM Plex Serif 600/700 (WOFF2, @ibm/plex-serif 2.0.0) and its OFL licence are served from `web/static/fonts/`. The logo (32 px) and the favicon come from `mockups/logo/`. Nothing is loaded from the internet (UX-DR1/3/6).
- Bad URLs (`/wallet/abc`, unknown paths) get a 404 *Page not found* page with a link to *Check a wallet* (UX-DR7).
- Every test names its FR, AD or UX-DR, and all tests run with sockets blocked.

**Never:**
- No hover or lift states and no responsive details: moved to Story 3.4 (Edvard, 2026-11-20). A plain `:focus-visible` ring stays, because it is accessibility, not polish.
- No chart, honesty notes, copy button or Exit PnL warning (Stories 3.1–3.4); no live client, jobs or fetching state (Epic 2); no stored Skill Test results.
- No `gh`, no `git add .`, no merge.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Sharp trader | loaded offline.db, Seed 44 | `/wallet/<sharp>`: "Skilled (high confidence)", ●●●, odds sentence, "100 resolved bets · Real PnL $2,000" | N/A |
| Coin-flipper | coin-flipper 0 | *No evidence of skill*, ○○○ | N/A |
| Thin / hand-check | 29 / 10 bets | dashed hero; "29 resolved bets; at least 30 are needed for a Verdict (1 more)"; no odds, no p | N/A |
| Upper case URL | `/wallet/0xAB…` | redirect to the lower-case URL | N/A |
| Bad URL | `/wallet/abc`, `/nope` | 404 *Page not found* | N/A |
| Not in sample | valid address, offline | "Not available offline …" | NotAvailableOffline → message |
| Not loaded | Sample Wallet, empty or missing offline.db | "The Sample Dataset is not loaded yet. Run `uv run liquidoracle load-sample` in the repository folder, then reload this page." | N/A |
| Live run | valid address, no `--offline` | "Live lookups are not built yet. Start the app with `--offline` to check the Sample Wallets." | N/A |

**Decisions (Edvard, 2026-11-20; all the AI's recommendations):**
- Polish (dark theme and toggle, hover and lift, responsive details) moves to Story 3.4 now, as the plan allows when Epic 1 runs late.
- After seeing the pages, Edvard pulled the dark theme back in: **dark by default** (not the system setting, his 2026-10-16 choice), with the toggle "Dark theme" (UX-DR2) remembered in the browser and still switching if storage is blocked (`web/static/js/theme.js`, loaded as a file, no inline script). The pages stay complete without JavaScript: dark, with the toggle hidden. Hover and responsive stay in 3.4.
- Edvard: the Verdict hero's dots sit beside the Verdict for every Verdict (the long *Skilled (high confidence)* wrapped the whole text below the dots).
- Spec kept whole (~2,200 tokens): one goal, and the CI job needs the Verdict page.
- Sample Wallets list: the five small Synthetic Wallets plus one item "Coin-flipper" (coin-flipper 0) and the note "and 999 more coin-flippers, checked by address". Rejected: all 1,000 items; no coin-flipper.
- A Sample Wallet not in `offline.db` gets the "not loaded yet" message. Rejected: loading it on the spot inside a page request (AD-5 keeps fetches for the Epic 2 worker).
- A live run gets the "Live lookups are not built yet" message until Story 2.5. Rejected: hiding the address field outside Offline Mode.

</frozen-after-approval>

## Code Map

- Exit PnL (issues.md, Story 1.2: split or merged Positions and sell fees) is not shown in 1.7; the question moves to Story 3.3.
- `src/liquidoracle/web/__init__.py`, `web/templates/check.html` -- placeholder app and page; replace. `create_app(settings)` becomes `create_app(settings, lookup)`.
- `src/liquidoracle/__main__.py` -- `open_sources` → `Sources(client, store)`; `serve` builds the app. Pass a `services.lookup.Lookup` built from `Sources` and `settings.seed`.
- `src/liquidoracle/services/fetch.py` -- `skill_result(store, wallet, seed=)`; reuse.
- `src/liquidoracle/data/store.py` -- `latest_snapshot(wallet).completed_at` (epoch s) for "Data stored"; `wallet_count()`.
- `src/liquidoracle/data/offline.py` -- `OfflineClient` builds its index once (issues.md: doesn't see files written after start). Add a rebuild on a miss when `sample_files(root)` has changed.
- `src/liquidoracle/data/errors.py` -- `NotAvailableOffline` (a `LookupError`).
- `src/liquidoracle/data/synthetic.py` -- `small_wallets()` names, `coin_flipper(i)` names `coin-flipper-0000`, private `_address(name)`: expose it so the list doesn't need to read files.
- `src/liquidoracle/core/phrases.py` -- `odds`, `money`, `not_enough_data`; add the odds sentence, the bets count and the stored date.
- `tests/test_architecture.py` -- import and mode-read rules; `web` may import `services`, `records` and `settings`.
- `tests/test_phrases.py` -- its scan forbids "1 time in" and similar outside `phrases.py`.
- `tests/test_web.py` -- replace the placeholder tests.
- `mockups/lookup.html`, `mockups/verdict.html` (lines 114-150, 398-438), `mockups/logo/*.svg` -- markup and CSS to adapt; the DESIGN.md and EXPERIENCE.md specs win where they differ.
- `.github/workflows/tests.yml` -- add the README job. `README.md` -- three commands and the address to open.

## Tasks & Acceptance

**Execution:**
- [x] `sprint-status.yaml` -- 1-6 `done` (its own first commit); 1-7 `in-progress`, then `review` at the end.
- [x] `epics.md`, `sprint-status.yaml`, memlog -- record the polish move to Story 3.4 (plan first).
- [x] `core/phrases.py` -- `odds_sentence(p)`, `resolved_bets(n)`, `stored_at(epoch, tz)` -- AD-25.
- [x] `services/lookup.py` -- `Lookup(client, store, seed)`: `check(address)` → typed outcome (verdict / not available offline / not loaded / live not built); `sample_wallets()` -- FR-1, FR-14.
- [x] `data/offline.py`, `data/synthetic.py` -- index refresh; public `address_of(name)` and display labels.
- [x] `web/__init__.py`, `web/templates/{base,check,verdict,message,not_found}.html`, `web/static/{css/app.css,fonts/*,img/*}` -- the pages.
- [x] `__main__.py` -- wire `open_sources` → `Lookup` → `create_app`.
- [x] `tests/test_web.py`, `tests/test_lookup.py`, `tests/test_wording.py`, plus additions to the phrase, offline and architecture tests -- the matrix, the a11y markup, the banned words (NFR-8), and no remote URLs in templates or CSS.
- [x] `.github/workflows/tests.yml`, `README.md` -- the README job (NFR-1, AD-17); update the status line and commands.

**Acceptance Criteria:**
- Given `uv run pytest`, then all tests pass with sockets blocked.
- Given the README's three commands on this PC, when the sharp trader's page is requested, then it contains "Skilled (high confidence)".

## Implementation Notes

- Implemented directly in the main session; subagents only for the review (Edvard's standing call).
- 1-6 `done` committed first (86a8042); the spec's baseline is that commit, so the review diff holds only Story 1.7.
- Plan first: epics.md Story 1.7 polish note says "Moved to Story 3.4"; UX memlog entry for Edvard's decision.
- `web` may not import `core` (AD-1), so `services/lookup.py` hands the templates finished text (`VerdictCard`, `Notice`, `SampleList`), all numbers from `core/phrases`. New phrase helpers: `odds_sentence`, `count`, `resolved_bets_word`, `stored_at` (English month names whatever the locale; local time).
- Only one Verdict needs a dot-free hero: `FILLED_DOTS` maps the four Verdicts to 3 / 2 / 0 / None. No Sample Wallet reads *Likely skilled*, so that variant is tested with a fixed card through a stand-in lookup.
- The Lookup form is `GET /?address=…`; a valid address redirects (302) to `/wallet/<lower>`; an upper-case `/wallet/` URL redirects (301). Errors re-render the page with `autofocus`, `aria-invalid` and `aria-describedby="address-error address-hint"`.
- "Is it in the Sample Dataset?" asks the client through the protocol (`positions` raising `NotAvailableOffline`), so `services` never reads the mode (AD-13). A Sample file still being written counts as not loaded.
- `OfflineClient(files, list_files=…)`: on a miss it lists the files again and rebuilds the index if the list changed. `open_sources` passes it; `load-sample` keeps its fixed list. `Store.has_snapshot` added for the Lookup page's cheap check.
- `services/fetch.stored_result` returns the result with the snapshot's `completed_at` for "Data stored …"; `skill_result` now calls it.
- Not in the plan, added by the AI: `run --offline` outside the repository folder stops with load-sample's plain message (the Sample files would not be found); a database that cannot be opened stops `run` with a plain message instead of a traceback.
- Fonts: `@ibm/plex-serif@2.0.0` `fonts/complete/woff2/IBMPlexSerif-{SemiBold,Bold}.woff2` and `license.txt` (saved as `LICENSE.txt`) from jsDelivr. Only 600 and 700 are bundled (AD-18), so 400-weight serif text (ledes, odds line) uses the system serifs (`--serif-text`) instead of a stretched 600. Not in the plan; a CSS choice.
- Light theme only; a plain `:focus-visible` ring and the forced-colours rule for the filled dots are kept (accessibility). The Verdict head grid does not stack yet (responsive moved to 3.4).
- Smoke run on this PC with the README's three commands: load-sample 18 s, 1,005 Wallets; sharp trader page contains "Skilled (high confidence)" (odds "about 1 time in 5,000"); coin-flipper 0 *No evidence of skill* (Real PnL −$226, "more than half the time"); stop-loss trader *Skilled (high confidence)*; favourite buyer *No evidence of skill*; thin wallet and hand-check *Not enough data*.
- An AI slip caught by its own test: the first `stored_at` test used a wrong epoch for 15 Oct 2026; fixed to 1,792,065,720.
- The requirement-name rule (NFR-7) caught 7 new tests citing only UJ-3 or Edvard's decision; FR/AD ids added.
- Full suite: 498 passed, 1 deselected (416 before + 82 new).
- Names differ from the task list: `Lookup.check` returns (address, error) and `wallet_page` the outcome; `sample_list()` not `sample_wallets()`; `count` + `resolved_bets_word` not `resolved_bets`; display labels live in `services/lookup.py` `SAMPLE_LIST`, not in `synthetic.py`. No architecture test changed: the existing rules already cover the new modules.
- After review, Edvard looked at the pages (2026-11-20). Two changes from him:
  - Dots: on *Skilled (high confidence)* the dots sat above the Verdict, on *No evidence of skill* beside it (the long Verdict wrapped as a whole). `.verdict` no longer wraps; the text wraps beside the dots.
  - Dark theme pulled back into 1.7, dark by default. `:root` holds the `-dark` tokens and `:root[data-theme="light"]` the light ones; `web/static/js/theme.js` (in `<head>`, a file, no inline code) applies a stored "light" pick before drawing, shows the toggle (hidden in the HTML, so no dead button without JavaScript), switches on a click, and guards both storage calls. Plan updated first: DESIGN.md, EXPERIENCE.md, epics.md (UX-DR2, the 1.7 note, Story 3.4) and two UX memlog entries. README says what theme.js does (AD-18).
- An AI slip while updating the tests: a helper script turned a regex word boundary into a control character and split two regexes over lines; the test run caught it, and a scan found no other control characters in the changed files.
- Full suite after both changes: 507 passed, 1 deselected.

## Spec Change Log

## Review Triage Log

Review pass 1 (2026-11-20). Three subagent reviewers on the diff since 86a8042 (spec left out): blind (B, 13 findings, floor 10), edge-case (E, 11) and verification-gap (V, 2 gaps + 1 other). 27 findings, grouped by root cause.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | V3, E1: before load-sample the listed Coin-flipper says "Not available offline" (its file is not written yet) | medium | True: coin-flipper files exist only after load-sample; tests used a folder that had them | patch: `synthetic.all_addresses()`; a Synthetic address with no snapshot is *not loaded*; tests on a fresh folder (both fail with the fix undone) |
| 2 | E5, B4: no 500 or 405 page; an unexpected error gives Werkzeug's bare page | medium | True: only 404 had a handler | patch: 405 → *Page not found*; 500 → "Something went wrong" in the frame; tests |
| 3 | E4, B3, V2: a database error reads as "not loaded, run load-sample", which can't help; the catches were untested | low | Partly: WAL readers are not blocked by load-sample, so only a corrupt file mid-run reaches it | patch: the StoreError catches deleted; such a page now gets #2's error page; test with a failing store |
| 4 | V1: `open_sources`' `list_files` wiring untested | low | True: dropping it failed no test | patch: test on the client `open_sources` returns (fails with the wiring undone) |
| 5 | V2: the Sample-file-being-written branch untested | low | True | patch: test with a cut-off JSON file |
| 6 | E2: two threads missing at once; the second sees the list already swapped and raises | low | True by reading `_refreshed` | patch: `_refresh` returns True whenever it can look again |
| 7 | E6: `Store()` mkdir OSError at start ends in a traceback | low | True (`instance` a file, read-only folder) | patch: OSError caught with StoreError |
| 8 | B10: message pages' tab title says "Verdict" | low | True; UX-DR8 page name first | patch: the notice heading leads the title; test |
| 9 | B9: wording scan skips `records.py` (the Verdict labels) | low | True | patch: `records.py` scanned |
| 10 | B8: "999 more coin-flippers, checked by address" gives no way to find one | low | True | patch: README says where the addresses are |
| 11 | B13: local-time `stored_at` test only checks the prefix; docstring has a stray `"."` | low | True | patch: exact local check; docstring fixed |
| 12 | E3: every miss lists the files and may rebuild the index | low | Rebuild only when the list changed; Synthetic addresses no longer reach the client (#1) | rejected |
| 13 | E7, B1: a live `run` creates `instance/live.db` in any folder | low | AD-6 puts live.db in `instance/`; the README runs from the repository; Story 2.1 needs it | rejected |
| 14 | B2: "client is None" acts as a second mode switch; Story 2.1's live client would show the Sample list | low | Latent: no live client exists until 2.1 | rejected; carried to issues.md for Story 2.1 |
| 15 | B5: no stacking, so 320 px / 200% zoom scrolls sideways | low | True, but UX-DR10 (which holds this rule) moved to Story 3.4 by Edvard's decision | rejected (intent) |
| 16 | B6: CI checks one Wallet, on Linux only; start-up loop doesn't fail early | low | AD-17 asks for one Sample Wallet's page; the other Verdicts are tested on 3 OS; a dead server fails at the next curl with its log | rejected |
| 17 | B7: live notice shows only `--offline`; no notice on the Lookup page in a live run | low | Edvard's approved wording and option A | rejected (intent) |
| 18 | B11: `positions()` parses a whole file to test membership; the OSError/ValueError branch is dead | false | The branch catches the exception (without it the page errors); one small file per check | rejected |
| 19 | E8: sprint-status 1-7 still `in-progress` | false | Set to `review` at the end of the workflow | rejected |
| 20 | E9, E10, E11: no architecture-test additions; `check` returns a tuple, `sample_list`/`resolved_bets_word` names, labels in services | low | The existing import rules already cover the new modules; names noted below | rejected (fix is a spec edit) |
| 21 | B12: spec untracked, no AI log yet; decision only in the UX memlog | false | Committed at session end; epics.md has no memlog, its note cites Edvard | rejected |
| 22 | B13: `serve` never closes the store | low | The process ends when `app.run` returns | rejected |

After the patches: 506 passed, 1 deselected.

## Verification

**Commands:**
- `uv run pytest` -- expected: all pass
- `uv run liquidoracle load-sample` then `uv run liquidoracle run --offline` -- expected: the pages render; the sharp trader shows *Skilled (high confidence)*
