"""Shared record types (Position, ActivityRow, Market, PricePoint, ...).

Layer `records` (AD-1): imports nothing from the app. Every other layer passes these around;
nothing above `data/` sees raw JSON (AD-2). Time is UTC epoch seconds, money is USD as `float`
(Consistency Conventions).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExclusionReason(StrEnum):
    """Why a Position is left out of the Skill Test (AD-11).

    Listed in the order the builder checks them: when several apply, the first is the one stored.
    """

    NOT_FULLY_READ = "not fully read"
    UNCLEAR_RESOLUTION = "unclear resolution"
    SPLIT_OR_MERGED = "split or merged"
    ONLY_IN_ACTIVITY = "only in activity rows"
    SHARE_GAP = "share gap"
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
    After resolution the winner's price is 1 and the loser's 0. `start_time` is Gamma's start date
    (where the window's activity read begins, AD-7); `fee_rate` and `fee_exponent` are its
    `feeSchedule` (checked in Story 2.3, AD-12), None when Gamma gives none; `tags` are the
    event tag labels (used from Story 7.1).
    """

    condition_id: str
    closed: bool
    closed_time: int | None
    token_ids: tuple[str, ...]
    outcome_prices: tuple[float, ...]
    fees_enabled: bool = False
    start_time: int | None = None
    fee_rate: float | None = None
    fee_exponent: float | None = None
    tags: tuple[str, ...] = ()

    @property
    def resolved(self) -> bool:
        """AD-7: closed, outcome prices exactly {0, 1}, and a resolution time."""
        return (
            self.closed
            and self.closed_time is not None
            and len(self.token_ids) == len(self.outcome_prices)
            and sorted(self.outcome_prices) == [0.0, 1.0]
        )


@dataclass(frozen=True, slots=True)
class PricePoint:
    """One price of one outcome at one time (AD-24; used by the Copy Test, Epic 6)."""

    token_id: str
    t: int
    price: float


@dataclass(frozen=True, slots=True)
class ListedPosition:
    """One row of a Wallet's positions lists (AD-10: which Positions exist, shares bought).

    `status` is CLOSED (sold, or redeemed after resolution) or OPEN (still held, which includes
    settled losers nobody redeemed). `first_entry_at` is the first buy time (AD-7).
    `last_event_at` is the Wallet's last event on it (a sell or a redemption), which is NOT the
    resolution time; it only tells the window when to stop reading the CLOSED list (AD-7).
    """

    condition_id: str
    token_id: str
    status: str
    shares_bought: float
    first_entry_at: int
    last_event_at: int


@dataclass(frozen=True, slots=True)
class SampleWallet:
    """Everything the Sample Dataset stores for one Wallet (AD-14), as the client would return it."""

    address: str
    name: str
    activity: tuple[ActivityRow, ...]
    positions: tuple[ListedPosition, ...]
    markets: tuple[Market, ...]
    prices: tuple[PricePoint, ...] = ()


@dataclass(frozen=True, slots=True)
class Position:
    """All of one Wallet's fills of one outcome in one Market (PRD Glossary, FR-3).

    `entry_price` (p) is the share-weighted average of the BUY fills; it and `exit_pnl` are None
    when the token has no buy. `shares_held` (s) is bought minus sold. `outcome` (o) is 1.0 or
    0.0, or None when the Market's resolution is unclear. `reason` is None for a tested Position
    or a Sliver.

    `own_fees` holds only the fees that passed the schedule check (AD-12). `failed_fee_count` and
    `failed_fees` are the fills whose fee failed it and their recorded total, which counts as 0.
    `share_gap` is how far the positions list and the activity rows disagree on shares bought, as a
    share of the larger (AD-11); None when the token is not on the positions lists, or when its
    activity was never read ("not fully read", so there is nothing to compare).
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
    share_gap: float | None = None
    failed_fee_count: int = 0
    failed_fees: float = 0.0


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
    def left_out_share(self) -> float:
        """The share of the window's Positions left out, for any reason together (FR-11); 0 for an empty window."""
        return len(self.left_out) / self.window_size if self.window_size else 0.0

    @property
    def failed_fee_count(self) -> int:
        """Fills whose Own Fee failed the schedule check, in the Positions that count in Real PnL (AD-12)."""
        return sum(p.failed_fee_count for p in (*self.tested, *self.slivers))

    @property
    def failed_fee_total(self) -> float:
        """The recorded total of those failed fees, shown on the card; each counts as 0 (AD-12)."""
        return sum((p.failed_fees for p in (*self.tested, *self.slivers)), 0.0)

    @property
    def excluded_counts(self) -> dict[ExclusionReason, int]:
        counts = {reason: 0 for reason in ExclusionReason}
        for position in self.left_out:
            if position.reason is None:
                raise ValueError(f"left-out Position {position.token_id} has no reason")
            counts[position.reason] += 1
        return counts


