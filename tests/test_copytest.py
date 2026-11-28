"""The Copy Test's per-Wallet part: the Copy Sample, Follower PnL and Follower Return, the Scan's Copy phase
and the job that runs it alone on a finished Scan (FR-18a; AD-5, AD-15, AD-19, AD-22; Story 6.2).

The core tests hand in Positions, fills and price points. The Scan tests write made-up Wallets as Sample
files, some with price paths, and run a real offline Scan over them with the worker, so the Copy phase
reads frozen snapshots and fetches prices through the offline client. A recording wrapper counts what the
phase asks its client for and can stand in for Polymarket not answering. No socket is opened (AD-17).

The three-Position reference made without the app's code is in `test_reference_follower.py`.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_holdup import DAY, SEED, address, counts, offline_scan, planted_client, planted_wallet  # noqa: F401
from test_watchlist import Row, hand_scan

from liquidoracle.core import copytest, holdup, rng
from liquidoracle.core.prices import MAX_AGE
from liquidoracle.data import synthetic
from liquidoracle.data.errors import PolymarketUnavailable
from liquidoracle.data.store import COPY_TEST, SCAN, SCAN_BEFORE, JobStatus, ScanStep, Store
from liquidoracle.records import (
    ActivityRow,
    CopyResult,
    FollowerResult,
    Market,
    Position,
    PricePoint,
    SampleWallet,
    Verdict,
)
from liquidoracle.services import scan as scan_module
from liquidoracle.services.jobs import FINISHED, Jobs, Worker
from liquidoracle.services.scans_page import ScansPage

T0 = synthetic.CUTOFF + 3600  # a buy an hour after the Cut-off Date
MINUTE = 60
ONE, FIVE, THIRTY = copytest.COPY_DELAYS


# --- hand-made Positions, fills and prices --------------------------------------------------------------


def condition(n: int) -> str:
    return f"0x{n:064x}"


def token(n: int) -> str:
    return str(1000 + n)


def market(n: int, *, won: bool = True, rate: float | None = None, exponent: float | None = None,
           fees: bool = False) -> Market:
    return Market(condition(n), True, T0 + 5 * 86_400, (token(n), token(n) + "9"), (1.0, 0.0) if won else (0.0, 1.0),
                  fees_enabled=fees, fee_rate=rate, fee_exponent=exponent)


def position(n: int, *, bought: float = 100.0, held: float | None = None, won: bool = True,
             price: float = 0.5) -> Position:
    held = bought if held is None else held
    return Position(condition(n), token(n), 1.0 if won else 0.0, price, bought, bought - held, held, 0.0, 0.0)


def buy(n: int, t: int = T0, size: float = 100.0, price: float = 0.5) -> ActivityRow:
    return ActivityRow("TRADE", condition(n), t, size, size * price, price, token(n), "BUY")


def flat(n: int, price: float, t: int = T0, minutes: Sequence[int] = range(-2, 33)) -> list[PricePoint]:
    """One point a minute around a buy at `t`, all at one price."""
    return [PricePoint(token(n), t + m * MINUTE, price) for m in minutes]


def follow(sample: Sequence[Position], rows: Sequence[ActivityRow], markets: Sequence[Market],
           points: Sequence[PricePoint], delay: int = FIVE) -> FollowerResult:
    by_token: dict[str, list[PricePoint]] = {}
    for point in sorted(points, key=lambda p: p.t):
        by_token.setdefault(point.token_id, []).append(point)
    return copytest.follow(
        sample, copytest.buy_fills(sample, rows), {m.condition_id: m for m in markets},
        lambda token_id: by_token.get(token_id, ()), delay,
    )


# --- the Copy Sample (PRD Glossary, FR-18a, AD-15) ------------------------------------------------------


def test_fr18a_a_small_after_part_is_sampled_whole() -> None:
    """FR-18a (matrix "Small after part"): with at most 100 tested after Positions the Copy Sample is all of them,
    in (condition, token) order: "priced 60 of 60". Exactly 100 is still all of them."""
    sixty = [position(n) for n in range(60)]
    sample = copytest.copy_sample(reversed(sixty), seed=SEED, wallet="0xw")
    assert sample == tuple(sixty) and copytest.SAMPLE_SIZE == 100
    hundred = [position(n) for n in range(100)]
    assert copytest.copy_sample(hundred, seed=SEED, wallet="0xw") == tuple(hundred)


def test_fr18a_a_large_after_part_gives_100_drawn_with_the_seed() -> None:
    """FR-18a, AD-15 (matrix "Large after part"): 250 tested after Positions give 100 of them, no Position twice;
    the same Seed gives the same 100 whatever order the Positions arrive in; another Seed, or another Wallet with
    the same Positions, gives another sample."""
    many = [position(n) for n in range(250)]
    sample = copytest.copy_sample(many, seed=SEED, wallet="0xw")
    assert len(sample) == len(set(sample)) == 100 and set(sample) < set(many)
    assert list(sample) == sorted(sample, key=lambda p: (p.condition_id, p.token_id))
    assert copytest.copy_sample(many[::-1], seed=SEED, wallet="0xw") == sample
    assert copytest.copy_sample(many[100:] + many[:100], seed=SEED, wallet="0xw") == sample
    assert copytest.copy_sample(many, seed=SEED + 1, wallet="0xw") != sample
    assert copytest.copy_sample(many, seed=SEED, wallet="0xv") != sample
    assert len(copytest.copy_sample(many[:101], seed=SEED, wallet="0xw")) == 100  # one over: drawn, not all


def test_ad15_the_copy_sample_has_its_own_random_purpose() -> None:
    """AD-15: the draw's purpose is `copysample`, code 3, a code that never changes; the earlier purposes keep theirs."""
    assert copytest.PURPOSE == "copysample"
    assert rng.PURPOSES == {"skilltest": 1, "holdup": 2, "copysample": 3}
    many = [position(n) for n in range(250)]
    picks = rng.generator(SEED, "copysample", "0xw").choice(250, size=100, replace=False)
    assert copytest.copy_sample(many, seed=SEED, wallet="0xw") == tuple(many[i] for i in sorted(int(i) for i in picks))


SUBPROCESS_SCRIPT = f"""
import json
from liquidoracle.core import copytest
from liquidoracle.core.positions import build_positions
from liquidoracle.data import synthetic
from liquidoracle.records import Position
many = [Position(f"0x{{n:064x}}", str(n), 1.0, 0.5, 100.0, 0.0, 100.0, 0.0, 0.0) for n in range(250)]
out = {{"sample": [p.token_id for p in copytest.copy_sample(set(many), seed={SEED}, wallet="0xw")]}}
for w in synthetic.small_wallets():
    if w.name not in ("forecaster", "speed-trader"):
        continue
    markets = {{m.condition_id: m for m in w.markets}}
    rows = [a for a in w.activity if a.timestamp >= synthetic.CUTOFF]
    listed = [p for p in w.positions if p.first_entry_at >= synthetic.CUTOFF]
    tested = build_positions(rows, markets, listed=listed).tested
    sample = copytest.copy_sample(set(tested), seed={SEED}, wallet=w.address)
    points = {{}}
    for point in w.prices:
        points.setdefault(point.token_id, []).append(point)
    result = copytest.copy_result(w.address, len(tested), sample, copytest.buy_fills(sample, rows), markets,
                                  lambda t: points.get(t, ()))
    out[w.name] = [[r.priced, r.left_out, r.follower_pnl, r.spent, r.own_pnl] for r in result.delays]
print(json.dumps(out, sort_keys=True))
"""


