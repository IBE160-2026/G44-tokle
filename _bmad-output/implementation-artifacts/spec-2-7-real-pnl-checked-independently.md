---
title: 'Story 2.7: Real PnL checked independently'
type: 'feature'
created: '2026-11-23'
status: 'done'
baseline_commit: 'e85f0838b3e6c94a976172ecea51acabaa56c03a'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The app's Real PnL on real Wallets has only ever been checked against itself, so a maths mistake in `core` could pass its own tests (FR-4 check, Story 2.7).

**Approach:** Compare the app's Real PnL for three committed real Sample Wallets, to the cent, with reference values made without the app's code: 0x29306d from a fresh AI helper's calculation (already committed, e85f083), and 0x0f4b0a and 0x091596 from one separate script that a second fresh helper writes from `prd.md` and the two Wallet files alone. Decided by Edvard 2026-11-23: helpers instead of his own spreadsheet; the same rule later for the Copy Test (FR-18a).

## Boundaries & Constraints

**Always:** The script helper sees only `prd.md`, the two Wallet files and a field note that says only what each field is: no rules, no hints from how the app does it, no app numbers; the PRD carries the rules (Edvard, at approval). Every `.py` in `tests/reference/` imports only the standard library, never `liquidoracle`; a rule test enforces it. Each reference CSV is committed before the comparison test exists. The test file says where each number came from. If a value differs, the cause (app, script or helper) is found and logged in this spec and the AI log; a reference value is never edited to match without a written reason in the same commit.

**Never:** Show the helper the app's code, tests, results or the Epic text. Hand-edit a helper's CSV or script. Run the script inside the test suite with network access (it needs none).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Match | App Real PnL for a Wallet, reference TOTAL row | Equal after rounding both to the cent | N/A |
| Mismatch | Any cent difference | Test fails naming the Wallet, both values and the reference's source | Cause found and logged before any change |
| Script imports the app | A `liquidoracle` or third-party import in a reference `.py` | Rule test fails naming file and import | N/A |
| Stale CSV | Script output differs from the committed CSV | Re-run test fails | N/A |

</frozen-after-approval>

## Code Map

