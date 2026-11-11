"""One frozen settings object, built once at startup (AD-13).

Priority: command-line flag, then the `.env` file, then the default. Process
environment variables are not read. Only this module and `__main__` may read
`.env`; everything else gets the `Settings` object passed down.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

log = logging.getLogger(__name__)

# Polite pacing toward Polymarket: never more than this many requests per second (NFR-6, AD-3).
MAX_REQUESTS_PER_SECOND = 5.0

# Every key `.env` may set. `.env.example` must list exactly these (NFR-5).
ENV_KEYS = (
    "PORT",
    "SEED",
    "POLYMARKET_REQUESTS_PER_SECOND",
    "OFFLINE",
    "ANTHROPIC_API_KEY",
)

_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off"}


class SettingsError(ValueError):
    """A setting has a value the app cannot start with. The message is shown as is."""


@dataclass(frozen=True)
class Settings:
    port: int = 8044  # [ASSUMPTION] AD-23: not 5000, which macOS AirPlay takes
    seed: int = 44  # [ASSUMPTION] AD-15: fixed default, shown on every results page
    polymarket_requests_per_second: float = MAX_REQUESTS_PER_SECOND
    offline: bool = False
    # repr=False keeps the key out of logs, tracebacks and debug output (NFR-5).
    anthropic_api_key: str | None = field(default=None, repr=False)


def load_settings(
    cli: Mapping[str, object | None] | None = None,
    env_file: Path | None = None,
) -> Settings:
    """Build the settings from command-line values, the `.env` file and the defaults.

    `cli` maps a field name (for example "port") to the flag's value, or None when
    the flag was not given. `env_file` is the `.env` path; a missing file is fine.
    """
    cli = cli or {}
    env = _read_env_file(env_file)
    defaults = Settings()

    def pick(name: str, key: str) -> object | None:
        if cli.get(name) is not None:
            return cli[name]
        value = env.get(key)
        if value is None or value.strip() == "":
            return None
        return value.strip()

    port = _parse_port(pick("port", "PORT"), defaults.port)
    seed = _parse_seed(pick("seed", "SEED"), defaults.seed)
    rate = _parse_rate(
        pick("polymarket_requests_per_second", "POLYMARKET_REQUESTS_PER_SECOND"),
        defaults.polymarket_requests_per_second,
    )
    offline = _parse_bool(pick("offline", "OFFLINE"), "OFFLINE", defaults.offline)
    key = pick("anthropic_api_key", "ANTHROPIC_API_KEY")

    return Settings(
        port=port,
        seed=seed,
        polymarket_requests_per_second=rate,
        offline=offline,
        anthropic_api_key=str(key) if key is not None else None,
    )


def _read_env_file(env_file: Path | None) -> dict[str, str | None]:
    if env_file is None or not env_file.is_file():
        return {}
    try:
        # interpolate=False: `${VAR}` would otherwise be filled in from the process
        # environment, which these settings never read (AD-13).
        values = dict(dotenv_values(env_file, interpolate=False, encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        raise SettingsError(
            f"The settings file {env_file} could not be read ({error}). "
            "Save it as plain UTF-8 text."
        ) from None
    unknown = sorted(set(values) - set(ENV_KEYS))
    if unknown:
        log.warning(
            "Ignoring unknown keys in %s: %s. Known keys: %s.",
            env_file,
            ", ".join(unknown),
            ", ".join(ENV_KEYS),
        )
    return values


def _parse_int(value: object, key: str) -> int:
    if isinstance(value, bool):
        raise SettingsError(f"{key} must be a whole number, not {value!r}.")
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except ValueError:
        raise SettingsError(f"{key} must be a whole number, not {value!r}.") from None


def _parse_port(value: object | None, default: int) -> int:
    if value is None:
        return default
    port = _parse_int(value, "PORT")
    if not 1 <= port <= 65535:
        raise SettingsError(f"PORT must be a number from 1 to 65535, not {port}.")
    return port


def _parse_seed(value: object | None, default: int) -> int:
    if value is None:
        return default
    seed = _parse_int(value, "SEED")
    if seed < 0:
        raise SettingsError(f"SEED must be a whole number of 0 or more, not {seed}.")
    return seed


def _parse_rate(value: object | None, default: float) -> float:
    if value is None:
        return default
    try:
        rate = float(str(value))
    except ValueError:
        raise SettingsError(
            f"POLYMARKET_REQUESTS_PER_SECOND must be a number, not {value!r}."
        ) from None
    if not math.isfinite(rate):
        raise SettingsError(
            f"POLYMARKET_REQUESTS_PER_SECOND must be a number, not {value!r}."
        )
    if rate <= 0:
        raise SettingsError(
            f"POLYMARKET_REQUESTS_PER_SECOND must be above 0, not {value}."
        )
    if rate > MAX_REQUESTS_PER_SECOND:
        raise SettingsError(
            f"POLYMARKET_REQUESTS_PER_SECOND is {value}, but at most "
            f"{MAX_REQUESTS_PER_SECOND:g} requests per second are allowed, "
            "to stay polite to Polymarket. Set it to 5 or lower."
        )
    return rate


def _parse_bool(value: object | None, key: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise SettingsError(f"{key} must be true or false, not {value!r}.")
