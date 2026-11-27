"""The Watchlist of one finished Scan, and the Verdict page a Watchlist row opens (FR-16, UX-DR33, UX-DR34,
UX-DR37, AD-21, AD-22; Story 4.5).

The page reads the store only: nothing is fetched or written, and the Watchlist never leaves the app
(FR-16). The Watchlist's rows come from the Scan's stored `scan_whole` results. A Verdict opened from a
row is recomputed from the Scan's frozen snapshots through `services.scan.parts_position_set`, the same
builder the Scan used, with the Scan's Seed and as-of time, so it shows the same result as its row
(AD-22). Words and numbers come from `core/phrases` (AD-25); templates only place them.
"""

from __future__ import annotations

from dataclasses import dataclass

from liquidoracle.core import phrases
from liquidoracle.core.skilltest import skill_test
from liquidoracle.data.store import SCAN_WHOLE, Scan, ScanResult, ScanStep, Snapshot, Store
from liquidoracle.data.window import cutoff_day
from liquidoracle.records import HOLDUP_GROUPS, Verdict
from liquidoracle.services import scan as scan_module
from liquidoracle.services.fetch import StoredResult
from liquidoracle.services.lookup import FILLED_DOTS, WalletPage, short_address, verdict_page

EYEBROW = "Wallet scan"  # shown in capitals by the eyebrow style (UX-DR33)
TABLE_TITLE = "Wallets rated Skilled (high confidence)"  # UX-DR34
CAPTION = "Sorted by p-value, smallest first. A smaller p-value means stronger evidence of skill, not a bigger edge."
EMPTY = ("No Wallet in this Scan was rated ", Verdict.SKILLED.value, ".")  # the middle part in italics (SM-C2)
NOT_FULLY_READ = "Not fully read"  # EXPERIENCE.md *Wallet not fully read*
NOT_FULLY_READ_TIP = "Polymarket's data for this Wallet could not be read in full; the unread bets are left out."
ODDS_HEADER = "Odds (with no edge)"
TAB_WATCHLIST = "Watchlist"  # the Scan tabs (UX-DR33); Epic 6 adds Copy Test
TAB_HOLDUP = "Hold-up Test"
PAGE_WATCHLIST, PAGE_HOLDUP = "watchlist", "hold_up"  # the pages' names, which the web layer gives its routes
SUMMARY_LABELS = ("Wallets scanned", f"Rated {Verdict.SKILLED.value}", "Scan run")  # DESIGN.md Scan header
PARTIAL = "not used: partial"  # AD-9, EXPERIENCE.md *Market not used*
# AD-21, FR-16: the population tested, filled with the Scan's own numbers
POPULATION = "Markets resolved in the {days} days before the Cut-off Date, top {markets} by volume"


@dataclass(frozen=True, slots=True)
class PartialMarket:
    """A Market of the Scan's set whose holder lists could not be read in full (AD-9), named without a title."""

    short_id: str  # "0x1a2b…9f0e"
    details: str  # "$1,234,567 volume · resolved 12 June 2025"; no date when its record holds no resolution time


@dataclass(frozen=True, slots=True)
class ScanTab:
    """One Scan tab (UX-DR33): a plain link to one of the Scan's pages."""

    label: str
    page: str  # PAGE_WATCHLIST or PAGE_HOLDUP


@dataclass(frozen=True, slots=True)
class ScanHeader:
    """The Scan header, summary card and tabs shared by the Scan pages (UX-DR33, AD-21)."""

    scan_id: int
    cutoff: str  # "1 July 2025"
    title: str  # "Scan of 200 Wallets"
    lede: str  # "Cut-off Date 1 July 2025 · run 26 Nov 2026"
    population: str  # "Markets resolved in the 90 days before the Cut-off Date, top 100 by volume · 97 of 100 Markets used · Seed 44"
    shortlist: str  # "Shortlist of about 600 by a quick profit estimate · 4 Wallets not fully read"
    summary: tuple[tuple[str, str], ...]  # (label, figure) x 3
    partial_title: str  # "3 Markets not used: partial"; "" when every Market was used
    partial: tuple[PartialMarket, ...]
    eyebrow: str = EYEBROW
    # Watchlist, then Hold-up Test when the Scan has its stored Hold-up result (none before Story 5.1)
    tabs: tuple[ScanTab, ...] = ()


