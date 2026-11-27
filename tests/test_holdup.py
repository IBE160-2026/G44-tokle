"""The Hold-up Test: the two groups, their pooled test, the stored result and the Scan's last phase (FR-17;
AD-5, AD-15, AD-19, AD-20, AD-22; Story 5.1).

The core tests plant Wallets as `holdup.Member`s. The Scan tests write made-up Wallets as Sample files and
run a real offline Scan over them with the worker, so the groups come from stored `scan_before` results and
frozen snapshots. The lucky-streak Wallets (FR-13) are built by the generator. No socket is opened (AD-17).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from test_watchlist import hand_scan

from liquidoracle.core import holdup, rng, skilltest
from liquidoracle.core.positions import build_positions
from liquidoracle.data import offline as offline_module
from liquidoracle.data import sample_json, synthetic
from liquidoracle.data.offline import OfflineClient, sample_files, sample_funnels
from liquidoracle.data.store import HOLDUP_AFTER, SCAN_BEFORE, SCAN_WHOLE, JobStatus, ScanStep, Store
from liquidoracle.data.window import cutoff_at
from liquidoracle.records import GroupResult, Position, PositionSet, SampleWallet, Verdict
from liquidoracle.services import holdup as holdup_page
from liquidoracle.services import scan as scan_module
from liquidoracle.services.jobs import Jobs, Worker

REPO = Path(__file__).resolve().parents[1]
SEED = 44  # the Settings default (AD-15), fixed here so the golden counts never follow a settings change
DAY = date(2025, 7, 1)
SKILLED, LIKELY, NO_EVIDENCE, NOT_ENOUGH = (
    Verdict.SKILLED, Verdict.LIKELY_SKILLED, Verdict.NO_EVIDENCE, Verdict.NOT_ENOUGH_DATA,
)

# The lucky-streak Wallets rated Skilled (high confidence) on their before part: found by running the Skill
# Test over all 1,000 (2026-11-27), not picked; the `slow` check below proves the list against the generator.
LUCKY_PASSERS = (201, 259, 543, 817, 861, 889, 985)

# AD-17 golden results: Simulations at or above the Real PnL, from this code's first run (2026-11-27). Any
# system that draws, pools or sums differently fails.
GOLDEN = {"steady-sharp": 0, "lucky-streaks": 6243, "shared-markets": 5751}

# The offline Scan's Comparison Group result (2026-11-27): the three real Sample Wallets with at least 10 bets after
# the Cut-off Date (0x0f4b0a 89, 0x736483 13, 0xd3a6e5 307). Story 5.2 writes these numbers into the README, so a
# change to the Sample Dataset or the builder that moves them must fail here. (bets, at or above, Real PnL)
REAL_COMPARISON = (409, 5573, -19216.76)
SMALL = {sample.name: sample for sample in synthetic.small_wallets()}

# The coin-flippers rated Skilled (high confidence) before the Cut-off Date by luck: found by running the Skill Test
# over all 1,000 (2026-11-27; the same six a full offline Scan stores as Passers), not picked. A `slow` check below
# proves the list against the generator.
LUCKY_COIN_FLIPPERS = (87, 236, 319, 730, 828, 880)
# The full offline Scan's group sizes, (Wallets, dropped), built from that list (Story 5.2 writes them into the
# README). Passers: the four made-up Wallets on the Watchlist and the lucky coin-flippers; sharp trader and the lucky
# ones are dropped. Comparison Group: the other coin-flippers and 5 real Wallets; those coin-flippers and 2 of the
# real Wallets are dropped.
BUILT_TO_HOLD_UP = ("steady-sharp", "forecaster", "speed-trader")  # the made-up Wallets that keep winning after the date
OFFLINE_PASSER_SIZES = (
    len(synthetic.WATCHLIST_NAMES) + len(LUCKY_COIN_FLIPPERS),
    len(synthetic.WATCHLIST_NAMES) - len(BUILT_TO_HOLD_UP) + len(LUCKY_COIN_FLIPPERS),
)
OFFLINE_COMPARISON_SIZES = (
    synthetic.COIN_FLIPPERS - len(LUCKY_COIN_FLIPPERS) + 5, synthetic.COIN_FLIPPERS - len(LUCKY_COIN_FLIPPERS) + 2,
)
BIGGEST_REAL = "0xd3a6e523c440f94f9259398fbcf7b5cc5ccffd55"  # 307 of the Comparison Group's 409 bets are its


# --- planted Wallets ------------------------------------------------------------------------------


def bet(market: int, price: float, won: bool, *, shares: float = 100.0, side: int = 0) -> Position:
    """A held Position in Market `m{market}`; `side` 0 or 1 picks the outcome token."""
    return Position(
        condition_id=f"m{market:05d}", token_id=f"m{market:05d}-{side}", outcome=1.0 if won else 0.0,
        entry_price=price, shares_bought=shares, shares_sold=0.0, shares_held=shares, own_fees=0.0, exit_pnl=0.0,
    )


def bets(count: int, *, first: int = 0, price: float = 0.5, won: int | None = None) -> PositionSet:
    """`count` held Positions in Markets `first`, `first` + 1, ...; the first `won` of them won (half by default)."""
    won = count // 2 if won is None else won
    return PositionSet(tuple(bet(first + i, price, i < won) for i in range(count)), (), ())


def wallet(n: int) -> str:
    return f"0x{n:040x}"


def member(n: int, verdict: Verdict, after: PositionSet, *, unread: bool = False) -> holdup.Member:
    return holdup.Member(wallet(n), verdict, after, unread)


def group(members: Sequence[holdup.Member], name: str = holdup.PASSERS) -> GroupResult:
    passers, comparison = holdup.hold_up(members, seed=SEED)
    return passers if name == holdup.PASSERS else comparison


def at_or_above(result: GroupResult) -> int:
    """The exact count behind a p-value: p = (1 + count) / 10,001 (FR-5)."""
    assert result.p_value is not None
    return round(result.p_value * (skilltest.SIMULATIONS + 1)) - 1


def part(sample: SampleWallet, *, after: bool) -> PositionSet:
    """A Synthetic Wallet's bets resolved before the default Cut-off Date, or the ones bought from it on."""
    markets = {m.condition_id: m for m in sample.markets if (m.closed_time >= synthetic.CUTOFF) == after}
    return build_positions(
        tuple(row for row in sample.activity if row.condition_id in markets), markets,
        listed=tuple(row for row in sample.positions if row.condition_id in markets),
    )


def as_member(sample: SampleWallet) -> holdup.Member:
    """The Wallet as the Hold-up Test sees it: its real Skill Test Verdict on the before part, and its after part."""
    before = skilltest.skill_test(part(sample, after=False), seed=SEED, unit_id=sample.address, scope=SCAN_BEFORE)
    return holdup.Member(sample.address, before.verdict, part(sample, after=True))


# --- the two groups (FR-17) -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [(SKILLED, holdup.PASSERS), (LIKELY, holdup.COMPARISON), (NO_EVIDENCE, holdup.COMPARISON), (NOT_ENOUGH, None)],
)
def test_fr17_the_before_verdict_alone_names_the_group(verdict: Verdict, expected: str | None) -> None:
    """FR-17: Skilled (high confidence) before = Passers; Likely skilled or No evidence = Comparison Group; Not
    enough data = neither."""
    assert holdup.group_of(verdict) == expected


