"""The Skill Test (FR-4 to FR-7, AD-15, AD-17, AD-20, AD-22, AD-25; Story 1.4).

The answers come from `sample_data/synthetic/expected.json`, written by hand in Story 1.3 before
this code existed. Only these tests may call `skilltest._engine` (Edvard, 2026-10-24).
"""

from __future__ import annotations

import ast
import inspect
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from liquidoracle.core import rng, skilltest
from liquidoracle.core.positions import build_positions
from liquidoracle.data import synthetic
from liquidoracle.records import Position, PositionSet, SampleWallet, Verdict

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "liquidoracle"
EXPECTED = json.loads((REPO / synthetic.SMALL_DIR / "expected.json").read_text(encoding="utf-8"))
SEED = 44  # the Settings default (AD-15); fixed here so the golden counts never follow a settings change
CENT = 0.005  # Conventions › Money: to the cent

SMALL = {wallet.name: wallet for wallet in synthetic.small_wallets()}

# AD-17 golden result: Simulations at or above the Real PnL with SEED, unit_id = the Wallet's address.
# Written from this code's first run (2026-11-18); any system that draws or sums differently fails.
GOLDEN = {
    "hand-check": 8,
    "favourite-buyer": 5768,
    "sharp-trader": 1,
    "thin-wallet": 330,
    "stop-loss-trader": 0,
    "coin-flipper-0000": 7356,
    "coin-flipper-0001": 8207,
    "coin-flipper-0002": 3270,
}


def positions(wallet: SampleWallet) -> PositionSet:
    return build_positions(wallet.activity, {m.condition_id: m for m in wallet.markets})


def bet(i: int, price: float, won: bool, *, shares: float = 100.0, fees: float = 0.0, side: int = 0) -> Position:
    """A held Position in its own Market `m{i}`; `side` 0 or 1 picks the outcome token."""
    return Position(
        condition_id=f"m{i:05d}", token_id=f"m{i:05d}-{side}", outcome=1.0 if won else 0.0,
        entry_price=price, shares_bought=shares, shares_sold=0.0, shares_held=shares,
        own_fees=fees, exit_pnl=0.0,
    )


def position_set(*bets: Position, slivers: tuple[Position, ...] = ()) -> PositionSet:
    return PositionSet(tested=tuple(bets), slivers=slivers, left_out=())


def wallet_named(name: str) -> SampleWallet:
    if name in SMALL:
        return SMALL[name]
    return synthetic.coin_flipper(int(name.rsplit("-", 1)[1]))


# --- Real PnL (FR-4) --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED["wallets"]))
def test_real_pnl_matches_the_hand_values(name: str) -> None:
    """FR-4: Real PnL over tested Positions and Slivers equals the hand value in expected.json to the cent."""
    expected = EXPECTED["wallets"][name]
    result = skilltest.skill_test(positions(SMALL[name]), seed=SEED, unit_id=SMALL[name].address)
    assert result.real_pnl == pytest.approx(expected["real_pnl"], abs=CENT)
    assert (result.tested_count, result.sliver_count) == (expected["tested"], expected["slivers"])


def test_slivers_count_in_the_money_and_the_simulations_but_not_toward_30() -> None:
    """FR-4, FR-6 (PRD Glossary, Sliver): 29 tested + 2 Slivers is Not enough data, yet the Slivers' money counts and they are simulated."""
    slivers = (bet(900, 0.5, True, shares=0.9), bet(901, 0.5, True, shares=0.9))  # each wins $0.45
    thin = position_set(*(bet(i, 0.5, i % 3 == 0) for i in range(29)), slivers=slivers)
    result = skilltest.skill_test(thin, seed=SEED, unit_id="sliver-wallet")
    assert result.verdict is Verdict.NOT_ENOUGH_DATA and result.tested_count == 29 and result.sliver_count == 2
    without = skilltest.skill_test(position_set(*thin.tested), seed=SEED, unit_id="sliver-wallet")
    assert result.real_pnl - without.real_pnl == pytest.approx(0.90, abs=CENT)

    full = position_set(*(bet(i, 0.5, i % 3 == 0) for i in range(30)), slivers=slivers)
    with_slivers = skilltest.skill_test(full, seed=SEED, unit_id="sliver-wallet")
    assert with_slivers.tested_count == 30 and with_slivers.p_value is not None
    engine = skilltest._engine((*full.tested, *full.slivers), seed=SEED, unit_id="sliver-wallet")
    tested_only = skilltest._engine(full.tested, seed=SEED, unit_id="sliver-wallet")
    assert with_slivers.at_or_above == engine.at_or_above != tested_only.at_or_above  # the Slivers were simulated


