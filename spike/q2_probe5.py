"""Q2 probe 5: how deep can /trades be paged for one old market?"""
import json
from api import get, DATA

cid = json.loads((__import__("api").RAW / "q2_gamma_markets2.json").read_text("utf8"))[0]["conditionId"]
for params in [
    {"limit": 500}, {"limit": 1000}, {"limit": 10000},
    {"limit": 10, "offset": 3000}, {"limit": 10, "offset": 10000}, {"limit": 10, "offset": 100000},
]:
    s, t, rl = get(DATA, "/trades", {"market": cid, **params})
    n = len(t) if isinstance(t, list) else None
    extra = ""
    if n:
        ts = [x["timestamp"] for x in t]
        extra = f"newest {max(ts)} oldest {min(ts)} wallets {len({x['proxyWallet'] for x in t})}"
    print(params, "->", s, n, extra, "" if s == 200 else str(t)[:200])
