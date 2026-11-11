"""The placeholder Check a wallet page (AD-18, UX-DR8)."""

from __future__ import annotations

import re

from liquidoracle.settings import Settings
from liquidoracle.web import create_app


def get_home(settings: Settings) -> str:
    response = create_app(settings).test_client().get("/")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_check_a_wallet_page_is_served() -> None:
    """UX-DR8, AD-18: `/` serves the Check a wallet page in English, with its tab title and one main heading."""
    html = get_home(Settings())
    assert "<title>Check a wallet · LiquidOracle</title>" in html
    assert '<html lang="en">' in html
    assert len(re.findall(r"<h1[\s>]", html)) == 1
    assert "<script" not in html  # complete without JavaScript


def test_offline_pill_shows_only_in_offline_mode() -> None:
    """UX-DR18, AD-13: the Offline pill appears when Offline Mode is on, and not otherwise."""
    assert "Offline Mode · sample data only" in get_home(Settings(offline=True))
    assert "Offline Mode · sample data only" not in get_home(Settings(offline=False))


def test_app_factory_does_not_turn_on_debug() -> None:
    """AD-23: the app is built with debug off."""
    assert create_app(Settings()).debug is False
