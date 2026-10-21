"""Q2 probe 7: build a candidate wallet list from trades in markets that closed in the 30 days before a cut-off.
10 markets x 1000 trades each (window ends at the market's close), then count unique wallets and overlap."""
import json, collections, datetime as dt
from api import get, GAMMA, DATA, RAW, log

CUTOFF = dt.datetime(2025, 6, 30, tzinfo=dt.timezone.utc)
s, ms, _ = get(GAMMA, "/markets", {
    "closed": "true", "end_date_min": "2025-06-01T00:00:00Z", "end_date_max": "2025-06-30T00:00:00Z",
    "order": "volumeNum", "ascending": "false", "limit": 10}, save_as="q2_gamma_june.json")
print("markets", s, len(ms))
seen = collections.defaultdict(set)   # wallet -> markets
trades_per_market = {}
for m in ms:
    closed = dt.datetime.fromisoformat(m["closedTime"].replace("+00", "+00:00"))
    end = int(min(closed, CUTOFF).timestamp())
    s, t, _ = get(DATA, "/trades", {"market": m["conditionId"], "limit": 1000, "end": end})
    trades_per_market[m["conditionId"]] = len(t) if s == 200 else s
    if s == 200:
        for x in t:
            seen[x["proxyWallet"]].add(m["conditionId"])
    print(m["conditionId"][:10], (m["question"] or "")[:50].encode("ascii", "replace").decode(), "| vol", round(m["volumeNum"]), "| got", trades_per_market[m["conditionId"]])
multi = sum(1 for v in seen.values() if len(v) >= 2)
print("unique wallets:", len(seen), "| in >=2 markets:", multi, "| requests this probe:", len(log))
(RAW / "q2_candidates_june.json").write_text(json.dumps({w: sorted(v) for w, v in seen.items()}))
