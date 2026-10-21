"""Q1: does /v2/activity exist, and how does it page?"""
import json
from api import get, DATA, RAW
w = json.loads((RAW / "q1_wallets.json").read_text())["typical"]
s, d, _ = get(DATA, "/v2/activity", {"user": w, "limit": 2, "type": "TRADE"})
print("v2/activity", s, list(d.keys()) if isinstance(d, dict) else d, "| row keys:", sorted(d["data"][0].keys()) if isinstance(d, dict) and d.get("data") else "")
print("pagination:", d.get("pagination") if isinstance(d, dict) else None)
s, d, _ = get(DATA, "/v2/activity", {"user": w, "limit": 1, "offset": 5001})
print("v2 with offset:", s, str(d)[:160])
