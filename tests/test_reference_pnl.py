"""Real PnL on three real Sample Wallets against references made without the app's code (FR-4, Story 2.7).

Where each reference number came from:

- 0x29306d: a fresh AI helper's step-by-step calculation, given only the PRD and the Wallet's file
  (`tests/reference/0x29306d-*`, committed in e85f083 before this test existed). It replaces
  Edvard's own spreadsheet (his decision, 2026-11-23).
- 0x0f4b0a and 0x091596: one separate script, `tests/reference/real_pnl_reference.py`, written by
  a second fresh AI helper from the PRD and a note on the data fields alone, committed with its
  output before this test existed. The note, `tests/reference/fields.md`, was written by the main
  Claude Code session from the data files and says only what each field is (Edvard's condition).
- Story 2.8 (FR-4 changed on 2026-11-23): a third fresh AI helper changed only the script's fee check to the new
  FR-4 sentence (a fee also passes at any whole-percent rate from 1% to 10%), given the script, its notes,
  `fields.md`, the two Wallet files and FR-4 as committed in b959f44, never the app's code; its new CSVs and the
  top section of `script-notes.md` were committed before the app's fee check changed.

The helpers' notes name the paths of their own scratch folders. In the repository, a script is
re-run as `python -I -S tests/reference/<script> sample_data/real/<address>.json ... <out_dir>`;
it writes `<first 8 characters>-real-pnl.csv` (and, for `real_pnl_reference.py`, `-fee-check.csv`).

If a value differs, the cause (app, script or helper) is found and logged in the spec of the story that changed it (2.7, 2.8);
a reference is never changed to match the app without a written reason.
"""

from __future__ import annotations

import ast
import csv
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from liquidoracle.core.positions import build_positions
from liquidoracle.data.offline import OfflineClient
from liquidoracle.data.store import Store
from liquidoracle.records import SkillTestResult
from liquidoracle.data.window import positions_near
from liquidoracle.services.fetch import fetch_wallet, stored_result

REPO = Path(__file__).resolve().parents[1]
REAL = REPO / "sample_data" / "real"
REFERENCE = REPO / "tests" / "reference"
SEED = 44

HELPER = "fresh AI helper's calculation (tests/reference/0x29306d-calc.py)"
SCRIPT = "independent script (tests/reference/real_pnl_reference.py)"

# Wallet address -> where its reference value came from.
SOURCES = {
    "0x29306ddc4724e24a23bf1c8679aa034376ea9dcb": HELPER,
    "0x0f4b0a6b7f82108924ac9c8320ed91028f504183": SCRIPT,
    "0x0915962b4c6bc4505e7434a0de815a596a6667c3": SCRIPT,
}

# Each reference script, the Wallets it was run on (in the order it takes them) and the
# files it writes per Wallet.
SCRIPTS = {
    "0x29306d-calc.py": (["0x29306ddc4724e24a23bf1c8679aa034376ea9dcb"], ["real-pnl"]),
    "real_pnl_reference.py": (
        ["0x0f4b0a6b7f82108924ac9c8320ed91028f504183", "0x0915962b4c6bc4505e7434a0de815a596a6667c3"],
        ["real-pnl", "fee-check"],
    ),
}


def reference_csv(address: str) -> Path:
    return REFERENCE / f"{address[:8]}-real-pnl.csv"


def reference_total(address: str) -> dict[str, str]:
    """The reference's TOTAL row: Real PnL and Own Fees rounded to the cent by whoever made it,
    and `resolved=..;sliver=..;left_out=..` in `reason`."""
    with reference_csv(address).open(encoding="utf-8", newline="") as f:
        rows = [row for row in csv.DictReader(f) if row["condition_id"] == "TOTAL"]
    assert len(rows) == 1, f"{reference_csv(address).name} must have exactly one TOTAL row"
    return rows[0]


def counts(total: dict[str, str]) -> dict[str, int]:
    return {key: int(value) for key, value in (part.split("=") for part in total["reason"].split(";"))}


def reference_failed_fees(address: str) -> int:
    """FR-4: fee-check rows marked FAILED on the reference's Resolved Positions and Slivers (0 without a fee file)."""
    fee_file = REFERENCE / f"{address[:8]}-fee-check.csv"
    if not fee_file.exists():
        return 0
    with reference_csv(address).open(encoding="utf-8", newline="") as f:
        counted = {(r["condition_id"], r["token_id"]) for r in csv.DictReader(f) if r["status"] in ("resolved", "sliver")}
    with fee_file.open(encoding="utf-8", newline="") as f:
        return sum(1 for r in csv.DictReader(f)
                   if r["result"].startswith("FAILED") and (r["condition_id"], r["token_id"]) in counted)


def app_failed_fees(address: str) -> int:
    """The app's failed-fee count on counted Positions; the stored result does not carry it yet (Epic 3)."""
    window = positions_near(OfflineClient([REAL / f"{address}.json"]), address)
    built = build_positions(window.activity, {m.condition_id: m for m in window.markets}, listed=window.positions,
                            not_fully_read=window.not_fully_read())
    return built.failed_fee_count


