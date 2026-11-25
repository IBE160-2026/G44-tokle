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
from liquidoracle.records import ExclusionReason as R

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
        position_set = build_positions(wallet.activity, {m.condition_id: m for m in wallet.markets}, listed=wallet.positions)
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


def test_ux_dr23_stored_on():
    """UX-DR23 (Story 2.5): the outage button's date, "Show stored data from 15 Oct 2026, 14:02",
    is the same date and time as "Data stored …"."""
    from datetime import timedelta, timezone

    moment = 1_792_065_720  # 2026-10-15 12:02 UTC
    assert phrases.stored_on(moment, timezone(timedelta(hours=2))) == "15 Oct 2026, 14:02"
    assert phrases.stored_at(moment) == f"Data stored {phrases.stored_on(moment)}"
    with pytest.raises(ValueError):
        phrases.stored_on(-1)


# --- Story 3.1: the luck chart's words (FR-9, UX-DR24, UX-DR25) ---------------------------------


@pytest.mark.parametrize(
    ("amount", "full", "short"),
    [
        (0.0, "$0", "$0"),
        (-0.0, "$0", "$0"),
        (500.0, "$500", "$500"),
        (-1500.0, "−$1,500", "−$1.5k"),
        (200_000.0, "$200,000", "$200k"),
        (-12_500.0, "−$12,500", "−$12.5k"),
        (1_250.0, "$1,250", "$1.25k"),
        (2_500_000.0, "$2,500,000", "$2.5M"),
        (1.25, "$1.25", "$1.25"),
        (-0.2, "−$0.20", "−$0.20"),
    ],
)
def test_ux_dr25_axis_money(amount, full, short):
    """UX-DR25: axis amounts in whole dollars, short below 640 px ("−$100k"); cents kept only off whole dollars."""
    assert phrases.axis_money(amount) == full
    assert phrases.axis_money(amount, short=True) == short


def test_ux_dr25_end_bar_and_marker_labels():
    """UX-DR25, FR-9: "−$200,000 or less", "$200,000 or more", "This Wallet: $40,180" and the beyond lines."""
    assert phrases.end_bar_label(-200_000.0, above=False) == "−$200,000 or less"
    assert phrases.end_bar_label(200_000.0, above=True, short=True) == "$200k or more"
    assert phrases.marker_label(40_180.4) == "This Wallet: $40,180"
    assert phrases.marker_label(-1_240.0) == "This Wallet: −$1,240"
    assert phrases.beyond_all(above=True) == "above all 10,000 Simulations"
    assert phrases.beyond_all(above=False) == "below all 10,000 Simulations"


def test_prd8_chart_text_alternative():
    """PRD §8, UX-DR24: the example from EXPERIENCE.md, word for word."""
    assert phrases.chart_text(40_180.0, 212, 0.25) == (
        "This Wallet made $40,180 on 212 resolved bets. "
        "In 10,000 replays with no edge, a result this good came up about 1 time in 4."
    )
    assert phrases.chart_text(-226.0, 100, 0.7).startswith("This Wallet made −$226 on 100 resolved bets.")


def test_ux_dr24_chart_text_says_below_all_only_when_asked():
    """UX-DR24 (Edvard, 2026-11-25, Story 3.5): below every Simulation the text adds "That is below all 10,000
    replays."; above all and inside the curve it adds nothing (the odds phrase carries "above all")."""
    below = phrases.chart_text(-2_970.0, 30, 1.0, below_all=True)
    assert below == (
        "This Wallet made −$2,970 on 30 resolved bets. "
        "In 10,000 replays with no edge, a result this good came up more than half the time. "
        "That is below all 10,000 replays."
    )
    assert "below all" not in phrases.chart_text(2_970.0, 30, 1 / 10_001)  # above all
    assert "below all" not in phrases.chart_text(40_180.0, 212, 0.25)  # inside the curve


def test_ux_dr24_about_this_chart():
    """UX-DR24 (Edvard, 2026-11-23): three paragraphs; the average is $0, or minus the fees when they round to a dollar."""
    first, second, third = phrases.about_chart(212, 0.0)
    assert first.startswith("Each replay (a Simulation) keeps this Wallet's 212 resolved bets, prices and stakes")
    assert second == "The bars count how many of the 10,000 replays ended at each result. On average, luck alone lands at $0."
    assert third.startswith('The blue line labelled "This Wallet" is this Wallet\'s Real PnL: what it made on the 212 bets')
    assert "arrow keys" not in " ".join((first, second, third))  # Story 3.2 adds how to explore
    assert phrases.about_chart(212, 0.4)[1].endswith("lands at $0.")
    assert phrases.about_chart(212, 1_087.34)[1].endswith(
        "On average, luck alone lands at −$1,087, what this Wallet paid in fees."
    )


