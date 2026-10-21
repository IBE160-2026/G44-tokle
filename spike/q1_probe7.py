"""Q1 probe 7: exact check (market filter) of whether lost and won-but-unredeemed positions of the rank-339 wallet are in /closed-positions.
Also: can Gamma return several markets in one request?"""
import json, random
from api import get, DATA, GAMMA, RAW
w = json.loads((RAW / "q1_wallets.json").read_text())["rank339"]
pos = json.loads((RAW / "q1_rank339_positions.json").read_text())
random.seed(44)
lost = [p for p in pos if p["redeemable"] and p["curPrice"] == 0]
won = [p for p in pos if p["redeemable"] and p["curPrice"] == 1]
def in_closed(sample):
    hit = 0
    for p in sample:
        s, c, _ = get(DATA, "/closed-positions", {"user": w, "market": p["conditionId"], "limit": 50})
        hit += any(x["asset"] == p["asset"] for x in c)
    return hit
sl, sw = random.sample(lost, 30), random.sample(won, 15)
print("lost, unredeemed: in closed (exact, by market):", in_closed(sl), "of", len(sl))
print("won, unredeemed:  in closed (exact, by market):", in_closed(sw), "of", len(sw), flush=True)
ids = list(dict.fromkeys(p["conditionId"] for p in lost))[:20]
for label, params in (("repeated param", [("condition_ids", i) for i in ids] + [("closed", "true"), ("limit", 100)]),
                      ("comma list", {"condition_ids": ",".join(ids), "closed": "true", "limit": 100})):
    s, ms, _ = get(GAMMA, "/markets", params)
    print("gamma", label, "->", s, len(ms) if isinstance(ms, list) else str(ms)[:100])
