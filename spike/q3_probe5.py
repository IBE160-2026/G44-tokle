"""Q3 probe 5: (A) price paid by the typical wallet's own fills minus the 1-min history price; (B) buy/sell gap in mid-priced, mid-volume markets."""
import json, statistics as st, datetime as dt, collections, random
from api import get, DATA, CLOB, GAMMA, RAW
def ts(s):
    s = s.replace("+00", "+00:00") if s.endswith("+00") else s.replace("Z", "+00:00")
    return int(dt.datetime.fromisoformat(s).timestamp())
def pct(a, p): a = sorted(a); return a[min(len(a) - 1, int(p * len(a)))]

print("(A) the typical wallet's own fills, 40 random fills from distinct markets since 2024-09 (price paid/received minus history price, in cents)")
tr = json.loads((RAW / "q1_typical_trades.json").read_text())
random.seed(44)
by_market = collections.defaultdict(list)
for r in tr:
    if r["timestamp"] > 1725000000 and abs(r["usdcSize"] - r["size"] * r["price"]) < 0.001:   # fee-free rows only, so the price is the pure fill price
        by_market[r["conditionId"]].append(r)
sample = [random.choice(v) for v in random.sample(list(by_market.values()), 40)]
res = {"BUY": [], "SELL": []}
for r in sample:
    s, d, _ = get(CLOB, "/prices-history", {"market": r["asset"], "startTs": r["timestamp"] - 180, "endTs": r["timestamp"] + 180, "fidelity": 1})
    h = d.get("history", []) if s == 200 else []
    if not h: continue
    near = min(h, key=lambda p: abs(p["t"] - r["timestamp"]))
    res[r["side"]].append(((r["price"] - near["p"]) * 100, r["price"], r["size"] * r["price"]))
for side, v in res.items():
    if v: print(f"  {side}: {len(v)} fills, paid minus history: median {st.median(x[0] for x in v):+.2f} c, p90 of |gap| {pct([abs(x[0]) for x in v], .9):.2f} c | median fill price {st.median(x[1] for x in v):.3f}, median size ${st.median(x[2] for x in v):,.0f}")

print("\n(B) mid-priced, mid-volume markets closed in March 2026 (one outcome token, 1000 trades before 3/4 of life)")
s, ms, _ = get(GAMMA, "/markets", {"closed": "true", "end_date_min": "2026-03-01T00:00:00Z", "end_date_max": "2026-04-01T00:00:00Z", "order": "volumeNum", "ascending": "false", "limit": 30, "offset": 20})
done = 0
for m in ms:
    if done >= 4: break
    tok = json.loads(m["clobTokenIds"])[0]; start, close = ts(m["startDate"]), ts(m["closedTime"])
    end = start + (close - start) * 3 // 4
    s, t, _ = get(DATA, "/trades", {"market": m["conditionId"], "limit": 1000, "end": end})
    t = [x for x in t if x["asset"] == tok] if s == 200 else []
    if len(t) < 200 or not 0.15 <= st.median(x["price"] for x in t) <= 0.85: continue
    done += 1
    lo, hi = min(x["timestamp"] for x in t), max(x["timestamp"] for x in t)
    s, d, _ = get(CLOB, "/prices-history", {"market": tok, "startTs": lo - 120, "endTs": hi + 120, "fidelity": 1})
    h = {p["t"] // 60: p["p"] for p in d.get("history", [])} if s == 200 else {}
    b = collections.defaultdict(lambda: {"BUY": [], "SELL": []})
    for x in t: b[x["timestamp"] // 600][x["side"]].append(x["price"])
    both = [(st.mean(v["BUY"]), st.mean(v["SELL"]), k) for k, v in b.items() if v["BUY"] and v["SELL"]]
    gap = [(a - c) * 100 for a, c, _ in both]; off = [(a - h[k * 10]) * 100 for a, c, k in both if k * 10 in h]
    print(f"  {m['question'][:44].encode('ascii','replace').decode():44} vol {round(m['volumeNum']):>9}, {len(t)} trades, price ~{st.median(x['price'] for x in t):.2f} | 10-min buckets with both sides: {len(both)}" + (f", BUY-SELL gap median {st.median(gap):.2f} c, p90 {pct(gap, .9):.2f} c; BUY minus history median {st.median(off):+.2f} c" if both and off else ""), flush=True)
