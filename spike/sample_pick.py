"""Sample Dataset pick (2026-10-21): a leak-free shortlist of real Wallets for PRD §9 Q5/Q6 (FR-12).

Rule (Edvard, 2026-10-21): candidates are picked on what they looked like BEFORE the Cut-off Date
only. Nothing after the date is used to pick, rank or describe them, except two activity counts that
FR-12 needs (bets opened after the date, and whether any of them paid fees). Those are counts, never
results, and are labelled as such in the table.

Method, mirroring the Scan funnel (PRD FR-16, spine AD-21, AD-9) instead of today's leaderboard
(today's leaderboard shows only Wallets that are still winning today, which is after-the-date
information):
  1. Markets resolved in the 90 days before the cut-off, top 100 by volume (Gamma).
  2. Candidates: every Wallet in those Markets' CLOSED and OPEN position lists (Data API v2).
     A Market read that hits the page cap gives no candidates (as AD-9).
  3. Pre-filter per candidate on those Markets only: sum of PnL (CLOSED realized_pnl,
     OPEN resolved value minus cost), and how many of the 100 Markets it held.
  4. A seeded, stratified draw of about 60 candidates (not just the top earners).
  5. Each drawn Wallet's before part: its latest 2,000 Positions in Markets that Gamma says
     resolved before the cut-off. Outcomes are read only for those Markets.
  6. A rough Skill Test estimate on the before part (independent draws, no linked bets, no fee
     handling), so the shortlist can cover each Verdict. The app's real Skill Test will differ.

Read-only, public endpoints, no keys, 4 requests per second (PRD s8 allows up to 5).
Outputs in spike/raw/sample/ (git-ignored). Re-runs reuse saved responses.
"""
import json
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

import api
from api import DATA, GAMMA, RAW

api.DELAY = 0.25
CUTOFF = datetime(2025, 7, 1, tzinfo=timezone.utc)            # 00:00 UTC (spine AD-7)
C = int(CUTOFF.timestamp())
DAY = 86400
OUT = RAW / "sample"
OUT.mkdir(parents=True, exist_ok=True)
MARKET_PAGES = 15        # cap per Market and status (1,000 rows a page)
WINDOW = 2000            # spine AD-8
SEED = 44


def fetch(base, path, params, tries=5):
    for i in range(tries):
        s, d, _ = api.get(base, path, params)
        if s == 200:
            return d
        if s in (429, 500, 502, 503, 504) or s is None:
            time.sleep(2 * (i + 1))
            continue
        if base == GAMMA and s in (403, 404) and not d:
            # Gamma outage 2026-10-21 15:35-15:37 UTC: every route answered an empty 404 (CloudFront)
            time.sleep(60)
            continue
        raise RuntimeError(f"{s} {path} {str(d)[:200]}")
    raise RuntimeError(f"gave up {path}")


def cached(name, fn):
    p = OUT / name
    if p.exists():
        return json.loads(p.read_text(encoding="utf8"))
    data = fn()
    p.write_text(json.dumps(data), encoding="utf8")
    return data


def ts(iso):
    return int(datetime.fromisoformat(iso.replace(" ", "T").replace("+00", "+00:00").replace("Z", "+00:00")).timestamp())


def resolved(m):
    """Spine AD-7: closed, outcome prices exactly {0, 1}, has closedTime."""
    try:
        prices = sorted(float(x) for x in json.loads(m.get("outcomePrices") or "[]"))
    except ValueError:
        return False
    return bool(m.get("closed")) and bool(m.get("closedTime")) and prices == [0.0, 1.0]


