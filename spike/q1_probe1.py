"""Q1 probe 1: pick an unranked pool wallet; measure history size and endpoint caps for each wallet."""
import json, random
from api import get, DATA, RAW

pool = json.loads((RAW / "q2_candidates_spread.json").read_text())
multi = sorted(w for w, v in pool.items() if len(v) >= 2)
wallets = json.loads((RAW / "q1_wallets.json").read_text())
random.seed(44); random.choice(multi)           # same first draw as before (the ranked 'typical')
for _ in range(8):
    w = random.choice(multi)
    s, d, _ = get(DATA, "/v1/leaderboard", {"timePeriod": "ALL", "orderBy": "PNL", "user": w})
    print("draw", w[:10], "leaderboard rows:", len(d) if isinstance(d, list) else d)
    if s == 200 and d == []:
        wallets["typical_unranked"] = w
        break
(RAW / "q1_wallets.json").write_text(json.dumps(wallets))
print(wallets, flush=True)

def size(path, w, extra=None):
    """Rough size via probing offsets with limit=1."""
    out = []
    for off in (0, 50, 500, 5000, 10000):
        s, d, _ = get(DATA, path, {"user": w, "limit": 1, "offset": off, **(extra or {})})
        out.append((off, s if s != 200 else len(d)))
        if s != 200 or not d:
            break
    return out

for name, w in wallets.items():
    print("==", name)
    print("  closed-positions rows at offsets:", size("/closed-positions", w))
    print("  activity rows at offsets        :", size("/activity", w))
