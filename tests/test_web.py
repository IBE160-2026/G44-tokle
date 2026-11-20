"""The pages: Check a wallet, the Verdict page and Page not found (FR-1, FR-8, FR-10, FR-14, AD-18; Story 1.7).

The app runs over the lookup service with the committed Synthetic Wallets and 3 coin-flippers
loaded, through Flask's test client, with sockets blocked. Markup checks follow EXPERIENCE.md
› Accessibility Floor and the UX-DR items named in each test.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from liquidoracle.data import synthetic
from liquidoracle.data.offline import OfflineClient, sample_files
from liquidoracle.data.store import OFFLINE_DB, Store
from liquidoracle.services.fetch import fetch_wallet
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
    yield create_app(Settings(offline=False), Lookup(None, store, seed=SEED)).test_client()
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
    with logo and Check a wallet, the favicon and the Offline pill. The only script is the theme.js
    file (no inline code), and its toggle is hidden until that script shows it (UX-DR2)."""
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
    assert re.findall(r"<script[^>]*>(.*?)</script>", page, re.S) == [""]
    assert '<script src="/static/js/theme.js"></script>' in page
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


class FakeLookup:
    """Hands the page a fixed card, to show the variant no Sample Wallet has (Likely skilled)."""

    def __init__(self, card: VerdictCard) -> None:
        self.card = card

    def wallet_page(self, address: str) -> WalletPage:
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


def test_live_run_verdict_page(live: FlaskClient) -> None:
    """AD-13 (Edvard, 2026-11-20): a live run says live lookups are not built yet and how to start offline."""
    page = html(live, f"/wallet/{SHARP}")
    assert h1s(page) == ["Live lookups not built yet"]
    assert "Start the app with <code>--offline</code> to check the Sample Wallets." in page


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
