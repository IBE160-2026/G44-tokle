"""Synthetic Wallets with known answers (FR-13, AD-14, AD-15; Story 1.3).

The answers live in `sample_data/synthetic/expected.json`, written by hand before the Skill Test.
These tests check that the generated Wallets really contain the bets those answers assume.
"""

from __future__ import annotations

import ast
import json
import math
import shutil
import subprocess
from collections import Counter
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
STAGE_1 = ("hand-check", "favourite-buyer", "sharp-trader", "thin-wallet", "stop-loss-trader")
STAGE_2 = ("steady-sharp", "forecaster", "speed-trader")
ANCHOR_IDS = frozenset(synthetic.funnel_volumes())


def positions(wallet: SampleWallet) -> PositionSet:
    return build_positions(wallet.activity, {m.condition_id: m for m in wallet.markets}, listed=wallet.positions)


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
    assert files_a == files_b and len(files_a) == len(SMALL) + 1 + 20  # the Wallets, the volume list, 20 coin-flippers
    for rel in files_a:
        assert (tmp_path / "a" / rel).read_bytes() == (tmp_path / "b" / rel).read_bytes(), rel


def test_committed_files_equal_fresh_output() -> None:
    """FR-13, AD-14: the committed Wallets are exactly what the generator writes now, LF line endings included."""
    for name, wallet in SMALL.items():
        committed = (SYNTHETIC_DIR / f"{name}.json").read_bytes()
        assert b"\r" not in committed, f"{name}.json has CRLF line endings"
        assert committed == sample_json.dumps(wallet).encode("utf-8"), name


def test_committed_volume_list_equals_fresh_output(tmp_path: Path) -> None:
    """AD-14, AD-21 (Story 4.6): the committed anchor volume list is exactly what the generator writes now."""
    synthetic.write_small(tmp_path)
    fresh = (tmp_path / synthetic.SMALL_DIR / synthetic.FUNNEL_FILE).read_bytes()
    assert (SYNTHETIC_DIR / synthetic.FUNNEL_FILE).read_bytes() == fresh
    assert sample_json.read_funnel(SYNTHETIC_DIR / synthetic.FUNNEL_FILE) == synthetic.funnel_volumes()


BANNED_IMPORTS = ("random", "numpy", "os", "secrets", "time", "liquidoracle.settings")


@pytest.mark.parametrize("module", ["synthetic.py", "sample_json.py"])
def test_generator_uses_its_own_constant_and_no_other_randomness(module: str) -> None:
    """AD-14, AD-15: the generator and its serializer read no settings or environment, and use neither `random`, numpy nor `hash()`."""
    tree = ast.parse((REPO / "src" / "liquidoracle" / "data" / module).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            # `from liquidoracle import settings` is caught as liquidoracle.settings
            imported |= {node.module or ""} | {f"{node.module}.{alias.name}" for alias in node.names}
        elif isinstance(node, ast.Name):
            assert node.id not in {"hash", "__import__"}, f"{node.id} is not allowed"
    assert [name for name in imported if name == BANNED_IMPORTS[-1] or name.split(".")[0] in BANNED_IMPORTS[:-1]] == []


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


def test_serializer_keeps_market_events() -> None:
    """AD-14, AD-20 (Story 2.4): a Market's event and negative-risk event survive the round trip."""
    wallet = SMALL["hand-check"]
    linked = replace(wallet, markets=(replace(wallet.markets[0], event_id="16868", neg_risk_id="0x5b32"), *wallet.markets[1:]))
    assert sample_json.loads(sample_json.dumps(linked)) == linked


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda d: d.pop("prices"),
        lambda d: d.update(extra=1),
        lambda d: d["markets"][0].update(closed="false"),
        lambda d: d["activity"][0].pop("side"),
        lambda d: d["positions"][0].update(colour="red"),
        lambda d: d.update(activity=None),
        lambda d: d.update(address=None),
        lambda d: d["activity"][0].update(token_id=5),
        lambda d: d["activity"][0].update(side="buy"),
        lambda d: d["activity"][0].update(timestamp="1735689600"),
        lambda d: d["activity"][0].update(timestamp=1735689600.9),
        lambda d: d["activity"][0].update(size=True),
        lambda d: d["markets"][0].update(token_ids="10"),
        lambda d: d["markets"][0].update(event_id=16868),
        lambda d: d["markets"][0].pop("neg_risk_id"),
        lambda d: d["positions"][0].update(status="PENDING"),
        lambda d: d["prices"].append("not an object"),
    ],
)
def test_serializer_refuses_malformed_files(corrupt: object) -> None:
    """AD-14: a missing, unknown or wrongly typed field is an error, never a silent default."""
    document = json.loads(sample_json.dumps(SMALL["hand-check"]))
    corrupt(document)  # type: ignore[operator]
    with pytest.raises(ValueError):
        sample_json.loads(json.dumps(document))


