"""Architecture probe 8 (2026-10-21): do v2 activity rows give the same fee as the v1 trade rows?

AD-12 reads Own Fees from v2 activity rows (cash paid - shares x price). The method was proven
on v1 trade rows only, and v1 retires on 2026-10-24. The typical wallet's v1 trade rows were
saved today (spike/raw/q1_typical_trades.json); here its v2 TRADE rows since 2026-06-01 (the
first fee row in the sample is 2026-06-09) are fetched and matched row by row on
(transaction hash, token, side, size). Identical-looking rows are separate fills, so matching
is by count per key, never de-duplicated.
"""
import json
from collections import Counter, defaultdict
from api import get, DATA, RAW

W = json.loads((RAW / "q1_wallets.json").read_text())["typical"]
START = 1780272000  # 2026-06-01 00:00 UTC

v2, params = [], {"user": W, "type": "TRADE", "start": START, "limit": 1000, "sort_direction": "ASC"}
while True:
    s, d, _ = get(DATA, "/v2/activity", params)
    assert s == 200, (s, str(d)[:300])
    v2 += d["data"]
    cur = (d.get("pagination") or {}).get("next_cursor")
    if not cur:
        break
    params = {"user": W, "type": "TRADE", "start": START, "sort_direction": "ASC", "cursor": cur}
v1 = [r for r in json.loads((RAW / "q1_typical_trades.json").read_text()) if r["timestamp"] >= START]

fee = lambda cash, size, price, side: (cash - size * price) if side == "BUY" else (size * price - cash)
k1 = defaultdict(list)
for r in v1:
    k1[(r["transactionHash"], r["asset"], r["side"], round(r["size"], 6))].append(fee(r["usdcSize"], r["size"], r["price"], r["side"]))
k2 = defaultdict(list)
for r in v2:
    k2[(r["transaction_hash"], r["token_id"], r["side"], round(r["size"], 6))].append(fee(r["usdc_size"], r["size"], r["price"], r["side"]))

both = set(k1) & set(k2)
fee_keys = [k for k in both if any(abs(f) > 0.0001 for f in k1[k] + k2[k])]
diffs = [abs(sorted(k1[k])[i] - sorted(k2[k])[i]) for k in fee_keys for i in range(min(len(k1[k]), len(k2[k])))]
print(f"v1 rows since 2026-06-01: {len(v1)} | v2 rows: {len(v2)} | keys in both: {len(both)} | only v1: {len(set(k1) - set(k2))} | only v2: {len(set(k2) - set(k1))}")
print(f"row counts per key equal: {sum(len(k1[k]) == len(k2[k]) for k in both)} of {len(both)}")
print(f"fee-bearing keys: {len(fee_keys)} | fee rows compared: {len(diffs)} | max |v1 fee - v2 fee|: {max(diffs) if diffs else '-'} "
      f"| within 0.0001: {sum(x <= 0.0001 for x in diffs)}")
print(f"total fees v1 {sum(f for k in fee_keys for f in k1[k]):.4f} | v2 {sum(f for k in fee_keys for f in k2[k]):.4f}")
