"""Q1: where does a fee show up in a wallet's data? Uses the saved 'typical' wallet files from q1_probe2.py.
1. trade rows: is usdcSize = size*price +/- fee?   2. does /closed-positions realizedPnl include fees?"""
import json
import datetime as dt
from api import RAW

tr = json.loads((RAW / "q1_typical_trades.json").read_text())
cl = {p["asset"]: p for p in json.loads((RAW / "q1_typical_closed.json").read_text())}
end = min(r["timestamp"] for r in tr[5000:5500])
tr = [r for r in tr[:5500] if r["timestamp"] > end] + tr[5500:]       # drop the boundary second from window 1
off = [r for r in tr if abs(r["usdcSize"] - r["size"] * r["price"]) > 0.001]
print("trade rows where usdcSize != size*price:", len(off), "of", len(tr), "| first:", dt.datetime.fromtimestamp(min(r["timestamp"] for r in off), dt.timezone.utc))
for side in ("BUY", "SELL"):
    r = max((r for r in off if r["side"] == side), key=lambda r: abs(r["usdcSize"] - r["size"] * r["price"]))
    p = r["price"]
    print(f"  {side} size {r['size']} price {p} usdcSize {r['usdcSize']} diff {r['usdcSize'] - r['size'] * p:+.4f} | size*p*(1-p) = {r['size'] * p * (1 - p):.4f} (diff / that = {abs(r['usdcSize'] - r['size'] * p) / (r['size'] * p * (1 - p)):.3f})")
print("\nrealizedPnl vs PnL rebuilt from trade rows (with fee in usdcSize / without):")
for a in {r["asset"] for r in off}:
    p = cl.get(a)
    if not p: continue
    rows = [r for r in tr if r["asset"] == a]
    b = [r for r in rows if r["side"] == "BUY"]; s = [r for r in rows if r["side"] == "SELL"]
    payout = (sum(r["size"] for r in b) - sum(r["size"] for r in s)) * p["curPrice"]
    withfee = sum(r["usdcSize"] for r in s) + payout - sum(r["usdcSize"] for r in b)
    nofee = sum(r["size"] * r["price"] for r in s) + payout - sum(r["size"] * r["price"] for r in b)
    print(f"  {p['title'][:40]:40} realizedPnl {p['realizedPnl']:10.2f} | with fee {withfee:10.2f} | without {nofee:10.2f}")
