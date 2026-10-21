"""Q1 probe 6: how big is the lost-position gap on the rank-339 wallet, what dates do /positions rows carry,
and can Gamma return many markets per request?"""
import json, collections
from api import get, DATA, GAMMA, RAW

w = json.loads((RAW / "q1_wallets.json").read_text())["rank339"]
def pages(path, extra, size, cap):
    rows, off = [], 0
    for _ in range(cap):
        s, d, _ = get(DATA, path, {"user": w, "limit": size, "offset": off, **extra})
        if s != 200 or not d: return rows, False
        rows += d; off += size
        if len(d) < size: return rows, False
    return rows, True
pos, pos_more = pages("/positions", {"sizeThreshold": 0}, 500, 20)
cl, cl_more = pages("/closed-positions", {}, 50, 60)
print(f"positions {len(pos)} (more: {pos_more}) | closed {len(cl)} (more: {cl_more})", flush=True)
c = collections.Counter()
for p in pos:
    c["redeemable, price 0 (lost)" if p["redeemable"] and p["curPrice"] == 0 else "redeemable, price 1 (won, unredeemed)" if p["redeemable"] and p["curPrice"] == 1 else "open market" if not p["redeemable"] else "redeemable, other price"] += 1
print("positions by kind:", dict(c))
cla = {x["asset"] for x in cl}
lost = [p for p in pos if p["redeemable"] and p["curPrice"] == 0]
print("lost positions also in closed:", sum(p["asset"] in cla for p in lost), "of", len(lost))
print("closed rows: price 1:", sum(x["curPrice"] == 1 for x in cl), "price 0:", sum(x["curPrice"] == 0 for x in cl), "other:", sum(x["curPrice"] not in (0, 1) for x in cl))
print("lost positions' total cashPnl:", round(sum(p["cashPnl"] for p in lost)), "| closed total realizedPnl:", round(sum(x["realizedPnl"] for x in cl)))
print("position row keys with dates:", [k for k in pos[0] if "date" in k.lower() or "time" in k.lower()])
(RAW / "q1_rank339_positions.json").write_text(json.dumps(pos)); (RAW / "q1_rank339_closed.json").write_text(json.dumps(cl))
# batch lookup of resolution times for lost positions
ids = list(dict.fromkeys(p["conditionId"] for p in lost))[:20]
s, ms, _ = get(GAMMA, "/markets", {"condition_ids": ids, "closed": "true", "limit": 100})
print("gamma batch of", len(ids), "condition ids ->", s, len(ms) if isinstance(ms, list) else ms)