def test_two_hash_seeds_give_the_same_copy_sample_and_follower_numbers() -> None:
    """FR-7, AD-15: two subprocesses with different PYTHONHASHSEED values, handed the Positions as a set, give the
    identical Copy Sample and the identical Follower numbers, to the last bit."""
    outputs = []
    for hash_seed in ("0", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        done = subprocess.run([sys.executable, "-c", SUBPROCESS_SCRIPT], env=env, capture_output=True,
                              text=True, timeout=120, check=True)
        outputs.append(json.loads(done.stdout))
    assert outputs[0] == outputs[1]
    assert len(outputs[0]["sample"]) == 100 and outputs[0]["forecaster"][2][0] == 100


# --- Follower PnL, Follower Fee and Follower Return (PRD Glossary, FR-18a) --------------------------------


def test_fr18a_one_buy_with_no_fee() -> None:
    """FR-18a (matrix "One buy, no fee"): 100 shares bought and held, outcome 1, price 0.60 five minutes after the
    buy: the follower pays 0.605, makes $39.50 on $60.50 spent, a Follower Return of 65.3%."""
    result = follow([position(1)], [buy(1)], [market(1)], flat(1, 0.60))
    assert (result.delay, result.priced, result.left_out) == (300, 1, 0)
    assert result.follower_pnl == pytest.approx(39.50, abs=1e-9) and result.spent == pytest.approx(60.50, abs=1e-9)
    assert round(100 * result.follower_return, 1) == 65.3
    assert result.own_pnl == pytest.approx(50.0)  # the Wallet's own: 100 x (1 - 0.50)
    lost = follow([position(1, won=False)], [buy(1)], [market(1, won=False)], flat(1, 0.60))
    assert lost.follower_pnl == pytest.approx(-60.50, abs=1e-9) and lost.follower_return == pytest.approx(-1.0)


def test_fr18a_the_price_is_the_one_recorded_a_copy_delay_after_the_buy() -> None:
    """FR-18a, AD-24: each Copy Delay reads the price recorded then (`price_at`: the last point at or before that
    time), never the price at the buy or a later one."""
    points = [PricePoint(token(1), T0 + m * MINUTE, 0.50 + m / 100) for m in range(-2, 33)]  # 0.51 at +1, 0.80 at +30
    for delay, recorded in ((ONE, 0.51), (FIVE, 0.55), (THIRTY, 0.80)):
        result = follow([position(1)], [buy(1)], [market(1)], points, delay)
        assert result.spent == pytest.approx(100 * (recorded + 0.005), abs=1e-9)
        assert result.follower_pnl == pytest.approx(100 * (1 - recorded - 0.005), abs=1e-9)
    between = [PricePoint(token(1), T0 + 290, 0.40), PricePoint(token(1), T0 + 301, 0.90)]
    assert follow([position(1)], [buy(1)], [market(1)], between).spent == pytest.approx(40.5)  # 0.90 is a second late


def test_fr18a_a_fill_counts_for_its_share_of_the_shares_held() -> None:
    """FR-18a (matrix "Part sold before resolution"): 100 bought in one fill and 40 held at resolution: the fill is
    copied with s = 40. With two fills of 300 and 100 and 300 held, they count for 225 and 75."""
    sold = follow([position(1, held=40.0)], [buy(1)], [market(1)], flat(1, 0.60))
    assert sold.spent == pytest.approx(40 * 0.605, abs=1e-9) and sold.follower_pnl == pytest.approx(40 * 0.395, abs=1e-9)
    later = T0 + 7 * MINUTE
    two = follow(
        [position(2, bought=400.0, held=300.0)], [buy(2, T0, 300.0), buy(2, later, 100.0)], [market(2)],
        [*flat(2, 0.30), *flat(2, 0.50, later, range(4, 33))],  # 0.30 five minutes after the first, 0.50 after the second
    )
    assert two.spent == pytest.approx(225 * 0.305 + 75 * 0.505, abs=1e-9)
    assert two.follower_pnl == pytest.approx(225 * 0.695 + 75 * 0.495, abs=1e-9)


def test_fr18a_a_position_with_one_unpriced_fill_is_left_out_of_that_delay_whole() -> None:
    """FR-18a (Edvard, 2026-11-28; matrix "One fill of three has no price"): a Position bought in three fills whose
    second fill has no price at 5 minutes is left out of the 5-minute sums whole and counted there; at 1 minute,
    where all three have a price, it is priced in full. The other Position is not affected."""
    second, third = T0 + 3600, T0 + 7200
    rows = [buy(1, T0, 50.0), buy(1, second, 30.0), buy(1, third, 20.0), buy(2)]
    points = [
        *flat(1, 0.60), *flat(1, 0.60, third),
        *flat(1, 0.60, second, range(-2, 3)),  # the second fill's prices stop 2 minutes after it
        *flat(2, 0.40),
    ]
    sample, markets = [position(1), position(2)], [market(1), market(2)]
    at_one = follow(sample, rows, markets, points, ONE)
    assert (at_one.priced, at_one.left_out) == (2, 0)
    assert at_one.spent == pytest.approx(100 * 0.605 + 100 * 0.405, abs=1e-9)
    at_five = follow(sample, rows, markets, points, FIVE)
    assert (at_five.priced, at_five.left_out) == (1, 1)
    assert at_five.spent == pytest.approx(100 * 0.405, abs=1e-9)  # nothing of Position 1, not even its priced fills
    assert at_five.follower_pnl == pytest.approx(100 * 0.595, abs=1e-9)
    assert at_five.own_pnl == pytest.approx(50.0)  # the Wallet's own PnL covers the same one Position


def test_fr18a_a_price_older_than_two_minutes_is_no_price() -> None:
    """FR-18c, AD-24: a buy whose last recorded price is more than 2 minutes old at the Copy Delay has no price
    there, so its Position is left out; exactly 2 minutes old still counts."""
    old = [PricePoint(token(1), T0 + FIVE - MAX_AGE - 1, 0.60)]
    assert follow([position(1)], [buy(1)], [market(1)], old).left_out == 1
    just = [PricePoint(token(1), T0 + FIVE - MAX_AGE, 0.60)]
    assert follow([position(1)], [buy(1)], [market(1)], just).priced == 1


def test_fr18a_the_price_paid_is_capped_at_1() -> None:
    """FR-18a (matrix "Price close to 1"): a recorded 0.998 plus the Spread Allowance would be 1.003; the follower
    pays 1.00, so a winning fill makes $0 and a fee Market charges nothing on it."""
    assert copytest.SPREAD_ALLOWANCE == 0.005
    result = follow([position(1)], [buy(1)], [market(1, fees=True, rate=0.05, exponent=1.0)], flat(1, 0.998))
    assert result.spent == pytest.approx(100.0, abs=1e-9) and result.follower_pnl == pytest.approx(0.0, abs=1e-9)
    under = follow([position(1)], [buy(1)], [market(1)], flat(1, 0.995))  # 0.995 + 0.005 is exactly 1
    assert under.spent == pytest.approx(100.0, abs=1e-9)


@pytest.mark.parametrize("exponent", [0.0, -1.0, 0.5, 2.0])
def test_fr18a_no_fee_at_the_cap_whatever_the_exponent(exponent: float) -> None:
    """FR-18a (Story 6.2 review): at a price paid of exactly 1, p(1 - p) is 0, so the Follower Fee is 0 for every
    exponent: an exponent of 0 does not charge the full rate there, and a negative one does not end the job with
    a division by zero. Below the cap the schedule applies as written."""
    capped = market(1, fees=True, rate=0.05, exponent=exponent)
    assert copytest.follower_fee(100.0, 1.0, capped) == 0.0 and copytest.follower_fee(100.0, 0.0, capped) == 0.0
    result = follow([position(1)], [buy(1)], [capped], flat(1, 0.999))
    assert result.spent == pytest.approx(100.0, abs=1e-9) and result.follower_pnl == pytest.approx(0.0, abs=1e-9)
    assert copytest.follower_fee(100.0, 0.5, capped) == pytest.approx(100 * 0.05 * 0.25**exponent)


def test_fr18a_a_copy_time_after_the_market_closed_has_no_rule_of_its_own() -> None:
    """FR-18a (Story 6.2 review; the AI's reading of the plan as written): a buy so close to the Market's close that
    the Copy Delay ends after it is priced like any other, at the price recorded then, and left out when none was
    recorded. Nothing looks at the Market's closing time."""
    late = replace(market(1), closed_time=T0 + 10 * MINUTE)  # closes 10 minutes after the buy
    recorded = follow([position(1)], [buy(1)], [late], flat(1, 0.999), THIRTY)
    assert (recorded.priced, recorded.spent) == (1, pytest.approx(100.0, abs=1e-9))
    silent = follow([position(1)], [buy(1)], [late], flat(1, 0.999, minutes=range(-2, 11)), THIRTY)
    assert (silent.priced, silent.left_out, silent.spent) == (0, 1, 0.0)


@pytest.mark.parametrize(("rate", "exponent"), [(0.05, 1.0), (0.03, 1.0), (0.25, 2.0), (0.02, 0.5)])
def test_fr18a_the_follower_fee_follows_the_markets_schedule(rate: float, exponent: float) -> None:
    """FR-18a (matrix "Market with a fee"; Edvard, 2026-11-28): the Follower Fee is s x rate x (p(1 - p))^exponent at
    the price paid, with the Market's listed rate; it comes off the PnL and is added to the money spent."""
    paid = 0.605
    fee = 100 * rate * (paid * (1 - paid)) ** exponent
    fee_market = market(1, fees=True, rate=rate, exponent=exponent)
    assert copytest.follower_fee(100.0, paid, fee_market) == pytest.approx(fee, rel=1e-12)
    result = follow([position(1)], [buy(1)], [fee_market], flat(1, 0.60))
    assert result.spent == pytest.approx(60.50 + fee, abs=1e-9)
    assert result.follower_pnl == pytest.approx(39.50 - fee, abs=1e-9)


@pytest.mark.parametrize("no_fee", [
    market(1), market(1, fees=False, rate=0.05, exponent=1.0), market(1, fees=True), market(1, fees=True, rate=0.05),
    market(1, fees=True, exponent=1.0),
], ids=["fees off", "fees off with a schedule", "no schedule", "no exponent", "no rate"])
def test_fr18a_no_fee_where_the_market_charges_none(no_fee: Market) -> None:
    """FR-18a (matrix "Market with no fee"): fees off, or no schedule listed, is a Follower Fee of 0."""
    assert copytest.follower_fee(100.0, 0.5, no_fee) == 0.0
    assert follow([position(1)], [buy(1)], [no_fee], flat(1, 0.60)).spent == pytest.approx(60.50, abs=1e-9)


def test_fr18a_nothing_priced_gives_no_follower_return() -> None:
    """FR-18a (matrix "Nothing priced at a delay"): when no Position has a price at a delay, the Follower PnL and
    the money spent are $0, there is no Follower Return (never a division by zero) and every Position is counted
    as left out. An empty Copy Sample gives the same, with nothing left out."""
    result = follow([position(1), position(2)], [buy(1), buy(2)], [market(1), market(2)], flat(1, 0.6, minutes=range(0, 20)),
                    THIRTY)
    assert (result.priced, result.left_out, result.follower_pnl, result.spent, result.own_pnl) == (0, 2, 0.0, 0.0, 0.0)
    assert result.follower_return is None
    empty = follow([], [], [], [])
    assert (empty.priced, empty.left_out, empty.follower_return) == (0, 0, None)


def test_fr18a_only_the_sampled_positions_buys_are_copied() -> None:
    """FR-18a, AD-10: the fills copied are the BUY trades of the sampled Positions; sells, other tokens and other
    row types are not. A sampled Position with no buy fill is an error, never a silent "no price"."""
    rows = [
        buy(1, T0 + 60), buy(1, T0), buy(2),
        ActivityRow("TRADE", condition(1), T0 + 90, 10.0, 6.0, 0.6, token(1), "SELL"),
        ActivityRow("REDEEM", condition(1), T0 + 9000, 90.0, 90.0, 1.0),
    ]
    fills = copytest.buy_fills([position(1)], rows)
    assert list(fills) == [(condition(1), token(1))]
    assert [row.timestamp for row in fills[(condition(1), token(1))]] == [T0, T0 + 60]  # oldest first
    assert copytest.fill_times(fills) == {token(1): (T0, T0 + 60)}
    with pytest.raises(ValueError, match="no buy fill"):
        follow([position(3)], rows, [market(3)], flat(3, 0.5))


def test_fr18a_who_is_priced() -> None:
    """FR-18a, FR-18b (matrix "Who is priced"): every Passer is priced, with 4 after bets or none; any other Wallet
    needs the Minimum After-bets, 10, because with fewer it can never be in the Copy Pool."""
    assert holdup.MIN_AFTER_BETS == 10
    assert copytest.is_priced(True, 4) and copytest.is_priced(True, 0)
    assert not copytest.is_priced(False, 9) and copytest.is_priced(False, 10)


def test_fr18a_a_copy_result_has_the_three_delays_shortest_first() -> None:
    """FR-18a: the Copy Delays are 1, 5 and 30 minutes and the Main Copy Delay is 5; a Wallet's result holds one
    result per delay, shortest first, with its "priced N of M"."""
    assert copytest.COPY_DELAYS == (60, 300, 1800) and copytest.MAIN_COPY_DELAY == 300
    sample = [position(1)]
    result = copytest.copy_result(
        "0xw", 250, sample, copytest.buy_fills(sample, [buy(1)]), {condition(1): market(1)}, lambda _: flat(1, 0.6),
        not_fully_read=True,
    )
    assert (result.wallet, result.after_positions, result.sampled, result.not_fully_read) == ("0xw", 250, 1, True)
    assert [r.delay for r in result.delays] == [60, 300, 1800]
    assert result.at(300) is result.delays[1]
    with pytest.raises(KeyError):
        result.at(120)


# --- the Copy phase of a Scan (AD-5, AD-19) --------------------------------------------------------------


def pathed_wallet(name: str, before: tuple[int, int], after: tuple[int, int], path: str) -> SampleWallet:
    """`planted_wallet` whose later bets have a price path: "drift" (the forecaster's) or "jump" (the speed trader's)."""
    made = synthetic._exact(name, before[0], 0.50, won=before[1])  # noqa: SLF001
    made += [
        replace(b, bought_at=synthetic.CUTOFF + i * synthetic.DAY, path=path)
        for i, b in enumerate(synthetic._exact(f"{name} after", after[0], 0.50, won=after[1]))  # noqa: SLF001
    ]
    return synthetic._wallet(name, made, anchors=True)  # noqa: SLF001


def copy_cast() -> list[SampleWallet]:
    """Six planted Wallets: a Passer with a drifting price (100 later bets), a Passer with 4 later bets whose price
    jumps, a Passer that stopped betting, a quiet Wallet (9 later bets), one with exactly 10 and no prices, and one
    with too few bets before the date but 100 after it, with prices."""
    return [
        pathed_wallet("copied", (100, 70), (100, 70), "drift"),
        pathed_wallet("few-later", (100, 70), (4, 3), "jump"),
        planted_wallet("stopped", (100, 70), (0, 0)),
        planted_wallet("quiet", (100, 50), (9, 5)),
        planted_wallet("ten-later", (100, 50), (10, 5)),
        pathed_wallet("thin-before", (20, 10), (100, 50), "drift"),
    ]


PRICED = ("copied", "few-later", "stopped", "ten-later", "thin-before")
REQUESTS = 100 + 4 + 10 + 100  # one token per later bet of the priced Wallets, each its own window


class Recorder:
    """A client that passes every call on, notes its name, and can stand in for Polymarket not answering a price
    request: with `fail_from` set, price request number `fail_from` (from 0) and every later one raise."""

    def __init__(self, client: Any, *, fail_from: int | None = None) -> None:
        self._client = client
        self.calls: list[str] = []
        self.tokens: list[str] = []  # the token of every price request that was answered
        self.fail_from = fail_from

    def __getattr__(self, name: str) -> Any:
        target = getattr(self._client, name)
        if not callable(target):
            return target

        def call(*args: Any, **kwargs: Any) -> Any:
            self.calls.append(name)
            if name == "price_history":
                if self.fail_from is not None and len(self.tokens) >= self.fail_from:
                    raise PolymarketUnavailable("fake: Polymarket does not answer")
                self.tokens.append(args[0])
            return target(*args, **kwargs)

        return call


class Planted:
    """An offline Scan over planted Wallets: the store, the job queue and a recording client."""

    def __init__(self, root: Path, wallets: Sequence[SampleWallet], *, seed: int = SEED,
                 fail_from: int | None = None) -> None:
        self.root = root
        self.size = len(wallets)
        self.seed = seed
        self.client = Recorder(planted_client(root, wallets), fail_from=fail_from)
        self.path = root / "scan.db"
        self.store = Store(self.path)
        self.jobs = Jobs(self.store)
        self.worker = Worker(self.client, self.jobs)

    def scan(self) -> tuple[int, int]:
        """Start a Scan and let the worker run it once; returns (scan id, job id)."""
        started = self.jobs.start_scan(DAY, self.size, seed=self.seed)
        assert started is not None and self.worker.run_once()
        return started

    def forget_the_copy_test(self, scan_id: int, *, prices_too: bool = True) -> None:
        """Make the finished Scan what one from before Story 6.2 is: no Copy rows, not marked, and (unless told
        otherwise) no stored prices. The test's own write."""
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM copy_result WHERE scan_id = ?", (scan_id,))
            db.execute("DELETE FROM copy_sample WHERE scan_id = ?", (scan_id,))
            db.execute("UPDATE scan SET copied_at = NULL WHERE scan_id = ?", (scan_id,))
            if prices_too:
                db.execute("DELETE FROM price_point")
                db.execute("DELETE FROM price_window")
        db.close()
        self.client.calls.clear()
        self.client.tokens.clear()

    def other_results(self, scan_id: int) -> tuple[Any, ...]:
        """Everything of the Scan that a Copy Test must not change."""
        return (
            self.store.scan_results(scan_id), self.store.group_results(scan_id), self.store.scan_wallets(scan_id),
            self.store.scan_markets(scan_id), self.store.scan(scan_id).step, self.store.scan(scan_id).as_of,
        )


@pytest.fixture
def planted(tmp_path: Path) -> Iterator[Planted]:
    made = Planted(tmp_path, copy_cast())
    yield made
    made.store.close()


@pytest.fixture(scope="module")
def whole_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[tuple[CopyResult, ...], tuple[Any, ...]]:
    """The cast's Scan run in one go: its Copy results and its other results, for comparing interrupted runs with."""
    made = Planted(tmp_path_factory.mktemp("whole"), copy_cast())
    try:
        scan_id, _ = made.scan()
        return made.store.copy_results(scan_id), made.other_results(scan_id)[:2]
    finally:
        made.store.close()


def by_name(results: Sequence[CopyResult]) -> dict[str, CopyResult]:
    cast = ("copied", "few-later", "stopped", "quiet", "ten-later", "thin-before", "big", "twin")
    names = {address(name): name for name in cast}
    return {names[result.wallet]: result for result in results}


def test_fr18a_a_new_scan_finishes_with_its_copy_results(planted: Planted) -> None:
    """FR-18a, AD-5 (matrix "A new Scan", "Who is priced"): a Scan run by the worker ends with the Copy phase and
    is finished with its Copy results stored: every Passer (the one with 4 later bets and the one with none too)
    and every other Wallet with at least 10 later bets, and not the one with 9. The numbers are the follower's:
    a drifting price still leaves a profit at 30 minutes, a price that jumped leaves none."""
    scan_id, job_id = planted.scan()
    scan, job = planted.store.scan(scan_id), planted.store.job(job_id)
    assert scan.step is ScanStep.DONE and scan.copied and scan.copied_at >= scan.as_of
    assert (job.kind, job.status, job.phase) == (SCAN, JobStatus.DONE, "copy")
    passers = {r.wallet for r in planted.store.scan_results(scan_id)
               if r.scope == SCAN_BEFORE and r.verdict == Verdict.SKILLED.value}
    assert passers == {address("copied"), address("few-later"), address("stopped")}
    stored = planted.store.copy_results(scan_id)
    assert [r.wallet for r in stored] == sorted(address(name) for name in PRICED)  # address order; "quiet" has no row
    results = by_name(stored)
    assert {name: (r.after_positions, r.sampled) for name, r in results.items()} == {
        "copied": (100, 100), "few-later": (4, 4), "stopped": (0, 0), "ten-later": (10, 10), "thin-before": (100, 100),
    }
    copied = results["copied"]
    assert [(r.delay, r.priced, r.left_out) for r in copied.delays] == [(60, 100, 0), (300, 100, 0), (1800, 100, 0)]
    # 70 winners and 30 losers of 100 shares at 0.50, the price a 240th of the way to the outcome per minute.
    assert copied.at(FIVE).follower_pnl == pytest.approx(7000 - 100 * (70 * 0.515417 + 30 * 0.494583), abs=0.01)
    assert copied.at(THIRTY).follower_pnl == pytest.approx(1700.0, abs=0.01) and copied.at(THIRTY).own_pnl == 2000.0
    assert copied.at(THIRTY).follower_return == pytest.approx(1700 / 5300, abs=1e-6)
    few = results["few-later"].at(FIVE)  # three winners bought at 1.00, one loser at half a cent
    assert (few.priced, few.follower_pnl, few.spent) == (4, pytest.approx(-0.5), pytest.approx(300.5))
    for r in results["ten-later"].delays:  # no stored prices: every Position left out, nothing spent
        assert (r.priced, r.left_out, r.follower_pnl, r.spent, r.follower_return) == (0, 10, 0.0, 0.0, None)
    assert all((r.priced, r.left_out) == (0, 0) for r in results["stopped"].delays)
    assert not any(r.not_fully_read for r in stored)


def test_fr18a_only_the_priced_wallets_sampled_buys_are_asked_for(planted: Planted) -> None:
    """FR-18a, AD-5: one price request per window of the priced Wallets' sampled buys, and none for the Wallet
    with 9 later bets or for anything bought before the Cut-off Date."""
    planted.scan()
    assert len(planted.client.tokens) == len(set(planted.client.tokens)) == REQUESTS
    cast = {sample.name: sample for sample in copy_cast()}
    quiet = {row.token_id for row in cast["quiet"].activity}
    before = {row.token_id for sample in cast.values() for row in sample.activity if row.timestamp < synthetic.CUTOFF}
    assert not set(planted.client.tokens) & (quiet | before)


def test_fr18a_250_after_positions_are_priced_100_of_250_under_the_scans_seed(tmp_path: Path) -> None:
    """FR-18a, AD-15 (matrix "Large after part"): a Wallet with 250 tested after Positions is priced on 100 of them,
    only those 100 are asked for, and a Scan with another Seed draws another 100."""
    asked = []
    for seed in (SEED, 7):
        made = Planted(tmp_path / str(seed), [planted_wallet("big", (100, 70), (250, 175))], seed=seed)
        try:
            scan_id, _ = made.scan()
            (result,) = made.store.copy_results(scan_id)
            assert (result.after_positions, result.sampled) == (250, 100)
            assert all(r.priced + r.left_out == 100 for r in result.delays)
            assert len(set(made.client.tokens)) == 100
            asked.append(set(made.client.tokens))
        finally:
            made.store.close()
    assert asked[0] != asked[1]


def twin_of(sample: SampleWallet, name: str, hours: int) -> SampleWallet:
    """Another Wallet that bought the same outcome tokens after the Cut-off Date, `hours` later than `sample` did,
    with the same price path around its own buys."""
    shift = hours * 3600
    late = {row.token_id for row in sample.activity if row.timestamp >= synthetic.CUTOFF}
    activity = tuple(
        replace(row, timestamp=row.timestamp + shift) if row.token_id in late else row for row in sample.activity
    )
    positions = tuple(
        replace(p, first_entry_at=p.first_entry_at + shift) if p.token_id in late else p for p in sample.positions
    )
    prices = tuple(replace(point, t=point.t + shift) for point in sample.prices)
    return replace(sample, address=address(name), name=name, activity=activity, positions=positions, prices=prices)


def test_fr18a_two_wallets_that_bought_the_same_token_are_both_priced(tmp_path: Path) -> None:
    """FR-18a, AD-14 (Story 6.2 review): Wallets of one Scan often hold the same outcome token. Each token's price
    windows are planned from every priced Wallet's buys together, so two Wallets that bought the same 100 tokens
    six hours apart are both priced on all of them at every delay, with one request per token."""
    first = pathed_wallet("copied", (100, 70), (100, 70), "drift")
    made = Planted(tmp_path, [first, twin_of(first, "twin", 6)])
    try:
        scan_id, _ = made.scan()
        one, two = by_name(made.store.copy_results(scan_id)).values()
        for result in (one, two):
            assert [(r.priced, r.left_out) for r in result.delays] == [(100, 0)] * 3
        assert [(r.follower_pnl, r.spent) for r in one.delays] == pytest.approx([(r.follower_pnl, r.spent) for r in two.delays])
        assert len(made.client.tokens) == len(set(made.client.tokens)) == 100
        windows = sqlite3.connect(made.path).execute("SELECT COUNT(*), COUNT(DISTINCT token_id) FROM price_window").fetchone()
        assert windows == (200, 100)  # two windows a token, asked together
    finally:
        made.store.close()


def record_progress(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int, int, str]]:
    seen: list[tuple[str, int, int, str]] = []
    original = Store.update_progress

    def record(self: Store, job_id: int, *, phase: str, done: int, total: int, message: str) -> None:
        seen.append((phase, done, total, message))
        original(self, job_id, phase=phase, done=done, total=total, message=message)

    monkeypatch.setattr(Store, "update_progress", record)
    return seen


