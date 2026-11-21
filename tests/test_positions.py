"""Building Positions from fills (FR-3, AD-7, AD-10, AD-11, AD-12; Story 1.2)."""

from __future__ import annotations

import random

import pytest

from liquidoracle.core.positions import build_positions, fee_passes, is_resolved, mostly_left_out
from liquidoracle.records import ActivityRow, ExclusionReason, ListedPosition, Market, Position, PositionSet

CENT = 0.005  # tests compare money to the cent (Consistency Conventions)

M = "0xmarket"
YES, NO = "yes-token", "no-token"


def market(
    condition_id: str = M,
    *,
    closed: bool = True,
    closed_time: int | None = 1_750_000_000,
    prices: tuple[float, ...] = (1.0, 0.0),
    fees: bool = False,
    schedule: tuple[float, float] | None = (0.03, 1.0),
) -> Market:
    """A fee Market gets Gamma's usual taker schedule, rate 0.03 and exponent 1, unless told otherwise (AD-12)."""
    rate, exponent = schedule if fees and schedule else (None, None)
    return Market(
        condition_id=condition_id,
        closed=closed,
        closed_time=closed_time,
        token_ids=(YES, NO),
        outcome_prices=prices,
        fees_enabled=fees,
        fee_rate=rate,
        fee_exponent=exponent,
    )


def buy(size: float, price: float, *, token: str = YES, cash: float | None = None, t: int = 1, cid: str = M) -> ActivityRow:
    usdc = size * price if cash is None else cash
    return ActivityRow("TRADE", cid, t, size, usdc, price, token_id=token, side="BUY")


def sell(size: float, price: float, *, token: str = YES, t: int = 2, cid: str = M) -> ActivityRow:
    return ActivityRow("TRADE", cid, t, size, size * price, price, token_id=token, side="SELL")


def market_row(kind: str, *, cid: str = M) -> ActivityRow:
    return ActivityRow(kind, cid, 3, 100.0, 100.0, 0.5)


def listed_for(fills: list[ActivityRow]) -> list[ListedPosition]:
    """A positions list that agrees with the fills: one row per traded token, shares bought = its BUY sizes (AD-10)."""
    bought: dict[tuple[str, str], float] = {}
    times: dict[tuple[str, str], list[int]] = {}
    for row in fills:
        if row.type == "TRADE" and row.token_id:
            key = (row.condition_id, row.token_id)
            bought[key] = bought.get(key, 0.0) + (row.size if row.side == "BUY" else 0.0)
            times.setdefault(key, []).append(row.timestamp)
    return [ListedPosition(c, t, "CLOSED", bought[(c, t)], min(times[(c, t)]), max(times[(c, t)])) for c, t in sorted(bought)]


def build(fills: list[ActivityRow], *markets: Market, listed: list[ListedPosition] | None = None) -> PositionSet:
    return build_positions(
        fills, {m.condition_id: m for m in (markets or (market(),))}, listed=listed_for(fills) if listed is None else listed
    )


def only(result: PositionSet) -> Position:
    everything = result.tested + result.slivers + result.left_out
    assert len(everything) == 1
    return everything[0]


# --- The I/O matrix -----------------------------------------------------------------------


def test_several_buys_make_one_position_at_the_share_weighted_price() -> None:
    """FR-3: BUY 100 @ 0.40 and BUY 300 @ 0.60 of one token form one Position, p = 0.55, s = 400."""
    result = build([buy(100, 0.40), buy(300, 0.60, t=5)])
    assert result.tested_count == 1
    position = result.tested[0]
    assert position.entry_price == pytest.approx(0.55)
    assert position.shares_held == 400
    assert position.shares_bought == 400
    assert position.outcome == 1.0


def test_partly_sold_position_enters_at_shares_held_and_original_price() -> None:
    """FR-3, PRD Glossary Exit PnL: BUY 100 @ 0.40, SELL 40 @ 0.70 is tested with s = 60 at p = 0.40, Exit PnL 12.00."""
    result = build([buy(100, 0.40), sell(40, 0.70)])
    position = result.tested[0]
    assert position.shares_held == 60
    assert position.entry_price == pytest.approx(0.40)
    assert position.exit_pnl == pytest.approx(12.00, abs=CENT)
    assert position.reason is None
    assert isinstance(build([buy(100, 0.40)]).tested[0].exit_pnl, float)  # 0.0, not the int 0


