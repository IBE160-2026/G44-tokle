"""Shared test setup (AD-17).

`--repetitions` sets how many times a `slow` check repeats a whole test: 100 by
default, 1000 on CI's Linux / Python 3.14 job. Slow checks are never skipped;
only their repetition count changes.
"""

from __future__ import annotations

import argparse

import pytest


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be a whole number, not {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be 1 or more, not {value}")
    return value


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--repetitions",
        type=_positive_int,
        default=100,
        help="how many times slow checks repeat a whole test (default 100; CI Linux 3.14 uses 1000)",
    )


@pytest.fixture
def repetitions(request: pytest.FixtureRequest) -> int:
    """Number of repetitions for a `slow` check (AD-17)."""
    return request.config.getoption("--repetitions")
