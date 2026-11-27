"""The Watchlist in a real browser: the "Not fully read" tooltip by pointer, keyboard and Esc (tag-tip.js), the
whole-row link, and the layout at phone widths (UX-DR10, UX-DR33, UX-DR34, UX-DR37, WCAG 1.4.13; Story 4.5).

The app is a live run over a database whose finished Scan is written by hand (`hand_scan`), so no worker runs
and nothing reaches Polymarket.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import serving
from pages import MakePage, assert_no_sideways_scroll
from playwright.sync_api import Page, expect
from test_watchlist import Row, hand_scan

from liquidoracle.data.store import Store
from liquidoracle.services.jobs import Jobs
from liquidoracle.services.lookup import Lookup
from liquidoracle.services.watchlist import NOT_FULLY_READ_TIP
from liquidoracle.settings import Settings
from liquidoracle.web import create_app

FLAGGED = "0x" + "5" * 40
CLEAN = "0x" + "6" * 40


@pytest.fixture
def watchlist(make_page: MakePage, tmp_path: Path) -> Iterator[MakePage]:
    path = tmp_path / "live.db"
    store = Store(path)
    scan_id = hand_scan(path, [Row(CLEAN, p_value=0.0002), Row(FLAGGED, p_value=0.003, unread=True)],
                        markets=(("0x" + "a" * 64, 9e6, "used"), ("0x" + "b" * 64, 8e6, "partial")))
    app = create_app(Settings(offline=False), Lookup(None, store, seed=44, jobs=Jobs(store)))
    try:
        with serving(app) as url:
            def make(**options) -> Page:
                return make_page(f"/scans/{scan_id}/watchlist", base=url, **options)
            yield make
    finally:
        store.close()


def test_wcag_1_4_13_the_tooltip_shows_on_hover_stays_on_itself_and_esc_hides_it(watchlist: MakePage) -> None:
    """UX-DR34, WCAG 1.4.13, EXPERIENCE.md *Wallet not fully read*: pointing at the tag shows the sentence; moving onto the
    tooltip keeps it; Esc hides it without moving the pointer; leaving and coming back shows it again."""
    page = watchlist()
    tag = page.locator(".info-tag")
    tip = page.get_by_role("tooltip")
    expect(tip).to_be_hidden()
    tag.hover()
    expect(tip).to_be_visible()
    expect(tip).to_have_text(NOT_FULLY_READ_TIP)
    tip.hover()
    expect(tip).to_be_visible()
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.mouse.move(0, 0)
    tag.hover()
    expect(tip).to_be_visible()


def test_wcag_1_4_13_the_tooltip_shows_on_keyboard_focus_and_esc_hides_it(watchlist: MakePage) -> None:
    """UX-DR34, WCAG 2.1.1, 1.4.13: Tab reaches the tag, which then shows its sentence and is described by it; Esc hides it;
    Tab away and back shows it again."""
    page = watchlist()
    tag = page.locator(".info-tag")
    tip = page.get_by_role("tooltip")
    page.locator(f'a.row-link[href$="{FLAGGED}"]').focus()
    page.keyboard.press("Tab")
    expect(tag).to_be_focused()
    expect(tip).to_be_visible()
    expect(tag).to_have_accessible_description(NOT_FULLY_READ_TIP)
    expect(tag).to_have_role("button")  # review pass 2: a named role, not a bare focusable span
    expect(tag).to_have_accessible_name("Not fully read")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    expect(tip).to_be_visible()


def test_ux_dr34_a_tap_opens_the_tooltip_on_a_touch_screen(watchlist: MakePage) -> None:
    """UX-DR34, Story 4.5 review: a touch screen has no hover and a tap's focus is not :focus-visible, so the tag
    shows its sentence on any focus; tapping elsewhere hides it."""
    page = watchlist(has_touch=True)
    tip = page.get_by_role("tooltip")
    page.locator(".info-tag").tap()
    expect(tip).to_be_visible()
    page.locator("h1").tap()
    expect(tip).to_be_hidden()


def test_ad18_without_javascript_the_tooltip_still_works_by_css(watchlist: MakePage) -> None:
    """AD-18: without tag-tip.js the sentence still shows on hover and is the tag's description."""
    page = watchlist(java_script_enabled=False)
    page.locator(".info-tag").hover()
    expect(page.get_by_role("tooltip")).to_be_visible()
    expect(page.locator(".info-tag")).to_have_accessible_description(NOT_FULLY_READ_TIP)


def test_ux_dr34_clicking_anywhere_on_a_row_opens_its_verdict(watchlist: MakePage) -> None:
    """UX-DR34: the whole row clicks through to the Verdict from the Scan, which links back to the Watchlist; the
    address is the row's one link, so the row is one Tab stop (the tag aside)."""
    page = watchlist()
    row = page.locator("tbody tr").first
    expect(row.get_by_role("link")).to_have_count(1)
    cell = row.locator("td").nth(3).bounding_box()  # a plain cell: the link's cover takes the click, as for a person
    assert cell
    page.mouse.click(cell["x"] + cell["width"] / 2, cell["y"] + cell["height"] / 2)
    expect(page).to_have_url(re.compile(rf"/scans/\d+/wallet/{CLEAN}$"))
    page.get_by_role("link", name="Back to Watchlist (Cut-off Date 1 July 2025)").click()
    expect(page.get_by_role("heading", level=1)).to_have_text("Scan of 2 Wallets")


@pytest.mark.parametrize("width", [320, 400, 900])
def test_ux_dr10_the_watchlist_never_scrolls_sideways(watchlist: MakePage, width: int) -> None:
    """UX-DR10: no sideways page scroll at phone widths; the table scrolls in its own named box instead; the summary
    card drops below the title under 900 px."""
    page = watchlist(width=width)
    assert_no_sideways_scroll(page, f"Watchlist at {width} px")
    title, card = page.locator("h1").bounding_box(), page.locator(".scan-summary").bounding_box()
    assert title and card
    assert (card["y"] > title["y"] + title["height"]) == (width < 900)


def test_ux_dr12_forced_colours_keep_the_pill_dots(watchlist: MakePage) -> None:
    """UX-DR12: in forced colours the pill's filled dots keep their fill, so the Verdict's strength still shows."""
    page = watchlist(forced_colors="active")
    filled = page.locator(".pill-dot.is-filled").first
    empty = page.locator(".pill-dot:not(.is-filled)")
    assert empty.count() == 0  # every Watchlist row is Skilled: three filled dots
    fill = filled.evaluate("e => getComputedStyle(e).backgroundColor")
    assert fill not in ("rgba(0, 0, 0, 0)", "transparent")
