"""Architecture probe 1 (2026-10-21): does /v2/positions?status=CLOSED really filter by time?

Data API v1 retires on 2026-10-24, so the app is built on v2. The cut-off rule
("the 2,000 Positions closest to the Cut-off Date on each side") needs a time filter.
Proof, not just status 200: a filtered page must differ from the unfiltered one,
respect the bound on every row, and start exactly where the unfiltered list crosses
the bound. A made-up parameter is sent as a control, to show what "ignored" looks like.
Also: is last_event_at the Market's resolution time (Gamma closedTime)?
"""
import json
from api import get, DATA, GAMMA, RAW

W = json.loads((RAW / "q1_wallets.json").read_text())["typical"]
BASE = {"user": W, "status": "CLOSED", "sort_by": "TIMESTAMP", "limit": 100}


def rows(params):
    s, d, _ = get(DATA, "/v2/positions", params)
    assert s == 200, (s, d)
    return d["data"], d.get("pagination")


def ts(r):
    return r["last_event_at"]


# 1. unfiltered, newest first
base, pag = rows({**BASE, "sort_direction": "DESC"})
print("unfiltered DESC:", len(base), "rows, newest", ts(base[0]), "oldest", ts(base[-1]), "| pagination", pag)
print("row keys:", sorted(base[0].keys()))
mid = ts(base[len(base) // 2])

# 2. control: an unknown parameter
ctrl, _ = rows({**BASE, "sort_direction": "DESC", "before_xyz": mid})
print("control (unknown param) identical to unfiltered:", [r["token_id"] for r in ctrl] == [r["token_id"] for r in base])

# 3. end filter, newest first: every row <= mid, and it starts where the unfiltered list crosses mid
endf, _ = rows({**BASE, "sort_direction": "DESC", "end": mid})
expect = [r["token_id"] for r in base if ts(r) <= mid]
got = [r["token_id"] for r in endf]
print("end=mid: rows", len(endf), "| all <= mid:", all(ts(r) <= mid for r in endf),
      "| differs from unfiltered:", got != [r["token_id"] for r in base],
      "| starts where unfiltered crosses mid:", got[:len(expect)] == expect[:len(got)])

# 4. start filter, oldest first: every row >= mid, first rows are the oldest ones >= mid
startf, _ = rows({**BASE, "sort_direction": "ASC", "start": mid})
expect_up = [r["token_id"] for r in reversed(base) if ts(r) >= mid]
got_up = [r["token_id"] for r in startf]
print("start=mid ASC: rows", len(startf), "| all >= mid:", all(ts(r) >= mid for r in startf),
      "| first rows match unfiltered >= mid:", got_up[:len(expect_up)] == expect_up[:len(got_up)])

# 5. last_event_at vs Gamma closedTime for 5 resolved rows
resolved = [r for r in base if r.get("current_price") in (0, 1)][:5] or base[:5]
s, mk, _ = get(GAMMA, "/markets", [("condition_ids", r["condition_id"]) for r in resolved] + [("closed", "true")])
closed = {m["conditionId"]: m.get("closedTime") for m in mk}
for r in resolved:
    print("  last_event_at", ts(r), "| gamma closedTime", closed.get(r["condition_id"]), "| current_price", r.get("current_price"))

# 6. (added after the first run) step 4's order check failed; is it only ties on last_event_at?
from collections import Counter
print("ties in unfiltered page:", sum(c - 1 for c in Counter(ts(r) for r in base).values() if c > 1))
print("start=mid ASC: same set as unfiltered >= mid:", set(got_up) == set(expect_up),
      "| ASC order by last_event_at:", [ts(r) for r in startf] == sorted(ts(r) for r in startf))
