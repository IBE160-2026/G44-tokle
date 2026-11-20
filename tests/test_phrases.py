"""Number phrases in one place (FR-8, FR-10, UX-DR14, AD-25; Story 1.5).

The FR-8 examples are copied from the PRD and the epics, not computed from the code.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from liquidoracle.core import phrases, skilltest
from liquidoracle.core.positions import build_positions
from liquidoracle.data import synthetic

SRC = Path(__file__).resolve().parents[1] / "src" / "liquidoracle"
SEED = 44  # the Settings default (AD-15), as in test_skilltest.py
FEWER = "fewer than 1 time in 10,000"


@pytest.mark.parametrize(
    ("p_value", "phrase"),
    [
        (0.0033, "about 1 time in 300"),
        (0.0099, "about 1 time in 100"),
        (0.25, "about 1 time in 4"),
        (0.27, "about 1 time in 4"),
        (0.45, "about 1 time in 2"),
        (0.11, "about 1 time in 9"),
    ],
)
def test_fr8_examples_from_the_prd(p_value, phrase):
    """FR-8: N = 1/p to 2 significant figures, a whole number below 10."""
    assert phrases.odds(p_value) == phrase


@pytest.mark.parametrize(
    ("p_value", "phrase"),
    [
        (1 / 10_001, FEWER),  # no Simulation reached the Real PnL
        (0.0001, FEWER),  # N exactly 10,000
        (0.0001004, FEWER),  # N 9,960 would round to 10,000
        (0.000101, "about 1 time in 9,900"),
        (2 / 10_001, "about 1 time in 5,000"),
        (0.0004, "about 1 time in 2,500"),
        (0.00016, "about 1 time in 6,300"),  # N exactly 6,250 in decimals; float division gave 6,249.999…
    ],
)
def test_fr8_floor_and_large_n(p_value, phrase):
    """FR-8: never "about 1 time in 10,000"; large N has comma groups."""
    assert phrases.odds(p_value) == phrase


@pytest.mark.parametrize(
    ("p_value", "phrase"),
    [
        (0.5, "about 1 time in 2"),
        (0.5001, "more than half the time"),
        (1.0, "more than half the time"),
        (0.104, "about 1 time in 10"),  # N 9.6 rounds up to 10
        (0.4, "about 1 time in 3"),  # N exactly 2.5: halves go up, not to the even 2
    ],
)
def test_fr8_half_and_near_ten(p_value, phrase):
    """FR-8: "more than half the time" only above 0.5; decimal rounding takes halves up."""
    assert phrases.odds(p_value) == phrase


def test_fr8_never_shows_a_decimal_or_ten_thousand():
    """FR-8: across every p-value 10,000 Simulations can give, N is a whole number, never 10,000,
    and never grows as p grows (a less rare result never reads as rarer)."""
    previous = 10_001
    for at_or_above in range(10_001):
        phrase = phrases.odds((1 + at_or_above) / 10_001)
        assert "." not in phrase
        assert phrase != "about 1 time in 10,000"
        if phrase.startswith("about 1 time in "):
            n = int(phrase.removeprefix("about 1 time in ").replace(",", ""))
            assert n <= previous
            previous = n


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        (12340, "$12,340"),
        (-1240, "−$1,240"),
        (0, "$0"),
        (0.0, "$0"),
        (-0.0, "$0"),
        (-0.4, "$0"),
        (1650.0, "$1,650"),
        (40180.5, "$40,181"),
        (-0.5, "−$1"),
        (2.5, "$3"),
        (1_234_567.49, "$1,234,567"),
        (np.float64(-25.0), "−$25"),
        (1e30, "$1,000,000,000,000,000,000,000,000,000,000"),  # past decimal's 28 digits, no error
        (-1e28, "−$10,000,000,000,000,000,000,000,000,000"),
    ],
)
def test_ux_dr14_money_in_whole_dollars(amount, text):
    """UX-DR14 (Edvard, 2026-11-18): whole dollars, a real minus sign, never "−$0"."""
    assert phrases.money(amount) == text


def test_ux_dr14_minus_is_the_real_sign():
    """UX-DR14: the sign is U+2212, not a hyphen."""
    assert phrases.money(-1240)[0] == "−"
    assert "-" not in phrases.money(-1240)


@pytest.mark.parametrize(
    ("count", "sentence"),
    [
        (12, "12 resolved bets; at least 30 are needed for a Verdict (18 more)"),
        (1, "1 resolved bet; at least 30 are needed for a Verdict (29 more)"),
        (0, "0 resolved bets; at least 30 are needed for a Verdict (30 more)"),
        (29, "29 resolved bets; at least 30 are needed for a Verdict (1 more)"),
        (np.int64(12), "12 resolved bets; at least 30 are needed for a Verdict (18 more)"),
    ],
)
def test_fr10_not_enough_data(count, sentence):
    """FR-10: the count and how many more are needed."""
    assert phrases.not_enough_data(count) == sentence


@pytest.mark.parametrize(
    "p_value",
    [0, 0.0, -0.01, 1.0001, 2, float("nan"), float("inf"), None, True, "0.01"],
)
def test_fr8_bad_p_value_is_refused(p_value):
    """FR-8: a p-value outside (0, 1], not a number, or a bool is a ValueError."""
    with pytest.raises(ValueError):
        phrases.odds(p_value)


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), float("-inf"), None, True, "12"])
def test_ux_dr14_bad_amount_is_refused(amount):
    """UX-DR14: money that is not a finite number is a ValueError."""
    with pytest.raises(ValueError):
        phrases.money(amount)


@pytest.mark.parametrize("count", [-1, 30, 212, True, 12.0, None, "12"])
def test_fr10_bad_count_is_refused(count):
    """FR-10: the sentence is only for 0 to 29 whole resolved bets."""
    with pytest.raises(ValueError):
        phrases.not_enough_data(count)


def test_ad25_numbers_come_from_the_skill_test():
    """AD-25: the 30 and the 10,000 are the Skill Test's own constants, not typed again."""
    assert phrases.FLOOR_PHRASE == f"fewer than 1 time in {skilltest.SIMULATIONS:,}"
    assert phrases.not_enough_data(0).endswith(f"({skilltest.MIN_RESOLVED} more)")


