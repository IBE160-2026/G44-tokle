"""The Watchlist and the Verdict page a Watchlist row opens (FR-11, FR-16, UX-DR33, UX-DR34, UX-DR37, AD-21, AD-22;
Story 4.5).

Two kinds of finished Scan are used. `scanned` runs a real Scan on the routed fake from `test_scan.py`
(four Markets in the set, two partial, real Wallets cut from the capture), so its results rest on real
frozen snapshots. `hand_scan` writes a finished Scan's rows straight into the database, for exact
p-values, Verdicts and flags. No socket is opened (AD-17).
"""

from __future__ import annotations

import dataclasses
import re
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
from flask.testing import FlaskClient
from markupsafe import Markup
from test_scan_job import SEED, SHORTLIST, SIZE, Rig, rig_for, start

from liquidoracle.core import phrases
from liquidoracle.data.store import SCAN_WHOLE, Store
from liquidoracle.data.window import cutoff_at
from liquidoracle.records import Verdict
from liquidoracle.services import watchlist as wl
from liquidoracle.services.jobs import Jobs
from liquidoracle.services.lookup import Lookup
from liquidoracle.services.scans_page import ScansPage
from liquidoracle.services.watchlist import Watchlists, scan_whole_result
from liquidoracle.settings import Settings
from liquidoracle.web import create_app

CUTOFF = cutoff_at(date(2025, 7, 1))
SKILLED = Verdict.SKILLED.value


@dataclass(frozen=True)
class Row:
    """One hand-made `scan_whole` result."""

    wallet: str
    verdict: str = SKILLED
    p_value: float | None = 0.001
    tested: int = 100
    real_pnl: float = 1_000.0
    unread: bool = False


def wallet(n: int) -> str:
    return f"0x{n:040x}"


def hand_scan(
    path: Path,
    rows: list[Row],
    *,
    markets: tuple[tuple[str, float, str], ...] = (("0x" + "a" * 64, 9e6, "used"),),
    shortlist: int = 9,
    step: str = "done",
    as_of: int = 1_790_000_000,
    seed: int = SEED,
) -> int:
    """A Scan whose rows are written straight into the database (the test's own write; no worker runs)."""
    db = sqlite3.connect(path)
    with db:  # commits; the connection is closed below, so Windows can remove the test's folder
        scan_id = int(db.execute(
            "INSERT INTO scan (cutoff, size, seed, as_of, step, candidate_count) VALUES (?, ?, ?, ?, ?, ?)",
            (CUTOFF, len(rows), seed, as_of, step, shortlist),
        ).lastrowid)
        db.executemany(
            "INSERT INTO scan_market (scan_id, seq, condition_id, volume, state) VALUES (?, ?, ?, ?, ?)",
            [(scan_id, i, cid, volume, state) for i, (cid, volume, state) in enumerate(markets)],
        )
        db.executemany(
            "INSERT INTO scan_wallet (scan_id, seq, wallet, estimate, top) VALUES (?, ?, ?, ?, 0)",
            [(scan_id, i, wallet(1000 + i), 1.0) for i in range(shortlist)],
        )
        for row in rows:
            for scope in (SCAN_WHOLE, "scan_before"):
                db.execute(
                    "INSERT INTO scan_result (scan_id, wallet, scope, cutoff, seed, verdict, p_value, tested_count,"
                    " real_pnl, not_fully_read) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (scan_id, row.wallet, scope, CUTOFF, seed, row.verdict, row.p_value, row.tested, row.real_pnl,
                     int(row.unread)),
                )
    db.close()
    return scan_id


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    made = Store(tmp_path / "live.db")
    yield made
    made.close()


@pytest.fixture(scope="module")
def scanned(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Rig, int]]:
    """A real finished Scan (shared: running one takes a few seconds)."""
    rig = rig_for(tmp_path_factory.mktemp("scanned") / "scan.db")
    scan_id, _ = start(rig)
    assert rig.worker.run_once()
    yield rig, scan_id
    rig.store.close()


def web_over(store: Store) -> FlaskClient:
    return create_app(Settings(offline=False), Lookup(None, store, seed=SEED, jobs=Jobs(store))).test_client()


