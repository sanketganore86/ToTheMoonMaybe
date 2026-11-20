# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "yfinance>=0.2.40", "requests", "lxml"]
# ///
"""Which stocks have their earnings REACTION DAY today (known before the open). No trades.

Reaction day (as in lab/earnings, hypothesis E002): the session after a report made at/after 12:00 ET, or the
same session for a report before 12:00 ET. Report dates and times come from Yahoo (polite.wait), fetched before
the open; scheduled dates are public in advance, so nothing here comes from after the decision.

  uv run earnings_cal.py --root lab/paper --universe lab/forecast/universe.csv [--date D]

Writes <root>/earnings/<date>.json once: {"date", "made_at", "reaction_day": [symbols], "reports": {...},
"failed": [symbols whose dates could not be fetched]}. A failed lookup never stops the morning run.
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
ET = "America/New_York"


def reaction_day(when, date):
    """True if a report stamped `when` (ET) makes `date` its reaction day."""
    d = pd.Timestamp(date)
    day = when.tz_localize(None).normalize() if when.tzinfo else when.normalize()
    if when.hour >= 12:
        return day < d and (day + pd.tseries.offsets.BDay(1)) == d
    return day == d


def lookup(symbols, date):
    import yfinance as yf
    from polite import report_failure, report_success, wait
    reports, hits, failed = {}, [], []
    for s in symbols:
        wait("yahoo")
        try:
            e = yf.Ticker(s).get_earnings_dates(limit=8)
        except Exception as ex:
            report_failure("yahoo", 120); failed.append(s); print(f"{s}: lookup failed ({type(ex).__name__})"); continue
        report_success("yahoo")
        if e is None or e.empty:
            continue
        for w in pd.to_datetime(e.index).tz_convert(ET):
            # 4 days back, 10 ahead: the spreads agent skips a stock with a report before its exit day
            if -4 <= (w.tz_localize(None).normalize() - pd.Timestamp(date)).days <= 10:
                reports.setdefault(s, []).append(w.isoformat())
                if reaction_day(w, date) and s not in hits:
                    hits.append(s)
    return hits, reports, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--universe", required=True)
    ap.add_argument("--date", default=pd.Timestamp.now(tz=ET).strftime("%Y-%m-%d"))
    a = ap.parse_args()
    out = Path(a.root) / "earnings" / f"{a.date}.json"
    if out.exists():
        print(f"{out} already exists; written once."); return
    u = pd.read_csv(a.universe)
    # index ETFs (SPY, QQQ) have no earnings reports; looking them up only risks a Yahoo error and its back-off
    symbols = list(u[u.get("sector", pd.Series("", index=u.index)) != "Index ETF"].symbol)
    try:
        hits, reports, failed = lookup(symbols, a.date)
    except Exception as ex:  # never block the morning run
        hits, reports, failed = [], {}, symbols
        print(f"earnings lookup unavailable ({type(ex).__name__}); no stock is marked")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"date": a.date, "made_at": pd.Timestamp.now(tz=ET).isoformat(timespec="seconds"),
                               "reaction_day": hits, "reports": reports, "failed": failed}, indent=1))
    print(f"earnings reaction day on {a.date}: {', '.join(hits) or 'none'}" + (f" (lookup failed: {', '.join(failed)})" if failed else ""))


if __name__ == "__main__":
    main()
