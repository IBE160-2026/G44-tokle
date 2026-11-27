"""`OfflineClient`: the Sample Dataset served through the client interface (AD-13, AD-14, FR-14).

It reads the Sample Dataset's JSON files with `sample_json` and returns the same `records` types
the live client returns. Anything outside the Sample Dataset raises `NotAvailableOffline`. It
never opens a network connection.

It is also a `FunnelClient` (Story 4.6), so the Scan runs offline on the live path: the Market set
comes from the Sample Dataset's volume list (`funnel-markets.json`, the synthetic anchor Markets),
and a Market's holder lists are derived from the Sample Wallets' own rows, as Polymarket derives
them from the same trades (AD-9, AD-10, AD-14, AD-21).
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from liquidoracle.data import sample_json, synthetic
from liquidoracle.data.errors import NotAvailableOffline
from liquidoracle.data.polymarket import LIST_STATUSES, MARKET_ROW_CAP, PAGE_LIMIT
from liquidoracle.records import ActivityRow, FunnelMarket, ListedPosition, Market, MarketHolder, Read, SampleWallet

# Folders that hold Sample Wallet files, relative to the repository folder: the real Wallets
# (Story 2.6, written by `build-sample`) and the Synthetic Wallets.
REAL_DIR = Path("sample_data") / "real"
SAMPLE_DIRS = (REAL_DIR, synthetic.SMALL_DIR, synthetic.COIN_FLIPPER_DIR)
# Files next to the Wallets that are not Wallets: the Synthetic Wallets' hand answers, and the real
# Wallets' Cut-off Date and sources.
NOT_WALLET_FILES = frozenset({"expected.json", "dataset.json", synthetic.FUNNEL_FILE})
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


def sample_funnel(root: Path) -> Path:
    """The Sample Dataset's volume list under the repository folder `root` (Story 4.6)."""
    return root / synthetic.SMALL_DIR / synthetic.FUNNEL_FILE


@dataclass(frozen=True, slots=True)
class _Index:
    wallets: dict[str, Path]  # address -> file
    markets: dict[str, Path]  # condition_id -> the first file holding it
    holders: dict[str, list[Path]]  # condition_id -> every file holding it (a Market's holder lists)


class OfflineClient:
    """Serves the Wallets in `files`. Safe to share between threads.

    With `list_files`, a miss lists the files again and rebuilds the index when the list has
    changed, so Sample files written after the app started (by `load-sample`) are found (Story 1.7).
    """

    def __init__(
        self,
        files: Sequence[Path],
        *,
        list_files: Callable[[], Sequence[Path]] | None = None,
        funnel: Path | None = None,
    ) -> None:
        self._files = tuple(files)
        self._list_files = list_files
        self._funnel = funnel  # the volume list; None or a missing file: no Market set (Story 4.6)
        self._index: _Index | None = None
        self._cached: tuple[Path, SampleWallet, dict[str, Market]] | None = None
        self._lock = threading.Lock()
        self._memory: dict[str, SampleWallet] = {}
        self._memory_markets: dict[str, Market] = {}
        self._holder_rows: dict[str, tuple[MarketHolder, ...]] = {}

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
        """The real Sample Wallets' addresses, from the file names in `sample_data/real/` (UX-DR17).

        Read from the names alone, so the Lookup page never parses the other 1,005 files: an
        old coin-flipper file left from before a format change would otherwise break the page
        (review, Story 2.6). `build-sample` names each file after its Wallet's address.
        """
        files = self._list_files() if self._list_files is not None else self._files
        return tuple(
            path.stem for path in files
            if path.parent.name == REAL_DIR.name and path.parent.parent.name == REAL_DIR.parent.name
            and ADDRESS.fullmatch(path.stem)
        )

    def addresses(self) -> tuple[str, ...]:
        """Every Sample Wallet's address, in file order. Offline only: `load-sample`, the Sample list and an
        offline Scan's N, so files written since the start (a `load-sample` run) count too (Story 4.6 review)."""
        self._refresh()
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

    def funnel_markets(self, closed_from: int, closed_until: int, count: int) -> tuple[FunnelMarket, ...]:
        """Up to `count` resolved Markets of the volume list whose `closed_time` is in [closed_from, closed_until),
        the highest volume first, ties by condition id: the live client's rule (AD-7, AD-21)."""
        if count < 1:
            raise ValueError(f"count must be 1 or more, not {count}")
        if closed_from >= closed_until:
            raise ValueError("the window must end after it starts")
        volumes = self._volumes()
        found = [
            FunnelMarket(market, volumes[market.condition_id])
            for market in (self.markets(volumes) if volumes else ())
            if market.resolved and market.closed_time is not None and closed_from <= market.closed_time < closed_until
        ]
        found.sort(key=lambda entry: (-entry.volume, entry.market.condition_id))
        return tuple(found[:count])

    def market_holders(self, condition_id: str, status: str) -> Read[MarketHolder]:
        """One of a Market's positions lists, CLOSED or OPEN, oldest first by last event (AD-9).

        One row per Sample Wallet's positions-list row on that Market, its numbers derived from that
        Wallet's own trades (`holder_rows`). A list over `MARKET_ROW_CAP` rows is partial, as live.
        """
        if status not in LIST_STATUSES:
            raise ValueError(f"status must be CLOSED or OPEN, not {status!r}")
        rows = tuple(row for row in self._holders(condition_id) if row.status == status)
        if len(rows) >= MARKET_ROW_CAP:
            return Read(rows[:MARKET_ROW_CAP], False)
        return Read(rows, True)

    def _volumes(self) -> dict[str, float]:
        if self._funnel is None or not self._funnel.is_file():
            return {}
        return sample_json.read_funnel(self._funnel)

    def _holders(self, condition_id: str) -> tuple[MarketHolder, ...]:
        """Every Sample Wallet's holder rows on one Market, worked out once and kept (both lists use them).

        Files written since the start are looked for first (a `load-sample` run clears what was kept). Each
        holder's file is read and dropped in turn, so about 1,000 coin-flippers are never in memory at once.
        """
        self._refresh()
        with self._lock:
            kept = self._holder_rows.get(condition_id)
        if kept is not None:
            return kept
        keyed = [
            item
            for wallet in self._memory.values() if any(m.condition_id == condition_id for m in wallet.markets)
            for item in holder_rows(wallet, condition_id)
        ]
        for path in self._get_index().holders.get(condition_id, ()):
            keyed.extend(holder_rows(sample_json.read_wallet(path), condition_id))
        keyed.sort(key=lambda item: (item[1], item[0].wallet, item[0].token_id))
        rows = tuple(row for row, _ in keyed)
        with self._lock:
            self._holder_rows[condition_id] = rows
        return rows

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
                self._holder_rows.clear()
            return True

    def _get_index(self) -> _Index:
        with self._lock:
            if self._index is None:
                self._index = _build_index(self._files)
            return self._index


