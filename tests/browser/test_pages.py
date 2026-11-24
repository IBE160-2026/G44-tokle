"""The pages in a real browser: copy button, breakpoints, hover, reduced motion and forced colours (Stories 3.4, 3.5).

Each test opens a fresh browser context (its own window size, theme, motion setting, platform and
clipboard rights) on the app that `conftest.py` starts on 127.0.0.1, through `make_page` (`pages.py`).
Every request the page makes to anywhere else is blocked and fails the test, so the browser never
reaches the network either (AD-17) and nothing is loaded from the internet (UX-DR3).
"""

from __future__ import annotations

import pytest
from pages import MAC_CHROME, MAC_SAFARI, NO_CLIPBOARD, REFUSE, assert_no_sideways_scroll, box, style
from playwright.sync_api import expect

from liquidoracle.data import synthetic

STOP_LOSS = synthetic.address_of("stop-loss-trader")  # has the Exit PnL warning beside the stats
SHARP = synthetic.address_of("sharp-trader")
FAVOURITE = synthetic.address_of("favourite-buyer")  # its marker sits mid-chart, with bars on both sides
THIN = synthetic.address_of("thin-wallet")  # Not enough data: the dashed Verdict, no chart
COIN_FLIPPER = synthetic.address_of(synthetic.coin_flipper_name(0))
UNKNOWN = "0x" + "0" * 40  # not in the Sample Dataset: the "Not available offline" message page
PAGES = [
    "/", f"/?address=0x{'z' * 120}",  # the Lookup page, and with a long invalid address echoed back
    f"/wallet/{STOP_LOSS}", f"/wallet/{SHARP}", f"/wallet/{THIN}", f"/wallet/{COIN_FLIPPER}",
    f"/wallet/{UNKNOWN}", "/no-such-page",
]
WIDTHS = [320, 360, 600, 900]
LIFTED = "matrix(1, 0, 0, 1, 0, -1)"
CTRL_C = "Copy failed. Select the address and press Ctrl+C."
CMD_C = "Copy failed. Select the address and press ⌘C."


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("path", PAGES)
def test_ux_dr10_no_sideways_scroll(make_page, path: str, width: int) -> None:
    """UX-DR10, 3.4 matrix: no page scrolls sideways at 320, 360, 600 or 900 px, and the odds line wraps as
    plain text: its column is never squeezed and it never falls to one word per line (the old bug)."""
    page = make_page(path, width)
    assert_no_sideways_scroll(page, f"{path} at {width} px")
    if page.locator(".odds").count():
        hero = box(page, ".verdict-head > div:first-child")
        assert hero["width"] >= min(300, 0.9 * box(page, ".verdict-card")["width"])
        lines, words = page.locator(".odds").evaluate(
            "(el) => [Math.round(el.getBoundingClientRect().height / parseFloat(getComputedStyle(el).lineHeight)),"
            " el.textContent.trim().split(/\\s+/).length]"
        )
        assert 2 * lines <= words + 1, f"{lines} lines for {words} words at {width} px"


@pytest.mark.parametrize("width", [320, 900])
@pytest.mark.parametrize("path", ["/", f"/wallet/{STOP_LOSS}"])
def test_ux_dr10_no_sideways_scroll_in_the_light_theme(make_page, path: str, width: int) -> None:
    """UX-DR10, UX-DR2: the light theme lays out the same, with no sideways scroll."""
    page = make_page(path, width, theme="light")
    assert page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "light"
    assert_no_sideways_scroll(page, f"{path} at {width} px, light")


@pytest.mark.parametrize("width", [900, 1280])
def test_ux_dr10_two_columns_from_900(make_page, width: int) -> None:
    """UX-DR10, 3.4 matrix "900 px and wider": the address card beside the hero, the warning beside the stats,
    the honesty notes in three columns."""
    page = make_page(f"/wallet/{STOP_LOSS}", width)
    assert box(page, ".address-card")["x"] > box(page, ".verdict")["x"] + 100
    assert box(page, ".stats-row .warning")["x"] > box(page, ".stats")["x"] + 100
    assert box(page, ".stats")["width"] >= 280  # the stats line never folds word by word beside the warning
    columns = page.locator(".limits-grid > div")
    assert columns.count() == 3 and len({round(columns.nth(i).bounding_box()["y"]) for i in range(3)}) == 1


@pytest.mark.parametrize("width", [899, 640])
def test_ux_dr10_stacked_below_900(make_page, width: int) -> None:
    """UX-DR10, 3.4 matrix "640-899 px": the address card under the hero, the warning under the stats, the
    honesty notes in one column."""
    page = make_page(f"/wallet/{STOP_LOSS}", width)
    hero = box(page, ".verdict-head > div:first-child")
    assert box(page, ".address-card")["y"] >= hero["y"] + hero["height"]
    stats = box(page, ".stats")
    assert box(page, ".stats-row .warning")["y"] >= stats["y"] + stats["height"]
    first, second = (page.locator(".limits-grid > div").nth(i).bounding_box() for i in range(2))
    assert second["y"] >= first["y"] + first["height"]
    assert style(page, ".verdict", "font-size") == "56px"  # phone sizes start below 640


