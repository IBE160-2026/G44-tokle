"""chart.js in a real browser: the slider, the tooltip, the marker, the build-up and the page without it (Story 3.5).

The 45 chart.js checks of Story 3.2 ran once in a throwaway script; these keep them. Pages come from the
Offline Mode app over the Synthetic Wallets: sharp-trader (marker on the last bar but one), stop-loss-trader
(above every replay: "No replay …", no bar lit) and favourite-buyer (marker in the middle). The words and
numbers come from the page (data- attributes), so these tests check what the script does with them, not
the bins and counts the Python tests already prove. Timing uses the page's paused clock, never a sleep.
"""

from __future__ import annotations

import re

import pytest
from pages import overlaps
from playwright.sync_api import Page, expect

from liquidoracle.data import synthetic

SHARP = synthetic.address_of("sharp-trader")
STOP_LOSS = synthetic.address_of("stop-loss-trader")
FAVOURITE = synthetic.address_of("favourite-buyer")
CHART_WALLETS = [SHARP, STOP_LOSS, FAVOURITE]
SHOWN = re.compile(r"\bis-shown\b")
BUILDING = re.compile(r"\bis-building\b")


def bars(page: Page) -> list[dict]:
    """Each bar's range, count and classes, in order."""
    return page.locator(".chart-bar").evaluate_all(
        "(all) => all.map((b) => ({ range: b.dataset.range, count: b.dataset.count, cls: b.getAttribute('class') }))"
    )


def lit(page: Page) -> list[int]:
    """The bars the marker lights (class is-tail)."""
    return [i for i, bar in enumerate(bars(page)) if "is-tail" in bar["cls"].split()]


def tail_from(page: Page) -> int:
    return int(page.locator(".chart").get_attribute("data-tail-from"))


def assert_value(page: Page, number: int) -> None:
    """The slider is on bar `number` (1-based): its value, its spoken text and the tooltip all say that bar."""
    slider, tip = page.locator(".chart-explore"), page.locator(".chart-tip")
    bar = bars(page)[number - 1]
    assert slider.get_attribute("aria-valuenow") == str(number)
    assert slider.get_attribute("aria-valuetext") == f"{bar['range']}: {bar['count']}"
    assert tip.inner_text().split("\n") == [bar["range"], bar["count"]]
    assert "is-active" in bar["cls"].split()
    expect(tip).to_have_class(SHOWN)


def point_at_bar(page: Page, index: int) -> None:
    """Moves the pointer over bar `index` on the slider that covers the bars."""
    bar = page.locator(".chart-bar").nth(index).bounding_box()
    slider = page.locator(".chart-explore").bounding_box()
    page.mouse.move(bar["x"] + bar["width"] / 2, slider["y"] + slider["height"] / 2)


def test_ux_dr26_tab_reaches_the_slider_then_the_marker(make_page) -> None:
    """UX-DR26, UX-DR27 (Story 3.5): after "About this chart", Tab reaches the slider "Replays by result",
    then the marker button."""
    page = make_page(f"/wallet/{SHARP}")
    page.locator(".about summary").focus()
    page.keyboard.press("Tab")
    expect(page.get_by_role("slider", name="Replays by result")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator(".chart-marker-button")).to_be_focused()


def test_ux_dr26_slider_keys(make_page) -> None:
    """UX-DR26, 3.5 matrix "Slider keys": Left/Down and Right/Up step one bar, Page Down/Up ten, Home/End go to
    the ends, and the spoken value is the tooltip's text; at both ends the keys stop."""
    page = make_page(f"/wallet/{SHARP}")
    count = page.locator(".chart-bar").count()
    marker = int(page.locator(".chart").get_attribute("data-marker-bar")) + 1
    assert 11 <= marker < count, f"the key steps below need the marker on bar 11 or later, before the last ({marker} of {count})"
    page.locator(".chart-explore").focus()
    assert_value(page, marker)  # focus starts on the marker's bar
    steps = [
        ("ArrowLeft", marker - 1), ("ArrowDown", marker - 2), ("ArrowRight", marker - 1), ("ArrowUp", marker),
        ("PageDown", marker - 10), ("PageUp", marker), ("End", count), ("ArrowRight", count), ("ArrowUp", count),
        ("PageUp", count), ("Home", 1), ("ArrowLeft", 1), ("ArrowDown", 1), ("PageDown", 1), ("PageUp", 11),
        ("End", count), ("PageDown", count - 10),
    ]
    for key, number in steps:
        page.keyboard.press(key)
        assert_value(page, number)
    assert sum("is-active" in bar["cls"].split() for bar in bars(page)) == 1


