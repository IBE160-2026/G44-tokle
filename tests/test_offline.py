"""Offline Mode: OfflineClient, the fetch pipeline and the round trip (FR-12, FR-14, AD-13, AD-14).

The round trip is generator -> files -> OfflineClient -> pipeline -> store -> Skill Test, with
sockets blocked. Its answers are `sample_data/synthetic/expected.json`, written by hand in Story 1.3.
Story 4.6 extends it to the offline Scan: the same files -> OfflineClient as a FunnelClient -> the
job queue and worker -> the Watchlist (FR-16).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

import liquidoracle.__main__ as cli
from liquidoracle.data import offline as offline_module
from liquidoracle.core.positions import build_positions
from liquidoracle.core.skilltest import skill_test
from liquidoracle.data import sample_json, synthetic
from liquidoracle.data.errors import NotAvailableOffline
from liquidoracle.data.offline import OfflineClient, holder_rows, sample_files, sample_funnel
from liquidoracle.data.polymarket import PolymarketClient
from liquidoracle.data.store import LIVE_DB, OFFLINE_DB, Store
from liquidoracle.data.window import cutoff_at
from liquidoracle.records import ActivityRow, ListedPosition, Market, Read, SampleWallet, Verdict
from liquidoracle.services.fetch import fetch_wallet, skill_result
from liquidoracle.services.jobs import Jobs, Worker
from liquidoracle.services.scans_page import ScansPage, Submitted
from liquidoracle.services.watchlist import Watchlists
from liquidoracle.settings import Settings

REPO = Path(__file__).resolve().parents[1]
EXPECTED = json.loads((REPO / synthetic.SMALL_DIR / "expected.json").read_text(encoding="utf-8"))
SEED = 44
COIN_FLIPPERS = 3
UNKNOWN = "0x" + "0" * 40


@pytest.fixture(scope="module")
def sample_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A repository-like folder: the committed Synthetic Wallets plus 3 freshly written coin-flippers."""
    root = tmp_path_factory.mktemp("repo")
    synthetic.write_small(root)
    (root / synthetic.SMALL_DIR / "expected.json").write_bytes((REPO / synthetic.SMALL_DIR / "expected.json").read_bytes())
    synthetic.write_coin_flippers(root, COIN_FLIPPERS)
    return root


@pytest.fixture(scope="module")
def loaded(sample_root: Path) -> Iterator[Store]:
    """Every Wallet in `sample_root` fetched through OfflineClient into a fresh database."""
    client = OfflineClient(sample_files(sample_root))
    db = Store(sample_root / OFFLINE_DB)
    for address in client.addresses():
        fetch_wallet(client, db, address)
    yield db
    db.close()


def generated() -> list:
    return [*synthetic.small_wallets(), *synthetic.coin_flippers(COIN_FLIPPERS)]


# --- OfflineClient (AD-2, FR-14) ---------------------------------------------------------------


def listed(client: OfflineClient, address: str) -> set[ListedPosition]:
    """Both positions lists of a Wallet, as one set."""
    return {*client.positions_list(address, "OPEN").rows, *client.positions_list(address, "CLOSED").rows}


def test_sample_files_are_the_wallets_and_skip_the_hand_answers(sample_root: Path) -> None:
    """AD-14: the client serves every Wallet file; expected.json is not a Wallet."""
    names = [p.name for p in sample_files(sample_root)]
    assert "expected.json" not in names
    assert len(names) == len(synthetic.small_wallets()) + COIN_FLIPPERS


def test_client_returns_the_generators_records(sample_root: Path) -> None:
    """AD-2, AD-14: OfflineClient returns the same `records` the generator wrote, through the client methods."""
    client = OfflineClient(sample_files(sample_root))
    for wallet in generated():
        assert listed(client, wallet.address) == set(wallet.positions)
        assert client.activity_rows(wallet.address, start=0) == Read(tuple(sorted(wallet.activity, key=lambda r: r.timestamp)), True)
        ids = [m.condition_id for m in wallet.markets]
        assert client.markets(reversed(ids)) == tuple(reversed(wallet.markets))


