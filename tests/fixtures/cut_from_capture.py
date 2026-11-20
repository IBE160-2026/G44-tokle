"""Cut the Story 2.2 test fixtures from the raw Sample Dataset capture (AD-17).

The capture (`spike/raw/sample/capture/`, git-ignored; backup zip outside the repository, see
`spike/FINDINGS.md`) holds each Wallet's positions lists and activity rows as the Data API sent
them. It holds no Gamma records: the 5 Nov 2026 rule kept Gamma reads off the Sample Wallets until
Edvard's Domain definitions and hand labels were committed, which they now are. So this script
fetches the real Gamma records for the two fixture Wallets' Markets once (read-only, public, no
keys, about 10 requests; Edvard, 2026-11-20) and keeps them raw next to the capture.

    uv run python tests/fixtures/cut_from_capture.py fetch-gamma   # network: Gamma only, once
    uv run python tests/fixtures/cut_from_capture.py cut           # no network: writes tests/fixtures/capture/

`cut` keeps only the fields the client reads, in the API's own shape, so the tests run the real
parsers on real rows through a fake transport. Same capture and Gamma files give the same bytes.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "spike" / "raw" / "sample" / "capture"
GAMMA_RAW = ROOT / "spike" / "raw" / "sample" / "gamma_fixture"
OUT = Path(__file__).resolve().parent / "capture"

# Two small real Sample Wallets: one clean (24 Positions), one with fees, OPEN rows, a CONVERSION
# and a combo row (66 Markets). Both are in the committed list of Sample Wallets (spike/FINDINGS.md).
WALLETS = {
    "0x29306ddc4724e24a23bf1c8679aa034376ea9dcb": "small-clean",
    "0x0915962b4c6bc4505e7434a0de815a596a6667c3": "fees-and-open",
}

POSITION_KEYS = ("condition_id", "token_id", "total_size", "first_entry_at", "last_event_at")
ACTIVITY_KEYS = ("type", "condition_id", "timestamp", "size", "usdc_size", "price", "token_id", "side", "is_combo")
GAMMA_KEYS = (
    "conditionId", "closed", "closedTime", "startDate", "clobTokenIds", "outcomePrices", "feesEnabled", "feeSchedule",
)


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _condition_ids(wallet: str) -> list[str]:
    lists = _load(CAPTURE / wallet / "positions.json")
    ids = {row["condition_id"] for row in lists["closed"] + lists["open"]}
    for part in ("activity_before", "activity_after"):
        ids |= {row["condition_id"] for row in _load(CAPTURE / wallet / f"{part}.json")["rows"]}
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
    for wallet in WALLETS:
        wanted = _condition_ids(wallet)
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
    for wallet, name in WALLETS.items():
        lists = _load(CAPTURE / wallet / "positions.json")
        rows = []
        for part in ("activity_before", "activity_after"):
            rows.extend(_load(CAPTURE / wallet / f"{part}.json")["rows"])
        rows.sort(key=lambda row: row["timestamp"])  # stable: same-second rows keep the capture's order
        gamma = _load(GAMMA_RAW / f"{wallet}.json")
        document = {
            "wallet": wallet,
            "source": "spike/raw/sample/capture (Data API v2, 2026-10-23) and Gamma /markets with include_tag (2026-11-20)",
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
    return kept


if __name__ == "__main__":
    commands = {"fetch-gamma": fetch_gamma, "cut": cut}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        raise SystemExit(f"usage: python {Path(__file__).name} {{{','.join(commands)}}}")
    commands[sys.argv[1]]()