@pytest.mark.parametrize("text", ["{not json", "[]", '{"address": NaN}', '{"address": Infinity}'])
def test_serializer_refuses_text_that_is_not_a_wallet(text: str) -> None:
    """AD-14: broken JSON, a non-object, NaN or Infinity all give the same ValueError."""
    with pytest.raises(ValueError, match="not a Sample Dataset Wallet file"):
        sample_json.loads(text)


def test_serializer_refuses_infinity_in_a_time_field() -> None:
    """AD-14: Infinity in a time field is a ValueError, not an OverflowError from int()."""
    text = sample_json.dumps(SMALL["hand-check"]).replace('"timestamp": 1735689600', '"timestamp": Infinity', 1)
    assert "Infinity" in text
    with pytest.raises(ValueError, match="Infinity is not allowed"):
        sample_json.loads(text)


@pytest.mark.parametrize("content", [b"{not json", "ÿ not utf-8".encode("latin-1")])
def test_read_wallet_names_the_broken_file(tmp_path: Path, content: bytes) -> None:
    """AD-14: a malformed or non-UTF-8 file gives a ValueError that names the file."""
    path = tmp_path / "broken-wallet.json"
    path.write_bytes(content)
    with pytest.raises(ValueError, match="broken-wallet.json"):
        sample_json.read_wallet(path)


# --- the intended bets, through the Story 1.2 builder (FR-13) ---------------------------------


def test_expected_fixture_covers_every_small_wallet() -> None:
    """FR-13: expected.json has an answer for each committed Wallet, and nothing else."""
    assert set(EXPECTED["wallets"]) == set(SMALL)
    committed = {p.stem for p in SYNTHETIC_DIR.glob("*.json")} - {"expected", Path(synthetic.FUNNEL_FILE).stem}
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
    total = real_pnl(built) + sum(p.exit_pnl for p in sold)  # no edge: about zero overall
    assert total == pytest.approx(expected["total_pnl"], abs=CENT)


def test_stop_loss_price_paths_explain_the_sells() -> None:
    """FR-11, FR-13: each sold token's price path falls to the sell price at the sell time, then ends at its outcome."""
    wallet = SMALL["stop-loss-trader"]
    path = {}
    for point in wallet.prices:
        path.setdefault(point.token_id, []).append((point.t, point.price))
    outcome = {m.token_ids[0]: m.outcome_prices[0] for m in wallet.markets}
    sold = {row.token_id: row for row in wallet.activity if row.side == "SELL"}
    for token, points in path.items():
        points.sort()
        assert points[0][1] == 0.50 and points[-1][1] == outcome[token]
        before_end = [price for _, price in points[:-1]]
        if token in sold:  # fell to the stop, sold exactly there, never lower before resolution
            assert sold[token].price == synthetic.STOP_LOSS_PRICE
            assert (sold[token].timestamp, synthetic.STOP_LOSS_PRICE) in points
            assert min(before_end) == synthetic.STOP_LOSS_PRICE
        else:  # held: never touched the stop
            assert min(before_end) > synthetic.STOP_LOSS_PRICE
    assert len(path) == 100 and len(sold) == 67


# --- structure the later stories rely on (AD-10, AD-14) ---------------------------------------


