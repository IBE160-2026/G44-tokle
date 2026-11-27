"""The Synthetic Wallets of FR-13 (stage 1), whose correct answers are known in advance.

Each Wallet is written as fills (activity rows) first; its Markets, positions-list rows and
price paths are then derived from those fills (AD-14). Every tested bet has its own two-outcome
Market, 100 shares and no fees. The stage 1 Wallets bet only before the default Cut-off Date
(2025-07-01); the stage 2 Wallets (steady sharp, forecaster, speed trader; Story 4.6) bet on both
sides of it, and the forecaster and speed trader have price paths around their later buys.

The offline Scan (Story 4.6) finds Wallets the normal way, through a fixed set of high-volume
anchor Markets inside the default funnel window: the four Wallets FR-16 expects on the offline
Watchlist and the coin-flippers each hold one small Position in every anchor Market, sold before
it resolves, so it never reaches a Skill Test (AD-11, AD-14, AD-21). The anchors' volumes are in
`funnel-markets.json`, written next to the committed Wallets.

Randomness: uniform draws from sha256 of (GENERATOR_SEED, Wallet, bet, purpose), standard
library only, never the `SEED` setting, `random` or `hash()` (AD-14, AD-15; Edvard, 2026-11-13).
The same code therefore gives the same bytes on every OS, Python and numpy version (FR-13).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from liquidoracle.data.sample_json import write_funnel, write_wallet
from liquidoracle.records import ActivityRow, ListedPosition, Market, PricePoint, SampleWallet

GENERATOR_SEED = 20261113  # the generator's own fixed constant (AD-14), not the SEED setting
SHARES = 100.0  # shares per bet: keeps the hand values round (sharp trader: $2,000.00)
START = 1_735_689_600  # 2025-01-01 00:00 UTC; 100 daily bets end well before 2025-07-01
CUTOFF = 1_751_328_000  # 2025-07-01 00:00 UTC, the default Cut-off Date: stage 2 Wallets' later bets start here
DAY = 86_400
MINUTE = 60
COIN_FLIPPERS = 1000
COIN_FLIPPER_BETS = 100
STOP_LOSS_PRICE = 0.25  # Edvard, 2026-11-13

SMALL_DIR = Path("sample_data") / "synthetic"  # committed
COIN_FLIPPER_DIR = Path("instance") / "synthetic" / "coin-flippers"  # git-ignored (FR-12)
FUNNEL_FILE = "funnel-markets.json"  # the anchor Markets' volumes, in SMALL_DIR (Story 4.6)

# The anchor Markets (AD-14, Story 4.6): resolution time and volume in USD, inside the default funnel
# window (the 90 days before 2025-07-01). [ASSUMPTION] 3 Markets and these volumes (2026-11-27).
ANCHORS = (
    (1_747_267_200, 3_000_000.0),  # 2025-05-15
    (1_748_736_000, 2_000_000.0),  # 2025-06-01
    (1_749_945_600, 1_000_000.0),  # 2025-06-15
)
ANCHOR_SHARES = 10.0  # one small Position per anchor, bought and sold at the same price: no Exit PnL
ANCHOR_PRICE = 0.50

# The price paths (FR-13, AD-14): one point a minute from 2 minutes before to 32 minutes after each
# later buy, the window the Copy Test reads (Epic 6).
PATH_MINUTES = range(-2, 33)
DRIFT_MINUTES = 240  # [ASSUMPTION] the forecaster's price reaches the outcome over 4 hours (2026-11-27)


PathKind = Literal["drift", "jump"]  # forecaster, speed trader


@dataclass(frozen=True, slots=True)
class _Bet:
    price: float
    won: bool  # did the outcome the Wallet bought win
    sell_price: float | None = None  # sold everything at this price before resolution
    bought_at: int | None = None  # None: START + its index in days
    path: PathKind | None = None  # its price path around the buy (forecaster, speed trader)


def uniform(wallet: str, bet: int, purpose: str) -> float:
    """A number in [0, 1) fixed by its inputs (AD-15 note, Story 1.3)."""
    digest = hashlib.sha256(f"{GENERATOR_SEED}:{wallet}:{bet}:{purpose}".encode()).digest()
    # 53 bits, a float's precision: 64 bits / 2**64 can round up to exactly 1.0 (review, 2026-11-13).
    return (int.from_bytes(digest[:8], "big") >> 11) / 2**53


SMALL_NAMES = (
    "hand-check", "favourite-buyer", "sharp-trader", "thin-wallet", "stop-loss-trader",
    "steady-sharp", "forecaster", "speed-trader",
)
# The Wallets FR-16 expects on the offline Watchlist; they hold the anchor Positions (the coin-flippers do too).
WATCHLIST_NAMES = ("sharp-trader", "steady-sharp", "forecaster", "speed-trader")


def small_wallets() -> tuple[SampleWallet, ...]:
    """The committed stage 1 Synthetic Wallets, in a fixed order."""
    return (
        _wallet("hand-check", _exact("hand-check", 10, 0.50, won=10)),
        _wallet("favourite-buyer", _exact("favourite-buyer", 100, 0.90, won=90)),
        _wallet("sharp-trader", _exact("sharp-trader", 100, 0.50, won=70), anchors=True),
        _wallet("thin-wallet", _exact("thin-wallet", 29, 0.50, won=20)),
        _wallet("stop-loss-trader", _stop_loss_bets(), with_prices=True),
        _wallet("steady-sharp", _two_sides("steady-sharp"), anchors=True),
        _wallet("forecaster", _two_sides("forecaster", path="drift"), anchors=True),
        _wallet("speed-trader", _two_sides("speed-trader", path="jump"), anchors=True),
    )


def coin_flipper_name(index: int) -> str:
    """The name of coin-flipper number `index`: "coin-flipper-0000"."""
    return f"coin-flipper-{index:04d}"


def coin_flipper(index: int) -> SampleWallet:
    """Coin-flipper number `index`: prices uniform in whole cents 0.10-0.90, won when a draw < price."""
    name = coin_flipper_name(index)
    bets = []
    for i in range(COIN_FLIPPER_BETS):
        cents = 10 + int(uniform(name, i, "price") * 81)  # 10..90, each equally likely
        price = cents / 100
        bets.append(_Bet(price, won=uniform(name, i, "outcome") < price))
    return _wallet(name, bets, anchors=True)  # in the offline Scan too (Edvard, 2026-11-27, Story 4.6)


def coin_flippers(count: int = COIN_FLIPPERS) -> Iterator[SampleWallet]:
    return (coin_flipper(i) for i in range(count))


def write_small(root: Path) -> list[Path]:
    """Write the committed Wallets and the anchor Markets' volumes under `root` (the repository folder)."""
    paths = []
    for wallet in small_wallets():
        path = root / SMALL_DIR / f"{wallet.name}.json"
        write_wallet(path, wallet)
        paths.append(path)
    write_funnel(root / SMALL_DIR / FUNNEL_FILE, funnel_volumes())
    return paths


