# Insurance pool: the rule, written before the run

Committed before `insurance_pick.py` runs, so the pick cannot be bent by what it finds (Edvard, 2026-10-24; PRD FR-18 fallback, spine AD-24).

**Why.** Polymarket's old price-history route is the only one with one-minute prices older than 7 days. If it is gone when the real-data Copy Test runs (SM-5, Story 6.6), that test needs prices captured in advance. This pool is the stand-in: a reduced Copy Test on 50 fixed Wallets, with its limits stated.

**The rule.**

1. Cut-off Date 1 July 2025 (the Sample Dataset's default, PRD §9 Q6).
2. Candidates: the Scan funnel (spine AD-21) as already read for the Sample Dataset pick: Markets resolved in the 90 days before the date, top 100 by volume; only the 77 Markets whose lists were read in full (AD-9); every Wallet in their CLOSED and OPEN lists.
3. Shortlist: the top 150 (3 × 50) by the AD-21 pre-filter, Σ CLOSED `realized_pnl` + Σ OPEN (resolved value − cost) on those Markets, ties broken by address.
4. Ranking: each shortlisted Wallet's before part (its latest 2,000 Positions in Markets resolved before the date) is fetched, and Wallets are ranked by Real PnL on the Positions held to resolution, summed in whole cents, ties broken by address. Fees are not involved: they did not exist before June 2026. A Wallet refused as a protocol contract address is dropped (AD-9, P-1) and the next one moves up. The top 50 are the pool.
5. Capture, per pool Wallet: positions (CLOSED and OPEN), activity after the date oldest-first and before it newest-first for the first-buy check (each capped at 300,000 rows, so fewer whales stop early), and one-minute price windows [t − 2 min, t + 32 min] for every buy fill of its first 2,000 after-part Positions in resolved Markets, with the `first_entry_at` check (AD-7, AD-14), from the old route at fidelity 1.
6. Pace: 3 workers sharing one locked limiter, at most 4.5 requests per second in all (under the PRD's 5).

**Nothing after the date decides who is in the pool.** Steps 2 to 4 read only Markets resolved before the date and Positions in them. The after part is read only in step 5, for the Wallets already chosen.

**Stated limits if it is used** (PRD FR-18): the pool is 50 Wallets fixed in advance, not the app's Scan; step 4's ranking is the spike's estimate (held Positions only), not the app's final Real PnL, so the app might have picked a slightly different 50; with fewer than 2 Passers the Copy Verdict is *Not enough data*, reported as it comes out.

**Output.** `spike/raw/insurance/` (git-ignored), zipped with a SHA-256 file to the backup folder and the USB stick. The pool's addresses and counts go in `spike/FINDINGS.md` after the run.
