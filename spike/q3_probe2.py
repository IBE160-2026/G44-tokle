"""Q3 probe 2: how old, how long a window, and thin markets."""
import json, datetime as dt
from api import get, CLOB, GAMMA, RAW
f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
gm = {m["conditionId"]: m for m in json.loads((RAW / "q2_gamma_markets.json").read_text())} if (RAW / "q2_gamma_markets.json").exists() else {}
ms = json.loads((RAW / "q2_gamma_markets2.json").read_text()) + json.loads((RAW / "q2_gamma_markets.json").read_text())
def token(m): return json.loads(m["clobTokenIds"])[0]
def closed_ts(m):
    s = m["closedTime"]; s = s.replace("+00", "+00:00") if s.endswith("+00") else s
    return int(dt.datetime.fromisoformat(s).timestamp())

print("-- by age / thinness: window = 2h ending 1h before close, fidelity 1")
for m in ms:
    pass
seen = set()
for m in ms:
    q = m["question"][:50].encode("ascii", "replace").decode()
    if q in seen: continue
    seen.add(q)
    t = closed_ts(m) - 3600
    s, d, _ = get(CLOB, "/prices-history", {"market": token(m), "startTs": t - 3600, "endTs": t + 3600, "fidelity": 1})
    h = d.get("history", []) if isinstance(d, dict) else []
    gaps = [b["t"] - a["t"] for a, b in zip(h, h[1:])]
    print(f"{f(t)} vol {round(m['volumeNum']):>11} | {q:50} | {s} {len(h):3} pts, max gap {max(gaps) if gaps else '-'}s" + ("" if s == 200 else " " + str(d)[:80]), flush=True)
    if len(seen) >= 8: break

m = ms[0]  # biggest market: how long a window can one request cover at fidelity 1?
print("\n-- window length at fidelity 1 on", m["question"][:40])
end = closed_ts(m) - 86400
for days in (1, 7, 14, 30):
    s, d, _ = get(CLOB, "/prices-history", {"market": token(m), "startTs": end - days * 86400, "endTs": end, "fidelity": 1})
    h = d.get("history", []) if isinstance(d, dict) else []
    print(f"  {days:2} days -> {s}, {len(h)} pts (full would be {days * 1440})" + ("" if s == 200 else " " + str(d)[:100]), flush=True)
