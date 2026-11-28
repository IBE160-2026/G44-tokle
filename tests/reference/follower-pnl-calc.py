"""Reference calculation of Follower PnL, Follower Return and Real PnL.

Made from the PRD's definitions (section 3 Glossary, FR-3, FR-4, FR-18a) and the
data file alone. Standard library only, exact decimal arithmetic.

Run as:
    python follower-pnl-calc.py follower-pnl-set.json <out_dir>

Writes <out_dir>/follower-pnl.csv.
"""

import csv
import json
import os
import sys
from decimal import Decimal, getcontext

# Every product and sum below is a finite decimal, so it is exact. Only the two
# divisions (a partly sold Position's s, and Follower Return) can be endless;
# 50 significant digits is far past anything the cent-level check needs.
getcontext().prec = 50

COPY_DELAYS_SECONDS = (60, 300, 1800)  # Copy Delay: 1, 5 and 30 minutes
SPREAD_ALLOWANCE = Decimal("0.005")  # Spread Allowance: half a cent
PRICE_CAP = Decimal(1)  # "capped at 1"
SLIVER_FRACTION = Decimal("0.01")  # Sliver: less than 1% of the bought shares...
SLIVER_SHARES = Decimal(1)  # ...and fewer than 1 share

COLUMNS = [
    "row_type",
    "delay_seconds",
    "condition_id",
    "token_id",
    "fill_timestamp",
    "fill_shares",
    "s",
    "recorded_price",
    "price_paid",
    "follower_fee",
    "fill_pnl",
    "fill_spent",
    "follower_pnl",
    "spent",
    "follower_return",
    "real_pnl",
]


def text(value):
    """A Decimal as plain digits: full precision, no exponent, no padding zeros."""
    if isinstance(value, Decimal):
        if value == 0:
            return "0"
        return format(value.normalize(), "f")
    return str(value)


def schedule_fee(shares, price, market):
    """Fee by the Market's fee schedule: shares * rate * (price * (1 - price)) ^ exponent.

    The Glossary writes s * rate * p * (1 - p) "with the rate and exponent from
    the Market's fee schedule". With exponent 1 (both Markets here) the exponent
    changes nothing. 0 in a Market that charges no fee.
    """
    if not market["fees_enabled"]:
        return Decimal(0)
    base = price * (Decimal(1) - price)
    exponent = market["fee_exponent"]
    if exponent != 1:
        base = base ** exponent
    return shares * market["fee_rate"] * base


def outcome_of(market, token_id):
    """Outcome o (1 or 0) of a token, or None when the Market is not clearly resolved (FR-3)."""
    prices = market["outcome_prices"]
    resolved = (
        market["closed"]
        and market["closed_time"] is not None
        and sorted(prices) == [Decimal(0), Decimal(1)]
    )
    if not resolved:
        return None
    return prices[market["token_ids"].index(token_id)]


def build_positions(data):
    """Combine the Wallet's fills into Positions (FR-3)."""
    markets = {m["condition_id"]: m for m in data["markets"]}
    built = []
    for listed in data["positions"]:
        key = (listed["condition_id"], listed["token_id"])
        market = markets[key[0]]
        rows = [
            r
            for r in data["activity"]
            if r["type"] == "TRADE" and (r["condition_id"], r["token_id"]) == key
        ]
        buys = sorted((r for r in rows if r["side"] == "BUY"), key=lambda r: r["timestamp"])
        sells = [r for r in rows if r["side"] == "SELL"]
        bought = sum((r["size"] for r in buys), Decimal(0))
        sold = sum((r["size"] for r in sells), Decimal(0))
        held = bought - sold  # shares held at resolution: bought minus sold (FR-3)
        outcome = outcome_of(market, key[1])
        if outcome is None:
            raise SystemExit("Market %s is not clearly resolved" % key[0])
        if bought != listed["shares_bought"]:
            raise SystemExit("shares bought disagree between the two sources for %s" % key[1])
        for r in buys + sells:
            if r["timestamp"] >= market["closed_time"]:
                raise SystemExit("a fill at or after resolution in %s" % key[1])

        # Entry Price p: share-weighted average of the buy fills; sells do not change it.
        entry_price = sum((r["size"] * r["price"] for r in buys), Decimal(0)) / bought

        # Own Fees: taker fees paid on the buys, read as the cash that changed
        # hands beyond size * price, and checked against the fee schedule (FR-4).
        own_fees = Decimal(0)
        for r in buys:
            fee = r["usdc_size"] - r["size"] * r["price"]
            if fee != 0:
                rates = [market["fee_rate"]] + [Decimal(n) / 100 for n in range(1, 11)]
                fits = market["fees_enabled"] and any(
                    fee == schedule_fee(r["size"], r["price"], dict(market, fee_rate=rate))
                    for rate in rates
                )
                if not fits:
                    print("fee fails the schedule check, counted as 0:", r, file=sys.stderr)
                    fee = Decimal(0)
            own_fees += fee

        is_sliver = (
            Decimal(0) < held < SLIVER_SHARES and held < SLIVER_FRACTION * bought
        )
        built.append(
            {
                "condition_id": key[0],
                "token_id": key[1],
                "market": market,
                "buys": buys,
                "bought": bought,
                "held": held,
                "outcome": outcome,
                "entry_price": entry_price,
                "own_fees": own_fees,
                "is_resolved": held > 0 and not is_sliver,
                "is_sliver": is_sliver,
            }
        )
    return built


