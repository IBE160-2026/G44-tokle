"""The real Wallets of the Sample Dataset: `build-sample` and its committed output (AD-14, FR-12, NFR-10; Story 2.6).

The build is tested on small made-up captures with the zip's layout, so the tests need neither the
raw capture (kept outside the repository) nor the network: the one-off fetch runs against a fake
live client. The committed `sample_data/real/` files are checked last, with sockets blocked.
"""

from __future__ import annotations

import dataclasses
import json
import time
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import liquidoracle.__main__ as cli
from liquidoracle.data import real_sample, sample_json, synthetic
from liquidoracle.data.offline import REAL_DIR, OfflineClient, sample_files
from liquidoracle.data.real_sample import ADDITIONS_NAME, CAPTURE_NAME, BuildError, build, fetch_additions
from liquidoracle.data.store import Store
from liquidoracle.data.window import positions_near
from liquidoracle.records import ActivityRow, ListedPosition, MarketHolder, Read, SampleWallet
from liquidoracle.services.fetch import fetch_wallet, stored_result
from liquidoracle.services.lookup import Lookup, Outcome

REPO = Path(__file__).resolve().parents[1]
SEED = 44
W1 = "0x" + "1" * 40
W2 = "0x" + "2" * 40
SPARE = "0x" + "3" * 40
PICKED = (W1, W2)
T0 = 1_740_000_000  # Feb 2025
DAY = 86_400


def cid(n: int) -> str:
    """Market n's condition id; n leads, so ids differ in the first 18 characters as the capture's list names need."""
    return f"0x{n:016x}{'0' * 48}"


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


def capture_zip(
    folder: Path, wallets: dict[str, dict[str, Any]], funnel: dict[str, dict[str, Any]] | None = None
) -> Path:
    """A zip with the capture's layout; each value holds `open`, `closed`, `capped`, `before`, `after`.

    `funnel` maps a condition id to its funnel entry's `closedTime`, `volumeNum` and its Market list
    (`partial`, `rows`), as the capture's Scan funnel stored them (Story 4.7); none by default."""
    path = folder / CAPTURE_NAME
    with zipfile.ZipFile(path, "w") as archive:
        # As in the real zip, its own pick file is out of date: the build never reads it.
        archive.writestr("sample/picked.json", json.dumps({"sample": [SPARE], "spares": list(wallets)}))
        entries = []
        for condition_id, market in (funnel or {}).items():
            entries.append({"conditionId": condition_id, "closedTime": market["closedTime"], "volumeNum": market["volumeNum"]})
            if "rows" in market:
                archive.writestr(real_sample.MARKET_LIST.format(condition_id[:18]),
                                 json.dumps({"partial": market.get("partial", False), "rows": market["rows"]}))
        archive.writestr(real_sample.FUNNEL_LIST, json.dumps(entries))
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


def test_shared_markets_do_not_make_the_client_reread_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-13 (found in Story 2.6): real Wallets share Markets. Fetching the second Wallet reads its own
    file once, not the first file again for every shared Market."""
    synthetic.write_small(tmp_path)
    sharp = sample_json.read_wallet(tmp_path / synthetic.SMALL_DIR / "sharp-trader.json")
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    sample_json.write_wallet(first, dataclasses.replace(sharp, address=W1))
    sample_json.write_wallet(second, dataclasses.replace(sharp, address=W2))  # the same 103 Markets (3 anchors)
    reads: list[str] = []
    real_read = sample_json.read_wallet
    monkeypatch.setattr(sample_json, "read_wallet", lambda path: reads.append(Path(path).name) or real_read(path))
    window = positions_near(OfflineClient([first, second]), W2)
    assert len(window.markets) == 103
    assert reads == ["b.json"]


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
    assert sorted(p.name for p in out.iterdir()) == sorted([f"{W1}.json", f"{W2}.json", "dataset.json", "funnel-markets.json"])
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


def test_trim_drops_open_rows_older_than_the_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-14's trim of a lookup-only Wallet: OPEN rows past the window's first left-out Market go; the window
    stays identical (a Wallet in the offline Scan keeps every row its before and after walks read, Story 4.7)."""
    monkeypatch.setitem(real_sample.LOOKUP_ONLY, W1, "a test")
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


