"""Architecture cost check (2026-10-21, offline, 0 requests): what does 'one price window per fill' cost?

Edvard's decision 4: every fill is copied at its own time + Copy Delay. Uses the typical wallet's
saved trade rows (spike/raw/q1_typical_trades.json). Per outcome token, the BUY fills' windows
[t - 2 min, t + 32 min] are merged when they overlap; requests are counted two ways:
  A. one request per merged window (naive);
  B. merged windows packed greedily into 14-day requests (one request covers up to 14 days of
     1-minute points, spike Q3), storing only the points inside the short windows.
Compared with the spike's per-outcome estimate (1.06 requests per outcome).
"""
import json
from collections import defaultdict
from api import RAW

tr = json.loads((RAW / "q1_typical_trades.json").read_text())
end = min(r["timestamp"] for r in tr[5000:5500])
tr = [r for r in tr[:5500] if r["timestamp"] > end] + tr[5500:]   # boundary second taken once (spike q1)
buys = defaultdict(list)
for r in tr:
    if r["type"] == "TRADE" and r["side"] == "BUY":
        buys[r["asset"]].append(r["timestamp"])
fills, merged, packed, points = 0, 0, 0, 0
for t in buys.values():
    t.sort(); fills += len(t)
    wins = []
    for x in t:
        a, b = x - 120, x + 32 * 60
        if wins and a <= wins[-1][1]:
            wins[-1][1] = max(wins[-1][1], b)
        else:
            wins.append([a, b])
    merged += len(wins)
    points += sum((b - a) // 60 + 1 for a, b in wins)
    start = None
    for a, b in wins:
        if start is None or b - start > 14 * 86400:
            packed += 1; start = a
print(f"outcome tokens bought: {len(buys)} | buy fills: {fills} ({fills / len(buys):.1f} per token)")
print(f"A. merged short windows: {merged} ({merged / len(buys):.2f} requests per token)")
print(f"B. packed into 14-day requests: {packed} ({packed / len(buys):.2f} requests per token; spike per-outcome estimate 1.06)")
print(f"minute points stored for the short windows: {points:,} (~{points * 16 / 1e6:.1f} MB at ~16 bytes per point as JSON)")