def holder_rows(wallet: SampleWallet, condition_id: str) -> list[tuple[MarketHolder, int]]:
    """The Wallet's rows in one Market's holder lists, each with its last event time (AD-9, AD-21).

    Derived from the Wallet's own trades: `avg_price` = cash paid / shares bought; a CLOSED row's
    `realized_pnl` = sells - avg x shares sold, plus (outcome price - avg) x shares held when the held
    shares were redeemed; an OPEN row's `current_size` = shares held. Only the Scan's pre-filter reads
    these numbers, never a Position (AD-10).

    Only TRADE rows count, enough for the Synthetic Wallets; a Wallet that got tokens by a split, merge or
    conversion gets wrong numbers here. Story 4.7 must check this before real Wallets are holders.
    """
    market = next((m for m in wallet.markets if m.condition_id == condition_id), None)
    rows = []
    for listed in wallet.positions:
        if listed.condition_id != condition_id:
            continue
        trades = [a for a in wallet.activity if a.type == "TRADE" and a.token_id == listed.token_id]
        bought = sum(a.size for a in trades if a.side == "BUY")
        cost = sum(a.usdc_size for a in trades if a.side == "BUY")
        sold = sum(a.size for a in trades if a.side == "SELL")
        proceeds = sum(a.usdc_size for a in trades if a.side == "SELL")
        avg = cost / bought if bought > 0 else 0.0
        held = max(bought - sold, 0.0)
        realized = proceeds - avg * sold
        current = 0.0
        if listed.status == "OPEN":
            current = held
        elif held > 0 and market is not None and listed.token_id in market.token_ids:
            realized += held * (market.outcome_prices[market.token_ids.index(listed.token_id)] - avg)
        rows.append((
            MarketHolder(wallet.address, listed.token_id, listed.status, round(realized, 6), round(current, 6), round(avg, 6)),
            listed.last_event_at,
        ))
    return rows


def _build_index(files: Sequence[Path]) -> _Index:
    wallets: dict[str, Path] = {}
    markets: dict[str, Path] = {}
    holders: dict[str, list[Path]] = {}
    for path in files:
        address, condition_ids = sample_json.read_ids(path)
        if not ADDRESS.fullmatch(address):
            raise ValueError(f"{path}: the address {address!r} is not 0x and 40 lower-case hex characters (FR-1)")
        if address in wallets:
            raise ValueError(f"{path}: the address {address} is also in {wallets[address]}")
        wallets[address] = path
        for condition_id in condition_ids:
            markets.setdefault(condition_id, path)
            holders.setdefault(condition_id, []).append(path)
    return _Index(wallets, markets, holders)
