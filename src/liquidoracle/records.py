"""Shared record types (Position, ActivityRow, Market, PricePoint, ...).

Layer `records` (AD-1): imports nothing from the app. Every other layer passes these around;
nothing above `data/` sees raw JSON (AD-2). Time is UTC epoch seconds, money is USD as `float`
(Consistency Conventions).
"""

from __future__ import annotations

import math
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

    `event_id` is Gamma's event (`events[0].id`), used to measure links not coupled (AD-20).
    `neg_risk_id` is the negative-risk event (`negRiskMarketID`), set only when Gamma says
    `negRisk` and the outcomes are Yes/No; then `token_ids[0]` is Yes (AD-20, Story 2.4).
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
    event_id: str | None = None
    neg_risk_id: str | None = None

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


# AD-24: where a price answer came from. `refused` marks a window Polymarket refused: it is stored with no points.
ROUTE_CLOB, ROUTE_V2, ROUTE_SAMPLE, ROUTE_REFUSED = "clob", "v2", "sample", "refused"
PRICE_ROUTES = (ROUTE_CLOB, ROUTE_V2, ROUTE_SAMPLE, ROUTE_REFUSED)
# AD-14: the longest window one price request may cover; Polymarket refuses longer ones (spike, Q3).
PRICE_REQUEST_SPAN = 14 * 86_400


@dataclass(frozen=True, slots=True)
class PriceRead:
    """The one-minute price points of one outcome inside one asked window, oldest first, one per second at
    most, and the route that answered (AD-24). No points means Polymarket has no one-minute price there."""

    points: tuple[PricePoint, ...]
    route: str


@dataclass(frozen=True, slots=True)
class PriceRequest:
    """One price request still to make (AD-14): the short windows of one token it covers, oldest first.
    The request asks for [`start`, `end`], at most `PRICE_REQUEST_SPAN` long; only the points inside
    `windows` are kept."""

    token_id: str
    windows: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if not self.windows:
            raise ValueError("a price request covers at least one window")
        last_end = None
        for start, end in self.windows:
            if end < start or (last_end is not None and start <= last_end):
                raise ValueError("a price request's windows are in time order and do not overlap")
            last_end = end
        if self.end - self.start > PRICE_REQUEST_SPAN:
            raise ValueError(f"a price request covers at most {PRICE_REQUEST_SPAN} seconds")

    @property
    def start(self) -> int:
        return self.windows[0][0]

    @property
    def end(self) -> int:
        return self.windows[-1][1]


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
    """Everything the Sample Dataset stores for one Wallet (AD-14), as the client would return it.

    `activity_from` and `activity_until` say where a real Wallet's capture stopped reading activity
    (Story 2.6): rows before `activity_from`, and rows from the second `activity_until` on, may be
    missing. None means nothing is missing on that side (every Synthetic Wallet).
    """

    address: str
    name: str
    activity: tuple[ActivityRow, ...]
    positions: tuple[ListedPosition, ...]
    markets: tuple[Market, ...]
    prices: tuple[PricePoint, ...] = ()
    activity_from: int | None = None
    activity_until: int | None = None


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

    `event_id` and `neg_risk_id` are copied from the Market (AD-20). `yes_side` is True when the
    token is the Yes outcome of a negative-risk Market; it wins on low draws in the Skill Test.
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
    event_id: str | None = None
    neg_risk_id: str | None = None
    yes_side: bool = False


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
    def read_count(self) -> int:
        """FR-11's M: the window's Positions whose history was read in full (all but "not fully read")."""
        unread = sum(1 for p in self.left_out if p.reason is ExclusionReason.NOT_FULLY_READ)
        return self.window_size - unread

    @property
    def held_count(self) -> int:
        """FR-11's N: of those, the ones not sold before resolution; a Sliver sold over 99%, so it counts as sold.

        A bet left out for another reason (split or merged, say) was still held (Edvard, 2026-11-24, Story 3.3).
        """
        sold = sum(1 for p in self.left_out if p.reason is ExclusionReason.SOLD_BEFORE_RESOLUTION)
        return self.read_count - sold - len(self.slivers)

    @property
    def exit_pnl(self) -> float:
        """FR-11's Exit PnL: Σ shares sold x (sell price - p) over the tested Positions, Slivers and Positions sold
        before resolution (Edvard, 2026-11-24, Story 3.3). Other left-out Positions are out: their fills or Entry
        Price cannot be trusted. No sell fees (PRD Glossary)."""
        sold = (p for p in self.left_out if p.reason is ExclusionReason.SOLD_BEFORE_RESOLUTION)
        return math.fsum(p.exit_pnl or 0.0 for p in (*self.tested, *self.slivers, *sold))

    @property
    def any_sold(self) -> bool:
        """FR-11: did any Position counted in the Exit PnL sell shares before resolution?"""
        sold = (p for p in self.left_out if p.reason is ExclusionReason.SOLD_BEFORE_RESOLUTION)
        return any(p.shares_sold > 0 for p in (*self.tested, *self.slivers, *sold))

    @property
    def largest_bet(self) -> float | None:
        """FR-11: the largest single bet's PnL, s x (o - p) - Own Fees, among the Positions in Real PnL; None when there are none."""
        bets = (*self.tested, *self.slivers)
        if not bets:
            return None
        # Tested Positions and Slivers always have an outcome and an Entry Price (the builder's rules).
        return max(math.fsum((p.shares_held * ((p.outcome or 0.0) - (p.entry_price or 0.0)), -p.own_fees)) for p in bets)

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
    `at_or_above` and `at_or_below` are None, `simulations` is 0 and there are no `bins` (FR-6, FR-10).
    `at_or_above` is the exact count of Simulations at or above the Real PnL (FR-5);
    `at_or_below` the count at or below it, so the chart can say "below all" only when no
    Simulation tied or fell below it (FR-9, AD-25; Story 3.1).
    `uncoupled_share` is the share of tested Positions whose Gamma event holds another tested
    Position not coupled with it, for the FR-11 note (AD-20).
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
    at_or_below: int | None
    p_value: float | None
    bins: tuple[ChartBin, ...]
    uncoupled_share: float