def test_exact_real_pnl_differs_from_the_rounded_comparison_sum() -> None:
    """FR-4, Conventions › Money (Edvard, 2026-11-05): with many fractional amounts the shown Real PnL is the exact sum, not the whole-cent one."""
    bets = [bet(i, 0.335, True, shares=1.0) for i in range(2000)]  # each wins 0.665
    run = skilltest._engine(bets, seed=SEED, unit_id="fractions")
    assert run.real_pnl == pytest.approx(1330.00, abs=CENT)
    assert abs(run.real_cents / 100 - run.real_pnl) > 1.0


# --- p-value (FR-5) ---------------------------------------------------------------------------


def test_hand_check_p_value_on_the_engine() -> None:
    """FR-5, FR-13: 10 bets at 0.50, all won: p between 0.0003 and 0.002 (exact 1/1024), on the engine because 10 < 30."""
    wallet = SMALL["hand-check"]
    built = positions(wallet)
    expected = EXPECTED["wallets"]["hand-check"]
    run = skilltest._engine((*built.tested, *built.slivers), seed=SEED, unit_id=wallet.address)
    assert expected["p_at_least"] <= run.p_value <= expected["p_below"]
    assert skilltest.skill_test(built, seed=SEED, unit_id=wallet.address).verdict is Verdict.NOT_ENOUGH_DATA


@pytest.mark.parametrize("name", ["favourite-buyer", "sharp-trader", "thin-wallet", "stop-loss-trader"])
def test_synthetic_wallets_get_their_expected_verdict(name: str) -> None:
    """FR-5, FR-6, FR-13: each Synthetic Wallet's p range and Verdict match expected.json."""
    expected = EXPECTED["wallets"][name]
    result = skilltest.skill_test(positions(SMALL[name]), seed=SEED, unit_id=SMALL[name].address)
    assert result.verdict == expected["verdict"]
    if "p_below" in expected:
        assert result.p_value < expected["p_below"]
    if "p_at_least" in expected:
        assert result.p_value >= expected["p_at_least"]


def test_stop_loss_trader_reads_skilled_the_known_limit() -> None:
    """FR-11, FR-13 (Edvard, 2026-11-13): no edge, but its 33 held bets all won, so the Verdict reads Skilled (high confidence) on purpose."""
    wallet = SMALL["stop-loss-trader"]
    built = positions(wallet)
    result = skilltest.skill_test(built, seed=SEED, unit_id=wallet.address)
    assert result.verdict is Verdict.SKILLED and result.tested_count == 33 and len(built.left_out) == 67
    exit_pnl = sum(p.exit_pnl for p in built.left_out)
    assert result.real_pnl + exit_pnl == pytest.approx(EXPECTED["wallets"]["stop-loss-trader"]["total_pnl"], abs=CENT)


def test_a_fixed_fee_lowers_real_pnl_and_leaves_the_p_value() -> None:
    """FR-5: $1.50 on every Position lowers Real PnL by exactly the total fee; p-value and Verdict stay the same for the same Seed."""
    wallet = SMALL["sharp-trader"]
    built = positions(wallet)
    with_fees = replace(built, tested=tuple(replace(p, own_fees=1.5) for p in built.tested))
    before = skilltest.skill_test(built, seed=SEED, unit_id=wallet.address)
    after = skilltest.skill_test(with_fees, seed=SEED, unit_id=wallet.address)
    assert before.real_pnl - after.real_pnl == pytest.approx(150.00, abs=CENT)
    assert after.own_fees == pytest.approx(150.00, abs=CENT)
    assert (after.at_or_above, after.p_value, after.verdict) == (before.at_or_above, before.p_value, before.verdict)


