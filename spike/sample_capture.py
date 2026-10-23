"""Sample Dataset capture (2026-10-21): raw data and 1-minute price windows for the picked Wallets.

Why now (spine AD-24): Polymarket replaced the CLOB `/prices-history` route on 2026-09-04 with
`/v2/prices-history`, which keeps 1-minute prices for at least 7 days only. The old route still
answers with no end date announced, so the Sample Dataset's windows are fetched while it does.

For each Wallet in spike/raw/sample/picked.json (Edvard's pick, PRD §9 Q5/Q6):
  1. positions (Data API v2 CLOSED and OPEN) and activity (TRADE, REDEEM, SPLIT, MERGE, CONVERSION),
     saved as returned, as the input the Sample Dataset serializer will later read (AD-14);
  2. the after part's buy fills: Positions whose first buy is on or after the Cut-off Date, in Markets
     Gamma says are resolved, the first 2,000 by first-buy time (AD-7, AD-8);
  3. one short window per buy fill, [t - 2 min, t + 32 min], merged where they overlap, packed into
     requests of at most 14 days per token, from the CLOB route with fidelity=1; only points inside
     the short windows are stored (AD-14). A window whose points are not 1-minute is counted, never
     silently kept as if it were (AD-24).

Read-only, public endpoints, no keys, 4 requests per second. Output in spike/raw/sample/capture/
(git-ignored for now). Resumable: finished parts are skipped on a re-run.
"""
import json
import sys
from collections import defaultdict

import api
from api import CLOB, DATA
from sample_pick import C, OUT, WINDOW, fetch, gamma_cache, gamma_lookup

CAP = OUT / "capture"
ROW_CAP = 150_000         # activity rows per Wallet; hitting it is reported, never silent
PRE, POST = 120, 32 * 60  # AD-14 window around each buy fill
SPAN = 14 * 86400         # longest window the CLOB route accepts at fidelity=1 (spike Q3)


def paged(path, params, cap):
    rows, cursor, hit = [], None, False
    while True:
        p = dict(params, cursor=cursor) if cursor else params
        d = fetch(DATA, path, p)
        rows += d.get("data") or []
        cursor = (d.get("pagination") or {}).get("next_cursor")
        if not (d.get("pagination") or {}).get("has_more") or not cursor:
            break
        if len(rows) >= cap:
            hit = True
            break
    return rows, hit


def save(path, data):
    path.write_text(json.dumps(data), encoding="utf8")


