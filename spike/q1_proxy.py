"""Proxy check: does /trades, /positions, /closed-positions, /activity and Gamma public-profile agree on the address?
Wallets: leaderboard #1 and #2 plus one typical wallet drawn at random (seed 44) from the spread pool (in >=2 markets)."""
import json, random
from api import get, DATA, GAMMA, RAW

pool = json.loads((RAW / "q2_candidates_spread.json").read_text())
multi = sorted(w for w, v in pool.items() if len(v) >= 2)
random.seed(44)
typical = random.choice(multi)
lb = json.loads((__import__("pathlib").Path(__file__).parent / "samples" / "q2_leaderboard.json").read_text())
wallets = {"lb1": lb[0]["proxyWallet"], "lb2": lb[1]["proxyWallet"], "typical": typical}
print(wallets, flush=True)
(RAW / "q1_wallets.json").write_text(json.dumps(wallets))

for name, w in wallets.items():
    print("==", name, w)
    for path in ("/positions", "/closed-positions", "/activity", "/trades"):
        s, d, _ = get(DATA, path, {"user": w, "limit": 3})
        addrs = {x.get("proxyWallet") for x in d} if s == 200 and isinstance(d, list) else None
        print(f"  {path:18} {s} rows={len(d) if isinstance(d, list) else '-'} proxyWallet field == query: {addrs == {w} if addrs else addrs}")
    s, d, _ = get(GAMMA, "/public-profile", {"address": w})
    print("  public-profile", s, {k: d[k] for k in d if k in ("proxyWallet", "name", "pseudonym", "createdAt")} if s == 200 and isinstance(d, dict) else str(d)[:150])
    s, d, _ = get(DATA, "/v1/leaderboard", {"timePeriod": "ALL", "orderBy": "PNL", "user": w})
    print("  leaderboard user=", s, [(r["rank"], round(r["pnl"]), round(r["vol"])) for r in d] if s == 200 and isinstance(d, list) else str(d)[:100])
