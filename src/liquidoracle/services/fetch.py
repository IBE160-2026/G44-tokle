"""The fetch pipeline: one Wallet from a client into the store, and its Skill Test (AD-14, AD-19).

Offline and live runs take this same path; only the client and the database file differ (AD-13).
"""

from __future__ import annotations

from dataclasses import dataclass

from liquidoracle.core.positions import build_positions
from liquidoracle.core.skilltest import skill_test
from liquidoracle.data.client import WalletClient
from liquidoracle.data.store import Store
from liquidoracle.records import SkillTestResult


def fetch_wallet(client: WalletClient, store: Store, wallet: str) -> int:
    """Fetch one Wallet and save it as one complete snapshot; returns its `fetch_id`.

    Everything is read from the client before anything is written, so a Wallet the client does
    not have (`NotAvailableOffline`, FR-14) leaves no snapshot behind.
    """
    wallet = wallet.strip().lower()  # FR-1: addresses are lower case
    positions = client.positions(wallet)
    activity = client.activity(wallet)
    condition_ids = sorted({row.condition_id for row in positions} | {row.condition_id for row in activity})
    markets = client.markets(condition_ids)

    fetch_id = store.begin_snapshot(wallet)
    store.add_positions(fetch_id, positions)
    store.add_activity(fetch_id, activity)
    store.save_markets(markets)
    store.finish_snapshot(fetch_id)
    return fetch_id


@dataclass(frozen=True, slots=True)
class StoredResult:
    """A Skill Test result and when the snapshot it rests on was completed (epoch seconds)."""

    result: SkillTestResult
    stored_at: int


def skill_result(store: Store, wallet: str, *, seed: int) -> SkillTestResult | None:
    """The Skill Test on the Wallet's latest complete snapshot, or None when none is stored."""
    stored = stored_result(store, wallet, seed=seed)
    return None if stored is None else stored.result


def stored_result(store: Store, wallet: str, *, seed: int) -> StoredResult | None:
    """The Skill Test on the Wallet's latest complete snapshot, with its time, or None when none is stored.

    The random unit is the Wallet's address (AD-15), the scope `lookup` (AD-22).
    """
    snapshot = store.latest_snapshot(wallet.strip().lower())
    if snapshot is None:
        return None
    position_set = build_positions(snapshot.activity, {m.condition_id: m for m in snapshot.markets})
    return StoredResult(skill_test(position_set, seed=seed, unit_id=snapshot.wallet), snapshot.completed_at)
