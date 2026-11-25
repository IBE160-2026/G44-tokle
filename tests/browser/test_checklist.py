"""The accessibility checklist, walked by keyboard in a real browser (Story 3.5 part B; epics.md Story 3.5).

One test per checklist item (1 to 12), plus the Real Wallets links and every page with JavaScript off.
The tests act with the keyboard only (`page.keyboard`, never a click) and read what the browser hands a
screen reader: each element's role, name, description and state, the reading order (Playwright's
accessibility snapshot, `aria_snapshot()`), and the text of the live regions. They replace Edvard's own
NVDA walk-through (his call of 2026-11-24). What they cannot prove, such as the words NVDA itself speaks
and its browse mode, is listed in docs/accessibility-check.md, with what each test found.

What part A or the Python tests already prove is cited, not tested again: the slider's full key set
(test_chart_script.py), the copy button's timing and failures (test_pages.py), the markup checks of every
page (tests/test_web.py).
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest
from pages import assert_no_sideways_scroll
from playwright.sync_api import Locator, Page, expect

from liquidoracle.data import synthetic
from liquidoracle.data.errors import PolymarketUnavailable
from liquidoracle.data.offline import REAL_DIR

REPO = Path(__file__).resolve().parents[2]

SHARP = synthetic.address_of("sharp-trader")
STOP_LOSS = synthetic.address_of("stop-loss-trader")  # has the Exit PnL warning
FAVOURITE = synthetic.address_of("favourite-buyer")  # marker mid-chart, with replays on both sides
THIN = synthetic.address_of("thin-wallet")  # Not enough data
UNKNOWN = "0x" + "0" * 40  # not in the Sample Dataset
JOB_LIMIT = 30.0  # seconds a live lookup on the stand-in Polymarket may take at most

# Every focusable control that is shown: what a keyboard walk must reach.
CONTROLS = """() => [...document.querySelectorAll('a[href], button, input, select, textarea, summary, [tabindex]')]
  .filter((el) => el.tabIndex >= 0 && !el.disabled && el.getClientRects().length > 0
                  && getComputedStyle(el).visibility !== 'hidden')"""
MARK_CONTROLS = f"() => ({CONTROLS})().forEach((el, i) => el.setAttribute('data-walk', i))"
ACTIVE = "() => { const el = document.activeElement; return el && el.dataset.walk !== undefined ? Number(el.dataset.walk) : -1; }"
RING = """() => { const el = document.activeElement, s = getComputedStyle(el), r = el.getBoundingClientRect();
  return { style: s.outlineStyle, width: parseFloat(s.outlineWidth), shown: r.width > 0 && r.height > 0,
           name: el.outerHTML.slice(0, 80) }; }"""


def tab_to(page: Page, target: Locator, *, key: str = "Tab", limit: int = 60) -> int:
    """Presses `key` until `target` has the focus; returns how many presses it took."""
    target.wait_for(state="attached")
    for presses in range(limit + 1):
        if target.evaluate("(el) => el === document.activeElement"):
            return presses
        page.keyboard.press(key)
    raise AssertionError(f"{limit} presses of {key} never reached {target}")


def assert_ring(page: Page) -> None:
    """The focused element is on screen with the 2 px focus ring (UX-DR9)."""
    ring = page.evaluate(RING)
    assert ring["shown"], f"the focused element is not on screen: {ring['name']}"
    assert ring["style"] != "none" and ring["width"] >= 2, f"no visible focus ring: {ring}"


def lines(locator: Locator) -> list[str]:
    """The accessibility snapshot, one node per line: what a screen reader reads, in reading order."""
    return [line.strip() for line in locator.aria_snapshot().splitlines()]


def first_line(snapshot: list[str], words: str) -> int:
    found = [i for i, line in enumerate(snapshot) if words in line]
    assert found, f"{words!r} is not in what a screen reader is given:\n" + "\n".join(snapshot)
    return found[0]


# --- 1 to 4: skip link, the Lookup field, the Verdict heading, plain text ------------------------


def test_checklist_1_skip_link_is_the_first_tab_stop(make_page) -> None:
    """Checklist 1, UX-DR8 (WCAG 2.4.1): on the Verdict page the first Tab lands on the link "Skip to content", with
    its focus ring, and Enter moves the focus into `main`. On the Lookup page the focus already starts in the address
    field inside `main` (autofocus, UX-DR16), so the first Tab goes on to "Check wallet"; the skip link is still the
    first stop of the page's tab order, reached by Shift+Tab (finding 1 in docs/accessibility-check.md)."""
    page = make_page(f"/wallet/{SHARP}")
    page.keyboard.press("Tab")
    skip = page.get_by_role("link", name="Skip to content")
    expect(skip).to_be_focused()
    assert_ring(page)
    page.keyboard.press("Enter")
    expect(page.get_by_role("main")).to_be_focused()

    lookup = make_page("/")
    field = lookup.get_by_role("textbox", name="Wallet address")
    expect(field).to_be_focused()
    assert field.evaluate("(el) => el.closest('main') !== null")
    lookup.keyboard.press("Tab")
    expect(lookup.get_by_role("button", name="Check wallet")).to_be_focused()
    tab_to(lookup, lookup.get_by_role("link", name="Skip to content"), key="Shift+Tab", limit=6)
    lookup.evaluate(MARK_CONTROLS)
    assert lookup.evaluate(ACTIVE) == 0  # the first control of the page
    lookup.keyboard.press("Enter")
    expect(lookup.get_by_role("main")).to_be_focused()