def cents(value: float) -> Decimal:
    return Decimal(repr(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def app_result(address: str, tmp_path: Path) -> SkillTestResult:
    """The app's Skill Test result, loaded offline exactly as `load-sample` and a lookup do."""
    store = Store(tmp_path / "offline.db")
    try:
        fetch_wallet(OfflineClient([REAL / f"{address}.json"]), store, address)
        result = stored_result(store, address, seed=SEED)
    finally:
        store.close()
    assert result is not None
    return result.result


def stdlib_violations(name: str, source: str) -> list[str]:
    """Every import in a reference script that is not the standard library, `liquidoracle` above all."""
    problems = []
    for node in ast.walk(ast.parse(source, filename=name)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = ["." * node.level + (node.module or "")]
        else:
            continue
        for module in modules:
            top = module.split(".")[0]
            if top != "__future__" and top not in sys.stdlib_module_names:
                problems.append(f"{name}: imports '{module}'")
    return problems


@pytest.mark.parametrize("address", sorted(SOURCES))
def test_app_real_pnl_equals_the_independent_reference_to_the_cent(address: str, tmp_path: Path) -> None:
    """FR-4: the app's Real PnL equals the reference made without the app's code, to the cent."""
    expected = Decimal(reference_total(address)["pnl_contribution"])
    got = cents(app_result(address, tmp_path).real_pnl)
    assert got == expected, f"{address}: app {got} vs {expected} from the {SOURCES[address]}"


@pytest.mark.parametrize("address", sorted(SOURCES))
def test_app_counts_and_own_fees_equal_the_independent_reference(address: str, tmp_path: Path) -> None:
    """FR-3, FR-4: the app tests as many Resolved Positions and Slivers, and counts the same Own Fees
    to the cent, and fails as many fees on them (0 since Story 2.8), as the reference, so errors in the total
    cannot cancel out unseen."""
    total = reference_total(address)
    result = app_result(address, tmp_path)
    expected = (counts(total)["resolved"], counts(total)["sliver"], Decimal(total["own_fees"] or "0"),
                reference_failed_fees(address))
    got = (result.tested_count, result.sliver_count, cents(result.own_fees), app_failed_fees(address))
    assert got == expected, f"{address}: app {got} vs {expected} from the {SOURCES[address]}"


def test_one_of_the_three_paid_fees() -> None:
    """FR-4: at least one of the three Wallets paid trading fees, and its reference subtracts them."""
    assert any(Decimal(reference_total(address)["own_fees"] or "0") > 0 for address in SOURCES)


def test_every_reference_script_imports_only_the_standard_library() -> None:
    """FR-4, Story 2.7: no reference script imports `liquidoracle` or any library outside Python itself."""
    scripts = sorted(REFERENCE.glob("*.py"))
    assert {p.name for p in scripts} == set(SCRIPTS)
    problems = [p for path in scripts for p in stdlib_violations(path.name, path.read_text(encoding="utf-8"))]
    assert problems == []


@pytest.mark.parametrize(
    "source",
    [
        "import liquidoracle\n",
        "from liquidoracle.core import skilltest\n",
        "from liquidoracle import records\n",
        "import numpy as np\n",
        "from . import helpers\n",
    ],
)
def test_planted_app_import_in_a_reference_script_is_caught(source: str) -> None:
    """FR-4, Story 2.7: the rule fails on a planted import of the app, a library or a sibling file."""
    assert stdlib_violations("planted.py", "import json\n" + source) != []


@pytest.mark.parametrize("script", sorted(SCRIPTS))
def test_rerunning_a_reference_script_gives_the_committed_csv(script: str, tmp_path: Path) -> None:
    """FR-4, Story 2.7: each committed reference CSV is exactly what its script writes, never hand-edited.
    `-S` leaves out site-packages, where the app is installed, so the script cannot load the app
    even indirectly. Compared line by line, since git may change line endings on checkout."""
    addresses, kinds = SCRIPTS[script]
    wallets = [str(REAL / f"{address}.json") for address in addresses]
    subprocess.run(
        [sys.executable, "-I", "-S", str(REFERENCE / script), *wallets, str(tmp_path)],
        check=True, capture_output=True, text=True, timeout=120,
    )
    for address in addresses:
        for kind in kinds:
            name = f"{address[:8]}-{kind}.csv"
            written = (tmp_path / name).read_text(encoding="utf-8").splitlines()
            assert written == (REFERENCE / name).read_text(encoding="utf-8").splitlines(), name


def test_the_app_cannot_be_imported_where_the_scripts_run() -> None:
    """FR-4, Story 2.7: the interpreter flags the re-run uses really cannot import `liquidoracle`."""
    run = subprocess.run([sys.executable, "-I", "-S", "-c", "import liquidoracle"],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode != 0 and "liquidoracle" in run.stderr
