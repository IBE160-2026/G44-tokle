"""The 10 real Wallets of the Sample Dataset, built from the raw capture (AD-14, FR-12; Story 2.6).

The capture zip (Data API v2, 23 Oct 2026) holds each picked Wallet's positions lists and activity
rows, but no Gamma records, and only 0xd218e4's oldest 60,000 CLOSED rows. Both are fetched once,
read-only, through the app's own client into an additions file next to the zip (Edvard, 2026-11-23).
Each file has its own SHA-256 file, checked before anything is read.

The build runs the app's own window (`positions_near`) on each Wallet over the whole capture, keeps
only what that window read (the trim, by script and never by hand), writes it with the one
serializer, reads the file back through `OfflineClient`, and refuses to finish unless the window is
identical. Where the capture's activity reads stopped is stored in each file, so a read past it is
cut short offline and the normal "not fully read" rule applies (AD-7, AD-11).

Story 4.7 adds the before and after parts around the default Cut-off Date for the Wallets in the
offline Scan: each file keeps what all three walks read and must replay all three. The build also
writes the real volume list from the capture's own funnel (the Markets the Wallets were picked
from, with their rows as Polymarket listed them), and stops if any of those rows could hold
something from after the Cut-off Date (Edvard, 2026-11-27).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
import zipfile
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from liquidoracle.data import sample_json, synthetic
from liquidoracle.data.errors import NotAvailableOffline
from liquidoracle.data.offline import OfflineClient
from liquidoracle.data.polymarket import (
    PolymarketClient,
    parse_activity_row,
    parse_listed_position,
    parse_market,
    parse_time,
)
from liquidoracle.data.window import cutoff_at, positions_near
from liquidoracle.records import ActivityRow, ListedPosition, Market, MarketHolder, Read, SampleWallet, Window

CAPTURE_NAME = "sample-capture-cutoff-2025-07-01.zip"
ADDITIONS_NAME = "sample-additions-2026-11-23.json"
REAL_DIR = Path("sample_data") / "real"
DATASET_FILE = "dataset.json"  # the Cut-off Date and where the set came from (FR-12)
STAGING_DIR = Path("instance") / "build-sample"  # git-ignored: files wait here until all of them pass
CAPTURED_ON = "2026-10-23"  # the capture's date (spike/FINDINGS.md)
CUTOFF = "2025-07-01"  # the default Cut-off Date (Edvard, 2026-10-23), stored with the Sample Dataset
CAPTURE_DIR = "sample/capture/"
# The 10 Sample Wallets, as spike/FINDINGS.md's table names them (Edvard, 2026-10-23; not the spares).
# The zip's own `sample/picked.json` was zipped before that day's swap of 0x091596 in for 0x8861f0,
# so the build never reads it (Edvard, 2026-11-23); each address must be in the zip.
PICK = (
    "0xcf0d7f69cf162918b33fc1ea7449583fa537132d",
    "0x73648309111de9f9d4e2a58a50f803fa7d30d44e",
    "0xd218e474776403a330142299f7796e8ba32eb5c9",
    "0xd3a6e523c440f94f9259398fbcf7b5cc5ccffd55",
    "0x63d43bbb87f85af03b8f2f9e2fad7b54334fa2f1",
    "0x94884db79666a1a34c46d03fb4f8e9cbcaf6b5a6",
    "0x7298060b1844a4c4ca0578146ab3f5e76aa1fcfc",
    "0x0f4b0a6b7f82108924ac9c8320ed91028f504183",
    "0x0915962b4c6bc4505e7434a0de815a596a6667c3",
    "0x29306ddc4724e24a23bf1c8679aa034376ea9dcb",
)
# Kept out of the offline Scan, with only their lookup window (Edvard, 2026-11-27, Story 4.7): the capture
# holds their activity only from May 2025, so their before part would read as wholly "not fully read", and
# both windows would add an estimated 60 to 130 MB.
LOOKUP_ONLY = {
    "0xd218e474776403a330142299f7796e8ba32eb5c9": "activity captured only from 29 May 2025",
    "0x63d43bbb87f85af03b8f2f9e2fad7b54334fa2f1": "activity captured only from 9 May 2025",
}
SIDES: tuple[str | None, ...] = (None, "before", "after")  # the lookup window, then Story 4.1's two parts
# The capture's own Scan funnel (21 Oct 2026, AD-21): the top 100 Markets by Gamma volume resolved in the
# 90 days before the Cut-off Date, and each Market's CLOSED and OPEN holder rows (spike/sample_pick.py).
FUNNEL_LIST = "sample/funnel_markets_20250701.json"
MARKET_LIST = "sample/market_{}.json"  # the condition id's first 18 characters
FUNNEL_FILE = synthetic.FUNNEL_FILE  # the real volume list, next to the real Wallets
# Rows that change what a Wallet holds in a Market; only a redemption may come after the Cut-off Date.
HOLDING_TYPES = frozenset({"TRADE", "SPLIT", "MERGE", "CONVERSION"})
# The capture read CLOSED lists oldest first and stopped at this many rows: 0xd218e4's newest
# Positions are missing, so its newest CLOSED pages come from the additions file (Edvard, 2026-11-23).
CAPTURE_CLOSED_CAP = 60_000
# The Gamma fields the Market parser reads (as `tests/fixtures/cut_from_capture.py`); tags keep their
# labels and events their ids only.
GAMMA_KEYS = (
    "conditionId", "closed", "closedTime", "startDate", "clobTokenIds", "outcomePrices", "feesEnabled",
    "feeSchedule", "outcomes", "negRisk", "negRiskMarketID",
)


class BuildError(Exception):
    """The build cannot go on; the message says why. Nothing is left half written in `sample_data/`."""


def sides_of(address: str) -> tuple[str | None, ...]:
    """The windows a Wallet's file must replay: all three, or the lookup window for a lookup-only Wallet."""
    return SIDES[:1] if address in LOOKUP_ONLY else SIDES


