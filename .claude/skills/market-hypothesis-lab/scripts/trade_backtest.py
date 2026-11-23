# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "numpy", "matplotlib"]
# ///
"""Per-trade test: does an entry signal + fixed exits reach a modest target (default +1% per
trade on the capital the position ties up) more reliably than the same trade entered at random?

Usage: uv run trade_backtest.py lab/AXP/hypotheses/T001_x.py --lab lab/AXP [--split 0.7]
                                [--sims 300] [--stock-cost-bps 5] [--no-journal]

A trade hypothesis file defines:
    HYPOTHESIS = {
        "ticker": "AXP",
        "statement": "...", "rationale": "...",
        "instrument": "stock_long",   # stock_long stock_short covered_call collar cash_secured_put
                                      # put_credit_spread call_debit_spread long_call long_put
        "params": {"dte": 30, "short_delta": 0.30, "width_pct": 0.05,    # options only
                   "allocation": 1.0},  # fraction of the ACCOUNT the position's capital uses
        "exit": {"take_profit": 0.01, "stop_loss": 0.03, "max_days": 20},
        "pass_criteria": {"max_p_value": 0.05, "min_trades": 20, "min_expectancy": 0.0,
                          "min_win_rate": 0.0, "max_worst_trade": -0.10},
        "start": "2018-03-01",        # optional evaluation window
    }
    def entries(df) -> pd.Series of bool   # True at the close where the signal is known

Pooled test (rare signals such as insider buying): put "tickers": [...] instead of "ticker",
keep the file in lab/_pooled/hypotheses/, and run with --lab lab/_pooled --lab-root lab.
The identical rule runs on every ticker, trades are pooled, and the random-entry null is
stratified by ticker. Read sentiment with features(df.attrs["lab"], df).

Mechanics (conservative): enter at the NEXT session's open; one position at a time. Stock
trades use intraday High/Low for limit (+TP) and stop fills, assuming the stop is hit first
when both are touched on the same day, and gaps fill at the open. Option structures are
marked at each close with the modeled prices from options.py (MODELED, label them so) and
exit on TP / SL / max_days / expiry. Returns are net of costs, on capital tied up.
Null: the same exits on randomly timed entries in the same OOS period -> p-value of the mean.

Sizing: every return, target and stop is measured on the ACCOUNT. allocation = 1.0 means the
position's capital (stock cost, put collateral, spread max-loss, option premium) is the whole
account slice for that trade. For levered structures use a small allocation: a long call with
allocation 0.05 risks 5% of the account, so +1% of the account is +20% on the premium. Keep
allocation 1.0 for stock, covered calls, collars and cash-secured puts.
"""
import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import options as op  # noqa: E402
import protect  # noqa: E402

DEFAULT_EXIT = {"take_profit": 0.01, "stop_loss": 0.03, "max_days": 20}
DEFAULT_CRIT = {"max_p_value": 0.05, "min_trades": 20, "min_expectancy": 0.0, "max_worst_trade": -0.10}
STOCKS = ("stock_long", "stock_short")


