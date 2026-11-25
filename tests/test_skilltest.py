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
    "two-sided-40": 495,
    "linked-event": 3906,  # AD-20 negative-risk layout, from its first run (2026-11-21, Story 2.4 review)
}


def positions(wallet: SampleWallet) -> PositionSet:
    return build_positions(wallet.activity, {m.condition_id: m for m in wallet.markets}, listed=wallet.positions)


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


def golden_bets(name: str) -> tuple[list[Position], str]:
    """The Positions and random unit behind a golden count. `two-sided-40` pins the AD-20 side rule."""
    if name == "two-sided-40":
        bets = [b for i in range(40)
                for b in (bet(i, 0.2 + 0.01 * i, i % 3 == 0, side=0), bet(i, 0.35, i % 3 != 0, shares=50.0, side=1))]
        return bets, name
    if name == "linked-event":  # AD-20 (review, Story 2.4): pins the negative-risk layout through the real engine
        bets = [
            linked(1, 0.2, True), linked(2, 0.3, False), linked(3, 0.4, False), linked(3, 0.55, True, yes=False),
            linked(4, 0.6, True, event="e2", event_id="ev2"), linked(5, 0.7, False, event="e2", event_id="ev2"),
            bet(9, 0.5, True),
        ]
        return bets, name
    wallet = wallet_named(name)
    built = positions(wallet)
    return [*built.tested, *built.slivers], wallet.address


# --- Real PnL (FR-4) --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED["wallets"]))
def test_real_pnl_matches_the_hand_values(name: str) -> None:
    """FR-4: Real PnL over tested Positions and Slivers equals the hand value in expected.json to the cent."""
    expected = EXPECTED["wallets"][name]
    result = skilltest.skill_test(positions(SMALL[name]), seed=SEED, unit_id=SMALL[name].address)
    assert result.real_pnl == pytest.approx(expected["real_pnl"], abs=CENT)
    assert (result.tested_count, result.sliver_count) == (expected["tested"], expected["slivers"])


@pytest.mark.parametrize("name", sorted(EXPECTED["wallets"]))
def test_the_public_real_pnl_is_the_one_skill_test_stores(name: str) -> None:
    """FR-4, AD-10 (Story 4.2): `real_pnl`, which the Scan ranks on, gives exactly the Real PnL `skill_test` stores,
    with or without enough bets, and the hand value to the cent; so ranking and Verdict share one source."""
    built = positions(SMALL[name])
    result = skilltest.skill_test(built, seed=SEED, unit_id=SMALL[name].address)
    assert skilltest.real_pnl(built) == result.real_pnl
    assert skilltest.real_pnl(built) == pytest.approx(EXPECTED["wallets"][name]["real_pnl"], abs=CENT)
    if result.simulations:  # the engine's own sum, in its own order, agrees to the last bit
        assert skilltest._engine((*built.tested, *built.slivers), seed=SEED, unit_id="x").real_pnl == result.real_pnl


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


def test_chart_bins_count_the_simulations_after_own_fees() -> None:
    """AD-25, Conventions › Money: $2 on each of 100 Positions moves every Simulation down $200, two $100 bars, on the same axis."""
    wallet = SMALL["sharp-trader"]
    built = positions(wallet)
    with_fees = replace(built, tested=tuple(replace(p, own_fees=2.0) for p in built.tested))
    before = skilltest.skill_test(built, seed=SEED, unit_id=wallet.address).bins
    after = skilltest.skill_test(with_fees, seed=SEED, unit_id=wallet.address).bins
    assert [(b.low, b.high) for b in after] == [(b.low, b.high) for b in before]
    assert before[1].high - before[1].low == 100.0
    assert [b.count for b in after[1:-3]] == [b.count for b in before[3:-1]]


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


def two_sided(low_won: bool) -> list[Position]:
    """One Market, both sides held: side 0 (the smaller token_id) 1 share at 0.60, side 1 100 shares at 0.30."""
    return [bet(1, 0.6, low_won, shares=1.0, side=0), bet(1, 0.3, not low_won, side=1)]