def _cutoff_day() -> date:
    return date.fromisoformat(CUTOFF)


# --- inputs ---------------------------------------------------------------------------------------


def checked(path: Path) -> str:
    """The file's SHA-256, after checking it against `<file>.sha256` (as `sha256sum -c` reads it)."""
    sums = path.with_name(path.name + ".sha256")
    if not path.is_file():
        raise BuildError(f"{path} not found")
    if not sums.is_file():
        raise BuildError(f"{sums} not found: the build checks every input against its SHA-256 file")
    words = sums.read_text(encoding="utf-8").split()
    expected = words[0].lower() if words else ""
    actual = sha256_of(path)
    if actual != expected:
        raise BuildError(f"{path.name} does not match {sums.name} (SHA-256 {actual}); refusing to build")
    return actual


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_sha256(path: Path) -> None:
    """Writes `<file>.sha256` in `sha256sum`'s format, with LF."""
    path.with_name(path.name + ".sha256").write_bytes(f"{sha256_of(path)}  {path.name}\n".encode())


@dataclass(frozen=True, slots=True)
class Captured:
    """One picked Wallet as the capture holds it: lists, activity, and where activity reading stopped."""

    address: str
    open_rows: tuple[ListedPosition, ...]
    closed_rows: tuple[ListedPosition, ...]
    closed_capped: bool
    activity: tuple[ActivityRow, ...]
    activity_from: int | None
    activity_until: int | None
    combos: tuple[tuple[str, int], ...] = ()  # combo rows (dropped from `activity`, AD-10): Market and time


def read_capture(zip_path: Path, pick: Sequence[str]) -> dict[str, Captured]:
    """Each picked Wallet's captured rows. A Wallet missing from the zip stops the build."""
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        missing = [a for a in pick if f"{CAPTURE_DIR}{a}/positions.json" not in names]
        if missing:
            raise BuildError(f"{zip_path.name} has no capture of {', '.join(missing)}")
        return {address: _captured(archive, address) for address in pick}


