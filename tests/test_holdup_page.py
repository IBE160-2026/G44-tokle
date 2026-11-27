"""The Hold-up Test page of a finished Scan, its tab, and the README's offline result (FR-17, NFR-13, UX-DR33,
UX-DR35, AD-13, AD-22; Story 5.2).

The page only shows the two `holdup_after` rows a Scan stored when it finished (Story 5.1), so these tests
write a finished Scan's rows straight into the database (`hand_scan`, `hand_groups`) for exact numbers.
The test that the stored rows are what a real Scan computes is in `test_holdup.py`. No socket is opened (AD-17).
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask.testing import FlaskClient
from markupsafe import Markup
from test_holdup import LUCKY_COIN_FLIPPERS, OFFLINE_COMPARISON_SIZES, OFFLINE_PASSER_SIZES, REAL_COMPARISON
from test_watchlist import CUTOFF, Row, hand_scan, wallet, web_over

from liquidoracle.core import holdup as core_holdup
from liquidoracle.core import phrases, skilltest
from liquidoracle.data.offline import OfflineClient
from liquidoracle.data.store import HOLDUP_AFTER, Store
from liquidoracle.records import COMPARISON, PASSERS, GroupResult, Verdict
from liquidoracle.services import holdup as page
from liquidoracle.services import scan as scan_module
from liquidoracle.services.holdup import HoldUps
from liquidoracle.services.lookup import Lookup
from liquidoracle.services.watchlist import Watchlists
from liquidoracle.settings import Settings
from liquidoracle.web import create_app

REPO = Path(__file__).resolve().parents[1]
SEED = 44
SKILLED, LIKELY, NO_EVIDENCE, NOT_ENOUGH = (
    Verdict.SKILLED, Verdict.LIKELY_SKILLED, Verdict.NO_EVIDENCE, Verdict.NOT_ENOUGH_DATA,
)
SIMS = skilltest.SIMULATIONS

# The full offline Scan's two stored rows, as two runs through the real app stored them (Story 5.1, and Story
# 5.2's own Scan). The numbers are not typed here but come from `test_holdup.py`, where tests stand behind them: the
# Passers' 300 bets, $6,000 and no Simulation as good, and the Comparison Group's bets, count and Real PnL, from a
# real offline Scan (`test_fr17_the_offline_scan_drops_the_coin_flippers_and_sets_the_flag`); the group sizes from
# the listed lucky coin-flippers (`test_fr17_the_listed_lucky_coin_flippers_are_every_one_that_passed`).
OFFLINE_PASSERS = GroupResult(PASSERS, SKILLED, 1 / (SIMS + 1), 300, 6000.0, *OFFLINE_PASSER_SIZES, 0)
OFFLINE_COMPARISON = GroupResult(
    COMPARISON, NO_EVIDENCE, (REAL_COMPARISON[1] + 1) / (SIMS + 1), REAL_COMPARISON[0], REAL_COMPARISON[2],
    *OFFLINE_COMPARISON_SIZES, 0,
)


WHO_PASSERS = "Wallets rated Skilled (high confidence) on their bets before the Cut-off Date."
WHO_COMPARISON = "Wallets rated Likely skilled or No evidence of skill on their bets before the Cut-off Date."


def passers(verdict: Verdict = SKILLED, p: float | None = 0.004, tested: int = 120, pnl: float = 2500.0, *,
            wallets: int = 10, dropped: int = 2, unread: int = 0) -> GroupResult:
    return GroupResult(PASSERS, verdict, p, tested, pnl, wallets, dropped, unread)


def comparison(verdict: Verdict = NO_EVIDENCE, p: float | None = 0.4, tested: int = 800, pnl: float = -310.4, *,
               wallets: int = 50, dropped: int = 12, unread: int = 3) -> GroupResult:
    return GroupResult(COMPARISON, verdict, p, tested, pnl, wallets, dropped, unread)


def hand_groups(path: Path, scan_id: int, *groups: GroupResult, seed: int = SEED) -> None:
    """A Scan's stored Hold-up rows, written straight into the database (the test's own write)."""
    db = sqlite3.connect(path)
    with db:
        db.executemany(
            "INSERT INTO group_result (scan_id, scope, group_name, cutoff, seed, verdict, p_value, tested_count,"
            " real_pnl, wallets, dropped, not_fully_read) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(scan_id, HOLDUP_AFTER, g.group, CUTOFF, seed, g.verdict.value, g.p_value, g.tested_count, g.real_pnl,
              g.wallets, g.dropped, g.not_fully_read) for g in groups],
        )
    db.close()


def held_up_scan(path: Path, *groups: GroupResult, seed: int = SEED, step: str = "done") -> int:
    """A finished Scan of two Wallets with these Hold-up rows (the offline Scan's by default)."""
    scan_id = hand_scan(path, [Row(wallet(1)), Row(wallet(2), verdict=NO_EVIDENCE.value, p_value=0.4)], seed=seed, step=step)
    hand_groups(path, scan_id, *(groups or (OFFLINE_PASSERS, OFFLINE_COMPARISON)), seed=seed)
    return scan_id


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "live.db"


@pytest.fixture
def store(path: Path) -> Iterator[Store]:
    made = Store(path)
    yield made
    made.close()


def offline_over(store: Store) -> FlaskClient:
    """The app in Offline Mode over this store (the page reads only the store)."""
    return create_app(Settings(offline=True), Lookup(OfflineClient([]), store, seed=SEED)).test_client()


def text(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def cards(html: str) -> dict[str, str]:
    """Each group card's HTML by its group."""
    found = re.findall(r'<section class="card group-card" aria-labelledby="group-(\w+)">(.*?)</section>', html, re.S)
    assert [key for key, _ in found] == [PASSERS, COMPARISON]  # the Passers first, always
    return dict(found)


def figures(card: str) -> list[tuple[str, str]]:
    return [(text(label), text(value)) for label, value in re.findall(r"<dt>(.*?)</dt><dd>(.*?)</dd>", card, re.S)]


def hold_up(web: FlaskClient, scan_id: int) -> str:
    reply = web.get(f"/scans/{scan_id}/hold-up")
    assert reply.status_code == 200, reply.status_code
    return reply.get_data(as_text=True)


# --- the view (FR-17, UX-DR35, AD-22) -----------------------------------------------------------------------


def test_fr17_the_offline_scans_stored_result_is_what_the_cards_show(store: Store, path: Path) -> None:
    """FR-17, UX-DR35, AD-22, AD-25 (matrix "Offline Scan"): the two stored rows of the offline Scan read as the
    Passers' and the Comparison Group's cards, each with its Verdict, the Verdict card's odds sentence and its five
    figures, and the dropped-share warning is set (70% against 99.7%)."""
    view = HoldUps(store).view(held_up_scan(path))
    assert view is not None
    first, second = view.cards
    assert (first.title, first.verdict, first.filled_dots, first.tone) == ("Before-Cut-off Passers", SKILLED.value, 3, "")
    assert first.odds_line == "a trader with no edge would do this well fewer than 1 time in 10,000."
    assert [(f.label, f.value) for f in first.figures] == [
        ("Resolved bets counted", "300"), ("Real PnL", "$6,000"), ("Wallets in the group", "10"),
        ("Wallets dropped", "7"), ("Wallets not fully read", "0"),
    ]
    assert (second.title, second.verdict, second.filled_dots, second.tone) == (
        "Comparison Group", NO_EVIDENCE.value, 0, "is-neutral",
    )
    assert second.odds_line == "a trader with no edge would do this well more than half the time."
    assert [f.value for f in second.figures] == ["409", f"{phrases.MINUS}$19,217", "999", "996", "0"]
    assert [f.rule for f in first.figures] == ["", "", "", "(fewer than 10 bets after the Cut-off Date)", ""]
    assert [f.label for f in second.figures] == [f.label for f in first.figures] == [label for label, _ in page.FIGURES]
    assert first.empty is None and second.empty is None
    assert view.warning == page.WARNING
    assert view.title == "Hold-up Test · 1 Jul 2025 · LiquidOracle"
    assert view.seed == "Seed 44" and view.header.title == "Scan of 2 Wallets"


def test_fr17_the_fixed_sentences_are_the_plans_word_for_word() -> None:
    """FR-17, FR-11, UX-DR35, AD-25: the warning, the note under the cards and the two empty-group sentences are the
    plan's own words; the 2,000 and the 10 are the app's constants, not typed again."""
    assert page.WARNING == (
        "More Wallets were dropped in one group than in the other. Wallets that stop betting may be the ones that "
        "lost, so the group with more dropped Wallets may look better than it is."
    )
    assert page.NOTE == (
        "Each Wallet's bets after the Cut-off Date are capped at its first 2,000. Bets in the same Market are "
        "simulated together, not as separate evidence."
    )
    assert "".join(page.NO_PASSERS) == (
        "No Wallet passed on its bets before the Cut-off Date, so the Hold-up Test and Copy Test have nothing to test."
    )
    assert page.EMPTY_COMPARISON == (
        "No Wallets in this group: every scanned Wallet passed or had ", "Not enough data", " before the Cut-off Date.",
    )
    assert page.DROPPED_RULE == f"(fewer than {core_holdup.MIN_AFTER_BETS} bets after the Cut-off Date)"
    assert page.OFFLINE_PASSERS == (
        "On the Sample Dataset, the Passers tested here are made-up Wallets built to have skill, not real traders: "
        "no real Wallet passed before the Cut-off Date."
    )
    assert page.OFFLINE_WARNING == (
        "The warning above is expected: the 1,000 coin-flipper Wallets have no bets after the Cut-off Date, so all "
        "of them are dropped, and nearly all of them are in the Comparison Group."
    )


def test_fr17_each_card_says_who_is_in_the_group(store: Store, path: Path) -> None:
    """FR-17, UX-DR35 (Edvard, 2026-11-27, after the review): under each card's title one line says who is in the
    group, with each Verdict's name in italics. The Verdicts it names are exactly the ones the app's own rule
    (`core.holdup.group_of`) puts in that group, so the line cannot drift from the rule. A card with no Wallets
    keeps its line."""
    for group in (PASSERS, COMPARISON):
        named = {part for part, italic in page.WHO[group] if italic}
        assert named == {v.value for v in Verdict if core_holdup.group_of(v) == group}, group
    assert "".join(part for part, _ in page.WHO[PASSERS]) == WHO_PASSERS
    assert "".join(part for part, _ in page.WHO[COMPARISON]) == WHO_COMPARISON
    scan_id = held_up_scan(path)
    view = HoldUps(store).view(scan_id)
    assert view is not None and [card.who for card in view.cards] == [page.WHO[PASSERS], page.WHO[COMPARISON]]
    both = cards(hold_up(web_over(store), scan_id))
    assert ('<h2 id="group-passers">Before-Cut-off Passers</h2>\n        <p class="sub group-who">Wallets rated '
            "<em>Skilled (high confidence)</em> on their bets before the Cut-off Date.</p>") in both[PASSERS]
    assert ('<p class="sub group-who">Wallets rated <em>Likely skilled</em> or <em>No evidence of skill</em> on their '
            "bets before the Cut-off Date.</p>") in both[COMPARISON]
    assert both[PASSERS].index("group-who") < both[PASSERS].index("verdict-pill")
    empty = held_up_scan(path, passers(NOT_ENOUGH, None, 0, 0.0, wallets=0, dropped=0),
                         comparison(NOT_ENOUGH, None, 0, 0.0, wallets=0, dropped=0, unread=0))
    for group, card in cards(hold_up(web_over(store), empty)).items():
        assert card.count('class="sub group-who"') == 1 and card.index("group-who") < card.index("empty-note"), group


@pytest.mark.parametrize(
    ("verdict", "p", "dots", "tone"),
    [(SKILLED, 0.004, 3, ""), (LIKELY, 0.03, 2, ""), (NO_EVIDENCE, 0.4, 0, "is-neutral"), (NOT_ENOUGH, None, None, "is-none")],
)
def test_ux_dr35_the_pill_follows_the_verdict(store: Store, path: Path, verdict: Verdict, p: float | None,
                                              dots: int | None, tone: str) -> None:
    """UX-DR35, DESIGN.md Verdict pill: three, two or no filled dots on the accent or neutral tint, and for
    *Not enough data* a dashed pill with no dots; the Verdict is always text, read as "Verdict: …"."""
    tested = 12 if p is None else 120
    scan_id = held_up_scan(path, passers(verdict, p, tested), comparison())
    view = HoldUps(store).view(scan_id)
    assert view is not None and (view.cards[0].filled_dots, view.cards[0].tone) == (dots, tone)
    card = cards(hold_up(web_over(store), scan_id))[PASSERS]
    pill = re.search(r'<span class="verdict-pill([^"]*)">(.*?)</p>', card, re.S)
    assert pill and pill.group(1).strip() == tone
    assert pill.group(2).count("is-filled") == (dots or 0)
    assert ('class="pill-dots"' in pill.group(2)) == (dots is not None)
    assert f'<span class="visually-hidden">Verdict: </span>{verdict.value}' in pill.group(2)


# --- the page (UX-DR33, UX-DR35, AD-18) ----------------------------------------------------------------------


def test_ux_dr35_the_holdup_page(store: Store, path: Path) -> None:
    """UX-DR33, UX-DR35, UX-DR8, AD-18: the tab title, the shared Scan header, the two tabs as links in a navigation
    region named "Scan" with this page marked, the warning (read with "Warning:" first) above the two cards, each
    card a labelled section with its figures as a description list, the note and the Seed under them, and no script
    but the theme's."""
    scan_id = held_up_scan(path)
    html = hold_up(web_over(store), scan_id)
    assert "<title>Hold-up Test · 1 Jul 2025 · LiquidOracle</title>" in html
    assert '<p class="eyebrow">Wallet scan</p>' in html and "<h1>Scan of 2 Wallets</h1>" in html
    nav = re.search(r'<nav class="scan-tabs" aria-label="Scan">(.*?)</nav>', html, re.S)
    assert nav and re.findall(r'<a href="([^"]+)"( aria-current="page")?>([^<]+)</a>', nav.group(1)) == [
        (f"/scans/{scan_id}/watchlist", "", "Watchlist"), (f"/scans/{scan_id}/hold-up", ' aria-current="page"', "Hold-up Test"),
    ]
    assert 'role="tablist"' not in html and 'role="tab"' not in html
    assert re.search(r'<a href="/scans" aria-current="true">Scan wallets</a>', html)
    warning = re.search(r'<div class="warning group-warning" role="note">(.*?)</div>', html, re.S)
    assert warning and text(warning.group(1)) == f"Warning: {page.WARNING}"
    assert '<span class="visually-hidden">Warning: </span>' in warning.group(1)
    assert html.index("group-warning") < html.index('class="group-cards"') < html.index('class="group-note"')
    both = cards(html)
    assert '<h2 id="group-passers">Before-Cut-off Passers</h2>' in both[PASSERS]
    assert '<h2 id="group-comparison">Comparison Group</h2>' in both[COMPARISON]
    assert '<p class="group-odds">a trader with no edge would do this well fewer than 1 time in 10,000.</p>' in both[PASSERS]
    assert figures(both[PASSERS]) == [
        ("Resolved bets counted", "300"), ("Real PnL", "$6,000"), ("Wallets in the group", "10"),
        ("Wallets dropped (fewer than 10 bets after the Cut-off Date)", "7"), ("Wallets not fully read", "0"),
    ]
    assert [value for _, value in figures(both[COMPARISON])] == ["409", f"{phrases.MINUS}$19,217", "999", "996", "0"]
    assert f'<p class="group-note">{Markup.escape(page.NOTE)}</p>' in html
    assert '<p class="computed-on">Seed 44</p>' in html
    assert re.findall(r"<script([^>]*)>", html) == [' src="/static/js/theme.js"']
    assert "Error" not in html and "<table" not in html


def test_ux_dr33_the_watchlist_gets_the_holdup_tab(store: Store, path: Path) -> None:
    """UX-DR33: the Watchlist of a Scan with a stored Hold-up result has both tabs with *Watchlist* marked, and the
    header on the two pages is the same."""
    scan_id = held_up_scan(path)
    web = web_over(store)
    watch = web.get(f"/scans/{scan_id}/watchlist").get_data(as_text=True)
    nav = re.search(r'<nav class="scan-tabs" aria-label="Scan">(.*?)</nav>', watch, re.S)
    assert nav and re.findall(r'<a href="([^"]+)"( aria-current="page")?>([^<]+)</a>', nav.group(1)) == [
        (f"/scans/{scan_id}/watchlist", ' aria-current="page"', "Watchlist"), (f"/scans/{scan_id}/hold-up", "", "Hold-up Test"),
    ]
    head = re.compile(r'<div class="scan-head">.*?</dl>\s*</div>', re.S)
    assert head.search(watch).group(0) == head.search(hold_up(web, scan_id)).group(0)
    assert Watchlists(store).view(scan_id).header == HoldUps(store).view(scan_id).header


def test_ad15_the_page_names_the_scans_own_seed(store: Store, path: Path) -> None:
    """AD-15, AD-22: the Seed under the cards is the Scan's, not the app's setting."""
    scan_id = held_up_scan(path, seed=7)
    assert HoldUps(store).view(scan_id).seed == "Seed 7"
    assert '<p class="computed-on">Seed 7</p>' in hold_up(web_over(store), scan_id)


# --- the warning and the offline info box (FR-17, AD-13; Edvard, 2026-11-27) ---------------------------------


def test_fr17_close_dropped_shares_show_no_warning(store: Store, path: Path) -> None:
    """FR-17 (matrix "Shares close"): at exactly 20 points apart (20% against 40%) there is no warning box; one
    Wallet more dropped and it shows."""
    close = held_up_scan(path, passers(wallets=10, dropped=2), comparison(wallets=50, dropped=20))
    apart = held_up_scan(path, passers(wallets=10, dropped=2), comparison(wallets=50, dropped=21))
    web = web_over(store)
    assert HoldUps(store).view(close).warning == "" and "group-warning" not in hold_up(web, close)
    assert "Warning:" not in hold_up(web, close)
    assert HoldUps(store).view(apart).warning == page.WARNING and "group-warning" in hold_up(web, apart)


def test_fr17_offline_the_info_box_says_the_passers_are_made_up_and_why_the_warning_shows(store: Store, path: Path) -> None:
    """FR-17, NFR-13, AD-13 (Edvard, 2026-11-27: decision Q1 and his addition): in Offline Mode an info box sits
    under the warning and above the cards, saying the tested Passers are made-up Wallets, not real traders, and why
    the warning shows on the Sample Dataset."""
    scan_id = held_up_scan(path)
    html = hold_up(offline_over(store), scan_id)
    box = re.search(r'<div class="info-box" role="note" id="offline-note">(.*?)</div>', html, re.S)
    assert box and text(box.group(1)) == f"{page.OFFLINE_PASSERS} {page.OFFLINE_WARNING}"
    assert html.index("group-warning") < html.index('id="offline-note"') < html.index('class="group-cards"')
    assert "Offline Mode</strong>" in html  # the pill: the same value shows both (AD-13)
    # UX-DR11: the offline page too has one main heading, then the two cards' titles (the box adds no heading)
    assert re.findall(r"<h([1-6])[ >]", html) == ["1", "2", "2"]


def test_fr17_offline_without_the_warning_the_box_keeps_only_its_first_sentence(store: Store, path: Path) -> None:
    """FR-17 (matrix "Shares close"): offline with close dropped shares the box does not explain a warning that is not
    there."""
    scan_id = held_up_scan(path, passers(wallets=10, dropped=2), comparison(wallets=50, dropped=12))
    html = hold_up(offline_over(store), scan_id)
    box = re.search(r'id="offline-note">(.*?)</div>', html, re.S)
    assert box and text(box.group(1)) == page.OFFLINE_PASSERS
    assert "The warning above" not in html and "group-warning" not in html


@pytest.mark.parametrize("flagged", [True, False])
def test_ad13_a_live_run_never_shows_the_offline_info_box(store: Store, path: Path, flagged: bool) -> None:
    """AD-13 (matrix "Live run"): the box belongs to the Sample Dataset, so a live run has none, with or without the
    warning."""
    groups = () if flagged else (passers(wallets=10, dropped=2), comparison(wallets=50, dropped=12))
    scan_id = held_up_scan(path, *groups)
    html = hold_up(web_over(store), scan_id)
    assert ("group-warning" in html) == flagged
    assert "offline-note" not in html and "Sample Dataset" not in html and "made-up" not in html


def test_fr17_the_box_does_not_speak_of_tested_passers_when_none_is_tested(store: Store, path: Path) -> None:
    """FR-17: with every Passer dropped (or no Passer at all) no Passer is tested, so the box's first sentence, about
    "the Passers tested here", is left out; offline with nothing to say, there is no box."""
    dropped = held_up_scan(path, passers(NOT_ENOUGH, None, 0, 0.0, wallets=6, dropped=3), comparison(wallets=50, dropped=45))
    none = held_up_scan(path, passers(NOT_ENOUGH, None, 0, 0.0, wallets=0, dropped=0), comparison())
    assert HoldUps(store).view(dropped).offline_notes == (page.OFFLINE_PASSERS, page.OFFLINE_WARNING)  # 50% against 90%
    all_dropped = held_up_scan(path, passers(NOT_ENOUGH, None, 0, 0.0, wallets=6, dropped=6), comparison(wallets=500, dropped=499))
    assert HoldUps(store).view(all_dropped).offline_notes == ()  # 100% against 99.8%: no Passer tested, no warning
    assert HoldUps(store).view(none).offline_notes == ()
    assert "offline-note" not in hold_up(offline_over(store), none)


def test_fr17_the_box_explains_the_warning_only_when_the_comparison_group_dropped_more(store: Store, path: Path) -> None:
    """FR-17 (review, Story 5.2): the box's second sentence gives the coin-flippers in the Comparison Group as the
    reason for the warning. When the warning shows because the Passers were dropped more (80% against 24%, or 100%
    against 60%), that is not the reason, so the sentence is left out; the warning itself still shows."""
    more = held_up_scan(path, passers(wallets=10, dropped=8), comparison(wallets=50, dropped=12))
    every = held_up_scan(path, passers(NOT_ENOUGH, None, 0, 0.0, wallets=6, dropped=6), comparison(wallets=50, dropped=30))
    assert HoldUps(store).view(more).warning == page.WARNING
    assert HoldUps(store).view(more).offline_notes == (page.OFFLINE_PASSERS,)
    assert HoldUps(store).view(every).warning == page.WARNING and HoldUps(store).view(every).offline_notes == ()
    html = hold_up(offline_over(store), more)
    assert "group-warning" in html and "The warning above" not in html
    assert "offline-note" not in hold_up(offline_over(store), every)


# --- the states (UX-DR35, EXPERIENCE.md State Patterns) ------------------------------------------------------


def test_fr17_no_passers_shows_the_sentence_and_still_the_comparison_group(store: Store, path: Path) -> None:
    """FR-17, UX-DR35 (matrix "No Passers"; Edvard, 2026-11-27, decision Q2): the Passers card holds only the
    sentence, the Comparison Group card still shows its own result, and no warning is set."""
    scan_id = held_up_scan(path, passers(NOT_ENOUGH, None, 0, 0.0, wallets=0, dropped=0), comparison())
    html = hold_up(web_over(store), scan_id)
    both = cards(html)
    assert text(both[PASSERS]) == f"Before-Cut-off Passers {WHO_PASSERS} {''.join(page.NO_PASSERS)}"
    assert "verdict-pill" not in both[PASSERS] and "<dl" not in both[PASSERS]
    assert '<p class="empty-note">' + page.NO_PASSERS[0] + "</p>" in both[PASSERS]
    assert "Verdict: </span>No evidence of skill" in both[COMPARISON]
    assert [value for _, value in figures(both[COMPARISON])] == ["800", f"{phrases.MINUS}$310", "50", "12", "3"]
    assert "group-warning" not in html


def test_fr17_an_empty_comparison_group_shows_its_sentence(store: Store, path: Path) -> None:
    """FR-17, UX-DR35 (matrix "Empty Comparison Group"): that card holds only its sentence, *Not enough data* in
    italics; the Passers card is whole and no warning is set."""
    scan_id = held_up_scan(path, passers(), comparison(NOT_ENOUGH, None, 0, 0.0, wallets=0, dropped=0, unread=0))
    html = hold_up(web_over(store), scan_id)
    both = cards(html)
    assert ("<p class=\"empty-note\">No Wallets in this group: every scanned Wallet passed or had <em>Not enough data</em>"
            " before the Cut-off Date.</p>") in both[COMPARISON]
    assert "verdict-pill" not in both[COMPARISON] and "<dl" not in both[COMPARISON]
    assert len(figures(both[PASSERS])) == 5 and "group-warning" not in html


def test_fr17_a_group_too_small_shows_not_enough_data_with_its_count(store: Store, path: Path) -> None:
    """FR-17, FR-10 (matrix "Group too small"): 12 pooled bets give the dashed *Not enough data* pill, the Verdict
    card's sentence with the count, and still the five figures."""
    scan_id = held_up_scan(path, passers(NOT_ENOUGH, None, 12, -40.0, wallets=3, dropped=2), comparison())
    card = cards(hold_up(web_over(store), scan_id))[PASSERS]
    assert '<span class="verdict-pill is-none">' in card and "pill-dot" not in card
    assert '<p class="group-odds">12 resolved bets; at least 30 are needed for a Verdict (18 more)</p>' in card
    assert [value for _, value in figures(card)] == ["12", f"{phrases.MINUS}$40", "3", "2", "0"]


def test_fr17_passers_that_all_stopped_betting_are_not_an_empty_group(store: Store, path: Path) -> None:
    """FR-17, FR-10 (found by a planted bug, Story 5.2): a group whose Wallets were all dropped still has Wallets, so
    its card shows *Not enough data* with 0 bets and its figures (6 Wallets, 6 dropped), not the sentence for a
    group with no Wallets. It is what the offline Scan's Passers would show without the three made-up Wallets."""
    scan_id = held_up_scan(path, passers(NOT_ENOUGH, None, 0, 0.0, wallets=6, dropped=6), comparison(wallets=50, dropped=30))
    view = HoldUps(store).view(scan_id)
    assert view is not None and view.cards[0].empty is None
    card = cards(hold_up(web_over(store), scan_id))[PASSERS]
    assert "".join(page.NO_PASSERS) not in text(card) and "empty-note" not in card
    assert '<span class="verdict-pill is-none">' in card
    assert '<p class="group-odds">0 resolved bets; at least 30 are needed for a Verdict (30 more)</p>' in card
    assert [value for _, value in figures(card)] == ["0", "$0", "6", "6", "0"]


# --- not found (Story 5.1's matrix "Older Scan"; AD-5) --------------------------------------------------------


def test_fr17_a_scan_from_before_the_holdup_test_has_no_tab_and_no_page(store: Store, path: Path) -> None:
    """FR-17, UX-DR33 (matrix "Older Scan"): a finished Scan with no stored Hold-up rows shows its Watchlist with
    one tab and no link to a Hold-up page, and that address is *Page not found*. One row alone is no result either."""
    older = hand_scan(path, [Row(wallet(1))])
    half = hand_scan(path, [Row(wallet(2))])
    hand_groups(path, half, passers())
    web = web_over(store)
    for scan_id in (older, half):
        watch = web.get(f"/scans/{scan_id}/watchlist")
        assert watch.status_code == 200
        html = watch.get_data(as_text=True)
        nav = re.search(r'<nav class="scan-tabs" aria-label="Scan">(.*?)</nav>', html, re.S)
        assert nav and re.findall(r"<a [^>]*>([^<]+)</a>", nav.group(1)) == ["Watchlist"]
        assert "hold-up" not in html
        assert HoldUps(store).view(scan_id) is None
        reply = web.get(f"/scans/{scan_id}/hold-up")
        assert reply.status_code == 404 and "Page not found" in reply.get_data(as_text=True)


@pytest.mark.parametrize("step", ["created", "markets", "shortlisted", "ranked"])
def test_fr17_an_unfinished_scan_has_no_holdup_page(store: Store, path: Path, step: str) -> None:
    """FR-17, AD-5 (matrix "Unknown or unfinished Scan"): results of a Scan that is not finished are never shown,
    even if rows were there."""
    scan_id = held_up_scan(path, step=step)
    assert HoldUps(store).view(scan_id) is None
    assert web_over(store).get(f"/scans/{scan_id}/hold-up").status_code == 404


def test_fr17_an_unknown_scan_is_not_found(store: Store, path: Path) -> None:
    """FR-17, UX-DR7 (matrix "Unknown or unfinished Scan"): a Scan that does not exist, or an address that is not a
    number, is *Page not found*; the page answers GET only."""
    scan_id = held_up_scan(path)
    web = web_over(store)
    for url in (f"/scans/{scan_id + 1}/hold-up", "/scans/abc/hold-up", f"/scans/{scan_id}/hold-up/x", f"/scans/{scan_id}/holdup"):
        reply = web.get(url)
        assert reply.status_code == 404 and "Page not found" in reply.get_data(as_text=True), url
    assert web.post(f"/scans/{scan_id}/hold-up").status_code == 404
    assert HoldUps(store).view(scan_id + 1) is None


# --- stored rows only (AD-22) --------------------------------------------------------------------------------


def test_ad22_the_page_only_reads_what_the_scan_stored(store: Store, path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-22, FR-17: opening the page runs no test again and writes nothing: the Scan's Hold-up phase, the pooled
    test and the Skill Test are not called, no frozen snapshot is read, and the database is unchanged. (The header
    still counts the Scan's stored results, Markets and shortlist, as on the Watchlist.)"""
    scan_id = held_up_scan(path)

    def never(*args: object, **kwargs: object) -> None:
        raise AssertionError("the Hold-up page tested or read a Wallet again")

    for owner, name in (
        (scan_module, "hold_up_scan"), (scan_module, "hold_up_members"), (core_holdup, "hold_up"),
        (core_holdup, "skill_test"), (skilltest, "skill_test"), (Store, "snapshot"), (Store, "finish_scan"),
    ):
        monkeypatch.setattr(owner, name, never)
    web = web_over(store)
    db = store._connection()
    changes = db.total_changes
    assert "999" in hold_up(web, scan_id)
    assert db.total_changes == changes
    assert store.group_results(scan_id) == (OFFLINE_PASSERS, OFFLINE_COMPARISON)


# --- the README's offline result (NFR-13; PRD §6.1 2b) -------------------------------------------------------


def readme_section() -> str:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    found = re.search(r"\n## The Hold-up Test on the Sample Dataset\n(.*?)\n## ", readme, re.S)
    assert found, "the README has no Hold-up result section"
    return found.group(1)


def test_nfr13_the_readme_reports_the_offline_holdup_result() -> None:
    """NFR-13, PRD §6.1 2b: the README states the offline Scan's Hold-up result for both groups in the words the
    page shows. Every number comes from `OFFLINE_PASSERS` and `OFFLINE_COMPARISON`, which are built from results
    other tests compute (see their comment), so a changed result that is not written into the README fails here."""
    section = readme_section()
    assert f"{len(LUCKY_COIN_FLIPPERS)} coin-flippers that passed by luck" in " ".join(section.split())
    for group in (OFFLINE_PASSERS, OFFLINE_COMPARISON):
        row = next(line for line in section.splitlines() if line.startswith(f"| {page.TITLES[group.group]} |"))
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert cells[1:] == [
            f"*{group.verdict.value}*", phrases.odds(group.p_value), phrases.count(group.tested_count),
            phrases.money(group.real_pnl), phrases.count(group.wallets), phrases.count(group.dropped),
            phrases.count(group.not_fully_read),
        ], row


def test_nfr13_the_readme_states_the_results_limits() -> None:
    """NFR-13, FR-17 (epics 5.2; Edvard, 2026-11-18 and 2026-11-27): the README says what the offline result
    cannot show: only 8 real Wallets, picked, not a full Scan; no real Wallet among the Passers; the Comparison
    Group resting on 3 real Wallets with 307 of its 409 bets from one; and why the dropped-share warning shows."""
    section = " ".join(readme_section().split())
    for needed in (
        "8 real Wallets", "0xd218e4", "0x63d43b", "not a full Scan",
        "No real Wallet is among the Passers", "made-up",
        "3 real Wallets", "307 of its 409 bets", "0xd3a6e5",
        "coin-flippers have no bets after the Cut-off Date", "The rule is not changed to hide it",
        "each keep their own price",
    ):
        assert needed in section, needed
