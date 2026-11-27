"""The Hold-up Test page of one finished Scan (FR-17, UX-DR33, UX-DR35, AD-22; Story 5.2).

The page shows what the Scan stored when it finished: the two `holdup_after` group results (Story 5.1).
Nothing is tested again, fetched or written here. The dropped-share warning is worked out from the two
stored rows by `core/holdup`. Words and numbers come from `core/phrases` (AD-25); templates only place them.

The test itself is in `core/holdup`, and its phase of the Scan job in `services/scan`.
"""

from __future__ import annotations

from dataclasses import dataclass

from liquidoracle.core import phrases
from liquidoracle.core.holdup import MIN_AFTER_BETS, dropped_shares_differ
from liquidoracle.data import synthetic
from liquidoracle.data.store import Store
from liquidoracle.data.window import WINDOW_LIMIT, cutoff_day
from liquidoracle.records import COMPARISON, HOLDUP_GROUPS, PASSERS, GroupResult, Verdict
from liquidoracle.services.lookup import FILLED_DOTS
from liquidoracle.services.watchlist import TAB_HOLDUP, ScanHeader, finished_scan, scan_header, whole_results

TITLES = {PASSERS: "Before-Cut-off Passers", COMPARISON: "Comparison Group"}  # UX-DR35
# Who is in each group, under its title (Edvard, 2026-11-27, after the review): the words `core.holdup.group_of`
# acts on, as (text, in italics) parts. A Verdict's name is always in italics.
_RATED, _BEFORE = ("Wallets rated ", False), (" on their bets before the Cut-off Date.", False)
WHO = {
    PASSERS: (_RATED, (Verdict.SKILLED.value, True), _BEFORE),
    COMPARISON: (_RATED, (Verdict.LIKELY_SKILLED.value, True), (" or ", False), (Verdict.NO_EVIDENCE.value, True), _BEFORE),
}
# FR-17, word for word
WARNING = (
    "More Wallets were dropped in one group than in the other. Wallets that stop betting may be the ones that "
    "lost, so the group with more dropped Wallets may look better than it is."
)
# EXPERIENCE.md *No Before-Cut-off Passers*, *Empty Comparison Group*: (before, in italics, after)
NO_PASSERS = (
    "No Wallet passed on its bets before the Cut-off Date, so the Hold-up Test and Copy Test have nothing to test.",
    "",
    "",
)
EMPTY_COMPARISON = (
    "No Wallets in this group: every scanned Wallet passed or had ",
    Verdict.NOT_ENOUGH_DATA.value,
    " before the Cut-off Date.",
)
# FR-11, FR-17, AD-20: the after part's cap and the shared draw, under the cards
NOTE = (
    f"Each Wallet's bets after the Cut-off Date are capped at its first {phrases.count(WINDOW_LIMIT)}. "
    "Bets in the same Market are simulated together, not as separate evidence."
)
DROPPED_RULE = f"(fewer than {MIN_AFTER_BETS} bets after the Cut-off Date)"  # FR-17, the Minimum After-bets
# The five figures in the order shown: (label, the rule behind the count, written after the label)
FIGURES = (
    ("Resolved bets counted", ""),
    ("Real PnL", ""),
    ("Wallets in the group", ""),
    ("Wallets dropped", DROPPED_RULE),
    ("Wallets not fully read", ""),
)
# Offline Mode only (Edvard, 2026-11-27). The first sentence is his addition, so the Passers card does not
# read as a real skilled trader found; `test_fr17_no_real_wallet_is_a_passer_in_the_offline_scan` fails if it
# stops being true. The second says why the warning shows on the Sample Dataset, so it does not look like a bug.
# Each is left out when it would describe nothing: the first when no Passer is tested, the second when the
# warning is not there or is there because the Passers, not the Comparison Group, were dropped more.
OFFLINE_PASSERS = (
    "On the Sample Dataset, the Passers tested here are made-up Wallets built to have skill, not real traders: "
    "no real Wallet passed before the Cut-off Date."
)
OFFLINE_WARNING = (
    f"The warning above is expected: the {phrases.count(synthetic.COIN_FLIPPERS)} coin-flipper Wallets have no "
    "bets after the Cut-off Date, so all of them are dropped, and nearly all of them are in the Comparison Group."
)
# DESIGN.md Verdict pill: the tint a Verdict's pill gets ("" is the accent tint)
PILL_TONE = {
    Verdict.SKILLED: "",
    Verdict.LIKELY_SKILLED: "",
    Verdict.NO_EVIDENCE: "is-neutral",
    Verdict.NOT_ENOUGH_DATA: "is-none",
}


