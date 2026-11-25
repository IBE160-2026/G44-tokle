"""Cut the Story 2.2, 2.3 and 4.1 test fixtures from the raw Sample Dataset capture (AD-17).

The capture (`spike/raw/sample/capture/`, git-ignored; backup zip outside the repository, see
`spike/FINDINGS.md`) holds each Wallet's positions lists and activity rows as the Data API sent
them. It holds no Gamma records: the 5 Nov 2026 rule kept Gamma reads off the Sample Wallets until
Edvard's Domain definitions and hand labels were committed, which they now are. So this script
fetches the real Gamma records for the two fixture Wallets' Markets once (read-only, public, no
keys, about 10 requests; Edvard, 2026-11-20) and keeps them raw next to the capture. Story 2.3
adds three Wallets, cut down to a few chosen Markets each, with Gamma fetched for those Markets
only (about 10 requests; Edvard, 2026-11-21). A Wallet whose Gamma file exists is not fetched again.
Story 4.1 adds a second fixture of 0x729806, `after-part`, whose Gamma records come from the frozen
additions file next to the capture zip (`../G44-tokle-data/`, checked against its SHA-256), so it
needs no network at all.

    uv run python tests/fixtures/cut_from_capture.py fetch-gamma   # network: Gamma only, once
    uv run python tests/fixtures/cut_from_capture.py cut           # no network: writes tests/fixtures/capture/

`cut` keeps only the fields the client reads, in the API's own shape, so the tests run the real
parsers on real rows through a fake transport. Same capture and Gamma files give the same bytes.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "spike" / "raw" / "sample" / "capture"
GAMMA_RAW = ROOT / "spike" / "raw" / "sample" / "gamma_fixture"
OUT = Path(__file__).resolve().parent / "capture"
if str(ROOT / "src") not in sys.path:  # the app's own helpers (cut-off, Gamma time, SHA-256 check), inserted once
    sys.path.insert(0, str(ROOT / "src"))

# Story 2.2: two small real Sample Wallets, whole: one clean (24 Positions), one with fees, OPEN
# rows, a CONVERSION and a combo row (66 Markets). Story 2.3: three Wallets cut to chosen Markets
# (see `_chosen`): 0x729806's split and merge Markets, 0x94884d's unredeemed losers on the OPEN list
# next to winners, 0x0f4b0a's fee Markets. All are Sample Wallets or spares (spike/FINDINGS.md).
# Story 4.1: 0x729806 again, cut to Markets around the Cut-off Date (`after-part`, see `_after_part_markets`).
FIXTURES = {
    "small-clean": "0x29306ddc4724e24a23bf1c8679aa034376ea9dcb",
    "fees-and-open": "0x0915962b4c6bc4505e7434a0de815a596a6667c3",
    "split-merge": "0x7298060b1844a4c4ca0578146ab3f5e76aa1fcfc",
    "open-losers": "0x94884db79666a1a34c46d03fb4f8e9cbcaf6b5a6",
    "fees": "0x0f4b0a6b7f82108924ac9c8320ed91028f504183",
    "after-part": "0x7298060b1844a4c4ca0578146ab3f5e76aa1fcfc",
}
# The fixtures whose Gamma records come from the frozen additions file instead of `fetch-gamma`.
FROM_ADDITIONS = frozenset({"after-part"})
ADDITIONS = ROOT.parent / "G44-tokle-data" / "sample-additions-2026-11-23.json"
# Resolved Markets as the Sample capture's funnel recorded them (no fees, no token ids); used only
# to choose fixture Markets, never as data in a fixture.
GAMMA_CACHE = ROOT / "spike" / "raw" / "sample" / "gamma_cache.json"

POSITION_KEYS = ("condition_id", "token_id", "total_size", "first_entry_at", "last_event_at")
ACTIVITY_KEYS = ("type", "condition_id", "timestamp", "size", "usdc_size", "price", "token_id", "side", "is_combo")
GAMMA_KEYS = (
    "conditionId", "closed", "closedTime", "startDate", "clobTokenIds", "outcomePrices", "feesEnabled", "feeSchedule",
    "outcomes", "negRisk", "negRiskMarketID",  # AD-20 (Story 2.4)
)


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(wallet: str) -> list[dict]:
    rows: list[dict] = []
    for part in ("activity_before", "activity_after"):
        rows.extend(_load(CAPTURE / wallet / f"{part}.json")["rows"])
    return rows


def _chosen(name: str) -> set[str] | None:
    """The Markets a Story 2.3 or 4.1 fixture keeps (None: the whole Wallet), the same on every rerun.

    split-merge and open-losers take the smallest qualifying Markets (fewest activity rows, ties by id);
    fees takes every listed Market with a buy fill that paid more than $0.00001 above shares x price;
    after-part: see `_after_part_markets`.
    """
    wallet = FIXTURES[name]
    if name in ("small-clean", "fees-and-open"):
        return None
    if name == "after-part":
        return _after_part_markets(wallet)
    lists = _load(CAPTURE / wallet / "positions.json")
    rows = _rows(wallet)
    resolved = _load(GAMMA_CACHE)
    listed = {row["condition_id"] for row in lists["closed"] + lists["open"]}
    count: dict[str, int] = {}
    kinds: dict[str, set[str]] = {}
    for row in rows:
        count[row["condition_id"]] = count.get(row["condition_id"], 0) + 1
        kinds.setdefault(row["condition_id"], set()).add(row["type"])

    def smallest(ids: set[str], n: int) -> set[str]:
        return set(sorted(ids & listed & set(resolved), key=lambda c: (count.get(c, 0), c))[:n])

    plain = {c for c, k in kinds.items() if not k & {"SPLIT", "MERGE", "CONVERSION"}}
    if name == "split-merge":
        merged = {c for c, k in kinds.items() if "MERGE" in k}
        split = {c for c, k in kinds.items() if "SPLIT" in k and "TRADE" in k} - merged
        return smallest(merged, 3) | smallest(split, 3)
    if name == "open-losers":
        losers = {r["condition_id"] for r in lists["open"] if r["current_price"] == 0 and r["redeemable"]}
        winners = {
            r["condition_id"] for r in lists["closed"]
            if r["condition_id"] in resolved and resolved[r["condition_id"]]["yes_won"] == (r["outcome_index"] == 0)
        }
        return smallest(losers & plain, 5) | smallest((winners & plain) - losers, 5)
    fee_markets = {
        r["condition_id"] for r in rows
        if r["type"] == "TRADE" and r["side"] == "BUY" and r["usdc_size"] - r["size"] * r["price"] > 1e-5
    }
    return fee_markets & listed


def _after_part_markets(wallet: str) -> set[str]:
    """The Markets of the after-part fixture (Story 4.1, AD-7), all with Gamma in the additions file:

    - the Market of every token with a BUY on or after the Cut-off Date in `activity_after.json` (41 tokens;
      20 of them have an earlier `first_entry_at`, so they only look new);
    - the 3 smallest Markets (fewest activity rows, ties by id) resolved on or after the cut-off whose listed
      rows were all first entered on or after it, but with no TRADE BUY after it (they enter by CONVERSION);
    - the smallest Market Gamma closed before the cut-off whose listed rows were all first entered on or
      after it (in neither part).
    """
    cutoff = _cutoff()
    gamma = _additions_gamma()
    lists = _load(CAPTURE / wallet / "positions.json")
    rows = _rows(wallet)
    after = _load(CAPTURE / wallet / "activity_after.json")["rows"]
    bought = {r["condition_id"] for r in after if r["type"] == "TRADE" and r["side"] == "BUY" and r["timestamp"] >= cutoff}

    by_market: dict[str, list[dict]] = {}
    for row in lists["closed"] + lists["open"]:
        by_market.setdefault(row["condition_id"], []).append(row)
    count: dict[str, int] = {}
    for row in rows:
        count[row["condition_id"]] = count.get(row["condition_id"], 0) + 1
    fresh = {c for c, listed in by_market.items() if all(r["first_entry_at"] >= cutoff for r in listed) and c in gamma}
    closed_at = {c: _closed_at(gamma[c]) for c in fresh}
    bought_after = {
        r["condition_id"] for r in rows if r["type"] == "TRADE" and r.get("side") == "BUY" and r["timestamp"] >= cutoff
    }
    no_buy = {c for c in fresh - bought_after if closed_at[c] is not None and closed_at[c] >= cutoff}
    closed_before = {c for c in fresh if closed_at[c] is not None and closed_at[c] < cutoff}

    def smallest(ids: set[str], n: int) -> set[str]:
        return set(sorted(ids, key=lambda c: (count.get(c, 0), c))[:n])

    print(f"after-part: {len(no_buy)} Markets entered on or after the cut-off with no buy, "
          f"{len(closed_before)} closed before it but entered on or after it")
    return bought | smallest(no_buy, 3) | smallest(closed_before, 1)


def _closed_at(market: dict) -> int | None:
    """Gamma's resolution time of a closed Market, parsed as the app parses it (None: not closed or no time)."""
    from liquidoracle.data.polymarket import parse_time

    return parse_time(market["closedTime"]) if market.get("closed") and market.get("closedTime") else None