def test_fr17_every_wallet_is_in_at_most_one_group() -> None:
    """FR-17: each Wallet is counted in exactly the group its before Verdict names, never both, and a Wallet with
    Not enough data before is in neither."""
    members = [
        member(1, SKILLED, bets(40)), member(2, SKILLED, bets(40, first=100)),
        member(3, LIKELY, bets(40, first=200)), member(4, NO_EVIDENCE, bets(40, first=300)),
        member(5, NO_EVIDENCE, bets(40, first=400)), member(6, NOT_ENOUGH, bets(40, first=500)),
    ]
    passers, comparison = holdup.hold_up(members, seed=SEED)
    assert (passers.group, passers.wallets, passers.tested_count) == (holdup.PASSERS, 2, 80)
    assert (comparison.group, comparison.wallets, comparison.tested_count) == (holdup.COMPARISON, 3, 120)
    with pytest.raises(ValueError, match="twice"):
        holdup.hold_up([member(1, SKILLED, bets(40)), member(1, NO_EVIDENCE, bets(40))], seed=SEED)


def test_fr17_after_outcomes_never_move_a_wallet_between_groups() -> None:
    """FR-17: the same Wallets with every after-part outcome turned around are in the same groups, with the same
    Wallet and dropped counts; only the tested result changes."""
    def planted(won: bool) -> list[holdup.Member]:
        return [
            member(1, SKILLED, PositionSet(tuple(bet(i, 0.5, won) for i in range(40)), (), ())),
            member(2, NO_EVIDENCE, PositionSet(tuple(bet(100 + i, 0.5, not won) for i in range(40)), (), ())),
            member(3, NO_EVIDENCE, bets(5, first=200)),
        ]

    lost, won = holdup.hold_up(planted(False), seed=SEED), holdup.hold_up(planted(True), seed=SEED)
    for a, b in zip(lost, won):
        assert (a.group, a.wallets, a.dropped) == (b.group, b.wallets, b.dropped)
    assert (lost[0].verdict, won[0].verdict) == (NO_EVIDENCE, SKILLED)
    assert (lost[1].verdict, won[1].verdict) == (SKILLED, NO_EVIDENCE)


# --- who counts, and what a group's result shows (FR-17) -------------------------------------------


def test_fr17_a_wallet_needs_10_after_bets_by_the_same_rule_in_both_groups() -> None:
    """FR-17, PRD Glossary (Minimum After-bets): 9 tested Positions after the cut-off drop a Wallet, 10 count it,
    and the rule is the same for a Passer and for the Comparison Group."""
    assert holdup.MIN_AFTER_BETS == 10
    for verdict, name in ((SKILLED, holdup.PASSERS), (NO_EVIDENCE, holdup.COMPARISON)):
        members = [
            member(1, verdict, bets(9)), member(2, verdict, bets(10, first=100)),
            member(3, verdict, bets(30, first=200)), member(4, verdict, PositionSet((), (), ())),
        ]
        result = group(members, name)
        assert (result.wallets, result.dropped, result.tested_count) == (4, 2, 40)


def test_fr17_slivers_count_in_the_money_but_not_toward_the_10() -> None:
    """FR-17, FR-4: a Wallet's Slivers are simulated and counted in the group's Real PnL, but only tested Positions
    count toward its 10 after bets and the group's Resolved Positions."""
    sliver = bet(900, 0.5, True, shares=1.0)
    with_sliver = PositionSet(bets(30).tested, (sliver,), ())
    nine = PositionSet(bets(9, first=100).tested, (bet(901, 0.5, True),), ())
    result = group([member(1, SKILLED, with_sliver), member(2, SKILLED, nine)])
    assert (result.wallets, result.dropped, result.tested_count) == (2, 1, 30)
    assert result.real_pnl == pytest.approx(group([member(1, SKILLED, bets(30))]).real_pnl + 0.5)


def test_fr17_a_group_shows_how_many_of_its_wallets_were_not_fully_read() -> None:
    """FR-17, FR-16: the count covers every Wallet in the group flagged "not fully read", dropped or not."""
    members = [
        member(1, SKILLED, bets(30), unread=True), member(2, SKILLED, bets(3, first=100), unread=True),
        member(3, SKILLED, bets(30, first=200)), member(4, NO_EVIDENCE, bets(30, first=300), unread=True),
    ]
    passers, comparison = holdup.hold_up(members, seed=SEED)
    assert (passers.not_fully_read, comparison.not_fully_read) == (2, 1)


def test_fr17_fewer_than_30_pooled_bets_give_not_enough_data() -> None:
    """FR-17: a group with 29 Resolved Positions after the cut-off shows Not enough data with its counts and Real
    PnL and no p-value; with 30 it gets a Verdict."""
    small = group([member(1, SKILLED, bets(19, won=19)), member(2, SKILLED, bets(10, first=100, won=10))])
    assert (small.verdict, small.p_value, small.tested_count, small.wallets, small.dropped) == (NOT_ENOUGH, None, 29, 2, 0)
    assert small.real_pnl == pytest.approx(29 * 50.0)
    enough = group([member(1, SKILLED, bets(20, won=20)), member(2, SKILLED, bets(10, first=100, won=10))])
    assert (enough.verdict, enough.tested_count) == (SKILLED, 30) and enough.p_value is not None


def test_fr17_no_passers_is_a_plain_result() -> None:
    """FR-17 (matrix "No Passers"): with no Wallet Skilled before, the Passers' result is 0 Wallets and Not enough
    data, the Comparison Group is still tested, and no flag is set."""
    passers, comparison = holdup.hold_up([member(1, NO_EVIDENCE, bets(40)), member(2, LIKELY, bets(3, first=100))], seed=SEED)
    assert passers == GroupResult(holdup.PASSERS, NOT_ENOUGH, None, 0, 0.0, 0, 0, 0)
    assert (comparison.wallets, comparison.dropped, comparison.verdict) == (2, 1, NO_EVIDENCE)
    assert not holdup.dropped_shares_differ(passers, comparison)
    nothing = holdup.hold_up([], seed=SEED)
    assert [r.wallets for r in nothing] == [0, 0] and not holdup.dropped_shares_differ(*nothing)


# --- the dropped-share flag (FR-17) ---------------------------------------------------------------


def counts(wallets: int, dropped: int, name: str = holdup.PASSERS) -> GroupResult:
    return GroupResult(name, NO_EVIDENCE, 0.5, 100, 0.0, wallets, dropped, 0)


@pytest.mark.parametrize(
    ("passers", "comparison", "flag"),
    [
        ((10, 6), (10, 1), True),  # the PRD's planted example: 60% against 10%
        ((10, 1), (10, 6), True),  # either group may be the one with more dropped
        ((10, 3), (10, 3), False),  # equal shares
        ((10, 0), (10, 0), False),
        ((10, 3), (10, 1), False),  # exactly 20 points is not "more than 20"
        ((10, 9), (10, 7), False),  # exactly 20 points where floats would say 20.000000000000007
        ((100, 41), (100, 20), True),  # 21 points
        ((10, 7), (999, 996), True),  # the full offline Scan, as measured: 70% against 99.7%
        ((0, 0), (10, 10), False),  # a group with no Wallets has no share
        ((10, 10), (0, 0), False),
    ],
)
def test_fr17_the_flag_is_set_above_a_20_point_gap(passers: tuple[int, int], comparison: tuple[int, int], flag: bool) -> None:
    """FR-17: the dropped shares differing by more than 20 percentage points sets the flag; equal shares, exactly 20
    points and an empty group do not."""
    assert holdup.DROPPED_GAP_POINTS == 20
    assert holdup.dropped_shares_differ(counts(*passers), counts(*comparison, holdup.COMPARISON)) is flag


