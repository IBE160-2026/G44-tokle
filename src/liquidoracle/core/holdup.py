"""The Hold-up Test: did the Wallets that passed before the Cut-off Date keep it up afterwards (FR-17).

A Scan's Wallets fall into two groups by their Verdict on the before part alone: the
Before-Cut-off Passers (*Skilled (high confidence)*) and the Comparison Group (*Likely skilled* or
*No evidence of skill*). Nothing from after the Cut-off Date decides who is in a group. Each
group's after-part bets are then pooled and run through the Skill Test as one test, so Wallets
that bet in the same Market share its draw and are not counted as separate evidence (AD-20).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from liquidoracle.core.skilltest import skill_test
from liquidoracle.records import COMPARISON, HOLDUP_AFTER, PASSERS, GroupResult, PositionSet, Verdict

PURPOSE = "holdup"  # AD-15: the random purpose; the unit is the group's test, not a Wallet
MIN_AFTER_BETS = 10  # [ASSUMPTION] PRD Glossary, Minimum After-bets: tested Positions a Wallet needs after the cut-off
DROPPED_GAP_POINTS = 20  # [ASSUMPTION] FR-17: the warning shows above this gap between the groups' dropped shares


@dataclass(frozen=True, slots=True)
class Member:
    """A Scan Wallet as the Hold-up Test sees it: its Verdict on the before part, and its after part.

    `after` is what the one Position builder made of the Wallet's after part (AD-11); it is never
    looked at to decide the Wallet's group. `not_fully_read`: its before or after part was not
    fully read.
    """

    wallet: str
    verdict_before: Verdict
    after: PositionSet
    not_fully_read: bool = False


def group_of(verdict_before: Verdict) -> str | None:
    """FR-17: the group a Wallet's before-part Verdict puts it in; None for *Not enough data*."""
    if verdict_before is Verdict.SKILLED:
        return PASSERS
    if verdict_before in (Verdict.LIKELY_SKILLED, Verdict.NO_EVIDENCE):
        return COMPARISON
    return None


def counts(member: Member) -> bool:
    """FR-17: a Wallet counts in its group's result with at least the Minimum After-bets, the same in both groups."""
    return member.after.tested_count >= MIN_AFTER_BETS


def hold_up(members: Sequence[Member], *, seed: int) -> tuple[GroupResult, GroupResult]:
    """The Passers' and the Comparison Group's results, in that order (FR-17).

    The Wallets that count are pooled in address order (AD-15) and tested as one Position set:
    the random unit is the group's test, so all its Wallets share each Market's draw (AD-20).
    """
    wallets = [member.wallet for member in members]
    if len(set(wallets)) != len(wallets):
        raise ValueError("a Wallet is in the Hold-up Test twice")
    return _group(PASSERS, members, seed), _group(COMPARISON, members, seed)


def dropped_shares_differ(passers: GroupResult, comparison: GroupResult) -> bool:
    """FR-17: do the groups' dropped shares differ by more than 20 percentage points?

    Whole-number arithmetic, so exactly 20 points is never "more". A group with no Wallets has
    no share: both sides of the comparison are then 0, so nothing is said.
    """
    gap = abs(passers.dropped * comparison.wallets - comparison.dropped * passers.wallets)
    return 100 * gap > DROPPED_GAP_POINTS * passers.wallets * comparison.wallets


def _group(group: str, members: Sequence[Member], seed: int) -> GroupResult:
    mine = sorted((m for m in members if group_of(m.verdict_before) == group), key=lambda m: m.wallet)
    counted = [m for m in mine if counts(m)]
    pooled = PositionSet(
        tested=tuple(p for m in counted for p in m.after.tested),
        slivers=tuple(p for m in counted for p in m.after.slivers),
        left_out=(),  # each Wallet's own exclusions stay with its own results (AD-11)
    )
    result = skill_test(pooled, seed=seed, unit_id=group, scope=HOLDUP_AFTER, purpose=PURPOSE)
    return GroupResult(
        group=group,
        verdict=result.verdict,
        p_value=result.p_value,
        tested_count=result.tested_count,
        real_pnl=result.real_pnl,
        wallets=len(mine),
        dropped=len(mine) - len(counted),
        not_fully_read=sum(1 for m in mine if m.not_fully_read),
    )
