"""Polite HTTP: the one way this skill talks to data providers.

Every fetcher must go through `request()` (or call `wait()` before a library call it does not
control, such as yfinance). Guarantees, shared across ALL processes on this machine via a
locked state file, so two background downloads can never double the rate to one host:

  - a minimum interval between requests per host (HOST_LIMITS)
  - a daily request cap per host (DAILY_CAP); exceeding it stops the fetch for the day
  - on HTTP 429/503 or a "slow down" body: honour Retry-After, else exponential backoff
    (30 s, 60 s, 120 s ... capped at 15 min), and every process pauses that host
  - circuit breaker: 5 consecutive failures pause the host for 1 hour and raise PoliteGiveUp

Edit the tables below only to be MORE conservative than the providers' published limits.
"""
import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

# seconds between requests (provider limits in comments; we stay well under them)
HOST_LIMITS = {
    "www.sec.gov": 0.5,            # SEC fair access: max 10/s  -> we use 2/s
    "data.sec.gov": 0.5,
    "api.finra.org": 2.0,          # no published cap for the public API; be modest
    "api.gdeltproject.org": 30.0,  # GDELT asks for <= 1 per 5 s and 429s heavily -> 1 per 30 s
    "yahoo": 3.0,                  # yfinance (one logical fetch per ticker)
    "paper-api.alpaca.markets": 0.5,  # Alpaca Trading API: 200/min -> we use 2/s (paper only)
}
DEFAULT_INTERVAL = 2.0
DAILY_CAP = {"www.sec.gov": 20000, "data.sec.gov": 2000, "api.finra.org": 500,
             "api.gdeltproject.org": 150, "yahoo": 300,
             "paper-api.alpaca.markets": 2000}
MAX_BACKOFF = 900
BREAKER_FAILS = 5
BREAKER_PAUSE = 3600
STATE_DIR = Path(os.environ.get("POLITE_STATE_DIR", Path.home() / ".cache" / "market-hypothesis-lab" / "polite"))
SLOW_DOWN_MARKERS = ("please limit requests", "rate limit", "too many requests")


class PoliteGiveUp(RuntimeError):
    pass


@contextmanager
def _state(host):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"{host}.json"
    with open(path, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        raw = fh.read()
        st = json.loads(raw) if raw.strip() else {}
        today = time.strftime("%Y-%m-%d")
        if st.get("day") != today:
            st.update(day=today, count=0)
        st.setdefault("last", 0.0); st.setdefault("cooldown_until", 0.0); st.setdefault("fails", 0)
        yield st
        fh.seek(0); fh.truncate(); fh.write(json.dumps(st)); fh.flush()


def wait(host):
    """Block until this host may be called again, then reserve the slot."""
    interval = HOST_LIMITS.get(host, DEFAULT_INTERVAL)
    while True:
        with _state(host) as st:
            if st["count"] >= DAILY_CAP.get(host, 1000):
                raise PoliteGiveUp(f"{host}: daily cap {DAILY_CAP.get(host, 1000)} reached; resume tomorrow")
            now = time.time()
            ready = max(st["last"] + interval, st["cooldown_until"])
            if now >= ready:
                st["last"] = now
                st["count"] += 1
                return
        time.sleep(min(ready - now, 60))


def _penalize(host, seconds):
    with _state(host) as st:
        st["fails"] += 1
        pause = BREAKER_PAUSE if st["fails"] >= BREAKER_FAILS else seconds
        st["cooldown_until"] = max(st["cooldown_until"], time.time() + pause)
        return st["fails"], pause


def _ok(host):
    with _state(host) as st:
        st["fails"] = 0


def report_failure(host, seconds=60):
    """For library calls (yfinance) that failed: back off this host for everyone."""
    fails, pause = _penalize(host, seconds)
    if fails >= BREAKER_FAILS:
        raise PoliteGiveUp(f"{host}: {fails} consecutive failures; paused {pause // 60} min")


def report_success(host):
    _ok(host)


_SESSION = None


def request(method, url, tries=6, **kw):
    """requests.request with the guarantees above. Returns a Response with status 200,
    or raises PoliteGiveUp. Use a descriptive User-Agent where the provider asks for one."""
    global _SESSION
    import requests
    if _SESSION is None:
        _SESSION = requests.Session()
    host = urlparse(url).hostname
    kw.setdefault("timeout", 120)
    for attempt in range(tries):
        wait(host)
        try:
            r = _SESSION.request(method, url, **kw)
        except requests.RequestException as e:
            fails, pause = _penalize(host, min(30 * 2 ** attempt, MAX_BACKOFF))
            print(f"  [polite] {host}: {type(e).__name__}; pausing {pause:.0f}s", flush=True)
            if fails >= BREAKER_FAILS:
                raise PoliteGiveUp(f"{host}: circuit open after {fails} failures") from e
            continue
        body_head = r.text[:200].lower() if r.headers.get("content-type", "").startswith("text") else ""
        throttled = r.status_code in (429, 503) or any(m in body_head for m in SLOW_DOWN_MARKERS)
        if r.status_code == 200 and not throttled:
            _ok(host)
            return r
        if r.status_code == 404:
            _ok(host)  # a missing document is not the provider pushing back
            r.raise_for_status()
        retry_after = r.headers.get("Retry-After")
        backoff = float(retry_after) if retry_after and retry_after.isdigit() else min(30 * 2 ** attempt, MAX_BACKOFF)
        fails, pause = _penalize(host, backoff)
        print(f"  [polite] {host}: HTTP {r.status_code}{' (slow-down notice)' if throttled else ''}; "
              f"pausing {pause:.0f}s", flush=True)
        if fails >= BREAKER_FAILS:
            raise PoliteGiveUp(f"{host}: circuit open after {fails} consecutive failures; paused 1 h")
    raise PoliteGiveUp(f"{host}: gave up after {tries} attempts")
