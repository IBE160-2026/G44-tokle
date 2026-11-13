---
title: 'Story 1.3: Synthetic Wallets with known answers'
type: 'feature'
created: '2026-11-13'
status: 'in-progress'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '8e55120f1d4ca2d79babeb449ee56c3b96ac19e9'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Skill Test (Story 1.4) must be checked against answers fixed before it exists. No made-up Wallets, no Sample Dataset file format and no `make-synthetic` command exist yet.

**Approach:** Add one serializer for Sample Dataset files (AD-14) and a generator, `data/synthetic.py`, that writes the stage 1 Synthetic Wallets of FR-13 as fills first, then derives each Wallet's Markets, positions lists and price paths from them. Commit the small Wallets plus a hand-written `expected.json` with each type's intended bets and FR-13 answer. The 1,000 coin-flippers go to `instance/` only.

## Boundaries & Constraints

**Always:**
- Types and counts: hand-check 10 at 0.50, all won; favourite buyer 100 at 0.90, exactly 90 won; sharp trader 100 at 0.50, exactly 70 won; thin wallet 29 resolved; stop-loss trader 100 at 0.50, no edge; coin-flippers 1,000 × 100, price uniform in whole cents 0.10–0.90, won when a draw < price.
- 100 shares per bet, fees off, every bet in its own two-outcome Market, resolved, all times before the default Cut-off Date (2025-07-01).
- A fixed generator constant, never the `SEED` setting; never `random`, numpy's global state or `hash()`.
- Output is byte-identical on every run, OS and Python version: sorted keys, LF line endings, written as bytes.
- `expected.json` is written by hand, never by the generator.
- Every test names its FR or AD.

**Never:**
- No Skill Test, Verdict, store, `OfflineClient` or `load-sample` code (Stories 1.4, 1.6).
- No stage 2/3 types, anchor Markets or Copy Test price windows.
- No coin-flipper file in the repository. No `git add .`, no merge, no `gh`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Hand-check via builder | its file | 10 tested, all o = 1, p = 0.50, Real PnL $500.00 | N/A |
| Sharp trader | its file | 100 tested, 70 won, Real PnL $2,000.00 | N/A |
| Favourite buyer | its file | 100 tested at 0.90, 90 won, Real PnL $0.00 | N/A |
| Thin wallet | its file | 29 tested | N/A |
| Stop-loss trader | its file | 33 tested, all won; 67 "sold before resolution" at 0.25, each Exit PnL −$25.00 (17 of them in Markets their side won) | N/A |
| Coin-flipper | any one | 100 tested, prices in whole cents within [0.10, 0.90]; total wins over 100 Wallets within 4 SD of Σp | N/A |
| Run twice | `make-synthetic` | identical bytes; committed files equal fresh output | N/A |
| Round trip | load(dump(w)) | equals w | N/A |

**Decisions (Edvard, 2026-11-13):**
- Stop-loss trader: fair price path with a stop at 0.25 (AI's option A). Of 100 bets at 0.50, 67 fall to 0.25 and are sold there, 17 of them in Markets their side later won; 33 are held and all win. Total −$25, about zero, but the held bets alone read *Skilled (high confidence)*: the FR-11 limit. Rejected: selling only the losers at 0.30 (the trader would "know" them).
- Generator randomness: uniform draws from sha256 of (constant, Wallet, bet, purpose), standard library only (AI's option A), because the spine puts the generator in `data/`, whose import rule bans numpy. Files never change with a numpy upgrade. AD-15 gets a note. Rejected: allowing numpy in `data`.
- Subagents for the review only, as in Stories 1.1 and 1.2.

</frozen-after-approval>

## Code Map

- `src/liquidoracle/records.py` -- add `ListedPosition` (condition_id, token_id, status CLOSED/OPEN, shares_bought, first_entry_at) and `SampleWallet` (address, name, activity, positions, markets, prices). Stdlib only.
- `src/liquidoracle/core/positions.py` -- `build_positions(fills, markets)`; reuse, do not change.
- `src/liquidoracle/__main__.py` -- `make-synthetic` stub prints "not built yet"; replace it.
- `tests/test_architecture.py` -- `data` may import records, settings, requests, anthropic; every test must name an FR/AD.
- `.gitignore` -- `instance/` already ignored. No `.gitattributes`; local `core.autocrlf=true` would turn committed LF JSON into CRLF.

## Tasks & Acceptance

**Execution:**
- [ ] plan first -- epics Story 1.3 gets the stop-loss counts; spine AD-15 note on the sha256 draws and AD-14 names the serializer module; memlog entries -- CLAUDE.md: plan before code.
- [ ] `src/liquidoracle/records.py` -- the two types -- AD-10, AD-14.
- [ ] `src/liquidoracle/data/sample_json.py` -- `dumps(wallet, compact)` / `loads(text)`, the one serializer -- AD-14.
- [ ] `src/liquidoracle/data/synthetic.py` -- one function per type, `small_wallets()`, `coin_flipper(i)`, `write_all(sample_dir, instance_dir)` -- FR-13, AD-14, AD-15.
- [ ] `src/liquidoracle/__main__.py` -- `make-synthetic` writes `sample_data/synthetic/*.json` and `instance/synthetic/coin-flippers/` -- FR-13.
- [ ] `sample_data/synthetic/expected.json` -- by hand: counts, Real PnL, FR-13 Verdict and p range per type; coin-flipper limits 7% / 2% -- FR-5, FR-6, FR-11, FR-13.
- [ ] `.gitattributes` -- `sample_data/**/*.json` as LF -- FR-13.
- [ ] `tests/test_synthetic.py` -- the matrix, plus own-Market check and no-coin-flipper-in-repo check -- FR-13, AD-14, AD-15.

**Acceptance Criteria:**
- Given `uv run liquidoracle make-synthetic`, then the five small files and `expected.json` sit in `sample_data/synthetic/`, the 1,000 coin-flippers in `instance/`, and `git status` shows no coin-flipper.
- Given `uv run pytest`, then all tests pass with sockets blocked.

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Design Notes

- Positions lists derived from fills: held winners and sold bets are CLOSED; held losers are OPEN (Polymarket's unredeemed losers), so both lists are exercised (FR-3).
- Price paths only where needed (stop-loss): buy price, the sell point, then the outcome at resolution.
- AI choices: 100 shares per bet (clean hand values); thin wallet 20 of 29 won, so a good-looking record still gets *Not enough data*; addresses `0x` + sha256 of the name.

## Verification

**Commands:**
- `uv run liquidoracle make-synthetic` then `git status` -- expected: no change to committed files
- `uv run pytest` -- expected: all pass
