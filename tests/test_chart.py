"""The luck chart, ready to draw (FR-9, UX-DR24, UX-DR25, AD-25; Story 3.1).

Each test names its row of the spec's I/O & Edge-Case Matrix. Planted Wallets are made of 30
one-Market bets, the Skill Test's minimum, so `skill_test` gives them a p-value and a chart.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from liquidoracle.core import phrases, skilltest
from liquidoracle.core.positions import build_positions
from liquidoracle.data import synthetic
from liquidoracle.records import Position, PositionSet, SampleWallet, SkillTestResult
from liquidoracle.services import chart
from liquidoracle.services.chart import Anchor, luck_chart

SEED = 44
SMALL = {wallet.name: wallet for wallet in synthetic.small_wallets()}


def result_of(wallet: SampleWallet) -> SkillTestResult:
    built = build_positions(wallet.activity, {m.condition_id: m for m in wallet.markets}, listed=wallet.positions)
    return skilltest.skill_test(built, seed=SEED, unit_id=wallet.address)


def planted(price: float, won: bool, *, bets: int = 30) -> SkillTestResult:
    """`bets` bets of 100 shares at `price`, each in its own Market, all won or all lost."""
    tested = tuple(
        Position(
            condition_id=f"m{i:05d}", token_id=f"m{i:05d}-0", outcome=1.0 if won else 0.0,
            entry_price=price, shares_bought=100.0, shares_sold=0.0, shares_held=100.0,
            own_fees=0.0, exit_pnl=0.0,
        )
        for i in range(bets)
    )
    return skilltest.skill_test(PositionSet(tested=tested, slivers=(), left_out=()), seed=SEED, unit_id="planted")


def axis_edges(result: SkillTestResult) -> tuple[float, float]:
    return result.bins[0].high, result.bins[-1].low  # type: ignore[return-value]


def test_fr9_normal_sharp_trader() -> None:
    """FR-9, matrix "Normal": $2,000 sits on the axis' top edge (core widened the axis to hold it); one replay is above it."""
    result = result_of(SMALL["sharp-trader"])
    assert (result.real_pnl, result.at_or_above) == (2000.0, 1)
    drawn = luck_chart(result)
    assert drawn.marker_label == "This Wallet: $2,000" and drawn.beyond is None
    assert "below all" not in drawn.text  # inside the curve: no extra sentence (UX-DR24, Story 3.5)
    assert drawn.marker_x == pytest.approx(chart.AXIS_START + skilltest.CHART_BARS)
    assert drawn.anchor is Anchor.END


def test_fr9_above_all_stop_loss_trader() -> None:
    """FR-9, matrix "Above all": no Simulation reached $1,650, so the label's second line says so."""
    result = result_of(SMALL["stop-loss-trader"])
    assert result.at_or_above == 0
    drawn = luck_chart(result)
    assert (drawn.marker_label, drawn.beyond) == ("This Wallet: $1,650", "above all 10,000 Simulations")
    assert "below all" not in drawn.text and drawn.text.endswith("fewer than 1 time in 10,000.")  # UX-DR24, Story 3.5


def test_fr9_planted_above_every_simulation_stretches_the_axis() -> None:
    """FR-9 check: a planted Real PnL above the largest Simulation; the axis holds it and the label says "above all"."""
    result = planted(0.01, won=True)  # 30 long shots that all won: no replay comes close
    low, high = axis_edges(result)
    assert result.at_or_above == 0 and result.real_pnl == pytest.approx(2970.0)
    assert low <= result.real_pnl <= high
    drawn = luck_chart(result)
    assert drawn.beyond == "above all 10,000 Simulations"
    assert chart.AXIS_START <= drawn.marker_x <= chart.AXIS_START + skilltest.CHART_BARS


