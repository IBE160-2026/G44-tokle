"""The real Wallets of the Sample Dataset: `build-sample` and its committed output (AD-14, FR-12, NFR-10; Story 2.6).

The build is tested on small made-up captures with the zip's layout, so the tests need neither the
raw capture (kept outside the repository) nor the network: the one-off fetch runs against a fake
live client. The committed `sample_data/real/` files are checked last, with sockets blocked.
"""

from __future__ import annotations

import json
import time
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import liquidoracle.__main__ as cli
from liquidoracle.data import real_sample, sample_json
from liquidoracle.data.offline import REAL_DIR, OfflineClient, sample_files
from liquidoracle.data.real_sample import ADDITIONS_NAME, CAPTURE_NAME, BuildError, build, fetch_additions
from liquidoracle.data.store import Store
from liquidoracle.data.window import positions_near
from liquidoracle.records import ActivityRow, ListedPosition, Read, SampleWallet
from liquidoracle.services.fetch import fetch_wallet, stored_result

REPO = Path(__file__).resolve().parents[1]
SEED = 44
W1 = "0x" + "1" * 40
W2 = "0x" + "2" * 40
SPARE = "0x" + "3" * 40
PICKED = (W1, W2)
T0 = 1_740_000_000  # Feb 2025
DAY = 86_400


def cid(n: int) -> str:
    return f"0x{n:064x}"


def iso(t: int) -> str:
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d %H:%M:%S+00")


def raw_position(n: int, *, bought: int | None = None) -> dict[str, Any]:
    first = bought if bought is not None else T0 + n * DAY
    return {"condition_id": cid(n), "token_id": f"{n}1", "total_size": 10.0, "avg_price": 0.4,
            "first_entry_at": first, "last_event_at": first + 60}


def raw_trade(n: int, t: int) -> dict[str, Any]:
    return {"type": "TRADE", "condition_id": cid(n), "timestamp": t, "size": 10.0, "usdc_size": 4.0,
            "price": 0.4, "token_id": f"{n}1", "side": "BUY", "is_combo": False}


