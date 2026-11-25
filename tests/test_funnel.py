"""The Scan funnel's pure steps: the pre-filter, the 3 x N shortlist and the top N (FR-16, AD-21).

Hand-made holder rows and Markets; nothing is read (AD-17).
"""

from __future__ import annotations

import pytest

from liquidoracle.core import funnel
from liquidoracle.records import Candidate, Market, MarketHolder, RankedWallet

YES, NO = "111", "222"
M1, M2 = f"0x{1:064x}", f"0x{2:064x}"


def market(condition_id: str, yes_won: bool = True) -> Market:
    prices = (1.0, 0.0) if yes_won else (0.0, 1.0)
    return Market(condition_id, closed=True, closed_time=1_750_000_000, token_ids=(YES, NO), outcome_prices=prices)


def wallet(n: int) -> str:
    return f"0x{n:040x}"


def closed(n: int, pnl: float, token: str = YES) -> MarketHolder:
    return MarketHolder(wallet(n), token, "CLOSED", pnl, 0.0, 0.5)


def held(n: int, token: str, size: float, avg_price: float) -> MarketHolder:
    return MarketHolder(wallet(n), token, "OPEN", 0.0, size, avg_price)


def test_closed_rows_count_their_realized_pnl() -> None:
    """AD-21: a CLOSED row adds its `realized_pnl`, a win or a loss, whatever token it was."""
    rows = [closed(1, 120.0), closed(1, -20.0, NO), closed(2, -5.5)]
    assert funnel.estimates({M1: rows}, {M1: market(M1)}) == {wallet(1): 100.0, wallet(2): -5.5}


def test_an_open_winner_counts_its_resolved_value_minus_cost() -> None:
    """AD-21: an OPEN row on the winning token adds size x (1 - avg_price)."""
    assert funnel.estimates({M1: [held(1, YES, 200.0, 0.3)]}, {M1: market(M1)}) == {wallet(1): pytest.approx(140.0)}


def test_an_unredeemed_loser_counts_minus_its_cost() -> None:
    """AD-21: an OPEN row on the losing token (an unredeemed loser) adds -size x avg_price, so losers count."""
    assert funnel.estimates({M1: [held(1, NO, 100.0, 0.4)]}, {M1: market(M1)}) == {wallet(1): pytest.approx(-40.0)}


def test_the_outcome_price_comes_from_the_markets_own_order() -> None:
    """AD-10, AD-21: the token's price is the Gamma price at the token's own place, so a No win pays the No holder."""
    estimate = funnel.estimates({M1: [held(1, NO, 10.0, 0.2), held(2, YES, 10.0, 0.2)]}, {M1: market(M1, yes_won=False)})
    assert estimate == {wallet(1): pytest.approx(8.0), wallet(2): pytest.approx(-2.0)}


def test_estimates_sum_over_every_used_market() -> None:
    """AD-21: a Wallet's estimate is the sum over the Markets given, both lists; only the Markets given count."""
    holders = {M1: [closed(1, 50.0), held(1, YES, 10.0, 0.5)], M2: [closed(1, -15.0), closed(3, 1.0)]}
    estimate = funnel.estimates(holders, {M1: market(M1), M2: market(M2)})
    assert estimate == {wallet(1): pytest.approx(40.0), wallet(3): 1.0}
    assert funnel.estimates({}, {M1: market(M1)}) == {}


def test_a_wallet_at_zero_is_still_a_candidate() -> None:
    """AD-21: every Wallet with a row is a candidate, also one whose estimate is exactly $0."""
    assert funnel.estimates({M1: [closed(1, 0.0)]}, {M1: market(M1)}) == {wallet(1): 0.0}


def test_an_open_row_on_a_token_the_market_does_not_have_is_refused() -> None:
    """AD-21: a holder of a token that is not one of the Market's outcomes is never guessed at."""
    with pytest.raises(ValueError, match="not an outcome"):
        funnel.estimates({M1: [held(1, "999", 1.0, 0.5)]}, {M1: market(M1)})


def test_the_shortlist_is_the_top_by_estimate_ties_by_address() -> None:
    """AD-21: the shortlist is the top `count` by estimate, highest first; equal estimates go by address."""
    estimate_of = {wallet(5): 10.0, wallet(2): 30.0, wallet(9): 30.0, wallet(1): -4.0, wallet(3): 10.0}
    assert funnel.shortlist(estimate_of, 4) == (
        Candidate(wallet(2), 30.0), Candidate(wallet(9), 30.0), Candidate(wallet(3), 10.0), Candidate(wallet(5), 10.0),
    )


def test_fewer_candidates_than_the_shortlist_are_all_kept() -> None:
    """AD-21: with fewer candidates than 3 x N, every one of them is shortlisted."""
    estimate_of = {wallet(1): 1.0, wallet(2): -1.0}
    assert [c.wallet for c in funnel.shortlist(estimate_of, 600)] == [wallet(1), wallet(2)]
    assert funnel.shortlist({}, 600) == ()


def test_the_top_n_by_real_pnl_ties_by_address() -> None:
    """AD-21: every ranked Wallet comes back by Real PnL, ties by address, and exactly the first N are marked top."""
    ranked = [RankedWallet(wallet(4), 5.0), RankedWallet(wallet(2), 9.0), RankedWallet(wallet(3), 5.0), RankedWallet(wallet(1), -1.0)]
    result = funnel.top_n(ranked, 2)
    assert [(w.wallet, w.top) for w in result] == [(wallet(2), True), (wallet(3), True), (wallet(4), False), (wallet(1), False)]


def test_a_refused_wallet_is_ranked_like_any_other() -> None:
    """AD-9 (Edvard, 2026-11-25, Story 4.2): a refused Wallet is ranked on $0, the same rule as every Wallet; it is
    not kept in the top N for being refused (rejected: always keeping it)."""
    refused = RankedWallet(wallet(1), 0.0, not_fully_read=True, refused=True)
    result = funnel.top_n([refused, RankedWallet(wallet(2), 3.0), RankedWallet(wallet(3), -3.0)], 1)
    assert [(w.wallet, w.top) for w in result] == [(wallet(2), True), (wallet(1), False), (wallet(3), False)]
    assert result[1].not_fully_read and result[1].refused


def test_fewer_ranked_than_n_are_all_kept() -> None:
    """AD-21: with fewer ranked Wallets than N, all of them are in the top N."""
    assert all(w.top for w in funnel.top_n([RankedWallet(wallet(1), 1.0), RankedWallet(wallet(2), 2.0)], 200))
    assert funnel.top_n([], 200) == ()


@pytest.mark.parametrize("size", [0, -1, True, 2.0])
def test_a_size_below_one_is_refused(size: object) -> None:
    """AD-21: N and the shortlist count are whole numbers of 1 or more."""
    with pytest.raises(ValueError):
        funnel.shortlist({}, size)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        funnel.top_n([], size)  # type: ignore[arg-type]
