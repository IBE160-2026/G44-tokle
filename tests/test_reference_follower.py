"""Follower PnL and Follower Return on a hand-made set against a reference made without the app's code
(FR-18a, Story 6.2; Edvard, 2026-11-23).

Where the reference numbers came from: a fresh AI helper's step-by-step calculation, given only the PRD, the
set (`tests/reference/follower-pnl-set.json`) and a note saying what each field is
(`follower-pnl-fields.md`, written by the main Claude Code session; it says nothing about how to use them).
The helper's script (`follower-pnl-calc.py`), its output (`follower-pnl.csv`) and its notes with every
reading it had to choose (`follower-pnl-notes.md`) were committed in 52f0854, before the app's Copy Test
code was run on the set and before this test existed. It replaces Edvard's own hand calculation.

The set is one made-up Wallet: two Markets with a fee (a Market has two outcomes, so at most two Positions
of one Wallet), a Position bought in three fills, the other outcome of the same Market, a Position partly
sold before resolution, and a price that reaches the cap of 1 at 30 minutes.

What the reference does not cover (Story 6.2 review): every buy in the set is on a whole minute with a price
point at exactly each Copy Delay, both Markets have a fee exponent of 1, and no price is missing. So it checks
the arithmetic of FR-18a. The two-minute rule for an older price, an exponent other than 1 and the left-out
Position are checked in `test_copytest.py` and `test_prices.py`, by tests written with the app.

If a value differs, the cause (app, script or helper) is found and logged in the spec of the story that
changed it; a reference is never changed to match the app without a written reason.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
from test_reference_pnl import FOLLOWER_SCRIPT, stdlib_violations

from liquidoracle.core import copytest
from liquidoracle.core.positions import build_positions
from liquidoracle.data.sample_json import read_wallet
from liquidoracle.records import FollowerResult, PricePoint, SampleWallet

REPO = Path(__file__).resolve().parents[1]
REFERENCE = REPO / "tests" / "reference"
SET = REFERENCE / "follower-pnl-set.json"
SCRIPT = REFERENCE / "follower-pnl-calc.py"
CSV = REFERENCE / "follower-pnl.csv"
SEED = 44
SOURCE = "fresh AI helper's calculation (tests/reference/follower-pnl-calc.py)"


def cents(value: float | str) -> Decimal:
    text = value if isinstance(value, str) else repr(value)
    return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def percent(value: float | str) -> Decimal:
    """A Follower Return as the page will show it: a percentage with one decimal."""
    text = value if isinstance(value, str) else repr(value)
    return (Decimal(text) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def reference_rows(path: Path = CSV) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def app_follow(wallet: SampleWallet, delay: int, token_id: str | None = None) -> FollowerResult:
    """The app's numbers at one Copy Delay, for the whole set or for the one Position on `token_id`."""
    markets = {m.condition_id: m for m in wallet.markets}
    tested = build_positions(wallet.activity, markets, listed=wallet.positions).tested
    sample = copytest.copy_sample(tested, seed=SEED, wallet=wallet.address)
    assert len(sample) == len(tested) == 3  # under 100, so the Copy Sample is all of them
    if token_id is not None:
        sample = tuple(p for p in sample if p.token_id == token_id)
    by_token: dict[str, list[PricePoint]] = {}
    for point in wallet.prices:
        by_token.setdefault(point.token_id, []).append(point)
    fills = copytest.buy_fills(sample, wallet.activity)
    return copytest.follow(sample, fills, markets, lambda token: by_token.get(token, ()), delay)


@pytest.fixture(scope="module")
def wallet() -> SampleWallet:
    return read_wallet(SET)


@pytest.mark.parametrize("delay", copytest.COPY_DELAYS)
def test_fr18a_follower_pnl_and_return_equal_the_helpers_reference(wallet: SampleWallet, delay: int) -> None:
    """FR-18a: over the three Positions, Follower PnL, the money spent and the Wallet's own Real PnL equal the
    helper's numbers to the cent, and the Follower Return equals it to a tenth of a percent, at each Copy Delay."""
    (reference,) = [r for r in reference_rows() if r["row_type"] == "wallet" and int(r["delay_seconds"]) == delay]
    app = app_follow(wallet, delay)
    assert (app.priced, app.left_out) == (3, 0), SOURCE
    assert cents(app.follower_pnl) == cents(reference["follower_pnl"]), SOURCE
    assert cents(app.spent) == cents(reference["spent"]), SOURCE
    assert app.follower_return is not None
    assert percent(app.follower_return) == percent(reference["follower_return"]), SOURCE
    assert cents(app.own_pnl) == cents(reference["real_pnl"]), SOURCE


def test_fr18a_each_position_equals_the_helpers_reference(wallet: SampleWallet) -> None:
    """FR-18a: each Position's own Follower PnL and money spent equal the helper's at each Copy Delay, so two
    errors that cancel in the Wallet's total would still show."""
    rows = [r for r in reference_rows() if r["row_type"] == "position"]
    assert len(rows) == 3 * len(copytest.COPY_DELAYS)
    for reference in rows:
        app = app_follow(wallet, int(reference["delay_seconds"]), reference["token_id"])
        assert app.priced == 1
        assert cents(app.follower_pnl) == cents(reference["follower_pnl"]), reference["token_id"]
        assert cents(app.spent) == cents(reference["spent"]), reference["token_id"]


def test_fr18a_the_set_has_what_the_plan_asks_for(wallet: SampleWallet) -> None:
    """FR-18a: the set has Markets with a fee, a Position bought in more than one fill, a Position partly sold
    before resolution, and a fill whose price paid is capped at 1 (the reference rows say so)."""
    assert all(m.fees_enabled and m.fee_rate for m in wallet.markets)
    fills = [r for r in reference_rows() if r["row_type"] == "fill" and r["delay_seconds"] == "300"]
    per_token: dict[str, int] = {}
    for row in fills:
        per_token[row["token_id"]] = per_token.get(row["token_id"], 0) + 1
    assert sorted(per_token.values()) == [1, 2, 3]
    assert any(Decimal(r["s"]) < Decimal(r["fill_shares"]) for r in fills)  # the partly sold Position
    capped = [r for r in reference_rows() if r["row_type"] == "fill" and Decimal(r["price_paid"]) == 1]
    assert len(capped) == 1 and Decimal(capped[0]["recorded_price"]) + Decimal("0.005") > 1


def test_the_reference_script_reproduces_its_csv(tmp_path: Path) -> None:
    """FR-18a (Story 6.2): the committed CSV is what the helper's script writes from the committed set: run alone
    (`-I -S`, so it can import nothing of the app), its output has the same rows."""
    subprocess.run([sys.executable, "-I", "-S", str(SCRIPT), str(SET), str(tmp_path)], check=True, timeout=120,
                   capture_output=True)
    assert reference_rows(tmp_path / CSV.name) == reference_rows()


def test_the_reference_script_imports_only_the_standard_library() -> None:
    """FR-18a (Story 6.2): the helper's script never imports the app (it was written without seeing it) or any
    package: the same rule, by the same check, as the Real PnL reference scripts."""
    assert SCRIPT.name == FOLLOWER_SCRIPT
    assert stdlib_violations(SCRIPT.name, SCRIPT.read_text(encoding="utf-8")) == []
