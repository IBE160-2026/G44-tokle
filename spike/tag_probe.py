"""Do Polymarket's event tags cover the Sample Wallets' Markets? (PRD FR-15, FR-19; spine AD-16; 2026-11-05)

Read-only, public Gamma requests, no keys. The first four steps leave out the events behind Edvard's 50
hand-label Markets (sample_data/hand_labels/markets.csv), so they never fetch or show their tags (Edvard,
2026-11-05). Only `compare` reads those, and it was first run after his labels were committed (f54d1b7).

  python spike/tag_probe.py endpoints   which Gamma routes return tags, on one event (5 requests)
  python spike/tag_probe.py draw        tags of a seeded 1,000 events, saved to raw/ (20 requests)
  python spike/tag_probe.py batch       tags on a 20-Market call, with and without include_tag (2 requests)
  python spike/tag_probe.py analyse     coverage from the saved draw, using tag_probe_map.json
  python spike/tag_probe.py compare     the test map against Edvard's 50 hand labels (3 requests)

tag_probe_map.json is the AI's rough test map, written on 2026-11-05 before Edvard's definitions, only to
size the problem. It was kept out of the repo until his definitions and labels were committed, so it could
not steer them. It is not the tag rules: those are written from his definitions and checked on other Markets.
"""
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import api
from api import GAMMA

HERE = Path(__file__).resolve().parent
SAMPLE = HERE / "raw" / "sample"
HAND_LABELS = HERE.parent / "sample_data" / "hand_labels" / "markets.csv"
DRAW_FILE = HERE / "raw" / "tag_probe_draw.json"
MAP_FILE = HERE / "tag_probe_map.json"
HAND50_FILE = HERE / "raw" / "tag_probe_hand50.json"
SEED, DRAW, BATCH = 20261105, 1000, 50


def load():
    """Each Sample Wallet's rows, each Market's event, and the events that must stay out."""
    with HAND_LABELS.open(encoding="utf8") as f:
        blind = {r["condition_id"] for r in csv.DictReader(f)}
    pick = json.loads((SAMPLE / "picked.json").read_text(encoding="utf8"))
    wallets, cond_event, blind_events = {}, {}, set()
    for w in pick["sample"]:
        pos = json.loads((SAMPLE / "capture" / w / "positions.json").read_text(encoding="utf8"))
        wallets[w] = pos["closed"] + pos["open"]
        for r in wallets[w]:
            cond_event[r["condition_id"]] = str(r["event_id"])
            if r["condition_id"] in blind:
                blind_events.add(str(r["event_id"]))
    return wallets, cond_event, blind_events


def labels(tags):
    return [t.get("label") for t in tags or []]


