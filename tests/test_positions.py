"""Building Positions from fills (FR-3, AD-7, AD-10, AD-11, AD-12; Story 1.2)."""

from __future__ import annotations

import random

import pytest

from liquidoracle.core.positions import build_positions, is_resolved
from liquidoracle.records import ActivityRow, ExclusionReason, Market, Position, PositionSet

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
) -> Market:
    return Market(
        condition_id=condition_id,
        closed=closed,
        closed_time=closed_time,
        token_ids=(YES, NO),
        outcome_prices=prices,
        fees_enabled=fees,
    )


def buy(size: float, price: float, *, token: str = YES, cash: float | None = None, t: int = 1, cid: str = M) -> ActivityRow:
    usdc = size * price if cash is None else cash
    return ActivityRow("TRADE", cid, t, size, usdc, price, token_id=token, side="BUY")


def sell(size: float, price: float, *, token: str = YES, t: int = 2, cid: str = M) -> ActivityRow:
    return ActivityRow("TRADE", cid, t, size, size * price, price, token_id=token, side="SELL")


def market_row(kind: str, *, cid: str = M) -> ActivityRow:
    return ActivityRow(kind, cid, 3, 100.0, 100.0, 0.5)


def build(fills: list[ActivityRow], *markets: Market) -> PositionSet:
    return build_positions(fills, {m.condition_id: m for m in (markets or (market(),))})


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


def test_sliver_limits_are_strict() -> None:
    """AD-11, PRD Glossary Sliver: exactly 1% left (0.9 share of 90) is not under 1%, so the Position is tested."""
    result = build([buy(90, 0.30), sell(89.1, 0.50)])
    assert result.tested[0].shares_held == pytest.approx(0.9)
    assert result.slivers == ()


def test_selling_more_than_bought_is_not_explained() -> None:
    """AD-11: BUY 100, SELL 120 gives s = -20, outside 0 < s <= shares bought, so 'not explained'."""
    position = only(build([buy(100, 0.40), sell(120, 0.50)]))
    assert position.reason is ExclusionReason.NOT_EXPLAINED
    assert position.shares_held == -20


def test_a_token_with_sells_only_is_not_explained() -> None:
    """AD-11: a SELL with no BUY has no Entry Price and is left out as 'not explained'."""
    position = only(build([sell(50, 0.50)]))
    assert position.reason is ExclusionReason.NOT_EXPLAINED
    assert position.entry_price is None
    assert position.exit_pnl is None


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
    """AD-12: in a fee Market, 100 shares @ 0.50 paid with 50.75 cash give an Own Fee of 0.75."""
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
    """AD-11: window size = tested + Slivers + every left-out count, and pages print only from this record."""
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
    first = build_positions(fills, markets)
    shuffled = list(fills)
    random.Random(44).shuffle(shuffled)
    assert build_positions(shuffled, markets) == first
    assert build_positions(iter(fills), markets) == first
    assert [(p.condition_id, p.token_id) for p in first.tested] == sorted((p.condition_id, p.token_id) for p in first.tested)


@pytest.mark.parametrize(
    "bad",
    [
        ActivityRow("TRADE", M, 1, 10.0, 4.0, 0.4, token_id=None, side="BUY"),
        ActivityRow("TRADE", M, 1, 10.0, 4.0, 0.4, token_id=YES, side=None),
        ActivityRow("REWARD", M, 1, 10.0, 4.0, 0.4),
    ],
)
def test_malformed_rows_are_refused(bad: ActivityRow) -> None:
    """AD-2, AD-10: a TRADE row without token or side, or an unknown row type, raises ValueError instead of a silent wrong count."""
    with pytest.raises(ValueError):
        build([bad])