def _cutoff() -> int:
    """The Sample Dataset's Cut-off Date, converted where the app converts it (AD-7)."""
    from liquidoracle.data.real_sample import CUTOFF
    from liquidoracle.data.window import cutoff_at

    return cutoff_at(date.fromisoformat(CUTOFF))


@cache
def _additions_gamma() -> dict[str, dict]:
    """Every raw Gamma record in the frozen additions file, by condition id (no network; read and checked once)."""
    from liquidoracle.data.real_sample import BuildError, checked

    try:
        checked(ADDITIONS)  # the same SHA-256 check as build-sample
    except BuildError as error:
        raise SystemExit(str(error)) from None
    return {market["conditionId"]: market for market in _load(ADDITIONS)["gamma"]}


def _condition_ids(name: str) -> list[str]:
    chosen = _chosen(name)
    if chosen is not None:
        return sorted(chosen)
    wallet = FIXTURES[name]
    lists = _load(CAPTURE / wallet / "positions.json")
    ids = {row["condition_id"] for row in lists["closed"] + lists["open"]}
    ids |= {row["condition_id"] for row in _rows(wallet)}
    return sorted(ids)


def fetch_gamma() -> None:
    """Fetch the raw Gamma records of every Market the two Wallets touch, 20 per request (AD-10)."""
    # The app's own transport and URL guard: GET only, Gamma only, no keys (AD-2).
    sys.path.insert(0, str(ROOT / "src"))
    from liquidoracle.data.polymarket import GAMMA_API, GAMMA_BATCH, HEADERS, RequestsTransport, check_url

    transport = RequestsTransport()
    url = f"{GAMMA_API}/markets"
    check_url(url)
    GAMMA_RAW.mkdir(parents=True, exist_ok=True)
    for name, wallet in FIXTURES.items():
        if name in FROM_ADDITIONS or (GAMMA_RAW / f"{wallet}.json").exists():
            continue  # fetched once already, or frozen in the additions file; never asked again
        wanted = _condition_ids(name)
        found: dict[str, dict] = {}
        for i in range(0, len(wanted), GAMMA_BATCH):
            batch = wanted[i : i + GAMMA_BATCH]
            for closed in ("true", "false"):  # without `closed` Gamma returns only open Markets (Story 2.1)
                ask = [c for c in batch if c not in found]
                if not ask:
                    break
                params = [("condition_ids", c) for c in ask] + [
                    ("closed", closed), ("include_tag", "true"), ("limit", str(len(ask)))]
                reply = transport.get(url, params, HEADERS)
                if reply.status != 200:
                    raise SystemExit(f"Gamma answered {reply.status}; nothing written for {wallet}")
                for market in json.loads(reply.body):
                    if market["conditionId"] in ask:
                        found[market["conditionId"]] = market
                time.sleep(0.5)  # well under AD-3's 5 requests per second
        missing = [c for c in wanted if c not in found]
        (GAMMA_RAW / f"{wallet}.json").write_text(json.dumps([found[c] for c in wanted if c in found]), encoding="utf-8")
        print(f"{wallet}: {len(found)} of {len(wanted)} Markets from Gamma; missing {missing}")


