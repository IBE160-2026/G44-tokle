#!/usr/bin/env python3
"""Independent reference calculation of a Wallet's Real PnL.

Follows only the PRD (section 3 Glossary, FR-3 Build Positions, FR-4 Real PnL)
and the field meanings in fields.md. Standard library only.

Usage:
    python -I real_pnl_reference.py <wallet.json> [<wallet.json> ...] <out_dir>

For each Wallet it writes:
    <out_dir>/<short>-real-pnl.csv   one row per Position plus a TOTAL row
    <out_dir>/<short>-fee-check.csv  every buy fill with a recorded fee, or in a
                                     Market with a fee schedule, and its check result
and prints a summary (including the judgment-call alternatives) to stdout.
"""

import csv
import json
import sys
from decimal import ROUND_HALF_UP, Decimal, getcontext
from pathlib import Path

getcontext().prec = 80  # far more than needed; only the totals are rounded

CENT = Decimal("0.01")

# Glossary, Sliver: less than 1% of its bought shares, and fewer than 1 share.
SLIVER_SHARE = Decimal("0.01")
SLIVER_MAX_SHARES = Decimal("1")
# FR-3: the two sources disagree on shares bought by more than 1%.
SOURCE_GAP_SHARE = Decimal("0.01")
# Fee check (judgment calls, see script-notes.md):
#  - a recorded fee whose size is at most FEE_ZERO is "no fee recorded"
#    (maker fill, or a Market without fees): it counts as 0 and is not a failure;
#  - a recorded fee passes when it is within max(FEE_TOL_ABS, FEE_TOL_REL x expected)
#    of the fee the Market's schedule formula gives for that fill, at the listed rate
#    or at any whole-percent rate from 1% to 10% (FR-4 as changed on 2026-11-23:
#    "Polymarket changes a Market's rate and lists only today's").
FEE_ZERO = Decimal("0.0001")
FEE_TOL_ABS = Decimal("0.0001")
FEE_TOL_REL = Decimal("0.01")
WHOLE_PERCENT_RATES = [Decimal(n) / 100 for n in range(1, 11)]  # 0.01, 0.02, ... 0.1

# Left-out reasons, in the order they are listed in the reason column.
R_SOLD = "fully sold before resolution"
R_CONVERT = "split, merged or converted shares in that Market"
R_ACTIVITY_ONLY = "token appears only in the activity rows"
R_HELD_RANGE = "shares held not between 0 and the shares bought"
R_SOURCES = "sources disagree on shares bought by more than 1%"
R_UNCLEAR = "unclear resolution"
R_NOT_READ = "history not read in full"
R_OPEN = "market not resolved"  # not one of FR-3's reasons: the Market has not resolved
R_NO_MARKET = "market data missing"  # not one of FR-3's reasons; does not occur in these files
REASON_ORDER = [R_SOLD, R_CONVERT, R_ACTIVITY_ONLY, R_HELD_RANGE, R_SOURCES,
                R_UNCLEAR, R_NOT_READ, R_OPEN, R_NO_MARKET]

COLUMNS = ["condition_id", "token_id", "buy_fills", "shares_bought", "shares_sold",
           "shares_held", "entry_price", "market_resolved", "outcome", "status",
           "reason", "own_fees", "pnl_contribution"]
FEE_COLUMNS = ["condition_id", "token_id", "timestamp", "size", "price", "usdc_size",
               "recorded_fee", "fees_enabled", "fee_rate", "fee_exponent",
               "expected_fee", "result"]


def dec(x):
    """A JSON number (already Decimal) or string as Decimal; None stays None."""
    if x is None:
        return None
    if isinstance(x, Decimal):
        return x
    if isinstance(x, bool):
        raise ValueError("boolean where a number was expected")
    return Decimal(str(x))


def fmt(x):
    """Full-precision plain decimal text, no exponent, no trailing zeros."""
    if x is None:
        return ""
    if x == 0:
        return "0"
    text = format(x.normalize(), "f")
    return text


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh, parse_float=Decimal, parse_int=Decimal)