def test_client_lower_cases_the_address(sample_root: Path) -> None:
    """FR-1: an address in capitals or with spaces finds the same Wallet."""
    wallet = synthetic.small_wallets()[0]
    client = OfflineClient(sample_files(sample_root))
    assert listed(client, "  " + wallet.address.upper().replace("0X", "0x") + " ") == set(wallet.positions)


def test_unknown_wallet_or_market_is_not_available_offline(sample_root: Path) -> None:
    """FR-14: anything outside the Sample Dataset raises NotAvailableOffline."""
    client = OfflineClient(sample_files(sample_root))
    with pytest.raises(NotAvailableOffline):
        client.positions_list(UNKNOWN, "OPEN")
    with pytest.raises(NotAvailableOffline):
        client.activity_rows(UNKNOWN, start=0)
    with pytest.raises(NotAvailableOffline):
        client.markets(["0xnot-a-market"])


def test_unknown_wallet_leaves_no_snapshot(tmp_path: Path, sample_root: Path) -> None:
    """FR-14, AD-19: a failed offline fetch writes nothing."""
    db = Store(tmp_path / "offline.db")
    try:
        with pytest.raises(NotAvailableOffline):
            fetch_wallet(OfflineClient(sample_files(sample_root)), db, UNKNOWN)
        assert db.wallet_count() == 0
        assert db._connection().execute("SELECT COUNT(*) FROM snapshot").fetchone() == (0,)
    finally:
        db.close()


def test_two_files_with_one_address_are_refused(tmp_path: Path) -> None:
    """AD-14: the Sample Dataset cannot hold one Wallet twice."""
    wallet = synthetic.small_wallets()[0]
    sample_json.write_wallet(tmp_path / "a.json", wallet)
    sample_json.write_wallet(tmp_path / "b.json", wallet)
    with pytest.raises(ValueError, match="also in"):
        OfflineClient([tmp_path / "a.json", tmp_path / "b.json"]).addresses()


@pytest.mark.parametrize("address", ["0x" + "AB" * 20, " 0x" + "ab" * 20, "0x" + "ab" * 19, "", "0xzz" + "ab" * 19])
def test_a_badly_formed_address_is_refused(tmp_path: Path, address: str) -> None:
    """FR-1, AD-14: a Sample file's address must be 0x and 40 lower-case hex characters; the error names the file."""
    wallet = synthetic.small_wallets()[0]
    sample_json.write_wallet(tmp_path / "odd.json", replace(wallet, address=address))
    with pytest.raises(ValueError, match="odd.json"):
        OfflineClient([tmp_path / "odd.json"]).addresses()


def test_a_malformed_file_names_itself(tmp_path: Path) -> None:
    """AD-14: a broken Sample Dataset file stops with its name, never a silent skip."""
    (tmp_path / "broken.json").write_text('{"address": "0xab"}', encoding="utf-8")
    with pytest.raises(ValueError, match="broken.json"):
        OfflineClient([tmp_path / "broken.json"]).addresses()


# --- The round trip (AD-14, FR-13) -------------------------------------------------------------


def test_round_trip_stores_exactly_the_generated_records(loaded: Store) -> None:
    """AD-14: generator -> OfflineClient -> pipeline -> store gives back every list unchanged."""
    for wallet in generated():
        snapshot = loaded.latest_snapshot(wallet.address)
        assert snapshot is not None, wallet.name
        assert set(snapshot.positions) == set(wallet.positions)  # every Synthetic Wallet fits one window
        assert sorted(snapshot.activity, key=repr) == sorted(wallet.activity, key=repr)
        assert set(snapshot.markets) == set(wallet.markets)


