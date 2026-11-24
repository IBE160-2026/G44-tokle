"""The pages: Check a wallet, the Verdict page and Page not found (FR-1, FR-8, FR-10, FR-14, AD-18; Story 1.7).

The app runs over the lookup service with the committed Synthetic Wallets and 3 coin-flippers
loaded, through Flask's test client, with sockets blocked. Markup checks follow EXPERIENCE.md
› Accessibility Floor and the UX-DR items named in each test.
"""

from __future__ import annotations

import dataclasses
import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from liquidoracle.data import sample_json, synthetic
from liquidoracle.data.offline import REAL_DIR, OfflineClient, sample_files
from liquidoracle.data.store import OFFLINE_DB, Store
from liquidoracle.services.fetch import fetch_wallet
from liquidoracle.services.jobs import Jobs
from liquidoracle.services.lookup import Lookup, Outcome, VerdictCard, WalletPage
from liquidoracle.settings import Settings
from liquidoracle.web import create_app

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "src" / "liquidoracle" / "web"
MOCKUPS = REPO / "_bmad-output" / "planning-artifacts" / "ux-designs" / "ux-LiquidOracle-2026-10-16" / "mockups"
DESIGN = MOCKUPS.parent / "DESIGN.md"
SEED = 44
UNKNOWN = "0x" + "0" * 40
SHARP = synthetic.address_of("sharp-trader")
THIN = synthetic.address_of("thin-wallet")
COIN_FLIPPER = synthetic.address_of(synthetic.coin_flipper_name(0))


@pytest.fixture(scope="module")
def loaded_lookup(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Lookup]:
    root = tmp_path_factory.mktemp("repo")
    synthetic.write_small(root)
    synthetic.write_coin_flippers(root, 3)
    client = OfflineClient(sample_files(root))
    store = Store(root / OFFLINE_DB)
    for address in client.addresses():
        fetch_wallet(client, store, address)
    yield Lookup(client, store, seed=SEED)
    store.close()


@pytest.fixture(scope="module")
def offline(loaded_lookup: Lookup) -> FlaskClient:
    return create_app(Settings(offline=True), loaded_lookup).test_client()


@pytest.fixture
def live(tmp_path: Path) -> Iterator[FlaskClient]:
    store = Store(tmp_path / "live.db")
    yield create_app(Settings(offline=False), Lookup(None, store, seed=SEED, jobs=Jobs(store))).test_client()
    store.close()


def html(client: FlaskClient, url: str, status: int = 200) -> str:
    response = client.get(url)
    assert response.status_code == status, response.status_code
    return response.get_data(as_text=True)