def market_state(m):
    """FR-3: resolved = closed, outcome prices exactly 0 and 1, and a resolution time.

    Returns 'resolved', 'unclear' (closed some other way), 'open' (not closed),
    or 'missing' (no Market data).
    """
    if m is None:
        return "missing"
    if not m.get("closed"):
        return "open"
    prices = [dec(p) for p in m.get("outcome_prices") or []]
    zero_one = (len(prices) >= 2
                and all(p == 0 or p == 1 for p in prices)
                and sum(1 for p in prices if p == 1) == 1)
    if zero_one and m.get("closed_time") is not None:
        return "resolved"
    return "unclear"


def outcome_of(m, token_id):
    """Outcome o: 1 if this token's final price is 1, else 0."""
    tokens = [str(t) for t in m["token_ids"]]
    price = dec(m["outcome_prices"][tokens.index(str(token_id))])
    return Decimal(1) if price == 1 else Decimal(0)


def schedule_fee(size, price, m, rate=None):
    """Fee the Market's schedule gives for buying `size` shares at `price`:
    size * rate * (price * (1 - price)) ** exponent (exponent 1 gives the
    Glossary's s * rate * p * (1 - p)), with the Market's listed exponent.
    Without `rate`: at the listed rate; 0 if the Market charges no fee;
    None if the schedule is enabled but incomplete.
    With `rate`: at that rate instead (FR-4's whole-percent rates)."""
    if rate is None:
        if not m or not m.get("fees_enabled"):
            return Decimal(0)
        rate = dec(m.get("fee_rate"))
        if rate is None:
            return None
    exponent = dec(m.get("fee_exponent")) if m else None
    base = price * (1 - price)
    if exponent is None or exponent == 1:
        shape = base
    else:
        shape = base ** exponent
    return size * rate * shape


def fee_fits(recorded, expected):
    tolerance = max(FEE_TOL_ABS, FEE_TOL_REL * expected)
    return abs(recorded - expected) <= tolerance


def check_fee(recorded, expected, listed_rate, earlier):
    """Returns (counted_fee, result, expected fee to show).

    `expected` is the fee at the listed rate (`listed_rate` names that rate);
    `earlier` is [(rate, fee at that rate)] for the whole-percent rates 1% to 10%.
    A fee that fits the listed rate passes at it; otherwise the closest-fitting
    whole-percent rate (a tie goes to the lower rate) is the one shown."""
    if abs(recorded) <= FEE_ZERO:
        return Decimal(0), "no fee recorded", expected
    if expected is not None and fee_fits(recorded, expected):
        return recorded, f"passed at listed rate {listed_rate}", expected
    fitting = [(abs(recorded - fee), rate, fee) for rate, fee in earlier
               if fee_fits(recorded, fee)]
    if fitting:
        _, rate, fee = min(fitting)
        return recorded, f"passed at rate {fmt(rate)} (listed {listed_rate})", fee
    if expected is None:
        return Decimal(0), "FAILED (fee schedule incomplete)", expected
    return Decimal(0), "FAILED", expected


