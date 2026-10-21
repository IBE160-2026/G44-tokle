"""Q3 probe 4: how big is the gap between what buyers and sellers actually paid, and where does the history price sit?
Per market: up to 1000 recent-ish trades of one outcome token (mid-life), grouped into 1-minute and 10-minute buckets."""
import json, statistics as st, datetime as dt, collections
from api import get, DATA, CLOB, RAW
def ts(s):
    s = s.replace("+00", "+00:00") if s.endswith("+00") else s.replace("Z", "+00:00")
    return int(dt.datetime.fromisoformat(s).timestamp())
m1 = json.loads((RAW / "q2_gamma_markets2.json").read_text()); m2 = json.loads((RAW / "q2_gamma_june.json").read_text()); m3 = json.loads((RAW / "q2_gamma_markets.json").read_text())
pick = {"Trump 2024 (huge)": m1[0], "NBA Raptors (large)": m2[1], "Korea election Lee (large)": m2[5], "Biden says Old ($10k)": m3[0], "Ocon pole ($1k)": m3[3]}
def pct(a, p): a = sorted(a); return a[min(len(a) - 1, int(p * len(a)))] if a else None
for name, m in pick.items():
    tok = json.loads(m["clobTokenIds"])[0]
    start, close = ts(m["startDate"]), ts(m["closedTime"])
    end = close - 6 * 3600 if close - start < 3 * 86400 else start + (close - start) * 3 // 4   # late-ish in life, away from the 0/1 collapse
    s, t, _ = get(DATA, "/trades", {"market": m["conditionId"], "limit": 1000, "end": end})
    t = [x for x in t if x["asset"] == tok] if s == 200 else []
    if len(t) < 20: print(name, "-> only", len(t), "trades of the first token"); continue
    lo, hi = min(x["timestamp"] for x in t), max(x["timestamp"] for x in t)
    s, d, _ = get(CLOB, "/prices-history", {"market": tok, "startTs": lo - 120, "endTs": hi + 120, "fidelity": 1})
    h = {p["t"] // 60: p["p"] for p in d.get("history", [])} if s == 200 else {}
    line = [f"{name}: {len(t)} trades over {round((hi - lo) / 60)} min, price ~{st.median(x['price'] for x in t):.2f}"]
    for label, size in (("1 min", 60), ("10 min", 600)):
        b = collections.defaultdict(lambda: {"BUY": [], "SELL": []})
        for x in t: b[x["timestamp"] // size][x["side"]].append(x["price"])
        both = [(st.mean(v["BUY"]), st.mean(v["SELL"]), key) for key, v in b.items() if v["BUY"] and v["SELL"]]
        spread = [(a - c) * 100 for a, c, _ in both]
        inside = sum(1 for a, c, k in both if h.get(k * size // 60) is not None and min(a, c) - 0.0005 <= h[k * size // 60] <= max(a, c) + 0.0005)
        gap_buy = [(a - h[k * size // 60]) * 100 for a, c, k in both if k * size // 60 in h]
        line.append(f"{label}: {len(both)} buckets with both sides; BUY-SELL gap median {st.median(spread):.2f} c, p90 {pct(spread, .9):.2f} c; mean BUY price minus history: median {st.median(gap_buy):+.2f} c" if both else f"{label}: no bucket with both sides")
    print("\n  ".join(line), flush=True)
