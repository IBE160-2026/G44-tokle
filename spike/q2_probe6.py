"""Q2 probe 6: any time filter on /trades? any holders list for a closed market? offset+limit ceiling?"""
import json
from api import get, DATA, RAW

cid = json.loads((RAW / "q2_gamma_markets2.json").read_text("utf8"))[0]["conditionId"]
def trades(**p):
    s, t, rl = get(DATA, "/trades", {"market": cid, "limit": 5, **p})
    if s != 200 or not isinstance(t, list):
        return s, str(t)[:160]
    return s, [x["timestamp"] for x in t]

print("no filter      ", trades())
print("end=1730000000 ", trades(end=1730000000))
print("before=1730000000", trades(before=1730000000))
print("start=1730900000", trades(start=1730900000))
print("offset=10000 limit=5000", trades(offset=10000, limit=5000))
s, h, rl = get(DATA, "/holders", {"market": cid, "limit": 5})
print("holders", s, (len(h), [len(x.get("holders", [])) for x in h]) if isinstance(h, list) else h)
