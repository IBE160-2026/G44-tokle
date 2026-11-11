"""Placeholder so the online rule can be checked before the first real online test (Epic 2)."""


import pytest


def test_online_tests_are_marked(request: pytest.FixtureRequest) -> None:
    """AD-17: a test in tests/online/ carries the `online` marker and is deselected by default."""
    assert request.node.get_closest_marker("online") is not None
