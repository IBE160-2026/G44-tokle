"""Q3 probe 1: minute-level price history for resolved markets, by age. Windows are +-1h around a real trade of the typical wallet."""
import json, datetime as dt, bisect
from api import get, CLOB, RAW
tr = json.loads((RAW / "q1_typical_trades.json").read_text())
f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
targets = ["2024-08-10", "2025-01-15", "2025-07-01", "2026-01-15", "2026-06-15", "2026-09-20"]
for day in targets:
    t0 = int(dt.datetime.fromisoformat(day + "T00:00:00+00:00").timestamp())
    r = min((x for x in tr if x["timestamp"] >= t0), key=lambda x: x["timestamp"])
    ts = r["timestamp"]
    out = {}
    for fid in (1, 5, 60):
        s, d, _ = get(CLOB, "/prices-history", {"market": r["asset"], "startTs": ts - 3600, "endTs": ts + 3600, "fidelity": fid})
        h = d.get("history", []) if isinstance(d, dict) else []
        out[fid] = (s, len(h), h)
        if fid == 1 and len(h) > 10: break
    desc = []
    for fid, (s, n, h) in out.items():
        near = min(h, key=lambda p: abs(p["t"] - ts)) if h else None
        desc.append(f"fid={fid}: {s}, {n} pts" + (f", nearest {abs(near['t'] - ts)}s away, hist {near['p']:.4f}" if near else (f" {str(d)[:80]}" if s != 200 else "")))
    print(f"{f(ts)} | trade {r['side']} @ {r['price']} | " + " | ".join(desc), flush=True)