class Verdict(StrEnum):
    """The four Verdicts (PRD Glossary, FR-6). The text is what the user reads."""

    SKILLED = "Skilled (high confidence)"
    LIKELY_SKILLED = "Likely skilled"
    NO_EVIDENCE = "No evidence of skill"
    NOT_ENOUGH_DATA = "Not enough data"


@dataclass(frozen=True, slots=True)
class ChartBin:
    """One bar of the luck chart, in USD (FR-9, AD-25).

    A bar holds the Simulations from `low` (included) up to `high` (not included); the last bar
    on the axis also holds `high` itself. The two end bars hold everything strictly beyond the
    axis: the first has `low` None, the last has `high` None.
    """

    low: float | None
    high: float | None
    count: int


@dataclass(frozen=True, slots=True)
class SkillTestResult:
    """One Skill Test result: its scope, Seed and counts (FR-4 to FR-7, AD-22, AD-25).

    The Wallet and `fetch_id` it belongs to are the store's key (Story 1.6), not fields here.

    `real_pnl` is the exact sum, Own Fees included (FR-4). For *Not enough data*, `p_value`
    and `at_or_above` are None, `simulations` is 0 and there are no `bins` (FR-6, FR-10).
    `at_or_above` is the exact count of Simulations at or above the Real PnL (FR-5).
    """

    scope: str
    seed: int
    verdict: Verdict
    tested_count: int
    sliver_count: int
    real_pnl: float
    own_fees: float
    simulations: int
    at_or_above: int | None
    p_value: float | None
    bins: tuple[ChartBin, ...]


@dataclass(frozen=True, slots=True)
class Read[T]:
    """The rows of one list read from Polymarket, and whether every page was read (AD-3).

    `complete` is False when a page kept timing out even after the walk restarted with a
    smaller `limit`, or when Polymarket said there was more but gave no cursor. The rows read
    so far are kept, so a partial read stays visible instead of passing as whole.
    """

    rows: tuple[T, ...]
    complete: bool


@dataclass(frozen=True, slots=True)
class Window:
    """One Wallet's window as `data/window.positions_near` returns it (AD-7, AD-8).

    `positions` are the positions-list rows in the window, `markets` their Gamma records and
    `activity` every activity row of those Markets. `activity_read_until` is None when the
    activity read was complete; otherwise it is the time of the last row read, and the
    Positions whose Market resolved in that second or later are "not fully read" (AD-7, AD-11).
    """

    wallet: str
    limit: int
    positions: tuple[ListedPosition, ...]
    markets: tuple[Market, ...]
    activity: tuple[ActivityRow, ...]
    activity_read_until: int | None

    def not_fully_read(self) -> tuple[ListedPosition, ...]:
        """The window's Positions whose Market resolved in or after the second of the last activity row read."""
        return unread_positions(self.positions, self.markets, self.activity_read_until)


def unread_positions(
    positions: tuple[ListedPosition, ...], markets: tuple[Market, ...], read_until: int | None
) -> tuple[ListedPosition, ...]:
    """AD-7: exactly the Positions whose Market `closed_time` is at or after `read_until` (None: none).

    "At" too: a cap can cut inside a second, so rows of that second may be unread (review, Story 2.2).
    """
    if read_until is None:
        return ()
    closed_at = {m.condition_id: m.closed_time for m in markets}
    return tuple(
        p for p in positions if (closed_at.get(p.condition_id) or 0) >= read_until
    )
