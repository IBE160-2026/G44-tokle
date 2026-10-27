"""Insurance pool (2026-10-24): pick 50 Wallets by spike/INSURANCE-RULE.md and capture their after-part prices.

The rule is in INSURANCE-RULE.md and was committed before this ran. Steps 2 to 4 (candidates, shortlist,
ranking) read only Markets resolved before the Cut-off Date; the after part is read only in step 5, for the
Wallets already chosen. Reuses the Sample Dataset pick's cached Market reads and Wallet rows.

Read-only, public endpoints, no keys. 3 workers share one locked limiter, at most 4.5 requests per second.
Output in spike/raw/insurance/ (git-ignored). Resumable (Edvard, 2026-10-24): every file is written atomically,
the ranking is saved as it goes, the pool is frozen in pool.json once chosen, and a re-run of the same command
skips every finished Wallet, file and price token. Only an activity read that was cut off mid-way starts that one
read again.

    python insurance_pick.py --dry-run   # steps 2-3 from cache only, no network
    python insurance_pick.py             # the whole rule
"""
import json
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import api
import sample_capture
import sample_pick
from sample_pick import C, CUTOFF, OUT, WINDOW, gamma_cache

POOL, SHORTLIST, WORKERS, RATE = 50, 150, 3, 4.5
INS = OUT.parent / "insurance"
INS.mkdir(parents=True, exist_ok=True)

# one limiter for all threads: the lock only books a time slot, the request itself runs outside it
_slot_lock, _next = threading.Lock(), [0.0]
_plain_get = api.get
api.DELAY = 0


def limited_get(*args, **kwargs):
    with _slot_lock:
        now = time.time()
        start = max(now, _next[0])
        _next[0] = start + 1 / RATE
    if start > now:
        time.sleep(start - now)
    try:
        return _plain_get(*args, **kwargs)
    except (TimeoutError, OSError) as e:
        # a read that times out mid-answer (found 2026-10-24 after 25 of 50 Wallets) is retried by fetch(),
        # which treats status None as retryable, instead of crashing the run (as spine AD-3 asks of the app)
        api.log.append((None, str(e)[:80]))
        return None, None, {}


api.get = limited_get
_gamma_lock = threading.Lock()
_plain_lookup = sample_pick.gamma_lookup


def locked_lookup(conds):
    with _gamma_lock:          # the Gamma cache is one shared file
        _plain_lookup(conds)


sample_pick.gamma_lookup = locked_lookup
sample_capture.gamma_lookup = locked_lookup
sample_capture.CAP = INS / "capture"
sample_capture.ROW_CAP = 300_000


def candidates():
    """Steps 2-3: complete Market reads only, pre-filter, top 150, ties by address."""
    markets = json.loads((OUT / f"funnel_markets_{CUTOFF:%Y%m%d}.json").read_text(encoding="utf8"))
    cand, used = defaultdict(float), 0
    for m in markets:
        mr = json.loads((OUT / f"market_{m['conditionId'][:18]}.json").read_text(encoding="utf8"))
        if mr["partial"]:
            continue
        used += 1
        for w, st, rp, cs, cp, ap in mr["rows"]:
            cand[w] += rp if st == "CLOSED" else cs * (cp - ap)
    ranked = sorted(cand, key=lambda w: (-cand[w], w))
    return ranked, used, len(cand)


def held_pnl_cents(w):
    """Step 4: Real PnL before the date on Positions held to resolution, in whole cents (as sample_sold.py)."""
    data = sample_pick.cached(f"wallet_{w[:12]}.json", lambda: sample_pick.wallet_rows(w))
    rows = [x for x in data["rows"] if (x.get("total_size") or 0) > 0]
    locked_lookup([x["condition_id"] for x in rows])
    pos = {}
    for x in rows:
        g = gamma_cache.get(x["condition_id"])
        if g and g["closed"] < C:
            won = g["yes_won"] if x.get("outcome_index") == 0 else not g["yes_won"]
            api_pnl = x.get("realized_pnl") if x["status"] == "CLOSED" else x.get("total_pnl")
            pos[x["token_id"]] = (g["closed"], api_pnl or 0, x["total_size"], x["avg_price"], 1 if won else 0)
    window = sorted(pos.values(), key=lambda v: -v[0])[:WINDOW]
    held = [v for v in window if abs(v[1] - v[2] * (v[4] - v[3])) <= 0.01 * v[2] * v[3] + 1]
    return sum(round(s * (1 - p) * 100) if o else round(-s * p * 100) for _, _, s, p, o in held), len(window), len(held)


def rank(shortlist):
    out = INS / "ranking.json"
    done = json.loads(out.read_text(encoding="utf8")) if out.exists() else {}

    lock = threading.Lock()

    def one(w):
        if w in done:
            return
        try:
            cents, n, n_held = held_pnl_cents(w)
            row = {"cents": cents, "window": n, "held": n_held}
        except RuntimeError as e:
            if "protocol contract" not in str(e):
                raise
            row = {"excluded": "protocol contract"}
        with lock:
            done[w] = row
            sample_pick.atomic_write(out, json.dumps(done, indent=1))
            print(f"  ranked {len(done)}/{len(shortlist)}, requests {len(api.log)}", flush=True)

    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(one, shortlist))
    ok = [w for w in shortlist if "cents" in done[w]]
    return sorted(ok, key=lambda w: (-done[w]["cents"], w))[:POOL], done


def main():
    ranked, used, n = candidates()
    print(f"cut-off {CUTOFF:%Y-%m-%d}: {used} Markets read in full, {n:,} candidates, shortlist {SHORTLIST}")
    shortlist = ranked[:SHORTLIST]
    if "--dry-run" in sys.argv:
        (INS / "shortlist_dryrun.json").write_text(json.dumps(shortlist, indent=1), encoding="utf8")
        print("dry run: shortlist written, no network used")
        return
    pool_file = INS / "pool.json"
    if pool_file.exists():               # frozen once chosen: a re-run never re-picks
        frozen = json.loads(pool_file.read_text(encoding="utf8"))
        pool, dropped = frozen["pool"], frozen["protocol_contracts_dropped"]
    else:
        pool, ranking = rank(shortlist)
        dropped = sum(1 for v in ranking.values() if v.get("excluded"))
        sample_pick.atomic_write(pool_file, json.dumps({"cutoff": f"{CUTOFF:%Y-%m-%d}", "rule": "spike/INSURANCE-RULE.md",
                                                        "pool": pool, "protocol_contracts_dropped": dropped}, indent=1))
    print(f"pool of {len(pool)} picked ({dropped} protocol contracts dropped); capturing, requests so far {len(api.log)}", flush=True)
    with ThreadPoolExecutor(WORKERS) as ex:
        for s in ex.map(sample_capture.capture_wallet, pool):
            print(json.dumps(s), flush=True)
    print("total requests this run:", len(api.log))


if __name__ == "__main__":
    sys.exit(main())