# The Hold-up Test's two groups, in the order results are given and shown, and the scope of its results
# (FR-17, AD-22). Here, because both `core` (which forms the groups) and `data` (which stores them) name them.
PASSERS, COMPARISON = "passers", "comparison"
HOLDUP_GROUPS = (PASSERS, COMPARISON)
HOLDUP_AFTER = "holdup_after"


@dataclass(frozen=True, slots=True)
class GroupResult:
    """One group's Hold-up Test result on its pooled after part (FR-17, AD-22).

    `group` is `passers` or `comparison`. `wallets` are the Wallets in the group, `dropped` those
    with too few bets after the Cut-off Date, `not_fully_read` those whose before or after part
    was not fully read. `tested_count` and `real_pnl` cover the pooled bets of the Wallets that
    were not dropped; `p_value` is None for *Not enough data*.
    """

    group: str
    verdict: Verdict
    p_value: float | None
    tested_count: int
    real_pnl: float
    wallets: int
    dropped: int
    not_fully_read: int


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
    `activity` every activity row of those Markets (for the after part, those rows from the
    cut-off on). `activity_read_until` is None when the
    activity read was complete; otherwise it is the time of the last row read, and the
    Positions whose Market resolved in that second or later are "not fully read" (AD-7, AD-11).

    `capped` is True when more Positions were eligible than the window holds, for FR-11's window
    line (Story 3.3): older ones for a lookup and the before part, later ones for the after part.

    `cutoff` (00:00 UTC epoch) and `side` ("before" or "after") name the part of a Cut-off Date
    this window is; both are None for a lookup's window (AD-7, Story 4.1).
    """

    wallet: str
    limit: int
    positions: tuple[ListedPosition, ...]
    markets: tuple[Market, ...]
    activity: tuple[ActivityRow, ...]
    activity_read_until: int | None
    capped: bool = False
    cutoff: int | None = None
    side: str | None = None

    def not_fully_read(self) -> tuple[ListedPosition, ...]:
        """The window's Positions whose Market resolved in or after the second of the last activity row read."""
        return unread_positions(self.positions, self.markets, self.activity_read_until)


@dataclass(frozen=True, slots=True)
class MarketHolder:
    """One row of a Market's positions list, `/v2/positions?condition=…` (AD-9, AD-21).

    `status` is the list asked for, CLOSED or OPEN. The three numbers feed only the Scan's
    pre-filter (AD-21): `realized_pnl` on a CLOSED row, `current_size` x (outcome price -
    `avg_price`) on an OPEN row. They never reach a Position or the Skill Test (AD-10).
    """

    wallet: str
    token_id: str
    status: str
    realized_pnl: float
    current_size: float
    avg_price: float


@dataclass(frozen=True, slots=True)
class FunnelMarket:
    """A Market of a Scan's Market set and its Gamma volume in USD, the one number that orders the set (AD-21)."""

    market: Market
    volume: float


@dataclass(frozen=True, slots=True)
class Candidate:
    """A shortlisted Wallet and its pre-filter estimate in USD (AD-21)."""

    wallet: str
    estimate: float


@dataclass(frozen=True, slots=True)
class RankedWallet:
    """One shortlisted Wallet ranked on the Real PnL of its before part (AD-9, AD-10, AD-21).

    `not_fully_read` is set when Polymarket refused the Wallet (`refused`) or when any Position of
    its before part is "not fully read" (AD-9). A refusal at any request discards the whole read
    (the window is all-or-nothing), so a refused Wallet ranks on $0.
    `top` marks the Wallets kept, the top N.
    """

    wallet: str
    real_pnl: float
    not_fully_read: bool = False
    refused: bool = False
    top: bool = False


@dataclass(frozen=True, slots=True)
class ScanFunnel:
    """One run of the Scan funnel, in memory (FR-16, AD-9, AD-21; stored by Story 4.3).

    `cutoff` is the Cut-off Date as 00:00 UTC epoch seconds (AD-7) and `size` is N.
    `markets` is the Market set by volume; `partial` the condition ids of those "not used:
    partial" (AD-9). `candidate_count` counts the Wallets in the used Markets. `shortlist` is the
    3 x N by estimate; `contracts` the shortlisted addresses dropped as protocol contracts
    (AD-9). `ranked` is every other shortlisted Wallet by Real PnL, the top N marked `top`.
    """

    cutoff: int
    size: int
    markets: tuple[FunnelMarket, ...]
    partial: tuple[str, ...]
    candidate_count: int
    shortlist: tuple[Candidate, ...]
    contracts: tuple[str, ...]
    ranked: tuple[RankedWallet, ...]

    @property
    def used_count(self) -> int:
        """AD-21's "N of 100 Markets used"."""
        return len(self.markets) - len(self.partial)

    @property
    def top(self) -> tuple[RankedWallet, ...]:
        return tuple(w for w in self.ranked if w.top)

    @property
    def not_fully_read_count(self) -> int:
        """Ranked Wallets flagged "not fully read", refused ones included (AD-9)."""
        return sum(1 for w in self.ranked if w.not_fully_read)

    @property
    def refused_count(self) -> int:
        return sum(1 for w in self.ranked if w.refused)


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