def test_fr9_planted_below_every_simulation() -> None:
    """FR-9, matrix "Below all": 30 favourites at 0.99 that all lost; no replay is at or below it, the axis holds it."""
    result = planted(0.99, won=False)
    low, high = axis_edges(result)
    assert (result.at_or_above, result.at_or_below) == (skilltest.SIMULATIONS, 0)
    assert low <= result.real_pnl <= high
    drawn = luck_chart(result)
    assert drawn.beyond == "below all 10,000 Simulations"
    assert drawn.marker_left < 50.0  # on the low side; the round axis is wider than the Real PnL itself
    assert drawn.text.endswith(" more than half the time. That is below all 10,000 replays.")  # UX-DR24, Story 3.5


def test_fr9_tie_with_the_lowest_replay_is_not_below_all() -> None:
    """FR-9, matrix "Ties lowest": 30 bets at 0.05 that all lost; about 21% of replays lose every bet too, so they tie."""
    result = planted(0.05, won=False)
    assert result.at_or_above == skilltest.SIMULATIONS and result.at_or_below > 0
    assert luck_chart(result).beyond is None
    assert "below all" not in luck_chart(result).text  # a tie is not below all (UX-DR24, Story 3.5)


def test_fr9_zero_real_pnl_sits_in_the_middle() -> None:
    """FR-9, matrix "Real PnL $0": favourite-buyer's Real PnL (float dust of $0) reads "$0" and the marker is at the centre."""
    result = result_of(SMALL["favourite-buyer"])
    assert result.real_pnl == pytest.approx(0.0, abs=0.005)  # float dust of an exact $0
    drawn = luck_chart(result)
    assert drawn.marker_label == "This Wallet: $0"
    assert drawn.marker_left == pytest.approx(50.0) and drawn.anchor is Anchor.MIDDLE


@pytest.mark.parametrize(
    ("share", "anchor"),
    [(0.0, Anchor.START), (0.1, Anchor.START), (0.2, Anchor.START), (0.5, Anchor.MIDDLE),
     (0.8, Anchor.END), (0.9, Anchor.END), (1.0, Anchor.END)],
)
def test_ux_dr25_marker_label_near_an_edge_is_anchored_inwards(share: float, anchor: Anchor) -> None:
    """UX-DR25, matrix "Marker near an edge": within 25% of a side the label hangs inwards, so it stays on the card."""
    result = result_of(SMALL["favourite-buyer"])
    low, high = axis_edges(result)
    moved = replace(result, real_pnl=low + share * (high - low))
    assert luck_chart(moved).anchor is anchor


@pytest.mark.parametrize(("share", "anchor"), [(0.55, Anchor.END), (0.7, Anchor.END), (0.45, Anchor.START)])
def test_ux_dr25_two_line_label_always_hangs_inwards(share: float, anchor: Anchor) -> None:
    """UX-DR25, FR-9 (Story 3.1 review): "above all 10,000 Simulations" is too wide to centre on a phone, so
    a beyond label hangs towards the middle wherever the marker is; a round axis can leave it at about 75%."""
    result = replace(result_of(SMALL["favourite-buyer"]), at_or_above=0)
    low, high = axis_edges(result)
    moved = replace(result, real_pnl=low + share * (high - low))
    assert luck_chart(moved).anchor is anchor


def test_fr10_not_enough_data_has_no_chart() -> None:
    """FR-10, matrix "Not enough data": a result without a p-value cannot be drawn."""
    result = result_of(SMALL["thin-wallet"])
    assert result.p_value is None
    with pytest.raises(ValueError, match="no luck chart"):
        luck_chart(result)