def all_test_wallets() -> list[SampleWallet]:
    return [*SMALL.values(), *(synthetic.coin_flipper(i) for i in range(5))]


def test_every_tested_position_has_its_own_market() -> None:
    """AD-14, AD-20: no two tested synthetic Positions share a Market, within or across Wallets; only the
    anchor Markets are shared, and their Positions are never tested (Story 4.6)."""
    seen: set[str] = set()
    for wallet in all_test_wallets():
        traded = {(row.condition_id, row.token_id) for row in wallet.activity if row.condition_id not in ANCHOR_IDS}
        markets = {m.condition_id for m in wallet.markets} - ANCHOR_IDS
        assert len(traded) == len(markets) == len(wallet.markets) - len({m.condition_id for m in wallet.markets} & ANCHOR_IDS)
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


def test_all_stage_1_activity_is_before_the_default_cut_off() -> None:
    """FR-13, PRD §9 Q6: every stage 1 fill and resolution is before 2025-07-01 (stage 2 Wallets bet on both sides)."""
    for wallet in [*(SMALL[name] for name in STAGE_1), *(synthetic.coin_flipper(i) for i in range(5))]:
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
        assert built.tested_count == expected["bets_each"] and not built.slivers
        assert len(built.left_out) == expected["left_out_each"]  # the 3 anchor bets (Story 4.6)
        assert {p.condition_id for p in built.left_out} == ANCHOR_IDS
        prices += [p.entry_price for p in built.tested]
    assert all(round(p * 100) == pytest.approx(p * 100, abs=1e-9) for p in prices)
    assert expected["price_min"] <= min(prices) and max(prices) <= expected["price_max"]


def test_coin_flipper_prices_are_uniform_over_the_cents() -> None:
    """FR-13: over the first 100 coin-flippers every cent from 0.10 to 0.90 occurs, each within 5 SD of 1/81 of the bets."""
    counts = Counter(
        round(row.price * 100)
        for wallet in synthetic.coin_flippers(100) for row in wallet.activity if row.condition_id not in ANCHOR_IDS
    )
    assert sorted(counts) == list(range(10, 91))
    n = sum(counts.values())
    mean, sd = n / 81, math.sqrt(n * (1 / 81) * (80 / 81))
    assert all(abs(count - mean) < 5 * sd for count in counts.values()), counts

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
    if shutil.which("git") is None or not (REPO / ".git").exists():
        pytest.skip("needs a git checkout (not a zip download)")
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(synthetic.COIN_FLIPPER_DIR / "coin-flipper-0000.json")],
        cwd=REPO, capture_output=True, timeout=30,
    )
    assert ignored.returncode == 0
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, timeout=30, check=True)
    data_files = [f for f in tracked.stdout.splitlines() if f.startswith(("sample_data/", "instance/"))]
    assert data_files and not [f for f in data_files if "coin-flipper" in f]


# --- the command (FR-13) ----------------------------------------------------------------------


