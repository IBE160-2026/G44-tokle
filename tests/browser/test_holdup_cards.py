"""The Hold-up Test page in a real browser: the two cards side by side only from 900 px, no sideways scroll at
phone widths, the Scan tabs by keyboard, forced colours, and the page with JavaScript off (FR-17, UX-DR10, UX-DR12,
UX-DR33, UX-DR35, AD-18; Story 5.2).

The app runs over a database whose finished Scan and Hold-up rows are written by hand (`held_up_scan`), so no
worker runs and nothing reaches Polymarket. The offline app is the same store behind an Offline Mode app.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import serving
from pages import MakePage, assert_no_sideways_scroll, box, style
from playwright.sync_api import Page, expect
from test_holdup_page import NOT_ENOUGH, comparison, held_up_scan, passers

from liquidoracle.data.offline import OfflineClient
from liquidoracle.data.store import Store
from liquidoracle.services import holdup as words
from liquidoracle.services.jobs import Jobs
from liquidoracle.services.lookup import Lookup
from liquidoracle.settings import Settings
from liquidoracle.web import create_app


@pytest.fixture
def holdup(make_page: MakePage, tmp_path: Path) -> Iterator[MakePage]:
    """`make(scan="full" | "small" | "big", offline=False, **page options)`: the Hold-up page of the offline Scan's
    stored rows, of a Scan whose Passers are too few to test, or of one with nine-digit amounts as a large live Scan
    could give, in a live run or in Offline Mode."""
    path = tmp_path / "live.db"
    store = Store(path)
    scans = {
        "full": held_up_scan(path),
        "small": held_up_scan(path, passers(NOT_ENOUGH, None, 12, -40.0, wallets=3, dropped=2), comparison()),
        "big": held_up_scan(
            path, passers(pnl=987_654_321.0, tested=1_234_567, wallets=12_345, dropped=1_234, unread=123),
            comparison(pnl=-123_456_789.4, tested=7_654_321, wallets=98_765, dropped=43_210, unread=4_321),
        ),
    }
    live = create_app(Settings(offline=False), Lookup(None, store, seed=44, jobs=Jobs(store)))
    sample = create_app(Settings(offline=True), Lookup(OfflineClient([]), store, seed=44))
    try:
        with serving(live) as live_url, serving(sample) as sample_url:
            def make(scan: str = "full", *, offline: bool = False, **options) -> Page:
                return make_page(f"/scans/{scans[scan]}/hold-up", base=sample_url if offline else live_url, **options)
            yield make
    finally:
        store.close()


@pytest.mark.parametrize("width", [320, 400, 899, 900, 1280])
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_ux_dr35_the_cards_sit_side_by_side_only_from_900_px(holdup: MakePage, width: int, theme: str) -> None:
    """UX-DR35, UX-DR10 (EXPERIENCE.md Responsive): from 900 px the two group cards are side by side with the same
    top and height; below, the Comparison Group card is under the Passers card. No width scrolls sideways, in either
    theme, with the warning and the offline info box showing."""
    page = holdup(offline=True, width=width, theme=theme)
    assert_no_sideways_scroll(page, f"Hold-up Test at {width} px, {theme}")
    first, second = (page.locator(".group-card").nth(i).bounding_box() for i in (0, 1))
    assert first and second
    if width >= 900:
        assert second["x"] > first["x"] + first["width"] and abs(second["y"] - first["y"]) < 1
        assert abs(second["height"] - first["height"]) < 1
    else:
        assert second["y"] >= first["y"] + first["height"] and abs(second["x"] - first["x"]) < 1
    cards = box(page, ".group-cards")
    assert box(page, ".group-warning")["y"] < box(page, "#offline-note")["y"] < cards["y"]
    assert box(page, ".group-note")["y"] >= cards["y"] + cards["height"]
    # The figures: two columns where a card has room for two, one column on a phone (review, Story 5.2).
    one, two = (page.locator(".group-card").first.locator("dd").nth(i).bounding_box() for i in (0, 1))
    assert one and two
    if width in (320, 400):
        assert abs(two["x"] - one["x"]) < 1 and two["y"] > one["y"] + one["height"]
    elif width in (899, 1280):  # at 899 px a stacked card is wide enough for three, and still has two
        assert abs(two["y"] - one["y"]) < 1 and two["x"] > one["x"] + one["width"]
        three = page.locator(".group-card").first.locator("dd").nth(2).bounding_box()
        assert three and abs(three["x"] - one["x"]) < 1 and three["y"] > one["y"] + one["height"]


def test_ux_dr35_two_numbers_in_a_row_line_up(holdup: MakePage) -> None:
    """UX-DR35 (found on the first screenshots, Story 5.2): "Wallets dropped" has a longer label than "Wallets in the
    group" beside it, and the two numbers still stand on one line."""
    page = holdup(width=1280)
    numbers = page.locator(".group-card").nth(1).locator("dd")
    in_group, dropped = numbers.nth(2).bounding_box(), numbers.nth(3).bounding_box()
    assert in_group and dropped and abs(in_group["y"] - dropped["y"]) < 1
    expect(numbers.nth(1)).to_have_text("−$19,217")
    # Side by side, the two cards' rows line up although the Comparison Group's "who is in the group" line is the
    # longer one (found on a screenshot after the line was added, Story 5.2).
    for selector in (".verdict-pill", ".group-odds", "dd"):
        left, right = (page.locator(".group-card").nth(i).locator(selector).first.bounding_box() for i in (0, 1))
        assert left and right and abs(left["y"] - right["y"]) < 1, selector