def raw_gamma(n: int, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "conditionId": cid(n), "closed": True, "closedTime": iso(T0 + n * DAY + DAY // 2),
        "startDate": iso(T0 + n * DAY - 3600), "clobTokenIds": json.dumps([f"{n}1", f"{n}2"]),
        "outcomePrices": '["1", "0"]', "outcomes": '["Yes", "No"]', "feesEnabled": False,
        "tags": [{"label": "Sports", "id": "1"}], "events": [{"id": f"e{n}", "title": "x"}], "volume": "123",
    }
    row.update(extra)
    return row


def capture_zip(folder: Path, wallets: dict[str, dict[str, Any]]) -> Path:
    """A zip with the capture's layout; each value holds `open`, `closed`, `capped`, `before`, `after`."""
    path = folder / CAPTURE_NAME
    with zipfile.ZipFile(path, "w") as archive:
        # As in the real zip, its own pick file is out of date: the build never reads it.
        archive.writestr("sample/picked.json", json.dumps({"sample": [SPARE], "spares": list(wallets)}))
        for address, parts in wallets.items():
            base = f"sample/capture/{address}/"
            archive.writestr(base + "positions.json", json.dumps(
                {"closed": parts.get("closed", []), "open": parts.get("open", []), "capped": parts.get("capped", False)}))
            before = sorted(parts.get("before", []), key=lambda r: -r["timestamp"])  # newest first, as captured
            archive.writestr(base + "activity_before.json", json.dumps({"rows": before, "capped": parts.get("before_capped", False)}))
            archive.writestr(base + "activity_after.json",
                             json.dumps({"rows": parts.get("after", []), "capped": parts.get("after_capped", False)}))
        archive.writestr(f"sample/capture/{SPARE}/positions.json", "not read")  # spares are never read
    real_sample.write_sha256(path)
    return path


class FakeLive:
    """The live client for `--fetch`: Gamma answers for `known`, and a CLOSED list for cut lists."""

    def __init__(self, known: dict[str, dict[str, Any]], closed: Iterable[dict[str, Any]] = ()) -> None:
        self.known = known
        self.closed = [real_sample.parse_listed_position(row, "CLOSED") for row in closed]
        self.asked: list[str] = []
        self.list_calls = 0

    def raw_markets(self, ids: Iterable[str]) -> tuple[dict[str, Any], ...]:
        wanted = list(ids)
        self.asked.extend(wanted)
        return tuple(self.known[c] for c in wanted if c in self.known)

    def positions_list(self, wallet: str, status: str, **options: Any) -> Read[ListedPosition]:
        self.list_calls += 1
        rows = sorted(self.closed, key=lambda row: row.last_event_at, reverse=True)
        return Read(tuple(rows), True)


def repo(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "pyproject.toml").write_text("", encoding="utf-8")
    (folder / "sample_data").mkdir()
    return folder


def small_capture(folder: Path) -> tuple[Path, FakeLive]:
    """W1: three CLOSED, one OPEN, clean. W2: activity capped after the second Market's buy."""
    w1 = {
        "closed": [raw_position(n) for n in (1, 2, 3)],
        "open": [raw_position(4)],
        "before": [raw_trade(n, T0 + n * DAY) for n in (1, 2)],
        "after": [raw_trade(n, T0 + n * DAY) for n in (3, 4)],
    }
    w2 = {
        "closed": [raw_position(n) for n in (5, 6, 7)],
        "after": [raw_trade(n, T0 + n * DAY) for n in (5, 6)],
        "after_capped": True,  # the capture stopped in Market 6's buy second; Market 7's buy is missing
    }
    known = {cid(n): raw_gamma(n) for n in range(1, 8)}
    return capture_zip(folder, {W1: w1, W2: w2}), FakeLive(known)


# --- OfflineClient: where the capture stopped ----------------------------------------------------


def bounded(**bounds: int | None) -> OfflineClient:
    rows = tuple(ActivityRow("TRADE", cid(1), t, 1.0, 0.5, 0.5, "11", "BUY") for t in (100, 200, 300))
    return OfflineClient.in_memory([SampleWallet(W1, "w", rows, (), (), **bounds)])


def test_offline_read_inside_the_capture_is_complete() -> None:
    """AD-7, AD-14: a read that ends before the capture's stop is whole."""
    read = bounded(activity_from=100, activity_until=300).activity_rows(W1, start=100, end=299)
    assert [r.timestamp for r in read.rows] == [100, 200] and read.complete


def test_offline_read_reaching_the_stop_second_is_cut_short_there() -> None:
    """AD-7: rows from the second `activity_until` on may be missing, so reaching it is a cut-short read."""
    for end in (300, 400, None):
        read = bounded(activity_until=300).activity_rows(W1, start=0, end=end)
        assert [r.timestamp for r in read.rows] == [100, 200, 300] and not read.complete


def test_offline_read_starting_before_the_capture_is_cut_short_at_once() -> None:
    """AD-7, AD-14: an oldest-first read cannot skip the missing start, so it returns nothing and says so."""
    read = bounded(activity_from=150).activity_rows(W1, start=100, end=250)
    assert read == Read((), False)
    inside = bounded(activity_from=150).activity_rows(W1, start=150, end=250)
    assert [r.timestamp for r in inside.rows] == [200] and inside.complete


def test_synthetic_files_have_no_bounds() -> None:
    """FR-13, AD-14: every Synthetic Wallet reads as complete everywhere (null bounds in the file)."""
    wallet = sample_json.read_wallet(REPO / "sample_data" / "synthetic" / "sharp-trader.json")
    assert (wallet.activity_from, wallet.activity_until) == (None, None)


# --- the build ------------------------------------------------------------------------------------


def built(folder: Path) -> tuple[Path, Path, FakeLive]:
    zip_path, live = small_capture(folder)
    root = repo(folder / "repo")
    fetch_additions(zip_path, live, pick=PICKED, log=lambda _: None)  # type: ignore[arg-type]
    build(zip_path, root, pick=PICKED, log=lambda _: None)
    return zip_path, root, live


def snapshot(folder: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(folder.iterdir())}


def test_build_writes_the_picked_wallets_and_the_cutoff(tmp_path: Path) -> None:
    """AD-14, FR-12: one file per picked Wallet (not the spares) and dataset.json with the Cut-off Date."""
    zip_path, root, _ = built(tmp_path)
    out = root / REAL_DIR
    assert sorted(p.name for p in out.iterdir()) == sorted([f"{W1}.json", f"{W2}.json", "dataset.json"])
    dataset = json.loads((out / "dataset.json").read_text(encoding="utf-8"))
    assert dataset["cutoff"] == "2025-07-01"
    assert dataset["wallets"] == [W1, W2]
    assert dataset["capture"] == {"file": CAPTURE_NAME, "sha256": real_sample.sha256_of(zip_path)}
    assert dataset["additions"]["sha256"] == real_sample.sha256_of(zip_path.with_name(ADDITIONS_NAME))
    assert dataset["two_dates"] == []
    assert OfflineClient(sample_files(root)).real_addresses() == (W1, W2)


def test_build_takes_the_pick_from_the_code_and_refuses_one_not_in_the_zip(tmp_path: Path) -> None:
    """AD-14 (Edvard, 2026-11-23): the zip's pick file predates the 23 Oct swap, so the 10 come from
    spike/FINDINGS.md as a constant; a picked Wallet missing from the zip stops the build."""
    assert len(real_sample.PICK) == 10 and "0x0915962b4c6bc4505e7434a0de815a596a6667c3" in real_sample.PICK
    assert "0x8861f0bb5e0c19474ba73beeadc13ed8915beed6" not in real_sample.PICK  # a spare since 23 Oct
    zip_path, live = small_capture(tmp_path)
    absent = "0x" + "4" * 40
    with pytest.raises(BuildError, match=f"no capture of {absent}"):
        fetch_additions(zip_path, live, pick=[W1, absent], log=lambda _: None)  # type: ignore[arg-type]


def test_build_twice_gives_identical_bytes(tmp_path: Path) -> None:
    """AD-14: the same zip and additions give the same files, byte for byte."""
    zip_path, root, _ = built(tmp_path)
    first = snapshot(root / REAL_DIR)
    build(zip_path, root, pick=PICKED, log=lambda _: None)
    assert snapshot(root / REAL_DIR) == first


def test_built_file_replays_the_same_window_as_the_whole_capture(tmp_path: Path) -> None:
    """AD-13, AD-14: the written file gives the window the whole capture gave."""
    _, root, _ = built(tmp_path)
    window = positions_near(OfflineClient([root / REAL_DIR / f"{W1}.json"]), W1)
    assert sorted(p.condition_id for p in window.positions) == [cid(n) for n in (1, 2, 3, 4)]
    assert window.activity_read_until is None and len(window.activity) == 4


def test_capped_activity_makes_later_positions_not_fully_read(tmp_path: Path) -> None:
    """FR-12, AD-7: the capture stopped in Market 6's buy second, so the window's read is cut there."""
    _, root, _ = built(tmp_path)
    wallet = sample_json.read_wallet(root / REAL_DIR / f"{W2}.json")
    assert wallet.activity_until == T0 + 6 * DAY
    window = positions_near(OfflineClient([root / REAL_DIR / f"{W2}.json"]), W2)
    assert window.activity_read_until == T0 + 6 * DAY  # Markets 6 and 7 resolved after it: not fully read


def test_capped_start_cuts_the_read_at_once(tmp_path: Path) -> None:
    """FR-12, AD-7: a capture missing the start of the window's read gives no rows: every Position is not fully read."""
    w = {"closed": [raw_position(n) for n in (1, 2)], "before": [raw_trade(2, T0 + 2 * DAY)], "before_capped": True}
    zip_path = capture_zip(tmp_path, {W1: w})
    root = repo(tmp_path / "repo")
    fetch_additions(zip_path, FakeLive({cid(n): raw_gamma(n) for n in (1, 2)}), pick=[W1], log=lambda _: None)  # type: ignore[arg-type]
    build(zip_path, root, pick=[W1], log=lambda _: None)
    window = positions_near(OfflineClient([root / REAL_DIR / f"{W1}.json"]), W1)
    assert window.activity == () and window.activity_read_until is not None
    assert window.activity_read_until < min(m.start_time or 0 for m in window.markets)


def test_wrong_zip_is_refused_and_nothing_written(tmp_path: Path) -> None:
    """AD-14: a zip that does not match its SHA-256 file is refused; nothing is written."""
    zip_path, live = small_capture(tmp_path)
    root = repo(tmp_path / "repo")
    fetch_additions(zip_path, live, pick=PICKED, log=lambda _: None)  # type: ignore[arg-type]
    zip_path.with_name(CAPTURE_NAME + ".sha256").write_text("0" * 64 + f"  {CAPTURE_NAME}\n", encoding="utf-8")
    with pytest.raises(BuildError, match="does not match"):
        build(zip_path, root, pick=PICKED)
    assert not (root / REAL_DIR).exists()


def test_changed_additions_file_is_refused(tmp_path: Path) -> None:
    """AD-14: the additions file is checked against its own SHA-256 file too."""
    zip_path, live = small_capture(tmp_path)
    fetch_additions(zip_path, live, pick=PICKED, log=lambda _: None)  # type: ignore[arg-type]
    additions = zip_path.with_name(ADDITIONS_NAME)
    additions.write_bytes(additions.read_bytes().replace(b"Sports", b"Sp0rts"))
    with pytest.raises(BuildError, match=ADDITIONS_NAME):
        build(zip_path, repo(tmp_path / "repo"), pick=PICKED)


def test_missing_sha256_file_or_additions_is_refused(tmp_path: Path) -> None:
    """AD-14: no additions file, or no SHA-256 file, and the build refuses."""
    zip_path, _ = small_capture(tmp_path)
    root = repo(tmp_path / "repo")
    with pytest.raises(BuildError, match="--fetch"):
        build(zip_path, root, pick=PICKED)
    zip_path.with_name(CAPTURE_NAME + ".sha256").unlink()
    with pytest.raises(BuildError, match="SHA-256 file"):
        build(zip_path, root, pick=PICKED)


def test_fetch_asks_gamma_once_per_market_and_records_what_it_lacks(tmp_path: Path) -> None:
    """AD-2, AD-14: the one-off fetch asks Gamma once per Market, keeps only the parsed fields, and records Markets Gamma lacks; the build then refuses to serve them."""
    zip_path, live = small_capture(tmp_path)
    del live.known[cid(4)]  # an OPEN row's Market that Gamma does not know
    fetch_additions(zip_path, live, pick=PICKED, log=lambda _: None)  # type: ignore[arg-type]
    assert sorted(set(live.asked)) == sorted(live.asked) and cid(4) in live.asked
    additions = real_sample.read_additions(zip_path.with_name(ADDITIONS_NAME))
    assert additions.gamma_missing == {cid(4)}
    assert set(additions.gamma[cid(1)]) == {*real_sample.GAMMA_KEYS, "tags", "events"} - {"feeSchedule", "negRiskMarketID", "negRisk"}
    assert additions.gamma[cid(1)]["tags"] == [{"label": "Sports"}] and additions.gamma[cid(1)]["events"] == [{"id": "e1"}]
    asked = len(live.asked)
    fetch_additions(zip_path, live, pick=PICKED, log=lambda _: None)  # type: ignore[arg-type]
    assert len(live.asked) == asked  # never asked again
    with pytest.raises(BuildError, match="Gamma has no record"):
        build(zip_path, repo(tmp_path / "repo"), pick=PICKED)


def test_cut_closed_list_comes_from_the_additions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-14 (Edvard, 2026-11-23): a CLOSED list cut in the capture is fetched once, newest first, and noted."""
    monkeypatch.setattr(real_sample, "CAPTURE_CLOSED_CAP", 2)
    w = {"closed": [raw_position(1), raw_position(2)], "capped": True,
         "after": [raw_trade(n, T0 + n * DAY) for n in (1, 2, 3)]}
    zip_path = capture_zip(tmp_path, {W1: w})
    live = FakeLive({cid(n): raw_gamma(n) for n in (1, 2, 3)}, closed=[raw_position(n) for n in (1, 2, 3)])
    root = repo(tmp_path / "repo")
    fetch_additions(zip_path, live, pick=[W1], log=lambda _: None)  # type: ignore[arg-type]
    fetch_additions(zip_path, live, pick=[W1], log=lambda _: None)  # type: ignore[arg-type]
    assert live.list_calls == 1
    build(zip_path, root, pick=[W1], log=lambda _: None)
    window = positions_near(OfflineClient([root / REAL_DIR / f"{W1}.json"]), W1)
    assert {p.condition_id for p in window.positions} == {cid(1), cid(2), cid(3)}
    dataset = json.loads((root / REAL_DIR / "dataset.json").read_text(encoding="utf-8"))
    assert dataset["two_dates"] == [f"{W1}: CLOSED list fetched {dataset['additions']['fetched_on']}, the rest captured 2026-10-23"]


def test_trim_drops_open_rows_older_than_the_window(tmp_path: Path) -> None:
    """AD-14's trim: OPEN rows past the window's first left-out Market go; the window stays identical."""
    n_open = 2_003  # 3 more than the window holds (AD-8)
    w = {"open": [raw_position(n) for n in range(1, n_open + 1)]}
    zip_path = capture_zip(tmp_path, {W1: w})
    root = repo(tmp_path / "repo")
    fetch_additions(zip_path, FakeLive({cid(n): raw_gamma(n) for n in range(1, n_open + 1)}), pick=[W1], log=lambda _: None)  # type: ignore[arg-type]
    build(zip_path, root, pick=[W1], log=lambda _: None)  # refuses unless the replayed window is identical
    wallet = sample_json.read_wallet(root / REAL_DIR / f"{W1}.json")
    window = positions_near(OfflineClient([root / REAL_DIR / f"{W1}.json"]), W1)
    assert len(window.positions) == 2_000
    assert len(wallet.positions) == 2_001  # the window and the first Market left out
    assert {cid(1), cid(2)}.isdisjoint(m.condition_id for m in wallet.markets)


def test_neg_risk_check_names_markets_that_are_not_yes_no(tmp_path: Path) -> None:
    """AD-20 (Story 2.4's open check): every negRisk Market in the files is checked for Yes/No outcomes."""
    zip_path, live = small_capture(tmp_path)
    live.known[cid(1)] = raw_gamma(1, negRisk=True, negRiskMarketID="0xe")
    live.known[cid(2)] = raw_gamma(2, negRisk=True, negRiskMarketID="0xe", outcomes='["Up", "Down"]')
    root = repo(tmp_path / "repo")
    fetch_additions(zip_path, live, pick=PICKED, log=lambda _: None)  # type: ignore[arg-type]
    build(zip_path, root, pick=PICKED, log=lambda _: None)
    dataset = json.loads((root / REAL_DIR / "dataset.json").read_text(encoding="utf-8"))
    assert dataset["neg_risk_check"] == {"neg_risk_markets": 2, "not_yes_no": [cid(2)]}


def test_build_sample_command_outside_the_repository_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                                    capsys: pytest.CaptureFixture[str]) -> None:
    """AD-14: build-sample runs only from the repository folder."""
    monkeypatch.chdir(tmp_path)
    assert cli.main(["build-sample", str(tmp_path / CAPTURE_NAME)]) == 2
    assert "must run from the LiquidOracle repository folder" in capsys.readouterr().err


def test_build_sample_command_stops_plainly_without_the_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                            capsys: pytest.CaptureFixture[str]) -> None:
    """AD-14: a missing zip stops the command with one plain line, exit 2."""
    monkeypatch.chdir(repo(tmp_path))
    assert cli.main(["build-sample", str(tmp_path / CAPTURE_NAME)]) == 2
    assert "build-sample stopped:" in capsys.readouterr().err