def test_each_side_of_one_market_wins_at_its_own_price() -> None:
    """AD-20, FR-5: side 1 (wins on U > 1 - p) wins in about 30% of Simulations, and side 0 or side 1 in about 90%: never both."""
    sd = math.sqrt(0.3 * 0.7 * skilltest.SIMULATIONS)
    # Real result: side 1 won ($69.40). Only Simulations where side 1 wins reach it.
    side_1 = skilltest._engine(two_sided(low_won=False), seed=SEED, unit_id="two-sided")
    assert abs(side_1.at_or_above - 0.3 * skilltest.SIMULATIONS) < 4 * sd
    # Real result: side 0 won (-$29.60). Every Simulation where either side wins reaches it.
    side_0 = skilltest._engine(two_sided(low_won=True), seed=SEED, unit_id="two-sided")
    assert abs(side_0.at_or_above - 0.9 * skilltest.SIMULATIONS) < 4 * math.sqrt(0.9 * 0.1 * skilltest.SIMULATIONS)


BAD_INPUT = {
    "three outcomes": [bet(1, 0.5, True, side=0), bet(1, 0.5, True, side=1), bet(1, 0.5, True, side=2)],
    "no outcome": [replace(bet(1, 0.5, True), outcome=None)],
    "no price": [replace(bet(1, 0.5, True), entry_price=None)],
    "price above 1": [replace(bet(1, 0.5, True), entry_price=1.5)],
    "no shares": [replace(bet(1, 0.5, True), shares_held=0.0)],
    "endless shares": [replace(bet(1, 0.5, True), shares_held=math.inf)],
    "no fee amount": [replace(bet(1, 0.5, True), own_fees=None)],
    "fee not a number": [replace(bet(1, 0.5, True), own_fees=math.nan)],
    "one Market in two events": [replace(bet(1, 0.5, True, side=0), neg_risk_id="e1", yes_side=True),
                                 replace(bet(1, 0.5, False, side=1), neg_risk_id="e2")],
}


@pytest.mark.parametrize("name", sorted(BAD_INPUT))
def test_bad_input_is_refused_by_both_functions(name: str) -> None:
    """AD-20, FR-4, FR-6: bad Positions raise ValueError from skill_test (also below 30 bets) and from the engine."""
    with pytest.raises(ValueError):
        skilltest.skill_test(position_set(*BAD_INPUT[name]), seed=SEED, unit_id="bad")
    with pytest.raises(ValueError):
        skilltest._engine(BAD_INPUT[name], seed=SEED, unit_id="bad")
    with pytest.raises(ValueError):
        skilltest._engine([], seed=SEED, unit_id="bad")


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
    """AD-17, AD-20: the stored count of Simulations at or above the Real PnL is reproduced exactly on every system."""
    bets, unit_id = golden_bets(name)
    run = skilltest._engine(bets, seed=SEED, unit_id=unit_id)
    assert run.at_or_above == GOLDEN[name]


SUBPROCESS_SCRIPT = f"""
import json
from liquidoracle.core import skilltest
from liquidoracle.core.positions import build_positions
from liquidoracle.data import synthetic
out = {{}}
for w in synthetic.small_wallets():
    built = build_positions(w.activity, {{m.condition_id: m for m in w.markets}}, listed=w.positions)
    r = skilltest.skill_test(built, seed={SEED}, unit_id=w.address)
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


def randomness_problems(source: str) -> list[str]:
    """AD-15: uses of `random`, numpy's global random state or `hash()` in one module's source."""
    problems = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "random" or alias.name.startswith("numpy.random"):
                    problems.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[0] == "random":
                problems.append(f"from {module} import")
            elif module == "numpy" and any(a.name == "random" for a in node.names):
                problems.append("from numpy import random")
            elif module == "numpy.random":
                problems += [f"numpy.random.{a.name}" for a in node.names if a.name not in RANDOM_ALLOWED]
        elif isinstance(node, ast.Name) and node.id in {"hash", "__import__"}:
            problems.append(node.id)
        elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)
              and node.value.attr == "random" and node.attr not in RANDOM_ALLOWED):
            problems.append(f".random.{node.attr}")
    return problems


def test_core_uses_no_global_or_hidden_randomness() -> None:
    """AD-15: no core module uses `random`, numpy's global random state or `hash()`."""
    problems = {path.name: randomness_problems(path.read_text(encoding="utf-8"))
                for path in sorted((SRC / "core").glob("*.py"))}
    assert {name: found for name, found in problems.items() if found} == {}


