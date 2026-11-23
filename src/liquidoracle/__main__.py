"""The `liquidoracle` command: run, load-sample, make-synthetic, build-sample.

This is the imperative shell's entry point. It reads the flags, builds the one
frozen settings object (AD-13) and starts the web app with the serving rules of
AD-23.
"""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from liquidoracle.data.client import WalletClient
from liquidoracle.data.store import LIVE_DB, OFFLINE_DB, Store, StoreError
from liquidoracle.services.jobs import Jobs
from liquidoracle.settings import Settings, SettingsError, load_settings

HOST = "127.0.0.1"  # AD-23: bound to this laptop only, never to the network

log = logging.getLogger("liquidoracle")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="liquidoracle",
        description="Skill or luck: check a Polymarket wallet's results. Local and read-only.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    run = commands.add_parser("run", help="start the web app on this computer")
    run.add_argument(
        "--offline",
        action="store_const",
        const=True,
        default=None,
        help="Offline Mode: sample data only, no network",
    )
    run.add_argument("--port", type=int, default=None, help="port to serve on (default 8044)")
    run.add_argument("--seed", type=int, default=None, help="random Seed for the tests (default 44)")

    commands.add_parser(
        "load-sample",
        help="load the Sample Dataset into instance/offline.db (run from the repository folder; takes under a minute)",
    )
    commands.add_parser("make-synthetic", help="generate the Synthetic Wallets (run from the repository folder)")
    build = commands.add_parser(
        "build-sample",
        help="rebuild the real Sample Wallets from the raw capture zip (not in the repository; run from the repository folder)",
    )
    build.add_argument("capture", type=Path, help="the capture zip, with its .sha256 and the additions file next to it")
    build.add_argument(
        "--fetch",
        action="store_true",
        help="first fetch what the capture lacks into the additions file (network, read-only; done once)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)

    if args.command == "load-sample":
        return load_sample(Path.cwd())
    if args.command == "make-synthetic":
        return make_synthetic(Path.cwd())
    if args.command == "build-sample":
        return build_sample(Path.cwd(), args.capture, fetch=args.fetch)
    if args.command != "run":  # argparse allows only these commands; never start by accident
        raise AssertionError(f"unhandled command {args.command!r}")

    env_file = Path.cwd() / ".env"
    if env_file.is_file():
        log.info("Reading settings from %s", env_file)
    else:
        log.info("No .env in %s; using flags and defaults", Path.cwd())
    try:
        settings = load_settings(
            cli={"offline": args.offline, "port": args.port, "seed": args.seed},
            env_file=env_file,
        )
    except SettingsError as error:
        print(f"LiquidOracle cannot start: {error}", file=sys.stderr)
        return 2

    return serve(settings)


def make_synthetic(root: Path) -> int:
    """FR-13, AD-14: write the small Synthetic Wallets (committed) and the coin-flippers (git-ignored)."""
    from liquidoracle.data import synthetic

    if not in_repository(root, "make-synthetic"):
        return 2
    small = synthetic.write_small(root)
    folder = synthetic.write_coin_flippers(root)
    print(f"Wrote {len(small)} Synthetic Wallets to {root / synthetic.SMALL_DIR}")
    print(f"Wrote {synthetic.COIN_FLIPPERS} coin-flippers to {folder} (not committed)")
    return 0


def build_sample(root: Path, capture: Path, *, fetch: bool) -> int:
    """AD-14, FR-12 (Story 2.6): write `sample_data/real/` from the capture zip and its additions file.

    Without `--fetch` it makes no network call. With it, the Gamma records and 0xd218e4's newest
    CLOSED pages the capture lacks are first fetched once, read-only, through the app's own client.
    """
    from liquidoracle.data import real_sample
    from liquidoracle.data.errors import PolymarketUnavailable
    from liquidoracle.data.polymarket import PolymarketClient
    from liquidoracle.settings import MAX_REQUESTS_PER_SECOND

    if not in_repository(root, "build-sample"):
        return 2
    started = time.monotonic()
    try:
        if fetch:
            path = real_sample.fetch_additions(capture, PolymarketClient(MAX_REQUESTS_PER_SECOND))
            print(f"Wrote {path} and its .sha256 ({time.monotonic() - started:.0f} s)")
        built = real_sample.build(capture, root)
    except (real_sample.BuildError, PolymarketUnavailable, OSError, ValueError, KeyError) as error:
        print(f"build-sample stopped: {error}", file=sys.stderr)
        return 2
    size = sum(item.file_bytes for item in built)
    print(f"Done: {len(built)} real Wallets in {root / real_sample.REAL_DIR}, {size / 1e6:.1f} MB "
          f"({time.monotonic() - started:.0f} s).")
    return 0


def load_sample(root: Path) -> int:
    """FR-12, FR-14, AD-14: regenerate the coin-flippers and load every Sample Wallet into offline.db.

    Always writes `instance/offline.db`, whatever the flags or `.env` say, through the same
    fetch pipeline a live lookup uses, with `OfflineClient` as the client.
    """
    from liquidoracle.data import offline, synthetic
    from liquidoracle.services import fetch

    if not in_repository(root, "load-sample"):
        return 2
    started = time.monotonic()
    try:
        print(f"Writing {synthetic.COIN_FLIPPERS:,} coin-flippers to {root / synthetic.COIN_FLIPPER_DIR} ...")
        synthetic.write_coin_flippers(root, synthetic.COIN_FLIPPERS)
        client = offline.OfflineClient(offline.sample_files(root))
        addresses = client.addresses()
        database = Store(root / OFFLINE_DB)
        try:
            print(f"Loading {len(addresses):,} Sample Wallets into {database.path} ...")
            for done, address in enumerate(addresses, start=1):
                fetch.fetch_wallet(client, database, address)
                if done % 100 == 0 or done == len(addresses):
                    print(f"  {done:,} of {len(addresses):,}")
            loaded = database.wallet_count()
        finally:
            database.close()
    except (OSError, ValueError, LookupError, StoreError) as error:  # LookupError: NotAvailableOffline
        print(f"load-sample stopped: {error}", file=sys.stderr)
        return 2
    print(f"Done: {loaded:,} Sample Wallets in {root / OFFLINE_DB} ({time.monotonic() - started:.0f} s).")
    return 0


def in_repository(root: Path, command: str) -> bool:
    """True when `root` is the LiquidOracle repository folder; otherwise says so on stderr."""
    if (root / "sample_data").is_dir() and (root / "pyproject.toml").is_file():
        return True
    print(
        f"{command} must run from the LiquidOracle repository folder ({root} has no sample_data/ "
        "and pyproject.toml).",
        file=sys.stderr,
    )
    return False


@dataclass(frozen=True)
class Sources:
    """The client, database and job queue a run uses (AD-13).

    `jobs` is None in Offline Mode: it fetches nothing in the background, and pages may ask its
    `OfflineClient` directly. A live run has a job queue, and only the worker uses its client (AD-5).
    """

    client: WalletClient
    store: Store
    jobs: Jobs | None


def open_sources(settings: Settings, root: Path) -> Sources:
    """AD-13: the one place the mode picks the client, the database file and the job queue.

    Offline Mode gets `OfflineClient` and `instance/offline.db`; a live run gets `PolymarketClient`,
    `instance/live.db` and a job queue. Nothing else branches on the mode. `serve` hands the result
    to the pages through `Lookup` and to the worker.
    """
    from liquidoracle.data.offline import OfflineClient, sample_files
    from liquidoracle.data.polymarket import PolymarketClient

    if settings.offline:
        # list_files: Sample files written after the start (a load-sample run) are still found.
        client = OfflineClient(sample_files(root), list_files=lambda: sample_files(root))
        return Sources(client, Store(root / OFFLINE_DB), None)
    store = Store(root / LIVE_DB)
    return Sources(PolymarketClient(settings.polymarket_requests_per_second), store, Jobs(store))


def serve(settings: Settings) -> int:
    """Start the web app with the AD-23 serving rules. Blocks until Ctrl+C."""
    from liquidoracle.services.jobs import Worker
    from liquidoracle.services.lookup import Lookup
    from liquidoracle.web import create_app

    root = Path.cwd()
    if settings.offline and not in_repository(root, "run --offline"):
        return 2
    if port_in_use(HOST, settings.port):
        print(
            f"LiquidOracle cannot start: port {settings.port} is already in use "
            "(is LiquidOracle already running?). Close the other program or choose "
            "another port with --port.",
            file=sys.stderr,
        )
        return 2

    try:
        sources = open_sources(settings, root)
    except (StoreError, OSError) as error:  # OSError: e.g. `instance` is a file, or the folder is read-only
        database = root / (OFFLINE_DB if settings.offline else LIVE_DB)
        print(
            f"LiquidOracle cannot start: the database {database} cannot be opened ({error}). "
            "Delete that file and start again; in Offline Mode, run `uv run liquidoracle load-sample` first.",
            file=sys.stderr,
        )
        return 2
    if sources.jobs is None:
        lookup = Lookup(sources.client, sources.store, seed=settings.seed)
    else:
        try:
            interrupted = sources.store.interrupt_running_jobs()  # AD-5: left running when the app last closed
        except StoreError as error:
            print(f"LiquidOracle cannot start: the database {sources.store.path} cannot be written ({error}).",
                  file=sys.stderr)
            return 2
        if interrupted:
            log.info("%d lookup(s) were cut off when the app last closed; they are marked interrupted", interrupted)
        Worker(sources.client, sources.jobs).start()  # AD-5, AD-23: the one worker, started only here
        lookup = Lookup(None, sources.store, seed=settings.seed, jobs=sources.jobs)
    app = create_app(settings, lookup)
    log.info("LiquidOracle is running at http://%s:%d (press Ctrl+C to stop)", HOST, settings.port)
    # If binding still fails (no permission, or another program took the port after the
    # check above), Werkzeug prints a plain message itself and exits with code 1.
    app.run(
        host=HOST,
        port=settings.port,
        debug=False,
        use_reloader=False,
        load_dotenv=False,
    )
    return 0


def port_in_use(host: str, port: int) -> bool:
    """True when something already answers on the port.

    Needed because on Windows a second server can bind the same port without an
    error, and then it never gets any requests (found while building Story 1.1).
    Accepted limits: a program that grabs the port between this check and the bind
    is not caught, and a free port can add up to half a second to the start.
    """
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


if __name__ == "__main__":
    sys.exit(main())