def test_checklist_2_empty_submit_is_read_as_an_error_on_the_field(make_page) -> None:
    """Checklist 2, UX-DR13, FR-1: the field is read as "Wallet address"; Enter on the empty field submits the form,
    and on the page that comes back the focus is in the field, which is marked invalid and described by
    "Error: Enter a wallet address." (the ✕ icon is silent)."""
    page = make_page("/")
    field = page.get_by_role("textbox", name="Wallet address")
    expect(field).to_be_focused()
    expect(field).to_have_accessible_description("A Wallet address starts with 0x and has 42 characters.")
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"/\?address=$"))
    field = page.get_by_role("textbox", name="Wallet address")
    expect(field).to_be_focused()
    expect(field).to_have_attribute("aria-invalid", "true")
    expect(field).to_have_accessible_description(
        "Error: Enter a wallet address. A Wallet address starts with 0x and has 42 characters.")
    assert lines(field)[0] == '- textbox "Wallet address" [invalid]:'


def test_checklist_3_verdict_heading_is_read_as_verdict(make_page) -> None:
    """Checklist 3, UX-DR20, UX-DR12: the page's one level-1 heading is read as "Verdict: Skilled (high confidence)";
    the dots give a screen reader nothing (the heading has no other content). Jumping by heading (NVDA's H) is
    browse mode, which no test can press; the heading is what it jumps to."""
    page = make_page(f"/wallet/{SHARP}")
    heading = page.get_by_role("heading", level=1)
    expect(heading).to_have_count(1)
    expect(heading).to_have_accessible_name("Verdict: Skilled (high confidence)")
    assert lines(heading) == ['- \'heading "Verdict: Skilled (high confidence)" [level=1]\'']
    assert page.locator(".dots").count() == 1  # the dots are drawn, just not read


def test_checklist_4_odds_stats_and_chart_text_are_plain_text_in_order(make_page) -> None:
    """Checklist 4, UX-DR12, UX-DR24, FR-8, FR-9: after the heading, a screen reader reads the odds phrase, then the
    stats, then (after the chart's title) the chart's text alternative, each as a plain paragraph; the drawing
    itself is not read (bars, axis and marker label are hidden)."""
    page = make_page(f"/wallet/{SHARP}")
    odds = page.locator(".odds").text_content().strip()
    alt = page.locator(".chart-alt").text_content().strip()
    read = lines(page.get_by_role("main"))
    order = [
        first_line(read, '[level=1]'),
        read.index(f"- paragraph: {odds}"),
        read.index("- paragraph: Stats"),
        first_line(read, "Real PnL"),
        first_line(read, 'heading "Simulated results'),
        read.index(f"- paragraph: {alt}"),
    ]
    assert order == sorted(order), order
    assert read[order[3] - 2] == "- paragraph:"  # the stats line is one paragraph with its two figures
    drawing = ("Number of replays", " or more", " or less")  # the y-axis title and the end bars' labels
    assert not any(words in line for line in read for words in drawing), "part of the drawing is read"
    assert [line for line in read if "This Wallet: $" in line] == [line for line in read if line.startswith("- 'button")]


