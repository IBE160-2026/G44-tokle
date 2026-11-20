"""The client interface every Wallet data source implements (AD-2, AD-13).

`PolymarketClient` (`data/polymarket.py`) and `OfflineClient` (`data/offline.py`) both offer these
three raw reads, and `data/window.positions_near` builds the Wallet window on them (AD-8), so
services never know which client they hold and offline data takes the live path.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol

from liquidoracle.records import ActivityRow, ListedPosition, Market, Read


class WalletClient(Protocol):
    def positions_list(
        self,
        wallet: str,
        status: str,
        *,
        sort_by: str | None = None,
        sort_direction: str | None = None,
        until: Callable[[tuple[ListedPosition, ...]], bool] | None = None,
    ) -> Read[ListedPosition]:
        """One positions list, CLOSED or OPEN, page by page; `until(page)` True stops it (AD-7, AD-10)."""
        ...

    def activity_rows(
        self,
        wallet: str,
        *,
        start: int,
        end: int | None = None,
        row_cap: int | None = None,
    ) -> Read[ActivityRow]:
        """The Wallet's activity rows from `start` to `end`, oldest first, at most `row_cap` (AD-7, AD-10)."""
        ...

    def markets(self, condition_ids: Iterable[str]) -> tuple[Market, ...]:
        """Gamma Market records for these ids, one each, in the order asked (AD-7, AD-10)."""
        ...
