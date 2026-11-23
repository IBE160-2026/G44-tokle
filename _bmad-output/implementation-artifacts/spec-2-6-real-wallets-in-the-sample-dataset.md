---
title: 'Story 2.6: Real Wallets in the Sample Dataset'
type: 'feature'
created: '2026-11-23'
status: 'in-review'
baseline_commit: '03c83f765f4cc677a64f4cafda8c0074d50d5f08'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Offline Mode has only Synthetic Wallets. The 10 real Sample Wallets sit in a raw capture zip outside the repo (positions lists and activity rows, 23 Oct 2026), with no Gamma records, and no script turns them into Sample Dataset files.

**Approach:** One command, `liquidoracle build-sample`, checks the zip against its SHA-256, runs the app's own window (`positions_near`) on each picked Wallet over the whole capture, and writes only the rows that window read to `sample_data/real/` with the one serializer. Offline Mode lists them under *Real Wallets*; their Verdicts, uncoupled shares and times are recorded in a note.

## Boundaries & Constraints

**Always:** The window comes from `positions_near` itself, never a copy of its rules. Where the capture stopped is stored in each file, so `OfflineClient` answers past it as a cut-short read and the normal "not fully read" rule applies. After writing, the build reads each file back through `OfflineClient` and refuses to finish unless the window is identical to the one built from the whole capture. Same inputs give identical bytes. The committed Sample Dataset stays under 50 MB (decision 6). Read-only toward Polymarket. Results recorded whatever they are; nothing tuned (NFR-13).

**Decisions (Edvard, 2026-11-23, all AI recommendations):** (1) The capture zip holds no Gamma records: they are fetched once with the app's own client (read-only) and frozen next to the zip as `sample-additions-2026-11-23.json` with its own `.sha256`; the build checks both files, and the epics AC changes to say so (plan first). (2) 0xd218e4's CLOSED list stopped at its oldest 60,000 rows: its newest CLOSED pages are fetched once into the same additions file, so it gets a normal Verdict page; that this Wallet's data comes from two dates (23 Oct and 23 Nov 2026) is written down. (3) Spec kept whole (~1,900 tokens). (4) Subagents for review only. Later the same day, after the first build: (5) the zip's pick file is the pre-swap version, so the 10 come from `spike/FINDINGS.md` as a constant, checked against the zip; (6) the size limit is raised from 25 MB to 50 MB (the needed rows come to about 35 MB).

