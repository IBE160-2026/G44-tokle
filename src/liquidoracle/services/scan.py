"""The Scan funnel: which Wallets a Scan checks, picked only from what happened before the Cut-off Date (FR-16, AD-21).

Four steps, each a plain function so Story 4.3 can run them as job phases with waiting lookups in
between (AD-5): `choose_markets` (the Market set), `read_candidates` (one Market's holders),
`shortlist` (3 x N by the pre-filter) and `rank_wallet` (one Wallet's before part). `run_funnel`
runs them all in order and returns one in-memory `ScanFunnel`; storing it, the job and Resume are
Story 4.3's.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from liquidoracle.core import funnel
from liquidoracle.core.positions import build_positions
from liquidoracle.core.skilltest import real_pnl
from liquidoracle.data.client import FunnelClient, WalletClient
from liquidoracle.data.errors import NoPolymarketHistory, PolymarketBadRequest, ProtocolContractAddress
from liquidoracle.data.window import WINDOW_LIMIT, cutoff_at, positions_near
from liquidoracle.records import Candidate, FunnelMarket, MarketHolder, RankedWallet, ScanFunnel

log = logging.getLogger(__name__)

MARKET_DAYS = 90  # [ASSUMPTION] AD-21: Markets resolved in the 90 days before the cut-off
MARKET_COUNT = 100  # [ASSUMPTION] AD-21: the top 100 of them by volume
SHORTLIST_FACTOR = 3  # [ASSUMPTION] AD-21: the shortlist is 3 x N
DEFAULT_SIZE = 200  # [ASSUMPTION] AD-21: N, the Wallets a Scan keeps
_DAY = 86_400


@dataclass(frozen=True, slots=True)
class MarketRead:
    """One Market of the set after its two holder lists are read (AD-9).

    `used` is True only when both lists were read complete and under `MARKET_ROW_CAP`; otherwise the
    Market is "not used: partial" and `holders` is empty, so it gives no candidates.
    """

    condition_id: str
    used: bool
    holders: tuple[MarketHolder, ...]


def choose_markets(client: FunnelClient, cutoff: date) -> tuple[FunnelMarket, ...]:
    """AD-21's Market set: resolved in the 90 days before the cut-off, the top 100 by volume; outcomes are not looked at."""
    cut = cutoff_at(cutoff)
    return client.funnel_markets(cut - MARKET_DAYS * _DAY, cut, MARKET_COUNT)


def read_candidates(client: FunnelClient, market: FunnelMarket) -> MarketRead:
    """One Market's CLOSED and OPEN holders (AD-9).

    A partial list (capped, or every try timed out) or one Polymarket refuses leaves the Market
    unused; when that is the CLOSED list, the OPEN list is not read. `PolymarketUnavailable` is
    raised and stops the Scan.
    """
    condition_id = market.market.condition_id
    rows: list[MarketHolder] = []
    for status in ("CLOSED", "OPEN"):
        try:
            read = client.market_holders(condition_id, status)
        except PolymarketBadRequest as error:
            log.warning("Polymarket refused the %s list of Market %s (%s); the Market is not used", status, condition_id, error)
            return MarketRead(condition_id, False, ())
        if not read.complete:
            return MarketRead(condition_id, False, ())
        rows.extend(read.rows)
    return MarketRead(condition_id, True, tuple(rows))


def shortlist(
    markets: Sequence[FunnelMarket], reads: Sequence[MarketRead], size: int
) -> tuple[int, tuple[Candidate, ...]]:
    """The candidate count and the 3 x N shortlist by the pre-filter, over the used Markets only (AD-21)."""
    record = {m.market.condition_id: m.market for m in markets}
    holders = {read.condition_id: read.holders for read in reads if read.used}
    estimate_of = funnel.estimates(holders, record)
    return len(estimate_of), funnel.shortlist(estimate_of, SHORTLIST_FACTOR * size)


def rank_wallet(client: WalletClient, wallet: str, cutoff: date) -> RankedWallet | None:
    """One shortlisted Wallet's Real PnL on its before part (AD-7, AD-9, AD-10); None for a protocol contract.

    The window goes through the one builder and `real_pnl`, the Skill Test's own source. A Wallet
    Polymarket refuses is kept and flagged "not fully read". `positions_near` is all-or-nothing, so a
    refusal at any request discards whatever was read, and the Wallet ranks on $0.
    One with no Polymarket history has $0 and no flag. `PolymarketUnavailable` is raised.
    """
    try:
        window = positions_near(client, wallet, cutoff, "before", WINDOW_LIMIT)
    except ProtocolContractAddress:
        log.info("%s is a protocol contract address; dropped from the Scan", wallet)
        return None
    except NoPolymarketHistory:
        return RankedWallet(wallet, 0.0)
    except PolymarketBadRequest as error:
        log.warning("Polymarket refused %s (%s); kept as not fully read", wallet, error)
        return RankedWallet(wallet, 0.0, not_fully_read=True, refused=True)
    unread = window.not_fully_read()
    position_set = build_positions(
        window.activity, {m.condition_id: m for m in window.markets}, listed=window.positions, not_fully_read=unread
    )
    return RankedWallet(wallet, real_pnl(position_set), not_fully_read=bool(unread))


def run_funnel(client: FunnelClient, cutoff: date, size: int = DEFAULT_SIZE) -> ScanFunnel:
    """The whole funnel for one Cut-off Date and N (FR-16, AD-21): Market set, candidates, shortlist, top N."""
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise ValueError(f"the number of Wallets must be a whole number of 1 or more, not {size!r}")
    markets = choose_markets(client, cutoff)
    reads = [read_candidates(client, market) for market in markets]
    candidate_count, chosen = shortlist(markets, reads, size)
    ranked: list[RankedWallet] = []
    contracts: list[str] = []
    for candidate in chosen:
        result = rank_wallet(client, candidate.wallet, cutoff)
        if result is None:
            contracts.append(candidate.wallet)
        else:
            ranked.append(result)
    return ScanFunnel(
        cutoff=cutoff_at(cutoff),
        size=size,
        markets=markets,
        partial=tuple(read.condition_id for read in reads if not read.used),
        candidate_count=candidate_count,
        shortlist=chosen,
        contracts=tuple(contracts),
        ranked=funnel.top_n(ranked, size),
    )
