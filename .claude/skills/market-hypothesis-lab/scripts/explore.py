# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "numpy"]
# ///
"""Descriptive statistics that seed hypotheses. Looks only at the IN-SAMPLE period
so that exploring the data does not leak information about the out-of-sample test.

Usage: uv run explore.py TSLA [--lab lab] [--split 0.7]
"""
import argparse
from pathlib import Path

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import patterns  # noqa: E402


def tstat(x):
    x = x.dropna()
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else np.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--lab", default="lab")
    ap.add_argument("--split", type=float, default=0.7)
    a = ap.parse_args()

    df = pd.read_csv(Path(a.lab) / "data" / f"{a.ticker.upper()}.csv", index_col=0, parse_dates=True)
    cut = df.index[int(len(df) * a.split)]
    df = df[df.index < cut]
    r = df["Close"].pct_change().dropna()
    print(f"IN-SAMPLE ONLY: {df.index[0].date()} -> {df.index[-1].date()}  ({len(r)} daily returns)")
    print(f"Out-of-sample begins {cut.date()} and is NOT shown here.\n")

    ann = 252
    print("== Return distribution ==")
    print(f"mean/day {r.mean():.4%}  std/day {r.std():.4%}  ann.vol {r.std()*np.sqrt(ann):.1%}")
    print(f"skew {r.skew():.2f}  excess kurtosis {r.kurt():.2f}  up-days {(r>0).mean():.1%}")
    print(f"buy&hold Sharpe (rf=0) {r.mean()/r.std()*np.sqrt(ann):.2f}\n")

    print("== Calendar-year returns ==")
    yr = (1 + r).groupby(r.index.year).prod() - 1
    print(yr.map(lambda v: f"{v:+.1%}").to_string(), "\n")

    print("== Autocorrelation (daily returns | absolute returns) ==")
    for lag in (1, 2, 3, 5, 10, 20):
        print(f"lag {lag:>2}: {r.autocorr(lag):+.3f} | {r.abs().autocorr(lag):+.3f}")
    print("(|returns| autocorr >> returns autocorr => volatility clusters but direction is hard)\n")

    print("== Day-of-week mean return (t-stat) ==")
    for d, g in r.groupby(r.index.dayofweek):
        print(f"{['Mon','Tue','Wed','Thu','Fri'][d]}: {g.mean():+.3%}  t={tstat(g):+.2f}  n={len(g)}")
    print()

    print("== Month-of-year mean return (t-stat) ==")
    for m, g in r.groupby(r.index.month):
        print(f"{m:>2}: {g.mean():+.3%}  t={tstat(g):+.2f}")
    print()

    print("== Next-day return after large moves (|r| > 2 sd) ==")
    sd = r.rolling(60).std()
    nxt = r.shift(-1)
    big_up, big_dn = r > 2 * sd, r < -2 * sd
    for name, m in (("after big UP", big_up), ("after big DOWN", big_dn), ("all days", r.notna())):
        print(f"{name:>15}: next-day mean {nxt[m].mean():+.3%}  t={tstat(nxt[m]):+.2f}  n={int(m.sum())}")
    print()

    print("== Trend: forward 20d return by position vs 50d/200d moving average ==")
    c = df["Close"]
    fwd = c.shift(-20) / c - 1
    for w in (50, 200):
        above = c > c.rolling(w).mean()
        print(f"MA{w}: above {fwd[above].mean():+.2%} (n={int(above.sum())})  below {fwd[~above & c.rolling(w).mean().notna()].mean():+.2%}")
    print("(overlapping 20d windows: t-stats would be inflated, treat as directional hints only)\n")

    print("== Volatility regime: next-day return by rolling-20d-vol quintile ==")
    vol = r.rolling(20).std()
    q = pd.qcut(vol, 5, labels=False)
    for k, g in nxt.groupby(q):
        print(f"Q{int(k)+1} (vol~{vol[q==k].mean()*np.sqrt(ann):.0%}): next-day mean {g.mean():+.3%} t={tstat(g):+.2f}")

    print("\n== Candlestick patterns: what happened next (in-sample) ==")
    print(f"{'pattern':>22} {'n':>5} {'next-day':>9} {'t':>6} {'next-5d':>8} {'5d up%':>7}")
    fwd5 = c.shift(-5) / c - 1
    base5 = fwd5.mean()
    for name, fn in patterns.ALL.items():
        full = fn(df).fillna(False).astype(bool)
        m = full.reindex(r.index, fill_value=False)
        if m.sum() < 5:
            continue
        f5 = fwd5[full].dropna()
        print(f"{name:>22} {int(m.sum()):>5} {nxt[m].mean():>+9.3%} {tstat(nxt[m]):>+6.2f} {f5.mean():>+8.2%} {(f5 > 0).mean():>7.0%}")
    print(f"{'(all days)':>22} {len(r):>5} {nxt.mean():>+9.3%} {'':>6} {base5:>+8.2%} {(fwd5.dropna() > 0).mean():>7.0%}")
    print("(compare each row with the all-days baseline; |t| < 2 is indistinguishable from noise)")

    dd = c / c.cummax() - 1
    print(f"\n== Max drawdown (buy&hold, in-sample): {dd.min():.1%} on {dd.idxmin().date()}")


if __name__ == "__main__":
    main()
