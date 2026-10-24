"""Draw the 50 Markets for Edvard's blind hand labels (PRD FR-19, spine AD-16; 2026-10-24).

Rule: from each of the 10 Sample Dataset Wallets (spike/raw/sample/picked.json, not the spares), 5 Markets
drawn with a fixed seed from the Markets in its captured positions lists that Gamma says are resolved
(closed, outcome prices exactly 0 and 1). No Market twice; a Wallet with fewer than 5 is topped up from the
next Wallet's draw. Only the question text is written out: no keyword label, no model label, no category or
tag field, so the labels are blind (Edvard, 2026-10-24).

Never writes the shared Gamma cache (the insurance run uses it). Read-only, a few Gamma requests,
paced so the total with the insurance run stays at 5 per second.
Output: sample_data/hand_labels/markets.csv (columns n, condition_id, question, domain; domain left empty).
"""
import csv
import json
import random
from pathlib import Path

import api
from api import GAMMA
from sample_pick import OUT, fetch, resolved

api.DELAY = 2.0
SEED, PER_WALLET, TOTAL = 20261024, 5, 50
OUTFILE = Path(__file__).resolve().parent.parent / "sample_data" / "hand_labels" / "markets.csv"


def main():
    pick = json.loads((OUT / "picked.json").read_text(encoding="utf8"))
    rng = random.Random(SEED)
    chosen, questions = [], {}
    for k, w in enumerate(sorted(pick["sample"])):
        pos = json.loads((OUT / "capture" / w / "positions.json").read_text(encoding="utf8"))
        conds = sorted({r["condition_id"] for r in pos["closed"] + pos["open"]} - set(chosen))
        rng.shuffle(conds)
        want = PER_WALLET * (k + 1) - len(chosen)    # 5 per Wallet, topping up an earlier Wallet's shortfall
        for i in range(0, len(conds), 20):
            if want <= 0:
                break
            batch = conds[i:i + 20]
            ms = fetch(GAMMA, "/markets", [("condition_ids", c) for c in batch] + [("closed", "true"), ("limit", 100)])
            ok = {m["conditionId"]: m for m in ms if resolved(m)}
            for c in batch:                     # keep the shuffled order, so the draw is the seeded one
                if want > 0 and c in ok:
                    chosen.append(c)
                    questions[c] = (ok[c].get("question") or "").strip()
                    want -= 1
    assert len(chosen) == TOTAL, len(chosen)
    OUTFILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTFILE.open("w", newline="", encoding="utf8") as f:
        wr = csv.writer(f)
        wr.writerow(["n", "condition_id", "question", "domain"])
        for n, c in enumerate(chosen, 1):
            wr.writerow([n, c, questions[c], ""])
    print(f"{len(chosen)} Markets written to {OUTFILE} ({len(api.log)} requests)")


if __name__ == "__main__":
    main()