def test_fr17_the_planted_60_and_10_percent_groups_set_the_flag() -> None:
    """FR-17 check: 10 Passers with 6 dropped and 10 Comparison Wallets with 1 dropped carry the flag; the same
    groups with 1 dropped each do not."""
    def planted(passers_dropped: int) -> tuple[GroupResult, GroupResult]:
        members = [member(i, SKILLED, bets(3 if i < passers_dropped else 30, first=100 * i)) for i in range(10)]
        members += [member(10 + i, NO_EVIDENCE, bets(3 if i < 1 else 30, first=100 * (10 + i))) for i in range(10)]
        return holdup.hold_up(members, seed=SEED)

    uneven, even = planted(6), planted(1)
    assert [(r.wallets, r.dropped) for r in uneven] == [(10, 6), (10, 1)]
    assert holdup.dropped_shares_differ(*uneven) and not holdup.dropped_shares_differ(*even)


# --- the pooled test: one draw per Market for the whole group (AD-20, AD-15) -------------------------


def shared_market_run(run: int, *, passers: int = 7, markets: int = 40, shared: bool = True) -> list[holdup.Member]:
    """FR-17's planted run: coin-flipper Passers holding the same side of the same Markets, prices of 10 to 90
    cents, outcomes drawn at the price. With `shared` False each Passer's copy sits in its own Market instead."""
    name = f"shared-markets-{run}"
    drawn = []
    for i in range(markets):
        price = (10 + int(synthetic.uniform(name, i, "price") * 81)) / 100
        drawn.append((price, synthetic.uniform(name, i, "outcome") < price))
    return [
        member(n, SKILLED, PositionSet(
            tuple(bet(i if shared else 1000 * (n + 1) + i, price, won) for i, (price, won) in enumerate(drawn)), (), ()
        ))
        for n in range(passers)
    ]


def test_ad20_passers_in_the_same_markets_win_and_lose_together() -> None:
    """AD-20, FR-17 (matrix "Shared Market"): two Passers holding the same token share its draw in every
    Simulation, so their pooled result is exactly that of one Wallet holding both stakes."""
    one = shared_market_run(0, passers=1)[0]
    doubled = PositionSet(tuple(replace(p, shares_bought=200.0, shares_held=200.0) for p in one.after.tested), (), ())
    together = group(shared_market_run(0, passers=2))
    as_one = group([member(1, SKILLED, doubled)])
    assert (together.tested_count, as_one.tested_count) == (80, 40)
    assert together.p_value == as_one.p_value and together.real_pnl == pytest.approx(as_one.real_pnl)
    apart = group(shared_market_run(0, passers=2, shared=False))
    assert apart.real_pnl == pytest.approx(together.real_pnl) and apart.p_value != together.p_value


def test_ad20_both_sides_of_a_market_held_by_two_wallets_cannot_both_win() -> None:
    """AD-20: one Wallet on each side of the same 40 Markets at 0.50, one side won each: in every Simulation exactly
    one side wins, so every total equals the real one and p is 1."""
    low = member(1, SKILLED, PositionSet(tuple(bet(i, 0.5, i % 2 == 0, side=0) for i in range(40)), (), ()))
    high = member(2, SKILLED, PositionSet(tuple(bet(i, 0.5, i % 2 == 1, side=1) for i in range(40)), (), ()))
    result = group([low, high])
    assert (result.tested_count, result.real_pnl, result.p_value) == (80, 0.0, 1.0)


def test_ad15_the_order_of_the_wallets_does_not_change_a_result() -> None:
    """AD-15: a group's result does not depend on the order its Wallets came in, also when two of them hold the
    same token at different prices and stakes; another Seed gives another result."""
    members = shared_market_run(1) + [member(20 + i, NO_EVIDENCE, bets(25, first=5000 + 100 * i, won=9 + i)) for i in range(4)]
    members.append(member(30, SKILLED, PositionSet(tuple(bet(i, 0.31 + i / 100, i % 3 == 0, shares=37.0) for i in range(40)), (), ())))
    members.append(member(31, SKILLED, PositionSet(tuple(bet(i, 0.62, i % 3 == 0, shares=5.5, side=1) for i in range(40)), (), ())))
    usual = holdup.hold_up(members, seed=SEED)
    assert usual == holdup.hold_up(members[::-1], seed=SEED) == holdup.hold_up(members[5:] + members[:5], seed=SEED)
    assert usual != holdup.hold_up(members, seed=SEED + 1)


def test_ad15_the_holdup_test_has_its_own_random_purpose() -> None:
    """AD-15: purpose codes never change; the Hold-up Test draws under `holdup` with the group's name as its id, so
    a group's result is not the Skill Test of a Wallet that happens to hold the same bets."""
    assert (rng.PURPOSES["skilltest"], rng.PURPOSES[holdup.PURPOSE]) == (1, 2)
    assert rng.spawn_key(holdup.PURPOSE, holdup.PASSERS)[0] == 2
    assert rng.spawn_key(holdup.PURPOSE, holdup.PASSERS) != rng.spawn_key(holdup.PURPOSE, holdup.COMPARISON)
    members = [member(1, SKILLED, bets(60, won=33))]
    as_wallet = skilltest.skill_test(members[0].after, seed=SEED, unit_id=holdup.PASSERS)
    assert group(members).p_value != as_wallet.p_value
    comparison = group([member(1, NO_EVIDENCE, bets(60, won=33))], holdup.COMPARISON)
    assert comparison.p_value != group(members).p_value  # each group is its own random unit


def test_ad15_an_unknown_purpose_is_refused_whatever_the_number_of_bets() -> None:
    """AD-15 (review, Story 5.1): a purpose the generator does not know is refused for 29 bets as for 30, so a
    misspelt one can never pass as Not enough data."""
    for count in (0, 29, 30):
        with pytest.raises(ValueError, match="unknown random purpose"):
            skilltest.skill_test(bets(count), seed=SEED, unit_id="x", purpose="hold-up")


def linked(market: int, price: float, won: bool, *, event: str) -> Position:
    """A held Yes Position in Market `n{market}` of the negative-risk event `event` (one of its Markets can win)."""
    return replace(
        bet(market, price, won), condition_id=f"n{market:05d}", token_id=f"n{market:05d}-yes",
        event_id=f"ev-{event}", neg_risk_id=event, yes_side=True,
    )


def pooled_wins(members: Sequence[holdup.Member]) -> dict[str, list[bool]]:
    """Who wins in each Simulation, by token, for these Wallets' pooled bets (drawn as the engine draws)."""
    pooled = [p for m in sorted(members, key=lambda m: m.wallet) for p in m.after.tested]
    ordered, won = skilltest._simulated_wins(pooled, seed=SEED, unit_id=holdup.PASSERS, simulations=skilltest.SIMULATIONS)
    return {p.token_id: [bool(x) for x in won[:, i]] for i, p in enumerate(ordered)}


def share(wins: list[bool]) -> float:
    return sum(wins) / len(wins)