def anchor_market_id(index: int) -> str:
    """The condition id of anchor Market number `index`."""
    return "0x" + hashlib.sha256(f"liquidoracle synthetic anchor market {index}".encode()).hexdigest()


def funnel_volumes() -> dict[str, float]:
    """Each anchor Market's volume in USD, by condition id: what Gamma's volume-ordered list gives (AD-21)."""
    return {anchor_market_id(i): volume for i, (_, volume) in enumerate(ANCHORS)}


def write_coin_flippers(root: Path, count: int = COIN_FLIPPERS) -> Path:
    """Write the coin-flippers under `root`/instance (never committed); returns their folder."""
    folder = root / COIN_FLIPPER_DIR
    for wallet in coin_flippers(count):
        write_wallet(folder / f"{wallet.name}.json", wallet, compact=True)
    return folder


def _exact(name: str, n: int, price: float, *, won: int) -> list[_Bet]:
    """n bets at one price, exactly `won` of them won; which ones is fixed by draws."""
    ranked = sorted(range(n), key=lambda i: uniform(name, i, "order"))
    winners = set(ranked[:won])
    return [_Bet(price, won=i in winners) for i in range(n)]


def _two_sides(name: str, *, path: PathKind | None = None) -> list[_Bet]:
    """A stage 2 Wallet (FR-13): 100 bets at 0.50 before the cut-off with exactly 70 won, and 100 bought
    from the cut-off on, one a day, with exactly 70 won; `path` gives the later bets their price path."""
    before = _exact(name, 100, 0.50, won=70)
    after = [
        replace(bet, bought_at=CUTOFF + i * DAY, path=path)
        for i, bet in enumerate(_exact(f"{name} after", 100, 0.50, won=70))
    ]
    return [*before, *after]


