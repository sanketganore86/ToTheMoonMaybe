# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "numpy", "yfinance>=0.2.40", "requests"]
# ///
"""Market-sentiment features from free, point-in-time data.

Free historical news/social sentiment is not available, so this uses what markets themselves
reveal about fear and risk appetite, all known at each day's close:

  Market-wide (downloaded into <lab>/data/):
    vix          CBOE VIX, 30-day implied vol of the S&P 500 (fear gauge)
    vix_z        VIX z-score vs its trailing 252d mean/std (how unusual today's fear is)
    vix_spike    VIX / its 20d mean - 1 (sudden fear jump)
    term         VIX / VIX3M; > 1 = backwardation = acute panic (short-term fear > long-term)
    skew         CBOE SKEW (price of crash protection; high = tail-hedging demand)
    credit       HYG/LQD ratio vs its 50d mean - 1 (> 0 = credit markets risk-on)
    spy_trend    SPY close / SPY 200d SMA - 1 (broad market regime)
  Stock-specific (from the stock's own OHLCV):
    attention    log(volume / 50d median volume) (abnormal attention)
    gap          Open / previous Close - 1 (overnight news reaction)

Usage:
  uv run sentiment.py fetch   --lab lab/AXP [--start 2005-01-01]  # market series + ^IRX (cached)
  uv run sentiment.py explore AXP --lab lab/AXP [--split 0.7]     # in-sample conditional returns
In a hypothesis:
  from sentiment import features
  f = features(Path(__file__).parents[1], df)   # DataFrame aligned to df.index, no lookahead
"""
import argparse
from pathlib import Path

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

MARKET = {"VIX": "^VIX", "VIX3M": "^VIX3M", "SKEW": "^SKEW", "HYG": "HYG", "LQD": "LQD", "SPY": "SPY"}


def _read(lab, name):
    return pd.read_csv(Path(lab) / "data" / f"{name}.csv", index_col=0, parse_dates=True)["Close"]


def features(lab, df):
    """lab may be None: then df.attrs["lab"] (set by the engines) is used.
    Sentiment features aligned to df.index. Market series are forward-filled onto the
    stock's calendar and only use data up to each date (rolling windows only)."""
    lab = lab if lab is not None else df.attrs["lab"]
    idx = df.index
    m = {k: _read(lab, k) for k in MARKET}
    m = pd.DataFrame(m).sort_index().ffill()
    f = pd.DataFrame(index=m.index)
    f["vix"] = m["VIX"]
    f["vix_z"] = (m["VIX"] - m["VIX"].rolling(252).mean()) / m["VIX"].rolling(252).std()
    f["vix_spike"] = m["VIX"] / m["VIX"].rolling(20).mean() - 1
    f["term"] = m["VIX"] / m["VIX3M"]
    f["skew"] = m["SKEW"]
    ratio = m["HYG"] / m["LQD"]
    f["credit"] = ratio / ratio.rolling(50).mean() - 1
    f["spy_trend"] = m["SPY"] / m["SPY"].rolling(200).mean() - 1
    f = f.reindex(f.index.union(idx)).ffill().reindex(idx)
    vol = df["Volume"].replace(0, np.nan)
    f["attention"] = np.log(vol / vol.rolling(50).median())
    f["gap"] = df["Open"] / df["Close"].shift(1) - 1
    from alt_sentiment import alt_features  # insider / short interest / news, when fetched
    return f.join(alt_features(lab, df))


def fetch(lab, start, refresh=False):
    """Market series via the central cache (incremental, no network while fresh)."""
    import cache
    from fetch_data import get_prices
    out = Path(lab) / "data"
    out.mkdir(parents=True, exist_ok=True)
    for name, sym in {**MARKET, "IRX": "^IRX"}.items():
        get_prices(sym, refresh, quiet=True, start=start)
        cache.materialize(f"prices/{cache.safe(sym)}.csv", out / f"{name}.csv", None, start, None)
        d = pd.read_csv(out / f"{name}.csv", index_col=0, parse_dates=True)
        print(f"{name:6} {len(d)} rows {d.index[0].date()} -> {d.index[-1].date()}")


def tstat(x):
    x = x.dropna()
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else np.nan


