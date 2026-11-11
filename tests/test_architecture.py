"""Architecture rules checked on the code itself (AD-1, AD-13, AD-17, NFR-7).

The checks parse every module with `ast`; nothing is imported or run.
"""

from __future__ import annotations

import ast
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from pytest_socket import SocketBlockedError

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "liquidoracle"
TESTS = REPO / "tests"

APP = "liquidoracle"

# AD-1: which app layers each layer may import (its own layer is always allowed).
# `settings` is passed down from the shell; core and records never see it (AD-13).
ALLOWED_APP_IMPORTS = {
    "records": set(),
    "core": {"records"},
    "data": {"records", "settings"},
    "services": {"records", "core", "data", "settings"},
    "web": {"records", "services", "settings"},
    "settings": set(),
    "__init__": set(),
    "__main__": {"records", "core", "data", "services", "web", "settings"},  # the shell
}

# AD-1: third-party libraries each layer may import. Anything else is refused.
ALLOWED_THIRD_PARTY = {
    "records": set(),
    "core": {"numpy"},
    "data": {"requests", "anthropic"},
    "services": set(),
    "web": {"flask", "jinja2"},
    "settings": {"dotenv"},
    "__init__": set(),
    "__main__": {"flask"},
}

# AD-1, AD-2, AD-6: standard-library modules that do network or database work. Only `data`
# and the shell (`__main__`) may use them.
IO_LAYERS = {"data", "__main__"}
IO_STDLIB = {
    "socket", "socketserver", "ssl", "http", "urllib", "xmlrpc", "ftplib", "smtplib",
    "imaplib", "poplib", "asyncio", "sqlite3", "dbm", "shelve",
}

# AD-13: only these modules may read the environment or `.env`.
ENV_READERS = {"__main__", "settings"}
ENV_NAMES = {"environ", "environb", "getenv", "getenvb", "putenv"}

REQUIREMENT_ID = re.compile(r"\b(?:FR|AD|NFR|SM)-\d+|\bUX-DR\d+")


def layer_of(rel: Path) -> str:
    """Layer name of a module path relative to src/liquidoracle."""
    first = rel.parts[0]
    return first[:-3] if first.endswith(".py") else first


def package_of(rel: Path) -> list[str]:
    """Dotted package of a module, as a list, for resolving relative imports."""
    parts = [APP, *rel.with_suffix("").parts]
    return parts if rel.name == "__init__.py" else parts[:-1]


def imported_modules(tree: ast.AST, rel: Path) -> list[str]:
    """Every module name a file imports, with relative imports made absolute."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package_of(rel)[: len(package_of(rel)) - node.level + 1]
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            if module == APP:  # `from liquidoracle import core`
                names.extend(f"{APP}.{alias.name}" for alias in node.names)
            else:
                names.append(module)
    return names


def import_violations(rel: Path, source: str) -> list[str]:
    """AD-1 import rule for one module. Returns one message per forbidden import."""
    layer = layer_of(rel)
    if layer not in ALLOWED_APP_IMPORTS:
        return [f"{rel}: unknown layer '{layer}'; add it to the AD-1 rule tables"]
    tree = ast.parse(source, filename=str(rel))
    problems = []
    for module in imported_modules(tree, rel):
        top = module.split(".")[0]
        if top == "__future__":
            continue
        if top == APP:
            parts = module.split(".")
            target = parts[1] if len(parts) > 1 else "__init__"
            if target != layer and target not in ALLOWED_APP_IMPORTS[layer]:
                problems.append(f"{rel}: layer '{layer}' may not import '{module}'")
        elif top in sys.stdlib_module_names:
            if layer not in IO_LAYERS and top in IO_STDLIB:
                problems.append(f"{rel}: layer '{layer}' may not import '{module}' (network or database)")
        elif top not in ALLOWED_THIRD_PARTY[layer]:
            problems.append(f"{rel}: layer '{layer}' may not import the library '{module}'")
    return problems


def env_read_violations(rel: Path, source: str) -> list[str]:
    """AD-13 rule: only __main__ and settings read the environment or `.env`."""
    if layer_of(rel) in ENV_READERS:
        return []
    tree = ast.parse(source, filename=str(rel))
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ENV_NAMES and isinstance(node.value, ast.Name) and node.value.id == "os":
            problems.append(f"{rel}: reads os.{node.attr}")
        elif isinstance(node, ast.ImportFrom) and node.module == "os" and any(a.name in ENV_NAMES for a in node.names):
            problems.append(f"{rel}: imports the environment from os")
        elif isinstance(node, ast.Import) and any(a.name.split(".")[0] == "dotenv" for a in node.names):
            problems.append(f"{rel}: imports dotenv")
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "dotenv":
            problems.append(f"{rel}: imports dotenv")
    return problems


def app_modules() -> list[tuple[Path, str]]:
    return [(p.relative_to(SRC), p.read_text(encoding="utf-8")) for p in sorted(SRC.rglob("*.py"))]


def test_every_layer_exists() -> None:
    """AD-1: the Structural Seed's packages are all present."""
    for name in ("records.py", "settings.py", "__main__.py", "web", "services", "core", "data"):
        assert (SRC / name).exists(), name