def price_path(path: PathKind, bought_at: int, price: float, won: bool) -> list[tuple[int, float]]:
    """The (time, price) points around one buy (FR-13): a forecaster's price drifts in a straight line to
    the outcome over `DRIFT_MINUTES`; a speed trader's jumps to it 10 seconds after the buy, so from the
    first minute on it is there. Up to the buy both stay at the buy price."""
    outcome = 1.0 if won else 0.0
    points = []
    for minute in PATH_MINUTES:
        if minute <= 0:
            value = price
        elif path == "drift":
            value = round(price + (outcome - price) * min(1.0, minute / DRIFT_MINUTES), 6)
        elif path == "jump":
            value = outcome
        else:
            raise ValueError(f"unknown price path {path!r}")
        points.append((bought_at + minute * MINUTE, value))
    return points


def _stop_loss_bets() -> list[_Bet]:
    """100 bets at 0.50, no edge, stop at 0.25 (FR-11, FR-13; Edvard, 2026-11-13).

    With a fair price, 2 in 3 bets touch 0.25 before resolving, and a quarter of those still win.
    So 67 are sold at 0.25 (17 in Markets their side later won), and the 33 held all win.
    """
    name = "stop-loss-trader"
    ranked = sorted(range(100), key=lambda i: uniform(name, i, "order"))
    kinds = {i: "held" for i in ranked[:33]}
    kinds |= {i: "sold, won" for i in ranked[33:50]}
    kinds |= {i: "sold, lost" for i in ranked[50:]}
    return [
        _Bet(0.50, won=kinds[i] != "sold, lost", sell_price=None if kinds[i] == "held" else STOP_LOSS_PRICE)
        for i in range(100)
    ]


def all_addresses(coin_flippers: int = COIN_FLIPPERS) -> frozenset[str]:
    """Every Synthetic Wallet's address, also before its file is written (Story 1.7: such a Wallet is
    "not loaded yet", never "not available offline")."""
    names = [*SMALL_NAMES, *(coin_flipper_name(i) for i in range(coin_flippers))]
    return frozenset(address_of(name) for name in names)


def address_of(name: str) -> str:
    """The fixed address of the Synthetic Wallet called `name`, without generating it (Story 1.7's Sample list)."""
    return "0x" + hashlib.sha256(f"liquidoracle synthetic wallet {name}".encode()).hexdigest()[:40]