@pytest.mark.parametrize("source", [
    "import random\n",
    "from random import random\n",
    "from numpy import random\n",
    "import numpy.random as npr\nnpr.seed(1)\n",
    "import numpy as np\nnp.random.seed(1)\n",
    "import numpy as np\nrng = np.random.default_rng()\n",
    "from numpy.random import default_rng\n",
    "key = hash('0xabc')\n",
])
def test_planted_randomness_is_caught(source: str) -> None:
    """AD-15: the ban catches each planted form of hidden randomness."""
    assert randomness_problems(source) != []


def test_seeded_generators_are_allowed() -> None:
    """AD-15: SeedSequence, PCG64 and Generator are the allowed way in."""
    source = "import numpy as np\ng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(1)))\n"
    assert randomness_problems(source) == []


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
    if result.at_or_above <= tail:  # the Real PnL sets the axis, so it is as tight as a round width allows
        assert edge <= 2.5 * abs(result.real_pnl)


@pytest.mark.parametrize("bets", range(30, 61, 3))
@pytest.mark.parametrize("shares", [0.03, 0.2, 1.0, 100.0])
def test_bins_keep_their_contract_for_small_and_large_stakes(bets: int, shares: float) -> None:
    """AD-25, FR-9: for tiny to large stakes the bars are equal whole-cent widths, each end bar holds at most 0.1%, and the Real PnL is on the axis."""
    run = skilltest._engine([bet(i, 0.5, i % 4 == 0, shares=shares) for i in range(bets)], seed=SEED, unit_id=f"{bets}")
    inner = run.bins[1:-1]
    widths = {round(b.high - b.low, 9) for b in inner}
    assert len(widths) == 1 and round(widths.pop() * 100, 9).is_integer()
    tail = skilltest.CHART_TAIL * skilltest.SIMULATIONS
    assert run.bins[0].count <= tail and run.bins[-1].count <= tail
    assert run.bins[0].high <= run.real_pnl <= run.bins[-1].low
    assert sum(b.count for b in run.bins) == skilltest.SIMULATIONS


def test_a_total_on_a_bar_edge_lands_in_the_bar_that_starts_there() -> None:
    """AD-25: totals in steps of $0.20 on $0.10 bars fill only the bars that start on an even tenth (floor(0.6 / 0.1) is 5)."""
    run = skilltest._engine([bet(i, 0.5, i % 2 == 0, shares=0.2) for i in range(30)], seed=SEED, unit_id="edges")
    inner = run.bins[1:-1]
    assert inner[0].high - inner[0].low == pytest.approx(0.1)
    odd = [b for b in inner[:-1] if round(b.low * 10) % 2 != 0]  # the last bar also holds its top edge
    assert sum(b.count for b in odd) == 0 and sum(b.count for b in inner) > 0


@pytest.mark.parametrize(("needed", "width"), [(0.001, 0.01), (0.013, 0.02), (0.021, 0.05), (0.21, 0.25),
                                               (3.1, 5.0), (7.0, 10.0), (100.0, 100.0), (101.0, 200.0)])
def test_bar_width_is_the_smallest_round_whole_cent_width(needed: float, width: float) -> None:
    """AD-25: the bar width is the smallest of 1, 2, 2.5 or 5 times a power of ten that is at least what is needed, in whole cents."""
    assert skilltest._nice(max(needed, skilltest._MIN_BAR_WIDTH)) == width


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


