"""Building Positions from a Wallet's fills (FR-3, AD-7, AD-10, AD-11, AD-12).

The only code that builds Positions and applies exclusions (AD-11). A pure function: the same
fills, listed Positions and Markets always give the same result, whatever order they come in.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

from liquidoracle.records import ActivityRow, ExclusionReason, ListedPosition, Market, Position, PositionSet

# Polymarket keeps shares to 6 decimals; rounding there removes float noise such as 3e-15
# left by bought - sold (found on the Sample Wallets, 2026-11-11).
SHARE_DECIMALS = 6

# A Sliver has less than this share of its bought shares left AND fewer than SLIVER_MAX_SHARES
# (PRD Glossary, Sliver; [ASSUMPTION: 1%], Edvard, 2026-11-11).
SLIVER_SHARE_OF_BOUGHT = 0.01
SLIVER_MAX_SHARES = 1.0

# AD-11: the positions list and the activity rows may disagree on shares bought by up to 1%
# [ASSUMPTION]. Gaps are compared rounded to 9 decimals, so exactly 1% is never a gap.
SHARE_GAP_ABOVE = 0.01
_GAP_DECIMALS = 9

# AD-12: an Own Fee passes when it is within this many USD of 0 (a maker fill) or of the Market's
# schedule [ASSUMPTION: $0.0001]. Real taker fees miss the schedule by at most $0.00001 (Story 2.3).
FEE_TOLERANCE = 0.0001

# FR-4 / AD-12 (Edvard, 2026-11-23, Story 2.8): Gamma lists only a Market's rate today and Polymarket
# changes rates, so a fee also passes at any whole-percent rate from 1% to 10% [ASSUMPTION].
WHOLE_PERCENT_RATES = tuple(k / 100 for k in range(1, 11))

# FR-11 / AD-11: above this share of the window left out, the card says only part was judged [ASSUMPTION].
LEFT_OUT_NOTE_ABOVE = 0.10

_MARKET_ROWS = frozenset({"SPLIT", "MERGE", "CONVERSION"})
_KNOWN_TYPES = _MARKET_ROWS | {"TRADE", "REDEEM"}


def is_resolved(market: Market) -> bool:
    """AD-7: closed, outcome prices exactly {0, 1}, and a resolution time (`Market.resolved`)."""
    return market.resolved


def mostly_left_out(position_set: PositionSet) -> bool:
    """FR-11: more than 10% of the window's Positions left out, for any reasons together."""
    return position_set.left_out_share > LEFT_OUT_NOTE_ABOVE


def fee_passes(fee: float, shares: float, price: float, market: Market) -> bool:
    """FR-4, AD-12: is one buy fill's Own Fee 0 (maker) or a taker fee the Market's schedule allows?

    Expected fee = shares x rate x (p(1 - p))^exponent, with the listed exponent and either the listed rate
    or one of `WHOLE_PERCENT_RATES` (Story 2.8). A negative fee, a fee that fits none of those rates within the
    tolerance, or a non-zero fee in a Market with no schedule, fails.
    """
    if abs(fee) <= FEE_TOLERANCE:
        return True
    if market.fee_rate is None or market.fee_exponent is None:
        return False
    fee_per_unit_rate = shares * (price * (1.0 - price)) ** market.fee_exponent
    rates = (market.fee_rate, *WHOLE_PERCENT_RATES)
    return any(abs(fee - fee_per_unit_rate * rate) <= FEE_TOLERANCE for rate in rates)


def build_positions(
    fills: Iterable[ActivityRow],
    markets: Mapping[str, Market],
    *,
    listed: Iterable[ListedPosition],
    not_fully_read: Iterable[ListedPosition] = (),
) -> PositionSet:
    """Combine a Wallet's activity rows into Positions and sort them into tested, Slivers and left out.

    `markets` maps condition_id to Market. The window is the Positions in closed Markets
    (AD-7); fills and listed Positions in Markets that are not closed, or have no Market record,
    are outside it.

    `listed` are the window's rows from the positions lists (AD-10). Every one of them comes out
    as tested, a Sliver or left out, also one with no fill; a traded token not among them is left
    out as "only in activity rows" (AD-11).

    `not_fully_read` are the window's Positions whose Market resolved in or after the second of the
    last activity row read (AD-7). Every Position in their Markets is left out as "not fully read", also one with
    no fill read at all, so it is still counted (AD-11).

    A CONVERSION row names a negative-risk event, not a Market, so it marks every Market of that
    event as "split or merged" (AD-11, Story 2.4).
    """
    listed_rows: dict[tuple[str, str], ListedPosition] = {}
    for row in listed:
        listed_rows.setdefault((row.condition_id, row.token_id), row)
    unread = {row.token_id: row for row in not_fully_read}
    unread_markets = {row.condition_id for row in unread.values()}
    split_markets: set[str] = set()
    conversion_events: set[str] = set()  # a CONVERSION names its negative-risk event, not a Market
    trades: dict[tuple[str, str], list[ActivityRow]] = {}
    for row in fills:
        if row.type not in _KNOWN_TYPES:
            raise ValueError(f"unknown activity row type {row.type!r}")
        if row.type in _MARKET_ROWS:
            if row.type == "CONVERSION":
                conversion_events.add(row.condition_id)
            split_markets.add(row.condition_id)
        elif row.type == "TRADE":
            if not row.token_id or row.side not in ("BUY", "SELL"):
                raise ValueError(f"TRADE row in {row.condition_id} lacks a token or a BUY/SELL side")
            trades.setdefault((row.condition_id, row.token_id), []).append(row)
        # REDEEM rows are never a share source (AD-10).

    keys = set(trades) | set(listed_rows)
    tested: list[Position] = []
    slivers: list[Position] = []
    left_out: list[Position] = []
    for condition_id, token_id in sorted(keys):
        market = markets.get(condition_id)
        if market is None or not market.closed:
            continue
        rows = trades.get((condition_id, token_id), [])
        if not rows and token_id in unread:
            continue  # counted below with what the positions list says
        split = condition_id in split_markets or market.neg_risk_id in conversion_events
        position = _build_one(market, condition_id, token_id, rows, split, listed_rows.get((condition_id, token_id)))
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
    return Position(
        condition_id=row.condition_id,
        token_id=row.token_id,
        outcome=_outcome(market, row.token_id),
        entry_price=None,
        shares_bought=round(row.shares_bought, SHARE_DECIMALS),
        shares_sold=0.0,
        shares_held=0.0,
        own_fees=0.0,
        exit_pnl=None,
        reason=ExclusionReason.NOT_FULLY_READ,
        event_id=None if market is None else market.event_id,
        neg_risk_id=None if market is None else market.neg_risk_id,
        yes_side=market is not None and _yes_side(market, row.token_id),
    )