def real_pnl(positions):
    """Real PnL: sum of s * (o - p) over Resolved Positions and Slivers, minus their Own Fees."""
    total = Decimal(0)
    for pos in positions:
        if pos["is_resolved"] or pos["is_sliver"]:
            total += pos["held"] * (pos["outcome"] - pos["entry_price"]) - pos["own_fees"]
    return total


def follower_fills(pos, delay, price_at):
    """One row per buy fill of a Position at one Copy Delay, or None if a price is missing."""
    fills = []
    for buy in pos["buys"]:
        recorded = price_at.get((pos["token_id"], buy["timestamp"] + delay))
        if recorded is None:
            return None  # no recorded price: the Position is left out of this delay (FR-18a)
        # s: this fill's share of the shares held at resolution, in proportion
        # to the fill's size among all the Position's bought shares.
        s = pos["held"] * buy["size"] / pos["bought"]
        # p_delay: the recorded price one Copy Delay later, plus the Spread Allowance, capped at 1.
        price_paid = min(recorded + SPREAD_ALLOWANCE, PRICE_CAP)
        fee = schedule_fee(s, price_paid, pos["market"])
        fills.append(
            {
                "fill_timestamp": buy["timestamp"],
                "fill_shares": buy["size"],
                "s": s,
                "recorded_price": recorded,
                "price_paid": price_paid,
                "follower_fee": fee,
                "fill_pnl": s * (pos["outcome"] - price_paid) - fee,
                "fill_spent": s * price_paid + fee,
            }
        )
    return fills


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: python follower-pnl-calc.py follower-pnl-set.json <out_dir>")
    with open(argv[1], encoding="utf-8") as handle:
        data = json.load(handle, parse_float=Decimal)
    out_dir = argv[2]
    os.makedirs(out_dir, exist_ok=True)

    price_at = {(p["token_id"], p["t"]): Decimal(p["price"]) for p in data["prices"]}
    positions = build_positions(data)
    copied = [pos for pos in positions if pos["is_resolved"]]
    wallet_real_pnl = real_pnl(copied)  # the Wallet's own Real PnL over the same Positions

    fill_rows, position_rows, wallet_rows = [], [], []
    for delay in COPY_DELAYS_SECONDS:
        wallet_pnl = Decimal(0)
        wallet_spent = Decimal(0)
        for pos in copied:
            fills = follower_fills(pos, delay, price_at)
            if fills is None:
                print("left out at %ss: %s" % (delay, pos["token_id"]), file=sys.stderr)
                continue
            ids = {
                "delay_seconds": delay,
                "condition_id": pos["condition_id"],
                "token_id": pos["token_id"],
            }
            for fill in fills:
                fill_rows.append(dict(ids, row_type="fill", **fill))
            pnl = sum((f["fill_pnl"] for f in fills), Decimal(0))
            spent = sum((f["fill_spent"] for f in fills), Decimal(0))
            position_rows.append(dict(ids, row_type="position", follower_pnl=pnl, spent=spent))
            wallet_pnl += pnl
            wallet_spent += spent
        wallet_rows.append(
            {
                "row_type": "wallet",
                "delay_seconds": delay,
                "follower_pnl": wallet_pnl,
                "spent": wallet_spent,
                "follower_return": wallet_pnl / wallet_spent,
                "real_pnl": wallet_real_pnl,
            }
        )

    out_path = os.path.join(out_dir, "follower-pnl.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)
        for row in fill_rows + position_rows + wallet_rows:
            writer.writerow([text(row[c]) if c in row else "" for c in COLUMNS])
    print("wrote", out_path)


if __name__ == "__main__":
    main(sys.argv)