def test_sells_never_change_the_entry_price() -> None:
    """AD-10 (Edvard, 2026-11-11): buy, sell, buy again keeps p at the average of all buys, unlike Polymarket's avg_price."""
    result = build([buy(100, 0.40, t=1), sell(100, 0.70, t=2), buy(100, 0.60, t=3)])
    position = result.tested[0]
    assert position.entry_price == pytest.approx(0.50)
    assert position.shares_held == 100
    assert position.exit_pnl == pytest.approx(100 * (0.70 - 0.50), abs=CENT)


def test_fully_sold_position_is_left_out_and_keeps_its_exit_pnl() -> None:
    """FR-3, AD-11: BUY 100 then SELL 100 is 'sold before resolution', with its (negative) Exit PnL kept."""
    result = build([buy(100, 0.60), sell(100, 0.45)])
    assert result.tested_count == 0
    position = only(result)
    assert position.reason is ExclusionReason.SOLD_BEFORE_RESOLUTION
    assert position.exit_pnl == pytest.approx(-15.00, abs=CENT)
    assert result.excluded_counts[ExclusionReason.SOLD_BEFORE_RESOLUTION] == 1


def test_a_tiny_remainder_is_a_sliver() -> None:
    """AD-11, PRD Glossary Sliver: BUY 1,000 then SELL 999.5 leaves 0.5 share (0.05%), a Sliver, neither tested nor left out."""
    result = build([buy(1000, 0.30), sell(999.5, 0.50)])
    assert result.tested_count == 0
    assert result.left_out == ()
    assert len(result.slivers) == 1
    sliver = result.slivers[0]
    assert sliver.shares_held == 0.5
    assert sliver.reason is None
    assert sliver.outcome == 1.0  # its money still counts (Story 1.4)
    assert result.window_size == 1


@pytest.mark.parametrize(
    ("bought", "sold"),
    [
        (1000, 995),  # 0.5% left, but 5 shares
        (20, 19.5),  # 0.5 share, but 2.5% left
    ],
)
def test_a_sliver_needs_both_limits(bought: float, sold: float) -> None:
    """AD-11, PRD Glossary Sliver: under 1% of bought AND under 1 share; meeting only one keeps the Position tested."""
    result = build([buy(bought, 0.30), sell(sold, 0.50)])
    assert result.tested_count == 1
    assert result.slivers == ()


@pytest.mark.parametrize("bought", [35, 57, 70, 90])
def test_exactly_one_percent_left_is_not_a_sliver(bought: float) -> None:
    """AD-11, PRD Glossary Sliver: exactly 1% left is not under 1%, also where 0.01 * bought is a hair above it in floats (70)."""
    result = build([buy(bought, 0.30), sell(round(bought * 0.99, 6), 0.50)])
    assert result.tested_count == 1
    assert result.slivers == ()


def test_exactly_one_share_left_is_not_a_sliver() -> None:
    """AD-11, PRD Glossary Sliver: 1 share of 1,000 is under 1% but not under 1 share, so the Position is tested."""
    result = build([buy(1000, 0.30), sell(999, 0.50)])
    assert result.tested[0].shares_held == 1
    assert result.slivers == ()


def test_a_losing_sliver_keeps_its_loss() -> None:
    """AD-11, PRD Glossary Sliver: a Sliver on the losing outcome is set apart with o = 0, so its loss still counts in Story 1.4."""
    result = build([buy(1000, 0.30, token=NO), sell(999.5, 0.50, token=NO)])
    assert result.tested_count == 0
    assert [s.outcome for s in result.slivers] == [0.0]


def test_selling_more_than_bought_is_not_explained() -> None:
    """AD-11: BUY 100, SELL 120 gives s = -20, outside 0 < s <= shares bought, so 'not explained'."""
    position = only(build([buy(100, 0.40), sell(120, 0.50)]))
    assert position.reason is ExclusionReason.NOT_EXPLAINED
    assert position.shares_held == -20


def test_a_token_with_sells_only_is_left_out_without_an_entry_price() -> None:
    """AD-11: a SELL with no BUY has no Entry Price. Since Story 2.3 it is left out by the list checks
    before 'not explained' is reached: a share gap of 1 when listed, 'only in activity rows' when not."""
    listed_one = only(build([sell(50, 0.50)]))
    assert (listed_one.reason, listed_one.share_gap) == (ExclusionReason.SHARE_GAP, 1.0)
    assert listed_one.entry_price is None
    assert listed_one.exit_pnl is None
    assert only(build([sell(50, 0.50)], listed=[])).reason is ExclusionReason.ONLY_IN_ACTIVITY


