"""Q1 trimmed samples (committed): no names, bios or images; only the fields the plan needs."""
import json
from api import RAW
S = __import__("pathlib").Path(__file__).parent / "samples"
tr = json.loads((RAW / "q1_typical_trades.json").read_text())
cl = json.loads((RAW / "q1_typical_closed.json").read_text())
fee = lambda r: abs(r["usdcSize"] - r["size"] * r["price"]) > 0.001
keep_c = ("proxyWallet", "conditionId", "asset", "outcome", "avgPrice", "totalBought", "realizedPnl", "curPrice", "timestamp", "endDate")
keep_t = ("proxyWallet", "conditionId", "asset", "type", "side", "size", "usdcSize", "price", "timestamp", "transactionHash")
split_like = next(p for p in cl if p["avgPrice"] == 0.5 and p["realizedPnl"] == 0)
lost = next(p for p in cl if p["curPrice"] == 0)
won = next(p for p in cl if p["curPrice"] == 1)
(S / "q1_closed_positions.json").write_text(json.dumps([{k: p[k] for k in keep_c} for p in (won, lost, split_like)], indent=1))
buy_fee = next(r for r in tr if fee(r) and r["side"] == "BUY"); sell_fee = next(r for r in tr if fee(r) and r["side"] == "SELL")
plain = next(r for r in tr if not fee(r))
(S / "q1_activity_trades.json").write_text(json.dumps([{k: r[k] for k in keep_t} for r in (plain, buy_fee, sell_fee)], indent=1))
fm = json.loads((RAW / "q1_fee_market.json").read_text())
(S / "q1_gamma_fee_market.json").write_text(json.dumps({k: fm[k] for k in ("conditionId", "question", "closedTime", "feesEnabled", "feeType", "feeSchedule")}, indent=1))
print("ok")