- `tests/reference/0x29306d-real-pnl.csv`, `-notes.md`, `-calc.py` -- helper 1's work (committed). TOTAL row: `condition_id == "TOTAL"`, total in `pnl_contribution` (295.06). App already gives 295.06297899… (checked 2026-11-23, 18 tested, 3 Slivers).
- `sample_data/real/0x0f4b0a6b7f82108924ac9c8320ed91028f504183.json` (274 Positions, 17 fee Markets, 67 negRisk) and `0x0915962b4c6bc4505e7434a0de815a596a6667c3.json` (66 Positions, 1 CONVERSION row whose `condition_id` is the event's `neg_risk_id`) -- the script's inputs. Both under 2,000 Positions, `activity_from/until` null.
- `src/liquidoracle/services/fetch.py` `fetch_wallet` + `stored_result` -- the app path to reuse in the test, exactly as `tests/test_real_sample.py:495` (NFR-10 test) does: `OfflineClient([file])`, `Store(tmp_path/...)`, `result.result.real_pnl` (float, exact sum).
- `tests/test_architecture.py` `imported_modules` -- reuse for the stdlib-only rule (`sys.stdlib_module_names`). `test_every_test_names_its_requirement`: every test docstring names FR-4 or similar.
- Do not change: `core/skilltest.py`, `core/positions` builder, the committed Sample Dataset.

## Tasks & Acceptance

**Execution:**
- [x] scratchpad `helper-2-7b/` -- copy `prd.md`, the two Wallet files and a format-facts note; spawn a fresh helper (Opus, extra-high effort) to write `real_pnl_reference.py` (stdlib only, `python -I real_pnl_reference.py <wallet.json>... <out_dir>`) plus one CSV per Wallet in helper 1's column layout and a `notes.md` of judgment calls; it lists every file it read -- independence (Story 2.7 AC 2).
- [x] `tests/reference/real_pnl_reference.py`, `0x0f4b0a-real-pnl.csv`, `0x091596-real-pnl.csv`, `script-notes.md` -- copy unchanged after checking the file list and that a re-run reproduces the CSVs; commit before the test -- AC order.
- [x] `tests/test_reference_pnl.py` -- (a) app Real PnL equals each reference to the cent, with a `SOURCES` table naming helper calculation vs script; (b) every `tests/reference/*.py` imports only the standard library, plus a planted-import case; (c) re-running the script into `tmp_path` reproduces the two committed CSVs byte for byte.
- [x] On any mismatch: find the cause, log it below, fix the side that is wrong (app fix gets its own test and commit).

**Acceptance Criteria:**
- Given the three committed references, when `uv run pytest` runs offline, then all three match the app to the cent and the suite stays green.
- Given 0x091596, when the script runs, then its Romania event is left out because of the CONVERSION and the $44.31 fee that fails the schedule check counts as 0 (Story 2.4, 2.3), or the difference is explained in the log.

## Implementation Notes

- Built directly in this session; subagents were used only for the two independent helpers (and later review), as in earlier stories.
- **No mismatch.** App vs reference: 0x29306d 295.06297899479273 vs helper 295.0629789947927066 (18 tested, 3 Slivers both); 0x0f4b0a -188.49 both (210/43, Own Fees 0.25, 7 fees failed); 0x091596 -49,571.22 both (14/24, Own Fees 1,087.34). AC 2 holds: the script left out the Romania event's 24 Markets (25 Positions) for the CONVERSION and counted the 44.3074 fee (3% Market, a Sliver) as 0.
- Commits: e85f083 helper 1 reference; 4810a37 helper 2 script, CSVs, `script-notes.md`, plus `fields.md` (the exact field note it was given, so a reader sees what it knew) and two `*-fee-check.csv` audit files the script writes itself. Test added after 4810a37.
- Deviation: the re-run test compares line by line, not byte for byte, because git's line-ending conversion changes the committed CSVs on checkout.
- Planted checks: halving Own Fees in `core/skilltest.py` failed both fee Wallets (-49,027.55 vs -49,571.22; -188.36 vs -188.49); editing the 0x29306d TOTAL to 295.07 failed the comparison and the re-run test. Both restored.
- The helpers' PRD copy also held the uncommitted FR-18a rewording (Copy Test, unrelated to Real PnL).
- PRD points the helpers flagged as unclear (both agreed with the app, so nothing failed): (1) FR-3 says "converted shares in that Market", but a CONVERSION row names the negative-risk event; helper 2 left out the whole event, the only reading that fits the data. (2) Own Fees on the buys of shares later sold count in full (Glossary literal; +636.90 on 0x091596 if only held shares were charged). (3) Every failed fee fits the fee formula at 1.67x to 7x the listed rate: consistent with Polymarket having changed rates (Story 2.6 note). (4) A Market not yet resolved is not one of FR-3's named reasons. (5) What the 1% source gap is measured against. (6) The fee check's tolerance is not defined.

## Spec Change Log

## Review Triage Log

Pass 1 (2026-11-23): blind hunter, edge-case hunter, verification-gap reviewer; 29 findings.

| # | Layer | Finding | Verdict | Evidence / route |
|---|-------|---------|---------|------------------|
| 1 | VG, ECH, BH | Re-run test skips the committed `*-fee-check.csv` files | medium | Confirmed: only `-real-pnl.csv` was read back. Patch: SCRIPTS lists each script's outputs; a planted edit in a fee-check row now fails. |
| 2 | VG, ECH, BH | Stdlib-only rule sees static imports only; `importlib`/`__import__` would pass | low | Real but no script does it. Patch (direct): re-run uses `python -I -S`, so site-packages (where the app is installed) is gone; new test shows `import liquidoracle` fails there. |
| 3 | BH | Equality test compares only the TOTAL; counts and Own Fees never compared with the app | medium | Patch: new test compares tested count, Sliver count and Own Fees to the cent (18/3/0, 210/43/0.25, 14/24/1,087.34 all match). |
| 4 | BH | epics.md FR-18a summary line still says "hand-calculated" | medium | Confirmed (line 55, missed by the 6.x rewording). Patch: reworded. |
| 5 | BH, VG | `script-notes.md` names the helper's scratch paths; repo re-run command not written anywhere | low | Patch: test docstring gives the repo command; helper's notes left as written. |
| 6 | BH | `fields.md` does not say who wrote it; CONVERSION line called interpretation | low | Authorship: patch in the test docstring (file kept exactly as given). The CONVERSION line states what the field holds, checked in the data (row value equals the event's `neg_risk_id`); it names no rule, so not a hint. |
| 7 | ECH | `store.close()` skipped if the app raises | low | Patch: try/finally. |
| 8 | BH | epic-2-context says "one of the three paid fees" | low | Patch: "at least one (0x0f4b0a and 0x091596 did)". |
| 9 | BH | Failed fees fit the fee formula at 1.67x-7x the listed rate: both app and reference drop real fees | medium | Pre-existing (Story 2.3 strict check against today's rate; rate change found in 2.6). Defer, raised with Edvard. |
| 10 | BH | Own Fees on buys of shares later sold count in full (J6, +636.90 on 0x091596) with no recorded decision | medium | Pre-existing; app and reference both follow the Glossary literally. Defer, raised with Edvard. |
| 11 | BH | FR-3 says "converted shares in that Market" though a CONVERSION names the event (J9) | low | Pre-existing wording; Edvard's 2.4 call (whole event) is in the epics. Defer, raised with Edvard. |
| 12 | BH | Helper's "market not resolved" / "market data missing" reasons are not FR-3 reasons | false | Reference script labels only; the app's window holds resolved Markets only, and neither label changes a total. |
| 13 | ECH, BH | Script crashes on 0/0 (shares_bought 0) or a token missing from token_ids | false | Not reachable in the committed files; a crash is a loud failure the re-run test would show. |
| 14 | ECH | Null `fee_exponent` assumed 1 | false | Exponent is 1.0 in every fee Market of both files. |
| 15 | ECH | Unknown activity types only printed | false | Files hold only TRADE, REDEEM, CONVERSION. |
| 16 | ECH | TRADE with null side silently dropped | false | No such row in the files. |
| 17 | ECH | Two Wallets with the same 8-character prefix overwrite each other | false | The three prefixes differ. |
| 18 | ECH | Double rounding (float repr then HALF_UP) near a half cent | false | App values sit far from a half-cent edge (…0630, …4879, …2170); a near-edge case would fail loudly, never pass wrongly by more than a cent. |
| 19 | ECH, BH | Spec said "byte for byte", test uses splitlines; pin `eol=lf` | false | Deviation already in Implementation Notes; `eol=lf` would break helper 1's CSV, whose script writes CRLF. |
| 20 | VG | Subprocess has network access | low | Rejected: neither script imports a network module; adding a network ban adds rules for an unseen case. |
| 21 | BH | Judgment-call numbering gaps in `script-notes.md` | low | Rejected: cosmetic, and the helper's own words are kept unedited. |
| 22 | BH | Spec untracked, no AI log | false | Both are committed at the end of the build (step 5 and the session log). |

## Verification

**Commands:**
- `uv run pytest tests/test_reference_pnl.py -v` -- expected: all pass, three Wallets compared.
- `uv run pytest` -- expected: whole suite green (894 passed: 878 + 16).
