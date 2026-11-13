"""The `liquidoracle` command and its serving rules (AD-23, AD-13, NFR-6)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from flask import Flask

import liquidoracle.__main__ as cli
from liquidoracle.settings import Settings


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


def test_load_sample_says_not_built_yet(capsys: pytest.CaptureFixture[str]) -> None:
    """AD-14: the load-sample command exists and says it is not built yet."""
    assert cli.main(["load-sample"]) == 0
    assert "not built yet (Story 1.6)" in capsys.readouterr().out


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


@pytest.fixture
def captured_settings(monkeypatch: pytest.MonkeyPatch) -> list[Settings]:
    """Replace serve() so no server starts; record the Settings that main() built."""
    seen: list[Settings] = []
    monkeypatch.setattr(cli, "serve", lambda settings: seen.append(settings) or 0)
    return seen


def test_offline_and_seed_flags_reach_the_settings(in_empty_dir: Path, captured_settings: list[Settings]) -> None:
    """AD-13: `run --offline --seed 7` gives settings with Offline Mode on and Seed 7."""
    assert cli.main(["run", "--offline", "--seed", "7"]) == 0
    assert (captured_settings[0].offline, captured_settings[0].seed) == (True, 7)


def test_offline_in_env_file_holds_when_no_flag_is_given(in_empty_dir: Path, captured_settings: list[Settings]) -> None:
    """AD-13: OFFLINE=true in .env turns on Offline Mode when --offline is not given."""
    (in_empty_dir / ".env").write_text("OFFLINE=true\nSEED=9\n", encoding="utf-8")
    assert cli.main(["run"]) == 0
    assert (captured_settings[0].offline, captured_settings[0].seed) == (True, 9)


def test_port_in_use_is_true_when_the_port_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-23: a port that accepts a connection counts as in use (the Windows double-start bug)."""

    class Answering:
        def __enter__(self) -> "Answering":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(cli.socket, "create_connection", lambda address, timeout: Answering())
    assert cli.port_in_use("127.0.0.1", 8044) is True


@pytest.mark.parametrize("error", [ConnectionRefusedError(), TimeoutError(), OSError("unreachable")])
def test_port_in_use_is_false_when_nothing_answers(monkeypatch: pytest.MonkeyPatch, error: OSError) -> None:
    """AD-23: a refused, timed-out or failed connection means the port is free."""

    def refuse(address: object, timeout: float) -> None:
        raise error

    monkeypatch.setattr(cli.socket, "create_connection", refuse)
    assert cli.port_in_use("127.0.0.1", 8044) is False
