"""The Copy Test's per-Wallet maths: what a follower copying a Wallet's buys late would have made (FR-18a).

A follower sees a buy and copies it one Copy Delay later, at the price recorded then plus the Spread
Allowance, and pays the Market's fee. Each buy fill of a Position is copied at its own time, for the
part of it the Wallet still held at resolution. Pure: the prices are handed in, and the same Positions,
fills, prices and Seed always give the same numbers (AD-15).

The Random Group Check, which says whether the Passers' result could be luck, is Story 6.3.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence

from liquidoracle.core.holdup import MIN_AFTER_BETS
from liquidoracle.core.prices import price_at
from liquidoracle.core.rng import generator
from liquidoracle.core.skilltest import real_pnl
from liquidoracle.records import ActivityRow, CopyResult, FollowerResult, Market, Position, PositionSet, PricePoint

COPY_DELAYS = (60, 300, 1800)  # PRD Glossary, Copy Delay: 1, 5 and 30 minutes, in seconds
MAIN_COPY_DELAY = 300  # PRD Glossary, Main Copy Delay: the only one that gives a Copy Verdict (FR-18b)
SPREAD_ALLOWANCE = 0.005  # [ASSUMPTION] PRD Glossary: half a cent added to the price a follower pays
SAMPLE_SIZE = 100  # [ASSUMPTION] PRD Glossary, Copy Sample: at most this many Positions per Wallet
PURPOSE = "copysample"  # AD-15: the random purpose of the Copy Sample draw; the unit is the Wallet

Key = tuple[str, str]  # (condition_id, token_id): one Position
Fills = Mapping[Key, Sequence[ActivityRow]]


def is_priced(passer: bool, after_positions: int) -> bool:
    """Is this Scan Wallet priced? Every Before-Cut-off Passer is (FR-18a shows each one), and every other
    Wallet with at least the Minimum After-bets tested after Positions: with fewer it can never be in the
    Copy Pool (FR-18b), so its prices would be fetched for nothing."""
    return passer or after_positions >= MIN_AFTER_BETS


def copy_sample(tested: Iterable[Position], *, seed: int, wallet: str) -> tuple[Position, ...]:
    """The Copy Sample (PRD Glossary): all of the Wallet's tested after Positions if at most `SAMPLE_SIZE`,
    otherwise that many drawn without replacement with the Seed.

    The Positions are sorted by (condition, token) before the draw and the Wallet has its own random
    stream (AD-15), so the sample depends on the Positions and the Seed only, not on their order or on
    which Wallets were sampled before. Returned in that sorted order.
    """
    ordered = sorted(tested, key=_key)
    if len(ordered) <= SAMPLE_SIZE:
        return tuple(ordered)
    picks = generator(seed, PURPOSE, wallet).choice(len(ordered), size=SAMPLE_SIZE, replace=False)
    return tuple(ordered[i] for i in sorted(int(i) for i in picks))


def buy_fills(sample: Iterable[Position], activity: Iterable[ActivityRow]) -> dict[Key, tuple[ActivityRow, ...]]:
    """The buy fills of each sampled Position, oldest first: the fills a follower copies (AD-10)."""
    wanted = {_key(position) for position in sample}
    found: dict[Key, list[ActivityRow]] = {key: [] for key in wanted}
    for row in activity:
        if row.type == "TRADE" and row.side == "BUY" and row.token_id is not None:
            key = (row.condition_id, row.token_id)
            if key in wanted:
                found[key].append(row)
    # Sorted, so the sums below do not depend on the order the rows arrived in.
    return {key: tuple(sorted(rows, key=lambda r: (r.timestamp, r.size, r.price, r.usdc_size))) for key, rows in found.items()}


def fill_times(fills: Fills) -> dict[str, tuple[int, ...]]:
    """Each token's buy times: what the price windows are planned from (`core/prices.fill_windows`)."""
    return {token_id: tuple(row.timestamp for row in rows) for (_, token_id), rows in fills.items()}