def test_ad5_an_outage_in_the_copy_phase_stops_the_scan_and_resume_asks_nothing_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, whole_run: tuple[tuple[CopyResult, ...], tuple[Any, ...]]
) -> None:
    """AD-5, AD-4, AD-19 (matrix "Polymarket stops answering in the Copy phase"): Polymarket not answering on
    price request 51 stops the job at "Copy Test: 50 of 214 prices". The Scan is not finished: no Copy rows, no
    Hold-up rows, no Watchlist. Resume goes on at 50 of 214, asks only for the windows not yet stored, and the
    results equal an uninterrupted run's."""
    seen = record_progress(monkeypatch)
    made = Planted(tmp_path, copy_cast(), fail_from=50)
    try:
        scan_id, job_id = made.scan()
        job = made.store.job(job_id)
        assert (job.status, job.phase, job.done, job.total) == (JobStatus.STOPPED, "copy", 50, REQUESTS)
        assert job.message == FINISHED[JobStatus.STOPPED] and seen[-1] == ("copy", 50, REQUESTS, "Copy Test: 50 of 214 prices")
        scan = made.store.scan(scan_id)
        assert scan.step is ScanStep.RANKED and not scan.copied
        assert made.store.copy_results(scan_id) == () and made.store.group_results(scan_id) == ()
        assert made.jobs.start_copy_test(scan_id) is None  # an unfinished Scan resumes; it gets no Copy Test job
        first = list(made.client.tokens)
        assert len(first) == 50

        made.client.fail_from = None
        wallet_reads = made.client.calls.count("positions_list")
        seen.clear()
        assert made.jobs.resume_scan(scan_id) is not None and made.worker.run_once()
        assert made.store.scan(scan_id).step is ScanStep.DONE and made.store.scan(scan_id).copied
        assert made.client.calls.count("positions_list") == wallet_reads  # no Wallet is read again
        assert len(made.client.tokens) == len(set(made.client.tokens)) == REQUESTS  # the first 50 are not asked again
        copy_steps = [step for step in seen if step[0] == "copy"]
        assert copy_steps[1] == ("copy", 50, REQUESTS, "Copy Test: 50 of 214 prices")
        assert copy_steps[-1] == ("copy", REQUESTS, REQUESTS, "Copy Test: 214 of 214 prices")
        assert (made.store.copy_results(scan_id), made.other_results(scan_id)[:2]) == whole_run
    finally:
        made.store.close()