# --- 5 to 7: the slider, the marker, the copy button ----------------------------------------------


def test_checklist_5_slider_is_read_with_its_value(make_page) -> None:
    """Checklist 5, UX-DR26: Tab reaches the slider "Replays by result", described by its hint and showing a focus
    ring; an arrow key changes the value a screen reader reads (aria-valuetext, the bar's range and count). Every
    key (arrows, Page Up/Down, Home/End, the ends) is proven in test_chart_script.py::test_ux_dr26_slider_keys."""
    page = make_page(f"/wallet/{SHARP}", reduced_motion="reduce")
    slider = page.get_by_role("slider", name="Replays by result")
    tab_to(page, slider)
    assert_ring(page)
    expect(slider).to_have_accessible_description(page.locator("#chart-explore-hint").text_content())
    before = slider.get_attribute("aria-valuetext")
    page.keyboard.press("ArrowLeft")
    expect(slider).not_to_have_attribute("aria-valuetext", before)
    bar = int(slider.get_attribute("aria-valuenow")) - 1
    words = page.locator(".chart-bar").nth(bar).evaluate("(b) => b.dataset.range + ': ' + b.dataset.count")
    expect(slider).to_have_attribute("aria-valuetext", words)
    page.keyboard.press("End")
    expect(slider).to_have_attribute("aria-valuenow", slider.get_attribute("aria-valuemax"))


def test_checklist_6_marker_is_read_and_announces_highlight_on_and_off(make_page) -> None:
    """Checklist 6, UX-DR27: Tab reaches the marker button, read with its name and its sentence (the tail count, as
    its description); Enter puts "Highlight on: …" in the polite live region and Esc puts "Highlight off"."""
    page = make_page(f"/wallet/{FAVOURITE}", reduced_motion="reduce")
    marker = page.locator(".chart-marker-button")
    tab_to(page, marker)
    assert_ring(page)
    expect(marker).to_have_accessible_name(re.compile(r"^This Wallet: .+\. Highlight the replays that did this well or better$"))
    expect(marker).to_have_accessible_description(page.locator("#chart-tail-text").text_content())
    live = page.locator(".chart-live")
    assert live.get_attribute("aria-live") == "polite"
    page.keyboard.press("Enter")
    expect(live).to_have_text(re.compile(r"^Highlight on: "))
    expect(page.get_by_role("button", name=re.compile("^This Wallet: "), pressed=True)).to_be_focused()
    page.keyboard.press("Escape")
    expect(live).to_have_text("Highlight off")
    expect(marker).to_have_attribute("aria-pressed", "false")


def test_checklist_7_copy_is_announced(make_page) -> None:
    """Checklist 7, UX-DR21: Tab reaches "Copy wallet address"; Enter copies, and the status region (role status,
    read without moving the focus) says "Address copied". The timing and the failures are proven in
    test_pages.py::test_ux_dr21_copy_works and test_ux_dr21_copy_refused."""
    page = make_page(f"/wallet/{SHARP}", permissions=["clipboard-read", "clipboard-write"])
    copy = page.get_by_role("button", name="Copy wallet address")
    tab_to(page, copy)
    assert_ring(page)
    page.keyboard.press("Enter")
    expect(page.get_by_role("status")).to_have_text("Address copied")
    expect(copy).to_be_focused()
    assert page.evaluate("() => navigator.clipboard.readText()") == SHARP


# --- 8 to 10: the warning, the honesty notes, the theme toggle ------------------------------------


def test_checklist_8_exit_warning_is_read_with_warning_first(make_page) -> None:
    """Checklist 8, FR-11, UX-DR15: on the stop-loss Synthetic Wallet the note beside the stats is read starting with
    "Warning:", then its two sentences; the icon is silent."""
    page = make_page(f"/wallet/{STOP_LOSS}")
    note = page.get_by_role("region", name=re.compile("^Verdict: ")).get_by_role("note")
    expect(note).to_have_count(1)
    read = lines(note)
    spoken = [line for line in read if line not in ("- note:", "- paragraph:")]
    assert spoken[0] == '- text: "Warning:"', read
    assert "Positions this Wallet sold before resolution lost money in total." in spoken[1]
    assert not any("img" in line for line in read)


