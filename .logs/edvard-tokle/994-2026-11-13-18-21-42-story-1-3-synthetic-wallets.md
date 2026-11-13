# Story 1.3: synthetic wallets

## 2026-11-13 kl. 18:21 — Edvard Tokle

### Oppgave
Edvard asked the AI to read the handoff, pull `main` and check whether Story 1.2 was really merged (if not, say so first). If it was, mark 1.2 done and build Story 1.3 (made-up Wallets with known answers) only, on its own branch, which he merges himself. Show him the log text before committing it, update the handoff at the end, and tell him how to run the tests himself.

### Plan
- PR #17 (Story 1.2) was merged; branch `story-1-3-synthetic-wallets` from `main` at 1807905, first commit sets 1.2 `done`. Spec: [spec-1-3-synthetic-wallets-with-known-answers.md](../../_bmad-output/implementation-artifacts/spec-1-3-synthetic-wallets-with-known-answers.md).
- Planning found one gap and one contradiction in the plan, which Edvard decided (stop-loss counts; sha256 draws instead of numpy). Plan changed first (PRD FR-13, spine AD-14/AD-15, epics, both memlogs), then the spec.
- As in Stories 1.1 and 1.2, the AI wrote the code itself and used three reviewer subagents for the review only (Edvard's choice).
- Noticed on `main`: the teacher's PRD feedback and a `technology.md` that describes another project (both 12 Nov, not touched).

### Resultat
- **Plan change (449a6cd):** stop-loss trader with a fair price and a stop at 25¢: 67 sold (17 in Markets their side later won), 33 held and all won, total −$25 (Edvard chose the AI's option A over "sell only the losers"). Generator draws come from sha256, standard library only, because `data/` may not import numpy (Edvard chose A over allowing numpy).
- **Built:** `ListedPosition` and `SampleWallet` in `records.py`; the one serializer `data/sample_json.py` (da430d0); hand-written `sample_data/synthetic/expected.json` (8cb019a); `data/synthetic.py` and `uv run liquidoracle make-synthetic` (07b25a0): five committed Wallets (about 400 KB) and 1,000 coin-flippers in `instance/` (about 87 MB, git-ignored). `.gitattributes` keeps the Wallet files at LF.
- **Tests:** 52 new, 174 passed and 1 deselected in total; the slow coin-flipper checks also pass at `--repetitions 1000`. 8 bugs planted by the AI each failed a test.
- **Review (4eb9ea6, 347a256):** 28 findings: 16 fixed, 12 rejected with reasons, none deferred. Bugs in the AI's code: the file reader converted wrong types silently and crashed on `Infinity`; no test noticed non-uniform coin-flipper prices; the `SEED` ban test missed one import form; the README still said "not built"; the AI had written invented times in `sprint-status.yaml`.
- **Commits:** 8e55120, 449a6cd, 8266aa6, da430d0, 8cb019a, 07b25a0, 4eb9ea6, 347a256, 5a97eb7. `sprint-status.yaml`: 1-2 `done`, 1-3 `review`. AI log draft: `docs/ai-logs/2026-11-13-story-1-3.md`.

### Åpne punkter
- Story 1.4: the Skill Test must meet `sample_data/synthetic/expected.json`, including the stop-loss trader reading *Skilled (high confidence)* (the FR-11 limit, on purpose).
- Story 1.6: `load-sample` regenerates the coin-flippers with `synthetic.write_coin_flippers`.
- The teacher's PRD feedback (`tilbakemelding-prd.md`, 12 Nov) is not handled: stage 2 minimum version, the FR-24 word list, FR-19 error handling, tidying §9.
- Ask the teacher whether `technology.md` (added to `main` on 12 Nov, about another project) was meant for this repository.