def test_a_file_that_replays_another_window_is_not_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-14: if a written file gives another window than the whole capture, the build stops and keeps nothing."""
    zip_path, live = small_capture(tmp_path)
    root = repo(tmp_path / "repo")
    fetch_additions(zip_path, live, pick=PICKED, log=lambda _: None)  # type: ignore[arg-type]
    trimmed = real_sample._trimmed  # noqa: SLF001

    def drop_one(*args: Any) -> Any:
        wallet, window = trimmed(*args)
        return dataclasses.replace(wallet, positions=wallet.positions[1:]), window

    monkeypatch.setattr(real_sample, "_trimmed", drop_one)
    with pytest.raises(BuildError, match=f"{W1}: the written file gives another lookup window"):
        build(zip_path, root, pick=PICKED, log=lambda _: None)
    assert not (root / REAL_DIR / f"{W1}.json").exists()


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


def test_read_capture_stores_where_the_capped_reads_stopped(tmp_path: Path) -> None:
    """AD-7, AD-14: a capped newest-first read is whole only from the second after its oldest row;
    a capped oldest-first read stopped in the second of its newest row."""
    w = {"closed": [raw_position(1)], "before": [raw_trade(1, T0 + 50), raw_trade(1, T0 + 10)], "before_capped": True,
         "after": [raw_trade(1, T0 + 100), raw_trade(1, T0 + 300)], "after_capped": True}
    captured = real_sample.read_capture(capture_zip(tmp_path, {W1: w}), [W1])[W1]
    assert (captured.activity_from, captured.activity_until) == (T0 + 11, T0 + 300)
    uncapped = real_sample.read_capture(capture_zip(tmp_path, {W1: {"closed": [raw_position(1)]}}), [W1])[W1]
    assert (uncapped.activity_from, uncapped.activity_until) == (None, None)


def test_a_cut_open_list_stops_the_build(tmp_path: Path) -> None:
    """AD-14: the capture flags a cut list; a cut OPEN list has no rule, so the build refuses it."""
    w = {"closed": [raw_position(1)], "open": [raw_position(2)], "capped": True}  # fewer CLOSED rows than the cap
    with pytest.raises(BuildError, match=f"{W1}: the capture's OPEN list was cut short"):
        real_sample.read_capture(capture_zip(tmp_path, {W1: w}), [W1])


def test_an_empty_or_malformed_sha256_file_is_refused(tmp_path: Path) -> None:
    """AD-14: a SHA-256 file with no hash, or another text, never passes the check."""
    zip_path, _ = small_capture(tmp_path)
    sums = zip_path.with_name(CAPTURE_NAME + ".sha256")
    for text in ("", "not a hash\n"):
        sums.write_text(text, encoding="utf-8")
        with pytest.raises(BuildError, match="does not match"):
            real_sample.checked(zip_path)


def test_fetch_refuses_to_add_to_a_changed_additions_file(tmp_path: Path) -> None:
    """AD-14 (review): an edited additions file is never added to and given a fresh SHA-256 by --fetch."""
    zip_path, live = small_capture(tmp_path)
    fetch_additions(zip_path, live, pick=PICKED, log=lambda _: None)  # type: ignore[arg-type]
    additions = zip_path.with_name(ADDITIONS_NAME)
    additions.write_bytes(additions.read_bytes().replace(b"Sports", b"Sp0rts"))
    with pytest.raises(BuildError, match=ADDITIONS_NAME):
        fetch_additions(zip_path, live, pick=PICKED, log=lambda _: None)  # type: ignore[arg-type]


def test_a_failed_build_leaves_the_committed_set_as_it_was(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-14 (review): files are replayed in a staging folder; one bad Wallet, even the second,
    leaves sample_data/real/ exactly as it was, and no staging folder behind."""
    zip_path, root, _ = built(tmp_path)
    before = snapshot(root / REAL_DIR)
    trimmed = real_sample._trimmed  # noqa: SLF001

    def break_second(captured: Any, *rest: Any) -> Any:
        wallet, window = trimmed(captured, *rest)
        if captured.address == W2:
            wallet = dataclasses.replace(wallet, positions=wallet.positions[1:])
        return wallet, window

    monkeypatch.setattr(real_sample, "_trimmed", break_second)
    with pytest.raises(BuildError, match=W2):
        build(zip_path, root, pick=PICKED, log=lambda _: None)
    assert snapshot(root / REAL_DIR) == before
    assert not (root / real_sample.STAGING_DIR).exists()