# --- Story 3.2: exploring the chart (UX-DR26, UX-DR27) ------------------------------------------


def test_ux_dr26_bar_range_and_replay_count():
    """UX-DR26: the slider's spoken example "$30,000 to $35,000: 289 replays"; end bars read as their labels."""
    assert f"{phrases.bar_range(30_000.0, 35_000.0)}: {phrases.replays(289)}" == "$30,000 to $35,000: 289 replays"
    assert phrases.bar_range(-5_000.0, 0.0) == "−$5,000 to $0"
    assert phrases.bar_range(1.25, 1.5) == "$1.25 to $1.50"
    assert phrases.bar_range(None, -195_000.0) == "−$195,000 or less"
    assert phrases.bar_range(195_000.0, None) == "$195,000 or more"
    assert (phrases.replays(0), phrases.replays(1), phrases.replays(10_000)) == ("0 replays", "1 replay", "10,000 replays")
    with pytest.raises(ValueError):
        phrases.bar_range(None, None)


@pytest.mark.parametrize(
    ("at_or_above", "sentence"),
    [
        (2_500, "2,500 of 10,000 replays did this well or better"),
        (1, "1 of 10,000 replays did this well or better"),
        (0, "No replay did this well or better"),
        (10_000, "All 10,000 replays did this well or better"),
    ],
)
def test_ux_dr27_tail_sentence(at_or_above, sentence):
    """UX-DR27: the tail label from the exact count, with its two edge sentences."""
    assert phrases.tail_sentence(at_or_above) == sentence


@pytest.mark.parametrize("bad", [-1, 10_001])
def test_ux_dr27_tail_sentence_refuses_impossible_counts(bad):
    """UX-DR27: a count outside 0 to 10,000 is a bug upstream, not a sentence."""
    with pytest.raises(ValueError):
        phrases.tail_sentence(bad)


# --- Story 3.3: the honesty notes (FR-11) ---------------------------------------------------------


@pytest.mark.parametrize(
    ("fraction", "text"),
    [(0.7, "70%"), (0.325, "33%"), (0.996, "99%"), (1.0, "100%"), (0.004, "less than 1%"), (0.0, "0%"), (0.005, "1%"),
     (0.285, "29%"), (0.145, "15%"), (0.565, "57%")],  # halves whose float x 100 falls just short (Story 3.3 review)
)
def test_fr11_share_in_whole_percent(fraction, text):
    """FR-11 (Story 3.3): whole percent, half up; never "100%" below all of it, never "0%" above none."""
    assert phrases.share(fraction) == text


@pytest.mark.parametrize(
    ("real_pnl", "largest", "parts"),
    [
        (2_000.0, 1_400.0, ("", "70%", "of the Real PnL came from the single largest bet.")),
        (295.06, 293.95, ("", "99%", "of the Real PnL came from the single largest bet.")),
        (100_000.0, 300.0, ("", "Less than 1%", "of the Real PnL came from the single largest bet.")),
        (8.0, 87.0, ("", "$87", "More than all of the Real PnL came from the single largest bet ($87); "
                                  "the other bets lost money overall.")),
        (-226.0, 90.0, ("Largest single bet:", "$90", "")),
        (0.0, 3_200.0, ("Largest single bet:", "$3,200", "")),
        (-1e-15, 10.0, ("Largest single bet:", "$10", "")),  # float noise is $0 in whole cents (favourite-buyer)
        (-500.0, -12.0, ("Largest single bet:", "−$12", "")),
        (-1_102.66, 0.01, ("Largest single bet:", "a gain of less than $1", "")),  # 0x94884d's best bet made 1 cent
        (0.0, None, ("", "", "No resolved bets to measure.")),
        # Story 3.3 review: a Real PnL the card shows as $0 takes the amount form; a share over 100% only by a
        # fraction of a cent is 100%; the over-100% amount never reads "$0".
        (0.30, 0.45, ("Largest single bet:", "a gain of less than $1", "")),
        (50.0, 50.004, ("", "100%", "of the Real PnL came from the single largest bet.")),
        (0.80, 1.20, ("", "$1", "More than all of the Real PnL came from the single largest bet ($1); "
                                "the other bets lost money overall.")),
    ],
)
def test_fr11_largest_bet_and_its_edge_cases(real_pnl, largest, parts):
    """FR-11, EXPERIENCE.md Voice and Tone: the share, the amount at $0 or below, the over-100% sentence, no bets."""
    assert phrases.largest_bet(real_pnl, largest) == parts