def test_ux_dr26_tooltip_stays_300_ms_and_esc_hides_it(make_page) -> None:
    """UX-DR26, WCAG 1.4.13, 3.5 matrix "Tooltip": pointing at a bar shows its range and count; after the pointer
    leaves it is still there at 299 ms and gone at 300 ms; Esc hides it at once. The page clock is paused."""
    page = make_page(f"/wallet/{FAVOURITE}", clock=True, reduced_motion="reduce")
    tip = page.locator(".chart-tip")
    assert page.locator(".chart-bar").count() > 30, "the test points at bars 5 and 30"
    point_at_bar(page, 5)
    expect(tip).to_have_class(SHOWN)
    bar = bars(page)[5]
    assert tip.inner_text().split("\n") == [bar["range"], bar["count"]]
    page.mouse.move(0, 799)
    page.clock.run_for(299)
    expect(tip).to_have_class(SHOWN)
    page.clock.run_for(1)
    expect(tip).not_to_have_class(SHOWN)
    point_at_bar(page, 30)
    expect(tip).to_have_class(SHOWN)
    page.keyboard.press("Escape")
    expect(tip).not_to_have_class(SHOWN)  # with the clock paused, nothing but Esc can have hidden it
    assert not any("is-active" in b["cls"].split() for b in bars(page))


@pytest.mark.parametrize("width", [1280, 600, 360])
@pytest.mark.parametrize("address", CHART_WALLETS)
def test_ux_dr26_tooltip_never_covers_the_marker(make_page, address: str, width: int) -> None:
    """UX-DR26, 3.5 matrix "Tooltip": on every bar, at 1280, 600 and 360 px, the tooltip never covers the
    marker's dot or its label, and stays on the card."""
    page = make_page(f"/wallet/{address}", width, reduced_motion="reduce")
    page.locator(".chart-explore").focus()
    page.keyboard.press("Home")
    for index in range(page.locator(".chart-bar").count()):
        tip, dot, label, card = page.evaluate(
            "() => ['.chart-tip', '.chart-dot', '.chart-marker-label', '.chart-card'].map((s) => {"
            " const r = document.querySelector(s).getBoundingClientRect();"
            " return { x: r.x, y: r.y, width: r.width, height: r.height }; })"
        )
        assert not overlaps(tip, dot), f"bar {index + 1} at {width} px: the tooltip covers the marker's dot"
        assert not overlaps(tip, label), f"bar {index + 1} at {width} px: the tooltip covers the marker's label"
        assert card["x"] <= tip["x"] and tip["x"] + tip["width"] <= card["x"] + card["width"], f"bar {index + 1} off the card"
        page.keyboard.press("ArrowRight")


@pytest.mark.parametrize("address", CHART_WALLETS)
def test_ux_dr27_marker_lights_the_tail(make_page, address: str) -> None:
    """UX-DR27, 3.5 matrix "Marker": focusing or pointing at the marker lights the bars from data-tail-from on
    and shows the tail label; leaving turns them off. For stop-loss-trader no bar is lit and the label says
    "No replay …"."""
    page = make_page(f"/wallet/{address}", reduced_motion="reduce")
    button, label = page.locator(".chart-marker-button"), page.locator(".chart-tail-label")
    count = page.locator(".chart-bar").count()
    expected = list(range(tail_from(page), count))
    assert lit(page) == [] and label.is_hidden()
    button.focus()
    expect(label).to_be_visible()
    assert lit(page) == expected
    assert button.get_attribute("aria-pressed") == "false"
    page.locator(".about summary").focus()
    expect(label).to_be_hidden()
    assert lit(page) == []
    button.hover()
    expect(label).to_be_visible()
    assert lit(page) == expected
    page.mouse.move(0, 799)
    expect(label).to_be_hidden()  # 300 ms after the pointer leaves
    assert lit(page) == []
    if address == STOP_LOSS:
        assert expected == [] and label.text_content().startswith("No replay")