@pytest.mark.parametrize("width", [639, 400])
def test_ux_dr10_phone_sizes(make_page, width: int) -> None:
    """UX-DR10, 3.4 matrix "400-639 px": Verdict 40 px, odds 21 px, page title 36 px, ledes 21 px, 16 px side
    margins, the "Check wallet" button under the field, the top bar's tools on their own row."""
    page = make_page(f"/wallet/{SHARP}", width)
    assert style(page, ".verdict", "font-size") == "40px"
    assert style(page, ".odds", "font-size") == "21px"
    assert style(page, "main .wrap", "padding-left") == "16px"
    lookup = make_page("/", width)
    assert style(lookup, "h1", "font-size") == "36px" and style(lookup, ".lede", "font-size") == "21px"
    field = box(lookup, ".text-input")
    assert field["height"] == 48  # stacked, the field keeps its height (its width basis once became its height)
    assert box(lookup, ".btn-primary")["y"] >= field["y"] + field["height"]
    brand = box(lookup, ".brand")
    assert box(lookup, ".bar-tools")["y"] >= brand["y"] + brand["height"]


@pytest.mark.parametrize("path", [f"/wallet/{SHARP}", f"/wallet/{THIN}"])
def test_ux_dr10_smallest_verdict(make_page, path: str) -> None:
    """UX-DR10, 3.4 matrix "Below 400 px": the Verdict at 34 px, also the dashed Not enough data one."""
    assert style(make_page(path, 399), ".verdict", "font-size") == "34px"


def test_ux_dr21_copy_works(make_page) -> None:
    """UX-DR21, 3.4 matrix "Copy works": the full address on the clipboard, "Copied" on the accent tint for
    2 seconds (and in the button's name, WCAG 2.5.3), "Address copied" announced; a second click within the
    2 seconds starts them again. The page clock is paused, so only run_for moves time."""
    page = make_page(f"/wallet/{SHARP}", clock=True, permissions=["clipboard-read", "clipboard-write"])
    button, label, status = page.locator(".copy-button"), page.locator(".copy-label"), page.locator(".copy-status")
    expect(page.get_by_role("button", name="Copy wallet address", exact=True)).to_be_visible()
    button.click()
    # expect() retries from Playwright's side; wait_for_function would poll with the page's paused timers.
    expect(label).to_have_text("Copied")
    page.clock.run_for(100)  # the status line announces 50 ms after the copy lands
    assert page.evaluate("() => navigator.clipboard.readText()") == SHARP
    assert "is-copied" in button.get_attribute("class")
    expect(page.get_by_role("button", name="Copy wallet address Copied")).to_be_visible()
    assert status.text_content() == "Address copied" and status.get_attribute("role") == "status"
    assert page.locator(".copy-error").is_hidden()
    page.clock.run_for(1300)
    button.click()
    expect(status).to_have_text("")  # the second copy landed: the status line is emptied before it speaks again
    page.clock.run_for(1500)  # 2.9 s after the first copy, 1.5 s after the second
    assert label.text_content() == "Copied"
    page.clock.run_for(600)
    assert label.text_content() == "" and "is-copied" not in button.get_attribute("class")


@pytest.mark.parametrize("script", [REFUSE, NO_CLIPBOARD])
def test_ux_dr21_copy_refused(make_page, script: str) -> None:
    """UX-DR21, 3.4 matrix "Copy refused": the error under the address, announced, with the address selected,
    whether the browser rejects the copy or has no clipboard at all (Windows wording, Ctrl+C)."""
    page = make_page(f"/wallet/{SHARP}", scripts=[script])
    page.locator(".copy-button").click()
    error = page.locator(".copy-error")
    error.wait_for(state="visible")
    assert error.text_content() == "Error: " + CTRL_C
    expect(page.locator(".copy-status")).to_have_text(CTRL_C)
    assert page.evaluate("() => window.getSelection().toString()") == SHARP
    assert page.locator(".copy-label").text_content() == ""


@pytest.mark.parametrize("platform", [MAC_CHROME, MAC_SAFARI])
def test_ux_dr21_copy_refused_on_a_mac(make_page, platform: str) -> None:
    """UX-DR21, 3.4 matrix "Copy refused": on a Mac the error names ⌘C, read from Chrome's userAgentData or,
    in Safari and Firefox, from navigator.platform."""
    page = make_page(f"/wallet/{SHARP}", platform=platform, scripts=[REFUSE])
    page.locator(".copy-button").click()
    page.locator(".copy-error").wait_for(state="visible")
    assert page.locator(".copy-error-text").text_content() == CMD_C
    expect(page.locator(".copy-status")).to_have_text(CMD_C)


