# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "numpy", "matplotlib"]
# ///
"""Test one pre-registered hypothesis and record the verdict in the lab journal.

Usage: uv run backtest.py lab/hypotheses/H001_name.py [--lab lab] [--ticker TSLA]
                          [--split 0.7] [--cost-bps 10] [--perms 2000] [--no-journal]

A hypothesis file defines:
    HYPOTHESIS = {
        "ticker": "TSLA",
        "statement": "...falsifiable claim...",
        "rationale": "...why it might be true...",
        "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
        "start": "2018-01-01",   # optional: evaluate only from here (e.g. when the data starts)
    }
    def signal(df: pd.DataFrame) -> pd.Series:
        # target position in [-1, 1] decided at the CLOSE of each day, using data up to
        # and including that day only. The engine holds it during the NEXT day.

The verdict is decided on the out-of-sample period only.
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

sys.path.insert(0, str(Path(__file__).parent))  # lets hypotheses `from patterns import ...`
import protect  # noqa: E402

ANN = 252
DEFAULT_CRITERIA = {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10}


def load_module(path):
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sharpe(x):
    s = x.std()
    return float(x.mean() / s * np.sqrt(ANN)) if s > 0 else 0.0


def stats(net, held):
    eq = (1 + net).cumprod()
    years = len(net) / ANN
    trades = int((held.diff().abs() > 0).sum())
    return {
        "total_return": float(eq.iloc[-1] - 1),
        "cagr": float(eq.iloc[-1] ** (1 / years) - 1) if years > 0 else 0.0,
        "ann_vol": float(net.std() * np.sqrt(ANN)),
        "sharpe": sharpe(net),
        "max_drawdown": float((eq / eq.cummax() - 1).min()),
        "exposure": float((held != 0).mean()),
        "trades": trades,
    }


def lookahead_check(mod, df, full_sig, n=8, seed=0):
    """Recompute the signal on truncated history; any mismatch means the signal peeked ahead."""
    rng = np.random.default_rng(seed)
    idx = rng.choice(np.arange(250, len(df) - 1), size=min(n, len(df) - 251), replace=False)
    bad = []
    for i in sorted(idx):
        s = mod.signal(df.iloc[: i + 1].copy())
        a, b = float(pd.Series(s).fillna(0).iloc[-1]), float(full_sig.iloc[i])
        if not np.isclose(a, b, equal_nan=True):
            bad.append(str(df.index[i].date()))
    return bad


def permutation_p(held, ret, cost, actual, n, seed=1):
    """Null: same positions (same exposure/turnover) but timing randomised by circular shift."""
    rng = np.random.default_rng(seed)
    h, r = held.to_numpy(), ret.to_numpy()
    c = (np.abs(np.diff(h, prepend=h[0])) * cost)
    beats = 0
    for _ in range(n):
        k = rng.integers(20, len(h) - 20)
        net = np.roll(h, k) * r - np.roll(c, k)
        sd = net.std(ddof=1)
        if sd > 0 and net.mean() / sd * np.sqrt(ANN) >= actual:
            beats += 1
    return (beats + 1) / (n + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hypothesis")
    ap.add_argument("--lab", default="lab")
    ap.add_argument("--ticker")
    ap.add_argument("--split", type=float, default=0.7)
    ap.add_argument("--cost-bps", type=float, default=10, help="per unit of position change, covers fees+slippage")
    ap.add_argument("--perms", type=int, default=2000)
    ap.add_argument("--no-journal", action="store_true", help="dry run: do not record (use only for debugging code)")
    ap.add_argument("--protection-only", action="store_true",
                    help="add/refresh only the capital-protection field of an EXISTING result; verdicts untouched")
    a = ap.parse_args()

    mod = load_module(a.hypothesis)
    H = mod.HYPOTHESIS
    hid = Path(a.hypothesis).stem
    ticker = (a.ticker or H.get("ticker", "TSLA")).upper()
    crit = {**DEFAULT_CRITERIA, **H.get("pass_criteria", {})}
    lab = Path(a.lab)

    df = pd.read_csv(lab / "data" / f"{ticker}.csv", index_col=0, parse_dates=True)
    sig = pd.Series(mod.signal(df.copy()), index=df.index).astype(float).fillna(0).clip(-1, 1)
    leaks = lookahead_check(mod, df, sig)

    ret = df["Close"].pct_change().fillna(0)
    held = sig.shift(1).fillna(0)
    cost = a.cost_bps / 1e4
    net = held * ret - held.diff().abs().fillna(held.abs()) * cost
    if a.protection_only:
        rp = lab / "results" / f"{hid}.json"
        old = json.loads(rp.read_text())
        old["protection"] = protect.assess_positions(net, H.get("protection"))
        rp.write_text(json.dumps(old, indent=2))
        print(f"{hid}: protection {old['protection']['verdict']}, safe exposure {old['protection']['safe_exposure']:.0%}")
        return

    # optional evaluation window: signals are computed on full history (warm-up), but the
    # 70/30 split and all metrics use only dates where the hypothesis' data exists
    if H.get("start"):
        keep = df.index >= pd.Timestamp(H["start"])
        df, sig, ret, held, net = df[keep], sig[keep], ret[keep], held[keep], net[keep]
        held.iloc[0] = 0.0  # no free entry on day one of the window
    cut = df.index[int(len(df) * a.split)]
    seg = {"in_sample": df.index < cut, "out_of_sample": df.index >= cut}
    res = {"id": hid, "ticker": ticker, "statement": H["statement"], "rationale": H.get("rationale", ""),
           "criteria": crit, "cost_bps": a.cost_bps, "split_date": str(cut.date()),
           "lookahead_violations": leaks, "tested_at": datetime.now().isoformat(timespec="seconds")}
    for name, m in seg.items():
        res[name] = {"period": f"{df.index[m][0].date()} -> {df.index[m][-1].date()}",
                     "strategy": stats(net[m], held[m]),
                     "buy_hold": stats(ret[m], pd.Series(1.0, index=ret[m].index))}

    oos = res["out_of_sample"]
    m = seg["out_of_sample"]
    p = permutation_p(held[m], ret[m], cost, oos["strategy"]["sharpe"], a.perms)
    oos["p_value_timing"] = p

    # multiple-testing bookkeeping: every recorded test spends some of the alpha budget
    journal = lab / "JOURNAL.md"
    prior = len(re.findall(r"^## [HT]\d", journal.read_text(), flags=re.M)) if journal.exists() else 0
    n_tests = prior + (0 if a.no_journal else 1)
    res["tests_so_far"] = n_tests
    res["bonferroni_alpha"] = crit["max_p_value"] / max(n_tests, 1)

    checks = {
        "no_lookahead": not leaks,
        "p_value": p <= crit["max_p_value"],
        "min_trades": oos["strategy"]["trades"] >= crit["min_trades"],
    }
    if crit.get("beat_buy_hold_sharpe"):
        checks["beat_buy_hold_sharpe"] = oos["strategy"]["sharpe"] > oos["buy_hold"]["sharpe"]
    if crit.get("beat_buy_hold_drawdown"):
        checks["beat_buy_hold_drawdown"] = oos["strategy"]["max_drawdown"] > oos["buy_hold"]["max_drawdown"]
    if "min_sharpe" in crit:
        checks["min_sharpe"] = oos["strategy"]["sharpe"] >= crit["min_sharpe"]
    res["checks"] = checks
    res["verdict"] = "SUPPORTED" if all(checks.values()) else "REJECTED"
    res["survives_multiple_testing"] = res["verdict"] == "SUPPORTED" and p <= res["bonferroni_alpha"]
    res["protection"] = protect.assess_positions(net, H.get("protection"))  # full history
    res["usable"] = res["verdict"] == "SUPPORTED" and res["protection"]["verdict"] != "FAIL"

    out = lab / "results" if not a.no_journal else Path(a.hypothesis).parent / "_debug_results"
    out.mkdir(parents=True, exist_ok=True)  # debug runs never land in results/ or the summary
    (out / f"{hid}.json").write_text(json.dumps(res, indent=2))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.plot((1 + net).cumprod(), label="strategy (net of costs)")
        ax.plot((1 + ret).cumprod(), label="buy & hold", alpha=0.7)
        ax.axvline(cut, color="grey", ls="--", lw=1)
        ax.text(cut, ax.get_ylim()[1], "  out-of-sample →", va="top", fontsize=9, color="grey")
        ax.set_yscale("log"); ax.set_title(f"{hid} [{ticker}] — {res['verdict']}"); ax.legend()
        fig.tight_layout(); fig.savefig(out / f"{hid}.png", dpi=110); plt.close(fig)
    except Exception as e:  # plotting is a convenience, never a reason to fail the test
        print("plot skipped:", e)

    def fmt(s):
        return (f"Sharpe {s['sharpe']:+.2f} | CAGR {s['cagr']:+.1%} | MaxDD {s['max_drawdown']:.1%} | "
                f"exposure {s['exposure']:.0%} | position changes {s['trades']}")

    lines = [f"## {hid} — {res['verdict']}",
             f"*{ticker}, tested {res['tested_at']}, costs {a.cost_bps:g} bps, split {res['split_date']}*", "",
             f"**Hypothesis:** {H['statement']}", f"**Rationale:** {H.get('rationale','')}", "",
             f"- In-sample  strategy: {fmt(res['in_sample']['strategy'])}",
             f"- In-sample  buy&hold: {fmt(res['in_sample']['buy_hold'])}",
             f"- **Out-of-sample strategy: {fmt(oos['strategy'])}**",
             f"- Out-of-sample buy&hold: {fmt(oos['buy_hold'])}",
             f"- Timing p-value (OOS, circular-shift null): {p:.3f}  "
             f"(Bonferroni alpha after {n_tests} tests: {res['bonferroni_alpha']:.4f})",
             f"- Checks: " + ", ".join(f"{k}={'✅' if v else '❌'}" for k, v in checks.items()),
             f"- Survives multiple-testing correction: {'yes' if res['survives_multiple_testing'] else 'no'}",
             *protect.journal_lines(res["protection"], "position"),
             "", "**Interpretation / next step:** _TODO_", ""]
    entry = "\n".join(lines)
    print(entry)
    if leaks:
        print(f"⚠️  LOOKAHEAD: signal changed when future data was removed, at {leaks}. Fix the signal; result is invalid.")
    if not a.no_journal:
        if not journal.exists():
            journal.write_text("# Hypothesis Journal\n\nEach entry is pre-registered, tested once out-of-sample, and kept "
                               "whether it passed or failed.\n\n")
        with journal.open("a") as f:
            f.write(entry + "\n")
        print(f"Recorded in {journal}; chart at {out / (hid + '.png')}")


if __name__ == "__main__":
    main()