@pytest.mark.parametrize("name", sorted(EXPECTED["wallets"]))
def test_round_trip_gives_each_synthetic_wallet_its_bets_and_verdict(loaded: Store, name: str) -> None:
    """AD-14, FR-4, FR-6, FR-13: through the store, each Wallet gets the bets, Real PnL and Verdict of expected.json.

    The hand-check Wallet has no Verdict in expected.json (its 10 bets were checked on the engine
    directly); on the normal path it must read Not enough data.
    """
    answer = EXPECTED["wallets"][name]
    wallet = next(w for w in synthetic.small_wallets() if w.name == name)
    snapshot = loaded.latest_snapshot(wallet.address)
    assert snapshot is not None
    built = build_positions(snapshot.activity, {m.condition_id: m for m in snapshot.markets}, listed=snapshot.positions)
    assert (len(built.tested), len(built.slivers), len(built.left_out)) == (
        answer["tested"], answer["slivers"], answer["left_out"])
    result = skill_result(loaded, wallet.address, seed=SEED)
    assert result is not None
    assert result.real_pnl == pytest.approx(answer["real_pnl"], abs=0.005)
    expected_verdict = answer["verdict"] or Verdict.NOT_ENOUGH_DATA.value
    assert result.verdict.value == expected_verdict
    if "p_below" in answer and answer["verdict"]:
        assert result.p_value is not None and result.p_value < answer["p_below"]
    if "p_at_least" in answer and answer["verdict"]:
        assert result.p_value is not None and result.p_value >= answer["p_at_least"]


def test_round_trip_result_equals_the_direct_result(loaded: Store) -> None:
    """AD-14, AD-15: the stored path gives the identical Skill Test result as the generator's own records."""
    for wallet in generated():
        markets = {m.condition_id: m for m in wallet.markets}
        direct = skill_test(build_positions(wallet.activity, markets, listed=wallet.positions), seed=SEED, unit_id=wallet.address)
        assert skill_result(loaded, wallet.address.upper().replace("0X", "0x"), seed=SEED) == direct


def test_no_snapshot_gives_no_result(tmp_path: Path) -> None:
    """AD-19: a Wallet with no stored snapshot has no result yet."""
    db = Store(tmp_path / "empty.db")
    try:
        assert skill_result(db, UNKNOWN, seed=SEED) is None
    finally:
        db.close()


# --- The mode swap (AD-13) ---------------------------------------------------------------------


def test_offline_mode_gets_offline_client_and_offline_db(tmp_path: Path) -> None:
    """AD-13, FR-14: Offline Mode gets OfflineClient and instance/offline.db; since Story 4.6 also a job queue
    over the same store, and the count of Sample Wallets, an offline Scan's N."""
    synthetic.write_small(tmp_path)
    sources = cli.open_sources(Settings(offline=True), tmp_path)
    try:
        assert isinstance(sources.client, OfflineClient)
        assert sources.store.path == tmp_path / OFFLINE_DB
        assert sources.jobs.store is sources.store
        assert sources.sample_size is not None and sources.sample_size() == len(synthetic.SMALL_NAMES)
        assert [m.volume for m in sources.client.funnel_markets(0, 2**40, 100)] == [3e6, 2e6, 1e6]
    finally:
        sources.store.close()


def test_live_run_gets_live_db(tmp_path: Path) -> None:
    """AD-13: a live run uses instance/live.db, never the offline file, the Polymarket client and a job queue (Story 2.5)."""
    sources = cli.open_sources(Settings(offline=False), tmp_path)
    try:
        assert sources.store.path == tmp_path / LIVE_DB
        assert isinstance(sources.client, PolymarketClient)
        assert sources.jobs is not None and sources.jobs.store is sources.store
        assert sources.sample_size is None
        assert not (tmp_path / OFFLINE_DB).exists()
    finally:
        sources.store.close()


# --- Size of the committed Sample Dataset (FR-12) ----------------------------------------------

MAX_SAMPLE_BYTES = 50_000_000  # [ASSUMPTION] FR-12, AD-14: no Git LFS (25 MB until Story 2.6; Edvard, 2026-11-23)


def sample_data_bytes(folder: Path) -> int:
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())


def test_committed_sample_dataset_is_under_the_size_limit() -> None:
    """FR-12, AD-14: the committed Sample Dataset stays under 50 MB."""
    assert 0 < sample_data_bytes(REPO / "sample_data") < MAX_SAMPLE_BYTES


def test_size_check_catches_a_large_dataset(tmp_path: Path) -> None:
    """FR-12: the size check fails on a folder over the limit (a sparse file, so nothing big is written)."""
    with open(tmp_path / "big.json", "wb") as big:
        big.truncate(MAX_SAMPLE_BYTES + 1)
    assert sample_data_bytes(tmp_path) >= MAX_SAMPLE_BYTES


