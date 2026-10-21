"""Q3 / PRD Q3 open point: how many price-history requests would a Copy Pool need?
Draw 10 pool wallets at random (seed 44) that rank in the top 3,000 all-time (closer to a Scan's top-200 than a random wallet),
read their closed positions (capped at 40 pages = 2,000 rows) and count distinct tokens, overall and after an example cut-off."""
import json, random, statistics as st, collections, datetime as dt
from api import get, DATA, RAW, log

CUTOFF = int(dt.datetime(2025, 6, 30, tzinfo=dt.timezone.utc).timestamp())
pool = json.loads((RAW / "q2_candidates_spread.json").read_text())
multi = sorted(w for w, v in pool.items() if len(v) >= 2)
random.seed(44)
random.shuffle(multi)
picked, draws = [], 0
for w in multi:
    if len(picked) == 10 or draws == 60: break
    draws += 1
    s, d, _ = get(DATA, "/v1/leaderboard", {"timePeriod": "ALL", "orderBy": "PNL", "user": w})
    if s == 200 and d and int(d[0]["rank"]) <= 3000:
        picked.append((w, int(d[0]["rank"])))
print(f"picked {len(picked)} wallets after {draws} draws; ranks {[r for _, r in picked]}", flush=True)

rows = {}
for w, rank in picked:
    got, off, truncated = [], 0, False
    for _ in range(40):
        s, d, _ = get(DATA, "/closed-positions", {"user": w, "limit": 50, "offset": off, "sortBy": "TIMESTAMP", "sortDirection": "ASC"})
        if s != 200 or not d: break
        got += d; off += 50
        if len(d) < 50: break
    else:
        truncated = True
    rows[w] = got
    after = [p for p in got if p["timestamp"] >= CUTOFF]
    print(f"  rank {rank:>5} {w[:10]}: {len(got):>4} closed rows{' (cap)' if truncated else ''}, tokens {len({p['asset'] for p in got}):>4}, after 2025-06-30: {len(after):>4} rows / {len({p['asset'] for p in after}):>4} tokens", flush=True)
(RAW / "q3_copy_pool_rows.json").write_text(json.dumps(rows))

allp = [p for v in rows.values() for p in v]
tok_all = [len({p["asset"] for p in v}) for v in rows.values()]
tok_after = [len({p["asset"] for p in v if p["timestamp"] >= CUTOFF}) for v in rows.values()]
u_all = len({p["asset"] for p in allp}); u_after = len({p["asset"] for p in allp if p["timestamp"] >= CUTOFF})
print(f"\nper wallet tokens, all: median {st.median(tok_all)}, mean {st.mean(tok_all):.0f}, max {max(tok_all)}; after cut-off: median {st.median(tok_after)}, mean {st.mean(tok_after):.0f}, max {max(tok_after)}")
print(f"sharing across the 10 wallets: tokens summed {sum(tok_all)} vs distinct {u_all} (all); {sum(tok_after)} vs {u_after} (after cut-off)")

# windows per token: typical wallet's real BUY times, how many 14-day windows does each token need?
tr = json.loads((RAW / "q1_typical_trades.json").read_text())
by = collections.defaultdict(list)
for r in tr:
    if r["side"] == "BUY": by[r["asset"]].append(r["timestamp"])
wins = []
for ts in by.values():
    ts.sort(); n, start = 1, ts[0]
    for t in ts:
        if t - start > 14 * 86400: n += 1; start = t
    wins.append(n)
print(f"typical wallet (real buy times): {len(by)} tokens need {sum(wins)} windows of 14 days ({sum(wins) / len(by):.2f} per token; {sum(1 for w in wins if w == 1)} tokens need just 1)")
print("requests this script:", len(log))
