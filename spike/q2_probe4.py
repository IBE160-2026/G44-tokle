"""Q2 probe 4: biggest markets closed before the cut-off; trades in one of them."""
import json
from api import get, GAMMA, DATA

CUTOFF = "2025-06-30"
s, d, rl = get(GAMMA, "/markets", {
    "closed": "true", "end_date_max": CUTOFF + "T00:00:00Z",
    "order": "volumeNum", "ascending": "false", "limit": 5}, save_as="q2_gamma_markets2.json")
print("gamma", s, len(d) if isinstance(d, list) else d)
for m in d:
    print(m["conditionId"][:12], "|", m["question"][:55], "| closed", m.get("closedTime"), "| vol", m.get("volumeNum"),
          "| feesEnabled", m.get("feesEnabled"), m.get("feeType"))
cid = d[0]["conditionId"]
print("\nTrades in:", d[0]["question"])
for params in [{"market": cid, "limit": 10}, {"market": cid, "limit": 10, "takerOnly": "false"}]:
    s, t, rl = get(DATA, "/trades", params)
    print(params.get("takerOnly", "default"), "->", s, len(t) if isinstance(t, list) else t)
    if s == 200 and t:
        print(" first:", {k: t[0][k] for k in t[0] if k in ("proxyWallet", "side", "size", "price", "timestamp", "transactionHash")})
        print(" keys:", sorted(t[0].keys()))