def capture_wallet(w):
    d = CAP / w
    d.mkdir(parents=True, exist_ok=True)
    if not (d / "positions.json").exists():
        closed, h1 = paged("/v2/positions", {"user": w, "status": "CLOSED", "limit": 1000,
                                             "sort_by": "TIMESTAMP", "sort_direction": "ASC"}, 60_000)
        open_, h2 = paged("/v2/positions", {"user": w, "status": "OPEN", "limit": 1000}, 60_000)
        save(d / "positions.json", {"closed": closed, "open": open_, "capped": h1 or h2})
    # two reads, so a long history before the date cannot use up the cap before the after part is reached:
    # before the date newest-first (the rows that decide whether a token was first bought before it),
    # and from the date oldest-first (the after part, AD-7)
    types = "TRADE,REDEEM,SPLIT,MERGE,CONVERSION"
    if not (d / "activity_before.json").exists():
        act_b, hit_b = paged("/v2/activity", {"user": w, "type": types, "start": 1, "end": C - 1,
                                              "limit": 1000, "sort_direction": "DESC"}, ROW_CAP)
        save(d / "activity_before.json", {"rows": act_b, "capped": hit_b})
    if not (d / "activity_after.json").exists():
        act_a, hit_a = paged("/v2/activity", {"user": w, "type": types, "start": C,
                                              "limit": 1000, "sort_direction": "ASC"}, ROW_CAP)
        save(d / "activity_after.json", {"rows": act_a, "capped": hit_a})
    ab = json.loads((d / "activity_before.json").read_text(encoding="utf8"))
    aa = json.loads((d / "activity_after.json").read_text(encoding="utf8"))
    act = ab["rows"] + aa["rows"]

    # after part: tokens whose first BUY is on or after the cut-off, in resolved Markets, first 2,000
    buys, first = defaultdict(list), {}
    for r in act:
        if r.get("type") == "TRADE" and r.get("side") == "BUY" and not r.get("is_combo"):
            buys[r["token_id"]].append(r["timestamp"])
            first[r["token_id"]] = min(first.get(r["token_id"], r["timestamp"]), r["timestamp"])
    cond = {r["token_id"]: r["condition_id"] for r in act if r.get("token_id")}
    # A capped before-read misses older buys, so a token first bought before the date can look new.
    # The positions list's own first_entry_at is checked too (found 2026-10-23: 165, 46 and 20 such tokens).
    pos = json.loads((d / "positions.json").read_text(encoding="utf8"))
    entry = {r["token_id"]: r.get("first_entry_at") for r in pos["closed"] + pos["open"]}
    after = sorted((t for t in first if first[t] >= C and not (entry.get(t) and entry[t] < C)), key=lambda t: first[t])
    gamma_lookup([cond[t] for t in after])
    after = [t for t in after if gamma_cache.get(cond[t])][:WINDOW]

    pf = d / "prices.json"
    prices = json.loads(pf.read_text(encoding="utf8")) if pf.exists() else {}
    stats = {"tokens": len(after), "requests": 0, "coarse": 0, "empty": 0}
    for i, t in enumerate(after):
        if t in prices:
            continue
        wins = []
        for x in sorted(buys[t]):
            a, b = x - PRE, x + POST
            if wins and a <= wins[-1][1]:
                wins[-1][1] = max(wins[-1][1], b)
            else:
                wins.append([a, b])
        groups = []
        for a, b in wins:
            if groups and b - groups[-1][0][0] <= SPAN:
                groups[-1].append([a, b])
            else:
                groups.append([[a, b]])
        pts, coarse = [], False
        errors = []
        for g in groups:
            try:
                h = fetch(CLOB, "/prices-history", {"market": t, "startTs": g[0][0], "endTs": g[-1][1], "fidelity": 1})
            except RuntimeError as e:      # one bad token is recorded, never stops the capture
                errors.append(str(e)[:200])
                continue
            finally:
                stats["requests"] += 1
            hist = h.get("history", []) if isinstance(h, dict) else []
            ts_ = sorted(p["t"] for p in hist)
            gaps = [b - a for a, b in zip(ts_, ts_[1:])]
            if gaps and sorted(gaps)[len(gaps) // 2] > 90:
                coarse = True
            pts += [[p["t"], p["p"]] for p in hist if any(a <= p["t"] <= b for a, b in g)]
        stats["coarse"] += coarse
        stats["empty"] += not pts
        prices[t] = {"windows": wins, "points": sorted(pts), "coarse": coarse, "requests": len(groups), "errors": errors}
        if i % 50 == 49:
            save(pf, prices)
            print(f"    {w[:10]} {i + 1}/{len(after)} tokens, requests {len(api.log)}", flush=True)
    save(pf, prices)
    done = {"wallet": w, "after_tokens": len(after), "buy_fills": sum(len(buys[t]) for t in after),
            "tokens_with_points": sum(1 for t in after if prices[t]["points"]),
            "coarse_tokens": sum(1 for t in after if prices[t]["coarse"]),
            "points": sum(len(prices[t]["points"]) for t in after),
            "tokens_failed": sum(1 for t in after if prices[t].get("errors")),
            "activity_rows_before": len(ab["rows"]), "activity_capped_before": ab["capped"],
            "activity_rows_after": len(aa["rows"]), "activity_capped_after": aa["capped"],
            "positions_capped": json.loads((d / "positions.json").read_text(encoding="utf8"))["capped"],
            "price_requests": sum(prices[t].get("requests", 0) for t in after)}
    save(d / "summary.json", done)
    return done


def main():
    picked = json.loads((OUT / "picked.json").read_text(encoding="utf8"))
    for w in picked["wallets"]:
        s = capture_wallet(w)
        print(json.dumps(s), flush=True)
    print("total requests this run:", len(api.log))


if __name__ == "__main__":
    sys.exit(main())
