"""The one frozen settings object (AD-13, NFR-5, NFR-6)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from liquidoracle.settings import ENV_KEYS, Settings, SettingsError, load_settings

REPO = Path(__file__).resolve().parents[1]


def write_env(tmp_path: Path, text: str) -> Path:
    env = tmp_path / ".env"
    env.write_text(text, encoding="utf-8")
    return env


def test_defaults_without_flags_or_env_file(tmp_path: Path) -> None:
    """AD-13, AD-23: with no flag and no .env, the defaults hold (port 8044, Seed 44, 5 requests/s)."""
    settings = load_settings(cli={}, env_file=tmp_path / "missing.env")
    assert settings == Settings(
        port=8044,
        seed=44,
        polymarket_requests_per_second=5.0,
        offline=False,
        anthropic_api_key=None,
    )


def test_env_file_beats_default(tmp_path: Path) -> None:
    """AD-13: a value in .env replaces the default."""
    env = write_env(tmp_path, "PORT=9000\nSEED=7\nOFFLINE=true\nPOLYMARKET_REQUESTS_PER_SECOND=2.5\n")
    settings = load_settings(cli={}, env_file=env)
    assert (settings.port, settings.seed, settings.offline) == (9000, 7, True)
    assert settings.polymarket_requests_per_second == 2.5


def test_flag_beats_env_file(tmp_path: Path) -> None:
    """AD-13: a command-line flag wins over .env (.env PORT=9000, --port 9100 gives 9100)."""
    env = write_env(tmp_path, "PORT=9000\nOFFLINE=false\n")
    settings = load_settings(cli={"port": 9100, "offline": True}, env_file=env)
    assert settings.port == 9100
    assert settings.offline is True


def test_flag_not_given_falls_through_to_env_file(tmp_path: Path) -> None:
    """AD-13: a flag left out (None) does not hide the .env value."""
    env = write_env(tmp_path, "PORT=9000\n")
    assert load_settings(cli={"port": None}, env_file=env).port == 9000


def test_empty_env_value_means_default(tmp_path: Path) -> None:
    """AD-13: `KEY=` with nothing after it counts as not set, so the default holds."""
    env = write_env(tmp_path, "PORT=\nANTHROPIC_API_KEY=\n")
    settings = load_settings(cli={}, env_file=env)
    assert settings.port == 8044
    assert settings.anthropic_api_key is None


def test_process_environment_is_not_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-13: only flag, .env and default count; a process environment variable is ignored."""
    monkeypatch.setenv("PORT", "7000")
    monkeypatch.setenv("POLYMARKET_REQUESTS_PER_SECOND", "99")
    settings = load_settings(cli={}, env_file=tmp_path / "missing.env")
    assert settings.port == 8044
    assert settings.polymarket_requests_per_second == 5.0