def test_ad20_two_wallets_in_one_negative_risk_event_cannot_both_win() -> None:
    """AD-20, FR-17 (review, Story 5.1): one Wallet holds Yes in one Market of a negative-risk event at 0.30 and
    another Wallet holds Yes in a second Market of it at 0.40. Pooled, at most one of them wins in any Simulation,
    each still at its own price; alone in separate tests they would be drawn apart."""
    first = member(1, SKILLED, PositionSet(tuple(linked(2 * e, 0.30, e % 3 == 0, event=f"e{e}") for e in range(30)), (), ()))
    second = member(2, SKILLED, PositionSet(tuple(linked(2 * e + 1, 0.40, e % 3 == 1, event=f"e{e}") for e in range(30)), (), ()))
    wins = pooled_wins([first, second])
    for e in range(3):
        a, b = wins[f"n{2 * e:05d}-yes"], wins[f"n{2 * e + 1:05d}-yes"]
        assert not any(x and y for x, y in zip(a, b))
        assert abs(share(a) - 0.30) < 0.02 and abs(share(b) - 0.40) < 0.02
    result = group([first, second])
    assert (result.tested_count, result.wallets) == (60, 2) and result.p_value is not None


def test_ad20_two_wallets_on_opposite_sides_keep_their_own_win_chance() -> None:
    """AD-20 (review, Story 5.1): Wallets on opposite sides of one Market share its draw. With prices summing to at
    most 1 they never both win; above that the coupling is as tight as the prices allow: at 0.70 and 0.70 both win
    in about 40% of the Simulations, and at 0.30 and 0.30 neither does in about 40%. Each side keeps its own price
    as its win chance (FR-5), which is the known limit of pooling Wallets that bought at different prices."""
    for price, both, neither in ((0.50, 0.0, 0.0), (0.70, 0.40, 0.0), (0.30, 0.0, 0.40)):
        low = member(1, SKILLED, PositionSet((bet(1, price, True, side=0),), (), ()))
        high = member(2, SKILLED, PositionSet((bet(1, price, False, side=1),), (), ()))
        wins = pooled_wins([low, high])
        a, b = wins["m00001-0"], wins["m00001-1"]
        assert abs(share(a) - price) < 0.02 and abs(share(b) - price) < 0.02
        assert abs(share([x and y for x, y in zip(a, b)]) - both) < 0.02
        assert abs(share([not x and not y for x, y in zip(a, b)]) - neither) < 0.02


def test_ad20_a_market_with_three_outcomes_in_one_pool_is_refused() -> None:
    """AD-20 (matrix "Bad pool"): three Passers on three different tokens of one Market cannot be coupled; the
    Skill Test's check refuses the pool."""
    members = [
        member(n, SKILLED, PositionSet((*bets(30, first=100 * n).tested, bet(9999, 0.3, n == 1, side=n)), (), ()))
        for n in (1, 2, 3)
    ]
    with pytest.raises(ValueError, match="outcomes in one test"):
        holdup.hold_up(members, seed=SEED)


@pytest.mark.parametrize(("positions", "rows"), [(1, 1000), (2000, 1000), (2001, 999), (100_000, 20), (5_000_000, 1)])
def test_ad15_blocks_shrink_with_the_pool(positions: int, rows: int) -> None:
    """AD-15, FR-17: a Wallet's own test (at most 2,000 Positions) is drawn in blocks of 1,000 Simulations as
    before; a larger pool draws fewer rows per block, never fewer than one."""
    assert skilltest._block_rows(positions) == rows


def test_ad15_the_block_size_does_not_change_the_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-15, AD-17: drawing the Simulations in smaller blocks gives the identical count, tail count and chart bars,
    so a large pooled group is tested exactly as a small one would be."""
    pooled = [p for m in shared_market_run(2) for p in m.after.tested]
    usual = skilltest._engine(pooled, seed=SEED, unit_id=holdup.PASSERS, purpose=holdup.PURPOSE)
    for cells in (len(pooled) * 7, len(pooled), 1):
        monkeypatch.setattr(skilltest, "_BLOCK_CELLS", cells)
        assert skilltest._engine(pooled, seed=SEED, unit_id=holdup.PASSERS, purpose=holdup.PURPOSE) == usual


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_ad17_golden_counts_are_reproduced(name: str) -> None:
    """AD-17: the stored count of Simulations at or above the Real PnL is reproduced on every system for three
    pooled groups: steady sharp, the lucky streaks, and seven Passers in the same 40 Markets."""
    if name == "steady-sharp":
        members = [as_member(SMALL["steady-sharp"])]
    elif name == "lucky-streaks":
        members = [as_member(synthetic.lucky_streak(i)) for i in LUCKY_PASSERS]
    else:
        members = shared_market_run(0)
    assert at_or_above(group(members)) == GOLDEN[name]


# --- the FR-17 checks on the Synthetic Wallets (FR-13) --------------------------------------------


def test_fr17_steady_sharp_holds_up() -> None:
    """FR-17 check, SM-4: steady sharp passes on its before part and is still Skilled (high confidence) on its 100
    bets after the Cut-off Date."""
    steady = as_member(SMALL["steady-sharp"])
    assert steady.verdict_before is SKILLED
    result = group([steady])
    assert (result.verdict, result.tested_count, result.wallets, result.dropped) == (SKILLED, 100, 1, 0)
    assert result.real_pnl == pytest.approx(2000.0)  # 70 of 100 won at 0.50, 100 shares each


def test_fr17_lucky_streaks_that_passed_before_show_no_evidence_after() -> None:
    """FR-17 check, FR-13, SM-4: each listed lucky-streak Wallet is Skilled (high confidence) on its 100 bets before
    the Cut-off Date by the real Skill Test; their pooled bets after it show No evidence of skill."""
    members = [as_member(synthetic.lucky_streak(i)) for i in LUCKY_PASSERS]
    assert all(m.verdict_before is SKILLED for m in members)
    result = group(members)
    assert (result.verdict, result.wallets, result.dropped, result.tested_count) == (NO_EVIDENCE, 7, 0, 700)


@pytest.mark.slow
def test_fr13_the_listed_lucky_streaks_are_every_one_that_passed(repetitions: int) -> None:
    """FR-13, FR-17: among the first `repetitions` lucky-streak Wallets (all 1,000 on CI Linux 3.14, else 100), the
    ones Skilled (high confidence) before the Cut-off Date are exactly the listed ones, so the list is not picked;
    each has 100 bets on each side."""
    passed = []
    for index, sample in enumerate(synthetic.lucky_streaks(min(repetitions, synthetic.LUCKY_STREAKS))):
        seen = as_member(sample)
        assert part(sample, after=False).tested_count == seen.after.tested_count == synthetic.COIN_FLIPPER_BETS
        if seen.verdict_before is SKILLED:
            passed.append(index)
    assert passed == [i for i in LUCKY_PASSERS if i < repetitions]


@pytest.mark.slow
def test_fr17_seven_passers_in_the_same_40_markets_rarely_look_skilled(repetitions: int) -> None:
    """FR-17 check, AD-20: across the planted runs (1,000 on CI Linux 3.14, else 100) in which 7 coin-flipper Passers
    hold the same side of the same 40 Markets, p < 0.05 in at most 7%. Counted as 280 separate bets instead, the
    same runs pass far more often: that is the fake significance the shared draw prevents."""
    def share_below(shared: bool, runs: int) -> float:
        p_values = [holdup.hold_up(shared_market_run(run, shared=shared), seed=SEED + run)[0].p_value for run in range(runs)]
        return sum(p < 0.05 for p in p_values) / runs

    assert share_below(shared=True, runs=repetitions) <= 0.07
    assert share_below(shared=False, runs=min(repetitions, 100)) > 0.15  # measured 28% of the first 100 runs


# --- the Hold-up phase of a Scan (AD-5, AD-19, AD-22) ---------------------------------------------


def planted_wallet(name: str, before: tuple[int, int], after: tuple[int, int]) -> SampleWallet:
    """A made-up Wallet in the offline Scan: (bets, won) at 0.50 before the cut-off and after it, plus the anchors."""
    made = synthetic._exact(name, before[0], 0.50, won=before[1])  # noqa: SLF001
    made += [
        replace(b, bought_at=synthetic.CUTOFF + i * synthetic.DAY)
        for i, b in enumerate(synthetic._exact(f"{name} after", after[0], 0.50, won=after[1]))  # noqa: SLF001
    ]
    return synthetic._wallet(name, made, anchors=True)  # noqa: SLF001


def planted_client(root: Path, wallets: Sequence[SampleWallet]) -> OfflineClient:
    """These Wallets written as Sample files under `root`, with the anchor Markets' volume list, served offline."""
    for sample in wallets:
        sample_json.write_wallet(root / synthetic.SMALL_DIR / f"{sample.name}.json", sample)
    sample_json.write_funnel(root / synthetic.SMALL_DIR / synthetic.FUNNEL_FILE, synthetic.funnel_volumes())
    return OfflineClient(sample_files(root), funnels=sample_funnels(root))