# --- the committed real Wallets (FR-12, FR-14, NFR-10) --------------------------------------------


COMMITTED = REPO / REAL_DIR


def committed_wallets() -> list[str]:
    return json.loads((COMMITTED / "dataset.json").read_text(encoding="utf-8"))["wallets"]


def test_committed_set_is_the_ten_picked_wallets_with_the_cutoff() -> None:
    """FR-12, AD-14: the committed set is the 10 picked Wallets, read strictly, with the Cut-off Date."""
    dataset = json.loads((COMMITTED / "dataset.json").read_text(encoding="utf-8"))
    assert dataset["cutoff"] == "2025-07-01" and len(dataset["wallets"]) == 10
    assert OfflineClient(sample_files(REPO)).real_addresses() == tuple(sorted(dataset["wallets"]))
    for address in dataset["wallets"]:
        assert sample_json.read_wallet(COMMITTED / f"{address}.json").address == address


@pytest.mark.parametrize("address", committed_wallets() if (COMMITTED / "dataset.json").is_file() else [])
def test_nfr10_each_real_wallet_gets_its_verdict_within_10_seconds(address: str, tmp_path: Path) -> None:
    """FR-14, NFR-10: each real Wallet loads offline (sockets blocked) and its Verdict from stored data
    takes under 10 s. The limit is the requirement itself, far above the measured times."""
    client = OfflineClient([COMMITTED / f"{address}.json"])
    store = Store(tmp_path / "offline.db")
    fetch_wallet(client, store, address)
    started = time.perf_counter()
    result = stored_result(store, address, seed=SEED)
    elapsed = time.perf_counter() - started
    store.close()
    assert result is not None
    print(f"NFR-10: {address} Verdict {result.result.verdict.value} from stored data in {elapsed:.2f} s")
    assert elapsed < 10.0