def endpoints():
    _, cond_event, blind_events = load()
    safe = sorted(set(cond_event.values()) - blind_events)
    event = safe[len(safe) // 2]
    cond = next(c for c, e in cond_event.items() if e == event)
    print("events", len(set(cond_event.values())), "left out", len(blind_events), "probe event", event)
    for path, params in [(f"/events/{event}/tags", None), (f"/events/{event}", None),
                         (f"/events/{event}", [("include_tag", "true")]),
                         ("/events", [("id", event), ("include_tag", "true")]),
                         ("/markets", [("condition_ids", cond), ("include_tag", "true"), ("closed", "true")])]:
        status, data, _ = api.get(GAMMA, path, params)
        row = data if isinstance(data, dict) else data[0]
        print(status, path, params, labels(data) if path.endswith("/tags") else labels(row.get("tags")))


def draw():
    _, cond_event, blind_events = load()
    events = sorted(set(cond_event.values()) - blind_events)
    chosen = random.Random(SEED).sample(events, DRAW)
    assert not set(chosen) & blind_events
    found, statuses = {}, Counter()
    for i in range(0, len(chosen), BATCH):
        status, data, _ = api.get(GAMMA, "/events", [("id", e) for e in chosen[i:i + BATCH]]
                                  + [("limit", 100), ("include_tag", "true")])
        statuses[status] += 1
        for x in data if isinstance(data, list) else []:
            found[str(x["id"])] = {"tags": labels(x.get("tags")), "slug": x.get("slug"),
                                   "closedTime": x.get("closedTime"), "endDate": x.get("endDate")}
    DRAW_FILE.write_text(json.dumps({"draw": chosen, "events": found}), encoding="utf8")
    print("requests", len(api.log), "statuses", dict(statuses), "returned", len(found), "of", len(chosen))


def batch():
    _, cond_event, blind_events = load()
    gamma = json.loads((SAMPLE / "gamma_cache.json").read_text(encoding="utf8"))
    ok = sorted(c for c, e in cond_event.items() if e not in blind_events and gamma.get(c))
    conds = random.Random(SEED).sample(ok, 20)
    for chosen, extra in [(conds, [("include_tag", "true")]), (conds[:5], [])]:
        status, data, _ = api.get(GAMMA, "/markets", [("condition_ids", c) for c in chosen]
                                  + [("closed", "true"), ("limit", 100)] + extra)
        print(status, "asked", len(chosen), "returned", len(data), "with tags", sum(bool(m.get("tags")) for m in data),
              "include_tag" if extra else "no include_tag")


def analyse():
    saved = json.loads(DRAW_FILE.read_text(encoding="utf8"))
    test_map = json.loads(MAP_FILE.read_text(encoding="utf8"))
    domains = {k: set(v) for k, v in test_map["domains"].items()}
    events = saved["events"]
    wallets, _, _ = load()
    markets = defaultdict(set)
    for rows in wallets.values():
        for r in rows:
            markets[str(r["event_id"])].add(r["condition_id"])

    def hits(e):
        return {k for k, v in domains.items() if set(events[e]["tags"]) & v}

    by_event, by_market = Counter(), Counter()
    for e in events:
        n = len(hits(e))
        kind = "none" if n == 0 else "one" if n == 1 else "more"
        by_event[kind] += 1
        by_market[kind] += len(markets[e])
    n_events, n_markets = sum(by_event.values()), sum(by_market.values())
    print("events", n_events, "of", len(saved["draw"]), "tagged", sum(bool(events[e]["tags"]) for e in events),
          "different tags", len({t for e in events for t in events[e]["tags"]}))
    print("by event", {k: f"{v / n_events:.1%}" for k, v in by_event.items()})
    print("by market", {k: f"{v / n_markets:.1%}" for k, v in by_market.items()})
    economy = [e for e in events if set(events[e]["tags"]) & set(test_map["economy_type"])]
    print("economy-type events", len(economy), "also Politics", sum("Politics" in events[e]["tags"] for e in economy))


def compare():
    """The test map against Edvard's labels. Off the map counts as other (FR-15); more than one Domain is a miss."""
    with HAND_LABELS.open(encoding="utf8") as f:
        rows = list(csv.DictReader(f))
    assert all(r["domain"] for r in rows), "the hand labels must be committed first"
    if not HAND50_FILE.exists():
        found = {}
        for i in range(0, len(rows), 20):
            _, data, _ = api.get(GAMMA, "/markets", [("condition_ids", r["condition_id"]) for r in rows[i:i + 20]]
                                 + [("closed", "true"), ("limit", 100), ("include_tag", "true")])
            for m in data:
                found[m["conditionId"]] = labels(m.get("tags"))
        HAND50_FILE.write_text(json.dumps(found), encoding="utf8")
        print("requests", len(api.log))
    tags = json.loads(HAND50_FILE.read_text(encoding="utf8"))
    domains = {k: set(v) for k, v in json.loads(MAP_FILE.read_text(encoding="utf8"))["domains"].items()}
    agree = 0
    for r in rows:
        t = tags.get(r["condition_id"])
        hits = sorted(k for k, v in domains.items() if set(t or []) & v)
        got = "no tags" if t is None else "other" if not hits else hits[0] if len(hits) == 1 else "+".join(hits)
        if got == r["domain"]:
            agree += 1
        else:
            print(f'{r["n"]:>2}  Edvard {r["domain"]:<8} map {got:<16} {r["question"][:70]}  {t}')
    print(f"agree {agree} of {len(rows)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    {"endpoints": endpoints, "draw": draw, "batch": batch, "analyse": analyse, "compare": compare}[sys.argv[1]]()