def test_ux_dr25_tiny_wallet_keeps_cents_on_the_axis() -> None:
    """UX-DR25, matrix "Tiny Wallet": with $0.25 bars the ticks keep their cents and the end bars read "−$5 or less"."""
    totals = np.linspace(-5.0, 5.0, skilltest.SIMULATIONS)
    bins = skilltest._bins(totals, 1.0)
    assert bins[1].high - bins[1].low == pytest.approx(0.25)  # type: ignore[operator]
    result = replace(result_of(SMALL["favourite-buyer"]), bins=bins, real_pnl=1.0)
    drawn = luck_chart(result)
    assert [t.label for t in drawn.ticks] == [
        "−$5", "−$3.75", "−$2.50", "−$1.25", "$0", "$1.25", "$2.50", "$3.75", "$5",
    ]
    assert (drawn.low_label, drawn.high_label) == ("−$5 or less", "$5 or more")
    assert (drawn.low_short, drawn.high_short) == ("−$5 or less", "$5 or more")


def test_ad25_bars_are_the_stored_bins() -> None:
    """AD-25: one bar per stored bin with its own count, the same output every time, and all 10,000 replays drawn."""
    result = result_of(SMALL["sharp-trader"])
    drawn = luck_chart(result)
    assert [bar.count for bar in drawn.bars] == [b.count for b in result.bins]
    assert sum(bar.count for bar in drawn.bars) == skilltest.SIMULATIONS
    assert luck_chart(result) == drawn
    # sharp-trader's tallest bar holds 792 replays, so the gridlines run 0 to 800 in steps of 200.
    assert [(g.level, g.label) for g in drawn.gridlines] == [
        (0.0, "0"), (25.0, "200"), (50.0, "400"), (75.0, "600"), (100.0, "800"),
    ]
    assert all(bar.height == pytest.approx(100.0 * bar.count / 800) for bar in drawn.bars)


def test_ux_dr25_layout_end_bars_gaps_and_ticks() -> None:
    """UX-DR25: end bar, gap, 40 axis bars, gap, end bar; 9 ticks every 5 bars, every other one minor."""
    drawn = luck_chart(result_of(SMALL["sharp-trader"]))
    slots = [round(bar.x - chart.BAR_INSET) for bar in drawn.bars]
    assert slots == [0, *range(2, 42), 43] and drawn.view_width == 44
    assert len(drawn.ticks) == 9
    assert [t.minor for t in drawn.ticks] == [False, True] * 4 + [False]
    assert drawn.ticks[0].left == pytest.approx(100 * 2 / 44) and drawn.ticks[-1].left == pytest.approx(100 * 42 / 44)
    assert [t.short for t in drawn.ticks][::2] == ["−$2k", "−$1k", "$0", "$1k", "$2k"]
    assert (drawn.low_short, drawn.high_short) == ("−$2k or less", "$2k or more")


@pytest.mark.parametrize(
    ("peak", "step"),
    [(1, 1), (4, 1), (5, 2), (931, 500), (792, 200), (1376, 500), (10_000, 5000)],
)
def test_ux_dr25_gridline_steps_are_round(peak: int, step: int) -> None:
    """UX-DR25: at most four gridlines above 0, at 1, 2 or 5 times a power of ten."""
    assert chart._grid_step(peak) == step


# --- Story 3.2: what chart.js shows (UX-DR26, UX-DR27) ------------------------------------------
# chart.js writes no words and counts nothing; every tooltip line, slider step, lit bar and tail
# sentence is decided here, so these tests cover the I/O matrix of spec-3-2.


def test_ux_dr27_normal_tail_from_the_marker_bar() -> None:
    """UX-DR27, 3.2 matrix "Normal" and "Real PnL on the top axis edge": sharp-trader's $2,000 is the axis' top
    edge, which the last axis bar holds (ChartBin), so the tail starts there; the sentence is the exact count."""
    result = result_of(SMALL["sharp-trader"])
    drawn = luck_chart(result)
    assert result.bins[-2].high == 2000.0 == result.real_pnl
    assert drawn.marker_bar == drawn.tail_from == skilltest.CHART_BARS  # bin 40: the last axis bar
    assert drawn.tail_text == "1 of 10,000 replays did this well or better"
    assert drawn.marker_button_label == "This Wallet: $2,000. Highlight the replays that did this well or better"