def planted_scan(root: Path, wallets: Sequence[SampleWallet], *, seed: int = SEED) -> tuple[Store, int, int]:
    """An offline Scan over these Wallets, started and run by the worker; returns the store, scan id and job id."""
    client = planted_client(root, wallets)
    db = Store(root / "scan.db")
    jobs = Jobs(db)
    started = jobs.start_scan(DAY, len(wallets), seed=seed)
    assert started is not None
    assert Worker(client, jobs).run_once()
    return db, started[0], started[1]


def the_cast(after_won: int = 70) -> list[SampleWallet]:
    """Six planted Wallets: a Passer (`after_won` of its 100 later bets won), a late bloomer (no edge before, all
    100 won after), a quiet one (9 later bets), one with exactly 10, one with too few bets before, and a Passer
    that stopped betting."""
    return [
        planted_wallet("held-up", (100, 70), (100, after_won)),
        planted_wallet("late-bloomer", (100, 50), (100, 100)),
        planted_wallet("quiet", (100, 50), (9, 5)),
        planted_wallet("ten-later", (100, 50), (10, 5)),
        planted_wallet("thin-before", (20, 10), (100, 50)),
        planted_wallet("stopped", (100, 70), (0, 0)),
    ]


def address(name: str) -> str:
    return synthetic.address_of(name)


def groups_of(db: Store, scan_id: int) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {holdup.PASSERS: set(), holdup.COMPARISON: set()}
    for seen in scan_module.hold_up_members(db, scan_id):
        found[holdup.group_of(seen.verdict_before)].add(seen.wallet)
    return found


def test_fr17_a_finished_scan_has_its_two_holdup_results(tmp_path: Path) -> None:
    """FR-17, AD-22, AD-5 (matrix "Scan finishes", "Too few after bets", "No after part"): the Scan's last phase
    stores one `holdup_after` row per group with the Scan, its cut-off and Seed, and only then is the Scan done. The
    groups come from the before part: a Wallet with 9 later bets or none is dropped, one with 10 counts, and one
    with too few bets before is in neither group."""
    db, scan_id, job_id = planted_scan(tmp_path, the_cast())
    try:
        scan, job = db.scan(scan_id), db.job(job_id)
        assert scan.step is ScanStep.DONE and job.status is JobStatus.DONE
        assert groups_of(db, scan_id) == {
            holdup.PASSERS: {address("held-up"), address("stopped")},
            holdup.COMPARISON: {address("late-bloomer"), address("quiet"), address("ten-later")},
        }
        passers, comparison = db.group_results(scan_id)  # the order `hold_up` gives them in
        assert passers == GroupResult(holdup.PASSERS, SKILLED, passers.p_value, 100, 2000.0, 2, 1, 0)
        assert passers.p_value is not None and passers.p_value < 0.01
        assert (comparison.group, comparison.wallets, comparison.dropped, comparison.tested_count) == (holdup.COMPARISON, 3, 1, 110)
        assert comparison.real_pnl == pytest.approx(100 * 50.0 + 0.0)  # late bloomer +$5,000, ten-later $0
        assert db.group_results(scan_id) == scan_module.hold_up_scan(db, scan_id)
        stored = db._connection().execute("SELECT DISTINCT scan_id, scope, cutoff, seed FROM group_result").fetchall()
        assert stored == [(scan_id, HOLDUP_AFTER, cutoff_at(DAY), SEED)]
        assert db.group_results(scan_id, "another_scope") == ()
    finally:
        db.close()


def test_fr17_a_wallet_skilled_only_on_its_whole_history_is_not_a_passer(tmp_path: Path) -> None:
    """FR-17: the late bloomer is Skilled (high confidence) on both parts together (`scan_whole`, the Watchlist) but
    not on its before part, so it is in the Comparison Group, never a Passer."""
    db, scan_id, _ = planted_scan(tmp_path, the_cast())
    try:
        late = {r.scope: r.verdict for r in db.scan_results(scan_id) if r.wallet == address("late-bloomer")}
        assert late == {SCAN_BEFORE: NO_EVIDENCE.value, SCAN_WHOLE: SKILLED.value}
        assert address("late-bloomer") in groups_of(db, scan_id)[holdup.COMPARISON]
    finally:
        db.close()


def test_fr17_changing_what_happened_after_the_cutoff_changes_no_group(tmp_path: Path) -> None:
    """FR-17 (tested by changing after-part outcomes): the same Scan with the Passer's later bets all lost has the
    same Wallets in each group and the same dropped counts; its Passers' result turns to No evidence of skill."""
    kept, scan_a, _ = planted_scan(tmp_path / "a", the_cast(after_won=70))
    lost, scan_b, _ = planted_scan(tmp_path / "b", the_cast(after_won=0))
    try:
        assert groups_of(kept, scan_a) == groups_of(lost, scan_b)
        (passers_a, comparison_a), (passers_b, comparison_b) = kept.group_results(scan_a), lost.group_results(scan_b)
        assert comparison_a == comparison_b
        assert (passers_a.wallets, passers_a.dropped) == (passers_b.wallets, passers_b.dropped) == (2, 1)
        assert (passers_a.verdict, passers_b.verdict) == (SKILLED, NO_EVIDENCE)
        whole = {r.wallet: r.verdict for r in lost.scan_results(scan_b) if r.scope == SCAN_WHOLE}
        assert whole[address("held-up")] != SKILLED.value  # the whole-history result did change; the group did not
    finally:
        kept.close()
        lost.close()