def test_a_negative_own_fee_is_refused() -> None:
    """AD-12 (Story 2.3): the builder's fee check never passes a negative fee, so one reaching the Skill Test is a bug."""
    wallet = SMALL["sharp-trader"]
    built = positions(wallet)
    broken = replace(built, tested=(replace(built.tested[0], own_fees=-0.01), *built.tested[1:]))
    with pytest.raises(ValueError, match="negative Own Fee"):
        skilltest.skill_test(broken, seed=SEED, unit_id=wallet.address)


# --- Linked bets: negative-risk events and the uncoupled share (AD-20, Story 2.4) ------------

RUNS = skilltest.SIMULATIONS


def linked(i: int, price: float, won: bool, *, yes: bool = True, event: str = "e1", event_id: str = "ev1",
           shares: float = 100.0) -> Position:
    """A held Position in Market `n{i}` of the negative-risk event `event`, on its Yes or No token."""
    return replace(
        bet(i, price, won, shares=shares), condition_id=f"n{i:05d}", token_id=f"n{i:05d}-{'yes' if yes else 'no'}",
        event_id=event_id, neg_risk_id=event, yes_side=yes,
    )


def wins_of(bets: list[Position], unit_id: str = "linked") -> dict[str, list[bool]]:
    ordered, won = skilltest._simulated_wins(bets, seed=SEED, unit_id=unit_id, simulations=RUNS)
    return {b.token_id: [bool(x) for x in won[:, i]] for i, b in enumerate(ordered)}


def near_price(wins: list[bool], price: float) -> bool:
    """Within 4 standard deviations of the price over RUNS Simulations (FR-5)."""
    return abs(sum(wins) - price * RUNS) < 4 * math.sqrt(price * (1 - price) * RUNS)


def test_a_planted_negative_risk_event_has_at_most_one_winner() -> None:
    """AD-20 (Story 2.4): three Yes Positions at 0.2, 0.3, 0.4 in one event: at most one wins per Simulation, and
    each wins at its own price. Drawn independently, two win together in about a quarter of the Simulations."""
    prices = (0.2, 0.3, 0.4)
    bets = [linked(i, p, False) for i, p in enumerate(prices)]
    wins = wins_of(bets)
    assert all(sum(row) <= 1 for row in zip(*wins.values()))
    assert all(near_price(wins[b.token_id], p) for b, p in zip(bets, prices))
    loose = wins_of([replace(b, neg_risk_id=None, yes_side=False) for b in bets])
    assert sum(1 for row in zip(*loose.values()) if sum(row) > 1) > 0.15 * RUNS


def test_no_bets_in_one_event_lose_at_most_once() -> None:
    """AD-20: No at 0.9, 0.8 and 0.85 (regions 0.1, 0.2, 0.15): at most one Market wins, so at most one No loses."""
    prices = (0.9, 0.8, 0.85)
    bets = [linked(i, p, True, yes=False) for i, p in enumerate(prices)]
    wins = wins_of(bets)
    assert all(sum(not w for w in row) <= 1 for row in zip(*wins.values()))
    assert all(near_price(wins[b.token_id], p) for b, p in zip(bets, prices))


def test_both_sides_of_a_negative_risk_market_and_its_event_mate() -> None:
    """AD-20: Yes 0.3 and No 0.6 in one Market (region max(0.3, 0.4)) and Yes 0.2 in another: Yes and No never both
    win, and when the other Market wins, this one's Yes loses and its No wins."""
    yes, no, other = linked(1, 0.3, False), linked(1, 0.6, True, yes=False), linked(2, 0.2, False)
    wins = wins_of([yes, no, other])
    assert not any(y and n for y, n in zip(wins[yes.token_id], wins[no.token_id]))
    assert all(n and not y for y, n, o in zip(wins[yes.token_id], wins[no.token_id], wins[other.token_id]) if o)
    assert near_price(wins[yes.token_id], 0.3) and near_price(wins[no.token_id], 0.6) and near_price(wins[other.token_id], 0.2)


