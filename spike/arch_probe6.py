"""Architecture probe 6 (2026-10-21): where does a Wallet's own fee live in v2, and is it already inside avg_price?

Real PnL is net of the Wallet's own fees (PRD, decided 2026-10-21). If avg_price already
includes the fee, subtracting entry_fees_usdc again would count the fee twice.
For each fee-paying closed Position of the typical wallet (1 request), compare:
  entry_cost_usdc  vs  total_size * avg_price  (+ entry_fees_usdc?)
  realized_pnl     vs  a rebuild with and without the fee.
Fees in the v1 trade rows (usdcSize - size*price, BUY side) are shown as the independent check.
"""
import json
from collections import defaultdict
from api import get, DATA, RAW

W = json.loads((RAW / "q1_wallets.json").read_text())["typical"]
s, d, _ = get(DATA, "/v2/positions", {"user": W, "status": "CLOSED", "limit": 1000})
pos = d["data"]
tr = json.loads((RAW / "q1_typical_trades.json").read_text())
buy_fee, sold = defaultdict(float), defaultdict(float)
for r in tr:
    if r["side"] == "BUY":
        buy_fee[r["asset"]] += r["usdcSize"] - r["size"] * r["price"]
print(f"{len(pos)} closed rows; fields used: total_size, avg_price, entry_cost_usdc, entry_fees_usdc, total_cost_usdc, realized_pnl, current_price")
for p in [p for p in pos if (p.get("entry_fees_usdc") or 0) > 0 or buy_fee.get(p["token_id"], 0) > 0.001]:
    size, avg, fee = p["total_size"], p["avg_price"], p.get("entry_fees_usdc") or 0
    payout = size * (p.get("current_price") or 0)
    print(f"- size {size:.2f} avg {avg:.4f} | entry_cost {p.get('entry_cost_usdc')} total_cost {p.get('total_cost_usdc')} "
          f"size*avg {size * avg:.4f} | fee v2 {fee:.4f} fee v1-rows {buy_fee.get(p['token_id'], 0):.4f} | "
          f"realized {p.get('realized_pnl')} rebuild no-fee {payout - size * avg:.4f} minus-fee {payout - size * avg - fee:.4f}")
