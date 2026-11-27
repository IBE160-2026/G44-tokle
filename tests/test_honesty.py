"""The honesty notes, ready to show (FR-11, UX-DR15, UX-DR29, AD-11; Story 3.3).

Each test names its row of the spec's I/O & Edge-Case Matrix. Real Wallets are loaded from the committed
Sample Dataset into a temporary database, as `load-sample` does.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from liquidoracle.core import phrases, skilltest
from liquidoracle.core.positions import build_positions
from liquidoracle.data import synthetic
from liquidoracle.data.offline import REAL_DIR, OfflineClient
from liquidoracle.data.store import Store
from liquidoracle.records import ExclusionReason, Position, PositionSet, SampleWallet
from liquidoracle.services.fetch import StoredResult, fetch_wallet, stored_result
from liquidoracle.services.honesty import HonestyNotes, honesty_notes

SEED = 44
SMALL = {wallet.name: wallet for wallet in synthetic.small_wallets()}
COMMITTED = Path(__file__).resolve().parents[1] / REAL_DIR
REAL = {
    "0xd218e4": "0xd218e474776403a330142299f7796e8ba32eb5c9",  # every bet not fully read, capped
    "0xd3a6e5": "0xd3a6e523c440f94f9259398fbcf7b5cc5ccffd55",  # every kind of reason, not capped
    "0x94884d": "0x94884db79666a1a34c46d03fb4f8e9cbcaf6b5a6",  # capped at 2,000
    "0xcf0d7f": "0xcf0d7f69cf162918b33fc1ea7449583fa537132d",  # the decision log's Exit PnL example
}


def stored_of(wallet: SampleWallet, *, capped: bool = False) -> StoredResult:
    built = build_positions(wallet.activity, {m.condition_id: m for m in wallet.markets}, listed=wallet.positions)
    return StoredResult(skilltest.skill_test(built, seed=SEED, unit_id=wallet.address), 0, built, capped, len(wallet.positions))


def stored_from(position_set: PositionSet, *, capped: bool = False) -> StoredResult:
    return StoredResult(
        skilltest.skill_test(position_set, seed=SEED, unit_id="planted"), 0, position_set, capped, position_set.window_size
    )


def bet(n: int, *, price: float, won: bool, shares: float = 100.0, **extra: object) -> Position:
    fields: dict = dict(
        condition_id=f"m{n:05d}", token_id=f"m{n:05d}-0", outcome=1.0 if won else 0.0, entry_price=price,
        shares_bought=shares, shares_sold=0.0, shares_held=shares, own_fees=0.0, exit_pnl=0.0,
    )
    fields.update(extra)
    return Position(**fields)


@pytest.fixture(scope="module")
def real(tmp_path_factory: pytest.TempPathFactory) -> dict[str, HonestyNotes]:
    store = Store(tmp_path_factory.mktemp("honesty") / "offline.db")
    notes = {}
    try:
        for short, address in REAL.items():
            fetch_wallet(OfflineClient([COMMITTED / f"{address}.json"]), store, address)
            found = stored_result(store, address, seed=SEED)
            assert found is not None
            notes[short] = honesty_notes(found)
    finally:
        store.close()
    return notes


def test_fr11_share_sharp_trader() -> None:
    """FR-11, matrix "Share": $50 of $2,000 came from the largest bet."""
    notes = honesty_notes(stored_of(SMALL["sharp-trader"]))
    assert (notes.largest_label, notes.largest_figure, notes.largest_text) == (
        "", "3%", "of the Real PnL came from the single largest bet."
    )


def test_fr11_over_100_percent() -> None:
    """FR-11, matrix "Over 100%": Real PnL $8, the largest bet $87, the other lost $79."""
    planted = PositionSet(
        tested=(bet(0, price=0.13, won=True), bet(1, price=1.0, won=False, shares=79.0)), slivers=(), left_out=()
    )
    notes = honesty_notes(stored_from(planted))
    assert notes.largest_figure == "$87" and notes.largest_text == (
        "More than all of the Real PnL came from the single largest bet ($87); the other bets lost money overall."
    )


@pytest.mark.parametrize(("wallet", "amount"), [(SMALL["favourite-buyer"], "$10"), (synthetic.coin_flipper(0), "$90")],
                         ids=["favourite-buyer", "coin-flipper-0000"])
def test_fr11_real_pnl_at_or_below_zero(wallet: SampleWallet, amount: str) -> None:
    """FR-11, matrix "Real PnL ≤ $0": favourite-buyer's Real PnL is float noise around $0, coin-flipper-0000 lost."""
    notes = honesty_notes(stored_of(wallet))
    assert (notes.largest_label, notes.largest_figure, notes.largest_text) == ("Largest single bet:", amount, "")


