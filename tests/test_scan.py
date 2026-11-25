"""The Scan funnel end to end: Market set, candidates, shortlist, ranking (FR-16, AD-7, AD-9, AD-10, AD-21).

The real client runs on a routed fake (`FakeScan`): hand-made funnel Markets and holder rows, and
real Wallets cut from the Sample Dataset capture as the shortlisted Wallets. No socket is opened (AD-17).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fake_polymarket import TIMEOUT, FakeClock, FakePolymarket, FakeScan, FakeTransport, status

from liquidoracle.core.positions import build_positions
from liquidoracle.core.skilltest import real_pnl, skill_test
from liquidoracle.data.errors import PolymarketUnavailable
from liquidoracle.data.polymarket import MARKET_ROW_CAP, PolymarketClient, parse_time
from liquidoracle.data.window import WINDOW_LIMIT, cutoff_at, positions_near
from liquidoracle.records import Candidate, RankedWallet, ScanFunnel
from liquidoracle.services import scan

DAY = date(2025, 7, 1)  # the Sample Dataset's Cut-off Date
CUT = cutoff_at(DAY)
ONE_DAY = 86_400

# Real Wallets from the capture, and their Real PnL before 1 July 2025 as the funnel ranks them.
SMALL = "0x29306ddc4724e24a23bf1c8679aa034376ea9dcb"  # small-clean: about +$0.83
LOSERS = "0x94884db79666a1a34c46d03fb4f8e9cbcaf6b5a6"  # open-losers: about -$0.42
FEES = "0x0915962b4c6bc4505e7434a0de815a596a6667c3"  # fees-and-open: about -$29,397
AFTER = "0x7298060b1844a4c4ca0578146ab3f5e76aa1fcfc"  # after-part: never shortlisted at N = 2
FIXTURES = ("small-clean", "open-losers", "fees-and-open", "after-part")

CONTRACT = "0x" + "c" * 40  # refused as a protocol contract address
REFUSED = "0x" + "b" * 40  # refused with another 400
EMPTY = "0x" + "e" * 40  # no Polymarket history
FILLER = "0x" + "f" * 40  # a candidate below the shortlist
CAPPED_ONLY, TIMED_ONLY, LATE, OLD, UNCLEAR = ("0x" + d * 40 for d in "12345")


def cid(n: int) -> str:
    return f"0x{n:064x}"


USED_1, USED_2, CAPPED, TIMED, LATE_M, OLD_M, UNCLEAR_M = (cid(n) for n in range(1, 8))


def gamma_time(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%d %H:%M:%S+00")


def funnel_market(n: int, closed_at: int, volume: float, prices: tuple[str, str] = ("1", "0")) -> dict[str, Any]:
    """A Market as Gamma's volume-ordered list returns it; its tokens are "<n>1" (Yes) and "<n>2" (No)."""
    return {
        "conditionId": cid(n),
        "closed": True,
        "closedTime": gamma_time(closed_at),
        "outcomes": '["Yes", "No"]',
        "outcomePrices": json.dumps(list(prices)),
        "clobTokenIds": json.dumps([f"{n}1", f"{n}2"]),
        "volumeNum": volume,
    }


def holder(wallet: str, condition_id: str, token: str, *, pnl: float = 0.0, size: float = 0.0, avg: float = 0.5) -> dict[str, Any]:
    return {
        "proxy_wallet": wallet, "condition_id": condition_id, "token_id": token,
        "realized_pnl": pnl, "current_size": size, "avg_price": avg,
    }


# 15,000 CLOSED rows: the capped Market reads every one of them and still gives no candidate.
CAPPED_ROWS = [holder(CAPPED_ONLY, CAPPED, "31", pnl=1e9)] + [
    holder(f"0x{n:040x}", CAPPED, "31", pnl=1.0) for n in range(1, MARKET_ROW_CAP)
]


