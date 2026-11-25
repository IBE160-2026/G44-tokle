"""The number phrases the user reads, in one place (AD-25, UX-DR14; Story 1.5).

Templates, the FR-24 check and the tests all call these functions, so the Verdict card, the
chart text and the Explanation can never phrase the same number two ways. Story 1.5 adds the
odds phrase, money and the *Not enough data* sentence; Story 1.7 the odds sentence, counts and the
"Data stored" date; later stories add theirs here (Copy Test
phrase, Minimum Luck Passes, Follower Return, the largest-bet sentence). A test fails if an odds
phrase, the *Not enough data* sentence or a minus-sign amount is written elsewhere under `src/`.
No scan can spot every hand-made money format, so pages must call `money()`.

Rounding is decimal and takes halves away from zero, never Python's round-half-to-even.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timezone, tzinfo
from decimal import ROUND_HALF_UP, Decimal
from numbers import Integral, Real

from liquidoracle.core.skilltest import MIN_RESOLVED, SIMULATIONS
from liquidoracle.records import ExclusionReason

MINUS = "−"  # UX-DR14: a real minus sign, not the hyphen "-"

FLOOR_PHRASE = f"fewer than 1 time in {SIMULATIONS:,}"  # FR-8: 10,000 Simulations cannot show less
MORE_THAN_HALF_PHRASE = "more than half the time"  # FR-8: p above 0.5

_ONE = Decimal(1)


def odds(p_value: float) -> str:
    """The p-value in plain words (FR-8): "about 1 time in 300".

    N = 1/p, to 2 significant figures, and to a whole number below 10, so never a decimal.
    "fewer than 1 time in 10,000" when no Simulation reached the Real PnL (p = 1/10,001) and
    whenever N would round to 10,000 or more, so "about 1 time in 10,000" never appears.
    "more than half the time" above 0.5. The p-value is taken as given, so a Domain Verdict can
    pass its Bonferroni-adjusted p (FR-20).
    """
    p = _real(p_value, "p-value")
    if not 0.0 < p <= 1.0:
        raise ValueError(f"a p-value must be above 0 and at most 1, got {p_value!r}")
    if p > 0.5:
        return MORE_THAN_HALF_PHRASE
    if p <= 1.0 / (SIMULATIONS + 1):
        return FLOOR_PHRASE
    n = _ONE / Decimal(repr(p))  # decimal division: 1/0.00016 is 6,250 exactly, not 6,249.999…
    if n < 10:
        rounded = n.quantize(_ONE, rounding=ROUND_HALF_UP)
    else:
        step = _ONE.scaleb(n.adjusted() - 1)  # 2 significant figures: 303 -> step 10
        rounded = (n / step).quantize(_ONE, rounding=ROUND_HALF_UP) * step
    if rounded >= SIMULATIONS:
        return FLOOR_PHRASE
    return f"about 1 time in {int(rounded):,}"


def money(amount: float) -> str:
    """USD in whole dollars (UX-DR14; Edvard, 2026-11-18): "$12,340", "−$1,240", never "−$0".

    Only the display rounds; stored and tested amounts stay exact to the cent (Conventions › Money).
    """
    value = _real(amount, "amount")
    dollars = int(Decimal(repr(value)).to_integral_value(rounding=ROUND_HALF_UP))  # no 28-digit limit
    sign = MINUS if dollars < 0 else ""
    return f"{sign}${abs(dollars):,}"


def not_enough_data(tested_count: int) -> str:
    """The *Not enough data* sentence (FR-10): "12 resolved bets; at least 30 are needed for a Verdict (18 more)"."""
    if isinstance(tested_count, bool) or not isinstance(tested_count, Integral):
        raise ValueError(f"a count must be a whole number, got {tested_count!r}")
    count = int(tested_count)
    if not 0 <= count < MIN_RESOLVED:
        raise ValueError(f"Not enough data needs 0 to {MIN_RESOLVED - 1} resolved bets, got {count}")
    bets = "bet" if count == 1 else "bets"
    return f"{count} resolved {bets}; at least {MIN_RESOLVED} are needed for a Verdict ({MIN_RESOLVED - count} more)"


def odds_sentence(p_value: float) -> str:
    """The odds line under the Verdict (UX-DR20), ending in a full stop: a trader with no edge would do this well about 1 time in 4."""
    return f"a trader with no edge would do this well {odds(p_value)}."


def count(number: int) -> str:
    """A whole count with comma groups (UX-DR14): "1,000"."""
    return f"{_whole(number, 'count'):,}"


def resolved_bets_word(number: int) -> str:
    """The words after a count of Resolved Positions (UX-DR15): "resolved bet" for 1, else "resolved bets"."""
    return "resolved bet" if _whole(number, "count") == 1 else "resolved bets"


# --- Story 3.1: the luck chart's words (FR-9, UX-DR24, UX-DR25) --------------------------------

CHART_TITLE_NOTE = f"({SIMULATIONS:,} replays with no edge)"  # after "Simulated results" (UX-DR24)

_CENT = Decimal("0.01")


def axis_money(amount: float, *, short: bool = False) -> str:
    """An amount on the chart's dollar axis (UX-DR25): "$50,000", or short "$50k" / "$1.25M".

    Whole dollars like `money()`; an edge that is not a whole dollar (a tiny Wallet's axis) keeps
    its cents, "$12.50", so two ticks never read the same.
    """
    cents = Decimal(repr(_real(amount, "amount"))).quantize(_CENT, rounding=ROUND_HALF_UP)
    if cents == 0:
        return "$0"
    sign = MINUS if cents < 0 else ""
    size = abs(cents)
    if size != size.to_integral_value():
        return f"{sign}${size:,.2f}"
    if short and size >= 1_000:
        scaled, unit = (size / 1_000_000, "M") if size >= 1_000_000 else (size / 1_000, "k")
        digits = f"{scaled:.2f}".rstrip("0").rstrip(".")
        return f"{sign}${digits}{unit}"
    return f"{sign}${int(size):,}"


def end_bar_label(edge: float, *, above: bool, short: bool = False) -> str:
    """An end bar's label (UX-DR25): "−$200,000 or less" for the low one, "$200,000 or more" for the high one."""
    return f"{axis_money(edge, short=short)} {'or more' if above else 'or less'}"


def marker_label(real_pnl: float) -> str:
    """The Wallet marker's label (UX-DR25): "This Wallet: $40,180"."""
    return f"This Wallet: {money(real_pnl)}"


def beyond_all(*, above: bool) -> str:
    """The marker's second line when the Real PnL is beyond every Simulation (FR-9): "above all 10,000 Simulations"."""
    return f"{'above' if above else 'below'} all {SIMULATIONS:,} Simulations"


def chart_text(real_pnl: float, tested_count: int, p_value: float, *, below_all: bool = False) -> str:
    """The chart's always-visible text alternative (PRD §8, UX-DR24).

    `below_all`: the Real PnL is below every Simulation. The marker's "below all 10,000 Simulations"
    sits in the drawing, hidden from screen readers, and the odds phrase then only says "more than
    half the time", so the text adds "That is below all 10,000 replays." (Edvard, 2026-11-25, Story 3.5).
    "Above all" needs no sentence: its odds phrase, "fewer than 1 time in 10,000", already says it.
    """
    text = (
        f"This Wallet made {money(real_pnl)} on {count(tested_count)} {resolved_bets_word(tested_count)}. "
        f"In {SIMULATIONS:,} replays with no edge, a result this good came up {odds(p_value)}."
    )
    return f"{text} That is below all {SIMULATIONS:,} replays." if below_all else text


def about_chart(tested_count: int, own_fees: float) -> tuple[str, str, str]:
    """The three paragraphs of "About this chart" (UX-DR24; wording approved by Edvard, 2026-11-23).

    Only what is true without JavaScript; Story 3.2 adds how to point at the bars. A replay's
    average is the Real PnL's luck-free value, $0 less the Own Fees (they lower every replay).
    """
    bets = f"{count(tested_count)} {resolved_bets_word(tested_count)}"
    average = money(-own_fees)
    landing = (
        "On average, luck alone lands at $0."
        if average == "$0"
        else f"On average, luck alone lands at {average}, what this Wallet paid in fees."
    )
    return (
        f"Each replay (a Simulation) keeps this Wallet's {bets}, prices and stakes, but lets every bet win "
        "or lose by chance, at the odds its price implied. That is one way a trader with no edge could have done.",
        f"The bars count how many of the {SIMULATIONS:,} replays ended at each result. {landing}",
        "The blue line labelled \"This Wallet\" is this Wallet's Real PnL: what it made on the "
        f"{count(tested_count)} bets it held to resolution. The more of the curve lies to its left, "
        "the harder the result is to explain by luck.",
    )


# --- Story 3.2: exploring the chart (UX-DR26, UX-DR27) -----------------------------------------


def bar_range(low: float | None, high: float | None) -> str:
    """A bar's range in the tooltip and the slider (UX-DR26): "$30,000 to $35,000"; an end bar reads as its label."""
    if low is None and high is not None:
        return end_bar_label(high, above=False)
    if high is None and low is not None:
        return end_bar_label(low, above=True)
    if low is None or high is None:
        raise ValueError("a bar needs at least one edge")
    return f"{axis_money(low)} to {axis_money(high)}"


def replays(number: int) -> str:
    """A count of replays (UX-DR26): "1 replay", "289 replays"."""
    whole = _whole(number, "count")
    return f"{count(whole)} {'replay' if whole == 1 else 'replays'}"


def tail_sentence(at_or_above: int) -> str:
    """The tail label (UX-DR27) from the exact count of Simulations at or above the Real PnL, never from the bars."""
    reached = _whole(at_or_above, "at_or_above")
    if not 0 <= reached <= SIMULATIONS:
        raise ValueError(f"at_or_above must be 0 to {SIMULATIONS:,}, got {reached}")
    if reached == 0:
        return "No replay did this well or better"
    if reached == SIMULATIONS:
        return f"All {SIMULATIONS:,} replays did this well or better"
    return f"{count(reached)} of {SIMULATIONS:,} replays did this well or better"


# --- Story 3.3: the honesty notes (FR-11, UX-DR15, UX-DR29) ------------------------------------

HONESTY_TITLE = "What this test can't see"
EXIT_WARNING = (  # FR-11, word for word: a bold first sentence, a normal second one (UX-DR15)
    "Positions this Wallet sold before resolution lost money in total.",
    "This Verdict covers only bets held to resolution.",
)
LIMITS_TEXT = (  # FR-11's fixed note, word for word from mockups/verdict.html
    "Long shots tend to be overpriced, so a Wallet that mostly buys favourites can beat the odds from that known "
    "pattern alone. The Verdict covers only bets held to resolution, so early exits are not measured and can make "
    "a Wallet look better or worse than it is. Wallets are often looked up because they already looked good, and "
    "picking by results makes luck look more like skill."
)
NOT_ADVICE = "This is not financial advice."
LEFT_OUT_LABEL = "Left out of the test:"

# The reasons as the card names them (UX-DR29), in the builder's order (AD-11).
REASON_WORDS = {
    ExclusionReason.NOT_FULLY_READ: "not fully read",
    ExclusionReason.UNCLEAR_RESOLUTION: "unclear resolution",
    ExclusionReason.SPLIT_OR_MERGED: "split or merged",
    ExclusionReason.ONLY_IN_ACTIVITY: "missing from Polymarket's positions list",
    ExclusionReason.SHARE_GAP: "Polymarket's two lists disagree",
    ExclusionReason.SOLD_BEFORE_RESOLUTION: "sold before resolution",
    ExclusionReason.NOT_EXPLAINED: "not explained by the activity",
}

_LESS_THAN_A_DOLLAR = "less than $1"


def share(fraction: float) -> str:
    """A share in whole percent (FR-11): "70%". Never "100%" below all of it, never "0%" above none:
    "99%" and "less than 1%" instead (Story 3.3)."""
    value = _real(fraction, "share")
    if value < 0:
        raise ValueError(f"a share must be at least 0, got {fraction!r}")
    if value == 0:
        return "0%"
    # Scaled in decimal: the float 0.285 * 100 is 28.4999…, which would round half down (Story 3.3 review).
    percent = int(Decimal(repr(value)).scaleb(2).to_integral_value(rounding=ROUND_HALF_UP))
    if percent == 0:
        return "less than 1%"
    if percent >= 100 and value < 1:
        return "99%"
    return f"{percent:,}%"


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def _cents(amount: float) -> int:
    return int(Decimal(repr(_real(amount, "amount"))).quantize(_CENT, rounding=ROUND_HALF_UP).scaleb(2))


def small_money(amount: float) -> str:
    """Money as `money()` does, but an amount that is not zero in cents and would show as "$0" reads
    "less than $1" (Story 3.3), so the card never prints "$0" for money that exists."""
    if _cents(amount) != 0 and money(amount) == "$0":
        return _LESS_THAN_A_DOLLAR
    return money(amount)


def largest_bet(real_pnl: float, largest: float | None) -> tuple[str, str, str]:
    """The first honesty column (FR-11, EXPERIENCE.md Voice and Tone) as (label, figure, sentence); empty parts are "".

    The share of the Real PnL from the largest single bet; its amount when the Real PnL is $0 or below as the
    card shows it (whole dollars, so float noise and a few cents are $0) or when the share is over 100% (compared
    in whole cents, so a Sliver losing a fraction of a cent is not "the other bets lost money"); a sentence when
    there is no bet (Story 3.3 review).
    """
    if largest is None:
        return "", "", "No resolved bets to measure."
    largest = _real(largest, "largest bet")
    real_cents = _cents(real_pnl)
    if real_cents <= 0 or money(real_pnl) == "$0":
        return "Largest single bet:", _signed_small_money(largest), ""
    if _cents(largest) > real_cents:
        amount = small_money(largest)
        return (
            "",
            amount,
            f"More than all of the Real PnL came from the single largest bet ({amount}); "
            "the other bets lost money overall.",
        )
    return "", _capital(share(min(max(largest / real_pnl, 0.0), 1.0))), "of the Real PnL came from the single largest bet."


def held(held_count: int, read_count: int) -> tuple[str, str]:
    """The second honesty column's figure and words (FR-11; Edvard, 2026-11-24): "33 of 100", "positions held to resolution."."""
    held_n, read_n = _whole(held_count, "count"), _whole(read_count, "count")
    if held_n > read_n:
        raise ValueError(f"{held_n} held cannot be more than {read_n} read")
    if read_n == 0:
        return "", "No bet's history was read in full, so this cannot be counted."
    return f"{count(held_n)} of {count(read_n)}", "positions held to resolution."


def exit_line(exit_pnl: float, *, any_sold: bool) -> str:
    """The Exit PnL under the held count (FR-11): "Shares sold before resolution: −$1,675 (Exit PnL)."."""
    return "".join(exit_parts(exit_pnl, any_sold=any_sold))


def exit_parts(exit_pnl: float, *, any_sold: bool) -> tuple[str, str, str]:
    """`exit_line` as (before, amount, after), so the page can set the amount in bold on one line (mockup)."""
    if not any_sold:
        return "No shares were sold before resolution.", "", ""
    return "Shares sold before resolution: ", _signed_small_money(exit_pnl), " (Exit PnL)."


def _signed_small_money(amount: float) -> str:
    """`money()`, but a gain or loss that is not zero in cents and would show as "$0" says so in words."""
    cents = _cents(amount)
    if cents != 0 and money(amount) == "$0":
        return f"a {'loss' if cents < 0 else 'gain'} of {_LESS_THAN_A_DOLLAR}"
    return money(amount)


def exit_warning_applies(exit_pnl: float) -> bool:
    """FR-11: the warning beside the stats when Exit PnL is below zero, in whole cents (float noise is no loss)."""
    return _cents(exit_pnl) < 0


def left_out(counts: Mapping[ExclusionReason, int]) -> str:
    """The "Left out of the test" line (FR-11, UX-DR29): reasons above 0 in the builder's order, or "none"."""
    parts = [f"{count(_whole(counts.get(r, 0), 'count'))} {words}" for r, words in REASON_WORDS.items() if counts.get(r, 0)]
    return f"{LEFT_OUT_LABEL} {', '.join(parts) if parts else 'none'}."


def fees_not_counted(failed_count: int, failed_total: float) -> str:
    """Fees that failed the fee schedule check, with their recorded total (FR-4, FR-11)."""
    n = _whole(failed_count, "count")
    if n == 0:
        return "Every fee matched the Market's fee schedule."
    fees, verb = ("fee", "was") if n == 1 else ("fees", "were")
    return (
        f"{count(n)} {fees} did not match the Market's fee schedule and {verb} not counted ({small_money(failed_total)})."
    )


def mostly_left_out_sentence(left_out_share: float) -> str:
    """FR-11's plain sentence when more than 10% of the window was left out (UX-DR29)."""
    return f"Only part of this Wallet's activity was judged: {share(left_out_share)} of its bets were left out."


def linked_bets_note(uncoupled_share: float) -> str:
    """FR-11's note when more than 20% of the tested bets have an event-mate the app cannot link (AD-20)."""
    return (
        f"{_capital(share(uncoupled_share))} of the tested bets share an event with "
        "another tested bet in a way the app cannot link, so some may depend on each other and the result can look "
        "stronger than it is."
    )


def window_line(window_size: int) -> str:
    """FR-11's window line for a capped lookup (Edvard, 2026-11-24: no total, the window stops reading at the cap)."""
    n = _whole(window_size, "count")
    return f"Based on the latest {count(n)} {'bet' if n == 1 else 'bets'}; older results are not included."


def computed_on(scope: str, window_size: int, *, capped: bool, seed: int) -> str:
    """The last honesty line (FR-11, AD-22): the set the result was computed on and its Seed, "Computed on the
    latest 2,000 bets · Seed 44". Only the `lookup` scope exists before Epic 4."""
    if scope != "lookup":
        raise ValueError(f"no wording for the scope {scope!r} yet")
    n = _whole(window_size, "count")
    if n == 0:
        bets = "no bets"
    elif capped:
        bets = f"the latest {count(n)} {'bet' if n == 1 else 'bets'}"
    elif n == 1:
        bets = "1 bet"
    else:
        bets = f"all {count(n)} bets"
    return f"Computed on {bets} · Seed {_whole(seed, 'Seed')}"


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def stored_at(epoch_seconds: int, tz: tzinfo | None = None) -> str:
    """When the Wallet's data was stored (FR-2, UX-DR20): "Data stored 15 Oct 2026, 14:02"."""
    return f"Data stored {stored_on(epoch_seconds, tz)}"


def stored_on(epoch_seconds: int, tz: tzinfo | None = None) -> str:
    """A stored snapshot's date and time (FR-2, UX-DR23): "15 Oct 2026, 14:02", as in "Show stored data from …".

    In the computer's own time zone unless `tz` is given. English month names, whatever the locale.
    """
    moment = datetime.fromtimestamp(_whole(epoch_seconds, "time"), tz=tz or timezone.utc)
    if tz is None:
        moment = moment.astimezone()  # the laptop's local time
    return f"{moment.day} {_MONTHS[moment.month - 1]} {moment.year}, {moment:%H:%M}"


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise ValueError(f"a {name} must be a whole number of at least 0, got {value!r}")
    return int(value)


def _real(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"the {name} must be a number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"the {name} must be finite, got {value!r}")
    return number