def _captured(archive: zipfile.ZipFile, address: str) -> Captured:
    folder = f"{CAPTURE_DIR}{address}/"
    lists = json.loads(archive.read(folder + "positions.json"))
    before = json.loads(archive.read(folder + "activity_before.json"))  # newest first, up to the cut-off
    after = json.loads(archive.read(folder + "activity_after.json"))  # oldest first, from the cut-off
    rows = [parse_activity_row(raw) for raw in reversed(before["rows"])] + [parse_activity_row(raw) for raw in after["rows"]]
    combos = tuple(
        sorted((str(raw.get("condition_id")), raw["timestamp"]) for raw in (*before["rows"], *after["rows"]) if raw.get("is_combo") is True)
    )
    activity = tuple(sorted((row for row in rows if row is not None), key=lambda row: row.timestamp))
    # A capped newest-first read may hold only part of its oldest second; a capped oldest-first read
    # only part of its newest. So the first whole second is one after the oldest row read, and
    # `activity_until` is the second the read stopped in (see `SampleWallet`).
    activity_from = min(raw["timestamp"] for raw in before["rows"]) + 1 if before["capped"] and before["rows"] else None
    activity_until = max(raw["timestamp"] for raw in after["rows"]) if after["capped"] and after["rows"] else None
    closed = tuple(parse_listed_position(raw, "CLOSED") for raw in lists["closed"])
    # The capture read CLOSED oldest first with a 60,000-row cap and OPEN in full; `capped` is set
    # for either, so a full 60,000 CLOSED rows is the cut list.
    closed_capped = bool(lists["capped"]) and len(lists["closed"]) >= CAPTURE_CLOSED_CAP
    if lists["capped"] and not closed_capped:
        raise BuildError(f"{address}: the capture's OPEN list was cut short; the build has no rule for that")
    return Captured(
        address=address,
        open_rows=tuple(parse_listed_position(raw, "OPEN") for raw in lists["open"]),
        closed_rows=closed,
        closed_capped=closed_capped,
        activity=activity,
        activity_from=activity_from,
        activity_until=activity_until,
        combos=combos,
    )


@dataclass(slots=True)
class Additions:
    """What the capture lacks, fetched once: raw Gamma answers and the newest CLOSED pages (Story 2.6)."""

    fetched_on: str = ""
    gamma: dict[str, dict[str, Any]] = field(default_factory=dict)
    gamma_missing: set[str] = field(default_factory=set)  # asked, but Gamma returned no record
    closed: dict[str, tuple[ListedPosition, ...]] = field(default_factory=dict)

    def markets(self) -> list[Market]:
        return [parse_market(raw) for raw in self.gamma.values()]


def read_additions(path: Path) -> Additions:
    document = json.loads(path.read_text(encoding="utf-8"))
    return Additions(
        fetched_on=document["fetched_on"],
        gamma={raw["conditionId"]: raw for raw in document["gamma"]},
        gamma_missing=set(document["gamma_missing"]),
        closed={
            wallet: tuple(sample_json.listed_position(row) for row in rows) for wallet, rows in document["closed"].items()
        },
    )


