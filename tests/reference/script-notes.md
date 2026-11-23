# Real PnL reference: script notes

Independent check of Real PnL for two Wallets, made only from `prd.md` (§3 Glossary, FR-3, FR-4), `fields.md` and the two Wallet files. No other file, code or web source was used.

Run (stdlib only):

```
python -I real_pnl_reference.py ../wallet-0x0f4b0a.json ../wallet-0x091596.json .
```

Outputs, all in `out/`:
- `<short>-real-pnl.csv`: one row per Position, plus a TOTAL row (columns as specified).
- `<short>-fee-check.csv`: every buy fill in a Market with a fee schedule, or with a recorded fee, showing the recorded fee, the fee the schedule expects, and the check result. This file is extra; it is how the fee check can be audited.
- stdout: a summary and the totals under each alternative reading (used below).

Two runs give byte-identical CSVs. Rows are sorted by `condition_id`, then `token_id`, with `\n` line endings.

## Results

| Wallet | Real PnL | Σ s·(o − p) | Own Fees | Resolved | Sliver | Left out | Failed fees (count, recorded total) |
|---|---|---|---|---|---|---|---|
| 0x0f4b0a | **−188.49** | −188.235774652495… | 0.252100000280511 (0.25) | 210 | 43 | 21 | 7, 0.2779299992182378 |
| 0x091596 | **−49,571.22** | −48,483.876531602940… | 1,087.3404388307589023 (1,087.34) | 14 | 24 | 28 | 2, 44.4823999718996 |

Full-precision Real PnL: 0x0f4b0a −188.4878746527758060938…; 0x091596 −49571.2169704336989648….

Left out, by first reason:
- 0x0f4b0a: 21 × fully sold before resolution.
- 0x091596: 25 × split, merged or converted shares in that Market; 2 × sources disagree on shares bought by more than 1% (both also "market not resolved"); 1 × fully sold before resolution.
- 0x091596, counting every reason that applies to a row: converted 25, sources disagree 23, shares held out of range 1, market not resolved 2, fully sold 1.

## How each rule was applied

**Position (Glossary, FR-3).** One Position per (`condition_id`, `token_id`), that is, one outcome in one Market. The set of Positions is the union of the `positions` rows (CLOSED and OPEN both) and the tokens in TRADE activity rows. A Wallet that holds both outcomes of a Market has two Positions.

**Shares bought, sold, held (FR-3).** Shares bought = Σ `size` of the Position's TRADE BUY rows. Shares sold = Σ `size` of its TRADE SELL rows. Shares held at resolution s = bought − sold. REDEEM rows are never used. No trade in either file falls after its Market's `closed_time`, so "held at resolution" equals "held after the last trade".

**Entry Price p (Glossary).** Σ(size · price) / Σ size over the buy fills, using each fill's `price` field. Sells don't change it. s · p is computed as s · Σ(size·price) / Σ size, a single division at 80-digit precision.

**Market resolved (FR-3).** `closed` is true, every outcome price is exactly 0 or 1 with exactly one 1, and `closed_time` is not null. If the Market is closed in any other way, the Position is left out as "unclear resolution" (no case in these files). If `closed` is false, the Market has not resolved (2 Markets in 0x091596).

**Outcome o.** 1 if the outcome price at the Position's `token_id` index is 1, else 0.

**Left-out reasons (FR-3).** These are checked on every Position. The `reason` column lists all that apply, in this order; the first is the primary one:
1. *fully sold before resolution*: bought > 0 and held exactly 0.
2. *split, merged or converted shares in that Market*: the Market has a SPLIT or MERGE row, or belongs to the negative-risk event named by a CONVERSION row (see J9).
3. *token appears only in the activity rows*: the token has trade rows but no `positions` row (none in these files).
4. *shares held not between 0 and the shares bought*: held < 0 or held > bought (activity figures).
5. *sources disagree on shares bought by more than 1%*: |activity bought − `positions.shares_bought`| / the larger of the two > 0.01.
6. *unclear resolution*: see above.
7. *history not read in full*: the Position's `first_entry_at` is before `activity_from`, or its `last_event_at` is after `activity_until`. Both are null in both files, so no Position is left out for this.
8. *market not resolved*: not one of FR-3's reasons; see J13.

**Sliver (Glossary, FR-3).** A Position with no left-out reason and 0 < held < 1% of shares bought and held < 1 share. Its money counts; it is not counted as a bet.

**Resolved Position.** A Position with no left-out reason and held > 0 that is not a Sliver.

**Real PnL (Glossary, FR-4).** Σ s·(o − p) − Own Fees, over Resolved Positions and Slivers. Each row's `pnl_contribution` is s·(o − p) − own_fees at full precision. The TOTAL row's Real PnL and Own Fees are each rounded to the cent with ROUND_HALF_UP; nothing else is rounded. The CSV rows, summed, give the same totals.

