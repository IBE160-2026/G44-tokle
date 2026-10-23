"""Add two before-part checks to the shortlist (2026-10-21, 0 requests, saved data only).

The rough estimate in sample_pick.py treats every Position as held to resolution. A Wallet that sells
before resolution then gets a wrong PnL (e.g. -$21M). Two numbers show where that happens:
  api_pnl: the data source's own PnL over the same before-part Positions;
  held_share: the share of those Positions whose own PnL matches holding to resolution (within 1%).
The app leaves fully sold Positions out (PRD FR-3, spine AD-11), so a low held_share means the app's
Verdict will rest on fewer Positions than the "Before: positions" column.
"""
import json
import random

from sample_pick import C, CUTOFF, OUT, WINDOW, gamma_cache

prof = json.loads((OUT / f"profiles_{CUTOFF:%Y%m%d}.json").read_text(encoding="utf8"))
for w, r in prof.items():
    f = next(OUT.glob(f"wallet_{w[:12]}.json"), None)
    if r.get("excluded") or not f:
        continue
    rows = [x for x in json.loads(f.read_text(encoding="utf8"))["rows"] if (x.get("total_size") or 0) > 0]
    pos = {}
    for x in rows:
        g = gamma_cache.get(x["condition_id"])
        if g and g["closed"] < C:
            won = g["yes_won"] if x.get("outcome_index") == 0 else not g["yes_won"]
            api = x.get("realized_pnl") if x["status"] == "CLOSED" else x.get("total_pnl")
            pos[x["token_id"]] = (g["closed"], api or 0, x["total_size"] * ((1 if won else 0) - x["avg_price"]), x["total_size"] * x["avg_price"],
                                  x["total_size"], x["avg_price"], 1 if won else 0)
    win = sorted(pos.values(), key=lambda v: -v[0])[:WINDOW]
    if win:
        r["api_pnl"] = round(sum(v[1] for v in win))
        held = [v for v in win if abs(v[1] - v[2]) <= 0.01 * v[3] + 1]
        r["held_share"] = round(len(held) / len(win), 2)
        # the rough Skill Test again, on held-to-the-end Positions only (closest to the app's exclusions), whole cents
        cents = [(round(v[4] * (1 - v[5]) * 100), round(-v[4] * v[5] * 100), v[5], v[6]) for v in held]
        real = sum(a if o else b for a, b, _, o in cents)
        rng, beat = random.Random(44), 0
        for _ in range(4000):
            beat += sum(a if rng.random() < q else b for a, b, q, _ in cents) >= real
        r["n_held"], r["pnl_held"] = len(held), round(real / 100)
        r["p_held"] = round((beat + 1) / 4001, 4) if len(held) >= 30 else None
        r["verdict_held"] = ("Not enough data" if len(held) < 30 else "Skilled (high)" if r["p_held"] < 0.01
                             else "Likely skilled" if r["p_held"] < 0.05 else "No evidence")
(OUT / f"profiles_{CUTOFF:%Y%m%d}.json").write_text(json.dumps(prof, indent=1), encoding="utf8")
for w, r in prof.items():
    if r.get("api_pnl") is not None and (r.get("n_before") or 0) >= 30:
        print(w[:8], r["n_before"], r["n_held"], r["verdict_held"], r["p_held"], r["pnl_held"], "api", r["api_pnl"])
