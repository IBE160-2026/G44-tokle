"""Every test in tests/online/ goes to the real network. It is marked `online`, and
`pyproject.toml` deselects that marker, so these tests never run in CI or by default (AD-17).

Run them on purpose with:  uv run pytest -m online --force-enable-socket tests/online
"""

from __future__ import annotations

from pathlib import Path

import pytest

ONLINE_DIR = Path(__file__).resolve().parent


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if ONLINE_DIR in Path(item.path).resolve().parents:
            item.add_marker(pytest.mark.online)