def test_ux_dr27_marker_pins_and_unpins(make_page) -> None:
    """UX-DR27, 3.5 matrix "Marker": Enter pins the highlight (aria-pressed, "Highlight on: …" in the live
    region); Esc, a second click or a slider step unpins it ("Highlight off")."""
    page = make_page(f"/wallet/{FAVOURITE}", reduced_motion="reduce")
    button, live, label = page.locator(".chart-marker-button"), page.locator(".chart-live"), page.locator(".chart-tail-label")
    on, off = live.get_attribute("data-highlight-on"), live.get_attribute("data-highlight-off")
    assert on.startswith("Highlight on: ") and off == "Highlight off"
    expected = list(range(tail_from(page), page.locator(".chart-bar").count()))

    button.focus()
    page.keyboard.press("Enter")
    expect(button).to_have_attribute("aria-pressed", "true")
    expect(live).to_have_text(on)
    page.locator(".about summary").focus()
    assert lit(page) == expected  # pinned: stays lit when focus leaves
    page.keyboard.press("Escape")
    expect(button).to_have_attribute("aria-pressed", "false")
    expect(live).to_have_text(off)
    assert lit(page) == [] and label.is_hidden()

    button.click()
    expect(button).to_have_attribute("aria-pressed", "true")
    expect(live).to_have_text(on)
    button.click()
    expect(button).to_have_attribute("aria-pressed", "false")
    expect(live).to_have_text(off)

    button.click()
    expect(live).to_have_text(on)
    page.locator(".chart-explore").focus()
    page.keyboard.press("ArrowLeft")
    expect(button).to_have_attribute("aria-pressed", "false")
    expect(live).to_have_text(off)
    assert lit(page) == []
    expect(page.locator(".chart-tip")).to_have_class(SHOWN)


def test_ux_dr27_tail_stays_300_ms_and_on_its_label(make_page) -> None:
    """UX-DR27, WCAG 1.4.13: after the pointer leaves the marker, the tail label and lit bars are still there at
    299 ms and gone at 300 ms; moving the pointer from the marker onto the tail label keeps them. The page clock
    is paused."""
    page = make_page(f"/wallet/{FAVOURITE}", clock=True, reduced_motion="reduce")
    button, label = page.locator(".chart-marker-button"), page.locator(".chart-tail-label")
    expected = list(range(tail_from(page), page.locator(".chart-bar").count()))
    assert expected, "the test needs a Wallet whose marker lights at least one bar"
    button.hover()
    expect(label).to_be_visible()
    page.mouse.move(0, 799)
    page.clock.run_for(299)
    expect(label).to_be_visible()
    assert lit(page) == expected
    page.clock.run_for(1)
    expect(label).to_be_hidden()
    assert lit(page) == []
    button.hover()
    expect(label).to_be_visible()
    label.hover()
    page.clock.run_for(400)
    expect(label).to_be_visible()
    assert lit(page) == expected


def test_ux_dr26_tooltip_can_be_hovered(make_page) -> None:
    """UX-DR26, WCAG 1.4.13 (hoverable): moving the pointer from a bar onto its tooltip keeps the tooltip. The page
    clock is paused."""
    page = make_page(f"/wallet/{FAVOURITE}", clock=True, reduced_motion="reduce")
    tip = page.locator(".chart-tip")
    assert page.locator(".chart-bar").count() > 5, "the test points at bar 5"
    point_at_bar(page, 5)
    expect(tip).to_have_class(SHOWN)
    tip.hover()
    page.clock.run_for(400)
    expect(tip).to_have_class(SHOWN)
    bar = bars(page)[5]
    assert tip.inner_text().split("\n") == [bar["range"], bar["count"]]


def test_ux_dr26_click_blur_and_alt_keys_on_the_slider(make_page) -> None:
    """UX-DR26, UX-DR27: a click on a bar while the highlight is pinned unpins it ("Highlight off") and shows that
    bar's tooltip; leaving the slider hides the tooltip; Alt+ArrowLeft is left to the browser (no step)."""
    page = make_page(f"/wallet/{FAVOURITE}", reduced_motion="reduce")
    button, live, tip = page.locator(".chart-marker-button"), page.locator(".chart-live"), page.locator(".chart-tip")
    assert page.locator(".chart-bar").count() > 5, "the test clicks bar 5"
    button.click()
    expect(button).to_have_attribute("aria-pressed", "true")
    point_at_bar(page, 5)
    page.mouse.down()
    page.mouse.up()
    expect(button).to_have_attribute("aria-pressed", "false")
    expect(live).to_have_text(live.get_attribute("data-highlight-off"))
    expect(tip).to_have_class(SHOWN)
    bar = bars(page)[5]
    assert tip.inner_text().split("\n") == [bar["range"], bar["count"]]
    assert lit(page) == []

    slider = page.locator(".chart-explore")
    slider.focus()
    expect(tip).to_have_class(SHOWN)
    before = slider.get_attribute("aria-valuenow")
    page.keyboard.press("Alt+ArrowLeft")
    assert slider.get_attribute("aria-valuenow") == before
    page.mouse.move(0, 799)
    page.locator(".about summary").focus()
    expect(tip).not_to_have_class(SHOWN)


