"""`OfflineClient`: the Sample Dataset served through the client interface (AD-13, AD-14, FR-14).

It reads the Sample Dataset's JSON files with `sample_json` and returns the same `records` types
the live client returns. Anything outside the Sample Dataset raises `NotAvailableOffline`. It
never opens a network connection.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from liquidoracle.data import sample_json, synthetic
from liquidoracle.data.errors import NotAvailableOffline
from liquidoracle.data.polymarket import LIST_STATUSES, PAGE_LIMIT
from liquidoracle.records import ActivityRow, ListedPosition, Market, Read, SampleWallet

# Folders that hold Sample Wallet files, relative to the repository folder: the real Wallets
# (Story 2.6, written by `build-sample`) and the Synthetic Wallets.
REAL_DIR = Path("sample_data") / "real"
SAMPLE_DIRS = (REAL_DIR, synthetic.SMALL_DIR, synthetic.COIN_FLIPPER_DIR)
# Files next to the Wallets that are not Wallets: the Synthetic Wallets' hand answers, and the real
# Wallets' Cut-off Date and sources.
NOT_WALLET_FILES = frozenset({"expected.json", "dataset.json"})
ADDRESS = re.compile(r"0x[0-9a-f]{40}")  # FR-1: a proxy-wallet address, lower case


def sample_files(root: Path) -> list[Path]:
    """Every Sample Wallet file under the repository folder `root`, in a fixed order.

    A missing folder is skipped: before `load-sample` has run, the coin-flippers do not exist yet.
    """
    files: list[Path] = []
    for folder in SAMPLE_DIRS:
        if (root / folder).is_dir():
            files.extend(sorted(p for p in (root / folder).glob("*.json") if p.name not in NOT_WALLET_FILES))
    return files


@dataclass(frozen=True, slots=True)
class _Index:
    wallets: dict[str, Path]  # address -> file
    markets: dict[str, Path]  # condition_id -> file


class OfflineClient:
    """Serves the Wallets in `files`. Safe to share between threads.

    With `list_files`, a miss lists the files again and rebuilds the index when the list has
    changed, so Sample files written after the app started (by `load-sample`) are found (Story 1.7).
    """

    def __init__(self, files: Sequence[Path], *, list_files: Callable[[], Sequence[Path]] | None = None) -> None:
        self._files = tuple(files)
        self._list_files = list_files
        self._index: _Index | None = None
        self._cached: tuple[Path, SampleWallet, dict[str, Market]] | None = None
        self._lock = threading.Lock()
        self._memory: dict[str, SampleWallet] = {}
        self._memory_markets: dict[str, Market] = {}

    @classmethod
    def in_memory(cls, wallets: Sequence[SampleWallet], markets: Iterable[Market] = ()) -> OfflineClient:
        """Serves Wallets already in memory and these Markets, no files (the build-sample script, Story 2.6)."""
        client = cls(())
        client._memory = {wallet.address: wallet for wallet in wallets}
        client._memory_markets = {market.condition_id: market for market in markets}
        for wallet in wallets:
            client._memory_markets.update((market.condition_id, market) for market in wallet.markets)
        return client

    def real_addresses(self) -> tuple[str, ...]:
        """The real Sample Wallets' addresses (files in `sample_data/real/`), in file order (UX-DR17)."""
        return tuple(a for a, path in self._get_index().wallets.items() if path.parent.name == REAL_DIR.name)

    def addresses(self) -> tuple[str, ...]:
        """Every Sample Wallet's address, in file order. Offline only: `load-sample` and the Sample list."""
        return tuple(self._memory) + tuple(self._get_index().wallets)

    def positions_list(
        self,
        wallet: str,
        status: str,
        *,
        sort_by: str | None = None,
        sort_direction: str | None = None,
        until: Callable[[tuple[ListedPosition, ...]], bool] | None = None,
    ) -> Read[ListedPosition]:
        """One positions list, served in pages of the live size so `until` stops at the same page (AD-7, AD-13).

        `sort_by="TIMESTAMP"` orders by `last_event_at`, as the live list does; ties keep file order.
        """
        if status not in LIST_STATUSES:
            raise ValueError(f"status must be CLOSED or OPEN, not {status!r}")
        rows = [row for row in self._wallet(wallet).positions if row.status == status]
        if sort_by == "TIMESTAMP":
            rows.sort(key=lambda row: row.last_event_at, reverse=sort_direction == "DESC")
        elif sort_by is not None:
            raise ValueError(f"OfflineClient sorts only by TIMESTAMP, not {sort_by!r}")
        read: list[ListedPosition] = []
        for i in range(0, len(rows), PAGE_LIMIT):
            page = tuple(rows[i : i + PAGE_LIMIT])
            read.extend(page)
            if until is not None and i + PAGE_LIMIT < len(rows) and until(page):
                break
        return Read(tuple(read), True)

    def activity_rows(
        self,
        wallet: str,
        *,
        start: int,
        end: int | None = None,
        row_cap: int | None = None,
    ) -> Read[ActivityRow]:
        """The Wallet's activity rows from `start` to `end` (both included), oldest first, at most `row_cap`.

        Rows with the same time keep their file order; identical rows stay separate fills.

        A real Wallet's file says where its capture stopped (Story 2.6). A read starting before
        `activity_from` is cut short at once, with no rows, since an oldest-first read cannot skip
        the missing start; a read reaching the second `activity_until` is cut short there. So the
        window's normal "not fully read" rule applies, as for a live read cut short (AD-7).
        """
        if row_cap is not None and row_cap < 1:  # as the live client (AD-13)
            raise ValueError(f"row_cap must be 1 or more, not {row_cap}")
        sample = self._wallet(wallet)
        if sample.activity_from is not None and start < sample.activity_from:
            return Read((), False)
        cut = sample.activity_until is not None and (end is None or end >= sample.activity_until)
        last = sample.activity_until if cut else end
        rows = sorted(
            (row for row in sample.activity if row.timestamp >= start and (last is None or row.timestamp <= last)),
            key=lambda row: row.timestamp,
        )
        if row_cap is not None and len(rows) > row_cap:
            return Read(tuple(rows[:row_cap]), False)
        return Read(tuple(rows), not cut)

    def markets(self, condition_ids: Iterable[str]) -> tuple[Market, ...]:
        """The Markets asked for, each once, in the order asked.

        The file read last (the Wallet being fetched) is asked first, then each other file once:
        real Wallets share Markets, and reading files in turn per Market re-read 10 MB files
        thousands of times (found in Story 2.6; Synthetic Wallets never share a Market).
        """
        wanted = list(dict.fromkeys(condition_ids))
        found = {c: self._memory_markets[c] for c in wanted if c in self._memory_markets}
        with self._lock:
            cached = self._cached
        if cached is not None:
            found.update((c, cached[2][c]) for c in wanted if c not in found and c in cached[2])
        index = self._get_index()
        by_file: dict[Path, list[str]] = {}
        for condition_id in wanted:
            if condition_id in found:
                continue
            path = index.markets.get(condition_id)
            if path is None and self._refresh():
                index = self._get_index()
                path = index.markets.get(condition_id)
            if path is None:
                raise NotAvailableOffline(f"Market {condition_id} is not in the Sample Dataset")
            by_file.setdefault(path, []).append(condition_id)
        for path, ids in by_file.items():
            markets = self._read(path)[1]
            found.update((c, markets[c]) for c in ids)
        return tuple(found[c] for c in wanted)

    def _wallet(self, wallet: str) -> SampleWallet:
        address = wallet.strip().lower()
        if address in self._memory:
            return self._memory[address]
        path = self._get_index().wallets.get(address)
        if path is None and self._refresh():
            path = self._get_index().wallets.get(address)
        if path is None:
            raise NotAvailableOffline(f"Wallet {wallet} is not in the Sample Dataset")
        return self._read(path)[0]

    def _read(self, path: Path) -> tuple[SampleWallet, dict[str, Market]]:
        """Read one file, keeping the last one: a fetch asks for one Wallet's lists in a row."""
        with self._lock:
            if self._cached is None or self._cached[0] != path:
                wallet = sample_json.read_wallet(path)
                self._cached = (path, wallet, {m.condition_id: m for m in wallet.markets})
            return self._cached[1], self._cached[2]

    def _refresh(self) -> bool:
        """On a miss: list the files again and drop the index if the list changed. True when it is worth
        looking again, also when another thread has just swapped in the new list (review, Story 1.7)."""
        if self._list_files is None:
            return False
        files = tuple(self._list_files())
        with self._lock:
            if files != self._files:
                self._files = files
                self._index = None
            return True

    def _get_index(self) -> _Index:
        with self._lock:
            if self._index is None:
                self._index = _build_index(self._files)
            return self._index


def _build_index(files: Sequence[Path]) -> _Index:
    wallets: dict[str, Path] = {}
    markets: dict[str, Path] = {}
    for path in files:
        address, condition_ids = sample_json.read_ids(path)
        if not ADDRESS.fullmatch(address):
            raise ValueError(f"{path}: the address {address!r} is not 0x and 40 lower-case hex characters (FR-1)")
        if address in wallets:
            raise ValueError(f"{path}: the address {address} is also in {wallets[address]}")
        wallets[address] = path
        for condition_id in condition_ids:
            markets.setdefault(condition_id, path)
    return _Index(wallets, markets)