@pytest.mark.parametrize("kind", ["SPLIT", "MERGE", "CONVERSION"])
def test_split_merge_or_conversion_leaves_the_whole_market_out(kind: str) -> None:
    """AD-11: one SPLIT, MERGE or CONVERSION row puts every Position in that Market out as 'split or merged'."""
    other = market("0xother")
    fills = [
        buy(100, 0.40),
        buy(50, 0.60, token=NO),
        market_row(kind),
        buy(10, 0.50, cid="0xother"),
    ]
    result = build(fills, market(), other)
    assert result.excluded_counts[ExclusionReason.SPLIT_OR_MERGED] == 2
    assert [p.condition_id for p in result.tested] == ["0xother"]


@pytest.mark.parametrize(
    "resolved_market",
    [
        market(prices=(0.5, 0.5)),  # 50-50
        market(closed_time=None),  # no resolution time
        market(prices=(1.0, 1.0)),
        market(prices=(0.0, 0.0)),
        market(prices=(0.98, 0.02)),
        Market(M, True, 1_750_000_000, (YES, NO, "third"), (1.0, 0.0)),  # lists out of step
    ],
)
def test_closed_market_without_a_clean_resolution_is_unclear(resolved_market: Market) -> None:
    """AD-7: a closed Market that is not exactly {0, 1} with a resolution time is 'unclear resolution'."""
    assert not is_resolved(resolved_market)
    position = only(build([buy(100, 0.40)], resolved_market))
    assert position.reason is ExclusionReason.UNCLEAR_RESOLUTION
    assert position.outcome is None


def test_resolved_market_is_recognised() -> None:
    """AD-7: closed, prices exactly {0, 1} in either order, and a resolution time make a Market resolved."""
    assert is_resolved(market(prices=(1.0, 0.0)))
    assert is_resolved(market(prices=(0.0, 1.0)))
    assert not is_resolved(market(closed=False))


def test_open_or_unknown_markets_are_outside_the_window() -> None:
    """AD-7: fills in a Market that is not closed, or has no Market record, are not counted at all."""
    fills = [buy(100, 0.40), buy(100, 0.40, cid="0xopen"), buy(100, 0.40, cid="0xunknown")]
    result = build(fills, market(), market("0xopen", closed=False, closed_time=None, prices=(0.6, 0.4)))
    assert result.window_size == 1
    assert result.tested_count == 1
    assert sum(result.excluded_counts.values()) == 0


def test_redeem_rows_never_change_shares() -> None:
    """AD-10: REDEEM rows are never a share source; a lost, unredeemed Position still has its bought shares."""
    redeem = ActivityRow("REDEEM", M, 9, 100.0, 100.0, 0.0)
    with_redeem = build([buy(100, 0.40), redeem])
    without = build([buy(100, 0.40)])
    assert with_redeem == without
    lost = only(build([buy(100, 0.40, token=NO)]))
    assert lost.outcome == 0.0
    assert lost.shares_held == 100


def test_own_fee_is_cash_paid_minus_shares_times_price() -> None:
    """AD-12: in a fee Market, 100 shares @ 0.50 paid with 50.75 cash give an Own Fee of 0.75 (= 100 x 0.03 x 0.5 x 0.5, so it passes)."""
    position = only(build([buy(100, 0.50, cash=50.75)], market(fees=True)))
    assert position.own_fees == pytest.approx(0.75, abs=CENT)


def test_no_own_fee_outside_fee_markets_and_none_on_sells() -> None:
    """AD-12: fees are read only in Markets with fees enabled, and only on BUY fills."""
    no_fee_market = only(build([buy(100, 0.50, cash=50.75)], market(fees=False)))
    assert no_fee_market.own_fees == 0.0
    sell_row = ActivityRow("TRADE", M, 2, 40.0, 27.5, 0.70, token_id=YES, side="SELL")
    with_sell = only(build([buy(100, 0.50, cash=50.75), sell_row], market(fees=True)))
    assert with_sell.own_fees == pytest.approx(0.75, abs=CENT)


def test_no_fills_give_an_empty_window() -> None:
    """AD-11: no fills give window 0, tested 0, and a zero count for every reason."""
    result = build([])
    assert result.window_size == 0
    assert result.tested_count == 0
    assert result.excluded_counts == {reason: 0 for reason in ExclusionReason}


