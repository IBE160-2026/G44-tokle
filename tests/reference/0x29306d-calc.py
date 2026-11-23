"""Independent Real PnL calculation for one Wallet, from the PRD (Glossary, FR-3, FR-4) only.

Standard library only. Usage:
    python -I calc.py <wallet.json> <out_dir>

All arithmetic is exact Decimal (JSON floats are parsed straight to Decimal, never
through binary float). Only the final total is rounded, to the cent, ROUND_HALF_UP.
"""

import csv
import json
import sys
from collections import OrderedDict
from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 50

ZERO = Decimal("0")
ONE = Decimal("1")
SLIVER_SHARE = Decimal("0.01")   # Glossary Sliver: < 1% of bought shares ...
SLIVER_ABS = Decimal("1")        # ... and fewer than 1 share
SOURCE_GAP_MAX = Decimal("0.01")  # FR-3: sources disagree on shares bought by > 1%
# Rounding noise: usdc_size has 6 decimals, so a cash-minus-shares*price residual
# smaller than one micro-USDC is not a fee, just rounding in the recorded price.
ROUNDING_TOL = Decimal("0.000001")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f, parse_float=Decimal, parse_int=Decimal)


def market_resolution(m):
    """FR-3: resolved iff closed, outcome prices exactly 0 and 1, and a resolution time."""
    prices = m["outcome_prices"]
    resolved = (
        m["closed"] is True
        and m["closed_time"] is not None
        and len(prices) >= 2
        and all(p in (ZERO, ONE) for p in prices)
        and sum(prices) == ONE
    )
    return resolved


def schedule_fee(m, shares, price):
    """Taker fee per the Market's fee schedule, same form as the PRD's Follower Fee:
    s * rate * (p * (1 - p)) ** exponent  (exponent 1 gives s * rate * p * (1 - p))."""
    if not m["fees_enabled"] or m["fee_rate"] is None:
        return ZERO
    exp = m["fee_exponent"] if m["fee_exponent"] is not None else ONE
    base = price * (ONE - price)
    if exp == exp.to_integral_value():
        factor = base ** int(exp)
    else:
        factor = base ** exp
    return shares * m["fee_rate"] * factor


