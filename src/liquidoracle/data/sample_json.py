"""The one serializer for Sample Dataset files (AD-14).

One JSON file per Wallet, holding its activity rows, positions-list rows, Markets and price
points as `records` types. Keys are sorted, line endings are LF and files are written as bytes,
so the same Wallet gives the same bytes on every OS and Python version (FR-13). Reading is
strict: a missing or unknown key is an error, never a silent default.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from liquidoracle.records import ActivityRow, ListedPosition, Market, PricePoint, SampleWallet


def dumps(wallet: SampleWallet, *, compact: bool = False) -> str:
    """The file text for one Wallet. `compact` drops the indentation (used for the large groups)."""
    document = {
        "address": wallet.address,
        "name": wallet.name,
        "activity": [asdict(row) for row in wallet.activity],
        "positions": [asdict(row) for row in wallet.positions],
        "markets": [asdict(market) for market in wallet.markets],
        "prices": [asdict(point) for point in wallet.prices],
    }
    if compact:
        text = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    else:
        text = json.dumps(document, sort_keys=True, indent=1, allow_nan=False)
    return text + "\n"


def loads(text: str) -> SampleWallet:
    """Read one Wallet back. Raises ValueError on any malformed content."""
    try:
        document = json.loads(text)
        _check_keys(document, {"address", "name", "activity", "positions", "markets", "prices"}, "wallet")
        return SampleWallet(
            address=str(document["address"]),
            name=str(document["name"]),
            activity=tuple(_activity_row(row) for row in document["activity"]),
            positions=tuple(_listed_position(row) for row in document["positions"]),
            markets=tuple(_market(row) for row in document["markets"]),
            prices=tuple(_price_point(row) for row in document["prices"]),
        )
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as error:
        raise ValueError(f"not a Sample Dataset Wallet file: {error}") from error


def write_wallet(path: Path, wallet: SampleWallet, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dumps(wallet, compact=compact).encode("utf-8"))


def read_wallet(path: Path) -> SampleWallet:
    try:
        return loads(path.read_bytes().decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError(f"{path}: {error}") from error


def _check_keys(row: dict[str, Any], expected: set[str], kind: str) -> None:
    if set(row) != expected:
        raise ValueError(f"{kind} keys {sorted(set(row) ^ expected)} missing or unknown")


def _bool(value: Any) -> bool:
    if not isinstance(value, bool):  # bool("false") would be True
        raise TypeError(f"expected true or false, not {value!r}")
    return value


def _keys(record_type: type) -> set[str]:
    return {field.name for field in fields(record_type)}


def _activity_row(row: dict[str, Any]) -> ActivityRow:
    _check_keys(row, _keys(ActivityRow), "activity row")
    return ActivityRow(
        type=str(row["type"]),
        condition_id=str(row["condition_id"]),
        timestamp=int(row["timestamp"]),
        size=float(row["size"]),
        usdc_size=float(row["usdc_size"]),
        price=float(row["price"]),
        token_id=row["token_id"],
        side=row["side"],
    )


def _listed_position(row: dict[str, Any]) -> ListedPosition:
    _check_keys(row, _keys(ListedPosition), "positions-list row")
    return ListedPosition(
        condition_id=str(row["condition_id"]),
        token_id=str(row["token_id"]),
        status=str(row["status"]),
        shares_bought=float(row["shares_bought"]),
        first_entry_at=int(row["first_entry_at"]),
    )


def _market(row: dict[str, Any]) -> Market:
    _check_keys(row, _keys(Market), "Market")
    closed_time = row["closed_time"]
    return Market(
        condition_id=str(row["condition_id"]),
        closed=_bool(row["closed"]),
        closed_time=None if closed_time is None else int(closed_time),
        token_ids=tuple(str(token) for token in row["token_ids"]),
        outcome_prices=tuple(float(price) for price in row["outcome_prices"]),
        fees_enabled=_bool(row["fees_enabled"]),
    )


def _price_point(row: dict[str, Any]) -> PricePoint:
    _check_keys(row, _keys(PricePoint), "price point")
    return PricePoint(token_id=str(row["token_id"]), t=int(row["t"]), price=float(row["price"]))