def scenario() -> FakeScan:
    """Seven Markets around 1 July 2025; four are in the set by volume, two of them partial.

    Estimates in the used Markets: CONTRACT 900, SMALL 500, LOSERS 400 (an OPEN winner), FEES 300,
    REFUSED 200, EMPTY 100 (with an unredeemed loser), AFTER 50, FILLER -5. At N = 2 the shortlist
    is the first six.
    """
    server = FakeScan(FIXTURES)
    server.funnel = [
        funnel_market(5, CUT + 2 * ONE_DAY, 2e7),  # resolved after the cut-off: out
        funnel_market(6, CUT - 91 * ONE_DAY, 1.5e7),  # before the window: out
        funnel_market(7, CUT - 3 * ONE_DAY, 1e7, ("0.5", "0.5")),  # unclear: out
        funnel_market(3, CUT - 5 * ONE_DAY, 9e6),  # CLOSED list reaches the cap: partial
        funnel_market(4, CUT - 20 * ONE_DAY, 8e6),  # OPEN list times out every try: partial
        funnel_market(1, CUT - 10 * ONE_DAY, 5e6),  # Yes won
        funnel_market(2, CUT - 80 * ONE_DAY, 4e6, ("0", "1")),  # No won
    ]
    server.holders = {
        (USED_1, "CLOSED"): [
            holder(SMALL, USED_1, "11", pnl=500), holder(CONTRACT, USED_1, "12", pnl=900),
            holder(FEES, USED_1, "11", pnl=300), holder(REFUSED, USED_1, "11", pnl=250),
            holder(EMPTY, USED_1, "11", pnl=130), holder(AFTER, USED_1, "12", pnl=50), holder(FILLER, USED_1, "12", pnl=-5),
        ],
        (USED_1, "OPEN"): [holder(LOSERS, USED_1, "11", size=500, avg=0.2)],  # winner held: 500 x (1 - 0.2)
        (USED_2, "CLOSED"): [holder(REFUSED, USED_2, "21", pnl=-50)],
        (USED_2, "OPEN"): [holder(EMPTY, USED_2, "21", size=100, avg=0.3)],  # unredeemed loser: -100 x 0.3
        (CAPPED, "CLOSED"): CAPPED_ROWS,
        (TIMED, "CLOSED"): [holder(TIMED_ONLY, TIMED, "41", pnl=1e9)],
        (LATE_M, "CLOSED"): [holder(LATE, LATE_M, "51", pnl=1e9)],
        (OLD_M, "CLOSED"): [holder(OLD, OLD_M, "61", pnl=1e9)],
        (UNCLEAR_M, "CLOSED"): [holder(UNCLEAR, UNCLEAR_M, "71", pnl=1e9)],
    }
    server.holder_answers[(TIMED, "OPEN")] = TIMEOUT
    server.refuse[CONTRACT] = status(400, b'{"error": "protocol contract address"}')
    server.refuse[REFUSED] = status(400, b'{"error": "bad request"}')
    return server


def live(server: FakeScan | FakePolymarket) -> tuple[PolymarketClient, FakeTransport]:
    clock = FakeClock()
    transport = FakeTransport(clock=clock, answer=server)
    return PolymarketClient(5.0, transport=transport, clock=clock, sleep=clock.sleep), transport


def run(server: FakeScan, size: int = 2) -> tuple[ScanFunnel, FakeTransport]:
    client, transport = live(server)
    return scan.run_funnel(client, DAY, size), transport


def verdict_real_pnl(name: str) -> float:
    """The Real PnL the Skill Test stores for the fixture Wallet's before part, read through a fresh client."""
    server = FakePolymarket(name)
    window = positions_near(live(server)[0], server.wallet, DAY, "before")
    built = build_positions(window.activity, {m.condition_id: m for m in window.markets}, listed=window.positions,
                            not_fully_read=window.not_fully_read())
    return skill_test(built, seed=44, unit_id=server.wallet).real_pnl


