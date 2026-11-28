"""Price history rules for the Copy Test (FR-18c, AD-14, AD-24). Pure: the same live and offline.

The Copy Test prices a follower who buys a few minutes after each of a Wallet's buy fills. So only
the prices near a fill are needed: one short window per fill, from 2 minutes before it to 32 minutes
after it (the longest Copy Delay is 30 minutes, and a price may be up to 2 minutes old). Windows
that overlap are merged, and the windows of one token are packed into requests of at most 14 days,
because one request can cover that much (measured: 1.06 requests per token instead of 3.9).

`price_at` is the one rule for "the price at time t": the last recorded point at or before t, and
only if it is at most 2 minutes old. It never looks at a later point, so a follower is never priced
with something that had not happened yet.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Sequence

from liquidoracle.records import PRICE_REQUEST_SPAN, PricePoint

BEFORE_FILL = 2 * 60  # AD-14: a fill's window starts this many seconds before it
AFTER_FILL = 32 * 60  # AD-14: and ends this many seconds after it
MAX_AGE = 2 * 60  # AD-24: a point older than this at time t is not a price at t

Span = tuple[int, int]  # [start, end] in epoch seconds, both ends included


def price_at(points: Sequence[PricePoint], t: int) -> float | None:
    """The price of one outcome at time `t`: the last point at or before `t`, if at most `MAX_AGE` old (AD-24).

    `points` are one token's points, oldest first. None when there is no such point: the buy's whole
    Position is then left out of that Copy Delay and counted (FR-18a, FR-18c; Edvard, 2026-11-28).
    """
    at = bisect_right(points, t, key=lambda point: point.t)
    if at == 0:
        return None
    point = points[at - 1]
    return point.price if t - point.t <= MAX_AGE else None


def fill_windows(fill_times: Iterable[int]) -> tuple[Span, ...]:
    """One window [fill - 2 min, fill + 32 min] per buy fill, merged where they overlap, oldest first (AD-14)."""
    return _merged((t - BEFORE_FILL, t + AFTER_FILL) for t in set(fill_times))


def uncovered(wanted: Iterable[Span], have: Iterable[Span]) -> tuple[Span, ...]:
    """The `wanted` windows that the stored windows `have` do not cover completely, oldest first (AD-4).

    A window that is only partly stored is asked for whole: requests are packed by token, so that
    costs no extra request, and the store keeps one row per point.
    """
    stored = _merged(have)
    starts = [start for start, _ in stored]
    missing = []
    for start, end in sorted(set(wanted)):
        at = bisect_right(starts, start) - 1
        if at < 0 or stored[at][1] < end:
            missing.append((start, end))
    return tuple(missing)


def pack(windows: Iterable[Span], span: int = PRICE_REQUEST_SPAN) -> tuple[tuple[Span, ...], ...]:
    """Group one token's windows into requests: each group runs at most `span` seconds from its first
    start to its last end (AD-14). A single window longer than that is cut into pieces first."""
    if span < 1:
        raise ValueError(f"span must be 1 or more, not {span}")
    pieces: list[Span] = []
    for start, end in sorted(set(windows)):
        if end < start:
            raise ValueError(f"a window ends before it starts: {(start, end)}")
        while end - start > span:
            pieces.append((start, start + span))
            start += span + 1
        pieces.append((start, end))
    groups: list[list[Span]] = []
    for piece in pieces:
        if groups and piece[1] - groups[-1][0][0] <= span:
            groups[-1].append(piece)
        else:
            groups.append([piece])
    return tuple(tuple(group) for group in groups)


def inside(points: Iterable[PricePoint], windows: Sequence[Span]) -> tuple[PricePoint, ...]:
    """The points whose time lies in one of `windows`, oldest first, one per time (AD-14: only these are stored).

    Two points with the same time keep the later one in `points`.
    """
    spans = _merged(windows)
    starts = [start for start, _ in spans]
    kept: dict[int, PricePoint] = {}
    for point in points:
        at = bisect_right(starts, point.t) - 1
        if at >= 0 and point.t <= spans[at][1]:
            kept[point.t] = point
    return tuple(kept[t] for t in sorted(kept))


def _merged(spans: Iterable[Span]) -> tuple[Span, ...]:
    """Spans sorted and joined where they overlap or follow each other with no second between."""
    merged: list[Span] = []
    for start, end in sorted(set(spans)):
        if end < start:
            raise ValueError(f"a window ends before it starts: {(start, end)}")
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return tuple(merged)
