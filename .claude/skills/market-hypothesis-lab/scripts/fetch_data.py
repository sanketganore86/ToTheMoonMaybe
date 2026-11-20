# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "yfinance>=0.2.40", "requests"]
# ///
"""Daily OHLCV (split/dividend adjusted) via the central cache.

Usage: uv run fetch_data.py TSLA --lab lab/TSLA [--start 2010-01-01] [--end 2026-01-01]
                            [--refresh] [--max-age 20]

The full history lives once in the machine-wide cache (see cache.py). A run makes no network
request if the cache is fresher than --max-age hours, otherwise it downloads only the days
since the last cached date. The lab receives a copy filtered to [--start, --end], so every
hypothesis in a lab is tested on the same frozen dataset until you re-run this.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import cache  # noqa: E402
from polite import report_failure, report_success, wait  # noqa: E402


def get_prices(symbol, refresh=False, max_age_h=cache.DEFAULT_MAX_AGE_H, quiet=False, start=None):
    """Update the cached history for symbol (incrementally) and return its cache path."""
    import yfinance as yf
    rel = f"prices/{cache.safe(symbol)}.csv"
    p, key = cache.path(rel), rel.rsplit(".", 1)[0]
    if p.exists() and start and pd.read_csv(p, index_col=0, parse_dates=True).index.min() > pd.Timestamp(start) + pd.Timedelta(days=7):
        if not quiet:
            print(f"{symbol}: cache starts after {start}; backfilling full history")
        p.unlink()
    if p.exists() and not refresh and cache.is_fresh(key, max_age_h):
        if not quiet:
            print(f"{symbol}: cache fresh, no download")
        return p
    since = None
    if p.exists():
        last = pd.read_csv(p, index_col=0, parse_dates=True).index.max()
        since = (last - pd.Timedelta(days=7)).strftime("%Y-%m-%d")  # overlap catches late corrections
    wait("yahoo")  # shared, cross-process rate limit (see polite.py)
    try:
        d = yf.Ticker(symbol).history(start=since, period=None if since else "max", auto_adjust=True)
    except Exception:
        report_failure("yahoo", 120)
        raise
    if d.empty:
        report_failure("yahoo", 120)
        raise SystemExit(f"No data returned for {symbol} (Yahoo may be throttling; retry later)")
    report_success("yahoo")
    d.index = d.index.tz_localize(None).normalize()
    d.index.name = "Date"
    d = d[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if since:
        # adjusted prices shift after splits/dividends: if the overlap disagrees, refetch everything
        old = pd.read_csv(p, index_col=0, parse_dates=True)
        ov = old.index.intersection(d.index)
        if len(ov) and (abs(old.loc[ov, "Close"] / d.loc[ov, "Close"] - 1) > 0.002).any():
            if not quiet:
                print(f"{symbol}: adjustment changed (split/dividend) -> full re-download")
            wait("yahoo")
            d = yf.Ticker(symbol).history(period="max", auto_adjust=True)
            d.index = d.index.tz_localize(None).normalize(); d.index.name = "Date"
            d = d[["Open", "High", "Low", "Close", "Volume"]].dropna()
            d.to_csv(p)
        else:
            cache.merge_csv(p, d)
    else:
        d.to_csv(p)
    cache.mark_refreshed(key)
    if not quiet:
        full = pd.read_csv(p, index_col=0, parse_dates=True)
        print(f"{symbol}: cache now {full.index[0].date()} -> {full.index[-1].date()} "
              f"({'+' + str(len(d)) + ' rows fetched' if since else 'full history fetched'})")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--lab", default="lab")
    ap.add_argument("--start", default=None, help="YYYY-MM-DD: first date copied into the lab")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD: last date copied into the lab")
    ap.add_argument("--refresh", action="store_true", help="ignore --max-age and check for new data")
    ap.add_argument("--max-age", type=float, default=cache.DEFAULT_MAX_AGE_H)
    a = ap.parse_args()
    t = a.ticker.upper()
    get_prices(t, a.refresh, a.max_age, start=a.start)
    out = Path(a.lab) / "data" / f"{cache.safe(t) if t.startswith('^') else t}.csv"
    cache.materialize(f"prices/{cache.safe(t)}.csv", out, None, a.start, a.end)
    df = pd.read_csv(out, index_col=0, parse_dates=True)
    print(f"Lab copy {out} ({len(df)} rows, {df.index[0].date()} -> {df.index[-1].date()})")


if __name__ == "__main__":
    main()
