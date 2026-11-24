"""Finding a browser for the browser tests (AD-17; Story 3.4, Edvard 2026-11-24).

No real browser is started here: a stand-in for Playwright fails or succeeds on demand.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Error

import browsers as browser_setup


class Chromium:
    def __init__(self, works: set[str]) -> None:
        self.works, self.tried = works, []

    def launch(self, channel: str) -> str:
        self.tried.append(channel)
        if channel not in self.works:
            raise Error(f"Chromium distribution '{channel}' is not found\nmore detail")
        return f"browser:{channel}"


class Playwright:
    def __init__(self, works: set[str]) -> None:
        self.chromium = Chromium(works)


def test_ad17_chrome_first_then_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-17: the installed Google Chrome is used when it starts, else Microsoft Edge."""
    monkeypatch.delenv("CI", raising=False)
    assert browser_setup.launch(Playwright({"chrome", "msedge"})) == "browser:chrome"
    edge_only = Playwright({"msedge"})
    assert browser_setup.launch(edge_only) == "browser:msedge"
    assert edge_only.chromium.tried == ["chrome", "msedge"]


@pytest.mark.parametrize("value", [None, "", "0", "false", "False", "no"])
def test_ad17_no_browser_skips_on_a_computer(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """AD-17: without CI set (or set to a false value) and no browser, the browser tests skip and say which
    browsers were tried."""
    if value is None:
        monkeypatch.delenv("CI", raising=False)
    else:
        monkeypatch.setenv("CI", value)
    with pytest.raises(pytest.skip.Exception) as skipped:
        browser_setup.launch(Playwright(set()))
    assert "install Google Chrome or Microsoft Edge" in str(skipped.value)
    assert "chrome: Chromium distribution 'chrome' is not found" in str(skipped.value) and "msedge:" in str(skipped.value)


def test_ad17_no_browser_fails_on_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-17 (Edvard, 2026-11-24): with CI set, a browser that cannot start fails the test, never a quiet skip,
    so a green check on GitHub means the browser tests ran."""
    monkeypatch.setenv("CI", "true")
    with pytest.raises(pytest.fail.Exception) as failed:
        browser_setup.launch(Playwright(set()))
    assert "install Google Chrome or Microsoft Edge" in str(failed.value)
