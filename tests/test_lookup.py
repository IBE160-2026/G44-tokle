"""The lookup service: an address in, the Verdict card's words out (FR-1, FR-8, FR-10, FR-14, AD-13, AD-25; Story 1.7).

Story 2.5's live lookups (jobs, freshness, outage) are tested in `test_live_lookup.py`.

Runs over a repository-like folder with the committed Synthetic Wallets and 3 coin-flippers,
loaded through the same pipeline `load-sample` uses, with sockets blocked.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from liquidoracle.core import phrases
from liquidoracle.data import synthetic
from liquidoracle.data.offline import OfflineClient, sample_files
from liquidoracle.data.store import OFFLINE_DB, Store
from liquidoracle.services import lookup as lookup_module
from liquidoracle.services.fetch import fetch_wallet
from liquidoracle.services.jobs import Jobs
from liquidoracle.services.lookup import (
    BAD_ADDRESS,
    EMPTY_ADDRESS,
    NOT_AVAILABLE_OFFLINE,
    NOT_LOADED,
    Lookup,
    Outcome,
    clean_address,
    short_address,
)

SEED = 44
UNKNOWN = "0x" + "0" * 40
SHARP = synthetic.address_of("sharp-trader")
THIN = synthetic.address_of("thin-wallet")
HAND_CHECK = synthetic.address_of("hand-check")
COIN_FLIPPER = synthetic.address_of(synthetic.coin_flipper_name(0))


def repository(root: Path, coin_flippers: int = 3) -> Path:
    synthetic.write_small(root)
    synthetic.write_coin_flippers(root, coin_flippers)
    return root


@pytest.fixture(scope="module")
def sample_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return repository(tmp_path_factory.mktemp("repo"))


@pytest.fixture(scope="module")
def offline(sample_root: Path) -> Iterator[Lookup]:
    """Offline Mode with every Sample Wallet loaded, as after `load-sample` (FR-14)."""
    client = OfflineClient(sample_files(sample_root))
    store = Store(sample_root / OFFLINE_DB)
    for address in client.addresses():
        fetch_wallet(client, store, address)
    yield Lookup(client, store, seed=SEED)
    store.close()


@pytest.fixture
def empty(sample_root: Path, tmp_path: Path) -> Iterator[Lookup]:
    """Offline Mode before `load-sample`: the Sample files exist, offline.db does not yet."""
    path = tmp_path / OFFLINE_DB
    assert not path.exists()
    store = Store(path)
    yield Lookup(OfflineClient(sample_files(sample_root)), store, seed=SEED)
    store.close()


@pytest.fixture
def live(tmp_path: Path) -> Iterator[Lookup]:
    """A live run (AD-13): a job queue, and no client the pages may ask (Story 2.5)."""
    store = Store(tmp_path / "live.db")
    yield Lookup(None, store, seed=SEED, jobs=Jobs(store))
    store.close()


# --- the address field (FR-1) ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, (None, EMPTY_ADDRESS)),
        ("", (None, EMPTY_ADDRESS)),
        ("   ", (None, EMPTY_ADDRESS)),
        ("abc", (None, BAD_ADDRESS)),
        ("0x" + "a" * 39, (None, BAD_ADDRESS)),  # 41 characters
        ("0x" + "a" * 41, (None, BAD_ADDRESS)),
        ("0x" + "g" * 40, (None, BAD_ADDRESS)),
        ("1x" + "a" * 40, (None, BAD_ADDRESS)),
        ("0x" + "ab" * 10 + " " + "ab" * 10, (None, BAD_ADDRESS)),  # a space inside
        ("  0x" + "AB" * 20 + "\t", ("0x" + "ab" * 20, None)),  # trimmed, lower case
    ],
)
def test_fr1_address_field(raw: str | None, expected: tuple[str | None, str | None]) -> None:
    """FR-1, UX-DR16: spaces around the address are removed; empty and malformed get their sentences."""
    assert clean_address(raw) == expected


def test_fr1_messages_are_word_for_word() -> None:
    """FR-1, FR-14, UX-DR16, UX-DR18: the three sentences as EXPERIENCE.md writes them."""
    assert EMPTY_ADDRESS == "Enter a wallet address."
    assert BAD_ADDRESS == "This is not a valid wallet address. It should start with 0x and have 42 characters."
    assert NOT_AVAILABLE_OFFLINE == "Not available offline. In Offline Mode only the Sample Wallets below can be checked."


def test_ux_dr8_short_address() -> None:
    """UX-DR8: tab titles show the first 6 and last 4 characters."""
    assert short_address("0x7c3a9e2b41d05f6a8c1e93b7d2f4a6c8e0b1d3f5") == "0x7c3a…d3f5"


def test_fr14_lookup_form_offline(offline: Lookup) -> None:
    """FR-14: offline, a Sample Wallet opens its page; any other valid address is refused on the Lookup page."""
    assert offline.check(" " + SHARP.upper().replace("0X", "0x") + " ") == (SHARP, None)
    assert offline.check(UNKNOWN) == (None, NOT_AVAILABLE_OFFLINE)
    assert offline.check("abc") == (None, BAD_ADDRESS)


def test_live_lookup_form_lets_a_valid_address_through(live: Lookup) -> None:
    """FR-1, AD-13: a live run checks only the format; the Verdict page does the fetching (Story 2.5)."""
    assert live.check(UNKNOWN) == (UNKNOWN, None)


# --- the Verdict card (FR-8, FR-10, UJ-3) ------------------------------------------------------


def test_fr8_sharp_trader_card(offline: Lookup) -> None:
    """FR-8, UJ-3: the sharp trader reads Skilled (high confidence), with three filled dots and phrases from core."""
    page = offline.wallet_page(SHARP)
    assert page.outcome is Outcome.VERDICT
    card = page.card
    assert card is not None
    assert (card.verdict, card.filled_dots) == ("Skilled (high confidence)", 3)
    assert card.odds_line.startswith("a trader with no edge would do this well ")
    assert (card.bets, card.bets_word, card.real_pnl) == ("100", "resolved bets", "$2,000")
    assert card.stored.startswith("Data stored ")


def test_fr8_coin_flipper_card(offline: Lookup) -> None:
    """FR-8, UJ-3: coin-flipper 0, the one in the Sample list, reads No evidence of skill with three empty dots."""
    card = offline.wallet_page(COIN_FLIPPER).card
    assert card is not None
    assert (card.verdict, card.filled_dots) == ("No evidence of skill", 0)


@pytest.mark.parametrize(("address", "count"), [(THIN, 29), (HAND_CHECK, 10)])
def test_fr10_not_enough_data_through_the_lookup(offline: Lookup, address: str, count: int) -> None:
    """FR-6, FR-10 (Edvard, 2026-10-24): the normal path never uses Story 1.4's bypass: 10 and 29 bets get
    *Not enough data*, no dots and no odds phrase, only the count sentence."""
    card = offline.wallet_page(address).card
    assert card is not None
    assert (card.verdict, card.filled_dots) == ("Not enough data", None)
    assert card.odds_line == phrases.not_enough_data(count)
    assert "time" not in card.odds_line
    if count == 29:
        assert card.odds_line == "29 resolved bets; at least 30 are needed for a Verdict (1 more)"


def test_ux_dr20_every_verdict_has_its_dots() -> None:
    """UX-DR20: ●●● Skilled, ●●○ Likely skilled, ○○○ No evidence, no dots for Not enough data."""
    assert {v.value: n for v, n in lookup_module.FILLED_DOTS.items()} == {
        "Skilled (high confidence)": 3,
        "Likely skilled": 2,
        "No evidence of skill": 0,
        "Not enough data": None,
    }


# --- no Verdict to show (FR-14; Edvard, 2026-11-20) --------------------------------------------


def test_fr14_unknown_address_offline(offline: Lookup) -> None:
    """FR-14: opened directly, an address outside the Sample Dataset shows Not available offline."""
    page = offline.wallet_page(UNKNOWN)
    assert (page.outcome, page.card) == (Outcome.NOT_AVAILABLE_OFFLINE, None)
    assert page.notice is not None and page.notice.error
    assert page.notice.before == NOT_AVAILABLE_OFFLINE


def test_sample_wallet_not_loaded_yet(empty: Lookup) -> None:
    """FR-14 (Edvard, 2026-11-20): before load-sample, a Sample Wallet is let through and its page says to run it;
    the Lookup page shows the same box. A missing offline.db is created empty, never an error."""
    assert empty.check(SHARP) == (SHARP, None)
    assert empty.check(UNKNOWN) == (None, NOT_AVAILABLE_OFFLINE)
    page = empty.wallet_page(SHARP)
    assert (page.outcome, page.notice) == (Outcome.NOT_LOADED, NOT_LOADED)
    assert empty.not_loaded() == NOT_LOADED
    assert NOT_LOADED.command == "uv run liquidoracle load-sample"


def test_not_loaded_box_goes_once_loaded(offline: Lookup) -> None:
    """FR-14 (Edvard, 2026-11-20): the box shows only while offline.db is empty."""
    assert offline.not_loaded() is None


def test_live_run_queues_a_lookup_and_shows_no_sample_list(live: Lookup) -> None:
    """AD-5, AD-13 (Story 2.5, closes the 2.1 issue): a live run queues a lookup job, and has no Sample
    list and no "not loaded" box."""
    page = live.wallet_page(SHARP)
    assert page.outcome is Outcome.QUEUED and page.job_id is not None
    assert live.sample_list() is None
    assert live.not_loaded() is None


def test_lookup_needs_exactly_one_of_client_and_jobs(tmp_path: Path) -> None:
    """AD-13: Offline Mode hands in its client, a live run its job queue; never both, never neither."""
    store = Store(tmp_path / "live.db")
    with pytest.raises(ValueError):
        Lookup(None, store, seed=SEED)
    with pytest.raises(ValueError):
        Lookup(OfflineClient(sample_files(tmp_path)), store, seed=SEED, jobs=Jobs(store))
    store.close()


# --- the Sample Wallets list (UX-DR17; Edvard, 2026-11-20) -------------------------------------


def test_ux_dr17_sample_list(offline: Lookup, sample_root: Path) -> None:
    """UX-DR17: the committed Synthetic Wallets (five of stage 1, three of stage 2 since Story 4.6) and one
    coin-flipper, each a Wallet the client has, then the note for the other 999 coin-flippers."""
    samples = offline.sample_list()
    assert samples is not None
    assert [item.label for item in samples.items] == [
        "Sharp trader", "Steady sharp", "Forecaster", "Speed trader", "Coin-flipper", "Favourite buyer",
        "Stop-loss trader", "Thin wallet", "Hand-check wallet",
    ]
    assert set(OfflineClient(sample_files(sample_root)).addresses()) >= {item.address for item in samples.items}
    assert {w.name for w in synthetic.small_wallets()} <= {name for name, _ in lookup_module.SAMPLE_LIST}
    assert samples.note == "and 999 more coin-flippers, checked by address"


def test_address_of_matches_the_generator() -> None:
    """AD-14: the list's addresses come from the generator's own rule, without generating the Wallets."""
    for wallet in [*synthetic.small_wallets(), synthetic.coin_flipper(0)]:
        assert synthetic.address_of(wallet.name) == wallet.address



# --- review fixes (Story 1.7) -----------------------------------------------------------------


def test_fr14_coin_flipper_before_load_sample_is_not_loaded(tmp_path: Path) -> None:
    """FR-14 (Edvard, 2026-11-20; review): on a fresh checkout the coin-flipper files do not exist yet,
    so the listed Coin-flipper reads "not loaded yet", never "Not available offline"."""
    synthetic.write_small(tmp_path)  # no coin-flippers written
    store = Store(tmp_path / OFFLINE_DB)
    fresh = Lookup(OfflineClient(sample_files(tmp_path)), store, seed=SEED)
    assert fresh.check(COIN_FLIPPER) == (COIN_FLIPPER, None)
    assert fresh.wallet_page(COIN_FLIPPER).outcome is Outcome.NOT_LOADED
    last = synthetic.address_of(synthetic.coin_flipper_name(synthetic.COIN_FLIPPERS - 1))
    assert fresh.wallet_page(last).outcome is Outcome.NOT_LOADED
    assert fresh.wallet_page(UNKNOWN).outcome is Outcome.NOT_AVAILABLE_OFFLINE
    store.close()


def test_fr14_sample_file_being_written_reads_as_not_loaded(tmp_path: Path) -> None:
    """FR-14 (review): a Sample file cut off mid-write (load-sample running) never breaks the page."""
    synthetic.write_small(tmp_path)
    (tmp_path / synthetic.SMALL_DIR / "half-written.json").write_text('{"activity": [', encoding="utf-8")
    store = Store(tmp_path / OFFLINE_DB)
    lookup = Lookup(OfflineClient(sample_files(tmp_path)), store, seed=SEED)
    assert lookup.wallet_page(UNKNOWN).outcome is Outcome.NOT_LOADED
    store.close()


def test_all_addresses_covers_every_synthetic_wallet() -> None:
    """AD-14: the small Wallets' names match the generator, and every coin-flipper address is known."""
    assert synthetic.SMALL_NAMES == tuple(w.name for w in synthetic.small_wallets())
    known = synthetic.all_addresses()
    assert len(known) == len(synthetic.SMALL_NAMES) + synthetic.COIN_FLIPPERS
    assert synthetic.coin_flipper(7).address in known
