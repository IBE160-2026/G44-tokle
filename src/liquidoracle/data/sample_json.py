"""The one serializer for Sample Dataset files (AD-14).

One JSON file per Wallet, holding its activity rows, positions-list rows, Markets and price
points as `records` types, and where a real Wallet's capture stopped reading activity (Story 2.6). Keys are sorted, line endings are LF and files are written as bytes,
so the same Wallet gives the same bytes on every OS and Python version (FR-13). Reading is
strict: a missing or unknown key, a wrongly typed value, NaN or Infinity is an error, never a
silent default or conversion.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from liquidoracle.records import ActivityRow, ListedPosition, Market, PricePoint, SampleWallet

WALLET_KEYS = {"address", "name", "activity", "positions", "markets", "prices", "activity_from", "activity_until"}


def dumps(wallet: SampleWallet, *, compact: bool = False) -> str:
    """The file text for one Wallet. `compact` drops the indentation (used for the large groups)."""
    document = {
        "address": wallet.address,
        "name": wallet.name,
        "activity": [asdict(row) for row in wallet.activity],
        "positions": [asdict(row) for row in wallet.positions],
        "markets": [asdict(market) for market in wallet.markets],
        "prices": [asdict(point) for point in wallet.prices],
        "activity_from": wallet.activity_from,
        "activity_until": wallet.activity_until,
    }
    if compact:
        text = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    else:
        text = json.dumps(document, sort_keys=True, indent=1, allow_nan=False)
    return text + "\n"


def loads(text: str) -> SampleWallet:
    """Read one Wallet back. Raises ValueError on any malformed content."""
    try:
        document = json.loads(text, parse_constant=_refuse_constant)
        if not isinstance(document, dict):
            raise TypeError("the file is not a JSON object")
        _check_keys(document, WALLET_KEYS, "wallet")
        return SampleWallet(
            address=_str(document["address"]),
            name=_str(document["name"]),
            activity=tuple(_activity_row(row) for row in _list(document["activity"])),
            positions=tuple(_listed_position(row) for row in _list(document["positions"])),
            markets=tuple(_market(row) for row in _list(document["markets"])),
            prices=tuple(_price_point(row) for row in _list(document["prices"])),
            activity_from=_optional_int(document["activity_from"]),
            activity_until=_optional_int(document["activity_until"]),
        )
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"not a Sample Dataset Wallet file: {error}") from error


def write_wallet(path: Path, wallet: SampleWallet, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dumps(wallet, compact=compact).encode("utf-8"))


def read_ids(path: Path) -> tuple[str, tuple[str, ...]]:
    """The Wallet address and Market ids in one file, without building its records.

    Used by `data/offline.py` to index the Sample Dataset quickly; `read_wallet` still checks
    the whole file strictly when the Wallet is read.
    """
    try:
        document = json.loads(path.read_bytes().decode("utf-8"), parse_constant=_refuse_constant)
        _check_keys(document, WALLET_KEYS, "wallet")
        address = _str(document["address"])
        markets = tuple(_str(market["condition_id"]) for market in _list(document["markets"]))
        return address, markets
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeDecodeError) as error:
        raise ValueError(f"{path}: not a Sample Dataset Wallet file: {error}") from error


def read_wallet(path: Path) -> SampleWallet:
    """Read one Wallet file. A malformed file gives a ValueError that names it."""
    try:
        return loads(path.read_bytes().decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError(f"{path}: {error}") from error


# Strict readers: JSON types must already be right; nothing is converted (bool("false") is True,
# int(1.9) is 1, str(None) is "None").


def _refuse_constant(name: str) -> float:
    raise ValueError(f"{name} is not allowed")


def _check_keys(row: Any, expected: set[str], kind: str) -> None:
    if not isinstance(row, dict):
        raise TypeError(f"{kind} is not a JSON object")
    if set(row) != expected:
        raise ValueError(f"{kind} keys {sorted(set(row) ^ expected)} missing or unknown")


def _keys(record_type: type) -> set[str]:
    return {field.name for field in fields(record_type)}


def _list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"expected a list, not {value!r}")
    return value


def _str(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError(f"expected text, not {value!r}")
    return value


def _int(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"expected a whole number, not {value!r}")
    return value


def _optional_int(value: Any) -> int | None:
    return None if value is None else _int(value)


def _float(value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"expected a number, not {value!r}")
    return float(value)


def _bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"expected true or false, not {value!r}")
    return value


def _one_of(value: Any, allowed: tuple[str | None, ...]) -> Any:
    if value not in allowed:
        raise ValueError(f"expected one of {allowed}, not {value!r}")
    return value


def _activity_row(row: Any) -> ActivityRow:
    _check_keys(row, _keys(ActivityRow), "activity row")
    return ActivityRow(
        type=_str(row["type"]),
        condition_id=_str(row["condition_id"]),
        timestamp=_int(row["timestamp"]),
        size=_float(row["size"]),
        usdc_size=_float(row["usdc_size"]),
        price=_float(row["price"]),
        token_id=None if row["token_id"] is None else _str(row["token_id"]),
        side=_one_of(row["side"], (None, "BUY", "SELL")),
    )


def listed_position(row: Any) -> ListedPosition:
    """One positions-list row read strictly; the build-sample script's additions file uses it (Story 2.6)."""
    try:
        return _listed_position(row)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"not a positions-list row: {error}") from error


def _listed_position(row: Any) -> ListedPosition:
    _check_keys(row, _keys(ListedPosition), "positions-list row")
    return ListedPosition(
        condition_id=_str(row["condition_id"]),
        token_id=_str(row["token_id"]),
        status=_one_of(row["status"], ("CLOSED", "OPEN")),
        shares_bought=_float(row["shares_bought"]),
        first_entry_at=_int(row["first_entry_at"]),
        last_event_at=_int(row["last_event_at"]),
    )


def _market(row: Any) -> Market:
    _check_keys(row, _keys(Market), "Market")
    return Market(
        condition_id=_str(row["condition_id"]),
        closed=_bool(row["closed"]),
        closed_time=None if row["closed_time"] is None else _int(row["closed_time"]),
        token_ids=tuple(_str(token) for token in _list(row["token_ids"])),
        outcome_prices=tuple(_float(price) for price in _list(row["outcome_prices"])),
        fees_enabled=_bool(row["fees_enabled"]),
        start_time=None if row["start_time"] is None else _int(row["start_time"]),
        fee_rate=None if row["fee_rate"] is None else _float(row["fee_rate"]),
        fee_exponent=None if row["fee_exponent"] is None else _float(row["fee_exponent"]),
        tags=tuple(_str(tag) for tag in _list(row["tags"])),
        event_id=None if row["event_id"] is None else _str(row["event_id"]),
        neg_risk_id=None if row["neg_risk_id"] is None else _str(row["neg_risk_id"]),
    )


def _price_point(row: Any) -> PricePoint:
    _check_keys(row, _keys(PricePoint), "price point")
    return PricePoint(token_id=_str(row["token_id"]), t=_int(row["t"]), price=_float(row["price"]))
