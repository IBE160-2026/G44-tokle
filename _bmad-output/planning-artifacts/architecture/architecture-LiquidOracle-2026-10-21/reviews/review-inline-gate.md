# Reviewer gate, first pass (2026-10-21)

Run inline by the authoring session, not by independent subagents, so it is a self-check. An independent review can still be run on request.

## Lint

`lint_spine.py`: 0 findings, before and after the fixes below.

## Reconcile against the inputs

| Input | Finding | Action |
| --- | --- | --- |
| PRD s8 Wording | The banned-word list had no single home; the FR-24 check and the templates could each keep their own. | Fixed: convention row "Banned words". |
| PRD FR-7 | AD-15 did not say who picks the Seed, so lookup and Scan could choose differently. | Fixed: a `SEED` setting with one fixed default `[ASSUMPTION]`. Raised with Edvard. |
| PRD Glossary, Cut-off Date | The after part is "opened on or after" the date, but no source was named for the opening time; the v2 `first_entry_at` was 0 on some rows (probe 3). | Fixed: AD-10 row "First entry time: activity rows". |
| UX EXPERIENCE.md | The partial-coverage display (AD-9) and the "Keyword rules" tag (AD-13) are not in the UX docs yet. | Plan change: EXPERIENCE.md through its memlog. |
| PRD s9 Q6 | The default Cut-off Date is still open (owner Edvard). | Not an architecture call; it stays in the PRD. |

## Adversarial pairs (two units that obey every AD and still clash)

| Pair | Hole | Fix |
| --- | --- | --- |
| Scan vs Hold-up Test | Each could build its own Position list and apply the exclusions differently. | AD-11: `core/positions` is the only builder; everyone calls it. |
| Before part vs after part | "Latest 2,000" and "first 2,000" had no ordering key, so one builder could use the API's `last_event_at`. | AD-8: order by Market resolution time (before) and first entry time (after). |
| Lookup vs Scan | Different Seeds give different p-values for the same Wallet. | AD-15: one `SEED` setting. |

## Checked, no change needed

- Every structural dimension is decided or deferred, including the operational one (local only, one user, CI, secrets in `.env`).
- Named technology was checked on PyPI, GitHub or the vendor docs on 2026-10-21; versions are in the memlog.
- Mermaid: one edge label with a URL is now quoted.

## For Edvard

1. Python >= 3.12, not >= 3.11 (numpy 2.5.4 needs 3.12).
2. AD-12: a fee outside the 0.03–0.07 band leaves its Position out (the AI's reading of "flag it, don't store it as real").
3. AD-15: one fixed default Seed.