def test_ad19_the_after_part_is_cut_to_the_scans_as_of_time(tmp_path: Path) -> None:
    """AD-19: Markets resolved at or after the Scan's as-of time are left out of the Hold-up Test, so a Scan
    resumed later tests what an uninterrupted run would have."""
    db, scan_id, _ = planted_scan(tmp_path, the_cast())
    try:
        scan = db.scan(scan_id)
        full = {m.wallet: m.after.tested_count for m in scan_module.hold_up_members(db, scan_id)}
        cut_at = synthetic.CUTOFF + 2 * synthetic.DAY + 50 * synthetic.DAY  # the 51st later bet resolves here
        db._connection().execute("UPDATE scan SET as_of = ? WHERE scan_id = ?", (cut_at, scan_id))
        db._connection().commit()
        early = {m.wallet: m.after.tested_count for m in scan_module.hold_up_members(db, scan_id)}
        assert (full[address("held-up")], early[address("held-up")]) == (100, 50)
        assert early[address("ten-later")] == 10 and scan.as_of > cut_at
    finally:
        db.close()


def test_fr17_a_passer_whose_after_part_was_refused_is_dropped_and_flagged(tmp_path: Path) -> None:
    """FR-17, AD-9 (matrix "No after part"): a Wallet whose after part Polymarket refused has no frozen after
    snapshot and a flagged `scan_whole` result; it stays in its group, is dropped for too few after bets, and is
    counted as not fully read."""
    db, scan_id, _ = planted_scan(tmp_path, the_cast())
    try:
        with db._write() as raw:  # what `_test_top` stores for a refused after part
            raw.execute("UPDATE scan_wallet SET after_fetch_id = NULL WHERE scan_id = ? AND wallet = ?", (scan_id, address("held-up")))
            raw.execute(
                "UPDATE scan_result SET not_fully_read = 1 WHERE scan_id = ? AND wallet = ? AND scope = ?",
                (scan_id, address("held-up"), SCAN_WHOLE),
            )
        refused = next(m for m in scan_module.hold_up_members(db, scan_id) if m.wallet == address("held-up"))
        assert (refused.verdict_before, refused.after.tested_count, refused.not_fully_read) == (SKILLED, 0, True)
        passers, _ = scan_module.hold_up_scan(db, scan_id)
        assert passers == GroupResult(holdup.PASSERS, NOT_ENOUGH, None, 0, 0.0, 2, 2, 1)
    finally:
        db.close()


def test_ad15_the_holdup_test_runs_under_the_scans_own_seed(tmp_path: Path) -> None:
    """AD-15, AD-22: the stored Hold-up result is the one the Scan's own Seed gives, here 7, not the default 44 (a
    Passer with 52 of its 100 later bets won, so the p-value sits mid-range and moves with the Seed)."""
    own = 7
    db, scan_id, _ = planted_scan(tmp_path, the_cast(after_won=52), seed=own)
    try:
        members = scan_module.hold_up_members(db, scan_id)
        passers, _ = db.group_results(scan_id)
        assert db.scan(scan_id).seed == own and passers == holdup.hold_up(members, seed=own)[0]
        assert passers.verdict is NO_EVIDENCE and 0.2 < passers.p_value < 0.6
        assert passers.p_value not in {holdup.hold_up(members, seed=other)[0].p_value for other in (0, SEED, own + 1)}
        assert db._connection().execute("SELECT DISTINCT seed FROM group_result").fetchall() == [(own,)]
    finally:
        db.close()


def test_fr17_a_passer_not_fully_read_is_kept_flagged_and_counted(tmp_path: Path) -> None:
    """FR-17, FR-16, AD-11: a Passer whose trades after the Cut-off Date could be read only in part is kept in its
    group on the bets that were read, and the group's "not fully read" count shows it."""
    cast = the_cast()
    cast[0] = replace(cast[0], activity_until=synthetic.CUTOFF + 60 * synthetic.DAY)
    db, scan_id, _ = planted_scan(tmp_path, cast)
    try:
        held_up = next(m for m in scan_module.hold_up_members(db, scan_id) if m.wallet == address("held-up"))
        assert held_up.not_fully_read and 10 <= held_up.after.tested_count < 100
        passers, comparison = db.group_results(scan_id)
        assert (passers.wallets, passers.dropped, passers.not_fully_read) == (2, 1, 1)
        assert passers.tested_count == held_up.after.tested_count and comparison.not_fully_read == 0
    finally:
        db.close()


class AppClosed(Exception):
    """Stands in for the app being closed: the job is left `running`."""


def test_ad5_a_scan_closed_in_the_holdup_phase_resumes_to_the_same_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-5, AD-19 (matrix "Interrupted"): the app closing during the Hold-up phase leaves the Scan unfinished with
    no Hold-up row; Resume runs the phase again and stores the same rows as an uninterrupted run."""
    whole, whole_id, _ = planted_scan(tmp_path / "whole", the_cast())
    expected = whole.group_results(whole_id)
    whole.close()

    real = scan_module.hold_up_scan
    closing = [True]

    def close_once(store: Store, scan_id: int, between: object) -> object:
        if closing:
            closing.clear()
            raise AppClosed
        return real(store, scan_id, between)

    client = planted_client(tmp_path / "closed", the_cast())
    db = Store(tmp_path / "closed" / "scan.db")
    try:
        jobs = Jobs(db)
        scan_id, job_id = jobs.start_scan(DAY, 6, seed=SEED)
        job = db.claim_next_job()
        monkeypatch.setattr(scan_module, "hold_up_scan", close_once)
        with pytest.raises(AppClosed):
            scan_module.run_scan(client, db, scan_id, job_id=job.id)
        stopped = db.job(job_id)
        assert (stopped.status, stopped.phase, stopped.message) == (JobStatus.RUNNING, "holdup", "Hold-up Test")
        assert db.scan(scan_id).step is ScanStep.RANKED and db.group_results(scan_id) == ()
        assert db.interrupt_running_jobs() == 1
        tested = len(db.scan_results(scan_id))
        assert jobs.resume_scan(scan_id) is not None and Worker(client, jobs).run_once()
        assert db.scan(scan_id).step is ScanStep.DONE
        assert db.group_results(scan_id) == expected and len(db.scan_results(scan_id)) == tested
    finally:
        db.close()


def test_ad5_a_waiting_lookup_can_run_between_two_wallets_of_the_holdup_phase(tmp_path: Path) -> None:
    """AD-5 (review, Story 5.1): the Hold-up phase calls `between` once after each group member's after part is
    read, and `run_scan` hands it the worker's own `between`, so a queued lookup does not wait for the whole phase."""
    client = planted_client(tmp_path, the_cast())
    db = Store(tmp_path / "scan.db")
    try:
        jobs = Jobs(db)
        scan_id, job_id = jobs.start_scan(DAY, 6, seed=SEED)
        job = db.claim_next_job()
        phases: list[str] = []
        scan_module.run_scan(client, db, scan_id, job_id=job.id, between=lambda: phases.append(db.job(job_id).phase))
        assert phases.count("holdup") == 5  # the five Wallets in a group; the one with too few bets before is not read
        calls: list[int] = []
        assert len(scan_module.hold_up_members(db, scan_id, lambda: calls.append(1))) == len(calls) == 5
    finally:
        db.close()


def test_ad5_the_progress_names_the_holdup_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-5, UX-DR32: after the Skill Tests the progress JSON carries the phase `holdup` and the step "Hold-up
    Test", and that is the Scan's last step."""
    seen: list[tuple[str, int, int, str]] = []
    original = Store.update_progress

    def record(self: Store, job_id: int, *, phase: str, done: int, total: int, message: str) -> None:
        seen.append((phase, done, total, message))
        original(self, job_id, phase=phase, done=done, total=total, message=message)

    monkeypatch.setattr(Store, "update_progress", record)
    db, _, _ = planted_scan(tmp_path, the_cast())
    db.close()
    checked = seen.index(("skill_tests", 6, 6, "6 of 6 Wallets checked"))
    assert seen[checked + 1:] == [("holdup", 0, 1, "Hold-up Test"), ("holdup", 1, 1, "Hold-up Test")]


