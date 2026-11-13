"""Synthetic Wallets with known answers (FR-13, AD-14, AD-15; Story 1.3).

The answers live in `sample_data/synthetic/expected.json`, written by hand before the Skill Test.
These tests check that the generated Wallets really contain the bets those answers assume.
"""

from __future__ import annotations

import ast
import json
import math
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

import liquidoracle.__main__ as cli
from liquidoracle.core.positions import build_positions
from liquidoracle.data import sample_json, synthetic
from liquidoracle.records import ExclusionReason, PositionSet, SampleWallet

REPO = Path(__file__).resolve().parents[1]
SYNTHETIC_DIR = REPO / synthetic.SMALL_DIR
EXPECTED = json.loads((SYNTHETIC_DIR / "expected.json").read_text(encoding="utf-8"))
CUT_OFF = 1_751_328_000  # 2025-07-01 00:00 UTC, the default Cut-off Date (PRD §9 Q6)
CENT = 0.005

SMALL = {wallet.name: wallet for wallet in synthetic.small_wallets()}


def positions(wallet: SampleWallet) -> PositionSet:
    return build_positions(wallet.activity, {m.condition_id: m for m in wallet.markets})


def real_pnl(position_set: PositionSet) -> float:
    # FR-4 with no fees: sum of s * (o - p) over tested Positions and Slivers.
    return sum(p.shares_held * (p.outcome - p.entry_price) for p in (*position_set.tested, *position_set.slivers))


# --- byte-identical output (FR-13) ---------------------------------------------------------


def test_two_runs_give_identical_bytes(tmp_path: Path) -> None:
    """FR-13: running the generator twice gives byte-identical files, small Wallets and coin-flippers."""
    for run in ("a", "b"):
        synthetic.write_small(tmp_path / run)
        synthetic.write_coin_flippers(tmp_path / run, count=20)
    files_a = sorted(p.relative_to(tmp_path / "a") for p in (tmp_path / "a").rglob("*.json"))
    files_b = sorted(p.relative_to(tmp_path / "b") for p in (tmp_path / "b").rglob("*.json"))
    assert files_a == files_b and len(files_a) == 25
    for rel in files_a:
        assert (tmp_path / "a" / rel).read_bytes() == (tmp_path / "b" / rel).read_bytes(), rel


def test_committed_files_equal_fresh_output() -> None:
    """FR-13, AD-14: the committed Wallets are exactly what the generator writes now, LF line endings included."""
    for name, wallet in SMALL.items():
        committed = (SYNTHETIC_DIR / f"{name}.json").read_bytes()
        assert b"\r" not in committed, f"{name}.json has CRLF line endings"
        assert committed == sample_json.dumps(wallet).encode("utf-8"), name


def test_generator_uses_its_own_constant_and_no_other_randomness() -> None:
    """AD-14, AD-15: the generator reads no settings and uses neither `random`, numpy nor `hash()`."""
    tree = ast.parse((REPO / "src" / "liquidoracle" / "data" / "synthetic.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "hash", "hash() changes with PYTHONHASHSEED"
    assert not {"random", "numpy", "liquidoracle.settings"} & imported
    assert not any(name.startswith(("numpy.", "random.")) for name in imported)


def test_draws_depend_only_on_their_inputs() -> None:
    """AD-15, FR-13: a draw is fixed by (Wallet, bet, purpose) and changes when any of them changes."""
    draw = synthetic.uniform("sharp-trader", 3, "order")
    assert draw == synthetic.uniform("sharp-trader", 3, "order")
    assert 0.0 <= draw < 1.0
    others = {synthetic.uniform("sharp-trader", 4, "order"), synthetic.uniform("thin-wallet", 3, "order"),
              synthetic.uniform("sharp-trader", 3, "price")}
    assert draw not in others


# --- the one serializer (AD-14) --------------------------------------------------------------


@pytest.mark.parametrize("compact", [False, True])
def test_serializer_round_trip(compact: bool) -> None:
    """AD-14: reading a written Wallet gives back the same records, in both layouts."""
    for wallet in (*SMALL.values(), synthetic.coin_flipper(0)):
        assert sample_json.loads(sample_json.dumps(wallet, compact=compact)) == wallet


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda d: d.pop("prices"),
        lambda d: d.update(extra=1),
        lambda d: d["markets"][0].update(closed="false"),
        lambda d: d["activity"][0].pop("side"),
        lambda d: d["positions"][0].update(colour="red"),
        lambda d: d.update(activity=None),
    ],
)
def test_serializer_refuses_malformed_files(corrupt: object) -> None:
    """AD-14: a missing, unknown or wrongly typed field is an error, never a silent default."""
    document = json.loads(sample_json.dumps(SMALL["hand-check"]))
    corrupt(document)  # type: ignore[operator]
    with pytest.raises(ValueError):
        sample_json.loads(json.dumps(document))