@dataclass(frozen=True, slots=True)
class Figure:
    """One small figure of a group card."""

    label: str
    value: str
    rule: str = ""  # the rule behind the count, after the label


@dataclass(frozen=True, slots=True)
class GroupCard:
    """One group's card (UX-DR35). A group with no Wallets has only its sentence, in `empty`."""

    key: str  # `passers` or `comparison`
    title: str
    who: tuple[tuple[str, bool], ...]  # the line under the title: (text, in italics) parts
    empty: tuple[str, str, str] | None
    verdict: str
    filled_dots: int | None  # None: no dots (*Not enough data*)
    tone: str
    odds_line: str  # the Verdict card's odds sentence, or its *Not enough data* sentence
    figures: tuple[Figure, ...]


@dataclass(frozen=True, slots=True)
class HoldUpView:
    header: ScanHeader
    title: str  # the tab title: "Hold-up Test · 1 Jul 2025 · LiquidOracle"
    warning: str  # FR-17's dropped-share warning; "" when the shares are close
    offline_notes: tuple[str, ...]  # what the page adds in Offline Mode; the web layer knows the mode (AD-13)
    cards: tuple[GroupCard, GroupCard]  # the Passers, then the Comparison Group
    note: str
    seed: str  # "Seed 44"


class HoldUps:
    """The Hold-up Test pages over one run's store (AD-13). Read-only."""

    def __init__(self, store: Store) -> None:
        self._store = store

    def view(self, scan_id: int) -> HoldUpView | None:
        """The Hold-up Test page of a finished Scan. None for an unknown or unfinished Scan, and for one
        finished before the Hold-up Test existed, which has no stored result (Story 5.1)."""
        scan = finished_scan(self._store, scan_id)
        if scan is None:
            return None
        groups = self._store.group_results(scan_id)
        if len(groups) != len(HOLDUP_GROUPS):
            return None
        passers, comparison = groups
        flagged = dropped_shares_differ(passers, comparison)
        notes = []
        if passers.dropped < passers.wallets:  # some Passer is tested
            notes.append(OFFLINE_PASSERS)
        # whole numbers, as in `dropped_shares_differ`: the Comparison Group's dropped share is the larger one
        if flagged and comparison.dropped * passers.wallets > passers.dropped * comparison.wallets:
            notes.append(OFFLINE_WARNING)
        return HoldUpView(
            header=scan_header(self._store, scan, whole_results(self._store, scan_id)),
            title=f"{TAB_HOLDUP} · {phrases.short_date(cutoff_day(scan.cutoff))} · LiquidOracle",
            warning=WARNING if flagged else "",
            offline_notes=tuple(notes),
            cards=(_card(passers, NO_PASSERS), _card(comparison, EMPTY_COMPARISON)),
            note=NOTE,
            seed=f"Seed {scan.seed}",
        )


def _card(result: GroupResult, empty: tuple[str, str, str]) -> GroupCard:
    values = (
        phrases.count(result.tested_count),
        phrases.money(result.real_pnl),
        phrases.count(result.wallets),
        phrases.count(result.dropped),
        phrases.count(result.not_fully_read),
    )
    return GroupCard(
        key=result.group,
        title=TITLES[result.group],
        who=WHO[result.group],
        empty=empty if result.wallets == 0 else None,
        verdict=result.verdict.value,
        filled_dots=FILLED_DOTS[result.verdict],
        tone=PILL_TONE[result.verdict],
        odds_line=(
            phrases.not_enough_data(result.tested_count) if result.p_value is None
            else phrases.odds_sentence(result.p_value)
        ),
        figures=tuple(Figure(label, value, rule) for (label, rule), value in zip(FIGURES, values, strict=True)),
    )