**Own Fees and the fee check (Glossary, FR-4).** For each buy fill of the Position:
- recorded fee = `usdc_size − size · price` (see J1);
- expected fee = size · rate · (price · (1 − price))^exponent from the Market's `fee_rate` and `fee_exponent`, or 0 if `fees_enabled` is false (J2);
- |recorded| ≤ 0.0001 is "no fee recorded" (a maker fill, or a Market without fees): it counts as 0 and is not a failure (J4);
- otherwise the fee passes if |recorded − expected| ≤ max(0.0001, 1% of expected) (J3), and then the recorded amount counts;
- a fee that fails counts as 0 (FR-4) and is listed below.

The `own_fees` column holds this sum for every Position, left-out ones included. Only resolved and sliver rows go into the TOTAL.

## Fees that failed the check

None of these are counted. All 9 are on Positions that count (resolved or sliver), so counting them would lower Real PnL by their recorded total (A1 below). In every case the recorded fee matches the same p·(1 − p) shape at a *different* rate than the one listed (the ratio column).

| Wallet | condition_id | Position status | fill time | size | price | recorded fee | listed rate | expected | ratio |
|---|---|---|---|---|---|---|---|---|---|
| 0x0f4b0a | 0xa919b6a7… | resolved | 1777505436 | 12.5 | 0.08 | 0.046 | 0.01 | 0.0092 | 5.00 |
| 0x0f4b0a | 0xc7bc5d75… | resolved | 1777508324 | 20 | 0.1 | 0.072 | 0.01 | 0.018 | 4.00 |
| 0x0f4b0a | 0xd175952d… | resolved | 1777508510 | 51.6875 | 0.0193470375 | 0.04903 | 0.01 | 0.0098065 | 5.00 |
| 0x0f4b0a | 0x7876e776… | resolved | 1778199168 | 1.369862 | 0.7299998102 | 0.01349 | 0.01 | 0.0027 | 5.00 |
| 0x0f4b0a | 0xf74326b8… | resolved | 1778199231 | 2.564101 | 0.3899998479 | 0.03049 | 0.01 | 0.0061 | 5.00 |
| 0x0f4b0a | 0x206138f3… | sliver | 1779156921 | 2.027775 | 0.72 | 0.02043 | 0.01 | 0.0040880 | 5.00 |
| 0x0f4b0a | 0x56e3a277… | resolved | 1779205903 | 14.285713 | 0.0699999363 | 0.04649 | 0.01 | 0.0093 | 5.00 |
| 0x091596 | 0xf7b7e74c… | resolved | 1779033324 | 10 | 0.5 | 0.175 | 0.01 | 0.025 | 7.00 |
| 0x091596 | 0x375409bc… | sliver | 1783805896 | 8783.348 | 0.1138518023 | 44.3074 | 0.03 | 26.5844 | 1.67 |

Failed totals: 0x0f4b0a 7 fees, 0.2779299992182378 recorded. 0x091596 2 fees, 44.4823999718996 recorded. Exact values are in the `*-fee-check.csv` files.

Passed fees: 12 in 0x0f4b0a and 38 in 0x091596, each within 0.000011 of the expected value (largest relative gap 0.11%). The recorded values look like the expected fee cut to 5 decimals. No-fee fills in fee-charging Markets: 6 in 0x0f4b0a and 4 in 0x091596, each with |recorded| ≤ 0.00000051. No Market without fees shows a recorded fee: the largest |usdc_size − size·price| there is 0.0000045.

## Judgment calls and unclear points

Each total below comes from running the alternative in the script (stdout). "Moves" means the change to Real PnL, rounded to the cent.