def cut() -> None:
    """Write one fixture file per Wallet: positions lists, activity oldest first, Gamma records."""
    OUT.mkdir(parents=True, exist_ok=True)
    for name, wallet in FIXTURES.items():
        lists = _load(CAPTURE / wallet / "positions.json")
        chosen = _chosen(name)
        if chosen is not None:
            lists = {status: [r for r in lists[status] if r["condition_id"] in chosen] for status in ("closed", "open")}
        source = "spike/raw/sample/capture (Data API v2, 2026-10-23) and Gamma /markets with include_tag (2026-11-20)"
        events: set[str] = set()
        if name in FROM_ADDITIONS:
            additions = _additions_gamma()
            gamma = sorted((additions[c] for c in chosen or set() if c in additions), key=lambda m: m["conditionId"])
            # A CONVERSION row names its Market's negative-risk event, not the Market (AD-11, Story 2.4).
            events = {m["negRiskMarketID"] for m in gamma if m.get("negRiskMarketID")}
            source = ("spike/raw/sample/capture (Data API v2, 2026-10-23) and Gamma /markets with include_tag "
                      f"from {ADDITIONS.name} (2026-11-23)")
        else:
            gamma = _load(GAMMA_RAW / f"{wallet}.json")
        rows = [
            r for r in _rows(wallet)
            if chosen is None or r["condition_id"] in chosen or (r["type"] == "CONVERSION" and r["condition_id"] in events)
        ]
        rows.sort(key=lambda row: row["timestamp"])  # stable: same-second rows keep the capture's order
        missing = sorted((chosen or set()) - {market["conditionId"] for market in gamma})
        if missing:  # a stale Gamma file would drop chosen Markets out of the window without a word
            raise SystemExit(f"{name}: no Gamma record for chosen Markets {missing}; delete its Gamma file and fetch again")
        document = {
            "wallet": wallet,
            "source": source,
            "positions_closed": [_keep(row, POSITION_KEYS) for row in lists["closed"]],
            "positions_open": [_keep(row, POSITION_KEYS) for row in lists["open"]],
            "activity": [_keep(row, ACTIVITY_KEYS) for row in rows],
            "gamma": [_gamma(market) for market in gamma],
        }
        path = OUT / f"{name}.json"
        path.write_bytes((json.dumps(document, indent=1, sort_keys=True) + "\n").encode("utf-8"))
        print(f"wrote {path.relative_to(ROOT)}: {len(document['positions_closed'])} CLOSED, "
              f"{len(document['positions_open'])} OPEN, {len(rows)} activity rows, {len(gamma)} Markets")


def _keep(row: dict, keys: tuple[str, ...]) -> dict:
    return {key: row[key] for key in keys if key in row}


def _gamma(market: dict) -> dict:
    kept = _keep(market, GAMMA_KEYS)
    kept["tags"] = [{"label": tag["label"]} for tag in market.get("tags") or []]
    if "events" in market:  # only each event's id is read (AD-20)
        kept["events"] = [{"id": event["id"]} for event in market["events"]]
    return kept


if __name__ == "__main__":
    commands = {"fetch-gamma": fetch_gamma, "cut": cut}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        raise SystemExit(f"usage: python {Path(__file__).name} {{{','.join(commands)}}}")
    commands[sys.argv[1]]()