def test_ad5_a_bad_pool_fails_the_scan_and_stores_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-5 (matrix "Bad pool"): an error in the Hold-up phase fails the job with no Resume; the Scan is not done
    and has no Hold-up row."""
    def refuse(*args: object, **kwargs: object) -> object:
        raise ValueError("Market m has 3 outcomes in one test; only two are supported")

    monkeypatch.setattr(scan_module.holdup, "hold_up", refuse)
    client = planted_client(tmp_path, the_cast())
    db = Store(tmp_path / "scan.db")
    try:
        jobs = Jobs(db)
        scan_id, job_id = jobs.start_scan(DAY, 6, seed=SEED)
        assert Worker(client, jobs).run_once()
        assert db.job(job_id).status is JobStatus.FAILED and db.scan(scan_id).step is ScanStep.RANKED
        assert db.group_results(scan_id) == () and jobs.resume_scan(scan_id) is None
    finally:
        db.close()


def test_ad22_the_group_rows_and_the_done_step_are_one_transaction(tmp_path: Path) -> None:
    """AD-22, AD-5: a Scan finishes with exactly its two Hold-up rows, stored with the step that finishes it or not
    at all. Anything but the two groups once each, an unknown Scan and a Scan at another step are refused, and a
    failure after the step moved rolls the step back. The rows come back Passers first, whatever order they came in."""
    path = tmp_path / "live.db"
    Store(path).close()
    scan_id, early, blocked = (hand_scan(path, [], step=step) for step in ("ranked", "shortlisted", "ranked"))
    db = Store(path)
    try:
        passers, comparison = counts(3, 1), counts(4, 2, holdup.COMPARISON)
        others = counts(1, 0, "others")
        for wrong in ([], [passers], [passers, passers], [passers, others], [passers, comparison, comparison]):
            with pytest.raises(ValueError, match="once each"):
                db.finish_scan(scan_id, wrong)
        assert db.scan(scan_id).step is ScanStep.RANKED and db.group_results(scan_id) == ()
        with pytest.raises(ValueError, match="not at step"):
            db.finish_scan(early, [passers, comparison])
        assert db.scan(early).step is ScanStep.SHORTLISTED and db.group_results(early) == ()
        with pytest.raises(ValueError, match="no Scan"):
            db.finish_scan(blocked + 1, [passers, comparison])

        with db._write() as raw:  # a row that should not be there: the insert fails after the step has moved
            raw.execute(
                "INSERT INTO group_result (scan_id, scope, group_name, cutoff, seed, verdict, tested_count, real_pnl,"
                " wallets, dropped, not_fully_read) VALUES (?, ?, ?, 0, 0, ?, 0, 0, 0, 0, 0)",
                (blocked, HOLDUP_AFTER, holdup.COMPARISON, NOT_ENOUGH.value),
            )
        with pytest.raises(sqlite3.IntegrityError):
            db.finish_scan(blocked, [passers, comparison])
        assert db.scan(blocked).step is ScanStep.RANKED  # rolled back with the failed insert
        assert [r.group for r in db.group_results(blocked)] == [holdup.COMPARISON]

        db.finish_scan(scan_id, [comparison, passers])
        assert db.scan(scan_id).step is ScanStep.DONE and db.group_results(scan_id) == (passers, comparison)
        with pytest.raises(ValueError, match="not at step"):
            db.finish_scan(scan_id, [passers, comparison])
        assert db.group_results(scan_id) == (passers, comparison)
    finally:
        db.close()


# --- the offline Scan of the Sample Dataset (FR-17; Edvard, 2026-11-27) ------------------------------

# The full 1,000 was run by hand (spec Implementation Notes); 90 hold the first lucky one (index 87), so the Scan
# and the `slow` check over the generator must agree on it.
SCAN_COIN_FLIPPERS = 90


@pytest.fixture(scope="module")
def offline_scan(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Store, int, dict[str, holdup.Member]]]:
    """A finished offline Scan of the committed Sample Wallets (real and made-up) and 90 coin-flippers, with its
    Hold-up members by address (shared: the Scan takes a few seconds)."""
    root = tmp_path_factory.mktemp("offline-scan")
    real = sorted((REPO / offline_module.REAL_DIR).glob("0x*.json"))
    small = sorted(p for p in (REPO / synthetic.SMALL_DIR).glob("*.json") if p.name not in offline_module.NOT_WALLET_FILES)
    flippers = sorted(synthetic.write_coin_flippers(root, SCAN_COIN_FLIPPERS).glob("*.json"))
    client = OfflineClient([*real, *small, *flippers], funnels=sample_funnels(REPO))
    db = Store(root / "scan.db")
    try:
        jobs = Jobs(db)
        scan_id, _ = jobs.start_scan(DAY, len(client.addresses()), seed=SEED)
        assert Worker(client, jobs).run_once() and db.scan(scan_id).step is ScanStep.DONE
        yield db, scan_id, {m.wallet: m for m in scan_module.hold_up_members(db, scan_id)}
    finally:
        db.close()


def test_fr17_the_offline_scan_drops_the_coin_flippers_and_sets_the_flag(
    offline_scan: tuple[Store, int, dict[str, holdup.Member]],
) -> None:
    """FR-17, FR-13 (matrix "Offline Scan"; Edvard, 2026-11-27): in an offline Scan of the committed Sample Wallets
    and 90 coin-flippers, no coin-flipper has a bet after the Cut-off Date, so every one is dropped; sharp trader is
    dropped too, while steady sharp, forecaster and speed trader are tested on 300 later bets and hold up. Nearly
    all of the Comparison Group is dropped, so the dropped-share flag is set: the warning is right and stays."""
    db, scan_id, members = offline_scan
    coin = {address(synthetic.coin_flipper_name(i)) for i in range(SCAN_COIN_FLIPPERS)}
    assert coin <= set(members) and all(members[w].after.tested_count == 0 for w in coin)
    passers, comparison = db.group_results(scan_id)
    four = {address(name) for name in synthetic.WATCHLIST_NAMES}
    lucky = {w for w in coin if members[w].verdict_before is SKILLED}
    # the Scan's own stored Verdicts agree with the listed lucky coin-flippers (review, Story 5.2)
    assert lucky == {address(synthetic.coin_flipper_name(i)) for i in LUCKY_COIN_FLIPPERS if i < SCAN_COIN_FLIPPERS}
    assert len(lucky) == 1
    assert {w for w, m in members.items() if m.verdict_before is SKILLED} == four | lucky
    assert (passers.wallets, passers.dropped) == (4 + len(lucky), 1 + len(lucky))
    assert (passers.verdict, passers.tested_count, passers.real_pnl) == (SKILLED, 300, pytest.approx(6000.0))
    real_members = set(members) - coin - four
    assert len(real_members) == 5 and not any(members[w].not_fully_read for w in real_members)
    assert sorted(members[w].after.tested_count for w in real_members) == [4, 9, 13, 89, 307]
    assert members[BIGGEST_REAL].after.tested_count == 307  # the README names this Wallet
    assert members[address("sharp-trader")].after.tested_count == 0
    assert comparison.wallets == len(coin - lucky) + 5 and comparison.dropped == len(coin - lucky) + 2
    # The dropped Wallets add nothing to a pool, so these are the full offline Scan's numbers (with all 1,000
    # coin-flippers: 999 Wallets, 996 dropped), the ones Story 5.2 reports.
    bets_counted, golden, real_pnl = REAL_COMPARISON
    assert (comparison.verdict, comparison.tested_count, at_or_above(comparison)) == (NO_EVIDENCE, bets_counted, golden)
    assert comparison.real_pnl == pytest.approx(real_pnl, abs=0.005)
    assert at_or_above(passers) == 0 and (passers.not_fully_read, comparison.not_fully_read) == (0, 0)
    assert holdup.dropped_shares_differ(passers, comparison)


def test_fr17_no_real_wallet_is_a_passer_in_the_offline_scan(
    offline_scan: tuple[Store, int, dict[str, holdup.Member]],
) -> None:
    """FR-17, NFR-13 (Edvard, 2026-11-27, Story 5.2): the offline Hold-up page and the README say "the Passers tested
    here are made-up Wallets built to have skill, not real traders: no real Wallet passed before the Cut-off Date."
    This fails the day that stops being true: a real Sample Wallet rated *Skilled (high confidence)* on its bets
    before the date, or a tested Passer that is not one of the three Wallets built to keep winning (a real Wallet,
    or a coin-flipper that passed by luck and kept betting)."""
    db, scan_id, members = offline_scan
    real = {path.stem for path in (REPO / offline_module.REAL_DIR).glob("0x*.json")}
    before = {r.wallet: r.verdict for r in db.scan_results(scan_id) if r.scope == SCAN_BEFORE}
    assert len(real) == 10 and len(real & set(before)) == 8  # the 8 real Wallets in the offline Scan (Story 4.7)
    # "Passed" by the app's own rule (`group_of`), so a changed rule that lets a real Wallet in fails here too.
    assert [w for w in sorted(real & set(before)) if holdup.group_of(Verdict(before[w])) == holdup.PASSERS] == []
    passed = {w for w, member in members.items() if holdup.group_of(member.verdict_before) == holdup.PASSERS}
    assert passed and not passed & real
    tested = {w for w in passed if holdup.counts(members[w])}
    assert tested == {address(name) for name in BUILT_TO_HOLD_UP}
    assert not tested & real
    # The sentence this test stands behind: reworded, it must be read against the checks above again.
    assert holdup_page.OFFLINE_PASSERS == (
        "On the Sample Dataset, the Passers tested here are made-up Wallets built to have skill, not real traders: "
        "no real Wallet passed before the Cut-off Date."
    )


OTHER_SEEDS = (1, 7, 2026, 31337)


def test_fr17_no_real_wallet_passes_before_the_date_under_other_seeds(
    offline_scan: tuple[Store, int, dict[str, holdup.Member]],
) -> None:
    """FR-17, AD-15 (review, Story 5.2): the Seed is a setting, and the offline page's sentence "no real Wallet passed
    before the Cut-off Date" does not name one. Each real Wallet's bets before the date, from the Scan's frozen
    snapshots, are tested again under four other Seeds: none passes, and the three made-up Wallets built to have skill
    pass under every one. With the Scan's own Seed the same recomputation gives the stored result, so it is the
    Scan's test that is repeated."""
    db, scan_id, _ = offline_scan
    scan = db.scan(scan_id)
    real = {path.stem for path in (REPO / offline_module.REAL_DIR).glob("0x*.json")}
    built = {address(name) for name in BUILT_TO_HOLD_UP}
    checked = set()
    for stored in db.scan_results(scan_id):
        if stored.scope != SCAN_BEFORE or stored.wallet not in real | built or stored.fetch_id is None:
            continue
        before = scan_module.parts_position_set([scan_module.as_of_part(db.snapshot(stored.fetch_id), scan.as_of)])
        same = skilltest.skill_test(before, seed=SEED, unit_id=stored.wallet, scope=SCAN_BEFORE)
        assert (same.verdict.value, same.p_value, same.tested_count) == (stored.verdict, stored.p_value, stored.tested_count)
        for seed in OTHER_SEEDS:
            again = skilltest.skill_test(before, seed=seed, unit_id=stored.wallet, scope=SCAN_BEFORE)
            passes = holdup.group_of(again.verdict) == holdup.PASSERS
            assert passes == (stored.wallet in built), (stored.wallet, seed, again.verdict, again.p_value)
        checked.add(stored.wallet)
    assert built <= checked and len(checked & real) == 8  # every real Wallet in the offline Scan was tested again