| # | Point | What I did | Alternative | 0x0f4b0a moves | 0x091596 moves |
|---|---|---|---|---|---|
| J6 | Own Fees on a partly sold Position (Resolved or Sliver). Glossary: "the taker fees … paid on the buys of a Position" | All buy fills' fees count, including fees on shares later sold | Pro rata: fees × held/bought | +0.00 (−188.49) | **+636.90 (−48,934.31)** |
| J9 | Which Markets a CONVERSION touches. The row carries the negative-risk event id, not a Market id | Every Market of that event (24 Markets; 25 Positions left out) | The rule leaves out nothing, because the row names no Market | 0 (no conversion) | **+952.42 (−48,618.79)** |
| J7 | Fees on sells | Not Own Fees (the Glossary says "on the buys") | Also subtract sell-side fees of counted Positions | −0.00 | **−1,272.52 (−50,843.73)** |
| J8 | Entry Price source | Fill `price` (share-weighted) | `usdc_size/size`, which folds the fee into p and so counts it twice with Own Fees | −0.51 (−189.00) | −450.61 (−50,021.83) |
| A1 | Failed fees. FR-4 is explicit, so this is not really a choice | Count 0 | Count as recorded | −0.28 (−188.77) | −44.48 (−49,615.70) |
| J1 | Where a fee is "recorded" | `usdc_size − size·price` on each buy fill. There is no fee field, and `usdc_size` is the cash that changed hands | Treat fees as absent | +0.25 | +1,087.34 |
| J3 | Fee-check tolerance (the PRD gives none) | max(0.0001, 1% of expected) | Any tolerance from 0.000011 abs (0.11% rel) to 0.0107 abs (66% rel) gives the same pass/fail split | 0 | 0 |
| J4 | A fill with a ≈ 0 fee in a fee-charging Market (maker) | "No fee recorded": counts 0, not a failure (Glossary: 0 on maker fills) | Count these as failures | 0 money; failed count +6 | 0 money; failed count +4 |
| J10 | Denominator of the 1% source gap | The larger of the two figures | Activity figure or `positions` figure | 0 | 0 |
| J12 | Sliver test: "less than 1% … and fewer than 1 share" | Both must hold, and a Sliver must also pass all left-out checks | "or" | 0 (no Position meets only one limit; the largest Sliver holds 0.0095 shares, 0.67%) | 0 (largest Sliver 0.036 shares, 0.032%) |
| J13 | Position in a Market that is not closed | `left_out`, reason "market not resolved". FR-3 doesn't name this case; such a Position simply isn't a Resolved Position | Leave the reason empty or drop the row | 0 | 0 (2 rows, no buy fills, no outcome) |
| J11 | "shares held not between 0 and the shares bought": which shares bought | Activity bought; held = 0 counts as fully sold, not out of range | The `positions` figure | 0 | 0 (the only case, 0xaf51603d…, is held −1,666.67 and is also converted) |
| J15 | Several reasons on one Position | All listed in a fixed order; the first is primary | Single reason | 0 | 0 |
| J16 | `own_fees` on left-out rows | Filled in (the Position's checked fees), but not part of the TOTAL. TOTAL `own_fees` is the counted rows' sum, rounded to the cent | Blank on left-out rows | 0 | 0 |

More detail on the calls that move the total:

- **J6 (Own Fees on sold shares).** In 0x091596, five Slivers bought tens of thousands of shares, paid a fee on each buy and sold almost everything. For example, 0x7976b8db… bought 52,080.59 shares, holds 0.005385, and has Own Fees of 182.19. Read literally, the Glossary says Real PnL is "minus the Own Fees on those Positions", and Own Fees are all "the taker fees … paid on the buys of a Position", so the whole fee counts. FR-3 adds that a Sliver's "money stays in Real PnL". The pro-rata reading would charge only the fee share of the shares held at resolution. The PRD doesn't address this case directly, so it is worth a decision.
- **J9 (CONVERSION scope).** 0x091596 has one CONVERSION row (size 1,666.666665, at 1747595267) for the event 0x5b32843a… (24 Markets). The data shows what happened. The Wallet bought 1,666.666665 NO shares in 0x5fc28bfc… and never sold them on the book. 23 sibling Markets each show 1,666.6666 extra shares in `positions` with no matching buy: 21 Positions have no trade rows at all, and 0xaf51603d… and 0xde69f3a4… each show a 1,666.67 gap. So the NO shares were converted into YES shares, and the Wallet did not hold them at resolution. If the rule left nothing out, that NO Position would count +1,066.67 that the Wallet never received. The other two Positions that would join are 0x5fc28bfc…'s YES side (−31.00) and 0xde69f3a4… (−83.24; its 0.90% source gap is under the 1% limit, so only the conversion rule catches it). Leaving out the whole event is the only reading that follows the data, because a CONVERSION burns NO shares in some of the event's Markets and creates YES shares in the others.
- **J7 and J8** are shown so that a comparison can spot them if the app made those choices. Neither is my reading of the PRD.

Other points, with no effect on these numbers:
- The fee formula with an exponent other than 1 is not defined in the PRD; the Follower Fee writes s · rate · p · (1 − p) "with the rate and exponent". Every Market here has exponent 1.0, so this doesn't matter.
- REDEEM rows: 28 in 0x0f4b0a, ignored as FR-3 requires.
- 0x091596's two unresolved Markets (0x2053d851…, 0xce9a5fa3…) have `positions` rows (5,131.7553 and 4,432.1014 shares bought) but no trade rows, so they are also "sources disagree".

## Files read

Only these four input files: `prd.md`, `fields.md`, `wallet-0x0f4b0a.json`, `wallet-0x091596.json`. Everything else in `out/` was written by me: `real_pnl_reference.py`, the four CSVs and this file.