def test_ux_dr21_a_later_copy_hides_the_error(make_page) -> None:
    """UX-DR21, 3.4 matrix "Copy refused": a later successful copy hides the error."""
    page = make_page(f"/wallet/{SHARP}", scripts=[REFUSE], permissions=["clipboard-read", "clipboard-write"])
    page.locator(".copy-button").click()
    page.locator(".copy-error").wait_for(state="visible")
    page.evaluate("() => Object.defineProperty(navigator, 'clipboard', { value: { writeText: () => Promise.resolve() } })")
    page.locator(".copy-button").click()
    page.locator(".copy-error").wait_for(state="hidden")
    expect(page.locator(".copy-label")).to_have_text("Copied")


def test_ux_dr21_a_refusal_right_after_a_copy_clears_copied(make_page) -> None:
    """UX-DR21 (Story 3.4 review): a refusal within 2 seconds of a copy never leaves "Copied" beside the error."""
    page = make_page(f"/wallet/{SHARP}", permissions=["clipboard-read", "clipboard-write"])
    page.locator(".copy-button").click()
    expect(page.locator(".copy-label")).to_have_text("Copied")
    page.evaluate(f"() => {{ {REFUSE} }}")
    page.locator(".copy-button").click()
    page.locator(".copy-error").wait_for(state="visible")
    assert page.locator(".copy-label").text_content() == ""
    assert "is-copied" not in page.locator(".copy-button").get_attribute("class")
    expect(page.locator(".copy-status")).to_have_text(CTRL_C)


def test_ad18_no_copy_button_without_javascript(make_page) -> None:
    """AD-18, UX-DR21, 3.4 matrix "No JavaScript": the address is shown and there is no copy button."""
    page = make_page(f"/wallet/{SHARP}", java_script_enabled=False)
    assert page.locator(".address").inner_text() == SHARP
    assert page.locator(".copy-button").is_hidden()


BUTTONS = [(f"/wallet/{SHARP}", ".copy-button"), ("/", ".theme-toggle"), ("/", ".btn-primary")]


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize(("path", "selector"), BUTTONS)
def test_ux_dr9_buttons_lift_on_hover_and_focus(make_page, path: str, selector: str, theme: str) -> None:
    """UX-DR9: buttons lift 1 px under the pointer and under keyboard focus alike, in 120 ms, in both themes.
    expect() waits for the transition to finish instead of a fixed pause, so a slow machine does not fail it."""
    page = make_page(path, theme=theme)
    button = page.locator(selector)
    assert style(page, selector, "transition-duration").split(", ")[0] == "0.12s"
    button.hover()
    expect(button).to_have_css("transform", LIFTED)
    page.mouse.move(0, 799)
    expect(button).to_have_css("transform", "none")  # back down once the pointer leaves
    button.focus()
    page.keyboard.press("Shift")  # a key press makes the focus keyboard focus, so :focus-visible applies
    expect(button).to_have_css("transform", LIFTED)


@pytest.mark.parametrize(("path", "selector"), BUTTONS)
def test_ux_dr11_nothing_moves_with_reduced_motion(make_page, path: str, selector: str) -> None:
    """UX-DR11, 3.4 matrix "Reduced motion": no lift and no transitions; the colours still change."""
    page = make_page(path, reduced_motion="reduce")
    assert style(page, selector, "transition-duration").split(", ")[0] == "0s"
    before = style(page, selector, "background-color")
    page.hover(selector)
    assert style(page, selector, "transform") == "none"
    assert style(page, selector, "background-color") != before
    page.mouse.move(0, 799)
    page.locator(selector).focus()
    page.keyboard.press("Shift")
    assert style(page, selector, "transform") == "none"


LOOKS = ("color", "background-color", "border-color", "box-shadow", "transform", "text-decoration-line", "cursor")


@pytest.mark.parametrize(("path", "selectors"), [
    (f"/wallet/{STOP_LOSS}", (".verdict-card", ".stats", ".chart-alt", ".limits-grid > div", ".left-out", ".computed-on")),
    ("/", (".card", ".lede", ".hint")),
])
def test_ux_dr9_cards_and_text_do_not_react(make_page, path: str, selectors: tuple[str, ...]) -> None:
    """UX-DR9: only clickable things react; a card, a figure or text under the pointer keeps its whole look."""
    page = make_page(path)
    for selector in selectors:
        before = [style(page, selector, prop) for prop in LOOKS]
        page.hover(selector, position={"x": 12, "y": 12})  # near a corner, inside the rounding, away from links
        page.wait_for_timeout(200)
        assert [style(page, selector, prop) for prop in LOOKS] == before, selector