def test_ad25_story_1_3_wallets_read_as_expected():
    """AD-25, FR-8, FR-10: the Synthetic Wallets' real results phrase end to end with Seed 44.

    The amounts and counts are the hand-written `expected.json` answers (Story 1.3). The odds are
    regression values: they follow from Story 1.4's golden counts (sharp trader 1 -> p 2/10,001).
    """
    read = {}
    for wallet in synthetic.small_wallets():
        position_set = build_positions(wallet.activity, {m.condition_id: m for m in wallet.markets})
        result = skilltest.skill_test(position_set, seed=SEED, unit_id=wallet.address)
        if result.p_value is None:
            read[wallet.name] = phrases.not_enough_data(result.tested_count)
        else:
            read[wallet.name] = phrases.odds(result.p_value)
        read[wallet.name] += " | " + phrases.money(result.real_pnl)
    assert read == {
        "hand-check": "10 resolved bets; at least 30 are needed for a Verdict (20 more) | $500",
        "favourite-buyer": "more than half the time | $0",
        "sharp-trader": "about 1 time in 5,000 | $2,000",
        "thin-wallet": "29 resolved bets; at least 30 are needed for a Verdict (1 more) | $550",
        "stop-loss-trader": f"{FEWER} | $1,650",
    }


# A minus sign counts only before "$", so a formula such as "s·(o − p)" in a docstring is allowed.
PHRASE_MARKERS = (
    "1 time in", "half the time", "needed for a Verdict",
    "−$", "&minus;$", "&#8722;$", "&#x2212;$", "\\u2212$",
)


