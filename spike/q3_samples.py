"""Q3 trimmed sample (committed): a few one-minute points of /prices-history for a resolved market."""
import json
from api import get, CLOB, RAW
S = __import__("pathlib").Path(__file__).parent / "samples"
r = next(x for x in json.loads((RAW / "q1_typical_trades.json").read_text()) if x["timestamp"] > 1768000000)
params = {"market": r["asset"], "startTs": r["timestamp"] - 180, "endTs": r["timestamp"] + 180, "fidelity": 1}
s, d, _ = get(CLOB, "/prices-history", params)
(S / "q3_prices_history.json").write_text(json.dumps({"request": params, "trade_timestamp": r["timestamp"], "trade_price": r["price"], "trade_side": r["side"], "history_first_8": d["history"][:8], "points_returned": len(d["history"])}, indent=1))
print(s, len(d["history"]))
