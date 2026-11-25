"""The Skill Test: Real PnL, 10,000 Simulations, the p-value and the Verdict (FR-4 to FR-7).

Only `skill_test` is for the rest of the app. It always applies the 30-bet minimum (FR-6).
`real_pnl` is the one source of Real PnL, shared by `skill_test` and the Scan's ranking (AD-10).
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
UNCOUPLED_NOTE_ABOVE = 0.20  # AD-20 [ASSUMPTION]: above this uncoupled share, the card adds an honesty note

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
    at_or_below: int
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
            sliver_count=slivers, real_pnl=real_pnl(position_set), own_fees=_own_fees(bets),
            simulations=0, at_or_above=None, at_or_below=None, p_value=None, bins=(),
            uncoupled_share=uncoupled_share(position_set.tested),
        )
    run = _engine(bets, seed=seed, unit_id=unit_id)
    return SkillTestResult(
        scope=scope, seed=seed, verdict=verdict_for(run.p_value), tested_count=tested,
        sliver_count=slivers, real_pnl=real_pnl(position_set), own_fees=run.own_fees,
        simulations=SIMULATIONS, at_or_above=run.at_or_above, at_or_below=run.at_or_below,
        p_value=run.p_value, bins=run.bins,
        uncoupled_share=uncoupled_share(position_set.tested),
    )


def verdict_for(p_value: float) -> Verdict:
    """FR-6: p < 0.01 Skilled (high confidence), p < 0.05 Likely skilled, otherwise no evidence."""
    if p_value < SKILLED_BELOW:
        return Verdict.SKILLED
    if p_value < LIKELY_SKILLED_BELOW:
        return Verdict.LIKELY_SKILLED
    return Verdict.NO_EVIDENCE


def uncoupled_share(tested: Sequence[Position]) -> float:
    """AD-20: the share of tested Positions whose Gamma event holds another tested Position not coupled with it.

    Two Positions are coupled when they share a draw: the same Market, or the same negative-risk
    event. Ladders are not detected (Story 2.4), so they count here. 0 for no tested Positions.
    """
    units_per_event: dict[str, set[tuple[str, str]]] = {}
    for bet in tested:
        if bet.event_id is not None:
            units_per_event.setdefault(bet.event_id, set()).add(_unit_key(bet))
    linked = sum(1 for bet in tested if bet.event_id is not None and len(units_per_event[bet.event_id]) > 1)
    return linked / len(tested) if tested else 0.0


def mostly_uncoupled(result: SkillTestResult) -> bool:
    """FR-11 / AD-20: more than 20% of the tested Positions have an uncoupled event-mate."""
    return result.uncoupled_share > UNCOUPLED_NOTE_ABOVE


def _engine(bets: Sequence[Position], *, seed: int, unit_id: str) -> _Run:
    """The Simulations and the p-value, with no minimum. Tests only (see the module docstring)."""
    _check(bets)
    if not bets:
        raise ValueError("the Skill Test needs at least one Position")
    ordered = _ordered(bets)
    draws = _Draws(ordered)

    # Conventions › Money: whole cents once per Position, no fees, so ties count exactly.
    win_cents = [round(b.shares_held * (1.0 - b.entry_price) * 100) for b in ordered]
    loss_cents = [round(-b.shares_held * b.entry_price * 100) for b in ordered]
    real_cents = sum(w if b.outcome == 1.0 else lo for b, w, lo in zip(ordered, win_cents, loss_cents))
    base = sum(loss_cents)
    gain = np.array([w - lo for w, lo in zip(win_cents, loss_cents)], dtype=np.int64)

    generator = _generator(seed, unit_id)
    totals = np.empty(SIMULATIONS, dtype=np.int64)
    for start in range(0, SIMULATIONS, _CHUNK):
        rows = min(_CHUNK, SIMULATIONS - start)
        totals[start:start + rows] = base + draws.won(generator, rows).astype(np.int64) @ gain

    at_or_above = int(np.count_nonzero(totals >= real_cents))
    at_or_below = int(np.count_nonzero(totals <= real_cents))  # FR-9: 0 means below every Simulation
    real_pnl = _real_pnl(ordered)
    own_fees = _own_fees(ordered)
    return _Run(
        real_pnl=real_pnl,
        own_fees=own_fees,
        real_cents=real_cents,
        at_or_above=at_or_above,
        at_or_below=at_or_below,
        p_value=(1 + at_or_above) / (SIMULATIONS + 1),
        bins=_bins(totals / 100.0 - own_fees, real_pnl),
    )


class _Draws:
    """AD-20: which of the ordered Positions win, for a block of Simulations.

    One uniform U per draw unit: a Market, or a whole negative-risk event. In a Market on its own,
    the smaller token_id (as text) wins on U < p and the other side on U > 1 - p (Story 1.4). In a
    negative-risk event, each Market gets a win region of length max(p of its Yes Positions,
    1 - p of its No Positions), laid end to end in condition_id order from 0 and wrapping past 1;
    the Market draws V = (U - start) mod 1, its Yes token wins on V < p and No on V > 1 - p. V is
    uniform, so every Position keeps its win chance, and only one Market's region holds U while
    the lengths sum to at most 1 (Story 2.4). Columns are sorted units, so a Wallet with no
    negative-risk Market draws exactly as before.
    """

    def __init__(self, ordered: Sequence[Position]) -> None:
        tokens = _tokens_per_market(ordered)
        units = sorted({_unit_key(b) for b in ordered})
        column = {unit: i for i, unit in enumerate(units)}
        starts = _region_starts(ordered)
        self.columns = len(units)
        self.unit_of = np.array([column[_unit_key(b)] for b in ordered], dtype=np.intp)
        self.wins_low = np.array(
            [b.yes_side if b.neg_risk_id is not None else b.token_id == min(tokens[b.condition_id]) for b in ordered],
            dtype=bool,
        )
        self.price = np.array([b.entry_price for b in ordered], dtype=np.float64)
        self.start = np.array([starts.get(b.condition_id, 0.0) for b in ordered], dtype=np.float64)

    def won(self, generator: np.random.Generator, rows: int) -> np.ndarray:
        u = generator.random((rows, self.columns))[:, self.unit_of]
        v = np.mod(u - self.start, 1.0)  # a start of 0 leaves U as it is: U is already in [0, 1)
        return np.where(self.wins_low, v < self.price, v > 1.0 - self.price)


def _simulated_wins(
    bets: Sequence[Position], *, seed: int, unit_id: str, simulations: int
) -> tuple[list[Position], np.ndarray]:
    """Tests only: the ordered Positions and who wins in each Simulation, drawn the way `_engine` draws."""
    _check(bets)
    ordered = _ordered(bets)
    return ordered, _Draws(ordered).won(_generator(seed, unit_id), simulations)


def _ordered(bets: Sequence[Position]) -> list[Position]:
    """AD-15: one fixed order, so the draws never depend on the order the Positions came in."""
    return sorted(bets, key=lambda b: (b.condition_id, b.token_id))


def _generator(seed: int, unit_id: str) -> np.random.Generator:
    return rng.generator(seed, "skilltest", unit_id)


def _unit_key(bet: Position) -> tuple[str, str]:
    """The draw a Position shares, its negative-risk event or else its Market (AD-20), as a sortable
    key that never mistakes an event id for a Market id."""
    return ("event", bet.neg_risk_id) if bet.neg_risk_id is not None else ("market", bet.condition_id)


def _region_starts(ordered: Sequence[Position]) -> dict[str, float]:
    """Where each negative-risk Market's win region starts in its event's U (AD-20, Story 2.4)."""
    length: dict[str, float] = {}
    event_of: dict[str, str] = {}
    for bet in ordered:
        if bet.neg_risk_id is None or bet.entry_price is None:
            continue
        reach = bet.entry_price if bet.yes_side else 1.0 - bet.entry_price
        length[bet.condition_id] = max(length.get(bet.condition_id, 0.0), reach)
        event_of[bet.condition_id] = bet.neg_risk_id
    starts: dict[str, float] = {}
    filled: dict[str, float] = {}
    for condition_id in sorted(length):
        event = event_of[condition_id]
        starts[condition_id] = math.fmod(filled.get(event, 0.0), 1.0)
        filled[event] = filled.get(event, 0.0) + length[condition_id]
    return starts


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
    events: dict[str, str | None] = {}
    for bet in bets:
        if events.setdefault(bet.condition_id, bet.neg_risk_id) != bet.neg_risk_id:
            raise ValueError(f"Market {bet.condition_id} has Positions in different negative-risk events")


def _tokens_per_market(bets: Sequence[Position]) -> dict[str, set[str]]:
    tokens: dict[str, set[str]] = {}
    for bet in bets:
        tokens.setdefault(bet.condition_id, set()).add(bet.token_id)
    for condition_id, ids in tokens.items():
        if len(ids) > 2:
            raise ValueError(f"Market {condition_id} has {len(ids)} outcomes in one test; only two are supported")
    return tokens


def real_pnl(position_set: PositionSet) -> float:
    """FR-4, AD-10: the Real PnL of a Position set, over its tested Positions and Slivers.

    The one source of Real PnL: `skill_test` stores it, and the Scan ranks on it (AD-21).
    """
    return _real_pnl((*position_set.tested, *position_set.slivers))


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