def write_additions(path: Path, additions: Additions) -> None:
    document = {
        "fetched_on": additions.fetched_on,
        "source": "Gamma /markets with include_tag, and Data API v2 /v2/positions CLOSED newest first; read-only",
        "gamma": [additions.gamma[c] for c in sorted(additions.gamma)],
        "gamma_missing": sorted(additions.gamma_missing),
        "closed": {wallet: [asdict(row) for row in rows] for wallet, rows in sorted(additions.closed.items())},
    }
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes((json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
    temporary.replace(path)
    write_sha256(path)


def _keep_gamma(raw: Mapping[str, Any]) -> dict[str, Any]:
    kept = {key: raw[key] for key in GAMMA_KEYS if key in raw}
    kept["tags"] = [{"label": tag["label"]} for tag in raw.get("tags") or [] if isinstance(tag, Mapping) and "label" in tag]
    if isinstance(raw.get("events"), list):
        kept["events"] = [{"id": event.get("id")} for event in raw["events"] if isinstance(event, Mapping)]
    return kept


# --- fetching once --------------------------------------------------------------------------------


def fetch_additions(
    zip_path: Path, live: PolymarketClient, *, pick: Sequence[str] = PICK, log: Callable[[str], None] = print
) -> Path:
    """Fetches what the capture lacks (network, read-only) into the additions file next to the zip.

    Each Wallet's windows are walked as the build will walk them (Story 4.7: also the before and after
    parts); every Market they ask Gamma about and 0xd218e4's CLOSED pages are fetched once. Records already
    in the file are never asked again.
    """
    checked(zip_path)
    captured = read_capture(zip_path, pick)
    path = zip_path.with_name(ADDITIONS_NAME)
    if path.is_file():
        checked(path)  # an edited or damaged file is never added to and signed again (review, Story 2.6)
        additions = read_additions(path)
    else:
        additions = Additions(fetched_on=datetime.now(UTC).date().isoformat())
    for address in pick:
        client = _FetchingClient(captured[address], live, additions)
        for side in sides_of(address):
            window = positions_near(client, address, None if side is None else _cutoff_day(), side)
            log(f"{address}: {side or 'lookup'} window of {len(window.positions):,} Positions; "
                f"Gamma records so far {len(additions.gamma):,}")
        write_additions(path, additions)  # after each Wallet, so a stop keeps what was fetched
    return path


class _FetchingClient:
    """The capture's lists and activity, Gamma (and 0xd218e4's CLOSED list) live, stored as they come."""

    def __init__(self, captured: Captured, live: PolymarketClient, additions: Additions) -> None:
        self._captured = captured
        self._live = live
        self._additions = additions

    def positions_list(self, wallet: str, status: str, **options: Any) -> Read[ListedPosition]:
        if status == "CLOSED" and self._captured.closed_capped and wallet not in self._additions.closed:
            read = self._live.positions_list(wallet, status, **options)
            if not read.complete:
                raise BuildError(f"{wallet}: Polymarket's CLOSED list could not be read whole; try again later")
            self._additions.closed[wallet] = read.rows
            return read
        return self._capture().positions_list(wallet, status, **options)

    def activity_rows(self, wallet: str, **options: Any) -> Read[ActivityRow]:
        return self._capture().activity_rows(wallet, **options)

    def _capture(self) -> OfflineClient:
        """The capture as it stands, with any CLOSED pages fetched so far."""
        return OfflineClient.in_memory([_full_wallet(self._captured, self._additions)])

    def markets(self, condition_ids: Iterable[str]) -> tuple[Market, ...]:
        wanted = list(dict.fromkeys(condition_ids))
        missing = [c for c in wanted if c not in self._additions.gamma and c not in self._additions.gamma_missing]
        if missing:
            for raw in self._live.raw_markets(missing):
                self._additions.gamma[raw["conditionId"]] = _keep_gamma(raw)
            self._additions.gamma_missing.update(c for c in missing if c not in self._additions.gamma)
        return tuple(parse_market(self._additions.gamma[c]) for c in wanted if c in self._additions.gamma)


def _full_wallet(captured: Captured, additions: Additions) -> SampleWallet:
    """The whole capture of one Wallet as a Sample Wallet, its CLOSED list from the additions when cut."""
    closed = additions.closed.get(captured.address, ()) if captured.closed_capped else captured.closed_rows
    return SampleWallet(
        address=captured.address,
        name=name_of(captured.address),
        activity=captured.activity,
        positions=captured.open_rows + closed,
        markets=(),
        activity_from=captured.activity_from,
        activity_until=captured.activity_until,
    )


def name_of(address: str) -> str:
    return f"real-{address[2:8]}"


# --- building (no network) ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Built:
    """One written real Wallet, for the build's report."""

    address: str
    path: Path
    window_positions: int
    activity_read_until: int | None
    file_bytes: int
    parts: tuple[tuple[str, int], ...] = ()  # Positions in the before and after parts (Story 4.7); none if lookup-only


def build(zip_path: Path, root: Path, *, pick: Sequence[str] = PICK, log: Callable[[str], None] = print) -> list[Built]:
    """Writes `sample_data/real/` from the capture and the additions file. No network (AD-14).

    The Wallets' files, `dataset.json`, and the real volume list with its holder rows (Story 4.7)."""
    capture_sha = checked(zip_path)
    additions_path = zip_path.with_name(ADDITIONS_NAME)
    if not additions_path.is_file():
        raise BuildError(f"{additions_path} not found: run build-sample with --fetch once first")
    additions_sha = checked(additions_path)
    captured = read_capture(zip_path, pick)
    additions = read_additions(additions_path)
    markets = {market.condition_id: market for market in additions.markets()}
    for address in pick:
        if captured[address].closed_capped and address not in additions.closed:
            raise BuildError(f"{address}: its CLOSED list was cut in the capture and is not in the additions file")

    # Every file is written and replayed in a staging folder (git-ignored) first; `sample_data/real/`
    # is touched only once all of them pass, so a failed build leaves it as it was (review, Story 2.6).
    staging = root / STAGING_DIR
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        built = [_written(captured[address], additions, markets, staging, log) for address in pick]
        funnel = real_funnel(zip_path, captured, markets, [a for a in pick if a not in LOOKUP_ONLY], staging)
        sample_json.write_funnel(staging / FUNNEL_FILE, funnel.volumes, funnel.holders)
        log(f"real volume list: {len(funnel.volumes)} Markets, {sum(map(len, funnel.holders.values()))} holder rows")
        dataset = _dataset(zip_path, capture_sha, additions_path, additions_sha, additions, captured, pick, built, funnel)
        (staging / DATASET_FILE).write_bytes((json.dumps(dataset, indent=1, sort_keys=True) + "\n").encode("utf-8"))
        out = root / REAL_DIR
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("*.json"):
            old.unlink()
        for new in sorted(staging.glob("*.json")):
            new.replace(out / new.name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return [dataclasses.replace(item, path=root / REAL_DIR / item.path.name) for item in built]


def _written(
    captured: Captured, additions: Additions, markets: Mapping[str, Market], folder: Path, log: Callable[[str], None]
) -> Built:
    """One Wallet's trimmed file in `folder`, kept only if it replays each window of the whole capture."""
    wallet, windows = _trimmed(captured, additions, markets, sides_of(captured.address))
    path = folder / f"{captured.address}.json"
    sample_json.write_wallet(path, wallet, compact=True)
    for side, window in windows.items():
        name = side or "lookup"
        try:
            replay = positions_near(OfflineClient([path]), captured.address, None if side is None else _cutoff_day(), side)
        except LookupError as error:  # NotAvailableOffline, NoPolymarketHistory: the file cannot replay at all
            raise BuildError(f"{captured.address}: the written file cannot replay its {name} window ({error})") from None
        if replay != window:
            raise BuildError(
                f"{captured.address}: the written file gives another {name} window than the capture; nothing kept"
            )
    size = path.stat().st_size
    lookup = windows[None]
    parts = tuple((side, len(window.positions)) for side, window in windows.items() if side is not None)
    shown = "".join(f", {side} part {count:,}" for side, count in parts)
    log(f"{captured.address}: {len(lookup.positions):,} Positions in the window{shown}, file {size / 1e6:.1f} MB")
    return Built(captured.address, path, len(lookup.positions), lookup.activity_read_until, size, parts)


def _dataset(
    zip_path: Path,
    capture_sha: str,
    additions_path: Path,
    additions_sha: str,
    additions: Additions,
    captured: Mapping[str, Captured],
    pick: Sequence[str],
    built: Sequence[Built],
    funnel: sample_json.FunnelFile,
) -> dict[str, Any]:
    """dataset.json: the Cut-off Date, both sources with their SHA-256, and the build's checks (FR-12).

    Story 4.7: the Positions in each Wallet's before and after parts, the Wallets kept to their lookup
    window with the reason, and where the real volume list came from with its counts."""
    return {
        "cutoff": CUTOFF,
        "wallets": list(pick),
        "parts": {item.address: dict(item.parts) for item in built if item.parts},
        "lookup_only": {address: LOOKUP_ONLY[address] for address in pick if address in LOOKUP_ONLY},
        "funnel": {
            "source": f"{FUNNEL_LIST} and sample/market_*.json in {zip_path.name}",
            "file": FUNNEL_FILE,
            "markets": len(funnel.volumes),
            "holder_rows": sum(map(len, funnel.holders.values())),
        },
        "capture": {"file": zip_path.name, "sha256": capture_sha},
        "additions": {"file": additions_path.name, "sha256": additions_sha, "fetched_on": additions.fetched_on},
        "built_by": f"uv run liquidoracle build-sample <folder>/{zip_path.name}",
        "neg_risk_check": neg_risk_check(additions, built),
        "two_dates": sorted(
            f"{address}: CLOSED list fetched {additions.fetched_on}, the rest captured {CAPTURED_ON}"
            for address in pick if captured[address].closed_capped
        ),
    }


def neg_risk_check(additions: Additions, built: Sequence[Built]) -> dict[str, Any]:
    """Story 2.4's open check: is every negRisk Market in the real Wallets' files a Yes/No Market?"""
    used: set[str] = set()
    for item in built:
        used.update(market.condition_id for market in sample_json.read_wallet(item.path).markets)
    neg_risk = [additions.gamma[c] for c in sorted(used) if additions.gamma[c].get("negRisk") is True]
    other = [raw["conditionId"] for raw in neg_risk if _outcomes(raw) != ["Yes", "No"]]
    return {"neg_risk_markets": len(neg_risk), "not_yes_no": other}


def _outcomes(raw: Mapping[str, Any]) -> list[str] | None:
    value = raw.get("outcomes")
    try:
        return json.loads(value) if isinstance(value, str) else value
    except ValueError:
        return None


def real_funnel(
    zip_path: Path,
    captured: Mapping[str, Captured],
    markets: Mapping[str, Market],
    scan: Sequence[str],
    folder: Path,
) -> sample_json.FunnelFile:
    """The real volume list: each completely read funnel Market a Wallet in `scan` holds, its Gamma volume,
    and those Wallets' rows on it as Polymarket listed them, in list order (AD-14, AD-21; Story 4.7).

    The capture's rows give no token: it is the one whose final price equals the row's, which a resolved
    Market makes exactly one (AD-7). A partial Market gives no candidates (AD-9), so it is left out. Every
    listed Market must be in a written file of `folder`, so `OfflineClient` can serve it.
    """
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        if FUNNEL_LIST not in names:
            raise BuildError(f"{zip_path.name} has no {FUNNEL_LIST}: the real Wallets cannot be put in the offline Scan")
        funnel = json.loads(archive.read(FUNNEL_LIST))
        prefixes = Counter(entry["conditionId"][:18] for entry in funnel)
        shared = sorted(prefix for prefix, count in prefixes.items() if count > 1)
        if shared:
            raise BuildError(f"two funnel Markets share the list name {MARKET_LIST.format(shared[0])}; cannot tell their lists apart")
        lists = {
            entry["conditionId"]: json.loads(archive.read(name))
            for entry in funnel
            if (name := MARKET_LIST.format(entry["conditionId"][:18])) in names
        }
    wanted = set(scan)
    volumes: dict[str, float] = {}
    holders: dict[str, tuple[MarketHolder, ...]] = {}
    for entry in funnel:
        condition_id = entry["conditionId"]
        listed = lists.get(condition_id)
        if listed is None or listed["partial"]:
            continue
        rows = [row for row in listed["rows"] if row[0] in wanted]
        if not rows:
            continue
        market = markets.get(condition_id)
        if market is None:
            raise BuildError(f"Gamma has no record of funnel Market {condition_id}")
        holders[condition_id] = tuple(
            _holder(row, market, parse_time(entry["closedTime"]), captured[row[0]]) for row in rows
        )
        volumes[condition_id] = float(entry["volumeNum"])
    served = {c for path in folder.glob("0x*.json") for c in sample_json.read_ids(path)[1]}
    missing = sorted(set(volumes) - served)
    if missing:
        raise BuildError(f"funnel Market {missing[0]} is in no written file, so the offline Scan could not read it")
    return sample_json.FunnelFile(volumes, holders)


def _holder(row: Sequence[Any], market: Market, funnel_closed: int, captured: Captured) -> MarketHolder:
    """One captured holder row `[wallet, status, realized_pnl, current_size, final_price, avg_price]`, checked so
    nothing in it comes from after the Cut-off Date (Edvard, 2026-11-27): the Market resolved before it (by Gamma
    and by the funnel list) with a final price of exactly 0 or 1; the capture read the Wallet's activity from the
    earlier of its resolution and the Cut-off Date on; and in that time the Wallet made no trade, split, merge,
    combo trade, or conversion in the Market's negative-risk event. Only a redemption may come later: it pays at
    an outcome already known before the Cut-off Date, so it adds nothing a Scan on that date could not know
    (the row may read CLOSED where it read OPEN then, as a live Scan reads it today)."""
    wallet, status, realized_pnl, current_size, final_price, avg_price = row
    cut = cutoff_at(_cutoff_day())
    where = f"{wallet} in funnel Market {market.condition_id}"
    if not market.resolved or market.closed_time is None or max(market.closed_time, funnel_closed) >= cut:
        raise BuildError(f"{where}: the Market did not resolve before the Cut-off Date; refusing to peek")
    if final_price not in (0, 1) or final_price not in market.outcome_prices:
        raise BuildError(f"{where}: final price {final_price} is not the Market's 0 or 1; refusing to peek")
    late = min(market.closed_time, funnel_closed, cut)
    if captured.activity_until is not None or (captured.activity_from is not None and captured.activity_from > late):
        raise BuildError(f"{where}: the capture did not read every activity row from {late} on; refusing to peek")
    # A conversion is about the whole negative-risk event, so its row carries the event's id (AD-10).
    ids = {market.condition_id} | ({market.neg_risk_id} if market.neg_risk_id else set())
    for activity in captured.activity:
        if activity.condition_id in ids and activity.type in HOLDING_TYPES and activity.timestamp >= late:
            raise BuildError(f"{where}: a {activity.type} row at {activity.timestamp} is not before {late}; refusing to peek")
    for condition_id, timestamp in captured.combos:
        if condition_id in ids and timestamp >= late:
            raise BuildError(f"{where}: a combo row at {timestamp} is not before {late}; refusing to peek")
    token = market.token_ids[market.outcome_prices.index(float(final_price))]
    if token not in {listed.token_id for listed in (*captured.open_rows, *captured.closed_rows)}:
        raise BuildError(f"{where}: token {token} is on none of the Wallet's positions lists")
    return MarketHolder(wallet, token, status, float(realized_pnl), float(current_size), float(avg_price))


class _Recorder:
    """Passes the windows' reads through and keeps what they returned (the trim's input)."""

    def __init__(self, client: OfflineClient) -> None:
        self._client = client
        self.open_rows: tuple[ListedPosition, ...] = ()
        self.closed_rows: tuple[ListedPosition, ...] = ()
        self.activity: Read[ActivityRow] | None = None

    def positions_list(self, wallet: str, status: str, **options: Any) -> Read[ListedPosition]:
        read = self._client.positions_list(wallet, status, **options)
        if status == "OPEN":
            self.open_rows = read.rows
        else:
            self.closed_rows = read.rows
        return read

    def activity_rows(self, wallet: str, **options: Any) -> Read[ActivityRow]:
        self.activity = self._client.activity_rows(wallet, **options)
        return self.activity

    def markets(self, condition_ids: Iterable[str]) -> tuple[Market, ...]:
        return self._client.markets(condition_ids)


def _trimmed(
    captured: Captured, additions: Additions, markets: Mapping[str, Market], sides: Sequence[str | None] = (None,)
) -> tuple[SampleWallet, dict[str | None, Window]]:
    """Each window over the whole capture, and the smallest Sample Wallet that gives the same windows.

    Kept, for the lookup window: every CLOSED row the walk read; the OPEN rows of Markets up to the window's
    first left-out Market in the cap order (older ones cannot change which Markets fit, AD-8). For the before
    and after parts (Story 4.7): every row their walks read. Then the Markets of kept rows, and the activity
    rows each window keeps, plus the last row of a read cut short so the replay stops in the same second.
    Rows keep the order the reads gave them, so a lookup-only Wallet's file is the same as before Story 4.7.
    """
    full = _full_wallet(captured, additions)
    client = OfflineClient.in_memory([full], markets.values())
    windows: dict[str | None, Window] = {}
    open_kept: set[int] = set()  # ids of the full capture's row objects, which every read hands out
    closed_kept: set[int] = set()
    activity_kept: set[int] = set()
    read_ends: list[int] = []
    for side in sides:
        recorder = _Recorder(client)
        try:
            window = positions_near(recorder, captured.address, None if side is None else _cutoff_day(), side)
        except NotAvailableOffline as error:
            # Live, such a Market is simply outside the window; a file could not serve it offline.
            raise BuildError(f"{captured.address}: Gamma has no record of a Market the window reads ({error})") from None
        windows[side] = window
        if side is None:
            kept_markets = _cap_prefix(window, (*recorder.open_rows, *recorder.closed_rows), markets)
            open_kept.update(id(row) for row in recorder.open_rows if row.condition_id in kept_markets)
        else:
            open_kept.update(map(id, recorder.open_rows))
        closed_kept.update(map(id, recorder.closed_rows))
        read = recorder.activity
        if read is not None:
            wanted = Counter(window.activity)
            for i, row in enumerate(read.rows):
                if wanted[row] > 0 or (not read.complete and i == len(read.rows) - 1):
                    wanted[row] -= 1
                    activity_kept.add(id(row))
            if not read.complete and read.rows:
                read_ends.append(read.rows[-1].timestamp)

    # The OPEN list's own order, then CLOSED newest first (the order the walks read them, ties in file order).
    open_rows = tuple(row for row in full.positions if row.status == "OPEN" and id(row) in open_kept)
    closed = sorted((row for row in full.positions if row.status == "CLOSED"), key=lambda row: row.last_event_at, reverse=True)
    positions = open_rows + tuple(row for row in closed if id(row) in closed_kept)
    market_ids = sorted({row.condition_id for row in positions})
    wallet = SampleWallet(
        address=captured.address,
        name=name_of(captured.address),
        activity=tuple(row for row in full.activity if id(row) in activity_kept),
        positions=positions,
        markets=tuple(markets[c] for c in market_ids),
        activity_from=captured.activity_from,
        # The earliest second a read was cut short in; the replay check refuses a file where that cuts
        # another window's read shorter than the capture did.
        activity_until=min(read_ends) if read_ends else captured.activity_until,
    )
    return wallet, windows


def _cap_prefix(window: Window, rows: Sequence[ListedPosition], markets: Mapping[str, Market]) -> set[str]:
    """The window's Markets and the first Market after them in the cap order (AD-8's order)."""
    chosen = {market.condition_id for market in window.markets}
    in_window = {
        row.condition_id for row in rows
        if row.condition_id in markets and markets[row.condition_id].closed and markets[row.condition_id].closed_time is not None
    }
    order = sorted(in_window, key=lambda c: (-(markets[c].closed_time or 0), c))
    prefix = set(chosen)
    for condition_id in order:
        if condition_id not in chosen:
            prefix.add(condition_id)
            break
    return prefix