def test_make_synthetic_writes_both_groups(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-13, AD-14: `make-synthetic` writes the five small Wallets and the 1,000 coin-flippers into instance/."""
    (tmp_path / "sample_data").mkdir()
    (tmp_path / "pyproject.toml").touch()
    monkeypatch.chdir(tmp_path)
    assert cli.main(["make-synthetic"]) == 0
    for name in SMALL:
        assert (tmp_path / synthetic.SMALL_DIR / f"{name}.json").read_bytes() == (SYNTHETIC_DIR / f"{name}.json").read_bytes()
    flippers = sorted((tmp_path / synthetic.COIN_FLIPPER_DIR).glob("*.json"))
    assert len(flippers) == 1000
    assert sample_json.read_wallet(flippers[-1]) == synthetic.coin_flipper(999)


@pytest.mark.parametrize("present", [(), ("sample_data",), ("pyproject.toml",)])
def test_make_synthetic_refuses_outside_the_repository(
    present: tuple[str, ...], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR-13: where sample_data/ and pyproject.toml are not both present, `make-synthetic` writes nothing and says why."""
    if "sample_data" in present:
        (tmp_path / "sample_data").mkdir()
    if "pyproject.toml" in present:
        (tmp_path / "pyproject.toml").touch()
    before = sorted(tmp_path.rglob("*"))
    monkeypatch.chdir(tmp_path)
    assert cli.main(["make-synthetic"]) == 2
    assert "repository folder" in capsys.readouterr().err
    assert sorted(tmp_path.rglob("*")) == before


def test_changing_a_wallet_changes_its_file() -> None:
    """FR-13, AD-14: the committed-files check would notice an edit (a changed price changes the bytes)."""
    wallet = SMALL["hand-check"]
    edited = replace(wallet, activity=(replace(wallet.activity[0], price=0.51), *wallet.activity[1:]))
    assert sample_json.dumps(edited) != sample_json.dumps(wallet)


def test_last_event_times_follow_the_fills_and_markets_open_before_the_first_buy() -> None:
    """AD-7, AD-14: a sold Position's last event is its sell, a held winner's is its redemption at
    resolution, a held loser's (OPEN) is its buy; every Market starts before the Wallet's first buy."""
    for wallet in synthetic.small_wallets():
        markets = {m.condition_id: m for m in wallet.markets}
        for row in wallet.positions:
            fills = [a for a in wallet.activity if a.token_id == row.token_id]
            sold = any(a.side == "SELL" for a in fills)
            market = markets[row.condition_id]
            assert market.start_time is not None and market.start_time < row.first_entry_at
            if row.status == "CLOSED" and not sold:
                assert row.last_event_at == market.closed_time
            else:
                assert row.last_event_at == max(a.timestamp for a in fills)


# --- stage 2: steady sharp, forecaster, speed trader and the anchor Markets (Story 4.6) --------------


@pytest.mark.parametrize("name", STAGE_2)
def test_fr13_stage_2_wallets_win_70_of_100_on_each_side_of_the_cut_off(name: str) -> None:
    """FR-13: 100 bets at 0.50 before the cut-off with exactly 70 won, 100 bought from it on with exactly 70 won."""
    wallet = SMALL[name]
    built = positions(wallet)
    resolved = {m.condition_id: m.closed_time for m in wallet.markets}
    first_buy = {row.condition_id: row.first_entry_at for row in wallet.positions}
    before = [p for p in built.tested if resolved[p.condition_id] < CUT_OFF]
    after = [p for p in built.tested if first_buy[p.condition_id] >= CUT_OFF]
    assert len(before) == len(after) == 100 and len(before) + len(after) == built.tested_count
    assert sum(p.outcome == 1.0 for p in before) == sum(p.outcome == 1.0 for p in after) == 70
    assert {p.entry_price for p in built.tested} == {0.5}


def test_fr13_forecaster_price_drifts_to_the_outcome_over_hours() -> None:
    """FR-13: around each later buy, one point a minute from -2 to +32 minutes; the price is 0.50 up to the buy
    and then moves a 240th of the way to the outcome each minute, so at 30 minutes it is 0.5625 or 0.4375."""
    wallet = SMALL["forecaster"]
    outcome = outcomes(wallet)
    paths = price_paths(wallet)
    assert len(paths) == 100
    for (token, bought_at), points in paths.items():
        assert [t - bought_at for t, _ in points] == [60 * m for m in range(-2, 33)]
        at = dict((t - bought_at, p) for t, p in points)
        assert at[-120] == at[0] == 0.5
        assert at[30 * 60] == pytest.approx(0.5625 if outcome[token] == 1.0 else 0.4375)
        moves = [b - a for (_, a), (_, b) in zip(points, points[1:])]
        assert all(m == pytest.approx(0.0) for m in moves[:2])
        assert all(m == pytest.approx((outcome[token] - 0.5) / 240, abs=1e-6) for m in moves[2:])


def test_fr13_speed_trader_price_jumps_to_the_outcome_within_the_first_minute() -> None:
    """FR-13: the speed trader buys at 0.50 seconds before the jump: 0.50 up to the buy, the outcome from 1 minute on."""
    wallet = SMALL["speed-trader"]
    outcome = outcomes(wallet)
    paths = price_paths(wallet)
    assert len(paths) == 100
    for (token, bought_at), points in paths.items():
        assert [p for t, p in points if t <= bought_at] == [0.5, 0.5, 0.5]
        assert {p for t, p in points if t > bought_at} == {outcome[token]}


def test_fr13_price_paths_only_around_later_buys() -> None:
    """FR-13, AD-14: only the forecaster's and speed trader's bets after the cut-off have a price path (the
    Copy Test samples after-part Positions only); steady sharp and the anchor bets have none."""
    assert SMALL["steady-sharp"].prices == ()
    for name in ("forecaster", "speed-trader"):
        assert min(point.t for point in SMALL[name].prices) >= CUT_OFF - 120


def test_ad14_anchor_holders_are_the_watchlist_wallets_and_the_coin_flippers() -> None:
    """AD-14 (Edvard, 2026-11-27): the four FR-16 Wallets and every coin-flipper hold one Position in each anchor
    Market; no other committed Wallet does."""
    holders = {name for name, wallet in SMALL.items() if ANCHOR_IDS <= {m.condition_id for m in wallet.markets}}
    assert holders == set(synthetic.WATCHLIST_NAMES)
    others = [wallet for name, wallet in SMALL.items() if name not in holders]
    assert all(not ANCHOR_IDS & {m.condition_id for m in wallet.markets} for wallet in others)
    assert all(ANCHOR_IDS <= {m.condition_id for m in w.markets} for w in synthetic.coin_flippers(5))


@pytest.mark.parametrize("name", synthetic.WATCHLIST_NAMES)
def test_ad11_anchor_bets_are_sold_before_resolution_with_no_exit_pnl(name: str) -> None:
    """AD-11, AD-14: each anchor bet is bought and fully sold at 0.50 before its Market resolves, so it is left out
    as "sold before resolution" and adds nothing to Real PnL or Exit PnL (sharp trader stays at $2,000)."""
    built = positions(SMALL[name])
    anchors = [p for p in built.left_out if p.condition_id in ANCHOR_IDS]
    assert len(anchors) == len(ANCHOR_IDS) == len(built.left_out)
    assert {p.reason for p in anchors} == {ExclusionReason.SOLD_BEFORE_RESOLUTION}
    assert all(p.shares_held == 0 and p.shares_sold == synthetic.ANCHOR_SHARES for p in anchors)
    assert built.exit_pnl == pytest.approx(0.0)
    assert not ANCHOR_IDS & {p.condition_id for p in built.tested}


def test_ad21_anchor_markets_are_resolved_inside_the_default_funnel_window() -> None:
    """AD-21: every anchor Market resolved in the 90 days before 2025-07-01, so a Scan with the default date
    lists them; their volumes order them."""
    markets = {m.condition_id: m for m in SMALL["sharp-trader"].markets if m.condition_id in ANCHOR_IDS}
    assert set(markets) == ANCHOR_IDS
    for market in markets.values():
        assert market.resolved and CUT_OFF - 90 * 86_400 <= market.closed_time < CUT_OFF
    assert sorted(synthetic.funnel_volumes().values(), reverse=True) == [3_000_000.0, 2_000_000.0, 1_000_000.0]


def outcomes(wallet: SampleWallet) -> dict[str, float]:
    """Each bought token's outcome (1.0 won, 0.0 lost)."""
    return {m.token_ids[0]: m.outcome_prices[0] for m in wallet.markets}


def price_paths(wallet: SampleWallet) -> dict[tuple[str, int], list[tuple[int, float]]]:
    """Each later buy's price points, keyed by (token, buy time), in time order."""
    buys = {row.token_id: row.timestamp for row in wallet.activity if row.side == "BUY"}
    paths: dict[tuple[str, int], list[tuple[int, float]]] = {}
    for point in wallet.prices:
        paths.setdefault((point.token_id, buys[point.token_id]), []).append((point.t, point.price))
    return {key: sorted(points) for key, points in paths.items()}
