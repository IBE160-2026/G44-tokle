"""The fetch pipeline: one Wallet's window from a client into the store, and its Skill Test (AD-8, AD-14, AD-19).

Offline and live runs take this same path; only the client and the database file differ (AD-13).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from liquidoracle.core.positions import build_positions
from liquidoracle.core.skilltest import skill_test
from liquidoracle.data.client import WalletClient
from liquidoracle.data.store import Snapshot, Store
from liquidoracle.data.window import WINDOW_LIMIT, positions_near
from liquidoracle.records import PositionSet, SkillTestResult


FRESH_FOR = 24 * 60 * 60  # [ASSUMPTION] AD-4: a stored snapshot under 24 hours old is used without a fetch


def fetch_wallet(
    client: WalletClient,
    store: Store,
    wallet: str,
    *,
    limit: int = WINDOW_LIMIT,
    cutoff: date | None = None,
    side: str | None = None,
) -> int:
    """Fetch one Wallet's window and save it as one complete snapshot; returns its `fetch_id` (AD-8, AD-19).

    With `cutoff` and `side` it is that part of the Cut-off Date (AD-7), stored under that key (AD-4).
    The Wallet's lock is held throughout, so a web thread and the worker never fetch the same
    Wallet at once. Everything is read before anything is written, so a Wallet the client does
    not have (`NotAvailableOffline`, FR-14) or a read Polymarket cuts short leaves no snapshot.
    """
    wallet = wallet.strip().lower()  # FR-1: addresses are lower case
    with store.wallet_lock(wallet):
        window = positions_near(client, wallet, cutoff, side, limit, stored_markets=store.resolved_markets)
        fetch_id = store.begin_snapshot(wallet, window_limit=window.limit, cutoff=window.cutoff, side=window.side)
        store.add_positions(fetch_id, window.positions)
        store.add_activity(fetch_id, window.activity)
        store.save_markets(window.markets)
        store.finish_snapshot(fetch_id, activity_read_until=window.activity_read_until, window_capped=window.capped)
    return fetch_id


@dataclass(frozen=True, slots=True)
class StoredResult:
    """A Skill Test result, when the snapshot it rests on was completed (epoch seconds), and what the honesty
    notes need from that snapshot: the Position builder's record and whether the window was capped (FR-11, AD-11)."""

    result: SkillTestResult
    stored_at: int
    positions: PositionSet
    capped: bool
    listed: int  # the window's positions-list rows: what the 2,000 cap counts (AD-8; Story 3.3 review)


def skill_result(store: Store, wallet: str, *, seed: int) -> SkillTestResult | None:
    """The Skill Test on the Wallet's latest complete snapshot, or None when none is stored."""
    stored = stored_result(store, wallet, seed=seed)
    return None if stored is None else stored.result


def stored_result(store: Store, wallet: str, *, seed: int) -> StoredResult | None:
    """The Skill Test on the Wallet's latest complete snapshot, with its time, or None when none is stored."""
    snapshot = store.latest_snapshot(wallet.strip().lower())
    return None if snapshot is None else result_of(snapshot, seed=seed)


def result_of(snapshot: Snapshot, *, seed: int) -> StoredResult:
    """The Skill Test on one stored snapshot, with the time it was completed and the Position set it ran on.

    The random unit is the Wallet's address (AD-15), the scope `lookup` (AD-22).
    """
    position_set = build_positions(
        snapshot.activity,
        {m.condition_id: m for m in snapshot.markets},
        listed=snapshot.positions,
        not_fully_read=snapshot.not_fully_read(),
    )
    result = skill_test(position_set, seed=seed, unit_id=snapshot.wallet)
    return StoredResult(result, snapshot.completed_at, position_set, snapshot.window_capped, len(snapshot.positions))