def test_fr11_no_bets_and_capped(real: dict[str, HonestyNotes]) -> None:
    """FR-11, matrix "No bets" and "Capped window": 0xd218e4's 2,000 bets are all not fully read."""
    notes = real["0xd218e4"]
    assert notes.largest_text == "No resolved bets to measure." and notes.largest_figure == ""
    assert notes.held_figure == "" and notes.held_text == "No bet's history was read in full, so this cannot be counted."
    # Story 3.3 review: nothing was read in full, so the card claims nothing about sales or fees.
    assert notes.exit_text == "" and notes.exit_parts == ("", "", "") and notes.fees == ""
    assert notes.left_out == "Left out of the test: 2,000 not fully read."
    assert notes.mostly_left_out == "Only part of this Wallet's activity was judged: 100% of its bets were left out."
    assert notes.window == "Based on the latest 2,000 bets; older results are not included."


def test_fr11_stop_loss_trader_shows_the_warning() -> None:
    """FR-11 check, matrix "Stop-loss": the stop-loss Synthetic Wallet shows the warning, its held count and Exit PnL."""
    notes = honesty_notes(stored_of(SMALL["stop-loss-trader"]))
    assert notes.exit_warning == (
        "Positions this Wallet sold before resolution lost money in total.",
        "This Verdict covers only bets held to resolution.",
    )
    assert (notes.held_figure, notes.held_text) == ("33 of 100", "positions held to resolution.")
    assert notes.exit_text == "Shares sold before resolution: −$1,675 (Exit PnL)."


def test_fr11_no_sales_shows_no_warning() -> None:
    """FR-11 check, matrix "No sales": favourite-buyer sold nothing, so no warning and no Exit PnL amount
    (sharp-trader sells its anchor bets since Story 4.6)."""
    notes = honesty_notes(stored_of(SMALL["favourite-buyer"]))
    assert notes.exit_warning is None and notes.held_figure == "100 of 100"
    assert notes.exit_text == "No shares were sold before resolution."
    assert notes.left_out == "Left out of the test: none." and notes.mostly_left_out == ""


def test_fr11_exit_pnl_at_or_above_zero_shows_no_warning(real: dict[str, HonestyNotes]) -> None:
    """FR-11 check: a Wallet with early sales and Exit PnL ≥ 0 (0xd3a6e5, $194,660) shows no warning."""
    assert real["0xd3a6e5"].exit_text == "Shares sold before resolution: $194,660 (Exit PnL)."
    assert real["0xd3a6e5"].exit_warning is None


def test_fr11_mixed_reasons_not_capped(real: dict[str, HonestyNotes]) -> None:
    """FR-11, matrix "Mixed reasons" and "Not capped" (Edvard, 2026-11-24): 939 of 1,173 held, though 641 are tested."""
    notes = real["0xd3a6e5"]
    assert notes.held_figure == "939 of 1,173"
    assert notes.left_out == (
        "Left out of the test: 5 unclear resolution, 287 split or merged, 6 Polymarket's two lists disagree, "
        "95 sold before resolution."
    )
    assert notes.mostly_left_out == "Only part of this Wallet's activity was judged: 34% of its bets were left out."
    assert notes.window == "" and notes.computed_on == "Computed on all 1,173 bets · Seed 44"


def test_fr11_capped_window(real: dict[str, HonestyNotes]) -> None:
    """FR-11, AD-22, matrix "Capped window": 0x94884d's window was cut at 2,000."""
    notes = real["0x94884d"]
    assert notes.window == "Based on the latest 2,000 bets; older results are not included."
    assert notes.computed_on == "Computed on the latest 2,000 bets · Seed 44"


