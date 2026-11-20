# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "numpy", "matplotlib", "mplfinance"]
# ///
"""Candlestick charts for visual analysis. Read the PNGs (they are images) to spot structure:
trend vs chop, gaps, wick behaviour around turns, volume spikes.

Usage:
  uv run candles.py TSLA [--lab lab] [--split 0.7]
      -> charts/insample_weekly.png  whole in-sample period, weekly candles, MA10/MA40 (~50/200d)
         charts/insample_recent.png  last 150 in-sample days, daily candles, MA20/MA50,
                                     candlestick patterns marked (green ^ bullish, red v bearish)
  uv run candles.py TSLA --hypothesis lab/hypotheses/H001_x.py --start 2023-01-01 --end 2023-08-01
      -> charts/<H id>_<start>_<end>.png  daily candles with the strategy's entries (^) / exits (v)
         Use this AFTER a test, to see why it won or lost. Before a verdict, keep --end before
         the split date so the out-of-sample period stays unseen.
"""
import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import mplfinance as mpf

sys.path.insert(0, str(Path(__file__).parent))
import patterns  # noqa: E402

BULL = ["hammer", "bullish_engulfing", "three_white_soldiers"]
BEAR = ["shooting_star", "bearish_engulfing", "three_black_crows"]
STYLE = mpf.make_mpf_style(base_mpf_style="yahoo", gridstyle=":", rc={"font.size": 9})


def marker_series(df, mask, where, offset):
    s = pd.Series(np.nan, index=df.index)
    s[mask] = df[where][mask] * offset
    return s


def plot(df, path, title, mav, extra=None):
    kw = dict(type="candle", style=STYLE, volume=True, mav=mav, title=title, figsize=(13, 7),
              warn_too_much_data=10_000, savefig=dict(fname=path, dpi=110, bbox_inches="tight"))
    if extra:
        kw["addplot"] = extra
    mpf.plot(df, **kw)
    print(f"Saved {path}")


def pattern_markers(df):
    bull = pd.concat([patterns.ALL[p](df) for p in BULL], axis=1).any(axis=1)
    bear = pd.concat([patterns.ALL[p](df) for p in BEAR], axis=1).any(axis=1)
    ap = []
    if bull.any():
        ap.append(mpf.make_addplot(marker_series(df, bull, "Low", 0.97), type="scatter", marker="^", markersize=60, color="green"))
    if bear.any():
        ap.append(mpf.make_addplot(marker_series(df, bear, "High", 1.03), type="scatter", marker="v", markersize=60, color="red"))
    return ap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--lab", default="lab")
    ap.add_argument("--split", type=float, default=0.7)
    ap.add_argument("--hypothesis")
    ap.add_argument("--start")
    ap.add_argument("--end")
    a = ap.parse_args()

    lab = Path(a.lab)
    df = pd.read_csv(lab / "data" / f"{a.ticker.upper()}.csv", index_col=0, parse_dates=True)
    out = lab / "charts"
    out.mkdir(parents=True, exist_ok=True)
    cut = df.index[int(len(df) * a.split)]

    if a.hypothesis:
        spec = importlib.util.spec_from_file_location("h", a.hypothesis)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        held = pd.Series(mod.signal(df.copy()), index=df.index).astype(float).fillna(0).shift(1).fillna(0)
        w = df.loc[a.start:a.end]
        h = held.loc[w.index]
        on, off = (h > 0) & (h.shift(1).fillna(0) <= 0), (h <= 0) & (h.shift(1).fillna(0) > 0)
        extra = []
        if on.any():
            extra.append(mpf.make_addplot(marker_series(w, on, "Low", 0.97), type="scatter", marker="^", markersize=80, color="blue"))
        if off.any():
            extra.append(mpf.make_addplot(marker_series(w, off, "High", 1.03), type="scatter", marker="v", markersize=80, color="black"))
        extra.append(mpf.make_addplot(h, panel=2, color="purple", ylabel="position", type="line"))
        name = f"{Path(a.hypothesis).stem}_{w.index[0].date()}_{w.index[-1].date()}.png"
        title = f"{a.ticker.upper()} {Path(a.hypothesis).stem}: entries ^ exits v"
        plot(w, out / name, title, (50, 200) if len(w) > 200 else (20, 50), extra)
        return

    ins = df[df.index < cut]
    if a.start or a.end:
        w = ins.loc[a.start:a.end]
        plot(w, out / f"insample_{w.index[0].date()}_{w.index[-1].date()}.png",
             f"{a.ticker.upper()} daily (in-sample window)", (20, 50), pattern_markers(w))
        return
    wk = ins.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
    plot(wk, out / "insample_weekly.png", f"{a.ticker.upper()} weekly, in-sample to {cut.date()}", (10, 40))
    recent = ins.iloc[-150:]
    ctx = ins.iloc[-350:]  # warm-up so MA200 and pattern trend checks exist on the visible bars
    plot(recent, out / "insample_recent.png", f"{a.ticker.upper()} daily, last 150 in-sample days (^ bull / v bear patterns)",
         (20, 50), [mpf.make_addplot(x.loc[recent.index], type="scatter", marker=m, markersize=60, color=col)
                    for x, m, col in [(marker_series(ctx, pd.concat([patterns.ALL[p](ctx) for p in BULL], axis=1).any(axis=1), "Low", 0.97), "^", "green"),
                                      (marker_series(ctx, pd.concat([patterns.ALL[p](ctx) for p in BEAR], axis=1).any(axis=1), "High", 1.03), "v", "red")]
                    if x.loc[recent.index].notna().any()])


if __name__ == "__main__":
    main()