SYSTEM_COLOUR = """(name) => {
  const probe = document.createElement('span');
  probe.style.color = name;
  document.body.append(probe);
  const value = getComputedStyle(probe).color;
  probe.remove();
  return value;
}"""


def test_ux_dr9_forced_colours_copied_state(make_page) -> None:
    """UX-DR9, UX-DR21, 3.5 matrix "Forced colours": in Windows High Contrast the copied state shows as a
    Highlight border (the accent tint is dropped), and the border goes back when "Copied" ends."""
    page = make_page(f"/wallet/{SHARP}", forced_colors="active", reduced_motion="reduce", clock=True,
                     permissions=["clipboard-read", "clipboard-write"])
    highlight = page.evaluate(SYSTEM_COLOUR, "Highlight")
    button = page.locator(".copy-button")
    expect(button).not_to_have_css("border-top-color", highlight)
    button.click()
    page.mouse.move(0, 799)
    button.blur()  # neither hovered nor focused (Chrome draws a Highlight border on both): only "Copied" can draw it
    expect(page.locator(".copy-label")).to_have_text("Copied")
    expect(button).to_have_css("border-top-color", highlight)
    page.clock.run_for(2100)
    expect(page.locator(".copy-label")).to_have_text("")
    expect(button).not_to_have_css("border-top-color", highlight)


# Whether one of the app's own forced-colours rules gives the element, in its present state, a Highlight border.
OWN_HIGHLIGHT_RULE = """(el) => [...document.styleSheets].flatMap((sheet) => [...sheet.cssRules])
  .filter((rule) => rule.media && rule.media.mediaText.includes('forced-colors: active'))
  .flatMap((media) => [...media.cssRules])
  .some((rule) => rule.style && /highlight/i.test(rule.style.getPropertyValue('border-color')) && el.matches(rule.selectorText))"""


@pytest.mark.parametrize(("path", "selector"), BUTTONS)
def test_ux_dr9_forced_colours_hover_and_focus(make_page, path: str, selector: str) -> None:
    """UX-DR9, 3.5 matrix "Forced colours": the copy, theme and primary buttons show a Highlight border under the
    pointer and under keyboard focus, and none at rest. Chrome and Edge also draw that border on a hovered or
    focused button by themselves, so the test also checks that the app's own rule applies (other browsers)."""
    page = make_page(path, forced_colors="active", reduced_motion="reduce")
    highlight = page.evaluate(SYSTEM_COLOUR, "Highlight")
    button = page.locator(selector)
    expect(button).not_to_have_css("border-top-color", highlight)
    assert not button.evaluate(OWN_HIGHLIGHT_RULE)
    button.hover()
    expect(button).to_have_css("border-top-color", highlight)
    assert button.evaluate(OWN_HIGHLIGHT_RULE), "no rule of the app's own gives the hovered button its border"
    page.mouse.move(0, 799)
    expect(button).not_to_have_css("border-top-color", highlight)
    button.focus()
    page.keyboard.press("Shift")  # keyboard focus, so :focus-visible applies
    expect(button).to_have_css("border-top-color", highlight)
    assert button.evaluate(OWN_HIGHLIGHT_RULE), "no rule of the app's own gives the focused button its border"


def bar_fills(page) -> list[str]:
    return page.locator(".chart-bar").evaluate_all("(all) => all.map((b) => getComputedStyle(b).fill)")


def test_ux_dr25_forced_colours_tail_and_active_bars(make_page) -> None:
    """UX-DR25, UX-DR27, 3.5 matrix "Forced colours": bars are CanvasText; the tail bars the marker lights and
    the bar the slider is on are Highlight."""
    page = make_page(f"/wallet/{FAVOURITE}", forced_colors="active", reduced_motion="reduce")
    highlight, ink = (page.evaluate(SYSTEM_COLOUR, name) for name in ("Highlight", "CanvasText"))
    assert highlight != ink
    tail_from = int(page.locator(".chart").get_attribute("data-tail-from"))
    count = page.locator(".chart-bar").count()
    assert 0 < tail_from < count, f"the test needs bars on both sides of the tail (tail from bar {tail_from} of {count})"
    assert bar_fills(page) == [ink] * count
    page.locator(".chart-marker-button").focus()
    expect(page.locator(".chart-bar").nth(count - 1)).to_have_css("fill", highlight)
    assert bar_fills(page) == [ink] * tail_from + [highlight] * (count - tail_from)
    page.locator(".chart-explore").focus()
    page.keyboard.press("Home")
    expect(page.locator(".chart-bar").first).to_have_css("fill", highlight)
    assert bar_fills(page) == [highlight] + [ink] * (count - 1)