@pytest.mark.parametrize("width", [320, 360, 400, 480, 640, 899, 900, 960, 1280])
def test_ux_dr10_nine_digit_amounts_stay_whole_and_inside_their_card(holdup: MakePage, width: int) -> None:
    """UX-DR10, UX-DR14 (review, Story 5.2): a large live Scan can pool to amounts like −$123,456,789. At every width
    each number stays on one line (a negative amount never splits after its minus sign), fits its own cell without
    running over the figure beside it, and the page does not scroll sideways: where two columns would be too
    narrow, the figures go to one."""
    page = holdup("big", width=width)
    assert_no_sideways_scroll(page, f"Hold-up Test with large amounts at {width} px")
    expect(page.locator(".group-card").nth(1).locator("dd").nth(1)).to_have_text("−$123,456,789")
    for card in page.locator(".group-card").all():
        inside = card.bounding_box()
        assert inside
        numbers = card.locator("dd")
        expect(numbers).to_have_count(5)
        boxes = []
        for number in numbers.all():
            lines, spill = number.evaluate(
                "e => [Math.round((e.getBoundingClientRect().height - parseFloat(getComputedStyle(e).paddingTop))"
                " / parseFloat(getComputedStyle(e).lineHeight)), e.scrollWidth - e.clientWidth]"
            )
            assert lines == 1 and spill <= 0, f"{number.inner_text()} at {width} px: {lines} lines, {spill} px too wide"
            found = number.bounding_box()
            assert found and found["x"] + found["width"] <= inside["x"] + inside["width"]
            boxes.append(found)
        for first, second in zip(boxes, boxes[1:]):  # neighbours in one row never overlap
            if abs(first["y"] - second["y"]) < 1:
                assert first["x"] + first["width"] <= second["x"]
    if width == 1280:
        # Even in a cell far too narrow, the amount is not broken after its minus sign: it stays one line.
        amount = page.locator(".group-card").nth(1).locator("dd").nth(1)
        one_line = amount.bounding_box()
        page.add_style_tag(content=".group-figures > div { width: 3rem; }")
        squeezed = amount.bounding_box()
        assert one_line and squeezed and squeezed["width"] < 60 and abs(squeezed["height"] - one_line["height"]) < 1


def test_ux_dr33_the_scan_tabs_are_links_walked_by_keyboard(holdup: MakePage) -> None:
    """UX-DR33, UX-DR13: the tabs are two links in a navigation region named "Scan"; the page being shown is the
    current one; Tab reaches them in order with a visible focus ring, and Enter on *Watchlist* opens that page, where
    *Watchlist* is the current one and the same Scan header stands."""
    page = holdup()
    nav = page.get_by_role("navigation", name="Scan")
    expect(nav.get_by_role("link")).to_have_text(["Watchlist", "Hold-up Test"])
    expect(nav.locator('[aria-current="page"]')).to_have_text("Hold-up Test")
    expect(page.get_by_role("tab")).to_have_count(0)
    title = page.locator("h1").inner_text()
    nav.get_by_role("link", name="Watchlist").focus()
    page.keyboard.press("Tab")
    current = nav.get_by_role("link", name="Hold-up Test")
    expect(current).to_be_focused()
    assert current.evaluate("e => e.matches(':focus-visible') && getComputedStyle(e).outlineStyle !== 'none'")
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"/scans/\d+/watchlist$"))
    expect(page.get_by_role("navigation", name="Scan").locator('[aria-current="page"]')).to_have_text("Watchlist")
    expect(page.locator("h1")).to_have_text(title)
    page.get_by_role("navigation", name="Scan").get_by_role("link", name="Hold-up Test").click()
    expect(page).to_have_title("Hold-up Test · 1 Jul 2025 · LiquidOracle")