def analyse(data):
    markets = {m["condition_id"]: m for m in data["markets"]}

    # Markets where the Wallet split, merged or converted shares.
    touched = set()
    unknown_types = set()
    for r in data["activity"]:
        kind = r["type"]
        if kind in ("TRADE", "REDEEM"):
            continue
        if kind in ("SPLIT", "MERGE", "CONVERSION"):
            cid = r["condition_id"]
            if cid in markets:
                touched.add(cid)
            # On a CONVERSION row condition_id is the negative-risk event id
            # (fields.md): every Market of that event is touched.
            for m in data["markets"]:
                if m.get("neg_risk_id") is not None and m["neg_risk_id"] == cid:
                    touched.add(m["condition_id"])
        else:
            unknown_types.add(kind)

    # Buy and sell fills per (condition_id, token_id).
    buys, sells = {}, {}
    for r in data["activity"]:
        if r["type"] != "TRADE":
            continue
        key = (r["condition_id"], str(r["token_id"]))
        if r["side"] == "BUY":
            buys.setdefault(key, []).append(r)
        elif r["side"] == "SELL":
            sells.setdefault(key, []).append(r)

    listed = {}
    for p in data["positions"]:
        key = (p["condition_id"], str(p["token_id"]))
        if key in listed:
            raise ValueError(f"position listed twice: {key}")
        listed[key] = p

    act_from = dec(data.get("activity_from"))
    act_until = dec(data.get("activity_until"))

    keys = sorted(set(listed) | set(buys) | set(sells))
    rows, fee_rows = [], []
    for key in keys:
        cid, tok = key
        m = markets.get(cid)
        state = market_state(m)
        b_fills = buys.get(key, [])
        s_fills = sells.get(key, [])
        bought = sum((dec(r["size"]) for r in b_fills), Decimal(0))
        sold = sum((dec(r["size"]) for r in s_fills), Decimal(0))
        held = bought - sold
        cost = sum((dec(r["size"]) * dec(r["price"]) for r in b_fills), Decimal(0))
        entry = cost / bought if bought > 0 else None
        cash_cost = sum((dec(r["usdc_size"]) for r in b_fills), Decimal(0))

        # Own Fees: the recorded taker fee on each buy fill, checked against the schedule.
        own_fees = Decimal(0)
        failed = []
        for r in sorted(b_fills, key=lambda r: (dec(r["timestamp"]), dec(r["size"]))):
            size, price, usdc = dec(r["size"]), dec(r["price"]), dec(r["usdc_size"])
            recorded = usdc - size * price
            expected = schedule_fee(size, price, m)
            earlier = [(rate, schedule_fee(size, price, m, rate)) for rate in WHOLE_PERCENT_RATES]
            if not m or not m.get("fees_enabled"):
                listed_rate = "no fee"
            elif m.get("fee_rate") is None:
                listed_rate = "none"
            else:
                listed_rate = fmt(dec(m["fee_rate"]))
            counted, result, shown = check_fee(recorded, expected, listed_rate, earlier)
            own_fees += counted
            if result.startswith("FAILED"):
                failed.append(recorded)
            if (m and m.get("fees_enabled")) or abs(recorded) > FEE_ZERO:
                fee_rows.append({
                    "condition_id": cid, "token_id": tok,
                    "timestamp": fmt(dec(r["timestamp"])), "size": fmt(size),
                    "price": fmt(price), "usdc_size": fmt(usdc),
                    "recorded_fee": fmt(recorded),
                    "fees_enabled": str(bool(m and m.get("fees_enabled"))).lower(),
                    "fee_rate": fmt(dec(m.get("fee_rate"))) if m else "",
                    "fee_exponent": fmt(dec(m.get("fee_exponent"))) if m else "",
                    "expected_fee": fmt(shown) if shown is not None else "",
                    "result": result,
                })
        # Sell-side fees (not Own Fees; kept only for the notes' alternative).
        sell_fees = sum((dec(r["size"]) * dec(r["price"]) - dec(r["usdc_size"])
                         for r in s_fills), Decimal(0))

        # FR-3 left-out reasons.
        reasons = []
        if bought > 0 and held == 0:
            reasons.append(R_SOLD)
        if cid in touched:
            reasons.append(R_CONVERT)
        if key not in listed:
            reasons.append(R_ACTIVITY_ONLY)
        if held < 0 or held > bought:
            reasons.append(R_HELD_RANGE)
        gap = None
        if key in listed:
            listed_bought = dec(listed[key]["shares_bought"])
            gap = abs(bought - listed_bought)
            denom = max(bought, listed_bought)
            if denom > 0 and gap / denom > SOURCE_GAP_SHARE:
                reasons.append(R_SOURCES)
        if state == "unclear":
            reasons.append(R_UNCLEAR)
        if key in listed:
            first = dec(listed[key].get("first_entry_at"))
            last = dec(listed[key].get("last_event_at"))
            if ((act_from is not None and first is not None and first < act_from)
                    or (act_until is not None and last is not None and last > act_until)):
                reasons.append(R_NOT_READ)
        if state == "open":
            reasons.append(R_OPEN)
        if state == "missing":
            reasons.append(R_NO_MARKET)
        reasons.sort(key=REASON_ORDER.index)

        outcome = outcome_of(m, tok) if state == "resolved" else None
        if reasons:
            status = "left_out"
        elif held < SLIVER_SHARE * bought and held < SLIVER_MAX_SHARES:
            status = "sliver"
        else:
            status = "resolved"

        gain = None
        contribution = None
        if status in ("resolved", "sliver"):
            # s * (o - p), with s * p computed as held * cost / bought (one division).
            gain = held * outcome - held * cost / bought
            contribution = gain - own_fees

        rows.append({
            "condition_id": cid, "token_id": tok, "buy_fills": len(b_fills),
            "bought": bought, "sold": sold, "held": held, "entry": entry,
            "cost": cost, "cash_cost": cash_cost,
            "state": state, "outcome": outcome, "status": status, "reasons": reasons,
            "own_fees": own_fees, "failed": failed, "sell_fees": sell_fees,
            "gain": gain, "contribution": contribution, "gap": gap,
            "listed_bought": dec(listed[key]["shares_bought"]) if key in listed else None,
            "listed_status": listed[key]["status"] if key in listed else "",
        })
    return rows, fee_rows, touched, unknown_types


