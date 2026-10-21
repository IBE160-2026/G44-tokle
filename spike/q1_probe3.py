"""Q1 probe 3: sizes and request cost for the other wallets; offset cap check; whale window span."""
import json, datetime as dt
from api import get, DATA, RAW, log
W = json.loads((RAW / "q1_wallets.json").read_text())
small = "0xac9abcb0"
pool = json.loads((RAW / "q2_candidates_spread.json").read_text())
W["small"] = next(w for w in pool if w.startswith(small))
(RAW / "q1_wallets.json").write_text(json.dumps(W))
fmt = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")

def count_closed(w, cap=40):
    n, off, req = 0, 0, 0
    while req < cap:
        s, d, _ = get(DATA, "/closed-positions", {"user": w, "limit": 50, "offset": off}); req += 1
        if s != 200 or not d: return n, req, False
        n += len(d); off += 50
    return n, req, True
def count_trades(w, cap=15):
    n, req = 0, 0
    for off in range(0, 5001, 500):
        if req >= cap: break
        s, d, _ = get(DATA, "/activity", {"user": w, "limit": 500, "offset": off, "start": 1}); req += 1
        if s != 200: return n, req, s
        n += len(d)
        if len(d) < 500: return n, req, False
    return n, req, True   # True = hit the cap, more rows exist

for name in ("lb1", "small"):
    print(name, "closed positions (n, requests, truncated):", count_closed(W[name]), "| activity rows (all types):", count_trades(W[name]), flush=True)

w = W["lb2"]
print("whale offset checks:")
for off in (5001,):
    s, d, _ = get(DATA, "/activity", {"user": w, "limit": 5, "offset": off}); print("  activity offset", off, "->", s, d if s != 200 else len(d))
for off in (20000, 50000, 99950, 100001):
    s, d, _ = get(DATA, "/closed-positions", {"user": w, "limit": 50, "offset": off}); print("  closed-positions offset", off, "->", s, d if s != 200 else len(d))
s, a, _ = get(DATA, "/activity", {"user": w, "limit": 500, "offset": 0, "start": 1}); s2, b, _ = get(DATA, "/activity", {"user": w, "limit": 500, "offset": 5000, "start": 1})
print("whale activity: newest page covers", fmt(a[-1]["timestamp"]), "->", fmt(a[0]["timestamp"]), "| rows at depth 5000 covers", fmt(b[-1]["timestamp"]), "->", fmt(b[0]["timestamp"]))
print("requests this probe:", len(log))