def test_regions_summing_above_1_keep_every_win_chance() -> None:
    """AD-20: Yes 0.6 and 0.7 cannot be disjoint; each still wins at its price, and they overlap only as the prices
    force (both win in about 0.6 + 0.7 - 1 = 30%)."""
    a, b = linked(1, 0.6, False), linked(2, 0.7, False)
    wins = wins_of([a, b])
    assert near_price(wins[a.token_id], 0.6) and near_price(wins[b.token_id], 0.7)
    assert near_price([x and y for x, y in zip(wins[a.token_id], wins[b.token_id])], 0.3)


def test_two_events_draw_apart() -> None:
    """AD-20: Markets of two different negative-risk events do not share a draw: both win together sometimes."""
    wins = wins_of([linked(1, 0.5, False, event="e1"), linked(2, 0.5, False, event="e2")])
    together = sum(1 for x, y in zip(*wins.values()) if x and y)
    assert near_price([True] * together + [False] * (RUNS - together), 0.25)


def test_linked_draws_are_repeatable_and_order_free() -> None:
    """AD-15: the same linked Positions and Seed give the identical result, in any order."""
    bets = [linked(i, p, i == 1) for i, p in enumerate((0.2, 0.3, 0.4))] + [bet(9, 0.5, True)]
    first = skilltest._engine(bets, seed=SEED, unit_id="linked")
    assert skilltest._engine(bets[::-1], seed=SEED, unit_id="linked") == first


def test_the_uncoupled_share_counts_event_mates_that_share_no_draw() -> None:
    """AD-20: two tested Positions in one Gamma event but different Markets, not negative-risk, both count; event-mates
    in one negative-risk event, both sides of one Market, and a Position alone in its event do not."""
    loose = [replace(bet(1, 0.5, True), event_id="ev9"), replace(bet(2, 0.5, True), event_id="ev9")]
    coupled = [linked(3, 0.2, False), linked(4, 0.3, True)]
    same_market = [replace(bet(5, 0.5, True, side=0), event_id="ev7"), replace(bet(5, 0.4, False, side=1), event_id="ev7")]
    alone = [replace(bet(6, 0.5, True), event_id="ev6"), bet(7, 0.5, True)]
    tested = [*loose, *coupled, *same_market, *alone]
    assert skilltest.uncoupled_share(tested) == 2 / 8
    assert skilltest.uncoupled_share([]) == 0.0
    mixed = [linked(1, 0.2, False), replace(bet(2, 0.5, True), event_id="ev1")]  # one coupled, one not, same event
    assert skilltest.uncoupled_share(mixed) == 1.0


@pytest.mark.parametrize(("total", "noted"), [(5, True), (10, False)])
def test_the_honesty_note_is_above_20_percent(total: int, noted: bool) -> None:
    """AD-20, FR-11: two uncoupled event-mates among 5 tested Positions (40%) get the note; among 10 (exactly 20%) not."""
    tested = [replace(bet(i, 0.5, True), event_id="ev" if i < 2 else None) for i in range(total)]
    result = skilltest.skill_test(position_set(*tested), seed=SEED, unit_id="note")
    assert result.verdict is Verdict.NOT_ENOUGH_DATA  # the share is stored with every result, also this one
    assert result.uncoupled_share == 2 / total
    assert skilltest.mostly_uncoupled(result) is noted


def test_a_markets_region_is_its_larger_side_not_both() -> None:
    """AD-20: Yes 0.5 and No 0.5 in one Market take a region of 0.5 (the larger side), so Yes 0.5 in a second Market
    fits beside it: the two Yes never both win, and when the second wins, the first Market's No wins."""
    yes, no, other = linked(1, 0.5, False), linked(1, 0.5, True, yes=False), linked(2, 0.5, False)
    wins = wins_of([yes, no, other])
    assert not any(y and o for y, o in zip(wins[yes.token_id], wins[other.token_id]))
    assert all(n for n, o in zip(wins[no.token_id], wins[other.token_id]) if o)
