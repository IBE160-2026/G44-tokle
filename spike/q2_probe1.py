"""Q2 probe 1: what does the leaderboard endpoint take, and how far back does it go?"""
import json
from api import get, DATA

for params in [
    {"timePeriod": "ALL", "orderBy": "PNL", "limit": 5},
    {"timePeriod": "MONTH", "orderBy": "PNL", "limit": 3},
    {"timePeriod": "ALL", "orderBy": "PNL", "limit": 3, "offset": 1000},
    {"timePeriod": "ALL", "orderBy": "PNL", "limit": 3, "endDate": "2025-06-30"},
]:
    s, d, rl = get(DATA, "/v1/leaderboard", params)
    print(params, "->", s, rl)
    print(json.dumps(d, indent=1)[:900] if s == 200 else d)
    print()