def text(page: str) -> str:
    """The page's words, tags removed and spaces collapsed."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page)).strip()


def h1s(page: str) -> list[str]:
    return [text(m) for m in re.findall(r"<h1[\s>].*?</h1>", page, re.S)]


PAGES = ["/", "/?address=", f"/wallet/{SHARP}", f"/wallet/{THIN}", f"/wallet/{UNKNOWN}", "/wallet/abc", "/no-such-page"]


# --- every page (AD-18, UX-DR3/4/5/6/8) --------------------------------------------------------


@pytest.mark.parametrize("url", PAGES)
def test_every_page_has_the_frame(offline: FlaskClient, url: str) -> None:
    """AD-18, UX-DR4/5/6/8: English, one main heading, the skip link as the first Tab stop, the top bar
    with logo and Check a wallet, the favicon and the Offline pill. The scripts are files (no inline
    code): theme.js on every page, copy-address.js with a Verdict card, chart.js only with a luck chart; the
    toggle is hidden until theme.js shows it (UX-DR2)."""
    page = offline.get(url).get_data(as_text=True)
    assert page.startswith("<!doctype html>\n<html lang=\"en\">")
    assert len(h1s(page)) == 1
    body = page[page.index("<body"):]
    first_focusable = re.search(r"<(a|button|input|select|textarea)\b[^>]*>", body)
    assert first_focusable and 'class="skip-link" href="#content"' in first_focusable.group(0)
    assert 'id="content"' in body and "Skip to content" in body
    assert 'class="brand-mark"' in page and ">Check a wallet</a>" in page
    assert 'rel="icon" type="image/svg+xml" href="/static/img/favicon.svg"' in page
    assert "Offline Mode</strong> · sample data only" in page
    scripts = re.findall(r"<script([^>]*)>(.*?)</script>", page, re.S)
    assert all(code == "" for _, code in scripts)
    expected = [' src="/static/js/theme.js"']
    if 'class="verdict-card"' in page:
        expected.append(' src="/static/js/copy-address.js" defer')
    if 'class="card chart-card"' in page:
        expected.append(' src="/static/js/chart.js" defer')
    assert [src for src, _ in scripts] == expected
    toggle = re.search(r'<button class="theme-toggle"[^>]*>', page).group(0)
    assert 'aria-label="Dark theme"' in toggle and 'aria-pressed="true"' in toggle and " hidden" in toggle
    assert not re.search(r"https?://", page)  # nothing is loaded from the internet (UX-DR3)


def test_offline_pill_only_in_offline_mode(live: FlaskClient) -> None:
    """UX-DR18, AD-13: no Offline pill and no Sample list in a live run."""
    page = html(live, "/")
    assert "Offline Mode" not in page
    assert "Sample Wallets" not in page


@pytest.mark.parametrize(
    ("url", "title"),
    [
        ("/", "Check a wallet · LiquidOracle"),
        (f"/wallet/{SHARP}", f"Verdict · {SHARP[:6]}…{SHARP[-4:]} · LiquidOracle"),
        ("/wallet/abc", "Page not found · LiquidOracle"),
    ],
)
def test_ux_dr8_tab_titles(offline: FlaskClient, url: str, title: str) -> None:
    """UX-DR8: page name first in the tab title."""
    assert f"<title>{title}</title>" in offline.get(url).get_data(as_text=True)


# --- Check a wallet (FR-1, UX-DR13, UX-DR16, UX-DR17) ------------------------------------------


def test_ux_dr16_lookup_page(offline: FlaskClient) -> None:
    """UX-DR16: eyebrow, title, lede and the address field card with focus in the field; a plain GET form."""
    page = html(offline, "/")
    assert re.search(r'<p class="eyebrow">Skill or luck</p>', page)
    assert h1s(page) == ["Check a wallet"]
    assert "replays its resolved bets 10,000 times" in page
    assert '<form class="card" action="/" method="get" novalidate>' in page
    assert '<label class="field-label" for="address">Wallet address</label>' in page
    field = re.search(r'<input[^>]*id="address"[^>]*>', page, re.S).group(0)
    assert "autofocus" in field and 'aria-describedby="address-hint"' in field
    assert "aria-invalid" not in field
    assert '<button class="btn-primary" type="submit">Check wallet</button>' in page


@pytest.mark.parametrize(
    ("raw", "sentence"),
    [
        ("", "Enter a wallet address."),
        ("+++", "Enter a wallet address."),  # "+" is a space in a query string
        ("abc", "This is not a valid wallet address. It should start with 0x and have 42 characters."),
        (UNKNOWN, "Not available offline. In Offline Mode only the Sample Wallets below can be checked."),
    ],
)
def test_ux_dr13_errors_stay_on_the_lookup_page(offline: FlaskClient, raw: str, sentence: str) -> None:
    """FR-1, FR-14, UX-DR13: the error sits under the field, tied to it, read with a hidden "Error:";
    the field is marked invalid and keeps focus; nothing is opened."""
    page = html(offline, f"/?address={raw}")
    field = re.search(r'<input[^>]*id="address"[^>]*>', page, re.S).group(0)
    assert 'aria-invalid="true"' in field
    assert 'aria-describedby="address-error address-hint"' in field
    assert "autofocus" in field
    error = re.search(r'<p class="error-message" id="address-error">(.*?)</p>', page, re.S).group(1)
    assert '<span class="visually-hidden">Error: </span>' in error
    assert text(error).endswith(sentence)
    assert h1s(page) == ["Check a wallet"]


def test_fr1_valid_address_opens_its_page_in_lower_case(offline: FlaskClient) -> None:
    """FR-1, UX-DR16: spaces removed, the Verdict page opened at the lower-case address."""
    mixed = "0x" + SHARP[2:].upper()
    response = offline.get(f"/?address=++{mixed}+")
    assert response.status_code == 302
    assert response.headers["Location"] == f"/wallet/{SHARP}"


def test_ux_dr17_sample_wallets_list(offline: FlaskClient) -> None:
    """UX-DR17 (Edvard, 2026-11-20): the Synthetic Wallets group, each item a link tagged "synthetic",
    one coin-flipper, and the note for the other 999."""
    page = html(offline, "/")
    assert '<h2 id="samples-title">Sample Wallets</h2>' in page
    assert '<h3 class="group-label" id="synthetic-label">Synthetic Wallets</h3>' in page
    links = re.findall(r'<a class="wallet-link" href="/wallet/(0x[0-9a-f]{40})"><span class="name">([^<]+)</span>'
                       r'<span class="info-tag">synthetic</span>', page)
    assert (SHARP, "Sharp trader") in links and (COIN_FLIPPER, "Coin-flipper") in links
    assert len(links) == 6
    assert "and 999 more coin-flippers, checked by address" in page


def test_ux_dr17_real_wallets_group(tmp_path: Path) -> None:
    """UX-DR17, FR-12 (Story 2.6): a *Real Wallets* group comes first, each real Wallet's short address
    in monospace, linking to its Verdict page. Without real files the group is not shown."""
    synthetic.write_small(tmp_path)
    real = "0x" + "a" * 36 + "d3f5"
    sharp = sample_json.read_wallet(tmp_path / synthetic.SMALL_DIR / "sharp-trader.json")
    sample_json.write_wallet(tmp_path / REAL_DIR / f"{real}.json", dataclasses.replace(sharp, address=real, name="real-aaaaaa"))
    client = OfflineClient(sample_files(tmp_path))
    store = Store(tmp_path / OFFLINE_DB)
    fetch_wallet(client, store, real)
    app = create_app(Settings(offline=True), Lookup(client, store, seed=SEED)).test_client()
    page = html(app, "/")
    assert page.index('id="real-label">Real Wallets</h3>') < page.index('id="synthetic-label">Synthetic Wallets</h3>')
    assert re.findall(r'<a class="wallet-link" href="/wallet/(0x[0-9a-f]{40})"><span class="name mono">([^<]+)</span>', page) == [
        (real, "0xaaaa…d3f5")
    ]
    assert h1s(html(app, f"/wallet/{real}")) == ["Verdict: Skilled (high confidence)"]  # sharp-trader's bets
    store.close()


def test_lookup_page_survives_an_old_coin_flipper_file(tmp_path: Path) -> None:
    """FR-14, UX-DR17 (review, Story 2.6): after a pull, coin-flipper files from before a format change
    must not break the Lookup page; the Real Wallets group reads only file names."""
    synthetic.write_small(tmp_path)
    synthetic.write_coin_flippers(tmp_path, 1)
    old = next((tmp_path / synthetic.COIN_FLIPPER_DIR).glob("*.json"))
    old.write_text(old.read_text(encoding="utf-8").replace('"activity_from": null,', ""), encoding="utf-8")
    real = "0x" + "b" * 40
    (tmp_path / REAL_DIR).mkdir(parents=True)
    (tmp_path / REAL_DIR / f"{real}.json").write_text("{}", encoding="utf-8")  # only its name is read here
    (tmp_path / REAL_DIR / "dataset.json").write_text("{}", encoding="utf-8")
    store = Store(tmp_path / OFFLINE_DB)
    app = create_app(Settings(offline=True), Lookup(OfflineClient(sample_files(tmp_path)), store, seed=SEED))
    page = html(app.test_client(), "/")
    assert f'href="/wallet/{real}"' in page and "Synthetic Wallets" in page
    store.close()


def test_no_real_wallets_group_without_real_files(offline: FlaskClient) -> None:
    """UX-DR17: with no files in sample_data/real/ the Real Wallets group is not shown."""
    assert "Real Wallets" not in html(offline, "/")


def test_not_loaded_box_on_the_lookup_page(tmp_path: Path) -> None:
    """FR-14 (Edvard, 2026-11-20): before load-sample the Lookup page says how to load the Sample Dataset."""
    synthetic.write_small(tmp_path)
    store = Store(tmp_path / OFFLINE_DB)
    client = create_app(Settings(offline=True), Lookup(OfflineClient(sample_files(tmp_path)), store, seed=SEED))
    page = html(client.test_client(), "/")
    assert "The Sample Dataset is not loaded yet. Run <code>uv run liquidoracle load-sample</code>" in page
    sharp = html(client.test_client(), f"/wallet/{SHARP}")
    assert h1s(sharp) == ["Sample Dataset not loaded"]
    store.close()


# --- the Verdict page (FR-8, FR-10, UX-DR20, UX-DR23, UJ-3) -------------------------------------


def test_fr8_sharp_trader_verdict_card(offline: FlaskClient) -> None:
    """FR-8, UX-DR20, UJ-3: the hero is the main heading read as "Verdict: Skilled (high confidence)",
    the dots are hidden from screen readers, then the odds line, the address card and the stats."""
    page = html(offline, f"/wallet/{SHARP}")
    assert '<p class="eyebrow">Wallet analysis</p>' in page
    assert h1s(page) == ["Verdict: Skilled (high confidence)"]
    hero = re.search(r"<h1[\s>].*?</h1>", page, re.S).group(0)
    assert '<span class="dots" aria-hidden="true">' in hero
    assert hero.count('class="dot is-filled"') == 3
    assert '<span class="visually-hidden">Verdict: </span>Skilled (high confidence)' in hero
    assert re.search(r'<p class="odds">a trader with no edge would do this well [^<]+\.</p>', page)
    assert f'<code class="address">{SHARP}</code>' in page
    assert "<strong>100</strong> resolved bets" in page and "Real PnL <strong>$2,000</strong>" in page
    assert re.search(r'<p class="stored">Data stored \d{1,2} [A-Z][a-z]{2} \d{4}, \d\d:\d\d</p>', page)


def test_uj3_coin_flipper_reads_no_evidence(offline: FlaskClient) -> None:
    """FR-8, UJ-3: the listed coin-flipper reads No evidence of skill, with three empty dots."""
    page = html(offline, f"/wallet/{COIN_FLIPPER}")
    assert h1s(page) == ["Verdict: No evidence of skill"]
    assert page.count('class="dot"') == 3 and "is-filled" not in page


def test_fr10_thin_wallet_not_enough_data(offline: FlaskClient) -> None:
    """FR-10, UX-DR23: the dashed hero, the count sentence, no dots and no odds phrase."""
    page = html(offline, f"/wallet/{THIN}")
    assert h1s(page) == ["Verdict: Not enough data"]
    assert 'class="verdict verdict-none"' in page and 'class="dots"' not in page
    assert '<p class="odds">29 resolved bets; at least 30 are needed for a Verdict (1 more)</p>' in page
    assert "a trader with no edge" not in page


# --- the chart card (FR-9, UX-DR24, UX-DR25; Story 3.1) -----------------------------------------

STOP_LOSS = synthetic.address_of("stop-loss-trader")


def chart_card(page: str) -> str:
    found = re.search(r'<section class="card chart-card".*?</section>', page, re.S)
    assert found, "no chart card"
    return found.group(0)


def test_fr9_chart_card_follows_the_verdict_card(offline: FlaskClient) -> None:
    """FR-9, UX-DR19, UX-DR24: after the Verdict card come the title, About (closed), the chart, the hint and
    the text alternative, in that order, complete without JavaScript (AD-18)."""
    page = html(offline, f"/wallet/{SHARP}")
    card = chart_card(page)
    assert page.index('class="verdict-card"') < page.index('class="card chart-card"')
    assert '<h2 id="chart-title">Simulated results <small>(10,000 replays with no edge)</small></h2>' in card
    assert re.search(r'<details class="about">\s*<summary>About this chart</summary>', card)  # closed by default
    order = [card.index(part) for part in ("<details", "<svg", 'class="chart-hint"', 'class="chart-alt"')]
    assert order == sorted(order)
    assert card.count('class="chart-bar"') == 42
    assert (
        '<p class="chart-alt">This Wallet made $2,000 on 100 resolved bets. '
        "In 10,000 replays with no edge, a result this good came up about 1 time in 5,000.</p>"
    ) in card
    assert "<script" not in card  # chart.js is loaded once, after the card (Story 3.2)
    # The marker reaches the page where the service put it: the axis' top edge, label hanging inwards.
    assert '<line class="chart-marker-line" x1="42.000" x2="42.000"' in card
    assert '<span class="chart-marker-label anchor-end" style="left: 95.455%" aria-hidden="true">This Wallet: $2,000</span>' in card
    assert '<span class="t-full">−$2,000 or less</span><span class="t-short">−$2k or less</span>' in card


def test_ux_dr25_bars_and_axes_are_hidden_from_screen_readers(offline: FlaskClient) -> None:
    """UX-DR25, NFR-9: every part of the drawing (bars, gridlines, ticks, end labels, marker and its label) is
    hidden from screen readers; since Story 3.2 each part carries aria-hidden itself, so the slider and the
    marker button beside them can be reached. The text alternative stays readable and carries the meaning."""
    card = chart_card(html(offline, f"/wallet/{SHARP}"))
    drawing = {
        "svg": r'<svg class="chart-svg"[^>]*>', "y title": r'<p class="chart-y-title"[^>]*>',
        "y labels": r'<span class="chart-y-label"[^>]*>', "dot": r'<span class="chart-dot"[^>]*>',
        "marker label": r'<span class="chart-marker-label[^>]*>', "ticks": r'<div class="chart-axis"[^>]*>',
        "end labels": r'<div class="chart-ends"[^>]*>', "tail label": r'<div class="chart-tail-label[^>]*>',
        "tooltip": r'<div class="chart-tip"[^>]*>',
    }
    for name, pattern in drawing.items():
        tags = re.findall(pattern, card)
        assert tags and all('aria-hidden="true"' in tag for tag in tags), name
    assert re.search(r'<span class="chart-marker-label[^>]*aria-hidden="true">This Wallet: \$2,000</span>', card)
    assert 'aria-hidden' not in re.search(r'<p class="chart-alt">', card).group(0)


def test_fr9_above_all_label_on_the_page(offline: FlaskClient) -> None:
    """FR-9: the stop-loss trader beat every replay, so the marker's second line says so."""
    card = chart_card(html(offline, f"/wallet/{STOP_LOSS}"))
    assert "This Wallet: $1,650<br>above all 10,000 Simulations" in card
    assert 'class="chart-frame has-beyond"' in card


