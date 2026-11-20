"""The Wallet lookup: an address in, the Verdict card's words out (FR-1, FR-2, FR-8, FR-10, FR-14; Story 1.7).

Pages call this module only. It reads the Wallet's latest stored snapshot, runs the Skill Test,
and turns the result into finished text from `core/phrases` (AD-25), so the templates never
format a number. Typed errors from `data` become the messages in EXPERIENCE.md (Conventions ›
Errors); a database that cannot be read is left to the pages' error page. Offline and live runs differ only in the client handed in at startup (AD-13): Offline
Mode has the `OfflineClient`; a live run has none until Story 2.1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from liquidoracle.core import phrases
from liquidoracle.core.skilltest import SIMULATIONS
from liquidoracle.data import synthetic
from liquidoracle.data.client import WalletClient
from liquidoracle.data.errors import NotAvailableOffline
from liquidoracle.data.store import Store
from liquidoracle.records import Verdict
from liquidoracle.services.fetch import stored_result

ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")  # FR-1: 0x and 40 hex characters, any case

# Messages, word for word from EXPERIENCE.md (FR-1, FR-14) and Story 1.7's decisions (Edvard, 2026-11-20).
EMPTY_ADDRESS = "Enter a wallet address."
BAD_ADDRESS = "This is not a valid wallet address. It should start with 0x and have 42 characters."
NOT_AVAILABLE_OFFLINE = "Not available offline. In Offline Mode only the Sample Wallets below can be checked."
LOOKUP_LEDE = (  # UX-DR16, from mockups/lookup.html; the count comes from the Skill Test (AD-25)
    f"Paste a Polymarket Wallet address. LiquidOracle replays its resolved bets {phrases.count(SIMULATIONS)} "
    "times to see how often luck alone would do as well."
)

# The Sample Wallets list (UX-DR17): the stage 1 Synthetic Wallets, and one coin-flipper for all 1,000
# (Edvard, 2026-11-20). The Real Wallets group arrives with Story 2.6.
SAMPLE_LIST = (
    ("sharp-trader", "Sharp trader"),
    (synthetic.coin_flipper_name(0), "Coin-flipper"),
    ("favourite-buyer", "Favourite buyer"),
    ("stop-loss-trader", "Stop-loss trader"),
    ("thin-wallet", "Thin wallet"),
    ("hand-check", "Hand-check wallet"),
)

# How many dots the Verdict hero fills (UX-DR20); None draws the dashed box with no dots.
FILLED_DOTS = {
    Verdict.SKILLED: 3,
    Verdict.LIKELY_SKILLED: 2,
    Verdict.NO_EVIDENCE: 0,
    Verdict.NOT_ENOUGH_DATA: None,
}


class Outcome(StrEnum):
    VERDICT = "verdict"
    NOT_AVAILABLE_OFFLINE = "not available offline"
    NOT_LOADED = "not loaded"
    LIVE_NOT_BUILT = "live not built"


@dataclass(frozen=True, slots=True)
class Notice:
    """A message page or box: a heading and a sentence, with an optional command shown as code."""

    heading: str
    before: str
    command: str = ""
    after: str = ""
    error: bool = False  # shown in the error style and read with a hidden "Error:" (UX-DR13)


NOT_LOADED = Notice(
    "Sample Dataset not loaded",
    "The Sample Dataset is not loaded yet. Run ",
    "uv run liquidoracle load-sample",
    " in the repository folder, then reload this page.",
)
LIVE_NOT_BUILT = Notice(
    "Live lookups not built yet",
    "Live lookups are not built yet. Start the app with ",
    "--offline",
    " to check the Sample Wallets.",
)
NOT_OFFLINE = Notice("Not available offline", NOT_AVAILABLE_OFFLINE, error=True)


@dataclass(frozen=True, slots=True)
class VerdictCard:
    """The Verdict card's finished text (FR-8, FR-10, UX-DR20)."""

    verdict: str
    filled_dots: int | None  # None: *Not enough data*, dashed and without dots
    odds_line: str  # the odds sentence, or the *Not enough data* sentence
    bets: str  # "100"
    bets_word: str  # "resolved bets"
    real_pnl: str  # "$2,000"
    stored: str  # "Data stored 20 Nov 2026, 16:08"


@dataclass(frozen=True, slots=True)
class WalletPage:
    outcome: Outcome
    address: str
    short_address: str
    card: VerdictCard | None = None
    notice: Notice | None = None