def _wallet(name: str, bets: list[_Bet], *, with_prices: bool = False, anchors: bool = False) -> SampleWallet:
    # 1. Fills first (AD-14). Per Market: its tokens, whether the bought one won, resolution and start time.
    activity: list[ActivityRow] = []
    market_of: dict[str, tuple[tuple[str, str], bool, int, int]] = {}
    prices: list[PricePoint] = []
    for i, bet in enumerate(bets):
        condition_id = "0x" + hashlib.sha256(f"liquidoracle synthetic market {name} {i}".encode()).hexdigest()
        bought, other = _token_id(condition_id, 0), _token_id(condition_id, 1)
        bought_at = START + i * DAY if bet.bought_at is None else bet.bought_at
        resolved_at = _resolved_at(bought_at)
        # The Market opened a day before the Wallet's buy (AD-7).
        market_of[condition_id] = ((bought, other), bet.won, resolved_at, bought_at - DAY)
        activity.append(_trade(condition_id, bought, "BUY", bought_at, bet.price))
        if bet.sell_price is not None:
            activity.append(_trade(condition_id, bought, "SELL", bought_at + DAY // 2, bet.sell_price))
        if bet.path is not None:  # the forecaster's and speed trader's paths (FR-13)
            prices.extend(PricePoint(bought, t, p) for t, p in price_path(bet.path, bought_at, bet.price, bet.won))
        elif with_prices:  # the price path behind the stop-loss sells
            prices.append(PricePoint(bought, bought_at, bet.price))
            if bet.sell_price is not None:
                prices.append(PricePoint(bought, bought_at + DAY // 2, bet.sell_price))
            prices.append(PricePoint(bought, resolved_at, 1.0 if bet.won else 0.0))
    if anchors:  # one small Position per anchor Market, sold the day before it resolves (Story 4.6)
        for k, (resolved_at, _) in enumerate(ANCHORS):
            condition_id = anchor_market_id(k)
            bought, other = _token_id(condition_id, 0), _token_id(condition_id, 1)
            market_of[condition_id] = ((bought, other), k % 2 == 0, resolved_at, resolved_at - 10 * DAY)
            activity.append(_trade(condition_id, bought, "BUY", resolved_at - 2 * DAY, ANCHOR_PRICE, ANCHOR_SHARES))
            activity.append(_trade(condition_id, bought, "SELL", resolved_at - DAY, ANCHOR_PRICE, ANCHOR_SHARES))

    # 2. Markets and positions-list rows derived from the fills.
    markets: list[Market] = []
    positions: list[ListedPosition] = []
    rows_of: dict[str, list[ActivityRow]] = {}
    for row in activity:
        rows_of.setdefault(row.condition_id, []).append(row)
    for condition_id, rows in rows_of.items():
        (bought, other), won, resolved_at, start_time = market_of[condition_id]
        first_buy = min(row.timestamp for row in rows if row.side == "BUY")
        markets.append(
            Market(
                condition_id=condition_id,
                closed=True,
                closed_time=resolved_at,
                token_ids=(bought, other),
                outcome_prices=(1.0, 0.0) if won else (0.0, 1.0),
                fees_enabled=False,
                start_time=start_time,
            )
        )
        shares_bought = sum((row.size for row in rows if row.side == "BUY"), 0.0)
        shares_held = shares_bought - sum((row.size for row in rows if row.side == "SELL"), 0.0)
        # Sold, or held and redeemed after a win: CLOSED. Held losers stay unredeemed: OPEN.
        status = "OPEN" if shares_held > 0 and not won else "CLOSED"
        # The Wallet's last event (AD-7): its last fill, or the redemption at resolution of a held winner.
        last_event = max(row.timestamp for row in rows)
        if status == "CLOSED" and shares_held > 0:
            last_event = resolved_at
        positions.append(ListedPosition(condition_id, bought, status, shares_bought, first_buy, last_event))

    return SampleWallet(
        address=address_of(name),
        name=name,
        activity=tuple(activity),
        positions=tuple(positions),
        markets=tuple(markets),
        prices=tuple(prices),
    )


def _token_id(condition_id: str, outcome: int) -> str:
    # Polymarket token ids are large decimal numbers.
    return str(int.from_bytes(hashlib.sha256(f"{condition_id}:{outcome}".encode()).digest(), "big"))


def _trade(
    condition_id: str, token_id: str, side: str, t: int, price: float, shares: float = SHARES
) -> ActivityRow:
    return ActivityRow(
        type="TRADE",
        condition_id=condition_id,
        timestamp=t,
        size=shares,
        usdc_size=round(shares * price, 6),  # no fees: cash = shares x price
        price=price,
        token_id=token_id,
        side=side,
    )


def _resolved_at(bought_at: int) -> int:
    return bought_at + 2 * DAY