def test_build_sample_command_builds_from_the_zip_without_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                                  capsys: pytest.CaptureFixture[str]) -> None:
    """AD-14: without --fetch the command makes no network call (sockets are blocked) and writes the set."""
    zip_path, live = small_capture(tmp_path)
    fetch_additions(zip_path, live, pick=PICKED, log=lambda _: None)  # type: ignore[arg-type]
    monkeypatch.setattr(real_sample, "PICK", PICKED)
    monkeypatch.chdir(repo(tmp_path / "repo"))
    assert cli.main(["build-sample", str(zip_path)]) == 0
    assert "Done: 2 real Wallets" in capsys.readouterr().out
    assert sorted(p.name for p in (tmp_path / "repo" / REAL_DIR).iterdir()) == sorted([f"{W1}.json", f"{W2}.json", "dataset.json", "funnel-markets.json"])


def test_build_sample_command_stops_plainly_on_a_broken_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                            capsys: pytest.CaptureFixture[str]) -> None:
    """AD-14 (review): a file that is not a zip, with a matching SHA-256 file, stops with one plain line."""
    broken = tmp_path / CAPTURE_NAME
    broken.write_bytes(b"not a zip")
    real_sample.write_sha256(broken)
    monkeypatch.chdir(repo(tmp_path / "repo"))
    assert cli.main(["build-sample", str(broken)]) == 2
    assert "build-sample stopped:" in capsys.readouterr().err


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


# --- the before and after parts and the real volume list (Story 4.7; AD-14, AD-21) ----------------

CUT = 1_751_328_000  # 1 July 2025, the default Cut-off Date
BEFORE_N = (1, 2)  # Markets bought and resolved before the cut-off (T0 is Feb 2025)
AFTER_N = (140, 141)  # Markets first bought after it (T0 + 140 days is mid-July 2025)


def two_sided(
    folder: Path,
    *,
    funnel: dict[str, dict[str, Any]] | None = None,
    extra: Iterable[dict[str, Any]] = (),
    gamma: dict[int, dict[str, Any]] | None = None,
    after_capped: bool = False,
) -> tuple[Path, FakeLive]:
    """W1 with two Markets on each side of the Cut-off Date; `extra` adds activity rows (a planted late one),
    `gamma` changes a Market's Gamma record, `after_capped` cuts the capture's after read short."""
    rows = [raw_trade(n, T0 + n * DAY) for n in (*BEFORE_N, *AFTER_N)] + list(extra)
    w1 = {
        "closed": [raw_position(n) for n in (*BEFORE_N, *AFTER_N)],
        "before": [row for row in rows if row["timestamp"] < CUT],
        "after": sorted((row for row in rows if row["timestamp"] >= CUT), key=lambda row: row["timestamp"]),
        "after_capped": after_capped,
    }
    known = {cid(n): raw_gamma(n, **(gamma or {}).get(n, {})) for n in (*BEFORE_N, *AFTER_N)}
    return capture_zip(folder, {W1: w1}, funnel), FakeLive(known)