# ---- 1. funnel Markets ------------------------------------------------------------------------
def funnel_markets():
    got, offset = [], 0
    lo, hi = C - 90 * DAY, C
    while len(got) < 100 and offset < 5000:
        page = fetch(GAMMA, "/markets", {
            "closed": "true", "order": "volumeNum", "ascending": "false", "limit": 100, "offset": offset,
            "end_date_min": datetime.fromtimestamp(lo - 120 * DAY, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_date_max": datetime.fromtimestamp(hi + 400 * DAY, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        if not page:
            break
        for m in page:
            if resolved(m) and lo <= ts(m["closedTime"]) < hi:
                got.append({k: m.get(k) for k in ("conditionId", "question", "closedTime", "volumeNum", "negRiskMarketID")})
        offset += 100
    return got[:100]


# ---- 2. Market-anchored candidate lists -------------------------------------------------------
def market_rows(cond):
    out = {"partial": False, "rows": []}
    for status in ("CLOSED", "OPEN"):
        cursor, pages = None, 0
        while True:
            p = {"condition": cond, "status": status, "limit": 1000, "sort_by": "TIMESTAMP", "sort_direction": "ASC"}
            if cursor:
                p["cursor"] = cursor
            d = fetch(DATA, "/v2/positions", p)
            for r in d.get("data") or []:
                out["rows"].append([r["proxy_wallet"], status, r.get("realized_pnl") or 0, r.get("current_size") or 0,
                                    r.get("current_price") or 0, r.get("avg_price") or 0])
            pages += 1
            pg = d.get("pagination") or {}
            if not pg.get("has_more"):
                break
            if pages >= MARKET_PAGES:
                out["partial"] = True
                break
            cursor = pg.get("next_cursor")
    return out


# ---- 5. a Wallet's positions and Gamma resolution data ----------------------------------------
GAMMA_CACHE_P = OUT / "gamma_cache.json"
gamma_cache = json.loads(GAMMA_CACHE_P.read_text(encoding="utf8")) if GAMMA_CACHE_P.exists() else {}


def gamma_lookup(conds):
    need = [c for c in dict.fromkeys(conds) if c not in gamma_cache]
    for i in range(0, len(need), 50):
        batch = need[i:i + 50]
        ms = fetch(GAMMA, "/markets", [("condition_ids", c) for c in batch] + [("closed", "true"), ("limit", 100)])
        found = {m["conditionId"]: m for m in ms}
        for c in batch:
            m = found.get(c)
            gamma_cache[c] = None if not m or not resolved(m) else {
                "closed": ts(m["closedTime"]), "yes_won": float(json.loads(m["outcomePrices"])[0]) == 1.0,
                "neg": m.get("negRiskMarketID"), "q": (m.get("question") or "")[:90],
                "slug": ((m.get("events") or [{}])[0].get("slug") or "")}
    GAMMA_CACHE_P.write_text(json.dumps(gamma_cache), encoding="utf8")


def wallet_rows(w):
    """CLOSED newest-first up to C+30 days (late redeemers), until enough rows end before C; OPEN in full."""
    rows, capped = [], False
    cursor, pages, before = None, 0, 0
    while True:
        p = {"user": w, "status": "CLOSED", "limit": 1000, "sort_by": "TIMESTAMP", "sort_direction": "DESC", "end": C + 30 * DAY}
        if cursor:
            p["cursor"] = cursor
        d = fetch(DATA, "/v2/positions", p)
        page = d.get("data") or []
        rows += page
        before += sum(r["last_event_at"] < C for r in page)
        pages += 1
        pg = d.get("pagination") or {}
        if not pg.get("has_more") or before >= WINDOW + 500:
            break
        if pages >= 15:
            capped = True
            break
        cursor = pg.get("next_cursor")
    cursor, pages = None, 0
    while True:
        p = {"user": w, "status": "OPEN", "limit": 1000}
        if cursor:
            p["cursor"] = cursor
        d = fetch(DATA, "/v2/positions", p)
        rows += d.get("data") or []
        pages += 1
        pg = d.get("pagination") or {}
        if not pg.get("has_more"):
            break
        if pages >= 10:
            capped = True
            break
        cursor = pg.get("next_cursor")
    # after-the-date ACTIVITY COUNT only (FR-12 needs Positions on both sides): one page, no outcomes read
    d = fetch(DATA, "/v2/positions", {"user": w, "status": "CLOSED", "limit": 1000, "sort_by": "TIMESTAMP",
                                       "sort_direction": "ASC", "start": C})
    after_closed = d.get("data") or []
    after_more = bool((d.get("pagination") or {}).get("has_more"))
    return {"rows": rows, "capped": capped, "after_closed": after_closed, "after_more": after_more}


DOMAINS = [("sports", "nba nfl mlb nhl epl ucl uefa fifa soccer football tennis ufc f1 grand-prix golf cricket"
            " champions league premier serie bundesliga laliga wnba ncaa super-bowl stanley world-series match vs- -vs-"
            " win-on game-"),
           ("crypto", "bitcoin btc eth ethereum solana crypto xrp doge memecoin coin token"),
           ("politics", "election trump president senate house governor mayor prime-minister biden harris"
            " poll party parliament pope chancellor cabinet tariff fed- -fed nominee vote")]


def domain(slug, q):
    s = (slug + " " + q.lower().replace(" ", "-"))
    for name, words in DOMAINS:
        if any(k in s for k in words.split()):
            return name
    return "other"


def profile(w, data):
    held = [r for r in data["rows"] if (r.get("total_size") or 0) > 0]
    gamma_lookup([r["condition_id"] for r in held])
    pos = {}
    for r in held:
        g = gamma_cache.get(r["condition_id"])
        if not g or g["closed"] >= C:          # outcome read only for Markets resolved before the cut-off
            continue
        won = g["yes_won"] if r.get("outcome_index") == 0 else not g["yes_won"]
        pos[r["token_id"]] = {"s": r["total_size"], "p": r["avg_price"], "o": 1 if won else 0, "t": g["closed"],
                              "first": r.get("first_entry_at") or 0, "neg": g["neg"], "dom": domain(g["slug"], g["q"]),
                              "cond": r["condition_id"], "lost_unredeemed": r["status"] != "CLOSED" and not won}
    allpos = sorted(pos.values(), key=lambda x: -x["t"])
    window = allpos[:WINDOW]
    n = len(window)
    res = {"wallet": w, "n_before": n, "n_before_seen": len(allpos), "capped_read": data["capped"]}
    if n:
        # whole cents, so a simulation equal to the real result counts as a tie (found 2026-10-21: float sum()
        # and += round differently, which turned a p of about 0.74 into 0.0002)
        cents = [(round(x["s"] * (1 - x["p"]) * 100), round(-x["s"] * x["p"] * 100), x["p"]) for x in window]
        real_c = sum(win if x["o"] else lose for (win, lose, _), x in zip(cents, window))
        real = real_c / 100
        exp = sum(x["p"] for x in window)
        wins = sum(x["o"] for x in window)
        rng = random.Random(SEED)
        sims, beat = 4000, 0
        for _ in range(sims):
            sim = 0
            for win, lose, p in cents:
                sim += win if rng.random() < p else lose
            beat += sim >= real_c
        pval = (beat + 1) / (sims + 1)
        conds = Counter(x["cond"] for x in window)
        negs = Counter(x["neg"] for x in window if x["neg"])
        res.update({
            "pnl_before": round(real), "wins": wins, "expected_wins": round(exp, 1),
            "median_entry": round(statistics.median(x["p"] for x in window), 2),
            "median_stake": round(statistics.median(x["s"] * x["p"] for x in window)),
            "p_est": round(pval, 4) if n >= 30 else None,
            "verdict_est": "Not enough data" if n < 30 else "Skilled (high)" if pval < 0.01 else "Likely skilled" if pval < 0.05 else "No evidence",
            "first_bet": datetime.fromtimestamp(min(x["first"] for x in window), timezone.utc).strftime("%Y-%m"),
            "domains": dict(Counter(x["dom"] for x in window).most_common()),
            "linked_share": round(sum(1 for x in window if conds[x["cond"]] > 1 or (x["neg"] and negs[x["neg"]] > 1)) / n, 2),
            "unredeemed_losers": sum(x["lost_unredeemed"] for x in window),
            "maybe_split": sum(1 for x in window if abs(x["p"] - 0.5) < 1e-9),
        })
    # after part: counts only (first buy on or after the cut-off); no outcome, price or PnL is read
    after_tokens = {r["token_id"] for r in data["after_closed"] + data["rows"] if (r.get("first_entry_at") or 0) >= C}
    fee_tokens = {r["token_id"] for r in data["after_closed"] + data["rows"]
                  if (r.get("first_entry_at") or 0) >= C and (r.get("entry_fees_usdc") or 0) > 0}
    res["n_after_count"] = len(after_tokens)
    res["n_after_more"] = data["after_more"]
    res["after_paid_fees"] = len(fee_tokens) > 0
    return res


def main():
    markets = cached(f"funnel_markets_{CUTOFF:%Y%m%d}.json", funnel_markets)
    print(f"cut-off {CUTOFF:%Y-%m-%d}: {len(markets)} funnel Markets, volume {markets[-1]['volumeNum']:,.0f} .. {markets[0]['volumeNum']:,.0f}")
    cand = defaultdict(lambda: {"markets": 0, "pnl": 0.0})
    used = 0
    for i, m in enumerate(markets):
        mr = cached(f"market_{m['conditionId'][:18]}.json", lambda: market_rows(m["conditionId"]))
        if mr["partial"]:
            continue
        used += 1
        seen = set()
        for w, st, rp, cs, cp, ap in mr["rows"]:
            c = cand[w]
            if w not in seen:
                c["markets"] += 1
                seen.add(w)
            c["pnl"] += rp if st == "CLOSED" else cs * (cp - ap)
        if i % 10 == 9:
            print(f"  read {i + 1} Markets, {len(cand):,} candidates so far, requests {len(api.log)}", flush=True)
    print(f"Markets used {used} of {len(markets)} (others hit the page cap); candidates {len(cand):,}")
    # 4. seeded stratified draw: what a Scan would pick, plus active, losing, middling and casual Wallets
    rng = random.Random(SEED)
    ws = sorted(cand, key=lambda w: (-cand[w]["pnl"], w))
    pick = {}
    def take(label, pool, k):
        pool = [w for w in pool if w not in pick]
        for w in (pool[:k] if label == "top" else rng.sample(pool, min(k, len(pool)))):
            pick[w] = label
    take("top", ws, 15)
    take("active", [w for w in ws if cand[w]["markets"] >= 5], 15)
    take("loser", [w for w in ws if cand[w]["pnl"] < -1000], 10)
    take("middle", [w for w in ws if 2 <= cand[w]["markets"] <= 4], 10)
    take("any", ws, 10)
    # second draw (2026-10-21): the first 59 gave one Skilled and no Likely skilled estimate; still before-only
    take("top2", ws[15:55], 25)
    take("heavy", [w for w in ws if cand[w]["markets"] >= 10], 15)
    print("drawn:", Counter(pick.values()))
    results = json.loads((OUT / f"profiles_{CUTOFF:%Y%m%d}.json").read_text()) if (OUT / f"profiles_{CUTOFF:%Y%m%d}.json").exists() else {}
    for j, (w, label) in enumerate(pick.items()):
        if w in results:
            continue
        try:
            data = cached(f"wallet_{w[:12]}.json", lambda: wallet_rows(w))
        except RuntimeError as e:
            if "protocol contract" not in str(e):
                raise
            # found 2026-10-21: Market position lists include Polymarket's own contracts; v2 refuses them as a user
            results[w] = {"wallet": w, "stratum": label, "excluded": "protocol contract"}
            print(f"  {j + 1}/{len(pick)} {w[:10]} {label}: excluded, protocol contract", flush=True)
            continue
        if "--rows-only" in sys.argv:      # Gamma outage 2026-10-21: fetch Data API rows now, profile later
            print(f"  {j + 1}/{len(pick)} {w[:10]} rows saved", flush=True)
            continue
        r = profile(w, data)
        r.update({"stratum": label, "funnel_markets": cand[w]["markets"], "funnel_pnl": round(cand[w]["pnl"])})
        results[w] = r
        (OUT / f"profiles_{CUTOFF:%Y%m%d}.json").write_text(json.dumps(results, indent=1), encoding="utf8")
        print(f"  {j + 1}/{len(pick)} {w[:10]} {label}: before {r['n_before']} {r.get('verdict_est')} pnl {r.get('pnl_before')} "
              f"after-count {r['n_after_count']}{'+' if r['n_after_more'] else ''} | requests {len(api.log)}", flush=True)
    print("total requests this run:", len(api.log))


if __name__ == "__main__":
    sys.exit(main())