def test_all_won_near_1_gives_the_product_of_the_prices() -> None:
    """FR-5, Conventions › Money (the tie test): bets all won at 0.97 to 0.99 tie only when all win, so p is about the product of the prices."""
    prices = [0.97 + 0.01 * (i % 3) for i in range(30)]
    run = skilltest._engine([bet(i, p, True) for i, p in enumerate(prices)], seed=SEED, unit_id="ties")
    product = math.prod(prices)
    sd = math.sqrt(product * (1 - product) / skilltest.SIMULATIONS)
    assert abs(run.p_value - product) < 4 * sd, (run.p_value, product)


@pytest.mark.slow
def test_coin_flippers_rarely_look_skilled(repetitions: int) -> None:
    """FR-5, FR-13: across the coin-flippers p < 0.05 for at most 7% and p < 0.01 for at most 2% (1,000 on CI Linux 3.14, else 100)."""
    limits = EXPECTED["coin_flippers"]
    p_values = []
    for wallet in synthetic.coin_flippers(repetitions):
        built = positions(wallet)
        assert built.tested_count == limits["bets_each"]
        p_values.append(skilltest.skill_test(built, seed=SEED, unit_id=wallet.address).p_value)
    assert sum(p < 0.05 for p in p_values) / len(p_values) <= limits["max_share_p_below_0_05"]
    assert sum(p < 0.01 for p in p_values) / len(p_values) <= limits["max_share_p_below_0_01"]


# --- one draw per Market (AD-20) --------------------------------------------------------------


def test_both_sides_of_one_market_share_the_draw() -> None:
    """AD-20: holding both sides at 0.50, exactly one wins in every Simulation, so every total is $0 and p is 1."""
    both = [bet(1, 0.5, True, side=0), bet(1, 0.5, False, side=1)]
    run = skilltest._engine(both, seed=SEED, unit_id="both-sides")
    assert run.at_or_above == skilltest.SIMULATIONS


@pytest.mark.parametrize("side", [0, 1])
def test_each_side_wins_at_its_entry_price(side: int) -> None:
    """AD-20, FR-5: whichever side of the Market it is, a Position at 0.30 wins in about 30% of Simulations."""
    run = skilltest._engine([bet(1, 0.3, True, side=side)], seed=SEED, unit_id=f"side-{side}")
    sd = math.sqrt(0.3 * 0.7 * skilltest.SIMULATIONS)
    assert abs(run.at_or_above - 0.3 * skilltest.SIMULATIONS) < 4 * sd


@pytest.mark.parametrize(
    "bad",
    [
        [bet(1, 0.5, True, side=0), bet(1, 0.5, True, side=1), bet(1, 0.5, True, side=2)],
        [replace(bet(1, 0.5, True), outcome=None)],
        [replace(bet(1, 0.5, True), entry_price=None)],
        [replace(bet(1, 0.5, True), entry_price=1.5)],
        [replace(bet(1, 0.5, True), shares_held=0.0)],
        [],
    ],
    ids=["three outcomes", "no outcome", "no price", "price above 1", "no shares", "no Positions"],
)
def test_bad_input_is_refused(bad: list[Position]) -> None:
    """AD-20, FR-4: a Market with three outcomes, a missing outcome or price, no shares or no Positions raise ValueError."""
    with pytest.raises(ValueError):
        skilltest._engine(bad, seed=SEED, unit_id="bad")


# --- Verdict (FR-6) ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("p_value", "verdict"),
    [(0.0001, Verdict.SKILLED), (0.0099, Verdict.SKILLED), (0.01, Verdict.LIKELY_SKILLED),
     (0.0499, Verdict.LIKELY_SKILLED), (0.05, Verdict.NO_EVIDENCE), (1.0, Verdict.NO_EVIDENCE)],
)
def test_verdict_thresholds(p_value: float, verdict: Verdict) -> None:
    """FR-6: p < 0.01 Skilled (high confidence), p < 0.05 Likely skilled, otherwise No evidence of skill."""
    assert skilltest.verdict_for(p_value) is verdict