def _yes_side(market: Market, token_id: str) -> bool:
    """AD-20: the Yes token of a negative-risk Market (its first outcome), which wins on low draws."""
    return market.neg_risk_id is not None and token_id == market.token_ids[0]


def _outcome(market: Market | None, token_id: str) -> float | None:
    if market is not None and is_resolved(market) and token_id in market.token_ids:
        return market.outcome_prices[market.token_ids.index(token_id)]
    return None


@dataclass(frozen=True, slots=True)
class _Fees:
    counted: float
    failed_count: int
    failed_total: float


def _check_fees(market: Market, buys: list[ActivityRow]) -> _Fees:
    """AD-12: each buy fill's Own Fee (cash - shares x price), checked; failures count as 0 and are recorded."""
    if not market.fees_enabled:
        return _Fees(0.0, 0, 0.0)
    counted = failed_total = 0.0
    failed_count = 0
    for row in buys:
        fee = row.usdc_size - row.size * row.price
        if not fee_passes(fee, row.size, row.price, market):
            failed_count += 1
            failed_total += fee
        elif abs(fee) > FEE_TOLERANCE:  # a maker fill's fee counts as exactly 0, so Own Fees are never negative
            counted += fee
    return _Fees(counted, failed_count, failed_total)


def _share_gap(bought: float, row: ListedPosition | None) -> float | None:
    """AD-11: |activity bought - listed bought| / the larger; 1 for a listed Position with no buy fill; None when unlisted.

    No buy fill is always 1, also when the list says 0 too: nothing was bought that the test could judge (review).
    """
    if row is None:
        return None
    if bought <= 0:
        return 1.0
    listed = round(row.shares_bought, SHARE_DECIMALS)
    return round(abs(bought - listed) / max(bought, listed), _GAP_DECIMALS)


def _sells_before_buying(rows: list[ActivityRow]) -> bool:
    """AD-11: does the running balance go below zero? Buys count first within one second (Edvard, 2026-11-21)."""
    balance = 0.0
    for row in sorted(rows, key=lambda r: (r.timestamp, r.side != "BUY")):
        balance += row.size if row.side == "BUY" else -row.size
        if round(balance, SHARE_DECIMALS) < 0:
            return True
    return False


def _build_one(
    market: Market,
    condition_id: str,
    token_id: str,
    rows: list[ActivityRow],
    split: bool,
    listed: ListedPosition | None,
) -> Position:
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
    fees = _check_fees(market, buys)

    # Shares bought stay the activity rows' sum, so both sides of s <= bought come from one source;
    # the share-gap reason keeps the positions list within 1% of it (AD-11).
    shares_bought = round(bought, SHARE_DECIMALS)
    shares_sold = round(sold, SHARE_DECIMALS)
    shares_held = round(bought - sold, SHARE_DECIMALS)
    share_gap = _share_gap(shares_bought, listed)
    outcome = _outcome(market, token_id)

    # AD-11: one reason, the first that applies in this order (Story 2.3).
    if outcome is None:
        reason = ExclusionReason.UNCLEAR_RESOLUTION
    elif split:
        reason = ExclusionReason.SPLIT_OR_MERGED
    elif listed is None:
        reason = ExclusionReason.ONLY_IN_ACTIVITY
    elif share_gap is not None and share_gap > SHARE_GAP_ABOVE:
        reason = ExclusionReason.SHARE_GAP
    elif shares_held == 0:
        reason = ExclusionReason.SOLD_BEFORE_RESOLUTION
    elif not 0 < shares_held <= shares_bought or _sells_before_buying(rows):
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
        own_fees=fees.counted,
        exit_pnl=exit_pnl,
        reason=reason,
        share_gap=share_gap,
        failed_fee_count=fees.failed_count,
        failed_fees=fees.failed_total,
        event_id=market.event_id,
        neg_risk_id=market.neg_risk_id,
        yes_side=_yes_side(market, token_id),
    )


def _is_sliver(position: Position) -> bool:
    return (
        # Rounded like the shares, so exactly 1% is never a Sliver (0.01 * 70 is 0.7000000000000001).
        position.shares_held < round(SLIVER_SHARE_OF_BOUGHT * position.shares_bought, SHARE_DECIMALS)
        and position.shares_held < SLIVER_MAX_SHARES
    )
