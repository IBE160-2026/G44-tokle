"""Q1: which closed markets carry fees over time, and what do the fee schedules look like? (Gamma /markets)"""
import json, collections
from api import get, GAMMA, RAW

months = [("2025-06-01", "2025-07-01"), ("2025-10-01", "2025-11-01"), ("2026-01-01", "2026-02-01"),
          ("2026-04-01", "2026-05-01"), ("2026-07-01", "2026-08-01"), ("2026-09-15", "2026-10-15")]
example, schedules = None, {}
for a, b in months:
    s, ms, _ = get(GAMMA, "/markets", {"closed": "true", "end_date_min": a + "T00:00:00Z", "end_date_max": b + "T00:00:00Z",
                                       "order": "volumeNum", "ascending": "false", "limit": 100})
    print(a, "->", s, len(ms), dict(collections.Counter((m.get("feesEnabled"), m.get("feeType")) for m in ms)))
    for m in ms:
        if m.get("feesEnabled"):
            example = example or m
            schedules.setdefault(m["feeType"], m.get("feeSchedule"))
print("\nfee schedules seen:")
for k, v in schedules.items():
    print(" ", k, v)
if example:
    (RAW / "q1_fee_market.json").write_text(json.dumps(example))
