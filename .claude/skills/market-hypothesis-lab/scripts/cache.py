# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2"]
# ///
"""Central, machine-wide data cache shared by every lab and session.

Every fetcher writes the FULL downloaded history here once, then copies (materialises) a
date-filtered view into the lab. Re-running a fetch is cheap:
  - fresh  : if the cache was refreshed less than --max-age hours ago, no network at all
  - update : otherwise only data newer than what is cached is requested (incremental)
  - filter : --start / --end limit both what is downloaded and what lands in the lab

Layout (override the root with MHL_CACHE):
  ~/.cache/market-hypothesis-lab/data/
    prices/<SYMBOL>.csv            daily OHLCV (stocks, ^VIX, SPY, ^IRX, ...)
    finra/<TICKER>.csv             short interest
    gdelt/<TICKER>.csv             news tone + volume
    edgar/<TICKER>/form4.csv       insider transactions (+ done.txt of fetched filings)
    meta.json                      last refresh time per item

Usage:
  uv run cache.py status                      # what is cached, how fresh, date ranges
  uv run cache.py seed --labs lab             # import data already sitting in lab folders
  uv run cache.py materialize AXP --lab lab/AXP --start 2015-01-01   # re-copy with a new window
"""
import argparse
import fcntl
import json
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

ROOT = Path(os.environ.get("MHL_CACHE", Path.home() / ".cache" / "market-hypothesis-lab" / "data"))
DEFAULT_MAX_AGE_H = 20  # data are daily; refreshing more often than this just loads providers

# lab file name  <-  (cache path relative to ROOT, date column; None = CSV index)
def lab_files(ticker):
    t = ticker.upper()
    return {
        f"{t}.csv": (f"prices/{t}.csv", None),
        "finra_short_interest.csv": (f"finra/{t}.csv", "settlementDate"),
        "gdelt_news.csv": (f"gdelt/{t}.csv", "date"),
        "edgar_form4.csv": (f"edgar/{t}/form4.csv", "filing_date"),
    }


MARKET_LAB_NAMES = {"VIX": "^VIX", "VIX3M": "^VIX3M", "SKEW": "^SKEW", "HYG": "HYG", "LQD": "LQD",
                    "SPY": "SPY", "IRX": "^IRX", "SPX": "^GSPC", "PUTIDX": "^PUT"}


def safe(symbol):
    return symbol.replace("^", "_").upper()


def path(rel):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def _meta():
    ROOT.mkdir(parents=True, exist_ok=True)
    with open(ROOT / "meta.json", "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        raw = fh.read()
        m = json.loads(raw) if raw.strip() else {}
        yield m
        fh.seek(0); fh.truncate(); fh.write(json.dumps(m, indent=1, sort_keys=True))


def is_fresh(key, max_age_h=DEFAULT_MAX_AGE_H):
    with _meta() as m:
        t = m.get(key, {}).get("refreshed")
    return t is not None and (time.time() - t) < max_age_h * 3600


def mark_refreshed(key, **info):
    with _meta() as m:
        m[key] = {**m.get(key, {}), **info, "refreshed": time.time()}


def get_info(key):
    with _meta() as m:
        return m.get(key, {})


def merge_csv(p, new, date_col=None, key_cols=None):
    """Append new rows to a cached CSV, de-duplicating (newest wins)."""
    if p.exists() and len(new):
        old = pd.read_csv(p, index_col=0 if date_col is None else None, parse_dates=date_col is None)
        if date_col is None:
            new = pd.concat([old[~old.index.isin(new.index)], new]).sort_index()
        else:
            keys = key_cols or [date_col]
            new = pd.concat([old, new]).drop_duplicates(keys, keep="last").sort_values(date_col)
    elif p.exists():
        return
    new.to_csv(p, index=date_col is None)


def materialize(rel, lab_file, date_col=None, start=None, end=None):
    """Copy a cached file into a lab, optionally keeping only [start, end]."""
    src = ROOT / rel
    if not src.exists():
        return False
    lab_file.parent.mkdir(parents=True, exist_ok=True)
    if not start and not end:
        shutil.copyfile(src, lab_file)
        return True
    if date_col is None:
        d = pd.read_csv(src, index_col=0, parse_dates=True)
        d = d.loc[start:end]
        d.to_csv(lab_file)
    else:
        d = pd.read_csv(src, parse_dates=[date_col])
        if start:
            d = d[d[date_col] >= pd.Timestamp(start)]
        if end:
            d = d[d[date_col] <= pd.Timestamp(end)]
        d.to_csv(lab_file, index=False)
    return True


def seed(labs="lab"):
    """Import data already in lab folders into the cache (never overwrites a larger cache file)."""
    n = 0
    for labdir in sorted(Path(labs).iterdir()):
        data = labdir / "data"
        if not data.is_dir():
            continue
        tk = labdir.name.upper()
        items = dict(lab_files(tk)) if not tk.startswith("_") else {}
        for name, sym in MARKET_LAB_NAMES.items():
            items[f"{name}.csv"] = (f"prices/{safe(sym)}.csv", None)
        for lab_name, (rel, _) in items.items():
            src, dst = data / lab_name, ROOT / rel
            if src.exists() and (not dst.exists() or src.stat().st_size > dst.stat().st_size):
                path(rel)
                shutil.copyfile(src, dst)
                n += 1
        done = data / "edgar_form4_done.txt"
        dst = ROOT / f"edgar/{tk}/done.txt"
        if done.exists() and (not dst.exists() or done.stat().st_size > dst.stat().st_size):
            path(f"edgar/{tk}/done.txt")
            shutil.copyfile(done, dst)
            n += 1
    print(f"Seeded {n} files into {ROOT}")


def status():
    with _meta() as m:
        meta = dict(m)
    if not ROOT.exists():
        print("cache empty"); return
    print(f"Cache: {ROOT}")
    for p in sorted(ROOT.rglob("*.csv")):
        rel = str(p.relative_to(ROOT))
        try:
            col = "filing_date" if "edgar" in rel else "settlementDate" if "finra" in rel else "date" if "gdelt" in rel else None
            d = pd.read_csv(p, usecols=[col] if col else [0])
            s = pd.to_datetime(d.iloc[:, 0])
            rng = f"{s.min().date()} -> {s.max().date()} ({len(d)} rows)" if len(d) else "empty"
        except Exception as e:
            rng = f"? ({e.__class__.__name__})"
        key = rel.rsplit(".", 1)[0]
        ref = meta.get(key, {}).get("refreshed")
        age = f"{(time.time() - ref) / 3600:.1f} h ago" if ref else "never via cache"
        print(f"  {rel:32} {rng:42} refreshed {age}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    s = sub.add_parser("seed"); s.add_argument("--labs", default="lab")
    m = sub.add_parser("materialize")
    m.add_argument("ticker"); m.add_argument("--lab", required=True)
    m.add_argument("--start"); m.add_argument("--end")
    a = ap.parse_args()
    if a.cmd == "status":
        status()
    elif a.cmd == "seed":
        seed(a.labs)
    else:
        for lab_name, (rel, col) in lab_files(a.ticker).items():
            if materialize(rel, Path(a.lab) / "data" / lab_name, col, a.start, a.end):
                print(f"  {lab_name} <- cache/{rel}")


if __name__ == "__main__":
    main()