def test_29_resolved_positions_give_not_enough_data_and_30_a_verdict() -> None:
    """FR-6, FR-10: 29 tested Positions give Not enough data, no p-value and no bins; 30 give a Verdict."""
    bets = [bet(i, 0.5, i % 2 == 0) for i in range(30)]
    short = skilltest.skill_test(position_set(*bets[:29]), seed=SEED, unit_id="w")
    assert short.verdict is Verdict.NOT_ENOUGH_DATA
    assert (short.p_value, short.at_or_above, short.simulations, short.bins) == (None, None, 0, ())
    enough = skilltest.skill_test(position_set(*bets), seed=SEED, unit_id="w")
    assert enough.verdict is not Verdict.NOT_ENOUGH_DATA and enough.p_value is not None


def test_the_public_function_cannot_skip_the_minimum() -> None:
    """FR-6 (Edvard, 2026-10-24): skill_test has no parameter that turns the 30-bet minimum off."""
    assert list(inspect.signature(skilltest.skill_test).parameters) == ["position_set", "seed", "unit_id", "scope"]


ENGINE_NAME = re.compile(r"\b_engine\b")


def engine_references(root: Path) -> list[str]:
    """Modules under `root`, other than core/skilltest.py, that mention `_engine`."""
    return [
        str(path.relative_to(root)) for path in sorted(root.rglob("*.py"))
        if path.relative_to(root).as_posix() != "core/skilltest.py"
        and ENGINE_NAME.search(path.read_text(encoding="utf-8"))
    ]


def test_only_the_tests_reference_the_engine() -> None:
    """FR-6 (Edvard, 2026-10-24): no module outside core/skilltest references the engine-level function; covers services and web too."""
    assert engine_references(SRC) == []


@pytest.mark.parametrize("source", ["from liquidoracle.core.skilltest import _engine\n",
                                    "run = getattr(skilltest, '_engine')\n"])
def test_planted_engine_reference_is_caught(tmp_path: Path, source: str) -> None:
    """FR-6 (Edvard, 2026-10-24): the rule fails on a planted reference in services."""
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "lookup.py").write_text(source, encoding="utf-8")
    assert engine_references(tmp_path) == ["services/lookup.py".replace("/", os.sep)]


# --- reproducibility (FR-7, AD-15, AD-17) -------------------------------------------------------


def test_same_data_and_seed_give_the_identical_result() -> None:
    """FR-7: the same Wallet and Seed give the identical result; another Seed gives other draws."""
    built = positions(SMALL["favourite-buyer"])
    first = skilltest.skill_test(built, seed=SEED, unit_id="w")
    assert skilltest.skill_test(built, seed=SEED, unit_id="w") == first
    assert skilltest.skill_test(built, seed=SEED + 1, unit_id="w").at_or_above != first.at_or_above


def test_position_order_does_not_change_the_result() -> None:
    """AD-15: Positions are sorted before drawing, so the order they arrive in never matters."""
    built = positions(wallet_named("coin-flipper-0000"))
    flipped = replace(built, tested=tuple(reversed(built.tested)))
    assert skilltest.skill_test(flipped, seed=SEED, unit_id="w") == skilltest.skill_test(built, seed=SEED, unit_id="w")


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_golden_count_is_reproduced(name: str) -> None:
    """AD-17: the stored count of Simulations at or above the Real PnL is reproduced exactly on every system."""
    wallet = wallet_named(name)
    built = positions(wallet)
    run = skilltest._engine((*built.tested, *built.slivers), seed=SEED, unit_id=wallet.address)
    assert run.at_or_above == GOLDEN[name]


SUBPROCESS_SCRIPT = """
import json
from liquidoracle.core import skilltest
from liquidoracle.core.positions import build_positions
from liquidoracle.data import synthetic
out = {}
for w in synthetic.small_wallets():
    built = build_positions(w.activity, {m.condition_id: m for m in w.markets})
    r = skilltest.skill_test(built, seed=44, unit_id=w.address)
    out[w.name] = [r.p_value, str(r.verdict), r.at_or_above]
print(json.dumps(out, sort_keys=True))
"""