def test_fr11_held_count_and_exit_pnl():
    """FR-11 (Edvard, 2026-11-24): "N of M positions held to resolution" and the Exit PnL line, with their edge cases."""
    assert phrases.held(33, 100) == ("33 of 100", "positions held to resolution.")
    assert phrases.held(939, 1_173) == ("939 of 1,173", "positions held to resolution.")
    assert phrases.held(0, 0) == ("", "No bet's history was read in full, so this cannot be counted.")
    with pytest.raises(ValueError):
        phrases.held(5, 4)
    assert phrases.exit_line(-1_675.0, any_sold=True) == "Shares sold before resolution: −$1,675 (Exit PnL)."
    assert phrases.exit_line(0.0, any_sold=False) == "No shares were sold before resolution."
    assert phrases.exit_line(0.0, any_sold=True) == "Shares sold before resolution: $0 (Exit PnL)."
    assert phrases.exit_line(-0.4, any_sold=True) == "Shares sold before resolution: a loss of less than $1 (Exit PnL)."
    assert phrases.exit_line(0.4, any_sold=True) == "Shares sold before resolution: a gain of less than $1 (Exit PnL)."


@pytest.mark.parametrize(("exit_pnl", "warns"), [(-1_675.0, True), (-0.01, True), (-0.004, False), (0.0, False), (5.0, False)])
def test_fr11_exit_warning_only_below_zero_in_cents(exit_pnl, warns):
    """FR-11: the warning shows when Exit PnL is below zero; float noise under half a cent is not a loss."""
    assert phrases.exit_warning_applies(exit_pnl) is warns


def test_fr11_left_out_line_fees_and_plain_sentences():
    """FR-11, UX-DR29: reasons in the builder's order with counts above 0, the fee line, the 10% and 20% sentences."""
    counts = {R.SOLD_BEFORE_RESOLUTION: 95, R.SPLIT_OR_MERGED: 287, R.UNCLEAR_RESOLUTION: 5, R.SHARE_GAP: 6,
              R.NOT_EXPLAINED: 0}
    assert phrases.left_out(counts) == (
        "Left out of the test: 5 unclear resolution, 287 split or merged, 6 Polymarket's two lists disagree, "
        "95 sold before resolution."
    )
    assert phrases.left_out({r: 0 for r in R}) == "Left out of the test: none."
    assert phrases.left_out({R.NOT_FULLY_READ: 2_000, R.ONLY_IN_ACTIVITY: 1}) == (
        "Left out of the test: 2,000 not fully read, 1 missing from Polymarket's positions list."
    )
    assert phrases.fees_not_counted(0, 0.0) == "Every fee matched the Market's fee schedule."
    assert phrases.fees_not_counted(3, 0.4) == (
        "3 fees did not match the Market's fee schedule and were not counted (less than $1)."
    )
    assert phrases.fees_not_counted(1, 44.48) == "1 fee did not match the Market's fee schedule and was not counted ($44)."
    assert phrases.mostly_left_out_sentence(0.335) == (
        "Only part of this Wallet's activity was judged: 34% of its bets were left out."
    )
    assert phrases.linked_bets_note(0.34).startswith("34% of the tested bets share an event with another tested bet")


def test_fr11_window_and_computed_on_lines():
    """FR-11, AD-22 (Edvard, 2026-11-24): the window line has no total; "Computed on … · Seed 44" names the set."""
    assert phrases.window_line(2_000) == "Based on the latest 2,000 bets; older results are not included."
    assert phrases.computed_on("lookup", 2_000, capped=True, seed=44) == "Computed on the latest 2,000 bets · Seed 44"
    assert phrases.computed_on("lookup", 1_173, capped=False, seed=44) == "Computed on all 1,173 bets · Seed 44"
    assert phrases.computed_on("lookup", 1, capped=False, seed=7) == "Computed on 1 bet · Seed 7"
    assert phrases.computed_on("lookup", 0, capped=False, seed=44) == "Computed on no bets · Seed 44"
    with pytest.raises(ValueError):
        phrases.computed_on("scan_whole", 10, capped=False, seed=44)
