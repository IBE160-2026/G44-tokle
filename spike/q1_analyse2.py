import json, collections, datetime as dt
from api import RAW
tr = json.loads((RAW / "q1_typical_trades.json").read_text())
cl = json.loads((RAW / "q1_typical_closed.json").read_text())
w1, w2 = tr[:5500], tr[5500:]
end = min(r["timestamp"] for r in w1[-500:])
merged = [r for r in w1 if r["timestamp"] > end] + w2          # window 1 rows at the boundary second are re-fetched in window 2
naive = tr
print("rows: window1", len(w1), "window2", len(w2), "| boundary ts", end, "| w1 rows at boundary", sum(r['timestamp'] == end for r in w1), "| w2 rows at boundary", sum(r['timestamp'] == end for r in w2))
print("merged (correct):", len(merged), "| naive concat:", len(naive))
key = lambda r: (r["transactionHash"], r["asset"], r["side"], r["price"], r["size"], r["timestamp"])
c = collections.Counter(map(key, merged))
dups = {k: n for k, n in c.items() if n > 1}
print("identical-looking row groups in merged:", len(dups), "rows in them:", sum(dups.values()), "| max group", max(dups.values()) if dups else 0)
print("fields:", sorted(merged[0].keys()))
print("types:", collections.Counter(r["type"] for r in merged), "sides:", collections.Counter(r["side"] for r in merged))
print("newest", dt.datetime.fromtimestamp(max(r['timestamp'] for r in merged), dt.timezone.utc), "oldest", dt.datetime.fromtimestamp(min(r['timestamp'] for r in merged), dt.timezone.utc))

def buys(rows):
    b = collections.defaultdict(float)
    for r in rows:
        if r["side"] == "BUY": b[r["asset"]] += r["size"]
    return b
def check(label, rows):
    b = buys(rows); ok = bad = miss = 0
    for p in cl:
        if p["asset"] not in b: miss += 1; continue
        if abs(b[p["asset"]] - p["totalBought"]) < 0.01: ok += 1
        else: bad += 1
    print(f"{label:28} closed positions: match totalBought {ok}, differ {bad}, no trades found {miss}")
check("merged, all rows kept", merged)
dd = list({key(r): r for r in merged}.values())
check("identical rows collapsed", dd)
check("naive concat (boundary x2)", naive)