@dataclass(frozen=True, slots=True)
class WatchlistRow:
    """One Wallet on the Watchlist (UX-DR34)."""

    address: str
    short_address: str
    link_label: str  # "Open Verdict for Wallet 0x1a2b…9f0e"
    verdict: str
    filled_dots: int
    odds: str  # the FR-8 odds phrase, from phrases.odds
    bets: str  # "212"
    real_pnl: str  # "$40,180"
    not_fully_read: bool


@dataclass(frozen=True, slots=True)
class WatchlistView:
    header: ScanHeader
    title: str  # the tab title: "Watchlist · 1 Jul 2025 · LiquidOracle"
    luck: str  # the Minimum Luck Passes sentence; "" when no Wallet got a Verdict (Edvard, 2026-11-26)
    rows: tuple[WatchlistRow, ...]  # empty: the Watchlist is empty, a valid result (SM-C2)


@dataclass(frozen=True, slots=True)
class ScanVerdict:
    """A Verdict page opened from a Scan, with its back link's words (UX-DR37)."""

    page: WalletPage
    back: str  # "Back to Watchlist (Cut-off Date 1 July 2025)"; the template adds the arrow
    tag: tuple[str, str] | None  # ("Not fully read", its tooltip) when the Watchlist row is flagged (Story 4.5 review)


class Watchlists:
    """The Watchlist pages over one run's store (AD-13). Read-only."""

    def __init__(self, store: Store) -> None:
        self._store = store

    def view(self, scan_id: int) -> WatchlistView | None:
        """The Watchlist of a finished Scan, or None for an unknown or unfinished Scan (its results are never shown)."""
        scan = finished_scan(self._store, scan_id)
        if scan is None:
            return None
        whole = _whole_results(self._store.scan_results(scan_id))
        skilled = sorted(_skilled(whole), key=lambda r: (r.p_value, -r.real_pnl, r.wallet))
        with_verdict = sum(1 for r in whole if r.p_value is not None)  # Edvard, 2026-11-26: only these count
        day = cutoff_day(scan.cutoff)
        return WatchlistView(
            header=scan_header(self._store, scan, whole),
            title=f"{TAB_WATCHLIST} · {phrases.short_date(day)} · LiquidOracle",
            luck=phrases.luck_passes(with_verdict) if with_verdict else "",
            rows=tuple(_row(r) for r in skilled),
        )

    def verdict(self, scan_id: int, address: str) -> ScanVerdict | None:
        """The Verdict page of a Wallet of a finished Scan: its `scan_whole` result recomputed from the frozen
        snapshots (AD-19, AD-22). None when the Scan, the Wallet's result or a frozen snapshot is missing."""
        scan = finished_scan(self._store, scan_id)
        if scan is None:
            return None
        found = next((r for r in _whole_results(self._store.scan_results(scan_id)) if r.wallet == address), None)
        if found is None:
            return None
        parts: list[Snapshot] = []
        for fetch_id in (found.fetch_id, found.after_fetch_id):
            if fetch_id is None:
                continue
            snapshot = self._store.snapshot(fetch_id)
            if snapshot is None:
                return None
            parts.append(snapshot)
        stored = scan_whole_result(address, parts, scan=scan)
        cutoff = phrases.long_date(cutoff_day(scan.cutoff))
        # The row's flag also holds what the parts cannot show: a part Polymarket refused (Edvard, 2026-11-26).
        tag = (NOT_FULLY_READ, NOT_FULLY_READ_TIP) if found.not_fully_read else None
        return ScanVerdict(verdict_page(address, stored), f"Back to Watchlist (Cut-off Date {cutoff})", tag)


def finished_scan(store: Store, scan_id: int) -> Scan | None:
    """The Scan when it is finished, else None: an unfinished Scan's results are never shown (AD-5)."""
    scan = store.scan(scan_id)
    return scan if scan is not None and scan.step is ScanStep.DONE else None


def whole_results(store: Store, scan_id: int) -> list[ScanResult]:
    """The Scan's stored `scan_whole` results, the ones its header counts."""
    return _whole_results(store.scan_results(scan_id))


