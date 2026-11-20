"""Modeled option prices for backtests (no free historical option data exists).

Model, kept deliberately simple and conservative:
  - Black-Scholes, European exercise (early assignment ignored), no dividends
  - risk-free rate = 13-week T-bill (^IRX) on the day
  - ATM implied vol: index = VIX_TO_ATM x VIX; stock = VRP x blend(20d, 252d realised vol)
    (implied vol usually trades a little above realised: the variance risk premium)
  - skew: iv(K) = iv_atm * (1 + SKEW * ln(S/K)), so OTM puts are dearer, OTM calls cheaper
  - costs per leg per side: half-spread max(SPREAD_PCT x premium, MIN_HALF_SPREAD) plus
    $0.65 commission per contract. Speculative names deserve a wider SPREAD_PCT.
validate_options.py compares this model with Cboe's real PUT index; read its output before
trusting results, and always label option results as MODELED.
"""
import math

import numpy as np
import pandas as pd

SKEW = 0.8
VIX_TO_ATM = 0.91  # fitted 2007-2016 (bias 0); 2017-2026 check: +0.08%/month optimistic, corr 0.98
VRP = 1.03  # index IV/RV is ~1.07 (validate_options.py); single stocks carry less premium -> conservative for sellers
SPREAD_PCT = 0.05
MIN_HALF_SPREAD = 0.02
COMMISSION = 0.0065  # $0.65 per 100-share contract, per share


def _ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs(S, K, T, r, iv, kind):
    """Black-Scholes price per share. kind 'C' or 'P'. T in years."""
    if T <= 1e-6 or iv <= 1e-6:
        return max(S - K, 0.0) if kind == "C" else max(K - S, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * iv * iv) * T) / (iv * math.sqrt(T))
    d2 = d1 - iv * math.sqrt(T)
    if kind == "C":
        return S * _ncdf(d1) - K * math.exp(-r * T) * _ncdf(d2)
    return K * math.exp(-r * T) * _ncdf(-d2) - S * _ncdf(-d1)


def delta(S, K, T, r, iv, kind):
    if T <= 1e-6:
        return float(S > K) if kind == "C" else -float(S < K)
    d1 = (math.log(S / K) + (r + 0.5 * iv * iv) * T) / (iv * math.sqrt(T))
    return _ncdf(d1) if kind == "C" else _ncdf(d1) - 1.0


def iv_at(iv_atm, S, K):
    return float(np.clip(iv_atm * (1.0 + SKEW * math.log(S / K)), 0.5 * iv_atm, 2.5 * iv_atm))


def strike_increment(S):
    return 0.5 if S < 25 else 1.0 if S < 200 else 5.0


def round_strike(K, S):
    inc = strike_increment(S)
    return max(inc, round(K / inc) * inc)


def strike_for_delta(S, T, r, iv_atm, target, kind):
    """Strike whose |delta| is closest to target (e.g. 0.30), on the listed-strike grid."""
    lo, hi = S * 0.3, S * 3.0
    for _ in range(60):
        K = 0.5 * (lo + hi)
        d = abs(delta(S, K, T, r, iv_at(iv_atm, S, K), kind))
        # call delta falls as K rises; |put delta| rises as K rises
        if (kind == "C" and d > target) or (kind == "P" and d < target):
            lo = K
        else:
            hi = K
    return round_strike(0.5 * (lo + hi), S)


def leg_cost(premium):
    return max(SPREAD_PCT * premium, MIN_HALF_SPREAD) + COMMISSION


def atm_iv_series(df, index_vix=None):
    """Daily ATM implied-vol estimate known at each close (no lookahead)."""
    if index_vix is not None:
        return (VIX_TO_ATM * index_vix / 100.0).reindex(df.index).ffill()
    r = np.log(df["Close"]).diff()
    rv20 = r.rolling(20).std() * np.sqrt(252)
    rv252 = r.rolling(252, min_periods=60).std() * np.sqrt(252)
    return (VRP * (0.5 * rv20 + 0.5 * rv252.fillna(rv20))).clip(lower=0.10)


def rate_series(df, irx_close):
    return (irx_close / 100.0).reindex(df.index).ffill().fillna(0.02)


# ------------------------------------------------------------------ structures
# Each structure: open(S, T, r, ivatm, params) -> dict(legs, capital, entry_cost)
# legs: list of (qty, kind, K) where kind in 'S' (stock), 'C', 'P'; qty +1 long, -1 short.

def _legs_value(legs, S, T, r, ivatm):
    v = 0.0
    for q, kind, K in legs:
        v += q * (S if kind == "S" else bs(S, K, T, r, iv_at(ivatm, S, K), kind))
    return v


def open_structure(name, S, T, r, ivatm, p):
    d = p.get("short_delta", 0.30)
    w = p.get("width_pct", 0.05)
    if name == "stock_long":
        legs = [(1, "S", None)]
    elif name == "stock_short":
        legs = [(-1, "S", None)]
    elif name == "covered_call":
        legs = [(1, "S", None), (-1, "C", strike_for_delta(S, T, r, ivatm, d, "C"))]
    elif name == "collar":
        legs = [(1, "S", None), (-1, "C", strike_for_delta(S, T, r, ivatm, d, "C")),
                (1, "P", strike_for_delta(S, T, r, ivatm, p.get("put_delta", 0.20), "P"))]
    elif name == "cash_secured_put":
        legs = [(-1, "P", strike_for_delta(S, T, r, ivatm, d, "P"))]
    elif name == "put_credit_spread":
        k1 = strike_for_delta(S, T, r, ivatm, d, "P")
        legs = [(-1, "P", k1), (1, "P", round_strike(k1 * (1 - w), S))]
    elif name == "call_debit_spread":
        k1 = strike_for_delta(S, T, r, ivatm, p.get("long_delta", 0.50), "C")
        legs = [(1, "C", k1), (-1, "C", round_strike(k1 * (1 + w), S))]
    elif name == "long_call":
        legs = [(1, "C", strike_for_delta(S, T, r, ivatm, p.get("long_delta", 0.50), "C"))]
    elif name == "long_put":
        legs = [(1, "P", strike_for_delta(S, T, r, ivatm, p.get("long_delta", 0.50), "P"))]
    else:
        raise ValueError(f"unknown instrument {name}")
    legs = [(q, k, K) for q, k, K in legs if k == "S" or K > 0]
    v0 = _legs_value(legs, S, T, r, ivatm)
    entry_cost = sum(leg_cost(bs(S, K, T, r, iv_at(ivatm, S, K), k)) for q, k, K in legs if k != "S")
    # capital = cash the position ties up (what a 1% return is measured against)
    if name == "cash_secured_put":
        capital = legs[0][2] - (-v0)  # strike collateral minus premium received
    elif name == "put_credit_spread":
        capital = (legs[0][2] - legs[1][2]) - (-v0)  # width minus credit = max loss
    elif name == "stock_short":
        capital = S
    else:
        capital = abs(v0)  # stock+options net debit, or option premium paid
    return {"legs": legs, "v0": v0, "capital": max(capital, 1e-6), "entry_cost": entry_cost}


def mark(pos, S, T, r, ivatm):
    return _legs_value(pos["legs"], S, T, r, ivatm)


def exit_cost(pos, S, T, r, ivatm, at_expiry):
    c = 0.0
    for q, k, K in pos["legs"]:
        if k == "S":
            continue
        val = bs(S, K, T, r, iv_at(ivatm, S, K), k)
        if at_expiry and val <= 0:
            continue  # expires worthless: nothing to trade
        c += leg_cost(val)
    return c
