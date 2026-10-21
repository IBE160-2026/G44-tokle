"""Architecture probe 5 (2026-10-21): does /v2/activity?type=SPLIT,MERGE really filter?

Detecting split/merge Positions (left out of the Skill Test) rests on this filter.
Proof, not just status 200: the filtered rows must all be SPLIT or MERGE, and a made-up
parameter (control) must return a different list that also has TRADE rows.
The typical wallet had 5 split/merge positions in the spike (v1).
"""
import json
from collections import Counter
from api import get, DATA, RAW

W = json.loads((RAW / "q1_wallets.json").read_text())["typical"]
s1, d1, _ = get(DATA, "/v2/activity", {"user": W, "type": "SPLIT,MERGE", "start": 1, "limit": 1000})
s2, d2, _ = get(DATA, "/v2/activity", {"user": W, "type_xyz": "SPLIT,MERGE", "start": 1, "limit": 1000})
f, c = d1.get("data") or [], d2.get("data") or []
print("filtered:", s1, len(f), "rows", Counter(r.get("type") for r in f), "| has_more", (d1.get("pagination") or {}).get("has_more"))
print("control :", s2, len(c), "rows", Counter(r.get("type") for r in c).most_common(4))
print("filter works:", bool(f) and all(r.get("type") in ("SPLIT", "MERGE") for r in f) and Counter(r.get("type") for r in c)["TRADE"] > 0)
print("markets in filtered rows:", len({r.get("condition_id") for r in f}), "| row keys:", sorted(f[0].keys()) if f else "-")