def test_ad5_a_waiting_lookup_can_run_between_any_two_units_of_the_copy_phase(planted: Planted) -> None:
    """AD-5: the Copy phase calls `between` once after each Wallet's after part is read and once after each price
    request, so a queued lookup never waits for the whole phase."""
    scan_id, _ = planted.scan()
    planted.forget_the_copy_test(scan_id)
    calls: list[int] = []
    results = scan_module.copy_scan(planted.client, planted.store, scan_id, lambda *a: None, lambda: calls.append(1))
    assert len(calls) == 6 + REQUESTS  # the six tested Wallets (the quiet one is read, then not priced), then the requests
    assert len(results) == len(PRICED)


def test_ad19_the_copy_sample_is_cut_to_the_scans_as_of_time(planted: Planted) -> None:
    """AD-19: Positions in Markets resolved at or after the Scan's as-of time are not in the Copy Sample, so a Copy
    Test run days after the Scan prices what the Scan itself would have."""
    scan_id, _ = planted.scan()
    cut_at = synthetic.CUTOFF + 2 * synthetic.DAY + 50 * synthetic.DAY  # the 51st later bet resolves here
    with sqlite3.connect(planted.path) as db:
        db.execute("UPDATE scan SET as_of = ? WHERE scan_id = ?", (cut_at, scan_id))
    db.close()
    planted.forget_the_copy_test(scan_id)
    wallets = {w.wallet: w for w in scan_module.copy_wallets(planted.store, scan_id)}
    assert (wallets[address("copied")].after_positions, len(wallets[address("copied")].sample)) == (50, 50)
    assert all(m.closed_time < cut_at for m in wallets[address("copied")].markets.values())


