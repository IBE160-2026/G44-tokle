"""Building Positions from a Wallet's fills (FR-3, AD-7, AD-10, AD-11, AD-12).

The only code that builds Positions and applies exclusions (AD-11). A pure function: the same
fills and Markets always give the same result, whatever order the fills come in.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace

from liquidoracle.records import ActivityRow, ExclusionReason, ListedPosition, Market, Position, PositionSet

# Polymarket keeps shares to 6 decimals; rounding there removes float noise such as 3e-15
# left by bought - sold (found on the Sample Wallets, 2026-11-11).
SHARE_DECIMALS = 6

# A Sliver has less than this share of its bought shares left AND fewer than SLIVER_MAX_SHARES
# (PRD Glossary, Sliver; [ASSUMPTION: 1%], Edvard, 2026-11-11).
SLIVER_SHARE_OF_BOUGHT = 0.01
SLIVER_MAX_SHARES = 1.0

_MARKET_ROWS = frozenset({"SPLIT", "MERGE", "CONVERSION"})
_KNOWN_TYPES = _MARKET_ROWS | {"TRADE", "REDEEM"}


def is_resolved(market: Market) -> bool:
    """AD-7: closed, outcome prices exactly {0, 1}, and a resolution time (`Market.resolved`)."""
    return market.resolved


def build_positions(
    fills: Iterable[ActivityRow],
    markets: Mapping[str, Market],
    *,
    not_fully_read: Iterable[ListedPosition] = (),
) -> PositionSet:
    """Combine a Wallet's activity rows into Positions and sort them into tested, Slivers and left out.

    `markets` maps condition_id to Market. The window is the Positions in closed Markets
    (AD-7); fills in Markets that are not closed, or have no Market record, are outside it.

    `not_fully_read` are the window's Positions whose Market resolved in or after the second of the
    last activity row read (AD-7). Every Position in their Markets is left out as "not fully read", also one with
    no fill read at all, so it is still counted (AD-11).
    """
    unread = {row.token_id: row for row in not_fully_read}
    unread_markets = {row.condition_id for row in unread.values()}
    split_markets: set[str] = set()
    trades: dict[tuple[str, str], list[ActivityRow]] = {}
    for row in fills:
        if row.type not in _KNOWN_TYPES:
            raise ValueError(f"unknown activity row type {row.type!r}")
        if row.type in _MARKET_ROWS:
            split_markets.add(row.condition_id)
        elif row.type == "TRADE":
            if not row.token_id or row.side not in ("BUY", "SELL"):
                raise ValueError(f"TRADE row in {row.condition_id} lacks a token or a BUY/SELL side")
            trades.setdefault((row.condition_id, row.token_id), []).append(row)
        # REDEEM rows are never a share source (AD-10).

    tested: list[Position] = []
    slivers: list[Position] = []
    left_out: list[Position] = []
    for condition_id, token_id in sorted(trades):
        market = markets.get(condition_id)
        if market is None or not market.closed:
            continue
        position = _build_one(market, condition_id, token_id, trades[(condition_id, token_id)], condition_id in split_markets)
        if condition_id in unread_markets:
            position = replace(position, reason=ExclusionReason.NOT_FULLY_READ)
        if position.reason is not None:
            left_out.append(position)
        elif _is_sliver(position):
            slivers.append(position)
        else:
            tested.append(position)
    for token_id, row in sorted(unread.items(), key=lambda item: (item[1].condition_id, item[0])):
        if (row.condition_id, token_id) not in trades:  # no fill of it was read before the cap
            left_out.append(_unread(row, markets.get(row.condition_id)))
    return PositionSet(tested=tuple(tested), slivers=tuple(slivers), left_out=tuple(left_out))


def _unread(row: ListedPosition, market: Market | None) -> Position:
    """A Position the activity read never reached: counted, with what the positions list says (AD-11)."""
    outcome = None
    if market is not None and is_resolved(market) and row.token_id in market.token_ids:
        outcome = market.outcome_prices[market.token_ids.index(row.token_id)]
    return Position(
        condition_id=row.condition_id,
        token_id=row.token_id,
        outcome=outcome,
        entry_price=None,
        shares_bought=round(row.shares_bought, SHARE_DECIMALS),
        shares_sold=0.0,
        shares_held=0.0,
        own_fees=0.0,
        exit_pnl=None,
        reason=ExclusionReason.NOT_FULLY_READ,
    )


def _build_one(market: Market, condition_id: str, token_id: str, rows: list[ActivityRow], split: bool) -> Position:
    # Sort so float sums do not depend on the order the fills arrived in.
    rows = sorted(rows, key=lambda r: (r.timestamp, r.side or "", r.size, r.price, r.usdc_size))
    buys = [r for r in rows if r.side == "BUY"]
    sells = [r for r in rows if r.side == "SELL"]

    bought = sum((r.size for r in buys), 0.0)
    sold = sum((r.size for r in sells), 0.0)
    entry_price = sum(r.size * r.price for r in buys) / bought if bought > 0 else None
    exit_pnl = None
    if entry_price is not None:
        exit_pnl = sum((r.size * (r.price - entry_price) for r in sells), 0.0)
    own_fees = sum((r.usdc_size - r.size * r.price for r in buys), 0.0) if market.fees_enabled else 0.0

    shares_bought = round(bought, SHARE_DECIMALS)
    shares_sold = round(sold, SHARE_DECIMALS)
    shares_held = round(bought - sold, SHARE_DECIMALS)

    outcome = None
    if is_resolved(market) and token_id in market.token_ids:
        outcome = market.outcome_prices[market.token_ids.index(token_id)]

    if outcome is None:
        reason = ExclusionReason.UNCLEAR_RESOLUTION
    elif split:
        reason = ExclusionReason.SPLIT_OR_MERGED
    elif shares_held == 0:
        reason = ExclusionReason.SOLD_BEFORE_RESOLUTION
    elif not 0 < shares_held <= shares_bought:
        reason = ExclusionReason.NOT_EXPLAINED
    else:
        reason = None

    return Position(
        condition_id=condition_id,
        token_id=token_id,
        outcome=outcome,
        entry_price=entry_price,
        shares_bought=shares_bought,
        shares_sold=shares_sold,
        shares_held=shares_held,
        own_fees=own_fees,
        exit_pnl=exit_pnl,
        reason=reason,
    )


def _is_sliver(position: Position) -> bool:
    return (
        # Rounded like the shares, so exactly 1% is never a Sliver (0.01 * 70 is 0.7000000000000001).
        position.shares_held < round(SLIVER_SHARE_OF_BOUGHT * position.shares_bought, SHARE_DECIMALS)
        and position.shares_held < SLIVER_MAX_SHARES
    )
