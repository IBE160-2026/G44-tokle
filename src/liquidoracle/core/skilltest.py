"""The Skill Test: Real PnL, 10,000 Simulations, the p-value and the Verdict (FR-4 to FR-7).

Only `skill_test` is for the rest of the app. It always applies the 30-bet minimum (FR-6).
`_engine` skips the minimum and is for the tests alone (the hand-check has 10 bets, FR-13); a
rule test fails if any module outside this file references it (Edvard, 2026-10-24).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from liquidoracle.core import rng
from liquidoracle.records import ChartBin, Position, PositionSet, SkillTestResult, Verdict

SIMULATIONS = 10_000
MIN_RESOLVED = 30  # FR-6: fewer tested Positions give Not enough data
SKILLED_BELOW = 0.01  # FR-6 / PRD §3 thresholds
LIKELY_SKILLED_BELOW = 0.05

CHART_BARS = 40  # AD-25 (Edvard, 2026-11-18): 40 equal bars plus two end bars
CHART_TAIL = 0.001  # each end bar may take up to 0.1% of the Simulations, so the axis shows the middle 99.8%
_NICE_STEPS = (1.0, 2.0, 2.5, 5.0, 10.0)
_MIN_BAR_WIDTH = 0.01  # one cent

_CHUNK = 1_000  # Simulations drawn per block; the same numbers as one big draw, less memory


@dataclass(frozen=True, slots=True)
class _Run:
    real_pnl: float
    own_fees: float
    real_cents: int
    at_or_above: int
    p_value: float
    bins: tuple[ChartBin, ...]


def skill_test(position_set: PositionSet, *, seed: int, unit_id: str, scope: str = "lookup") -> SkillTestResult:
    """Run the Skill Test on one Position set (FR-4 to FR-7).

    The tested Positions and the Slivers are simulated and counted in Real PnL; only the tested
    ones count toward the 30 minimum (PRD Glossary, Sliver). `unit_id` names the random unit
    (the Wallet's address for a lookup, AD-15).
    """
    bets = (*position_set.tested, *position_set.slivers)
    _check(bets)
    tested = position_set.tested_count
    slivers = len(position_set.slivers)
    if tested < MIN_RESOLVED:
        return SkillTestResult(
            scope=scope, seed=seed, verdict=Verdict.NOT_ENOUGH_DATA, tested_count=tested,
            sliver_count=slivers, real_pnl=_real_pnl(bets), own_fees=_own_fees(bets),
            simulations=0, at_or_above=None, p_value=None, bins=(),
        )
    run = _engine(bets, seed=seed, unit_id=unit_id)
    return SkillTestResult(
        scope=scope, seed=seed, verdict=verdict_for(run.p_value), tested_count=tested,
        sliver_count=slivers, real_pnl=run.real_pnl, own_fees=run.own_fees,
        simulations=SIMULATIONS, at_or_above=run.at_or_above, p_value=run.p_value, bins=run.bins,
    )


def verdict_for(p_value: float) -> Verdict:
    """FR-6: p < 0.01 Skilled (high confidence), p < 0.05 Likely skilled, otherwise no evidence."""
    if p_value < SKILLED_BELOW:
        return Verdict.SKILLED
    if p_value < LIKELY_SKILLED_BELOW:
        return Verdict.LIKELY_SKILLED
    return Verdict.NO_EVIDENCE


def _engine(bets: Sequence[Position], *, seed: int, unit_id: str) -> _Run:
    """The Simulations and the p-value, with no minimum. Tests only (see the module docstring)."""
    _check(bets)
    if not bets:
        raise ValueError("the Skill Test needs at least one Position")
    ordered = sorted(bets, key=lambda b: (b.condition_id, b.token_id))  # AD-15

    # AD-20: one U per Market; in each Market the smaller token_id (as text) wins on U < p, the other on U > 1 - p.
    tokens = _tokens_per_market(ordered)
    markets = sorted(tokens)
    column = {condition_id: i for i, condition_id in enumerate(markets)}
    market_of = np.array([column[b.condition_id] for b in ordered], dtype=np.intp)
    wins_low = np.array([b.token_id == min(tokens[b.condition_id]) for b in ordered], dtype=bool)
    price = np.array([b.entry_price for b in ordered], dtype=np.float64)
    high_bar = 1.0 - price

    # Conventions › Money: whole cents once per Position, no fees, so ties count exactly.
    win_cents = [round(b.shares_held * (1.0 - b.entry_price) * 100) for b in ordered]
    loss_cents = [round(-b.shares_held * b.entry_price * 100) for b in ordered]
    real_cents = sum(w if b.outcome == 1.0 else lo for b, w, lo in zip(ordered, win_cents, loss_cents))
    base = sum(loss_cents)
    gain = np.array([w - lo for w, lo in zip(win_cents, loss_cents)], dtype=np.int64)

    generator = rng.generator(seed, "skilltest", unit_id)
    totals = np.empty(SIMULATIONS, dtype=np.int64)
    for start in range(0, SIMULATIONS, _CHUNK):
        rows = min(_CHUNK, SIMULATIONS - start)
        draws = generator.random((rows, len(markets)))[:, market_of]
        won = np.where(wins_low, draws < price, draws > high_bar)
        totals[start:start + rows] = base + won.astype(np.int64) @ gain

    at_or_above = int(np.count_nonzero(totals >= real_cents))
    real_pnl = _real_pnl(ordered)
    own_fees = _own_fees(ordered)
    return _Run(
        real_pnl=real_pnl,
        own_fees=own_fees,
        real_cents=real_cents,
        at_or_above=at_or_above,
        p_value=(1 + at_or_above) / (SIMULATIONS + 1),
        bins=_bins(totals / 100.0 - own_fees, real_pnl),
    )


def _check(bets: Sequence[Position]) -> None:
    """Refuse Positions the Skill Test cannot judge, whatever their number (FR-4, AD-20)."""
    for bet in bets:
        if bet.outcome not in (0.0, 1.0):
            raise ValueError(f"Position {bet.token_id} has no clear outcome ({bet.outcome!r})")
        if bet.entry_price is None or not 0.0 <= bet.entry_price <= 1.0:
            raise ValueError(f"Position {bet.token_id} has no Entry Price between 0 and 1 ({bet.entry_price!r})")
        if not (math.isfinite(bet.shares_held) and bet.shares_held > 0):
            raise ValueError(f"Position {bet.token_id} holds no shares ({bet.shares_held!r})")
        if bet.own_fees is None or not math.isfinite(bet.own_fees):
            raise ValueError(f"Position {bet.token_id} has no Own Fees amount ({bet.own_fees!r})")
        if bet.own_fees < 0:  # the builder's fee check never passes one (AD-12, Story 2.3)
            raise ValueError(f"Position {bet.token_id} has a negative Own Fee ({bet.own_fees!r})")
    _tokens_per_market(bets)


def _tokens_per_market(bets: Sequence[Position]) -> dict[str, set[str]]:
    tokens: dict[str, set[str]] = {}
    for bet in bets:
        tokens.setdefault(bet.condition_id, set()).add(bet.token_id)
    for condition_id, ids in tokens.items():
        if len(ids) > 2:
            raise ValueError(f"Market {condition_id} has {len(ids)} outcomes in one test; only two are supported")
    return tokens


def _real_pnl(bets: Sequence[Position]) -> float:
    """FR-4: the exact sum of s * (o - p) - Own Fees; fsum, so the order never matters."""
    return math.fsum(term for b in bets for term in (b.shares_held * (b.outcome - b.entry_price), -b.own_fees))


def _own_fees(bets: Sequence[Position]) -> float:
    return math.fsum(b.own_fees for b in bets)


def _bins(totals: np.ndarray, real_pnl: float) -> tuple[ChartBin, ...]:
    """AD-25: 40 equal bars on a round axis centred on $0, plus the two end bars.

    Simulations are sorted against the stored edges themselves, so a total that sits on an edge
    always lands in the bar that starts there. The last bar on the axis also holds its top edge,
    so a value at exactly the edge (the Real PnL or the 99.9% point) is on the axis, not beyond it.
    """
    low, high = np.quantile(totals, [CHART_TAIL, 1.0 - CHART_TAIL])
    reach = max(abs(real_pnl), abs(float(low)), abs(float(high)))
    width = _nice(max(2.0 * reach / CHART_BARS, _MIN_BAR_WIDTH))
    half = CHART_BARS // 2
    edges = np.array([round((i - half) * width, 2) for i in range(CHART_BARS + 1)])
    index = np.searchsorted(edges, totals, side="right") - 1  # -1 below the axis, CHART_BARS beyond it
    index[totals == edges[-1]] = CHART_BARS - 1
    below = int(np.count_nonzero(index < 0))
    above = int(np.count_nonzero(index >= CHART_BARS))
    inside = np.bincount(index[(index >= 0) & (index < CHART_BARS)], minlength=CHART_BARS)
    bars = [ChartBin(low=None, high=float(edges[0]), count=below)]
    bars += [ChartBin(low=float(edges[i]), high=float(edges[i + 1]), count=int(inside[i])) for i in range(CHART_BARS)]
    bars.append(ChartBin(low=float(edges[-1]), high=None, count=above))
    return tuple(bars)


def _nice(width: float) -> float:
    """The smallest round bar width (1, 2, 2.5 or 5 times a power of ten) at least `width`.

    Widths are whole cents (2.5 cents is skipped), so every edge is exact when stored in cents.
    """
    power = math.floor(math.log10(width))
    for step in _NICE_STEPS:
        candidate = round(step * 10.0**power, 10)
        whole_cents = abs(candidate * 100 - round(candidate * 100)) < 1e-6
        if candidate >= width and whole_cents:
            return candidate
    raise AssertionError("unreachable: 10 * 10**power always covers width")