def test_the_whole_funnel_on_one_cut_off_date() -> None:
    """FR-16, AD-9, AD-21: the Market set by volume, two Markets not used: partial, the candidates of the used ones,
    the 3 x N shortlist, the contract dropped, and every other shortlisted Wallet ranked with the top N marked."""
    result, _ = run(scenario())
    assert (result.cutoff, result.size) == (CUT, 2)
    assert [(m.market.condition_id, m.volume) for m in result.markets] == [
        (CAPPED, 9e6), (TIMED, 8e6), (USED_1, 5e6), (USED_2, 4e6),
    ]
    assert result.partial == (CAPPED, TIMED) and result.used_count == 2
    assert result.candidate_count == 8  # CONTRACT, SMALL, LOSERS, FEES, REFUSED, EMPTY, AFTER, FILLER
    assert result.shortlist == (
        Candidate(CONTRACT, 900.0), Candidate(SMALL, 500.0), Candidate(LOSERS, pytest.approx(400.0)),
        Candidate(FEES, 300.0), Candidate(REFUSED, 200.0), Candidate(EMPTY, pytest.approx(100.0)),
    )
    assert result.contracts == (CONTRACT,)
    assert [(w.wallet, w.top, w.not_fully_read, w.refused) for w in result.ranked] == [
        (SMALL, True, False, False),
        (REFUSED, True, True, True),  # $0, the same rule as every Wallet; first of the two at $0 by address
        (EMPTY, False, False, False),  # no history: $0, not flagged
        (LOSERS, False, False, False),
        (FEES, False, False, False),
    ]
    assert [w.wallet for w in result.top] == [SMALL, REFUSED]
    assert (result.not_fully_read_count, result.refused_count) == (1, 1)


def test_ranking_uses_the_skill_tests_real_pnl_on_real_wallets() -> None:
    """AD-10, AD-21: each real Wallet is ranked on its before part's Real PnL, the very number its Skill Test stores."""
    result, _ = run(scenario())
    pnl = {w.wallet: w.real_pnl for w in result.ranked}
    assert pnl[SMALL] == verdict_real_pnl("small-clean") == pytest.approx(0.83, abs=0.005)
    assert pnl[LOSERS] == verdict_real_pnl("open-losers") == pytest.approx(-0.42, abs=0.005)
    assert pnl[FEES] == verdict_real_pnl("fees-and-open") == pytest.approx(-29397.13, abs=0.005)
    assert pnl[REFUSED] == pnl[EMPTY] == 0.0


def test_every_market_anchored_request_carries_the_time_sort() -> None:
    """AD-9: every Market-anchored request of a whole funnel run sends `sort_by=TIMESTAMP&sort_direction=ASC`."""
    _, transport = run(scenario())
    anchored = [c.query for c in transport.calls if "condition" in c.query]
    assert len(anchored) >= 4 + 15  # both lists of the used Markets, and the capped list's 15 pages
    assert all((q["sort_by"], q["sort_direction"]) == ("TIMESTAMP", "ASC") for q in anchored)


def test_a_capped_market_gives_no_candidates_though_its_rows_were_read() -> None:
    """AD-9 (Edvard, 2026-11-25): a CLOSED list that reaches 15,000 rows makes its Market partial; none of its
    holders is a candidate, and its OPEN list is not read."""
    result, transport = run(scenario())
    capped_calls = [c.query for c in transport.calls if c.query.get("condition") == CAPPED]
    assert len(capped_calls) == 15 and {q["status"] for q in capped_calls} == {"CLOSED"}
    assert CAPPED in result.partial
    assert CAPPED_ONLY not in {c.wallet for c in result.shortlist}


def test_a_market_whose_list_timed_out_every_try_is_partial_and_the_scan_goes_on() -> None:
    """AD-9, AD-3: a list whose every try timed out leaves its Market "not used: partial", and the funnel goes on."""
    result, transport = run(scenario())
    assert sum(1 for c in transport.calls if c.query.get("condition") == TIMED and c.query["status"] == "OPEN") == 3
    assert TIMED in result.partial
    assert TIMED_ONLY not in {c.wallet for c in result.shortlist}