def test_fr10_not_enough_data_shows_no_chart_card(offline: FlaskClient) -> None:
    """FR-10, UX-DR23: *Not enough data* has no chart card."""
    page = html(offline, f"/wallet/{THIN}")
    assert "chart-card" not in page and "Simulated results" not in page


def test_ux_dr25_chart_styles() -> None:
    """UX-DR25, UX-DR12: 200 px tall and short labels below 640 px, end labels hidden below 400 px, and
    the bars and marker in system colours under forced colours."""
    css = (WEB / "static" / "css" / "app.css").read_text(encoding="utf-8")
    narrow = re.search(r"@media \(max-width: 639px\) \{(.*?)\n\}", css, re.S).group(1)
    assert ".chart-plot { height: 200px; }" in narrow and ".chart .t-short { display: inline; }" in narrow
    assert ".chart-tick.is-minor { display: none; }" in narrow
    assert re.search(r"@media \(max-width: 399px\) \{\s*\.chart-ends \{ display: none; \}", css)
    forced = "".join(re.findall(r"@media \(forced-colors: active\) \{(.*?)\n\}", css, re.S))
    assert ".chart-bar { fill: CanvasText; }" in forced and ".chart-marker-line { stroke: Highlight; }" in forced


# --- Story 3.2: exploring the chart (UX-DR26, UX-DR27, UX-DR28) -----------------------------------
# chart.js only shows, hides and moves what the page already holds, so these tests check what it is
# given; the script itself is checked in a browser (spec-3-2, Edvard 2026-11-23: no JS test runner yet).