def test_fr18a_a_passer_whose_after_part_was_refused_is_still_listed_and_flagged(planted: Planted) -> None:
    """FR-18a, AD-9: a Passer whose after part Polymarket refused has no frozen after snapshot. It still gets its
    row, "priced 0 of 0", flagged "not fully read", so every Before-Cut-off Passer is shown; another Wallet with no
    after part gets none. Neither costs a price request."""
    scan_id, _ = planted.scan()
    with sqlite3.connect(planted.path) as db:  # what `_test_top` stores for a refused after part
        for name in ("copied", "thin-before"):
            db.execute("UPDATE scan_wallet SET after_fetch_id = NULL WHERE scan_id = ? AND wallet = ?", (scan_id, address(name)))
            db.execute("UPDATE scan_result SET not_fully_read = 1 WHERE scan_id = ? AND wallet = ? AND scope = 'scan_whole'",
                       (scan_id, address(name)))
    db.close()
    planted.forget_the_copy_test(scan_id)
    assert planted.jobs.start_copy_test(scan_id) is not None and planted.worker.run_once()
    results = by_name(planted.store.copy_results(scan_id))
    assert sorted(results) == ["copied", "few-later", "stopped", "ten-later"]
    refused = results["copied"]
    assert (refused.after_positions, refused.sampled, refused.not_fully_read) == (0, 0, True)
    assert all((r.priced, r.left_out, r.follower_return) == (0, 0, None) for r in refused.delays)
    assert not results["few-later"].not_fully_read
    assert len(planted.client.tokens) == 4 + 10


