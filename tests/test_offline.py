"""Offline Mode: OfflineClient, the fetch pipeline and the round trip (FR-12, FR-14, AD-13, AD-14).

The round trip is generator -> files -> OfflineClient -> pipeline -> store -> Skill Test, with
sockets blocked. Its answers are `sample_data/synthetic/expected.json`, written by hand in Story 1.3.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

import liquidoracle.__main__ as cli
from liquidoracle.core.positions import build_positions
from liquidoracle.core.skilltest import skill_test
from liquidoracle.data import sample_json, synthetic
from liquidoracle.data.errors import NotAvailableOffline
from liquidoracle.data.offline import OfflineClient, sample_files
from liquidoracle.data.store import LIVE_DB, OFFLINE_DB, Store
from liquidoracle.records import Verdict
from liquidoracle.services.fetch import fetch_wallet, skill_result
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


def test_sample_files_are_the_wallets_and_skip_the_hand_answers(sample_root: Path) -> None:
    """AD-14: the client serves every Wallet file; expected.json is not a Wallet."""
    names = [p.name for p in sample_files(sample_root)]
    assert "expected.json" not in names
    assert len(names) == len(synthetic.small_wallets()) + COIN_FLIPPERS


def test_client_returns_the_generators_records(sample_root: Path) -> None:
    """AD-2, AD-14: OfflineClient returns the same `records` the generator wrote, through the client methods."""
    client = OfflineClient(sample_files(sample_root))
    for wallet in generated():
        assert client.positions(wallet.address) == wallet.positions
        assert client.activity(wallet.address) == wallet.activity
        ids = [m.condition_id for m in wallet.markets]
        assert client.markets(reversed(ids)) == tuple(reversed(wallet.markets))


def test_client_lower_cases_the_address(sample_root: Path) -> None:
    """FR-1: an address in capitals or with spaces finds the same Wallet."""
    wallet = synthetic.small_wallets()[0]
    client = OfflineClient(sample_files(sample_root))
    assert client.activity("  " + wallet.address.upper().replace("0X", "0x") + " ") == wallet.activity


def test_unknown_wallet_or_market_is_not_available_offline(sample_root: Path) -> None:
    """FR-14: anything outside the Sample Dataset raises NotAvailableOffline."""
    client = OfflineClient(sample_files(sample_root))
    with pytest.raises(NotAvailableOffline):
        client.positions(UNKNOWN)
    with pytest.raises(NotAvailableOffline):
        client.activity(UNKNOWN)
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
        assert snapshot.positions == wallet.positions
        assert snapshot.activity == wallet.activity
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
    built = build_positions(snapshot.activity, {m.condition_id: m for m in snapshot.markets})
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
        direct = skill_test(build_positions(wallet.activity, markets), seed=SEED, unit_id=wallet.address)
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
    """AD-13, FR-14: Offline Mode gets OfflineClient and instance/offline.db."""
    sources = cli.open_sources(Settings(offline=True), tmp_path)
    try:
        assert isinstance(sources.client, OfflineClient)
        assert sources.store.path == tmp_path / OFFLINE_DB
    finally:
        sources.store.close()


def test_live_run_gets_live_db(tmp_path: Path) -> None:
    """AD-13: a live run uses instance/live.db, never the offline file; its client arrives in Story 2.1."""
    sources = cli.open_sources(Settings(offline=False), tmp_path)
    try:
        assert sources.store.path == tmp_path / LIVE_DB
        assert sources.client is None
        assert not (tmp_path / OFFLINE_DB).exists()
    finally:
        sources.store.close()


# --- Size of the committed Sample Dataset (FR-12) ----------------------------------------------

MAX_SAMPLE_BYTES = 25_000_000  # [ASSUMPTION] FR-12, AD-14: no Git LFS


def sample_data_bytes(folder: Path) -> int:
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())


def test_committed_sample_dataset_is_under_25_mb() -> None:
    """FR-12, AD-14: the committed Sample Dataset stays under 25 MB."""
    assert 0 < sample_data_bytes(REPO / "sample_data") < MAX_SAMPLE_BYTES


def test_size_check_catches_a_large_dataset(tmp_path: Path) -> None:
    """FR-12: the size check fails on a folder over the limit (a sparse file, so nothing big is written)."""
    with open(tmp_path / "big.json", "wb") as big:
        big.truncate(MAX_SAMPLE_BYTES + 1)
    assert sample_data_bytes(tmp_path) >= MAX_SAMPLE_BYTES