JS = WEB / "static" / "js" / "chart.js"


def tag(card: str, pattern: str) -> str:
    found = re.search(pattern, card)
    assert found, pattern
    return found.group(0)


def test_ux_dr26_slider_and_button_wait_for_the_script(offline: FlaskClient) -> None:
    """UX-DR26, UX-DR27, AD-18, 3.2 matrix "No JS": the slider, the marker button, the tail label, the tooltip, the
    explore hint and About's fourth paragraph are all hidden until chart.js shows them; the 3.1 hint is not."""
    card = chart_card(html(offline, f"/wallet/{SHARP}"))
    slider = tag(card, r'<div class="chart-explore"[^>]*>')
    for part in ('role="slider"', 'tabindex="0"', 'aria-label="Replays by result"', 'aria-describedby="chart-explore-hint"',
                 'aria-valuemin="1"', 'aria-valuemax="42"', 'aria-valuenow="41"',
                 'aria-valuetext="$1,900 to $2,000: 0 replays"', "data-explore hidden"):
        assert part in slider, part
    button = tag(card, r'<button class="chart-marker-button"[^>]*>')
    for part in ('type="button"', 'aria-pressed="false"', 'style="left: 95.455%"', 'aria-describedby="chart-tail-text"',
                 'aria-label="This Wallet: $2,000. Highlight the replays that did this well or better"', "data-explore hidden"):
        assert part in button, part
    assert '<p class="visually-hidden" id="chart-tail-text" hidden>1 of 10,000 replays did this well or better</p>' in card
    assert re.search(r'<div class="chart-tail-label is-left"[^>]*data-explore hidden>1 of 10,000 replays did this well or better</div>', card)
    assert re.search(r'<div class="chart-tip" aria-hidden="true" data-explore hidden></div>', card)
    assert ('<p class="chart-hint" data-no-explore>Each bar is a range of results. '
            "The taller the bar, the more replays ended there.</p>") in card
    assert ('<p class="chart-hint" id="chart-explore-hint" data-explore hidden>Point at a bar, or use the arrow keys, '
            "to see how many replays ended there.</p>") in card
    assert re.search(r"<p data-explore hidden>Point at a bar, or step through the bars with the arrow keys", card)
    # Without chart.js nothing in the card but About can take focus: the slider and button are script parts.
    focusable = re.findall(r'<(?:button|a|input)\b[^>]*>|<[^>]*tabindex="0"[^>]*>', card)
    assert len(focusable) == 2 and all("data-explore hidden" in t for t in focusable)


def test_ux_dr26_every_bar_carries_its_tooltip_words(offline: FlaskClient) -> None:
    """UX-DR26: each bar holds its range and replay count for the tooltip and the slider, in order; the end bars
    read as their labels, and each bar knows its place in the build-up."""
    card = chart_card(html(offline, f"/wallet/{SHARP}"))
    bars = re.findall(r'<rect class="chart-bar"[^>]*style="--i: (\d+)" data-range="([^"]*)" data-count="([^"]*)"/>', card)
    assert len(bars) == 42 and [int(i) for i, _, _ in bars] == list(range(42))
    assert bars[0][1:] == ("−$2,000 or less", "0 replays")
    assert bars[-1][1:] == ("$2,000 or more", "1 replay")
    assert bars[40][1] == "$1,900 to $2,000"
    assert sum(int(count.split()[0].replace(",", "")) for _, _, count in bars) == 10_000


@pytest.mark.parametrize(
    ("address", "tail_from", "sentence"),
    [
        (SHARP, 40, "1 of 10,000 replays did this well or better"),
        (STOP_LOSS, 42, "No replay did this well or better"),
    ],
)
def test_ux_dr27_tail_data_on_the_page(offline: FlaskClient, address: str, tail_from: int, sentence: str) -> None:
    """UX-DR27, 3.2 matrix "Normal" and "None reached": the page tells chart.js the first bar to light (none
    for stop-loss-trader) and the Highlight on/off words, with the tail sentence from the exact count."""
    card = chart_card(html(offline, f"/wallet/{address}"))
    chart = tag(card, r'<div class="chart" [^>]*>')
    assert f'data-tail-from="{tail_from}"' in chart and "data-marker-bar=" in chart
    assert f'data-highlight-on="Highlight on: {sentence}" data-highlight-off="Highlight off"' in card
    assert f">{sentence}</div>" in card


def test_ux_dr26_chart_script_follows_the_card_once(offline: FlaskClient) -> None:
    """AD-18, 3.2 matrix "Not enough data": chart.js is loaded once, after the card, only when there is a chart."""
    page = html(offline, f"/wallet/{SHARP}")
    assert page.count('<script src="/static/js/chart.js" defer></script>') == 1
    assert page.index("</section>", page.index('class="card chart-card"')) < page.index("js/chart.js")
    assert "chart.js" not in html(offline, f"/wallet/{THIN}")