def explore(ticker, lab, split, start=None):
    df = pd.read_csv(Path(lab) / "data" / f"{ticker.upper()}.csv", index_col=0, parse_dates=True)
    f = features(lab, df)
    if start:  # analyse only the window where the data of interest exists (features keep warm-up)
        keep = df.index >= pd.Timestamp(start)
        df, f = df[keep], f[keep]
    cut = df.index[int(len(df) * split)]
    ins = df.index < cut
    c = df["Close"]
    nxt = c.pct_change().shift(-1)
    f20 = c.shift(-20) / c - 1
    print(f"SENTIMENT, IN-SAMPLE ONLY: {df.index[0].date()} -> {df.index[ins][-1].date()} (OOS from {cut.date()} hidden)\n")
    print(f"{'condition':>50} {'days':>5} {'next-day':>9} {'t':>6} {'fwd 20d':>8}")

    def row(name, mask):
        mk = mask & ins
        if mk.sum() < 15:
            return
        print(f"{name:>50} {int(mk.sum()):>5} {nxt[mk].mean():>+9.3%} {tstat(nxt[mk]):>+6.2f} {f20[mk].mean():>+8.2%}")

    row("all days", pd.Series(True, index=df.index))
    print("-- market fear (VIX) --")
    q = pd.Series(np.nan, index=df.index)
    vix_in = f["vix"][ins]
    edges = vix_in.quantile([0.2, 0.4, 0.6, 0.8]).to_list()  # in-sample quantiles only
    for i, (lo, hi) in enumerate(zip([-np.inf] + edges, edges + [np.inf])):
        row(f"VIX quintile {i+1} ({lo:.0f}-{hi:.0f})" if np.isfinite(lo) and np.isfinite(hi) else f"VIX quintile {i+1}", (f["vix"] > lo) & (f["vix"] <= hi))
    row("VIX z-score > +2 (extreme fear)", f["vix_z"] > 2)
    row("VIX spike > +30% vs 20d mean", f["vix_spike"] > 0.3)
    row("term > 1 (backwardation, panic)", f["term"] > 1)
    row("term < 0.85 (complacency)", f["term"] < 0.85)
    print("-- tail-hedging (SKEW) --")
    sk = f["skew"][ins].quantile([0.2, 0.8]).to_list()
    row(f"SKEW low (<{sk[0]:.0f})", f["skew"] < sk[0])
    row(f"SKEW high (>{sk[1]:.0f})", f["skew"] > sk[1])
    print("-- credit risk appetite (HYG/LQD) --")
    row("credit risk-on (> +1% vs 50d)", f["credit"] > 0.01)
    row("credit risk-off (< -1% vs 50d)", f["credit"] < -0.01)
    print("-- broad market regime --")
    row("SPY above 200d SMA", f["spy_trend"] > 0)
    row("SPY below 200d SMA", f["spy_trend"] < 0)
    print("-- stock attention / news reaction --")
    row("attention > 2x median volume", f["attention"] > np.log(2))
    row("high attention AND up day", (f["attention"] > np.log(2)) & (c.pct_change() > 0))
    row("high attention AND down day", (f["attention"] > np.log(2)) & (c.pct_change() < 0))
    g = f["gap"]
    gs = g.rolling(60).std()
    row("gap up > 2 sd (good news)", g > 2 * gs)
    row("gap down > 2 sd (bad news)", g < -2 * gs)
    row("gap down > 2 sd but closed > open", (g < -2 * gs) & (c > df["Open"]))
    if "insider_buy_90" in f:
        print("-- insiders (SEC Form 4, by filing date) --")
        row("any insider open-market BUY in last 90d", f["insider_buy_90"] > 0)
        row("cluster: >=2 insider buys in last 90d", f["insider_buyers_90"] >= 2)
        row("no insider buys in last 90d", f["insider_buy_90"] == 0)
        row("net insider flow positive (90d)", f["insider_net_90"] > 0)
        row("heavy discretionary selling (top 20% of 90d sales)", f["insider_sell_90"] > f["insider_sell_90"][ins].quantile(0.8))
    if "short_dtc" in f:
        print("-- short interest (FINRA, +10 business days publication lag) --")
        row("days-to-cover z > +1 (shorts crowding)", f["short_dtc_z"] > 1)
        row("days-to-cover z < -1 (shorts covering)", f["short_dtc_z"] < -1)
        row("short interest +25% over 3 months", f["short_chg_3m"] > 0.25)
        row("short interest -25% over 3 months", f["short_chg_3m"] < -0.25)
    if "news_tone" in f:
        print("-- news (GDELT tone and volume, next-session) --")
        row("news tone z < -1.5 (unusually negative)", f["news_tone_z"] < -1.5)
        row("news tone z > +1.5 (unusually positive)", f["news_tone_z"] > 1.5)
        row("news burst (volume z > 2)", f["news_vol_z"] > 2)
        row("news burst AND negative tone", (f["news_vol_z"] > 2) & (f["news_tone"] < f["news_tone"].rolling(180, min_periods=60).median()))
        row("news burst AND positive tone", (f["news_vol_z"] > 2) & (f["news_tone"] > f["news_tone"].rolling(180, min_periods=60).median()))
    r = c.pct_change()
    beta = r[ins].cov(f["vix"].pct_change()[ins]) / f["vix"].pct_change()[ins].var()
    print(f"\nSensitivity of daily return to VIX % change (in-sample): {beta:+.3f} "
          f"(more negative = stock sells off harder when fear rises)")
    print("Rows are overlapping/conditional means; with ~20 rows, expect ~1 |t|>2 by chance.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("fetch"); a1.add_argument("--lab", required=True); a1.add_argument("--start", default="2005-01-01")
    a1.add_argument("--refresh", action="store_true")
    a2 = sub.add_parser("explore"); a2.add_argument("ticker"); a2.add_argument("--lab", required=True); a2.add_argument("--split", type=float, default=0.7)
    a2.add_argument("--start", help="analyse only from this date (e.g. 2018-01-15 for short interest / news)")
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(a.lab, a.start, a.refresh)
    else:
        explore(a.ticker, a.lab, a.split, a.start)


if __name__ == "__main__":
    main()