@pytest.mark.slow
def test_fr17_the_listed_lucky_coin_flippers_are_every_one_that_passed(repetitions: int) -> None:
    """FR-17, FR-13, NFR-13 (review, Story 5.2): among the first `repetitions` coin-flippers (all 1,000 on CI Linux
    3.14, else 100), the ones rated *Skilled (high confidence)* before the Cut-off Date are exactly the listed ones,
    and none has a bet after the date. The README's group sizes (10 Passers with 7 dropped, 999 with 996 dropped)
    are built from this list, so a change to the generator or the Skill Test that moves them fails here."""
    passed = []
    for index, sample in enumerate(synthetic.coin_flippers(min(repetitions, synthetic.COIN_FLIPPERS))):
        seen = as_member(sample)
        assert seen.after.tested_count == 0 and not seen.after.slivers
        if holdup.group_of(seen.verdict_before) == holdup.PASSERS:
            passed.append(index)
    assert passed == [i for i in LUCKY_COIN_FLIPPERS if i < repetitions]
    assert OFFLINE_PASSER_SIZES == (10, 7) and OFFLINE_COMPARISON_SIZES == (999, 996)  # what the README states


def test_fr13_the_lucky_streaks_are_for_the_checks_only() -> None:
    """FR-13, AD-14 (Edvard, 2026-11-27): the lucky-streak Wallets are built by the generator and never written or
    loaded: the generator has no writer for them, their addresses are not Sample Wallets, and they hold no anchor
    Positions, so no Scan finds them. Building one twice gives the same bytes, with 100 bets on each side of the
    Cut-off Date, the later ones at prices of 10 to 90 cents."""
    assert not [name for name in dir(synthetic) if "lucky" in name.lower() and name.startswith("write")]
    assert [synthetic.lucky_streak_name(i) for i in (0, 999)] == ["lucky-streak-0000", "lucky-streak-0999"]
    assert sample_json.dumps(synthetic.lucky_streak(2), compact=True) == sample_json.dumps(synthetic.lucky_streak(2), compact=True)
    assert synthetic.lucky_streak(2) != synthetic.lucky_streak(3)
    anchors = set(synthetic.funnel_volumes())
    streak = synthetic.lucky_streak(0)
    assert not anchors & {m.condition_id for m in streak.markets} and len(streak.markets) == 200
    assert sum(m.closed_time < synthetic.CUTOFF for m in streak.markets) == 100
    assert min(row.timestamp for row in streak.activity if row.timestamp >= synthetic.CUTOFF) == synthetic.CUTOFF
    assert streak.address not in synthetic.all_addresses()
    assert {round(p.entry_price * 100) for p in as_member(streak).after.tested} <= set(range(10, 91))
