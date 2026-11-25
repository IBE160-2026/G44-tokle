"""Browser tests: the real pages in a real browser (AD-17, AD-18; Stories 3.4 and 3.5).

Two apps run in threads of the test process, on 127.0.0.1 only: `app_url`, in Offline Mode over the
committed Synthetic Wallets, and `live_app`, a live run with the real job queue and worker whose
Polymarket is a stand-in that serves the same Synthetic Wallets from files and never touches the
network. Two more Offline Mode apps serve the accessibility checklist (Story 3.5 part B):
`not_loaded_url`, before `load-sample`, and `real_wallets_url`, over the committed real Wallets' files.
Playwright for Python drives the Chrome or Edge already installed (`browsers.py`, which also decides
skip or fail when none starts). Sockets are allowed here to 127.0.0.1 only, never to the network.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest
from browsers import launch
from flask import Flask
from pages import MakePage, opened
from playwright.sync_api import Browser, sync_playwright
from werkzeug.serving import make_server

from liquidoracle.data import synthetic
from liquidoracle.data.errors import PolymarketUnavailable
from liquidoracle.data.offline import REAL_DIR, OfflineClient, sample_files
from liquidoracle.data.store import OFFLINE_DB, Store
from liquidoracle.records import ActivityRow, ListedPosition, Market, Read
from liquidoracle.services.fetch import fetch_wallet
from liquidoracle.services.jobs import Jobs, Worker
from liquidoracle.services.lookup import Lookup
from liquidoracle.settings import Settings
from liquidoracle.web import create_app

HERE = Path(__file__).resolve().parent
LOCAL = "127.0.0.1"
HOLD_LIMIT = 60.0  # seconds a held-back stand-in waits at most, so a failed test never leaves the worker stuck


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
def sample_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A repository folder with the committed Synthetic Wallets and one coin-flipper."""
    root = tmp_path_factory.mktemp("browser-repo")
    synthetic.write_small(root)
    synthetic.write_coin_flippers(root, 1)
    return root


@contextmanager
def serving(app: Flask) -> Iterator[str]:
    """The app on a free port of 127.0.0.1, in a thread; yields its base URL."""
    server = make_server(LOCAL, 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{LOCAL}:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture(scope="session")
def app_url(sample_root: Path) -> Iterator[str]:
    """The app in Offline Mode with the committed Synthetic Wallets and one coin-flipper, on a free port."""
    client = OfflineClient(sample_files(sample_root))
    store = Store(sample_root / OFFLINE_DB)
    for address in client.addresses():
        fetch_wallet(client, store, address)
    with serving(create_app(Settings(offline=True), Lookup(client, store, seed=44))) as url:
        yield url
    store.close()


@pytest.fixture(scope="session")
def not_loaded_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Offline Mode before `load-sample`: the Synthetic Wallets' files but an empty database (Story 3.5)."""
    root = tmp_path_factory.mktemp("not-loaded-repo")
    synthetic.write_small(root)
    store = Store(root / OFFLINE_DB)
    with serving(create_app(Settings(offline=True), Lookup(OfflineClient(sample_files(root)), store, seed=44))) as url:
        yield url
    store.close()


@pytest.fixture(scope="session")
def real_wallets_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Offline Mode over the committed real Wallets' files, read in place (never written), for the Lookup
    page's Real Wallets group (Story 3.5). The database is empty: only the list is looked at."""
    real = sorted((HERE.parents[1] / REAL_DIR).glob("0x*.json"))
    assert real, f"no real Wallets in {REAL_DIR}"
    store = Store(tmp_path_factory.mktemp("real-wallets") / OFFLINE_DB)
    with serving(create_app(Settings(offline=True), Lookup(OfflineClient(real), store, seed=44))) as url:
        yield url
    store.close()


@pytest.fixture
def make_page(browser: Browser, app_url: str) -> Iterator[MakePage]:
    """Opens pages of the Offline Mode app, or of another test app with `base=` (see `pages.opened`)."""
    with opened(browser, app_url) as make:
        yield make


class StandInPolymarket:
    """The live run's Polymarket in the browser tests (Story 3.5): the `WalletClient` protocol over the
    Synthetic Wallets' files, so a live lookup ends in a Verdict with a luck chart. It never touches the
    network. An address it does not know has no positions, as on Polymarket (empty lists, then *No
    Polymarket history found*). A test can hold it back until it is released, or make it fail.
    The HTTP path to the real Polymarket is tested in tests/test_live_lookup.py.
    """

    def __init__(self, client: OfflineClient) -> None:
        self._client = client
        self._known = frozenset(client.addresses())
        self._open = threading.Event()
        self._open.set()
        self.failure: Exception | None = None

    def hold(self) -> None:
        """Every read waits until `release()` (the fetching page stays up meanwhile)."""
        self._open.clear()

    def release(self) -> None:
        self._open.set()

    def fail_with(self, error: Exception) -> None:
        """Every read from now on raises `error` (e.g. `PolymarketUnavailable`: Polymarket did not answer)."""
        self.failure = error

    def _gate(self) -> None:
        """Run at the start of every read: wait while held back, then fail if told to."""
        if not self._open.wait(HOLD_LIMIT):
            raise PolymarketUnavailable("the stand-in was held back too long")
        if self.failure is not None:
            raise self.failure

    def positions_list(
        self,
        wallet: str,
        status: str,
        *,
        sort_by: str | None = None,
        sort_direction: str | None = None,
        until: Callable[[tuple[ListedPosition, ...]], bool] | None = None,
    ) -> Read[ListedPosition]:
        self._gate()
        if wallet not in self._known:
            return Read((), True)
        return self._client.positions_list(wallet, status, sort_by=sort_by, sort_direction=sort_direction, until=until)

    def activity_rows(self, wallet: str, *, start: int, end: int | None = None, row_cap: int | None = None) -> Read[ActivityRow]:
        self._gate()
        return self._client.activity_rows(wallet, start=start, end=end, row_cap=row_cap)

    def markets(self, condition_ids: Iterable[str]) -> tuple[Market, ...]:
        self._gate()
        return self._client.markets(condition_ids)


@dataclass(frozen=True)
class LiveApp:
    url: str
    polymarket: StandInPolymarket


@pytest.fixture
def live_app(sample_root: Path, tmp_path: Path) -> Iterator[LiveApp]:
    """A live run with an empty database: the real job queue, lookup, pages and worker thread, in front of
    the stand-in Polymarket (Story 3.5). Opening a Wallet queues a lookup and shows the fetching page."""
    polymarket = StandInPolymarket(OfflineClient(sample_files(sample_root)))
    store = Store(tmp_path / "live.db")
    jobs = Jobs(store)
    worker = Worker(polymarket, jobs)
    thread = worker.start()
    try:
        with serving(create_app(Settings(offline=False), Lookup(None, store, seed=44, jobs=jobs))) as url:
            yield LiveApp(url, polymarket)
    finally:
        polymarket.release()
        worker.stop()
        thread.join(timeout=10)
        assert not thread.is_alive(), "the worker thread did not stop"
        store.close()