def test_serializer_refuses_text_that_is_not_json() -> None:
    """AD-14: a broken file gives a ValueError that names the file."""
    with pytest.raises(ValueError, match="not a Sample Dataset Wallet file"):
        sample_json.loads("{not json")


# --- the intended bets, through the Story 1.2 builder (FR-13) ---------------------------------


def test_expected_fixture_covers_every_small_wallet() -> None:
    """FR-13: expected.json has an answer for each committed Wallet, and nothing else."""
    assert set(EXPECTED["wallets"]) == set(SMALL)
    committed = {p.stem for p in SYNTHETIC_DIR.glob("*.json")} - {"expected"}
    assert committed == set(SMALL)


@pytest.mark.parametrize("name", sorted(SMALL))
def test_wallet_gives_the_intended_bets(name: str) -> None:
    """FR-13, FR-3: each Wallet's builder output matches its hand-written counts, prices and Real PnL."""
    expected = EXPECTED["wallets"][name]
    built = positions(SMALL[name])
    assert built.tested_count == expected["tested"]
    assert sum(p.outcome == 1.0 for p in built.tested) == expected["won"]
    assert len(built.slivers) == expected["slivers"]
    assert len(built.left_out) == expected["left_out"]
    assert {p.entry_price for p in built.tested} == {expected["entry_price"]}
    assert real_pnl(built) == pytest.approx(expected["real_pnl"], abs=CENT)


def test_hand_values_agree_with_the_counts() -> None:
    """FR-4, FR-13: each hand-written Real PnL equals won * s * (1 - p) - lost * s * p for 100 shares."""
    for name, expected in EXPECTED["wallets"].items():
        p, won, lost = expected["entry_price"], expected["won"], expected["tested"] - expected["won"]
        assert expected["real_pnl"] == pytest.approx(100 * (won * (1 - p) - lost * p), abs=CENT), name


def test_hand_check_exact_p_is_one_in_1024() -> None:
    """FR-5, FR-13: only 'all 10 won' beats or ties the hand-check, so its exact p is 0.5 ** 10."""
    expected = EXPECTED["wallets"]["hand-check"]
    assert expected["exact_p"] == 0.5**10
    assert expected["p_at_least"] < expected["exact_p"] < expected["p_below"]


def test_stop_loss_trader_sells_the_fallen_bets() -> None:
    """FR-11, FR-13: 67 bets sold at 0.25 with Exit PnL -$25 each (17 in Markets their side won); 33 held, all won."""
    expected = EXPECTED["wallets"]["stop-loss-trader"]
    built = positions(SMALL["stop-loss-trader"])
    sold = built.left_out
    assert all(p.reason == ExclusionReason.SOLD_BEFORE_RESOLUTION for p in sold)
    assert len(sold) == expected["sold_before_resolution"]
    assert sum(p.outcome == 1.0 for p in sold) == expected["sold_in_markets_their_side_won"]
    for p in sold:
        assert p.exit_pnl == pytest.approx(expected["exit_pnl_each"], abs=CENT)
    assert sum(p.exit_pnl for p in sold) == pytest.approx(expected["exit_pnl_total"], abs=CENT)
    assert all(p.outcome == 1.0 and p.shares_held == 100 for p in built.tested)


def test_stop_loss_price_paths_explain_the_sells() -> None:
    """FR-11, FR-13: each sold token's price path falls to the sell price at the sell time, then ends at its outcome."""
    wallet = SMALL["stop-loss-trader"]
    path = {}
    for point in wallet.prices:
        path.setdefault(point.token_id, []).append((point.t, point.price))
    outcome = {m.token_ids[0]: m.outcome_prices[0] for m in wallet.markets}
    for row in wallet.activity:
        points = sorted(path[row.token_id])
        assert points[-1][1] == outcome[row.token_id]
        if row.side == "BUY":
            assert points[0] == (row.timestamp, row.price)
        else:
            assert (row.timestamp, row.price) in points and row.price < points[0][1]
    assert len(path) == 100


# --- structure the later stories rely on (AD-10, AD-14) ---------------------------------------


def all_test_wallets() -> list[SampleWallet]:
    return [*SMALL.values(), *(synthetic.coin_flipper(i) for i in range(5))]


def test_every_tested_position_has_its_own_market() -> None:
    """AD-14, AD-20: no two synthetic Positions share a Market, within or across Wallets."""
    seen: set[str] = set()
    for wallet in all_test_wallets():
        traded = {(row.condition_id, row.token_id) for row in wallet.activity}
        markets = {m.condition_id for m in wallet.markets}
        assert len(traded) == len(markets) == len(wallet.markets)
        assert not seen & markets
        seen |= markets
        assert all(len(m.token_ids) == 2 for m in wallet.markets)


