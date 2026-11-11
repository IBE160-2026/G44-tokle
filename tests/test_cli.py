"""The `liquidoracle` command and its serving rules (AD-23, AD-13, NFR-6)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from flask import Flask

import liquidoracle.__main__ as cli


@pytest.fixture
def in_empty_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run from a folder with no .env, so a developer's own .env cannot change the test."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def fake_server(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace Flask.run so no server starts; record the arguments it was given."""
    calls: dict[str, Any] = {}

    def fake_run(self: Flask, **kwargs: Any) -> None:
        calls.update(kwargs)

    monkeypatch.setattr(Flask, "run", fake_run)
    monkeypatch.setattr(cli, "port_in_use", lambda host, port: False)
    return calls


@pytest.mark.parametrize(("command", "story"), [("load-sample", "1.6"), ("make-synthetic", "1.3")])
def test_unbuilt_commands_say_not_built_yet(command: str, story: str, capsys: pytest.CaptureFixture[str]) -> None:
    """AD-14, FR-13: the load-sample and make-synthetic commands exist and say they are not built yet."""
    assert cli.main([command]) == 0
    assert f"not built yet (Story {story})" in capsys.readouterr().out


def test_run_uses_the_serving_rules(in_empty_dir: Path, fake_server: dict[str, Any]) -> None:
    """AD-23, NFR-3: run binds to 127.0.0.1 on port 8044 with debug, reloader and dotenv loading off."""
    assert cli.main(["run"]) == 0
    assert fake_server == {
        "host": "127.0.0.1",
        "port": 8044,
        "debug": False,
        "use_reloader": False,
        "load_dotenv": False,
    }


def test_port_flag_beats_env_file(in_empty_dir: Path, fake_server: dict[str, Any]) -> None:
    """AD-13: `--port` wins over PORT in .env."""
    (in_empty_dir / ".env").write_text("PORT=9000\n", encoding="utf-8")
    assert cli.main(["run", "--port", "9100"]) == 0
    assert fake_server["port"] == 9100


def test_pace_above_five_stops_run_with_a_plain_message(
    in_empty_dir: Path, fake_server: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """NFR-6: POLYMARKET_REQUESTS_PER_SECOND=6 stops the start with exit code 2, one sentence, no traceback."""
    (in_empty_dir / ".env").write_text("POLYMARKET_REQUESTS_PER_SECOND=6\n", encoding="utf-8")
    assert cli.main(["run"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("LiquidOracle cannot start: POLYMARKET_REQUESTS_PER_SECOND is 6")
    assert "at most 5 requests per second" in err
    assert "Traceback" not in err
    assert fake_server == {}  # the server never started


def test_bad_env_value_stops_run_with_a_plain_message(
    in_empty_dir: Path, fake_server: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """AD-13: a bad value such as PORT=abc stops the start with a sentence naming the key."""
    (in_empty_dir / ".env").write_text("PORT=abc\n", encoding="utf-8")
    assert cli.main(["run"]) == 2
    err = capsys.readouterr().err
    assert "PORT must be a whole number" in err
    assert "Traceback" not in err


def test_busy_port_stops_run_with_a_plain_message(
    in_empty_dir: Path, fake_server: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AD-23: if the port already answers, run stops instead of starting a second, silent server."""
    monkeypatch.setattr(cli, "port_in_use", lambda host, port: True)
    assert cli.main(["run"]) == 2
    assert "port 8044 is already in use" in capsys.readouterr().err
    assert fake_server == {}


def test_server_error_on_start_gives_a_plain_message(
    in_empty_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AD-23: an operating-system error while binding is shown as a sentence, not a traceback."""

    def failing_run(self: Flask, **kwargs: Any) -> None:
        raise OSError(98, "Address already in use")

    monkeypatch.setattr(Flask, "run", failing_run)
    monkeypatch.setattr(cli, "port_in_use", lambda host, port: False)
    assert cli.main(["run"]) == 2
    err = capsys.readouterr().err
    assert "cannot start on port 8044: Address already in use" in err
    assert "Traceback" not in err
