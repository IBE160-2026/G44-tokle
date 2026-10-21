"""Architecture probe 2 (2026-10-21): re-check the spike's load-bearing findings on Data API v2.

v1 retires on 2026-10-24. Order of checks (Edvard's call):
  A. Can a Market's trades still be walked back in time? (the Scan's candidate method, PRD Q2)
     The docs say /v2/trades honours start/end on the user shape only. Prove it either way,
     with a made-up parameter as control. If it fails, try the fallback: /v2/positions anchored
     on the Market (no user), which would list the Market's wallets directly.
  B. Page sizes: is 1000 per page real, also on the second (cursor) page?
  C. Is the CLOB price history unchanged (one-minute points, 14-day window)?
  D. Does v2's entry_fees_usdc match the fees seen in the v1 trade rows (taker fee rule)?
"""
import json
from collections import defaultdict
from api import get, DATA, CLOB, RAW

wallets = json.loads((RAW / "q1_wallets.json").read_text())
# First run picked the biggest Market in q2_gamma_markets.json, which closed in 2022: /v2/trades returned 0 rows
# (the docs say an omitted start floors to three years back). Now: a large Market from 2025, plus one check of the 2022 one.
old = max((m for m in json.loads((RAW / "q2_gamma_markets.json").read_text()) if m.get("closedTime")), key=lambda m: m["volumeNum"])
mk = next(m for m in json.loads((RAW / "q2_gamma_markets2.json").read_text()) if m["question"].startswith("Will Donald Trump be inaugurated"))
COND = mk["conditionId"]
print(f"Market: {mk['question'][:60]} | volume {mk['volumeNum']:,.0f} | closed {mk['closedTime']}")


def call(path, params):
    s, d, _ = get(DATA, path, params)
    assert s == 200, (path, params, s, str(d)[:300])
    return d.get("data") or [], d.get("pagination") or {}


# ---- A. walk back a Market's trades -------------------------------------------------------
t1, p1 = call("/v2/trades", {"condition": COND, "limit": 1000})
tkey = next(k for k in ("block_timestamp", "timestamp", "created_at") if k in t1[0])
ids = lambda rows: [(r.get("transaction_hash"), r.get("token_id"), r.get(tkey), r.get("size")) for r in rows]
print(f"\nA1 unfiltered: {len(t1)} rows, time key '{tkey}', newest {t1[0][tkey]}, oldest {t1[-1][tkey]}, "
      f"has_more {p1.get('has_more')} | row keys {sorted(t1[0].keys())}")
t2, _ = call("/v2/trades", {"condition": COND, "limit": 1000, "before_xyz": 1})
print("A2 control (unknown param) identical:", ids(t2) == ids(t1))
bound = int(t1[-1][tkey]) - 7 * 86400
t3, _ = call("/v2/trades", {"condition": COND, "limit": 1000, "end": bound})
walkback = bool(t3) and ids(t3) != ids(t1) and all(int(r[tkey]) <= bound for r in t3)
print(f"A3 end=oldest-7d: {len(t3)} rows, differs {ids(t3) != ids(t1)}, all <= bound "
      f"{all(int(r[tkey]) <= bound for r in t3) if t3 else 'n/a'} -> walkback by time works: {walkback}")
t4, p4 = call("/v2/trades", {"condition": COND, "limit": 1000, "cursor": p1["next_cursor"]})
print(f"A4 cursor page 2: {len(t4)} rows, newest {t4[0][tkey] if t4 else '-'}, oldest {t4[-1][tkey] if t4 else '-'}, "
      f"continues older: {bool(t4) and int(t4[0][tkey]) <= int(t1[-1][tkey])}, has_more {p4.get('has_more')}")

if not walkback:
    for st in ("CLOSED", "REDEEMABLE_LOST"):
        f, pf = call("/v2/positions", {"condition": COND, "status": st, "limit": 1000})
        print(f"A5 fallback /v2/positions?condition=…&status={st}: {len(f)} rows, "
              f"{len({r['proxy_wallet'] for r in f})} distinct wallets, has_more {pf.get('has_more')}, "
              f"oldest first_entry_at {min((r.get('first_entry_at') or 0) for r in f) if f else '-'}")

s0, d0, _ = get(DATA, "/v2/trades", {"condition": old["conditionId"], "limit": 10, "start": 1})
print(f"A6 2022 Market ({old['closedTime'][:10]}) with start=1: status {s0}, rows {len((d0 or {}).get('data') or []) if isinstance(d0, dict) else d0}")

# ---- B. page sizes ------------------------------------------------------------------------
b1, pb1 = call("/v2/positions", {"user": wallets["rank339"], "status": "CLOSED", "limit": 1000})
b2, pb2 = call("/v2/positions", {"user": wallets["rank339"], "status": "CLOSED", "cursor": pb1["next_cursor"]}) \
    if pb1.get("next_cursor") else ([], {})
print(f"\nB rank-339 CLOSED: page 1 {len(b1)} rows, page 2 {len(b2)} rows, has_more {pb2.get('has_more')}")

# ---- C. CLOB price history unchanged? -----------------------------------------------------
q3 = json.loads((RAW.parent / "samples" / "q3_prices_history.json").read_text())
tok, t0 = q3["request"]["market"], q3["trade_timestamp"]
s, d, _ = get(CLOB, "/prices-history", {"market": tok, "startTs": t0 - 7 * 86400, "endTs": t0 + 7 * 86400, "fidelity": 1})
hist = d.get("history", []) if isinstance(d, dict) else []
saved = {(h["t"], h["p"]) for h in q3["history_first_8"]}
print(f"\nC CLOB prices-history 14 days, fidelity 1: status {s}, {len(hist)} points "
      f"(spike: 20,154 for 14 days) | saved spike points still identical: {saved <= {(h['t'], h['p']) for h in hist}}")

# ---- D. entry_fees_usdc vs v1 trade rows --------------------------------------------------
pos, _ = call("/v2/positions", {"user": wallets["typical"], "status": "CLOSED", "limit": 1000})
tr = json.loads((RAW / "q1_typical_trades.json").read_text())
fee_rows = defaultdict(float)
for r in tr:
    if r["side"] == "BUY":
        fee_rows[r["asset"]] += r["usdcSize"] - r["size"] * r["price"]
paid = [p for p in pos if (p.get("entry_fees_usdc") or 0) > 0]
print(f"\nD typical wallet: {len(pos)} CLOSED rows in one page; {len(paid)} with entry_fees_usdc > 0")
for p in paid[:10]:
    print(f"  entry_fees_usdc {p['entry_fees_usdc']:.4f} | fees in v1 BUY rows {fee_rows.get(p['token_id'], 0):.4f}")