def test_positions_lists_are_derived_from_the_fills() -> None:
    """AD-10, AD-14: one positions-list row per traded token, with bought shares and first buy from the fills."""
    for wallet in all_test_wallets():
        listed = {(p.condition_id, p.token_id): p for p in wallet.positions}
        assert len(listed) == len(wallet.positions)
        built = positions(wallet)
        for position in (*built.tested, *built.left_out):
            row = listed[(position.condition_id, position.token_id)]
            buys = [r for r in wallet.activity if r.token_id == position.token_id and r.side == "BUY"]
            assert row.shares_bought == position.shares_bought
            assert row.first_entry_at == min(r.timestamp for r in buys)
            held_loser = position.shares_held > 0 and position.outcome == 0.0
            assert row.status == ("OPEN" if held_loser else "CLOSED")


def test_all_activity_is_before_the_default_cut_off() -> None:
    """FR-13, PRD §9 Q6: every fill and resolution is before 2025-07-01, so later stories can add an after part."""
    for wallet in all_test_wallets():
        assert max(row.timestamp for row in wallet.activity) < CUT_OFF
        assert max(m.closed_time for m in wallet.markets) < CUT_OFF
        assert all(not m.fees_enabled for m in wallet.markets)


def test_addresses_are_distinct_wallet_addresses() -> None:
    """AD-14, FR-1: each Synthetic Wallet has its own 0x address of 40 hex digits."""
    addresses = [w.address for w in all_test_wallets()]
    assert len(set(addresses)) == len(addresses)
    assert all(len(a) == 42 and a.startswith("0x") and int(a[2:], 16) >= 0 for a in addresses)


# --- the coin-flippers (FR-5, FR-13) -----------------------------------------------------------


@pytest.mark.slow
def test_coin_flippers_bet_at_whole_cent_prices(repetitions: int) -> None:
    """FR-13: each coin-flipper has 100 tested bets at whole-cent prices from 0.10 to 0.90, both ends used."""
    expected = EXPECTED["coin_flippers"]
    prices = []
    for wallet in synthetic.coin_flippers(repetitions):
        built = positions(wallet)
        assert built.tested_count == expected["bets_each"] and not built.left_out and not built.slivers
        prices += [p.entry_price for p in built.tested]
    assert all(round(p * 100) == pytest.approx(p * 100, abs=1e-9) for p in prices)
    assert min(prices) == expected["price_min"] and max(prices) == expected["price_max"]


@pytest.mark.slow
def test_coin_flippers_win_at_their_prices(repetitions: int) -> None:
    """FR-5, FR-13: within each price band, wins stay within 4 standard deviations of the sum of the prices."""
    bands: dict[str, list[tuple[float, bool]]] = {"low": [], "middle": [], "high": []}
    for wallet in synthetic.coin_flippers(repetitions):
        for p in positions(wallet).tested:
            band = "low" if p.entry_price < 0.35 else "high" if p.entry_price > 0.65 else "middle"
            bands[band].append((p.entry_price, p.outcome == 1.0))
    for band, bets in bands.items():
        mean = sum(price for price, _ in bets)
        sd = math.sqrt(sum(price * (1 - price) for price, _ in bets))
        wins = sum(won for _, won in bets)
        assert abs(wins - mean) < 4 * sd, (band, wins, mean, sd)


def test_coin_flippers_are_never_committed() -> None:
    """FR-12, AD-14: the coin-flipper folder is git-ignored and no coin-flipper file is tracked."""
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(synthetic.COIN_FLIPPER_DIR / "coin-flipper-0000.json")],
        cwd=REPO, capture_output=True, timeout=30,
    )
    assert ignored.returncode == 0
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, timeout=30, check=True)
    assert "coin-flipper" not in tracked.stdout


# --- the command (FR-13) ----------------------------------------------------------------------


def test_make_synthetic_writes_both_groups(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-13, AD-14: `make-synthetic` writes the five small Wallets and the 1,000 coin-flippers into instance/."""
    (tmp_path / "sample_data").mkdir()
    monkeypatch.chdir(tmp_path)
    assert cli.main(["make-synthetic"]) == 0
    for name in SMALL:
        assert (tmp_path / synthetic.SMALL_DIR / f"{name}.json").read_bytes() == (SYNTHETIC_DIR / f"{name}.json").read_bytes()
    flippers = sorted((tmp_path / synthetic.COIN_FLIPPER_DIR).glob("*.json"))
    assert len(flippers) == 1000
    assert sample_json.read_wallet(flippers[-1]) == synthetic.coin_flipper(999)


def test_make_synthetic_refuses_outside_the_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR-13: run outside the repository folder, `make-synthetic` writes nothing and says why."""
    monkeypatch.chdir(tmp_path)
    assert cli.main(["make-synthetic"]) == 2
    assert "repository folder" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_changing_a_wallet_changes_its_file() -> None:
    """FR-13, AD-14: the committed-files check would notice an edit (a changed price changes the bytes)."""
    wallet = SMALL["hand-check"]
    edited = replace(wallet, activity=(replace(wallet.activity[0], price=0.51), *wallet.activity[1:]))
    assert sample_json.dumps(edited) != sample_json.dumps(wallet)
