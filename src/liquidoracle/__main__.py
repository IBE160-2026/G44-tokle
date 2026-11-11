"""The `liquidoracle` command: run, load-sample, make-synthetic.

This is the imperative shell's entry point. It reads the flags, builds the one
frozen settings object (AD-13) and starts the web app with the serving rules of
AD-23.
"""

from __future__ import annotations

import argparse
import logging
import socket
import sys
from pathlib import Path

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

    commands.add_parser("load-sample", help="load the Sample Dataset (not built yet)")
    commands.add_parser("make-synthetic", help="generate the Synthetic Wallets (not built yet)")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)

    if args.command == "load-sample":
        print("load-sample is not built yet (Story 1.6).")
        return 0
    if args.command == "make-synthetic":
        print("make-synthetic is not built yet (Story 1.3).")
        return 0

    try:
        settings = load_settings(
            cli={"offline": args.offline, "port": args.port, "seed": args.seed},
            env_file=Path.cwd() / ".env",
        )
    except SettingsError as error:
        print(f"LiquidOracle cannot start: {error}", file=sys.stderr)
        return 2

    return serve(settings)


def serve(settings: Settings) -> int:
    """Start the web app with the AD-23 serving rules. Blocks until Ctrl+C."""
    from liquidoracle.web import create_app

    if port_in_use(HOST, settings.port):
        print(
            f"LiquidOracle cannot start: port {settings.port} is already in use "
            "(is LiquidOracle already running?). Close the other program or choose "
            "another port with --port.",
            file=sys.stderr,
        )
        return 2

    app = create_app(settings)
    log.info("LiquidOracle is running at http://%s:%d (press Ctrl+C to stop)", HOST, settings.port)
    try:
        app.run(
            host=HOST,
            port=settings.port,
            debug=False,
            use_reloader=False,
            load_dotenv=False,
        )
    except OSError as error:  # most often: the port is already in use
        print(
            f"LiquidOracle cannot start on port {settings.port}: {error.strerror or error}. "
            "Close the other program or choose another port with --port.",
            file=sys.stderr,
        )
        return 2
    return 0


def port_in_use(host: str, port: int) -> bool:
    """True when something already answers on the port.

    Needed because on Windows a second server can bind the same port without an
    error, and then it never gets any requests (found while building Story 1.1).
    """
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


if __name__ == "__main__":
    sys.exit(main())
