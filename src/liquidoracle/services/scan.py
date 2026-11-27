"""The Scan: which Wallets it checks, picked only from what happened before the Cut-off Date, and their
Skill Tests, run as a resumable job (FR-16, AD-5, AD-19, AD-21, AD-22).

The funnel's four steps are plain functions: `choose_markets` (the Market set), `read_candidates`
(one Market's holders), `shortlist` (3 x N by the pre-filter) and `rank_wallet` (one Wallet's
before part). `run_funnel` runs them in memory and returns one `ScanFunnel` (Story 4.2).

`run_scan` (Story 4.3) runs the same steps as the job's phases, `ranking` then `skill_tests`,
storing each Market and each Wallet as it finishes, so Resume carries on from what is stored and
never reads a finished Market or Wallet again. Between two units of work (one Market, one Wallet)
it calls `between`, where the worker runs any waiting lookup (AD-5).
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from liquidoracle.core import funnel, phrases
from liquidoracle.core.positions import build_positions
from liquidoracle.core.skilltest import real_pnl, skill_test
from liquidoracle.data.client import FunnelClient, WalletClient
from liquidoracle.data.errors import NoPolymarketHistory, PolymarketBadRequest, ProtocolContractAddress
from liquidoracle.data.store import (
    AFTER,
    BEFORE,
    SCAN_BEFORE,
    SCAN_WHOLE,
    ScanResult,
    ScanStep,
    ScanWallet,
    Snapshot,
    Store,
    WalletOutcome,
)
from liquidoracle.data.window import WINDOW_LIMIT, cutoff_at, cutoff_day, positions_near
from liquidoracle.records import (
    ActivityRow,
    Candidate,
    FunnelMarket,
    ListedPosition,
    Market,
    MarketHolder,
    PositionSet,
    RankedWallet,
    ScanFunnel,
)
from liquidoracle.services.fetch import FRESH_FOR, fetch_wallet

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
    unused; when that is the CLOSED list, the OPEN list is not read. An OPEN row on a token that is
    not one of the Market's outcomes also leaves it unused: the estimate cannot price it (Story 4.3,
    deferred from 4.2). `PolymarketUnavailable` is raised and stops the Scan.
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
    tokens = set(market.market.token_ids)
    unknown = next((row.token_id for row in rows if row.status == "OPEN" and row.token_id not in tokens), None)
    if unknown is not None:
        log.warning("Market %s lists token %s, which is not one of its outcomes; the Market is not used",
                    condition_id, unknown)
        return MarketRead(condition_id, False, ())
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
    return _ranked(wallet, window)


class _Part(Protocol):
    """What ranking and the Skill Test read from a window or a stored snapshot: both have these."""

    @property
    def positions(self) -> tuple[ListedPosition, ...]: ...
    @property
    def activity(self) -> tuple[ActivityRow, ...]: ...
    @property
    def markets(self) -> tuple[Market, ...]: ...
    def not_fully_read(self) -> tuple[ListedPosition, ...]: ...


def _ranked(wallet: str, part: _Part) -> RankedWallet:
    """A Wallet's Real PnL on its before part, through the one builder and the Skill Test's own source (AD-10)."""
    unread = part.not_fully_read()
    position_set = build_positions(
        part.activity, {m.condition_id: m for m in part.markets}, listed=part.positions, not_fully_read=unread
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


# --- the Scan as a resumable job (Story 4.3) ------------------------------------------------------

RANKING, SKILL_TESTS = "ranking", "skill_tests"  # AD-5's first two phases; Epics 5 and 6 add Hold-up and Copy Test
STARTING = "Reading Markets"  # the progress message before the Market set is known (EXPERIENCE.md)
RANKING_MESSAGE = "Ranking"


def reading_markets(done: int, total: int) -> str:
    return f"Reading Markets: {phrases.of_total(done, total)}"


def fetching_wallets(done: int, total: int) -> str:
    return f"Fetching Wallets: {phrases.of_total(done, total)}"


def wallets_checked(done: int, total: int) -> str:
    return f"{phrases.of_total(done, total)} Wallets checked"


def run_scan(
    client: FunnelClient, store: Store, scan_id: int, *, job_id: int, between: Callable[[], None] = lambda: None
) -> None:
    """Run one Scan's job from wherever its stored state says it got to, until every phase is done (AD-5, FR-16).

    Each Market and each Wallet is stored as it finishes, so a stopped or interrupted Scan resumes
    without reading them again (AD-19). `between()` runs between two units of work. Errors propagate:
    the worker makes `PolymarketUnavailable` `stopped` and anything else `failed`.
    """
    scan = store.scan(scan_id)
    if scan is None:
        raise ValueError(f"no Scan {scan_id}")
    if scan.data_rebuilt:
        raise ValueError(f"Scan {scan_id}'s data was rebuilt; it cannot resume (AD-6)")
    day = cutoff_day(scan.cutoff)

    def progress(phase: str, done: int, total: int, message: str) -> None:
        store.update_progress(job_id, phase=phase, done=done, total=total, message=message)

    if scan.step is ScanStep.CREATED:
        progress(RANKING, 0, 0, STARTING)
        store.set_scan_markets(scan_id, choose_markets(client, day))
        between()
    _read_markets(client, store, scan_id, progress, between)
    if store.scan(scan_id).step is ScanStep.MARKETS:
        candidates = store.scan_candidates(scan_id)
        store.set_shortlist(
            scan_id, funnel.shortlist(candidates, SHORTLIST_FACTOR * scan.size), candidate_count=len(candidates)
        )
    _rank_wallets(client, store, scan_id, day, progress, between)
    if store.scan(scan_id).step is ScanStep.SHORTLISTED:
        progress(RANKING, 1, 1, RANKING_MESSAGE)
        ranked = [_ranked_row(w) for w in store.scan_wallets(scan_id) if w.outcome is not WalletOutcome.CONTRACT]
        store.mark_top(scan_id, [w.wallet for w in funnel.top_n(ranked, scan.size) if w.top])
    if store.scan(scan_id).step is ScanStep.RANKED:
        _test_top(client, store, scan_id, day, scan.seed, scan.as_of, progress, between)
        store.finish_scan(scan_id)


def _read_markets(
    client: FunnelClient, store: Store, scan_id: int, progress: Callable[..., None], between: Callable[[], None]
) -> None:
    """Read each unread Market of the set in volume order; its state and pre-filter terms are stored together."""
    markets = store.scan_markets(scan_id)
    records = store.resolved_markets([m.condition_id for m in markets])
    for i, market in enumerate(markets):
        if market.state is not None:
            continue
        progress(RANKING, i, len(markets), reading_markets(i, len(markets)))
        record = records[market.condition_id]
        read = read_candidates(client, FunnelMarket(record, market.volume))
        terms = funnel.market_terms(read.holders, record) if read.used else {}
        store.record_market_read(scan_id, market.seq, used=read.used, terms=terms)
        between()
    progress(RANKING, len(markets), len(markets), reading_markets(len(markets), len(markets)))


def _rank_wallets(
    client: FunnelClient,
    store: Store,
    scan_id: int,
    day: date,
    progress: Callable[..., None],
    between: Callable[[], None],
) -> None:
    """Read each unread shortlisted Wallet's before part, freeze it to the Scan and store how it ranked (AD-9, AD-19)."""
    wallets = store.scan_wallets(scan_id)
    for i, wallet in enumerate(wallets):
        if wallet.outcome is not None:
            continue
        progress(RANKING, i, len(wallets), fetching_wallets(i, len(wallets)))
        try:
            fetch_id = fetch_part(client, store, wallet.wallet, day, BEFORE)
        except ProtocolContractAddress:
            log.info("%s is a protocol contract address; dropped from the Scan", wallet.wallet)
            store.record_ranking(scan_id, wallet.wallet, outcome=WalletOutcome.CONTRACT, real_pnl=None,
                                 not_fully_read=False, fetch_id=None)
        except NoPolymarketHistory:
            store.record_ranking(scan_id, wallet.wallet, outcome=WalletOutcome.NO_HISTORY, real_pnl=0.0,
                                 not_fully_read=False, fetch_id=None)
        except PolymarketBadRequest as error:
            log.warning("Polymarket refused %s (%s); kept as not fully read", wallet.wallet, error)
            store.record_ranking(scan_id, wallet.wallet, outcome=WalletOutcome.REFUSED, real_pnl=0.0,
                                 not_fully_read=True, fetch_id=None)
        else:
            ranked = _ranked(wallet.wallet, _snapshot(store, fetch_id))
            store.record_ranking(scan_id, wallet.wallet, outcome=WalletOutcome.RANKED, real_pnl=ranked.real_pnl,
                                 not_fully_read=ranked.not_fully_read, fetch_id=fetch_id)
        between()
    progress(RANKING, len(wallets), len(wallets), fetching_wallets(len(wallets), len(wallets)))


