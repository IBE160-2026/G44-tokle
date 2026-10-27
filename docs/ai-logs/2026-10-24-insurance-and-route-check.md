# AI session log, 2026-10-24: insurance pool and daily price-route check

- **Tool**: Claude Code (model Claude Opus 5.5) in the VS Code extension.
- **Student**: Edvard Tokle (G44).
- **What this covers**: two decisions taken during the epics step (Epic 6, the Copy Test) whose code merges before that step's log: a 50-Wallet insurance capture of price windows, and a daily check of Polymarket's old price-history route. The rest of the epics session is in its own log.
- **Result**: `spike/INSURANCE-RULE.md`, `spike/insurance_pick.py`, safer file writes in `spike/sample_pick.py` and `spike/sample_capture.py`, `.github/workflows/price-route-check.yml`; plan text in PRD FR-18 and spine AD-24 (with the epics branch); branch `route-check-insurance`.

## 1. The problem

The real-data Copy Test (SM-5) needs one-minute prices after each buy. Only the old price route has them for dates older than 7 days, and it has no announced end date; Data API v1 was retired with three days' notice. The Sample Dataset's 10 Wallets are captured, but a real Scan's Copy Pool (about 200 Wallets) is not.

## 2. What the AI proposed and what Edvard changed

| Topic | AI proposal | Edvard's decision |
|---|---|---|
| Watching the route | Check it weekly | **Changed: daily**. "v1 only gave 3 days notice", and it is one request |
| If the route dies | Report honestly that the real Copy Test could not run | **Not accepted yet**: he asked for the price of a smaller insurance capture first, "50 wallets instead of 200, all their after windows, picked by a rule we can write down now", then decided |
| Insurance cost | About 28,000 to 35,000 requests, about 2 hours with 3 workers at most 5 per second, 3 to 4 GB raw; usable as a reduced Copy Test with stated limits (50 fixed Wallets; ranked by the spike's estimate; *Not enough data* with fewer than 2 Passers) | **Yes**: run it this week, 3 workers; rule and script committed before the run; zip it to the USB stick next to the first capture with the same checksum routine |
| Running it safely | Resume from saved Wallet rows and price files | **Added**: make it properly resumable before starting ("if it dies at hour 2 it picks up where it stopped"). The AI then made every write atomic, saved the ranking as it goes and froze the pool once chosen; it proved the resume on the real run by stopping it at 54 of 150 ranked and restarting (it went on at 55) |
| Where the daily check runs | A scheduled GitHub Actions workflow, or a local task | **GitHub Actions**: it runs when his PC is off and shows whether the course organisation allows Actions. His conditions: one plain GET, no keys, alert only when the answer changes; if Actions is blocked, a local task and a log of how we found out |
| Plan first | The fallback and the daily check written into PRD FR-18 and spine AD-24 before any code | As proposed |

The AI also checked the current `actions/cache` release before pinning it (v6.1.0) and tested the workflow's check locally against the live route: the first run and a repeated answer stayed quiet, and a planted change from "coarse" to "one-minute" raised the alert.

## 3. What happened

- The workflow's first run, triggered by its push, finished green (2026-10-24, 15:15 UTC): **GitHub Actions works in the course organisation**. This also closes the open risk from the architecture step for the CI. The daily schedule starts once the workflow is on `main`.
- The insurance pool was picked by the committed rule: 150 shortlisted, 1 protocol contract dropped, 50 Wallets frozen in `pool.json` (553 requests). The price capture was running when this log was written; its counts go in `spike/FINDINGS.md`.