def follower_fee(shares: float, price: float, market: Market) -> float:
    """The Follower Fee (PRD Glossary): what the Market would charge for buying `shares` at `price`.

    shares x rate x (p(1 - p))^exponent, the formula the Own Fee check uses (AD-12), with the rate the
    Market lists today (Edvard, 2026-11-28). 0 where the Market charges no fee or lists no schedule,
    and 0 at a price of 1 (the cap) or 0, where p(1 - p) is 0 whatever the exponent.
    """
    if not market.fees_enabled or market.fee_rate is None or market.fee_exponent is None:
        return 0.0
    base = price * (1.0 - price)
    if base <= 0.0:  # 0 ** 0 would charge the full rate, and 0 to a negative power is an error
        return 0.0
    return shares * market.fee_rate * base**market.fee_exponent


def follow(
    sample: Sequence[Position],
    fills: Fills,
    markets: Mapping[str, Market],
    points_of: Callable[[str], Sequence[PricePoint]],
    delay: int,
) -> FollowerResult:
    """The Copy Sample copied at one Copy Delay (FR-18a).

    Each buy fill is copied at its own time plus `delay`, at the recorded price then (`price_at`) plus
    the Spread Allowance, capped at 1. Its size s is the fill's share of the shares held at resolution:
    the held shares are split over the buy fills in proportion to their size, so a sell is not taken
    off the first or the last fill. A copy time after the Market closed gets no rule of its own: it
    is priced if a price was recorded then and left out if none was.
    Follower PnL = sum of s x (o - price paid) - Follower Fee; money spent = sum of s x price paid +
    Follower Fee. A Position is priced only when every one of its buy fills has a price; otherwise the
    whole Position is left out and counted (Edvard, 2026-11-28). `points_of(token_id)` gives one
    token's price points, oldest first.
    """
    pnl: list[float] = []
    spent: list[float] = []
    priced: list[Position] = []
    for position in sample:
        rows = fills.get(_key(position), ())
        market = markets[position.condition_id]
        if not rows or position.outcome is None:
            raise ValueError(f"Copy Sample Position {position.token_id} has no buy fill or no outcome")
        bought = math.fsum(row.size for row in rows)
        points = points_of(position.token_id)
        terms: list[tuple[float, float]] = []
        for row in rows:
            recorded = price_at(points, row.timestamp + delay)
            if recorded is None:
                break
            paid = min(1.0, recorded + SPREAD_ALLOWANCE)
            shares = row.size * position.shares_held / bought
            fee = follower_fee(shares, paid, market)
            terms.append((shares * (position.outcome - paid) - fee, shares * paid + fee))
        if len(terms) < len(rows):
            continue  # a fill with no recorded price: the whole Position is left out of this delay
        priced.append(position)
        pnl.extend(term[0] for term in terms)
        spent.extend(term[1] for term in terms)
    return FollowerResult(
        delay=delay,
        priced=len(priced),
        left_out=len(sample) - len(priced),
        follower_pnl=math.fsum(pnl),
        spent=math.fsum(spent),
        own_pnl=real_pnl(PositionSet(tested=tuple(priced), slivers=(), left_out=())),
    )


def copy_result(
    wallet: str,
    after_positions: int,
    sample: Sequence[Position],
    fills: Fills,
    markets: Mapping[str, Market],
    points_of: Callable[[str], Sequence[PricePoint]],
    *,
    not_fully_read: bool = False,
) -> CopyResult:
    """One priced Wallet's result at every Copy Delay, over its Copy Sample ("priced N of M", FR-18a)."""
    return CopyResult(
        wallet=wallet,
        after_positions=after_positions,
        sampled=len(sample),
        not_fully_read=not_fully_read,
        delays=tuple(follow(sample, fills, markets, points_of, delay) for delay in COPY_DELAYS),
    )


def _key(position: Position) -> Key:
    return position.condition_id, position.token_id