@pytest.mark.parametrize(("share", "shown"), [(0.34, True), (0.20, False)])
def test_fr11_linked_bets_note_above_20_percent(share: float, shown: bool) -> None:
    """FR-11, AD-20, matrix "Linked over 20%": the note shows above 20% of the tested bets, not at 20%."""
    stored = stored_of(SMALL["sharp-trader"])
    notes = honesty_notes(replace(stored, result=replace(stored.result, uncoupled_share=share)))
    assert notes.linked.startswith("34% of the tested bets share an event") if shown else notes.linked == ""


def test_fr11_fees_that_failed_the_check() -> None:
    """FR-4, FR-11, matrix "Fees failed": three fees with a recorded $0.40 between them."""
    planted = PositionSet(
        tested=(bet(0, price=0.5, won=True, failed_fee_count=2, failed_fees=0.3),
                bet(1, price=0.5, won=False, failed_fee_count=1, failed_fees=0.1)),
        slivers=(), left_out=(),
    )
    notes = honesty_notes(stored_from(planted))
    assert notes.fees == "3 fees did not match the Market's fee schedule and were not counted (less than $1)."
    assert honesty_notes(stored_of(SMALL["sharp-trader"])).fees == "Every fee matched the Market's fee schedule."


def test_fr11_the_fixed_texts_are_on_every_card() -> None:
    """FR-11, UX-DR29: the title, the limits note and "This is not financial advice." on every card, also thin-wallet's."""
    notes = honesty_notes(stored_of(SMALL["thin-wallet"]))
    assert notes.title == "What this test can't see" and notes.not_advice == "This is not financial advice."
    assert notes.limits.startswith("Long shots tend to be overpriced") and notes.limits.endswith(
        "picking by results makes luck look more like skill."
    )


def test_ad11_held_read_and_exit_pnl_count_only_what_the_app_can_see() -> None:
    """AD-11, FR-11 (Edvard, 2026-11-24): M leaves out "not fully read"; N also sold and Slivers; the Exit PnL sums
    tested, Slivers and sold-before-resolution only, so a split-or-merged bet's Exit PnL never counts."""
    sold = bet(3, price=0.5, won=True, shares=0.0, shares_bought=100.0, shares_sold=100.0, exit_pnl=-20.0,
               reason=ExclusionReason.SOLD_BEFORE_RESOLUTION)
    split = bet(4, price=0.5, won=True, shares_sold=10.0, exit_pnl=1_000.0, reason=ExclusionReason.SPLIT_OR_MERGED)
    unread = bet(5, price=0.5, won=True, exit_pnl=500.0, reason=ExclusionReason.NOT_FULLY_READ)
    sliver = bet(6, price=0.5, won=True, shares=0.5, shares_bought=100.0, shares_sold=99.5, exit_pnl=-5.0)
    tested = bet(7, price=0.5, won=True, shares_bought=110.0, shares_sold=10.0, exit_pnl=3.0)
    position_set = PositionSet(tested=(tested,), slivers=(sliver,), left_out=(sold, split, unread))
    assert (position_set.window_size, position_set.read_count, position_set.held_count) == (5, 4, 2)  # tested, split
    assert position_set.exit_pnl == pytest.approx(-22.0) and position_set.any_sold
    assert position_set.largest_bet == pytest.approx(50.0)  # tested: 100 x 0.5; the Sliver 0.5 x 0.5
    empty = PositionSet(tested=(), slivers=(), left_out=(unread,))
    assert (empty.read_count, empty.held_count, empty.exit_pnl, empty.any_sold, empty.largest_bet) == (0, 0, 0.0, False, None)


def test_fr11_exit_pnl_leaves_out_split_or_merged_sales(real: dict[str, HonestyNotes]) -> None:
    """FR-11 (Edvard, 2026-11-24): 0xcf0d7f's Exit PnL sums tested bets, Slivers and bets sold before resolution only:
    −$195,091, the figure the decision log gives (−$23,285 if its 46 split-or-merged bets counted), so it warns."""
    notes = real["0xcf0d7f"]
    assert notes.exit_text == "Shares sold before resolution: −$195,091 (Exit PnL)." and notes.exit_warning is not None