**Never:** Editing `sample_data/` by hand. Price windows (Epic 6) or before/after windows (Story 4.6). The spares. Committing the zip or raw Gamma. Changing any Position rule, the Skill Test, or the live lookup.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Build | zip + SHA match | 10 files in `sample_data/real/` + `dataset.json` (Cut-off Date 2025-07-01, both SHA-256s) | N/A |
| Wrong zip | SHA mismatch or missing `.sha256` | nothing written | exit 2, says which file |
| Rerun | same inputs | byte-identical output | N/A |
| Capped activity | 0x63d43b, 0xd218e4 (and 0x729806's before part) | Positions past the capture's stop "not fully read" | N/A |
| Replay differs | written file gives another window | nothing kept | exit 2, names the Wallet |
| Offline lookup | `run --offline`, sockets blocked | *Real Wallets* group, 10 shortened addresses, each opens a Verdict page | N/A |

</frozen-after-approval>

## Code Map

- `records.py` `SampleWallet` -- add `activity_from: int | None`, `activity_until: int | None` (None = no limit). Capture semantics: rows before `activity_from` may be missing; rows from second `activity_until` on may be missing.
- `data/sample_json.py` -- write/read both keys (strict); regenerate `sample_data/synthetic/*.json` with `make-synthetic` (2 null keys each).
- `data/offline.py` -- `activity_rows`: `start < activity_from` → `Read((), False)`; rows up to `activity_until`; complete only if `end < activity_until` and not over `row_cap`. `SAMPLE_DIRS` + `sample_data/real`; `NOT_WALLET_FILES` + `dataset.json`.
- `data/polymarket.py` -- `PolymarketClient.raw_markets(ids)` returning Gamma's raw dicts; `markets()` built on it (still the one network client, AD-2).
- `data/real_sample.py` (new) -- zip reading + SHA check, additions file (raw Gamma kept to `tests/fixtures/cut_from_capture.py`'s `GAMMA_KEYS`, tag labels, event ids), a recording client around `OfflineClient`, the trim, the replay check, the negRisk outcome check, `dataset.json`. Reuse `window.positions_near`, `sample_json.write_wallet(compact=True)`.
- `__main__.py` -- `build-sample ZIP [--fetch]`: `--fetch` adds missing Gamma records and 0xd218e4's newest CLOSED pages to the additions file through `PolymarketClient`; without it, no network.
- `services/lookup.py` `sample_list`, `web/templates/samples.html` -- *Real Wallets* group first (mockup `ux-designs/.../mockups/lookup.html:224`), monospace short addresses.
- `tests/test_offline.py` (25 MB test exists), `tests/test_lookup.py`, `tests/test_web.py`, `tests/test_cli.py` -- counts 1,005 → 1,015.
- Pick: `spike/raw/sample/picked.json` key `sample`; estimates in `spike/FINDINGS.md:111-124`.

## Tasks & Acceptance

**Execution:**
- [x] `epics.md` 2.6, spine AD-14, `deferred-work.md` (capped capture, negRisk items resolved), `.memlog.md` -- plan first.
- [x] `records.py`, `sample_json.py`, `offline.py`, synthetic files -- capture bounds.
- [x] `polymarket.py`, `real_sample.py`, `__main__.py` -- fetch once, build, commit `sample_data/real/`.
- [x] `lookup.py`, `samples.html`, `app.css` -- Real Wallets group.
- [x] `docs/real-wallets.md` (new) -- per Wallet: pick estimate, Verdict, tested / left out (not fully read), uncoupled share, Verdict time from stored data; one live lookup with fetch time; negRisk check result. README: raw capture not in repo, set built by `build-sample`.
- [x] tests -- SHA refusal; byte-identical rerun on a small made-up zip; OfflineClient bounds; every committed real Wallet loads with sockets blocked and gets its Verdict under 10 s (NFR-10); Real Wallets group in the page; architecture rules pass.

**Acceptance Criteria:**
- Given `uv run pytest`, then all pass with sockets blocked.
- Given `uv run liquidoracle load-sample` then `run --offline`, then 1,015 Wallets load and all 10 real Wallets open a Verdict page.

## Implementation Notes

- Written by the main session (subagents for review only, Edvard's call). 859 tests pass (809 before), 2 online tests deselected. `load-sample`: 1,015 Wallets in 20 s.
- **One-off fetch** (`build-sample --fetch`, 23 Nov 2026): Gamma records of 35,869 Markets and 0xd218e4's newest CLOSED pages, read-only through `PolymarketClient` at 5 requests a second, about 8 minutes in all; stored in `../G44-tokle-data/sample-additions-2026-11-23.json` (26 MB) with its `.sha256`. It also holds 29 records of the spare 0x8861f0 from the first run (harmless; never written to `sample_data/`).
- **Found by real data, fixed:** (1) the first fetch stopped on an open Gamma Market without `outcomePrices` (0xd218e4's UFC title Market); the Story 2.1 parser refused the whole answer, so a live lookup touching such a Market failed as an outage. Now an open Market without prices is read unpriced; a closed one is still refused (`8c8b3ea`, two tests). Finding the record took about 800 extra read-only Gamma requests (a scratch script). (2) The zip's `sample/picked.json` predates the 23 Oct swap, so the first build wrote the spare 0x8861f0 and left out 0x091596; caught in the build's output; the 10 now come from `spike/FINDINGS.md` (decision 5). (3) `OfflineClient.markets` looked each Market up in the first file holding it, so real Wallets sharing Markets re-read 10 MB files thousands of times (one Wallet 68 s with all files, 0.4 s alone); found by the new Verdict-page test; it now reads each file once per call (`19fb770`, regression test fails on the old code).
- **Results** (`docs/real-wallets.md`): 0xcf0d7f *Likely skilled* (p 0.048), as estimated; 0x736483 *No evidence* (estimate *Likely skilled*; 700 Slivers, 527 sold); 0xd218e4, 0x63d43b and 0x729806 *Not enough data*, every Position not fully read (capture capped before the window's trades); the others as estimated. Uncoupled shares 0-16.4%, all under 20%. negRisk: 7,376 Markets, all Yes/No. NFR-10 from stored data: slowest 0.46 s (0x94884d). Live with the fetch: 0xd3a6e5 21.7 s, 0x63d43b 298 s (also capped live: *Not enough data*).
- 0x091596's Real PnL here is -49,571.22, 17 cents from Story 2.4's fixture value: logged in `deferred-work.md` for Story 2.7.
- **Deviations:** the Real Wallets group lists all 10 short addresses (the mockup shows 4 and "and 6 more"), so each can be clicked. `_cap_prefix` repeats the window's resolved-Market order to choose which OPEN rows to keep; it is only a trim, and the replay check refuses any file whose window differs. `Lookup`'s client is now typed `OfflineClient` (it always was one) so it can list the real Wallets.
- AI slips: `git add -A _bmad-output` picked up Edvard's two untracked `validation-report.html` files in the plan commit; amended before any push. Three test assertions were first written so they could not fail (`or True`, `or len(...)`, a no-op line), fixed before the first run.

## Spec Change Log

## Review Triage Log

Pass 1 (2026-11-23). Three reviewers: blind hunter (BH), edge-case hunter (EC), verification gap (VG). The diff left out the 10 data files (35 MB) and this spec (edge-case hunter only). 42 findings: 18 fix groups patched, 1 deferred, the rest rejected. No loopback.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| EC1 | After a pull, coin-flipper files from before the format change break the Lookup page | medium | Confirmed: `sample_list` called `real_addresses`, which built the full index, and `read_ids` refuses a file without the two new keys, so `/` gave 500 and hid the "run load-sample" box | patch (group with EC2, EC3): `real_addresses` reads file names only, re-listing files; test with an old coin-flipper file (fails on the old code) |
| EC2 | The first Lookup page in Offline Mode parses every Sample file | low | Confirmed, same call | patch (EC1 group) |
| EC3 | Real files written while the app runs never show | low | Confirmed: the index was built once | patch (EC1 group): names re-listed each time |
| BH1 | A build failing on Wallet k leaves `sample_data/real/` half written, despite the docstring | medium | Confirmed: files were written one by one, the failing one unlinked, `dataset.json` not rewritten | patch (group with EC4, EC5): write and replay in a git-ignored staging folder, swap in only when all pass; test breaks the second Wallet (fails on the old code) |
| EC4 | Same as BH1 | medium | Same | patch (BH1 group) |
| EC5 | A replay mismatch deletes the committed file | medium | Same root | patch (BH1 group) |
| BH2 | `--fetch` adds to an existing additions file without checking its SHA-256, then signs it again | medium | Confirmed in `fetch_additions` | patch (group with EC10): `checked()` first; test (fails on the old code) |
| EC10 | Same as BH2 | medium | Same | patch (BH2 group) |
| BH3 | PRD FR-12's stated limitation names two Wallets and one direction; three Wallets show *Not enough data* | low | Confirmed: PRD and epics 2.6 text; `docs/real-wallets.md` already explained it | patch: PRD FR-12 and epics 2.6 AC lines, memlog entry; Edvard was told before the build |
| BH5 | README says "the two largest Wallets"; the note names three | low | Confirmed | patch: README names all three and what the examiner will see |
| BH4 | The capture is built around 1 July 2025, while the lookup window is October 2026; Story 4.6 may meet the same gap | maybe-false | Would be medium for 4.6's before window and the Hold-up Test; settled by running 4.6's before window on the capture | defer |
| BH6 | Test name still says 25 MB | low | Confirmed | patch (with VG-o1): renamed |
| VG-o1 | Same as BH6 | low | Same | patch (BH6 group) |
| BH7 | Memlog says "about 32 MB untrimmed" and later "35 MB trimmed" | low | True: 32 MB was a pre-build estimate | patch: memlog correction entry (append-only) |
| BH8a | `Lookup` takes the concrete `OfflineClient` | false | Services may import data (AD-1 rules pass); `Lookup` was always given an `OfflineClient` and its docstring says so; no caller diverges | reject |
| BH8b | Import order and a stray blank line in `lookup.py` | low | Confirmed | patch: direct correction |
| BH9 | `with_closed` is dead and `_FetchingClient` keeps two views of the capture | low | Confirmed: every call passed True | patch: flag removed, one `_capture()` view |
| BH10 | Dates hard-coded; a later `--fetch` would keep the first `fetched_on` | low | The capture date is now one constant; the additions file is frozen and checked, and a later fetch is not planned | patch (constant only); rest rejected |
| EC11 | Same as BH10's second half | low | Same | reject |
| BH11 | Real Wallets links are short addresses only, hard for screen readers | low | The presentation is DESIGN.md's (shortened addresses in monospace, UX-DR17); Story 3.5 runs the accessibility check | reject (noted for Story 3.5) |
| BH12 | `real_addresses` matches the folder name only, skips in-memory Wallets, order unclear | low | Only `sample_data/real` is in `SAMPLE_DIRS`; in-memory clients are build-only; the name order is the address order, which the test checks; the parent check now also needs `sample_data` | patch (parent check, in EC1 group); rest rejected |
| BH13a | No test of the `--fetch` CLI path | low | The fetch itself is tested through `fetch_additions` with a fake client; the flag's no-network side is now tested (VG2) | reject |
| BH13b | No test of the cut OPEN list refusal | low | Pre-verified by VG4 | patch (group with VG4): test |
| BH13c | No test of an empty or malformed `.sha256` | low | Confirmed | patch: test |
| BH13d | No test that `markets()` prefers cached Markets | false | `test_shared_markets_do_not_make_the_client_reread_files` checks exactly that | reject |
| BH13e | No test of a build failing partway | medium | BH1 | patch (BH1 group) |
| BH14 | `build_sample` misses `BadZipFile` and `NotAvailableOffline` | low | Confirmed: traceback instead of the plain line | patch (group with EC6): catches `LookupError` and `BadZipFile`; test with a broken zip |
| EC6 | Same, plus `NoPolymarketHistory` and `TypeError` | low | `NoPolymarketHistory` is a `LookupError`; `TypeError` needs a hand-made zip | patch (BH14 group) |
| BH14b | Ctrl+C during `--fetch` loses the current Wallet's Gamma records | low | True; the next run fetches only what is missing | reject |
| BH15 | No AI log; sprint status still in-progress | false | Both come at the end of the session (step 5) | reject |
| BH16 | The 17-cent gap on 0x091596 is deferred without checking the obvious cause | low | Checked: Polymarket changed 5 of its Markets' fee rates between 20 and 23 November, so the strict fee check passes a different set | patch: cause written into `deferred-work.md` for Story 2.7 |
| BH17 | `sample_json.py` docstring line too long | low | Confirmed | patch: rewrapped |
| VG1 | The 10 Verdicts recorded in the note are pinned by no test | medium | Pre-verified gap | patch: golden test (Verdict, tested, Real PnL in dollars) per Wallet |
| VG2 | The `--fetch` wiring and a successful CLI build are untested | medium | Pre-verified gap | patch: CLI builds from a zip with sockets blocked; the CLI now passes `pick=PICK` explicitly |
| VG3 | The `+1` on `activity_from` is not pinned | medium | Pre-verified gap | patch: `read_capture` test on capped reads |
| VG4 | The cut OPEN list refusal has no test | low | Pre-verified gap; filed as defer | patch (BH13b group): one short test |
| VG-o2 | An open Market with no `outcomePrices` key at all is read unpriced | false | It is meant to be: patched to "explicit null only", the real build then refused the very Market that started this (Gamma leaves the key out; 1 of 5,330 open Markets in the fetch, none null). The first probe used `.get()`, which hides the difference. Reverted; docstring and tests now name the left-out key | reject (a test pins both shapes) |
| EC13 | Same as VG-o2 | false | Same | reject |
| EC7 | A picked Wallet with an empty window crashes the replay | low | Not reachable with the 10 picked Wallets; now a plain `BuildError` through the replay guard | patch (in BH1 group's `_written`) |
| EC8 | A capped OPEN list with 60,000 CLOSED rows would read as whole | low | Not in the frozen capture (0xd218e4's OPEN list has 8,163 rows); the fix adds a guard | reject |
| EC9 | A refetched CLOSED list with uncapped activity would read as fully read | low | Not in the frozen capture: 0xd218e4's activity is capped, so its new Positions are not fully read | reject |
| EC12 | A Market Gamma omits once is stored as missing for ever | low | The frozen additions file has no missing Markets | reject |

After the patches: 878 tests pass (859 before review), 2 online tests deselected. The new tests for EC1, BH1 and BH2 were run against the old code and fail there. The real build run after the patches caught one wrong review fix (VG-o2), and also showed the staging fix working: the failed build left `sample_data/real/` untouched and no staging folder behind.

## Design Notes

**Trim (AD-14: by script, never by hand).** A file keeps: every CLOSED row the walk read; OPEN rows of Markets at or before the window's first left-out Market in the cap order (older OPEN rows cannot change `_cap`); Markets of kept rows; activity rows the window keeps, plus the read's last row when it was cut short, with `activity_until` set to that row's second (so `read_until` replays exactly). Without the trim the set would be well over the limit (about 36,000 Markets, mostly the two largest Wallets' OPEN lists); with it, 35.6 MB, nearly all activity rows the windows need (decision 6). The replay check proves each trim.

## Verification

**Commands:**
- `uv run liquidoracle build-sample ../G44-tokle-data/sample-capture-cutoff-2025-07-01.zip` twice -- expected: `git status` shows no change after the second run.
- `uv run pytest` -- expected: all pass (809 before, 859 after).

**Manual checks:**
- `run --offline`: open each real Wallet; `run` live: look up 0xd3a6e5 and time the fetch.