def _test_top(
    client: FunnelClient,
    store: Store,
    scan_id: int,
    day: date,
    seed: int,
    as_of: int,
    progress: Callable[..., None],
    between: Callable[[], None],
) -> None:
    """Each top-N Wallet's after part, frozen to the Scan, and its `scan_before` and `scan_whole` results (AD-22)."""
    top = [w for w in store.scan_wallets(scan_id) if w.top]
    done = store.tested_wallets(scan_id)
    for i, wallet in enumerate(top):
        if wallet.wallet in done:
            continue
        progress(SKILL_TESTS, i, len(top), wallets_checked(i, len(top)))
        before = None if wallet.before_fetch_id is None else _snapshot(store, wallet.before_fetch_id)
        after = None
        refused_after = False
        if before is not None:  # a refused or empty Wallet has nothing after the date either
            try:
                after = _snapshot(store, fetch_part(client, store, wallet.wallet, day, AFTER))
            except PolymarketBadRequest as error:  # kept and flagged, like a refused before part (AD-9)
                log.warning("Polymarket refused the after part of %s (%s); kept as not fully read", wallet.wallet, error)
                refused_after = True
        store.save_results(
            scan_id, wallet.wallet, after_fetch_id=None if after is None else after.fetch_id,
            results=scan_results(wallet, before, after, seed=seed, as_of=as_of, refused_after=refused_after),
        )
        between()
    progress(SKILL_TESTS, len(top), len(top), wallets_checked(len(top), len(top)))