def load(path):
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Market:
    def __init__(self, df, lab):
        self.df = df
        self.o, self.h, self.l, self.c = (df[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
        self.dates = df.index
        irx = pd.read_csv(Path(lab) / "data" / "IRX.csv", index_col=0, parse_dates=True)["Close"]
        self.r = op.rate_series(df, irx).to_numpy(float)
        self.iv = op.atm_iv_series(df).bfill().to_numpy(float)


def run_trade(m, i, inst, params, ex, stock_cost, *, end=None):
    """Open at session i's open (signal was at i-1's close). Returns (exit_idx, ret, reason)."""
    alloc = params.get("allocation", 1.0)
    tp, sl, maxd = ex["take_profit"] / alloc, ex["stop_loss"] / alloc, ex["max_days"]  # on position capital
    n = len(m.c) if end is None else end
    j, ret, why = _run(m, i, inst, params, tp, sl, maxd, n, stock_cost)
    if n < len(m.c) and (why == "end" or (why == "time" and j - i + 1 < maxd)):
        return j, ret * alloc, "split"
    return j, ret * alloc, why  # account return


def _run(m, i, inst, params, tp, sl, maxd, n, stock_cost):
    if inst in STOCKS:
        side = 1 if inst == "stock_long" else -1
        e = m.o[i]
        cost = 2 * stock_cost
        up, dn = (e * (1 + tp), e * (1 - sl)) if side == 1 else (e * (1 - tp), e * (1 + sl))
        for j in range(i, min(i + maxd, n)):
            o, h, l = m.o[j], m.h[j], m.l[j]
            if side == 1:
                if j > i and o <= dn: return j, o / e - 1 - cost, "stop(gap)"
                if l <= dn: return j, -sl - cost, "stop"
                if j > i and o >= up: return j, o / e - 1 - cost, "target(gap)"
                if h >= up: return j, tp - cost, "target"
            else:
                if j > i and o >= dn: return j, 1 - o / e - cost, "stop(gap)"
                if h >= dn: return j, -sl - cost, "stop"
                if j > i and o <= up: return j, 1 - o / e - cost, "target(gap)"
                if l <= up: return j, tp - cost, "target"
        j = min(i + maxd, n) - 1
        return j, side * (m.c[j] / e - 1) - cost, "time"
    dte = params.get("dte", 30)
    S0, r0, iv0 = m.o[i], m.r[i - 1], m.iv[i - 1]
    T0 = dte / 365
    pos = op.open_structure(inst, S0, T0, r0, iv0, params)
    if any(k == "S" for _, k, _ in pos["legs"]):
        pos["entry_cost"] += stock_cost * S0
    cap = pos["capital"]
    for j in range(i, n):
        days = (m.dates[j] - m.dates[i]).days
        T = max(T0 - days / 365, 0.0)
        expiry = T <= 0 or days >= dte
        v = op.mark(pos, m.c[j], T, m.r[j], m.iv[j])
        xc = op.exit_cost(pos, m.c[j], T, m.r[j], m.iv[j], expiry)
        if any(k == "S" for _, k, _ in pos["legs"]):
            xc += stock_cost * m.c[j]
        ret = (v - pos["v0"] - pos["entry_cost"] - xc) / cap
        if j > i and ret >= tp: return j, ret, "target"
        if j > i and ret <= -sl: return j, ret, "stop"
        if expiry: return j, ret, "expiry"
        if j - i + 1 >= maxd: return j, ret, "time"
    return n - 1, ret, "end"


def simulate(m, sig, lo, hi, inst, params, ex, stock_cost):
    """Walk entries and exits in [lo, hi), omitting trades still open at an internal cutoff."""
    trades, i = [], lo
    while i < hi:
        if sig[i - 1] and i < len(m.c) - 1:
            j, ret, why = run_trade(m, i, inst, params, ex, stock_cost, end=hi)
            if why != "split":
                trades.append((m.dates[i], m.dates[j], j - i + 1, ret, why))
            i = j + 1
        else:
            i += 1
    return pd.DataFrame(trades, columns=["entry", "exit", "sessions", "ret", "reason"])


def summarize(t, ex, years):
    if t.empty:
        return {"trades": 0}
    eq = (1 + t.ret).cumprod()
    return {"trades": int(len(t)), "trades_per_year": round(len(t) / max(years, 1e-9), 1),
            "win_rate": float((t.ret > 0).mean()), "hit_target": float(t.reason.str.startswith("target").mean()),
            "mean": float(t.ret.mean()), "median": float(t.ret.median()), "worst": float(t.ret.min()),
            "best": float(t.ret.max()), "avg_sessions": float(t.sessions.mean()),
            "compounded": float(eq.iloc[-1] - 1), "max_drawdown": float((eq / eq.cummax() - 1).min())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hypothesis")
    ap.add_argument("--lab", default="lab", help="lab holding the journal (pooled: e.g. lab/_pooled)")
    ap.add_argument("--lab-root", default="lab", help="pooled only: folder containing one lab per ticker")
    ap.add_argument("--split", type=float, default=0.7)
    ap.add_argument("--sims", type=int, default=300)
    ap.add_argument("--stock-cost-bps", type=float, default=5, help="per side")
    ap.add_argument("--no-journal", action="store_true")
    a = ap.parse_args()

    mod = load(a.hypothesis)
    H = mod.HYPOTHESIS
    hid, inst = Path(a.hypothesis).stem, H["instrument"]
    params, ex = H.get("params", {}), {**DEFAULT_EXIT, **H.get("exit", {})}
    crit = {**DEFAULT_CRIT, **H.get("pass_criteria", {})}
    stock_cost = a.stock_cost_bps / 1e4
    if "spread_pct" in params:
        op.SPREAD_PCT = params["spread_pct"]
    pooled = "tickers" in H
    tickers = [t.upper() for t in H["tickers"]] if pooled else [H["ticker"].upper()]
    lab = Path(a.lab)  # pooled: the journal lab (e.g. lab/_pooled); per-ticker data in <lab-root>/<T>
    root = Path(a.lab_root) if pooled else None
    rng = np.random.default_rng(0)

    books, leaks = [], []
    for tk in tickers:
        tlab = root / tk if pooled else lab
        df = pd.read_csv(tlab / "data" / f"{tk}.csv", index_col=0, parse_dates=True)
        df.attrs["lab"] = str(tlab)  # hypotheses read sentiment via features(df.attrs["lab"], df)
        sig_full = pd.Series(mod.entries(df.copy()), index=df.index).fillna(False).astype(bool)
        for k in sorted(rng.choice(np.arange(300, len(df) - 1), size=min(8, len(df) - 301), replace=False)):
            cut_df = df.iloc[: k + 1].copy()
            cut_df.attrs["lab"] = str(tlab)
            s = pd.Series(mod.entries(cut_df)).fillna(False).astype(bool)
            if bool(s.iloc[-1]) != bool(sig_full.iloc[k]):
                leaks.append(f"{tk} {df.index[k].date()}")
        m = Market(df, tlab)
        sig = sig_full.to_numpy()
        start = df.index.searchsorted(pd.Timestamp(H["start"])) if H.get("start") else 260  # 1y warm-up
        start = max(start, 260)
        cut = start + int((len(df) - start) * a.split)
        t_is = simulate(m, sig, start, cut, inst, params, ex, stock_cost).assign(ticker=tk)
        t_oos = simulate(m, sig, cut, len(df), inst, params, ex, stock_cost).assign(ticker=tk)
        books.append(dict(tk=tk, df=df, m=m, sig=sig, start=start, cut=cut, t_is=t_is, t_oos=t_oos))

    yrs_is = sum((b["df"].index[b["cut"] - 1] - b["df"].index[b["start"]]).days for b in books) / 365.25 / len(books)
    yrs_oos = sum((b["df"].index[-1] - b["df"].index[b["cut"]]).days for b in books) / 365.25 / len(books)
    t_is = pd.concat([b["t_is"] for b in books], ignore_index=True)
    t_oos = pd.concat([b["t_oos"] for b in books], ignore_index=True).sort_values("entry", ignore_index=True)
    s_is, s_oos = summarize(t_is.sort_values("entry"), ex, yrs_is), summarize(t_oos, ex, yrs_oos)

    # null: same exits on random OOS entry sessions, stratified: each ticker contributes as many
    # random trades as it had real ones, so a ticker with many signals cannot dominate the null
    p, null_mean = None, float("nan")
    if len(t_oos):
        cache, means = {}, []
        for _ in range(a.sims):
            rets = []
            for b in books:
                k = len(b["t_oos"])
                if not k:
                    continue
                cand = np.arange(b["cut"], len(b["df"]) - 2)
                for i in rng.choice(cand, size=min(k, len(cand)), replace=False):
                    key = (b["tk"], int(i))
                    if key not in cache:
                        cache[key] = run_trade(b["m"], int(i), inst, params, ex, stock_cost)[1]
                    rets.append(cache[key])
            means.append(np.mean(rets))
        p = (np.sum(np.array(means) >= s_oos["mean"]) + 1) / (a.sims + 1)
        null_mean = float(np.mean(means))

    bh = np.mean([b["df"]["Close"].iloc[-1] / b["df"]["Close"].iloc[b["cut"]] - 1 for b in books])
    per_ticker = {b["tk"]: {"oos_trades": int(len(b["t_oos"])),
                            "oos_mean": float(b["t_oos"].ret.mean()) if len(b["t_oos"]) else None}
                  for b in books}
    ticker = "POOLED(" + ",".join(tickers) + ")" if pooled else tickers[0]
    res = {"id": hid, "ticker": ticker, "kind": "trade", "instrument": inst, "params": params, "exit": ex,
           "statement": H["statement"], "rationale": H.get("rationale", ""), "criteria": crit,
           "modeled_options": inst not in STOCKS,
           "split_date": ", ".join(f"{b['tk']} {b['df'].index[b['cut']].date()}" for b in books) if pooled
           else str(books[0]["df"].index[books[0]["cut"]].date()),
           "window_start": str(books[0]["df"].index[books[0]["start"]].date()), "lookahead_violations": leaks,
           "in_sample": s_is, "out_of_sample": s_oos, "per_ticker": per_ticker, "p_value_vs_random_entries": p,
           "random_entry_mean": null_mean, "buy_hold_oos_total": float(bh),
           "tested_at": datetime.now().isoformat(timespec="seconds")}
    journal = lab / "JOURNAL.md"
    prior = len(re.findall(r"^## [HT]\d", journal.read_text(), flags=re.M)) if journal.exists() else 0
    n_tests = prior + (0 if a.no_journal else 1)
    res["tests_so_far"], res["bonferroni_alpha"] = n_tests, crit["max_p_value"] / max(n_tests, 1)
    o = s_oos
    checks = {"no_lookahead": not leaks, "min_trades": o.get("trades", 0) >= crit["min_trades"],
              "p_value": p is not None and p <= crit["max_p_value"],
              "expectancy": o.get("trades", 0) > 0 and o["mean"] > crit["min_expectancy"],
              "worst_trade": o.get("trades", 0) > 0 and o["worst"] >= crit["max_worst_trade"]}
    if crit.get("min_win_rate"):
        checks["win_rate"] = o.get("trades", 0) > 0 and o["win_rate"] >= crit["min_win_rate"]
    res["checks"] = checks
    res["verdict"] = "SUPPORTED" if all(checks.values()) else "REJECTED"
    res["survives_multiple_testing"] = res["verdict"] == "SUPPORTED" and p <= res["bonferroni_alpha"]
    # capital protection (separate from the pre-registered edge verdict; full history)
    res["protection"] = protect.assess_trades(pd.concat([
        simulate(b["m"], b["sig"], b["start"], len(b["df"]), inst, params, ex, stock_cost)
        for b in books
    ], ignore_index=True),
                                              params.get("allocation", 1.0), H.get("protection"))
    res["usable"] = res["verdict"] == "SUPPORTED" and res["protection"]["verdict"] != "FAIL"

    out = lab / "results" if not a.no_journal else Path(a.hypothesis).parent / "_debug_results"
    out.mkdir(parents=True, exist_ok=True)  # debug runs never land in results/ or the summary
    (out / f"{hid}.json").write_text(json.dumps(res, indent=2, default=str))
    pd.concat([t_is.assign(period="in_sample"), t_oos.assign(period="out_of_sample")]).to_csv(out / f"{hid}_trades.csv", index=False)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(12, 4))
        for t, lbl in ((t_is, "in-sample"), (t_oos, "out-of-sample")):
            if len(t):
                ax[0].plot(t.exit, (1 + t.ret).cumprod(), label=lbl)
                ax[1].hist(t.ret * 100, bins=30, alpha=0.6, label=lbl)
        ax[0].set_title(f"{hid}: equity, one trade at a time"); ax[0].legend()
        ax[1].axvline(ex["take_profit"] * 100, color="green", ls="--"); ax[1].axvline(-ex["stop_loss"] * 100, color="red", ls="--")
        ax[1].set_title("return per trade (%)"); ax[1].legend()
        fig.tight_layout(); fig.savefig(out / f"{hid}.png", dpi=110); plt.close(fig)
    except Exception as e:
        print("plot skipped:", e)

    def fmt(s):
        if not s.get("trades"):
            return "no trades"
        return (f"{s['trades']} trades ({s['trades_per_year']}/yr) | win {s['win_rate']:.0%} | hit +{ex['take_profit']:.0%} "
                f"{s['hit_target']:.0%} | mean {s['mean']:+.2%} | median {s['median']:+.2%} | worst {s['worst']:+.1%} | "
                f"compounded {s['compounded']:+.0%} | maxDD {s['max_drawdown']:.0%} | avg {s['avg_sessions']:.1f} sessions")

    tag = " (MODELED option prices)" if res["modeled_options"] else ""
    lines = [f"## {hid} — {res['verdict']}",
             f"*{ticker} {inst}{tag}, tested {res['tested_at']}, exits TP +{ex['take_profit']:.1%} / SL -{ex['stop_loss']:.1%} / "
             f"max {ex['max_days']} sessions, window from {res['window_start']}, split {res['split_date']}*", "",
             f"**Hypothesis:** {H['statement']}", f"**Rationale:** {H.get('rationale', '')}", "",
             f"- In-sample: {fmt(s_is)}", f"- **Out-of-sample: {fmt(s_oos)}**",
             f"- Random-entry baseline (same exits, OOS): mean {null_mean:+.2%} per trade; p-value "
             f"{p if p is None else round(p, 3)} (Bonferroni alpha after {n_tests} tests: {res['bonferroni_alpha']:.4f})",
             f"- Buy & hold over the OOS period: {res['buy_hold_oos_total']:+.0%}" + (" (average across tickers)" if pooled else ""),
             *([f"- Per ticker OOS: " + ", ".join(f"{k} {v['oos_trades']} trades" + (f" {v['oos_mean']:+.2%}" if v['oos_mean'] is not None else "")
                                                   for k, v in per_ticker.items())] if pooled else []),
             "- Checks: " + ", ".join(f"{k}={'✅' if v else '❌'}" for k, v in checks.items()),
             f"- Survives multiple-testing correction: {'yes' if res['survives_multiple_testing'] else 'no'}",
             *protect.journal_lines(res["protection"], "trade"),
             "", "**Interpretation / next step:** _TODO_", ""]
    entry = "\n".join(lines)
    print(entry)
    if leaks:
        print(f"⚠️  LOOKAHEAD at {leaks}: entries() changed when future data was removed. Result invalid.")
    if not a.no_journal:
        if not journal.exists():
            journal.write_text("# Hypothesis Journal\n\nEach entry is pre-registered, tested once out-of-sample, and kept "
                               "whether it passed or failed.\n\n")
        with journal.open("a") as f:
            f.write(entry + "\n")
        print(f"Recorded in {journal}; trades in {out / (hid + '_trades.csv')}")


if __name__ == "__main__":
    main()