def test_ad11_sales_only_in_split_or_unread_bets_are_no_sales() -> None:
    """FR-11, AD-11 (Story 3.3 review): sales in a split-or-merged or not-fully-read bet are outside the Exit PnL, so a
    set whose only sales sit there reads "No shares were sold before resolution."."""
    split = bet(1, price=0.5, won=True, shares_sold=40.0, exit_pnl=-30.0, reason=ExclusionReason.SPLIT_OR_MERGED)
    unread = bet(2, price=0.5, won=True, shares_sold=10.0, exit_pnl=-5.0, reason=ExclusionReason.NOT_FULLY_READ)
    position_set = PositionSet(tested=(bet(0, price=0.5, won=True),), slivers=(), left_out=(split, unread))
    assert position_set.any_sold is False and position_set.exit_pnl == 0.0
    notes = honesty_notes(stored_from(position_set))
    assert notes.exit_text == "No shares were sold before resolution." and notes.exit_warning is None


def test_fr11_a_capped_window_names_what_the_cap_counted() -> None:
    """FR-11, AD-8 (Story 3.3 review): the cap counts positions-list rows, so a token found only in activity rows
    never makes the window line read more than the window holds."""
    activity_only = bet(9, price=0.5, won=True, reason=ExclusionReason.ONLY_IN_ACTIVITY)
    position_set = PositionSet(tested=(bet(0, price=0.5, won=True), bet(1, price=0.5, won=False)), slivers=(),
                               left_out=(activity_only,))
    stored = StoredResult(skilltest.skill_test(position_set, seed=SEED, unit_id="planted"), 0, position_set, True, 2)
    notes = honesty_notes(stored)
    assert notes.window == "Based on the latest 2 bets; older results are not included."
    assert notes.computed_on == "Computed on the latest 2 bets · Seed 44"
    assert honesty_notes(replace(stored, capped=False)).computed_on == "Computed on all 3 bets · Seed 44"


def test_fr11_a_scan_result_always_shows_both_windows() -> None:
    """FR-11, AD-8 (Edvard, 2026-11-26, Story 4.5): a `scan_whole` result shows the two-window line even when no part
    was capped, and its last line names the Cut-off Date; a lookup's notes are unchanged."""
    from datetime import date

    position_set = PositionSet(tested=(bet(0, price=0.5, won=True), bet(1, price=0.5, won=False)), slivers=(), left_out=())
    result = skilltest.skill_test(position_set, seed=SEED, unit_id="planted", scope="scan_whole")
    scan_result = StoredResult(result, 0, position_set, False, 2, cutoff=date(2025, 7, 1), sides=("before", "after"))
    notes = honesty_notes(scan_result)
    assert notes.window == phrases.SCAN_WINDOW_LINE
    assert notes.computed_on == "Computed on 2 bets around the Cut-off Date 1 July 2025 · Seed 44"
    lookup = honesty_notes(stored_from(position_set))
    assert lookup.window == "" and lookup.computed_on == "Computed on all 2 bets · Seed 44"


def test_fr11_a_scan_result_names_only_the_windows_read() -> None:
    """FR-11, AD-8 (Edvard, 2026-11-26, Story 4.5 review): with the after part refused the line names the before
    window alone and says the after part could not be read; with nothing read there is no window line."""
    from dataclasses import replace as changed
    from datetime import date

    position_set = PositionSet(tested=(bet(0, price=0.5, won=True),), slivers=(), left_out=())
    result = skilltest.skill_test(position_set, seed=SEED, unit_id="planted", scope="scan_whole")
    both = StoredResult(result, 0, position_set, False, 1, cutoff=date(2025, 7, 1), sides=("before", "after"))
    assert honesty_notes(changed(both, sides=("before",))).window == phrases.SCAN_BEFORE_ONLY_LINE == (
        "Based on the latest 2,000 bets resolved before the Cut-off Date; the bets bought after it could not be read."
    )
    nothing = honesty_notes(changed(both, sides=()))
    assert nothing.window == "" and nothing.computed_on.startswith("Computed on ")