def text(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


# --- the Scan header (UX-DR33, AD-21) ------------------------------------------------------------------------


def test_ux_dr33_the_scan_header_states_the_population_shortlist_and_partial_markets(scanned: tuple[Rig, int]) -> None:
    """UX-DR33, AD-21, FR-16: title, ledes with the Cut-off Date and run date, the population line with the Markets
    used of the stored set and the Seed, the shortlist line (Edvard, 2026-11-26), the summary card, and the
    disclosure naming each partial Market by short ID, volume and resolution date (no title is stored)."""
    rig, scan_id = scanned
    view = Watchlists(rig.store).view(scan_id)
    assert view is not None
    header = view.header
    results = [r for r in rig.store.scan_results(scan_id) if r.scope == SCAN_WHOLE]
    run = phrases.run_date(rig.store.scan(scan_id).as_of)
    assert header.title == f"Scan of {len(results)} Wallets" == f"Scan of {SIZE} Wallets"
    assert header.lede == f"Cut-off Date 1 July 2025 · run {run}"
    assert header.population == (
        "Markets resolved in the 90 days before the Cut-off Date, top 100 by volume · 2 of 4 Markets used · Seed 44"
    )
    unread = sum(r.not_fully_read for r in results)
    assert header.shortlist == (
        f"Shortlist of about {SHORTLIST} by a quick profit estimate · {unread} "
        f"{'Wallet' if unread == 1 else 'Wallets'} not fully read"
    )
    skilled = sum(r.verdict == SKILLED for r in results)
    assert header.summary == (("Wallets scanned", "3"), (f"Rated {SKILLED}", str(skilled)), ("Scan run", run))
    assert header.partial_title == "2 Markets not used: partial"
    partial = {m.condition_id for m in rig.store.scan_markets(scan_id) if m.state == "partial"}
    assert {p.short_id for p in header.partial} == {f"{cid[:6]}…{cid[-4:]}" for cid in partial}
    for market in header.partial:
        assert re.fullmatch(r"\$[\d,]+ volume · resolved \d{1,2} (June|May|April) 2025", market.details), market


def test_ux_dr33_no_partial_market_means_no_disclosure(store: Store, tmp_path: Path) -> None:
    """UX-DR33: every Market used, so no disclosure; "1 of 1 Markets used" counts the stored set."""
    scan_id = hand_scan(tmp_path / "live.db", [Row(wallet(1))])
    view = Watchlists(store).view(scan_id)
    assert view is not None and view.header.partial == () and view.header.partial_title == ""
    assert "· 1 of 1 Markets used ·" in view.header.population
    page = web_over(store).get(f"/scans/{scan_id}/watchlist").get_data(as_text=True)
    assert "<details" not in page


def test_ux_dr33_a_partial_market_without_a_stored_record_has_no_date(store: Store, tmp_path: Path) -> None:
    """AD-9: a partial Market whose Gamma record is not stored is named by short ID and volume only."""
    cid = "0x" + "b" * 64
    scan_id = hand_scan(tmp_path / "live.db", [Row(wallet(1))], markets=((cid, 1_234_567.4, "partial"),))
    view = Watchlists(store).view(scan_id)
    assert view is not None
    assert view.header.partial_title == "1 Market not used: partial"
    assert [(p.short_id, p.details) for p in view.header.partial] == [("0xbbbb…bbbb", "$1,234,567 volume")]
    assert "0 of 1 Markets used" in view.header.population


# --- the table and the luck sentence (UX-DR34, FR-16) ----------------------------------------------------


def test_fr16_only_skilled_wallets_sorted_by_p_value_then_real_pnl(store: Store, tmp_path: Path) -> None:
    """FR-16, UX-DR34: the rows are the `scan_whole` results rated Skilled (high confidence), smallest p-value
    first, a tie by the larger Real PnL, then the address; no other Verdict is listed."""
    rows = [
        Row(wallet(1), p_value=0.004, real_pnl=100.0),
        Row(wallet(2), p_value=0.0001, real_pnl=50.0),
        Row(wallet(3), p_value=0.004, real_pnl=500.0),
        Row(wallet(4), verdict=Verdict.LIKELY_SKILLED.value, p_value=0.03),
        Row(wallet(5), verdict=Verdict.NO_EVIDENCE.value, p_value=0.4),
        Row(wallet(6), verdict=Verdict.NOT_ENOUGH_DATA.value, p_value=None, tested=12),
        Row(wallet(7), p_value=0.004, real_pnl=500.0),
    ]
    view = Watchlists(store).view(hand_scan(tmp_path / "live.db", rows))
    assert view is not None
    assert [r.address for r in view.rows] == [wallet(2), wallet(3), wallet(7), wallet(1)]
    assert view.header.title == "Scan of 7 Wallets"
    assert view.header.summary[1] == (f"Rated {SKILLED}", "4")


def test_fr16_the_luck_sentence_counts_only_wallets_with_a_verdict(store: Store, tmp_path: Path) -> None:
    """FR-16, PRD Glossary (Edvard, 2026-11-26): Minimum Luck Passes counts the Wallets that got a Verdict, so
    150 of a Scan of 163 with 13 *Not enough data* reads "about 2 of the 150 Wallets with a Verdict"."""
    rows = [Row(wallet(i), verdict=Verdict.NO_EVIDENCE.value, p_value=0.5) for i in range(150)]
    rows += [Row(wallet(500 + i), verdict=Verdict.NOT_ENOUGH_DATA.value, p_value=None, tested=3) for i in range(13)]
    view = Watchlists(store).view(hand_scan(tmp_path / "live.db", rows))
    assert view is not None
    assert view.header.title == "Scan of 163 Wallets"
    assert view.luck == phrases.luck_passes(150)
    assert view.luck.startswith("At least about 2 of the 150 Wallets with a Verdict would pass by luck alone")


def test_ux_dr34_a_row_reads_its_result(store: Store, tmp_path: Path) -> None:
    """UX-DR34: short address with its link name, the pill's Verdict and dots, the FR-8 odds phrase, the count and
    the money from `core/phrases` (AD-25), and the Not fully read flag."""
    view = Watchlists(store).view(hand_scan(tmp_path / "live.db", [
        Row(wallet(0xABC), p_value=1 / 10_001, tested=1_234, real_pnl=-40_180.4, unread=True),
    ]))
    assert view is not None
    (row,) = view.rows
    short = f"{wallet(0xABC)[:6]}…{wallet(0xABC)[-4:]}"
    assert (row.short_address, row.link_label) == (short, f"Open Verdict for Wallet {short}")
    assert (row.verdict, row.filled_dots) == (SKILLED, 3)
    assert row.odds == phrases.odds(1 / 10_001)
    assert (row.bets, row.real_pnl, row.not_fully_read) == ("1,234", phrases.money(-40_180.4), True)


def test_ux_dr34_the_watchlist_page(store: Store, tmp_path: Path) -> None:
    """UX-DR33, UX-DR34, UX-DR8: tab title, eyebrow, the Scan tabs as links in a navigation region named "Scan" with
    the current page marked, the info box above the table, the caption, the column headers with no rank column,
    in-app links with no external-link icon, and the tag's tooltip sentence in the page without JavaScript."""
    scan_id = hand_scan(tmp_path / "live.db", [Row(wallet(1), unread=True), Row(wallet(2), p_value=0.0005)])
    page = web_over(store).get(f"/scans/{scan_id}/watchlist").get_data(as_text=True)
    assert "<title>Watchlist · 1 Jul 2025 · LiquidOracle</title>" in page
    assert '<p class="eyebrow">Wallet scan</p>' in page
    nav = re.search(r'<nav class="scan-tabs" aria-label="Scan">(.*?)</nav>', page, re.S)
    assert nav and re.search(rf'<a href="/scans/{scan_id}/watchlist" aria-current="page">Watchlist</a>', nav.group(1))
    assert 'role="tablist"' not in page and 'role="tab"' not in page
    assert page.index('class="info-box"') < page.index("<table")
    assert f'<p class="sub" id="watchlist-caption">{wl.CAPTION}</p>' in page
    assert '<table class="scan-table watch-table" aria-describedby="watchlist-caption">' in page
    headers = [text(h) for h in re.findall(r"<th scope=\"col\"[^>]*>(.*?)</th>", page, re.S)]
    assert headers == ["Wallet", "Verdict", "Odds (with no edge)", "Resolved bets", "Real PnL"]
    links = re.findall(r'<a class="row-link" href="([^"]+)" aria-label="([^"]+)">([^<]+)</a>', page)
    assert [href for href, _, _ in links] == [f"/scans/{scan_id}/wallet/{wallet(2)}", f"/scans/{scan_id}/wallet/{wallet(1)}"]
    assert all(label.endswith(shown) for _, label, shown in links)  # WCAG 2.5.3: the name holds the visible text
    assert 'target="_blank"' not in page and "external" not in page
    tag = re.search(r'<button class="info-tag" type="button" aria-describedby="(tip-\d+)">Not fully read</button>', page)
    assert tag and re.search(rf'role="tooltip" id="{tag.group(1)}">{re.escape(str(Markup.escape(wl.NOT_FULLY_READ_TIP)))}<', page)
    assert page.count("Not fully read</button>") == 1
    assert 'role="region" aria-labelledby="watchlist-title" tabindex="0"' in page
    assert re.search(r'<a href="/scans" aria-current="true">Scan wallets</a>', page)


def test_sm_c2_an_empty_watchlist_is_a_plain_result(store: Store, tmp_path: Path) -> None:
    """SM-C2, FR-16: no Wallet rated Skilled shows the sentence instead of the table, and the info box stays."""
    scan_id = hand_scan(tmp_path / "live.db", [Row(wallet(1), verdict=Verdict.NO_EVIDENCE.value, p_value=0.3)])
    view = Watchlists(store).view(scan_id)
    assert view is not None and view.rows == ()
    page = web_over(store).get(f"/scans/{scan_id}/watchlist").get_data(as_text=True)
    assert "<table" not in page and 'class="info-box"' in page
    assert f"No Wallet in this Scan was rated <em>{SKILLED}</em>." in page
    assert "Error" not in page


# --- not found (FR-16: results of an unfinished Scan are never shown) -----------------------------------


@pytest.mark.parametrize("step", ["created", "markets", "shortlisted", "ranked"])
def test_fr16_an_unfinished_scan_has_no_watchlist(store: Store, tmp_path: Path, step: str) -> None:
    """FR-16, UX-DR31: a Scan not yet done shows no results: its Watchlist and Verdict pages are *Page not found*."""
    scan_id = hand_scan(tmp_path / "live.db", [Row(wallet(1))], step=step)
    web = web_over(store)
    assert Watchlists(store).view(scan_id) is None
    assert web.get(f"/scans/{scan_id}/watchlist").status_code == 404
    assert web.get(f"/scans/{scan_id}/wallet/{wallet(1)}").status_code == 404


def test_unknown_scans_and_wallets_are_not_found(scanned: tuple[Rig, int]) -> None:
    """An unknown Scan, an address with no result in that Scan, or a malformed address is *Page not found*; an
    address in capitals is sent to its lower-case page (FR-1)."""
    rig, scan_id = scanned
    web = web_over(rig.store)
    tested = next(r.wallet for r in rig.store.scan_results(scan_id) if r.scope == SCAN_WHOLE)
    assert web.get("/scans/999/watchlist").status_code == 404
    assert web.get(f"/scans/999/wallet/{tested}").status_code == 404
    assert web.get(f"/scans/{scan_id}/wallet/{wallet(77)}").status_code == 404
    assert web.get(f"/scans/{scan_id}/wallet/0x123").status_code == 404
    moved = web.get(f"/scans/{scan_id}/wallet/{tested.upper().replace('0X', '0x')}")
    assert moved.status_code == 301 and moved.headers["Location"].endswith(f"/scans/{scan_id}/wallet/{tested}")


def test_ad19_a_missing_frozen_snapshot_is_not_found(scanned: tuple[Rig, int], monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-19: a Verdict from a Scan rests only on its frozen snapshots; one gone means no page, never a guess."""
    rig, scan_id = scanned
    with_parts = next(r for r in rig.store.scan_results(scan_id) if r.scope == SCAN_WHOLE and r.fetch_id is not None)
    monkeypatch.setattr(rig.store, "snapshot", lambda fetch_id: None)
    assert Watchlists(rig.store).verdict(scan_id, with_parts.wallet) is None


# --- the Verdict opened from a Scan (UX-DR37, AD-22) -----------------------------------------------------


def test_ad22_the_verdict_from_a_scan_equals_its_stored_result(scanned: tuple[Rig, int]) -> None:
    """AD-22: for every tested Wallet, the result recomputed from the frozen snapshots with the Scan's Seed and as-of
    time equals the stored `scan_whole` row exactly, and its Verdict card says the same."""
    rig, scan_id = scanned
    scan = rig.store.scan(scan_id)
    assert scan is not None
    results = [r for r in rig.store.scan_results(scan_id) if r.scope == SCAN_WHOLE]
    assert any(r.after_fetch_id is not None for r in results), "the scenario should freeze an after part"
    for stored in results:
        parts = [rig.store.snapshot(f) for f in (stored.fetch_id, stored.after_fetch_id) if f is not None]
        again = scan_whole_result(stored.wallet, parts, scan=scan).result
        assert (again.verdict.value, again.p_value, again.tested_count, again.real_pnl) == (
            stored.verdict, stored.p_value, stored.tested_count, stored.real_pnl
        ), stored.wallet
        found = Watchlists(rig.store).verdict(scan_id, stored.wallet)
        assert found is not None and found.page.card is not None
        assert found.page.card.verdict == stored.verdict
        assert found.page.card.bets == phrases.count(stored.tested_count)
        assert found.page.card.real_pnl == phrases.money(stored.real_pnl)
        assert found.page.card.stored == phrases.stored_at(max((p.completed_at for p in parts), default=scan.as_of))
        assert found.back == "Back to Watchlist (Cut-off Date 1 July 2025)"
        assert found.tag == ((wl.NOT_FULLY_READ, wl.NOT_FULLY_READ_TIP) if stored.not_fully_read else None)


def test_ad19_a_market_resolved_after_the_scans_as_of_time_stays_out(scanned: tuple[Rig, int]) -> None:
    """AD-19: the page cuts the parts at the Scan's as-of time, as the Scan did: a Scan whose as-of is moved back
    before every resolution tests nothing."""
    rig, scan_id = scanned
    scan = rig.store.scan(scan_id)
    stored = next(r for r in rig.store.scan_results(scan_id) if r.scope == SCAN_WHOLE and r.fetch_id is not None)
    parts = [rig.store.snapshot(f) for f in (stored.fetch_id, stored.after_fetch_id) if f is not None]
    early = dataclasses.replace(scan, as_of=0)
    assert scan_whole_result(stored.wallet, parts, scan=early).result.tested_count == 0


def test_ux_dr37_the_verdict_page_from_a_scan(scanned: tuple[Rig, int]) -> None:
    """UX-DR37, FR-11 (Edvard, 2026-11-26): the back link above the eyebrow returns to the Watchlist; the honesty notes
    always show the two-window line and the Scan's computed-on line; the tab title is the Verdict's."""
    rig, scan_id = scanned
    stored = next(r for r in rig.store.scan_results(scan_id) if r.scope == SCAN_WHOLE and r.fetch_id is not None)
    page = web_over(rig.store).get(f"/scans/{scan_id}/wallet/{stored.wallet}").get_data(as_text=True)
    back = re.search(r'<a class="back-link" href="([^"]+)"><span aria-hidden="true">← </span>([^<]+)</a>', page)
    assert back and back.groups() == (f"/scans/{scan_id}/watchlist", "Back to Watchlist (Cut-off Date 1 July 2025)")
    assert page.index('class="back-link"') < page.index('class="eyebrow"')
    assert phrases.SCAN_WINDOW_LINE in page
    assert re.search(r"Computed on (no bets|1 bet|[\d,]+ bets) around the Cut-off Date 1 July 2025 · Seed 44", page)
    assert f"<title>Verdict · {stored.wallet[:6]}…{stored.wallet[-4:]} · LiquidOracle</title>" in page
    assert '<a href="/scans" aria-current="true">Scan wallets</a>' in page  # opened from the Scan pages


def test_ux_dr37_a_lookup_verdict_has_no_back_link(scanned: tuple[Rig, int], tmp_path: Path) -> None:
    """UX-DR37: the back link shows only on a Verdict opened from a Scan."""
    from test_web import SHARP, sample_files  # noqa: PLC0415  (Offline Mode's Sample Wallets)

    from liquidoracle.data import synthetic
    from liquidoracle.data.offline import OfflineClient
    from liquidoracle.services.fetch import fetch_wallet

    synthetic.write_small(tmp_path)
    store = Store(tmp_path / "offline.db")
    try:
        fetch_wallet(OfflineClient(sample_files(tmp_path)), store, SHARP)
        app = create_app(Settings(offline=True), Lookup(OfflineClient(sample_files(tmp_path)), store, seed=SEED))
        page = app.test_client().get(f"/wallet/{SHARP}").get_data(as_text=True)
    finally:
        store.close()
    assert "back-link" not in page and "Back to Watchlist" not in page
    assert 'aria-current="true"' not in page


# --- the Scan list link (UX-DR31) and read-only (FR-16) --------------------------------------------------


def test_ux_dr31_a_finished_scan_links_its_watchlist(store: Store, tmp_path: Path) -> None:
    """UX-DR31: a finished Scan's Watchlist size, 0 too, is a link named with its Cut-off Date; an unfinished one is
    not."""
    done = hand_scan(tmp_path / "live.db", [Row(wallet(1), verdict=Verdict.NO_EVIDENCE.value, p_value=0.4)])
    open_ = hand_scan(tmp_path / "live.db", [Row(wallet(2))], step="ranked")
    rows = {r.scan_id: r for r in ScansPage(store, jobs=None, seed=SEED, rate=5.0).view().rows}
    assert rows[done].watchlist_label == "0 Wallets on the Watchlist (Cut-off Date 1 July 2025)"
    assert rows[open_].watchlist_label is None
    assert wl.watchlist_label(1, "1 July 2025") == "1 Wallet on the Watchlist (Cut-off Date 1 July 2025)"
    page = web_over(store).get("/scans").get_data(as_text=True)
    assert (f'<a href="/scans/{done}/watchlist" aria-label="0 Wallets on the Watchlist (Cut-off Date 1 July 2025)">0</a>'
            in page)
    assert f"/scans/{open_}/watchlist" not in page


def test_fr16_the_watchlist_pages_only_read(scanned: tuple[Rig, int]) -> None:
    """FR-16: opening the Watchlist and a Verdict from it sends nothing anywhere and writes nothing."""
    rig, scan_id = scanned
    web = web_over(rig.store)
    calls = len(rig.transport.calls)
    db = rig.store._connection()
    changes = db.total_changes
    stored = next(r for r in rig.store.scan_results(scan_id) if r.scope == SCAN_WHOLE)
    assert web.get(f"/scans/{scan_id}/watchlist").status_code == 200
    assert web.get(f"/scans/{scan_id}/wallet/{stored.wallet}").status_code == 200
    assert len(rig.transport.calls) == calls
    assert db.total_changes == changes


# --- review loop 1 (Edvard, 2026-11-26): the windows read, the row's flag, no Wallet with a Verdict ---------


def test_fr11_a_capped_scan_result_counts_the_rows_left_after_the_as_of_cut(scanned: tuple[Rig, int]) -> None:
    """FR-11, AD-8, AD-19: a capped part's computed-on line counts the positions-list rows left once the Markets
    resolved at or after the Scan's as-of time are cut, never the rows of a Market the Scan did not test."""
    from liquidoracle.services.honesty import honesty_notes

    rig, scan_id = scanned
    scan = rig.store.scan(scan_id)
    stored = next(r for r in rig.store.scan_results(scan_id) if r.scope == SCAN_WHOLE and r.fetch_id is not None)
    parts = [rig.store.snapshot(f) for f in (stored.fetch_id, stored.after_fetch_id) if f is not None]
    late = parts[0].positions[0].condition_id
    parts[0] = dataclasses.replace(
        parts[0], window_capped=True,
        markets=tuple(dataclasses.replace(m, closed_time=scan.as_of) if m.condition_id == late else m
                      for m in parts[0].markets),
    )
    kept = sum(1 for part in parts for row in part.positions if row.condition_id != late)
    assert kept < sum(len(part.positions) for part in parts)
    notes = honesty_notes(scan_whole_result(stored.wallet, parts, scan=scan))
    assert notes.computed_on == f"Computed on {phrases.count(kept)} bets around the Cut-off Date 1 July 2025 · Seed 44"


def test_fr11_a_refused_after_part_names_only_the_before_window(scanned: tuple[Rig, int]) -> None:
    """FR-11 (Edvard, 2026-11-26, Story 4.5 review): a result resting on the before part alone (Polymarket refused
    the after part) says so; one with nothing read shows no window line."""
    from liquidoracle.services.honesty import honesty_notes

    rig, scan_id = scanned
    scan = rig.store.scan(scan_id)
    stored = next(r for r in rig.store.scan_results(scan_id) if r.scope == SCAN_WHOLE and r.fetch_id is not None)
    before = rig.store.snapshot(stored.fetch_id)
    assert honesty_notes(scan_whole_result(stored.wallet, [before], scan=scan)).window == phrases.SCAN_BEFORE_ONLY_LINE
    assert honesty_notes(scan_whole_result(stored.wallet, [], scan=scan)).window == ""


def test_ux_dr37_a_flagged_rows_verdict_keeps_its_tag(store: Store, tmp_path: Path) -> None:
    """FR-16, UX-DR37 (Edvard, 2026-11-26, Story 4.5 review): a Verdict opened from a row flagged Not fully read
    shows the same tag and tooltip beside its stats; with nothing read it shows no window line and its "Data
    stored" is the Scan's time; an unflagged row's Verdict has no tag."""
    flagged, clean = wallet(1), wallet(2)
    scan_id = hand_scan(tmp_path / "live.db", [
        Row(flagged, verdict=Verdict.NOT_ENOUGH_DATA.value, p_value=None, tested=0, real_pnl=0.0, unread=True),
        Row(clean, verdict=Verdict.NOT_ENOUGH_DATA.value, p_value=None, tested=0, real_pnl=0.0),
    ])
    found = Watchlists(store).verdict(scan_id, flagged)
    assert found is not None and found.tag == (wl.NOT_FULLY_READ, wl.NOT_FULLY_READ_TIP)
    assert found.page.card is not None and found.page.card.stored == phrases.stored_at(1_790_000_000)
    web = web_over(store)
    page = web.get(f"/scans/{scan_id}/wallet/{flagged}").get_data(as_text=True)
    assert re.search(r'<button class="info-tag" type="button" aria-describedby="verdict-tip">Not fully read</button>', page)
    assert str(Markup.escape(wl.NOT_FULLY_READ_TIP)) in page and "js/tag-tip.js" in page
    assert str(Markup.escape(phrases.SCAN_WINDOW_LINE)) not in page
    assert str(Markup.escape(phrases.SCAN_BEFORE_ONLY_LINE)) not in page
    other = web.get(f"/scans/{scan_id}/wallet/{clean}").get_data(as_text=True)
    assert "info-tag" not in other and "js/tag-tip.js" not in other


def test_fr16_no_wallet_with_a_verdict_means_no_luck_sentence(store: Store, tmp_path: Path) -> None:
    """FR-16, SM-C2 (Edvard, 2026-11-26, Story 4.5 review): when no Wallet got a Verdict the info box is left out and
    the empty-Watchlist sentence stands alone."""
    scan_id = hand_scan(tmp_path / "live.db", [
        Row(wallet(i), verdict=Verdict.NOT_ENOUGH_DATA.value, p_value=None, tested=4) for i in range(3)
    ])
    view = Watchlists(store).view(scan_id)
    assert view is not None and view.luck == "" and view.rows == ()
    page = web_over(store).get(f"/scans/{scan_id}/watchlist").get_data(as_text=True)
    assert 'class="info-box"' not in page and "would pass by luck alone" not in page
    assert "No Wallet in this Scan was rated" in page


def test_ux_dr20_data_stored_is_when_the_later_part_was_completed(scanned: tuple[Rig, int]) -> None:
    """UX-DR20, AD-19: a Scan Verdict's "Data stored" is the completion time of its later part, not the earlier."""
    rig, scan_id = scanned
    scan = rig.store.scan(scan_id)
    stored = next(r for r in rig.store.scan_results(scan_id) if r.scope == SCAN_WHOLE and r.after_fetch_id is not None)
    before, after = rig.store.snapshot(stored.fetch_id), rig.store.snapshot(stored.after_fetch_id)
    parts = [dataclasses.replace(before, completed_at=scan.as_of - 3_600), dataclasses.replace(after, completed_at=scan.as_of - 60)]
    assert scan_whole_result(stored.wallet, parts, scan=scan).stored_at == scan.as_of - 60
    assert scan_whole_result(stored.wallet, parts[::-1], scan=scan).stored_at == scan.as_of - 60


# --- review pass 2 -----------------------------------------------------------------------------------------


def test_ad22_a_skilled_verdict_from_a_scan_equals_its_row_with_the_scans_own_seed(store: Store, tmp_path: Path) -> None:
    """AD-22, UX-DR37: for a Wallet that ran the Simulations (the sharp trader split at its middle Market, Skilled),
    a Scan with Seed 7 gives the same Verdict, p-value, bets and Real PnL on its Verdict page as `scan_results` stored,
    and the page shows the odds line, the chart and "Seed 7"; with Seed 44 the p-value would differ."""
    from test_scan_job import split_parts

    from liquidoracle.data import synthetic
    from liquidoracle.data.store import ScanWallet, WalletOutcome
    from liquidoracle.services.scan import scan_results

    sharp = next(w for w in synthetic.small_wallets() if w.address.startswith("0x2ccde450"))
    before, after = split_parts(sharp)
    ids = []
    for part in (before, after):  # the two parts frozen in the store, as a Scan leaves them
        fetch_id = store.begin_snapshot(sharp.address, window_limit=part.window_limit, cutoff=part.cutoff, side=part.side)
        store.add_positions(fetch_id, part.positions)
        store.add_activity(fetch_id, part.activity)
        store.save_markets(part.markets)
        store.finish_snapshot(fetch_id)
        ids.append(fetch_id)
    as_of = 1_790_000_000
    row = ScanWallet(0, sharp.address, 0.0, WalletOutcome.RANKED, 0.0, False, ids[0], ids[1], True)
    stored = [store.snapshot(i) for i in ids]
    whole = scan_results(row, stored[0], stored[1], seed=7, as_of=as_of)[1]
    other = scan_results(row, stored[0], stored[1], seed=44, as_of=as_of)[1]
    assert whole.verdict == SKILLED and whole.p_value is not None and whole.p_value != other.p_value
    scan_id = hand_scan(tmp_path / "live.db", [Row(sharp.address, whole.verdict, whole.p_value, whole.tested_count,
                                                   whole.real_pnl)], seed=7, as_of=as_of)
    with sqlite3.connect(tmp_path / "live.db") as db:
        db.execute("UPDATE scan_result SET fetch_id = ?, after_fetch_id = ? WHERE scan_id = ?", (*ids, scan_id))
    db.close()

    found = Watchlists(store).verdict(scan_id, sharp.address)
    assert found is not None and found.page.card is not None and found.page.chart is not None
    again = scan_whole_result(sharp.address, stored, scan=store.scan(scan_id)).result
    assert (again.verdict.value, again.p_value, again.tested_count, again.real_pnl) == (
        whole.verdict, whole.p_value, whole.tested_count, whole.real_pnl
    )
    assert found.page.card.odds_line == phrases.odds_sentence(whole.p_value)
    page = web_over(store).get(f"/scans/{scan_id}/wallet/{sharp.address}").get_data(as_text=True)
    assert phrases.odds(whole.p_value) in page and 'class="card chart-card"' in page
    assert "around the Cut-off Date 1 July 2025 · Seed 7" in page