@dataclass(frozen=True, slots=True)
class SampleItem:
    label: str
    address: str


@dataclass(frozen=True, slots=True)
class SampleList:
    items: tuple[SampleItem, ...]
    note: str  # "and 999 more coin-flippers, checked by address"


def clean_address(raw: str | None) -> tuple[str | None, str | None]:
    """FR-1: (the address in lower case, None), or (None, the error sentence). Spaces around it are removed."""
    text = (raw or "").strip()
    if not text:
        return None, EMPTY_ADDRESS
    if not ADDRESS.fullmatch(text):
        return None, BAD_ADDRESS
    return text.lower(), None


def short_address(address: str) -> str:
    """UX-DR8: "0x7c3a…d3f5", for tab titles and headings."""
    return f"{address[:6]}…{address[-4:]}"


class Lookup:
    """One run's lookups, over the client and database picked at startup (AD-13). Safe to share between threads."""

    def __init__(self, client: WalletClient | None, store: Store, *, seed: int) -> None:
        self._client = client
        self._store = store
        self._seed = seed
        self._synthetic = synthetic.all_addresses()  # the coin-flippers' files exist only after load-sample

    def check(self, raw: str | None) -> tuple[str | None, str | None]:
        """The Lookup form (FR-1, FR-14): (address to open, None) or (None, the error under the field).

        Nothing is fetched. An address outside the Sample Dataset is refused here in Offline Mode.
        """
        address, error = clean_address(raw)
        if address is None:
            return None, error
        if self._outcome_without_snapshot(address) is Outcome.NOT_AVAILABLE_OFFLINE:
            return None, NOT_AVAILABLE_OFFLINE
        return address, None

    def wallet_page(self, address: str) -> WalletPage:
        """The Verdict page for a valid lower-case address (FR-8, FR-10, FR-14)."""
        stored = stored_result(self._store, address, seed=self._seed)
        if stored is None:
            # None here means a snapshot was finished just now, after the read above: reloading shows it.
            outcome = self._outcome_without_snapshot(address) or Outcome.NOT_LOADED
            notice = {
                Outcome.NOT_AVAILABLE_OFFLINE: NOT_OFFLINE,
                Outcome.LIVE_NOT_BUILT: LIVE_NOT_BUILT,
            }.get(outcome, NOT_LOADED)
            return WalletPage(outcome, address, short_address(address), notice=notice)
        result = stored.result
        enough = result.p_value is not None
        card = VerdictCard(
            verdict=result.verdict.value,
            filled_dots=FILLED_DOTS[result.verdict],
            odds_line=phrases.odds_sentence(result.p_value) if enough else phrases.not_enough_data(result.tested_count),
            bets=phrases.count(result.tested_count),
            bets_word=phrases.resolved_bets_word(result.tested_count),
            real_pnl=phrases.money(result.real_pnl),
            stored=phrases.stored_at(stored.stored_at),
        )
        return WalletPage(Outcome.VERDICT, address, short_address(address), card=card)

    def sample_list(self) -> SampleList | None:
        """The Sample Wallets list (UX-DR17), or None outside Offline Mode (no Sample client)."""
        if self._client is None:
            return None
        items = tuple(SampleItem(label, synthetic.address_of(name)) for name, label in SAMPLE_LIST)
        others = synthetic.COIN_FLIPPERS - 1
        return SampleList(items, f"and {phrases.count(others)} more coin-flippers, checked by address")

    def not_loaded(self) -> Notice | None:
        """The *not loaded* box for the Lookup page: Offline Mode with nothing in the database."""
        if self._client is None:
            return None
        return NOT_LOADED if self._store.wallet_count() == 0 else None

    def _outcome_without_snapshot(self, address: str) -> Outcome | None:
        """For an address: None if it has a snapshot; otherwise why there is no Verdict to show."""
        if self._store.has_snapshot(address):
            return None
        if self._client is None:
            return Outcome.LIVE_NOT_BUILT
        if address in self._synthetic:
            return Outcome.NOT_LOADED  # a Synthetic Wallet whose file or snapshot load-sample has not written yet
        try:
            self._client.positions(address)  # asks the Sample Dataset whether it has this Wallet
        except NotAvailableOffline:
            return Outcome.NOT_AVAILABLE_OFFLINE
        except (OSError, ValueError):  # a Sample file still being written by load-sample
            return Outcome.NOT_LOADED
        return Outcome.NOT_LOADED
