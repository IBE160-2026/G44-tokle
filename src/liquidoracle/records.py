"""Shared record types (Position, ActivityRow, Market, PricePoint, ...).

Layer `records` (AD-1): imports nothing from the app. Every other layer passes these around;
nothing above `data/` sees raw JSON (AD-2). Time is UTC epoch seconds, money is USD as `float`
(Consistency Conventions).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExclusionReason(StrEnum):
    """Why a Position is left out of the Skill Test (AD-11). Stories 2.2 and 2.3 add the rest."""

    UNCLEAR_RESOLUTION = "unclear resolution"
    SPLIT_OR_MERGED = "split or merged"
    SOLD_BEFORE_RESOLUTION = "sold before resolution"
    NOT_EXPLAINED = "not explained"


@dataclass(frozen=True, slots=True)
class ActivityRow:
    """One row of a Wallet's activity (AD-10).

    `type` is TRADE, REDEEM, SPLIT, MERGE or CONVERSION. Only TRADE rows carry a `token_id`
    and a `side` (BUY or SELL); the others are about a whole Market (`condition_id`).
    `size` is shares, `usdc_size` is the cash moved, fee included.
    """

    type: str
    condition_id: str
    timestamp: int
    size: float
    usdc_size: float
    price: float
    token_id: str | None = None
    side: str | None = None


@dataclass(frozen=True, slots=True)
class Market:
    """One Market as Gamma describes it (AD-7, AD-10).

    `token_ids` and `outcome_prices` are aligned: the i-th price belongs to the i-th outcome.
    After resolution the winner's price is 1 and the loser's 0.
    """

    condition_id: str
    closed: bool
    closed_time: int | None
    token_ids: tuple[str, ...]
    outcome_prices: tuple[float, ...]
    fees_enabled: bool = False


@dataclass(frozen=True, slots=True)
class PricePoint:
    """One price of one outcome at one time (AD-24; used by the Copy Test, Epic 6)."""

    token_id: str
    t: int
    price: float


@dataclass(frozen=True, slots=True)
class Position:
    """All of one Wallet's fills of one outcome in one Market (PRD Glossary, FR-3).

    `entry_price` (p) is the share-weighted average of the BUY fills; it and `exit_pnl` are None
    when the token has no buy. `shares_held` (s) is bought minus sold. `outcome` (o) is 1.0 or
    0.0, or None when the Market's resolution is unclear. `reason` is None for a tested Position
    or a Sliver.
    """

    condition_id: str
    token_id: str
    outcome: float | None
    entry_price: float | None
    shares_bought: float
    shares_sold: float
    shares_held: float
    own_fees: float
    exit_pnl: float | None
    reason: ExclusionReason | None = None


@dataclass(frozen=True, slots=True)
class PositionSet:
    """What `core/positions` returns for one window (AD-11).

    `tested` are the Resolved Positions; `slivers` count in the money and the Simulations but
    not as bets (PRD Glossary, Sliver); `left_out` each carry their `reason`.
    """

    tested: tuple[Position, ...]
    slivers: tuple[Position, ...]
    left_out: tuple[Position, ...]

    @property
    def window_size(self) -> int:
        return len(self.tested) + len(self.slivers) + len(self.left_out)

    @property
    def tested_count(self) -> int:
        return len(self.tested)

    @property
    def excluded_counts(self) -> dict[ExclusionReason, int]:
        counts = {reason: 0 for reason in ExclusionReason}
        for position in self.left_out:
            if position.reason is None:
                raise ValueError(f"left-out Position {position.token_id} has no reason")
            counts[position.reason] += 1
        return counts