def held(n: int, *rows: list[Any], partial: bool = False, closed: int | None = None) -> dict[str, Any]:
    """A funnel entry for Market n, resolved as `raw_gamma` says unless `closed` is given, with these holder rows."""
    return {"closedTime": iso(closed if closed is not None else T0 + n * DAY + DAY // 2), "volumeNum": 1_000_000.0 * n,
            "partial": partial, "rows": list(rows)}


def build_two_sided(folder: Path, **options: Any) -> Path:
    zip_path, live = two_sided(folder, **options)
    root = repo(folder / "repo")
    fetch_additions(zip_path, live, pick=[W1], log=lambda _: None)  # type: ignore[arg-type]
    build(zip_path, root, pick=[W1], log=lambda _: None)
    return root


def test_ad14_build_replays_the_before_and_after_parts(tmp_path: Path) -> None:
    """AD-14, FR-12 (Story 4.7): a Wallet in the offline Scan gets both parts around 1 July 2025 from Story 4.1's
    rules; its file replays each part as the whole capture gave it, and dataset.json counts them."""
    root = build_two_sided(tmp_path)
    path = root / REAL_DIR / f"{W1}.json"
    cutoff = datetime.fromtimestamp(CUT, UTC).date()
    before = positions_near(OfflineClient([path]), W1, cutoff, "before")
    after = positions_near(OfflineClient([path]), W1, cutoff, "after")
    assert sorted(p.condition_id for p in before.positions) == [cid(n) for n in BEFORE_N]
    assert sorted(p.condition_id for p in after.positions) == [cid(n) for n in AFTER_N]
    dataset = json.loads((root / REAL_DIR / "dataset.json").read_text(encoding="utf-8"))
    assert dataset["parts"] == {W1: {"before": 2, "after": 2}} and dataset["lookup_only"] == {}
    assert dataset["funnel"] == {"source": f"{real_sample.FUNNEL_LIST} and sample/market_*.json in {CAPTURE_NAME}",
                                 "file": "funnel-markets.json", "markets": 0, "holder_rows": 0}


@pytest.mark.parametrize("side", ["before", "after"])
def test_ad14_a_file_that_replays_another_part_is_not_kept(side: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-14 (Story 4.7, matrix "Replay differs"): if the written file gives another before or after part than the
    whole capture, the build stops naming the Wallet and side, and keeps nothing."""
    zip_path, live = two_sided(tmp_path)
    root = repo(tmp_path / "repo")
    fetch_additions(zip_path, live, pick=[W1], log=lambda _: None)  # type: ignore[arg-type]
    trimmed = real_sample._trimmed  # noqa: SLF001

    def other_part(*args: Any) -> Any:
        wallet, windows = trimmed(*args)
        return wallet, {**windows, side: dataclasses.replace(windows[side], positions=())}

    monkeypatch.setattr(real_sample, "_trimmed", other_part)
    with pytest.raises(BuildError, match=f"{W1}: the written file gives another {side} window"):
        build(zip_path, root, pick=[W1], log=lambda _: None)
    assert not (root / REAL_DIR).exists() or not any((root / REAL_DIR).iterdir())


def test_ad14_a_lookup_only_wallet_keeps_its_lookup_window_and_no_funnel_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-14 (Edvard, 2026-11-27, matrix "Heavy two"): a lookup-only Wallet gets no before or after part and no
    holder row, even on a Market it holds; dataset.json says why. The pick names exactly 0xd218e4 and 0x63d43b."""
    assert set(real_sample.LOOKUP_ONLY) == {"0xd218e474776403a330142299f7796e8ba32eb5c9",
                                            "0x63d43bbb87f85af03b8f2f9e2fad7b54334fa2f1"}
    monkeypatch.setitem(real_sample.LOOKUP_ONLY, W1, "a test")
    root = build_two_sided(tmp_path, funnel={cid(1): held(1, [W1, "CLOSED", 3.0, 0, 1, 0.4])})
    dataset = json.loads((root / REAL_DIR / "dataset.json").read_text(encoding="utf-8"))
    assert dataset["parts"] == {} and dataset["lookup_only"] == {W1: "a test"}
    assert sample_json.read_funnel(root / REAL_DIR / real_sample.FUNNEL_FILE) == sample_json.FunnelFile({}, {})


def test_ad21_real_volume_list_copies_the_captured_rows(tmp_path: Path) -> None:
    """AD-21, AD-14 (Story 4.7): each completely read funnel Market the Wallet holds is listed with its volume and
    the Wallet's rows as captured; the token is the one with the row's final price. A partial Market, one nobody
    in the Scan holds and one with no captured list are left out."""
    other = "0x" + "9" * 40
    funnel = {
        cid(1): held(1, [W1, "CLOSED", 3.0, 0, 1, 0.4], [other, "CLOSED", 9.0, 0, 1, 0.1]),
        cid(2): held(2, [W1, "OPEN", 0, 10.0, 0, 0.4], partial=True),
        cid(3): held(3, [other, "CLOSED", 1.0, 0, 1, 0.5]),
        cid(4): {"closedTime": iso(T0 + 4 * DAY), "volumeNum": 5.0},  # no Market list in the capture
    }
    root = build_two_sided(tmp_path, funnel=funnel)
    found = sample_json.read_funnel(root / REAL_DIR / real_sample.FUNNEL_FILE)
    assert found.volumes == {cid(1): 1_000_000.0}
    assert found.holders == {cid(1): (MarketHolder(W1, "11", "CLOSED", 3.0, 0.0, 0.4),)}


def test_ad21_a_late_redemption_is_allowed(tmp_path: Path) -> None:
    """AD-21 (Edvard's no-peeking check): a redemption after the Cut-off Date pays at an outcome known before it,
    so it does not stop the build."""
    late = {"type": "REDEEM", "condition_id": cid(1), "timestamp": CUT + DAY, "size": 10.0, "usdc_size": 10.0,
            "price": 1.0, "token_id": None, "side": None, "is_combo": False}
    root = build_two_sided(tmp_path, funnel={cid(1): held(1, [W1, "CLOSED", 6.0, 0, 1, 0.4])}, extra=[late])
    assert cid(1) in sample_json.read_funnel(root / REAL_DIR / real_sample.FUNNEL_FILE).volumes


@pytest.mark.parametrize(
    ("planted", "match"),
    [
        ("trade after the cut-off", "TRADE row"),
        ("trade after resolution", "TRADE row"),
        ("final price 0.5", "final price"),
        ("resolved after the cut-off", "did not resolve before the Cut-off Date"),
        ("token not held", "on none of the Wallet's positions lists"),
    ],
)
def test_ad21_no_peeking_check_stops_the_build(planted: str, match: str, tmp_path: Path) -> None:
    """AD-21 (Edvard, 2026-11-27, matrix "Late row"): the build stops, keeping nothing, on any copied row that could
    hold something from after the Cut-off Date: a trade from the cut-off or the Market's resolution on, a final price
    that is not 0 or 1, a Market resolved on or after the cut-off; and on a row for a token the Wallet never held."""
    row: list[Any] = [W1, "CLOSED", 3.0, 0, 1, 0.4]
    extra: list[dict[str, Any]] = []
    entry = held(1, row)
    if planted == "trade after the cut-off":
        extra = [raw_trade(1, CUT + DAY)]
    elif planted == "trade after resolution":
        extra = [raw_trade(1, T0 + DAY + DAY // 2)]  # the second Market 1 resolves in
    elif planted == "final price 0.5":
        row[4] = 0.5
    elif planted == "resolved after the cut-off":
        entry = held(1, row, closed=CUT)
    else:
        row[4] = 0  # the losing token "12", which W1 never held
    zip_path, live = two_sided(tmp_path, funnel={cid(1): entry}, extra=extra)
    root = repo(tmp_path / "repo")
    fetch_additions(zip_path, live, pick=[W1], log=lambda _: None)  # type: ignore[arg-type]
    with pytest.raises(BuildError, match=match):
        build(zip_path, root, pick=[W1], log=lambda _: None)
    assert not (root / REAL_DIR).exists() or not any((root / REAL_DIR).iterdir())


def test_ad14_fetch_walks_the_parts_the_build_will_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-14 (Story 4.7, matrix "Market record missing"): `--fetch` walks each Wallet's before and after parts as
    the build will, so a Market record only those parts need is fetched once; a lookup-only Wallet walks only its
    lookup window."""
    zip_path, live = small_capture(tmp_path)
    monkeypatch.setitem(real_sample.LOOKUP_ONLY, W2, "a test")
    walked: list[tuple[str, str | None]] = []
    real_walk = real_sample.positions_near

    def walk(client: Any, wallet: str, cutoff: Any = None, side: str | None = None) -> Any:
        walked.append((wallet, side))
        return real_walk(client, wallet, cutoff, side)

    monkeypatch.setattr(real_sample, "positions_near", walk)
    fetch_additions(zip_path, live, pick=PICKED, log=lambda _: None)  # type: ignore[arg-type]
    assert walked == [(W1, None), (W1, "before"), (W1, "after"), (W2, None)]


EVENT = "0x" + "e" * 64  # Market 1's negative-risk event, when the case makes it one


def market_row(kind: str, condition_id: str, t: int, *, combo: bool = False) -> dict[str, Any]:
    """A non-trade activity row (split, merge, conversion), or with `combo` a combo trade, as the Data API sends it."""
    if combo:
        return {**raw_trade(1, t), "is_combo": True}
    return {"type": kind, "condition_id": condition_id, "timestamp": t, "size": 10.0, "usdc_size": 10.0, "price": 0.0,
            "token_id": None, "side": None, "is_combo": False}


@pytest.mark.parametrize(
    ("planted", "match"),
    [
        ("split after the cut-off", "SPLIT row"),
        ("merge after the cut-off", "MERGE row"),
        ("conversion in the event after the cut-off", "CONVERSION row"),
        ("combo trade after the cut-off", "combo row"),
        ("capture cut short", "did not read every activity row"),
        ("Gamma resolved at the cut-off", "did not resolve before the Cut-off Date"),
        ("Gamma never resolved", "did not resolve before the Cut-off Date"),
    ],
)
def test_ad21_no_peeking_check_sees_every_late_holding_row(planted: str, match: str, tmp_path: Path) -> None:
    """AD-21 (Edvard's no-peeking check, review of Story 4.7): a late split, merge or combo trade in the Market, a
    late conversion in its negative-risk event (whose row carries the event's id), a capture that stopped reading
    activity, and a Gamma record resolved on or after the cut-off or not at all each stop the build."""
    options: dict[str, Any] = {}
    if planted.startswith("split"):
        options["extra"] = [market_row("SPLIT", cid(1), CUT + DAY)]
    elif planted.startswith("merge"):
        options["extra"] = [market_row("MERGE", cid(1), CUT + DAY)]
    elif planted.startswith("conversion"):
        options["gamma"] = {1: {"negRisk": True, "negRiskMarketID": EVENT}}
        options["extra"] = [market_row("CONVERSION", EVENT, CUT + DAY)]
    elif planted.startswith("combo"):
        options["extra"] = [market_row("TRADE", cid(1), CUT + DAY, combo=True)]
    elif planted == "capture cut short":
        options["after_capped"] = True
    elif planted == "Gamma resolved at the cut-off":
        options["gamma"] = {1: {"closedTime": iso(CUT)}}
    else:
        options["gamma"] = {1: {"outcomePrices": '["0.5", "0.5"]'}}
    zip_path, live = two_sided(tmp_path, funnel={cid(1): held(1, [W1, "CLOSED", 3.0, 0, 1, 0.4])}, **options)
    root = repo(tmp_path / "repo")
    fetch_additions(zip_path, live, pick=[W1], log=lambda _: None)  # type: ignore[arg-type]
    with pytest.raises(BuildError, match=match):
        build(zip_path, root, pick=[W1], log=lambda _: None)
    assert not (root / REAL_DIR).exists() or not any((root / REAL_DIR).iterdir())


def test_ad14_two_funnel_markets_with_one_list_name_stop_the_build(tmp_path: Path) -> None:
    """AD-14 (review of Story 4.7): the capture names a Market's list by the first 18 characters of its id, so two
    funnel Markets sharing them would silently swap lists; the build stops instead."""
    twin = cid(1)[:18] + "f" * 48
    entry = {"closedTime": iso(T0), "volumeNum": 1.0}  # no list of its own: the name is already taken
    zip_path, _ = two_sided(tmp_path, funnel={cid(1): held(1, [W1, "CLOSED", 3.0, 0, 1, 0.4]), twin: entry})
    captured = real_sample.read_capture(zip_path, [W1])
    with pytest.raises(BuildError, match="share the list name"):
        real_sample.real_funnel(zip_path, captured, {}, [W1], tmp_path)


def test_ad14_real_volume_list_needs_the_funnel_and_a_file_for_each_market(tmp_path: Path) -> None:
    """AD-14 (Story 4.7): a capture without its funnel list stops the build; a listed Market no written file holds
    stops it too, since the offline Scan could not read that Market."""
    zip_path, _ = two_sided(tmp_path, funnel={cid(1): held(1, [W1, "CLOSED", 3.0, 0, 1, 0.4])})
    captured = real_sample.read_capture(zip_path, [W1])
    markets = {cid(1): real_sample.parse_market(raw_gamma(1))}
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(BuildError, match="in no written file"):
        real_sample.real_funnel(zip_path, captured, markets, [W1], empty)
    bare = tmp_path / "bare.zip"
    with zipfile.ZipFile(zip_path) as source, zipfile.ZipFile(bare, "w") as target:
        for name in source.namelist():
            if name != real_sample.FUNNEL_LIST:
                target.writestr(name, source.read(name))
    with pytest.raises(BuildError, match="funnel_markets_20250701.json"):
        real_sample.real_funnel(bare, captured, markets, [W1], empty)


# --- the committed real Wallets (FR-12, FR-14, NFR-10) --------------------------------------------


COMMITTED = REPO / REAL_DIR
CAPPED = (
    "0xd218e474776403a330142299f7796e8ba32eb5c9",
    "0x63d43bbb87f85af03b8f2f9e2fad7b54334fa2f1",
    "0x7298060b1844a4c4ca0578146ab3f5e76aa1fcfc",
)


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


@pytest.mark.parametrize("address", committed_wallets() if (COMMITTED / "dataset.json").is_file() else [])
def test_fr14_each_real_wallet_opens_a_verdict_page_offline(address: str, tmp_path: Path) -> None:
    """FR-14, UX-DR17: each committed real Wallet, loaded as load-sample does, opens a Verdict page."""
    client = OfflineClient(sorted(COMMITTED.glob("0x*.json")))
    store = Store(tmp_path / "offline.db")
    fetch_wallet(client, store, address)
    page = Lookup(client, store, seed=SEED).wallet_page(address)
    store.close()
    assert page.outcome is Outcome.VERDICT and page.card is not None


@pytest.mark.parametrize("address", CAPPED)
def test_fr12_capped_real_wallets_are_not_fully_read(address: str, tmp_path: Path) -> None:
    """FR-12, AD-7: where the capture stopped before the window's trades, every window Position is
    "not fully read" (0xd218e4 and 0x63d43b both ways, 0x729806 before the date), never patched."""
    client = OfflineClient([COMMITTED / f"{address}.json"])
    store = Store(tmp_path / "offline.db")
    fetch_wallet(client, store, address)
    snapshot = store.latest_snapshot(address)
    store.close()
    assert snapshot is not None and len(snapshot.positions) > 0
    assert len(snapshot.not_fully_read()) == len(snapshot.positions)


# The committed real Wallets' results as recorded in docs/real-wallets.md (Verdict, tested bets,
# Real PnL in whole dollars). A change to any rule that moves one must update that note too.
RECORDED = {
    "0xcf0d7f69cf162918b33fc1ea7449583fa537132d": ("Likely skilled", 139, 822_007),
    "0x73648309111de9f9d4e2a58a50f803fa7d30d44e": ("No evidence of skill", 229, -633),
    "0xd218e474776403a330142299f7796e8ba32eb5c9": ("Not enough data", 0, 0),
    "0xd3a6e523c440f94f9259398fbcf7b5cc5ccffd55": ("No evidence of skill", 641, 117_604),  # 118_065 before Story 2.8 (fees)
    "0x63d43bbb87f85af03b8f2f9e2fad7b54334fa2f1": ("Not enough data", 0, 0),
    "0x94884db79666a1a34c46d03fb4f8e9cbcaf6b5a6": ("No evidence of skill", 1_423, -1_103),
    "0x7298060b1844a4c4ca0578146ab3f5e76aa1fcfc": ("Not enough data", 0, 0),
    "0x0f4b0a6b7f82108924ac9c8320ed91028f504183": ("No evidence of skill", 210, -189),  # -188 before Story 2.8
    "0x0915962b4c6bc4505e7434a0de815a596a6667c3": ("Not enough data", 14, -49_616),  # -49_571 before Story 2.8
    "0x29306ddc4724e24a23bf1c8679aa034376ea9dcb": ("Not enough data", 18, 295),
}


@pytest.mark.parametrize("address", sorted(RECORDED))
def test_nfr13_each_real_wallet_gives_its_recorded_result(address: str, tmp_path: Path) -> None:
    """FR-12, NFR-13 (review): each committed real Wallet gives the Verdict, tested bets and Real PnL
    recorded in docs/real-wallets.md, so the note cannot go stale without a test failing."""
    client = OfflineClient([COMMITTED / f"{address}.json"])
    store = Store(tmp_path / "offline.db")
    fetch_wallet(client, store, address)
    result = stored_result(store, address, seed=SEED)
    store.close()
    assert result is not None
    assert (result.result.verdict.value, result.result.tested_count, round(result.result.real_pnl)) == RECORDED[address]
