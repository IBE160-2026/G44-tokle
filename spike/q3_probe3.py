"""Q3 probe 3: where does minute-level history start, and is coarser history available for older resolved markets?"""
import json, datetime as dt
from api import get, CLOB, GAMMA, RAW
def ts(s):
    s = s.replace("+00", "+00:00") if s.endswith("+00") else s.replace("Z", "+00:00")
    return int(dt.datetime.fromisoformat(s).timestamp())
f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
rows = []
for a, b in [("2022-03-01", "2022-04-01"), ("2023-01-01", "2023-02-01"), ("2023-07-01", "2023-08-01"), ("2024-01-01", "2024-02-01"), ("2024-04-01", "2024-05-01")]:
    s, ms, _ = get(GAMMA, "/markets", {"closed": "true", "end_date_min": a + "T00:00:00Z", "end_date_max": b + "T00:00:00Z", "order": "volumeNum", "ascending": "false", "limit": 3})
    for m in ms[:2]:
        if m.get("clobTokenIds"): rows.append((a, m))
print("candidate markets:", len(rows), flush=True)
for a, m in rows:
    tok = json.loads(m["clobTokenIds"])[0]; t = ts(m["closedTime"]) - 3 * 3600
    res = []
    for fid in (1, 60, 720):
        s, d, _ = get(CLOB, "/prices-history", {"market": tok, "startTs": t - 7200, "endTs": t + 7200, "fidelity": fid})
        h = d.get("history", []) if isinstance(d, dict) else []
        res.append(f"fid {fid}: {len(h)} pts")
    s, d, _ = get(CLOB, "/prices-history", {"market": tok, "interval": "max", "fidelity": 60})
    h = d.get("history", []) if isinstance(d, dict) else []
    res.append(f"interval=max fid60: {len(h)} pts" + (f" ({f(h[0]['t'])} to {f(h[-1]['t'])})" if h else ""))
    print(f"{a} vol {round(m['volumeNum']):>10} {m['question'][:36].encode('ascii','replace').decode():36} | " + " | ".join(res), flush=True)