# --- Rules across the matrix --------------------------------------------------------------


def test_one_reason_per_position_in_a_fixed_order() -> None:
    """AD-11: unclear resolution beats split or merged, which beats sold before resolution."""
    unclear_and_split = only(build([buy(100, 0.4), sell(100, 0.5), market_row("SPLIT")], market(prices=(0.5, 0.5))))
    assert unclear_and_split.reason is ExclusionReason.UNCLEAR_RESOLUTION
    split_and_sold = only(build([buy(100, 0.4), sell(100, 0.5), market_row("MERGE")]))
    assert split_and_sold.reason is ExclusionReason.SPLIT_OR_MERGED


def test_float_noise_does_not_leave_shares_held() -> None:
    """AD-11: buys of 10.1 and 20.2 sold as 30.3 are fully sold, although the float difference is about 3.6e-15."""
    assert 10.1 + 20.2 - 30.3 != 0
    position = only(build([buy(10.1, 0.40), buy(20.2, 0.40, t=2), sell(30.3, 0.50, t=3)]))
    assert position.reason is ExclusionReason.SOLD_BEFORE_RESOLUTION


def test_token_missing_from_its_market_is_unclear() -> None:
    """AD-7: a fill whose token is not one of its Market's outcomes cannot be resolved, so 'unclear resolution'."""
    position = only(build([buy(100, 0.40, token="stranger")]))
    assert position.reason is ExclusionReason.UNCLEAR_RESOLUTION


def test_window_adds_up() -> None:
    """AD-11: window size = tested + Slivers + every left-out count."""
    fills = [
        buy(100, 0.40, cid="0xa"),  # tested
        buy(100, 0.40, cid="0xb"),
        sell(100, 0.50, cid="0xb"),  # sold
        buy(1000, 0.40, cid="0xc"),
        sell(999.5, 0.50, cid="0xc"),  # sliver
        buy(100, 0.40, cid="0xd"),
        market_row("SPLIT", cid="0xd"),  # split
        buy(100, 0.40, cid="0xe"),
        sell(150, 0.50, cid="0xe"),  # not explained
    ]
    markets = [market(c) for c in ("0xa", "0xb", "0xc", "0xd", "0xe")]
    result = build(fills, *markets)
    assert result.tested_count == 1
    assert len(result.slivers) == 1
    assert result.window_size == result.tested_count + len(result.slivers) + sum(result.excluded_counts.values()) == 5


def test_builder_is_pure_and_order_independent() -> None:
    """AD-11, FR-3: the same fills in any order, built twice, give the same result, sorted by Market then token."""
    fills = [
        buy(33.3, 0.41, cid="0xb", t=1),
        buy(66.7, 0.43, cid="0xb", t=2),
        sell(10.1, 0.60, cid="0xb", t=3),
        buy(5, 0.9, token=NO, cid="0xa", t=4),
        buy(7, 0.2, cid="0xa", t=4),
        buy(12.5, 0.55, cid="0xc", t=5),
    ]
    markets = {c: market(c, fees=True) for c in ("0xa", "0xb", "0xc")}
    first = build_positions(fills, markets, listed=listed_for(fills))
    shuffled = list(fills)
    random.Random(44).shuffle(shuffled)
    assert build_positions(shuffled, markets, listed=listed_for(fills)[::-1]) == first
    assert build_positions(iter(fills), markets, listed=iter(listed_for(fills))) == first
    assert [(p.condition_id, p.token_id) for p in first.tested] == sorted((p.condition_id, p.token_id) for p in first.tested)


@pytest.mark.parametrize(
    "bad",
    [
        ActivityRow("TRADE", M, 1, 10.0, 4.0, 0.4, token_id=None, side="BUY"),
        ActivityRow("TRADE", M, 1, 10.0, 4.0, 0.4, token_id="", side="BUY"),  # the shape of non-TRADE rows
        ActivityRow("TRADE", M, 1, 10.0, 4.0, 0.4, token_id=YES, side=None),
        ActivityRow("REWARD", M, 1, 10.0, 4.0, 0.4),
    ],
)
def test_malformed_rows_are_refused(bad: ActivityRow) -> None:
    """AD-2, AD-10: a TRADE row without token or side, or an unknown row type, raises ValueError instead of a silent wrong count."""
    with pytest.raises(ValueError):
        build([bad])


