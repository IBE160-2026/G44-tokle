# Working notes: Real PnL for Wallet 0x29306ddc4724e24a23bf1c8679aa034376ea9dcb

Independent check, done from `prd.md` (§3 Glossary, §4.1 FR-3, §4.2 FR-4) and `wallet-0x29306d.json` only.
Script: `calc.py` (standard library only, all `Decimal`; JSON numbers parsed straight to `Decimal`).

**Result: Real PnL = 295.0629789947927066, so $295.06 to the cent.**
Counts: 18 Resolved Positions, 3 Slivers, 3 left out (24 Positions in all).
Own Fees counted: $0 in total. 293.95 of the 295.06 comes from one Position (0x324d…, 753.73 shares at 0.61, won).

## How each rule was applied

- **Positions (Glossary, FR-3 bullet 1-2).** One Position per (condition_id, token_id). Built from both sources: the
  TRADE rows in `activity` and the `positions` list (all 24 entries are CLOSED; there are no OPEN ones). 23 Positions
  appear in both; 1 (0x0b4c…) appears only in the positions list; none appears only in activity.
- **Entry Price p.** Share-weighted average of the BUY fills' `price` field; sells do not change it.
- **Shares held s.** Sum of BUY `size` minus sum of SELL `size` from the Wallet's own TRADE rows. REDEEM rows are
  ignored for share counting (FR-3).
- **Market resolved (FR-3 bullet 3).** `closed` is true, `outcome_prices` are exactly 0 and 1, `closed_time` present.
  23 of 24 Markets pass; 0x0b4c… fails (closed=false, closed_time=null, prices 0.0085/0.9915).
- **Outcome o.** The `outcome_prices` entry at the same index as the Position's token in `token_ids`.
- **Left-out checks (FR-3 bullet 5-6).** Fully sold (held = 0); token only in activity; held not in [0, bought];
  source gap = |activity bought − positions shares_bought| / positions shares_bought > 1%; Market not resolved.
- **Sliver (Glossary).** Held at resolution < 1% of bought shares **and** < 1 share. Money counts in Real PnL.
- **Timing.** No TRADE row is at or after its Market's `closed_time`, so every sell happened before resolution and
  "held at resolution" = bought − sold for every Position.
- **Real PnL (Glossary, FR-4).** Σ s·(o − p) over Resolved Positions and Slivers, minus their Own Fees. Exact
  decimal sum; only the total rounded (ROUND_HALF_UP) to 0.01.

## Per-Position decisions (the non-trivial ones)

| Market | Decision | Why |
|---|---|---|
| 0x7e84… | Sliver | bought 16.503, sold 16.5, held 0.003 (0.018%, < 1 share); o = 1; contributes 0.000006 |
| 0x7da6… | Sliver | bought 16.4825, sold 16.48, held 0.0025; o = 1; contributes 0.000005 |
| 0xeba5… | Sliver | bought 17.635666, sold 17.63, held 0.005666; o = 1; contributes 0.0000339960… |
| 0xde8c… | Resolved (partly sold) | two buys (18.775 + 1.255 = 20.03 at 0.996), sold 18.77 before resolution, held 1.26 (6.3%, ≥ 1 share), so not a Sliver; tested with s = 1.26 at p = 0.996 (FR-3 bullet 9); contributes 0.00504 |
| 0xd8b9… | Left out: fully sold | bought 21.8, sold 21.8 before resolution |
| 0xc9dc… | Left out: fully sold | bought 3618, sold 771.82 + 2846.18 = 3618 before resolution (would have lost: o = 0) |
| 0x0b4c… | Left out: source gap above 1%; unclear resolution | in the positions list (21.04 shares bought) but no activity row at all, so the gap is 100%; and its Market is not resolved |
| all other 15 | Resolved, held in full | one buy each, no sells, o = 1 in every case, source gap ≤ 0.008% |

All 18 Resolved Positions and all 3 Slivers won (o = 1). The Wallet mostly bought outcomes priced 0.96–0.999.

## Fee check (FR-4), per fee-charging Market

Own Fee per buy fill = `usdc_size` − `size` × `price`. Schedule fee used for the check, taken from the PRD's own
fee form (Follower Fee): s · rate · (p · (1 − p))^exponent.