def test_ux_dr35_a_screen_reader_is_given_the_cards_in_order(holdup: MakePage) -> None:
    """UX-DR35, UX-DR11, UX-DR13: one main heading, then each card as a region named by its title, the Passers first;
    the Verdict is read as "Verdict: …" with the dots hidden; the warning is a note starting with "Warning:" and
    comes before the cards in reading order."""
    page = holdup()
    expect(page.get_by_role("heading", level=1)).to_have_count(1)
    expect(page.get_by_role("heading", level=2)).to_have_text(["Before-Cut-off Passers", "Comparison Group"])
    regions = page.get_by_role("region")
    expect(regions).to_have_count(2)
    expect(regions.nth(0)).to_have_accessible_name("Before-Cut-off Passers")
    # who is in the group is read right after the title, before the Verdict (Edvard, 2026-11-27)
    expect(regions.nth(0).locator(".group-who")).to_have_text(
        "Wallets rated Skilled (high confidence) on their bets before the Cut-off Date."
    )
    assert regions.nth(0).evaluate(
        "e => [...e.querySelectorAll('h2, .group-who, .verdict-pill, .group-odds, dl')].map(x => x.className || x.tagName)"
    ) == ["H2", "sub group-who", "verdict-pill", "group-odds", "group-figures"]
    expect(regions.nth(0).locator(".verdict-pill")).to_have_text(re.compile(r"^\s*Verdict: Skilled \(high confidence\)\s*$"))
    expect(regions.nth(0).locator(".pill-dots")).to_have_attribute("aria-hidden", "true")
    expect(regions.nth(1).get_by_role("term")).to_have_count(5)
    expect(regions.nth(1).get_by_role("definition")).to_have_text(["409", "−$19,217", "999", "996", "0"])
    warning = page.get_by_role("note")
    expect(warning).to_have_count(1)  # a live run: no offline info box
    expect(warning).to_have_text(re.compile(r"^\s*Warning: More Wallets were dropped"))
    order = page.evaluate(
        "() => [...document.querySelectorAll('main h1, main [role=note], main h2, main .group-note')]"
        ".map(e => e.className || e.tagName)"
    )
    assert order == ["H1", "warning group-warning", "H2", "H2", "group-note"]


def test_ad18_the_page_is_whole_without_javascript(holdup: MakePage) -> None:
    """AD-18: with JavaScript off the offline page shows the warning, the info box with both sentences, both cards
    and the note; the tabs still work, because they are links."""
    page = holdup(offline=True, java_script_enabled=False)
    expect(page.locator(".group-warning")).to_be_visible()
    expect(page.locator("#offline-note")).to_have_text(re.compile(re.escape(words.OFFLINE_PASSERS) + r"\s+" + re.escape(words.OFFLINE_WARNING)))
    expect(page.locator(".group-card")).to_have_count(2)
    expect(page.locator(".group-note")).to_have_text(words.NOTE)
    page.get_by_role("link", name="Watchlist", exact=True).click()
    expect(page).to_have_url(re.compile(r"/watchlist$"))


def test_ux_dr12_forced_colours_keep_the_pills_and_the_warning(holdup: MakePage) -> None:
    """UX-DR12: in forced colours the filled dots keep their fill and the empty ones their ring, every pill gets an
    outline in place of its lost tint (dashed for *Not enough data*), and the warning box keeps a border."""
    page = holdup(forced_colors="active")
    clear = ("rgba(0, 0, 0, 0)", "transparent")
    filled = page.locator(".group-card").nth(0).locator(".pill-dot.is-filled")
    expect(filled).to_have_count(3)
    assert filled.first.evaluate("e => getComputedStyle(e).backgroundColor") not in clear
    empty = page.locator(".group-card").nth(1).locator(".pill-dot:not(.is-filled)")
    expect(empty).to_have_count(3)
    assert empty.first.evaluate("e => getComputedStyle(e).borderTopWidth") == "3px"
    assert style(page, ".group-warning", "border-left-style") == "solid"
    for card in (0, 1):  # the accent and the neutral pill: an outline, since the tint is gone (review, Story 5.2)
        outline = page.locator(".group-card").nth(card).locator(".verdict-pill").evaluate(
            "e => [getComputedStyle(e).borderTopStyle, getComputedStyle(e).borderTopWidth]"
        )
        assert outline == ["solid", "1px"]
    plain = holdup()
    assert plain.locator(".group-card").first.locator(".verdict-pill").evaluate("e => getComputedStyle(e).borderTopStyle") == "none"
    small = holdup("small", forced_colors="active")
    assert style(small, ".verdict-pill.is-none", "border-top-style") == "dashed"
    expect(small.locator(".verdict-pill.is-none .pill-dot")).to_have_count(0)


def test_ux_dr35_the_pill_tints_tell_the_verdicts_apart(holdup: MakePage) -> None:
    """UX-DR35, DESIGN.md Verdict pill: *Skilled* sits on the accent tint, *No evidence of skill* on the neutral
    tint, and *Not enough data* has no fill and a dashed outline; each is also text."""
    page = holdup()
    accent = page.locator(".group-card").nth(0).locator(".verdict-pill").evaluate("e => getComputedStyle(e).backgroundColor")
    neutral = style(page, ".verdict-pill.is-neutral", "background-color")
    assert accent != neutral and "rgba(0, 0, 0, 0)" not in (accent, neutral)
    small = holdup("small")
    assert style(small, ".verdict-pill.is-none", "background-color") == "rgba(0, 0, 0, 0)"
    expect(small.locator(".group-odds").first).to_have_text("12 resolved bets; at least 30 are needed for a Verdict (18 more)")