def test_not_fully_read_positions_are_left_out_and_counted() -> None:
    """AD-7, AD-11: every Position in a Market the capped activity read did not finish is left out as
    "not fully read": one with fills read keeps its numbers, one with none read is still counted."""
    later = "0xlater"
    unread_with_fill = ListedPosition(later, YES, "CLOSED", 10.0, 1, 5)
    unread_without = ListedPosition(later, NO, "OPEN", 4.0, 1, 5)
    result = build_positions(
        [buy(10, 0.4), buy(10, 0.3, cid=later)],
        {M: market(), later: market(later)},
        listed=[*listed_for([buy(10, 0.4)]), unread_with_fill, unread_without],
        not_fully_read=[unread_with_fill, unread_without],
    )
    assert len(result.tested) == 1  # the fully read Market is untouched
    reasons = {(p.token_id, p.reason) for p in result.left_out}
    assert reasons == {(YES, ExclusionReason.NOT_FULLY_READ), (NO, ExclusionReason.NOT_FULLY_READ)}
    assert result.excluded_counts[ExclusionReason.NOT_FULLY_READ] == 2
    assert result.window_size == 3
    bare = next(p for p in result.left_out if p.token_id == NO)
    assert (bare.shares_bought, bare.entry_price, bare.outcome) == (4.0, None, 0.0)


# --- Story 2.3: the positions lists, the fee check and the left-out share --------------------

def listed(shares: float, *, token: str = YES, cid: str = M, status: str = "CLOSED") -> ListedPosition:
    return ListedPosition(cid, token, status, shares, 1, 2)


def test_a_token_only_in_activity_rows_is_left_out() -> None:
    """AD-11, FR-3: a traded token on neither positions list is left out as 'only in activity rows', with no gap."""
    position = only(build([buy(100, 0.40)], listed=[]))
    assert position.reason is ExclusionReason.ONLY_IN_ACTIVITY
    assert position.share_gap is None


def test_a_share_gap_above_one_percent_is_left_out_with_its_size() -> None:
    """AD-11: listed 5,000 against 4,895 bought in the activity rows is a 2.1% gap, left out with the gap stored."""
    position = only(build([buy(4895, 0.40)], listed=[listed(5000)]))
    assert position.reason is ExclusionReason.SHARE_GAP
    assert position.share_gap == pytest.approx(0.021)


@pytest.mark.parametrize(("listed_shares", "bought"), [(100, 99), (99, 100), (7, 6.93)])
def test_a_gap_of_exactly_one_percent_is_not_a_share_gap(listed_shares: float, bought: float) -> None:
    """AD-11: exactly 1% either way (and 0.07 of 7, which floats make 1.0000000000000009%) stays in the test."""
    position = only(build([buy(bought, 0.40)], listed=[listed(listed_shares)]))
    assert position.reason is None
    assert position.share_gap == pytest.approx(0.01)


def test_just_over_one_percent_is_a_share_gap() -> None:
    """AD-11: 98.9 bought against 100 listed is a 1.1% gap."""
    assert only(build([buy(98.9, 0.40)], listed=[listed(100)])).reason is ExclusionReason.SHARE_GAP


def test_a_listed_position_with_no_fill_is_counted_as_a_share_gap() -> None:
    """AD-11 (Story 2.3): a listed Position with no TRADE row (0x091596's conversion outputs) no longer vanishes:
    it is counted, left out as 'share gap' with gap 1."""
    result = build([buy(100, 0.40)], listed=[listed(100), listed(1666.6666, token=NO)])
    assert result.tested_count == 1
    bare = only(PositionSet(tested=(), slivers=(), left_out=result.left_out))
    assert (bare.token_id, bare.reason, bare.share_gap, bare.entry_price) == (NO, ExclusionReason.SHARE_GAP, 1.0, None)
    assert result.window_size == 2


def test_a_listed_position_with_zero_shares_and_no_fill_is_counted() -> None:
    """AD-11 (review): a list row of 0 shares with no fill neither crashes nor reads as 'sold before resolution';
    nothing was bought, so it is a share gap of 1, and it is counted."""
    result = build([], listed=[listed(0.0)])
    position = only(result)
    assert (position.reason, position.share_gap) == (ExclusionReason.SHARE_GAP, 1.0)
    assert result.window_size == 1