- **0x6928… (fees_enabled, fee_rate 0.01, fee_exponent 1).** One buy: 21.93 at 0.993, usdc 21.77649.
  Recorded fee = 21.77649 − 21.93 × 0.993 = **0 exactly**. A taker fee by the schedule would be
  21.93 × 0.01 × 0.993 × 0.007 = 0.0015243543. Recorded 0 is consistent with a maker fill (Glossary: Own Fees are 0
  on maker fills), so the check passes and Own Fees = 0. (Had the schedule fee been charged and counted instead, the
  total would be 295.0614546…, still $295.06.)
- **0x0b4c… (fees_enabled, fee_rate 0.05, fee_exponent 1).** No buy fills in activity, so nothing to check;
  the Position is left out anyway.
- **All 22 other Markets: fees_enabled = false.** Own Fees are 0 by the Glossary. The residual
  `usdc_size − size × price` on their buys is between −6.5e-10 and +7e-11 (or exactly 0): rounding in the recorded
  price, far below one micro-USDC. Not treated as fees, and none counted as a failed fee.

Failed fee checks: **0**.

## Judgment calls and unclear points in the PRD

1. **Whose source does the gap rule measure against?** FR-3 says "the two sources disagree on shares bought by more
   than 1%" without a base. I used |activity − positions| / positions. The positions list reports shares_bought
   truncated to 4 decimals (e.g. 1.0182 vs 1.018277), so every gap is tiny (max 0.0076%) and the base choice
   changes nothing except for 0x0b4c…, which is 100% in any base.
2. **A Market that has not resolved at all.** FR-3 defines "resolved" and names "unclear resolution" for Markets that
   resolved "any other way (for example 50-50)". It does not name a reason for a Market that is still open
   (closed=false, no closed_time). I filed 0x0b4c… under "unclear resolution" as the nearest PRD reason, together
   with "source gap above 1%". No precedence between the FR-3 reasons is given, so I list both. It does not affect
   Real PnL.
3. **A token only in the positions list.** FR-3 names the reverse case ("token appears only in the activity rows")
   but not this one. 0x0b4c… is covered by the gap rule and the resolution rule, so I did not need a new reason.
4. **Is the activity complete?** The task says `activity_from`/`activity_until` = null means the whole activity, so I
   did **not** apply "history could not be read in full". But the file itself hints at gaps:
   - the 0x0b4c… buy (first_entry_at 2026-02-11 07:13 UTC) falls inside the activity's time span, yet has no row;
   - the last activity row is 2026-03-16; five positions have `last_event_at` on 2026-08-17 (0x0b4c…, 0xaec7…,
     0x9030…, 0xdf3a…, 0xc798…), so their later events (most likely redemptions for the four resolved ones) are missing
     from activity.
   Redemptions never count shares (FR-3), and the four resolved ones' buys match the positions list within 0.003%, so
   I kept them as Resolved Positions. **If an app instead marks those four as "not fully read" and leaves them out,
   its total would be 295.0172119…, i.e. $295.02.** This is the only judgment call that moves the cent.
5. **Splits, merges, conversions.** The file only carries TRADE and REDEEM rows, so the "split, merged or converted"
   rule cannot be tested from it. I assumed none occurred. Several Markets are in negative-risk events (neg_risk_id
   set); that matters for linked draws in FR-5, not for Real PnL.
6. **Entry Price from `price`, not `usdc_size / size`.** Own Fees are defined as cash − shares × price, so using cash
   per share as p would subtract any fee twice. Here the two differ by < 1e-9 per share, so the total does not move.
7. **What "checked against the Market's fee schedule" means.** The PRD does not say. I accepted a recorded fee if it is
   0 (maker) or equals the schedule's taker fee within 1e-6, otherwise counted 0 and reported it as failed. The fee
   exponent is applied as (p(1 − p))^exponent; it is 1 for both fee Markets, so this reading does not matter here.
8. **Tiny residuals in no-fee Markets** are set to 0 by the Glossary ("0 in Markets that charge no fee") and not
   reported as failed fees, because they are rounding (< 1e-9), not money.
9. **Slivers that were never redeemed.** The three Slivers have no REDEEM row; by FR-3 that does not matter, their
   s·(o − p) is counted (together 0.0000449960…, no effect at the cent).
10. **Rounding.** ROUND_HALF_UP on the final total only; the exact total ends in …0.06298, so any rounding mode gives
    $295.06.

## Sensitivity summary

| Variant | Total |
|---|---|
| As computed (PRD as read above) | **295.06** (295.0629789947927066) |
| 4 positions with missing Aug-2026 events left out as "not fully read" | 295.02 |
| 0x6928… charged the schedule taker fee | 295.06 (295.0614546…) |
| Slivers dropped from Real PnL | 295.06 |
