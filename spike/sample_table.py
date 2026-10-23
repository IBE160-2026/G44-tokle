"""Print the profiled candidates (sample_pick.py output) as one table, before-the-cut-off numbers only.

Columns from the before part: Resolved Positions (latest 2,000), rough p-value and Verdict estimate,
PnL, wins vs expected wins, median entry price and stake, main domain, linked-bet share, unredeemed
losers, possible splits. From the after part, counts only: bets opened on or after the cut-off and
whether any paid fees. Addresses are shortened on purpose: a known name is later knowledge.
"""
import json
import sys

from sample_pick import CUTOFF, OUT

rows = json.loads((OUT / f"profiles_{CUTOFF:%Y%m%d}.json").read_text(encoding="utf8"))
only = set(sys.argv[1:])
print("| # | Wallet | Drawn as | Before: positions | Est. Verdict (p) | Before PnL $ | Wins / expected | Median entry | Median stake $ | Main domain | Linked | Unredeemed losers | Split-like | After: bets opened (count) | After fees |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for i, (w, r) in enumerate(sorted(rows.items(), key=lambda kv: (kv[1].get("p_est") is None, kv[1].get("p_est") or 1, kv[0]))):
    if only and w[:8] not in only:
        continue
    if r.get("excluded"):
        print(f"| {i + 1} | {w[:8]}… | {r['stratum']} | excluded: {r['excluded']} |" + " |" * 11)
        continue
    n = r["n_before"]
    dom = r.get("domains") or {}
    main = max(dom, key=dom.get) if dom else "-"
    share = f"{main} {dom[main] / n:.0%}" if dom else "-"
    p = f"{r['verdict_est']} ({r['p_est']})" if r.get("p_est") is not None else r.get("verdict_est", "Not enough data")
    after = f"{r['n_after_count']}{'+' if r['n_after_more'] else ''}"
    print(f"| {i + 1} | {w[:8]}… | {r['stratum']} | {n}{' (cap)' if n >= 2000 else ''}{' *' if r['capped_read'] else ''} | {p} | "
          f"{r.get('pnl_before', 0):,} | {r.get('wins', '-')} / {r.get('expected_wins', '-')} | {r.get('median_entry', '-')} | "
          f"{r.get('median_stake', '-')} | {share} | {r.get('linked_share', '-')} | {r.get('unredeemed_losers', '-')} | "
          f"{r.get('maybe_split', '-')} | {after} | {'yes' if r['after_paid_fees'] else 'no'} |")
