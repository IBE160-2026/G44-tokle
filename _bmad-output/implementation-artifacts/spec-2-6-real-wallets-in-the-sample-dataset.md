---
title: 'Story 2.6: Real Wallets in the Sample Dataset'
type: 'feature'
created: '2026-11-23'
status: 'in-progress'
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

**Always:** The window comes from `positions_near` itself, never a copy of its rules. Where the capture stopped is stored in each file, so `OfflineClient` answers past it as a cut-short read and the normal "not fully read" rule applies. After writing, the build reads each file back through `OfflineClient` and refuses to finish unless the window is identical to the one built from the whole capture. Same inputs give identical bytes. The committed Sample Dataset stays under 25 MB. Read-only toward Polymarket. Results recorded whatever they are; nothing tuned (NFR-13).

**Decisions (Edvard, 2026-11-23, all AI recommendations):** (1) The capture zip holds no Gamma records: they are fetched once with the app's own client (read-only) and frozen next to the zip as `sample-additions-2026-11-23.json` with its own `.sha256`; the build checks both files, and the epics AC changes to say so (plan first). (2) 0xd218e4's CLOSED list stopped at its oldest 60,000 rows: its newest CLOSED pages are fetched once into the same additions file, so it gets a normal Verdict page; that this Wallet's data comes from two dates (23 Oct and 23 Nov 2026) is written down. (3) Spec kept whole (~1,900 tokens). (4) Subagents for review only.

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
- [ ] `epics.md` 2.6, spine AD-14, `deferred-work.md` (capped capture, negRisk items resolved), `.memlog.md` -- plan first.
- [ ] `records.py`, `sample_json.py`, `offline.py`, synthetic files -- capture bounds.
- [ ] `polymarket.py`, `real_sample.py`, `__main__.py` -- fetch once, build, commit `sample_data/real/`.
- [ ] `lookup.py`, `samples.html`, `app.css` -- Real Wallets group.
- [ ] `docs/real-wallets.md` (new) -- per Wallet: pick estimate, Verdict, tested / left out (not fully read), uncoupled share, Verdict time from stored data; one live lookup with fetch time; negRisk check result. README: raw capture not in repo, set built by `build-sample`.
- [ ] tests -- SHA refusal; byte-identical rerun on a small made-up zip; OfflineClient bounds; every committed real Wallet loads with sockets blocked and gets its Verdict under 10 s (NFR-10); Real Wallets group in the page; architecture rules pass.

**Acceptance Criteria:**
- Given `uv run pytest`, then all pass with sockets blocked.
- Given `uv run liquidoracle load-sample` then `run --offline`, then 1,015 Wallets load and all 10 real Wallets open a Verdict page.

## Design Notes

**Trim (AD-14: by script, never by hand).** A file keeps: every CLOSED row the walk read; OPEN rows of Markets at or before the window's first left-out Market in the cap order (older OPEN rows cannot change `_cap`); Markets of kept rows; activity rows the window keeps, plus the whole read when it was cut short (so `read_until` replays exactly). Without the trim the set is about 32 MB (39,000 Markets, mostly the two largest Wallets' OPEN lists). The replay check proves each trim.

## Verification

**Commands:**
- `uv run liquidoracle build-sample ../G44-tokle-data/sample-capture-cutoff-2025-07-01.zip` twice -- expected: `git status` shows no change after the second run.
- `uv run pytest` -- expected: all pass (809 before).

**Manual checks:**
- `run --offline`: open each real Wallet; `run` live: look up 0xd3a6e5 and time the fetch.
