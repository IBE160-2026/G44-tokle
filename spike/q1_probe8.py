"""Q1 probe 8: explain the totalBought gaps on the typical wallet with the other activity types (SPLIT, MERGE, CONVERSION, REDEEM)."""
import json, collections
from api import get, DATA, RAW
w = json.loads((RAW / "q1_wallets.json").read_text())["typical"]
tr = json.loads((RAW / "q1_typical_trades.json").read_text())
cl = json.loads((RAW / "q1_typical_closed.json").read_text())
end = min(r["timestamp"] for r in tr[5000:5500])
tr = [r for r in tr[:5500] if r["timestamp"] > end] + tr[5500:]
buy = collections.defaultdict(float)
for r in tr:
    if r["side"] == "BUY": buy[r["asset"]] += r["size"]
gaps = [p for p in cl if p["asset"] in buy and abs(buy[p["asset"]] - p["totalBought"]) >= 0.01]
nobuy = [p for p in cl if p["asset"] not in buy]
print("rows with a gap:", len(gaps), "| rows with no BUY rows:", len(nobuy))
for p in gaps + nobuy[:2]:
    s, a, _ = get(DATA, "/activity", {"user": w, "market": p["conditionId"], "start": 1, "limit": 500})
    by = collections.defaultdict(float)
    for r in a:
        if r["asset"] == p["asset"] or r["type"] in ("SPLIT", "MERGE", "CONVERSION"):
            by[(r["type"], r["side"] or "-", r["outcome"] if r["type"] == "TRADE" or r["type"] == "REDEEM" else "(market)")] += r["size"]
    print(f"\n{p['title'][:55]} / {p['outcome']} | totalBought {p['totalBought']:.2f} | BUY rows {buy.get(p['asset'], 0):.2f} | gap {p['totalBought'] - buy.get(p['asset'], 0):+.2f}")
    print("  activity types in this market:", dict(collections.Counter(r['type'] for r in a)))
    for k, v in sorted(by.items()): print("   ", k, round(v, 2))