def test_fr18a_a_wallet_not_fully_read_keeps_its_flag_in_the_copy_test(tmp_path: Path) -> None:
    """FR-18a, FR-16, AD-9: a Wallet whose trades after the Cut-off Date could be read only in part is priced on
    the bets that were read and carries its "not fully read" flag into its Copy result; the others do not."""
    cast = copy_cast()
    cast[0] = replace(cast[0], activity_until=synthetic.CUTOFF + 60 * synthetic.DAY)
    made = Planted(tmp_path, cast)
    try:
        scan_id, _ = made.scan()
        results = by_name(made.store.copy_results(scan_id))
        partly = results.pop("copied")
        assert partly.not_fully_read and 10 <= partly.after_positions == partly.sampled < 100
        assert partly.at(FIVE).priced == partly.sampled
        assert not any(r.not_fully_read for r in results.values())
    finally:
        made.store.close()


# --- a finished Scan gets its Copy Test afterwards (Edvard, 2026-11-28) -----------------------------------


def test_ad5_a_finished_scan_without_a_copy_test_gets_one_from_its_own_job(
    planted: Planted, whole_run: tuple[tuple[CopyResult, ...], tuple[Any, ...]]
) -> None:
    """AD-5, AD-19 (Edvard, 2026-11-28; matrix "Finished Scan with no Copy Test"): a Copy Test job for a Scan that
    finished without one runs only the Copy phase. The client is asked for prices and nothing else: no Wallet,
    Market or holder list. The Scan's Watchlist and Hold-up results, frozen snapshots and as-of time are unchanged,
    its Copy results equal a new Scan's, and it is then marked as having a Copy Test."""
    scan_id, _ = planted.scan()
    planted.forget_the_copy_test(scan_id)
    assert not planted.store.scan(scan_id).copied and planted.store.copy_results(scan_id) == ()
    before = planted.other_results(scan_id)
    snapshots = sqlite3.connect(planted.path).execute("SELECT COUNT(*), MAX(fetch_id) FROM snapshot").fetchone()

    job_id = planted.jobs.start_copy_test(scan_id)
    assert job_id is not None and planted.store.job(job_id).kind == COPY_TEST
    assert planted.store.job(job_id).status is JobStatus.QUEUED and planted.store.scan(scan_id).job.id == job_id
    assert planted.worker.run_once()
    job = planted.store.job(job_id)
    assert (job.status, job.phase, job.done, job.total, job.scan_id) == (JobStatus.DONE, "copy", REQUESTS, REQUESTS, scan_id)
    assert set(planted.client.calls) == {"price_history"} and len(planted.client.tokens) == REQUESTS
    assert planted.other_results(scan_id) == before
    assert sqlite3.connect(planted.path).execute("SELECT COUNT(*), MAX(fetch_id) FROM snapshot").fetchone() == snapshots
    assert planted.store.scan(scan_id).copied
    assert (planted.store.copy_results(scan_id), before[:2]) == whole_run
    assert planted.jobs.start_copy_test(scan_id) is None  # it has one now


def test_ad5_a_stopped_copy_test_job_is_followed_by_one_that_goes_on(
    planted: Planted, whole_run: tuple[tuple[CopyResult, ...], tuple[Any, ...]]
) -> None:
    """AD-5, AD-4 (matrix "That job stops"): an outage part-way stops the Copy Test job; the Scan stays finished,
    with its other results and no Copy Test. It has no Resume (it is finished); a new Copy Test job goes on from
    the stored prices and asks for no stored window again."""
    scan_id, _ = planted.scan()
    planted.forget_the_copy_test(scan_id)
    before = planted.other_results(scan_id)
    planted.client.fail_from = 30
    first = planted.jobs.start_copy_test(scan_id)
    assert planted.worker.run_once()
    job = planted.store.job(first)
    assert (job.kind, job.status, job.done, job.total) == (COPY_TEST, JobStatus.STOPPED, 30, REQUESTS)
    scan = planted.store.scan(scan_id)
    assert scan.step is ScanStep.DONE and not scan.copied and planted.store.copy_results(scan_id) == ()
    assert planted.other_results(scan_id) == before
    assert planted.jobs.resume_scan(scan_id) is None
    # What the Scans page shows for it today (its own state is settled with the button, Story 6.4): nothing runs,
    # the Scan is still Finished, and Start Scan is free again.
    view = ScansPage(planted.store, jobs=planted.jobs, seed=SEED, rate=5.0).view()
    assert view.running is None and not view.form.blocked
    assert (view.rows[0].status, view.rows[0].resume_label) == ("Finished", None)

    planted.client.fail_from = None
    second = planted.jobs.start_copy_test(scan_id)
    assert second not in (None, first) and planted.worker.run_once()
    assert planted.store.job(second).status is JobStatus.DONE and planted.store.scan(scan_id).copied
    assert len(planted.client.tokens) == len(set(planted.client.tokens)) == REQUESTS
    assert (planted.store.copy_results(scan_id), planted.other_results(scan_id)[:2]) == whole_run


