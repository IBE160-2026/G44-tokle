"""Save small trimmed samples for Q2 (committed). Trims profile fields; keeps the fields the plan needs."""
import json
from api import get, DATA, RAW
S = __import__("pathlib").Path(__file__).parent / "samples"
S.mkdir(exist_ok=True)

s, lb, _ = get(DATA, "/v1/leaderboard", {"timePeriod": "ALL", "orderBy": "PNL", "limit": 2})
keep = ("rank", "proxyWallet", "vol", "pnl")
(S / "q2_leaderboard.json").write_text(json.dumps([{k: r[k] for k in keep} for r in lb], indent=1))

ms = json.loads((RAW / "q2_gamma_june.json").read_text("utf8"))[:2]
keep = ("conditionId", "question", "closed", "closedTime", "endDate", "volumeNum", "feesEnabled", "feeType", "clobTokenIds", "outcomes", "outcomePrices")
(S / "q2_gamma_markets.json").write_text(json.dumps([{k: m.get(k) for k in keep} for m in ms], indent=1))

s, t, _ = get(DATA, "/trades", {"market": ms[0]["conditionId"], "limit": 3, "end": 1750000000})
keep = ("proxyWallet", "side", "size", "price", "timestamp", "outcome", "conditionId", "transactionHash")
(S / "q2_trades.json").write_text(json.dumps([{k: r[k] for k in keep} for r in t], indent=1))
print("ok", [p.name for p in S.iterdir()])