def test_not_fully_read_beats_the_list_checks_and_a_gap_beats_selling_first() -> None:
    """AD-11 order (review): an unread Market wins over a share gap; a share gap wins over 'not explained'."""
    unread = listed(200)
    result = build_positions([buy(100, 0.4)], {M: market()}, listed=[unread], not_fully_read=[unread])
    assert only(result).reason is ExclusionReason.NOT_FULLY_READ
    gap_and_sold_first = only(build([sell(10, 0.5, t=1), buy(30, 0.4, t=2)], listed=[listed(60)]))
    assert gap_and_sold_first.reason is ExclusionReason.SHARE_GAP


def test_list_reasons_come_after_split_and_unclear_and_before_sold() -> None:
    """AD-11 order (Story 2.3): unclear, split or merged, only in activity rows, share gap, sold before resolution."""
    split = market_row("SPLIT")
    assert only(build([split], listed=[listed(50)])).reason is ExclusionReason.SPLIT_OR_MERGED
    assert only(build([buy(10, 0.4), split], listed=[])).reason is ExclusionReason.SPLIT_OR_MERGED
    unclear = market(prices=(0.5, 0.5))
    assert only(build([buy(10, 0.4)], unclear, listed=[])).reason is ExclusionReason.UNCLEAR_RESOLUTION
    gap_and_sold = only(build([buy(100, 0.4), sell(100, 0.5)], listed=[listed(200)]))
    assert gap_and_sold.reason is ExclusionReason.SHARE_GAP
    only_and_gap = only(build([buy(100, 0.4)], listed=[listed(200, cid="0xother")]))
    assert only_and_gap.reason is ExclusionReason.ONLY_IN_ACTIVITY


def test_listed_positions_outside_the_window_are_ignored() -> None:
    """AD-7: a listed Position in a Market that is not closed, or not known, is outside the window."""
    result = build([], market(closed=False), listed=[listed(10), listed(10, cid="0xunknown")])
    assert result.window_size == 0


def test_selling_before_buying_is_not_explained_even_with_shares_left() -> None:
    """AD-11 (Edvard, 2026-11-21): SELL 10 then BUY 30 ends with 20 held, but the shares sold came from
    outside the fills, so the share count cannot be trusted: 'not explained'."""
    position = only(build([sell(10, 0.5, t=1), buy(30, 0.4, t=2)]))
    assert position.shares_held == 20
    assert position.reason is ExclusionReason.NOT_EXPLAINED


def test_a_sell_and_a_buy_in_the_same_second_count_the_buy_first() -> None:
    """AD-11: within one second the order of rows is unknown, so buys count first."""
    position = only(build([sell(10, 0.5, t=5), buy(30, 0.4, t=5)]))
    assert position.reason is None
    assert position.shares_held == 20


@pytest.mark.parametrize("side", ["before", "after"])
def test_the_same_rules_apply_on_both_sides_of_the_cut_off_date(side: str) -> None:
    """AD-11, FR-3: the builder has no notion of the date; the same fills a year before or after
    1 July 2025 give the same reasons, gaps and fees."""
    cut_off = 1_751_328_000  # 2025-07-01 00:00 UTC
    shift = -365 * 86_400 if side == "before" else 365 * 86_400
    t = cut_off + shift
    a, b, c, d = "0xa", "0xb", "0xc", "0xd"
    fills = [
        buy(100, 0.4, cid=a, t=t), buy(100, 0.4, cid=b, t=t), buy(4895, 0.4, cid=c, t=t),
        sell(10, 0.5, cid=d, t=t), buy(30, 0.4, cid=d, t=t + 1), buy(100, 0.5, cid=a, t=t, token=NO, cash=50.75),
    ]
    markets = [market(x, closed_time=t + 86_400, fees=True) for x in (a, b, c, d)]
    result = build(fills, *markets, listed=[listed(100, cid=a), listed(100, cid=a, token=NO), listed(5000, cid=c),
                                             listed(30, cid=d)])
    reasons = sorted((p.condition_id, p.token_id, p.reason) for p in result.left_out)
    assert reasons == [(b, YES, ExclusionReason.ONLY_IN_ACTIVITY), (c, YES, ExclusionReason.SHARE_GAP),
                       (d, YES, ExclusionReason.NOT_EXPLAINED)]
    assert [(p.token_id, round(p.own_fees, 6)) for p in result.tested] == [(NO, 0.75), (YES, 0.0)]


# The fee check (AD-12): rate 0.03, exponent 1, so 100 shares at 0.50 owe 0.75.

