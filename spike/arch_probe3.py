"""Architecture probe 3 (2026-10-21): the fallback for the Scan's candidate list, and checks B to D.

Probe 2 showed /v2/trades ignores end= for a Market (same rows as a made-up parameter), so a
Market's trades cannot be walked back by time; only cursor paging goes back, about 9 hours per
1000 rows on a big Market. Its fallback call, /v2/positions anchored on the Market with
status=CLOSED and limit=1000, timed out (503, retryable) on the $400M inauguration Market.
  F. Fallback: list a Market's wallets through /v2/positions?condition=… (smaller pages, a
     mid-size Market too). Does it list wallets that traded, including losers?
  A6. Does start=1 reach a 2022 Market's trades?
  B, C, D as in probe 2.
"""
import json
from collections import defaultdict
from api import get, DATA, CLOB, RAW

wallets = json.loads((RAW / "q1_wallets.json").read_text())
big = next(m for m in json.loads((RAW / "q2_gamma_markets2.json").read_text()) if m["question"].startswith("Will Donald Trump be inaugurated"))
mid = max((m for m in json.loads((RAW / "q2_gamma_june.json").read_text()) if m.get("closedTime")), key=lambda m: -abs(m["volumeNum"] - 5e6))
old = max((m for m in json.loads((RAW / "q2_gamma_markets.json").read_text()) if m.get("closedTime")), key=lambda m: m["volumeNum"])


def call(path, params):
    s, d, _ = get(DATA, path, params)
    if s != 200:
        return None, {"status": s, "error": str(d)[:160]}
    return d.get("data") or [], d.get("pagination") or {}


# ---- F. fallback: a Market's wallets from /v2/positions ----------------------------------
for name, m, lim in (("big", big, 100), ("mid", mid, 1000)):
    for st in ("CLOSED", "REDEEMABLE_LOST"):
        rows, pg = call("/v2/positions", {"condition": m["conditionId"], "status": st, "limit": lim})
        if rows is None:
            print(f"F {name} {st} limit {lim}: failed {pg}")
            continue
        pnl = [r.get("realized_pnl") or 0 for r in rows]
        print(f"F {name} ({m['question'][:40]}, vol {m['volumeNum']:,.0f}, closed {m['closedTime'][:10]}) {st} limit {lim}: "
              f"{len(rows)} rows, {len({r['proxy_wallet'] for r in rows})} wallets, has_more {pg.get('has_more')}, "
              f"losers {sum(p < 0 for p in pnl)}, first_entry_at range "
              f"{min((r.get('first_entry_at') or 0) for r in rows) if rows else '-'}..{max((r.get('first_entry_at') or 0) for r in rows) if rows else '-'}")

# ---- A6. 2022 Market with start=1 ---------------------------------------------------------
rows, pg = call("/v2/trades", {"condition": old["conditionId"], "limit": 10, "start": 1})
print(f"\nA6 2022 Market ({old['closedTime'][:10]}) trades with start=1: {pg if rows is None else str(len(rows)) + ' rows'}")

# ---- B. page sizes ------------------------------------------------------------------------
b1, pb1 = call("/v2/positions", {"user": wallets["rank339"], "status": "CLOSED", "limit": 1000})
b2, pb2 = call("/v2/positions", {"user": wallets["rank339"], "status": "CLOSED", "cursor": pb1["next_cursor"]}) \
    if b1 is not None and pb1.get("next_cursor") else ([], {})
print(f"\nB rank-339 CLOSED: page 1 {len(b1) if b1 is not None else pb1}, page 2 {len(b2) if b2 is not None else pb2}, "
      f"has_more {pb2.get('has_more')}")

# ---- C. CLOB price history unchanged? -----------------------------------------------------
q3 = json.loads((RAW.parent / "samples" / "q3_prices_history.json").read_text())
tok, t0 = q3["request"]["market"], q3["trade_timestamp"]
s, d, _ = get(CLOB, "/prices-history", {"market": tok, "startTs": t0 - 7 * 86400, "endTs": t0 + 7 * 86400, "fidelity": 1})
hist = d.get("history", []) if isinstance(d, dict) else []
saved = {(h["t"], h["p"]) for h in q3["history_first_8"]}
print(f"\nC CLOB prices-history 14 days, fidelity 1: status {s}, {len(hist)} points (spike: 20,154) | "
      f"spike's saved points still identical: {saved <= {(h['t'], h['p']) for h in hist}}")

# ---- D. entry_fees_usdc vs v1 trade rows --------------------------------------------------
pos, _ = call("/v2/positions", {"user": wallets["typical"], "status": "CLOSED", "limit": 1000})
tr = json.loads((RAW / "q1_typical_trades.json").read_text())
fee_rows = defaultdict(float)
for r in tr:
    if r["side"] == "BUY":
        fee_rows[r["asset"]] += r["usdcSize"] - r["size"] * r["price"]
paid = [p for p in pos or [] if (p.get("entry_fees_usdc") or 0) > 0]
print(f"\nD typical wallet: {len(pos or [])} CLOSED rows in one page; {len(paid)} with entry_fees_usdc > 0")
for p in paid[:10]:
    print(f"  entry_fees_usdc {p['entry_fees_usdc']:.4f} | fees in v1 BUY rows {fee_rows.get(p['token_id'], 0):.4f}")
