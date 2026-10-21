"""Q1 probe 2: full history of the 'typical' wallet. Does /activity cut off? Are identical rows separate fills?"""
import json, collections
from api import get, DATA, RAW, log

W = json.loads((RAW / "q1_wallets.json").read_text())["typical"]

def all_closed(w):
    rows, off = [], 0
    while True:
        s, d, _ = get(DATA, "/closed-positions", {"user": w, "limit": 50, "offset": off, "sortBy": "TIMESTAMP", "sortDirection": "DESC"})
        if s != 200 or not d: break
        rows += d; off += 50
    return rows

def all_trades(w):
    """Page /activity type=TRADE newest first; when offset hits the cap, restart with end= oldest timestamp seen."""
    rows, end, windows = [], None, 0
    while True:
        windows += 1
        got_in_window = 0
        for off in range(0, 5001, 500):
            p = {"user": w, "type": "TRADE", "limit": 500, "offset": off, "start": 1}
            if end: p["end"] = end
            s, d, _ = get(DATA, "/activity", p)
            if s != 200: print("  stop", s, str(d)[:100]); return rows, windows
            rows += d; got_in_window += len(d)
            if len(d) < 500: return rows, windows
        end = min(r["timestamp"] for r in rows[-500:])   # next window ends at oldest second seen (boundary rows overlap)
        print(f"  window {windows} full ({got_in_window} rows), next end={end}", flush=True)

closed = all_closed(W)
print("closed positions:", len(closed), "| requests so far", len(log), flush=True)
(RAW / "q1_typical_closed.json").write_text(json.dumps(closed))
trades, windows = all_trades(W)
print("trade rows fetched (before boundary dedupe):", len(trades), "windows:", windows, "| requests", len(log))
(RAW / "q1_typical_trades.json").write_text(json.dumps(trades))
