# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Cross-ticker results table from every lab/*/results/*.json -> lab/SUMMARY_TABLE.md.

Usage: uv run summarize.py [--labs lab]
"""
import argparse
import glob
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labs", default="lab")
    a = ap.parse_args()
    pos, trd = [], []
    for f in sorted(glob.glob(f"{a.labs}/**/results/*.json", recursive=True)):
        r = json.load(open(f))
        o = r.get("out_of_sample", {})
        if r.get("kind") == "trade":
            tag = " (modeled)" if r.get("modeled_options") else ""
            p = r.get("p_value_vs_random_entries")
            pr = r.get("protection", {})
            tk = r["ticker"] if len(r["ticker"]) < 30 else r["ticker"][:26] + "…)"
            prot = (f"{pr.get('verdict', '-')} | {pr['safe_allocation_per_trade']:.1%} | {pr['safe_annual_return']:+.1%}"
                    if "safe_allocation_per_trade" in pr else "not run | - | -")
            trd.append(f"| {tk} | {r['id']} | {r['instrument']}{tag} | {o.get('trades', 0)} | "
                       f"{o.get('worst', 0):+.1%} | {o.get('mean', 0):+.2%} | "
                       f"{r.get('random_entry_mean', 0):+.2%} | {'-' if p is None else f'{p:.2f}'} | {r['verdict']} | {prot} |")
        else:
            pr = r.get("protection", {})
            prot = (f"{pr['verdict']} | {pr['safe_exposure']:.0%}" if "safe_exposure" in pr else "not run | -")
            pos.append(f"| {r['ticker']} | {r['id']} | {o['strategy']['max_drawdown']:.0%} | {o['buy_hold']['max_drawdown']:.0%} | "
                       f"{o['strategy']['sharpe']:+.2f} | {o['buy_hold']['sharpe']:+.2f} | "
                       f"{o['p_value_timing']:.2f} | {r['verdict']} | {prot} |")
    out = ["# Results across all labs", ""]
    if pos:
        out += ["## Position strategies (vs buy & hold, out-of-sample)", "",
                "| Ticker | Hypothesis | MaxDD | B&H MaxDD | Sharpe | B&H Sharpe | p | Edge verdict | Protection | Safe exposure |",
                "|---|---|---|---|---|---|---|---|---|---|", *pos, ""]
    if trd:
        out += ["## Trade strategies (per trade, account returns, out-of-sample)", "",
                "| Ticker | Hypothesis | Instrument | Trades | Worst trade | Mean/trade | Random mean | p | Edge verdict | Protection | Safe size/trade | Safe ~annual |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|", *trd, "",
                "Protection = full-history check against -2%/trade and -10% drawdown limits; returns shown at the safe size.", ""]
    n_pass = sum("SUPPORTED" in x for x in pos + trd)
    out.append(f"{len(pos) + len(trd)} tests, {n_pass} supported.")
    Path(a.labs, "SUMMARY_TABLE.md").write_text("\n".join(out) + "\n")
    print("\n".join(out[-1:]), "->", Path(a.labs, "SUMMARY_TABLE.md"))


if __name__ == "__main__":
    main()