def test_two_hash_seeds_give_identical_results() -> None:
    """FR-7, AD-15: two subprocesses with different PYTHONHASHSEED values give identical p-values and Verdicts."""
    outputs = []
    for hash_seed in ("0", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        done = subprocess.run([sys.executable, "-c", SUBPROCESS_SCRIPT], env=env, capture_output=True,
                              text=True, timeout=120, check=True)
        outputs.append(json.loads(done.stdout))
    assert outputs[0] == outputs[1]
    assert outputs[0]["sharp-trader"][1] == Verdict.SKILLED


def test_spawn_key_is_fixed_by_purpose_and_id() -> None:
    """AD-15: spawn_key is (purpose code, first 8 bytes of sha256 of the id); unknown purposes are refused."""
    assert rng.spawn_key("skilltest", "0xabc") == (1, int.from_bytes(sha256(b"0xabc").digest()[:8], "big"))
    with pytest.raises(ValueError):
        rng.spawn_key("lottery", "0xabc")


RANDOM_ALLOWED = {"SeedSequence", "PCG64", "Generator"}


def test_core_uses_no_global_or_hidden_randomness() -> None:
    """AD-15: no core module uses `random`, numpy's global random state or `hash()`."""
    problems = []
    for path in sorted((SRC / "core").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "random" for a in node.names):
                problems.append(f"{path.name}: import random")
            elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "random":
                problems.append(f"{path.name}: from random import")
            elif isinstance(node, ast.ImportFrom) and node.module == "numpy.random":
                problems += [f"{path.name}: numpy.random.{a.name}" for a in node.names if a.name not in RANDOM_ALLOWED]
            elif isinstance(node, ast.Name) and node.id in {"hash", "__import__"}:
                problems.append(f"{path.name}: {node.id}")
            elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)
                  and node.value.attr == "random" and node.attr not in RANDOM_ALLOWED):
                problems.append(f"{path.name}: .random.{node.attr}")
    assert problems == []


# --- the stored result (AD-22, AD-25, NFR-10) ---------------------------------------------------


@pytest.mark.parametrize("name", ["favourite-buyer", "sharp-trader", "stop-loss-trader"])
def test_result_carries_its_seed_scope_counts_and_bins(name: str) -> None:
    """AD-22, AD-25, FR-9: scope lookup, the Seed, counts, 40 bars centred on $0 plus two end bars covering every Simulation and the Real PnL."""
    wallet = SMALL[name]
    result = skilltest.skill_test(positions(wallet), seed=SEED, unit_id=wallet.address)
    assert (result.scope, result.seed, result.simulations) == ("lookup", SEED, skilltest.SIMULATIONS)
    bins = result.bins
    assert len(bins) == skilltest.CHART_BARS + 2
    assert bins[0].low is None and bins[-1].high is None
    assert sum(b.count for b in bins) == skilltest.SIMULATIONS
    edge = bins[-1].low
    assert bins[0].high == -edge and bins[1].low == -edge and bins[-2].high == edge
    assert all(a.high == b.low for a, b in zip(bins, bins[1:]))
    assert len({round(b.high - b.low, 6) for b in bins[1:-1]}) == 1  # equal bars
    assert -edge <= result.real_pnl <= edge  # FR-9: the axis includes the Real PnL
    tail = skilltest.CHART_TAIL * skilltest.SIMULATIONS
    assert bins[0].count <= tail and bins[-1].count <= tail


def test_real_pnl_above_every_simulation_stays_on_the_axis() -> None:
    """FR-9, AD-25: the stop-loss trader's Real PnL is above all 10,000 Simulations, and the axis still includes it."""
    wallet = SMALL["stop-loss-trader"]
    result = skilltest.skill_test(positions(wallet), seed=SEED, unit_id=wallet.address)
    assert result.at_or_above == 0
    assert result.real_pnl <= result.bins[-1].low


def test_a_1000_position_wallet_takes_under_10_seconds() -> None:
    """NFR-10, SM-3: the Skill Test on 1,000 Resolved Positions runs well inside the 10-second lookup budget."""
    bets = [bet(i, 0.1 + 0.8 * ((i * 37) % 81) / 80, i % 2 == 0) for i in range(1000)]
    started = time.perf_counter()
    result = skilltest.skill_test(position_set(*bets), seed=SEED, unit_id="big-wallet")
    elapsed = time.perf_counter() - started
    assert result.p_value is not None
    assert elapsed < 10.0, elapsed
