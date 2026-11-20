"""Banned and avoided words (NFR-8, UX-DR15, FR-24; Story 1.7).

The word lists are copied from EXPERIENCE.md › Voice and Tone. The scan reads every template and
every fixed text in Python code the user can read: string constants in `web`, `services` and
`core/phrases.py` and `records.py` (the Verdict labels), docstrings and comments left out.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "liquidoracle"

BANNED = ("guaranteed", "insider", "will win")  # PRD §8, FR-24
AVOIDED = (
    "copy this", "follow", "recommended", "winner", "best", "top", "safe", "proven",
    "sure thing", "beat the market", "genius", "smart money",
)
ALLOWED = ("top Wallets by profit",)  # the factual Scan definition (EXPERIENCE.md)
WORDS = re.compile(r"\b(" + "|".join(re.escape(w) for w in BANNED + AVOIDED) + r")\b", re.IGNORECASE)


def fixed_texts(root: Path) -> list[tuple[str, str]]:
    """(where, text) for every template and every user-facing string constant under `root`."""
    found: list[tuple[str, str]] = []
    for path in sorted((root / "web" / "templates").rglob("*.html")):
        found.append((path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")))
    modules = [*sorted((root / "web").rglob("*.py")), *sorted((root / "services").rglob("*.py"))]
    modules += [root / "core" / "phrases.py", root / "records.py"]  # records: the Verdict labels on the hero
    for path in modules:
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                found.append((f"{path.relative_to(root).as_posix()}:{node.lineno}", node.value))
    return found


def offenders(root: Path) -> list[str]:
    result = []
    for where, content in fixed_texts(root):
        for allowed in ALLOWED:
            content = content.replace(allowed, "")
        result += [f"{where}: {m.group(0)!r}" for m in WORDS.finditer(content)]
    return result


def test_nfr8_no_banned_or_avoided_words() -> None:
    """NFR-8, UX-DR15: no template or fixed text says a banned or avoided word."""
    assert fixed_texts(SRC), "the scan found nothing to read"
    assert offenders(SRC) == []


@pytest.mark.parametrize(
    ("planted", "content"),
    [
        ("web/templates/verdict.html", "<p>This Wallet is the BEST.</p>"),
        ("web/templates/x.html", "<p>A sure thing.</p>"),
        ("services/lookup.py", 'NOTE = "Follow this Wallet"\n'),
        ("core/phrases.py", 'X = "profits are guaranteed"\n'),
        ("web/__init__.py", 'TITLE = f"{n} will win"\n'),
    ],
)
def test_nfr8_scan_catches_a_planted_word(tmp_path: Path, planted: str, content: str) -> None:
    """NFR-8: the scan fails on a planted word, and not on docstrings, the Scan definition or "Follower PnL"."""
    for folder in ("web/templates", "services", "core"):
        (tmp_path / folder).mkdir(parents=True)
    (tmp_path / "services" / "ok.py").write_text(
        '"""It is safe to share between threads."""\nA = "top Wallets by profit"\nB = "Follower PnL"\n', encoding="utf-8"
    )
    assert offenders(tmp_path) == []
    (tmp_path / planted).write_text(content, encoding="utf-8")
    assert len(offenders(tmp_path)) == 1
