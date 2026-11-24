"""Browser tests: the real pages in a real browser (AD-17, AD-18; Story 3.4).

The app runs in Offline Mode on 127.0.0.1 over the committed Synthetic Wallets, in a thread of the
test process. Playwright for Python drives the Chrome or Edge already installed (`browsers.py`,
which also decides skip or fail when none starts). Sockets are allowed here to 127.0.0.1 only,
never to the network.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from browsers import launch
from playwright.sync_api import Browser, sync_playwright
from werkzeug.serving import make_server

from liquidoracle.data import synthetic
from liquidoracle.data.offline import OfflineClient, sample_files
from liquidoracle.data.store import OFFLINE_DB, Store
from liquidoracle.services.fetch import fetch_wallet
from liquidoracle.services.lookup import Lookup
from liquidoracle.settings import Settings
from liquidoracle.web import create_app

HERE = Path(__file__).resolve().parent
LOCAL = "127.0.0.1"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """AD-17: every test in this folder may open sockets to 127.0.0.1 and nowhere else."""
    for item in items:
        if HERE in Path(str(item.path)).resolve().parents:
            item.add_marker(pytest.mark.allow_hosts([LOCAL]))


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        found = launch(playwright)
        yield found
        found.close()


@pytest.fixture(scope="session")
def app_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """The app in Offline Mode with the committed Synthetic Wallets and one coin-flipper, on a free port."""
    root = tmp_path_factory.mktemp("browser-repo")
    synthetic.write_small(root)
    synthetic.write_coin_flippers(root, 1)
    client = OfflineClient(sample_files(root))
    store = Store(root / OFFLINE_DB)
    for address in client.addresses():
        fetch_wallet(client, store, address)
    server = make_server(LOCAL, 0, create_app(Settings(offline=True), Lookup(client, store, seed=44)), threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://{LOCAL}:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)
    store.close()