def test_markets_outside_the_set_are_never_read() -> None:
    """AD-21, AD-7: Markets resolved after the cut-off or before the window, and unclear ones, are not in the set;
    their holders are never asked for and never become candidates."""
    result, transport = run(scenario())
    asked = {c.query["condition"] for c in transport.calls if "condition" in c.query}
    assert asked == {USED_1, USED_2, CAPPED, TIMED}
    assert not {LATE, OLD, UNCLEAR} & {c.wallet for c in result.shortlist}


def test_a_refused_market_list_leaves_the_market_unused() -> None:
    """AD-9: a Market list Polymarket refuses with a 4xx is not complete, so the Market is not used: partial."""
    server = scenario()
    server.holder_answers[(USED_2, "OPEN")] = status(400, b'{"error": "bad request"}')
    result, _ = run(server)
    assert result.partial == (CAPPED, TIMED, USED_2)
    assert result.candidate_count == 8  # every candidate also holds USED_1
    assert dict((c.wallet, c.estimate) for c in result.shortlist)[EMPTY] == 130.0  # USED_2's loser no longer counts


def test_an_outage_on_a_market_list_stops_the_funnel() -> None:
    """AD-9, AD-3: any `PolymarketUnavailable` other than all timeouts propagates; Story 4.3 makes the job `stopped`."""
    server = scenario()
    server.holder_answers[(USED_1, "OPEN")] = status(503)
    with pytest.raises(PolymarketUnavailable):
        run(server)


def test_an_outage_on_a_wallet_read_stops_the_funnel() -> None:
    """AD-9, AD-3: a shortlisted Wallet's read that keeps failing is never skipped: the funnel stops."""
    server = scenario()
    server.refuse[SMALL] = status(503)
    with pytest.raises(PolymarketUnavailable):
        run(server)


def test_a_wallet_not_fully_read_is_flagged_and_ranked_on_what_was_read() -> None:
    """AD-9, AD-11: a shortlisted Wallet whose activity read stops early is kept, flagged "not fully read", and
    ranked on the Real PnL of the Positions that were read."""
    def cut_short(server: FakePolymarket) -> FakePolymarket:
        server.page_size = 20
        server.timeout_from_page["ACTIVITY"] = 1  # the activity read keeps timing out from its second page
        return server

    reference = cut_short(FakePolymarket("fees-and-open"))
    window = positions_near(live(reference)[0], FEES, DAY, "before", WINDOW_LIMIT)
    assert window.not_fully_read()
    built = build_positions(window.activity, {m.condition_id: m for m in window.markets}, listed=window.positions,
                            not_fully_read=window.not_fully_read())
    expected = real_pnl(built)
    assert expected != 0.0 and expected != verdict_real_pnl("fees-and-open")

    server = scenario()
    cut_short(server.wallets[FEES])
    result, _ = run(server)
    (ranked,) = [w for w in result.ranked if w.wallet == FEES]
    assert ranked.not_fully_read and not ranked.refused
    assert ranked.real_pnl == expected
    assert result.not_fully_read_count == 2


def test_with_few_candidates_all_are_kept() -> None:
    """AD-21: with fewer candidates than 3 x N, all are shortlisted; with fewer ranked than N, all are in the top N."""
    result, _ = run(scenario(), size=500)
    assert len(result.shortlist) == result.candidate_count == 8
    assert len(result.ranked) == 7 and all(w.top for w in result.ranked)
    assert {w.wallet: w.real_pnl for w in result.ranked}[FILLER] == 0.0  # no history


def test_a_refused_wallet_is_not_kept_for_being_refused() -> None:
    """AD-9 (Edvard, 2026-11-25, Story 4.2): at N = 1 the refused Wallet, at $0, is ranked but not in the top N."""
    result, _ = run(scenario(), size=1)
    assert [w.wallet for w in result.top] == [SMALL]
    assert len(result.shortlist) == 3  # CONTRACT, SMALL, LOSERS
    assert [w.wallet for w in result.ranked] == [SMALL, LOSERS]


