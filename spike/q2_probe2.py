"""Q2 probe 2: leaderboard limits, and does any date parameter change the ranking?"""
import json
from api import get, DATA

def top(params):
    s, d, rl = get(DATA, "/v1/leaderboard", params)
    if s != 200:
        return s, str(d)[:200]
    return s, [(r["rank"], r["proxyWallet"][:8]) for r in d]

base = {"timePeriod": "ALL", "orderBy": "PNL"}
tests = [
    ("limit=100", {**base, "limit": 100}),
    ("limit=50", {**base, "limit": 50}),
    ("offset=1001", {**base, "limit": 2, "offset": 1001}),
    ("offset=5000", {**base, "limit": 2, "offset": 5000}),
    ("timePeriod=YEAR", {"timePeriod": "YEAR", "orderBy": "PNL", "limit": 2}),
    ("date=2025-06-30", {**base, "limit": 2, "date": "2025-06-30"}),
    ("end=1751241600", {**base, "limit": 2, "end": 1751241600}),
    ("before=2025-06-30", {**base, "limit": 2, "before": "2025-06-30"}),
]
for name, p in tests:
    s, r = top(p)
    print(name, "->", s, len(r) if isinstance(r, list) else "", (r[:2] if isinstance(r, list) else r))