def scan_header(store: Store, scan: Scan, whole: list[ScanResult]) -> ScanHeader:
    """The header every page of a finished Scan shows (UX-DR33, AD-21), with the tabs the Scan has: the
    Hold-up Test tab only when its two group results are stored (Story 5.2)."""
    day = cutoff_day(scan.cutoff)
    cutoff = phrases.long_date(day)
    run = phrases.run_date(scan.as_of)
    markets = store.scan_markets(scan.scan_id)
    partial = [m for m in markets if m.state == "partial"]
    used = sum(1 for m in markets if m.state == "used")
    records = store.resolved_markets([m.condition_id for m in partial])
    shortlist = len(store.scan_wallets(scan.scan_id))
    unread = sum(1 for r in whole if r.not_fully_read)
    skilled = len(_skilled(whole))
    n = len(whole)
    tabs = [ScanTab(TAB_WATCHLIST, PAGE_WATCHLIST)]
    if len(store.group_results(scan.scan_id)) == len(HOLDUP_GROUPS):
        tabs.append(ScanTab(TAB_HOLDUP, PAGE_HOLDUP))
    return ScanHeader(
        scan_id=scan.scan_id,
        cutoff=cutoff,
        title=f"Scan of {phrases.count(n)} {_wallets(n)}",
        lede=f"Cut-off Date {cutoff} · run {run}",
        population=(
            POPULATION.format(days=scan_module.MARKET_DAYS, markets=scan_module.MARKET_COUNT)
            + f" · {phrases.of_total(used, len(markets))} Markets used · Seed {scan.seed}"
        ),
        shortlist=(
            f"Shortlist of about {phrases.count(shortlist)} by a quick profit estimate · "
            f"{phrases.count(unread)} {_wallets(unread)} not fully read"
        ),
        summary=tuple(zip(SUMMARY_LABELS, (phrases.count(n), phrases.count(skilled), run), strict=True)),
        partial_title=(
            f"{phrases.count(len(partial))} {'Market' if len(partial) == 1 else 'Markets'} {PARTIAL}"
            if partial else ""
        ),
        partial=tuple(
            PartialMarket(
                short_address(m.condition_id),
                _details(m.volume, records[m.condition_id].closed_time if m.condition_id in records else None),
            )
            for m in partial
        ),
        tabs=tuple(tabs),
    )


def scan_whole_result(address: str, parts: list[Snapshot], *, scan: Scan) -> StoredResult:
    """A Wallet's `scan_whole` result from its frozen parts, as `services.scan.scan_results` computed it
    (AD-22), with what the honesty notes need. "Data stored" is when the later part was completed."""
    cut = [scan_module.as_of_part(part, scan.as_of) for part in parts]
    position_set = scan_module.parts_position_set(cut)
    result = skill_test(position_set, seed=scan.seed, unit_id=address, scope=SCAN_WHOLE)
    return StoredResult(
        result,
        max((part.completed_at for part in parts), default=scan.as_of),
        position_set,
        any(part.window_capped for part in parts),
        sum(len(part.positions) for part in cut),
        cutoff=cutoff_day(scan.cutoff),
        sides=tuple(part.side for part in parts if part.side is not None),
    )


def watchlist_label(size: int, cutoff: str) -> str:
    """The Scan list's link name for a Watchlist size, unique per Cut-off Date (Story 4.5):
    "3 Wallets on the Watchlist (Cut-off Date 1 July 2025)". It starts with the number the link shows."""
    return f"{phrases.count(size)} {_wallets(size)} on the Watchlist (Cut-off Date {cutoff})"


def _whole_results(results: tuple[ScanResult, ...]) -> list[ScanResult]:
    return [r for r in results if r.scope == SCAN_WHOLE]


def _skilled(whole: list[ScanResult]) -> list[ScanResult]:
    """The results on the Watchlist: the one rule behind its rows and the header's count (FR-16)."""
    return [r for r in whole if r.verdict == Verdict.SKILLED.value and r.p_value is not None]


def _row(result: ScanResult) -> WatchlistRow:
    short = short_address(result.wallet)
    verdict = Verdict(result.verdict)
    dots = FILLED_DOTS[verdict]
    if result.p_value is None or dots is None:  # never: the Watchlist holds only Skilled results
        raise ValueError(f"{result.wallet} has no p-value to list")
    return WatchlistRow(
        address=result.wallet,
        short_address=short,
        link_label=f"Open Verdict for Wallet {short}",
        verdict=verdict.value,
        filled_dots=dots,
        odds=phrases.odds(result.p_value),
        bets=phrases.count(result.tested_count),
        real_pnl=phrases.money(result.real_pnl),
        not_fully_read=result.not_fully_read,
    )


def _wallets(n: int) -> str:
    return "Wallet" if n == 1 else "Wallets"


def _details(volume: float, closed_time: int | None) -> str:
    """A partial Market's volume and resolution day (Edvard, 2026-11-26: no title is stored). The day is its UTC
    day, counted from 1970 by `cutoff_day`, since Windows refuses `fromtimestamp` before 1970."""
    text = f"{phrases.money(volume)} volume"
    return text if closed_time is None else f"{text} · resolved {phrases.long_date(cutoff_day(closed_time))}"
