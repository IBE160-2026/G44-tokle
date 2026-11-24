"""progress.js in a real browser: a live lookup from the fetching page to its result (Story 3.5).

Each test runs its own live app (`live_app` in conftest.py): an empty database, the real job queue and
worker thread, and a stand-in Polymarket that serves the Synthetic Wallets from files. The test holds the
stand-in back so the fetching page is up, then releases it or makes it fail, and watches progress.js poll
and swap the result in. Waiting is done by Playwright's retrying expect or the page's paused clock.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable

import pytest
from pages import assert_no_sideways_scroll
from playwright.sync_api import Page, Route, expect

from liquidoracle.data import synthetic
from liquidoracle.data.errors import PolymarketUnavailable

SHARP = synthetic.address_of("sharp-trader")
NEVER_SEEN = "0x" + "0" * 40  # the stand-in has no positions for it, as Polymarket answers an unused address
RESULT_WAIT = 30_000  # ms: the worker fetches and the page renders 10,000 replays; expect returns as soon as it is there
MAX_FAILURES = 30
# Records each history.replaceState call, so the test sees which URL progress.js put in the address bar.
WATCH_ADDRESS = """
window.__replaced = [];
const replaceState = history.replaceState.bind(history);
history.replaceState = (state, title, url) => { window.__replaced.push(new URL(url, location.href).href); return replaceState(state, title, url); };
"""


def wait_for_polls(page: Page, times: int) -> None:
    """Waits for `times` progress requests (events from the page, not a sleep)."""
    for _ in range(times):
        page.wait_for_event("request", lambda request: request.url.endswith("/progress"), timeout=10_000)


def run_until(page: Page, done: Callable[[], bool]) -> None:
    """Moves the paused page clock in 100 ms steps (a poll comes once a second, so none is skipped or doubled)
    until `done()`, or fails after 60 s of real time."""
    deadline = time.monotonic() + 60
    while not done():
        assert time.monotonic() < deadline, "the page stopped polling too soon"
        page.clock.run_for(100)


def assert_fetching(page: Page, address: str) -> None:
    short = f"{address[:6]}…{address[-4:]}"
    expect(page.locator("h1")).to_have_text(f"Checking {short}")
    expect(page).to_have_title(f"Checking · {short} · LiquidOracle")
    expect(page).to_have_url(re.compile(rf"/wallet/{address}\?job=\d+$"))


def test_ux_dr22_live_lookup_swaps_in_the_verdict(make_page, live_app) -> None:
    """UX-DR22, AD-5, AD-18, UX-DR21, 3.5 matrix "Live lookup": the fetching page polls the job's progress; when
    the stand-in is released the Verdict replaces it, the tab title changes, focus moves to its main heading,
    the chart is enhanced and the copy button copies. The server renders the result at the fetching page's
    own URL, so only that same-URL case is checked: replaceState is called with the reply's URL and a reload
    shows the Verdict (a result at another URL is not tested here)."""
    live_app.polymarket.hold()
    page = make_page(f"/wallet/{SHARP}", base=live_app.url, scripts=[WATCH_ADDRESS],
                     permissions=["clipboard-read", "clipboard-write"])
    assert_fetching(page, SHARP)
    fetching_url = page.url
    wait_for_polls(page, 2)
    expect(page.locator("#job-block")).to_be_visible()  # still fetching while Polymarket is held back

    live_app.polymarket.release()
    heading = page.locator("#verdict-heading")
    expect(heading).to_be_focused(timeout=RESULT_WAIT)
    expect(heading).to_contain_text("Verdict: ")
    expect(page.locator("#job-block")).to_have_count(0)
    expect(page).to_have_title(f"Verdict · {SHARP[:6]}…{SHARP[-4:]} · LiquidOracle")
    assert page.evaluate("() => window.__replaced") == [fetching_url]  # the result's own address (here the same)

    expect(page.locator(".chart")).to_have_attribute("data-enhanced", "true")
    slider = page.get_by_role("slider", name="Replays by result")
    expect(slider).to_be_visible()
    slider.focus()
    page.keyboard.press("Home")
    expect(slider).to_have_attribute("aria-valuenow", "1")

    page.locator(".copy-button").click()
    expect(page.locator(".copy-label")).to_have_text("Copied")
    assert page.evaluate("() => navigator.clipboard.readText()") == SHARP

    page.reload()  # the same URL now gives the Verdict itself, not a fetch to follow
    expect(page.locator("#verdict-heading")).to_be_visible()
    expect(page.locator("#job-block")).to_have_count(0)


@pytest.mark.parametrize(("address", "heading"), [
    (SHARP, "Polymarket did not answer"),
    (NEVER_SEEN, "No Polymarket history found"),
])
def test_ux_dr23_message_page_swapped_in(make_page, live_app, address: str, heading: str) -> None:
    """UX-DR23, UX-DR22, FR-1, FR-2, 3.5 matrix "Polymarket down / no history": when Polymarket fails or has
    nothing for the address, the matching message page replaces the fetching page, focus on its heading."""
    live_app.polymarket.hold()
    if address == SHARP:
        live_app.polymarket.fail_with(PolymarketUnavailable("the stand-in is down"))
    page = make_page(f"/wallet/{address}", base=live_app.url)
    assert_fetching(page, address)
    live_app.polymarket.release()
    h1 = page.locator("h1")
    expect(h1).to_have_text(heading, timeout=RESULT_WAIT)
    expect(h1).to_be_focused()
    expect(page).to_have_title(f"{heading} · {address[:6]}…{address[-4:]} · LiquidOracle")
    expect(page.locator("#job-block")).to_have_count(0)


def test_ad18_progress_gives_up_after_30_failed_polls(make_page, live_app) -> None:
    """AD-18, UX-DR22, 3.5 matrix "Progress keeps failing": when every progress reply fails, the page polls 30
    times, then stops; the "Reload this page" link is still there. The page clock is paused and moved in
    100 ms steps, so a poll (one a second) is never skipped or doubled."""
    live_app.polymarket.hold()
    page = make_page(f"/wallet/{SHARP}", base=live_app.url, clock=True)
    failed: list[str] = []

    def fail(route: Route) -> None:
        failed.append(route.request.url)
        route.fulfill(status=500, body="")

    page.route("**/jobs/*/progress", fail)
    run_until(page, lambda: len(failed) >= MAX_FAILURES)
    assert len(failed) == MAX_FAILURES
    for _ in range(60):  # another minute of page time, a second at a time: no 31st poll
        page.clock.run_for(1000)
    assert len(failed) == MAX_FAILURES
    assert_fetching(page, SHARP)
    expect(page.get_by_role("link", name="Reload this page")).to_be_visible()


def test_ux_dr10_fetching_and_unavailable_pages_fit_320_px(make_page, live_app) -> None:
    """UX-DR10, UX-DR22, UX-DR23 (Story 3.4 review B7): the fetching page and the Polymarket did not answer page
    do not scroll sideways at 320 px."""
    live_app.polymarket.hold()
    live_app.polymarket.fail_with(PolymarketUnavailable("the stand-in is down"))
    page = make_page(f"/wallet/{SHARP}", 320, base=live_app.url)
    assert_fetching(page, SHARP)
    assert_no_sideways_scroll(page, "the fetching page at 320 px")
    live_app.polymarket.release()
    expect(page.locator("h1")).to_have_text("Polymarket did not answer", timeout=RESULT_WAIT)
    assert_no_sideways_scroll(page, "the Polymarket did not answer page at 320 px")
    page.reload()
    expect(page.locator("h1")).to_have_text("Polymarket did not answer")
    assert_no_sideways_scroll(page, "the Polymarket did not answer page, loaded, at 320 px")


def test_ad18_progress_failure_count_resets_after_a_good_reply(make_page, live_app) -> None:
    """AD-18, UX-DR22: progress.js gives up only after 30 failed polls in a row; one reply that reaches the app
    ("running") in between starts the count again, so here 29 + 30 polls fail before it stops."""
    live_app.polymarket.hold()
    page = make_page(f"/wallet/{SHARP}", base=live_app.url, clock=True)
    failed: list[str] = []
    answered: list[str] = []

    def mostly_fail(route: Route) -> None:
        if len(failed) == MAX_FAILURES - 1 and not answered:
            answered.append(route.request.url)
            route.continue_()  # the app answers "running": Polymarket is still held back
        else:
            failed.append(route.request.url)
            route.fulfill(status=500, body="")

    page.route("**/jobs/*/progress", mostly_fail)
    run_until(page, lambda: len(failed) >= 2 * MAX_FAILURES - 1)
    for _ in range(60):  # another minute of page time: no further poll
        page.clock.run_for(1000)
    assert len(answered) == 1 and len(failed) == 2 * MAX_FAILURES - 1
    assert_fetching(page, SHARP)


def test_ad18_progress_gone_shows_the_result(make_page, live_app) -> None:
    """AD-18, UX-DR22: when the progress URL answers 404 (the job is gone), progress.js fetches the page at once
    and swaps in what it shows, here the Verdict once the stand-in is released, without reloading the page."""
    live_app.polymarket.hold()
    page = make_page(f"/wallet/{SHARP}", base=live_app.url)
    assert_fetching(page, SHARP)
    page.evaluate("() => { window.__notReloaded = true; }")
    gone: list[str] = []

    def answer_gone(route: Route) -> None:
        gone.append(route.request.url)
        route.fulfill(status=404, content_type="application/json", body='{"error": "no such job"}')

    page.route("**/jobs/*/progress", answer_gone)
    live_app.polymarket.release()
    heading = page.locator("#verdict-heading")
    expect(heading).to_be_focused(timeout=RESULT_WAIT)
    assert gone, "no progress request was answered 404"
    assert page.evaluate("() => window.__notReloaded") is True  # swapped in, not a page load