def test_the_funnel_reads_no_market_trades_activity_or_leaderboard() -> None:
    """AD-9, AD-2: no `/v2/activity?condition=`, no `/v2/trades` and no leaderboard; Market lists are positions lists."""
    _, transport = run(scenario())
    for call in transport.calls:
        assert not call.url.endswith(("/v2/trades", "/trades")) and "leaderboard" not in call.url
        if call.url.endswith("/v2/activity"):
            assert "condition" not in call.query and "user" in call.query


def flip_outcomes_from(markets: list[dict[str, Any]], cut: int) -> int:
    """Swap the outcome of every Market resolved on or after `cut`; returns how many changed."""
    flipped = 0
    for market in markets:
        if market.get("closedTime") and parse_time(market["closedTime"]) >= cut and market.get("outcomePrices"):
            prices = json.loads(market["outcomePrices"])
            if sorted(float(p) for p in prices) == [0.0, 1.0]:
                market["outcomePrices"] = json.dumps(list(reversed(prices)))
                flipped += 1
    return flipped


def test_outcomes_after_the_cut_off_cannot_change_the_funnel() -> None:
    """FR-16, AD-7, AD-21 (the leak test): changing the outcome of every Market resolved on or after the cut-off,
    in the shortlisted Wallets' data and in Gamma's answers, leaves the Market set, shortlist and top N identical."""
    before, _ = run(scenario())
    server = scenario()
    flipped = sum(flip_outcomes_from(wallet.gamma, CUT) for wallet in server.wallets.values())
    flipped += flip_outcomes_from(server.funnel, CUT)
    assert flipped >= 30  # small-clean 12, fees-and-open 23 (some open), after-part 44, and the late funnel Market
    after, _ = run(server)
    assert after == before
    assert after.markets == before.markets and after.shortlist == before.shortlist and after.top == before.top


def test_the_leak_test_would_catch_a_ranking_on_the_whole_history(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-16, AD-7: planted check of the leak test: ranking on a lookup window (no cut-off) does change with outcomes
    after the cut-off, so the test above fails on such a leak."""
    def leaky(client: Any, wallet: str, cutoff: date, side: str, limit: int) -> Any:
        return positions_near(client, wallet, limit=limit)

    monkeypatch.setattr(scan, "positions_near", leaky)
    before, _ = run(scenario())
    server = scenario()
    for wallet in server.wallets.values():
        flip_outcomes_from(wallet.gamma, CUT)
    after, _ = run(server)
    assert after.ranked != before.ranked


@pytest.mark.parametrize("size", [0, -3, True, 2.5])
def test_a_bad_size_is_refused_before_any_request(size: object) -> None:
    """FR-16, AD-21: N is a whole number of 1 or more; nothing is sent otherwise."""
    client, transport = live(scenario())
    with pytest.raises(ValueError):
        scan.run_funnel(client, DAY, size)  # type: ignore[arg-type]
    assert transport.calls == []


def test_the_cut_off_is_a_date() -> None:
    """AD-7: the funnel takes the Cut-off Date as a date, converted in one place; a datetime is refused."""
    client, transport = live(scenario())
    with pytest.raises(TypeError):
        scan.run_funnel(client, datetime(2025, 7, 1, tzinfo=UTC), 2)
    assert transport.calls == []


def test_the_funnel_constants() -> None:
    """AD-21: 90 days, the top 100 Markets, a 3 x N shortlist and N = 200 by default, each an [ASSUMPTION]."""
    assert (scan.MARKET_DAYS, scan.MARKET_COUNT, scan.SHORTLIST_FACTOR, scan.DEFAULT_SIZE) == (90, 100, 3, 200)


def test_rank_wallet_outcomes_one_by_one() -> None:
    """AD-9: a contract is dropped (None), a refused Wallet is flagged at $0, a Wallet with no history is $0 unflagged."""
    client, _ = live(scenario())
    assert scan.rank_wallet(client, CONTRACT, DAY) is None
    assert scan.rank_wallet(client, REFUSED, DAY) == RankedWallet(REFUSED, 0.0, not_fully_read=True, refused=True)
    assert scan.rank_wallet(client, EMPTY, DAY) == RankedWallet(EMPTY, 0.0)
