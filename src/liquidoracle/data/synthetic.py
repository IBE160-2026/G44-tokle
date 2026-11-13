"""The Synthetic Wallets of FR-13 (stage 1), whose correct answers are known in advance.

Each Wallet is written as fills (activity rows) first; its Markets, positions-list rows and
price paths are then derived from those fills (AD-14). Every bet has its own two-outcome
Market, 100 shares, no fees, and times before the default Cut-off Date (2025-07-01).

Randomness: uniform draws from sha256 of (GENERATOR_SEED, Wallet, bet, purpose), standard
library only, never the `SEED` setting, `random` or `hash()` (AD-14, AD-15; Edvard, 2026-11-13).
The same code therefore gives the same bytes on every OS, Python and numpy version (FR-13).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from liquidoracle.data.sample_json import write_wallet
from liquidoracle.records import ActivityRow, ListedPosition, Market, PricePoint, SampleWallet

GENERATOR_SEED = 20261113  # the generator's own fixed constant (AD-14), not the SEED setting
SHARES = 100.0  # shares per bet: keeps the hand values round (sharp trader: $2,000.00)
START = 1_735_689_600  # 2025-01-01 00:00 UTC; 100 daily bets end well before 2025-07-01
DAY = 86_400
COIN_FLIPPERS = 1000
COIN_FLIPPER_BETS = 100
STOP_LOSS_PRICE = 0.25  # Edvard, 2026-11-13

SMALL_DIR = Path("sample_data") / "synthetic"  # committed
COIN_FLIPPER_DIR = Path("instance") / "synthetic" / "coin-flippers"  # git-ignored (FR-12)


@dataclass(frozen=True, slots=True)
class _Bet:
    price: float
    won: bool  # did the outcome the Wallet bought win
    sell_price: float | None = None  # sold everything at this price before resolution


def uniform(wallet: str, bet: int, purpose: str) -> float:
    """A number in [0, 1) fixed by its inputs (AD-15 note, Story 1.3)."""
    digest = hashlib.sha256(f"{GENERATOR_SEED}:{wallet}:{bet}:{purpose}".encode()).digest()
    # 53 bits, a float's precision: 64 bits / 2**64 can round up to exactly 1.0 (review, 2026-11-13).
    return (int.from_bytes(digest[:8], "big") >> 11) / 2**53


def small_wallets() -> tuple[SampleWallet, ...]:
    """The committed stage 1 Synthetic Wallets, in a fixed order."""
    return (
        _wallet("hand-check", _exact("hand-check", 10, 0.50, won=10)),
        _wallet("favourite-buyer", _exact("favourite-buyer", 100, 0.90, won=90)),
        _wallet("sharp-trader", _exact("sharp-trader", 100, 0.50, won=70)),
        _wallet("thin-wallet", _exact("thin-wallet", 29, 0.50, won=20)),
        _wallet("stop-loss-trader", _stop_loss_bets(), with_prices=True),
    )


def coin_flipper(index: int) -> SampleWallet:
    """Coin-flipper number `index`: prices uniform in whole cents 0.10-0.90, won when a draw < price."""
    name = f"coin-flipper-{index:04d}"
    bets = []
    for i in range(COIN_FLIPPER_BETS):
        cents = 10 + int(uniform(name, i, "price") * 81)  # 10..90, each equally likely
        price = cents / 100
        bets.append(_Bet(price, won=uniform(name, i, "outcome") < price))
    return _wallet(name, bets)


def coin_flippers(count: int = COIN_FLIPPERS) -> Iterator[SampleWallet]:
    return (coin_flipper(i) for i in range(count))


def write_small(root: Path) -> list[Path]:
    """Write the committed Wallets under `root` (the repository folder)."""
    paths = []
    for wallet in small_wallets():
        path = root / SMALL_DIR / f"{wallet.name}.json"
        write_wallet(path, wallet)
        paths.append(path)
    return paths


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


def _address(name: str) -> str:
    return "0x" + hashlib.sha256(f"liquidoracle synthetic wallet {name}".encode()).hexdigest()[:40]


def _wallet(name: str, bets: list[_Bet], *, with_prices: bool = False) -> SampleWallet:
    # 1. Fills first (AD-14).
    activity: list[ActivityRow] = []
    outcome_of: dict[str, tuple[tuple[str, str], bool]] = {}
    prices: list[PricePoint] = []
    for i, bet in enumerate(bets):
        condition_id = "0x" + hashlib.sha256(f"liquidoracle synthetic market {name} {i}".encode()).hexdigest()
        bought, other = _token_id(condition_id, 0), _token_id(condition_id, 1)
        outcome_of[condition_id] = ((bought, other), bet.won)
        bought_at = START + i * DAY
        activity.append(_trade(condition_id, bought, "BUY", bought_at, bet.price))
        if bet.sell_price is not None:
            activity.append(_trade(condition_id, bought, "SELL", bought_at + DAY // 2, bet.sell_price))
        if with_prices:  # the price path behind the stop-loss sells
            prices.append(PricePoint(bought, bought_at, bet.price))
            if bet.sell_price is not None:
                prices.append(PricePoint(bought, bought_at + DAY // 2, bet.sell_price))
            prices.append(PricePoint(bought, _resolved_at(bought_at), 1.0 if bet.won else 0.0))

    # 2. Markets and positions-list rows derived from the fills.
    markets: list[Market] = []
    positions: list[ListedPosition] = []
    rows_of: dict[str, list[ActivityRow]] = {}
    for row in activity:
        rows_of.setdefault(row.condition_id, []).append(row)
    for condition_id, rows in rows_of.items():
        (bought, other), won = outcome_of[condition_id]
        first_buy = min(row.timestamp for row in rows if row.side == "BUY")
        markets.append(
            Market(
                condition_id=condition_id,
                closed=True,
                closed_time=_resolved_at(first_buy),
                token_ids=(bought, other),
                outcome_prices=(1.0, 0.0) if won else (0.0, 1.0),
                fees_enabled=False,
            )
        )
        shares_bought = sum((row.size for row in rows if row.side == "BUY"), 0.0)
        shares_held = shares_bought - sum((row.size for row in rows if row.side == "SELL"), 0.0)
        # Sold, or held and redeemed after a win: CLOSED. Held losers stay unredeemed: OPEN.
        status = "OPEN" if shares_held > 0 and not won else "CLOSED"
        positions.append(ListedPosition(condition_id, bought, status, shares_bought, first_buy))

    return SampleWallet(
        address=_address(name),
        name=name,
        activity=tuple(activity),
        positions=tuple(positions),
        markets=tuple(markets),
        prices=tuple(prices),
    )


def _token_id(condition_id: str, outcome: int) -> str:
    # Polymarket token ids are large decimal numbers.
    return str(int.from_bytes(hashlib.sha256(f"{condition_id}:{outcome}".encode()).digest(), "big"))


def _trade(condition_id: str, token_id: str, side: str, t: int, price: float) -> ActivityRow:
    return ActivityRow(
        type="TRADE",
        condition_id=condition_id,
        timestamp=t,
        size=SHARES,
        usdc_size=round(SHARES * price, 6),  # no fees: cash = shares x price
        price=price,
        token_id=token_id,
        side=side,
    )


def _resolved_at(bought_at: int) -> int:
    return bought_at + 2 * DAY
