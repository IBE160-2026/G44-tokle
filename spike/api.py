"""Tiny polite HTTP helper for the data spike. Read-only, public endpoints, no keys."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DATA = "https://data-api.polymarket.com"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

RAW = Path(__file__).parent / "raw"
DELAY = 1.5  # seconds between requests, on purpose slow
_last = [0.0]
log = []  # every request made, for the request count in FINDINGS


def get(base, path, params=None, save_as=None):
    wait = DELAY - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    url = base + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"User-Agent": "liquidoracle-spike/0.1 (student project)"})
    status, body = None, None
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status, body = r.status, r.read()
            headers = dict(r.headers)
    except urllib.error.HTTPError as e:
        status, body, headers = e.code, e.read(), dict(e.headers)
    _last[0] = time.time()
    log.append((status, url))
    try:
        data = json.loads(body)
    except Exception:
        data = body.decode("utf8", "replace")[:500]
    if save_as:
        RAW.mkdir(exist_ok=True)
        (RAW / save_as).write_text(json.dumps(data), encoding="utf8")
    rl = {k: v for k, v in headers.items() if "ratelimit" in k.lower() or "retry" in k.lower()}
    return status, data, rl