HONESTY_ORDER = (
    "of the Real PnL came from the single largest bet.", "positions held to resolution.",
    "Shares sold before resolution:", "Long shots tend to be overpriced", "This is not financial advice.",
    "Left out of the test:", "Every fee matched", "Only part of this Wallet", "Computed on all 100 bets · Seed 44",
)


def test_checklist_9_honesty_notes_are_reachable_by_heading_and_read_in_order(make_page) -> None:
    """Checklist 9, FR-11, UX-DR29: "What this test can't see" is a level-2 heading naming its region, and the
    region is read in the order it is shown, with nothing in it hidden or collapsed."""
    page = make_page(f"/wallet/{STOP_LOSS}")
    expect(page.get_by_role("heading", name="What this test can't see", level=2)).to_have_count(1)
    region = page.get_by_role("region", name="What this test can't see")
    read = "\n".join(lines(region))
    shown = re.sub(r"\s+", " ", region.inner_text())
    assert [read.index(words) for words in HONESTY_ORDER] == sorted(read.index(words) for words in HONESTY_ORDER)
    assert [shown.index(words) for words in HONESTY_ORDER] == sorted(shown.index(words) for words in HONESTY_ORDER)


@pytest.mark.parametrize("path", ["/", f"/wallet/{SHARP}"])
def test_checklist_10_theme_toggle_is_a_pressed_button(make_page, path: str) -> None:
    """Checklist 10, UX-DR2: the toggle is read as the button "Dark theme", pressed; Enter and Space each flip its
    pressed state (and the theme), with the focus staying on it."""
    page = make_page(path)
    toggle = page.get_by_role("button", name="Dark theme")
    tab_to(page, toggle, key="Shift+Tab" if path == "/" else "Tab")
    assert_ring(page)
    assert lines(toggle) == ['- button "Dark theme" [pressed]']
    page.keyboard.press("Enter")
    expect(toggle).to_have_attribute("aria-pressed", "false")
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    assert lines(toggle) == ['- button "Dark theme"']
    page.keyboard.press("Space")
    expect(page.get_by_role("button", name="Dark theme", pressed=True)).to_be_focused()
    expect(page.locator("html")).not_to_have_attribute("data-theme", "light")


# --- 11 and 12: the whole keyboard walk, zoom and narrow windows ----------------------------------


FOCUSED = "() => document.activeElement ? document.activeElement.outerHTML.slice(0, 120) : 'nothing'"


def walk(page: Page, key: str, start: int, count: int) -> list[int]:
    """Presses `key` count + 3 times from stop `start` (-1: before the first control) and returns the stops.

    Each press must go to the next control in page order, with its focus ring. The only stops off the controls
    (-1: the focus left the page) are one run at the wrap point: right after the last control (the first, for
    Shift+Tab), and then the walk comes back to the first (the last). A walk that starts before the first control
    goes straight to it. Chrome leaves the page once after the last control on Tab, but goes from the first control
    straight to the last on Shift+Tab, so Shift+Tab may skip the run. Any other stop fails, naming the element that
    has the focus."""
    step, last, first = (1, count - 1, 0) if key == "Tab" else (-1, 0, count - 1)
    stops, prev, runs = [], start, 0
    for _ in range(count + 3):
        page.keyboard.press(key)
        stop = page.evaluate(ACTIVE)
        if prev == last:
            allowed = {-1} if key == "Tab" else {-1, first}  # the wrap point
        elif prev == -1:
            allowed = {first} if not stops else {first, -1}
        else:
            allowed = {prev + step}
        assert stop in allowed, f"{key} from stop {prev} went to stop {stop}, expected {sorted(allowed)}: {page.evaluate(FOCUSED)}"
        if stop >= 0:
            assert_ring(page)
        elif prev != -1:
            runs += 1
        stops.append(stop)
        prev = stop
    assert runs == 1 if key == "Tab" else runs <= 1, f"{key} left the page {runs} times in {stops}"
    return stops


