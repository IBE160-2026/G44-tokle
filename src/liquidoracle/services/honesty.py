"""The honesty notes: what the Skill Test cannot see, as finished text (FR-11, UX-DR15, UX-DR29; Story 3.3).

Every number comes from the Position builder's record or the Skill Test result kept in `StoredResult`
(AD-11), and every sentence from `core/phrases` (AD-25), so the template only places the text.
"""

from __future__ import annotations

from dataclasses import dataclass

from liquidoracle.core import phrases
from liquidoracle.core.positions import mostly_left_out
from liquidoracle.core.skilltest import mostly_uncoupled
from liquidoracle.services.fetch import StoredResult


@dataclass(frozen=True, slots=True)
class HonestyNotes:
    """The honesty notes card and the Exit PnL warning. An empty string means "leave this part out"."""

    title: str
    exit_warning: tuple[str, str] | None  # FR-11: shown beside the stats only when Exit PnL is below zero
    largest_label: str  # "Largest single bet:" when the Real PnL is $0 or below
    largest_figure: str  # "70%" or an amount
    largest_text: str
    held_figure: str  # "33 of 100"
    held_text: str
    exit_text: str
    exit_parts: tuple[str, str, str]  # exit_text split around its amount, which the page sets in bold
    limits: str
    not_advice: str
    left_out: str
    fees: str
    mostly_left_out: str  # FR-11's over-10% sentence, in the warning style
    linked: str  # FR-11's over-20% linked-bets note
    window: str  # FR-11's window line, only when the window was capped
    computed_on: str


def honesty_notes(stored: StoredResult) -> HonestyNotes:
    """The honesty notes for one stored lookup, also for *Not enough data* (FR-10, FR-11)."""
    result, positions = stored.result, stored.positions
    label, figure, text = phrases.largest_bet(result.real_pnl, positions.largest_bet)
    held_figure, held_text = phrases.held(positions.held_count, positions.read_count)
    # A capped window names what the cap counted, the positions-list rows, never more than the limit; the builder's
    # count also holds tokens found only in activity rows (Story 3.3 review). Uncapped: every bet the builder saw.
    in_set = stored.listed if stored.capped else positions.window_size
    # Nothing in Real PnL: no bet's sales or fees were read, so those lines would claim what the app cannot see.
    measured = positions.largest_bet is not None
    return HonestyNotes(
        title=phrases.HONESTY_TITLE,
        exit_warning=phrases.EXIT_WARNING if phrases.exit_warning_applies(positions.exit_pnl) else None,
        largest_label=label,
        largest_figure=figure,
        largest_text=text,
        held_figure=held_figure,
        held_text=held_text,
        exit_text=phrases.exit_line(positions.exit_pnl, any_sold=positions.any_sold) if positions.read_count else "",
        exit_parts=(
            phrases.exit_parts(positions.exit_pnl, any_sold=positions.any_sold) if positions.read_count else ("", "", "")
        ),
        limits=phrases.LIMITS_TEXT,
        not_advice=phrases.NOT_ADVICE,
        left_out=phrases.left_out(positions.excluded_counts),
        fees=phrases.fees_not_counted(positions.failed_fee_count, positions.failed_fee_total) if measured else "",
        mostly_left_out=phrases.mostly_left_out_sentence(positions.left_out_share) if mostly_left_out(positions) else "",
        linked=phrases.linked_bets_note(result.uncoupled_share) if mostly_uncoupled(result) else "",
        window=phrases.window_line(in_set) if stored.capped else "",
        computed_on=phrases.computed_on(result.scope, in_set, capped=stored.capped, seed=result.seed),
    )