def fetch_part(client: WalletClient, store: Store, wallet: str, day: date, side: str) -> int:
    """The `fetch_id` of the Wallet's part of the Cut-off Date: a stored one under 24 hours old (AD-4), else fetched.

    The stored part must have the same Wallet, date and side (Edvard, 2026-11-26, Story 4.3).
    """
    fresh = store.serving_snapshot(
        wallet, window_limit=WINDOW_LIMIT, max_age=FRESH_FOR, cutoff=cutoff_at(day), side=side
    )
    if fresh is not None:
        return fresh.fetch_id
    return fetch_wallet(client, store, wallet, cutoff=day, side=side)


def scan_results(
    wallet: ScanWallet,
    before: Snapshot | None,
    after: Snapshot | None,
    *,
    seed: int,
    as_of: int | None = None,
    refused_after: bool = False,
) -> tuple[ScanResult, ScanResult]:
    """A top-N Wallet's two results (AD-22): `scan_before` on its before part, `scan_whole` on both parts together.

    The two parts never share a Market (AD-7), so their rows are simply put together. Markets
    resolved at or after the Scan's `as_of` time are left out (AD-19), so a Scan resumed days
    later tests what an uninterrupted run would have. The random unit is the Wallet's address
    (AD-15). A Wallet with no stored part is tested on nothing (Not enough data) and keeps its
    "not fully read" flag.
    """
    before_only = [] if before is None else [as_of_part(before, as_of)]
    both = before_only + ([] if after is None else [as_of_part(after, as_of)])
    results = []
    for scope, used in ((SCAN_BEFORE, before_only), (SCAN_WHOLE, both)):
        position_set = parts_position_set(used)
        result = skill_test(position_set, seed=seed, unit_id=wallet.wallet, scope=scope)
        unread = any(part.not_fully_read() for part in used)
        flagged = wallet.not_fully_read or unread or (scope == SCAN_WHOLE and refused_after)
        results.append(ScanResult(
            wallet.wallet, scope, result.verdict.value, result.p_value, result.tested_count, result.real_pnl, flagged,
            None if before is None else before.fetch_id,
            None if scope == SCAN_BEFORE or after is None else after.fetch_id,
        ))
    return results[0], results[1]


def parts_position_set(parts: Sequence[Snapshot]) -> PositionSet:
    """The Position set of a Wallet's parts taken together, already cut to the Scan's as-of time (AD-11, AD-22).

    The two parts never share a Market (AD-7), so their rows are simply put together. The Watchlist's
    Verdict page (Story 4.5) calls this too, so it tests exactly what `scan_results` tested.
    """
    return build_positions(
        tuple(row for part in parts for row in part.activity),
        {m.condition_id: m for part in parts for m in part.markets},
        listed=tuple(row for part in parts for row in part.positions),
        not_fully_read=tuple(row for part in parts for row in part.not_fully_read()),
    )


def as_of_part(part: Snapshot, as_of: int | None) -> Snapshot:
    """AD-19: the part without the Markets resolved at or after `as_of` (all of it when None), with their rows."""
    if as_of is None:
        return part
    late = {m.condition_id for m in part.markets if m.closed_time is None or m.closed_time >= as_of}
    if not late:
        return part
    return dataclasses.replace(
        part,
        positions=tuple(p for p in part.positions if p.condition_id not in late),
        activity=tuple(a for a in part.activity if a.condition_id not in late),
        markets=tuple(m for m in part.markets if m.condition_id not in late),
    )


def _ranked_row(wallet: ScanWallet) -> RankedWallet:
    return RankedWallet(
        wallet.wallet, wallet.real_pnl or 0.0, not_fully_read=wallet.not_fully_read,
        refused=wallet.outcome is WalletOutcome.REFUSED,
    )


def _snapshot(store: Store, fetch_id: int) -> Snapshot:
    snapshot = store.snapshot(fetch_id)
    if snapshot is None:
        raise ValueError(f"snapshot {fetch_id} of a Scan is missing")
    return snapshot
