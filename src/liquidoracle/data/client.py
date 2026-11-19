"""The client interface every Wallet data source implements (AD-2).

`OfflineClient` (`data/offline.py`) implements it now; the live Polymarket client implements the
same methods in Epic 2, so services never know which one they hold (AD-13). Story 2.2 replaces
`positions` with `positions_near(wallet, cutoff, side, limit)` in both.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from liquidoracle.records import ActivityRow, ListedPosition, Market


class WalletClient(Protocol):
    def positions(self, wallet: str) -> tuple[ListedPosition, ...]:
        """The Wallet's positions-list rows, CLOSED and OPEN (AD-10)."""
        ...

    def activity(self, wallet: str) -> tuple[ActivityRow, ...]:
        """The Wallet's activity rows, in order (AD-10)."""
        ...

    def markets(self, condition_ids: Iterable[str]) -> tuple[Market, ...]:
        """Gamma Market records for these ids, one each, in the order asked (AD-7, AD-10)."""
        ...
