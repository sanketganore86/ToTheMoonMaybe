# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "numpy"]
# ///
"""Pre-test screen: run a hypothesis on the IN-SAMPLE period only, split into two halves.

Usage: uv run screen.py lab/AXP/hypotheses/H004_x.py --lab lab/AXP [--split 0.7] [--cost-bps 10]

An idea worth spending an out-of-sample test on should beat its criterion in BOTH halves.
Ideas that work in only one half are usually one episode (e.g. 2008) in disguise. Screening
never touches out-of-sample data and is not recorded in the journal, so it costs nothing.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from backtest import load_module, position_returns, stats  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hypothesis")
    ap.add_argument("--lab", default="lab")
    ap.add_argument("--lab-root", default="lab", help="pooled trade hypotheses: folder with one lab per ticker")
    ap.add_argument("--split", type=float, default=0.7)
    ap.add_argument("--cost-bps", type=float, default=10)
    a = ap.parse_args()

    mod = load_module(a.hypothesis)
    if hasattr(mod, "entries"):
        return screen_trades(mod, a)
    ticker = mod.HYPOTHESIS.get("ticker").upper()
    full = pd.read_csv(Path(a.lab) / "data" / f"{ticker}.csv", index_col=0, parse_dates=True)
    start = mod.HYPOTHESIS.get("start")
    win = full[full.index >= pd.Timestamp(start)] if start else full
    cut = win.index[int(len(win) * a.split)]
    df = full[full.index < cut]  # the signal never even sees OOS rows
    sig = pd.Series(mod.signal(df.copy()), index=df.index).astype(float).fillna(0).clip(-1, 1)
    ret, held, fees = position_returns(df, sig, a.cost_bps / 1e4, start)
    net = held * ret - fees
    mid = len(ret) // 2
    if mid < 2:
        ap.error("screen needs at least one complete open-to-open interval per half")
    halves = (slice(0, mid - 1), slice(mid, len(ret)))
    verdicts = []
    print(f"SCREEN {Path(a.hypothesis).stem} [{ticker}] in-sample only, next-open fills, costs {a.cost_bps:g} bps")
    for name, sl in zip(("half 1", "half 2"), halves):
        s, b = stats(net.iloc[sl], held.iloc[sl]), stats(ret.iloc[sl], pd.Series(1.0, index=ret.iloc[sl].index))
        better_sharpe = s["sharpe"] > b["sharpe"]
        better_dd = s["max_drawdown"] > b["max_drawdown"]
        verdicts.append((better_sharpe, better_dd))
        print(f"  {name} {ret.index[sl][0].date()}..{ret.index[sl][-1].date()}: strategy Sharpe {s['sharpe']:+.2f} "
              f"MaxDD {s['max_drawdown']:.0%} expo {s['exposure']:.0%} changes {s['trades']} | "
              f"buy&hold Sharpe {b['sharpe']:+.2f} MaxDD {b['max_drawdown']:.0%}")
    crit = mod.HYPOTHESIS.get("pass_criteria", {})
    want_sharpe = crit.get("beat_buy_hold_sharpe", True)
    want_dd = crit.get("beat_buy_hold_drawdown", False)
    ok = all((not want_sharpe or s_) and (not want_dd or d_) for s_, d_ in verdicts)
    if not want_sharpe and not want_dd:
        # standalone signal: both halves profitable AND the weaker half at least half as good
        sh = [stats(net.iloc[sl], held.iloc[sl])["sharpe"] for sl in halves]
        ok = min(sh) > 0 and min(sh) >= 0.5 * max(sh)
    print("  =>", "PASSES screen: worth one out-of-sample test" if ok else
          "FAILS screen: unstable in-sample. Do not test; note it in the journal as screened out.")


def screen_trades(mod, a):
    """Trade hypotheses (single or pooled): in each in-sample half, mean account return per
    trade must be > 0 AND beat the same exits on randomly timed entries (stratified by ticker)."""
    import trade_backtest as tb
    H = mod.HYPOTHESIS
    inst = H["instrument"]
    params, ex = H.get("params", {}), {**tb.DEFAULT_EXIT, **H.get("exit", {})}
    pooled = "tickers" in H
    tickers = [x.upper() for x in H["tickers"]] if pooled else [H["ticker"].upper()]
    rng = np.random.default_rng(3)
    halves = {"half 1": ([], []), "half 2": ([], [])}
    print(f"SCREEN {Path(a.hypothesis).stem} [{', '.join(tickers)} {inst}] in-sample only")
    for tk in tickers:
        tlab = Path(a.lab_root) / tk if pooled else Path(a.lab)
        full = pd.read_csv(tlab / "data" / f"{tk}.csv", index_col=0, parse_dates=True)
        start = full.index.searchsorted(pd.Timestamp(H["start"])) if H.get("start") else 260
        start = max(start, 260)
        cut = start + int((len(full) - start) * a.split)
        df = full.iloc[:cut].copy()  # never sees OOS rows
        df.attrs["lab"] = str(tlab)
        m = tb.Market(df, tlab)
        sig = pd.Series(mod.entries(df.copy()), index=df.index).fillna(False).astype(bool).to_numpy()
        mid = start + (cut - start) // 2
        for name, lo, hi in (("half 1", start, mid), ("half 2", mid, cut)):
            t = tb.simulate(m, sig, lo, hi, inst, params, ex, 5e-4)
            halves[name][0].extend(t.ret.tolist())
            if len(t):
                candidates = np.arange(lo, min(hi, len(df) - 1))
                picks = rng.choice(candidates, size=min(150, len(candidates)), replace=False)
                random_trades = [tb.run_trade(m, int(i), inst, params, ex, 5e-4, end=hi) for i in picks]
                returns = [ret for _, ret, reason in random_trades if reason != "split"]
                base = np.mean(returns) if returns else np.nan
                halves[name][1].extend([base] * len(t))  # ticker's average random trade, weighted by its trade count
    ok = True
    for name, (rets, base) in halves.items():
        if len(rets) < 5:
            print(f"  {name}: only {len(rets)} trades"); ok = False; continue
        r = np.array(rets)
        good = r.mean() > 0 and r.mean() > np.mean(base)
        ok &= good
        print(f"  {name}: {len(r)} trades, win {(r > 0).mean():.0%}, mean {r.mean():+.2%}, worst {r.min():+.1%} | "
              f"random entries mean {np.mean(base):+.2%} {'✅' if good else '❌'}")
    print("  =>", "PASSES screen: worth one out-of-sample test" if ok else
          "FAILS screen: unstable in-sample. Do not test; note it in the journal as screened out.")


if __name__ == "__main__":
    main()