def phrase_offenders(root: Path) -> list[str]:
    """Files under `root`, other than core/phrases.py, that write a number phrase themselves."""
    home = root / "core" / "phrases.py"
    offenders = []
    for path in sorted(root.rglob("*")):
        if path == home or not path.is_file() or path.suffix not in {".py", ".html", ".js", ".css", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8")
        offenders += [f"{path.relative_to(root).as_posix()}: {m!r}" for m in PHRASE_MARKERS if m in text]
    return offenders


def test_ad25_phrases_live_only_in_core_phrases():
    """AD-25: no other file under src/ writes an odds phrase or a minus sign itself."""
    assert phrase_offenders(SRC) == []


@pytest.mark.parametrize(
    ("planted", "content"),
    [
        ("web/templates/verdict.html", "<p>about 1 time in {{ n }}</p>"),
        ("web/templates/card.html", "<p>&minus;${{ amount }}</p>"),
        ("services/explain.py", 'TEXT = "a trader with no edge would do this well more than half the time"\n'),
        ("core/skilltest.py", 'LOSS = "−$" + amount\n'),
        ("web/templates/loss.html", "<td>&#8722;${{ amount }}</td>"),
        ("web/static/chart.js", "label = n + ' resolved bets; at least 30 are needed for a Verdict';\n"),
    ],
)
def test_ad25_scan_catches_a_planted_phrase(tmp_path, planted, content):
    """AD-25: the scan fails on a phrase written outside core/phrases.py, and not on phrases.py itself."""
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "phrases.py").write_text('MINUS = "−"  # about 1 time in N\n', encoding="utf-8")
    (tmp_path / "core" / "maths.py").write_text('"""Real PnL = Σ s·(o − p) − Own Fees."""\n', encoding="utf-8")
    assert phrase_offenders(tmp_path) == []  # a minus in a formula is not a phrase
    target = tmp_path / planted
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    assert phrase_offenders(tmp_path) != []
    assert all(line.startswith(planted) for line in phrase_offenders(tmp_path))


# --- Story 1.7: the odds sentence, counts and the stored date (UX-DR14, UX-DR20) ----------------


@pytest.mark.parametrize(
    ("p_value", "sentence"),
    [
        (0.25, "a trader with no edge would do this well about 1 time in 4."),
        (1 / 10_001, "a trader with no edge would do this well fewer than 1 time in 10,000."),
        (0.7, "a trader with no edge would do this well more than half the time."),
    ],
)
def test_ux_dr20_odds_sentence(p_value, sentence):
    """UX-DR20, FR-8: the line under the Verdict wraps the FR-8 phrase (EXPERIENCE.md, UJ-1)."""
    assert phrases.odds_sentence(p_value) == sentence


@pytest.mark.parametrize(
    ("number", "digits", "word"),
    [(0, "0", "resolved bets"), (1, "1", "resolved bet"), (212, "212", "resolved bets"), (1000, "1,000", "resolved bets")],
)
def test_ux_dr14_counts(number, digits, word):
    """UX-DR14, UX-DR15: counts have comma groups; one bet is "resolved bet"."""
    assert (phrases.count(number), phrases.resolved_bets_word(number)) == (digits, word)


@pytest.mark.parametrize("number", [-1, 1.5, True, "3", None])
def test_ux_dr14_bad_count_is_refused(number):
    """UX-DR14: a count is a whole number of at least 0."""
    with pytest.raises(ValueError):
        phrases.count(number)
    with pytest.raises(ValueError):
        phrases.resolved_bets_word(number)


def test_fr2_stored_at():
    """FR-2, UX-DR20: "Data stored 15 Oct 2026, 14:02", English month names, no leading zero on the day."""
    from datetime import datetime, timedelta, timezone

    moment = 1_792_065_720  # 2026-10-15 12:02 UTC
    assert phrases.stored_at(moment, timezone.utc) == "Data stored 15 Oct 2026, 12:02"
    assert phrases.stored_at(moment, timezone(timedelta(hours=2))) == "Data stored 15 Oct 2026, 14:02"
    assert phrases.stored_at(1_767_232_800, timezone.utc) == "Data stored 1 Jan 2026, 02:00"
    local = datetime.fromtimestamp(moment).astimezone()  # the computer's own time zone
    assert phrases.stored_at(moment) == phrases.stored_at(moment, local.tzinfo)
