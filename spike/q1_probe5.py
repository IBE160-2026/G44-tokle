"""Q1 probe 5: on wallets that do hold tokens, are price-0 (lost, unredeemed) positions in /positions only, or also in /closed-positions?"""
import json, collections
from api import get, DATA, RAW

pool = json.loads((RAW / "q2_candidates_spread.json").read_text())
W = json.loads((RAW / "q1_wallets.json").read_text())
W["rank339"] = next(w for w in pool if w.startswith("0xa2f1fecf"))
(RAW / "q1_wallets.json").write_text(json.dumps(W))

for name in ("lb2", "rank339"):
    w = W[name]
    s, red, _ = get(DATA, "/positions", {"user": w, "redeemable": "true", "sizeThreshold": 0, "limit": 100})
    s2, allp, _ = get(DATA, "/positions", {"user": w, "sizeThreshold": 0, "limit": 100})
    zero = [p for p in red if p["curPrice"] == 0]
    print(f"== {name} {w[:10]}: redeemable rows {len(red)} (price 0: {len(zero)}), first 100 of all positions {len(allp)} (price 0: {sum(p['curPrice'] == 0 for p in allp)}, redeemable: {sum(bool(p['redeemable']) for p in allp)})", flush=True)
    for p in zero[:6]:
        s, c, _ = get(DATA, "/closed-positions", {"user": w, "market": p["conditionId"], "limit": 50})
        same = [x for x in c if x["asset"] == p["asset"]]
        print(f"   price-0 position size {p['size']:.1f} cashPnl {p['cashPnl']:.2f} realizedPnl {p['realizedPnl']:.2f} | closed rows for that market: {len(c)}, same token: {len(same)}")
    (RAW / f"q1_{name}_positions_redeemable.json").write_text(json.dumps(red))