def test_ux_dr27_none_reached_lights_nothing() -> None:
    """UX-DR27, 3.2 matrix "None reached": stop-loss-trader beat every replay; no bar is lit."""
    drawn = luck_chart(result_of(SMALL["stop-loss-trader"]))
    assert drawn.tail_from == len(drawn.bars) == skilltest.CHART_BARS + 2
    assert drawn.tail_text == "No replay did this well or better"


def test_ux_dr27_all_reached_lights_every_bar() -> None:
    """UX-DR27, 3.2 matrix "All reached": a Wallet that lost every bet ties the lowest replay, so all 10,000 did as well."""
    result = planted(0.05, won=False)
    assert result.at_or_above == skilltest.SIMULATIONS
    drawn = luck_chart(result)
    assert drawn.tail_from == 0
    assert drawn.tail_text == "All 10,000 replays did this well or better"


@pytest.mark.parametrize("share", [0.0, 0.3, 0.5, 0.5125, 0.77, 1.0])
def test_ux_dr27_marker_bar_holds_the_real_pnl(share: float) -> None:
    """UX-DR27: the marker's bar is the one whose range holds the Real PnL, by core's rule (low edge in, top edge
    in the last axis bar); a value exactly on an inner edge belongs to the bar that starts there."""
    result = result_of(SMALL["favourite-buyer"])
    low, high = axis_edges(result)
    moved = replace(result, real_pnl=low + share * (high - low))
    drawn = luck_chart(moved)
    held = moved.bins[drawn.marker_bar]
    assert 1 <= drawn.marker_bar <= skilltest.CHART_BARS
    assert held.low is not None and held.high is not None
    assert held.low <= moved.real_pnl < held.high or (moved.real_pnl == held.high == high)
    assert drawn.tail_from == drawn.marker_bar  # some but not all replays reached it
    assert drawn.tail_left is (share > 0.5)  # the tail label hangs towards the middle, so it stays on the card


def test_ux_dr26_every_bar_carries_its_range_and_count() -> None:
    """UX-DR26: each bar's tooltip and slider text are the phrases for its own stored bin; the end bars read as labels."""
    result = result_of(SMALL["sharp-trader"])
    drawn = luck_chart(result)
    assert [(b.range_text, b.count_text) for b in drawn.bars] == [
        (phrases.bar_range(b.low, b.high), phrases.replays(b.count)) for b in result.bins
    ]
    assert drawn.bars[0].range_text == drawn.low_label == "−$2,000 or less"
    assert drawn.bars[-1].range_text == drawn.high_label == "$2,000 or more"
    assert drawn.bars[1].range_text == "−$2,000 to −$1,900"


def test_ux_dr26_explore_words_come_only_with_the_script() -> None:
    """UX-DR26 (Edvard, 2026-11-23): the explore hint and About's fourth paragraph; the 3.1 hint is unchanged."""
    drawn = luck_chart(result_of(SMALL["sharp-trader"]))
    assert drawn.hint == "Each bar is a range of results. The taller the bar, the more replays ended there."
    assert drawn.explore_hint == "Point at a bar, or use the arrow keys, to see how many replays ended there."
    assert drawn.about_explore.startswith("Point at a bar, or step through the bars with the arrow keys")
    assert len(drawn.about) == 3


def test_ux_dr27_about_explains_why_the_tail_count_and_the_odds_differ() -> None:
    """UX-DR27, FR-5 (Edvard, 2026-11-24, Story 3.3): the tail label's count and the odds differ by the p-value's +1,
    so the script-only About paragraph, shown with the tail label, says why."""
    drawn = luck_chart(result_of(SMALL["sharp-trader"]))
    assert drawn.tail_text == "1 of 10,000 replays did this well or better"
    assert drawn.about_explore.endswith(
        "The odds above count this Wallet's own result as one more replay, so they read a little less rare than this "
        "count and never claim zero."
    )
