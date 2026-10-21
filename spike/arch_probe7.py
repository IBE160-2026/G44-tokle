"""Architecture probe 7 (2026-10-21): does /v2/activity filter a Wallet's rows by time for real?

The per-Wallet activity read (trades, redeems, splits, merges) is limited to the window
around the Cut-off Date, so start= and end= must work. Same proof as probe 1: a made-up
parameter as control, the filtered page must differ, respect the bound on every row, and
start exactly where the unfiltered list crosses the bound (compared as sets, since rows
can share a timestamp).
"""
import json
from api import get, DATA, RAW

W = json.loads((RAW / "q1_wallets.json").read_text())["typical"]
BASE = {"user": W, "type": "TRADE,REDEEM", "limit": 1000}


def rows(params):
    s, d, _ = get(DATA, "/v2/activity", params)
    assert s == 200, (s, str(d)[:300])
    return d["data"]


key = lambda r: (r["transaction_hash"], r["token_id"], r["type"], r["side"], r["size"], r["timestamp"])
base = rows({**BASE, "start": 1})
t = [r["timestamp"] for r in base]
mid = t[len(t) // 2]
print(f"unfiltered: {len(base)} rows, newest {t[0]}, oldest {t[-1]}, mid {mid}")
ctrl = rows({**BASE, "start": 1, "before_xyz": mid})
print("control (unknown param) identical:", [key(r) for r in ctrl] == [key(r) for r in base])
endf = rows({**BASE, "start": 1, "end": mid})
want = {key(r) for r in base if r["timestamp"] <= mid}
got = {key(r) for r in endf}
print(f"end=mid: {len(endf)} rows | all <= mid {all(r['timestamp'] <= mid for r in endf)} | differs {got != {key(r) for r in base}} "
      f"| contains every unfiltered row <= mid {want <= got}")
startf = rows({**BASE, "start": mid, "sort_direction": "ASC"})
want = {key(r) for r in base if r["timestamp"] >= mid}
got = {key(r) for r in startf}
print(f"start=mid ASC: {len(startf)} rows | all >= mid {all(r['timestamp'] >= mid for r in startf)} | "
      f"ascending {[r['timestamp'] for r in startf] == sorted(r['timestamp'] for r in startf)} | "
      f"contains every unfiltered row >= mid {want <= got}")
