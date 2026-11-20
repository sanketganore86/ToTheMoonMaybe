"""Capital protection: the user's first principle. Every engine reports, besides its
pre-registered edge verdict, whether the strategy at its planned size stays inside hard loss
limits over the FULL history (in-sample + out-of-sample, so 2008/2020-type crashes count),
and the largest size that would have.

Limits (override per hypothesis with "protection": {...}):
  max_trade_loss  0.02   worst single trade (or day, for position strategies) as account loss
  max_drawdown    0.10   worst peak-to-trough fall of the account
Concurrent trades (pooled tests) share one account: overlapping positions add up, and the
sum of simultaneously open positions may never exceed 100% of the account.
"""
import numpy as np
import pandas as pd

DEFAULT = {"max_trade_loss": 0.02, "max_drawdown": 0.10}


def _account_path(trades, k):
    """Account equity if each trade gets k x its planned allocation; P&L booked at exit."""
    r = (trades.assign(acct=trades.ret * k).groupby("exit")["acct"].sum().sort_index())
    eq = np.cumprod(1 + r.to_numpy())
    dd = (eq / np.maximum.accumulate(eq) - 1).min() if len(eq) else 0.0
    return eq, float(dd)


def max_concurrent(trades):
    if trades.empty:
        return 0
    ev = pd.concat([pd.Series(1, index=trades.entry), pd.Series(-1, index=trades.exit + pd.Timedelta(seconds=1))])
    return int(ev.sort_index().cumsum().max())


def assess_trades(trades, alloc, limits=None):
    """trades: DataFrame(entry, exit, ret) with ret already = account return at the planned allocation."""
    L = {**DEFAULT, **(limits or {})}
    if trades.empty:
        return {"limits": L, "verdict": "NO TRADES"}
    conc = max_concurrent(trades)

    def ok(k):
        _, dd = _account_path(trades, k)
        return (k * trades.ret).min() >= -L["max_trade_loss"] and dd >= -L["max_drawdown"] and k * alloc * conc <= 1.0 + 1e-9

    _, dd1 = _account_path(trades, 1.0)
    planned_ok = ok(1.0)
    lo, hi = 0.0, 1.0
    if planned_ok:
        lo = 1.0
    else:
        for _ in range(50):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    years = max((trades.exit.max() - trades.entry.min()).days / 365.25, 1e-9)
    _, dd_safe = _account_path(trades, lo)
    eq_safe, _ = _account_path(trades, lo)
    return {
        "limits": L, "planned_allocation": alloc, "max_concurrent_positions": conc,
        "planned_worst_trade": float(trades.ret.min()), "planned_max_drawdown": dd1,
        "planned_verdict": "PASS" if planned_ok else "FAIL",
        "safe_allocation_per_trade": float(alloc * lo),
        "safe_mean_per_trade": float(trades.ret.mean() * lo), "safe_worst_trade": float(trades.ret.min() * lo),
        "safe_max_drawdown": dd_safe,
        "safe_annual_return": float(eq_safe[-1] ** (1 / years) - 1) if lo > 0 else 0.0,
        "verdict": "PASS" if planned_ok else ("PASS ONLY WHEN SIZED DOWN" if lo > 0.005 else "FAIL"),
    }


def assess_positions(net, limits=None):
    """net: daily account returns of a position strategy at full planned exposure."""
    L = {**DEFAULT, **(limits or {})}
    net = net.dropna()

    def stats(k):
        eq = np.cumprod(1 + k * net.to_numpy())
        return float((k * net).min()), float((eq / np.maximum.accumulate(eq) - 1).min()), eq

    def ok(k):
        w, dd, _ = stats(k)
        return w >= -L["max_trade_loss"] and dd >= -L["max_drawdown"]

    lo, hi = (1.0, 1.0) if ok(1.0) else (0.0, 1.0)
    if lo < 1.0:
        for _ in range(50):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    w1, dd1, _ = stats(1.0)
    ws, dds, eq = stats(lo)
    years = max(len(net) / 252, 1e-9)
    return {"limits": L, "planned_worst_day": w1, "planned_max_drawdown": dd1,
            "planned_verdict": "PASS" if ok(1.0) else "FAIL", "safe_exposure": float(lo),
            "safe_worst_day": ws, "safe_max_drawdown": dds,
            "safe_annual_return": float(eq[-1] ** (1 / years) - 1) if lo > 0 else 0.0,
            "verdict": "PASS" if ok(1.0) else ("PASS ONLY WHEN SIZED DOWN" if lo > 0.005 else "FAIL")}


def journal_lines(pr, kind="trade"):
    L = pr["limits"]
    if pr.get("verdict") == "NO TRADES":
        return ["- **Capital protection:** no trades to assess."]
    head = (f"- **Capital protection** (limits: worst {'trade' if kind == 'trade' else 'day'} "
            f"≥ -{L['max_trade_loss']:.0%} of account, drawdown ≥ -{L['max_drawdown']:.0%}; full history): **{pr['verdict']}**")
    if kind == "trade":
        return [head,
                f"  - at planned size ({pr['planned_allocation']:.0%} of account per trade, up to "
                f"{pr['max_concurrent_positions']} positions open at once): worst trade {pr['planned_worst_trade']:+.1%}, "
                f"account drawdown {pr['planned_max_drawdown']:.0%}",
                f"  - safe size: {pr['safe_allocation_per_trade']:.1%} of account per trade -> mean {pr['safe_mean_per_trade']:+.3%} "
                f"per trade, worst {pr['safe_worst_trade']:+.2%}, drawdown {pr['safe_max_drawdown']:.1%}, "
                f"~{pr['safe_annual_return']:+.1%}/yr"]
    return [head,
            f"  - at full exposure: worst day {pr['planned_worst_day']:+.1%}, drawdown {pr['planned_max_drawdown']:.0%}",
            f"  - safe exposure: {pr['safe_exposure']:.0%} of account -> worst day {pr['safe_worst_day']:+.2%}, "
            f"drawdown {pr['safe_max_drawdown']:.1%}, ~{pr['safe_annual_return']:+.1%}/yr"]
