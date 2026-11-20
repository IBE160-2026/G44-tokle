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
from liquidoracle.records import ActivityRow, ListedPosition, Market, SampleWallet

# Folders that hold Sample Wallet files, relative to the repository folder. Story 2.6 adds the real Wallets.
SAMPLE_DIRS = (synthetic.SMALL_DIR, synthetic.COIN_FLIPPER_DIR)
NOT_WALLET_FILES = frozenset({"expected.json"})  # the hand answers next to the Synthetic Wallets
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

    def addresses(self) -> tuple[str, ...]:
        """Every Sample Wallet's address, in file order. Offline only: `load-sample` and the Sample list."""
        return tuple(self._get_index().wallets)

    def positions(self, wallet: str) -> tuple[ListedPosition, ...]:
        return self._wallet(wallet).positions

    def activity(self, wallet: str) -> tuple[ActivityRow, ...]:
        return self._wallet(wallet).activity

    def markets(self, condition_ids: Iterable[str]) -> tuple[Market, ...]:
        index = self._get_index()
        found: list[Market] = []
        for condition_id in dict.fromkeys(condition_ids):  # each id once, in the order asked
            path = index.markets.get(condition_id)
            if path is None and self._refresh():
                index = self._get_index()
                path = index.markets.get(condition_id)
            if path is None:
                raise NotAvailableOffline(f"Market {condition_id} is not in the Sample Dataset")
            found.append(self._read(path)[1][condition_id])
        return tuple(found)

    def _wallet(self, wallet: str) -> SampleWallet:
        address = wallet.strip().lower()
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