def write_wallet(data, out_dir):
    rows, fee_rows, touched, unknown_types = analyse(data)
    short = data["address"][:8]

    counted = [r for r in rows if r["status"] in ("resolved", "sliver")]
    n_res = sum(1 for r in rows if r["status"] == "resolved")
    n_sl = sum(1 for r in rows if r["status"] == "sliver")
    n_out = sum(1 for r in rows if r["status"] == "left_out")
    total_fees = sum((r["own_fees"] for r in counted), Decimal(0))
    total_gain = sum((r["gain"] for r in counted), Decimal(0))
    real_pnl = total_gain - total_fees

    path = Path(out_dir) / f"{short}-real-pnl.csv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([
                r["condition_id"], r["token_id"], r["buy_fills"], fmt(r["bought"]),
                fmt(r["sold"]), fmt(r["held"]), fmt(r["entry"]),
                "true" if r["state"] == "resolved" else "false",
                fmt(r["outcome"]) if r["outcome"] is not None else "",
                r["status"], "; ".join(r["reasons"]), fmt(r["own_fees"]),
                fmt(r["contribution"]) if r["contribution"] is not None else "",
            ])
        w.writerow(["TOTAL", "", "", "", "", "", "", "", "", "",
                    f"resolved={n_res};sliver={n_sl};left_out={n_out}",
                    fmt(total_fees.quantize(CENT, rounding=ROUND_HALF_UP)),
                    fmt(real_pnl.quantize(CENT, rounding=ROUND_HALF_UP))])

    fee_path = Path(out_dir) / f"{short}-fee-check.csv"
    fee_rows.sort(key=lambda f: (f["condition_id"], f["token_id"],
                                 Decimal(f["timestamp"]), Decimal(f["size"])))
    with open(fee_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(FEE_COLUMNS)
        for f in fee_rows:
            w.writerow([f[c] for c in FEE_COLUMNS])

    # ----- summary and judgment-call alternatives (stdout only) -----
    def r2(x):
        return x.quantize(CENT, rounding=ROUND_HALF_UP)

    print(f"===== {data['address']} ({short})")
    print(f"Real PnL {r2(real_pnl)}  (full precision {fmt(real_pnl)})")
    print(f"  sum s*(o-p) {fmt(total_gain)}   Own Fees {fmt(total_fees)} (~{r2(total_fees)})")
    print(f"  resolved={n_res} sliver={n_sl} left_out={n_out} positions={len(rows)}")
    if unknown_types:
        print(f"  activity types not handled: {sorted(unknown_types)}")
    print(f"  markets touched by split/merge/conversion: {len(touched)}")
    by_primary, by_any = {}, {}
    for r in rows:
        if r["reasons"]:
            by_primary[r["reasons"][0]] = by_primary.get(r["reasons"][0], 0) + 1
            for x in r["reasons"]:
                by_any[x] = by_any.get(x, 0) + 1
    print("  left out by first reason:", {k: by_primary[k] for k in REASON_ORDER if k in by_primary})
    print("  left out, any reason:     ", {k: by_any[k] for k in REASON_ORDER if k in by_any})

    failed_counted = [x for r in counted for x in r["failed"]]
    failed_all = [x for r in rows for x in r["failed"]]
    print(f"  failed fees on counted Positions: {len(failed_counted)} totalling {fmt(sum(failed_counted, Decimal(0)))}")
    print(f"  failed fees on all Positions:     {len(failed_all)} totalling {fmt(sum(failed_all, Decimal(0)))}")

    alt = {}
    # A1: failed fees counted at their recorded value instead of 0.
    alt["A1 failed fees counted as recorded"] = real_pnl - sum(failed_counted, Decimal(0))
    # A2: Own Fees pro rata to shares held (instead of all buy fees).
    pro = Decimal(0)
    for r in counted:
        pro += r["gain"] - (r["own_fees"] * r["held"] / r["bought"])
    alt["A2 Own Fees pro rata to shares held"] = pro
    # A3: Entry Price from cash paid (usdc_size, fee included) instead of fill price.
    a3 = Decimal(0)
    for r in counted:
        a3 += r["held"] * r["outcome"] - r["held"] * r["cash_cost"] / r["bought"] - r["own_fees"]
    alt["A3 Entry Price from usdc_size/size"] = a3
    # A4: sell-side fees on counted Positions also subtracted.
    alt["A4 also subtract sell-side fees"] = real_pnl - sum((r["sell_fees"] for r in counted), Decimal(0))
    # A5: conversion rule applied to nothing (rows left out only for it would count).
    a5 = real_pnl
    a5_rows = 0
    for r in rows:
        if r["reasons"] == [R_CONVERT] and r["held"] > 0:
            a5 += r["held"] * r["outcome"] - r["held"] * r["cost"] / r["bought"] - r["own_fees"]
            a5_rows += 1
    alt[f"A5 conversion leaves nothing out ({a5_rows} rows join)"] = a5
    for name, value in alt.items():
        print(f"  {name}: {r2(value)} (moves total by {r2(value - real_pnl)})")

    # Borderline checks for thresholds (printed only when a choice could matter).
    max_rel_gap_kept = Decimal(0)
    for r in rows:
        if r["gap"] is not None and r["gap"] > 0:
            denoms = [d for d in (r["bought"], r["listed_bought"]) if d > 0]
            rels = [r["gap"] / d for d in denoms]
            if R_SOURCES not in r["reasons"]:
                max_rel_gap_kept = max([max_rel_gap_kept] + rels)
            if any(x > Decimal("0.001") for x in rels):
                print(f"  gap {r['condition_id'][:12]} act={fmt(r['bought'])} listed={fmt(r['listed_bought'])} "
                      f"gap={fmt(r['gap'])} rel={[round(x, 6) for x in rels]} status={r['status']} reasons={r['reasons']}")
    print(f"  largest relative gap among Positions not left out for it: {max_rel_gap_kept:.8f}")
    only_share = only_one = 0
    for r in rows:
        if r["held"] > 0 and r["bought"] > 0 and not r["reasons"]:
            small_share = r["held"] < SLIVER_SHARE * r["bought"]
            small_count = r["held"] < SLIVER_MAX_SHARES
            if small_share and not small_count:
                only_share += 1
                print(f"  under 1% but >=1 share: {r['condition_id'][:12]} held={fmt(r['held'])} bought={fmt(r['bought'])}")
            if small_count and not small_share:
                only_one += 1
                print(f"  under 1 share but >=1%: {r['condition_id'][:12]} held={fmt(r['held'])} bought={fmt(r['bought'])} "
                      f"gain={r2(r['gain'])}")
    print(f"  sliver 'and' vs 'or': {only_share} under 1% only, {only_one} under 1 share only")
    slivers = [r for r in rows if r["status"] == "sliver"]
    if slivers:
        print(f"  slivers: max held {fmt(max(r['held'] for r in slivers))}, max share "
              f"{max(r['held'] / r['bought'] for r in slivers):.8f}, money {fmt(sum((r['contribution'] for r in slivers), Decimal(0)))}")
    return short, real_pnl, n_res, n_sl, n_out, total_fees


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    out_dir = Path(argv[-1])
    out_dir.mkdir(parents=True, exist_ok=True)
    for wallet_path in argv[1:-1]:
        write_wallet(load(wallet_path), out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
