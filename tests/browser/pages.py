"""What the browser test files share: opening pages, measuring them, and the scripts that set a platform (Story 3.5).

`opened(browser, app_url)` hands out `make(path, …)`, which opens a page in a fresh browser context: its
own window size, theme, motion setting, platform and clipboard rights. Every request the page makes
outside the app it was opened on is blocked and fails the test, so the browser never reaches the
network (AD-17) and nothing is loaded from the internet (UX-DR3). `base` opens a page on another app
started by the tests (the live app with the stand-in Polymarket in `conftest.py`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from playwright.sync_api import Browser, BrowserContext, Page, Route

START = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)

# Platforms, so the copy error's wording does not depend on the machine the tests run on (macOS on CI).
WINDOWS = ("Object.defineProperty(navigator, 'userAgentData', { configurable: true, value: { platform: 'Windows' } });"
           "Object.defineProperty(navigator, 'platform', { configurable: true, value: 'Win32' });")
MAC_CHROME = "Object.defineProperty(navigator, 'userAgentData', { configurable: true, value: { platform: 'macOS' } });"
MAC_SAFARI = ("Object.defineProperty(navigator, 'userAgentData', { configurable: true, value: undefined });"
              "Object.defineProperty(navigator, 'platform', { configurable: true, value: 'MacIntel' });")
REFUSE = "Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: () => Promise.reject(new Error('refused')) } });"
NO_CLIPBOARD = "Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined });"
LIGHT = "try { localStorage.setItem('lo-theme', 'light'); } catch (e) {}"

MakePage = Callable[..., Page]


@contextmanager
def opened(browser: Browser, app_url: str) -> Iterator[MakePage]:
    """`make(path, width=1280, height=800, base=app_url, platform=WINDOWS, scripts=[], theme="dark", clock=False,
    **context options)`; the contexts close and the blocked requests are checked when the block ends.

    With `clock`, the page's clock is installed before the page loads and paused 5 seconds later, so only
    `page.clock.run_for` moves time from then on.
    """
    contexts: list[BrowserContext] = []
    elsewhere: list[str] = []

    def make(path: str, width: int = 1280, height: int = 800, *, base: str | None = None, **options) -> Page:
        home = base or app_url

        def stay_local(route: Route) -> None:
            if route.request.url.startswith(home + "/"):
                route.continue_()
            else:
                elsewhere.append(route.request.url)
                route.abort()

        scripts = [options.pop("platform", WINDOWS), *options.pop("scripts", [])]
        if options.pop("theme", "dark") == "light":
            scripts.append(LIGHT)
        clock = options.pop("clock", False)
        context = browser.new_context(viewport={"width": width, "height": height}, **options)
        contexts.append(context)
        context.route("**/*", stay_local)
        for script in scripts:
            context.add_init_script(script)
        page = context.new_page()
        if clock:
            page.clock.install(time=START)
        page.goto(home + path)
        if clock:
            page.clock.pause_at(START + timedelta(seconds=5))  # from here only run_for moves time
        return page

    yield make
    for context in contexts:
        context.close()
    assert elsewhere == [], f"the page asked for something outside the app: {elsewhere}"


def box(page: Page, selector: str) -> dict:
    found = page.locator(selector).first.bounding_box()
    assert found is not None, selector
    return found


def style(page: Page, selector: str, prop: str) -> str:
    return page.locator(selector).first.evaluate(f"(el) => getComputedStyle(el).getPropertyValue('{prop}')")


def assert_no_sideways_scroll(page: Page, label: str) -> None:
    overflow = page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 0, f"{label} scrolls {overflow} px sideways"


def overlaps(a: dict, b: dict) -> bool:
    """Whether two bounding boxes share any area."""
    return a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"] and a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"]