@pytest.mark.parametrize("path", ["/", f"/wallet/{SHARP}", f"/wallet/{STOP_LOSS}"])
def test_checklist_11_tab_walks_every_control_with_a_ring_and_no_trap(make_page, path: str) -> None:
    """Checklist 11, UX-DR9, WCAG 2.1.1, 2.1.2, 2.4.3, 2.4.7: Tab visits every shown control in page order, each with
    its visible focus ring, leaves the page once after the last and comes back to the first; Shift+Tab, from the
    control the Tab walk ended on, walks the same stops backwards (in Chrome it goes from the first control straight
to the last). Nothing holds the focus. That each control works
    by keyboard is checked by items 1, 2, 5 to 7, 10."""
    page = make_page(path, reduced_motion="reduce")
    page.evaluate(MARK_CONTROLS)
    count = page.evaluate(f"() => ({CONTROLS})().length")
    start = page.evaluate(ACTIVE)  # the Lookup page starts in the field; the others start before the first control
    forward = walk(page, "Tab", start, count)
    assert {stop for stop in forward if stop >= 0} == set(range(count))
    assert forward[-1] >= 0, "the Tab walk must end on a control"
    backward = walk(page, "Shift+Tab", forward[-1], count)
    assert {stop for stop in backward if stop >= 0} == set(range(count))


def fetching_page(make_page, live_app, address: str, width: int, **options) -> Page:
    """The live app's fetching page for `address`, held there by the stand-in Polymarket."""
    live_app.polymarket.hold()
    page = make_page(f"/wallet/{address}", width, base=live_app.url, **options)
    expect(page.get_by_role("heading", level=1)).to_have_text(f"Checking {address[:6]}…{address[-4:]}")
    return page


@pytest.mark.parametrize("path", ["/", f"/wallet/{SHARP}", f"/wallet/{STOP_LOSS}"])
def test_checklist_12_no_sideways_scroll_at_200_percent_zoom(make_page, path: str) -> None:
    """Checklist 12, UX-DR10, WCAG 1.4.10: at 200% zoom of a 1280 px window (640 CSS px at device scale 2) the
    Lookup and Verdict pages do not scroll sideways. 320 px is proven for them in
    test_pages.py::test_ux_dr10_no_sideways_scroll."""
    page = make_page(path, 640, 800, device_scale_factor=2)
    assert page.evaluate("() => window.innerWidth") == 640
    assert_no_sideways_scroll(page, f"{path} at 200% zoom")


@pytest.mark.parametrize(("width", "scale"), [(640, 2), (320, 1)])
def test_checklist_12_fetching_page_has_no_sideways_scroll(make_page, live_app, width: int, scale: int) -> None:
    """Checklist 12, UX-DR10, UX-DR22: the fetching page, with its long address, does not scroll sideways at 200%
    zoom or in a 320 px window."""
    page = fetching_page(make_page, live_app, SHARP, width, device_scale_factor=scale)
    assert_no_sideways_scroll(page, f"the fetching page at {width} px, scale {scale}")


# --- Real Wallets links ---------------------------------------------------------------------------


def test_real_wallets_links_have_unique_names_in_their_list(make_page, real_wallets_url: str) -> None:
    """UX-DR17, WCAG 2.4.4, 2.5.3 (AI's call in the spec, approved with it by Edvard, 2026-11-25): every committed real
    Wallet has a link inside the list named "Real Wallets", read by the short address it shows ("0x7298…fcfc"; the
    chevron is decorative and hidden), and no two links share a name."""
    page = make_page("/", base=real_wallets_url)
    group = page.get_by_role("list", name="Real Wallets")
    names = re.findall(r'link "([^"]+)"', group.aria_snapshot())
    links = group.get_by_role("link")
    assert len(names) == links.count() == len(list((REPO / REAL_DIR).glob("0x*.json")))
    for link in links.all():
        expect(link).to_have_accessible_name(link.locator(".name").inner_text())
    assert all(re.fullmatch(r"0x[0-9a-f]{4}…[0-9a-f]{4}", name) for name in names), names
    assert len(set(names)) == len(names), f"two links share a name: {names}"


# --- every page with JavaScript off (AD-18, NFR-9) -------------------------------------------------


def assert_complete(page: Page, h1: str | re.Pattern[str]) -> None:
    """A page without JavaScript: one shown h1, content in `main`, and nothing shown that needs a script (the only
    shown button is a form's submit button)."""
    heading = page.get_by_role("heading", level=1)
    expect(heading).to_have_count(1)
    expect(heading).to_be_visible()
    expect(heading).to_have_text(h1)
    assert len(page.get_by_role("main").inner_text().strip()) > len(heading.inner_text()) + 20
    for button in page.get_by_role("button").all():
        if button.is_visible():
            assert button.evaluate("(b) => b.type === 'submit' && b.form !== null"), button.evaluate("(b) => b.outerHTML")
    assert not any(el.is_visible() for el in page.locator("[data-explore]").all())


