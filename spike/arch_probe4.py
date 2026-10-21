"""Architecture probe 4 (2026-10-21): is the Market-anchored /v2/positions list a complete candidate list?

Probe 3: status=CLOSED by Market works (1000 rows, 995 wallets, 874 losers on a $71M Market),
REDEEMABLE_LOST needs a user. The v2 docs say status OPEN (the default) is the superset that
includes settled-but-unredeemed positions. Checks:
  G1. OPEN by Market on the same resolved $71M Market: does it list holders of the LOSING outcome
      (current_price 0), i.e. the unredeemed losers that CLOSED misses?
  G2. Does CLOSED by Market reach an older Market (resolved Aug to Oct 2023), where /v2/trades
      returned nothing for a 2022 Market?
"""
import json
from api import get, DATA, GAMMA, RAW

mid = max((m for m in json.loads((RAW / "q2_gamma_june.json").read_text()) if m.get("closedTime")), key=lambda m: -abs(m["volumeNum"] - 5e6))

s, d, _ = get(DATA, "/v2/positions", {"condition": mid["conditionId"], "limit": 1000})
rows = d.get("data") or [] if s == 200 else []
print(f"G1 {mid['question'][:40]} OPEN by Market: status {s}, {len(rows)} rows, {len({r['proxy_wallet'] for r in rows})} wallets, "
      f"current_price 0: {sum((r.get('current_price') or 0) == 0 for r in rows)}, current_price 1: {sum((r.get('current_price') or 0) == 1 for r in rows)}, "
      f"has_more {(d.get('pagination') or {}).get('has_more') if s == 200 else d}")

# The Gamma market search returned 403 (CloudFront "Bad request") on the run of 2026-10-21, so the 2023 Market
# is taken from rows the spike already saved (closed positions, timestamp = resolution time in v1).
import datetime as dt
pool = [r for rows_ in json.loads((RAW / "q3_copy_pool_rows.json").read_text()).values() for r in rows_]
old = [r for r in pool if 1690848000 <= r["timestamp"] < 1696118400]          # 2023-08-01 .. 2023-10-01
r0 = max(old, key=lambda r: r["totalBought"])
m = {"conditionId": r0["conditionId"], "question": r0["title"], "volumeNum": 0,
     "closedTime": dt.datetime.fromtimestamp(r0["timestamp"], dt.timezone.utc).isoformat()}
s, d, _ = get(DATA, "/v2/positions", {"condition": m["conditionId"], "status": "CLOSED", "limit": 1000})
rows = d.get("data") or [] if s == 200 else []
print(f"G2 {m['question'][:40]} (closed {m.get('closedTime', '')[:10]}, vol {m['volumeNum']:,.0f}) CLOSED by Market: status {s}, "
      f"{len(rows)} rows, {len({r['proxy_wallet'] for r in rows})} wallets, losers {sum((r.get('realized_pnl') or 0) < 0 for r in rows)}, "
      f"has_more {(d.get('pagination') or {}).get('has_more') if s == 200 else d}")