def test_client_finds_sample_files_written_after_it_started(tmp_path: Path) -> None:
    """FR-14, Story 1.7: with `list_files`, a Wallet whose file appears after the index was built
    (load-sample run while the app is open) is found; an unknown address still raises."""
    synthetic.write_small(tmp_path)
    client = OfflineClient(sample_files(tmp_path), list_files=lambda: sample_files(tmp_path))
    late = synthetic.coin_flipper(0)
    with pytest.raises(NotAvailableOffline):
        listed(client, late.address)  # builds the index without the coin-flipper
    synthetic.write_coin_flippers(tmp_path, 1)
    assert listed(client, late.address) == set(late.positions)
    assert client.markets([late.markets[0].condition_id]) == (late.markets[0],)
    with pytest.raises(NotAvailableOffline):
        listed(client, UNKNOWN)


def test_client_without_list_files_keeps_its_first_files(tmp_path: Path) -> None:
    """AD-14: a client built from a fixed file list (load-sample's) never looks for new files."""
    synthetic.write_small(tmp_path)
    client = OfflineClient(sample_files(tmp_path))
    client.addresses()
    synthetic.write_coin_flippers(tmp_path, 1)
    with pytest.raises(NotAvailableOffline):
        listed(client, synthetic.coin_flipper(0).address)



def test_open_sources_client_finds_files_written_after_start(tmp_path: Path) -> None:
    """AD-13, FR-14 (review): the client Offline Mode's pages get from `open_sources` sees Sample files
    that load-sample writes after the app started."""
    synthetic.write_small(tmp_path)
    sources = cli.open_sources(Settings(offline=True), tmp_path)
    assert len(sources.client.addresses()) == len(synthetic.small_wallets())  # index built now
    synthetic.write_coin_flippers(tmp_path, 1)
    late = synthetic.coin_flipper(0)
    assert listed(sources.client, late.address) == set(late.positions)
    sources.store.close()