def test_app_imports_follow_the_layer_rule() -> None:
    """AD-1: every module of every layer imports only what the layer diagram allows."""
    modules = app_modules()
    assert len(modules) >= 8
    problems = [p for rel, src in modules for p in import_violations(rel, src)]
    assert problems == []


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("core/skilltest.py", "import requests\n"),
        ("core/skilltest.py", "from urllib.request import urlopen\n"),
        ("core/skilltest.py", "import sqlite3\n"),
        ("core/skilltest.py", "from liquidoracle.data import store\n"),
        ("core/skilltest.py", "from ..settings import Settings\n"),
        ("core/skilltest.py", "from liquidoracle import web\n"),
        ("records.py", "from liquidoracle.core import phrases\n"),
        ("data/store.py", "from liquidoracle.services import lookup\n"),
        ("web/routes.py", "from liquidoracle.data import store\n"),
        ("web/routes.py", "import anthropic\n"),
        ("services/lookup.py", "import sqlite3\n"),
        ("web/routes.py", "import socket\n"),
        ("helpers.py", "import json\n"),
    ],
)
def test_planted_forbidden_import_is_caught(path: str, source: str) -> None:
    """AD-1: the rule fails on a planted forbidden import, such as `requests` inside `core`."""
    assert import_violations(Path(path), source) != []


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("core/skilltest.py", "import numpy as np\nfrom liquidoracle.records import Position\n"),
        ("core/skilltest.py", "from . import rng\nfrom ..records import Position\n"),
        ("services/lookup.py", "from liquidoracle.core import skilltest\nfrom liquidoracle.data import store\n"),
        ("web/routes.py", "from flask import Flask\nfrom liquidoracle.services import lookup\n"),
        ("data/store.py", "import sqlite3\nfrom liquidoracle.records import Position\n"),
        ("__main__.py", "import socket\n"),
    ],
)
def test_allowed_imports_pass(path: str, source: str) -> None:
    """AD-1: imports the layer diagram allows are not reported."""
    assert import_violations(Path(path), source) == []


def test_only_main_and_settings_read_the_environment() -> None:
    """AD-13: no code outside __main__ and settings reads os.environ, os.getenv or .env."""
    problems = [p for rel, src in app_modules() for p in env_read_violations(rel, src)]
    assert problems == []


@pytest.mark.parametrize(
    "source",
    ["import os\nkey = os.environ['X']\n", "import os\nos.getenv('X')\n", "from os import environ\n", "from dotenv import dotenv_values\n"],
)
def test_planted_environment_read_is_caught(source: str) -> None:
    """AD-13: the rule fails on a planted environment read outside __main__ and settings."""
    assert env_read_violations(Path("services/lookup.py"), source) != []


@pytest.mark.filterwarnings("ignore:A test tried to use socket")
def test_opening_a_socket_fails() -> None:
    """AD-17: every test runs with sockets blocked, so a test that opens a socket fails."""
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_online_tests_are_deselected_by_default() -> None:
    """AD-17: tests in tests/online/ are marked `online` and do not run unless asked for."""
    command = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests/online"]
    default = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=120)
    assert re.search(r"\b[1-9]\d* deselected", default.stdout), default.stdout + default.stderr
    assert "test_online_marker.py::" not in default.stdout, default.stdout
    chosen = subprocess.run([*command, "-m", "online"], cwd=REPO, capture_output=True, text=True, timeout=120)
    assert "test_online_marker.py::test_online_tests_are_marked" in chosen.stdout, chosen.stdout + chosen.stderr


def test_repetitions_option_sets_the_slow_count(repetitions: int, request: pytest.FixtureRequest) -> None:
    """AD-17: slow checks read their repetition count from one option (default 100)."""
    assert repetitions == request.config.getoption("--repetitions")
    assert repetitions >= 1


def test_repetitions_default_is_100_and_bad_values_are_refused() -> None:
    """AD-17: the repetition count defaults to 100 and must be a whole number of 1 or more."""
    command = [sys.executable, "-m", "pytest", "--help", "-p", "no:cacheprovider"]
    out = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=120).stdout
    assert "(default 100;" in " ".join(out.split()), out
    for bad in ("0", "-1", "abc"):
        refused = subprocess.run(
            [*command[:3], "--collect-only", "-q", "-p", "no:cacheprovider", f"--repetitions={bad}", "tests/online"],
            cwd=REPO, capture_output=True, text=True, timeout=120,
        )
        assert refused.returncode == 4 and "--repetitions" in refused.stderr, refused.stderr


def test_every_test_names_its_requirement() -> None:
    """NFR-7: each test names the FR, AD, NFR, SM or UX-DR it checks in its docstring."""
    missing = []
    for path in sorted(TESTS.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                doc = ast.get_docstring(node) or ""
                if not REQUIREMENT_ID.search(doc):
                    missing.append(f"{path.relative_to(REPO)}::{node.name}")
    assert missing == []
