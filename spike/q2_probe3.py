"""Q2 probe 3: list markets that closed before a cut-off, then see who traded in one."""
import json
from api import get, GAMMA, DATA

CUTOFF = "2025-06-30"
s, d, rl = get(GAMMA, "/markets", {
    "closed": "true", "end_date_max": CUTOFF + "T00:00:00Z",
    "order": "volume", "ascending": "false", "limit": 5}, save_as="q2_gamma_markets.json")
print("gamma markets", s, rl, type(d).__name__, len(d) if isinstance(d, list) else d)
if s == 200:
    for m in d:
        print(m.get("conditionId"), "|", (m.get("question") or "")[:60], "| end", m.get("endDate"),
              "| closed", m.get("closed"), "| vol", m.get("volumeNum"), "| closedTime", m.get("closedTime"))
    print("keys:", sorted(d[0].keys()))
