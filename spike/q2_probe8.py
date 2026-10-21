"""Q2 probe 8: same 10 markets as probe 7, but the 1000 trades are spread over each market's whole life
(10 evenly spaced time windows x 100 trades) instead of the last 1000 before close."""
import json, collections, datetime as dt
from api import RAW, DATA, get, log

CUTOFF = dt.datetime(2025, 6, 30, tzinfo=dt.timezone.utc)
ms = json.loads((RAW / "q2_gamma_june.json").read_text("utf8"))
def ts(s):
    s = s.replace("+00", "+00:00") if s.endswith("+00") else s.replace("Z", "+00:00")
    return dt.datetime.fromisoformat(s)

seen = collections.defaultdict(set)
for m in ms:
    start = ts(m["startDate"]).timestamp()
    stop = min(ts(m["closedTime"]), CUTOFF).timestamp()
    n = 0
    for i in range(1, 11):
        end = int(start + (stop - start) * i / 10)
        s, t, _ = get(DATA, "/trades", {"market": m["conditionId"], "limit": 100, "end": end})
        if s != 200:
            print("  error", s, str(t)[:100]); continue
        n += len(t)
        for x in t:
            seen[x["proxyWallet"]].add(m["conditionId"])
    print(m["conditionId"][:10], "span days", round((stop - start) / 86400), "| trades", n, flush=True)
late = json.loads((RAW / "q2_candidates_june.json").read_text())
multi = sum(1 for v in seen.values() if len(v) >= 2)
print("SPREAD: unique wallets", len(seen), "| in >=2 markets", multi)
print("LATE (probe 7): unique", len(late), "| in >=2 markets", sum(1 for v in late.values() if len(v) >= 2))
print("wallets in both samples:", len(set(seen) & set(late)), "| requests:", len(log))
(RAW / "q2_candidates_spread.json").write_text(json.dumps({w: sorted(v) for w, v in seen.items()}))
