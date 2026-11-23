"""The luck chart, ready to draw (FR-9, UX-DR24, UX-DR25, AD-18, AD-25; Story 3.1).

`luck_chart` turns one Skill Test result into finished geometry and words, so the template only
places them and never counts or formats anything. The bars are the result's own 42 bins (AD-25):
the low end bar, the 40 bars of the dollar axis and the high end bar. "Above all" and "below all"
come from the result's exact counts, never from the bars.

Geometry: the SVG's view box is `VIEW_WIDTH` slots wide and 100 high. Slot 0 is the low end bar,
slot 1 a gap, slots 2 to 41 the axis bars, slot 42 a gap and slot 43 the high end bar. Heights
and gridlines are in percent of the plot; HTML labels use `left` percentages of the same width.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from liquidoracle.core import phrases
from liquidoracle.core.skilltest import CHART_BARS
from liquidoracle.records import SkillTestResult

VIEW_WIDTH = CHART_BARS + 4  # the two end bars and a gap beside each
AXIS_START = 2  # the slot where the axis begins
BAR_INSET = 0.1  # each bar leaves this much of its slot empty on both sides
TICK_EVERY = 5  # a tick every 5 axis bars; every other one is hidden below 640 px (UX-DR25)
GRID_LINES = 4  # about this many gridlines above 0
_GRID_STEPS = (1, 2, 5)
# A one-line marker label within this percent of either side is anchored inwards, so even a 360 px wide
# page keeps it on the card (Story 3.1 review: 15% let a centred label spill past the right edge).
EDGE_ZONE = 25.0

# The hint line (Edvard, 2026-11-23): only what is true without JavaScript; Story 3.2 adds how to explore.
HINT = "Each bar is a range of results. The taller the bar, the more replays ended there."
Y_TITLE = "Number of replays"


class Anchor(StrEnum):
    """Which point of the marker label sits on the marker line."""

    START = "start"
    MIDDLE = "middle"
    END = "end"


@dataclass(frozen=True, slots=True)
class Bar:
    x: float  # left side in view-box units
    width: float
    height: float  # percent of the plot
    count: int


@dataclass(frozen=True, slots=True)
class Gridline:
    level: float  # percent of the plot from its base
    label: str  # "200"


@dataclass(frozen=True, slots=True)
class Tick:
    left: float  # percent of the chart width
    label: str  # "$100,000"
    short: str  # "$100k", below 640 px
    minor: bool  # hidden below 640 px


@dataclass(frozen=True, slots=True)
class LuckChart:
    """Everything the chart card shows (UX-DR24, UX-DR25)."""

    title_note: str
    about: tuple[str, str, str]
    hint: str
    text: str  # the text alternative under the chart
    y_title: str
    view_width: int
    bars: tuple[Bar, ...]
    gridlines: tuple[Gridline, ...]
    ticks: tuple[Tick, ...]
    low_label: str
    low_short: str
    high_label: str
    high_short: str
    marker_x: float  # view-box units
    marker_left: float  # percent of the chart width
    marker_label: str
    beyond: str | None  # "above all 10,000 Simulations", or None
    anchor: Anchor


def luck_chart(result: SkillTestResult) -> LuckChart:
    """The chart for a result with a p-value; *Not enough data* has no chart (FR-10)."""
    if result.p_value is None or result.at_or_above is None or result.at_or_below is None:
        raise ValueError("a result without a p-value has no luck chart")
    bins = result.bins
    if len(bins) != CHART_BARS + 2 or bins[0].low is not None or bins[-1].high is not None:
        raise ValueError(f"a luck chart needs {CHART_BARS} axis bars and two end bars, got {len(bins)} bins")
    axis = bins[1:-1]
    edges = [_edge(b.low) for b in axis] + [_edge(axis[-1].high)]
    low, high = edges[0], edges[-1]

    peak = max(1, max(b.count for b in bins))
    step = _grid_step(peak)
    top = step * math.ceil(peak / step)  # the top gridline: the tallest bar rounded up to whole steps
    bars = tuple(
        Bar(x=slot + BAR_INSET, width=1 - 2 * BAR_INSET, height=100.0 * b.count / top, count=b.count)
        for slot, b in zip(_slots(), bins, strict=True)
    )
    gridlines = tuple(Gridline(level=100.0 * v / top, label=phrases.count(v)) for v in range(0, top + 1, step))
    ticks = tuple(
        Tick(
            left=_percent(AXIS_START + i),
            label=phrases.axis_money(edges[i]),
            short=phrases.axis_money(edges[i], short=True),
            minor=i % (2 * TICK_EVERY) != 0,
        )
        for i in range(0, CHART_BARS + 1, TICK_EVERY)
    )

    # The axis always holds the Real PnL (core widens it, AD-25); clamp only against float dust.
    share = min(max((result.real_pnl - low) / (high - low), 0.0), 1.0)
    marker_x = AXIS_START + CHART_BARS * share
    marker_left = _percent(marker_x)
    if result.at_or_above == 0:
        beyond = phrases.beyond_all(above=True)
    elif result.at_or_below == 0:
        beyond = phrases.beyond_all(above=False)
    else:
        beyond = None
    if beyond is not None:  # the long two-line label always hangs towards the middle
        anchor = Anchor.END if marker_left >= 50.0 else Anchor.START
    elif marker_left < EDGE_ZONE:
        anchor = Anchor.START
    elif marker_left > 100.0 - EDGE_ZONE:
        anchor = Anchor.END
    else:
        anchor = Anchor.MIDDLE

    return LuckChart(
        title_note=phrases.CHART_TITLE_NOTE,
        about=phrases.about_chart(result.tested_count, result.own_fees),
        hint=HINT,
        text=phrases.chart_text(result.real_pnl, result.tested_count, result.p_value),
        y_title=Y_TITLE,
        view_width=VIEW_WIDTH,
        bars=bars,
        gridlines=gridlines,
        ticks=ticks,
        low_label=phrases.end_bar_label(low, above=False),
        low_short=phrases.end_bar_label(low, above=False, short=True),
        high_label=phrases.end_bar_label(high, above=True),
        high_short=phrases.end_bar_label(high, above=True, short=True),
        marker_x=marker_x,
        marker_left=marker_left,
        marker_label=phrases.marker_label(result.real_pnl),
        beyond=beyond,
        anchor=anchor,
    )


def _slots() -> list[int]:
    """The slot of each of the 42 bins, in order."""
    return [0, *range(AXIS_START, AXIS_START + CHART_BARS), VIEW_WIDTH - 1]


def _percent(slot: float) -> float:
    return 100.0 * slot / VIEW_WIDTH


def _edge(value: float | None) -> float:
    if value is None:
        raise ValueError("an axis bar must have both edges")
    return value


def _grid_step(peak: int) -> int:
    """The smallest round step (1, 2 or 5 times a power of ten) giving at most `GRID_LINES` lines above 0."""
    power = 10 ** max(0, math.floor(math.log10(max(peak / GRID_LINES, 1))))
    while True:
        for unit in _GRID_STEPS:
            step = unit * power
            if math.ceil(peak / step) <= GRID_LINES:
                return step
        power *= 10