def test_ad25_chart_script_writes_no_words() -> None:
    """AD-25, UX-DR26: chart.js reads every word and number from the page; it has no money, counts or sentences
    of its own, and swapped-in pages are enhanced through progress.js."""
    script = JS.read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", script, flags=re.S)  # comments may quote examples
    assert "'" not in code and "`" not in code  # every string is double-quoted, so the scan below sees them all
    for text in re.findall(r'"([^"\\]*)"', code):
        assert not re.search(r"\$|\d,\d|replay|Highlight|did this well", text), text
    assert "innerHTML" not in code  # the tooltip is built from text nodes
    assert "window.LiquidOracleChart = { enhance: enhance };" in code
    progress = (WEB / "static" / "js" / "progress.js").read_text(encoding="utf-8")
    assert "window.LiquidOracleChart.enhance(main)" in progress


def test_ux_dr27_ux_dr28_explore_styles() -> None:
    """UX-DR27, UX-DR28, UX-DR11, UX-DR12: tail and active bars in DESIGN.md's colours, Highlight under forced
    colours, the build-up only from pre-build, and no motion with reduce motion on."""
    css = (WEB / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert ".chart-bar.is-tail { fill: var(--chart-tail); }" in css
    assert ".chart-bar.is-active { fill: var(--chart-active); }" in css
    forced = "".join(re.findall(r"@media \(forced-colors: active\) \{(.*?)\n\}", css, re.S))
    assert ".chart-bar.is-tail, .chart-bar.is-active { fill: Highlight; }" in forced
    assert ".chart-plot.pre-build .chart-bar { transform: scaleY(0); }" in css
    reduced = re.search(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", css, re.S).group(1)
    assert re.search(r"\.chart-bar, [^{]*\.chart-marker-line \{ transition: none; \}", reduced)
    script = JS.read_text(encoding="utf-8")
    assert '"(prefers-reduced-motion: reduce)"' in script and 'plot.classList.add("pre-build")' in script
    printed = re.search(r"@media print \{(.*?)\n\}", css, re.S).group(1)  # never left half-built on paper
    assert ".chart-plot.pre-build .chart-bar { transform: none; }" in printed


class FakeLookup:
    """Hands the page a fixed card, to show the variant no Sample Wallet has (Likely skilled)."""

    def __init__(self, card: VerdictCard) -> None:
        self.card = card

    def wallet_page(self, address: str, *, job: int | None = None, stored: bool = False) -> WalletPage:
        return WalletPage(Outcome.VERDICT, address, "0xabcd…ef01", card=self.card)


@pytest.mark.parametrize(
    ("verdict", "filled"),
    [("Skilled (high confidence)", 3), ("Likely skilled", 2), ("No evidence of skill", 0)],
)
def test_ux_dr20_all_dotted_variants(verdict: str, filled: int) -> None:
    """UX-DR20: ●●●, ●●○ and ○○○, always three dots, each with the Verdict read as "Verdict: …"."""
    card = VerdictCard(verdict, filled, "a trader with no edge would do this well x.", "40", "resolved bets", "$1", "Data stored x")
    app: Flask = create_app(Settings(), FakeLookup(card))  # type: ignore[arg-type]
    page = html(app.test_client(), f"/wallet/{UNKNOWN}")
    assert h1s(page) == [f"Verdict: {verdict}"]
    assert page.count('class="dot is-filled"') == filled
    assert page.count('class="dot"') == 3 - filled


# --- no Verdict to show, and bad addresses (FR-14, UX-DR7) --------------------------------------


def test_fr14_unknown_address_opened_directly(offline: FlaskClient) -> None:
    """FR-14, UX-DR18: the Verdict page of an address outside the Sample Dataset shows the error and the list."""
    page = html(offline, f"/wallet/{UNKNOWN}")
    assert h1s(page) == ["Not available offline"]
    assert '<span class="visually-hidden">Error: </span>Not available offline. In Offline Mode only' in page
    assert "Sample Wallets" in page


def test_live_run_verdict_page_starts_fetching(live: FlaskClient) -> None:
    """AD-5, UX-DR22 (Story 2.5): a live run's Verdict page queues a lookup and shows the fetching state;
    the rest of the live pages are tested in test_live_lookup.py."""
    reply = live.get(f"/wallet/{SHARP}")
    assert reply.status_code == 302 and reply.headers["Location"] == f"/wallet/{SHARP}?job=1"
    page = html(live, f"/wallet/{SHARP}?job=1")
    assert h1s(page) == [f"Checking {SHARP[:6]}…{SHARP[-4:]}"]


@pytest.mark.parametrize("url", ["/wallet/abc", "/wallet/0x123", f"/wallet/{SHARP}/x", "/no-such-page"])
def test_ux_dr7_page_not_found(offline: FlaskClient, url: str) -> None:
    """UX-DR7: any bad address shows Page not found with a link to Check a wallet."""
    page = html(offline, url, status=404)
    assert h1s(page) == ["Page not found"]
    assert '<a href="/">Check a wallet</a>' in page


def test_ux_dr7_upper_case_address_moves_to_lower_case(offline: FlaskClient) -> None:
    """FR-1: one URL per Wallet: an upper-case address redirects to the lower-case one."""
    response = offline.get("/wallet/0x" + SHARP[2:].upper())
    assert (response.status_code, response.headers["Location"]) == (301, f"/wallet/{SHARP}")


# --- look and files (UX-DR1, UX-DR3, UX-DR6) ---------------------------------------------------


def test_ux_dr1_colour_tokens_match_design_md() -> None:
    """UX-DR1, UX-DR2 (Edvard, 2026-11-20): `:root` holds the dark theme, the default, with each colour's
    DESIGN.md `-dark` value; `:root[data-theme="light"]` holds the same tokens with the light values."""
    design = dict(re.findall(r"^  ([a-z-]+): '(#[0-9A-F]{6})'$", DESIGN.read_text(encoding="utf-8"), re.M))
    css = (WEB / "static" / "css" / "app.css").read_text(encoding="utf-8")
    dark_block = re.search(r"^:root \{(.*?)^\}", css, re.S | re.M).group(1)
    light_block = re.search(r'^:root\[data-theme="light"\] \{(.*?)^\}', css, re.S | re.M).group(1)
    dark = dict(re.findall(r"--([a-z-]+): (#[0-9A-F]{6});", dark_block))
    light = dict(re.findall(r"--([a-z-]+): (#[0-9A-F]{6});", light_block))
    assert dark.pop("pill-edge") == design["border-strong-dark"]  # the pill's border-dark-theme
    assert dark and set(dark) == set(light), "the two themes must set the same colour tokens"
    for name in dark:
        assert design.get(name) == light[name], name
        assert design.get(f"{name}-dark") == dark[name], f"{name}-dark"
    assert "color-scheme: dark;" in dark_block and "color-scheme: light;" in light_block


def test_ux_dr2_theme_script_is_listed_and_falls_back(offline: FlaskClient) -> None:
    """UX-DR2, AD-18: theme.js is served, the README lists it, and every storage call is guarded so a
    blocked storage still lets the toggle switch the page."""
    script = html(offline, "/static/js/theme.js")
    assert script.count("localStorage") == 2 and script.count("try {") == 2
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "theme.js" in readme


def test_ad18_readme_lists_every_javascript_file() -> None:
    """AD-18: the README names each JavaScript file and what it does (Edvard, 2026-10-21)."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for script in sorted((WEB / "static" / "js").glob("*.js")):
        assert f"`{script.name}`:" in readme, script.name


def test_ux_dr22_fetching_dots_stand_still_with_reduce_motion() -> None:
    """UX-DR22, EXPERIENCE.md (Motion): the fetching dots pulse, and with *reduce motion* on they do not."""
    css = (WEB / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert re.search(r"\.fetch-dots span \{[^}]*animation: fetch-pulse", css)
    reduced = re.search(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", css, re.S)
    assert reduced and re.search(r"\.fetch-dots span \{[^}]*animation: none", reduced.group(1))


def test_ux_dr3_fonts_are_bundled_and_local(offline: FlaskClient) -> None:
    """UX-DR3, AD-18: IBM Plex Serif 600 and 700 as WOFF2 with the OFL licence, served by the app,
    and no stylesheet or page loading anything from the internet."""
    css = html(offline, "/static/css/app.css")
    assert not re.search(r"https?://|@import", css)
    for name, weight in [("IBMPlexSerif-SemiBold.woff2", 600), ("IBMPlexSerif-Bold.woff2", 700)]:
        assert f'url("../fonts/{name}")' in css and f"font-weight: {weight};" in css
        response = offline.get(f"/static/fonts/{name}")
        assert response.status_code == 200 and response.data[:4] == b"wOF2"
    licence = (WEB / "static" / "fonts" / "LICENSE.txt").read_text(encoding="utf-8")
    assert "SIL Open Font License, Version 1.1" in licence


def test_ux_dr6_logo_and_favicon_come_from_the_mockups(offline: FlaskClient) -> None:
    """UX-DR6: the favicon is the mockup file unchanged (it turns dark-theme blue by itself); the
    top-bar logo draws the master's shapes."""
    assert offline.get("/static/img/favicon.svg").data.replace(b"\r\n", b"\n") == (
        (MOCKUPS / "logo" / "favicon.svg").read_bytes().replace(b"\r\n", b"\n")
    )
    shapes = re.compile(r'<(?:circle|path|rect x="35[^"]*")[^>]*>')
    master = shapes.findall((MOCKUPS / "logo" / "liquidoracle-logo.svg").read_text(encoding="utf-8"))
    logo = shapes.findall((WEB / "templates" / "logo.svg.html").read_text(encoding="utf-8"))
    # The master is drawn in the accent blue; the top bar draws it in currentColor, set to the accent in app.css.
    normalise = lambda items: [re.sub(r' (class|mask)="[^"]*"', "", s).replace("#1D5BA6", "currentColor") for s in items]  # noqa: E731
    assert normalise(logo) == normalise(master) and len(master) >= 3


def test_app_factory_does_not_turn_on_debug(loaded_lookup: Lookup) -> None:
    """AD-23: the app is built with debug off."""
    assert create_app(Settings(), loaded_lookup).debug is False



# --- review fixes: error pages and tab titles (Story 1.7) ---------------------------------------


class BrokenStore:
    """A database that fails on every read, as a corrupt file would mid-run."""

    def __getattr__(self, name: str):
        def fail(*args, **kwargs):
            raise sqlite3.DatabaseError("file is not a database")
        return fail


def test_ad18_a_failing_database_shows_a_plain_error_page() -> None:
    """AD-18, Conventions › Errors (review): a database that cannot be read gives a page in the app's
    frame with a way back, never a raw exception or Werkzeug's bare page."""
    app = create_app(Settings(offline=True), Lookup(OfflineClient([]), BrokenStore(), seed=SEED))  # type: ignore[arg-type]
    for url in ("/", f"/wallet/{SHARP}"):
        page = html(app.test_client(), url, status=500)
        assert h1s(page) == ["Something went wrong"]
        assert "<title>Something went wrong · LiquidOracle</title>" in page
        assert '<a href="/">Check a wallet</a>' in page and "Traceback" not in page


def test_ux_dr7_a_post_gets_page_not_found(offline: FlaskClient) -> None:
    """UX-DR7 (review): no page takes a POST; it gets Page not found in the frame, not a bare 405."""
    response = offline.post("/")
    assert response.status_code == 404
    assert h1s(response.get_data(as_text=True)) == ["Page not found"]


def test_ux_dr8_message_pages_name_themselves_in_the_tab(offline: FlaskClient) -> None:
    """UX-DR8 (review): page name first, so the tab of a message page names the message."""
    page = html(offline, f"/wallet/{UNKNOWN}")
    assert f"<title>Not available offline · 0x0000…0000 · LiquidOracle</title>" in page


def test_fr14_listed_coin_flipper_before_load_sample(tmp_path: Path) -> None:
    """FR-14 (Edvard, 2026-11-20; review): on a fresh checkout every listed Sample Wallet, the
    Coin-flipper included, opens the "not loaded yet" page."""
    synthetic.write_small(tmp_path)
    store = Store(tmp_path / OFFLINE_DB)
    client = create_app(Settings(offline=True), Lookup(OfflineClient(sample_files(tmp_path)), store, seed=SEED)).test_client()
    for address in re.findall(r'class="wallet-link" href="/wallet/(0x[0-9a-f]{40})"', html(client, "/")):
        assert h1s(html(client, f"/wallet/{address}")) == ["Sample Dataset not loaded"], address
    store.close()


# --- the honesty notes and the Exit PnL warning (FR-11, UX-DR15, UX-DR29; Story 3.3) ----------


def honesty_card(page: str) -> str:
    found = re.search(r'<section class="card honesty-card".*?</section>', page, re.S)
    assert found, "no honesty notes card"
    return found.group(0)


def stats_row(page: str) -> str:
    found = re.search(r'<div class="stats-row">.*?</section>', page, re.S)
    assert found, "no stats row"
    return found.group(0)


def test_fr11_honesty_notes_follow_the_chart_card(offline: FlaskClient) -> None:
    """FR-11, UX-DR19, UX-DR29: Verdict card, chart card, then "What this test can't see" with its three columns,
    the left-out block and the computed-on line, in that order, never collapsed."""
    page = html(offline, f"/wallet/{SHARP}")
    assert page.index('class="verdict-card"') < page.index('class="card chart-card"') < page.index('class="card honesty-card"')
    card = honesty_card(page)
    assert '<h2 id="honesty-title">What this test can&#39;t see</h2>' in card
    assert "<details" not in card and not re.search(r"<[^>]*\shidden[\s>]", card)  # never collapsed or hidden
    order = [card.index(part) for part in (
        '<p class="figure">3%</p>', "of the Real PnL came from the single largest bet.",
        '<p class="figure">100 of 100</p>', "positions held to resolution.", "No shares were sold before resolution.",
        "Long shots tend to be overpriced", '<p class="not-advice">This is not financial advice.</p>',
        "<p>Left out of the test: none.</p>", "<p>Every fee matched the Market&#39;s fee schedule.</p>",
        '<p class="computed-on">Computed on all 100 bets · Seed 44</p>',
    )]
    assert order == sorted(order)
    assert re.findall(r"<h[12][\s>]", page) == ["<h1 ", "<h2 ", "<h2 "]  # headings in order (UX-DR11)


def test_fr10_fr11_not_enough_data_still_shows_the_honesty_notes(offline: FlaskClient) -> None:
    """FR-10, FR-11, UX-DR23: thin-wallet has no chart card but its honesty notes follow the Verdict card."""
    page = html(offline, f"/wallet/{THIN}")
    card = honesty_card(page)
    assert page.index('class="verdict-card"') < page.index('class="card honesty-card"')
    assert '<p class="figure">29 of 29</p>' in card and "Computed on all 29 bets · Seed 44" in card


def test_fr11_stop_loss_trader_warning_is_read_as_a_warning(offline: FlaskClient) -> None:
    """FR-11 check, UX-DR15: the stop-loss Synthetic Wallet's warning sits beside the stats, inside the Verdict card,
    its icon hidden and "Warning:" read first; the over-10% sentence uses the same box."""
    page = html(offline, f"/wallet/{STOP_LOSS}")
    row = stats_row(page)
    assert re.search(
        r'<div class="warning" role="note">\s*<svg class="warning-icon"[^>]*aria-hidden="true"[^>]*>.*?</svg>\s*'
        r'<p><span class="visually-hidden">Warning: </span><strong>Positions this Wallet sold before resolution lost '
        r"money in total\.</strong><br>This Verdict covers only bets held to resolution\.</p>",
        row, re.S,
    )
    assert row.index('class="stats"') < row.index('class="warning"')
    assert "<h1" not in row  # never in the Verdict hero (DESIGN.md)
    card = honesty_card(page)
    assert '<p>Shares sold before resolution: <strong class="amount">−$1,675</strong> (Exit PnL).</p>' in card
    assert re.search(
        r'<div class="warning" role="note">.*?<span class="visually-hidden">Warning: </span>Only part of this '
        r"Wallet&#39;s activity was judged: 67% of its bets were left out\.</p>",
        card, re.S,
    )


@pytest.mark.parametrize("address", [SHARP, THIN, COIN_FLIPPER])
def test_fr11_no_warning_without_an_exit_loss(offline: FlaskClient, address: str) -> None:
    """FR-11 check: Wallets that sold nothing before resolution show no warning anywhere."""
    page = html(offline, f"/wallet/{address}")
    assert 'class="warning"' not in page and "Warning:" not in page


def test_ux_dr15_ux_dr29_honesty_styles() -> None:
    """UX-DR15, UX-DR29, UX-DR12: the warning tokens, the three columns stacking below 900 px, and a warning box that
    keeps its border in forced colours."""
    css = (WEB / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert "background: var(--warning-bg); color: var(--warning-ink);" in css
    assert "border-left: 6px solid var(--warning-border);" in css
    assert ".limits-grid { display: grid; grid-template-columns: 1fr 1fr 1.6fr;" in css
    narrow = re.search(r"@media \(max-width: 899px\) \{(.*?)\n\}", css, re.S).group(1)
    assert ".limits-grid { grid-template-columns: minmax(0, 1fr); }" in narrow and ".stats-row" in narrow
    forced = re.search(r"@media \(forced-colors: active\) \{\n  \.dot\.is-filled(.*?)\n\}", css, re.S).group(1)
    assert ".warning { border: 1px solid CanvasText;" in forced


def test_fr11_a_losing_wallet_shows_its_largest_bet_as_an_amount(offline: FlaskClient) -> None:
    """FR-11, EXPERIENCE.md Voice and Tone: coin-flipper-0000 lost money, so the first column reads
    "Largest single bet:" over the amount, with no share sentence."""
    card = honesty_card(html(offline, f"/wallet/{COIN_FLIPPER}"))
    assert re.search(r'<div>\s*<p class="figure-label">Largest single bet:</p>\s*<p class="figure">\$90</p>\s*</div>', card)
    assert "of the Real PnL came from" not in card


def test_fr11_capped_real_wallet_page_shows_the_window_line(tmp_path: Path) -> None:
    """FR-11, AD-22 (Story 3.3 review): 0x94884d's window was capped at 2,000, so its page shows the window line and
    names the latest 2,000 bets."""
    address = "0x94884db79666a1a34c46d03fb4f8e9cbcaf6b5a6"
    client = OfflineClient([REPO / REAL_DIR / f"{address}.json"])
    store = Store(tmp_path / OFFLINE_DB)
    try:
        fetch_wallet(client, store, address)
        page = html(create_app(Settings(offline=True), Lookup(client, store, seed=SEED)).test_client(), f"/wallet/{address}")
    finally:
        store.close()
    card = honesty_card(page)
    assert "<p>Based on the latest 2,000 bets; older results are not included.</p>" in card
    assert '<p class="computed-on">Computed on the latest 2,000 bets · Seed 44</p>' in card


class NotesLookup:
    """A lookup whose one page carries the given honesty notes (the linked-bets note needs a planted share)."""

    def __init__(self, page: WalletPage) -> None:
        self.page = page

    def wallet_page(self, address: str, *, job: int | None = None, stored: bool = False) -> WalletPage:
        return self.page


def test_fr11_linked_bets_note_reaches_the_page(loaded_lookup: Lookup) -> None:
    """FR-11, AD-20 (Story 3.3 review): when more than 20% of the tested bets have an event-mate, the note is on the card."""
    page = loaded_lookup.wallet_page(SHARP)
    assert page.notes is not None and page.notes.linked == ""
    planted = dataclasses.replace(page, notes=dataclasses.replace(page.notes, linked="34% of the tested bets share an event."))
    app: Flask = create_app(Settings(offline=True), NotesLookup(planted))  # type: ignore[arg-type]
    card = honesty_card(html(app.test_client(), f"/wallet/{SHARP}"))
    assert "<p>34% of the tested bets share an event.</p>" in card


# Story 3.4: the copy button, interaction states and breakpoints. What only a browser can show (copying,
# widths, hover, reduced motion) is in tests/browser/; these check what the server and stylesheet hand it.

COPY_JS = WEB / "static" / "js" / "copy-address.js"


def address_card(page: str) -> str:
    start = page.index('<div class="address-card">')
    return page[start:page.index("<hr", start)]


def test_ux_dr21_copy_button_markup(offline: FlaskClient) -> None:
    """UX-DR21, AD-18: the address card holds the full address, a named copy button with its words in data-
    attributes, the error line with a hidden "Error: " (hidden until a copy fails) and a status line."""
    card = address_card(html(offline, f"/wallet/{SHARP}"))
    assert f'<code class="address">{SHARP}</code>' in card
    button = re.search(r'<button class="icon-button copy-button"[^>]*>', card).group(0)
    assert 'type="button"' in button and "aria-label" not in button
    # WCAG 2.5.3: the name is the button's own text, so the visible "Copied" joins it while it shows.
    assert '<span class="visually-hidden">Copy wallet address </span><span class="copy-label"></span>' in card
    assert 'data-copied="Copied"' in button and 'data-done="Address copied"' in button
    assert 'data-mac-text="Copy failed. Select the address and press ⌘C."' in button
    assert ('<p class="copy-error" hidden><span class="visually-hidden">Error: </span>'
            '<span class="copy-error-text">Copy failed. Select the address and press Ctrl+C.</span></p>') in card
    assert '<p class="visually-hidden copy-status" role="status"></p>' in card


def test_ad18_copy_button_shows_only_with_the_script() -> None:
    """AD-18, UX-DR21: the stylesheet hides the copy button until copy-address.js marks the page, so without
    JavaScript there is no dead button; the script marks the page and listens on the whole document, so a
    Verdict that progress.js swaps in works too."""
    css = (WEB / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert ".copy-button { display: none; }" in css and ":root.has-copy .copy-button { display: inline-flex; }" in css
    script = COPY_JS.read_text(encoding="utf-8")
    assert 'root.classList.add("has-copy");' in script and 'document.addEventListener("click"' in script


def test_ad25_copy_script_writes_no_words() -> None:
    """AD-25, UX-DR21: copy-address.js reads every word from the page; its own strings are names only."""
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", COPY_JS.read_text(encoding="utf-8"), flags=re.S)
    assert "'" not in code and "`" not in code  # every string is double-quoted, so the scan below sees them all
    for text in re.findall(r'"([^"\\]*)"', code):
        assert re.fullmatch(r"[a-z.-]*|use strict|click", text), text
    assert "innerHTML" not in code


def css_rules(css: str) -> list[tuple[str, str]]:
    """(media condition, selector) for every rule, one level of @media deep; comments removed."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules, heads = [], []
    for match in re.finditer(r"([^{}]+)\{|\}", css):
        if match.group(0) == "}":
            heads.pop()
            continue
        head = " ".join(match.group(1).split())
        if not head.startswith("@"):
            rules.append((next((h for h in heads if h.startswith("@media")), ""), head))
        heads.append(head)
    return rules


def test_ux_dr9_every_hover_has_a_focus_twin() -> None:
    """UX-DR9: every hover rule sits in a media query with (hover: hover), and a :focus-visible rule in the same
    media without it styles the same thing, so keyboard focus looks like hover (also under forced colours);
    hover never lands on cards, stats or text."""
    css = (WEB / "static" / "css" / "app.css").read_text(encoding="utf-8")
    rules = css_rules(css)
    hover = [(media, s.strip()) for media, head in rules for s in head.split(",") if ":hover" in s]
    assert hover, "no hover rules found"
    focus = {(media, s.strip()) for media, head in rules for s in head.split(",") if ":focus-visible" in s}
    for media, selector in hover:
        if "reduced-motion" in media:
            continue  # this block only takes the movement away again
        assert "(hover: hover)" in media, selector
        twin_media = re.sub(r"^@media \(hover: hover\)$|\s+and \(hover: hover\)", "", media)
        assert (twin_media, selector.replace(":hover", ":focus-visible")) in focus, selector
        assert not re.search(r"\.(card|verdict-card|stats|chart-alt|limits-grid|left-out)\b", selector), selector


def test_ux_dr10_ux_dr11_breakpoints_and_motion_rules() -> None:
    """UX-DR10, UX-DR11: only the 900, 640 and 400 px breakpoints; the Verdict header stacks below 900 px;
    phone sizes below 640 px and the smallest Verdict below 400 px; nothing lifts or moves with reduce motion."""
    css = (WEB / "static" / "css" / "app.css").read_text(encoding="utf-8")
    widths = set(re.findall(r"@media \(max-width: (\d+)px\)", css))
    assert widths == {"899", "639", "399"}
    stack = re.search(r"@media \(max-width: 899px\) \{[^\n]*\n(.*?)\n\}", css, re.S).group(1)
    assert ".verdict-head, .stats-row { grid-template-columns: minmax(0, 1fr); }" in stack
    phone = "".join(re.findall(r"@media \(max-width: 639px\) \{[^\n]*\n(.*?)\n\}", css, re.S))
    for rule in (".verdict { font-size: 40px; gap: 18px; }", ".odds { font-size: 21px; }", "h1 { font-size: 36px;",
                 ".field-row { flex-direction: column; }", ".wrap { padding: 0 var(--space-4); }"):
        assert rule in phone, rule
    assert re.search(r"@media \(max-width: 399px\) \{\s*\.verdict \{ font-size: 34px; \}", css)
    reduced = "".join(re.findall(r"@media \(prefers-reduced-motion: reduce\) \{[^\n]*\n(.*?)\n\}", css, re.S))
    assert ".theme-toggle, .icon-button, .btn-primary { transition: none; }" in reduced
    assert ".btn-primary:hover, .btn-primary:focus-visible { transform: none; }" in reduced
