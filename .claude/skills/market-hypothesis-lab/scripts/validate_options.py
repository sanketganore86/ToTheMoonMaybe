# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "numpy"]
# ///
"""Sanity-check the option model against a real, traded benchmark: the Cboe S&P 500
PutWrite index (^PUT), which sells a one-month at-the-money SPX put every month (third Friday)
and holds T-bill collateral. We replicate it with options.py (S&P 500 close, VIX as implied
vol, ^IRX rates, no trading costs, like the index) and compare month by month.

Usage: uv run validate_options.py --market lab/_market/data
Needs SPX.csv, VIX.csv, IRX.csv, PUTIDX.csv (fetched politely via fetch_data / sentiment).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import options as op  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="lab/_market/data")
    ap.add_argument("--atm-factor", type=float, default=None,
                    help="ATM IV = factor x VIX (VIX embeds OTM-put skew, so ATM IV is lower)")
    a = ap.parse_args()
    factor = a.atm_factor if a.atm_factor is not None else op.VIX_TO_ATM
    m = Path(a.market)
    rd = lambda n: pd.read_csv(m / f"{n}.csv", index_col=0, parse_dates=True)["Close"]
    spx, vix, irx, put = rd("SPX"), rd("VIX"), rd("IRX"), rd("PUTIDX")
    idx = spx.index.intersection(put.index)
    spx, put = spx[idx], put[idx]
    vix, irx = vix.reindex(idx).ffill() / 100, irx.reindex(idx).ffill() / 100

    # roll dates: third Friday of each month (or the trading day before)
    fridays = [d for d in pd.date_range(idx[0], idx[-1], freq="WOM-3FRI")]
    rolls = [idx[idx <= d][-1] for d in fridays if (idx <= d).any()]
    rows = []
    for t0, t1 in zip(rolls[:-1], rolls[1:]):
        S0, S1, K = spx[t0], spx[t1], spx[t0]
        T = (t1 - t0).days / 365
        prem = op.bs(S0, K, T, irx[t0], factor * vix[t0], "P")
        model = (prem + K * (np.exp(irx[t0] * T) - 1) - max(K - S1, 0)) / K
        real = put[t1] / put[t0] - 1
        rows.append((t1, model, real))
    r = pd.DataFrame(rows, columns=["date", "model", "real"]).set_index("date")
    corr = r.model.corr(r.real)
    ann = (1 + r).groupby(r.index.year).prod() - 1
    for name, part in (("calibration 2007-2016", r[r.index.year <= 2016]), ("check 2017+", r[r.index.year >= 2017])):
        print(f"{name}: mean bias {part.model.mean() - part.real.mean():+.3%}/month, corr {part.model.corr(part.real):.3f}")
    print(f"Months compared: {len(r)}  ({r.index[0].date()} -> {r.index[-1].date()})")
    print(f"Monthly correlation model vs real PUT index: {corr:.3f}")
    print(f"Mean monthly return  model {r.model.mean():+.3%}   real {r.real.mean():+.3%}")
    print(f"Worst month          model {r.model.min():+.2%}   real {r.real.min():+.2%}")
    print(f"Months with gain >= 1%: model {(r.model >= 0.01).mean():.0%}  real {(r.real >= 0.01).mean():.0%}")
    print("\nCalendar years (model | real):")
    for y, row in ann.iterrows():
        print(f"  {y}: {row.model:+7.1%} | {row.real:+7.1%}")
    bias = r.model.mean() - r.real.mean()
    verdict = "OK" if corr > 0.9 and abs(bias) < 0.002 else "CHECK"
    print(f"\nVerdict: {verdict} (want correlation > 0.9 and mean bias < 0.2%/month; bias {bias:+.3%})")


if __name__ == "__main__":
    main()
