# Follower PnL reference calculation: working notes

Made from `prd.md` (section 3 Glossary, FR-3, FR-4, FR-18a, FR-18c) and `follower-pnl-set.json` alone. No application code was read. The script is `follower-pnl-calc.py`; its output, with full precision, is `follower-pnl.csv`.

Run: `python follower-pnl-calc.py follower-pnl-set.json <out_dir>`

## Result

| Copy Delay | Follower PnL | Money spent | Follower Return | Wallet's Real PnL |
|---|---|---|---|---|
| 1 minute (60 s) | $232.07 | $317.93 | 73.0% | $238.12 |
| 5 minutes (300 s, Main Copy Delay) | $220.16 | $329.84 | 66.7% | $238.12 |
| 30 minutes (1800 s) | $148.55 | $401.45 | 37.0% | $238.12 |

Unrounded: Follower PnL 232.0656235, 220.16107975, 148.54937975; spent 317.9343765, 329.83892025, 401.45062025; Real PnL 238.1235. No Position is left out at any delay.

Per Position (Follower PnL / spent):

| Position | 1 min | 5 min | 30 min |
|---|---|---|---|
| A, token 1111…, won, 3 fills | 133.8842025 / 116.1157975 | 127.0856025 / 122.9143975 | 82.95929 / 167.04071 |
| B, token 2222…, lost, 1 fill | −102.5 / 102.5 | −98.89676 / 98.89676 | −73.69551 / 73.69551 |
| C, token 3333…, won, 2 fills, partly sold | 200.681421 / 99.318579 | 191.97223725 / 108.02776275 | 139.28559975 / 160.71440025 |

Cross-check: in each delay, Follower PnL + spent = 550, the payout of the 250 + 300 winning shares.

## How each rule was applied

1. **Positions (Glossary *Position*, FR-3).** Fills are grouped by Market and outcome token: A = 120 + 80 + 50 shares, B = 200, C = 300 + 100 bought and 100 sold. Both Markets are closed, have outcome prices exactly 1 and 0 and a resolution time, so they are resolved (FR-3). Outcome *o* is the token's outcome price: A 1, B 0, C 1.
2. **Shares held at resolution (FR-3: "bought shares minus its sold shares").** A 250, B 200, C 400 − 100 = 300. All three are Resolved Positions; none is a Sliver. B is listed as OPEN: an unredeemed loser, which FR-3 says counts like any other.
3. **Each fill is copied at its own time plus the Copy Delay (FR-18a; Glossary *Follower PnL*: "A Position bought in 12 fills is copied 12 times, each at its own time").** The recorded price is the `prices` point of the same token at exactly `fill timestamp + delay`. Every fill is on a whole minute and every point needed exists.
4. **Price paid (Glossary *Follower PnL*, *Spread Allowance*).** *p*<sub>delay</sub> = recorded price + 0.005, capped at 1. The cap bites once: A's third fill at 30 minutes, 0.997 + 0.005 = 1.002, becomes 1.
5. **Follower Fee (Glossary).** *s* · rate · *p*<sub>delay</sub> · (1 − *p*<sub>delay</sub>) with the Market's rate: 0.05 for A and B, 0.03 for C.
6. **Fill profit and money spent (Glossary *Follower PnL*, *Follower Return*).** Profit = *s* · (*o* − *p*<sub>delay</sub>) − Follower Fee; spent = *s* · *p*<sub>delay</sub> + Follower Fee. Summed per Position, then over the three Positions. Follower Return = the Wallet's Follower PnL ÷ the Wallet's money spent.
7. **Real PnL (Glossary *Real PnL*, *Entry Price*, *Own Fees*; FR-4).** Σ *s* · (*o* − *p*) minus Own Fees, with *p* the share-weighted average of the buy fills:
   - A: 250 · (1 − 0.44) − 3.054 = 136.946
   - B: 200 · (0 − 0.50) − 2.5 = −102.5
   - C: 300 · (1 − 0.3125) − 2.5725 = 203.6775
   - Total 238.1235. All six fees pass the FR-4 check at the Market's listed rate.

Arithmetic is `decimal.Decimal` with JSON numbers parsed straight to Decimal. Every figure is an exact finite decimal except Follower Return, a division kept to 50 significant digits.

## Readings I had to choose

1. **A partly sold Position's *s* per fill (Position C).** The Glossary says *s* is "that fill's share of the shares held at resolution" but not how a sell is spread over the fills. I split the 300 held shares in proportion to fill size: 300 · 300/400 = 225 and 300 · 100/400 = 75. This matches FR-3, which tests a partly sold Position "at the original Entry Price", the average over all buy fills. Alternatives: the sell comes off the first fill (200 and 100), which changes Follower PnL by −1.26, −1.13 and −1.12 at 1, 5 and 30 minutes (Return 72.3%, 66.2%, 36.6%); or off the last fill (300 and 0), which changes it by +3.79, +3.40 and +3.37 (Return 75.1%, 68.5%, 38.2%). This is the only choice that moves the result past the cent by a wide margin.
2. **Which price the Follower Fee is charged on.** I used the price paid, with the Spread Allowance and the cap, because the Glossary defines *p*<sub>delay</sub> as the market price "plus the Spread Allowance (capped at 1)" and the fee as the fee "for buying *s* shares at *p*<sub>delay</sub>". Alternative: the recorded price without the allowance. That changes Follower PnL by +0.0226, +0.0184 and −0.0023, so the cent figures would read 232.09, 220.18 and 148.55; the Return stays 73.0%, 66.8% (from 66.7%) and 37.0%. Under my reading the capped fill pays no fee, since 1 · (1 − 1) = 0.
3. **Own Fees are not a field in the data.** The Glossary says "as Polymarket recorded them". I read a buy's fee as `usdc_size − size · price`, the cash beyond the price. All six equal `size · rate · price · (1 − price)` at the listed rate, so the reading and the FR-4 check agree.
4. **Own Fees of the partly sold Position C.** I subtracted the whole fee on both buys (2.5725), because *Own Fees* is "the taker fees a Wallet paid on the buys of a Position" and Real PnL subtracts "the Own Fees on those Positions". Alternative: only the held three quarters (1.929375), which gives Real PnL 238.766625 (238.77 instead of 238.12).
5. **The fee exponent.** The Glossary formula shows no exponent but says the "rate and exponent" come from the fee schedule. I read it as *s* · rate · (*p* · (1 − *p*))<sup>exponent</sup>. Both Markets have exponent 1, so no number depends on this.
6. **Which recorded price is "one Copy Delay after".** I take the point at exactly that second and nothing else (FR-18c: no coarser prices). The data needs no choice here. A fill between two whole minutes would need a rule the PRD does not give.
7. **Missing prices.** FR-18a leaves out the whole Position; FR-18c says "a buy ... is left out". The script follows FR-18a. It does not arise in this set.
8. **The Copy Sample.** The Glossary limits it to the after part of a Cut-off Date. The set has no Cut-off Date, so all three Resolved Positions are priced, as the task states.
