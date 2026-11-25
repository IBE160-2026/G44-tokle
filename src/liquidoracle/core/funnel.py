"""The Scan funnel's pure steps: the pre-filter, the 3 x N shortlist and the top N (FR-16, AD-21).

Nothing here reads Polymarket; `services/scan` runs these steps on what the client read. Every
order breaks ties by address, so the same reads always give the same funnel (AD-15).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace

from liquidoracle.records import Candidate, Market, MarketHolder, RankedWallet


def estimates(holders: Mapping[str, Sequence[MarketHolder]], markets: Mapping[str, Market]) -> dict[str, float]:
    """AD-21's pre-filter per Wallet, over the used Markets only: Σ CLOSED `realized_pnl` + Σ OPEN
    `current_size` x (the token's outcome price - `avg_price`).

    `holders` maps each used Market's condition id to the rows of both its lists; `markets` gives
    its Gamma record, whose outcome price is 1 or 0 (every Market of the set is resolved). An OPEN
    row on the losing token is an unredeemed loser and counts -size x `avg_price`. Every Wallet with
    a row is a candidate, also one whose estimate is $0.
    """
    terms: dict[str, list[float]] = {}
    for condition_id, rows in holders.items():
        market = markets[condition_id]
        price_of = dict(zip(market.token_ids, market.outcome_prices, strict=True))
        for row in rows:
            if row.status == "CLOSED":
                term = row.realized_pnl
            elif row.status == "OPEN":
                if row.token_id not in price_of:
                    raise ValueError(f"token {row.token_id} is not an outcome of Market {condition_id}")
                term = row.current_size * (price_of[row.token_id] - row.avg_price)
            else:
                raise ValueError(f"a holder row's status must be CLOSED or OPEN, not {row.status!r}")
            terms.setdefault(row.wallet, []).append(term)
    return {wallet: math.fsum(values) for wallet, values in terms.items()}


def shortlist(estimate_of: Mapping[str, float], count: int) -> tuple[Candidate, ...]:
    """The top `count` candidates by estimate (3 x N in a Scan), ties broken by address; all of them when fewer."""
    _check_size(count)
    ordered = sorted(estimate_of.items(), key=lambda item: (-item[1], item[0]))
    return tuple(Candidate(wallet, estimate) for wallet, estimate in ordered[:count])


def top_n(ranked: Iterable[RankedWallet], size: int) -> tuple[RankedWallet, ...]:
    """Every ranked Wallet by Real PnL, highest first and ties broken by address, the first `size` marked `top`."""
    _check_size(size)
    ordered = sorted(ranked, key=lambda w: (-w.real_pnl, w.wallet))
    return tuple(replace(w, top=i < size) for i, w in enumerate(ordered))


def _check_size(count: int) -> None:
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError(f"the number of Wallets must be a whole number of 1 or more, not {count!r}")