def test_settings_are_frozen() -> None:
    """AD-13: the settings object cannot be changed after it is built."""
    settings = load_settings(cli={}, env_file=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.port = 1  # type: ignore[misc]


def test_api_key_is_kept_out_of_repr(tmp_path: Path) -> None:
    """NFR-5: the key never shows in repr or str, so it cannot reach a log line."""
    env = write_env(tmp_path, "ANTHROPIC_API_KEY=sk-ant-secret-123\n")
    settings = load_settings(cli={}, env_file=env)
    assert settings.anthropic_api_key == "sk-ant-secret-123"
    assert "sk-ant-secret-123" not in repr(settings)
    assert "sk-ant-secret-123" not in str(settings)


@pytest.mark.parametrize("rate", ["5", "5.0", "0.5", "1"])
def test_pace_up_to_five_is_allowed(tmp_path: Path, rate: str) -> None:
    """NFR-6: 5 requests per second or fewer is accepted."""
    env = write_env(tmp_path, f"POLYMARKET_REQUESTS_PER_SECOND={rate}\n")
    assert load_settings(cli={}, env_file=env).polymarket_requests_per_second == float(rate)


@pytest.mark.parametrize("rate", ["6", "5.01", "100"])
def test_pace_above_five_stops_the_start(tmp_path: Path, rate: str) -> None:
    """NFR-6: a pace above 5 requests per second is refused with a plain sentence naming the limit."""
    env = write_env(tmp_path, f"POLYMARKET_REQUESTS_PER_SECOND={rate}\n")
    with pytest.raises(SettingsError, match=r"POLYMARKET_REQUESTS_PER_SECOND .* at most 5 requests per second"):
        load_settings(cli={}, env_file=env)


@pytest.mark.parametrize(
    ("line", "key"),
    [
        ("PORT=abc", "PORT"),
        ("PORT=0", "PORT"),
        ("PORT=70000", "PORT"),
        ("PORT=80.5", "PORT"),
        ("SEED=-1", "SEED"),
        ("SEED=x", "SEED"),
        ("POLYMARKET_REQUESTS_PER_SECOND=0", "POLYMARKET_REQUESTS_PER_SECOND"),
        ("POLYMARKET_REQUESTS_PER_SECOND=-2", "POLYMARKET_REQUESTS_PER_SECOND"),
        ("POLYMARKET_REQUESTS_PER_SECOND=x", "POLYMARKET_REQUESTS_PER_SECOND"),
        ("POLYMARKET_REQUESTS_PER_SECOND=nan", "POLYMARKET_REQUESTS_PER_SECOND"),
        ("POLYMARKET_REQUESTS_PER_SECOND=inf", "POLYMARKET_REQUESTS_PER_SECOND"),
        ("OFFLINE=maybe", "OFFLINE"),
    ],
)
def test_bad_values_give_a_plain_error_naming_the_key(tmp_path: Path, line: str, key: str) -> None:
    """AD-13, NFR-6: a bad value stops the start with a sentence that names the setting."""
    env = write_env(tmp_path, line + "\n")
    with pytest.raises(SettingsError, match=key):
        load_settings(cli={}, env_file=env)


def test_bad_flag_value_is_checked_too() -> None:
    """AD-13: values from flags pass the same checks as values from .env."""
    with pytest.raises(SettingsError, match="PORT"):
        load_settings(cli={"port": 0}, env_file=None)


@pytest.mark.parametrize(("text", "expected"), [("true", True), ("TRUE", True), ("1", True), ("no", False), ("0", False)])
def test_offline_accepts_common_spellings(tmp_path: Path, text: str, expected: bool) -> None:
    """AD-13: OFFLINE=true turns on Offline Mode; common true/false spellings are accepted."""
    env = write_env(tmp_path, f"OFFLINE={text}\n")
    assert load_settings(cli={}, env_file=env).offline is expected


def test_env_example_lists_every_key() -> None:
    """NFR-5: .env.example lists exactly the keys the settings read."""
    lines = (REPO / ".env.example").read_text(encoding="utf-8").splitlines()
    keys = {line.split("=", 1)[0].strip() for line in lines if "=" in line and not line.lstrip().startswith("#")}
    assert keys == set(ENV_KEYS)


def test_env_file_does_not_fill_in_process_variables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-13: `${PORT}` in .env is not filled in from the process environment."""
    monkeypatch.setenv("PORT", "7000")
    env = write_env(tmp_path, "PORT=${PORT}\n")
    with pytest.raises(SettingsError, match="PORT must be a whole number"):
        load_settings(cli={}, env_file=env)


def test_unreadable_env_file_gives_a_plain_error(tmp_path: Path) -> None:
    """AD-13: a .env that is not UTF-8 text stops the start with a sentence, not a traceback."""
    env = tmp_path / ".env"
    env.write_bytes("PORT=9000\n".encode("utf-16"))
    with pytest.raises(SettingsError, match="could not be read"):
        load_settings(cli={}, env_file=env)


def test_unknown_env_key_is_warned_about(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """AD-13: a misspelt key such as POTR=9000 is named in a warning, and the default holds."""
    env = write_env(tmp_path, "POTR=9000\n")
    with caplog.at_level("WARNING", logger="liquidoracle.settings"):
        settings = load_settings(cli={}, env_file=env)
    assert settings.port == 8044
    assert "POTR" in caplog.text
