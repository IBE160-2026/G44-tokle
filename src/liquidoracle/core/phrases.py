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
from datetime import datetime, timezone, tzinfo
from decimal import ROUND_HALF_UP, Decimal
from numbers import Integral, Real

from liquidoracle.core.skilltest import MIN_RESOLVED, SIMULATIONS

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


def chart_text(real_pnl: float, tested_count: int, p_value: float) -> str:
    """The chart's always-visible text alternative (PRD §8, UX-DR24)."""
    return (
        f"This Wallet made {money(real_pnl)} on {count(tested_count)} {resolved_bets_word(tested_count)}. "
        f"In {SIMULATIONS:,} replays with no edge, a result this good came up {odds(p_value)}."
    )


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