# Counts the chart coming into view (data-seen) and leaving it (data-left), as chart.js's observer sees it.
OBSERVE = """() => {
  const root = document.documentElement;
  root.dataset.seen = '0';
  root.dataset.left = '0';
  let inView = false;
  new IntersectionObserver((entries) => {
    const now = entries[0].isIntersecting;
    if (now && !inView) root.dataset.seen = String(Number(root.dataset.seen) + 1);
    if (!now && inView) root.dataset.left = String(Number(root.dataset.left) + 1);
    inView = now;
  }, { threshold: 0.35 }).observe(document.querySelector('.chart-plot'));
}"""


def scroll_to_chart(page: Page, times_seen: int) -> None:
    """Scrolls the chart into view and waits until the browser has told its observers (ours is made after
    chart.js's, so chart.js has heard by then); the paused clock then holds the next animation frame."""
    page.locator(".chart-plot").scroll_into_view_if_needed()
    expect(page.locator("html")).to_have_attribute("data-seen", str(times_seen))


def test_ux_dr28_build_up_once_under_a_second(make_page) -> None:
    """UX-DR28, 3.5 matrix "Build-up": the chart waits out of view; scrolled into view, the bars grow once and
    is-building is gone within a second, with every bar's and the marker's transition done by then;
    scrolled away and back, nothing grows again."""
    page = make_page(f"/wallet/{SHARP}", 1280, 500, clock=True)
    plot = page.locator(".chart-plot")
    expect(plot).to_have_class("chart-plot pre-build")  # below the fold: not built yet
    page.evaluate(OBSERVE)
    scroll_to_chart(page, 1)
    page.clock.run_for(20)  # the next animation frame
    expect(plot).to_have_class(BUILDING)
    longest = page.evaluate(
        "() => Math.max(...['.chart-bar:last-of-type', '.chart-dot', '.chart-marker-label', '.chart-marker-line'].map((s) => {"
        " const st = getComputedStyle(document.querySelector(s));"
        " const sec = (v) => v.split(',').map((x) => parseFloat(x) * (x.trim().endsWith('ms') ? 1 : 1000));"
        " const d = sec(st.transitionDuration), w = sec(st.transitionDelay);"
        " return Math.max(...d.map((x, i) => x + w[i % w.length])); }))"
    )
    assert 500 < longest <= 1000, f"the build-up takes {longest} ms"
    page.clock.run_for(1000)
    expect(plot).to_have_class("chart-plot")
    page.evaluate("() => window.scrollTo(0, 0)")
    expect(page.locator("html")).to_have_attribute("data-left", "1")  # out of view before scrolling back
    scroll_to_chart(page, 2)
    for _ in range(3):  # once per view: no second build-up, neither at the next frame nor later
        page.clock.run_for(20)
        expect(plot).to_have_class("chart-plot")
    page.clock.run_for(1200)
    expect(plot).to_have_class("chart-plot")


def test_ux_dr28_no_build_up_with_reduced_motion(make_page) -> None:
    """UX-DR28, UX-DR11, 3.5 matrix "Build-up": with reduced motion the bars never wait or grow."""
    page = make_page(f"/wallet/{SHARP}", 1280, 500, clock=True, reduced_motion="reduce")
    plot = page.locator(".chart-plot")
    expect(plot).to_have_class("chart-plot")
    page.evaluate(OBSERVE)
    scroll_to_chart(page, 1)
    for _ in range(3):
        page.clock.run_for(400)
        expect(plot).to_have_class("chart-plot")


@pytest.mark.parametrize("how", ["javascript off", "chart.js blocked"])
def test_ad18_chart_complete_without_the_script(make_page, how: str) -> None:
    """AD-18, UX-DR28, 3.5 matrix "No JS": without chart.js the slider, the marker button and the tooltip are
    hidden and the hint written for a page without the script is shown; the chart is drawn in full."""
    if how == "javascript off":
        page = make_page(f"/wallet/{SHARP}", java_script_enabled=False)
    else:
        page = make_page(f"/wallet/{SHARP}")
        page.route("**/static/js/chart.js", lambda route: route.abort())
        page.reload()
    for selector in (".chart-explore", ".chart-marker-button", ".chart-tip", ".chart-tail-label", "#chart-explore-hint"):
        expect(page.locator(selector)).to_be_hidden()
    expect(page.locator(".chart-hint[data-no-explore]")).to_be_visible()
    expect(page.locator(".chart-alt")).to_be_visible()
    assert page.locator(".chart").get_attribute("data-enhanced") is None
    assert page.locator(".chart-plot").get_attribute("class") == "chart-plot"  # never left waiting to grow
