"""The Wallet lookup: an address in, the Verdict card's words out (FR-1, FR-2, FR-8, FR-10, FR-14; Stories 1.7, 2.5).

Pages call this module only. It reads the Wallet's stored snapshot, runs the Skill Test, and turns
the result into finished text from `core/phrases` (AD-25), so the templates never format a number.
Typed errors from `data` become the messages in EXPERIENCE.md (Conventions › Errors); a database
that cannot be read is left to the pages' error page.

Offline and live runs differ only in what is handed in at startup (AD-13). Offline Mode has the
`OfflineClient`, which a page may ask directly (it reads local files), and no job queue: its stored
snapshots never go stale. A live run has a job queue and no client here: only the worker talks to
Polymarket (AD-5), and a page serves a fresh snapshot (AD-4) or queues a lookup job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from liquidoracle.core import phrases
from liquidoracle.core.skilltest import SIMULATIONS
from liquidoracle.data import synthetic
from liquidoracle.data.errors import NotAvailableOffline
from liquidoracle.data.offline import OfflineClient
from liquidoracle.data.store import NO_HISTORY, JobStatus, Store
from liquidoracle.data.window import WINDOW_LIMIT
from liquidoracle.records import Verdict
from liquidoracle.services.chart import LuckChart, luck_chart
from liquidoracle.services.fetch import FRESH_FOR, StoredResult, result_of, stored_result
from liquidoracle.services.honesty import HonestyNotes, honesty_notes
from liquidoracle.services.jobs import FETCHING, NO_HISTORY_MESSAGE, Jobs

ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")  # FR-1: 0x and 40 hex characters, any case

# [ASSUMPTION] Story 2.5 review: an outage or error page is shown again on reload for this many seconds after its
# job ended; after that, reloading it tries again ("Try again in a few minutes.").
RETRY_AFTER = 60

# Messages, word for word from EXPERIENCE.md (FR-1, FR-14) and Story 1.7's decisions (Edvard, 2026-11-20).
EMPTY_ADDRESS = "Enter a wallet address."
BAD_ADDRESS = "This is not a valid wallet address. It should start with 0x and have 42 characters."
NOT_AVAILABLE_OFFLINE = "Not available offline. In Offline Mode only the Sample Wallets below can be checked."
LOOKUP_LEDE = (  # UX-DR16, from mockups/lookup.html; the count comes from the Skill Test (AD-25)
    f"Paste a Polymarket Wallet address. LiquidOracle replays its resolved bets {phrases.count(SIMULATIONS)} "
    "times to see how often luck alone would do as well."
)
# The fetching state (UX-DR22, EXPERIENCE.md); defined once in services/jobs.py, where the progress JSON uses it.
FETCHING_LINE = FETCHING
# The no-history hint: PRD FR-1's sentence (Story 2.5).
PROFILE_HINT = (
    "Use the address shown on the Polymarket profile page. An address from a wallet app may show no history."
)

# The Sample Wallets list (UX-DR17): the stage 1 Synthetic Wallets, and one coin-flipper for all 1,000
# (Edvard, 2026-11-20). The Real Wallets group (Story 2.6) lists every real Wallet's short address.
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
    QUEUED = "queued"  # a lookup job was queued or joined: open the page of that job
    FETCHING = "fetching"  # UX-DR22
    NO_HISTORY = "no history"  # UX-DR23
    UNAVAILABLE = "unavailable"  # UX-DR23: Polymarket did not answer
    FAILED = "failed"  # an unexpected error, logged by the worker


@dataclass(frozen=True, slots=True)
class Notice:
    """A message page or box: a heading and a sentence, with an optional command shown as code."""

    heading: str
    before: str
    command: str = ""
    after: str = ""
    error: bool = False  # shown in the error style and read with a hidden "Error:" (UX-DR13)
    hint: str = ""  # a second sentence under the first


NOT_LOADED = Notice(
    "Sample Dataset not loaded",
    "The Sample Dataset is not loaded yet. Run ",
    "uv run liquidoracle load-sample",
    " in the repository folder, then reload this page.",
)
NOT_OFFLINE = Notice("Not available offline", NOT_AVAILABLE_OFFLINE, error=True)
NO_HISTORY_NOTICE = Notice(  # UX-DR23, EXPERIENCE.md
    NO_HISTORY_MESSAGE, "No Polymarket history found for this address.", hint=PROFILE_HINT
)
UNAVAILABLE_HEADING = "Polymarket did not answer"  # UX-DR23
TRY_AGAIN = "Try again in a few minutes."  # UX-DR23: when no stored data of this view exists


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
    job_id: int | None = None  # QUEUED and FETCHING: the job the page follows
    stored_from: str | None = None  # UNAVAILABLE: "18 Nov 2026, 14:02" when a snapshot of this view exists
    chart: LuckChart | None = None  # VERDICT with a p-value: the chart card (FR-9); None for *Not enough data* (FR-10)
    notes: HonestyNotes | None = None  # VERDICT: the honesty notes and Exit PnL warning, every Verdict (FR-11)


@dataclass(frozen=True, slots=True)
class SampleItem:
    label: str
    address: str


@dataclass(frozen=True, slots=True)
class SampleList:
    items: tuple[SampleItem, ...]
    note: str  # "and 999 more coin-flippers, checked by address"
    real: tuple[SampleItem, ...] = ()  # the Real Wallets group: short addresses as labels (UX-DR17)


@dataclass(frozen=True, slots=True)
class Progress:
    """GET /jobs/<id>/progress (Consistency Conventions › Job progress): the only worker-page contract."""

    status: str
    phase: str
    done: int
    total: int
    message: str


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
    """One run's lookups, over what was picked at startup (AD-13). Safe to share between threads.

    `client` is Offline Mode's Sample client, which pages may ask directly; `jobs` is a live run's
    job queue. Exactly one of them is given.
    """

    def __init__(self, client: OfflineClient | None, store: Store, *, seed: int, jobs: Jobs | None = None) -> None:
        if (client is None) == (jobs is None):
            raise ValueError("a Lookup needs either the Offline Mode client or a live run's job queue")
        self._client = client
        self._store = store
        self._seed = seed
        self._jobs = jobs
        self._synthetic = synthetic.all_addresses()  # the coin-flippers' files exist only after load-sample

    def check(self, raw: str | None) -> tuple[str | None, str | None]:
        """The Lookup form (FR-1, FR-14): (address to open, None) or (None, the error under the field).

        Nothing is fetched. An address outside the Sample Dataset is refused here in Offline Mode.
        """
        address, error = clean_address(raw)
        if address is None:
            return None, error
        if self._client is not None and self._offline_outcome(address) is Outcome.NOT_AVAILABLE_OFFLINE:
            return None, NOT_AVAILABLE_OFFLINE
        return address, None

    def wallet_page(self, address: str, *, job: int | None = None, stored: bool = False) -> WalletPage:
        """The Verdict page for a valid lower-case address (FR-1, FR-2, FR-8, FR-10, FR-14).

        `job` is the lookup job the page follows; `stored` asks for the stored snapshot whatever its
        age (the outage page's "Show stored data from …"). Both are ignored in Offline Mode.
        """
        if self._jobs is None:
            return self._offline_page(address)
        if stored:
            snapshot = self._store.serving_snapshot(address, window_limit=WINDOW_LIMIT)
            if snapshot is not None:
                return self._verdict(address, result_of(snapshot, seed=self._seed))
        # The job is read before the snapshot: a job that ends in between then finds its snapshot,
        # instead of looking unfinished-and-unstored and queueing a second fetch (Story 2.5 review).
        followed = self._store.job(job) if job is not None else None
        fresh = self._store.serving_snapshot(address, window_limit=WINDOW_LIMIT, max_age=FRESH_FOR)
        if followed is not None and followed.wallet == address:
            if followed.status in (JobStatus.QUEUED, JobStatus.RUNNING):
                return self._page(Outcome.FETCHING, address, job_id=followed.id)
            if fresh is None and followed.status is JobStatus.DONE and followed.result == NO_HISTORY:
                return self._page(Outcome.NO_HISTORY, address, notice=NO_HISTORY_NOTICE)
            recent = followed.finished_at is not None and followed.finished_at > self._store.now() - RETRY_AFTER
            if fresh is None and recent and followed.status is JobStatus.STOPPED:
                when = self._store.snapshot_time(address, window_limit=WINDOW_LIMIT)
                return self._page(
                    Outcome.UNAVAILABLE, address, stored_from=None if when is None else phrases.stored_on(when)
                )
            if fresh is None and recent and followed.status is JobStatus.FAILED:
                return self._page(Outcome.FAILED, address)
            # done with a snapshot, interrupted, or stopped or failed a while ago: the usual answer below
            # (a fresh snapshot, or a new job: reloading an old outage page tries again)
        if fresh is not None:
            return self._verdict(address, result_of(fresh, seed=self._seed))
        return self._page(Outcome.QUEUED, address, job_id=self._jobs.queue_lookup(address))

    def progress(self, job_id: int) -> Progress | None:
        """A job's progress for `progress.js`, or None when there is no such job."""
        found = self._store.job(job_id)
        if found is None:
            return None
        return Progress(found.status.value, found.phase, found.done, found.total, found.message)

    def sample_list(self) -> SampleList | None:
        """The Sample Wallets list (UX-DR17), or None outside Offline Mode (no Sample client)."""
        if self._client is None:
            return None
        items = tuple(SampleItem(label, synthetic.address_of(name)) for name, label in SAMPLE_LIST)
        others = synthetic.COIN_FLIPPERS - 1
        real = tuple(SampleItem(short_address(a), a) for a in self._client.real_addresses())
        return SampleList(items, f"and {phrases.count(others)} more coin-flippers, checked by address", real)

    def not_loaded(self) -> Notice | None:
        """The *not loaded* box for the Lookup page: Offline Mode with nothing in the database."""
        if self._client is None:
            return None
        return NOT_LOADED if self._store.wallet_count() == 0 else None

    # --- helpers ---------------------------------------------------------------------------------

    def _offline_page(self, address: str) -> WalletPage:
        """Story 1.7's Offline Mode page: the stored snapshot, whatever its age, or why there is none."""
        found = stored_result(self._store, address, seed=self._seed)
        if found is not None:
            return self._verdict(address, found)
        # None here may mean a snapshot was finished just now, after the read above: reloading shows it.
        outcome = self._offline_outcome(address) or Outcome.NOT_LOADED
        notice = NOT_OFFLINE if outcome is Outcome.NOT_AVAILABLE_OFFLINE else NOT_LOADED
        return self._page(outcome, address, notice=notice)

    def _offline_outcome(self, address: str) -> Outcome | None:
        """Offline Mode: None if the address has a snapshot; otherwise why there is no Verdict to show."""
        if self._client is None:  # never reached: only Offline Mode asks this
            raise RuntimeError("only Offline Mode has a client to ask")
        if self._store.has_snapshot(address):
            return None
        if address in self._synthetic:
            return Outcome.NOT_LOADED  # a Synthetic Wallet whose file or snapshot load-sample has not written yet
        try:
            self._client.positions_list(address, "CLOSED")  # asks the Sample Dataset whether it has this Wallet
        except NotAvailableOffline:
            return Outcome.NOT_AVAILABLE_OFFLINE
        except (OSError, ValueError):  # a Sample file still being written by load-sample
            return Outcome.NOT_LOADED
        return Outcome.NOT_LOADED

    @staticmethod
    def _page(
        outcome: Outcome,
        address: str,
        *,
        card: VerdictCard | None = None,
        notice: Notice | None = None,
        job_id: int | None = None,
        stored_from: str | None = None,
        chart: LuckChart | None = None,
        notes: HonestyNotes | None = None,
    ) -> WalletPage:
        return WalletPage(outcome, address, short_address(address), card, notice, job_id, stored_from, chart, notes)

    def _verdict(self, address: str, stored: StoredResult) -> WalletPage:
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
        return self._page(
            Outcome.VERDICT, address, card=card, chart=luck_chart(result) if enough else None, notes=honesty_notes(stored)
        )