def test_ad5_a_copy_test_job_the_app_was_closed_on_can_be_started_again(planted: Planted) -> None:
    """AD-5: a Copy Test job left running when the app closed becomes `interrupted`; the Scan has no Copy Test yet
    and a new job may start."""
    scan_id, _ = planted.scan()
    planted.forget_the_copy_test(scan_id, prices_too=False)
    first = planted.jobs.start_copy_test(scan_id)
    assert planted.store.claim_next_job().id == first and planted.store.interrupt_running_jobs() == 1
    assert planted.store.job(first).status is JobStatus.INTERRUPTED and not planted.store.scan(scan_id).copied
    assert planted.jobs.start_copy_test(scan_id) is not None and planted.worker.run_once()
    assert planted.store.scan(scan_id).copied and planted.client.tokens == []  # every window was already stored


def test_ad5_a_copy_test_job_that_may_not_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-5 (matrix "A Copy Test job that may not start"): nothing is queued for an unknown Scan, an unfinished
    one, one whose data was rebuilt or one that already has a Copy Test, nor while a Scan or a Copy Test job is
    queued or running; and no Scan starts while a Copy Test job is open. Run directly, the phase refuses such a
    Scan before it reads a snapshot or asks for a price."""
    def never(*args: object, **kwargs: object) -> object:
        raise AssertionError("the Copy phase ran for a Scan that may not have one")

    monkeypatch.setattr(scan_module, "copy_scan", never)
    path = tmp_path / "live.db"
    Store(path).close()
    ok, unfinished, rebuilt, has_one = (
        hand_scan(path, [Row("0x" + "1" * 40)], step=step) for step in ("done", "ranked", "done", "done")
    )
    with sqlite3.connect(path) as raw:
        raw.execute("UPDATE scan SET data_rebuilt = 1 WHERE scan_id = ?", (rebuilt,))
        raw.execute("UPDATE scan SET copied_at = 1 WHERE scan_id = ?", (has_one,))
    raw.close()
    db = Store(path)
    try:
        jobs = Jobs(db)
        for refused in (ok + 99, unfinished, rebuilt, has_one):
            assert jobs.start_copy_test(refused) is None
            with pytest.raises(ValueError, match="no Scan|not a finished Scan without a Copy Test"):
                scan_module.run_copy_test(None, db, refused, job_id=1)
            with pytest.raises(ValueError, match="no Scan|not a finished Scan without a Copy Test"):
                db.save_copy_test(refused, [])
        assert db._connection().execute("SELECT COUNT(*) FROM job").fetchone() == (0,)

        first = jobs.start_copy_test(ok)
        assert first is not None
        assert jobs.start_copy_test(ok) is None  # a second click while the first is queued
        assert jobs.start_scan(DAY, 10, seed=SEED) is None  # one Scan or Copy Test job at a time
        assert db.claim_job(first) and jobs.start_copy_test(ok) is None  # and while it runs
        db.finish_job(first, JobStatus.FAILED, message="x")
        started = jobs.start_scan(DAY, 10, seed=SEED)
        assert started is not None and jobs.start_copy_test(ok) is None  # a Scan is queued
    finally:
        db.close()


def test_ad5_a_failing_copy_test_job_fails_without_touching_the_scan(
    planted: Planted, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-5: an unexpected error in a Copy Test job ends it `failed`, logged and never shown raw; the Scan keeps its
    results and has no Copy rows, so the job can be started again once the cause is gone."""
    scan_id, _ = planted.scan()
    planted.forget_the_copy_test(scan_id, prices_too=False)
    before = planted.other_results(scan_id)

    def broken(*args: object, **kwargs: object) -> object:
        raise RuntimeError("a bug")

    with monkeypatch.context() as patched:
        patched.setattr(scan_module.copytest, "copy_result", broken)
        job_id = planted.jobs.start_copy_test(scan_id)
        assert planted.worker.run_once()
    job = planted.store.job(job_id)
    assert (job.status, job.message) == (JobStatus.FAILED, FINISHED[JobStatus.FAILED])
    assert planted.other_results(scan_id) == before and not planted.store.scan(scan_id).copied
    assert planted.store.copy_results(scan_id) == () and planted.jobs.start_copy_test(scan_id) is not None


def test_ad5_a_bug_in_the_copy_phase_does_not_cost_a_new_scan_its_results(
    planted: Planted, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    whole_run: tuple[tuple[CopyResult, ...], tuple[Any, ...]],
) -> None:
    """AD-5 (Edvard, 2026-11-28, after the review; matrix "A bug in the Copy phase of a new Scan"): an unexpected
    error in the Copy phase is logged and the Scan finishes without a Copy Test, with the Watchlist and Hold-up
    results it had already worked out. The job is done, not failed. Once the cause is gone, a Copy Test job gives
    the Scan the same Copy results a clean run has."""
    def broken(*args: object, **kwargs: object) -> object:
        raise RuntimeError("a bug")

    with monkeypatch.context() as patched, caplog.at_level("ERROR", logger="liquidoracle.services.scan"):
        patched.setattr(scan_module.copytest, "copy_result", broken)
        scan_id, job_id = planted.scan()
    assert "finished without a Copy Test" in caplog.text and "a bug" in caplog.text
    scan = planted.store.scan(scan_id)
    assert planted.store.job(job_id).status is JobStatus.DONE
    assert scan.step is ScanStep.DONE and not scan.copied and planted.store.copy_results(scan_id) == ()
    assert planted.other_results(scan_id)[:2] == whole_run[1]  # every Skill Test and both Hold-up results
    assert planted.jobs.start_copy_test(scan_id) is not None and planted.worker.run_once()
    assert planted.store.scan(scan_id).copied and planted.store.copy_results(scan_id) == whole_run[0]


def test_ux_dr31_the_scans_page_while_a_copy_test_job_is_open(planted: Planted) -> None:
    """UX-DR31, UX-DR32 (Story 6.2; the button is Story 6.4): while a Copy Test job is queued or running, the Scans
    page shows it as the running work with the job's own step, the Scan's row still says Finished, and Start Scan
    is unavailable."""
    scan_id, _ = planted.scan()
    planted.forget_the_copy_test(scan_id)
    page = ScansPage(planted.store, jobs=planted.jobs, seed=SEED, rate=5.0)
    assert page.view().running is None
    job_id = planted.jobs.start_copy_test(scan_id)
    view = page.view()
    assert view.running is not None and (view.running.scan_id, view.running.job_id) == (scan_id, job_id)
    assert view.running.step == "Copy Test" and view.form.blocked
    assert view.rows[0].status == "Finished" and view.rows[0].resume_label is None
    assert planted.worker.run_once() and page.view().running is None


# --- what the store keeps (AD-22) ------------------------------------------------------------------------


def a_copy(n: int, *, unread: bool = False) -> CopyResult:
    return CopyResult(f"0x{n:040x}", 250, 100, unread, (
        FollowerResult(60, 100, 0, 12.5, 400.0, 20.0), FollowerResult(300, 98, 2, -3.25, 390.125, 19.0),
        FollowerResult(1800, 0, 100, 0.0, 0.0, 0.0),
    ))