OFFLINE_PAGES = [
    ("/", "Check a wallet"), ("/?address=abc", "Check a wallet"),
    (f"/wallet/{SHARP}", "Verdict: Skilled (high confidence)"), (f"/wallet/{STOP_LOSS}", re.compile(r"^\s*Verdict: ")),
    (f"/wallet/{THIN}", "Verdict: Not enough data"), (f"/wallet/{UNKNOWN}", "Not available offline"),
    ("/no-such-page", "Page not found"),
]


@pytest.mark.parametrize(("path", "h1"), OFFLINE_PAGES)
def test_ad18_every_offline_page_is_complete_without_javascript(make_page, path: str, h1) -> None:
    """AD-18, NFR-9, UX-DR12 (Story 3.5 AC1): with JavaScript off every Offline Mode page is complete. The chart
    without its script is proven in test_chart_script.py::test_ad18_chart_complete_without_the_script."""
    assert_complete(make_page(path, java_script_enabled=False), h1)


def test_ad18_not_loaded_page_is_complete_without_javascript(make_page, not_loaded_url: str) -> None:
    """AD-18, FR-14: before load-sample, the Lookup page's box and a Wallet's page say how to load it, without JavaScript."""
    lookup = make_page("/", base=not_loaded_url, java_script_enabled=False)
    assert_complete(lookup, "Check a wallet")
    expect(lookup.get_by_role("note")).to_contain_text("uv run liquidoracle load-sample")
    assert_complete(make_page(f"/wallet/{SHARP}", base=not_loaded_url, java_script_enabled=False), "Sample Dataset not loaded")


def test_ad18_lookup_form_submits_by_keyboard_without_javascript(make_page) -> None:
    """AD-18, FR-1: with JavaScript off, typing an address in the field and pressing Enter opens its Verdict page."""
    page = make_page("/", java_script_enabled=False)
    tab_to(page, page.get_by_role("textbox", name="Wallet address"))
    page.keyboard.type(SHARP)
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(rf"/wallet/{SHARP}$"))
    assert_complete(page, "Verdict: Skilled (high confidence)")


def wait_for_job(page: Page) -> None:
    """Asks the fetching page's progress address every 50 ms until the job has ended, for at most JOB_LIMIT seconds."""
    progress = page.url.split("/wallet/")[0] + page.locator("#job-block").get_attribute("data-progress")
    deadline = time.monotonic() + JOB_LIMIT
    while True:
        reply = page.request.get(progress)
        assert reply.ok, f"the progress address answered {reply.status}"
        if reply.json()["status"] not in ("queued", "running"):
            return
        assert time.monotonic() < deadline, "the lookup job did not end"
        page.wait_for_timeout(50)


@pytest.mark.parametrize(("address", "failure", "h1"), [
    (SHARP, None, "Verdict: Skilled (high confidence)"),
    ("0x" + "5" * 40, None, "No Polymarket history found"),
    ("0x" + "6" * 40, PolymarketUnavailable("the stand-in is down"), "Polymarket did not answer"),
    ("0x" + "7" * 40, KeyError("a bug"), "Something went wrong"),
])
def test_ad18_live_pages_are_complete_without_javascript(make_page, live_app, address: str, failure, h1: str) -> None:
    """AD-18, UX-DR22, UX-DR23: in a live run with JavaScript off, the fetching page is complete and its "Reload this
    page" link, followed by keyboard, shows the result: the Verdict, No history, Polymarket did not answer, or the
    plain error page."""
    page = fetching_page(make_page, live_app, address, 1280, java_script_enabled=False)
    assert_complete(page, f"Checking {address[:6]}…{address[-4:]}")
    if failure is not None:
        live_app.polymarket.fail_with(failure)
    live_app.polymarket.release()
    wait_for_job(page)
    tab_to(page, page.get_by_role("link", name="Reload this page"))
    page.keyboard.press("Enter")
    expect(page.get_by_role("heading", level=1)).to_have_text(h1)
    assert_complete(page, h1)
