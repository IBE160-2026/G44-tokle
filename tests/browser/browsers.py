"""Which browser the browser tests drive (AD-17; Story 3.4).

The installed Google Chrome, then Microsoft Edge; Playwright downloads nothing. With `CI` set
(GitHub Actions sets CI=true) a browser that cannot start fails the test, so a green check means the
browser tests ran (Edvard, 2026-11-24). Without `CI` they skip and say which browsers were tried.
"""

from __future__ import annotations

import os

import pytest
from playwright.sync_api import Browser, Error, Playwright

CHANNELS = ("chrome", "msedge")


def in_ci() -> bool:
    """GitHub sets CI=true; an empty, "0", "false" or "no" value (some local setups export one) is not CI."""
    return os.environ.get("CI", "").strip().lower() not in ("", "0", "false", "no")


def launch(playwright: Playwright) -> Browser:
    """The first installed browser that starts; on CI a failure, elsewhere a skip, when none does."""
    tried = []
    for channel in CHANNELS:
        try:
            return playwright.chromium.launch(channel=channel)
        except Error as error:
            tried.append(f"{channel}: {str(error).splitlines()[0]}")
    reason = "no browser for the browser tests (install Google Chrome or Microsoft Edge); tried " + "; ".join(tried)
    if in_ci():
        pytest.fail(reason, pytrace=False)
    pytest.skip(reason)
