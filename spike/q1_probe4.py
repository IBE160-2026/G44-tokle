"""Q1 probe 4: do losing (price 0) bets sit in /positions instead of /closed-positions?
For the typical and the tiny wallet: every token the wallet ever traded or holds, and where it shows up."""
import json, collections
from api import get, DATA, GAMMA, RAW

W = json.loads((RAW / "q1_wallets.json").read_text())

def pages(path, w, extra, size, cap=40):
    rows, off = [], 0
    for _ in range(cap):
        s, d, _ = get(DATA, path, {"user": w, "limit": size, "offset": off, **extra})
        if s != 200 or not d: break
        rows += d; off += size
        if len(d) < size: break
    return rows

def traded_assets(name, w):
    if name == "typical":
        tr = json.loads((RAW / "q1_typical_trades.json").read_text())
    else:
        tr = pages("/activity", w, {"start": 1}, 500)
    return tr

for name in ("typical", "small"):
    w = W[name]
    print("==", name, w)
    closed = pages("/closed-positions", w, {}, 50)
    for label, extra in (("default (sizeThreshold=1)", {}), ("sizeThreshold=0", {"sizeThreshold": 0}), ("sizeThreshold=0, includeArchived", {"sizeThreshold": 0, "includeArchived": "true"})):
        pos = pages("/positions", w, extra, 500)
        print(f"  /positions {label}: {len(pos)} rows | price 0: {sum(p['curPrice'] == 0 for p in pos)} | redeemable: {sum(bool(p['redeemable']) for p in pos)}")
    (RAW / f"q1_{name}_positions.json").write_text(json.dumps(pos))
    tr = traded_assets(name, w)
    types = collections.Counter(r["type"] for r in tr)
    traded = {r["asset"] for r in tr if r["type"] == "TRADE"}
    cl, ps = {p["asset"] for p in closed}, {p["asset"] for p in pos}
    print(f"  closed rows {len(closed)} (price 0: {sum(p['curPrice'] == 0 for p in closed)}) | traded tokens {len(traded)}: in closed {len(traded & cl)}, in positions only {len((traded & ps) - cl)}, in neither {len(traded - cl - ps)} | activity types {dict(types)}")
    (RAW / f"q1_{name}_closed_full.json").write_text(json.dumps(closed))