def fee_buy(fee: float, *, size: float = 100, price: float = 0.50) -> ActivityRow:
    return buy(size, price, cash=size * price + fee)


def test_a_taker_fee_on_schedule_passes_and_counts() -> None:
    """AD-12: 0.75 on 100 shares at 0.50 in a 3% Market is the scheduled fee; within $0.0001 of it passes."""
    for fee in (0.75, 0.75009, 0.74991):
        position = only(build([fee_buy(fee)], market(fees=True)))
        assert position.own_fees == pytest.approx(fee, abs=1e-9)
        assert position.failed_fee_count == 0


def test_a_maker_fill_passes_and_counts_as_exactly_zero() -> None:
    """AD-12: a maker fill pays no fee; real rows leave a rounding gap such as -5.1e-7, which counts as 0."""
    position = only(build([fee_buy(-5.1e-7), fee_buy(0.0)], market(fees=True)))
    assert position.own_fees == 0.0
    assert position.failed_fee_count == 0


def test_a_negative_fee_fails_counts_as_zero_and_keeps_the_position() -> None:
    """AD-12 (moved from Story 2.2): a fee of -0.50 fails, counts as 0, is recorded with its value, and its
    Position stays in the test."""
    result = build([fee_buy(-0.50), fee_buy(0.75)], market(fees=True))
    position = only(result)
    assert position.reason is None and position in result.tested
    assert position.own_fees == pytest.approx(0.75)
    assert (position.failed_fee_count, position.failed_fees) == (1, pytest.approx(-0.50))
    assert (result.failed_fee_count, result.failed_fee_total) == (1, pytest.approx(-0.50))


def test_a_fee_off_schedule_fails() -> None:
    """AD-12: 1.25 where the schedule says 0.75 (a 5% fill in a Market now at 3%) fails, as does 0.7502."""
    for fee in (1.25, 0.7502, 0.3):
        position = only(build([fee_buy(fee)], market(fees=True)))
        assert position.own_fees == 0.0
        assert (position.failed_fee_count, position.failed_fees) == (1, pytest.approx(fee))


def test_with_no_schedule_only_a_zero_fee_passes() -> None:
    """AD-12: fees enabled but no `feeSchedule`: nothing to check a fee against, so only a maker fill passes."""
    no_schedule = market(fees=True, schedule=None)
    assert only(build([fee_buy(0.0)], no_schedule)).failed_fee_count == 0
    assert only(build([fee_buy(0.75)], no_schedule)).failed_fee_count == 1


def test_the_exponent_is_applied_to_p_times_one_minus_p() -> None:
    """AD-12: expected fee = shares x rate x (p(1-p))^exponent; with exponent 2, 100 x 0.03 x 0.0625 = 0.1875."""
    squared = market(fees=True, schedule=(0.03, 2.0))
    assert fee_passes(0.1875, 100, 0.50, squared)
    assert not fee_passes(0.75, 100, 0.50, squared)


def test_only_counted_positions_carry_failed_fees_to_the_card() -> None:
    """AD-12: a failed fee in a left-out Position never counts in Real PnL, so the card does not list it."""
    a, b = "0xa", "0xb"
    fills = [buy(100, 0.5, cid=a, cash=60), buy(100, 0.5, cid=b, cash=60), sell(100, 0.6, cid=b)]
    result = build(fills, market(a, fees=True), market(b, fees=True))
    assert result.left_out[0].failed_fee_count == 1
    assert (result.failed_fee_count, result.failed_fee_total) == (1, pytest.approx(10.0))


def test_the_left_out_share_and_the_ten_percent_flag() -> None:
    """FR-11, AD-11: 3 of 20 left out is 15%, flag on; 2 of 20 is exactly 10%, flag off; an empty window is 0%."""
    def window(left: int) -> PositionSet:
        tested = [buy(10, 0.4, cid=f"0x{i:02}") for i in range(20 - left)]
        sold = [row for i in range(20 - left, 20) for row in (buy(10, 0.4, cid=f"0x{i:02}"), sell(10, 0.5, cid=f"0x{i:02}"))]
        return build(tested + sold, *(market(f"0x{i:02}") for i in range(20)))

    assert (window(3).left_out_share, mostly_left_out(window(3))) == (0.15, True)
    assert (window(2).left_out_share, mostly_left_out(window(2))) == (0.10, False)
    assert build([]).left_out_share == 0.0