def test_ad22_copy_results_are_stored_with_the_step_that_finishes_the_scan(tmp_path: Path) -> None:
    """AD-22, AD-5: a Scan finishes with its Copy results or not at all. They are read back by Wallet with their
    delays shortest first; a Scan in which no Wallet was priced is still marked as having a Copy Test; a Wallet
    twice, or a delay twice, is refused; and a failure after the step moved rolls everything back."""
    path = tmp_path / "live.db"
    Store(path).close()
    scan_id, empty, blocked = (hand_scan(path, [], step="ranked") for _ in range(3))
    db = Store(path)
    try:
        groups = [counts(3, 1), counts(4, 2, holdup.COMPARISON)]
        twice = replace(a_copy(1), delays=(FollowerResult(60, 1, 0, 0.0, 1.0, 0.0),) * 2)
        for wrong in ([a_copy(1), a_copy(1)], [twice]):
            with pytest.raises(ValueError, match="twice|two results"):
                db.finish_scan(scan_id, groups, wrong)
        assert db.scan(scan_id).step is ScanStep.RANKED and db.copy_results(scan_id) == () and not db.scan(scan_id).copied

        with db._write() as raw:  # a row that should not be there: the insert fails after the step has moved
            raw.execute(
                "INSERT INTO copy_sample (scan_id, wallet, cutoff, seed, after_positions, sampled, not_fully_read)"
                " VALUES (?, ?, 0, 0, 1, 1, 0)", (blocked, a_copy(2).wallet),
            )
        with pytest.raises(sqlite3.IntegrityError):
            db.finish_scan(blocked, groups, [a_copy(2)])
        assert db.scan(blocked).step is ScanStep.RANKED and db.group_results(blocked) == () and not db.scan(blocked).copied

        copies = [a_copy(2, unread=True), a_copy(1)]
        db.finish_scan(scan_id, groups, copies)
        assert db.scan(scan_id).step is ScanStep.DONE and db.scan(scan_id).copied_at == db.now()
        assert db.copy_results(scan_id) == (a_copy(1), a_copy(2, unread=True))
        assert db.copy_results(scan_id)[0].at(300).follower_return == pytest.approx(-3.25 / 390.125)
        seeds = db._connection().execute("SELECT DISTINCT cutoff, seed FROM copy_sample WHERE scan_id = ?", (scan_id,)).fetchall()
        assert seeds == [(db.scan(scan_id).cutoff, db.scan(scan_id).seed)]  # every result records its Seed (AD-15)

        db.finish_scan(empty, groups, [])
        assert db.scan(empty).copied and db.copy_results(empty) == ()
        assert [s.copied for s in db.scans()] == [False, True, True]  # newest first: blocked, empty, scan_id

        with db._write() as raw:
            raw.execute("DELETE FROM copy_sample WHERE scan_id = ?", (blocked,))
        db.finish_scan(blocked, groups, None)  # its Copy phase met an error: finished without a Copy Test
        assert db.scan(blocked).step is ScanStep.DONE and not db.scan(blocked).copied
        assert len(db.group_results(blocked)) == 2 and db.copy_results(blocked) == ()
    finally:
        db.close()


def test_ad22_a_finished_scans_copy_test_is_saved_once(tmp_path: Path) -> None:
    """AD-22 (Story 6.2): `save_copy_test` adds the Copy rows of a finished Scan and marks it, in one transaction,
    and refuses a second time; a failed save leaves the Scan without a Copy Test."""
    path = tmp_path / "live.db"
    Store(path).close()
    scan_id = hand_scan(path, [Row("0x" + "1" * 40)])
    db = Store(path)
    try:
        with pytest.raises(ValueError, match="twice"):
            db.save_copy_test(scan_id, [a_copy(1), a_copy(1)])
        assert not db.scan(scan_id).copied and db.copy_results(scan_id) == ()
        db.save_copy_test(scan_id, [a_copy(1)])
        assert db.scan(scan_id).copied and db.copy_results(scan_id) == (a_copy(1),)
        with pytest.raises(ValueError, match="not a finished Scan without a Copy Test"):
            db.save_copy_test(scan_id, [a_copy(2)])
        assert db.copy_results(scan_id) == (a_copy(1),)
    finally:
        db.close()


# --- the Sample Dataset copied offline (FR-13, FR-18a) ----------------------------------------------------


def test_fr18a_the_speed_trader_and_the_forecaster_copied_offline(
    offline_scan: tuple[Store, int, dict[str, holdup.Member]],
) -> None:
    """FR-18a, FR-13 (the two checks that are never cut): in an offline Scan of the committed Sample Wallets run by
    the worker, a follower of the speed trader has made nothing or lost at 5 minutes, at every delay in fact, and a
    follower of the forecaster is still in profit at 30 minutes, though less than at 1 minute. Both are priced
    on all 100 of their later bets."""
    db, scan_id, _ = offline_scan
    assert db.scan(scan_id).copied
    results = {r.wallet: r for r in db.copy_results(scan_id)}
    speed, forecaster = results[address("speed-trader")], results[address("forecaster")]
    assert all((r.priced, r.left_out) == (100, 0) for r in (*speed.delays, *forecaster.delays))
    assert speed.at(FIVE).follower_pnl <= 0 and speed.at(FIVE).follower_pnl == pytest.approx(-15.0)
    assert all(r.follower_pnl <= 0 and r.own_pnl == 2000.0 for r in speed.delays)
    assert forecaster.at(THIRTY).follower_pnl > 0 and forecaster.at(THIRTY).follower_pnl == pytest.approx(1700.0)
    assert forecaster.at(ONE).follower_pnl > forecaster.at(FIVE).follower_pnl > forecaster.at(THIRTY).follower_pnl
    assert forecaster.at(THIRTY).follower_pnl < forecaster.at(THIRTY).own_pnl  # arriving late costs something


def test_fr18a_the_offline_scans_priced_wallets_and_the_ones_with_no_prices_yet(
    offline_scan: tuple[Store, int, dict[str, holdup.Member]],
) -> None:
    """FR-18a, AD-14: in the offline Scan the priced Wallets are the Passers and every other Wallet with at least 10
    tested after bets. The steady sharp and the real Wallets have no stored prices (the real ones get theirs in
    Story 6.5), so all their sampled bets are counted as left out at every delay, never priced at a guess."""
    db, scan_id, members = offline_scan
    results = {r.wallet: r for r in db.copy_results(scan_id)}
    passers = {w for w, m in members.items() if holdup.group_of(m.verdict_before) == holdup.PASSERS}
    after = {r.wallet: r.after_positions for r in results.values()}
    assert passers <= set(results)
    assert all(count >= holdup.MIN_AFTER_BETS for wallet, count in after.items() if wallet not in passers)
    enough = {w for w, m in members.items() if m.after.tested_count >= holdup.MIN_AFTER_BETS}
    assert enough <= set(results)
    with_prices = {address("forecaster"), address("speed-trader")}
    for wallet, result in results.items():
        assert result.sampled == min(result.after_positions, copytest.SAMPLE_SIZE)
        if wallet not in with_prices:
            assert all((r.priced, r.left_out, r.spent) == (0, result.sampled, 0.0) for r in result.delays)
    assert results[address("steady-sharp")].sampled == 100
    real = [r for w, r in results.items() if r.after_positions > 100]
    assert len(real) == 1 and real[0].sampled == 100  # 0xd3a6e5: "priced 100 of 307"