def test_offline_lists_come_in_live_sized_pages_and_stop_where_until_says(
    sample_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-7, AD-13 (review): OfflineClient sorts by last event like the live list, serves pages of the live
    size, and stops after the page `until` accepts; the last page is never put to `until`."""
    import liquidoracle.data.offline as offline_module

    monkeypatch.setattr(offline_module, "PAGE_LIMIT", 3)
    wallet = synthetic.small_wallets()[0]
    client = OfflineClient(sample_files(sample_root))
    every = client.positions_list(wallet.address, "CLOSED", sort_by="TIMESTAMP", sort_direction="DESC").rows
    assert len(every) > 6
    assert [r.last_event_at for r in every] == sorted((r.last_event_at for r in every), reverse=True)
    pages: list[int] = []
    read = client.positions_list(
        wallet.address, "CLOSED", sort_by="TIMESTAMP", sort_direction="DESC",
        until=lambda page: pages.append(len(page)) or len(pages) == 2,
    )
    assert pages == [3, 3] and read.rows == every[:6] and read.complete


def test_offline_activity_cap_keeps_the_oldest_rows_and_says_so(sample_root: Path) -> None:
    """AD-7, AD-13 (review): a capped offline read keeps exactly the oldest `row_cap` rows and is incomplete;
    a cap below 1 is refused like the live client's."""
    wallet = synthetic.small_wallets()[0]
    client = OfflineClient(sample_files(sample_root))
    every = client.activity_rows(wallet.address, start=0).rows
    capped = client.activity_rows(wallet.address, start=0, row_cap=5)
    assert capped == Read(every[:5], False)
    assert client.activity_rows(wallet.address, start=0, row_cap=len(every)).complete
    with pytest.raises(ValueError, match="row_cap"):
        client.activity_rows(wallet.address, start=0, row_cap=0)


# --- OfflineClient as a FunnelClient (Story 4.6; AD-9, AD-14, AD-21) ---------------------------

ANCHOR_IDS = list(synthetic.funnel_volumes())  # condition ids, in the volume list's order
DEFAULT_CUT = cutoff_at(date(2025, 7, 1))
DAY = 86_400


def funnel_client(root: Path) -> OfflineClient:
    return OfflineClient(sample_files(root), funnel=sample_funnel(root))


def test_ad21_offline_market_set_is_the_anchors_by_volume(sample_root: Path) -> None:
    """AD-21, AD-14: with the default Cut-off Date the offline Market set is the 3 anchor Markets, highest volume
    first, each with the record a Wallet file holds; the live rule's window and count apply."""
    client = funnel_client(sample_root)
    chosen = client.funnel_markets(DEFAULT_CUT - 90 * DAY, DEFAULT_CUT, 100)
    assert [entry.volume for entry in chosen] == [3_000_000.0, 2_000_000.0, 1_000_000.0]
    assert {entry.market.condition_id for entry in chosen} == set(ANCHOR_IDS)
    assert all(entry.market.resolved for entry in chosen)
    assert len(client.funnel_markets(DEFAULT_CUT - 90 * DAY, DEFAULT_CUT, 2)) == 2
    # 2025-06-01 00:00 is in [from, until) only when `until` is after it: the window's end is exclusive.
    june_first = 1_748_736_000
    assert [e.volume for e in client.funnel_markets(june_first, june_first + 1, 100)] == [2_000_000.0]
    assert client.funnel_markets(june_first + 1, DEFAULT_CUT, 100)[0].volume == 1_000_000.0
    assert client.funnel_markets(DEFAULT_CUT, DEFAULT_CUT + 90 * DAY, 100) == ()


def test_ad21_offline_market_set_without_a_volume_list_is_empty(sample_root: Path) -> None:
    """AD-21: a client with no volume list (or a missing file) has no Market set, so a Scan finds no candidates."""
    assert OfflineClient(sample_files(sample_root)).funnel_markets(0, 2**40, 100) == ()
    assert OfflineClient(sample_files(sample_root), funnel=sample_root / "missing.json").funnel_markets(0, 2**40, 100) == ()
    with pytest.raises(ValueError, match="count"):
        funnel_client(sample_root).funnel_markets(0, 1, 0)
    with pytest.raises(ValueError, match="window"):
        funnel_client(sample_root).funnel_markets(5, 5, 1)


def test_ad9_offline_holder_lists_are_every_sample_wallet_in_the_market(sample_root: Path) -> None:
    """AD-9, AD-14: an anchor Market's CLOSED list holds the four FR-16 Wallets and every coin-flipper, oldest first,
    complete; its OPEN list is empty (every anchor Position was sold). The numbers come from each Wallet's trades."""
    client = funnel_client(sample_root)
    expected = {synthetic.address_of(n) for n in synthetic.WATCHLIST_NAMES}
    expected |= {synthetic.address_of(synthetic.coin_flipper_name(i)) for i in range(COIN_FLIPPERS)}
    for condition_id in ANCHOR_IDS:
        closed = client.market_holders(condition_id, "CLOSED")
        assert closed.complete and {row.wallet for row in closed.rows} == expected
        assert all((row.realized_pnl, row.current_size, row.avg_price) == (0.0, 0.0, 0.5) for row in closed.rows)
        assert [row.wallet for row in closed.rows] == sorted(row.wallet for row in closed.rows)  # same last event: by address
        assert client.market_holders(condition_id, "OPEN") == Read((), True)
    with pytest.raises(ValueError, match="CLOSED or OPEN"):
        client.market_holders(ANCHOR_IDS[0], "REDEEMABLE")


def test_ad9_offline_holder_list_over_the_cap_is_partial(sample_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-9: as live, a holder list that reaches `MARKET_ROW_CAP` rows is partial, so the Market gives no candidates."""
    monkeypatch.setattr(offline_module, "MARKET_ROW_CAP", 3)
    read = funnel_client(sample_root).market_holders(ANCHOR_IDS[0], "CLOSED")
    assert not read.complete and len(read.rows) == 3


def test_ad21_holder_rows_derive_the_pre_filter_numbers_from_trades() -> None:
    """AD-21, AD-10: a planted Wallet in one Market: a CLOSED winner partly sold then redeemed, and an OPEN loser
    partly sold. avg = cash / shares bought; CLOSED realised = sells - avg x sold + (1 - avg) x held; OPEN keeps
    the shares held as `current_size`."""
    market = Market("0x" + "c" * 64, True, 2_000, ("1", "2"), (1.0, 0.0), False)
    trades = (
        ActivityRow("TRADE", market.condition_id, 100, 10.0, 4.0, 0.4, "1", "BUY"),
        ActivityRow("TRADE", market.condition_id, 200, 10.0, 6.0, 0.6, "1", "BUY"),
        ActivityRow("TRADE", market.condition_id, 300, 5.0, 4.0, 0.8, "1", "SELL"),
        ActivityRow("TRADE", market.condition_id, 400, 8.0, 2.4, 0.3, "2", "BUY"),
        ActivityRow("TRADE", market.condition_id, 500, 2.0, 0.2, 0.1, "2", "SELL"),
    )
    listed = (
        ListedPosition(market.condition_id, "1", "CLOSED", 20.0, 100, 2_000),
        ListedPosition(market.condition_id, "2", "OPEN", 8.0, 400, 500),
    )
    wallet = SampleWallet("0x" + "d" * 40, "planted", trades, listed, (market,))
    (winner, w_last), (loser, l_last) = holder_rows(wallet, market.condition_id)
    assert (winner.status, winner.avg_price, winner.current_size, w_last) == ("CLOSED", 0.5, 0.0, 2_000)
    assert winner.realized_pnl == pytest.approx(4.0 - 0.5 * 5 + 15 * (1.0 - 0.5))  # 9.0
    assert (loser.status, loser.avg_price, loser.current_size, l_last) == ("OPEN", 0.3, 6.0, 500)
    assert loser.realized_pnl == pytest.approx(0.2 - 0.3 * 2)
    assert holder_rows(wallet, "0x" + "e" * 64) == []


# --- The offline Scan (FR-16, AD-14, AD-5; Story 4.6) --------------------------------------------

SCAN_COIN_FLIPPERS = 40  # enough for some luck; the full 1,000 was run by hand (spec Implementation Notes)


@pytest.fixture(scope="module")
def offline_scan(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Store, int, OfflineClient]]:
    """An offline Scan started from the Scans page in Offline Mode and run by the worker to the end, sockets blocked."""
    root = tmp_path_factory.mktemp("scan-repo")
    synthetic.write_small(root)
    synthetic.write_coin_flippers(root, SCAN_COIN_FLIPPERS)
    client = funnel_client(root)
    db = Store(root / OFFLINE_DB)
    jobs = Jobs(db)
    page = ScansPage(db, jobs=jobs, seed=SEED, rate=5.0, sample_size=lambda: len(client.addresses()))
    assert page.submit("", "", confirmed=False) == (Submitted.STARTED, None)
    assert Worker(client, jobs).run_once()
    (scan,) = db.scans()
    yield db, scan.scan_id, client
    db.close()


def test_fr16_offline_scan_puts_the_four_on_the_watchlist(offline_scan: tuple[Store, int, OfflineClient]) -> None:
    """FR-16 check, AD-14: an offline Scan with the default Cut-off Date puts at least sharp trader, steady sharp,
    forecaster and speed trader on the Watchlist, and states the luck passes for the Wallets it tested."""
    db, scan_id, _ = offline_scan
    view = Watchlists(db).view(scan_id)
    assert view is not None
    on_list = {row.address for row in view.rows}
    assert {synthetic.address_of(name) for name in synthetic.WATCHLIST_NAMES} <= on_list
    tested = len(synthetic.WATCHLIST_NAMES) + SCAN_COIN_FLIPPERS
    assert view.header.title == f"Scan of {tested} Wallets"
    assert view.luck == (
        f"About 1 in 100 Wallets would pass by luck alone, probably more, because these Wallets were picked for high"
        f" profit. With only {tested} Wallets with a Verdict, even one passing could be luck."
    )
    assert len(on_list) <= len(synthetic.WATCHLIST_NAMES) + 3  # a few coin-flippers at most pass by luck


def test_ad14_offline_scan_runs_the_whole_live_path(offline_scan: tuple[Store, int, OfflineClient]) -> None:
    """AD-14, AD-21 (Story 4.6, matrix "Offline Scan"): the job finishes; the Market set is the 3 anchors, all used;
    the candidates are exactly the anchor holders; N is every Sample Wallet; nothing is flagged not fully read."""
    db, scan_id, client = offline_scan
    scan = db.scan(scan_id)
    assert scan.step.value == "done" and scan.job.status.value == "done"
    assert scan.size == len(client.addresses()) == len(synthetic.SMALL_NAMES) + SCAN_COIN_FLIPPERS
    assert [(m.condition_id, m.state) for m in db.scan_markets(scan_id)] == [(c, "used") for c in ANCHOR_IDS]
    holders = {synthetic.address_of(n) for n in synthetic.WATCHLIST_NAMES}
    holders |= {synthetic.address_of(synthetic.coin_flipper_name(i)) for i in range(SCAN_COIN_FLIPPERS)}
    assert set(db.scan_candidates(scan_id)) == holders
    assert all(w.top and not w.not_fully_read for w in db.scan_wallets(scan_id))


def test_ad11_offline_scan_results_leave_out_the_anchor_bets(offline_scan: tuple[Store, int, OfflineClient]) -> None:
    """AD-11, AD-22 (Story 4.6, matrix "Anchor bets"): the Scan's results count exactly the hand-written tested bets:
    the whole Scan both sides, the before part only the bets resolved before the cut-off; anchors never count."""
    db, scan_id, _ = offline_scan
    results = {(r.wallet, r.scope): r for r in db.scan_results(scan_id)}
    for name in synthetic.WATCHLIST_NAMES:
        answer = EXPECTED["wallets"][name]
        whole = results[(synthetic.address_of(name), "scan_whole")]
        before = results[(synthetic.address_of(name), "scan_before")]
        assert (whole.verdict, whole.tested_count) == (answer["verdict"], answer["tested"])
        assert whole.real_pnl == pytest.approx(answer["real_pnl"], abs=0.005)
        assert before.tested_count == 100 and before.verdict == answer["verdict"]


def test_ad5_offline_scan_with_a_missing_coin_flipper_folder(tmp_path: Path) -> None:
    """AD-5 (Story 4.6, matrix "Coin-flippers missing"): before `load-sample` has written the coin-flippers, an
    offline Scan runs on the committed files and still finds the four."""
    synthetic.write_small(tmp_path)
    client = funnel_client(tmp_path)
    db = Store(tmp_path / OFFLINE_DB)
    try:
        jobs = Jobs(db)
        jobs.start_scan(date(2025, 7, 1), len(client.addresses()), seed=SEED)
        assert Worker(client, jobs).run_once()
        (scan,) = db.scans()
        view = Watchlists(db).view(scan.scan_id)
        assert view is not None
        assert {row.address for row in view.rows} == {synthetic.address_of(n) for n in synthetic.WATCHLIST_NAMES}
    finally:
        db.close()


def test_ad14_offline_scan_finds_coin_flippers_written_after_the_start(tmp_path: Path) -> None:
    """AD-14, FR-12 (Story 4.6 review): the app may start before `load-sample` writes the coin-flippers (the
    "not loaded" page says to run it then). The Scan's N and the anchor holder lists then include them,
    also after both were first read without them."""
    synthetic.write_small(tmp_path)
    client = OfflineClient(sample_files(tmp_path), list_files=lambda: sample_files(tmp_path), funnel=sample_funnel(tmp_path))
    assert len(client.addresses()) == len(synthetic.SMALL_NAMES)
    assert len(client.market_holders(ANCHOR_IDS[0], "CLOSED").rows) == len(synthetic.WATCHLIST_NAMES)
    synthetic.write_coin_flippers(tmp_path, 5)
    assert len(client.market_holders(ANCHOR_IDS[0], "CLOSED").rows) == len(synthetic.WATCHLIST_NAMES) + 5
    assert len(client.addresses()) == len(synthetic.SMALL_NAMES) + 5