def main(wallet_path, out_dir):
    d = load(wallet_path)
    markets = {m["condition_id"]: m for m in d["markets"]}
    plist = {(p["condition_id"], p["token_id"]): p for p in d["positions"]}

    # Positions = (condition_id, token_id) pairs from activity trades and from the positions list.
    pos = OrderedDict()

    def get(cid, tok):
        key = (cid, tok)
        if key not in pos:
            pos[key] = {"buys": [], "sells": [], "first_ts": None}
        return pos[key]

    for r in sorted(d["activity"], key=lambda r: r["timestamp"]):
        if r["type"] != "TRADE":
            continue  # FR-3: redemptions never count shares
        p = get(r["condition_id"], r["token_id"])
        if p["first_ts"] is None:
            p["first_ts"] = r["timestamp"]
        (p["buys"] if r["side"] == "BUY" else p["sells"]).append(r)
    for key, pl in plist.items():
        p = get(*key)
        if p["first_ts"] is None:
            p["first_ts"] = pl["first_entry_at"]

    rows = []
    fee_log = []
    total = ZERO
    counts = {"resolved": 0, "sliver": 0, "left_out": 0}

    for (cid, tok), p in sorted(pos.items(), key=lambda kv: kv[1]["first_ts"]):
        m = markets.get(cid)
        bought = sum((b["size"] for b in p["buys"]), ZERO)
        sold = sum((s["size"] for s in p["sells"]), ZERO)
        held = bought - sold
        entry = (sum((b["size"] * b["price"] for b in p["buys"]), ZERO) / bought) if bought > 0 else None

        resolved = m is not None and market_resolution(m)
        outcome = None
        if resolved:
            idx = m["token_ids"].index(tok) if tok in m["token_ids"] else None
            outcome = m["outcome_prices"][idx] if idx is not None else None

        # Own Fees per buy fill: cash paid - shares * price, checked against the schedule.
        own_fees = ZERO
        for b in p["buys"]:
            recorded = b["usdc_size"] - b["size"] * b["price"]
            sched = schedule_fee(m, b["size"], b["price"]) if m else ZERO
            if m is not None and m["fees_enabled"]:
                is_zero = abs(recorded) <= ROUNDING_TOL
                matches = abs(recorded - sched) <= ROUNDING_TOL
                if is_zero:
                    verdict, counted = "pass (0: maker fill or no fee recorded)", ZERO
                elif matches:
                    verdict, counted = "pass (equals schedule taker fee)", recorded
                else:
                    verdict, counted = "FAIL (counted as 0)", ZERO
            else:
                # Glossary: Own Fees are 0 in Markets that charge no fee.
                if abs(recorded) <= ROUNDING_TOL:
                    verdict = "no-fee Market; residual is rounding noise"
                else:
                    verdict = "no-fee Market; nonzero residual = FAILED fee (counted as 0)"
                counted = ZERO
            own_fees += counted
            fee_log.append({
                "condition_id": cid, "token_id": tok, "ts": b["timestamp"],
                "size": b["size"], "price": b["price"], "usdc": b["usdc_size"],
                "recorded": recorded, "schedule": sched,
                "fees_enabled": m["fees_enabled"] if m else None,
                "verdict": verdict, "counted": counted,
            })

        # Classification (FR-3 order of checks; first applicable reason is primary).
        reasons = []
        pl = plist.get((cid, tok))
        gap_note = ""
        if pl is not None:
            ref = pl["shares_bought"]
            gap = abs(bought - ref) / ref if ref != 0 else (ZERO if bought == 0 else ONE)
            gap_note = f"positions shares_bought={ref}, activity={bought}, gap={gap:.6%}"
        else:
            gap = None
        if pl is None and p["buys"]:
            reasons.append("token only in activity rows")
        if bought > 0 and held == 0 and not reasons:
            reasons.append("fully sold")
        if bought > 0 and not (ZERO <= held <= bought):
            reasons.append("shares held out of range")
        if gap is not None and gap > SOURCE_GAP_MAX:
            reasons.append("source gap above 1%")
        if not resolved:
            reasons.append("unclear resolution")
        if resolved and outcome is None:
            reasons.append("token not in Market data")

        status = "left_out"
        contrib = None
        if not reasons:
            is_sliver = held < bought * SLIVER_SHARE and held < SLIVER_ABS
            status = "sliver" if is_sliver else "resolved"
            contrib = held * (outcome - entry) - own_fees
            total += contrib
        counts[status] += 1

        rows.append({
            "condition_id": cid,
            "token_id": tok,
            "buy_fills": len(p["buys"]),
            "shares_bought": bought,
            "shares_sold": sold,
            "shares_held": held,
            "entry_price": "" if entry is None else entry,
            "market_resolved": "true" if resolved else "false",
            "outcome": "" if outcome is None else int(outcome),
            "status": status,
            "reason": "; ".join(reasons),
            "own_fees": own_fees if p["buys"] else "",
            "pnl_contribution": "" if contrib is None else contrib,
            "_gap": gap_note,
        })

    total_cents = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    cols = ["condition_id", "token_id", "buy_fills", "shares_bought", "shares_sold",
            "shares_held", "entry_price", "market_resolved", "outcome", "status",
            "reason", "own_fees", "pnl_contribution"]
    addr6 = d["address"][:8]
    out_csv = f"{out_dir}/{addr6}-real-pnl.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (str(v) if isinstance(v, Decimal) else v) for k, v in r.items()})
        w.writerow({
            "condition_id": "TOTAL", "token_id": "", "buy_fills": "", "shares_bought": "",
            "shares_sold": "", "shares_held": "", "entry_price": "", "market_resolved": "",
            "outcome": "", "status": "",
            "reason": f"resolved={counts['resolved']};sliver={counts['sliver']};left_out={counts['left_out']}",
            "own_fees": str(sum((r["own_fees"] for r in rows if r["status"] != "left_out" and r["own_fees"] != ""), ZERO)),
            "pnl_contribution": str(total_cents),
        })

    # Console report for the notes.
    print(f"Wallet {d['address']}  activity rows={len(d['activity'])}  positions={len(d['positions'])}  markets={len(d['markets'])}")
    print(f"Real PnL exact = {total}")
    print(f"Real PnL (cents, ROUND_HALF_UP) = {total_cents}")
    print(f"counts = {counts}")
    print()
    for r in rows:
        print(f"{r['condition_id'][:10]} {r['status']:8} fills={r['buy_fills']} bought={r['shares_bought']} "
              f"sold={r['shares_sold']} held={r['shares_held']} p={r['entry_price']} o={r['outcome']} "
              f"fees={r['own_fees']} contrib={r['pnl_contribution']} reason='{r['reason']}' | {r['_gap']}")
    print()
    print("Timing check (trades at/after the Market's resolution time):")
    late = [r for r in d["activity"] if r["type"] == "TRADE"
            and markets.get(r["condition_id"]) is not None
            and markets[r["condition_id"]]["closed_time"] is not None
            and r["timestamp"] >= markets[r["condition_id"]]["closed_time"]]
    print(f"  {len(late)} late trades" + ("" if not late else ": " + ", ".join(
        f"{r['condition_id'][:10]} {r['side']} ts={r['timestamp']}" for r in late)))
    last_act = max(r["timestamp"] for r in d["activity"])
    after = [p for p in d["positions"] if p["last_event_at"] > last_act]
    print(f"  last activity row ts={last_act}; positions with last_event_at after it: "
          + ", ".join(f"{p['condition_id'][:10]}({p['last_event_at']})" for p in after))
    print()
    print("Fee check per buy fill:")
    for fl in fee_log:
        print(f"{fl['condition_id'][:10]} ts={fl['ts']} fees_enabled={fl['fees_enabled']} size={fl['size']} "
              f"price={fl['price']} usdc={fl['usdc']} recorded={fl['recorded']} schedule={fl['schedule']} "
              f"-> {fl['verdict']}; counted={fl['counted']}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
